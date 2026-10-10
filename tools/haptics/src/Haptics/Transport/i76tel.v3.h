/*
 * FROZEN COPY for tools/haptics: tools/telemetry/i76tel.h at version 3 as landed by the proxy agent
 * (branch worktree-agent-a2d1aee61832dc0d1, commit 80e1667). Decodes v3 frames whatever the live header says.
 *
 * i76tel.h - Interstate '76 telemetry export: the wire / shared-memory layout.
 *
 * Written by the Strlkup proxy (music-fix/strlkproxy.c, I76_TELEMETRY=<port>) once per rendered frame, read by
 * tools/telemetry/i76tel.py and by FFB / motion tools. The proxy #includes this file, and i76tel.py parses it at
 * run time to build its struct format, so the three cannot drift apart: change a field here and both sides follow.
 *
 * Every field is little-endian and naturally aligned (the layout is identical with or without packing), so a C
 * reader can #include this as-is and a Python reader can use struct.unpack with '<'. Source addresses are the
 * pristine 2017 Galaxy exe (md5 9a232dcc); the field comments cite them (i76-map types/i76_runtime.h,
 * subsystems/*.md, docs/records/FFB-DATA-AUDIT.md). v2 was verified live 2026-10-01 (verification-2026-10-01.txt);
 * the v3 additions (2026-10-10, docs/HAPTICS-ARCHITECTURE.md 4.1) are static-verified only, not yet run.
 *
 * Versions. v3 widened i76tel_event_t (36 -> 56 bytes) and appended fields to i76tel_frame_t after event_count; every
 * v2 frame field keeps its offset, so a reader built on the v2 header still decodes a v3 frame (not its events). For
 * the other direction i76tel.py keeps the frozen v2 layout in i76tel_v2.h and picks the layout by the frame's
 * version field, so a v3 reader still decodes a v2 proxy (the committed Strlkup.dll until it is rebuilt).
 *
 * Parser contract for i76tel.py: one field per line, `type name;` or `type name[N];`, scalar types from
 * <stdint.h> plus float / double / char, struct types defined earlier in this file. Keep it that way.
 */
#ifndef I76TEL_H
#define I76TEL_H
#include <stdint.h>

#define I76TEL_MAGIC    0x54363749u  /* the bytes 'I' '7' '6' 'T' in memory order */
#define I76TEL_VERSION  3
#define I76TEL_RING     64           /* event ring entries; slot = seq % I76TEL_RING */
#define I76TEL_PORT     7676         /* default UDP port (I76_TELEMETRY=1) */
#define I76TEL_SHM_NAME "Local\\I76Telemetry"

/* event types (i76tel_event_t.type) */
#define I76TEL_EV_SHOT       1   /* weapon_FireShot 0x4a6e90, player's weapons only: f = {hud row, ammo left, damage per hit, dt_left}, i = {weapdef index, rounds in this call} */
#define I76TEL_EV_EXPLOSION  2   /* entity_SpawnExplosion 0x49ead0, any: f = {x, y, z, distance to the player (-1 when none)}, i = {template name bytes 0-3, bytes 4-7} */
#define I76TEL_EV_IMPACT     3   /* physics_ApplyCollisionDamage 0x4a7c80, any target: f = {impact vector x, y, z, armour+chassis+component hp the player lost in the call}, i = {target is the player, source object class (+0x6c; 0 = terrain / none, 1 car, 0x33 ordnance, 0x34 explosion)} */
/* v3 (I76_TELEMETRY plus I76_SOUND_EVENTS=1 / I76_DAMAGE_EVENTS=1; static-verified, not run). Unused f / i slots are 0. */
#define I76TEL_EV_SOUND_START 4  /* sound_StartVoice 0x4220c0 returned 1 (a voice really started, or came back from parking), any voice: f = {frequency Hz (voice+0x18, after the random pitch and the start callback), volume % (+0x1c), x, y, z (world position +0x40 of the voice object's root, read before the start), pan (+0x20)}, i = {name bytes 0-3, 4-7 (voice+4), I76TEL_SND_* bits, object (voice+0x5c before the start; 0 = 2D), voice address} */
#define I76TEL_EV_SOUND_STOP  5  /* a voice that had a SOUND_START stopped: f = {sim seconds since its start}, i = {name bytes 0-3, 4-7, reason (I76TEL_STOP_*) | I76TEL_STOP_PLAYER, object recorded at the start, voice address} */
#define I76TEL_EV_DAMAGE_SIDE 6  /* entity_DamageAndKill 0x463a80 (object, damage record, hit point in the target's frame) on a live vehicle with a record: f = {incoming damage (sum of the record amounts whose type bit is set), armour+chassis+component hp the target lost in the call, hit point x, y, z}, i = {armour side 0 front 1 left 2 right 3 back 4 top, zone 0..6, I76TEL_DMG_* bits, type mask (record+4) | record flags (record+6) << 16, shooter object class (record+0 -> +0x6c; 0 none)} */
#define I76TEL_EV_WEAPON_UI   7  /* the weapon cycle / link / unlink click (the three call 0x4250f0 sites beside the FFB one-shots 0x4f234c/50/54), under I76_SOUND_EVENTS: i = {0 cycle, 1 link, 2 unlink} */

/* SOUND_START / SOUND_STOP i[2] bits */
#define I76TEL_SND_MODE      0xff     /* SOUND_START: voice+0x3c mode: 0 one-shot, 1 loop, 2 sustained loop (needs a request every frame) */
#define I76TEL_SND_PLAYER    0x100    /* the voice object's root (+0x68 chain) is the local player (object flag 0x10) */
#define I76TEL_SND_HAS_POS   0x200    /* SOUND_START: f[2..4] hold a position (the voice had an object) */
#define I76TEL_SND_DETACHED  0x400    /* SOUND_START: voice flag 0x200, a detached one-shot (vvcoll, vexplode, weapon impacts; 3D min distance 100 m) */
#define I76TEL_SND_VOICE_LVL 0x800    /* SOUND_START: voice flag 4, plays at the voice (CB) level instead of the SFX level */
#define I76TEL_SND_PRIO_SHIFT 16      /* SOUND_START: priority (voice+0x34, clamped to 0xffff) in bits 16..31 */
/* SOUND_STOP i[2]: reason (bits 0..15) | I76TEL_STOP_PLAYER. Reasons 1 and 2 are the proxy's; any other value is the
   argument sound_StopVoice 0x422d20 was called with: 0x20 (0x4212fe, 0x421a98, 0x4229b8, 0x425a58), 0x40 (0x422c3e in
   the distance parker 0x422b40, 0x425a6d), 0x80 (0x425a85), 0x100 (0x42290e in sound_AllocVoice). 0x40 keeps the voice
   parked (it can come back with a new SOUND_START); the others stop it */
#define I76TEL_STOP_RELEASED 1        /* voice released (0x425ef0: explicit stops - horn, engine loop, CB, siren - finished one-shots, dead objects) */
#define I76TEL_STOP_ENDED    2        /* the per-frame update 0x421400 found the buffer stopped (or its restart failed) and kept the voice (call 0x422540 at 0x42150b / 0x4215a2) */
#define I76TEL_STOP_PARK     0x40     /* sound_StopVoice reason 0x40: parked for distance / voice pressure */
#define I76TEL_STOP_PLAYER   0x10000  /* the voice's root object was the local player at its start */
/* DAMAGE_SIDE i[2] bits */
#define I76TEL_DMG_PLAYER    0x1      /* the target is the local player (object_IsPlayer) */
#define I76TEL_DMG_BY_PLAYER 0x2      /* the record's shooter object is the local player */
#define I76TEL_DMG_KILLED    0x4      /* entity flag 0x20 (destroyed) went on during the call */

/* i76tel_frame_t.event_hooks bits: which event hooks are installed (a consumer can tell "no sounds" from "not tapped") */
#define I76TEL_HOOK_SHOT        0x01
#define I76TEL_HOOK_EXPLOSION   0x02
#define I76TEL_HOOK_IMPACT      0x04
#define I76TEL_HOOK_SOUND_START 0x08
#define I76TEL_HOOK_SOUND_STOP  0x10
#define I76TEL_HOOK_DAMAGE_SIDE 0x20
#define I76TEL_HOOK_WEAPON_UI   0x40

#pragma pack(push, 1)

typedef struct i76tel_wheel_t {         /* 36 bytes. Component slots 0 1 2 3 4 5 = FL FR ML MR RL RR ([ent+0x3a8+4i]+0x70, type 30; I76_WheelData) */
    int32_t  present;                   /* 1 when the slot holds a type-30 object (the mid pair is often absent) */
    int32_t  hp;                        /* wheel+0x04 */
    int32_t  hp_max;                    /* wheel+0x08 */
    float    grip;                      /* wheel+0x0c: max(hp/max x base, 0.5) after any hit; lateral cap = 7.84 x sum (0x4bd1e0) */
    float    ground_speed;              /* wheel+0x20 signed, the spin animation's speed */
    float    susp_offset;               /* wheel+0x24 filtered suspension offset, +-0.25 r */
    int32_t  unloaded;                  /* wheel+0x40 off the ground (suppresses skid marks) */
    int32_t  flat;                      /* wheel+0x44 flat tyre */
    int32_t  skid_active;               /* wheel+0x48 */
} i76tel_wheel_t;

typedef struct i76tel_event_t {         /* 56 bytes (v3; v2 was 36: f[4], i[2]) */
    uint32_t seq;                       /* 1, 2, 3 ... over the whole session; a gap in a stream means the ring wrapped before a send */
    uint32_t frame;                     /* proxy frame counter the event happened in (= i76tel_frame_t.proxy_frame of the frame that carries it) */
    uint32_t type;                      /* I76TEL_EV_* */
    float    f[6];                      /* per type, see the I76TEL_EV_* comments; types 1-3 use f[0..3] exactly as in v2 */
    int32_t  i[5];                      /* per type; types 1-3 use i[0..1] exactly as in v2 */
} i76tel_event_t;

typedef struct i76tel_frame_t {         /* 664 bytes (v3; v2 was the first 628), one per rendered frame */
    uint32_t magic;                     /* I76TEL_MAGIC */
    uint16_t version;                   /* I76TEL_VERSION */
    uint16_t size;                      /* sizeof(i76tel_frame_t) */
    uint32_t seq;                       /* publish counter, 1 per rendered frame */
    uint32_t frame;                     /* simclock_frame_count 0x5a7e1c (the frame just completed) */
    uint32_t proxy_frame;               /* the proxy's own frame counter (g_frame), the one events are stamped with */
    float    sim_time;                  /* simclock_time 0x5a7e74, s */
    float    sim_dt;                    /* simclock_sim_dt 0x4fe420, the frame's physics dt, s */
    float    dt;                        /* simclock_dt 0x4fe428, the clamped frame dt, s */
    int32_t  step_count;                /* physics substeps the player's tick ran this frame (fixed-step accumulator under I76_FIXED_STEP, else floor(sim_dt x 20) + 1 capped at 20); -1 unknown */
    uint32_t player_present;            /* 1 when [[0x54a264]] is a live local-player object with an entity; every field below is 0 otherwise */
    uint32_t obj_addr;                  /* the player object (I76_Object*), for scanners that want to read on */
    uint32_t ent_addr;                  /* its entity (obj+0x70, I76_Entity*) */
    double   pos[3];                    /* obj+0x40 world position x, y (up), z */
    float    rot[9];                    /* obj+0x18 rotation, rows right / up / forward (row vectors: world = local x R + T). pitch = asin(rot[7]), roll = asin(rot[1]), heading = atan2(rot[6], rot[8]) */
    float    velocity[3];               /* ent+0xbc world velocity, m/s */
    float    speed;                     /* ent+0xac |velocity|, m/s */
    float    pitch_rate;                /* ent+0xc8 body frame, rad/s (snapped to 0 at rest by the contact model) */
    float    yaw_rate;                  /* ent+0xcc */
    float    roll_rate;                 /* ent+0xd0 */
    float    accel[3];                  /* ent+0xd4 acceleration out of physics_IntegrateVehicleMotion, world frame, m/s^2 */
    float    accel_body[3];             /* FFB block 0x4f2418..0x4f2420 = accel rotated into the body frame; written only while ffb_present */
    float    steer;                     /* ent+0xe0 steer_applied, -1..1 */
    float    throttle;                  /* ent+0xe4 throttle_applied, -1..1; braking is throttle < 0 (there is no separate brake input) */
    float    gear_dir;                  /* ent+0xe8 +-1 drive direction */
    int32_t  handbrake;                 /* ent+0xf0 */
    int32_t  exhaust_brake;             /* ent+0xf4 (special type 4 active) */
    int32_t  gear_lever;                /* ent+0x104 0 P, 1 R, 2 N, 3 D, 4 "2", 5 "1" */
    int32_t  gear;                      /* eng+0x08 0 reverse, 1 idle/neutral, 2/3/4 = 1st/2nd/3rd (eng = [[ent+0x3c4]+0x70]) */
    float    rpm;                       /* eng+0x1c, 850..7000 */
    float    speedo;                    /* eng+0x24 mph when geared, raw m/s in the free-rev branch (stock bug) - use speed */
    float    drive_power;               /* eng+0x10 */
    int32_t  engine_hp;                 /* eng+0x00 */
    int32_t  engine_hp_max;             /* eng+0x04 */
    int32_t  susp_hp;                   /* [[ent+0x3c8]+0x70]+0x00 */
    int32_t  susp_hp_max;               /* +0x04 */
    int32_t  brake_hp;                  /* [[ent+0x3cc]+0x70]+0x04 */
    int32_t  brake_hp_max;              /* +0x08 */
    float    brake_effective;           /* brake+0x10 = max(hp/max, 0.2) x strength */
    uint32_t flags;                     /* ent+0x454: 0x1 engine running, 0x2 skid, 0x4 airborne, 0x8 starting, 0x20 destroyed, 0x400 oil, 0x800 nitrous, 0x2000 grip limit, 0x4000 critical kill, 0x8000 wreck */
    uint32_t surface;                   /* ent+0x45c surface type (WRLD table index) */
    float    ground_normal[3];          /* ent+0x460 */
    float    clearance;                 /* ent+0x470 probe y - ground height */
    float    state_timer;               /* ent+0x450 */
    int32_t  armour[4];                 /* ent+0x138 front, left, right, back */
    int32_t  armour_max[4];             /* ent+0x158 */
    int32_t  chassis[4];                /* ent+0x148 */
    int32_t  chassis_max[4];            /* ent+0x168 */
    i76tel_wheel_t wheel[6];            /* component slots 0..5 */
    int32_t  weapon_row;                /* selected HUD row of the player's weapon record (0x5be4d8 + i x 0x2c8, +4); -1 none */
    int32_t  weapon_def;                /* selected instance +0x30 weapdef index (0x5d88d8 + i x 0xd8); -1 none */
    int32_t  weapon_ammo;               /* selected instance +0x20; 0x0fffffff = unlimited */
    int32_t  weapon_hp;                 /* selected instance +0x0c condition */
    char     weapon_name[8];            /* selected weapon root object name (.gdf), not NUL-terminated when 8 long */
    uint32_t ffb_present;               /* 0x52bbd0: the exe writes its FFB block 0x4f2328 only while this is 1 (wheel driver present or the shim installed) */
    int32_t  ffb_rpm;                   /* 0x4f2334 ftol(rpm) */
    uint32_t ffb_engine_running;        /* 0x4f2338 = flags & 1 */
    uint32_t ffb_engine_starting;       /* 0x4f233c = flags bit 3 */
    uint32_t ffb_gear_changed;          /* 0x4f2340 set to 1 when eng+8 != previous (0x4f2314); whether it is cleared on other frames is not yet read live */
    uint32_t ffb_nitrous;               /* 0x4f2344 = flags & 0x800 while a special slot is type 2 */
    uint32_t ffb_list_ordnance;         /* 0x4f2478 impact list head (nodes +0 direction deg, +4 damage); nodes live one frame and are gone by the time this is read: use I76TEL_EV_IMPACT */
    uint32_t ffb_list_concussion;       /* 0x4f247c */
    uint32_t ffb_list_collision;        /* 0x4f2484 */
    float    ffb_dt;                    /* 0x4f2488 simclock_GetDt copy */
    /* v2 (2026-10-02): the inputs the oracles could only fit, not read */
    float    engine_power;              /* eng+0x14 ENGN power P (drive power = P x f x rpm x (7000-rpm)/3500^2) */
    float    mass;                      /* ent+0xa4 total mass (kg); offline brake strength = 2300/m */
    float    inv_mass;                  /* ent+0xa8 1/m */
    float    drag;                      /* ent+0x120 VDFC drag: a = -0.1 x drag x v^2 */
    float    health_pct;                /* object_HealthFraction(obj) 0x40b450 called on the game thread: 28 + 72 x worst side ratio,
                                           or the unscaled component ratio once engine/susp/brakes < 99.99% (damage.md);
                                           min(28 + 72 x side, 100 x core) under I76_FIX_HEALTH_PCT=1, 100 x core under =2 */
    uint32_t event_seq;                 /* total events recorded so far (the last event's seq) */
    uint32_t event_count;               /* events appended to this datagram after the struct (0 in shared memory) */
    /* v3 (2026-10-10): appended, so every v2 offset above is unchanged. Static-verified, not yet run */
    float    wheelbase;                 /* ent+0x118 |P(slot1) - P(slot5)| (physics_InitEntity, fst at 0x438c64), m */
    float    front_track;               /* ent+0x114 |P(slot1) - P(slot0)| (fstp at 0x438c01), m */
    float    steer_gain;                /* ent+0x110 = 1 / (2 x wheelbase) (0x438c72); yaw rate = steer x speed x steer_gain below the cap (0x43cfdb) */
    float    grip_sum;                  /* wheel+0x0c of slots 0, 1, 4, 5 (ent+0x3a8/0x3ac/0x3b8/0x3bc, the four reads in 0x43ce10) */
    float    grip_cap;                  /* 7.84 x grip_sum (0x4bd1e0): the steering routine's lateral limit, m/s^2, while flags & 0x10000 is clear;
                                           with 0x10000 (arcade / Taurus) the exe uses ground_g x handling x surface grip x grip_sum / 4 instead */
    float    ground_g;                  /* ent+0x46c = 9.8 x n.y^3 (gravity along the ground normal; read at 0x43ceab) */
    int32_t  music_track;               /* the proxy's own state: CD track playing now (g_playingTrack), 0 none (lets a loopback LFE tap duck under music) */
    uint32_t event_hooks;               /* I76TEL_HOOK_* bits of the event hooks installed this session */
    uint32_t sound_voices;              /* voices with a SOUND_START and no SOUND_STOP yet (I76_SOUND_EVENTS), 0 otherwise */
} i76tel_frame_t;

typedef struct i76tel_shm_t {           /* the Local\I76Telemetry mapping */
    uint32_t seq;                       /* odd while the writer is inside, even when the block is consistent: read seq, copy, re-read seq, accept if equal and even */
    uint32_t size;                      /* sizeof(i76tel_shm_t) */
    i76tel_frame_t frame;
    i76tel_event_t ring[64];            /* I76TEL_RING entries, slot = event seq % 64 */
} i76tel_shm_t;

#pragma pack(pop)

#endif /* I76TEL_H */
