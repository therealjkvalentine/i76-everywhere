/*
 * i76tel.h - Interstate '76 telemetry export: the wire / shared-memory layout.
 *
 * Written by the Strlkup proxy (music-fix/strlkproxy.c, I76_TELEMETRY=<port>) once per rendered frame, read by
 * tools/telemetry/i76tel.py and by FFB / motion tools. The proxy #includes this file, and i76tel.py parses it at
 * run time to build its struct format, so the three cannot drift apart: change a field here and both sides follow.
 *
 * Every field is little-endian and naturally aligned (the layout is identical with or without packing), so a C
 * reader can #include this as-is and a Python reader can use struct.unpack with '<'. Source addresses are the
 * pristine 2017 Galaxy exe (md5 9a232dcc); the field comments cite them (i76-map types/i76_runtime.h,
 * subsystems/*.md, docs/FFB-DATA-AUDIT.md). Nothing in this file has been verified live yet.
 *
 * Parser contract for i76tel.py: one field per line, `type name;` or `type name[N];`, scalar types from
 * <stdint.h> plus float / double / char, struct types defined earlier in this file. Keep it that way.
 */
#ifndef I76TEL_H
#define I76TEL_H
#include <stdint.h>

#define I76TEL_MAGIC    0x54363749u  /* the bytes 'I' '7' '6' 'T' in memory order */
#define I76TEL_VERSION  1
#define I76TEL_RING     64           /* event ring entries; slot = seq % I76TEL_RING */
#define I76TEL_PORT     7676         /* default UDP port (I76_TELEMETRY=1) */
#define I76TEL_SHM_NAME "Local\\I76Telemetry"

/* event types (i76tel_event_t.type) */
#define I76TEL_EV_SHOT       1   /* weapon_FireShot 0x4a6e90, player's weapons only: f = {hud row, ammo left, damage per hit, dt_left}, i = {weapdef index, rounds in this call} */
#define I76TEL_EV_EXPLOSION  2   /* entity_SpawnExplosion 0x49ead0, any: f = {x, y, z, distance to the player (-1 when none)}, i = {template name bytes 0-3, bytes 4-7} */
#define I76TEL_EV_IMPACT     3   /* physics_ApplyCollisionDamage 0x4a7c80, any target: f = {impact vector x, y, z, armour+chassis+component hp the player lost in the call}, i = {target is the player, source object class (+0x6c; 0 = terrain / none, 1 car, 0x33 ordnance, 0x34 explosion)} */

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

typedef struct i76tel_event_t {         /* 36 bytes */
    uint32_t seq;                       /* 1, 2, 3 ... over the whole session; a gap in a stream means the ring wrapped before a send */
    uint32_t frame;                     /* proxy frame counter the event happened in (= i76tel_frame_t.proxy_frame of the frame that carries it) */
    uint32_t type;                      /* I76TEL_EV_* */
    float    f[4];                      /* per type, see the I76TEL_EV_* comments */
    int32_t  i[2];
} i76tel_event_t;

typedef struct i76tel_frame_t {         /* 608 bytes, one per rendered frame */
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
    uint32_t event_seq;                 /* total events recorded so far (the last event's seq) */
    uint32_t event_count;               /* events appended to this datagram after the struct (0 in shared memory) */
} i76tel_frame_t;

typedef struct i76tel_shm_t {           /* the Local\I76Telemetry mapping */
    uint32_t seq;                       /* odd while the writer is inside, even when the block is consistent: read seq, copy, re-read seq, accept if equal and even */
    uint32_t size;                      /* sizeof(i76tel_shm_t) */
    i76tel_frame_t frame;
    i76tel_event_t ring[64];            /* I76TEL_RING entries, slot = event seq % 64 */
} i76tel_shm_t;

#pragma pack(pop)

#endif /* I76TEL_H */
