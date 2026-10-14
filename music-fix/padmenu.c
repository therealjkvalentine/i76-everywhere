/* ===========================================================================
 * PAD MENU  (I76_PAD_MENU=1; off by default)
 * ===========================================================================
 * Included from strlkproxy.c right after cursormap.c (it uses cm_window / cm_map) and before hook_LoadLibraryA,
 * which calls pad_menu_attach.
 *
 * THE PROBLEM (owner, Steam Deck docked to a TV, 2026-10-13): "the controller can't be used to navigate the menu".
 * The shell (i76shell.dll: main menu, TRIP, bookmarks, garage, save screen) and the exe's in-mission Esc menu are
 * point-and-click 640x480 pages. Handheld, the Deck's right trackpad is a mouse (Steam layout v10); an external pad
 * on a TV has no trackpad, and the shared pad layer (i76-remap.ahk) only clicks where the pointer already is
 * (A = click + Enter) - nothing moves the pointer.
 *
 * THE FIX. A thread polls XInput (every slot, merged: docked, the Deck's own controller and the TV pad are both
 * connected and either may be slot 0) every 8 ms, and ONLY while the game shows a menu:
 *
 *    game state [0x4c2164] == 6            the shell
 *    game state 5 and [0x4fe534] == 0x10   the exe's Esc / mission-over menu (mouse via WndProc -> 0x4972d0)
 *    and no other application's window is in front
 *
 * it moves the real pointer, exactly as a mouse or the trackpad would:
 *
 *    left stick   pointer, speed ~ deflection^2, ramping up over 0.6 s of continuous push
 *    D-pad        pointer, slow first (fine placement), accelerating while held
 *    A            left button (down on press, up on release: drags work) - left to the pad layer when it runs
 *    B            Esc (back)
 *    Start        Enter (closes the shell's OK popups when the F7 shell patch is installed)
 *
 * The position is kept in 640x480 UI units. v3 (2026-10-14, owner on the Deck: "sometimes it doesn't move the cursor
 * and it doesn't seem to move it right over the correct mouse coordinates"): v1/v2 only warped the OS pointer
 * (SetCursorPos) and let the game read it back through the cursor map. Under gamescope that is two round trips through
 * a compositor that may not honour an app's pointer warp, and v2 resynchronised from whatever GetCursorPos returned
 * whenever it differed from the warp target by > 2 px - so a warp that did not land (or landed late) dragged the pad
 * position straight back: no movement. v3 makes the pad the source of truth while it drives:
 *
 *    - the pad position (UI units) is published to cursormap.c (g_cm_pad_own / g_cm_pad_xy), whose GetCursorPos,
 *      GetCursorInfo and PeekMessageA mouse-lParam slots in i76.exe / i76shell.dll (and dgVoodoo's cursor reads with
 *      I76_CURSOR_MAP_DGV) return it - the hit-test and any cursor the game or dgVoodoo draws agree with the pad,
 *      whether or not the OS pointer followed. Clicks (ours through SendInput, or the pad layer's AHK Click) arrive as
 *      mouse messages whose lParam is rewritten to the same point.
 *    - the OS pointer is still warped to the same spot (cm_map: client rect, stretched or ar) for the visible arrow.
 *      Each warp is read back on the next poll and counted (landed / not landed: "warp" lines in mciproxy.log).
 *    - the pointer goes back to the OS only when it moves by something other than our warp (the trackpad, a mouse:
 *      the read-back position changes between two polls without a warp in between) or the game calls SetCursorPos.
 *
 * Needs I76_CURSOR_MAP (the slots live there); without it v3 falls back to warping only (logged). Buttons go in
 * through SendInput (the path the pad layer's AHK Click already uses under Proton). In a mission outside a menu and
 * with the switch unset, the thread does nothing (unset: no thread, no XInput load).
 *
 * GATING (v3): shell (state 6) and Esc menu (mode 0x10) as before; plus "a page of the exe that is not driving"
 * (state 5, mode not 1 driving / 0x20 movie / 0): the Esc menu's exit dialog takes the mode out of 0x10 (lab
 * MOUSE-ESC-MENU-AND-SAVE-SCREEN.md), so v2 stopped moving the pointer exactly there. Only the pointer and A work on
 * those pages; B / Start stay shell + Esc menu. Another process's window in front stops it only after 400 ms, so a
 * passing overlay or tooltip does not cut a push. Every activation change logs state, mode and the foreground owner.
 *
 * WITH THE PAD LAYER (i76-remap.ahk; its hidden window class "AutoHotkey" is looked up): AHK already turns A into
 * click + Enter, so the proxy does not click as well (a double click). AHK also turns the D-pad into H / I / N / M,
 * Start into M and B into Tab - keys that would type into the bookmark name on the save screen. While that pad
 * button is held (and 150 ms after) those key messages are turned into WM_NULL on their way into the game (the
 * exe's and the shell's PeekMessageA slots, chained after cursormap). A real keyboard is unaffected.
 *
 * THE OK POPUPS. Modal_ImageOk / Modal_Ok spin on Mouse_Update + Mouse_GetLeftClick without presenting a frame, so
 * the pencil dgVoodoo draws freezes where it was (lab GARAGE-POPUP-STUCK.md); the pointer still moves and A still
 * hits OK. Start (Enter) closes them only with the F7 shell patch (tools/patch-shell-f7.py).
 *
 *    I76_PAD_MENU_SPEED=<UI px/s>   top pointer speed, default 700 (640 px in about a second)
 *    I76_PAD_MENU_LOG=1             activation changes, the first 40 actions, warp read-backs in mciproxy.log
 *    I76_PAD_MENU_AHK=0|1           force "pad layer present" off / on (default: detected by window class)
 *    I76_PAD_MENU_PAGES=0           shell + Esc menu only (the v2 gate; default 1 = also the exe's other non-driving pages)
 *    I76_PAD_MENU_VIRTUAL=0         the v2 behaviour: warp the OS pointer only, the game reads it back (A/B test)
 *
 * STEAM INPUT: the left stick must be a plain stick (XInput "joystick_move", as in deck/controller_neptune_i76_pad.vdf),
 * not "Joystick Mouse" / "As Mouse": a stick that is also a Steam mouse moves the OS pointer at the same time, which
 * v3 reads as "something else moved it" and hands the pointer back on every poll. The right trackpad may stay a mouse.
 */
typedef struct { WORD wButtons; BYTE bLeftTrigger, bRightTrigger; SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY; } PmPad;
typedef struct { DWORD dwPacketNumber; PmPad Gamepad; } PmState;
static DWORD (WINAPI *p_pm_XInputGetState)(DWORD, PmState *);
static BOOL  (WINAPI *p_pm_SetCursorPos)(int, int);
static BOOL  (WINAPI *p_pm_GetCursorPos)(LPPOINT);
static BOOL  (WINAPI *p_pm_PeekExe)(LPMSG, HWND, UINT, UINT, UINT);
static BOOL  (WINAPI *p_pm_PeekShell)(LPMSG, HWND, UINT, UINT, UINT);
static int   g_pm_on, g_pm_log, g_pm_ahk_force = -1, g_pm_nlog, g_pm_pages = 1, g_pm_virtual = 1;
static float g_pm_speed = 700.0f;
static volatile LONG g_pm_active;                       /* the thread's last verdict: a menu is up */
static volatile DWORD g_pm_held_until[4];               /* filter windows: 0 dpad, 1 start, 2 B (GetTickCount) */

#define PM_DPAD_U 0x0001
#define PM_DPAD_D 0x0002
#define PM_DPAD_L 0x0004
#define PM_DPAD_R 0x0008
#define PM_START  0x0010
#define PM_A      0x1000
#define PM_B      0x2000

static void pm_logf(const char *what, long a, long b) {
    if (g_pm_log && g_pm_nlog < 40) { g_pm_nlog++; mlog("  pad-menu: %s (%ld,%ld)", what, a, b); }
}
/* 1 shell, 2 Esc menu, 3 another non-driving page of the exe (the exit dialog, ...): pointer + A only */
static int pm_menu_up(void) {
    int st = *(volatile int *)0x004c2164, mode;
    if (st == 6) return 1;
    if (st != 5) return 0;
    mode = *(volatile int *)0x004fe534;
    if (mode == 0x10) return 2;
    if (g_pm_pages && mode != 1 && mode != 0x20 && mode != 0) return 3;
    return 0;
}
static int pm_ahk(void) {
    if (g_pm_ahk_force >= 0) return g_pm_ahk_force;
    return FindWindowA("AutoHotkey", NULL) != NULL;
}
static void pm_mouse(DWORD flags) {
    INPUT in; ZeroMemory(&in, sizeof in);
    in.type = INPUT_MOUSE; in.mi.dwFlags = flags;
    SendInput(1, &in, sizeof in);
}
static void pm_key(WORD vk, int up) {
    INPUT in; ZeroMemory(&in, sizeof in);
    in.type = INPUT_KEYBOARD; in.ki.wVk = vk; in.ki.wScan = (WORD)MapVirtualKeyA(vk, 0);
    in.ki.dwFlags = up ? KEYEVENTF_KEYUP : 0;
    SendInput(1, &in, sizeof in);
}
/* UI (640x480) <-> screen through cursormap's mapping; without a window yet: identity */
static void pm_ui_to_screen(float ux, float uy, POINT *s) {
    CmMap m = cm_map();
    if (m.on) { s->x = m.ox + (LONG)(ux * m.kx + 0.5); s->y = m.oy + (LONG)(uy * m.ky + 0.5); }
    else { s->x = (LONG)(ux + 0.5f); s->y = (LONG)(uy + 0.5f); }
}
static void pm_screen_to_ui(POINT s, float *ux, float *uy) {
    CmMap m = cm_map();
    if (m.on) { *ux = (float)((s.x - m.ox) / m.kx); *uy = (float)((s.y - m.oy) / m.ky); }
    else { *ux = (float)s.x; *uy = (float)s.y; }
    if (*ux < 0) *ux = 0; if (*ux > 639) *ux = 639; if (*uy < 0) *uy = 0; if (*uy > 479) *uy = 479;
}
static float pm_axis(SHORT v) {                          /* deadzone 7849 (XInput's), then squared, signed, -1..1 */
    float a = (float)v, dz = 7849.0f, f;
    if (a > -dz && a < dz) return 0.0f;
    f = ((a < 0 ? -a : a) - dz) / (32767.0f - dz); if (f > 1.0f) f = 1.0f;
    f *= f;
    return a < 0 ? -f : f;
}

static void pm_publish(float ux, float uy) {            /* the pad position the game reads (cursormap.c) */
    InterlockedExchange(&g_cm_pad_xy, MAKELONG((WORD)(int)(ux + 0.5f), (WORD)(int)(uy + 0.5f)));
}
static int pm_far(POINT a, POINT b) { return a.x - b.x > 2 || b.x - a.x > 2 || a.y - b.y > 2 || b.y - a.y > 2; }

static DWORD WINAPI pm_thread(LPVOID arg) {
    float ux = 320.0f, uy = 240.0f, ramp = 0.0f, dramp = 0.0f;
    POINT seen = { -100000, -100000 };       /* the OS pointer as read on the previous poll */
    POINT target = { -100000, -100000 };     /* where our last warp put it */
    int warped = 0;                          /* a warp was issued since the previous poll */
    LONG w_n = 0, w_ok = 0, w_miss = 0, ext_n = 0, w_logged = 0;
    WORD prev = 0; int was = 0, a_down = 0, a_ours = 0;
    DWORD t0 = GetTickCount(), fg_other_since = 0;
    const char *names[3] = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
    HMODULE x = NULL; int k;
    (void)arg;
    /* loaded here, not in DllMain: no LoadLibrary under the loader lock */
    for (k = 0; k < 3 && !x; k++) x = LoadLibraryA(names[k]);
    if (x) p_pm_XInputGetState = (DWORD (WINAPI *)(DWORD, PmState *))GetProcAddress(x, "XInputGetState");
    mlog("  pad-menu: XInput %s", p_pm_XInputGetState ? names[k - 1] : "NOT found (xinput1_4 / 1_3 / 9_1_0) - pad menu idle");
    if (!p_pm_XInputGetState) return 0;
    for (;;) {
        DWORD now = GetTickCount(), dtms = now - t0, i, fgpid = 0;
        WORD btn = 0; int sx = 0, sy = 0, connected = 0, up, fg_ok;
        float lx = 0.0f, ly = 0.0f, dt;
        HWND h, fg;
        t0 = now;
        dt = dtms > 100 ? 0.1f : dtms / 1000.0f;
        for (i = 0; i < 4; i++) {
            PmState s;
            if (p_pm_XInputGetState(i, &s) != 0) continue;
            connected++;
            btn |= s.Gamepad.wButtons;
            sx += s.Gamepad.sThumbLX; sy += s.Gamepad.sThumbLY;
        }
        if (sx > 32767) sx = 32767; if (sx < -32768) sx = -32768;
        if (sy > 32767) sy = 32767; if (sy < -32768) sy = -32768;
        h = cm_window();
        /* no foreground window known (can happen under a compositor) counts as ours; another process's window in front
           stops the pad only after 400 ms, so a passing overlay / tooltip does not cut a push */
        fg = GetForegroundWindow();
        if (fg) GetWindowThreadProcessId(fg, &fgpid);
        if (!fg || fgpid == GetCurrentProcessId()) { fg_ok = 1; fg_other_since = 0; }
        else { if (!fg_other_since) fg_other_since = now ? now : 1; fg_ok = (now - fg_other_since) < 400; }
        up = connected && h && fg_ok ? pm_menu_up() : 0;
        if (up != was) {
            if (g_pm_log) {
                char cls[64] = "";
                if (fg && !fg_ok) GetClassNameA(fg, cls, sizeof cls);
                mlog("  pad-menu: %s (game state %d, mode 0x%x, %d pad(s), window %s, foreground %s%s%s; warps %ld: landed %ld, "
                     "not landed %ld; pointer moved by something else %ld)",
                     up == 1 ? "shell - pointer on the pad" : up == 2 ? "Esc menu - pointer on the pad" :
                     up == 3 ? "exe page (not driving) - pointer on the pad, A only" : "off",
                     *(volatile int *)0x004c2164, *(volatile int *)0x004fe534, connected, h ? "found" : "NOT found",
                     !fg ? "none" : fgpid == GetCurrentProcessId() ? "the game" : "ANOTHER PROCESS", cls[0] ? " class " : "", cls,
                     w_n, w_ok, w_miss, ext_n);
            }
            if (!up && a_down && a_ours) pm_mouse(MOUSEEVENTF_LEFTUP);   /* never leave the button down in a mission */
            if (!up) { a_down = a_ours = 0; InterlockedExchange(&g_cm_pad_own, 0); }
            was = up; warped = 0; seen.x = -100000;
        }
        InterlockedExchange(&g_pm_active, up);
        if (up) {
            POINT cur; int moved = 0, have = p_pm_GetCursorPos(&cur) != 0;
            if (have) {
                if (seen.x == -100000) {                            /* first poll on this page: start where the OS pointer is */
                    if (!g_cm_pad_own) pm_screen_to_ui(cur, &ux, &uy);
                } else if (warped) {                                /* read back our own warp: landed or not */
                    if (pm_far(cur, target)) {
                        w_miss++;
                        if (g_pm_log && w_logged < 6) { w_logged++;
                            mlog("  pad-menu: warp to (%ld,%ld) read back (%ld,%ld) - not landed (%ld of %ld); the game reads the pad position anyway",
                                 target.x, target.y, cur.x, cur.y, w_miss, w_n); }
                    } else w_ok++;
                } else if (pm_far(cur, seen)) {                     /* moved by something else: trackpad, mouse, the game */
                    ext_n++;
                    InterlockedExchange(&g_cm_pad_own, 0);
                    pm_screen_to_ui(cur, &ux, &uy);
                }
                seen = cur;
            }
            warped = 0;
            lx = pm_axis((SHORT)sx); ly = pm_axis((SHORT)sy);
            if (lx != 0.0f || ly != 0.0f) {
                ramp += dt / 0.6f; if (ramp > 1.0f) ramp = 1.0f;
                ux += lx * g_pm_speed * (0.3f + 0.7f * ramp) * dt;
                uy -= ly * g_pm_speed * (0.3f + 0.7f * ramp) * dt;    /* stick up = positive Y = screen up */
                moved = 1;
            } else ramp = 0.0f;
            if (btn & (PM_DPAD_U | PM_DPAD_D | PM_DPAD_L | PM_DPAD_R)) {
                float v, dx = 0.0f, dy = 0.0f;
                if (!(prev & (PM_DPAD_U | PM_DPAD_D | PM_DPAD_L | PM_DPAD_R))) {   /* a tap moves 2 UI px */
                    dramp = 0.0f;
                    dx = (btn & PM_DPAD_R ? 2.0f : 0.0f) - (btn & PM_DPAD_L ? 2.0f : 0.0f);
                    dy = (btn & PM_DPAD_D ? 2.0f : 0.0f) - (btn & PM_DPAD_U ? 2.0f : 0.0f);
                } else {
                    dramp += dt / 0.8f; if (dramp > 1.0f) dramp = 1.0f;
                    v = g_pm_speed * (0.06f + 0.94f * dramp * dramp) * dt;
                    dx = (btn & PM_DPAD_R ? v : 0.0f) - (btn & PM_DPAD_L ? v : 0.0f);
                    dy = (btn & PM_DPAD_D ? v : 0.0f) - (btn & PM_DPAD_U ? v : 0.0f);
                }
                ux += dx; uy += dy; moved = 1;
                g_pm_held_until[0] = now + 150;
            }
            if (moved) {
                POINT s;
                if (ux < 0) ux = 0; if (ux > 639) ux = 639; if (uy < 0) uy = 0; if (uy > 479) uy = 479;
                if (g_pm_virtual) {
                    pm_publish(ux, uy);
                    if (!g_cm_pad_own) { InterlockedExchange(&g_cm_pad_own, 1); pm_logf("pad takes the pointer at UI", (long)ux, (long)uy); }
                }
                pm_ui_to_screen(ux, uy, &s);
                if (s.x != target.x || s.y != target.y || (have && pm_far(cur, s))) {
                    p_pm_SetCursorPos(s.x, s.y); target = s; warped = 1; w_n++;
                }
            }
            /* A: the left button, unless the pad layer clicks already (its click lands at the pad position too:
               cursormap rewrites the button message's lParam while the pad owns the pointer) */
            if ((btn & PM_A) && !(prev & PM_A)) {
                a_down = 1; a_ours = !pm_ahk();
                if (a_ours) { pm_mouse(MOUSEEVENTF_LEFTDOWN); pm_logf("A: left down at UI", (long)ux, (long)uy); }
                else pm_logf("A: pad layer clicks (AHK) at UI", (long)ux, (long)uy);
            }
            if (!(btn & PM_A) && a_down) { if (a_ours) pm_mouse(MOUSEEVENTF_LEFTUP); a_down = a_ours = 0; }
            if (up != 3) {                                          /* B / Start: shell and Esc menu only */
                if (btn & PM_B) g_pm_held_until[2] = now + 150;
                if ((btn & PM_B) && !(prev & PM_B)) { pm_key(VK_ESCAPE, 0); pm_key(VK_ESCAPE, 1); pm_logf("B: Esc", up, 0); }
                if (btn & PM_START) g_pm_held_until[1] = now + 150;
                if ((btn & PM_START) && !(prev & PM_START)) { pm_key(VK_RETURN, 0); pm_key(VK_RETURN, 1); pm_logf("Start: Enter", up, 0); }
            }
        }
        prev = btn;
        Sleep(connected ? 8 : 250);
    }
    return 0;
}

/* The pad layer's keys for the pad buttons the menu now uses: WM_NULL while that button is held (and 150 ms after). */
static void pm_filter(LPMSG msg) {
    DWORD now; WPARAM vk; int hit = 0;
    if (!msg || !g_pm_active) return;
    if (msg->message != WM_KEYDOWN && msg->message != WM_KEYUP && msg->message != WM_CHAR) return;
    vk = msg->wParam;
    if (msg->message == WM_CHAR && vk >= 'a' && vk <= 'z') vk -= 'a' - 'A';
    now = GetTickCount();
#define PM_WIN(k) ((LONG)(g_pm_held_until[k] - now) > 0)
    if (vk == 'H' || vk == 'I' || vk == 'N') hit = PM_WIN(0);           /* D-pad up / down / left */
    else if (vk == 'M') hit = PM_WIN(0) || PM_WIN(1);                     /* D-pad right, Start */
    else if (vk == VK_TAB) hit = PM_WIN(2);                               /* B (VK_TAB is also Tab's WM_CHAR) */
#undef PM_WIN
    if (hit && pm_ahk()) msg->message = WM_NULL;
}
static BOOL WINAPI pm_PeekExe(LPMSG msg, HWND hw, UINT lo, UINT hi, UINT rm) {
    BOOL ok = p_pm_PeekExe(msg, hw, lo, hi, rm);
    if (ok) pm_filter(msg);
    return ok;
}
static BOOL WINAPI pm_PeekShell(LPMSG msg, HWND hw, UINT lo, UINT hi, UINT rm) {
    BOOL ok = p_pm_PeekShell(msg, hw, lo, hi, rm);
    if (ok) pm_filter(msg);
    return ok;
}

/* from hook_LoadLibraryA, after cursor_map_attach (so the chain is pad filter -> cursor map -> user32) */
static void pad_menu_attach(HMODULE m, const char *b) {
    static int shell_done;
    if (!g_pm_on || shell_done || _strnicmp(b, "i76shell", 8) != 0) return;
    shell_done = 1;
    p_pm_PeekShell = (BOOL (WINAPI *)(LPMSG, HWND, UINT, UINT, UINT))patch_iat(m, "USER32.dll", "PeekMessageA", pm_PeekShell);
    mlog("  pad-menu: i76shell.dll PeekMessageA %s", p_pm_PeekShell ? "chained (pad-layer key filter)" : "NOT found");
}
static void apply_pad_menu(void) {
    char v[16]; DWORD n = GetEnvironmentVariableA("I76_PAD_MENU", v, sizeof(v));
    HMODULE u = GetModuleHandleA("user32.dll"), exe = GetModuleHandleA(NULL), sh;
    HANDLE th; int virt_req;
    if (n == 0 || n >= sizeof(v) || v[0] == '0') return;
    {   char c[16]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_SPEED", c, sizeof(c));
        if (k && k < sizeof(c)) { int s = atoi(c); if (s >= 50 && s <= 5000) g_pm_speed = (float)s; } }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_LOG", c, sizeof(c)); g_pm_log = (k && k < sizeof(c) && c[0] == '1'); }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_AHK", c, sizeof(c));
        if (k && k < sizeof(c)) g_pm_ahk_force = (c[0] == '1') ? 1 : 0; }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_PAGES", c, sizeof(c)); if (k && k < sizeof(c) && c[0] == '0') g_pm_pages = 0; }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_VIRTUAL", c, sizeof(c)); if (k && k < sizeof(c) && c[0] == '0') g_pm_virtual = 0; }
    p_pm_SetCursorPos = (BOOL (WINAPI *)(int, int))GetProcAddress(u, "SetCursorPos");     /* the real ones: never a hook */
    p_pm_GetCursorPos = (BOOL (WINAPI *)(LPPOINT))GetProcAddress(u, "GetCursorPos");
    g_pm_on = 1;
    p_pm_PeekExe = (BOOL (WINAPI *)(LPMSG, HWND, UINT, UINT, UINT))patch_iat(exe, "USER32.dll", "PeekMessageA", pm_PeekExe);
    if ((sh = GetModuleHandleA("i76shell.dll")) != NULL) pad_menu_attach(sh, "i76shell.dll");
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(exe, "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    virt_req = g_pm_virtual;
    if (!g_cm_mode) g_pm_virtual = 0;                       /* the slots that return the pad position live in the cursor map */
    th = CreateThread(NULL, 0, pm_thread, NULL, 0, NULL);
    if (th) CloseHandle(th);
    mlog("  pad-menu: v3 on (top speed %d UI px/s; shell [0x4c2164]==6, Esc menu [0x4fe534]==0x10%s; "
         "exe PeekMessageA %s; LoadLibraryA %s; pad layer %s; %s)", (int)g_pm_speed,
         g_pm_pages ? ", other non-driving exe pages (pointer + A)" : " only",
         p_pm_PeekExe ? "chained" : "NOT found", p_LoadLibraryA ? "hooked" : "NOT hooked",
         g_pm_ahk_force < 0 ? "detected per press" : g_pm_ahk_force ? "forced on" : "forced off",
         !virt_req ? "I76_PAD_MENU_VIRTUAL=0: OS pointer warp only (v2)" :
         g_cm_mode ? "the game reads the pad position through the cursor map while the pad drives" :
                     "NO cursor map (I76_CURSOR_MAP unset or u32x): OS pointer warp only");
}
