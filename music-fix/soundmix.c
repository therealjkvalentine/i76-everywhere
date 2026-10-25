/* soundmix.c - SOUND BALANCE: per-category gains, the music slider curve, and Nitro's lost SFX / voice volume
 * (nitro-polish lane 2026-10-24; docs/records/NITRO-POLISH-2026-10-24.md s.3). Included from strlkproxy.c after polish.c.
 *
 * How the engine sets a voice's loudness (Gold 0x4217e0 = Nitro 0x419cc0..., static, both exes read side by side):
 *   millibels = T[ trunc(vol% (voice +0x1c) x 0.1 x L) ],  T[0] = -10000, T[i] = 400 x log2(i / 100)  (table Gold 0x5fcc20, Nitro 0x654680)
 *   L = the SFX level (manager +0x14) or, for a voice with flag 4 (+0x14; the CB / mission speech), the voice level (+0x18), 0..10.
 *   IDirectSoundBuffer::SetVolume(millibels) at Gold 0x421854 / Nitro 0x419d2c - the only SetVolume call in either exe.
 * So the SFX and voice sliders fall 4 dB per halving (T), while the music slider (auxSetVolume -> the proxy's MCI
 * `setaudio volume` 0..1000 -> mciqtz32 AmpFactorToDB(v x 65535 / 1000)) is linear in amplitude: 6 dB per halving.
 *
 * NITRO: the volume is never applied while DirectSound 3D is up. Gold skips that block only when [0x52467c] is set (zeroed at
 * DirectSound start, 0x425c4d, never set); Nitro tests the manager's 3D listener (+8) instead: `mov eax, [mgr + 8]; test; jne`
 * to the 3D update at 0x419cee. With a listener (every normal boot) neither slider nor any sound's own volume % reaches
 * DirectSound: every SFX and every voice line plays at the buffer's 0 dB. I76_NITRO_3D_VOLUME (default 1 on Nitro) runs the
 * stock volume block first on that path too (Gold's order: volume, then the 3D update). 0 = stock Nitro.
 *
 * I76_SFX_GAIN=<dB>, I76_VOICE_GAIN=<dB> (both exes, -40..+20, default 0): added to the millibels at the SetVolume call
 * (a silent voice, T[0], stays silent; the result is clamped to DirectSound's -10000..0, so a positive gain only lifts a
 * level below the top of the slider).
 * I76_MUSIC_GAIN=<dB> (-40..+20): the MCI volume x 10^(dB / 20), capped at 1000.
 * I76_MUSIC_CURVE=sfx: the music slider follows the SFX / voice curve (amplitude = level ^ 0.664, -4 dB per halving)
 * instead of the stock linear one, so equal sliders give equal mix gain; unset = stock.
 * I76_SOUND_VOL_LOG=1 (lab): the first 300 SetVolume calls (name, flags, vol %, level, mB stock -> sent) and a census line
 * every 10 s (calls, by category, and the Nitro 3D-path applications).
 */
static int g_smx_on, g_smx_log, g_smx_n3d;
static LONG g_smx_gain[2];                                    /* millibels: [0] SFX, [1] voice */
static DWORD g_smx_ftol = 0x004ba090;                         /* the ftol call replaced at the SetVolume site (chained target) */
static DWORD g_smx_calls[2], g_smx_n3d_calls, g_smx_logged, g_smx_last;
static LONG g_smx_mb_lo[2] = { 1, 1 }, g_smx_mb_hi[2] = { -20000, -20000 };

static float sm_env_db(const char *name, float lo, float hi, int *set) {
    char v[32]; float f;
    *set = 0;
    if (!env_str(name, v, sizeof(v))) return 0.0f;
    f = (float)atof(v);
    if (f < lo || f > hi) { mlog("  sound-mix: %s=%s out of range (%.0f..%.0f dB) - ignored", name, v, lo, hi); return 0.0f; }
    *set = 1; return f;
}

static LONG __cdecl sm_adjust(BYTE *v, LONG mb) {
    int cat = (v && (*(DWORD *)(v + 0x14) & 4)) ? 1 : 0;
    LONG out = mb;
    if (mb > -10000) { out = mb + g_smx_gain[cat]; if (out > 0) out = 0; if (out < -10000) out = -10000; }
    g_smx_calls[cat]++;
    if (out < g_smx_mb_lo[cat] || g_smx_mb_lo[cat] == 1) g_smx_mb_lo[cat] = out;
    if (out > g_smx_mb_hi[cat]) g_smx_mb_hi[cat] = out;
    if (g_smx_log) {
        BYTE *mgr = *(BYTE **)(DWORD_PTR)NA(0x00524564);
        if (g_smx_logged < 300 && v) {
            char nm[17]; lstrcpynA(nm, (const char *)(v + 4), 17);
            g_smx_logged++;
            mlog("  sound-vol: %-16s flags %04lx vol %5.1f %% %s level %d -> %ld mB stock, %ld sent", nm, (unsigned long)(*(DWORD *)(v + 0x14) & 0xffff),
                 *(float *)(v + 0x1c), cat ? "voice" : "sfx", mgr ? *(int *)(mgr + (cat ? 0x18 : 0x14)) : -1, (long)mb, (long)out);
        }
        if (GetTickCount() - g_smx_last >= 10000) {
            g_smx_last = GetTickCount();
            mlog("  sound-vol: census - SetVolume sfx %lu (%ld..%ld mB), voice %lu (%ld..%ld mB); Nitro 3D-path volume applications %lu; levels sfx %d voice %d; listener %p (3D flag %ld)",
                 (unsigned long)g_smx_calls[0], (long)g_smx_mb_lo[0], (long)g_smx_mb_hi[0], (unsigned long)g_smx_calls[1], (long)g_smx_mb_lo[1], (long)g_smx_mb_hi[1],
                 (unsigned long)g_smx_n3d_calls, mgr ? *(int *)(mgr + 0x14) : -1, mgr ? *(int *)(mgr + 0x18) : -1, mgr ? *(void **)(mgr + 8) : 0, (long)*(volatile LONG *)(DWORD_PTR)(g_exe == EXE_NITRO ? 0x004f1e84 : 0x004ed7e4));
            if (mgr) {   /* the active voice list (manager +0x1c, next at +0): what is sounding now, to catch a voice that never ends */
                char buf[1400]; int o = 0, guard = 0; BYTE *e;
                for (e = *(BYTE **)(mgr + 0x1c); e && guard++ < 64 && o < 1300; e = *(BYTE **)e) {
                    char nm[17]; BYTE *db = *(BYTE **)(e + 0x54); DWORD hz = 0, st = 0; LONG vl = 1;
                    lstrcpynA(nm, (const char *)(e + 4), 17);
                    if (db) {   /* the buffer's own view: GetFrequency (vtbl 8), GetStatus (9), GetVolume (6) */
                        ((HRESULT (__stdcall *)(void *, DWORD *))(*(void ***)db)[8])(db, &hz);
                        ((HRESULT (__stdcall *)(void *, DWORD *))(*(void ***)db)[9])(db, &st);
                        ((HRESULT (__stdcall *)(void *, LONG *))(*(void ***)db)[6])(db, &vl);
                    }
                    o += _snprintf(buf + o, sizeof(buf) - o, " %s[m%d ka%d v%.0f f%04lx o%p 3d%d hz%.0f/%lu st%lx mB%ld]", nm, *(int *)(e + 0x3c), *(BYTE *)(e + 0x74),
                                   *(float *)(e + 0x1c), (unsigned long)(*(DWORD *)(e + 0x14) & 0xffff), *(void **)(e + 0x5c), *(void **)(e + 0x58) ? 1 : 0,
                                   *(float *)(e + 0x18), (unsigned long)hz, (unsigned long)st, (long)vl);
                }
                buf[o < (int)sizeof(buf) ? o : (int)sizeof(buf) - 1] = 0;
                mlog("  sound-vol: active%s", buf);
            }
        }
    }
    return out;
}

/* replaces the `call ftol` that turns T[idx] into the SetVolume argument (Gold 0x42184d, Nitro 0x419d25): esi = the voice */
static __declspec(naked) void sm_ftol_stub(void) {
    __asm {
        call dword ptr [g_smx_ftol]                /* eax = the stock millibels (pops st0, as the original) */
        push eax
        push esi
        call sm_adjust
        add esp, 8
        ret
    }
}

/* Nitro: the stock volume block (0x419cf0..0x419d2c) for a voice on the 3D path */
static void __cdecl sm_nitro3d_apply(BYTE *v) {
    BYTE *mgr = *(BYTE **)(DWORD_PTR)0x00523114, *buf;
    DWORD fl; int L, idx; float f; LONG mb;
    if (!g_smx_n3d || !v || !mgr) return;
    fl = *(DWORD *)(v + 0x14);
    if (!(fl & 0x40)) return;                                 /* as 0x419cf3: only when the voice's volume is marked changed */
    L = *(int *)(mgr + ((fl & 4) ? 0x18 : 0x14));
    f = *(float *)(v + 0x1c) * *(float *)(DWORD_PTR)0x004c1b18 * (float)L;
    idx = (int)f;                                             /* ftol truncates */
    if (idx < 0) idx = 0; if (idx > 100) idx = 100;
    mb = (LONG)((float *)(DWORD_PTR)0x00654680)[idx];
    mb = sm_adjust(v, mb);
    buf = *(BYTE **)(v + 0x54);
    if (!buf) return;
    g_smx_n3d_calls++;
    ((HRESULT (__stdcall *)(void *, LONG))(*(void ***)buf)[15])(buf, mb);   /* IDirectSoundBuffer::SetVolume, as 0x419d2c */
}
/* at Nitro 0x419ce9 (`mov eax, [ecx + 8]; test eax, eax`, 5 bytes; the `jne 0x419d3f` after it is kept): ecx = the manager */
static __declspec(naked) void sm_nitro3d_stub(void) {
    __asm {
        mov eax, dword ptr [ecx + 8]
        test eax, eax
        jz done
        pushad
        push esi
        call sm_nitro3d_apply
        add esp, 4
        popad
        mov eax, dword ptr [ecx + 8]
        test eax, eax
    done:
        ret
    }
}

/* music: the slider position (aux peak 0..0xFFFF) -> the MCI volume 0..1000 (strlkproxy.c hook_auxSetVolume) */
static int g_smx_mus_read, g_smx_mus_curve; static float g_smx_mus_k = 1.0f;
static DWORD sm_music_volume(DWORD peak) {
    double f = (double)peak / 65535.0, v;
    if (!g_smx_mus_read) {
        char c[16]; int set; float db;
        g_smx_mus_read = 1;
        db = sm_env_db("I76_MUSIC_GAIN", -40.0f, 20.0f, &set);
        if (set) g_smx_mus_k = (float)pow(10.0, db / 20.0);
        g_smx_mus_curve = env_str("I76_MUSIC_CURVE", c, sizeof(c)) && _stricmp(c, "sfx") == 0;
        if (set || g_smx_mus_curve)
            mlog("  sound-mix: music %s, gain %+.1f dB (I76_MUSIC_GAIN / I76_MUSIC_CURVE)", g_smx_mus_curve ? "on the SFX / voice slider curve (level ^ 0.664)" : "stock linear slider", set ? db : 0.0f);
    }
    if (g_smx_mus_curve) f = f > 0.0 ? pow(f, 0.6644) : 0.0;
    v = f * 1000.0 * g_smx_mus_k;
    if (v > 1000.0) v = 1000.0;
    return (DWORD)(v + 0.5);
}

/* NITRO 3D SOUND: Nitro asks for 3D only through Aureal A3D. Its DirectSound start 0x41bea0, with the 3D flag [0x4f1e84] = 1 (data),
 * does CoCreateInstance(A3D's CLSID 0x4c1b30, IID 0x4c5468) + Initialize; when that fails (no A3D driver: every machine since
 * ~2000) it clears the 3D flag (`mov [ebp], ebx` at 0x41bf16) and takes DirectSoundCreate. With the flag 0 the primary buffer is
 * made without DSBCAPS_CTRL3D (0x41bfe7) and no listener is asked for (0x41c162): every voice is 2D, at its full volume whatever
 * its distance (measured: listener 0, flag 0 on the console and headless, n 4 boots). Gold always uses DirectSound 3D (flags
 * 0x11, listener QI at 0x425db9; min 10 m, max 400 m, rolloff 1). I76_NITRO_DS3D (default 1 on Nitro) keeps the flag on that
 * fallback: plain DirectSound with 3D, as Gold. 0 = stock Nitro (no 3D). */
static void apply_nitro_ds3d(void) {
    static const BYTE old[7] = { 0x53, 0x56, 0x53, 0x89, 0x5d, 0x00, 0xe8 }, nop3[3] = { 0x90, 0x90, 0x90 };
    BYTE *p = (BYTE *)(DWORD_PTR)0x0041bf13; DWORD o;
    if (g_exe != EXE_NITRO) return;
    if (env_flag("I76_NITRO_DS3D", 8, 1) != 1) { mlog("  nitro-ds3d: off (I76_NITRO_DS3D=0) - stock Nitro: no A3D -> 2D sound, no distance attenuation"); return; }
    if (memcmp(p, old, 7) != 0) { mlog("  nitro-ds3d: 0x41bf13 is not the stock bytes - not applied"); return; }
    if (!VirtualProtect(p + 3, 3, PAGE_EXECUTE_READWRITE, &o)) return;
    memcpy(p + 3, nop3, 3); VirtualProtect(p + 3, 3, o, &o);
    if (memcmp(p + 3, nop3, 3) != 0) { mlog("  nitro-ds3d: write did not read back - not applied"); return; }
    InterlockedIncrement(&g_nsite_ok);
    mlog("  nitro-ds3d: on - no A3D: the 3D flag is kept on the DirectSound fallback (0x41bf16 `mov [ebp], ebx` -> nop): 3D primary buffer + listener, as Gold");
}

static void apply_sound_mix(void) {
    int s1, s2; float a, b;
    apply_nitro_ds3d();
    a = sm_env_db("I76_SFX_GAIN", -40.0f, 20.0f, &s1);
    b = sm_env_db("I76_VOICE_GAIN", -40.0f, 20.0f, &s2);
    g_smx_gain[0] = (LONG)(a * 100.0f + (a < 0 ? -0.5f : 0.5f)); g_smx_gain[1] = (LONG)(b * 100.0f + (b < 0 ? -0.5f : 0.5f));
    g_smx_log = env_flag("I76_SOUND_VOL_LOG", 8, 0) == 1;
    g_smx_n3d = g_exe == EXE_NITRO && env_flag("I76_NITRO_3D_VOLUME", 8, 1) == 1;
    if (g_exe == EXE_NITRO && !g_smx_n3d) mlog("  sound-mix: I76_NITRO_3D_VOLUME=0 - stock Nitro (with a 3D listener no SFX / voice volume reaches DirectSound)");
    if (!s1 && !s2 && !g_smx_log && !g_smx_n3d) return;
    if (g_exe == EXE_NITRO) {
        static const BYTE blk[16] = { 0x8b, 0x0d, 0x14, 0x31, 0x52, 0x00, 0x8b, 0x41, 0x08, 0x85, 0xc0, 0x75, 0x4f, 0x8b, 0x46, 0x14 };   /* 0x419ce3 */
        static const BYTE vol[13] = { 0xd9, 0x04, 0x85, 0x80, 0x46, 0x65, 0x00, 0xe8, 0x9c, 0x5e, 0x0a, 0x00, 0x50 };                     /* 0x419d1e */
        const BYTE *p = (const BYTE *)(DWORD_PTR)0x00419ce3;
        if (memcmp(p, blk, 16) != 0 || memcmp((const void *)(DWORD_PTR)0x00419d1e, vol, 13) != 0) {
            mlog("  sound-mix: Nitro's volume block 0x419ce3 / 0x419d1e is not the stock bytes - not applied"); g_smx_n3d = 0; return;
        }
        if (!nitro_patch_call(0x00419d25, 0x004bfbc6, (void *)sm_ftol_stub, &g_smx_ftol, "SetVolume millibels (sound-mix)")) { g_smx_n3d = 0; return; }
        if (g_smx_n3d) {
            BYTE w[5] = { 0xE8 }; DWORD old; LONG rel = (LONG)((DWORD_PTR)sm_nitro3d_stub - (0x00419ce9 + 5));
            memcpy(w + 1, &rel, 4);
            if (VirtualProtect((void *)(DWORD_PTR)0x00419ce9, 5, PAGE_EXECUTE_READWRITE, &old)) {
                memcpy((void *)(DWORD_PTR)0x00419ce9, w, 5); VirtualProtect((void *)(DWORD_PTR)0x00419ce9, 5, old, &old);
            }
            if (memcmp((const void *)(DWORD_PTR)0x00419ce9, w, 5) != 0) { mlog("  sound-mix: Nitro 3D-path site 0x419ce9 write did not read back - 3D volume off"); g_smx_n3d = 0; }
            else { InterlockedIncrement(&g_nsite_ok); mlog("  nitro-only site 3D-path volume (sound-mix): 0x419ce9 -> stub, patched"); }
        }
    } else if (g_exe == EXE_GOLD) {
        if (!st_call_site(0x0042184d, 0x004ba090, (void *)sm_ftol_stub, &g_smx_ftol, "SetVolume millibels (sound-mix)")) return;
    } else { mlog("  sound-mix: unknown exe - not applied"); return; }
    g_smx_on = 1;
    mlog("  sound-mix: on - SFX %+.1f dB, voice %+.1f dB at the SetVolume call%s%s", g_smx_gain[0] / 100.0, g_smx_gain[1] / 100.0,
         g_exe == EXE_NITRO ? (g_smx_n3d ? "; Nitro 3D path applies the SFX / voice volume (I76_NITRO_3D_VOLUME=1)" : "; Nitro 3D path stock") : "",
         g_smx_log ? "; log on (I76_SOUND_VOL_LOG)" : "");
}
