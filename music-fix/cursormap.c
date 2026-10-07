/* ===========================================================================
 * CURSOR MAP  (I76_CURSOR_MAP=1 | stretched | ar; off by default)
 * ===========================================================================
 * Included from strlkproxy.c (before hook_LoadLibraryA, which calls cursor_map_attach).
 *
 * THE PROBLEM. i76.exe and i76shell.dll (menus, garage, save screen) were written for a 640x480 fullscreen mode,
 * where screen == client == UI coordinates. They read the pointer with GetCursorPos / mouse-message lParams and
 * hit-test the raw numbers against 640x480 rectangles. When the 640x480 picture is presented on a bigger window
 * without a real mode change (dgVoodoo `FullscreenAttributes = fake`, windowed, or a wide `[Glide] Resolution`),
 * those numbers are screen pixels, so the game "points" at (x, y) of its 640x480 page while the OS arrow is drawn
 * at (x, y) of the screen: on the Steam Deck (1280x800) the arrow shows up and to the left of the spot the game
 * acts on, by x2 / x1.67 (owner report 2026-10-07, after the Deck moved to fake fullscreen on 2026-10-06).
 *
 * THE FIX, without touching either binary. u32x.dll (u32x/README.md) does this on Windows, but needs the import
 * name in i76.exe and i76shell.dll rewritten to load it. This proxy is already loaded by every install, so it
 * repoints the same four USER32 import slots in i76.exe at load and in i76shell.dll when the exe LoadLibraryA's it:
 *
 *    GetCursorPos  screen -> UI         SetCursorPos  UI -> screen
 *    ClipCursor    UI rect -> screen    PeekMessageA  mouse lParam client -> UI
 *
 * The mapping comes from the game window's live client rect on every call: `stretched` (=1, the default) scales x
 * and y separately, matching dgVoodoo ScalingMode = stretched (the widescreen setups); `ar` keeps 4:3 and centres
 * it, matching stretched_ar. A client rect of exactly 640x480 is the identity (a real mode change, nothing to do).
 * Unlike u32x_min it translates in-range values too: on a 1280x800 screen most raw positions are inside 0..639 /
 * 0..479 and still wrong.
 *
 * Stands down when u32x.dll is loaded (the Windows daily driver: it already maps, and mapping twice is wrong).
 * Only the game's own modules are repointed; dgVoodoo, Wine and AutoHotkey keep the real calls.
 */
static int  g_cm_mode;                 /* 0 off, 1 stretched, 2 ar */
static int  g_cm_log;                  /* I76_CURSOR_LOG=1: rect changes + the first 40 distinct translations */
static HWND g_cm_hwnd;
static BOOL (WINAPI *p_cm_GetCursorPos)(LPPOINT);
static BOOL (WINAPI *p_cm_SetCursorPos)(int, int);
static BOOL (WINAPI *p_cm_ClipCursor)(const RECT *);
static BOOL (WINAPI *p_cm_PeekMessageA)(LPMSG, HWND, UINT, UINT, UINT);
static HMODULE WINAPI hook_LoadLibraryA(LPCSTR name);

typedef struct { double kx, ky; int ox, oy, on; } CmMap;

static HWND cm_window(void) {
    if (g_cm_hwnd && IsWindow(g_cm_hwnd)) return g_cm_hwnd;
    g_cm_hwnd = FindWindowA("Interstate '76 Gold Edition", NULL);
    if (!g_cm_hwnd) g_cm_hwnd = FindWindowA(NULL, "Interstate '76 Gold Edition");
    return g_cm_hwnd;
}
/* UI unit -> screen pixel. on = 0: pass through untranslated (no window yet, or a real 640x480 client). */
static CmMap cm_map(void) {
    CmMap m = { 1.0, 1.0, 0, 0, 0 };
    HWND h = cm_window(); RECT rc; POINT org = { 0, 0 };
    if (!h || !GetClientRect(h, &rc) || rc.right <= 0 || rc.bottom <= 0) return m;
    if (rc.right == 640 && rc.bottom == 480) return m;
    ClientToScreen(h, &org);
    if (g_cm_log) {
        static LONG lw, lh, lx, ly;
        if (rc.right != lw || rc.bottom != lh || org.x != lx || org.y != ly) {
            RECT wr; GetWindowRect(h, &wr);
            lw = rc.right; lh = rc.bottom; lx = org.x; ly = org.y;
            mlog("  cursor-map: client %ldx%ld at (%ld,%ld), window (%ld,%ld)-(%ld,%ld), hwnd %p",
                 rc.right, rc.bottom, org.x, org.y, wr.left, wr.top, wr.right, wr.bottom, (void *)h);
        }
    }
    m.kx = rc.right / 640.0; m.ky = rc.bottom / 480.0;
    m.ox = org.x; m.oy = org.y;
    if (g_cm_mode == 2) {
        double k = m.kx < m.ky ? m.kx : m.ky;
        m.ox += (int)((rc.right - 640.0 * k) / 2.0); m.oy += (int)((rc.bottom - 480.0 * k) / 2.0);
        m.kx = m.ky = k;
    }
    m.on = 1;
    return m;
}
static LONG cm_clamp(LONG v, LONG hi) { return v < 0 ? 0 : (v > hi ? hi : v); }
static void cm_to_ui(const CmMap *m, POINT *p) {
    p->x = cm_clamp((LONG)((p->x - m->ox) / m->kx + 0.5), 639);
    p->y = cm_clamp((LONG)((p->y - m->oy) / m->ky + 0.5), 479);
}

static BOOL WINAPI cm_GetCursorPos(LPPOINT p) {
    BOOL ok = p_cm_GetCursorPos(p);
    if (ok && p) {
        POINT raw = *p; CmMap m = cm_map();
        if (m.on) cm_to_ui(&m, p);
        if (g_cm_log) {
            static int n; static LONG px = -1, py = -1;
            if (n < 40 && (raw.x != px || raw.y != py)) { n++; px = raw.x; py = raw.y;
                RECT cc; GetClipCursor(&cc);
                mlog("  cursor-map: GetCursorPos (%ld,%ld) -> (%ld,%ld)%s; clip (%ld,%ld)-(%ld,%ld)", raw.x, raw.y, p->x, p->y,
                     m.on ? "" : " (pass)", cc.left, cc.top, cc.right, cc.bottom); }
        }
    }
    return ok;
}
static BOOL WINAPI cm_SetCursorPos(int x, int y) {
    CmMap m = cm_map();
    if (m.on) return p_cm_SetCursorPos(m.ox + (int)(x * m.kx + 0.5), m.oy + (int)(y * m.ky + 0.5));
    return p_cm_SetCursorPos(x, y);
}
static BOOL WINAPI cm_ClipCursor(const RECT *r) {
    CmMap m = cm_map();
    if (g_cm_log) {
        void *ra = __builtin_return_address(0);
        if (r) mlog("  cursor-map: ClipCursor (%ld,%ld)-(%ld,%ld) from %p", r->left, r->top, r->right, r->bottom, ra);
        else   mlog("  cursor-map: ClipCursor NULL from %p", ra);
    }
    if (r && m.on) {
        RECT s;
        s.left  = m.ox + (int)(r->left  * m.kx + 0.5); s.top    = m.oy + (int)(r->top    * m.ky + 0.5);
        s.right = m.ox + (int)(r->right * m.kx + 0.5); s.bottom = m.oy + (int)(r->bottom * m.ky + 0.5);
        return p_cm_ClipCursor(&s);
    }
    return p_cm_ClipCursor(r);
}
static BOOL WINAPI cm_PeekMessageA(LPMSG msg, HWND hw, UINT lo, UINT hi, UINT rm) {
    BOOL ok = p_cm_PeekMessageA(msg, hw, lo, hi, rm);
    if (ok && msg && msg->hwnd && msg->message >= WM_MOUSEFIRST && msg->message <= WM_MOUSELAST
        && msg->message != WM_MOUSEWHEEL) {                 /* the wheel's lParam is screen coordinates already */
        CmMap m = cm_map();
        if (m.on) {
            POINT p; p.x = (short)LOWORD(msg->lParam); p.y = (short)HIWORD(msg->lParam);
            ClientToScreen(msg->hwnd, &p);
            cm_to_ui(&m, &p);
            msg->lParam = MAKELPARAM((WORD)p.x, (WORD)p.y);
        }
    }
    return ok;
}

/* Repoint one module's USER32 slots. Returns the number of slots taken (0..4). */
static int cm_patch_module(HMODULE mod, const char *what) {
    void *o; int n = 0;
    if ((o = patch_iat(mod, "USER32.dll", "GetCursorPos", cm_GetCursorPos))) { if (!p_cm_GetCursorPos) p_cm_GetCursorPos = o; n++; }
    if ((o = patch_iat(mod, "USER32.dll", "SetCursorPos", cm_SetCursorPos))) { if (!p_cm_SetCursorPos) p_cm_SetCursorPos = o; n++; }
    if ((o = patch_iat(mod, "USER32.dll", "ClipCursor",   cm_ClipCursor)))   { if (!p_cm_ClipCursor)   p_cm_ClipCursor   = o; n++; }
    if ((o = patch_iat(mod, "USER32.dll", "PeekMessageA", cm_PeekMessageA))) { if (!p_cm_PeekMessageA) p_cm_PeekMessageA = o; n++; }
    mlog("  cursor-map: %s %d/4 USER32 slots repointed", what, n);
    return n;
}
/* from hook_LoadLibraryA: b = the loaded file's base name */
static void cursor_map_attach(HMODULE m, const char *b) {
    static int shell_done;
    if (g_cm_mode && !shell_done && _strnicmp(b, "i76shell", 8) == 0) { shell_done = 1; cm_patch_module(m, b); }
}
static void apply_cursor_map(void) {
    char v[16]; DWORD n = GetEnvironmentVariableA("I76_CURSOR_MAP", v, sizeof(v));
    HMODULE exe = GetModuleHandleA(NULL), sh;
    if (n == 0 || n >= sizeof(v) || v[0] == '0') return;
    if (GetModuleHandleA("u32x.dll") || patch_iat_has_dll(exe, "u32x.dll")) {
        mlog("  cursor-map: u32x.dll present (it maps the cursor already) - not applied");
        return;
    }
    g_cm_mode = (lstrcmpiA(v, "ar") == 0) ? 2 : 1;
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_CURSOR_LOG", c, sizeof(c)); g_cm_log = (k && k < sizeof(c) && c[0] == '1'); }
    {   /* the real functions, so a hook never calls itself even if a slot was already taken by someone else */
        HMODULE u = GetModuleHandleA("user32.dll");
        p_cm_GetCursorPos = (BOOL (WINAPI *)(LPPOINT))GetProcAddress(u, "GetCursorPos");
        p_cm_SetCursorPos = (BOOL (WINAPI *)(int, int))GetProcAddress(u, "SetCursorPos");
        p_cm_ClipCursor   = (BOOL (WINAPI *)(const RECT *))GetProcAddress(u, "ClipCursor");
        p_cm_PeekMessageA = (BOOL (WINAPI *)(LPMSG, HWND, UINT, UINT, UINT))GetProcAddress(u, "PeekMessageA");
    }
    mlog("  cursor-map: on (%s: the 640x480 UI %s the game window's client rect)",
         g_cm_mode == 2 ? "ar" : "stretched", g_cm_mode == 2 ? "letterboxed 4:3 in" : "stretched over");
    cm_patch_module(exe, "i76.exe");
    if ((sh = GetModuleHandleA("i76shell.dll")) != NULL) cursor_map_attach(sh, "i76shell.dll");
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(exe, "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    mlog("  cursor-map: i76shell.dll %s; LoadLibraryA %s", sh ? "already loaded" : "patched when the game loads it",
         p_LoadLibraryA ? "hooked" : "NOT hooked");
}
