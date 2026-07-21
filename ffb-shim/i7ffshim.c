/* i7ffshim.c — fake i7_SFRCE.DLL: receive Interstate '76's force-feedback
 * stream and drive gamepad rumble (XInput) + a telemetry file.
 *
 * Background (scratchpad-fable/ffb-deep-dive.md, static RE 2026-07-19):
 * i76.exe's FFB is a plugin architecture. The exe computes a 364-byte force
 * state block at 0x4f2328 EVERY sim tick and hands it to i7_SFRCE.DLL, which
 * is the only thing that touches DirectInput. The exe checks just three
 * GetProcAddress names and the HRESULT sign. So a drop-in replacement DLL:
 *   - makes FFB "active" with NO DirectInput device (Mac/Wine!),
 *   - receives engine/terrain/speed/weapon/impact state per tick,
 *   - can rumble any XInput pad and log the whole stream.
 *
 * ABI (verified in disasm): all stdcall, exported undecorated by name.
 *   I7FF_InitSystem(block*)  once at boot; >= 0 means "FF present"
 *   I7FF_SIM_Effect(block*)  every sim tick + after every on/off toggle
 *   I7FF_ExitSystem(void)    at shutdown
 * Contract: validate block[0]==0x16c; clear the one-shot flags after acting
 * (engine-start +0x14, wpn cycle/link/unlink +0x24/28/2c, per-hardpoint
 * +0x04/+0x08); leave impact nodes untouched (+0x10/+0x14 zero) so the exe
 * frees them next tick.
 *
 * Freestanding build (no CRT), imports KERNEL32+USER32; XInput is loaded
 * dynamically (works under Wine; harmless if absent — telemetry still runs).
 * STATUS: compiles + spec-complete; NOT yet run against the live game.
 * Rumble mapping constants are first-guess — tune from the telemetry.
 */

#include <winsock2.h>
#include <windows.h>

/* ---- the force block (offsets from ffb-deep-dive.md §3) ---- */
#pragma pack(push, 1)
typedef struct {
    float dir_deg;     /* +0x00 impact direction, degrees (FLOAT — verified live:
                        *   field held 0x424C0000 = 50.0f, not an int) */
    float magnitude;   /* +0x04 damage points (FLOAT, same) */
    DWORD di_dir;      /* +0x08 DLL scratch */
    DWORD di_mag;      /* +0x0c DLL scratch */
    DWORD started;     /* +0x10 we NEVER set -> exe frees the node */
    void *effect;      /* +0x14 we NEVER set */
    void *next;        /* +0x18 */
    void *prev;        /* +0x1c */
} IMPACT_NODE;

typedef struct {
    DWORD firing;      /* +0x00 nonzero while trigger held */
    DWORD misfire1;    /* +0x04 one-shot (clear after use) */
    DWORD misfire2;    /* +0x08 one-shot (clear after use) */
    DWORD wpn_id;      /* +0x0c */
    float freq;        /* +0x10 */
    DWORD gain;        /* +0x14 */
    DWORD prev;        /* +0x18 DLL scratch */
} HARDPOINT;           /* stride 0x1c */

typedef struct {
    DWORD size;            /* +0x000 == 0x16c */
    DWORD reset;           /* +0x004 */
    DWORD forces_on;       /* +0x008 master switch */
    int   engine_pitch;    /* +0x00c */
    DWORD engine_running;  /* +0x010 */
    DWORD engine_starting; /* +0x014 one-shot */
    DWORD engine_changed;  /* +0x018 */
    DWORD mount_mod2;      /* +0x01c */
    DWORD mount_mod3;      /* +0x020 */
    DWORD wpn_cycle;       /* +0x024 one-shot */
    DWORD wpn_link;        /* +0x028 one-shot */
    DWORD wpn_unlink;      /* +0x02c one-shot */
    HARDPOINT hp[6];       /* +0x030..+0xd7 */
    int   scratch[3];      /* +0x0d8 */
    DWORD vest[3];         /* +0x0e4 vestigial */
    float force_x;         /* +0x0f0 body-frame steering kick */
    float force_y1;        /* +0x0f4 */
    float force_y2;        /* +0x0f8 */
    DWORD steer_right;     /* +0x0fc */
    DWORD steer_left;      /* +0x100 */
    float speed;           /* +0x104 mph, clamped 165 */
    int   tire[4];         /* +0x108 FL/FR/RL/RR status */
    int   tire_prev[4];    /* +0x118 DLL scratch */
    DWORD airborne;        /* +0x128 */ DWORD airborne_prev;
    DWORD skidding;        /* +0x130 */ DWORD skidding_prev;
    DWORD sliding;         /* +0x138 */ DWORD sliding_prev;
    DWORD oilslick;        /* +0x140 */ DWORD oilslick_prev;
    DWORD surface;         /* +0x148 terrain id+1, 0=stopped */
    DWORD surface_prev;    /* +0x14c */
    IMPACT_NODE *ordnance;   /* +0x150 weapon hits on player */
    IMPACT_NODE *concussion; /* +0x154 explosions nearby */
    IMPACT_NODE *dead_list;  /* +0x158 written, never consumed */
    IMPACT_NODE *collision;  /* +0x15c rams/scenery hits */
    float dt;              /* +0x160 frame seconds */
    void *exe_priv;        /* +0x164 */
    DWORD hinstance;       /* +0x168 */
} I7FF_BLOCK;              /* 0x16c bytes */
#pragma pack(pop)

/* ---- XInput, loaded dynamically ---- */
typedef struct { WORD wLeftMotorSpeed, wRightMotorSpeed; } XVIB;
typedef DWORD (WINAPI *XSetStateFn)(DWORD, XVIB *);
typedef DWORD (WINAPI *XGetStateFn)(DWORD, void *);   /* buf big enough for XINPUT_STATE */
static XSetStateFn xset;
static XGetStateFn xget;
static int g_pad = -1;         /* the connected controller slot (0-3), -1 = none yet */

/* scan XInput slots 0-3 for a connected pad; returns the slot or -1 */
static int find_pad(void)
{
    unsigned char st[16];      /* XINPUT_STATE = dwPacketNumber + 14-byte gamepad */
    int i;
    if (!xget) return 0;       /* no getstate: fall back to slot 0 (old behavior) */
    for (i = 0; i < 4; i++)
        if (xget(i, st) == 0)  /* ERROR_SUCCESS = connected */
            return i;
    return -1;
}

/* ---- UDP telemetry to a motion-sim receiver (SimTools/SimHub plugin, or
 * tools/ffb-udp-listen.py). 127.0.0.1:? by default; a receiver on another host
 * needs the port forwarded or the addr changed + rebuild. The payload is the
 * same key=value line as the telemetry file, one datagram per emitted tick. */
static SOCKET g_udp = INVALID_SOCKET;
static struct sockaddr_in g_dst;
#define FFB_UDP_PORT 17676

/* ---- sound-derived rumble envelopes (tools/gpw-envelopes.py output) ----
 * Loaded at init from rumble-envelopes.ini (game dir, or C:\AutoHotkey\). Each
 * line "name=v0,v1,..." is one .gpw effect's amplitude envelope (0-100). We
 * play these to give each real EVENT the FEEL of its actual sound — the rumble
 * follows what the game is doing (skid, fire, impact), never the button. */
#define MAXENV 160
#define MAXLEN 96
typedef struct { char name[16]; unsigned char v[MAXLEN]; int len; } ENVELOPE;
static ENVELOPE g_env[MAXENV];
static int g_nenv;
static int g_tex_idx = -1;   /* the wheel-slip grit texture envelope */
static int g_tex_pos;        /* looping cursor into it */

/* ===== RUMBLE TUNING — every driving-feel constant in one place =====
 * Two motors: LEFT = low-freq/heavy (engine, road, slip grind, weight,
 * impacts, landings); RIGHT = high-freq/buzz (skid chirp, weapon fire, gear
 * clicks). Design canon (informed by sim-tactile practice): keep the CONTINUOUS
 * layers quiet so TRANSIENTS read on top — hierarchy + restraint. Wheel slip is
 * the loud one (driving feel priority); engine/road/weight are a subtle floor;
 * impacts/landings are sharp peaks. Tune these by feel from the telemetry. */
#define R_ENGINE_IDLE  0.32f  /* engine RUMBLE base (LEFT) — low/soft at idle, higher-freq
                               * and louder toward high RPM (follows engine_pitch) */
#define R_ROAD_MAX     0.42f  /* road/sand ceiling at speed (RIGHT, high-freq, sandy) */
#define R_WEIGHT_MAX   0.12f  /* cornering/brake load cue ceiling (LEFT) */
#define R_SLIP_LAT     0.35f  /* how much lateral force feeds wheel slip */
#define R_WEAPON       0.95f  /* weapon-fire buzz — STRONG (combat is the point); gain is
                               * only ~5-10 in this game so we don't scale down by it much */
#define R_LAND_MAX     0.85f  /* landing thump ceiling, scaled by speed (LEFT) */
#define R_BLOWOUT      0.70f  /* tire-blowout jolt (LEFT) */
#define R_IMPACT_NORM  220.0f /* impact magnitude -> 0..1 divisor */
/* ERM-motor shaping (docs/SIM-RUMBLE-RESEARCH.md): the bottom ~30% of a rumble
 * motor's range isn't felt, so an ACTIVE event is lifted above this dead-zone
 * (Min Force); gentle inputs are gamma-2 curved so cruising stays calm and real
 * events pop; motors take the MAX of their effects each frame, never the SUM. */
#define R_DEADZONE     0.28f  /* min-force floor for active EVENT effects */
#define R_ROAD_FLOOR   0.06f  /* road connection: very subtle, "notice it in absence" */
#define R_TH_EVENT     0.01f  /* dead-band below which an event is silent (was 0.05:
                               * things cut out too early, dropped to 20%) */
#define R_TH_AMBIENT   0.004f /* dead-band for ambient floors (was 0.02, -80%) */
#define MAXF(a,b)      ((a) > (b) ? (a) : (b))

/* ---- state ---- */
static float g_env_low;                 /* decaying impact/one-shot energy  */
static float g_env_high;                /* misfire / transient crack (RIGHT) */
static float g_env_wpn;                 /* weapon-fire buzz, slow decay (RIGHT) */
static float g_env_land;                /* landing / blowout transient (LEFT) */
static void *g_seen[16];                /* recently processed impact nodes  */
static int   g_seen_i;
static DWORD g_tick;
static int   g_prev_air;                /* airborne edge -> landing thump */
static int   g_tireflat_prev;           /* which tires were flat -> blowout edge */
static unsigned g_engphase;             /* engine idle-lope oscillator */
static int   g_road_pos;                /* road-texture envelope cursor */
static int   g_road_idx = -1;           /* road-surface texture envelope */
static int   g_wpn_was;                 /* was a weapon firing last frame (kick-start edge) */
static const char *TELEMETRY = "C:\\AutoHotkey\\ffb-state.txt";
static const char *DRIVELOG  = "C:\\AutoHotkey\\ffb-drive.log";   /* time-series for tuning */
static const char *EVENTLOG  = "C:\\AutoHotkey\\ffb-events.txt";

static float clamp01(float v) { return v < 0 ? 0 : (v > 1 ? 1.0f : v); }

static void write_file(const char *path, const char *s, int n, int append)
{
    HANDLE h = CreateFileA(path, append ? FILE_APPEND_DATA : GENERIC_WRITE, FILE_SHARE_READ,
                           0, append ? OPEN_ALWAYS : CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    DWORD w;
    if (h == INVALID_HANDLE_VALUE) return;
    if (append && GetFileSize(h, 0) > 262144) {   /* keep the event log bounded */
        CloseHandle(h);
        h = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, 0);
        if (h == INVALID_HANDLE_VALUE) return;
    }
    WriteFile(h, s, n, &w, 0);
    CloseHandle(h);
}

/* parse rumble-envelopes.ini into g_env[] (freestanding, no CRT) */
static void load_envelopes(void)
{
    static char buf[131072];
    static const char *paths[] = { "rumble-envelopes.ini",
                                    "C:\\AutoHotkey\\rumble-envelopes.ini", 0 };
    HANDLE h = INVALID_HANDLE_VALUE;
    DWORD got = 0;
    char *p;
    int i;
    for (i = 0; paths[i] && h == INVALID_HANDLE_VALUE; i++)
        h = CreateFileA(paths[i], GENERIC_READ, FILE_SHARE_READ, 0,
                        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;             /* no table: physics-only rumble */
    ReadFile(h, buf, sizeof(buf) - 1, &got, 0);
    CloseHandle(h);
    buf[got] = 0;
    p = buf;
    while (*p && g_nenv < MAXENV) {
        char *nl = p, *eq;
        while (*nl && *nl != '\n') nl++;
        if (*nl) *nl = 0;
        if (*p && *p != ';' && *p != '\r' && *p != '#') {
            eq = p;
            while (*eq && *eq != '=') eq++;
            if (*eq == '=') {
                ENVELOPE *e = &g_env[g_nenv];
                char *q = eq + 1;
                int n = 0, val = 0, have = 0;
                *eq = 0;
                lstrcpynA(e->name, p, 16);
                while (*q && n < MAXLEN) {
                    if (*q >= '0' && *q <= '9') { val = val * 10 + (*q - '0'); have = 1; }
                    else if (*q == ',') { e->v[n++] = (unsigned char)val; val = 0; have = 0; }
                    q++;
                }
                if (have && n < MAXLEN) e->v[n++] = (unsigned char)val;
                e->len = n;
                if (n > 0) g_nenv++;
            }
        }
        p = nl + 1;
    }
}

static int find_env(const char *name)
{
    int i;
    for (i = 0; i < g_nenv; i++)
        if (lstrcmpiA(g_env[i].name, name) == 0) return i;
    return -1;
}

/* pick the wheel-slip grit texture: prefer a skid, then a loose-surface loop */
static void pick_texture(void)
{
    static const char *cands[] = { "tskid1", "tskid2", "vcdgrav", "vcddirt",
                                   "vcdsand", "tturn1", 0 };
    int i;
    for (i = 0; cands[i]; i++)
        if ((g_tex_idx = find_env(cands[i])) >= 0) return;
}

/* one looping sample of the grit texture, 0..1 (falls back to a plain
 * oscillator if no envelope table loaded) */
static float texture_tick(void)
{
    if (g_tex_idx < 0 || g_env[g_tex_idx].len <= 0)
        return (g_tick & 1) ? 1.0f : 0.4f;
    g_tex_pos = (g_tex_pos + 1) % g_env[g_tex_idx].len;
    return g_env[g_tex_idx].v[g_tex_pos] / 100.0f;
}

/* pick the ROAD texture from the ground/surface loops (sand/gravel/dirt) — a
 * different sound than the skid chirp, so the road floor feels like ground */
static void pick_road_texture(void)
{
    static const char *cands[] = { "vcdsand", "vcdgrav", "vcddirt", "vcdoil",
                                   "tskid1", 0 };
    int i;
    for (i = 0; cands[i]; i++)
        if ((g_road_idx = find_env(cands[i])) >= 0) return;
}

/* road-surface grit texture, on its OWN cursor + sound so it doesn't lock-step
 * with the slip chirp — gives the tyre-on-ground floor its own life */
static float road_tick(void)
{
    if (g_road_idx < 0 || g_env[g_road_idx].len <= 0)
        return (g_tick % 3) ? 0.5f : 1.0f;
    g_road_pos = (g_road_pos + 2) % g_env[g_road_idx].len;   /* step 2 = a touch coarser */
    return g_env[g_road_idx].v[g_road_pos] / 100.0f;
}

/* per-surface road roughness, indexed by the surf id (0=stopped..9=in-air).
 * GUESS from the terrain-name order — TUNE from telemetry: drive on sand, note
 * the surf= value, and bump that index. Desert game: most ground rough, paved
 * roads smooth. */
static const float R_SURF_ROUGH[10] = {
    /* flattened from field data: the user's ROADS logged as surf 1 & 3, so those
     * are moderate now (were too intense at 0.8/1.0). Still guesses for the rest;
     * tune from ffb-drive.log once we align a surf id to "that was sand". */
    0.0f, 0.55f, 0.55f, 0.60f, 0.80f, 0.70f, 0.45f, 0.75f, 0.75f, 0.0f
};

static int seen_node(void *n)
{
    int i;
    for (i = 0; i < 16; i++) if (g_seen[i] == n) return 1;
    g_seen[g_seen_i] = n;
    g_seen_i = (g_seen_i + 1) & 15;
    return 0;
}

/* walk one impact list; returns added low-motor energy. base/k mirror the
 * real DLL's magnitude formulas ((35..55 + ~0.6*dmg)*100, decayed). */
static float impacts(IMPACT_NODE *n, float base, float k, const char *tag)
{
    float add = 0;
    int guard = 8;
    char buf[128];
    while (n && guard--) {
        if (IsBadReadPtr(n, sizeof(*n))) break;
        if (!n->started && !n->effect && !seen_node(n)) {
            float dmg = n->magnitude;
            float mag;
            if (dmg < 0) dmg = -dmg;
            if (dmg > 500.0f) dmg = 500.0f;            /* clamp: guard vs any stray value */
            mag = base + k * dmg;                       /* ~35..300 */
            add += mag / R_IMPACT_NORM;
            wsprintfA(buf, "%lu %s dir=%d dmg=%d\r\n",
                      g_tick, tag, (int)n->dir_deg, (int)dmg);
            write_file(EVENTLOG, buf, lstrlenA(buf), 1);
        }
        n = (IMPACT_NODE *)n->next;
    }
    return add;
}

/* shape one effect through the sim-tactile chain (docs/SIM-RUMBLE-RESEARCH.md):
 *   Threshold (dead-band: silent until it matters — stops the floor firing on
 *   noise) -> rescale -> Gamma-2 (gentle stays gentle, events pop) -> Min-Force
 *   (lift above the ERM dead-zone so an active event is FELT the frame it fires).
 * floor=0 for ambient layers that should stay a whisper; floor≈dead-zone for
 * events that must land. */
static float shape(float raw, float threshold, float floor)
{
    if (raw <= threshold) return 0;
    raw = (raw - threshold) / (1.0f - threshold);
    if (raw > 1.0f) raw = 1.0f;
    return floor + (1.0f - floor) * raw * raw;
}

static void rumble(float low, float high)
{
    XVIB v;
    if (!xset) return;
    /* re-find the pad every ~1s if we don't have one (hot-plug / late connect) */
    if (g_pad < 0 && (g_tick % 20) == 0)
        g_pad = find_pad();
    if (g_pad < 0) return;
    v.wLeftMotorSpeed  = (WORD)(clamp01(low)  * 65535.0f);
    v.wRightMotorSpeed = (WORD)(clamp01(high) * 65535.0f);
    if (xset(g_pad, &v) != 0)   /* slot went away (unplugged) -> re-scan next time */
        g_pad = -1;
}

HRESULT __stdcall shim_InitSystem(I7FF_BLOCK *b)
{
    static const char *xdlls[] = { "xinput1_3.dll", "xinput9_1_0.dll", "xinput1_4.dll", 0 };
    int i;
    if (!b || b->size != 0x16c) return 0x80070057;   /* invalid struct size */
    for (i = 0; !xset && xdlls[i]; i++) {
        HMODULE m = LoadLibraryA(xdlls[i]);
        if (m) {
            xset = (XSetStateFn)GetProcAddress(m, "XInputSetState");
            xget = (XGetStateFn)GetProcAddress(m, "XInputGetState");
        }
    }
    g_pad = find_pad();        /* find the controller now (re-scanned later if absent) */
    {   /* open the UDP telemetry socket (best-effort; files still work if it fails) */
        WSADATA wsa;
        if (WSAStartup(0x0202, &wsa) == 0) {
            g_udp = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            g_dst.sin_family = AF_INET;
            g_dst.sin_port = htons(FFB_UDP_PORT);
            g_dst.sin_addr.s_addr = htonl(0x7f000001);   /* 127.0.0.1 */
        }
    }
    load_envelopes();
    pick_texture();
    pick_road_texture();
    {   /* record how many envelopes loaded — first thing to check in telemetry */
        char m[64];
        int n = wsprintfA(m, "i7ffshim: init ok, %d envelopes\r\n", g_nenv);
        write_file(TELEMETRY, m, n, 0);
    }
    return 0;
}

/* ===================================================================== *
 *  WHAT THE GAME TELLS US EACH TICK.
 *  Everything the engine computes about the car's physical state, read out
 *  of the raw force block ONCE into named fields in real units. The effects
 *  below read only this — never the raw block — so this struct is the whole
 *  answer to "what signal is coming from the game". Ranges are what we've seen
 *  live. read_game_state() also CONSUMES the latched/one-shot fields (clears
 *  them on the block) so they fire once, not forever.
 * ===================================================================== */
typedef struct {
    /* --- motion --- */
    float speed;          /* mph. 0..~90 */
    int   rpm;            /* engine pitch, an RPM proxy. idle ~1000, redline ~4700 */
    int   running;       /* engine on? */
    /* --- tyre <-> ground (the loud, important stuff) --- */
    int   skidding;      /* rear stepping out */
    int   sliding;       /* front washing / general slide */
    int   oil;           /* on an oil slick */
    int   airborne;      /* all wheels off the ground */
    int   surface;       /* terrain id 1..9 (0 = stopped); indexes R_SURF_ROUGH */
    int   tire[4];       /* per-wheel status; >3000 = flat/blown */
    /* --- forces (body frame) --- */
    float lateral;       /* cornering load (fy), signed. ~±2000 */
    float longitudinal;  /* accel/brake load (fx), signed */
    float fy2;           /* second lateral component (telemetry only) */
    int   steer;         /* -1 left / 0 / +1 right (past a dead-zone) */
    /* --- weapons --- */
    int   firing[6];     /* per-hardpoint: is this gun firing (latched flag) */
    int   gain[6];       /* per-hardpoint strength, ~5..10 */
    int   misfire[6];    /* per-hardpoint dry/jam one-shot */
    int   wpn_cycle, wpn_link, wpn_unlink;   /* UI one-shots */
    int   engine_start;  /* ignition one-shot */
    /* --- impact events (linked lists of {direction°, damage}) --- */
    IMPACT_NODE *ordnance;    /* you were shot */
    IMPACT_NODE *concussion;  /* nearby explosion */
    IMPACT_NODE *collision;   /* you rammed something */
    /* --- timing --- */
    float dt;            /* seconds since last tick (~0.05) */
} GameState;

static void read_game_state(I7FF_BLOCK *b, GameState *g)
{
    int i;
    g->speed    = b->speed;
    g->rpm      = b->engine_pitch;
    g->running  = (int)b->engine_running;
    g->skidding = (int)b->skidding;
    g->sliding  = (int)b->sliding;
    g->oil      = (int)b->oilslick;
    g->airborne = (int)b->airborne;
    g->surface  = (int)b->surface;
    for (i = 0; i < 4; i++) g->tire[i] = b->tire[i];
    g->lateral      = b->force_y1;
    g->longitudinal = b->force_x;
    g->fy2          = b->force_y2;
    g->steer        = b->steer_right ? 1 : (b->steer_left ? -1 : 0);
    for (i = 0; i < 6; i++) {
        g->firing[i]  = (int)b->hp[i].firing;
        g->gain[i]    = (int)b->hp[i].gain;
        g->misfire[i] = (b->hp[i].misfire1 || b->hp[i].misfire2);
        b->hp[i].firing = 0;                       /* consume: the flag latches otherwise */
        b->hp[i].misfire1 = b->hp[i].misfire2 = 0;
    }
    g->wpn_cycle   = (int)b->wpn_cycle;   b->wpn_cycle   = 0;
    g->wpn_link    = (int)b->wpn_link;    b->wpn_link    = 0;
    g->wpn_unlink  = (int)b->wpn_unlink;  b->wpn_unlink  = 0;
    g->engine_start = (int)b->engine_starting; b->engine_starting = 0;
    g->ordnance   = b->ordnance;
    g->concussion = b->concussion;
    g->collision  = b->collision;
    g->dt = (b->dt > 0 && b->dt <= 0.95f) ? b->dt : 0.05f;
}

HRESULT __stdcall shim_SIM_Effect(I7FF_BLOCK *b)
{
    GameState g;
    float low, high, dt, engine, road, road_rough, road_out, weight, slip, tex, slip_low, slip_high, weapon;
    int i, firing_gain, mask, fb[6];
    DWORD f0_raw;
    char buf[600];
    int n;

    if (!b || b->size != 0x16c) return 0x80070057;
    g_tick++;

    if (!b->forces_on) {              /* master off: stop everything */
        g_env_low = g_env_high = g_env_wpn = g_env_land = 0;
        rumble(0, 0);
        return 0;
    }
    read_game_state(b, &g);           /* pull the game's state into named fields */
    dt = g.dt;
    for (i = 0; i < 6; i++) fb[i] = g.firing[i] != 0;    /* (telemetry) */
    f0_raw = (DWORD)g.firing[0];

    /* Each effect below picks: which GAME SIGNAL drives it, HOW we turn that into
     * a 0..1 level, and WHY it feels that way. Transients feed decaying envelopes
     * (globals); continuous effects compute a level for this frame. The MIX at
     * the end takes the MAX per motor. HEAVY motor = body/low-freq, BUZZ = edge. */

    /* -- IGNITION -------------------------------------------------------------
     * SIGNAL  g.engine_start (one-shot when the starter cranks)
     * PROCESS add a short pulse to the heavy transient envelope
     * WHY     a felt "thunk" as the engine catches. */
    if (g.engine_start) g_env_low += 0.30f;

    /* -- WEAPON UI CLICKS -----------------------------------------------------
     * SIGNAL  g.wpn_cycle/link/unlink (one-shots)
     * PROCESS short crisp pulses on the buzz transient envelope
     * WHY     tactile confirm of a menu/loadout action. */
    if (g.wpn_cycle)  g_env_high += 0.30f;
    if (g.wpn_link)   g_env_high += 0.25f;
    if (g.wpn_unlink) g_env_high += 0.25f;

    /* -- IMPACTS --------------------------------------------------------------
     * SIGNAL  g.ordnance/concussion/collision (event lists w/ direction+damage)
     * PROCESS the real DLL's magnitude formulas -> heavy envelope (+ a little
     *         crack on the buzz motor)
     * WHY     getting shot / rammed / blasted should be the sharpest thing you
     *         feel, cued on the hit and decaying fast. */
    {
        float im = 0;
        im += impacts(g.ordnance,   40.0f, 0.6667f, "ordnance");
        im += impacts(g.concussion, 35.0f, 0.6667f, "concussion");
        im += impacts(g.collision,  55.0f, 0.5625f, "collision");
        g_env_low  += im;
        g_env_high += im * 0.35f;
    }

    /* -- LANDING + BLOWOUT ----------------------------------------------------
     * SIGNAL  airborne->ground edge (g.airborne) ; a tyre newly going flat (g.tire)
     * PROCESS one thump into the landing envelope, scaled by speed / fixed jolt
     * WHY     touchdown and a blowout are discrete "events" you should feel land. */
    if (g_prev_air && !g.airborne) {
        float sc = g.speed / 50.0f; if (sc > 1.0f) sc = 1.0f;
        float t = R_LAND_MAX * (0.35f + 0.65f * sc);
        if (t > g_env_land) g_env_land = t;
    }
    g_prev_air = g.airborne;
    mask = 0;
    for (i = 0; i < 4; i++) if (g.tire[i] > 3000) mask |= (1 << i);
    if ((mask & ~g_tireflat_prev) && R_BLOWOUT > g_env_land) g_env_land = R_BLOWOUT;
    g_tireflat_prev = mask;

    /* -- ENGINE (heavy motor, continuous) ------------------------------------
     * SIGNAL  g.rpm (engine pitch, ~1000..4700) ; g.running
     * PROCESS a triangle throb whose RATE and LEVEL both rise with RPM; idle end
     *         kept almost silent
     * WHY     a low rumble that tracks the engine — barely there at idle, growls
     *         higher/louder toward redline. Off when the engine's off. */
    engine = 0;
    if (g.running) {
        float rpm = (g.rpm - 800.0f) / 3200.0f;
        unsigned period; float ph, tri;
        if (rpm < 0) rpm = 0; if (rpm > 1.0f) rpm = 1.0f;
        period = (unsigned)(10.0f - rpm * 7.0f); if (period < 3) period = 3;
        g_engphase++;
        ph = (float)(g_engphase % period) / (float)period;
        tri = ph < 0.5f ? ph * 2.0f : 2.0f - ph * 2.0f;
        engine = R_ENGINE_IDLE * (0.18f + 0.70f * rpm) * (0.5f + 0.5f * tri);
    }

    /* -- ROAD / SAND (buzz motor, continuous) --------------------------------
     * SIGNAL  g.speed ; g.surface (roughness) — NOT the engine
     * PROCESS speed-scaled grit textured by the ground .gpw, with a min-force
     *         floor that grows with speed
     * WHY     a high-freq "sandy" texture that tells you how fast you're rolling
     *         over what — present even coasting with the engine off. */
    road = 0; road_rough = 0; road_out = 0;
    if (!g.airborne && g.speed > 4.0f) {
        float sc = g.speed / 65.0f; if (sc > 1.0f) sc = 1.0f;
        road_rough = (g.surface > 0 && g.surface < 10) ? R_SURF_ROUGH[g.surface] : 0.6f;
        road = R_ROAD_MAX * sc * road_rough * (0.5f + 0.5f * road_tick());
        road_out = shape(road, R_TH_AMBIENT, sc * 0.24f);
    }

    /* -- WEIGHT (heavy motor, continuous) ------------------------------------
     * SIGNAL  g.lateral / g.longitudinal (body-frame force = cornering/accel load)
     * PROCESS a quiet sustained level from the GRIP portion of the force
     * WHY     a subtle sense of the car's mass leaning under you; the loud part
     *         of losing grip lives in SLIP, not here. */
    weight = 0;
    if (!g.airborne) {
        float fy = g.lateral < 0 ? -g.lateral : g.lateral;
        float fx = g.longitudinal < 0 ? -g.longitudinal : g.longitudinal;
        float lat = fy / 1500.0f; if (lat > 1.0f) lat = 1.0f;
        float lon = fx / 1500.0f; if (lon > 1.0f) lon = 1.0f;
        weight = R_WEIGHT_MAX * (0.6f * lat + 0.5f * lon);
    }

    /* -- WHEEL SLIP (both motors, continuous) — THE PRIORITY ------------------
     * SIGNAL  g.skidding/sliding/oil (real traction-loss flags) ; g.lateral ; g.tire
     * PROCESS sum the flags, amplify by cornering force WHILE slipping, gate by
     *         speed; textured by the real skid .gpw -> grind (heavy) + chirp (buzz)
     * WHY     breaking the tyres loose is the signature feel; it comes from the
     *         same physics that plays the skid sound, never from a button. */
    slip = 0;
    if (g.skidding) slip += 0.50f;
    if (g.sliding)  slip += 0.50f;
    if (g.oil)      slip += 0.35f;
    if (g.skidding || g.sliding) {
        float fy = g.lateral < 0 ? -g.lateral : g.lateral;
        if (fy > 2000.0f) fy = 2000.0f;
        slip += (fy / 2000.0f) * R_SLIP_LAT;
    }
    for (i = 0; i < 4; i++) if (g.tire[i] > 3000) slip += 0.12f;
    if (g.airborne || g.speed < 3.0f) slip = 0;
    else { float sc = g.speed / 40.0f; if (sc > 1.0f) sc = 1.0f; slip *= 0.4f + 0.6f * sc; }
    if (slip > 1.0f) slip = 1.0f;
    tex = texture_tick();
    slip_low  = slip * (0.55f + 0.45f * tex);
    slip_high = slip * 0.45f * tex;

    /* -- WEAPONS (buzz motor) ------------------------------------------------
     * SIGNAL  g.firing[] (latched per-hardpoint) ; g.gain[] (~5..10) ; g.misfire[]
     * PROCESS strongest firing gun -> a slow-decay envelope with an OVERDRIVE
     *         KICK on the first frame (full power to beat the motor's ~50-100ms
     *         spin-up), settling to the sustained level; misfire = a crack
     * WHY     combat should hit hard and instantly; decaying means it can't stick
     *         even though the firing flag never clears itself. */
    weapon = 0;
    firing_gain = 0;
    for (i = 0; i < 6; i++) {
        if (g.misfire[i]) g_env_high = MAXF(g_env_high, 0.30f);
        if (g.firing[i]) {
            float gn = g.gain[i] > 0 ? (float)g.gain[i] / 10.0f : 1.0f;   /* gain ~5-10 */
            float w;
            if (gn > 1.0f) gn = 1.0f;
            w = R_WEAPON * (0.75f + 0.25f * gn);
            if (w > weapon) weapon = w;
            if (g.gain[i] > firing_gain) firing_gain = g.gain[i];
        }
    }
    if (weapon > 0) {
        if (!g_wpn_was) g_env_wpn = 1.0f;               /* kick-start (spin the motor up fast) */
        else            g_env_wpn = MAXF(g_env_wpn, weapon);
    }
    g_wpn_was = (weapon > 0);

    /* ================= DECAY + MIX ========================================= */
    g_env_low  -= dt * 2.2f; if (g_env_low  < 0) g_env_low  = 0;
    g_env_high -= dt * 3.0f; if (g_env_high < 0) g_env_high = 0;
    g_env_wpn  -= dt * 1.2f; if (g_env_wpn  < 0) g_env_wpn  = 0;   /* slow -> ~0.3s felt buzz */
    g_env_land -= dt * 2.5f; if (g_env_land < 0) g_env_land = 0;
    /* Shape + MAX per motor (never SUM — the mush trap). Reworked from field feel:
     * LEFT = heavy/low-freq BODY — idle throb, road/ground rumble (moved here: on
     * the high motor it read 'buzzy'), weight, slip grind, impacts, landing.
     * RIGHT = high-freq EDGE — skid chirp, weapon buzz, transient crack. */
    low  = engine;                                          /* RPM rumble, direct */
    low  = MAXF(low, shape(weight,     R_TH_AMBIENT, 0.0f));
    low  = MAXF(low, shape(slip_low,   R_TH_EVENT, R_DEADZONE));
    low  = MAXF(low, shape(g_env_low,  R_TH_EVENT, R_DEADZONE));
    low  = MAXF(low, shape(g_env_land, R_TH_EVENT, R_DEADZONE));
    high = road_out;                                        /* sandy road, speed-scaled */
    high = MAXF(high, shape(slip_high,  R_TH_EVENT, R_DEADZONE));
    high = MAXF(high, shape(g_env_wpn,  R_TH_EVENT, R_DEADZONE));   /* weapon fire (strong) */
    high = MAXF(high, shape(g_env_high, R_TH_EVENT, R_DEADZONE));   /* misfire/crack */
    rumble(clamp01(low), clamp01(high));

    /* telemetry: one key=value line, ints only (wsprintfA has no %f). Values
     * *1000 keep the force vector's sign+precision. This same line is the file
     * status AND the UDP payload — a motion-sim receiver reads surge≈fx,
     * sway≈fy, plus speed/engine/terrain/impacts. */
    n = wsprintfA(buf,
        "tick=%lu on=%lu pad=%d spd10=%d surf=%lu run=%lu pitch=%d air=%lu skid=%lu "
        "slide=%lu oil=%lu steer=%d fx1000=%d fy1000=%d fy2_1000=%d "
        "tires=%d,%d,%d,%d fire=%d%d%d%d%d%d f0=%lu gain=%d "
        "eng=%d road=%d weight=%d slip=%d wpn=%d jolt=%d low100=%d high100=%d\r\n",
        g_tick, b->forces_on, g_pad, (int)(g.speed * 10), (DWORD)g.surface,
        (DWORD)g.running, g.rpm, (DWORD)g.airborne, (DWORD)g.skidding,
        (DWORD)g.sliding, (DWORD)g.oil, g.steer,
        (int)(g.longitudinal * 1000), (int)(g.lateral * 1000),
        (int)(g.fy2 * 1000), g.tire[0], g.tire[1], g.tire[2],
        g.tire[3], fb[0], fb[1], fb[2], fb[3], fb[4], fb[5],
        (unsigned long)f0_raw, firing_gain,
        (int)(engine * 100), (int)(road * 100), (int)(weight * 100),
        (int)(slip * 100), (int)(weapon * 100),
        (int)((g_env_low + g_env_land) * 100), (int)(low * 100), (int)(high * 100));
    if (g_udp != INVALID_SOCKET)                      /* every tick for the rig */
        sendto(g_udp, buf, n, 0, (struct sockaddr *)&g_dst, sizeof(g_dst));
    if (!(g_tick & 1))                                /* every other for disk */
        write_file(TELEMETRY, buf, n, 0);
    if ((g_tick % 10) == 0)                           /* ~2/sec APPENDED time-series
                                                       * so a drive can be reviewed after */
        write_file(DRIVELOG, buf, n, 1);
    return 0;
}

HRESULT __stdcall shim_ExitSystem(void)
{
    rumble(0, 0);
    if (g_udp != INVALID_SOCKET) { closesocket(g_udp); g_udp = INVALID_SOCKET; WSACleanup(); }
    write_file(TELEMETRY, "i7ffshim: exit\r\n", 16, 0);
    return 0;
}

BOOL WINAPI DllMainCRTStartup(HINSTANCE h, DWORD reason, LPVOID res)
{
    (void)h; (void)reason; (void)res;
    return TRUE;
}
