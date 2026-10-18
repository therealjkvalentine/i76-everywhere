/* ===========================================================================
 * FRAME-DT REPLAY  (I76_REPLAY=<file.rpl>; lab instrument, off by default; 2026-10-16)
 * ===========================================================================
 * i76-everywhere docs/records/LAB-FRAME-REPLAY.md, EMU-MEMTRACE.md section 7 items 2 and 3. Replays a per-frame memory
 * trace of the emulated 1997 PC (I76MEM, MEM.BIN -> lab tools\replay\rpl_make.py) through this exe, so the emulator's
 * frames and ours can be diffed one for one:
 *   - start state: once the player car exists (and I76_REPLAY_DELAY wall seconds later, default 3), at the top of a
 *     frame (frame hook, before simclock_Update) the car is placed at the trace's END state of its start frame: object
 *     +0x18 rotation (9 floats), +0x40 position (3 doubles); entity +0xac speed, +0xb0 1/speed, +0xbc velocity,
 *     +0xc8 body rates, +0xd4 acceleration;
 *   - dt: every following frame, right after simclock_Update, sim_dt 0x4fe420 / dt 0x4fe428 get the trace frame's values
 *     (bit for bit) and their rates 0x4fe424 / 0x4fe42c = 1 / value as simclock computes them; sim_time 0x5a7e70 and
 *     time 0x5a7e74 are moved by the same difference;
 *   - inputs: the one call of input_ApplyToEntity 0x44f1c0 (at 0x44df61, once per frame, before the vehicle ticks) goes
 *     through a wrapper that, after the stock code, writes the trace frame's applied steer +0xe0, throttle +0xe4 and
 *     handbrake +0xf0 into the player entity;
 *   - log: at the top of the next frame, i.e. after that frame's physics, collisions and render (where I76MEM reads in
 *     the emulator), one CSV line of the player's state in the trace's column names (I76_REPLAY_LOG, default
 *     <file>.lab.csv), then '#end' after the last row; forcing stops there and the game goes on as stock.
 * Addresses: our exe (AiO 6319abf7) = the Gold CD exe the Gold traces come from (same link, physics byte-identical:
 * emu\tools\memtrace\addrmap-gold.md). A retail 1.0 trace is replayed the same way: I76MEM maps its fields to the same
 * meanings. Nothing is patched without I76_REPLAY. */
typedef struct { DWORD frame; float sim_dt, dt, steer, throttle; int hb; char phase[16]; } rpl_row_t;
static rpl_row_t *g_rpl_rows;
static DWORD g_rpl_n, g_rpl_i, g_rpl_start_frame, g_rpl_in_calls, g_rpl_in_total;
static int g_rpl_state;                                      /* 0 waiting for the player, 1 replaying, 2 done */
static rpl_row_t *g_rpl_cur;
static double g_rpl_pos[3];
static float g_rpl_rot[9], g_rpl_vel[3], g_rpl_speed, g_rpl_inv, g_rpl_rates[3], g_rpl_acc[3];
static FILE *g_rpl_log;
static DWORD g_rpl_seen_tick, g_rpl_delay_ms = 3000, g_rpl_skips;
static int g_rpl_skip = 1;                                  /* I76_REPLAY_SKIP=0: do not press MAIN_MENU through the opening */
static DWORD g_rpl_eflags, g_rpl_eflags_mask;                /* I76_REPLAY_EFLAGS=<hex mask>: entity +0x454 bits taken from the trace */
static int g_rpl_have_eflags;
/* I76_REPLAY_PREROLL=<frames> (2026-10-17, item 51; 0 = off, the wall-clock I76_REPLAY_DELAY as before): count the wait
 * before the placement in frames, and run those frames at the trace's first sim_dt / dt instead of the real frame time.
 * The placement sets position, rotation, velocity, rates and acceleration only; everything else (wheels, suspension,
 * drivetrain) comes from the frames before it. With a wall-clock wait those frames had real (jittering) times and the
 * Instant Melee A/A pair differed 3 frames into the throttle (frame 709, 1e-9 m). */
static DWORD g_rpl_preroll, g_rpl_pre_n;
static int g_rpl_pre_on;
/* I76_REPLAY_SRAND=<seed> (2026-10-17, item 51): the exe seeds MSVCRT rand() with time(NULL) at every mission start
 * (i76-map functions/004a9020, 004ad260); under this switch every srand() call of i76.exe gets <seed> instead, so two
 * replays draw the same random numbers. Test of whether the A/A divergence comes from rand(). */
static unsigned g_rpl_seed; static int g_rpl_seed_on; static volatile LONG g_rpl_srand_n;
static void (__cdecl *p_rpl_srand)(unsigned);
static void __cdecl rpl_srand(unsigned s) { (void)s; InterlockedIncrement(&g_rpl_srand_n); if (p_rpl_srand) p_rpl_srand(g_rpl_seed); }
/* I76_REPLAY_RANDLOG=1 (2026-10-17): census of i76.exe's rand() callers while replaying: per replayed frame, one mlog line
 * '  replay: rand frame <trace frame> n <calls> <return address>x<count> ...' (main thread only, up to 16 callers). */
static int g_rpl_randlog; static int (__cdecl *p_rpl_rand)(void);
static DWORD g_rpl_rc_ra[16], g_rpl_rc_n[16], g_rpl_rc_k, g_rpl_rc_total, g_rpl_main_tid;
static int __cdecl rpl_rand(void) {
    if (g_rpl_state == 1 && GetCurrentThreadId() == g_rpl_main_tid) {
        DWORD ra = (DWORD)(DWORD_PTR)_ReturnAddress(), i;
        for (i = 0; i < g_rpl_rc_k && g_rpl_rc_ra[i] != ra; i++) ;
        if (i < 16) { if (i == g_rpl_rc_k) { g_rpl_rc_ra[i] = ra; g_rpl_rc_n[i] = 0; g_rpl_rc_k++; } g_rpl_rc_n[i]++; }
        g_rpl_rc_total++;
    }
    return p_rpl_rand ? p_rpl_rand() : 0;
}
static void rpl_rand_flush(DWORD frame) {
    char b[600]; int o; DWORD i;
    if (!g_rpl_randlog || !g_rpl_rc_total) return;
    o = wsprintfA(b, "  replay: rand frame %lu n %lu", (unsigned long)frame, (unsigned long)g_rpl_rc_total);
    for (i = 0; i < g_rpl_rc_k && o < 560; i++) o += wsprintfA(b + o, " %08lx x%lu", (unsigned long)g_rpl_rc_ra[i], (unsigned long)g_rpl_rc_n[i]);
    mlog("%s", b);
    g_rpl_rc_k = 0; g_rpl_rc_total = 0;
}
static char g_rpl_src[160];

static float rpl_hexf(const char *s) { DWORD u = strtoul(s, 0, 16); float f; memcpy(&f, &u, 4); return f; }
static double rpl_hexd(const char *s) {
    unsigned __int64 u = 0; double d;
    for (; *s; s++) { int c = *s, v = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
                      if (v < 0) break; u = (u << 4) | (unsigned)v; }
    memcpy(&d, &u, 8); return d;
}

/* file: '#' comments, 'src <text>', one 'S' line (pos x3 as 16-hex-digit doubles, rot x9, vel x3, speed, inv speed,
 * rates x3, accel x3 as 8-hex-digit floats), then 'F <trace frame> <sim_dt> <dt> <steer> <throttle> <handbrake int> <phase>' */
static int rpl_load(const char *path) {
    FILE *f = fopen(path, "r");
    char ln[512]; DWORD cap = 0; int have_s = 0;
    if (!f) { mlog("  replay: cannot open '%s'", path); return 0; }
    while (fgets(ln, sizeof ln, f)) {
        char *tok[32]; int n = 0; char *p = ln;
        while (n < 32) { while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++; if (!*p) break; tok[n++] = p;
                         while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++; if (*p) *p++ = 0; }
        if (!n || tok[0][0] == '#') continue;
        if (!strcmp(tok[0], "src") && n > 1) { lstrcpynA(g_rpl_src, tok[1], sizeof g_rpl_src); continue; }
        if (!strcmp(tok[0], "S") && n >= 24) {
            int i, k = 1;
            for (i = 0; i < 3; i++) g_rpl_pos[i] = rpl_hexd(tok[k++]);
            for (i = 0; i < 9; i++) g_rpl_rot[i] = rpl_hexf(tok[k++]);
            for (i = 0; i < 3; i++) g_rpl_vel[i] = rpl_hexf(tok[k++]);
            g_rpl_speed = rpl_hexf(tok[k++]); g_rpl_inv = rpl_hexf(tok[k++]);
            for (i = 0; i < 3; i++) g_rpl_rates[i] = rpl_hexf(tok[k++]);
            for (i = 0; i < 3; i++) g_rpl_acc[i] = rpl_hexf(tok[k++]);
            if (n > k) { g_rpl_eflags = strtoul(tok[k++], 0, 16); g_rpl_have_eflags = 1; }   /* optional: entity flags */
            have_s = 1; continue;
        }
        if (!strcmp(tok[0], "F") && n >= 7) {
            rpl_row_t *r;
            if (g_rpl_n == cap) {
                rpl_row_t *nr = (rpl_row_t *)realloc(g_rpl_rows, (cap ? cap * 2 : 4096) * sizeof *nr);
                if (!nr) break;
                g_rpl_rows = nr; cap = cap ? cap * 2 : 4096;
            }
            r = &g_rpl_rows[g_rpl_n++];
            r->frame = strtoul(tok[1], 0, 10); r->sim_dt = rpl_hexf(tok[2]); r->dt = rpl_hexf(tok[3]);
            r->steer = rpl_hexf(tok[4]); r->throttle = rpl_hexf(tok[5]); r->hb = atoi(tok[6]);
            lstrcpynA(r->phase, n > 7 ? tok[7] : "", sizeof r->phase);
        }
    }
    fclose(f);
    if (!have_s || !g_rpl_n) { mlog("  replay: '%s' has %s - off", path, have_s ? "no F rows" : "no S line"); return 0; }
    return 1;
}

static void rpl_log_header(void) {
    fprintf(g_rpl_log, "# I76_REPLAY lab log: src %s, %lu rows; one line per replayed frame, read at the top of the next frame "
                       "(after its physics, collisions and render)\n", g_rpl_src, (unsigned long)g_rpl_n);
    fprintf(g_rpl_log, "frame,lab_frame,phase,sim_dt,dt,sim_time,x,y,z,vx,vy,vz,speed,pitch_rate,yaw_rate,roll_rate,"
                       "r0,r1,r2,r3,r4,r5,r6,r7,r8,ax,ay,az,steer,throttle,handbrake,flags,surface,clearance,step_ms,"
                       "rpm,gear,health,input_calls,near_dist,mass,armour,armour_chassis_max\n");
}

static int rpl_sum(BYTE *p, int n) { int s = 0, i; for (i = 0; i < n; i++) s += ((int *)p)[i]; return s; }

static void rpl_log_frame(const rpl_row_t *row) {
    BYTE *ent = 0, *obj = tel_player(&ent), *eng;
    float rpm = -1.0f; int gear = -1, i; double nd = -1.0;
    if (!obj) { fprintf(g_rpl_log, "%lu,%lu,%s,no player\n", (unsigned long)row->frame, (unsigned long)g_frame, row->phase); return; }
    if ((eng = tel_comp(ent, 7, 21)) != 0) { gear = *(int *)(eng + 0x08); rpm = *(float *)(eng + 0x1c); }
    {   /* nearest other entry of the world position table 0x54e11c (16 slots of x, y, z, radius floats) */
        double px = *(double *)(obj + 0x40), pz = *(double *)(obj + 0x50);
        for (i = 0; i < 16; i++) {
            float *q = (float *)(0x0054e11c + 0x20 * i); double dx = q[0] - px, dz = q[2] - pz, d = sqrt(dx * dx + dz * dz);
            if (q[0] != q[0] || (fabs(q[0]) < 0.01 && fabs(q[2]) < 0.01) || d < 0.5) continue;
            if (nd < 0 || d < nd) nd = d;
        }
    }
    {
        double *p = (double *)(obj + 0x40); float *r = (float *)(obj + 0x18);
        float *v = (float *)(ent + 0xbc), *w = (float *)(ent + 0xc8), *a = (float *)(ent + 0xd4);
        fprintf(g_rpl_log, "%lu,%lu,%s,%.9g,%.9g,%.9g,%.10f,%.10f,%.10f,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,"
                           "%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%d,%lu,%lu,%.6g,%.4f,%.1f,%d,%d,%lu,%.2f,%.6g,%d,%d\n",
                (unsigned long)row->frame, (unsigned long)g_frame, row->phase,
                *(volatile float *)0x004fe420, *(volatile float *)0x004fe428, *(volatile float *)0x005a7e70,
                p[0], p[1], p[2], v[0], v[1], v[2], *(float *)(ent + 0xac), w[0], w[1], w[2],
                r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], a[0], a[1], a[2],
                *(float *)(ent + 0xe0), *(float *)(ent + 0xe4), *(int *)(ent + 0xf0),
                (unsigned long)*(DWORD *)(ent + 0x454), (unsigned long)*(DWORD *)(ent + 0x45c), *(float *)(ent + 0x470),
                *(float *)(ent + 0x448) * 1000.0f, rpm, gear, tel_health_sum(obj), (unsigned long)g_rpl_in_calls, nd,
                *(float *)(ent + 0xa4), rpl_sum(ent + 0x138, 8), rpl_sum(ent + 0x158, 8));
    }
    if ((row->frame & 63) == 0) fflush(g_rpl_log);
}

/* I76_REPLAY_EFLAGS=<hex mask> (default 0 = none): the masked bits of the entity flags +0x454 are set to the trace's start
 * value at the placement and again at the top of every replayed frame. 10000 = flag 0x10000, the "Arcade Phys." bit every
 * retail 1.0 trace carries and no Gold trace does (docs/records/RETAIL-HANDLING.md); the other bits are the engine's
 * own per-step state (airborne, landed, skid ...) and are left to it. */
static void rpl_hold_flags(BYTE *ent) {
    if (!g_rpl_eflags_mask || !g_rpl_have_eflags) return;
    *(volatile DWORD *)(ent + 0x454) = (*(volatile DWORD *)(ent + 0x454) & ~g_rpl_eflags_mask) | (g_rpl_eflags & g_rpl_eflags_mask);
}

static void rpl_place(BYTE *obj, BYTE *ent) {
    memcpy(obj + 0x18, g_rpl_rot, 36);
    memcpy(obj + 0x40, g_rpl_pos, 24);
    *(float *)(ent + 0xac) = g_rpl_speed; *(float *)(ent + 0xb0) = g_rpl_inv;
    memcpy(ent + 0xbc, g_rpl_vel, 12); memcpy(ent + 0xc8, g_rpl_rates, 12); memcpy(ent + 0xd4, g_rpl_acc, 12);
    rpl_hold_flags(ent);
}

/* frame hook, before simclock_Update */
static void rpl_pre(void) {
    BYTE *ent = 0, *obj;
#ifdef _MSC_VER
    __try {
#endif
        if (g_rpl_state == 1) {
            if (g_rpl_cur) { rpl_log_frame(g_rpl_cur); rpl_rand_flush(g_rpl_cur->frame); }
            g_rpl_in_calls = 0;
            if (g_rpl_i < g_rpl_n && tel_player(&ent)) rpl_hold_flags(ent);
            if (g_rpl_i >= g_rpl_n) {
                fprintf(g_rpl_log, "#end %lu rows, %lu input-apply calls, lab frames %lu..%lu\n", (unsigned long)g_rpl_n,
                        (unsigned long)g_rpl_in_total, (unsigned long)g_rpl_start_frame, (unsigned long)g_frame);
                fclose(g_rpl_log); g_rpl_log = 0; g_rpl_state = 2; g_rpl_cur = 0;
                mlog("  replay: done, %lu rows (lab frames %lu..%lu)", (unsigned long)g_rpl_n, (unsigned long)g_rpl_start_frame, (unsigned long)g_frame);
            }
            return;
        }
        if (g_rpl_state != 0) return;
        obj = tel_player(&ent);
        if (obj && g_rpl_skip && ((*(volatile BYTE *)0x004fe534 & 0x3e) || *(volatile DWORD *)0x005244c0) && (g_frame % 20) == 0) {
            /* the mission's opening (camera sequence, the player script-driven 0x5244c0 or a pause state): press the
             * MAIN_MENU key the way the keyboard handler does, by putting its scan code in the last-key slot 0x5367c8
             * that the FSM's isKeypress 0x44de40 and the state handler 0x49d000 read (command 0x22 in the scan-code
             * table 0x53db30, from input.map); no input injection, so it works headless */
            int sc;
            for (sc = 1; sc < 256; sc++) if (((volatile BYTE *)0x0053db30)[sc] == 0x22) break;
            if (sc < 256) { *(volatile DWORD *)0x005367c8 = (DWORD)sc; g_rpl_skips++; }
        }
        if (!obj || *(volatile DWORD *)0x004c2164 != 5 || (*(volatile BYTE *)0x004fe534 & 0x3e) || *(volatile DWORD *)0x005244c0) {
            g_rpl_seen_tick = 0; g_rpl_pre_n = 0; g_rpl_pre_on = 0; return;
        }
        if (g_rpl_preroll) {
            if (g_rpl_pre_n < g_rpl_preroll) { g_rpl_pre_n++; g_rpl_pre_on = 1; return; }
            g_rpl_pre_on = 0;
        } else {
            if (!g_rpl_seen_tick) { g_rpl_seen_tick = GetTickCount(); return; }
            if (GetTickCount() - g_rpl_seen_tick < g_rpl_delay_ms) return;
        }
        rpl_place(obj, ent);
        g_rpl_main_tid = GetCurrentThreadId();
        g_rpl_state = 1; g_rpl_i = 0; g_rpl_start_frame = g_frame; g_rpl_in_calls = 0;
        mlog("  replay: started at lab frame %lu (pre-roll %lu fixed-dt frames, srand calls %ld), placed at %.3f %.3f %.3f, %lu rows from trace frame %lu (%lu MAIN_MENU presses through the opening)",
             (unsigned long)g_frame, (unsigned long)g_rpl_pre_n, g_rpl_srand_n, g_rpl_pos[0], g_rpl_pos[1], g_rpl_pos[2], (unsigned long)g_rpl_n, (unsigned long)g_rpl_rows[0].frame,
             (unsigned long)g_rpl_skips);
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { mlog("  replay: fault in the frame hook - stopped"); g_rpl_state = 2; }
#endif
}

/* frame hook, right after simclock_Update */
static void rpl_post_clock(void) {
    rpl_row_t *r;
    float d;
    if (g_rpl_state == 0 && g_rpl_pre_on) r = &g_rpl_rows[0];   /* pre-roll: the trace's first frame times, no row consumed */
    else {
        if (g_rpl_state != 1 || g_rpl_i >= g_rpl_n) { g_rpl_cur = 0; return; }
        r = g_rpl_cur = &g_rpl_rows[g_rpl_i++];
    }
    d = r->sim_dt - *(volatile float *)0x004fe420;
    *(volatile float *)0x005a7e70 += d;                       /* simclock_sim_time: as if it had added the trace's dt */
    *(volatile float *)0x005a7e74 += r->dt - *(volatile float *)0x004fe428;
    *(volatile float *)0x004fe420 = r->sim_dt; *(volatile float *)0x004fe424 = 1.0f / r->sim_dt;
    *(volatile float *)0x004fe428 = r->dt;     *(volatile float *)0x004fe42c = 1.0f / r->dt;
}

static void __cdecl rpl_input_wrap(void) {
    BYTE *ent = 0;
    ((void (__cdecl *)(void))0x0044f1c0)();                   /* input_ApplyToEntity, stock */
    if (g_rpl_state != 1 || !g_rpl_cur) return;
    g_rpl_in_calls++; g_rpl_in_total++;
    if (!tel_player(&ent)) return;
    *(float *)(ent + 0xe0) = g_rpl_cur->steer;
    *(float *)(ent + 0xe4) = g_rpl_cur->throttle;
    *(int *)(ent + 0xf0) = g_rpl_cur->hb;
}

/* Headless (disconnected session, lab nullglide / nullddraw renderers): the window is never activated, so the game's
 * active flag 0x504c1c stays 0. The pre-loop at 0x40374b runs the mission loader 0x49d000 only while it is set; with it 0
 * the loader never runs, the loop ends and the start-up path calls the still-null camera callback [0x4c2720] at
 * 0x403868 (fault at address 0). I76_KEEP_ACTIVE holds the flag only from the frame hook, which runs later, in the
 * frame loop. So under I76_REPLAY a small thread holds it from the start until the frame hook has run 30 frames. */
static volatile LONG g_rpl_act_sets;
static DWORD WINAPI rpl_active_thread(LPVOID p) {
    (void)p;
    while (g_frame < 30) {
        if (*(volatile DWORD *)0x00504c1c == 0) { *(volatile DWORD *)0x00504c1c = 1; InterlockedIncrement(&g_rpl_act_sets); }
        Sleep(2);
    }
    mlog("  replay: active-flag thread done at frame %lu (%ld sets)", (unsigned long)g_frame, g_rpl_act_sets);
    return 0;
}

/* I76_REPLAY_CLICKS="x,y,ms;x,y,ms;..." (2026-10-16): click through the shell headless, e.g. into an Instant Melee (the
 * melee arenas cannot be booted with I76_MISSION: bwd2_LoadMissionFile's 'm' missions spawn their players from the
 * shell's melee setup, and a direct boot of m01 never creates the player). Once the shell (game state 6) has been up for
 * 3 s, each click is a WM_MOUSEMOVE + WM_LBUTTONDOWN + WM_LBUTTONUP posted to the game window at the 640x480 UI point,
 * with cursormap's pad ownership set to the same point (GetCursorPos / the PeekMessageA mouse lParam slots answer it;
 * needs I76_CURSOR_MAP=1, and I76_CURSOR_MAP_U32X=1 for the u32x slots); then it waits ms. No input injection. */
static char g_rpl_clicks[512];
/* the shell polls the button with GetAsyncKeyState / GetKeyState (i76shell.dll's u32x.dll slots), not messages */
static volatile LONG g_rpl_lbtn;
static SHORT (WINAPI *p_rpl_gaks)(int), (WINAPI *p_rpl_gks)(int);
static volatile LONG g_rpl_gaks_n, g_rpl_gaks_lb, g_rpl_gks_n;
static SHORT WINAPI rpl_GetAsyncKeyState(int vk) { InterlockedIncrement(&g_rpl_gaks_n); if (vk == VK_LBUTTON) InterlockedIncrement(&g_rpl_gaks_lb); if (vk == VK_LBUTTON && g_rpl_lbtn) return (SHORT)0x8001; return p_rpl_gaks ? p_rpl_gaks(vk) : 0; }
static SHORT WINAPI rpl_GetKeyState(int vk) { InterlockedIncrement(&g_rpl_gks_n); if (vk == VK_LBUTTON && g_rpl_lbtn) return (SHORT)0xFF80; return p_rpl_gks ? p_rpl_gks(vk) : 0; }
static int rpl_hook_buttons(HMODULE m) {
    static const char *dlls[2] = { "u32x.dll", "USER32.dll" };
    int i, k = 0; void *o;
    for (i = 0; i < 2; i++) {
        if ((o = patch_iat(m, dlls[i], "GetAsyncKeyState", rpl_GetAsyncKeyState)) != 0) { if (!p_rpl_gaks) p_rpl_gaks = (SHORT (WINAPI *)(int))o; k++; }
        if ((o = patch_iat(m, dlls[i], "GetKeyState", rpl_GetKeyState)) != 0) { if (!p_rpl_gks) p_rpl_gks = (SHORT (WINAPI *)(int))o; k++; }
    }
    return k;
}
static DWORD WINAPI rpl_click_thread(LPVOID p) {
    char *c = g_rpl_clicks; DWORD shell_since = 0; int n = 0;
    (void)p;
    for (;;) {                                               /* the shell, 3 s */
        if (*(volatile DWORD *)0x004c2164 == 6) { if (!shell_since) shell_since = GetTickCount(); else if (GetTickCount() - shell_since > 3000) break; }
        else shell_since = 0;
        Sleep(50);
    }
    {
        HMODULE sh = GetModuleHandleA("i76shell.dll");
        int a = rpl_hook_buttons(GetModuleHandleA(NULL)), b = sh ? rpl_hook_buttons(sh) : -1;
        mlog("  replay: shell clicker - button slots taken: i76.exe %d, i76shell.dll %d", a, b);
    }
    while (*c) {
        int x = atoi(c), y = 0, ms = 2000; char *q = strchr(c, ',');
        HWND h = cm_window();
        if (q) { y = atoi(q + 1); q = strchr(q + 1, ','); if (q && (!strchr(c, ';') || q < strchr(c, ';'))) ms = atoi(q + 1); }
        InterlockedExchange(&g_cm_pad_xy, MAKELONG(x, y)); InterlockedExchange(&g_cm_pad_own, 1);
        if (h) {
            LPARAM lp = MAKELPARAM(x, y);
            if (n == 0) {                                     /* a headless window is never activated: tell it it is */
                PostMessageA(h, WM_ACTIVATEAPP, TRUE, 0); PostMessageA(h, WM_ACTIVATE, WA_ACTIVE, 0); PostMessageA(h, WM_SETFOCUS, 0, 0);
                Sleep(300);
            }
            PostMessageA(h, WM_MOUSEMOVE, 0, lp); Sleep(150);
            InterlockedExchange(&g_rpl_lbtn, 1);
            PostMessageA(h, WM_LBUTTONDOWN, MK_LBUTTON, lp); Sleep(250);
            InterlockedExchange(&g_rpl_lbtn, 0);
            PostMessageA(h, WM_LBUTTONUP, 0, lp);
        }
        n++;
        mlog("  replay: shell click %d at UI %d,%d (window %p, game state %lu), then %d ms; GetAsyncKeyState calls %ld (LBUTTON %ld), "
             "GetKeyState %ld, foreground %p active %p", n, x, y, (void *)h, (unsigned long)*(volatile DWORD *)0x004c2164, ms,
             g_rpl_gaks_n, g_rpl_gaks_lb, g_rpl_gks_n, (void *)GetForegroundWindow(), (void *)GetActiveWindow());
        Sleep(ms);
        c = strchr(c, ';'); if (!c) break; c++;
    }
    return 0;
}

static void apply_replay(void) {
    char path[MAX_PATH], logp[MAX_PATH], v[16];
    BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
    LONG rel;
    if (!env_str("I76_REPLAY", path, sizeof path)) return;
    if (!rpl_load(path)) return;
    if (env_str("I76_REPLAY_DELAY", v, sizeof v)) g_rpl_delay_ms = (DWORD)(atof(v) * 1000.0);
    if (env_str("I76_REPLAY_EFLAGS", v, sizeof v)) g_rpl_eflags_mask = strtoul(v, 0, 16);
    if (env_str("I76_REPLAY_PREROLL", v, sizeof v)) g_rpl_preroll = strtoul(v, 0, 10);
    if (env_str("I76_REPLAY_SRAND", v, sizeof v)) {
        void *o = patch_iat(GetModuleHandleA(NULL), "MSVCRT.dll", "srand", rpl_srand);
        g_rpl_seed = (unsigned)strtoul(v, 0, 10);
        if (o) { p_rpl_srand = (void (__cdecl *)(unsigned))o; g_rpl_seed_on = 1; }
        mlog("  replay: srand %s (seed %u)", o ? "fixed" : "NOT hooked (no MSVCRT.dll srand import)", g_rpl_seed);
    }
    if (env_flag("I76_REPLAY_RANDLOG", 8, 0)) {
        void *o = patch_iat(GetModuleHandleA(NULL), "MSVCRT.dll", "rand", rpl_rand);
        if (o) { p_rpl_rand = (int (__cdecl *)(void))o; g_rpl_randlog = 1; }
        mlog("  replay: rand census %s", o ? "on" : "NOT hooked");
    }
    g_rpl_skip = env_flag("I76_REPLAY_SKIP", 8, 1) != 0;
    if (!env_str("I76_REPLAY_LOG", logp, sizeof logp)) { lstrcpynA(logp, path, MAX_PATH - 9); lstrcatA(logp, ".lab.csv"); }
    rel = (LONG)(0x0044f1c0 - (0x0044df61 + 5)); memcpy(o + 1, &rel, 4);
    rel = (LONG)((DWORD_PTR)rpl_input_wrap - (0x0044df61 + 5)); memcpy(w + 1, &rel, 4);
    if (!patch_bytes(0x0044df61, o, w, 5, "input_ApplyToEntity call (replay)")) { mlog("  replay: input call site not as expected - off"); return; }
    install_frame_hook();
    if (!g_frame_hook) { mlog("  replay: no frame hook - off"); return; }
    g_rpl_log = fopen(logp, "w");
    if (!g_rpl_log) { mlog("  replay: cannot write '%s' - off", logp); return; }
    rpl_log_header();
    fflush(g_rpl_log);
    g_rpl_on = 1;
    if (env_flag("I76_REPLAY_ACTIVE", 8, 1)) CloseHandle(CreateThread(0, 0, rpl_active_thread, 0, 0, 0));
    if (env_str("I76_REPLAY_CLICKS", g_rpl_clicks, sizeof g_rpl_clicks)) CloseHandle(CreateThread(0, 0, rpl_click_thread, 0, 0, 0));
    mlog("  replay: on - %lu rows (trace frames %lu..%lu, src %s), start %.0f ms (pre-roll %lu frames, 0 = wall clock) after the player exists, log %s; "
         "entity flag bits from the trace: mask 0x%lX (trace start flags %s0x%lX)",
         (unsigned long)g_rpl_n, (unsigned long)g_rpl_rows[0].frame, (unsigned long)g_rpl_rows[g_rpl_n - 1].frame, g_rpl_src,
         (double)g_rpl_delay_ms, (unsigned long)g_rpl_preroll, logp, (unsigned long)g_rpl_eflags_mask, g_rpl_have_eflags ? "" : "none, ", (unsigned long)g_rpl_eflags);
}
