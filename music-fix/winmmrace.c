/* winmmrace.c - the winmmbase 26100.9549 start-up crash (Windows 11 24H2 26100.9711, 2026-10-24;
 * docs/records/DGVOODOO-UPDATE-2026-10-24.md s.4 and s.7). Included by strlkproxy.c after iat_slot().
 *
 * FIX: I76_WINMM_HEAPFIX (below). DIAGNOSTICS (I76_WINMM_TRACE=1, off by default): who the system winmmbase's GlobalAlloc / GlobalReAlloc / GlobalLock
 * imports resolve to, its driver-table count / handle, and a GlobalAlloc + GlobalLock done through those same pointers,
 * logged with the thread id and tick each time the proxy is about to make its first real winmm call, and again from the
 * crash handler when a fault lands in winmmbase. */
static int g_wmr_trace = -1;
static DWORD WINAPI wmr_watch(LPVOID arg);
static HANDLE g_wmr_pre;   /* set when the preload + sweep is done */
static int wmr_sweep(const char *when, int fix, int log);
static int wmr_trace_on(void) {
    if (g_wmr_trace < 0) { char v[8]; DWORD n = GetEnvironmentVariableA("I76_WINMM_TRACE", v, sizeof v); g_wmr_trace = n && v[0] == '1'; }
    return g_wmr_trace;
}
static const char *wmr_owner(const void *p, char *buf, int cap) {
    MEMORY_BASIC_INFORMATION mb; char path[MAX_PATH]; const char *b;
    if (!p || !VirtualQuery(p, &mb, sizeof mb) || mb.Type != MEM_IMAGE || !mb.AllocationBase) { _snprintf(buf, cap, "%p (no image)", p); return buf; }
    path[0] = 0; GetModuleFileNameA((HMODULE)mb.AllocationBase, path, sizeof path);
    b = strrchr(path, '\\'); b = b ? b + 1 : path;
    _snprintf(buf, cap, "%s+0x%lX", b, (unsigned long)((DWORD_PTR)p - (DWORD_PTR)mb.AllocationBase));
    return buf;
}
/* winmmbase 10.0.26100.9549: driver table count at +0x1d6d4, GlobalAlloc'd handle at +0x1d6d8 (fault +0x5AB3:
 * "cmp [edx+8], edi" on the pointer GlobalLock gave back for that handle). Only read when the fault bytes match. */
static HMODULE wmr_mod_of(const void *p);
static int wmr_is_sys(const void *p);
static int wmr_is_9549(BYTE *wb) {
    static const BYTE sig[] = { 0x39, 0x7A, 0x08, 0x75, 0x05, 0xF6, 0x02, 0x02 };   /* +0x5AB3 */
    return wb && !IsBadReadPtr(wb + 0x5AB3, sizeof sig) && memcmp(wb + 0x5AB3, sig, sizeof sig) == 0;
}
/* the Global* and Local* memory functions: name and the api set winmmbase 9549 takes it from (wmr_slot also tries the others).
 * Indices 0..5 keep the winmmbase layout the trace reads (Alloc Free ReAlloc Lock Unlock Handle). */
#define WMR_L2  "api-ms-win-core-heap-l2-1-0.dll"
#define WMR_OB  "api-ms-win-core-heap-obsolete-l1-1-0.dll"
static const struct { const char *fn; const char *dll; } g_wmr_imp[] = {
    { "GlobalAlloc", WMR_L2 }, { "GlobalFree", WMR_L2 }, { "GlobalReAlloc", WMR_OB }, { "GlobalLock", WMR_OB }, { "GlobalUnlock", WMR_OB },
    { "GlobalHandle", WMR_OB }, { "GlobalSize", WMR_OB }, { "GlobalFlags", WMR_OB },
    { "LocalAlloc", WMR_L2 }, { "LocalFree", WMR_L2 }, { "LocalReAlloc", WMR_L2 }, { "LocalLock", WMR_OB }, { "LocalUnlock", WMR_OB },
    { "LocalHandle", WMR_OB }, { "LocalSize", WMR_OB }, { "LocalFlags", WMR_OB } };
#define WMR_NIMP 16
#define WMR_NSHOW 8   /* the trace's per-slot line: the Global* ones */
static void **wmr_slot_raw(HMODULE wb, int i);
static void **wmr_iat(HMODULE mod, const char *dll, const char *func);
/* checked: the census walks every module, some of which (resource / data mappings, drivers) have import tables that do
 * not read as a normal image's (measured: a read fault in KERNELBASE's lstrcmpiA from the walk, 4 of 4 trace boots) */
static void **wmr_slot(HMODULE wb, int i) {
    MEMORY_BASIC_INFORMATION mb;
    if (!wb || ((DWORD_PTR)wb & 3) || !VirtualQuery(wb, &mb, sizeof mb) || mb.Type != MEM_IMAGE || mb.AllocationBase != (void *)wb) return NULL;
    return wmr_slot_raw(wb, i);
}
/* iat_slot with every RVA checked against SizeOfImage (no fault, so the crash log's one shot is never spent here) */
static void **wmr_iat(HMODULE mod, const char *dll, const char *func) {
    BYTE *base = (BYTE *)mod; IMAGE_NT_HEADERS *nt; IMAGE_DATA_DIRECTORY dd; IMAGE_IMPORT_DESCRIPTOR *d; DWORD sz;
    if (((IMAGE_DOS_HEADER *)base)->e_magic != IMAGE_DOS_SIGNATURE) return NULL;
    nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    if (IsBadReadPtr(nt, sizeof *nt) || nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) return NULL;
    sz = nt->OptionalHeader.SizeOfImage; dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dd.VirtualAddress || dd.VirtualAddress >= sz) return NULL;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress); (BYTE *)(d + 1) <= base + sz && d->Name; d++) {
        IMAGE_THUNK_DATA *oft, *ft; DWORD o = d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk;
        if (d->Name >= sz || o >= sz || d->FirstThunk >= sz) continue;
        if (lstrcmpiA((char *)(base + d->Name), dll) != 0) continue;
        oft = (IMAGE_THUNK_DATA *)(base + o); ft = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (; (BYTE *)(oft + 1) <= base + sz && oft->u1.AddressOfData; oft++, ft++) {
            if (oft->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            if (oft->u1.AddressOfData + 2 >= sz) continue;
            if (lstrcmpA((char *)((IMAGE_IMPORT_BY_NAME *)(base + oft->u1.AddressOfData))->Name, func) == 0) return (void **)&ft->u1.Function;
        }
    }
    return NULL;
}
static void **wmr_slot_raw(HMODULE wb, int i) {
    static const char *alt[] = { "kernel32.dll", "api-ms-win-core-heap-l1-1-0.dll", "api-ms-win-core-heap-l2-1-0.dll",
                                 "api-ms-win-core-heap-obsolete-l1-1-0.dll", "KERNELBASE.dll" };
    void **sl = wmr_iat(wb, g_wmr_imp[i].dll, g_wmr_imp[i].fn); int k;
    for (k = 0; !sl && k < 5; k++) sl = wmr_iat(wb, alt[k], g_wmr_imp[i].fn);
    return sl;
}
/* where a hook stub jumps (E9 rel32 / FF 25 [abs] / 68 imm32 C3), for the log */
static const void *wmr_stub_target(const BYTE *p) {
    if (!p || IsBadReadPtr(p, 6)) return NULL;
    if (p[0] == 0xE9) return p + 5 + *(const LONG *)(p + 1);
    if (p[0] == 0xFF && p[1] == 0x25 && !IsBadReadPtr(*(void *const *)(p + 2), 4)) return **(void **const *)(p + 2);
    if (p[0] == 0x68 && p[5] == 0xC3) return *(void *const *)(p + 1);
    return NULL;
}
static void wmr_state(const char *where) {
    HMODULE wb = GetModuleHandleA("winmmbase.dll");
    char line[1024]; int n = 0, i;
    if (!wb) { mlog("  winmm-trace %s: tid %lu t=%lu winmmbase not loaded", where, GetCurrentThreadId(), GetTickCount()); return; }
    for (i = 0; i < WMR_NSHOW; i++) {
        void **sl = wmr_slot(wb, i); char o[96], o2[96]; const void *tg = sl ? wmr_stub_target((const BYTE *)*sl) : NULL;
        n += _snprintf(line + n, sizeof line - n, "%s%s -> %s%s%s", i ? ", " : "", g_wmr_imp[i].fn,
                       sl ? wmr_owner(*sl, o, sizeof o) : "(no import)", tg ? " jmp " : "", tg ? wmr_owner(tg, o2, sizeof o2) : "");
        if (n >= (int)sizeof line - 100) break;
    }
    line[sizeof line - 1] = 0;
    {   /* what GetProcAddress (which a layer may hook) hands this module for the same six, from kernel32 and KERNELBASE */
        char g[2400]; int m = 0; HMODULE k32 = GetModuleHandleA("kernel32.dll"), kb = GetModuleHandleA("KERNELBASE.dll");
        for (i = 0; i < WMR_NIMP; i++) { char o[96], o2[96];
            if (m >= (int)sizeof g - 200) break;
            m += _snprintf(g + m, sizeof g - m, "%s%s k32 %s kb %s", i ? ", " : "", g_wmr_imp[i].fn,
                           wmr_owner(k32 ? (void *)GetProcAddress(k32, g_wmr_imp[i].fn) : NULL, o, sizeof o),
                           wmr_owner(kb ? (void *)GetProcAddress(kb, g_wmr_imp[i].fn) : NULL, o2, sizeof o2));
            if (m >= (int)sizeof g - 120) break; }
        g[sizeof g - 1] = 0;
        mlog("  winmm-trace %s: GetProcAddress: %s", where, g);
    }
    wmr_sweep(where, 0, 1);
    mlog("  winmm-trace %s: tid %lu t=%lu winmmbase %p%s; %s", where, GetCurrentThreadId(), GetTickCount(), (void *)wb,
         wmr_is_9549((BYTE *)wb) ? " (9549 layout)" : "", line);
    if (wmr_is_9549((BYTE *)wb)) {
        DWORD cnt = *(volatile DWORD *)((BYTE *)wb + 0x1d6d4); HGLOBAL h = *(HGLOBAL volatile *)((BYTE *)wb + 0x1d6d8);
        void **sl = wmr_slot(wb, 3); void *p = NULL; DWORD le = 0;
        if (h && sl) { SetLastError(0); p = ((LPVOID (WINAPI *)(HGLOBAL))*sl)(h); le = GetLastError(); if (p) GlobalUnlock(h); }
        mlog("  winmm-trace %s: driver table count %lu handle %p -> its GlobalLock %p (err %lu)", where, (unsigned long)cnt, (void *)h, p, (unsigned long)le);
    }
    {   /* the allocation winmmbase makes (GMEM_MOVEABLE | GMEM_ZEROINIT, 16 bytes), through its own import pointers */
        void **sa = wmr_slot(wb, 0), **sl = wmr_slot(wb, 3), **sf = wmr_slot(wb, 1);
        if (sa && sl && sf) {
            HGLOBAL t; void *p; DWORD le;
            SetLastError(0);
            t = ((HGLOBAL (WINAPI *)(UINT, SIZE_T))*sa)(0x42, 0x10);
            p = t ? ((LPVOID (WINAPI *)(HGLOBAL))*sl)(t) : NULL; le = GetLastError();
            mlog("  winmm-trace %s: test GlobalAlloc(0x42, 16) = %p, GlobalLock = %p (err %lu)", where, (void *)t, p, (unsigned long)le);
            if (t) ((HGLOBAL (WINAPI *)(HGLOBAL))*sf)(t);
        }
    }
}

/* THE FIX (I76_WINMM_HEAPFIX; default auto = on when the split below is seen; =0 off, =1 report the state even when not split).
 * Measured 2026-10-24 on 26100.9711 (DGVOODOO-UPDATE-2026-10-24 s.7, laptop, I76_WINMM_TRACE=1):
 *  - Windows applies a compatibility shim to i76.exe (AcGenral.DLL). It replaces kernel32's GlobalAlloc / GlobalFree /
 *    GlobalReAlloc / GlobalLock / GlobalUnlock / GlobalHandle with its own heap (GetProcAddress hands every one of them out
 *    as AcGenral.DLL+0x72C40 ... +0x73230), and patches the modules' imports of them.
 *  - winmmbase 26100.9549 imports GlobalAlloc / GlobalFree through api-ms-win-core-heap-l2-1-0 (the shim patches those
 *    slots: AcGenral) but GlobalReAlloc / GlobalLock / GlobalUnlock / GlobalHandle through api-ms-win-core-heap-obsolete-l1-1-0,
 *    which the shim does not catch: those stay KERNELBASE.
 *  - winmmbase's driver table is GlobalAlloc(GMEM_MOVEABLE) then GlobalLock. The shim's GlobalAlloc returns a plain heap
 *    pointer; KERNELBASE's GlobalLock takes any value with bit 2 set for a moveable-memory handle, finds none (err 6) and
 *    returns NULL; winmmbase reads [NULL+8] at +0x5AB3. Bit 2 of a heap pointer is set or not by where the heap stands, so
 *    about half the boots; the preset's allocations move the heap, hence its odds (no preset 0 of 8).
 *  - The same split is in nearly EVERY module of the process, not only winmmbase (census, trace boots: USER32, ole32, combase,
 *    gdi32full, SHELL32, SHLWAPI, urlmon, windows.storage, MSACM32 ...): GlobalAlloc / GlobalFree the shim's, Lock / Unlock /
 *    ReAlloc / Handle the system's. Fixing winmmbase alone took its crash away (0 of 20) but left 3 crashes in 40 boots in
 *    DSOUND, wdmaud.drv and the shim's heap itself, all in the same CD-audio start-up.
 * So: every module whose Global* set is split gets the shim's own functions (what GetProcAddress(kernel32) returns) in its
 * system slots, so each module uses ONE allocator again, the shim's, as the shim intends. Only slots that are the system's
 * are changed, only in a module that already has a slot into the layer, and only to that layer's function. It runs from
 * DllMain, then from a watch thread (50 ms for 30 s, 1 s to 2 min, then 5 s) and before real winmm calls (at most every
 * 100 ms) for modules loaded later. A first version pointed winmmbase's six at KERNELBASE instead: the shim re-patches
 * GlobalAlloc / GlobalFree after DllMain and the mixed window corrupted the heap; not used. */
static int g_wmr_fix = -1;          /* -1 not decided, 0 off / not needed, 1 on */
static HMODULE wmr_mod_of(const void *p) {
    MEMORY_BASIC_INFORMATION mb;
    return (p && VirtualQuery(p, &mb, sizeof mb) && mb.Type == MEM_IMAGE) ? (HMODULE)mb.AllocationBase : NULL;
}
static int wmr_is_sys(const void *p) {
    char o[96]; wmr_owner(p, o, sizeof o);
    return _strnicmp(o, "KERNELBASE.dll+", 15) == 0 || _strnicmp(o, "kernel32.dll+", 13) == 0 || _strnicmp(o, "ntdll.dll+", 10) == 0;
}
static void wmr_apply_fix(const char *when) {
    char v[8]; DWORD n; int ns;
    if (g_wmr_fix >= 0) return;
    n = GetEnvironmentVariableA("I76_WINMM_HEAPFIX", v, sizeof v);
    if (n && v[0] == '0') { g_wmr_fix = 0; mlog("  winmm-heapfix: off (I76_WINMM_HEAPFIX=0)"); return; }
    ns = wmr_sweep(when, 1, wmr_trace_on());
    if (!ns) {   /* no layer on Global*, or no split module yet: asked again before each of the first 64 real winmm calls */
        static int seen; if (!seen++) mlog("  winmm-heapfix: not needed so far (%s: no module with a split Global* set)", when);
        if (seen >= 64) g_wmr_fix = 0;
        return;
    }
    g_wmr_fix = 1;
    g_wmr_pre = CreateEventA(NULL, TRUE, FALSE, NULL);
    { HANDLE th = CreateThread(NULL, 0, wmr_watch, NULL, 0, NULL); if (th) CloseHandle(th); else if (g_wmr_pre) SetEvent(g_wmr_pre); }
    mlog("  winmm-heapfix: on (%s): %d module(s) had GlobalAlloc / GlobalFree from the layer but other Global* from the system - now all the layer's; "
         "modules loaded later are swept by the watch and before each real winmm call", when, ns);
}
/* The modules winmm loads INSIDE the game's first calls (driver and mpegvideo chain; v4 census: msacm32.drv, midimap,
 * WMVCore, mfplat, loaded during "status i76len length" and used in the same call, before any sweep could reach them; 3 of 20
 * boots then crashed in wdmaud.drv / the shim's heap). They are loaded here first, off the loader lock, and swept, and the
 * proxy's first real winmm call waits for that (at most 3 s). Plain LoadLibrary: the reference stays for the process. */
static void wmr_preload(void) {
    static const char *m[] = { "wdmaud.drv", "msacm32.drv", "midimap.dll", "mciqtz32.dll", "quartz.dll", "mfplat.dll", "WMVCore.dll",
                               "MMDevAPI.dll", "AudioSes.dll", "dsound.dll", NULL };
    int i, n = 0; DWORD t0 = GetTickCount();
    for (i = 0; m[i]; i++) if (LoadLibraryA(m[i])) n++;
    i = wmr_sweep("preload", 1, wmr_trace_on());
    {   /* the layer's patch of a freshly loaded module can land a moment after LoadLibrary returns (measured: the sweep right
           after the loads found 0 of 5 split in 1 of 27 boots, the watch fixed them 50 ms later): sweep again for 500 ms */
        int k; for (k = 0; k < 20; k++) { Sleep(25); i += wmr_sweep("preload", 1, 0); }
    }
    mlog("  winmm-heapfix: preloaded %d audio / MCI modules in %lu ms, %d split module(s) after the sweep", n, GetTickCount() - t0, i);
}
static void wmr_wait_pre(void) { if (g_wmr_pre) WaitForSingleObject(g_wmr_pre, 3000); }
/* the sweep again: every 50 ms for 30 s (the game's first winmm calls come about 3 s in), every 1 s to 2 min, then every 5 s */
static DWORD WINAPI wmr_watch(LPVOID arg) {
    DWORD t0 = GetTickCount(), d; (void)arg;
    wmr_preload(); if (g_wmr_pre) SetEvent(g_wmr_pre);
    for (;;) { wmr_sweep("watch", 1, 0); d = GetTickCount() - t0; Sleep(d < 30000 ? 50 : d < 120000 ? 1000 : 5000); }
}
/* EVERY module: the same split can sit in any module that imports Global* through both api sets (wdmaud.drv, dsound, ...).
 * fix != 0: change the system slots of a split module to the layer's functions. Returns the number of split modules seen;
 * logs them when log != 0 (trace) or when a slot was changed. */
static int wmr_sweep(const char *when, int fix, int log) {
    static const char *skip[] = { "ntdll.dll", "kernel32.dll", "KERNELBASE.dll", "apphelp.dll", NULL };
    HMODULE k32 = GetModuleHandleA("kernel32.dll"), layer; void *lf[WMR_NIMP]; int i, nsplit = 0;
    HANDLE sn; MODULEENTRY32 me;
    if (!k32) return 0;
    for (i = 0; i < WMR_NIMP; i++) lf[i] = (void *)GetProcAddress(k32, g_wmr_imp[i].fn);   /* the layer hooks GetProcAddress: its own */
    if (!lf[0] || wmr_is_sys(lf[0]) || !(layer = wmr_mod_of(lf[0]))) return 0;              /* no layer on GlobalAlloc in this process */
    sn = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, 0);
    if (sn == INVALID_HANDLE_VALUE) return 0;
    me.dwSize = sizeof me;
    if (Module32First(sn, &me)) do {
        void **sl[WMR_NIMP]; int k, nl = 0, ns = 0, ch = 0; char map[WMR_NIMP + 1]; HMODULE pin = NULL;
        if (me.hModule == layer) continue;
        for (k = 0; skip[k] && lstrcmpiA(me.szModule, skip[k]) != 0; k++) ;
        if (skip[k]) continue;
        /* pin it: a module in the snapshot can be unloaded while it is walked (measured: a read fault in the walk, 1 of 20) */
        if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS, (LPCSTR)me.hModule, &pin) || pin != me.hModule) { if (pin) FreeLibrary(pin); continue; }
        for (i = 0; i < WMR_NIMP; i++) {
            sl[i] = wmr_slot(me.hModule, i);
            if (!sl[i]) map[i] = '-';
            else if (wmr_mod_of(*sl[i]) == layer) { map[i] = 'L'; nl++; }
            else if (wmr_is_sys(*sl[i])) { map[i] = 'S'; if (lf[i] && wmr_mod_of(lf[i]) == layer) ns++; else map[i] = 's'; }   /* s: the layer has none of its own */
            else map[i] = '?';
        }
        map[WMR_NIMP] = 0;
        if (!(nl && ns)) { FreeLibrary(pin); continue; }
        nsplit++;
        if (fix) for (i = 0; i < WMR_NIMP; i++) {
            DWORD old;
            if (map[i] != 'S' || !lf[i] || wmr_mod_of(lf[i]) != layer) continue;
            if (VirtualProtect(sl[i], sizeof(void *), PAGE_READWRITE, &old)) {
                InterlockedExchangePointer(sl[i], lf[i]); VirtualProtect(sl[i], sizeof(void *), old, &old);
                if (*sl[i] == lf[i]) ch++;
            }
        }
        if (log || ch) mlog("  winmm-heapfix: %s: %s split (Global / Local Alloc Free ReAlloc Lock Unlock Handle Size Flags = %.8s / %.8s)%s%d slot(s) -> the layer's, tid %lu t=%lu",
                            when, me.szModule, map, map + 8, fix ? ", " : " - not fixed, ", ch, GetCurrentThreadId(), GetTickCount());
        FreeLibrary(pin);
    } while (Module32Next(sn, &me));
    CloseHandle(sn);
    return nsplit;
}
static DWORD WINAPI wmr_census_thread(LPVOID arg) {
    static const DWORD at[] = { 1000, 3000, 5000, 10000, 20000 }; static const char *lb[] = { "census 1 s", "census 3 s", "census 5 s", "census 10 s", "census 20 s" };
    DWORD t0 = GetTickCount(); int i; (void)arg;
    for (i = 0; i < 5; i++) { DWORD d = GetTickCount() - t0; if (d < at[i]) Sleep(at[i] - d); if (!wmr_sweep(lb[i], 0, 1)) mlog("  winmm-trace %s: no split module", lb[i]); }
    return 0;
}
static void wmr_before_real(const char *what) {
    static volatile LONG n;
    if (g_wmr_fix < 0) wmr_apply_fix(what);
    else if (g_wmr_fix == 1) { wmr_wait_pre(); static DWORD last; DWORD t = GetTickCount(); if (t - last >= 100) { last = t; wmr_sweep(what, 1, 0); } }
    if (!wmr_trace_on()) return;
    if (InterlockedIncrement(&n) <= 3) wmr_state(what);
}
