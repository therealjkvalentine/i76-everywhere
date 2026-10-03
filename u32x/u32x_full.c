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
 * THE EXE'S OWN MENU (2026-10-02, docs/MOUSE-ESC-MENU-AND-SAVE-SCREEN.md): the in-mission Esc
 * menu is not the shell's. i76.exe hit-tests WM_LBUTTONDOWN/UP lParams itself (WndProc
 * 0x404b5d / 0x404b30 -> shell_MenuHandleMouse 0x4972d0, only while [0x4fe534] == 0x10) in the
 * coordinates of the 3D frame it draws the page into, after a per-video-mode rescale. The
 * "exe menu" block below detects that state from the engine's own globals (fixed image base,
 * byte-signature guarded), maps the message coordinates from the box dgVoodoo lets the pointer
 * reach (measured: 4:3 x client height at the client origin) onto the 640x480 page, and undoes
 * the engine's rescale. I76_U32X_MENU=0 turns it all off; I76_U32X_MENU_BOX=0 keeps the
 * pointer-under-the-drawn-item mapping instead (which cannot reach the right edge here).
 *
 * ONE POINTER (2026-10-02, opt-in: I76_U32X_VPTR=1; i76-everywhere docs/MENU-REBUILD-DESIGN.md
 * section 7, milestone A1; docs/MOUSE-ESC-MENU-AND-SAVE-SCREEN.md section 9): the "vptr" block
 * maps the box the pointer can reach linearly onto 640x480 for the SHELL's calls, and shows a
 * click-through topmost layered arrow where the mapped point lands in the drawn picture (shell
 * screens and the exe's Esc menu; hidden in the mission), hiding the OS arrow only while it is
 * up. It pumps nothing and patches nothing; with the switch unset none of it runs.
 *
 * Build (x86 REQUIRED - the game is 32-bit):
 *   vcvars32 && cl /O2 /LD u32x.c /link /DEF:u32x.def user32.lib /OUT:u32x.dll
 * Deploy: copy u32x.dll beside i76shell.dll, then patch the shell's import string
 * "USER32.dll" -> "u32x.dll" (tools/framerate/... deploy script does both, with backups).
 */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <intrin.h>
#pragma intrinsic(_ReturnAddress)
#pragma comment(lib, "gdi32.lib")       /* the vptr cursor window's DIB (build scripts link user32 only) */

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
/* rate-limited: the cursor calls fire every frame, so cap each site's output */
#define LOG_V(...) do { static int n_; if (n_++ < 200) logf(__VA_ARGS__); } while (0)
#else
#define LOG(...)   ((void)0)
#define LOG_V(...) ((void)0)
#endif

/* ---- call census (U32X_LOG builds only) -------------------------------------------------
 * IsHungAppWindow turned out to be a liar on the Save Bookmark screen: it goes true the
 * moment the screen is touched WHILE THE SCREEN IS STILL WORKING, and hours went into
 * chasing that flag instead of the fault. So stop reading a proxy and count the real thing.
 * Every interesting call site bumps a counter and a background thread prints the deltas
 * twice a second; the counter that STOPS ADVANCING names the loop that stopped. */
#ifdef U32X_LOG
static volatile LONG c_gcp, c_peek, c_gaks, c_gks, c_disp, c_tran, c_mvk, c_focus,
                     c_dib, c_text, c_wproc, c_key, c_mouse, c_char;
#define BUMP(x) InterlockedIncrement((LONG volatile *)&(x))
/* TextOut fires per frame with the same strings; cap generously and dedupe below */
#define LOG_T(...) do { static int n_; if (n_++ < 3000) logf(__VA_ARGS__); } while (0)
#else
#define BUMP(x)    ((void)0)
#define LOG_T(...) ((void)0)
#endif

#ifdef U32X_LOG
#include <intrin.h>
/* Which module+offset is calling us? The engine and the shell are separate binaries and
 * only one of them owns the name-entry loop; the caller address says which, and gives an
 * offset to disassemble instead of guessing at behaviour from the outside. */
static void log_caller(const char *tag, void *ra)
{
    MEMORY_BASIC_INFORMATION mbi;
    char path[MAX_PATH];
    const char *base = "?";
    if (VirtualQuery(ra, &mbi, sizeof mbi) && mbi.AllocationBase &&
        GetModuleFileNameA((HMODULE)mbi.AllocationBase, path, sizeof path)) {
        const char *p2 = path, *q;
        for (q = path; *q; q++) if (*q == '\\') p2 = q + 1;
        base = p2;
        LOG("[%lu] CALLER %s = %s +0x%lX  (ra=%p)\n", (unsigned long)GetTickCount(), tag,
            base, (unsigned long)((BYTE *)ra - (BYTE *)mbi.AllocationBase), ra);
    } else {
        LOG("[%lu] CALLER %s = unmapped ra=%p\n", (unsigned long)GetTickCount(), tag, ra);
    }
}
#endif

/* ---- bisect switches (2026-10-02, the TRIP garage DONE regression) ----------------------
 * Every behaviour this file adds on top of u32x_min.c can be turned off from the launching
 * shell's environment, one launch each, no rebuild. "0" disables (or "1" enables, for the one
 * that defaults off); anything else / unset = the default. Read once, logged in the log build.
 *   I76_U32X_QUITGUARD=0     pump_keepalive may swallow WM_QUIT again (the regression; control)
 *   I76_U32X_PUMP_PRIVATE=1  pump_keepalive dispatches WM_USER.. / 0xC0xx messages again (old)
 *   I76_U32X_PUMPS=0         no keep-alive pumping at all (every site)
 *   I76_U32X_MODAL_PUMP=1    pump from the shell's input polls inside its modal loops again (the
 *                            054fb411 behaviour; P1-19, the garage DONE popup dead end; control)
 *   I76_U32X_KEYS=0          GetAsyncKeyState / GetKeyState are plain pass-throughs (no pump)
 *   I76_U32X_IAT=0           no IAT patches (BitBlt / StretchBlt / SetDIBitsToDevice / grBufferSwap)
 *   I76_U32X_DIALOG=0        dialog_owns_input() is always false
 *   I76_U32X_CLIPMAP=0       ClipCursor passes through unmapped (the Aug-16 v4 behaviour)
 *   I76_U32X_MENU=0          the exe Esc-menu block off (exists since e99b4e1)
 *   I76_U32X_MENU_BOX=0      the reachable-box mapping off (exists since 53a8cae)
 * A1 "one pointer" (the vptr block, all of it OFF unless the first is 1):
 *   I76_U32X_VPTR=1              master switch (default 0 = none of the block runs)
 *   I76_U32X_VPTR_MAP=0          no shell box mapping (the regime rule as without VPTR)
 *   I76_U32X_VPTR_CURSOR=0       no cursor window anywhere (and so no ShowCursor call)
 *   I76_U32X_VPTR_CURSOR_SHELL=0 cursor window in the exe's Esc menu only
 *   I76_U32X_VPTR_HIDEOS=0       never touch ShowCursor (the OS arrow stays as the game left it)
 *   I76_U32X_VPTR_WIDEN=0        leave a UI-sized corner clip where it is (default: move it onto
 *                                the picture rect, so the hand is on the drawn item)
 *   I76_U32X_VPTR_CURSOR_ALWAYS=1 show the cursor window even where the OS arrow already is
 *   I76_U32X_VPTR_WINDOW=1       experiment: put the window's client on the 4:3 picture rect */
static int env_switch(const char *name, int *cache, int def)
{
    if (*cache < 0) {
        char v[8];
        DWORD n = GetEnvironmentVariableA(name, v, sizeof v);
        *cache = (n == 1 && v[0] == '0') ? 0 : (n == 1 && v[0] == '1') ? 1 : def;
        LOG("%s -> %d\n", name, *cache);
    }
    return *cache;
}
static int sw_quitguard(void)    { static int c = -1; return env_switch("I76_U32X_QUITGUARD",    &c, 1); }
static int sw_pump_private(void) { static int c = -1; return env_switch("I76_U32X_PUMP_PRIVATE", &c, 0); }
static int sw_pumps(void)        { static int c = -1; return env_switch("I76_U32X_PUMPS",        &c, 1); }
static int sw_modalpump(void)    { static int c = -1; return env_switch("I76_U32X_MODAL_PUMP",   &c, 0); }
static int sw_keys(void)         { static int c = -1; return env_switch("I76_U32X_KEYS",         &c, 1); }
static int sw_iat(void)          { static int c = -1; return env_switch("I76_U32X_IAT",          &c, 1); }
static int sw_dialog(void)       { static int c = -1; return env_switch("I76_U32X_DIALOG",       &c, 1); }
static int sw_clipmap(void)      { static int c = -1; return env_switch("I76_U32X_CLIPMAP",      &c, 1); }
static int sw_vptr(void)         { static int c = -1; return env_switch("I76_U32X_VPTR",         &c, 0); }
static int sw_vptr_map(void)     { static int c = -1; return env_switch("I76_U32X_VPTR_MAP",     &c, 1); }
static int sw_vptr_cursor(void)  { static int c = -1; return env_switch("I76_U32X_VPTR_CURSOR",  &c, 1); }
static int sw_vptr_shellcur(void){ static int c = -1; return env_switch("I76_U32X_VPTR_CURSOR_SHELL", &c, 1); }
static int sw_vptr_hideos(void)  { static int c = -1; return env_switch("I76_U32X_VPTR_HIDEOS",  &c, 1); }
static int sw_vptr_widen(void)   { static int c = -1; return env_switch("I76_U32X_VPTR_WIDEN",   &c, 1); }
static int sw_vptr_always(void)  { static int c = -1; return env_switch("I76_U32X_VPTR_CURSOR_ALWAYS", &c, 0); }
static int sw_vptr_window(void)  { static int c = -1; return env_switch("I76_U32X_VPTR_WINDOW",  &c, 0); }

/* ---- locate the game window ------------------------------------------------------------
 * v2 (2026-08-16): do NOT trust FindWindowA. Measured live on the portable install, all four
 * FindWindow variants returned NULL for a window whose class AND title are byte-exact
 * "Interstate '76 Gold Edition" (EnumWindows finds it fine). A proxy that cannot find the
 * window silently disables itself, which is exactly how the first build shipped "fixed" but
 * left the shell reading raw screen coordinates. Enumerate our OWN process's top-level
 * visible windows instead - no string matching, cannot fail this way. */
static HWND g_hwnd = NULL;
static HWND g_vp_hwnd;                  /* the vptr cursor window (below) - never "the game window" */
static HWND game_window(void);

static BOOL CALLBACK find_own_window(HWND h, LPARAM lp)
{
    DWORD pid = 0;
    RECT  rc;

    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h) || h == g_vp_hwnd)
        return TRUE;                        /* keep looking */
    if (!GetClientRect(h, &rc) || rc.right < 64 || rc.bottom < 64)
        return TRUE;                        /* skip the hidden ActiveMovie / FFB helper windows */

    /* LARGEST, not first (2026-08-08). A modal Win32 dialog - "overwrite this
     * bookmark?" - is ALSO a visible top-level window of this process, and
     * EnumWindows hands windows out in z-order, so the dialog arrived first and
     * became "the game window". get_map() then derived scale and origin from the
     * DIALOG's client rect, corrupting every translation while it was up. The game
     * is fullscreen and a dialog never is, so take the biggest and the ambiguity
     * disappears. */
    {
        HWND *best = (HWND *)lp;
        RECT cur;
        if (*best && GetClientRect(*best, &cur) &&
            (long)cur.right * cur.bottom >= (long)rc.right * rc.bottom)
            return TRUE;                    /* we already have a bigger one */
        *best = h;
    }
    return TRUE;                            /* keep looking - we want the biggest */
}

/* Does one of OUR OTHER top-level windows own the input right now?
 *
 * That means a modal dialog is up. Its buttons are hit-tested in REAL SCREEN
 * coordinates, so translating into the game's 640x480 space - or clamping into it -
 * makes the dialog unclickable, which is exactly the "are you sure you want to
 * overwrite" failure. While a dialog has focus we must do nothing at all. */
static int dialog_owns_input(void)
{
    HWND  fg  = GetForegroundWindow();
    HWND  gw;
    DWORD pid = 0;

    if (!fg || !sw_dialog())
        return 0;
    gw = game_window();
    if (!gw || fg == gw || IsChild(gw, fg) || fg == g_vp_hwnd)
        return 0;
    GetWindowThreadProcessId(fg, &pid);
    return pid == GetCurrentProcessId();
}

static HWND game_window(void)
{
    HWND found = NULL;

    if (g_hwnd && IsWindow(g_hwnd) && IsWindowVisible(g_hwnd))
        return g_hwnd;
    EnumWindows(find_own_window, (LPARAM)&found);
    if (!found)
        found = FindWindowA("Interstate '76 Gold Edition", NULL);   /* legacy fallbacks */
    if (!found)
        found = GetActiveWindow();
    g_hwnd = found;
    return found;
}

/* the app's own coordinate space - dgVoodoo maps the physical pointer into it for us */
#define UI_W 640
#define UI_H 480

static LONG clampl(LONG v, LONG lo, LONG hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* ---- the engine's own state: is i76.exe's in-mission menu up? (2026-10-02) -------------
 * i76.exe is a fixed-base image (0x400000, no relocations - autotest/lib/memlib.ps1 reads the
 * same VAs from outside the process). Its Esc menu hit-tests mouse-button messages itself:
 *   WndProc 0x404b5d (0x201) / 0x404b30 (0x202): only while [0x4fe534] == 0x10, it passes the
 *   RAW lParam to shell_MenuHandleMouse 0x4972d0, which first rescales the point by the video
 *   mode row (0x4f9e08 + 28*[0x5dd360]: x *= row[5]/row[3], y *= row[6]/row[4]; identity for
 *   mode 5 = 640x480, 480/640 for mode 6, 320/640 for mode 8; [0x5dd360]==0 means row 5) and
 *   then tests it against the page rect 0x654a3c..0x654a48, which 0x4956e0 centred inside the
 *   display RECT at 0x5dcedc (left,top,right,bottom - 640x480 in -glide).
 * The page is blitted into the 3D frame, so it is presented with the FRAME's geometry. The 2D
 * shell's 640x480 surface is a 4:3 box; the frame is 4:3 too unless dgVoodoo fills its forced
 * [Glide] Resolution with it (lab conf: 3360x2100 = 16:10). Default 4:3, overridable for the
 * live test with I76_U32X_MENU_ASPECT=16:10 (or WxH). I76_U32X_MENU=0 disables the block.
 * Everything here is guarded by a byte signature of 0x4972d0: an unknown exe build gets the
 * plain shell behaviour and nothing is read from it. */
#define EXE_BASE        0x400000
#define EXE_MODE        0x4fe534      /* render_gate_flags: 0x10 = in-game menu            */
#define EXE_VIDMODE     0x5dd360      /* video mode index 1..8 (0 is treated as row 5)      */
#define EXE_MODETAB     0x4f9e08      /* 9 rows x 7 dwords; [3],[4] display  [5],[6] render */
#define EXE_DISPRECT    0x5dcedc      /* RECT of the display frame                          */
#define EXE_MENUMOUSE   0x4972d0      /* shell_MenuHandleMouse: signature anchor            */

static int exe_known(void)
{
    static int known = -1;
    if (known < 0) {
        /* 0x4972d0: sub esp,28h ; mov eax,[esp+34h] ; push ebx ; push ebp */
        static const BYTE sig[] = { 0x83,0xEC,0x28, 0x8B,0x44,0x24,0x34, 0x53, 0x55 };
        const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)EXE_BASE;
        known = 0;
        if (GetModuleHandleA(NULL) == (HMODULE)EXE_BASE && dos->e_magic == IMAGE_DOS_SIGNATURE) {
            const IMAGE_NT_HEADERS *nt = (const IMAGE_NT_HEADERS *)((const BYTE *)dos + dos->e_lfanew);
            if (nt->Signature == IMAGE_NT_SIGNATURE &&
                nt->OptionalHeader.SizeOfImage > (EXE_MENUMOUSE - EXE_BASE) + sizeof sig &&
                memcmp((const void *)EXE_MENUMOUSE, sig, sizeof sig) == 0)
                known = 1;
        }
        LOG("exe signature %s\n", known ? "matched - exe menu handling on"
                                        : "NOT matched - exe menu handling off");
    }
    return known;
}

static int menu_enabled(void)
{
    static int en = -1;
    if (en < 0) {
        char v[8];
        DWORD n = GetEnvironmentVariableA("I76_U32X_MENU", v, sizeof v);
        en = (n == 1 && v[0] == '0') ? 0 : 1;
        LOG("I76_U32X_MENU -> %d\n", en);
    }
    return en;
}

static int exe_in_menu(void)
{
    return menu_enabled() && exe_known() && *(volatile DWORD *)EXE_MODE == 0x10;
}

/* Which module is calling us? The shell and the engine share this proxy; only the engine's
 * calls while its menu is up get the frame mapping. */
static int caller_is_exe(const void *ra)
{
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)EXE_BASE;
    const IMAGE_NT_HEADERS *nt;
    if (!exe_known())
        return 0;
    nt = (const IMAGE_NT_HEADERS *)((const BYTE *)dos + dos->e_lfanew);
    return (ULONG_PTR)ra >= EXE_BASE &&
           (ULONG_PTR)ra <  EXE_BASE + nt->OptionalHeader.SizeOfImage;
}

/* the engine's logical frame - what 0x4956e0 centres the page in; 640x480 unless it says otherwise */
static void exe_frame(int *w, int *h)
{
    const LONG *rc = (const LONG *)EXE_DISPRECT;
    int fw = rc[2] - rc[0], fh = rc[3] - rc[1];
    if (fw < 320 || fw > 4096 || fh < 200 || fh > 4096) { fw = UI_W; fh = UI_H; }
    *w = fw; *h = fh;
}

/* The inverse of 0x4972d0's per-mode rescale. Returns 1 and the ratios to PRE-multiply a frame
 * point by (x_msg = x_frame * display/render) when the live row is sane and not the identity. */
static int exe_mode_ratio(double *rx, double *ry, int *vm_out)
{
    DWORD vm = *(volatile DWORD *)EXE_VIDMODE;
    const LONG *row;
    if (vm == 0) vm = 5;                            /* 0x497307: mode 0 reads row 5 */
    if (vm > 8) return 0;
    row = (const LONG *)(EXE_MODETAB + 28 * vm);
    *vm_out = (int)vm;
    if (row[3] <= 0 || row[4] <= 0 || row[5] <= 0 || row[6] <= 0 ||
        row[3] > 4096 || row[4] > 4096 || row[5] > 4096 || row[6] > 4096)
        return 0;
    if (row[3] == row[5] && row[4] == row[6])
        return 0;
    *rx = (double)row[3] / (double)row[5];
    *ry = (double)row[4] / (double)row[6];
    return 1;
}

/* Aspect of the presented 3D frame. Default 4:3: dgVoodoo ScalingMode=stretched_ar keeps the
 * app's aspect, and the Aug-15 capture of this menu (captures/save/pause.png) shows the cockpit
 * in the same 4:3 box as the shell. The override exists so the live test can try 16:10 (the
 * forced [Glide] Resolution's aspect) without a rebuild if the right edge still falls short. */
static void menu_aspect(double *aw, double *ah)
{
    static double w = 0.0, h = 0.0;
    if (w <= 0.0) {
        char v[32];
        int a = 0, b = 0;
        DWORD n = GetEnvironmentVariableA("I76_U32X_MENU_ASPECT", v, sizeof v);
        if (n > 0 && n < sizeof v &&
            (sscanf(v, "%d:%d", &a, &b) == 2 || sscanf(v, "%dx%d", &a, &b) == 2) &&
            a > 0 && b > 0) {
            w = a; h = b;
        } else {
            w = 4.0; h = 3.0;
        }
        LOG("exe menu frame aspect %g:%g\n", w, h);
    }
    *aw = w; *ah = h;
}

/* ---- the logical <-> screen mapping ----------------------------------------------------
 * A logical lw x lh frame of aspect aw:ah, centred at the largest fit inside the live client
 * rect (stretched_ar). For the 2D shell that is the 640x480 UI at 4:3, scale_x == scale. For
 * the exe menu it is the engine's display frame at the presented frame aspect, where the two
 * scales may differ - or, when dgVoodoo's reachable box is known, that box (see menu_box). */
typedef struct {
    double scale;      /* y: logical unit -> pixels                        */
    double scale_x;    /* x: logical unit -> pixels (== scale at 4:3)      */
    int    sx, sy;     /* screen position of logical (0,0)                 */
    int    lw, lh;     /* logical frame being mapped                       */
    int    cw, ch;     /* live client size (diagnostics)                   */
    int    valid;
    const char *tag;   /* "UI" / "frame" / "box" (logs)                    */
} Map;

static Map map_for(double aw, double ah, int lw, int lh)
{
    Map m = { 1.0, 1.0, 0, 0, UI_W, UI_H, 0, 0, 0, "UI" };
    HWND h = game_window();
    RECT rc;
    POINT org = { 0, 0 };
    double sw, sh, s, fw, fh;

    m.lw = lw; m.lh = lh;
    if (!h || !GetClientRect(h, &rc))
        return m;
    if (rc.right <= 0 || rc.bottom <= 0 || aw <= 0.0 || ah <= 0.0 || lw <= 0 || lh <= 0)
        return m;
    m.cw = rc.right; m.ch = rc.bottom;
    ClientToScreen(h, &org);

    /* aspect-correct letterbox: the frame is centred at the largest fit (stretched_ar) */
    sw = (double)rc.right  / aw;
    sh = (double)rc.bottom / ah;
    s  = (sw < sh) ? sw : sh;
    if (s <= 0.0)
        return m;
    fw = aw * s; fh = ah * s;                       /* presented frame in pixels */
    m.scale   = fh / (double)lh;
    m.scale_x = fw / (double)lw;
    m.sx = org.x + (int)((rc.right  - fw) / 2.0);
    m.sy = org.y + (int)((rc.bottom - fh) / 2.0);
    m.valid = 1;
    return m;
}

/* the 2D shell: a 640x480 surface, always 4:3 */
static Map get_map(void) { return map_for(4.0, 3.0, UI_W, UI_H); }

/* ---- the reachable box (Test A, 2026-10-02) --------------------------------------------
 * Measured on the sandbox with the Aug-16 DLL and with this source's log build alike: in the
 * mission GetClipCursor reads 0,0-1920,1440 on a 3440x1440 client (the engine's own clip is
 * 0..639x479 and arrives here, but dgVoodoo imposes its own); in the Esc menu the OS clip is
 * released (0,0-3440,1440) yet SetCursorPos(3400,700) reads back (1919,700) every time - the
 * WM_MOUSEMOVE arrives at client x 3400 and the pointer is put straight back. No SetCursorPos
 * from the exe appears in the log, the cursor roams freely with no game running, and
 * CaptureMouse=false / FreeMouse=true change nothing. So dgVoodoo pins the pointer inside the
 * app's 640x480 scaled by the window-height factor, ANCHORED AT THE CLIENT ORIGIN, and ignores
 * the 760 px pillarbox of the drawn 4:3 frame (760..2680). Hit-testing was right (a raw click at
 * the drawn Play Options, client (1480,510), mapped to frame (240,170) and opened it); the Exit
 * at drawn x = 760 + 3*432 = 2056 is unreachable only because the pointer stops at 1919.
 *
 * Warping the pointer ourselves is pointless (dgVoodoo re-pins). Instead, while the menu is up,
 * the reachable box becomes the mapping domain: box -> 640x480 page space, linearly, so every
 * drawn item can be hit - the hand sits left of the drawn item by the scaled pillarbox offset,
 * the same "up in the corner" relation the shell screens already have. The box is RECORDED from
 * GetClipCursor while the engine is NOT in the menu (mode != 0x10): a clip smaller than the
 * client and larger than UI size; a clip that covers the client forgets it. With no measured box
 * the presented-frame map above is used (the computed-box fallback is gone, see menu_box_map).
 * I76_U32X_MENU_BOX=0 disables the box and leaves the frame map.
 *
 * CORRECTION (2026-10-02, late): the 1920x1440 box above was the doing of dgVoodoo's GLOBAL
 * %APPDATA% conf (FullScreenMode true, Resolution 1920x1440), which was live because dgVoodoo
 * 2.87.3 silently rejected game\dgVoodoo.conf. With the sandbox conf fixed and accepted the
 * clip in the mission and in the menu is the whole client and nothing pins the pointer. */
static RECT  g_box;          /* last reachable box seen outside the menu, screen coords */
static int   g_box_seen;
static DWORD g_box_tick;

static int menu_box_enabled(void)
{
    static int en = -1;
    if (en < 0) {
        char v[8];
        DWORD n = GetEnvironmentVariableA("I76_U32X_MENU_BOX", v, sizeof v);
        en = (n == 1 && v[0] == '0') ? 0 : 1;
        LOG("I76_U32X_MENU_BOX -> %d\n", en);
    }
    return en;
}

/* called from the exe's per-frame paths; cheap, rate-limited to 10 Hz */
static void menu_box_record(void)
{
    static DWORD last;
    DWORD now;
    RECT c, rc;
    POINT org = { 0, 0 };
    HWND h;
    LONG w, hh;

    if (!menu_enabled() || !menu_box_enabled() || !exe_known())
        return;
    if (*(volatile DWORD *)EXE_MODE == 0x10)
        return;                                     /* in the menu the clip is released */
    now = GetTickCount();
    if (now - last < 100)
        return;
    last = now;
    if (!GetClipCursor(&c))
        return;
    h = game_window();
    if (!h || !GetClientRect(h, &rc) || rc.right <= 0 || rc.bottom <= 0)
        return;
    ClientToScreen(h, &org);
    w = c.right - c.left; hh = c.bottom - c.top;
    if (w <= UI_W + 64 || hh <= UI_H + 64)
        return;                                     /* a UI-sized box: the engine's / none */
    if (w >= rc.right && hh >= rc.bottom) {
        /* the whole client or the screen: the pointer is FREE, and that is a measurement too -
         * a box remembered from another regime must not outlive it (2026-10-02, late) */
        if (g_box_seen)
            LOG("MENU box forgotten: clip (%ld,%ld)-(%ld,%ld) covers the client %ldx%ld\n",
                c.left, c.top, c.right, c.bottom, rc.right, rc.bottom);
        g_box_seen = 0;
        return;
    }
    if (c.left < org.x - 8 || c.top < org.y - 8 ||
        c.right > org.x + rc.right + 8 || c.bottom > org.y + rc.bottom + 8)
        return;                                     /* not inside our client */
    if (!g_box_seen || memcmp(&c, &g_box, sizeof c) != 0)
        LOG("MENU box recorded (%ld,%ld)-(%ld,%ld) client %ldx%ld org (%ld,%ld)\n",
            c.left, c.top, c.right, c.bottom, rc.right, rc.bottom, org.x, org.y);
    g_box = c; g_box_seen = 1; g_box_tick = now;
}

/* the box as a Map onto lw x lh; 0 when no usable box */
static int menu_box_map(Map *out, int lw, int lh)
{
    HWND h = game_window();
    RECT rc, b;
    POINT org = { 0, 0 };
    Map m = { 1.0, 1.0, 0, 0, UI_W, UI_H, 0, 0, 0, "box" };

    if (!menu_box_enabled() || !h || !GetClientRect(h, &rc) || rc.right <= 0 || rc.bottom <= 0)
        return 0;
    ClientToScreen(h, &org);
    if (g_box_seen &&
        g_box.left >= org.x - 8 && g_box.top >= org.y - 8 &&
        g_box.right <= org.x + rc.right + 8 && g_box.bottom <= org.y + rc.bottom + 8) {
        b = g_box;                                  /* measured */
    } else {
        /* NO COMPUTED BOX (2026-10-02, late). Until tonight a pillarboxed client with no measured
         * box got "4:3 x client height at the client origin". That shape was never dgVoodoo's
         * rule: it was the 2020 GLOBAL conf (Resolution 1920x1440) that dgVoodoo fell back to
         * while it rejected game\dgVoodoo.conf. With the conf accepted the pointer roams the
         * whole client in the mission and in the menu, and the computed box made the drawn Exit
         * (2056,1335) miss while I76_U32X_MENU_BOX=0 hit it. Only a measured clip is a box;
         * with none, the caller uses the presented-frame map (hand on the drawn item). */
        return 0;
    }
    if (b.right - b.left < 320 || b.bottom - b.top < 240 || lw <= 0 || lh <= 0)
        return 0;
    m.cw = rc.right; m.ch = rc.bottom;
    m.lw = lw; m.lh = lh;
    m.sx = b.left; m.sy = b.top;
    m.scale_x = (double)(b.right - b.left) / (double)lw;
    m.scale   = (double)(b.bottom - b.top) / (double)lh;
    m.valid = 1;
    *out = m;
    return 1;
}

/* the exe's in-mission menu: the MEASURED reachable box when there is one, else its display
 * frame at the presented frame aspect */
static Map get_menu_map(void)
{
    double aw, ah; int fw, fh;
    Map m;
    exe_frame(&fw, &fh);
    if (menu_box_map(&m, fw, fh))
        return m;
    menu_aspect(&aw, &ah);
    m = map_for(aw, ah, fw, fh);
    m.tag = "frame";
    return m;
}

/* the map a given caller gets: the exe while its menu is up -> frame map; everyone else -> UI */
static Map map_for_caller(const void *ra)
{
    return (exe_in_menu() && caller_is_exe(ra)) ? get_menu_map() : get_map();
}

static void screen_to_logical(const Map *m, LONG sx, LONG sy, LONG *lx, LONG *ly)
{
    *lx = clampl((LONG)((sx - m->sx) / m->scale_x + 0.5), 0, m->lw - 1);
    *ly = clampl((LONG)((sy - m->sy) / m->scale   + 0.5), 0, m->lh - 1);
}

/* While the exe menu is up the pointer must be able to reach the whole mapping domain. If
 * something holds it in a UI-sized box - the engine's own ClipCursor(0,0,w,h) passed through
 * by an older proxy build - move the clip onto the menu map's domain (the reachable box, or
 * the presented frame). Rate-limited; a free or already larger clip is left alone (Test A:
 * in the menu the OS clip reads 0,0-3440,1440, so this never fires there; dgVoodoo's own
 * pinning is not a clip and cannot be lifted from here). Leaving the menu, the engine re-arms
 * its own clip (0x4952b0 -> 0x44bb40 -> mouse_Poll), which My_ClipCursor maps. */
static void menu_free_pointer(void)
{
    static DWORD last;
    DWORD now;
    RECT c, s;
    Map m;

    if (!exe_in_menu())
        return;
    now = GetTickCount();
    if (now - last < 100)
        return;
    last = now;
    if (!GetClipCursor(&c))
        return;
    if ((c.right - c.left) > UI_W + 64 || (c.bottom - c.top) > UI_H + 64)
        return;                                     /* already free */
    m = get_menu_map();
    if (!m.valid)
        return;
    s.left   = m.sx;
    s.top    = m.sy;
    s.right  = m.sx + (LONG)(m.lw * m.scale_x + 0.5);
    s.bottom = m.sy + (LONG)(m.lh * m.scale   + 0.5);
    LOG("MENU clip (%ld,%ld)-(%ld,%ld) is UI-sized - moved onto the frame (%ld,%ld)-(%ld,%ld)\n",
        c.left, c.top, c.right, c.bottom, s.left, s.top, s.right, s.bottom);
    ClipCursor(&s);
}

/* ==== A1 "ONE POINTER" (2026-10-02) =====================================================
 * i76-everywhere docs/MENU-REBUILD-DESIGN.md section 7; docs/MOUSE-ESC-MENU-AND-SAVE-SCREEN.md
 * section 9. Everything below is dead unless I76_U32X_VPTR=1.
 *
 * Measured (same doc, sections 5a and 7; the integrator's gate run of 2026-10-02): dgVoodoo
 * confines the OS pointer to the app's 640x480 scaled by a factor, anchored at the client
 * origin - 1920x1440 in the Glide mission and Esc menu, and the plain 640x480 corner while the
 * shell's DirectDraw screens are up (there the shell reads the OS position 1:1). The 4:3
 * picture is drawn at 760..2680. So the hand is never over what it points at, and in the Esc
 * menu nothing is drawn at the point that will be hit.
 *
 * Two things, each with its own kill switch:
 *
 * 1. THE SHELL MAP (I76_U32X_VPTR_MAP). For callers inside i76shell.dll the box the pointer can
 *    reach is read from GetClipCursor on every call and mapped LINEARLY onto 640x480:
 *      - a UI-sized box (640x480 +-1): UI = position - box origin. Exactly the 1:1 the shell has
 *        today (the harness's SetCursorPos(ux,uy) clicks keep working unchanged);
 *      - any other box smaller than the client (dgVoodoo's scaled 1920x1440 box, or a clip that
 *        was put on the picture rect): UI = (position - box origin) * 640 / box width. Pointer
 *        travel is then 1 picture pixel per pixel of hand on this geometry;
 *      - no clip (free pointer): the regime rule that exists (the 4:3 picture map), untouched.
 *    The value handed back is client origin + UI, because Mouse_Update 0x1001fbf0 runs
 *    ScreenToClient on it. Mouse-message lParams and the shell's SetCursorPos follow the same box.
 *    In a corner box the map is the identity, so the 3x hand-vs-picture speed stays: 640 px of
 *    reach cannot cover 640 UI units any slower. So the default is to MOVE that box onto the
 *    picture rect (vptr_try_widen; I76_U32X_VPTR_WIDEN=0 keeps the corner).
 *
 * 2. THE CURSOR WINDOW (I76_U32X_VPTR_CURSOR). A 24x38 arrow in a WS_EX_LAYERED |
 *    WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW popup, OWNED by the
 *    game window, created lazily on the thread that owns the game window, drawn once with
 *    UpdateLayeredWindow and from then on only moved. Its top-left (the hot spot) is put where
 *    the mapped point lands in the PICTURE: picture origin + scale * UI, from the live client
 *    rect (760 + 3*ux, 3*uy here). Shown while the shell polls the mouse (a shell GetCursorPos in
 *    the last 500 ms) and while the exe's Esc menu is up ([0x4fe534] == 0x10); hidden in the
 *    mission, during loads, when the game is not the foreground window, while one of its
 *    dialogs is, AND WHEREVER THE OS ARROW IS ALREADY WITHIN ~1 UI UNIT OF THAT POINT (free
 *    pointer, or the clip moved onto the picture): then the real arrow is the one pointer
 *    (I76_U32X_VPTR_CURSOR_ALWAYS=1 shows ours regardless). The OS arrow is hidden by exactly one ShowCursor(FALSE) when ours appears and
 *    given back by exactly one ShowCursor(TRUE) when ours goes (I76_U32X_VPTR_HIDEOS=0: never).
 *
 * THE WM_QUIT LESSON, applied: nothing here calls PeekMessage, GetMessage, DispatchMessage,
 * SendMessage or PostMessage, and no IAT is patched. The window needs no WM_PAINT (layered,
 * pre-rendered) and takes no input (HTTRANSPARENT + WS_EX_TRANSPARENT), so the only traffic it
 * adds is the synchronous WM_WINDOWPOS* / WM_SHOWWINDOW that SetWindowPos / ShowWindow SEND to
 * our own WndProc, plus whatever the system broadcasts to every top-level window - and those the
 * application's own loop retrieves and dispatches, as it does for its own window. Owned on
 * purpose: .NET's Process.MainWindowHandle (which the whole autotest harness uses) skips owned
 * windows, and an unowned topmost window would have become "the game window" there. It is under
 * 64 px both ways so find_own_window (and uiclick.ps1's Get-UiMap) can never pick it. */
static HINSTANCE g_inst;

/* is the return address inside i76shell.dll? (not cached: the exe loads the DLL at run time) */
static int caller_is_shell(const void *ra)
{
    HMODULE sh = GetModuleHandleA("i76shell.dll");
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)sh;
    const IMAGE_NT_HEADERS *nt;
    if (!sh || dos->e_magic != IMAGE_DOS_SIGNATURE)
        return 0;
    nt = (const IMAGE_NT_HEADERS *)((const BYTE *)dos + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE)
        return 0;
    return (ULONG_PTR)ra >= (ULONG_PTR)sh &&
           (ULONG_PTR)ra <  (ULONG_PTR)sh + nt->OptionalHeader.SizeOfImage;
}

/* what kind of box the pointer lives in right now (a direct GetClipCursor measurement) */
#define VB_NONE 0       /* no window / no answer: fall back to the existing regime rule      */
#define VB_UI   1       /* 640x480 +-1: the 1:1 corner box                                   */
#define VB_BOX  2       /* some other box smaller than the client: map it linearly           */
#define VB_FREE 3       /* the clip covers the client (or the screen): existing picture map  */
static int vptr_shell_box(RECT *box)
{
    HWND h = game_window();
    RECT rc, c;
    LONG w, hh;

    if (!h || !GetClientRect(h, &rc) || rc.right <= 0 || rc.bottom <= 0 || !GetClipCursor(&c))
        return VB_NONE;
    w = c.right - c.left; hh = c.bottom - c.top;
    if (w < 64 || hh < 64)
        return VB_NONE;
    if (w >= rc.right && hh >= rc.bottom)
        return VB_FREE;
    *box = c;
    if (w >= UI_W - 1 && w <= UI_W + 1 && hh >= UI_H - 1 && hh <= UI_H + 1)
        return VB_UI;
    return VB_BOX;
}

static void vptr_box_to_ui(const RECT *b, int kind, LONG sx, LONG sy, LONG *ux, LONG *uy)
{
    LONG w = b->right - b->left, h = b->bottom - b->top;
    LONG dx = sx - b->left, dy = sy - b->top;
    if (dx < 0) dx = 0;
    if (dy < 0) dy = 0;
    if (kind != VB_UI && w > 0 && h > 0) {      /* floor: x 0..2 -> 0, 3..5 -> 1 at 3.0x */
        dx = (dx * UI_W) / w;
        dy = (dy * UI_H) / h;
    }
    *ux = clampl(dx, 0, UI_W - 1);
    *uy = clampl(dy, 0, UI_H - 1);
}

/* the shell hands SetCursorPos a screen point = client origin + UI; put the pointer on the
 * middle of that UI cell inside the box, so the floor above reads the same UI point back */
static void vptr_ui_to_box(const RECT *b, int x, int y, POINT *out)
{
    HWND h = game_window();
    POINT org = { 0, 0 };
    LONG w = b->right - b->left, hh = b->bottom - b->top;
    LONG ux, uy;
    if (h) ClientToScreen(h, &org);
    ux = clampl(x - org.x, 0, UI_W - 1);
    uy = clampl(y - org.y, 0, UI_H - 1);
    out->x = b->left + (ux * w + w / 2) / UI_W;
    out->y = b->top  + (uy * hh + hh / 2) / UI_H;
}

/* HAND ON THE DRAWN ITEM (default under VPTR; I76_U32X_VPTR_WIDEN=0 turns it off): when the
 * shell sits in the UI-sized corner box, put the clip on the drawn 4:3 picture rect instead -
 * what My_ClipCursor has done since Sep-5 for a clip the game itself asks for. Every cursor
 * import of i76.exe and i76shell.dll goes through this proxy and My_ClipCursor never passes a
 * UI-sized rect on, so a 640x480 clip that is live in the shell (leg-b: OS (217,311) -> shell
 * mouse (217,311)) was set by something else - dgVoodoo's CaptureMouse in the shell's 640x480
 * DirectDraw mode [inferred from the import tables; not observed]. If our clip holds, the box
 * becomes VB_BOX == the picture, the hand is over the picture at picture speed and the real
 * arrow is right, so vptr_tick shows no cursor window.
 * If something (dgVoodoo's CaptureMouse) puts the corner box back, that is counted, and after
 * three reverts this stands down for the rest of the process - the mapping always follows the
 * box that is actually measured, so a revert costs nothing but the attempt. What this cannot
 * see: a pin that is NOT a clip (what the old global conf did in the Esc menu). If the pointer
 * then stops short while the clip reads wide, the pencil cannot reach the whole form: set
 * I76_U32X_VPTR_WIDEN=0 (1:1 corner + the cursor window) and report it. */
static void vptr_try_widen(void)
{
    static int   reverted, armed;
    static DWORD last, armed_tick;
    DWORD now;
    Map pm;
    RECT s;

    if (!sw_vptr_widen() || reverted >= 3)
        return;
    now = GetTickCount();
    if (armed) {                            /* we widened, and the box is UI-sized again */
        armed = 0;
        if (now - armed_tick > 2000) {
            reverted = 0;                   /* it held for a while: somebody's legitimate re-clip */
        } else {
            reverted++;
            LOG("[%lu] VPTR widen: the corner box came back after %lu ms (%d of 3)%s\n",
                (unsigned long)now, (unsigned long)(now - armed_tick), reverted,
                reverted >= 3 ? " - giving up, the box is not ours to move" : "");
        }
    }
    if (reverted >= 3 || now - last < 250)
        return;
    last = now;
    pm = get_map();
    if (!pm.valid)
        return;
    s.left   = pm.sx;
    s.top    = pm.sy;
    s.right  = pm.sx + (LONG)(UI_W * pm.scale_x + 0.5);
    s.bottom = pm.sy + (LONG)(UI_H * pm.scale   + 0.5);
    if (ClipCursor(&s)) {
        armed = 1; armed_tick = now;
        LOG("[%lu] VPTR widen: clip -> picture rect (%ld,%ld)-(%ld,%ld)\n",
            (unsigned long)now, s.left, s.top, s.right, s.bottom);
    }
}

/* ---- the cursor window ---- */
static int   g_vp_tries;        /* CreateWindowEx attempts (max 3 per process)               */
static int   g_vp_k;            /* arrow magnification currently painted (0 = none)          */
static int   g_vp_shown;
static int   g_vp_oshidden;     /* we owe the thread exactly one ShowCursor(TRUE)            */
static DWORD g_vp_tid;          /* the UI thread that shows / hides                          */
static POINT g_vp_at;           /* last screen position of the hot spot                      */
static POINT g_vp_ui;           /* last UI point handed to the shell                         */
static DWORD g_vp_shell_tick;   /* when                                                      */
static int   g_vp_shell_seen;

static void vptr_note_shell(LONG ux, LONG uy)
{
    g_vp_ui.x = ux; g_vp_ui.y = uy;
    g_vp_shell_tick = GetTickCount();
    g_vp_shell_seen = 1;
}

/* GetCursorPos for a shell caller under VPTR. 1 = *p rewritten (client origin + UI). */
static int vptr_shell_getpos(POINT *p)
{
    RECT b;
    HWND h;
    POINT org = { 0, 0 };
    LONG ux, uy;
    int kind;

    if (!sw_vptr_map())
        return 0;
    kind = vptr_shell_box(&b);
    if (kind != VB_UI && kind != VB_BOX)
        return 0;                           /* free / unknown: the existing regime rule */
    if (kind == VB_UI)
        vptr_try_widen();
    vptr_box_to_ui(&b, kind, p->x, p->y, &ux, &uy);
    h = game_window();
    if (h) ClientToScreen(h, &org);
    LOG_V("VPTR GetCursorPos shell raw=(%ld,%ld) box (%ld,%ld)-(%ld,%ld) %s -> UI=(%ld,%ld)\n",
          p->x, p->y, b.left, b.top, b.right, b.bottom, kind == VB_UI ? "1:1" : "linear", ux, uy);
    p->x = org.x + ux;
    p->y = org.y + uy;
    vptr_note_shell(ux, uy);
    return 1;
}

static LRESULT CALLBACK VptrWndProc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    switch (m) {
    case WM_NCHITTEST:     return HTTRANSPARENT;
    case WM_MOUSEACTIVATE: return MA_NOACTIVATE;
    case WM_CLOSE:         return 0;        /* dies with its owner, not before */
    }
    return DefWindowProcA(h, m, w, l);
}

/* the classic arrow, 12x19, hot spot at (0,0): X outline, . fill, blank = transparent */
static int vptr_paint(int k)
{
    static const char *const shape[19] = {
        "X           ",
        "XX          ",
        "X.X         ",
        "X..X        ",
        "X...X       ",
        "X....X      ",
        "X.....X     ",
        "X......X    ",
        "X.......X   ",
        "X........X  ",
        "X.........X ",
        "X......XXXXX",
        "X...X..X    ",
        "X..XX..X    ",
        "X.X  X..X   ",
        "XX   X..X   ",
        "X     X..X  ",
        "      X..X  ",
        "       XX   "
    };
    BITMAPINFO bi;
    BLENDFUNCTION bf;
    void *bits = NULL;
    HDC sdc, mdc;
    HBITMAP bmp;
    HGDIOBJ old;
    SIZE sz;
    POINT src = { 0, 0 };
    int w = 12 * k, h = 19 * k, x, y, ok = 0;

    ZeroMemory(&bi, sizeof bi);
    bi.bmiHeader.biSize        = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth       = w;
    bi.bmiHeader.biHeight      = -h;        /* top-down */
    bi.bmiHeader.biPlanes      = 1;
    bi.bmiHeader.biBitCount    = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    sdc = GetDC(NULL);
    mdc = sdc ? CreateCompatibleDC(sdc) : NULL;
    bmp = mdc ? CreateDIBSection(mdc, &bi, DIB_RGB_COLORS, &bits, NULL, 0) : NULL;
    if (bmp && bits) {
        DWORD *px = (DWORD *)bits;
        for (y = 0; y < h; y++) {
            const char *row = shape[y / k];
            for (x = 0; x < w; x++) {
                char c = row[x / k];        /* every row is 12 characters */
                px[y * w + x] = (c == 'X') ? 0xFF000000u : (c == '.') ? 0xFFFFFFFFu : 0u;
            }                               /* opaque or clear: already premultiplied */
        }
        old = SelectObject(mdc, bmp);
        sz.cx = w; sz.cy = h;
        bf.BlendOp = AC_SRC_OVER; bf.BlendFlags = 0;
        bf.SourceConstantAlpha = 255; bf.AlphaFormat = AC_SRC_ALPHA;
        ok = UpdateLayeredWindow(g_vp_hwnd, sdc, NULL, &sz, mdc, &src, 0, &bf, ULW_ALPHA);
        SelectObject(mdc, old);
    }
    if (bmp) DeleteObject(bmp);
    if (mdc) DeleteDC(mdc);
    if (sdc) ReleaseDC(NULL, sdc);
    return ok;
}

/* hide ours and give the OS arrow back; UI thread only (ShowCursor's count is per thread) */
static void vptr_hide(void)
{
    if (!g_vp_shown && !g_vp_oshidden)
        return;
    if (g_vp_tid && GetCurrentThreadId() != g_vp_tid)
        return;
    if (g_vp_shown) {
        g_vp_shown = 0;
        if (g_vp_hwnd && IsWindow(g_vp_hwnd))
            ShowWindow(g_vp_hwnd, SW_HIDE);
        LOG("[%lu] VPTR cursor hidden\n", (unsigned long)GetTickCount());
    }
    if (g_vp_oshidden) {
        g_vp_oshidden = 0;
        ShowCursor(TRUE);                   /* the one that pairs with vptr_show's FALSE */
    }
}

static void vptr_show(HWND gw, LONG x, LONG y, double scale)
{
    int k = (int)(scale * 2.0 / 3.0 + 0.5);
    if (k < 1) k = 1;
    if (k > 3) k = 3;                       /* 36x57 at most: stays under the 64 px floor */

    if (g_vp_hwnd && !IsWindow(g_vp_hwnd)) {    /* went with its owner */
        g_vp_hwnd = NULL; g_vp_k = 0;
        vptr_hide();
    }
    if (!g_vp_hwnd) {
        static int registered;
        if (g_vp_tries >= 3)
            return;
        g_vp_tries++;
        if (!registered) {
            WNDCLASSA wc;
            ZeroMemory(&wc, sizeof wc);
            wc.lpfnWndProc   = VptrWndProc;
            wc.hInstance     = g_inst;
            wc.lpszClassName = "u32xVptr";
            registered = RegisterClassA(&wc) != 0;
        }
        g_vp_hwnd = CreateWindowExA(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE |
                                    WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                                    "u32xVptr", "u32x pointer", WS_POPUP,
                                    (int)x, (int)y, 12 * k, 19 * k, gw, NULL, g_inst, NULL);
        LOG("[%lu] VPTR cursor window %p (owner %p, attempt %d, thread %lu)\n",
            (unsigned long)GetTickCount(), (void *)g_vp_hwnd, (void *)gw, g_vp_tries,
            (unsigned long)GetCurrentThreadId());
        if (!g_vp_hwnd)
            return;
        g_vp_k = 0;
    }
    if (k != g_vp_k) {
        if (!vptr_paint(k)) {
            LOG("VPTR UpdateLayeredWindow failed (%lu)\n", (unsigned long)GetLastError());
            return;
        }
        g_vp_k = k;
    }
    if (!g_vp_shown || x != g_vp_at.x || y != g_vp_at.y) {
        SetWindowPos(g_vp_hwnd, HWND_TOPMOST, (int)x, (int)y, 0, 0,
                     SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_NOSENDCHANGING |
                     (g_vp_shown ? SWP_NOZORDER : SWP_SHOWWINDOW));
        g_vp_at.x = x; g_vp_at.y = y;
    }
    if (!g_vp_shown) {
        g_vp_shown = 1;
        g_vp_tid = GetCurrentThreadId();
        if (sw_vptr_hideos() && !g_vp_oshidden) {
            ShowCursor(FALSE);              /* exactly one; vptr_hide gives exactly one back */
            g_vp_oshidden = 1;
        }
        LOG("[%lu] VPTR cursor shown at (%ld,%ld) x%d\n", (unsigned long)GetTickCount(), x, y, k);
    }
}

/* EXPERIMENT (I76_U32X_VPTR_WINDOW=1, default off; MENU-REBUILD-DESIGN section 7 step 3): put
 * the game window's CLIENT on the 4:3 picture rectangle (1920x1440 at x 760 here). If
 * dgVoodoo's box is anchored at the client origin it then coincides with the picture and the
 * real arrow is right everywhere; if dgVoodoo sizes the window back or the box stays at the
 * screen origin, the log build's 1 Hz "VPTR state" line records that. At most 3 attempts, 1 s
 * apart, only from the top of the application's own message loop (My_PeekMessageA), and only
 * while the client is wider than 4:3. SetWindowPos SENDS WM_WINDOWPOSCHANGED / WM_SIZE to the
 * game's WndProc synchronously; it does not touch the queue. No backdrop is drawn: the desktop
 * shows either side for the length of the experiment. */
static void vptr_window_experiment(HWND gw)
{
    static int   tries;
    static DWORD last;
    DWORD now;
    RECT rc, wr, after;
    POINT org = { 0, 0 };
    LONG pw;

    if (!sw_vptr_window() || tries >= 3)
        return;
    now = GetTickCount();
    if (now - last < 1000)
        return;
    last = now;
    if (!GetClientRect(gw, &rc) || rc.bottom < 240)
        return;
    pw = (LONG)((double)rc.bottom * 4.0 / 3.0 + 0.5);
    if (rc.right <= pw + 2)
        return;                             /* already 4:3 (or narrower): nothing to do */
    ClientToScreen(gw, &org);
    wr.left   = org.x + (rc.right - pw) / 2;
    wr.top    = org.y;
    wr.right  = wr.left + pw;
    wr.bottom = org.y + rc.bottom;
    AdjustWindowRectEx(&wr, (DWORD)GetWindowLongA(gw, GWL_STYLE), FALSE,
                       (DWORD)GetWindowLongA(gw, GWL_EXSTYLE));
    tries++;
    SetWindowPos(gw, NULL, wr.left, wr.top, wr.right - wr.left, wr.bottom - wr.top,
                 SWP_NOZORDER | SWP_NOACTIVATE);
    org.x = org.y = 0;
    ClientToScreen(gw, &org);
    GetClientRect(gw, &after);
    LOG("[%lu] VPTR window experiment %d: client %ldx%ld -> asked %ldx%ld at x %ld, now %ldx%ld at (%ld,%ld)\n",
        (unsigned long)now, tries, rc.right, rc.bottom, pw, rc.bottom, wr.left,
        after.right, after.bottom, org.x, org.y);
}

/* Called from My_GetCursorPos and from the top of My_PeekMessageA (from_loop). Decides whether
 * our cursor is up and where, and moves it. Reads state, moves one window; nothing else. */
static void vptr_tick(int from_loop)
{
    HWND gw, fg;
    DWORD now;
    int want = 0;
    LONG ax = 0, ay = 0;
    double sc = 1.0;
    const char *mode = "none";

    if (!sw_vptr())
        return;
    gw = game_window();
    if (!gw || GetWindowThreadProcessId(gw, NULL) != GetCurrentThreadId())
        return;                             /* the game's UI thread only */
    if (from_loop)
        vptr_window_experiment(gw);
    if (!sw_vptr_cursor())
        return;

    now = GetTickCount();
    fg  = GetForegroundWindow();
    if (fg && (fg == gw || IsChild(gw, fg)) && !IsIconic(gw)) {
        if (g_vp_shell_seen && now - g_vp_shell_tick < 500) {
            /* a shell screen is polling the mouse: the point it was just handed */
            mode = "shell";
            if (sw_vptr_shellcur()) {
                Map pm = get_map();
                if (pm.valid) {
                    ax = pm.sx + (LONG)(g_vp_ui.x * pm.scale_x + 0.5);
                    ay = pm.sy + (LONG)(g_vp_ui.y * pm.scale   + 0.5);
                    sc = pm.scale; want = 1;
                }
            }
        } else if (exe_in_menu()) {
            /* the exe's Esc menu: the frame point a click would be given (the same map and
             * rounding as My_PeekMessageA), drawn where that point is in the presented frame */
            POINT p;
            mode = "menu";
            if (GetCursorPos(&p)) {
                Map hit = get_menu_map(), pic;
                double aw, ah;
                int fw, fh;
                LONG lx, ly;
                exe_frame(&fw, &fh);
                menu_aspect(&aw, &ah);
                pic = map_for(aw, ah, fw, fh);
                if (hit.valid && pic.valid) {
                    screen_to_logical(&hit, p.x, p.y, &lx, &ly);
                    ax = pic.sx + (LONG)(lx * pic.scale_x + 0.5);
                    ay = pic.sy + (LONG)(ly * pic.scale   + 0.5);
                    sc = pic.scale; want = 1;
                }
            }
        }
    }
    if (want && !sw_vptr_always()) {
        /* ONE pointer: where the OS arrow already sits on the point that will be hit (a free
         * pointer through the picture / frame map, or a clip that was moved onto the picture)
         * the real arrow is the pointer and ours stays away. */
        POINT raw;
        LONG tol = (LONG)(sc + 1.5);
        if (GetCursorPos(&raw) &&
            raw.x >= ax - tol && raw.x <= ax + tol && raw.y >= ay - tol && raw.y <= ay + tol)
            want = 0;
    }
    if (want) vptr_show(gw, ax, ay, sc);
    else      vptr_hide();

#ifdef U32X_LOG
    {   static DWORD last_;
        if (now - last_ >= 1000) {          /* the record for the WIDEN / WINDOW experiments */
            RECT c, rc;
            POINT org = { 0, 0 }, raw = { 0, 0 };
            CURSORINFO ci;
            last_ = now;
            SetRectEmpty(&c); SetRectEmpty(&rc);
            GetClipCursor(&c); GetClientRect(gw, &rc); ClientToScreen(gw, &org); GetCursorPos(&raw);
            ZeroMemory(&ci, sizeof ci); ci.cbSize = sizeof ci; GetCursorInfo(&ci);
            LOG("[%lu] VPTR state mode=%s clip (%ld,%ld)-(%ld,%ld) client %ldx%ld at (%ld,%ld) raw=(%ld,%ld) "
                "ui=(%ld,%ld) shown=%d at=(%ld,%ld) os_hidden_by_us=%d os_showing=%d\n",
                (unsigned long)now, mode, c.left, c.top, c.right, c.bottom, rc.right, rc.bottom,
                org.x, org.y, raw.x, raw.y, g_vp_ui.x, g_vp_ui.y, g_vp_shown, g_vp_at.x, g_vp_at.y,
                g_vp_oshidden, (int)(ci.flags & CURSOR_SHOWING));
        }
    }
#else
    (void)mode;
#endif
}

/* WHY THE EARLIER VERSIONS WERE WRONG (kept so nobody re-derives them):
 *   v1 decided whether to translate from the MAGNITUDE of the coordinate - values inside
 *      0..639/0..479 were assumed pre-mapped. At 3440x1440 the UI renders at screen x=760..2680,
 *      so the whole top-left 640x480 of the screen lies in the left black bar: v1 passed real
 *      black-bar positions through as if they were UI space. Its untranslated ClipCursor then
 *      pinned the pointer inside exactly that box, so its calibration could never escape.
 *   v2 translated unconditionally - correct when the pointer is free, but it double-maps the
 *      coordinates dgVoodoo has ALREADY mapped, which killed menu highlighting.
 * Both guessed. v4 measures instead (see pointer_is_confined below). */

/* ---- intercepts ------------------------------------------------------------------------ */

/* WHICH REGIME ARE WE IN?  This is the measurable discriminator the earlier versions lacked.
 *
 * dgVoodoo runs the mouse one of two ways, and the correct behaviour is opposite in each:
 *   CONFINED  - dgVoodoo pins the pointer inside a UI-sized box (ClipCursor(0,0,640,480)) and
 *               maps it into the app's space itself. The app's coordinates are ALREADY right;
 *               translating them (v2) breaks every menu. -> PASS THROUGH.
 *   FREE      - no confinement (windowed mode, or the clip was lost mid-game, which is THE
 *               FREEZE). The app now receives raw SCREEN coordinates it can never match
 *               against its 640x480 widgets. -> TRANSLATE via the live window geometry.
 *
 * Asking GetClipCursor is a direct measurement of which one is live, so we never have to guess
 * from the magnitude of a coordinate - the mistake that made v1 and v2 wrong. */
static int pointer_is_confined(void)
{
    RECT c;
    if (!GetClipCursor(&c))
        return 0;
    return (c.right - c.left) <= (UI_W + 64) && (c.bottom - c.top) <= (UI_H + 64);
}

/* ---- keep the window alive while the shell spins ---------------------------------------
 * The shell has TWO modal loops that never service the message queue:
 *   - name entry     : PeekMessageA(.., WM_KEYFIRST, WM_KEYLAST, ..) - keyboard only
 *   - button/confirm : a GetCursorPos poll - no PeekMessage at all
 * Either way Windows sees no pumping, declares the process NOT RESPONDING after ~5s, and
 * DWM lays a Ghost window over it. The ghost then owns the input, so the next keystroke or
 * click never reaches the game and it is wedged for good.
 *
 * Pump everything the shell is NOT itself consuming: skip keyboard (0x100-0x108) and mouse
 * (0x200-0x20E) so its own loops still receive them, and dispatch the rest. Bounded, and
 * rate-limited so this can never become the hot path.  */
/* WM_QUIT IS NOT OURS TO TAKE.  (2026-10-02, the TRIP garage DONE regression)
 *
 * ShellMain's frame loop (i76shell 0x1001e260) has exactly one exit: its own
 *     PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)  ->  msg.message == WM_QUIT
 * and the shell leaves for a mission by ShellWindowProc's 0xC010 case doing RequireCD2 (exe
 * callback 17: volume probes, an MCI open, a .smk open) and then PostQuitMessage(0xC001)
 * (0x1001e127). The very next thing that loop does after dispatching 0xC010 is Mouse_Update ->
 * GetCursorPos + 3x GetAsyncKeyState - all of which pump here. The first pump range used to be
 * 0..WM_KEYFIRST-1 with PM_REMOVE, which contains WM_QUIT (0x12): the pump took the quit and
 * "dispatched" it to nobody. ShellMain then spun in PeekMessageA forever with no screen
 * function - exe frame counter 0, game state 6, main thread in NtUserPeekMessage (win32u+0x101C
 * is the return address inside that stub), measured 4 of 4 on the bookmark -> garage -> DONE
 * route. The exe's WinMain loops read WM_QUIT the same way, so the same theft could lose an
 * exit there too.
 *
 * So: the ranges now step around WM_QUIT, and because PeekMessage is documented to return
 * WM_QUIT whatever the filter says, any WM_QUIT that still comes out is put straight back with
 * PostQuitMessage(wParam) (same exit code, same thread) and the pump stands down until the
 * application's own PeekMessageA has collected it (or 2 s pass). I76_U32X_QUITGUARD=0 restores
 * the old behaviour for the control run.
 *
 * Also no longer touched: WM_USER and above. The shell drives its screen changes with posted
 * private messages (0xC002..0xC026, registered range) that the stock code dispatches only from
 * the top of ShellMain's loop; pumping them from inside Mouse_Update or a modal poll ran screen
 * transitions re-entrantly. Hang detection never needed them. I76_U32X_PUMP_PRIVATE=1 = old. */
static volatile LONG g_quit_held;       /* a WM_QUIT we re-posted is waiting for its owner */
static DWORD         g_quit_tick;

/* returns 0 when the pump must stop (a WM_QUIT was found and handed back) */
static int pump_dispatch(MSG *m)
{
    if (m->message == WM_QUIT && sw_quitguard()) {
        PostQuitMessage((int)m->wParam);
        g_quit_tick = GetTickCount();
        g_quit_held = 1;
        LOG("[%lu] pump_keepalive met WM_QUIT wp=0x%X - re-posted, pump standing down\n",
            (unsigned long)g_quit_tick, (unsigned)m->wParam);
        return 0;
    }
    TranslateMessage(m); DispatchMessageA(m);
    return 1;
}

static void pump_keepalive(void)
{
    static DWORD last = 0;
    DWORD now = GetTickCount();
    MSG m;
    int n, guard;
    UINT top;

    if (!sw_pumps())
        return;
    guard = sw_quitguard();
    if (guard && g_quit_held) {
        if (now - g_quit_tick < 2000)
            return;                 /* the owner's loop has not collected its WM_QUIT yet */
        g_quit_held = 0;
    }
    if (now - last < 40)        /* ~25 Hz is plenty to satisfy hang detection */
        return;
    last = now;
    LOG_V("pump_keepalive running\n");

    if (guard) {
        for (n = 0; n < 16 && PeekMessageA(&m, NULL, 0, WM_QUIT - 1, PM_REMOVE); n++)
            if (!pump_dispatch(&m)) return;
        for (n = 0; n < 16 && PeekMessageA(&m, NULL, WM_QUIT + 1, WM_KEYFIRST - 1, PM_REMOVE); n++)
            if (!pump_dispatch(&m)) return;
    } else {
        for (n = 0; n < 16 && PeekMessageA(&m, NULL, 0, WM_KEYFIRST - 1, PM_REMOVE); n++)
            if (!pump_dispatch(&m)) return;
    }
    for (n = 0; n < 16 && PeekMessageA(&m, NULL, WM_KEYLAST + 1, WM_MOUSEFIRST - 1, PM_REMOVE); n++)
        if (!pump_dispatch(&m)) return;
    top = sw_pump_private() ? 0xFFFFFFFF : WM_USER - 1;
    for (n = 0; n < 16 && PeekMessageA(&m, NULL, WM_MOUSELAST + 1, top, PM_REMOVE); n++)
        if (!pump_dispatch(&m)) return;
}

/* NO KEEP-ALIVE PUMP INSIDE THE SHELL'S MODAL LOOPS.  (2026-10-03, BACKLOG P1-19)
 *
 * The garage DONE refusal ("CAN'T GET VERY FAR WITHOUT AN ENGINE") is Modal_ImageOk 0x1000b800:
 * one present, then Mouse_Update + Mouse_GetLeftClick forever, no PeekMessage of its own. Stock,
 * a deactivation (Alt+Tab, Win key, a toast) is simply not delivered until the popup closes, so
 * the shell's input gate [0x10043224] stays 1 and a click on OK still works on return. Our pump
 * from GetCursorPos / GetAsyncKeyState delivered the WM_ACTIVATEAPP 0 right there: ShellWindowProc
 * cleared the gate, Mouse_Update then returns before any USER32 call, nothing pumps again, the
 * WM_ACTIVATEAPP 1 never arrives - mouse dead for good. Measured in the lab sandbox: 2 of 2 stuck
 * (gate 0 within 0.3 s of the focus change, shell mouse frozen), I76_U32X_PUMPS=0 control 4 of 4
 * closed with the gate at 1 (lab docs\GARAGE-POPUP-STUCK.md section 7).
 *
 * So a shell caller pumps only while ShellMain's own loop is alive, i.e. its unfiltered
 * PeekMessageA(&m, NULL, 0, 0, PM_REMOVE) ran within the last 250 ms. A shell caller whose main
 * loop has gone quiet is inside a modal (Modal_*, the save screen's confirm, the ControlConfig
 * capture): stock delivers nothing there and neither do we. Ghosting is already off
 * (DisableProcessWindowsGhosting, DllMain). The keyboard-filter pump in My_PeekMessageA (name
 * entry) is untouched: there the shell's own filtered peek delivers sent messages anyway, as in
 * stock, and keeps peeking, so its gate recovers. Exe callers (the mission) are untouched.
 * I76_U32X_MODAL_PUMP=1 restores the old unconditional pump for the control run. */
static volatile DWORD g_shell_loop_tick;    /* last unfiltered PeekMessageA from i76shell (ShellMain) */

static void pump_from_poll(const void *ra)
{
    if (!sw_modalpump() && GetTickCount() - g_shell_loop_tick > 250 && caller_is_shell(ra)) {
        LOG_V("[%lu] shell poll outside ShellMain's loop (modal) - no pump\n", (unsigned long)GetTickCount());
        return;
    }
    pump_keepalive();
}

/* ---- reach the save screen from the RENDER side ----------------------------------------
 * MEASURED 2026-09-05: on the Save Bookmark screen the shell calls NONE of the USER32
 * functions this proxy exports - the instrumented log goes silent the instant that screen
 * opens, yet its clicks still work. Its modal loop drains the engine's 64-entry key ring
 * without ever pumping the message queue, so the ring is never refilled: one character lands
 * and the game wedges. Pumping from GetCursorPos / PeekMessageA / GetAsyncKeyState was tried
 * and does nothing, because none of them are called.
 *
 * But the screen DRAWS. i76shell.dll imports GDI32 BitBlt/StretchBlt (it renders into a
 * CreateDIBSection and blits), and that happens every frame while the modal loop runs. So
 * patch the shell's IAT for those two and pump there - the one side still reachable.
 *
 * Done by rewriting i76shell's import table at runtime rather than by adding another proxy
 * DLL, because u32x is already inside the process. Same technique as music-fix/strlkproxy.c.
 */
typedef BOOL (WINAPI *BitBltFn)(HDC,int,int,int,int,HDC,int,int,DWORD);
typedef BOOL (WINAPI *StretchBltFn)(HDC,int,int,int,int,HDC,int,int,int,int,DWORD);
static BitBltFn     real_BitBlt;
static StretchBltFn real_StretchBlt;
static int          g_gdiPatched;

static void pump_keepalive(void);   /* defined below */

static BOOL WINAPI My_BitBlt(HDC d,int x,int y,int w,int h,HDC s,int sx,int sy,DWORD rop)
{
    pump_keepalive();
    return real_BitBlt ? real_BitBlt(d,x,y,w,h,s,sx,sy,rop) : FALSE;
}
static BOOL WINAPI My_StretchBlt(HDC d,int x,int y,int w,int h,HDC s,int sx,int sy,int sw,int sh,DWORD rop)
{
    pump_keepalive();
    return real_StretchBlt ? real_StretchBlt(d,x,y,w,h,s,sx,sy,sw,sh,rop) : FALSE;
}

/* Redirect one named import of `mod` to `repl`; returns the original. */
static void *patch_iat(HMODULE mod, const char *dll, const char *fn, void *repl)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)mod;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    DWORD rva;
    if (!mod || dos->e_magic != IMAGE_DOS_SIGNATURE) return NULL;
    nt = (IMAGE_NT_HEADERS *)((BYTE *)mod + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return NULL;
    rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return NULL;
    for (imp = (IMAGE_IMPORT_DESCRIPTOR *)((BYTE *)mod + rva); imp->Name; imp++) {
        const char *name = (const char *)((BYTE *)mod + imp->Name);
        IMAGE_THUNK_DATA *oft, *ft;
        if (lstrcmpiA(name, dll) != 0) continue;
        oft = (IMAGE_THUNK_DATA *)((BYTE *)mod + imp->OriginalFirstThunk);
        ft  = (IMAGE_THUNK_DATA *)((BYTE *)mod + imp->FirstThunk);
        for (; oft->u1.AddressOfData; oft++, ft++) {
            IMAGE_IMPORT_BY_NAME *ibn;
            DWORD old;
            void *prev;
            if (IMAGE_SNAP_BY_ORDINAL(oft->u1.Ordinal)) continue;
            ibn = (IMAGE_IMPORT_BY_NAME *)((BYTE *)mod + oft->u1.AddressOfData);
            if (lstrcmpA((const char *)ibn->Name, fn) != 0) continue;
            if (!VirtualProtect(&ft->u1.Function, sizeof(void *), PAGE_READWRITE, &old)) return NULL;
            prev = (void *)ft->u1.Function;
            ft->u1.Function = (ULONG_PTR)repl;
            VirtualProtect(&ft->u1.Function, sizeof(void *), old, &old);
            return prev;
        }
    }
    return NULL;
}

/* Lazy: i76shell.dll is not necessarily loaded when u32x's DllMain runs. Called from the
 * hooks below, so it lands as soon as anything at all goes through this proxy. */
/* THE PER-FRAME CALL that actually reaches the save screen.
 *
 * The GDI hooks above land but are never called: in -glide mode the shell's
 * BitBlt/StretchBlt imports are the software/VESA fallback and stay cold (verified -
 * the patch resolved real addresses and neither wrapper ever ran). The live chain is
 * i76.exe -> ZGLIDE.DLL -> glide2x.dll, and ZGLIDE calls grBufferSwap to present each
 * frame. The Save Bookmark screen blinks its text caret, so it is still presenting
 * while its modal loop spins - which makes this the one reachable place that runs when
 * nothing else we can hook does. */
typedef void (WINAPI *grBufferSwapFn)(DWORD);
static grBufferSwapFn real_grBufferSwap;

static void WINAPI My_grBufferSwap(DWORD interval)
{
    pump_keepalive();
    if (real_grBufferSwap) real_grBufferSwap(interval);
}

/* i76.exe presents the 2D shell screens with SetDIBitsToDevice - it renders into a
 * CreateDIBSection and blits the DIB to the window. The Save Bookmark screen blinks its
 * caret, so this runs while the modal loop spins. Note it is i76.exe that imports it, not
 * i76shell.dll - the shell's own GDI imports are the software/VESA fallback and stay cold,
 * which is why patching only the shell changed nothing. */
typedef int (WINAPI *SetDIBitsToDeviceFn)(HDC,int,int,DWORD,DWORD,int,int,UINT,UINT,
                                          const void *,const BITMAPINFO *,UINT);
static SetDIBitsToDeviceFn real_SetDIBitsToDevice;

static int WINAPI My_SetDIBitsToDevice(HDC dc,int x,int y,DWORD w,DWORD h,int sx,int sy,
                                       UINT start,UINT lines,const void *bits,
                                       const BITMAPINFO *bi,UINT use)
{
    BUMP(c_dib);
    pump_keepalive();
    return real_SetDIBitsToDevice
        ? real_SetDIBitsToDevice(dc,x,y,w,h,sx,sy,start,lines,bits,bi,use) : 0;
}

#ifdef U32X_LOG
typedef BOOL (WINAPI *TextOutFn)(HDC, int, int, LPCSTR, int);
static TextOutFn real_TextOutA;
static BOOL WINAPI My_TextOutA(HDC dc, int x, int y, LPCSTR str, int n);
#endif

static void ensure_gdi_patched(void)
{
    HMODULE sh, zg;
    if (g_gdiPatched) return;
    if (!sw_iat()) { g_gdiPatched = 1; return; }
    sh = GetModuleHandleA("i76shell.dll");
    zg = GetModuleHandleA("ZGLIDE.DLL");
    if (!sh && !zg) return;
    g_gdiPatched = 1;                       /* attempt once, even if a name is absent */
    if (sh) {
        real_BitBlt     = (BitBltFn)    patch_iat(sh, "GDI32.dll", "BitBlt",     (void *)My_BitBlt);
        real_StretchBlt = (StretchBltFn)patch_iat(sh, "GDI32.dll", "StretchBlt", (void *)My_StretchBlt);
    }
    {   /* i76.exe: the DIB blit that actually presents the shell screens */
        HMODULE ex = GetModuleHandleA(NULL);
        real_SetDIBitsToDevice = (SetDIBitsToDeviceFn)
            patch_iat(ex, "GDI32.dll", "SetDIBitsToDevice", (void *)My_SetDIBitsToDevice);
#ifdef U32X_LOG
        real_TextOutA = (TextOutFn)
            patch_iat(ex, "GDI32.dll", "TextOutA", (void *)My_TextOutA);
        LOG("patch: TextOutA=%p\n", (void *)real_TextOutA);
#endif
    }
    if (zg)
        real_grBufferSwap = (grBufferSwapFn)patch_iat(zg, "glide2x.dll", "_grBufferSwap@4",   /* DECORATED __stdcall name - the
                                                             * undecorated form is not in the
                                                             * import table and silently misses */
                                                      (void *)My_grBufferSwap);
    LOG("patch: BitBlt=%p StretchBlt=%p grBufferSwap=%p SetDIBits=%p\n", (void *)real_BitBlt, (void *)real_StretchBlt, (void *)real_grBufferSwap, (void *)real_SetDIBitsToDevice);
}

BOOL WINAPI My_GetCursorPos(LPPOINT p)
{
    const void *ra = _ReturnAddress();
    BOOL ok;

    BUMP(c_gcp);
    ok = GetCursorPos(p);

    ensure_gdi_patched();

    /* The confirm-popup poll lives here: it calls GetCursorPos forever and pumps nothing.
     * Without this the window is declared hung, gets ghosted, and can never be clicked.
     * (2026-10-03: not from a shell modal any more - pump_from_poll; ghosting is off anyway.) */
    pump_from_poll(ra);
    menu_box_record();
    menu_free_pointer();

    if (ok && p) {
        Map m;
        int shell = sw_vptr() && caller_is_shell(ra);
        if (dialog_owns_input()) {
            /* real screen coordinates, and deliberately NOT clamped */
            LOG_V("GetCursorPos dialog focused raw=(%d,%d) - pass through\n", p->x, p->y);
            vptr_tick(0);                   /* a dialog is foreground: our cursor stands down */
            return ok;
        }
        if (shell && vptr_shell_getpos(p)) {    /* A1: the reachable box -> 640x480, linearly */
            vptr_tick(0);
            return ok;
        }
        m = map_for_caller(ra);
        if (pointer_is_confined()) {
            LOG_V("GetCursorPos confined raw=(%d,%d) - pass through\n", p->x, p->y);
        } else if (m.valid) {
            LONG ux, uy;
            screen_to_logical(&m, p->x, p->y, &ux, &uy);
            LOG_V("GetCursorPos free raw=(%d,%d) -> %s=(%ld,%ld) scale=%.3f/%.3f org=(%d,%d)\n",
                  p->x, p->y, m.tag, ux, uy, m.scale_x, m.scale, m.sx, m.sy);
            p->x = ux;
            p->y = uy;
        }
        /* never hand the caller something unresolvable, so a poll loop waiting for a hit
         * can always terminate - this is what makes the freeze structurally impossible */
        p->x = clampl(p->x, 0, m.lw - 1);
        p->y = clampl(p->y, 0, m.lh - 1);
        if (shell)
            vptr_note_shell(p->x, p->y);    /* VPTR_MAP=0 / free pointer: today's value, still shown */
    }
    vptr_tick(0);
    return ok;
}

BOOL WINAPI My_SetCursorPos(int x, int y)
{
    const void *ra = _ReturnAddress();
    Map m;
    if (sw_vptr() && sw_vptr_map() && caller_is_shell(ra)) {
        RECT b;
        if (vptr_shell_box(&b) == VB_BOX) { /* A1: the inverse of vptr_shell_getpos */
            POINT s;
            vptr_ui_to_box(&b, x, y, &s);
            LOG_V("VPTR SetCursorPos shell (%d,%d) -> box (%ld,%ld)\n", x, y, s.x, s.y);
            return SetCursorPos(s.x, s.y);
        }
    }
    if (pointer_is_confined())
        return SetCursorPos(x, y);          /* dgVoodoo owns the mapping - do not remap */
    m = map_for_caller(ra);
    if (m.valid)                            /* free pointer: logical -> screen */
        return SetCursorPos(m.sx + (int)(x * m.scale_x + 0.5),
                            m.sy + (int)(y * m.scale   + 0.5));
    return SetCursorPos(x, y);
}

/* THE NAME-ENTRY LOOP POLLS THE KEYBOARD DIRECTLY.  (2026-09-05)
 *
 * Measured: on the Save Bookmark screen the shell calls NEITHER PeekMessageA nor
 * GetCursorPos - the instrumented log goes completely silent the moment that screen
 * opens. What it imports and uses instead is GetAsyncKeyState / GetKeyState, polled
 * in a loop that never services the message queue. Windows therefore declares the
 * process not responding, DWM ghosts the window, the ghost takes the input, and the
 * second keystroke never arrives. First character lands, then dead - exactly the
 * field report.
 *
 * So pump here as well. pump_keepalive() is rate-limited to ~25 Hz and skips the
 * keyboard and mouse ranges, so the shell's own polling still sees everything. */
SHORT WINAPI My_GetAsyncKeyState(int vk)
{
    BUMP(c_gaks);
    if (sw_keys())
        pump_from_poll(_ReturnAddress());   /* Mouse_Update's button reads: same rule as GetCursorPos */
    return GetAsyncKeyState(vk);
}

SHORT WINAPI My_GetKeyState(int vk)
{
    BUMP(c_gks);
    if (!sw_keys())
        return GetKeyState(vk);
#ifdef U32X_LOG
    /* gks spikes to exactly 3 per keystroke on the save screen - that is the engine
     * deciding what character a key means. Log which keys it asks about and from where. */
    {   SHORT r;
        pump_from_poll(_ReturnAddress());
        r = GetKeyState(vk);
        LOG("[%lu] GetKeyState(0x%02X) = 0x%04X\n", (unsigned long)GetTickCount(),
            (unsigned)vk, (unsigned short)r);
        log_caller("getkeystate", _ReturnAddress());
        return r;
    }
#else
    pump_from_poll(_ReturnAddress());
    return GetKeyState(vk);
#endif
}

BOOL WINAPI My_ClipCursor(const RECT *r)
{
    /* MAP A UI-SPACE CLIP ONTO THE RENDERED UI.  (2026-09-05)
     *
     * The shell calls ClipCursor(0,0,640,480) - its own coordinate space. Passing that
     * through traps the physical pointer in the top-left 640x480 of the DESKTOP, which at
     * 3440x1440 is inside the left black bar: the UI is drawn at x=760..2680, so the pointer
     * can never physically reach a button. Measured live: clip=0,0-640,480 while the SAVE
     * button sits at real (1821,1285). That is the "I have to click once to get the cursor
     * back" and "can't click YES" report, and it is why the confirm poll spins forever - the
     * click it waits for is unreachable, not merely mistimed.
     *
     * docs/SAVE-FREEZE-ROOT-CAUSE.md already specifies this behaviour for v4 ("ClipCursor now
     * always maps the UI rect onto the real on-screen content rect, so the pointer is confined
     * to the RENDERED UI instead of the physical corner") - the shipped code never did it.
     * The doc described the intent; the binary kept the old pass-through.
     *
     * So: if the caller is clipping to something that fits inside UI space, scale it onto the
     * real content rect. Anything larger is already screen-space - leave it alone, which keeps
     * windowed mode and a genuine full-screen release untouched.
     *
     * The engine's own clip is mouse_Poll 0x44b8c0: ClientToScreen(0,0)..(w-1,h-1) with
     * w,h = [0x5dcf2c]/[0x5dcf30] (measured 0,0-640,480 on 2026-09-05), so it arrives here as a
     * UI-sized rect and is mapped the same way; while the exe menu is up it goes onto the
     * frame rect instead (map_for_caller). */
    if (sw_clipmap() && r && r->left >= -1 && r->top >= -1 &&
        (r->right - r->left) <= UI_W + 1 && (r->bottom - r->top) <= UI_H + 1) {
        Map m = map_for_caller(_ReturnAddress());
        if (m.valid) {
            RECT s;
            s.left   = m.sx + (LONG)(r->left   * m.scale_x + 0.5);
            s.top    = m.sy + (LONG)(r->top    * m.scale   + 0.5);
            s.right  = m.sx + (LONG)(r->right  * m.scale_x + 0.5);
            s.bottom = m.sy + (LONG)(r->bottom * m.scale   + 0.5);
            LOG("ClipCursor UI (%ld,%ld)-(%ld,%ld) -> screen (%ld,%ld)-(%ld,%ld)\n",
                r->left, r->top, r->right, r->bottom, s.left, s.top, s.right, s.bottom);
            return ClipCursor(&s);
        }
    }
    if (r) {
        LOG("ClipCursor (%ld,%ld)-(%ld,%ld)\n", r->left, r->top, r->right, r->bottom);
    } else {
        LOG("ClipCursor RELEASE\n");
    }
    return ClipCursor(r);
}

BOOL WINAPI My_PeekMessageA(LPMSG msg, HWND hWnd, UINT lo, UINT hi, UINT remove)
{
    const void *ra = _ReturnAddress();
    BOOL ok;

    BUMP(c_peek);
    menu_box_record();                      /* the engine's loop comes through here every frame */
    menu_free_pointer();
    vptr_tick(1);                           /* A1: place / hide our cursor; touches no message */

    /* KEEP THE WINDOW ALIVE DURING TEXT ENTRY.  (2026-09-05)
     *
     * The shell's name-entry loop drains ONLY keyboard messages:
     *     PeekMessageA(&msg, NULL, WM_KEYFIRST, WM_KEYLAST, PM_REMOVE)
     * so while you are typing a bookmark name it never touches WM_PAINT, WM_TIMER,
     * or the WM_NULL that Windows' hang detection sends via SendMessageTimeout.
     * After ~5s Windows declares the app NOT RESPONDING and DWM puts a Ghost
     * window over it - and the ghost then owns the keyboard, so no further
     * keystroke ever reaches the game.
     *
     * Symptom, exactly as reported from the field: the first character appears,
     * the second one never does, and the game is wedged with a whitened window.
     * It is not a cursor problem at all - it needs no mouse to happen.
     *
     * So when we see that keyboard-only filter, pump everything ELSE first. The
     * caller still gets precisely the keyboard message it asked for; Windows just
     * stops thinking the process died. Bounded so this can never itself spin.
     */
    LOG_V("PeekMsg filter lo=0x%X hi=0x%X hwnd=%p\n", lo, hi, (void*)hWnd);
#ifdef U32X_LOG
    /* The save screen spins here at a steady 60 Hz forever while polling no input at all.
     * Log the filter twice a second, and EVERY message actually retrieved, to see whether
     * the loop is starving (never gets a message) or draining and discarding them. */
    {   static DWORD last_;
        DWORD now_ = GetTickCount();
        if (now_ - last_ >= 500) {
            last_ = now_;
            LOG("[%lu] PEEK filter lo=0x%X hi=0x%X hwnd=%p rem=%u\n",
                (unsigned long)now_, lo, hi, (void *)hWnd, remove);
        }
    }
#endif
    if (lo == WM_KEYFIRST && hi == WM_KEYLAST) {
        LOG_V("  -> keyboard-only filter, pumping\n");
#ifdef U32X_LOG
        {   static DWORD last_;
            DWORD now_ = GetTickCount();
            if (now_ - last_ >= 1000) { last_ = now_; log_caller("nameloop-peek", _ReturnAddress()); }
        }
#endif
        pump_keepalive();
    }

    if (lo == 0 && hi == 0 && caller_is_shell(ra))
        g_shell_loop_tick = GetTickCount();     /* ShellMain's frame loop is alive (pump_from_poll) */

    ok = PeekMessageA(msg, hWnd, lo, hi, remove);
    if (ok && msg && msg->message == WM_QUIT && (remove & PM_REMOVE)) {
        g_quit_held = 0;                    /* the application's own loop has its WM_QUIT */
        vptr_hide();                        /* that loop is ending (shell -> mission load, or exit) */
    }
#ifdef U32X_LOG
    if (ok && msg)
        LOG("[%lu] PEEK -> msg=0x%04X hwnd=%p wp=0x%X\n", (unsigned long)GetTickCount(),
            msg->message, (void *)msg->hwnd, (unsigned)msg->wParam);
#endif
    if (ok && msg &&
        msg->message >= WM_MOUSEFIRST && msg->message <= WM_MOUSELAST &&
        msg->message != WM_MOUSEWHEEL) {          /* wheel lParam is already screen coords */
        /* Mouse MESSAGES must follow exactly the same regime rule as GetCursorPos - menu hover
         * and clicks ride on these, so clamping them (as the clip-guard build did) pins every
         * event to x=639 and no widget ever lights up. */
        LONG cx = (short)LOWORD(msg->lParam);     /* client coords of msg->hwnd */
        LONG cy = (short)HIWORD(msg->lParam);
        HWND gw = game_window();
        RECT vb;

        /* Only the GAME's own window speaks 640x480. A modal dialog's mouse
         * messages carry ITS client coordinates and its buttons hit-test in that
         * space, so rewriting them into UI space meant no dialog button could ever
         * be hit - the overwrite prompt could be seen but never answered. */
        if (gw && msg->hwnd != gw && !IsChild(gw, msg->hwnd)) {
            LOG_V("PeekMsg 0x%04X for a non-game window - untouched\n", msg->message);
        } else if (sw_vptr() && sw_vptr_map() && caller_is_shell(ra) &&
                   vptr_shell_box(&vb) == VB_BOX) {
            /* A1: the shell's message coordinates follow the same box map as its GetCursorPos.
             * (A UI-sized box and a free pointer keep the two branches below, unchanged.) */
            POINT pt; LONG lx, ly;
            pt.x = cx; pt.y = cy;
            ClientToScreen(msg->hwnd, &pt);
            vptr_box_to_ui(&vb, VB_BOX, pt.x, pt.y, &lx, &ly);
            LOG_V("VPTR PeekMsg 0x%04X client=(%ld,%ld) -> UI=(%ld,%ld) via box (%ld,%ld)-(%ld,%ld)\n",
                  msg->message, cx, cy, lx, ly, vb.left, vb.top, vb.right, vb.bottom);
            msg->lParam = MAKELPARAM((WORD)lx, (WORD)ly);
        } else if (!pointer_is_confined()) {
            /* THE EXE MENU'S CLICK PATH (2026-10-02). WinMain's loops dispatch this message to
             * the WndProc, which in mode 0x10 hands the lParam to shell_MenuHandleMouse 0x4972d0
             * (0x404b5d / 0x404b30). That function hit-tests in the 3D FRAME's coordinates
             * after rescaling by the video-mode row, so for the engine we map into the frame
             * (map_for_caller) and pre-multiply by the inverse of its rescale. For the shell
             * nothing changes: 640x480 UI, 4:3, as before. */
            int  menu = exe_in_menu() && caller_is_exe(ra);
            Map  m    = menu ? get_menu_map() : get_map();
            if (m.valid) {
                POINT pt; LONG lx, ly;
                pt.x = cx; pt.y = cy;
                ClientToScreen(msg->hwnd, &pt);   /* -> screen, then screen -> logical */
                screen_to_logical(&m, pt.x, pt.y, &lx, &ly);
                if (menu) {
                    double rx, ry; int vm;
                    if (exe_mode_ratio(&rx, &ry, &vm)) {
                        LONG ox = lx, oy = ly;
                        lx = clampl((LONG)(lx * rx + 0.5), 0, 0x7fff);
                        ly = clampl((LONG)(ly * ry + 0.5), 0, 0x7fff);
                        LOG_V("MENU mode %d rescale inverse %.3f/%.3f: (%ld,%ld) -> (%ld,%ld)\n",
                              vm, rx, ry, ox, oy, lx, ly);
                    }
                    LOG_V("MENU PeekMsg 0x%04X client=(%ld,%ld) -> frame=(%ld,%ld) via %s %dx%d scale=%.3f/%.3f org=(%d,%d)\n",
                          msg->message, cx, cy, lx, ly, m.tag, m.lw, m.lh, m.scale_x, m.scale, m.sx, m.sy);
                } else {
                    LOG_V("PeekMsg 0x%04X free client=(%ld,%ld) -> UI=(%ld,%ld)\n",
                          msg->message, cx, cy, lx, ly);
                }
                msg->lParam = MAKELPARAM((WORD)lx, (WORD)ly);
            }
        } else if (cx < 0 || cx >= UI_W || cy < 0 || cy >= UI_H) {
            /* confined regime: coordinates are already the app's own, so only guard the
             * pathological out-of-range case so a hit-test can always resolve */
            LONG nx = clampl(cx, 0, UI_W - 1), ny = clampl(cy, 0, UI_H - 1);
            LOG_V("PeekMsg 0x%04X confined out-of-range (%ld,%ld) -> clamped (%ld,%ld)\n",
                  msg->message, cx, cy, nx, ny);
            msg->lParam = MAKELPARAM((WORD)nx, (WORD)ny);
        }
    }
    return ok;
}


/* ================= diagnostic instrument (U32X_LOG builds only) ==========================
 * Subclass the game window so we see EVERY message it actually receives, patch TextOutA so
 * we see what the shell actually draws, and sample both on a timer. Between them these
 * answer the question the hang flag could not: on the Save Bookmark screen, do input
 * messages arrive at all, does the game dispatch them, and does the screen redraw after. */
#ifdef U32X_LOG

#define MAXW 8
static HWND    g_hw[MAXW];
static WNDPROC g_op[MAXW];
static volatile LONG g_nw;

static LRESULT CALLBACK LogWndProc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    WNDPROC orig = NULL;
    LONG i, n = g_nw;
    for (i = 0; i < n && i < MAXW; i++) if (g_hw[i] == h) { orig = g_op[i]; break; }

    BUMP(c_wproc);
    if (m == WM_KEYDOWN || m == WM_KEYUP || m == WM_SYSKEYDOWN || m == WM_SYSKEYUP) {
        BUMP(c_key);
        LOG("[%lu] WNDPROC key   msg=0x%04X vk=0x%02X\n",
            (unsigned long)GetTickCount(), m, (unsigned)w);
    } else if (m == WM_CHAR || m == WM_SYSCHAR) {
        BUMP(c_char);
        LOG("[%lu] WNDPROC CHAR  0x%02X\n", (unsigned long)GetTickCount(), (unsigned)w);
    } else if (m >= WM_MOUSEFIRST && m <= WM_MOUSELAST && m != WM_MOUSEMOVE) {
        BUMP(c_mouse);
        LOG("[%lu] WNDPROC mouse msg=0x%04X at (%d,%d)\n", (unsigned long)GetTickCount(),
            m, (int)(short)LOWORD(l), (int)(short)HIWORD(l));
    } else if (m == WM_ACTIVATE || m == WM_ACTIVATEAPP ||
               m == WM_SETFOCUS || m == WM_KILLFOCUS || m == WM_NCACTIVATE) {
        LOG("[%lu] WNDPROC focus msg=0x%04X wp=0x%X\n",
            (unsigned long)GetTickCount(), m, (unsigned)w);
    }
    return orig ? CallWindowProcA(orig, h, m, w, l) : DefWindowProcA(h, m, w, l);
}

HWND WINAPI My_CreateWindowExA(DWORD ex, LPCSTR cls, LPCSTR nm, DWORD st, int x, int y,
                               int cw, int ch, HWND par, HMENU mn, HINSTANCE in, LPVOID pm)
{
    HWND h = CreateWindowExA(ex, cls, nm, st, x, y, cw, ch, par, mn, in, pm);
    if (h) {
        LONG i = InterlockedIncrement((LONG volatile *)&g_nw) - 1;
        if (i < MAXW) {
            g_hw[i] = h;
            g_op[i] = (WNDPROC)(LONG_PTR)SetWindowLongA(h, GWL_WNDPROC,
                                                        (LONG)(LONG_PTR)LogWndProc);
            LOG("[%lu] subclassed hwnd=%p orig=%p\n",
                (unsigned long)GetTickCount(), (void *)h, (void *)g_op[i]);
        }
    }
    return h;
}

LRESULT WINAPI My_DispatchMessageA(const MSG *m) { BUMP(c_disp); return DispatchMessageA(m); }
BOOL    WINAPI My_TranslateMessage(const MSG *m) { BUMP(c_tran); return TranslateMessage(m); }
UINT    WINAPI My_MapVirtualKeyA(UINT c, UINT t) { BUMP(c_mvk);  return MapVirtualKeyA(c, t); }
HWND    WINAPI My_GetFocus(void)                 { BUMP(c_focus); return GetFocus(); }

static BOOL WINAPI My_TextOutA(HDC dc, int x, int y, LPCSTR str, int n)
{
    /* Dedupe against the last 16 distinct strings: the screen redraws the same labels every
     * frame, and only a CHANGE - a typed character landing, a field updating - is evidence. */
    static char seen[16][64];
    static int  slot;
    BUMP(c_text);
    if (str && n > 0) {
        char buf[64];
        int len = n < 63 ? n : 63, i, dup = 0;
        for (i = 0; i < len; i++) buf[i] = str[i];
        buf[len] = 0;
        for (i = 0; i < 16; i++) if (lstrcmpA(seen[i], buf) == 0) { dup = 1; break; }
        if (!dup) {
            lstrcpynA(seen[slot], buf, sizeof seen[0]);
            slot = (slot + 1) & 15;
            LOG_T("[%lu] TextOut (%d,%d) [%s]\n", (unsigned long)GetTickCount(), x, y, buf);
        }
    }
    return real_TextOutA ? real_TextOutA(dc, x, y, str, n) : FALSE;
}

/* ---- the shell's 64-entry key ring ------------------------------------------------------
 * Found by disassembling the save screen's key handler (I76SHELL.DLL +0x1D732):
 *
 *     mov  eax, [0x100D2160]                  ; write index
 *     mov  word [eax*2 + 0x100F6420], si      ; ring[write++] = key | modifier bits
 *     inc  eax                                ;   0x100 = Ctrl, 0x200 = Shift, 0x400 = Alt
 *     cmp  eax, 0x40                          ; 64 entries, wraps
 *     ...  cmp eax, [0x100D215C]              ; read index - if it collides, drop the oldest
 *
 * Keys are PRODUCED into this ring by the window path and CONSUMED by whatever screen is
 * up. Watching both indices separates the two halves of "typing does nothing": a write
 * index that does not move means the keystroke never became a ring entry; a write index
 * that moves while the read index sits still means the screen is not draining it. */
#define SHELL_WR 0xD2160
#define SHELL_RD 0xD215C
#define SHELL_RING 0xF6420

static void log_keyring(void)
{
    static DWORD pw = 0xFFFFFFFF, pr = 0xFFFFFFFF;
    HMODULE sh = GetModuleHandleA("i76shell.dll");
    DWORD wr, rd;
    if (!sh) return;
    wr = *(volatile DWORD *)((BYTE *)sh + SHELL_WR);
    rd = *(volatile DWORD *)((BYTE *)sh + SHELL_RD);
    if (wr == pw && rd == pr) return;
    {
        volatile WORD *ring = (WORD *)((BYTE *)sh + SHELL_RING);
        char buf[400];
        int i, n = 0;
        n += wsprintfA(buf + n, "[%lu] KEYRING wr=%lu rd=%lu pending=%ld |",
                       (unsigned long)GetTickCount(), wr, rd,
                       (long)((wr - rd) & 0x3F));
        for (i = 0; i < 12 && i < 0x40; i++)
            n += wsprintfA(buf + n, " %04X", ring[i]);
        LOG("%s\n", buf);
        pw = wr; pr = rd;
    }
}

static DWORD WINAPI census_thread(LPVOID unused)
{
    LONG prev[14];
    int i;
    (void)unused;
    for (i = 0; i < 14; i++) prev[i] = 0;
    for (;;) {
        LONG v[14];
        HWND gw;
        /* sub-sample the ring at 50 Hz so a keystroke is never missed between censuses */
        for (i = 0; i < 10; i++) { Sleep(50); log_keyring(); }
        v[0]=c_gcp;  v[1]=c_peek;  v[2]=c_gaks;  v[3]=c_gks;   v[4]=c_disp;
        v[5]=c_tran; v[6]=c_mvk;   v[7]=c_focus; v[8]=c_dib;   v[9]=c_text;
        v[10]=c_wproc; v[11]=c_key; v[12]=c_mouse; v[13]=c_char;
        gw = FindWindowA(NULL, "Interstate '76 Gold Edition");
        LOG("[%lu] CENSUS gcp=%ld peek=%ld gaks=%ld gks=%ld disp=%ld tran=%ld mvk=%ld "
            "focus=%ld dib=%ld text=%ld wproc=%ld key=%ld mouse=%ld char=%ld hung=%d\n",
            (unsigned long)GetTickCount(),
            v[0]-prev[0], v[1]-prev[1], v[2]-prev[2], v[3]-prev[3], v[4]-prev[4],
            v[5]-prev[5], v[6]-prev[6], v[7]-prev[7], v[8]-prev[8], v[9]-prev[9],
            v[10]-prev[10], v[11]-prev[11], v[12]-prev[12], v[13]-prev[13],
            gw ? (int)IsHungAppWindow(gw) : -1);
        for (i = 0; i < 14; i++) prev[i] = v[i];
    }
}
#endif /* U32X_LOG */

#ifdef U32X_LOG
/* i76shell imports ToAscii - the classic "what character is this key" call. If the name
 * field is fed through it, this fires once per keystroke and its return value says whether
 * a character was produced at all. */
int WINAPI My_ToAscii(UINT vk, UINT scan, const BYTE *state, LPWORD out, UINT flags)
{
    int r = ToAscii(vk, scan, state, out, flags);
    LOG("[%lu] ToAscii vk=0x%02X scan=0x%02X -> %d char=0x%04X\n",
        (unsigned long)GetTickCount(), vk, scan, r, out ? *out : 0);
    log_caller("toascii", _ReturnAddress());
    return r;
}
#endif

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_inst = inst;
        DisableThreadLibraryCalls(inst);
        LOG("=== u32x attached ===\n");

        /* STOP DWM GHOSTING THIS PROCESS.  (2026-09-06)
         *
         * Measured cause of the Save Bookmark wedge, from a per-call census in this DLL.
         * The order is the opposite of what it looks like from the outside:
         *
         *   t+0.0s  SAVE BOOKMARK clicked; the screen is fine and the engine polls
         *           normally - GetCursorPos 60/s, GetAsyncKeyState 180/s.
         *   t+5.9s  IsHungAppWindow goes true and the window is deactivated by something
         *           nobody clicked:  WM_NCACTIVATE 0 / WM_ACTIVATE 0 / WM_ACTIVATEAPP 0 /
         *           WM_KILLFOCUS. That is DWM replacing the window with a Ghost.
         *   after   the engine collapses to one call, sixty times a second, forever:
         *           PeekMessageA(&msg, NULL, WM_KEYFIRST, WM_KEYLAST, PM_REMOVE),
         *           polling nothing - and never receiving a key, because the ghost owns
         *           the input now.
         *
         * So the starving keyboard peek is the CONSEQUENCE of losing activation, not the
         * cause, and pumping harder does not help - the engine was already pumping 60/s
         * when Windows ghosted it. What actually has to be prevented is the ghosting.
         * That is what this call is for; it is the documented, per-process switch.
         *
         * Field report this explains exactly: one character lands and then nothing, and
         * clicking buys one more character - because the click re-activates the real
         * window for a moment. */
        {
            HMODULE u = GetModuleHandleA("user32.dll");
            typedef void (WINAPI *DPWGFn)(void);
            DPWGFn dpwg = u ? (DPWGFn)GetProcAddress(u, "DisableProcessWindowsGhosting")
                            : NULL;
            if (dpwg) { dpwg(); LOG("ghosting disabled\n"); }
            else       LOG("DisableProcessWindowsGhosting NOT FOUND\n");
        }
#ifdef U32X_LOG
        {   DWORD tid;
            HANDLE th = CreateThread(NULL, 0, census_thread, NULL, 0, &tid);
            if (th) CloseHandle(th); }
#endif
    }
    return TRUE;
}
