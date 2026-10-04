/*
 * find-reads.exe <pid> <seconds> <addr1> [addr2] [addr3] [addr4]
 *
 * Attaches as a debugger and sets a HARDWARE data breakpoint (Dr0..Dr3, break on
 * read/write, 4 bytes) on each address. Every time the game reads/writes one, the
 * CPU traps; we log the instruction pointer (EIP) that did it. Prints a histogram of
 * EIP -> count per address at the end. That tells us EXACTLY which code reads a given
 * position copy - so we can see whether render_scene (0x004621E0) is among the readers.
 *
 * Build (32-bit, to match i76.exe):  cl /nologo /O2 find-reads.c
 * Detaches cleanly (clears the debug registers, sets kill-on-exit FALSE) so the game
 * keeps running afterwards.
 */
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>

#define MAXBP 4
static DWORD  g_addr[MAXBP];
static int    g_naddr = 0;

/* histogram of (eip, which-address) -> count */
#define MAXH 4096
static struct { DWORD eip; int which; unsigned count; } g_hist[MAXH];
static int g_nhist = 0;

static void tally(DWORD eip, int which) {
    for (int i = 0; i < g_nhist; i++)
        if (g_hist[i].eip == eip && g_hist[i].which == which) { g_hist[i].count++; return; }
    if (g_nhist < MAXH) { g_hist[g_nhist].eip = eip; g_hist[g_nhist].which = which; g_hist[g_nhist].count = 1; g_nhist++; }
}

/* Build Dr7 enabling each used Dr as a 4-byte read/write breakpoint. */
static DWORD make_dr7(void) {
    DWORD dr7 = 0;
    for (int i = 0; i < g_naddr; i++) {
        dr7 |= (1u << (i * 2));                 /* Ln local enable            */
        dr7 |= (3u << (16 + i * 4));            /* RWn = 11 read/write        */
        dr7 |= (3u << (18 + i * 4));            /* LENn = 11 four bytes       */
    }
    return dr7;
}

static void set_bp_on_thread(DWORD tid) {
    HANDLE t = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME, FALSE, tid);
    if (!t) return;
    CONTEXT c; c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (GetThreadContext(t, &c)) {
        if (g_naddr > 0) c.Dr0 = g_addr[0];
        if (g_naddr > 1) c.Dr1 = g_addr[1];
        if (g_naddr > 2) c.Dr2 = g_addr[2];
        if (g_naddr > 3) c.Dr3 = g_addr[3];
        c.Dr7 = make_dr7();
        c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
        SetThreadContext(t, &c);
    }
    CloseHandle(t);
}

static void clear_bp_on_thread(DWORD tid) {
    HANDLE t = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT, FALSE, tid);
    if (!t) return;
    CONTEXT c; c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (GetThreadContext(t, &c)) { c.Dr0 = c.Dr1 = c.Dr2 = c.Dr3 = 0; c.Dr7 = 0; SetThreadContext(t, &c); }
    CloseHandle(t);
}

static void for_each_thread(DWORD pid, void (*fn)(DWORD)) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) return;
    THREADENTRY32 te; te.dwSize = sizeof(te);
    if (Thread32First(snap, &te)) {
        do { if (te.th32OwnerProcessID == pid) fn(te.th32ThreadID); } while (Thread32Next(snap, &te));
    }
    CloseHandle(snap);
}

static int which_dr(DWORD dr6) {
    if (dr6 & 1) return 0;
    if (dr6 & 2) return 1;
    if (dr6 & 4) return 2;
    if (dr6 & 8) return 3;
    return -1;
}

int main(int argc, char** argv) {
    if (argc < 4) { printf("usage: find-reads <pid> <seconds> <addr1> [addr2..4]\n"); return 1; }
    DWORD pid = strtoul(argv[1], 0, 0);
    int seconds = atoi(argv[2]);
    for (int i = 3; i < argc && g_naddr < MAXBP; i++) g_addr[g_naddr++] = strtoul(argv[i], 0, 16);

    printf("attaching to pid %lu, %d addr(s), %d s:\n", pid, g_naddr, seconds);
    for (int i = 0; i < g_naddr; i++) printf("  Dr%d = 0x%08lX\n", i, g_addr[i]);

    DebugSetProcessKillOnExit(FALSE);
    if (!DebugActiveProcess(pid)) { printf("DebugActiveProcess failed: %lu\n", GetLastError()); return 1; }

    for_each_thread(pid, set_bp_on_thread);

    DWORD start = GetTickCount();
    unsigned long total = 0;
    DEBUG_EVENT ev;
    for (;;) {
        if (!WaitForDebugEvent(&ev, 200)) {
            if (GetTickCount() - start > (DWORD)seconds * 1000) break;
            continue;
        }
        DWORD status = DBG_CONTINUE;
        if (ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT) {
            EXCEPTION_RECORD* er = &ev.u.Exception.ExceptionRecord;
            if (er->ExceptionCode == EXCEPTION_SINGLE_STEP) {
                HANDLE t = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT, FALSE, ev.dwThreadId);
                if (t) {
                    CONTEXT c; c.ContextFlags = CONTEXT_DEBUG_REGISTERS | CONTEXT_CONTROL;
                    if (GetThreadContext(t, &c)) {
                        int w = which_dr(c.Dr6);
                        if (w >= 0) { tally(c.Eip, w); total++; }
                        c.Dr6 = 0; c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
                        SetThreadContext(t, &c);
                    }
                    CloseHandle(t);
                } else {
                    status = DBG_EXCEPTION_NOT_HANDLED;
                }
            } else if (er->ExceptionCode != EXCEPTION_BREAKPOINT) {
                status = DBG_EXCEPTION_NOT_HANDLED;   /* pass real faults to the game */
            }
        } else if (ev.dwDebugEventCode == CREATE_THREAD_DEBUG_EVENT) {
            set_bp_on_thread(ev.dwThreadId);
        }
        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, status);
        if (GetTickCount() - start > (DWORD)seconds * 1000) break;
        if (total > 200000) { printf("hit cap 200000\n"); break; }
    }

    for_each_thread(pid, clear_bp_on_thread);
    DebugActiveProcessStop(pid);

    /* sort histogram by count, desc (simple selection sort, small N) */
    for (int i = 0; i < g_nhist; i++)
        for (int j = i + 1; j < g_nhist; j++)
            if (g_hist[j].count > g_hist[i].count) {
                DWORD e = g_hist[i].eip; int w = g_hist[i].which; unsigned c = g_hist[i].count;
                g_hist[i] = g_hist[j];
                g_hist[j].eip = e; g_hist[j].which = w; g_hist[j].count = c;
            }
    printf("\ntotal hits: %lu, distinct read/write sites: %d\n", total, g_nhist);
    printf("%-6s %-12s %-10s\n", "addr#", "EIP", "count");
    for (int i = 0; i < g_nhist && i < 40; i++)
        printf("Dr%d    0x%08lX   %u\n", g_hist[i].which, g_hist[i].eip, g_hist[i].count);
    return 0;
}
