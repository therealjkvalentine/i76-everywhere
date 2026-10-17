/* ===========================================================================
 * WHOLE-SIM FIXED TICK  (I76_SIM_TICK_MS=<ms>; lab experiment, off by default; 2026-10-17)
 * ===========================================================================
 * i76-everywhere docs/records/WHOLE-SIM-TICK-2026-10-17.md, PHYSICS-STEP-STUDY-DESIGN.md s.7.2. The alternative to
 * I76_FIXED_STEP + the patch pile: the game's WHOLE per-frame simulation runs only on tick frames, with sim_dt = the
 * tick; every other display frame runs only the camera and the render path, with every moving object drawn between
 * its last two simulated poses. In 1997 one frame was one pass of everything; this keeps that coupling and moves only
 * the drawing out of it, so the engine's own stepper does the rest (count = floor(20 x T) + 1: 2 x 33.3 ms substeps at
 * a 66.7 ms tick, 1 x 33.3 ms at 33.3 ms) and the per-frame patches have nothing left to rescale.
 *
 * The cut (static, AiO 6319abf7 = Galaxy 9a232dcc at these bytes; WinMain's mission loop 0x40398d..0x4040c4, offline):
 *   SIM  (gated: run on tick frames only; each `call` site is repointed at a gate that chains to what was there)
 *     0x4039bd input_UpdateControls 0x44d9e0   key edges, discrete one-frame pulses, held bytes
 *     0x403a12 physics_CollideAll   0x4349c0   object/vehicle collision sweep over [0, sim_dt]
 *     0x403a1c input_ProcessFrame   0x44dec0   -> input_ApplyToEntity (controls into the player entity)
 *     0x403d86 entity_TickAll       0x461c80   class slot +0xc of every live object: entity_TickVehicle (stepper,
 *                                              camera_ClassifyDistance -> far path 0x43a3c0), aircraft, gates, ...
 *     0x403da6 / 0x403dd0 net_RegenPointTick 0x4515e0 (multi-melee regen points; result tested)
 *     0x403dd5 entity_PostTickAll   0x461d50   slot +0x10 (player: 0x463950 -> ffb_WriteSimState)
 *     0x403ddf ai_FrameTick         0x40a320   hand-off latch, FSM machines (script VM), every AI behaviour
 *     0x403de7 entity_TickTurretFire 0x462a90
 *     0x403dec weapon_UpdateProjectiles 0x4a0410 (incl. delayed impacts, stationary hazards)
 *     0x403df6 weapon_Update        0x4a4130   firing, lock tones, HUD ammo digits
 *     0x403dfb image_UpdateTexAnims 0x44af80   texture animations (time-based; gated with the sim)
 *   CLOCK  0x4039b8 simclock_Update 0x49c920: called on tick frames only (frame hook), then dt = sim_dt = T, rates
 *          1/T, and simclock_time / sim_time / accum_dt advanced by exactly T. simclock_frame_count 0x5a7e1c (read only
 *          by render code: texture cache LRU, cockpit, via GetFrameCount 0x49c7d0) still counts DISPLAY frames.
 *   RENDER (every display frame)
 *     0x403e16 call [0x4c2720]  camera mode (chase lag, cockpit sway 0x437f90, free-look, hood ...) - on the DRAWN poses,
 *                               with dt = sim_dt = the display frame's wall dt (camera code reads GetDt and GetSimDt)
 *     0x403e1c renderer_EvictFarEntityGeometry 0x4066e0, 0x403e27 shell_cb_10 -> sound_UpdateListener 0x422440
 *              (DS3D listener from the camera 0x4c2890 + the player's velocity: display rate, drawn camera)
 *     0x403e69 renderer_DrawFrame 0x401c90 (scene, flamer streams, smoke, skid marks, trails, mirror, HUD), Flip.
 *   Camera-relative work on the SIM side: camera_ClassifyDistance (near / far vehicle path) and the AI's view tests
 *   read the camera the last display frame left, i.e. the drawn pose (<= one tick behind physics), as 1997 read the
 *   previous frame's camera.
 *   Sim logic inside draw code, held to the tick (the FRAMERATE_FIXES wrappers, reused with g_tick20 = "this display
 *   frame ran a tick", g_ref_dt = T): flamer ageing 0x443e90 and update / damage / hit explosion (main pass only,
 *   flamer dt = T, hit test on the tick clock), smoke puff ageing (drawn extrapolated between ticks), missile trail
 *   fade, radar ping. Display-rate cosmetics scaled by display dt / T (I76_SIM_TICK_COSMETIC=0 off): clouds,
 *   free-look keys, zoom key.
 * Interpolation: at the start of each tick every live object's 0x40-byte transform (object +0x18) is recorded, at
 * the end of the sim block again; objects that moved get drawn at lerp(start, end, alpha), alpha = wall time since
 * the tick / T (one tick of display latency). Swapped in around the camera mode and the render only, the physics
 * pose put back right after; an object whose pose changed outside the sim (trainer) is drawn as it is. Covered:
 * the live object list 0x54b204 (vehicles, aircraft, objects with a tick) and the projectile lists (0x655290, stride
 * 0xd0, [0x5a810c] ordnance types, linked by +0x60). Cameras set from the sim (script cameras in the FSM) are
 * interpolated between the last two ticks' views when no camera mode set the view this display frame.
 * Excludes I76_FIXED_STEP, I76_RENDER_INTERP and I76_FRAMERATE_FIXES (not applied if any is on).
 * I76_SIM_TICK_LOG=<s> logs the counters every <s> seconds; Local\I76SimTick publishes them (tools: wst_*.py). */

typedef struct {
    DWORD magic, version;
    float tick_s, alpha;
    DWORD ticks, dframes, nontick, gameplay_frames;
    DWORD gate[12];
    DWORD veh_ticks, veh_hist[6];        /* vehicle ticks on tick frames: stepper count 0..4, [5] = far path */
    DWORD pl_hist[6];
    float pl_step_ms;
    DWORD multi_due, pad0;
    double wall_s, dropped_s;
    DWORD moving_last, moving_max, swaps, ext_writes;
    DWORD leak_checks, leak_mismatch, dead_after_render, pad1;
    DWORD jud_moved[4], jud_stall[4];    /* player, AI vehicle, projectile, other */
    DWORD cam_moved, cam_stall, simcam_interp, cam_disp_sets;
    DWORD flame_hits, flame_dmg, ping_req, ping_play;
    DWORD census_frames, objs_seen, proj_seen, pad2;
} wst_shm_t;
static volatile wst_shm_t *g_wst;
static wst_shm_t g_wst_local;

static float g_st_T;                 /* tick, s */
static double g_st_acc = 1.0, g_st_since;   /* acc starts high: the first gameplay frame ticks */  /* wall s since the last tick boundary / since the last tick frame */
static LARGE_INTEGER g_st_q;
static float g_st_disp_dt = 0.0083f;
static float g_st_clk[4];            /* sim_dt, sim_rate, dt, rate of the tick (what the sim saw) */
static int g_st_in_disp;             /* inside the display window (camera + render) */
static int g_st_cosmetic = 1;
static DWORD g_st_logper, g_st_lastlog;
static DWORD g_stc[12];              /* chained call targets of the gated sites */

/* ---- objects ------------------------------------------------------------------------------------------------- */
#define WST_N 2048
#define WST_H 8192
typedef struct { BYTE *obj; DWORD handle; xform_t prev, cur, save, disp; int kind, live, swapped; } wmov_t;
typedef struct { BYTE *obj; DWORD stamp; int idx; } whent_t;
static whent_t g_wh[WST_H], g_wh2[WST_H];          /* tick-start poses / moving-set dedupe + liveness */
static struct { BYTE *obj; xform_t pose; } g_wa[WST_N];
static int g_wa_n;
static wmov_t g_wm[WST_N];
static int g_wm_n;
static DWORD g_wh_stamp = 1;

static unsigned wh_slot(BYTE *o) { return (unsigned)((((DWORD)(DWORD_PTR)o) >> 3) * 2654435761u) & (WST_H - 1); }
static int wh_find(whent_t *t, BYTE *o, DWORD stamp) {
    unsigned i = wh_slot(o), n;
    for (n = 0; n < WST_H; n++, i = (i + 1) & (WST_H - 1)) {
        if (t[i].stamp != stamp) return -1;
        if (t[i].obj == o) return t[i].idx;
    }
    return -1;
}
static int wh_put(whent_t *t, BYTE *o, DWORD stamp, int idx) {   /* 0 = already there */
    unsigned i = wh_slot(o), n;
    for (n = 0; n < WST_H; n++, i = (i + 1) & (WST_H - 1)) {
        if (t[i].stamp != stamp) { t[i].stamp = stamp; t[i].obj = o; t[i].idx = idx; return 1; }
        if (t[i].obj == o) return 0;
    }
    return 0;
}
static DWORD g_wh2_stamp = 1;

/* every live object: the ticked list 0x54b204 (handle at node+8, resolved as entity_TickAll does), then the projectile
 * lists. cb(obj, handle, kind): kind 0 player, 1 vehicle, 2 projectile, 3 other */
typedef void (*wst_cb)(BYTE *obj, DWORD handle, int kind);
static void wst_walk(wst_cb cb) {
    BYTE *node = *(BYTE **)0x0054b204;
    int guard = 0, i, n;
    while (node && guard++ < 8192) {
        DWORD h = *(DWORD *)(node + 8);
        BYTE *o = ((BYTE *(__cdecl *)(DWORD, const char *))0x0045f0f0)(h, (const char *)0x004f7c5c);
        if (o) {
            int kind = 3;
            if (*(int *)(o + 0x6c) == 1) kind = ((int (__cdecl *)(BYTE *))0x00458bf0)(o) ? 0 : 1;
            cb(o, h, kind);
        }
        node = *(BYTE **)node;
    }
    n = *(int *)0x005a810c;
    if (n < 0 || n > 64) n = 0;
    for (i = 0; i < n; i++) {
        BYTE *par = *(BYTE **)(0x0065528c + i * 0xd0), *p;
        BYTE *heads[2];
        int k;
        heads[0] = par ? *(BYTE **)(par + 0x64) : 0;
        heads[1] = *(BYTE **)(0x00655290 + i * 0xd0);
        for (k = 0; k < 2; k++) {
            guard = 0;
            for (p = heads[k]; p && guard++ < 2048; p = *(BYTE **)(p + 0x60)) cb(p, 0, 2);
        }
    }
}

static void wa_cb(BYTE *o, DWORD h, int kind) {
    (void)h; (void)kind;
    if (g_wa_n >= WST_N) return;
    if (!wh_put(g_wh, o, g_wh_stamp, g_wa_n)) return;      /* listed twice: keep the first */
    g_wa[g_wa_n].obj = o; g_wa[g_wa_n].pose = *(xform_t *)(o + 0x18); g_wa_n++;
}
/* tick start: everything's pose before the sim; also the leak check (a moving object must start the tick where
 * the last tick left it: anything else was written outside the sim - the trainer - or leaked from the render swap) */
static void wst_tick_start(void) {
    int i;
    for (i = 0; i < g_wm_n; i++) {
        xform_t *p = (xform_t *)(g_wm[i].obj + 0x18);
        if (!g_wm[i].live) continue;
        g_wst_local.leak_checks++;
        if (memcmp(p, &g_wm[i].cur, sizeof(xform_t)) != 0) {
            /* the sim pose is not where the last tick left it: the drawn pose (a leak of the swap) or an outside write */
            if (g_wm[i].kind <= 2 && memcmp(p, &g_wm[i].disp, sizeof(xform_t)) == 0) g_wst_local.leak_mismatch++;
            else g_wst_local.ext_writes++;
        }
    }
    if (++g_wh_stamp == 0) g_wh_stamp = 1;
    g_wa_n = 0;
    wst_walk(wa_cb);
}
static double wst_d2(const xform_t *a, const xform_t *b) {
    double x = a->p[0] - b->p[0], y = a->p[1] - b->p[1], z = a->p[2] - b->p[2];
    return x * x + y * y + z * z;
}
static void wm_cb(BYTE *o, DWORD h, int kind) {
    int idx;
    xform_t *now = (xform_t *)(o + 0x18);
    double lim;
    if (g_wm_n >= WST_N) return;
    if (!wh_put(g_wh2, o, g_wh2_stamp, 0)) return;         /* already in this tick's moving set */
    idx = wh_find(g_wh, o, g_wh_stamp);
    if (idx < 0) return;                                     /* spawned during the tick: drawn where it is */
    if (memcmp(&g_wa[idx].pose, now, sizeof(xform_t)) == 0) return;   /* did not move */
    lim = kind <= 1 ? 12.0 * 12.0 : 150.0 * 150.0;           /* a respawn / teleport, not motion */
    if (wst_d2(&g_wa[idx].pose, now) > lim) return;
    g_wm[g_wm_n].obj = o; g_wm[g_wm_n].handle = h; g_wm[g_wm_n].kind = kind;
    g_wm[g_wm_n].prev = g_wa[idx].pose; g_wm[g_wm_n].cur = *now;
    g_wm[g_wm_n].live = 1; g_wm[g_wm_n].swapped = 0;
    g_wm_n++;
}
static void wst_tick_end(void) {
    g_wm_n = 0;
    if (++g_wh2_stamp == 0) g_wh2_stamp = 1;
    wst_walk(wm_cb);
    g_wst_local.moving_last = (DWORD)g_wm_n;
    if ((DWORD)g_wm_n > g_wst_local.moving_max) g_wst_local.moving_max = (DWORD)g_wm_n;
}

/* rotation rows lerped, then re-orthonormalised keeping each row's (lerped) length: vehicles are orthonormal, other
 * objects may carry a scale. More than ~60 degrees in one tick: the newer rotation (a lerp would collapse). */
static void wst_lerp(xform_t *o, const xform_t *a, const xform_t *b, float t) {
    float la[3], lb[3], l[3];
    int i, k;
    *o = *b;
    for (i = 0; i < 3; i++) o->p[i] = a->p[i] + (b->p[i] - a->p[i]) * (double)t;
    for (k = 0; k < 3; k++) {
        la[k] = sqrtf(v3dot(a->r + 3 * k, a->r + 3 * k)); lb[k] = sqrtf(v3dot(b->r + 3 * k, b->r + 3 * k));
        if (la[k] < 1e-6f || lb[k] < 1e-6f) return;
        l[k] = la[k] + (lb[k] - la[k]) * t;
    }
    if (v3dot(a->r + 6, b->r + 6) < 0.5f * la[2] * lb[2] || v3dot(a->r + 3, b->r + 3) < 0.5f * la[1] * lb[1]) return;
    {
        xform_t u = *a, v = *b, w;
        for (k = 0; k < 3; k++) for (i = 0; i < 3; i++) { u.r[3 * k + i] /= la[k]; v.r[3 * k + i] /= lb[k]; }
        xf_lerp(&w, &u, &v, t);
        for (k = 0; k < 3; k++) for (i = 0; i < 3; i++) o->r[3 * k + i] = w.r[3 * k + i] * l[k];
    }
}

static int g_st_swapped;
static void wst_swap_in(void) {
    int i;
    if (g_st_swapped) return;
    for (i = 0; i < g_wm_n; i++) {
        wmov_t *m = &g_wm[i];
        xform_t *p, d;
        m->swapped = 0;
        if (!m->live) continue;
        p = (xform_t *)(m->obj + 0x18);
        if (memcmp(p, &m->cur, sizeof(xform_t)) != 0) { g_wst_local.ext_writes++; m->live = 0; continue; }   /* written outside the sim */
        m->save = *p;
        if (m->kind <= 1) xf_lerp(&d, &m->prev, &m->cur, g_wst_local.alpha);
        else wst_lerp(&d, &m->prev, &m->cur, g_wst_local.alpha);
        *p = d; m->disp = d; m->swapped = 1;
    }
    g_st_swapped = 1;
    g_wst_local.swaps++;
}
static void wst_swap_out(int revalidate);
static void live_cb(BYTE *o, DWORD h, int kind) { (void)kind; wh_put(g_wh2, o, g_wh2_stamp, (int)h); }
static void wst_swap_out(int revalidate) {
    int i;
    if (!g_st_swapped) return;
    if (revalidate) {                                        /* the render pass may destroy (flamer kill) */
        if (++g_wh2_stamp == 0) g_wh2_stamp = 1;
        wst_walk(live_cb);
    }
    for (i = 0; i < g_wm_n; i++) {
        wmov_t *m = &g_wm[i];
        if (!m->swapped) continue;
        if (revalidate && m->kind != 2) {
            int h = wh_find(g_wh2, m->obj, g_wh2_stamp);
            if (h < 0 || (DWORD)h != m->handle) { m->live = 0; m->swapped = 0; g_wst_local.dead_after_render++; continue; }
        }
        *(xform_t *)(m->obj + 0x18) = m->save; m->swapped = 0;
    }
    g_st_swapped = 0;
}

/* ---- judder census (also usable under I76_RENDER_INTERP: I76_JUDDER_CENSUS=1) ----------------------------------- */
#define JC_N 4096
static struct { BYTE *obj; double p[3]; DWORD moved; int kind; } g_jc[JC_N];
static DWORD g_jc_frame;
static double g_jc_cam[3]; static DWORD g_jc_cam_moved;
static void jc_cb(BYTE *o, DWORD h, int kind) {
    unsigned i = wh_slot(o) & (JC_N - 1), n;
    double *p = (double *)(o + 0x40);
    (void)h;
    for (n = 0; n < 64; n++, i = (i + 1) & (JC_N - 1)) {
        if (g_jc[i].obj == o || g_jc[i].obj == 0) break;
        if (g_jc_frame - g_jc[i].moved > 600) break;         /* long-idle slot: reuse */
    }
    if (n == 64) return;
    if (g_jc[i].obj != o) { g_jc[i].obj = o; memcpy(g_jc[i].p, p, 24); g_jc[i].moved = 0; g_jc[i].kind = kind; return; }
    if (kind == 2) g_wst_local.proj_seen++; else g_wst_local.objs_seen++;
    if (memcmp(g_jc[i].p, p, 24) != 0) { g_wst_local.jud_moved[kind]++; g_jc[i].moved = g_jc_frame; memcpy(g_jc[i].p, p, 24); }
    else if (g_jc[i].moved && g_jc_frame - g_jc[i].moved <= 12) g_wst_local.jud_stall[kind]++;
}
static void judder_census(void) {
    double *c = (double *)0x004c2890;                       /* camera +0x160: eye position (sound_UpdateListener) */
    g_jc_frame++;
    g_wst_local.census_frames++;
    wst_walk(jc_cb);
    if (memcmp(g_jc_cam, c, 24) != 0) { g_wst_local.cam_moved++; g_jc_cam_moved = g_jc_frame; memcpy(g_jc_cam, c, 24); }
    else if (g_jc_cam_moved && g_jc_frame - g_jc_cam_moved <= 12) g_wst_local.cam_stall++;
}

/* ---- camera ------------------------------------------------------------------------------------------------------ */
static BYTE *g_st_cam_tramp;
static xform_t g_st_simcam[2]; static DWORD g_st_simcam_tick[2];   /* [1] = newest sim-window camera set */
static DWORD g_st_cam_disp_frame;
static int __cdecl st_cam_set(BYTE *cam, xform_t *t) {
    if (cam == (BYTE *)0x004c2730 && t) {
        if (g_st_in_disp) { g_st_cam_disp_frame = g_wst_local.dframes; g_wst_local.cam_disp_sets++; }
        else {
            if (g_st_simcam_tick[1] != g_wst_local.ticks) { g_st_simcam[0] = g_st_simcam[1]; g_st_simcam_tick[0] = g_st_simcam_tick[1]; }
            g_st_simcam[1] = *t; g_st_simcam_tick[1] = g_wst_local.ticks;
        }
    }
    return ((int (__cdecl *)(BYTE *, xform_t *))g_st_cam_tramp)(cam, t);
}

/* ---- clock -------------------------------------------------------------------------------------------------------- */
static void st_clock_set(float sdt, float dt) {
    *(volatile float *)0x004fe420 = sdt; *(volatile float *)0x004fe424 = 1.0f / sdt;
    *(volatile float *)0x004fe428 = dt;  *(volatile float *)0x004fe42c = 1.0f / dt;
}
static void st_clock_tick(void) { st_clock_set(g_st_clk[0], g_st_clk[2]); }

static void wst_publish(void) {
    if (g_wst) memcpy((void *)g_wst, &g_wst_local, sizeof(wst_shm_t));
}

/* top of the frame hook: the sim clock back to the tick's values (the display window changed them), before telemetry
 * and the frame log read it */
static void simtick_top(void) {
    if (g_st_clk[0] > 0.0f) st_clock_tick();
    g_st_in_disp = 0;
}

/* in place of the frame hook's simclock_Update call */
static void simtick_clock(void) {
    LARGE_INTEGER q;
    double d;
    int gameplay = *(volatile DWORD *)0x00504c1c != 0 && (*(volatile BYTE *)0x004fe534 & 0x3e) == 0;
    QueryPerformanceCounter(&q);
    d = g_st_q.QuadPart ? (double)(q.QuadPart - g_st_q.QuadPart) / (double)g_qpf.QuadPart : 0.0;
    g_st_q = q;
    g_st_disp_dt = (float)(d < 0.001 ? 0.001 : d > 0.2 ? 0.2 : d);
    g_wst_local.dframes++;
    if (!gameplay) {                                         /* shell / pause: stock, every frame */
        ((void (__cdecl *)(void))0x0049c920)();
        g_st_now = 1; g_st_acc = g_st_T; g_st_since = 0.0; g_wm_n = 0;
        g_st_clk[0] = 0.0f;
        g_tick20 = 1;
        wst_publish();
        return;
    }
    g_wst_local.gameplay_frames++;
    if (*(volatile int *)0x005a7e18 == 0 && g_st_acc < (double)g_st_T) g_st_acc = (double)g_st_T;   /* simclock_Init ran: a new mission */
    g_wst_local.wall_s += d > 0.25 ? 0.25 : d;
    g_st_acc += d > 0.25 ? 0.25 : d;
    g_st_since += d;
    if (g_st_acc >= (double)g_st_T) {
        volatile float *acc = (volatile float *)0x005a7e14, *tm = (volatile float *)0x005a7e74, *stm = (volatile float *)0x005a7e70;
        float acc0 = *acc, tm0 = *tm, stm0 = *stm;
        int warm = *(volatile int *)0x005a7e18 >= *(volatile int *)0x004be990;   /* accum_dt counts from the 4th frame */
        g_st_acc -= (double)g_st_T;
        if (g_st_acc >= (double)g_st_T) {                    /* fell behind (a hitch): one tick per display frame */
            double k = floor(g_st_acc / (double)g_st_T);
            g_wst_local.multi_due++; g_wst_local.dropped_s += k * (double)g_st_T; g_st_acc -= k * (double)g_st_T;
        }
        g_st_now = 1;
        wst_tick_start();
        ((void (__cdecl *)(void))0x0049c920)();             /* simclock_Update: frame count, last tick, first-frames latch */
        st_clock_set(g_st_T, g_st_T);
        *tm = tm0 + g_st_T; *stm = stm0 + g_st_T;
        if (warm) *acc = acc0 + g_st_T;
        g_st_clk[0] = g_st_T; g_st_clk[1] = 1.0f / g_st_T; g_st_clk[2] = g_st_T; g_st_clk[3] = 1.0f / g_st_T;
        g_wst_local.ticks++;
        g_st_since = 0.0;
        g_tick20 = 1; g_tick20_n++; g_acc20 = 0.0f;
        radar_ping_flush();
    } else {
        g_st_now = 0;
        (*(volatile DWORD *)0x005a7e1c)++;                  /* display-frame count for the render-side readers */
        g_wst_local.nontick++;
        g_tick20 = 0; g_acc20 = (float)g_st_since;
    }
    g_wst_local.alpha = (float)(g_st_acc / (double)g_st_T);
    if (g_wst_local.alpha > 1.0f) g_wst_local.alpha = 1.0f;
    if (g_st_cosmetic) {                                     /* per-call cosmetics at the tick's per-second rate */
        float k = g_st_disp_dt / g_st_T;
        g_cloud_u = 1.0f * k; g_cloud_v = -1.0f * k; g_cam_rate = -0.017453292f * k; g_zoom_rate = -0.01f * k;
    }
    if (g_st_logper && GetTickCount() - g_st_lastlog >= g_st_logper) {
        g_st_lastlog = GetTickCount();
        mlog("  sim-tick: %lu ticks / %.1f s gameplay (%.3f /s), %lu display frames; gates TickAll %lu Collide %lu AI %lu Proj %lu; "
             "player steps hist 0:%lu 1:%lu 2:%lu 3:%lu far:%lu (%.2f ms); moving %lu (max %lu); leak %lu/%lu ext %lu; dropped %.3f s",
             (unsigned long)g_wst_local.ticks, g_wst_local.wall_s, g_wst_local.wall_s > 0 ? g_wst_local.ticks / g_wst_local.wall_s : 0.0,
             (unsigned long)g_wst_local.dframes, (unsigned long)g_wst_local.gate[3], (unsigned long)g_wst_local.gate[1],
             (unsigned long)g_wst_local.gate[7], (unsigned long)g_wst_local.gate[9],
             (unsigned long)g_wst_local.pl_hist[0], (unsigned long)g_wst_local.pl_hist[1], (unsigned long)g_wst_local.pl_hist[2],
             (unsigned long)g_wst_local.pl_hist[3], (unsigned long)g_wst_local.pl_hist[5], g_wst_local.pl_step_ms,
             (unsigned long)g_wst_local.moving_last, (unsigned long)g_wst_local.moving_max, (unsigned long)g_wst_local.leak_mismatch,
             (unsigned long)g_wst_local.leak_checks, (unsigned long)g_wst_local.ext_writes, g_wst_local.dropped_s);
    }
    wst_publish();
}

/* ---- gates --------------------------------------------------------------------------------------------------------- */
#define ST_GATE0(i) static void __cdecl st_gate##i(void) { if (g_st_now) { g_wst_local.gate[i]++; ((void (__cdecl *)(void))g_stc[i])(); } }
ST_GATE0(0) ST_GATE0(1) ST_GATE0(2) ST_GATE0(6) ST_GATE0(8) ST_GATE0(9) ST_GATE0(10) ST_GATE0(11)
static void __cdecl st_gate3(void) {                       /* entity_TickAll */
    if (!g_st_now) return;
    g_wst_local.gate[3]++;
    ((void (__cdecl *)(void))g_stc[3])();
}
static int __cdecl st_gate4(void) { if (!g_st_now) return 0; g_wst_local.gate[4]++; return ((int (__cdecl *)(void))g_stc[4])(); }
static int __cdecl st_gate5(void) { if (!g_st_now) return 0; g_wst_local.gate[5]++; return ((int (__cdecl *)(void))g_stc[5])(); }
static void __cdecl st_gate7(DWORD a) { if (g_st_now) { g_wst_local.gate[7]++; ((void (__cdecl *)(DWORD))g_stc[7])(a); } }

/* the vehicle class tick (counting only). StepperNext counts the stepper's +8 down to 0 during the tick, so the
 * substep count is read right after simclock_StepperBegin (its one call in entity_TickVehicle, 0x463888); a tick with
 * no StepperBegin took the far path (0x43a3c0, one whole-tick step). */
static DWORD g_st_vtick_prev, g_st_begin_prev;
static int g_st_begin_cnt = -1; static float g_st_begin_step;
static void __cdecl st_stepper_begin(float *stepper) {
    ((void (__cdecl *)(float *))g_st_begin_prev)(stepper);
    g_st_begin_cnt = ((int *)stepper)[2]; g_st_begin_step = stepper[1];
}
static void __cdecl st_vehicle_tick(BYTE *obj) {
    BYTE *veh = *(BYTE **)(obj + 0x70);
    int isfar = 0, cnt;
    g_st_begin_cnt = -1;
    ((void (__cdecl *)(BYTE *))g_st_vtick_prev)(obj);
    if (!veh) return;
    cnt = g_st_begin_cnt;
    if (cnt < 0) { isfar = 1; cnt = 0; }
    g_wst_local.veh_ticks++;
    g_wst_local.veh_hist[isfar ? 5 : (cnt > 4 ? 4 : cnt)]++;
    if (((int (__cdecl *)(BYTE *))0x00458bf0)(obj)) {
        g_wst_local.pl_hist[isfar ? 5 : (cnt > 4 ? 4 : cnt)]++;
        if (!isfar) g_wst_local.pl_step_ms = g_st_begin_step * 1000.0f;
    }
}

/* ---- display window ------------------------------------------------------------------------------------------------ */
static void __cdecl st_cam_wrap(void) {
    void (__cdecl *mode)(void) = *(void (__cdecl **)(void))0x004c2720;
    if (g_st_now && g_st_clk[0] > 0.0f) wst_tick_end();     /* the sim block is done: poses after the tick */
    if (g_st_now && g_lat_step_fn) g_lat_step_fn();
    g_st_in_disp = 1;
    if (g_st_clk[0] > 0.0f) st_clock_set(g_st_disp_dt, g_st_disp_dt);   /* camera code: the display frame's dt */
    wst_swap_in();
    if (mode) mode();
    wst_swap_out(0);
}
static void __cdecl st_render_wrap(void *cam) {
    int camx = 0;
    xform_t cx;
    wst_swap_in();
    if (g_st_cam_disp_frame != g_wst_local.dframes && g_st_simcam_tick[1] == g_wst_local.ticks &&
        g_st_simcam_tick[0] + 1 == g_st_simcam_tick[1] && g_st_cam_tramp) {   /* a sim-set (script) camera: between ticks */
        xf_lerp(&cx, &g_st_simcam[0], &g_st_simcam[1], g_wst_local.alpha);
        g_st_in_disp = 2;
        ((int (__cdecl *)(BYTE *, xform_t *))g_st_cam_tramp)((BYTE *)0x004c2730, &cx);
        camx = 1; g_wst_local.simcam_interp++;
    }
    {   /* the player as drawn (I76_BREAKABLE_BOX=4 reads it) */
        int i;
        for (i = 0; i < g_wm_n; i++) if (g_wm[i].kind == 0 && g_wm[i].swapped) {
            BYTE *o = g_wm[i].obj; double *p = (double *)(o + 0x40);
            if (g_pld_frame == g_frame - 1 && g_pld_obj == o) memcpy(g_pld_prev, g_pld_p, 24); else memcpy(g_pld_prev, p, 24);
            memcpy(g_pld_p, p, 24); memcpy(g_pld_r, o + 0x18, 36); g_pld_obj = o; g_pld_frame = g_frame;
            break;
        }
    }
    judder_census();
    if (g_lat_draw_fn) g_lat_draw_fn();
    g_idbg.flame_hits = g_idbg_flame_hits; g_idbg.flame_dmg = g_idbg_flame_dmg;
    g_wst_local.flame_hits = g_idbg_flame_hits; g_wst_local.flame_dmg = g_idbg_flame_dmg;
    g_wst_local.ping_req = g_idbg_ping_req; g_wst_local.ping_play = g_idbg_ping_play;
    ((void (__cdecl *)(void *))0x00401c90)(cam);
    if (camx) ((int (__cdecl *)(BYTE *, xform_t *))g_st_cam_tramp)((BYTE *)0x004c2730, &g_st_simcam[1]);
    wst_swap_out(g_st_now);
    g_st_in_disp = 1;
    wst_publish();
}
/* the flamer's main-pass update on a tick frame: the tick's clock (its hit test reads the sim rate), damage allowed */
static void __cdecl st_flame_main(BYTE *cam) {
    float save[4];
    int tick = g_tick20 && g_st_clk[0] > 0.0f;
    save[0] = *(volatile float *)0x004fe420; save[1] = *(volatile float *)0x004fe424;
    save[2] = *(volatile float *)0x004fe428; save[3] = *(volatile float *)0x004fe42c;
    if (tick) st_clock_tick();
    g_flame_dmg_ok = g_tick20;
    ((void (__cdecl *)(BYTE *))0x00443fc0)(cam);
    g_flame_dmg_ok = 0;
    if (tick) {
        *(volatile float *)0x004fe420 = save[0]; *(volatile float *)0x004fe424 = save[1];
        *(volatile float *)0x004fe428 = save[2]; *(volatile float *)0x004fe42c = save[3];
    }
}

/* repoint a `call rel32` at site to wrap, keeping whatever it called (stock target expected; another wrapper is
 * chained and logged). Returns 1 on success, 0 if the site is not a call. */
static int st_call_site(DWORD site, DWORD stock, void *wrap, DWORD *chain, const char *what) {
    BYTE *p = (BYTE *)(DWORD_PTR)site, o[5], w[5] = { 0xE8 };
    LONG rel;
    DWORD tgt;
    if (p[0] != 0xE8) { mlog("  sim-tick: %s at 0x%08lX is not a call - not patched", what, (unsigned long)site); return 0; }
    memcpy(o, p, 5);
    memcpy(&rel, p + 1, 4); tgt = site + 5 + (DWORD)rel;
    if (tgt != stock) mlog("  sim-tick: %s at 0x%08lX already calls 0x%08lX (stock 0x%08lX) - chained", what, (unsigned long)site, (unsigned long)tgt, (unsigned long)stock);
    if (chain) *chain = tgt;
    rel = (LONG)((DWORD_PTR)wrap - (site + 5)); memcpy(w + 1, &rel, 4);
    if (!patch_bytes(site, o, w, 5, what)) return 0;
    return memcmp(p, w, 5) == 0;                             /* read back */
}

static void apply_simtick(void) {
    char v[24];
    double ms;
    int n = 0, g = 0, h = 0, c = 0;
    if (!env_str("I76_SIM_TICK_MS", v, sizeof(v))) return;
    ms = atof(v);
    if (ms < 10.0 || ms > 100.0) { mlog("  sim-tick: '%s' is not 10..100 ms - off", v); return; }
    if (g_fixed_step > 0.0f || g_interp || g_ratefix) {
        mlog("  sim-tick: NOT applied - excludes I76_FIXED_STEP / I76_RENDER_INTERP / I76_FRAMERATE_FIXES (one of them is on)"); return;
    }
    if (!g_qpf.QuadPart) { QueryPerformanceFrequency(&g_qpf); QueryPerformanceCounter(&g_qp0); }
    install_frame_hook();
    if (!g_frame_hook) { mlog("  sim-tick: frame hook missing - off"); return; }
    g_st_T = (float)(ms / 1000.0);
    g_ref_dt = g_st_T; g_ref_rate = 1.0f / g_st_T;           /* the reused draw-side wrappers: flamer dt floor, smoke */
    g_st_cosmetic = env_flag("I76_SIM_TICK_COSMETIC", 8, 1);
    g_st_logper = (DWORD)env_int("I76_SIM_TICK_LOG", 8, 0) * 1000u;
    {   /* the sim block's call sites */
        static const struct { DWORD site, stock; int gi; const char *what; } gs[12] = {
            { 0x004039bd, 0x0044d9e0, 0, "input_UpdateControls call" }, { 0x00403a12, 0x004349c0, 1, "physics_CollideAll call" },
            { 0x00403a1c, 0x0044dec0, 2, "input_ProcessFrame call" },   { 0x00403d86, 0x00461c80, 3, "entity_TickAll call" },
            { 0x00403da6, 0x004515e0, 4, "net_RegenPointTick call (a)" }, { 0x00403dd0, 0x004515e0, 5, "net_RegenPointTick call (b)" },
            { 0x00403dd5, 0x00461d50, 6, "entity_PostTickAll call" },   { 0x00403ddf, 0x0040a320, 7, "ai_FrameTick call" },
            { 0x00403de7, 0x00462a90, 8, "entity_TickTurretFire call" }, { 0x00403dec, 0x004a0410, 9, "weapon_UpdateProjectiles call" },
            { 0x00403df6, 0x004a4130, 10, "weapon_Update call" },        { 0x00403dfb, 0x0044af80, 11, "image_UpdateTexAnims call" } };
        void *w[12];
        int i;
        w[0] = (void *)st_gate0; w[1] = (void *)st_gate1; w[2] = (void *)st_gate2; w[3] = (void *)st_gate3;
        w[4] = (void *)st_gate4; w[5] = (void *)st_gate5; w[6] = (void *)st_gate6; w[7] = (void *)st_gate7;
        w[8] = (void *)st_gate8; w[9] = (void *)st_gate9; w[10] = (void *)st_gate10; w[11] = (void *)st_gate11;
        for (i = 0; i < 12; i++) g += st_call_site(gs[i].site, gs[i].stock, w[gs[i].gi], &g_stc[gs[i].gi], gs[i].what);
    }
    if (g != 12) {                                           /* all or nothing: undo is not attempted, so refuse loudly */
        mlog("  sim-tick: only %d/12 sim gates patched - the tick stays OFF (gates pass through)", g);
        g_st_now = 1;
        return;
    }
    {   /* display window: camera mode call, render call, camera SetTransform detour, vehicle class tick (counting) */
        static const BYTE camu_old[6] = { 0xFF, 0x15, 0x20, 0x27, 0x4C, 0x00 };   /* call [0x4c2720] at 0x403e16 */
        static const BYTE cam_old[6]  = { 0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF8 };   /* 0x472990 entry */
        static const BYTE tick_old[4] = { 0x00, 0x38, 0x46, 0x00 };                /* 0x463800 in the class table */
        BYTE camu_new[6] = { 0xE8, 0, 0, 0, 0, 0x90 }, cam_new[6] = { 0xE9, 0, 0, 0, 0, 0x90 }, tick_new[4];
        LONG rel; DWORD a;
        rel = (LONG)((DWORD_PTR)st_cam_wrap - (0x00403e16 + 5)); memcpy(camu_new + 1, &rel, 4);
        h += patch_bytes(0x00403e16, camu_old, camu_new, 6, "camera mode call (sim-tick)") && memcmp((void *)0x00403e16, camu_new, 6) == 0;
        h += st_call_site(0x00403e69, 0x00401c90, (void *)st_render_wrap, 0, "renderer_DrawFrame call (sim-tick)");
        g_st_cam_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
        if (g_st_cam_tramp && memcmp((void *)0x00472990, cam_old, 6) == 0) {
            memcpy(g_st_cam_tramp, cam_old, 6); g_st_cam_tramp[6] = 0xE9;
            rel = (LONG)(0x00472996 - ((DWORD_PTR)g_st_cam_tramp + 11)); memcpy(g_st_cam_tramp + 7, &rel, 4);
            rel = (LONG)((DWORD_PTR)st_cam_set - (0x00472990 + 5)); memcpy(cam_new + 1, &rel, 4);
            h += patch_bytes(0x00472990, cam_old, cam_new, 6, "camera SetTransform entry (sim-tick)") && memcmp((void *)0x00472990, cam_new, 6) == 0;
        } else { g_st_cam_tramp = 0; mlog("  sim-tick: camera SetTransform entry not stock - script cameras not interpolated"); }
        if (memcmp((void *)0x004f7788, tick_old, 4) == 0) {
            g_st_vtick_prev = 0x00463800;
            a = (DWORD)(DWORD_PTR)st_vehicle_tick; memcpy(tick_new, &a, 4);
            h += patch_bytes(0x004f7788, tick_old, tick_new, 4, "vehicle tick class slot (sim-tick count)");
            st_call_site(0x00463888, 0x0049cc20, (void *)st_stepper_begin, &g_st_begin_prev, "StepperBegin call in entity_TickVehicle (sim-tick count)");
        }
    }
    {   /* sim logic inside draw code, held to the tick (wrappers shared with I76_FRAMERATE_FIXES) */
        static const struct { DWORD site, stock; void *wrap; const char *what; } cs[] = {
            { 0x00401cec, 0x00443e90, (void *)flame_age_wrap,    "flamer ageing (software)" },
            { 0x00401fcc, 0x00443e90, (void *)flame_age_wrap,    "flamer ageing (hardware)" },
            { 0x00401e23, 0x00443fc0, (void *)st_flame_main,     "flamer update, main pass (software)" },
            { 0x004020e8, 0x00443fc0, (void *)st_flame_main,     "flamer update, main pass (hardware)" },
            { 0x00443fca, 0x0049c8b0, (void *)step20_dt,         "flamer update dt" },
            { 0x004357c3, 0x004a8240, (void *)flame_damage_wrap, "flamer damage" },
            { 0x0044471d, 0x0049ead0, (void *)flame_expl_wrap,   "flamer hit explosion" },
            { 0x00401e50, 0x004414a0, (void *)smoke_update_wrap, "smoke puffs (software)" },
            { 0x0040211a, 0x004414a0, (void *)smoke_update_wrap, "smoke puffs (hardware)" },
            { 0x004414b9, 0x0049c8b0, (void *)step20_dt,         "smoke puff dt" },
            { 0x00401e35, 0x00442ba0, (void *)trails_wrap,       "missile trails (software)" },
            { 0x004020ff, 0x00442ba0, (void *)trails_wrap,       "missile trails (hardware)" },
            { 0x004605ee, 0x004250f0, (void *)radar_ping_wrap,   "radar ping" },
            { 0x004608f1, 0x004250f0, (void *)radar_ping_wrap,   "radar ping (2)" } };
        int i;
        for (i = 0; i < (int)(sizeof(cs) / sizeof(cs[0])); i++) n += st_call_site(cs[i].site, cs[i].stock, cs[i].wrap, 0, cs[i].what);
    }
    if (g_st_cosmetic) {   /* display-rate cosmetics: per-call constants at the tick's per-second rate */
        static const BYTE cu_old[6] = { 0xD9, 0x05, 0xC4, 0xC4, 0x4B, 0x00 }, cv_old[6] = { 0xD9, 0x05, 0x00, 0xC5, 0x4B, 0x00 };
        static const BYTE fl_old[6] = { 0xD8, 0x0D, 0x28, 0xC5, 0x4B, 0x00 }, zm_old[6] = { 0xD8, 0x0D, 0xAC, 0xC5, 0x4B, 0x00 };
        static const DWORD fl_sites[4] = { 0x00405bd0, 0x00405c1c, 0x004061e7, 0x00406233 };
        BYTE cu_new[6] = { 0xD9, 0x05 }, cv_new[6] = { 0xD9, 0x05 }, fl_new[6] = { 0xD8, 0x0D }, zm_new[6] = { 0xD8, 0x0D };
        DWORD a; int i;
        a = (DWORD)(DWORD_PTR)&g_cloud_u; memcpy(cu_new + 2, &a, 4);
        a = (DWORD)(DWORD_PTR)&g_cloud_v; memcpy(cv_new + 2, &a, 4);
        a = (DWORD)(DWORD_PTR)&g_cam_rate; memcpy(fl_new + 2, &a, 4);
        a = (DWORD)(DWORD_PTR)&g_zoom_rate; memcpy(zm_new + 2, &a, 4);
        c += patch_bytes(0x00405461, cu_old, cu_new, 6, "cloud scroll u (sim-tick)");
        c += patch_bytes(0x00405484, cv_old, cv_new, 6, "cloud scroll v (sim-tick)");
        for (i = 0; i < 4; i++) c += patch_bytes(fl_sites[i], fl_old, fl_new, 6, "free-look rate (sim-tick)");
        c += patch_bytes(0x00408a3f, zm_old, zm_new, 6, "zoom rate (sim-tick)");
    }
    {
        HANDLE m = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(wst_shm_t), "Local\\I76SimTick");
        if (m) g_wst = (volatile wst_shm_t *)MapViewOfFile(m, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(wst_shm_t));
        g_wst_local.magic = 0x31545357u; g_wst_local.version = 1; g_wst_local.tick_s = g_st_T;
        wst_publish();
    }
    g_simtick = 1; g_st_now = 1;
    g_jc_on = 1;
    mlog("  sim-tick: ON - whole sim every %.3f ms (%.3f ticks/s; vehicle stepper count %d x %.2f ms); %d/12 sim gates, %d/4 display hooks, "
         "%d/14 draw-side holds, %d/7 cosmetic sites (I76_SIM_TICK_COSMETIC=%d); shm Local\\I76SimTick %s",
         ms, 1000.0 / ms, (int)(g_st_T * 20.0f) + 1, ms / (double)((int)(g_st_T * 20.0f) + 1), g, h, n, c, g_st_cosmetic,
         g_wst ? "mapped" : "MISSING");
}

/* I76_JUDDER_CENSUS=1 without the tick (under I76_RENDER_INTERP: render_wrap calls judder_census): the same counters */
static void apply_judder_census(void) {
    if (g_simtick || !env_present("I76_JUDDER_CENSUS")) return;
    {
        HANDLE m = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(wst_shm_t), "Local\\I76SimTick");
        if (m) g_wst = (volatile wst_shm_t *)MapViewOfFile(m, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(wst_shm_t));
        g_wst_local.magic = 0x31545357u; g_wst_local.version = 1; g_wst_local.tick_s = g_fixed_step;
    }
    g_jc_on = 1;
    mlog("  judder-census: on (%s); shm %s", g_interp ? "render-interp render wrap" : "NO render wrap - nothing counted", g_wst ? "mapped" : "MISSING");
}
static void judder_census_publish(void) { g_wst_local.dframes = g_frame; wst_publish(); }
