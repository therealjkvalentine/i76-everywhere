/* TERRAIN GEOMORPH AND FLAT-TILE SPLIT  (terrain-geomorph lane 2026-10-21; docs/records/TERRAIN-MORPH-2026-10-21.md)
 * Included by strlkproxy.c after the terrain LOD / hysteresis code. Gold and Nitro (nitro-owner lane 2026-10-23: the renderer is
 * Gold's code relocated; every read through nitro.c's g_ta_* addresses, every site through the site map). Off unless set:
 *   I76_TERRAIN_MORPH=<band>        geomorph: band <= 1 = a fraction of the distance at which a vertex appeared, > 1 = metres
 *   I76_TERRAIN_MORPH_STATELESS=1   with I76_TERRAIN_MORPH: the stateless form (no tables; band = fraction of the vertex's split ring)
 *   I76_TERRAIN_MORPH_SHADE=<x>     stateless: the shade blends over x times the height's band (1..4, default 1; 2026-10-23)
 *   I76_TERRAIN_MORPH_BIG=1|2       stateless: also blend the 64+ sample levels (1 = height and shade, the 2026-10-22 form that
 *                                   slid; 2 = shade only). Unset = they stay at t = 1 (75b8888)
 *   I76_TERRAIN_MORPH_NEAR=<m>      stateless: no blend nearer than m metres (render-finish lane 2026-10-23: a blended height moves
 *                                   the texture print with it, UVs are per vertex). Continuous: a vertex's height and shade bands
 *                                   are cut to end at m (t reaches 1 there); a vertex whose split distance is within m of it is not
 *                                   blended at all (it pops as stock). Unset / 0 = unchanged
 *   I76_TERRAIN_MORPH_LOG=<csv>     lab instrument: per main terrain pass, how far vertices move on screen, near / mid / far (a
 *                                   snap = > 4 px in one pass) and by class (carried, born by a split, new at the view edge, gone) x
 *                                   size (<= 1, 1-4, 4-16, > 16 px); works with the morph off too (the same instrument on the stock)
 *   I76_TERRAIN_FLAT_SPLIT=<f>[,<eps m>]  a flat node (all its samples within eps of its coarse two-triangle surface, default
 *                                   0.3 m) skips the surface-type split until it is within f x the split ring (0 < f <= 1)
 *
 * THE MECHANISM (stock, i76.exe 6319abf7):
 *  - renderer_QueueTerrain 0x490a00 rebuilds the terrain quadtree 0x4911e0 every pass (main camera at 0x4020a4, rear mirror
 *    at 0x44594e with camera 0x608c80). Vertices go to [0x5dd320] (stride 12: x, y, z floats; x / z = integer sample
 *    coordinates, 5 m per sample, y = the RAW 12-bit height, x 0.1 m) and their UV / shade to [0x5dd2ec] (stride 12: u, v,
 *    shade); the frame's count is [0x6442ec]. The 4 root corners are vertices 0..3 (0x490be4..0x490df5).
 *  - The edge split 0x4918f0 makes ONE new vertex at the integer midpoint of an edge, with its TRUE height 0x493160(mx, mz)
 *    (0x491988), unless the edge was split already (shared edges: a vertex is made once per pass). A node split
 *    (0x49167c) splits its four sides, then the edge between two opposite side midpoints (the centre vertex).
 *  - Nothing blends between levels: when a node splits, its 5 new vertices jump from the coarse surface to their true
 *    heights in one frame (the "redraw" / pop), and when it merges they vanish in one frame.
 *  - After the quadtree: 0x4937c0 transforms every vertex IN PLACE to view space; then, when lighting is on ([0x5a4618]),
 *    0x490f08..0x490f6d computes each vertex's shade from the heightmap around its sample (0x490fb0: neighbour heights,
 *    view depth) into [0x5dd2ec]+8. So a new vertex also brings a new shade value at once (the Gouraud "shade pop").
 *  - Then 0x491a30 emits the leaves (call at 0x490f9b hardware, 0x490f82 software). The sim never reads these arrays:
 *    the ground query is 0x493550 (bilinear on the heightmap), so changing [0x5dd320] y is render-only.
 *
 * THE MORPH: the call to 0x4937c0 at 0x490eed is wrapped. Before the transform, every vertex (index >= 4) is named by its
 * sample (x, z); its level follows from the coordinates relative to the root square ([0x6442e0] / [0x6442e4], size
 * 1 << [0x6442e8]): m = the lowest set bit of the relative x or z. One of them odd in m -> a side midpoint of a node of size
 * 2m, parents (x -+ m, z) or (x, z -+ m); both -> the centre, parents (x - m, z - m) and (x + m, z + m) (the diagonal the
 * leaf fan 0x491a30 draws from its min corner). Parents always have lower indices (an edge's ends exist before it is split),
 * so walking the indices upward blends each vertex against ALREADY BLENDED parents: y = lerp(mean(parents), true, t).
 * t comes from a per-vertex memory across main passes (the hysteresis code's node table, here keyed by sample): a vertex that
 * is new in this pass while a node that would have had it as a midpoint / centre (or that node's parent / grandparent) was a
 * LEAF in the previous main pass appeared by a split: it remembers d0 = its distance then, and t = clamp((d0 - d) / band).
 * Any other new vertex (view edge, first pass, camera jump > 40 m) is mature (t = 1): no flattened ground at the view edge.
 * Retreating, d grows back toward d0 and t goes back to 0 before the node merges at the same ring (merge direction).
 * The mirror pass is stock (t = 1). After the shade loop the emit calls are wrapped and the shade is blended with the same t.
 *
 * FLAT SPLIT: a node that passes the height-error tests (0x4913e0..0x49153b) and is larger than 4 samples (0x491541) is still
 * split when its sample lines carry surface types 2, 3, 4, 6, 7 (0x4915f5..0x49166a; .ter bits 13-15). On T05 that is most of
 * the ground, so flat ground splits down to 20 m at the split ring (renderer.md row "terrain quadtree LOD"). The stub at
 * 0x491556 keeps such a node a leaf when it is flat (cached per node) and farther than f x its split ring.
 */
#define TM_MAXV   32768u
#define TM_SLOTS  65536u
typedef struct { unsigned __int64 k; float d0, y, sh, mx, shmx, shd, dd; int idx, open, m; } tm_slot_t;   /* dd: distance this pass, samples (row-crossing bands) */   /* mx / open / m: the per-split event (largest one-pass move) */      /* k 0 = empty (keys are offset, never 0) */
static tm_slot_t *g_tm_v[2]; static DWORD *g_tm_vu[2], g_tm_vn[2];               /* vertex maps: this main pass / previous */
static unsigned __int64 *g_tm_l[2]; static DWORD *g_tm_lu[2], g_tm_ln[2];        /* leaf key sets */
static int g_tm_cur = 0, g_tm_prev_ok, g_tm_on, g_tm_morph, g_tm_frac;
static float g_tm_band = 0.0f;                         /* fraction of d0, or samples */
static float g_tm_eye_prev[2];
static float *g_tm_t; static int *g_tm_pa, *g_tm_pb; static tm_slot_t **g_tm_slot;
static int g_tm_n, g_tm_pass_main, g_tm_have;
static DWORD g_tm_passes, g_tm_born, g_tm_morphing, g_tm_mature_new, g_tm_jumps_reset, g_tm_win_passes, g_tm_win_morphing;
static FILE *g_tm_log, *g_tm_ev; static LARGE_INTEGER g_tm_qpf;
static double g_tm_fx, g_tm_fz, g_tm_px, g_tm_pz; static int g_tm_fok;
static double g_tm_jpx[3], g_tm_spx[3], g_tm_shj, g_tm_maxj, g_tm_bin[4][4];   /* bin[class][size]: class carried / born / mature-new / gone; size <=1, 1-4, 4-16, >16 px */ static DWORD g_tm_new, g_tm_gone, g_tm_nview, g_tm_rc[3];   /* rc: carried vertices whose hardware shade ROW round(31 s) changed this pass, near / mid / far (terrain-pop lane 2026-10-23: the emitters quantise s to 32 rows, TERRAIN-POPS-2026-10-23) */
static DWORD g_tm_sj[4], g_tm_sjb[4], g_tm_rootmv; static double g_tm_sjs[4], g_tm_j100, g_tm_s100, g_tm_lastdm; static int g_tm_root_prev[3];   /* render-finish 2026-10-23: carried-vertex shade jumps >= 1/32 in one pass by band < 300 / 300-900 / 900-1600 / > 1600 m (all, on 64+ edges) and their sum; snaps / carried slides within 100 m (px); root square moved this pass */
static DWORD g_tm_ret_xform = 0x004937c0, g_tm_ret_emit = 0x00491a30;

static unsigned __int64 tm_vkey(int x, int z) { return ((unsigned __int64)(DWORD)(x + 8192) << 32) | (DWORD)(z + 8192); }
static unsigned __int64 tm_lkey(int x, int z, int s) { return ((unsigned __int64)(DWORD)(x + 8192) << 40) | ((unsigned __int64)(DWORD)(z + 8192) << 16) | (DWORD)(s & 0xffff); }
static DWORD tm_hash(unsigned __int64 k) { k ^= k >> 31; k *= 0x9e3779b97f4a7c15ull; k ^= k >> 29; return (DWORD)k & (TM_SLOTS - 1); }
static tm_slot_t *tm_vfind(int t, unsigned __int64 k) {
    DWORD i = tm_hash(k), n; tm_slot_t *s = g_tm_v[t];
    for (n = 0; n < 128; n++, i = (i + 1) & (TM_SLOTS - 1)) { if (!s[i].k) return NULL; if (s[i].k == k) return &s[i]; }
    return NULL;
}
static tm_slot_t *tm_vput(int t, unsigned __int64 k) {
    DWORD i = tm_hash(k), n; tm_slot_t *s = g_tm_v[t];
    for (n = 0; n < 128; n++, i = (i + 1) & (TM_SLOTS - 1)) {
        if (!s[i].k) { if (g_tm_vn[t] >= TM_MAXV) return NULL; s[i].k = k; s[i].d0 = -1.0f; s[i].idx = -1; s[i].mx = -1.0f; s[i].open = 0; s[i].m = 0; s[i].shmx = 0.0f; s[i].shd = -1.0f; g_tm_vu[t][g_tm_vn[t]++] = i; return &s[i]; }
        if (s[i].k == k) return &s[i];
    }
    return NULL;
}
static void tm_vclear(int t) { DWORD j; for (j = 0; j < g_tm_vn[t]; j++) g_tm_v[t][g_tm_vu[t][j]].k = 0; g_tm_vn[t] = 0; }
static int tm_lhas(int t, unsigned __int64 k) {
    DWORD i = tm_hash(k), n; unsigned __int64 *s = g_tm_l[t];
    for (n = 0; n < 128; n++, i = (i + 1) & (TM_SLOTS - 1)) { if (!s[i]) return 0; if (s[i] == k) return 1; }
    return 0;
}
static void tm_lput(int t, unsigned __int64 k) {
    DWORD i = tm_hash(k), n; unsigned __int64 *s = g_tm_l[t];
    for (n = 0; n < 128; n++, i = (i + 1) & (TM_SLOTS - 1)) {
        if (!s[i]) { if (g_tm_ln[t] >= TM_MAXV) return; s[i] = k; g_tm_lu[t][g_tm_ln[t]++] = i; return; }
        if (s[i] == k) return;
    }
}
static void tm_lclear(int t) { DWORD j; for (j = 0; j < g_tm_ln[t]; j++) g_tm_l[t][g_tm_lu[t][j]] = 0; g_tm_ln[t] = 0; }
static int tm_lowbit(int v, int R) { return v > 0 ? (v & -v) : R; }
/* the vertex's level and parents from its sample position: returns m (0 = not a split vertex), parents in *a / *b */
static int tm_parents(int x, int z, int ox, int oz, int R, int *ax, int *az, int *bx, int *bz, int *axis) {
    int rx = x - ox, rz = z - oz, lx, lz, m;
    if (rx < 0 || rz < 0 || rx > R || rz > R) return 0;
    lx = tm_lowbit(rx, R); lz = tm_lowbit(rz, R);
    if (lx >= R && lz >= R) return 0;                                  /* a root corner */
    if (lx == lz) { m = lx; *ax = x - m; *az = z - m; *bx = x + m; *bz = z + m; *axis = 2; }
    else if (lx < lz) { m = lx; *ax = x - m; *az = z; *bx = x + m; *bz = z; *axis = 0; }
    else { m = lz; *ax = x; *az = z - m; *bx = x; *bz = z + m; *axis = 1; }
    return m;
}
/* did a node that has (x, z) as a side midpoint / centre (size 2m), or its parent / grandparent, sit as a leaf last pass */
static int tm_was_leaf(int x, int z, int m, int axis, int ox, int oz) {
    int c, nx[2], nz[2], nn, S = 2 * m, k, s;
    if (axis == 2) { nx[0] = x - m; nz[0] = z - m; nn = 1; }
    else if (axis == 0) { nx[0] = x - m; nz[0] = z; nx[1] = x - m; nz[1] = z - S; nn = 2; }
    else { nx[0] = x; nz[0] = z - m; nx[1] = x - S; nz[1] = z - m; nn = 2; }
    for (c = 0; c < nn; c++)
        for (k = 0, s = S; k < 3 && s <= 64; k++, s *= 2) {
            int qx = ox + ((nx[c] - ox) & ~(s - 1)), qz = oz + ((nz[c] - oz) & ~(s - 1));
            if (tm_lhas(1 - g_tm_cur, tm_lkey(qx, qz, s))) return 1;
        }
    return 0;
}
static double tm_qms(void) { LARGE_INTEGER n; QueryPerformanceCounter(&n); return g_tm_qpf.QuadPart ? (double)n.QuadPart * 1000.0 / (double)g_tm_qpf.QuadPart : 0.0; }
/* on screen (the rc-draw census's scale: 3440 px over 121.7 deg) and inside the cockpit's view about the direction of travel */
static double tm_px(double dy_raw, double dx, double dz, int *band) {
    double dm = sqrt(dx * dx + dz * dz) * 5.0;
    if (!g_tm_fok || dm < 20.0 || (dx * g_tm_fx + dz * g_tm_fz) * 5.0 / dm < 0.487) return -1.0;
    *band = dm < 300.0 ? 0 : dm < 900.0 ? 1 : 2; g_tm_lastdm = dm;
    return fabs(dy_raw) * 0.1 / dm * (3440.0 / 2.1240);
}
static void tm_acc(double px, int band, int cls) {
    if (px < 0.0) return;
    g_tm_bin[cls][px <= 1.0 ? 0 : px <= 4.0 ? 1 : px <= 16.0 ? 2 : 3] += px;
    if (g_tm_lastdm < 100.0) { if (px > 4.0) g_tm_j100 += px; else if (cls == 0) g_tm_s100 += px; }   /* within 100 m: snaps (any class) / carried slides */
    if (px > 4.0) { g_tm_jpx[band] += px; if (px > g_tm_maxj) g_tm_maxj = px; } else g_tm_spx[band] += px;   /* a snap: > 4 px in one pass */
}

/* ---- STATELESS MORPH (I76_TERRAIN_MORPH_STATELESS=1 with I76_TERRAIN_MORPH=<band>; 2026-10-22) ----
 * No tables. The five calls of the edge split 0x4918f0 (0x491681 / 0x49168e / 0x491697 / 0x4916a0 / 0x4916e2, all in the quadtree's
 * split block) go through tm_edge_wrap, which records for the vertex the split made (index = [0x6442ec] before the call) the edge's two
 * ends (word v0, word v1 of the edge record): its parents, an array write per vertex. Before the transform, each vertex's level comes
 * from its parent edge (length S samples, axis-aligned: a node side, or the centre line between two side midpoints), and its blend
 * factor from the split test's own ring: the node splits when d_node^2 <= S^2 K (K = [0x6442c8]), so
 *     t = clamp((S sqrt(K) - d_node) / band),  band = fraction x S sqrt(K) (at least 40 m), or metres,
 * with d_node = the distance to the nearer of the vertex's nodes (a side midpoint: the two node centres S/2 off the side; the centre:
 * itself). t = 0 when the nearer node enters its ring (the split), so a ring split starts on its parents' line; a merge leaves at the
 * same ring with t back at 0. Splits made inside the ring by the error-threshold steps start partly blended (accepted). One vertex,
 * one t: no cracks. Parents are blended first (lower index), so y = lerp(mean(parents), true, t) chains through levels. The shade
 * rides the same t (tm_emit_wrap). Runs in every pass (mirror too). */
/* 2026-10-22 rows: in the no-dashboard view 22-34 % of splits happen INSIDE the ring (the height-error steps: the stock splits a node in
 * the band when err x S > floor_pow2(d^2) x B, B = [0x6442cc]; 0x491373), and the ring-only t popped them (95th 33 px). The step's
 * distance follows from the error: split <=> floor_pow2(d^2) <= P*, P* = the largest power of two below err x S / B, i.e. d < d_e =
 * sqrt(2 P*). The vertex's own midpoint error (|true height - mean of its true edge ends|; the centre: against the node's min / max
 * corners, the stock's own centre test 0x4913c4) is one of the node's tested errors, so d_e(own) <= the node's error-split distance:
 * D = min(ring, d_e(own)) never puts t above 0 at the split, and it is fixed per vertex (t continuous in d). A vertex whose own error
 * is small stays near its parents' line until close, by at most that small error. No reads beyond the vertex array. */
static short *g_ep_a, *g_ep_b; static DWORD *g_ep_s, g_tm_pid = 1; static int g_tm_sl, g_tm_slhave; static LONGLONG g_tm_ticks;
static void __cdecl tm_edge_wrap(BYTE *edge) {
    int n0 = *(volatile int *)(DWORD_PTR)g_ta_vn, had = edge && *(DWORD *)(edge + 4) != 0;
    ((void (__cdecl *)(BYTE *))(DWORD_PTR)g_ta_split)(edge);
    if (!had && n0 >= 0 && n0 < (int)TM_MAXV && *(volatile int *)(DWORD_PTR)g_ta_vn == n0 + 1) {
        g_ep_a[n0] = *(const short *)edge; g_ep_b[n0] = *(const short *)(edge + 2); g_ep_s[n0] = g_tm_pid; }
}
static int *g_sl_i, *g_sl_a, *g_sl_b, g_sl_m, g_tm_big; static float g_tm_near = 0.0f; static BYTE *g_tm_bg;   /* near: samples; bg: this pass's vertex sits on a 64+ sample edge (instrument) */
static float *g_sl_t, *g_sl_ts, *g_tm_ts, g_tm_shmul = 1.0f;   /* ts: the shade's t */
/* pass 1 reads only TRUE heights (nothing is blended yet) and keeps the vertices with t < 1 in a list; pass 2 blends the list in index
 * order (parents first). Per vertex: a few multiplies and compares (squared distances); square roots only for the listed ones. */
static void tm_stateless(const BYTE *cam, float *V, int n) {
    float sc = *(volatile float *)(DWORD_PTR)g_ta_sc, K = *(volatile float *)(DWORD_PTR)g_ta_K, B = *(volatile float *)(DWORD_PTR)g_ta_B;
    float ex = (float)(*(const double *)(cam + 0x160) * sc), ez = (float)(*(const double *)(cam + 0x170) * sc);
    float fb = g_tm_band * g_tm_shmul, om = 1.0f - fb, om2 = om * om;      /* the shortcut uses the wider (shade) band */
    /* the shortcut (skip when d <= D - bandS without a square root) is exact only once band = frac x D is past its 8-sample floor,
     * i.e. D >= 8 / frac: that threshold is the HEIGHT band's, whatever the shade multiplier (2026-10-23: it was computed from fb, so
     * with _SHADE 3 every split with D between 8/fb and 8/frac snapped its shade from ts to 1 at d = (1 - fb) D - the owner's "more
     * abrupt" shade on PLAY-OWNER-2300-SHADE) */
    float invB = B > 0.0f ? 1.0f / B : 0.0f, cut2 = g_tm_frac && g_tm_band > 0.0f && fb < 1.0f ? (8.0f / g_tm_band) * (8.0f / g_tm_band) : 1e30f;
    int ox = *(volatile int *)(DWORD_PTR)g_ta_ox, oz = *(volatile int *)(DWORD_PTR)g_ta_oz, i, k, m = 0; DWORD pid = g_tm_pid;
    if (g_tm_log) for (i = 0; i < n; i++) { g_tm_t[i] = g_tm_ts[i] = 1.0f; g_tm_pa[i] = g_tm_pb[i] = -1; if (g_tm_bg) g_tm_bg[i] = 0; }   /* the table instrument reads every vertex */
    for (i = 4; i < n; i++) {
        int a, b, iS, ip, alongx, big; float ax, az, bx, bz, x, z, dx, dz, d2, D2, e, q, h, D, d, band, bandS, t, ts;
        if (g_ep_s[i] != pid) continue;
        a = g_ep_a[i]; b = g_ep_b[i];
        if (a < 0 || b < 0 || a >= i || b >= i) continue;
        ax = V[3 * a]; az = V[3 * a + 2]; bx = V[3 * b]; bz = V[3 * b + 2]; x = V[3 * i]; z = V[3 * i + 2];
        alongx = fabsf(ax - bx) >= fabsf(az - bz);
        iS = (int)((alongx ? fabsf(ax - bx) : fabsf(az - bz)) + 0.5f);
        big = iS >= 64; if (g_tm_bg) g_tm_bg[i] = (BYTE)big;
        if (iS < 2 || (big && !g_tm_big)) continue;        /* nodes of 64+ samples split at any distance (0x4912f0, no test): t = 1. Their
                                                              alignment follows the root square, so a blend there would jump as it moves
                                                              (I76_TERRAIN_MORPH_BIG shows it: 1 = height and shade, 2 = shade only). */
        ip = alongx ? (int)z - oz : (int)x - ox;
        dx = fabsf(x - ex); dz = fabsf(z - ez); h = 0.5f * (float)iS;
        if (ip >= 0 && (ip & (iS - 1)) == 0) {             /* a side midpoint: the nearer node centre; its own error against its edge ends */
            if (alongx) dz = dz > h ? dz - h : h - dz; else dx = dx > h ? dx - h : h - dx;
            e = fabsf(V[3 * i + 1] - 0.5f * (V[3 * a + 1] + V[3 * b + 1]));
        } else {                                           /* the centre: against the node's min / max corners (the stock's centre test) */
            int c[4], cmin = -1, cmax = -1; float smin = 1e30f, smax = -1e30f;
            c[0] = g_ep_s[a] == pid ? g_ep_a[a] : -1; c[1] = g_ep_s[a] == pid ? g_ep_b[a] : -1;
            c[2] = g_ep_s[b] == pid ? g_ep_a[b] : -1; c[3] = g_ep_s[b] == pid ? g_ep_b[b] : -1;
            for (k = 0; k < 4; k++) if (c[k] >= 0 && c[k] < i) { float sxz = V[3 * c[k]] + V[3 * c[k] + 2]; if (sxz < smin) { smin = sxz; cmin = c[k]; } if (sxz > smax) { smax = sxz; cmax = c[k]; } }
            e = (cmin >= 0 && cmax >= 0 && cmin != cmax) ? fabsf(V[3 * i + 1] - 0.5f * (V[3 * cmin + 1] + V[3 * cmax + 1])) : 1e9f;
        }
        d2 = dx * dx + dz * dz;
        D2 = (float)(iS * iS) * K;                         /* the ring, squared */
        q = e * (float)iS * invB;                          /* the error step: split <=> floor_pow2(d^2) < q */
        if (invB > 0.0f) {
            if (q <= 1e-6f) D2 = 0.0f;
            else { DWORD bits; float p; memcpy(&bits, &q, 4); bits &= 0xff800000u; memcpy(&p, &bits, 4); if (p == q) p *= 0.5f; if (2.0f * p < D2) D2 = 2.0f * p; }
        }
        if (D2 <= 0.0f) t = ts = 0.0f;                     /* no error: stays on its parents' line (where it is anyway) */
        else {
            if (g_tm_frac && D2 >= cut2 && d2 <= D2 * om2) continue;   /* deep inside: t = 1, no square root */
            D = sqrtf(D2); band = g_tm_frac ? g_tm_band * D : g_tm_band; if (g_tm_frac && band < 8.0f) band = 8.0f;
            bandS = band * g_tm_shmul;                     /* the shade's band: the same start (t = 0 at the split), a longer fade */
            if (g_tm_near > 0.0f) {                        /* I76_TERRAIN_MORPH_NEAR: both bands end at the near limit (t = 1 there) */
                float lim = D - g_tm_near;
                if (lim < 0.5f) continue;                  /* split within the limit: not blended (the stock pop) */
                if (band > lim) band = lim;
                if (bandS > lim) bandS = lim;
            }
            if (D > bandS && d2 <= (D - bandS) * (D - bandS)) continue;
            d = sqrtf(d2); t = band > 0.0f ? (D - d) / band : 1.0f; ts = bandS > 0.0f ? (D - d) / bandS : 1.0f;
            if (ts >= 1.0f) continue;
            if (t > 1.0f) t = 1.0f;
            if (t < 0.0f) t = 0.0f;
            if (ts < 0.0f) ts = 0.0f;
        }
        if (big && g_tm_big == 2) t = 1.0f;                /* shade only */
        g_sl_i[m] = i; g_sl_a[m] = a; g_sl_b[m] = b; g_sl_t[m] = t; g_sl_ts[m] = ts; m++;
        g_tm_t[i] = t; g_tm_ts[i] = ts; g_tm_pa[i] = a; g_tm_pb[i] = b;
    }
    for (k = 0; k < m; k++) {                              /* pass 2: blend, parents first (the list is in index order) */
        int j = g_sl_i[k], a = g_sl_a[k], b = g_sl_b[k]; float ym = 0.5f * (V[3 * a + 1] + V[3 * b + 1]);
        V[3 * j + 1] = ym + (V[3 * j + 1] - ym) * g_sl_t[k];
    }
    g_tm_morphing += m; g_tm_win_morphing += m;
    g_sl_m = m; g_tm_pid++; g_tm_n = n; g_tm_slhave = 1;
}

static void __cdecl tm_xform_wrap(void) {
    BYTE *cam = *(BYTE * volatile *)(DWORD_PTR)g_ta_cam;
    float *V = *(float * volatile *)(DWORD_PTR)g_ta_V;
    int n = *(volatile int *)(DWORD_PTR)g_ta_vn, i, ox, oz, R, prev = 1 - g_tm_cur, teleport;
    float sc = *(volatile float *)(DWORD_PTR)g_ta_sc, ex, ez; LARGE_INTEGER q0, q1;
    QueryPerformanceCounter(&q0);
    g_tm_have = 0; g_tm_slhave = 0; g_tm_pass_main = cam && cam != (BYTE *)(DWORD_PTR)g_ta_mircam;
    if (g_tm_sl && cam && V && n > 4 && n <= (int)TM_MAXV && *(volatile DWORD *)(DWORD_PTR)g_ta_leaf != 0) tm_stateless(cam, V, n);
    if (!g_tm_on || !g_tm_pass_main || !V || n <= 4 || n > (int)TM_MAXV || *(volatile DWORD *)(DWORD_PTR)g_ta_leaf == 0) goto done;
    if (g_tm_sl && !g_tm_log) goto done;                   /* stateless without the instrument: no tables at all */
    ex = (float)(*(const double *)(cam + 0x160) * sc); ez = (float)(*(const double *)(cam + 0x170) * sc);
    ox = *(volatile int *)(DWORD_PTR)g_ta_ox; oz = *(volatile int *)(DWORD_PTR)g_ta_oz; R = 1 << (*(volatile int *)(DWORD_PTR)g_ta_lv & 31);
    teleport = !g_tm_prev_ok || (ex - g_tm_eye_prev[0]) * (ex - g_tm_eye_prev[0]) + (ez - g_tm_eye_prev[1]) * (ez - g_tm_eye_prev[1]) > 64.0f;
    if (teleport && g_tm_prev_ok) g_tm_jumps_reset++;
    if (g_tm_log) {                                    /* direction of travel for the view cone (as the census) */
        double mx = ex - g_tm_px, mz = ez - g_tm_pz, ml = sqrt(mx * mx + mz * mz);
        if (ml > 0.4) { if (ml < 40.0 && g_tm_passes) { g_tm_fx = mx / ml; g_tm_fz = mz / ml; g_tm_fok = 1; } g_tm_px = ex; g_tm_pz = ez; }
        g_tm_jpx[0] = g_tm_jpx[1] = g_tm_jpx[2] = g_tm_spx[0] = g_tm_spx[1] = g_tm_spx[2] = g_tm_shj = g_tm_maxj = 0.0; g_tm_new = g_tm_gone = g_tm_nview = 0; memset(g_tm_bin, 0, sizeof(g_tm_bin)); g_tm_rc[0] = g_tm_rc[1] = g_tm_rc[2] = 0;
        memset(g_tm_sj, 0, sizeof(g_tm_sj)); memset(g_tm_sjb, 0, sizeof(g_tm_sjb)); memset(g_tm_sjs, 0, sizeof(g_tm_sjs)); g_tm_j100 = g_tm_s100 = 0.0;
        {   int r0 = *(volatile int *)(DWORD_PTR)g_ta_ox, r1 = *(volatile int *)(DWORD_PTR)g_ta_oz, r2 = *(volatile int *)(DWORD_PTR)g_ta_lv;
            g_tm_rootmv = g_tm_prev_ok && (r0 != g_tm_root_prev[0] || r1 != g_tm_root_prev[1] || r2 != g_tm_root_prev[2]); g_tm_root_prev[0] = r0; g_tm_root_prev[1] = r1; g_tm_root_prev[2] = r2; }
    }
    tm_vclear(g_tm_cur);
    for (i = 0; i < n; i++) {
        tm_slot_t *s = tm_vput(g_tm_cur, tm_vkey((int)V[3 * i], (int)V[3 * i + 2]));
        g_tm_slot[i] = s; if (s && s->idx < 0) s->idx = i;
        if (!g_tm_sl) { g_tm_t[i] = 1.0f; g_tm_pa[i] = g_tm_pb[i] = -1; }   /* stateless: t / parents already set (the tables only measure) */
    }
    for (i = 4; i < n; i++) {
        int x = (int)V[3 * i], z = (int)V[3 * i + 2], ax, az, bx, bz, axis, m, ia, ib;
        tm_slot_t *s = g_tm_slot[i], *pa, *pb, *ps; float d, t = 1.0f, band, yt, ym;
        if (!s || s->idx != i) continue;
        m = tm_parents(x, z, ox, oz, R, &ax, &az, &bx, &bz, &axis);
        if (!m) continue;
        pa = tm_vfind(g_tm_cur, tm_vkey(ax, az)); pb = tm_vfind(g_tm_cur, tm_vkey(bx, bz));
        if (!pa || !pb || pa->idx < 0 || pb->idx < 0 || pa->idx >= i || pb->idx >= i) continue;
        ia = pa->idx; ib = pb->idx; if (!g_tm_sl) { g_tm_pa[i] = ia; g_tm_pb[i] = ib; }
        else if (g_tm_pa[i] < 0) { g_tm_pa[i] = ia; g_tm_pb[i] = ib; }   /* stateless, t = 1: the instrument still needs its parents (shade, events) */
        d = sqrtf(((float)x - ex) * ((float)x - ex) + ((float)z - ez) * ((float)z - ez)); s->dd = d;
        ps = g_tm_prev_ok ? tm_vfind(prev, s->k) : NULL;
        if (ps) { s->d0 = ps->d0; s->mx = ps->mx; s->open = ps->open; s->m = ps->m; s->shmx = ps->shmx; s->shd = ps->shd; }
        else {
            if (!teleport && tm_was_leaf(x, z, m, axis, ox, oz)) { s->d0 = d; g_tm_born++; s->open = 1; s->mx = -1.0f; s->m = m; s->shmx = 0.0f; s->shd = -1.0f; } else { s->d0 = -1.0f; g_tm_mature_new++; }
            if (g_tm_log) g_tm_new++;
        }
        yt = V[3 * i + 1]; ym = 0.5f * (V[3 * ia + 1] + V[3 * ib + 1]);
        if (g_tm_sl) t = g_tm_t[i];                       /* blended already by tm_stateless */
        else if (g_tm_morph && s->d0 > 0.0f) {
            band = g_tm_frac ? g_tm_band * s->d0 : g_tm_band;
            if (g_tm_frac && band < 8.0f) band = 8.0f;      /* at least 40 m: a vertex born close in (an error step at 40-160 m) does not race */
            t = band > 0.0f ? (s->d0 - d) / band : 1.0f;
            if (t < 0.0f) t = 0.0f; else if (t > 1.0f) t = 1.0f;
            if (t < 1.0f) { V[3 * i + 1] = ym + (yt - ym) * t; g_tm_morphing++; g_tm_win_morphing++; }
        }
        g_tm_t[i] = t;
        if (g_tm_log) {                                /* on-screen jump of this vertex since the previous main pass */
            int b; double px;
            px = tm_px(ps ? V[3 * i + 1] - ps->y : V[3 * i + 1] - ym, (double)x - ex, (double)z - ez, &b);
            if (px >= 0.0) { tm_acc(px, b, ps ? 0 : s->d0 > 0.0f ? 1 : 2); g_tm_nview++; }
            if (s->open && px > s->mx) s->mx = (float)px;   /* per split: the largest one-pass move (closed with the shade in tm_emit_wrap) */
        }
    }
    for (i = 0; i < n; i++) if (g_tm_slot[i] && g_tm_slot[i]->idx == i) g_tm_slot[i]->y = V[3 * i + 1];
    if (g_tm_log && g_tm_prev_ok) {                    /* vertices gone since the previous pass (merges): their jump to the coarse surface */
        DWORD j;
        for (j = 0; j < g_tm_vn[prev]; j++) {
            tm_slot_t *q = &g_tm_v[prev][g_tm_vu[prev][j]], *pa, *pb; int x, z, ax, az, bx, bz, axis, b; double px;
            if (tm_vfind(g_tm_cur, q->k)) continue;
            x = (int)(q->k >> 32) - 8192; z = (int)(DWORD)(q->k & 0xffffffffu) - 8192;
            if (!tm_parents(x, z, ox, oz, R, &ax, &az, &bx, &bz, &axis)) continue;
            pa = tm_vfind(g_tm_cur, tm_vkey(ax, az)); pb = tm_vfind(g_tm_cur, tm_vkey(bx, bz));
            if (!pa || !pb) continue;                  /* left the view, not merged */
            px = tm_px(q->y - 0.5 * (pa->y + pb->y), (double)x - ex, (double)z - ez, &b);
            if (px >= 0.0) { tm_acc(px, b, 3); g_tm_gone++; }
            if (q->open && g_tm_ev) { float mx = (float)px > q->mx ? (float)px : q->mx; if (mx >= 0.0f) fprintf(g_tm_ev, "%.1f,%.0f,%d,%.2f,%.4f,%.4f,g\n", tm_qms(), q->d0 * 5.0f, 10 * q->m, mx, q->shmx, q->shd); }
        }
    }
    {   const BYTE *leaf = *(BYTE * volatile *)(DWORD_PTR)g_ta_leaf; DWORD guard = 0;      /* this pass's leaves, for the next */
        tm_lclear(g_tm_cur);
        while (leaf && guard++ < TM_MAXV) { tm_lput(g_tm_cur, tm_lkey(*(const short *)leaf, *(const short *)(leaf + 2), *(const int *)(leaf + 4))); leaf = *(BYTE * const *)(leaf + 8); }
    }
    g_tm_eye_prev[0] = ex; g_tm_eye_prev[1] = ez; g_tm_n = n; g_tm_have = 1;
done:
    QueryPerformanceCounter(&q1); g_tm_ticks += q1.QuadPart - q0.QuadPart;     /* the morph's own work (the transform below excluded) */
    ((void (__cdecl *)(void))(DWORD_PTR)g_tm_ret_xform)();
}
static void __cdecl tm_emit_wrap(DWORD a, DWORD b) {
    LARGE_INTEGER q0, q1; QueryPerformanceCounter(&q0);
    if (g_tm_slhave && !g_tm_have) {                       /* stateless, no instrument: the shade of the listed vertices only */
        float *U = *(float * volatile *)(DWORD_PTR)g_ta_U; int k;
        if (U && *(volatile int *)(DWORD_PTR)g_ta_lit != 0)
            for (k = 0; k < g_sl_m; k++) { int j = g_sl_i[k]; float sm = 0.5f * (U[3 * g_sl_a[k] + 2] + U[3 * g_sl_b[k] + 2]); U[3 * j + 2] = sm + (U[3 * j + 2] - sm) * g_sl_ts[k]; }
        g_tm_passes++; g_tm_win_passes++; g_tm_slhave = 0;
    }
    else if (g_tm_have || g_tm_slhave) {
        float *U = *(float * volatile *)(DWORD_PTR)g_ta_U; int i, lit = *(volatile int *)(DWORD_PTR)g_ta_lit != 0;
        float *V = *(float * volatile *)(DWORD_PTR)g_ta_V;
        for (i = 4; i < g_tm_n && U && lit; i++) {
            int ia = g_tm_pa[i], ib = g_tm_pb[i]; float sm, t = g_tm_t[i], ts = g_tm_sl ? g_tm_ts[i] : t;
            tm_slot_t *s = g_tm_have ? g_tm_slot[i] : NULL, *ps;
            if (ia < 0 || ib < 0) continue;
            sm = 0.5f * (U[3 * ia + 2] + U[3 * ib + 2]);
            if (s && s->idx == i && s->open && s->shd < 0.0f) s->shd = (float)fabs(U[3 * i + 2] - sm);   /* the shade step a split would show */
            if (ts < 1.0f) U[3 * i + 2] = sm + (U[3 * i + 2] - sm) * ts;     /* the shade rides its own t (= the height's unless _SHADE) */
            if (g_tm_ev && s && s->idx == i && s->open) {   /* per split: largest one-pass shade step, then the event once the blend is done */
                tm_slot_t *pq = g_tm_prev_ok ? tm_vfind(1 - g_tm_cur, s->k) : NULL;
                float st = (float)fabs(U[3 * i + 2] - (pq ? pq->sh : sm));
                if (st > s->shmx) s->shmx = st;
                if (t >= 1.0f && ts >= 1.0f) { if (s->mx >= 0.0f) fprintf(g_tm_ev, "%.1f,%.0f,%d,%.2f,%.4f,%.4f,c\n", tm_qms(), s->d0 * 5.0f, 10 * s->m, s->mx, s->shmx, s->shd); s->open = 0; }
            }
            if (g_tm_log && s && s->idx == i) {         /* shade jump of a vertex born this pass (vs its parents' mean) */
                ps = g_tm_prev_ok ? tm_vfind(1 - g_tm_cur, s->k) : NULL;
                if (!ps && V[3 * i + 2] > 4.0f) g_tm_shj += fabs(U[3 * i + 2] - sm);
                if (ps && (int)(31.0f * U[3 * i + 2] + 0.5f) != (int)(31.0f * ps->sh + 0.5f)) {   /* a carried vertex crossed a hardware shade row: a 20-23 grey step on screen */
                    float dm = s->dd * 5.0f; g_tm_rc[dm < 300.0f ? 0 : dm < 900.0f ? 1 : 2]++; }
                if (ps) {                               /* a one-pass shade jump of a carried vertex (a stock row or more): not drift */
                    float ds = (float)fabs(U[3 * i + 2] - ps->sh), dm = s->dd * 5.0f; int b4 = dm < 300.0f ? 0 : dm < 900.0f ? 1 : dm < 1600.0f ? 2 : 3;
                    if (ds >= 0.03125f) { g_tm_sj[b4]++; g_tm_sjs[b4] += ds; if (g_tm_bg && g_tm_bg[i]) g_tm_sjb[b4]++; } }
            }
            if (s && s->idx == i) s->sh = U[3 * i + 2];
        }
        g_tm_passes++; g_tm_win_passes++;
        if (g_tm_log && g_tm_have) {
            fprintf(g_tm_log, "%lu,%.3f,%d,%lu,%lu,%lu,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.4f,%.1f,%.1f", (unsigned long)g_frame, tm_qms(), g_tm_n,
                    (unsigned long)g_tm_new, (unsigned long)g_tm_gone, (unsigned long)g_tm_nview,
                    g_tm_jpx[0], g_tm_jpx[1], g_tm_jpx[2], g_tm_spx[0], g_tm_spx[1], g_tm_spx[2], g_tm_maxj, g_tm_shj,
                    g_tm_eye_prev[0] * 5.0f, g_tm_eye_prev[1] * 5.0f);
            {   int c, kk; for (c = 0; c < 4; c++) for (kk = 0; kk < 4; kk++) fprintf(g_tm_log, ",%.1f", g_tm_bin[c][kk]); fprintf(g_tm_log, ",%lu,%lu,%lu", (unsigned long)g_tm_rc[0], (unsigned long)g_tm_rc[1], (unsigned long)g_tm_rc[2]);
                for (kk = 0; kk < 4; kk++) fprintf(g_tm_log, ",%lu,%lu,%.3f", (unsigned long)g_tm_sj[kk], (unsigned long)g_tm_sjb[kk], g_tm_sjs[kk]);
                fprintf(g_tm_log, ",%.1f,%.1f,%lu\n", g_tm_j100, g_tm_s100, (unsigned long)g_tm_rootmv); }
            if ((g_tm_passes & 63) == 0) { fflush(g_tm_log); if (g_tm_ev) fflush(g_tm_ev); }
        }
        if (g_tm_have) { g_tm_cur = 1 - g_tm_cur; g_tm_prev_ok = 1; }
        g_tm_have = 0; g_tm_slhave = 0;
    }
    QueryPerformanceCounter(&q1); g_tm_ticks += q1.QuadPart - q0.QuadPart;
    if (g_fe_chain_tm) fe_haze_apply();                    /* faredge.c I76_HAZE: after the morph's shade blend, before the emit */
    if (g_pd_on && g_tm_pass_main) pd_terrain_pass();      /* passtimers.c I76_PASS_DUMP: V / U as the emit reads them */
    ((void (__cdecl *)(DWORD, DWORD))(DWORD_PTR)g_tm_ret_emit)(a, b);
}

/* ---- flat-tile split ---- */
#define TF_SLOTS 65536u
typedef struct { unsigned __int64 k; DWORD sig; float err; } tf_slot_t;
static tf_slot_t *g_tf_tab; static float g_tf_f2 = 0.0f, g_tf_eps = 3.0f;    /* f^2; eps in raw height units */
static int g_tf_on; static DWORD g_tf_res, g_tf_kept, g_tf_tested, g_tf_win_kept, g_tf_ret = 0x0049155c, g_tf_leaf = 0x004917b4;
static int tf_h(int x, int z) { return ((int (__cdecl *)(int, int))(DWORD_PTR)g_ta_height)(x, z); }
/* the largest |height - coarse surface| over the node's samples; the coarse leaf is the fan from the min corner: triangles
 * (c00, c10, c11) and (c00, c11, c01) (0x491a30 starts the polygon at the min corner) */
static float tf_err(int x0, int z0, int S) {
    int i, j; float c00 = (float)tf_h(x0, z0), c10 = (float)tf_h(x0 + S, z0), c01 = (float)tf_h(x0, z0 + S), c11 = (float)tf_h(x0 + S, z0 + S), e = 0.0f, inv = 1.0f / (float)S;
    for (j = 0; j <= S; j++) for (i = 0; i <= S; i++) {
        float u = i * inv, v = j * inv, p, d;
        p = u >= v ? c00 + (c10 - c00) * u + (c11 - c10) * v : c00 + (c01 - c00) * v + (c11 - c01) * u;
        d = (float)tf_h(x0 + i, z0 + j) - p; if (d < 0.0f) d = -d; if (d > e) e = d;
    }
    return e;
}
static int __cdecl tf_keep(int cx, int cz, int h) {
    float ex = *(volatile float *)(DWORD_PTR)g_ta_ex, ez = *(volatile float *)(DWORD_PTR)g_ta_ez, K = *(volatile float *)(DWORD_PTR)g_ta_K;
    float dx = (float)cx - ex, dz = (float)cz - ez, d2 = dx * dx + dz * dz; int S = 2 * h, x0 = cx - h, z0 = cz - h; DWORD i, n, sig;
    unsigned __int64 k; tf_slot_t *s = NULL;
    g_tf_tested++;
    if (d2 < g_tf_f2 * (float)(S * S) * K) return 0;           /* within f x the ring: stock (the surface-type scan) */
    k = tm_lkey(x0, z0, S); sig = (DWORD)tf_h(x0, z0) | ((DWORD)tf_h(x0 + S, z0 + S) << 16);
    for (i = tm_hash(k), n = 0; n < 64; n++, i = (i + 1) & (TF_SLOTS - 1)) {
        if (!g_tf_tab[i].k || g_tf_tab[i].k == k) { s = &g_tf_tab[i]; break; }
    }
    if (s && s->k == k && s->sig == sig) { if (s->err > g_tf_eps) return 0; }
    else { float e = tf_err(x0, z0, S); if (s) { s->k = k; s->sig = sig; s->err = e; } if (e > g_tf_eps) return 0; }
    g_tf_kept++; g_tf_win_kept++;
    return 1;
}
static __declspec(naked) void tf_stub(void) {                    /* jmp from 0x491556 (replaces sub esi,ebx; sub edi,ebx; mov eax,esi) */
    __asm {
        pushad
        push ebx
        push edi
        push esi
        call tf_keep
        add esp, 12
        mov g_tf_res, eax
        popad
        cmp g_tf_res, 0
        jne leaf
        sub esi, ebx
        sub edi, ebx
        mov eax, esi
        jmp dword ptr [g_tf_ret]
    leaf:
        jmp dword ptr [g_tf_leaf]
    }
}

static void terrain_morph_report(void) {
    if (g_tm_on && g_tm_win_passes)
        mlog("  terrain-morph: %lu main passes (%lu since the last line), %lu vertices born by a split, %lu new but mature (view edge / jump), %lu camera jumps; vertex-passes morphing %lu (%.1f per pass); own cost %.0f us per pass",
             (unsigned long)g_tm_passes, (unsigned long)g_tm_win_passes, (unsigned long)g_tm_born, (unsigned long)g_tm_mature_new, (unsigned long)g_tm_jumps_reset,
             (unsigned long)g_tm_morphing, (double)g_tm_win_morphing / g_tm_win_passes,
             g_tm_qpf.QuadPart ? (double)g_tm_ticks * 1e6 / (double)g_tm_qpf.QuadPart / g_tm_win_passes : -1.0);
    g_tm_ticks = 0;
    if (g_tf_on) mlog("  terrain-flat-split: %lu flat nodes kept coarse (%lu since the last line), %lu tests", (unsigned long)g_tf_kept, (unsigned long)g_tf_win_kept, (unsigned long)g_tf_tested);
    g_tm_win_passes = g_tm_win_morphing = 0; g_tf_win_kept = 0;
}

static void apply_terrain_morph(void) {
    static const BYTE xf_old[5] = { 0xe8, 0xce, 0x28, 0x00, 0x00 };   /* call 0x4937c0 at 0x490eed */
    static const BYTE eh_old[5] = { 0xe8, 0x90, 0x0a, 0x00, 0x00 };   /* call 0x491a30 at 0x490f9b (hardware) */
    static const BYTE es_old[5] = { 0xe8, 0xa9, 0x0a, 0x00, 0x00 };   /* call 0x491a30 at 0x490f82 (software) */
    static const BYTE tf_old[6] = { 0x2b, 0xf3, 0x2b, 0xfb, 0x8b, 0xc6 };   /* sub esi,ebx; sub edi,ebx; mov eax,esi at 0x491556 */
    char v[64], lf[260], *c; DWORD nm = env_str("I76_TERRAIN_MORPH", v, sizeof(v)), nl, nf; float band = 0.0f, f = 0.0f, eps = 0.3f; int i, ok;
    BYTE w5[5] = { 0xe8 }, w6[6] = { 0xe9, 0, 0, 0, 0, 0x90 }; LONG rel;
    if (nm) { band = (float)atof(v); if (band == 0.0f) nm = 0; }      /* 0 = off, as unset */
    nl = env_str("I76_TERRAIN_MORPH_LOG", lf, sizeof(lf));
    {   char fv[64]; nf = env_str("I76_TERRAIN_FLAT_SPLIT", fv, sizeof(fv));
        if (nf) { f = (float)atof(fv); c = strchr(fv, ','); if (c) eps = (float)atof(c + 1); } }
    if (!nm && !nl && !nf) return;
    if (!g_ta_ok) { mlog("  terrain-morph: the terrain renderer's addresses are not all mapped (Nitro) - not applied"); return; }
    g_tm_ret_xform = g_ta_xform; g_tm_ret_emit = g_ta_emit; g_tf_ret = NA(0x0049155c); g_tf_leaf = NA(0x004917b4);   /* Gold: the same values; Nitro: mapped (nitro-owner lane 2026-10-23) */
    if (nm && (band <= 0.0f || (band > 1.0f && (band < 5.0f || band > 1000.0f)) || (band <= 1.0f && band < 0.02f))) {
        mlog("  terrain-morph: I76_TERRAIN_MORPH %s out of range (0.02..1 = fraction of the split distance, 5..1000 = metres) - not applied", v); nm = 0; }
    if (nm) { char sv[8]; if (env_str("I76_TERRAIN_MORPH_STATELESS", sv, sizeof(sv)) && atoi(sv) == 1) g_tm_sl = 1; }
    if (nm && g_tm_sl) { char sv[16];
        if (env_str("I76_TERRAIN_MORPH_SHADE", sv, sizeof(sv))) { float x = (float)atof(sv); if (x >= 1.0f && x <= 4.0f) g_tm_shmul = x; else mlog("  terrain-morph: I76_TERRAIN_MORPH_SHADE %s out of range (1..4) - 1", sv); }
        if (env_str("I76_TERRAIN_MORPH_NEAR", sv, sizeof(sv))) { float x = (float)atof(sv); if (x != 0.0f) { if (x >= 10.0f && x <= 500.0f) g_tm_near = x / 5.0f; else mlog("  terrain-morph: I76_TERRAIN_MORPH_NEAR %s out of range (10..500 m) - off", sv); } }
        if (env_str("I76_TERRAIN_MORPH_BIG", sv, sizeof(sv))) { int b = atoi(sv); if (b == 1 || b == 2) g_tm_big = b; else mlog("  terrain-morph: I76_TERRAIN_MORPH_BIG %s not 1 / 2 - off", sv); } }
    if (nm || nl) {
        g_ep_a = (short *)VirtualAlloc(NULL, TM_MAXV * sizeof(short), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_ep_b = (short *)VirtualAlloc(NULL, TM_MAXV * sizeof(short), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_ep_s = (DWORD *)VirtualAlloc(NULL, TM_MAXV * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_sl_i = (int *)VirtualAlloc(NULL, TM_MAXV * sizeof(int), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_sl_a = (int *)VirtualAlloc(NULL, TM_MAXV * sizeof(int), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_sl_b = (int *)VirtualAlloc(NULL, TM_MAXV * sizeof(int), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_sl_t = (float *)VirtualAlloc(NULL, TM_MAXV * sizeof(float), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_sl_ts = (float *)VirtualAlloc(NULL, TM_MAXV * sizeof(float), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_tm_ts = (float *)VirtualAlloc(NULL, TM_MAXV * sizeof(float), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (nl) g_tm_bg = (BYTE *)VirtualAlloc(NULL, TM_MAXV, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!g_ep_a || !g_ep_b || !g_ep_s || !g_sl_i || !g_sl_a || !g_sl_b || !g_sl_t || !g_sl_ts || !g_tm_ts) { mlog("  terrain-morph: no memory - not applied"); return; }
        QueryPerformanceFrequency(&g_tm_qpf);
        for (i = 0; i < 2 && (!g_tm_sl || nl); i++) {       /* the per-vertex tables: the memory form, or the instrument */
            g_tm_v[i] = (tm_slot_t *)VirtualAlloc(NULL, TM_SLOTS * sizeof(tm_slot_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            g_tm_vu[i] = (DWORD *)VirtualAlloc(NULL, TM_MAXV * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            g_tm_l[i] = (unsigned __int64 *)VirtualAlloc(NULL, TM_SLOTS * sizeof(unsigned __int64), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            g_tm_lu[i] = (DWORD *)VirtualAlloc(NULL, TM_MAXV * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        }
        g_tm_t = (float *)VirtualAlloc(NULL, TM_MAXV * sizeof(float), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_tm_pa = (int *)VirtualAlloc(NULL, TM_MAXV * sizeof(int), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_tm_pb = (int *)VirtualAlloc(NULL, TM_MAXV * sizeof(int), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_tm_slot = (tm_slot_t **)VirtualAlloc(NULL, TM_MAXV * sizeof(tm_slot_t *), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if ((!(g_tm_sl && !nl) && (!g_tm_v[0] || !g_tm_v[1] || !g_tm_vu[0] || !g_tm_vu[1] || !g_tm_l[0] || !g_tm_l[1] || !g_tm_lu[0] || !g_tm_lu[1])) || !g_tm_t || !g_tm_pa || !g_tm_pb || !g_tm_slot) {
            mlog("  terrain-morph: no memory - not applied"); return; }
        if (nm) { g_tm_morph = 1; if (band <= 1.0f) { g_tm_frac = 1; g_tm_band = band; } else g_tm_band = band / 5.0f; }
        if (nl) { g_tm_log = fopen(lf, "w"); QueryPerformanceFrequency(&g_tm_qpf);
                  { char ef[280]; _snprintf(ef, sizeof(ef) - 1, "%s.events.csv", lf); ef[sizeof(ef) - 1] = 0; g_tm_ev = fopen(ef, "w"); if (g_tm_ev) fprintf(g_tm_ev, "t_ms,d0_m,size_m,max_move_px,max_shade_step,shade_split_delta,end\n"); }
                  if (g_tm_log) fprintf(g_tm_log, "frame,t_ms,verts,new,gone,in_view,jump_px_near,jump_px_mid,jump_px_far,smooth_px_near,smooth_px_mid,smooth_px_far,max_jump_px,shade_jump_new,eye_x,eye_z,carried_le1,carried_1_4,carried_4_16,carried_gt16,born_le1,born_1_4,born_4_16,born_gt16,mature_le1,mature_1_4,mature_4_16,mature_gt16,gone_le1,gone_1_4,gone_4_16,gone_gt16,rowcross_near,rowcross_mid,rowcross_far,sj_near,sjbig_near,sjsum_near,sj_mid,sjbig_mid,sjsum_mid,sj_far1,sjbig_far1,sjsum_far1,sj_far2,sjbig_far2,sjsum_far2,jump_px_100,slide_px_100,root_moved\n"); }
        ok = site_is(0x00490eed, xf_old, 5) && site_is(0x00490f9b, eh_old, 5) && site_is(0x00490f82, es_old, 5);   /* Gold: memcmp; Nitro: the mapped sites hold Nitro's own stock calls (nitro.c site_is) */
        if (!ok) mlog("  terrain-morph: QueueTerrain call sites differ (another patch or another exe) - not applied");
        else {
            rel = (LONG)((DWORD_PTR)tm_xform_wrap - (0x00490eed + 5)); memcpy(w5 + 1, &rel, 4);
            ok = patch_bytes(0x00490eed, xf_old, w5, 5, "terrain morph transform call");
            rel = (LONG)((DWORD_PTR)tm_emit_wrap - (0x00490f9b + 5)); memcpy(w5 + 1, &rel, 4);
            ok = ok && patch_bytes(0x00490f9b, eh_old, w5, 5, "terrain morph emit call (hardware)");
            rel = (LONG)((DWORD_PTR)tm_emit_wrap - (0x00490f82 + 5)); memcpy(w5 + 1, &rel, 4);
            ok = ok && patch_bytes(0x00490f82, es_old, w5, 5, "terrain morph emit call (software)");
            if (ok && g_tm_sl) {                           /* the five calls of the edge split 0x4918f0 in the quadtree's split block */
                static const DWORD es[5] = { 0x00491681, 0x0049168e, 0x00491697, 0x004916a0, 0x004916e2 };
                BYTE cur[5]; int k, good = 1;
                for (k = 0; k < 5; k++) { LONG r0 = (LONG)(0x004918f0 - (es[k] + 5)); cur[0] = 0xe8; memcpy(cur + 1, &r0, 4); if (!site_is(es[k], cur, 5)) good = 0; }
                if (!good) { mlog("  terrain-morph: stateless: an edge-split call site differs - stateless NOT applied (the table form runs)"); g_tm_sl = 0; }
                else for (k = 0; k < 5; k++) {
                    LONG r0 = (LONG)(0x004918f0 - (es[k] + 5)); cur[0] = 0xe8; memcpy(cur + 1, &r0, 4);
                    rel = (LONG)((DWORD_PTR)tm_edge_wrap - (es[k] + 5)); memcpy(w5 + 1, &rel, 4);
                    if (!patch_bytes(es[k], cur, w5, 5, "terrain morph edge-split call")) { mlog("  terrain-morph: stateless: patch %d failed", k); ok = 0; }
                }
                if (g_tm_sl && !ok) g_tm_sl = 0;
            }
            g_tm_on = ok;
        }
        if (g_tm_morph && g_tm_sl)
            mlog("  terrain-morph: %s, STATELESS (no tables: parents from the edge split 0x4918f0, t from the vertex's own split ring S sqrt(K); band %.2f %s; height and shade, shade band x%.2f; no blend nearer than %.0f m; 64+ levels %s; every pass)%s",
                 g_tm_on ? "on" : "NOT applied", band, g_tm_frac ? "x the ring distance (at least 40 m)" : "m", g_tm_shmul, g_tm_near * 5.0f,
                 g_tm_big == 1 ? "BLENDED (height and shade)" : g_tm_big == 2 ? "shade only" : "stock (t = 1)", g_tm_log ? "; log on (its tables measure only)" : "");
        else if (g_tm_morph)
            mlog("  terrain-morph: %s (a vertex born by a split blends from its parents' height and shade to its own over %.2f %s; render only, the ground query 0x493550 is untouched)%s",
                 g_tm_on ? "on" : "NOT applied", band, g_tm_frac ? "x the distance it appeared at" : "m", g_tm_log ? "; log on" : "");
        else mlog("  terrain-morph: %s (LOG ONLY: no blending, the jump instrument runs on the stock terrain)", g_tm_on ? "on" : "NOT applied");
        if (nl) mlog("  terrain-morph: log %s -> %s", g_tm_log ? "on" : "NOT opened", lf);
    }
    if (nf) {
        if (f <= 0.0f || f > 1.0f || eps < 0.0f || eps > 5.0f) { mlog("  terrain-flat-split: I76_TERRAIN_FLAT_SPLIT %.3f,%.2f out of range (0 < f <= 1, eps 0..5 m) - not applied", f, eps); return; }
        g_tf_tab = (tf_slot_t *)VirtualAlloc(NULL, TF_SLOTS * sizeof(tf_slot_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!g_tf_tab) { mlog("  terrain-flat-split: no memory - not applied"); return; }
        g_tf_f2 = f * f; g_tf_eps = eps * 10.0f;
        rel = (LONG)((DWORD_PTR)tf_stub - (0x00491556 + 5)); memcpy(w6 + 1, &rel, 4);
        g_tf_on = patch_bytes(0x00491556, tf_old, w6, 6, "terrain flat split");
        mlog("  terrain-flat-split: %s (a node within %.2f m of its coarse surface skips the surface-type split until it is within %.2f x its split ring)",
             g_tf_on ? "on" : "NOT applied", eps, f);
    }
}
