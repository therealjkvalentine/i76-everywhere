/* ===========================================================================
 * TERRAIN SHADE TABLE  (I76_SHADE_TABLE; terrain-pass-opt lane 2026-10-25, docs/records/TERRAIN-PASS-OPT-PLAN-2026-10-25.md unit U7)
 * ===========================================================================
 * Included by strlkproxy.c after faredge.c (before terrainmorph.c). Gold only.
 *   I76_SHADE_TABLE=1        the shade loop's call of renderer_ShadeTerrainVertex 0x490fb0 (at 0x490f50) takes the vertex's static
 *                            slope term from a per-sample table instead of recomputing it (4 + 1 world_GetTerrainSampleRaw reads, the
 *                            normal, the rsqrt 0x495000 whose result the exe discards, a divide) every pass
 *   I76_SHADE_TABLE_VERIFY=1 lab: every vertex is also shaded by the stock function and the two floats compared bit for bit (a log line
 *                            per 600 frames: vertices, table hits, mismatches)
 * THE STOCK FUNCTION (i76.exe 6319abf7, read 2026-10-25): shade(sx, sz, depth) =
 *     k = 0.1 / [0x6442c0];  h = H(sx, sz) k and the four neighbours' H x k  (H = world_GetTerrainSampleRaw 0x493160, 12-bit heights)
 *     nx, nz = the quarter sums of the neighbour differences (stored as floats);  r = rsqrt(nx^2 + nz^2 - (-1))  (r is popped unused)
 *     s = (L.y - nx L.x) - nz L.z      (L = [0x59c578] / [0x59c57c] / [0x59c580])
 *     s < 0 -> A ([0x59c54c]);  else min(1, s x clamp(depth [0x643600] + [0x6435fc], 0.75, 1) + A)
 * Only the tail (from the comparison with 0) depends on the pass (depth). s depends on the sample, k and L.
 * HOW IT STAYS BIT-EXACT: the exe's own machine code runs, copied from 0x490fb0..0x4911d2 into an executable buffer: the five H calls
 * relocated, the rsqrt call replaced by fldz (the dummy is popped where r was), and at 0x491155 (s in st(0), the x87 register) a jump
 * out that stores s as an 80-bit value (fstp tbyte: no rounding whatever the precision control) into the sample's slot, then the copied
 * tail. A later vertex on the same sample loads the 80-bit s (fld tbyte), builds the same frame (sub esp 0x40, push esi, push edi) and
 * enters the same copied tail. Same operations, same operands, same register precision: the same float.
 * Slots: per 128 x 128 tile (the exe's own tile grid, 0x644380), 128 x 128 x 16 bytes reserved and committed on first touch (only
 * touched pages take memory): 10 bytes s, a DWORD generation. The generation moves on at every world_InitTerrainGrid 0x493080 (mission
 * load: its one call at 0x493bdf is wrapped) and whenever [0x6442c0] or L differ from the values the table was built with. */
static int g_ps_on, g_ps_verify;
static DWORD g_ps_gen = 1, g_ps_k_raw, g_ps_l_raw[3], g_ps_hits, g_ps_miss, g_ps_out, g_ps_vn, g_ps_vbad, g_ps_gens, g_ps_frames;
static BYTE *g_ps_tile[16384];
static BYTE *g_ps_code;                          /* the copied stock function */
static DWORD g_ps_head, g_ps_tail, g_ps_store_back, g_ps_cur_slot, g_ps_next_init = 0x00493080;
static __declspec(naked) void ps_store(void) {   /* the copy's 0x491155 jumps here: s in st(0) */
    __asm {
        mov eax, g_ps_cur_slot
        fld st(0)
        fstp tbyte ptr [eax]
        mov ecx, g_ps_gen
        mov dword ptr [eax + 12], ecx
        fcom dword ptr ds:[0x004be800]               /* the instruction the jump replaced */
        jmp dword ptr [g_ps_store_back]
    }
}
static BYTE * __cdecl ps_slot(int sx, int sz) {   /* the sample's slot (0 = off the tile grid: the stock call) */
    int tx = (sx + 0xc00) >> 7, tz = (sz + 0xc00) >> 7; BYTE *t;
    DWORD k = *(volatile DWORD *)0x006442c0, l0 = *(volatile DWORD *)0x0059c578, l1 = *(volatile DWORD *)0x0059c57c, l2 = *(volatile DWORD *)0x0059c580;
    if (k != g_ps_k_raw || l0 != g_ps_l_raw[0] || l1 != g_ps_l_raw[1] || l2 != g_ps_l_raw[2]) {
        g_ps_k_raw = k; g_ps_l_raw[0] = l0; g_ps_l_raw[1] = l1; g_ps_l_raw[2] = l2; g_ps_gen++; g_ps_gens++; }
    if (tx < 0 || tx > 127 || tz < 0 || tz > 127) { g_ps_out++; return 0; }
    t = g_ps_tile[tz * 128 + tx];
    if (!t) { t = (BYTE *)VirtualAlloc(NULL, 128 * 128 * 16, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE); if (!t) { g_ps_out++; return 0; } g_ps_tile[tz * 128 + tx] = t; }
    return t + ((((sz + 0xc00) & 127) << 7) + ((sx + 0xc00) & 127)) * 16;
}
static __declspec(naked) float __cdecl ps_shade(int sx, int sz, float depth) {   /* replaces the call at 0x490f50 */
    __asm {
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call ps_slot
        add esp, 8
        test eax, eax
        jz stock
        mov ecx, g_ps_gen
        cmp dword ptr [eax + 12], ecx
        jne miss
        inc g_ps_hits
        sub esp, 0x40                                 /* the stock frame at 0x491155: sub esp,0x40 / push esi / push edi */
        push esi
        push edi
        fld tbyte ptr [eax]
        jmp dword ptr [g_ps_tail]
    miss:
        inc g_ps_miss
        mov g_ps_cur_slot, eax
        jmp dword ptr [g_ps_head]
    stock:
        mov eax, 0x00490fb0
        jmp eax
    }
}
typedef float (__cdecl *ps_fn_t)(int, int, float);
static float __cdecl ps_shade_verify(int sx, int sz, float depth) {   /* I76_SHADE_TABLE_VERIFY: both, compared */
    float a = ((ps_fn_t)(DWORD_PTR)0x00490fb0)(sx, sz, depth), b = ps_shade(sx, sz, depth);
    g_ps_vn++; if (*(DWORD *)&a != *(DWORD *)&b) g_ps_vbad++;
    return a;
}
static int __cdecl ps_init_wrap(DWORD a, DWORD b, DWORD c) {     /* world_InitTerrainGrid at 0x493bdf: a new terrain */
    int r = ((int (__cdecl *)(DWORD, DWORD, DWORD))(DWORD_PTR)g_ps_next_init)(a, b, c);
    g_ps_gen++; g_ps_gens++;
    return r;
}
static void shade_table_frame(void) {
    if (!g_ps_on || ++g_ps_frames < 600) return;
    mlog("  shade-table: 600 frames: %lu vertices from the table, %lu computed (and stored), %lu off the grid (stock); %lu generations",
         (unsigned long)g_ps_hits, (unsigned long)g_ps_miss, (unsigned long)g_ps_out, (unsigned long)g_ps_gens);
    if (g_ps_verify) mlog("  shade-table verify: %lu vertices compared with the stock function, %lu bit mismatches", (unsigned long)g_ps_vn, (unsigned long)g_ps_vbad);
    g_ps_hits = g_ps_miss = g_ps_out = g_ps_gens = g_ps_vn = g_ps_vbad = 0; g_ps_frames = 0;
}
static void apply_shade_table(void) {
    /* the stock function, as read from the pristine exe 6319abf7: its first and last bytes and the call / patch points */
    static const BYTE head0[9] = { 0x83, 0xec, 0x40, 0xd9, 0x05, 0x20, 0xe8, 0x4b, 0x00 };   /* sub esp,0x40; fld dword [0x4be820] */
    static const BYTE at155[6] = { 0xd8, 0x15, 0x00, 0xe8, 0x4b, 0x00 };                     /* fcom dword [0x4be800] */
    static const BYTE end[4] = { 0x83, 0xc4, 0x40, 0xc3 };                                    /* add esp,0x40; ret at 0x4911cf */
    static const DWORD hcalls[5] = { 0x490fcf, 0x490fec, 0x491009, 0x491026, 0x491041 };
    const DWORD F = 0x00490fb0, N = 0x004911d3 - 0x00490fb0; BYTE cs[5] = { 0xe8 }, w5[5] = { 0xe8 }; LONG rel; int i, ok = 1;
    int on = env_flag("I76_SHADE_TABLE", 4, 0);
    g_ps_verify = env_flag("I76_SHADE_TABLE_VERIFY", 4, 0) == 1;
    if (on != 1 && !g_ps_verify) return;
    if (g_exe != EXE_GOLD) { mlog("  shade-table: Gold only - off"); return; }
    if (memcmp((void *)(DWORD_PTR)F, head0, 9) || memcmp((void *)(DWORD_PTR)0x00491155, at155, 6) || memcmp((void *)(DWORD_PTR)0x004911cf, end, 4)) ok = 0;
    for (i = 0; i < 5 && ok; i++) { rel = (LONG)(0x00493160 - (hcalls[i] + 5)); memcpy(cs + 1, &rel, 4); if (memcmp((void *)(DWORD_PTR)hcalls[i], cs, 5)) ok = 0; }
    rel = (LONG)(0x00495000 - (0x0049112b + 5)); memcpy(cs + 1, &rel, 4); if (ok && memcmp((void *)(DWORD_PTR)0x0049112b, cs, 5)) ok = 0;
    rel = (LONG)(F - (0x00490f50 + 5)); memcpy(cs + 1, &rel, 4); if (ok && memcmp((void *)(DWORD_PTR)0x00490f50, cs, 5)) ok = 0;
    if (!ok) { mlog("  shade-table: renderer_ShadeTerrainVertex / its call differ from the stock bytes - not applied"); return; }
    g_ps_code = (BYTE *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_ps_code) { mlog("  shade-table: no memory - not applied"); return; }
    memcpy(g_ps_code, (void *)(DWORD_PTR)F, N);
    for (i = 0; i < 5; i++) { DWORD o = hcalls[i] - F; rel = (LONG)(0x00493160 - ((DWORD)(DWORD_PTR)g_ps_code + o + 5)); memcpy(g_ps_code + o + 1, &rel, 4); }
    {   DWORD o = 0x0049112b - F; g_ps_code[o] = 0xd9; g_ps_code[o + 1] = 0xee; g_ps_code[o + 2] = 0x90; g_ps_code[o + 3] = 0x90; g_ps_code[o + 4] = 0x90; }   /* fldz: r is popped unused */
    {   DWORD o = 0x00491155 - F; rel = (LONG)((DWORD)(DWORD_PTR)ps_store - ((DWORD)(DWORD_PTR)g_ps_code + o + 5));
        g_ps_code[o] = 0xe9; memcpy(g_ps_code + o + 1, &rel, 4); g_ps_code[o + 5] = 0x90;
        g_ps_store_back = (DWORD)(DWORD_PTR)g_ps_code + o + 6; }
    /* the hit path enters at the copy's 0x491155 itself, i.e. the fcom: but that byte range now holds the jump out, so the hit path
       enters a second, unpatched copy of the tail (0x491155..0x4911d2) placed after the first */
    {   DWORD o2 = N + 16, tl = 0x004911d3 - 0x00491155;
        memcpy(g_ps_code + o2, (void *)(DWORD_PTR)0x00491155, tl);   /* the tail has no calls, only short forward jumps: position-free */
        g_ps_tail = (DWORD)(DWORD_PTR)g_ps_code + o2; }
    g_ps_head = (DWORD)(DWORD_PTR)g_ps_code;
    FlushInstructionCache(GetCurrentProcess(), g_ps_code, 4096);
    st_call_site(0x00493bdf, 0x00493080, (void *)ps_init_wrap, &g_ps_next_init, "shade-table world_InitTerrainGrid call (new terrain)");
    rel = (LONG)((DWORD_PTR)(g_ps_verify ? (void *)ps_shade_verify : (void *)ps_shade) - (0x00490f50 + 5)); memcpy(w5 + 1, &rel, 4);
    rel = (LONG)(F - (0x00490f50 + 5)); memcpy(cs + 1, &rel, 4);
    g_ps_on = patch_bytes(0x00490f50, cs, w5, 5, "shade-table call");
    mlog("  shade-table: %s (the terrain shade loop's slope term from a per-sample table; the exe's own code copied at %p, rsqrt dropped: its result was unused)%s",
         g_ps_on ? "on" : "NOT applied", (void *)g_ps_code, g_ps_verify ? "; VERIFY on (every vertex also shaded by the stock function, compared bit for bit; the stock value is drawn)" : "");
}
