/* escmenu.c - I76_MENU_PTR: the pointer in the exe's in-mission Esc menu under DxWnd (the Macs).
 * Included from strlkproxy.c after mpmenu.c. Record: docs/records/MAC-CONVERGE-2026-10-20.md section 3.
 *
 * THE PROBLEM (owner, laptop, 2026-10-20: "the mouse and keyboard don't work on the game pause menu correctly").
 * The Esc menu is the exe's (shell_BeginInGameMenu 0x4953e0, page rect [0x654a3c..0x654a48] in 640x480 frame pixels;
 * lab MOUSE-ESC-MENU-AND-SAVE-SCREEN.md s.2). The WndProc 0x404830 hands the lParam of WM_LBUTTONDOWN / UP to
 * 0x4972d0 (call sites 0x404b89 / 0x404b4c) while [0x4fe534] == 0x10, and that function hit-tests it as a 640x480
 * coordinate. Measured on Andrew's Mac (1440x900 window): the click positions that reach 0x4972d0 follow the window
 * up to about window x 800 / y 560-600 and then STOP - every click lower or further right lands on the last row it
 * reached (Play Options: y 560..840 all hit row 4), and Cancel / Back (UI y 434..453) could not be clicked at all
 * (0 of 61 clicks). The I76_MENU_PTR_LOG lines show why: under DxWnd the window is 800x600 as the game sees it, the
 * message comes out of the exe's PeekMessageA slot (u32x.dll) already clamped to (639, 479) for a click at window
 * (1000, 840), and DxWnd's window-procedure layer then scales it once more. The exe's own GetCursorPos slot (u32x.dll,
 * the read the shell's pointer works through) gives the right 640x480 point for the same click: (444, 448).
 *
 * THE FIX. The two calls into 0x4972d0 are repointed to emp_menu_mouse, which hands 0x4972d0 the exe's own pointer
 * read (its GetCursorPos import, clamped to 0..639 / 0..479) instead of the message's lParam. It sits after every
 * layer (DxWnd, u32x), so nothing that rewrites messages on the way can move the point again. Only the Esc menu (and
 * the mission-over menu, the same function) is affected; the keys (0x496e10) are untouched.
 *
 *   I76_MENU_PTR=auto (default)   on only when dxwnd.dll is loaded in the game (the Macs); the PC path is untouched
 *   I76_MENU_PTR=1 / 0            force on / off
 *   I76_MENU_PTR_LOG=1            every menu click: the message's lParam and the point used (first 60)
 */
static int g_emp_mode = 2;                       /* 0 off, 1 forced on, 2 auto (on with DxWnd) */
static int g_emp_log;
static BOOL (WINAPI *p_emp_GetCursorPos)(LPPOINT);
static volatile LONG g_emp_logged;
static void __cdecl emp_menu_mouse(int msg, int wparam, DWORD lparam) {
    POINT p; DWORD in = lparam;
    if (p_emp_GetCursorPos && p_emp_GetCursorPos(&p)) {
        if (p.x < 0) p.x = 0; if (p.x > 639) p.x = 639;
        if (p.y < 0) p.y = 0; if (p.y > 479) p.y = 479;
        lparam = MAKELONG((WORD)p.x, (WORD)p.y);
    }
    if (g_emp_log && InterlockedIncrement(&g_emp_logged) <= 60)
        mlog("  menu-ptr: msg 0x%03x lParam (%d,%d) -> (%d,%d)", msg, (short)LOWORD(in), (short)HIWORD(in),
             (short)LOWORD(lparam), (short)HIWORD(lparam));
    ((void (__cdecl *)(int, int, DWORD))0x004972d0)(msg, wparam, lparam);
}
static const char *emp_owner(void *p) {          /* the module a function pointer lies in (log) */
    static char nm[64]; HMODULE m = NULL;
    nm[0] = 0;
    if (p && GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)p, &m) && m) {
        char full[MAX_PATH]; const char *s;
        if (GetModuleFileNameA(m, full, sizeof full)) { s = strrchr(full, '\\'); lstrcpynA(nm, s ? s + 1 : full, sizeof nm); }
    }
    return nm[0] ? nm : "?";
}
static void emp_install(void) {
    static const DWORD site[2] = { 0x00404b4c, 0x00404b89 };   /* WM_LBUTTONUP, WM_LBUTTONDOWN: e8 -> 0x4972d0 */
    HMODULE exe = GetModuleHandleA(NULL); void **gs = iat_slot(exe, "u32x.dll", "GetCursorPos");
    int i, ok = 0;
    if (!gs) gs = iat_slot(exe, "USER32.dll", "GetCursorPos");
    if (!gs) { mlog("  menu-ptr: i76.exe imports no GetCursorPos - off"); return; }
    p_emp_GetCursorPos = (BOOL (WINAPI *)(LPPOINT))*gs;
    for (i = 0; i < 2; i++) {
        BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 }; BYTE *p = (BYTE *)(DWORD_PTR)site[i];
        LONG a0 = (LONG)(0x004972d0 - (site[i] + 5)), a1 = (LONG)((DWORD)(DWORD_PTR)emp_menu_mouse - (site[i] + 5));
        memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
        ok += mpm_write(p, o5, w5, 5);
    }
    mlog("  menu-ptr: Esc-menu clicks take the pointer from i76.exe's GetCursorPos slot (%s %p): %d / 2 call sites %s",
         emp_owner((void *)p_emp_GetCursorPos), (void *)p_emp_GetCursorPos, ok,
         ok == 2 ? "repointed, read back OK" : "NOT all repointed (unexpected bytes)");
}
static DWORD WINAPI emp_watch(LPVOID arg) {
    int i;
    (void)arg;
    for (i = 0; i < 6000 && *(volatile int *)0x4c2164 != 6; i++) Sleep(50);   /* the shell is up: every layer has loaded */
    Sleep(1000);
    if (g_emp_mode == 2 && !GetModuleHandleA("dxwnd.dll")) { mlog("  menu-ptr: auto - no DxWnd in this game: off (the PC path)"); return 0; }
    emp_install();
    return 0;
}
static void apply_menu_ptr(void) {
    char v[8]; DWORD n = env_str("I76_MENU_PTR", v, sizeof v);
    HANDLE th;
    if (n && v[0] == '0') { mlog("  menu-ptr: off (I76_MENU_PTR=0)"); return; }
    g_emp_mode = (n && v[0] == '1') ? 1 : 2;
    g_emp_log = env_flag("I76_MENU_PTR_LOG", 4, 0) == 1;
    th = CreateThread(NULL, 0, emp_watch, NULL, 0, NULL);
    mlog("  menu-ptr: %s - Esc-menu clicks from the exe's own pointer read; installed once the shell is up%s",
         g_emp_mode == 1 ? "on (I76_MENU_PTR=1)" : "auto (on under DxWnd)", th ? "" : " - thread NOT started");
    if (th) CloseHandle(th);
}

/* ---- I76_MENU_PTR_CENTRE (default 1 when I76_CURSOR_MAP maps i76.exe's pointer; 0 = stock) -------------------------
 * Owner 2026-10-20 / 10-21 (MENU-SOUND-POLISH s.A, s.H): "I lose mouse visibility/use when I click exit game" / "still
 * can't consistently see the pointer when I use the exit menu". Measured (s.H): every time the Esc menu opens, the
 * pointer is put on the screen's bottom edge (y 1437..1439 of 1440, the arrow drawn below the screen: 11 of 11 opens,
 * both lanes' runs). Cause: the engine's show-pointer routine 0x44bcc0 (the menus' open, 0x4953e5) keeps x and sets
 * y = [0x5dcf30] / 2 (0x44bd38), the client height in screen pixels (1440 -> 720), then SetCursorPos; with I76_CURSOR_MAP
 * that SetCursorPos is the 640x480 UI -> screen map, so 720 is read as a UI y and lands at 2160 -> clamped to the bottom.
 * In a real 640x480 mode [0x5dcf30] = 480 and the stock code centres. Fix: the load at 0x44bd38 (`mov eax, [0x5dcf30]`,
 * A1 30 CF 5D 00) reads a 480 here instead, so the pointer opens at UI y 240 = the middle of the menu, x unchanged.
 * The hide routine 0x44bb40 (driving) is left alone: the pointer is hidden there. Off when the cursor map does not take
 * i76.exe's slots (the Macs' DxWnd path, u32x alone): there the stock value is in the coordinates SetCursorPos expects. */
static DWORD g_mpc_ui_h = 480;
static void apply_menu_ptr_centre(void) {
    static const BYTE o[5] = { 0xA1, 0x30, 0xCF, 0x5D, 0x00 };
    BYTE w[5] = { 0xA1 };
    DWORD a = (DWORD)(DWORD_PTR)&g_mpc_ui_h;
    if (env_flag("I76_MENU_PTR_CENTRE", 8, 1) == 0) { mlog("  menu-ptr-centre: off (I76_MENU_PTR_CENTRE=0): stock"); return; }
    if (!g_cm_mode) { mlog("  menu-ptr-centre: the cursor map is off here - stock (nothing to correct)"); return; }
    memcpy(w + 1, &a, 4);
    /* Nitro (parity lane 2026-10-24, records/NITRO-PARITY-2026-10-24.md): the same show-pointer code at 0x443688 (`mov eax, [0x653bb0]`,
     * the client height; site map reloc, 18 bytes the same instructions) and the same cursor map on nitro.exe's SetCursorPos slot, so the
     * same bottom-edge pointer; patch_bytes relocates the site and reads it back (nitro_patch_bytes), our operand is kept verbatim */
    if (!patch_bytes(0x0044bd38, o, w, 5, "show-pointer recentre height (menu-ptr-centre)") || (g_exe != EXE_NITRO && memcmp((void *)0x0044bd38, w, 5) != 0)) {
        mlog("  menu-ptr-centre: 0x44bd38 did not verify - not applied"); return;
    }
    mlog("  menu-ptr-centre: on - a menu opens with the pointer at UI y 240 (the screen's middle under the cursor map), not the bottom edge");
}
