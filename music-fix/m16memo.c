/* ===========================================================================
 * M16 VARIANT MEMO  (I76_M16_MEMO; terrain-pass-opt lane 2026-10-25, docs/records/TERRAIN-PASS-OPT-PLAN-2026-10-25.md C1 / unit U3)
 * ===========================================================================
 * Included by strlkproxy.c before passtimers.c. Gold only.
 *   I76_M16_MEMO=1   the hardware (.m16) variant of a face texture is resolved by name once per mission and kept, instead of being
 *                    released and re-acquired from the file cache every frame
 *   I76_M16_MEMO=2   lab VERIFY: the stock path runs unchanged; on every load the memo would have answered, the pointer it would have
 *                    returned is compared with the one the stock acquire returns (a log line per 600 frames)
 * THE STOCK PATH (i76.exe 6319abf7, U1 counters 2026-10-25): renderer_GetFaceTexture 0x44a290 (the clutter loop calls it for every bush
 * face record, 0x45c7eb, ~600 / frame on T05) finds the face entry by name (_stricmp chain) and, for a hardware camera, calls
 * image_LoadM16Variant 0x471980(&entry+0x38, entry+4) at 0x44a5f0: a cached slot returns at once; an empty one builds "<name>.m16" and
 * goes through vfs_GetFileSize 0x46fee0 + vfs_AcquireFile 0x46ffc0 (upper-casing, name compares in the file cache: msvcrt's locale
 * path, ~3 MultiByteToWideChar per compare), then marks the header from FULLRES.LST. The slots are emptied again every frame by
 * renderer_ReleaseM16Texture 0x471b70 (vfs_ReleaseFile by name), so ~330 acquire + release pairs run per frame for the same names.
 * THE MEMO: name -> the pointer the first acquire returned. A load into an empty slot whose name is in the memo takes that pointer (no
 * acquire); the first load of a name is the stock acquire, and the memo owns that one reference. A release of a slot that holds a memo
 * pointer only empties the slot (the reference stays with the memo). The memo gives its references back after
 * image_ShutdownFaceTextures 0x44a630 (its one call 0x40463f: mission end; the shutdown's own releases are skipped like any other) and
 * is dropped without releasing at image_InitFaceTextures 0x449610 (call 0x4033bc) if a shutdown was missed. The pointer is the file
 * cache's buffer for that name: the same one the stock acquire hands back while a reference is held (verify mode checks it per load),
 * so ZGLIDE sees the same texture source; its TMU cache (keyed downstream, tex-census NO-SLOT) is not involved. */
#define MM_SLOTS 4096
typedef struct { char name[16]; DWORD p; } mm_ent_t;
static mm_ent_t *g_mm; static DWORD *g_mm_pset; static int g_mm_mode;   /* pset: the memo's pointers, open addressing (0 = empty) */ static DWORD g_mm_n, g_mm_hits, g_mm_miss, g_mm_skip, g_mm_vchk, g_mm_vbad, g_mm_frames, g_mm_flushed;
static DWORD g_mm_next_load = 0x00471980, g_mm_rel_site[8], g_mm_rel_next[8], g_mm_next_shut = 0x0044a630, g_mm_next_init = 0x00449610; static int g_mm_rel_ns;
static DWORD mm_hash(const char *s) { DWORD h = 2166136261u; int i; for (i = 0; i < 16 && s[i]; i++) h = (h ^ (BYTE)s[i]) * 16777619u; return h; }
static mm_ent_t *mm_find(const char *name, int add) {
    DWORD i = mm_hash(name) & (MM_SLOTS - 1), n;
    for (n = 0; n < MM_SLOTS; n++, i = (i + 1) & (MM_SLOTS - 1)) {
        if (!g_mm[i].name[0]) { if (!add || g_mm_n >= MM_SLOTS / 2) return NULL; lstrcpynA(g_mm[i].name, name, 16); g_mm[i].p = 0; g_mm_n++; return &g_mm[i]; }
        if (strncmp(g_mm[i].name, name, 15) == 0) return &g_mm[i];
    }
    return NULL;
}
static DWORD mm_phash(DWORD p) { p ^= p >> 16; p *= 0x45d9f3bu; p ^= p >> 16; return p & (MM_SLOTS - 1); }
static void mm_padd(DWORD p) {
    DWORD i = mm_phash(p), n;
    for (n = 0; n < MM_SLOTS; n++, i = (i + 1) & (MM_SLOTS - 1)) { if (g_mm_pset[i] == p) return; if (!g_mm_pset[i]) { g_mm_pset[i] = p; return; } }
}
static int mm_owns(DWORD p) {                      /* is p a memo pointer (the release path: ~255 set slots / frame on T05) */
    DWORD i, n; if (!p || !g_mm_n) return 0;
    for (n = 0, i = mm_phash(p); n < MM_SLOTS; n++, i = (i + 1) & (MM_SLOTS - 1)) { if (g_mm_pset[i] == p) return 1; if (!g_mm_pset[i]) return 0; }
    return 0;
}
static DWORD __cdecl mm_load(DWORD *slot, const char *name) {          /* the call at 0x44a5f0 */
    mm_ent_t *e; DWORD p;
    if (!slot || *slot || !name || !name[0] || lstrlenA(name) > 15) return ((DWORD (__cdecl *)(DWORD *, const char *))(DWORD_PTR)g_mm_next_load)(slot, name);
    e = mm_find(name, 1);
    if (g_mm_mode == 1 && e && e->p) { *slot = e->p; g_mm_hits++; return e->p; }
    p = ((DWORD (__cdecl *)(DWORD *, const char *))(DWORD_PTR)g_mm_next_load)(slot, name);
    if (g_mm_mode == 2) { if (e && e->p) { g_mm_vchk++; if (e->p != p) g_mm_vbad++; } else if (e && p) e->p = p; return p; }   /* verify: stock path, pointers compared */
    if (e && p && !e->p) { e->p = p; mm_padd(p); g_mm_miss++; }         /* this reference now belongs to the memo */
    return p;
}
static void __cdecl mm_release(DWORD *slot, const char *name) {        /* the release call sites */
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(), nx = 0x00471b70; int i;
    for (i = 0; i < g_mm_rel_ns; i++) if (g_mm_rel_site[i] + 5 == ra) { nx = g_mm_rel_next[i]; break; }
    if (g_mm_mode == 1 && slot && *slot && mm_owns(*slot)) { *slot = 0; g_mm_skip++; return; }
    ((void (__cdecl *)(DWORD *, const char *))(DWORD_PTR)nx)(slot, name);
}
static void mm_flush(int give_back) {
    DWORD i, k = 0;
    for (i = 0; i < MM_SLOTS; i++) if (g_mm[i].name[0]) {
        if (give_back && g_mm[i].p && g_mm_mode == 1) { DWORD s = g_mm[i].p; ((void (__cdecl *)(DWORD *, const char *))(DWORD_PTR)0x00471b70)(&s, g_mm[i].name); k++; }
        g_mm[i].name[0] = 0; g_mm[i].p = 0;
    }
    if (g_mm_n) mlog("  m16-memo: %s - %lu names dropped%s", give_back ? "face textures shut down (mission end)" : "face textures re-initialised without a shutdown", (unsigned long)g_mm_n, give_back ? ", their references given back" : " (references not given back: the file cache was rebuilt)");
    memset(g_mm_pset, 0, MM_SLOTS * sizeof(DWORD)); g_mm_n = 0; g_mm_flushed += k;
}
static void __cdecl mm_shutdown_wrap(void) { ((void (__cdecl *)(void))(DWORD_PTR)g_mm_next_shut)(); mm_flush(1); }
static void __cdecl mm_init_wrap(void) { if (g_mm_n) mm_flush(0); ((void (__cdecl *)(void))(DWORD_PTR)g_mm_next_init)(); }
static void m16_memo_frame(void) {
    if (!g_mm_mode || ++g_mm_frames < 600) return;
    if (g_mm_mode == 1) mlog("  m16-memo: 600 frames: %lu loads answered by the memo (%.1f / frame), %lu first acquires, %lu releases skipped (%.1f / frame); %lu names held",
                             (unsigned long)g_mm_hits, g_mm_hits / 600.0, (unsigned long)g_mm_miss, (unsigned long)g_mm_skip, g_mm_skip / 600.0, (unsigned long)g_mm_n);
    else mlog("  m16-memo verify: 600 frames: %lu loads the memo would have answered, %lu with a different pointer than the stock acquire; %lu names", (unsigned long)g_mm_vchk, (unsigned long)g_mm_vbad, (unsigned long)g_mm_n);
    g_mm_hits = g_mm_miss = g_mm_skip = g_mm_vchk = g_mm_vbad = 0; g_mm_frames = 0;
}
static void apply_m16_memo(void) {
    static const DWORD rs[5] = { 0x449fd2, 0x44a128, 0x44a237, 0x44a8bf, 0x44a6aa };
    int k, ok, mode = env_int("I76_M16_MEMO", 4, 0);
    if (mode != 1 && mode != 2) return;
    if (g_exe != EXE_GOLD) { mlog("  m16-memo: Gold only - off"); return; }
    g_mm = (mm_ent_t *)VirtualAlloc(NULL, MM_SLOTS * sizeof(mm_ent_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_mm_pset = (DWORD *)VirtualAlloc(NULL, MM_SLOTS * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!g_mm || !g_mm_pset) { mlog("  m16-memo: no memory - off"); return; }
    g_mm_mode = mode;
    ok = st_call_site(0x0044a5f0, 0x00471980, (void *)mm_load, &g_mm_next_load, "m16-memo LoadM16Variant call");
    for (k = 0; k < 5 && ok; k++) if (st_call_site(rs[k], 0x00471b70, (void *)mm_release, &g_mm_rel_next[g_mm_rel_ns], "m16-memo ReleaseM16Texture call")) g_mm_rel_site[g_mm_rel_ns++] = rs[k]; else ok = 0;
    ok = ok && st_call_site(0x0040463f, 0x0044a630, (void *)mm_shutdown_wrap, &g_mm_next_shut, "m16-memo ShutdownFaceTextures call");
    ok = ok && st_call_site(0x004033bc, 0x00449610, (void *)mm_init_wrap, &g_mm_next_init, "m16-memo InitFaceTextures call");
    if (!ok) { g_mm_mode = 0; mlog("  m16-memo: a call site differs - PARTIAL, memo off (the wrapped sites call through)"); return; }
    mlog("  m16-memo: %s (face textures' .m16 variants resolved by name once per mission; 1 load + 5 release + shutdown / init sites)",
         mode == 1 ? "on" : "VERIFY (stock path; the memo's pointer compared per load)");
}
