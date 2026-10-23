/* TERRAIN POP INSTRUMENTS  (terrain-pop lane 2026-10-23; docs/records/TERRAIN-POPS-2026-10-23.md)
 * Included by strlkproxy.c after terrainmorph.c. Lab only, off unless set. Gold only (the sites are mirrordetail.c's).
 *   I76_TEX_LEVEL_LOG=<csv>   per main terrain pass: how many leaves changed TEXTURE LEVEL since the previous pass (the picker
 *                             0x4923f0 picks level = clamp(9 - floor(log2(640 x 40 / z)), 0, 6) per leaf, i.e. a hard switch at
 *                             z = 50 / 100 / 200 / 400 / 800 / 1600 m - a whole tile changes its texture in one frame), by the
 *                             picker's own z band, with the nearest switch's z; <csv>.events.csv has one line per switch (capped).
 *   I76_SHADE_CENSUS=1        the vertex colour ZGLIDE hands glide2x (grDrawTriangle, GrVertex r at +12): a histogram of its
 *                             integer levels, so "is the Gouraud shade quantised in hardware" (renderer.md: the D3D path indexes a
 *                             64-entry grey table by 16 + round(31 s)) is settled by a count, not a reading. Report every 600 frames.
 */
#define TP_SLOTS 65536u
#define TP_MAXL  32768u
typedef struct { unsigned __int64 k; float zp; int lvl; } tp_slot_t;
static tp_slot_t *g_tp_tab[2]; static DWORD *g_tp_use[2], g_tp_n[2]; static int g_tp_cur;
static FILE *g_tp_log, *g_tp_ev; static DWORD g_tp_frame_seen, g_tp_passes, g_tp_evn;
static DWORD g_tp_leaves, g_tp_lvl[8], g_tp_sw, g_tp_band[6], g_tp_up, g_tp_down; static float g_tp_near;
static DWORD g_sc_hist[256], g_sc_nonint, g_sc_tris; static int g_sc_on;
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
static void terrain_pops_report(void) {
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
}
static void apply_terrain_pops(void) {
    char lf[260]; int i;
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
