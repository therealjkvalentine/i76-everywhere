/* ffbfocus.c - stock force feedback across Alt-Tab and level restarts (I76_FFB_REACQUIRE, default 1; I76_FFB_TRACE, default 0)
 * Gold and Nitro (nitro-parity lane 2026-10-24: the exe reads through NA, the hook site through the site map); included by strlkproxy.c. Record: docs/records/FFB-FOCUS-2026-10-24.md.
 *
 * The owner's case (2026-10-24, RC proxy 53944fb2, T300, stock FFB): after a level restart and Alt-Tab the wheel's effects
 * came and went, then i76.exe died at I7_SFRCE.DLL+0x2505 reading 0. The sequence, from the DLL (md5 687cc35b, the
 * SideWinder SDK helper) and the exe:
 *   - WM_ACTIVATEAPP 0 (0x404afb) calls ffb_ForcesOff 0x445b60: block+8 = 0, then I7FF_SIM_Effect. The DLL (0x1000373a)
 *     sends SendForceFeedbackCommand(DISFFC_STOPALL) and RELEASES its six weapon-slot effects (0x10013998..0x100139ac).
 *     Every other effect (engine 0x10013994 / 0x10013990 / 0x1001398c, the rest at 0x100139b0..0x100139d8) is stopped and
 *     kept; nothing ever starts it again until the exe asks for that effect anew. That is "lost FFB after tabbing away".
 *   - WM_ACTIVATEAPP 1 (0x404aa7) calls ffb_ForcesOn 0x445b40. The DLL re-creates a slot effect lazily, on the next shot,
 *     through its template creator (0x10002336, `call ecx`). The DLL opened the device DISCL_EXCLUSIVE | DISCL_BACKGROUND
 *     ONCE at boot (0x10003850) and never calls Acquire again. When the device is not exclusively acquired at that moment
 *     the creator fails (0x80040205 DIERR_NOTEXCLUSIVEACQUIRED: the hr in the crash record's stack, [esp+0x10]), the slot
 *     stays NULL, and when the shot's parameter differs from the cached one the code at 0x100024cb calls Stop
 *     ([edx+0x20]) or GetParameters ([edx+0x14], the faulting `mov eax,[edx]` at +0x2505) on the NULL slot.
 * The fix, all in-process and only when the DLL is that exact build:
 *   1. NULL guard: +0x24b2 (`mov eax,[esp+0x38]; cmp [eax+8],ebp; je +0x2547`) jumps to a stub that first tests the slot
 *      (edx) and takes the function's own "no parameter change" path (+0x2547, which already NULL-checks before
 *      SetParameters / Start) when it is NULL. The shot loses its kick; the game does not die.
 *   2. Re-acquire: the device's Acquire is called again whenever the game is active and forces are on, on every
 *      activation, every 2 s, and right after any DirectInput call of the DLL fails with NOTEXCLUSIVEACQUIRED /
 *      NOTACQUIRED / INPUTLOST (that call is then retried once).
 *   3. Restart: effects that were playing with an infinite duration when STOPALL (or a lost acquisition) stopped them are
 *      started again (Start(1, 0), as the DLL starts them) on the next activation with the device acquired.
 * The DirectInput calls are observed by patching the IDirectInputDevice2A and IDirectInputEffect vtables of dinput.dll in
 * this process (the DLL's are the only DirectInput objects of that interface here). I76_FFB_TRACE=1 logs every call. */

#define FFR_DIERR_NOTEXCL   ((HRESULT)0x80040205L)
#define FFR_DIERR_NOTACQ    ((HRESULT)0x8007000CL)
#define FFR_DIERR_INPUTLOST ((HRESULT)0x8007001EL)
#define FFR_ACQ_ERR(h) ((h) == FFR_DIERR_NOTEXCL || (h) == FFR_DIERR_NOTACQ || (h) == FFR_DIERR_INPUTLOST)

static int g_ffr_on = -1, g_ffr_trace, g_ffr_state;       /* state: 0 not looked, 1 hooked, 2 refused (other DLL / no device) */
static BYTE *g_ffr_base;
static void *g_ffr_dev;
static DWORD g_ffr_tick, g_ffr_prev_active = 2, g_ffr_prev_forces = 2, g_ffr_need_check, g_ffr_lost;
static DWORD g_ffr_sfr_4bf, g_ffr_sfr_547;
static volatile LONG g_ffr_null_skips;
static LONG g_ffr_null_logged;
static DWORD g_ffr_n_reacq, g_ffr_n_retry_ok, g_ffr_n_retry_fail, g_ffr_n_restart, g_ffr_n_acqfail;
static DWORD g_ffr_n_start_ok, g_ffr_n_start_fail, g_ffr_n_create_ok, g_ffr_n_create_fail, g_ffr_n_setp_ok, g_ffr_n_setp_fail;
static DWORD g_ffr_n_stopall, g_ffr_n_unacq, g_ffr_n_acq_calls, g_ffr_n_cycles;
static DWORD g_ffr_cyc_start_ok, g_ffr_cyc_start_fail, g_ffr_cyc_create_ok, g_ffr_cyc_create_fail, g_ffr_cyc_setp_ok, g_ffr_cyc_null;

typedef HRESULT (__stdcall *ffr_fn0)(void *);
typedef ULONG   (__stdcall *ffr_fnrel)(void *);
typedef HRESULT (__stdcall *ffr_fn1)(void *, DWORD);
typedef HRESULT (__stdcall *ffr_fnp)(void *, void *);
typedef HRESULT (__stdcall *ffr_fnpd)(void *, void *, DWORD);
typedef HRESULT (__stdcall *ffr_fndd)(void *, DWORD, DWORD);
typedef HRESULT (__stdcall *ffr_fncreate)(void *, const GUID *, const void *, void **, void *);
static ffr_fn0 o_dev_acq, o_dev_unacq;
static ffr_fncreate o_dev_create;
static ffr_fnp o_dev_ffstate;
static ffr_fn1 o_dev_cmd;
static void **g_ffr_eff_vt;
static ffr_fnrel o_eff_release;
static ffr_fnpd o_eff_getp, o_eff_setp;
static ffr_fndd o_eff_start;
static ffr_fn0 o_eff_stop, o_eff_download;
static ffr_fnp o_eff_status;
static int g_ffr_keep_blur, g_ffr_blurred;
static DWORD g_ffr_n_blur;
static void ffr_count_playing(int *playing, int *known);

/* the effects the DLL holds, as far as the hooks saw them */
#define FFR_MAXEFF 64
static struct { void *e; DWORD dur; int playing, restart; } g_ffr_eff[FFR_MAXEFF];
static int ffr_slot(void *e, int add) {
    int i, fr = -1;
    for (i = 0; i < FFR_MAXEFF; i++) { if (g_ffr_eff[i].e == e) return i; if (!g_ffr_eff[i].e && fr < 0) fr = i; }
    if (add && fr >= 0) { g_ffr_eff[fr].e = e; g_ffr_eff[fr].dur = 0; g_ffr_eff[fr].playing = g_ffr_eff[fr].restart = 0; }
    return add ? fr : -1;
}
static const char *ffr_rva(void *ret) {               /* "+0x1234" for a return address inside I7_SFRCE.DLL */
    static char b[24]; DWORD_PTR r = (DWORD_PTR)ret, base = (DWORD_PTR)g_ffr_base;
    if (base && r > base && r < base + 0x19000) wsprintfA(b, "+0x%lX", (unsigned long)(r - base)); else wsprintfA(b, "%p", ret);
    return b;
}
/* NA(): Nitro's addresses (0x526a6c, 0x4f2d58; site map) - Nitro runs the same ffb code and the same I7_SFRCE.DLL (nitro-parity lane 2026-10-24) */
static int ffr_game_active(void) { return *(volatile DWORD *)(DWORD_PTR)NA(0x00504c1c) != 0; }
static int ffr_forces_on(void)   { return *(volatile DWORD *)(DWORD_PTR)NA(0x004f2330) != 0; }

static void ffr_mark_restart(const char *why) {
    int i, n = 0;
    for (i = 0; i < FFR_MAXEFF; i++)
        if (g_ffr_eff[i].e && g_ffr_eff[i].playing) {
            g_ffr_eff[i].playing = 0;
            if (g_ffr_eff[i].dur == 0xFFFFFFFFu) { g_ffr_eff[i].restart = 1; n++; }
        }
    if (g_ffr_trace || n) mlog("  ffb-focus: %s stopped the playing effects; %d infinite one(s) to restart on the next activation", why, n);
}
/* Acquire the device again. 1 = acquired (now or already), 0 = could not. */
static int ffr_acquire(const char *why) {
    HRESULT r;
    if (!g_ffr_dev || !o_dev_acq || g_ffr_state != 1) return 0;
    r = o_dev_acq(g_ffr_dev); g_ffr_n_acq_calls++;
    if (r == 0) {                                   /* DI_OK: it was NOT acquired, now it is */
        g_ffr_n_reacq++; g_ffr_lost = 0;
        mlog("  ffb-focus: device RE-ACQUIRED (%s; it had lost its exclusive acquisition) - re-acquire #%lu, tick %lu",
             why, (unsigned long)g_ffr_n_reacq, (unsigned long)g_ffr_tick);
        ffr_mark_restart("the lost acquisition");
        return 1;
    }
    if (r > 0) return 1;                            /* S_FALSE (DI_NOEFFECT): it was acquired already */
    if (g_ffr_n_acqfail++ < 20 || g_ffr_trace) mlog("  ffb-focus: Acquire FAILED hr 0x%08lX (%s, tick %lu)", (unsigned long)r, why, (unsigned long)g_ffr_tick);
    return 0;
}
static void ffr_restart_pending(void) {
    int i, n = 0, bad = 0;
    for (i = 0; i < FFR_MAXEFF; i++)
        if (g_ffr_eff[i].e && g_ffr_eff[i].restart) {
            HRESULT r = o_eff_start(g_ffr_eff[i].e, 1, 0);
            g_ffr_eff[i].restart = 0;
            if (r >= 0) { g_ffr_eff[i].playing = 1; n++; g_ffr_n_start_ok++; g_ffr_cyc_start_ok++; } else { bad++; g_ffr_n_start_fail++; g_ffr_cyc_start_fail++; }
        }
    g_ffr_n_restart += n;
    if (n || bad) mlog("  ffb-focus: restarted %d infinite effect(s) the stop had ended (%d failed), tick %lu", n, bad, (unsigned long)g_ffr_tick);
}

/* ---- device hooks (IDirectInputDevice2A) ---- */
static HRESULT __stdcall h_dev_acq(void *t) {
    HRESULT r = o_dev_acq(t);
    if (g_ffr_trace) mlog("  ffb-trace: dev Acquire -> 0x%08lX tick %lu", (unsigned long)r, (unsigned long)g_ffr_tick);
    return r;
}
static HRESULT __stdcall h_dev_unacq(void *t) {
    HRESULT r = o_dev_unacq(t); g_ffr_n_unacq++;
    mlog("  ffb-focus: dev Unacquire (from %s) -> 0x%08lX tick %lu", ffr_rva(_ReturnAddress()), (unsigned long)r, (unsigned long)g_ffr_tick);
    return r;
}
static void ffr_hook_effect_vt(void *eff);
static HRESULT __stdcall h_dev_create(void *t, const GUID *g, const void *de, void **pe, void *unk) {
    void *ret = _ReturnAddress();
    HRESULT r = o_dev_create(t, g, de, pe, unk), r0 = r;
    if (r < 0 && FFR_ACQ_ERR(r) && g_ffr_on && ffr_game_active() && ffr_acquire("CreateEffect failed")) {
        r = o_dev_create(t, g, de, pe, unk);
        if (r >= 0) g_ffr_n_retry_ok++; else g_ffr_n_retry_fail++;
    }
    if (r >= 0) { g_ffr_n_create_ok++; g_ffr_cyc_create_ok++; } else { g_ffr_n_create_fail++; g_ffr_cyc_create_fail++; }
    if (r >= 0 && pe && *pe) { ffr_hook_effect_vt(*pe); ffr_slot(*pe, 1); }
    if (g_ffr_trace || (r < 0 && g_ffr_n_create_fail <= 20))
        mlog("  ffb-trace: dev CreateEffect (from %s) -> 0x%08lX%s eff %p tick %lu", ffr_rva(ret), (unsigned long)r,
             r0 != r ? " (after a re-acquire; first try failed)" : "", pe ? *pe : 0, (unsigned long)g_ffr_tick);
    return r;
}
static HRESULT __stdcall h_dev_ffstate(void *t, void *st) { return o_dev_ffstate(t, st); }
static HRESULT __stdcall h_dev_cmd(void *t, DWORD c) {
    HRESULT r = o_dev_cmd(t, c);
    if (c & 0x3) {                                 /* only a stop while the game is inactive (the WM_ACTIVATEAPP 0 forces-off) is undone */
        g_ffr_n_stopall++;
        if (!ffr_game_active()) ffr_mark_restart((c & 1) ? "DISFFC_RESET (game inactive)" : "DISFFC_STOPALL (game inactive)");
        else { int i; for (i = 0; i < FFR_MAXEFF; i++) g_ffr_eff[i].playing = g_ffr_eff[i].restart = 0; }
    }
    if (g_ffr_trace) mlog("  ffb-trace: dev SendForceFeedbackCommand(0x%lX) (from %s) -> 0x%08lX tick %lu", (unsigned long)c,
                          ffr_rva(_ReturnAddress()), (unsigned long)r, (unsigned long)g_ffr_tick);
    return r;
}

/* ---- effect hooks (IDirectInputEffect) ---- */
static ULONG __stdcall h_eff_release(void *t) {
    ULONG n = o_eff_release(t);
    if (n == 0) { int i = ffr_slot(t, 0); if (i >= 0) g_ffr_eff[i].e = 0; }
    if (g_ffr_trace) mlog("  ffb-trace: eff %p Release (from %s) -> %lu", t, ffr_rva(_ReturnAddress()), (unsigned long)n);
    return n;
}
static HRESULT __stdcall h_eff_getp(void *t, void *de, DWORD f) { return o_eff_getp(t, de, f); }
static HRESULT __stdcall h_eff_setp(void *t, void *de, DWORD f) {
    HRESULT r = o_eff_setp(t, de, f), r0 = r;
    if (r < 0 && FFR_ACQ_ERR(r) && g_ffr_on && ffr_game_active() && ffr_acquire("SetParameters failed")) {
        r = o_eff_setp(t, de, f);
        if (r >= 0) g_ffr_n_retry_ok++; else g_ffr_n_retry_fail++;
    }
    if (r >= 0) { g_ffr_n_setp_ok++; g_ffr_cyc_setp_ok++; } else g_ffr_n_setp_fail++;
    if ((g_ffr_trace && (r < 0 || r0 != r || g_ffr_n_setp_ok <= 40)) || (r < 0 && g_ffr_n_setp_fail <= 20)) mlog("  ffb-trace: eff %p SetParameters(0x%lX) (from %s) -> 0x%08lX%s", t, (unsigned long)f,
                          ffr_rva(_ReturnAddress()), (unsigned long)r, r0 != r ? " (retried after a re-acquire)" : "");
    return r;
}
static HRESULT __stdcall h_eff_start(void *t, DWORD it, DWORD f) {
    HRESULT r = o_eff_start(t, it, f), r0 = r; int i;
    if (r < 0 && FFR_ACQ_ERR(r) && g_ffr_on && ffr_game_active() && ffr_acquire("Start failed")) {
        r = o_eff_start(t, it, f);
        if (r >= 0) g_ffr_n_retry_ok++; else g_ffr_n_retry_fail++;
    }
    if (r >= 0) { g_ffr_n_start_ok++; g_ffr_cyc_start_ok++; } else { g_ffr_n_start_fail++; g_ffr_cyc_start_fail++; }
    if ((i = ffr_slot(t, 1)) >= 0) {
        if (!g_ffr_eff[i].dur) {                    /* the duration once: DIEP_DURATION into a DX5 DIEFFECT (0x34 bytes) */
            DWORD de[13]; memset(de, 0, sizeof de); de[0] = 0x34;
            g_ffr_eff[i].dur = o_eff_getp(t, de, 1) >= 0 ? (de[2] ? de[2] : 1) : 1;
        }
        g_ffr_eff[i].playing = r >= 0; g_ffr_eff[i].restart = 0;
    }
    if (g_ffr_trace || (r < 0 && g_ffr_n_start_fail <= 20))
        mlog("  ffb-trace: eff %p Start(%lu, 0x%lX) (from %s) -> 0x%08lX%s dur %s tick %lu", t, (unsigned long)it, (unsigned long)f,
             ffr_rva(_ReturnAddress()), (unsigned long)r, r0 != r ? " (retried after a re-acquire)" : "",
             i >= 0 && g_ffr_eff[i].dur == 0xFFFFFFFFu ? "INFINITE" : "finite", (unsigned long)g_ffr_tick);
    return r;
}
static HRESULT __stdcall h_eff_stop(void *t) {
    HRESULT r = o_eff_stop(t); int i = ffr_slot(t, 0);
    if (i >= 0) g_ffr_eff[i].playing = g_ffr_eff[i].restart = 0;
    if (g_ffr_trace) mlog("  ffb-trace: eff %p Stop (from %s) -> 0x%08lX", t, ffr_rva(_ReturnAddress()), (unsigned long)r);
    return r;
}
static HRESULT __stdcall h_eff_download(void *t) {
    HRESULT r = o_eff_download(t), r0 = r;
    if (r < 0 && FFR_ACQ_ERR(r) && g_ffr_on && ffr_game_active() && ffr_acquire("Download failed")) {
        r = o_eff_download(t);
        if (r >= 0) g_ffr_n_retry_ok++; else g_ffr_n_retry_fail++;
    }
    if (g_ffr_trace) mlog("  ffb-trace: eff %p Download (from %s) -> 0x%08lX%s", t, ffr_rva(_ReturnAddress()), (unsigned long)r,
                          r0 != r ? " (retried after a re-acquire)" : "");
    return r;
}

static int ffr_vt_put(void **vt, int idx, void *fn, void **orig) {
    DWORD op;
    if (!VirtualProtect(&vt[idx], sizeof(void *), PAGE_READWRITE, &op)) return 0;
    *orig = vt[idx]; vt[idx] = fn;
    VirtualProtect(&vt[idx], sizeof(void *), op, &op);
    return vt[idx] == fn;
}
static void ffr_hook_effect_vt(void *eff) {
    void **vt = *(void ***)eff; int ok;
    if (g_ffr_eff_vt == vt) return;
    if (g_ffr_eff_vt) { mlog("  ffb-focus: an effect with another vtable %p (hooked %p) - not traced", (void *)vt, (void *)g_ffr_eff_vt); return; }
    g_ffr_eff_vt = vt;
    ok  = ffr_vt_put(vt, 2,  (void *)h_eff_release,  (void **)&o_eff_release);
    ok &= ffr_vt_put(vt, 5,  (void *)h_eff_getp,     (void **)&o_eff_getp);
    ok &= ffr_vt_put(vt, 6,  (void *)h_eff_setp,     (void **)&o_eff_setp);
    ok &= ffr_vt_put(vt, 7,  (void *)h_eff_start,    (void **)&o_eff_start);
    ok &= ffr_vt_put(vt, 8,  (void *)h_eff_stop,     (void **)&o_eff_stop);
    ok &= ffr_vt_put(vt, 10, (void *)h_eff_download, (void **)&o_eff_download);
    o_eff_status = (ffr_fnp)vt[9];                  /* GetEffectStatus: read, not hooked (the transition lines count playing effects) */
    mlog("  ffb-focus: IDirectInputEffect vtable %p hooked (Release GetParameters SetParameters Start Stop Download): %s", (void *)vt, ok ? "ok" : "FAILED");
}

/* the NULL-slot guard in the DLL: replaces `mov eax,[esp+0x38]; cmp [eax+8],ebp; je +0x2547` at +0x24b2 */
static __declspec(naked) void ffr_null_stub(void) {
    __asm {
        test edx, edx
        jz nul
        mov eax, [esp + 0x38]
        cmp dword ptr [eax + 8], ebp
        je skip
        jmp dword ptr [g_ffr_sfr_4bf]
    nul:                                            /* count only where the stock code would have dereferenced the NULL slot */
        mov eax, [esp + 0x38]
        cmp dword ptr [eax + 8], ebp
        je skip
        mov ecx, [esp + 0x18]
        mov eax, [esp + 0x24]
        cmp eax, [ecx]
        je skip
        lock inc dword ptr [g_ffr_null_skips]
    skip:
        jmp dword ptr [g_ffr_sfr_547]
    }
}

static void ffr_init(void) {
    static const BYTE site[13] = { 0x8b, 0x44, 0x24, 0x38, 0x39, 0x68, 0x08, 0x0f, 0x84, 0x88, 0x00, 0x00, 0x00 };
    static const BYTE crash[4] = { 0x8b, 0x02, 0x8d, 0x4c };           /* +0x2505 mov eax,[edx]; lea ecx,... */
    HMODULE h = GetModuleHandleA("I7_SFRCE.DLL"); BYTE *b, w[13]; void **vt; DWORD op; LONG rel; int ok;
    static int tries;
    if (!h) { if (++tries > 600) { g_ffr_state = 2; mlog("  ffb-focus: I7_SFRCE.DLL never loaded - nothing to do"); } return; }
    b = (BYTE *)h; g_ffr_base = b; g_ffr_state = 2;
    if (memcmp(b + 0x24b2, site, 13) != 0 || memcmp(b + 0x2505, crash, 4) != 0 || b[0x36d0] != 0xa1
        || *(DWORD *)(b + 0x36d1) != (DWORD)(DWORD_PTR)(b + 0x138c8) || *(DWORD *)(b + 0x1be4) != (DWORD)(DWORD_PTR)(b + 0x138cc)) {
        mlog("  ffb-focus: I7_SFRCE.DLL at %p is not the build this knows (md5 687cc35b) - nothing changed", (void *)b);
        return;
    }
    g_ffr_sfr_4bf = (DWORD)(DWORD_PTR)(b + 0x24bf); g_ffr_sfr_547 = (DWORD)(DWORD_PTR)(b + 0x2547);
    if (!g_ffr_on) { mlog("  ffb-focus: NULL-slot guard NOT installed (I76_FFB_REACQUIRE=0, trace only)"); goto hooks; }
    memset(w, 0x90, sizeof w); w[0] = 0xE9; rel = (LONG)((DWORD_PTR)ffr_null_stub - (DWORD_PTR)(b + 0x24b2 + 5)); memcpy(w + 1, &rel, 4);
    ok = VirtualProtect(b + 0x24b2, 13, PAGE_EXECUTE_READWRITE, &op);
    if (ok) { memcpy(b + 0x24b2, w, 13); VirtualProtect(b + 0x24b2, 13, op, &op); FlushInstructionCache(GetCurrentProcess(), b + 0x24b2, 13); }
    mlog("  ffb-focus: NULL-slot guard at I7_SFRCE.DLL+0x24b2 (the +0x2505 fault): %s", ok && memcmp(b + 0x24b2, w, 13) == 0 ? "in, read back ok" : "FAILED");
hooks:
    g_ffr_dev = *(void **)(b + 0x138cc);
    if (!g_ffr_dev) { mlog("  ffb-focus: the DLL has no device (I7FF_InitSystem found no force-feedback joystick) - guard only"); return; }
    vt = *(void ***)g_ffr_dev;
    ok  = ffr_vt_put(vt, 7,  (void *)h_dev_acq,     (void **)&o_dev_acq);
    ok &= ffr_vt_put(vt, 8,  (void *)h_dev_unacq,   (void **)&o_dev_unacq);
    ok &= ffr_vt_put(vt, 18, (void *)h_dev_create,  (void **)&o_dev_create);
    ok &= ffr_vt_put(vt, 21, (void *)h_dev_ffstate, (void **)&o_dev_ffstate);
    ok &= ffr_vt_put(vt, 22, (void *)h_dev_cmd,     (void **)&o_dev_cmd);
    mlog("  ffb-focus: device %p, IDirectInputDevice2A vtable %p hooked (Acquire Unacquire CreateEffect GetForceFeedbackState SendForceFeedbackCommand): %s; re-acquire %s, trace %s",
         g_ffr_dev, (void *)vt, ok ? "ok" : "FAILED", g_ffr_on ? "on" : "off (I76_FFB_REACQUIRE=0: observe only)", g_ffr_trace ? "on" : "off");
    g_ffr_state = ok ? 1 : 2;
    { DWORD st = 0; HRESULT r = o_dev_ffstate(g_ffr_dev, &st);
      mlog("  ffb-focus: at hook time GetForceFeedbackState -> 0x%08lX state 0x%lX", (unsigned long)r, (unsigned long)st); }
}

/* effects the device reports playing (DIEGES_PLAYING), out of those the hooks know */
static void ffr_count_playing(int *playing, int *known) {
    int i; *playing = *known = 0;
    if (!o_eff_status) return;
    for (i = 0; i < FFR_MAXEFF; i++) if (g_ffr_eff[i].e) { DWORD st = 0; (*known)++; if (o_eff_status(g_ffr_eff[i].e, &st) >= 0 && (st & 1)) (*playing)++; }
}
/* Called at the top of every ffb_PlayEffect 0x446110 (the per-frame FFB tick 0x445e83 and the forces on / off calls),
 * on the game thread, before the exe hands the block to I7FF_SIM_Effect. */
static void __cdecl ffr_tick(void) {
    DWORD act, frc;
    g_ffr_tick++;
    if (g_ffr_state == 0) ffr_init();
    if (g_ffr_state != 1) return;
    /* I7FF_ExitSystem (game exit) releases the device and zeroes [+0x138cc] / [+0x138c8]; a WM_ACTIVATEAPP 0 during the exit still
     * reaches ffb_PlayEffect. Never touch the device after that (the lab's observe-only run of 2026-10-24 23:38 faulted in ntdll
     * on the freed device from here). A device the DLL opens again (its lazy re-init) is taken over as the new one. */
    {   void *d = *(void * volatile *)(g_ffr_base + 0x138cc);
        if (d != g_ffr_dev || !*(volatile DWORD *)(g_ffr_base + 0x138c8)) {
            int i;
            mlog("  ffb-focus: the DLL's device changed %p -> %p (init %lu) at tick %lu - %s", g_ffr_dev, d,
                 (unsigned long)*(volatile DWORD *)(g_ffr_base + 0x138c8), (unsigned long)g_ffr_tick, d ? "following the new one" : "standing down");
            for (i = 0; i < FFR_MAXEFF; i++) g_ffr_eff[i].e = 0;
            g_ffr_dev = d;
            if (!d || !*(volatile DWORD *)(g_ffr_base + 0x138c8)) { g_ffr_dev = 0; g_ffr_state = 4; return; }
        }
    }
    act = ffr_game_active(); frc = ffr_forces_on();
    if (g_ffr_blurred && act) {                     /* the first FFB call after a kept-on blur: the activation's ffb_ForcesOn */
        DWORD st = 0; HRESULT r = o_dev_ffstate(g_ffr_dev, &st); int pl, kn;
        ffr_count_playing(&pl, &kn); g_ffr_blurred = 0; g_ffr_n_cycles++;
        mlog("  ffb-focus: focus back #%lu (tick %lu): GetForceFeedbackState -> 0x%08lX state 0x%lX%s; effects STILL playing %d of %d known (nothing restarted yet); since the previous return Start ok %lu fail %lu, CreateEffect ok %lu fail %lu, SetParameters ok %lu, NULL slots skipped %ld",
             (unsigned long)g_ffr_n_cycles, (unsigned long)g_ffr_tick, (unsigned long)r, (unsigned long)st,
             r == FFR_DIERR_NOTEXCL || r == FFR_DIERR_NOTACQ ? " = NOT ACQUIRED" : "", pl, kn,
             (unsigned long)g_ffr_cyc_start_ok, (unsigned long)g_ffr_cyc_start_fail, (unsigned long)g_ffr_cyc_create_ok,
             (unsigned long)g_ffr_cyc_create_fail, (unsigned long)g_ffr_cyc_setp_ok, (long)(g_ffr_null_skips - (LONG)g_ffr_cyc_null));
        g_ffr_cyc_start_ok = g_ffr_cyc_start_fail = g_ffr_cyc_create_ok = g_ffr_cyc_create_fail = g_ffr_cyc_setp_ok = 0;
        g_ffr_cyc_null = (DWORD)g_ffr_null_skips;
        if (r == FFR_DIERR_NOTEXCL || r == FFR_DIERR_NOTACQ) g_ffr_lost = 1;
        g_ffr_need_check = 1;
    }
    if (act != g_ffr_prev_active || frc != g_ffr_prev_forces) {
        DWORD st = 0; HRESULT r = o_dev_ffstate(g_ffr_dev, &st); int pl, kn;
        ffr_count_playing(&pl, &kn);
        if (act && !g_ffr_prev_active && g_ffr_prev_active != 2) {   /* an activation: one focus cycle ends here */
            g_ffr_n_cycles++;
            mlog("  ffb-focus: cycle %lu ended (tick %lu): since the last activation Start ok %lu fail %lu, CreateEffect ok %lu fail %lu, SetParameters ok %lu, NULL slots skipped %ld",
                 (unsigned long)g_ffr_n_cycles, (unsigned long)g_ffr_tick, (unsigned long)g_ffr_cyc_start_ok, (unsigned long)g_ffr_cyc_start_fail,
                 (unsigned long)g_ffr_cyc_create_ok, (unsigned long)g_ffr_cyc_create_fail, (unsigned long)g_ffr_cyc_setp_ok,
                 (long)(g_ffr_null_skips - (LONG)g_ffr_cyc_null));
            g_ffr_cyc_start_ok = g_ffr_cyc_start_fail = g_ffr_cyc_create_ok = g_ffr_cyc_create_fail = g_ffr_cyc_setp_ok = 0;
            g_ffr_cyc_null = (DWORD)g_ffr_null_skips;
        }
        mlog("  ffb-focus: game %s, forces %s (tick %lu): GetForceFeedbackState -> 0x%08lX state 0x%lX%s; effects playing %d of %d known", act ? "ACTIVE" : "inactive",
             frc ? "on" : "off", (unsigned long)g_ffr_tick, (unsigned long)r, (unsigned long)st,
             r == FFR_DIERR_NOTEXCL || r == FFR_DIERR_NOTACQ ? " = NOT ACQUIRED" : "", pl, kn);
        if (r == FFR_DIERR_NOTEXCL || r == FFR_DIERR_NOTACQ) g_ffr_lost = 1;
        if (act && frc) g_ffr_need_check = 1;
        g_ffr_prev_active = act; g_ffr_prev_forces = frc;
    }
    if (g_ffr_null_skips != g_ffr_null_logged) {
        g_ffr_null_logged = g_ffr_null_skips;
        if (g_ffr_null_logged <= 20 || (g_ffr_null_logged & 63) == 0)
            mlog("  ffb-focus: weapon effect with no effect object skipped (the +0x2505 fault avoided), %ld so far, tick %lu", (long)g_ffr_null_logged, (unsigned long)g_ffr_tick);
    }
    if (!g_ffr_on || !act || !frc) return;
    /* [0x52bbe4] = 0: the custom interposer (tools/ffb, Tel-SetEngineFfb) holds the wheel and has switched the game's effects off -
     * never take the device back from it */
    if (*(volatile DWORD *)(DWORD_PTR)NA(0x0052bbe4) == 0) return;
    if (g_ffr_need_check || g_ffr_lost || (g_ffr_tick % 120) == 0) {
        g_ffr_need_check = 0;
        if (ffr_acquire(g_ffr_lost ? "lost at the last check" : "activation / periodic check")) ffr_restart_pending();
    }
}

/* keep-on-blur: what WM_ACTIVATEAPP 0 calls instead of ffb_ForcesOff (0x445b60). The forces stay on; this only records the
 * focus loss (device state, effects playing), so the activation tick can say what survived the time in the background. */
static void __cdecl ffr_on_blur(void) {
    int pl = 0, kn = 0; DWORD st = 0; HRESULT r = 0;
    g_ffr_blurred = 1; g_ffr_n_blur++;
    if (g_ffr_state == 1 && g_ffr_dev) { r = o_dev_ffstate(g_ffr_dev, &st); ffr_count_playing(&pl, &kn); }
    mlog("  ffb-focus: focus lost #%lu (tick %lu): forces kept ON; GetForceFeedbackState -> 0x%08lX state 0x%lX; effects playing %d of %d known",
         (unsigned long)g_ffr_n_blur, (unsigned long)g_ffr_tick, (unsigned long)r, (unsigned long)st, pl, kn);
}
static void ffr_config(void) {
    if (g_ffr_on >= 0) return;
    g_ffr_on = env_flag("I76_FFB_REACQUIRE", 8, 1) == 1;
    g_ffr_trace = env_flag("I76_FFB_TRACE", 8, 0) == 1;
    if (!g_ffr_on && !g_ffr_trace) { g_ffr_state = 3; mlog("  ffb-focus: off (I76_FFB_REACQUIRE=0)"); return; }
    if (g_ffr_on && env_flag("I76_FFB_KEEP_ON_BLUR", 8, 1) == 1) {
        /* WM_ACTIVATEAPP 0 calls ffb_ForcesOff (`call 0x445b60` at 0x404afb): the DLL then STOPALLs and releases the weapon
         * slots. Skipped: the device (DISCL_EXCLUSIVE | DISCL_BACKGROUND) and its effects stay with the game while it is in the
         * background or paused; the activation's ffb_ForcesOn (0x404aa7) then finds the forces on already. */
        static const BYTE call_off[5] = { 0xE8, 0x60, 0x10, 0x04, 0x00 }; BYTE w[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)ffr_on_blur - ((DWORD_PTR)NA(0x00404afb) + 5)); memcpy(w + 1, &rel, 4);
        g_ffr_keep_blur = patch_bytes(0x00404afb, call_off, w, 5, "ffb-keep-on-blur");
        mlog("  ffb-focus: keep-on-blur: WM_ACTIVATEAPP 0 no longer turns the forces off (0x404afb call 0x445b60 -> call ffr_on_blur, which only logs): %s",
             g_ffr_keep_blur && memcmp((const void *)(DWORD_PTR)NA(0x00404afb), w, 5) == 0 ? "read back ok" : "NOT applied");
    }
    mlog("  ffb-focus: armed (re-acquire %s, NULL-slot guard %s, keep-on-blur %s, trace %s); hooks go in at the first ffb_PlayEffect once I7_SFRCE.DLL is loaded",
         g_ffr_on ? "on" : "off", g_ffr_on ? "on" : "off", g_ffr_keep_blur ? "on" : "off", g_ffr_trace ? "on" : "off");
}
