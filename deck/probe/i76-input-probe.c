/* i76-input-probe: measures EXACTLY what Interstate '76 would see, at the same
 * Windows API boundaries the game uses (winmm joystick + user32 keyboard/mouse).
 * Run it as a Steam shortcut with the SAME controller config as the game:
 * whatever this logs IS what Steam Input + Proton deliver. Whatever differs
 * in-game after that is the game's own input.map layer.
 *
 * Logs to console AND i76-probe.log next to the exe. Runs 120 s.
 * Build: i686-w64-mingw32-gcc i76-input-probe.c -o i76-input-probe.exe -lwinmm -static
 */
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <string.h>

static FILE *lf;
static DWORD t0;
static void logline(const char *fmt, ...) {
    va_list ap; char buf[512];
    va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
    DWORD t = GetTickCount() - t0;
    printf("[%6lu.%03lus] %s\n", t/1000, t%1000, buf);
    if (lf) { fprintf(lf, "[%6lu.%03lus] %s\n", t/1000, t%1000, buf); fflush(lf); }
}

struct keydef { int vk; const char *name; };
static struct keydef keys[] = {
    {VK_SPACE,"SPACE"},{VK_RETURN,"ENTER"},{VK_ESCAPE,"ESC"},{VK_TAB,"TAB"},
    {VK_UP,"UP"},{VK_DOWN,"DOWN"},{VK_LEFT,"LEFT"},{VK_RIGHT,"RIGHT"},
    {'W',"W"},{'A',"A"},{'S',"S"},{'D',"D"},{'C',"C"},{'X',"X"},{'V',"V"},
    {'F',"F"},{'M',"M"},{'N',"N"},{'R',"R"},{'K',"K"},{'I',"I"},{'H',"H"},
    {'G',"G"},{'B',"B"},{'Q',"Q"},{'T',"T"},{'Y',"Y"},{'U',"U"},
    {VK_PRIOR,"PGUP"},{VK_NEXT,"PGDN"},
    {VK_LBUTTON,"MOUSE-L"},{VK_RBUTTON,"MOUSE-R"},{VK_MBUTTON,"MOUSE-M"},
};
#define NKEYS (sizeof keys / sizeof keys[0])

int main(void) {
    t0 = GetTickCount();
    lf = fopen("i76-probe.log", "w");
    logline("=== I76 INPUT PROBE start (120s). Press every input now. ===");

    UINT ndev = joyGetNumDevs();
    logline("winmm joyGetNumDevs = %u", ndev);
    JOYCAPSA caps;
    int present[4] = {0,0,0,0};
    for (UINT id = 0; id < 4 && id < ndev; id++) {
        JOYINFOEX ji; ji.dwSize = sizeof ji; ji.dwFlags = JOY_RETURNALL;
        MMRESULT r = joyGetPosEx(id, &ji);
        if (r == JOYERR_NOERROR) {
            present[id] = 1;
            joyGetDevCapsA(id, &caps, sizeof caps);
            logline("JOYSTICK id=%u PRESENT name='%s' axes=%lu btns=%lu Xrange=%lu-%lu",
                    id, caps.szPname, caps.wNumAxes, caps.wNumButtons, caps.wXmin, caps.wXmax);
        } else {
            logline("joystick id=%u absent (err %u)", id, r);
        }
    }

    DWORD lastX[4]={0}, lastY[4]={0}, lastZ[4]={0}, lastR[4]={0}, lastB[4]={0}, lastPOV[4]={0};
    SHORT kprev[NKEYS]; memset(kprev, 0, sizeof kprev);
    POINT mprev = {0,0}; GetCursorPos(&mprev);
    DWORD lastHeartbeat = 0;

    while (GetTickCount() - t0 < 120000) {
        /* joystick axes/buttons, log on change beyond jitter */
        for (UINT id = 0; id < 4; id++) {
            if (!present[id]) continue;
            JOYINFOEX ji; ji.dwSize = sizeof ji; ji.dwFlags = JOY_RETURNALL;
            if (joyGetPosEx(id, &ji) != JOYERR_NOERROR) continue;
            #define MOVED(a,b) ((a)>(b)?(a)-(b):(b)-(a)) > 1200
            if (MOVED(ji.dwXpos,lastX[id]) || MOVED(ji.dwYpos,lastY[id]) ||
                MOVED(ji.dwZpos,lastZ[id]) || MOVED(ji.dwRpos,lastR[id]) ||
                ji.dwButtons != lastB[id] || ji.dwPOV != lastPOV[id]) {
                logline("JOY%u X=%5lu Y=%5lu Z=%5lu R=%5lu U=%5lu V=%5lu btn=%08lx pov=%lu",
                        id, ji.dwXpos, ji.dwYpos, ji.dwZpos, ji.dwRpos,
                        ji.dwUpos, ji.dwVpos, ji.dwButtons, ji.dwPOV);
                lastX[id]=ji.dwXpos; lastY[id]=ji.dwYpos; lastZ[id]=ji.dwZpos;
                lastR[id]=ji.dwRpos; lastB[id]=ji.dwButtons; lastPOV[id]=ji.dwPOV;
            }
        }
        /* keys: transitions only */
        for (size_t i = 0; i < NKEYS; i++) {
            SHORT s = GetAsyncKeyState(keys[i].vk) & 0x8000;
            if (s && !kprev[i]) logline("KEY DOWN  %s", keys[i].name);
            if (!s && kprev[i]) logline("KEY UP    %s", keys[i].name);
            kprev[i] = s;
        }
        /* mouse position on move >8px */
        POINT p; GetCursorPos(&p);
        if (abs(p.x-mprev.x) > 8 || abs(p.y-mprev.y) > 8) {
            logline("MOUSE pos=(%ld,%ld)", p.x, p.y);
            mprev = p;
        }
        /* heartbeat every 10s so a silent log still proves the probe ran */
        DWORD el = GetTickCount() - t0;
        if (el - lastHeartbeat >= 10000) {
            logline("-- heartbeat: %lus elapsed, foreground=%p --", el/1000, (void*)GetForegroundWindow());
            lastHeartbeat = el;
        }
        Sleep(16);
    }
    logline("=== probe done ===");
    if (lf) fclose(lf);
    return 0;
}
