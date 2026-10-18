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
    DWORD early_ticks, early_kb, early_lab, early_blocked;   /* I76_SIM_TICK_INPUT=1 (version 2) */
    /* version 3 (2026-10-18 tick-gaps): joystick watch, projectile spawn census / drawing, flamer census */
    DWORD early_joy, joy_watch_calls, joy_watch_ids, joy_watch_us;   /* early ticks from a joystick change; watcher joyGetPosEx calls, ids watched last, QPC us spent */
    DWORD jud_stall_pnew, proj_spawned, proj_spawn_drawn, proj_vchk_n;   /* stalls of projectiles spawned in the last tick; spawns; spawns drawn moving; velocity checks */
    float proj_verr[3]; DWORD proj_age0;                     /* sum of |v_est - v_next| / |v_next| per candidate (rows / fwd x |v| / fwd x speed); spawns with age 0 */
    DWORD proj_vok[3], proj_vskip;                           /* checks within 10 % per candidate; spawns without a usable velocity */
    DWORD flame_amt, flame_upd, flame_seg_sum, flame_seg_n;  /* flamer census (strlkproxy.c flame_census_*) */
    float flame_hit_s, pad3;
} wst_shm_t;
static volatile wst_shm_t *g_wst;
static wst_shm_t g_wst_local;

static int st_call_site(DWORD site, DWORD stock, void *wrap, DWORD *chain, const char *what);
static float g_st_T;                 /* tick, s */
static double g_st_acc = 1.0, g_st_since;   /* acc starts high: the first gameplay frame ticks */  /* wall s since the last tick boundary / since the last tick frame */
static LARGE_INTEGER g_st_q;
static float g_st_disp_dt = 0.0083f;
static float g_st_clk[4];            /* sim_dt, sim_rate, dt, rate of the tick (what the sim saw) */
static int g_st_in_disp;             /* inside the display window (camera + render) */
static int g_st_cosmetic = 1;
static DWORD g_st_logper, g_st_lastlog;
static DWORD g_stc[12];              /* chained call targets of the gated sites */

/* ---- I76_SIM_TICK_INPUT=1: input-triggered early tick (lab variant, 2026-10-17 tick-latency lane) ------------------
 * The tick's input latency is the wait for the next tick (uniform 0..T). Sampling the controls every display frame and
 * applying the latest sample at the next tick does not shorten it: the engine already keeps the latest state for the
 * tick (keyboard: input_KeyboardUpdateKeyState 0x44eab0 holds a key's down bit until input_KeyboardPoll 0x44e670 has
 * reported it once, typed keys queue in a 64-entry ring 0x608e60; analog sinks are read at use; key-driven axes ramp
 * by GetDt inside input_UpdateKeyAnalogSink 0x44d780, so running input_UpdateControls per display frame would change
 * the ramp rate). What does shorten it is running the tick when the input arrives: a display frame that sees the
 * player's controls changed since the last tick runs the tick now, borrowing it from the accumulator (acc goes
 * negative, at most one tick outstanding), so the tick grid and the long-run rate are unchanged and every tick is
 * still exactly T of simulation. Drawing: see g_st_seg_early below (blend from the pose about to be drawn).
 * Change detection, per display frame, no game code run: the keyboard driver's down bits 0x6092d0[16] differ from the
 * snapshot taken after the last tick's input_UpdateControls, or a release is pending in 0x6092e0[16]; plus a lab hook
 * (the side build's drive block: a new drive-key sequence).
 * Joysticks (2026-10-18 tick-gaps; I76_SIM_TICK_JOY=0 turns this part off): the engine reads a wheel or pad through
 * winmm, joyGetPosEx (input_JoystickPoll 0x450870, IAT 0x4bc384, only while GetFocus() is its window) from the driver's
 * poll inside input_UpdateControls; DirectInput is used for force feedback only. The proxy's IAT hook on joyGetPosEx
 * (strlkproxy.c, joy routing) records what the engine got for each joystick id during the tick's input_UpdateControls
 * (id, its JOYINFOEX flags, axes, buttons, POV). On a non-tick display frame the watcher calls the same hooked
 * joyGetPosEx (same id and flags; routing and the test pad apply) for each id the engine polled in the last tick and
 * fires the early tick when a button or the POV changed or an axis moved more than a dead band from the engine's
 * reading: I76_SIM_TICK_JOY_DB permille of that axis's range from joyGetDevCapsA (default 10 = 1 %, at least 1 count),
 * so axis noise does not borrow ticks. No game code runs for this; the borrow rule is the keyboard's. */
static int g_st_input, g_st_early_now;
static MMRESULT (WINAPI *g_st_joy_call)(UINT, LPJOYINFOEX);     /* the hooked joyGetPosEx (set by apply_joy_routing) */
static MMRESULT (WINAPI *g_st_joy_caps)(UINT_PTR, LPJOYCAPSA, UINT);
static int g_st_joy_on, g_st_joy_rec, g_st_joy_pm = 10;
static struct { int valid, polled, dbset; DWORD flags, ax[6], buttons, pov, db[6]; } g_sj[16];
static void st_joy_note(UINT id, const JOYINFOEX *j, MMRESULT rc) {   /* from hook_joyGetPosEx while the tick's input runs */
    if (id >= 16 || !j || rc != JOYERR_NOERROR) return;
    g_sj[id].polled = 1; g_sj[id].flags = j->dwFlags;
    g_sj[id].ax[0] = j->dwXpos; g_sj[id].ax[1] = j->dwYpos; g_sj[id].ax[2] = j->dwZpos;
    g_sj[id].ax[3] = j->dwRpos; g_sj[id].ax[4] = j->dwUpos; g_sj[id].ax[5] = j->dwVpos;
    g_sj[id].buttons = j->dwButtons; g_sj[id].pov = j->dwPOV;
}
static void st_joy_db(UINT id) {
    JOYCAPSA c; int k;
    DWORD lo[6], hi[6];
    for (k = 0; k < 6; k++) { lo[k] = 0; hi[k] = 65535; }
    memset(&c, 0, sizeof(c));
    if (g_st_joy_caps && g_st_joy_caps(id, &c, sizeof(c)) == JOYERR_NOERROR) {
        lo[0] = c.wXmin; hi[0] = c.wXmax; lo[1] = c.wYmin; hi[1] = c.wYmax; lo[2] = c.wZmin; hi[2] = c.wZmax;
        lo[3] = c.wRmin; hi[3] = c.wRmax; lo[4] = c.wUmin; hi[4] = c.wUmax; lo[5] = c.wVmin; hi[5] = c.wVmax;
    }
    for (k = 0; k < 6; k++) {
        DWORD r = hi[k] > lo[k] ? hi[k] - lo[k] : 65535, d = (DWORD)(((double)r * g_st_joy_pm) / 1000.0);
        g_sj[id].db[k] = d < 1 ? 1 : d;
    }
    g_sj[id].dbset = 1;
}
static int st_joy_changed(void) {
    static const DWORD axbit[6] = { JOY_RETURNX, JOY_RETURNY, JOY_RETURNZ, JOY_RETURNR, JOY_RETURNU, JOY_RETURNV };
    UINT id; int k, n = 0, hit = 0;
    LARGE_INTEGER q0, q1;
    if (!g_st_joy_on || !g_st_joy_call) return 0;
    QueryPerformanceCounter(&q0);
    for (id = 0; id < 16 && !hit; id++) {
        JOYINFOEX j;
        if (!g_sj[id].valid) continue;
        if (!g_sj[id].dbset) st_joy_db(id);
        memset(&j, 0, sizeof(j)); j.dwSize = sizeof(j); j.dwFlags = g_sj[id].flags;
        n++; g_wst_local.joy_watch_calls++;
        if (g_st_joy_call(id, &j) != JOYERR_NOERROR) continue;
        if ((g_sj[id].flags & JOY_RETURNBUTTONS) && j.dwButtons != g_sj[id].buttons) hit = 1;
        if ((g_sj[id].flags & (JOY_RETURNPOV | JOY_RETURNPOVCTS)) && j.dwPOV != g_sj[id].pov) hit = 1;
        for (k = 0; k < 6 && !hit; k++) {
            DWORD a = (&j.dwXpos)[k], b = g_sj[id].ax[k];
            if ((g_sj[id].flags & axbit[k]) && (a > b ? a - b : b - a) > g_sj[id].db[k]) hit = 1;
        }
    }
    QueryPerformanceCounter(&q1);
    g_wst_local.joy_watch_ids = (DWORD)n;
    g_wst_local.joy_watch_us += (DWORD)((q1.QuadPart - q0.QuadPart) * 1000000 / g_qpf.QuadPart);
    if (hit) g_wst_local.early_joy++;
    return hit;
}
/* Drawing after an early tick (2nd form, after the first boots showed a heading kink of 0.4 deg median, up to 1.5 deg,
 * on the early-tick frame with alpha extrapolated backwards): each moving object is drawn from the pose this frame
 * would have drawn without the early tick (D) to the new tick's pose, with beta = (acc - acc0) / (T - acc0) running
 * 0 -> 1 until the next regular tick (acc0 = the accumulator right after the borrow, negative). That segment is
 * (2 - a) T long and covers (1 - a) of the old tick's motion plus the new one, so steady motion keeps its drawn speed
 * and the drawn pose is continuous on the early frame. */
static int g_st_seg_early, g_we_n, g_we_on;
static double g_st_acc0;
static struct { BYTE *obj; xform_t pose; } g_we[2048];   /* D per object, filled on the early frame (linear search: early ticks only) */
static FILE *g_st_dlog;                      /* I76_SIM_TICK_DRAWLOG=<path>: the player's drawn pose per display frame (lab) */
static BYTE g_st_kb_snap[16];
static int (*g_st_input_peek_fn)(void);     /* lab drive block: nonzero when the harness posted new keys */
static int st_input_changed(void) {
    const BYTE *d0 = (const BYTE *)0x006092d0, *e0 = (const BYTE *)0x006092e0;
    int i;
    if (g_st_input_peek_fn && g_st_input_peek_fn()) { g_wst_local.early_lab++; return 1; }
    if (memcmp(d0, g_st_kb_snap, 16) != 0) { g_wst_local.early_kb++; return 1; }
    for (i = 0; i < 16; i++) if (e0[i]) { g_wst_local.early_kb++; return 1; }
    return st_joy_changed();
}

/* ---- objects ------------------------------------------------------------------------------------------------- */
#define WST_N 2048
#define WST_H 8192
typedef struct { BYTE *obj; DWORD handle; xform_t prev, cur, save, disp, dend; int kind, live, swapped, spawn; } wmov_t;
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

/* ---- projectiles spawned inside a tick (2026-10-18 tick-gaps; I76_SIM_TICK_PROJ) ----------------------------------
 * A projectile fired during a tick has no tick-start pose, so the interpolation cannot place it: it was drawn at its
 * end-of-tick pose E for the whole next display window (a one-tick freeze at the muzzle, which the census counts as a
 * stall whenever the pool hands out a recently moving projectile's address), then moved on from E one tick late like
 * everything else. Its velocity is known at spawn (projectile data, object +0x70: +0x14 velocity in the projectile's
 * own frame, +0x38 the ORDF speed), so I76_SIM_TICK_PROJ=1 (default; 0 = off) draws it moving from E along that velocity during its first
 * window (E -> E + f v T, f = 0.5) and starts the next tick's segment from that drawn pose (E + f v T -> the next
 * tick's pose), so the round leaves the muzzle at once, never moves backwards and catches the one-tick-late timeline
 * of everything else over two windows (half speed for 2 x T, then normal). The sim pose is never changed (drawing
 * only, swapped in and out like every other pose). Census (always on with the tick): spawns, stalls of last-tick spawns,
 * and a check of three velocity readings against the motion of the next tick. */
typedef struct { BYTE *obj; xform_t e; float v[3][3]; int vok; int drawn; double d[3]; } wspawn_t;
static wspawn_t g_wsp[2][512]; static int g_wsp_n[2], g_wsp_cur;   /* [cur] = this tick's spawns, [cur ^ 1] = the last tick's */
static int g_st_proj = 1;                                     /* I76_SIM_TICK_PROJ (default on since 2026-10-18 tick-gaps: 0 = last night's freeze) */
static float g_st_proj_f = 0.5f;
static int g_st_proj_vsel = 0;                               /* which velocity reading the drawing uses (0 rows, 1 fwd x |v|, 2 fwd x speed) */
static int st_proj_vel(BYTE *o, float v[3][3]) {             /* 1 = read; v[0] rows . local v, v[1] forward x |v|, v[2] forward x speed */
    int ok = 0;
#ifdef _MSC_VER
    __try {
#endif
        BYTE *pd = *(BYTE **)(o + 0x70);
        const float *r = (const float *)(o + 0x18), *lv;
        float n[3], f[3], sp, lvn;
        int k, i;
        if (pd && (DWORD_PTR)pd > 0x10000) {
            lv = (const float *)(pd + 0x14); sp = *(const float *)(pd + 0x38);
            for (k = 0; k < 3; k++) { n[k] = sqrtf(v3dot(r + 3 * k, r + 3 * k)); if (n[k] < 1e-6f) n[k] = 1.0f; }
            for (i = 0; i < 3; i++) {
                v[0][i] = lv[0] * r[i] / n[0] + lv[1] * r[3 + i] / n[1] + lv[2] * r[6 + i] / n[2];
                f[i] = r[6 + i] / n[2];
            }
            lvn = sqrtf(v3dot(lv, lv));
            for (i = 0; i < 3; i++) { v[1][i] = f[i] * lvn; v[2][i] = f[i] * sp; }
            ok = lvn > 0.01f && lvn < 5000.0f;   /* also false for NaN */
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { ok = 0; }
#endif
    return ok;
}
static int st_proj_age0(BYTE *o) {
    int z = 0;
#ifdef _MSC_VER
    __try {
#endif
        BYTE *pd = *(BYTE **)(o + 0x70);
        if (pd && (DWORD_PTR)pd > 0x10000) z = *(const float *)(pd + 0x08) - *(const float *)(pd + 0x04) <= 0.0f;
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { z = 0; }
#endif
    return z;
}
static wspawn_t *st_spawn_last(BYTE *o) {
    int i, c = g_wsp_cur ^ 1;
    for (i = 0; i < g_wsp_n[c]; i++) if (g_wsp[c][i].obj == o) return &g_wsp[c][i];
    return 0;
}

static void wm_cb(BYTE *o, DWORD h, int kind) {
    int idx;
    xform_t *now = (xform_t *)(o + 0x18);
    double lim;
    if (g_wm_n >= WST_N) return;
    if (!wh_put(g_wh2, o, g_wh2_stamp, 0)) return;         /* already in this tick's moving set */
    idx = wh_find(g_wh, o, g_wh_stamp);
    if (idx < 0) {                                           /* spawned during the tick */
        wspawn_t *s;
        if (kind != 2 || g_wsp_n[g_wsp_cur] >= 512) return;   /* (vehicles / objects: drawn where they are) */
        s = &g_wsp[g_wsp_cur][g_wsp_n[g_wsp_cur]++];
        s->obj = o; s->e = *now; s->drawn = 0;
        s->vok = st_proj_vel(o, s->v);
        g_wst_local.proj_spawned++;
        if (st_proj_age0(o)) g_wst_local.proj_age0++;
        if (!s->vok) { g_wst_local.proj_vskip++; return; }
        if (g_st_proj) {                                     /* drawn moving from E during its first window */
            wmov_t *m = &g_wm[g_wm_n];
            int i;
            m->obj = o; m->handle = 0; m->kind = 2; m->prev = *now; m->cur = *now; m->dend = *now;
            for (i = 0; i < 3; i++) m->dend.p[i] += (double)s->v[g_st_proj_vsel][i] * (double)g_st_T * (double)g_st_proj_f;
            for (i = 0; i < 3; i++) s->d[i] = m->dend.p[i];
            m->live = 1; m->swapped = 0; m->spawn = 1; s->drawn = 1;
            g_wst_local.proj_spawn_drawn++;
            g_wm_n++;
        }
        return;
    }
    if (memcmp(&g_wa[idx].pose, now, sizeof(xform_t)) == 0) return;   /* did not move */
    lim = kind <= 1 ? 12.0 * 12.0 : 150.0 * 150.0;           /* a respawn / teleport, not motion */
    if (wst_d2(&g_wa[idx].pose, now) > lim) return;
    g_wm[g_wm_n].obj = o; g_wm[g_wm_n].handle = h; g_wm[g_wm_n].kind = kind;
    g_wm[g_wm_n].prev = g_wa[idx].pose; g_wm[g_wm_n].cur = *now; g_wm[g_wm_n].spawn = 0;
    if (kind == 2) {                                         /* spawned in the last tick: check its velocity; continue from its drawn pose */
        wspawn_t *s = st_spawn_last(o);
        if (s && s->vok && memcmp(&s->e, &g_wa[idx].pose, sizeof(xform_t)) == 0) {
            double m3[3], mm, e3[3], ee;
            int c, i;
            for (i = 0; i < 3; i++) m3[i] = (now->p[i] - s->e.p[i]) / (double)g_st_T;
            mm = sqrt(m3[0] * m3[0] + m3[1] * m3[1] + m3[2] * m3[2]);
            if (mm > 0.01) {
                g_wst_local.proj_vchk_n++;
                for (c = 0; c < 3; c++) {
                    for (i = 0; i < 3; i++) e3[i] = (double)s->v[c][i] - m3[i];
                    ee = sqrt(e3[0] * e3[0] + e3[1] * e3[1] + e3[2] * e3[2]) / mm;
                    g_wst_local.proj_verr[c] += (float)(ee > 10.0 ? 10.0 : ee);
                    if (ee < 0.1) g_wst_local.proj_vok[c]++;
                }
                for (i = 0; i < 3; i++) e3[i] = (double)s->v[g_st_proj_vsel][i] - m3[i];
                ee = sqrt(e3[0] * e3[0] + e3[1] * e3[1] + e3[2] * e3[2]) / mm;
                if (s->drawn && ee < 0.5) for (i = 0; i < 3; i++) g_wm[g_wm_n].prev.p[i] = s->d[i];   /* same round: go on from where it was drawn */
            }
        }
    }
    if (g_we_on) {                                           /* after an early tick: blend from what was about to be drawn */
        int j;
        for (j = 0; j < g_we_n; j++) if (g_we[j].obj == o) { g_wm[g_wm_n].prev = g_we[j].pose; break; }
    }
    g_wm[g_wm_n].live = 1; g_wm[g_wm_n].swapped = 0;
    g_wm_n++;
}
static void wst_tick_end(void) {
    g_wm_n = 0;
    if (++g_wh2_stamp == 0) g_wh2_stamp = 1;
    g_wsp_cur ^= 1; g_wsp_n[g_wsp_cur] = 0;                  /* the last tick's spawns stay readable in [cur ^ 1] */
    wst_walk(wm_cb);
    g_we_on = 0; g_we_n = 0;
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

/* the drawing blend factor of this display frame: acc / T, or beta inside an early segment (I76_SIM_TICK_INPUT) */
static float st_alpha(void) {
    double a = g_st_seg_early ? (g_st_acc - g_st_acc0) / ((double)g_st_T - g_st_acc0) : g_st_acc / (double)g_st_T;
    return (float)(a < 0.0 ? 0.0 : a > 1.0 ? 1.0 : a);
}
/* on the early frame, before the tick: the pose each moving object would have been drawn at this frame */
static void st_early_from(void) {
    float a = st_alpha();
    int i;
    g_we_n = 0;
    for (i = 0; i < g_wm_n && g_we_n < 2048; i++) {
        wmov_t *m = &g_wm[i];
        if (!m->live || memcmp((xform_t *)(m->obj + 0x18), &m->cur, sizeof(xform_t)) != 0) continue;   /* written outside the sim */
        g_we[g_we_n].obj = m->obj;
        if (m->kind <= 1) xf_lerp(&g_we[g_we_n].pose, &m->prev, &m->cur, a);
        else wst_lerp(&g_we[g_we_n].pose, &m->prev, m->spawn ? &m->dend : &m->cur, a);
        g_we_n++;
    }
    g_we_on = 1;
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
        else wst_lerp(&d, &m->prev, m->spawn ? &m->dend : &m->cur, g_wst_local.alpha);
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
    else if (g_jc[i].moved && g_jc_frame - g_jc[i].moved <= 12) {
        g_wst_local.jud_stall[kind]++;
        if (kind == 2 && g_simtick) {                        /* a round spawned in the newest tick? */
            int k, c = g_wsp_cur;
            for (k = 0; k < g_wsp_n[c]; k++) if (g_wsp[c][k].obj == o) { g_wst_local.jud_stall_pnew++; break; }
        }
    }
}
static void judder_census(void) {
    double *c = (double *)0x004c2890;                       /* camera +0x160: eye position (sound_UpdateListener) */
    g_jc_frame++;
    g_wst_local.census_frames++;
    wst_walk(jc_cb);
    if (memcmp(g_jc_cam, c, 24) != 0) { g_wst_local.cam_moved++; g_jc_cam_moved = g_jc_frame; memcpy(g_jc_cam, c, 24); }
    else if (g_jc_cam_moved && g_jc_frame - g_jc_cam_moved <= 12) g_wst_local.cam_stall++;
}

/* I76_SIM_TICK_PROJLOG=<path> (lab instrument, 2026-10-18): one line per projectile per drawn frame - wall s, display
 * frame, tick frame, early tick, object, drawn x y z - for the continuity check of tracers and missiles */
static FILE *g_st_plog; static DWORD g_st_plog_n; static LARGE_INTEGER g_st_plog_q;
static void st_plog_cb(BYTE *o, DWORD h, int kind) {
    double *p = (double *)(o + 0x40);
    (void)h;
    if (kind != 2) return;
    fprintf(g_st_plog, "%.6f,%lu,%d,%d,%08lx,%.3f,%.3f,%.3f\n", (double)(g_st_plog_q.QuadPart - g_qp0.QuadPart) / (double)g_qpf.QuadPart,
            (unsigned long)g_wst_local.dframes, g_st_now, g_st_early_now, (unsigned long)(DWORD_PTR)o, p[0], p[1], p[2]);
    g_st_plog_n++;
}

/* ---- tracers (2026-10-18 tick-fix; I76_SIM_TICK_TRACER, default 1; owner playtest: "the gun tracers don't go out from the
 * car, just the first moment is visible") -------------------------------------------------------------------------------
 * A tracer is not drawn from its round's pose. The engine keeps a fixed ring of tracer records (0x64 bytes, created at
 * mission load by 0x441be0; [0x52ba48] = the next record to hand out, +0 = next): +4 the round (projectile object),
 * +8 "updated since the last draw", +0xc / +0x10 the older / newer slot of a 2-entry ring (next-index table 0x52ba38 =
 * {1, 0}), +0x14 type (table 0x4f1c38), +0x18 colour, +0x1c two slots of 3 world points (36 bytes each; type 2 uses the
 * first point only). weapon_FireProjectile 0x49fb40 -> 0x441d10 takes the next record (older = newer = 0, slot 0 = the
 * muzzle, +8 = 1); every weapon_StepBullet 0x4abe60 -> 0x441ef0(round, type) finds the record owned by the round, sets +8,
 * advances the newer index and writes the round's position there. renderer_QueueTracers 0x442480 (and the mirror's
 * 0x4420b0) draws the segment older -> newer and then CLEARS +8; a record whose +8 is already 0 when it is drawn is
 * RESET: older = newer = 0 and owner +4 = 0. In stock every drawn frame ran a step first, so that only fired for a dead
 * round. Under the tick the round steps once per tick and is drawn 4 times (120 fps / 30 ticks): the 2nd drawn frame
 * after a tick reset the record and dropped its owner, so 0x441ef0 never found it again - the round's tracer showed for
 * one or two frames at the muzzle and never again (both the 33.3 and the 66.7 ms tick). The segment also lay one tick
 * ahead of the drawn (interpolated) world.
 * Fix (drawing only): at the end of each tick the records updated in it are listed; around each render they are marked
 * updated (+8 = 1, so the renderer does not reset them), and their two slots are swapped for the drawn segment: the
 * newer end at lerp(older, newer, alpha) (where the round is drawn), the older end one tick of motion behind it (the
 * stock streak length at a 30 fps frame), or at the muzzle while the round is in its first tick (no streak behind the
 * gun). After the render the slots and indices are put back and +8 = 0 (as the stock render leaves it), so the next
 * tick's step and the reset of a dead round work as in stock: a record not updated in a tick is reset by the first
 * render after it. I76_SIM_TICK_TRACER=0 = the old behaviour. */
typedef struct { BYTE *t, *owner; int first, draw; DWORD f8, fc, f10, saved; float s[18]; } wtrc_t;
static wtrc_t g_trc[512]; static int g_trc_n;
static struct { BYTE *t, *owner; DWORD touched; } g_trcp[512]; static int g_trcp_n;   /* the last tick's view (first-tick test) */
static int g_st_trc = 1;
static DWORD g_trc_drawn, g_trc_resets_saved, g_trc_first;
static FILE *g_st_tlog; static DWORD g_st_tlog_n;
static int st_trc_ok(BYTE *t) { return t && (DWORD_PTR)t > 0x10000; }
static void st_trc_tick_end(void) {                          /* after the sim block of a tick */
    BYTE *t0 = *(BYTE **)0x0052ba48, *t;
    int guard = 0, n = 0, i, np = 0;
    static struct { BYTE *t, *owner; DWORD touched; } nw[512];
    g_trc_n = 0;
    if (!st_trc_ok(t0)) { g_trcp_n = 0; return; }
    t = t0;
    do {
        DWORD touched = *(DWORD *)(t + 8), h = *(DWORD *)(t + 0xc), tl = *(DWORD *)(t + 0x10);
        BYTE *owner = *(BYTE **)(t + 4);
        int first = 1;
        for (i = 0; i < g_trcp_n; i++) if (g_trcp[i].t == t) { first = !(g_trcp[i].touched && g_trcp[i].owner == owner); break; }
        if (touched && owner && n < 512) {
            wtrc_t *e = &g_trc[n++];
            e->t = t; e->owner = owner; e->first = first; e->draw = h < 2 && tl < 2 && h != tl; e->saved = 0;
            if (first && e->draw) g_trc_first++;
        }
        if (np < 512) { nw[np].t = t; nw[np].owner = owner; nw[np].touched = touched; np++; }
        t = *(BYTE **)t;
    } while (st_trc_ok(t) && t != t0 && ++guard < 4096);
    g_trc_n = n;
    memcpy(g_trcp, nw, sizeof(nw[0]) * np); g_trcp_n = np;
}
static void st_trc_in(float a) {                             /* before a render: the drawn segment, record kept alive */
    int i, k;
    for (i = 0; i < g_trc_n; i++) {
        wtrc_t *e = &g_trc[i];
        BYTE *t = e->t;
        float *s = (float *)(t + 0x1c);
        if (*(BYTE **)(t + 4) != e->owner) continue;        /* handed to a new round meanwhile (not expected between ticks) */
        e->f8 = *(DWORD *)(t + 8); e->fc = *(DWORD *)(t + 0xc); e->f10 = *(DWORD *)(t + 0x10);
        memcpy(e->s, s, sizeof(e->s)); e->saved = 1;
        if (!e->f8) g_trc_resets_saved++;                    /* the stock render would have reset this record now */
        *(DWORD *)(t + 8) = 1;
        if (e->draw && e->fc < 2 && e->f10 < 2 && e->fc != e->f10) {
            float *o = e->s + 9 * e->fc, *nn = e->s + 9 * e->f10, *wo = s + 9 * e->fc, *wn = s + 9 * e->f10;
            for (k = 0; k < 9; k++) {
                float d = nn[k] - o[k], head = o[k] + a * d;
                wn[k] = head;
                wo[k] = e->first ? o[k] : head - d;
            }
            g_trc_drawn++;
        }
    }
}
static void st_trc_out(void) {                               /* after the render: the sim's record back, +8 as a stock render leaves it */
    int i;
    for (i = 0; i < g_trc_n; i++) {
        wtrc_t *e = &g_trc[i];
        BYTE *t = e->t;
        if (!e->saved) continue;
        e->saved = 0;
        if (*(BYTE **)(t + 4) != e->owner) continue;
        memcpy(t + 0x1c, e->s, sizeof(e->s));
        *(DWORD *)(t + 0xc) = e->fc; *(DWORD *)(t + 0x10) = e->f10; *(DWORD *)(t + 8) = 0;
    }
}
/* I76_SIM_TICK_TRCLOG=<path> (lab instrument): every drawable tracer record per drawn frame, as the renderer sees it -
 * wall s, display frame, tick frame, record, round, first tick, older x y z, newer x y z (slot point 0) */
static void st_trc_log(void) {
    BYTE *t0 = *(BYTE **)0x0052ba48, *t;
    int guard = 0;
    LARGE_INTEGER q;
    if (!st_trc_ok(t0)) return;
    QueryPerformanceCounter(&q);
    t = t0;
    do {
        DWORD h = *(DWORD *)(t + 0xc), tl = *(DWORD *)(t + 0x10);
        if (*(DWORD *)(t + 8) && h < 2 && tl < 2 && h != tl) {
            const float *o = (const float *)(t + 0x1c) + 9 * h, *nn = (const float *)(t + 0x1c) + 9 * tl;
            int i, first = 0;
            for (i = 0; i < g_trc_n; i++) if (g_trc[i].t == t) { first = g_trc[i].first; break; }
            fprintf(g_st_tlog, "%.6f,%lu,%d,%08lx,%08lx,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f\n", (double)(q.QuadPart - g_qp0.QuadPart) / (double)g_qpf.QuadPart,
                    (unsigned long)g_wst_local.dframes, g_st_now, (unsigned long)(DWORD_PTR)t, (unsigned long)(DWORD_PTR)*(BYTE **)(t + 4), first,
                    o[0], o[1], o[2], nn[0], nn[1], nn[2]);
            g_st_tlog_n++;
        }
        t = *(BYTE **)t;
    } while (st_trc_ok(t) && t != t0 && ++guard < 4096);
}

/* ---- sustained sounds between ticks (2026-10-18 tick-fix; I76_SIM_TICK_SOUND, default 1; owner playtest: "sound effects
 * aren't playing quite right, seems like they are being restarted fast") ------------------------------------------------
 * Sustained loops (voice mode +0x3c == 2: tyre skid / turn / dust from physics_PlayTyreSounds 0x43d500 at the end of the
 * player's vehicle tick, tflat, fdmg1, the missile-lock tones of weapon_Update 0x4a3760; requested through
 * sound_PlayOnObjectSustained 0x423230) live while they are requested: each request adds 1 to the voice's keep-alive
 * byte +0x74 (0x421c8b), and the per-frame sound update shell_cb_10 0x421400 (call 0x403e27, every DISPLAY frame) stops a
 * mode-2 voice whose keep-alive is 0 and clears it otherwise (0x42151e / 0x42155f). In stock every frame ran the sim, so a
 * held state requested its loop on every frame. Under the tick the request comes once per tick and the next display
 * frame's update stops the loop: the road / skid noise was stopped and started again at every tick (30 / 15 times a
 * second). Fix: the tick frame (camera wrapper, after the sim block, before the sound update) lists the mode-2 voices
 * the tick requested (keep-alive > 0); on the following non-tick frames each listed voice that is still in the active
 * list (manager [0x524564] +0x1c, next +0) and still mode 2 gets keep-alive 1 before the update, as if the sim had
 * requested it on that frame too. A loop the next tick does not request is stopped by that tick frame's update, as in
 * stock (at most one tick late). */
static BYTE *g_snd_keep[256]; static int g_snd_keep_n, g_st_snd = 1;
static DWORD g_snd_held;
static void st_snd_keep(int tickframe) {
    BYTE *mgr = *(BYTE **)0x00524564, *e;
    int i, guard = 0;
    if (!mgr || *(DWORD *)0x004ed7e8 == 0) { g_snd_keep_n = 0; return; }
    if (tickframe) {
        g_snd_keep_n = 0;
        for (e = *(BYTE **)(mgr + 0x1c); e && guard++ < 512; e = *(BYTE **)e)
            if (*(int *)(e + 0x3c) == 2 && *(BYTE *)(e + 0x74) && g_snd_keep_n < 256) g_snd_keep[g_snd_keep_n++] = e;
        return;
    }
    for (e = *(BYTE **)(mgr + 0x1c); e && guard++ < 512; e = *(BYTE **)e) {
        if (*(int *)(e + 0x3c) != 2 || *(BYTE *)(e + 0x74)) continue;
        for (i = 0; i < g_snd_keep_n; i++) if (g_snd_keep[i] == e) { *(BYTE *)(e + 0x74) = 1; g_snd_held++; break; }
    }
}

/* I76_SOUND_CENSUS=1 (lab instrument, any frame loop): every voice start (sound_StartVoice 0x4220c0 from the per-frame
 * update 0x4214e0 and the un-park path 0x422422, call sites repointed) that played, split by mode and by sample name,
 * with the sim time (0x5a7e70): starts per sim second, so the tick, promotion 18 and the stock loop can be compared. A
 * `sound-census:` line every 5 s of wall time. */
static DWORD g_scn_starts, g_scn_loops, g_scn_last; static float g_scn_t0 = -1.0f;
static struct { char name[16]; DWORD n, loop; } g_scn[48]; static int g_scn_n;
static int __cdecl st_snd_start_count(BYTE *voice, int k) {
    int r = ((int (__cdecl *)(BYTE *, int))0x004220c0)(voice, k);
    if (r && voice && *(DWORD *)0x004ed7e8) {
        const char *nm = (const char *)(voice + 4);
        int i, loop = *(int *)(voice + 0x3c) == 2;
        float t = *(volatile float *)0x005a7e70;
        g_scn_starts++; if (loop) g_scn_loops++;
        if (g_scn_t0 < 0.0f) g_scn_t0 = t;
        for (i = 0; i < g_scn_n; i++) if (strncmp(g_scn[i].name, nm, 15) == 0) break;
        if (i == g_scn_n && g_scn_n < 48) { lstrcpynA(g_scn[i].name, nm, 16); g_scn[i].n = 0; g_scn[i].loop = 0; g_scn_n++; }
        if (i < g_scn_n) { g_scn[i].n++; if (loop) g_scn[i].loop++; }
        if (GetTickCount() - g_scn_last >= 5000) {
            char buf[1200]; int o = 0, j;
            g_scn_last = GetTickCount();
            for (j = 0; j < g_scn_n && o < 1100; j++) o += _snprintf(buf + o, sizeof(buf) - o, " %s=%lu%s", g_scn[j].name, (unsigned long)g_scn[j].n, g_scn[j].loop ? "L" : "");
            buf[o < (int)sizeof(buf) ? o : (int)sizeof(buf) - 1] = 0;
            mlog("  sound-census: sim %.3f..%.3f s, starts %lu (sustained loops %lu), loop keep-alives held between ticks %lu;%s",
                 g_scn_t0, t, (unsigned long)g_scn_starts, (unsigned long)g_scn_loops, (unsigned long)g_snd_held, buf);
        }
    }
    return r;
}
static void apply_sound_census(void) {
    int n = 0;
    if (!env_present("I76_SOUND_CENSUS")) return;
    n += st_call_site(0x004214e0, 0x004220c0, (void *)st_snd_start_count, 0, "sound_StartVoice call in the sound update (sound census)");
    n += st_call_site(0x00422422, 0x004220c0, (void *)st_snd_start_count, 0, "sound_StartVoice call in the un-park path (sound census)");
    mlog("  sound-census: %d/2 call sites", n);
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

/* Flamer stream ageing (2026-10-18 tick-gaps; I76_SIM_TICK_FLAME_AGE=<hz>, default 20, 0 = every tick).
 * weapon_AgeFlamerStreams 0x443e90 retracts a stream by 2 segments on every call that saw no shot since the last one;
 * flamers shoot 20 times a second, so a stream only grows when it is aged at most 20 times a second (stock 20 fps: full
 * length, 19 segments; stock 30 fps and the 33.3 ms tick: 2 calls in 3 have a shot, +1 +1 -2, about 2 segments - the
 * same frame-rate bug I76_FRAMERATE_FIXES holds to its 20 Hz grid). Here the ageing runs on a tick frame only when
 * at least 1/hz of sim time has passed since the last ageing (every 2nd tick at 33.3 ms = 15 a second, every tick at
 * 66.7 ms), so each call's fired flag covers a whole shot interval or more and a held trigger never retracts the stream.
 * (A first form aged on the ticks that crossed a 50 ms grid line, 2 in 3: windows of 33 and 67 ms, and whether the
 * 33 ms window held a shot depended on the phase of the weapon timer - 18.7 segments in 3 boots, 2.5 in the next.) The update / damage still run once per tick (30 a second at 33.3 ms, the
 * 1997 design value D x f per second per hitting segment: max(1, int(30 x 1 x T)) = 1). */
static int g_st_fage_hz = 20, g_st_fage_due = 1;
static double g_st_fage_acc;
static void __cdecl st_flame_age_wrap(void) { if (g_tick20 && g_st_fage_due) ((void (__cdecl *)(void))0x00443e90)(); }
static void st_flame_age_tick(void) {                         /* on each tick frame */
    double per;
    if (g_st_fage_hz <= 0) { g_st_fage_due = 1; return; }
    per = 1.0 / (double)g_st_fage_hz;
    g_st_fage_acc += (double)g_st_T;
    if (g_st_fage_acc >= per - 1e-6) { g_st_fage_due = 1; g_st_fage_acc = 0.0; }
    else g_st_fage_due = 0;
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
    int early = 0;
    int gameplay = *(volatile DWORD *)0x00504c1c != 0 && (*(volatile BYTE *)0x004fe534 & 0x3e) == 0;
    QueryPerformanceCounter(&q);
    d = g_st_q.QuadPart ? (double)(q.QuadPart - g_st_q.QuadPart) / (double)g_qpf.QuadPart : 0.0;
    g_st_q = q;
    g_st_disp_dt = (float)(d < 0.001 ? 0.001 : d > 0.2 ? 0.2 : d);
    g_wst_local.dframes++;
    if (!gameplay) {                                         /* shell / pause: stock, every frame */
        ((void (__cdecl *)(void))0x0049c920)();
        g_st_now = 1; g_st_acc = g_st_T; g_st_since = 0.0; g_wm_n = 0; g_st_seg_early = 0; g_we_n = 0; g_trc_n = 0; g_trcp_n = 0;
        g_st_clk[0] = 0.0f;
        g_tick20 = 1; g_st_fage_due = 1;
        wst_publish();
        return;
    }
    g_wst_local.gameplay_frames++;
    if (*(volatile int *)0x005a7e18 == 0 && g_st_acc < (double)g_st_T) g_st_acc = (double)g_st_T;   /* simclock_Init ran: a new mission */
    g_wst_local.wall_s += d > 0.25 ? 0.25 : d;
    g_st_acc += d > 0.25 ? 0.25 : d;
    g_st_since += d;
    if (g_st_input && g_st_acc < (double)g_st_T && st_input_changed()) {   /* I76_SIM_TICK_INPUT: run the tick now (borrowed) */
        if (g_st_acc >= 0.0) { early = 1; g_wst_local.early_ticks++; } else g_wst_local.early_blocked++;   /* one outstanding at most */
    }
    g_st_early_now = early;
    if (g_st_acc >= (double)g_st_T || early) {
        volatile float *acc = (volatile float *)0x005a7e14, *tm = (volatile float *)0x005a7e74, *stm = (volatile float *)0x005a7e70;
        float acc0 = *acc, tm0 = *tm, stm0 = *stm;
        int warm = *(volatile int *)0x005a7e18 >= *(volatile int *)0x004be990;   /* accum_dt counts from the 4th frame */
        if (early) st_early_from();                          /* what this frame would have drawn: the blend's start */
        g_st_acc -= (double)g_st_T;
        if (early) { g_st_acc0 = g_st_acc; g_st_seg_early = 1; }
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
        g_wst_local.ticks++; g_st_tickno++;
        g_st_since = 0.0;
        g_tick20 = 1; g_tick20_n++; g_acc20 = 0.0f;
        st_flame_age_tick();
        radar_ping_flush();
    } else {
        g_st_now = 0;
        (*(volatile DWORD *)0x005a7e1c)++;                  /* display-frame count for the render-side readers */
        g_wst_local.nontick++;
        g_tick20 = 0; g_acc20 = (float)g_st_since;
    }
    if (g_st_now && !early) g_st_seg_early = 0;              /* a regular tick ends an early segment */
    g_wst_local.alpha = st_alpha();
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
static void __cdecl st_gate0(void) {                       /* input_UpdateControls, then the keyboard snapshot */
    int i;
    if (!g_st_now) return;
    g_wst_local.gate[0]++;
    for (i = 0; i < 16; i++) g_sj[i].polled = 0;
    g_st_joy_rec = 1;                                        /* the joystick hook records what the engine reads (st_joy_note) */
    ((void (__cdecl *)(void))g_stc[0])();
    g_st_joy_rec = 0;
    for (i = 0; i < 16; i++) g_sj[i].valid = g_sj[i].polled;
    memcpy(g_st_kb_snap, (const void *)0x006092d0, 16);
}
ST_GATE0(1) ST_GATE0(2) ST_GATE0(6) ST_GATE0(8) ST_GATE0(9) ST_GATE0(10) ST_GATE0(11)
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
    if (g_st_now && g_st_clk[0] > 0.0f && g_st_trc) st_trc_tick_end();   /* tracer records updated in this tick */
    if (g_st_snd && g_st_clk[0] > 0.0f) st_snd_keep(g_st_now);   /* sustained sounds: list (tick frame) / keep alive (between ticks) */
    if (g_st_now && g_st_clk[0] > 0.0f && g_bbox_sweep) sign_sweep_tick();   /* signs: this tick's motion, before its first drawn frame */
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
    if (g_st_dlog) {   /* wall s, tick frame, early tick, alpha, drawn player position and forward row */
        int i;
        for (i = 0; i < g_wm_n; i++) if (g_wm[i].kind == 0) {
            xform_t *x = (xform_t *)(g_wm[i].obj + 0x18);
            LARGE_INTEGER q; QueryPerformanceCounter(&q);
            fprintf(g_st_dlog, "%.6f,%d,%d,%.4f,%.4f,%.4f,%.4f,%.5f,%.5f,%.5f\n", (double)(q.QuadPart - g_qp0.QuadPart) / (double)g_qpf.QuadPart,
                    g_st_now, g_st_early_now, g_wst_local.alpha, x->p[0], x->p[1], x->p[2], x->r[6], x->r[7], x->r[8]);
            break;
        }
    }
    if (g_st_plog && g_st_plog_n < 3000000) {                /* I76_SIM_TICK_PROJLOG: every projectile's drawn position this frame */
        QueryPerformanceCounter(&g_st_plog_q);
        wst_walk(st_plog_cb);
    }
    if (g_lat_draw_fn) g_lat_draw_fn();
    g_idbg.flame_hits = g_idbg_flame_hits; g_idbg.flame_dmg = g_idbg_flame_dmg;
    g_wst_local.flame_hits = g_idbg_flame_hits; g_wst_local.flame_dmg = g_idbg_flame_dmg;
    g_wst_local.ping_req = g_idbg_ping_req; g_wst_local.ping_play = g_idbg_ping_play;
    g_wst_local.flame_amt = g_flc_amt_pl + g_flc_amt_ot; g_wst_local.flame_upd = g_flc_frames_app;
    g_wst_local.flame_seg_sum = g_flc_seg_sum; g_wst_local.flame_seg_n = g_flc_seg_n; g_wst_local.flame_hit_s = g_flc_t0 >= 0.0f ? g_flc_t1 - g_flc_t0 : 0.0f;
    if (g_st_trc) st_trc_in(g_wst_local.alpha);
    if (g_st_tlog && g_st_tlog_n < 3000000) st_trc_log();
    ((void (__cdecl *)(void *))0x00401c90)(cam);
    if (g_st_trc) st_trc_out();
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
    flc_count_update(g_tick20, 0);
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
    g_st_input = env_flag("I76_SIM_TICK_INPUT", 8, 0) == 1;
    g_st_joy_on = g_st_input && env_flag("I76_SIM_TICK_JOY", 8, 1) == 1;   /* the joystick part of the early tick (hook: apply_joy_routing) */
    g_st_joy_pm = env_int("I76_SIM_TICK_JOY_DB", 8, 10); if (g_st_joy_pm < 0) g_st_joy_pm = 0; if (g_st_joy_pm > 500) g_st_joy_pm = 500;
    g_st_proj = env_flag("I76_SIM_TICK_PROJ", 8, g_st_proj) == 1;
    g_st_proj_vsel = env_int("I76_SIM_TICK_PROJ_V", 8, g_st_proj_vsel); if (g_st_proj_vsel < 0 || g_st_proj_vsel > 2) g_st_proj_vsel = 0;
    g_st_trc = env_flag("I76_SIM_TICK_TRACER", 8, g_st_trc) == 1;
    g_st_snd = env_flag("I76_SIM_TICK_SOUND", 8, g_st_snd) == 1;
    g_st_fage_hz = env_int("I76_SIM_TICK_FLAME_AGE", 8, g_st_fage_hz); if (g_st_fage_hz < 0) g_st_fage_hz = 0; if (g_st_fage_hz > 1000) g_st_fage_hz = 1000;
    {   char dp[MAX_PATH];
        if (env_str("I76_SIM_TICK_DRAWLOG", dp, sizeof(dp)) && (g_st_dlog = fopen(dp, "w")) != 0) {
            setvbuf(g_st_dlog, NULL, _IOFBF, 1 << 13);   /* the process is killed at the end: at most 8 KB lost */
            fprintf(g_st_dlog, "t,tick,early,alpha,x,y,z,fx,fy,fz\n");
        }
        if (env_str("I76_SIM_TICK_TRCLOG", dp, sizeof(dp)) && (g_st_tlog = fopen(dp, "w")) != 0) {
            setvbuf(g_st_tlog, NULL, _IOFBF, 1 << 13);
            fprintf(g_st_tlog, "t,dframe,tick,rec,round,first,ox,oy,oz,nx,ny,nz
");
        }
        if (env_str("I76_SIM_TICK_PROJLOG", dp, sizeof(dp)) && (g_st_plog = fopen(dp, "w")) != 0) {
            setvbuf(g_st_plog, NULL, _IOFBF, 1 << 13);
            fprintf(g_st_plog, "t,dframe,tick,early,obj,x,y,z\n");
        }
    }
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
            { 0x00401cec, 0x00443e90, (void *)st_flame_age_wrap, "flamer ageing (software)" },
            { 0x00401fcc, 0x00443e90, (void *)st_flame_age_wrap, "flamer ageing (hardware)" },
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
        g_wst_local.magic = 0x31545357u; g_wst_local.version = 3; g_wst_local.tick_s = g_st_T;
        wst_publish();
    }
    g_simtick = 1; g_st_now = 1;
    g_jc_on = 1;
    mlog("  sim-tick: ON - whole sim every %.3f ms (%.3f ticks/s; vehicle stepper count %d x %.2f ms); %d/12 sim gates, %d/4 display hooks, "
         "%d/14 draw-side holds, %d/7 cosmetic sites (I76_SIM_TICK_COSMETIC=%d); early tick on input %s; new rounds drawn moving %s; tracers kept and drawn between ticks %s; sustained sounds kept between ticks %s; flamer streams aged at %d Hz%s; shm Local\\I76SimTick %s",
         ms, 1000.0 / ms, (int)(g_st_T * 20.0f) + 1, ms / (double)((int)(g_st_T * 20.0f) + 1), g, h, n, c, g_st_cosmetic,
         g_st_input ? (g_st_joy_on ? "ON (I76_SIM_TICK_INPUT=1: keyboard + joystick)" : "ON (I76_SIM_TICK_INPUT=1: keyboard; I76_SIM_TICK_JOY=0)") : "off",
         g_st_proj ? "ON (I76_SIM_TICK_PROJ=1)" : "off", g_st_trc ? "ON (I76_SIM_TICK_TRACER=1)" : "off", g_st_snd ? "ON (I76_SIM_TICK_SOUND=1)" : "off", g_st_fage_hz > 0 ? g_st_fage_hz : (int)(1.0f / g_st_T + 0.5f),
         g_st_fage_hz > 0 ? " (I76_SIM_TICK_FLAME_AGE)" : " (every tick: I76_SIM_TICK_FLAME_AGE=0)", g_wst ? "mapped" : "MISSING");
}
/* called by apply_joy_routing once the joyGetPosEx hook is in (or not): the joystick watch needs it */
static void simtick_joy_ready(MMRESULT (WINAPI *pos)(UINT, LPJOYINFOEX), MMRESULT (WINAPI *caps)(UINT_PTR, LPJOYCAPSA, UINT)) {
    if (!g_st_joy_on) return;
    g_st_joy_call = pos; g_st_joy_caps = caps;
    if (pos) mlog("  sim-tick: early tick watches the joysticks the engine polls (joyGetPosEx hook in; dead band %d permille of the axis range)", g_st_joy_pm);
    else { g_st_joy_on = 0; mlog("  sim-tick: joystick watch OFF - no joyGetPosEx hook (no WINMM import?): a wheel / pad waits for the next tick"); }
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
