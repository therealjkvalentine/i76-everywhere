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
 * I76_COOP_SCALE=0 turns it off (the copies stay parked). */
static int g_mpf_fill = -1, g_mpf_scale = 1, g_mpf_scale_max = 3, g_mpf_log, g_mpf_test;
static volatile LONG g_mpf_parks, g_mpf_acts, g_mpf_copies;
typedef struct { DWORD lo, hi, olo, ohi; BYTE kind, j; float px, pz; int li, oli; BYTE state; } mpf_tag_t;
enum { MPF_PLAY = 0, MPF_PARKED = 1, MPF_COPY_IN = 2 };
#define MPF_MAX 256
static mpf_tag_t g_mpf[MPF_MAX]; static int g_mpf_n;
static char g_mpf_mission[16]; static BYTE *g_mpf_tab; static int g_mpf_count; static int g_mpf_loaded;
static BYTE g_mpf_engaged[2048];
static BYTE *g_mpf_tgt[MPF_MAX];
static int g_mpf_humans = -1, g_mpf_humans_seen = -1; static DWORD g_mpf_humans_since, g_mpf_last_act;
static int mpf_humans_now(void) { int k, n = 0; for (k = 0; k < 16; k++) if (*(WORD *)((BYTE *)0x00541070 + k * 0x48)) n++; return n; }
static BYTE *mpf_obj(int li) { return (li >= 0 && li < g_mpf_count) ? *(BYTE **)(g_mpf_tab + li * 16 + 8) : NULL; }
static int mpf_find(DWORD lo, DWORD hi) {
    int i; for (i = 0; i < g_mpf_count; i++) if (*(DWORD *)(g_mpf_tab + i * 16) == lo && *(DWORD *)(g_mpf_tab + i * 16 + 4) == hi) return i;
    return -1;
}
static void mpf_load(void) {                                 /* the mission's tags (both roles; only the host acts) */
    const char *m = (const char *)0x005049f0; BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8);
    char path[64]; HANDLE h; DWORD sz, got = 0; BYTE *buf; DWORD p; DWORD now = GetTickCount();
    if (g_mpf_loaded && tab == g_mpf_tab && count == g_mpf_count && _strnicmp(m, g_mpf_mission, 15) == 0) return;
    g_mpf_loaded = 1; g_mpf_tab = tab; g_mpf_count = (tab && count > 0 && count <= 2048) ? count : 0; strncpy(g_mpf_mission, m, 15); g_mpf_mission[15] = 0;
    g_mpf_n = 0; memset(g_mpf_engaged, 0, sizeof(g_mpf_engaged)); memset(g_mpf_tgt, 0, sizeof(g_mpf_tgt));
    memset(g_mpf_park_since, 0, sizeof(g_mpf_park_since)); g_mpf_humans = -1; g_mpf_humans_seen = -1; g_mpf_last_act = 0;
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
    for (i = 0; i < g_mpf_count; i++) { BYTE *o = coop_ai_object(i, g_mpf_count, g_mpf_tab); if (o && aim_alive(o) && !mpf_parked_obj(o)) { double d = mpf_d2(o, x, z); if (d < best) best = d; } }
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
/* --- AI fill (host, from aim_tick) ------------------------------------------------------------------------------- */
static void mpf_fill_tick(void) {
    int i, h, pool = 0, play = 0, target, n; DWORD now = GetTickCount();
    mpf_load();
    if (!g_mpf_n || g_mpf[0].kind != 1 || g_mpf_fill == 0) return;
    if ((h = mpf_humans_stable()) < 1) return;
    if (now - g_mpf_last_act < 500) return;
    for (i = 0; i < g_mpf_n; i++) { pool++; if (g_mpf[i].state == MPF_PLAY) play++; }
    n = g_mpf_fill < 0 ? pool + 1 : g_mpf_fill;
    target = n - h; if (target < 0) target = 0; if (target > pool) target = pool;
    if (play > target) {                                     /* park the live car farthest from every human (else a wreck) */
        int pick = -1; double fd = -1;
        for (i = 0; i < g_mpf_n; i++) {
            BYTE *o = mpf_obj(g_mpf[i].li); double d;
            if (g_mpf[i].state != MPF_PLAY || !o) continue;
            d = aim_alive(o) ? mpf_near_human(o) : -0.5;
            if (d > fd) { fd = d; pick = i; }
        }
        if (pick >= 0) { char why[64]; sprintf(why, "%d humans, %d of %d AI wanted", h, target, pool); mpf_park(&g_mpf[pick], why); g_mpf_last_act = now; }
    } else if (play < target) {                              /* bring a live parked car to the freest spawn point */
        int pick = -1, s, ns = *(int *)0x00540d98, best_s = -1; double best = -1;
        for (i = 0; i < g_mpf_n; i++) if (g_mpf[i].state == MPF_PARKED && aim_alive(mpf_obj(g_mpf[i].li))) { pick = i; break; }
        if (pick < 0) return;
        for (s = 0; s < ns && s < 64; s++) {
            double x = *(double *)(0x0053fdb0 + s * 0x40), z = *(double *)(0x0053fdc0 + s * 0x40), d = mpf_near_car(x, z);
            if (d > best) { best = d; best_s = s; }
        }
        if (best_s < 0 || best < 30.0 * 30.0) return;
        {   char why[64]; sprintf(why, "%d humans, %d of %d AI wanted (spawn point %d)", h, target, pool, best_s);
            mpf_bring(&g_mpf[pick], *(double *)(0x0053fdb0 + best_s * 0x40), *(double *)(0x0053fdc0 + best_s * 0x40), rand() % 360, why); }
        g_mpf_last_act = now;
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
    k = h - 1; if (k > g_mpf_scale_max) k = g_mpf_scale_max;
    if (k > 0 && now - last >= 250) {                        /* bring copies of engaged live originals */
        last = now;
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
    len = sprintf(line, "  mpfill: t %lu, %s, %.12s, humans %d (stable %d), tagged %d: in play %d, copies in %d, parked %d; parks %ld acts %ld",
                  GetTickCount(), role == 1 ? "host" : "joiner", (char *)0x005049f0, mpf_humans_now(), g_mpf_humans, g_mpf_n, inn, cin, park, g_mpf_parks, g_mpf_acts);
    if (g_mpf_log && tab && count > 0 && count <= 2048) {
        len += sprintf(line + len, "; AI");
        for (i = 0; i < count && len < (int)sizeof(line) - 80; i++) {
            BYTE *o = coop_ai_object(i, count, tab);
            if (!o) continue;
            len += sprintf(line + len, " %d:%c%.1f,%.1f", i, mpf_parked_obj(o) ? 'p' : aim_alive(o) ? 'a' : 'd', *(double *)(o + 0x40), *(double *)(o + 0x50));
        }
        len += sprintf(line + len, "; H");
        for (k = 0; k < 16 && len < (int)sizeof(line) - 60; k++) {
            BYTE *p = (BYTE *)0x00541070 + k * 0x48, *o = aim_slot_car(k);
            if (!*(WORD *)p) continue;
            if (o) len += sprintf(line + len, " %u:%c%.1f,%.1f", *(WORD *)p, aim_alive(o) ? 'a' : 'd', *(double *)(o + 0x40), *(double *)(o + 0x50));
            else len += sprintf(line + len, " %u:-", *(WORD *)p);
        }
    }
    mlog("%s", line);
}
void mpfill_pump(int role) {                                 /* from aimelee_pump, every pump call in a network game */
    static DWORD grid;
    DWORD now;
    if (!role || !coop_ai_in_mission()) return;
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
    g_mpf_scale_max = env_int("I76_COOP_SCALE_MAX", 8, 3); if (g_mpf_scale_max < 0) g_mpf_scale_max = 0; if (g_mpf_scale_max > 8) g_mpf_scale_max = 8;
    g_mpf_log = env_flag("I76_MPF_LOG", 8, 0);
    g_mpf_test = env_flag("I76_COOP_SCALE_TEST", 8, 0);   /* LAB ONLY: treat every enemy original as engaged at load (copies come in at once) */
    mlog("  mpfill: AI fill %s, co-op scaling %s (copies per enemy up to %d joiners), car census log %s",
         g_mpf_fill < 0 ? "auto (pool + 1 combatants)" : g_mpf_fill == 0 ? "off" : "fixed", g_mpf_scale ? "on" : "off", g_mpf_scale_max, g_mpf_log ? "on" : "off");
    if (g_mpf_fill > 0) mlog("  mpfill: I76_AIMELEE_FILL=%d combatants", g_mpf_fill);
}
