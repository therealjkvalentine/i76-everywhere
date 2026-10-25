/* aimelee.c - AI MELEE: computer opponents in a network melee (I76_AIMELEE, default on with I76_COOP_AI=1; acts only
 * in an arena file named ai_*.lvl). Included from strlkproxy.c after the co-op section (it uses coop_ai_role,
 * coop_ai_in_mission, coop_ai_object, coop_chain_send, g_coop_next, g_coop_chain). Design:
 * docs/records/AI-MELEE-AND-LATE-JOIN-2026-10-19.md (option (b)); what was built and measured:
 * docs/records/AI-MELEE-M1-2026-10-19.md.
 *
 * THE ARENA (tools/aimelee-mission.py): a stock melee arena plus N AI cars as ODEF class-1 car objects on team 7, in
 * ADDON\ai_*.lvl (lower case: the shells CRC-check a .lvl on join). Every machine loads the cars with the arena; the
 * co-op sync already in the proxy (I76_COOP_AI) makes the HOST's copies the real ones: 'AT' carries their state to the
 * joiners, the joiners' shots reach them through the stock 'SH' replay, damage to them is computed on the host only.
 *
 * 1. HOST TICK (0x40a5d0 `call 0x401310` in ai_FrameTick, the "single-player melee?" test that picks
 *    ai_MeleeFrameTick 0x40a130 over the script runner fsm_RunMachines). In a network game 0x501818 is 0, so the
 *    script runner runs (the arena has an empty FSM) and 0x40a130 never does - so the host's death cannot end the game
 *    through it (0x40a130 sets the outcome when the world root dies). Here, on the host in an ai_*.lvl, every AI car of
 *    the label table (coop_ai_object: class 1, not player-flagged, no player-table slot) that is alive gets
 *    ai_SetBehaviour 0x412830(car, target, 0 = attack) every frame, as 0x40a130 does for the world root. Target: the
 *    nearest live human car of the 16 player-table slots (I76_AIMELEE_TEAMS=1: only humans whose team, object+0x10
 *    bits 16..18, differs from the car's). Sticky: the car keeps its target until it dies or another human is 20 %
 *    nearer (no flip-flop between two humans at similar range). Once per mission per car: skill I76_AIMELEE_SKILL
 *    (1..5, default 3, the stock melee's; 0x40bd90 + ai+0xa818 = skill - 1, as 0x40a270); the host's own car gets the
 *    attacker cap I76_AIMELEE_CAP (default 8, the stock melee's 0x40c0a0: only the world root has an "on deck" limit).
 * 2. KILL CREDIT (0x46419d `call 0x401310` near the end of entity_DamageAndKill 0x463a80, reached once per kill;
 *    edi = victim object, ebp = damage record, *record = attacker). In a network game the stock code credits only
 *    player victims. Host: an AI victim whose attacker maps to a player id (0x4551f0, also for projectiles) is queued
 *    and sent from the pump as 'AK' { u16 'AK', u8 seq, u8 0, u16 killer id, i16 victim label index, i32 score }
 *    (3 copies, deduplicated by seq). score = victim mass x killer 1/mass x [0x4bdf78] (1000), the stock 0x454ff0
 *    formula. The killer's machine (the host itself, or a joiner) adds 1 kill and the score to its OWN slot through
 *    0x454ea0, which also runs the MAX SCORE test; its 'ST' carries the new numbers to everyone (stock). Every machine
 *    prints "<AI name> was destroyed by <player>" (0x453df0, the local message line). AI names: the shell's AUTO
 *    MELEE list (53 names, i76shell 0x1004b438), the k-th AI car of the arena gets name (5 + 13 k) % 53; since 2026-10-25 a
 *    sci-fi name + " (AI)" instead (I76_AI_NAMES, default 1; ai_label below).
 * 3. WAVES (I76_AIMELEE_WAVE=1, default; needs I76_COOP_CHAIN=1): when every AI car has been dead for
 *    I76_AIMELEE_WAVE_S seconds (default 8), the host reloads the same arena in the same session through the co-op
 *    chain ('AM' kind 0, state 7: the measured co-op reload path), so the AI come back. Each machine keeps its own
 *    kills / deaths / score across the reload (saved at the reload, written back through 0x454ea0 once its car is in
 *    the table again).
 * 4. RESPAWN (I76_AIMELEE_RESPAWN=1, default): in an ai_*.lvl a dead human (host or joiner) asks for a respawn
 *    (0x451570(1), the co-op scenes' auto respawn) - otherwise a host killed by the AI would sit in the death view.
 * I76_AIMELEE=0 turns all of it off (the AI cars then sit idle, the co-op sync still mirrors them).
 * LAB ONLY: I76_AIMELEE_TEST_HP=<1..100> removes every AI car's armour and cuts its chassis to that % of max on the host
 * when its skill is set (so a test kill takes a few hits); off by default, never in a pack.
 * 5. TEAMS (docs/records/MP-TEAMS-2026-10-20.md). Stock team play: the host form's TEAM PLAY box (shell [0x100d4024]
 *    & 0x8000) becomes setup bit 3 -> exe 0x541010 on every machine; each human picks a team in the shell's popup
 *    (0x1000bdd0: 8 rows, Grey Hounds .. Men In Black = team 0..7, the exe's 3 bits); the pick travels in the ANet
 *    player data (byte 1 = team + 1) into the player slot's flags +0x1c bits 16..18 (0x4541b0) and from there into
 *    the car's object+0x10 bits 16..18 (0x451180). Team play off: every machine puts ITSELF on team 0 and every other
 *    human on team 1. The AI cars are team 7 in the arena file = Men In Black, the LAST row of the popup.
 *    I76_AIMELEE_TEAMS: unset / auto (default) = the team rule is on when the session has TEAM PLAY on; 0 = never
 *    (AI attack every human); 1 = always. With the rule on an AI car attacks the nearest live car of ANOTHER team -
 *    humans, and the other AI cars on another team (so an AI standing in for a human fights like him); a human who
 *    picked Men In Black plays on the AI's side. The host carries each AI car's team to the joiners in byte 3 of its
 *    'AT' record (0x80 | team; 0 before, ignored by older proxies), and a joiner moves its copy to that team list
 *    (mpf_move_team), so radar colours, target lock (0x461040 skips same-team cars) and gun hold agree everywhere.
 *    A human's kill of an AI car of HIS OWN team scores nothing (stock: 0x464890 credits only another team's victim);
 *    the message still shows. The AI fill's team rule (who parks, which team a returning AI takes) is in mpfill.c.
 * 6. AI RESPAWN (I76_AIMELEE_RESPAWN_AI=1, default; owner 2026-10-20 "shouldn't they be respawned instead"; record
 *    docs/records/AI-MELEE-RESPAWN-2026-10-20.md). A dead AI car comes back like a human: I76_AIMELEE_RESPAWN_AI_S
 *    (default 5, the stock respawn delay 0x4bdf30) after its death the HOST builds a fresh car of the same .vcf (the
 *    label is the .vcf stem) at the spawn point farthest from every live car with the stock spawner 0x4513c0 (the
 *    single-player melee's AI spawn; 0x451180 is its network-player twin), puts the new object into the label-table
 *    entry of the wreck (so 'AT', the fill tags and the name stay with the label index), moves it to the wreck's team
 *    list and removes the wreck as the human respawn does (0x4575d0 + 0x465310, as 0x451180 does with a player's old
 *    car). A JOINER does the same for its own copy when the host's 'AT' record for that label says "alive" while its
 *    copy is a wreck (aim_at_revive, from coop_ai_apply); the mirror then snaps the new car to the host's transform.
 *    No packet is added, so a late joiner, a lost packet and a host migration all heal from the next 'AT'. With it on,
 *    waves default off (I76_AIMELEE_WAVE=1 brings them back; I76_AIMELEE_RESPAWN_AI=0 = the M1 behaviour).
 * 7. SCORE ROWS (I76_AIMELEE_SCORE_ROWS=1, default): every AI car in play holds a row of the stock player table
 *    0x541070 on every machine (id AIM_ID0 + its number, the AUTO MELEE name, flags team << 16 | 2 = "team read", no
 *    car pointer, latency -1 so 0x454340 never elects it host, last-heard = now so 0x454e60 does not wait for it), taken
 *    from the top slot down (0x4541b0 gives humans the lowest free slot), counted in [0x541068] (the scoreboard
 *    0x451f10 prints that many rows). Each AI car's owner id (entity+0x480) is its row id, so the stock code does the
 *    rest: a human killed by an AI gets "<X> was killed by <AI name>" and a death without the -500 (0x463a80 /
 *    0x455130 see a killer); the host's 'AT' record carries the row's kills / deaths / score (0x4644d0 reads them by
 *    owner id) and every joiner's mirror writes them into its own row through 0x454ea0, which runs the MAX SCORE test;
 *    team sums (0x452930, the standings) walk all 16 slots. The HOST keeps the AI rows: an AI's kill of a human (its own
 *    car: entity+0x482; a remote human: the killer id of the 'ST' record that wrecks it, hook at 0x456c78) and of
 *    another AI (kill hook) add 1 kill and the stock score (victim mass x killer 1/mass x 1000); every AI death adds a
 *    death (-500, floor 0, when nobody gets the kill, as 0x455130); same-team kills score nothing (stock). A parked AI
 *    (fill) gives its row back (the host marks parked cars with 0x40 in 'AT' byte 3) and gets its numbers back when it
 *    returns. The scoreboard box (0x451ac0, 9 lines: header + 8 rows) is created with 15 lines in an ai_*.lvl. */
static int g_aim_test_hp, g_aim_on, g_aim_skill = 3, g_aim_cap = 8, g_aim_teams = -1, g_aim_wave = 1, g_aim_wave_s = 8, g_aim_respawn = 1;
static int g_aim_respawn_ai = 1, g_aim_respawn_ai_s = 5, g_aim_rows = 1, g_aim_test_shoot, g_aim_test_own_hp, g_aim_test_split, g_aim_test_ctl;
#define AIM_ID0 0x7E00                                       /* AI row ids: AIM_ID0 + AI number (ANet ids are small) */
static int aim_is_ai_id(unsigned id) { return id >= AIM_ID0 && id < AIM_ID0 + 64; }
static DWORD g_aim_dead_t[2048];                             /* host: label dead since (GetTickCount | 1) */
static BYTE g_aim_at_flags[2048];                            /* joiner: last 'AT' byte 3 per label (0x80 valid, 0x40 parked) */
static volatile LONG g_aim_respawns, g_aim_revives, g_aim_rowcredits;
static BYTE *aim_recreate(int li, int sp, const char *why); static void aim_row_add(unsigned id, int dk, int dd, int ds, const char *why);
static double mpf_near_car(double x, double z); static double mpf_d2(BYTE *a, double x, double z);   /* mpfill.c */
static void aim_respawn_tick(void); static void aim_rows_tick(int role); static void aim_lab_tick(void); static void aim_av_tick(int role, int r, void *buf, void *size);
static int mpf_heading(BYTE *o); static void mpf_teleport(BYTE *o, double x, double z, int hdg);
#define AIM_LAST_TEAM 7                                      /* Men In Black: the popup's last row, the arena file's AI team */
static int aim_team_rule(void) { return g_aim_teams > 0 || (g_aim_teams < 0 && *(volatile int *)0x00541010); }
static int aim_team(BYTE *o) { return (int)((*(DWORD *)(o + 0x10) >> 16) & 7); }
static volatile LONG g_aim_ticks, g_aim_orders, g_aim_kills, g_aim_ak_sent, g_aim_ak_got, g_aim_credited, g_aim_waves;
#define AIM_AK_PKT 0x4b41                                    /* 'AK' */
#define AIM_MAX 64
static BYTE *g_aim_car[AIM_MAX], *g_aim_tgt[AIM_MAX]; static int g_aim_skilled[AIM_MAX], g_aim_n;
static BYTE *g_aim_capped;
static BYTE g_aim_dead_seen[2048];                       /* label index: 1 = its death was logged (kill hook or tick) */                                   /* the host car that got the attacker cap */
static DWORD g_aim_last_tick, g_aim_all_dead_since, g_aim_status_t;
static void aim_save_score(void);
static int mpf_parked_obj(BYTE *o); static int mpf_move_team(BYTE *o, DWORD team); static void mpf_fill_tick(void); static void mpf_coop_tick(void); void mpfill_pump(int role);   /* mpfill.c */
static int g_aim_inj; static char g_aim_inj_m[16];         /* 8. the loaded stock arena got the injected AI pool */
static int aim_arena(void) {                                 /* "ai_*.lvl" (any case), or a stock arena with the injected pool (8.) */
    const char *m = (const char *)0x005049f0; size_t L = strlen(m);
    if (!g_aim_on) return 0;
    if (g_aim_inj && _strnicmp(m, g_aim_inj_m, 15) == 0) return 1;
    return _strnicmp(m, "ai_", 3) == 0 && L > 7 && L < 16 && _stricmp(m + L - 4, ".lvl") == 0;
}
/* 5. 'AT' byte 3 (strlkproxy.c coop_ai_host_send / coop_ai_apply): the host's team of an AI car, 0x80 | team */
static BYTE aim_at_team(BYTE *o) {                           /* 7. + 0x40 = parked by the fill (the joiners drop its row) */
    if (!aim_arena() || !(aim_team_rule() || g_aim_rows)) return 0;
    return (BYTE)(0x80 | aim_team(o) | (g_aim_rows && mpf_parked_obj(o) ? 0x40 : 0));
}
static void aim_at_team_apply(int li, BYTE *o, BYTE v) {    /* joiner */
    static BYTE failed[2048]; int was;
    if (li >= 0 && li < 2048 && aim_arena()) g_aim_at_flags[li] = v;
    if (!(v & 0x80) || !aim_arena() || li < 0 || li >= 2048 || (was = aim_team(o)) == (v & 7)) return;
    if (mpf_move_team(o, v & 7)) { failed[li] = 0; mlog("  aimelee: AI '%.8s' (label %d) team %d -> %d (host's 'AT')", (char *)o, li, was, v & 7); }
    else if (!failed[li]) { failed[li] = 1; mlog("  aimelee: AI '%.8s' (label %d) not in team list %d - team %d from the host not applied", (char *)o, li, was, v & 7); }
}
static int aim_alive(BYTE *o) {
    BYTE *e = o ? *(BYTE **)(o + 0x70) : NULL;
    return e && !(e[0x454] & 0x20) && !(*(DWORD *)(o + 0x10) & 0x200);
}
static BYTE *aim_slot_car(int k) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; return *(WORD *)p ? *(BYTE **)(p + 0x28) : NULL; }
/* AI car number of a label (names, row ids). Counted ONCE per mission load (label table + count), when every AI car of the
 * file / pool is a whole car on every machine. A live count drifted: in the soak (cycle 19) a joiner's parked wreck stopped
 * counting as a car, every later car's number moved down by one, and its row took the next car's id and name. */
static short g_aim_ord[2048]; static BYTE *g_aim_ord_tab; static int g_aim_ord_count = -1, g_aim_ord_n;
static void aim_ord_build(void) {
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i, k = 0;
    if (tab == g_aim_ord_tab && count == g_aim_ord_count) return;
    g_aim_ord_tab = tab; g_aim_ord_count = count;
    for (i = 0; i < 2048; i++) g_aim_ord[i] = -1;
    if (tab && count > 0 && count <= 2048) for (i = 0; i < count; i++) if (coop_ai_object(i, count, tab)) g_aim_ord[i] = (short)k++;
    g_aim_ord_n = k;
}
static int aim_ordinal(int li) {                             /* label index -> 0-based AI car number, -1 if none */
    aim_ord_build();
    return li >= 0 && li < 2048 && li < g_aim_ord_count ? g_aim_ord[li] : -1;
}
static int aim_label_of(int k) {                             /* 0-based AI car number -> label index, -1 if none */
    int i; aim_ord_build();
    for (i = 0; i < g_aim_ord_count && i < 2048; i++) if (g_aim_ord[i] == k) return i;
    return -1;
}
static BYTE *aim_ai_obj(int k) { int li = aim_label_of(k); return li < 0 ? NULL : *(BYTE **)(*(BYTE **)(0x0054a178 + 4) + li * 16 + 8); }
/* AI NAMES (I76_AI_NAMES, default 1 whenever the AI cars have names: aimelee rows / kill lines, nitro_ai.c; owner 2026-10-25 "AI cars
 * should have (AI) after and AI names like HAL9000, MOTHER, etc. from sci-fi"; record docs/records/AI-NAMES-2026-10-25.md).
 * The k-th AI car of the mission is "<sci-fi name> (AI)". k is the car's AI number (aim_ordinal: label-table order, counted once
 * per load, identical on every machine because every machine loads the same file + pool), and the name is
 * AI_NAMES[(k + seed) % N] with seed = a hash of the mission file name (also identical everywhere), so nothing travels on the
 * wire: the host and every joiner (PC or Mac, same proxy) derive the same label for the same car, and the cast changes from
 * arena to arena. Width: the player-table name is 24 bytes (0x454620 / 0x454680 copy 0x18), the scoreboard prints it with
 * "%-15s" under a 15-character "Player Name" header, so every label is at most 15 characters: names up to 10 + " (AI)".
 * Dropped as too long: DEEP THOUGHT, NEUROMANCER. A human who drops in parks an AI car (mpfill.c) and that car's row is given
 * back (aim_rows_tick), so its label leaves the list; the human's row carries his own ANet name (stock).
 * I76_AI_NAMES=0: the stock names (Gold: the shell's AUTO MELEE list; Nitro: nitro_ai.c's list), no suffix. */
static const char *const AI_NAMES[] = {
    "HAL 9000", "MOTHER", "SKYNET", "JOSHUA", "GLaDOS", "KITT", "VIKI", "SONNY", "MARVIN", "GORT", "ROBBY", "BISHOP", "ASH",
    "TARS", "CASE", "HOLLY", "SHODAN", "EDI", "CORTANA", "COLOSSUS", "PROTEUS", "ED-209", "DAVID", "AVA", "SAMANTHA",
    "WINTERMUTE", "DURANDAL", "MULTIVAC", "ROY" };
#define AI_NAMES_N ((int)(sizeof(AI_NAMES) / sizeof(AI_NAMES[0])))
static int g_ai_names = -1;
static int ai_names_on(void) { if (g_ai_names < 0) g_ai_names = env_flag("I76_AI_NAMES", 8, 1) != 0; return g_ai_names; }
static unsigned ai_names_seed(const char *mission) {         /* FNV-1a of the lower-case file name, at most 15 chars */
    unsigned h = 2166136261u; int i;
    for (i = 0; mission && mission[i] && i < 15; i++) { BYTE c = (BYTE)mission[i]; h ^= c >= 'A' && c <= 'Z' ? c + 32 : c; h *= 16777619u; }
    return h;
}
static const char *ai_label(int k, unsigned seed, char *buf) { /* buf >= 24 bytes; k = the 0-based AI car number */
    sprintf(buf, "%s (AI)", AI_NAMES[(unsigned)((k < 0 ? 0 : k) + seed % AI_NAMES_N) % AI_NAMES_N]);
    return buf;
}
static const char *aim_name(int k, char *buf) {             /* sci-fi label (I76_AI_NAMES), else the shell's AUTO MELEE names, else "AI n" */
    HMODULE sh;
    if (ai_names_on() && k >= 0) return ai_label(k, ai_names_seed((const char *)0x005049f0), buf);
    sh = GetModuleHandleA("i76shell.dll");
    sprintf(buf, "AI %d", k + 1);
    if (sh && k >= 0) {
        BYTE *b = (BYTE *)sh; IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(b + ((IMAGE_DOS_HEADER *)b)->e_lfanew);
        DWORD sz = nt->OptionalHeader.SizeOfImage, slot = 0x1004b438 - 0x10000000 + 4 * ((5 + 13 * k) % 53);
        const char *s = *(const char **)(b + slot);
        if ((BYTE *)s > b && (BYTE *)s < b + sz - 24 && s[0] >= 'A' && s[0] <= 'Z') { strncpy(buf, s, 23); buf[23] = 0; }
    }
    return buf;
}
static int aim_slot_of(WORD id) { int k; for (k = 0; k < 16; k++) if (*(WORD *)((BYTE *)0x00541070 + k * 0x48) == id) return k; return -1; }
static int aim_index(BYTE *o) {                              /* per-car memory (targets, skill applied) */
    int i;
    for (i = 0; i < g_aim_n; i++) if (g_aim_car[i] == o) return i;
    if (g_aim_n >= AIM_MAX) return -1;
    g_aim_car[g_aim_n] = o; g_aim_tgt[g_aim_n] = NULL; g_aim_skilled[g_aim_n] = 0;
    return g_aim_n++;
}
/* --- 1. the host tick ---------------------------------------------------------------------------------------- */
static void aim_tick(void) {
    BYTE *tab = *(BYTE **)(0x0054a178 + 4), **root; int count = *(int *)(0x0054a178 + 8), i, k, alive = 0, total = 0, rule, nai = 0;
    BYTE *ais[AIM_MAX];
    DWORD now = GetTickCount(); static BYTE *last_tab; static int last_count;
    if (now - g_aim_last_tick > 2000 || tab != last_tab || count != last_count) {   /* a new mission (or a wave reload) */
        g_aim_n = 0; g_aim_capped = NULL; g_aim_all_dead_since = 0; last_tab = tab; last_count = count;
        memset(g_aim_dead_seen, 0, sizeof(g_aim_dead_seen)); memset(g_aim_dead_t, 0, sizeof(g_aim_dead_t));
        if (tab && count > 0 && count <= 2048)               /* wrecks already there (a host migration): their deaths were counted */
            for (i = 0; i < count; i++) { BYTE *o = coop_ai_object(i, count, tab); if (o && !aim_alive(o)) g_aim_dead_seen[i] = 1; }
    }
    g_aim_last_tick = now;
    g_aim_ticks++;
    if (!tab || count <= 0 || count > 2048) return;
    mpf_fill_tick();                                         /* I76_AIMELEE_FILL: park / bring pool cars (mpfill.c) */
    rule = aim_team_rule();
    if (rule)                                                /* 5. AI cars in play are targets for an AI of another team */
        for (i = 0; i < count && nai < AIM_MAX; i++) { BYTE *o = coop_ai_object(i, count, tab); if (o && !mpf_parked_obj(o) && aim_alive(o)) ais[nai++] = o; }
    root = ((BYTE **(__cdecl *)(void))0x00457530)();
    if (root && *root && *root != g_aim_capped && *(BYTE **)(*root + 0x70) && *(BYTE **)(*(BYTE **)(*root + 0x70) + 0x108)) {
        int cap = g_aim_cap;
        ((void (__cdecl *)(BYTE *, int *))0x0040c0a0)(*root, &cap);
        g_aim_capped = *root;
    }
    for (i = 0; i < count; i++) {
        BYTE *o = coop_ai_object(i, count, tab), *best = NULL, *cur; double ax, az, bd = 1e30, cd = 1e30; int j;
        if (!o || mpf_parked_obj(o)) continue;               /* parked by the AI fill: out of the game, not in the wave */
        total++;
        if (!aim_alive(o)) {                                 /* a death that never reached the kill hook: no attacker record */
            if (!g_aim_dead_seen[i]) {
                g_aim_dead_seen[i] = 1; mlog("  aimelee: AI #%d '%.8s' (label %d) died without an attacker record (collision, fall or no-owner damage) - no credit", aim_ordinal(i) + 1, (char *)o, i);
                if (g_aim_rows && aim_ordinal(i) >= 0) aim_row_add(AIM_ID0 + aim_ordinal(i), 0, 1, -500, "death, no killer");
            }
            continue;
        }
        alive++;
        if ((j = aim_index(o)) < 0) continue;
        if (!g_aim_skilled[j] && *(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) {
            int s = difficulty_ai_skill(g_aim_skill), s0 = s;     /* DIFFICULTY HOOK (difficulty.c): Play Options byte, env overrides */
            ((void (__cdecl *)(BYTE *, int *, int *))0x0040bd90)(o, &s, &s);
            *(int *)(*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108) + 0xa818) = s0 - 1;
            g_aim_skilled[j] = 1;
            if (g_aim_test_split && aim_ordinal(i) == 0 && aim_team(o) != 6 && mpf_move_team(o, 6))   /* LAB: AI #1 on team 6 (AI vs AI) */
                mlog("  aimelee: LAB I76_AIMELEE_TEST_SPLIT - AI '%.8s' (label %d) moved to team 6", (char *)o, i);
            if (g_aim_test_hp) {                             /* LAB: armour and chassis to n % of max (cheats.md entity map) */
                BYTE *e = *(BYTE **)(o + 0x70); int sd;
                for (sd = 0; sd < 4; sd++) {
                    int a = 0, c = *(int *)(e + 0x168 + 4 * sd) * g_aim_test_hp / 100;   /* armour gone: every hit reaches the chassis */
                    if (c < 1) c = 1;
                    *(int *)(e + 0x138 + 4 * sd) = a; *(int *)(e + 0x178 + 4 * sd) = a;
                    *(int *)(e + 0x148 + 4 * sd) = c; *(int *)(e + 0x18c + 4 * sd) = c;
                }
                mlog("  aimelee: LAB I76_AIMELEE_TEST_HP=%d - AI '%.8s' armour 0, chassis cut to %d %%", g_aim_test_hp, (char *)o, g_aim_test_hp);
            }
        }
        ax = *(double *)(o + 0x40); az = *(double *)(o + 0x50);
        cur = g_aim_tgt[j];
        for (k = 0; k < 16 + nai; k++) {                     /* the 16 player slots, then (team rule) the AI cars in play */
            BYTE *h = k < 16 ? aim_slot_car(k) : ais[k - 16]; double dx, dz, d;
            if (!h || h == o || !aim_alive(h)) continue;
            if (rule && aim_team(h) == aim_team(o)) continue;
            dx = *(double *)(h + 0x40) - ax; dz = *(double *)(h + 0x50) - az; d = dx * dx + dz * dz;
            if (h == cur) cd = d;
            if (d < bd) { bd = d; best = h; }
        }
        if (!best) continue;                                 /* no human to attack: leave the car as it is */
        if (cur && cd < 1e29 && bd > 0.64 * cd) best = cur;  /* keep the current target unless another is 20 % nearer */
        g_aim_tgt[j] = best;
        ((int (__cdecl *)(BYTE *, BYTE *, int))0x00412830)(o, best, 0);
        g_aim_orders++;
    }
    /* --- 3. waves: every AI dead for g_aim_wave_s -> the host reloads the arena (co-op chain path) --- */
    if (total && !alive && g_aim_wave) {
        if (!g_aim_all_dead_since) g_aim_all_dead_since = now;
        else if (now - g_aim_all_dead_since >= (DWORD)g_aim_wave_s * 1000 && *(volatile int *)0x004c2164 == 5) {
            const char *cur = (const char *)0x005049f0;
            if (!g_coop_chain) { static int said; if (!said++) mlog("  aimelee: all %d AI dead - no wave without I76_COOP_CHAIN=1", total); }
            else {
                char msg[64];
                strncpy(g_coop_next, cur, 15); g_coop_next[15] = 0;
                aim_save_score();
                coop_chain_send(0, g_coop_next);
                *(volatile int *)0x004c2164 = 7;
                g_aim_waves++;
                sprintf(msg, "Wave %ld: %d AI coming", g_aim_waves + 1, total);
                ((void (__cdecl *)(short, const char *))0x00453df0)(0, msg);
                mlog("  aimelee: all %d AI dead for %d s - wave %ld: host reloads '%s' (AM sent, chain)", total, g_aim_wave_s, g_aim_waves + 1, cur);
                g_aim_all_dead_since = 0;
            }
        }
    } else g_aim_all_dead_since = 0;
}
static int __cdecl aim_melee_flag(void) {                    /* replaces `call 0x401310` at 0x40a5d0 */
    int r = *(volatile int *)0x00501818;
    if (!r && coop_ai_role() == 1) {
        if (aim_arena()) aim_tick();
        else if (coop_chain_num((const char *)0x005049f0) || coop_scen_num((const char *)0x005049f0)) mpf_coop_tick();   /* I76_COOP_SCALE (mpfill.c): co-op scenes and (2026-10-24) scenarios */
    }
    return r;
}
/* --- 2. kill credit -------------------------------------------------------------------------------------------- */
static struct { WORD killer; short li; int score; BYTE own; } g_aim_q[16]; static volatile LONG g_aim_qn;
static void __cdecl aim_on_kill(BYTE *victim, BYTE *rec) {
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), li;
    WORD killer; int k; BYTE *kc;
    if (!rec || !victim || coop_ai_role() != 1 || !aim_arena() || !tab || count <= 0 || count > 2048) return;
    for (li = 0; li < count && *(BYTE **)(tab + li * 16 + 8) != victim; li++) ;
    if (li == count || !coop_ai_object(li, count, tab)) return;
    g_aim_dead_seen[li] = 1;
    g_aim_kills++;
    killer = (WORD)((unsigned (__cdecl *)(BYTE *))0x004551f0)(*(BYTE **)rec);
    if (g_aim_rows && aim_is_ai_id(killer)) kc = aim_ai_obj(killer - AIM_ID0);   /* 7. an AI car killed it */
    else if (!killer || (k = aim_slot_of(killer)) < 0 || !(kc = aim_slot_car(k)) || !*(BYTE **)(kc + 0x70)) {
        mlog("  aimelee: AI #%d (label %d) destroyed, no player credited (attacker id %u)", aim_ordinal(li) + 1, li, killer);
        if (g_aim_rows) aim_row_add(AIM_ID0 + aim_ordinal(li), 0, 1, -500, "death, no killer credited");
        return;
    }
    if (!kc || !*(BYTE **)(kc + 0x70)) { mlog("  aimelee: AI #%d (label %d) destroyed by AI id %u whose car is gone - no credit", aim_ordinal(li) + 1, li, killer); return; }
    if (g_aim_qn < 16) {
        float v = *(float *)(*(BYTE **)(victim + 0x70) + 0xa4) * *(float *)(*(BYTE **)(kc + 0x70) + 0xa8) * *(float *)0x004bdf78;
        int own = (aim_team_rule() || aim_is_ai_id(killer)) && aim_team(kc) == aim_team(victim);   /* 5. own team: no score (stock team kill) */
        g_aim_q[g_aim_qn].killer = killer; g_aim_q[g_aim_qn].li = (short)li; g_aim_q[g_aim_qn].score = own ? 0 : (int)v; g_aim_q[g_aim_qn].own = (BYTE)own;
        g_aim_qn++;
        if (g_aim_rows && !own) {                            /* 7. the victim's row: a death; an AI killer's row: the kill */
            aim_row_add(AIM_ID0 + aim_ordinal(li), 0, 1, 0, "killed");
            if (aim_is_ai_id(killer)) aim_row_add(killer, 1, 0, (int)v, "killed an AI");
        }
    }
}
static __declspec(naked) void aim_kill_stub(void) {        /* replaces `call 0x401310` at 0x46419d */
    __asm {
        push ebp                                /* damage record (param_2) */
        push edi                                /* victim object (param_1) */
        call aim_on_kill
        add esp, 8
        mov eax, 0x00401310
        jmp eax                                 /* the original call's work; returns to 0x4641a2 */
    }
}
static WORD g_aim_seq_seen[32]; static unsigned g_aim_seq_n;
static void aim_credit(WORD killer, short li, int score, int own) {   /* every machine: message; the killer: its own slot */
    char ai[24], who[32] = "?", msg[96]; int k;
    if (!((int (__cdecl *)(short, char *))0x00454620)((short)killer, who) && aim_is_ai_id(killer)) aim_name(killer - AIM_ID0, who);
    who[24] = 0;
    sprintf(msg, "%s was destroyed by %s", aim_name(aim_ordinal(li), ai), who);
    ((void (__cdecl *)(short, const char *))0x00453df0)(0, msg);
    if (own) { mlog("  aimelee: %s - his own team's AI car: no score (team play)", msg); return; }
    if (killer == *(volatile WORD *)0x00541028 && (k = aim_slot_of(killer)) >= 0) {
        BYTE *p = (BYTE *)0x00541070 + k * 0x48;
        ((void (__cdecl *)(int, int, int, int))0x00454ea0)(killer, *(int *)(p + 0x40) + score, *(short *)(p + 0x3c) + 1, *(short *)(p + 0x3e));
        g_aim_credited++;
        mlog("  aimelee: credited here - %s, +1 kill, +%d score (now %d kills, %d)", msg, score, *(short *)(p + 0x3c), *(int *)(p + 0x40));
    } else mlog("  aimelee: %s (+%d to player %u)", msg, score, killer);
}
static void aim_flush(void) {                                /* host, in the pump */
    static BYTE seq; LONG i, n = g_aim_qn;
    for (i = 0; i < n; i++) {
        BYTE pkt[12 + COOP_DP_SLACK]; int c;
        if (++seq == 0) seq = 1;
        memset(pkt, 0, sizeof(pkt));
        *(WORD *)pkt = AIM_AK_PKT; pkt[2] = seq; *(WORD *)(pkt + 4) = g_aim_q[i].killer; *(short *)(pkt + 6) = g_aim_q[i].li;
        *(int *)(pkt + 8) = g_aim_q[i].score; pkt[3] = g_aim_q[i].own;
        for (c = 0; c < 3; c++)
            if (((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028,
                                                    ((WORD (__cdecl *)(void))0x00454e10)(), 0, pkt, 12) == 0) g_aim_ak_sent++;
        aim_credit(g_aim_q[i].killer, g_aim_q[i].li, g_aim_q[i].score, g_aim_q[i].own);
    }
    g_aim_qn = 0;
}
static void aim_receive(BYTE *pkt, int size) {              /* joiner */
    int i; WORD tag;
    if (size < 12 || !pkt[2]) return;
    tag = (WORD)(pkt[2] | (*(WORD *)(pkt + 6) << 8));      /* seq + label: the 3 copies of one kill */
    for (i = 0; i < 32; i++) if (g_aim_seq_seen[i] == tag) return;
    g_aim_seq_seen[g_aim_seq_n++ % 32] = tag;
    g_aim_ak_got++;
    aim_credit(*(WORD *)(pkt + 4), *(short *)(pkt + 6), *(int *)(pkt + 8), pkt[3] == 1);
}
/* --- 3b. scores across a wave reload; 4. respawn; status line -------------------------------------------------- */
static int g_aim_saved; static short g_aim_sk, g_aim_sd; static int g_aim_ss; static DWORD g_aim_restore_after;
static void aim_save_score(void) {
    int k = aim_slot_of(*(volatile WORD *)0x00541028);
    if (k < 0) return;
    { BYTE *p = (BYTE *)0x00541070 + k * 0x48; g_aim_sk = *(short *)(p + 0x3c); g_aim_sd = *(short *)(p + 0x3e); g_aim_ss = *(int *)(p + 0x40); }
    g_aim_saved = 1; g_aim_restore_after = GetTickCount() + 3000;
    mlog("  aimelee: wave reload - own score kept: %d kills, %d deaths, %d", g_aim_sk, g_aim_sd, g_aim_ss);
}
static void aim_status(int role) {
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i, n = 0, a = 0, len;
    char line[1800];
    len = sprintf(line, "  aimelee: t %lu, %s, %.12s, ticks %ld orders %ld, AI kills %ld, AK sent %ld got %ld, credited here %ld, waves %ld, respawns %ld revives %ld rowcredits %ld; AI",
                  GetTickCount(), role == 1 ? "host" : "joiner", (char *)0x005049f0, g_aim_ticks, g_aim_orders, g_aim_kills, g_aim_ak_sent, g_aim_ak_got, g_aim_credited, g_aim_waves,
                  g_aim_respawns, g_aim_revives, g_aim_rowcredits);
    if (tab && count > 0 && count <= 2048)
        for (i = 0; i < count && len < 600; i++) {
            BYTE *o = coop_ai_object(i, count, tab);
            if (!o) continue;
            n++; if (aim_alive(o)) a++;
            {   int j, k, tk = -1;                           /* the host's target: player-table slot, or 100 + label of an AI car */
                for (j = 0; j < g_aim_n; j++) if (g_aim_car[j] == o && g_aim_tgt[j]) {
                    for (k = 0; k < 16; k++) if (aim_slot_car(k) == g_aim_tgt[j]) tk = k;
                    for (k = 0; tk < 0 && k < count; k++) if (*(BYTE **)(tab + k * 16 + 8) == g_aim_tgt[j]) tk = 100 + k;
                }
                len += sprintf(line + len, " [%d %.8s %s %.0f%% %.1f,%.1f ->%d t%d]", i, (char *)o, aim_alive(o) ? "live" : "dead",
                               aim_alive(o) ? ((double (__cdecl *)(BYTE *))0x0040b450)(o) : 0.0, *(double *)(o + 0x40), *(double *)(o + 0x50), tk, aim_team(o));
            }
        }
    len += sprintf(line + len, " = %d/%d alive; teamplay %d rule %d; humans", a, n, *(volatile int *)0x00541010, aim_team_rule());
    for (i = 0; i < 16; i++) {                               /* 5. each human: player id : slot team (flags +0x1c) / car team */
        BYTE *p = (BYTE *)0x00541070 + i * 0x48, *c = aim_slot_car(i);
        if (*(WORD *)p && !aim_is_ai_id(*(WORD *)p)) len += sprintf(line + len, " %u:t%d/%df%x", *(WORD *)p, (int)((*(DWORD *)(p + 0x1c) >> 16) & 7), c ? aim_team(c) : -1, (unsigned)(*(DWORD *)(p + 0x1c) & 0xffff));
    }
    len += sprintf(line + len, "; rows %d", *(volatile int *)0x00541068);   /* 7. every row: id slot team kills/deaths/score */
    for (i = 0; i < 16 && len < 1300; i++) {
        BYTE *p = (BYTE *)0x00541070 + i * 0x48;
        if (*(WORD *)p) len += sprintf(line + len, " %u@%d:t%d %d/%d/%d", *(WORD *)p, i, (int)((*(DWORD *)(p + 0x1c) >> 16) & 7), *(short *)(p + 0x3c), *(short *)(p + 0x3e), *(int *)(p + 0x40));
    }
    {   BYTE **root = ((BYTE **(__cdecl *)(void))0x00457530)();   /* own car: health % (0x40b450) and position */
        if (root && *root && *(BYTE **)(*root + 0x70))
            sprintf(line + len, "; own car %s %.0f%% %.1f,%.1f", aim_alive(*root) ? "live" : "dead",
                    ((double (__cdecl *)(BYTE *))0x0040b450)(*root), *(double *)(*root + 0x40), *(double *)(*root + 0x50));
    }
    mlog("%s", line);
}
void aimelee_pump(int role, int r, void *buf, void *size) {         /* from coop_dpReceive, every pump call */
    DWORD now;
    if (!g_aim_on || !role) return;
    if (r == 0 && buf && size && *(WORD *)buf == AIM_AK_PKT && role == 2) aim_receive((BYTE *)buf, *(int *)size);
    mpfill_pump(role);                                       /* mpfill.c: status line */
    aim_av_tick(role, r, buf, size);                         /* 8. pool announcement / mismatch message */
    if (!aim_arena()) return;
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AM_PKT && !g_aim_saved) aim_save_score();
    if (role == 1 && g_aim_qn) aim_flush();
    if (!coop_ai_in_mission()) return;
    now = GetTickCount();
    if (role == 1) aim_respawn_tick();                       /* 6. dead AI back after I76_AIMELEE_RESPAWN_AI_S */
    aim_rows_tick(role);                                     /* 7. AI rows in the player table */
    if (g_aim_test_ctl) aim_lab_tick();
    if (g_aim_saved && (LONG)(now - g_aim_restore_after) > 0) {
        int k = aim_slot_of(*(volatile WORD *)0x00541028);
        if (k >= 0 && aim_slot_car(k)) {
            BYTE *p = (BYTE *)0x00541070 + k * 0x48;
            mlog("  aimelee: after the reload own slot read %d kills, %d deaths, %d - writing back %d, %d, %d",
                 *(short *)(p + 0x3c), *(short *)(p + 0x3e), *(int *)(p + 0x40), g_aim_sk, g_aim_sd, g_aim_ss);
            ((void (__cdecl *)(int, int, int, int))0x00454ea0)(*(volatile WORD *)0x00541028, g_aim_ss, g_aim_sk, g_aim_sd);
            g_aim_saved = 0;
        }
    }
    if (g_aim_respawn) {                                     /* 4. the co-op scenes' auto respawn, in ai_*.lvl too */
        static DWORD last; BYTE **root; BYTE *o;
        if (now - last > 1000) {
            last = now;
            root = ((BYTE **(__cdecl *)(void))0x00457530)();
            o = root ? *root : NULL;
            if (o && *(BYTE **)(o + 0x70) && ((*(BYTE **)(o + 0x70))[0x454] & 0x20) && !*(volatile int *)0x00540d8c) {
                ((int (__cdecl *)(int))0x00451570)(1);    /* waits out the 5 s itself; sets 0x540d8c once sent */
                if (*(volatile int *)0x00540d8c) mlog("  aimelee: %s dead - respawn requested", role == 1 ? "host" : "joiner");
            }
        }
    }
    if (now / 5000 != g_aim_status_t) { g_aim_status_t = now / 5000; aim_status(role); }   /* on the 5 s wall-clock grid: two copies on one PC log at the same moment */
}
/* --- 6. AI respawn (header) ------------------------------------------------------------------------------------- */
static BYTE *aim_recreate(int li, int sp, const char *why) {  /* host and joiner: a fresh car for label li at spawn point sp */
    BYTE *tab = *(BYTE **)(0x0054a178 + 4), *old, *nw; int count = *(int *)(0x0054a178 + 8), team, j, k; DWORD lo, hi; int *ent;
    if (!tab || count <= 0 || count > 2048 || li < 0 || li >= count || !(old = coop_ai_object(li, count, tab))) return NULL;
    if (sp < 0 || sp >= *(int *)0x00540d98) sp = 0;
    lo = *(DWORD *)(tab + li * 16); hi = *(DWORD *)(tab + li * 16 + 4); team = aim_team(old); k = aim_ordinal(li);
    nw = ((BYTE *(__cdecl *)(int, int, DWORD, DWORD, int))0x004513c0)(sp, 0, lo, hi, 0);   /* the stock melee spawner (isPlayer 0) */
    if (!nw || !*(BYTE **)(nw + 0x70)) { mlog("  aimelee: respawn of '%.8s' (label %d) FAILED - the spawner returned no car", (char *)old, li); return NULL; }
    *(BYTE **)(tab + li * 16 + 8) = nw;                      /* the label entry now names the new car: 'AT', tags, name follow */
    ent = ((int *(__cdecl *)(BYTE *))0x004575d0)(old);       /* the wreck goes, as 0x451180 removes a player's old car */
    if (ent) ((void (__cdecl *)(int *))0x00465310)(ent);
    if (aim_team(nw) != team && !mpf_move_team(nw, (DWORD)team)) mlog("  aimelee: respawned '%.8s' not in its team list - team %d kept", (char *)nw, aim_team(nw));
    if (g_aim_rows && k >= 0) *(WORD *)(*(BYTE **)(nw + 0x70) + 0x480) = (WORD)(AIM_ID0 + k);
    for (j = 0; j < g_aim_n; j++) if (g_aim_car[j] == old) { g_aim_car[j] = nw; g_aim_tgt[j] = NULL; g_aim_skilled[j] = 0; }
    g_aim_dead_seen[li] = 0; g_aim_dead_t[li] = 0;
    mlog("  aimelee: t %lu AI #%d '%.8s' (label %d) respawned at %.1f,%.1f (spawn point %d), team %d - %s", GetTickCount(), k + 1, (char *)nw, li,
         *(double *)(nw + 0x40), *(double *)(nw + 0x50), sp, aim_team(nw), why);
    return nw;
}
static int aim_free_spawn(void) {                            /* the spawn point farthest from every live car (>= 30 m), -1 */
    int s, ns = *(int *)0x00540d98, best_s = -1; double best = -1;
    for (s = 0; s < ns && s < 64; s++) {
        double d = mpf_near_car(*(double *)(0x0053fdb0 + s * 0x40), *(double *)(0x0053fdc0 + s * 0x40));
        if (d > best) { best = d; best_s = s; }
    }
    return best < 30.0 * 30.0 ? -1 : best_s;
}
static void aim_respawn_tick(void) {                         /* host, from the pump: one respawn per call at most */
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i; DWORD now = GetTickCount();
    if (!g_aim_respawn_ai || !tab || count <= 0 || count > 2048 || *(volatile int *)0x004c2164 != 5) return;
    for (i = 0; i < count; i++) {
        BYTE *o = coop_ai_object(i, count, tab); int sp; char why[64];
        if (!o || mpf_parked_obj(o) || aim_alive(o)) { g_aim_dead_t[i] = 0; continue; }
        if (!g_aim_dead_t[i]) { g_aim_dead_t[i] = now | 1; continue; }
        if ((LONG)(now - g_aim_dead_t[i]) < g_aim_respawn_ai_s * 1000) continue;   /* signed: dead_t = now | 1 can be 1 ms ahead */
        if ((sp = aim_free_spawn()) < 0) continue;
        sprintf(why, "host, dead %.1f s", (LONG)(now - g_aim_dead_t[i]) / 1000.0);
        if (aim_recreate(i, sp, why)) g_aim_respawns++; else g_aim_dead_t[i] = now | 1;   /* failed: try again later */
        return;
    }
}
static BYTE *aim_at_revive(int li, BYTE *o, BYTE *r) {       /* joiner, from coop_ai_apply: host says alive, ours is a wreck */
    int s, ns = *(int *)0x00540d98, sp = 0; double best = 1e30; BYTE *nw;
    if (!g_aim_respawn_ai || !aim_arena() || aim_alive(o) || (*(DWORD *)(r + 4 + 0x48) & 8)) return o;
    for (s = 0; s < ns && s < 64; s++) {
        double dx = *(double *)(0x0053fdb0 + s * 0x40) - *(double *)(o + 0x40), dz = *(double *)(0x0053fdc0 + s * 0x40) - *(double *)(o + 0x50);
        if (dx * dx + dz * dz < best) { best = dx * dx + dz * dz; sp = s; }
    }
    nw = aim_recreate(li, sp, "joiner, the host's 'AT' says alive");
    if (!nw) return o;
    g_aim_revives++;
    return nw;
}
/* --- 7. score rows (header) ------------------------------------------------------------------------------------ */
static struct { short k, d; int s; } g_aim_led[64];          /* each AI's numbers while it has no row (parked), this arena */
static char g_aim_led_m[16]; static DWORD g_aim_led_t;
static BYTE *aim_row(unsigned id) { int k = aim_slot_of((WORD)id); return k < 0 ? NULL : (BYTE *)0x00541070 + k * 0x48; }
static void aim_row_add(unsigned id, int dk, int dd, int ds, const char *why) {   /* host: an AI's kills / deaths / score */
    int n = (int)id - AIM_ID0; BYTE *p = aim_row(id); int k, d, s;
    if (n < 0 || n >= 64 || coop_ai_role() != 1) return;
    if (p) { k = *(short *)(p + 0x3c); d = *(short *)(p + 0x3e); s = *(int *)(p + 0x40); }
    else { k = g_aim_led[n].k; d = g_aim_led[n].d; s = g_aim_led[n].s; }
    k += dk; d += dd; s += ds; if (s < 0) s = 0;              /* 0x455130: never below 0 */
    g_aim_led[n].k = (short)k; g_aim_led[n].d = (short)d; g_aim_led[n].s = s;
    if (p) ((void (__cdecl *)(int, int, int, int))0x00454ea0)((int)id, s, k, d);   /* stores and runs the MAX SCORE test */
    g_aim_rowcredits++;
    mlog("  aimelee: t %lu row %u (AI #%d) %s: %+d kill, %+d death, %+d -> %d kills, %d deaths, %d%s", GetTickCount(), id, n + 1, why, dk, dd, ds, k, d, s, p ? "" : " (no row now: kept)");
}
static int aim_kill_value(BYTE *victim, BYTE *killer) {     /* the stock 0x454ff0 formula */
    if (!victim || !killer || !*(BYTE **)(victim + 0x70) || !*(BYTE **)(killer + 0x70)) return 0;
    return (int)(*(float *)(*(BYTE **)(victim + 0x70) + 0xa4) * *(float *)(*(BYTE **)(killer + 0x70) + 0xa8) * *(float *)0x004bdf78);
}
static void aim_human_killed(BYTE *victim, unsigned killer, const char *how) {   /* host: a human car wrecked by an AI */
    BYTE *kc;
    if (!g_aim_rows || !aim_is_ai_id(killer) || coop_ai_role() != 1 || !aim_arena()) return;
    kc = aim_ai_obj((int)killer - AIM_ID0);
    if (!kc) { mlog("  aimelee: a human was killed by AI id %u, no such car - no credit", killer); return; }
    if (aim_team(kc) == aim_team(victim)) { mlog("  aimelee: AI id %u killed a human of its own team (%s) - no score (team kill)", killer, how); return; }
    aim_row_add(killer, 1, 0, aim_kill_value(victim, kc), how);
}
static void __cdecl aim_st_mirror(BYTE *o, BYTE *rec) {    /* replaces `call 0x464890` at 0x456c78 ('ST' of a remote player) */
    if (o && rec && *(BYTE **)(o + 0x70) && (*(DWORD *)(rec + 0x48) & 8) && aim_alive(o)) aim_human_killed(o, *(WORD *)(rec + 0x58), "killed a remote human");
    ((void (__cdecl *)(BYTE *, BYTE *))0x00464890)(o, rec);
}
static void aim_rows_tick(int role) {                        /* every machine, in an ai_*.lvl mission */
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i, s; DWORD now = GetTickCount();
    static DWORD last; double t;
    if (!g_aim_rows || now - last < 200 || !*(volatile int *)0x00541034 || !tab || count <= 0 || count > 2048) return;
    last = now;
    if (_strnicmp(g_aim_led_m, (const char *)0x005049f0, 15) != 0 || now - g_aim_led_t > 60000) {   /* new arena / session */
        memset(g_aim_led, 0, sizeof(g_aim_led)); strncpy(g_aim_led_m, (const char *)0x005049f0, 15); g_aim_led_m[15] = 0;
    }
    g_aim_led_t = now;
    t = ((double (__cdecl *)(void))0x0049c8c0)();
    for (i = 0; i < count; i++) {
        BYTE *o = coop_ai_object(i, count, tab), *p; int k, want; WORD id;
        if (!o || (k = aim_ordinal(i)) < 0 || k >= 64) continue;
        id = (WORD)(AIM_ID0 + k);
        *(WORD *)(*(BYTE **)(o + 0x70) + 0x480) = id;       /* owner id: kill attribution, 'AT' numbers, HUD name */
        want = role == 1 ? !mpf_parked_obj(o) : ((g_aim_at_flags[i] & 0x80) && !(g_aim_at_flags[i] & 0x40));
        p = aim_row(id);
        if (want && !p) {
            char nm[24];
            for (s = 15; s >= 0 && *(WORD *)((BYTE *)0x00541070 + s * 0x48); s--) ;
            if (s < 0) { static DWORD told; if (now - told > 30000) { told = now; mlog("  aimelee: no free player slot for AI #%d's row (16 in use)", k + 1); } continue; }
            p = (BYTE *)0x00541070 + s * 0x48;
            memset(p, 0, 0x48);
            *(WORD *)p = id; aim_name(k, nm); strncpy((char *)p + 2, nm, 23);
            *(DWORD *)(p + 0x1c) = ((DWORD)aim_team(o) << 16) | 2;
            memcpy(p + 0x20, tab + i * 16, 8);
            *(float *)(p + 0x2c) = (float)t; *(DWORD *)(p + 0x30) = 0xbf800000; *(float *)(p + 0x44) = 1.0f;
            *(short *)(p + 0x3c) = g_aim_led[k].k; *(short *)(p + 0x3e) = g_aim_led[k].d; *(int *)(p + 0x40) = g_aim_led[k].s;
            (*(volatile int *)0x00541068)++;
            mlog("  aimelee: row for AI #%d '%s' (label %d) in slot %d, id %u, team %d, %d kills %d deaths %d", k + 1, nm, i, s, id, aim_team(o),
                 g_aim_led[k].k, g_aim_led[k].d, g_aim_led[k].s);
        } else if (!want && p) {
            g_aim_led[k].k = *(short *)(p + 0x3c); g_aim_led[k].d = *(short *)(p + 0x3e); g_aim_led[k].s = *(int *)(p + 0x40);
            *(WORD *)p = 0; (*(volatile int *)0x00541068)--;
            mlog("  aimelee: row of AI #%d (label %d) given back (parked), kept %d kills %d deaths %d", k + 1, i, g_aim_led[k].k, g_aim_led[k].d, g_aim_led[k].s);
            continue;
        }
        if (p) {
            *(DWORD *)(p + 0x1c) = (*(DWORD *)(p + 0x1c) & ~0x70000u) | ((DWORD)aim_team(o) << 16) | 2;
            *(float *)(p + 0x2c) = (float)t;
            if (role != 1) { g_aim_led[k].k = *(short *)(p + 0x3c); g_aim_led[k].d = *(short *)(p + 0x3e); g_aim_led[k].s = *(int *)(p + 0x40); }
        }
    }
    if (role == 1) {                                         /* the host's own car killed by an AI: entity+0x482 (0x463a80) */
        static BYTE *done; BYTE **root = ((BYTE **(__cdecl *)(void))0x00457530)(), *o = root ? *root : NULL;
        if (o && *(BYTE **)(o + 0x70) && !aim_alive(o) && o != done) { done = o; aim_human_killed(o, *(WORD *)(*(BYTE **)(o + 0x70) + 0x482), "killed the host"); }
    }
}
static int g_aim_box_lines;                                   /* the scoreboard box: 15 lines in an ai_*.lvl, 9 (stock) elsewhere */
static void __cdecl aim_box_create(void) {                  /* replaces `call 0x451ac0` at 0x452d9f (network setup) */
    BYTE want = (BYTE)(g_aim_rows && aim_arena() ? g_aim_box_lines : 9); DWORD old;
    if (*(volatile BYTE *)0x00451b02 != want && VirtualProtect((void *)0x00451b02, 1, PAGE_EXECUTE_READWRITE, &old)) {
        *(volatile BYTE *)0x00451b02 = want; VirtualProtect((void *)0x00451b02, 1, old, &old);
    }
    ((void (__cdecl *)(void))0x00451ac0)();
}
/* LAB ONLY (never in a pack): I76_AIMELEE_TEST_SHOOT=<s> - every s seconds the local car is put 14 m behind the nearest
 * live AI car in play, facing the same way, and pulls its own triggers for 1.5 s (a scripted kill of an AI cut by
 * I76_AIMELEE_TEST_HP); I76_AIMELEE_TEST_OWN_HP=<n> cuts the local car's armour to 0 and chassis to n % at each spawn
 * (so the AI kill humans quickly). */
static void aim_cut(BYTE *o, int pct) {
    BYTE *e = *(BYTE **)(o + 0x70); int sd;
    for (sd = 0; sd < 4; sd++) {
        int c = *(int *)(e + 0x168 + 4 * sd) * pct / 100; if (c < 1) c = 1;
        *(int *)(e + 0x138 + 4 * sd) = 0; *(int *)(e + 0x178 + 4 * sd) = 0; *(int *)(e + 0x148 + 4 * sd) = c; *(int *)(e + 0x18c + 4 * sd) = c;
    }
}
static volatile LONG g_aim_lab_fire; static SHORT (WINAPI *p_aim_gaks)(int);
static SHORT WINAPI aim_lab_gaks(int vk) {                  /* LAB: the exe's GetAsyncKeyState (u32x.dll slot) - fire keys held during a shoot */
    if (g_aim_lab_fire && (vk == '1' || vk == '2' || vk == '3' || vk == '4' || vk == VK_RETURN || vk == VK_LBUTTON)) return (SHORT)0x8001;
    return p_aim_gaks ? p_aim_gaks(vk) : 0;
}
static void aim_lab_tick(void) {
    static BYTE *cut; static DWORD next, fire_until, lastf; BYTE **root = ((BYTE **(__cdecl *)(void))0x00457530)(), *me = root ? *root : NULL;
    DWORD now = GetTickCount();
    if (now - lastf > 2000) {                                /* LAB: <game>imelee-test.txt "shoot S ownhp N" overrides the switches */
        char path[MAX_PATH + 32], b[64]; HANDLE f; DWORD n = 0; int sh, hp;
        lastf = now; sprintf(path, "%s\\aimelee-test.txt", g_dir);
        f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
        if (f != INVALID_HANDLE_VALUE) {
            memset(b, 0, sizeof(b)); ReadFile(f, b, sizeof(b) - 1, &n, NULL); CloseHandle(f);
            if (sscanf(b, "shoot %d ownhp %d", &sh, &hp) == 2 && (sh != g_aim_test_shoot || hp != g_aim_test_own_hp)) {
                mlog("  aimelee: LAB control file: shoot %d ownhp %d", sh, hp); g_aim_test_shoot = sh; g_aim_test_own_hp = hp; cut = NULL; next = now;
            }
        }
    }
    if (!me || !*(BYTE **)(me + 0x70) || !aim_alive(me)) return;
    if (g_aim_test_own_hp && me != cut) { cut = me; aim_cut(me, g_aim_test_own_hp); mlog("  aimelee: LAB I76_AIMELEE_TEST_OWN_HP=%d - own car cut", g_aim_test_own_hp); }
    if (!g_aim_test_shoot) return;
    if ((LONG)(now - next) >= 0) {
        BYTE *tab = *(BYTE **)(0x0054a178 + 4), *best = NULL; int count = *(int *)(0x0054a178 + 8), i; double bd = 1e30;
        next = now + g_aim_test_shoot * 1000;
        for (i = 0; tab && i < count && count <= 2048; i++) {
            BYTE *o = coop_ai_object(i, count, tab); double d;
            if (!o || !aim_alive(o) || (g_aim_at_flags[i] & 0x40) || mpf_parked_obj(o)) continue;
            d = mpf_d2(o, *(double *)(me + 0x40), *(double *)(me + 0x50)); if (d < bd) { bd = d; best = o; }
        }
        if (best) {
            int hd = mpf_heading(best); double r = hd / 57.29578;
            mpf_teleport(me, *(double *)(best + 0x40) - sin(r) * 14.0, *(double *)(best + 0x50) - cos(r) * 14.0, hd);
            fire_until = now + 1500;
            mlog("  aimelee: LAB shoot - behind '%.8s' at %.1f,%.1f heading %d", (char *)best, *(double *)(best + 0x40), *(double *)(best + 0x50), hd);
        }
    }
    g_aim_lab_fire = (LONG)(fire_until - now) > 0;
    if (!p_aim_gaks) { static int tried; if (!tried++) { void *o = patch_iat(GetModuleHandleA(NULL), "u32x.dll", "GetAsyncKeyState", (void *)aim_lab_gaks);
        if (!o) o = patch_iat(GetModuleHandleA(NULL), "USER32.dll", "GetAsyncKeyState", (void *)aim_lab_gaks);
        p_aim_gaks = (SHORT (WINAPI *)(int))o; mlog("  aimelee: LAB fire keys through the exe's GetAsyncKeyState slot: %s", o ? "hooked" : "NOT hooked"); } }
    if ((LONG)(fire_until - now) > 0) {
        int w8[8], k; memset(w8, 0, sizeof(w8));
        if (((int (__cdecl *)(BYTE *, int *))0x004a31d0)(me, w8) == 1)
            for (k = 0; k < w8[0] && k < 5; k++) if (w8[1 + k] >= 0) ((int (__cdecl *)(int, int))0x004a3560)(w8[1 + k], 1);
    }
}
/* --- 8. AI cars in every melee arena (owner 2026-10-20 night: "shouldn't there be ai cars for all player slots not
 * occupied by a human for all levels?"; record AI-MELEE-RESPAWN-2026-10-20.md section 8). I76_AIMELEE_ARENAS=1 (default):
 * when a network game loads one of the 15 stock melee arenas (m01.msn .. m15.msn), every machine appends AIM_POOL car
 * records to the arena's ODEF list right after the stock walk (bwd2_h_ODEF 0x4b45b0 -> 0x4b7a90, the call at 0x4b45bf)
 * and builds them with the loader's own OBJ handler bwd2_h_OBJ 0x4b7ac0, exactly as if the file held them: class-1 car,
 * team 7, label = a multiplayer car variant in I76.ZFS (fixed per arena, so every machine builds the same list), tagged as
 * tools/mp_pool.py tags a pool car (kind 1) with a parking spot on the empty ground at -9000,-9000 (outside the 80 x 80
 * ZMAP: a void tile at height 0, 12.7 km or more from every arena object, all of which lie at x, z >= 0). Same file + same
 * appended records = the same label-table indices everywhere, so 'AT', the fill and the rows work as in ai_*.lvl. The cars
 * start parked; the host's fill (mpfill.c) brings in N - humans of them, N = the host's NO. DRIVERS (shell 0x100f1f50).
 * The files on disk stay stock, the arena list keeps its 15 names. I76_AIMELEE_FILL=0 or I76_AIMELEE_ARENAS=0 skips the
 * injection (stock game: a stock joiner can play). A joiner without the pool (older proxy, stock game, switch off) cannot
 * see the cars: the joiners announce their pool with 'AV' every 5 s, and the host prints a message line once for a human
 * that has said nothing after 15 s. */
#define AIM_POOL 7
#define AIM_AV_PKT 0x5641                                    /* 'AV' */
static int g_aim_arenas = 1;
static BYTE g_aim_inj_body[AIM_POOL][100]; static int g_aim_inj_cnt;
static const char *const g_aim_cars[] = { "valepre1", "valepre2", "valepre3", "vastryd1", "vastryd2", "vastryd3", "vazamz1", "vazamz2", "vazamz3",
    "vccameo1", "vccameo2", "vccameo3", "vcgcour1", "vcgcour2", "vcgcour3", "vcmanta1", "vcmanta2", "vcmanta3", "vcroyal1", "vcroyal2", "vcroyal3",
    "vcpolic1", "vcpolic2", "vcpolic3", "vcvan1", "vcvan2", "vcvan3", "vdlight1", "vdlight2", "vdlight3", "vdstag1", "vdstag2", "vdstag3",
    "vfcoupe1", "vfcoupe2", "vfcoupe3", "vfdclyd1", "vfdclyd2", "vfdclyd3", "vfpalmn1", "vfpalmn2", "vfpalmn3", "vfratlr1", "vfratlr2", "vfratlr3",
    "vfypony1", "vfypony2", "vfypony3", "vgoon1", "vgoon2", "vgoon3", "vjsovrn1", "vjsovrn2", "vjsovrn3", "vmxmarx1", "vmxmarx2", "vmxmarx3",
    "vpjrabt1", "vpjrabt2", "vpjrabt3", "vppirna1", "vppirna2", "vppirna3", "vavikea1", "vavikea2", "vavikea3" };   /* I76.ZFS md5 6dd57b16 (aimelee-mission.py car_pool, bus left out) */
static int aim_stock_arena(const char *m) {                  /* "mNN.msn" NN 1..15 -> NN, else 0 */
    int n;
    if ((m[0] | 0x20) != 'm' || m[1] < '0' || m[1] > '9' || m[2] < '0' || m[2] > '9' || _stricmp(m + 3, ".msn") != 0) return 0;
    n = (m[1] - '0') * 10 + (m[2] - '0');
    return n >= 1 && n <= 15 ? n : 0;
}
static int aim_fill_off(void) { char v[16]; return GetEnvironmentVariableA("I76_AIMELEE_FILL", v, sizeof(v)) && v[0] == '0' && atoi(v) == 0; }
static int __cdecl aim_odef(int *a, BYTE *b, int *c) {     /* replaces `call 0x4b7a90` at 0x4b45bf (the ODEF walk) */
    int r = ((int (__cdecl *)(int *, BYTE *, int *))0x004b7a90)(a, b, c), n, i, k, made = 0;
    const char *m = (const char *)0x005049f0;
    g_aim_inj = 0; g_aim_inj_cnt = 0;
    if (!g_aim_on || !g_aim_arenas || !(n = aim_stock_arena(m))) return r;
    if (!*(volatile int *)0x00541030 || *(volatile int *)0x00501818) {
        mlog("  aimelee: '%s' loads outside a network melee (net %d, single-player melee %d) - no AI pool", m, *(volatile int *)0x00541030, *(volatile int *)0x00501818);
        return r;
    }
    if (aim_fill_off()) { mlog("  aimelee: '%s' - I76_AIMELEE_FILL=0: stock arena, no AI pool", m); return r; }
    for (i = 0; i < AIM_POOL; i++) {
        BYTE chunk[108], *body = chunk + 8; const char *stem = g_aim_cars[(n * 11 + i * 7) % (sizeof(g_aim_cars) / sizeof(g_aim_cars[0]))];
        float px = -9000.0f + (float)(i % 3) * 25.0f, pz = -9000.0f + (float)(i / 3) * 25.0f;
        memset(chunk, 0, sizeof(chunk)); memcpy(chunk, "OBJ", 4); *(DWORD *)(chunk + 4) = 108;
        strncpy((char *)body, stem, 8);
        for (k = 0; k < i; k++) if (_strnicmp((char *)g_aim_inj_body[k], stem, 8) == 0) break;   /* a repeated stem: instance bit (label_bytes) */
        if (k < i) body[7] |= 0x80;
        *(float *)(body + 8) = 1.0f; *(float *)(body + 24) = 1.0f; *(float *)(body + 40) = 1.0f;   /* rotation: identity */
        *(float *)(body + 44) = px; *(float *)(body + 48) = 0.0f; *(float *)(body + 52) = pz;
        memcpy(body + 56, "I76P", 4); body[60] = 1;          /* tools/mp_pool.py tag: kind 1 (AI fill pool), park x, z */
        *(float *)(body + 72) = px; *(float *)(body + 76) = pz;
        *(DWORD *)(body + 92) = 1; body[98] = AIM_LAST_TEAM;  /* class 1 (car), team 7 */
        memcpy(g_aim_inj_body[i], body, 100);
        if (((int (__cdecl *)(BYTE *))0x004b7ac0)(chunk)) made++;
        else mlog("  aimelee: pool car %d '%.8s' NOT built by the OBJ handler", i + 1, stem);
    }
    g_aim_inj_cnt = AIM_POOL; g_aim_inj = made > 0; strncpy(g_aim_inj_m, m, 15); g_aim_inj_m[15] = 0;
    mlog("  aimelee: '%s' (network melee) - %d of %d AI pool cars built after the arena's objects (label table now %d), parked at -9000,-9000",
         m, made, AIM_POOL, *(int *)(0x0054a178 + 8));
    return r;
}
static int aim_drivers(void) {                               /* the host form's NO. DRIVERS (shell 0x100f1f50), 0 if unreadable */
    HMODULE sh = GetModuleHandleA("i76shell.dll"); int v;
    if (!sh) return 0;
    v = *(int *)((BYTE *)sh + (0x100f1f50 - 0x10000000));
    return v >= 1 && v <= 8 ? v : 0;
}
static WORD g_aim_av_id[16]; static BYTE g_aim_av_told[16];
static void aim_av_tick(int role, int r, void *buf, void *size) {   /* 8. pool announcement 'AV' {u16 'AV', u16 id, u8 pool, u8 1} */
    DWORD now = GetTickCount(); int k;
    if (role == 1 && r == 0 && buf && size && *(int *)size >= 6 && *(WORD *)buf == AIM_AV_PKT) {
        WORD id = *(WORD *)((BYTE *)buf + 2);
        for (k = 0; k < 16 && g_aim_av_id[k] && g_aim_av_id[k] != id; k++) ;
        if (k < 16 && !g_aim_av_id[k]) { g_aim_av_id[k] = id; mlog("  aimelee: player %u has the AI pool (%u cars)", id, ((BYTE *)buf)[4]); }
    }
    if (!g_aim_inj || !aim_arena() || !coop_ai_in_mission()) return;
    if (role == 2) {
        static DWORD last;
        if (now - last > 5000) {
            BYTE pkt[8 + COOP_DP_SLACK]; last = now; memset(pkt, 0, sizeof(pkt));
            *(WORD *)pkt = AIM_AV_PKT; *(WORD *)(pkt + 2) = *(volatile WORD *)0x00541028; pkt[4] = (BYTE)g_aim_inj_cnt; pkt[5] = 1;
            ((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028, ((WORD (__cdecl *)(void))0x00454e10)(), 0, pkt, 6);
        }
    } else if (role == 1) {
        static WORD tid[16]; static DWORD tsince[16];
        for (k = 0; k < 16; k++) {
            BYTE *p = (BYTE *)0x00541070 + k * 0x48; WORD id = *(WORD *)p; int j, got = 0;
            if (!id || aim_is_ai_id(id) || id == *(volatile WORD *)0x00541028) { tid[k] = 0; continue; }
            if (tid[k] != id) { tid[k] = id; tsince[k] = now; g_aim_av_told[k] = 0; }
            for (j = 0; j < 16; j++) if (g_aim_av_id[j] == id) got = 1;
            if (!got && !g_aim_av_told[k] && now - tsince[k] > 15000) {
                char msg[96], nm[32] = "?";
                g_aim_av_told[k] = 1;
                ((int (__cdecl *)(short, char *))0x00454620)((short)id, nm); nm[24] = 0;
                sprintf(msg, "%s has no AI pack: no computer cars on his screen", nm);
                ((void (__cdecl *)(short, const char *))0x00453df0)(0, msg);
                mlog("  aimelee: %s (player %u said nothing about the AI pool in 15 s: older proxy, stock game or I76_AIMELEE_ARENAS=0)", msg, id);
            }
        }
    }
}
static void apply_mpfill(void);
static void apply_aimelee(void) {
    BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 }; LONG a0, a1; int ok = 0;
    if (!real_dpReceive) return;                              /* needs I76_COOP_AI=1 (the sync and the pump hook) */
    if (env_flag("I76_AIMELEE", 8, 1) == 0) { mlog("  aimelee: off (I76_AIMELEE=0)"); return; }
    g_aim_skill = env_int("I76_AIMELEE_SKILL", 8, 3); if (g_aim_skill < 1 || g_aim_skill > 5) g_aim_skill = 3;
    g_aim_cap = env_int("I76_AIMELEE_CAP", 8, 8); if (g_aim_cap < 1) g_aim_cap = 8;
    g_aim_teams = env_flag("I76_AIMELEE_TEAMS", 8, -1);     /* unset / auto: follow the session's TEAM PLAY */
    g_aim_respawn_ai = env_flag("I76_AIMELEE_RESPAWN_AI", 8, 1);
    g_aim_respawn_ai_s = env_int("I76_AIMELEE_RESPAWN_AI_S", 8, 5); if (g_aim_respawn_ai_s < 1) g_aim_respawn_ai_s = 5;
    g_aim_rows = env_flag("I76_AIMELEE_SCORE_ROWS", 8, 1);
    g_aim_box_lines = env_int("I76_AIMELEE_BOX_LINES", 8, 15); if (g_aim_box_lines < 9 || g_aim_box_lines > 17) g_aim_box_lines = 15;
    g_aim_test_shoot = env_int("I76_AIMELEE_TEST_SHOOT", 8, 0); if (g_aim_test_shoot < 0) g_aim_test_shoot = 0;
    g_aim_test_split = env_flag("I76_AIMELEE_TEST_SPLIT", 8, 0) == 1;
    g_aim_test_own_hp = env_int("I76_AIMELEE_TEST_OWN_HP", 8, 0); if (g_aim_test_own_hp < 0 || g_aim_test_own_hp > 100) g_aim_test_own_hp = 0;
    g_aim_test_ctl = env_flag("I76_AIMELEE_TEST", 8, 0) == 1 || g_aim_test_shoot || g_aim_test_own_hp;   /* LAB: aim_lab_tick runs */
    g_aim_wave = env_flag("I76_AIMELEE_WAVE", 8, g_aim_respawn_ai ? 0 : 1);
    g_aim_wave_s = env_int("I76_AIMELEE_WAVE_S", 8, 8); if (g_aim_wave_s < 1) g_aim_wave_s = 8;
    g_aim_respawn = env_flag("I76_AIMELEE_RESPAWN", 8, 1);
    g_aim_test_hp = env_int("I76_AIMELEE_TEST_HP", 8, 0); if (g_aim_test_hp < 0 || g_aim_test_hp > 100) g_aim_test_hp = 0;
    a0 = (LONG)(0x00401310 - (0x0040a5d0 + 5)); a1 = (LONG)((DWORD_PTR)aim_melee_flag - (0x0040a5d0 + 5));
    memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
    ok += patch_bytes(0x0040a5d0, o5, w5, 5, "aimelee: host tick (ai_FrameTick melee test)");
    a0 = (LONG)(0x00401310 - (0x0046419d + 5)); a1 = (LONG)((DWORD_PTR)aim_kill_stub - (0x0046419d + 5));
    memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
    ok += patch_bytes(0x0046419d, o5, w5, 5, "aimelee: kill credit (entity_DamageAndKill)");
    if (g_aim_rows) {                                        /* 7. the 'ST' mirror call (AI kills of remote humans) and the box size */
        a0 = (LONG)(0x00464890 - (0x00456c78 + 5)); a1 = (LONG)((DWORD_PTR)aim_st_mirror - (0x00456c78 + 5));
        memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
        if (!patch_bytes(0x00456c78, o5, w5, 5, "aimelee: 'ST' mirror (AI kill credit)")) mlog("  aimelee: 'ST' mirror site NOT patched - AI kills of joiners are not credited");
        a0 = (LONG)(0x00451ac0 - (0x00452d9f + 5)); a1 = (LONG)((DWORD_PTR)aim_box_create - (0x00452d9f + 5));
        memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
        if (!patch_bytes(0x00452d9f, o5, w5, 5, "aimelee: scoreboard box")) mlog("  aimelee: scoreboard box site NOT patched - 8 rows visible");
    }
    g_aim_arenas = env_flag("I76_AIMELEE_ARENAS", 8, 1);
    if (g_aim_arenas) {                                      /* 8. the pool injection after the ODEF walk */
        a0 = (LONG)(0x004b7a90 - (0x004b45bf + 5)); a1 = (LONG)((DWORD_PTR)aim_odef - (0x004b45bf + 5));
        memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
        if (!patch_bytes(0x004b45bf, o5, w5, 5, "aimelee: ODEF walk (AI pool in every arena)")) { g_aim_arenas = 0; mlog("  aimelee: ODEF site NOT patched - no AI in the stock arenas"); }
    }
    g_aim_on = ok == 2;
    if (g_aim_on) apply_mpfill();                            /* AI fill + co-op scaling ride on the same tick site (mpfill.c) */
    mlog("  aimelee: %s (%d/2 sites) - in ai_*.lvl arenas: skill %d, attacker cap %d, teams %s, waves %s (%d s, %s), respawn %s",
         g_aim_on ? "on" : "NOT installed", ok, g_aim_skill, g_aim_cap, g_aim_teams < 0 ? "auto (rule on with TEAM PLAY)" : g_aim_teams ? "on" : "off (AI attack every human)",
         g_aim_wave ? "on" : "off", g_aim_wave_s, g_coop_chain ? "chain on" : "NEEDS I76_COOP_CHAIN=1", g_aim_respawn ? "on" : "off");
    mlog("  aimelee: AI respawn %s (%d s), score rows %s (box %d lines)%s%s", g_aim_respawn_ai ? "on" : "off (waves)", g_aim_respawn_ai_s,
         g_aim_rows ? "on" : "off", g_aim_box_lines, g_aim_test_shoot ? ", LAB shoot test" : "", g_aim_test_own_hp ? ", LAB own HP cut" : "");
}
