/* TERRAIN POP INSTRUMENTS  (terrain-pop lane 2026-10-23; docs/records/TERRAIN-POPS-2026-10-23.md)
 * Included by strlkproxy.c after terrainmorph.c. Lab only, off unless set. Gold only (the sites are mirrordetail.c's).
 *   I76_TEX_LEVEL_LOG=<csv>   per main terrain pass: how many leaves changed TEXTURE LEVEL since the previous pass (the picker
 *                             0x4923f0 picks level = clamp(9 - floor(log2(640 x 40 / z)), 0, 6) per leaf, i.e. a hard switch at
 *                             z = 50 / 100 / 200 / 400 / 800 / 1600 m - a whole tile changes its texture in one frame), by the
 *                             picker's own z band, with the nearest switch's z; <csv>.events.csv has one line per switch (capped).
 *   I76_SHADE_CENSUS=1        the vertex colour ZGLIDE hands glide2x (grDrawTriangle, GrVertex r at +12): a histogram of its
 *                             integer levels, so "is the Gouraud shade quantised in hardware" (renderer.md: the D3D path indexes a
 *                             64-entry grey table by 16 + round(31 s)) is settled by a count, not a reading. Report every 600 frames.
 *   I76_SHADE_SMOOTH=1        the hardware vertex shade without the 32-row quantisation: every polygon emitter (17 sites, 0x4282e0 ..
 *                             0x42cca5) turns the vertex shade s (0..1) into ZGLIDE's intensity with round(31 s) + 16 into the 64-entry
 *                             grey table 0x526790 (built from the .lum by 0x426c30, T05: 255 x8, 232 232 209 209 187 187 165 165 165
 *                             145 145 125 125 106 106 87 87 70 70 70 54 54 39 39) - so a vertex's brightness moves in steps of 20-23
 *                             grey (12 %) as its shade crosses a row boundary (flat T05 ground: at ~291 m and ~157 m from the camera,
 *                             the depth term g(z)), and the morph's shade fade walks the same steps. The switch multiplies by 255
 *                             instead and indexes a 256-entry table that interpolates the stock rows (rebuilt whenever the stock
 *                             table changes). Gold only; all 17 + 17 sites signature-checked, all or nothing.
 */
#define TP_SLOTS 65536u
#define TP_MAXL  32768u
typedef struct { unsigned __int64 k; float zp; int lvl; } tp_slot_t;
static tp_slot_t *g_tp_tab[2]; static DWORD *g_tp_use[2], g_tp_n[2]; static int g_tp_cur;
static FILE *g_tp_log, *g_tp_ev; static DWORD g_tp_frame_seen, g_tp_passes, g_tp_evn;
static DWORD g_tp_leaves, g_tp_lvl[8], g_tp_sw, g_tp_band[6], g_tp_up, g_tp_down; static float g_tp_near;
static DWORD g_sc_hist[256], g_sc_nonint, g_sc_tris; static int g_sc_on;
static int g_ss_builds;                                  /* I76_SHADE_SMOOTH (below): table builds, for the report */
static void (__stdcall *p_sc_DrawTriangle)(const void *, const void *, const void *);
static DWORD g_tp_next = 0x004923f0;                      /* the picker, or whatever another switch (mirror-detail) pushed at the site before us */
static int tp_level_of(DWORD tex) { int l; for (l = 0; l < 7; l++) if (tex && (*(DWORD *)(0x005a4588 + 8 * l) == tex || *(DWORD *)(0x005a458c + 8 * l) == tex)) return l; return 7; }

static unsigned __int64 tp_key(int x, int z, int s) { return ((unsigned __int64)(DWORD)(x & 0xffff) << 40) | ((unsigned __int64)(DWORD)(z & 0xffff) << 16) | (DWORD)(s & 0xffff); }
static tp_slot_t *tp_find(int t, unsigned __int64 k) {
    DWORD i = tm_hash(k), n; tp_slot_t *s = g_tp_tab[t];
    for (n = 0; n < 128; n++, i = (i + 1) & (TP_SLOTS - 1)) { if (!s[i].k) return NULL; if (s[i].k == k) return &s[i]; }
    return NULL;
}
static tp_slot_t *tp_put(int t, unsigned __int64 k) {
    DWORD i = tm_hash(k), n; tp_slot_t *s = g_tp_tab[t];
    for (n = 0; n < 128; n++, i = (i + 1) & (TP_SLOTS - 1)) {
        if (!s[i].k) { if (g_tp_n[t] >= TP_MAXL) return NULL; s[i].k = k; g_tp_use[t][g_tp_n[t]++] = i; return &s[i]; }
        if (s[i].k == k) return &s[i];
    }
    return NULL;
}
static void tp_clear(int t) { DWORD j; for (j = 0; j < g_tp_n[t]; j++) g_tp_tab[t][g_tp_use[t][j]].k = 0; g_tp_n[t] = 0; }
static int tp_band(float z) { return z < 50.0f ? 0 : z < 100.0f ? 1 : z < 200.0f ? 2 : z < 400.0f ? 3 : z < 800.0f ? 4 : 5; }
static void tp_close_pass(void) {                         /* the previous frame's main pass is complete: log it, swap the tables */
    if (g_tp_log && g_tp_passes) {
        fprintf(g_tp_log, "%lu,%.3f,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%.1f,%lu,%lu\n",
                (unsigned long)g_tp_frame_seen, tm_qms(), (unsigned long)g_tp_leaves,
                (unsigned long)g_tp_lvl[0], (unsigned long)g_tp_lvl[1], (unsigned long)g_tp_lvl[2], (unsigned long)g_tp_lvl[3], (unsigned long)g_tp_lvl[4], (unsigned long)g_tp_lvl[5], (unsigned long)g_tp_lvl[6], (unsigned long)g_tp_lvl[7],
                (unsigned long)g_tp_sw, (unsigned long)g_tp_band[0], (unsigned long)g_tp_band[1], (unsigned long)g_tp_band[2], (unsigned long)g_tp_band[3], (unsigned long)g_tp_band[4], (unsigned long)g_tp_band[5],
                g_tp_sw ? g_tp_near : -1.0f, (unsigned long)g_tp_up, (unsigned long)g_tp_down);
        if ((g_tp_passes & 63) == 0) { fflush(g_tp_log); if (g_tp_ev) fflush(g_tp_ev); }
    }
    g_tp_cur = 1 - g_tp_cur; tp_clear(g_tp_cur);
    g_tp_leaves = g_tp_sw = g_tp_up = g_tp_down = 0; memset(g_tp_lvl, 0, sizeof g_tp_lvl); memset(g_tp_band, 0, sizeof g_tp_band); g_tp_near = 1e9f;
    g_tp_passes++;
}
/* after the picker (or the chained callback) ran for this leaf: tex = [0x59c558] as it chose it; main camera only */
static void __cdecl tp_leaf(DWORD leaf, float invz) {
    int x, z, s, lvl; float zp; unsigned __int64 k; tp_slot_t *cur, *prev; DWORD tex = *(volatile DWORD *)0x0059c558;
    if (!leaf || !g_tp_tab[0] || *(volatile DWORD *)0x006442d4 == 0x00608c80) return;
    if (g_frame != g_tp_frame_seen) { tp_close_pass(); g_tp_frame_seen = g_frame; }
    x = *(const short *)(DWORD_PTR)leaf; z = *(const short *)(DWORD_PTR)(leaf + 2); s = *(const int *)(DWORD_PTR)(leaf + 4);
    lvl = tp_level_of(tex); zp = invz > 1e-9f ? 1.0f / invz : 1e9f;
    k = tp_key(x, z, s);
    g_tp_leaves++; g_tp_lvl[lvl & 7]++;
    cur = tp_put(g_tp_cur, k); if (!cur) return;
    cur->lvl = lvl; cur->zp = zp;
    prev = g_tp_n[1 - g_tp_cur] ? tp_find(1 - g_tp_cur, k) : NULL;
    if (prev && prev->lvl != lvl && lvl < 7 && prev->lvl < 7) {
        g_tp_sw++; g_tp_band[tp_band(zp)]++; if (zp < g_tp_near) g_tp_near = zp;
        if (lvl < prev->lvl) g_tp_down++; else g_tp_up++;          /* down = finer texture (approaching) */
        if (g_tp_ev && g_tp_evn < 200000) { g_tp_evn++; fprintf(g_tp_ev, "%lu,%.1f,%d,%d,%d,%.1f,%.1f,%d,%d\n", (unsigned long)g_frame, tm_qms(), x, z, s, prev->zp, zp, prev->lvl, lvl); }
    }
}
static __declspec(naked) void tp_pick_stub(void) {             /* in place of `push <callback>` at 0x490f96: the fan calls cdecl(leaf, invz); eax is dead after */
    __asm {
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call dword ptr [g_tp_next]
        add  esp, 8
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call tp_leaf
        add  esp, 8
        ret
    }
}
static void __stdcall sc_DrawTriangle(const void *a, const void *b, const void *c) {
    const void *v[3]; int i; v[0] = a; v[1] = b; v[2] = c;
    for (i = 0; i < 3; i++) {
        float r = *(const float *)((const BYTE *)v[i] + 12); int bin = (int)(r + 0.5f);
        if (bin < 0) bin = 0; else if (bin > 255) bin = 255;
        g_sc_hist[bin]++; if (r - (float)bin > 0.02f || (float)bin - r > 0.02f) g_sc_nonint++;
    }
    g_sc_tris++;
    p_sc_DrawTriangle(a, b, c);
}
static DWORD g_tp_reported;
static void terrain_pops_report(void) {
    g_tp_reported = g_frame;
    if (g_sc_on && g_sc_tris) {
        char line[900]; size_t n = 0; DWORD tot = 3 * g_sc_tris, i, levels = 0;
        for (i = 0; i < 256; i++) if (g_sc_hist[i] * 500 >= tot) levels++;          /* bins holding >= 0.2 % */
        for (i = 0; i < 256 && n < sizeof line - 24; i++) if (g_sc_hist[i] * 500 >= tot) n += (size_t)_snprintf(line + n, sizeof line - n, " %lu:%.1f%%", (unsigned long)i, 100.0 * g_sc_hist[i] / tot);
        line[n] = 0;
        mlog("  shade-census: %lu triangles, %lu vertices, %.2f%% non-integer r; %lu integer levels hold >= 0.2%% each:%s",
             (unsigned long)g_sc_tris, (unsigned long)tot, 100.0 * g_sc_nonint / tot, (unsigned long)levels, line);
        memset(g_sc_hist, 0, sizeof g_sc_hist); g_sc_nonint = g_sc_tris = 0;
    }
    if (g_tp_log) mlog("  tex-level-log: %lu main passes logged, %lu level switches written", (unsigned long)g_tp_passes, (unsigned long)g_tp_evn);
    if (g_ss_on) mlog("  shade-smooth: on, table built %d time(s)", g_ss_builds);
}

/* ---- I76_SHADE_SMOOTH ---- */
static float g_ss_m255 = -255.0f;                          /* in place of [0x4bcd34] = -31.0 (the emitters do fmul then magic-round) */
static DWORD g_ss_tab[16 + 256 + 64];                      /* 16 guard entries below (k + 16 is the index, as the stock), 256, 64 above */
static DWORD g_ss_snap[64]; static int g_ss_on, g_ss_builds;
static void ss_build(void) {                               /* from the stock 64 entries (rows 31 - k at 0x526790 + 4 k, k = -16..47) */
    const DWORD *T = (const DWORD *)(DWORD_PTR)0x00526790; int k, i;
    memcpy(g_ss_snap, T - 16, sizeof g_ss_snap);
    for (i = 0; i < 16; i++) g_ss_tab[i] = T[0] & 0xff;
    for (k = 0; k < 256; k++) {
        float pos = 31.0f * (float)k / 255.0f; int a = (int)pos; float f = pos - (float)a; DWORD va, vb;
        if (a >= 31) { a = 31; f = 0.0f; }
        va = T[a] & 0xff; vb = T[a + (a < 31 ? 1 : 0)] & 0xff;
        g_ss_tab[16 + k] = (DWORD)((float)va * (1.0f - f) + (float)vb * f + 0.5f);
    }
    for (i = 0; i < 64; i++) g_ss_tab[16 + 256 + i] = T[31] & 0xff;
    g_ss_builds++;
}
static void ss_frame(void) {                               /* per frame: the mode slot rebuilds the stock table from the current palette / .lum */
    if (memcmp(g_ss_snap, (const void *)(DWORD_PTR)(0x00526790 - 64), sizeof g_ss_snap)) ss_build();
}
static void apply_shade_smooth(void) {
    static const DWORD cs[17] = { 0x427edb, 0x427fc3, 0x42834b, 0x42861c, 0x4287bb, 0x428861, 0x429439, 0x42975a, 0x429b77, 0x42b86c, 0x42bb5a, 0x42beac, 0x42c19a, 0x42c509, 0x42c82d, 0x42c969, 0x42cc8d };
    static const DWORD ts[17] = { 0x427f08, 0x427fe4, 0x428378, 0x42865f, 0x4287e8, 0x4288ac, 0x429456, 0x429772, 0x429b8f, 0x42b88a, 0x42bb73, 0x42beca, 0x42c1b3, 0x42c526, 0x42c845, 0x42c986, 0x42cca5 };
    static const BYTE c_old[4] = { 0x34, 0xcd, 0x4b, 0x00 }, t_old[4] = { 0x90, 0x67, 0x52, 0x00 };
    BYTE c_new[4], t_new[4]; DWORD a = (DWORD)(DWORD_PTR)&g_ss_m255, b = (DWORD)(DWORD_PTR)(g_ss_tab + 16); int i, ok = 1;
    if (env_flag("I76_SHADE_SMOOTH", 8, 0) != 1) return;
    if (g_exe == EXE_NITRO) { mlog("  shade-smooth: Nitro - not applied (Gold sites only)"); return; }
    memcpy(c_new, &a, 4); memcpy(t_new, &b, 4);
    for (i = 0; i < 17 && ok; i++) {                        /* fmul dword ptr [0x4bcd34] = d8 0d <addr>; mov r32, [r32*4 + 0x526790] = 8b <modrm 0x04..0x3c> <sib scale 4> <disp> */
        const BYTE *c = (const BYTE *)(DWORD_PTR)cs[i], *t = (const BYTE *)(DWORD_PTR)ts[i];
        if (c[-2] != 0xd8 || c[-1] != 0x0d || memcmp(c, c_old, 4)) ok = 0;
        if (t[-3] != 0x8b || (t[-2] & 0xc7) != 0x04 || (t[-1] & 0xc0) != 0x80 || memcmp(t, t_old, 4)) ok = 0;
    }
    if (!ok) { mlog("  shade-smooth: emitter site %d is not as expected (another exe or patch) - not applied", i); return; }
    ss_build();
    for (i = 0; i < 17 && ok; i++) ok = patch_bytes(cs[i], c_old, c_new, 4, "shade-smooth multiplier") && patch_bytes(ts[i], t_old, t_new, 4, "shade-smooth table");
    g_ss_on = ok;
    mlog("  shade-smooth: %s (vertex shade -> ZGLIDE intensity through a 256-entry table interpolating the stock 32 rows; stock rows now: %lu %lu %lu %lu %lu %lu %lu %lu / %lu %lu %lu %lu %lu %lu %lu %lu / %lu %lu %lu %lu %lu %lu %lu %lu / %lu %lu %lu %lu %lu %lu %lu %lu)",
         ok ? "on" : "NOT applied (a site failed; the rest may be patched)",
         g_ss_snap[16] & 0xff, g_ss_snap[17] & 0xff, g_ss_snap[18] & 0xff, g_ss_snap[19] & 0xff, g_ss_snap[20] & 0xff, g_ss_snap[21] & 0xff, g_ss_snap[22] & 0xff, g_ss_snap[23] & 0xff,
         g_ss_snap[24] & 0xff, g_ss_snap[25] & 0xff, g_ss_snap[26] & 0xff, g_ss_snap[27] & 0xff, g_ss_snap[28] & 0xff, g_ss_snap[29] & 0xff, g_ss_snap[30] & 0xff, g_ss_snap[31] & 0xff,
         g_ss_snap[32] & 0xff, g_ss_snap[33] & 0xff, g_ss_snap[34] & 0xff, g_ss_snap[35] & 0xff, g_ss_snap[36] & 0xff, g_ss_snap[37] & 0xff, g_ss_snap[38] & 0xff, g_ss_snap[39] & 0xff,
         g_ss_snap[40] & 0xff, g_ss_snap[41] & 0xff, g_ss_snap[42] & 0xff, g_ss_snap[43] & 0xff, g_ss_snap[44] & 0xff, g_ss_snap[45] & 0xff, g_ss_snap[46] & 0xff, g_ss_snap[47] & 0xff);
}
static void terrain_pops_frame(void) {                    /* from the frame hook: every frame */
    if (g_ss_on) ss_frame();
    if ((g_sc_on || g_tp_log) && g_frame - g_tp_reported >= 600) terrain_pops_report();   /* clutter_frame_wrap reports too when the clutter switch is on; the guard keeps one per 600 */
}
static void apply_terrain_pops(void) {
    char lf[260]; int i;
    apply_shade_smooth();
    g_sc_on = env_flag("I76_SHADE_CENSUS", 8, 0) == 1;
    if (g_sc_on && g_exe == EXE_NITRO) { mlog("  shade-census: Nitro - off"); g_sc_on = 0; }
    if (g_sc_on) mlog("  shade-census: on (ZGLIDE grDrawTriangle vertex r histogram; hooked when ZGLIDE loads)");
    if (!env_str("I76_TEX_LEVEL_LOG", lf, sizeof(lf))) return;
    if (g_exe == EXE_NITRO) { mlog("  tex-level-log: Nitro - off"); return; }
    for (i = 0; i < 2; i++) {
        g_tp_tab[i] = (tp_slot_t *)VirtualAlloc(NULL, TP_SLOTS * sizeof(tp_slot_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_tp_use[i] = (DWORD *)VirtualAlloc(NULL, TP_MAXL * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    }
    if (!g_tp_tab[0] || !g_tp_tab[1] || !g_tp_use[0] || !g_tp_use[1]) { mlog("  tex-level-log: no memory - off"); g_tp_tab[0] = NULL; return; }
    {   BYTE cur[5], push_new[5] = { 0x68 }; DWORD a = (DWORD)(DWORD_PTR)tp_pick_stub;   /* `push <callback>` at 0x490f96: stock 0x4923f0, or another switch's stub (chained) */
        memcpy(cur, (const void *)(DWORD_PTR)0x00490f96, 5);
        if (cur[0] != 0x68) { mlog("  tex-level-log: picker site is not a push - off"); g_tp_tab[0] = NULL; return; }
        memcpy(&g_tp_next, cur + 1, 4); memcpy(push_new + 1, &a, 4);
        if (!patch_bytes(0x00490f96, cur, push_new, 5, "terrain leaf texture picker (tex-level-log)")) { mlog("  tex-level-log: picker site not patched - off"); g_tp_tab[0] = NULL; return; }
        mlog("  tex-level-log: picker site chained (next 0x%08lx%s)", (unsigned long)g_tp_next, g_tp_next == 0x004923f0 ? " = the stock picker" : " = another switch's stub");
    }
    g_tp_log = fopen(lf, "w");
    if (g_tp_log) {
        char ef[280]; _snprintf(ef, sizeof(ef) - 1, "%s.events.csv", lf); ef[sizeof(ef) - 1] = 0; g_tp_ev = fopen(ef, "w");
        fprintf(g_tp_log, "frame,t_ms,leaves,l0,l1,l2,l3,l4,l5,l6,lnone,switches,sw_z_lt50,sw_50_100,sw_100_200,sw_200_400,sw_400_800,sw_gt800,nearest_switch_z,finer,coarser\n");
        if (g_tp_ev) fprintf(g_tp_ev, "frame,t_ms,x,z,size,z_prev,z_now,level_prev,level_now\n");
    }
    g_tp_near = 1e9f; g_tp_passes = 0;
    mlog("  tex-level-log: %s -> %s (main pass only; a switch = the same leaf (x, z, size) drawn with another texture level than the previous frame)", g_tp_log ? "on" : "NOT opened", lf);
}
