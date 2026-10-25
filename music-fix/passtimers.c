/* ===========================================================================
 * PASS TIMERS + PASS DUMP  (terrain-pass-opt lane 2026-10-25; docs/records/TERRAIN-PASS-OPT-PLAN-2026-10-25.md unit U1)
 * ===========================================================================
 * Included by strlkproxy.c just before faredge.c (fe_DrawTri reads g_pt_on). Lab instruments, Gold only, off unless set:
 *   I76_PASS_TIMERS=1   every 600 frames one "pass-timers:" block in mciproxy.log:
 *     - fe_DrawTri (faredge.c's IAT hook on ZGLIDE's grDrawTriangle): calls inside / outside the hardware flush, the hook's own
 *       time and the synchronous time of the call into glide2x (dgVoodoo), per call (ns) and per frame (us); rdtsc, calibrated
 *       against QPC over the window, the cost of one rdtsc pair subtracted;
 *     - clutter_draw_wrap / clutter_build / clutter_template_table own time per frame (the clutter block's hooks);
 *     - the face-texture path: renderer_GetFaceTexture 0x44a290 (every direct call site wrapped, inclusive time, by caller),
 *       image_LoadM16Variant 0x471980 (the one call at 0x44a5f0: cached = the slot was set, else a load from the pak), and
 *       renderer_ReleaseM16Texture 0x471b70 (the call sites in SetFaceTextureFrame / Free / Unload / GetPrivateFaceBitmap),
 *       split by phase (main clutter call, rear mirror 0x445750, hardware flush, other);
 *     - i76.exe's MSVCRT _stricmp (every call, by return address: the innermost exe caller) and KERNEL32 CreateFileA /
 *       GetFileAttributesA / FindFirstFileA (by return address); msvcrt's own MultiByteToWideChar (count, time);
 *     - registry opens / queries: every IAT slot of every loaded module that holds advapi32 / kernelbase RegOpenKeyExA/W,
 *       RegOpenKeyA/W, RegQueryValueExA/W, RegCloseKey, or ntdll NtOpenKey / NtOpenKeyEx (kernelbase's own imports) is
 *       repointed (patched at frame 300 and again at 1500), counted by the calling module (the first return address on
 *       the stack outside ntdll / kernelbase / kernel32 / advapi32 / sechost);
 *     - Glide state calls ZGLIDE makes (its IAT, hooked when ZGLIDE loads, below faredge.c's hooks): grTexSource (and how
 *       many change the texture address), grAlphaBlendFunction, grAlphaCombine, grColorCombine, grChromakeyMode,
 *       grTexDownloadMipMap; and whether glide2x exports grDrawPolygonVertexList / grDrawPlanarPolygonVertexList.
 *   I76_PASS_DUMP=<file>[,<first frame>,<count>]   equivalence stream: per main terrain pass one line
 *       T,<frame>,<n>,<fnv V>,<fnv U>  (FNV-1a over the raw bytes of the vertex array [0x5dd320] and the UV / shade array
 *       [0x5dd2ec], 3 floats per vertex each, after the morph's blends and the haze, just before the leaf emit),
 *     per frame D,<frame>,<tris>,<fnv>  (every grDrawTriangle inside the hardware flush: x, y, r, alpha, oow of its three
 *       vertices as fe_DrawTri hands them to glide2x) and C,<frame>,<records>,<fnv>  (the flush's polygon draws through
 *       clutter_draw_wrap: record type, vertex count, texture handle). Frames first..first+count-1 also write the raw V / U
 *       arrays to <file>.bin (per pass: DWORD frame, DWORD n, V[3n] floats, U[3n] floats). Default window 0 frames.
 * Nothing here changes a vertex, a shade, an alpha or a call order: every hook calls through with the same arguments. */
#include <intrin.h>
static int g_pt_on, g_pd_on;
static DWORD g_pt_frames, g_pt_report_at;
static double g_pt_ns_per_tick;                  /* calibrated: ns per TSC tick */
static unsigned __int64 g_pt_tsc0; static LARGE_INTEGER g_pt_q0;
static unsigned __int64 g_pt_rd_ovh;             /* ticks of one back-to-back rdtsc pair */
/* fe_DrawTri: [0] inside the flush, [1] outside */
static unsigned __int64 g_pt_dt_own[2], g_pt_dt_sync[2]; static DWORD g_pt_dt_n[2];
/* clutter hooks */
static unsigned __int64 g_pt_cl_draw, g_pt_cl_build, g_pt_cl_tab; static DWORD g_pt_cl_draw_n;
/* phase: 0 other, 1 main clutter call, 2 rear mirror, 3 hardware flush */
static int g_pt_phase;
#define PT_PH 4
static const char *g_pt_phname[PT_PH] = { "other", "clutter", "mirror", "flush" };
static unsigned __int64 g_pt_gft_t[PT_PH], g_pt_m16_t[PT_PH], g_pt_rel_t[PT_PH];
static DWORD g_pt_gft_n[PT_PH], g_pt_m16_load[PT_PH], g_pt_m16_cached[PT_PH], g_pt_rel_n[PT_PH], g_pt_rel_live[PT_PH];
/* return-address buckets (stricmp, file A-API, GetFaceTexture callers, registry by module) */
typedef struct { DWORD ra; DWORD n; unsigned __int64 t; } pt_bk_t;
#define PT_BK 24
static pt_bk_t g_pt_sc[PT_BK], g_pt_fa[PT_BK], g_pt_gf[PT_BK], g_pt_rg[PT_BK], g_pt_rl[PT_BK];
static DWORD g_pt_sc_n, g_pt_fa_n, g_pt_rg_n, g_pt_mb_n; static unsigned __int64 g_pt_sc_t, g_pt_mb_t;
static void pt_bk_add(pt_bk_t *b, DWORD ra, unsigned __int64 t) {
    int i;
    for (i = 0; i < PT_BK && b[i].ra && b[i].ra != ra; i++) ;
    if (i == PT_BK) i = PT_BK - 1, ra = 0xffffffff;                       /* overflow bucket */
    if (!b[i].ra) b[i].ra = ra;
    b[i].n++; b[i].t += t;
}
/* glide state calls */
static DWORD g_pt_gs_texsrc, g_pt_gs_texchg, g_pt_gs_blend, g_pt_gs_acomb, g_pt_gs_ccomb, g_pt_gs_chroma, g_pt_gs_dl, g_pt_gs_last_tex = 0xffffffff;
static int g_pt_poly_vl = -1, g_pt_poly_pvl = -1;
/* pass dump */
static FILE *g_pd_f, *g_pd_bin; static DWORD g_pd_first, g_pd_count, g_pd_tris, g_pd_recs, g_pd_hd = 2166136261u, g_pd_hc = 2166136261u;
static __inline DWORD pd_fnv(DWORD h, const void *p, DWORD n) { const BYTE *b = (const BYTE *)p; while (n--) { h ^= *b++; h *= 16777619u; } return h; }

static __inline unsigned __int64 pt_now(void) { return __rdtsc(); }
static __inline unsigned __int64 pt_net(unsigned __int64 d) { return d > g_pt_rd_ovh ? d - g_pt_rd_ovh : 0; }

/* ---- fe_DrawTri (faredge.c) ---- */
static __inline void pt_drawtri_add(int in, unsigned __int64 own, unsigned __int64 sync) { g_pt_dt_own[in ? 0 : 1] += pt_net(own); g_pt_dt_sync[in ? 0 : 1] += pt_net(sync); g_pt_dt_n[in ? 0 : 1]++; }
static __inline void pd_drawtri(const void *a, const void *b, const void *c) {   /* inside the flush: what glide2x receives */
    const void *v[3]; int i; v[0] = a; v[1] = b; v[2] = c;
    for (i = 0; i < 3; i++) {
        const BYTE *p = (const BYTE *)v[i];
        g_pd_hd = pd_fnv(g_pd_hd, p + 0, 8);  /* x, y */
        g_pd_hd = pd_fnv(g_pd_hd, p + 12, 4); /* r */
        g_pd_hd = pd_fnv(g_pd_hd, p + 28, 8); /* alpha, oow */
    }
    g_pd_tris++;
}

/* ---- the face-texture path (call-site wraps) ---- */
#define PT_GFT_SITES 32
static DWORD g_pt_gft_site[PT_GFT_SITES], g_pt_gft_next[PT_GFT_SITES]; static int g_pt_gft_ns;
static DWORD __cdecl pt_gft_wrap(DWORD obj, DWORD name, DWORD cam) {
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(), r, nx = 0x0044a290; int i; unsigned __int64 t0, t1;
    for (i = 0; i < g_pt_gft_ns; i++) if (g_pt_gft_site[i] + 5 == ra) { nx = g_pt_gft_next[i]; break; }
    t0 = pt_now();
    r = ((DWORD (__cdecl *)(DWORD, DWORD, DWORD))(DWORD_PTR)nx)(obj, name, cam);
    t1 = pt_now();
    g_pt_gft_n[g_pt_phase]++; g_pt_gft_t[g_pt_phase] += pt_net(t1 - t0);
    pt_bk_add(g_pt_gf, ra - 5, pt_net(t1 - t0));
    return r;
}
static DWORD g_pt_m16_next = 0x00471980, g_pt_rel_next[8], g_pt_rel_site[8]; static int g_pt_rel_ns;
static DWORD __cdecl pt_m16_wrap(DWORD *slot, const char *name) {
    int cached = slot && *slot; DWORD r; unsigned __int64 t0 = pt_now(), t1;
    r = ((DWORD (__cdecl *)(DWORD *, const char *))(DWORD_PTR)g_pt_m16_next)(slot, name);
    t1 = pt_now();
    if (cached) g_pt_m16_cached[g_pt_phase]++; else g_pt_m16_load[g_pt_phase]++;
    g_pt_m16_t[g_pt_phase] += pt_net(t1 - t0);
    return r;
}
static void __cdecl pt_rel_wrap(DWORD *slot, const char *name) {
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(), nx = 0x00471b70; int i, live = slot && *slot; unsigned __int64 t0, t1;
    for (i = 0; i < g_pt_rel_ns; i++) if (g_pt_rel_site[i] + 5 == ra) { nx = g_pt_rel_next[i]; break; }
    t0 = pt_now();
    ((void (__cdecl *)(DWORD *, const char *))(DWORD_PTR)nx)(slot, name);
    t1 = pt_now();
    g_pt_rel_n[g_pt_phase]++; if (live) g_pt_rel_live[g_pt_phase]++; g_pt_rel_t[g_pt_phase] += pt_net(t1 - t0);
    pt_bk_add(g_pt_rl, (ra - 5) | (live ? 0u : 0x80000000u), pt_net(t1 - t0));   /* bit 31: the slot was already empty */
}
static DWORD g_pt_mir_next = 0x00445750;
static void __cdecl pt_mirror_wrap(DWORD a, DWORD b, DWORD c) {        /* renderer_DrawRearMirror at 0x401fde (cdecl; up to 3 args forwarded) */
    int ph = g_pt_phase; g_pt_phase = 2;
    ((void (__cdecl *)(DWORD, DWORD, DWORD))(DWORD_PTR)g_pt_mir_next)(a, b, c);
    g_pt_phase = ph;
}

/* ---- exe imports: _stricmp, file A-API; msvcrt's MultiByteToWideChar ---- */
static int (__cdecl *p_pt_stricmp)(const char *, const char *);
static int __cdecl pt_stricmp(const char *a, const char *b) {
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(); int r; unsigned __int64 t0 = pt_now(), t1;
    r = p_pt_stricmp(a, b); t1 = pt_now();
    g_pt_sc_n++; g_pt_sc_t += pt_net(t1 - t0); pt_bk_add(g_pt_sc, ra, pt_net(t1 - t0));
    return r;
}
static HANDLE (WINAPI *p_pt_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static HANDLE WINAPI pt_CreateFileA(LPCSTR f, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD fl, HANDLE t) {
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(); HANDLE h; unsigned __int64 t0 = pt_now();
    h = p_pt_CreateFileA(f, a, s, sa, c, fl, t); g_pt_fa_n++; pt_bk_add(g_pt_fa, ra, pt_net(pt_now() - t0)); return h;
}
static DWORD (WINAPI *p_pt_GetFileAttributesA)(LPCSTR);
static DWORD WINAPI pt_GetFileAttributesA(LPCSTR f) {
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(), r; unsigned __int64 t0 = pt_now();
    r = p_pt_GetFileAttributesA(f); g_pt_fa_n++; pt_bk_add(g_pt_fa, ra | 0x80000000u, pt_net(pt_now() - t0)); return r;   /* bit 31: GetFileAttributesA */
}
static HANDLE (WINAPI *p_pt_FindFirstFileA)(LPCSTR, LPWIN32_FIND_DATAA);
static HANDLE WINAPI pt_FindFirstFileA(LPCSTR f, LPWIN32_FIND_DATAA d) {
    DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(); HANDLE h; unsigned __int64 t0 = pt_now();
    h = p_pt_FindFirstFileA(f, d); g_pt_fa_n++; pt_bk_add(g_pt_fa, ra | 0x40000000u, pt_net(pt_now() - t0)); return h;   /* bit 30: FindFirstFileA */
}
static int (WINAPI *p_pt_MBtoWC)(UINT, DWORD, LPCSTR, int, LPWSTR, int);
static int WINAPI pt_MBtoWC(UINT cp, DWORD fl, LPCSTR s, int n, LPWSTR w, int wn) {
    int r; unsigned __int64 t0 = pt_now();
    r = p_pt_MBtoWC(cp, fl, s, n, w, wn); g_pt_mb_n++; g_pt_mb_t += pt_net(pt_now() - t0); return r;
}

/* ---- registry: every module's IAT slot that holds one of the targets ---- */
static HMODULE g_pt_sys[6]; static int g_pt_nsys;
static int pt_is_sys(DWORD a) {
    HMODULE m = NULL; int i;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)(DWORD_PTR)a, &m) || !m) return -1;
    for (i = 0; i < g_pt_nsys; i++) if (m == g_pt_sys[i]) return 1;
    return 0;
}
/* the first return address on the stack outside the system modules: a candidate is a DWORD whose preceding bytes are a call */
static DWORD pt_caller(const DWORD *sp) {
    int i; const DWORD *top = (const DWORD *)((NT_TIB *)NtCurrentTeb())->StackBase;
    for (i = 0; i < 256 && sp + i < top; i++) {
        DWORD a = sp[i]; const BYTE *p = (const BYTE *)(DWORD_PTR)a; int s; HMODULE hm = NULL;
        /* inside a loaded image = readable (not IsBadReadPtr: its first-chance fault reads as a CRASH line in the log) */
        if (a < 0x10000 || !GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)(DWORD_PTR)(a - 6), &hm) || !hm) continue;
        if (!(p[-5] == 0xE8 || (p[-6] == 0xFF && (p[-5] & 0x38) == 0x10) || (p[-2] == 0xFF && (p[-1] & 0x38) == 0x10) || (p[-3] == 0xFF && (p[-2] & 0x38) == 0x10))) continue;
        s = pt_is_sys(a);
        if (s == 0) return a;
    }
    return 0;
}
#define PT_RG_FN 10
static const char *g_pt_rg_name[PT_RG_FN] = { "RegOpenKeyExA", "RegOpenKeyExW", "RegOpenKeyA", "RegOpenKeyW", "RegQueryValueExA", "RegQueryValueExW", "RegCloseKey", "NtOpenKey", "NtOpenKeyEx", "RegCreateKeyExA" };
static void *g_pt_rg_real[PT_RG_FN][3];          /* advapi32, kernelbase, ntdll export addresses */
static DWORD g_pt_rg_cnt[PT_RG_FN];
static void pt_rg_note(int k, const DWORD *sp) { DWORD c = pt_caller(sp); g_pt_rg_cnt[k]++; g_pt_rg_n++; pt_bk_add(g_pt_rg, c, 0); }
/* each wrapper calls the exact export it replaced (stored per slot is overkill: the advapi32 export forwards to kernelbase anyway;
 * for a slot that held the kernelbase / ntdll address we keep that one: g_pt_rg_use[k] set at patch time per address kind) */
static void *g_pt_rg_use[PT_RG_FN][3];
#define PT_RG_WRAP(k, name, ret, sig, args) \
    static ret WINAPI pt_rg_##name##_0 sig { pt_rg_note(k, (const DWORD *)_AddressOfReturnAddress()); return ((ret (WINAPI *) sig)g_pt_rg_use[k][0]) args; } \
    static ret WINAPI pt_rg_##name##_1 sig { pt_rg_note(k, (const DWORD *)_AddressOfReturnAddress()); return ((ret (WINAPI *) sig)g_pt_rg_use[k][1]) args; } \
    static ret WINAPI pt_rg_##name##_2 sig { pt_rg_note(k, (const DWORD *)_AddressOfReturnAddress()); return ((ret (WINAPI *) sig)g_pt_rg_use[k][2]) args; }
PT_RG_WRAP(0, OKEA, LONG, (HKEY h, LPCSTR s, DWORD o, REGSAM m, PHKEY r), (h, s, o, m, r))
PT_RG_WRAP(1, OKEW, LONG, (HKEY h, LPCWSTR s, DWORD o, REGSAM m, PHKEY r), (h, s, o, m, r))
PT_RG_WRAP(2, OKA, LONG, (HKEY h, LPCSTR s, PHKEY r), (h, s, r))
PT_RG_WRAP(3, OKW, LONG, (HKEY h, LPCWSTR s, PHKEY r), (h, s, r))
PT_RG_WRAP(4, QVA, LONG, (HKEY h, LPCSTR s, LPDWORD rs, LPDWORD t, LPBYTE d, LPDWORD c), (h, s, rs, t, d, c))
PT_RG_WRAP(5, QVW, LONG, (HKEY h, LPCWSTR s, LPDWORD rs, LPDWORD t, LPBYTE d, LPDWORD c), (h, s, rs, t, d, c))
PT_RG_WRAP(6, CK, LONG, (HKEY h), (h))
PT_RG_WRAP(7, NOK, LONG, (PHANDLE k, DWORD a, void *oa), (k, a, oa))
PT_RG_WRAP(8, NOKX, LONG, (PHANDLE k, DWORD a, void *oa, ULONG o), (k, a, oa, o))
PT_RG_WRAP(9, CKEA, LONG, (HKEY h, LPCSTR s, DWORD r0, LPSTR c, DWORD o, REGSAM m, LPSECURITY_ATTRIBUTES sa, PHKEY r, LPDWORD d), (h, s, r0, c, o, m, sa, r, d))
static void *g_pt_rg_hook[PT_RG_FN][3] = {
    { (void *)pt_rg_OKEA_0, (void *)pt_rg_OKEA_1, (void *)pt_rg_OKEA_2 }, { (void *)pt_rg_OKEW_0, (void *)pt_rg_OKEW_1, (void *)pt_rg_OKEW_2 },
    { (void *)pt_rg_OKA_0, (void *)pt_rg_OKA_1, (void *)pt_rg_OKA_2 }, { (void *)pt_rg_OKW_0, (void *)pt_rg_OKW_1, (void *)pt_rg_OKW_2 },
    { (void *)pt_rg_QVA_0, (void *)pt_rg_QVA_1, (void *)pt_rg_QVA_2 }, { (void *)pt_rg_QVW_0, (void *)pt_rg_QVW_1, (void *)pt_rg_QVW_2 },
    { (void *)pt_rg_CK_0, (void *)pt_rg_CK_1, (void *)pt_rg_CK_2 }, { (void *)pt_rg_NOK_0, (void *)pt_rg_NOK_1, (void *)pt_rg_NOK_2 },
    { (void *)pt_rg_NOKX_0, (void *)pt_rg_NOKX_1, (void *)pt_rg_NOKX_2 }, { (void *)pt_rg_CKEA_0, (void *)pt_rg_CKEA_1, (void *)pt_rg_CKEA_2 } };
static int pt_iat_by_addr(HMODULE mod) {           /* repoint every IAT slot of mod that holds a target address */
    BYTE *base = (BYTE *)mod; IMAGE_NT_HEADERS *nt; IMAGE_DATA_DIRECTORY dd; IMAGE_IMPORT_DESCRIPTOR *d; int n = 0;
    __try {
        nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
        dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
        if (!dd.VirtualAddress) return 0;
        for (d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress); d->Name; d++) {
            IMAGE_THUNK_DATA *ft = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
            for (; ft->u1.Function; ft++) {
                int k, j; void *cur = (void *)ft->u1.Function;
                for (k = 0; k < PT_RG_FN; k++) for (j = 0; j < 3; j++) if (g_pt_rg_real[k][j] && cur == g_pt_rg_real[k][j]) {
                    DWORD old;
                    if (VirtualProtect(&ft->u1.Function, sizeof(void *), PAGE_READWRITE, &old)) {
                        g_pt_rg_use[k][j] = cur; ft->u1.Function = (DWORD_PTR)g_pt_rg_hook[k][j];
                        VirtualProtect(&ft->u1.Function, sizeof(void *), old, &old); n++;
                    }
                    goto next;
                }
            next: ;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return n;
}
static void pt_reg_attach(void) {
    static const char *mods[3] = { "advapi32.dll", "kernelbase.dll", "ntdll.dll" };
    HMODULE ms[256]; DWORD need = 0; int i, k, j, slots = 0, nm = 0; HANDLE pr = GetCurrentProcess();
    BOOL (WINAPI *enm)(HANDLE, HMODULE *, DWORD, LPDWORD) = (BOOL (WINAPI *)(HANDLE, HMODULE *, DWORD, LPDWORD))GetProcAddress(GetModuleHandleA("kernel32.dll"), "K32EnumProcessModules");
    if (!g_pt_nsys) {
        const char *sn[6] = { "ntdll.dll", "kernelbase.dll", "kernel32.dll", "advapi32.dll", "sechost.dll", "win32u.dll" };
        for (i = 0; i < 6; i++) { HMODULE m = GetModuleHandleA(sn[i]); if (m) g_pt_sys[g_pt_nsys++] = m; }
        for (k = 0; k < PT_RG_FN; k++) for (j = 0; j < 3; j++) { HMODULE m = GetModuleHandleA(mods[j]); g_pt_rg_real[k][j] = m ? (void *)GetProcAddress(m, g_pt_rg_name[k]) : NULL; }
    }
    if (!enm || !enm(pr, ms, sizeof ms, &need)) { mlog("  pass-timers: registry hooks - no module list"); return; }
    nm = (int)(need / sizeof(HMODULE)); if (nm > 256) nm = 256;
    for (i = 0; i < nm; i++) slots += pt_iat_by_addr(ms[i]);
    mlog("  pass-timers: registry hooks - %d IAT slots repointed over %d modules (frame %lu)", slots, nm, (unsigned long)g_frame);
}

/* ---- Glide state calls (ZGLIDE's IAT, at load: below faredge.c's hooks) ---- */
static void (__stdcall *p_pt_TexSource)(int, DWORD, DWORD, void *); static void (__stdcall *p_pt_Blend)(int, int, int, int);
static void (__stdcall *p_pt_ACombine)(int, int, int, int, int); static void (__stdcall *p_pt_CCombine)(int, int, int, int, int);
static void (__stdcall *p_pt_Chroma)(int); static void (__stdcall *p_pt_Download)(int, DWORD, DWORD, void *);
static void __stdcall pt_TexSource(int t, DWORD a, DWORD eo, void *i) { g_pt_gs_texsrc++; if (a != g_pt_gs_last_tex) { g_pt_gs_texchg++; g_pt_gs_last_tex = a; } p_pt_TexSource(t, a, eo, i); }
static void __stdcall pt_Blend(int a, int b, int c, int d) { g_pt_gs_blend++; p_pt_Blend(a, b, c, d); }
static void __stdcall pt_ACombine(int a, int b, int c, int d, int e) { g_pt_gs_acomb++; p_pt_ACombine(a, b, c, d, e); }
static void __stdcall pt_CCombine(int a, int b, int c, int d, int e) { g_pt_gs_ccomb++; p_pt_CCombine(a, b, c, d, e); }
static void __stdcall pt_Chroma(int m) { g_pt_gs_chroma++; p_pt_Chroma(m); }
static void __stdcall pt_Download(int t, DWORD a, DWORD eo, void *i) { g_pt_gs_dl++; p_pt_Download(t, a, eo, i); }
static void pt_glide_attach(HMODULE z) {
    void *o; HMODULE g = GetModuleHandleA("glide2x.dll");
    static int done; if (done || !g_pt_on) return; done = 1;
#define PT_GH(name, hook, ptr) o = patch_iat(z, "glide2x.dll", name, (void *)hook); if (o && o != (void *)hook) *(void **)&ptr = o;
    PT_GH("_grTexSource@16", pt_TexSource, p_pt_TexSource)
    PT_GH("_grAlphaBlendFunction@16", pt_Blend, p_pt_Blend)
    PT_GH("_grAlphaCombine@20", pt_ACombine, p_pt_ACombine)
    PT_GH("_grColorCombine@20", pt_CCombine, p_pt_CCombine)
    PT_GH("_grChromakeyMode@4", pt_Chroma, p_pt_Chroma)
    PT_GH("_grTexDownloadMipMap@16", pt_Download, p_pt_Download)
#undef PT_GH
    if (g) { g_pt_poly_vl = GetProcAddress(g, "_grDrawPolygonVertexList@8") != NULL; g_pt_poly_pvl = GetProcAddress(g, "_grDrawPlanarPolygonVertexList@8") != NULL; }
    mlog("  pass-timers: ZGLIDE glide state hooks: texsource %s, blend %s, acombine %s, ccombine %s, chroma %s, download %s; glide2x %p exports grDrawPolygonVertexList %s, grDrawPlanarPolygonVertexList %s, grDrawPolygon %s",
         p_pt_TexSource ? "ok" : "NOT", p_pt_Blend ? "ok" : "NOT", p_pt_ACombine ? "ok" : "NOT", p_pt_CCombine ? "ok" : "NOT", p_pt_Chroma ? "ok" : "NOT", p_pt_Download ? "ok" : "NOT",
         (void *)g, g_pt_poly_vl == 1 ? "yes" : g_pt_poly_vl == 0 ? "NO" : "?", g_pt_poly_pvl == 1 ? "yes" : g_pt_poly_pvl == 0 ? "NO" : "?",
         g && GetProcAddress(g, "_grDrawPolygon@12") ? "yes" : "NO");
}

/* ---- the dump: per main terrain pass (from tm_emit_wrap), per frame (from the flush end) ---- */
static void pd_terrain_pass(void) {
    float *V, *U; int n; DWORD hv, hu;
    if (!g_pd_f) return;
    V = *(float * volatile *)(DWORD_PTR)g_ta_V; U = *(float * volatile *)(DWORD_PTR)g_ta_U; n = *(volatile int *)(DWORD_PTR)g_ta_vn;
    if (!V || !U || n <= 0 || n > 32768) return;
    hv = pd_fnv(2166136261u, V, (DWORD)n * 12u); hu = pd_fnv(2166136261u, U, (DWORD)n * 12u);
    fprintf(g_pd_f, "T,%lu,%d,%08lx,%08lx\n", (unsigned long)g_frame, n, (unsigned long)hv, (unsigned long)hu);
    if (g_pd_bin && g_frame >= g_pd_first && g_frame < g_pd_first + g_pd_count) {
        DWORD h[2]; h[0] = g_frame; h[1] = (DWORD)n; fwrite(h, 4, 2, g_pd_bin); fwrite(V, 12, n, g_pd_bin); fwrite(U, 12, n, g_pd_bin);
    }
}
static void pd_frame_end(void) {                     /* the hardware flush's end (fe_flush_wrap) */
    if (!g_pd_f) return;
    fprintf(g_pd_f, "D,%lu,%lu,%08lx\nC,%lu,%lu,%08lx\n", (unsigned long)g_frame, (unsigned long)g_pd_tris, (unsigned long)g_pd_hd,
            (unsigned long)g_frame, (unsigned long)g_pd_recs, (unsigned long)g_pd_hc);
    g_pd_tris = g_pd_recs = 0; g_pd_hd = g_pd_hc = 2166136261u;
    if ((g_frame & 63) == 0) { fflush(g_pd_f); if (g_pd_bin) fflush(g_pd_bin); }
}
static __inline void pd_clutter_rec(const BYTE *rec, int n, DWORD tex) {
    DWORD t[3]; t[0] = rec ? *(const DWORD *)(rec + 0xc) : 0xffffffff; t[1] = (DWORD)n; t[2] = tex;
    g_pd_hc = pd_fnv(g_pd_hc, t, 12); g_pd_recs++;
}

/* ---- the report ---- */
static void pt_bk_log(const char *what, pt_bk_t *b, DWORD frames, int mod) {
    char line[900]; int o, i, k, order[PT_BK], m = 0;
    for (i = 0; i < PT_BK && b[i].ra; i++) order[m++] = i;
    for (i = 0; i < m; i++) for (k = i + 1; k < m; k++) if (b[order[k]].n > b[order[i]].n) { int t = order[i]; order[i] = order[k]; order[k] = t; }
    o = _snprintf(line, sizeof line, "  pass-timers: %s per frame:", what);
    for (i = 0; i < m && i < 10 && o < (int)sizeof line - 80; i++) {
        pt_bk_t *e = &b[order[i]];
        if (mod) {
            HMODULE h = NULL; char nm[64] = "?"; DWORD ra = e->ra;
            if (ra && GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)(DWORD_PTR)ra, &h) && h) {
                char p[MAX_PATH]; const char *s; GetModuleFileNameA(h, p, sizeof p); s = strrchr(p, '\\'); lstrcpynA(nm, s ? s + 1 : p, sizeof nm); }
            o += _snprintf(line + o, sizeof line - o, " %s+%lx %.2f", nm, (unsigned long)(ra - (DWORD)(DWORD_PTR)h), (double)e->n / frames);
        } else o += _snprintf(line + o, sizeof line - o, " %08lx %.1f (%.1f us)", (unsigned long)e->ra, (double)e->n / frames, e->t * g_pt_ns_per_tick / 1000.0 / frames);
    }
    if (m == 0) o += _snprintf(line + o, sizeof line - o, " none");
    line[sizeof line - 1] = 0; mlog("%s", line);
    memset(b, 0, sizeof(pt_bk_t) * PT_BK);
}
static void pt_report(void) {
    unsigned __int64 t1 = pt_now(); LARGE_INTEGER q1; double F = g_pt_frames ? (double)g_pt_frames : 1.0, ns; int p;
    QueryPerformanceCounter(&q1);
    if (q1.QuadPart > g_pt_q0.QuadPart && t1 > g_pt_tsc0) g_pt_ns_per_tick = (double)(q1.QuadPart - g_pt_q0.QuadPart) * 1e9 / (double)g_qpf.QuadPart / (double)(t1 - g_pt_tsc0);
    ns = g_pt_ns_per_tick;
    mlog("  pass-timers: %lu frames (to %lu), tsc %.4f ns/tick, rdtsc pair %llu ticks subtracted", (unsigned long)g_pt_frames, (unsigned long)g_frame, ns, (unsigned long long)g_pt_rd_ovh);
    mlog("  pass-timers: fe_DrawTri inside the flush %.0f calls/frame, own %.1f ns/call = %.1f us/frame, glide2x sync %.1f ns/call = %.1f us/frame; outside %.0f calls/frame, own %.1f us, sync %.1f us/frame",
         g_pt_dt_n[0] / F, g_pt_dt_n[0] ? g_pt_dt_own[0] * ns / g_pt_dt_n[0] : 0.0, g_pt_dt_own[0] * ns / 1000.0 / F, g_pt_dt_n[0] ? g_pt_dt_sync[0] * ns / g_pt_dt_n[0] : 0.0, g_pt_dt_sync[0] * ns / 1000.0 / F,
         g_pt_dt_n[1] / F, g_pt_dt_own[1] * ns / 1000.0 / F, g_pt_dt_sync[1] * ns / 1000.0 / F);
    mlog("  pass-timers: clutter hooks: draw wrap %.1f us/frame (%.0f calls), build %.1f us/frame, template tables %.1f us/frame; morph (its own timer line) separate",
         g_pt_cl_draw * ns / 1000.0 / F, g_pt_cl_draw_n / F, g_pt_cl_build * ns / 1000.0 / F, g_pt_cl_tab * ns / 1000.0 / F);
    for (p = 0; p < PT_PH; p++)
        if (g_pt_gft_n[p] || g_pt_m16_load[p] || g_pt_m16_cached[p] || g_pt_rel_n[p])
            mlog("  pass-timers: face textures [%s]: GetFaceTexture %.1f/frame %.1f us; m16 variant %.2f loads + %.1f cached/frame %.1f us; release %.2f/frame (%.2f live) %.1f us",
                 g_pt_phname[p], g_pt_gft_n[p] / F, g_pt_gft_t[p] * ns / 1000.0 / F, g_pt_m16_load[p] / F, g_pt_m16_cached[p] / F, g_pt_m16_t[p] * ns / 1000.0 / F,
                 g_pt_rel_n[p] / F, g_pt_rel_live[p] / F, g_pt_rel_t[p] * ns / 1000.0 / F);
    mlog("  pass-timers: exe _stricmp %.1f/frame %.1f us; file A-API %.2f/frame; msvcrt MultiByteToWideChar %.1f/frame %.1f us; registry calls %.2f/frame (OKExA %.2f OKExW %.2f OKA %.2f QVA %.2f QVW %.2f close %.2f NtOpenKey %.2f NtOpenKeyEx %.2f)",
         g_pt_sc_n / F, g_pt_sc_t * ns / 1000.0 / F, g_pt_fa_n / F, g_pt_mb_n / F, g_pt_mb_t * ns / 1000.0 / F, g_pt_rg_n / F,
         g_pt_rg_cnt[0] / F, g_pt_rg_cnt[1] / F, g_pt_rg_cnt[2] / F, g_pt_rg_cnt[4] / F, g_pt_rg_cnt[5] / F, g_pt_rg_cnt[6] / F, g_pt_rg_cnt[7] / F, g_pt_rg_cnt[8] / F);
    pt_bk_log("GetFaceTexture by call site", g_pt_gf, g_pt_frames ? g_pt_frames : 1, 0);
    pt_bk_log("ReleaseM16Texture by call site (bit 31: slot already empty)", g_pt_rl, g_pt_frames ? g_pt_frames : 1, 0);
    pt_bk_log("exe _stricmp by return address", g_pt_sc, g_pt_frames ? g_pt_frames : 1, 0);
    if (g_pt_fa_n) pt_bk_log("file A-API by return address (bit 31 GetFileAttributesA, bit 30 FindFirstFileA)", g_pt_fa, g_pt_frames ? g_pt_frames : 1, 0);
    pt_bk_log("registry calls by caller module", g_pt_rg, g_pt_frames ? g_pt_frames : 1, 1);
    mlog("  pass-timers: glide state calls per frame: texsource %.0f (%.0f new address), blend %.0f, acombine %.0f, ccombine %.0f, chroma %.0f, download %.2f; polygon entry points %s",
         g_pt_gs_texsrc / F, g_pt_gs_texchg / F, g_pt_gs_blend / F, g_pt_gs_acomb / F, g_pt_gs_ccomb / F, g_pt_gs_chroma / F, g_pt_gs_dl / F,
         g_pt_poly_vl == 1 ? "present" : g_pt_poly_vl == 0 ? "ABSENT" : "unknown");
    memset(g_pt_dt_own, 0, sizeof g_pt_dt_own); memset(g_pt_dt_sync, 0, sizeof g_pt_dt_sync); memset(g_pt_dt_n, 0, sizeof g_pt_dt_n);
    g_pt_cl_draw = g_pt_cl_build = g_pt_cl_tab = 0; g_pt_cl_draw_n = 0;
    memset(g_pt_gft_t, 0, sizeof g_pt_gft_t); memset(g_pt_m16_t, 0, sizeof g_pt_m16_t); memset(g_pt_rel_t, 0, sizeof g_pt_rel_t);
    memset(g_pt_gft_n, 0, sizeof g_pt_gft_n); memset(g_pt_m16_load, 0, sizeof g_pt_m16_load); memset(g_pt_m16_cached, 0, sizeof g_pt_m16_cached);
    memset(g_pt_rel_n, 0, sizeof g_pt_rel_n); memset(g_pt_rel_live, 0, sizeof g_pt_rel_live);
    g_pt_sc_n = g_pt_fa_n = g_pt_rg_n = g_pt_mb_n = 0; g_pt_sc_t = g_pt_mb_t = 0; memset(g_pt_rg_cnt, 0, sizeof g_pt_rg_cnt);
    g_pt_gs_texsrc = g_pt_gs_texchg = g_pt_gs_blend = g_pt_gs_acomb = g_pt_gs_ccomb = g_pt_gs_chroma = g_pt_gs_dl = 0;
    g_pt_frames = 0; g_pt_tsc0 = pt_now(); QueryPerformanceCounter(&g_pt_q0);
}
static void pass_timers_frame(void) {                /* from the frame hook */
    if (!g_pt_on) return;
    if (g_frame == 300 || g_frame == 1500) pt_reg_attach();
    if (++g_pt_frames >= 600) pt_report();
}

static void apply_pass_timers(void) {
    char v[300], *c; int i, k, nw = 0, nr = 0;
    if (g_exe != EXE_GOLD) return;
    if (env_str("I76_PASS_DUMP", v, sizeof v)) {
        char fn[300]; lstrcpynA(fn, v, sizeof fn); c = strchr(fn, ','); if (c) { *c = 0; g_pd_first = strtoul(c + 1, &c, 10); if (c && *c == ',') g_pd_count = strtoul(c + 1, 0, 10); }
        g_pd_f = fopen(fn, "w");
        if (g_pd_f && g_pd_count) { char bn[320]; _snprintf(bn, sizeof bn - 1, "%s.bin", fn); bn[sizeof bn - 1] = 0; g_pd_bin = fopen(bn, "wb"); }
        g_pd_on = g_pd_f != NULL;
        mlog("  pass-dump: %s -> %s (raw V / U for frames %lu..%lu%s)", g_pd_on ? "on" : "NOT opened", fn, (unsigned long)g_pd_first, (unsigned long)(g_pd_first + g_pd_count), g_pd_bin ? "" : ", none");
    }
    if (env_flag("I76_PASS_TIMERS", 4, 0) != 1) return;
    g_pt_on = 1;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    {   unsigned __int64 a, b, best = ~0ull; for (i = 0; i < 64; i++) { a = __rdtsc(); b = __rdtsc(); if (b - a < best) best = b - a; } g_pt_rd_ovh = best; }
    g_pt_tsc0 = pt_now(); QueryPerformanceCounter(&g_pt_q0); g_pt_ns_per_tick = 0.0;
    /* GetFaceTexture's direct calls (scanned: every E8 to 0x44a290 in .text) */
    {   static const DWORD gft[] = { 0x44552a, 0x448bb6, 0x449077, 0x449588, 0x44a7c9, 0x459e56, 0x459f25, 0x45ad1a, 0x45c7eb, 0x45cb15, 0x45d473, 0x45d9a9,
                                      0x45dc7d, 0x45de23, 0x46038c, 0x460a2e, 0x467b30, 0x48f15f, 0x48f6e0, 0x4906fc, 0x4a4503, 0x4a49d5 };
        for (k = 0; k < (int)(sizeof gft / sizeof gft[0]) && g_pt_gft_ns < PT_GFT_SITES; k++)
            if (st_call_site(gft[k], 0x0044a290, (void *)pt_gft_wrap, &g_pt_gft_next[g_pt_gft_ns], "pass-timers GetFaceTexture call")) { g_pt_gft_site[g_pt_gft_ns++] = gft[k]; nw++; } }
    if (st_call_site(0x0044a5f0, 0x00471980, (void *)pt_m16_wrap, &g_pt_m16_next, "pass-timers LoadM16Variant call")) nw++;
    {   static const DWORD rs[] = { 0x449fd2, 0x44a128, 0x44a237, 0x44a8bf };
        for (k = 0; k < 4; k++) if (st_call_site(rs[k], 0x00471b70, (void *)pt_rel_wrap, &g_pt_rel_next[g_pt_rel_ns], "pass-timers ReleaseM16Texture call")) { g_pt_rel_site[g_pt_rel_ns++] = rs[k]; nr++; } }
    if (st_call_site(0x00401fde, 0x00445750, (void *)pt_mirror_wrap, &g_pt_mir_next, "pass-timers DrawRearMirror call (phase)")) nw++;
    {   HMODULE e = GetModuleHandleA(NULL), mv = GetModuleHandleA("msvcrt.dll");
        *(void **)&p_pt_stricmp = patch_iat(e, "MSVCRT.dll", "_stricmp", (void *)pt_stricmp);
        *(void **)&p_pt_CreateFileA = patch_iat(e, "KERNEL32.dll", "CreateFileA", (void *)pt_CreateFileA);
        *(void **)&p_pt_GetFileAttributesA = patch_iat(e, "KERNEL32.dll", "GetFileAttributesA", (void *)pt_GetFileAttributesA);
        *(void **)&p_pt_FindFirstFileA = patch_iat(e, "KERNEL32.dll", "FindFirstFileA", (void *)pt_FindFirstFileA);
        if (mv) { *(void **)&p_pt_MBtoWC = patch_iat(mv, "KERNEL32.dll", "MultiByteToWideChar", (void *)pt_MBtoWC);
                  if (!p_pt_MBtoWC) *(void **)&p_pt_MBtoWC = patch_iat(mv, "api-ms-win-core-string-l1-1-0.dll", "MultiByteToWideChar", (void *)pt_MBtoWC); }
        mlog("  pass-timers: on - %d call sites wrapped (GetFaceTexture %d, LoadM16Variant, DrawRearMirror), %d release sites; exe _stricmp %s, CreateFileA %s, GetFileAttributesA %s, FindFirstFileA %s; msvcrt MultiByteToWideChar %s; rdtsc pair %llu ticks",
             nw, g_pt_gft_ns, nr, p_pt_stricmp ? "hooked" : "NOT", p_pt_CreateFileA ? "hooked" : "NOT", p_pt_GetFileAttributesA ? "hooked" : "not imported", p_pt_FindFirstFileA ? "hooked" : "not imported",
             p_pt_MBtoWC ? "hooked" : "NOT", (unsigned long long)g_pt_rd_ovh);
    }
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    if (GetModuleHandleA("zglide.dll")) pt_glide_attach(GetModuleHandleA("zglide.dll"));
}
