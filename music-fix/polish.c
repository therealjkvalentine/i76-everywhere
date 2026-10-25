/* ===========================================================================
 * OWNER POLISH 2026-10-20 (docs/records/MENU-SOUND-POLISH-2026-10-20.md; included from strlkproxy.c before simtick.c)
 * ===========================================================================
 *
 * I76_SIGN_SOUND_RESTART=1 (off by default; on in the staged tick19 presets). Owner, play-test of the release candidate:
 * "i would really like the barricade hit sound to interrupt a playing barricade hit sound when triggered/appropriate
 * because it would sound a lot cooler to hit them and hear as they get closer together".
 *   The sound. A class-4 object (sign post, road-closed barricade) hit by a car plays vnvco3.wav on the CAR:
 *   physics_CollideBodyPair 0x434e5c..0x434ebc -> sound_PlayOnObject 0x4231f0 -> sound_StartObjectSound 0x421b40
 *   (I76_BREAKABLE_BOX's sweep plays the same call, simtick.c st_sign_sound). vnvco3.gpw's GAS0 header is all -1, so
 *   the defaults hold: priority 50, ONE instance, one-shot, 0.386 s (11025 Hz mono 8-bit, 4256 samples).
 *   Why a hit is dropped. The voice admission 0x422750 counts the active voices with the same name (0x422850..0x42287a)
 *   and, at the instance limit (voice +0x38 = 1), takes a voice of that name only if the new one's priority is
 *   strictly higher (0x4228b0 jg); the same car asking again has the same priority, so 0x422750 refuses and
 *   0x425130 / 0x421b40 return 0: the second hit inside 0.386 s plays nothing.
 *   The switch. Before the engine's call, if a vnvco3 voice is playing ON THAT CAR (0x4221d0 finds it by object and
 *   name, as setSiren's stop does) and the hit is a new one, that voice is stopped and freed with the engine's own
 *   stop 0x421e70 (-> 0x425ef0: Stop + Release + free, the path the per-frame update takes when a one-shot ends), then
 *   the engine's call starts the sound afresh. "New hit": the object hit (the tree root, +0x68 parents, of the other
 *   body's part [edi+4] at 0x434ebc; the sign the sweep knocks a post off) has not started or restarted the sound in
 *   the last 1.5 s. A barricade whose bar and legs touch the car over several passes therefore restarts the sound once,
 *   not every pass; the next barricade along the road (T05's ten swend_1, two pairs 5 m apart) restarts it. Other
 *   cars' voices and other names are never touched.
 *   Log: I76_SIGN_SOUND_LOG=1 (lab) logs every vnvco3 request (first 400: path, car, object hit, playing voice before,
 *   restarted, started or refused) and a total line every 25 requests; counting runs whether the restart is on or not,
 *   so the same log reads "before" (switch off) and "after".
 *
 * I76_FADE_NO_FLIP=1 (off by default; on in the staged tick19 presets). Owner: "when you click to exit the game two
 * frames flip back and forth really fast - this is not new, has always happened, but it looks a little buggy".
 *   Cause. The exe's palette fade 0x479a90 (fade-out 0x479c60: 32 steps, 10 ms each; called on leaving the mission
 *   0x4036af / 0x4041da / 0x404341 and after the mission-over menu 0x4044c7 = Exit Game, Abort, Replay ...) uploads a
 *   palette (0x5dd2c8) and PRESENTS (call [0x5dd2e0] at 0x479bdd) every step. Under the hardware (Glide) renderer the
 *   palette changes nothing on screen and nothing is drawn between the swaps, so each step flips to the other buffer:
 *   the last two frames alternate 32 times (~0.32 s).
 *   The switch. The present inside the fade loop (0x479bdd only) is skipped while the hardware renderer is live
 *   ([0x5dd2a8] == 1, renderer_IsHardwareDevice 0x495060); the palette uploads and the 10 ms step waits are unchanged,
 *   so the fade takes as long as before and the screen holds the last frame. The software renderer keeps its present
 *   (there the palette IS the fade). Log line at load; with I76_FADE_LOG=1 (lab) or I76_SIGN_SOUND_LOG=1 a line at a fade's 1st, 8th, 16th, 24th, 32nd step.
 */
static int st_call_site(DWORD site, DWORD stock, void *wrap, DWORD *chain, const char *what);   /* simtick.c */
static int g_mk;                                             /* I76_MENU_KEYS (below), read by simtick.c st_input_changed */
static int mpm_write(BYTE *p, const BYTE *expect, const BYTE *want, int n);   /* mpmenu.c */

/* ---- I76_SIGN_SOUND_RESTART ---------------------------------------------------------------------------------------- */
#define SSR_NAME ((const char *)(DWORD_PTR)NA(0x004f1578))  /* "vnvco3.wav" (0x434e62 pushes it) */
static int g_ssr, g_ssr_log;
static DWORD g_ssr_next = 0x004231f0;                        /* the call at 0x434ebc (chained if another hook is there) */
static BYTE *g_ssr_other;                                    /* [edi+4] at 0x434ebc: the other body of the contact */
static DWORD g_ssr_req, g_ssr_started, g_ssr_refused, g_ssr_restarted, g_ssr_same, g_ssr_logged;
static struct { BYTE *other; DWORD tick; } g_ssr_seen[32];
static int g_ssr_seen_i;
static int ssr_new_hit(BYTE *other) {                        /* 1 = this body has not (re)started the sound in the last 1.5 s */
    DWORD now = GetTickCount(); int i;
    if (!other) return 1;
    for (i = 0; i < 32; i++) if (g_ssr_seen[i].other == other && now - g_ssr_seen[i].tick < 1500) return 0;
    return 1;
}
static void ssr_note(BYTE *other) {
    int i;
    if (!other) return;
    for (i = 0; i < 32; i++) if (g_ssr_seen[i].other == other) { g_ssr_seen[i].tick = GetTickCount(); return; }
    g_ssr_seen[g_ssr_seen_i].other = other; g_ssr_seen[g_ssr_seen_i].tick = GetTickCount(); g_ssr_seen_i = (g_ssr_seen_i + 1) & 31;
}
/* the vnvco3 request for car (other = the post / part, 0 if unknown); play = the call that starts it. Returns its result. */
static int ssr_play(const char *path, BYTE *car, BYTE *other, int (__cdecl *play)(const char *, BYTE *, int), int f) {
    BYTE *v = 0; int restarted = 0, nh, r;
#ifdef _MSC_VER
    __try {
#endif
        if (car) v = ((BYTE *(__cdecl *)(const char *, BYTE *))(DWORD_PTR)NA(0x004221d0))(SSR_NAME, car);   /* the voice playing it on this car */
        nh = ssr_new_hit(other);
        if (v && g_ssr) {
            if (nh) { ((void (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x00421e70))(v); restarted = 1; g_ssr_restarted++; }   /* NA: Nitro 0x41a310 (nitro-owner lane 2026-10-23; was Gold's address on both) */
            else g_ssr_same++;
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_ssr = 0; mlog("  sign-sound: fault in the restart - turned off"); }
#endif
    g_ssr_req++;
    r = play(SSR_NAME, car, f);
    if (r) { g_ssr_started++; if (nh || restarted) ssr_note(other); } else g_ssr_refused++;
    if (g_ssr_log) {
        if (g_ssr_logged < 400) {
            g_ssr_logged++;
            mlog("  sign-sound: %s req %lu t=%lu car %p other %p playing-before %p %s -> %s", path, (unsigned long)g_ssr_req,
                 (unsigned long)GetTickCount(), (void *)car, (void *)other, (void *)v,
                 restarted ? "RESTARTED" : (v ? (g_ssr ? "same body: kept" : "kept (switch off)") : "none playing"),
                 r ? "started" : "REFUSED");
        }
        if (g_ssr_req % 25 == 0)
            mlog("  sign-sound: totals req %lu started %lu refused %lu restarted %lu same-body %lu (restart %s)", (unsigned long)g_ssr_req,
                 (unsigned long)g_ssr_started, (unsigned long)g_ssr_refused, (unsigned long)g_ssr_restarted, (unsigned long)g_ssr_same,
                 g_ssr ? "on" : "off");
    }
    return r;
}
static int __cdecl ssr_next_call(const char *name, BYTE *obj, int f) {
    return ((int (__cdecl *)(const char *, BYTE *, int))g_ssr_next)(name, obj, f);
}
static BYTE *ssr_root(BYTE *o) {                             /* the part's tree root (the ODEF object), as bbox_speed_normal: +0x68 = parent */
    int guard = 0;
#ifdef _MSC_VER
    __try {
#endif
        while (o && *(BYTE **)(o + 0x68) && ++guard < 16) o = *(BYTE **)(o + 0x68);
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    return o;
}
static int __cdecl ssr_coll(const char *name, BYTE *obj, int f) {
    if (name != SSR_NAME) return ssr_next_call(name, obj, f);
    return ssr_play("contact", obj, ssr_root(g_ssr_other), ssr_next_call, f);
}
static __declspec(naked) void ssr_coll_thunk(void) {         /* at 0x434ebc: edi = the record of the other body (0x434dc7..0x434ddb) */
    __asm {
        mov eax, dword ptr [edi + 4]
        mov dword ptr [g_ssr_other], eax
        jmp ssr_coll
    }
}
static int __cdecl ssr_stock_call(const char *name, BYTE *obj, int f) {
    return ((int (__cdecl *)(const char *, BYTE *, int))(DWORD_PTR)NA(0x004231f0))(name, obj, f);
}
/* simtick.c st_sign_sound: the sweep's knock-off (no engine contact), root = the sign whose post was knocked off */
static void ssr_sweep_sound(BYTE *car, BYTE *root) {
    if (g_ssr || g_ssr_log) ssr_play("sweep", car, root, ssr_stock_call, 0);
    else ssr_stock_call(SSR_NAME, car, 0);
}
static void apply_sign_sound_restart(void) {
    int on = env_flag("I76_SIGN_SOUND_RESTART", 8, 0) == 1, lg = env_flag("I76_SIGN_SOUND_LOG", 8, 0) == 1;
    static const BYTE nm[11] = "vnvco3.wav";
    if (!on && !lg) return;
    if (!NA(0x00421e70) || !NA(0x004f1578) || memcmp((const void *)(DWORD_PTR)NA(0x004f1578), nm, 11) != 0) { mlog("  sign-sound: 0x4f1578 is not \"vnvco3.wav\" (unknown exe) - not applied"); return; }
    g_ssr = on; g_ssr_log = lg;
    if (!st_call_site(0x00434ebc, 0x004231f0, (void *)ssr_coll_thunk, &g_ssr_next, "collision sound (sign-sound restart)")) {
        mlog("  sign-sound: the contact sound call 0x434ebc was not patched - the sweep path only");
    }
    mlog("  sign-sound: I76_SIGN_SOUND_RESTART=%d (a new hit on a sign / barricade %s the vnvco3 playing on that car), log %s",
         g_ssr, g_ssr ? "stops and restarts" : "does not interrupt", g_ssr_log ? "on" : "off");
}

/* ---- I76_FADE_NO_FLIP -------------------------------------------------------------------------------------------- */
static int g_fade_noflip, g_fade_log;
static DWORD g_fade_steps, g_fade_skipped, g_fade_last;   /* per fade (a gap of 1 s starts a new one) */
static DWORD g_fade_hw = 0x005dd2a8, g_fade_pres = 0x005dd2e0;   /* renderer-is-hardware flag, present slot (Nitro: NA at apply) */
static void __cdecl fade_present(void *disp) {               /* replaces call [0x5dd2e0] at 0x479bdd (the fade loop's present) */
    DWORD now = GetTickCount();
    int skip = g_fade_noflip && *(volatile DWORD *)(DWORD_PTR)g_fade_hw == 1;   /* hardware renderer: the palette fades nothing */
    if (now - g_fade_last > 1000) { g_fade_steps = 0; g_fade_skipped = 0; }
    g_fade_last = now; g_fade_steps++; if (skip) g_fade_skipped++;
    if (g_fade_log && (g_fade_steps == 1 || g_fade_steps % 8 == 0))
        mlog("  fade: step %lu t=%lu, present %s (%lu skipped so far)", (unsigned long)g_fade_steps, (unsigned long)now,
             skip ? "SKIPPED" : "made", (unsigned long)g_fade_skipped);
    if (skip) return;
    ((void (__cdecl *)(void *))*(DWORD *)(DWORD_PTR)g_fade_pres)(disp);
}
static void apply_fade_no_flip(void) {
    static const BYTE o[6] = { 0xFF, 0x15, 0xE0, 0xD2, 0x5D, 0x00 };   /* call dword ptr [0x5dd2e0] */
    BYTE w[6] = { 0xE8, 0, 0, 0, 0, 0x90 };
    LONG rel;
    g_fade_noflip = env_flag("I76_FADE_NO_FLIP", 8, 0) == 1;
    g_fade_log = env_flag("I76_FADE_LOG", 8, 0) == 1 || env_flag("I76_SIGN_SOUND_LOG", 8, 0) == 1;
    if (!g_fade_noflip && !g_fade_log) return;
    g_fade_hw = NA(0x005dd2a8); g_fade_pres = NA(0x005dd2e0);
    if (!g_fade_hw || !g_fade_pres) { g_fade_noflip = 0; mlog("  fade: no Nitro address for the renderer flag / present slot - not applied"); return; }
    rel = (LONG)((DWORD_PTR)fade_present - (0x00479bdd + 5)); memcpy(w + 1, &rel, 4);
    if (!patch_bytes(0x00479bdd, o, w, 6, "palette fade present (fade-no-flip)") || (g_exe != EXE_NITRO && memcmp((void *)0x00479bdd, w, 6) != 0)) {   /* Nitro: nitro_patch_bytes read it back */
        g_fade_noflip = 0; mlog("  fade: the fade present 0x479bdd did not verify - not applied"); return;
    }
    mlog("  fade: I76_FADE_NO_FLIP=%d (the palette fade's 32 presents %s under the hardware renderer)", g_fade_noflip,
         g_fade_noflip ? "skipped" : "kept, counted");
}

/* ---- I76_ARENA_NAME (default 1; 0 = stock) ------------------------------------------------------------------------
 * Owner 2026-10-20 night: "Why is the game name populated with the next area name instead of the selected area name?"
 * When the host has not typed a GAME NAME, picking an arena on the host form copies the default name into 0x100d4050 from
 * the stock table `0x1004b510 + index * 0x2d` (i76shell a300db63, EntryForm 0x10028610: the two copies at 0x10029c5c and
 * 0x1002a2c6, `lea edi, [eax + eax*8 + 0x1004b510]` with eax = index * 5, then repne scasb / rep movs). The table has the
 * 15 stock arenas; for the add-on entries (index >= 15: AI arenas, scenarios, co-op scenes, any ADDON *.lvl) the copy read
 * past it into the next table, so the name was another entry's (COOP-LIST-ENTRIES-2026-10-18.md s.1 "Side effect").
 * The list and the AREA OF PLAY box already take an add-on's title from the add-on list ([[0x100f2194]+8] - 0x3c +
 * index * 4, 0x10029bf5 / 0x1002b37e); the two copies now do the same: each lea becomes `call arena_name_stub; nop; nop`,
 * which leaves in edi the stock entry for index < 15 and the add-on's own title for index >= 15 (index-generic: whatever
 * the add-on list holds), copied into a 45-byte buffer (the stock entry size) so the shell's copy is never longer than
 * before. Log line "arena-name: 2 / 2 default-name copies repointed"; the first 20 add-on names are logged. */
static BYTE *g_an_base;
static char g_an_buf[0x2d];
static DWORD g_an_n;
static const char *__cdecl arena_name_src(void) {
    BYTE *b = g_an_base;
    int idx = *(int *)(b + (0x100d4474u - 0x10000000u));
    const char *s = (const char *)(b + (0x1004b510u - 0x10000000u)) + (idx >= 0 && idx < 15 ? idx : 0) * 0x2d;
    if (idx >= 15) {
#ifdef _MSC_VER
        __try {
#endif
            BYTE *list = *(BYTE **)(b + (0x100f2194u - 0x10000000u));
            const char *t = list ? *(const char **)(*(BYTE **)(list + 8) - 0x3c + idx * 4) : 0;
            if (t) { lstrcpynA(g_an_buf, t, sizeof g_an_buf); s = g_an_buf; }
#ifdef _MSC_VER
        } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
        if (++g_an_n <= 20) mlog("  arena-name: entry %d -> default game name '%s'", idx, s);
    }
    return s;
}
static __declspec(naked) void arena_name_stub(void) {        /* replaces lea edi, [eax + eax*8 + 0x1004b510] (7 bytes) */
    __asm {
        push eax
        push ecx
        push edx
        call arena_name_src
        mov edi, eax
        pop edx
        pop ecx
        pop eax
        ret
    }
}
static void arena_name_attach(BYTE *base) {                   /* from mp_menu_attach (mpmenu.c), once, when i76shell is in */
    /* 2026-10-24 (owner: "when co-op missions were broadcast, the names did not make it through"; records/LAN-FIXES-2026-10-24.md s.7):
     * two more copies of the same lea read the stock table with an add-on index - the host form's init 0x10027c80 (0x10027d83,
     * the form opening on the last chosen arena) and the GAME NAME box's default when the field is left as it was (0x1002d1ef);
     * both now take the add-on's title too */
    static const DWORD site[4] = { 0x10029c5c, 0x1002a2c6, 0x10027d83, 0x1002d1ef };
    DWORD tbl = (DWORD)(DWORD_PTR)base + (0x1004b510u - 0x10000000u);
    int i, ok = 0;
    if (env_flag("I76_ARENA_NAME", 8, 1) == 0) { mlog("  arena-name: off (I76_ARENA_NAME=0): stock default game names"); return; }
    g_an_base = base;
    for (i = 0; i < 4; i++) {
        BYTE *p = base + (site[i] - 0x10000000u), o[7] = { 0x8D, 0xBC, 0xC0 }, w[7] = { 0xE8, 0, 0, 0, 0, 0x90, 0x90 };
        LONG rel = (LONG)((DWORD)(DWORD_PTR)arena_name_stub - ((DWORD)(DWORD_PTR)p + 5));
        memcpy(o + 3, &tbl, 4); memcpy(w + 1, &rel, 4);
        ok += mpm_write(p, o, w, 7);
    }
    mlog("  arena-name: %d / 4 default-name copies repointed (add-on entries name the game after their own title)%s", ok,
         ok == 4 ? ", read back OK" : " - unknown i76shell build?");
}

/* ---- I76_MENU_KEYS (default 1; 0 = stock) -------------------------------------------------------------------------
 * Owner 2026-10-20 night: "The arrow keys in the pause menu control the car?" Stock: the frame loop runs the sim block
 * (0x403a02..: collisions, input_ProcessFrame 0x44dec0 -> input_ApplyToEntity, the vehicle step) when the game is active
 * and the render-gate flags 0x4fe534 & 0x3e are clear, OR when 0x452d20 (a network game) says so (0x4039e4..0x4039fc).
 * The Esc menu (its sub-menus and the mission-over menu too) is 0x4fe534 = 0x10: single player skips the sim (the menu
 * pauses), a network game keeps it running - and input_UpdateControls 0x44d9e0 has already filled the control block
 * 0x5367c8..0x536803 (15 dwords, cleared together at 0x44dd13: the gamekey word, the throttle / steer axes, the held key
 * bytes) from the keyboard and the sticks, so the arrow keys that move the menu bar also steer the car.
 * With the switch: while 0x4fe534 == 0x10 the call input_ProcessFrame at 0x403a1c (chained: under the tick it is the
 * tick's gate) first clears the 15 dwords, so the player's car sees no key and zero axes: input_ApplyToEntity's analog
 * path sets throttle and steer to 0 (the car coasts, wheels straight; the hold timers reset) and no gamekey fires. The
 * menu's own keys come through the window procedure (WM_KEYDOWN -> 0x496e10) and are not touched; the Mac's DxWnd path
 * reaches the same frame loop, so the same clear applies there. Under the tick, I76_SIM_TICK_INPUT's early tick ignores
 * input while the menu is up (simtick.c st_input_changed). I76_MENU_KEYS_LOG=1 (lab): a line every 120th cleared frame.
 * CORRECTED 2026-10-25 (records/MP-AI-DAMAGE-RATE-2026-10-25.md s.4): the menu's keys do NOT come only through the window
 * procedure - the menu's key step 0x496e10 (from the menu-mode frame routine 0x49d000, later in the same frame) reads its key
 * from the block's FIRST dword 0x5367c8 (Enter 0xd, Tab 9, Space 0x20, Esc 0x1b, arrows 0xc6..0xc9), which the clear zeroed:
 * in a network game the Esc menu answered no key (the mouse worked). Now: save blk[0], clear, call input_ProcessFrame (the
 * car still sees nothing), then put the key back if nothing wrote the word meanwhile, so the menu consumes it; the next frame's
 * clear hides it from the car again. I76_MENU_KEYS_LOG=1 also logs each key kept. */
static int g_mk_log;
static DWORD g_mk_next = 0x0044dec0, g_mk_frames, g_mk_eaten, g_mk_kept, g_mk_mode = 0x004fe534, g_mk_blk = 0x005367c8;   /* Nitro: NA at apply */
static void __cdecl menu_keys_wrap(void) {
    if (g_mk && *(volatile DWORD *)(DWORD_PTR)g_mk_mode == 0x10) {
        DWORD *blk = (DWORD *)(DWORD_PTR)g_mk_blk; int i, any = 0;
        for (i = 0; i < 15; i++) if (blk[i]) { any = 1; break; }
        g_mk_frames++;
        if (any) {
            DWORD key = blk[0];
            g_mk_eaten++;
            if (g_mk_log && (g_mk_eaten % 120) == 1)
                mlog("  menu-keys: Esc menu up, the control block held input (throttle axis %ld, steer axis %ld, keys %08lx %08lx) - cleared (%lu frames so far)",
                     (long)(int)blk[1], (long)(int)blk[3], (unsigned long)blk[2], (unsigned long)blk[4], (unsigned long)g_mk_eaten);
            memset(blk, 0, 60);
            ((void (__cdecl *)(void))g_mk_next)();          /* the car's input_ProcessFrame sees an empty block */
            if (key && !blk[0]) {                            /* the menu's key step (0x49d000 -> 0x496e10, later in this frame) reads blk[0] */
                blk[0] = key; g_mk_kept++;
                if (g_mk_log) mlog("  menu-keys: kept the menu's key 0x%lx for the Esc menu (%lu so far)", (unsigned long)key, (unsigned long)g_mk_kept);
            }
            return;
        }
    }
    ((void (__cdecl *)(void))g_mk_next)();
}
static void apply_menu_keys(void) {
    g_mk = env_flag("I76_MENU_KEYS", 8, 1) == 1;
    g_mk_log = env_flag("I76_MENU_KEYS_LOG", 8, 0) == 1;
    if (!g_mk) { mlog("  menu-keys: off (I76_MENU_KEYS=0): stock (in a network game the Esc menu's keys also drive the car)"); return; }
    g_mk_mode = NA(0x004fe534); g_mk_blk = NA(0x005367c8);
    if (!g_mk_mode || !g_mk_blk) { g_mk = 0; mlog("  menu-keys: no Nitro address for the menu mode / control block - off"); return; }
    if (!st_call_site(0x00403a1c, 0x0044dec0, (void *)menu_keys_wrap, &g_mk_next, "input_ProcessFrame call (menu-keys)")) {
        g_mk = 0; mlog("  menu-keys: 0x403a1c not patched - off"); return;
    }
    mlog("  menu-keys: on - while the Esc menu is up (0x4fe534 = 0x10) the car gets no keys / axes (coasts); no early tick from menu keys");
}

/* ---- I76_FONT_PRIVATE (default 1; 0 = stock) ---------------------------------------------------------------------
 * Main, measured 2026-10-20 night: the game registers its font Lee_____.ttf with Windows at every boot (i76.exe 0x4769e0:
 * AddFontResourceA <current directory>\Lee_____.ttf, GDI32 slot 0x4bc078) and removes it only on its own orderly shutdown
 * path (RemoveFontResourceA 0x4bc07c, 0x4769e0 / 0x476c90); every boot that ends otherwise (a crash, a harness kill, a
 * TerminateProcess, Windows logging off) leaves one system-wide registration behind. The count grows by one per such boot
 * (the lab twin had 1,564, a plain lab copy 770) and while any is left Windows keeps the .ttf open, so the game folder can
 * be neither renamed nor deleted until the font is removed that many times or the PC restarts.
 * With the switch: i76.exe's two GDI32 slots go to font_add / font_remove, which do the same with FR_PRIVATE
 * (AddFontResourceExA / RemoveFontResourceExA): the font is this process's own, visible to its GDI text calls as before,
 * and Windows drops it when the process ends, however it ends. Log line at load and one per call. */
static int (WINAPI *p_font_addex)(LPCSTR, DWORD, PVOID);
static BOOL (WINAPI *p_font_remex)(LPCSTR, DWORD, PVOID);
static int WINAPI font_add(LPCSTR path) {
    int r = p_font_addex(path, FR_PRIVATE, NULL);
    mlog("  font-private: AddFontResourceA(\"%s\") -> AddFontResourceExA FR_PRIVATE = %d", path ? path : "(null)", r);
    return r;
}
static BOOL WINAPI font_remove(LPCSTR path) {
    BOOL r = p_font_remex(path, FR_PRIVATE, NULL);
    mlog("  font-private: RemoveFontResourceA(\"%s\") -> RemoveFontResourceExA FR_PRIVATE = %d", path ? path : "(null)", r);
    return r;
}
static void apply_font_private(void) {
    HMODULE gdi = GetModuleHandleA("gdi32.dll"), exe = GetModuleHandleA(NULL);
    int n = 0;
    if (env_flag("I76_FONT_PRIVATE", 8, 1) == 0) { mlog("  font-private: off (I76_FONT_PRIVATE=0): the font is registered system-wide as stock"); return; }
    if (!gdi) gdi = LoadLibraryA("gdi32.dll");
    p_font_addex = (int (WINAPI *)(LPCSTR, DWORD, PVOID))GetProcAddress(gdi, "AddFontResourceExA");
    p_font_remex = (BOOL (WINAPI *)(LPCSTR, DWORD, PVOID))GetProcAddress(gdi, "RemoveFontResourceExA");
    if (!p_font_addex || !p_font_remex) { mlog("  font-private: AddFontResourceExA / RemoveFontResourceExA not found - off"); return; }
    if (patch_iat(exe, "GDI32.dll", "AddFontResourceA", (void *)font_add)) n++;
    if (patch_iat(exe, "GDI32.dll", "RemoveFontResourceA", (void *)font_remove)) n++;
    mlog("  font-private: %d / 2 i76.exe GDI32 font slots -> FR_PRIVATE (the font is released when the process ends)", n);
}
