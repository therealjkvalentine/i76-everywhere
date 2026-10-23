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
 *
 * GAME TYPE entries (owner ruling 2026-10-23, record s.0.5.17; phase 1 = host side, lab only): I76_NITRO_GAMETYPES=1
 * replaces the two boxes by two rows of the stock GAME TYPE popup, "Arena Drop-In + AI" (shell type 6, form mask 0x20)
 * and "Co-Op" (type 7, mask 0x40), on the IPX / internet host forms (provider 3 / 4; the modem forms show 3 stock rows).
 * The species and the options follow the selected type (6 -> ARENA+, 7 -> ARENA+ and CO-OP SCENES with P01-P19 as the
 * whole arena list, 1..5 -> stock 604). Sites, each byte-checked, all or nothing (nft_attach):
 *   G1 the popup open `call 0x10021d80` at 0x10032391 -> nft_popup: 7 visible rows on the form's 9-row list picture (6, 229 x 236,
 *      the id-11 popup's geometry and hit records; put back for every other popup open), our row draw (nft_rows).
 *   G2 the type-change list switch: `cmp eax, 4` 0x100342f7 -> 6, `jmp [eax*4 + 0x100346f8]` 0x10034302 -> nft_list_stub.
 *   G3 the limit popup's two type switches (0x10032771 / 0x1003277a, 0x10036f36 / 0x10036f3f): 7-entry copies, 6 / 7 = Combat.
 *   G4 the six form-field reads of the type name table 0x10045894 -> our 8-entry table (field names: the long one shortened
 *      to fit the 100-px field).
 *   G5 the prefs save `mov edx, [0x10045860]` at 0x100320aa -> type 6 / 7 saved as Combat (1): a type above 5 restored at
 *      the next boot by a stock shell (or I76_NITRO_GAMETYPES unset) would index the 5-entry tables.
 *   G6 the mode-string lookup `call 0x10039270` at 0x1002e978 (0x1002e8b8: form mask 1 / 2 / 4 / 8 / 16 -> "Team " / "Race" /
 *      "N Team C.T.F.", else the key "Unknown" 0x10045330): mask 0x20 / 0x40 -> our names (the form's top line read "Unknown").
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
static int g_nf_types;      /* I76_NITRO_GAMETYPES=1: the GAME TYPE entries instead of the boxes */
static void nft_sync(void);

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

/* CO-OP SCENES: P01-P19 as arena-list records (0x34 bytes: title +0, file +0x20), appended / taken off at the end.
 * The records come from the shell's own heap [0x1004d630]: every rebuild frees the list's items with HeapFree on it
 * (0x1000e080 -> [0x1003a090]); static records (6760b24) were handed to HeapFree on each rebuild. */
static char *g_nf_coop_first, *g_nf_coop_last;
static char *nf_coop_rec(int k) {
    char *r = (char *)HeapAlloc(*(HANDLE *)NF_R(0x1004d630), HEAP_ZERO_MEMORY, 0x34);
    if (r) { sprintf(r, "Co-op P%02d", k + 1); sprintf(r + 0x20, "p%02d.msn", k + 1); }
    return r;
}
static int nf_coop_append(BYTE *l) {   /* P01-P19 at the end of the list; returns how many */
    int k; char *r;
    for (k = 0; k < 19 && (r = nf_coop_rec(k)) != 0; k++) {
        ((void (__cdecl *)(void *, void *, void *))NF_R(0x1000e100))(l, r, 0); (*(int *)NF_R(0x1004585c))++;
        if (!k) g_nf_coop_first = r; g_nf_coop_last = r;
    }
    return k;
}
static int nf_coop_listed(void) {
    BYTE *l = *(BYTE **)NF_R(0x10179eac); int n = l ? *(int *)(l + 4) : 0;
    return n >= 19 && g_nf_coop_last && ((char **)*(BYTE **)(l + 8))[n - 1] == g_nf_coop_last;
}
static void nf_coop_list(int on) {
    BYTE *l = *(BYTE **)NF_R(0x10179eac); int k, n;
    if (!l || on == nf_coop_listed()) return;
    if (on) nf_coop_append(l);
    else {
        n = *(int *)(l + 4);
        for (k = n - 19; k < n; k++) HeapFree(*(HANDLE *)NF_R(0x1004d630), 0, ((char **)*(BYTE **)(l + 8))[k]);
        *(int *)(l + 4) -= 19; *(int *)NF_R(0x1004585c) -= 19; g_nf_coop_last = 0;
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
    if (g_nf_types) { nft_sync(); return; }   /* the options follow the selected game type; no boxes */
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

/* ---- GAME TYPE entries (I76_NITRO_GAMETYPES=1; header G1..G5) ---- */
#define NFT_ARENA 6                    /* shell game type [0x10045860] (popup row 5, form mask 1 << 5 = 0x20) */
#define NFT_COOP  7                    /* row 6, mask 0x40 */
static const char *g_nft_rows[7];      /* popup rows: [0..4] the stock names, [5] [6] ours */
static DWORD g_nft_field[9];           /* the form-field table, index = type: [0] 0, [1..5] stock, [6] [7] ours, [8] 0 */
static DWORD g_nft_lim1[7], g_nft_lim2[7];   /* the limit popup's type switches, [5] [6] = Combat's [0] */
static DWORD g_nft_list_tab, g_nft_list_back, g_nft_popup0, g_nft_type_va;
static LONG g_nft_opens, g_nft_rowdraws; static int g_nft_w[7];
static int nft_type(void) { return *(int *)NF_R(0x10045860); }
static const char *nft_name(int t) { return t >= 1 && t <= 7 && g_nft_rows[t - 1] ? g_nft_rows[t - 1] : "?"; }
static int nft_coop_only_listed(void) {
    BYTE *l = *(BYTE **)NF_R(0x10179eac);
    return l && *(int *)(l + 4) == 19 && g_nf_coop_first && ((char **)*(BYTE **)(l + 8))[0] == g_nf_coop_first;
}
static void nft_coop_only(void) {   /* P01-P19 as the whole arena list (after the Combat builder's state resets) */
    BYTE *l = *(BYTE **)NF_R(0x10179eac); int k, n;
    if (!l) { l = ((BYTE *(__cdecl *)(int))NF_R(0x1000e000))(0x100); *(BYTE **)NF_R(0x10179eac) = l; }
    if (!l) return;
    n = *(int *)(l + 4);
    for (k = 0; k < n; k++) HeapFree(*(HANDLE *)NF_R(0x1004d630), 0, ((char **)*(BYTE **)(l + 8))[k]);
    *(int *)(l + 4) = 0; *(int *)NF_R(0x1004585c) = 0; *(int *)NF_R(0x10045858) = -1; g_nf_coop_first = g_nf_coop_last = 0;
    nf_coop_append(l);
}
static void nft_sync(void) {   /* main thread: options and species from the selected type */
    int t = nft_type(); LONG o = !nf_host_form() ? 0 : t == NFT_ARENA ? NF_ARENA : t == NFT_COOP ? (NF_ARENA | NF_COOP) : 0;
    WORD sp = o ? NMP_SPECIES_ARENA : g_nf_species0;
    if (t == NFT_COOP && o && !nft_coop_only_listed()) nft_coop_only();   /* the arena list was rebuilt under us */
    if (*(WORD *)NF_R(0x10046cb0) != sp) *(WORD *)NF_R(0x10046cb0) = sp;
    if (o != g_nf_opt) NMP_LOG("  nitro-types: type %d (%s) -> ARENA+ %s, CO-OP SCENES %s; species %04x", t, nft_name(t), o & NF_ARENA ? "on" : "off",
                               o & NF_COOP ? "on" : "off", sp);
    g_nf_opt = o; g_nmp_opts = o;
}
static void __cdecl nft_list(DWORD idx) {   /* the type-change switch, idx = type - 1 (0..6); runs before the stock list build */
    BYTE *l;
    if (idx == NFT_ARENA - 1 || idx == NFT_COOP - 1) {
        ((void (__cdecl *)(void))NF_R(0x10035800))();   /* Combat's arena list (*.cbt) */
        if (idx == NFT_COOP - 1) nft_coop_only();
    }
    nft_sync();
    l = *(BYTE **)NF_R(0x10179eac);
    NMP_LOG("  nitro-types: selected %lu '%s': type %d, form mask %02lx, team %ld, species %04x, arena list %d%s", idx + 1, nft_name(idx + 1), nft_type(),
            *(DWORD *)NF_R(0x1017a07c), *(LONG *)NF_R(0x1017a088), *(WORD *)NF_R(0x10046cb0), l ? *(int *)(l + 4) : -1,
            idx < 5 ? " (the stock list is built after this line)" : "");
}
static __declspec(naked) void nft_list_stub(void) {
    __asm {
        pushad
        push eax
        call nft_list
        add esp, 4
        popad
        cmp eax, 5
        jae ours
        mov ecx, g_nft_list_tab
        jmp dword ptr [ecx + eax*4]
    ours:
        jmp dword ptr [g_nft_list_back]
    }
}
static void __cdecl nft_rows(int x, int y, int first, int count) {   /* the popup's row draw for 7 rows (as 0x100341e0) */
    BYTE *disp = *(BYTE **)NF_R(0x10130488), *fp = *(BYTE **)NF_R(0x1013049c); int i, rh = *(int *)NF_R(0x10138c38);
    if (!disp || !fp) return;
    for (i = first < 0 ? 0 : first; i < first + count && i < 7; i++, y += rh)
        g_nft_w[i] = ((nf_text_fn)NF_R(0x10012dc0))(disp, 0, x + 8, y, *(int *)(fp + 0x408), g_nft_rows[i], 0);
    if (!g_nft_rowdraws++) NMP_LOG("  nitro-types: popup rows drawn (first %d, %d) - text widths %d %d %d %d %d %d %d (list hit area %d px wide)", first, count,
                                   g_nft_w[0], g_nft_w[1], g_nft_w[2], g_nft_w[3], g_nft_w[4], g_nft_w[5], g_nft_w[6], 0xd6 - 0x10);
}
static void __cdecl nft_popup(DWORD *desc, DWORD pic, DWORD b) {   /* the GAME TYPE popup opens (descriptor 0x100459d8, picture 0x24) */
    /* Picture 0x24 is a fixed 172 x 152 bitmap with 5 row boxes and its button (record s.0.5.17): 7 rows do not fit it. The form's
     * own 9-row list popup (hit id 11, 0x10032fe0) uses picture 6, 229 x 236, rows from (0x16, 0x30), list hit {2, 0x10, 0xd6, 0x2f,
     * 0xc6}, button {3, 0x92, 0xd7, 0xd1, 0xe1}; the 7-row popup borrows that picture and geometry. */
    static const DWORD list6[5] = { 2, 0x10, 0xd6, 0x2f, 0xc6 }, btn6[5] = { 3, 0x92, 0xd7, 0xd1, 0xe1 },
        list24[5] = { 2, 0xc, 0x9f, 0x1c, 0x71 }, btn24[5] = { 3, 0x59, 0xa0, 0x7c, 0x8c };
    DWORD *r2 = (DWORD *)NF_R(0x100459b0), *r3 = (DWORD *)NF_R(0x100459c4);
    int p = *(int *)NF_R(0x1004701c), rh = *(int *)NF_R(0x10138c38), seven = 0;
    if ((p == 3 || p == 4) && desc[6] == 5 && desc[8] == 5 && rh > 0 && rh < 40 && pic == 0x24) {
        seven = 1; pic = 6; desc[2] = 0xe5; desc[3] = 0xec; desc[4] = 0x16; desc[5] = 0x30; desc[6] = desc[8] = 7; desc[10] = (DWORD)(DWORD_PTR)nft_rows;
    }
    memcpy(r2, seven ? list6 : list24, 20); memcpy(r3, seven ? btn6 : btn24, 20);
    g_nft_opens++;
    NMP_LOG("  nitro-types: GAME TYPE popup open #%ld (provider %d): picture %lu, %lu rows, %lu x %lu at %lu,%lu, rows from +%lu,+%lu, row %d px, list hit %lu-%lu / %lu-%lu, button %lu-%lu / %lu-%lu",
            g_nft_opens, p, pic, desc[6], desc[2], desc[3], desc[0], desc[1], desc[4], desc[5], rh, r2[1], r2[2], r2[3], r2[4], r3[1], r3[2], r3[3], r3[4]);
    ((void (__cdecl *)(DWORD *, DWORD, DWORD))g_nft_popup0)(desc, pic, b);
}
static __declspec(naked) void nft_save_type(void) {   /* G5: replaces `mov edx, [0x10045860]` (no flag is read after it) */
    __asm {
        mov edx, g_nft_type_va
        mov edx, [edx]
        cmp edx, 5
        jle done
        mov edx, 1
    done:
        ret
    }
}
static DWORD g_nft_lookup0;
static const char *__cdecl nft_lookup(void *tab, const char *key) {   /* G6: the mode-string lookup of 0x1002e8b8 (mask -> "Race" ...) */
    const char *r = ((const char *(__cdecl *)(void *, const char *))g_nft_lookup0)(tab, key);
    if ((DWORD)(DWORD_PTR)key == NF_R(0x10045330)) {   /* the "Unknown" default: a mask outside 1 / 2 / 4 / 8 / 16 */
        BYTE *f = *(BYTE **)NF_R(0x1015b8dc); DWORD m = f ? *(DWORD *)(f + 0xd4) : 0;
        if (m == (1u << (NFT_ARENA - 1))) r = g_nft_rows[NFT_ARENA - 1];
        else if (m == (1u << (NFT_COOP - 1))) r = g_nft_rows[NFT_COOP - 1];
        NMP_LOG("  nitro-types: lobby mode text for form mask %02lx -> '%s'", m, r ? r : "(null)");
    }
    return r;
}
static void nf_open_note(void) {
    if (!g_nf_sh || !(g_nf_on || g_nf_types)) return;
    NMP_LOG("  nitro-form: at dpOpen - provider %d, game type %d (%s), form mask %02lx, team %ld, options %02lx, species word %04x", *(int *)NF_R(0x1004701c),
            nft_type(), g_nf_types ? nft_name(nft_type()) : "-", *(DWORD *)NF_R(0x1017a07c), *(LONG *)NF_R(0x1017a088), g_nf_opt, *(WORD *)NF_R(0x10046cb0));
}
static int nft_jmptab(DWORD at, DWORD tab) { BYTE *p = (BYTE *)(DWORD_PTR)NF_R(at); return p[0] == 0xff && p[1] == 0x24 && p[2] == 0x85 && *(DWORD *)(p + 3) == NF_R(tab); }
static int nft_attach(void) {   /* the number of sites written (15 = all) */
    static const BYTE c4[3] = { 0x83, 0xf8, 0x04 }, sv[2] = { 0x8b, 0x15 }, hh[2] = { 0xc7, 0x05 }, rows0[3] = { 0x53, 0x8b, 0x5c };
    static const DWORD fsites[6] = { 0x10031d94, 0x10033b88, 0x100341bc, 0x100357cf, 0x10036648, 0x10036ec7 };
    static const DWORD r2s[5] = { 2, 0xc, 0x9f, 0x1c, 0x71 }, r3s[5] = { 3, 0x59, 0xa0, 0x7c, 0x8c };
    DWORD r, *t0 = (DWORD *)NF_R(0x10045894); int ok, k, n = 0; BYTE w[8];
    ok = nf_is_call(0x10032391, 0x10021d80) && nf_bytes(0x100341e0, rows0, 3)
      && !memcmp((void *)(DWORD_PTR)NF_R(0x100459b0), r2s, 20) && !memcmp((void *)(DWORD_PTR)NF_R(0x100459c4), r3s, 20)
      && nf_bytes(0x1003230e, hh, 2) && *(DWORD *)NF_R(0x10032310) == NF_R(0x100459e4) && *(DWORD *)NF_R(0x10032314) == 0x98
      && nf_bytes(0x100342f7, c4, 3) && nft_jmptab(0x10034302, 0x100346f8)
      && nf_bytes(0x10032771, c4, 3) && nft_jmptab(0x1003277a, 0x1003369c) && nf_bytes(0x10036f36, c4, 3) && nft_jmptab(0x10036f3f, 0x10037224)
      && nf_bytes(0x100320aa, sv, 2) && *(DWORD *)NF_R(0x100320ac) == NF_R(0x10045860)
      && t0[0] == 0 && t0[6] == 0
      && nf_is_call(0x1002e978, 0x10039270) && *(BYTE *)NF_R(0x1002e96b) == 0x68 && *(DWORD *)NF_R(0x1002e96c) == NF_R(0x10045330);
    for (k = 0; ok && k < 6; k++) ok = *(DWORD *)NF_R(fsites[k]) == NF_R(0x10045894);
    for (k = 1; ok && k <= 5; k++) ok = t0[k] != 0;
    if (!ok) { NMP_LOG("  nitro-types: nitshell bytes NOT as f804f50d - game types off (the boxes stay off too)"); return 0; }
    for (k = 0; k < 5; k++) g_nft_rows[k] = (const char *)(DWORD_PTR)t0[k + 1];
    g_nft_rows[5] = "Arena Drop-In + AI"; g_nft_rows[6] = "Co-Op";
    for (k = 0; k <= 5; k++) g_nft_field[k] = t0[k];
    g_nft_field[6] = (DWORD)(DWORD_PTR)"Arena + AI"; g_nft_field[7] = (DWORD)(DWORD_PTR)"Co-Op"; g_nft_field[8] = 0;
    memcpy(g_nft_lim1, (void *)(DWORD_PTR)NF_R(0x1003369c), 20); g_nft_lim1[5] = g_nft_lim1[6] = g_nft_lim1[0];
    memcpy(g_nft_lim2, (void *)(DWORD_PTR)NF_R(0x10037224), 20); g_nft_lim2[5] = g_nft_lim2[6] = g_nft_lim2[0];
    g_nft_lookup0 = NF_R(0x10039270);
    g_nft_list_tab = NF_R(0x100346f8); g_nft_list_back = NF_R(0x10034329); g_nft_popup0 = NF_R(0x10021d80); g_nft_type_va = NF_R(0x10045860);
    g_nf_types = 1;   /* before the writes */
    r = (DWORD)(DWORD_PTR)g_nft_field; for (k = 0; k < 6; k++) n += nf_write(NF_R(fsites[k]), &r, 4);                       /* G4 x6 */
    n += nf_call(0x10032391, (void *)nft_popup);                                                                            /* G1 */
    w[0] = 6; n += nf_write(NF_R(0x100342f9), w, 1);                                                                         /* G2 cmp */
    { LONG rel = (LONG)((DWORD_PTR)nft_list_stub - (NF_R(0x10034302) + 5)); w[0] = 0xe9; memcpy(w + 1, &rel, 4); w[5] = w[6] = 0x90; }
    n += nf_write(NF_R(0x10034302), w, 7);                                                                                   /* G2 jmp */
    w[0] = 6; n += nf_write(NF_R(0x10032773), w, 1); n += nf_write(NF_R(0x10036f38), w, 1);                                  /* G3 cmps */
    r = (DWORD)(DWORD_PTR)g_nft_lim1; n += nf_write(NF_R(0x1003277d), &r, 4);
    r = (DWORD)(DWORD_PTR)g_nft_lim2; n += nf_write(NF_R(0x10036f42), &r, 4);                                                /* G3 tables */
    { LONG rel = (LONG)((DWORD_PTR)nft_save_type - (NF_R(0x100320aa) + 5)); w[0] = 0xe8; memcpy(w + 1, &rel, 4); w[5] = 0x90; }
    n += nf_write(NF_R(0x100320aa), w, 6);                                                                                   /* G5 */
    n += nf_call(0x1002e978, (void *)nft_lookup);                                                                           /* G6 */
    return n;
}

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
    if (GetEnvironmentVariableA("I76_NITRO_GAMETYPES", v, sizeof v) && v[0] == '1') {   /* the GAME TYPE entries, no boxes */
        k = nft_attach();
        if (k) k += nf_call(0x10001531, (void *)nf_ctor);
        NMP_LOG("  nitro-types: %s - %d/16 nitshell sites (field names x6, popup open, type switch x2, limit switches x4, prefs save, mode string, constructor);"
                " GAME TYPE rows 6 '%s' and 7 '%s' on the IPX / internet host forms, check boxes off", k == 16 ? "ON" : k ? "PARTIAL" : "OFF", k,
                g_nft_rows[5] ? g_nft_rows[5] : "-", g_nft_rows[6] ? g_nft_rows[6] : "-");
        return;
    }
    g_nf_on = 1;   /* before the writes: nf_draw checks it */
    r = (DWORD)(DWORD_PTR)nf_redraw; n += nf_write(NF_R(0x100318f7), &r, 4);
    for (k = 0; k < 3; k++) n += nf_call(rdcalls[k], (void *)nf_redraw);
    n += nf_call(0x10001531, (void *)nf_ctor);
    {   BYTE w[6] = { 0x0f, 0x87 }; LONG rel = (LONG)((DWORD_PTR)nf_ja_stub - (NF_R(0x1003219b) + 6)); memcpy(w + 2, &rel, 4); n += nf_write(NF_R(0x1003219b), w, 6); }
    NMP_LOG("  nitro-form: %s - %d/6 nitshell sites (constructor, click, redraw x4); boxes ARENA+ (0x10) and CO-OP SCENES (0x11) on host forms, both off = stock",
            n == 6 ? "ON" : "PARTIAL", n);
}
