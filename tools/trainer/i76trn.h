/*
 * i76trn.h - Interstate '76 trainer control block: the shared-memory layout between a trainer front end and the
 * Strlkup proxy (music-fix/strlkproxy.c, section TRAINER CONTROL BLOCK).
 *
 * The proxy creates Local\I76Trainer in DllMain (always, no switch: an untouched block costs one dword test per
 * frame) and, at the top of every frame on the game's own thread, reads the client's request and applies it to
 * the player's vehicle. Doing it on the game thread is what makes the writes stick: an external poke can land
 * inside the render window, where I76_RENDER_INTERP puts the physics pose back, and a hit can register in the
 * same frame as a repair. Here the hold runs before simclock_Update, the physics tick and the render.
 *
 * Same parser contract as tools/telemetry/i76tel.h (i76trainer_gui.py parses this file at run time): one field
 * per line, `type name;` or `type name[N];`, <stdint.h> scalars plus float / double / char, plus struct types defined earlier
 * in this file. Keep it that way.
 *
 * 2026-10-20: the full-state store / restore (I76TRN_CMD_STORE_STATE / SET_STATE, i76trn_ext_t). The mapping grew to
 * 168 + 1304 bytes; i76trn_ctl_t and its version / size stay 1 / 168, so every older front end still drives the block, and
 * a front end that finds no ext_magic (an older proxy) keeps the position-only teleport.
 * Addresses: pristine 2017 Galaxy exe md5 9a232dcc; sources cited per field (i76-map subsystems/cheats.md).
 */
#ifndef I76TRN_H
#define I76TRN_H
#include <stdint.h>

#define I76TRN_MAGIC    0x43363749u  /* 'I' '7' '6' 'C' in memory order */
#define I76TRN_VERSION  1
#define I76TRN_SHM_NAME "Local\\I76Trainer"

/* i76trn_ctl_t.flags - held every frame while set (the client clears a bit to release it) */
#define I76TRN_F_GOD        0x0001   /* player armour + chassis (+0x138/+0x148 and the HUD copies +0x178/+0x18c) at max,
                                        every component at max, flats cleared; and options_play_flags bits 0x18
                                        (unlimited armour + chassis: entity_ApplyDamage zeroes the amount) forced on */
#define I76TRN_F_AMMO       0x0002   /* options_play_flags bit 0x04 forced on, and every live weapon instance's ammo
                                        (0x5aab08 + i x 0x4c, +0x20) set to 0x0fffffff */
#define I76TRN_F_NOFLATS    0x0004   /* wheel flat flag (+0x44) cleared and the radius restored, nothing else */
#define I76TRN_F_COMPONENTS 0x0008   /* components at max only (engine, suspension, brakes, wheels, weapons' hp) */
#define I76TRN_F_FREEZE_POS 0x0010   /* hold the player at pos[] with zero velocity (parking brake for the camera) */

/* i76trn_ctl_t.cmd - one-shots: fill the operands, set cmd, then increment req_seq; the proxy runs it once and
   writes ack_seq = req_seq */
#define I76TRN_CMD_NONE      0
#define I76TRN_CMD_REPAIR    1       /* one full repair (as I76TRN_F_GOD does every frame) */
#define I76TRN_CMD_TELEPORT  2       /* obj+0x40 = pos[] (doubles, y up), ent+0xbc = vel[] */
#define I76TRN_CMD_AMMO      3       /* every live weapon slot's ammo = ammo_value (0x0fffffff = unlimited) */
#define I76TRN_CMD_SLOT_AMMO 4       /* weapon slot slot_index ammo = ammo_value */
#define I76TRN_CMD_PLAYFLAGS 5       /* options_play_flags = (flags & ~play_clear) | play_set, once */
#define I76TRN_CMD_STOP      6       /* ent+0xbc velocity = 0 and the three body rates (+0xc8..+0xd0) = 0 */
/* full car state (2026-10-20, owner request: "teleport ... should also teleport 6 axis position and speed when stored").
   Served only by a proxy whose block carries the extension below (i76trn_ext_t at I76TRN_EXT_OFFSET, ext magic set); an
   older proxy answers cmd_result 2 (unknown command) and the client falls back to I76TRN_CMD_TELEPORT */
#define I76TRN_CMD_STORE_STATE 7     /* capture the player's full state into ext.stored (and ext.target), ext.store_seq++ */
#define I76TRN_CMD_SET_STATE   8     /* put ext.target back (the parts in ext.restore_parts, 0 = all), ext.restore_seq++ */

/* the extension: the 168-byte i76trn_ctl_t above is unchanged (version 1, size 168), so a version-1 reader still drives the
   block; the mapping is larger and i76trn_ext_t follows it. A front end checks ext_magic before using any of it. */
#define I76TRN_EXT_OFFSET   168
#define I76TRN_EXT_MAGIC    0x53363749u  /* 'I' '7' '6' 'S' in memory order */
#define I76TRN_EXT_VERSION  1

/* i76trn_state_t.parts / i76trn_ext_t.restore_parts */
#define I76TRN_ST_POSE      0x0001   /* obj+0x18 rotation rows + obj+0x40 position */
#define I76TRN_ST_MOTION    0x0002   /* velocity, |v| and 1/|v|, body rates, acceleration */
#define I76TRN_ST_CONTACT   0x0004   /* airborne / skid / contact-latched bits, surface, ground normal, ground g, clearance, fall-kill reference */
#define I76TRN_ST_WHEELS    0x0008   /* per wheel: spin speed, suspension offset and its filter history, ground heights, unloaded flag, local y */
#define I76TRN_ST_ENGINE    0x0010   /* gear, drive power, rpm, speedo */
#define I76TRN_ST_ALL       0x001f
#define I76TRN_ST_FLAG_MASK 0x00000016u  /* the ent+0x454 bits a restore puts back: 0x2 skid, 0x4 airborne, 0x10 body contact latched */

/* i76trn_ext_t.hotkeys: the proxy watches two keys while the game window has the focus (edge-triggered, polled once a frame) */
#define I76TRN_HK_ON        0x0001   /* Ctrl+9 = store (I76TRN_CMD_STORE_STATE), Ctrl+0 = restore (I76TRN_CMD_SET_STATE of ext.target);
                                        9 / 0 are bound nowhere in gamekey.map or input.map, and F1-F12 all are */

#pragma pack(push, 1)

typedef struct i76trn_ctl_t {           /* 168 bytes */
    /* client -> proxy */
    uint32_t magic;                     /* I76TRN_MAGIC, written by the proxy at creation; the client checks it */
    uint16_t version;                   /* I76TRN_VERSION */
    uint16_t size;                      /* sizeof(i76trn_ctl_t) */
    uint32_t flags;                     /* I76TRN_F_* held every frame */
    uint32_t play_set;                  /* I76TRN_CMD_PLAYFLAGS operands: bits of options_play_flags 0x654b98 to set / clear */
    uint32_t play_clear;
    uint32_t req_seq;                   /* increment after filling cmd + operands */
    uint32_t cmd;                       /* I76TRN_CMD_* */
    int32_t  slot_index;                /* I76TRN_CMD_SLOT_AMMO */
    int32_t  ammo_value;                /* I76TRN_CMD_AMMO / SLOT_AMMO */
    double   pos[3];                    /* I76TRN_CMD_TELEPORT / I76TRN_F_FREEZE_POS target, world x, y (up), z */
    float    vel[3];                    /* I76TRN_CMD_TELEPORT velocity after the move (usually 0) */
    /* proxy -> client */
    uint32_t ack_seq;                   /* the last req_seq the proxy consumed */
    uint32_t heartbeat;                 /* the proxy's frame counter; stalls when the game is paused or gone */
    uint32_t applied;                   /* the flags the proxy actually applied in the last frame (0 outside a mission) */
    uint32_t player_present;            /* 1 while [[0x54a264]] is a live local-player object with an entity */
    uint32_t play_flags_now;            /* options_play_flags as read this frame */
    uint32_t play_flags_saved;          /* the value the proxy saw before it first forced bits; restored when the forcing flag is cleared */
    uint32_t faults;                    /* SEH faults caught while applying (each costs one frame, never the game) */
    uint32_t cmd_result;                /* 0 ok, 1 no player, 2 unknown cmd, 3 bad slot */
    char     msg[64];                   /* last status line, NUL-terminated */
} i76trn_ctl_t;

typedef struct i76trn_wheel_state_t {   /* 76 bytes: one wheel ([ent+0x3a8+4i] object, its +0x70 wheel data w, type 30) */
    uint32_t present;                   /* 1 when the slot held a type-30 wheel at the capture */
    float    ground_speed;              /* w+0x20 signed spin speed */
    float    susp_offset;               /* w+0x24 filtered suspension offset */
    float    ground_height;             /* w+0x2c terrain height at the wheel */
    float    prev_bump;                 /* w+0x30 previous bumped ground height */
    float    prev_dbump;                /* w+0x34 previous per-step change of the ground height */
    uint32_t unloaded;                  /* w+0x40 off the ground */
    double   iir[5];                    /* w+0x58..+0x7f the suspension target's 2nd-order filter {a1, a2, b0, y1, y2} */
    double   local_y;                   /* wheel object +0x48: local y = rest y + suspension offset */
} i76trn_wheel_state_t;

typedef struct i76trn_state_t {         /* 632 bytes: the player's car as the physics carries it from one step to the next */
    uint32_t valid;                     /* 1 when filled */
    uint32_t parts;                     /* I76TRN_ST_* captured */
    uint32_t frame;                     /* the proxy frame it was captured on (top of frame, before the tick) */
    uint32_t sim_frame;                 /* simclock_frame_count 0x5a7e1c at the capture */
    float    mass;                      /* ent+0xa4 (not restored: a restore onto another car skips wheels / engine) */
    float    rot[9];                    /* obj+0x18 rows right / up / forward (i76tel.h rot[]) */
    double   pos[3];                    /* obj+0x40 world x, y (up), z */
    float    vel[3];                    /* ent+0xbc world velocity, m/s */
    float    speed;                     /* ent+0xac |v| */
    float    inv_speed;                 /* ent+0xb0 1/|v| */
    float    rates[3];                  /* ent+0xc8 body rates pitch, yaw, roll, rad/s */
    float    accel[3];                  /* ent+0xd4 last step's acceleration (the next step's weight transfer reads it) */
    uint32_t ent_flags;                 /* ent+0x454 & I76TRN_ST_FLAG_MASK */
    uint32_t surface;                   /* ent+0x45c */
    float    ground_normal[3];          /* ent+0x460 (the next step's probe normal) */
    float    ground_g;                  /* ent+0x46c */
    float    clearance;                 /* ent+0x470 */
    float    last_ground_y;             /* ent+0x474 ground height at the last grounded step (fall kill: landing 35 m below it) */
    int32_t  gear;                      /* engine ([[ent+0x3c4]+0x70]) +0x08 */
    float    drive_power;               /* engine +0x10 */
    float    rpm;                       /* engine +0x1c */
    float    speedo;                    /* engine +0x24 */
    uint32_t wheel_mask;                /* bit i = wheel slot i captured */
    i76trn_wheel_state_t wheel[6];      /* component slots 0..5 = FL FR ML MR RL RR */
} i76trn_state_t;

typedef struct i76trn_ext_t {           /* at I76TRN_EXT_OFFSET in the same mapping; 1304 bytes */
    uint32_t ext_magic;                 /* I76TRN_EXT_MAGIC, written by the proxy when it serves the commands 7 / 8 */
    uint16_t ext_version;               /* I76TRN_EXT_VERSION */
    uint16_t ext_size;                  /* sizeof(i76trn_ext_t) */
    /* client -> proxy */
    uint32_t restore_parts;             /* I76TRN_CMD_SET_STATE: I76TRN_ST_* to put back, 0 = all */
    uint32_t hotkeys;                   /* I76TRN_HK_* */
    /* proxy -> client */
    uint32_t store_seq;                 /* +1 at every capture (command or Ctrl+9) */
    uint32_t restore_seq;               /* +1 at every restore (command or Ctrl+0) */
    uint32_t restore_frame;             /* the proxy frame of the last restore (top of frame, before the tick) */
    uint32_t readback_bad;              /* fields that did not read back as written in the last restore (0 = landed) */
    uint32_t hotkey_stores;             /* Ctrl+9 / Ctrl+0 presses served */
    uint32_t hotkey_restores;
    i76trn_state_t stored;              /* proxy -> client: the last capture */
    i76trn_state_t target;              /* client -> proxy: what I76TRN_CMD_SET_STATE / Ctrl+0 put back (a capture copies itself here) */
} i76trn_ext_t;

#pragma pack(pop)

#endif /* I76TRN_H */
