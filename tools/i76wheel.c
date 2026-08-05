/* i76wheel - mouse-wheel -> keystrokes for Interstate '76 / Nitro Pack.
 *
 * The 1997 engine's input.map mouse device has exactly three buttons and no
 * wheel channels, so the wheel cannot be bound in-engine at all. This helper
 * installs a low-level mouse hook and, ONLY while i76.exe or nitro.exe owns the
 * foreground window, translates wheel motion into a keypress. Everything else
 * passes through untouched; outside the game it does nothing.
 *
 * DEFAULTS (2026-08-04): wheel up -> Tab (weapon_cycle), wheel down -> Five
 * (hardpoint5_fire, normally the dropper). Previously Q/T for targeting.
 *
 * The keys are CONFIGURABLE, because which hardpoint holds the dropper depends
 * on the car's loadout - it is not a fixed property of the game:
 *
 *     i76wheel.exe                     defaults, as above
 *     i76wheel.exe /up=Tab /down=4     dropper on hardpoint 4
 *     i76wheel.exe /up=Q   /down=T     the old targeting behaviour
 *
 * Accepts a single character (Q, T, 5) or a name (Tab, Enter, Space). The value
 * must match whatever input.map binds the action to - check with
 * tools/lint-input-map.py, which validates names against the exe's own tables.
 *
 * Exits by itself when no game process has been in the foreground for 60s after
 * having seen one (or kill it; the PLAY launcher manages its lifetime).
 *
 * Build: tools/build-i76wheel.ps1   (MSVC x86; gcc also fine:
 *        gcc -O2 -s -o i76wheel.exe i76wheel.c -luser32)
 */
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <string.h>
#include <stdio.h>

static DWORD lastGameSeen = 0;
static BOOL  everSeen = FALSE;

/* Defaults: cycle the front weapon on wheel up, drop the dropper on wheel down. */
static WORD  g_vkUp   = VK_TAB;   /* weapon_cycle    */
static WORD  g_vkDown = '5';      /* hardpoint5_fire */

/* Map a token from the command line to a virtual-key code.
 *
 * Only the tokens input.map can actually name are supported; a bare digit or
 * letter is passed through as its ASCII code, which is what VkKeyScan would give
 * for the unshifted key anyway. Returns 0 for an unrecognised token so the caller
 * can keep its default rather than silently sending a wrong key - a wheel that
 * fires the wrong weapon is worse than a wheel that does nothing. */
static WORD vk_from_name(const char *s)
{
    if (!s || !*s) return 0;
    if (!s[1]) {                                  /* single character */
        char c = s[0];
        if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
        if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z')) return (WORD)c;
        return 0;
    }
    if (!_stricmp(s, "Tab"))    return VK_TAB;
    if (!_stricmp(s, "Enter"))  return VK_RETURN;
    if (!_stricmp(s, "Space"))  return VK_SPACE;
    if (!_stricmp(s, "One"))    return '1';
    if (!_stricmp(s, "Two"))    return '2';
    if (!_stricmp(s, "Three"))  return '3';
    if (!_stricmp(s, "Four"))   return '4';
    if (!_stricmp(s, "Five"))   return '5';
    return 0;
}

static void parse_args(LPSTR cmd)
{
    char buf[512], *tok;
    if (!cmd || !*cmd) return;
    strncpy(buf, cmd, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = 0;
    for (tok = strtok(buf, " \t"); tok; tok = strtok(NULL, " \t")) {
        const char *val = NULL;
        WORD vk;
        if (!_strnicmp(tok, "/up=", 4) || !_strnicmp(tok, "-up=", 4))        val = tok + 4;
        else if (!_strnicmp(tok, "/down=", 6) || !_strnicmp(tok, "-down=", 6)) val = tok + 6;
        else continue;
        vk = vk_from_name(val);
        if (!vk) continue;                          /* keep the default */
        if (tok[1] == 'u' || tok[1] == 'U') g_vkUp = vk; else g_vkDown = vk;
    }
}

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
            send_key(delta > 0 ? g_vkUp : g_vkDown);
            return 1;   /* swallow the wheel event */
        }
    }
    return CallNextHookEx(NULL, code, wp, lp);
}

int WINAPI WinMain(HINSTANCE hi, HINSTANCE hp, LPSTR cmd, int show)
{
    HHOOK hh;
    parse_args(cmd);
    hh = SetWindowsHookExA(WH_MOUSE_LL, hook, hi, 0);
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
