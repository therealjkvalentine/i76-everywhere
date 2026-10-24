/* ===========================================================================
 * REAR MIRROR DETAIL  (rear-mirror lane 2026-10-23; docs/records/MIRROR-DETAIL-2026-10-23.md; lab docs/CLUTTER-AND-MIRROR.md s.2)
 * ===========================================================================
 * Included from strlkproxy.c after skymirror.c; applied after apply_terrain_lod / apply_terrain_hyst (the main terrain call site
 * 0x4020a4 is chained, whoever took it first). Gold and Nitro (nitro-owner lane 2026-10-23: DrawRearMirror Gold 0x445750 = Nitro
 * 0x42c7e0, the upload call by hand in manual_sites.txt; reads through nitro.c's g_ta_*). Off unless set:
 *
 *   I76_MIRROR_DUMP=<N>            lab instrument: every N mirror redraws write the finished mirror bitmap (the 256x64 8-bit private
 *                                  copy of ZMIRI101, [0x608cbc], as it is re-uploaded as the "RearView" texture at 0x445a3c) to
 *                                  <game>\mirror-<redraw>.bmp (8 bpp, palette = the display context's at 0x5dcfa8), the raw palette once
 *                                  to <game>\mirror-pal.bin, and log the census below for that redraw. At most 400 dumps per run.
 *   I76_MIRROR_TERRAIN_MODE=<hex>  the software draw mode given to the mirror pass's terrain leaves instead of the stock one
 *                                  ([0x59c548] as the texture-level picker 0x4923f0 set it; the main pass is untouched).
 *                                  0x15 = textured + Gouraud (per-vertex shade) + perspective; stock is the 0xe0 block (one shade
 *                                  row per polygon). Needs Terrain Textures on (the picker is only called then).
 *
 * THE MECHANISM (stock, i76.exe 9a232dcc / 6319abf7). renderer_DrawRearMirror 0x445750 at mirror level 2 queues the scene for the
 * mirror camera 0x608c80 with the SAME passes as the main view: sky light 0x401bd0, terrain renderer_QueueTerrain 0x490a00 (call
 * 0x44594e), roads 0x48e900, flamers, objects, clouds, then flushes with 0x48fac0(cam, 1). The terrain leaf fan 0x491a30 calls one
 * per-leaf callback (textured: 0x4923f0 when options_terrain_textures [0x654b8b] is set, else 0x4922f0 untextured) and then the
 * emitter 0x4924b0 / 0x4922f0, which builds the draw record (mode at rec+8 from [0x59c548], texture rec+4 from [0x59c558]), projects it
 * through 0x4f9538[mode] and queues it with 0x48fe10; the queue rewrites mode = (mode & ~0x10) | 8 (screen space). The picker
 * 0x4923f0(leaf, 1/z) chooses the texture level from the CAMERA's bitmap width ([[cam+0x3c]] = 256 for the mirror, 640 main:
 * level = clamp(9 - floor(log2(W x 40 / z)), 0, 6)), the mode from [0x59c570] (node > 8 samples) or [0x59c554] (<= 8), and the
 * texture from 0x471f00(&set[level], cam) - the camera picks the variant (the mirror's bitmap is kind 0: 8-bit). The flush draws every
 * record of a kind-0 bitmap with the software rasteriser 0x471fd0 (8-bit, span tables 0x4f8d38[mode & 0x1ff]).
 *
 * Span drawers that exist for textured terrain (exe tables read 2026-10-23): 0xf4 / 0xec (stock terrain, 0x4859e0: one shade row
 * per polygon), 0x15 (0x487ea0: textured Gouraud perspective) which the queue turns into 0x0d (0x487190, the 0x05 drawer), 0x4d
 * (0x48a580, keyed Gouraud). 0xf5 / 0xd5 / 0xe5 fall to the default entry 0x47d110 (276 of 512 modes): not drawable.
 */
/*   I76_MIRROR_EVERY=<N>           redraw the mirror every N-th frame (2..8). The 2017 Galaxy exe gates the redraw on the frame count
 *                                  (every 2nd frame); GOG's AiO build and our 6319abf7 removed the gate (`EB 17 90 90 90` at 0x4457b4:
 *                                  every frame, see REAR MIRROR CADENCE). The `call simclock_GetFrameCount` is restored to a counter
 *                                  that advances 2/N per frame, so the stock "next = count + 2" passes every N frames. Not with
 *                                  I76_MIRROR_RATE (that owns the site under I76_FRAMERATE_FIXES).
 */
static DWORD g_md_dump_n, g_md_mode, g_md_on, g_md_every, g_md_calls;
static DWORD g_md_next_upload, g_md_next_tmir, g_md_next_tmain;
static DWORD g_md_redraws, g_md_dumps, g_md_pal_done;
typedef struct { DWORD leaves, texnull, big, forced; DWORD modes[8], modev[8]; int verts; DWORD lvl[8]; } md_pass_t;
static md_pass_t g_md_mir, g_md_main, g_md_main_last;
static float g_md_tex;          /* I76_MIRROR_TEX=<f>: the mirror's leaves re-pick their texture level as a 640 x f wide view would (0 = the picker's 256) */
static DWORD g_md_pal;          /* I76_MIRROR_PAL=1: the mirror pixels remapped from the 8-bit build's palette space to the hardware build's (md_remap_bitmap below) */
static DWORD g_md_setrep;
static DWORD g_md_m16, g_md_m16sky; /* I76_MIRROR_M16_SKY=1 (opt-in; owner 2026-10-23: 'I actually prefer the original mirror cloud texture'): the sky too */
/* I76_MIRROR_M16=1: the mirror pass samples the main view's .m16 art - terrain levels (md_m16_copy); with I76_MIRROR_M16_SKY=1 also the sky draw's cloud texture (md_sky_tex at 0x405403) - quantised into the display palette */
typedef struct { DWORD src, fp; BYTE *copy; } md_m16_t;
#define MD_M16_MAX 64           /* 7 terrain levels + the road sets (10 near + 10 far slots per road type) + the sky */
static md_m16_t g_m16[MD_M16_MAX]; static int g_m16_n;
/* I76_MIRROR_M16_ROADS (default 1 = on when I76_MIRROR_M16 is; render-finish lane 2026-10-24, owner: "the mirror palette match issue also
 * applies to dirt roads - in software they are dark brown, accelerated light brown"): the road queue renderer_QueueRoadsAndDecals
 * 0x48e900 fetches each segment's texture with 0x471f00(&0x59c3a0[idx], cam) at 0x48ec53 (idx from the segment's near (z < 60 m x
 * I76_ROAD_TEX) or far slot set); the pair is {8-bit art, .m16 art} like the terrain's, the mirror's kind-0 bitmap gets the 8-bit one.
 * The asphalt's two drawings happen to agree, the dirt road's do not (8-bit dark brown, .m16 light brown). The mirror camera now gets
 * the .m16 road art quantised into the display palette (md_m16_copy, the same cache). Gold only (the Nitro site is not mapped). */
static DWORD g_md_m16roads, g_md_next_roadtex, g_md_road_n, g_md_road_sw;
/* the copy cache's fingerprint of a source texture: header, 32 spread texels and the first 16 palette words (a second guard, after
 * md_m16_check, against a new mission's art at an old address: the road sets are not in md_m16_check's signature) */
static DWORD md_m16_fp(const BYTE *m) {
    DWORD w = *(const DWORD *)m, h = *(const DWORD *)(m + 4), n, i, f = 2166136261u;
    f = (f ^ w) * 16777619u; f = (f ^ h) * 16777619u;
    h &= 0x1fffffff; n = w * h;
    if (w == 0 || h == 0 || w > 1024 || h > 1024) return f;
    for (i = 0; i < 32; i++) f = (f ^ m[8 + (n / 32) * i]) * 16777619u;
    if (*(const DWORD *)(m + 4) & 0x80000000) for (i = 0; i < 16; i++) f = (f ^ *(const WORD *)(m + 8 + n + 4 + 2 * i)) * 16777619u;
    return f;
}
static int md_level_of(DWORD tex) { int l; for (l = 0; l < 7; l++) if (tex && (*(DWORD *)(g_ta_texset + 8 * l) == tex || *(DWORD *)(g_ta_texset4 + 8 * l) == tex)) return l; for (l = 0; l < g_m16_n; l++) if ((DWORD)(DWORD_PTR)g_m16[l].copy == tex) return md_level_of(g_m16[l].src); return 7; }
/* The .m16 terrain texture (raw file: dword w, dword 0xc0000000 | h, w x h palette indices, then dword count + count RGB565 words;
 * 0x42ee21..0x42ee49 / 0x42ef20) becomes an 8-bit texture of the same shape (dword w, dword 0x40000000 | h, w x h display-palette
 * indices): each embedded palette entry is mapped once to the nearest colour of the context palette 0x5dcfa8 (0xff, the colour key,
 * never a target). The 8-bit build's own terrain art (what the mirror sampled) is a different, low-contrast drawing in another tint
 * (t05: peach vs the .m16's tan sand with dark speckles) - the owner's "no texture, different colour" 2026-10-23. */
static DWORD g_md_next_skytex;
static BYTE *md_m16_copy(DWORD src, int smooth);
static DWORD __cdecl md_sky_tex(DWORD set, DWORD cam) {        /* 0x471f00(set, cam) at 0x405403: the sky draw's cloud texture (set 0x504c38), software branch */
    DWORD r = ((DWORD (__cdecl *)(DWORD, DWORD))(DWORD_PTR)g_md_next_skytex)(set, cam);
    if (cam == g_ta_mircam && g_md_m16 && g_md_m16sky && set) { DWORD m = *(DWORD *)(DWORD_PTR)(set + 4); BYTE *c = m ? md_m16_copy(m, 1) : NULL; if (c) return (DWORD)(DWORD_PTR)c; }
    return r;
}
static BYTE *md_m16_copy(DWORD src, int smooth) {
    int i; BYTE *m = (BYTE *)(DWORD_PTR)src, *out, *ctx = (BYTE *)g_ta_ctxpal; DWORD w, h, n, k, cnt; WORD *pw; BYTE map[256];
    DWORD fp;
    if (!m) return NULL;
    fp = md_m16_fp(m);
    for (i = 0; i < g_m16_n; i++) if (g_m16[i].src == src) { if (g_m16[i].fp == fp) return g_m16[i].copy; break; }
    if (i < g_m16_n) {                                           /* same address, other art (a new mission): drop the stale copy */
        if (g_m16[i].copy) VirtualFree(g_m16[i].copy, 0, MEM_RELEASE);
        g_m16[i] = g_m16[--g_m16_n];
        mlog("  mirror-m16: texture %p changed under the cache (a new mission) - stale copy released", m);
    }
    if (g_m16_n >= MD_M16_MAX) return NULL;
    w = *(DWORD *)m; h = *(DWORD *)(m + 4);
    if (!(h & 0x80000000)) return NULL;                          /* no embedded palette: not an .m16 */
    h &= 0x1fffffff; n = w * h;
    if (w == 0 || h == 0 || w > 1024 || h > 1024) return NULL;
    cnt = *(DWORD *)(m + 8 + n); pw = (WORD *)(m + 8 + n + 4);
    if (cnt == 0 || cnt > 256) return NULL;
    for (k = 0; k < 256; k++) {
        int r, g, b, j, bj = 0; DWORD bd = 0xffffffff; WORD c = k < cnt ? pw[k] : 0;
        r = ((c >> 11) & 31) * 255 / 31; g = ((c >> 5) & 63) * 255 / 63; b = (c & 31) * 255 / 31;
        for (j = 0; j < 255; j++) { int dr = r - ctx[j * 3], dg = g - ctx[j * 3 + 1], db = b - ctx[j * 3 + 2]; DWORD d2 = (DWORD)(dr * dr + dg * dg + db * db); if (d2 < bd) { bd = d2; bj = j; } }
        map[k] = (BYTE)bj;
    }
    out = (BYTE *)VirtualAlloc(NULL, 8 + n, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!out) return NULL;
    *(DWORD *)out = w; *(DWORD *)(out + 4) = 0x40000000 | h;
    if (smooth == 1) {                                           /* the sky: a 3x3 box blur in RGB before the quantisation - the cloud art's fine texels, point-sampled
                                                                    into 256x64, came out as speckle (the main view bilinear-filters them); terrain keeps its texels */
        BYTE *rgb = (BYTE *)VirtualAlloc(NULL, n * 3, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE); DWORD x, y; WORD *cache = (WORD *)VirtualAlloc(NULL, 65536 * 2, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (rgb && cache) {
            for (k = 0; k < n; k++) { WORD c = m[8 + k] < cnt ? pw[m[8 + k]] : 0; rgb[k * 3] = (BYTE)(((c >> 11) & 31) * 255 / 31); rgb[k * 3 + 1] = (BYTE)(((c >> 5) & 63) * 255 / 63); rgb[k * 3 + 2] = (BYTE)((c & 31) * 255 / 31); }
            for (k = 0; k < 65536; k++) cache[k] = 0xffff;
            for (y = 0; y < h; y++) for (x = 0; x < w; x++) {
                int r = 0, g = 0, b = 0, dx, dy, j, bj = 0; DWORD bd = 0xffffffff, key;
                for (dy = -1; dy <= 1; dy++) for (dx = -1; dx <= 1; dx++) { DWORD xx = (x + dx + w) % w, yy = (y + dy + h) % h, q = (yy * w + xx) * 3; r += rgb[q]; g += rgb[q + 1]; b += rgb[q + 2]; }
                r /= 9; g /= 9; b /= 9; key = ((DWORD)(r >> 3) << 11) | ((DWORD)(g >> 2) << 5) | (DWORD)(b >> 3);
                if (cache[key] != 0xffff) { out[8 + y * w + x] = (BYTE)cache[key]; continue; }
                for (j = 0; j < 255; j++) { int dr = r - ctx[j * 3], dg = g - ctx[j * 3 + 1], db = b - ctx[j * 3 + 2]; DWORD d2 = (DWORD)(dr * dr + dg * dg + db * db); if (d2 < bd) { bd = d2; bj = j; } }
                cache[key] = (WORD)bj; out[8 + y * w + x] = (BYTE)bj;
            }
        } else for (k = 0; k < n; k++) out[8 + k] = map[m[8 + k]];
        if (rgb) VirtualFree(rgb, 0, MEM_RELEASE); if (cache) VirtualFree(cache, 0, MEM_RELEASE);
    } else for (k = 0; k < n; k++) out[8 + k] = map[m[8 + k]];
    g_m16[g_m16_n].src = src; g_m16[g_m16_n].fp = fp; g_m16[g_m16_n].copy = out; g_m16_n++;
    mlog("  mirror-m16: %s .m16 %p (%lux%lu, %lu palette entries) quantised into the display palette%s -> 8-bit copy %p for the mirror pass", smooth == 1 ? "sky" : smooth == 2 ? "road" : "terrain level", m, (unsigned long)w, (unsigned long)h, (unsigned long)cnt, smooth ? " after a 3x3 blur" : "", out);
    return out;
}

static DWORD __cdecl md_road_tex(DWORD set, DWORD cam) {       /* 0x471f00(set, cam) at 0x48ec53: a road segment's texture */
    DWORD r = ((DWORD (__cdecl *)(DWORD, DWORD))(DWORD_PTR)g_md_next_roadtex)(set, cam);
    if (cam == g_ta_mircam && set) {
        DWORD m = *(DWORD *)(DWORD_PTR)(set + 4); BYTE *c = m ? md_m16_copy(m, 2) : NULL;
        g_md_road_n++;
        if (c) { g_md_road_sw++; return (DWORD)(DWORD_PTR)c; }
    }
    return r;
}
static void md_count(md_pass_t *p, DWORD mode, DWORD tex, int big) {
    int i;
    p->leaves++; if (!tex) p->texnull++; if (big) p->big++;
    for (i = 0; i < 8; i++) {
        if (p->modes[i] && p->modev[i] == mode) { p->modes[i]++; return; }
        if (!p->modes[i]) { p->modev[i] = mode; p->modes[i] = 1; return; }
    }
}
static void __cdecl md_after_pick(DWORD leaf, float invz) {    /* after 0x4923f0: its globals are set, the record is not built yet */
    DWORD cam = *(volatile DWORD *)g_ta_cam;
    DWORD mode = *(volatile DWORD *)g_ta_mode, tex = *(volatile DWORD *)g_ta_tex;
    int big = leaf ? *(int *)(DWORD_PTR)(leaf + 4) > 8 : 0;
    if (cam == g_ta_mircam) {
        if (g_md_mode) { *(volatile DWORD *)g_ta_mode = g_md_mode; g_md_mir.forced++; }
        if (g_md_tex > 0.0f) {                                   /* the picker's level for a 640 x f wide view: level = 0x88 - exponent(W x 40 x 1/z), clamped 0..6 */
            float v = (640.0f * 40.0f * g_md_tex) * invz; int e = (*(int *)&v) >> 23, l = 0x88 - e; DWORD t;
            if (l < 0) l = 0; else if (l > 6) l = 6;
            t = *(DWORD *)(g_ta_texset + 8 * l);                  /* the 8-bit variant (the mirror bitmap is kind 0) */
            if (t) { *(volatile DWORD *)g_ta_tex = t; tex = t; }
        }
        if (g_md_m16) {                                          /* the .m16 art of the level the leaf got, as an 8-bit copy */
            int l = md_level_of(tex); DWORD m = l < 7 ? *(DWORD *)(g_ta_texset4 + 8 * l) : 0; BYTE *c = m ? md_m16_copy(m, 0) : NULL;
            if (c) { *(volatile DWORD *)g_ta_tex = (DWORD)(DWORD_PTR)c; tex = (DWORD)(DWORD_PTR)c; }
        }
        md_count(&g_md_mir, mode, tex, big); g_md_mir.lvl[md_level_of(tex)]++;
    } else { md_count(&g_md_main, mode, tex, big); g_md_main.lvl[md_level_of(tex)]++; }
}
static __declspec(naked) void md_pick_stub(void) {             /* in place of `push 0x4923f0` at 0x490f96: the fan calls this cdecl(leaf, invz); eax is dead after */
    __asm {
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call dword ptr [g_ta_pick]
        add  esp, 8
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call md_after_pick
        add  esp, 8
        ret
    }
}
static void md_set_report(void) {                              /* once: the 7-level terrain texture set 0x5a4588 (8-bit variant, .m16 variant); raw files: dword w, dword flags | h, texels from +8 */
    int l, k;
    for (l = 0; l < 7; l++) for (k = 0; k < 2; k++) {
        BYTE *t = *(BYTE **)(g_ta_texset + 8 * l + 4 * k); DWORD w, h, n, i, ns = 0; BYTE cnt[256];
        if (!t) { mlog("  mirror-detail: texset level %d %s: NULL", l, k ? "m16" : "8bit"); continue; }
        w = *(DWORD *)t; h = *(DWORD *)(t + 4);
        if (w == 0 || w > 1024 || (h & 0x1fffffff) == 0 || (h & 0x1fffffff) > 1024) { mlog("  mirror-detail: texset level %d %s @%p: header %08lx %08lx not a texture", l, k ? "m16" : "8bit", t, (unsigned long)w, (unsigned long)h); continue; }
        n = w * (h & 0x1fffffff); ZeroMemory(cnt, sizeof cnt);
        for (i = 0; i < n; i++) cnt[t[8 + i]] = 1;
        for (i = 0; i < 256; i++) ns += cnt[i];
        mlog("  mirror-detail: texset level %d %s @%p: %lux%lu flags %08lx, %lu distinct texel values%s", l, k ? "m16" : "8bit", t, (unsigned long)w, (unsigned long)(h & 0x1fffffff), (unsigned long)(h & 0xe0000000), (unsigned long)ns,
             (h & 0x80000000) ? " (embedded palette after the texels)" : "");
    }
    {   char path[MAX_PATH]; HANDLE f; DWORD wr; WORD *tab = *(WORD **)g_ta_tab;
        wsprintfA(path, "%s\\mirror-uptab.bin", g_dir);
        f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        if (f != INVALID_HANDLE_VALUE) { WriteFile(f, (void *)g_ta_uptab, 512, &wr, NULL); CloseHandle(f); }
        if (tab && !IsBadReadPtr(tab, 65536 * 2)) {
            wsprintfA(path, "%s\\mirror-tab.bin", g_dir);
            f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
            if (f != INVALID_HANDLE_VALUE) { WriteFile(f, tab, 65536 * 2, &wr, NULL); CloseHandle(f); }
        }
        mlog("  mirror-detail: upload table 0x608980 -> mirror-uptab.bin (entry 0xea = 0x%04x, 0xef = 0x%04x); .tab %p%s; context palette 0xea = (%u,%u,%u)",
             ((WORD *)g_ta_uptab)[0xea], ((WORD *)g_ta_uptab)[0xef], tab, tab ? " -> mirror-tab.bin" : " (none loaded)",
             ((BYTE *)g_ta_ctxpal)[0xea * 3], ((BYTE *)g_ta_ctxpal)[0xea * 3 + 1], ((BYTE *)g_ta_ctxpal)[0xea * 3 + 2]);
    }
}
/* I76_MIRROR_LOD=<m> (1..256): the mirror pass's terrain LOD factor relative to the stock constants, whatever I76_TERRAIN_LOD gave the
 * main view (the 256x64 mirror cannot show LOD 24; measured 2026-10-23: the mirror at the main's LOD 24 over 2300 m cost 15-55 % of the
 * frame). QueueTerrain 0x490a00 derives the pass's split constant [0x6442c8] from [0x4fad20] (x focal / half width: the mirror's own
 * resolution is already in it) and the height-error threshold [0x6442cc] from [0x4fad24] at every pass (0x490aa1 / 0x490ac9); terrain
 * init 0x493080 wrote both at mission load from the (patched) per-level immediates. So the mirror wrap scales the two floats by m / f
 * (A) and f / m (B) around its call and restores them: data only, the main pass never sees it. */
static float g_md_lod, g_md_fa = 1.0f, g_md_fb = 1.0f;   /* fa / fb = what apply_terrain_lod gave the main view */
/* nitro-owner lane 2026-10-24: the .m16 copies are keyed by the source texture's address. A new mission loads its own .m16 art, often
 * at the addresses the previous mission's used (the game's heap is rebuilt per mission), so the cache handed the mirror the previous
 * mission's copy - and on Nitro, after Abort Mission > another scenario, the WHOLE picture came up in the previous mission's colours
 * (yellow / green, console 2026-10-24 00:40; every mirror key but M16 on: right colours; M16 off alone: right colours). The cache now
 * belongs to one set of terrain textures and one display palette: when the 7 level pointers or the context palette change (a mission
 * change) it is emptied and the old copies released, before the mirror pass picks any texture. */
static DWORD g_m16_sig;
static void md_m16_check(void) {
    DWORD sig = 2166136261u; int i; const BYTE *ctx = (const BYTE *)(DWORD_PTR)g_ta_ctxpal;
    for (i = 0; i < 14; i++) sig = (sig ^ *(const DWORD *)(DWORD_PTR)(g_ta_texset + 4 * i)) * 16777619u;
    for (i = 0; i < 768; i += 4) sig = (sig ^ *(const DWORD *)(ctx + i)) * 16777619u;
    if (sig == g_m16_sig) return;
    if (g_m16_sig && g_m16_n) {
        for (i = 0; i < g_m16_n; i++) if (g_m16[i].copy) VirtualFree(g_m16[i].copy, 0, MEM_RELEASE);
        mlog("  mirror-m16: terrain textures / display palette changed (a new mission) - %d cached .m16 copies released", g_m16_n);
        g_m16_n = 0;
    }
    g_m16_sig = sig;
}
static void __cdecl md_terrain_mir(void *cam) {
    float a = *(volatile float *)g_ta_fa, b = *(volatile float *)g_ta_fb;
    if (g_md_m16) md_m16_check();
    ZeroMemory(&g_md_mir, sizeof g_md_mir); g_md_road_n = g_md_road_sw = 0;
    if (g_md_lod > 0.0f) { *(volatile float *)g_ta_fa = a * (g_md_lod / g_md_fa); *(volatile float *)g_ta_fb = b * (g_md_fb / g_md_lod); }
    ((void (__cdecl *)(void *))(DWORD_PTR)g_md_next_tmir)(cam);
    if (g_md_lod > 0.0f) { *(volatile float *)g_ta_fa = a; *(volatile float *)g_ta_fb = b; }
    g_md_mir.verts = *(volatile int *)g_ta_vn;
}
static void __cdecl md_terrain_main(void *cam) {
    ZeroMemory(&g_md_main, sizeof g_md_main);
    ((void (__cdecl *)(void *))(DWORD_PTR)g_md_next_tmain)(cam);
    g_md_main.verts = *(volatile int *)g_ta_vn;
    g_md_main_last = g_md_main;
}
static void md_modes_txt(const md_pass_t *p, char *out, size_t cap) {
    int i; size_t n = 0; out[0] = 0;
    for (i = 0; i < 8 && p->modes[i]; i++) n += (size_t)_snprintf(out + n, cap - n, "%s0x%lx:%lu", i ? " " : "", (unsigned long)p->modev[i], (unsigned long)p->modes[i]);
}
static void md_dump(void) {
    BYTE *bm = *(BYTE **)g_ta_mirbm; DWORD w, h, y, wr; BYTE *px, *pal = (BYTE *)g_ta_ctxpal;
    char path[MAX_PATH]; HANDLE f; BITMAPFILEHEADER bf; BITMAPINFOHEADER bi; RGBQUAD q[256]; int i;
    if (!bm) return;
    w = *(DWORD *)bm; h = *(WORD *)(bm + 4); px = *(BYTE **)(bm + 0x14);
    if (!px || w == 0 || h == 0 || w > 1024 || h > 1024 || (w & 3)) { mlog("  mirror-detail: dump skipped (bitmap %lux%lu px %p)", (unsigned long)w, (unsigned long)h, px); return; }
    if (!g_md_pal_done) {
        g_md_pal_done = 1;
        wsprintfA(path, "%s\\mirror-pal.bin", g_dir);
        f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        if (f != INVALID_HANDLE_VALUE) { WriteFile(f, pal, 1024, &wr, NULL); CloseHandle(f); }
    }
    for (i = 0; i < 256; i++) { q[i].rgbRed = pal[i * 3]; q[i].rgbGreen = pal[i * 3 + 1]; q[i].rgbBlue = pal[i * 3 + 2]; q[i].rgbReserved = 0; }
    wsprintfA(path, "%s\\mirror-%05lu.bmp", g_dir, (unsigned long)g_md_redraws);
    f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) return;
    ZeroMemory(&bf, sizeof bf); ZeroMemory(&bi, sizeof bi);
    bf.bfType = 0x4d42; bf.bfOffBits = sizeof bf + sizeof bi + sizeof q; bf.bfSize = bf.bfOffBits + w * h;
    bi.biSize = sizeof bi; bi.biWidth = (LONG)w; bi.biHeight = (LONG)h; bi.biPlanes = 1; bi.biBitCount = 8; bi.biClrUsed = 256;
    WriteFile(f, &bf, sizeof bf, &wr, NULL); WriteFile(f, &bi, sizeof bi, &wr, NULL); WriteFile(f, q, sizeof q, &wr, NULL);
    for (y = h; y-- > 0;) WriteFile(f, px + y * w, w, &wr, NULL);
    CloseHandle(f);
    g_md_dumps++;
}
/* I76_MIRROR_PAL=1: the mirror's indices are 8-bit-build palette indices (X.act): the 8-bit textures, the clear 0xea, the cloud
 * colour 0xef and the shared .lum shade tables were all made for it, while the hardware build displays everything through
 * X_16.act (the WRLD of miss16\X.MSN names it; K1e4) - ZGLIDE converts the uploaded 8-bit mirror with that one (its
 * SetTexturePalette export is a stub: `xor eax, eax; ret`), so where the two palettes differ (t05: 0xea sky (175,213,241) in
 * X.act, (128,170,173) in X_16.act; the cloud texels come out peach, the sand ochre) the mirror shows the wrong colours - the
 * owner's "orange sky" 2026-10-23. Fix: before each upload, map every pixel from X.act space to the nearest colour of X_16.act
 * (one 256-entry table per mission, built once; the pair is found by matching the context palette 0x5dcfa8 against the 16
 * X_16.act palettes compiled in (mirrorpal.h) - best sum of absolute differences, since the context copy carries the monitor
 * brightness gamma 0x4797f0). A mission whose palette matches nothing well (a stem with no 8-bit twin, or a mod) is left alone. */
#include "mirrorpal.h"
static BYTE g_mp_map[256]; static int g_mp_pair = -1, g_mp_tried; static DWORD g_mp_ctxsum;
static void md_remap_bitmap(void) {
    BYTE *bm = *(BYTE **)g_ta_mirbm, *px, *ctx = (BYTE *)g_ta_ctxpal; DWORD w, h, n, i, sum = 0;
    if (!bm) return;
    w = *(DWORD *)bm; h = *(WORD *)(bm + 4); px = *(BYTE **)(bm + 0x14);
    if (!px || w == 0 || h == 0 || w > 1024 || h > 1024) return;
    for (i = 0; i < 768; i++) sum = sum * 31 + ctx[i];
    if (sum != g_mp_ctxsum || !g_mp_tried) {                     /* a new palette (mission change): identify the pair again */
        int best = -1, k, j; DWORD bestd = 0xffffffff;
        g_mp_ctxsum = sum; g_mp_tried = 1; g_mp_pair = -1;
        for (k = 0; k < MP_PAIRS; k++) {
            DWORD dd = 0; for (i = 0; i < 768; i++) { int t = (int)ctx[i] - (int)mp_pairs[k].p16[i]; dd += (DWORD)(t < 0 ? -t : t); }
            if (dd < bestd) { bestd = dd; best = k; }
        }
        if (best >= 0 && bestd < 768 * 24) {                     /* within 24/channel on average: the gamma copy of that palette */
            const BYTE *p8 = mp_pairs[best].p8, *p16 = mp_pairs[best].p16;
            for (i = 0; i < 256; i++) {
                int r = p8[i * 3], g = p8[i * 3 + 1], b = p8[i * 3 + 2], bj = (int)i; DWORD bd = 0xffffffff;
                for (j = 0; j < 255; j++) {                      /* 0xff = the texture colour key: never a target */
                    int dr = r - p16[j * 3], dg = g - p16[j * 3 + 1], db = b - p16[j * 3 + 2]; DWORD d2 = (DWORD)(dr * dr + dg * dg + db * db);
                    if (d2 < bd) { bd = d2; bj = j; }
                }
                g_mp_map[i] = (BYTE)bj;
            }
            g_mp_map[0xff] = 0xff;
            g_mp_pair = best;
            mlog("  mirror-pal: context palette matches %s_16.act (sum of differences %lu): mirror pixels remapped %s.act -> nearest %s_16.act colour (0xea -> 0x%02x, 0xef -> 0x%02x)",
                 mp_pairs[best].stem, (unsigned long)bestd, mp_pairs[best].stem, mp_pairs[best].stem, g_mp_map[0xea], g_mp_map[0xef]);
        } else mlog("  mirror-pal: context palette matches no compiled-in _16 palette (best %s, sum %lu) - mirror left as is", best >= 0 ? mp_pairs[best].stem : "-", (unsigned long)bestd);
    }
    if (g_mp_pair < 0) return;
    n = w * h;
    for (i = 0; i < n; i++) px[i] = g_mp_map[px[i]];
}
static void __cdecl md_upload(DWORD tex, const char *name) {   /* 0x42ec20 at 0x445a3c: the finished mirror (scene + frame mask) goes up as "RearView" */
    g_md_redraws++;
    if (g_md_pal) md_remap_bitmap();                             /* before the dump: the PNGs show what is uploaded */
    if (g_md_dump_n && g_md_redraws % g_md_dump_n == 0 && g_md_dumps < 400) {
        char mm[160], mn[160]; BYTE *bm = *(BYTE **)g_ta_mirbm;
        md_dump();
        if (!g_md_setrep) { g_md_setrep = 1; md_set_report(); }
        md_modes_txt(&g_md_mir, mm, sizeof mm); md_modes_txt(&g_md_main_last, mn, sizeof mn);
        mlog("  mirror-detail: redraw %lu dumped: mirror pass %d verts, %lu leaves (big %lu, tex null %lu, forced %lu) modes {%s} levels [%lu %lu %lu %lu %lu %lu %lu ?%lu]; main pass %d verts, %lu leaves (big %lu, tex null %lu) modes {%s} levels [%lu %lu %lu %lu %lu %lu %lu ?%lu]; options terrain-detail %u textures %u mirror %u visibility %u; bitmap %lux%lu kind %lu; mirror road segments %lu (.m16 copy %lu)",
             (unsigned long)g_md_redraws, g_md_mir.verts, (unsigned long)g_md_mir.leaves, (unsigned long)g_md_mir.big, (unsigned long)g_md_mir.texnull, (unsigned long)g_md_mir.forced, mm,
             (unsigned long)g_md_mir.lvl[0], (unsigned long)g_md_mir.lvl[1], (unsigned long)g_md_mir.lvl[2], (unsigned long)g_md_mir.lvl[3], (unsigned long)g_md_mir.lvl[4], (unsigned long)g_md_mir.lvl[5], (unsigned long)g_md_mir.lvl[6], (unsigned long)g_md_mir.lvl[7],
             g_md_main_last.verts, (unsigned long)g_md_main_last.leaves, (unsigned long)g_md_main_last.big, (unsigned long)g_md_main_last.texnull, mn,
             (unsigned long)g_md_main_last.lvl[0], (unsigned long)g_md_main_last.lvl[1], (unsigned long)g_md_main_last.lvl[2], (unsigned long)g_md_main_last.lvl[3], (unsigned long)g_md_main_last.lvl[4], (unsigned long)g_md_main_last.lvl[5], (unsigned long)g_md_main_last.lvl[6], (unsigned long)g_md_main_last.lvl[7],
             *(BYTE *)g_ta_o82, *(BYTE *)g_ta_o8b, *(BYTE *)g_ta_o8d, *(BYTE *)g_ta_o8a,
             bm ? (unsigned long)*(DWORD *)bm : 0ul, bm ? (unsigned long)*(WORD *)(bm + 4) : 0ul, bm ? (unsigned long)*(DWORD *)(bm + 8) : 0ul, (unsigned long)g_md_road_n, (unsigned long)g_md_road_sw);
    }
    ((void (__cdecl *)(DWORD, const char *))(DWORD_PTR)g_md_next_upload)(tex, name);
}
static int __cdecl md_frame_count(void) { return (int)((++g_md_calls * 2) / g_md_every); }   /* in place of simclock_GetFrameCount at 0x4457b4 */
static void apply_mirror_every(void) {
    static const BYTE gate_galaxy[5] = { 0xE8, 0x17, 0x70, 0x05, 0x00 };   /* call 0x49c7d0 at 0x4457b4 (Galaxy: every 2nd frame) */
    static const BYTE gate_aio[5]    = { 0xEB, 0x17, 0x90, 0x90, 0x90 };   /* jmp 0x4457cd: gate removed (AiO / 6319abf7: every frame) */
    BYTE w[5] = { 0xE8 }; LONG rel; char v[8]; int ok; const char *layout;
    if (!env_str("I76_MIRROR_EVERY", v, sizeof(v))) return;
    g_md_every = (DWORD)atoi(v);
    if (g_md_every < 2 || g_md_every > 8) { mlog("  mirror-every: %s out of range (2..8) - not applied", v); g_md_every = 0; return; }
    {   char mv[4]; if (env_str("I76_MIRROR_RATE", mv, sizeof(mv)) && mv[0] != '0' && g_ratefix) { mlog("  mirror-every: I76_MIRROR_RATE owns the gate - off"); g_md_every = 0; return; } }
    if (g_exe == EXE_NITRO) {                                /* Nitro keeps the Galaxy gate (DrawRearMirror 0x42c7e0, read side by side 2026-10-23):
                                                                `call 0x4a2bf0` (frame count) / cmp [0x523328] / jl at 0x42c844 - every 2nd frame stock */
        if (!nitro_patch_call(0x0042c844, 0x004a2bf0, (void *)md_frame_count, NULL, "rear mirror refresh gate frame count (mirror-every)")) { g_md_every = 0; mlog("  mirror-every: Nitro gate site not as expected - off"); return; }
        mlog("  mirror-every: the rear mirror redraws every %lu-th frame (Nitro: stock gate every 2nd frame, its frame count replaced)", (unsigned long)g_md_every);
        return;
    }
    rel = (LONG)((DWORD_PTR)md_frame_count - (0x004457b4 + 5)); memcpy(w + 1, &rel, 4);
    if (memcmp((void *)0x004457b4, gate_aio, 5) == 0) { layout = "AiO: gate was removed, mirror every frame"; ok = patch_bytes(0x004457b4, gate_aio, w, 5, "rear mirror refresh gate (mirror-every, AiO)"); }
    else { layout = "Galaxy: every 2nd frame"; ok = patch_bytes(0x004457b4, gate_galaxy, w, 5, "rear mirror refresh gate (mirror-every, Galaxy)"); }
    if (!ok) { g_md_every = 0; mlog("  mirror-every: gate site not as expected - off"); return; }
    mlog("  mirror-every: the rear mirror redraws every %lu-th frame (stock layout %s)", (unsigned long)g_md_every, layout);
}
static void apply_mirror_detail(void) {
    static const BYTE push_old[5] = { 0x68, 0xF0, 0x23, 0x49, 0x00 };   /* push 0x4923f0 at 0x490f96 (textured leaf callback) */
    BYTE push_new[5] = { 0x68 }; DWORD a; char v[16]; int n = 0;
    apply_mirror_every();     /* I76_MIRROR_EVERY=<N> */
    if (env_str("I76_MIRROR_DUMP", v, sizeof(v))) g_md_dump_n = (DWORD)atoi(v);
    if (env_str("I76_MIRROR_TERRAIN_MODE", v, sizeof(v))) g_md_mode = (DWORD)strtoul(v, NULL, 16) & 0x1ff;
    if (env_str("I76_MIRROR_LOD", v, sizeof(v))) {
        char va[16]; float f = 1.0f;
        g_md_lod = (float)atof(v);
        if (g_md_lod < 1.0f || g_md_lod > 256.0f) { mlog("  mirror-lod: %s out of range (1..256) - not applied", v); g_md_lod = 0.0f; }
        if (env_str("I76_TERRAIN_LOD", va, sizeof(va))) f = (float)atof(va);
        g_md_fa = env_str("I76_TERRAIN_LOD_A", va, sizeof(va)) ? (float)atof(va) : f;
        g_md_fb = env_str("I76_TERRAIN_LOD_B", va, sizeof(va)) ? (float)atof(va) : f;
        if (g_md_fa < 1.0f || g_md_fa > 256.0f) g_md_fa = 1.0f;
        if (g_md_fb < 1.0f || g_md_fb > 256.0f) g_md_fb = 1.0f;
    }
    if (env_str("I76_MIRROR_TEX", v, sizeof(v))) { g_md_tex = (float)atof(v); if (g_md_tex < 0.25f || g_md_tex > 16.0f) { mlog("  mirror-tex: %s out of range (0.25..16) - not applied", v); g_md_tex = 0.0f; } }
    g_md_pal = env_flag("I76_MIRROR_PAL", 8, 0) == 1;
    g_md_m16 = env_flag("I76_MIRROR_M16", 8, 0) == 1;
    g_md_m16roads = g_md_m16 && env_flag("I76_MIRROR_M16_ROADS", 8, 1) == 1;   /* default on with M16: the dirt roads' two drawings differ (owner 2026-10-24) */
    g_md_m16sky = g_md_m16 && env_flag("I76_MIRROR_M16_SKY", 8, 0) == 1;   /* default off: the stock 8-bit cloud art (the owner prefers it; "a tint to the mirror") */
    if (!g_md_dump_n && !g_md_mode && g_md_lod <= 0.0f && g_md_tex <= 0.0f && !g_md_pal && !g_md_m16) return;
    if (!g_ta_ok) { mlog("  mirror-detail: the terrain renderer's addresses are not all mapped (Nitro) - off"); g_md_dump_n = g_md_mode = 0; g_md_lod = g_md_tex = 0.0f; g_md_pal = g_md_m16 = 0; return; }
    if (g_md_dump_n || g_md_mode || g_md_tex > 0.0f || g_md_pal || g_md_m16) {
        a = (DWORD)(DWORD_PTR)md_pick_stub; memcpy(push_new + 1, &a, 4);
        n += patch_bytes(0x00490f96, push_old, push_new, 5, "terrain leaf texture picker (mirror-detail)");
        n += st_call_site(0x004020a4, 0x00490a00, (void *)md_terrain_main, &g_md_next_tmain, "main QueueTerrain call (mirror-detail)");
        n += st_call_site(0x00445a3c, 0x0042ec20, (void *)md_upload, &g_md_next_upload, "mirror texture re-upload (mirror-detail)");
    } else n = 3;
    n += st_call_site(0x0044594e, 0x00490a00, (void *)md_terrain_mir, &g_md_next_tmir, "mirror QueueTerrain call (mirror-detail)");
    if (g_md_m16roads) {
        if (g_exe == EXE_NITRO) { mlog("  mirror-m16: roads - the Nitro road texture site is not mapped; roads stay the 8-bit art"); g_md_m16roads = 0; }
        else if (!st_call_site(0x0048ec53, 0x00471f00, (void *)md_road_tex, &g_md_next_roadtex, "road segment texture pick (mirror-m16 roads)")) { mlog("  mirror-m16: road site not patched - roads stay the 8-bit art"); g_md_m16roads = 0; }
    }
    if (g_md_m16sky) { if (!st_call_site(0x00405403, 0x00471f00, (void *)md_sky_tex, &g_md_next_skytex, "sky draw cloud texture pick, software branch (mirror-m16)")) { mlog("  mirror-m16: sky site not patched - clouds stay the 8-bit art"); g_md_m16sky = 0; } }
    g_md_on = n == 4;
    if (!g_md_on) { mlog("  mirror-detail: %d/4 sites - OFF (mode override / mirror LOD / tex / pal / m16 disabled)", n); g_md_mode = 0; g_md_dump_n = 0; g_md_lod = g_md_tex = 0.0f; g_md_pal = g_md_m16 = g_md_m16roads = 0; return; }
    mlog("  mirror-detail: on -%s%s%s%s%s%s", g_md_dump_n ? " dump every N redraws;" : "", g_md_mode ? " forced terrain mode;" : "",
         g_md_lod > 0.0f ? " mirror terrain LOD of its own;" : "", g_md_tex > 0.0f ? " mirror texture level re-picked;" : "", g_md_pal ? " pixels remapped to the _16 palette;" : "", g_md_m16 ? " terrain from the .m16 art;" : "");
    if (g_md_tex > 0.0f) {
        char tv[16]; float tt = env_str("I76_TERRAIN_TEX", tv, sizeof(tv)) ? (float)atof(tv) : 1.0f;
        mlog("  mirror-tex: the mirror's terrain leaves take the texture level a %.0f px wide view at x1 would at the same distance (absolute: I76_TERRAIN_TEX x%.0f scales the picker's own choice, which for the mirror's 256 px is a %.0f px view at x1; the main view's is %.0f)",
             640.0f * g_md_tex, tt, 256.0f * tt, 640.0f * tt);
    }
    if (g_md_m16) mlog("  mirror-m16: the mirror pass samples the main view's .m16 terrain art%s, quantised into the display palette once per texture", g_md_m16sky ? " and its .m16 cloud art (I76_MIRROR_M16_SKY=1)" : " (sky: the stock 8-bit cloud art; I76_MIRROR_M16_SKY=1 opts in)");
    if (g_md_m16) mlog("  mirror-m16: roads %s", g_md_m16roads ? "from the .m16 road art too (I76_MIRROR_M16_ROADS=0 keeps the 8-bit road art)" : "stay the 8-bit road art");
    if (g_md_pal) mlog("  mirror-pal: the mirror's pixels are remapped from the 8-bit build's palette to the nearest colours of the hardware build's before each upload (%d palette pairs compiled in)", MP_PAIRS);
    if (g_md_lod > 0.0f) mlog("  mirror-lod: the mirror pass splits terrain at x%.2f the stock distance (height-error / %.2f); the main view keeps x%.2f / %.2f", g_md_lod, g_md_lod, g_md_fa, g_md_fb);
    if (g_md_dump_n) mlog("  mirror-detail: dump every %lu mirror redraws to %s\\mirror-<redraw>.bmp (palette 0x5dcfa8 -> mirror-pal.bin)", (unsigned long)g_md_dump_n, g_dir);
    if (g_md_mode) mlog("  mirror-detail: mirror pass terrain mode forced to 0x%lx (span drawer 0x%08lx after the queue's | 8 / & ~0x10)", (unsigned long)g_md_mode,
                        (unsigned long)*(DWORD *)(g_ta_span + 4 * (((g_md_mode & ~0x10u) | 8u) & 0x1ff)));
}
