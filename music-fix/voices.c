/* voices.c - I76_VOICES: a voice overlay folder the Gold exe reads INSTEAD of its own voice lines, switchable per launch
 * (content-installer lane 2026-10-25, docs/records/CONTENT-INSTALLER-2026-10-25.md; owner ruling 5: German retail voices).
 *
 * Why a redirect and not loose files in ADDON\: a loose ADDON\<name>.wav already wins over I76.ZFS (VFS container 0 is
 * hard-wired to "addon", vfs_LoadZix 0x4b23e0; the lowest container index holding a name wins in 0x4b2e00; proven live for
 * ADDON\vppirna1.vcf, CONTENT-FEASIBILITY s.4.2) - but files in ADDON\ are always on, for every launcher, and they are
 * part of what a LAN partner must match. The owner wants German voices per launch. So the overlay lives in its own folder
 * and the proxy makes it look like part of ADDON\ for this launch only:
 *
 *   - the VFS builds its file table ONCE at start-up: vfs_Lookup 0x4b28c0 runs FindFirstFileA("<container>\*.*") /
 *     FindNextFileA over each local-directory container (KERNEL32 IAT 0x4bc134 / 0x4bc13c / 0x4bc138 on 9a232dcc), names
 *     _strlwr'd and strncpy'd into 16-byte records. Hooked here: for the pattern "addon\*.*" the enumeration returns the real
 *     ADDON\ entries and then every *.wav of the overlay folder whose name ADDON\ does not already hold (ADDON wins: a
 *     map pack's or a patch's own file is never shadowed). Other patterns pass straight through.
 *   - a file that resolves to container 0 is opened as "addon\<name>" with MSVCRT fopen (0x4b3030 / 0x4b3310 build the path
 *     with "%s\\%s", IAT 0x4bc23c). Hooked here: "addon\<name>" for a name that came from the overlay (and is not really in
 *     ADDON\) opens "<overlay>\<name>" instead.
 * Nothing on disk changes; without I76_VOICES nothing is hooked.
 *
 *   I76_VOICES=de        the overlay folder <game>\voices-de (what tools\patch-kit\i76e-extras.ps1 -GermanVoices builds)
 *   I76_VOICES=<path>    any folder of .wav files (absolute, or relative to the game folder)
 *   I76_VOICES=en / 0    off (the same as unset)
 * Log: "voices: ..." at start-up (folder, file count, hooks), "voices: addon\x.wav -> <overlay>\x.wav" for the first 12
 * redirected opens, then a count every 50.
 * Gold only (the German dub is a Gold / 1.0 data set; Nitro's VFS addresses differ and are not hooked). */

#include <ctype.h>

typedef HANDLE (WINAPI *vo_ffirst_t)(LPCSTR, LPWIN32_FIND_DATAA);
typedef BOOL   (WINAPI *vo_fnext_t)(HANDLE, LPWIN32_FIND_DATAA);
typedef BOOL   (WINAPI *vo_fclose_t)(HANDLE);
typedef FILE * (__cdecl *vo_fopen_t)(const char *, const char *);
static vo_ffirst_t vo_real_ffirst;
static vo_fnext_t  vo_real_fnext;
static vo_fclose_t vo_real_fclose;
static vo_fopen_t  vo_real_fopen;
static char  vo_dir[MAX_PATH];        /* the overlay folder, absolute */
static char (*vo_names)[16];          /* overlay *.wav names, lower case, sorted (8.3 names; longer ones are skipped) */
static int   vo_n, vo_cap;
static unsigned char *vo_from_overlay; /* per vo_names entry: 1 = handed to the VFS as part of addon\ (not really in ADDON\) */
static LONG  vo_redirects;

/* one enumeration we answer: a snapshot of the merged listing */
typedef struct { DWORD magic; int n, i; WIN32_FIND_DATAA *e; } vo_enum;
#define VO_MAGIC 0x564F4943u          /* 'VOIC' */
static vo_enum *vo_live[8];

static int vo_cmp(const void *a, const void *b) { return strcmp((const char *)a, (const char *)b); }
static int vo_find(const char *name) {   /* index in vo_names, -1 */
    char k[16]; int i;
    for (i = 0; i < 15 && name[i]; i++) k[i] = (char)tolower((unsigned char)name[i]);
    if (name[i]) return -1;
    k[i] = 0;
    { char (*p)[16] = bsearch(k, vo_names, vo_n, 16, vo_cmp); return p ? (int)(p - vo_names) : -1; }
}

static int vo_is_addon_all(const char *pat) {   /* "addon\*.*" as vfs_Lookup builds it (container name "addon") */
    return pat && !_stricmp(pat, "addon\\*.*");
}

static HANDLE WINAPI vo_hook_ffirst(LPCSTR pat, LPWIN32_FIND_DATAA fd) {
    vo_enum *en; HANDLE h; WIN32_FIND_DATAA w; int cap = 64, k, slot;
    if (!vo_is_addon_all(pat)) return vo_real_ffirst(pat, fd);
    for (slot = 0; slot < 8 && vo_live[slot]; slot++) ;
    if (slot == 8) return vo_real_ffirst(pat, fd);
    en = (vo_enum *)calloc(1, sizeof(*en));
    if (!en) return vo_real_ffirst(pat, fd);
    en->magic = VO_MAGIC; en->e = (WIN32_FIND_DATAA *)malloc(cap * sizeof(WIN32_FIND_DATAA));
    if (!en->e) { free(en); return vo_real_ffirst(pat, fd); }
    for (k = 0; k < vo_n; k++) vo_from_overlay[k] = 1;
    h = vo_real_ffirst(pat, &w);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            int j = vo_find(w.cFileName);
            if (j >= 0) vo_from_overlay[j] = 0;          /* really in ADDON\: ADDON's own file wins */
            if (en->n == cap) { WIN32_FIND_DATAA *ne = (WIN32_FIND_DATAA *)realloc(en->e, (cap *= 2) * sizeof(*ne)); if (!ne) break; en->e = ne; }
            en->e[en->n++] = w;
        } while (vo_real_fnext(h, &w));
        vo_real_fclose(h);
    }
    {   /* the overlay's names that ADDON\ does not hold */
        char p[MAX_PATH]; HANDLE h2; int added = 0;
        _snprintf(p, sizeof p, "%s\\*.wav", vo_dir); p[sizeof p - 1] = 0;
        h2 = vo_real_ffirst(p, &w);
        if (h2 != INVALID_HANDLE_VALUE) {
            do {
                int j = vo_find(w.cFileName);
                if (j < 0 || !vo_from_overlay[j] || (w.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
                if (en->n == cap) { WIN32_FIND_DATAA *ne = (WIN32_FIND_DATAA *)realloc(en->e, (cap *= 2) * sizeof(*ne)); if (!ne) break; en->e = ne; }
                en->e[en->n++] = w; added++;
            } while (vo_real_fnext(h2, &w));
            vo_real_fclose(h2);
        }
        { static int logged; if (logged++ < 4) mlog("voices: VFS scan of addon\\*.*: %d ADDON entries + %d overlay voice files", en->n - added, added); }
    }
    if (!en->n) { free(en->e); free(en); SetLastError(ERROR_FILE_NOT_FOUND); return INVALID_HANDLE_VALUE; }
    *fd = en->e[0]; en->i = 1;
    vo_live[slot] = en;
    return (HANDLE)en;
}
static int vo_slot(HANDLE h) {
    int s;
    for (s = 0; s < 8; s++) if (vo_live[s] && (HANDLE)vo_live[s] == h) return s;
    return -1;
}
static BOOL WINAPI vo_hook_fnext(HANDLE h, LPWIN32_FIND_DATAA fd) {
    int s = vo_slot(h); vo_enum *en;
    if (s < 0) return vo_real_fnext(h, fd);
    en = vo_live[s];
    if (en->i >= en->n) { SetLastError(ERROR_NO_MORE_FILES); return FALSE; }
    *fd = en->e[en->i++];
    return TRUE;
}
static BOOL WINAPI vo_hook_fclose(HANDLE h) {
    int s = vo_slot(h);
    if (s < 0) return vo_real_fclose(h);
    free(vo_live[s]->e); free(vo_live[s]); vo_live[s] = 0;
    return TRUE;
}
static FILE * __cdecl vo_hook_fopen(const char *path, const char *mode) {
    if (path && !_strnicmp(path, "addon\\", 6) && !strchr(path + 6, '\\') && (!mode || mode[0] == 'r')) {
        int j = vo_find(path + 6);
        if (j >= 0 && vo_from_overlay[j]) {
            char p[MAX_PATH]; FILE *f; LONG n;
            _snprintf(p, sizeof p, "%s\\%s", vo_dir, path + 6); p[sizeof p - 1] = 0;
            f = vo_real_fopen(p, mode);
            n = InterlockedIncrement(&vo_redirects);
            if (n <= 12 || n % 50 == 0) mlog("voices: %s -> %s%s (redirect %ld)", path, p, f ? "" : " FAILED - the game's own line instead", n);
            if (f) return f;
        }
    }
    return vo_real_fopen(path, mode);
}

static void apply_voices(HMODULE exe) {
    char v[MAX_PATH]; char p[MAX_PATH]; WIN32_FIND_DATAA w; HANDLE h;
    if (!env_str("I76_VOICES", v, sizeof v)) return;
    if (!_stricmp(v, "en") || !strcmp(v, "0") || !_stricmp(v, "off")) { mlog("voices: I76_VOICES=%s - the game's own voices", v); return; }
    if (!_stricmp(v, "de")) _snprintf(vo_dir, sizeof vo_dir, "%s\\voices-de", g_dir);
    else if (v[0] && (v[1] == ':' || (v[0] == '\\' && v[1] == '\\'))) lstrcpynA(vo_dir, v, sizeof vo_dir);
    else _snprintf(vo_dir, sizeof vo_dir, "%s\\%s", g_dir, v);
    vo_dir[sizeof vo_dir - 1] = 0;
    { size_t L = strlen(vo_dir); while (L && (vo_dir[L - 1] == '\\' || vo_dir[L - 1] == '/')) vo_dir[--L] = 0; }
    _snprintf(p, sizeof p, "%s\\*.wav", vo_dir); p[sizeof p - 1] = 0;
    h = FindFirstFileA(p, &w);
    if (h == INVALID_HANDLE_VALUE) { flog("voices: I76_VOICES=%s but %s holds no .wav - the game's own voices", v, vo_dir); return; }
    do {
        int i; size_t L = strlen(w.cFileName);
        if ((w.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || L > 15) continue;
        if (vo_n == vo_cap) {
            int nc = vo_cap ? vo_cap * 2 : 256; char (*nn)[16] = realloc(vo_names, nc * 16);
            if (!nn) break;
            vo_names = nn; vo_cap = nc;
        }
        for (i = 0; i <= (int)L; i++) vo_names[vo_n][i] = (char)tolower((unsigned char)w.cFileName[i]);
        vo_n++;
    } while (FindNextFileA(h, &w));
    FindClose(h);
    if (!vo_n) { flog("voices: %s holds no usable .wav (8.3 names) - the game's own voices", vo_dir); return; }
    qsort(vo_names, vo_n, 16, vo_cmp);
    vo_from_overlay = (unsigned char *)calloc(vo_n, 1);
    if (!vo_from_overlay) { vo_n = 0; return; }
    vo_real_ffirst = (vo_ffirst_t)patch_iat(exe, "KERNEL32.dll", "FindFirstFileA", (void *)vo_hook_ffirst);
    vo_real_fnext  = (vo_fnext_t)patch_iat(exe, "KERNEL32.dll", "FindNextFileA", (void *)vo_hook_fnext);
    vo_real_fclose = (vo_fclose_t)patch_iat(exe, "KERNEL32.dll", "FindClose", (void *)vo_hook_fclose);
    vo_real_fopen  = (vo_fopen_t)patch_iat(exe, "MSVCRT.dll", "fopen", (void *)vo_hook_fopen);
    if (!vo_real_ffirst || !vo_real_fnext || !vo_real_fclose || !vo_real_fopen) {
        /* put back whatever did attach: half a hook set would list files it cannot open */
        if (vo_real_ffirst) patch_iat(exe, "KERNEL32.dll", "FindFirstFileA", (void *)vo_real_ffirst);
        if (vo_real_fnext)  patch_iat(exe, "KERNEL32.dll", "FindNextFileA", (void *)vo_real_fnext);
        if (vo_real_fclose) patch_iat(exe, "KERNEL32.dll", "FindClose", (void *)vo_real_fclose);
        if (vo_real_fopen)  patch_iat(exe, "MSVCRT.dll", "fopen", (void *)vo_real_fopen);
        flog("voices: NOT applied - this exe's KERNEL32 FindFirstFileA / FindNextFileA / FindClose / MSVCRT fopen imports were not all found");
        vo_n = 0; return;
    }
    flog("voices: I76_VOICES=%s - %d voice files in %s shadow the game's own lines of the same name (ADDON\\ files still win); VFS scan + fopen hooked", v, vo_n, vo_dir);
}
