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
    DWORD dir_deg;     /* +0x00 impact direction, degrees from car nose */
    DWORD magnitude;   /* +0x04 damage points */
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
static XSetStateFn xset;

/* ---- UDP telemetry to a motion-sim receiver (SimTools/SimHub plugin, or
 * tools/ffb-udp-listen.py). 127.0.0.1:? by default; a receiver on another host
 * needs the port forwarded or the addr changed + rebuild. The payload is the
 * same key=value line as the telemetry file, one datagram per emitted tick. */
static SOCKET g_udp = INVALID_SOCKET;
static struct sockaddr_in g_dst;
#define FFB_UDP_PORT 17676

/* ---- state ---- */
static float g_env_low;                 /* decaying impact/one-shot energy  */
static float g_env_high;
static void *g_seen[16];                /* recently processed impact nodes  */
static int   g_seen_i;
static DWORD g_tick;
static const char *TELEMETRY = "C:\\AutoHotkey\\ffb-state.txt";
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
            float mag = base + k * (float)(int)n->magnitude;   /* ~35..300+ */
            add += mag / 220.0f;
            wsprintfA(buf, "%lu %s dir=%ld dmg=%ld\r\n",
                      g_tick, tag, (long)n->dir_deg, (long)n->magnitude);
            write_file(EVENTLOG, buf, lstrlenA(buf), 1);
        }
        n = (IMPACT_NODE *)n->next;
    }
    return add;
}

static void rumble(float low, float high)
{
    XVIB v;
    if (!xset) return;
    v.wLeftMotorSpeed  = (WORD)(clamp01(low)  * 65535.0f);
    v.wRightMotorSpeed = (WORD)(clamp01(high) * 65535.0f);
    xset(0, &v);
}

HRESULT __stdcall shim_InitSystem(I7FF_BLOCK *b)
{
    static const char *xdlls[] = { "xinput1_3.dll", "xinput9_1_0.dll", "xinput1_4.dll", 0 };
    int i;
    if (!b || b->size != 0x16c) return 0x80070057;   /* invalid struct size */
    for (i = 0; !xset && xdlls[i]; i++) {
        HMODULE m = LoadLibraryA(xdlls[i]);
        if (m) xset = (XSetStateFn)GetProcAddress(m, "XInputSetState");
    }
    {   /* open the UDP telemetry socket (best-effort; files still work if it fails) */
        WSADATA wsa;
        if (WSAStartup(0x0202, &wsa) == 0) {
            g_udp = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            g_dst.sin_family = AF_INET;
            g_dst.sin_port = htons(FFB_UDP_PORT);
            g_dst.sin_addr.s_addr = htonl(0x7f000001);   /* 127.0.0.1 */
        }
    }
    write_file(TELEMETRY, "i7ffshim: init ok\r\n", 19, 0);
    return 0;
}

HRESULT __stdcall shim_SIM_Effect(I7FF_BLOCK *b)
{
    float low, high, dt, engine, terrain, weapon;
    int i, firing_gain;
    char buf[512];
    int n;

    if (!b || b->size != 0x16c) return 0x80070057;
    g_tick++;
    dt = (b->dt > 0 && b->dt <= 0.95f) ? b->dt : 0.05f;

    if (!b->forces_on) {              /* master off: stop everything */
        g_env_low = g_env_high = 0;
        rumble(0, 0);
        return 0;
    }

    /* one-shots (cleared like the real DLL does) */
    if (b->engine_starting) { g_env_low += 0.5f; b->engine_starting = 0; }
    if (b->wpn_cycle)  { g_env_high += 0.30f; b->wpn_cycle = 0; }
    if (b->wpn_link)   { g_env_high += 0.25f; b->wpn_link = 0; }
    if (b->wpn_unlink) { g_env_high += 0.25f; b->wpn_unlink = 0; }

    /* impacts: real-DLL formulas, normalized into the low-motor envelope */
    g_env_low += impacts(b->ordnance,   40.0f, 0.6667f, "ordnance");
    g_env_low += impacts(b->concussion, 35.0f, 0.6667f, "concussion");
    g_env_low += impacts(b->collision,  55.0f, 0.5625f, "collision");

    /* continuous layers */
    engine = 0;
    if (b->engine_running) {          /* loudest at idle, like the real DLL */
        float g = 20.0f - b->speed * 0.5f;
        if (g < 0) g = 0;
        engine = (g / 20.0f) * 0.22f;
    }
    terrain = 0;
    if (!b->airborne && b->surface && b->speed > 1.0f)
        terrain = (b->speed / 165.0f) * 0.18f          /* surface-id order TBD */
                + (b->skidding ? 0.10f : 0) + (b->sliding ? 0.08f : 0);
    weapon = 0;
    firing_gain = 0;
    for (i = 0; i < 6; i++) {
        if (b->hp[i].misfire1 || b->hp[i].misfire2) {
            g_env_high += 0.3f;
            b->hp[i].misfire1 = b->hp[i].misfire2 = 0;
        }
        if (b->hp[i].firing) {
            weapon += 0.35f;
            firing_gain = (int)b->hp[i].gain;
        }
    }

    /* decay + mix */
    g_env_low  -= dt * 2.2f; if (g_env_low  < 0) g_env_low  = 0;
    g_env_high -= dt * 3.0f; if (g_env_high < 0) g_env_high = 0;
    low  = clamp01(g_env_low + engine + terrain);
    high = clamp01(g_env_high + weapon);
    rumble(low, high);

    /* telemetry: one key=value line, ints only (wsprintfA has no %f). Values
     * *1000 keep the force vector's sign+precision. This same line is the file
     * status AND the UDP payload — a motion-sim receiver reads surge≈fx,
     * sway≈fy, plus speed/engine/terrain/impacts. */
    n = wsprintfA(buf,
        "tick=%lu on=%lu spd10=%d surf=%lu run=%lu pitch=%d air=%lu skid=%lu "
        "slide=%lu oil=%lu steer=%d fx1000=%d fy1000=%d fy2_1000=%d "
        "tires=%d,%d,%d,%d fire=%d%d%d%d%d%d gain=%d low100=%d high100=%d\r\n",
        g_tick, b->forces_on, (int)(b->speed * 10), b->surface,
        b->engine_running, b->engine_pitch, b->airborne, b->skidding,
        b->sliding, b->oilslick, b->steer_right ? 1 : (b->steer_left ? -1 : 0),
        (int)(b->force_x * 1000), (int)(b->force_y1 * 1000),
        (int)(b->force_y2 * 1000), b->tire[0], b->tire[1], b->tire[2],
        b->tire[3], b->hp[0].firing != 0, b->hp[1].firing != 0,
        b->hp[2].firing != 0, b->hp[3].firing != 0, b->hp[4].firing != 0,
        b->hp[5].firing != 0, firing_gain,
        (int)(low * 100), (int)(high * 100));
    if (g_udp != INVALID_SOCKET)                      /* every tick for the rig */
        sendto(g_udp, buf, n, 0, (struct sockaddr *)&g_dst, sizeof(g_dst));
    if (!(g_tick & 1))                                /* every other for disk */
        write_file(TELEMETRY, buf, n, 0);
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
