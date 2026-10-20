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
 *    MELEE list (53 names, i76shell 0x1004b438), the k-th AI car of the arena gets name (5 + 13 k) % 53.
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
 *    the message still shows. The AI fill's team rule (who parks, which team a returning AI takes) is in mpfill.c. */
static int g_aim_test_hp, g_aim_on, g_aim_skill = 3, g_aim_cap = 8, g_aim_teams = -1, g_aim_wave = 1, g_aim_wave_s = 8, g_aim_respawn = 1;
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
static int aim_arena(void) {                                 /* "ai_*.lvl" (any case) */
    const char *m = (const char *)0x005049f0; size_t L = strlen(m);
    return g_aim_on && _strnicmp(m, "ai_", 3) == 0 && L > 7 && L < 16 && _stricmp(m + L - 4, ".lvl") == 0;
}
/* 5. 'AT' byte 3 (strlkproxy.c coop_ai_host_send / coop_ai_apply): the host's team of an AI car, 0x80 | team */
static BYTE aim_at_team(BYTE *o) { return (BYTE)((aim_arena() && aim_team_rule()) ? 0x80 | aim_team(o) : 0); }
static void aim_at_team_apply(int li, BYTE *o, BYTE v) {    /* joiner */
    static BYTE failed[2048]; int was;
    if (!(v & 0x80) || !aim_arena() || li < 0 || li >= 2048 || (was = aim_team(o)) == (v & 7)) return;
    if (mpf_move_team(o, v & 7)) { failed[li] = 0; mlog("  aimelee: AI '%.8s' (label %d) team %d -> %d (host's 'AT')", (char *)o, li, was, v & 7); }
    else if (!failed[li]) { failed[li] = 1; mlog("  aimelee: AI '%.8s' (label %d) not in team list %d - team %d from the host not applied", (char *)o, li, was, v & 7); }
}
static int aim_alive(BYTE *o) {
    BYTE *e = o ? *(BYTE **)(o + 0x70) : NULL;
    return e && !(e[0x454] & 0x20) && !(*(DWORD *)(o + 0x10) & 0x200);
}
static BYTE *aim_slot_car(int k) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; return *(WORD *)p ? *(BYTE **)(p + 0x28) : NULL; }
static int aim_ordinal(int li) {                             /* label index -> 0-based AI car number, -1 if none */
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i, k = 0;
    if (!tab || count <= 0 || count > 2048 || li < 0 || li >= count) return -1;
    for (i = 0; i < li; i++) if (coop_ai_object(i, count, tab)) k++;
    return coop_ai_object(li, count, tab) ? k : -1;
}
static const char *aim_name(int k, char *buf) {             /* the shell's AUTO MELEE names, else "AI n" */
    HMODULE sh = GetModuleHandleA("i76shell.dll");
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
        memset(g_aim_dead_seen, 0, sizeof(g_aim_dead_seen));
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
            if (!g_aim_dead_seen[i]) { g_aim_dead_seen[i] = 1; mlog("  aimelee: AI #%d '%.8s' (label %d) died without an attacker record (collision, fall or no-owner damage) - no credit", aim_ordinal(i) + 1, (char *)o, i); }
            continue;
        }
        alive++;
        if ((j = aim_index(o)) < 0) continue;
        if (!g_aim_skilled[j] && *(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) {
            int s = g_aim_skill;
            ((void (__cdecl *)(BYTE *, int *, int *))0x0040bd90)(o, &s, &s);
            *(int *)(*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108) + 0xa818) = g_aim_skill - 1;
            g_aim_skilled[j] = 1;
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
        else if (coop_chain_num((const char *)0x005049f0)) mpf_coop_tick();   /* I76_COOP_SCALE (mpfill.c) */
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
    if (!killer || (k = aim_slot_of(killer)) < 0 || !(kc = aim_slot_car(k)) || !*(BYTE **)(kc + 0x70)) {
        mlog("  aimelee: AI #%d (label %d) destroyed, no player credited (attacker id %u)", aim_ordinal(li) + 1, li, killer);
        return;
    }
    if (g_aim_qn < 16) {
        float v = *(float *)(*(BYTE **)(victim + 0x70) + 0xa4) * *(float *)(*(BYTE **)(kc + 0x70) + 0xa8) * *(float *)0x004bdf78;
        int own = aim_team_rule() && aim_team(kc) == aim_team(victim);   /* 5. his own team's AI: no score (stock team kill) */
        g_aim_q[g_aim_qn].killer = killer; g_aim_q[g_aim_qn].li = (short)li; g_aim_q[g_aim_qn].score = own ? 0 : (int)v; g_aim_q[g_aim_qn].own = (BYTE)own;
        g_aim_qn++;
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
    ((int (__cdecl *)(short, char *))0x00454620)((short)killer, who); who[24] = 0;
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
    char line[1400];
    len = sprintf(line, "  aimelee: t %lu, %s, %.12s, ticks %ld orders %ld, AI kills %ld, AK sent %ld got %ld, credited here %ld, waves %ld; AI",
                  GetTickCount(), role == 1 ? "host" : "joiner", (char *)0x005049f0, g_aim_ticks, g_aim_orders, g_aim_kills, g_aim_ak_sent, g_aim_ak_got, g_aim_credited, g_aim_waves);
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
        if (*(WORD *)p) len += sprintf(line + len, " %u:t%d/%df%x", *(WORD *)p, (int)((*(DWORD *)(p + 0x1c) >> 16) & 7), c ? aim_team(c) : -1, (unsigned)(*(DWORD *)(p + 0x1c) & 0xffff));
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
    if (!aim_arena()) return;
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AM_PKT && !g_aim_saved) aim_save_score();
    if (role == 1 && g_aim_qn) aim_flush();
    if (!coop_ai_in_mission()) return;
    now = GetTickCount();
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
static void apply_mpfill(void);
static void apply_aimelee(void) {
    BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 }; LONG a0, a1; int ok = 0;
    if (!real_dpReceive) return;                              /* needs I76_COOP_AI=1 (the sync and the pump hook) */
    if (env_flag("I76_AIMELEE", 8, 1) == 0) { mlog("  aimelee: off (I76_AIMELEE=0)"); return; }
    g_aim_skill = env_int("I76_AIMELEE_SKILL", 8, 3); if (g_aim_skill < 1 || g_aim_skill > 5) g_aim_skill = 3;
    g_aim_cap = env_int("I76_AIMELEE_CAP", 8, 8); if (g_aim_cap < 1) g_aim_cap = 8;
    g_aim_teams = env_flag("I76_AIMELEE_TEAMS", 8, -1);     /* unset / auto: follow the session's TEAM PLAY */
    g_aim_wave = env_flag("I76_AIMELEE_WAVE", 8, 1);
    g_aim_wave_s = env_int("I76_AIMELEE_WAVE_S", 8, 8); if (g_aim_wave_s < 1) g_aim_wave_s = 8;
    g_aim_respawn = env_flag("I76_AIMELEE_RESPAWN", 8, 1);
    g_aim_test_hp = env_int("I76_AIMELEE_TEST_HP", 8, 0); if (g_aim_test_hp < 0 || g_aim_test_hp > 100) g_aim_test_hp = 0;
    a0 = (LONG)(0x00401310 - (0x0040a5d0 + 5)); a1 = (LONG)((DWORD_PTR)aim_melee_flag - (0x0040a5d0 + 5));
    memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
    ok += patch_bytes(0x0040a5d0, o5, w5, 5, "aimelee: host tick (ai_FrameTick melee test)");
    a0 = (LONG)(0x00401310 - (0x0046419d + 5)); a1 = (LONG)((DWORD_PTR)aim_kill_stub - (0x0046419d + 5));
    memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
    ok += patch_bytes(0x0046419d, o5, w5, 5, "aimelee: kill credit (entity_DamageAndKill)");
    g_aim_on = ok == 2;
    if (g_aim_on) apply_mpfill();                            /* AI fill + co-op scaling ride on the same tick site (mpfill.c) */
    mlog("  aimelee: %s (%d/2 sites) - in ai_*.lvl arenas: skill %d, attacker cap %d, teams %s, waves %s (%d s, %s), respawn %s",
         g_aim_on ? "on" : "NOT installed", ok, g_aim_skill, g_aim_cap, g_aim_teams < 0 ? "auto (rule on with TEAM PLAY)" : g_aim_teams ? "on" : "off (AI attack every human)",
         g_aim_wave ? "on" : "off", g_aim_wave_s, g_coop_chain ? "chain on" : "NEEDS I76_COOP_CHAIN=1", g_aim_respawn ? "on" : "off");
}
