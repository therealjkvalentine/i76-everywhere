/* nitro_ai.c - ARENA+ on Nitro: AI melee in a network combat arena (nitro-mp-design lane, 2026-10-21; estimate item 4).
 * Record: docs/records/NITRO-MP-DESIGN-2026-10-21.md s.0.5.5. A port of the Gold AI lane's aimelee.c 1, 2, 4, 6, 7, 8 and
 * mpfill.c (fill only) and the co-op AI sync of strlkproxy.c (coop_ai_*), re-addressed for nitro.exe 28b8ae27 through the
 * nitro-port lane's sites_nitro.h (read-only; each looked-up value checked against this lane's own reading) - their files
 * are not edited. Included after nitro_mp.c (it uses nmp_send, nmp_role, nmp_arena, NMP_ROW and the resolved globals).
 *
 * WHEN: only in an ARENA+ session (ANet species 0x7676, nitro_mp.c) of a COMBAT arena (*.cbt), on every machine. A stock
 * session - or a race / CTF - is never touched: every patched call site below checks nai_on() first and otherwise does
 * exactly what the stock call did.
 *
 * WHAT (Gold reference in brackets):
 *   POOL [aimelee 8]   after the arena's ODEF walk (ODEF handler 0x4bd4b0, call 0x4b3630 at 0x4bd4bf [0x4b45bf ->
 *                      0x4b7a90]) NAI_POOL=7 car records go through the OBJ handler 0x4b3660 [0x4b7ac0]: class-1 car, team 7
 *                      (Men In Black, the popup's 8th name in Nitro too), a multiplayer variant of the original cars
 *                      (byte-identical in nitro.zfs), parked at -9000,-9000. Same records on every machine = same label
 *                      indices, so 'AT' needs no ids.
 *   FILL [mpfill]      host: AI in play = clamp(NO. DRIVERS - humans, 0, pool); NO. DRIVERS = the host form's max drivers
 *                      (nitshell form [0x32] = 0x1017a070). A joining human parks the AI (a wreck first, else the one
 *                      farthest from the humans); a leaving human brings one back at the free spawn point. Park = FSM
 *                      teleport 0x406120 [0x414bc0] + behaviour 0x21 'hide' 0x415490 [0x412830]; bring = teleport +
 *                      startCar 0x466600 [0x467400].
 *   SYNC [coop_ai]     host: every AI car in 'AT' (2 records / packet, 108 or 208 B, unreliable; parked cars every 2 s),
 *                      state by net_PackVehicleState 0x463660 [0x4644d0], fire mask from the AI's trigger pulls (0x4064e6
 *                      [0x414f86] -> weapon_SetTrigger 0x4af010), byte 3 = 0x80 | team | 0x40 parked. Joiner: the record
 *                      goes to the same label through the remote-car mirror 0x463a20 [0x464890]; ai_FrameTick is not run
 *                      on a joiner (call 0x432e24 [0x403ddf]), object_ClassDamage 0x44fd80 [0x462040] is skipped for the
 *                      mirrored cars at its 5 call sites (0x461114 0x46504b 0x465693 0x4a7c43 0x4a7cd6), the host's
 *                      trigger pulls are replayed for 150 ms.
 *   TICK [aimelee 1]   host, at the "single-player melee?" call 0x4079a2 [0x40a5d0] in ai_FrameTick: every live AI car
 *                      gets ai_SetBehaviour(car, nearest live human, 0 = attack) each frame (sticky target, 20 %), skill
 *                      once per car through nai_skill() (= difficulty.c's mapping on Nitro's DEF byte 0x5fb0fc [0x654b9c]:
 *                      Wimp 4, Champ 3, Badass 1; I76_AIMELEE_SKILL overrides), host's car attacker cap 8 (0x418710).
 *   KILL [aimelee 2]   host, at 0x46332e [0x46419d] (`call 0x42fee0` near the end of entity_DamageAndKill 0x462c00; edi =
 *                      victim, ebp = damage record): an AI victim -> 'AK' {seq, killer id, label, score, own} RELIABLE to
 *                      the group; every machine prints "<AI> was destroyed by <player>" (0x4447a0); the killer's machine
 *                      adds 1 kill and the score (victim mass x killer 1/mass x [0x4c4624]) to its own row (0x447050).
 *   RESPAWN [aimelee 6] host: 5 s after an AI car died, a fresh car of the same label at the spawn point farthest from every
 *                      car (team-0 spawn table 0x5414f8 + k*0x40, count [0x5414d8]) by the spawner 0x44c930 [0x4513c0],
 *                      the label entry repointed, the wreck removed (0x454070 + 0x4644b0); a joiner does the same when the
 *                      host's 'AT' says "alive" and its copy is a wreck. Dead humans ask for a respawn (0x44caf0(1)).
 *   ROWS [aimelee 7]   every AI car in play holds a row of Nitro's player table (0x53ed08, 16 x 0x50: id 0x7E00 + n, name,
 *                      flags team << 16 | 2, +0x30 latency -1, +0x44 1.0, +0x48 team 7), from the top slot down, counted
 *                      in [0x53ed00]; its owner id (entity +0x484 [+0x480]) is the row id. The host keeps the AI rows'
 *                      numbers (deaths, -500 with no killer, kills of humans read from the victim's killer id +0x486).
 * NOT PORTED (record s.0.5.5): co-op scenes / scaling, waves, the teams ledger of the fill, host-migration reconcile,
 * the scoreboard box size (8 rows: enough for the default fill), 'AV' pool announcement.
 */
#define NAI_POOL 7
#define NAI_ID0 0x7E00
#define NAI_TEAM 7
#define NAI_MAXL 2048
static int nai_is_ai_id(unsigned id) { return id >= NAI_ID0 && id < NAI_ID0 + 64; }
static DWORD n_lab, n_mission, n_simtime, n_beh, n_skill, n_cap, n_health, n_objid, n_setscore, n_chat, n_name, n_spawner,
             n_findrec, n_remove, n_mirror, n_wlist, n_trigger, n_cdamage, n_killk, n_spcount, n_sptab, n_teamlist, n_teamcnt,
             n_teleport, n_startcar, n_defbyte, n_spmelee, n_respawn, n_respawn_flag, n_ingame;
static volatile LONG g_nai_ok;
static HMODULE g_nai_shell;

/* ---- the session / arena ---- */
static int nai_combat_name(const char *m) { size_t L = strlen(m); return L > 4 && _stricmp(m + L - 4, ".cbt") == 0; }
static int g_nai_inj; static char g_nai_inj_m[16];
static int g_nai_coop; static char g_nai_coop_m[16];   /* CO-OP SCENES: an ARENA+ session on one of Nitro's own campaign missions pNN.msn */
static int nai_coop_name(const char *m) { return (m[0] | 0x20) == 'p' && m[1] >= '0' && m[1] <= '9' && m[2] >= '0' && m[2] <= '9' && _stricmp(m + 3, ".msn") == 0; }
static int nai_pool_on(void) { return g_nai_ok && nmp_arena() && g_nai_inj && _strnicmp((char *)(DWORD_PTR)n_mission, g_nai_inj_m, 15) == 0; }
static int nai_coop_on(void) { return g_nai_ok && nmp_arena() && g_nai_coop && _strnicmp((char *)(DWORD_PTR)n_mission, g_nai_coop_m, 15) == 0; }
static int nai_on(void) { return nai_pool_on() || nai_coop_on(); }

/* ---- label table and cars ---- */
static BYTE *nai_tab(void) { return *(BYTE **)(DWORD_PTR)(n_lab + 4); }
static int nai_count(void) { int c = *(int *)(DWORD_PTR)(n_lab + 8); return c > 0 && c <= NAI_MAXL ? c : 0; }
static BYTE *nai_slot_car(int k) { BYTE *p = NMP_ROW(k); return *(WORD *)p && !nai_is_ai_id(*(WORD *)p) ? *(BYTE **)(p + 0x28) : NULL; }
static BYTE *nai_object(int i) {                     /* a mission vehicle no player drives [coop_ai_object] */
    BYTE *o, *tab = nai_tab(); int k, count = nai_count();
    if (!tab || i >= count) return NULL;
    o = *(BYTE **)(tab + i * 16 + 8);
    if (!o || *(int *)(o + 0x6c) != 1 || !*(BYTE **)(o + 0x70) || (o[0x10] & 0x10)) return NULL;
    for (k = 0; k < 16; k++) { BYTE *p = NMP_ROW(k); if (*(WORD *)p && *(BYTE **)(p + 0x28) == o) return NULL; }
    return o;
}
static int nai_alive(BYTE *o) { BYTE *e = o ? *(BYTE **)(o + 0x70) : NULL; return e && !(e[0x458] & 0x20) && !(*(DWORD *)(o + 0x10) & 0x200); }
static int nai_team(BYTE *o) { return (int)((*(DWORD *)(o + 0x10) >> 16) & 7); }

/* ---- pool records (injected at load) and their state ---- */
static BYTE g_nai_body[NAI_POOL][100]; static int g_nai_li[NAI_POOL], g_nai_parked[NAI_POOL], g_nai_pool_n;
static DWORD g_nai_park_since[NAI_MAXL];
static const char *const g_nai_cars[] = { "valepre1", "valepre2", "valepre3", "vastryd1", "vastryd2", "vastryd3", "vazamz1", "vazamz2", "vazamz3",
    "vccameo1", "vccameo2", "vccameo3", "vcgcour1", "vcgcour2", "vcgcour3", "vcmanta1", "vcmanta2", "vcmanta3", "vcroyal1", "vcroyal2", "vcroyal3",
    "vcpolic1", "vcpolic2", "vcpolic3", "vcvan1", "vcvan2", "vcvan3", "vdlight1", "vdlight2", "vdlight3", "vdstag1", "vdstag2", "vdstag3",
    "vfcoupe1", "vfcoupe2", "vfcoupe3", "vfdclyd1", "vfdclyd2", "vfdclyd3", "vfpalmn1", "vfpalmn2", "vfpalmn3", "vfratlr1", "vfratlr2", "vfratlr3",
    "vfypony1", "vfypony2", "vfypony3", "vgoon1", "vgoon2", "vgoon3", "vjsovrn1", "vjsovrn2", "vjsovrn3", "vmxmarx1", "vmxmarx2", "vmxmarx3",
    "vpjrabt1", "vpjrabt2", "vpjrabt3", "vppirna1", "vppirna2", "vppirna3", "vavikea1", "vavikea2", "vavikea3" };   /* aimelee.c's list (I76.ZFS = nitro.zfs names) */
static int nai_pool_index(int li) { int q; for (q = 0; q < g_nai_pool_n; q++) if (g_nai_li[q] == li) return q; return -1; }
static int nai_parked_li(int li) { int q = nai_pool_index(li); return q >= 0 && g_nai_parked[q]; }
static int nai_ordinal(int li) { return nai_pool_index(li); }
static void nai_coop_load(const char *m);
static int __cdecl nai_odef(int *a, BYTE *b, int *c) {   /* replaces `call 0x4b3630` at 0x4bd4bf */
    int r = ((int (__cdecl *)(int *, BYTE *, int *))(DWORD_PTR)0x004b3630)(a, b, c), i, k, made = 0; unsigned h = 0;
    const char *m = (const char *)(DWORD_PTR)n_mission; BYTE *tab;
    g_nai_inj = 0; g_nai_pool_n = 0; g_nai_coop = 0;
    if (g_nai_ok && nmp_arena() && nai_coop_name(m)) { nai_coop_load(m); return r; }
    if (!g_nai_ok || !nmp_arena() || !nai_combat_name(m)) {
        if (g_nai_ok && nai_combat_name(m)) NMP_LOG("  nitro-ai: '%s' outside an ARENA+ session - stock arena, no AI pool", m);
        return r;
    }
    for (i = 0; m[i]; i++) h = h * 31 + (BYTE)(m[i] | 0x20);
    for (i = 0; i < NAI_POOL; i++) {
        BYTE chunk[108], *body = chunk + 8; const char *stem = g_nai_cars[(h + i * 7) % (sizeof(g_nai_cars) / sizeof(g_nai_cars[0]))];
        float px = -9000.0f + (float)(i % 3) * 25.0f, pz = -9000.0f + (float)(i / 3) * 25.0f;
        memset(chunk, 0, sizeof chunk); memcpy(chunk, "OBJ", 4); *(DWORD *)(chunk + 4) = 108;
        strncpy((char *)body, stem, 8);
        for (k = 0; k < i; k++) if (_strnicmp((char *)g_nai_body[k], stem, 8) == 0) break;
        if (k < i) body[7] |= 0x80;
        *(float *)(body + 8) = 1.0f; *(float *)(body + 24) = 1.0f; *(float *)(body + 40) = 1.0f;
        *(float *)(body + 44) = px; *(float *)(body + 48) = 0.0f; *(float *)(body + 52) = pz;
        memcpy(body + 56, "I76P", 4); body[60] = 1; *(float *)(body + 72) = px; *(float *)(body + 76) = pz;
        *(DWORD *)(body + 92) = 1; body[98] = NAI_TEAM;
        memcpy(g_nai_body[i], body, 100);
        if (((int (__cdecl *)(BYTE *))(DWORD_PTR)0x004b3660)(chunk)) made++;
        else NMP_LOG("  nitro-ai: pool car %d '%.8s' NOT built by the OBJ handler", i + 1, stem);
    }
    tab = nai_tab();
    for (i = 0; i < NAI_POOL; i++) {   /* label indices of the pool cars (same order on every machine) */
        int li, cnt = nai_count(); g_nai_li[i] = -1;
        for (li = 0; tab && li < cnt; li++) if (memcmp(tab + li * 16, g_nai_body[i], 8) == 0) { g_nai_li[i] = li; break; }
        g_nai_parked[i] = 1; if (g_nai_li[i] >= 0) g_nai_park_since[g_nai_li[i]] = GetTickCount();
    }
    g_nai_pool_n = NAI_POOL; g_nai_inj = made > 0; strncpy(g_nai_inj_m, m, 15); g_nai_inj_m[15] = 0;
    NMP_LOG("  nitro-ai: '%s' (ARENA+ combat) - %d of %d AI pool cars built, labels %d %d %d %d %d %d %d, parked at -9000,-9000",
            m, made, NAI_POOL, g_nai_li[0], g_nai_li[1], g_nai_li[2], g_nai_li[3], g_nai_li[4], g_nai_li[5], g_nai_li[6]);
    return r;
}

/* ---- names, skill, rows ---- */
static const char *nai_name(int k, char *buf) {     /* the Gold AUTO MELEE list is in i76shell; Nitro: a fixed list */
    static const char *const nm[] = { "Torque Daisy", "Gasket Head", "Tar Mack", "Griffin Farquar", "Lug Nut", "Smokey Jo", "Dusty Rhodes" };
    strcpy(buf, k >= 0 && k < 7 ? nm[k] : "AI"); return buf;
}
static int nai_skill(void) {                         /* difficulty.c's mapping on Nitro's DEF byte */
    static const int map[3] = { 4, 3, 1 }; char v[8]; int raw = *(volatile BYTE *)(DWORD_PTR)n_defbyte;
    if (GetEnvironmentVariableA("I76_AIMELEE_SKILL", v, sizeof v) && atoi(v) >= 1 && atoi(v) <= 5) return atoi(v);
    return map[raw <= 2 ? raw : 1];
}
static struct { short k, d; int s; } g_nai_led[64];
static BYTE *nai_row(unsigned id) { int k; for (k = 0; k < 16; k++) if (*(WORD *)NMP_ROW(k) == (WORD)id) return NMP_ROW(k); return NULL; }
static void nai_row_add(unsigned id, int dk, int dd, int ds, const char *why) {   /* host: an AI's numbers */
    int n = (int)id - NAI_ID0, k, d, s; BYTE *p = nai_row(id);
    if (n < 0 || n >= 64 || nmp_role() != 1) return;
    k = g_nai_led[n].k + dk; d = g_nai_led[n].d + dd; s = g_nai_led[n].s + ds; if (s < 0) s = 0;
    g_nai_led[n].k = (short)k; g_nai_led[n].d = (short)d; g_nai_led[n].s = s;
    if (p) ((void (__cdecl *)(int, int, int, int))(DWORD_PTR)n_setscore)((int)id, s, k, d);
    NMP_LOG("  nitro-ai: row %u (AI #%d) %s: %+d kill %+d death %+d -> %d / %d / %d", id, n + 1, why, dk, dd, ds, k, d, s);
}
static void nai_rows_tick(int role) {                /* every machine: AI rows for the AI cars in play */
    static DWORD last; DWORD now = GetTickCount(); int q, s; float t = (float)((double (__cdecl *)(void))(DWORD_PTR)n_simtime)();
    if (now - last < 200) return;
    last = now;
    for (q = 0; q < g_nai_pool_n; q++) {
        int li = g_nai_li[q]; BYTE *o = li >= 0 ? nai_object(li) : NULL, *p; WORD id = (WORD)(NAI_ID0 + q); int want;
        if (!o) continue;
        *(WORD *)(*(BYTE **)(o + 0x70) + 0x484) = id;   /* owner id: kill attribution, 'AT' numbers */
        want = !g_nai_parked[q];
        p = nai_row(id);
        if (want && !p) {
            char nm[24];
            for (s = 15; s >= 0 && *(WORD *)NMP_ROW(s); s--) ;
            if (s < 0) continue;
            p = NMP_ROW(s); memset(p, 0, 0x50);
            *(WORD *)p = id; nai_name(q, nm); strncpy((char *)p + 2, nm, 23);
            *(DWORD *)(p + 0x1c) = ((DWORD)nai_team(o) << 16) | 2;
            *(float *)(p + 0x2c) = t; *(DWORD *)(p + 0x30) = 0xbf800000; *(float *)(p + 0x44) = 1.0f; *(int *)(p + 0x48) = nai_team(o);
            *(short *)(p + 0x3c) = g_nai_led[q].k; *(short *)(p + 0x3e) = g_nai_led[q].d; *(int *)(p + 0x40) = g_nai_led[q].s;
            (*(volatile int *)(DWORD_PTR)a_count)++;
            NMP_LOG("  nitro-ai: row for AI #%d '%s' (label %d) in slot %d, id %u", q + 1, nm, li, s, id);
        } else if (!want && p) {
            g_nai_led[q].k = *(short *)(p + 0x3c); g_nai_led[q].d = *(short *)(p + 0x3e); g_nai_led[q].s = *(int *)(p + 0x40);
            *(WORD *)p = 0; (*(volatile int *)(DWORD_PTR)a_count)--;
            NMP_LOG("  nitro-ai: row of AI #%d given back (parked)", q + 1);
            continue;
        }
        if (p) {
            *(float *)(p + 0x2c) = t;
            if (role != 1) { g_nai_led[q].k = *(short *)(p + 0x3c); g_nai_led[q].d = *(short *)(p + 0x3e); g_nai_led[q].s = *(int *)(p + 0x40); }
        }
    }
}

/* ---- teleport, park, bring, free spawn ---- */
static void nai_teleport(BYTE *o, double x, double z, int hdg) {
    BYTE path[0x58]; float node[3]; int spd = 0;
    memset(path, 0, sizeof path); node[0] = (float)x; node[1] = 0.0f; node[2] = (float)z; *(float **)(path + 0x54) = node;
    hdg %= 360; if (hdg < 0) hdg += 360;
    ((void (__cdecl *)(BYTE *, BYTE *, int *, int *, int *, int *))(DWORD_PTR)n_teleport)(o, path, &spd, &hdg, NULL, NULL);
}
static double nai_d2(BYTE *a, double x, double z) { double dx = *(double *)(a + 0x40) - x, dz = *(double *)(a + 0x50) - z; return dx * dx + dz * dz; }
static double nai_near_car(double x, double z) {
    double best = 1e30; int k, q;
    for (k = 0; k < 16; k++) { BYTE *h = nai_slot_car(k); if (h && nai_alive(h)) { double d = nai_d2(h, x, z); if (d < best) best = d; } }
    for (q = 0; q < g_nai_pool_n; q++) { BYTE *o = g_nai_li[q] >= 0 ? nai_object(g_nai_li[q]) : NULL; if (o && !g_nai_parked[q] && nai_alive(o)) { double d = nai_d2(o, x, z); if (d < best) best = d; } }
    return best;
}
static int nai_free_spawn(double *x, double *z) {   /* team-0 spawn table: the point farthest from every live car (>= 30 m) */
    int s, ns = *(int *)(DWORD_PTR)n_spcount, best_s = -1; double best = -1;
    for (s = 0; s < ns && s < 64; s++) {
        double d = nai_near_car(*(double *)(DWORD_PTR)(n_sptab + 0x28 + s * 0x40), *(double *)(DWORD_PTR)(n_sptab + 0x38 + s * 0x40));
        if (d > best) { best = d; best_s = s; }
    }
    if (best_s < 0 || best < 900.0) return -1;
    *x = *(double *)(DWORD_PTR)(n_sptab + 0x28 + best_s * 0x40); *z = *(double *)(DWORD_PTR)(n_sptab + 0x38 + best_s * 0x40);
    return best_s;
}
static void nai_park(int q, const char *why) {
    BYTE *o = nai_object(g_nai_li[q]);
    if (!o) return;
    if (nai_alive(o)) {
        nai_teleport(o, *(float *)(g_nai_body[q] + 72), *(float *)(g_nai_body[q] + 76), 0);
        if (*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) ((int (__cdecl *)(BYTE *, BYTE *, int))(DWORD_PTR)n_beh)(o, NULL, 0x21);
    }
    g_nai_parked[q] = 1; g_nai_park_since[g_nai_li[q]] = GetTickCount();
    NMP_LOG("  nitro-ai: parked AI #%d '%.8s' (label %d, %s) - %s", q + 1, (char *)o, g_nai_li[q], nai_alive(o) ? "live" : "wreck", why);
}
static BYTE *nai_recreate(int q, int sp, const char *why);
static void nai_bring(int q, const char *why) {
    BYTE *o = nai_object(g_nai_li[q]); double x, z; int sp;
    if (!o || (sp = nai_free_spawn(&x, &z)) < 0) return;
    if (!nai_alive(o)) { if (!(o = nai_recreate(q, sp, why))) return; }
    else { nai_teleport(o, x, z, rand() % 360); ((void (__cdecl *)(BYTE *))(DWORD_PTR)n_startcar)(o); }
    g_nai_parked[q] = 0; g_nai_park_since[g_nai_li[q]] = 0;
    NMP_LOG("  nitro-ai: AI #%d '%.8s' (label %d) into the game at spawn point %d (%.1f,%.1f) - %s", q + 1, (char *)o, g_nai_li[q], sp, x, z, why);
}
static int nai_humans(void) { int k, n = 0; for (k = 0; k < 16; k++) { WORD id = *(WORD *)NMP_ROW(k); if (id && !nai_is_ai_id(id)) n++; } return n; }
static int nai_drivers(void) {   /* the host's NO. DRIVERS: its own form, or (a joiner / a migrated host) the one from the host's hello */
    int v; if (g_nmp_drivers_rx >= 1 && g_nmp_drivers_rx <= 8) return g_nmp_drivers_rx;
    if (!g_nai_shell) g_nai_shell = GetModuleHandleA("nitshell.dll");
    if (!g_nai_shell) return 0;
    v = *(int *)((BYTE *)g_nai_shell + (0x1017a070 - 0x10000000));
    if (v >= 1 && v <= 8) { g_nmp_host_drivers = v; return v; }
    return 0;
}
static int g_nai_humans = -1, g_nai_hseen = -1; static DWORD g_nai_hsince;
static void nai_fill_tick(void) {                    /* host */
    int h = nai_humans(), want, inplay = 0, q, n = nai_drivers(); DWORD now = GetTickCount();
    if (h != g_nai_hseen) { g_nai_hseen = h; g_nai_hsince = now; }
    if (now - g_nai_hsince < 1500) return;
    if (h != g_nai_humans) { NMP_LOG("  nitro-ai: humans %d -> %d (NO. DRIVERS %d)", g_nai_humans, h, n); g_nai_humans = h; }
    if (!n) n = 4;
    want = n - h; if (want < 0) want = 0; if (want > g_nai_pool_n) want = g_nai_pool_n;
    for (q = 0; q < g_nai_pool_n; q++) if (g_nai_li[q] >= 0 && !g_nai_parked[q]) inplay++;
    if (inplay > want) {                             /* a wreck first, else the live one farthest from every human */
        int pick = -1; double best = -1;
        for (q = 0; q < g_nai_pool_n; q++) { BYTE *o; if (g_nai_parked[q] || !(o = nai_object(g_nai_li[q]))) continue;
            if (!nai_alive(o)) { pick = q; break; }
            { double d = 1e30; int k; for (k = 0; k < 16; k++) { BYTE *c = nai_slot_car(k); if (c && nai_alive(c)) { double e = nai_d2(o, *(double *)(c + 0x40), *(double *)(c + 0x50)); if (e < d) d = e; } }
              if (d > best) { best = d; pick = q; } } }
        if (pick >= 0) { char why[64]; sprintf(why, "%d humans, %d of %d AI wanted", h, want, g_nai_pool_n); nai_park(pick, why); }
    } else if (inplay < want) {
        for (q = 0; q < g_nai_pool_n; q++) if (g_nai_li[q] >= 0 && g_nai_parked[q]) { char why[64]; sprintf(why, "%d humans, %d of %d AI wanted", h, want, g_nai_pool_n); nai_bring(q, why); break; }
    }
}

/* ---- host tick (ai_FrameTick) ---- */
static BYTE *g_nai_tgt[NAI_POOL]; static int g_nai_skilled[NAI_POOL]; static BYTE *g_nai_capped; static DWORD g_nai_dead_t[NAI_POOL]; static BYTE g_nai_dead_seen[NAI_POOL];
static volatile LONG g_nai_orders, g_nai_respawns, g_nai_revives, g_nai_kills, g_nai_ak_sent, g_nai_ak_got, g_nai_credited;
static void nai_host_tick(void) {
    int q, k; BYTE **root = ((BYTE **(__cdecl *)(void))(DWORD_PTR)a_root)();
    nai_fill_tick();
    if (root && *root && *root != g_nai_capped && *(BYTE **)(*root + 0x70) && *(BYTE **)(*(BYTE **)(*root + 0x70) + 0x108)) {
        int cap = 8; ((void (__cdecl *)(BYTE *, int *))(DWORD_PTR)n_cap)(*root, &cap); g_nai_capped = *root;
    }
    for (q = 0; q < g_nai_pool_n; q++) {
        BYTE *o = g_nai_li[q] >= 0 ? nai_object(g_nai_li[q]) : NULL, *best = NULL, *cur; double ax, az, bd = 1e30, cd = 1e30;
        if (!o || g_nai_parked[q]) continue;
        if (!nai_alive(o)) {
            if (!g_nai_dead_seen[q]) { g_nai_dead_seen[q] = 1; NMP_LOG("  nitro-ai: AI #%d died without an attacker record - no credit", q + 1); nai_row_add(NAI_ID0 + q, 0, 1, -500, "death, no killer"); }
            continue;
        }
        if (!g_nai_skilled[q] && *(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) {
            int s = nai_skill(), s0 = s;
            ((void (__cdecl *)(BYTE *, int *, int *))(DWORD_PTR)n_skill)(o, &s, &s);
            *(int *)(*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108) + 0xa818) = s0 - 1;
            g_nai_skilled[q] = 1;
            {   char v[8]; int hp = GetEnvironmentVariableA("NMP_LAB_AI_HP", v, sizeof v) ? atoi(v) : 0;   /* LAB: armour 0, chassis hp % */
                if (hp > 0 && hp <= 100) { BYTE *e = *(BYTE **)(o + 0x70); int sd; for (sd = 0; sd < 4; sd++) { int c = *(int *)(e + 0x168 + 4 * sd) * hp / 100; if (c < 1) c = 1;
                    *(int *)(e + 0x138 + 4 * sd) = 0; *(int *)(e + 0x178 + 4 * sd) = 0; *(int *)(e + 0x148 + 4 * sd) = c; *(int *)(e + 0x18c + 4 * sd) = c; } } }
            NMP_LOG("  nitro-ai: AI #%d skill %d (DEF byte %d)", q + 1, s0, *(volatile BYTE *)(DWORD_PTR)n_defbyte);
        }
        ax = *(double *)(o + 0x40); az = *(double *)(o + 0x50); cur = g_nai_tgt[q];
        for (k = 0; k < 16; k++) {
            BYTE *h = nai_slot_car(k); double d;
            if (!h || !nai_alive(h)) continue;
            d = nai_d2(h, ax, az); if (h == cur) cd = d; if (d < bd) { bd = d; best = h; }
        }
        if (!best) continue;
        if (cur && cd < 1e29 && bd > 0.64 * cd) best = cur;
        g_nai_tgt[q] = best;
        ((int (__cdecl *)(BYTE *, BYTE *, int))(DWORD_PTR)n_beh)(o, best, 0);
        g_nai_orders++;
    }
}
static int __cdecl nai_melee_flag(void) {            /* replaces `call 0x42fee0` at 0x4079a2 */
    int r = *(volatile int *)(DWORD_PTR)n_spmelee;
    if (!r && nai_pool_on() && nmp_role() == 1) nai_host_tick();
    return r;
}
static DWORD g_nai_frame_next = 0x004076f0;          /* ai_FrameTick, or the tick's gate when I76_SIM_TICK_MS took the site first */
static void __cdecl nai_ai_frame(DWORD a) {          /* replaces `call 0x4076f0` (ai_FrameTick, 1 cdecl arg) at 0x432e24: joiners mirror */
    if (nai_on() && nmp_role() == 2) return;
    ((void (__cdecl *)(DWORD))(DWORD_PTR)g_nai_frame_next)(a);
}

/* ---- AI weapons: record (host), replay (joiner); damage only on the host ---- */
static BYTE g_nai_fired[1024]; static BYTE g_nai_mask[NAI_MAXL]; static DWORD g_nai_until[NAI_MAXL];
static int __cdecl nai_trigger(int w, int v) { if (w >= 0 && w < 1024 && v) g_nai_fired[w] = 1; return ((int (__cdecl *)(int, int))(DWORD_PTR)n_trigger)(w, v); }
static int nai_weapon_mask(BYTE *o) {
    int w8[8], i, mask = 0; memset(w8, 0, sizeof w8);
    if (((int (__cdecl *)(BYTE *, int *))(DWORD_PTR)n_wlist)(o, w8) != 1) return 0;
    for (i = 0; i < w8[0] && i < 5; i++) if (w8[1 + i] >= 0 && w8[1 + i] < 1024 && g_nai_fired[w8[1 + i]]) mask |= 1 << i;
    if (w8[6] > 0 && w8[6] < 1024 && g_nai_fired[w8[6]]) mask |= 0x20;
    if (w8[7] > 0 && w8[7] < 1024 && g_nai_fired[w8[7]]) mask |= 0x40;
    return mask;
}
static int nai_is_mirrored(BYTE *o) {
    int q; if (!o) return 0;
    if (nai_coop_on()) { int i, c = nai_count(); for (i = 0; i < c; i++) if (nai_object(i) == o) return 1; return 0; }
    for (q = 0; q < g_nai_pool_n; q++) if (g_nai_li[q] >= 0 && nai_object(g_nai_li[q]) == o) return 1;
    return 0;
}
static int nai_sync_n(void) { return nai_coop_on() ? nai_count() : g_nai_pool_n; }   /* the cars the host owns: pool, or every mission vehicle (co-op) */
static int nai_sync_li(int k) { return nai_coop_on() ? (nai_object(k) ? k : -1) : g_nai_li[k]; }
static int __cdecl nai_class_damage(BYTE *o, int a, int rec) {   /* replaces `call 0x44fd80` x5 */
    if (nai_on() && nmp_role() == 2 && nai_is_mirrored(o)) return 0;
    return ((int (__cdecl *)(BYTE *, int, int))(DWORD_PTR)n_cdamage)(o, a, rec);
}
static void nai_joiner_fire(void) {
    int q, k, w8[8]; DWORD now = GetTickCount();
    for (q = 0; q < nai_sync_n(); q++) {
        int li = nai_sync_li(q), m; BYTE *o;
        if (li < 0 || li >= NAI_MAXL || !(m = g_nai_mask[li]) || (LONG)(now - g_nai_until[li]) > 0 || !(o = nai_object(li))) continue;
        memset(w8, 0, sizeof w8);
        if (((int (__cdecl *)(BYTE *, int *))(DWORD_PTR)n_wlist)(o, w8) != 1) continue;
        for (k = 0; k < w8[0] && k < 5; k++) if (m & (1 << k)) ((int (__cdecl *)(int, int))(DWORD_PTR)n_trigger)(w8[1 + k], 1);
        if ((m & 0x20) && w8[6]) ((int (__cdecl *)(int, int))(DWORD_PTR)n_trigger)(w8[6], 1);
        if ((m & 0x40) && w8[7]) ((int (__cdecl *)(int, int))(DWORD_PTR)n_trigger)(w8[7], 1);
    }
}

/* ---- 'AT' (host send, joiner apply) ---- */
static float g_nai_seen_t[NAI_MAXL]; static volatile LONG g_nai_at_sent, g_nai_at_applied;
static void nai_at_send(void) {
    static DWORD last; static unsigned rounds; BYTE pkt[8 + 2 * 100]; int n = 0, q; DWORD now = GetTickCount();
    if (now - last < 100) return;
    last = now; rounds++;
    int sn = nai_sync_n(), coop = nai_coop_on();
    for (q = 0; q <= sn; q++) {
        int li = q < sn ? nai_sync_li(q) : -1; BYTE *o = li >= 0 && li < NAI_MAXL ? nai_object(li) : NULL;
        if (o && !coop && g_nai_parked[q] && now - g_nai_park_since[li] > 1500 && rounds % 20) o = NULL;
        if (o) {
            BYTE *r = pkt + 8 + n * 100;
            *(WORD *)r = (WORD)li; r[2] = (BYTE)nai_weapon_mask(o); r[3] = (BYTE)(0x80 | nai_team(o) | (!coop && g_nai_parked[q] ? 0x40 : 0));
            ((void (__cdecl *)(BYTE *, float *))(DWORD_PTR)a_pack)(o, (float *)(r + 4));
            n++;
        }
        if (n && (n == 2 || q == sn)) {
            *(WORD *)pkt = NMP_TAG_AT; pkt[2] = 0; pkt[3] = (BYTE)n; *(float *)(pkt + 4) = *(float *)(pkt + 12);
            if (nmp_send(nmp_group(), pkt, 8 + n * 100, 0) == 0) g_nai_at_sent += n;
            n = 0;
        }
    }
    memset(g_nai_fired, 0, sizeof g_nai_fired);
}
static void nai_at_apply(const BYTE *pkt, int size) {
    int n = pkt[3], j;
    if (size < 8 + n * 100 || n > 2) return;
    for (j = 0; j < n; j++) {
        const BYTE *r = pkt + 8 + j * 100; int li = *(WORD *)r, q = nai_pool_index(li); float t = *(float *)(r + 4); BYTE *o;
        if ((q < 0 && !nai_coop_on()) || li >= NAI_MAXL || !(o = nai_object(li))) continue;
        if (q < 0) {   /* co-op: a mission vehicle - mirror it, no pool state */
            if (t <= g_nai_seen_t[li] && t > g_nai_seen_t[li] - 2.0f) continue;
            g_nai_seen_t[li] = t; g_nai_mask[li] = r[2]; g_nai_until[li] = GetTickCount() + 150;
            ((void (__cdecl *)(BYTE *, const float *))(DWORD_PTR)n_mirror)(o, (const float *)(r + 4));
            g_nai_at_applied++; continue;
        }
        if (t <= g_nai_seen_t[li] && t > g_nai_seen_t[li] - 2.0f) continue;
        g_nai_seen_t[li] = t;
        g_nai_parked[q] = (r[3] & 0x40) != 0;        /* the joiner's view of the fill: rows follow it */
        if (!nai_alive(o) && !(*(DWORD *)(r + 4 + 0x48) & 8) && !g_nai_parked[q]) {   /* the host respawned it: rebuild ours */
            int s, ns = *(int *)(DWORD_PTR)n_spcount, sp = 0; double best = 1e30;
            for (s = 0; s < ns && s < 64; s++) { double d = nai_d2(o, *(double *)(DWORD_PTR)(n_sptab + 0x28 + s * 0x40), *(double *)(DWORD_PTR)(n_sptab + 0x38 + s * 0x40)); if (d < best) { best = d; sp = s; } }
            if ((o = nai_recreate(q, sp, "joiner, the host's 'AT' says alive"))) g_nai_revives++; else continue;
        }
        g_nai_mask[li] = r[2]; g_nai_until[li] = GetTickCount() + 150;
        ((void (__cdecl *)(BYTE *, const float *))(DWORD_PTR)n_mirror)(o, (const float *)(r + 4));
        g_nai_at_applied++;
    }
}

/* ---- respawn ---- */
static BYTE *nai_recreate(int q, int sp, const char *why) {
    BYTE *tab = nai_tab(), *old, *nw; int li = g_nai_li[q]; DWORD lo, hi; int *ent, team;
    if (!tab || li < 0 || !(old = nai_object(li))) return NULL;
    if (sp < 0 || sp >= *(int *)(DWORD_PTR)n_spcount) sp = 0;
    lo = *(DWORD *)(tab + li * 16); hi = *(DWORD *)(tab + li * 16 + 4); team = nai_team(old);
    nw = ((BYTE *(__cdecl *)(int, int, DWORD, DWORD, int))(DWORD_PTR)n_spawner)(sp, 0, lo, hi, 0);
    if (!nw || !*(BYTE **)(nw + 0x70)) { NMP_LOG("  nitro-ai: respawn of AI #%d FAILED (the spawner returned no car)", q + 1); return NULL; }
    *(BYTE **)(tab + li * 16 + 8) = nw;
    ent = ((int *(__cdecl *)(BYTE *))(DWORD_PTR)n_findrec)(old);
    if (ent) ((void (__cdecl *)(int *))(DWORD_PTR)n_remove)(ent);
    if (nai_team(nw) != team) {                      /* team lists [0x506960 + t*0x100], counts [0x51e190 + t*4] */
        DWORD cur = (DWORD)nai_team(nw); int *c0 = (int *)(DWORD_PTR)(n_teamcnt + cur * 4), *c1 = (int *)(DWORD_PTR)(n_teamcnt + team * 4), i;
        BYTE ***l0 = (BYTE ***)(DWORD_PTR)(n_teamlist + cur * 0x100), ***l1 = (BYTE ***)(DWORD_PTR)(n_teamlist + team * 0x100);
        for (i = 0; i < *c0 && i < 64; i++) if (l0[i] && *l0[i] == nw) break;
        if (i < *c0 && i < 64 && *c1 < 64) { l1[(*c1)++] = l0[i]; l0[i] = l0[*c0 - 1]; (*c0)--; *(DWORD *)(nw + 0x10) = (*(DWORD *)(nw + 0x10) & ~0x70000u) | ((DWORD)team << 16); }
    }
    *(WORD *)(*(BYTE **)(nw + 0x70) + 0x484) = (WORD)(NAI_ID0 + q);
    g_nai_tgt[q] = NULL; g_nai_skilled[q] = 0; g_nai_dead_seen[q] = 0; g_nai_dead_t[q] = 0;
    NMP_LOG("  nitro-ai: t %lu AI #%d '%.8s' (label %d) respawned at %.1f,%.1f (spawn point %d), team %d - %s", GetTickCount(), q + 1, (char *)nw, li,
            *(double *)(nw + 0x40), *(double *)(nw + 0x50), sp, nai_team(nw), why);
    return nw;
}
static void nai_respawn_tick(void) {                 /* host: one per call */
    int q; DWORD now = GetTickCount();
    for (q = 0; q < g_nai_pool_n; q++) {
        BYTE *o = g_nai_li[q] >= 0 ? nai_object(g_nai_li[q]) : NULL; double x, z; int sp; char why[48];
        if (!o || g_nai_parked[q] || nai_alive(o)) { g_nai_dead_t[q] = 0; continue; }
        if (!g_nai_dead_t[q]) { g_nai_dead_t[q] = now | 1; continue; }
        if ((LONG)(now - g_nai_dead_t[q]) < 5000 || (sp = nai_free_spawn(&x, &z)) < 0) continue;
        sprintf(why, "host, dead %.1f s", (LONG)(now - g_nai_dead_t[q]) / 1000.0);
        if (nai_recreate(q, sp, why)) g_nai_respawns++; else g_nai_dead_t[q] = now | 1;
        return;
    }
}

/* ---- kills ---- */
static struct { WORD killer; short li; int score; BYTE own; } g_nai_q[16]; static volatile LONG g_nai_qn;
static void __cdecl nai_on_kill(BYTE *victim, BYTE *rec) {
    int q, k; WORD killer; BYTE *kc = NULL;
    if (!rec || !victim || !nai_on() || nmp_role() != 1) return;
    for (q = 0; q < g_nai_pool_n; q++) if (g_nai_li[q] >= 0 && nai_object(g_nai_li[q]) == victim) break;
    if (q == g_nai_pool_n) return;
    g_nai_dead_seen[q] = 1; g_nai_kills++;
    killer = (WORD)((unsigned (__cdecl *)(BYTE *))(DWORD_PTR)n_objid)(*(BYTE **)rec);
    if (nai_is_ai_id(killer)) { int kq = killer - NAI_ID0; if (kq >= 0 && kq < g_nai_pool_n) kc = nai_object(g_nai_li[kq]); }
    else for (k = 0; k < 16; k++) if (*(WORD *)NMP_ROW(k) == killer) kc = *(BYTE **)(NMP_ROW(k) + 0x28);
    if (!killer || !kc || !*(BYTE **)(kc + 0x70)) {
        NMP_LOG("  nitro-ai: AI #%d destroyed, no player credited (attacker id %u)", q + 1, killer);
        nai_row_add(NAI_ID0 + q, 0, 1, -500, "death, no killer credited");
        return;
    }
    if (g_nai_qn < 16) {
        float v = *(float *)(*(BYTE **)(victim + 0x70) + 0xa4) * *(float *)(*(BYTE **)(kc + 0x70) + 0xa8) * *(float *)(DWORD_PTR)n_killk;
        int own = nai_is_ai_id(killer) && nai_team(kc) == nai_team(victim);
        g_nai_q[g_nai_qn].killer = killer; g_nai_q[g_nai_qn].li = (short)g_nai_li[q]; g_nai_q[g_nai_qn].score = own ? 0 : (int)v; g_nai_q[g_nai_qn].own = (BYTE)own; g_nai_qn++;
        if (!own) { nai_row_add(NAI_ID0 + q, 0, 1, 0, "killed"); if (nai_is_ai_id(killer)) nai_row_add(killer, 1, 0, (int)v, "killed an AI"); }
    }
}
static __declspec(naked) void nai_kill_stub(void) {  /* replaces `call 0x42fee0` at 0x46332e */
    __asm {
        push ebp
        push edi
        call nai_on_kill
        add esp, 8
        mov eax, 0x0042fee0
        jmp eax
    }
}
static void nai_credit(WORD killer, short li, int score, int own) {
    char ai[24], who[32] = "?", msg[96]; int q = nai_pool_index(li); BYTE *p;
    if (!((int (__cdecl *)(short, char *))(DWORD_PTR)n_name)((short)killer, who) && nai_is_ai_id(killer)) nai_name(killer - NAI_ID0, who);
    who[24] = 0;
    sprintf(msg, "%s was destroyed by %s", nai_name(q, ai), who);
    ((void (__cdecl *)(short, const char *))(DWORD_PTR)n_chat)(0, msg);
    if (own) { NMP_LOG("  nitro-ai: %s - own team: no score", msg); return; }
    if (killer == nmp_me() && (p = nai_row(killer))) {
        ((void (__cdecl *)(int, int, int, int))(DWORD_PTR)n_setscore)(killer, *(int *)(p + 0x40) + score, *(short *)(p + 0x3c) + 1, *(short *)(p + 0x3e));
        g_nai_credited++;
        NMP_LOG("  nitro-ai: credited here - %s, +1 kill, +%d (now %d kills, %d)", msg, score, *(short *)(p + 0x3c), *(int *)(p + 0x40));
    } else NMP_LOG("  nitro-ai: %s (+%d to player %u)", msg, score, killer);
}
static void nai_flush(void) {                        /* host: 'AK' reliable, one copy */
    static BYTE seq; LONG i, n = g_nai_qn;
    for (i = 0; i < n; i++) {
        BYTE pkt[12];
        if (++seq == 0) seq = 1;
        *(WORD *)pkt = NMP_TAG_AK; pkt[2] = seq; pkt[3] = g_nai_q[i].own; *(WORD *)(pkt + 4) = g_nai_q[i].killer; *(short *)(pkt + 6) = g_nai_q[i].li;
        *(int *)(pkt + 8) = g_nai_q[i].score;
        if (nmp_send(nmp_group(), pkt, 12, 1) == 0) g_nai_ak_sent++;
        nai_credit(g_nai_q[i].killer, g_nai_q[i].li, g_nai_q[i].score, g_nai_q[i].own);
    }
    g_nai_qn = 0;
}
static void nai_human_killed(BYTE *victim, unsigned killer, const char *how) {   /* host: a human wrecked by an AI */
    int kq = (int)killer - NAI_ID0; BYTE *kc;
    if (!nai_is_ai_id(killer) || kq >= g_nai_pool_n || !(kc = nai_object(g_nai_li[kq]))) return;
    nai_row_add(killer, 1, 0, (int)(*(float *)(*(BYTE **)(victim + 0x70) + 0xa4) * *(float *)(*(BYTE **)(kc + 0x70) + 0xa8) * *(float *)(DWORD_PTR)n_killk), how);
}
static void __cdecl nai_st_mirror(BYTE *o, BYTE *rec) {   /* replaces `call 0x463a20` at 0x445db8 ('ST' of a remote player) */
    if (nai_on() && nmp_role() == 1 && o && rec && *(BYTE **)(o + 0x70) && (*(DWORD *)(rec + 0x48) & 8) && nai_alive(o)) nai_human_killed(o, *(WORD *)(rec + 0x58), "killed a remote human");
    ((void (__cdecl *)(BYTE *, BYTE *))(DWORD_PTR)n_mirror)(o, rec);
}
static void __cdecl nai_score_set(int id, int score, int kills, int deaths) {   /* replaces `call 0x447050` at 0x464409 */
    if ((WORD)id == 0) return;
    ((void (__cdecl *)(int, int, int, int))(DWORD_PTR)n_setscore)(id, score, kills, deaths);
}

/* ---- LAB ONLY (never in a pack): NMP_LAB_SHOOT=<s> puts the local car 14 m behind the nearest live AI every s seconds and
 * fires for 1.5 s; NMP_LAB_OWN_HP=<n> cuts the local car to n % at each spawn (so the AI kill it). ---- */
static volatile LONG g_nai_lab_fire; static SHORT (WINAPI *p_nai_gaks)(int); static SHORT (WINAPI *p_nai_gks)(int);
static int nai_fire_vk(int vk) { return vk == VK_SPACE || (vk >= '1' && vk <= '5') || vk == VK_LBUTTON; }
static volatile LONG g_nai_lab_keyhits;
static SHORT WINAPI nai_lab_gaks(int vk) { if (g_nai_lab_fire && nai_fire_vk(vk)) { g_nai_lab_keyhits++; return (SHORT)0x8001; } return p_nai_gaks ? p_nai_gaks(vk) : 0; }
static SHORT WINAPI nai_lab_gks(int vk) { if (g_nai_lab_fire && nai_fire_vk(vk)) { g_nai_lab_keyhits++; return (SHORT)0x8000; } return p_nai_gks ? p_nai_gks(vk) : 0; }
static DWORD WINAPI nai_lab_fire_thread(LPVOID p) {   /* LAB: the weapon_fire held byte 0x53490b (read at 0x4b14d5) while a window is open */
    (void)p; for (;;) { if (g_nai_lab_fire) *(volatile BYTE *)0x0053490b = 1; Sleep(1); }
}
static void nai_lab_tick(void) {
    static BYTE *cut, *tgt; static DWORD next, fire_until, follow; char v[8]; int shoot, own;
    BYTE **root = ((BYTE **(__cdecl *)(void))(DWORD_PTR)a_root)(), *me = root ? *root : NULL; DWORD now = GetTickCount();
    shoot = GetEnvironmentVariableA("NMP_LAB_SHOOT", v, sizeof v) ? atoi(v) : 0;
    own = GetEnvironmentVariableA("NMP_LAB_OWN_HP", v, sizeof v) ? atoi(v) : 0;
    if (!me || !*(BYTE **)(me + 0x70) || !nai_alive(me)) return;
    if (own > 0 && me != cut) { BYTE *e = *(BYTE **)(me + 0x70); int sd; cut = me;
        for (sd = 0; sd < 4; sd++) { int c = *(int *)(e + 0x168 + 4 * sd) * own / 100; if (c < 1) c = 1; *(int *)(e + 0x138 + 4 * sd) = 0; *(int *)(e + 0x178 + 4 * sd) = 0; *(int *)(e + 0x148 + 4 * sd) = c; *(int *)(e + 0x18c + 4 * sd) = c; }
        NMP_LOG("  nitro-ai: LAB own car cut to %d %%", own); }
    if (shoot <= 0) return;
    if (!next) next = now;   /* a machine up more than 24.8 days (Andrew's Mac: 2397485012 ms) has (LONG)(now - 0) < 0: never fired */
    if ((LONG)(now - next) >= 0) {
        int q; BYTE *best = NULL; double bd = 1e30;
        next = now + shoot * 1000;
        for (q = 0; q < g_nai_pool_n; q++) { BYTE *o = g_nai_li[q] >= 0 ? nai_object(g_nai_li[q]) : NULL; double d; if (!o || g_nai_parked[q] || !nai_alive(o)) continue;
            d = nai_d2(o, *(double *)(me + 0x40), *(double *)(me + 0x50)); if (d < bd) { bd = d; best = o; } }
        if (tgt) {   /* the last window: fire keys read, weapons, the target's health */
            int w8[8]; memset(w8, 0, sizeof w8); ((int (__cdecl *)(BYTE *, int *))(DWORD_PTR)n_wlist)(me, w8);
            NMP_LOG("  nitro-ai: LAB window done - fire keys read %ld times, own weapons %d (%d %d %d), target %s %.0f%%", g_nai_lab_keyhits, w8[0], w8[1], w8[2], w8[3],
                    nai_alive(tgt) ? "live" : "dead", nai_alive(tgt) ? ((double (__cdecl *)(BYTE *))(DWORD_PTR)n_health)(tgt) : 0.0);
            g_nai_lab_keyhits = 0;
        }
        if (best) { tgt = best; fire_until = now + 3000; follow = 0;
            NMP_LOG("  nitro-ai: LAB shoot - behind '%.8s' at %.1f,%.1f", (char *)best, *(double *)(best + 0x40), *(double *)(best + 0x50)); }
    }
    if ((LONG)(fire_until - now) > 0 && tgt && nai_alive(tgt) && now - follow > 200) {   /* stay 10 m behind the target, its heading, while firing */
        float fx = *(float *)(tgt + 0x18 + 24), fz = *(float *)(tgt + 0x18 + 32); int hd = (int)(atan2(fx, fz) * 57.29578); double r = hd / 57.29578;
        follow = now;
        nai_teleport(me, *(double *)(tgt + 0x40) - sin(r) * 10.0, *(double *)(tgt + 0x50) - cos(r) * 10.0, hd);
    }
    g_nai_lab_fire = (LONG)(fire_until - now) > 0;   /* the fire keys (Space, 1-5) read as held: nitro.exe's GetAsyncKeyState / GetKeyState */
    {   /* LAB: the weapon_fire reader `mov al, [0x53490b]` at 0x4b14d5 reads `mov al, 1` during a window (patched here, on the
         * game thread, and put back after). Was a thread holding the byte at 1 every 1 ms: the game's input pass rewrites the
         * byte each frame, and under Wine (the Macs) Sleep(1) is too coarse to win that race - the Mac joiner never fired. */
        static int state = -1; static const BYTE sig[5] = { 0xa0, 0x0b, 0x49, 0x53, 0x00 }, one[5] = { 0xb0, 0x01, 0x90, 0x90, 0x90 };
        int want = g_nai_lab_fire != 0; DWORD op;
        if (state < 0) { state = memcmp((void *)0x004b14d5, sig, 5) == 0 ? 0 : 2;
            NMP_LOG("  nitro-ai: LAB weapon_fire reader at 0x4b14d5 %s", state == 0 ? "reads 1 during windows (patched in place, checked)" : "differs - fire not forced"); }
        if (state != 2 && want != state && VirtualProtect((void *)0x004b14d5, 5, PAGE_EXECUTE_READWRITE, &op)) {
            memcpy((void *)0x004b14d5, want ? one : sig, 5); VirtualProtect((void *)0x004b14d5, 5, op, &op);
            FlushInstructionCache(GetCurrentProcess(), (void *)0x004b14d5, 5); state = want;
        } }
    if (!p_nai_gaks) { static int tried; if (!tried++) { p_nai_gaks = (SHORT (WINAPI *)(int))NMP_IAT(GetModuleHandleA(NULL), "USER32.dll", "GetAsyncKeyState", (void *)nai_lab_gaks);
        p_nai_gks = (SHORT (WINAPI *)(int))NMP_IAT(GetModuleHandleA(NULL), "USER32.dll", "GetKeyState", (void *)nai_lab_gks);
        NMP_LOG("  nitro-ai: LAB fire keys through nitro.exe's GetAsyncKeyState %s / GetKeyState %s", p_nai_gaks ? "hooked" : "NOT hooked", p_nai_gks ? "hooked" : "NOT hooked"); } }
    if ((LONG)(fire_until - now) > 0) {
        int w8[8], k; memset(w8, 0, sizeof w8);
        if (((int (__cdecl *)(BYTE *, int *))(DWORD_PTR)n_wlist)(me, w8) == 1) for (k = 0; k < w8[0] && k < 5; k++) if (w8[1 + k] >= 0) ((int (__cdecl *)(int, int))(DWORD_PTR)n_trigger)(w8[1 + k], 1);
    }
}


/* ---- CO-OP SCENES (item 5; owner: Nitro's own P01-P19 only, no Gold missions) [Gold: coop_ai_* + coop_spawn] ----
 * An ARENA+ session whose mission is pNN.msn (listed only while the CO-OP SCENES box is on; lab: arena_poc's
 * NMP_LAB_COOP_LIST). Every machine loads the mission; the HOST runs the script and the AI (ai_FrameTick is skipped on
 * joiners), every mission vehicle goes to the joiners in 'AT' (2 per packet) and is mirrored there, damage to them is
 * computed on the host only, their trigger pulls are replayed. The host's car is the mission's own player object
 * (objFlags 0x10), adopted at the network spawn (7 calls of the player spawner 0x44c6f0 [0x451180]) and linked to the
 * host's id with 0x446a90 [0x454750] - the script watches that object. Joiners need spawn points: a campaign mission has
 * none, so 4 team-0 spawn records are written beside the player object at load (the spawner 0x44c930 / 'SP' read
 * them). Not ported: CB radio ('AC'), objectives ('AO'), the scene chain ('AM'), per-joiner scaling. */
static BYTE *nai_mission_player(void) {
    BYTE *tab = nai_tab(); int i, k, c = nai_count();
    for (i = 0; tab && i < c; i++) {
        BYTE *o = *(BYTE **)(tab + i * 16 + 8);
        if (!o || *(int *)(o + 0x6c) != 1 || !(o[0x10] & 0x10) || !*(BYTE **)(o + 0x70) || ((*(BYTE **)(o + 0x70))[0x458] & 0x20)) continue;
        for (k = 0; k < 16; k++) { BYTE *p = NMP_ROW(k); if (*(WORD *)p && *(BYTE **)(p + 0x28) == o) break; }
        if (k == 16) return o;
    }
    return NULL;
}
static volatile LONG g_nai_adopted;
static void nai_coop_load(const char *m) {
    BYTE *pl = nai_mission_player(); int *cnt = (int *)(DWORD_PTR)n_spcount, k, made = 0;
    g_nai_coop = 1; strncpy(g_nai_coop_m, m, 15); g_nai_coop_m[15] = 0;
    if (pl && *cnt == 0) {
        for (k = 0; k < 4; k++) {
            BYTE *rec = (BYTE *)(DWORD_PTR)(n_sptab + k * 0x40);
            memcpy(rec, pl + 0x18, 0x40);
            *(double *)(rec + 0x28) += 25.0 * (k + 1);
            made++;
        }
        *cnt = made;
    }
    NMP_LOG("  nitro-ai: '%s' - CO-OP SCENE (ARENA+): mission player object %p (%.8s) at %.1f,%.1f; team-0 spawn points %d (%d written beside it); %d label(s)",
            m, (void *)pl, pl ? (char *)pl : "-", pl ? *(double *)(pl + 0x40) : 0.0, pl ? *(double *)(pl + 0x50) : 0.0, *cnt, made, nai_count());
}
static char *__cdecl nai_coop_spawn(short id, int idx, int type, void *data, size_t size) {   /* replaces `call 0x44c6f0` x7 */
    WORD host = nmp_hostid(), me = nmp_me();
    if (nai_coop_on() && host && (WORD)id == host) {
        BYTE *o = nai_mission_player();
        if (o) {
            unsigned __int64 nm = ((unsigned __int64 (__cdecl *)(short))(DWORD_PTR)0x00446b40)(id);
            if (!nm && data && size) nm = ((unsigned __int64 (__cdecl *)(void *, size_t))(DWORD_PTR)0x004484e0)(data, size);
            if ((WORD)id != me) *(DWORD *)(o + 0x10) = (*(DWORD *)(o + 0x10) & ~0x10u) | 0x20;   /* the host's remote car here */
            ((int (__cdecl *)(short, DWORD, DWORD, BYTE *))(DWORD_PTR)0x00446a90)(id, (DWORD)nm, (DWORD)(nm >> 32), o);
            g_nai_adopted++;
            NMP_LOG("  nitro-ai: co-op - host (id %u) %s the mission's player object %p ('%.8s')", id, (WORD)id == me ? "drives" : "is shown as", (void *)o, (char *)o);
            return (char *)o;
        }
    }
    return ((char *(__cdecl *)(short, int, int, void *, size_t))(DWORD_PTR)0x0044c6f0)(id, idx, type, data, size);
}
static void nai_coop_status(int role) {
    char line[1600]; int len, i, c = nai_count(), shown = 0, alive = 0, dead = 0; BYTE **root = ((BYTE **(__cdecl *)(void))(DWORD_PTR)a_root)();
    len = sprintf(line, "  nitro-ai: t %lu %s %.12s CO-OP adopted %ld AT sent %ld applied %ld; own car %s; mission cars", GetTickCount(), role == 1 ? "host" : "joiner",
                  (char *)(DWORD_PTR)n_mission, g_nai_adopted, g_nai_at_sent, g_nai_at_applied, root && *root ? ((*root)[0x10] & 0x10 ? "= mission player" : "network car") : "-");
    for (i = 0; i < c; i++) {
        BYTE *o = nai_object(i); if (!o) continue;
        if (nai_alive(o)) alive++; else dead++;
        if (shown < 8 && len < 1400) { len += sprintf(line + len, " [L%d %.8s %s %.1f,%.1f]", i, (char *)o, nai_alive(o) ? "live" : "dead", *(double *)(o + 0x40), *(double *)(o + 0x50)); shown++; }
    }
    len += sprintf(line + len, " = %d live %d dead; humans", alive, dead);
    for (i = 0; i < 16; i++) { BYTE *p = NMP_ROW(i), *o = *(WORD *)p ? *(BYTE **)(p + 0x28) : NULL; if (*(WORD *)p) len += sprintf(line + len, " %u%s", *(WORD *)p, o ? "" : "(no car)");
        if (o && len < 1550) len += sprintf(line + len, "@%.1f,%.1f", *(double *)(o + 0x40), *(double *)(o + 0x50)); }
    NMP_LOG("%s", line);
}

/* nitshell's mission-file check 0x1002fda0 (host create 0x1002fadc, join reply 0x10030106) knows only the arena
 * extensions (.cbt .rac .cf2-4 .lvl) and answers "Mission file %s not found" for anything else. In a co-op scene
 * (ARENA+ species, pNN.msn) it is answered here instead: CRC-32 of the loose file miss16\ (else miss8\) on both sides,
 * so host and joiner compare the same way the shell does for arenas. Any other mission: the stock check. */
static BYTE *g_nai_sh;
static int nai_call(DWORD site, DWORD target, void *fn, const char *what);
static DWORD nai_crc32_file(const char *path) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL); BYTE buf[4096]; DWORD n, c = 0xffffffffu, k; int b;
    if (h == INVALID_HANDLE_VALUE) return 0;
    while (ReadFile(h, buf, sizeof buf, &n, NULL) && n) for (k = 0; k < n; k++) { c ^= buf[k]; for (b = 0; b < 8; b++) c = (c >> 1) ^ (0xedb88320u & (0u - (c & 1u))); }
    CloseHandle(h);
    return ~c;
}
static DWORD __cdecl nai_mission_check(char *name) {   /* replaces `call 0x1002fda0` at the two shell sites */
    if (name && nai_coop_name(name) && g_nmp_species == NMP_SPECIES_ARENA) {
        char p[64]; DWORD c; _snprintf(p, sizeof p - 1, "miss16\\%s", name); p[sizeof p - 1] = 0;
        if (!(c = nai_crc32_file(p))) { _snprintf(p, sizeof p - 1, "miss8\\%s", name); c = nai_crc32_file(p); }
        NMP_LOG("  nitro-ai: co-op mission check '%s' -> crc %08lx (%s)", name, c, c ? p : "NOT FOUND");
        if (c) return c;
    }
    return ((DWORD (__cdecl *)(char *))(g_nai_sh + 0x2fda0))(name);
}
static void nai_attach_shell(HMODULE sh) {
    int n = 0; g_nai_sh = (BYTE *)sh;
    n += nai_call((DWORD)(g_nai_sh + 0x2fadc), (DWORD)(g_nai_sh + 0x2fda0), (void *)nai_mission_check, "co-op mission check (host)");
    n += nai_call((DWORD)(g_nai_sh + 0x30106), (DWORD)(g_nai_sh + 0x2fda0), (void *)nai_mission_check, "co-op mission check (join)");
    NMP_LOG("  nitro-ai: nitshell co-op mission check %d/2 sites", n);
}
/* ---- host migration (nitro_mp.c calls this once when this joiner became the host) [mpfill mpf_migr_pending] ----
 * The joiner already holds everything a host needs: the pool's parked / in-play state from the old host's 'AT' byte 3,
 * the AI rows with their numbers (g_nai_led follows the rows on a joiner), the AI cars at the old host's last positions.
 * So the reconcile is: keep the parked / in-play split as the 'AT' said, recount the humans (the fill then brings a
 * car back for the human who left), skill the AI cars again (their brains now run here), forget old targets and death
 * timers (dead cars restart their 5 s). */
static void nai_migrated(void) {
    int q, play = 0, park = 0, dead = 0;
    if (!nai_on()) return;
    for (q = 0; q < g_nai_pool_n; q++) {
        BYTE *o = g_nai_li[q] >= 0 ? nai_object(g_nai_li[q]) : NULL;
        g_nai_skilled[q] = 0; g_nai_tgt[q] = NULL; g_nai_dead_t[q] = 0;
        if (!o) continue;
        if (g_nai_parked[q]) { park++; g_nai_park_since[g_nai_li[q]] = GetTickCount(); } else play++;
        if (!nai_alive(o)) { dead++; g_nai_dead_seen[q] = 1; }
    }
    g_nai_humans = -1; g_nai_hseen = -1; g_nai_capped = NULL;
    NMP_LOG("  nitro-ai: host migration - reconciled from the old host's last 'AT': %d in play (%d dead), %d parked; rows %d; NO. DRIVERS %d (from the hello)",
            play, dead, park, *(volatile int *)(DWORD_PTR)a_count, nai_drivers());
}

/* ---- pump hooks (nitro_mp.c) ---- */
static WORD g_nai_seq_seen[32]; static unsigned g_nai_seq_n;
static void nai_rx(WORD from, const BYTE *p, int n) {
    (void)from;
    if (!nai_on()) return;
    if (*(WORD *)p == NMP_TAG_AT && nmp_role() == 2) nai_at_apply(p, n);
    else if (*(WORD *)p == NMP_TAG_AK && nmp_role() == 2 && n >= 12) {
        WORD tag = (WORD)(p[2] | (*(WORD *)(p + 6) << 8)); int i;
        for (i = 0; i < 32; i++) if (g_nai_seq_seen[i] == tag) return;
        g_nai_seq_seen[g_nai_seq_n++ % 32] = tag; g_nai_ak_got++;
        nai_credit(*(WORD *)(p + 4), *(short *)(p + 6), *(int *)(p + 8), p[3] == 1);
    }
}
static void nai_status(int role) {
    char line[2000]; int len, q, k;
    len = sprintf(line, "  nitro-ai: t %lu %s %.12s humans %d drivers %d orders %ld kills %ld AK sent %ld got %ld credited %ld respawns %ld revives %ld AT sent %ld applied %ld; AI",
                  GetTickCount(), role == 1 ? "host" : "joiner", (char *)(DWORD_PTR)n_mission, nai_humans(), nai_drivers(), g_nai_orders, g_nai_kills,
                  g_nai_ak_sent, g_nai_ak_got, g_nai_credited, g_nai_respawns, g_nai_revives, g_nai_at_sent, g_nai_at_applied);
    for (q = 0; q < g_nai_pool_n; q++) {
        int li = g_nai_li[q]; BYTE *o = li >= 0 ? nai_object(li) : NULL;
        if (!o) { len += sprintf(line + len, " [%d -]", q + 1); continue; }
        len += sprintf(line + len, " [%d L%d %s %s %.0f%% %.1f,%.1f]", q + 1, li, g_nai_parked[q] ? "parked" : "play", nai_alive(o) ? "live" : "dead",
                       nai_alive(o) ? ((double (__cdecl *)(BYTE *))(DWORD_PTR)n_health)(o) : 0.0, *(double *)(o + 0x40), *(double *)(o + 0x50));
    }
    len += sprintf(line + len, "; rows %d", *(volatile int *)(DWORD_PTR)a_count);
    for (k = 0; k < 16 && len < 1800; k++) { BYTE *p = NMP_ROW(k); if (*(WORD *)p) len += sprintf(line + len, " %u@%d:t%d %d/%d/%d", *(WORD *)p, k, (int)((*(DWORD *)(p + 0x1c) >> 16) & 7), *(short *)(p + 0x3c), *(short *)(p + 0x3e), *(int *)(p + 0x40)); }
    NMP_LOG("%s", line);
}
static void nai_tick(int role) {
    static DWORD stat, since; static int left; DWORD now = GetTickCount();
    if (!nai_on() || *(volatile int *)(DWORD_PTR)a_state != 5) return;
    {   char v[8]; int leave = GetEnvironmentVariableA("NMP_LAB_LEAVE_AT", v, sizeof v) ? atoi(v) : 0;   /* LAB: the stock end-of-session exit */
        if (!since) since = now;
        if (leave > 0 && !left && role == 1 && now - since > (DWORD)leave * 1000) { left = 1; NMP_LOG("  nitro-ai: LAB host leaves (game state 3) after %d s", leave); *(volatile int *)(DWORD_PTR)a_state = 3; return; } }
    if (role == 1) { nai_at_send(); if (g_nai_qn) nai_flush(); if (nai_pool_on()) nai_respawn_tick(); }
    else if (role == 2) nai_joiner_fire();
    if (nai_pool_on()) nai_rows_tick(role);
    nai_lab_tick();
    {   static DWORD last; BYTE **root; BYTE *o;   /* dead human: ask for the respawn (0x44caf0(1) waits out the 5 s itself) */
        if (now - last > 1000) { last = now; root = ((BYTE **(__cdecl *)(void))(DWORD_PTR)a_root)(); o = root ? *root : NULL;
            if (o && *(BYTE **)(o + 0x70) && ((*(BYTE **)(o + 0x70))[0x458] & 0x20) && !*(volatile int *)(DWORD_PTR)n_respawn_flag) {
                if (role == 1) { static BYTE *done; if (o != done) { done = o; nai_human_killed(o, *(WORD *)(*(BYTE **)(o + 0x70) + 0x486), "killed the host"); } }
                ((int (__cdecl *)(int))(DWORD_PTR)n_respawn)(1);
                if (*(volatile int *)(DWORD_PTR)n_respawn_flag) NMP_LOG("  nitro-ai: %s dead - respawn requested", role == 1 ? "host" : "joiner"); } } }
    if (now / 5000 != stat) { stat = now / 5000; if (nai_coop_on()) nai_coop_status(role); else nai_status(role); }
}

/* ---- attach ---- */
static int nai_call(DWORD site, DWORD target, void *fn, const char *what) {   /* `call target` at site -> `call fn` */
    BYTE *p = (BYTE *)(DWORD_PTR)site; LONG rel; DWORD op;
    if (p[0] != 0xE8 || (DWORD)(site + 5 + *(LONG *)(p + 1)) != target) { NMP_LOG("  nitro-ai: site %s at 0x%06lx is not `call 0x%06lx` - OFF", what, site, target); return 0; }
    rel = (LONG)((DWORD_PTR)fn - (site + 5));
    VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &op); *(LONG *)(p + 1) = rel; VirtualProtect(p, 5, op, &op);
    FlushInstructionCache(GetCurrentProcess(), p, 5);
    return *(LONG *)(p + 1) == rel;
}
static int nai_call_chain(DWORD site, DWORD stock, void *fn, DWORD *next, const char *what) {   /* as nai_call, but a site another
    * feature already took (simtick.c's st_call_site: the I76_SIM_TICK_MS gate of ai_FrameTick) is chained: we run first and call
    * what was there (the gate runs ai_FrameTick on tick frames). If the tick patches after us it chains to us the same way. */
    BYTE *p = (BYTE *)(DWORD_PTR)site; DWORD tgt;
    if (p[0] != 0xE8) { NMP_LOG("  nitro-ai: site %s at 0x%06lx is not a call - OFF", what, site); return 0; }
    tgt = (DWORD)(site + 5 + *(LONG *)(p + 1));
    if (tgt != stock) NMP_LOG("  nitro-ai: site %s at 0x%06lx already calls 0x%08lx (stock 0x%06lx) - chained", what, site, tgt, stock);
    *next = tgt;
    return nai_call(site, tgt, fn, what);
}
static void nai_attach(void) {
    static const BYTE resp_sig[6] = { 0xa1, 0x38, 0x6a, 0x52, 0x00, 0x85 };
    int ok;
    if (!g_nmp_on) return;
    ok = nmp_site(0x54a178, 0x552fd8, "label table", &n_lab) & nmp_site(0x5049f0, 0x526758, "mission name", &n_mission)
       & nmp_site(0x49c8c0, 0x4a2ce0, "sim time", &n_simtime) & nmp_site(0x412830, 0x415490, "ai_SetBehaviour", &n_beh)
       & nmp_site(0x40bd90, 0x418400, "fsm_SetSkill", &n_skill) & nmp_site(0x40c0a0, 0x418710, "fsm_SetMaxAttackers", &n_cap)
       & nmp_site(0x40b450, 0x417ac0, "object_HealthFraction", &n_health) & nmp_site(0x4551f0, 0x4473b0, "net_GetObjectPlayerId", &n_objid)
       & nmp_site(0x454ea0, 0x447050, "net_SetPlayerScore", &n_setscore) & nmp_site(0x453df0, 0x4447a0, "net_ShowChatMessage", &n_chat)
       & nmp_site(0x454620, 0x4467e0, "net_FindPlayerById", &n_name) & nmp_site(0x4513c0, 0x44c930, "spawner", &n_spawner)
       & nmp_site(0x4575d0, 0x454070, "entity_FindWorldRecord", &n_findrec) & nmp_site(0x465310, 0x4644b0, "entity_RemoveVehicle", &n_remove)
       & nmp_site(0x464890, 0x463a20, "net_ApplyVehicleState", &n_mirror) & nmp_site(0x4a31d0, 0x4aec80, "weapon list", &n_wlist)
       & nmp_site(0x4a3560, 0x4af010, "weapon_SetTrigger", &n_trigger) & nmp_site(0x462040, 0x44fd80, "object_ClassDamage", &n_cdamage)
       & nmp_site(0x4bdf78, 0x4c4624, "kill score constant", &n_killk) & nmp_site(0x540d98, 0x5414d8, "spawn count", &n_spcount)
       & nmp_site(0x507da0, 0x506960, "team lists", &n_teamlist) & nmp_site(0x51f5d0, 0x51e190, "team counts", &n_teamcnt)
       & nmp_site(0x414bc0, 0x406120, "fsm_TeleportOffset", &n_teleport) & nmp_site(0x467400, 0x466600, "entity_StartEngine", &n_startcar)
       & nmp_site(0x654b9c, 0x5fb0fc, "DEF difficulty byte", &n_defbyte) & nmp_site(0x501818, 0x523580, "single-player melee flag", &n_spmelee)
       & nmp_site(0x540d8c, 0x5454fc, "respawn pending", &n_respawn_flag) & nmp_site(0x541034, 0x53f268, "in-game flag", &n_ingame);
    n_sptab = 0x005414f8;                            /* not in the port table: team-0 spawn records (0x44c930 reads them), position at +0x28 */
    n_respawn = 0x0044caf0;                          /* the table maps Gold 0x451570 to 0x44cb06 (mid-function); the function starts here */
    ok = ok && nmp_sig(n_respawn, resp_sig, 6, "net_RequestRespawn") && *(DWORD *)(DWORD_PTR)n_spcount < 65;
    if (!ok) { NMP_LOG("  nitro-ai: OFF (sites)"); return; }
    ok = nai_call(0x4bd4bf, 0x4b3630, (void *)nai_odef, "ODEF walk") & nai_call(0x4079a2, 0x42fee0, (void *)nai_melee_flag, "host tick")
       & nai_call(0x46332e, 0x42fee0, (void *)nai_kill_stub, "kill credit") & nai_call(0x4064e6, 0x4af010, (void *)nai_trigger, "AI trigger")
       & nai_call_chain(0x432e24, 0x4076f0, (void *)nai_ai_frame, &g_nai_frame_next, "ai_FrameTick") & nai_call(0x464409, 0x447050, (void *)nai_score_set, "mirror score")
       & nai_call(0x445db8, 0x463a20, (void *)nai_st_mirror, "'ST' mirror")
       & nai_call(0x461114, 0x44fd80, (void *)nai_class_damage, "damage 1") & nai_call(0x46504b, 0x44fd80, (void *)nai_class_damage, "damage 2")
       & nai_call(0x465693, 0x44fd80, (void *)nai_class_damage, "damage 3") & nai_call(0x4a7c43, 0x44fd80, (void *)nai_class_damage, "damage 4")
       & nai_call(0x4a7cd6, 0x44fd80, (void *)nai_class_damage, "damage 5");
    {   static const DWORD sp[7] = { 0x432956, 0x432ce0, 0x445bb2, 0x445cfc, 0x445e2c, 0x44607d, 0x447d05 };   /* player spawner calls [Gold's 7 coop_spawn sites] */
        int q, n = 0; for (q = 0; q < 7; q++) n += nai_call(sp[q], 0x44c6f0, (void *)nai_coop_spawn, "co-op spawn");
        NMP_LOG("  nitro-ai: co-op: %d/7 player-spawn calls adopt the mission player object for the host (co-op scenes only)", n); }
    g_nmp_rx_hook = nai_rx; g_nmp_tick_hook = nai_tick; g_nmp_migr_hook = nai_migrated; g_nmp_shell_hook = nai_attach_shell;
    g_nai_ok = 1;
    NMP_LOG("  nitro-ai: ON (%s) - pool %d, combat arenas in ARENA+ sessions only; skill from the DEF byte (%d)", ok ? "all 12 sites" : "SOME SITES OFF", NAI_POOL,
            *(volatile BYTE *)(DWORD_PTR)n_defbyte);
}

#ifdef NMP_IN_PROXY
/* ---- the shipped proxy's entry (strlkproxy.c: nitro_dllmain -> apply_nitro_mp; hook_LoadLibraryA -> nmp_attach_shell).
 * Nitro only (nitro_dllmain is not reached on Gold). I76_NITRO_MP=0 leaves everything here off; I76_NITRO_AI=0 keeps the
 * ANet 2 layer but not the AI. Inert in a stock session: the dpReceive hook passes through and every patched call site
 * does what the stock call did unless the session is ARENA+ (species 0x7676), which only the host form's ARENA+ boxes
 * create (record s.0.3; nitro_form.c, the host form's ARENA+ / CO-OP SCENES boxes, both off by default). ---- */
static HMODULE WINAPI hook_LoadLibraryA(LPCSTR name);
static void apply_nitro_mp(void) {
    if (env_flag("I76_NITRO_MP", 8, 1) == 0) { mlog("  nitro-mp: I76_NITRO_MP=0 - off"); return; }
    nmp_attach_exe();
    if (g_nmp_on && env_flag("I76_NITRO_AI", 8, 1) != 0) nai_attach();
    if (g_nmp_on && !p_LoadLibraryA)   /* nitshell.dll is loaded by nitro.exe through LoadLibraryA: its hooks attach there */
        p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
}
#endif
