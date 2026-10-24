/* ===========================================================================
 * FAR-EDGE FADE  (far-edge lane 2026-10-23; docs/records/FAR-EDGE-FADE-2026-10-23.md)
 * ===========================================================================
 * Owner 2026-10-23: "build out both haze and glide fog for me to test, and make sure it's pretty far out, not close, so it
 * works pretty close to the limit of what is rendered but transitions a little more smoothly from the flat horizon textures";
 * and the level boundaries "sweep up so you can't drive on forever ... treating those boundaries in a special way that fades
 * them to the horizon better". Included from strlkproxy.c BEFORE terrainmorph.c (tm_emit_wrap chains fe_haze_apply when the
 * morph owns the terrain emit sites). Gold only (i76.exe 6319abf7 sites; Nitro refused). Off unless set:
 *
 *   I76_HAZE=<start>[,<strength>]   the game's own terrain vertex shade pushed toward the brightest row over the last part of
 *                                   the far clip: from start x far (0.5..0.98, default 0.85) to the far clip the shade s becomes
 *                                   s + (target - s) x strength x smoothstep((z - z0) / (far - z0)); strength 0.1..1 (default 1).
 *                                   Both terrain passes (main at its far clip, rear mirror at I76_MIRROR_FAR); I76_HAZE_MIRROR=0
 *                                   keeps the mirror stock. Shade only (no tint: the hardware path modulates the texel by a grey
 *                                   from the 64-entry luma table, index 16 + round(31 s); the stock depth term g(z) already
 *                                   reaches 1.0 at 600 m, so past that the far ground is lit by slope alone).
 *   I76_HAZE_TARGET=<0..1>          the shade reached at the far clip (default 1.0 = the brightest row = the unmodulated texel).
 *   I76_GLIDE_FOG=<start>[,<colour>] hardware fog through glide2x (dgVoodoo): a 64-entry fog table (grFogTable) clear until
 *                                   start x far (default 0.85), full at the far clip, colour = the horizon strips' bottom rows
 *                                   (colour 'hzd' = 'strip', default: the horizon strips' 8-bit textures at 0x504850, bottom rows through
 *                                   the context palette 0x5dcfa8), 'sky' (the cloud dome texture 0x504c38's mean, the dome colour
 *                                   just above the horizon), 'mix[,f]' (strip toward sky by f, default 0.5), 'white[,f]' (strip
 *                                   toward white by f) or 'rrggbb' hex (far-edge follow-up: T05's strip 483620 reads as darkening). Fog is ON only around the hardware scene's depth-bucket flush
 *                                   (0x48fac0(cam, 1) at 0x40216d: terrain, roads, objects, clutter, smoke, tracers) and OFF
 *                                   for everything else in the frame: the sky dome and horizon strips (drawn before it), the
 *                                   cockpit mesh, instruments, target brackets, mask and text (after it). The rear mirror is a
 *                                   software render (no Glide calls). The fog w is ZGLIDE's vertex oow (= view z in metres,
 *                                   measured by the probe); I76_GLIDE_FOG_WM=<metres per w> overrides (default 1).
 *   I76_GLIDE_FOG_ALPHA=1           with I76_GLIDE_FOG: FADE TO TRANSPARENT instead of to a colour. ZGLIDE sets, per render op,
 *                                   grColorCombine / grAlphaCombine / grAlphaBlendFunction (its opaque ops: blend ONE / ZERO at
 *                                   0x10001fa0 / 0x1000200b / 0x10002399 / 0x100024fa; its translucent ops use SRC_ALPHA /
 *                                   ONE_MINUS_SRC_ALPHA with the texture or iterated alpha) over a W-buffer (LEQUAL, writes on).
 *                                   Inside the flush bracket the two state imports are IAT-hooked: an opaque request becomes
 *                                   SRC_ALPHA / ONE_MINUS_SRC_ALPHA with alpha = the iterated vertex alpha, and the grDrawTriangle
 *                                   hook writes each vertex's alpha (GrVertex +28) as 255 x (1 - fade(w)) from its oow; translucent
 *                                   requests pass through untouched (smoke, tracers keep their alpha). The sky dome and the horizon
 *                                   strips are drawn before the flush (0x402128 / 0x402131 before 0x40216d), so the far ground
 *                                   blends into the sky behind it; painter's order (far first) keeps nearer ground opaque over it.
 *                                   The fog table is not set in this mode (no colour).
 *   I76_EDGE_FADE=1|<pull>[,<band m>] level-boundary tiles faded harder (through I76_HAZE): the terrain tile table 0x644380 holds
 *                                   16384 tile pointers, every tile outside the mission's zone grid = the flat static tile
 *                                   0x59c588 (terrain init 0x493080). A vertex within band m (50..640, default 320) of such a VOID
 *                                   tile has its haze start pulled in: z0 = start x far x (1 - pull x (1 - d / band)), pull 0.1..0.9
 *                                   (1 = default 0.4). Continuous in d (no seams). The haze path only: the fog table is by w.
 *   I76_FAR_EDGE_LOG=1              lab: every 300 main passes a line - haze band vertices and distinct grey levels
 *                                   (round(31 s)) in the band; with the fog: ZGLIDE grDrawTriangle w (1 / oow) inside and
 *                                   outside the flush bracket (min / max / count) - the probe that settled the w units.
 */
static int g_tm_on;                             /* terrainmorph.c (included after this file): its emit-site wrap is live */
static int g_fe_haze_on, g_fe_haze_mirror = 1, g_fe_chain_tm, g_fe_log, g_fe_edge_on, g_fe_far_env, g_fe_fog_on, g_fe_fog_fixed;
static float g_fe_haze_start = 0.85f, g_fe_haze_str = 1.0f, g_fe_haze_target = 1.0f, g_fe_edge_pull = 0.4f, g_fe_edge_band = 64.0f, g_fe_mirror_far = 100.0f;   /* band in samples (5 m) */
static float g_fe_fog_start = 0.85f, g_fe_fog_wm = 1.0f, g_fe_fog_far_built = -1.0f, g_fe_fog_mixf = 0.5f;
static int g_fe_fog_src;                        /* 0 hzd / strip, 1 sky, 2 mix (strip toward the sky), 3 white (strip toward white) */
static DWORD g_fe_strip_rgb, g_fe_sky_rgb;
static DWORD g_fe_ret_emit = 0x00491a30, g_fe_next_flush, g_fe_fog_rgb = 0x00c0b0a0, g_fe_fog_rgb_built = 0xffffffff, g_fe_fog_start_built;
static BYTE *g_fe_ring, *g_fe_vmask;            /* 128x128 tiles: ring 0 void / 1 void-adjacent / 2 next / 3 open; vmask = which of the 8 neighbours are void */
static DWORD g_fe_ring_sig, g_fe_ring_tick, g_fe_hzd_tick, g_fe_hzd_sig;
static DWORD g_fe_passes, g_fe_band_v, g_fe_edge_v, g_fe_lvl[64];
static BYTE g_fe_table[64];
typedef void (__stdcall *fe_FogMode_t)(int); typedef void (__stdcall *fe_FogColor_t)(DWORD); typedef void (__stdcall *fe_FogTable_t)(const BYTE *);
typedef float (__stdcall *fe_IndexToW_t)(int); typedef void (__stdcall *fe_DrawTri_t)(const void *, const void *, const void *);
static fe_FogMode_t p_fe_FogMode; static fe_FogColor_t p_fe_FogColor; static fe_FogTable_t p_fe_FogTable; static fe_IndexToW_t p_fe_IndexToW; static fe_DrawTri_t p_fe_DrawTri;
static int g_fe_glide_tries, g_fe_in_flush, g_fe_probe_tried, g_fe_alpha, g_fe_opaque, g_fe_ablend_tried;
typedef void (__stdcall *fe_Blend_t)(int, int, int, int); typedef void (__stdcall *fe_ACombine_t)(int, int, int, int, int);
static fe_Blend_t p_fe_Blend; static fe_ACombine_t p_fe_ACombine; static int g_fe_ac_last[5] = { 3, 8, 1, 1, 0 }; static float g_fe_az0, g_fe_ainv;
static DWORD g_fe_atris, g_fe_averts_faded; static int g_fe_opaque_req, g_fe_keyed; typedef void (__stdcall *fe_Chroma_t)(int); static fe_Chroma_t p_fe_Chroma;
/* the override is on only for an opaque (ONE / ZERO) request without a colour key: chroma-keyed records (the bushes) drawn with
 * the iterated-alpha combine lost their key (black squares, boot 112109) */
/* I76_CLUTTER_ALPHA_FADE (render-finish lane 2026-10-23, strlkproxy.c clutter block): while the hardware flush draws a bush's face
 * record, g_cl_force holds blend SRC_ALPHA / ONE_MINUS_SRC_ALPHA with alpha = TEXTURE x ITERATED (the keyed texels keep alpha 0: the
 * s.12 lesson) and fe_DrawTri scales the vertex alpha by g_cl_cur (0..255); ZGLIDE's own requests inside the record are remembered
 * and restored after it (its state cache then matches the hardware). */
static int g_cl_force, g_fe_bl_last[4] = { 4, 0, 4, 0 }; static float g_cl_cur = 255.0f; static DWORD g_cl_ftris;
static void fe_apply_state(void) {
    int want = g_fe_alpha && g_fe_in_flush && g_fe_opaque_req && !g_fe_keyed;
    if (want && !g_fe_opaque) { p_fe_Blend(1, 5, 4, 0); p_fe_ACombine(3, 1, 0, 1, 0); g_fe_opaque = 1; }   /* alpha = TEXTURE x ITERATED (ZGLIDE's own keyed translucent op 0x10002205): keyed texels keep alpha 0, 565 terrain has none and takes the vertex alpha */
    else if (!want && g_fe_opaque) { p_fe_Blend(4, 0, 0, 0); p_fe_ACombine(g_fe_ac_last[0], g_fe_ac_last[1], g_fe_ac_last[2], g_fe_ac_last[3], g_fe_ac_last[4]); g_fe_opaque = 0; }
}
static double g_fe_pw_in_min = 1e30, g_fe_pw_in_max, g_fe_pw_out_min = 1e30, g_fe_pw_out_max; static DWORD g_fe_pt_in, g_fe_pt_out, g_fe_pt_in_far, g_fe_frames;

static float fe_main_far(void) { return g_fe_far_env ? g_far_clip : *(volatile float *)(DWORD_PTR)0x004c271c; }

/* ---- the level boundary: ring map over the tile table (rebuilt when the table's content changes: mission load) ---- */
static void fe_ring_build(void) {
    const DWORD *T = (const DWORD *)(DWORD_PTR)0x00644380; DWORD sig = 0; int i, x, z, nvoid = 0, n1 = 0, n2 = 0;
    for (i = 0; i < 16384; i++) sig = sig * 31u + T[i];
    if (sig == g_fe_ring_sig) return;
    g_fe_ring_sig = sig;
    for (i = 0; i < 16384; i++) { g_fe_ring[i] = T[i] == 0x0059c588u ? 0 : 3; g_fe_vmask[i] = 0; if (!g_fe_ring[i]) nvoid++; }
    for (z = 0; z < 128; z++) for (x = 0; x < 128; x++) {
        int dx, dz, k = 0; BYTE m = 0;
        if (g_fe_ring[z * 128 + x] == 0) continue;
        for (dz = -1; dz <= 1; dz++) for (dx = -1; dx <= 1; dx++) {
            if (!dx && !dz) continue;
            if (x + dx >= 0 && x + dx < 128 && z + dz >= 0 && z + dz < 128 && g_fe_ring[(z + dz) * 128 + x + dx] == 0) m |= (BYTE)(1 << k);
            k++;
        }
        if (m) { g_fe_ring[z * 128 + x] = 1; g_fe_vmask[z * 128 + x] = m; n1++; }
    }
    for (z = 0; z < 128; z++) for (x = 0; x < 128; x++) {
        int dx, dz, near1 = 0;
        if (g_fe_ring[z * 128 + x] != 3) continue;
        for (dz = -1; dz <= 1 && !near1; dz++) for (dx = -1; dx <= 1; dx++)
            if (x + dx >= 0 && x + dx < 128 && z + dz >= 0 && z + dz < 128 && g_fe_ring[(z + dz) * 128 + x + dx] == 1) { near1 = 1; break; }
        if (near1) { g_fe_ring[z * 128 + x] = 2; n2++; }
    }
    mlog("  far-edge: tile map rebuilt - %d void tiles (the flat static tile), %d authored tiles touching the void, %d one ring in, %d open", nvoid, n1, n2, 16384 - nvoid - n1 - n2);
}
/* distance in samples from sample (sx, sz) to the nearest void tile; >= 128 when none within the 8 neighbours */
static float fe_void_dist(int sx, int sz) {
    int tx = (sx + 0xc00) >> 7, tz = (sz + 0xc00) >> 7, k = 0, dx, dz; BYTE r, m; float best = 1e9f;
    if (tx < 0 || tx > 127 || tz < 0 || tz > 127) return 1e9f;
    r = g_fe_ring[tz * 128 + tx];
    if (r == 0) return 0.0f;
    if (r != 1) return 1e9f;
    m = g_fe_vmask[tz * 128 + tx];
    for (dz = -1; dz <= 1; dz++) for (dx = -1; dx <= 1; dx++) {
        float x0, x1, z0, z1, ex = 0.0f, ez = 0.0f, d2;
        if (!dx && !dz) continue;
        if (m & (1 << k)) {
            x0 = (float)(((tx + dx) << 7) - 0xc00); x1 = x0 + 128.0f; z0 = (float)(((tz + dz) << 7) - 0xc00); z1 = z0 + 128.0f;
            if ((float)sx < x0) ex = x0 - (float)sx; else if ((float)sx > x1) ex = (float)sx - x1;
            if ((float)sz < z0) ez = z0 - (float)sz; else if ((float)sz > z1) ez = (float)sz - z1;
            d2 = ex * ex + ez * ez; if (d2 < best) best = d2;
        }
        k++;
    }
    return best < 1e9f ? (float)sqrt(best) : 1e9f;
}

/* ---- (1) HAZE: after the exe's shade loop, before the leaf emit (both passes) ---- */
static void fe_haze_apply(void) {
    BYTE *cam; float *V, *U; int n, i, mirror; float fz, z0, inv, tgt = g_fe_haze_target, str = g_fe_haze_str;
    if (!g_fe_haze_on) return;
    cam = *(BYTE * volatile *)(DWORD_PTR)0x006442d4; V = *(float * volatile *)(DWORD_PTR)0x005dd320; U = *(float * volatile *)(DWORD_PTR)0x005dd2ec;
    n = *(volatile int *)(DWORD_PTR)0x006442ec;
    if (!cam || !V || !U || n <= 0 || n > 32768 || *(volatile int *)(DWORD_PTR)0x005a4618 == 0) return;
    mirror = cam == (BYTE *)(DWORD_PTR)0x00608c80;
    if (mirror && !g_fe_haze_mirror) return;
    fz = mirror ? g_fe_mirror_far : fe_main_far();
    if (fz <= 0.0f) return;
    if (g_fe_edge_on && !mirror) { DWORD t = GetTickCount(); if (t - g_fe_ring_tick > 2000) { g_fe_ring_tick = t; fe_ring_build(); } }
    z0 = fz * g_fe_haze_start; inv = fz > z0 ? 1.0f / (fz - z0) : 0.0f;
    for (i = 0; i < n; i++) {
        float z = V[3 * i + 2], s, f, zs = z0, iv = inv;
        if (z <= z0 * (1.0f - (g_fe_edge_on ? g_fe_edge_pull : 0.0f))) continue;       /* below every possible start */
        if (g_fe_edge_on && g_fe_ring_sig) {
            int sx = (int)(U[3 * i] * 8.0f + 0.5f), sz = (int)(U[3 * i + 1] * 8.0f + 0.5f);   /* the sample from its UV (0x490a00: uv = sample x 0.125) */
            float d = fe_void_dist(sx, sz);
            if (d < g_fe_edge_band) { float w = 1.0f - d / g_fe_edge_band; zs = z0 * (1.0f - g_fe_edge_pull * w); iv = fz > zs ? 1.0f / (fz - zs) : 0.0f; if (g_fe_log && !mirror && z > zs) g_fe_edge_v++; }
        }
        if (z <= zs) continue;
        f = (z - zs) * iv; if (f > 1.0f) f = 1.0f;
        f = f * f * (3.0f - 2.0f * f) * str;
        s = U[3 * i + 2]; s += (tgt - s) * f;
        if (s > 1.0f) s = 1.0f; else if (s < 0.0f) s = 0.0f;
        U[3 * i + 2] = s;
        if (g_fe_log && !mirror) { g_fe_band_v++; g_fe_lvl[(int)(31.0f * s + 0.5f) & 63]++; }
    }
    if (!mirror) {
        g_fe_passes++;
        if (g_fe_log && (g_fe_passes % 300) == 0) {
            int k, distinct = 0, lo = -1, hi = -1;
            for (k = 0; k < 64; k++) if (g_fe_lvl[k]) { distinct++; if (lo < 0) lo = k; hi = k; }
            mlog("  far-edge haze: %lu main passes; last 300: %lu vertices in the band (%.1f per pass), %d distinct grey levels round(31 s) in %d..%d%s%lu edge-pulled",
                 (unsigned long)g_fe_passes, (unsigned long)g_fe_band_v, g_fe_band_v / 300.0, distinct, lo, hi, g_fe_edge_on ? "; " : "", (unsigned long)g_fe_edge_v);
            memset(g_fe_lvl, 0, sizeof g_fe_lvl); g_fe_band_v = g_fe_edge_v = 0;
        }
    }
}
static void __cdecl fe_emit_wrap(DWORD a, DWORD b) {        /* the emit sites when the morph does not own them */
    fe_haze_apply();
    ((void (__cdecl *)(DWORD, DWORD))(DWORD_PTR)g_fe_ret_emit)(a, b);
}

/* ---- (2) GLIDE FOG: table + colour, on around the hardware scene's depth-bucket flush ---- */
static int fe_glide_resolve(void) {
    HMODULE g;
    if (p_fe_FogMode && p_fe_FogTable && p_fe_FogColor) return 1;
    if (g_fe_glide_tries > 300) return 0;
    g_fe_glide_tries++;
    g = GetModuleHandleA("glide2x.dll");
    if (!g) return 0;
    p_fe_FogMode = (fe_FogMode_t)GetProcAddress(g, "_grFogMode@4");
    p_fe_FogColor = (fe_FogColor_t)GetProcAddress(g, "_grFogColorValue@4");
    p_fe_FogTable = (fe_FogTable_t)GetProcAddress(g, "_grFogTable@4");
    p_fe_IndexToW = (fe_IndexToW_t)GetProcAddress(g, "_guFogTableIndexToW@4");
    mlog("  glide-fog: glide2x.dll at %p: grFogMode %s, grFogColorValue %s, grFogTable %s, guFogTableIndexToW %s", (void *)g,
         p_fe_FogMode ? "ok" : "MISSING", p_fe_FogColor ? "ok" : "MISSING", p_fe_FogTable ? "ok" : "MISSING", p_fe_IndexToW ? "ok" : "missing (the 2^(3 + i/4) / (8 - i%4) rule used)");
    if (!p_fe_FogMode || !p_fe_FogColor || !p_fe_FogTable) { g_fe_glide_tries = 1000; mlog("  glide-fog: OFF (a fog entry point is missing)"); return 0; }
    return 1;
}
static float fe_index_to_w(int i) {
    if (p_fe_IndexToW) return p_fe_IndexToW(i);
    return (float)(pow(2.0, 3.0 + (double)(i >> 2)) / (double)(8 - (i & 3)));     /* Glide 2.x fog.c guFogTableIndexToW (SST-1: 64 entries, w 1..52428) */
}
/* the horizon colour: the mean of the bottom 4 rows of every horizon strip bitmap (0x4016e0 draws DAT_00503034 strips from the
 * texture pairs at 0x504850, 0x18 bytes each: [0] the 8-bit bitmap, [1] the hardware variant; 0x471f00 picks [1] for a kind-1
 * camera bitmap). An 8-bit bitmap (+0x2c == 1) goes through the context palette 0x5dcfa8 (as the mirror dump, 3 bytes per entry). */
/* the sky colour (far-edge follow-up 2026-10-23, owner: "I see it getting darker ... I don't know that it looks like a fog"):
 * the cloud dome 0x405200 textures its 6000 m dome with the texture pair at 0x504c38 ([0] the 8-bit record, the same layout as
 * the strips; 0x4054f1 reads its first texel as the flat colour when clouds are off). The dome just above the horizon is
 * foreshortened over the whole texture (and its UV scrolls), so the colour there is the texture's mean: all rows through the
 * context palette (and mirror-pal's map, as the strips). */
static int fe_sky_colour(DWORD *rgb) {
    const BYTE *tx = *(const BYTE * volatile *)(DWORD_PTR)0x00504c38, *px, *pal = (const BYTE *)(DWORD_PTR)0x005dcfa8;
    DWORD w, hf, h, i, cnt = 0; double r = 0, g = 0, b = 0; static int logged;
    if (!tx || IsBadReadPtr(tx, 8)) return 0;
    w = *(const DWORD *)tx; hf = *(const DWORD *)(tx + 4); h = hf & 0x1fffffff; px = tx + 8;
    if (!logged) { logged = 1; mlog("  glide-fog: sky texture (0x504c38 [0]) %lux%lu flags %lx", (unsigned long)w, (unsigned long)h, (unsigned long)(hf >> 29)); }
    if (w == 0 || h == 0 || w > 2048 || h > 2048 || (hf & 0x80000000u) || IsBadReadPtr(px, w * h)) return 0;
    for (i = 0; i < w * h; i++) { BYTE k = px[i]; if (g_mp_pair >= 0) k = g_mp_map[k]; r += pal[k * 3]; g += pal[k * 3 + 1]; b += pal[k * 3 + 2]; cnt++; }
    *rgb = ((DWORD)(r / cnt + 0.5) << 16) | ((DWORD)(g / cnt + 0.5) << 8) | (DWORD)(b / cnt + 0.5);
    return 1;
}
static DWORD fe_lerp_rgb(DWORD a, DWORD b, float f) {
    DWORD o = 0; int s;
    for (s = 0; s <= 16; s += 8) { float ca = (float)((a >> s) & 255), cb = (float)((b >> s) & 255); o |= (DWORD)(ca + (cb - ca) * f + 0.5f) << s; }
    return o;
}
static int fe_hzd_colour(DWORD *rgb) {
    int ns = *(volatile int *)(DWORD_PTR)0x00503034, s, y, x; double r = 0, g = 0, b = 0; DWORD cnt = 0; const BYTE *pal = (const BYTE *)(DWORD_PTR)0x005dcfa8;
    static int logged, logged2;
    if (ns <= 0 || ns > 64) return 0;
    for (s = 0; s < ns; s++) {
        /* a texture record (0x471c10 loader; 0x44a740 copies ((h << 3) >> 3) x w + 8 bytes): DWORD w, DWORD h | flags (bit 31 = embedded
         * 16-bit palette, .m16), then the 8-bit texels. [0] of the pair is the 8-bit one; [1] the hardware (.m16) variant. */
        const DWORD *set = (const DWORD *)(DWORD_PTR)(0x00504850 + s * 0x18); const BYTE *tx = (const BYTE *)(DWORD_PTR)set[0];
        DWORD w, h, hf; const BYTE *px;
        if (!tx || IsBadReadPtr(tx, 8)) continue;
        w = *(const DWORD *)tx; hf = *(const DWORD *)(tx + 4); h = hf & 0x1fffffff; px = tx + 8;
        if (!logged) { logged = 1; mlog("  glide-fog: horizon strip 0 texture %lux%lu flags %lx (8-bit)", (unsigned long)w, (unsigned long)h, (unsigned long)(hf >> 29)); }
        if (w == 0 || h == 0 || w > 2048 || h > 2048 || (hf & 0x80000000u) || IsBadReadPtr(px, w * h)) continue;
        /* the strip is stored bottom-up: rows 84..127 are black (the transparent sky above the mesa line: lowest non-black row 83 = the
         * peaks on T05), row 0 is the picture's base, where the far rim of the ground meets it. Take rows 0..7. */
        if (!logged2) { int yb; double lum = 0; for (yb = (int)h - 1; yb >= 0; yb--) { lum = 0; for (x = 0; x < (int)w; x++) { BYTE i = px[yb * w + x]; lum += 0.30 * pal[i * 3] + 0.59 * pal[i * 3 + 1] + 0.11 * pal[i * 3 + 2]; } if (lum / w >= 8.0) break; }
            logged2 = 1; mlog("  glide-fog: horizon strip 0: highest non-black row %d of %lu (stored bottom-up; the base rows 0..7 give the colour)", yb, (unsigned long)h); }
        /* the 8-bit strip's indices belong to the 8-bit build's palette (t05.act); the hardware build's context holds t05_16.act. With
         * I76_MIRROR_PAL=1 mirrordetail.c has the nearest-colour remap for the pair (g_mp_map, once the pair is found): use it. */
        for (y = 0; y < 8 && y < (int)h; y++) for (x = 0; x < (int)w; x++) {
            BYTE i = px[y * w + x]; if (g_mp_pair >= 0) i = g_mp_map[i];
            r += pal[i * 3]; g += pal[i * 3 + 1]; b += pal[i * 3 + 2];
            cnt++;
        }
    }
    if (!cnt) return 0;
    *rgb = ((DWORD)(r / cnt + 0.5) << 16) | ((DWORD)(g / cnt + 0.5) << 8) | (DWORD)(b / cnt + 0.5);
    return 1;
}
static void fe_fog_update(float fz) {
    DWORD rgb = g_fe_fog_rgb, t = GetTickCount();
    if (!g_fe_fog_fixed && t - g_fe_hzd_tick > 2000) {
        DWORD c, sk = 0; int hok, sok; g_fe_hzd_tick = t;
        hok = fe_hzd_colour(&c); sok = fe_sky_colour(&sk);                  /* read in every mode: the log names both */
        if (hok) g_fe_strip_rgb = c;
        if (sok) g_fe_sky_rgb = sk;
        if (g_fe_fog_src == 0 && hok) g_fe_fog_rgb = c;
        else if (g_fe_fog_src == 1 && sok) g_fe_fog_rgb = sk;
        else if (g_fe_fog_src == 2 && hok && sok) g_fe_fog_rgb = fe_lerp_rgb(c, sk, g_fe_fog_mixf);
        else if (g_fe_fog_src == 3 && hok) g_fe_fog_rgb = fe_lerp_rgb(c, 0x00ffffff, g_fe_fog_mixf);
        rgb = g_fe_fog_rgb;
    }
    if (rgb != g_fe_fog_rgb_built) {
        static const char *src[4] = { "horizon strips, base rows", "sky texture mean", "strip toward the sky", "strip toward white" };
        g_fe_fog_rgb_built = rgb; p_fe_FogColor(rgb & 0x00ffffff);   /* ARGB: ZGLIDE opens the SST with cformat 0 */
        if (g_fe_fog_fixed) mlog("  glide-fog: colour %06lx (fixed)", (unsigned long)rgb);
        else mlog("  glide-fog: colour %06lx (%s%s; strip %06lx, sky %06lx, mix %.2f; %s)", (unsigned long)rgb, src[g_fe_fog_src & 3], g_fe_fog_src >= 2 ? " by the fraction" : "",
                  (unsigned long)g_fe_strip_rgb, (unsigned long)g_fe_sky_rgb, g_fe_fog_mixf, g_mp_pair >= 0 ? "through mirror-pal's 8-bit -> hardware palette map" : "context palette (no mirror-pal map)");
    }
    if (fz != g_fe_fog_far_built || g_fe_fog_start_built != (DWORD)(g_fe_fog_start * 1000.0f)) {
        int i; float z0 = fz * g_fe_fog_start, inv = fz > z0 ? 1.0f / (fz - z0) : 0.0f; char txt[200]; int n = 0;
        for (i = 0; i < 64; i++) {
            float w = fe_index_to_w(i) * g_fe_fog_wm, f = (w - z0) * inv;
            if (f < 0.0f) f = 0.0f; else if (f > 1.0f) f = 1.0f;
            f = f * f * (3.0f - 2.0f * f);
            g_fe_table[i] = (BYTE)(f * 255.0f + 0.5f);
        }
        p_fe_FogTable(g_fe_table);
        g_fe_fog_far_built = fz; g_fe_fog_start_built = (DWORD)(g_fe_fog_start * 1000.0f);
        for (i = 0; i < 64 && n < (int)sizeof txt - 24; i++) if (i == 0 ? g_fe_table[0] != 0 : g_fe_table[i] != g_fe_table[i - 1])
            n += _snprintf(txt + n, sizeof txt - n, " [%d]%.0fm=%u", i, fe_index_to_w(i) * g_fe_fog_wm, g_fe_table[i]);
        txt[n] = 0;
        mlog("  glide-fog: table for far %.0f m: clear to %.0f m, full at %.0f m; entries%s", fz, z0, fz, txt);
    }
}
static void __stdcall fe_DrawTri(const void *a, const void *b, const void *c) {   /* the probe: w = 1 / oow of vertex a (GrVertex +32) */
    float oow = *(const float *)((const BYTE *)a + 32); double w = oow > 0.0f ? 1.0 / oow : -1.0;
    int fw = 0;
    if (g_fe_alpha && g_fe_in_flush && g_fe_opaque) {       /* fade to transparent: the vertex alpha from its own w */
        fw = 1;
        const void *v[3]; int i; v[0] = a; v[1] = b; v[2] = c; g_fe_atris++;
        for (i = 0; i < 3; i++) {
            float o = *(const float *)((const BYTE *)v[i] + 32), wv = o > 0.0f ? 1.0f / o : 0.0f, f = (wv - g_fe_az0) * g_fe_ainv, al = 255.0f;
            if (f > 0.0f) { if (f > 1.0f) f = 1.0f; f = f * f * (3.0f - 2.0f * f); al = 255.0f * (1.0f - f); g_fe_averts_faded++; }
            *(float *)((BYTE *)v[i] + 28) = al;
        }
    }
    if (g_cl_force) {                                        /* a fading bush: its alpha x the feather's (or alone) */
        const void *v[3]; int i; v[0] = a; v[1] = b; v[2] = c; g_cl_ftris++;
        for (i = 0; i < 3; i++) *(float *)((BYTE *)v[i] + 28) = fw ? *(const float *)((const BYTE *)v[i] + 28) * g_cl_cur * (1.0f / 255.0f) : g_cl_cur;
    }
    if (g_fe_in_flush) { g_fe_pt_in++; if (w > 0) { if (w < g_fe_pw_in_min) g_fe_pw_in_min = w; if (w > g_fe_pw_in_max) g_fe_pw_in_max = w; if (w > 0.9 * g_fe_fog_far_built) g_fe_pt_in_far++; } }
    else { g_fe_pt_out++; if (w > 0) { if (w < g_fe_pw_out_min) g_fe_pw_out_min = w; if (w > g_fe_pw_out_max) g_fe_pw_out_max = w; } }
    p_fe_DrawTri(a, b, c);
}
static void __stdcall fe_Blend(int rsf, int rdf, int asf, int adf) {      /* ZGLIDE's grAlphaBlendFunction, in the bracket */
    g_fe_opaque_req = rsf == 4 && rdf == 0;
    g_fe_bl_last[0] = rsf; g_fe_bl_last[1] = rdf; g_fe_bl_last[2] = asf; g_fe_bl_last[3] = adf;
    if (g_cl_force) return;                                  /* the bush fade holds its blend for this record (restored after it) */
    if (g_fe_alpha && g_fe_in_flush) { g_fe_opaque = 0; fe_apply_state(); if (g_fe_opaque) return; }
    p_fe_Blend(rsf, rdf, asf, adf);
}
static void __stdcall fe_ACombine(int fn, int fac, int loc, int oth, int inv) {   /* ZGLIDE's grAlphaCombine: remembered; forced to iterated while the override is on */
    g_fe_ac_last[0] = fn; g_fe_ac_last[1] = fac; g_fe_ac_last[2] = loc; g_fe_ac_last[3] = oth; g_fe_ac_last[4] = inv;
    if (g_cl_force || (g_fe_alpha && g_fe_in_flush && g_fe_opaque)) { p_fe_ACombine(3, 1, 0, 1, 0); return; }
    p_fe_ACombine(fn, fac, loc, oth, inv);
}
static void __stdcall fe_Chroma(int mode) {                                /* ZGLIDE's grChromakeyMode: keyed records keep their own state */
    p_fe_Chroma(mode); g_fe_keyed = mode != 0;
    if (g_fe_alpha && g_fe_in_flush) fe_apply_state();
}
static void fe_alpha_attach(void) {
    HMODULE z; void *o;
    if (g_fe_ablend_tried) return;
    z = GetModuleHandleA("zglide.dll"); if (!z) return;
    g_fe_ablend_tried = 1;
    o = patch_iat(z, "glide2x.dll", "_grAlphaBlendFunction@16", (void *)fe_Blend); if (o && o != (void *)fe_Blend) p_fe_Blend = (fe_Blend_t)o;
    o = patch_iat(z, "glide2x.dll", "_grAlphaCombine@20", (void *)fe_ACombine); if (o && o != (void *)fe_ACombine) p_fe_ACombine = (fe_ACombine_t)o;
    o = patch_iat(z, "glide2x.dll", "_grChromakeyMode@4", (void *)fe_Chroma); if (o && o != (void *)fe_Chroma) p_fe_Chroma = (fe_Chroma_t)o;
    mlog("  glide-fog alpha: ZGLIDE grAlphaBlendFunction %s, grAlphaCombine %s, grChromakeyMode %s", p_fe_Blend ? "hooked" : "NOT hooked", p_fe_ACombine ? "hooked" : "NOT hooked", p_fe_Chroma ? "hooked" : "NOT hooked");
    if (!p_fe_Blend || !p_fe_ACombine || !p_fe_Chroma) { g_fe_alpha = 0; mlog("  glide-fog alpha: OFF"); }
}
static void fe_probe_attach(void) {
    HMODULE z; void *o;
    if (g_fe_probe_tried) return;
    z = GetModuleHandleA("zglide.dll"); if (!z) return;
    g_fe_probe_tried = 1;
    o = patch_iat(z, "glide2x.dll", "_grDrawTriangle@12", (void *)fe_DrawTri);
    if (o && o != (void *)fe_DrawTri) { p_fe_DrawTri = (fe_DrawTri_t)o; mlog("  glide-fog probe: ZGLIDE grDrawTriangle hooked (previous %p)", o); }
    else mlog("  glide-fog probe: grDrawTriangle NOT hooked");
}
static int fe_cl_begin(float a255) {                        /* before a fading bush record: 1 = the state is held */
    fe_probe_attach(); fe_alpha_attach();
    if (!p_fe_Blend || !p_fe_ACombine || !p_fe_DrawTri) return 0;
    g_cl_cur = a255; g_cl_force = 1;
    p_fe_Blend(1, 5, 4, 0); p_fe_ACombine(3, 1, 0, 1, 0);
    return 1;
}
static void fe_cl_end(void) {                                /* after it: ZGLIDE's last requests back (or the feather's override) */
    g_cl_force = 0;
    if (g_fe_alpha && g_fe_in_flush && g_fe_opaque) return;  /* the feather's override is the same state */
    p_fe_Blend(g_fe_bl_last[0], g_fe_bl_last[1], g_fe_bl_last[2], g_fe_bl_last[3]);
    p_fe_ACombine(g_fe_ac_last[0], g_fe_ac_last[1], g_fe_ac_last[2], g_fe_ac_last[3], g_fe_ac_last[4]);
    if (g_fe_alpha && g_fe_in_flush) fe_apply_state();
}
static void __cdecl fe_flush_wrap(void *cam, int flag) {      /* 0x48fac0(cam, 1) at 0x40216d (hardware scene) */
    int on = g_fe_fog_on && *(volatile DWORD *)(DWORD_PTR)0x00504be8 != 0 && cam != (void *)(DWORD_PTR)0x00608c80 && fe_glide_resolve();
    if (on) {
        float fz = fe_main_far();
        if (g_fe_log || g_fe_alpha) fe_probe_attach();
        if (g_fe_alpha) fe_alpha_attach();
        if (g_fe_alpha && p_fe_Blend && p_fe_DrawTri) {
            g_fe_az0 = fz * g_fe_fog_start; g_fe_ainv = fz > g_fe_az0 ? 1.0f / (fz - g_fe_az0) : 0.0f;
            g_fe_in_flush = 1; g_fe_opaque_req = 1; g_fe_opaque = 0;         /* the first records are opaque terrain: ZGLIDE's state cache may not call */
            fe_apply_state();
        } else {
            fe_fog_update(fz);
            p_fe_FogMode(2);                                 /* GR_FOG_WITH_TABLE */
            g_fe_in_flush = 1;
        }
    }
    ((void (__cdecl *)(void *, int))(DWORD_PTR)g_fe_next_flush)(cam, flag);
    if (on) {
        g_fe_in_flush = 0;
        if (g_fe_alpha && p_fe_Blend && p_fe_DrawTri) {
            fe_apply_state();                                /* in_flush is 0: the override comes off, ZGLIDE's own state back */
            if (g_fe_log && (++g_fe_frames % 300) == 0) { mlog("  glide-fog alpha: last 300 frames - %lu opaque-op triangles, %lu vertices faded (band from %.0f m)", (unsigned long)g_fe_atris, (unsigned long)g_fe_averts_faded, g_fe_az0); g_fe_atris = g_fe_averts_faded = 0; }
            return;
        }
        p_fe_FogMode(0);                                     /* GR_FOG_DISABLE */
        if (g_fe_log && p_fe_DrawTri && (++g_fe_frames % 300) == 0) {
            mlog("  glide-fog probe: last 300 frames - inside the flush %lu tris, w %.1f..%.1f (%lu past 0.9 x far); outside %lu tris, w %.1f..%.1f",
                 (unsigned long)g_fe_pt_in, g_fe_pw_in_min < 1e29 ? g_fe_pw_in_min : 0.0, g_fe_pw_in_max, (unsigned long)g_fe_pt_in_far,
                 (unsigned long)g_fe_pt_out, g_fe_pw_out_min < 1e29 ? g_fe_pw_out_min : 0.0, g_fe_pw_out_max);
            g_fe_pt_in = g_fe_pt_out = g_fe_pt_in_far = 0; g_fe_pw_in_min = g_fe_pw_out_min = 1e30; g_fe_pw_in_max = g_fe_pw_out_max = 0.0;
        }
    }
}

static void apply_far_edge(void) {
    static const BYTE eh_old[5] = { 0xe8, 0x90, 0x0a, 0x00, 0x00 };   /* call 0x491a30 at 0x490f9b (hardware) */
    static const BYTE es_old[5] = { 0xe8, 0xa9, 0x0a, 0x00, 0x00 };   /* call 0x491a30 at 0x490f82 (software) */
    char v[64], *c; DWORD nh = env_str("I76_HAZE", v, sizeof(v)), nf, ne; BYTE w5[5] = { 0xe8 }; LONG rel; int ok;
    char fv[64], ev[32], mv[32];
    nf = env_str("I76_GLIDE_FOG", fv, sizeof(fv));
    ne = env_str("I76_EDGE_FADE", ev, sizeof(ev));
    g_fe_log = env_flag("I76_FAR_EDGE_LOG", 4, 0) == 1;
    if (!nh && !nf && !ne) return;
    if (g_exe == EXE_NITRO) { mlog("  far-edge: Nitro - not applied (Gold sites only)"); return; }
    g_fe_far_env = env_str("I76_FAR_CLIP", mv, sizeof(mv)) != 0;
    if (env_str("I76_MIRROR_FAR", mv, sizeof(mv))) { float f = (float)atof(mv); if (f >= 100.0f && f <= 2500.0f) g_fe_mirror_far = f; }
    if (env_flag("I76_HAZE_MIRROR", 4, 1) == 0) g_fe_haze_mirror = 0;
    if (nh) {
        float st = (float)atof(v), str = 1.0f;
        c = strchr(v, ','); if (c) str = (float)atof(c + 1);
        if (st < 0.5f || st > 0.98f) { mlog("  far-edge: I76_HAZE start %s out of range (0.5..0.98 of the far clip) - haze not applied", v); nh = 0; }
        else if (str < 0.1f || str > 1.0f) { mlog("  far-edge: I76_HAZE strength %.2f out of range (0.1..1) - haze not applied", str); nh = 0; }
        else { g_fe_haze_start = st; g_fe_haze_str = str; }
        if (nh && env_str("I76_HAZE_TARGET", mv, sizeof(mv))) { float t = (float)atof(mv); if (t >= 0.0f && t <= 1.0f) g_fe_haze_target = t; else mlog("  far-edge: I76_HAZE_TARGET %s out of range (0..1) - 1", mv); }
    }
    if (ne && !nh) { mlog("  far-edge: I76_EDGE_FADE needs I76_HAZE (it pulls the haze start in at the void tiles) - off"); ne = 0; }
    if (ne) {
        float p = (float)atof(ev);
        if (p == 1.0f) p = 0.4f;
        if (p < 0.1f || p > 0.9f) { mlog("  far-edge: I76_EDGE_FADE %s not 1 or a pull 0.1..0.9 - off", ev); ne = 0; }
        else {
            g_fe_ring = (BYTE *)VirtualAlloc(NULL, 16384, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            g_fe_vmask = (BYTE *)VirtualAlloc(NULL, 16384, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            if (!g_fe_ring || !g_fe_vmask) { mlog("  far-edge: no memory for the tile map - edge fade off"); ne = 0; }
            else { char *cb = strchr(ev, ','); if (cb) { float bm = (float)atof(cb + 1); if (bm >= 50.0f && bm <= 640.0f) g_fe_edge_band = bm / 5.0f; else mlog("  far-edge: I76_EDGE_FADE band %s out of range (50..640 m) - 320", cb + 1); }
                   g_fe_edge_pull = p; g_fe_edge_on = 1; }
        }
    }
    if (nh) {
        g_fe_haze_on = 1;
        if (!memcmp((const void *)(DWORD_PTR)0x00490f9b, eh_old, 5) && !memcmp((const void *)(DWORD_PTR)0x00490f82, es_old, 5)) {
            rel = (LONG)((DWORD_PTR)fe_emit_wrap - (0x00490f9b + 5)); memcpy(w5 + 1, &rel, 4);
            ok = patch_bytes(0x00490f9b, eh_old, w5, 5, "terrain emit call (far-edge haze, hardware)");
            rel = (LONG)((DWORD_PTR)fe_emit_wrap - (0x00490f82 + 5)); memcpy(w5 + 1, &rel, 4);
            ok = ok && patch_bytes(0x00490f82, es_old, w5, 5, "terrain emit call (far-edge haze, software)");
            if (!ok) { g_fe_haze_on = 0; mlog("  far-edge: haze NOT applied (emit sites)"); }
        } else if (g_tm_on) { g_fe_chain_tm = 1; }        /* terrainmorph.c owns the sites: tm_emit_wrap calls fe_haze_apply */
        else { g_fe_haze_on = 0; mlog("  far-edge: the terrain emit sites are neither stock nor the morph's - haze NOT applied"); }
        if (g_fe_haze_on)
            mlog("  far-edge: haze on - terrain shade -> %.2f over the last %.0f %% of the far clip (start %.2f x far, strength %.2f, smoothstep; %s; %s)%s",
                 g_fe_haze_target, 100.0f * (1.0f - g_fe_haze_start), g_fe_haze_start, g_fe_haze_str, g_fe_haze_mirror ? "main and mirror passes" : "main pass only",
                 g_fe_chain_tm ? "chained after the morph's shade blend" : "own emit-site wrap", g_fe_edge_on ? "; edge fade on" : "");
        if (g_fe_edge_on) mlog("  far-edge: edge fade - within %.0f m of a void tile the haze start is pulled in by up to %.0f %% (continuous in the distance)", 5.0f * g_fe_edge_band, 100.0f * g_fe_edge_pull);
    }
    if (nf) {
        float st = (float)atof(fv); int good = 1;
        c = strchr(fv, ',');
        if (st < 0.5f || st > 0.98f) { mlog("  glide-fog: I76_GLIDE_FOG start %s out of range (0.5..0.98 of the far clip) - not applied", fv); good = 0; }
        if (good && c) {                                 /* <start>,<colour>[,<fraction>]: hzd | strip | sky | mix | white | rrggbb */
            char *c2 = strchr(c + 1, ','), *e = NULL; if (c2) { float f = (float)atof(c2 + 1); *c2 = 0; if (f >= 0.0f && f <= 1.0f) g_fe_fog_mixf = f; else mlog("  glide-fog: fraction %s out of range (0..1) - 0.5", c2 + 1); }
            if (!_stricmp(c + 1, "hzd") || !_stricmp(c + 1, "strip")) g_fe_fog_src = 0;
            else if (!_stricmp(c + 1, "sky")) g_fe_fog_src = 1;
            else if (!_stricmp(c + 1, "mix")) g_fe_fog_src = 2;
            else if (!_stricmp(c + 1, "white")) g_fe_fog_src = 3;
            else if (strlen(c + 1) == 6 && (strtoul(c + 1, &e, 16), e && *e == 0)) { g_fe_fog_rgb = (DWORD)strtoul(c + 1, NULL, 16); g_fe_fog_fixed = 1; }
            else { mlog("  glide-fog: colour '%s' is none of hzd / strip / sky / mix / white / rrggbb - not applied", c + 1); good = 0; }
        }
        if (good && env_flag("I76_GLIDE_FOG_ALPHA", 4, 0) == 1) g_fe_alpha = 1;
        if (good && env_str("I76_GLIDE_FOG_WM", mv, sizeof(mv))) { float wm = (float)atof(mv); if (wm > 0.001f && wm < 1000.0f) g_fe_fog_wm = wm; }
        if (good) {
            g_fe_fog_start = st;
            if (st_call_site(0x0040216d, 0x0048fac0, (void *)fe_flush_wrap, &g_fe_next_flush, "hardware scene flush (glide fog)")) {
                g_fe_fog_on = 1;
                mlog("  glide-fog: on - fog table clear to %.2f x far, full at the far clip, colour %s (fraction %.2f); fog on only around the depth-bucket flush (sky, horizon, cockpit, HUD, mirror untouched); metres per w %.3f",
                     st, g_fe_fog_fixed ? "fixed" : g_fe_fog_src == 1 ? "the sky texture's mean" : g_fe_fog_src == 2 ? "strip toward the sky" : g_fe_fog_src == 3 ? "strip toward white" : "the horizon strips' bottom rows", g_fe_fog_mixf, g_fe_fog_wm);
                if (g_fe_alpha) mlog("  glide-fog alpha: FADE TO TRANSPARENT - opaque ops in the flush blend by a per-vertex alpha 255 x (1 - smoothstep from %.2f x far to the far clip); no colour fog", st);
            } else mlog("  glide-fog: NOT applied (flush site)");
        }
    }
}
