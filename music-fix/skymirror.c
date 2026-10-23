/* ===========================================================================
 * I76_SKY_MIRROR=0: the rear-view mirror's pass does not scroll the sky  (opt-in; nitro-port lane, NITRO-PORT s.11, 2026-10-22)
 * ===========================================================================
 * Included from strlkproxy.c after simtick.c; applied after every switch that repoints the cloud scroll (simtick.c's cosmetic
 * patch, I76_FRAMERATE_FIXES).
 *
 * THE QUANTITY. The cloud scroll is advanced inside the sky draw (Gold 0x405200 / Nitro 0x434380): every call
 *     u = fmod(u - k_u / (1001 - s), 1.0)   v = fmod(v - k_v / (1001 - s), 1.0)   (k_u = 1.0 at 0x4bc4c4, k_v = -1.0 at 0x4bc500;
 *     u double 0x507cd8 / Nitro 0x529b20, s = the mission's sky speed 0x504c30 / 0x526a78)
 * The sky draw is called by the main view (0x401cc0 / 0x401fa0) AND by the rear-view mirror (Gold 0x445750 from 0x401cfe /
 * 0x401fde; Nitro 0x42c7e0 from 0x4308ce / 0x430b9e), so with the mirror on the sky scrolls once more per mirror frame:
 * Gold AiO (our 6319abf7) draws the mirror every frame (x 2.0; the 2017 Galaxy exe every second frame, see I76_MIRROR_RATE),
 * Nitro every second frame (0x42c844: frame counter 0x5b22e4 + 2; x 1.5, measured on the Mac: cockpit 1.50, intro camera
 * 1.00, mirror option off 1.00). Retail 1.0 does the same with its own sky draw (0x407b40, step 1/1024 per call, called
 * from the view 0x4076e5 and from the mirror 0x471390 at 0x47153b; no refresh gate read in 0x471390: every frame). The owner's 1997 reference (86Box P166, lowest
 * detail) runs with the mirror OFF.
 *
 * THE SWITCH. =0 zeroes the per-call constants for the mirror's call of the sky draw only (the mirror still draws its sky
 * picture; the main view scrolls it once per frame): the scroll per second is then the one-pass rate whatever the mirror
 * setting (24 / (1001 - s) per s under the tick or at 24 fps, retail mirror off 24 / 1024). Unset / 1 = stock. Works with or
 * without the tick: when nothing else repointed the two constants, this switch repoints them to its own 1.0 / -1.0.
 * Signature-checked (each call site must call the stock mirror function or a chain of ours); Gold and Nitro (site map).
 */
static float g_sm_u = 1.0f, g_sm_v = -1.0f;
static float *g_sm_pu, *g_sm_pv;                 /* what the sky draw reads for k_u / k_v (ours, or simtick / ratefix's) */
static DWORD g_sm_next[2];                       /* the mirror function each site called */
static volatile LONG g_sm_calls;
static void sm_mirror(int i) {
    float u = *g_sm_pu, v = *g_sm_pv;
    *g_sm_pu = 0.0f; *g_sm_pv = 0.0f;
    ((void (__cdecl *)(void))(DWORD_PTR)g_sm_next[i])();
    *g_sm_pu = u; *g_sm_pv = v;
    InterlockedIncrement(&g_sm_calls);
}
static void __cdecl sm_mirror0(void) { sm_mirror(0); }
static void __cdecl sm_mirror1(void) { sm_mirror(1); }
static float *sm_site_operand(DWORD site, const BYTE *stock6, float *mine, const char *what) {
    BYTE *p = (BYTE *)(DWORD_PTR)NA(site), w[6] = { 0xD9, 0x05 };
    DWORD a;
    if (!p || p[0] != 0xD9 || p[1] != 0x05) { mlog("  sky-mirror: %s at 0x%08lX is not fld [m32] - off", what, (unsigned long)site); return 0; }
    memcpy(&a, p + 2, 4);
    if (a != (DWORD)NA(*(const DWORD *)(stock6 + 2))) return (float *)(DWORD_PTR)a;   /* simtick / ratefix took it: zero theirs */
    a = (DWORD)(DWORD_PTR)mine; memcpy(w + 2, &a, 4);
    return patch_bytes(site, stock6, w, 6, what) ? mine : 0;
}
static void apply_sky_mirror(void) {
    static const BYTE cu_old[6] = { 0xD9, 0x05, 0xC4, 0xC4, 0x4B, 0x00 }, cv_old[6] = { 0xD9, 0x05, 0x00, 0xC5, 0x4B, 0x00 };
    int n = 0;
    if (env_flag("I76_SKY_MIRROR", 8, 1) != 0) return;
    {   char mv[4]; DWORD mk = env_str("I76_MIRROR_RATE", mv, sizeof(mv));   /* Gold's I76_MIRROR_RATE wraps the mirror's own cloud call */
        if (mk && mv[0] != '0' && g_ratefix) { mlog("  sky-mirror: I76_MIRROR_RATE owns the mirror's cloud step - off"); return; } }
    if (!(g_sm_pu = sm_site_operand(0x00405461, cu_old, &g_sm_u, "cloud scroll u (sky-mirror)")) ||
        !(g_sm_pv = sm_site_operand(0x00405484, cv_old, &g_sm_v, "cloud scroll v (sky-mirror)"))) { mlog("  sky-mirror: cloud constants not reachable - off"); return; }
    n += st_call_site(0x00401cfe, 0x00445750, (void *)sm_mirror0, &g_sm_next[0], "mirror render call, hardware path (sky-mirror)");
    n += st_call_site(0x00401fde, 0x00445750, (void *)sm_mirror1, &g_sm_next[1], "mirror render call, software path (sky-mirror)");
    mlog("  sky-mirror: ON - the rear-view mirror's sky draw does not scroll the clouds (%d/2 mirror call sites; constants %s)",
         n, g_sm_pu == &g_sm_u ? "repointed here" : "shared with the tick / rate fixes");
}
