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
 *   i76probe pos                   one line: state, net flag, own / host id, every position-table slot (x,y,z)
 *   i76probe click <x> <y>         click at a 640x480 UI coordinate, by default mapped into the 4:3 picture of the client.
 *                                  Mapping overrides: I76PROBE_MAP="kx ox ky oy" (client = o + k * UI, a measured fit),
 *                                  I76PROBE_STRETCH=1 (whole client: the Deck's proxy cursor map), I76PROBE_RAW=1 (x y
 *                                  are client pixels), I76PROBE_SETTLE=<ms> (extra moves + wait before the press),
 *                                  I76PROBE_NOMOVE=<ms> (buttons only, held ms: the pointer was placed by other means)
 *   i76probe pclick <x> <y>        the same click as posted WM_MOUSEMOVE / WM_LBUTTONDOWN / UP messages to the game window
 *   i76probe mclick <x> <y>        write x,y into the shell's mouse object, then press the button (forms only; a write)
 *   i76probe key <vk-hex> [ms]     press a virtual key (hex, e.g. 1B Esc, 0D Enter), held ms (default 80)
 *   i76probe type <text>           type letters/digits/space
 *   i76probe find <text>           every address in the game's committed readable memory holding the ASCII text,
 *                                  with 48 bytes of context (e.g. a session name to see whether a join list filled)
 *   i76probe peek <addr|shell+off> [n] / dump <addr> <len> <file> / poke <addr> <dword>...   memory (poke = a write)
 *   i76probe mods / regions / stack  loaded modules; big committed regions; every thread's EIP + module return addresses
 *   i76probe throttle <n> <ms>     write the input block's throttle (memlib InThrottle 0x5367CC) for ms, then 0
 *   I76PROBE_PID=<pid> picks the game when several i76.exe run (the PC); I76PROBE_HWND=<hex> picks the window.
 *
 * The Mac pointer, measured 2026-10-18 (docs/records/LAN-MATRIX-2026-10-18.md): the shell's main-menu buttons take the
 * click's own coordinates, but the entry forms (host / join, EntryForm_Frame 0x10028610) hit-test the shell's mouse
 * object [[0x100cc514]+0x2c/+0x30], which under Wine's Mac driver follows the REAL macOS pointer. SendInput from this
 * probe (started over SSH, no Mac driver) moves only Wine's server cursor, so JOIN GAME / BROADCAST were pressed at
 * wherever the real pointer sat. Warp the real pointer first (tools/lan-test/cur.swift, CGWarpMouseCursorPosition; works
 * over SSH without Accessibility on an unlocked Mac). On a LOCKED Mac neither path reaches the game: keys only.
 * Shell framebuffer (a screenshot that works everywhere): display object [0x100cc518], 640x480 8-bit buffers at its
 * dwords 17 and 22 (tools/lan-test/fbshot.sh).
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

static DWORD find_pid(void) {    /* I76PROBE_PID picks one when several i76.exe run (the PC: lab agents' games) */
    PROCESSENTRY32 pe;
    if (getenv("I76PROBE_PID")) return (DWORD)atoi(getenv("I76PROBE_PID")); HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0); DWORD pid = 0;
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
static void cmd_pos(void) {    /* one line: game state, net flag, own / host ANet id, every non-zero position-table slot */
    int i; printf("gs %d net %d me %u host %u |", ri(0x4c2164), ri(0x541030), rw(0x541028), rw(0x541064));
    for (i = 0; i < 16; i++) {
        float v[4]; rd(0x54E11C + i * 0x20, v, 16);
        if (v[0] == v[0] && (v[0] > 0.01f || v[0] < -0.01f || v[2] > 0.01f || v[2] < -0.01f)) printf(" %d:%.2f,%.2f,%.2f", i, v[0], v[1], v[2]);
    }
    printf("\n");
}
/* shell state (<re-archive>/shell/tools/shellstate.ps1, SCREENS.md): VAs at i76shell.dll's preferred base 0x10000000 */
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
        printf("  button id %d click %d,%d rect x %d..%d y %d..%d\n", ri(bt), (ri(bt + 4) + ri(bt + 8)) / 2,
               (ri(bt + 0xc) + ri(bt + 0x10)) / 2, ri(bt + 4), ri(bt + 8), ri(bt + 0xc), ri(bt + 0x10));
    }
}
static void client_map(int x, int y, POINT *pt) {      /* UI 640x480 -> screen point inside the 4:3 picture */
    RECT r; double s, ox, oy;
    GetClientRect(g_wnd, &r);
    if (getenv("I76PROBE_RAW")) {       /* x y are client-area pixels (for calibrating the mapping) */
        pt->x = x; pt->y = y; ClientToScreen(g_wnd, pt); return;
    }
    if (getenv("I76PROBE_MAP")) {       /* "kx ox ky oy": UI -> client pixels, x' = ox + kx * x (a measured fit) */
        double kx, ox, ky, oy;
        if (sscanf(getenv("I76PROBE_MAP"), "%lf %lf %lf %lf", &kx, &ox, &ky, &oy) == 4) {
            pt->x = (LONG)(ox + kx * (x + 0.5)); pt->y = (LONG)(oy + ky * (y + 0.5)); ClientToScreen(g_wnd, pt); return;
        }
    }
    if (getenv("I76PROBE_STRETCH")) {   /* DxWnd stretches 640x480 over the whole client (no 4:3 letterbox) */
        pt->x = (LONG)((x + 0.5) * r.right / 640.0); pt->y = (LONG)((y + 0.5) * r.bottom / 480.0);
        ClientToScreen(g_wnd, pt); return;
    }
    s = (double)r.right / 640.0; if ((double)r.bottom / 480.0 < s) s = (double)r.bottom / 480.0;
    ox = (r.right - 640.0 * s) / 2.0; oy = (r.bottom - 480.0 * s) / 2.0;
    pt->x = (LONG)(ox + (x + 0.5) * s); pt->y = (LONG)(oy + (y + 0.5) * s);
    ClientToScreen(g_wnd, pt);
}
static void fg(void) { if (g_wnd) { SetForegroundWindow(g_wnd); SetActiveWindow(g_wnd); } }
static void cmd_pclick(int x, int y) {   /* PostMessage the button down/up straight to the game window (no SendInput) */
    POINT pt, cl; client_map(x, y, &pt); cl = pt; ScreenToClient(g_wnd, &cl);
    SetCursorPos(pt.x, pt.y); Sleep(100);
    PostMessageA(g_wnd, WM_MOUSEMOVE, 0, MAKELPARAM(cl.x, cl.y)); Sleep(150);
    PostMessageA(g_wnd, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(cl.x, cl.y)); Sleep(100);
    PostMessageA(g_wnd, WM_LBUTTONUP, 0, MAKELPARAM(cl.x, cl.y));
    printf("pclick UI %d,%d -> client %ld,%ld\n", x, y, cl.x, cl.y);
}
static void cmd_click(int x, int y) {
    POINT pt; INPUT in[3]; int sw = GetSystemMetrics(SM_CXVIRTUALSCREEN), sh = GetSystemMetrics(SM_CYVIRTUALSCREEN);
    int vx = GetSystemMetrics(SM_XVIRTUALSCREEN), vy = GetSystemMetrics(SM_YVIRTUALSCREEN);
    client_map(x, y, &pt); fg();
    memset(in, 0, sizeof(in));
    if (getenv("I76PROBE_NOMOVE")) {   /* buttons only: the pointer was put there by other means (mac: cur warp) */
        int hold = atoi(getenv("I76PROBE_NOMOVE")); if (hold < 50) hold = 90;
        in[1].type = INPUT_MOUSE; in[1].mi.dwFlags = MOUSEEVENTF_LEFTDOWN; SendInput(1, &in[1], sizeof(INPUT)); Sleep(hold);
        in[2].type = INPUT_MOUSE; in[2].mi.dwFlags = MOUSEEVENTF_LEFTUP; SendInput(1, &in[2], sizeof(INPUT));
        printf("buttons only at UI %d,%d (screen %ld,%ld)\n", x, y, pt.x, pt.y); return;
    }
    SetCursorPos(pt.x, pt.y); Sleep(120);
    in[0].type = INPUT_MOUSE; in[0].mi.dx = (LONG)((pt.x - vx) * 65535.0 / (sw - 1)); in[0].mi.dy = (LONG)((pt.y - vy) * 65535.0 / (sh - 1));
    in[0].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
    SendInput(1, in, sizeof(INPUT)); Sleep(120);
    {   /* I76PROBE_SETTLE=<ms>: two more absolute moves (1 px off, then on target) and a wait, so a game that
         * polls the pointer (DxWnd / DirectInput) has seen the new position before the button goes down */
        const char *st = getenv("I76PROBE_SETTLE"); int ms = st ? atoi(st) : 0;
        if (ms > 0) {
            INPUT m = in[0]; m.mi.dx += 40; SendInput(1, &m, sizeof(INPUT)); Sleep(ms / 2);
            SetCursorPos(pt.x, pt.y); SendInput(1, in, sizeof(INPUT)); Sleep(ms);
        }
    }
    in[1].type = INPUT_MOUSE; in[1].mi.dwFlags = MOUSEEVENTF_LEFTDOWN; SendInput(1, &in[1], sizeof(INPUT)); Sleep(90);
    in[2].type = INPUT_MOUSE; in[2].mi.dwFlags = MOUSEEVENTF_LEFTUP; SendInput(1, &in[2], sizeof(INPUT));
    { POINT c; GetCursorPos(&c); printf("click UI %d,%d -> screen %ld,%ld (cursor now %ld,%ld)\n", x, y, pt.x, pt.y, c.x, c.y); }
}
static int g_xkey;   /* xkey: send as an extended key (KEYEVENTF_EXTENDEDKEY), as a real keyboard's arrow / Ins / Del block does */
static void key(WORD vk, int ms) {
    INPUT in; memset(&in, 0, sizeof(in));
    in.type = INPUT_KEYBOARD; in.ki.wVk = vk; in.ki.wScan = (WORD)MapVirtualKeyA(vk, 0);
    if (g_xkey) in.ki.dwFlags = KEYEVENTF_EXTENDEDKEY;
    SendInput(1, &in, sizeof(INPUT)); Sleep(ms);
    in.ki.dwFlags |= KEYEVENTF_KEYUP; SendInput(1, &in, sizeof(INPUT)); Sleep(60);
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
    if (!strcmp(argv[1], "wins")) {
        POINT c; GUITHREADINFO gi; gi.cbSize = sizeof(gi);
        g_list = 1; g_pid = find_pid(); EnumWindows(enum_cb, 0); GetCursorPos(&c);
        GetGUIThreadInfo(0, &gi);
        printf("foreground %p active %p focus %p capture %p cursor %ld,%ld\n", (void *)GetForegroundWindow(), (void *)gi.hwndActive,
               (void *)gi.hwndFocus, (void *)gi.hwndCapture, c.x, c.y);
        return 0;
    }
    if (!attach()) return 1;
    if (!strcmp(argv[1], "state")) cmd_state();
    else if (!strcmp(argv[1], "shell")) cmd_shell();
    else if (!strcmp(argv[1], "pos")) cmd_pos();
    else if (!strcmp(argv[1], "move") && argc > 3) { POINT pt; client_map(atoi(argv[2]), atoi(argv[3]), &pt); fg(); SetCursorPos(pt.x, pt.y); printf("cursor -> %ld,%ld\n", pt.x, pt.y); }
    else if (!strcmp(argv[1], "shot") && argc > 2) cmd_shot(argv[2]);
    else if (!strcmp(argv[1], "find") && argc > 2) cmd_find(argv[2]);
    else if (!strcmp(argv[1], "peek") && argc > 2) {   /* peek <addr|shell+off> [dwords]: hex dwords */
        DWORD a = (DWORD)strtoul(argv[2], NULL, 16), n = argc > 3 ? (DWORD)atoi(argv[3]) : 16, i;
        if (!strncmp(argv[2], "shell+", 6)) a = shell_base() + (DWORD)strtoul(argv[2] + 6, NULL, 16);
        for (i = 0; i < n; i++) printf("%s%08lx", i % 8 ? " " : (i ? "\n" : ""), (unsigned long)ri(a + 4 * i));
        printf("\n");
    }
    else if (!strcmp(argv[1], "dump") && argc > 4) {   /* dump <addr> <len> <file>: raw bytes */
        DWORD a = (DWORD)strtoul(argv[2], NULL, 16), n = (DWORD)strtoul(argv[3], NULL, 0); BYTE *b = (BYTE *)malloc(n); SIZE_T got = 0; FILE *f;
        ReadProcessMemory(g_proc, (LPCVOID)(ULONG_PTR)a, b, n, &got); f = fopen(argv[4], "wb");
        if (f) { fwrite(b, 1, got, f); fclose(f); } printf("dumped %lu of %lu bytes from 0x%08lx\n", (unsigned long)got, (unsigned long)n, (unsigned long)a);
    }
    else if (!strcmp(argv[1], "stack")) {              /* every thread: EIP and the stack words that point into a module */
        THREADENTRY32 te; HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0); MODULEENTRY32 me; HANDLE ms;
        struct { DWORD b, e; char n[32]; } mod[64]; int nm = 0, k;
        me.dwSize = sizeof(me); ms = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, g_pid);
        if (ms != INVALID_HANDLE_VALUE && Module32First(ms, &me)) do if (nm < 64) {
            mod[nm].b = (DWORD)(ULONG_PTR)me.modBaseAddr; mod[nm].e = mod[nm].b + me.modBaseSize; lstrcpynA(mod[nm].n, me.szModule, 32); nm++; } while (Module32Next(ms, &me));
        te.dwSize = sizeof(te);
        if (Thread32First(s, &te)) do if (te.th32OwnerProcessID == g_pid) {
            HANDLE t = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID);
            CONTEXT c; DWORD w[768], i; int shown = 0;
            if (!t) continue;
            c.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER; SuspendThread(t);
            if (GetThreadContext(t, &c)) {
                printf("thread %lu eip %08lx esp %08lx:", (unsigned long)te.th32ThreadID, (unsigned long)c.Eip, (unsigned long)c.Esp);
                for (k = 0; k < nm; k++) if (c.Eip >= mod[k].b && c.Eip < mod[k].e) printf(" [%s+%lx]", mod[k].n, (unsigned long)(c.Eip - mod[k].b));
                memset(w, 0, sizeof(w)); rd(c.Esp, w, sizeof(w));
                for (i = 0; i < 768 && shown < 24; i++) for (k = 0; k < nm; k++) if (w[i] >= mod[k].b && w[i] < mod[k].e &&
                    (!_stricmp(mod[k].n, "i76shell.dll") || !_stricmp(mod[k].n, "i76.exe") || !_stricmp(mod[k].n, "anetdll.dll") ||
                     !_strnicmp(mod[k].n, "strlkup", 7) || !_stricmp(mod[k].n, "u32x.dll") || !_strnicmp(mod[k].n, "winet", 5) ||
                     !_strnicmp(mod[k].n, "wipx", 4) || !_stricmp(mod[k].n, "ipxwrapper.dll"))) {
                    printf(" %s+%lx", mod[k].n, (unsigned long)(w[i] - mod[k].b)); shown++; }
                printf("\n");
            }
            ResumeThread(t); CloseHandle(t);
        } while (Thread32Next(s, &te));
    }
    else if (!strcmp(argv[1], "poke") && argc > 3) {   /* poke <addr> <dword-hex>...: write, then read back */
        DWORD a = (DWORD)strtoul(argv[2], NULL, 16); int i; SIZE_T wr;
        for (i = 3; i < argc; i++) { DWORD v = (DWORD)strtoul(argv[i], NULL, 16);
            WriteProcessMemory(g_proc, (LPVOID)(ULONG_PTR)(a + 4 * (i - 3)), &v, 4, &wr);
            printf("0x%08lx <- %08lx, reads %08lx\n", (unsigned long)(a + 4 * (i - 3)), (unsigned long)v, (unsigned long)ri(a + 4 * (i - 3))); }
    }
    else if (!strcmp(argv[1], "showwin") && argc > 2) {  /* showwin <SW_ n>: ShowWindow on the game window (6 = minimise,
                                                           9 = restore); nitro-mac lane 2026-10-22, the launch stubs' quit test */
        BOOL was = ShowWindow(g_wnd, atoi(argv[2]));
        printf("showwin %d on %p: was visible %d, iconic now %d\n", atoi(argv[2]), (void *)g_wnd, was, IsIconic(g_wnd));
    }
    else if (!strcmp(argv[1], "mclick") && argc > 3) { /* mclick x y: hold the shell's mouse object at UI x,y (rewritten
                                                          every ~1 ms, the game rewrites it every frame), press, release */
        DWORD b = shell_base(), mo; int x = atoi(argv[2]), y = atoi(argv[3]), k; SIZE_T wr; INPUT in;
        int hold = getenv("I76PROBE_MCLICK_HOLD") ? atoi(getenv("I76PROBE_MCLICK_HOLD")) : 300;
        DWORD t0;
        /* I76PROBE_MO_PTR=<hex>: the address holding the mouse object's pointer (Nitro: NITSHELL base + 0x130484,
         * nitro-mac lane 2026-10-21); default Gold's i76shell+0xcc514 */
        if (getenv("I76PROBE_MO_PTR")) mo = (DWORD)ri((DWORD)strtoul(getenv("I76PROBE_MO_PTR"), NULL, 16));
        else { if (!b) { printf("no shell\n"); return 1; } mo = (DWORD)ri(0x100cc514 + b - 0x10000000); }
        if (!mo) { printf("no mouse object\n"); return 1; }
#define MHOLD(ms) for (t0 = GetTickCount(); GetTickCount() - t0 < (DWORD)(ms);) { WriteProcessMemory(g_proc, (LPVOID)(ULONG_PTR)(mo + 0x2c), &x, 4, &wr); \
            WriteProcessMemory(g_proc, (LPVOID)(ULONG_PTR)(mo + 0x30), &y, 4, &wr); Sleep(1); }
        fg(); MHOLD(150);
        memset(&in, 0, sizeof(in)); in.type = INPUT_MOUSE; in.mi.dwFlags = MOUSEEVENTF_LEFTDOWN; SendInput(1, &in, sizeof(INPUT));
        MHOLD(hold);
        in.mi.dwFlags = MOUSEEVENTF_LEFTUP; SendInput(1, &in, sizeof(INPUT));
        MHOLD(150);
#undef MHOLD
        printf("mclick %d,%d: mouse object now %d,%d\n", x, y, ri(mo + 0x2c), ri(mo + 0x30));
    }
    else if (!strcmp(argv[1], "boxtext")) {            /* every dialog (#32770) of the game: title and its controls' text */
        HWND h = NULL; char t[512];
        while ((h = FindWindowExA(NULL, h, "#32770", NULL)) != NULL) {
            DWORD pid; HWND c = NULL; GetWindowThreadProcessId(h, &pid); if (pid != g_pid) continue;
            GetWindowTextA(h, t, sizeof(t)); printf("box %p '%s':", (void *)h, t);
            while ((c = FindWindowExA(h, c, NULL, NULL)) != NULL) { GetWindowTextA(c, t, sizeof(t)); if (*t) printf(" [%s]", t); }
            printf("\n");
        }
    }
    else if (!strcmp(argv[1], "mods")) {               /* loaded modules: base, size, name */
        MODULEENTRY32 me; HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, g_pid);
        me.dwSize = sizeof(me);
        if (s != INVALID_HANDLE_VALUE && Module32First(s, &me)) do printf("0x%08lx %7lu %s\n", (unsigned long)(ULONG_PTR)me.modBaseAddr,
            (unsigned long)me.modBaseSize, me.szModule); while (Module32Next(s, &me));
    }
    else if (!strcmp(argv[1], "regions")) {            /* committed private regions >= 256 KB (candidate frame buffers) */
        MEMORY_BASIC_INFORMATION mi; ULONG_PTR a = 0x10000;
        while (a < 0x7fff0000 && VirtualQueryEx(g_proc, (LPCVOID)a, &mi, sizeof(mi)) == sizeof(mi)) {
            if (mi.State == MEM_COMMIT && mi.RegionSize >= 0x40000) printf("0x%08lx %8lu KB type 0x%lx prot 0x%lx\n",
                (unsigned long)(ULONG_PTR)mi.BaseAddress, (unsigned long)(mi.RegionSize >> 10), mi.Type, mi.Protect);
            a = (ULONG_PTR)mi.BaseAddress + mi.RegionSize;
        }
    }
    else if (!strcmp(argv[1], "deskshot") && argc > 2) { g_desk = 1; cmd_shot(argv[2]); }
    else if (!strcmp(argv[1], "pclick") && argc > 3) cmd_pclick(atoi(argv[2]), atoi(argv[3]));
    else if (!strcmp(argv[1], "click") && argc > 3) cmd_click(atoi(argv[2]), atoi(argv[3]));
    else if (!strcmp(argv[1], "pmsg") && argc > 4) {   /* pmsg <msg-hex> x y: SetCursorPos there, then PostMessage one mouse
                                                          message (e.g. 201 = button down only: hit-test a menu without the
                                                          button-up that would activate the item) */
        POINT pt, cl; UINT m = (UINT)strtoul(argv[2], NULL, 16); client_map(atoi(argv[3]), atoi(argv[4]), &pt); cl = pt; ScreenToClient(g_wnd, &cl);
        SetCursorPos(pt.x, pt.y); Sleep(100);
        PostMessageA(g_wnd, m, m == WM_LBUTTONDOWN ? MK_LBUTTON : 0, MAKELPARAM(cl.x, cl.y));
        printf("pmsg 0x%x client %ld,%ld\n", m, cl.x, cl.y);
    }
    else if (!strcmp(argv[1], "xkey") && argc > 2) { g_xkey = 1; fg(); key((WORD)strtol(argv[2], NULL, 16), argc > 3 ? atoi(argv[3]) : 80); printf("xkey %s\n", argv[2]); }
    else if (!strcmp(argv[1], "key") && argc > 2) { fg(); key((WORD)strtol(argv[2], NULL, 16), argc > 3 ? atoi(argv[3]) : 80); printf("key %s\n", argv[2]); }
    else if (!strcmp(argv[1], "type") && argc > 2) { const char *p; fg(); for (p = argv[2]; *p; p++) { SHORT v = VkKeyScanA(*p); key((WORD)(v & 0xff), 60); } printf("typed\n"); }
    else if (!strcmp(argv[1], "throttle") && argc > 3) {
        int v = atoi(argv[2]), ms = atoi(argv[3]), t; SIZE_T n;
        for (t = 0; t < ms; t += 20) { WriteProcessMemory(g_proc, (LPVOID)0x5367CC, &v, 4, &n); Sleep(20); }
        v = 0; WriteProcessMemory(g_proc, (LPVOID)0x5367CC, &v, 4, &n); printf("throttle written for %d ms\n", ms);
    } else { printf("bad command\n"); return 2; }
    return 0;
}
