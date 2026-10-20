/* mpmenu.c - I76_MP_MENU: the MULTI MELEE connection choice (i76shell.dll a300db63 / pristine deb41008; the code
 * patched here is identical in both). Included from strlkproxy.c after padmenu.c, before hook_LoadLibraryA.
 * Record: docs/records/COOP-LIST-ENTRIES-2026-10-18.md section 7 (2026-10-19).
 *
 * THE MENU (static, addresses at the preferred base 0x10000000; the patch adds the module's real base):
 *   MELEE > MULTI MELEE shows HOST / JOIN. The main-menu dispatch (jump table 0x1002655c) runs
 *     HOST 0x10025dee: [0x100d3a54] = 1, HOST/JOIN records out of the list, MODEM IPX INTERNET NULLMODEM added,
 *                      then `jmp 0x10025f39` into JOIN's tail (OTHER added, all five shown)
 *     JOIN 0x10025e97: [0x100d3a54] = 0, same lists; tail ends at 0x10025f82 `jmp 0x10026515` (the dispatch exit)
 *   The provider row is a FIXED button list (records MODEM 0x100d3f60 id 6, IPX 0x100d3dd8 id 7, INTERNET 0x100d3eb8
 *   id 14, NULLMODEM 0x100d3da0 id 8, OTHER 0x100d3c50 id 16, laid out by MainMenu_Layout 0x10027334..0x100273cf), not
 *   a DirectPlay enumeration. IPX 0x100260b2: [0x100d217c] = [0x100d3a54] ? 3 : 7 (host / join IPX), call
 *   0x10027c80 (host form init, arena list), message 0xc026 (the network entry form), `jmp 0x10026515`.
 *
 * I76_MP_MENU=1 (default): "skip". 0x10025f82 `jmp 0x10026515` -> `jmp 0x100260b2`: HOST and JOIN run their own
 *   code (identical state to stock) and fall straight into the IPX handler in the same click, as if IPX had been
 *   clicked next. One 5-byte relative jump inside the function; nothing else changes.
 * I76_MP_MENU=2: "hide". HOST / JOIN show the provider row with IPX only: the list-add and show calls of MODEM,
 *   INTERNET, NULLMODEM and OTHER in the HOST / JOIN code become 5-byte NOPs (cdecl: the pushes and the caller's
 *   `add esp` stay balanced). The close paths remove records that are not in the list (0x10027a90 tolerates that)
 *   and erase their rectangles (harmless).
 * I76_MP_MENU=0: stock menu. I76_ARENA_FIT (below) is independent of it.
 * Every site is checked against the stock bytes before writing and read back after (log line "mp-menu").
 *
 * TWO WAYS IN (2026-10-20, records/LAN-MATRIX-2026-10-20.md section 7): the PC sees i76shell load through the proxy's
 * hook on i76.exe's KERNEL32!LoadLibraryA slot (hook_LoadLibraryA, unchanged). Under DxWnd (the Macs: Wine + `dxwnd.exe
 * /R:1`) that slot is taken over after the proxy's DllMain, as DxWnd does with the WINMM slots (music-guard), so the
 * hook never ran there: "armed" but never "patched", 9 of 9 launches on each Mac. A watch thread (mpm_watch) therefore
 * polls GetModuleHandleA("i76shell.dll") every 50 ms; once the module has been resident for 750 ms (its load is over)
 * and nothing patched it yet, it patches from there and logs who held the LoadLibraryA slot. The patch runs once
 * (g_mpm_done, interlocked): on the PC the hook gets there first and the thread only ends.
 */
static int g_mpm_mode = -1;                     /* -1 = not read yet */

static int mpm_write(BYTE *p, const BYTE *expect, const BYTE *want, int n) {
    DWORD op;
    if (memcmp(p, expect, n) != 0) return 0;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &op)) return 0;
    memcpy(p, want, n);
    VirtualProtect(p, n, op, &op);
    FlushInstructionCache(GetCurrentProcess(), p, n);
    return memcmp(p, want, n) == 0;             /* verify the write landed */
}

/* I76_ARENA_FIT (default 1): the host form's AREA OF PLAY list. EntryForm_DrawArenaList 0x1002b350 clears its box
 * (0x10038fd0: x 11, w 206) and draws each title at x 0x22 in the form font (font object [0x100cc52c], height 15) with
 * the display object's text call 0x100395b0 (thiscall: x, y, font, text, 0), which does not clip: a title wider than
 * the box (~19 characters) ran over its right border and stayed there (the box is cleared, the border strip is not),
 * measured 2026-10-19 with "Oil Well Well (Scenario)". Both calls in that function (0x1002b3af the chosen arena,
 * 0x1002b421 the six rows) go through mpm_text_stub, which draws the titles at x I76_ARENA_X (default 18) in font
 * object I76_ARENA_FONT (default 1 = [0x100cc524], the same handwriting at height 12, 'The Crater' 78 px against 95;
 * 0 = [0x100cc520] is a plain sans at height 10, -1 = the form's own) and, only if a title is still wider than the box
 * (x .. 0xd4), shortens its name with a "." and keeps the " (...)" kind suffix. With the defaults every title fits
 * whole except "Trailer Pk. Madn. (Scenario)" (records/COOP-LIST-ENTRIES-2026-10-18.md 8.2). Nothing is written to
 * the arena records; the shell's 5 fonts are measured into the log once (glyph width 0x1003e42c, height 0x1003e419). */
static int g_mpm_fit = -1;
static DWORD g_mpm_draw, g_mpm_glyph;           /* relocated 0x100395b0 / 0x1003e42c */
static char g_mpm_buf[64];
static int mpm_width(void *font, const char *s, int n) {
    int w = 0;
    for (; n > 0 && *s; s++, n--) w += ((int (__cdecl *)(void *, int))g_mpm_glyph)(font, (BYTE)*s);
    return w;
}
static BYTE *g_mpm_base;                        /* i76shell base (font globals) */
static int g_mpm_font = 1;                      /* I76_ARENA_FONT: 0..4 = font object 0x100cc520 + 4 n, -1 = the form's own (0x100cc52c) */
static int g_mpm_x = 18;                        /* I76_ARENA_X: left edge of the titles (stock 0x22 = 34) */
static void *g_mpm_font_out;
static void *mpm_font_obj(int k) {              /* the glyph table of font object k (its +0x408), or NULL */
    BYTE *o = *(BYTE **)(g_mpm_base + (0x100cc520u - 0x10000000u) + 4 * k);
    return o ? *(void **)(o + 0x408) : NULL;
}
static const char *__cdecl mpm_fit(void *font, const char *s) {
    const char *suf; int n, ls, cut, w = 0xd4 - g_mpm_x;   /* right limit x 0xd4, inside the box and its border */
    static int surveyed;
    if (font && s && g_mpm_glyph && !surveyed) {           /* once: what each of the shell's 5 fonts would need */
        int k; surveyed = 1;
        for (k = 0; k < 5; k++) { void *f = mpm_font_obj(k);
            if (f) mlog("  arena-fit: font %d (0x%08lX): height %d, '%s' = %d px", k, (unsigned long)(0x100cc520u + 4 * k),
                        ((int (__cdecl *)(void *))(g_mpm_base + 0x3e419))(f), s, mpm_width(f, s, 1 << 20)); }
    }
    if (g_mpm_font >= 0 && mpm_font_obj(g_mpm_font)) font = mpm_font_obj(g_mpm_font);
    g_mpm_font_out = font;
    if (!s || !font || !g_mpm_glyph || mpm_width(font, s, 1 << 20) <= w) return s;
    n = (int)strlen(s);
    if (n >= (int)sizeof g_mpm_buf - 2) n = (int)sizeof g_mpm_buf - 2;
    suf = strstr(s, " (");
    if (!suf || suf - s >= n) suf = s + n;      /* no kind suffix: shorten the end */
    ls = (int)strlen(suf);
    for (cut = (int)(suf - s) - 1; cut > 0; cut--) {
        while (cut > 0 && s[cut - 1] == ' ') cut--;
        memcpy(g_mpm_buf, s, cut); g_mpm_buf[cut] = '.';
        memcpy(g_mpm_buf + cut + 1, suf, ls); g_mpm_buf[cut + 1 + ls] = 0;
        if (mpm_width(font, g_mpm_buf, 1 << 20) <= w) return g_mpm_buf;
    }
    return s;
}
static __declspec(naked) void mpm_text_stub(void) {    /* replaces `call 0x100395b0` (thiscall, 5 stack args) */
    __asm {
        push ecx                                /* [esp+4] ret, +8 x, +0xc y, +0x10 font, +0x14 text */
        mov eax, [esp + 0x14]
        push eax                                /* text */
        mov eax, [esp + 0x14]
        push eax                                /* font */
        call mpm_fit
        add esp, 8
        pop ecx
        mov [esp + 0x10], eax                   /* the text argument */
        mov eax, g_mpm_font_out
        mov [esp + 0xc], eax                    /* the font argument */
        mov eax, g_mpm_x
        mov [esp + 4], eax                      /* x */
        jmp dword ptr [g_mpm_draw]
    }
}

/* from hook_LoadLibraryA, or from the watch thread (mpm_watch) when that hook never sees the shell load */
static volatile LONG g_mpm_done;                /* 1 once one path has patched the shell (it is patched once) */
static void mp_menu_attach(HMODULE m, const char *b) {
    BYTE *base = (BYTE *)m;
    if (_strnicmp(b, "i76shell", 8) != 0 || InterlockedCompareExchange(&g_mpm_done, 1, 0) != 0) return;
#define MPM_VA(va) (base + ((DWORD)(va) - 0x10000000u))
    if (g_mpm_fit == 1) {
        static const DWORD site[2] = { 0x1002b3af, 0x1002b421 };
        int i, ok = 0;
        g_mpm_base = base;
        g_mpm_draw = (DWORD)(DWORD_PTR)MPM_VA(0x100395b0); g_mpm_glyph = (DWORD)(DWORD_PTR)MPM_VA(0x1003e42c);
        for (i = 0; i < 2; i++) {
            BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 }; BYTE *p = MPM_VA(site[i]);
            LONG a0 = (LONG)(g_mpm_draw - ((DWORD)(DWORD_PTR)p + 5)), a1 = (LONG)((DWORD)(DWORD_PTR)mpm_text_stub - ((DWORD)(DWORD_PTR)p + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            ok += mpm_write(p, o5, w5, 5);
        }
        mlog("  arena-fit: AREA OF PLAY titles at x %d fitted to %d px, font %d (-1 = the form's): %d / 2 text calls %s",
             g_mpm_x, 0xd4 - g_mpm_x, g_mpm_font, ok,
             ok == 2 ? "repointed, read back OK" : "NOT all repointed");
    }
    if (g_mpm_mode <= 0) return;
    if (g_mpm_mode == 1) {
        static const BYTE old_[5] = { 0xE9, 0x8E, 0x05, 0x00, 0x00 };            /* jmp 0x10026515 */
        static const BYTE new_[5] = { 0xE9, 0x2B, 0x01, 0x00, 0x00 };            /* jmp 0x100260b2 (IPX) */
        int ok = mpm_write(MPM_VA(0x10025f82), old_, new_, 5);
        mlog("  mp-menu: skip - MULTI MELEE > HOST / JOIN go straight to IPX (i76shell+0x25f82 jmp -> IPX handler 0x100260b2): %s",
             ok ? "patched, read back OK" : "NOT patched (unexpected bytes) - stock menu");
    } else if (g_mpm_mode == 2) {
        /* call sites (e8 rel32) of the list-add 0x10027970 / show 0x10033570 for MODEM, INTERNET, NULLMODEM, OTHER */
        static const struct { DWORD va, target; } s[] = {
            { 0x10025e40, 0x10027970 }, { 0x10025e69, 0x10027970 }, { 0x10025e7e, 0x10027970 },   /* HOST adds */
            { 0x10025ee6, 0x10027970 }, { 0x10025f10, 0x10027970 }, { 0x10025f24, 0x10027970 },   /* JOIN adds */
            { 0x10025f39, 0x10027970 },                                                           /* OTHER (both) */
            { 0x10025f46, 0x10033570 }, { 0x10025f60, 0x10033570 }, { 0x10025f6d, 0x10033570 }, { 0x10025f7a, 0x10033570 },
        };
        static const BYTE nop5[5] = { 0x0F, 0x1F, 0x44, 0x00, 0x00 };
        int i, ok = 0, n = (int)(sizeof s / sizeof s[0]);
        BYTE exp_[11][5];
        for (i = 0; i < n; i++) {                 /* check every site first: all or nothing */
            LONG rel = (LONG)(s[i].target - (s[i].va + 5));
            exp_[i][0] = 0xE8; memcpy(&exp_[i][1], &rel, 4);
            if (memcmp(MPM_VA(s[i].va), exp_[i], 5) != 0) break;
        }
        if (i == n) for (i = 0; i < n; i++) ok += mpm_write(MPM_VA(s[i].va), exp_[i], nop5, 5);
        mlog("  mp-menu: hide - HOST / JOIN show IPX only (MODEM, INTERNET, NULLMODEM, OTHER not added): %d / %d sites %s",
             ok, n, ok == n ? "patched, read back OK" : "NOT patched (unexpected bytes) - stock menu");
    }
#undef MPM_VA
}

static DWORD WINAPI mpm_watch(LPVOID arg) {    /* the DxWnd-proof way in: poll until i76shell is resident, patch once */
    DWORD t0 = GetTickCount(), seen = 0;
    (void)arg;
    while (!g_mpm_done && GetTickCount() - t0 < 30u * 60u * 1000u) {
        HMODULE sh = GetModuleHandleA("i76shell.dll");
        if (!sh) seen = 0;
        else if (!seen) seen = GetTickCount() | 1;
        else if (GetTickCount() - seen >= 750) {
            void **slot = iat_slot(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA");
            char who[MAX_PATH] = "?", *b = who, *q; HMODULE hm = NULL;
            if (slot && GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                           (LPCSTR)*slot, &hm) && hm) GetModuleFileNameA(hm, who, sizeof(who));
            for (q = who; *q; q++) if (*q == '\\' || *q == '/') b = q + 1;
            if (g_mpm_done) break;              /* the hook got there while this thread waited */
            mlog("  mp-menu: i76shell.dll resident at %p but not seen through the LoadLibraryA hook (the exe's LoadLibraryA slot is %s, held by %s) - patching from the watch thread",
                 (void *)sh, slot && *slot == (void *)hook_LoadLibraryA ? "ours" : "NOT ours", b);
            mp_menu_attach(sh, "i76shell.dll");
            break;
        }
        Sleep(50);
    }
    return 0;
}

static void apply_mp_menu(void) {
    HMODULE sh;
    g_mpm_mode = env_int("I76_MP_MENU", 8, 1);
    if (g_mpm_mode < 0 || g_mpm_mode > 2) g_mpm_mode = 1;
    g_mpm_fit = env_flag("I76_ARENA_FIT", 8, 1);
    g_mpm_font = env_int("I76_ARENA_FONT", 8, 1); if (g_mpm_font > 4) g_mpm_font = 1;
    g_mpm_x = env_int("I76_ARENA_X", 8, 18); if (g_mpm_x < 12 || g_mpm_x > 0x22) g_mpm_x = 18;
    if (g_mpm_mode == 0) mlog("  mp-menu: stock (I76_MP_MENU=0): MODEM / IPX / INTERNET / NULLMODEM / OTHER");
    if (g_mpm_mode == 0 && g_mpm_fit != 1) return;
    if ((sh = GetModuleHandleA("i76shell.dll")) != NULL) mp_menu_attach(sh, "i76shell.dll");
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    {   HANDLE th = g_mpm_done ? NULL : CreateThread(NULL, 0, mpm_watch, NULL, 0, NULL);
        mlog("  mp-menu: mode %d armed (%s), arena-fit %s; LoadLibraryA %s; shell watch %s", g_mpm_mode,
             g_mpm_mode == 1 ? "skip to IPX" : g_mpm_mode == 2 ? "IPX only" : "stock", g_mpm_fit == 1 ? "on" : "off (I76_ARENA_FIT=0)",
             p_LoadLibraryA ? "hooked" : "NOT hooked", g_mpm_done ? "not needed (shell already patched)" : th ? "on" : "NOT started");
        if (th) CloseHandle(th);
    }
}
