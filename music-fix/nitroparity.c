/* nitroparity.c - Gold fixes that live in u32x.dll on Gold, done by the proxy on Nitro (nitro-parity lane 2026-10-24).
 * Included by strlkproxy.c after cursormap.c. Record: docs/records/NITRO-PARITY-2026-10-24.md.
 *
 * nitro.exe and NITSHELL.DLL import USER32 directly (NITRO-PORT s.10): u32x.dll, Gold's mouse DLL, is not in the Nitro process,
 * so the u32x fixes that are not about the pointer never ran there. Two of them matter in play:
 *
 * 1. GHOSTING (I76_NO_GHOSTING, default 1). u32x_full.c (2026-09-06) calls DisableProcessWindowsGhosting at attach: a shell screen
 *    that polls without pumping for 5 s gets replaced by a DWM ghost window, which takes the activation and the keyboard ("one
 *    character lands and then nothing" on Gold's save screen, measured by a per-call census).
 * 2. MESSAGE BOXES IN FRONT (I76_NITRO_MSGBOX, default 1). u32x_full.c (2026-10-03, audit b2): a plain MessageBoxA over the
 *    fullscreen picture was measured opening BEHIND it (the game then looks frozen; the engine also hides and clips the
 *    pointer). Nitro shows the same kind of boxes from the same two places: nitro.exe (CD / fatal errors) and NITSHELL.DLL (the
 *    network errors, "Unable to create an IPX connection..." in the Gold shell; the multiplayer screens). Both MessageBoxA import
 *    slots go through nmb_MessageBoxA: the clip is released and the arrow shown for the box, the box is MB_TOPMOST |
 *    MB_SETFOREGROUND and a thread-local CBT hook centres it on the game window as topmost; afterwards the ShowCursor count and
 *    the clip are given back and the game window is put in front again. Every box is logged with its caption and text. */

static void nitro_no_ghosting(void) {
    HMODULE u = GetModuleHandleA("user32.dll"); void (WINAPI *f)(void);
    if (env_flag("I76_NO_GHOSTING", 8, 1) == 0) { mlog("  no-ghosting: off (I76_NO_GHOSTING=0): stock (DWM may ghost a window that stops pumping)"); return; }
    f = u ? (void (WINAPI *)(void))GetProcAddress(u, "DisableProcessWindowsGhosting") : NULL;
    if (f) f();
    mlog("  no-ghosting: %s", f ? "on - DisableProcessWindowsGhosting called (as u32x does on Gold)" : "user32 has no DisableProcessWindowsGhosting - not applied");
}

typedef int (WINAPI *nmb_fn)(HWND, LPCSTR, LPCSTR, UINT);
static nmb_fn g_nmb_real;
static int g_nmb_on = -1;
static HHOOK g_nmb_hook;
static HWND g_nmb_placed;
static volatile LONG g_nmb_n;

static HWND nmb_game_window(void) {
    HWND h = FindWindowA("Interstate '76 Nitro Pack", NULL);
    if (!h) h = FindWindowA(NULL, "Interstate '76 Nitro Pack");
    return h;
}
static LRESULT CALLBACK nmb_cbt(int code, WPARAM wp, LPARAM lp) {
    if (code == HCBT_ACTIVATE && (HWND)wp != g_nmb_placed) {
        HWND dlg = (HWND)wp, gw = nmb_game_window(); char cls[16]; RECT dr, gr;
        if (GetClassNameA(dlg, cls, sizeof cls) && lstrcmpA(cls, "#32770") == 0 && GetWindowRect(dlg, &dr)) {
            int w = dr.right - dr.left, h = dr.bottom - dr.top, x = dr.left, y = dr.top;
            if (gw && dlg != gw && GetWindowRect(gw, &gr)) {
                MONITORINFO mi; mi.cbSize = sizeof mi;
                x = (gr.left + gr.right) / 2 - w / 2; y = (gr.top + gr.bottom) / 2 - h / 2;
                if (GetMonitorInfoA(MonitorFromWindow(gw, MONITOR_DEFAULTTONEAREST), &mi)) {
                    if (x > mi.rcWork.right - w) x = mi.rcWork.right - w; if (x < mi.rcWork.left) x = mi.rcWork.left;
                    if (y > mi.rcWork.bottom - h) y = mi.rcWork.bottom - h; if (y < mi.rcWork.top) y = mi.rcWork.top;
                }
            }
            SetWindowPos(dlg, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE);
            g_nmb_placed = dlg;
            mlog("  nitro-msgbox: box %p placed at (%d,%d) %dx%d, topmost", (void *)dlg, x, y, w, h);
        }
    }
    return CallNextHookEx(g_nmb_hook, code, wp, lp);
}
static int WINAPI nmb_MessageBoxA(HWND owner, LPCSTR text, LPCSTR cap, UINT type) {
    RECT clip; int clipped = 0, shows = 0, r; HHOOK prev = g_nmb_hook; HWND prevp = g_nmb_placed, gw = nmb_game_window();
    LONG k = InterlockedIncrement(&g_nmb_n);
    if (k <= 50) mlog("nitro-msgbox #%ld: \"%.80s\": \"%.200s\" (type 0x%X)", k, cap ? cap : "", text ? text : "", type);
    if (!g_nmb_real) return IDOK;
    if (GetClipCursor(&clip)) {
        int vl = GetSystemMetrics(SM_XVIRTUALSCREEN), vt = GetSystemMetrics(SM_YVIRTUALSCREEN);
        clipped = clip.left > vl || clip.top > vt || clip.right < vl + GetSystemMetrics(SM_CXVIRTUALSCREEN) || clip.bottom < vt + GetSystemMetrics(SM_CYVIRTUALSCREEN);
    }
    ClipCursor(NULL);
    while (ShowCursor(TRUE) < 0 && shows < 64) shows++;
    shows++;                                                  /* the call that reached >= 0 counted too */
    g_nmb_hook = SetWindowsHookExA(WH_CBT, nmb_cbt, NULL, GetCurrentThreadId());
    r = g_nmb_real(owner, text, cap, type | MB_TOPMOST | MB_SETFOREGROUND);
    if (g_nmb_hook) UnhookWindowsHookEx(g_nmb_hook);
    g_nmb_hook = prev; g_nmb_placed = prevp;
    while (shows-- > 0) ShowCursor(FALSE);
    if (clipped) ClipCursor(&clip);
    if (gw) SetForegroundWindow(gw);
    if (k <= 50) mlog("nitro-msgbox #%ld: answered %d", k, r);
    return r;
}
/* nitro.exe from nitro_dllmain, NITSHELL.DLL from hook_LoadLibraryA (once) */
static void nitro_msgbox_attach(HMODULE m, const char *what) {
    static volatile LONG shell_done; void *old;
    if (g_exe != EXE_NITRO) return;
    if (g_nmb_on < 0) g_nmb_on = env_flag("I76_NITRO_MSGBOX", 8, 1) == 1;
    if (!g_nmb_on) { if (!m) mlog("  nitro-msgbox: off (I76_NITRO_MSGBOX=0): stock message boxes"); return; }
    if (m && InterlockedCompareExchange(&shell_done, 1, 0) != 0) return;
    if (!m) m = GetModuleHandleA(NULL);
    old = patch_iat(m, "USER32.dll", "MessageBoxA", (void *)nmb_MessageBoxA);
    if (old && old != (void *)nmb_MessageBoxA && !g_nmb_real) g_nmb_real = (nmb_fn)old;
    if (!g_nmb_real) g_nmb_real = (nmb_fn)GetProcAddress(GetModuleHandleA("user32.dll"), "MessageBoxA");
    mlog("  nitro-msgbox: %s MessageBoxA slot %s (boxes in front of the picture, centred, with the arrow; as u32x on Gold)",
         what, old ? "hooked" : "NOT found");
}
