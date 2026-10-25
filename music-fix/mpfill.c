/* mpfill.c - AI FILL in the AI melee arenas (I76_AIMELEE_FILL) and CO-OP SCALING (I76_COOP_SCALE): pre-spawned car
 * pools for network games, docs/records/MP-OVERNIGHT-2026-10-20.md. Included from strlkproxy.c after aimelee.c (it uses
 * coop_ai_role, coop_ai_object, coop_ai_in_mission, coop_chain_num, the aimelee tick). Needs I76_COOP_AI=1 (the 'AT'
 * sync) and the aimelee tick site (I76_AIMELEE on, its default).
 *
 * NO CAR IS CREATED AFTER LOAD. The mission file holds every car a game will ever use (tools/mp_pool.py tags them in
 * the ODEF record's 36 unused bytes: "I76P", kind, copy number, original label, parking spot). Every machine loads
 * them with the mission, so the stock load gives them to joiners and the proxy's 'AT' sync (by label-table index)
 * carries their state; the host only moves cars between their parking spot (an empty terrain tile ~8 km from the
 * mission: flat ground, beyond every draw distance and the 600 m radar) and the game:
 *   park:     fsm_TeleportOffset 0x414bc0 to the spot (the FSM 'teleport' action's own code) + ai_SetBehaviour(car, 0,
 *             0x21) = the FSM 'hide' (engine off; an engine-off car is off the radar, object_IsRadarVisible 0x466de0)
 *   activate: fsm_TeleportOffset to the place it is wanted + startCar 0x467400; the attack order follows.
 * Parked cars go into 'AT' every 2 s instead of 10 times a second.
 *
 * AI FILL (kind 1, ADDON\ai_*.lvl, host): the arena's AI cars are the pool. Target combatants N = I76_AIMELEE_FILL
 * (default: pool + 1, so a lone host meets every AI car the title names and every human beyond the first retires one;
 * 0 = off, every AI car always plays as before). AI cars in play = clamp(N - humans, 0, pool). A human joining parks
 * the live AI car farthest from every human (no damage, no kill, no score); a human leaving brings a parked one back at
 * the spawn point farthest from every car. Humans = player-table slots with an id, counted after 1.5 s without change.
 * The wave rule (aimelee.c) counts only the cars in play.
 * TEAMS (I76_AIMELEE_FILL_TEAM, default 1; acts only while aimelee.c's team rule is on, i.e. TEAM PLAY by default): the
 * pool and every AI car the arena starts with are on team 7 (Men In Black, the last row of the team popup). A human
 * leaving (his slot gone) queues his team; the AI that comes back for him moves to that team (mpf_move_team) and fights
 * for it. A human joining queues his team; the car parked for him is, in this order: a live AI of his team, a wreck of
 * his team, a live Men In Black AI, a Men In Black wreck, any other (farthest from every human within a class); a
 * parked car goes back to team 7. g_mpf_vac[t] counts the AI standing in for team t; it survives a wave reload of the
 * same arena (the reload brings every car back on team 7, and the host moves vac[t] of them back to team t). A leave
 * and a join of the same team in one human-count change cancel. I76_AIMELEE_FILL_TEAM=0: every AI stays on team 7.
 *
 * CO-OP SCALING (kind 2, ADDON\coopNN.lvl built with coop-mission.py --copies K, host): each enemy car has K parked
 * copies (team 0 in the file, so the script's allEnemyDead / isWithinEnemy, which walk teams 1..7, never count a
 * parked one; a lone host's mission is the stock one). A copy that comes in is moved from team list 0 to its
 * original's list with its team bits (mpf_move_team; the engine removes a dying object from the list of its flags'
 * team - only changing the bits left a dangling handle in list 0 and crashed the next teardown, 0x4099af, n 1), so it
 * fights as an enemy and counts like one: allEnemyDead waits for it too. Copy j comes into the game when its original is first
 * given a behaviour aimed at a human (coop_ai_attack: the original "engages") while it is alive and at least j joiners
 * are present (I76_COOP_SCALE_MAX caps j, default 3): beside the original (12 + 8 j m behind it, 6 m to a side), with
 * the original's team bits, then the same attack tick as the AI melee (nearest live human, sticky) until it dies. A
 * joiner who arrives later brings the next copy of every engaged live original; a copy in the game stays there. With
 * no joiner nothing moves: the lone host plays the stock mission (the copies sit 8 km away, engine off).
 * I76_COOP_SCALE=0 turns it off (the copies stay parked).
 *
 * HOST MIGRATION (2026-10-20, records/LAN-MATRIX-2026-10-20.md section 7). Only the host moves tagged cars and keeps
 * their state; a joiner's table keeps the file's state (fill cars "in play", copies "parked") while 'AT' moves the cars.
 * When the host leaves and this joiner becomes host, its table did not match the map: a copy the old host had brought
 * in was "parked" in it, so a copy beyond the new joiner count stayed on the map as a stray (matrix c07: Scene 5, copy 3
 * at 14382, 43598), and a fill car the old host had parked was "in play". So when a proxy that was a joiner in this
 * mission load (g_mpf_joiner_gen) acts as host, it waits until the humans count has settled and 3 s have passed, then
 * reconciles once, by position (300 m from the car's parking spot): a fill car at its spot is counted parked; a live
 * copy away from its spot is adopted (its original's team, the attack tick, as if brought in here) while its copy number
 * is within this host's joiner count (and co-op scaling is on), else parked (spot, engine off, team 0). Wrecks stay.
 * A host that never was a joiner in the mission (every game without a migration) never runs it. */
static int g_mpf_fill = -1, g_mpf_scale = 1, g_mpf_scale_max = 3, g_mpf_log, g_mpf_test, g_mpf_fill_team = 1, g_mpf_scale_near = 500;
static int g_mpf_vac[8];                                     /* AI cars in play standing in for a human of team t */
static int g_mpf_leftq[16], g_mpf_leftn, g_mpf_joinq[16], g_mpf_joinn;   /* teams of humans who left / joined, not yet served */
static WORD g_mpf_sid[16]; static BYTE g_mpf_steam[16]; static int g_mpf_snap_h = -1;   /* the humans at the last count */
static DWORD g_mpf_last_fill;
static volatile LONG g_mpf_parks, g_mpf_acts, g_mpf_copies;
typedef struct { DWORD lo, hi, olo, ohi; BYTE kind, j; float px, pz; int li, oli; BYTE state; } mpf_tag_t;
enum { MPF_PLAY = 0, MPF_PARKED = 1, MPF_COPY_IN = 2 };
#define MPF_MAX 256
static mpf_tag_t g_mpf[MPF_MAX]; static int g_mpf_n;
static char g_mpf_mission[16]; static BYTE *g_mpf_tab; static int g_mpf_count; static int g_mpf_loaded;
static BYTE g_mpf_engaged[2048];
static BYTE *g_mpf_tgt[MPF_MAX];
static int g_mpf_gen, g_mpf_joiner_gen = -1, g_mpf_migr_done; static DWORD g_mpf_migr_at;   /* host migration (above) */
static int g_mpf_humans = -1, g_mpf_humans_seen = -1; static DWORD g_mpf_humans_since, g_mpf_last_act;
static int mpf_is_human(BYTE *p) { return *(WORD *)p && !aim_is_ai_id(*(WORD *)p); }   /* a player-table slot held by a human (aimelee.c 7: AI rows) */
static int mpf_humans_now(void) { int k, n = 0; for (k = 0; k < 16; k++) if (mpf_is_human((BYTE *)0x00541070 + k * 0x48)) n++; return n; }
static BYTE *mpf_obj(int li) {                              /* NULL while the tags belong to another load: a second session in the */
    if (g_mpf_tab != *(BYTE **)(0x0054a178 + 4) || g_mpf_count != *(int *)(0x0054a178 + 8)) return NULL;   /* same process read freed */
    return (li >= 0 && li < g_mpf_count) ? *(BYTE **)(g_mpf_tab + li * 16 + 8) : NULL;                  /* memory here (polish lane) */
}
static int mpf_find(DWORD lo, DWORD hi) {
    int i; for (i = 0; i < g_mpf_count; i++) if (*(DWORD *)(g_mpf_tab + i * 16) == lo && *(DWORD *)(g_mpf_tab + i * 16 + 4) == hi) return i;
    return -1;
}
static void mpf_load(void) {                                 /* the mission's tags (both roles; only the host acts) */
    const char *m = (const char *)0x005049f0; BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8);
    char path[64]; HANDLE h; DWORD sz, got = 0; BYTE *buf; DWORD p; DWORD now = GetTickCount();
    if (g_mpf_loaded && tab == g_mpf_tab && count == g_mpf_count && _strnicmp(m, g_mpf_mission, 15) == 0) return;
    if (_strnicmp(m, g_mpf_mission, 15) != 0 || now - g_mpf_last_fill > 60000) {   /* a new arena or session: no team ledger */
        memset(g_mpf_vac, 0, sizeof(g_mpf_vac)); g_mpf_leftn = g_mpf_joinn = 0; g_mpf_snap_h = -1;
    }
    g_mpf_loaded = 1; g_mpf_tab = tab; g_mpf_count = (tab && count > 0 && count <= 2048) ? count : 0; strncpy(g_mpf_mission, m, 15); g_mpf_mission[15] = 0;
    g_mpf_gen++; g_mpf_migr_at = 0; g_mpf_migr_done = 0;    /* a new mission load: no migration in it yet */
    g_mpf_n = 0; memset(g_mpf_engaged, 0, sizeof(g_mpf_engaged)); memset(g_mpf_tgt, 0, sizeof(g_mpf_tgt));
    memset(g_mpf_park_since, 0, sizeof(g_mpf_park_since)); g_mpf_humans = -1; g_mpf_humans_seen = -1; g_mpf_last_act = 0;
    if (g_mpf_count && g_aim_inj && _strnicmp(m, g_aim_inj_m, 15) == 0) {   /* aimelee.c 8: the injected pool's tags, parked at load */
        int q;
        for (q = 0; q < g_aim_inj_cnt && g_mpf_n < MPF_MAX; q++) {
            mpf_tag_t *t = &g_mpf[g_mpf_n]; BYTE *b = g_aim_inj_body[q];
            t->lo = *(DWORD *)b; t->hi = *(DWORD *)(b + 4); t->kind = 1; t->j = 0; t->olo = t->ohi = 0;
            t->px = *(float *)(b + 72); t->pz = *(float *)(b + 76); t->li = mpf_find(t->lo, t->hi); t->oli = -1;
            if (t->li < 0) continue;
            t->state = MPF_PARKED; g_mpf_park_since[t->li] = now; g_mpf_n++;
        }
        mlog("  mpfill: '%s' - %d injected pool cars (AI fill pool, parked), role %s", m, g_mpf_n, coop_ai_role() == 1 ? "host" : "joiner");
        return;
    }
    if (!g_mpf_count || _stricmp(m + (strlen(m) > 4 ? strlen(m) - 4 : 0), ".lvl") != 0) return;
    _snprintf(path, sizeof(path) - 1, "addon\\%s", m); path[sizeof(path) - 1] = 0;
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    sz = GetFileSize(h, NULL);
    buf = (sz > 0 && sz < (8u << 20)) ? (BYTE *)malloc(sz) : NULL;
    if (buf) ReadFile(h, buf, sz, &got, NULL);
    CloseHandle(h);
    if (!buf) return;
    for (p = 0; p + 108 <= got && g_mpf_n < MPF_MAX; p++) {
        mpf_tag_t *t; BYTE *b;
        if (buf[p] != 'O' || memcmp(buf + p, "OBJ\0", 4) || *(DWORD *)(buf + p + 4) != 108 || memcmp(buf + p + 8 + 56, "I76P", 4)) continue;
        b = buf + p + 8; t = &g_mpf[g_mpf_n];
        t->lo = *(DWORD *)b; t->hi = *(DWORD *)(b + 4); t->kind = b[60]; t->j = b[61];
        t->olo = *(DWORD *)(b + 64); t->ohi = *(DWORD *)(b + 68); t->px = *(float *)(b + 72); t->pz = *(float *)(b + 76);
        t->li = mpf_find(t->lo, t->hi); t->oli = t->kind == 2 ? mpf_find(t->olo, t->ohi) : -1;
        if (t->li < 0 || (t->kind == 2 && t->oli < 0)) continue;
        t->state = t->kind == 2 ? MPF_PARKED : MPF_PLAY;
        if (t->state == MPF_PARKED) g_mpf_park_since[t->li] = now;
        g_mpf_n++; p += 107;
    }
    free(buf);
    if (g_mpf_test) { int i; for (i = 0; i < g_mpf_n; i++) if (g_mpf[i].kind == 2) g_mpf_engaged[g_mpf[i].oli] = 1; }   /* LAB: every original engaged */
    if (g_mpf_n) mlog("  mpfill: '%s' - %d tagged cars (%s), role %s", m, g_mpf_n, g_mpf[0].kind == 1 ? "AI fill pool" : "co-op copies",
                      coop_ai_role() == 1 ? "host" : "joiner");
}
static int mpf_parked_obj(BYTE *o) {                         /* aimelee.c: a car out of the game */
    int i; for (i = 0; i < g_mpf_n; i++) if (g_mpf[i].state == MPF_PARKED && mpf_obj(g_mpf[i].li) == o) return 1;
    return 0;
}
static void mpf_teleport(BYTE *o, double x, double z, int hdg) {   /* the FSM teleport (speed 0) to x, z on the ground */
    BYTE path[0x58]; float node[3]; int spd = 0;
    memset(path, 0, sizeof(path)); node[0] = (float)x; node[1] = 0.0f; node[2] = (float)z;
    *(float **)(path + 0x54) = node;
    hdg %= 360; if (hdg < 0) hdg += 360;
    ((void (__cdecl *)(BYTE *, BYTE *, int *, int *, int *, int *))0x00414bc0)(o, path, &spd, &hdg, NULL, NULL);
}
static int mpf_heading(BYTE *o) {                            /* object rotation rows at +0x18: forward = row 2 */
    float fx = *(float *)(o + 0x18 + 24), fz = *(float *)(o + 0x18 + 32);
    return (int)(atan2(fx, fz) * 57.29578);
}
static void mpf_park(mpf_tag_t *t, const char *why) {
    BYTE *o = mpf_obj(t->li);
    if (!o) return;
    if (aim_alive(o)) {
        mpf_teleport(o, t->px, t->pz, 0);
        if (*(BYTE **)(o + 0x70) && *(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) ((int (__cdecl *)(BYTE *, BYTE *, int))0x00412830)(o, NULL, 0x21);
    }
    t->state = MPF_PARKED; g_mpf_park_since[t->li] = GetTickCount(); g_mpf_parks++;
    mlog("  mpfill: parked '%.8s' (label %d, %s) at %.0f,%.0f - %s", (char *)o, t->li, aim_alive(o) ? "live" : "wreck", t->px, t->pz, why);
}
static void mpf_bring(mpf_tag_t *t, double x, double z, int hdg, const char *why) {
    BYTE *o = mpf_obj(t->li);
    if (!o) return;
    mpf_teleport(o, x, z, hdg);
    ((void (__cdecl *)(BYTE *))0x00467400)(o);               /* startCar */
    t->state = t->kind == 2 ? MPF_COPY_IN : MPF_PLAY; g_mpf_park_since[t->li] = 0; g_mpf_acts++;
    mlog("  mpfill: '%.8s' (label %d) into the game at %.1f,%.1f heading %d - %s", (char *)o, t->li, x, z, hdg, why);
}
static int mpf_move_team(BYTE *o, DWORD team) {             /* team lists 0x507da0 + t*0x100 (64 handles), counts 0x51f5d0 + t*4 */
    DWORD cur = (*(DWORD *)(o + 0x10) >> 16) & 7; int *cnt0 = (int *)(0x0051f5d0 + cur * 4), *cnt1 = (int *)(0x0051f5d0 + team * 4), i;
    BYTE ***l0 = (BYTE ***)(0x00507da0 + cur * 0x100), ***l1 = (BYTE ***)(0x00507da0 + team * 0x100);
    if (team == cur) return 1;
    if (*cnt1 >= 64) return 0;
    for (i = 0; i < *cnt0 && i < 64; i++) if (l0[i] && *l0[i] == o) break;
    if (i >= *cnt0 || i >= 64) return 0;                     /* not in its flags' list: leave everything as it is */
    l1[(*cnt1)++] = l0[i];                                   /* the same handle, moved: entity removal looks in the list of the flags' team */
    l0[i] = l0[*cnt0 - 1]; (*cnt0)--;
    *(DWORD *)(o + 0x10) = (*(DWORD *)(o + 0x10) & ~0x70000u) | (team << 16);
    return 1;
}
static double mpf_d2(BYTE *a, double x, double z) { double dx = *(double *)(a + 0x40) - x, dz = *(double *)(a + 0x50) - z; return dx * dx + dz * dz; }
static double mpf_near_car(double x, double z) {             /* squared distance to the nearest live car in the game */
    double best = 1e30; int k, i;
    for (k = 0; k < 16; k++) { BYTE *h = aim_slot_car(k); if (h && aim_alive(h)) { double d = mpf_d2(h, x, z); if (d < best) best = d; } }
    {   BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8);   /* the current table (never the tags' copy) */
        for (i = 0; tab && count <= 2048 && i < count; i++) { BYTE *o = coop_ai_object(i, count, tab); if (o && aim_alive(o) && !mpf_parked_obj(o)) { double d = mpf_d2(o, x, z); if (d < best) best = d; } } }
    return best;
}
static double mpf_near_human(BYTE *o) {
    double best = 1e30; int k;
    for (k = 0; k < 16; k++) { BYTE *h = aim_slot_car(k); if (h && aim_alive(h)) { double d = mpf_d2(h, *(double *)(o + 0x40), *(double *)(o + 0x50)); if (d < best) best = d; } }
    return best;
}
static int mpf_humans_stable(void) {                         /* humans, once unchanged for 1.5 s; -1 before */
    int h = mpf_humans_now(); DWORD now = GetTickCount();
    if (h != g_mpf_humans_seen) { g_mpf_humans_seen = h; g_mpf_humans_since = now; }
    if (now - g_mpf_humans_since >= 1500 && h != g_mpf_humans) {
        if (g_mpf_humans >= 0) mlog("  mpfill: humans %d -> %d", g_mpf_humans, h);
        g_mpf_humans = h;
    }
    return g_mpf_humans;
}
/* --- host migration: reconcile the table with the map once (header) ------------------------------------------- */
static int mpf_migr_pending(int h) {                         /* 1 while the reconcile still waits (the caller then holds) */
    DWORD now = GetTickCount(); int i, k, adopt = 0, park = 0, fix = 0;
    if (g_mpf_joiner_gen != g_mpf_gen || g_mpf_migr_done || !g_mpf_n) return 0;
    if (!g_mpf_migr_at) {
        g_mpf_migr_at = now | 1;
        mlog("  mpfill: host migration - this machine was a joiner in '%s' and is the host now; reconciling the %d tagged cars once the humans count has settled",
             g_mpf_mission, g_mpf_n);
        return 1;
    }
    if (now - g_mpf_migr_at < 3000 || h < 1) return 1;
    g_mpf_migr_done = 1;
    k = h - 1; if (k > g_mpf_scale_max) k = g_mpf_scale_max;
    for (i = 0; i < g_mpf_n; i++) {
        mpf_tag_t *t = &g_mpf[i]; BYTE *o = mpf_obj(t->li), *orig; double d;
        if (!o) continue;
        d = mpf_d2(o, t->px, t->pz);
        if (t->kind == 1) {                                  /* fill car the old host had parked */
            if (t->state == MPF_PLAY && (d < 300.0 * 300.0 || (g_aim_at_flags[t->li] & 0xC0) == 0xC0)) {
                t->state = MPF_PARKED; g_mpf_park_since[t->li] = now; fix++;
                mlog("  mpfill: host migration - '%.8s' (label %d) is at its parking spot: counted parked", (char *)o, t->li);
            }
            continue;
        }
        if (t->state != MPF_PARKED || d < 300.0 * 300.0 || !aim_alive(o)) continue;
        orig = mpf_obj(t->oli);
        if (g_mpf_scale && t->j <= k && orig && mpf_move_team(o, (*(DWORD *)(orig + 0x10) >> 16) & 7)) {
            t->state = MPF_COPY_IN; g_mpf_park_since[t->li] = 0; adopt++;
            mlog("  mpfill: host migration - copy %d '%.8s' (label %d) at %.0f,%.0f stays in the game (%d joiner(s)), team %d",
                 t->j, (char *)o, t->li, *(double *)(o + 0x40), *(double *)(o + 0x50), h - 1, aim_team(o));
        } else {
            char why[96];
            sprintf(why, "host migration: copy %d, %d joiner(s) here, was at %.0f,%.0f", t->j, h - 1, *(double *)(o + 0x40), *(double *)(o + 0x50));
            mpf_park(t, why); mpf_move_team(o, 0); park++;
        }
    }
    mlog("  mpfill: host migration - reconciled: %d fill car(s) counted parked, %d copy(ies) kept in, %d copy(ies) re-parked (%d humans)", fix, adopt, park, h);
    return 0;
}
/* --- AI fill (host, from aim_tick) ------------------------------------------------------------------------------- */
static int mpf_team_rule(void) { return g_mpf_fill_team && aim_team_rule(); }
static DWORD g_mpf_tsig, g_mpf_tsig_since;
static DWORD mpf_team_sig(void) {                            /* every slot's id and team: a new slot can read team 0 for a moment */
    DWORD s = 0; int k;                                      /* (measured: a joiner's slot first shows flags 0x1, team 0, then 0x2 + */
    for (k = 0; k < 16; k++) {                               /*  his team: 0x4541b0 sets bit 1 only when it read the team from ANet) */
        BYTE *p = (BYTE *)0x00541070 + k * 0x48; DWORD f = *(DWORD *)(p + 0x1c);
        if (mpf_is_human(p)) s = s * 31 + *(WORD *)p * 16 + ((f >> 16) & 7) * 2 + ((f >> 1) & 1);
    }
    return s;
}
static int mpf_teams_read(void) {                            /* every slot's team came from its player data (flags bit 1) */
    int k; for (k = 0; k < 16; k++) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; if (mpf_is_human(p) && !(*(DWORD *)(p + 0x1c) & 2)) return 0; }
    return 1;
}
static void mpf_team_refresh(void) {                         /* a known player's team changed (e.g. his slot read team 0 first) */
    int k, j;
    for (k = 0; k < 16; k++) {
        BYTE *p = (BYTE *)0x00541070 + k * 0x48; BYTE t = (BYTE)((*(DWORD *)(p + 0x1c) >> 16) & 7);
        if (!mpf_is_human(p)) continue;
        for (j = 0; j < g_mpf_snap_h; j++) if (g_mpf_sid[j] == *(WORD *)p && g_mpf_steam[j] != t) {
            mlog("  mpfill: teams - player %u now reads team %d (was %d)", g_mpf_sid[j], t, g_mpf_steam[j]); g_mpf_steam[j] = t;
        }
    }
}
static void mpf_q_pop(int *q, int *n) { if (*n > 0) { memmove(q, q + 1, (*n - 1) * sizeof(int)); (*n)--; } }
static void mpf_team_diff(void) {                            /* who left / joined since the last count, with their teams */
    WORD id[16]; BYTE tm[16]; int k, j, n = 0;
    for (k = 0; k < 16; k++) {
        BYTE *p = (BYTE *)0x00541070 + k * 0x48;
        if (mpf_is_human(p)) { id[n] = *(WORD *)p; tm[n] = (BYTE)((*(DWORD *)(p + 0x1c) >> 16) & 7); n++; }
    }
    if (g_mpf_snap_h >= 0) {
        for (j = 0; j < g_mpf_snap_h; j++) {
            for (k = 0; k < n && id[k] != g_mpf_sid[j]; k++) ;
            if (k == n && g_mpf_leftn < 16) { g_mpf_leftq[g_mpf_leftn++] = g_mpf_steam[j]; mlog("  mpfill: teams - player %u (team %d) left", g_mpf_sid[j], g_mpf_steam[j]); }
        }
        for (k = 0; k < n; k++) {
            for (j = 0; j < g_mpf_snap_h && g_mpf_sid[j] != id[k]; j++) ;
            if (j < g_mpf_snap_h) continue;
            for (j = 0; j < g_mpf_leftn && g_mpf_leftq[j] != tm[k]; j++) ;
            if (j < g_mpf_leftn) {                           /* he takes the place of a leaver of his team: nothing moves */
                memmove(g_mpf_leftq + j, g_mpf_leftq + j + 1, (g_mpf_leftn - j - 1) * sizeof(int)); g_mpf_leftn--;
                mlog("  mpfill: teams - player %u joined team %d in place of a leaver of that team", id[k], tm[k]);
            } else if (g_mpf_joinn < 16) { g_mpf_joinq[g_mpf_joinn++] = tm[k]; mlog("  mpfill: teams - player %u joined team %d", id[k], tm[k]); }
        }
    }
    memcpy(g_mpf_sid, id, sizeof(id)); memcpy(g_mpf_steam, tm, sizeof(tm)); g_mpf_snap_h = n;
}
static void mpf_fill_tick(void) {
    int i, h, pool = 0, play = 0, target, n, rule; DWORD now = GetTickCount();
    mpf_load();
    if (!g_mpf_n || g_mpf[0].kind != 1 || g_mpf_fill == 0) return;
    g_mpf_last_fill = now;
    if ((h = mpf_humans_stable()) < 1) return;
    if (mpf_migr_pending(h)) return;
    rule = mpf_team_rule();
    if (rule) {                                              /* act on teams only once every slot's team has held for 3 s */
        DWORD sig = mpf_team_sig();
        if (sig != g_mpf_tsig) { g_mpf_tsig = sig; g_mpf_tsig_since = now; }
        if (now - g_mpf_tsig_since < 3000 || (!mpf_teams_read() && now - g_mpf_tsig_since < 15000)) return;
        mpf_team_refresh();
        if (h != g_mpf_snap_h) mpf_team_diff();
    }
    if (now - g_mpf_last_act < 500) return;
    for (i = 0; i < g_mpf_n; i++) { pool++; if (g_mpf[i].state == MPF_PLAY) play++; }
    n = g_mpf_fill >= 0 ? g_mpf_fill : (g_aim_inj && aim_drivers()) ? aim_drivers() : pool + 1;   /* injected arena: NO. DRIVERS */
    {   static BYTE hid[2048]; static BYTE *hob[2048];          /* a parked car that was never hidden (the injected pool): engine off once */
        for (i = 0; i < g_mpf_n; i++) {
            BYTE *o = mpf_obj(g_mpf[i].li); int li = g_mpf[i].li;
            if (g_mpf[i].state != MPF_PARKED || !o || (hid[li] && hob[li] == o) || !aim_alive(o) || !*(BYTE **)(o + 0x70) || !*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) continue;
            ((int (__cdecl *)(BYTE *, BYTE *, int))0x00412830)(o, NULL, 0x21); hid[li] = 1; hob[li] = o;
        }
    }
    target = n - h; if (target < 0) target = 0; if (target > pool) target = pool;
    if (play > target) {                                     /* park the live car farthest from every human (else a wreck) */
        int pick = -1, best_rank = 99, want = rule && g_mpf_joinn ? g_mpf_joinq[0] : -1; double fd = -1;
        for (i = 0; i < g_mpf_n; i++) {
            BYTE *o = mpf_obj(g_mpf[i].li); double d; int rank = 0;
            if (g_mpf[i].state != MPF_PLAY || !o) continue;
            d = aim_alive(o) ? mpf_near_human(o) : g_aim_respawn_ai ? 1e31 : -0.5;   /* with AI respawn a wreck goes first */
            if (rule) { int t = aim_team(o); rank = (t == want ? 0 : t == AIM_LAST_TEAM ? 2 : 4) + ((aim_alive(o) != 0) == (g_aim_respawn_ai == 0) ? 0 : 1); }   /* teams: his team's AI first */
            if (rank < best_rank || (rank == best_rank && d > fd)) { best_rank = rank; fd = d; pick = i; }
        }
        if (pick >= 0) {
            BYTE *o = mpf_obj(g_mpf[pick].li); int t = aim_team(o); char why[96];
            if (rule) sprintf(why, "%d humans, %d of %d AI wanted; team %d joined, this car is team %d", h, target, pool, want, t);
            else sprintf(why, "%d humans, %d of %d AI wanted", h, target, pool);
            mpf_park(&g_mpf[pick], why); g_mpf_last_act = now;
            if (rule) {
                if (t != AIM_LAST_TEAM && g_mpf_vac[t] > 0) g_mpf_vac[t]--;
                if (t != AIM_LAST_TEAM && aim_alive(o) && mpf_move_team(o, AIM_LAST_TEAM)) mlog("  mpfill: teams - parked '%.8s' back to team %d (pool)", (char *)o, AIM_LAST_TEAM);
                mpf_q_pop(g_mpf_joinq, &g_mpf_joinn);
            }
        }
    } else if (play < target) {                              /* bring a live parked car to the freest spawn point */
        int pick = -1, s, ns = *(int *)0x00540d98, best_s = -1, team = AIM_LAST_TEAM; double best = -1;
        for (i = 0; i < g_mpf_n; i++) if (g_mpf[i].state == MPF_PARKED && aim_alive(mpf_obj(g_mpf[i].li))) { pick = i; break; }
        if (pick < 0 && g_aim_respawn_ai) for (i = 0; i < g_mpf_n; i++) if (g_mpf[i].state == MPF_PARKED && mpf_obj(g_mpf[i].li)) { pick = i; break; }   /* a parked wreck: respawned below */
        if (pick < 0) return;
        for (s = 0; s < ns && s < 64; s++) {
            double x = *(double *)(0x0053fdb0 + s * 0x40), z = *(double *)(0x0053fdc0 + s * 0x40), d = mpf_near_car(x, z);
            if (d > best) { best = d; best_s = s; }
        }
        if (best_s < 0 || best < 30.0 * 30.0) return;
        if (!aim_alive(mpf_obj(g_mpf[pick].li))) {           /* AI respawn: a fresh car for the parked wreck, at that spawn point */
            if (!aim_recreate(g_mpf[pick].li, best_s, "the fill brings a parked wreck back")) return;
            g_mpf[pick].state = MPF_PLAY; g_mpf_park_since[g_mpf[pick].li] = 0; g_mpf_acts++; g_mpf_last_act = now;
            if (rule && g_mpf_leftn) { BYTE *o = mpf_obj(g_mpf[pick].li); if (mpf_move_team(o, (DWORD)g_mpf_leftq[0]) && g_mpf_leftq[0] != AIM_LAST_TEAM) g_mpf_vac[g_mpf_leftq[0]]++; mpf_q_pop(g_mpf_leftq, &g_mpf_leftn); }
            return;
        }
        if (rule && g_mpf_leftn) team = g_mpf_leftq[0];      /* teams: the AI takes the leaver's team */
        if (rule && team != AIM_LAST_TEAM) {
            BYTE *o = mpf_obj(g_mpf[pick].li);
            if (mpf_move_team(o, (DWORD)team)) g_mpf_vac[team]++;
            else { mlog("  mpfill: teams - '%.8s' not in its team list, stays on team %d", (char *)o, aim_team(o)); team = aim_team(o); }
        }
        {   char why[96];
            if (rule) sprintf(why, "%d humans, %d of %d AI wanted (spawn point %d), team %d", h, target, pool, best_s, team);
            else sprintf(why, "%d humans, %d of %d AI wanted (spawn point %d)", h, target, pool, best_s);
            mpf_bring(&g_mpf[pick], *(double *)(0x0053fdb0 + best_s * 0x40), *(double *)(0x0053fdc0 + best_s * 0x40), rand() % 360, why); }
        if (rule) mpf_q_pop(g_mpf_leftq, &g_mpf_leftn);
        g_mpf_last_act = now;
    } else if (rule) {                                       /* settled: stale queues go; the team ledger is restored */
        int cnt[8], t;
        g_mpf_leftn = g_mpf_joinn = 0;
        memset(cnt, 0, sizeof(cnt));
        for (i = 0; i < g_mpf_n; i++) { BYTE *o = mpf_obj(g_mpf[i].li); if (g_mpf[i].state == MPF_PLAY && o) cnt[aim_team(o)]++; }
        for (t = 0; t < 8; t++) if (t != AIM_LAST_TEAM && cnt[t] < g_mpf_vac[t]) {   /* e.g. after a wave reload: every car is back on team 7 */
            for (i = 0; i < g_mpf_n; i++) {
                BYTE *o = mpf_obj(g_mpf[i].li);
                if (g_mpf[i].state != MPF_PLAY || !o || !aim_alive(o) || aim_team(o) != AIM_LAST_TEAM) continue;
                if (mpf_move_team(o, (DWORD)t)) { mlog("  mpfill: teams - '%.8s' (label %d) back on team %d (it stands in for a team-%d human; %d of %d)", (char *)o, g_mpf[i].li, t, t, cnt[t] + 1, g_mpf_vac[t]); g_mpf_last_act = now; }
                break;
            }
            if (i < g_mpf_n) break;                          /* one move per tick */
        }
    }
}
/* --- co-op scaling (host, every frame from the ai_FrameTick site) ------------------------------------------------- */
static void mpf_engaged(BYTE *a) {                           /* coop_ai_attack: a behaviour aimed at a human (host) */
    int i;
    if (!g_mpf_scale) return;
    mpf_load();                                              /* never a stale table across a reload */
    if (!g_mpf_n) return;
    for (i = 0; i < g_mpf_n; i++) if (g_mpf[i].kind == 2 && mpf_obj(g_mpf[i].oli) == a) { g_mpf_engaged[g_mpf[i].oli] = 1; return; }
}
static void mpf_coop_tick(void) {
    int i, h, k; DWORD now = GetTickCount(); static DWORD last;
    mpf_load();
    if (!g_mpf_n || g_mpf[0].kind != 2 || !g_mpf_scale) return;
    h = mpf_humans_stable();
    if (mpf_migr_pending(h)) return;
    k = h - 1; if (k > g_mpf_scale_max) k = g_mpf_scale_max;
    if (k > 0 && now - last >= 250) {                        /* bring copies of engaged live originals */
        last = now;
        /* 2026-10-24 (owner: extra enemies seemed to come only for some of them; lab: Oil Well Well 1 copy of 24 in 90 s,
         * Scene 5 1 of 39): an original also counts as engaged once a live human is within I76_COOP_SCALE_NEAR m
         * (default 500; 0 = only the behaviour rule) - an enemy the humans meet brings its copies whatever its script does */
        if (g_mpf_scale_near > 0)
            for (i = 0; i < g_mpf_n; i++) {
                mpf_tag_t *t = &g_mpf[i]; BYTE *orig = t->kind == 2 ? mpf_obj(t->oli) : NULL;
                if (!orig || g_mpf_engaged[t->oli] || !aim_alive(orig) || mpf_parked_obj(orig)) continue;
                if (mpf_near_human(orig) < (double)g_mpf_scale_near * g_mpf_scale_near) {
                    g_mpf_engaged[t->oli] = 1;
                    mlog("  mpfill: '%.8s' (label %d) engaged - a human within %d m", (char *)orig, t->oli, g_mpf_scale_near);
                }
            }
        for (i = 0; i < g_mpf_n; i++) {
            mpf_tag_t *t = &g_mpf[i]; BYTE *o = mpf_obj(t->li), *orig = mpf_obj(t->oli);
            if (t->state != MPF_PARKED || t->j > k || !o || !orig || !g_mpf_engaged[t->oli] || !aim_alive(orig) || !aim_alive(o) || mpf_parked_obj(orig)) continue;
            {   int hd = mpf_heading(orig); double r = hd / 57.29578, back = 12.0 + 8.0 * t->j, side = (t->j & 1) ? 6.0 : -6.0;
                double x = *(double *)(orig + 0x40) - sin(r) * back + cos(r) * side, z = *(double *)(orig + 0x50) - cos(r) * back - sin(r) * side;
                char why[64];
                if (!mpf_move_team(o, (*(DWORD *)(orig + 0x10) >> 16) & 7)) { t->state = MPF_COPY_IN + 1; mlog("  mpfill: copy '%.8s' (label %d) not in its team list - left parked", (char *)o, t->li); break; }
                sprintf(why, "copy %d of '%.8s' (label %d), %d joiner(s)", t->j, (char *)orig, t->oli, h - 1);
                mpf_bring(t, x, z, hd, why); g_mpf_copies++;
            }
            break;                                           /* one per 250 ms */
        }
    }
    for (i = 0; i < g_mpf_n; i++) {                          /* the copies in the game attack the nearest live human */
        mpf_tag_t *t = &g_mpf[i]; BYTE *o = mpf_obj(t->li), *best = NULL, *cur = g_mpf_tgt[i]; double bd = 1e30, cd = 1e30; int s;
        if (t->state != MPF_COPY_IN || !o || !aim_alive(o) || !*(BYTE **)(o + 0x70) || !*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108)) continue;
        for (s = 0; s < 16; s++) {
            BYTE *hc = aim_slot_car(s); double d;
            if (!hc || !aim_alive(hc)) continue;
            d = mpf_d2(hc, *(double *)(o + 0x40), *(double *)(o + 0x50));
            if (hc == cur) cd = d;
            if (d < bd) { bd = d; best = hc; }
        }
        if (!best) continue;
        if (cur && cd < 1e29 && bd > 0.64 * cd) best = cur;
        g_mpf_tgt[i] = best;
        ((int (__cdecl *)(BYTE *, BYTE *, int))0x00412830)(o, best, 0);
    }
}
/* --- status line (both roles, 5 s wall-clock grid): every AI car with position, every human (desync checks) -------- */
static void mpf_status(int role) {
    char line[4096]; int len, i, k, inn = 0, park = 0, cin = 0;
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8);
    mpf_load();
    for (i = 0; i < g_mpf_n; i++) { if (g_mpf[i].state == MPF_PARKED) park++; else if (g_mpf[i].state == MPF_COPY_IN) cin++; else inn++; }
    len = sprintf(line, "  mpfill: t %lu, %s, %.12s, humans %d (stable %d), tagged %d: in play %d, copies in %d, parked %d; parks %ld acts %ld; teams rule %d vac %d%d%d%d%d%d%d q %d/%d",
                  GetTickCount(), role == 1 ? "host" : "joiner", (char *)0x005049f0, mpf_humans_now(), g_mpf_humans, g_mpf_n, inn, cin, park, g_mpf_parks, g_mpf_acts,
                  mpf_team_rule(), g_mpf_vac[0], g_mpf_vac[1], g_mpf_vac[2], g_mpf_vac[3], g_mpf_vac[4], g_mpf_vac[5], g_mpf_vac[6], g_mpf_leftn, g_mpf_joinn);
    if (g_mpf_log && tab && count > 0 && count <= 2048) {
        len += sprintf(line + len, "; AI");
        for (i = 0; i < count && len < (int)sizeof(line) - 80; i++) {
            BYTE *o = coop_ai_object(i, count, tab);
            if (!o) continue;
            len += sprintf(line + len, " %d:%c%.1f,%.1f/t%d", i, mpf_parked_obj(o) ? 'p' : aim_alive(o) ? 'a' : 'd', *(double *)(o + 0x40), *(double *)(o + 0x50), aim_team(o));
        }
        len += sprintf(line + len, "; H");
        for (k = 0; k < 16 && len < (int)sizeof(line) - 60; k++) {
            BYTE *p = (BYTE *)0x00541070 + k * 0x48, *o = aim_slot_car(k);
            if (!mpf_is_human(p)) continue;
            if (o) len += sprintf(line + len, " %u:%c%.1f,%.1f/t%d", *(WORD *)p, aim_alive(o) ? 'a' : 'd', *(double *)(o + 0x40), *(double *)(o + 0x50), aim_team(o));
            else len += sprintf(line + len, " %u:-", *(WORD *)p);
        }
    }
    mlog("%s", line);
}
void mpfill_pump(int role) {                                 /* from aimelee_pump, every pump call in a network game */
    static DWORD grid;
    DWORD now;
    if (!role || !coop_ai_in_mission()) return;
    if (role == 2) { mpf_load(); g_mpf_joiner_gen = g_mpf_gen; }   /* a joiner in this load: if it turns host, reconcile */
    now = GetTickCount();
    if (now / 5000 != grid) {
        grid = now / 5000;
        mpf_load();
        if (g_mpf_n || g_mpf_log) mpf_status(role);
    }
}
static void apply_mpfill(void) {
    char v[16];
    g_mpf_fill = -1;
    if (GetEnvironmentVariableA("I76_AIMELEE_FILL", v, sizeof(v)) && v[0] && _stricmp(v, "auto") != 0) g_mpf_fill = atoi(v);
    g_mpf_scale = env_flag("I76_COOP_SCALE", 8, 1);
    g_mpf_scale_near = env_int("I76_COOP_SCALE_NEAR", 8, 500); if (g_mpf_scale_near < 0) g_mpf_scale_near = 0;
    g_mpf_scale_max = env_int("I76_COOP_SCALE_MAX", 8, 3); if (g_mpf_scale_max < 0) g_mpf_scale_max = 0; if (g_mpf_scale_max > 8) g_mpf_scale_max = 8;
    g_mpf_log = env_flag("I76_MPF_LOG", 8, 0);
    g_mpf_test = env_flag("I76_COOP_SCALE_TEST", 8, 0);
    g_mpf_fill_team = env_flag("I76_AIMELEE_FILL_TEAM", 8, 1);   /* teams: a returning AI takes the leaver's team (with the team rule) */   /* LAB ONLY: treat every enemy original as engaged at load (copies come in at once) */
    mlog("  mpfill: AI fill %s, co-op scaling %s (copies per enemy up to %d joiners), car census log %s, fill teams %s",
         g_mpf_fill < 0 ? "auto (pool + 1 combatants)" : g_mpf_fill == 0 ? "off" : "fixed", g_mpf_scale ? "on" : "off", g_mpf_scale_max, g_mpf_log ? "on" : "off",
         g_mpf_fill_team ? "on (with the team rule: a returning AI takes the leaver's team)" : "off (AI stay on team 7)");
    if (g_mpf_fill > 0) mlog("  mpfill: I76_AIMELEE_FILL=%d combatants", g_mpf_fill);
}
