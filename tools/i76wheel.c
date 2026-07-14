/* i76wheel - mouse-wheel -> targeting keys for Interstate '76 / Nitro Pack.
 *
 * The 1997 engine's input.map mouse device has exactly three buttons and no
 * wheel channels, so the wheel can't be bound in-engine. This helper installs
 * a low-level mouse hook and, ONLY while i76.exe or nitro.exe owns the
 * foreground window, translates:
 *     wheel up   -> Q  (frontal_target      - target what's under the reticle)
 *     wheel down -> T  (target_nearest_enemy)
 * Everything else passes through untouched; outside the game it does nothing.
 * Exits by itself when no game process has been in the foreground for 60s
 * after having seen one (or kill it; the PLAY launcher manages its lifetime).
 *
 * Build (w64devkit): gcc -O2 -s -o i76wheel.exe i76wheel.c -luser32
 */
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <string.h>

static DWORD lastGameSeen = 0;
static BOOL  everSeen = FALSE;

static BOOL game_is_foreground(void)
{
    HWND fg = GetForegroundWindow();
    if (!fg) return FALSE;
    DWORD pid = 0;
    GetWindowThreadProcessId(fg, &pid);
    if (!pid) return FALSE;
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!h) return FALSE;
    char path[MAX_PATH] = "";
    DWORD n = MAX_PATH;
    BOOL ok = QueryFullProcessImageNameA(h, 0, path, &n);
    CloseHandle(h);
    if (!ok) return FALSE;
    const char *base = strrchr(path, '\\');
    base = base ? base + 1 : path;
    return _stricmp(base, "i76.exe") == 0 || _stricmp(base, "nitro.exe") == 0;
}

static void send_key(WORD vk)
{
    INPUT in[2];
    ZeroMemory(in, sizeof(in));
    in[0].type = INPUT_KEYBOARD; in[0].ki.wVk = vk;
    in[1].type = INPUT_KEYBOARD; in[1].ki.wVk = vk; in[1].ki.dwFlags = KEYEVENTF_KEYUP;
    SendInput(2, in, sizeof(INPUT));
}

static LRESULT CALLBACK hook(int code, WPARAM wp, LPARAM lp)
{
    if (code == HC_ACTION && wp == WM_MOUSEWHEEL) {
        MSLLHOOKSTRUCT *m = (MSLLHOOKSTRUCT *)lp;
        if (game_is_foreground()) {
            short delta = (short)HIWORD(m->mouseData);
            send_key(delta > 0 ? 'Q' : 'T');
            return 1;   /* swallow the wheel event */
        }
    }
    return CallNextHookEx(NULL, code, wp, lp);
}

int WINAPI WinMain(HINSTANCE hi, HINSTANCE hp, LPSTR cmd, int show)
{
    HHOOK hh = SetWindowsHookExA(WH_MOUSE_LL, hook, hi, 0);
    if (!hh) return 1;
    SetTimer(NULL, 1, 5000, NULL);
    MSG msg;
    while (GetMessageA(&msg, NULL, 0, 0) > 0) {
        if (msg.message == WM_TIMER) {
            if (game_is_foreground()) { lastGameSeen = GetTickCount(); everSeen = TRUE; }
            else if (everSeen && GetTickCount() - lastGameSeen > 60000) break;
        }
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    UnhookWindowsHookEx(hh);
    return 0;
}
