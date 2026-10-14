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
 * The position is kept in 640x480 UI units and placed with the real SetCursorPos through cursormap's cm_map (the
 * game window's client rect, stretched or ar), so the speed is the same on 1280x800 and 3840x2160. When the real
 * pointer moved by itself (trackpad, mouse) the pad position is resynchronised from it. Buttons go in through
 * SendInput (the path the pad layer's AHK Click already uses under Proton). In a mission outside the Esc menu, in a
 * cutscene-free load, and with the switch unset, the thread does nothing (unset: no thread, no XInput load).
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
 *    I76_PAD_MENU_LOG=1             activation changes and the first 40 actions in mciproxy.log
 *    I76_PAD_MENU_AHK=0|1           force "pad layer present" off / on (default: detected by window class)
 */
typedef struct { WORD wButtons; BYTE bLeftTrigger, bRightTrigger; SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY; } PmPad;
typedef struct { DWORD dwPacketNumber; PmPad Gamepad; } PmState;
static DWORD (WINAPI *p_pm_XInputGetState)(DWORD, PmState *);
static BOOL  (WINAPI *p_pm_SetCursorPos)(int, int);
static BOOL  (WINAPI *p_pm_GetCursorPos)(LPPOINT);
static BOOL  (WINAPI *p_pm_PeekExe)(LPMSG, HWND, UINT, UINT, UINT);
static BOOL  (WINAPI *p_pm_PeekShell)(LPMSG, HWND, UINT, UINT, UINT);
static int   g_pm_on, g_pm_log, g_pm_ahk_force = -1, g_pm_nlog;
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
static int pm_menu_up(void) {
    int st = *(volatile int *)0x004c2164;
    if (st == 6) return 1;
    if (st == 5 && *(volatile int *)0x004fe534 == 0x10) return 2;
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

static DWORD WINAPI pm_thread(LPVOID arg) {
    float ux = 320.0f, uy = 240.0f, ramp = 0.0f, dramp = 0.0f;
    POINT last = { -100000, -100000 };
    WORD prev = 0; int was = 0, a_down = 0, a_ours = 0;
    DWORD t0 = GetTickCount();
    const char *names[3] = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
    HMODULE x = NULL; int k;
    (void)arg;
    /* loaded here, not in DllMain: no LoadLibrary under the loader lock */
    for (k = 0; k < 3 && !x; k++) x = LoadLibraryA(names[k]);
    if (x) p_pm_XInputGetState = (DWORD (WINAPI *)(DWORD, PmState *))GetProcAddress(x, "XInputGetState");
    mlog("  pad-menu: XInput %s", p_pm_XInputGetState ? names[k - 1] : "NOT found (xinput1_4 / 1_3 / 9_1_0) - pad menu idle");
    if (!p_pm_XInputGetState) return 0;
    for (;;) {
        DWORD now = GetTickCount(), dtms = now - t0, i;
        WORD btn = 0; int sx = 0, sy = 0, connected = 0, up;
        float lx = 0.0f, ly = 0.0f, dt;
        HWND h;
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
        {   DWORD pid = 0; HWND fg = GetForegroundWindow();
            if (fg) GetWindowThreadProcessId(fg, &pid);
            /* no foreground window known (can happen under a compositor) counts as ours: only another app in front stops it */
            up = connected && h && (!fg || pid == GetCurrentProcessId()) ? pm_menu_up() : 0; }
        if (up != was) {
            if (g_pm_log) mlog("  pad-menu: %s (game state %d, mode 0x%x, %d pad(s))",
                               up == 1 ? "shell - pointer on the pad" : up == 2 ? "Esc menu - pointer on the pad" : "off (no menu)",
                               *(volatile int *)0x004c2164, *(volatile int *)0x004fe534, connected);
            if (!up && a_down && a_ours) pm_mouse(MOUSEEVENTF_LEFTUP);   /* never leave the button down in a mission */
            if (!up) a_down = a_ours = 0;
            was = up; last.x = -100000;
        }
        InterlockedExchange(&g_pm_active, up);
        if (up) {
            POINT cur; int moved = 0;
            /* resync when something else moved the pointer (trackpad, mouse, the game's own SetCursorPos) */
            if (p_pm_GetCursorPos(&cur) && (cur.x - last.x > 2 || last.x - cur.x > 2 || cur.y - last.y > 2 || last.y - cur.y > 2)) {
                pm_screen_to_ui(cur, &ux, &uy);
                last = cur;      /* else a slow push (< 1 screen px per poll) is reset to the pixel every poll and never moves */
            }
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
                pm_ui_to_screen(ux, uy, &s);
                if (s.x != last.x || s.y != last.y) { p_pm_SetCursorPos(s.x, s.y); last = s; }
            }
            /* A: the left button, unless the pad layer clicks already */
            if ((btn & PM_A) && !(prev & PM_A)) {
                a_down = 1; a_ours = !pm_ahk();
                if (a_ours) { pm_mouse(MOUSEEVENTF_LEFTDOWN); pm_logf("A: left down at UI", (long)ux, (long)uy); }
                else pm_logf("A: pad layer clicks (AHK) at UI", (long)ux, (long)uy);
            }
            if (!(btn & PM_A) && a_down) { if (a_ours) pm_mouse(MOUSEEVENTF_LEFTUP); a_down = a_ours = 0; }
            if (btn & PM_B) g_pm_held_until[2] = now + 150;
            if ((btn & PM_B) && !(prev & PM_B)) { pm_key(VK_ESCAPE, 0); pm_key(VK_ESCAPE, 1); pm_logf("B: Esc", up, 0); }
            if (btn & PM_START) g_pm_held_until[1] = now + 150;
            if ((btn & PM_START) && !(prev & PM_START)) { pm_key(VK_RETURN, 0); pm_key(VK_RETURN, 1); pm_logf("Start: Enter", up, 0); }
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
    HANDLE th;
    if (n == 0 || n >= sizeof(v) || v[0] == '0') return;
    {   char c[16]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_SPEED", c, sizeof(c));
        if (k && k < sizeof(c)) { int s = atoi(c); if (s >= 50 && s <= 5000) g_pm_speed = (float)s; } }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_LOG", c, sizeof(c)); g_pm_log = (k && k < sizeof(c) && c[0] == '1'); }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_PAD_MENU_AHK", c, sizeof(c));
        if (k && k < sizeof(c)) g_pm_ahk_force = (c[0] == '1') ? 1 : 0; }
    p_pm_SetCursorPos = (BOOL (WINAPI *)(int, int))GetProcAddress(u, "SetCursorPos");     /* the real ones: never a hook */
    p_pm_GetCursorPos = (BOOL (WINAPI *)(LPPOINT))GetProcAddress(u, "GetCursorPos");
    g_pm_on = 1;
    p_pm_PeekExe = (BOOL (WINAPI *)(LPMSG, HWND, UINT, UINT, UINT))patch_iat(exe, "USER32.dll", "PeekMessageA", pm_PeekExe);
    if ((sh = GetModuleHandleA("i76shell.dll")) != NULL) pad_menu_attach(sh, "i76shell.dll");
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(exe, "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    th = CreateThread(NULL, 0, pm_thread, NULL, 0, NULL);
    if (th) CloseHandle(th);
    mlog("  pad-menu: on (top speed %d UI px/s; shell [0x4c2164]==6 and Esc menu [0x4fe534]==0x10 only; "
         "exe PeekMessageA %s; LoadLibraryA %s; pad layer %s)", (int)g_pm_speed,
         p_pm_PeekExe ? "chained" : "NOT found", p_LoadLibraryA ? "hooked" : "NOT hooked",
         g_pm_ahk_force < 0 ? "detected per press" : g_pm_ahk_force ? "forced on" : "forced off");
}
