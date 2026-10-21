/* nitro_mp.c - ARENA+ on Nitro: the ANet 2 layer (nitro-mp-design lane, 2026-10-21; estimate item 3).
 * Record: docs/records/NITRO-MP-DESIGN-2026-10-21.md (section 0 = ARENA+, 0.5.x = proofs, 1 = the ANet 2 map).
 * RE notes: i76-map nitro-net\README.md (exe, nitshell, anet2 real code).
 *
 * BUILT ON the nitro-port lane's site table (sites_nitro.h, read-only here): every exe address below is the Gold address
 * looked up there, and the looked-up Nitro value must equal the one this lane read (nmp_site), else the feature is off.
 * Addresses outside that table carry their own byte signature (nmp_sig).
 *
 * HOW IT IS INCLUDED. Two hosts, one source:
 *   - the proxy (strlkproxy.c, after nitro.c): NMP_IN_PROXY defined by the includer; logging = mlog, IAT = patch_iat.
 *     NOT INCLUDED YET (strlkproxy.c is shared; the one #include + the two calls below are the integration step).
 *   - the lab instrument nmpdrv (i76-uncap-lab tools\nitro-mp\nmpdrv): defines NMP_LOG / NMP_IAT and includes this file
 *     and sites_nitro.h; that is how sections 0.5.4 of the record were measured.
 * Entry points: nmp_attach_exe() (DllMain, nitro.exe only), nmp_attach_shell(nitshell) (when nitshell.dll is mapped),
 * nmp_status(tag) (read-back line).
 *
 * WHAT IT DOES (and nothing else; the entity features - AI fill, rows, respawn - come on top, record s.3.1):
 *   1. RECEIVE: nitro.exe's import ANET2.DLL!dpReceive -> nmp_dpReceive: the real call first, then (pump-driven, like
 *      Gold's coop_dpReceive) our tick and our packets. nitro's pump 0x448d80 drops unknown tags itself; anet2 hands every
 *      packet whose first byte is not 'd' to the game (anet2 0x020fa420), so our tags ('A?') arrive.
 *   2. SEND: nmp_send(): payload <= 249 B unreliable / 244 B reliable (anet2 0x020ff500 / 0x020ff600 refuse len+6 > 255 /
 *      250), copied into a buffer with 16 spare bytes (dpSend writes a 6-byte trailer past the payload, in place).
 *      Reliable (flag 1) for 'AH' hello, 'AK' kill, 'AM' reload; unreliable for 'AT' AI state, 2 records per packet max.
 *   3. MODE: the session's ANet species decides: 0x7676 = ARENA+ (record s.0.5.2), 604 = stock. Taken from nitshell's
 *      dpOpen (host: the record it creates; joiner: the record it joins). In a stock session nothing below sends or acts.
 *   4. HELLO: in an ARENA+ session the host sends 'AH' {u16 'AH', u8 seq, u8 proto, u16 species, u16 sender id, u32
 *      options} (reliable, to the game group) whenever the player count changed and until every joiner answered; a joiner
 *      answers each new seq with its own 'AH' to the host.
 *   5. AI STATE 'AT' {u16 'AT', u8 0, u8 n<=2, float time, n x {u16 label, u8 fire, u8 team, record[0x60]}} (Gold's
 *      format). Lab proof only (NMP_AT_SELFTEST=1): after the hello each side sends one 'AT' with its OWN car (label
 *      0xFFFF, packed by net_PackVehicleState) and the receiver compares it with its mirror of that car.
 *   6. LIST (nitshell): one dpEnumSessions with species 0 (= any, anet2 0x020f8a20), the stdcall callback filtered to 604
 *      and 0x7676, ours shown as "ARENA+ <name>".
 *   7. LOBBY: nmp_lobby_subscribe() is a STUB (record s.0.5.3): on a game server the client subscribes to the session
 *      table per species (anet2 0x020f6480, key {table, species}); listing ARENA+ sessions there needs the same
 *      subscription for 0x7676. Not called.
 * NOT HERE YET: the ARENA+ check boxes on the host form (record s.0.3, hooks F1-F6; proven in the lab instrument's
 * arena_poc.c, record s.0.5.1) and the entity features (s.3.1).
 */
#include <math.h>
#ifndef NMP_LOG
#define NMP_LOG mlog
#endif
#ifndef NMP_IAT
#define NMP_IAT(m, d, f, n) patch_iat((m), (d), (f), (n))
#endif

#define NMP_SPECIES_ARENA 0x7676
#define NMP_SPECIES_STOCK 0x025c
#define NMP_PROTO 1
#define NMP_TAG_AH 0x4841      /* 'AH' (low byte first, as dppt_MAKE) */
#define NMP_TAG_AT 0x5441      /* 'AT' */
#define NMP_TAG_AK 0x4b41      /* 'AK' (reserved: kill credit) */
#define NMP_TAG_AM 0x4d41      /* 'AM' (reserved: reload / next scene) */
#define NMP_MAX_UNREL 249
#define NMP_MAX_REL 244
#define NMP_SLACK 16

/* ---- sites (Gold -> Nitro through sites_nitro.h; the value this lane read must match) ---- */
static DWORD nmp_lookup(DWORD gold) {
    int lo = 0, hi = (int)(sizeof(g_nitro_sites) / sizeof(g_nitro_sites[0])) - 1;
    while (lo <= hi) { int m = (lo + hi) / 2; if (g_nitro_sites[m].gold == gold) return g_nitro_sites[m].nitro; if (g_nitro_sites[m].gold < gold) lo = m + 1; else hi = m - 1; }
    return 0;
}
static int nmp_site(DWORD gold, DWORD want, const char *what, DWORD *out) {
    DWORD n = nmp_lookup(gold);
    *out = n;
    if (n != want) { NMP_LOG("  nitro-mp: site %s gold 0x%06lx -> table 0x%06lx, expected 0x%06lx - OFF", what, gold, n, want); return 0; }
    return 1;
}
static int nmp_sig(DWORD va, const BYTE *b, int n, const char *what) {
    int ok = memcmp((void *)(DWORD_PTR)va, b, n) == 0;
    if (!ok) NMP_LOG("  nitro-mp: signature %s at 0x%06lx differs - OFF", what, va);
    return ok;
}
static DWORD a_grpfn, a_dp, a_me, a_net, a_group, a_host, a_count, a_players, a_state, a_pack, a_root;   /* resolved Nitro addresses */
#define NMP_ROW(k) ((BYTE *)(DWORD_PTR)a_players + (k) * 0x50)       /* player table rows: 0x50 bytes on Nitro (0x48 on Gold) */

/* ---- state ---- */
typedef int (__cdecl *nmp_recv_fn)(void *, void *, void *, int, void *, void *);
typedef int (__cdecl *nmp_send_fn)(void *, int, int, int, void *, int);
static nmp_recv_fn nmp_real_recv; static nmp_send_fn nmp_dpsend;
static volatile LONG g_nmp_on;                       /* exe side attached */
static volatile LONG g_nmp_species;                  /* species of the session nitshell opened (0 = none yet) */
static volatile LONG g_nmp_opts;                     /* host's ARENA+ options (bit 0 AI DROP-IN ...), set by the shell part */
static LONG g_nmp_sent[8], g_nmp_got[8], g_nmp_senderr, g_nmp_toobig;
static BYTE g_hello_seq; static int g_hello_count = -1; static DWORD g_hello_last;
static WORD g_hello_acked[16]; static int g_hello_acks;  /* host: joiners that answered the current seq */
static BYTE g_hello_seen = 0xff;                         /* joiner: last host seq answered */
static WORD g_hello_from;                                /* joiner: host id from the last hello */
static int g_at_selftest, g_at_sent, g_at_recv;
/* hooks for the AI layer on top (nitro_ai.c): packets of ours other than 'AH', every pump call in an ARENA+ session */
static void (*g_nmp_rx_hook)(WORD from, const BYTE *p, int n); static void (*g_nmp_tick_hook)(int role);

static int nmp_arena(void) { return g_nmp_on && g_nmp_species == NMP_SPECIES_ARENA && *(volatile int *)(DWORD_PTR)a_net; }
static WORD nmp_me(void) { return *(volatile WORD *)(DWORD_PTR)a_me; }
static WORD nmp_hostid(void) { return *(volatile WORD *)(DWORD_PTR)a_host; }
static WORD nmp_group(void) { return ((WORD (__cdecl *)(void))(DWORD_PTR)a_grpfn)(); }   /* net_GetGroupId (site 0x454e10) */
static int nmp_role(void) { WORD me = nmp_me(), h = nmp_hostid(); if (!*(volatile int *)(DWORD_PTR)a_net || !me || !h) return 0; return me == h ? 1 : 2; }
static int nmp_tagidx(WORD t) { return t == NMP_TAG_AH ? 0 : t == NMP_TAG_AT ? 1 : t == NMP_TAG_AK ? 2 : t == NMP_TAG_AM ? 3 : 7; }

/* ---- send ---- */
static int nmp_send(WORD to, const void *pkt, int len, int reliable) {
    static BYTE buf[256 + NMP_SLACK]; int r;
    if (len > (reliable ? NMP_MAX_REL : NMP_MAX_UNREL)) { g_nmp_toobig++; NMP_LOG("  nitro-mp: %d-byte packet refused (limit %d)", len, reliable ? NMP_MAX_REL : NMP_MAX_UNREL); return -1; }
    memcpy(buf, pkt, len); memset(buf + len, 0, NMP_SLACK);
    r = nmp_dpsend(*(void **)(DWORD_PTR)a_dp, nmp_me(), to, reliable ? 1 : 0, buf, len);
    if (r == 0) g_nmp_sent[nmp_tagidx(*(WORD *)pkt)]++; else g_nmp_senderr++;
    return r;
}

/* ---- hello ---- */
static void nmp_hello_send(WORD to, BYTE seq) {
    BYTE p[12];
    *(WORD *)p = NMP_TAG_AH; p[2] = seq; p[3] = NMP_PROTO; *(WORD *)(p + 4) = (WORD)g_nmp_species; *(WORD *)(p + 6) = nmp_me();
    *(DWORD *)(p + 8) = (DWORD)g_nmp_opts;
    nmp_send(to, p, sizeof p, 1);
}
static void nmp_hello_recv(WORD from, const BYTE *p, int n) {
    if (n < 12) return;
    if (nmp_role() == 1) {   /* host: an answer */
        int k; if (p[2] != g_hello_seq) return;
        for (k = 0; k < g_hello_acks; k++) if (g_hello_acked[k] == from) return;
        if (g_hello_acks < 16) g_hello_acked[g_hello_acks++] = from;
        NMP_LOG("  nitro-mp: hello answered by %u (seq %u, proto %u, species %04x)", from, p[2], p[3], *(WORD *)(p + 4));
    } else {                  /* joiner: the host's hello -> answer once per seq */
        g_hello_from = from;
        if (p[2] != g_hello_seen) {
            g_hello_seen = p[2];
            NMP_LOG("  nitro-mp: hello from host %u (seq %u, proto %u, species %04x, options %08lx) - answering", from, p[2], p[3], *(WORD *)(p + 4), *(DWORD *)(p + 8));
            nmp_hello_send(from, p[2]);
        }
    }
}

/* ---- 'AT' ---- */
static BYTE *nmp_own_car(void) { BYTE **root = ((BYTE **(__cdecl *)(void))(DWORD_PTR)a_root)(); return root ? *root : 0; }
static BYTE *nmp_row_of(WORD id) { int k; for (k = 0; k < 16; k++) if (*(WORD *)NMP_ROW(k) == id) return NMP_ROW(k); return 0; }
static void nmp_at_self(void) {   /* lab proof: one record, our own car */
    BYTE p[8 + 100]; BYTE *o = nmp_own_car();
    if (!o) return;
    *(WORD *)p = NMP_TAG_AT; p[2] = 0; p[3] = 1;
    *(WORD *)(p + 8) = 0xFFFF; p[10] = 0; p[11] = 0;
    ((void (__cdecl *)(BYTE *, float *))(DWORD_PTR)a_pack)(o, (float *)(p + 12));
    *(float *)(p + 4) = *(float *)(p + 12);
    if (nmp_send(nmp_group(), p, sizeof p, 0) == 0) {
        g_at_sent++;
        NMP_LOG("  nitro-mp: 'AT' sent (%d B, own car at %.1f,%.1f)", (int)sizeof p, *(double *)(o + 0x40), *(double *)(o + 0x50));
    }
}
static void nmp_at_recv(WORD from, const BYTE *p, int n) {
    int k, cnt = p[3];
    if (n < 8 + cnt * 100 || cnt > 2) { NMP_LOG("  nitro-mp: 'AT' from %u malformed (%d B, n %d)", from, n, cnt); return; }
    for (k = 0; k < cnt; k++) {
        const BYTE *r = p + 8 + k * 100; const float *f = (const float *)(r + 4);
        if (*(WORD *)r == 0xFFFF) {   /* self-test record: the sender's own car; compare with our mirror of it */
            BYTE *row = nmp_row_of(from), *o = row ? *(BYTE **)(row + 0x28) : 0; int i, hit = -1; double x = 0, z = 0;
            if (o) { x = *(double *)(o + 0x40); z = *(double *)(o + 0x50);
                for (i = 0; i + 2 < 24; i++) if (fabs(f[i] - x) < 5.0 && fabs(f[i + 2] - z) < 5.0) { hit = i; break; } }
            g_at_recv++;
            NMP_LOG("  nitro-mp: 'AT' from %u: own-car record, our mirror of %u at %.1f,%.1f, record position %s (floats %d..%d: %.1f, %.1f, %.1f)",
                    from, from, x, z, hit >= 0 ? "AGREES" : "not found", hit, hit + 2, hit >= 0 ? f[hit] : 0, hit >= 0 ? f[hit + 1] : 0, hit >= 0 ? f[hit + 2] : 0);
        }
    }
}

/* ---- tick (every pump call) ---- */
static void nmp_tick(void) {
    DWORD now = GetTickCount(); int role = nmp_role(), cnt;
    if (!nmp_arena() || *(volatile int *)(DWORD_PTR)a_state != 5) return;
    cnt = *(volatile int *)(DWORD_PTR)a_count;
    if (role == 1) {
        if (cnt != g_hello_count) { g_hello_count = cnt; g_hello_seq++; g_hello_acks = 0; g_hello_last = 0; }
        if (cnt > 1 && g_hello_acks < cnt - 1 && now - g_hello_last > 2000) { g_hello_last = now; nmp_hello_send(nmp_group(), g_hello_seq); }
    }
    if (g_at_selftest && g_at_sent == 0 && ((role == 1 && g_hello_acks > 0) || (role == 2 && g_hello_seen != 0xff))) nmp_at_self();
}

static int __cdecl nmp_dpReceive(void *dp, void *from, void *to, int flags, void *buf, void *size) {
    int r = nmp_real_recv(dp, from, to, flags, buf, size);
    if (!nmp_arena()) return r;   /* stock session: pass-through, nothing read, nothing sent */
    if (r == 0 && buf && size && from) {
        WORD t = *(WORD *)buf, f = *(WORD *)from; int n = *(int *)size;
        if (t == NMP_TAG_AH || t == NMP_TAG_AT || t == NMP_TAG_AK || t == NMP_TAG_AM) g_nmp_got[nmp_tagidx(t)]++;
        if (t == NMP_TAG_AH) nmp_hello_recv(f, (const BYTE *)buf, n);
        else if (t == NMP_TAG_AT && n >= 8 && *(WORD *)((BYTE *)buf + 8) == 0xFFFF) nmp_at_recv(f, (const BYTE *)buf, n);
        else if (g_nmp_rx_hook && (t == NMP_TAG_AT || t == NMP_TAG_AK || t == NMP_TAG_AM)) g_nmp_rx_hook(f, (const BYTE *)buf, n);
    }
    nmp_tick();
    if (g_nmp_tick_hook) g_nmp_tick_hook(nmp_role());
    return r;
}

/* ---- read-back ---- */
static void nmp_status(const char *tag) {
    char line[1600]; int len, k;
    if (!g_nmp_on) return;
    len = sprintf(line, "  nitro-mp %s: species %04lx arena %d role %d state %d net %d me %u host %u rows %d; sent AH %ld AT %ld, got AH %ld AT %ld, errors %ld, too big %ld; acks %d; at sent %d recv %d; table:",
                  tag, g_nmp_species, nmp_arena(), nmp_role(), *(volatile int *)(DWORD_PTR)a_state, *(volatile int *)(DWORD_PTR)a_net, nmp_me(), nmp_hostid(),
                  *(volatile int *)(DWORD_PTR)a_count, g_nmp_sent[0], g_nmp_sent[1], g_nmp_got[0], g_nmp_got[1], g_nmp_senderr, g_nmp_toobig, g_hello_acks, g_at_sent, g_at_recv);
    for (k = 0; k < 16; k++) {
        BYTE *row = NMP_ROW(k), *o; if (!*(WORD *)row) continue;
        o = *(BYTE **)(row + 0x28);
        len += sprintf(line + len, " [%u '%.12s' flags %lx%s", *(WORD *)row, (char *)row + 2, *(DWORD *)(row + 0x1c), o ? "" : " no car]");
        if (o) len += sprintf(line + len, " at %.1f,%.1f]", *(double *)(o + 0x40), *(double *)(o + 0x50));
    }
    NMP_LOG("%s", line);
}

/* ---- nitshell: species of the session opened / joined, the single type-0 list ---- */
typedef int (__stdcall *nmp_enumcb_fn)(BYTE *, long *, long, void *);
typedef int (__cdecl *nmp_enum_fn)(void *, BYTE *, void *, long, nmp_enumcb_fn, void *);
typedef int (__cdecl *nmp_open_fn)(void *, BYTE *, void *, void *);
static nmp_enum_fn nmp_real_enum; static nmp_open_fn nmp_real_open; static nmp_enumcb_fn nmp_shell_cb;
static int __stdcall nmp_enum_cb(BYTE *s, long *tmo, long fl, void *ctx) {
    if (s) {
        WORD sp = *(WORD *)(s + 0xd);
        if (sp != NMP_SPECIES_STOCK && sp != NMP_SPECIES_ARENA) return 1;   /* another game's session: skip, go on */
        if (sp == NMP_SPECIES_ARENA && memcmp(s + 0x17, "ARENA+ ", 7)) {
            char nm[32]; memcpy(nm, s + 0x17, 32); nm[31] = 0; _snprintf((char *)s + 0x17, 31, "ARENA+ %s", nm); s[0x17 + 31] = 0;
        }
    }
    return nmp_shell_cb(s, tmo, fl, ctx);
}
static int __cdecl nmp_enum(void *dp, BYTE *sd, void *mbz, long tmo, nmp_enumcb_fn cb, void *ctx) {
    static BYTE sd0[0x200];
    memset(sd0, 0, sizeof sd0); memcpy(sd0, sd, 0x5f); *(WORD *)(sd0 + 0xd) = 0;   /* species 0 = any (anet2 0x020f8a20) */
    nmp_shell_cb = cb;
    return nmp_real_enum(dp, sd0, mbz, tmo, nmp_enum_cb, ctx);
}
static int __cdecl nmp_open(void *dp, BYTE *sd, void *cb, void *ctx) {
    int r;
    if (sd) g_nmp_species = *(WORD *)(sd + 0xd);
    r = nmp_real_open(dp, sd, cb, ctx);
    NMP_LOG("  nitro-mp: dpOpen species %04lx '%.31s' -> %d (%s)", g_nmp_species, sd ? (char *)sd + 0x17 : "", r,
            g_nmp_species == NMP_SPECIES_ARENA ? "ARENA+" : "stock");
    return r;
}
static int nmp_lobby_subscribe(void) {   /* STUB (record s.0.5.3): a second {table, 0x7676} subscription on the game server */
    return 0;
}
static void nmp_attach_shell(HMODULE sh) {
    void *e, *o;
    if (!g_nmp_on) return;
    e = NMP_IAT(sh, "anet2.dll", "dpEnumSessions", (void *)nmp_enum); o = NMP_IAT(sh, "anet2.dll", "dpOpen", (void *)nmp_open);
    if (e) nmp_real_enum = (nmp_enum_fn)e; if (o) nmp_real_open = (nmp_open_fn)o;
    NMP_LOG("  nitro-mp: nitshell hooks: dpEnumSessions %s (one call, species 0, filtered to 604 + 7676), dpOpen %s; lobby subscription: stub (%d)",
            e ? "ok" : "MISSING", o ? "ok" : "MISSING", nmp_lobby_subscribe());
}

/* ---- exe ---- */
static void nmp_attach_exe(void) {
    static const BYTE pack_sig[6] = { 0x83, 0xec, 0x4c, 0x53, 0x8b, 0x5c }, grp_sig[6] = { 0x66, 0xa1, 0xf8, 0xec, 0x53, 0x00 };
    HMODULE an = GetModuleHandleA("anet2.dll"); void *r;
    int ok = nmp_site(0x541024, 0x53f258, "dp handle", &a_dp) & nmp_site(0x541028, 0x53f25c, "my id", &a_me)
           & nmp_site(0x541030, 0x53f264, "net flag", &a_net) & nmp_site(0x541060, 0x53ecf8, "group", &a_group)
           & nmp_site(0x541064, 0x53ecfc, "host id", &a_host) & nmp_site(0x541068, 0x53ed00, "player count", &a_count)
           & nmp_site(0x541070, 0x53ed08, "player table", &a_players) & nmp_site(0x4c2164, 0x4f30cc, "game state", &a_state)
           & nmp_site(0x4644d0, 0x463660, "net_PackVehicleState", &a_pack) & nmp_site(0x457530, 0x453fd0, "world_GetRoot", &a_root)
           & nmp_site(0x454e10, 0x446fc0, "net_GetGroupId", &a_grpfn);
    ok = ok && nmp_sig(a_pack, pack_sig, 6, "net_PackVehicleState") && nmp_sig(a_grpfn, grp_sig, 6, "net_GetGroupId");
    nmp_dpsend = an ? (nmp_send_fn)GetProcAddress(an, "dpSend") : 0;
    if (!ok || !nmp_dpsend) { NMP_LOG("  nitro-mp: OFF (sites %d, dpSend %p)", ok, (void *)nmp_dpsend); return; }
    r = NMP_IAT(GetModuleHandleA(0), "anet2.dll", "dpReceive", (void *)nmp_dpReceive);
    if (!r) { NMP_LOG("  nitro-mp: OFF (no ANET2.DLL!dpReceive import)"); return; }
    nmp_real_recv = (nmp_recv_fn)r;
    { char v[8]; DWORD k = GetEnvironmentVariableA("NMP_AT_SELFTEST", v, sizeof v); g_at_selftest = k > 0 && k < sizeof v && v[0] == '1'; }
    g_nmp_on = 1;
    NMP_LOG("  nitro-mp: ON - dpReceive hooked, sends <= %d / %d B (+%d slack), hello reliable, 'AT' 2 records max%s", NMP_MAX_UNREL, NMP_MAX_REL, NMP_SLACK,
            g_at_selftest ? ", 'AT' self-test armed (lab)" : "");
}
