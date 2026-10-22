/* nitro_form.c - ARENA+ on Nitro: the host-form check boxes (nitro-mp-design lane, 2026-10-21; owner's item 2 of the
 * evening: the boxes move from the lab instrument into the shipped proxy). Included by nitro_mp.c; nmp_attach_shell()
 * calls nf_attach(nitshell). Record: docs/records/NITRO-MP-DESIGN-2026-10-21.md s.0.3 (design), 0.5.1 (lab proof),
 * 0.5.10 (this). RE: i76-map nitro-net\README.md.
 *
 * On nitshell's network HOST form (provider [0x1004701c] 2..5) two check boxes under the label ARENA+ and its
 * owner-approved description:
 *   [ ] ARENA+        (hit id 0x10)  on -> the session is ARENA+ (ANet species 0x7676), AI fill the open slots
 *   [ ] CO-OP SCENES  (hit id 0x11)  Nitro's own P01-P19 appended to the arena list (implies ARENA+)
 * Both off (the default, and after every new entry into the network menus) = the stock form and a stock session (604):
 * the species word is not written, the arena list is not touched, the hit test and every stock click run as before.
 *
 * nitshell f804f50d (base 0x10000000; NF_R() relocates), each site checked by its bytes before anything is written:
 *   F1 `call 0x100318e0` (form constructor) at 0x10001531 -> nf_ctor: constructor, then our hit records (once per hit
 *      list; the list [0x10179ea8] is rebuilt on every entry into the network menus by 0x10031320) and the first draw.
 *   F2 `ja 0x10032054` at 0x1003219b (click handler, ids > 15) -> nf_ja_stub: ids 0x10 / 0x11 toggle, then the stock exit.
 *   F3 the redraw 0x10033770: the constructor's `mov [0x10047044], 0x10033770` immediate (0x100318f7) and its three
 *      direct calls (0x1002e740, 0x10037a0e, 0x10037c45) -> nf_redraw: the stock redraw, then our boxes.
 *   Calls used: list append 0x1000e100(list, rec, 0), erase 0x10012a50 (thiscall display, x, y, w, h), text 0x10012dc0
 *   (thiscall display, x, y, font, s, 0); display [0x10130488], font [[0x1013049c] + 0x408]; arena list [0x10179eac]
 *   {?, count +4, items +8} with the shell's count [0x1004585c] and selection [0x10045858]; species word [0x10046cb0].
 * I76_NITRO_FORM=0 leaves the form stock (the rest of ARENA+ then never meets an ARENA+ session from this host).
 */
#define NF_SB 0x10000000u
static BYTE *g_nf_sh;
#define NF_R(a) ((DWORD)(DWORD_PTR)(g_nf_sh + ((DWORD)(a) - NF_SB)))
#define NF_ARENA 1
#define NF_COOP  2
static volatile LONG g_nf_opt;                 /* bit 0 ARENA+, bit 1 CO-OP SCENES */
static int g_nf_on; static WORD g_nf_species0; static DWORD g_nf_ja_back, g_nf_redraw0, g_nf_ctor0;
static LONG g_nf_hits, g_nf_draws;

/* Layout, form pixels (640 x 480). The lab proof's strip under the arena list (x 12, y 273-299) turned out, on the first
 * console screenshot (record s.0.5.10), to be the OPTIONS header and the list's lower arrow. The free parchment is the
 * middle of the car panel: between the front view (ends y ~172) and the side view (starts y ~307), left of the
 * WEAPONS / PARTS column (x 457); no stock hit rectangle lies there (record s.0.2). Lines: {x, y, what, text};
 * what 0 = text, NF_ARENA / NF_COOP = that box's line, drawn "[X] text" / "[ ] text". The hit rectangle of a box covers its
 * "[ ]" (strict bounds in the shell's hit test 0x1000e2e0). */
#define NF_X 232
#define NF_Y 182
#define NF_BOX1_Y (NF_Y + 72)
#define NF_BOX2_Y (NF_Y + 87)
#define NF_ERASE_X (NF_X - 4)
#define NF_ERASE_Y (NF_Y - 2)
#define NF_ERASE_W 222
#define NF_ERASE_H 104
static DWORD g_nf_rec[2][5] = { { 0x10, NF_X - 3, NF_X + 24, NF_BOX1_Y - 2, NF_BOX1_Y + 13 },
                                { 0x11, NF_X - 3, NF_X + 24, NF_BOX2_Y - 1, NF_BOX2_Y + 13 } };
struct nf_line { short x, y, what; const char *s; };
static const struct nf_line g_nf_lines[] = {   /* the description is the owner-approved text, unchanged, wrapped */
    { NF_X, NF_Y, 0, "ARENA+" },
    { NF_X, NF_Y + 16, 0, "Every arena plus the" },
    { NF_X, NF_Y + 29, 0, "original '76 missions," },
    { NF_X, NF_Y + 42, 0, "with AI filling the" },
    { NF_X, NF_Y + 55, 0, "open slots." },
    { NF_X, NF_BOX1_Y, NF_ARENA, "ARENA+" },
    { NF_X, NF_BOX2_Y, NF_COOP, "CO-OP SCENES" },
};
static int g_nf_width[8];   /* text widths of the first draw (logged once) */

typedef int (__fastcall *nf_erase_fn)(void *self, void *edx, int x, int y, int w, int h);
typedef int (__fastcall *nf_text_fn)(void *self, void *edx, int x, int y, int font, const char *s, void *z);
static int nf_host_form(void) { int p = *(int *)NF_R(0x1004701c); return p >= 2 && p <= 5; }

static void nf_draw(void) {   /* main thread (constructor, redraw, click) */
    BYTE *disp = *(BYTE **)NF_R(0x10130488), *fp = *(BYTE **)NF_R(0x1013049c); int font, i; char t[64];
    if (!g_nf_on || !disp || !fp || !nf_host_form()) return;
    font = *(int *)(fp + 0x408);
    ((nf_erase_fn)NF_R(0x10012a50))(disp, 0, NF_ERASE_X, NF_ERASE_Y, NF_ERASE_W, NF_ERASE_H);
    for (i = 0; i < (int)(sizeof g_nf_lines / sizeof g_nf_lines[0]); i++) {
        const struct nf_line *l = &g_nf_lines[i]; const char *s = l->s;
        if (l->what) { _snprintf(t, sizeof t - 1, "[%c] %s", (g_nf_opt & l->what) ? 'X' : ' ', l->s); t[sizeof t - 1] = 0; s = t; }
        g_nf_width[i & 7] = ((nf_text_fn)NF_R(0x10012dc0))(disp, 0, l->x, l->y, font, s, 0);
    }
    if (!g_nf_draws++) NMP_LOG("  nitro-form: first draw on the host form - text widths %d %d %d %d %d %d %d (free width %d)", g_nf_width[0], g_nf_width[1],
                               g_nf_width[2], g_nf_width[3], g_nf_width[4], g_nf_width[5], g_nf_width[6], NF_ERASE_W - 4);
}

/* CO-OP SCENES: P01-P19 as arena-list records (0x34 bytes: title +0, file +0x20), appended / taken off at the end */
static char g_nf_coop[19][0x34];
static int nf_coop_listed(void) {
    BYTE *l = *(BYTE **)NF_R(0x10179eac); int n = l ? *(int *)(l + 4) : 0;
    return n >= 19 && ((char **)*(BYTE **)(l + 8))[n - 1] == g_nf_coop[18];
}
static void nf_coop_list(int on) {
    BYTE *l = *(BYTE **)NF_R(0x10179eac); int k;
    if (!l || on == nf_coop_listed()) return;
    if (on) {
        for (k = 0; k < 19; k++) {
            memset(g_nf_coop[k], 0, 0x34); sprintf(g_nf_coop[k], "Co-op P%02d", k + 1); sprintf(g_nf_coop[k] + 0x20, "p%02d.msn", k + 1);
            ((void (__cdecl *)(void *, void *, void *))NF_R(0x1000e100))(l, g_nf_coop[k], 0); (*(int *)NF_R(0x1004585c))++;
        }
    } else {
        *(int *)(l + 4) -= 19; *(int *)NF_R(0x1004585c) -= 19;
        if (*(int *)NF_R(0x10045858) >= *(int *)(l + 4)) *(int *)NF_R(0x10045858) = -1;   /* -1 = none, the list's own start value */
    }
}
static void nf_apply(void) {   /* options -> species word, list, hello */
    WORD sp = g_nf_opt ? NMP_SPECIES_ARENA : g_nf_species0;
    if (*(WORD *)NF_R(0x10046cb0) != sp) *(WORD *)NF_R(0x10046cb0) = sp;
    nf_coop_list((g_nf_opt & NF_COOP) != 0);
    g_nmp_opts = g_nf_opt;
}
static void __cdecl nf_redraw(void) { ((void (__cdecl *)(void))g_nf_redraw0)(); nf_draw(); }
static void __cdecl nf_toggle(DWORD id) {   /* main thread, from the click handler */
    LONG o = g_nf_opt;
    if (!nf_host_form()) return;
    if (id == 0x10) o = (o & NF_ARENA) ? 0 : NF_ARENA;                                   /* ARENA+ off clears CO-OP too */
    else if (id == 0x11) o = (o & NF_COOP) ? (o & ~NF_COOP) : (o | NF_COOP | NF_ARENA);
    g_nf_opt = o; g_nf_hits++;
    nf_apply();
    NMP_LOG("  nitro-form: click id 0x%lx -> ARENA+ %s, CO-OP SCENES %s; species %04x, arena list %d", id, o & NF_ARENA ? "on" : "off",
            o & NF_COOP ? "on" : "off", *(WORD *)NF_R(0x10046cb0), *(int *)NF_R(0x1004585c));
    nf_redraw();
}
static __declspec(naked) void nf_ja_stub(void) {
    __asm {
        cmp ebx, 0x10
        jb skip
        cmp ebx, 0x11
        ja skip
        pushad
        push ebx
        call nf_toggle
        add esp, 4
        popad
    skip:
        jmp dword ptr [g_nf_ja_back]
    }
}
static void __cdecl nf_ctor(DWORD a) {
    BYTE *hl; int n, i, have = 0;
    ((void (__cdecl *)(DWORD))g_nf_ctor0)(a);
    hl = *(BYTE **)NF_R(0x10179ea8); n = hl ? *(int *)(hl + 4) : 0;
    for (i = 0; i < n; i++) if (((DWORD **)*(BYTE **)(hl + 8))[i] == g_nf_rec[0]) have = 1;
    if (hl && !have) {   /* a fresh hit list = a new entry into the network menus: options back to off, the stock species */
        ((void (__cdecl *)(void *, void *, void *))NF_R(0x1000e100))(hl, g_nf_rec[0], 0);
        ((void (__cdecl *)(void *, void *, void *))NF_R(0x1000e100))(hl, g_nf_rec[1], 0);
        if (g_nf_opt) NMP_LOG("  nitro-form: new entry into the network menus - ARENA+ options cleared");
        g_nf_opt = 0; g_nmp_opts = 0;
        if (*(WORD *)NF_R(0x10046cb0) != g_nf_species0) *(WORD *)NF_R(0x10046cb0) = g_nf_species0;
    } else if ((g_nf_opt & NF_COOP) && !nf_coop_listed()) nf_coop_list(1);   /* the arena list was rebuilt under us */
    nf_draw();
}

static int nf_bytes(DWORD va, const BYTE *b, int n) { return memcmp((void *)(DWORD_PTR)NF_R(va), b, n) == 0; }
static int nf_write(DWORD at, const void *b, int n) {
    DWORD op; BYTE *p = (BYTE *)(DWORD_PTR)at;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &op)) return 0;
    memcpy(p, b, n); VirtualProtect(p, n, op, &op); FlushInstructionCache(GetCurrentProcess(), p, n);
    return memcmp(p, b, n) == 0;
}
static int nf_is_call(DWORD site, DWORD target) { BYTE *p = (BYTE *)(DWORD_PTR)NF_R(site); return p[0] == 0xE8 && (DWORD)(NF_R(site) + 5 + *(LONG *)(p + 1)) == NF_R(target); }
static int nf_call(DWORD site, void *fn) { BYTE w[5] = { 0xE8 }; LONG rel = (LONG)((DWORD_PTR)fn - (NF_R(site) + 5)); memcpy(w + 1, &rel, 4); return nf_write(NF_R(site), w, 5); }

static void nf_attach(HMODULE sh) {
    static const BYTE ja[6] = { 0x0f, 0x87, 0xb3, 0xfe, 0xff, 0xff }, ap[6] = { 0x53, 0x55, 0x8b, 0x6c, 0x24, 0x10 },
        rd[5] = { 0x83, 0xec, 0x08, 0x8b, 0x0d }, er[6] = { 0x83, 0xec, 0x14, 0x8b, 0x44, 0x24 }, tx[6] = { 0x83, 0xec, 0x08, 0x8b, 0x54, 0x24 },
        ct[3] = { 0x83, 0xec, 0x0c }, mv[2] = { 0xc7, 0x05 };
    static const DWORD rdcalls[3] = { 0x1002e740, 0x10037a0e, 0x10037c45 };
    char v[8]; int ok, n = 0, k; DWORD r;
    if (GetEnvironmentVariableA("I76_NITRO_FORM", v, sizeof v) && v[0] == '0') { NMP_LOG("  nitro-form: I76_NITRO_FORM=0 - off"); return; }
    g_nf_sh = (BYTE *)sh;
    ok = nf_bytes(0x1003219b, ja, 6) && nf_bytes(0x1000e100, ap, 6) && nf_bytes(0x10033770, rd, 5) && nf_bytes(0x10012a50, er, 6)
      && nf_bytes(0x10012dc0, tx, 6) && nf_bytes(0x100318e0, ct, 3) && nf_bytes(0x100318f1, mv, 2)
      && *(DWORD *)NF_R(0x100318f3) == NF_R(0x10047044) && *(DWORD *)NF_R(0x100318f7) == NF_R(0x10033770)
      && nf_is_call(0x10001531, 0x100318e0) && nf_is_call(rdcalls[0], 0x10033770) && nf_is_call(rdcalls[1], 0x10033770) && nf_is_call(rdcalls[2], 0x10033770);
    g_nf_species0 = *(WORD *)NF_R(0x10046cb0);
    if (!ok || g_nf_species0 != NMP_SPECIES_STOCK) { NMP_LOG("  nitro-form: OFF (nitshell bytes %s, species %04x)", ok ? "as f804f50d" : "NOT as f804f50d", g_nf_species0); return; }
    g_nf_ja_back = NF_R(0x10032054); g_nf_redraw0 = NF_R(0x10033770); g_nf_ctor0 = NF_R(0x100318e0);
    g_nf_on = 1;   /* before the writes: nf_draw checks it */
    r = (DWORD)(DWORD_PTR)nf_redraw; n += nf_write(NF_R(0x100318f7), &r, 4);
    for (k = 0; k < 3; k++) n += nf_call(rdcalls[k], (void *)nf_redraw);
    n += nf_call(0x10001531, (void *)nf_ctor);
    {   BYTE w[6] = { 0x0f, 0x87 }; LONG rel = (LONG)((DWORD_PTR)nf_ja_stub - (NF_R(0x1003219b) + 6)); memcpy(w + 2, &rel, 4); n += nf_write(NF_R(0x1003219b), w, 6); }
    NMP_LOG("  nitro-form: %s - %d/6 nitshell sites (constructor, click, redraw x4); boxes ARENA+ (0x10) and CO-OP SCENES (0x11) on host forms, both off = stock",
            n == 6 ? "ON" : "PARTIAL", n);
}
