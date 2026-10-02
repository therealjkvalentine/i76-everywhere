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
 * per line, `type name;` or `type name[N];`, <stdint.h> scalars plus float / double / char. Keep it that way.
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

#pragma pack(pop)

#endif /* I76TRN_H */
