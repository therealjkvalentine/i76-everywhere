/* i76probe.exe - look at and drive a running i76.exe from INSIDE its Wine session (or on Windows).
 *
 * Why: over SSH a Mac process may not post macOS events (no Accessibility) or capture the screen (no Screen
 * Recording), and the screen may be locked. A Windows program started with the game's own wine + WINEPREFIX joins
 * the game's wineserver, so it can read the game's memory, read back the game window's pixels from Wine's own
 * window surface, and inject input through Wine (SendInput / SetCursorPos never leave Wine). Game night 2026-10-17
 * (docs/records/GAME-NIGHT-ROLLOUT-2026-10-17.md).
 *
 *   i76probe wins                  every visible top-level window (the game's marked); I76PROBE_HWND=<hex> picks one
 *   i76probe state                 game state, network flag, own/host ANet id, player table, position table
 *   i76probe shot <file.bmp>       the game window's client area as a 24-bit BMP (+ its rects on stdout)
 *   i76probe deskshot <file.bmp>   the same rectangle copied from the SCREEN DC (BitBlt): on a Mac the game's GL surface
 *                                  reads back black through PrintWindow, the composited desktop does not
 *   i76probe click <x> <y>         click at a 640x480 UI coordinate (mapped into the 4:3 picture in the client area)
 *   i76probe key <vk-hex> [ms]     press a virtual key (hex, e.g. 1B Esc, 0D Enter), held ms (default 80)
 *   i76probe type <text>           type letters/digits/space
 *   i76probe find <text>           every address in the game's committed readable memory holding the ASCII text,
 *                                  with 48 bytes of context (e.g. a session name to see whether a join list filled)
 *   i76probe throttle <n> <ms>     write the input block's throttle (memlib InThrottle 0x5367CC) for ms, then 0
 *
 * Addresses: lab autotest/lib/memlib.ps1 and music-fix/strlkproxy.c (coop_ai_role, coop_ai_log). Build (x86):
 *   cl /nologo /O2 i76probe.c user32.lib gdi32.lib
 */
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static DWORD g_pid;
static HANDLE g_proc;
static HWND g_wnd;
static int g_desk;

static DWORD find_pid(void) {
    PROCESSENTRY32 pe; HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0); DWORD pid = 0;
    pe.dwSize = sizeof(pe);
    if (Process32First(s, &pe)) do { if (!_stricmp(pe.szExeFile, "i76.exe")) { pid = pe.th32ProcessID; break; } } while (Process32Next(s, &pe));
    CloseHandle(s);
    return pid;
}
static int g_list;
static BOOL CALLBACK enum_cb(HWND h, LPARAM l) {
    DWORD pid; RECT r; char cls[64] = "", title[64] = ""; (void)l;
    GetWindowThreadProcessId(h, &pid);
    if (g_list && IsWindowVisible(h)) {
        RECT w; GetWindowRect(h, &w); GetClassNameA(h, cls, sizeof(cls)); GetWindowTextA(h, title, sizeof(title));
        printf("hwnd %p pid %lu%s class '%s' title '%s' rect %ld,%ld %ldx%ld\n", (void *)h, pid, pid == g_pid ? " (i76)" : "", cls, title,
               w.left, w.top, w.right - w.left, w.bottom - w.top);
    }
    if (getenv("I76PROBE_HWND")) { if ((HWND)(ULONG_PTR)strtoul(getenv("I76PROBE_HWND"), NULL, 16) == h) g_wnd = h; return TRUE; }
    if (pid == g_pid && IsWindowVisible(h)) {
        GetClientRect(h, &r);
        if (r.right >= 320 && r.bottom >= 240) {
            RECT b; if (!g_wnd) { g_wnd = h; return TRUE; }
            GetClientRect(g_wnd, &b);
            if ((r.right * r.bottom) > (b.right * b.bottom)) g_wnd = h;
        }
    }
    return TRUE;
}
static int attach(void) {
    g_pid = find_pid();
    if (!g_pid) { printf("no i76.exe\n"); return 0; }
    g_proc = OpenProcess(PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION, FALSE, g_pid);
    EnumWindows(enum_cb, 0);
    return 1;
}
static int rd(DWORD a, void *b, SIZE_T n) { SIZE_T got = 0; return ReadProcessMemory(g_proc, (LPCVOID)(ULONG_PTR)a, b, n, &got) && got == n; }
static int ri(DWORD a) { int v = 0; rd(a, &v, 4); return v; }
static WORD rw(DWORD a) { WORD v = 0; rd(a, &v, 2); return v; }

static void cmd_state(void) {
    int i;
    printf("pid %lu window %p\n", g_pid, (void *)g_wnd);
    printf("game state %d, play mode 0x%x, net %d, me %u, host %u, frame %d\n", ri(0x4c2164), ri(0x4fe534), ri(0x541030),
           rw(0x541028), rw(0x541064), ri(0x5A7E1C));
    for (i = 0; i < 16; i++) {
        DWORD p = 0x541070 + i * 0x48; WORD id = rw(p); DWORD car = (DWORD)ri(p + 0x28); double x = 0, z = 0;
        if (!id) continue;
        if (car) { rd(car + 0x40, &x, 8); rd(car + 0x50, &z, 8); }
        printf("player slot %d: id %u car 0x%08lx at %.1f,%.1f\n", i, id, car, x, z);
    }
    for (i = 0; i < 16; i++) {
        float v[4]; rd(0x54E11C + i * 0x20, v, 16);
        if (v[0] == v[0] && (v[0] > 0.01f || v[0] < -0.01f || v[2] > 0.01f || v[2] < -0.01f))
            printf("pos slot %d: %.1f %.1f %.1f r %.1f\n", i, v[0], v[1], v[2], v[3]);
    }
}
/* shell state (i76-map/shell/tools/shellstate.ps1, SCREENS.md): VAs at i76shell.dll's preferred base 0x10000000 */
static DWORD shell_base(void) {
    MODULEENTRY32 me; HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, g_pid); DWORD b = 0;
    me.dwSize = sizeof(me);
    if (s != INVALID_HANDLE_VALUE && Module32First(s, &me)) do { if (!_stricmp(me.szModule, "i76shell.dll")) { b = (DWORD)(ULONG_PTR)me.modBaseAddr; break; } } while (Module32Next(s, &me));
    if (s != INVALID_HANDLE_VALUE) CloseHandle(s);
    return b;
}
static void cmd_shell(void) {
    DWORD b = shell_base(), d, mo, lst; int i, n;
    if (!b) { printf("shell: i76shell.dll not loaded\n"); return; }
    d = b - 0x10000000;
    mo = (DWORD)ri(0x100cc514 + d);
    printf("shell base 0x%08lx screen 0x%04x sfn 0x%08lx mfn 0x%08lx modal 0x%08lx mouse %d,%d buttons-down %d\n", b,
           ri(0x100d2168 + d), (DWORD)ri(0x100d219c + d) - d, (DWORD)ri(0x100d21a0 + d) ? (DWORD)ri(0x100d21a0 + d) - d : 0,
           (DWORD)ri(0x100d21a4 + d), mo ? ri(mo + 0x2c) : -1, mo ? ri(mo + 0x30) : -1, mo ? ri(mo + 0x34) : -1);
    lst = (DWORD)ri(0x100d3e7c + d);
    if (!lst) return;
    n = ri(lst + 4);
    for (i = 0; i < n && i < 32; i++) {
        DWORD bt = (DWORD)ri((DWORD)ri(lst + 8) + 4 * i);
        printf("  button id %d click %d,%d\n", ri(bt), (ri(bt + 4) + ri(bt + 8)) / 2, (ri(bt + 0xc) + ri(bt + 0x10)) / 2);
    }
}
static void client_map(int x, int y, POINT *pt) {      /* UI 640x480 -> screen point inside the 4:3 picture */
    RECT r; double s, ox, oy;
    GetClientRect(g_wnd, &r);
    s = (double)r.right / 640.0; if ((double)r.bottom / 480.0 < s) s = (double)r.bottom / 480.0;
    ox = (r.right - 640.0 * s) / 2.0; oy = (r.bottom - 480.0 * s) / 2.0;
    pt->x = (LONG)(ox + (x + 0.5) * s); pt->y = (LONG)(oy + (y + 0.5) * s);
    ClientToScreen(g_wnd, pt);
}
static void fg(void) { if (g_wnd) { SetForegroundWindow(g_wnd); SetActiveWindow(g_wnd); } }
static void cmd_click(int x, int y) {
    POINT pt; INPUT in[3]; int sw = GetSystemMetrics(SM_CXVIRTUALSCREEN), sh = GetSystemMetrics(SM_CYVIRTUALSCREEN);
    int vx = GetSystemMetrics(SM_XVIRTUALSCREEN), vy = GetSystemMetrics(SM_YVIRTUALSCREEN);
    client_map(x, y, &pt); fg();
    SetCursorPos(pt.x, pt.y); Sleep(120);
    memset(in, 0, sizeof(in));
    in[0].type = INPUT_MOUSE; in[0].mi.dx = (LONG)((pt.x - vx) * 65535.0 / (sw - 1)); in[0].mi.dy = (LONG)((pt.y - vy) * 65535.0 / (sh - 1));
    in[0].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
    SendInput(1, in, sizeof(INPUT)); Sleep(120);
    in[1].type = INPUT_MOUSE; in[1].mi.dwFlags = MOUSEEVENTF_LEFTDOWN; SendInput(1, &in[1], sizeof(INPUT)); Sleep(90);
    in[2].type = INPUT_MOUSE; in[2].mi.dwFlags = MOUSEEVENTF_LEFTUP; SendInput(1, &in[2], sizeof(INPUT));
    { POINT c; GetCursorPos(&c); printf("click UI %d,%d -> screen %ld,%ld (cursor now %ld,%ld)\n", x, y, pt.x, pt.y, c.x, c.y); }
}
static void key(WORD vk, int ms) {
    INPUT in; memset(&in, 0, sizeof(in));
    in.type = INPUT_KEYBOARD; in.ki.wVk = vk; in.ki.wScan = (WORD)MapVirtualKeyA(vk, 0);
    SendInput(1, &in, sizeof(INPUT)); Sleep(ms);
    in.ki.dwFlags = KEYEVENTF_KEYUP; SendInput(1, &in, sizeof(INPUT)); Sleep(60);
}
static void cmd_shot(const char *path) {
    RECT r; HDC wdc, mdc; HBITMAP bm; BITMAPINFOHEADER bi; BITMAPFILEHEADER bf; BYTE *bits; FILE *f; int w, h, stride, i;
    long sum = 0;
    GetClientRect(g_wnd, &r); w = r.right; h = r.bottom;
    wdc = GetDC(g_wnd); mdc = CreateCompatibleDC(wdc);
    memset(&bi, 0, sizeof(bi)); bi.biSize = sizeof(bi); bi.biWidth = w; bi.biHeight = h; bi.biPlanes = 1; bi.biBitCount = 24;
    bm = CreateDIBSection(wdc, (BITMAPINFO *)&bi, DIB_RGB_COLORS, (void **)&bits, NULL, 0);
    SelectObject(mdc, bm);
    if (g_desk) { HDC sdc = GetDC(NULL); POINT o = {0, 0}; ClientToScreen(g_wnd, &o); BitBlt(mdc, 0, 0, w, h, sdc, o.x, o.y, SRCCOPY); ReleaseDC(NULL, sdc); }
    else if (!PrintWindow(g_wnd, mdc, 1)) BitBlt(mdc, 0, 0, w, h, wdc, 0, 0, SRCCOPY);
    GdiFlush();
    stride = (w * 3 + 3) & ~3;
    for (i = 0; i < stride * h; i += 97) sum += bits[i];
    memset(&bf, 0, sizeof(bf)); bf.bfType = 0x4d42; bf.bfOffBits = sizeof(bf) + sizeof(bi); bf.bfSize = bf.bfOffBits + stride * h;
    f = fopen(path, "wb"); if (f) { fwrite(&bf, sizeof(bf), 1, f); fwrite(&bi, sizeof(bi), 1, f); fwrite(bits, stride * h, 1, f); fclose(f); }
    { POINT o = {0, 0}; ClientToScreen(g_wnd, &o); printf("shot %dx%d at screen %ld,%ld -> %s (sample sum %ld)\n", w, h, o.x, o.y, path, sum); }
    DeleteObject(bm); DeleteDC(mdc); ReleaseDC(g_wnd, wdc);
}

static void cmd_find(const char *t) {
    MEMORY_BASIC_INFORMATION mi; ULONG_PTR a = 0x10000; size_t tl = strlen(t); int hits = 0;
    while (a < 0x7fff0000 && VirtualQueryEx(g_proc, (LPCVOID)a, &mi, sizeof(mi)) == sizeof(mi)) {
        if (mi.State == MEM_COMMIT && !(mi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) && mi.RegionSize < (64u << 20)) {
            BYTE *buf = (BYTE *)malloc(mi.RegionSize); SIZE_T got = 0;
            if (buf && ReadProcessMemory(g_proc, mi.BaseAddress, buf, mi.RegionSize, &got)) {
                SIZE_T i, j;
                for (i = 0; i + tl <= got && hits < 40; i++) if (!memcmp(buf + i, t, tl)) {
                    printf("0x%08lx: ", (unsigned long)((ULONG_PTR)mi.BaseAddress + i));
                    for (j = i; j < i + 48 && j < got; j++) putchar(buf[j] >= 32 && buf[j] < 127 ? buf[j] : '.');
                    putchar('\n'); hits++;
                }
            }
            free(buf);
        }
        a = (ULONG_PTR)mi.BaseAddress + mi.RegionSize;
    }
    printf("%d hits\n", hits);
}

int main(int argc, char **argv) {
    if (argc < 2) { printf("i76probe state | shot f.bmp | click x y | key vk [ms] | type text | throttle n ms\n"); return 2; }
    if (!strcmp(argv[1], "wins")) { g_list = 1; g_pid = find_pid(); EnumWindows(enum_cb, 0); return 0; }
    if (!attach()) return 1;
    if (!strcmp(argv[1], "state")) cmd_state();
    else if (!strcmp(argv[1], "shell")) cmd_shell();
    else if (!strcmp(argv[1], "move") && argc > 3) { POINT pt; client_map(atoi(argv[2]), atoi(argv[3]), &pt); fg(); SetCursorPos(pt.x, pt.y); printf("cursor -> %ld,%ld\n", pt.x, pt.y); }
    else if (!strcmp(argv[1], "shot") && argc > 2) cmd_shot(argv[2]);
    else if (!strcmp(argv[1], "find") && argc > 2) cmd_find(argv[2]);
    else if (!strcmp(argv[1], "deskshot") && argc > 2) { g_desk = 1; cmd_shot(argv[2]); }
    else if (!strcmp(argv[1], "click") && argc > 3) cmd_click(atoi(argv[2]), atoi(argv[3]));
    else if (!strcmp(argv[1], "key") && argc > 2) { fg(); key((WORD)strtol(argv[2], NULL, 16), argc > 3 ? atoi(argv[3]) : 80); printf("key %s\n", argv[2]); }
    else if (!strcmp(argv[1], "type") && argc > 2) { const char *p; fg(); for (p = argv[2]; *p; p++) { SHORT v = VkKeyScanA(*p); key((WORD)(v & 0xff), 60); } printf("typed\n"); }
    else if (!strcmp(argv[1], "throttle") && argc > 3) {
        int v = atoi(argv[2]), ms = atoi(argv[3]), t; SIZE_T n;
        for (t = 0; t < ms; t += 20) { WriteProcessMemory(g_proc, (LPVOID)0x5367CC, &v, 4, &n); Sleep(20); }
        v = 0; WriteProcessMemory(g_proc, (LPVOID)0x5367CC, &v, 4, &n); printf("throttle written for %d ms\n", ms);
    } else { printf("bad command\n"); return 2; }
    return 0;
}
