/*
 * inputrec.exe - record and replay real keyboard/mouse input, with timing.
 *
 *   inputrec rec  <file> [seconds]   record global input until F12 or timeout
 *   inputrec play <file> [speed]     replay it (speed 1.0 = original timing)
 *
 * WHY: some things cannot be automated blind - lining up the training-mission jump, or
 * navigating a fiddly garage UI whose hotspots we cannot find. A human does it ONCE, and the
 * recording can then be replayed identically at 20 Hz and at 60 Hz, which is exactly the
 * controlled A/B the physics comparisons need.
 *
 * Uses low-level hooks (WH_KEYBOARD_LL / WH_MOUSE_LL) so it captures input no matter which
 * window has focus, and SendInput to replay. Mouse is recorded as ABSOLUTE screen position:
 * I'76 maps the cursor into its own space, and absolute positioning is what the menu clicks
 * were calibrated against.
 *
 * Build (32-bit to match the rest of the lab): cl /nologo /O2 inputrec.c user32.lib
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

#define MAXEV 200000
typedef struct { double t; int type; int a, b, c; } Ev;
/* type: 0 = key, 1 = mouse move, 2 = mouse button, 3 = wheel */
static Ev*    g_ev;
static int    g_n = 0;
static double g_freq, g_t0;
static HHOOK  g_kb, g_ms;
static int    g_stop = 0;
static double g_limit = 0;

static double now(void){ LARGE_INTEGER c; QueryPerformanceCounter(&c); return (double)c.QuadPart / g_freq; }

static void add(int type, int a, int b, int c){
    if(g_n >= MAXEV) return;
    g_ev[g_n].t = now() - g_t0;
    g_ev[g_n].type = type; g_ev[g_n].a = a; g_ev[g_n].b = b; g_ev[g_n].c = c;
    g_n++;
}

static LRESULT CALLBACK kb_proc(int code, WPARAM w, LPARAM l){
    if(code == HC_ACTION){
        KBDLLHOOKSTRUCT* k = (KBDLLHOOKSTRUCT*)l;
        int up = (w == WM_KEYUP || w == WM_SYSKEYUP);
        if(k->vkCode == VK_F12 && !up) g_stop = 1;      /* F12 ends the recording */
        else add(0, (int)k->vkCode, up, (int)k->scanCode);
    }
    return CallNextHookEx(g_kb, code, w, l);
}
static LRESULT CALLBACK ms_proc(int code, WPARAM w, LPARAM l){
    if(code == HC_ACTION){
        MSLLHOOKSTRUCT* m = (MSLLHOOKSTRUCT*)l;
        switch(w){
            case WM_MOUSEMOVE:   add(1, m->pt.x, m->pt.y, 0); break;
            case WM_LBUTTONDOWN: add(2, 0, 0, 0); break;
            case WM_LBUTTONUP:   add(2, 0, 1, 0); break;
            case WM_RBUTTONDOWN: add(2, 1, 0, 0); break;
            case WM_RBUTTONUP:   add(2, 1, 1, 0); break;
            case WM_MOUSEWHEEL:  add(3, GET_WHEEL_DELTA_WPARAM(m->mouseData), 0, 0); break;
        }
    }
    return CallNextHookEx(g_ms, code, w, l);
}

static int do_record(const char* path, double seconds){
    g_ev = (Ev*)malloc(sizeof(Ev) * MAXEV);
    if(!g_ev){ printf("out of memory\n"); return 1; }
    g_limit = seconds;
    g_kb = SetWindowsHookExA(WH_KEYBOARD_LL, kb_proc, GetModuleHandle(NULL), 0);
    g_ms = SetWindowsHookExA(WH_MOUSE_LL,    ms_proc, GetModuleHandle(NULL), 0);
    if(!g_kb || !g_ms){ printf("SetWindowsHookEx failed %lu\n", GetLastError()); return 1; }
    g_t0 = now();
    printf("RECORDING to %s - press F12 to stop", path);
    if(seconds > 0) printf(" (or %.0f s)", seconds);
    printf("\n"); fflush(stdout);

    MSG msg;
    for(;;){
        while(PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)){ TranslateMessage(&msg); DispatchMessage(&msg); }
        if(g_stop) break;
        if(seconds > 0 && (now() - g_t0) > seconds) break;
        Sleep(1);
    }
    UnhookWindowsHookEx(g_kb); UnhookWindowsHookEx(g_ms);

    FILE* f = fopen(path, "w");
    if(!f){ printf("cannot write %s\n", path); return 1; }
    fprintf(f, "t_ms,type,a,b,c\n");
    for(int i = 0; i < g_n; i++)
        fprintf(f, "%.3f,%d,%d,%d,%d\n", g_ev[i].t * 1000.0, g_ev[i].type, g_ev[i].a, g_ev[i].b, g_ev[i].c);
    fclose(f);
    printf("recorded %d events over %.2f s -> %s\n", g_n, now() - g_t0, path);
    return 0;
}

static void send_key(int vk, int scan, int up){
    INPUT in; memset(&in, 0, sizeof(in));
    in.type = INPUT_KEYBOARD;
    in.ki.wVk = (WORD)vk;
    in.ki.wScan = (WORD)scan;
    in.ki.dwFlags = (up ? KEYEVENTF_KEYUP : 0);
    SendInput(1, &in, sizeof(INPUT));
}
static void send_button(int btn, int up){
    INPUT in; memset(&in, 0, sizeof(in));
    in.type = INPUT_MOUSE;
    if(btn == 0) in.mi.dwFlags = up ? MOUSEEVENTF_LEFTUP : MOUSEEVENTF_LEFTDOWN;
    else         in.mi.dwFlags = up ? MOUSEEVENTF_RIGHTUP : MOUSEEVENTF_RIGHTDOWN;
    SendInput(1, &in, sizeof(INPUT));
}

static int do_play(const char* path, double speed){
    FILE* f = fopen(path, "r");
    if(!f){ printf("cannot read %s\n", path); return 1; }
    char line[256];
    if(!fgets(line, sizeof(line), f)){ fclose(f); return 1; }   /* header */
    g_ev = (Ev*)malloc(sizeof(Ev) * MAXEV);
    g_n = 0;
    while(fgets(line, sizeof(line), f) && g_n < MAXEV){
        double t; int ty, a, b, c;
        if(sscanf(line, "%lf,%d,%d,%d,%d", &t, &ty, &a, &b, &c) == 5){
            g_ev[g_n].t = t / 1000.0; g_ev[g_n].type = ty;
            g_ev[g_n].a = a; g_ev[g_n].b = b; g_ev[g_n].c = c; g_n++;
        }
    }
    fclose(f);
    if(speed <= 0) speed = 1.0;
    printf("replaying %d events at %.2fx\n", g_n, speed);
    double start = now();
    for(int i = 0; i < g_n; i++){
        double due = g_ev[i].t / speed;
        for(;;){
            double wait = due - (now() - start);
            if(wait <= 0) break;
            if(wait > 0.003) Sleep((DWORD)((wait - 0.002) * 1000.0)); else Sleep(0);
        }
        switch(g_ev[i].type){
            case 0: send_key(g_ev[i].a, g_ev[i].c, g_ev[i].b); break;
            case 1: SetCursorPos(g_ev[i].a, g_ev[i].b); break;
            case 2: send_button(g_ev[i].a, g_ev[i].b); break;
            case 3: { INPUT in; memset(&in,0,sizeof(in)); in.type=INPUT_MOUSE;
                      in.mi.dwFlags=MOUSEEVENTF_WHEEL; in.mi.mouseData=g_ev[i].a;
                      SendInput(1,&in,sizeof(INPUT)); } break;
        }
    }
    printf("replay done in %.2f s\n", now() - start);
    return 0;
}

int main(int argc, char** argv){
    LARGE_INTEGER fq; QueryPerformanceFrequency(&fq); g_freq = (double)fq.QuadPart;
    if(argc < 3){
        printf("usage:\n  inputrec rec  <file> [seconds]\n  inputrec play <file> [speed]\n");
        return 1;
    }
    if(!strcmp(argv[1], "rec"))  return do_record(argv[2], argc > 3 ? atof(argv[3]) : 0);
    if(!strcmp(argv[1], "play")) return do_play(argv[2], argc > 3 ? atof(argv[3]) : 1.0);
    printf("unknown mode '%s'\n", argv[1]);
    return 1;
}
