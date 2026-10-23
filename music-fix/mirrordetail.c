/* ===========================================================================
 * REAR MIRROR DETAIL  (rear-mirror lane 2026-10-23; docs/records/MIRROR-DETAIL-2026-10-23.md; lab docs/CLUTTER-AND-MIRROR.md s.2)
 * ===========================================================================
 * Included from strlkproxy.c after skymirror.c; applied after apply_terrain_lod / apply_terrain_hyst (the main terrain call site
 * 0x4020a4 is chained, whoever took it first). Gold only (the Nitro site map has none of these sites yet). Off unless set:
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
typedef struct { DWORD leaves, texnull, big, forced; DWORD modes[8], modev[8]; int verts; } md_pass_t;
static md_pass_t g_md_mir, g_md_main, g_md_main_last;

static void md_count(md_pass_t *p, DWORD mode, DWORD tex, int big) {
    int i;
    p->leaves++; if (!tex) p->texnull++; if (big) p->big++;
    for (i = 0; i < 8; i++) {
        if (p->modes[i] && p->modev[i] == mode) { p->modes[i]++; return; }
        if (!p->modes[i]) { p->modev[i] = mode; p->modes[i] = 1; return; }
    }
}
static void __cdecl md_after_pick(DWORD leaf) {                /* after 0x4923f0: its globals are set, the record is not built yet */
    DWORD cam = *(volatile DWORD *)0x006442d4;
    DWORD mode = *(volatile DWORD *)0x0059c548, tex = *(volatile DWORD *)0x0059c558;
    int big = leaf ? *(int *)(DWORD_PTR)(leaf + 4) > 8 : 0;
    if (cam == 0x00608c80) {
        if (g_md_mode) { *(volatile DWORD *)0x0059c548 = g_md_mode; g_md_mir.forced++; }
        md_count(&g_md_mir, mode, tex, big);
    } else md_count(&g_md_main, mode, tex, big);
}
static __declspec(naked) void md_pick_stub(void) {             /* in place of `push 0x4923f0` at 0x490f96: the fan calls this cdecl(leaf, invz); eax is dead after */
    __asm {
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        mov  eax, 0x004923f0
        call eax
        add  esp, 8
        push dword ptr [esp + 4]
        call md_after_pick
        add  esp, 4
        ret
    }
}
/* I76_MIRROR_LOD=<m> (1..256): the mirror pass's terrain LOD factor relative to the stock constants, whatever I76_TERRAIN_LOD gave the
 * main view (the 256x64 mirror cannot show LOD 24; measured 2026-10-23: the mirror at the main's LOD 24 over 2300 m cost 15-55 % of the
 * frame). QueueTerrain 0x490a00 derives the pass's split constant [0x6442c8] from [0x4fad20] (x focal / half width: the mirror's own
 * resolution is already in it) and the height-error threshold [0x6442cc] from [0x4fad24] at every pass (0x490aa1 / 0x490ac9); terrain
 * init 0x493080 wrote both at mission load from the (patched) per-level immediates. So the mirror wrap scales the two floats by m / f
 * (A) and f / m (B) around its call and restores them: data only, the main pass never sees it. */
static float g_md_lod, g_md_fa = 1.0f, g_md_fb = 1.0f;   /* fa / fb = what apply_terrain_lod gave the main view */
static void __cdecl md_terrain_mir(void *cam) {
    float a = *(volatile float *)0x004fad20, b = *(volatile float *)0x004fad24;
    ZeroMemory(&g_md_mir, sizeof g_md_mir);
    if (g_md_lod > 0.0f) { *(volatile float *)0x004fad20 = a * (g_md_lod / g_md_fa); *(volatile float *)0x004fad24 = b * (g_md_fb / g_md_lod); }
    ((void (__cdecl *)(void *))(DWORD_PTR)g_md_next_tmir)(cam);
    if (g_md_lod > 0.0f) { *(volatile float *)0x004fad20 = a; *(volatile float *)0x004fad24 = b; }
    g_md_mir.verts = *(volatile int *)0x006442ec;
}
static void __cdecl md_terrain_main(void *cam) {
    ZeroMemory(&g_md_main, sizeof g_md_main);
    ((void (__cdecl *)(void *))(DWORD_PTR)g_md_next_tmain)(cam);
    g_md_main.verts = *(volatile int *)0x006442ec;
    g_md_main_last = g_md_main;
}
static void md_modes_txt(const md_pass_t *p, char *out, size_t cap) {
    int i; size_t n = 0; out[0] = 0;
    for (i = 0; i < 8 && p->modes[i]; i++) n += (size_t)_snprintf(out + n, cap - n, "%s0x%lx:%lu", i ? " " : "", (unsigned long)p->modev[i], (unsigned long)p->modes[i]);
}
static void md_dump(void) {
    BYTE *bm = *(BYTE **)0x00608cbc; DWORD w, h, y, wr; BYTE *px, *pal = (BYTE *)0x005dcfa8;
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
static void __cdecl md_upload(DWORD tex, const char *name) {   /* 0x42ec20 at 0x445a3c: the finished mirror (scene + frame mask) goes up as "RearView" */
    g_md_redraws++;
    if (g_md_dump_n && g_md_redraws % g_md_dump_n == 0 && g_md_dumps < 400) {
        char mm[160], mn[160]; BYTE *bm = *(BYTE **)0x00608cbc;
        md_dump();
        md_modes_txt(&g_md_mir, mm, sizeof mm); md_modes_txt(&g_md_main_last, mn, sizeof mn);
        mlog("  mirror-detail: redraw %lu dumped: mirror pass %d verts, %lu leaves (big %lu, tex null %lu, forced %lu) modes {%s}; main pass %d verts, %lu leaves (big %lu, tex null %lu) modes {%s}; options terrain-detail %u textures %u mirror %u visibility %u; bitmap %lux%lu kind %lu",
             (unsigned long)g_md_redraws, g_md_mir.verts, (unsigned long)g_md_mir.leaves, (unsigned long)g_md_mir.big, (unsigned long)g_md_mir.texnull, (unsigned long)g_md_mir.forced, mm,
             g_md_main_last.verts, (unsigned long)g_md_main_last.leaves, (unsigned long)g_md_main_last.big, (unsigned long)g_md_main_last.texnull, mn,
             *(BYTE *)0x654b82, *(BYTE *)0x654b8b, *(BYTE *)0x654b8d, *(BYTE *)0x654b8a,
             bm ? (unsigned long)*(DWORD *)bm : 0ul, bm ? (unsigned long)*(WORD *)(bm + 4) : 0ul, bm ? (unsigned long)*(DWORD *)(bm + 8) : 0ul);
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
    if (g_exe == EXE_NITRO) { mlog("  mirror-every: not ported to Nitro - off"); g_md_every = 0; return; }
    {   char mv[4]; if (env_str("I76_MIRROR_RATE", mv, sizeof(mv)) && mv[0] != '0' && g_ratefix) { mlog("  mirror-every: I76_MIRROR_RATE owns the gate - off"); g_md_every = 0; return; } }
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
    if (!g_md_dump_n && !g_md_mode && g_md_lod <= 0.0f) return;
    if (g_exe == EXE_NITRO) { mlog("  mirror-detail: not ported to Nitro - off"); g_md_dump_n = g_md_mode = 0; g_md_lod = 0.0f; return; }
    if (g_md_dump_n || g_md_mode) {
        a = (DWORD)(DWORD_PTR)md_pick_stub; memcpy(push_new + 1, &a, 4);
        n += patch_bytes(0x00490f96, push_old, push_new, 5, "terrain leaf texture picker (mirror-detail)");
        n += st_call_site(0x004020a4, 0x00490a00, (void *)md_terrain_main, &g_md_next_tmain, "main QueueTerrain call (mirror-detail)");
        n += st_call_site(0x00445a3c, 0x0042ec20, (void *)md_upload, &g_md_next_upload, "mirror texture re-upload (mirror-detail)");
    } else n = 3;
    n += st_call_site(0x0044594e, 0x00490a00, (void *)md_terrain_mir, &g_md_next_tmir, "mirror QueueTerrain call (mirror-detail)");
    g_md_on = n == 4;
    if (!g_md_on) { mlog("  mirror-detail: %d/4 sites - OFF (mode override / mirror LOD disabled)", n); g_md_mode = 0; g_md_dump_n = 0; g_md_lod = 0.0f; return; }
    mlog("  mirror-detail: on - %s%s%s%s%s", g_md_dump_n ? "dump every N redraws" : "", g_md_dump_n && g_md_mode ? "; " : "",
         g_md_mode ? "mirror terrain leaves drawn in a forced mode" : "", (g_md_dump_n || g_md_mode) && g_md_lod > 0.0f ? "; " : "",
         g_md_lod > 0.0f ? "mirror terrain LOD of its own" : "");
    if (g_md_lod > 0.0f) mlog("  mirror-lod: the mirror pass splits terrain at x%.2f the stock distance (height-error / %.2f); the main view keeps x%.2f / %.2f", g_md_lod, g_md_lod, g_md_fa, g_md_fb);
    if (g_md_dump_n) mlog("  mirror-detail: dump every %lu mirror redraws to %s\\mirror-<redraw>.bmp (palette 0x5dcfa8 -> mirror-pal.bin)", (unsigned long)g_md_dump_n, g_dir);
    if (g_md_mode) mlog("  mirror-detail: mirror pass terrain mode forced to 0x%lx (span drawer 0x%08lx after the queue's | 8 / & ~0x10)", (unsigned long)g_md_mode,
                        (unsigned long)*(DWORD *)(0x004f8d38 + 4 * (((g_md_mode & ~0x10u) | 8u) & 0x1ff)));
}
