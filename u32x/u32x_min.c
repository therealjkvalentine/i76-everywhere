/*
 * u32x.c - USER32 coordinate-translation proxy for Interstate '76's 2D shell.
 *
 * THE BUG THIS FIXES (docs/SAVE-FREEZE-ROOT-CAUSE.md in i76-everywhere): i76shell.dll was
 * written for 1997 fullscreen 640x480, where screen == client == UI coordinates. It reads the
 * mouse with GetCursorPos / mouse-message lParams and hit-tests the raw values against 640x480
 * widget rectangles. Under dgVoodoo the 640x480 surface is stretched across the whole window
 * (3440x1440 here), so the numbers the shell sees are wildly out of range: buttons can only be
 * clicked when the pointer happens to sit in the top-left 640x480 of the screen, and the
 * "Overwrite an existing bookmark?" popup's poll loop can spin forever -> "not responding".
 *
 * THE FIX: i76shell.dll's import table is retargeted from USER32.dll to this DLL (the same
 * proxy technique as the repo's SMACKW32 music fix). 39 of its 43 USER32 imports forward
 * straight through (see u32x.def). Four are intercepted to translate between REAL screen
 * coordinates and the shell's 640x480 UI space, using the game window's live client rect and
 * aspect-preserving letterbox math (matches dgVoodoo ScalingMode = stretched_ar):
 *
 *    GetCursorPos  screen -> UI   (the poll the freeze spins in)
 *    SetCursorPos  UI -> screen   (shell warps the pointer, e.g. onto default buttons)
 *    ClipCursor    UI rect -> the real on-screen 4:3 content rect (keeps the pointer on the
 *                  rendered UI instead of trapping it in the physical top-left corner)
 *    PeekMessageA  rewrites mouse-message lParams client -> UI (the click hit-test path)
 *
 * The mapping is recomputed on every call from the live window, so windowed mode, Alt+Enter
 * toggles and any resolution all stay correct. If the game window cannot be found the calls
 * fall through untranslated (never break input outright).
 *
 * Build (x86 REQUIRED - the game is 32-bit):
 *   vcvars32 && cl /O2 /LD u32x.c /link /DEF:u32x.def user32.lib /OUT:u32x.dll
 * Deploy: copy u32x.dll beside i76shell.dll, then patch the shell's import string
 * "USER32.dll" -> "u32x.dll" (tools/framerate/... deploy script does both, with backups).
 */
#include <windows.h>
#include <stdio.h>

/* ---- diagnostic log (define U32X_LOG at build time to enable) -------------------------- */
#ifdef U32X_LOG
static void logf(const char *fmt, ...)
{
    FILE *f = fopen("C:\\Users\\james\\i76-uncap-lab\\captures\\save\\u32x.log", "a");
    if (f) {
        va_list ap; va_start(ap, fmt);
        vfprintf(f, fmt, ap);
        va_end(ap);
        fclose(f);
    }
}
#define LOG(...) logf(__VA_ARGS__)
#else
#define LOG(...) ((void)0)
#endif

/* ---- locate the game window (class name observed live; title identical) ---------------- */
static HWND g_hwnd = NULL;

static HWND game_window(void)
{
    if (g_hwnd && IsWindow(g_hwnd))
        return g_hwnd;
    g_hwnd = FindWindowA("Interstate '76 Gold Edition", NULL);
    if (!g_hwnd)
        g_hwnd = FindWindowA(NULL, "Interstate '76 Gold Edition");
    if (!g_hwnd)
        g_hwnd = GetActiveWindow();
    return g_hwnd;
}

/* ---- the 640x480 <-> screen mapping ---------------------------------------------------- */
typedef struct {
    double scale;      /* UI unit -> pixels                       */
    int    sx, sy;     /* screen position of UI (0,0)             */
    int    valid;
} Map;

static Map get_map(void)
{
    Map m = { 1.0, 0, 0, 0 };
    HWND h = game_window();
    RECT rc;
    POINT org = { 0, 0 };
    double sw, sh;

    if (!h || !GetClientRect(h, &rc))
        return m;
    if (rc.right <= 0 || rc.bottom <= 0)
        return m;
    ClientToScreen(h, &org);

    /* aspect-correct letterbox: the 4:3 UI is centred at the largest fit (stretched_ar) */
    sw = (double)rc.right  / 640.0;
    sh = (double)rc.bottom / 480.0;
    m.scale = (sw < sh) ? sw : sh;
    if (m.scale <= 0.0)
        return m;
    m.sx = org.x + (int)((rc.right  - 640.0 * m.scale) / 2.0);
    m.sy = org.y + (int)((rc.bottom - 480.0 * m.scale) / 2.0);
    m.valid = 1;
    return m;
}

static LONG clampl(LONG v, LONG lo, LONG hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* Self-calibration: some wrappers (dgVoodoo, some configs) already hand the shell 640x480
 * coordinates; others hand it raw screen coordinates (the case that freezes). We learn which by
 * watching GetCursorPos: the first time it returns a value OUTSIDE 0..639/0..479, this build's
 * environment is not pre-mapping, so the write path (SetCursorPos/ClipCursor) must translate too.
 * Until then we pass the write path through, which is correct for the pre-mapping case. */
static volatile LONG g_translate = 0;

/* ---- intercepts ------------------------------------------------------------------------ */

BOOL WINAPI My_GetCursorPos(LPPOINT p)
{
    BOOL ok = GetCursorPos(p);
    Map  m  = get_map();
#ifdef U32X_LOG
    {
        static int rx = -99999, ry = -99999;
        if (ok && p && (p->x != rx || p->y != ry)) {
            rx = p->x; ry = p->y;
            logf("GetCursorPos raw=(%d,%d) valid=%d scale=%.3f org=(%d,%d)\n",
                 p->x, p->y, m.valid, m.scale, m.sx, m.sy);
        }
    }
#endif
    if (ok && p && m.valid) {
        /* If the value is already inside the 640x480 UI range, the wrapper (dgVoodoo) has
         * already mapped it - pass through. Only translate when it is a raw screen coordinate
         * outside that range (the case that freezes the shell). Either way the shell always
         * receives an in-range coordinate, so its hit-test can always resolve and the
         * "Overwrite?" poll loop can never spin forever. */
        if (p->x < 0 || p->x > 639 || p->y < 0 || p->y > 479) {
            g_translate = 1;                        /* wrapper is NOT pre-mapping */
            p->x = clampl((LONG)((p->x - m.sx) / m.scale + 0.5), 0, 639);
            p->y = clampl((LONG)((p->y - m.sy) / m.scale + 0.5), 0, 479);
        }
    }
    return ok;
}

BOOL WINAPI My_SetCursorPos(int x, int y)
{
    Map m = get_map();
    if (g_translate && m.valid)
        return SetCursorPos(m.sx + (int)(x * m.scale + 0.5),
                            m.sy + (int)(y * m.scale + 0.5));
    return SetCursorPos(x, y);      /* wrapper un-maps, or unknown: pass through */
}

BOOL WINAPI My_ClipCursor(const RECT *r)
{
    Map m = get_map();
    if (r && g_translate && m.valid) {
        /* the shell clips to its UI space (0,0,640,480); clip to where that actually is */
        RECT s;
        s.left   = m.sx + (int)(r->left   * m.scale + 0.5);
        s.top    = m.sy + (int)(r->top    * m.scale + 0.5);
        s.right  = m.sx + (int)(r->right  * m.scale + 0.5);
        s.bottom = m.sy + (int)(r->bottom * m.scale + 0.5);
        return ClipCursor(&s);
    }
    return ClipCursor(r);
}

BOOL WINAPI My_PeekMessageA(LPMSG msg, HWND hWnd, UINT lo, UINT hi, UINT remove)
{
    BOOL ok = PeekMessageA(msg, hWnd, lo, hi, remove);
    if (ok && msg &&
        msg->message >= WM_MOUSEFIRST && msg->message <= WM_MOUSELAST &&
        msg->message != WM_MOUSEWHEEL) {          /* wheel lParam is already screen coords */
        Map m = get_map();
        LONG cx = (short)LOWORD(msg->lParam);     /* client coords of msg->hwnd */
        LONG cy = (short)HIWORD(msg->lParam);
        if (m.valid && (cx < 0 || cx > 639 || cy < 0 || cy > 479)) {
            g_translate = 1;
            POINT p; p.x = cx; p.y = cy;
            ClientToScreen(msg->hwnd, &p);
            p.x = clampl((LONG)((p.x - m.sx) / m.scale + 0.5), 0, 639);
            p.y = clampl((LONG)((p.y - m.sy) / m.scale + 0.5), 0, 479);
            LOG("PeekMsg 0x%04X client=(%ld,%ld) -> UI=(%ld,%ld)\n", msg->message, cx, cy, p.x, p.y);
            msg->lParam = MAKELPARAM((WORD)p.x, (WORD)p.y);
        }
    }
    return ok;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)inst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);

        /* STOP DWM GHOSTING THIS PROCESS.  (2026-09-07)
         *
         * The Save Bookmark screen dies about 5.9 seconds after it opens. Measured with a
         * per-call census: the engine polls normally the whole time (GetCursorPos 60/s,
         * GetAsyncKeyState 180/s) and then the window is deactivated by something nobody
         * clicked - WM_NCACTIVATE 0 / WM_ACTIVATE 0 / WM_ACTIVATEAPP 0 / WM_KILLFOCUS. That
         * is DWM replacing it with a Ghost, after which the engine collapses into a keyboard
         * PeekMessage that starves forever, because the ghost now owns the input.
         *
         * It bites when you PAUSE on that screen - which is exactly what naming a save after
         * a mission looks like. An automated test that types instantly never reaches 5.9s,
         * which is how this got wrongly filed as "not hit in normal play". It is.
         *
         * This is the ONLY change from the shipped u32x (commit bfbc2ba). Deliberately NOT
         * the ClipCursor remapping or keep-alive pumping from the same weekend, so cursor
         * behaviour under CaptureMouse=true stays bit-for-bit what it is today. */
        {
            HMODULE u32 = GetModuleHandleA("user32.dll");
            typedef void (WINAPI *DPWGFn)(void);
            DPWGFn dpwg = u32 ? (DPWGFn)GetProcAddress(u32, "DisableProcessWindowsGhosting")
                              : NULL;
            if (dpwg) dpwg();
        }
        LOG("=== u32x attached ===\n");
    }
    return TRUE;
}
