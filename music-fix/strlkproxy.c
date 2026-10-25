/*
 * Interstate '76 - in-mission music fix (base game), via an IAT hook.
 *
 * THE PROBLEM. The base-game soundtrack is CD-audio played through MCI: the game
 * opens the "cdaudio" device with mciSendCommandA and plays track N. GOG ships
 * those tracks as music\N.mp3, but on a machine with no optical drive the MCI
 * cdaudio device won't open (MCIERR 266) - so there is no music, and the game
 * pops "Please insert CD 2". (Nitro is unaffected - it uses audiere.dll.)
 *
 * WHY NOT A winmm.dll PROXY. The obvious fix - drop a winmm.dll in the game folder
 * - does NOT work here: dgVoodoo hardens the DLL search path to System32, so the
 * game binds mciSendCommandA to the real C:\Windows\SysWOW64\winmm.dll before an
 * app-dir winmm can load (verified with a module lister; DotLocal didn't help).
 *
 * THE FIX. We instead proxy Strlkup.dll - a tiny (5-export) DLL that i76.exe
 * imports STATICALLY, so it loads at process init. All five exports are forwarded
 * to the renamed original (strlkup_orig.dll). In DllMain we rewrite i76.exe's
 * Import Address Table slot for WINMM.dll!mciSendCommandA to point at our own
 * function (the loader has already snapped that slot to the real winmm before any
 * DllMain runs, and the game doesn't call it until a mission starts - so the
 * overwrite always wins). Our hook emulates the cdaudio device: MCI_OPEN cdaudio
 * succeeds against a virtual device, MCI_PLAY of track N plays music\N.mp3 through
 * the mpegvideo MCI device (which works fine with no CD), and status queries
 * report a disc present so the CD prompt never fires. Every non-cdaudio call is
 * passed straight to the real winmm.
 *
 * REVERT: restore the original Strlkup.dll (setup keeps it as strlkup_orig.dll).
 * Build: build.ps1 (32-bit, w64devkit). I76MUSIC_LOG=1 -> mciproxy.log for tracing.
 */
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#ifdef _MSC_VER
#include <intrin.h>
#if defined(_MSC_VER) && !defined(__clang__)
/* MSVC has no __builtin_return_address; the co-op hooks (13b5455) and cursormap.c use it, which broke the MSVC
   link (LNK2019 ___builtin_return_address, 2026-10-07). Only level 0 is used anywhere in this file. */
#define __builtin_return_address(level) _ReturnAddress()
#endif
#endif
#include <tlhelp32.h>
#include "../tools/telemetry/i76tel.h"   /* telemetry export layout, shared with tools/telemetry/i76tel.py */
typedef char i76tel_v3_size_check[(sizeof(i76tel_frame_t) == 664 && sizeof(i76tel_event_t) == 56) ? 1 : -1];   /* i76tel.h v3: README layout */
#include "../tools/trainer/i76trn.h"     /* trainer control block layout, shared with tools/trainer/i76trainer_gui.py */

#define FAKE_CD_ID 0xC0DE

static char     g_dir[MAX_PATH];
static char     g_alias[16] = "i76cd";
static int      g_open = 0;
static int      g_logging = 0;

/* ENVIRONMENT READS (2026-10-10, docs/records/PROXY-CLEANUP-2026-10-10.md). Every switch read goes through env_str: a
 * value that is unset, empty, or too long for the caller's buffer (cap - 1 characters) reads as unset (0, buf[0] = 0),
 * which is exactly what the hand-rolled `n && n < sizeof(v)` reads it replaced did. cap is the buffer size each site
 * always used, kept so that an over-long value is rejected exactly as before. */
static DWORD env_str(const char *name, char *buf, DWORD cap) {
    DWORD n = GetEnvironmentVariableA(name, buf, cap);
    if (n == 0 || n >= cap) { if (cap) buf[0] = 0; return 0; }
    return n;
}
/* I76_SHM_SUFFIX=<text> (lab, 2026-10-19, shm-suffix lane; docs/records/TWO-CLOCKS-2026-10-19.md "safety finding"): appended to every
 * named kernel object the proxy creates (the three file mappings Local\I76Telemetry, Local\I76Trainer, Local\I76SimTick; no events,
 * mutexes, semaphores or pipes in the proxy are named). Unset = the default names, which every proxy instance on the machine
 * shares - so a lab run beside the owner's game must set it. Backslashes in the value become '_' (a name cannot have them). */
static const char *shm_suffix(void) {
    static char s[64]; static int done;
    if (!done) {
        char v[64]; int i;
        done = 1;
        if (env_str("I76_SHM_SUFFIX", v, sizeof(v))) { for (i = 0; v[i]; i++) s[i] = v[i] == '\\' ? '_' : v[i]; s[i] = 0; }
    }
    return s;
}
/* base + suffix into out (cap bytes; the result is the pointer for CreateFileMappingA) */
static const char *shm_name(char *out, size_t cap, const char *base) {
    _snprintf(out, cap, "%s%s", base, shm_suffix()); out[cap - 1] = 0;
    return out;
}
/* presence only, whatever the value (the `GetEnvironmentVariableA(name, NULL, 0)` switches) */
static int env_present(const char *name) { return GetEnvironmentVariableA(name, NULL, 0) > 0; }
/* first character '1' -> 1, '0' -> 0; unset, empty, too long for cap, or any other character -> dflt */
static int env_flag(const char *name, DWORD cap, int dflt) {
    char v[32];
    if (cap > sizeof(v)) cap = sizeof(v);
    if (!env_str(name, v, cap)) return dflt;
    return v[0] == '1' ? 1 : v[0] == '0' ? 0 : dflt;
}
/* atoi of the value; unset, empty or too long for cap -> dflt */
static int env_int(const char *name, DWORD cap, int dflt) {
    char v[32];
    if (cap > sizeof(v)) cap = sizeof(v);
    return env_str(name, v, cap) ? atoi(v) : dflt;
}

typedef MCIERROR (WINAPI *mciStrFn)(LPCSTR, LPSTR, UINT, HWND);
typedef MCIERROR (WINAPI *mciCmdFn)(MCIDEVICEID, UINT, DWORD_PTR, DWORD_PTR);
static mciStrFn real_mciSendStringA;
static mciCmdFn real_mciSendCommandA;

/* --- aux (CD-audio volume) -------------------------------------------------
 * WHY THESE ARE HOOKED (added 2026-08-04):
 *
 * With only mciSendCommandA hooked, mciproxy.log showed the IAT patch landing and
 * then NOTHING - the game never called it once, in a mission or anywhere else. It
 * was not failing at CD audio, it was declining to attempt it.
 *
 * The game imports auxGetNumDevs / auxGetDevCapsA / auxSetVolume, and on a machine
 * with no optical drive the real auxGetNumDevs() returns 0 (measured). On 90s
 * hardware CD audio was mixed in ANALOGUE and its level set through an `aux`
 * device, so "no aux device" meant "no CD audio present" - and the engine gates on
 * that before it ever opens the MCI device.
 *
 * So advertise exactly one aux device of type AUXCAPS_CDAUDIO when the system has
 * none. That is the gate the engine is checking.
 *
 * It also fixes the volume limitation the README flagged: auxSetVolume was a no-op
 * with no device, so the in-game music slider could not attenuate our mpegvideo
 * playback. Now it is translated to `setaudio <alias> volume to N`.
 */
typedef UINT     (WINAPI *auxNumFn)(void);
typedef MMRESULT (WINAPI *auxCapsFn)(UINT_PTR, LPAUXCAPSA, UINT);
typedef MMRESULT (WINAPI *auxVolFn)(UINT, DWORD);
static auxNumFn  real_auxGetNumDevs;
static auxCapsFn real_auxGetDevCapsA;
static auxVolFn  real_auxSetVolume;

static DWORD g_volume = 1000;      /* MCI scale, 0..1000 */

static void vmlog(const char *fmt, va_list ap) {
    char path[MAX_PATH]; _snprintf(path, sizeof(path), "%s\\mciproxy.log", g_dir);
    FILE *f = fopen(path, "a"); if (!f) return;
    vfprintf(f, fmt, ap);
    fputc('\n', f); fclose(f);
}
static void mlog(const char *fmt, ...) {
    va_list ap;
    if (!g_logging) return;
    va_start(ap, fmt); vmlog(fmt, ap); va_end(ap);
}
/* flog: written whether or not I76MUSIC_LOG is set. For rare, high-value events only (a CD prompt is one: it shows
 * up on a handful of launches and the whole point of catching it is not to need the run again). */
static void flog(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt); vmlog(fmt, ap); va_end(ap);
}
static void wmr_before_real(const char *what);   /* winmmrace.c */
static void wmr_apply_fix(const char *when);
static DWORD WINAPI wmr_census_thread(LPVOID arg);
static int wmr_trace_on(void);
#include "nitro.c"       /* exe detection (Gold / Nitro / other) and the Gold -> Nitro site map (nitro-port lane, 2026-10-21) */

/* resolve the real winmm entry points from the already-loaded system winmm */
static void ensure_real(void) {
    if (real_mciSendCommandA) return;
    HMODULE w = GetModuleHandleA("winmm.dll");
    if (!w) w = LoadLibraryA("winmm.dll");
    if (w) {
        real_mciSendStringA  = (mciStrFn)GetProcAddress(w, "mciSendStringA");
        real_mciSendCommandA = (mciCmdFn)GetProcAddress(w, "mciSendCommandA");
        real_auxGetNumDevs   = (auxNumFn)GetProcAddress(w, "auxGetNumDevs");
        real_auxGetDevCapsA  = (auxCapsFn)GetProcAddress(w, "auxGetDevCapsA");
        real_auxSetVolume    = (auxVolFn)GetProcAddress(w, "auxSetVolume");
    }
}

/* --- the music thread (I76_MUSIC_THREAD=1, off by default) ---------------------------------------------------
 * Every mciSendString the proxy makes (open / play / pause / status of the mp3) normally runs on the GAME's thread,
 * inside its MCI call. When the audio device does not answer - Wine with no output device, a CoreAudio device that is
 * being reconfigured - the mpegvideo open blocks in quartz / mmdevapi and the whole game freezes with it (measured on
 * the Mac 2026-10-04/05: main thread parked in quartz <- mciqtz32 <- WINMM, at the shell and at mission start).
 * With the switch, one dedicated thread owns every MCI string call (MCI aliases belong to the thread that opened
 * them, so all of them must come from the same one); the game's thread hands the command over and waits at most
 * 300 ms. A call that does not come back in time answers "device not ready" and the game goes on; while the music
 * thread is stuck for over a second, further calls fail at once instead of queueing behind it. */
typedef struct mreq { struct mreq *next; HANDLE done; volatile LONG state; /* 0 queued, 1 done, 2 abandoned */
                      MCIERROR err; UINT retlen; char cmd[MAX_PATH + 96]; char ret[128]; } mreq;
static int g_mt_on = -1;
static CRITICAL_SECTION g_mq_cs;
static mreq *g_mq_head, *g_mq_tail;
static HANDLE g_mq_sem;
static volatile LONG g_mq_busy_since;                       /* GetTickCount|1 while a call runs, 0 when idle */
static DWORD WINAPI music_worker(LPVOID arg) {
    (void)arg;
    for (;;) {
        mreq *r;
        WaitForSingleObject(g_mq_sem, INFINITE);
        EnterCriticalSection(&g_mq_cs);
        r = g_mq_head; if (r) { g_mq_head = r->next; if (!g_mq_head) g_mq_tail = NULL; }
        LeaveCriticalSection(&g_mq_cs);
        if (!r) continue;
        InterlockedExchange(&g_mq_busy_since, (LONG)(GetTickCount() | 1));
        r->err = real_mciSendStringA(r->cmd, r->retlen ? r->ret : NULL, r->retlen, NULL);
        InterlockedExchange(&g_mq_busy_since, 0);
        if (InterlockedCompareExchange(&r->state, 1, 0) == 2) {        /* the caller gave up: ours to free */
            CloseHandle(r->done); HeapFree(GetProcessHeap(), 0, r);
        } else SetEvent(r->done);
    }
}
static int music_thread_on(void) {
    if (g_mt_on < 0) {
        char v[8]; DWORD n = GetEnvironmentVariableA("I76_MUSIC_THREAD", v, sizeof(v));
        g_mt_on = n && v[0] == '1';
        if (g_mt_on) {
            InitializeCriticalSection(&g_mq_cs);
            g_mq_sem = CreateSemaphoreA(NULL, 0, 0x7fffffff, NULL);
            CloseHandle(CreateThread(NULL, 0, music_worker, NULL, 0, NULL));
            mlog("  music-thread: on (MCI string calls off the game thread, 300 ms wait)");
        }
    }
    return g_mt_on;
}
static MCIERROR mci_call(const char *cmd, char *ret, UINT retlen) {
    static DWORD warned;
    mreq *r; LONG busy; MCIERROR e;
    ensure_real();
    if (!real_mciSendStringA) return MCIERR_DEVICE_NOT_READY;
    wmr_before_real(cmd);
    if (!music_thread_on()) return real_mciSendStringA(cmd, ret, retlen, NULL);
    busy = g_mq_busy_since;
    if (busy && GetTickCount() - (DWORD)busy > 1000) {
        if (GetTickCount() - warned > 5000) { mlog("  music-thread: stuck for %lu ms - '%s' skipped", GetTickCount() - (DWORD)busy, cmd); warned = GetTickCount(); }
        return MCIERR_DEVICE_NOT_READY;
    }
    r = (mreq *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof *r);
    if (!r) return MCIERR_OUT_OF_MEMORY;
    lstrcpynA(r->cmd, cmd, sizeof(r->cmd));
    r->retlen = ret ? (retlen < sizeof(r->ret) ? retlen : (UINT)sizeof(r->ret)) : 0;
    r->done = CreateEventA(NULL, TRUE, FALSE, NULL);
    EnterCriticalSection(&g_mq_cs);
    if (g_mq_tail) g_mq_tail->next = r; else g_mq_head = r;
    g_mq_tail = r;
    LeaveCriticalSection(&g_mq_cs);
    ReleaseSemaphore(g_mq_sem, 1, NULL);
    if (WaitForSingleObject(r->done, 300) != WAIT_OBJECT_0 && InterlockedCompareExchange(&r->state, 2, 0) == 0) {
        mlog("  music-thread: '%s' did not answer in 300 ms - the game goes on", cmd);
        return MCIERR_DEVICE_NOT_READY;                         /* the worker frees r when the call returns */
    }
    WaitForSingleObject(r->done, INFINITE);                     /* done (possibly just after the timeout) */
    if (ret && retlen) lstrcpynA(ret, r->ret, retlen);
    e = r->err;
    CloseHandle(r->done); HeapFree(GetProcessHeap(), 0, r);
    return e;
}

/* --- aux hooks ------------------------------------------------------------ */
/* mci_str is defined below; hook_auxSetVolume needs it to push the volume onto the
 * playing alias. Forward-declared rather than moving these hooks further down, so
 * the aux code stays beside the comment explaining why it exists. */
static void mci_str(const char *cmd);

/* How many aux devices the SYSTEM has. A windowing layer with its own virtual CD (DxWnd, the Mac's daily path) hooks
 * GetProcAddress too, so "the real auxGetNumDevs" can resolve into that layer and report its fake drives (2 under
 * DxWnd, measured 2026-10-04) even with its virtual CD switched off - and the proxy then stood aside for a CD player
 * that does not exist: the game opened the cdaudio device and never issued a PLAY. Count only what winmm.dll itself
 * reports. */
static UINT real_aux_devices(void) {
    static int foreign = -1;
    ensure_real();
    if (!real_auxGetNumDevs) return 0;
    if (foreign < 0) {
        HMODULE m = NULL; char path[MAX_PATH] = "", *b = path, *q;
        GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)real_auxGetNumDevs, &m);
        if (m) GetModuleFileNameA(m, path, sizeof(path));
        for (q = path; *q; q++) if (*q == '\\' || *q == '/') b = q + 1;
        foreign = m && lstrcmpiA(b, "winmm.dll") != 0;
        if (foreign) mlog("  aux devices come from %s, not winmm.dll (a layer's virtual CD): counted as none", b);
    }
    if (!foreign) wmr_before_real("auxGetNumDevs");
    return foreign ? 0 : real_auxGetNumDevs();
}

/* Claim one CD-audio aux device only when the system genuinely has none, so a
 * machine WITH real aux hardware keeps its own behaviour untouched. */
static UINT WINAPI hook_auxGetNumDevs(void) {
    UINT n;
    ensure_real();
    n = real_aux_devices();
    mlog("auxGetNumDevs called (real=%u) -> %u", n, n ? n : 1);
    if (n == 0) return 1;
    return n;
}

static MMRESULT WINAPI hook_auxGetDevCapsA(UINT_PTR id, LPAUXCAPSA caps, UINT size) {
    UINT n;
    ensure_real();
    n = real_aux_devices();
    if (n == 0 && caps && size >= sizeof(AUXCAPSA)) {
        memset(caps, 0, size);
        caps->wMid = 1; caps->wPid = 1; caps->vDriverVersion = 0x0100;
        lstrcpynA(caps->szPname, "I76 CD Audio", sizeof(caps->szPname));
        caps->wTechnology = AUXCAPS_CDAUDIO;   /* the thing the engine looks for */
        caps->dwSupport   = AUXCAPS_VOLUME;
        mlog("auxGetDevCapsA(%u) -> fake CD-audio caps (AUXCAPS_CDAUDIO)", (unsigned)id);
        return MMSYSERR_NOERROR;
    }
    mlog("auxGetDevCapsA(%u) passed through (real n=%u)", (unsigned)id, n);
    return real_auxGetDevCapsA ? real_auxGetDevCapsA(id, caps, size) : MMSYSERR_NODRIVER;
}

static MMRESULT WINAPI hook_auxSetVolume(UINT id, DWORD vol) {
    /* aux volume is two 16-bit channels; MCI wants 0..1000. Take the louder. */
    DWORD lo = LOWORD(vol), hi = HIWORD(vol);
    DWORD peak = (hi > lo) ? hi : lo;
    UINT n;
    ensure_real();
    g_volume = (peak * 1000UL) / 0xFFFFUL;
    if (g_open) {
        char cmd[96];
        _snprintf(cmd, sizeof(cmd), "setaudio %s volume to %lu", g_alias, (unsigned long)g_volume);
        mci_str(cmd);
    }
    mlog("auxSetVolume(0x%08lX) -> %lu/1000", (unsigned long)vol, (unsigned long)g_volume);
    n = real_aux_devices();
    if (n > 0 && real_auxSetVolume) return real_auxSetVolume(id, vol);
    return MMSYSERR_NOERROR;
}

/* --- the fake disc -------------------------------------------------------- */
/* Original layout: track 1 DATA, tracks 2..17 AUDIO. GOG's music\N.mp3 numbering follows the CD track numbers
 * except four files (3/15/16/17.mp3 hold disc 17/16/3/15; I76_MUSIC_DISC_ORDER below translates them).
 * Retail 1.0 (2026-10-16, docs/records/MUSIC-RETAIL-INTENT.md) reads this TOC with first track = 1 hard-coded and
 * MCI_STATUS_NUMBER_OF_TRACKS as the last; it never asks for the first track. */
#define FIRST_TRACK 2
/* the last audio track of the virtual disc: 17 (the Gold CD); on Nitro the highest music\N.mp3 present (nitro.c port: GOG's
 * Nitro ships 2..11), set once in nitro_dllmain. A variable since 2026-10-21; 17 on Gold, as the constant was. */
#define LAST_TRACK_MAX 32
static int g_last_track = 17;
#define LAST_TRACK  g_last_track

static DWORD g_timeFormat = MCI_FORMAT_MSF;
static int   g_curTrack = 0;
static int   g_playingTrack = 0;   /* what is REALLY on the head right now */
/* The engine never asks for one track: every MCI_PLAY carries MCI_FROM|MCI_TO (flags 0xC in every field log), the
 * run N..15 built by 0x424190 from the TOC table (i76-map sound.md; docs/MUSIC-TRACK-MAP.md). Until 2026-10-01 the
 * proxy read only dwFrom, so the mpegvideo device stopped after one song, the exe's status poll (0x424550; every
 * 60 s in a mission, 5 s in the shell: 0x42341b) saw playing -> stopped and re-issued the same track: one song
 * looping with gaps. g_runStart / g_runEnd hold the requested run; playing_now() advances to the next track when the
 * current one ends - but only when the exe asks, i.e. at its next poll, so a mission run has 0-60 s of silence
 * between songs (lab logs 2026-10-04: every song change 60.0-60.5 s after the last). A real CD plays the run without
 * a gap. I76_MUSIC_GAPLESS=1 (below) advances within ~0.5 s instead. */
static int   g_runStart = 0, g_runEnd = 0;
/* I76_MUSIC_RESUME (default on; =0 = the old stop-and-restart): the engine STOPs / PAUSEs / CLOSEs the CD whenever it
 * leaves the driving view (the in-mission menu, a cutscene, the shell) and later re-issues MCI_PLAY for the same run,
 * which a real CD player - and this proxy until 2026-10-04 - answered by starting the song again from 0:00 (owner:
 * "music should continue, not restart, when I go back into the game from a menu"). Now a stop pauses the mp3 where it
 * is, and a PLAY of the same run resumes it; a PLAY of anything else closes it and starts the new track as before.
 * 2026-10-16 (static, retail 1.0 and AiO alike): the in-mission menu (0x44fc00 retail) and movies do not STOP the CD,
 * they call the pause toggle (AiO 0x424190: MCI_PAUSE 0x809 when the status reads playing, MCI_RESUME 0x855 when it
 * reads paused, a fresh MCI_PLAY when it reads stopped). The proxy never answers "paused", so the exe's unpause took
 * the stopped branch and re-issued PLAY: that was the restart. Real STOPs come only at mission start / win / Replay
 * and on each shell entry, where retail restarts the track. I76_MUSIC_TRUE_PAUSE=1 (below) answers the pause exactly. */
static int   g_resumeOn = -1, g_paused = 0, g_pausedRunStart = 0, g_pausedRunEnd = 0;
static int   g_truePaused = 0;     /* paused by MCI_PAUSE under I76_MUSIC_TRUE_PAUSE: status reads MCI_MODE_PAUSE */
static int music_retail(void) {    /* I76_MUSIC_RETAIL=1: every retail-1.0 music option at once (each still overridable) */
    static int r = -1;
    if (r < 0) r = env_flag("I76_MUSIC_RETAIL", 8, 0);
    return r;
}
static int resume_on(void) {       /* default on; default off under I76_MUSIC_RETAIL (stops are stops, as on the CD) */
    if (g_resumeOn < 0) { char v[8]; DWORD n = env_str("I76_MUSIC_RESUME", v, sizeof(v)); g_resumeOn = n ? !(v[0] == '0') : !music_retail(); }
    return g_resumeOn;
}
/* Three music options (2026-10-04; docs/MUSIC-TRACK-MAP.md top section, lab docs/MUSIC-RUN-END-2026-10-04.md):
 *  - run end (default: EXCLUSIVE, a bug fix; I76_MUSIC_TO_INCLUSIVE=1 restores the old reading). MCI_TO is an end
 *    POSITION: "play from track N to the start of track T" stops before T. The exe only passes TOC track starts, so
 *    the last track is T-1. Read inclusively, every AiO mission run 12..15 played 15.mp3 as an extra song and M09's
 *    15..16 played 16.mp3 after 15.
 *  - I76_MUSIC_DISC_ORDER=1 (off): GOG's mp3s are not in the disc's order for four tracks (frame-walk lengths vs the
 *    redump TOC): disc 3 = 16.mp3, 15 = 17.mp3, 16 = 15.mp3, 17 = 3.mp3. Applied to the files played AND to the TOC
 *    lengths/positions the exe reads, so the disc the exe sees is the original's.
 *  - I76_MUSIC_SHELL=1997 (off): in the shell (game state [0x4c2164] == 6) the Gold DLL's menu 13 and credits 8 become
 *    the 1997 DLL's choices, one track each: 13 -> disc 15 (Ovum Bisquit), 8 -> disc 16 (Malochio Down). The exe's
 *    own 5 s shell poll replays the requested track when it stops, so each loops. The remapped play always uses the
 *    disc-order file (17.mp3 / 15.mp3), with or without I76_MUSIC_DISC_ORDER, since the option asks for those songs. */
/* Retail-1.0 options (2026-10-16, docs/records/MUSIC-RETAIL-INTENT.md; all off by default, all on with
 * I76_MUSIC_RETAIL=1, each overridable by its own variable):
 *  - I76_MUSIC_GAPLESS=1: the exe's music watchdog (0x423400) reads GetTickCount through `call [0x4bc100]` at 0x42340d
 *    on every call while music is marked playing. That one call site is repointed to gapless_tick(), which returns the
 *    real tick and, at most every 500 ms, asks the mp3 whether the song ended and starts the next song of the run. Only
 *    within a run: the end of the run is still left to the exe's own poll (0-60 s later in a mission, then its track-2
 *    fallback), as on the CD. The sim clock's GetTickCount calls are not touched.
 *  - I76_MUSIC_TRUE_PAUSE=1: MCI_PAUSE pauses and MCI_STATUS_MODE then reads MCI_MODE_PAUSE; MCI_RESUME (0x855)
 *    continues. Matches the CD for the in-mission menu and movies, including during the track-2 fallback run, where
 *    the stop-as-pause path (I76_MUSIC_RESUME) restarts the mission's own run instead.
 *  - I76_MUSIC_MISSIONS=1997: the 1997 CD's T16.MSN has WRLD 14 (Untitled #13 alone); GOG / Gold miss8 + miss16 have
 *    7 (run 7..14). In a mission whose name (0x5049f0, the exe's own t17 check reads it) is t16, a run that starts at
 *    7 starts at 14 alone. (S01: 1997 = 1, GOG miss16 = 1, only GOG miss8 = 2; not remapped.) */
static int g_gapless = 0, g_truePause = 0, g_missions1997 = 0;
static int g_toIncl = -1, g_discOrder = 0, g_shell1997 = 0;
static int g_runForce = 0, g_playingForce = 0, g_pausedForce = 0;   /* 1 = the run is a shell-1997 remap */
static void apply_music_gapless(void);
static void music_opts(void) {
    char v[16]; DWORD n; int r;
    if (g_toIncl >= 0) return;
    r = music_retail();
    g_toIncl    = env_flag("I76_MUSIC_TO_INCLUSIVE", sizeof(v), 0);
    g_discOrder = env_flag("I76_MUSIC_DISC_ORDER", sizeof(v), r);
    n = env_str("I76_MUSIC_SHELL", v, sizeof(v));        g_shell1997 = n ? (lstrcmpA(v, "1997") == 0) : r;
    g_gapless   = env_flag("I76_MUSIC_GAPLESS", sizeof(v), r);
    g_truePause = env_flag("I76_MUSIC_TRUE_PAUSE", sizeof(v), r);
    n = env_str("I76_MUSIC_MISSIONS", v, sizeof(v));     g_missions1997 = n ? (lstrcmpA(v, "1997") == 0) : r;
    if (g_exe == EXE_NITRO && (g_discOrder || g_shell1997 || g_missions1997)) {   /* facts about the Gold CD / GOG Gold's mp3s */
        mlog("  music: Nitro - disc order, shell 1997 and missions 1997 describe the Gold CD: off");
        g_discOrder = g_shell1997 = g_missions1997 = 0;
    }
    mlog("  music: run end %s, disc order %s, shell %s, resume %s",
         g_toIncl ? "INCLUSIVE (I76_MUSIC_TO_INCLUSIVE=1, old)" : "exclusive",
         g_discOrder ? "ON {3:16,15:17,16:15,17:3}" : "off (N -> N.mp3)",
         g_shell1997 ? "1997 (13 -> disc 15, 8 -> disc 16, one track)" : "as asked", resume_on() ? "on" : "off");
    mlog("  music: retail set %s, gapless %s, true pause %s, missions %s", r ? "ON (I76_MUSIC_RETAIL=1)" : "off",
         g_gapless ? "on" : "off", g_truePause ? "on" : "off", g_missions1997 ? "1997 (t16 7 -> 14 alone)" : "as the files say");
    if (g_gapless) apply_music_gapless();
}
/* disc track -> music\N.mp3 number */
static int disc_file(int trk, int force) {
    if (g_discOrder || force) switch (trk) { case 3: return 16; case 15: return 17; case 16: return 15; case 17: return 3; }
    return trk;
}
static DWORD game_state(void) {
    DWORD a = NA(0x004c2164);
    return (!a || IsBadReadPtr((void *)(DWORD_PTR)a, 4)) ? 0xFFFFFFFFu : *(volatile DWORD *)(DWORD_PTR)a;
}
static MCIERROR play_track(int track);
static DWORD g_lenCache[LAST_TRACK_MAX + 1];   /* ms, 0 = not yet queried */

static void mci_str(const char *cmd);

/* Ask the real MCI how long a track is, once, and remember. The engine asks for
 * every track's length before it will play anything, and a zero answer reads as an
 * empty disc. */
static DWORD track_len_ms(int trk) {
    char mp3[MAX_PATH], cmd[MAX_PATH + 64], ret[64];
    if (trk < FIRST_TRACK || trk > LAST_TRACK) return 0;
    if (g_lenCache[trk]) return g_lenCache[trk];
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, disc_file(trk, 0));
    if (GetFileAttributesA(mp3) == INVALID_FILE_ATTRIBUTES) return 0;
    ensure_real();
    if (!real_mciSendStringA) return 0;
    _snprintf(cmd, sizeof(cmd), "open \"%s\" type mpegvideo alias i76len", mp3);
    if (mci_call(cmd, NULL, 0) != 0) return 0;
    ret[0] = 0;
    if (mci_call("status i76len length", ret, sizeof(ret)) == 0)
        g_lenCache[trk] = (DWORD)strtoul(ret, NULL, 10);
    mci_call("close i76len", NULL, 0);
    return g_lenCache[trk];
}

static DWORD disc_len_ms(void) {
    int i; DWORD t = 0;
    for (i = FIRST_TRACK; i <= LAST_TRACK; i++) t += track_len_ms(i);
    return t;
}

/* Where track N STARTS on the disc, cumulatively.
 *
 * This is what MCI_STATUS_POSITION + MCI_TRACK asks, and getting it wrong is what
 * stopped playback after the open already worked. The log showed the game querying
 * position for track 2..17 in sequence - it is reading a table of contents, and it
 * derives each track's length from the difference between consecutive starts. I was
 * answering with the current PLAYBACK position (0 while stopped), so every track
 * looked zero-length and there was nothing to play.
 *
 * Only the relative spacing matters, so audio is laid out from zero; the data track
 * ahead of it is not modelled. */
static DWORD track_start_ms(int trk) {
    int i; DWORD t = 0;
    if (trk <= FIRST_TRACK) return 0;
    for (i = FIRST_TRACK; i < trk && i <= LAST_TRACK; i++) t += track_len_ms(i);
    return t;
}

static DWORD position_ms(void) {
    char cmd[64], ret[64];
    if (!g_open) return 0;
    ensure_real();
    if (!real_mciSendStringA) return 0;
    _snprintf(cmd, sizeof(cmd), "status %s position", g_alias);
    ret[0] = 0;
    if (mci_call(cmd, ret, sizeof(ret)) != 0) return 0;
    return (DWORD)strtoul(ret, NULL, 10);
}

static int playing_now(void) {
    char cmd[64], ret[64];
    if (!g_open) return 0;
    ensure_real();
    if (!real_mciSendStringA) return 0;
    _snprintf(cmd, sizeof(cmd), "status %s mode", g_alias);
    ret[0] = 0;
    if (mci_call(cmd, ret, sizeof(ret)) != 0) return 0;
    if (strstr(ret, "playing") != NULL) return 1;
    if (strstr(ret, "paused") != NULL) return 0;                                         /* paused is not ended */
    if (g_playingTrack && g_playingTrack >= g_runStart && g_playingTrack < g_runEnd) {   /* song ended: next in the run */
        int next = g_playingTrack + 1;
        mlog("  run %d..%d: track %d ended -> %d (t=%lu)", g_runStart, g_runEnd, g_playingTrack, next, (unsigned long)GetTickCount());
        return play_track(next) == 0;
    }
    return 0;
}

/* I76_MUSIC_GAPLESS: the exe's music watchdog calls this instead of GetTickCount (call site 0x42340d only; see the
 * option block above). It runs on the game thread, the thread that opened the mp3 alias, and only while the exe has
 * music marked playing. */
static DWORD WINAPI gapless_tick(void) {
    static DWORD next; static int busy;
    DWORD t = GetTickCount();
    if (g_gapless && !busy && g_open && !g_paused && g_playingTrack && g_playingTrack >= g_runStart
        && g_playingTrack < g_runEnd && (LONG)(t - next) >= 0) {
        busy = 1; next = t + 500;
        playing_now();                 /* "playing" -> nothing; ended -> the next song of the run, logged */
        busy = 0;
    }
    return t;
}
static void *g_gapless_ptr = (void *)gapless_tick;
static int patch_bytes(DWORD_PTR va, const BYTE *expect, const BYTE *want, SIZE_T n, const char *what);
static void apply_music_gapless(void) {
    static const BYTE old_call[6] = { 0xFF, 0x15, 0x00, 0xC1, 0x4B, 0x00 };   /* call [0x4bc100] GetTickCount */
    static int done;
    BYTE new_call[6] = { 0xFF, 0x15, 0, 0, 0, 0 };
    DWORD a = (DWORD)(DWORD_PTR)&g_gapless_ptr;
    if (done) return;
    done = 1;
    memcpy(new_call + 2, &a, 4);
    if (!NA(0x0042340d) || IsBadReadPtr((void *)(DWORD_PTR)NA(0x0042340d), 6) || !patch_bytes(0x0042340d, old_call, new_call, 6, "music watchdog GetTickCount call")
        || memcmp((void *)(DWORD_PTR)NA(0x0042340d), new_call, 6) != 0) {
        g_gapless = 0;
        mlog("  music gapless: NOT applied (0x42340d is not the AiO / Galaxy watchdog call) - songs change at the exe's poll");
        return;
    }
    mlog("  music gapless: watchdog call 0x42340d -> gapless_tick (read back ok); a run's next song starts within ~0.5 s");
}

/* Encode milliseconds in whatever time format the game selected via MCI_SET. */
static DWORD fmt_time(DWORD ms, int trk) {
    DWORD m = ms / 60000, s = (ms / 1000) % 60, f = (ms % 1000) * 75 / 1000;
    if (g_timeFormat == MCI_FORMAT_MILLISECONDS) return ms;
    if (g_timeFormat == MCI_FORMAT_TMSF)
        return MCI_MAKE_TMSF(trk ? trk : FIRST_TRACK, m, s, f);
    return MCI_MAKE_MSF(m, s, f);
}

static void mci_str(const char *cmd) {
    ensure_real();
    MCIERROR e = real_mciSendStringA ? mci_call(cmd, NULL, 0) : 1;
    /* Two calls, not one conditional format string. The single-format version
     *     mlog(e ? "str FAIL(%lu): %s" : "str ok: %s", (unsigned long)e, cmd);
     * passes `e` as the FIRST vararg, so on the success path - whose format has
     * only %s - that %s consumed `e` (zero) and every successful command logged
     * as "str ok: (null)". The commands that matter most were the ones we could
     * not read. */
    if (e) mlog("  str FAIL(%lu): %s", (unsigned long)e, cmd);
    else   mlog("  str ok: %s", cmd);
}

static void stop_track(void) {
    g_truePaused = 0;                  /* a closed track is not paused */
    if (!g_open) return;
    char cmd[64]; _snprintf(cmd, sizeof(cmd), "close %s", g_alias);
    mci_str(cmd); g_open = 0;
    g_playingTrack = 0;   /* nothing on the head now - a later PLAY must restart */
}

/* Is track N actually on disk? */
static int track_exists(int trk) {
    char mp3[MAX_PATH];
    if (trk < FIRST_TRACK || trk > LAST_TRACK) return 0;
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, disc_file(trk, g_runForce));
    return GetFileAttributesA(mp3) != INVALID_FILE_ATTRIBUTES;
}

/* The nearest track that IS on disk, searching outward from the one asked for.
 *
 * WHY substitute rather than return an error: the engine picks a specific track
 * per mission, so on a partial music folder - a trimmed install, an interrupted
 * copy, somebody's own rip that starts at a different number - that mission plays
 * in silence with nothing on screen to explain it. Silence reads as "the music fix
 * is broken" when fifteen of sixteen tracks are fine. A neighbouring track keeps
 * the score running, and the log says plainly what was substituted and why.
 *
 * Returns 0 only when the music folder has nothing in it at all, which IS worth
 * reporting as an error. */
static int nearest_track(int want) {
    int d;
    if (track_exists(want)) return want;
    for (d = 1; d <= LAST_TRACK - FIRST_TRACK; d++) {
        if (track_exists(want - d)) return want - d;
        if (track_exists(want + d)) return want + d;
    }
    return 0;
}

/* CD-audio track N -> music\N.mp3 (track 1 was the data track; there is no 1.mp3) */
/* Is our mpegvideo device actually still playing? Asked rather than assumed:
 * "we started it once" is not "it is still going", and a track that has run to
 * its end must be allowed to start again. */
static int still_playing(void) {
    char ret[64];
    if (!g_open || !real_mciSendStringA) return 0;
    ret[0] = 0;
    if (mci_call("status i76cd mode", ret, sizeof(ret)) != 0) return 0;
    return strncmp(ret, "playing", 7) == 0;
}

static MCIERROR play_track(int track) {
    char mp3[MAX_PATH], cmd[MAX_PATH + 64];
    int actual;

    /* TRACK 1 IS THE DATA TRACK. On the original mixed-mode disc it held the
     * game, not audio, so playing it produced SILENCE. The engine really does ask
     * for it - ten times in one session in the field log - and nearest_track() was
     * helpfully substituting track 2, so music played in the places the original
     * was quiet. That is a large part of "it plays the wrong song". Answer success
     * and play nothing, which is what the disc did. */
    if (track < FIRST_TRACK) {
        mlog("  track %d is the DATA track - silence, as the original disc gave", track);
        stop_track();
        g_playingTrack = 0;
        return 0;
    }

    /* ALREADY PLAYING THIS TRACK -> DO NOTHING.
     *
     * The engine re-issues MCI_PLAY for the SAME track constantly. Measured in the
     * field log: track 7 asked for 116 times, track 2 105 times, track 13 80 -
     * each one previously a fresh open+play that restarted the song from zero.
     * That is why music restarted whenever the window lost and regained focus, and
     * why a track could never play through to its end. A CD player asked for the
     * track already under the head does not lift the needle. */
    if (track == g_runStart && g_playingTrack > g_runStart && g_playingTrack <= g_runEnd && g_playingForce == g_runForce
        && still_playing()) {
        mlog("  PLAY track %d re-issued while its run is on track %d - kept", track, g_playingTrack);
        return 0;
    }
    if (track == g_playingTrack && g_playingForce == g_runForce && still_playing()) {
        mlog("  track %d already playing - not restarting", track);
        return 0;
    }

    actual = nearest_track(track);
    if (!actual) {
        mlog("  track %d and every other track MISSING under %s\\music - no music",
             track, g_dir);
        return MCIERR_FILE_NOT_FOUND;
    }
    if (actual != track)
        mlog("  track %d not on disk - substituting nearest available (%d)", track, actual);
    track = actual;
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, disc_file(track, g_runForce));
    if (disc_file(track, g_runForce) != track)
        mlog("  disc track %d -> file %d.mp3 (%s)", track, disc_file(track, g_runForce), g_runForce ? "shell 1997" : "disc order");
    stop_track();
    _snprintf(cmd, sizeof(cmd), "open \"%s\" type mpegvideo alias %s", mp3, g_alias); mci_str(cmd);
    g_open = 1;
    _snprintf(cmd, sizeof(cmd), "setaudio %s volume to %lu", g_alias, (unsigned long)g_volume); mci_str(cmd);   /* the exe sets the
                                                                   slider once (0x423d50), not per track: re-apply it (M2) */
    _snprintf(cmd, sizeof(cmd), "play %s", g_alias); mci_str(cmd);
    g_playingTrack = track; g_playingForce = g_runForce;
    mlog("  PLAY track %d (t=%lu)", track, (unsigned long)GetTickCount());
    return 0;
}

/* Does this MCI_OPEN want the CD-audio device?
 *
 * THE BUG THAT MADE THIS WHOLE FIX INERT (found 2026-08-04): this used to return 0
 * whenever MCI_OPEN_TYPE_ID was set - and that is the ONLY form i76.exe ever uses.
 * Logging every call showed the game opening five times with
 *
 *     msg 0x803 (MCI_OPEN)  flags 0x3000 = MCI_OPEN_TYPE | MCI_OPEN_TYPE_ID
 *
 * so the hook refused the exact call it exists to catch, passed it to the real
 * winmm, and got 266 back. The hook was installed, the IAT patch was correct, and
 * it declined the request - which looked identical to "the game never asked".
 *
 * With MCI_OPEN_TYPE_ID, lpstrDeviceType is NOT a string: the field holds an
 * integer device-type id (MCI_DEVTYPE_CD_AUDIO). String-comparing it can never
 * match, and dereferencing it as a pointer would be a wild read - which is
 * presumably why the original bailed rather than risk it. The correct handling is
 * to compare the low word as a number.
 */
static int wants_cdaudio(DWORD_PTR flags, MCI_OPEN_PARMSA *p) {
    if (!(flags & MCI_OPEN_TYPE) || !p) return 0;
    if (flags & MCI_OPEN_TYPE_ID)
        return LOWORD((DWORD_PTR)p->lpstrDeviceType) == MCI_DEVTYPE_CD_AUDIO;
    return p->lpstrDeviceType && lstrcmpiA(p->lpstrDeviceType, "cdaudio") == 0;
}

static MCIERROR WINAPI hook_mciSendCommandA(MCIDEVICEID id, UINT msg, DWORD_PTR flags, DWORD_PTR param) {
    ensure_real();
    wmr_before_real("mciSendCommandA");
    /* Log EVERY call, including ones we pass straight through. Two rounds were lost
     * to logs that recorded only cdaudio traffic: "no lines" then means either "the
     * game never called this" or "it called about something else", and those need
     * different fixes. Now the absence of a line is real evidence. */
    if (wmr_trace_on()) mlog("mciSendCommandA(id=%u msg=0x%X flags=0x%lX) tid %lu t=%lu", (unsigned)id, msg, (unsigned long)flags, GetCurrentThreadId(), GetTickCount());
    else mlog("mciSendCommandA(id=%u msg=0x%X flags=0x%lX)", (unsigned)id, msg, (unsigned long)flags);
    if (msg == MCI_OPEN) {
        MCI_OPEN_PARMSA *p = (MCI_OPEN_PARMSA *)param;
        if (wants_cdaudio(flags, p)) { p->wDeviceID = FAKE_CD_ID; mlog("MCI_OPEN cdaudio -> virtual"); return 0; }
        return real_mciSendCommandA ? real_mciSendCommandA(id, msg, flags, param) : MCIERR_DEVICE_OPEN;
    }
    if (id != FAKE_CD_ID)
        return real_mciSendCommandA ? real_mciSendCommandA(id, msg, flags, param) : MCIERR_INVALID_DEVICE_ID;

    switch (msg) {
    case MCI_SET: {
        /* Record the format instead of just accepting it: every LENGTH and POSITION
         * answer has to be encoded in whatever the game selected, and MSF vs TMSF vs
         * milliseconds are not interchangeable. */
        MCI_SET_PARMS *sp = (MCI_SET_PARMS *)param;
        if (sp && (flags & MCI_SET_TIME_FORMAT)) {
            g_timeFormat = sp->dwTimeFormat;
            mlog("  MCI_SET time format -> %lu", (unsigned long)g_timeFormat);
        }
        return 0;
    }
    case MCI_PLAY: {
        MCI_PLAY_PARMS *p = (MCI_PLAY_PARMS *)param;
        int track = 1;
        if (p && (flags & MCI_FROM)) {
            DWORD from = (DWORD)p->dwFrom;          /* TMSF: track in the low byte */
            track = (from & 0xFF) ? (int)(from & 0xFF) : (int)from;
        }
        int force = 0;
        music_opts();
        {
            int to = track;
            if (p && (flags & MCI_TO)) {
                DWORD t = (DWORD)p->dwTo; int tt = (t & 0xFF) ? (int)(t & 0xFF) : (int)t;
                /* I76_MUSIC_TRUE_PAUSE: an end at or before the start is refused, as a CD drive refuses it. The exe sends
                 * one only from its pause toggle reading "stopped" (Esc in the gap after a run ends, before its poll):
                 * from = TOC[-1] (the track count, 17) to = the start of 15. Played, it put 17.mp3 under the menu. */
                if (g_truePause && !g_toIncl && tt <= track) {
                    mlog("MCI_PLAY flags=0x%lX from=%ld to=%ld: end before start - refused (out of range), nothing changed",
                         (unsigned long)flags, (long)p->dwFrom, (long)p->dwTo);
                    return MCIERR_OUTOFRANGE;
                }
                to = g_toIncl ? tt : (tt > track ? tt - 1 : track);   /* MCI_TO = end position: stops BEFORE track tt */
            } else if (g_exe == EXE_NITRO && p && (flags & MCI_FROM)) {
                /* Nitro's CD player (0x41cae0) sends MCI_FROM alone (flags 0x4): on a CD that plays to the end of the disc.
                 * Gold always sends FROM|TO (0xC), so its path is unchanged. */
                to = LAST_TRACK;
            }
            if (to < track) to = track;
            if (to > LAST_TRACK) to = LAST_TRACK;
            mlog("MCI_PLAY flags=0x%lX from=%ld to=%ld -> run %d..%d%s (t=%lu)",
                 (unsigned long)flags, p ? (long)p->dwFrom : -1, p ? (long)p->dwTo : -1, track, to,
                 g_toIncl ? " (to inclusive)" : "", (unsigned long)GetTickCount());
            if (g_shell1997 && (track == 13 || track == 8)) {
                DWORD st = game_state();
                if (st == 6) {
                    int nt = (track == 13) ? 15 : 16;
                    mlog("  shell 1997: state 6, run %d..%d -> disc %d alone (file %d.mp3)", track, to, nt, disc_file(nt, 1));
                    track = to = nt; force = 1;
                } else mlog("  shell 1997: track %d asked in state %lu (not the shell) - unchanged", track, (unsigned long)st);
            }
            if (g_missions1997 && track == 7 && game_state() != 6 && NA(0x005049f0) && !IsBadReadPtr((void *)(DWORD_PTR)NA(0x005049f0), 4)) {
                const char *mn = (const char *)(DWORD_PTR)NA(0x005049f0);   /* the mission basename WinMain copies in (0x403419) */
                if ((mn[0] == 't' || mn[0] == 'T') && mn[1] == '1' && mn[2] == '6' && (mn[3] == 0 || mn[3] == '.')) {
                    mlog("  missions 1997: t16 run %d..%d -> 14 alone (1997 CD T16.MSN WRLD 14)", track, to);
                    track = to = 14;
                }
            }
            g_runStart = track; g_runEnd = to;
        }
        g_curTrack = track;
        if (g_paused) {
            g_paused = 0; g_truePaused = 0;
            if (track == g_pausedRunStart && force == g_pausedForce && g_open && g_playingTrack) {
                char cmd[64];
                _snprintf(cmd, sizeof(cmd), "resume %s", g_alias); mci_str(cmd);
                g_runStart = g_pausedRunStart; g_runEnd = g_pausedRunEnd; g_runForce = force;
                mlog("  PLAY run %d..%d after a stop: track %d RESUMED where it was", g_runStart, g_runEnd, g_playingTrack);
                return 0;
            }
            mlog("  PLAY of a different run (%d, paused run was %d): the paused track is closed", track, g_pausedRunStart);
            stop_track();
        }
        g_runForce = force;
        return play_track(track);
    }
#ifndef MCI_RESUME
#define MCI_RESUME 0x0855
#endif
    case MCI_RESUME:                                    /* the exe's unpause when the status read "paused" */
        if (g_truePaused && g_open && g_playingTrack) {
            char cmd[64];
            _snprintf(cmd, sizeof(cmd), "resume %s", g_alias); mci_str(cmd);
            g_paused = 0; g_truePaused = 0;
            g_runStart = g_pausedRunStart; g_runEnd = g_pausedRunEnd; g_runForce = g_pausedForce;
            mlog("  MCI_RESUME: track %d continues (run %d..%d)", g_playingTrack, g_runStart, g_runEnd);
        } else mlog("  MCI_RESUME with nothing truly paused - ignored");
        return 0;
    case MCI_STOP: case MCI_PAUSE: case MCI_CLOSE:
        music_opts();
        if (msg == MCI_PAUSE && g_truePause && g_open && g_playingTrack) {
            char cmd[64];
            if (!g_paused) { g_pausedRunStart = g_runStart; g_pausedRunEnd = g_runEnd; g_pausedForce = g_runForce; }
            _snprintf(cmd, sizeof(cmd), "pause %s", g_alias); mci_str(cmd);
            g_paused = 1; g_truePaused = 1;
            mlog("  MCI_PAUSE: track %d paused, status reads paused until MCI_RESUME (run %d..%d)",
                 g_playingTrack, g_pausedRunStart, g_pausedRunEnd);
            g_runStart = g_runEnd = 0;
            return 0;
        }
        g_truePaused = 0;                               /* a STOP / CLOSE ends a true pause: status reads stopped */
        if (resume_on() && g_open && g_playingTrack) {
            char cmd[64];
            if (!g_paused) { g_pausedRunStart = g_runStart; g_pausedRunEnd = g_runEnd; g_pausedForce = g_runForce; }
            _snprintf(cmd, sizeof(cmd), "pause %s", g_alias); mci_str(cmd);
            g_paused = 1;
            mlog("  %s: track %d paused where it is (run %d..%d kept for a resume)",
                 msg == MCI_STOP ? "MCI_STOP" : msg == MCI_PAUSE ? "MCI_PAUSE" : "MCI_CLOSE",
                 g_playingTrack, g_pausedRunStart, g_pausedRunEnd);
            g_runStart = g_runEnd = 0;                  /* paused: playing_now() must not advance the run */
            return 0;
        }
        g_runStart = g_runEnd = 0; stop_track(); return 0;
    /* MCI_STATUS - and the per-track answers matter as much as the open.
     *
     * This used to answer `default: dwReturn = 0`, and the log showed the game
     * asking EIGHTEEN per-track questions (flags 0x110 = MCI_STATUS_ITEM|MCI_TRACK)
     * and then never issuing MCI_PLAY. Of course: told every track is type 0 (not
     * audio) and length 0 (empty), a CD player has nothing to play. Answering
     * MCI_OPEN is necessary but nowhere near sufficient - the engine validates the
     * disc before it will touch it.
     *
     * Track 1 is reported as DATA and tracks 2..17 as AUDIO, which is the layout of
     * the original mixed-mode disc and exactly why GOG's files start at 2.mp3.
     */
    case MCI_STATUS: {
        MCI_STATUS_PARMS *p = (MCI_STATUS_PARMS *)param;
        if (p && (flags & MCI_STATUS_ITEM)) {
            int trk = (flags & MCI_TRACK) ? (int)p->dwTrack : 0;
            switch (p->dwItem) {
            case MCI_STATUS_MEDIA_PRESENT:    p->dwReturn = TRUE; break;
            case MCI_STATUS_MODE:             p->dwReturn = (g_truePaused && g_open) ? MCI_MODE_PAUSE
                                                          : playing_now() ? MCI_MODE_PLAY : MCI_MODE_STOP; break;
            case MCI_STATUS_NUMBER_OF_TRACKS: p->dwReturn = LAST_TRACK; break;
            case MCI_STATUS_READY:            p->dwReturn = TRUE; break;
            case MCI_STATUS_TIME_FORMAT:      p->dwReturn = g_timeFormat; break;
            case MCI_STATUS_CURRENT_TRACK:    p->dwReturn = g_curTrack ? g_curTrack : FIRST_TRACK; break;
            case MCI_STATUS_LENGTH:
                p->dwReturn = fmt_time(trk ? track_len_ms(trk) : disc_len_ms(), trk);
                break;
            case MCI_STATUS_POSITION:
                /* WITH a track: where that track starts (a TOC query). WITHOUT:
                 * where playback currently is. Two different questions sharing one
                 * item code, and conflating them cost a round here. */
                p->dwReturn = trk ? fmt_time(track_start_ms(trk), trk)
                                  : fmt_time(position_ms(), g_curTrack);
                break;
            /* A CD player asks whether each track is audio or data. Answering 0 -
             * which is neither - is what stopped playback. */
            case MCI_CDA_STATUS_TYPE_TRACK:
                p->dwReturn = (trk <= 1) ? MCI_CDA_TRACK_OTHER : MCI_CDA_TRACK_AUDIO;
                break;
            default:                          p->dwReturn = 0; break;
            }
            mlog("  status item=0x%lX track=%d -> %lu",
                 (unsigned long)p->dwItem, trk, (unsigned long)p->dwReturn);
        }
        return 0;
    }
    default: return 0;   /* a fake device shouldn't error the game */
    }
}

/* Rewrite module's IAT slot for dll!func -> newfn. Returns the old pointer. */
static int patch_iat_has_dll(HMODULE mod, const char *dll) {
    BYTE *base = (BYTE *)mod;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *d;
    if (!dd.VirtualAddress) return 0;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress); d->Name; d++)
        if (lstrcmpiA((char *)(base + d->Name), dll) == 0) return 1;
    return 0;
}
static void *patch_iat(HMODULE mod, const char *dll, const char *func, void *newfn) {
    BYTE *base = (BYTE *)mod;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dd.VirtualAddress) return NULL;
    IMAGE_IMPORT_DESCRIPTOR *d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress);
    for (; d->Name; d++) {
        if (lstrcmpiA((char *)(base + d->Name), dll) != 0) continue;
        DWORD ntRVA = d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk;
        IMAGE_THUNK_DATA *oft = (IMAGE_THUNK_DATA *)(base + ntRVA);
        IMAGE_THUNK_DATA *ft  = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (; oft->u1.AddressOfData; oft++, ft++) {
            if (oft->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            IMAGE_IMPORT_BY_NAME *ibn = (IMAGE_IMPORT_BY_NAME *)(base + oft->u1.AddressOfData);
            if (lstrcmpA((char *)ibn->Name, func) != 0) continue;
            DWORD old; void *prev = (void *)ft->u1.Function;
            if (VirtualProtect(&ft->u1.Function, sizeof(void *), PAGE_READWRITE, &old)) {
                ft->u1.Function = (DWORD_PTR)newfn;
                VirtualProtect(&ft->u1.Function, sizeof(void *), old, &old);
                return prev;
            }
        }
    }
    return NULL;
}

/* I76_MUSIC_GUARD (default on; =0 off). The music hooks are i76.exe IAT slots set in DllMain. A layer that hooks the
 * same imports later - DxWnd does, for its own virtual CD, on the Mac's daily path - silently takes them back, and
 * the proxy then never sees a CD command (measured 2026-10-03/04: no MCI line in mciproxy.log under DxWnd, and its
 * aux hook reporting DxWnd's 2 fake drives as "real"). Every 500 ms, put any slot that is not ours back, once
 * logged with the module that held it. With DxWnd's own virtual CD switched off (profile flagm0 bit 0) the proxy is
 * then the only CD player. Costs one pointer compare per slot per tick. */
static void **iat_slot(HMODULE mod, const char *dll, const char *func) {
    BYTE *base = (BYTE *)mod;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *d;
    if (!dd.VirtualAddress) return NULL;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress); d->Name; d++) {
        IMAGE_THUNK_DATA *oft, *ft;
        if (lstrcmpiA((char *)(base + d->Name), dll) != 0) continue;
        oft = (IMAGE_THUNK_DATA *)(base + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        ft  = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (; oft->u1.AddressOfData; oft++, ft++) {
            if (oft->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            if (lstrcmpA((char *)((IMAGE_IMPORT_BY_NAME *)(base + oft->u1.AddressOfData))->Name, func) == 0)
                return (void **)&ft->u1.Function;
        }
    }
    return NULL;
}
#include "winmmrace.c"   /* winmmbase 26100.9549 start-up crash: trace + guard (2026-10-24) */
static DWORD WINAPI music_guard(LPVOID arg) {
    static const struct { const char *name; void *hook; } h[] = {
        { "mciSendCommandA", (void *)hook_mciSendCommandA }, { "auxGetNumDevs", (void *)hook_auxGetNumDevs },
        { "auxGetDevCapsA",  (void *)hook_auxGetDevCapsA },  { "auxSetVolume",  (void *)hook_auxSetVolume } };
    HMODULE exe = GetModuleHandleA(NULL);
    int logged[4] = { 0, 0, 0, 0 }, i;
    (void)arg;
    for (;;) {
        Sleep(500);
        for (i = 0; i < 4; i++) {
            void **slot = iat_slot(exe, g_exe == EXE_NITRO ? "WIN32.dll" : "WINMM.dll", h[i].name);   /* Nitro: GOG's winmm stand-in */
            if (!slot || *slot == h[i].hook) continue;
            if (logged[i] < 3) {                                 /* who took it */
                HMODULE m = NULL; char who[MAX_PATH] = "?", *b = who, *q;
                if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                       (LPCSTR)*slot, &m) && m) GetModuleFileNameA(m, who, sizeof(who));
                for (q = who; *q; q++) if (*q == '\\' || *q == '/') b = q + 1;
                mlog("  music-guard: WINMM!%s slot held by %s (%p) - re-claimed", h[i].name, b, *slot);
                logged[i]++;
            }
            patch_iat(exe, g_exe == EXE_NITRO ? "WIN32.dll" : "WINMM.dll", h[i].name, h[i].hook);
        }
    }
}
/* ===========================================================================
 * FORWARDING THE FIVE Strlkup EXPORTS WITHOUT LINKER FORWARDERS
 * ===========================================================================
 * The original build used .def forwarders (`StrLookupCreate =
 * strlkup_orig.StrLookupCreate`), which gcc/dlltool emits correctly. MSVC's
 * link.exe does not: from either the .def or /EXPORT:name=strlkup_orig.name it
 * reports all five as unresolved externals, wanting the symbols to exist locally
 * instead of treating a dotted target as a forward. Since w64devkit is not
 * installed here, forward by hand instead.
 *
 * THE FOUR FUNCTIONS: __declspec(naked) stubs that JMP to the real address. On
 * x86 a plain jmp leaves the stack frame exactly as the caller built it - return
 * address, arguments, everything - so the real function sees precisely what it
 * would have seen, and returns straight to the game. That works for ANY calling
 * convention and ANY argument list, which matters because these signatures are
 * not documented anywhere we have.
 *
 * THE DATA EXPORT is different and cannot be jmp'd to. i76.exe imports
 * StrLookup_Global_Object as DATA, so the loader binds its IAT slot to the ADDRESS
 * of a variable, and thereafter reads through that address.
 *
 * Mirroring the value into our own exported variable does NOT work: measured, the
 * original's StrLookup_Global_Object is NULL when strlkup_orig.dll loads (it is
 * filled in later, presumably by StrLookupCreate), so a DllMain-time copy hands the
 * game a permanent NULL. And the jmp stubs give no post-call hook to re-sync from.
 *
 * So instead we REPOINT THE GAME'S IAT SLOT at the original's variable - the same
 * patch_iat used for the winmm hooks. Our exported variable exists only to satisfy
 * the loader during binding; immediately afterwards the game is reading the real
 * one, which is exactly what a linker forwarder would have achieved, with no copy
 * and nothing to go stale.
 */
static HMODULE g_orig;
static FARPROC p_Create, p_Destroy, p_Find, p_Format;
static void  **p_GlobalObj;

/* Exported DATA slot: must exist before the loader binds the game's import. */
__declspec(dllexport) void *StrLookup_Global_Object = NULL;

/* Repoint the game's DATA import at the original's variable. Returns the slot's
 * previous value (our own variable's address) so it can be logged. */
static void *redirect_global_import(HMODULE exe) {
    BYTE *base = (BYTE *)exe;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *d;
    if (!p_GlobalObj || !dd.VirtualAddress) return NULL;
    d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress);
    for (; d->Name; d++) {
        IMAGE_THUNK_DATA *oft, *ft;
        if (lstrcmpiA((char *)(base + d->Name), "Strlkup.dll") != 0) continue;
        oft = (IMAGE_THUNK_DATA *)(base + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        ft  = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (; oft->u1.AddressOfData; oft++, ft++) {
            IMAGE_IMPORT_BY_NAME *ibn;
            if (oft->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            ibn = (IMAGE_IMPORT_BY_NAME *)(base + oft->u1.AddressOfData);
            if (lstrcmpA((char *)ibn->Name, "StrLookup_Global_Object") != 0) continue;
            {
                DWORD old; void *prev = (void *)ft->u1.Function;
                if (VirtualProtect(&ft->u1.Function, sizeof(void *), PAGE_READWRITE, &old)) {
                    ft->u1.Function = (DWORD_PTR)p_GlobalObj;
                    VirtualProtect(&ft->u1.Function, sizeof(void *), old, &old);
                    return prev;
                }
            }
        }
    }
    return NULL;
}

static void load_orig(void) {
    char path[MAX_PATH];
    if (g_orig) return;
    /* By FULL PATH beside this DLL. Loading "strlkup_orig.dll" by bare name would
     * search the app directory first, which is fine here, but being explicit costs
     * nothing and cannot be surprised by a working-directory change. */
    _snprintf(path, sizeof(path), "%s\\strlkup_orig.dll", g_dir);
    g_orig = LoadLibraryA(path);
    if (!g_orig) {
        char msg[MAX_PATH + 160];
        _snprintf(msg, sizeof(msg),
                  "Strlkup proxy could not load:\n%s\n\n"
                  "Restore the original by copying strlkup_orig.dll over Strlkup.dll.", path);
        MessageBoxA(NULL, msg, "I76 music fix", MB_OK | MB_ICONERROR);
        return;
    }
    p_Create    = GetProcAddress(g_orig, "StrLookupCreate");
    p_Destroy   = GetProcAddress(g_orig, "StrLookupDestroy");
    p_Find      = GetProcAddress(g_orig, "StrLookupFind");
    p_Format    = GetProcAddress(g_orig, "StrLookupFormat");
    p_GlobalObj = (void **)GetProcAddress(g_orig, "StrLookup_Global_Object");
    mlog("  strlkup_orig: Create=%p Destroy=%p Find=%p Format=%p GlobalObj=%p val=%p",
         p_Create, p_Destroy, p_Find, p_Format, (void *)p_GlobalObj, StrLookup_Global_Object);
}

/* Bare jmp - no prologue, no epilogue, no stack touched. */
#define FWD(name, slot)                                                  \
    __declspec(dllexport) __declspec(naked) void name(void) {             \
        __asm { jmp dword ptr [slot] }                                    \
    }
FWD(StrLookupCreate,  p_Create)
FWD(StrLookupDestroy, p_Destroy)
FWD(StrLookupFind,    p_Find)
FWD(StrLookupFormat,  p_Format)
#undef FWD

/* ===========================================================================
 * LAUNCH STRAIGHT INTO A MISSION   (I76_MISSION=t01)
 * ===========================================================================
 * Set I76_MISSION to a mission basename and the game boots directly into it,
 * skipping the menus entirely. Missions live in miss8\ and miss16\ as
 * <letter><NN>.MSN - m01..m15 campaign, t01..t17, s01..s07, a01.
 *
 * HOW IT WORKS. i76.exe already HAS a "mission named on the command line" path:
 * a global buffer at 0x5049f0 holds a mission basename, and at 0x4033fd
 *
 *     cmp dword ptr [esp+0x1c], ebx     ; was a name supplied?
 *     jne 0x403476                      ; yes -> SKIP the menu's own name copy
 *
 * The flag is set at 0x402d6f purely from `[0x5049f0] != 0`. So filling that
 * buffer is enough - no new code paths, we use the engine's own.
 *
 * WHAT DOES NOT WORK, tested rather than assumed: passing the name on the actual
 * command line. The parser at 0x49d1d0 tokenises on " ," and dispatches only on
 * '/' and '-'; a bare argument falls to the loop tail and is DISCARDED. Probing
 * 0x5049f0 after launching with `-glide t01`, `-glide -mission t01` and
 * `-glide /t01` gives an empty buffer every time. The plumbing exists; nothing
 * fills it. So we fill it.
 *
 * TWO instructions would otherwise wipe what we write, both before the flag is
 * read, so both are NOPed:
 *     0x402d33  88 0D F0 49 50 00   mov byte ptr [0x5049f0], cl  (pre-parse)
 *     0x49d1e0  C6 00 00            mov byte ptr [eax], 0        (in the parser)
 *
 * DllMain runs before the exe's entry point, so writing here lands before any of
 * this executes.
 *
 * Every patch VERIFIES the existing bytes first and refuses if they differ - a
 * different build of i76.exe would otherwise be silently corrupted at addresses
 * that mean something else entirely.
 */
static int patch_bytes(DWORD_PTR va, const BYTE *expect, const BYTE *want, SIZE_T n, const char *what) {
    DWORD old;
    BYTE *p = (BYTE *)va;
    if (g_exe == EXE_NITRO) return nitro_patch_bytes((DWORD)va, expect, want, n, what);   /* va is a Gold address (nitro.c) */
    if (memcmp(p, expect, n) != 0) {
        mlog("  patch: %s at 0x%08lX has UNEXPECTED bytes - not patching", what, (unsigned long)va);
        return 0;
    }
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memcpy(p, want, n);
    VirtualProtect(p, n, old, &old);
    return 1;
}

static void apply_mission_launch(void) {
    char mission[32];
    DWORD n = env_str("I76_MISSION", mission, sizeof(mission));
    static const BYTE clr1_old[6] = { 0x88, 0x0D, 0xF0, 0x49, 0x50, 0x00 };
    static const BYTE clr1_nop[6] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    static const BYTE clr2_old[3] = { 0xC6, 0x00, 0x00 };
    static const BYTE clr2_nop[3] = { 0x90, 0x90, 0x90 };
    int ok1, ok2;
    if (n == 0) return;                               /* not requested */

    ok1 = patch_bytes(0x00402d33, clr1_old, clr1_nop, 6, "pre-parse clear");
    ok2 = patch_bytes(0x0049d1e0, clr2_old, clr2_nop, 3, "parser clear");
    if (!ok1 || !ok2) {
        mlog("  mission-launch ABORTED (%d/%d patches applied) - booting to the menu", ok1 + ok2, 2);
        return;
    }
    lstrcpynA((char *)(DWORD_PTR)NA(0x005049f0), mission, 16);
    /* 2026-09-27: the name alone no longer skips the menus (six boots across both exe builds, three shell DLLs and
     * the Aug 8 proxy binary all sat in the shell with the buffer intact). WinMain runs the shell unless the dword
     * at 0x504c10 is nonzero (cmp at 0x403197, jne 0x403201 past the shell_RunAndGetChoice call at 0x4031f5); the
     * mission-name path at 0x402d82 leaves that dword alone, and nothing in the exe sets it, so set it here. */
    *(volatile DWORD *)(DWORD_PTR)NA(0x00504c10) = 1;

    /* OPTIONALLY SKIP THE INTRO MOVIES  (I76_SKIP_MOVIES=1).
     *
     * The intro (introf01.smk) and credits (credf01.smk) play before the mission
     * parser is ever reached, so an automated test spends a minute or two watching
     * them. Skipping is a convenience for testing, NOT part of booting into a
     * mission - the game gets there on its own, just slowly.
     *
     * HOW, and the first attempt was wrong. The engine skips a movie whose open
     * FAILS:
     *     0x403056  test eax,eax
     *     0x403058  je 0x4030e0      ; open failed -> skip to credits
     * and I first made that jump unconditional (0F 84 -> 90 E9). That jumps away
     * AFTER a SUCCESSFUL open, leaving the movie subsystem half-initialised and the
     * handle never closed - the game then hung on the loading screen, reported from
     * the field as "stuck on please stand by, no menu, no movie, no game".
     *
     * So instead make the OPEN fail, which is the path the engine already handles:
     * corrupt the first character of each filename so the file cannot be found.
     * Same effect, entirely inside behaviour the engine was written to expect.
     */
    if (env_present("I76_SKIP_MOVIES")) {
        static const BYTE intro_old[1] = { 'i' };   /* 'introf01.smk' @ 0x4c25b0 */
        static const BYTE intro_new[1] = { 'X' };
        static const BYTE cred_old[1]  = { 'c' };   /* 'credf01.smk'  @ 0x4c25a4 */
        static const BYTE cred_new[1]  = { 'X' };
        int m1 = patch_bytes(0x004c25b0, intro_old, intro_new, 1, "intro movie name");
        int m2 = patch_bytes(0x004c25a4, cred_old,  cred_new,  1, "credits movie name");
        mlog("  mission-launch: movie names invalidated %d/2 (open will fail -> engine skips)", m1 + m2);
    }
    mlog("  mission-launch: booting directly into '%s'", mission);
}

/* ===========================================================================
 * HIGH-RESOLUTION SIM CLOCK  (I76_HIRES_CLOCK=1; off by default)
 * ===========================================================================
 * The whole sim is dt-driven: simclock_Update 0x49c920 runs once per frame and
 * every physics substep, AI timer and camera rate derives from its dt (map:
 * i76-map subsystems\damage.md neighbours, batch simclock-stepper). It computes
 *
 *     t = (float)(GetTickCount() * 0.001);   dt = t - last;   last = t;
 *
 * which has two defects, both measured/derived 2026-09-26:
 *   1. GetTickCount steps in 15-16 ms on stock Windows, and timeBeginPeriod
 *      does not change that (measured). At 20 fps dt reads 47 or 63 ms (the
 *      jitter the FFB dt at 0x4f2488 always showed); at 60 fps most frames read
 *      0 (clamped to 1 ms) or 15.6 ms.
 *   2. t is stored as a 32-bit float of SECONDS SINCE BOOT (fstp dword at
 *      0x49c94c), so its precision decays with uptime: dt snaps to a 7.8 ms grid
 *      after 1 day, 62.5 ms after 7 days, 250 ms after 30 days - and Windows
 *      Fast Startup does not reset uptime across "shutdowns". GOG's 2019 AiO build
 *      already fixes this one by masking the tick to 23 bits (wraps every ~2.3 h);
 *      the 2017 Galaxy exe does not. Neither fixes defect 1.
 *
 * Fix: repoint only simclock's two `call dword ptr [GetTickCount]` sites
 * (simclock_Init 0x49c85f, simclock_Update 0x49c929; FF 15 00 C1 4B 00) at a
 * pointer to a clock that returns QueryPerformanceCounter milliseconds since
 * this process started: 1 ms resolution, and small enough that float32 keeps
 * sub-ms precision for ~4.6 hours of play (still 7.8 ms only after 24 hours).
 * No other GetTickCount user in the exe (CD audio, AI) is touched. Static
 * reading only - NOT yet measured in game.
 */
static LARGE_INTEGER g_qpf, g_qp0;
static DWORD WINAPI hires_clock_ms(void) {
    LARGE_INTEGER n;
    QueryPerformanceCounter(&n);
    return (DWORD)(((n.QuadPart - g_qp0.QuadPart) * 1000) / g_qpf.QuadPart);
}
static void *g_hires_clock_ptr = (void *)hires_clock_ms;

static void install_frame_hook(void);                        /* below, with the frame hook */
static int g_frame_hook, g_hires_on;
static void apply_hires_clock(void) {
    static const BYTE old_call[6] = { 0xFF, 0x15, 0x00, 0xC1, 0x4B, 0x00 };  /* call [0x4bc100] GetTickCount */
    BYTE new_call[6] = { 0xFF, 0x15, 0, 0, 0, 0 };
    DWORD a = (DWORD)(DWORD_PTR)&g_hires_clock_ptr;
    int n1, n2;
    if (!env_present("I76_HIRES_CLOCK")) return;
    if (env_present("I76_TICK_MS")) { mlog("  hires-clock: I76_TICK_MS is set - the coarse tick clock wins, hires not applied"); return; }
    if (!QueryPerformanceFrequency(&g_qpf) || g_qpf.QuadPart == 0) { mlog("  hires-clock: no QPC - not patching"); return; }
    QueryPerformanceCounter(&g_qp0);
    memcpy(new_call + 2, &a, 4);
    /* Two layouts: the 2017 Galaxy exe (md5 9a232dcc) and GOG's 2019 AiO build (60abf7bc, and the patched
     * sandbox 4fabc303 built on it), whose rewritten simclock masks the tick with `and eax, 0x7fffff` right
     * after the call - AiO's own fix for defect 2, which moves both calls 2 bytes earlier. Only a site
     * whose bytes match is written. */
    if (memcmp((void *)0x0049c85f, old_call, 6) == 0) {
        n1 = patch_bytes(0x0049c85f, old_call, new_call, 6, "simclock_Init GetTickCount call (Galaxy)");
        n2 = patch_bytes(0x0049c929, old_call, new_call, 6, "simclock_Update GetTickCount call (Galaxy)");
    } else {
        n1 = patch_bytes(0x0049c85d, old_call, new_call, 6, "simclock_Init GetTickCount call (AiO)");
        n2 = patch_bytes(0x0049c927, old_call, new_call, 6, "simclock_Update GetTickCount call (AiO)");
    }
    mlog("  hires-clock: %d/2 simclock call sites repointed to QPC ms (ptr %p)", n1 + n2, (void *)&g_hires_clock_ptr);
    if (n1 + n2 == 2) {                                      /* exact per-frame dt from the frame hook (frame_cap_then_clock) */
        install_frame_hook();
        g_hires_on = g_frame_hook;
        mlog("  hires-clock: exact frame dt %s", g_hires_on ? "on" : "NOT applied (frame hook missing)");
    }
}

/* ===========================================================================
 * COARSE TICK CLOCK  (I76_TICK_MS=<ms>, e.g. 55 or 15.625; off by default; lab tool for reference profiles)
 * ===========================================================================
 * Lab doc AI-COMBAT-PARITY-2026-10-13.md (what "stock" is). The 1997 engine's whole sim clock is GetTickCount at
 * simclock's two call sites (above), so its frame dt is quantised to whatever tick the OS gave that call: 15.625 ms on
 * this Windows 10 PC, other values on other machines and OSes. To reproduce another machine's clock on this PC both
 * sites are repointed (as I76_HIRES_CLOCK does) at a clock that returns QPC milliseconds rounded DOWN to multiples of
 * the given tick (a fractional tick is kept exactly: the n-th tick reads floor(n x tick) ms). Combine with
 * I76_FPS_CAP for the frame rate. I76_TICK_MS=15.625 is the control (it must behave like the real GetTickCount here).
 * Excludes I76_HIRES_CLOCK. Nothing else in the exe that reads GetTickCount is touched. */
static double g_tick_emu_ms;
static DWORD WINAPI tick_emu_ms(void) {
    LARGE_INTEGER n;
    double ms, k;
    QueryPerformanceCounter(&n);
    ms = (double)(n.QuadPart - g_qp0.QuadPart) * 1000.0 / (double)g_qpf.QuadPart;
    k = floor(ms / g_tick_emu_ms);
    return (DWORD)floor(k * g_tick_emu_ms) + 1000;          /* +1 s: never 0 at the first read */
}
static void *g_tick_emu_ptr = (void *)tick_emu_ms;
static void apply_tick_emu(void) {
    static const BYTE old_call[6] = { 0xFF, 0x15, 0x00, 0xC1, 0x4B, 0x00 };  /* call [0x4bc100] GetTickCount */
    BYTE new_call[6] = { 0xFF, 0x15, 0, 0, 0, 0 };
    DWORD a = (DWORD)(DWORD_PTR)&g_tick_emu_ptr;
    char v[24]; int n1, n2;
    if (!env_str("I76_TICK_MS", v, sizeof(v))) return;
    g_tick_emu_ms = atof(v);
    if (g_tick_emu_ms < 1.0 || g_tick_emu_ms > 200.0) { mlog("  tick-ms: '%s' is not 1..200 ms - off", v); return; }
    if (!QueryPerformanceFrequency(&g_qpf) || g_qpf.QuadPart == 0) { mlog("  tick-ms: no QPC - not patching"); return; }
    QueryPerformanceCounter(&g_qp0);
    memcpy(new_call + 2, &a, 4);
    if (memcmp((void *)0x0049c85f, old_call, 6) == 0) {
        n1 = patch_bytes(0x0049c85f, old_call, new_call, 6, "simclock_Init GetTickCount call (Galaxy, tick-ms)");
        n2 = patch_bytes(0x0049c929, old_call, new_call, 6, "simclock_Update GetTickCount call (Galaxy, tick-ms)");
    } else {
        n1 = patch_bytes(0x0049c85d, old_call, new_call, 6, "simclock_Init GetTickCount call (AiO, tick-ms)");
        n2 = patch_bytes(0x0049c927, old_call, new_call, 6, "simclock_Update GetTickCount call (AiO, tick-ms)");
    }
    mlog("  tick-ms: sim clock on a %.3f ms tick (%d/2 simclock GetTickCount sites repointed)", g_tick_emu_ms, n1 + n2);
}

/* ===========================================================================
 * FRAME-RATE-INDEPENDENT ENGINE RESPONSE  (I76_ENGINE_DT_FIX=1; off by default)
 * ===========================================================================
 * Vehicle physics runs in substeps: entity_TickVehicle 0x463800 splits the frame's
 * sim dt into count = min(floor(dt * 20) + 1, 20) equal steps (simclock_StepperBegin
 * 0x49cc20, rate 1/0.05 from entity_InitVehicle). But the engine/gearbox update
 * 0x46a320, called from the physics step 0x438fd0 once PER SUBSTEP, reads the WHOLE
 * frame's dt (call simclock_GetDt at 0x46a333) and uses 2*dt as the smoothing factor
 * for engine RPM (+0x1c) and its second smoothed value (+0x24), from which it writes
 * the torque term (+0x10). So the smoothing is applied `count` times per frame with
 * the full dt: at 20 fps (2 substeps) RPM/torque converge about twice as fast per
 * second as at 60 fps (1 substep), and GetTickCount jitter flips count between 1 and 2
 * even at a nominal 20 fps.
 *
 * Fix: repoint that one call at a function returning 2 * (sim_dt / count), computed
 * exactly as the stepper computes it. The factor 2 keeps the familiar 20 fps response
 * (2 substeps of 25 ms, each with factor 2*50 ms) at every frame rate: per 50 ms the
 * retained fraction is (1-0.1)^2 = 0.81 at 20 fps and (1-0.0667)^3 = 0.81 at 60 fps.
 * Static reading only - NOT yet measured in game.
 */
static float g_fixed_step;
/* I76_REF_FPS=<fps> (default 20; 2026-10-14, lab docs\W95-18-BASELINE-2026-10-14.md): the reference frame rate every
 * frame-rate fix reproduces. Stock behaviour is per frame; the fixes give each per-frame effect its per-SECOND value at
 * this rate: the per-frame constants (x dt x rate), the grid that holds per-frame rolls / decisions / hazard steps /
 * flamer ageing / smoke (1 / rate), the AI gain pins (dt = 1 / rate), the flamer dt floor, the back_away stamp, and the
 * whole-frame dt the engine update reads per substep under I76_FIXED_STEP (1 / rate). 20 = stock20 (the I76PATCH 20 fps
 * cap on Windows 10, unchanged default); 18.2 = W95-18, the box spec (Windows 95 GetTickCount 55 ms, one tick per frame at
 * the PC timer's 18.2 Hz). I76_AI_GRID_HZ defaults to this rate. */
static float g_ref_rate = 20.0f, g_ref_dt = 0.05f;
static DWORD g_stepframes, g_stepframe_last;               /* frames on which a fixed step ran (instrument) */
static DWORD vehicle_steps(BYTE *e);                         /* the vehicle's own fixed steps so far (below, with the fixed step) */
static int g_in_far;                                        /* inside physics_StepVehicleFar (I76_FAR_ENGINE_DT, below) */
static int g_engine_dt_on;
static float __cdecl engine_substep_dt(void) {
    float sim_dt, rate; int count;
    /* I76_FAR_ENGINE_DT: the far path applies the engine update once per frame, where the stock whole-frame dt is right */
    if (g_in_far) return *(volatile float *)0x004fe428;    /* simclock_dt, what simclock_GetDt returns */
    /* I76_FIXED_STEP: stock at 20 fps hands the engine the whole frame's dt (~50 ms) on every substep; keep that */
    if (g_fixed_step > 0.0f) return g_ref_dt;               /* I76_REF_FPS: 0.055 = W95-18's 55 ms frame */
    sim_dt = *(volatile float *)0x004fe420;                 /* simclock_sim_dt */
    rate = 1.0f / 0.05f;                                    /* stepper rate set by entity_InitVehicle */
    count = (int)(sim_dt * rate) + 1;                       /* truncation, as _ftol at 0x49cc2d */
    if (count > 20) count = 20;
    return 2.0f * (sim_dt / (float)count);
}

static void apply_engine_dt_fix(void) {
    static const BYTE old_call[5] = { 0xE8, 0x78, 0x25, 0x03, 0x00 };   /* call 0x49c8b0 (simclock_GetDt) at 0x46a333 */
    BYTE new_call[5] = { 0xE8, 0, 0, 0, 0 };
    LONG rel = (LONG)((DWORD_PTR)engine_substep_dt - (0x0046a333 + 5));
    if (!env_present("I76_ENGINE_DT_FIX")) return;
    memcpy(new_call + 1, &rel, 4);
    g_engine_dt_on = patch_bytes(0x0046a333, old_call, new_call, 5, "engine update simclock_GetDt call");
    mlog("  engine-dt-fix: %d/1 call site repointed (0x46a333 -> %p)", g_engine_dt_on, (void *)engine_substep_dt);
}

/* ===========================================================================
 * FAR-VEHICLE ENGINE DT  (I76_FAR_ENGINE_DT=1, needs I76_ENGINE_DT_FIX; off by default)
 * ===========================================================================
 * Far vehicles (physics.md "Far vehicles"): beyond the camera far radius + 25 m, entity_TickVehicle 0x463800 takes
 * one whole-frame kinematic step, physics_StepVehicleFar 0x43a3c0 (sole caller 0x46384e, `push edi; push esi`, result
 * unused), which calls physics_UpdateEngine 0x46a320 once per frame (0x43a548). There the stock whole-frame dt read
 * at 0x46a333 is already right (one application per frame), but I76_ENGINE_DT_FIX repoints that read at
 * engine_substep_dt: 2 x dt (no fixed step: 2x the stock far-path convergence at any rate) or 0.05 on every frame
 * (fixed step: 3x at 60 fps, 6x at 120). The far call is flagged and the engine gets the stock value inside it
 * (docs/records/FRAMERATE-COVERAGE-2026-10-02.md P4 / U4). Static reading - NOT yet measured in game.
 */
static DWORD g_idbg_far_steps;                              /* copied into the debug block by the render wrapper */
static void __cdecl far_step_wrap(DWORD obj, DWORD arg) {
    g_in_far = 1;
    ((void (__cdecl *)(DWORD, DWORD))0x0043a3c0)(obj, arg);
    g_in_far = 0;
    g_idbg_far_steps++;
}
static void apply_far_engine_dt(void) {
    static const BYTE old_call[5] = { 0xE8, 0x6D, 0x6B, 0xFD, 0xFF };   /* call 0x43a3c0 (physics_StepVehicleFar) at 0x46384e */
    BYTE new_call[5] = { 0xE8, 0, 0, 0, 0 };
    LONG rel = (LONG)((DWORD_PTR)far_step_wrap - (0x0046384e + 5));
    if (!env_present("I76_FAR_ENGINE_DT")) return;
    if (!g_engine_dt_on) { mlog("  far-engine-dt: needs I76_ENGINE_DT_FIX - not applied"); return; }
    memcpy(new_call + 1, &rel, 4);
    mlog("  far-engine-dt: %d/1 far vehicle step call repointed (0x46384e -> %p): stock whole-frame dt for the far engine update",
         patch_bytes(0x0046384e, old_call, new_call, 5, "far vehicle step call"), (void *)far_step_wrap);
}

/* ===========================================================================
 * PRECISE FRAME CAP  (I76_FPS_CAP=<frames per second>; off by default)
 * ===========================================================================
 * The engine has no limiter: WinMain's loop renders as fast as it can, and every
 * community fix caps it from outside (dgVoodoo FPSLimit, I76PATCH.DLL, i76fix's
 * Sleep before the frame clock). This one sits exactly where i76fix does - the
 * per-frame `call simclock_Update` at 0x4039b8 (E8 63 8F 09 00, the same in the
 * Galaxy and AiO builds) - and waits on the QPC clock, so the cap holds to well
 * under a millisecond instead of the 15.6 ms Sleep granularity. Added for the
 * frame-rate measurements (i76-map captures\014-framerate), useful on its own.
 */
static LARGE_INTEGER g_cap_period, g_cap_next;
static int g_cap_started;
/* per-frame rescaled constants (I76_FRAMERATE_FIXES): start at the stock values */
static float g_cloud_u = 1.0f, g_cloud_v = -1.0f, g_cam_rate = -0.017453292f, g_zoom_rate = -0.01f, g_thr_up = -0.4f, g_thr_dn = 0.5f;
static int g_ratefix;
static LARGE_INTEGER g_prev_q;
static float g_acc20;                                        /* 20 Hz grid: g_tick20 is set on frames that cross it */
static int g_tick20 = 1;
static DWORD g_tick20_n;                                     /* grid frames so far */
/* AI decision grid (I76_AI_GRID_HZ=<hz>, default 20 = the 20 Hz grid above, unchanged): the held AI decisions (fire, dodge,
 * skid / horn rolls) are made on frames that cross this grid. Lab doc AI-COMBAT-PARITY-2026-10-13.md: the 1997 game as
 * played makes one decision per FRAME, ~24 per second at the frame rate its physics step was taken from (I76_FIXED_STEP=24). */
static float g_ai_hz = 20.0f, g_accai;
static int g_tickai = 1;
static DWORD g_tickai_n;
static float g_grid_acc, g_grid_win = 0.05f;                 /* time since the last grid frame; on a grid frame, the window it closes */
static float g_turn_k = 1.0f, g_turn_g = 1.0f;               /* per-step turn scales (radar missiles): min(dt x 20, 1) and its gain form */
static int g_coll_dup;                                       /* collision pass: the contact just found repeats last frame's (below) */
static void radar_ping_flush(void);
static DWORD g_frame;                                        /* proxy frame counter, advanced by the frame hook */
static void terrain_pops_frame(void);                        /* terrainpops.c: I76_SHADE_SMOOTH table rebuild, its own 600-frame report (called from the frame hook below) */
static DWORD g_voltest_frame; static int g_voltest_level;    /* I76_VOLUME_TEST */
static int g_tel_on;                                         /* I76_TELEMETRY: publish the completed frame (below, with the telemetry export) */
static void tel_frame(void);
static int g_simtick, g_st_now = 1;                          /* I76_SIM_TICK_MS (simtick.c): whole-sim tick on; this display frame runs the sim */
static void simtick_top(void);
static void simtick_clock(void);
static int g_jc_on;                                          /* judder census (simtick.c; I76_JUDDER_CENSUS under I76_RENDER_INTERP) */
static int g_flc_on, g_flame_wrapped; static void flame_census_frame(void);    /* I76_FLAME_CENSUS (below, with the flamers) */
static void judder_census(void);
static int g_stf_on, g_stf_scrape_on;                      /* tick-factors (simtick.c): wrappers in; scrape repeats through coll_damage_wrap */
static void st_factor_frame(void);
static DWORD st_coll_damage_call(DWORD victim, DWORD source, DWORD v, DWORD n, DWORD p);
static int st_dmg_chain_take(void *stub);
static void judder_census_publish(void);
static void (*g_lat_step_fn)(void), (*g_lat_draw_fn)(void); /* lab latency probe (side build drive block): end of the sim block / draw */
static int g_rpl_on;                                         /* I76_REPLAY (replay.c, included below): frame-dt replay of an emulator trace */
static void rpl_pre(void);
static void rpl_post_clock(void);
static int g_cbt_on;                                         /* I76_COMBAT_LOG (below, after the telemetry export) */
static void cbt_frame(void);
static void cbt_shot(BYTE *inst);
static void cbt_coll(BYTE *target, BYTE *source);
static void cbt_damage(BYTE *obj, BYTE *shooter, float amt, int lost, int killed);
static i76trn_ctl_t *g_trn;                                  /* trainer control block (below, with apply_trainer) */
static void trn_frame(void);
static int g_start_on;                                       /* I76_START_POS (below, after the trainer) */
static void start_pos_frame(void);
static int g_rh_on;                                          /* I76_RETAIL_HANDLING (below, after the start position) */
static void retail_handling_frame(void);
static int g_bbox_sweep;                                     /* I76_BREAKABLE_BOX=3: sign-post sweep (below, with the breakable box) */
static volatile DWORD g_sweep_entries, g_sweep_scored, g_sweep_engine, g_sweep_frames;
static void sign_sweep(void);
static void sign_sweep_tick(void);                           /* I76_SIM_TICK_MS: the sweep once per tick, at the end of the sim block */
static void sign_pend_frame(void);                           /* ... and the queued knock-offs every display frame */
static DWORD g_st_tickno;                                    /* ticks run (simtick.c), the sweep's clock under the tick */
static int g_bbox_defer;                                     /* I76_BREAKABLE_BOX=4: post knock-offs wait for the DRAWN car (below) */
static int sign_defer_engine(BYTE *victim, BYTE *source, const float *v, const float *n, const float *p);
static void sign_gap_log_engine(BYTE *victim, BYTE *source);
static double g_pld_p[3], g_pld_prev[3]; static float g_pld_r[9]; static BYTE *g_pld_obj; static DWORD g_pld_frame;   /* the player as last DRAWN (render-interp) */
/* I76_FPS_LOG=<seconds> (off by default): every period, log the frame rate and where each frame's time went -
 * "work" is hook return to the next hook entry (sim, render, Flip / present, anything the frame blocks on), "cap"
 * is the I76_FPS_CAP wait. Work near the frame time with the process far below a full core means the frame is
 * WAITING (present, a lock, a sleep), not computing - the question that decides what to cut first. */
static LONGLONG g_fl_period, g_fl_start, g_fl_out, g_fl_work, g_fl_workmax, g_fl_cap;
static DWORD g_fl_frames;
static volatile LONG g_coop_hits_impact, g_coop_hits_flame, g_coop_remote;   /* I76_COOP_DAMAGE counters (see below) */
static void coop_ai_log(void);                                                   /* I76_COOP_AI status line (see below) */
static LONG g_coop_logged = -1;
static void fps_log_frame(LONGLONG tin, LONGLONG tcap, LONGLONG tout) {
    LONGLONG work = g_fl_out ? tin - g_fl_out : 0;
    if (!g_fl_start) g_fl_start = tin;
    g_fl_out = tout;
    g_fl_frames++; g_fl_work += work; g_fl_cap += tcap - tin;
    if (work > g_fl_workmax) g_fl_workmax = work;
    if (tout - g_fl_start >= g_fl_period) {
        double s = (double)(tout - g_fl_start) / (double)g_qpf.QuadPart, f = (double)g_fl_frames;
        double ms = 1000.0 / (double)g_qpf.QuadPart;
        mlog("  fps: %.1f (%lu frames / %.1f s); work %.2f ms avg, %.2f ms max; cap wait %.2f ms avg",
             f / s, (unsigned long)g_fl_frames, s, g_fl_work * ms / f, g_fl_workmax * ms, g_fl_cap * ms / f);
        g_fl_start = tout; g_fl_frames = 0; g_fl_work = g_fl_workmax = g_fl_cap = 0;
        if (g_coop_hits_impact + g_coop_hits_flame + g_coop_remote != g_coop_logged) {
            g_coop_logged = g_coop_hits_impact + g_coop_hits_flame + g_coop_remote;
            if (g_coop_logged) mlog("  coop-damage: %ld weapon hits and %ld flame hits scaled so far (%ld by a remote player's car)",
                                    g_coop_hits_impact, g_coop_hits_flame, g_coop_remote);
        }
        coop_ai_log();
    }
}
/* I76_FRAME_LOG=<file> (lab instrument, off by default; 2026-10-14, lab docs\W95-18-BASELINE-2026-10-14.md): one line per
 * mission frame, written where the sim clock is about to be read (after any I76_FPS_CAP wait), so the wall period is
 * what GetTickCount / the tick emulation sees:
 *   proxy frame, wall period since the previous line (ms, QPC), sim_dt and dt of the frame just completed (ms), and the
 *   local player's physics stepper (entity + 0x444, as simclock_StepperBegin 0x49cc20 left it in that frame:
 *   +4 step size in ms, +8 step count) - the engine's own substep pattern, stock or fixed-step.
 * Buffered, flushed every 32 lines (the harness kills the game). Counts and changes nothing. */
static FILE *g_frlog;
static LARGE_INTEGER g_frlog_prev;
static DWORD g_frlog_n;
/* I76_KEEP_ACTIVE=1 (lab harness, off by default; 2026-10-14): the game minimises itself on WM_ACTIVATEAPP 0 and clears
 * its active flag [0x504c1c]; the main loop then skips the mission tick (0x4039e4 -> 0x40402f) while the frame hook and
 * the sim clock keep running, so an unattended run that loses the foreground for a moment freezes every car while sim time
 * goes on (measured: T04 racers stopped mid-lap, a 120 fps run spinning at 30 kfps). This sets the flag again on every
 * frame (and applies I76_NO_MINIMIZE's push 8), and counts the frames it had to. */
static int g_keep_active, g_frlog_inact;
static DWORD g_keep_active_n;
static void frame_log_line(void) {
    LARGE_INTEGER q; double per = 0.0; float step = -1.0f; int cnt = -1, fg = 0;
    BYTE **rec, *obj, *ent;
    {   DWORD pid = 0; HWND w = GetForegroundWindow(); if (w) GetWindowThreadProcessId(w, &pid); fg = pid == GetCurrentProcessId(); }
    QueryPerformanceCounter(&q);
    if (g_frlog_prev.QuadPart) per = (double)(q.QuadPart - g_frlog_prev.QuadPart) * 1000.0 / (double)g_qpf.QuadPart;
    g_frlog_prev = q;
#ifdef _MSC_VER
    __try {
#endif
        rec = *(BYTE ***)(DWORD_PTR)NA(0x0054a264); obj = rec ? *rec : 0;
        if (obj && (*(DWORD *)(obj + 0x10) & 0x10) && (ent = *(BYTE **)(obj + 0x70)) != 0) {
            step = *(float *)(ent + EF(0x444) + 4); cnt = *(int *)(ent + EF(0x444) + 8);
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { step = -2.0f; cnt = -2; }
#endif
    fprintf(g_frlog, "%lu,%.3f,%.3f,%.3f,%.3f,%d,%d,%d\n", (unsigned long)g_frame, per, *(volatile float *)(DWORD_PTR)NA(0x004fe420) * 1000.0f,
            *(volatile float *)(DWORD_PTR)NA(0x004fe428) * 1000.0f, step * 1000.0f, cnt, fg, g_frlog_inact);
    if ((++g_frlog_n & 31) == 0) fflush(g_frlog);
}
static void __cdecl frame_cap_then_clock(void) {
    LARGE_INTEGER now, fl_in = {0}, fl_cap = {0};
    if (g_fl_period) QueryPerformanceCounter(&fl_in);
    if (g_simtick) simtick_top();                           /* I76_SIM_TICK_MS: the sim clock back to the tick's values */
    /* The frame just rendered is complete here (ticks, post-ticks, camera, render, Flip): publish it before any cap
     * wait, so the datagram leaves as soon as the frame is on screen. Under I76_SIM_TICK_MS only frames that ran a
     * tick are published (the others repeat the same sim state). */
    if (g_tel_on && (!g_simtick || g_st_now)) tel_frame();
    if (g_cbt_on) cbt_frame();
    if (!g_cap_period.QuadPart) goto clock;
    QueryPerformanceCounter(&now);
    if (!g_cap_started) {
        g_cap_started = 1; g_cap_next.QuadPart = now.QuadPart;
    } else {
        while (now.QuadPart < g_cap_next.QuadPart) {
            LONGLONG left_ms = (g_cap_next.QuadPart - now.QuadPart) * 1000 / g_qpf.QuadPart;
            Sleep(left_ms > 2 ? (DWORD)(left_ms - 2) : 0);    /* coarse sleep, then spin the last ~2 ms */
            QueryPerformanceCounter(&now);
        }
    }
    g_cap_next.QuadPart += g_cap_period.QuadPart;
    if (now.QuadPart - g_cap_next.QuadPart > g_cap_period.QuadPart) g_cap_next.QuadPart = now.QuadPart;  /* fell behind: resync */
clock:
    if (g_fl_period) QueryPerformanceCounter(&fl_cap);
    g_frlog_inact = *(volatile DWORD *)(DWORD_PTR)NA(0x00504c1c) == 0;     /* the game's active flag (WM_ACTIVATEAPP) */
    if (g_keep_active && g_frlog_inact) { *(volatile DWORD *)(DWORD_PTR)NA(0x00504c1c) = 1; g_keep_active_n++; }
    if (g_frlog) frame_log_line();
    g_frame++;
    if (g_voltest_frame && g_frame == g_voltest_frame) {    /* I76_VOLUME_TEST=<level>,<frame>: call sound_SetCdVolume on the
                                                               game's own thread, as the Options slider does (test knob) */
        mlog("  volume-test: sound_SetCdVolume(%d) at frame %lu", g_voltest_level, (unsigned long)g_frame);
        ((void (__cdecl *)(int))0x00424b60)(g_voltest_level);
    }
    if (g_rpl_on) rpl_pre();                                /* I76_REPLAY: log the frame just done; place the car at the start */
    if (g_trn) trn_frame();                                 /* trainer control block: hold / one-shots, before the tick */
    terrain_pops_frame();                                   /* terrainpops.c: I76_SHADE_SMOOTH table rebuild; the lab instruments' 600-frame report */
    if (g_start_on) start_pos_frame();                      /* I76_START_POS: one placement after the mission starts */
    if (g_rh_on) retail_handling_frame();                   /* I76_RETAIL_HANDLING: the player's car keeps the arcade bit */
    if (g_bbox_sweep) { if (g_simtick) sign_pend_frame(); else sign_sweep(); }   /* I76_BREAKABLE_BOX=3: posts the last step drove through (tick: sweep at the tick's end, simtick.c) */
    if (g_flc_on) flame_census_frame();                     /* I76_FLAME_CENSUS: stream lengths, log line */
    if (g_stf_on) st_factor_frame();                        /* tick-factors census line (I76_FACTOR_CENSUS / I76_SIM_TICK_LOG) */
    if (g_simtick) simtick_clock();                         /* I76_SIM_TICK_MS: simclock_Update on tick frames only, dt = the tick */
    else ((void (__cdecl *)(void))(DWORD_PTR)NA(0x0049c920))();           /* simclock_Update */
    if (g_hires_on && !g_simtick) {
        /* The hires clock still hands simclock whole milliseconds (it stands in for GetTickCount), so at 60 fps the
         * frame dt reads 16 or 17 ms while the display shows 16.67: everything drawn advances 1 ms too little or too
         * much, alternately. Measured as 0.024 m/frame^2 of jitter on a car at 28 m/s under a static script camera
         * (capture 014, scam24b). Offline (sim_dt == dt) replace both with the exact QPC interval. simclock_time keeps
         * its own ms sum, which tracks real time either way. */
        LARGE_INTEGER q;
        QueryPerformanceCounter(&q);
        if (g_prev_q.QuadPart) {
            float dts = (float)((double)(q.QuadPart - g_prev_q.QuadPart) / (double)g_qpf.QuadPart);
            volatile float *sim_dt = (volatile float *)(DWORD_PTR)NA(0x004fe420), *sim_rate = (volatile float *)(DWORD_PTR)NA(0x004fe424);
            volatile float *dt = (volatile float *)(DWORD_PTR)NA(0x004fe428), *rate = (volatile float *)(DWORD_PTR)NA(0x004fe42c);
            if (*sim_dt == *dt && dts >= 0.001f && dts <= 0.2f) { *dt = *sim_dt = dts; *rate = *sim_rate = 1.0f / dts; }
        }
        g_prev_q = q;
    }
    if (g_rpl_on) rpl_post_clock();                         /* I76_REPLAY: this frame's sim_dt / dt from the trace */
    if (g_ratefix) {
        /* constants the engine applies once per frame / per render pass, rescaled so their effect per SECOND is
         * what it was at 20 fps: value x (frame dt / 0.05). simclock_dt 0x4fe428 is this frame's clamped dt. */
        float k = *(volatile float *)0x004fe428 * g_ref_rate;   /* I76_REF_FPS (default 20) */
        g_cloud_u = 1.0f * k; g_cloud_v = -1.0f * k; g_cam_rate = -0.017453292f * k; g_zoom_rate = -0.01f * k;
        g_thr_up = -0.4f * k; g_thr_dn = 0.5f * k;
        g_acc20 += *(volatile float *)0x004fe428;
        g_grid_acc += *(volatile float *)0x004fe428;
        g_tick20 = g_acc20 >= g_ref_dt - 0.001f;             /* 1 ms tolerance: n x dt lands a hair under 0.05 (I76_REF_FPS: 1 / rate) */
        if (g_tick20) {
            g_acc20 -= g_ref_dt; if (g_acc20 > g_ref_dt || g_acc20 < -0.01f) g_acc20 = 0.0f; g_tick20_n++; radar_ping_flush();
            g_grid_win = g_grid_acc; g_grid_acc = 0.0f;      /* what a per-frame step skipped since the last grid frame has to cover */
        }
        if (g_ai_hz == g_ref_rate) { g_tickai = g_tick20; g_tickai_n = g_tick20_n; }
        else {                                               /* I76_AI_GRID_HZ: same accumulator form at another rate */
            float per = 1.0f / g_ai_hz;
            g_accai += *(volatile float *)0x004fe428;
            g_tickai = g_accai >= per - 0.001f;
            if (g_tickai) { g_accai -= per; if (g_accai > per || g_accai < -0.01f) g_accai = 0.0f; g_tickai_n++; }
        }
        /* a turn of `a` per 50 ms step, spread over frames: a rate limit scales by k; a proportional step that removes
         * 0.75 of the error scales to 1 - 0.25^k of it, so 1/k frames remove 0.75 again (radar_turn_wrap) */
        g_turn_k = k < 1.0f ? k : 1.0f;
        {   /* 0.25^k = exp(-ln 4 x k), k in (0, 1]: 12 series terms are exact to float (no CRT pow: it adds 25 KB) */
            double x = -1.3862943611198906 * (double)g_turn_k, term = 1.0, e = 1.0; int j;
            for (j = 1; j <= 12; j++) { term *= x / (double)j; e += term; }
            g_turn_g = g_turn_k >= 1.0f ? 1.0f : (float)((1.0 - e) / 0.75);   /* 20 fps and below: stock, exactly */
        }
    }
    g_coll_dup = 0;
    if (g_fl_period) {
        LARGE_INTEGER fl_out;
        QueryPerformanceCounter(&fl_out);
        fps_log_frame(fl_in.QuadPart, fl_cap.QuadPart, fl_out.QuadPart);
    }
}

static void install_frame_hook(void) {
    static const BYTE old_call[5] = { 0xE8, 0x63, 0x8F, 0x09, 0x00 };   /* call 0x49c920 at 0x4039b8 */
    BYTE new_call[5] = { 0xE8, 0, 0, 0, 0 };
    LONG rel = (LONG)((DWORD_PTR)frame_cap_then_clock - (0x004039b8 + 5));
    if (g_frame_hook) return;
    memcpy(new_call + 1, &rel, 4);
    g_frame_hook = patch_bytes(0x004039b8, old_call, new_call, 5, "frame clock call");
    mlog("  frame hook at 0x4039b8: %s", g_frame_hook ? "installed" : "NOT installed");
}

static void apply_volume_test(void) {
    char v[32]; DWORD n = env_str("I76_VOLUME_TEST", v, sizeof(v));
    if (n == 0) return;
    g_voltest_level = atoi(v); g_voltest_frame = (DWORD)atol(strchr(v, ',') ? strchr(v, ',') + 1 : "600");
    install_frame_hook();
    mlog("  volume-test: armed - level %d at proxy frame %lu", g_voltest_level, (unsigned long)g_voltest_frame);
}
/* The frame hook only runs inside the mission loop (game state 0x4c2164 == 5), so a game parked in the shell, a
 * movie or a modal logs nothing at all. This thread says where it is instead: once a period, if the frame counter
 * has not moved, the state and the counter. */
static HANDLE g_fl_main;                                     /* the game's main thread (DllMain runs on it) */
static DWORD WINAPI fps_log_watch(LPVOID arg) {
    DWORD sec = (DWORD)(DWORD_PTR)arg, last = (DWORD)-1;
    for (;;) {
        Sleep(sec * 1000);
        if (g_frame == last) {
            volatile BYTE *b = (volatile BYTE *)(DWORD_PTR)(NA(0x004039b8) ? NA(0x004039b8) : 0x004039b8);   /* our call, or did something rewrite it? */
            /* Where the main thread is parked: eip and up to 8 return addresses off the ebp chain. Read while it is
             * suspended, logged after it resumes (mlog must not run while it might hold a lock we need). */
            DWORD ret[9] = {0}; int nret = 0;
            if (g_fl_main && SuspendThread(g_fl_main) != (DWORD)-1) {
                CONTEXT c; DWORD fp, fr[2]; SIZE_T got;
                c.ContextFlags = CONTEXT_CONTROL;
                if (GetThreadContext(g_fl_main, &c)) {
                    ret[nret++] = c.Eip; fp = c.Ebp;
                    while (nret < 9 && fp &&
                           ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(DWORD_PTR)fp, fr, 8, &got) && got == 8) {
                        ret[nret++] = fr[1];
                        if (fr[0] <= fp) break;                       /* frames grow up the stack; stop on a bad link */
                        fp = fr[0];
                    }
                }
                ResumeThread(g_fl_main);
            }
            mlog("  fps: no mission frames; game state %ld, proxy frame %lu; hook site %02x %02x %02x %02x %02x; "
                 "main thread at %08lx < %08lx %08lx %08lx %08lx %08lx %08lx %08lx %08lx",
                 (LONG)nrd32(0x004c2164), (unsigned long)g_frame, b[0], b[1], b[2], b[3], b[4],
                 ret[0], ret[1], ret[2], ret[3], ret[4], ret[5], ret[6], ret[7], ret[8]);
            {   /* which module each address is in, as module+offset */
                int k; char line[600]; int pos = 0;
                for (k = 0; k < nret && pos < (int)sizeof(line) - 80; k++) {
                    HMODULE m = NULL; char name[MAX_PATH] = "?", *base = name, *q;
                    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                           (LPCSTR)(DWORD_PTR)ret[k], &m) && m) {
                        GetModuleFileNameA(m, name, sizeof(name));
                        for (q = name; *q; q++) if (*q == '\\' || *q == '/') base = q + 1;
                    }
                    pos += _snprintf(line + pos, sizeof(line) - pos, " %s+%lx", base,
                                     (unsigned long)(m ? ret[k] - (DWORD)(DWORD_PTR)m : ret[k]));
                }
                line[sizeof(line) - 1] = 0;
                mlog("  fps: main thread modules:%s", line);
            }
        }
        last = g_frame;
    }
}
/* I76_FPS_PROF=1 (with I76_FPS_LOG): a sampling profiler for "where do the frame's milliseconds go". Every ~2 ms
 * the main thread is suspended just long enough to read eip, then resumed; only after the resume is the sample
 * classified (module lookup takes the loader lock, which the suspended thread might hold). Each log period it
 * prints the share per module and the hottest 4 KB code pages of i76.exe. Adds a few % overhead: diagnosis only. */
#define PROF_MODS 24
static HMODULE g_pm_mod[PROF_MODS]; static DWORD g_pm_n[PROF_MODS], g_pm_total;
static DWORD g_pm_page[0xC0];                                   /* i76.exe 0x400000..0x4bffff by 4 KB page */
#define PROF_CALLERS 32
static DWORD g_pc_chain[10], g_pc_chain_n;                     /* one raw chain of an outside-the-exe sample per period */
static DWORD g_pc_addr[PROF_CALLERS], g_pc_n[PROF_CALLERS];     /* outside the exe: the first exe return address up the
                                                                   ebp chain, i.e. which game call site is waiting */
static void prof_log(void) {
    int i, j, order[PROF_MODS], n = 0; char line[700]; int pos = 0;
    if (!g_pm_total) return;
    for (i = 0; i < PROF_MODS; i++) if (g_pm_n[i]) order[n++] = i;
    for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) if (g_pm_n[order[j]] > g_pm_n[order[i]]) { int t = order[i]; order[i] = order[j]; order[j] = t; }
    for (i = 0; i < n && i < 8 && pos < (int)sizeof(line) - 60; i++) {
        char name[MAX_PATH] = "?", *base = name, *q;
        if (g_pm_mod[order[i]]) GetModuleFileNameA(g_pm_mod[order[i]], name, sizeof(name));
        for (q = name; *q; q++) if (*q == '\\' || *q == '/') base = q + 1;
        pos += _snprintf(line + pos, sizeof(line) - pos, " %s %.0f%%", base, 100.0 * g_pm_n[order[i]] / g_pm_total);
    }
    line[sizeof(line) - 1] = 0;
    mlog("  prof: %lu samples:%s", (unsigned long)g_pm_total, line);
    pos = 0;
    for (i = 0; i < 6; i++) {                                     /* top i76.exe pages */
        int best = -1;
        for (j = 0; j < 0xC0; j++) if (g_pm_page[j] && (best < 0 || g_pm_page[j] > g_pm_page[best])) best = j;
        if (best < 0) break;
        pos += _snprintf(line + pos, sizeof(line) - pos, " %06lx %.0f%%", 0x400000ul + best * 0x1000ul, 100.0 * g_pm_page[best] / g_pm_total);
        g_pm_page[best] = 0;
    }
    line[sizeof(line) - 1] = 0;
    if (pos) mlog("  prof: i76.exe hot pages:%s", line);
    pos = 0;
    for (i = 0; i < 6; i++) {                                     /* top exe call sites seen from outside the exe */
        int best = -1;
        for (j = 0; j < PROF_CALLERS; j++) if (g_pc_n[j] && (best < 0 || g_pc_n[j] > g_pc_n[best])) best = j;
        if (best < 0) break;
        pos += _snprintf(line + pos, sizeof(line) - pos, " %08lx %.0f%%", (unsigned long)g_pc_addr[best], 100.0 * g_pc_n[best] / g_pm_total);
        g_pc_n[best] = 0;
    }
    line[sizeof(line) - 1] = 0;
    if (pos) mlog("  prof: outside the exe, called from:%s", line);
    if (g_pc_chain_n) {                                           /* the sample chain: eip, esp, ebp, then return addresses */
        int k; pos = 0;
        for (k = 0; k < (int)g_pc_chain_n && pos < (int)sizeof(line) - 70; k++) {
            HMODULE m = NULL; char name[MAX_PATH] = "-", *base = name, *q;
            if (k != 1 && k != 2 && GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                                       (LPCSTR)(DWORD_PTR)g_pc_chain[k], &m) && m) {
                GetModuleFileNameA(m, name, sizeof(name));
                for (q = name; *q; q++) if (*q == '\\' || *q == '/') base = q + 1;
            }
            pos += _snprintf(line + pos, sizeof(line) - pos, " %08lx(%s)", (unsigned long)g_pc_chain[k], base);
        }
        line[sizeof(line) - 1] = 0;
        mlog("  prof: one outside sample [eip esp ebp ret...]:%s", line);
        g_pc_chain_n = 0;
    }
    memset(g_pc_addr, 0, sizeof g_pc_addr); memset(g_pc_n, 0, sizeof g_pc_n);
    memset(g_pm_n, 0, sizeof g_pm_n); memset(g_pm_page, 0, sizeof g_pm_page); g_pm_total = 0;
}
static DWORD WINAPI prof_thread(LPVOID arg) {
    DWORD period_ms = (DWORD)(DWORD_PTR)arg, t0 = GetTickCount();
    for (;;) {
        CONTEXT c; DWORD eip = 0; HMODULE m = NULL; int i;
        Sleep(2);
        if (SuspendThread(g_fl_main) == (DWORD)-1) continue;
        DWORD caller = 0;
        c.ContextFlags = CONTEXT_CONTROL;
        if (GetThreadContext(g_fl_main, &c)) {
            eip = c.Eip;
            if (eip < 0x400000 || eip >= 0x4c0000) {              /* walk the ebp chain to the first exe return address */
                DWORD fp = c.Ebp, fr[2]; SIZE_T got; int d, keep = !g_pc_chain_n;
                if (keep) { g_pc_chain[0] = eip; g_pc_chain[1] = c.Esp; g_pc_chain[2] = c.Ebp; g_pc_chain_n = 3; }
                for (d = 0; d < 12 && fp; d++) {
                    if (!ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(DWORD_PTR)fp, fr, 8, &got) || got != 8) break;
                    if (keep && g_pc_chain_n < 10) g_pc_chain[g_pc_chain_n++] = fr[1];
                    if (fr[1] >= 0x400000 && fr[1] < 0x4c0000) { caller = fr[1]; break; }
                    if (fr[0] <= fp) break;
                    fp = fr[0];
                }
            }
        }
        ResumeThread(g_fl_main);
        if (!eip || !g_frame) continue;                           /* only while mission frames run */
        if (caller) {
            for (i = 0; i < PROF_CALLERS; i++) if (g_pc_addr[i] == caller || !g_pc_n[i]) { g_pc_addr[i] = caller; g_pc_n[i]++; break; }
        }
        GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)(DWORD_PTR)eip, &m);
        for (i = 0; i < PROF_MODS; i++) if (g_pm_mod[i] == m || (!g_pm_mod[i] && !g_pm_n[i])) { g_pm_mod[i] = m; g_pm_n[i]++; break; }
        if (eip >= 0x400000 && eip < 0x4c0000) g_pm_page[(eip - 0x400000) >> 12]++;
        g_pm_total++;
        if (GetTickCount() - t0 >= period_ms) { prof_log(); t0 = GetTickCount(); }
    }
}
static void apply_frame_log(void) {
    char v[MAX_PATH];
    if (!env_str("I76_FRAME_LOG", v, sizeof(v))) return;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    g_frlog = fopen(v, "w");
    if (!g_frlog) { mlog("  frame-log: cannot open '%s' - off", v); return; }
    fprintf(g_frlog, "frame,wall_ms,sim_dt_ms,dt_ms,step_ms,step_count,fg,inactive\n");
    install_frame_hook();
    mlog("  frame-log: one line per mission frame to %s (wall period, sim dt, player stepper step / count)%s", v,
         g_frame_hook ? "" : " (hook failed: no log)");
}
static void apply_fps_log(void) {
    char v[16]; DWORD n = env_str("I76_FPS_LOG", v, sizeof(v)); int sec;
    if (n == 0 || (sec = atoi(v)) < 1 || sec > 600) return;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    g_fl_period = g_qpf.QuadPart * sec;
    install_frame_hook();
    g_fl_main = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, GetCurrentThreadId());
    CloseHandle(CreateThread(NULL, 0, fps_log_watch, (LPVOID)(DWORD_PTR)sec, 0, NULL));
    if (GetEnvironmentVariableA("I76_FPS_PROF", v, sizeof(v)) && v[0] == '1' && g_fl_main) {
        CloseHandle(CreateThread(NULL, 0, prof_thread, (LPVOID)(DWORD_PTR)(sec * 1000), 0, NULL));
        mlog("  fps-prof: sampling the main thread every ~2 ms");
    }
    mlog("  fps-log: every %d s%s", sec, g_frame_hook ? "" : " (hook failed: no log)");
}
static void apply_frame_cap(void) {
    static const BYTE old_call[5] = { 0xE8, 0x63, 0x8F, 0x09, 0x00 };   /* call 0x49c920 at 0x4039b8 */
    BYTE new_call[5] = { 0xE8, 0, 0, 0, 0 };
    char v[16]; double fps;
    LONG rel = (LONG)((DWORD_PTR)frame_cap_then_clock - (0x004039b8 + 5));
    DWORD n = env_str("I76_FPS_CAP", v, sizeof(v));
    /* fractional rates allowed (2026-10-14, lab W95-18-BASELINE: 18.2 = the PC timer's 18.2 Hz, one 55 ms Windows 95
     * GetTickCount tick per frame); the period is rounded to the nearest QPC count */
    if (n == 0 || (fps = atof(v)) < 5.0 || fps > 1000.0) return;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    g_cap_period.QuadPart = (LONGLONG)((double)g_qpf.QuadPart / fps + 0.5);
    {   /* The cap sleeps (left - 2) ms and spins the rest. With the default 15.6 ms timer tick a 3 ms sleep takes a
         * whole tick, so any cap above ~64 fps delivered ~62 (measured 2026-10-03: I76_FPS_CAP=179 -> 62.6 fps under
         * nGlide). Ask for 1 ms timer resolution for the life of the process (winmm resolved at run time: the fix
         * builds of the exe have no WINMM import). */
        HMODULE wm = LoadLibraryA("winmm.dll");
        UINT (WINAPI *tbp)(UINT) = wm ? (UINT (WINAPI *)(UINT))GetProcAddress(wm, "timeBeginPeriod") : NULL;
        if (tbp) tbp(1);
    }
    (void)old_call; (void)new_call; (void)rel;
    install_frame_hook();
    mlog("  fps-cap: %.3f fps (period %.4f ms)%s", fps, (double)g_cap_period.QuadPart * 1000.0 / (double)g_qpf.QuadPart,
         g_frame_hook ? "" : " (hook failed: no cap)");
}

/* ===========================================================================
 * FRAME-RATE FIXES  (I76_FRAMERATE_FIXES=1; off by default)
 * ===========================================================================
 * Sites that apply a constant once per frame (or per render pass) with no dt, so
 * their effect per second scales with the frame rate (i76-map subsystemsramerate.md):
 *   cloud scroll   renderer_DrawClouds: fld [0x4bc4c4] (+1.0) at 0x405461, fld [0x4bc500] (-1.0) at 0x405484 -
 *                  u -= 1/(1001-s), v += 1/(1001-s) per call; measured 3.0x faster at 60 fps (capture 014)
 *   free-look keys camera_FreeLookA/B: fmul [0x4bc528] (-1 deg) at 0x405bd0 0x405c1c 0x4061e7 0x406233
 *   zoom key       camera mode 0x408a10: zoom *= 1 - input x 0.01 per frame (fmul [0x4bc5ac] at 0x408a3f)
 *   throttle keys  input_ApplyToEntity: throttle += 0.4 x (1 - hold/3) per frame for throttle-up (fmul [0x4bd8f4] at
 *                  0x44f306) and -= 0.5 x (...) for throttle-down (fmul [0x4bd8f8] at 0x44f366); measured: full in
 *                  2 frames at any rate, so 3x faster at 60 fps - matters when tests drive by held keys
 * Each operand is repointed at a proxy variable that the frame hook sets to constant x dt x 20 after every
 * simclock_Update, which keeps the 20 fps look at any frame rate. Only the listed instructions change; the
 * constants themselves (shared with other code) are untouched.
 */
/* Sounds requested on every frame while a state holds (repeat-until-false sites): the missile-lock tones (weapon
 * update 0x4a3760, msllock1/2/3.wav, reported beeping fast at 60 fps) and the vehicle's per-frame sounds at the end of
 * its tick (0x43d500: tskid/tturn/vcddirt/vcdsand from the 0x4bd0d0 table, tflat.wav, fdmg1.wav). Each is requested
 * through 0x423230. The sound layer (0x421b40) only refreshes a LOOPING (state 2) instance of the same name on the same
 * object and starts a new one otherwise, so after each beep ends the next one starts on the next frame: the gap
 * between beeps is quantised to the frame time, and the tone beeps faster at 60 fps (reported in play). Starts are
 * let through on a 20 Hz grid only; a request for a looping instance that is already playing still goes through on
 * every frame, because the per-frame sound update stops loops whose keep-alive (+0x74) was not refreshed. */
static int __cdecl frame_sound_wrap(const char *name, BYTE *obj, int flag) {
    if (!g_tick20) {
        BYTE *mgr = *(BYTE **)0x00524564, *e;
        BYTE *o = obj;
        if (!o) { BYTE **pp = ((BYTE **(__cdecl *)(void))0x00457530)(); o = pp ? *pp : 0; }   /* as 0x423230 does */
        for (e = mgr ? *(BYTE **)(mgr + 0x1c) : 0; e; e = *(BYTE **)e)
            if (*(BYTE **)(e + 0x5c) == o && lstrcmpiA((const char *)(e + 4), name) == 0 && *(int *)(e + 0x3c) == 2) break;
        if (!e) return 0;                                    /* would start a new beep: wait for the 20 Hz grid */
    }
    return ((int (__cdecl *)(const char *, BYTE *, int))0x00423230)(name, obj, flag);
}

/* AI throttle (ai_UpdateThrottle 0x40f9c0): throttle = f((target speed - speed) x simclock_GetSimRate), i.e. the
 * acceleration that would close the gap in ONE FRAME. That is a gain proportional to the frame rate, not a
 * derivative of a measured change, so at 60 fps it asks for 3x the correction, saturates and chatters (capture 014:
 * total variation 26.2 /s at 60 fps vs 1.56 at 20; 5.33 even with the hires clock and fixed step). Both reads
 * (0x40fa15 type-9 branch, 0x40fa8d vehicles) get the 20 fps rate. */
static float __cdecl ai_rate20(void) { return g_ref_rate; }   /* I76_REF_FPS (default 20) */
/* AI steering (ai_SteerToHeading 0x40fe80): steer = skill x heading error / (sim_dt x k x v), the yaw rate that closes the
 * heading error in one frame (i76-map subsystems/ai.md). The sim_dt read at 0x40fed9 is used only as that divisor, so it
 * gets the 20 fps value. */
static float __cdecl ai_dt20(void) { return g_ref_dt; }       /* I76_REF_FPS (default 0.05) */
/* AI GAINS ON THE 1997 FRAME CLOCK  (I76_AI_STOCK_CLOCK=1, needs I76_FRAMERATE_FIXES + I76_FIXED_STEP; off by default)
 * Lab doc AI-PACE-2026-10-12.md (T04 racers). Both gains above are dead-beat: the command is sized to close the error over
 * ONE frame of the dt the AI reads (k = this frame), but the physics applies it over the NEXT frame (k + 1): the yaw
 * (speed) change a command makes is skill x error x dt[k+1] / dt[k]. The 1997 game reads its clock from GetTickCount,
 * 15.625 ms quanta on this hardware, so at a nominal 24 fps the frame dts run 46.9, 46.9, 31.2 ms (3, 3, 2 ticks) and
 * the ratio cycles 1, 0.67, 1.5: every third command overshoots by half and the next one undershoots. The racers
 * weave a little through every bend and lap T04 ~5 % slower than with an exact clock (measured: stock24 with only
 * I76_HIRES_CLOCK, or only I76_FRAMERATE_FIXES, runs at best-wide's pace; the AI pass rate is not it - best-wide
 * capped at 24 fps, one AI pass per step, is as quick as at 120). Under I76_FIXED_STEP every step is exactly
 * 1/rate, so the pinned gains give a ratio of 1 every time: smoother, and quicker than 1997.
 * With this switch the three gain reads return the stock clock's ratio for the step the command will drive:
 * dt_used = step x dt[k] / dt[k+1], dt[k] = 15.625 ms x (floor(k x step / 15.625 ms) - floor((k - 1) x step / 15.625 ms)),
 * k = the physics step index from sim time [0x5a7e70] x rate (every AI pass between two steps reads the same k, and
 * the last one before step k+1 is the one that drives it). Throttle sites get 1 / dt_used, the steering site dt_used.
 * I76_AI_STOCK_CLOCK=1 uses the 15.625 ms tick; a value of 1.5..100 is taken as the tick in ms (e.g. 10 = a 100 Hz timer).
 * I76_AI_STOCK_CLOCK_FPS=<fps> emulates a game at that frame rate (e.g. 20) instead of one frame per fixed step; frames
 * that read 0 ticks get simclock's 1 ms floor, as a 55 ms tick at 20+ fps does (2026-10-13, AI-COMBAT-PARITY).
 * Measured T04 (lab doc): best-wide + this switch laps at stock24 pace. */
static int g_ai_stockclk;
static double g_ai_tick = 0.015625;
static double g_ai_frame;                                    /* I76_AI_STOCK_CLOCK_FPS: the emulated 1997 frame (s); 0 = the fixed step */
static double ai_stock_frame_dt(double j, double F) {       /* the 1997 frame j's dt: whole ticks, simclock's clamp [1, 200] ms */
    double d = g_ai_tick * (floor(j * F / g_ai_tick + 1e-9) - floor((j - 1.0) * F / g_ai_tick + 1e-9));
    return d < 0.001 ? 0.001 : d > 0.2 ? 0.2 : d;
}
static float ai_stock_dt_used(void) {
    double S = (double)g_fixed_step, t = (double)*(volatile float *)0x005a7e70, F = g_ai_frame > 0.0 ? g_ai_frame : S;
    double j = floor(t / F + 1e-3);
    /* the command sized with frame j's dt, applied over frame j+1: per-command correction dt[j+1] / dt[j]; one fixed
     * step S carries the same fraction when the gain reads S x dt[j] / dt[j+1] */
    return (float)(S * ai_stock_frame_dt(j, F) / ai_stock_frame_dt(j + 1.0, F));
}
static float __cdecl ai_gain_rate(void) { return g_ai_stockclk == 1 ? 1.0f / ai_stock_dt_used() : g_ref_rate; }
static float __cdecl ai_gain_dt(void) { return g_ai_stockclk ? ai_stock_dt_used() : g_ref_dt; }

/* Radar ping (CRADAR.WAV, radar blip routine 0x460310, played through 0x4250f0 at 0x4605ee / 0x4608f1). Unlocked,
 * the sweep advances on game time (one of 30 positions per 0.2 s) and a blip pings when the window [previous,
 * current position] passes it - frame-rate neutral. Locked on, the position is re-aimed at the target's bearing every
 * frame while the previous position (+8) is only updated on the unlocked path, so every other blip inside the wedge
 * pings on EVERY FRAME: 20 pings/s at 20 fps, 60/s at 60 fps (reported "lock beep too fast"). Pings are coalesced
 * onto the 20 Hz grid: one asked for between grid frames is held and played on the next one, so sweep pings are
 * never lost and the locked case pings at most 20 times a second, as at stock 20 fps. */
static DWORD g_idbg_ping_req, g_idbg_ping_play, g_idbg_ping_frames, g_ping_req_last;           /* copied into the debug block by the render wrapper */
static const char *g_ping_name;
static BYTE *g_ping_obj;
static int g_ping_flag, g_ping_pending;
static DWORD g_ping_frame, g_ping_tick;
static int __cdecl radar_ping_wrap(const char *name, BYTE *obj, int flag) {
    g_idbg_ping_req++;
    if (g_ping_req_last != g_frame) { g_ping_req_last = g_frame; g_idbg_ping_frames++; }
    if (!g_tick20) { g_ping_name = name; g_ping_obj = obj; g_ping_flag = flag; g_ping_pending = 1; g_ping_tick = GetTickCount(); return 0; }
    if (g_ping_frame == g_frame) return 0;                   /* one per grid frame */
    g_ping_frame = g_frame; g_ping_pending = 0; g_idbg_ping_play++;
    return ((int (__cdecl *)(const char *, BYTE *, int))(DWORD_PTR)NA(0x004250f0))(name, obj, flag);
}
static void radar_ping_flush(void) {                        /* from the frame hook, on grid frames */
    /* a ping held across a mission end must not play: its object is freed by then (the next mission crashed in
     * 0x4250f0 -> 0x458c90 on the freed pointer, co-op soak 2026-10-07, after 50+ clean reloads). Held pings are at
     * most one grid frame (50 ms) old in play; older ones are dropped. */
    if (g_ping_pending && GetTickCount() - g_ping_tick > 250) g_ping_pending = 0;
    if (g_ping_pending && g_ping_frame != g_frame) {
        g_ping_pending = 0; g_ping_frame = g_frame; g_idbg_ping_play++;
        ((int (__cdecl *)(const char *, BYTE *, int))(DWORD_PTR)NA(0x004250f0))(g_ping_name, g_ping_obj, g_ping_flag);
    }
}

/* Flamers (i76-map subsystems/weapons.md, renderer.md). Three per-render-call dependencies:
 *  - weapon_AgeFlamerStreams 0x443e90 (top of each render) retracts a stream by 2 segments on every call unless the
 *    weapon fired since the last call (+0x10 flag, cleared by the same call). Shots come on the weapon's own timer
 *    (20/s for every flamer), so at 60 fps two calls in three see no shot and the stream never grows past a segment
 *    or two; at 20 fps it grows one segment per shot up to 19.
 *  - weapon_UpdateFlamerStreams 0x443fc0 rebuilds the flame's shape on every call from the frame dt (droop ~ dt^2,
 *    bend toward the target ~ dt), and applies damage through weapon_FlameHitTest 0x4354c0 -> weapon_ApplyFlameDamage
 *    0x4a8240 per hitting segment per call: max(1, int(damage x difficulty x dt)). Per second that is 20 calls at
 *    20 fps and 60 at 60 fps; the rear-mirror pass (renderer_DrawRearMirror 0x445750) calls it once more per frame.
 * Here: the stream ages on the 20 Hz grid (the fired flag collects over the grid window); the update sees the stock
 * 20 fps dt (max(dt, 0.05)), so shape and per-hit damage are the stock-20 ones; damage is applied only from the main
 * render pass on grid frames, i.e. 20 times a second, as at stock 20 fps with the mirror off. */
static DWORD g_idbg_flame_hits, g_idbg_flame_dmg;           /* copied into the debug block by the render wrapper */
static int g_flame_dmg_ok;
static float g_st_flame_dmg = 1.0f;                          /* I76_SIM_TICK_FLAME_DMG as a number: a fixed factor (simtick.c; flame_damage_wrap below) */
static int g_st_flame_auto;                                  /* 1 = the rate-aware factor (I76_SIM_TICK_FLAME_DMG unset or 'auto'; TICK-FINISH s.18) */
static float g_st_flame_ref = 3.5f, g_st_flame_k = 1.0f;     /* ... its factor at the 1997 rate (I76_SIM_TICK_FLAME_DMG_REF), and T_ref / T */
static DWORD g_fdc_in, g_fdc_out;                            /* flame amounts before / after that factor (log) */
static float __cdecl step20_dt(void) { float dt = *(volatile float *)(DWORD_PTR)NA(0x004fe428); return dt > g_ref_dt ? dt : g_ref_dt; }
static void __cdecl flame_age_wrap(void) { if (g_tick20) ((void (__cdecl *)(void))(DWORD_PTR)NA(0x00443e90))(); }
/* flamer census, update cadence: every weapon_UpdateFlamerStreams call while a stream is live, split into calls whose
 * hits would apply damage (stock: every call, main pass and mirror; the 20 Hz grid / the tick: main-pass calls on grid
 * frames / tick frames) and calls that cannot, with the sim time span - the damage per second per hitting segment is
 * these calls per sim second x max(1, int(D x f x dt)) whether or not the harness gets a segment onto a target. */
static DWORD g_flc_upd_dmg, g_flc_upd_nodmg, g_flc_upd_mirror;
static float g_flc_u0 = -1.0f, g_flc_u1;
static int flc_stream_live(void) {
    int live = 0;
#ifdef _MSC_VER
    __try {
#endif
        BYTE *s0 = *(BYTE **)0x0052bb90, *st = s0; int k = 0;
        while (st && k++ < 64) { if (*(DWORD *)(st + 4) && *(int *)(st + 0x14) > 0) { live = 1; break; } st = *(BYTE **)st; if (st == s0) break; }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { live = 0; }
#endif
    return live;
}
static void flc_count_update(int dmg, int mirror) {
    float t;
    if (!g_flc_on || !flc_stream_live()) return;
    t = *(volatile float *)0x005a7e70;
    if (dmg) g_flc_upd_dmg++; else g_flc_upd_nodmg++;
    if (mirror) g_flc_upd_mirror++;
    if (g_flc_u0 < 0.0f) g_flc_u0 = t;
    g_flc_u1 = t;
}
static void __cdecl flame_census_main(BYTE *cam) { flc_count_update(1, 0); ((void (__cdecl *)(BYTE *))0x00443fc0)(cam); }   /* stock frame loop */
static void __cdecl flame_census_mirror(BYTE *cam) { flc_count_update(!g_flame_wrapped, 1); ((void (__cdecl *)(BYTE *))0x00443fc0)(cam); }
static void __cdecl flame_update_main(BYTE *cam) {
    flc_count_update(g_tick20, 0);
    g_flame_dmg_ok = g_tick20;
    ((void (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x00443fc0))(cam);
    g_flame_dmg_ok = 0;
}
typedef struct { DWORD d[6]; } dmgrec_t;                    /* passed by value: owner, kind 4, ..., amount at d[4] */
/* FLAMER CENSUS (I76_FLAME_CENSUS=1, lab instrument, 2026-10-18 tick-gaps; counts only, changes nothing): every flamer
 * damage application (weapon_FlameHitTest -> weapon_ApplyFlameDamage, site 0x4357c3) with its amount (record d[4]),
 * split by owner (record d[0] = the player's object or not), the sim time (simclock 0x5a7e70) of the first and last
 * application and the mean segment count of the live streams (ring 0x52bb90, +0x14) sampled each display frame while a
 * stream exists. Under I76_FRAMERATE_FIXES / I76_SIM_TICK_MS the counts come from their damage wrapper (applied
 * calls only); without either, the census puts a pass-through counting wrapper on the site. A `flame-census:` line is
 * logged at most once a second of wall time when something changed. */
static DWORD g_flc_hits, g_flc_app, g_flc_amt_pl, g_flc_amt_ot, g_flc_app_pl, g_flc_raw[4], g_flc_nraw, g_flc_seg_sum, g_flc_seg_n, g_flc_last_log;
static DWORD g_flc_frames_app, g_flc_frame_last;
static DWORD g_flc_expl, g_flc_expl_blk;                   /* flame census: hit explosions spawned / held back (tick-fix 2026-10-18) */
static float g_flc_t0 = -1.0f, g_flc_t1, g_flc_tpl0 = -1.0f, g_flc_tpl1;
static void flame_census_note(const dmgrec_t *rec) {
    BYTE **pp = *(BYTE ***)0x0054a264, *pl = pp ? *pp : 0;
    float t = *(volatile float *)0x005a7e70;
    DWORD a = rec->d[4];
    g_flc_app++;
    if (g_flc_nraw < 4) g_flc_raw[g_flc_nraw++] = a;
    if (a > 100000) a = 0;                                   /* not an integer amount: counted, not summed */
    if (pl && rec->d[0] == (DWORD)(DWORD_PTR)pl) { g_flc_amt_pl += a; g_flc_app_pl++; if (g_flc_tpl0 < 0.0f) g_flc_tpl0 = t; g_flc_tpl1 = t; }
    else g_flc_amt_ot += a;
    if (g_flc_t0 < 0.0f) g_flc_t0 = t;
    g_flc_t1 = t;
    if (g_flc_frame_last != g_frame) { g_flc_frame_last = g_frame; g_flc_frames_app++; }
}
/* I76_FLAME_PROBE_AT=x,y,z (lab instrument, tick-fix 2026-10-18; with I76_FLAME_CENSUS): every weapon_FlameHitTest call from
 * the flamer update (site 0x44449b; args 0..2 = one end of the tested segment, 4..6 = the other, as floats) is counted and
 * the closest any tested segment came to the point is kept per log line: does the stream reach the target at all, and is
 * the hit test called while it does. */
static float g_fhp_at[3], g_fhp_min = 1e30f; static DWORD g_fhp_calls, g_fhp_near, g_fhp_nearhit; static int g_fhp_on;
static float g_fhp_snap[8];
static DWORD g_fhp_c[2], g_fhp_n[2], g_fhp_h[2]; static double g_fhp_seg[2];   /* [0] non-grid / non-tick frames, [1] grid / tick frames: calls, near calls, hits, sum |seg| */   /* the last near call: arg3 (segment radius), sim_dt, sim rate, dt, rate, |A-B|, result, the tick flag */
static int __cdecl flame_hit_probe(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD a6, DWORD a7,
                                   DWORD a8, DWORD a9, DWORD a10, DWORD a11, DWORD a12, DWORD a13, DWORD a14) {
    float A[3], B[3], d[3], w[3], t, dd, e2; int k;
    memcpy(&A[0], &a0, 4); memcpy(&A[1], &a1, 4); memcpy(&A[2], &a2, 4);
    memcpy(&B[0], &a4, 4); memcpy(&B[1], &a5, 4); memcpy(&B[2], &a6, 4);
    for (k = 0; k < 3; k++) { d[k] = B[k] - A[k]; w[k] = g_fhp_at[k] - A[k]; }
    dd = d[0] * d[0] + d[1] * d[1] + d[2] * d[2];
    t = dd > 1e-9f ? (w[0] * d[0] + w[1] * d[1] + w[2] * d[2]) / dd : 0.0f;
    if (t < 0.0f) t = 0.0f; if (t > 1.0f) t = 1.0f;
    for (k = 0, e2 = 0.0f; k < 3; k++) { float q = A[k] + t * d[k] - g_fhp_at[k]; e2 += q * q; }
    g_fhp_calls++;
    if (e2 == e2 && e2 < g_fhp_min) g_fhp_min = e2;
    {
        int r = ((int (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))0x004354c0)
                (a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14);
        { int c = g_tick20 ? 1 : 0; g_fhp_c[c]++; g_fhp_seg[c] += sqrt((double)dd); if (e2 < 4.0f) g_fhp_n[c]++; if (r) g_fhp_h[c]++; }
        if (e2 < 4.0f || r) {
            if (e2 < 4.0f) { g_fhp_near++; if (r) g_fhp_nearhit++; }
            memcpy(&g_fhp_snap[0], &a3, 4);
            g_fhp_snap[1] = *(volatile float *)0x004fe420; g_fhp_snap[2] = *(volatile float *)0x004fe424;
            g_fhp_snap[3] = *(volatile float *)0x004fe428; g_fhp_snap[4] = *(volatile float *)0x004fe42c;
            g_fhp_snap[5] = sqrtf(dd); g_fhp_snap[6] = (float)r; g_fhp_snap[7] = (float)g_tick20;
        }
        return r;
    }
}
/* ... and (2026-10-18 tick-fix 2) the narrow test call inside weapon_FlameHitTest (site 0x435691 -> 0x43d770, reached only
 * when the tested point A is inside the record's bound sphere + 1 m): per world record that reaches it (up to 16), the
 * record type (+0x14), its object's class (+0x6c), bound radius and world centre, narrow calls and narrow hits split by
 * frame kind, the ray (A, d) as passed, d x sim_dt (the swept length the narrow test covers) and the clock at the call. */
typedef struct { DWORD rec, obj, cls, type; float rad, c[3]; DWORD n[2], h[2]; double sweep[2], dmin; float sdt[2], A[3], d[3]; } fnp_t;
static fnp_t g_fnp[16]; static int g_fnp_n; static DWORD g_fnp_over;
static int __cdecl flame_narrow_probe(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD rec, DWORD out, DWORD tp, DWORD pp, DWORD z, DWORD one) {
    int r = ((int (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))0x0043d770)(a0, a1, a2, a3, a4, a5, rec, out, tp, pp, z, one);
    int i, c = g_tick20 ? 1 : 0; fnp_t *e = 0; float A[3], d[3], ctr[4], sdt = *(volatile float *)0x004fe420; double q = 0.0;
    memcpy(&A[0], &a0, 4); memcpy(&A[1], &a1, 4); memcpy(&A[2], &a2, 4); memcpy(&d[0], &a3, 4); memcpy(&d[1], &a4, 4); memcpy(&d[2], &a5, 4);
    for (i = 0; i < g_fnp_n; i++) if (g_fnp[i].rec == rec) { e = &g_fnp[i]; break; }
    if (!e) {
        if (g_fnp_n >= 16) { g_fnp_over++; return r; }
        e = &g_fnp[g_fnp_n++]; memset(e, 0, sizeof(*e)); e->rec = rec; e->dmin = 1e30;
#ifdef _MSC_VER
        __try {
#endif
            e->obj = *(DWORD *)(DWORD_PTR)rec; e->type = *(DWORD *)(DWORD_PTR)(rec + 0x14); e->rad = *(float *)(DWORD_PTR)(rec + 0x10);
            if (e->obj) e->cls = *(DWORD *)(DWORD_PTR)(e->obj + 0x6c);
#ifdef _MSC_VER
        } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    }
#ifdef _MSC_VER
    __try {
#endif
        ((float *(__cdecl *)(float *, DWORD))0x00457650)(ctr, rec);
        e->c[0] = ctr[0]; e->c[1] = ctr[1]; e->c[2] = ctr[2];
        for (i = 0; i < 3; i++) q += (double)(A[i] - ctr[i]) * (A[i] - ctr[i]);
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    e->n[c]++; if (r) e->h[c]++;
    e->sweep[c] += sqrt((double)d[0] * d[0] + (double)d[1] * d[1] + (double)d[2] * d[2]) * sdt;
    e->sdt[c] = sdt;
    if (q < e->dmin) { e->dmin = q; memcpy(e->A, A, sizeof(A)); memcpy(e->d, d, sizeof(d)); }
    return r;
}
/* The flame's narrow test as a call site of its own (2026-10-19 flame-box): weapon_FlameHitTest's call at 0x435691 goes
 * through flame_narrow_call, which marks "inside a flame narrow test" for the breakable-box flame fix (bbox_flame_thunk)
 * and the box-test probe, then calls 0x43d770 or, with the census probe on, flame_narrow_probe. */
static volatile int g_in_flame_narrow;
static DWORD g_flame_narrow_next = 0x0043d770;
static int __cdecl flame_narrow_call(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD rec, DWORD out, DWORD tp, DWORD pp, DWORD z, DWORD one) {
    int r;
    g_in_flame_narrow = 1;
    r = ((int (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))(DWORD_PTR)g_flame_narrow_next)(a0, a1, a2, a3, a4, a5, rec, out, tp, pp, z, one);
    g_in_flame_narrow = 0;
    return r;
}
/* I76_FLAME_BOX_PROBE=1 (lab instrument, 2026-10-19 flame-box; needs I76_BREAKABLE_BOX and I76_BREAKABLE_BOX_FLAME=0 to
 * see the box at all): the box-part call of the tree narrow test (0x43dd3e -> slab test 0x43df10; args: ray P, D in part
 * space (6 floats), the part's box min, max (6 floats), two out pointers, the pad), counted only inside a flame narrow test.
 * The slab test is replayed in C in the code's own order (x, z, y; |D| < 1e-4 = parallel) and each call is filed under the
 * first comparison that rejects it; the replay's verdict is checked against the real return value. For the misses, the
 * closest the swept segment P .. P + D x sim_dt comes to the unpadded box (16 samples). */
enum { FBX_PAR_X, FBX_PAR_Z, FBX_PAR_Y, FBX_BEH_X, FBX_BEH_Z, FBX_BEH_Y, FBX_DISJ, FBX_BEHIND, FBX_SHORT, FBX_INSIDE, FBX_HIT, FBX_N };
static const char *g_fbx_name[FBX_N] = { "x parallel outside", "z parallel outside", "y parallel outside", "x slab behind", "z slab behind",
                                          "y slab behind", "slabs disjoint (passes beside)", "exit behind", "entry beyond sim_dt (too short)",
                                          "entry < 0 (starts inside)", "HIT" };
static DWORD g_fbx[FBX_N], g_fbx_agree, g_fbx_disagree, g_fbx_dist[5]; static int g_fbx_on;
static float g_fbx_pad = -1.0f, g_fbx_lo[3], g_fbx_hi[3], g_fbx_lastP[3], g_fbx_lastD[3];
static int __cdecl flame_box_probe(DWORD p0, DWORD p1, DWORD p2, DWORD d0, DWORD d1, DWORD d2, DWORD l0, DWORD l1, DWORD l2,
                                   DWORD h0, DWORD h1, DWORD h2, DWORD o1, DWORD o2, DWORD pd) {
    int r = ((int (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))0x0043df10)
            (p0, p1, p2, d0, d1, d2, l0, l1, l2, h0, h1, h2, o1, o2, pd);
    float P[3], D[3], lo[3], hi[3], pad, tn = -1e30f, tf = 1e30f, sdt = *(volatile float *)0x004fe420; int k, ax, why = -1;
    static const int order[3] = { 0, 2, 1 };
    if (!g_in_flame_narrow) return r;
    memcpy(&P[0], &p0, 4); memcpy(&P[1], &p1, 4); memcpy(&P[2], &p2, 4); memcpy(&D[0], &d0, 4); memcpy(&D[1], &d1, 4); memcpy(&D[2], &d2, 4);
    memcpy(&lo[0], &l0, 4); memcpy(&lo[1], &l1, 4); memcpy(&lo[2], &l2, 4); memcpy(&hi[0], &h0, 4); memcpy(&hi[1], &h1, 4); memcpy(&hi[2], &h2, 4);
    memcpy(&pad, &pd, 4);
    g_fbx_pad = pad; memcpy(g_fbx_lo, lo, sizeof(lo)); memcpy(g_fbx_hi, hi, sizeof(hi));
    for (k = 0; k < 3 && why < 0; k++) {
        float l, h, t0, t1;
        ax = order[k]; l = lo[ax] - pad; h = hi[ax] + pad;
        if (D[ax] > -1e-4f && D[ax] < 1e-4f) {
            if (P[ax] < l || P[ax] > h) { why = FBX_PAR_X + k; break; }
            t0 = -1e30f; t1 = 1e30f;
        } else {
            t0 = (l - P[ax]) / D[ax]; t1 = (h - P[ax]) / D[ax];
            if (t0 > t1) { float s = t0; t0 = t1; t1 = s; }
            if (t1 < 0.0f) { why = FBX_BEH_X + k; break; }
        }
        if (t0 > tn) tn = t0;
        if (t1 < tf) tf = t1;
    }
    if (why < 0) why = tn > tf ? FBX_DISJ : tf < 0.0f ? FBX_BEHIND : sdt < tn ? FBX_SHORT : tn < 0.0f ? FBX_INSIDE : FBX_HIT;
    g_fbx[why]++;
    if ((why == FBX_HIT) == (r != 0)) g_fbx_agree++; else g_fbx_disagree++;
    memcpy(g_fbx_lastP, P, sizeof(P)); memcpy(g_fbx_lastD, D, sizeof(D));
    if (why != FBX_HIT) {                                    /* closest approach of the swept segment to the unpadded box */
        double best = 1e30; int s;
        for (s = 0; s <= 16; s++) {
            double q = 0.0; float t = sdt * s / 16.0f;
            for (k = 0; k < 3; k++) { float x = P[k] + D[k] * t, c = x < lo[k] ? lo[k] - x : x > hi[k] ? x - hi[k] : 0.0f; q += (double)c * c; }
            if (q < best) best = q;
        }
        best = sqrt(best);
        g_fbx_dist[best < 0.25 ? 0 : best < 0.5 ? 1 : best < 1.0 ? 2 : best < 2.0 ? 3 : 4]++;
    }
    return r;
}
static void flame_box_log(void) {
    char b[700]; int i, n = 0;
    if (!g_fbx_on) return;
    for (i = 0; i < FBX_N; i++) if (g_fbx[i]) n += wsprintfA(b + n, "%s%s %lu", n ? ", " : "", g_fbx_name[i], (unsigned long)g_fbx[i]);
    b[n] = 0;
    mlog("  flame-box: box-part slab tests in flame narrow tests: %s; replay agrees %lu / disagrees %lu; pad %.3f; box %.2f..%.2f x %.2f..%.2f x %.2f..%.2f; "
         "misses by closest approach to the unpadded box <0.25 / <0.5 / <1 / <2 / >=2 m: %lu / %lu / %lu / %lu / %lu; last P %.2f,%.2f,%.2f D %.1f,%.1f,%.1f",
         n ? b : "none", (unsigned long)g_fbx_agree, (unsigned long)g_fbx_disagree, g_fbx_pad, g_fbx_lo[0], g_fbx_hi[0], g_fbx_lo[1], g_fbx_hi[1], g_fbx_lo[2], g_fbx_hi[2],
         (unsigned long)g_fbx_dist[0], (unsigned long)g_fbx_dist[1], (unsigned long)g_fbx_dist[2], (unsigned long)g_fbx_dist[3], (unsigned long)g_fbx_dist[4],
         g_fbx_lastP[0], g_fbx_lastP[1], g_fbx_lastP[2], g_fbx_lastD[0], g_fbx_lastD[1], g_fbx_lastD[2]);
}
static void flame_narrow_log(void) {
    int i;
    flame_box_log();
    if (g_simtick) mlog("  flame-dmg: factor %s under the tick: amounts %lu in, %lu applied", g_st_flame_auto ? "rate-aware" : "fixed", (unsigned long)g_fdc_in, (unsigned long)g_fdc_out);
    for (i = 0; i < g_fnp_n; i++) {
        fnp_t *e = &g_fnp[i];
        mlog("  flame-narrow: rec %08lx obj %08lx class %lu type %lu radius %.2f centre %.2f,%.2f,%.2f; narrow calls (other / grid-or-tick) %lu / %lu, hits %lu / %lu; "
             "mean |d| x sim_dt %.3f / %.3f m, last sim_dt %.4f / %.4f; closest A %.2f m: A %.2f,%.2f,%.2f d %.2f,%.2f,%.2f",
             (unsigned long)e->rec, (unsigned long)e->obj, (unsigned long)e->cls, (unsigned long)e->type, e->rad, e->c[0], e->c[1], e->c[2],
             (unsigned long)e->n[0], (unsigned long)e->n[1], (unsigned long)e->h[0], (unsigned long)e->h[1],
             e->n[0] ? e->sweep[0] / e->n[0] : 0.0, e->n[1] ? e->sweep[1] / e->n[1] : 0.0, e->sdt[0], e->sdt[1], sqrt(e->dmin),
             e->A[0], e->A[1], e->A[2], e->d[0], e->d[1], e->d[2]);
    }
    if (g_fnp_over) mlog("  flame-narrow: %lu calls on records past the 16 kept", (unsigned long)g_fnp_over);
}
static void flame_census_frame(void) {                      /* frame hook: stream lengths + the log line */
    if (!g_flc_on) return;
#ifdef _MSC_VER
    __try {
#endif
        BYTE *s0 = *(BYTE **)0x0052bb90, *st = s0; int k = 0;
        while (st && k++ < 64) {
            if (*(DWORD *)(st + 4)) { g_flc_seg_sum += *(DWORD *)(st + 0x14); g_flc_seg_n++; }
            st = *(BYTE **)st; if (st == s0) break;
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    if ((g_flc_hits || g_flc_seg_n) && GetTickCount() - g_flc_last_log >= 1000) {
        static DWORD logged_app = 0xFFFFFFFFu, logged_seg = 0xFFFFFFFFu;
        if (logged_app != g_flc_app || logged_seg != g_flc_seg_n) {
            logged_app = g_flc_app; logged_seg = g_flc_seg_n; g_flc_last_log = GetTickCount();
            mlog("  flame-census: sim %.3f s, hit calls %lu, applied %lu on %lu frames (player %lu, amount %lu, sim %.3f..%.3f s; others amount %lu), "
                 "sim %.3f..%.3f s, stream segments mean %.2f (n %lu), raw amounts %08lx %08lx %08lx %08lx; "
                 "updates with a live stream: %lu damage-capable (%lu mirror) + %lu not, sim %.3f..%.3f s; hit explosions spawned %lu, held back %lu; "
                 "probe: hit-test calls %lu, within 2 m of the point %lu (returned nonzero %lu), closest %.2f m; last near-or-hitting call: radius %.3f sim_dt %.4f rate %.2f dt %.4f rate %.2f |seg| %.3f r %.0f grid/tick %.0f; by frame (other / grid-or-tick): calls %lu / %lu, near %lu / %lu, hits %lu / %lu, mean |seg| %.2f / %.2f m",
                 *(volatile float *)0x005a7e70, (unsigned long)g_flc_hits, (unsigned long)g_flc_app, (unsigned long)g_flc_frames_app,
                 (unsigned long)g_flc_app_pl, (unsigned long)g_flc_amt_pl, g_flc_tpl0, g_flc_tpl1, (unsigned long)g_flc_amt_ot,
                 g_flc_t0, g_flc_t1, g_flc_seg_n ? (double)g_flc_seg_sum / g_flc_seg_n : 0.0, (unsigned long)g_flc_seg_n,
                 (unsigned long)g_flc_raw[0], (unsigned long)g_flc_raw[1], (unsigned long)g_flc_raw[2], (unsigned long)g_flc_raw[3],
                 (unsigned long)g_flc_upd_dmg, (unsigned long)g_flc_upd_mirror, (unsigned long)g_flc_upd_nodmg, g_flc_u0, g_flc_u1,
                 (unsigned long)g_flc_expl, (unsigned long)g_flc_expl_blk, (unsigned long)g_fhp_calls, (unsigned long)g_fhp_near,
                 (unsigned long)g_fhp_nearhit, g_fhp_min < 1e29f ? sqrt((double)g_fhp_min) : -1.0, g_fhp_snap[0], g_fhp_snap[1], g_fhp_snap[2],
                 g_fhp_snap[3], g_fhp_snap[4], g_fhp_snap[5], g_fhp_snap[6], g_fhp_snap[7],
                 (unsigned long)g_fhp_c[0], (unsigned long)g_fhp_c[1], (unsigned long)g_fhp_n[0], (unsigned long)g_fhp_n[1],
                 (unsigned long)g_fhp_h[0], (unsigned long)g_fhp_h[1], g_fhp_c[0] ? g_fhp_seg[0] / g_fhp_c[0] : 0.0, g_fhp_c[1] ? g_fhp_seg[1] / g_fhp_c[1] : 0.0);
            {   static DWORD nl; if (g_fhp_on && ++nl % 5 == 0) flame_narrow_log(); }
        }
    }
}
/* Flame damage factor under the whole-sim tick (2026-10-19 flame-dmg; I76_SIM_TICK_FLAME_DMG=<f>, parsed and defaulted in
 * simtick.c; 1 = off). 1997 at 20 fps applied flame damage from the main pass AND the rear-mirror pass (40 updates a
 * second); the tick applies it once per tick. Each application's amount (record d[4], max(1, int(D x f x dt)): 1 at
 * 33.3 ms, 2 at 66.7 ms) is multiplied by the factor, the fraction carried per target (16 kept), so the factor is per unit
 * of damage and therefore per unit of sim time in both tick arms. Every stream goes through this site (0x4357c3 in
 * weapon_FlameHitTest), the AI's flamers included. Only under the tick (g_simtick): the 20 Hz grid and the stock loop
 * are untouched.
 * 2026-10-19 (tick42 lane, TICK-FINISH s.18): the factor is rate-aware by default (I76_SIM_TICK_FLAME_DMG unset or 'auto';
 * a number keeps the fixed factor above). The engine's amount per application is a = max(1, int(R x T)) (R = the flamer's
 * GDFC damage x the difficulty factor), so the tick's flame units per sim second, a / T, do not follow 1 / T: a Gas
 * Launcher (R 30) gets 30 / s at 33.3 and at 66.7 ms (a = 1, 2) but 24 / s at 41.667 ms (a = 1). Each application is now
 * scaled to what a 1997 pass at the reference frame (T_ref = 1 / I76_SIM_TICK_REF_HZ, 41.667 ms) computed, a_ref =
 * max(1, int(a x T_ref / T)), per sim second: factor = G x (a_ref / T_ref) / (a / T), G = I76_SIM_TICK_FLAME_DMG_REF
 * (default 3.5, the car calibration: = 2.8 at 33.3 and 66.7 ms for the Gas Launcher, s.12; 3.5 at 41.667 ms). a_ref from
 * a alone equals int(R x T_ref) for every stock flamer and difficulty (R 11.25 .. 120) at 33.3, 41.667 and 66.7 ms. */
static float flame_dmg_factor(DWORD a) {
    int ar;
    if (!g_st_flame_auto) return g_st_flame_dmg;
    ar = (int)((float)a * g_st_flame_k + 0.001f); if (ar < 1) ar = 1;
    return g_st_flame_ref * (float)ar / ((float)a * g_st_flame_k);
}
static struct { DWORD tgt; float carry; } g_fdc[16]; static int g_fdc_next;
static DWORD flame_dmg_scale(DWORD target, DWORD a) {
    float x; int i; DWORD n;
    if (a == 0 || a > 100000) return a;                     /* not an integer amount: as stock */
    for (i = 0; i < 16; i++) if (g_fdc[i].tgt == target) break;
    if (i == 16) { i = g_fdc_next; g_fdc_next = (g_fdc_next + 1) & 15; g_fdc[i].tgt = target; g_fdc[i].carry = 0.0f; }
    x = (float)a * flame_dmg_factor(a) + g_fdc[i].carry;
    n = (DWORD)x; g_fdc[i].carry = x - (float)n;
    g_fdc_in += a; g_fdc_out += n;
    return n;
}
static void __cdecl flame_damage_wrap(DWORD target, dmgrec_t rec, DWORD extra) {
    g_idbg_flame_hits++;
    if (g_flc_on) g_flc_hits++;
    if (!g_flame_dmg_ok) return;
    if (g_simtick && (g_st_flame_auto || g_st_flame_dmg != 1.0f)) { DWORD n = flame_dmg_scale(target, rec.d[4]); if (!n) return; rec.d[4] = n; }
    g_idbg_flame_dmg++;
    if (g_flc_on) flame_census_note(&rec);
    ((void (__cdecl *)(DWORD, dmgrec_t, DWORD))(DWORD_PTR)NA(0x004a8240))(target, rec, extra);
}
static void __cdecl flame_expl_count(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g) {   /* stock loop: count, spawn as stock */
    g_flc_expl++;
    ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))0x0049ead0)(a, b, c, d, e, f, g);
}
static void __cdecl flame_census_wrap(DWORD target, dmgrec_t rec, DWORD extra) {   /* stock frame loop: count, then apply as stock */
    g_flc_hits++;
    flame_census_note(&rec);
    ((void (__cdecl *)(DWORD, dmgrec_t, DWORD))0x004a8240)(target, rec, extra);
}

/* The flame-hit explosion (entity_SpawnExplosion 0x49ead0 from 0x44471d: the ORDF car-impact xdf, xflht1 for stock
 * flamers, blast damage 0) is spawned on every update call that has a contact, the mirror pass included: held to the
 * same main-pass grid frames as the damage. 7 dword arguments, result unused. */
static void __cdecl flame_expl_wrap(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g) {
    if (g_flame_dmg_ok) g_flc_expl++; else g_flc_expl_blk++;
    if (g_flame_dmg_ok)
        ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))(DWORD_PTR)NA(0x0049ead0))(a, b, c, d, e, f, g);
}

/* AI fire decisions (i76-map subsystems/ai.md, weapons.md). Every frame each AI car's behaviour calls ai_FireWeapons
 * 0x414ef0, which asks ai_ShouldFireWeapon 0x418200 for each weapon and pulls its trigger for that frame when the
 * answer is yes; turrets (entity_TickTurretFire 0x462a90) do the same. The answer includes a random gate per call:
 * class 4 (rockets, missiles) passes with p = 0.2 x skill^2, mortars when rand%1000 + rand%1000 < 3500 x skill, guns
 * when three such draws sum below 6000 x skill. So at 60 fps the gate is rolled 3x as often and a weapon that passes
 * rarely fires up to 3x as often (bounded by its refire time). Decisions are now made on grid frames and held for the
 * 20 Hz window, keyed by the weapon's AI record (arg 7), as a 50 ms stock frame holds them. I76_AI_FIRE_CACHE=0 keeps
 * the counters but passes every call through (for measuring stock behaviour). */
typedef struct { void *key; DWORD tick; int res; } aifire_t;
static aifire_t g_aifire[1024];
static int g_aifire_cache = 1;
static DWORD g_idbg_aifire_calls, g_idbg_aifire_yes;
static int __cdecl ai_fire_wrap(DWORD a, DWORD b, float c, float d, DWORD e, DWORD f, int *rec, DWORD h) {
    unsigned i = (unsigned)(((DWORD)(DWORD_PTR)rec >> 2) & 1023), n;
    int r;
    if (g_aifire_cache && !g_tickai) {
        for (n = 0; n < 1024; n++, i = (i + 1) & 1023) {
            if (g_aifire[i].key == rec) return g_aifire[i].tick == g_tickai_n ? g_aifire[i].res : 0;
            if (!g_aifire[i].key) break;
        }
        return 0;                                           /* not decided in this window */
    }
    r = ((int (__cdecl *)(DWORD, DWORD, float, float, DWORD, DWORD, int *, DWORD))0x00418200)(a, b, c, d, e, f, rec, h);
    g_idbg_aifire_calls++; if (r) g_idbg_aifire_yes++;
    if (g_aifire_cache) {
        for (n = 0; n < 1024; n++, i = (i + 1) & 1023)
            if (g_aifire[i].key == rec || !g_aifire[i].key) { g_aifire[i].key = rec; g_aifire[i].tick = g_tickai_n; g_aifire[i].res = r; break; }
    }
    return r;
}

/* HUD ammo digits (weapon_HudRollAmmoDigits 0x4a4e40, from weapon_Update at 0x4a44ca with force = 0): each call rolls a
 * digit strip one step toward the new count (0x4a4eda), so a full roll takes 0.45 s at 20 fps and 0.15 s at 60. The
 * panel is persistent (a matching digit returns without drawing), so skipping the call between grid frames just
 * steps the roll at 20 Hz. */
static void __cdecl ammo_roll_wrap(DWORD a, DWORD b, DWORD c, DWORD d) {
    if (g_tick20 || d) ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD))0x004a4e40)(a, b, c, d);
}

/* Smoke puffs (renderer_UpdateSmoke 0x4414a0, once per render). Each call spawns every emitter's puffs, draws the
 * live ones, moves them by dt and ages them one step; a puff lives 20 calls. At 60 fps that is 3x the puffs, each
 * living a third as long: the same count on screen but columns a third as tall, with the drift table stepping 3x as
 * fast. The update now runs on grid frames only, with dt max(dt, 0.05); between them the live puffs are drawn
 * (renderer_QueueSmokePuff 0x441930) at their position extrapolated along their velocity, so motion stays smooth. */
static void __cdecl smoke_update_wrap(BYTE *cam) {
    BYTE *p; double save[3]; float t; int k;
    if (g_tick20) { ((void (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x004414a0))(cam); return; }
    if (!*(volatile int *)(DWORD_PTR)NA(0x0052ba34)) return;
    t = g_acc20 - g_ref_dt;                                 /* the update draws before it moves: last tick drew P0 */
    if (t > 0.0f) t = 0.0f; if (t < -g_ref_dt) t = -g_ref_dt;
    for (p = *(BYTE **)(DWORD_PTR)NA(0x0052ba30); p; p = *(BYTE **)(p + 0x40)) {
        if (*(int *)(p + 4) >= 20) continue;                /* expired: freed on the next grid frame, not drawn */
        memcpy(save, p + 0x28, sizeof(save));
        for (k = 0; k < 3; k++) ((double *)(p + 0x28))[k] = save[k] + (double)(((float *)(p + 0x10))[k] * t);
        ((void (__cdecl *)(BYTE *, BYTE *))(DWORD_PTR)NA(0x00441930))(cam, p);
        memcpy(p + 0x28, save, sizeof(save));
    }
}

/* Missile smoke trails (renderer_QueueSmokeTrails 0x442ba0, once per render): in a trail's last 2 s each call drops up
 * to 4 tail segments (0x442bd6), so at 60 fps trails vanish 3x as fast. Between grid frames a trail inside that window
 * gets its expiry (+0xc) moved just past now + 2 for the duration of the call, then restored. */
static void __cdecl trails_wrap(BYTE *cam) {
    BYTE *head = *(BYTE **)(DWORD_PTR)NA(0x0052bae8), *r;
    float saved[256]; int n = 0;
    if (!g_tick20 && head) {
        float now = ((float (__cdecl *)(void))(DWORD_PTR)NA(0x0049c8c0))(), lim = now + 2.0f;
        lim += lim * 1e-6f;
        r = head;
        do {
            float *e = (float *)(r + 0xc);
            if (n < 256) { saved[n++] = *e; if (*e >= now && *e < lim) *e = lim; }
            r = *(BYTE **)r;
        } while (r && r != head);
    }
    ((void (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x00442ba0))(cam);
    if (n) {
        int i = 0;
        r = head;
        do { if (i < n) *(float *)(r + 0xc) = saved[i++]; r = *(BYTE **)r; } while (r && r != head && i < n);
    }
}

static void apply_framerate_fixes(void) {
    static const BYTE cu_old[6] = { 0xD9, 0x05, 0xC4, 0xC4, 0x4B, 0x00 };   /* fld dword ptr [0x4bc4c4] */
    static const BYTE cv_old[6] = { 0xD9, 0x05, 0x00, 0xC5, 0x4B, 0x00 };   /* fld dword ptr [0x4bc500] */
    static const BYTE fl_old[6] = { 0xD8, 0x0D, 0x28, 0xC5, 0x4B, 0x00 };   /* fmul dword ptr [0x4bc528] */
    static const DWORD fl_sites[4] = { 0x00405bd0, 0x00405c1c, 0x004061e7, 0x00406233 };
    BYTE cu_new[6] = { 0xD9, 0x05 }, cv_new[6] = { 0xD9, 0x05 }, fl_new[6] = { 0xD8, 0x0D };
    DWORD a; int i, n = 0;
    if (!env_present("I76_FRAMERATE_FIXES")) return;
    install_frame_hook();
    if (!g_frame_hook) { mlog("  framerate-fixes: frame hook missing - not applied"); return; }
    a = (DWORD)(DWORD_PTR)&g_cloud_u; memcpy(cu_new + 2, &a, 4);
    a = (DWORD)(DWORD_PTR)&g_cloud_v; memcpy(cv_new + 2, &a, 4);
    a = (DWORD)(DWORD_PTR)&g_cam_rate; memcpy(fl_new + 2, &a, 4);
    n += patch_bytes(0x00405461, cu_old, cu_new, 6, "cloud scroll u");
    n += patch_bytes(0x00405484, cv_old, cv_new, 6, "cloud scroll v");
    for (i = 0; i < 4; i++) n += patch_bytes(fl_sites[i], fl_old, fl_new, 6, "free-look rate");
    {
        static const BYTE zm_old[6] = { 0xD8, 0x0D, 0xAC, 0xC5, 0x4B, 0x00 };   /* fmul dword ptr [0x4bc5ac] (-0.01) */
        BYTE zm_new[6] = { 0xD8, 0x0D };
        a = (DWORD)(DWORD_PTR)&g_zoom_rate; memcpy(zm_new + 2, &a, 4);
        n += patch_bytes(0x00408a3f, zm_old, zm_new, 6, "zoom rate");
    }
    {
        static const BYTE tu_old[6] = { 0xD8, 0x0D, 0xF4, 0xD8, 0x4B, 0x00 };   /* fmul dword ptr [0x4bd8f4] (-0.4) */
        static const BYTE td_old[6] = { 0xD8, 0x0D, 0xF8, 0xD8, 0x4B, 0x00 };   /* fmul dword ptr [0x4bd8f8] (0.5) */
        BYTE tu_new[6] = { 0xD8, 0x0D }, td_new[6] = { 0xD8, 0x0D };
        a = (DWORD)(DWORD_PTR)&g_thr_up; memcpy(tu_new + 2, &a, 4);
        a = (DWORD)(DWORD_PTR)&g_thr_dn; memcpy(td_new + 2, &a, 4);
        n += patch_bytes(0x0044f306, tu_old, tu_new, 6, "throttle-up ramp");
        n += patch_bytes(0x0044f366, td_old, td_new, 6, "throttle-down ramp");
    }
    {
        static const BYTE l3_old[5] = { 0xE8, 0xCD, 0xF1, 0xF7, 0xFF };   /* call 0x423230 at 0x4a405e (msllock3) */
        static const BYTE l12_old[5] = { 0xE8, 0x7E, 0xF1, 0xF7, 0xFF };  /* call 0x423230 at 0x4a40ad (msllock1/2) */
        BYTE l_new[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)frame_sound_wrap - (0x004a405e + 5)); memcpy(l_new + 1, &rel, 4);
        n += patch_bytes(0x004a405e, l3_old, l_new, 5, "missile lock tone 3");
        rel = (LONG)((DWORD_PTR)frame_sound_wrap - (0x004a40ad + 5)); memcpy(l_new + 1, &rel, 4);
        n += patch_bytes(0x004a40ad, l12_old, l_new, 5, "missile lock tones 1/2");
    }
    {
        static const BYTE a1_old[5] = { 0xE8, 0x96, 0xCD, 0x08, 0x00 };   /* call simclock_GetSimRate at 0x40fa15 */
        static const BYTE a2_old[5] = { 0xE8, 0x1E, 0xCD, 0x08, 0x00 };   /* call simclock_GetSimRate at 0x40fa8d */
        BYTE a_new[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)ai_gain_rate - (0x0040fa15 + 5)); memcpy(a_new + 1, &rel, 4);
        n += patch_bytes(0x0040fa15, a1_old, a_new, 5, "AI throttle gain (type 9)");
        rel = (LONG)((DWORD_PTR)ai_gain_rate - (0x0040fa8d + 5)); memcpy(a_new + 1, &rel, 4);
        n += patch_bytes(0x0040fa8d, a2_old, a_new, 5, "AI throttle gain (vehicles)");
        {
            static const BYTE s_old[5] = { 0xE8, 0xC2, 0xC8, 0x08, 0x00 };  /* call simclock_GetSimDt at 0x40fed9 */
            BYTE s_new[5] = { 0xE8 };
            rel = (LONG)((DWORD_PTR)ai_gain_dt - (0x0040fed9 + 5)); memcpy(s_new + 1, &rel, 4);
            n += patch_bytes(0x0040fed9, s_old, s_new, 5, "AI steering gain");
        }
    }
    {
        static const BYTE p1_old[5] = { 0xE8, 0xFD, 0x4A, 0xFC, 0xFF };   /* call 0x4250f0 at 0x4605ee (CRADAR.WAV) */
        static const BYTE p2_old[5] = { 0xE8, 0xFA, 0x47, 0xFC, 0xFF };   /* call 0x4250f0 at 0x4608f1 (CRADAR.WAV) */
        BYTE p_new[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)radar_ping_wrap - (0x004605ee + 5)); memcpy(p_new + 1, &rel, 4);
        n += patch_bytes(0x004605ee, p1_old, p_new, 5, "radar ping");
        rel = (LONG)((DWORD_PTR)radar_ping_wrap - (0x004608f1 + 5)); memcpy(p_new + 1, &rel, 4);
        n += patch_bytes(0x004608f1, p2_old, p_new, 5, "radar ping (2)");
    }
    {   /* 0x43d500, once per frame per vehicle: skid/turn/surface (x2), flat tyre, damage - each `call 0x423230` */
        static const DWORD site[4] = { 0x0043d54d, 0x0043d590, 0x0043d5ec, 0x0043d62b };
        static const BYTE old_rel[4][4] = { { 0xDE, 0x5C, 0xFE, 0xFF }, { 0x9B, 0x5C, 0xFE, 0xFF },
                                            { 0x3F, 0x5C, 0xFE, 0xFF }, { 0x00, 0x5C, 0xFE, 0xFF } };
        for (i = 0; i < 4; i++) {
            BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
            LONG rel = (LONG)((DWORD_PTR)frame_sound_wrap - (site[i] + 5));
            memcpy(o + 1, old_rel[i], 4); memcpy(w + 1, &rel, 4);
            n += patch_bytes(site[i], o, w, 5, "vehicle per-frame sound");
        }
    }
    {   /* flamers, smoke puffs, missile trails: `call` sites repointed at the wrappers above */
        static const struct { DWORD site, target; void *wrap; const char *what; } cs[] = {
            { 0x00401cec, 0x00443e90, (void *)flame_age_wrap,    "flamer ageing (software)" },
            { 0x00401fcc, 0x00443e90, (void *)flame_age_wrap,    "flamer ageing (hardware)" },
            { 0x00401e23, 0x00443fc0, (void *)flame_update_main, "flamer update, main pass (software)" },
            { 0x004020e8, 0x00443fc0, (void *)flame_update_main, "flamer update, main pass (hardware)" },
            { 0x00443fca, 0x0049c8b0, (void *)step20_dt,         "flamer update dt" },
            { 0x004357c3, 0x004a8240, (void *)flame_damage_wrap, "flamer damage" },
            { 0x0044471d, 0x0049ead0, (void *)flame_expl_wrap,   "flamer hit explosion" },
            { 0x00414f75, 0x00418200, (void *)ai_fire_wrap,      "AI fire decision (vehicles)" },
            { 0x00462bfb, 0x00418200, (void *)ai_fire_wrap,      "AI fire decision (turrets)" },
            { 0x00462c3e, 0x00418200, (void *)ai_fire_wrap,      "AI fire decision (turrets, 2)" },
            { 0x004a44ca, 0x004a4e40, (void *)ammo_roll_wrap,    "HUD ammo digit roll" },
            { 0x00401e50, 0x004414a0, (void *)smoke_update_wrap, "smoke puffs (software)" },
            { 0x0040211a, 0x004414a0, (void *)smoke_update_wrap, "smoke puffs (hardware)" },
            { 0x004414b9, 0x0049c8b0, (void *)step20_dt,         "smoke puff dt" },
            { 0x00401e35, 0x00442ba0, (void *)trails_wrap,       "missile trails (software)" },
            { 0x004020ff, 0x00442ba0, (void *)trails_wrap,       "missile trails (hardware)" },
        };
        for (i = 0; i < (int)(sizeof(cs) / sizeof(cs[0])); i++) {
            BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
            LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
            memcpy(o + 1, &rel, 4);
            rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
            n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
        }
    }
    if (env_flag("I76_AI_FIRE_CACHE", 8, 1) == 0) g_aifire_cache = 0;
    {   /* I76_AI_GRID_HZ (beside g_tick20_n): the held AI decisions on another grid rate */
        char v[16];
        if (env_str("I76_AI_GRID_HZ", v, sizeof(v))) {
            float hz = (float)atof(v);
            if (hz >= 5.0f && hz <= 200.0f) { g_ai_hz = hz; mlog("  ai-grid-hz: held AI decisions (fire, dodge, skid / horn rolls) on a %.1f Hz grid (default 20)", hz); }
            else mlog("  ai-grid-hz: '%s' is not 5..200 - the 20 Hz grid kept", v);
        }
    }
    g_ratefix = 1;
    {   /* I76_AI_STOCK_CLOCK (above ai_gain_rate): the gain sites see the 1997 GetTickCount frame clock's dt ratio */
        char v[16];
        if (env_str("I76_AI_STOCK_CLOCK", v, sizeof(v)) && v[0] != '0') {
            double ms = atof(v);
            if (ms >= 1.5 && ms <= 100.0) g_ai_tick = ms / 1000.0;
            if (g_fixed_step > 0.0f) {
                g_ai_stockclk = (v[0] == 's' || v[0] == 'S') ? 2 : 1;   /* "steer": the steering site only (lab A/B) */
                {   /* I76_AI_STOCK_CLOCK_FPS=<fps>: the 1997 frame rate whose clock is emulated (default: the fixed step rate) */
                    char f[16];
                    if (env_str("I76_AI_STOCK_CLOCK_FPS", f, sizeof(f)) && atof(f) >= 5.0 && atof(f) <= 200.0) {
                        g_ai_frame = 1.0 / atof(f);
                        mlog("  ai-stock-clock: emulated frame %.2f ms (%.1f fps)", g_ai_frame * 1000.0, atof(f));
                    }
                }
                mlog("  ai-stock-clock: AI throttle / steering gains on the stock frame clock (tick %.3f ms, step %.2f ms: dt ratio cycle as a GetTickCount game at %.1f fps)",
                     g_ai_tick * 1000.0, g_fixed_step * 1000.0f, g_ai_frame > 0.0 ? 1.0 / g_ai_frame : 1.0 / (double)g_fixed_step);
            } else mlog("  ai-stock-clock: needs I76_FIXED_STEP - not applied");
        }
    }
    mlog("  framerate-fixes: %d/36 sites repointed (clouds, free-look keys, zoom key, throttle keys, lock tones, radar ping, vehicle sounds, AI throttle + steering gain, flamers, smoke puffs, missile trails, AI fire decisions, ammo digits)", n);
}

/* ===========================================================================
 * AI DODGE GATE + AVOIDANCE HORIZON  (I76_AI_FIXES=1; off by default)
 * ===========================================================================
 * Kept out of I76_FRAMERATE_FIXES on purpose so each can be A/B'd against the recommended set
 * (docs/records/FRAMERATE-COVERAGE-2026-10-02.md P2 / P3, both unmeasured static readings).
 *
 * P2, AI dodge checks (ai_TestControlCandidate 0x41b270, i76-map subsystems/ai.md 7). Each avoidance candidate (14 call
 * sites, several per car per frame) rolls rand() % 1000 against 850 + 150 x (1 - skill) (0x41b651-0x41b692: constants
 * 0x4bc91c = 1, 0x4bca70 = -150, 0x4bca74 = 850) and, on a pass (p = 0.15 x skill per call), runs the incoming-projectile
 * check ai_CheckIncomingProjectiles 0x41abf0 (sole caller 0x41b698: `push ebp; push ebx; push esi; push edi`, `add esp,
 * 0x10`, result tested in eax). Rolled once per frame per candidate, so at 60 fps the AI looks for projectiles to dodge
 * 3x as often per second as at stock 20 (6x at 120). Held to grid frames: between them the check reports "nothing
 * incoming", as a frame that does not exist at 20 fps would. The roll itself still runs (rand() is consumed as before).
 * I76_AI_DODGE_HOLD=0 keeps the counters but passes every call through (for measuring stock behaviour), as
 * I76_AI_FIRE_CACHE=0 does for the fire gate.
 *
 * P3, AI avoidance horizon (ai.md 34-39). Each candidate control pair is tested by predicting ONE FRAME of motion
 * (physics_PredictVehicleMotion 0x43a560 reads sim_dt at 0x43a562) and probing terrain (0x419930, no clock read) at the
 * predicted pose, then sweeping cars (0x41a530) and static colliders (0x41a040) by a velocity rebuilt from that
 * displacement x sim_rate x 50 x gear (0x41b58f / 0x41b5ab, 0x41b5b0-0x41b5f5) over their own sim_dt (0x41a54e,
 * 0x41a047). The sweep lengths cancel; the horizon does not: 50 ms at 20 fps, 16.7 at 60, 8.3 at 120. All five reads
 * get the 20 fps values (ai_dt20 / ai_rate20 above), so the AI looks 50 ms ahead at any rate and the prediction, the
 * velocity derived from it and the probes' sweeps stay mutually consistent, as they are at stock 20 fps.
 */
static int g_dodge_hold = 1;
static DWORD g_idbg_dodge_calls, g_idbg_dodge_yes;         /* copied into the debug block by the render wrapper */
/* STATIONARY HAZARD CONTACT EFFECTS (part of I76_FRAMERATE_FIXES; found in play at 120 fps, 2026-10-02: "the oil
 * slick sound plays too fast"). The projectile update 0x4a0410 steps every live ordnance once per rendered frame.
 * The oil slick (weapon_StepOilSlick 0x4aa150) and the fire patch (weapon_StepFirePatch 0x4aa450) are stationary
 * probes: on every step with a vehicle in contact they call weapon impact 0x4a7190, which spawns the impact
 * template (entity_SpawnExplosion 0x49ead0) and its 3D sound (0x4232a0). So the effect, its sound and whatever the
 * template does fire once per FRAME in contact: 20 / s at stock 20 fps, 60 at 60, 120 at 120. The traction-loss
 * timer the oil starts (0x466e80, 2 s) is idempotent and stays per frame. Both call sites are held to the 20 Hz
 * grid, like the other per-frame starts here. Same bytes on the Galaxy and AiO exes. Static + field report; the
 * events/s measurement (telemetry EXPLOSION events parked on a slick at 20 / 60 / 120) is still to run. */
static DWORD g_idbg_hazard_calls;
static void __cdecl hazard_impact_wrap(DWORD a, DWORD b, DWORD c, DWORD d) {
    if (!g_tick20) return;
    g_idbg_hazard_calls++;
    ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD))0x004a7190)(a, b, c, d);
}
/* THE WHOLE STEP, not only its effect (docs/records/PER-FRAME-AUDIT-2026-10-03.md H1). The contact test of these probes is
 * physics_SweepSegment 0x435830 (0x435cc0 for the canister), and a hit there applies the ordnance's damage at once
 * (0x435c92 -> physics_ApplyCollisionDamage 0x4a7c80: weapon_BuildImpactDamage 0x4a76a0, the full per-shot amount,
 * no dt) before the step ever reaches the impact call above. So a car standing in a fire patch takes the Fire-Dropper's
 * damage once per FRAME: 20 hits/s at stock 20 fps, 60 at 60, 120 at 120; the wheel hazard (id 0xe, no stock weapon)
 * damages the nearest wheel the same way, and the oil slick restarts its traction-loss timer. The four stationary
 * steps are therefore called on grid frames only, from their call sites in weapon_StepProjectileByType 0x4a0800
 * (`push dt; push edi; call`, result in eax; all return 1: they die by life, which 0x4a0990 counts down by dt before
 * the step, untouched). A grid-frame step has to cover the time since the last one, as a 50 ms stock frame does: the
 * sweep reads the sim dt and rate itself (0x43583a / 0x435846), so both are set to the grid window for the call and
 * put back. The canister (id 0x16, no stock weapon) flies like a mortar until it lands (pd+0x48) and is only held
 * once it burns. */
static DWORD g_idbg_hazard_steps;
static DWORD hazard_step_call(DWORD fn, BYTE *proj, float dt) {
    volatile float *sim_dt = (volatile float *)(DWORD_PTR)NA(0x004fe420), *sim_rate = (volatile float *)(DWORD_PTR)NA(0x004fe424);
    float d0 = *sim_dt, r0 = *sim_rate, w = g_grid_win;
    DWORD r;
    if (w < d0) w = d0;
    if (w > 0.2f) w = 0.2f;                                 /* simclock's own dt clamp */
    *sim_dt = w; *sim_rate = 1.0f / w;
    g_idbg_hazard_steps++;
    r = ((DWORD (__cdecl *)(BYTE *, float))(DWORD_PTR)fn)(proj, dt);
    *sim_dt = d0; *sim_rate = r0;
    return r;
}
static DWORD __cdecl hazard_step_oil(BYTE *proj, float dt)   { return g_tick20 ? hazard_step_call(0x004aa150, proj, dt) : 1; }
static DWORD __cdecl hazard_step_wheel(BYTE *proj, float dt) { return g_tick20 ? hazard_step_call(0x004aa2d0, proj, dt) : 1; }
static DWORD __cdecl hazard_step_fire(BYTE *proj, float dt)  { return g_tick20 ? hazard_step_call(0x004aa450, proj, dt) : 1; }
static DWORD __cdecl hazard_step_canister(BYTE *proj, float dt) {
    BYTE *pd = *(BYTE **)(proj + 0x70);
    if (!pd || *(int *)(pd + 0x48) == 0)                    /* still in flight: a moving projectile, dt-driven */
        return ((DWORD (__cdecl *)(BYTE *, float))(DWORD_PTR)NA(0x004ac800))(proj, dt);
    return g_tick20 ? hazard_step_call(0x004ac800, proj, dt) : 1;
}
static void apply_hazard_fix(void) {
    static const struct { DWORD site, target; void *wrap; const char *what; } cs[6] = {
        { 0x004aa27f, 0x004a7190, (void *)hazard_impact_wrap,   "oil slick contact effect" },      /* E8 0C CF FF FF */
        { 0x004aa559, 0x004a7190, (void *)hazard_impact_wrap,   "fire patch contact effect" },     /* E8 32 CC FF FF */
        { 0x004a08ec, 0x004aa150, (void *)hazard_step_oil,      "oil slick step" },                /* E8 5F 98 00 00 */
        { 0x004a0900, 0x004aa2d0, (void *)hazard_step_wheel,    "wheel hazard step" },             /* E8 CB 99 00 00 */
        { 0x004a0914, 0x004aa450, (void *)hazard_step_fire,     "fire patch step" },               /* E8 37 9B 00 00 */
        { 0x004a0856, 0x004ac800, (void *)hazard_step_canister, "canister step (landed)" } };      /* E8 A5 BF 00 00 */
    int i, n = 0;
    if (!g_ratefix) return;
    for (i = 0; i < 6; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
    }
    mlog("  hazard-contact: %d/6 sites repointed (oil slick / fire patch / wheel hazard / landed canister: contact test, damage, effect and sound on the 20 Hz grid)", n);
}

/* ===========================================================================
 * MORE PER-FRAME ACTIONS  (part of I76_FRAMERATE_FIXES; docs/records/PER-FRAME-AUDIT-2026-10-03.md)
 * ===========================================================================
 * Found by the 2026-10-03 audit of everything that acts once per rendered frame (or once per projectile step, which
 * is the same thing: weapon_UpdateProjectiles 0x4a0410 steps each live ordnance once per frame). All static readings
 * of md5 9a232dcc, bytes identical on the AiO-based sandbox exe; none measured in game yet.
 *
 * R1, radar missile turn (weapon_StepRadarMissile 0x4aa9f0, ids 8: DrRadar, Cherub; its jammer-proof twin 0x4ab1c0,
 * id 0x14, no stock weapon). Each STEP, when dot(nose, target) < 0.998, the missile rotates about cross(nose, target)
 * by min(0.75 x |cross|, c), c = sin 3 / 15 / 20 deg for < 15 / 15-150 / > 150 m flown (0x4aabf1..0x4aac62: gain
 * 0x4bec24, limits 0x4bec2c / 0x4bec34 / 0x4bec38, used as radians), then `call math_MatrixFromAxisAngle
 * 0x494460(out, -angle, axis x, y, z)` at 0x4aaca0; the twin at 0x4ab400. Nothing scales it by dt: the
 * far limit is 392 deg/s at stock 20 fps, 1176 at 60, 2352 at 120, and the proportional part converges 3x / 6x as fast,
 * so radar missiles out-turn everything at high frame rates. The angle is rescaled at the call: a clamped angle (one
 * of the three constants) x k, k = min(dt x 20, 1); an unclamped one, which removes 0.75 of the error per stock
 * step, x (1 - 0.25^k) / 0.75, which removes 0.75 again over 1/k frames. At 20 fps and below both factors are 1.
 *
 * S1, dead-weapon click (weapon_ReadPlayerTrigger 0x4a5870): while fire is held on a weapon at 0 condition the
 * trigger is cleared and WMISS.WAV is requested through the one-shot 0x4250f0 at 0x4a5a0e on EVERY FRAME - the same
 * repeat-until-false shape as the lock tones. Requests between grid frames are dropped (the key is a level, the next
 * grid frame asks again).
 *
 * A1, AI skid-turn roll (ai_ShouldSkid 0x41f590, the transition test behaviour 5 dirt_brave -> 7 tactic_skid): the
 * first thing it does against a vehicle target is roll rand() % (8 + int((1 - skill) x 40)) == 0, skill = ai+0xa820
 * (0x41f5d4..0x41f600; 0x4bcae4 = 1, 0x4bcb64 = 40), once per frame, so the mean wait for a handbrake turn is 3x / 6x
 * shorter at 60 / 120 fps. A2, AI horn (ai_WillCollideOnPath 0x41d8b0, the 'avoid clsn' interrupt test): when the
 * avoidance probe finds a vehicle in the way, (rand() & 3) == 0 honks (0x41dacc -> sound_PlayHorn 0x424f10), per
 * frame. Both `call [rand]` (FF 15 0C C2 4B 00) are repointed at a function that rolls on grid frames and returns 1
 * (which fails both tests) between them. I76_AI_ROLL_HOLD=0 keeps the counters and rolls every frame (to measure
 * stock), as I76_AI_FIRE_CACHE=0 does for the fire gate.
 */
static DWORD g_idbg_radar_turns, g_idbg_wmiss_req, g_idbg_wmiss_play, g_idbg_skid_rolls, g_idbg_horn_rolls;
static void *__cdecl radar_turn_wrap(float *out, float angle, float x, float y, float z) {
    float a = angle < 0.0f ? -angle : angle;
    /* clamped: the angle is one of the three limit floats, loaded as-is (fld [limit]; fchs; fstp) - exact compare */
    int clamped = a == *(volatile float *)0x004bec2c || a == *(volatile float *)0x004bec34 || a == *(volatile float *)0x004bec38;
    g_idbg_radar_turns++;
    return ((void *(__cdecl *)(float *, float, float, float, float))0x00494460)(out, angle * (clamped ? g_turn_k : g_turn_g), x, y, z);
}
static int __cdecl wmiss_wrap(const char *name, BYTE *obj, int flag) {
    g_idbg_wmiss_req++;
    if (!g_tick20) return 0;
    g_idbg_wmiss_play++;
    return ((int (__cdecl *)(const char *, BYTE *, int))0x004250f0)(name, obj, flag);
}
static int g_ai_roll_hold = 1;
static int __cdecl ai_skid_rand(void) {
    if (g_ai_roll_hold && !g_tickai) return 1;
    g_idbg_skid_rolls++;
    return (*(int (__cdecl **)(void))0x004bc20c)();         /* the exe's own rand (MSVCRT import) */
}
static int __cdecl ai_horn_rand(void) {
    if (g_ai_roll_hold && !g_tickai) return 1;
    g_idbg_horn_rolls++;
    return (*(int (__cdecl **)(void))0x004bc20c)();
}
static void apply_perframe_fixes(void) {
    static const struct { DWORD site, target; void *wrap; const char *what; } cs[3] = {
        { 0x004aaca0, 0x00494460, (void *)radar_turn_wrap, "radar missile turn" },                  /* E8 BB 97 FE FF */
        { 0x004ab400, 0x00494460, (void *)radar_turn_wrap, "radar missile turn (id 0x14)" },        /* E8 5B 90 FE FF */
        { 0x004a5a0e, 0x004250f0, (void *)wmiss_wrap,      "dead-weapon click (WMISS.WAV)" } };     /* E8 DD F6 F7 FF */
    static const struct { DWORD site; void *wrap; const char *what; } rs[2] = {
        { 0x0041f5d4, (void *)ai_skid_rand, "AI skid-turn roll" },
        { 0x0041dacc, (void *)ai_horn_rand, "AI horn roll" } };
    static const BYTE rand_old[6] = { 0xFF, 0x15, 0x0C, 0xC2, 0x4B, 0x00 };   /* call dword ptr [0x4bc20c] (rand) */
    int i, n = 0;
    if (!g_ratefix) return;
    for (i = 0; i < 3; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
    }
    for (i = 0; i < 2; i++) {
        BYTE w[6] = { 0xE8, 0, 0, 0, 0, 0x90 };             /* call rel32; nop */
        LONG rel = (LONG)((DWORD_PTR)rs[i].wrap - (rs[i].site + 5));
        memcpy(w + 1, &rel, 4);
        n += patch_bytes(rs[i].site, rand_old, w, 6, rs[i].what);
    }
    if (env_flag("I76_AI_ROLL_HOLD", 8, 1) == 0) g_ai_roll_hold = 0;
    mlog("  perframe-fixes: %d/5 sites repointed (radar missile turn x2 scaled by dt x 20, WMISS click on the 20 Hz grid, AI skid-turn and horn rolls %s)",
         n, g_ai_roll_hold ? "held to the 20 Hz grid" : "counted, every frame");
}

static int __cdecl ai_dodge_wrap(DWORD a, DWORD b, DWORD c, DWORD d) {
    int r;
    if (g_dodge_hold && !g_tickai) return 0;
    r = ((int (__cdecl *)(DWORD, DWORD, DWORD, DWORD))0x0041abf0)(a, b, c, d);
    g_idbg_dodge_calls++; if (r) g_idbg_dodge_yes++;
    return r;
}
static void apply_ai_fixes(void) {
    static const struct { DWORD site, target; void *wrap; const char *what; } cs[] = {
        { 0x0041b698, 0x0041abf0, (void *)ai_dodge_wrap, "AI dodge check" },                 /* E8 53 F5 FF FF */
        { 0x0043a562, 0x0049c7a0, (void *)ai_dt20,       "AI avoidance prediction dt" },     /* E8 39 22 06 00 */
        { 0x0041b58f, 0x0049c7b0, (void *)ai_rate20,     "AI avoidance rate (cap test)" },   /* E8 1C 12 08 00 */
        { 0x0041b5ab, 0x0049c7b0, (void *)ai_rate20,     "AI avoidance rate" },              /* E8 00 12 08 00 */
        { 0x0041a54e, 0x0049c7a0, (void *)ai_dt20,       "AI car probe dt" },                /* E8 4D 22 08 00 */
        { 0x0041a047, 0x0049c7a0, (void *)ai_dt20,       "AI collider probe dt" },           /* E8 54 27 08 00 */
    };
    int i, n = 0, first = 0, last = (int)(sizeof(cs) / sizeof(cs[0]));
    char v[16];
    if (!env_present("I76_AI_FIXES")) return;
    /* 2026-10-13 (AI-COMBAT-PARITY): I76_AI_FIXES=dodge = the dodge hold only, =horizon = the five horizon pins only */
    env_str("I76_AI_FIXES", v, sizeof(v));
    if (v[0] == 'd' || v[0] == 'D') last = 1;
    if (v[0] == 'h' || v[0] == 'H') first = 1;
    if (!g_ratefix && first == 0) { mlog("  ai-fixes: dodge hold needs I76_FRAMERATE_FIXES (the 20 Hz grid) - horizon pins only"); first = 1; }
    for (i = first; i < last; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
    }
    if (env_flag("I76_AI_DODGE_HOLD", 8, 1) == 0) g_dodge_hold = 0;
    mlog("  ai-fixes: %d/%d sites repointed (dodge check %s, avoidance horizon %s)",
         n, last - first, first ? "skipped" : g_dodge_hold ? "held to the AI decision grid" : "counted, passed through",
         last > 1 ? "pinned to 50 ms: prediction dt, rate x2, probe dt x2" : "not pinned");
}

/* ===========================================================================
 * AI BACK_AWAY RING ON THE 20 Hz GRID  (I76_AI_BACKAWAY_GRID=1; off by default)
 * ===========================================================================
 * Lab doc 2026-10-04-milk-truck-opening-divergence.md sections 7-8. The back_away interrupt test 0x41d240 stores
 * ai_GripLimitedThrottle(e, 1.0) (0x43c600) into a 4-slot ring ai+0x9d58..+0x9d64 (all 1.0 at AI init, 0x415610)
 * indexed by `call 0x415600` at 0x41d286 (= `mov eax,[0x524550]`, the AI-pass stamp: inc once per AI/FSM pass at
 * 0x40a658, i.e. once per rendered frame) & 3, and pushes back_away (reverse, 4 s) when all four are < 0.1
 * ([0x4bcadc]). "Four frames below 0.1" is 200 ms at stock 20 fps but 33 ms at 120, less than one FIXED_STEP 24
 * physics step: an AI car that spawns unloaded on a slope (T12's speedy) reverses at 0.3-0.4 s and loops for the
 * rest of the minute (best-wide 0/5 shot cuts vs vanilla 7/7 at 6.6 s). The call is repointed at a stub that
 * returns round(sim time [0x5a7e70] x 20), a 20 Hz grid count: the ring then holds the last value of each of the
 * last four grid ticks (~150-200 ms) at any frame rate; at 20 fps and below one grid tick per frame = stock. The
 * index is used for nothing else (ring users: 0x415610 init, 0x41d29d store, 0x41d2a7..0x41d2e9 test).
 * Tested in-process first (probe -GridFix, same 6-instruction body): best-wide 5/5 cut at 6.6-6.7 s, 0 reverses.
 *
 * Audit of the other users of the stamp (2026-10-04, exe 6319abf7; all 8 `call 0x415600` and all 6 [0x524550]
 * references): fsm_isShot 0x40b410 / fsm_isRammed 0x40b800 / fsm_isAttacked 0x40b990 (calls 0x40b41e/42e,
 * 0x40b80e/81e, 0x40b99e/9ae) and the rammed terminator 0x41c2c0 (0x41c2d2) compare a stamp written by the
 * damage notifier 0x4157a0 (raw [0x524550] at 0x415830/0x415844/0x415855 -> ai+0xa6d8/+0xa6d4/+0xa6dc) with
 * "this pass or the last one" (the terminator: this pass), and the FSM edge reads consume the stamp. Writer and
 * readers count the same passes and the readers are polled every pass, so the catch is certain at any rate:
 * neutral, left alone (repointing only the readers would also compare frame stamps with grid counts). */
static float g_bag_k20 = 20.0f;
static __declspec(naked) void ai_backaway_grid_stub(void) {      /* replaces `call 0x415600` at 0x41d286 */
    __asm {                                     /* clobbers eax only (as the original); FPU stack balanced */
        push eax                                /* scratch slot */
        fld dword ptr ds:[0x005a7e70]           /* simclock sim time, s (0x49c7c0 reads the same float) */
        fmul g_bag_k20
        fistp dword ptr [esp]                   /* current rounding mode, as the in-process test's cave */
        pop eax
        ret
    }
}
/* ===========================================================================
 * AI TURRET FIRE ROLL ON THE DECISION GRID  (I76_AI_TURRET_HOLD=1, needs I76_FRAMERATE_FIXES; off by default)
 * ===========================================================================
 * entity_TickTurretFire 0x462a90: a turret with N > 1 (rec+0x50) first rolls rand() % (2N - 2) == 0 (0x462c0f) and
 * only then asks ai_ShouldFireWeapon (0x462c3e), whose answer I76_FRAMERATE_FIXES holds for the grid window. The outer
 * roll is not held: between grid frames a failed roll skips the held "yes", so the trigger is pulled for only part of
 * the window (N = 2: about 58 % of stock). The roll is made on decision-grid frames only and returns 0 (= pass)
 * between them, so the held decision (or "not decided in this window") stands for the whole window, as one stock
 * frame does. Static reading (lab doc AI-COMBAT-PARITY-2026-10-13.md). */
static DWORD g_idbg_turret_rolls;
static int __cdecl ai_turret_rand(void) {
    if (!g_tickai) return 0;
    g_idbg_turret_rolls++;
    return (*(int (__cdecl **)(void))0x004bc20c)();
}
static void apply_ai_turret_hold(void) {
    static const BYTE rand_old[6] = { 0xFF, 0x15, 0x0C, 0xC2, 0x4B, 0x00 };
    BYTE w[6] = { 0xE8, 0, 0, 0, 0, 0x90 };
    LONG rel = (LONG)((DWORD_PTR)ai_turret_rand - (0x00462c0f + 5));
    if (!env_present("I76_AI_TURRET_HOLD")) return;
    if (!g_ratefix) { mlog("  ai-turret-hold: needs I76_FRAMERATE_FIXES - not applied"); return; }
    memcpy(w + 1, &rel, 4);
    mlog("  ai-turret-hold: %d/1 turret outer fire roll on the AI decision grid",
         patch_bytes(0x00462c0f, rand_old, w, 6, "turret outer fire roll (turret hold)"));
}

/* ===========================================================================
 * AI THROTTLE EASE PER SECOND, NOT PER PASS  (I76_AI_THROTTLE_EASE=1; off by default)
 * ===========================================================================
 * ai_ThrottleUpBySkill 0x410170 (tactic_skid, dirt_standoff phase 1, avoid clsn below 10 m/s, rockford): every AI pass
 * eases the throttle toward the grip-limited full throttle, thr += s x (G - thr), s = ai+0xa81c, then caps it. Per
 * pass, not per second: at 120 fps under I76_FIXED_STEP=24 five passes compound before each step (1 - (1 - s)^5 of the
 * gap instead of s). The eight call sites (all `push obj; call 0x410170`) are repointed at a wrapper that lets the
 * function run and then scales the change it made by s_eff / s, s_eff = 1 - (1 - s)^(dt / T), dt = this frame's dt,
 * T = one decision-grid period (1 / I76_AI_GRID_HZ, 50 ms by default = stock 20 fps): the ease per second of the
 * reference frame rate. The result lies between the old and the new value, so the function's own cap still holds.
 * At the reference frame rate (dt = T) it is the stock function. Static reading (lab doc AI-COMBAT-PARITY-2026-10-13.md). */
static DWORD g_ease_calls;
static double pow01(double b, double x) {                   /* b^x for b in (0, 1], x in [0, 1]: binary digits of x by square roots (no CRT pow) */
    double r = 1.0, f = b; int k;
    for (k = 0; k < 24; k++) { f = sqrt(f); x *= 2.0; if (x >= 1.0) { r *= f; x -= 1.0; } }
    return r;
}
static void __cdecl ai_ease_wrap(BYTE *obj) {
    BYTE *e = obj ? *(BYTE **)(obj + 0x70) : 0, *ai;
    float before = 0.0f, s = 0.0f, dt, T;
    if (e) { before = *(float *)(e + 0xe4); ai = *(BYTE **)(e + 0x108); if (ai) s = *(float *)(ai + 0xa81c); }
    ((void (__cdecl *)(BYTE *))0x00410170)(obj);
    g_ease_calls++;
    dt = *(volatile float *)0x004fe428; T = 1.0f / g_ai_hz;
    if (e && s > 0.0f && s < 1.0f && dt > 0.0f && dt < T) {
        double se = 1.0 - pow01(1.0 - (double)s, (double)dt / (double)T);
        float after = *(float *)(e + 0xe4);
        *(float *)(e + 0xe4) = before + (after - before) * (float)(se / (double)s);
    }
}
static void apply_ai_throttle_ease(void) {
    static const DWORD site[8] = { 0x0041c733, 0x0041dbfe, 0x0041dcac, 0x0041de96, 0x0041df44, 0x0041e9e8, 0x0041ea79, 0x0041f847 };
    int i, n = 0;
    if (!env_present("I76_AI_THROTTLE_EASE")) return;
    for (i = 0; i < 8; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(0x00410170 - (site[i] + 5)); memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)ai_ease_wrap - (site[i] + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(site[i], o, w, 5, "ai_ThrottleUpBySkill call (throttle ease)");
    }
    mlog("  ai-throttle-ease: %d/8 ai_ThrottleUpBySkill calls eased per %.1f ms of frame time, not per pass", n, 1000.0f / g_ai_hz);
}

static int tel_repoint_call_early(DWORD site, DWORD target, void *wrap, const char *what) {   /* verify-first `call rel32` repoint */
    BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
    LONG rel = (LONG)(target - (site + 5));
    memcpy(o + 1, &rel, 4);
    rel = (LONG)((DWORD_PTR)wrap - (site + 5)); memcpy(w + 1, &rel, 4);
    return patch_bytes(site, o, w, 5, what);
}
/* ===========================================================================
 * AI PATH SEARCH SLICES ON THE DECISION GRID  (I76_AI_SEARCH_HOLD=1, needs I76_FRAMERATE_FIXES; off by default)
 * ===========================================================================
 * The route search (do search / evade / race and the 'handle too far search' a car enters when it is > 180 m from its
 * target) is time-sliced: ai_PathSearchStep 0x40f1e0, called once per AI pass from the search update 0x420d30
 * (0x420dd0, result -> ai+0x84, 1 = still searching), expands up to 100 nodes per call. Per pass, not per second: at
 * 120 fps a search completes in a sixth of the sim time it took at 20 fps, so cars re-engage from far away sooner.
 * The call is repointed at a wrapper that, on frames off the decision grid and while a search is in progress
 * (ai+0x84 == 1), skips the slice and reports "still searching"; on grid frames, or in any other state, it runs the
 * step. Static reading (audit item 6, lab doc AI-COMBAT-PARITY-2026-10-13.md). */
static DWORD g_search_steps, g_search_skips;
static int __cdecl ai_search_wrap(BYTE *ai, void *out, void *arg) {
    if (!g_tickai && ai && *(int *)(ai + 0x84) == 1) { g_search_skips++; return 1; }
    g_search_steps++;
    return ((int (__cdecl *)(BYTE *, void *, void *))0x0040f1e0)(ai, out, arg);
}
static void apply_ai_search_hold(void) {
    if (!env_present("I76_AI_SEARCH_HOLD")) return;
    if (!g_ratefix) { mlog("  ai-search-hold: needs I76_FRAMERATE_FIXES - not applied"); return; }
    mlog("  ai-search-hold: %d/1 path search slice on the AI decision grid",
         tel_repoint_call_early(0x00420dd0, 0x0040f1e0, (void *)ai_search_wrap, "path search step call (search hold)"));
}

/* ===========================================================================
 * AI HANDBRAKE TURN HELD TO A PHYSICS STEP  (I76_AI_SKID_HOLD=1, needs I76_FIXED_STEP; off by default)
 * ===========================================================================
 * Lab doc AI-COMBAT-PARITY-2026-10-13.md. tactic_skid (behaviour 7, the AI's handbrake turn, pushed by ai_ShouldSkid
 * 0x41f590): its enter 0x41f750 sets full lock and the handbrake (0x41f7b7 `mov [edx+0xf0], 1`) and a one-pass flag
 * ai+0xa97c; the update 0x41f7f0 clears the flag on the pass that entered and releases the handbrake on the NEXT AI
 * pass (0x41f839 `mov [ecx+0xf0], 0`). The physics reads +0xf0 only inside its substeps, and the AI pass runs after the
 * frame's steps, so the handbrake is seen by the steps of exactly one frame: one step in the 1997 game (every frame
 * steps), but at 120 fps under I76_FIXED_STEP=24 only one frame in five has a step: about 80 % of the AI's handbrake
 * turns never reach the physics and become a 0.5 s full-lock lunge on rolling wheels. Both writes are repointed at
 * stubs: the enter stamps the car with the count of frames that ran a fixed step; the release is skipped until a
 * step has run since then (so the handbrake is held for exactly one physics step, as stock). Without a fixed step
 * every frame steps and the stubs do what the instructions did. */
static struct { BYTE *e; DWORD stamp; float t; } g_skid_hb[64];   /* stamp = the car's own step count at the enter, t = sim time */
static DWORD g_skid_hb_enter, g_skid_hb_deferred;
static void __cdecl skid_hb_enter(BYTE *e) {
    int k, fr = -1;
    *(DWORD *)(e + 0xf0) = 1;
    g_skid_hb_enter++;
    for (k = 0; k < 64; k++) { if (g_skid_hb[k].e == e) { fr = k; break; } if (fr < 0 && !g_skid_hb[k].e) fr = k; }
    if (fr < 0) fr = (int)(((DWORD_PTR)e >> 4) & 63);
    g_skid_hb[fr].e = e; g_skid_hb[fr].stamp = vehicle_steps(e); g_skid_hb[fr].t = *(volatile float *)0x005a7e74;
}
static void __cdecl skid_hb_release(BYTE *e) {
    int k;
    for (k = 0; k < 64; k++) if (g_skid_hb[k].e == e) break;
    if (k < 64) {
        if (g_skid_hb[k].stamp == vehicle_steps(e) && g_fixed_step > 0.0f &&
            *(volatile float *)0x005a7e74 - g_skid_hb[k].t < 0.2f) { g_skid_hb_deferred++; return; }   /* this car has not stepped yet (bounded: a far car steps outside the stepper) */
        g_skid_hb[k].e = 0;
    }
    *(DWORD *)(e + 0xf0) = 0;
}
static void apply_ai_skid_hold(void) {
    static const BYTE en_old[10] = { 0xC7, 0x82, 0xF0, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00 };   /* 0x41f7b7 mov [edx+0xf0],1 */
    static const BYTE re_old[10] = { 0xC7, 0x81, 0xF0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };   /* 0x41f839 mov [ecx+0xf0],0 */
    BYTE en_new[10] = { 0x52, 0xE8, 0, 0, 0, 0, 0x83, 0xC4, 0x04, 0x90 };   /* push edx; call stub; add esp,4; nop */
    BYTE re_new[10] = { 0x51, 0xE8, 0, 0, 0, 0, 0x83, 0xC4, 0x04, 0x90 };   /* push ecx; call stub; add esp,4; nop */
    LONG rel; int n;
    if (!env_present("I76_AI_SKID_HOLD")) return;
    if (g_fixed_step <= 0.0f) { mlog("  ai-skid-hold: needs I76_FIXED_STEP - not applied"); return; }
    rel = (LONG)((DWORD_PTR)skid_hb_enter - (0x0041f7b8 + 5)); memcpy(en_new + 2, &rel, 4);
    rel = (LONG)((DWORD_PTR)skid_hb_release - (0x0041f83a + 5)); memcpy(re_new + 2, &rel, 4);
    n = patch_bytes(0x0041f7b7, en_old, en_new, 10, "tactic_skid handbrake on (skid hold)")
      + patch_bytes(0x0041f839, re_old, re_new, 10, "tactic_skid handbrake off (skid hold)");
    mlog("  ai-skid-hold: %d/2 sites (the AI handbrake turn's handbrake held until a physics step has seen it)", n);
}

static void apply_ai_backaway_grid(void) {
    static const BYTE old[5] = { 0xE8, 0x75, 0x83, 0xFF, 0xFF };   /* call 0x415600 at 0x41d286 */
    BYTE w[5] = { 0xE8 };
    LONG rel;
    char v[8]; DWORD k = env_str("I76_AI_BACKAWAY_GRID", v, sizeof(v));
    if (k == 0 || v[0] == '0') return;
    rel = (LONG)((DWORD_PTR)ai_backaway_grid_stub - (0x0041d286 + 5)); memcpy(w + 1, &rel, 4);
    if (patch_bytes(0x0041d286, old, w, 5, "AI back_away ring index")) {
        mlog("  ai-backaway-grid: back_away ring on the 20 Hz grid (0x41d286 -> sim time x 20; read back %s)",
             memcmp((void *)0x0041d286, w, 5) == 0 ? "ok" : "MISMATCH");
    } else {
        mlog("  ai-backaway-grid: NOT applied (0x41d286 bytes differ from E8 75 83 FF FF)");
    }
}

/* ===========================================================================
 * CO-OP DAMAGE FACTOR  (I76_COOP_DAMAGE=<factor>, e.g. 0.6; off by default; network games only)
 * ===========================================================================
 * The game's only difficulty lever is the player's own weapon damage (weapons.md): weapon_BuildImpactDamage 0x4a76a0
 * and the flamer hit 0x444384 load 2.0 / 1.0 / 0.75 by difficulty [0x654b9c] when the shooter is the player
 * (`call 0x458bf0`, objFlags bit 0x10) and the game is NOT a network game (`call 0x452d20`); a network game, or any
 * other shooter, gets the 1.0 kept in a stack slot ([esp+8] / [esp+0x11c] at the call). For co-op (docs/COOP-SPIKE.md)
 * both calls are repointed at both sites:
 *   - "is the shooter a human": the player flag, OR the car of any player in the network table 0x541070 (16 x 0x48,
 *     vehicle at +0x28), so a remote player's shots scale the same on every machine;
 *   - "is this a network game": unchanged answer, and when it is, the co-op factor is written into the caller's 1.0 slot
 *     first, which the network path then loads. Offline nothing changes (the difficulty table is used as stock).
 * 0.5 makes two players together as strong as one on Normal; 0.6 is 1.2x. Read from the 2019 AiO exe (60abf7bc base).
 * With I76_FPS_LOG on, the log line after each fps line counts the scaled hits (and those credited to a remote
 * player's car through the network table), the in-game evidence that the factor is being applied.
 * MEASURED 2026-10-06 (docs/COOP-SPIKE.md "Measured"): IPX game, PC host + Mac joiner, arena M01 cut to two spawns with a
 * parked tractor / bus 20 m ahead of each, 3 s of 50 cal (hardpoint 1), armour read in the host's memory. Per hit:
 * host's own shots 25.0 stock -> 12.0 at 0.5 (725 vs 348 over 29 hits, twice, identical); the Mac's shots on the host
 * 12.0 at 0.5 (516 / 43 hits, all 43 credited through the network table). 25 x 0.5 = 12.5 is truncated to 12. */
static DWORD g_coop_dmg_bits;                               /* the factor as float bits, written into the caller's slot */
static int __cdecl coop_is_human(BYTE *obj) {               /* replaces `call 0x458bf0` (cdecl, 1 arg) at both sites */
    int i;
    if (!obj) return 0;
    if (obj[0x10] & 0x10) return 1;
    for (i = 0; i < 16; i++) {
        BYTE *p = (BYTE *)0x00541070 + i * 0x48;
        if (*(WORD *)p && *(BYTE **)(p + 0x28) == obj) { if (*(volatile int *)0x00541030) g_coop_remote++; return 1; }
    }
    return 0;
}
static __declspec(naked) void coop_net_impact_stub(void) {  /* replaces `call 0x452d20` at 0x4a76d1 */
    __asm {
        mov eax, 0x00452d20
        call eax                                /* net_IsNetworkGame */
        test eax, eax
        jz done
        mov ecx, g_coop_dmg_bits
        mov [esp + 0xC], ecx                    /* caller's [esp+8]: the 1.0 the network path loads */
        inc g_coop_hits_impact
    done:
        ret
    }
}
static __declspec(naked) void coop_net_flame_stub(void) {   /* replaces `call 0x452d20` at 0x44439f */
    __asm {
        mov eax, 0x00452d20
        call eax
        test eax, eax
        jz done
        mov ecx, g_coop_dmg_bits
        mov [esp + 0x120], ecx                  /* caller's [esp+0x11c] */
        inc g_coop_hits_flame
    done:
        ret
    }
}
/* FFB GUARD (I76_FFB_GUARD; default on with I76_COOP_AI=1, the LAN preset, off otherwise until a promotion decides). ffb_PlayEffect 0x446110 calls I7FF_SIM_Effect ([0x52bbe4], resolved whenever
 * I7_SFRCE.DLL loads) without asking whether I7FF_InitSystem opened a device ([0x52bbd0], 0 = "Failed to open FF Joystick").
 * With no device the DLL dereferences its never-created effect object: 0xC0000005 at I7_SFRCE.DLL+0x2505 read 0 (the
 * 2026-08-02 field case, records/FFB-LAPTOP-RECON.md; and a lab LAN host on 2026-10-24 when its car fired, stack 0x4f2328 +
 * return 0x446130, records/LAN-FIXES-2026-10-24.md s.6). The function's first instruction `mov eax, [0x52bbe4]` becomes a
 * call that returns that pointer only while the device flag is set, so the function's own `test eax, eax; je` skips the
 * effect (and returns success) on a machine without a force-feedback device. With a device nothing changes. */
static __declspec(naked) void ffb_guard_stub(void) {
    __asm {
        mov eax, dword ptr ds:[0x0052bbd0]
        test eax, eax
        jz none
        mov eax, dword ptr ds:[0x0052bbe4]
    none:
        ret
    }
}
static void apply_ffb_guard(void) {
    BYTE old[5] = { 0xA1, 0xE4, 0xBB, 0x52, 0x00 }, w[5] = { 0xE8 }; LONG r = (LONG)((DWORD_PTR)ffb_guard_stub - (0x00446110 + 5));
    char v[8]; int lan = env_str("I76_COOP_AI", v, sizeof(v)) && v[0] == '1';   /* default on in the LAN preset only (I76_COOP_AI=1) */
    if (env_flag("I76_FFB_GUARD", 8, lan) != 1) { mlog("  ffb-guard: off (I76_FFB_GUARD=0, or not a LAN launch)"); return; }
    memcpy(w + 1, &r, 4);
    mlog("  ffb-guard: ffb_PlayEffect 0x446110 %s (I7FF_SIM_Effect only while I7FF_InitSystem has a device)",
         patch_bytes(0x00446110, old, w, 5, "ffb-guard") ? "guarded" : "NOT guarded (bytes differ)");
}
/* CO-OP SCRIPT GUARD (I76_COOP_SCRIPT_GUARD, default 1 with I76_COOP_CHAIN; records/LAN-FIXES-2026-10-24.md s.6).
 * The owner's host-death crashes (family pack, 2026-10-24): host i76.exe+0x684BD read 0x30 (esi 0), joiner +0xB902 read
 * 0x40 and +0x9D8D0 read 0x40 (eax 0); the lab (family source d249380, after a host migration and a host death) host and
 * joiner both at +0x94DB5 read 0x18 from 0x49d5f0. All four are the mission script's actions (the FSM dispatcher 0x412ce0):
 * every entity argument is re-resolved through 0x45f0f0, which gives NULL once the object it names is gone (a player car
 * the network code removed: the host's own car on a respawn, the old host's car on a migration), and the action
 * functions use it unchecked: 0x40b8e0 / 0x40b940 (is within distance / box of a path point), 0x49d5f0 / 0x49d740 (the
 * script camera on an object), 0x468440 (an object's world position, cached). Each of these gets an entry check: a NULL
 * object argument returns 0 (0x468440: its output vector zeroed and returned) instead of reading page 0. The script then
 * runs on: the mission's own "player is dead / gone" rule fails it and the chain reloads the scene for everybody. */
static void *g_csg_mem; static volatile LONG g_csg_hits[5];
static int csg_one(int k, DWORD fn, const BYTE *exp_, int n, const int *chk, int nchk, int zero_out) {
    BYTE *s = (BYTE *)g_csg_mem + k * 96, *p = s, w[16]; int i; LONG rel; DWORD op;
    if (memcmp((void *)fn, exp_, n) != 0) return 0;          /* no counter on the fast path: only on a skip */
    for (i = 0; i < nchk; i++) {                             /* cmp dword [esp+k], 0 ; je skip */
        *p++ = 0x83; *p++ = 0x7C; *p++ = 0x24; *p++ = (BYTE)chk[i]; *p++ = 0x00;
        *p++ = 0x0F; *p++ = 0x84; *(DWORD *)p = 0; p += 4;   /* patched to skip below */
    }
    memcpy(p, exp_, n); p += n;                              /* the relocated instructions (position independent) */
    *p++ = 0xE9; rel = (LONG)((fn + n) - ((DWORD)(DWORD_PTR)p + 4)); memcpy(p, &rel, 4); p += 4;
    {   BYTE *skip = p, *q = s; int j;
        for (j = 0; j < nchk; j++) { q += 5; q += 2; rel = (LONG)(skip - (q + 4)); memcpy(q, &rel, 4); q += 4; }
        *p++ = 0xF0; *p++ = 0xFF; *p++ = 0x05; *(DWORD *)p = (DWORD)(DWORD_PTR)&g_csg_hits[k]; p += 4;   /* lock inc [hits] */
        if (zero_out) {                                      /* mov eax,[esp+4]; mov [eax],0; [eax+4],0; [eax+8],0 */
            static const BYTE z[] = { 0x8B, 0x44, 0x24, 0x04, 0xC7, 0x00, 0, 0, 0, 0, 0xC7, 0x40, 0x04, 0, 0, 0, 0, 0xC7, 0x40, 0x08, 0, 0, 0, 0 };
            memcpy(p, z, sizeof z); p += sizeof z;
        } else { *p++ = 0x31; *p++ = 0xC0; }                 /* xor eax, eax */
        *p++ = 0xC3;
    }
    memset(w, 0x90, sizeof w); w[0] = 0xE9; rel = (LONG)((DWORD)(DWORD_PTR)s - (fn + 5)); memcpy(w + 1, &rel, 4);
    if (!VirtualProtect((void *)fn, n, PAGE_EXECUTE_READWRITE, &op)) return 0;
    memcpy((void *)fn, w, n); VirtualProtect((void *)fn, n, op, &op); FlushInstructionCache(GetCurrentProcess(), (void *)fn, n);
    return memcmp((void *)fn, w, n) == 0;
}
static void apply_coop_script_guard(void) {
    static const BYTE e0[] = { 0x83, 0xEC, 0x08, 0x8B, 0x44, 0x24, 0x0C };                  /* 0x40b8e0 */
    static const BYTE e1[] = { 0x8B, 0x44, 0x24, 0x04, 0x8B, 0x4C, 0x24, 0x08 };            /* 0x40b940 */
    static const BYTE e2[] = { 0x81, 0xEC, 0x9C, 0x00, 0x00, 0x00 };                        /* 0x49d5f0 */
    static const BYTE e3[] = { 0x55, 0x8B, 0xEC, 0x81, 0xEC, 0xA0, 0x00, 0x00, 0x00 };      /* 0x49d740 */
    static const BYTE e4[] = { 0x83, 0xEC, 0x28, 0x33, 0xD2 };                              /* 0x468440 */
    static const int c8[] = { 8 }, c4_14[] = { 4, 0x14 }, c10[] = { 0x10 };
    int ok = 0;
    if (env_flag("I76_COOP_SCRIPT_GUARD", 8, 1) == 0) { mlog("  coop-script-guard: off (I76_COOP_SCRIPT_GUARD=0)"); return; }
    g_csg_mem = VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_csg_mem) return;
    ok += csg_one(0, 0x0040b8e0, e0, sizeof e0, c8, 1, 0);
    ok += csg_one(1, 0x0040b940, e1, sizeof e1, c8, 1, 0);
    ok += csg_one(2, 0x0049d5f0, e2, sizeof e2, c4_14, 2, 0);
    ok += csg_one(3, 0x0049d740, e3, sizeof e3, c10, 1, 0);
    ok += csg_one(4, 0x00468440, e4, sizeof e4, c8, 1, 1);
    mlog("  coop-script-guard: %d/5 script action functions check their object argument (0x40b8e0 0x40b940 0x49d5f0 0x49d740 0x468440)", ok);
}
static void coop_script_guard_log(void) {                    /* from the pump: a skipped NULL is worth a line */
    static LONG seen[5]; int k;
    for (k = 0; k < 5; k++) if (g_csg_hits[k] != seen[k]) {
        static const DWORD fn[5] = { 0x40b8e0, 0x40b940, 0x49d5f0, 0x49d740, 0x468440 };
        mlog("  coop-script-guard: 0x%06lx called with a NULL object %ld time(s) (a removed car the script still names) - skipped", (unsigned long)fn[k], g_csg_hits[k] - seen[k]);
        seen[k] = g_csg_hits[k];
    }
}
static void apply_coop_damage(void) {
    static const struct { DWORD site, target; void *stub; const char *what; } s[4] = {
        { 0x004a76c5, 0x00458bf0, (void *)coop_is_human,        "impact: is-player" },
        { 0x004a76d1, 0x00452d20, (void *)coop_net_impact_stub, "impact: network factor" },
        { 0x00444393, 0x00458bf0, (void *)coop_is_human,        "flamer: is-player" },
        { 0x0044439f, 0x00452d20, (void *)coop_net_flame_stub,  "flamer: network factor" },
    };
    char v[16]; float f; int i, n = 0;
    DWORD k = env_str("I76_COOP_DAMAGE", v, sizeof(v));
    if (k == 0) return;
    f = (float)atof(v);
    if (!(f > 0.0f && f <= 4.0f)) { mlog("  coop-damage: '%s' is not a factor in (0, 4] - off", v); return; }
    memcpy(&g_coop_dmg_bits, &f, 4);
    for (i = 0; i < 4; i++) {
        BYTE old[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG r0 = (LONG)(s[i].target - (s[i].site + 5)), r1 = (LONG)((DWORD_PTR)s[i].stub - (s[i].site + 5));
        memcpy(old + 1, &r0, 4); memcpy(w + 1, &r1, 4);
        if (patch_bytes(s[i].site, old, w, 5, s[i].what)) n++;
        else mlog("  coop-damage: %s at 0x%08lx NOT patched (bytes differ)", s[i].what, (unsigned long)s[i].site);
    }
    mlog("  coop-damage: %d/4 sites; humans' weapon damage x %.2f in network games (offline: difficulty as stock)", n, f);
}

/* ===========================================================================
 * CO-OP SHARED ENEMIES  (I76_COOP_AI=1 on BOTH machines; off by default; network games only)
 * ===========================================================================
 * docs/COOP-SPIKE.md. In a network game each machine runs its own copy of a mission's AI cars and script, so the two
 * players fight different enemies. This makes the HOST's copies the real ones:
 *   - role: network game [0x541030] and both ids known; host when the local id [0x541028] equals the host id
 *     [0x541064], joiner otherwise;
 *   - host: about 10 times a second, every vehicle in the mission's label table (0x54a178: {heap, table, count};
 *     entries of 16 bytes = label[8], object), skipping player cars (objFlags 0x10 or in the network player table), is
 *     exported with the game's own state writer 0x4644d0 (object, float[24]: the 0x60-byte record the 'ST' packet
 *     carries: time, transform, velocity, spin, controls, flags incl. destroyed, damage levels, target) and sent as
 *     packet 'AT' = { u16 'AT', u8 0, u8 n, float time, n x { u16 label index, u16 0, record[0x60] } }, n <= 2
 *     (208 bytes): 5 per packet (508) never arrived, ANet's packet limit is lower than the pump's 512-byte buffer. Same mission file on both machines = same label order.
 *   - joiner: the 'AT' packets are caught after the game's dpReceive (the pump ignores the unknown type) and each
 *     record goes to the same-index car through the remote-car mirror 0x464890 (object, record), the function that
 *     drives remote players' cars from 'ST'; older records than the last applied are dropped. ai_FrameTick (the AI
 *     decisions AND the mission script, call at 0x403ddf) is skipped, so physics drives those cars with the host's
 *     controls between packets, as for remote players.
 *   - the joiner's shots already reach the host's copies through the game's own 'SH' fire packets (measured with
 *     I76_COOP_DAMAGE: the host computes them), so kills happen on the host and arrive with the 'destroyed' flag.
 * Read from the 2019 AiO exe (60abf7bc base) and the Ghidra export of 9a232dcc (same addresses here).
 *   - fire: the host records the AI's trigger pulls (`call 0x4a3560` at 0x414f86 in ai_FireWeapons) and puts a per-car
 *     mask in each record (byte 2; bits as in 'SH': weapons 0..4 of the 0x4a31d0 list, 0x20 / 0x40 the two specials);
 *     the joiner pulls those triggers on every pump call for 150 ms after each record.
 *   - damage: on the joiner, object_ClassDamage (5 call sites) is skipped for the mirrored cars, so only the host's
 *     copies take damage; a kill arrives in the record's 'destroyed' flag and the mirror wrecks the car.
 * MEASURED 2026-10-06 (docs/COOP-SPIKE.md "Shared enemies"): PC host + Mac joiner, co-op T01 and T04. Roles right; the
 * joiner applied 1,625-7,038 records per run; positions match (T04's gang at rest: 1210.0,50265.0 on both; after the
 * host's mission ended, both cars' last positions identical); the host's AI fire replayed on the joiner (11,729 pulls).
 * 5 records per packet (508 B) were silently dropped by ANet: 2 per packet. NOT observed yet: a hit, a kill. Gaps: the
 * mission outcome is the host's alone (when the host's mission ends the joiner stays in), radio/objectives are not
 * sent, and AI cars carry owner id 0 into the mirror's score bookkeeping. (All three since handled: the campaign chain,
 * 'AC' / 'AO', coop_ai_score_set.) */
typedef int (__cdecl *dprecv_fn)(void *, void *, void *, int, void *, void *);
typedef int (__cdecl *dpsend_fn)(void *, int, int, int, void *, int);
static int coop_chain_num(const char *cur);                  /* "coopNN.lvl" -> NN, else 0 (CO-OP CAMPAIGN CHAIN) */
static int coop_scen_num(const char *cur);                   /* "autoNN.lvl" -> NN, else 0 (scenarios as arenas) */
static void coop_near_trail(void);                           /* I76_COOP_NEAR_HOST (below coop_spawn) */
/* ANet's dpSend writes 4 bytes PAST the payload it is given (the from / to ids, in place: 03 00 04 00 = id 3 to
 * group 4, read from a host crash dump 2026-10-18). A send buffer on the stack with nothing after it lets that tail
 * overwrite the next local; in coop_chain_at_end (coop_chain_send inlined) it was the /GS cookie, and every host chain
 * reload (win or loss) ended in 0xC0000409 (LAN proxy 33211f11 too, n 5, COOP-LIST-ENTRIES-2026-10-18.md). Every
 * buffer handed to dpSend keeps COOP_DP_SLACK spare bytes after the payload. */
#define COOP_DP_SLACK 16
static dprecv_fn real_dpReceive;
static volatile LONG g_coop_ai_sent, g_coop_ai_applied, g_coop_ai_role, g_coop_ai_senderr, g_coop_ai_rx;
static DWORD g_coop_ai_last;
static float g_coop_ai_seen[2048];
static DWORD g_mpf_park_since[2048];                         /* mpfill.c: label index parked since (0 = in play); 'AT' sends it every 2 s */
static void mpf_engaged(BYTE *a);                            /* mpfill.c: an enemy original turned on a human (co-op scaling) */
static BYTE aim_at_team(BYTE *o); static void aim_at_team_apply(int li, BYTE *o, BYTE v); static BYTE *aim_at_revive(int li, BYTE *o, BYTE *r);   /* aimelee.c: an AI car's team in 'AT' byte 3 (team play) */
static BYTE g_coop_ai_fired[1024];                          /* host: weapon instances the AI triggered since the last send */
static BYTE g_coop_ai_mask[2048];                           /* joiner: last fire mask per label index ... */
static DWORD g_coop_ai_until[2048];                         /* ... and until when it holds (GetTickCount) */
static volatile LONG g_coop_ai_shots, g_coop_ai_blocked;
static int coop_ai_weapon_mask(BYTE *o, int *w8) {          /* weapon list 0x4a31d0: count, w[5], special a, b (as 'SH') */
    int i, mask = 0;
    memset(w8, 0, 8 * sizeof(int));
    if (((int (__cdecl *)(BYTE *, int *))0x004a31d0)(o, w8) != 1) return -1;
    for (i = 0; i < w8[0] && i < 5; i++) if (w8[1 + i] >= 0 && w8[1 + i] < 1024 && g_coop_ai_fired[w8[1 + i]]) mask |= 1 << i;
    if (w8[6] > 0 && w8[6] < 1024 && g_coop_ai_fired[w8[6]]) mask |= 0x20;
    if (w8[7] > 0 && w8[7] < 1024 && g_coop_ai_fired[w8[7]]) mask |= 0x40;
    return mask;
}
#define COOP_AI_PKT 0x5441                                   /* 'AT' (low byte first, as dppt_MAKE) */
static int coop_ai_role(void) {
    WORD me, host;
    if (!*(volatile int *)0x00541030) return 0;
    me = *(volatile WORD *)0x00541028; host = *(volatile WORD *)0x00541064;
    if (!me || !host) return 0;
    return me == host ? 1 : 2;
}
static int coop_ai_in_mission(void) {                        /* game state 5 and a world root */
    return *(volatile int *)0x004c2164 == 5 && ((int (__cdecl *)(void))0x00457530)() != 0;   /* world_GetRoot */
}
static BYTE *coop_ai_object(int i, int count, BYTE *tab) {   /* a mission vehicle that no player drives, or NULL */
    BYTE *o; int k;
    if (i >= count) return NULL;
    o = *(BYTE **)(tab + i * 16 + 8);
    /* a label can name an object the game has freed (jump lane 2026-10-21: a single-player re-placement rebuilt the car and
     * coop_ai_log read the old one, an access violation every boot): unreadable objects are skipped */
    if (!o || IsBadReadPtr(o, 0x74) || *(int *)(o + 0x6c) != 1 || !*(BYTE **)(o + 0x70) || IsBadReadPtr(*(BYTE **)(o + 0x70), 0x458) || (o[0x10] & 0x10)) return NULL;
    for (k = 0; k < 16; k++) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; if (*(WORD *)p && *(BYTE **)(p + 0x28) == o) return NULL; }
    return o;
}
static void coop_ai_host_send(void) {
    BYTE pkt[512]; BYTE *tab; int count, i, n = 0; static unsigned rounds;
    DWORD now = GetTickCount();
    if (now - g_coop_ai_last < 100 || !coop_ai_in_mission()) return;
    g_coop_ai_last = now;
    tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (!tab || count <= 0 || count > 2048) return;
    rounds++;
    for (i = 0; i <= count; i++) {
        BYTE *o = i < count ? coop_ai_object(i, count, tab) : NULL;
        if (o && g_mpf_park_since[i] && now - g_mpf_park_since[i] > 1500 && rounds % 20) o = NULL;   /* parked: every 2 s */
        if (o) {
            BYTE *r = pkt + 8 + n * 100;
            int w8[8], m = coop_ai_weapon_mask(o, w8);
            *(WORD *)r = (WORD)i; r[2] = (BYTE)(m < 0 ? 0 : m); r[3] = aim_at_team(o);
            ((void (__cdecl *)(BYTE *, float *))0x004644d0)(o, (float *)(r + 4));
            n++;
        }
        if (n && (n == 2 || i == count)) {
            *(WORD *)pkt = COOP_AI_PKT; pkt[2] = 0; pkt[3] = (BYTE)n;
            *(float *)(pkt + 4) = *(float *)(pkt + 8 + 4);
            if (((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028,
                                                    ((WORD (__cdecl *)(void))0x00454e10)(), 0, pkt, 8 + n * 100) == 0) g_coop_ai_sent += n;
            else g_coop_ai_senderr++;
            n = 0;
        }
    }
    memset(g_coop_ai_fired, 0, sizeof(g_coop_ai_fired));
}
static void coop_ai_apply(BYTE *pkt, int size) {
    BYTE *tab; int count, n, j;
    if (size < 8 || !coop_ai_in_mission()) return;
    n = pkt[3]; if (8 + n * 100 > size) return;
    tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (!tab || count <= 0 || count > 2048) return;
    for (j = 0; j < n; j++) {
        BYTE *r = pkt + 8 + j * 100; int i = *(WORD *)r; float t = *(float *)(r + 4);
        BYTE *o = coop_ai_object(i, count, tab);
        if (!o) continue;
        if (t <= g_coop_ai_seen[i] && t > g_coop_ai_seen[i] - 2.0f) continue;   /* older than the last one (time restarts on a reload) */
        g_coop_ai_seen[i] = t;
        o = aim_at_revive(i, o, r);                          /* aimelee.c: the host respawned this AI car, ours is a wreck */
        g_coop_ai_mask[i] = r[2]; g_coop_ai_until[i] = GetTickCount() + 150;
        aim_at_team_apply(i, o, r[3]);
        ((void (__cdecl *)(BYTE *, float *))0x00464890)(o, (float *)(r + 4));
        g_coop_ai_applied++;
    }
}
static int g_coop_chain = 0;                                /* I76_COOP_CHAIN (see "CO-OP CAMPAIGN CHAIN" below) */
static int g_coop_adopt = 1;                                /* I76_COOP_ADOPT=0: the host keeps a separate network car (diagnostic) */
static int g_coop_hostmodel = 1;                            /* I76_COOP_HOSTMODEL=0: the joiner's mission player object keeps the local car model */
static volatile LONG g_coop_chain_sent, g_coop_chain_got;
static volatile LONG g_coop_retarget;                       /* enemy attacks moved to the nearer human (host) */
static volatile LONG g_coop_adopted, g_coop_respawns, g_coop_cb_sent, g_coop_cb_played, g_coop_obj_sent, g_coop_obj_got;
/* own car dead (entity +0x454 & 0x20) and no respawn pending (0x540d8c): ask for one, at most once a second */
static void coop_auto_respawn(const char *who) {
    static DWORD last; DWORD now = GetTickCount();
    BYTE **root; BYTE *o;
    if (now - last <= 1000) return;
    last = now;
    root = ((BYTE **(__cdecl *)(void))0x00457530)();
    o = root ? *root : NULL;
    if (o && *(BYTE **)(o + 0x70) && ((*(BYTE **)(o + 0x70))[0x454] & 0x20) && !*(volatile int *)0x00540d8c) {
        ((int (__cdecl *)(int))0x00451570)(1);   /* waits out the 5 s itself; sets the pending flag 0x540d8c once sent */
        if (*(volatile int *)0x00540d8c) { g_coop_respawns++; mlog("  coop-chain: %s dead - respawn requested", who); }
    }
}
static int g_coop_diag; static void coop_sb_log(void);
/* Heap shim watch (I76_COOP_HEAPWATCH=1; I76_COOP_HEAPLOCK=1 also serialises). On Windows the compatibility shim
 * AcGenral (applied to i76.exe by Windows' own database) replaces HeapCreate / HeapDestroy with a private heap whose
 * HeapDestroy unlinks the heap from ONE global list without a global lock (AcGenral 10.0.19041.3636 +0x98abd..0x98adc:
 * walk from the head, next at +0x48, then VirtualFree). The rare host crash at a chain reload is that walk reading a
 * node whose memory was already released (read 0x138B0048, list node 0x138B0000, in the chunk heap's HeapDestroy
 * 0x4a2d22; 3 times in ~100 reloads, always with a joiner present). The shim engine hooks the imports of every
 * non-system module, the network DLLs too, so a heap created or destroyed on a network thread at the same moment
 * would corrupt the list. This counts every module's HeapCreate / HeapDestroy by thread and, with the lock, makes
 * them one at a time. Modules are (re)scanned from the pump every 5 s; each slot keeps its own original. */
#define COOP_HP_N 24
static void **g_hp_cslot[COOP_HP_N], **g_hp_dslot[COOP_HP_N];
static void *g_hp_corig[COOP_HP_N], *g_hp_dorig[COOP_HP_N];
static char g_hp_mod[COOP_HP_N][20]; static int g_hp_shim[COOP_HP_N], g_hp_n;
static volatile LONG g_hp_cnt[COOP_HP_N][4];                /* create main, create other, destroy main, destroy other */
static DWORD g_hp_main; static int g_hp_lock_on; static CRITICAL_SECTION g_hp_cs;
/* Live shim heaps (handle = header address; the shim's destroy frees the header's segment chain, next at +4, after
 * unlinking the heap from its list, next at +0x48). After each destroy every other live heap must still be mapped;
 * one that is not is a dead node left in the shim's list - the crash signature - and is logged with both callers.
 * Before a destroy a segment chain that leads into another live heap's header is cut there (that heap then keeps its
 * memory; the destroyed heap leaks the rest of its chain). */
#define HP_LIVE 1024
static BYTE *g_hp_live[HP_LIVE]; static void *g_hp_live_by[HP_LIVE]; static int g_hp_nlive;
static volatile LONG g_hp_dead, g_hp_cut;
static int hp_mapped(const void *p) {
    MEMORY_BASIC_INFORMATION mi;
    return VirtualQuery(p, &mi, sizeof(mi)) == sizeof(mi) && mi.State == MEM_COMMIT;
}
/* The guard (on with I76_COOP_AI unless I76_COOP_HEAPGUARD=0). Measured 2026-10-07 with the watch: every heap
 * create/destroy came from i76.exe on the main thread (no race), no destroy freed another live heap, and the crash
 * still came - once as the walk reading a released node, once as the walk running off the END of the list (the heap
 * being destroyed was no longer reachable). So the list links get damaged; the writer is not found. The guard walks
 * the shim's list itself first (head found by matching the shim's own unlink code, `mov ecx,[list]; add ecx,8; ...
 * lea ecx,[eax+48h]; mov eax,[ecx]; cmp eax,edi; jne`, AcGenral 10.0.19041.3636 +0x98ac5; no match = no guard), every
 * node checked readable. A heap it cannot reach is put back at the head before the shim's destroy runs, so the shim
 * finds it at once, unlinks it and frees it (measured: one teardown found ~40 heaps unreachable - the list had been
 * cut - and the first of them would have been the crash). */
static BYTE **g_hp_list;                                    /* AcGenral's global; its +8 is the list head */
static int g_hs_want = 1;                                   /* I76_COOP_SHIMLOCK=0: no lock in the shim itself */
static int g_hp_guard, g_hp_only_exe; static volatile LONG g_hp_skipped;
/* The race, found 2026-10-07: the other party is the NVIDIA user-mode D3D11 driver (nvwgf2um.dll, under dgVoodoo's
 * D3D11 output). It lives in the DriverStore, not System32, so the shim engine treats it as an application module and
 * its heap calls go through the same AcGenral heap; it destroys heaps on its own worker thread (a crash record: the
 * shim's walk on that thread, called from nvwgf2um+0x94FDF7) while the game creates them on the main thread. The
 * shim's internal create (+0x9899b, fastcall + 1 stack arg, ret 4) inserts at the head and its internal destroy
 * (+0x98a70, heap in ecx, ret) unlinks, neither under a lock: a destroy between a create's read of the head and its
 * write leaves the new heap pointing at the freed one (the dead node) and everything older cut off (the "list ends
 * early" teardowns). Both are wrapped here in one lock; each is found by its own prologue near the list code it
 * contains, and nothing is patched unless both match. The game's own calls do not reach the driver's path, so
 * hooking imports could never serialise it. */
static CRITICAL_SECTION g_hs_cs; static BYTE *g_hs_ctramp, *g_hs_dtramp; static volatile LONG g_hs_on;
static void __cdecl hs_enter(void) { EnterCriticalSection(&g_hs_cs); }
static void __cdecl hs_leave(void) { LeaveCriticalSection(&g_hs_cs); }
static __declspec(naked) void hs_create_stub(void) {        /* ecx, edx = args, [esp+4] = the stack arg */
    __asm {
        push ecx
        push edx
        call hs_enter
        pop edx
        pop ecx
        push dword ptr [esp + 4]                /* the stack arg again: the original's ret 4 pops this copy */
        call dword ptr [g_hs_ctramp]
        push eax
        call hs_leave
        pop eax
        ret 4
    }
}
static __declspec(naked) void hs_destroy_stub(void) {       /* ecx = heap */
    __asm {
        push ecx
        call hs_enter
        pop ecx
        call dword ptr [g_hs_dtramp]
        push eax
        call hs_leave
        pop eax
        ret
    }
}
static BYTE *hs_back(BYTE *from, int range, const BYTE *pro, int n) {   /* nearest prologue before `from` */
    BYTE *q;
    for (q = from; q > from - range; q--) if (memcmp(q, pro, n) == 0) return q;
    return NULL;
}
static void hs_install(BYTE *unlink_code, BYTE *m, BYTE *end) {
    static const BYTE dpro[10] = { 0x8B, 0xFF, 0x53, 0x57, 0x6A, 0x00, 0x33, 0xD2, 0x8B, 0xF9 };   /* destroy: 6 bytes moved */
    static const BYTE cpro[14] = { 0x8B, 0xFF, 0x55, 0x8B, 0xEC, 0x51, 0x51, 0x83, 0x65, 0xFC, 0x00, 0x56, 0x8B, 0xF1 };  /* create: 5 moved */
    static const BYTE ins[11] = { 0x8B, 0x40, 0x08, 0x89, 0x43, 0x48, 0xA1 };   /* mov eax,[eax+8]; mov [ebx+48h],eax; mov eax,[g] */
    BYTE *df = hs_back(unlink_code, 0x80, dpro, sizeof(dpro)), *ip = NULL, *cf = NULL, *t; DWORD old; LONG rel;
    for (t = m + 0x1000; t < end && !ip; t++)
        if (t[0] == 0xA1 && memcmp(t + 5, ins, 7) == 0 && *(BYTE ***)(t + 1) == g_hp_list && *(BYTE ***)(t + 12) == g_hp_list &&
            t[16] == 0x89 && t[17] == 0x58 && t[18] == 0x08) ip = t;
    if (ip) cf = hs_back(ip, 0x100, cpro, sizeof(cpro));
    if (!df || !cf) { mlog("  coop-heap: shim create/destroy not recognised (destroy %p, insert %p, create %p) - no shim lock", df, ip, cf); return; }
    t = (BYTE *)VirtualAlloc(NULL, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!t) return;
    InitializeCriticalSection(&g_hs_cs);
    g_hs_ctramp = t; memcpy(t, cf, 5); t[5] = 0xE9; rel = (LONG)((cf + 5) - (t + 10)); memcpy(t + 6, &rel, 4);
    g_hs_dtramp = t + 32; memcpy(t + 32, df, 6); t[38] = 0xE9; rel = (LONG)((df + 6) - (t + 43)); memcpy(t + 39, &rel, 4);
    FlushInstructionCache(GetCurrentProcess(), t, 64);
    if (VirtualProtect(df, 6, PAGE_EXECUTE_READWRITE, &old)) {
        BYTE j[6]; rel = (LONG)((BYTE *)hs_destroy_stub - (df + 5)); j[0] = 0xE9; memcpy(j + 1, &rel, 4); j[5] = 0x90;
        memcpy(df, j, 6); VirtualProtect(df, 6, old, &old);
    }
    if (VirtualProtect(cf, 5, PAGE_EXECUTE_READWRITE, &old)) {
        BYTE j[5]; rel = (LONG)((BYTE *)hs_create_stub - (cf + 5)); j[0] = 0xE9; memcpy(j + 1, &rel, 4);
        memcpy(cf, j, 5); VirtualProtect(cf, 5, old, &old);
    }
    FlushInstructionCache(GetCurrentProcess(), NULL, 0);
    g_hs_on = 1;
    mlog("  coop-heap: shim heap create +0x%lx / destroy +0x%lx now run one at a time (all threads)", (unsigned long)(cf - m), (unsigned long)(df - m));
}
static void hp_find_list(void) {
    BYTE *m = (BYTE *)GetModuleHandleA("AcGenral.dll"), *p, *end;
    static const BYTE tail[14] = { 0x83, 0xC1, 0x08, 0xEB, 0x03, 0x8D, 0x48, 0x48, 0x8B, 0x01, 0x3B, 0xC7, 0x75, 0xF7 };
    IMAGE_NT_HEADERS *nt;
    if (!m) return;
    nt = (IMAGE_NT_HEADERS *)(m + ((IMAGE_DOS_HEADER *)m)->e_lfanew);
    end = m + nt->OptionalHeader.SizeOfImage - 20;
    for (p = m + 0x1000; p < end; p++)
        if (p[0] == 0x8B && p[1] == 0x0D && memcmp(p + 6, tail, sizeof(tail)) == 0 && hp_mapped(p)) {
            g_hp_list = *(BYTE ***)(p + 2);
            mlog("  coop-heap: AcGenral heap list at %p (code +0x%lx) - destroy guard on", g_hp_list, (unsigned long)(p - m));
            if (g_hs_want) hs_install(p, m, end);
            return;
        }
    mlog("  coop-heap: AcGenral loaded but its heap list code was not recognised - no destroy guard");
}
static BYTE *g_hp_tail; static int g_hp_len;               /* the last walk: where the list ended, how long it was */
static int hp_reachable(BYTE *h, BYTE **dead) {              /* 1 found, 0 not (dead = the unreadable node, if any) */
    BYTE *n, *prev = NULL; int steps = 0;
    *dead = NULL;
    if (!hp_mapped(g_hp_list) || !hp_mapped(*g_hp_list + 8)) return 1;   /* cannot tell: let the shim do it */
    for (n = *(BYTE **)(*g_hp_list + 8); n && steps < 16384; steps++) {
        if (n == h) return 1;
        if (!hp_mapped(n + 0x48)) { *dead = n; g_hp_tail = prev; g_hp_len = steps; return 0; }
        prev = n; n = *(BYTE **)(n + 0x48);
    }
    g_hp_tail = prev; g_hp_len = steps;
    return n == h;
}
static HANDLE hp_create(int i, DWORD f, SIZE_T a, SIZE_T b, void *by) {
    HANDLE h;
    InterlockedIncrement(&g_hp_cnt[i][GetCurrentThreadId() == g_hp_main ? 0 : 1]);
    if (g_hp_lock_on) EnterCriticalSection(&g_hp_cs);
    h = ((HANDLE (WINAPI *)(DWORD, SIZE_T, SIZE_T))g_hp_corig[i])(f, a, b);
    if (h && g_hp_shim[i] && g_hp_nlive < HP_LIVE) { g_hp_live[g_hp_nlive] = (BYTE *)h; g_hp_live_by[g_hp_nlive] = by; g_hp_nlive++; }
    if (g_hp_lock_on) LeaveCriticalSection(&g_hp_cs);
    return h;
}
static BOOL hp_destroy(int i, HANDLE h, void *by) {
    BOOL r; int k, j;
    InterlockedIncrement(&g_hp_cnt[i][GetCurrentThreadId() == g_hp_main ? 2 : 3]);
    if (g_hp_lock_on) EnterCriticalSection(&g_hp_cs);
    for (k = 0; k < g_hp_nlive; k++) if (g_hp_live[k] == (BYTE *)h) { g_hp_live[k] = g_hp_live[--g_hp_nlive]; g_hp_live_by[k] = g_hp_live_by[g_hp_nlive]; break; }
    if (g_hp_shim[i] && h && hp_mapped(h)) {                /* the segment chain must not lead into another live heap */
        BYTE *seg = (BYTE *)h; int steps = 0;
        while (seg && steps++ < 256 && hp_mapped(seg + 4)) {
            BYTE *next = *(BYTE **)(seg + 4);
            for (j = 0; next && j < g_hp_nlive; j++) if (g_hp_live[j] == next) break;
            if (next && j < g_hp_nlive) {
                mlog("  coop-heap: destroying %p (caller %p): its segment chain leads into LIVE heap %p (created by %p) - cut at %p",
                     h, by, next, g_hp_live_by[j], seg);
                *(BYTE **)(seg + 4) = NULL; InterlockedIncrement(&g_hp_cut);
                break;
            }
            seg = next;
        }
    }
    if (g_hp_guard && g_hp_list && g_hp_shim[i] && h) {
        BYTE *dead;
        if (!hp_reachable((BYTE *)h, &dead)) {
            static int told;
            InterlockedIncrement(&g_hp_skipped);
            if (told++ < 3) {                                /* where the list ends now, and what that node looks like */
                int j; void *tby = NULL; char hx[0x50 * 3 + 1]; int L = 0;
                for (j = 0; j < g_hp_nlive; j++) if (g_hp_live[j] == g_hp_tail) tby = g_hp_live_by[j];
                if (g_hp_tail && hp_mapped(g_hp_tail)) for (j = 0; j < 0x50; j++) L += sprintf(hx + L, "%02x", g_hp_tail[j]);
                hx[L] = 0;
                mlog("  coop-heap: HeapDestroy(%p) from %p: not reachable in the shim's heap list (%s; walk ended after %d nodes at %p, created by %p) - relinked at the head",
                     h, by, dead ? "a released node blocks the walk" : "the list ends early", g_hp_len, g_hp_tail, tby);
                mlog("  coop-heap:   end node header %s%s", hx, dead ? " (released node follows)" : "");
            }
            if (!hp_mapped((BYTE *)h + 0x48)) {             /* cannot relink: leave it allocated rather than crash */
                mlog("  coop-heap: HeapDestroy(%p) SKIPPED - header not mapped", h);
                if (g_hp_lock_on) LeaveCriticalSection(&g_hp_cs);
                return TRUE;
            }
            /* put it back at the head: the shim's walk then finds it first and unlinks it (head = its next = the old
             * head), so the list is as before and the heap is freed properly */
            *(BYTE **)((BYTE *)h + 0x48) = *(BYTE **)(*g_hp_list + 8);
            *(BYTE **)(*g_hp_list + 8) = (BYTE *)h;
        }
    }
    r = ((BOOL (WINAPI *)(HANDLE))g_hp_dorig[i])(h);
    if (g_hp_shim[i])
        for (k = 0; k < g_hp_nlive; k++)
            if (!hp_mapped(g_hp_live[k])) {
                mlog("  coop-heap: after destroying %p (caller %p) live heap %p (created by %p) is GONE - dead node in the shim's list",
                     h, by, g_hp_live[k], g_hp_live_by[k]);
                InterlockedIncrement(&g_hp_dead);
                g_hp_live[k] = g_hp_live[--g_hp_nlive]; g_hp_live_by[k] = g_hp_live_by[g_hp_nlive]; k--;
            }
    if (g_hp_lock_on) LeaveCriticalSection(&g_hp_cs);
    return r;
}
#define HPW(i) static HANDLE WINAPI hpc##i(DWORD f, SIZE_T a, SIZE_T b) { return hp_create(i, f, a, b, __builtin_return_address(0)); } \
               static BOOL WINAPI hpd##i(HANDLE h) { return hp_destroy(i, h, __builtin_return_address(0)); }
HPW(0) HPW(1) HPW(2) HPW(3) HPW(4) HPW(5) HPW(6) HPW(7) HPW(8) HPW(9) HPW(10) HPW(11)
HPW(12) HPW(13) HPW(14) HPW(15) HPW(16) HPW(17) HPW(18) HPW(19) HPW(20) HPW(21) HPW(22) HPW(23)
static void *const g_hpc[COOP_HP_N] = { hpc0, hpc1, hpc2, hpc3, hpc4, hpc5, hpc6, hpc7, hpc8, hpc9, hpc10, hpc11,
    hpc12, hpc13, hpc14, hpc15, hpc16, hpc17, hpc18, hpc19, hpc20, hpc21, hpc22, hpc23 };
static void *const g_hpd[COOP_HP_N] = { hpd0, hpd1, hpd2, hpd3, hpd4, hpd5, hpd6, hpd7, hpd8, hpd9, hpd10, hpd11,
    hpd12, hpd13, hpd14, hpd15, hpd16, hpd17, hpd18, hpd19, hpd20, hpd21, hpd22, hpd23 };
static int g_hp_watch;
static void **hp_slot(HMODULE mod, const char *func) {        /* iat_slot for any module: needs the name table, checks every RVA */
    BYTE *base = (BYTE *)mod; IMAGE_NT_HEADERS *nt; IMAGE_IMPORT_DESCRIPTOR *d; DWORD size, n = 0;
    if (((IMAGE_DOS_HEADER *)base)->e_magic != IMAGE_DOS_SIGNATURE) return NULL;
    nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return NULL;
    size = nt->OptionalHeader.SizeOfImage;
    if (!nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress) return NULL;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(base + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
         d->Name && n < 256; d++, n++) {
        IMAGE_THUNK_DATA *oft, *ft; DWORD k;
        if (d->Name >= size || !d->OriginalFirstThunk || d->OriginalFirstThunk >= size || d->FirstThunk >= size) continue;
        if (lstrcmpiA((char *)(base + d->Name), "KERNEL32.dll") != 0) continue;
        oft = (IMAGE_THUNK_DATA *)(base + d->OriginalFirstThunk); ft = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (k = 0; oft->u1.AddressOfData && k < 4096; oft++, ft++, k++) {
            if (oft->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            if (oft->u1.AddressOfData + 2 >= size) break;
            if (lstrcmpA((char *)((IMAGE_IMPORT_BY_NAME *)(base + oft->u1.AddressOfData))->Name, func) == 0) return (void **)&ft->u1.Function;
        }
    }
    return NULL;
}
static void coop_heap_scan(void) {                           /* from the pump (main thread) */
    static DWORD last; DWORD now = GetTickCount();
    HANDLE sn; MODULEENTRY32 me; HMODULE self = NULL;
    if (!g_hp_watch || (last && now - last < 5000)) return;
    last = now;
    {   int k;                                               /* a live heap released by anything but a destroy */
        if (g_hp_lock_on) EnterCriticalSection(&g_hp_cs);
        for (k = 0; k < g_hp_nlive; k++)
            if (!hp_mapped(g_hp_live[k])) {
                mlog("  coop-heap: live heap %p (created by %p) is GONE without a destroy", g_hp_live[k], g_hp_live_by[k]);
                InterlockedIncrement(&g_hp_dead);
                g_hp_live[k] = g_hp_live[--g_hp_nlive]; g_hp_live_by[k] = g_hp_live_by[g_hp_nlive]; k--;
            }
        if (g_hp_lock_on) LeaveCriticalSection(&g_hp_cs);
    }
    if (!g_hp_main) { g_hp_main = GetCurrentThreadId(); if (g_hp_guard && !g_hp_list) hp_find_list(); }
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)coop_heap_scan, &self);
    sn = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, 0);
    if (sn == INVALID_HANDLE_VALUE) return;
    me.dwSize = sizeof(me);
    if (Module32First(sn, &me)) do {
        void **cs, **ds; int i, k;
        if (me.hModule == self || g_hp_n >= COOP_HP_N) continue;
        if (g_hp_only_exe && me.hModule != GetModuleHandleA(NULL)) continue;
        cs = hp_slot(me.hModule, "HeapCreate"); ds = hp_slot(me.hModule, "HeapDestroy");
        if (!cs || !ds) continue;
        for (k = 0; k < g_hp_n; k++) if (g_hp_cslot[k] == cs) break;
        if (k < g_hp_n) continue;                            /* already ours */
        {   HMODULE owner = NULL; char on[MAX_PATH] = "?";
            GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)*cs, &owner);
            if (owner) { char *b; GetModuleFileNameA(owner, on, sizeof(on)); b = strrchr(on, '\\'); if (b) memmove(on, b + 1, strlen(b)); }
            i = g_hp_n;
            g_hp_cslot[i] = cs; g_hp_dslot[i] = ds; g_hp_corig[i] = *cs; g_hp_dorig[i] = *ds;
            lstrcpynA(g_hp_mod[i], me.szModule, sizeof(g_hp_mod[i]));
            g_hp_shim[i] = _strnicmp(on, "kernel", 6) != 0;
            {   DWORD old;
                if (VirtualProtect(cs, sizeof(void *), PAGE_READWRITE, &old)) { *cs = g_hpc[i]; VirtualProtect(cs, sizeof(void *), old, &old); }
                if (VirtualProtect(ds, sizeof(void *), PAGE_READWRITE, &old)) { *ds = g_hpd[i]; VirtualProtect(ds, sizeof(void *), old, &old); }
            }
            g_hp_n++;
            mlog("  coop-heap: watching %s (HeapCreate goes to %s)%s", me.szModule, on, g_hp_lock_on ? ", serialised" : "");
        }
    } while (Module32Next(sn, &me));
    CloseHandle(sn);
}
static void coop_heap_log(void) {
    char line[COOP_HP_N * 48 + 32]; int i, len = sprintf(line, "  coop-heap:");
    if (!g_hp_watch || !g_hp_n) return;
    for (i = 0; i < g_hp_n; i++)
        if (g_hp_cnt[i][0] | g_hp_cnt[i][1] | g_hp_cnt[i][2] | g_hp_cnt[i][3])
            len += sprintf(line + len, " %.12s c%ld/%ld d%ld/%ld;", g_hp_mod[i], g_hp_cnt[i][0], g_hp_cnt[i][1], g_hp_cnt[i][2], g_hp_cnt[i][3]);
    mlog("%s (main/other thread); live %d, dead nodes %ld, chains cut %ld, destroys relinked %ld", line, g_hp_nlive, g_hp_dead, g_hp_cut, g_hp_skipped);
}
static void coop_ai_log(void) {                            /* after each fps line: role, counts, first two mission cars */
    BYTE *tab; int count, i, shown = 0; char buf[512]; int len;
    if (!real_dpReceive) return;
    coop_heap_log();
    if (!*(volatile int *)0x00541030) return;                /* single player: no co-op cars to report (and nothing to read) */
    len = sprintf(buf, "  coop-ai: role %s, sent %ld (send errors %ld), packets in %ld, applied %ld, fire pulls %ld, local damage blocked %ld",
                  g_coop_ai_role == 1 ? "host" : g_coop_ai_role == 2 ? "joiner" : "none", g_coop_ai_sent, g_coop_ai_senderr, g_coop_ai_rx,
                  g_coop_ai_applied, g_coop_ai_shots, g_coop_ai_blocked);
    len += sprintf(buf + len, ", retargets %ld, adopted %ld, respawns %ld, cb sent %ld played %ld", g_coop_retarget, g_coop_adopted, g_coop_respawns, g_coop_cb_sent, g_coop_cb_played);
    len += sprintf(buf + len, ", objectives sent %ld got %ld", g_coop_obj_sent, g_coop_obj_got);
    if (g_coop_diag) { static int t; if (++t % 2 == 0) coop_sb_log(); }
    if (g_coop_chain) len += sprintf(buf + len, ", chain AM sent %ld got %ld, mission %.12s", g_coop_chain_sent, g_coop_chain_got, (char *)0x005049f0);
    tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (tab && count > 0 && count <= 2048 && *(volatile int *)0x004c2164 == 5)
        for (i = 0; i < count && shown < 2; i++) {
            BYTE *o = coop_ai_object(i, count, tab);
            if (!o) continue;
            len += sprintf(buf + len, "; #%d %.8s at %.1f,%.1f armour %d%s", i, (char *)(tab + i * 16), *(double *)(o + 0x40),
                           *(double *)(o + 0x50), *(int *)(*(BYTE **)(o + 0x70) + 0x138 + 12),
                           (*(BYTE **)(o + 0x70))[0x454] & 0x20 ? " DEAD" : "");
            shown++;
        }
    if (tab && count > 0 && count <= 2048 && *(volatile int *)0x004c2164 == 5) {
        int alive = 0, dead = 0;
        for (i = 0; i < count; i++) { BYTE *o = coop_ai_object(i, count, tab); if (o) { if ((*(BYTE **)(o + 0x70))[0x454] & 0x20) dead++; else alive++; } }
        len += sprintf(buf + len, "; mission cars alive %d dead %d", alive, dead);
        {   BYTE **root = ((BYTE **(__cdecl *)(void))0x00457530)();          /* world_GetRoot: the local player's car */
            BYTE *e = (root && *root) ? *(BYTE **)(*root + 0x70) : NULL;
            if (e) len += sprintf(buf + len, "; own armour %d,%d,%d,%d", *(int *)(e + 0x138), *(int *)(e + 0x13c), *(int *)(e + 0x140), *(int *)(e + 0x144)); }
    }
    mlog("%s", buf);
}
static void coop_ai_joiner_fire(void) {                     /* every pump call: hold the host's triggers for 150 ms */
    BYTE *tab; int count, i, k, w8[8]; DWORD now = GetTickCount();
    if (!coop_ai_in_mission()) return;
    tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (!tab || count <= 0 || count > 2048) return;
    for (i = 0; i < count; i++) {
        BYTE *o; int m = g_coop_ai_mask[i];
        if (!m || (LONG)(now - g_coop_ai_until[i]) > 0 || !(o = coop_ai_object(i, count, tab))) continue;
        memset(w8, 0, sizeof(w8));
        if (((int (__cdecl *)(BYTE *, int *))0x004a31d0)(o, w8) != 1) continue;
        for (k = 0; k < w8[0] && k < 5; k++) if (m & (1 << k)) ((int (__cdecl *)(int, int))0x004a3560)(w8[1 + k], 1);
        if ((m & 0x20) && w8[6]) ((int (__cdecl *)(int, int))0x004a3560)(w8[6], 1);
        if ((m & 0x40) && w8[7]) ((int (__cdecl *)(int, int))0x004a3560)(w8[7], 1);
        g_coop_ai_shots++;
    }
}
static int __cdecl coop_ai_trigger(int w, int v) {         /* replaces `call 0x4a3560` at 0x414f86 (ai_FireWeapons) */
    if (w >= 0 && w < 1024 && v) g_coop_ai_fired[w] = 1;
    return ((int (__cdecl *)(int, int))0x004a3560)(w, v);
}
static int coop_ai_is_mirrored(BYTE *o) {                  /* joiner: one of the cars the host drives */
    BYTE *tab; int count, i;
    if (!o || *(int *)(o + 0x6c) != 1 || (o[0x10] & 0x10)) return 0;
    tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (!tab || count <= 0 || count > 2048) return 0;
    for (i = 0; i < count; i++) if (*(BYTE **)(tab + i * 16 + 8) == o) return coop_ai_object(i, count, tab) != NULL;
    return 0;
}
/* Score: the remote-car mirror 0x464890 ends with 0x454ea0(owner id, score, kills, deaths) (`call` at 0x465267), which
 * stores the record's score in the owner's player table slot and checks MAX SCORE. A mission car's owner id is 0, and
 * the slot lookup for id 0 finds the first EMPTY slot, so on the joiner each enemy wrote into a free slot (in a team
 * game that slot's team, 0, then counted toward the max-score check). Real players never have id 0: skipped for it. */
static void __cdecl coop_ai_score_set(int id, int score, int kills, int deaths) {
    if ((WORD)id == 0) return;
    ((void (__cdecl *)(int, int, int, int))0x00454ea0)(id, score, kills, deaths);
}
/* Rear mirror without a car: renderer_DrawRearMirror 0x445750 reads the local car through the world root
 * (*world_GetRoot() -> 0x467440 -> +0x70) with no NULL check. A joiner can run mission frames before its own car
 * exists (stuck in a load the host had already left, soak 2026-10-07: crash at 0x467444 reading 0x70, from 0x4457f6,
 * twice). Both calls (0x401cfe, 0x401fde) skip the mirror while there is no local car. */
static volatile LONG g_coop_mirror_skips;
static void __cdecl coop_mirror(void) {
    BYTE **root = ((BYTE **(__cdecl *)(void))0x00457530)();
    if (!root || !*root || !*(BYTE **)(*root + 0x70)) { g_coop_mirror_skips++; return; }
    ((void (__cdecl *)(void))0x00445750)();
}
static int __cdecl coop_ai_class_damage(BYTE *o, int a, int rec) {   /* replaces `call object_ClassDamage 0x462040` x5 */
    if (coop_ai_role() == 2 && coop_ai_is_mirrored(o)) { g_coop_ai_blocked++; return 0; }
    return ((int (__cdecl *)(BYTE *, int, int))0x00462040)(o, a, rec);
}
#define COOP_AM_PKT 0x4d41                                   /* 'AM' (co-op chain, below) */
#define COOP_AC_PKT 0x4341                                   /* 'AC' (CB radio line, below) */
#define COOP_AO_PKT 0x4f41                                   /* 'AO' (objective success / fail / reveal, below) */
static void coop_obj_receive(BYTE *pkt, int size);
static void coop_cb_receive(BYTE *pkt, int size);
static void coop_cb_flush(void); static volatile LONG g_coop_cb_qn;
static void coop_obj_flush(void); static volatile LONG g_coop_obj_qn; static void coop_obj_catchup(void);
static void coop_chain_receive(BYTE *pkt, int size);
static void coop_chain_pending(void);
static LONG g_coop_rx_run, g_coop_rx_logged;                /* diagnostics: packets in one unbroken pump loop */
static WORD g_coop_rx_types[64], g_coop_rx_from[64]; static int g_coop_rx_n;
static WORD g_coop_group; static DWORD g_coop_group_wait;    /* the session's game group, kept across chain reloads */
static char g_coop_pending_am[16];                          /* an 'AM' that arrived while this machine was loading */
static int g_coop_reload_host;                              /* this machine was the host when the chain reloaded (handshake below) */
static int g_coop_host_wait_ms = 3000;                      /* I76_COOP_HOST_WAIT_MS: 0 = stock (wait for 5 s of quiet) */
static int g_coop_test_host_respawn;                         /* LAB ONLY I76_COOP_TEST_HOST_RESPAWN=1: the host asks for a respawn when dead */
static int coop_chain_frames_running(void);
static int __cdecl coop_dpReceive(void *dp, void *from, void *to, int flags, void *buf, void *size) {
    int r = real_dpReceive(dp, from, to, flags, buf, size);
    int role = coop_ai_role();
    coop_heap_scan();
    if (g_coop_chain && *(volatile int *)0x00541030 && *(volatile int *)0x004c2164 != 5) {   /* diagnostics while not playing */
        static DWORD lastw; DWORD now = GetTickCount();
        if (now - lastw > 5000) {
            lastw = now;
            mlog("  coop-chain: waiting - state %d, group %u (kept %u), in-game %d, pump-exit %d, me %u, host %u, players %d",
                 *(volatile int *)0x004c2164, *(volatile WORD *)0x00541060, g_coop_group, *(volatile int *)0x00541034,
                 *(volatile int *)0x00609320, *(volatile WORD *)0x00541028, *(volatile WORD *)0x00541064,
                 ((int (__cdecl *)(void))0x00454610)());
        }
    }
    if (g_coop_chain && __builtin_return_address(0) == (void *)0x00452F70) {   /* the join handshake 0x452f20 */
        /* The handshake (called every frame until it returns 1) ends when this player's 'SP' arrives (sent to players
         * joining from the menus) or after 5 s (game clock) with no 'XX' / 0xcc43 from a lower id (0x540ffc = the last
         * one). On a chain reload both machines load together and the host's load is that quiet spell. When the host
         * is already PLAYING (it finished the mission the joiner was still loading; soak 2026-10-07) its 'XX' and
         * 0xcc43 never stop (measured: every 0.2 s for minutes) and the joiner waited forever. After 8 s the host's
         * chatter is aged on every empty receive, so the game's own timeout spawns the joiner as for a late join; a
         * held 'AM' then takes it to the host's mission. */
        static WORD ty[16], fr[16]; static int n, total; static DWORD last, start, told;
        DWORD now = GetTickCount();
        if (!last || now - last > 3000) { n = 0; total = 0; start = now; told = 0; }  /* a new handshake */
        last = now;
        if (r != 0 && now - start > 8000 && *(volatile WORD *)0x00541064 && *(volatile WORD *)0x00541064 != *(volatile WORD *)0x00541028) {
            *(volatile float *)0x00540ffc = (float)((double (__cdecl *)(void))0x0049c8c0)() - 10.0f;
            if (!told) { told = 1; mlog("  coop-chain: handshake 8 s old and the host is not quiet (it is already playing) - spawning on the game's timeout path"); }
        }
        /* The same wait on the HOST after a chain reload (owner 2026-10-24: after the scenario restarted, the host sat with
         * the camera at the map's corner for about a minute; records/LAN-FIXES-2026-10-24.md s.5). Any 'XX' from any id
         * restarts the quiet clock (0x452f20: 0x5858 -> [0x540ffc] = now), and a joiner that finished its own load first
         * plays and sends 'XX' every 0.2 s, so the host's handshake never saw 5 s of quiet until the joiner left. Nobody
         * sends the host an 'SP' (it is the one that sends them). So on a machine that was the host when the chain
         * reloaded, the quiet clock is aged after I76_COOP_HOST_WAIT_MS (default 3000) of handshake: the host spawns, the
         * session goes on with the joiners already in it. */
        if (r != 0 && g_coop_reload_host && g_coop_host_wait_ms > 0 && now - start > (DWORD)g_coop_host_wait_ms) {
            *(volatile float *)0x00540ffc = (float)((double (__cdecl *)(void))0x0049c8c0)() - 10.0f;
            if (!told) { told = 1; mlog("  coop-chain: host handshake after the reload %lu ms old (%d packets meanwhile) - spawning on the game's timeout path", now - start, total); }
        }
        if (r == 0 && buf && from) {
            int k;
            for (k = 0; k < n; k++) if (ty[k] == *(WORD *)buf && fr[k] == *(WORD *)from) break;
            if (k == n && n < 16) { ty[n] = *(WORD *)buf; fr[n] = *(WORD *)from; n++; }
            if (++total <= 12 || (total % 200) == 0) {
                char line[16 * 12 + 96]; int i, len = sprintf(line, "  coop-chain: handshake rx #%d (pump-exit %d, quiet-since %.1f, now %.1f), kinds:", total,
                    *(volatile int *)0x00609320, *(volatile float *)0x00540ffc, (float)((double (__cdecl *)(void))0x0049c8c0)());   /* simclock_GetTime */
                for (i = 0; i < n; i++) len += sprintf(line + len, " %c%c/%u", ty[i] & 0xff, ty[i] >> 8, fr[i]);
                mlog("%s", line);
            }
        }
    }
    if (g_coop_chain && *(volatile int *)0x00541030 && *(volatile int *)0x004c2164 == 5) {   /* a load-time network wait */
        static DWORD lastf, lastt, lastlog; DWORD now = GetTickCount();
        if (g_frame != lastf) { lastf = g_frame; lastt = now; }
        else if (lastt && now - lastt > 5000 && now - lastlog > 5000) {
            lastlog = now;
            mlog("  coop-chain: no mission frames for %lu s in state 5 - dpReceive called from %p (group %u, me %u, host %u, players %d, held AM '%s')",
                 (now - lastt) / 1000, __builtin_return_address(0), *(volatile WORD *)0x00541060, *(volatile WORD *)0x00541028,
                 *(volatile WORD *)0x00541064, ((int (__cdecl *)(void))0x00454610)(), g_coop_pending_am);
        }
    }
    if (g_coop_chain) {
        /* net_WaitForGroupThenEnumPlayers 0x454090 (every load) clears the group 0x541060 and loops dpReceive +
         * dpEnumGroups until a group shows up. After a chain reload the joiner sometimes never saw it again (stuck in
         * state 7 for minutes while the host went on; 1 of 3 fast-chain runs). The group id does not change across a
         * reload, so after 3 s of waiting it is put back from the last mission. */
        WORD gr = *(volatile WORD *)0x00541060;
        if (gr && *(volatile int *)0x004c2164 == 5) { g_coop_group = gr; g_coop_group_wait = 0; }
        else if (!gr && g_coop_group && *(volatile int *)0x00541030) {
            DWORD now = GetTickCount();
            if (!g_coop_group_wait) g_coop_group_wait = now;
            else if (now - g_coop_group_wait > 3000) {
                *(volatile WORD *)0x00541060 = g_coop_group; g_coop_group_wait = 0;
                mlog("  coop-chain: the session group did not come back after the reload - reusing %u", g_coop_group);
            }
        }
    }
    if (r != 0) g_coop_rx_run = 0;
    else {
        if (g_coop_rx_n < 64 && buf && from) { g_coop_rx_types[g_coop_rx_n] = *(WORD *)buf; g_coop_rx_from[g_coop_rx_n] = *(WORD *)from; g_coop_rx_n++; }
        if (++g_coop_rx_run == 2000 && g_coop_rx_logged < 3) {
            char line[64 * 12 + 64]; int i, len = sprintf(line, "  coop-ai: pump loop at 2000 packets; last types/from:");
            for (i = 0; i < g_coop_rx_n; i++) len += sprintf(line + len, " %c%c/%u", g_coop_rx_types[i] & 0xff, g_coop_rx_types[i] >> 8, g_coop_rx_from[i]);
            mlog("%s", line); g_coop_rx_logged++;
        }
        if (g_coop_rx_n >= 64) g_coop_rx_n = 0;
    }
    g_coop_ai_role = role;
    if (g_coop_reload_host && coop_chain_frames_running()) g_coop_reload_host = 0;   /* the reload is over: mission frames run */
    if (g_csg_mem) coop_script_guard_log();
    if (role == 1 && g_coop_test_host_respawn && g_coop_chain && coop_ai_in_mission() && (coop_chain_num((const char *)0x005049f0) || coop_scen_num((const char *)0x005049f0)))
        coop_auto_respawn("host (LAB I76_COOP_TEST_HOST_RESPAWN)");   /* LAB ONLY: the player asking for a respawn in the death view */
    if (role == 1) { coop_ai_host_send(); coop_obj_catchup(); if (g_coop_cb_qn) coop_cb_flush(); if (g_coop_obj_qn) coop_obj_flush(); }
    else if (role == 2) {
        coop_ai_joiner_fire();
        if (g_coop_chain) coop_near_trail();                 /* I76_COOP_NEAR_HOST: the host's path, for this joiner's next spawn */
        /* the joiner respawns by itself (RAISE_DEAD has no key) - in a co-op mission (coopNN.lvl) or a scenario
         * (autoNN.lvl) only. Until 2026-10-18 this ran in every network game with I76_COOP_CHAIN, melee included, so in
         * a melee the joiner came back 5 s after a death and the host did not (owner's playtest, laptop host + Michael,
         * Suburbia). Stock melee is stock. */
        if (g_coop_chain && coop_ai_in_mission() && (coop_chain_num((const char *)0x005049f0) || coop_scen_num((const char *)0x005049f0)))
            coop_auto_respawn("joiner");
    }
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AI_PKT) { g_coop_ai_rx++; coop_ai_apply((BYTE *)buf, *(int *)size); }
    if (role != 1 && r == 0 && buf && size && *(WORD *)buf == COOP_AM_PKT && *(volatile int *)0x00541030) coop_chain_receive((BYTE *)buf, *(int *)size);
    if (role != 1 && g_coop_chain) coop_chain_pending();
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AC_PKT) coop_cb_receive((BYTE *)buf, *(int *)size);
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AO_PKT) coop_obj_receive((BYTE *)buf, *(int *)size);
    { void aimelee_pump(int, int, void *, void *); aimelee_pump(role, r, buf, size); }   /* I76_AIMELEE (aimelee.c) */
    return r;
}
/* CO-OP CAMPAIGN CHAIN (I76_COOP_CHAIN=1 with I76_COOP_AI=1, both machines). A network game tears its in-game network
 * state down at mission end and goes back to the shell, which owns the connection. The Replay path (game state 7)
 * reloads WITHOUT the shell, and the reload runs net setup 0x452d40 again with the same session handle, so a mission
 * can be swapped in place. The co-op missions are installed as their own multiplayer arenas, ADDON\coop01.lvl ..
 * coop17.lvl (= T01..T17, tools/coop-install.py; the shell lists every addon\*.lvl after the 15 stock arenas, titled
 * "Co-op Scene N", docs/records/COOP-LIST-ENTRIES-2026-10-18.md). No stock arena is replaced, and the chain only acts
 * in a coopNN mission (a melee ends as the game decides). At `call 0x461810` 0x404110 (first call after the mission loop,
 * WinMain's stack balanced, before the outcome is read at 0x404123):
 *   - host, game state 1 (won): the next mission's name goes to the setup block WinMain copies from on every load
 *     ([esp+0x2b9] in WinMain = stub esp + 4 + 0x2b9; copied to 0x5049f0 at 0x403419) and to 0x5049f0, state 7, and an
 *     'AM' packet { u16 'AM', u8 0, u8 kind (1 next, 0 retry), char name[16] } goes to the joiner (3 copies);
 *     game state 0 / 0xb (lost): the same with the same mission (both retry); after m57 a win is left alone;
 *   - joiner: 'AM' (caught in the dpReceive hook) sets state 7 and queues the name, written here when its loop exits.
 *   - both: the teardown clears the network flag (0x453860, then `push 0; call 0x452d30` at 0x404662) and the reload
 *     re-initialises the network (0x452d40 with the setup block's session handle) only if the flag is set, so a pending
 *     chain reload passes 1 there (the shell does the same, `push 1` at 0x4024ea). Without it the reload came back as a
 *     single-player mission (measured 2026-10-07: player table empty, host stopped sending). */
static char g_coop_next[16];
static int g_coop_reload_pending;                           /* a chain reload: keep the game networked through teardown */
static DWORD g_coop_reload_frame;                           /* g_frame at the last chain reload (coop_chain_frames_running) */
static void __cdecl coop_netflag(int v) {                   /* replaces `call 0x452d30` (net flag := v) at 0x404662 */
    if (g_coop_reload_pending) { v = 1; g_coop_reload_pending = 0; mlog("  coop-chain: teardown keeps the network flag for the reload"); }
    ((void (__cdecl *)(int))0x00452d30)(v);
}
static int coop_chain_num(const char *cur) {                /* "coopNN.lvl" (any case) -> NN 1..17, else 0 */
    int n;
    if (_strnicmp(cur, "coop", 4) != 0 || cur[4] < '0' || cur[4] > '9' || cur[5] < '0' || cur[5] > '9') return 0;
    if (_stricmp(cur + 6, ".lvl") != 0) return 0;
    n = (cur[4] - '0') * 10 + (cur[5] - '0');
    return n >= 1 && n <= 17 ? n : 0;
}
static int coop_scen_num(const char *cur) {                 /* "autoNN.lvl" (any case) -> NN 1..7, else 0 */
    int n;
    if (_strnicmp(cur, "auto", 4) != 0 || cur[4] < '0' || cur[4] > '9' || cur[5] < '0' || cur[5] > '9') return 0;
    if (_stricmp(cur + 6, ".lvl") != 0) return 0;
    n = (cur[4] - '0') * 10 + (cur[5] - '0');
    return n >= 1 && n <= 7 ? n : 0;
}
static int coop_chain_next(const char *cur, char *out) {    /* coop01..coop16 -> +1, coop17 -> none */
    int n = coop_chain_num(cur);
    if (!n || n >= 17) return 0;
    sprintf(out, "coop%02d.lvl", n + 1);
    return 1;
}
/* The join reply ('JO', net_SendJoinAccept 0x455fa0) carries the mission name (0x5049f0, at +0x32) and [0x504a04] (at
 * +0x44), which the shell set ONCE at the network start (0x40253e, from its setup +0x6c) to the CRC-32 of addon\<name>
 * when the arena is an addon .lvl (Crc32_File 0x10022bc0 in i76shell, poly 0x04C11DB7, MSB first, init/xorout ~0).
 * A joiner's shell (0x1002fcd8) compares it with the CRC of its own addon\<name> and refuses the join on a mismatch.
 * After a chain reload the name changes, so the host puts the new file's CRC there too, or a late joiner would be
 * refused with "Your mission file coop02.lvl does not match the host's". Only when the slot holds the old file's CRC. */
static int coop_addon_crc(const char *name, DWORD *out) {
    static DWORD tab[256]; static int built; char path[64]; BYTE buf[4096]; DWORD got, c = 0xffffffff; HANDLE h;
    if (!built) { DWORD i, k, v; for (i = 0; i < 256; i++) { v = i << 24; for (k = 0; k < 8; k++) v = (v & 0x80000000) ? (v << 1) ^ 0x04c11db7 : v << 1; tab[i] = v; } built = 1; }
    _snprintf(path, sizeof(path) - 1, "addon\\%s", name); path[sizeof(path) - 1] = 0;
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return 0;
    while (ReadFile(h, buf, sizeof(buf), &got, NULL) && got) { DWORD i; for (i = 0; i < got; i++) c = (c << 8) ^ tab[(c >> 24) ^ buf[i]]; }
    CloseHandle(h);
    *out = ~c;
    return 1;
}
static void coop_chain_crc(const char *cur, const char *next) {
    volatile DWORD *slot = (volatile DWORD *)0x00504a04; DWORD a, b;
    if (!coop_addon_crc(cur, &a) || !coop_addon_crc(next, &b)) { mlog("  coop-chain: join CRC not updated (addon\\%s or addon\\%s unreadable)", cur, next); return; }
    if (*slot != a) { mlog("  coop-chain: join CRC slot %08lx is not addon\\%s's %08lx - left alone", (unsigned long)*slot, cur, (unsigned long)a); return; }
    *slot = b;
    mlog("  coop-chain: join CRC %08lx (%s) -> %08lx (%s)", (unsigned long)a, cur, (unsigned long)b, next);
}
static BYTE g_coop_am_seq;                                  /* host: number of the reload; joiner: last one applied */
static void coop_chain_send(int kind, const char *name) {
    BYTE pkt[20 + COOP_DP_SLACK]; int i;
    memset(pkt, 0, sizeof(pkt));
    if (++g_coop_am_seq == 0) g_coop_am_seq = 1;
    *(WORD *)pkt = COOP_AM_PKT; pkt[2] = g_coop_am_seq; pkt[3] = (BYTE)kind; strncpy((char *)pkt + 4, name, 15);
    for (i = 0; i < 3; i++)
        if (((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028,
                                                ((WORD (__cdecl *)(void))0x00454e10)(), 0, pkt, 20) == 0) g_coop_chain_sent++;
}
static void __cdecl coop_chain_at_end(char *winmain_esp) {
    volatile int *state = (volatile int *)0x004c2164;
    char *setup_name = winmain_esp + 0x2b9, *cur = (char *)0x005049f0;
    int role = coop_ai_role();
    /* co-op entries and scenarios (autoNN.lvl, 2026-10-19): a loss reloads the same file for everybody; a won co-op
     * mission loads the next one, a won scenario (or coop17) ends normally. The scenario scripts watch the host's car
     * (the entity "user", resolved once at load), so the host does not auto-respawn: its death is the scenario's loss
     * (records/COOP-LIST-ENTRIES-2026-10-18.md section 8). */
    if (role == 1 && (*state == 1 || *state == 0 || *state == 0xb) && (coop_chain_num(cur) || coop_scen_num(cur))) {
        char next[16];
        int won = *state == 1;
        if (won && !coop_chain_next(cur, next)) { mlog("  coop-chain: '%s' won and nothing follows it - normal end", cur); return; }
        if (!won) { strncpy(next, cur, 15); next[15] = 0; }
        coop_chain_send(won, next);
        if (won) coop_chain_crc(cur, next);
        strncpy(g_coop_next, next, 15); g_coop_next[15] = 0;
        *state = 7;
        mlog("  coop-chain: host %s '%s' -> loading '%s' in the same session (AM sent x%ld)", won ? "won" : "lost", cur, next, g_coop_chain_sent);
    }
    if (*state == 7 && g_coop_next[0]) {
        g_coop_reload_pending = 1;
        g_coop_reload_host = role == 1;                      /* the host's handshake after this reload is not left waiting (dpReceive hook) */
        g_coop_reload_frame = g_frame;
        /* exactly strlen + 1 bytes: the setup block's field size is not known, and a 16-byte strncpy zero-filled
         * whatever follows "mNN.msn" (suspect for the rare teardown heap crash, 2026-10-07) */
        { size_t L = strlen(g_coop_next); if (L > 12) L = 12; memcpy(setup_name, g_coop_next, L); setup_name[L] = 0; memcpy(cur, g_coop_next, L); cur[L] = 0; }
        mlog("  coop-chain: %s reloads as '%s' (reload #%u)", role == 1 ? "host" : "joiner", g_coop_next, g_coop_am_seq);
        g_coop_next[0] = 0;
    }
}
static __declspec(naked) void coop_chain_stub(void) {       /* replaces `call 0x461810` at 0x404110 */
    __asm {
        mov eax, 0x00461810
        call eax
        lea eax, [esp + 4]                      /* WinMain's esp before this call */
        push eax
        call coop_chain_at_end
        add esp, 4
        ret
    }
}
/* "In the mission" for the chain means mission FRAMES are running: state 5 and a world root are already true inside a
 * load's network wait (main thread in the WIPX receive, no mission frames), and an 'AM' that set state 7 there left
 * the joiner in that wait for good (soak 2026-10-07: the host won the mission the joiner was still loading). So:
 * more than 10 mission frames since this machine's last chain reload, the latest one less than half a second ago. */
static int coop_chain_frames_running(void) {
    static DWORD lastf, lastt; DWORD now = GetTickCount();
    if (g_frame != lastf) { lastf = g_frame; lastt = now; }
    return lastt && now - lastt < 500 && g_frame - g_coop_reload_frame > 10 && coop_ai_in_mission();
}
static void coop_chain_receive(BYTE *pkt, int size) {      /* joiner (or not yet sure), in the pump */
    if (size < 20 || !g_coop_chain) return;
    /* the 3 copies of one reload: the 2nd and 3rd often sit in the queue through the joiner's load and arrived once its
     * mission ran, which reloaded it a second time and left it stuck in state 7 (fast-chain run 2026-10-07) */
    if (pkt[2] && pkt[2] == g_coop_am_seq) return;
    if (pkt[2]) g_coop_am_seq = pkt[2];
    g_coop_chain_got++;
    if (!coop_chain_frames_running()) {                      /* loading: keep it for when the mission runs */
        strncpy(g_coop_pending_am, (char *)pkt + 4, 15); g_coop_pending_am[15] = 0;
        return;
    }
    strncpy(g_coop_next, (char *)pkt + 4, 15); g_coop_next[15] = 0;
    *(volatile int *)0x004c2164 = 7;
}
static void coop_chain_pending(void) {                       /* every pump call: a held 'AM' once the mission runs */
    if (!g_coop_pending_am[0] || !coop_chain_frames_running()) return;
    if (_strnicmp(g_coop_pending_am, (char *)0x005049f0, 8) == 0) { g_coop_pending_am[0] = 0; return; }   /* already there */
    strncpy(g_coop_next, g_coop_pending_am, 15); g_coop_next[15] = 0; g_coop_pending_am[0] = 0;
    *(volatile int *)0x004c2164 = 7;
    mlog("  coop-chain: applying an 'AM' that arrived during the load -> '%s'", g_coop_next);
}
/* Enemies only know one player: the scripts aim at "player" (the host's car). On the host, all 9 calls of
 * ai_SetBehaviour 0x412830 go through here; any behaviour with a human target except follow (0x1e) retargets to the
 * nearest live human car (wingmen still follow the script's player). First version only did attack/evade/race: in T05
 * t05cm03 stayed on the host 700 m away with the joiner 27 m from it (another behaviour). T04's gang
 * uses only evade (0x412fad, behaviour 24, the player as threat; I76_COOP_AI_DIAG=1 counts per site), and fires from
 * ai_SetBehaviour's fire decision at that target. The joiner sees the fire through the replayed triggers and takes the
 * hits on its own car. */
static int __cdecl coop_ai_attack(BYTE *a, BYTE *t, int b, int x) {
    int human = 0, k0;
    if (t && (t[0x10] & 0x10)) human = 1;
    else if (t) for (k0 = 0; k0 < 16; k0++) { BYTE *p = (BYTE *)0x00541070 + k0 * 0x48; if (*(WORD *)p && *(BYTE **)(p + 0x28) == t) { human = 1; break; } }
    if (b != 0x1e && a && t && !human && coop_ai_role() == 1 && coop_scen_num((const char *)0x005049f0))
        mpf_engaged(a);                                      /* scenarios (2026-10-24): an enemy given ANY target is in the fight (Oil Well Well's go for the
                                                                wells, measured: 1 of 8 originals turned on a human in 90 s); its copies come in and attack humans */
    if (b != 0x1e && a && human && coop_ai_role() == 1) {   /* every behaviour aimed at a human except follow */
        mpf_engaged(a);                                      /* co-op scaling: this enemy has met a human (mpfill.c) */
        double ax = *(double *)(a + 0x40), az = *(double *)(a + 0x50), best = 1e30; BYTE *pick = t; int k;
        for (k = 0; k < 16; k++) {
            BYTE *p = (BYTE *)0x00541070 + k * 0x48, *o;
            if (!*(WORD *)p || !(o = *(BYTE **)(p + 0x28)) || !*(BYTE **)(o + 0x70) || ((*(BYTE **)(o + 0x70))[0x454] & 0x20)) continue;
            { double dx = *(double *)(o + 0x40) - ax, dz = *(double *)(o + 0x50) - az, d = dx * dx + dz * dz; if (d < best) { best = d; pick = o; } }
        }
        if (pick != t) g_coop_retarget++;
        t = pick;
    }
    return ((int (__cdecl *)(BYTE *, BYTE *, int, int))0x00412830)(a, t, b, x);
}
static LONG g_coop_sb_hist[9][40];                          /* diagnostics (I76_COOP_AI_DIAG=1): ai_SetBehaviour behaviour ids per site */
static LONG g_coop_sb_human[9];
#define COOP_SB_STUB(n) static int __cdecl coop_sb_##n(BYTE *a, BYTE *t, int b, int x) { \
    int k; if (b >= 0 && b < 40) g_coop_sb_hist[n][b]++; \
    if (t && (t[0x10] & 0x10)) g_coop_sb_human[n]++; else if (t) for (k = 0; k < 16; k++) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; if (*(WORD *)p && *(BYTE **)(p + 0x28) == t) { g_coop_sb_human[n]++; break; } } \
    return coop_ai_attack(a, t, b, x); }
COOP_SB_STUB(0) COOP_SB_STUB(1) COOP_SB_STUB(2) COOP_SB_STUB(3) COOP_SB_STUB(4) COOP_SB_STUB(5) COOP_SB_STUB(6) COOP_SB_STUB(7) COOP_SB_STUB(8)
static void coop_sb_log(void) {
    char line[900]; int n, b, len;
    static const DWORD sites[9] = { 0x40a232, 0x412dac, 0x412def, 0x412e32, 0x412e9c, 0x412f11, 0x412fad, 0x413049, 0x414046 };
    len = sprintf(line, "  coop-ai diag: SetBehaviour calls by site:");
    for (n = 0; n < 9; n++) {
        int any = 0; for (b = 0; b < 40; b++) if (g_coop_sb_hist[n][b]) any = 1;
        if (!any) continue;
        len += sprintf(line + len, " [%06lx human %ld:", (unsigned long)sites[n], g_coop_sb_human[n]);
        for (b = 0; b < 40; b++) if (g_coop_sb_hist[n][b]) len += sprintf(line + len, " b%d=%ld", b, g_coop_sb_hist[n][b]);
        len += sprintf(line + len, "]");
    }
    mlog("%s", line);
}
/* The mission's own player object (the ODEF record with objFlags 0x10, label e.g. 'vppirna1') is what the script
 * watches ("keep up", "isDead player", attack targets). A network game spawns a NEW car for every player (0x451180),
 * so the host drove a different object and the script followed a stand-in (measured 2026-10-07 in T05: label object
 * 0x136EF034 flags 0x10810 vs the host's table car 0x1371F16C flags 0x810, 3 km apart). With I76_COOP_CHAIN the spawn
 * of the HOST's car instead adopts the unclaimed mission player object, on both machines: linked to the host's id
 * through 0x454750 (table car + entity+0x480); on the joiner it is the host's remote car (flag 0x10 -> 0x20, as
 * 0x451180 marks remote cars). On the joiner that object carries the joiner's car model (the player vcf substitution
 * uses the local car name 0x5dd370): cosmetic. A host respawn finds it claimed and spawns normally (the mission has
 * failed by then). */
static BYTE *coop_find_mission_player(void) {
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i, k;
    if (!tab || count <= 0 || count > 2048) return NULL;
    for (i = 0; i < count; i++) {
        BYTE *o = *(BYTE **)(tab + i * 16 + 8);
        if (!o || *(int *)(o + 0x6c) != 1 || !(o[0x10] & 0x10) || !*(BYTE **)(o + 0x70) || ((*(BYTE **)(o + 0x70))[0x454] & 0x20)) continue;
        for (k = 0; k < 16; k++) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; if (*(WORD *)p && *(BYTE **)(p + 0x28) == o) break; }
        if (k == 16) return o;
    }
    return NULL;
}
/* The host's car model on the joiner. The object loader 0x4ad6f0 gives every player-flagged (0x10) object the LOCAL
 * car file (`push 0x5dd370` 0x4ad750, the path the multiplayer menu set), so on the joiner the mission player object,
 * which shows the host, had the joiner's car (and its weapon layout). The host is not known yet while a mission loads
 * (host id 0, measured), but its car file is on disk from the mission before: the network join sends the host's .vcf
 * and 0x455e60 writes it as nvclN.vcf, the name in the host's player table slot. So on a chain reload the joiner
 * loads the mission player object from that file, if the game can open it (0x470340, the loader's own lookup).
 * The first mission of a session still shows the joiner's model. Removing the object and showing the host's own
 * network car instead crashed the joiner in the mission code that still refers to the player object (0x40c084). */
static char g_coop_host_car[16];
static const char *__cdecl coop_player_car(BYTE *o) {
    const char *local = (const char *)0x005dd370;
    if (!g_coop_chain || !g_coop_adopt || !g_coop_hostmodel || !g_coop_host_car[0] || !*(volatile int *)0x00541030) return local;
    if (!o || !(o[0x10] & 0x10) || *(volatile WORD *)0x00541064) return local;   /* only during the load (host still 0) */
    if (!((BYTE (__cdecl *)(const char *))0x00470340)(g_coop_host_car)) {
        mlog("  coop-chain: mission player object - the host's '%s' cannot be opened, local car", g_coop_host_car);
        return local;
    }
    mlog("  coop-chain: mission player object loads the host's car '%s' (local is '%s')", g_coop_host_car, local);
    return g_coop_host_car;
}
static __declspec(naked) void coop_player_car_stub(void) {  /* replaces `push 0x5dd370` 0x4ad750 (5 bytes) */
    __asm {
        mov eax, [ebx]                          /* the object being loaded (0x4ad711) */
        push eax
        call coop_player_car
        add esp, 4
        pop ecx                                 /* our return address */
        push eax                                /* what the original pushed */
        jmp ecx
    }
}
/* JOINER SPAWNS NEAR THE HOST (I76_COOP_NEAR_HOST, default 1; acts only with I76_COOP_CHAIN, in coopNN.lvl / autoNN.lvl,
 * owner 2026-10-24: "a joiner who respawns should appear NEAR THE HOST, not at the mission's own spawn").
 * The local car of every machine is built by 0x451180(own id, 0x451030() = a random free spawn point, type 0) at the
 * WinMain / pump sites 0x403ab8, 0x403cd5, 0x456f17 (records/LAN-FIXES-2026-10-24.md s.3); 0x451180 copies the 0x40-byte
 * spawn entry 0x53fd88 + idx * 0x40 (rotation rows right / up / forward, 9 floats; position doubles at +0x28) to the new
 * object's +0x18. Remote machines see the car where its owner's 'ST' puts it, so only the owner's own build matters.
 * On a joiner whose host car is alive, that entry is replaced for the one call (and put back) by a pose near the host:
 *   - the host's TRAIL: every 250 ms the joiner keeps the host car's position (64 points, 16 s). The newest trail point
 *     20-40 m from where the host is now, with no car or wreck within 10 m, is ground the host has just driven: on its
 *     road, behind it. Else a point 25 / 30 / 35 m behind the host (0 / +-8 m to the side), then 25 m to either side,
 *     with the same clearance and its ground within 5 m of the host's.
 *   - height: the ground there (0x493550, the sim's own query) + 1.5 m (the car drops onto it);
 *   - facing: the host's heading (yaw only).
 * No candidate (the host is dead, gone, or boxed in): the stock spawn point. Logged as "coop-near-host". */
static int g_coop_near = 1;
static BYTE *g_coop_mp_obj;                                  /* the mission player object adopted for the host in this load (coop_spawn) */
#define COOP_TRAIL 64
static double g_ct_x[COOP_TRAIL], g_ct_z[COOP_TRAIL]; static int g_ct_n, g_ct_head; static BYTE *g_ct_car; static DWORD g_ct_last;
static BYTE *coop_host_car(void) {
    WORD host = *(volatile WORD *)0x00541064; int k;
    if (!host) return NULL;
    for (k = 0; k < 16; k++) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; if (*(WORD *)p == host) return *(BYTE **)(p + 0x28); }
    return NULL;
}
static int coop_car_alive(BYTE *o) {
    BYTE *e = (o && !IsBadReadPtr(o, 0x74)) ? *(BYTE **)(o + 0x70) : NULL;
    return e && !IsBadReadPtr(e, 0x458) && !(e[0x454] & 0x20);
}
static BYTE *g_cn_placed, *g_cn_seen; static DWORD g_cn_seen_t; static int g_cn_fix;
static int coop_near_pick(BYTE *h, double *ox, double *oz, char *how);
static void coop_near_after_join(BYTE *h) {
    /* A JOIN builds the joiner's car while the host is not known yet (host id 0 during the handshake, so the spawn above
     * cannot act; measured: 313 m from the host). The first time this joiner's car is seen in a co-op mission, not built
     * by coop_spawn_near_host and more than 60 m from a live host, it is moved once within 10 s: the same pick, the pose
     * written on the game thread (rotation rows, position, velocity / body rates / speed 0, as the trainer's TELEPORT +
     * STOP). The host and the other joiners see it there from its next 'ST'. */
    BYTE **root = ((BYTE **(__cdecl *)(void))0x00457530)(), *o = root ? *root : NULL, *e; DWORD now = GetTickCount();
    double x, z, dx, dz; char how[96]; float fx, fz, r;
    if (!o) return;
    if (o != g_cn_seen) { g_cn_seen = o; g_cn_seen_t = now; g_cn_fix = o != g_cn_placed; }
    if (!g_cn_fix || now - g_cn_seen_t > 10000 || !h || !coop_car_alive(h) || !coop_car_alive(o)) { if (now - g_cn_seen_t > 10000) g_cn_fix = 0; return; }
    if (!coop_chain_num((const char *)0x005049f0) && !coop_scen_num((const char *)0x005049f0)) { g_cn_fix = 0; return; }
    dx = *(double *)(o + 0x40) - *(double *)(h + 0x40); dz = *(double *)(o + 0x50) - *(double *)(h + 0x50);
    if (dx * dx + dz * dz < 60.0 * 60.0) { g_cn_fix = 0; return; }
    if (now - g_cn_seen_t < 1000 || !coop_near_pick(h, &x, &z, how)) return;   /* let the car settle a moment first */
    g_cn_fix = 0;
    fx = *(float *)(h + 0x18 + 24); fz = *(float *)(h + 0x18 + 32); r = (float)sqrt((double)fx * fx + (double)fz * fz);
    if (r < 1e-3f) { fx = 0.0f; fz = 1.0f; r = 1.0f; }
    fx /= r; fz /= r;
    {   float *m = (float *)(o + 0x18); memset(m, 0, 9 * sizeof(float)); m[0] = fz; m[2] = -fx; m[4] = 1.0f; m[6] = fx; m[8] = fz; }
    *(double *)(o + 0x40) = x; *(double *)(o + 0x50) = z; *(double *)(o + 0x48) = ((double (__cdecl *)(double, double))0x00493550)(x, z) + 1.5;
    e = *(BYTE **)(o + 0x70);
    if (e) { memset(e + 0xbc, 0, 12); memset(e + 0xc8, 0, 12); *(float *)(e + 0xac) = 0.0f; *(float *)(e + 0xb0) = 0.0f; }
    mlog("  coop-near-host: t %lu joiner's car (built at the join, %.0f m from the host) moved to %.1f,%.1f heading %d (%s)",
         now, sqrt(dx * dx + dz * dz), x, z, (int)(atan2(fx, fz) * 57.29578), how);
}
static void coop_near_trail(void) {                          /* joiner, every pump call: the host car's recent path */
    DWORD now = GetTickCount(); BYTE *h;
    if (!g_coop_near || now - g_ct_last < 250) return;
    g_ct_last = now;
    h = coop_ai_in_mission() ? coop_host_car() : NULL;
    coop_near_after_join(h);
    if (!h || !coop_car_alive(h)) { g_ct_n = 0; g_ct_car = NULL; return; }
    if (h != g_ct_car) { g_ct_n = 0; g_ct_car = h; }         /* a new mission or a new host car: a new trail */
    if (g_ct_n) {                                            /* a jump of > 80 m in 250 ms is a teleport / reload, not a path */
        int p = (g_ct_head + COOP_TRAIL - 1) % COOP_TRAIL; double dx = *(double *)(h + 0x40) - g_ct_x[p], dz = *(double *)(h + 0x50) - g_ct_z[p];
        if (dx * dx + dz * dz > 80.0 * 80.0) g_ct_n = 0;
    }
    g_ct_x[g_ct_head] = *(double *)(h + 0x40); g_ct_z[g_ct_head] = *(double *)(h + 0x50);
    g_ct_head = (g_ct_head + 1) % COOP_TRAIL; if (g_ct_n < COOP_TRAIL) g_ct_n++;
}
static double coop_near_clear(double x, double z) {          /* squared distance to the nearest car or wreck (players' and mission cars) */
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i, k; double best = 1e30;
    for (k = 0; k < 16; k++) {
        BYTE *p = (BYTE *)0x00541070 + k * 0x48, *o = *(WORD *)p ? *(BYTE **)(p + 0x28) : NULL;
        if (o && !IsBadReadPtr(o, 0x58)) { double dx = *(double *)(o + 0x40) - x, dz = *(double *)(o + 0x50) - z; if (dx * dx + dz * dz < best) best = dx * dx + dz * dz; }
    }
    for (i = 0; tab && count > 0 && count <= 2048 && i < count; i++) {
        BYTE *o = coop_ai_object(i, count, tab);
        if (o) { double dx = *(double *)(o + 0x40) - x, dz = *(double *)(o + 0x50) - z; if (dx * dx + dz * dz < best) best = dx * dx + dz * dz; }
    }
    return best;
}
static int coop_near_pick(BYTE *h, double *ox, double *oz, char *how) {
    double hx = *(double *)(h + 0x40), hz = *(double *)(h + 0x50), hg, r;
    float fx = *(float *)(h + 0x18 + 24), fz = *(float *)(h + 0x18 + 32); int i, j;
    static const double back[3] = { 25.0, 30.0, 35.0 }, side[3] = { 0.0, 8.0, -8.0 };
    for (i = 1; i <= g_ct_n; i++) {                          /* newest first */
        int p = (g_ct_head + COOP_TRAIL - i) % COOP_TRAIL; double dx = g_ct_x[p] - hx, dz = g_ct_z[p] - hz, d2 = dx * dx + dz * dz;
        if (d2 < 20.0 * 20.0 || d2 > 40.0 * 40.0 || coop_near_clear(g_ct_x[p], g_ct_z[p]) < 10.0 * 10.0) continue;
        *ox = g_ct_x[p]; *oz = g_ct_z[p]; sprintf(how, "the host's trail %.2f s ago, %.1f m from it", i * 0.25, sqrt(d2));
        return 1;
    }
    r = sqrt((double)fx * fx + (double)fz * fz); if (r < 1e-3) { fx = 0.0f; fz = 1.0f; r = 1.0; }
    fx = (float)(fx / r); fz = (float)(fz / r);
    hg = ((double (__cdecl *)(double, double))0x00493550)(hx, hz);
    for (i = 0; i < 5; i++) for (j = 0; j < 3; j++) {
        double b = i < 3 ? back[i] : 0.0, s = i < 3 ? side[j] : (i == 3 ? 25.0 : -25.0), x, z;
        if (i >= 3 && j) continue;
        x = hx - fx * b + fz * s; z = hz - fz * b - fx * s;  /* right = (fz, 0, -fx) */
        if (coop_near_clear(x, z) < 10.0 * 10.0) continue;
        if (fabs(((double (__cdecl *)(double, double))0x00493550)(x, z) - hg) > 5.0) continue;
        *ox = x; *oz = z; sprintf(how, "%.0f m behind the host, %.0f m to its side", b, s);
        return 1;
    }
    return 0;
}
static char *coop_spawn_near_host(unsigned id, int idx, int type, void *data, size_t size, int *done) {
    BYTE *h = coop_host_car(), *e, save[0x40]; double x, z, y; char how[96]; char *o; float fx, fz, r;
    *done = 0;
    if (!g_coop_near || type != 0 || idx < 0 || idx >= 64 || !h || !coop_car_alive(h) || !coop_ai_in_mission()) return NULL;
    if (!coop_chain_num((const char *)0x005049f0) && !coop_scen_num((const char *)0x005049f0)) return NULL;
    if (!coop_near_pick(h, &x, &z, how)) { mlog("  coop-near-host: no clear place near the host - stock spawn point %d", idx); return NULL; }
    e = (BYTE *)0x0053fd88 + idx * 0x40;
    memcpy(save, e, 0x40);
    fx = *(float *)(h + 0x18 + 24); fz = *(float *)(h + 0x18 + 32); r = (float)sqrt((double)fx * fx + (double)fz * fz);
    if (r < 1e-3f) { fx = 0.0f; fz = 1.0f; r = 1.0f; }
    fx /= r; fz /= r;
    memset(e, 0, 0x28);
    ((float *)e)[0] = fz; ((float *)e)[2] = -fx;              /* right */
    ((float *)e)[4] = 1.0f;                                   /* up */
    ((float *)e)[6] = fx; ((float *)e)[8] = fz;               /* forward = the host's heading */
    *(double *)(e + 0x28) = x; *(double *)(e + 0x38) = z;
    y = ((double (__cdecl *)(double, double))0x00493550)(x, z) + 1.5;
    *(double *)(e + 0x30) = y;
    o = ((char *(__cdecl *)(unsigned, int, int, void *, size_t))0x00451180)(id, idx, type, data, size);
    memcpy(e, save, 0x40);
    *done = 1; g_cn_placed = (BYTE *)o;
    {   double dx = x - *(double *)(h + 0x40), dz = z - *(double *)(h + 0x50);
        mlog("  coop-near-host: t %lu joiner (id %u) spawns %.1f m from the host at %.1f,%.1f,%.1f heading %d (%s; stock spawn point %d)",
             GetTickCount(), id, sqrt(dx * dx + dz * dz), x, y, z, (int)(atan2(fx, fz) * 57.29578), how, idx); }
    return o;
}
static char *__cdecl coop_spawn(unsigned id, int idx, int type, void *data, size_t size) {   /* replaces `call 0x451180` x7 */
    WORD host = *(volatile WORD *)0x00541064, me = *(volatile WORD *)0x00541028;
    /* The HOST's respawn in a co-op scene / scenario (records/LAN-FIXES-2026-10-24.md s.6). The host's car there is the
     * mission's player object (adopted below), the one the script names; a respawn builds a new car and removes it
     * (0x451180: 0x4575d0 + 0x465310), the script's next action on "player" resolves NULL and the game dies (the owner's
     * host crash at +0x684BD). The host's death already fails the mission and the chain reloads it for everybody (~7 s),
     * so a respawn of the host in these missions is not built, on any machine: the dead car stays until the reload. */
    if (g_coop_chain && g_coop_adopt && *(volatile int *)0x00541030 && host && (WORD)id == host && g_coop_mp_obj &&
        (coop_chain_num((const char *)0x005049f0) || coop_scen_num((const char *)0x005049f0)) && coop_host_car() == g_coop_mp_obj &&
        !coop_car_alive(g_coop_mp_obj)) {
        static DWORD said;
        if (GetTickCount() - said > 3000) { said = GetTickCount(); mlog("  coop-chain: the host's respawn (id %u) is not built in a co-op mission - its car is the mission's player object; the mission's loss reloads it", id); }
        return (char *)g_coop_mp_obj;
    }
    if (g_coop_chain && *(volatile int *)0x00541030 && host && me && (WORD)id == me && me != host) {
        int done; char *o = coop_spawn_near_host(id, idx, type, data, size, &done);
        if (done) return o;
    }
    if (g_coop_chain && g_coop_adopt && *(volatile int *)0x00541030 && host && (WORD)id == host) {
        BYTE *o = coop_find_mission_player();
        if (o) {
            unsigned __int64 nm = ((unsigned __int64 (__cdecl *)(short))0x00454800)((short)id);
            if (!nm && data && size) nm = ((unsigned __int64 (__cdecl *)(void *, size_t))0x00455e60)(data, size);
            if ((WORD)id != me) {
                char nm9[9]; int k;
                *(DWORD *)(o + 0x10) = (*(DWORD *)(o + 0x10) & ~0x10u) | 0x20;
                for (k = 0; k < 8; k++) nm9[k] = (char)(((BYTE *)&nm)[k] & 0x7f);
                nm9[8] = 0;
                if (nm9[0]) sprintf(g_coop_host_car, "%s.vcf", nm9);   /* for the next load, coop_player_car */
            }
            ((int (__cdecl *)(short, DWORD, DWORD, BYTE *))0x00454750)((short)id, (DWORD)nm, (DWORD)(nm >> 32), o);
            g_coop_adopted++; g_coop_mp_obj = o;
            mlog("  coop-chain: host (id %u) %s the mission's player object %p (%.8s; model %.8s)", id, (WORD)id == me ? "drives" : "is shown as", o, (char *)&nm, (char *)o);
            return (char *)o;
        }
    }
    return ((char *(__cdecl *)(unsigned, int, int, void *, size_t))0x00451180)(id, idx, type, data, size);
}
/* CB radio (the story's voice lines and the AI's taunts) is played by 0x423620(file, speaker object, priority). On the
 * joiner the script and AI are off, so nothing played. The host forwards the game-logic calls (0x40a0f8 AI, the script
 * actions' 0x40bfcc / 0x40bfee / 0x40c011 / 0x40c029 and cb 0x41348f) as 'AC' { u16 'AC', u8 0, u8 priority,
 * i16 speaker label index (-1 none), u16 0, char file[32] } and the joiner plays the same line. */
static int coop_label_index(BYTE *o) {
    BYTE *tab = *(BYTE **)(0x0054a178 + 4); int count = *(int *)(0x0054a178 + 8), i;
    if (!o || !tab || count <= 0 || count > 2048) return -1;
    for (i = 0; i < count; i++) if (*(BYTE **)(tab + i * 16 + 8) == o) return i;
    return -1;
}
static BYTE g_coop_cb_q[8][40 + COOP_DP_SLACK];                             /* queued here, sent from the pump */
static int __cdecl coop_cb_play(char *file, BYTE *speaker, int prio) {
    /* Sending from here (inside the script / AI frame) crashed the host in the script dispatcher's epilogue
     * (0x4144d1, esi corrupt; 1 of 1 runs with it, 0 of 1 without); the line is queued and sent from the pump. */
    if (coop_ai_role() == 1 && file && g_coop_cb_qn < 8) {
        BYTE *pkt = g_coop_cb_q[g_coop_cb_qn]; memset(pkt, 0, 40);
        *(WORD *)pkt = COOP_AC_PKT; pkt[3] = (BYTE)prio; *(short *)(pkt + 4) = (short)coop_label_index(speaker);
        strncpy((char *)pkt + 8, file, 31);
        g_coop_cb_qn++;
    }
    return ((int (__cdecl *)(char *, BYTE *, int))0x00423620)(file, speaker, prio);
}
static void coop_cb_flush(void) {                            /* host, in the pump */
    LONG i, n = g_coop_cb_qn;
    for (i = 0; i < n; i++)
        if (((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028,
                                                ((WORD (__cdecl *)(void))0x00454e10)(), 0, g_coop_cb_q[i], 40) == 0) g_coop_cb_sent++;
    g_coop_cb_qn = 0;
}
static void coop_cb_receive(BYTE *pkt, int size) {           /* joiner, in the pump */
    BYTE *tab, *o = NULL; int count, li; char file[32];
    if (size < 40 || !coop_ai_in_mission()) return;
    li = *(short *)(pkt + 4); tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (li >= 0 && tab && li < count && count <= 2048) o = *(BYTE **)(tab + li * 16 + 8);
    memcpy(file, pkt + 8, 31); file[31] = 0;
    ((int (__cdecl *)(char *, BYTE *, int))0x00423620)(file, o, pkt[3]);
    g_coop_cb_played++;
}
/* Objectives: the script's success / fail / reveal actions (calls at 0x4136b1 fsm_Success 0x45e9e0, 0x4136c7 fsm_Fail
 * 0x45ea90, 0x41420e reveal 0x40be50 -> 0x45e960) run on the host only; forwarded as 'AO' { u16 'AO', u8 0, u8 kind
 * (1 success, 2 fail, 3 reveal), int objective } so the buddy's notepad (and its chime) follows. A repeat is harmless:
 * the functions' error path 0x42d5d0 is empty. Objective table: count 0x6093c0, valid 0x6093c8[i], flags 0x609420[i]
 * (1 hidden, 2 succeeded, 4 failed). A player who joins late gets every objective's flags once (kind 4, written
 * directly, no chime). */
static int g_coop_obj_q[16][2];
static void coop_obj_queue(int kind, int n) { if (coop_ai_role() == 1 && g_coop_obj_qn < 16) { g_coop_obj_q[g_coop_obj_qn][0] = kind; g_coop_obj_q[g_coop_obj_qn][1] = n; g_coop_obj_qn++; } }
static void __cdecl coop_obj_success(int n) { coop_obj_queue(1, n); ((void (__cdecl *)(int))0x0045e9e0)(n); }
static void __cdecl coop_obj_fail(int n) { coop_obj_queue(2, n); ((void (__cdecl *)(int))0x0045ea90)(n); }
static void __cdecl coop_obj_reveal(int *p) { if (p) coop_obj_queue(3, *p); ((void (__cdecl *)(int *))0x0040be50)(p); }
static void coop_obj_flush(void) {
    LONG i, n = g_coop_obj_qn;
    for (i = 0; i < n; i++) {
        BYTE pkt[8 + COOP_DP_SLACK]; *(WORD *)pkt = COOP_AO_PKT; pkt[2] = 0; pkt[3] = (BYTE)g_coop_obj_q[i][0]; *(int *)(pkt + 4) = g_coop_obj_q[i][1];
        if (((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028,
                                                ((WORD (__cdecl *)(void))0x00454e10)(), 0, pkt, 8) == 0) g_coop_obj_sent++;
    }
    g_coop_obj_qn = 0;
}
static void coop_obj_receive(BYTE *pkt, int size) {          /* joiner, in the pump */
    int n;
    if (size < 8 || !coop_ai_in_mission()) return;
    n = *(int *)(pkt + 4);
    if (pkt[3] != 4 && (n < 1 || n > 32)) return;
    if (pkt[3] == 1) ((void (__cdecl *)(int))0x0045e9e0)(n);
    else if (pkt[3] == 2) ((void (__cdecl *)(int))0x0045ea90)(n);
    else if (pkt[3] == 3) ((void (__cdecl *)(int))0x0045e960)(n);
    else if (pkt[3] == 4) {                                  /* catch-up: raw flags, no chime */
        int f = (*(int *)(pkt + 4) >> 8) & 7, i = (*(int *)(pkt + 4) & 0xff) - 1;
        if (i >= 0 && i < *(volatile int *)0x006093c0 && ((int *)0x006093c8)[i]) ((int *)0x00609420)[i] = (((int *)0x00609420)[i] & ~7) | f;
    }
    g_coop_obj_got++;
}
static void coop_obj_catchup(void) {                         /* host: a newcomer with a car for 3 s -> every objective's flags */
    static WORD seen[16]; static DWORD carsince[16]; static DWORD last; DWORD now = GetTickCount(); int k, j, fresh = 0;
    if (now - last < 1000) return;
    last = now;
    if (!coop_ai_in_mission()) { memset(seen, 0, sizeof(seen)); memset(carsince, 0, sizeof(carsince)); return; }
    for (k = 0; k < 16; k++) {
        BYTE *p = (BYTE *)0x00541070 + k * 0x48; WORD id = *(WORD *)p;
        if (!id || id == *(volatile WORD *)0x00541028 || !*(BYTE **)(p + 0x28)) { carsince[k] = 0; continue; }
        for (j = 0; j < 16 && seen[j] != id; j++) ;
        if (j < 16) continue;                                 /* already caught up */
        if (!carsince[k]) { carsince[k] = now; continue; }
        if (now - carsince[k] < 3000) continue;
        for (j = 0; j < 16 && seen[j]; j++) ;
        if (j < 16) seen[j] = id;
        fresh = 1;
    }
    if (fresh) {
        int n = *(volatile int *)0x006093c0, i;
        for (i = 0; i < n && i < 32 && g_coop_obj_qn < 16; i++)
            if (((int *)0x006093c8)[i]) coop_obj_queue(4, (i + 1) | ((((int *)0x00609420)[i] & 7) << 8));
        mlog("  coop-ai: new player in the session - %d objective states queued for it", n);
    }
}
static int __cdecl coop_ai_frametick(int a) {              /* replaces `call ai_FrameTick 0x40a320` at 0x403ddf */
    if (coop_ai_role() == 2 && coop_ai_in_mission()) return 0;
    return ((int (__cdecl *)(int))0x0040a320)(a);
}
static void apply_coop_ai(HMODULE exe) {
    BYTE old[5] = { 0xE8 }, w[5] = { 0xE8 }; LONG r0, r1;
    char v[8]; DWORD k = env_str("I76_COOP_AI", v, sizeof(v));
    if (k == 0 || v[0] != '1') return;
    real_dpReceive = (dprecv_fn)patch_iat(exe, "anetdll.dll", "dpReceive", (void *)coop_dpReceive);
    {
        if (env_flag("I76_COOP_HEAPWATCH", 8, 0) == 1) g_hp_watch = 1;
        if (env_flag("I76_COOP_HEAPLOCK", 8, 0) == 1) { g_hp_watch = 1; g_hp_lock_on = 1; }
        if (env_flag("I76_COOP_SHIMLOCK", 8, 1) == 0) g_hs_want = 0;
        if (env_flag("I76_COOP_HEAPGUARD", 8, 1) != 0 && GetModuleHandleA("AcGenral.dll")) {
            g_hp_guard = 1;
            if (!g_hp_watch) { g_hp_watch = 1; g_hp_only_exe = 1; }   /* guard alone: i76.exe's imports only */
            hp_find_list();                                  /* at load: the shim lock covers the whole session */
        }
        if (g_hp_watch) InitializeCriticalSection(&g_hp_cs);
    }
    r0 = (LONG)(0x0040a320 - (0x00403ddf + 5)); r1 = (LONG)((DWORD_PTR)coop_ai_frametick - (0x00403ddf + 5));
    memcpy(old + 1, &r0, 4); memcpy(w + 1, &r1, 4);
    mlog("  coop-ai: dpReceive %s, ai_FrameTick call %s (host sends mission cars as 'AT', joiner mirrors them)",
         real_dpReceive ? "hooked" : "NOT hooked",
         patch_bytes(0x00403ddf, old, w, 5, "coop-ai: ai_FrameTick") ? "repointed" : "NOT repointed");
    {   /* AI trigger pulls (host records them) and the damage entry (joiner blocks it for mirrored cars) */
        static const struct { DWORD site, target; void *stub; } c[27] = {
            { 0x00414f86, 0x004a3560, (void *)coop_ai_trigger },
            { 0x00465e5a, 0x00462040, (void *)coop_ai_class_damage }, { 0x0046648f, 0x00462040, (void *)coop_ai_class_damage },
            { 0x0046aae4, 0x00462040, (void *)coop_ai_class_damage }, { 0x004a81d3, 0x00462040, (void *)coop_ai_class_damage },
            { 0x004a8266, 0x00462040, (void *)coop_ai_class_damage },
            { 0x00412dac, 0x00412830, (void *)coop_ai_attack }, { 0x0040a232, 0x00412830, (void *)coop_ai_attack },
            { 0x00412def, 0x00412830, (void *)coop_ai_attack }, { 0x00412e32, 0x00412830, (void *)coop_ai_attack },
            { 0x00412e9c, 0x00412830, (void *)coop_ai_attack }, { 0x00412f11, 0x00412830, (void *)coop_ai_attack },
            { 0x00412fad, 0x00412830, (void *)coop_ai_attack }, { 0x00413049, 0x00412830, (void *)coop_ai_attack },
            { 0x00414046, 0x00412830, (void *)coop_ai_attack },
            { 0x00465267, 0x00454ea0, (void *)coop_ai_score_set },
            { 0x00401cfe, 0x00445750, (void *)coop_mirror }, { 0x00401fde, 0x00445750, (void *)coop_mirror },
            { 0x0040a0f8, 0x00423620, (void *)coop_cb_play }, { 0x0040bfcc, 0x00423620, (void *)coop_cb_play },
            { 0x0040bfee, 0x00423620, (void *)coop_cb_play }, { 0x0040c011, 0x00423620, (void *)coop_cb_play },
            { 0x0040c029, 0x00423620, (void *)coop_cb_play }, { 0x0041348f, 0x00423620, (void *)coop_cb_play },
            { 0x004136b1, 0x0045e9e0, (void *)coop_obj_success }, { 0x004136c7, 0x0045ea90, (void *)coop_obj_fail },
            { 0x0041420e, 0x0040be50, (void *)coop_obj_reveal },
        };
        static const struct { DWORD site; void *stub; } dg[9] = { { 0x40a232, (void *)coop_sb_0 }, { 0x412dac, (void *)coop_sb_1 },
            { 0x412def, (void *)coop_sb_2 }, { 0x412e32, (void *)coop_sb_3 }, { 0x412e9c, (void *)coop_sb_4 }, { 0x412f11, (void *)coop_sb_5 },
            { 0x412fad, (void *)coop_sb_6 }, { 0x413049, (void *)coop_sb_7 }, { 0x414046, (void *)coop_sb_8 } };
        char dv[8]; DWORD dk = env_str("I76_COOP_AI_DIAG", dv, sizeof(dv));
        int i, n = 0;
        int nsites = env_flag("I76_COOP_CB", 8, 1) == 0 ? 18 : 27;   /* I76_COOP_CB=0: no radio / objective forwarding */
        for (i = 0; i < nsites; i++) {
            BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 };
            LONG a0 = (LONG)(c[i].target - (c[i].site + 5)), a1 = (LONG)((DWORD_PTR)c[i].stub - (c[i].site + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            if (c[i].site == 0x004a81d3 && st_dmg_chain_take(c[i].stub)) { n++; continue; }   /* tick-factors holds the site: chain behind it */
            if (patch_bytes(c[i].site, o5, w5, 5, "coop-ai: trigger/damage")) n++;
        }
        mlog("  coop-ai: %d/%d trigger + damage + SetBehaviour + score + mirror + radio + objective sites repointed", n, nsites);
        if (dk && dv[0] == '1') {
            int m = 0;
            for (i = 0; i < 9; i++) {
                BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 }, cur[5];
                LONG a1 = (LONG)((DWORD_PTR)dg[i].stub - (dg[i].site + 5)), a0 = (LONG)(0x00412830 - (dg[i].site + 5));
                memcpy(cur, (void *)dg[i].site, 5); memcpy(w5 + 1, &a1, 4); memcpy(o5 + 1, &a0, 4);
                if (cur[0] == 0xE8) { DWORD old; if (VirtualProtect((void *)dg[i].site, 5, PAGE_EXECUTE_READWRITE, &old)) { memcpy((void *)dg[i].site, w5, 5); VirtualProtect((void *)dg[i].site, 5, old, &old); m++; } }
            }
            g_coop_diag = 1; mlog("  coop-ai diag: %d/9 SetBehaviour sites instrumented", m);
        }
    }
    {
        if (env_flag("I76_COOP_CHAIN", 8, 0) == 1) {
            BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 };
            LONG a0 = (LONG)(0x00461810 - (0x00404110 + 5)), a1 = (LONG)((DWORD_PTR)coop_chain_stub - (0x00404110 + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            g_coop_chain = patch_bytes(0x00404110, o5, w5, 5, "coop-chain: loop exit");
            a0 = (LONG)(0x00452d30 - (0x00404662 + 5)); a1 = (LONG)((DWORD_PTR)coop_netflag - (0x00404662 + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            if (!patch_bytes(0x00404662, o5, w5, 5, "coop-chain: teardown net flag")) g_coop_chain = 0;
            {   static const DWORD sp[7] = { 0x403ab8, 0x403cd5, 0x456161, 0x456a6c, 0x456bbc, 0x456cec, 0x456f17 };
                int q, ok = 0;
                for (q = 0; q < 7; q++) {
                    a0 = (LONG)(0x00451180 - (sp[q] + 5)); a1 = (LONG)((DWORD_PTR)coop_spawn - (sp[q] + 5));
                    memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
                    if (patch_bytes(sp[q], o5, w5, 5, "coop-chain: spawn")) ok++;
                }
                mlog("  coop-chain: %d/7 spawn sites adopt the mission player object for the host", ok);
                {   BYTE pu[5] = { 0x68, 0x70, 0xd3, 0x5d, 0x00 }, cl[5] = { 0xE8 };
                    LONG ac = (LONG)((DWORD_PTR)coop_player_car_stub - (0x004ad750 + 5));
                    memcpy(cl + 1, &ac, 4);
                    patch_bytes(0x004ad750, pu, cl, 5, "coop-chain: mission player car (host's model on the joiner)");
                }
                { if (env_flag("I76_COOP_ADOPT", 8, 1) == 0) { g_coop_adopt = 0; mlog("  coop-chain: adoption OFF (I76_COOP_ADOPT=0)"); } }
                { if (env_flag("I76_COOP_HOSTMODEL", 8, 1) == 0) { g_coop_hostmodel = 0; mlog("  coop-chain: host model on the joiner OFF (I76_COOP_HOSTMODEL=0)"); } }
                g_coop_near = env_flag("I76_COOP_NEAR_HOST", 8, 1) != 0;
                g_coop_host_wait_ms = env_int("I76_COOP_HOST_WAIT_MS", 8, 3000); if (g_coop_host_wait_ms < 0) g_coop_host_wait_ms = 0;
                g_coop_test_host_respawn = env_flag("I76_COOP_TEST_HOST_RESPAWN", 8, 0) == 1;
                apply_coop_script_guard();
                mlog("  coop-chain: host handshake after a chain reload: %s", g_coop_host_wait_ms ? "the quiet wait ends after I76_COOP_HOST_WAIT_MS" : "stock (I76_COOP_HOST_WAIT_MS=0)");
                mlog("  coop-chain: joiners spawn near the host in co-op scenes and scenarios %s", g_coop_near ? "ON (I76_COOP_NEAR_HOST)" : "OFF (I76_COOP_NEAR_HOST=0)");
            }
            mlog("  coop-chain: %s (won -> next co-op mission, lost -> retry, same session)", g_coop_chain ? "on" : "NOT installed");
        }
    }
    if (!real_dpReceive) { mlog("  coop-ai: no dpReceive import - off"); }
}

#include "difficulty.c"  /* Play Options Difficulty Level -> AI skill in network AI arenas (difficulty_ai_skill, called by aimelee.c) */
#include "aimelee.c"     /* I76_AIMELEE: AI cars in network melee arenas ai_*.lvl (host tick, kill credit, waves) */
#include "mpfill.c"      /* I76_AIMELEE_FILL / I76_COOP_SCALE: pre-spawned pools, parked and brought in by the host */

/* ===========================================================================
 * REAR MIRROR CADENCE  (I76_MIRROR_RATE=1, needs I76_FRAMERATE_FIXES; off by default)
 * ===========================================================================
 * Rear mirror (renderer_DrawRearMirror 0x445750, framerate.md row 7): redraws when frame_count >= next, next =
 * frame + 2 (`call simclock_GetFrameCount` 0x4457b4; `cmp eax,[0x52bbc8]; jl skip; add eax,2; mov [0x52bbc8],eax`
 * 0x4457b9-0x4457c8), i.e. every 2nd frame - 10/s at stock 20, 30/s at 60, 60/s at 120, and at mirror level 2 each
 * redraw is a full scene (terrain, roads, flamers, objects, tracers, puffs, clouds, bucket flush, 0x445933-0x4459b4).
 * On the 20 Hz grid count the same gate gives every 2nd grid tick = 10/s at any rate, as stock. The cloud scroll
 * (sites 0x405461/0x405484, rescaled per call to dt x 20) is also advanced by the mirror's own 0x405200 call
 * (0x4459a1, args cam 0x608c80, colour 0xef): stock is 20 main + 10 mirror steps/s = 30/s, and with the mirror at
 * 10/s each mirror call must step the stock 1.0, not the rescaled dt x 20, to keep the measured 0.0300 /s (capture
 * 014). The wrapper sets the stock step for the mirror call and restores the per-frame value after. The mirror pass's
 * flamer update calls 0x4458fe / 0x445968 stay unwrapped on purpose (g_flame_dmg_ok is 0 there, nothing is applied).
 * Kept out of I76_FRAMERATE_FIXES for A/B (docs/records/FRAMERATE-COVERAGE-2026-10-02.md P5 / U5). NOT yet measured in game.
 *
 * Two layouts at the gate, as for the hires clock: the 2017 Galaxy exe (md5 9a232dcc) has the `call` above; GOG's
 * 2019 AiO build (60abf7bc, and the sandbox exe built on it) removed the gate itself - `EB 17 90 90 90` jumps over
 * the compare to 0x4457cd and the `jl` became `jb` (0F 82), the only Galaxy/AiO difference in this function (i76-map
 * binaries/diff-9a232dcc-vs-60abf7bc.tsv, cluster 0x4457b4-0x4457c1) - so there the mirror redraws on EVERY frame.
 * Writing the call restores the gate on the grid count in both; the unsigned compare is fine with a DWORD count.
 */
static DWORD g_idbg_mirror_draws;                           /* copied into the debug block by the render wrapper */
static int g_mirror_rate_mode = 1;                          /* 1 = every 2nd grid tick (10/s, stock), 2 = every tick (20/s) */
static int __cdecl mirror_frame_count(void) {
    int c = g_ratefix ? (int)g_tick20_n * g_mirror_rate_mode : *(volatile int *)0x005a7e1c;
    if (c >= *(volatile int *)0x0052bbc8) g_idbg_mirror_draws++;    /* the gate that follows passes: a redraw */
    return c;
}
static void __cdecl mirror_clouds_wrap(void *cam, DWORD colour) {
    float u = g_cloud_u, v = g_cloud_v;
    g_cloud_u = 1.0f / (float)g_mirror_rate_mode; g_cloud_v = -1.0f / (float)g_mirror_rate_mode;   /* 20/s: half steps, same 10 steps/s */
    ((void (__cdecl *)(void *, DWORD))0x00405200)(cam, colour);
    g_cloud_u = u; g_cloud_v = v;
}
static void apply_mirror_rate(void) {
    static const BYTE gate_galaxy[5] = { 0xE8, 0x17, 0x70, 0x05, 0x00 };   /* call 0x49c7d0 simclock_GetFrameCount at 0x4457b4 (Galaxy) */
    static const BYTE gate_aio[5]    = { 0xEB, 0x17, 0x90, 0x90, 0x90 };   /* jmp 0x4457cd: gate removed (AiO: mirror every frame) */
    static const BYTE cloud_old[5]   = { 0xE8, 0x5A, 0xF8, 0xFB, 0xFF };   /* call 0x405200 renderer_DrawClouds at 0x4459a1 */
    BYTE gate_new[5] = { 0xE8 }, cloud_new[5] = { 0xE8 };
    LONG rel; int n = 0; const char *layout;
    {   char mv[4]; DWORD mk = env_str("I76_MIRROR_RATE", mv, sizeof(mv));
        if (mk == 0 || mv[0] == '0') return;
        g_mirror_rate_mode = mv[0] == '2' ? 2 : 1; }   /* =2: the gate's "next = count + 2" passes on every grid tick (20/s) */
    if (!g_ratefix) { mlog("  mirror-rate: needs I76_FRAMERATE_FIXES (the 20 Hz grid) - not applied"); return; }
    rel = (LONG)((DWORD_PTR)mirror_frame_count - (0x004457b4 + 5)); memcpy(gate_new + 1, &rel, 4);
    if (memcmp((void *)0x004457b4, gate_aio, 5) == 0) {
        layout = "AiO: gate was removed, mirror every frame";
        n += patch_bytes(0x004457b4, gate_aio, gate_new, 5, "rear mirror refresh gate (AiO)");
    } else {
        layout = "Galaxy";
        n += patch_bytes(0x004457b4, gate_galaxy, gate_new, 5, "rear mirror refresh gate (Galaxy)");
    }
    rel = (LONG)((DWORD_PTR)mirror_clouds_wrap - (0x004459a1 + 5)); memcpy(cloud_new + 1, &rel, 4);
    n += patch_bytes(0x004459a1, cloud_old, cloud_new, 5, "rear mirror cloud step");
    mlog("  mirror-rate: %d/2 sites repointed (refresh gate on the 20 Hz grid count = %d redraws/s, layout %s; mirror cloud step %s)", n, g_mirror_rate_mode == 2 ? 20 : 10, layout, g_mirror_rate_mode == 2 ? "0.5 per redraw = the stock 10 steps/s" : "at the stock 1.0");
}

/* ===========================================================================
 * STOCK BUG: HEALTH PERCENT  (I76_FIX_HEALTH_PCT=1; off by default - changes stock play)
 * ===========================================================================
 * object_HealthFraction 0x40b450 returns a vehicle's health in percent: 28 + 72 x (worst armour/chassis side ratio)
 * while engine, suspension and brakes are all >= 99.99%. As soon as one of them is below that, it returns the worst
 * component ratio UNSCALED (0..1): the switch at 0x40b6e3 (table 0x40b7b8, all four entries 0x40b6f0) jumps
 * straight to the clamp. A 99% engine therefore reads as 0.99 "percent". Confirmed live (i76-map damage.md: a 99%
 * engine starts the heaviest damage smoke). Callers that see it: damage smoke, entity_DamageComponent's < 33 test
 * (handgun hits go to component 6), fsm_HpLesser (script hpLesser), ai_ShouldFleeWhenHurt (AI flees below
 * 30 + 17 x skill), the target-bracket readout and the network state packers.
 * Missions may have been tuned around the stock behaviour, so this is opt-in.
 *
 * What the fix returns: health = min(28 + 72 x r, 100 x c), r = the worst armour/chassis side ratio (the stock
 * intact-core value), c = the worst live core component ratio. The first version (2026-09-27) returned 100 x c alone
 * on the component branch; that forgot the armour, so a car at 30% armour read 49.6 (yellow target bar) until its
 * engine took a scratch and 98 (green, nearly full) after it - the bar rose and changed colour the wrong way as the
 * car was shot (field report 2026-10-02, docs/records/HEALTH-BAR-COLOUR.md). The bar's colour and length are pure functions
 * of this value (renderer_DrawTargetBrackets 0x45af10: red <= 33.3, yellow <= 66.7, green < 100, white = 100;
 * length 30 x sqrt(v/100) px), so the value has to be monotone in damage. min() is: it never rises, it equals the
 * stock value while the core is intact, and it keeps every measured result of the x100 version (99% engine: no
 * smoke; 50% engine: smoke) because those runs had near-full armour. I76_FIX_HEALTH_PCT=2 keeps the x100-only
 * reading for A/B runs.
 *
 * Two sites, both byte-checked before either is written:
 *   1. the four table entries at 0x40b7b8 -> hf_comp_stub: st0 (c) x 100, parked in the frame slot [esp+0x14]
 *      (local_3c: FLT_MAX from the prologue at 0x40b470; its only other use is the multi-part cases 2/3/0xb/0xc at
 *      0x40b75c..0x40b776, which return through their own epilogue, never through 0x40b6f0), then jump to the
 *      armour/chassis side loop at 0x40b5f5, which computes 28 + 72 x r and exits to 0x40b6f0;
 *   2. the clamp entry 0x40b6f0 (fcom [0x4bc620], 6 bytes) -> hf_min_stub: st0 = min(st0, [esp+0x14]), the
 *      displaced fcom, back to 0x40b6f6. The other paths into 0x40b6f0 (intact core via 0x40b6ca / 0x40b6dc, the
 *      impossible dead-count > 3 default via 0x40b6ec) still hold FLT_MAX in the slot, so they are unchanged.
 *   The slot lives in the caller's frame, so the fix is re-entrant and needs no global. All three core components
 *   dead leaves c = FLT_MAX (x100 = +inf): the sides decide, instead of the stock 100 for a dead car. */
static DWORD g_hf_cont   = 0x0040b6f0;   /* the clamp (x100-only reading) */
static DWORD g_hf_sides  = 0x0040b5f5;   /* the armour/chassis side loop */
static DWORD g_hf_resume = 0x0040b6f6;   /* after the displaced fcom at 0x40b6f0 */
static __declspec(naked) void hf_scale_stub(void) {        /* =2: x100, straight to the clamp (the 2026-09-27 reading) */
    __asm {
        fmul dword ptr ds:[0x004bc620]
        jmp dword ptr [g_hf_cont]
    }
}
static __declspec(naked) void hf_comp_stub(void) {         /* =1: switch-table target; st0 = c, edi = entity, frame intact */
    __asm {
        fmul dword ptr ds:[0x004bc620]      ; 100 x c
        fstp dword ptr [esp + 0x14]         ; park it; pops st0 as the stock fstp st(0) at 0x40b5f3 does
        jmp dword ptr [g_hf_sides]
    }
}
static __declspec(naked) void hf_min_stub(void) {          /* =1: entered from 0x40b6f0; st0 = 28 + 72 x r */
    __asm {
        fcom dword ptr [esp + 0x14]
        fnstsw ax                           ; eax is dead here: the next stock instruction (0x40b6f6) is fnstsw ax
        test ah, 1                          ; C0 set: st0 < slot, keep the side value
        jne keep
        fstp st(0)
        fld dword ptr [esp + 0x14]
    keep:
        fcom dword ptr ds:[0x004bc620]      ; the displaced instruction
        jmp dword ptr [g_hf_resume]
    }
}
static void apply_fix_health_pct(void) {
    static const BYTE old_tab[16] = { 0xF0, 0xB6, 0x40, 0x00, 0xF0, 0xB6, 0x40, 0x00, 0xF0, 0xB6, 0x40, 0x00, 0xF0, 0xB6, 0x40, 0x00 };
    static const BYTE old_jmp[7] = { 0xFF, 0x24, 0x9D, 0xB8, 0xB7, 0x40, 0x00 };   /* jmp [ebx*4 + 0x40b7b8] at 0x40b6e3 */
    static const BYTE k100[4] = { 0x00, 0x00, 0xC8, 0x42 };                          /* 100.0f at 0x4bc620 */
    static const BYTE old_clamp[6] = { 0xD8, 0x15, 0x20, 0xC6, 0x4B, 0x00 };         /* fcom dword ptr [0x4bc620] at 0x40b6f0 */
    static const BYTE old_sides[6] = { 0x8D, 0x8F, 0x58, 0x01, 0x00, 0x00 };         /* lea ecx, [edi+0x158] at 0x40b5f5 */
    BYTE new_tab[16], new_clamp[6] = { 0xE9, 0, 0, 0, 0, 0x90 };
    char v[8]; DWORD a, rel; int x100_only, i;
    DWORD n = GetEnvironmentVariableA("I76_FIX_HEALTH_PCT", v, sizeof(v));
    if (n == 0) return;
    x100_only = (n < sizeof(v) && v[0] == '2');
    a = (DWORD)(DWORD_PTR)(x100_only ? hf_scale_stub : hf_comp_stub);
    if (!site_is(0x0040b6e3, old_jmp, 7) || !site_is(0x004bc620, k100, 4) ||
        !site_is(0x0040b6f0, old_clamp, 6) || !site_is(0x0040b5f5, old_sides, 6)) {
        mlog("  fix-health-pct: bytes differ at 0x40b6e3 / 0x4bc620 / 0x40b6f0 / 0x40b5f5 - not applied"); return;
    }
    {   static const DWORD sa[1] = { 0x004bc620 };       /* the 100.0f the stubs multiply by (Nitro 0x4c1ab0) */
        if (!nitro_reloc_stub((void *)hf_scale_stub, sa, 1, 32, "health percent stub (x100)") ||
            !nitro_reloc_stub((void *)hf_comp_stub, sa, 1, 32, "health percent stub (component)") ||
            !nitro_reloc_stub((void *)hf_min_stub, sa, 1, 48, "health percent stub (min)")) { mlog("  fix-health-pct: NOT applied (stubs)"); return; }
        g_hf_cont = NA(0x0040b6f0); g_hf_sides = NA(0x0040b5f5); g_hf_resume = NA(0x0040b6f6);   /* = the initial values on Gold */
    }
    for (i = 0; i < 4; i++) memcpy(new_tab + 4 * i, &a, 4);
    if (!patch_bytes(0x0040b7b8, old_tab, new_tab, 16, "health percent switch table")) { mlog("  fix-health-pct: NOT applied"); return; }
    if (x100_only) { mlog("  fix-health-pct: on (component branch x100 only - A/B reading, the target bar can rise; docs/HEALTH-BAR-COLOUR.md)"); return; }
    rel = (DWORD)(DWORD_PTR)hf_min_stub - (0x0040b6f0 + 5);
    memcpy(new_clamp + 1, &rel, 4);
    if (!patch_bytes(0x0040b6f0, old_clamp, new_clamp, 6, "health percent clamp entry")) {
        /* cannot happen after the pre-check; still, never leave the two sites disagreeing */
        patch_bytes(0x0040b7b8, new_tab, old_tab, 16, "health percent switch table (restore)");
        mlog("  fix-health-pct: NOT applied"); return;
    }
    mlog("  fix-health-pct: on (health = min(28 + 72 x worst side ratio, 100 x worst core ratio); sites 0x40b7b8, 0x40b6f0)");
}

/* ===========================================================================
 * STOCK BUG: LABEL TABLE GROWTH  (I76_FIX_LABEL_TABLE=1; I76_LABEL_TEST=1 shrinks the start capacity to test it)
 * ===========================================================================
 * entity_LabelMapInsert 0x4ad450 (entity_AddLabel 0x457610: the per-mission table of object instance labels, heap
 * record 0x54a178 {heap, table, count, capacity}, start capacity 0x800 from heap_Create 0x4ad410) grows the table
 * when count >= capacity, and every part of that path is wrong:
 *   - the size comes from the CRT's _msize, but the table lives in a private HeapCreate heap;
 *   - a successful HeapReAlloc returns 0 and throws the new pointer away (the block may have moved: the table
 *     pointer now dangles);
 *   - a failed one zeroes the table pointer and then writes the entry through it.
 * Stock missions stay under 2048 labels; big custom ones would corrupt the heap. The fix replaces the grow block
 * (0x4ad465..0x4ad48a) with a call to label_grow: HeapSize + HeapReAlloc, store the pointer, capacity += 0x100; on
 * failure the entry is dropped (return 0) and the table is left intact. */
static int __cdecl label_grow(DWORD *t) {
    SIZE_T sz = HeapSize((HANDLE)(DWORD_PTR)t[0], 0, (void *)(DWORD_PTR)t[1]);
    void *p;
    if (sz == (SIZE_T)-1) return 0;
    p = HeapReAlloc((HANDLE)(DWORD_PTR)t[0], HEAP_ZERO_MEMORY, (void *)(DWORD_PTR)t[1], sz + 0x1000);
    if (!p) return 0;
    t[1] = (DWORD)(DWORD_PTR)p; t[3] += 0x100;
    return 1;
}
static void apply_fix_label_table(void) {
    static const BYTE old_blk[38] = { 0x8B, 0x4E, 0x04, 0x51, 0xFF, 0x15, 0x60, 0xC1, 0x4B, 0x00, 0x8B, 0x56, 0x04, 0x83, 0xC4, 0x04,
                                      0x05, 0x00, 0x10, 0x00, 0x00, 0x50, 0x8B, 0x06, 0x52, 0x6A, 0x08, 0x50, 0xFF, 0x15, 0xE4, 0xC0,
                                      0x4B, 0x00, 0x85, 0xC0, 0x74, 0x0A };
    BYTE blk[38]; LONG rel; int ok;
    if (!env_present("I76_FIX_LABEL_TABLE")) return;
    memset(blk, 0x90, sizeof(blk));
    blk[0] = 0x56;                                          /* push esi (the table record) */
    blk[1] = 0xE8; rel = (LONG)((DWORD_PTR)label_grow - (NA(0x004ad466) + 5)); memcpy(blk + 2, &rel, 4);   /* NA: Gold = 0x4ad466 */
    blk[6] = 0x83; blk[7] = 0xC4; blk[8] = 0x04;            /* add esp, 4 */
    blk[9] = 0x85; blk[10] = 0xC0;                          /* test eax, eax */
    blk[11] = 0x74; blk[12] = 0x19;                         /* je 0x4ad48b (return 0) */
    blk[13] = 0xEB; blk[14] = 0x33;                         /* jmp 0x4ad4a7 (insert) */
    ok = patch_bytes(0x004ad465, old_blk, blk, sizeof(blk), "label table grow");
    mlog("  fix-label-table: %s", ok ? "on" : "NOT applied");
    if (ok && env_present("I76_LABEL_TEST")) {
        static const BYTE cap_old[7] = { 0xC7, 0x46, 0x0C, 0x00, 0x08, 0x00, 0x00 };   /* mov [esi+0xc], 0x800 at 0x4ad43b */
        static const BYTE cap_new[7] = { 0xC7, 0x46, 0x0C, 0x10, 0x00, 0x00, 0x00 };   /* ... 0x10 */
        mlog("  label-test: start capacity 16 %s", patch_bytes(0x004ad43b, cap_old, cap_new, 7, "label table start capacity") ? "(grows on every mission load)" : "NOT applied");
    }
}

/* ===========================================================================
 * DRAW DISTANCE  (I76_FAR_CLIP=<metres>; off by default)
 * ===========================================================================
 * docs/DRAW-DISTANCE.md: every mission's WRLD chunk carries far = 600 m, parsed into the one global 0x4c271c, read
 * by the projection setup at 0x4059de (`mov eax, [0x4c271c]`). The renderer's 12-byte draw-record arena (512 KB,
 * [0x5dd324]) and the transformed-vertex buffer (0x1a5e0 B, [0x5dd320], split at +0xd2f0) have no bounds check and
 * overflowed at far = 5000 (585,736 B used; crash at 0x491a11), so the pools are enlarged 16x in the same step -
 * never one without the other (patch-farclip.ps1 did the same to the file). This runs from DllMain, before WinMain
 * allocates the pools (0x402f98..0x402fd9). The read is repointed at g_far_clip, so the menu path (150 m) and the
 * clamp in camera_Create 0x472220 (100..100000) are untouched. Second ceiling (i76-map renderer.md): the depth
 * buckets drop anything past about 3796 m whatever the far clip says. */
static float g_far_clip = 600.0f;
static void apply_far_clip(void) {
    static const BYTE rd_old[5] = { 0xA1, 0x1C, 0x27, 0x4C, 0x00 };          /* mov eax, [0x4c271c] at 0x4059de */
    static const struct { DWORD va; DWORD old; } pool[5] = {
        { 0x00402f99, 0x40000 }, { 0x00402f9e, 0x1a5e0 }, { 0x00402fc6, 0xd2f0 }, { 0x00402fcb, 0x80000 }, { 0x00402fd0, 0x80000 } };
    char v[16]; DWORD n; float far_m; BYTE rd_new[5] = { 0xA1 }; DWORD a; int i, ok = 0, filepatched = 0;
    n = env_str("I76_FAR_CLIP", v, sizeof(v));
    if (n == 0) return;
    far_m = (float)atof(v);
    /* Third ceiling (docs/records/FARCLIP-CAMERA-CRASH.md, 2026-10-02): the terrain tessellator stores vertex indices as int16
     * (renderer_SplitTerrainEdge 0x4918f0); past ~32,767 terrain vertices in a frame the index wraps and the game dies.
     * The hood view (120 deg) and binoculars (8x) reach that between 2500 and 2750 m on t01, so 2500 is the cap. */
    if (far_m < 100.0f || far_m > 2500.0f) { mlog("  far-clip: %s out of the safe range (100..2500 m: int16 terrain vertex indices, see FARCLIP-CAMERA-CRASH.md) - not applied", v); return; }
    /* An exe already file-patched by tools/framerate/patch-farclip.ps1 (the sandbox is) carries the pools at x16 and
     * `mov eax, imm32 <float>` at the read site. Recognise that, report the file value, and still take over the read
     * so the environment value wins (2026-10-02: "pool constant 0 differs - not applied" hid that the 1800 m came from
     * the file, not the switch). */
    for (i = 0; i < 5; i++) if (NA(pool[i].va) && *(DWORD *)(DWORD_PTR)NA(pool[i].va) == pool[i].old * 16) filepatched++;
    if (filepatched == 5 && *(BYTE *)(DWORD_PTR)NA(0x004059de) == 0xB8) {
        BYTE imm_old[5]; float file_m;
        memcpy(imm_old, (void *)(DWORD_PTR)NA(0x004059de), 5); memcpy(&file_m, imm_old + 1, 4);
        g_far_clip = far_m;
        a = (DWORD)(DWORD_PTR)&g_far_clip; memcpy(rd_new + 1, &a, 4);
        ok = patch_bytes(0x004059de, imm_old, rd_new, 5, "far clip read (file-patched exe)");
        mlog("  far-clip: exe is file-patched (%g m, pools x16); %s (%g m from I76_FAR_CLIP)", file_m, ok ? "read site repointed" : "NOT repointed", far_m);
        return;
    }
    for (i = 0; i < 5; i++) if (!NA(pool[i].va) || *(DWORD *)(DWORD_PTR)NA(pool[i].va) != pool[i].old) { mlog("  far-clip: pool constant %d differs - not applied", i); return; }
    if (!site_is(0x004059de, rd_old, 5)) { mlog("  far-clip: read site differs - not applied"); return; }
    for (i = 0; i < 5; i++) {
        DWORD nv = pool[i].old * 16;
        ok += patch_bytes(pool[i].va, (const BYTE *)&pool[i].old, (const BYTE *)&nv, 4, "render pool x16");
    }
    g_far_clip = far_m;
    a = (DWORD)(DWORD_PTR)&g_far_clip; memcpy(rd_new + 1, &a, 4);
    ok += patch_bytes(0x004059de, rd_old, rd_new, 5, "far clip read");
    mlog("  far-clip: %s (%g m, pools x16, %d/6 sites)%s", ok == 6 ? "on" : "PARTIAL", far_m, ok,
         "");
}

/* ===========================================================================
 * CRASH LOG  (always on; I76_CRASH_LOG=0 disables)
 * ===========================================================================
 * A vectored exception handler that writes the faulting address, code, registers and the first stack dwords to
 * mciproxy.log, then lets the exception continue to the default handler (the game dies as before). "Instrument the
 * crash": a reproducible fault address is the fastest route to the function (tools/disasm.py). Added 2026-10-02 after
 * the hood-view / binoculars crash on the far-clip-patched sandbox exe. */
static LONG CALLBACK crash_log_handler(EXCEPTION_POINTERS *ep) {
    EXCEPTION_RECORD *r = ep->ExceptionRecord; CONTEXT *c = ep->ContextRecord;
    static int depth;
    if ((r->ExceptionCode & 0xF0000000) != 0xC0000000 || depth) return EXCEPTION_CONTINUE_SEARCH;   /* real faults only, once */
    if (g_exe == EXE_NITRO && r->ExceptionCode == 0xC0000096 && (DWORD)(DWORD_PTR)r->ExceptionAddress >= 0x0049ac70 && (DWORD)(DWORD_PTR)r->ExceptionAddress < 0x0049ad10) {   /* cli at 0x49acb7, out at 0x49acba, ... */
        /* nitro-owner lane 2026-10-23: Nitro's PIT CPU-speed probe (nitro.c nitro_pit_skip) faults first-chance at every boot and the
         * game handles it; it used to take this handler's one shot, so a later real fault on Nitro (the mission-over Replay's
         * "Unhandled Exception" box) left no record. Logged once, the shot kept. */
        static int pit_seen; if (pit_seen++ < 4) mlog("crash-log: Nitro's PIT probe 0xC0000096 at 0x%08lX (first chance, handled by the game) - not counted", (unsigned long)(DWORD_PTR)r->ExceptionAddress);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    depth++;
    mlog("CRASH: code 0x%08lX at 0x%08lX (exe+0x%lX) %s addr 0x%08lX | eax %08lX ebx %08lX ecx %08lX edx %08lX esi %08lX edi %08lX ebp %08lX esp %08lX | frame %lu state %lu cam cb 0x%08lX mode %lu",
         (unsigned long)r->ExceptionCode, (unsigned long)(DWORD_PTR)r->ExceptionAddress,
         (unsigned long)((DWORD_PTR)r->ExceptionAddress - (DWORD_PTR)GetModuleHandleA(NULL)),
         r->ExceptionCode == EXCEPTION_ACCESS_VIOLATION ? (r->ExceptionInformation[0] ? "write" : "read") : "",
         (unsigned long)(r->NumberParameters > 1 ? r->ExceptionInformation[1] : 0),
         (unsigned long)c->Eax, (unsigned long)c->Ebx, (unsigned long)c->Ecx, (unsigned long)c->Edx, (unsigned long)c->Esi,
         (unsigned long)c->Edi, (unsigned long)c->Ebp, (unsigned long)c->Esp,
         (unsigned long)nrd32(0x005a7e1c), (unsigned long)nrd32(0x004c2164),
         (unsigned long)nrd32(0x004c2720), (unsigned long)nrd32(0x004c2728));
    {
        DWORD *sp = (DWORD *)(DWORD_PTR)c->Esp; char buf[400]; int i, n = 0;
        for (i = 0; i < 16; i++) {
            if (IsBadReadPtr(sp + i, 4)) break;
            n += _snprintf(buf + n, sizeof(buf) - n, " %08lX", (unsigned long)sp[i]);
        }
        buf[n] = 0; mlog("CRASH: stack%s", buf);
    }
    {   /* the module that owns the fault address and the first return addresses outside the exe (2026-10-04: the driver's
           0x6E988AD3 had to be matched by hand to AcGenral.DLL+0x98AD3 from a September WER report) */
        DWORD *sp = (DWORD *)(DWORD_PTR)c->Esp; char buf[600]; int i, n = 0, m = 0;
        DWORD a[4]; int na = 0;
        a[na++] = (DWORD)(DWORD_PTR)r->ExceptionAddress;
        for (i = 0; i < 16 && na < 4; i++) {
            DWORD d;
            if (IsBadReadPtr(sp + i, 4)) break;
            d = sp[i];
            if (d >= 0x00400000 && d < 0x00610000) continue;          /* the exe: already readable as exe+offset */
            if (d < 0x00010000 || d >= 0x80000000) continue;
            a[na++] = d;
        }
        for (i = 0; i < na; i++) {
            MEMORY_BASIC_INFORMATION mb; char path[MAX_PATH]; const char *base;
            if (!VirtualQuery((void *)(DWORD_PTR)a[i], &mb, sizeof mb) || mb.Type != MEM_IMAGE || !mb.AllocationBase) continue;
            path[0] = 0; GetModuleFileNameA((HMODULE)mb.AllocationBase, path, sizeof path);
            base = strrchr(path, '\\'); base = base ? base + 1 : path;
            n += _snprintf(buf + n, sizeof(buf) - n, "%s %08lX = %s+0x%lX (base %p)", m++ ? ";" : "", (unsigned long)a[i], base,
                           (unsigned long)(a[i] - (DWORD)(DWORD_PTR)mb.AllocationBase), mb.AllocationBase);
            if (n >= (int)sizeof(buf) - 80) break;
        }
        buf[n < (int)sizeof(buf) ? n : (int)sizeof(buf) - 1] = 0;
        if (m) mlog("CRASH: modules%s", buf);
    }
    {   /* winmm-race lane 2026-10-24: a fault inside winmmbase - its import owners and driver table (winmmrace.c) */
        MEMORY_BASIC_INFORMATION mb; HMODULE wb = GetModuleHandleA("winmmbase.dll");
        if (wb && VirtualQuery(r->ExceptionAddress, &mb, sizeof mb) && mb.AllocationBase == (void *)wb) wmr_state("crash");
    }
    {   /* nitro-owner lane 2026-10-23: a fault inside a system DLL (ntdll's heap) names no exe frame in the 16 dwords above; the
           first 12 values deeper on the stack that point into the exe's code (return-address candidates, oldest last) */
        DWORD *sp = (DWORD *)(DWORD_PTR)c->Esp; char buf[400]; int i, n = 0, k = 0;
        for (i = 0; i < 1024 && k < 12; i++) {
            DWORD d;
            if (IsBadReadPtr(sp + i, 4)) break;
            d = sp[i];
            if (d >= 0x00401000 && d < 0x004c1000) { n += _snprintf(buf + n, sizeof(buf) - n, " +%x:%06lX", i * 4, (unsigned long)d); k++; }
        }
        buf[n < (int)sizeof(buf) ? n : (int)sizeof(buf) - 1] = 0;
        if (k) mlog("CRASH: exe code addresses on the stack%s", buf);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
static void apply_crash_log(void) {
    char v[8];
    if (GetEnvironmentVariableA("I76_CRASH_LOG", v, sizeof(v)) && v[0] == '0') return;
    AddVectoredExceptionHandler(1, crash_log_handler);
}

/* ===========================================================================
 * PHYSICS SUBSTEP RATE  (I76_PHYS_RATE=<steps per second>; off by default; EXPERIMENT)
 * ===========================================================================
 * entity_InitVehicle seeds each vehicle's physics stepper with a 0.05 s maximum
 * step (push 0x3d4ccccd at 0x46312b): the frame's dt is split into
 * floor(dt * 20) + 1 equal substeps, i.e. two 25 ms steps at 20 fps but one
 * 16.7 ms step at 60 fps. This replaces 0.05 with 1/rate so the substep size can
 * be varied independently of the frame rate - the experiment that decides
 * whether the 60 fps chassis/cockpit buzz comes from the step size.
 */
static void apply_phys_rate(void) {
    static const BYTE old_push[5] = { 0x68, 0xCD, 0xCC, 0x4C, 0x3D };   /* push 0.05f at 0x46312b */
    BYTE new_push[5] = { 0x68, 0, 0, 0, 0 };
    char v[16]; int rate; float step;
    DWORD n = env_str("I76_PHYS_RATE", v, sizeof(v));
    if (n == 0 || (rate = atoi(v)) < 10 || rate > 2000) return;
    step = 1.0f / (float)rate;
    memcpy(new_push + 1, &step, 4);
    /* three pushes of the 0.05 max step: entity_InitVehicle, entity_TickVehicle's re-seed branch (0x46385c,
     * which re-initialises the stepper whenever that branch runs - the first experiment patched only 0x46312b
     * and the live stepper still read rate 20), and the network path 0x455230 */
    mlog("  phys-rate: max substep 1/%d s, %d/3 sites patched (0x46312b, 0x46385c, 0x45531b)", rate,
         patch_bytes(0x0046312b, old_push, new_push, 5, "vehicle stepper max step (init)") +
         patch_bytes(0x0046385c, old_push, new_push, 5, "vehicle stepper max step (tick re-seed)") +
         patch_bytes(0x0045531b, old_push, new_push, 5, "vehicle stepper max step (network)"));
}

/* ===========================================================================
 * FIXED PHYSICS STEP  (I76_FIXED_STEP=<steps per second>, e.g. 40; off by default)
 * ===========================================================================
 * Measured 2026-09-27 (i76-map captures\014-framerate): the chassis/cockpit
 * buzz follows the physics SUBSTEP SIZE, not the frame rate as such. At 20 fps
 * the body's roll rate reverses 3.6-6.0 times a second with the stock 25 ms steps,
 * 8.7-11.5 with 12.5 ms steps; at 60 fps 8.9-15.5 with 16.7 ms steps, 15-21 with
 * 5.7 ms steps. simclock_StepperBegin 0x49cc20 splits each frame's dt into
 * floor(dt*20)+1 equal steps, so the step size - and the car's behaviour -
 * changes with the frame rate.
 *
 * This replaces simclock_StepperBegin (jmp at its entry, stock bytes
 * D9 05 20 E4 4F 00 = fld [simclock_sim_dt], the same in Galaxy and AiO) with a
 * fixed-step accumulator per stepper: every frame adds sim_dt, runs as many whole
 * steps of exactly 1/rate as have accumulated (at most 20), and carries the rest.
 * Which rate matches stock: at a 20 fps cap the stock clock (GetTickCount, 15.6 ms
 * quanta) gives frame dts of 46.9 / 62.5 ms, which the stepper splits into steps of
 * 46.9 ms (80%) and 31.2 ms - mean 41.7 ms (capture 014, 2026-09-27). 24 steps/s
 * (41.7 ms) reproduces that; 40 (25 ms, the first choice) made jumps fall short and
 * the body motion quick in play, because the contact model is step-size dependent.
 * I76_RENDER_INTERP hides the low physics cadence.
 */
static struct { void *s; float acc; int n; DWORD frame; DWORD steps; } g_step_acc[64];

static int step_slot(void *stepper, int add);
static DWORD vehicle_steps(BYTE *e) {                       /* entity_TickVehicle passes &entity+0x444 to the stepper (0x463881) */
    int k = step_slot(e + 0x444, 0);
    return k < 0 ? g_stepframes : g_step_acc[k].steps;      /* not stepped yet / far path: the global count */
}
static int step_slot(void *stepper, int add) {
    int i, slot = -1;
    for (i = 0; i < 64; i++) {
        if (g_step_acc[i].s == stepper) return i;
        if (slot < 0 && g_step_acc[i].s == 0) slot = i;
    }
    if (!add) return -1;
    if (slot < 0) slot = (int)(((DWORD_PTR)stepper >> 4) & 63);   /* table full: reuse a slot */
    g_step_acc[slot].s = stepper; g_step_acc[slot].acc = 0.0f; g_step_acc[slot].steps = 0;
    return slot;
}

static void __cdecl fixed_stepper_begin(float *stepper) {
    float sim_dt = *(volatile float *)0x004fe420;          /* simclock_sim_dt */
    int slot = step_slot(stepper, 1), n;
    g_step_acc[slot].acc += sim_dt;
    n = (int)(g_step_acc[slot].acc / g_fixed_step);
    if (n > 20) { n = 20; g_step_acc[slot].acc = 0.0f; } else g_step_acc[slot].acc -= (float)n * g_fixed_step;
    g_step_acc[slot].n = n; g_step_acc[slot].frame = g_frame;   /* for render interpolation */
    g_step_acc[slot].steps += (DWORD)n;                      /* cumulative, per vehicle (I76_AI_SKID_HOLD) */
    if (n > 0 && g_stepframe_last != g_frame) { g_stepframe_last = g_frame; g_stepframes++; }
    stepper[1] = g_fixed_step;                               /* +4 step */
    ((int *)stepper)[2] = n;                                 /* +8 count */
}

/* ===========================================================================
 * INPUT LATCH  (I76_INPUT_LATCH=1; off by default; meant for I76_FIXED_STEP)
 * ===========================================================================
 * Owner report 2026-10-04: "pressing I for the ignition works maybe one time in five" (best-wide: 120 fps,
 * I76_FIXED_STEP=24). Static reading, md5 9a232dcc = AiO 6319abf7 at these bytes:
 *   - start_engine (byte 0x5367e6) and toggle_lights (0x5367e7) are discrete commands of type 2 (table 0x4f2aa0 /
 *     0x4f2ac0). input_UpdateControls 0x44d9e0 zeroes every discrete byte each frame (0x44daa6) and sets it for ONE
 *     frame on the key's rising edge (0x44db74..0x44db87), however long the key is held;
 *   - input_ApplyToEntity 0x44f1c0 copies the bytes, once per rendered frame, into the player entity: 0x44f4cf
 *     `mov [edi+0xec], ecx` (ignition request) and 0x44f4dc `mov [edi+0x100], edx` (lights request);
 *   - entity_UpdateState 0x465370 reads and clears both (0x4653d4 / 0x465438, 0x4653c7 / 0x4653df) - once per PHYSICS
 *     STEP, from the substep loop of entity_TickVehicle 0x463800 (0x4638b0).
 * Stock, every frame has at least one substep, so the one-frame pulse is always consumed. Under I76_FIXED_STEP a
 * frame can have none: at 24 steps/s and 120 fps four frames in five run no step, the next frame's copy overwrites the
 * pulse with 0, and the press is lost - one press in five works, which is what the owner counted. Holding the key
 * longer does not help (edge-triggered). The headlights key has the same loss.
 * Fix: make the two copies OR instead of MOV (opcode 89 -> 09, one byte each, same length and operands), so the
 * request stays set until the next physics step consumes and clears it. With a step every frame (stock) nothing
 * changes. */
static void apply_input_latch(void) {
    static const BYTE ign_old[6] = { 0x89, 0x8F, 0xEC, 0x00, 0x00, 0x00 };   /* 0x44f4cf mov [edi+0xec], ecx */
    static const BYTE ign_new[6] = { 0x09, 0x8F, 0xEC, 0x00, 0x00, 0x00 };   /*          or  [edi+0xec], ecx */
    static const BYTE lgt_old[6] = { 0x89, 0x97, 0x00, 0x01, 0x00, 0x00 };   /* 0x44f4dc mov [edi+0x100], edx */
    static const BYTE lgt_new[6] = { 0x09, 0x97, 0x00, 0x01, 0x00, 0x00 };   /*          or  [edi+0x100], edx */
    int n;
    if (!env_present("I76_INPUT_LATCH")) {
        if (g_fixed_step > 0.0f)
            mlog("  input-latch: off - with I76_FIXED_STEP the ignition (I) and lights keys are lost on frames without a physics step; I76_INPUT_LATCH=1 keeps them");
        return;
    }
    n = patch_bytes(0x0044f4cf, ign_old, ign_new, 6, "ignition request copy (input latch)")
      + patch_bytes(0x0044f4dc, lgt_old, lgt_new, 6, "lights request copy (input latch)");
    mlog("  input-latch: %d/2 sites (ignition, lights requests held until the next physics step)%s", n,
         g_fixed_step > 0.0f ? "" : " - note: without I76_FIXED_STEP every frame steps, so this changes nothing");
}

static void apply_ref_fps(void) {
    char v[16]; double r;
    if (!env_str("I76_REF_FPS", v, sizeof(v))) return;
    r = atof(v);
    if (r < 10.0 || r > 60.0) { mlog("  ref-fps: '%s' is not 10..60 - the 20 fps reference kept", v); return; }
    g_ref_rate = (float)r; g_ref_dt = (float)(1.0 / r);
    g_grid_win = g_ref_dt; g_ai_hz = g_ref_rate; g_bag_k20 = g_ref_rate;
    mlog("  ref-fps: frame-rate fixes reproduce a %.2f fps game (grid / gain pins / engine substep dt %.2f ms; AI grid default %.2f Hz)",
         r, 1000.0 * g_ref_dt, r);
}
static void apply_fixed_step(void) {
    static const BYTE old_entry[6] = { 0xD9, 0x05, 0x20, 0xE4, 0x4F, 0x00 };   /* fld [0x4fe420] at 0x49cc20 */
    BYTE jmp[6] = { 0xE9, 0, 0, 0, 0, 0x90 };
    char v[16]; double rate;
    LONG rel = (LONG)((DWORD_PTR)fixed_stepper_begin - (0x0049cc20 + 5));
    DWORD n = env_str("I76_FIXED_STEP", v, sizeof(v));
    if (n == 0 || (rate = atof(v)) < 10.0 || rate > 1000.0) return;   /* fractional rates allowed */
    g_fixed_step = (float)(1.0 / rate);
    memcpy(jmp + 1, &rel, 4);
    if (!patch_bytes(0x0049cc20, old_entry, jmp, 6, "simclock_StepperBegin entry")) g_fixed_step = 0.0f;
    mlog("  fixed-step: %.2f steps/s (%.2f ms) %s", rate, g_fixed_step * 1000.0f, g_fixed_step > 0 ? "on" : "NOT applied");
}

/* ===========================================================================
 * COLLISION SWEEP WINDOW  (I76_COLL_WINDOW=1, needs I76_FIXED_STEP; off by default)
 * ===========================================================================
 * physics_CollideObjects 0x4349c0 runs once per frame from WinMain 0x403a12 (physics.md "Objects and vehicles"). Its
 * sweeps cover [0, frame dt] from the current pose and the car consumes the contact on its next substep. With
 * I76_FIXED_STEP the pose only moves on step frames, by one step (41.7 ms at 24/s), while the sweep still covers one
 * frame: 16.7 ms at 60 fps, 8.3 at 120 - 40% / 20% of the step the contact is consumed by. Cover one whole step
 * instead (or the frame, if it is longer: several steps per frame below the step rate), so the contact the step
 * consumes is the one on the path the step will take. Stock (no fixed step) is unchanged. Far vehicles (0x43a3c0, one
 * whole-frame step) are swept over the same window; they are > 849 m from the camera and take collision damage on the
 * predicted contact (0x4643c0 applies it at once), so a far car may be damaged up to (step - dt) early.
 * Three `call simclock_GetSimDt` (0x49c7a0) in the collision tree, a single chain of callers (0x4349c0 <- WinMain
 * only; 0x434bb0 <- 0x434ae7 / 0x434b19 in 0x4349c0 only; 0x43f8c0 <- 0x43f656 in the pair test's scenery path and its
 * own recursion 0x43fd5f). docs/records/FRAMERATE-COVERAGE-2026-10-02.md P1 / U1. Unmeasured: cactus-ab.ps1 at 60 and 120
 * with the fixed step, before and after, n >= 10 approaches per rate.
 */
static float __cdecl coll_dt(void) {
    float sim_dt = *(volatile float *)0x004fe420;          /* simclock_sim_dt */
    return (g_fixed_step > sim_dt) ? g_fixed_step : sim_dt;
}
/* I76_COLL_WINDOW=2 (2026-10-08, owner: ~1 in 3 roadblocks hit in T05 at 120 fps): =1 widens only the three sweep
 * extents above; the two FINAL accept tests still compare the time of impact with the frame dt - the slab test
 * 0x43df10 (box-box points, sphere) at 0x43e1c8 and the mesh test 0x43ebc0 at 0x43ec6a, both `t <= GetSimDt()`
 * (lab docs/COLLISION-MISS-2026-10-08.md s.3) - so a contact past the first frame of the step is still dropped and the
 * car is inside / past the object on the next step (a start-inside point is ignored). Those two routines are shared
 * with the AI's look-ahead colliders (0x43d770 / 0x43d9e0), so they read the window only while physics_CollideObjects
 * runs: its one call (WinMain 0x403a12; no arguments, plain ret, ebx is callee-saved) is wrapped to set a flag.
 * Repeated contacts on frames with no step: pair with I76_COLL_DEDUPE=1. */
static volatile int g_in_coll_pass;
static int g_coll_v3;
static void coll_v3_report(void);
static int g_cw_when;
static void coll_when_report(void);
static void __cdecl coll_pass_wrap(void) {
    g_in_coll_pass = 1;
    ((void (__cdecl *)(void))0x004349c0)();
    g_in_coll_pass = 0;
    if (g_coll_v3) coll_v3_report();
    if (g_cw_when) coll_when_report();
}
/* I76_COLL_WINDOW_WHEN / I76_COLL_WINDOW_SCALE (2026-10-12, owner: with =2 "many of the obstacles are hit before you run
 * into them ... could it be triggered a step later / on time?"; lab docs/COLL-TIMING-2026-10-12.md). Under =2 the pass
 * of EVERY frame accepts a contact up to one whole step (41.7 ms) ahead of the current pose. The pose only moves on step
 * frames, so a contact in the coming step is accepted - and a breakable knocked off - in the first pass after the
 * previous step: at 120 fps up to 4 frames before the tick that carries the car there (and I76_RENDER_INTERP draws the
 * car a further step behind the physics pose).
 *   WHEN=stepframe: widen only for a pair whose body will step in THIS frame's tick. The window is the motion that tick
 *     will make, n x step, with n predicted exactly as fixed_stepper_begin computes it: (the stepper's carried
 *     accumulator + this frame's sim_dt, already set by the frame clock before 0x403a12) / step, at most 20. Other
 *     frames keep the stock window (sim_dt). Per body, through the pair-test wrapper around 0x43f510 (coll_shapes_wrap,
 *     installed with the fixed step): a class-1 vehicle that went through the fixed stepper last frame uses its own
 *     prediction; a class-1 vehicle that did not (far / wrecked: whole-frame motion) uses sim_dt; other movers (classes
 *     7 / 9, layout not read) keep the =2 window; statics add nothing. No pair window (wrapper missing) = the =2 window,
 *     counted as a fallback in the 30 s line.
 *   SCALE=<0.05..1>: the widened window is scale x the step (x n under stepframe), never below sim_dt. Below 1 the
 *     window no longer covers the whole step, so some contacts are missed again (an entry plane is found with
 *     probability about scale under the every-frame mode).
 * Default (neither set): exactly =2 as before (max(sim_dt, step) on every frame). */
static int g_cw_when;                                        /* 0: every frame (=2 as built), 1: stepframe */
static float g_cw_scale = 1.0f;
static float g_pair_win = -1.0f;                             /* stepframe: the pair's window, set around 0x43f510; < 0 unset */
static volatile DWORD g_cw_pairs, g_cw_wide, g_cw_stock, g_cw_fallback;
static float coll_wide(void) {                               /* the =2 window, scaled: max(sim_dt, scale x step) */
    float sim_dt = *(volatile float *)0x004fe420, w = g_cw_scale * g_fixed_step;
    return w > sim_dt ? w : sim_dt;
}
static float __cdecl coll_dt_gated(void) {
    if (!g_in_coll_pass) return *(volatile float *)0x004fe420;
    if (g_cw_when) {
        if (g_pair_win >= 0.0f) return g_pair_win;
        g_cw_fallback++;
    }
    return coll_wide();
}
/* the motion a body's coming tick makes: n x step as fixed_stepper_begin will compute it; 0 = a static; -1 = a mover
 * whose stepper is unknown (keep =2); -2 = a vehicle not on the fixed stepper last frame (whole-frame motion = sim_dt) */
static float body_coming_motion(BYTE *obj, float sim_dt) {
    int cls, s, n;
    BYTE *ent;
    volatile float a;
    if (!obj) return 0.0f;
    cls = *(int *)(obj + 0x6c);
    if (cls != 1 && cls != 7 && cls != 9) return 0.0f;     /* movers are classes 1, 7, 9 (0x458c10) */
    ent = *(BYTE **)(obj + 0x70);
    if (cls != 1 || !ent) return -1.0f;
    s = step_slot(ent + 0x444, 0);
    if (s < 0 || g_step_acc[s].frame != g_frame - 1) return -2.0f;
    a = g_step_acc[s].acc + sim_dt;                          /* the same float sum the stepper stores */
    n = (int)(a / g_fixed_step);
    if (n > 20) n = 20;
    return (float)n * g_fixed_step;
}
static float coll_pair_window(BYTE *a, BYTE *b) {
    float sim_dt = *(volatile float *)0x004fe420, w = sim_dt, m[2];
    int i;
    m[0] = body_coming_motion(a, sim_dt); m[1] = body_coming_motion(b, sim_dt);
    for (i = 0; i < 2; i++) {
        float x = m[i] == -1.0f ? coll_wide() : m[i] > 0.0f ? g_cw_scale * m[i] : 0.0f;
        if (x > w) w = x;
    }
    g_cw_pairs++;
    if (w > sim_dt) g_cw_wide++; else g_cw_stock++;
    return w;
}
static void coll_when_report(void) {                         /* from the pass wrapper: one line per 30 s while it changes */
    static DWORD last_frame, last_pairs;
    if (g_frame - last_frame < 3600 || g_cw_pairs == last_pairs) return;
    last_frame = g_frame; last_pairs = g_cw_pairs;
    mlog("  coll-window when=stepframe: pair tests %lu, widened (a body steps this frame) %lu, stock window %lu, no pair window (=2 used) %lu",
         g_cw_pairs, g_cw_wide, g_cw_stock, g_cw_fallback);
}
/* I76_COLL_WINDOW=3 (2026-10-11, lab docs/COLL-WINDOW-DEATH-SPOT-2026-10-11.md; proposal: COLLISION-MISS-2026-10-08.md
 * s.6.5): =2 widened every slab-test accept (box-box points, scenery boxes, spheres) and the mesh accept. =3 widens ONLY
 * the slab accept reached from the sphere test 0x440d90 (call 0x43df10 at 0x440f37) when the sphere's part node is of
 * class 4 / 0x5a / 0x5b - the set entity_CollideStoreContact 0x4643c0 discards (0x458c30): a vehicle never copies such
 * a contact into entity+0x38 and takes no damage or impulse from it, so a widened contact cannot change any vehicle's
 * motion; what remains is the knock-off of the breakable (swend_1 barricades: class 4, default part kind 0x5000 =
 * sphere 0.75 r). Box-box (car vs car, scenery boxes), scenery meshes and non-breakable spheres keep the stock accept.
 * Patches: the =1 sweep reads (the pair must still pass the broadphase and the prefilters), the 0x403a12 pass flag, the
 * 0x440f37 call (thunk: node = 0x440d90's arg 2 = [esp+0x124] at the call - 0x440ded reads arg 2 as [esp+0xe8] in a
 * 0xe0 frame, plus 0x3c of pushes; the walker 0x43f8c0 passes ebp = the node, ebp+0x64 its first child), and 0x43e1c8. */
static volatile int g_sph_discard;
static DWORD g_sph_ret, g_sph_slab = 0x0043df10;
static volatile DWORD g_sph_calls, g_sph_wide, g_sph_cls[128], g_sph_cls_other;
static void __cdecl sph_classify(BYTE *node) {
    int c = -1;
#ifdef _MSC_VER
    __try { if (node) c = *(int *)(node + 0x6c); } __except (EXCEPTION_EXECUTE_HANDLER) { c = -2; }
#else
    if (node) c = *(int *)(node + 0x6c);
#endif
    g_sph_calls++;
    if (c >= 0 && c < 128) g_sph_cls[c]++; else g_sph_cls_other++;
    g_sph_discard = g_in_coll_pass && (c == 4 || c == 0x5a || c == 0x5b);
    if (g_sph_discard) g_sph_wide++;
}
#ifdef _MSC_VER
static __declspec(naked) void sph_slab_thunk(void) {          /* replaces `call 0x43df10` at 0x440f37 (cdecl, 0x3c of args) */
    __asm {
        pop  g_sph_ret                          /* 0x440f3c; esp is now the call's: the slab test's arguments at [esp] */
        pushad
        push dword ptr [esp + 0x144]            /* 0x440d90's arg 2 (the part node): [esp+0x124] + 0x20 of pushad */
        call sph_classify
        add  esp, 4
        popad
        call dword ptr [g_sph_slab]             /* the slab test, same arguments, same registers */
        mov  g_sph_discard, 0
        push g_sph_ret
        ret
    }
}
#endif
static float __cdecl coll_dt_v3(void) {                      /* the slab accept 0x43e1c8 under =3 */
    return (g_in_coll_pass && g_sph_discard) ? coll_dt() : *(volatile float *)0x004fe420;
}
static void coll_v3_report(void) {                           /* from the pass wrapper: one line per 30 s while it changes */
    static DWORD last_frame, last_calls;
    if (g_frame - last_frame < 3600 || g_sph_calls == last_calls) return;
    {   char b[256]; int i, n = 0;
        last_frame = g_frame; last_calls = g_sph_calls;
        for (i = 0; i < 128 && n < 200; i++) if (g_sph_cls[i]) n += wsprintfA(b + n, " %x:%lu", i, g_sph_cls[i]);
        mlog("  coll-window v3: sphere->slab tests %lu, widened (class 4/5a/5b, in the pass) %lu; part classes seen:%s other %lu",
             g_sph_calls, g_sph_wide, n ? b : " -", g_sph_cls_other);
    }
}
static void apply_coll_window(void) {
    static const struct { DWORD site; BYTE old[5]; const char *what; } s[3] = {
        { 0x004349da, { 0xE8, 0xC1, 0x7D, 0x06, 0x00 }, "collision sweep dt (driver 0x4349c0)" },        /* -> [esp+0x10], the xz AABB sweep extent */
        { 0x00434c70, { 0xE8, 0x2B, 0x7B, 0x06, 0x00 }, "collision sweep dt (pair test 0x434bb0)" },     /* pushed to the swept-sphere test 0x434f00 */
        { 0x0043f9e1, { 0xE8, 0xBA, 0xCD, 0x05, 0x00 }, "collision sweep dt (scenery tree 0x43f8c0)" },  /* pushed to the node sweep */
    };
    int i, n = 0;
    if (!env_present("I76_COLL_WINDOW")) return;
    if (g_fixed_step <= 0.0f) { mlog("  coll-window: needs I76_FIXED_STEP - not applied"); return; }
    for (i = 0; i < 3; i++) {
        BYTE w[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)coll_dt - (s[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(s[i].site, s[i].old, w, 5, s[i].what);
    }
    mlog("  coll-window: %d/3 sweep dt reads -> max(sim_dt, fixed step %.1f ms)", n, g_fixed_step * 1000.0f);
    {   char v[4]; DWORD k = env_str("I76_COLL_WINDOW", v, sizeof(v));
        if (k == 1 && v[0] == '2') {
            static const struct { DWORD site; BYTE old[5]; void *fn; const char *what; } t[3] = {
                { 0x00403a12, { 0xE8, 0xA9, 0x0F, 0x03, 0x00 }, (void *)coll_pass_wrap, "collision pass flag (WinMain -> 0x4349c0)" },
                { 0x0043e1c8, { 0xE8, 0xD3, 0xE5, 0x05, 0x00 }, (void *)coll_dt_gated,  "collision accept dt (slab test 0x43df10)" },
                { 0x0043ec6a, { 0xE8, 0x31, 0xDB, 0x05, 0x00 }, (void *)coll_dt_gated,  "collision accept dt (mesh test 0x43ebc0)" },
            };
            int m = 0, mask = env_int("I76_COLL_WINDOW_SITES", 8, 3) & 3;  /* 1 = slab test 0x43e1c8, 2 = mesh test 0x43ec6a (2026-10-09: both = the car sank into the terrain on t04 drives) */
            for (i = 0; i < 3; i++) {
                BYTE w[5] = { 0xE8 };
                LONG rel = (LONG)((DWORD_PTR)t[i].fn - (t[i].site + 5)); memcpy(w + 1, &rel, 4);
                if (i > 0 && m == 0) break;                 /* no flag, no gated reads: the AI would see the window */
                if (i > 0 && !(mask & (1 << (i - 1)))) continue;
                m += patch_bytes(t[i].site, t[i].old, w, 5, t[i].what);
            }
            {   char wv[16], sv[16];
                DWORD wk = GetEnvironmentVariableA("I76_COLL_WINDOW_WHEN", wv, sizeof(wv));
                DWORD sk = GetEnvironmentVariableA("I76_COLL_WINDOW_SCALE", sv, sizeof(sv));
                if (sk && sk < sizeof(sv)) {
                    double f = atof(sv);
                    if (f >= 0.05 && f <= 1.0) g_cw_scale = (float)f;
                    else mlog("  coll-window: I76_COLL_WINDOW_SCALE=%s outside 0.05..1 - ignored", sv);
                }
                if (wk && wk < sizeof(wv)) {
                    if (lstrcmpiA(wv, "stepframe") == 0) g_cw_when = (m > 0);
                    else if (lstrcmpiA(wv, "always") != 0) mlog("  coll-window: I76_COLL_WINDOW_WHEN=%s unknown (always | stepframe) - every frame", wv);
                }
            }
            mlog("  coll-window v2: %d patched (pass flag + accept tests, sites mask %d: 1 slab 0x43e1c8, 2 mesh 0x43ec6a); when %s, scale %.2f (window %.1f ms of the %.1f ms step)",
                 m, mask, g_cw_when ? "stepframe (only for a body whose tick steps this frame, n x step)" : "every frame",
                 g_cw_scale, g_cw_scale * g_fixed_step * 1000.0f, g_fixed_step * 1000.0f);
        }
#ifdef _MSC_VER
        else if (k == 1 && v[0] == '3') {
            static const struct { DWORD site; BYTE old[5]; void *fn; const char *what; } t3[3] = {
                { 0x00403a12, { 0xE8, 0xA9, 0x0F, 0x03, 0x00 }, (void *)coll_pass_wrap, "collision pass flag (WinMain -> 0x4349c0)" },
                { 0x00440f37, { 0xE8, 0xD4, 0xCF, 0xFF, 0xFF }, (void *)sph_slab_thunk, "sphere test -> slab test (part class probe)" },
                { 0x0043e1c8, { 0xE8, 0xD3, 0xE5, 0x05, 0x00 }, (void *)coll_dt_v3,     "collision accept dt (slab test, breakable spheres only)" },
            };
            int m = 0;
            for (i = 0; i < 3; i++) {
                BYTE w[5] = { 0xE8 };
                LONG rel = (LONG)((DWORD_PTR)t3[i].fn - (t3[i].site + 5)); memcpy(w + 1, &rel, 4);
                if (i > 0 && m == 0) break;                 /* no flag: nothing is gated, leave the rest stock */
                m += patch_bytes(t3[i].site, t3[i].old, w, 5, t3[i].what);
            }
            g_coll_v3 = (m == 3);
            mlog("  coll-window v3: %d/3 patched (pass flag, sphere->slab probe 0x440f37, slab accept 0x43e1c8 widened only for "
                 "sphere parts of class 4 / 0x5a / 0x5b; mesh 0x43ec6a and box-box stock)", m);
        }
#endif
    }
}

/* ===========================================================================
 * COLLISION CONTACT REPEATS  (with I76_FIXED_STEP; I76_COLL_DEDUPE=0 counts only)
 * ===========================================================================
 * docs/records/PER-FRAME-AUDIT-2026-10-03.md C1. A dependency the fixed step itself creates. physics_CollideAll 0x4349c0 runs
 * once per rendered frame (WinMain 0x403a12, after the frame clock, before the object ticks). For every contact
 * physics_CollideBodyPair 0x434bb0 plays an impact sound (sound_PlayOnObject at 0x434ebc, or vvbo1.wav at 0x434d7e for
 * a walkable structure) and runs both bodies' class collision handlers (object_ClassCollide 0x461f70), which apply
 * physics_ApplyCollisionDamage 0x4a7c80 AT ONCE (vehicles: entity_CollideStoreContact 0x4643c0 at 0x4644bc; scenery
 * and types 7 / 0xa: object_CollideApplyDamage 0x46f890 at 0x46f8d4) and stamp the AI damage event. A car then
 * consumes the stored contact on its next substep. Stock runs at least one substep every frame, so the response
 * always lands before the next test. With the fixed step at 60 / 120 fps most frames run NO substep: pose and
 * velocity are bit-identical on the next frame, the same contact is found again, and the sound, the damage and the
 * AI event repeat on every frame until the step comes - up to 3 times per impact at 60 fps with 24 steps/s, 5 at 120.
 *
 * A contact is a repeat when the same pair made one on the previous frame and neither body has moved since: for a
 * vehicle, exactly, its fixed stepper ran 0 steps in the previous frame's tick (g_step_acc, stamped by
 * fixed_stepper_begin; a far or wrecked vehicle does not go through it and counts as moved); for anything else its
 * position doubles (+0x40) are unchanged. The two `call physics_CollideShapes 0x43f510` in the pair test (0x434ccf /
 * 0x434cf1, the only callers) are wrapped to make that call; on a repeat the two sound calls and the two damage
 * calls return without acting. The handlers still run, so the stored contact record is rewritten exactly as before.
 * Without the fixed step nothing is patched. Static reading, not measured: the acceptance run is the counters
 * (coll_events / coll_dups per second in sustained contact) and the damage per ram at 20 vs 120 fps.
 */
typedef struct { BYTE *a, *b; DWORD frame; double pa[3], pb[3]; } collpair_t;
static collpair_t g_collpair[64];
static int g_coll_dedupe = 1;
static DWORD g_idbg_coll_events, g_idbg_coll_dups;
static int coll_body_unmoved(BYTE *obj, const double *snap) {
    if (*(int *)(obj + 0x6c) == 1 && *(BYTE **)(obj + 0x70)) {                 /* a vehicle: stepper at entity+0x444 */
        int s = step_slot(*(BYTE **)(obj + 0x70) + 0x444, 0);
        return s >= 0 && g_step_acc[s].frame == g_frame - 1 && g_step_acc[s].n == 0;
    }
    return memcmp(obj + 0x40, snap, 24) == 0;
}
static int __cdecl coll_shapes_wrap(BYTE **ra, BYTE **rb, void *ca, void *cb) {
    int r, i, slot = 0;
    BYTE *a, *b;
    DWORD oldest = 0xffffffff;
    if (g_cw_when) g_pair_win = (ra && rb) ? coll_pair_window(*ra, *rb) : -1.0f;   /* I76_COLL_WINDOW_WHEN=stepframe */
    r = ((int (__cdecl *)(BYTE **, BYTE **, void *, void *))(DWORD_PTR)NA(0x0043f510))(ra, rb, ca, cb);
    g_pair_win = -1.0f;
    g_coll_dup = 0;
    if (!r) return r;
    a = *ra; b = *rb;                                                          /* record +0: the object */
    if (!a || !b) return r;
    if (a > b) { BYTE *t = a; a = b; b = t; }                                  /* the two call sites pass either order */
    g_idbg_coll_events++;
    for (i = 0; i < 64; i++) {
        if (g_collpair[i].a == a && g_collpair[i].b == b) { slot = i; break; }
        if (g_collpair[i].frame < oldest) { oldest = g_collpair[i].frame; slot = i; }
    }
    if (i < 64 && g_collpair[slot].frame == g_frame - 1
        && coll_body_unmoved(a, g_collpair[slot].pa) && coll_body_unmoved(b, g_collpair[slot].pb)) {
        g_idbg_coll_dups++;
        g_coll_dup = g_coll_dedupe;
    }
    g_collpair[slot].a = a; g_collpair[slot].b = b; g_collpair[slot].frame = g_frame;
    memcpy(g_collpair[slot].pa, a + 0x40, 24); memcpy(g_collpair[slot].pb, b + 0x40, 24);
    return r;
}
static int __cdecl coll_sound_wrap(const char *name, BYTE *obj, int flag) {
    if (g_coll_dup) return 0;
    return ((int (__cdecl *)(const char *, BYTE *, int))(DWORD_PTR)NA(0x004231f0))(name, obj, flag);
}
/* I76_BREAKABLE_BOX=2 (2026-10-12, owner: "a few signs like the highway 360 one that you can run into like 10 times
 * before anything happens"; lab docs/SIGN-FIX-2026-10-12.md). 0x4a7c80 scores mass x (v . n)^2 x 6.67e-5, truncated,
 * against the part's hit points (5 for every sign); n is the contact normal. For a sphere contact (every sign post)
 * that is the car-box face the post's centre crossed, so a post entering through the TOP face (sign on a bank above
 * the road: 32 posts game-wide, e.g. the US 380 shields in T02 / T07) or a SIDE face (a swerve or slide into it)
 * scores ~0 and the sign stays up. Under =2, for a class-4 victim, n becomes the unit vector along the impact
 * velocity (same hemisphere as the stock n), so the score is mass x |v|^2 x 6.67e-5: any ram above the stock
 * threshold speed (about 6.3 m/s for a 1900 kg car) knocks it off, whatever face it came through. Vehicles, classes
 * 2 / 7 / 10 and every other damage path keep the stock normal. */
static int g_bbox_speed;
static volatile DWORD g_bbox_speed_hits, g_bbox_speed_glance;
static struct { BYTE *root; DWORD frame; } g_sweep_hit[32];        /* =3: recent engine class-4 contacts (root, frame) */
static int g_sweep_hit_i;
static void sweep_note_engine_hit(BYTE *root) {
    int i;
    for (i = 0; i < 32; i++) if (g_sweep_hit[i].root == root) { g_sweep_hit[i].frame = g_frame; return; }
    g_sweep_hit[g_sweep_hit_i].root = root; g_sweep_hit[g_sweep_hit_i].frame = g_frame; g_sweep_hit_i = (g_sweep_hit_i + 1) & 31;
}
static int sweep_engine_hit_since(BYTE *root, DWORD frames) {
    int i;
    for (i = 0; i < 32; i++) if (g_sweep_hit[i].root == root) return g_frame - g_sweep_hit[i].frame <= frames;
    return 0;
}
static int bbox_speed_normal(BYTE *victim, const float *v, const float *n, float *out) {
    BYTE *root = victim;
    double vv, d, k;
#ifdef _MSC_VER
    __try {
#endif
        if (!victim || !v || !n) return 0;
        while (*(BYTE **)(root + 0x68)) root = *(BYTE **)(root + 0x68);     /* 0x458c90: the tree root (the ODEF object) */
        if (*(int *)(victim + 0x6c) != 4 && *(int *)(root + 0x6c) != 4) return 0;
        sweep_note_engine_hit(root);                                          /* =3: the sweep leaves this one alone */
        vv = (double)v[0] * v[0] + (double)v[1] * v[1] + (double)v[2] * v[2];
        if (vv < 1e-4) return 0;
        vv = sqrt(vv);
        d = ((double)v[0] * n[0] + (double)v[1] * n[1] + (double)v[2] * n[2]) / vv;   /* cos(impact, normal) */
        k = (d < 0.0 ? -1.0 : 1.0) / vv;
        out[0] = (float)(v[0] * k); out[1] = (float)(v[1] * k); out[2] = (float)(v[2] * k);
        g_bbox_speed_hits++;
        if (d > -0.7 && d < 0.7) g_bbox_speed_glance++;
        if (g_bbox_speed_hits <= 40)
            mlog("  breakable-speed: class-4 hit %lu, closing %.1f m/s, along the stock normal %.1f m/s (score x%.1f)%s",
                 g_bbox_speed_hits, vv, vv * (d < 0.0 ? -d : d), d * d > 1e-6 ? 1.0 / (d * d) : 999.0,
                 d > -0.7 && d < 0.7 ? " - glancing: stock would have scored it low" : "");
        return 1;
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    return 0;
}
static DWORD __cdecl coll_damage_wrap(DWORD victim, DWORD source, DWORD v, DWORD n, DWORD p) {
    float nn[3];
    if (g_coll_dup) return 1;                                                  /* "victim still there"; both callers ignore it */
    if (g_bbox_speed && bbox_speed_normal((BYTE *)victim, (const float *)v, (const float *)n, nn)) n = (DWORD)(DWORD_PTR)nn;
    if (g_bbox_defer && sign_defer_engine((BYTE *)victim, (BYTE *)source, (const float *)v, (const float *)n, (const float *)p)) return 1;
    if (g_bbox_sweep && !g_bbox_defer) sign_gap_log_engine((BYTE *)victim, (BYTE *)source);
    if (g_stf_scrape_on) return st_coll_damage_call(victim, source, v, n, p);   /* tick-factors: repeats of a contact at the 1997 rate */
    return ((DWORD (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD))(DWORD_PTR)NA(0x004a7c80))(victim, source, v, n, p);
}
static void apply_coll_dedupe(void) {
    static const struct { DWORD site, target; void *wrap; const char *what; } cs[6] = {
        { 0x00434ccf, 0x0043f510, (void *)coll_shapes_wrap, "collision contact test" },             /* E8 3C A8 00 00 */
        { 0x00434cf1, 0x0043f510, (void *)coll_shapes_wrap, "collision contact test (swapped)" },   /* E8 1A A8 00 00 */
        { 0x00434d7e, 0x004231f0, (void *)coll_sound_wrap,  "collision sound (walkable)" },         /* E8 6D E4 FE FF */
        { 0x00434ebc, 0x004231f0, (void *)coll_sound_wrap,  "collision sound (impact)" },           /* E8 2F E3 FE FF */
        { 0x004644bc, 0x004a7c80, (void *)coll_damage_wrap, "collision damage (vehicles)" },        /* E8 BF 37 04 00 */
        { 0x0046f8d4, 0x004a7c80, (void *)coll_damage_wrap, "collision damage (objects)" } };       /* E8 A7 83 03 00 */
    int i, n = 0;
    if (g_fixed_step <= 0.0f) return;                       /* only the fixed step makes frames without a substep */
    install_frame_hook();
    if (!g_frame_hook) { mlog("  coll-dedupe: frame hook missing - not applied"); return; }
    for (i = 0; i < 6; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
    }
    if (env_flag("I76_COLL_DEDUPE", 8, 1) == 0) g_coll_dedupe = 0;
    mlog("  coll-dedupe: %d/6 sites repointed (contact repeats on frames without a physics step: sound + damage %s)",
         n, g_coll_dedupe ? "applied once per step" : "counted, passed through");
}

/* ===========================================================================
 * RENDER INTERPOLATION  (I76_RENDER_INTERP=1, needs I76_FIXED_STEP; off by default)
 * ===========================================================================
 * With a fixed 25 ms physics step at 60 fps, the cars advance on two frames out
 * of three and stand still on the third: a 20 Hz judder. The fix is the standard
 * one: draw each vehicle between its last two physics poses, at the fraction of
 * a step that has accumulated since (alpha = leftover / step, one step of display
 * latency).
 *
 * Every object's pose is a 0x40-byte transform at object+0x18 (3x3 float rotation,
 * rows = right/up/forward, then three position doubles at +0x28), and the physics
 * writes it directly (physics_ResolveGroundContact: ebx = obj+0x18, doubles at
 * ebx+0x28). There is no separate render copy, so the interpolated pose is
 * swapped in around the render call only and the physics value is restored
 * right after; the simulation never sees it.
 *   vehicle tick   class table slot 0x4f7788 (type 1, +0xc = entity_TickVehicle 0x463800) points at a wrapper
 *                  that keeps the pose before the last substep
 *   render         `call 0x401c90` (render(&camera 0x4c2730)) at 0x403e69
 *   camera         the camera modes set the view with 0x472990 (SetTransform(cam, T)) from inside the player's
 *                  tick, i.e. from the physics pose. The entry is detoured (first 6 bytes 55 8B EC 83 E4 F8 run
 *                  in a trampoline) to record the last T; at render time a camera set by a camera mode function
 *                  (0x405b90..0x409700, car-relative) is moved rigidly with the player's interpolation, and put
 *                  back after the frame. Script cameras (fsm_Cam*, 0x49d4a0..) are world-fixed and left alone.
 * Objects ticked this frame are re-validated through the live-object list (0x54b204, lookup 0x45f0f0) before
 * their pose is touched, so an object destroyed later in the frame is skipped.
 */
typedef struct { float r[9]; float pad; double p[3]; } xform_t;     /* 0x40 bytes */
typedef struct { BYTE *obj; xform_t prev2, prev, disp, save; float alpha; DWORD stamp; int player, live; } ient_t;
static ient_t g_ie[64];
static void ient_disp(ient_t *e, xform_t *out, const xform_t *cur);
static int g_interp;
static BYTE *g_cam_tramp;
static xform_t g_cam_last;
static DWORD g_cam_stamp, g_cam_caller, g_cam_sets;
/* read by captures\014-framerate\fr_probe.py (address logged at start) */
static struct { DWORD frame; float alpha; double true_p[3], disp_p[3]; int nveh, cam_fixed; DWORD cam_caller, cam_mode; double cam_true[3], cam_drawn[3];
                struct { DWORD frame, cam; double true_p[3], disp_p[3], cam_p[3]; float v_tick0, v_tick1; int steps, pad; float roll_t, pitch_t, roll_d, pitch_d; } ring[16];
                DWORD ping_req, ping_play, ping_frames, flame_hits, flame_dmg, aifire_calls, aifire_yes, tick20_n;
                DWORD dodge_calls, dodge_yes, mirror_draws, far_steps;
                DWORD hazard_impacts, hazard_steps, radar_turns, wmiss_req, wmiss_play, skid_rolls, horn_rolls, coll_events, coll_dups;   /* PER-FRAME-AUDIT-2026-10-03 */
              } g_idbg;   /* every frame, for samplers that miss some; new fields append */

static float v3dot(const float *a, const float *b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
static void v3norm(float *a) {
    float l = sqrtf(v3dot(a, a));
    if (l > 1e-12f) { a[0] /= l; a[1] /= l; a[2] /= l; }
}
/* o = a + (b - a) t, rotation re-orthonormalised (forward row kept, then up, then right: handedness of the lerp) */
static void xf_lerp(xform_t *o, const xform_t *a, const xform_t *b, float t) {
    int i;
    float *rt = o->r, *up = o->r + 3, *fw = o->r + 6, d;
    for (i = 0; i < 9; i++) o->r[i] = a->r[i] + (b->r[i] - a->r[i]) * t;
    for (i = 0; i < 3; i++) o->p[i] = a->p[i] + (b->p[i] - a->p[i]) * (double)t;
    o->pad = b->pad;
    v3norm(fw);
    d = v3dot(up, fw); for (i = 0; i < 3; i++) up[i] -= d * fw[i];
    v3norm(up);
    d = v3dot(rt, fw); for (i = 0; i < 3; i++) rt[i] -= d * fw[i];
    d = v3dot(rt, up); for (i = 0; i < 3; i++) rt[i] -= d * up[i];
    v3norm(rt);
}
/* uniform quadratic B-spline through three poses (C1: no kink at the step boundaries); at t it sits between the
 * midpoints (a+b)/2 and (b+c)/2, i.e. half a step behind the linear blend of b and c */
static void xf_bspline(xform_t *o, const xform_t *a, const xform_t *b, const xform_t *c, float t) {
    float w0 = 0.5f * (1.0f - t) * (1.0f - t), w1 = 0.5f + t - t * t, w2 = 0.5f * t * t, d;
    float *rt = o->r, *up = o->r + 3, *fw = o->r + 6;
    int i;
    for (i = 0; i < 9; i++) o->r[i] = w0 * a->r[i] + w1 * b->r[i] + w2 * c->r[i];
    for (i = 0; i < 3; i++) o->p[i] = w0 * a->p[i] + w1 * b->p[i] + w2 * c->p[i];
    o->pad = c->pad;
    v3norm(fw);
    d = v3dot(up, fw); for (i = 0; i < 3; i++) up[i] -= d * fw[i];
    v3norm(up);
    d = v3dot(rt, fw); for (i = 0; i < 3; i++) rt[i] -= d * fw[i];
    d = v3dot(rt, up); for (i = 0; i < 3; i++) rt[i] -= d * up[i];
    v3norm(rt);
}
static int g_smooth = 1;                                     /* I76_INTERP_SMOOTH: 0 off, 1 world cameras only, 2 all */
static int smooth_now(void) {
    DWORD mode = *(DWORD *)0x004c2720;
    if (g_smooth == 2) return 1;
    if (g_smooth == 0) return 0;
    /* the player-attached views keep the low-latency linear blend: cockpit, chase, free-look */
    return !(mode == 0x00406ab0 || mode == 0x00407ad0 || mode == 0x00405b90 || mode == 0x004061b0);
}

static double xf_dist2(const xform_t *a, const xform_t *b) {
    double x = a->p[0] - b->p[0], y = a->p[1] - b->p[1], z = a->p[2] - b->p[2];
    return x * x + y * y + z * z;
}

static BYTE *g_tick_obj;                                     /* the vehicle whose tick is running, and its pose before it */
static xform_t g_tick_start;
static DWORD g_cam_interp_frame;                             /* frame whose camera update already saw the drawn pose */

/* after a vehicle's substeps: keep its pose before the last step and the blend fraction (idempotent within a frame) */
static ient_t *ient_update(BYTE *obj, const xform_t *s) {
    xform_t *e_now;
    BYTE *veh;
    int i, slot = -1, st;
    ient_t *e;
    for (i = 0; i < 64; i++) {
        if (g_ie[i].obj == obj) { slot = i; break; }
        if (slot < 0 && (g_ie[i].obj == 0 || g_frame - g_ie[i].stamp > 60)) slot = i;
    }
    if (slot < 0) return 0;                                  /* more than 64 live vehicles: draw this one un-interpolated */
    e = &g_ie[slot];
    if (e->obj == obj && e->stamp == g_frame) return e;      /* already updated this frame (camera path ran first) */
    e_now = (xform_t *)(obj + 0x18);
    veh = *(BYTE **)(obj + 0x70);
    st = veh ? step_slot(veh + 0x444, 0) : -1;
    if (e->obj != obj || st < 0 || g_step_acc[st].frame != g_frame) {
        e->prev2 = e->prev = *e_now;                         /* new, or ticked without the fixed stepper: no blend */
        e->alpha = 1.0f;
    } else {
        int n = g_step_acc[st].n;
        if (n == 1) { e->prev2 = e->prev; e->prev = *s; }
        else if (n > 1) {                                    /* the poses before the last two steps, on the frame's straight line */
            xf_lerp(&e->prev2, s, e_now, (float)(n - 2) / (float)n);
            xf_lerp(&e->prev, s, e_now, (float)(n - 1) / (float)n);
        }
        /* n == 0: no step this frame - keep the history, alpha grows */
        e->alpha = g_step_acc[st].acc / g_fixed_step;
        if (e->alpha < 0.0f) e->alpha = 0.0f; else if (e->alpha > 1.0f) e->alpha = 1.0f;
    }
    if (xf_dist2(&e->prev, e_now) > 64.0 || xf_dist2(&e->prev2, e_now) > 256.0)
        e->prev2 = e->prev = *e_now;                         /* a respawn or teleport */
    e->obj = obj;
    e->stamp = g_frame;
    e->player = ((int (__cdecl *)(BYTE *))0x00458bf0)(obj) != 0;   /* object_IsPlayer */
    return e;
}

static void __cdecl tick_vehicle_wrap(BYTE *obj) {
    xform_t s = *(xform_t *)(obj + 0x18);
    BYTE *veh = *(BYTE **)(obj + 0x70);
    float v0 = veh ? *(float *)(veh + 0xac) : 0.0f;
    ient_t *e;
    g_tick_obj = obj; g_tick_start = s;
    ((void (__cdecl *)(BYTE *))0x00463800)(obj);            /* entity_TickVehicle */
    g_tick_obj = 0;
    e = ient_update(obj, &s);
    if (e && e->player && veh) {                             /* diagnostics: speed across the player's tick, and its steps */
        int r = g_frame & 15, st = step_slot(veh + 0x444, 0);
        g_idbg.ring[r].v_tick0 = v0; g_idbg.ring[r].v_tick1 = *(float *)(veh + 0xac);
        g_idbg.ring[r].steps = (st >= 0 && g_step_acc[st].frame == g_frame) ? g_step_acc[st].n : -1;
    }
}

/* The camera mode runs once per frame from the frame loop (`call [0x4c2720]` at 0x403e16, after the object ticks and
 * before the render), and on one path from inside the player's tick (0x46391f). Run it with the player drawn where it
 * will be rendered, so a lagging chase camera follows the smooth pose instead of the 24/40 Hz physics one; the physics
 * pose is put back as soon as the camera returns. */
/* A LIVE object behind a reference handle, WITHOUT touching its reference count (2026-10-19 sp-fix lane, TICK-FINISH s.16).
 * 0x45f0f0 is not a lookup: it is the engine's release-if-dead. For an object still alive (word +8 != 1) it returns the
 * object; for a dead one it drops one reference (+0xc, and its children's through 0x45f0c0) or, at the last one, frees
 * it, and returns 0. Each holder (the live list in entity_TickAll "clasfn", the texture-animation list in
 * image_UpdateTexAnims "texanm", ...) calls it once per pass to let go of its own reference. The proxy's walks called it
 * as a lookup, so every walk over a dead object stole a reference: under the tick (wst_walk, several walks per tick) the
 * live list's release then freed objects the texture-animation list still held, and image_UpdateTexAnims read the freed
 * object (exe+0x5F103, frame 1: INSTANT MELEE on "Scene 1 (Co-op)" coop01.lvl crashed every boot under the tick).
 * mark_live (I76_RENDER_INTERP, promotion 18) had the same call. This reads the same test 0x45f0f0 makes (null handle,
 * word +8 == 1) and changes nothing. */
static BYTE *obj_live_noref(DWORD h) {
    BYTE *o = (BYTE *)(DWORD_PTR)h;
    return o && *(WORD *)(o + 8) != 1 ? o : NULL;
}
static void mark_live(void) {                                /* which of this frame's vehicles are still live objects */
    BYTE *node = *(BYTE **)0x0054b204;
    int i, guard = 0;
    for (i = 0; i < 64; i++) g_ie[i].live = 0;
    while (node && guard++ < 4096) {
        BYTE *o = obj_live_noref(*(DWORD *)(node + 8));   /* not 0x45f0f0: that releases a reference of a dead object */
        if (o) for (i = 0; i < 64; i++) if (g_ie[i].obj == o && g_ie[i].stamp == g_frame) g_ie[i].live = 1;
        node = *(BYTE **)node;
    }
}

/* Swap every vehicle ticked this frame (and still live) to its drawn pose, and back. Used around code that only
 * places the camera, so a camera tracking any car sees the pose that will be rendered. Not re-entrant. */
static int g_swapped;
static DWORD g_fsmcam_calls;                                 /* diagnostics: script camera actions run */
static int swap_all_in(void) {
    int i, n = 0;
    if (!g_interp || g_swapped) return 0;
    mark_live();
    for (i = 0; i < 64; i++) {
        ient_t *e = &g_ie[i];
        if (!e->live) continue;
        e->save = *(xform_t *)(e->obj + 0x18);
        ient_disp(e, &e->disp, &e->save);
        *(xform_t *)(e->obj + 0x18) = e->disp;
        n++;
    }
    g_swapped = 1;
    return 1;
}
static void swap_all_out(void) {
    int i;
    for (i = 0; i < 64; i++) if (g_ie[i].live) *(xform_t *)(g_ie[i].obj + 0x18) = g_ie[i].save;
    g_swapped = 0;
}

/* Script cameras (jump cam, cut-scenes): the FSM camera actions are called by fsm_ActionDispatch from the script VM
 * on every frame the script holds them, and set the view (0x472990) from object poses. Run them on drawn poses. The
 * actions are cdecl; forwarding eight dwords covers every one (extra ones are the caller's own stack, only read). */
typedef int (__cdecl *fsm8_t)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
static int fsmcam_call(DWORD addr, DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, DWORD h) {
    DWORD sets = g_cam_sets;
    int r, sw = swap_all_in();
    r = ((fsm8_t)addr)(a, b, c, d, e, f, g, h);
    if (sw) { swap_all_out(); if (g_cam_sets != sets) g_cam_interp_frame = g_frame; }
    g_fsmcam_calls++;
    return r;
}
static int __cdecl fsm_cam_objobj_w(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, DWORD h)   { return fsmcam_call(0x0049d5f0, a, b, c, d, e, f, g, h); }
static int __cdecl fsm_cam_objdir_w(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, DWORD h)   { return fsmcam_call(0x0049d4a0, a, b, c, d, e, f, g, h); }
static int __cdecl fsm_cam_toobject_w(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, DWORD h) { return fsmcam_call(0x0049d740, a, b, c, d, e, f, g, h); }
static int __cdecl fsm_cam_transdir_w(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, DWORD h) { return fsmcam_call(0x0049dac0, a, b, c, d, e, f, g, h); }
static int __cdecl fsm_cam_f12_w(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, DWORD h)      { return fsmcam_call(0x0049dda0, a, b, c, d, e, f, g, h); }

static void __cdecl cam_update_wrap(void) {
    void (__cdecl *mode)(void) = *(void (__cdecl **)(void))0x004c2720;
    BYTE *obj = g_tick_obj;
    ient_t *e = 0;
    int i;
    (void)i;
    if (g_interp && !obj) {                                             /* the frame loop's camera update (0x403e16) */
        DWORD sets = g_cam_sets;
        if (g_lat_step_fn) g_lat_step_fn();                             /* lab latency probe: the sim block is done */
        int sw = swap_all_in();                                         /* every car on its drawn pose */
        if (mode) mode();
        if (sw) { swap_all_out(); if (g_cam_sets != sets) g_cam_interp_frame = g_frame; }
        return;
    }
    if (g_interp && obj) e = ient_update(obj, &g_tick_start);          /* from inside the player's tick (0x46391f) */
    if (e) {
        xform_t save = *(xform_t *)(obj + 0x18), disp;
        DWORD sets = g_cam_sets;
        ient_disp(e, &disp, &save);
        *(xform_t *)(obj + 0x18) = disp;
        mode();
        *(xform_t *)(obj + 0x18) = save;
        if (g_cam_sets != sets) g_cam_interp_frame = g_frame;   /* the view was set from the drawn pose */
    } else if (mode) mode();
}

static void ient_disp(ient_t *e, xform_t *out, const xform_t *cur) {
    if (smooth_now()) xf_bspline(out, &e->prev2, &e->prev, cur, e->alpha);
    else xf_lerp(out, &e->prev, cur, e->alpha);
}

static int __cdecl cam_set_hook(BYTE *cam, xform_t *t) {
    if (cam == (BYTE *)0x004c2730 && t) {
#ifdef _MSC_VER
        g_cam_caller = (DWORD)(DWORD_PTR)_ReturnAddress();
#else
        g_cam_caller = (DWORD)(DWORD_PTR)__builtin_return_address(0);
#endif
        g_cam_last = *t; g_cam_stamp = g_frame; g_cam_sets++;
    }
    return ((int (__cdecl *)(BYTE *, xform_t *))g_cam_tramp)(cam, t);
}

static void __cdecl render_wrap(void *cam) {
    int i, n = 0, cam_fixed = 0;
    ient_t *pl = 0;
    xform_t camx;
    if (g_interp) {
        mark_live();
        for (i = 0; i < 64; i++) {
            ient_t *e = &g_ie[i];
            if (!e->live) continue;
            e->save = *(xform_t *)(e->obj + 0x18);
            ient_disp(e, &e->disp, &e->save);
            *(xform_t *)(e->obj + 0x18) = e->disp;
            if (e->player) pl = e;
            n++;
        }
        if (pl) {                                           /* I76_BREAKABLE_BOX=4 (and its =3 gap log): the pose on screen */
            if (g_pld_frame == g_frame - 1 && g_pld_obj == pl->obj) memcpy(g_pld_prev, g_pld_p, 24); else memcpy(g_pld_prev, pl->disp.p, 24);
            memcpy(g_pld_p, pl->disp.p, 24); memcpy(g_pld_r, pl->disp.r, 36); g_pld_obj = pl->obj; g_pld_frame = g_frame;
        }
        if (pl && g_cam_stamp == g_frame && g_cam_interp_frame != g_frame &&
            g_cam_caller >= 0x00405b90 && g_cam_caller < 0x00409700) {
            /* carry the camera with the player: c' = (c - p) M + p', Rc' = Rc M, M = R^T R' (row vectors) */
            const float *R = pl->save.r, *Q = pl->disp.r, *C = g_cam_last.r;
            float M[9];
            int j, k;
            for (j = 0; j < 3; j++) for (k = 0; k < 3; k++)
                M[j * 3 + k] = R[0 * 3 + j] * Q[0 * 3 + k] + R[1 * 3 + j] * Q[1 * 3 + k] + R[2 * 3 + j] * Q[2 * 3 + k];
            camx = g_cam_last;
            for (j = 0; j < 3; j++) for (k = 0; k < 3; k++)
                camx.r[j * 3 + k] = C[j * 3 + 0] * M[0 * 3 + k] + C[j * 3 + 1] * M[1 * 3 + k] + C[j * 3 + 2] * M[2 * 3 + k];
            for (k = 0; k < 3; k++)
                camx.p[k] = (g_cam_last.p[0] - pl->save.p[0]) * M[0 * 3 + k] + (g_cam_last.p[1] - pl->save.p[1]) * M[1 * 3 + k]
                          + (g_cam_last.p[2] - pl->save.p[2]) * M[2 * 3 + k] + pl->disp.p[k];
            ((int (__cdecl *)(BYTE *, xform_t *))g_cam_tramp)((BYTE *)0x004c2730, &camx);
            cam_fixed = 1;
            for (k = 0; k < 3; k++) { g_idbg.cam_true[k] = g_cam_last.p[k]; g_idbg.cam_drawn[k] = camx.p[k]; }
        }
        g_idbg.ping_req = g_idbg_ping_req; g_idbg.ping_play = g_idbg_ping_play; g_idbg.ping_frames = g_idbg_ping_frames;
        g_idbg.flame_hits = g_idbg_flame_hits; g_idbg.flame_dmg = g_idbg_flame_dmg;
        g_idbg.aifire_calls = g_idbg_aifire_calls; g_idbg.aifire_yes = g_idbg_aifire_yes; g_idbg.tick20_n = g_tick20_n;
        g_idbg.dodge_calls = g_idbg_dodge_calls; g_idbg.dodge_yes = g_idbg_dodge_yes;
        g_idbg.mirror_draws = g_idbg_mirror_draws; g_idbg.far_steps = g_idbg_far_steps;
        g_idbg.hazard_impacts = g_idbg_hazard_calls; g_idbg.hazard_steps = g_idbg_hazard_steps; g_idbg.radar_turns = g_idbg_radar_turns;
        g_idbg.wmiss_req = g_idbg_wmiss_req; g_idbg.wmiss_play = g_idbg_wmiss_play;
        g_idbg.skid_rolls = g_idbg_skid_rolls; g_idbg.horn_rolls = g_idbg_horn_rolls;
        g_idbg.coll_events = g_idbg_coll_events; g_idbg.coll_dups = g_idbg_coll_dups;
        g_idbg.frame = g_frame; g_idbg.nveh = n; g_idbg.cam_fixed = cam_fixed;
        g_idbg.cam_caller = g_cam_caller; g_idbg.cam_mode = *(DWORD *)0x004c2720;
        if (pl) {
            int r = g_frame & 15;
            g_idbg.alpha = pl->alpha;
            for (i = 0; i < 3; i++) { g_idbg.true_p[i] = pl->save.p[i]; g_idbg.disp_p[i] = pl->disp.p[i]; }
            g_idbg.ring[r].frame = 0;                            /* frame number last, so a reader never pairs it with old data */
            g_idbg.ring[r].cam = cam_fixed ? 1 : (g_cam_interp_frame == g_frame ? 2 : 0);   /* 1 carried, 2 set from drawn pose */
            g_idbg.ring[r].pad = (int)g_fsmcam_calls;                                      /* script camera actions so far */
            for (i = 0; i < 3; i++) {
                g_idbg.ring[r].true_p[i] = pl->save.p[i]; g_idbg.ring[r].disp_p[i] = pl->disp.p[i];
                g_idbg.ring[r].cam_p[i] = cam_fixed ? camx.p[i] : g_cam_last.p[i];
            }
            /* body attitude, true and drawn: roll = asin(right.y), pitch = asin(forward.y) (rows right/up/forward) */
            g_idbg.ring[r].roll_t = pl->save.r[1]; g_idbg.ring[r].pitch_t = pl->save.r[7];
            g_idbg.ring[r].roll_d = pl->disp.r[1]; g_idbg.ring[r].pitch_d = pl->disp.r[7];
            *(volatile DWORD *)&g_idbg.ring[r].frame = g_frame;
        }
    }
    if (g_jc_on && !g_simtick) { judder_census(); judder_census_publish(); }   /* I76_JUDDER_CENSUS (simtick.c) */
    if (g_lat_draw_fn) g_lat_draw_fn();                     /* lab latency probe: this frame draws the result */
    ((void (__cdecl *)(void *))0x00401c90)(cam);
    if (g_interp) {
        for (i = 0; i < 64; i++) if (g_ie[i].live) *(xform_t *)(g_ie[i].obj + 0x18) = g_ie[i].save;
        if (cam_fixed) ((int (__cdecl *)(BYTE *, xform_t *))g_cam_tramp)((BYTE *)0x004c2730, &g_cam_last);
    }
}

static void apply_render_interp(void) {
    static const BYTE tick_old[4] = { 0x00, 0x38, 0x46, 0x00 };                 /* 0x463800 in the class table */
    static const BYTE rend_old[5] = { 0xE8, 0x22, 0xDE, 0xFF, 0xFF };           /* call 0x401c90 at 0x403e69 */
    static const BYTE cam_old[6]  = { 0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF8 };     /* 0x472990 entry */
    static const BYTE camu_old[6] = { 0xFF, 0x15, 0x20, 0x27, 0x4C, 0x00 };     /* call [0x4c2720] at 0x46391f */
    BYTE camu_new[6] = { 0xE8, 0, 0, 0, 0, 0x90 };
    BYTE tick_new[4], rend_new[5] = { 0xE8 }, cam_new[6] = { 0xE9, 0, 0, 0, 0, 0x90 };
    DWORD a; LONG rel; int ok = 0;
    if (!env_present("I76_RENDER_INTERP")) return;
    g_smooth = env_int("I76_INTERP_SMOOTH", 8, g_smooth);
    if (g_fixed_step <= 0.0f) { mlog("  render-interp: needs I76_FIXED_STEP - not applied"); return; }
    install_frame_hook();
    if (!g_frame_hook) { mlog("  render-interp: frame hook missing - not applied"); return; }
    if (memcmp((void *)0x00472990, cam_old, 6) != 0 || memcmp((void *)0x00403e69, rend_old, 5) != 0 ||
        memcmp((void *)0x004f7788, tick_old, 4) != 0) {
        mlog("  render-interp: unexpected bytes at a hook site - not applied"); return;
    }
    g_cam_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_cam_tramp) return;
    memcpy(g_cam_tramp, cam_old, 6);
    g_cam_tramp[6] = 0xE9;
    rel = (LONG)(0x00472996 - ((DWORD_PTR)g_cam_tramp + 11)); memcpy(g_cam_tramp + 7, &rel, 4);
    rel = (LONG)((DWORD_PTR)cam_set_hook - (0x00472990 + 5)); memcpy(cam_new + 1, &rel, 4);
    rel = (LONG)((DWORD_PTR)render_wrap - (0x00403e69 + 5)); memcpy(rend_new + 1, &rel, 4);
    a = (DWORD)(DWORD_PTR)tick_vehicle_wrap; memcpy(tick_new, &a, 4);
    ok += patch_bytes(0x00472990, cam_old, cam_new, 6, "camera SetTransform entry");
    ok += patch_bytes(0x00403e69, rend_old, rend_new, 5, "render call");
    ok += patch_bytes(0x004f7788, tick_old, tick_new, 4, "vehicle tick class slot");
    g_interp = ok == 3;
    if (g_interp) {                                          /* optional: camera update against the drawn pose */
        rel = (LONG)((DWORD_PTR)cam_update_wrap - (0x0046391f + 5)); memcpy(camu_new + 1, &rel, 4);
        ok += patch_bytes(0x0046391f, camu_old, camu_new, 6, "player camera update call (in tick)");
        rel = (LONG)((DWORD_PTR)cam_update_wrap - (0x00403e16 + 5)); memcpy(camu_new + 1, &rel, 4);
        ok += patch_bytes(0x00403e16, camu_old, camu_new, 6, "camera update call (frame loop)");
        {
            static const struct { DWORD site, target; void *w; } fc[6] = {
                { 0x00413118, 0x0049d5f0, (void *)fsm_cam_objobj_w },  { 0x0041319a, 0x0049d4a0, (void *)fsm_cam_objdir_w },
                { 0x004131f1, 0x0049d740, (void *)fsm_cam_toobject_w }, { 0x00413266, 0x0049d740, (void *)fsm_cam_toobject_w },
                { 0x004132ac, 0x0049dac0, (void *)fsm_cam_transdir_w }, { 0x00413327, 0x0049dda0, (void *)fsm_cam_f12_w } };
            int j;
            for (j = 0; j < 6; j++) {
                BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
                LONG r0 = (LONG)(fc[j].target - (fc[j].site + 5)), r1 = (LONG)((DWORD_PTR)fc[j].w - (fc[j].site + 5));
                memcpy(o + 1, &r0, 4); memcpy(w + 1, &r1, 4);
                ok += patch_bytes(fc[j].site, o, w, 5, "script camera action call");
            }
        }
    }
    mlog("  render-interp: %d/11 hooks, %s, smoothing %d (debug block %p)", ok, g_interp ? "on" : "NOT applied", g_smooth, (void *)&g_idbg);
}

/* ===========================================================================
 * TELEMETRY EXPORT  (I76_TELEMETRY=<udp port>; 1 = port 7676; off by default)
 * ===========================================================================
 * Replaces the memory scanners the FFB / motion tools use to read the player's
 * state (docs/records/FFB-DATA-AUDIT.md section 4.2, row 8 of section 6). Once per
 * rendered frame a packed i76tel_frame_t (tools/telemetry/i76tel.h, the one
 * source of the layout) is filled from the player's object / entity / engine /
 * wheel blocks and from the exe's own FFB block 0x4f2328, then
 *   (a) sent as one UDP datagram to 127.0.0.1:port, followed by the events
 *       recorded since the previous send, and
 *   (b) written in place to the shared memory Local\I76Telemetry together with
 *       the whole 64-entry event ring, bracketed by a seq counter (odd while
 *       writing, even when consistent) so a reader can reject a torn copy.
 *
 * WHEN. The audit suggested the `call 0x446110` at 0x445e83 (ffb_WriteSimState's
 * dispatch) or the render wrapper. Neither is unconditional: 0x445ba0 returns at
 * 0x445bb0 unless 0x52bbd0 == 1 (a wheel driver or the shim present), and
 * render_wrap exists only under I76_RENDER_INTERP. The frame hook at 0x4039b8 is
 * the point every per-frame feature here already shares, and WinMain's loop
 * (framerate.md: clock, input, ticks, post-ticks, VM, camera, render, Flip) makes
 * its entry the first instruction after the previous frame is complete. So the
 * snapshot is taken at the top of frame_cap_then_clock, before simclock_Update
 * advances the counters: it describes the frame just shown, with the physics
 * pose (render-interp puts the drawn pose back after the render call).
 *
 * WHAT. Player chain [0x54a264] -> record -> [+0] object -> [obj+0x70] entity,
 * accepted only while object flag 0x10 (local player, the test object_IsPlayer
 * 0x458bf0 makes) is set; engine [[ent+0x3c4]+0x70] type 21, suspension +0x3c8
 * type 23, brakes +0x3cc type 22, wheels [ent+0x3a8+4i] type 30 - each component
 * is used only when its object carries that class type at +0x6c. Field sources
 * are cited in i76tel.h. The snapshot runs under SEH: between missions the record
 * pointer can be stale, and a fault there must cost one frame of telemetry, not
 * the game.
 *
 * EVENTS, through the two hook kinds already in this file:
 *   weapon_FireShot 0x4a6e90(instance, weapdef, count, dt_left) - two call sites
 *       (0x4a6b16, 0x4a6d43, both in weapon_UpdateInstanceFiring 0x4a6470) are
 *       repointed; the wrapper records player shots (instance+0x18 -> vehicle
 *       weapon record -> +0 vehicle object) after the shot, so ammo is post-shot.
 *   entity_SpawnExplosion 0x49ead0(name lo, name hi, p3, x, y, z, owner) - 21
 *       call sites in 14 functions, so its entry is detoured as cam_set_hook
 *       does 0x472990: the 8 position-independent prologue bytes run in a
 *       trampoline. The template name is passed by value as two dwords (the
 *       function upper-cases its own copy).
 *   physics_ApplyCollisionDamage 0x4a7c80(target, source, normal, impact vector,
 *       direction) - 7 call sites, entry detoured (6 bytes). The damage amount is
 *       computed inside (weapon_BuildImpactDamage for ordnance, mass x closing
 *       speed for collisions) and only reaches the FFB lists while 0x52bbd0 == 1,
 *       so the wrapper measures it as the player's armour + chassis + component
 *       hp before minus after the call.
 * Zero cost when I76_TELEMETRY is unset: nothing is patched and the frame hook
 * is not installed on its account.
 * Verified live 2026-10-01 (tools/telemetry/verification-2026-10-01.txt).
 *
 * i76tel v3 (2026-10-10, docs/HAPTICS-ARCHITECTURE.md 4.1): the event grew to
 * 56 bytes, the frame gained wheelbase / track / steer gain / grip cap / ground
 * g / music track / hook mask (appended, v2 offsets unchanged), and two opt-in
 * event groups, each only with I76_TELEMETRY on (see "SOUND / DAMAGE EVENTS"
 * below): I76_SOUND_EVENTS=1 (SOUND_START / SOUND_STOP / WEAPON_UI) and
 * I76_DAMAGE_EVENTS=1 (DAMAGE_SIDE). Unset, neither patches anything. The v3
 * additions are static-verified only (tools/telemetry/verify_v3_sites.py).
 */
static i76tel_event_t g_tel_ring[I76TEL_RING];
static DWORD g_tel_ev_seq, g_tel_ev_sent, g_tel_pub_seq, g_tel_faults;
static HMODULE g_tel_ws;
static SOCKET g_tel_sock = INVALID_SOCKET;
static struct sockaddr_in g_tel_dst;
static int (__stdcall *p_tel_sendto)(SOCKET, const char *, int, int, const struct sockaddr *, int);
static HANDLE g_tel_map;
static i76tel_shm_t *g_tel_shm;
static BYTE *g_tel_tramp, *g_tel_expl_tramp, *g_tel_coll_tramp;
static int g_tel_tramp_used;
static DWORD g_tel_hooks;                                    /* I76TEL_HOOK_* bits installed (frame.event_hooks) */
static DWORD g_snd_live;                                     /* I76_SOUND_EVENTS: tracked voices (frame.sound_voices) */

/* one ring slot, zeroed, stamped; the caller fills f / i */
static i76tel_event_t *tel_event_new(DWORD type) {
    DWORD seq = ++g_tel_ev_seq;
    i76tel_event_t *e = &g_tel_ring[seq % I76TEL_RING];
    memset(e, 0, sizeof *e);
    e->seq = seq; e->frame = g_frame; e->type = type;
    return e;
}

static void tel_event(DWORD type, float f0, float f1, float f2, float f3, int i0, int i1) {
    i76tel_event_t *e = tel_event_new(type);
    e->f[0] = f0; e->f[1] = f1; e->f[2] = f2; e->f[3] = f3;
    e->i[0] = i0; e->i[1] = i1;
}

/* the local player's object and entity, or 0 */
static BYTE *tel_player(BYTE **ent_out) {
    BYTE **rec = *(BYTE ***)(DWORD_PTR)NA(0x0054a264), *obj, *ent;
    obj = rec ? *rec : 0;
    if (!obj || !(*(DWORD *)(obj + 0x10) & 0x10)) return 0;    /* I76_OBJF_LOCAL_PLAYER, as object_IsPlayer tests */
    ent = *(BYTE **)(obj + 0x70);
    if (!ent) return 0;
    if (ent_out) *ent_out = ent;
    return obj;
}

/* a component's data block ([slot object]+0x70) when the slot holds an object of the expected class, else 0 */
static BYTE *tel_comp(BYTE *ent, int slot, int type) {
    BYTE *o = *(BYTE **)(ent + 0x3a8 + 4 * slot);
    if (!o || *(int *)(o + 0x6c) != type) return 0;
    return *(BYTE **)(o + 0x70);
}

/* armour + chassis + engine / suspension / brake / wheel hp: the quantity a hit on the player takes away */
static int tel_health_sum(BYTE *obj) {
    BYTE *ent = *(BYTE **)(obj + 0x70), *c;
    int s = 0, i;
    if (!ent) return 0;
    for (i = 0; i < 4; i++) s += *(int *)(ent + 0x138 + 4 * i) + *(int *)(ent + 0x148 + 4 * i);
    if ((c = tel_comp(ent, 7, 21)) != 0) s += *(int *)c;
    if ((c = tel_comp(ent, 8, 23)) != 0) s += *(int *)c;
    if ((c = tel_comp(ent, 9, 22)) != 0) s += *(int *)(c + 4);
    for (i = 0; i < 6; i++) if ((c = tel_comp(ent, i, 30)) != 0) s += *(int *)(c + 4);
    return s;
}

static void tel_header(i76tel_frame_t *t) {                   /* fixed globals only: safe whatever the player chain holds */
    memset(t, 0, sizeof *t);
    t->magic = I76TEL_MAGIC; t->version = I76TEL_VERSION; t->size = (uint16_t)sizeof *t;
    t->frame = *(DWORD *)(DWORD_PTR)NA(0x005a7e1c);                         /* simclock_frame_count */
    t->proxy_frame = g_frame;
    t->sim_time = *(float *)(DWORD_PTR)NA(0x005a7e74);                      /* simclock_time */
    t->sim_dt = *(float *)(DWORD_PTR)NA(0x004fe420);                        /* simclock_sim_dt */
    t->dt = *(float *)(DWORD_PTR)NA(0x004fe428);                            /* simclock_dt */
    t->step_count = -1;
    t->ffb_present = *(DWORD *)(DWORD_PTR)NA(0x0052bbd0);
    t->ffb_rpm = *(int *)(DWORD_PTR)NA(0x004f2334);
    t->ffb_engine_running = *(DWORD *)(DWORD_PTR)NA(0x004f2338);
    t->ffb_engine_starting = *(DWORD *)(DWORD_PTR)NA(0x004f233c);
    t->ffb_gear_changed = *(DWORD *)(DWORD_PTR)NA(0x004f2340);
    t->ffb_nitrous = *(DWORD *)(DWORD_PTR)NA(0x004f2344);
    memcpy(t->accel_body, (void *)(DWORD_PTR)NA(0x004f2418), 12);
    t->ffb_list_ordnance = *(DWORD *)(DWORD_PTR)NA(0x004f2478);
    t->ffb_list_concussion = *(DWORD *)(DWORD_PTR)NA(0x004f247c);
    t->ffb_list_collision = *(DWORD *)(DWORD_PTR)NA(0x004f2484);
    t->ffb_dt = *(float *)(DWORD_PTR)NA(0x004f2488);
    t->event_seq = g_tel_ev_seq;
    t->music_track = g_playingTrack;                         /* v3: the proxy's own state */
    t->event_hooks = g_tel_hooks;
    t->sound_voices = g_snd_live;
}

static void tel_player_fill(i76tel_frame_t *t) {
    BYTE *ent = 0, *obj = tel_player(&ent), *c;
    int i, n;
    if (!obj) return;
    t->player_present = 1;
    t->obj_addr = (uint32_t)(DWORD_PTR)obj; t->ent_addr = (uint32_t)(DWORD_PTR)ent;
    memcpy(t->pos, obj + 0x40, sizeof t->pos);
    memcpy(t->rot, obj + 0x18, sizeof t->rot);
    memcpy(t->velocity, ent + 0xbc, sizeof t->velocity);
    t->speed = *(float *)(ent + 0xac);
    t->pitch_rate = *(float *)(ent + 0xc8); t->yaw_rate = *(float *)(ent + 0xcc); t->roll_rate = *(float *)(ent + 0xd0);
    memcpy(t->accel, ent + 0xd4, sizeof t->accel);
    t->steer = *(float *)(ent + 0xe0); t->throttle = *(float *)(ent + 0xe4); t->gear_dir = *(float *)(ent + 0xe8);
    t->handbrake = *(int *)(ent + 0xf0); t->exhaust_brake = *(int *)(ent + 0xf4); t->gear_lever = *(int *)(ent + 0x104);
    if ((c = tel_comp(ent, 7, 21)) != 0) {                   /* I76_EngineData */
        t->engine_hp = *(int *)c; t->engine_hp_max = *(int *)(c + 4); t->gear = *(int *)(c + 8);
        t->drive_power = *(float *)(c + 0x10); t->rpm = *(float *)(c + 0x1c); t->speedo = *(float *)(c + 0x24);
    }
    if ((c = tel_comp(ent, 8, 23)) != 0) { t->susp_hp = *(int *)c; t->susp_hp_max = *(int *)(c + 4); }
    if ((c = tel_comp(ent, 9, 22)) != 0) { t->brake_hp = *(int *)(c + 4); t->brake_hp_max = *(int *)(c + 8); t->brake_effective = *(float *)(c + 0x10); }
    if ((c = tel_comp(ent, 7, 21)) != 0) t->engine_power = *(float *)(c + 0x14);          /* v2 fields */
    t->mass = *(float *)(ent + 0xa4); t->inv_mass = *(float *)(ent + 0xa8); t->drag = *(float *)(ent + 0x120);
    t->health_pct = ((float (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x0040b450))(obj);                        /* object_HealthFraction, pure read */
    t->flags = *(DWORD *)(ent + EF(0x454)); t->surface = *(DWORD *)(ent + EF(0x45c));
    memcpy(t->ground_normal, ent + EF(0x460), sizeof t->ground_normal);
    t->clearance = *(float *)(ent + EF(0x470)); t->state_timer = *(float *)(ent + EF(0x450));
    memcpy(t->armour, ent + 0x138, 16); memcpy(t->armour_max, ent + 0x158, 16);
    memcpy(t->chassis, ent + 0x148, 16); memcpy(t->chassis_max, ent + 0x168, 16);
    t->wheelbase = *(float *)(ent + 0x118); t->front_track = *(float *)(ent + 0x114);    /* v3 fields (physics.md, 0x438c64 / 0x438c01 / 0x438c72) */
    t->steer_gain = *(float *)(ent + 0x110); t->ground_g = *(float *)(ent + EF(0x46c));
    {                                                        /* the four grip reads of physics_ComputeSteerYawRate 0x43ce10: slots 0 1 4 5,
                                                                no class test there either (the accessors 0x467450..0x467480) */
        static const int gs[4] = { 0, 1, 4, 5 };
        float sum = 0.0f;
        for (i = 0; i < 4; i++) {
            BYTE *o = *(BYTE **)(ent + 0x3a8 + 4 * gs[i]), *wd = o ? *(BYTE **)(o + 0x70) : 0;
            if (wd) sum += *(float *)(wd + 0xc);
        }
        t->grip_sum = sum; t->grip_cap = 7.84f * sum;        /* 0x4bd1e0 */
    }
    for (i = 0; i < 6; i++) {
        i76tel_wheel_t *w = &t->wheel[i];
        if ((c = tel_comp(ent, i, 30)) == 0) continue;       /* I76_WheelData */
        w->present = 1; w->hp = *(int *)(c + 4); w->hp_max = *(int *)(c + 8); w->grip = *(float *)(c + 0xc);
        w->ground_speed = *(float *)(c + 0x20); w->susp_offset = *(float *)(c + 0x24);
        w->unloaded = *(int *)(c + 0x40); w->flat = *(int *)(c + 0x44); w->skid_active = *(int *)(c + 0x48);
    }
    /* selected weapon: the vehicle weapon record whose +0 is this object (0x5be4d8 + i x 0x2c8, count 0x5da78c), its
     * selected row +4, the row's instance at +0x58 + row x 0x58 + 0x50 (weapons.md) */
    t->weapon_row = t->weapon_def = -1;
    n = *(int *)(DWORD_PTR)NA(0x005da78c);
    if (n > 150) n = 150;                                     /* 0x5be4d8..0x5d88d8 holds 151 records at most */
    for (i = 0; i < n; i++) {
        BYTE *rec = (BYTE *)(DWORD_PTR)NA(0x005be4d8) + i * 0x2c8;
        int row;
        if (*(BYTE **)rec != obj) continue;
        row = *(int *)(rec + 4);
        t->weapon_row = row;
        if (row >= 0 && row < 7) {
            int idx = *(int *)(rec + 0x58 + row * 0x58 + 0x50);   /* slot+0x50 is an INDEX into the instance table
                                                                       (I76_WeaponSlot; live: 2/3/1 on the sandbox car) */
            BYTE *inst = (idx >= 0 && idx < *(int *)(DWORD_PTR)NA(0x005da750) && idx < 150) ? (BYTE *)(DWORD_PTR)NA(0x005aab08) + idx * 0x4c : 0, *root;
            if (inst) {
                t->weapon_def = *(int *)(inst + 0x30); t->weapon_ammo = *(int *)(inst + 0x20); t->weapon_hp = *(int *)(inst + 0xc);
                root = *(BYTE **)(inst + 8);
                if (root) memcpy(t->weapon_name, root, 8);
            }
        }
        break;
    }
    if (g_fixed_step > 0.0f) {                               /* substeps the fixed stepper ran in the frame just completed */
        int st = step_slot(ent + EF(0x444), 0);
        if (st >= 0 && g_step_acc[st].frame == g_frame) t->step_count = g_step_acc[st].n;
    } else {
        int cnt = (int)(t->sim_dt * 20.0f) + 1;               /* simclock_StepperBegin: floor(dt x 20) + 1, at most 20 */
        t->step_count = cnt > 20 ? 20 : cnt;
    }
}

static int tel_fill(i76tel_frame_t *t) {
    tel_header(t);
#ifdef _MSC_VER
    __try { tel_player_fill(t); }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        g_tel_faults++;
        tel_header(t);                                       /* a stale player chain: this frame reports no player */
        return 0;
    }
#else
    tel_player_fill(t);
#endif
    return 1;
}

static void tel_frame(void) {
    static BYTE pkt[sizeof(i76tel_frame_t) + I76TEL_RING * sizeof(i76tel_event_t)];
    i76tel_frame_t *t = (i76tel_frame_t *)pkt;
    DWORD n, first, k;
    tel_fill(t);
    t->seq = ++g_tel_pub_seq;
    n = g_tel_ev_seq - g_tel_ev_sent;                        /* events since the last datagram; the ring keeps the newest 64 */
    if (n > I76TEL_RING) n = I76TEL_RING;
    first = g_tel_ev_seq - n + 1;
    for (k = 0; k < n; k++)
        memcpy(pkt + sizeof *t + k * sizeof(i76tel_event_t), &g_tel_ring[(first + k) % I76TEL_RING], sizeof(i76tel_event_t));
    t->event_count = n;
    g_tel_ev_sent = g_tel_ev_seq;
    if (g_tel_sock != INVALID_SOCKET)
        p_tel_sendto(g_tel_sock, (const char *)pkt, (int)(sizeof *t + n * sizeof(i76tel_event_t)), 0, (const struct sockaddr *)&g_tel_dst, sizeof g_tel_dst);
    if (g_tel_shm) {
        volatile uint32_t *seq = &g_tel_shm->seq;
        uint32_t v = *seq;
        *seq = v + 1;                                        /* odd: being written */
#ifdef _MSC_VER
        _ReadWriteBarrier();
#else
        __sync_synchronize();
#endif
        memcpy(&g_tel_shm->frame, t, sizeof *t);
        g_tel_shm->frame.event_count = 0;                    /* the ring is beside it, not appended */
        memcpy(g_tel_shm->ring, g_tel_ring, sizeof g_tel_ring);
#ifdef _MSC_VER
        _ReadWriteBarrier();
#else
        __sync_synchronize();
#endif
        *seq = v + 2;                                        /* even: consistent */
    }
}

/* --- event hooks ---------------------------------------------------------- */
static void __cdecl tel_fire_wrap(BYTE *inst, BYTE *wdef, int count, float dt_left) {
    BYTE **vrec, *veh;
    ((void (__cdecl *)(BYTE *, BYTE *, int, float))(DWORD_PTR)NA(0x004a6e90))(inst, wdef, count, dt_left);   /* weapon_FireShot */
    if (!inst) return;
    if (g_cbt_on) cbt_shot(inst);
    vrec = *(BYTE ***)(inst + 0x18);                         /* I76_WeaponInstance.vrec -> +0 vehicle object */
    veh = vrec ? *vrec : 0;
    if (veh && ((int (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x00458bf0))(veh))   /* object_IsPlayer */
        tel_event(I76TEL_EV_SHOT, (float)*(int *)(inst + 0x1c), (float)*(int *)(inst + 0x20), (float)*(DWORD *)(inst + 0x10), dt_left,
                  *(int *)(inst + 0x30), count);
}

static float tel_player_dist(float x, float y, float z) {   /* distance from the player, -1 without one; guarded like the snapshot */
    float d = -1.0f;
#ifdef _MSC_VER
    __try {
#endif
        BYTE *obj = tel_player(0);
        if (obj) {
            double *p = (double *)(obj + 0x40);
            double dx = x - p[0], dy = y - p[1], dz = z - p[2];
            d = (float)sqrt(dx * dx + dy * dy + dz * dz);
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_tel_faults++; }
#endif
    return d;
}

static DWORD * __cdecl tel_expl_hook(DWORD name_lo, DWORD name_hi, DWORD p3, float x, float y, float z, DWORD owner) {
    DWORD lo = name_lo, hi = name_hi;                        /* the callee upper-cases its own copy of the name */
    DWORD *r = ((DWORD *(__cdecl *)(DWORD, DWORD, DWORD, float, float, float, DWORD))g_tel_expl_tramp)(name_lo, name_hi, p3, x, y, z, owner);
    tel_event(I76TEL_EV_EXPLOSION, x, y, z, tel_player_dist(x, y, z), (int)lo, (int)hi);
    return r;
}

static int __cdecl tel_coll_hook(BYTE *target, BYTE *source, float *normal, float *impact, float *dir) {
    int is_player = target && ((int (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x00458bf0))(target) != 0;
    int before = is_player ? tel_health_sum(target) : 0, r;
    float v[3] = { 0.0f, 0.0f, 0.0f };
    if (impact) { v[0] = impact[0]; v[1] = impact[1]; v[2] = impact[2]; }
    r = ((int (__cdecl *)(BYTE *, BYTE *, float *, float *, float *))g_tel_coll_tramp)(target, source, normal, impact, dir);
    if (g_cbt_on) cbt_coll(target, source);
    tel_event(I76TEL_EV_IMPACT, v[0], v[1], v[2], is_player ? (float)(before - tel_health_sum(target)) : 0.0f,
              is_player, source ? *(int *)(source + 0x6c) : 0);
    return r;                                                /* the exe's bool result, in al; eax passes through untouched */
}

/* Entry detour of the cam_set_hook kind: the first n bytes of the function (position-independent, verified first) are
 * copied into a trampoline that jumps back to entry+n, and the entry becomes `jmp hook` padded with nops. Returns the
 * trampoline (what the hook calls to run the original) or 0 with nothing changed. */
static BYTE *tel_detour(DWORD entry, const BYTE *expect, int n, void *hook, const char *what) {
    BYTE patch[16], *tr;
    LONG rel;
    DWORD ea = NA(entry);                                    /* Nitro: the mapped entry; patch_bytes checks its signature */
    if (!g_tel_tramp) g_tel_tramp = (BYTE *)VirtualAlloc(NULL, 128, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_tel_tramp || g_tel_tramp_used + n + 5 > 128 || n > 11 || !ea || (g_exe != EXE_NITRO && memcmp((void *)entry, expect, n) != 0)) {
        mlog("  patch: %s at 0x%08lX has UNEXPECTED bytes (or no trampoline room) - not patching", what, (unsigned long)entry);
        return 0;
    }
    tr = g_tel_tramp + g_tel_tramp_used;
    memcpy(tr, (const void *)(DWORD_PTR)ea, n);              /* = expect on Gold (checked above); Nitro's own bytes there */
    tr[n] = 0xE9; rel = (LONG)((ea + n) - ((DWORD_PTR)tr + n + 5)); memcpy(tr + n + 1, &rel, 4);
    memset(patch, 0x90, sizeof patch);
    patch[0] = 0xE9; rel = (LONG)((DWORD_PTR)hook - (entry + 5)); memcpy(patch + 1, &rel, 4);
    if (!patch_bytes(entry, expect, patch, n, what)) return 0;
    g_tel_tramp_used += n + 5;
    return tr;
}

/* --- SOUND / DAMAGE EVENTS (i76tel v3; opt-in on top of I76_TELEMETRY) ---------------------------------------
 * I76_SOUND_EVENTS=1: one SOUND_START per voice that really starts, one SOUND_STOP when it stops, WEAPON_UI clicks.
 * The request wrappers (0x421b40 and its 22+23+9+14+35+4 callers) only queue; the DirectSound Play happens in
 * sound_StartVoice 0x4220c0(voice, k), called by the per-frame update 0x421400 (0x4214e0) and the un-park path
 * (0x422422). It returns 1 when it played (it also returns 1 with the sound system off, [0x4ed7e8] == 0, which is
 * tested first). A voice stops on four paths, all tapped, and a voice is reported stopped once, only if it was
 * reported started (the table below; extra stops of an unknown voice are dropped):
 *   0x425ef0(voice)  release: explicit stops 0x421e70 (horn, engine loop, CB, siren: 19 callers), finished one-shots
 *                    and dead-object voices in 0x421400, voice stealing; entry detoured (6 bytes sub esp,0x214)
 *   0x422d20(voice, reason)  stop / park, reason 0x20 / 0x40 / 0x80 / 0x100 by caller; entry detoured (5 bytes)
 *   call 0x422540(voice, 0) at 0x42150b / 0x4215a2  the per-frame update keeps an ended voice (failed restart /
 *                    buffer no longer playing, including a sustained loop nobody refreshed: skid, tyre, damage)
 * The voice record (sound.md "Instance"): name +4, flags +0x14 (4 voice level, 0x200 detached 100 m one-shot),
 * frequency +0x18, volume % +0x1c, pan +0x20, priority +0x34, mode +0x3c, object +0x5c. The object is read BEFORE
 * the start because 0x4217e0 drops a detached one-shot's object after its one positioning; the position is the
 * object's root (+0x68 chain, as 0x458c90 walks it) world position +0x40; is-player is the root's flag 0x10.
 * WEAPON_UI: the cycle / link / unlink handlers each play their click through call 0x4250f0 at 0x4a5dff / 0x4a6333 /
 * 0x4a6021, next to the FFB one-shot stores 0x4f234c / 0x4f2350 / 0x4f2354; those three call sites are repointed.
 *
 * I76_DAMAGE_EVENTS=1: entity_DamageAndKill 0x463a80(object, record, hit point in the target's frame), reached
 * through the class damage-handler slot 0x4f77a4 (and the one direct call 0x4652f9, record 0: no event). Entry
 * detoured (6 bytes sub esp,0xc0). The side / zone are recomputed here with the exe's own rule and constants
 * (damage.md C8: top when u.y > 0.8 (0x4be1c8); else side and zone from the renormalised (hx, hz) against
 * +-0.707 (0x4be1cc / 0x4be1d0) and 0) - the exe keeps them in locals. Its rsqrt 0x495000 is a table approximation,
 * so a hit within rounding of a boundary may classify differently. The amount is the record's incoming total and
 * the hp the target lost in the call (armour + chassis + components, before minus after). Events only where the exe
 * does damage: a record, a live object (+0x10 bit 0x20 clear) and entity (+0x454 bit 0x20 clear).
 * Static-verified only (tools/telemetry/verify_v3_sites.py: every site's bytes in the pristine and the twin exe). */
#define SND_TRACK 128
typedef struct { BYTE *voice, *obj; DWORD name[2]; float t0; int player; } snd_track_t;
static snd_track_t g_snd[SND_TRACK];
static DWORD g_snd_overflow, g_snd_starts, g_snd_stops, g_dmg_events;
static BYTE *g_snd_start_tramp, *g_snd_stop_tramp, *g_snd_rel_tramp, *g_dmg_tramp;

static BYTE *snd_root(BYTE *o) {                             /* 0x458c90: follow +0x68 to the topmost object */
    int k;
    for (k = 0; o && *(BYTE **)(o + 0x68) && k < 16; k++) o = *(BYTE **)(o + 0x68);
    return o;
}

static void snd_started(BYTE *voice, BYTE *obj, const double *pos, int has_pos, int player) {
    i76tel_event_t *e;
    snd_track_t *t = 0, *fr = 0;
    DWORD mode = 0, prio = 0, fl = 0;
    int j;
    for (j = 0; j < SND_TRACK; j++) {
        if (g_snd[j].voice == voice) { t = &g_snd[j]; break; }   /* restarted without a stop we saw: one entry */
        if (!fr && !g_snd[j].voice) fr = &g_snd[j];
    }
    if (!t) { t = fr; if (t) g_snd_live++; else g_snd_overflow++; }
    e = tel_event_new(I76TEL_EV_SOUND_START);
    g_snd_starts++;
#ifdef _MSC_VER
    __try {
#endif
        e->f[0] = *(float *)(voice + 0x18); e->f[1] = *(float *)(voice + 0x1c); e->f[5] = *(float *)(voice + 0x20);
        memcpy(e->i, voice + 4, 8);
        mode = *(DWORD *)(voice + 0x3c); prio = *(DWORD *)(voice + 0x34); fl = *(DWORD *)(voice + 0x14);
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_tel_faults++; }
#endif
    if (has_pos) { e->f[2] = (float)pos[0]; e->f[3] = (float)pos[1]; e->f[4] = (float)pos[2]; }
    if (prio > 0xffff) prio = 0xffff;
    e->i[2] = (int)((mode & I76TEL_SND_MODE) | (player ? I76TEL_SND_PLAYER : 0) | (has_pos ? I76TEL_SND_HAS_POS : 0) |
                    ((fl & 0x200) ? I76TEL_SND_DETACHED : 0) | ((fl & 4) ? I76TEL_SND_VOICE_LVL : 0) | (prio << I76TEL_SND_PRIO_SHIFT));
    e->i[3] = (int)(DWORD_PTR)obj; e->i[4] = (int)(DWORD_PTR)voice;
    if (t) {
        t->voice = voice; t->obj = obj; t->player = player; t->t0 = *(float *)0x005a7e74;     /* simclock_time */
        t->name[0] = (DWORD)e->i[0]; t->name[1] = (DWORD)e->i[1];
    }
}

static void snd_ended(BYTE *voice, int reason) {
    i76tel_event_t *e;
    snd_track_t *t = 0;
    int j;
    if (!voice) return;
    for (j = 0; j < SND_TRACK; j++) if (g_snd[j].voice == voice) { t = &g_snd[j]; break; }
    if (!t) return;                                          /* never reported started (culled, failed, or before the hook) */
    e = tel_event_new(I76TEL_EV_SOUND_STOP);
    g_snd_stops++;
    e->f[0] = *(float *)(DWORD_PTR)NA(0x005a7e74) - t->t0;
    e->i[0] = (int)t->name[0]; e->i[1] = (int)t->name[1];
    e->i[2] = reason | (t->player ? I76TEL_STOP_PLAYER : 0);
    e->i[3] = (int)(DWORD_PTR)t->obj; e->i[4] = (int)(DWORD_PTR)voice;
    t->voice = 0;
    if (g_snd_live) g_snd_live--;
}

static int __cdecl snd_start_hook(BYTE *voice, int k) {
    BYTE *obj = 0, *root;
    double pos[3] = { 0.0, 0.0, 0.0 };
    int has_pos = 0, player = 0, on = *(DWORD *)(DWORD_PTR)NA(0x004ed7e8) != 0, r;   /* sound system up (StartVoice returns 1 without it) */
#ifdef _MSC_VER
    __try {
#endif
        if (voice && on && (obj = *(BYTE **)(voice + 0x5c)) != 0 && (root = snd_root(obj)) != 0) {
            memcpy(pos, root + 0x40, sizeof pos); has_pos = 1;
            player = (*(DWORD *)(root + 0x10) & 0x10) != 0;
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_tel_faults++; has_pos = player = 0; }
#endif
    r = ((int (__cdecl *)(BYTE *, int))g_snd_start_tramp)(voice, k);
    if (r && voice && on) snd_started(voice, obj, pos, has_pos, player);
    return r;
}

static int __cdecl snd_stop_hook(BYTE *voice, int reason) {   /* 0x422d20 */
    snd_ended(voice, reason & 0xffff);
    return ((int (__cdecl *)(BYTE *, int))g_snd_stop_tramp)(voice, reason);
}

static int __cdecl snd_rel_hook(BYTE *voice) {               /* 0x425ef0 */
    snd_ended(voice, I76TEL_STOP_RELEASED);
    return ((int (__cdecl *)(BYTE *))g_snd_rel_tramp)(voice);
}

static int __cdecl snd_end_wrap(BYTE *voice, int to_active) { /* call 0x422540 at 0x42150b / 0x4215a2 */
    snd_ended(voice, I76TEL_STOP_ENDED);
    return ((int (__cdecl *)(BYTE *, int))(DWORD_PTR)NA(0x00422540))(voice, to_active);
}

static int __cdecl wui_click(int which, const char *name, BYTE *obj, int flag) {
    i76tel_event_t *e = tel_event_new(I76TEL_EV_WEAPON_UI);
    e->i[0] = which;
    return ((int (__cdecl *)(const char *, BYTE *, int))(DWORD_PTR)NA(0x004250f0))(name, obj, flag);
}
static int __cdecl wui_cycle_wrap(const char *n, BYTE *o, int f)  { return wui_click(0, n, o, f); }
static int __cdecl wui_link_wrap(const char *n, BYTE *o, int f)   { return wui_click(1, n, o, f); }
static int __cdecl wui_unlink_wrap(const char *n, BYTE *o, int f) { return wui_click(2, n, o, f); }

/* side / zone of a hit point in the target's frame, the 0x463b4a..0x463d1e rule; -1 / -1 for a zero vector */
static void dmg_classify(const float *p, int *side, int *zone) {
    double l2 = (double)p[0] * p[0] + (double)p[1] * p[1] + (double)p[2] * p[2], h2, r, hx, hz;
    *side = *zone = -1;
    if (!(l2 > 1e-12)) return;
    r = 1.0 / sqrt(l2);
    if ((float)(p[1] * r) > 0.8f) { *side = 4; *zone = 6; return; }
    hx = p[0] * r; hz = p[2] * r;
    h2 = hx * hx + hz * hz;
    if (!(h2 > 1e-12)) return;
    r = 1.0 / sqrt(h2);
    hx = (float)(hx * r); hz = (float)(hz * r);
    if (hx > 0.707f) *side = 2; else if (hx < -0.707f) *side = 1; else if (hz > 0.707f) *side = 0; else *side = 3;
    if (hz > 0.707f) *zone = 0;
    else if (hz < -0.707f) *zone = 5;
    else if (hz > 0.0) *zone = hx > 0.0 ? 3 : 1;
    else *zone = hx > 0.0 ? 4 : 2;
}

static int __cdecl dmg_hook(BYTE *obj, BYTE *rec, float *pt) {
    int ok = 0, before = 0, after = 0, side = -1, zone = -1, bits = 0, mask = 0, scls = 0, k, r;
    float amt = 0.0f, p[3] = { 0.0f, 0.0f, 0.0f };
    BYTE *ent = 0, *cshooter = 0;
#ifdef _MSC_VER
    __try {
#endif
        ent = obj ? *(BYTE **)(obj + 0x70) : 0;
        if (rec && pt && ent && !(*(BYTE *)(obj + 0x10) & 0x20) && !(*(DWORD *)(ent + EF(0x454)) & 0x20)) {   /* the exe's own guards */
            WORD m = *(WORD *)(rec + 4), fl = *(WORD *)(rec + 6);
            BYTE *shooter = *(BYTE **)rec;
            cshooter = shooter;
            for (k = 0; k < 4; k++) if (m & (1 << k)) amt += (float)*(int *)(rec + 8 + 4 * k);
            p[0] = pt[0]; p[1] = pt[1]; p[2] = pt[2];
            dmg_classify(p, &side, &zone);
            if (*(DWORD *)(obj + 0x10) & 0x10) bits |= I76TEL_DMG_PLAYER;          /* object_IsPlayer's test */
            if (shooter) { scls = *(int *)(shooter + 0x6c); if (*(DWORD *)(shooter + 0x10) & 0x10) bits |= I76TEL_DMG_BY_PLAYER; }
            mask = (int)(m | ((DWORD)fl << 16));
            before = tel_health_sum(obj);
            ok = 1;
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_tel_faults++; ok = 0; }
#endif
    r = ((int (__cdecl *)(BYTE *, BYTE *, float *))g_dmg_tramp)(obj, rec, pt);
    if (ok) {
        i76tel_event_t *e;
#ifdef _MSC_VER
        __try {
#endif
            after = tel_health_sum(obj);
            if (*(DWORD *)(ent + EF(0x454)) & 0x20) bits |= I76TEL_DMG_KILLED;
#ifdef _MSC_VER
        } __except (EXCEPTION_EXECUTE_HANDLER) { g_tel_faults++; after = before; }
#endif
        e = tel_event_new(I76TEL_EV_DAMAGE_SIDE);
        g_dmg_events++;
        e->f[0] = amt; e->f[1] = (float)(before - after); e->f[2] = p[0]; e->f[3] = p[1]; e->f[4] = p[2];
        e->i[0] = side; e->i[1] = zone; e->i[2] = bits; e->i[3] = mask; e->i[4] = scls;
        if (g_cbt_on) cbt_damage(obj, cshooter, amt, before - after, (bits & I76TEL_DMG_KILLED) != 0);
    }
    return r;
}

/* repoint one `call rel32` site from `target` to `wrap` (verify-first) */
static int tel_repoint_call(DWORD site, DWORD target, void *wrap, const char *what) {
    BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
    LONG rel = (LONG)(target - (site + 5));
    memcpy(o + 1, &rel, 4);
    rel = (LONG)((DWORD_PTR)wrap - (site + 5)); memcpy(w + 1, &rel, 4);
    return patch_bytes(site, o, w, 5, what);
}

static int env_is_1(const char *name) {
    char v[8];
    return env_str(name, v, sizeof(v)) && v[0] == '1' && v[1] == 0;
}

static void apply_sound_events(void) {
    static const BYTE start_old[6] = { 0xA1, 0xE8, 0xD7, 0x4E, 0x00, 0x53 };   /* 0x4220c0: mov eax,[0x4ed7e8]; push ebx */
    static const BYTE stop_old[5]  = { 0x56, 0x8B, 0x74, 0x24, 0x08 };         /* 0x422d20: push esi; mov esi,[esp+8] */
    static const BYTE rel_old[6]   = { 0x81, 0xEC, 0x14, 0x02, 0x00, 0x00 };   /* 0x425ef0: sub esp,0x214 */
    int stops = 0, ui = 0;
    if (!env_is_1("I76_SOUND_EVENTS")) return;
    /* stop paths first: a start reported with no stop tap would leave the voice in the table forever */
    g_snd_rel_tramp = tel_detour(0x00425ef0, rel_old, 6, (void *)snd_rel_hook, "sound voice release entry (sound events)");
    g_snd_stop_tramp = tel_detour(0x00422d20, stop_old, 5, (void *)snd_stop_hook, "sound_StopVoice entry (sound events)");
    stops = (g_snd_rel_tramp != 0) + (g_snd_stop_tramp != 0);
    stops += tel_repoint_call(0x0042150b, 0x00422540, (void *)snd_end_wrap, "sound update: ended voice kept (failed restart) (sound events)");
    stops += tel_repoint_call(0x004215a2, 0x00422540, (void *)snd_end_wrap, "sound update: ended voice kept (sound events)");
    if (stops == 4) {
        g_snd_start_tramp = tel_detour(0x004220c0, start_old, 6, (void *)snd_start_hook, "sound_StartVoice entry (sound events)");
        if (g_snd_start_tramp) g_tel_hooks |= I76TEL_HOOK_SOUND_START | I76TEL_HOOK_SOUND_STOP;
    }
    ui += tel_repoint_call(0x004a5dff, 0x004250f0, (void *)wui_cycle_wrap, "weapon cycle click call (sound events)");
    ui += tel_repoint_call(0x004a6333, 0x004250f0, (void *)wui_link_wrap, "weapon link click call (sound events)");
    ui += tel_repoint_call(0x004a6021, 0x004250f0, (void *)wui_unlink_wrap, "weapon unlink click call (sound events)");
    if (ui) g_tel_hooks |= I76TEL_HOOK_WEAPON_UI;
    mlog("  sound-events: %s - stop taps %d/4 (release 0x425ef0, StopVoice 0x422d20, update 0x42150b / 0x4215a2), start tap %s (StartVoice 0x4220c0), weapon-UI clicks %d/3, event %u B",
         (g_tel_hooks & I76TEL_HOOK_SOUND_START) ? "on" : "NOT on", stops, g_snd_start_tramp ? "on" : "NOT installed (needs all 4 stop taps)",
         ui, (unsigned)sizeof(i76tel_event_t));
}

static void apply_damage_events(void) {
    static const BYTE dmg_old[6] = { 0x81, 0xEC, 0xC0, 0x00, 0x00, 0x00 };     /* 0x463a80: sub esp,0xc0 */
    if (!env_is_1("I76_DAMAGE_EVENTS")) return;
    g_dmg_tramp = tel_detour(0x00463a80, dmg_old, 6, (void *)dmg_hook, "entity_DamageAndKill entry (damage events)");
    if (g_dmg_tramp) g_tel_hooks |= I76TEL_HOOK_DAMAGE_SIDE;
    mlog("  damage-events: %s - entity_DamageAndKill 0x463a80 entry %s",
         g_dmg_tramp ? "on" : "NOT on", g_dmg_tramp ? "detoured" : "NOT detoured");
}

static void apply_telemetry(void) {
    static const BYTE expl_old[8] = { 0x8B, 0x44, 0x24, 0x04, 0x8B, 0x4C, 0x24, 0x08 };   /* 0x49ead0: mov eax,[esp+4]; mov ecx,[esp+8] */
    static const BYTE coll_old[6] = { 0x81, 0xEC, 0xD0, 0x00, 0x00, 0x00 };               /* 0x4a7c80: sub esp, 0xd0 */
    static const DWORD fire_sites[2] = { 0x004a6b16, 0x004a6d43 };                          /* call 0x4a6e90 in weapon_UpdateInstanceFiring */
    char v[16]; int port, hooks = 0, i;
    DWORD n = env_str("I76_TELEMETRY", v, sizeof(v));
    if (n == 0) {
        if (env_is_1("I76_SOUND_EVENTS") || env_is_1("I76_DAMAGE_EVENTS"))
            mlog("  telemetry: off - I76_SOUND_EVENTS / I76_DAMAGE_EVENTS need I76_TELEMETRY, nothing patched");
        return;
    }
    port = atoi(v);
    if (port == 1) port = I76TEL_PORT;
    if (port < 1 || port > 65535) { mlog("  telemetry: '%s' is not a port - off", v); return; }
    {   /* Nitro: every address the snapshot reads must be mapped (nitro.c); Gold: always true */
        static const DWORD need[] = { 0x0054a264, 0x005a7e1c, 0x005a7e74, 0x004fe420, 0x004fe428, 0x0052bbd0, 0x004f2334, 0x004f2338,
            0x004f233c, 0x004f2340, 0x004f2344, 0x004f2418, 0x004f2478, 0x004f247c, 0x004f2484, 0x004f2488, 0x0040b450, 0x005da78c,
            0x005be4d8, 0x005da750, 0x005aab08, 0x004a6e90, 0x00458bf0 };
        if (!nitro_need("telemetry", need, (int)(sizeof need / sizeof need[0]))) { mlog("  telemetry: off (site map)"); return; }
    }
    install_frame_hook();
    if (!g_frame_hook) { mlog("  telemetry: frame hook missing - off"); return; }

    /* UDP, through ws2_32 loaded by hand: winsock is not linked by either toolchain's build line, and a LoadLibrary
     * here keeps the dependency inside the feature that uses it (nothing is loaded when the variable is unset). The
     * winsock 1 types from windows.h match ws2_32's exports for these five calls. */
    g_tel_ws = LoadLibraryA("ws2_32.dll");
    if (g_tel_ws) {
        int (__stdcall *p_startup)(WORD, WSADATA *) = (int (__stdcall *)(WORD, WSADATA *))GetProcAddress(g_tel_ws, "WSAStartup");
        SOCKET (__stdcall *p_socket)(int, int, int) = (SOCKET (__stdcall *)(int, int, int))GetProcAddress(g_tel_ws, "socket");
        WSADATA wsa;
        p_tel_sendto = (int (__stdcall *)(SOCKET, const char *, int, int, const struct sockaddr *, int))GetProcAddress(g_tel_ws, "sendto");
        if (p_startup && p_socket && p_tel_sendto && p_startup(0x0202, &wsa) == 0) {
            g_tel_sock = p_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            g_tel_dst.sin_family = AF_INET;
            g_tel_dst.sin_port = (u_short)(((port & 0xff) << 8) | (port >> 8));      /* htons by hand: no need for the import */
            g_tel_dst.sin_addr.s_addr = 0x0100007f;                                  /* 127.0.0.1 */
        }
    }
    /* shared memory: created here, so a reader that starts later finds it; one that started earlier (and created it
     * empty) is handed the same section by name */
    char tel_nm[96];
    g_tel_map = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(i76tel_shm_t), shm_name(tel_nm, sizeof tel_nm, I76TEL_SHM_NAME));
    if (g_tel_map) {
        g_tel_shm = (i76tel_shm_t *)MapViewOfFile(g_tel_map, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(i76tel_shm_t));
        if (g_tel_shm) { memset(g_tel_shm, 0, sizeof *g_tel_shm); g_tel_shm->size = sizeof(i76tel_shm_t); }
        else mlog("  telemetry: shm view refused - a reader built on an older i76tel.h created %s smaller than %u B; start it after the game or update it (UDP is unaffected)",
                  tel_nm, (unsigned)sizeof(i76tel_shm_t));
    }
    /* events */
    for (i = 0; i < 2; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(0x004a6e90 - (fire_sites[i] + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)tel_fire_wrap - (fire_sites[i] + 5)); memcpy(w + 1, &rel, 4);
        hooks += patch_bytes(fire_sites[i], o, w, 5, "weapon_FireShot call (telemetry)");
    }
    if (hooks) g_tel_hooks |= I76TEL_HOOK_SHOT;
    g_tel_expl_tramp = tel_detour(0x0049ead0, expl_old, 8, (void *)tel_expl_hook, "entity_SpawnExplosion entry (telemetry)");
    g_tel_coll_tramp = tel_detour(0x004a7c80, coll_old, 6, (void *)tel_coll_hook, "physics_ApplyCollisionDamage entry (telemetry)");
    hooks += (g_tel_expl_tramp != 0) + (g_tel_coll_tramp != 0);
    if (g_tel_expl_tramp) g_tel_hooks |= I76TEL_HOOK_EXPLOSION;
    if (g_tel_coll_tramp) g_tel_hooks |= I76TEL_HOOK_IMPACT;
    g_tel_on = 1;
    mlog("  telemetry: on - udp 127.0.0.1:%d %s, shm %s %s, %d/4 event hooks (FireShot call sites x2, SpawnExplosion entry, ApplyCollisionDamage entry), frame %u B + events %u B, ring %d",
         port, g_tel_sock != INVALID_SOCKET ? "open" : "FAILED", tel_nm, g_tel_shm ? "mapped" : "FAILED",
         hooks, (unsigned)sizeof(i76tel_frame_t), (unsigned)sizeof(i76tel_event_t), I76TEL_RING);
    apply_sound_events();     /* opt-in: I76_SOUND_EVENTS=1 (i76tel v3) */
    apply_damage_events();    /* opt-in: I76_DAMAGE_EVENTS=1 (i76tel v3) */
}

/* ===========================================================================
 * COMBAT INSTRUMENT  (I76_COMBAT_LOG=<file>; needs I76_TELEMETRY + I76_DAMAGE_EVENTS; off by default; lab tool)
 * ===========================================================================
 * Lab doc AI-COMBAT-PARITY-2026-10-13.md. Counts only - nothing the game computes is changed: per car on the 8 team
 * lists (0x507da0, counts 0x51f5d0; slot -> object, entity obj+0x70, AI block entity+0x108) it samples once per
 * rendered frame, weighted by the simclock time that frame advanced: distance to the player (ground plane), speed,
 * the top of the behaviour stack (ai+0xa874[ai+0xa93c], ids 0..33 of table 0x4c3e00: time in each and entries), the
 * target (ai+0xa9b4 == player), steer sign reversals (+0xe0, |steer| > 0.2), handbrake (+0xf0) entries, alive/dead.
 * Events from the telemetry wrappers: every weapon_FireShot by shooter and weapon definition (instance +0x30), every
 * entity_DamageAndKill with its shooter (requested amount = the record's damage sum, which the god flag does not
 * zero; health lost; kill), every physics_ApplyCollisionDamage between an AI car and the player (raw calls and
 * contacts = calls more than 0.5 s apart). The decision gates are counted by the same pass-through wrappers the
 * frame-rate fixes use (ai_fire_wrap, ai_dodge_wrap, ai_skid_rand, ai_horn_rand), installed here when no switch has
 * installed them, so every condition (stock included) reports the same counters. The file is rewritten about once a
 * second of real time, so a run that is killed still leaves its last snapshot. */
#define CBT_CARS 64
#define CBT_BEH 35                                           /* 0..33 + 34 = out of range */
#define CBT_WPN 8
typedef struct {
    BYTE *obj; int g, i, player, alive; char name[9];
    double t_seen, t_dead, t_tgt, dsum, dmin, dbin[5], vsum;
    double bt[CBT_BEH]; DWORD be[CBT_BEH]; int beh;
    float steer_last; DWORD steer_rev, hb_on; int hb;
    float pend_steer; int pend_hb, pend_ok; float c_steer_last; DWORD c_rev, c_hb_on, c_steps; int c_hb;   /* commands a physics step consumed */
    int wdef[CBT_WPN]; DWORD wshots[CBT_WPN]; DWORD shots_other;
    double dmg_req_player, dmg_req_taken, dmg_req_by_player, lost_taken; DWORD hits_player, hits_taken, hits_by_player;
    DWORD coll_calls, coll_contacts; double coll_last;
} cbt_car_t;
static cbt_car_t g_cbt[CBT_CARS];
static char g_cbt_path[MAX_PATH];
static float g_cbt_last_t; static int g_cbt_have_t;
static DWORD g_cbt_prev_frame, g_cbt_prev_steps;
static double g_cbt_t; static DWORD g_cbt_frames, g_cbt_flush_tick;
static BYTE *g_cbt_player;
static int g_cbt_stepped;
static double g_cbt_player_dmg_req; static DWORD g_cbt_player_hits;
static cbt_car_t *cbt_find(BYTE *obj, int add) {
    int k, fr = -1;
    if (!obj) return 0;
    for (k = 0; k < CBT_CARS; k++) { if (g_cbt[k].obj == obj) return &g_cbt[k]; if (fr < 0 && !g_cbt[k].obj) fr = k; }
    if (!add || fr < 0) return 0;
    memset(&g_cbt[fr], 0, sizeof g_cbt[fr]);
    g_cbt[fr].obj = obj; g_cbt[fr].dmin = 1e9; g_cbt[fr].beh = -1; g_cbt[fr].t_dead = -1.0; g_cbt[fr].t_seen = -1.0;
    lstrcpynA(g_cbt[fr].name, (const char *)obj, 9);
    return &g_cbt[fr];
}
static void cbt_shot(BYTE *inst) {
    BYTE **vrec = *(BYTE ***)(inst + 0x18), *veh = vrec ? *vrec : 0;
    cbt_car_t *c = cbt_find(veh, 0);
    int d = *(int *)(inst + 0x30), k;
    if (!c) return;
    for (k = 0; k < CBT_WPN; k++) {
        if (c->wshots[k] && c->wdef[k] == d) { c->wshots[k]++; return; }
        if (!c->wshots[k]) { c->wdef[k] = d; c->wshots[k] = 1; return; }
    }
    c->shots_other++;
}
static void cbt_coll(BYTE *target, BYTE *source) {
    cbt_car_t *c = 0;
    if (!g_cbt_player || !target || !source) return;
    if (target == g_cbt_player) c = cbt_find(source, 0);
    else if (source == g_cbt_player) c = cbt_find(target, 0);
    if (!c || c->player) return;
    c->coll_calls++;
    if (g_cbt_t - c->coll_last > 0.5) c->coll_contacts++;
    c->coll_last = g_cbt_t;
}
static void cbt_damage(BYTE *obj, BYTE *shooter, float amt, int lost, int killed) {
    cbt_car_t *t = cbt_find(obj, 0), *s = shooter ? cbt_find(shooter, 0) : 0;
    int to_player = obj && (*(DWORD *)(obj + 0x10) & 0x10);
    int by_player = shooter && (*(DWORD *)(shooter + 0x10) & 0x10);
    if (to_player) { g_cbt_player_dmg_req += amt; g_cbt_player_hits++; }
    if (s && to_player && s != t) { s->dmg_req_player += amt; s->hits_player++; }
    if (t && !t->player) {
        t->dmg_req_taken += amt; t->hits_taken++; t->lost_taken += lost;
        if (by_player) { t->dmg_req_by_player += amt; t->hits_by_player++; }
        if (killed && t->t_dead < 0.0) t->t_dead = g_cbt_t;
    }
}
static void cbt_flush(void) {
    char tmp[MAX_PATH + 8], line[2400];
    HANDLE h; DWORD w; int k, j, n;
    wsprintfA(tmp, "%s.tmp", g_cbt_path);
    h = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    n = sprintf(line, "T sim=%.3f frames=%lu aifire_calls=%lu aifire_yes=%lu dodge_calls=%lu dodge_yes=%lu skid_rolls=%lu horn_rolls=%lu player_hits=%lu player_dmg_req=%.0f stepframes=%lu skidhb_enter=%lu skidhb_deferred=%lu turret_rolls=%lu ease_calls=%lu search_steps=%lu search_skips=%lu\n",
                g_cbt_t, (unsigned long)g_cbt_frames, (unsigned long)g_idbg_aifire_calls, (unsigned long)g_idbg_aifire_yes,
                (unsigned long)g_idbg_dodge_calls, (unsigned long)g_idbg_dodge_yes, (unsigned long)g_idbg_skid_rolls,
                (unsigned long)g_idbg_horn_rolls, (unsigned long)g_cbt_player_hits, g_cbt_player_dmg_req,
                (unsigned long)g_stepframes, (unsigned long)g_skid_hb_enter, (unsigned long)g_skid_hb_deferred, (unsigned long)g_idbg_turret_rolls,
                (unsigned long)g_ease_calls, (unsigned long)g_search_steps, (unsigned long)g_search_skips);
    WriteFile(h, line, n, &w, NULL);
    for (k = 0; k < CBT_CARS; k++) {
        cbt_car_t *c = &g_cbt[k];
        if (!c->obj) continue;
        n = sprintf(line, "C g=%d i=%d name=%s player=%d alive=%d t_seen=%.2f t_dead=%.2f t_tgt=%.2f dsum=%.1f dmin=%.1f d25=%.2f d50=%.2f d100=%.2f d200=%.2f dfar=%.2f vsum=%.1f steer_rev=%lu hb_on=%lu shots_other=%lu dmg_req_player=%.0f hits_player=%lu dmg_req_taken=%.0f hits_taken=%lu lost_taken=%.0f dmg_req_by_player=%.0f hits_by_player=%lu coll_calls=%lu coll_contacts=%lu c_steps=%lu c_rev=%lu c_hb_on=%lu shots=",
                    c->g, c->i, c->name, c->player, c->alive, c->t_seen, c->t_dead, c->t_tgt, c->dsum, c->dmin < 1e8 ? c->dmin : -1.0,
                    c->dbin[0], c->dbin[1], c->dbin[2], c->dbin[3], c->dbin[4], c->vsum, (unsigned long)c->steer_rev, (unsigned long)c->hb_on,
                    (unsigned long)c->shots_other, c->dmg_req_player, (unsigned long)c->hits_player, c->dmg_req_taken, (unsigned long)c->hits_taken,
                    c->lost_taken, c->dmg_req_by_player, (unsigned long)c->hits_by_player, (unsigned long)c->coll_calls, (unsigned long)c->coll_contacts,
                    (unsigned long)c->c_steps, (unsigned long)c->c_rev, (unsigned long)c->c_hb_on);
        for (j = 0; j < CBT_WPN && c->wshots[j]; j++) {
            char nm[9] = "?";
            BYTE *d = (BYTE *)0x005d88d8 + c->wdef[j] * 0xd8;
            int q;
            if (c->wdef[j] >= 0 && c->wdef[j] < 64 && !IsBadReadPtr(d, 8)) {
                for (q = 0; q < 8 && d[q] > 0x20 && d[q] < 0x7f; q++) nm[q] = (char)d[q];
                nm[q] = 0;
            }
            n += sprintf(line + n, "%d:%s:%lu,", c->wdef[j], nm, (unsigned long)c->wshots[j]);
        }
        n += sprintf(line + n, " bt=");
        for (j = 0; j < CBT_BEH; j++) if (c->be[j]) n += sprintf(line + n, "%d:%.2f:%lu,", j, c->bt[j], (unsigned long)c->be[j]);
        line[n++] = '\n';
        WriteFile(h, line, n, &w, NULL);
    }
    CloseHandle(h);
    MoveFileExA(tmp, g_cbt_path, MOVEFILE_REPLACE_EXISTING);
}
static void cbt_sample(void) {
    float now = *(volatile float *)0x005a7e74, dt;
    double px = 0.0, pz = 0.0; int g, i, have_p = 0;
    BYTE *pobj = tel_player(0);
    if (!g_cbt_have_t) { g_cbt_last_t = now; g_cbt_have_t = 1; return; }
    dt = now - g_cbt_last_t; g_cbt_last_t = now;
    if (dt < 0.0f || dt > 0.5f) return;                     /* a mission change or a pause */
    g_cbt_t += dt; g_cbt_frames++;
    {   /* did the frame since the last sample run a physics step? (always, without a fixed step) */
        int stepped = g_fixed_step <= 0.0f || g_stepframes != g_cbt_prev_steps;
        g_cbt_prev_steps = g_stepframes; g_cbt_stepped = stepped;
    }
    g_cbt_player = pobj;
    if (pobj) { px = *(double *)(pobj + 0x40); pz = *(double *)(pobj + 0x50); have_p = 1; }
    for (g = 0; g < 8; g++) {
        int n = ((volatile int *)0x0051f5d0)[g];
        BYTE **list = (BYTE **)(DWORD_PTR)(0x00507da0 + 0x100 * g);
        if (n < 0 || n > 64) continue;
        for (i = 0; i < n; i++) {
            BYTE *w = list[i], *obj, *e, *ai; cbt_car_t *c; int dead, b, depth;
            if (!w || IsBadReadPtr(w, 4)) continue;
            obj = *(BYTE **)w;
            if (!obj || IsBadReadPtr(obj, 0x74)) continue;
            e = *(BYTE **)(obj + 0x70);
            if (!e || IsBadReadPtr(e, 0x458)) continue;
            c = cbt_find(obj, 1);
            if (!c) continue;
            c->g = g; c->i = i;
            c->player = (*(DWORD *)(obj + 0x10) & 0x10) != 0;
            dead = (*(BYTE *)(obj + 0x10) & 0x20) || (*(DWORD *)(e + 0x454) & 0x20);
            c->alive = !dead;
            if (c->t_seen < 0.0) c->t_seen = g_cbt_t;
            if (dead) { if (c->t_dead < 0.0) c->t_dead = g_cbt_t; continue; }
            if (c->player) continue;
            if (have_p) {
                double dx = *(double *)(obj + 0x40) - px, dz = *(double *)(obj + 0x50) - pz, d = sqrt(dx * dx + dz * dz);
                c->dsum += d * dt; if (d < c->dmin) c->dmin = d;
                c->dbin[d < 25.0 ? 0 : d < 50.0 ? 1 : d < 100.0 ? 2 : d < 200.0 ? 3 : 4] += dt;
            }
            c->vsum += (double)*(float *)(e + 0xac) * dt;
            {
                float st = *(float *)(e + 0xe0);
                if ((st > 0.2f && c->steer_last < -0.2f) || (st < -0.2f && c->steer_last > 0.2f)) c->steer_rev++;
                if (st > 0.2f || st < -0.2f) c->steer_last = st;
            }
            { int hb = *(DWORD *)(e + 0xf0) != 0; if (hb && !c->hb) c->hb_on++; c->hb = hb; }
            if (c->pend_ok && g_cbt_stepped) {              /* the values sampled last frame were consumed by its step(s) */
                float st = c->pend_steer;
                c->c_steps++;
                if ((st > 0.2f && c->c_steer_last < -0.2f) || (st < -0.2f && c->c_steer_last > 0.2f)) c->c_rev++;
                if (st > 0.2f || st < -0.2f) c->c_steer_last = st;
                if (c->pend_hb && !c->c_hb) c->c_hb_on++;
                c->c_hb = c->pend_hb;
            }
            c->pend_steer = *(float *)(e + 0xe0); c->pend_hb = *(DWORD *)(e + 0xf0) != 0; c->pend_ok = 1;
            ai = *(BYTE **)(e + 0x108);
            if (!ai || IsBadReadPtr(ai + 0xa874, 0x150)) continue;
            depth = *(int *)(ai + 0xa93c);
            b = (depth >= 0 && depth < 50) ? *(int *)(ai + 0xa874 + 4 * depth) : -1;
            if (b < 0 || b > 33) b = 34;
            c->bt[b] += dt;
            if (b != c->beh) { c->be[b]++; c->beh = b; }
            if (pobj && *(BYTE **)(ai + 0xa9b4) == pobj) c->t_tgt += dt;
        }
    }
}
static void cbt_frame(void) {
#ifdef _MSC_VER
    __try { cbt_sample(); } __except (EXCEPTION_EXECUTE_HANDLER) { g_tel_faults++; }
#else
    cbt_sample();
#endif
    if (GetTickCount() - g_cbt_flush_tick > 1000) { g_cbt_flush_tick = GetTickCount(); cbt_flush(); }
}
static int cbt_wrap_if_stock(DWORD site, DWORD target, void *wrap, const char *what) {
    BYTE o[5] = { 0xE8 };
    LONG rel = (LONG)(target - (site + 5));
    memcpy(o + 1, &rel, 4);
    if (memcmp((void *)(DWORD_PTR)site, o, 5) != 0) return 0;  /* a switch already wrapped it */
    return tel_repoint_call(site, target, wrap, what);
}
static void apply_combat_log(void) {
    static const BYTE rand_old[6] = { 0xFF, 0x15, 0x0C, 0xC2, 0x4B, 0x00 };
    int nf = 0, nd = 0, nr = 0, i;
    if (!env_str("I76_COMBAT_LOG", g_cbt_path, sizeof(g_cbt_path))) return;
    if (!g_tel_on || !g_dmg_tramp) { mlog("  combat-log: needs I76_TELEMETRY=1 and I76_DAMAGE_EVENTS=1 - off"); return; }
    /* pass-through counters where no switch holds the site: g_tick20 stays 1 without the frame-rate fixes, and the
     * holds are off for sites installed here, so every call goes to the game's own function */
    if (!g_ratefix) g_aifire_cache = 0;
    nf += cbt_wrap_if_stock(0x00414f75, 0x00418200, (void *)ai_fire_wrap, "AI fire decision (vehicles, combat-log)");
    nf += cbt_wrap_if_stock(0x00462bfb, 0x00418200, (void *)ai_fire_wrap, "AI fire decision (turrets, combat-log)");
    nf += cbt_wrap_if_stock(0x00462c3e, 0x00418200, (void *)ai_fire_wrap, "AI fire decision (turrets 2, combat-log)");
    if (cbt_wrap_if_stock(0x0041b698, 0x0041abf0, (void *)ai_dodge_wrap, "AI dodge check (combat-log)")) { g_dodge_hold = 0; nd = 1; }
    if (!g_ratefix) {
        static const struct { DWORD site; void *wrap; } rs[2] = { { 0x0041f5d4, (void *)ai_skid_rand }, { 0x0041dacc, (void *)ai_horn_rand } };
        for (i = 0; i < 2; i++) {
            BYTE w[6] = { 0xE8, 0, 0, 0, 0, 0x90 };
            LONG rel = (LONG)((DWORD_PTR)rs[i].wrap - (rs[i].site + 5));
            memcpy(w + 1, &rel, 4);
            nr += patch_bytes(rs[i].site, rand_old, w, 6, "AI skid / horn roll (combat-log)");
        }
    }
    install_frame_hook();
    g_cbt_on = g_frame_hook;
    mlog("  combat-log: %s -> %s (pass-through counters added: fire %d/3, dodge %d/1, skid+horn %d/2)",
         g_cbt_on ? "on" : "NOT on (frame hook)", g_cbt_path, nf, nd, nr);
}

/* ===========================================================================
 * GLIDE REFRESH OVERRIDE  (I76_GLIDE_REFRESH=<hz>; off by default; docs/records/FPS-120.md)
 * ===========================================================================
 * The frame rate sits at exactly 60 whatever the panel does (179 Hz desktop, FPSLimit inert, ForceVerticalSync
 * false, a forced "3360x2100, 120" Glide resolution: all measured 60.0 on 2026-10-02), with the main thread waiting
 * inside the NVIDIA D3D11 user-mode driver's present. The one lever not yet pulled: the renderer (ZGLIDE.DLL, loaded
 * by name through LoadLibraryA) opens its window with grSstWinOpen(hWnd, res, refresh = GR_REFRESH_60Hz, ...) and
 * dgVoodoo paces windowed presents at the refresh the app asked for. zglide reaches grSstWinOpen through its own
 * import slot (glide2x.dll!_grSstWinOpen@28), so: hook the exe's LoadLibraryA, and when ZGLIDE.DLL comes in, repoint
 * that slot at a wrapper that substitutes the requested refresh code. Glide 2.x codes: 60 Hz 0, 70 1, 72 2, 75 3,
 * 80 4, 90 5, 100 6, 85 7, 120 8; "none" 0xff. Measured result in the log. */
typedef DWORD (__stdcall *grSstWinOpen_t)(DWORD hwnd, DWORD res, DWORD refresh, DWORD cfmt, DWORD origin, int ncol, int naux);
static grSstWinOpen_t p_grSstWinOpen;
static HMODULE (WINAPI *p_LoadLibraryA)(LPCSTR);
static DWORD g_glide_refresh_code = 0xffffffff, g_glide_refresh_hz;
/* I76_GLIDE_GAMMA=<g> (2026-10-07; off by default). ZGLIDE.DLL imports no Glide gamma call at all (its glide2x imports
 * were listed: no grGammaCorrectionValue), so the game never sets a ramp and dgVoodoo's [Glide] EnableGlideGammaRamp has
 * nothing to apply on any platform (A/B on the Steam Deck: identical frames with it on and off). On a real Voodoo the
 * board's own default gamma (about 1.3) brightened the picture; nothing provides that here, which is the "darker than I
 * remember" look. With this switch the wrapper below calls glide2x!grGammaCorrectionValue(g) after every successful
 * grSstWinOpen. A curve lifts the mid-tones without clipping highlights, which dgVoodoo's linear [General] Brightness
 * does. Needs EnableGlideGammaRamp = true in the conf. */
static float g_glide_gamma;

static void glide_apply_gamma(void) {
    void (__stdcall *gamma)(float);
    HMODULE g = GetModuleHandleA("glide2x.dll");
    if (g_glide_gamma <= 0.0f) return;
    gamma = g ? (void (__stdcall *)(float))GetProcAddress(g, "_grGammaCorrectionValue@4") : NULL;
    if (gamma) gamma(g_glide_gamma);
    mlog("  glide-gamma: grGammaCorrectionValue(%d.%02d) %s", (int)g_glide_gamma, (int)(g_glide_gamma * 100.0f + 0.5f) % 100,
         gamma ? "called" : "NOT found in glide2x.dll");
}

static DWORD __stdcall hook_grSstWinOpen(DWORD hwnd, DWORD res, DWORD refresh, DWORD cfmt, DWORD origin, int ncol, int naux) {
    DWORD r;
    /* only I76_GLIDE_REFRESH substitutes the refresh; under I76_GLIDE_GAMMA alone (or the removed I76_GLIDE_DIR) the renderer's own
       code goes through (before 2026-10-07 the unset 0xffffffff was passed and rescued by the fallback reopen below) */
    DWORD code = (g_glide_refresh_code != 0xffffffff) ? g_glide_refresh_code : refresh;
    mlog("  glide-refresh: grSstWinOpen(res %lu, refresh %lu -> %lu (%lu Hz), cfmt %lu, origin %lu, %d/%d buffers)",
         (unsigned long)res, (unsigned long)refresh, (unsigned long)code, (unsigned long)g_glide_refresh_hz,
         (unsigned long)cfmt, (unsigned long)origin, ncol, naux);
    r = p_grSstWinOpen(hwnd, res, code, cfmt, origin, ncol, naux);
    mlog("  glide-refresh: context %lu", (unsigned long)r);
    if (!r) {   /* dgVoodoo rejects codes above 8 (measured 2026-10-02: code 9 -> context 0, then the exe faults at
                   0x42e209): never leave the game without a window - fall back to what the renderer asked for */
        r = p_grSstWinOpen(hwnd, res, refresh, cfmt, origin, ncol, naux);
        mlog("  glide-refresh: code %lu rejected - reopened with the renderer's own refresh %lu, context %lu",
             (unsigned long)code, (unsigned long)refresh, (unsigned long)r);
    }
    if (r) glide_apply_gamma();
    return r;
}

/* ===========================================================================
 * TEXTURE CENSUS  (I76_TEX_CENSUS=1; off by default; lab docs/TEXTURE-DELIVERY.md s.2/6, docs/TERRAIN-WHITE-FLASH.md)
 * ===========================================================================
 * Count-only hooks on ZGLIDE's glide2x imports (no behaviour change): texture downloads and their bytes
 * (grTexCalcMemRequired of the GrTexInfo), full cache flushes (grTexMinAddress: once in FirstDevice, once per flush at
 * 0x100017f7), and a readback of grTexMaxAddress (which MemorySizeOfTMU dgVoodoo really took). Per swapped frame
 * (grBufferSwap) it samples ZGLIDE's own state: next free TMU address [0x1001fd20] (bytes resident = next - min),
 * TMU index [0x1001f894], and the "no slot, drawn with the wrong texture" flag [0x10178ea0] (set at 0x100018f3,
 * cleared by the flush). Every flush and every rising edge of the flag is logged with its frame number and QPC ms;
 * a summary line every 600 swaps. */
typedef struct { int smallLod, largeLod, aspect, format; void *data; } tc_texinfo_t;
static int g_tc_on;
static HMODULE g_tc_zg;
static DWORD g_tc_minaddr;
static DWORD (__stdcall *p_tc_MaxAddress)(DWORD);
static DWORD (__stdcall *p_tc_MinAddress)(DWORD);
static void  (__stdcall *p_tc_Download)(DWORD, DWORD, DWORD, tc_texinfo_t *);
static DWORD (__stdcall *p_tc_CalcMem)(int, int, int, int);
static void  (__stdcall *p_tc_Swap)(int);
static DWORD g_tc_swaps, g_tc_dl, g_tc_dlb, g_tc_flush, g_tc_minc, g_tc_noslot, g_tc_noslot_frames, g_tc_last_flag;
static DWORD g_tc_win_dl, g_tc_win_dlb, g_tc_win_flush, g_tc_win_noslot, g_tc_peak_res;
static double tc_ms(void) { LARGE_INTEGER q; QueryPerformanceCounter(&q); return (double)q.QuadPart * 1000.0 / (double)g_qpf.QuadPart; }
static DWORD tc_zg(DWORD va) { return g_tc_zg ? *(volatile DWORD *)((BYTE *)g_tc_zg + (va - 0x10000000)) : 0; }
static DWORD __stdcall tc_MaxAddress(DWORD t) {
    DWORD r = p_tc_MaxAddress(t); static DWORD last = 0xffffffff;
    if (r != last) { last = r; mlog("  tex-census: grTexMaxAddress(%lu) = 0x%lx (%lu KB usable TMU)", (unsigned long)t, (unsigned long)r, (unsigned long)(r / 1024)); }
    return r;
}
static void tc_dump(const char *kind, int buf);
static DWORD g_tc_shot_at, g_tc_ctl_at, g_tc_shots;
static DWORD __stdcall tc_MinAddress(DWORD t) {
    DWORD r = p_tc_MinAddress(t);
    g_tc_minaddr = r; g_tc_minc++;
    if (g_tc_minc > 1 || g_tc_swaps) {   /* the FirstDevice call is not a flush */
        g_tc_flush++; g_tc_win_flush++;
        if (g_tc_on == 2 && g_tc_shots < 16 && !g_tc_shot_at && !g_tc_ctl_at) { g_tc_shots++; g_tc_shot_at = g_tc_swaps + 1; tc_dump("flush-front", 0); }
        mlog("  tex-census: FLUSH #%lu at swap %lu (proxy frame %lu, t %.0f ms): %lu downloads / %lu KB since start, resident before %lu KB, no-slot flag %lu",
             (unsigned long)g_tc_flush, (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)g_tc_dl,
             (unsigned long)(g_tc_dlb / 1024), (unsigned long)((tc_zg(0x1001fd20) - r) / 1024), (unsigned long)tc_zg(0x10178ea0));
    } else mlog("  tex-census: grTexMinAddress(%lu) = 0x%lx (FirstDevice)", (unsigned long)t, (unsigned long)r);
    return r;
}
static int g_fp_on;                                     /* I76_FLASH_PROBE (FLASH PROBE below) */
static void fp_log_download(DWORD addr, tc_texinfo_t *i, DWORD bytes, DWORD *sp);
static void fp_before_swap(void);
static void fp_window(void);
static void __stdcall tc_Download(DWORD tmu, DWORD addr, DWORD eo, tc_texinfo_t *i) {
    DWORD b = (p_tc_CalcMem && i) ? p_tc_CalcMem(i->smallLod, i->largeLod, i->aspect, i->format) : 0;
    g_tc_dl++; g_tc_dlb += b; g_tc_win_dl++; g_tc_win_dlb += b;
    if (g_fp_on) fp_log_download(addr, i, b, (DWORD *)_AddressOfReturnAddress());
    p_tc_Download(tmu, addr, eo, i);
}
/* I76_TEX_CENSUS=2 adds frame dumps: the back buffer about to be shown at the swap right after a flush (the frame
 * drawn while the no-slot flag was up) and a control 30 swaps later, read with grLfbReadRegion (app resolution, RGB565)
 * to <game>\texcensus-<swap>-{flush,ctl}.bmp, at most 16 flushes. */
static void tc_dump(const char *kind, int buf) {
    typedef int (__stdcall *rd_t)(int, DWORD, DWORD, DWORD, DWORD, DWORD, void *);
    typedef DWORD (__stdcall *wh_t)(void);
    HMODULE g = GetModuleHandleA("glide2x.dll");
    rd_t rd = (rd_t)GetProcAddress(g, "_grLfbReadRegion@28");
    wh_t sw = (wh_t)GetProcAddress(g, "_grSstScreenWidth@0"), sh = (wh_t)GetProcAddress(g, "_grSstScreenHeight@0");
    DWORD w = sw ? sw() : 640, h = sh ? sh() : 480, y, x; WORD *px; BYTE *row; char path[MAX_PATH]; HANDLE f; DWORD wr;
    BITMAPFILEHEADER bf; BITMAPINFOHEADER bi;
    if (!rd || w == 0 || h == 0 || w > 4096 || h > 4096) { mlog("  tex-census: dump %s - no grLfbReadRegion / size %lux%lu", kind, (unsigned long)w, (unsigned long)h); return; }
    px = (WORD *)HeapAlloc(GetProcessHeap(), 0, w * h * 2); row = (BYTE *)HeapAlloc(GetProcessHeap(), 0, w * 3 + 4);
    if (!px || !row) return;
    if (!rd(buf /* 0 front, 1 back */, 0, 0, w, h, w * 2, px)) { mlog("  tex-census: dump %s - grLfbReadRegion failed", kind); goto out; }
    wsprintfA(path, "%s\\texcensus-%05lu-%s.bmp", g_dir, (unsigned long)g_tc_swaps, kind);
    f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) goto out;
    ZeroMemory(&bf, sizeof bf); ZeroMemory(&bi, sizeof bi);
    bf.bfType = 0x4d42; bf.bfOffBits = sizeof bf + sizeof bi; bf.bfSize = bf.bfOffBits + ((w * 3 + 3) & ~3u) * h;
    bi.biSize = sizeof bi; bi.biWidth = (LONG)w; bi.biHeight = (LONG)h; bi.biPlanes = 1; bi.biBitCount = 24;
    WriteFile(f, &bf, sizeof bf, &wr, NULL); WriteFile(f, &bi, sizeof bi, &wr, NULL);
    for (y = h; y-- > 0;) {
        for (x = 0; x < w; x++) { WORD p = px[y * w + x];
            row[x * 3 + 2] = (BYTE)(((p >> 11) & 31) * 255 / 31); row[x * 3 + 1] = (BYTE)(((p >> 5) & 63) * 255 / 63); row[x * 3] = (BYTE)((p & 31) * 255 / 31); }
        WriteFile(f, row, (w * 3 + 3) & ~3u, &wr, NULL);
    }
    CloseHandle(f);
    mlog("  tex-census: dumped %s (%lux%lu)", path, (unsigned long)w, (unsigned long)h);
out:
    HeapFree(GetProcessHeap(), 0, px); HeapFree(GetProcessHeap(), 0, row);
}
/* ===========================================================================
 * FRAME SPIKE LOG  (I76_FRAME_SPIKES=<ms>, 1 = 250; off by default; lab docs/RENDER-FREEZE-2026-10-04.md)
 * ===========================================================================
 * For the owner's "the picture freezes for a few seconds while the game runs on" and "the terrain flashes to sky"
 * reports under best-wide. Turns on the texture census hooks (above; no behaviour change) and times every swap:
 * frame = swap-to-swap interval, present = time inside glide2x grBufferSwap (dgVoodoo's present + its pacing).
 * A frame or present at or above the threshold is logged as SPIKE with that frame's census deltas (downloads, KB,
 * flushes, no-slot flag, resident) and the scene counters sampled at the scene flush (road_flush_wrap, below):
 *   terrain vertices [0x6442ec] (reset per QueueTerrain; renderer_SplitTerrainEdge stores the index as int16, so a
 *     frame past 32,767 draws wrong vertices without faulting - docs/records/FARCLIP-CAMERA-CRASH.md; the 2500 m cap
 *     was measured WITHOUT I76_TERRAIN_LOD, which raises the count),
 *   draw-record arena use [0x654380] - [0x5dd324] (pool 0x80000 x16, docs/DRAW-DISTANCE.md), its record count
 *     [0x59c568], span nodes [0x6543b8] - [0x6543bc] (road pool).
 * The other two enlarged constants (0x40000 at 0x402f99, the 0xd2f0 split) have no known cursor: not sampled.
 * Rising edges past 32,767 vertices are logged as TERRAIN-WRAP; a summary every 600 swaps. Live 2026-10-04 on the
 * lab twin: vertex counts 1.1k..17.9k and arena 0.1..0.7 MB, matching the soaks; every spike was a chain of ZGLIDE
 * cache flushes (lab docs/RENDER-FREEZE-2026-10-04.md). */
static DWORD g_fs_ms;                                   /* threshold; 0 = off */
static double g_fs_last;                                /* tc_ms() after the previous swap */
static DWORD g_fs_dl0, g_fs_dlb0, g_fs_fl0;             /* census totals after the previous swap */
static DWORD g_fs_spikes, g_fs_win_spikes, g_fs_win_slow, g_fs_win_dlmax;
static double g_fs_win_frame, g_fs_win_present;
static DWORD g_fs_vcount, g_fs_arena, g_fs_recs, g_fs_nodes, g_fs_scenes;          /* last scene flush */
static DWORD g_fs_win_vmax, g_fs_win_arena, g_fs_win_over, g_fs_over_total, g_fs_last_over;
static void fs_sample_scene(void) {                     /* from road_flush_wrap, before the flush */
    DWORD v = *(volatile DWORD *)(DWORD_PTR)NA(0x006442ec), cur = *(volatile DWORD *)(DWORD_PTR)NA(0x00654380), base = *(volatile DWORD *)(DWORD_PTR)NA(0x005dd324);
    DWORD nc = *(volatile DWORD *)(DWORD_PTR)NA(0x006543b8), nb = *(volatile DWORD *)(DWORD_PTR)NA(0x006543bc);
    g_fs_scenes++;
    g_fs_vcount = v; g_fs_recs = *(volatile DWORD *)(DWORD_PTR)NA(0x0059c568);
    g_fs_arena = (base && cur >= base) ? cur - base : 0;
    g_fs_nodes = (nb && nc >= nb) ? nc - nb : 0;
    if (v > g_fs_win_vmax) g_fs_win_vmax = v;
    if (g_fs_arena > g_fs_win_arena) g_fs_win_arena = g_fs_arena;
    if (v > 32767) {
        g_fs_win_over++; g_fs_over_total++;
        if (!g_fs_last_over)
            mlog("  frame-spikes: TERRAIN-WRAP at swap %lu (proxy frame %lu, t %.0f ms): %lu terrain vertices > 32767 (int16 index wraps: wrong vertices this frame); arena %lu KB",
                 (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)v, (unsigned long)(g_fs_arena >> 10));
    }
    g_fs_last_over = v > 32767;
}
static void fs_after_swap(double t0) {
    double t1 = tc_ms(), frame = g_fs_last > 0.0 ? t1 - g_fs_last : 0.0, present = t1 - t0;
    DWORD dl = g_tc_dl - g_fs_dl0, kb = (g_tc_dlb - g_fs_dlb0) >> 10, fl = g_tc_flush - g_fs_fl0;
    if (frame > g_fs_win_frame) g_fs_win_frame = frame;
    if (present > g_fs_win_present) g_fs_win_present = present;
    if (dl > g_fs_win_dlmax) g_fs_win_dlmax = dl;
    if (frame >= 100.0) g_fs_win_slow++;
    if (g_fs_last > 0.0 && (frame >= (double)g_fs_ms || present >= (double)g_fs_ms)) {
        g_fs_spikes++; g_fs_win_spikes++;
        mlog("  frame-spikes: SPIKE #%lu at swap %lu (proxy frame %lu, t %.0f ms, state %lu): frame %.1f ms, present %.1f ms | this frame: %lu downloads %lu KB, %lu flushes, no-slot %lu, resident %lu KB | scene: terrain vertices %lu, arena %lu KB (%lu records), span nodes %lu KB",
             (unsigned long)g_fs_spikes, (unsigned long)g_tc_swaps, (unsigned long)g_frame, t1, (unsigned long)*(volatile DWORD *)(DWORD_PTR)NA(0x004c2164),
             frame, present, (unsigned long)dl, (unsigned long)kb, (unsigned long)fl, (unsigned long)tc_zg(0x10178ea0),
             (unsigned long)((tc_zg(0x1001fd20) - g_tc_minaddr) / 1024), (unsigned long)g_fs_vcount, (unsigned long)(g_fs_arena >> 10),
             (unsigned long)g_fs_recs, (unsigned long)(g_fs_nodes >> 10));
    }
    if (g_tc_swaps % 600 == 0) {
        mlog("  frame-spikes: swaps %lu: last 600: max frame %.1f ms, max present %.1f ms, %lu frames >= 100 ms, %lu spikes >= %lu ms, max %lu downloads in one frame | terrain vertices max %lu (%lu frames > 32767), arena max %lu KB; %lu scene flushes | totals %lu spikes, %lu wrap frames",
             (unsigned long)g_tc_swaps, g_fs_win_frame, g_fs_win_present, (unsigned long)g_fs_win_slow, (unsigned long)g_fs_win_spikes,
             (unsigned long)g_fs_ms, (unsigned long)g_fs_win_dlmax, (unsigned long)g_fs_win_vmax, (unsigned long)g_fs_win_over,
             (unsigned long)(g_fs_win_arena >> 10), (unsigned long)g_fs_scenes, (unsigned long)g_fs_spikes, (unsigned long)g_fs_over_total);
        g_fs_win_frame = g_fs_win_present = 0.0; g_fs_win_spikes = g_fs_win_slow = g_fs_win_dlmax = 0;
        g_fs_win_vmax = g_fs_win_arena = g_fs_win_over = g_fs_scenes = 0;
    }
    g_fs_last = tc_ms(); g_fs_dl0 = g_tc_dl; g_fs_dlb0 = g_tc_dlb; g_fs_fl0 = g_tc_flush;   /* after the mlog: its cost is not the next frame's */
}

/* ===========================================================================
 * CAMERA-UNDER-GROUND TERRAIN SKIP  (I76_CAM_GROUND_FIX=1; off by default; lab docs/RENDER-FREEZE-2026-10-04.md s.9)
 * ===========================================================================
 * The owner's one-frame "terrain vanishes, sky shows" (b). renderer_QueueTerrain 0x490a00 calls the terrain setup
 * 0x4929b0(camera) at 0x490b1e; its first step (0x4929f7..0x492a11) samples the terrain height under the camera
 * (0x493550, cdecl (double x, double z) -> st0) and, if the camera is less than 0.01 m (0x4be878) above it, returns 0:
 * QueueTerrain then queues NO terrain this frame and fills the view with palette 0xb4 (0x490b46, 0x474ea0); under
 * Glide the sky and clouds drawn before stay, so the whole ground turns to sky for that frame. It happens whenever the
 * eye point dips under the local terrain surface: cockpit / hood eye with the car nosed into a bank or a slope, a
 * chase camera behind a crest. Found with I76_FLASH_PROBE on t04 (2026-10-05): 3 zero-terrain frames in 60 s of
 * circle driving into the dunes, eye 0.04 .. 1.25 m under the surface, the dumped frame all sky below the horizon.
 * Fix: call the setup; when it bails, lift the camera's y (+0x168, double) to 0.05 m above the sampled height, call it
 * again so the terrain footprint and quadtree are built as for a camera just above the ground, and put y back before
 * anything else reads it. The view transform is untouched (the frame is drawn from the real eye; the surface just
 * above the eye is seen from below, as the car body already is). Counted and logged (first 20, then every 600 swaps
 * with I76_FLASH_PROBE). The same setup serves the mirror pass, which gets the same treatment. */
static int g_cg_on; static DWORD g_cg_lifts, g_cg_fail;
static int __cdecl cam_ground_setup_wrap(BYTE *cam) {
    int r = ((int (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x004929b0))(cam);
    if (r == 0 && g_cg_on && cam) {
        double *py = (double *)(cam + 0x168), y0 = *py;
        double h = ((double (__cdecl *)(double, double))(DWORD_PTR)NA(0x00493550))(*(double *)(cam + 0x160), *(double *)(cam + 0x170));
        if (h > -1.0e6 && h < 1.0e6 && h + 0.05 > y0 && h + 0.05 - y0 < 50.0) {
            *py = h + 0.05;
            r = ((int (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x004929b0))(cam);
            *py = y0;
            g_cg_lifts++;
            if (!r) g_cg_fail++;
            if (g_cg_lifts <= 20 || !r)
                mlog("  cam-ground-fix: lift #%lu (camera %p, %s, mode %d): eye %.3f m under the terrain height %.2f; setup %s",
                     (unsigned long)g_cg_lifts, (void *)cam, cam == (BYTE *)(DWORD_PTR)NA(0x004c2730) ? "main" : "other", *(int *)(DWORD_PTR)NA(0x004c2728), h - y0, h, r ? "ok, terrain queued" : "STILL refused");
            /* 2026-10-09: the main camera under the ground IN COCKPIT VIEW (camera_mode 0x4c2728 == 0) means the car
               body is under it too (orbit / chase views put the eye near the ground on their own). Counted apart. */
            if (cam == (BYTE *)(DWORD_PTR)NA(0x004c2730) && *(int *)(DWORD_PTR)NA(0x004c2728) == 0) {
                static unsigned long n_ck;
                if (++n_ck <= 200) mlog("  cam-ground-fix: COCKPIT-UNDER #%lu: eye %.3f m under the terrain height %.2f", n_ck, h - y0, h);
            }
        }
    }
    return r;
}
static void apply_cam_ground_fix(void) {
    static const BYTE old[5] = { 0xe8, 0x8d, 0x1e, 0x00, 0x00 };   /* call 0x4929b0 at 0x490b1e */
    BYTE w[5] = { 0xe8 }; LONG rel;
    if (env_flag("I76_CAM_GROUND_FIX", 4, 0) != 1) return;
    rel = (LONG)((DWORD_PTR)cam_ground_setup_wrap - (0x00490b1e + 5)); memcpy(w + 1, &rel, 4);
    g_cg_on = patch_bytes(0x00490b1e, old, w, 5, "terrain setup call (camera-under-ground lift)");
    mlog("  cam-ground-fix: %s (QueueTerrain 0x490b1e -> lift the camera 0.05 m above the terrain for the terrain setup when it is under it)",
         g_cg_on ? "on" : "NOT applied (bytes differ)");
}

/* ===========================================================================
 * FLASH PROBE  (I76_FLASH_PROBE=1 per-frame terrain counters, =2 also pixel rows; needs I76_FRAME_SPIKES; off by default)
 * ===========================================================================
 * For the owner's one-frame "terrain vanishes, sky colour shows" (lab docs/RENDER-FREEZE-2026-10-04.md (b)); a 150 ms
 * screen sampler sees a one-frame event only ~5 % of the time, so this looks at EVERY main scene:
 *  - at the main scene flush (road_flush_wrap): terrain vertices [0x6442ec] (reset by renderer_QueueTerrain 0x490add
 *    BEFORE its camera-under-ground bail 0x490b26: no terrain queued, screen filled with palette 0xb4 by 0x474ea0), the
 *    camera QueueTerrain was given [0x6442d4] (position doubles at +0x160), the terrain height under it (0x493550,
 *    cdecl (double x, double z), st0), state, camera mode [0x4c2728]. A scene with 0 vertices after one with > 500, or
 *    under 30 % of the previous scene's with the camera moved < 2 m, is logged as TERRAIN-DROP and its back buffer is
 *    dumped at the swap that follows (<game>\texcensus-<swap>-flashprobe-drop.bmp, at most 12 dumps in all).
 *  - =2: before each swap, grLfbReadRegion reads rows at I76_FLASH_ROWS percent of the height (default 12,55,70; the
 *    first is the reference "sky" row). A frame whose lower rows are uniform (mean abs deviation < 6) and either within
 *    30 of the reference row's colour or near-white, after a frame where they were not, is logged as PIXEL-FLASH and
 *    dumped (texcensus-<swap>-flashprobe-pix.bmp). Costs one back-buffer readback per frame: measure before trusting fps.
 *  - texture downloads of swaps 1800..1802 and 7200..7202 are logged one by one (address, size, LODs, aspect, format,
 *    the first i76.exe return addresses on the stack) to name the steady per-frame uploads. */
static DWORD g_fp_prev_v, g_fp_events, g_fp_zero, g_fp_drop, g_fp_dumps, g_fp_dump_kind, g_fp_scenes;
static DWORD g_fp_win_vmin = 0xffffffff, g_fp_win_zero, g_fp_win_drop, g_fp_pix_events, g_fp_win_pix, g_fp_logged_cam;
static double g_fp_prev_pos[3];
static int g_fp_rows[3] = { 12, 55, 70 };
static int g_fp_prev_flag;
static double g_fp_win_maxlow;                      /* min distance low-vs-ref in the window (closest to sky) */
static DWORD g_fp_seen_lifts;
static void fp_scene(void *cam_arg) {
    DWORD v = *(volatile DWORD *)(DWORD_PTR)NA(0x006442ec); BYTE *cam = *(BYTE **)(DWORD_PTR)NA(0x006442d4); double p[3] = { 0, 0, 0 }, mv = 0.0, gh = 0.0;
    g_fp_scenes++;
    if (!g_fp_logged_cam) { g_fp_logged_cam = 1; mlog("  flash-probe: first main scene: flush camera %p, QueueTerrain camera %p", cam_arg, (void *)cam); }
    if (cam) { memcpy(p, cam + 0x160, sizeof p); }
    { double dx = p[0] - g_fp_prev_pos[0], dy = p[1] - g_fp_prev_pos[1], dz = p[2] - g_fp_prev_pos[2]; mv = sqrt(dx * dx + dy * dy + dz * dz); }
    if (v < g_fp_win_vmin) g_fp_win_vmin = v;
    if (g_fp_prev_v > 500 && (v == 0 || (v * 10 < g_fp_prev_v * 3 && mv < 2.0))) {
        float *pl = (float *)(DWORD_PTR)NA(0x0054e11c);
        g_fp_events++; if (v == 0) { g_fp_zero++; g_fp_win_zero++; } else { g_fp_drop++; g_fp_win_drop++; }
        if (cam) gh = ((double (__cdecl *)(double, double))(DWORD_PTR)NA(0x00493550))(p[0], p[2]);
        if (g_fp_events <= 300)
            mlog("  flash-probe: TERRAIN-DROP #%lu at swap %lu (proxy frame %lu, t %.0f ms, state %lu, cam mode %lu): terrain vertices %lu (previous scene %lu) | camera (%.2f, %.2f, %.2f), %.3f m above the terrain height %.2f, moved %.2f m since the previous scene | player (%.1f, %.1f, %.1f) | records %lu",
                 (unsigned long)g_fp_events, (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)*(volatile DWORD *)(DWORD_PTR)NA(0x004c2164),
                 (unsigned long)*(volatile DWORD *)(DWORD_PTR)NA(0x004c2728), (unsigned long)v, (unsigned long)g_fp_prev_v, p[0], p[1], p[2], p[1] - gh, gh, mv,
                 pl[0], pl[1], pl[2], (unsigned long)*(volatile DWORD *)(DWORD_PTR)NA(0x0059c568));
        if (g_fp_dumps < 12 && !g_fp_dump_kind) g_fp_dump_kind = 1;
    }
    if (g_cg_lifts != g_fp_seen_lifts) {       /* a lifted (fixed) frame: dump the first few to see what it looks like */
        g_fp_seen_lifts = g_cg_lifts;
        if (g_fp_dumps < 12 && !g_fp_dump_kind && g_cg_lifts <= 6) g_fp_dump_kind = 2;
    }
    g_fp_prev_v = v; memcpy(g_fp_prev_pos, p, sizeof p);
}
static void fp_dump_named(const char *kind) {       /* tc_dump writes texcensus-<swap>-<kind>.bmp; name it flashprobe-... */
    char k[32]; wsprintfA(k, "flashprobe-%s", kind); tc_dump(k, 1); g_fp_dumps++;
}
typedef int (__stdcall *fp_rd_t)(int, DWORD, DWORD, DWORD, DWORD, DWORD, void *);
static fp_rd_t g_fp_rd; static DWORD g_fp_w, g_fp_h; static WORD *g_fp_row;
static void fp_row_stats(DWORD y, double m[3], double *mad) {      /* 32 samples across one row of the back buffer */
    int i; double s[32][3];
    m[0] = m[1] = m[2] = 0; *mad = 0;
    if (!g_fp_rd(1, 0, y, g_fp_w, 1, g_fp_w * 2, g_fp_row)) { *mad = -1; return; }
    for (i = 0; i < 32; i++) { WORD q = g_fp_row[(g_fp_w * (2 * i + 1)) / 64];
        s[i][0] = ((q >> 11) & 31) * 255.0 / 31; s[i][1] = ((q >> 5) & 63) * 255.0 / 63; s[i][2] = (q & 31) * 255.0 / 31;
        m[0] += s[i][0]; m[1] += s[i][1]; m[2] += s[i][2]; }
    m[0] /= 32; m[1] /= 32; m[2] /= 32;
    for (i = 0; i < 32; i++) *mad += (fabs(s[i][0] - m[0]) + fabs(s[i][1] - m[1]) + fabs(s[i][2] - m[2])) / 3.0;
    *mad /= 32;
}
static void fp_before_swap(void) {
    if (g_fp_dump_kind) { fp_dump_named(g_fp_dump_kind == 2 ? "lifted" : "drop"); g_fp_dump_kind = 0; }
    if (g_fp_on < 2) return;
    if (!g_fp_rd) {
        HMODULE g = GetModuleHandleA("glide2x.dll"); DWORD (__stdcall *sw)(void), (__stdcall *sh)(void);
        g_fp_rd = (fp_rd_t)GetProcAddress(g, "_grLfbReadRegion@28");
        sw = (DWORD (__stdcall *)(void))GetProcAddress(g, "_grSstScreenWidth@0"); sh = (DWORD (__stdcall *)(void))GetProcAddress(g, "_grSstScreenHeight@0");
        g_fp_w = sw ? sw() : 0; g_fp_h = sh ? sh() : 0;
        if (!g_fp_rd || !g_fp_w || g_fp_w > 8192 || !g_fp_h) { g_fp_on = 1; mlog("  flash-probe: no grLfbReadRegion / screen size - pixel rows off"); return; }
        g_fp_row = (WORD *)HeapAlloc(GetProcessHeap(), 0, g_fp_w * 2 + 16);
        mlog("  flash-probe: pixel rows at %d/%d/%d %% of %lux%lu", g_fp_rows[0], g_fp_rows[1], g_fp_rows[2], (unsigned long)g_fp_w, (unsigned long)g_fp_h);
    }
    if (*(volatile DWORD *)(DWORD_PTR)NA(0x004c2164) != 5) { g_fp_prev_flag = 0; return; }     /* missions only */
    {   double r[3], a[3], b[3], mr, ma, mb, da, db; int white, sky, flag;
        fp_row_stats(g_fp_h * g_fp_rows[0] / 100, r, &mr); fp_row_stats(g_fp_h * g_fp_rows[1] / 100, a, &ma); fp_row_stats(g_fp_h * g_fp_rows[2] / 100, b, &mb);
        if (mr < 0 || ma < 0 || mb < 0) return;
        da = (fabs(a[0] - r[0]) + fabs(a[1] - r[1]) + fabs(a[2] - r[2])) / 3.0; db = (fabs(b[0] - r[0]) + fabs(b[1] - r[1]) + fabs(b[2] - r[2])) / 3.0;
        sky = ma < 6 && mb < 6 && da < 30 && db < 30;
        white = ma < 6 && mb < 6 && a[0] > 225 && a[1] > 225 && a[2] > 225 && b[0] > 225 && b[1] > 225 && b[2] > 225;
        flag = sky || white;
        if (flag && !g_fp_prev_flag) {
            g_fp_pix_events++; g_fp_win_pix++;
            if (g_fp_pix_events <= 300)
                mlog("  flash-probe: PIXEL-FLASH #%lu (%s) at swap %lu (proxy frame %lu, t %.0f ms, cam mode %lu): ref row rgb %.0f %.0f %.0f | row %d%% rgb %.0f %.0f %.0f mad %.1f | row %d%% rgb %.0f %.0f %.0f mad %.1f | terrain vertices %lu",
                     (unsigned long)g_fp_pix_events, white ? "white" : "sky", (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(),
                     (unsigned long)*(volatile DWORD *)(DWORD_PTR)NA(0x004c2728), r[0], r[1], r[2], g_fp_rows[1], a[0], a[1], a[2], ma, g_fp_rows[2], b[0], b[1], b[2], mb,
                     (unsigned long)g_fp_prev_v);
            if (g_fp_dumps < 12) fp_dump_named("pix");
        }
        g_fp_prev_flag = flag;
        if (da + db > g_fp_win_maxlow) g_fp_win_maxlow = da + db;
    }
}
static void fp_window(void) {                          /* every 600 swaps, from tc_Swap */
    mlog("  flash-probe: swaps %lu: last 600: %lu main scenes, terrain vertices min %lu, %lu zero-terrain scenes, %lu drops < 30 %%, %lu pixel flashes | totals %lu terrain events (%lu zero), %lu pixel flashes | cam-ground lifts %lu (%lu refused)",
         (unsigned long)g_tc_swaps, (unsigned long)g_fp_scenes, (unsigned long)(g_fp_win_vmin == 0xffffffff ? 0 : g_fp_win_vmin), (unsigned long)g_fp_win_zero,
         (unsigned long)g_fp_win_drop, (unsigned long)g_fp_win_pix, (unsigned long)g_fp_events, (unsigned long)g_fp_zero, (unsigned long)g_fp_pix_events, (unsigned long)g_cg_lifts, (unsigned long)g_cg_fail);
    g_fp_scenes = 0; g_fp_win_vmin = 0xffffffff; g_fp_win_zero = g_fp_win_drop = g_fp_win_pix = 0; g_fp_win_maxlow = 0;
}
static void fp_log_download(DWORD addr, tc_texinfo_t *i, DWORD bytes, DWORD *sp) {
    DWORD ra[3] = { 0, 0, 0 }; int k = 0, j;
    if (!((g_tc_swaps >= 1800 && g_tc_swaps < 1803) || (g_tc_swaps >= 7200 && g_tc_swaps < 7203))) return;
    for (j = 0; j < 400 && k < 3; j++) { DWORD d = sp[j]; if (d >= 0x00401000 && d < 0x004bb000) ra[k++] = d; }
    mlog("  flash-probe: download at swap %lu: addr 0x%lx, %lu B, lod %d..%d, aspect %d, format %d; exe returns %08lx %08lx %08lx",
         (unsigned long)g_tc_swaps, (unsigned long)addr, (unsigned long)bytes, i ? i->smallLod : -1, i ? i->largeLod : -1, i ? i->aspect : -1,
         i ? i->format : -1, (unsigned long)ra[0], (unsigned long)ra[1], (unsigned long)ra[2]);
}

/* ===========================================================================
 * TERRAIN DRAW CENSUS  (I76_DRAW_PROBE=1, with I76_FRAME_SPIKES; off by default; lab docs/TERRAIN-DROPOUT-HILL-2026-10-12.md)
 * ===========================================================================
 * The owner's cockpit-only terrain drop-out on the T05 descent happened while I76_FLASH_PROBE saw normal terrain VERTEX
 * counts every scene. That counter [0x6442ec] is the quadtree's vertex count; it says nothing about the polygons after
 * it. This counts every later stage, per swap, for the main camera 0x4c2730 apart from the others (mirror):
 *   emit   the textured terrain emitter 0x4924b0 calls the mode's clip function [0x4f9538 + mode*4] at 0x4925a8
 *          (wrapped): polygons offered; clip0 = the clip returned 0 vertices (the polygon is dropped before queueing);
 *   insert the bucket insert 0x48fe10 at 0x4925bc (wrapped; its silent refusals replayed from 0x48fe17..0x48fe76):
 *          lowz = sort z below the bucket floor [0x6543ac], far = bucket > 4096, big = more than 32 vertices,
 *          ins = accepted;
 *   drawn  the hardware flush's polygon draw 0x4260d0 at 0x48fb7e (wrapped): polygons handed over for this camera,
 *          and those with a terrain texture (the handles the emitter used, [0x59c558]);
 *   tris   ZGLIDE's grDrawTriangle calls in the swap (all passes, HUD included); lfb = its grLfbLock calls.
 * A swap whose main-camera terrain draws fall under 30 % of the previous swap's (previous >= 200) is logged as
 * TERRAIN-LOSS with every stage, so the stage that lost the terrain is named; a swap whose triangles fall under 50 %
 * with terrain draws normal is TRIANGLE-LOSS. If the owner sees the ground vanish and neither fires, the polygons
 * reached Glide: the loss is in the presentation (dgVoodoo), not in the game. Summary every 600 swaps. Counting only. */
static int g_dp_on;
static DWORD g_dp_emit[2], g_dp_clip0[2], g_dp_ins[2], g_dp_lowz[2], g_dp_far[2], g_dp_big[2], g_dp_draw[2], g_dp_tdraw[2];
static DWORD g_dp_tris, g_dp_lfb, g_dp_prev_tdraw, g_dp_prev_tris, g_dp_loss, g_dp_tloss;
static DWORD g_dp_win_min_tdraw = 0xffffffff, g_dp_win_min_tris = 0xffffffff, g_dp_win_lfb, g_dp_win_clip0, g_dp_win_lowz, g_dp_win_far;
static DWORD g_dp_ttex[16]; static int g_dp_nttex;
static float g_dp_zmin_seen, g_dp_span_seen;
static void (__stdcall *p_dp_DrawTriangle)(const void *, const void *, const void *);
static int (__stdcall *p_dp_LfbLock)(int, int, int, int, int, void *);
static void __stdcall dp_DrawTriangle(const void *a, const void *b, const void *c) { g_dp_tris++; p_dp_DrawTriangle(a, b, c); }
static int __stdcall dp_LfbLock(int t, int buf, int wm, int org, int pp, void *info) { g_dp_lfb++; return p_dp_LfbLock(t, buf, wm, org, pp, info); }
static int dp_cam(const void *cam) { return cam == (const void *)0x004c2730 ? 0 : 1; }
static int __cdecl dp_clip_wrap(void *cam, void *vin, void *vout, int n, DWORD mode) {
    int (__cdecl *fn)(void *, void *, void *, int, DWORD) = *(int (__cdecl **)(void *, void *, void *, int, DWORD))(0x004f9538 + mode * 4);
    int r = fn(cam, vin, vout, n, mode), k = dp_cam(cam), i;
    DWORD tex = *(volatile DWORD *)0x0059c558;
    g_dp_emit[k]++; if (r == 0) g_dp_clip0[k]++;
    for (i = 0; i < g_dp_nttex && g_dp_ttex[i] != tex; i++) {}
    if (i == g_dp_nttex && g_dp_nttex < 16 && tex) g_dp_ttex[g_dp_nttex++] = tex;
    return r;
}
static void *__cdecl dp_insert_wrap(float z) {
    BYTE *rec = *(BYTE **)0x006543c0; int k = dp_cam(*(void **)0x006442d4);
    float zmin = *(volatile float *)0x006543ac;
    if (k == 0) { g_dp_zmin_seen = zmin; g_dp_span_seen = *(volatile float *)0x006543a4; }
    if (z < zmin) g_dp_lowz[k]++;
    else if ((double)z - (double)zmin > 4096.5) g_dp_far[k]++;
    else if (rec && *(int *)rec > 0x20) g_dp_big[k]++;
    else g_dp_ins[k]++;
    return ((void *(__cdecl *)(float))0x0048fe10)(z);
}
static void *__cdecl dp_draw_wrap(void *cam, void *v, int n, DWORD tex, DWORD mode) {
    int k = dp_cam(cam), i;
    g_dp_draw[k]++;
    for (i = 0; i < g_dp_nttex; i++) if (g_dp_ttex[i] == tex) { g_dp_tdraw[k]++; break; }
    return ((void *(__cdecl *)(void *, void *, int, DWORD, DWORD))0x004260d0)(cam, v, n, tex, mode);
}
static void dp_swap(void) {                 /* from tc_Swap, before the present: this swap's census */
    int inm = *(volatile DWORD *)0x004c2164 == 5, j;
    DWORD mode = *(volatile DWORD *)0x004c2728;
    if (inm && g_dp_emit[0]) {
        if (g_dp_tdraw[0] < g_dp_win_min_tdraw) g_dp_win_min_tdraw = g_dp_tdraw[0];
        if (g_dp_tris < g_dp_win_min_tris) g_dp_win_min_tris = g_dp_tris;
    }
    g_dp_win_lfb += g_dp_lfb; g_dp_win_clip0 += g_dp_clip0[0]; g_dp_win_lowz += g_dp_lowz[0]; g_dp_win_far += g_dp_far[0];
    if (inm && g_dp_prev_tdraw >= 200 && g_dp_tdraw[0] * 10 < g_dp_prev_tdraw * 3) {
        g_dp_loss++;
        if (g_dp_loss <= 100)
            mlog("  draw-probe: TERRAIN-LOSS #%lu at swap %lu (proxy frame %lu, t %.0f ms, cam mode %lu): main terrain polygons emitted %lu, clipped away %lu, below the bucket floor %lu (floor %.1f, span %.1f), past bucket 4096 %lu, > 32 vertices %lu, queued %lu, drawn %lu (previous swap %lu); all polygons drawn %lu | other cameras: emitted %lu queued %lu drawn %lu | triangles %lu (previous %lu), LFB locks %lu | terrain vertices %lu",
                 (unsigned long)g_dp_loss, (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)mode,
                 (unsigned long)g_dp_emit[0], (unsigned long)g_dp_clip0[0], (unsigned long)g_dp_lowz[0], g_dp_zmin_seen, g_dp_span_seen,
                 (unsigned long)g_dp_far[0], (unsigned long)g_dp_big[0], (unsigned long)g_dp_ins[0], (unsigned long)g_dp_tdraw[0],
                 (unsigned long)g_dp_prev_tdraw, (unsigned long)g_dp_draw[0], (unsigned long)g_dp_emit[1], (unsigned long)g_dp_ins[1],
                 (unsigned long)g_dp_draw[1], (unsigned long)g_dp_tris, (unsigned long)g_dp_prev_tris, (unsigned long)g_dp_lfb,
                 (unsigned long)*(volatile DWORD *)0x006442ec);
    } else if (inm && g_dp_prev_tris >= 2000 && g_dp_tris * 2 < g_dp_prev_tris && g_dp_tdraw[0] * 10 >= g_dp_prev_tdraw * 7) {
        g_dp_tloss++;
        if (g_dp_tloss <= 100)
            mlog("  draw-probe: TRIANGLE-LOSS #%lu at swap %lu (proxy frame %lu, t %.0f ms, cam mode %lu): triangles %lu (previous %lu) with main terrain polygons drawn %lu (previous %lu), LFB locks %lu",
                 (unsigned long)g_dp_tloss, (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)mode,
                 (unsigned long)g_dp_tris, (unsigned long)g_dp_prev_tris, (unsigned long)g_dp_tdraw[0], (unsigned long)g_dp_prev_tdraw, (unsigned long)g_dp_lfb);
    }
    g_dp_prev_tdraw = inm ? g_dp_tdraw[0] : 0; g_dp_prev_tris = inm ? g_dp_tris : 0;
    for (j = 0; j < 2; j++) g_dp_emit[j] = g_dp_clip0[j] = g_dp_ins[j] = g_dp_lowz[j] = g_dp_far[j] = g_dp_big[j] = g_dp_draw[j] = g_dp_tdraw[j] = 0;
    g_dp_tris = g_dp_lfb = 0;
    if (g_tc_swaps % 600 == 0) {
        mlog("  draw-probe: swaps %lu: last 600: main terrain polygons drawn min %lu, triangles min %lu, LFB locks %lu, main terrain clipped away %lu, below the floor %lu, past 4096 %lu | totals %lu terrain losses, %lu triangle losses | %d terrain textures seen",
             (unsigned long)g_tc_swaps, (unsigned long)(g_dp_win_min_tdraw == 0xffffffff ? 0 : g_dp_win_min_tdraw),
             (unsigned long)(g_dp_win_min_tris == 0xffffffff ? 0 : g_dp_win_min_tris), (unsigned long)g_dp_win_lfb,
             (unsigned long)g_dp_win_clip0, (unsigned long)g_dp_win_lowz, (unsigned long)g_dp_win_far,
             (unsigned long)g_dp_loss, (unsigned long)g_dp_tloss, g_dp_nttex);
        g_dp_win_min_tdraw = g_dp_win_min_tris = 0xffffffff; g_dp_win_lfb = g_dp_win_clip0 = g_dp_win_lowz = g_dp_win_far = 0;
    }
}
/* TERRAIN PASS RECORD  (I76_DRAW_PROBE=2 / 3, lab docs/TERRAIN-DROPOUT-HILL-2026-10-12.md s.9)
 * The census above showed the main camera's terrain polygons falling at the EMIT stage (0x4924b0 offered 113-388
 * instead of ~1000-1500) with the quadtree's vertex count normal. =2 wraps renderer_QueueTerrain 0x490a00 at its main
 * hardware call 0x4020a4 and at the rear mirror's 0x44594e and records each pass: leaves made by the quadtree 0x4911e0
 * ([0x59c56c], counted in 0x491810), nodes it culled against the footprint hull ([0x5a45c0], 0x49179b), edges
 * [0x59c568], vertices [0x6442ec], hull planes [0x6442f0] / 0x644308, root square [0x6442e0..e8], the LOD scales
 * [0x6442c8] / [0x6442cc], polygons offered to the clip in that pass, the FPU control word at entry, whether the mirror
 * pass ran since the previous main pass, and the camera (eye +0x160, far corners +0x178, view rotation +0x40 and
 * position +0x68). A main pass offering < 30 % of the previous main pass's polygons (previous >= 300) is logged as
 * PASS-LOSS with this pass, the previous one and the last mirror pass. =3 also re-runs QueueTerrain once on such a pass
 * and logs what the re-run offered (deterministic in the camera = same count; a transient = a normal count). */
typedef struct {
    DWORD seq, leaves, culled, edges, verts, hulln, emit, clip0, root[3];
    DWORD wl, wfront, wback, wbehind, wnear;            /* the leaf list walked again after the pass (view space) */
    float near_dmin, near_dmax, zmin;
    WORD cw; BYTE mirror_before, valid;
    float lod_c8, lod_cc, rot[9];
    double eye[3], corner[4][3], pos[3], hull[6][3];
    double t_ms;
} dpp_t;
static int g_dpp_level;
static DWORD g_dpp_seq, g_dpp_loss, g_dpp_rerun_ok, g_dpp_mirror_since;
static dpp_t g_dpp_cur, g_dpp_prev, g_dpp_mirror;
static void dpp_fill(dpp_t *p, const BYTE *cam, DWORD emit0, DWORD clip00, int k, WORD cw) {
    int i, j, n = *(volatile int *)0x006442f0;
    p->seq = ++g_dpp_seq; p->t_ms = tc_ms(); p->cw = cw; p->valid = 1;
    p->leaves = *(volatile DWORD *)0x0059c56c; p->culled = *(volatile DWORD *)0x005a45c0; p->edges = *(volatile DWORD *)0x0059c568;
    p->verts = *(volatile DWORD *)0x006442ec; p->hulln = (DWORD)n;
    p->root[0] = *(volatile DWORD *)0x006442e0; p->root[1] = *(volatile DWORD *)0x006442e4; p->root[2] = *(volatile DWORD *)0x006442e8;
    p->lod_c8 = *(volatile float *)0x006442c8; p->lod_cc = *(volatile float *)0x006442cc;
    p->emit = g_dp_emit[k] - emit0; p->clip0 = g_dp_clip0[k] - clip00;
    for (i = 0; i < 3; i++) { p->eye[i] = *(const double *)(cam + 0x160 + 8 * i); p->pos[i] = *(const double *)(cam + 0x68 + 8 * i); }
    for (i = 0; i < 4; i++) for (j = 0; j < 3; j++) p->corner[i][j] = *(const double *)(cam + 0x178 + 0x18 * i + 8 * j);
    for (i = 0; i < 9; i++) p->rot[i] = *(const float *)(cam + 0x40 + 4 * i);
    for (i = 0; i < 6; i++) {                           /* plane i: float a (x) at +0, float c (z) at +8, double d at +0x10 */
        const BYTE *pl = (const BYTE *)0x00644308 + 0x18 * i;
        p->hull[i][0] = i < n ? *(const float *)pl : 0.0; p->hull[i][1] = i < n ? *(const float *)(pl + 8) : 0.0;
        p->hull[i][2] = i < n ? *(const double *)(pl + 0x10) : 0.0;
    }
}
/* After the pass [0x5dd320] holds the vertices in view space (0x4937c0). Walk the leaf list ([0x59c560], next at +8;
 * edges at +0xc/+0x10/+0x14/+0x18, edge = word v0, word v1) and repeat the emit walk's facing test on the leaf's two
 * corner triangles (c0 = e2.v0, c1 = e1.v0, c2 = e3.v1, c3 = e0.v1: the order 0x491a30 collects them in): plane
 * n = (c1 - c0) x (c2 - c0), d = -n.c0 / |n| (the signed distance of the eye from the leaf's plane). wfront / wback =
 * leaves whose first triangle has d < 0 / >= 0 (the walk needs d < 0); wbehind = all four corners at view z < 1;
 * near_dmin / dmax = the range of d over leaves with a corner within 60 m (view z). */
static void dpp_walk(dpp_t *p) {
    const BYTE *leaf = *(BYTE * volatile *)0x0059c560; const float *V = *(float * volatile *)0x005dd320;
    DWORD guard = 0;
    p->wl = p->wfront = p->wback = p->wbehind = p->wnear = 0; p->near_dmin = 1e30f; p->near_dmax = -1e30f; p->zmin = 1e30f;
    if (!V) return;
    while (leaf && guard++ < 200000) {
        const BYTE *e0 = *(BYTE **)(leaf + 0xc), *e1 = *(BYTE **)(leaf + 0x10), *e2 = *(BYTE **)(leaf + 0x14), *e3 = *(BYTE **)(leaf + 0x18);
        const float *c[4]; float u[3], w[3], n[3], len, d, zm; int i;
        if (!e0 || !e1 || !e2 || !e3) break;
        c[0] = V + 3 * *(const short *)e2; c[1] = V + 3 * *(const short *)e1; c[2] = V + 3 * *(const short *)(e3 + 2); c[3] = V + 3 * *(const short *)(e0 + 2);
        for (i = 0; i < 3; i++) { u[i] = c[1][i] - c[0][i]; w[i] = c[2][i] - c[0][i]; }
        n[0] = u[1] * w[2] - u[2] * w[1]; n[1] = u[2] * w[0] - u[0] * w[2]; n[2] = u[0] * w[1] - u[1] * w[0];
        len = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
        d = len > 0.0f ? -(n[0] * c[0][0] + n[1] * c[0][1] + n[2] * c[0][2]) / len : 0.0f;
        p->wl++; if (d < 0.0f) p->wfront++; else p->wback++;
        zm = c[0][2]; for (i = 1; i < 4; i++) if (c[i][2] < zm) zm = c[i][2];
        if (zm < p->zmin) p->zmin = zm;
        if (c[0][2] < 1.0f && c[1][2] < 1.0f && c[2][2] < 1.0f && c[3][2] < 1.0f) p->wbehind++;
        if (zm < 60.0f) { p->wnear++; if (d < p->near_dmin) p->near_dmin = d; if (d > p->near_dmax) p->near_dmax = d; }
        leaf = *(BYTE **)(leaf + 8);
    }
}
static void dpp_log(const char *tag, const dpp_t *p) {
    if (!p->valid) { mlog("    %s: none", tag); return; }
    mlog("    %s: pass %lu t %.0f: leaves %lu, hull-culled nodes %lu, edges %lu, vertices %lu, offered %lu (clip0 %lu), hull %lu planes, root (%ld, %ld, bits %lu), lod %.5g / %.5g, fpu cw %04x, mirror ran before it %d",
         tag, (unsigned long)p->seq, p->t_ms, (unsigned long)p->leaves, (unsigned long)p->culled, (unsigned long)p->edges, (unsigned long)p->verts,
         (unsigned long)p->emit, (unsigned long)p->clip0, (unsigned long)p->hulln, (long)p->root[0], (long)p->root[1], (unsigned long)p->root[2],
         p->lod_c8, p->lod_cc, (unsigned)p->cw, (int)p->mirror_before);
    mlog("    %s: leaf walk: %lu leaves, facing %lu, back-facing %lu, all corners behind %lu; %lu leaves within 60 m, eye-to-plane d %.3f .. %.3f; min view z %.2f",
         tag, (unsigned long)p->wl, (unsigned long)p->wfront, (unsigned long)p->wback, (unsigned long)p->wbehind, (unsigned long)p->wnear,
         p->near_dmin, p->near_dmax, p->zmin);
    mlog("    %s: eye (%.3f %.3f %.3f) pos (%.3f %.3f %.3f) rot [%.4f %.4f %.4f | %.4f %.4f %.4f | %.4f %.4f %.4f]",
         tag, p->eye[0], p->eye[1], p->eye[2], p->pos[0], p->pos[1], p->pos[2],
         p->rot[0], p->rot[1], p->rot[2], p->rot[3], p->rot[4], p->rot[5], p->rot[6], p->rot[7], p->rot[8]);
    mlog("    %s: far corners (%.1f %.1f %.1f) (%.1f %.1f %.1f) (%.1f %.1f %.1f) (%.1f %.1f %.1f); hull a c d: (%.4f %.4f %.2f) (%.4f %.4f %.2f) (%.4f %.4f %.2f) (%.4f %.4f %.2f) (%.4f %.4f %.2f) (%.4f %.4f %.2f)",
         tag, p->corner[0][0], p->corner[0][1], p->corner[0][2], p->corner[1][0], p->corner[1][1], p->corner[1][2],
         p->corner[2][0], p->corner[2][1], p->corner[2][2], p->corner[3][0], p->corner[3][1], p->corner[3][2],
         p->hull[0][0], p->hull[0][1], p->hull[0][2], p->hull[1][0], p->hull[1][1], p->hull[1][2], p->hull[2][0], p->hull[2][1], p->hull[2][2],
         p->hull[3][0], p->hull[3][1], p->hull[3][2], p->hull[4][0], p->hull[4][1], p->hull[4][2], p->hull[5][0], p->hull[5][1], p->hull[5][2]);
}
static WORD dpp_cw(void) { WORD cw; __asm { fnstcw cw } return cw; }
static void __cdecl dpp_qt_mirror(BYTE *cam) {
    DWORD e0 = g_dp_emit[1], c0 = g_dp_clip0[1]; WORD cw = dpp_cw();
    ((void (__cdecl *)(BYTE *))0x00490a00)(cam);
    dpp_fill(&g_dpp_mirror, cam, e0, c0, 1, cw); dpp_walk(&g_dpp_mirror);
    g_dpp_mirror_since = 1;
}
static void __cdecl dpp_qt_main(BYTE *cam) {
    DWORD e0 = g_dp_emit[0], c0 = g_dp_clip0[0]; WORD cw = dpp_cw();
    ((void (__cdecl *)(BYTE *))0x00490a00)(cam);
    dpp_fill(&g_dpp_cur, cam, e0, c0, 0, cw); dpp_walk(&g_dpp_cur);
    g_dpp_cur.mirror_before = (BYTE)g_dpp_mirror_since; g_dpp_mirror_since = 0;
    if (g_dpp_prev.valid && g_dpp_prev.emit >= 300 && g_dpp_cur.emit * 10 < g_dpp_prev.emit * 3 && *(volatile DWORD *)0x004c2164 == 5) {
        g_dpp_loss++;
        if (g_dpp_loss <= 60) {
            mlog("  draw-probe: PASS-LOSS #%lu (swap %lu, cam mode %d): main pass offered %lu polygons, previous main pass %lu",
                 (unsigned long)g_dpp_loss, (unsigned long)g_tc_swaps, *(int *)0x004c2728, (unsigned long)g_dpp_cur.emit, (unsigned long)g_dpp_prev.emit);
            dpp_log("this  ", &g_dpp_cur); dpp_log("prev  ", &g_dpp_prev); dpp_log("mirror", &g_dpp_mirror);
        }
        if (g_dpp_level >= 3) {                          /* experiment: the same camera, once more */
            dpp_t r; DWORD e1 = g_dp_emit[0], c1 = g_dp_clip0[0];
            ((void (__cdecl *)(BYTE *))0x00490a00)(cam);
            dpp_fill(&r, cam, e1, c1, 0, dpp_cw()); dpp_walk(&r);
            if (r.emit * 10 >= g_dpp_prev.emit * 7) g_dpp_rerun_ok++;
            if (g_dpp_loss <= 60) { mlog("    re-run of the same pass offered %lu polygons (re-runs that came back >= 70 %%: %lu of %lu)",
                                         (unsigned long)r.emit, (unsigned long)g_dpp_rerun_ok, (unsigned long)g_dpp_loss); dpp_log("re-run", &r); }
        }
    }
    g_dpp_prev = g_dpp_cur;
}
/* ===========================================================================
 * TERRAIN FOOTPRINT HULL  (I76_TERRAIN_HULL_FIX=1; off by default; lab docs/TERRAIN-DROPOUT-HILL-2026-10-12.md s.10)
 * ===========================================================================
 * The owner's cockpit-only "ground vanishes for a frame" on the T05 descent. The terrain setup 0x4929b0 builds the
 * view's footprint on the ground as the convex hull of five points in sample space (s = [0x6442c4]): the eye and the
 * four far-plane corners (raw x/z, or moved along the eye ray to y = 0 when all four are at or below it). The hull is
 * an angle-sorted gift wrap (0x492da1..0x492f38: fpatan at 0x492eaf, "smallest angle strictly above the previous
 * edge's" at 0x492eee..0x492f08), its edges become side planes in 0x644308 (0x18 each: float a, b, c, pad, double d;
 * inside = a x + c z + d >= 0) with the count in [0x6442f0], and the quadtree 0x4911e0 culls every node with half-size
 * < 32 samples whose bounding circle lies outside one plane (0x49124d..0x4912a0). In some cockpit poses (a near-
 * degenerate point set: each top far corner almost straight above its bottom one, seen from the eye) the wrap drops
 * a hull vertex, the eye among them, and returns a polygon that misses the ground around the car: every near node is
 * culled, the frame keeps only terrain more than 0.5-1.4 km away. Measured with I76_DRAW_PROBE=2/3 (s.9-10): 42
 * collapsed passes in 10 cockpit runs, each one with the eye outside its own hull, a re-run of the same camera
 * collapsing the same way (deterministic), the mirror pass not involved (same rate with it at 10/s).
 * Fix: after a successful setup, rebuild the hull from the same five points with a monotone chain in doubles and write
 * the planes in the exe's format (normals facing the centroid, as 0x493026 does). The same wrapper sits on the setup
 * call 0x490b1e that I76_CAM_GROUND_FIX uses, and chains to it. Passes where the exe's hull left out a point of the
 * true hull by more than half a sample are counted and the first 20 logged ("terrain-hull-fix: event"). */
static int g_hf_on; static DWORD g_hf_events, g_hf_passes, g_hf_skip;
static double hf_cross(const double *o, const double *a, const double *b) {
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}
static void hf_rebuild(BYTE *cam) {
    double s = (double)*(volatile float *)(DWORD_PTR)NA(0x006442c4), P[5][2], H[12][2], ex, ey, ez, cx, cy, cz, gx = 0.0, gz = 0.0, worst = 0.0;
    int i, j, n = 0, k = 0, below = 1, ng = *(volatile int *)(DWORD_PTR)NA(0x006442f0), t;
    BYTE *pl = (BYTE *)(DWORD_PTR)NA(0x00644308);
    ex = *(double *)(cam + 0x160); ey = *(double *)(cam + 0x168); ez = *(double *)(cam + 0x170);
    for (i = 0; i < 4; i++) if (*(double *)(cam + 0x178 + 0x18 * i + 8) > 0.0) below = 0;
    P[n][0] = s * ex; P[n][1] = s * ez; n++;
    for (i = 0; i < 4; i++) {
        cx = *(double *)(cam + 0x178 + 0x18 * i); cy = *(double *)(cam + 0x178 + 0x18 * i + 8); cz = *(double *)(cam + 0x178 + 0x18 * i + 16);
        if (below) {                                   /* the setup's projection branch 0x492b77: onto y = 0 along the eye ray */
            double dn = ey - cy, f;
            if (dn == 0.0) { g_hf_skip++; return; }
            f = cy / dn; cx = cx + f * (cx - ex); cz = cz + f * (cz - ez);
        }
        P[n][0] = s * cx; P[n][1] = s * cz; n++;
    }
    for (i = 0; i < n; i++) if (!(P[i][0] == P[i][0]) || !(P[i][1] == P[i][1]) || P[i][0] > 1e7 || P[i][0] < -1e7 || P[i][1] > 1e7 || P[i][1] < -1e7) { g_hf_skip++; return; }
    for (i = 1; i < n; i++) {                          /* sort by x, then z (5 points: insertion sort) */
        double a = P[i][0], b = P[i][1];
        for (j = i - 1; j >= 0 && (P[j][0] > a || (P[j][0] == a && P[j][1] > b)); j--) { P[j + 1][0] = P[j][0]; P[j + 1][1] = P[j][1]; }
        P[j + 1][0] = a; P[j + 1][1] = b;
    }
    for (i = 0; i < n; i++) {                          /* Andrew's monotone chain, collinear points dropped */
        while (k >= 2 && hf_cross(H[k - 2], H[k - 1], P[i]) <= 1e-9) k--;
        H[k][0] = P[i][0]; H[k][1] = P[i][1]; k++;
    }
    for (i = n - 2, t = k + 1; i >= 0; i--) {
        while (k >= t && hf_cross(H[k - 2], H[k - 1], P[i]) <= 1e-9) k--;
        H[k][0] = P[i][0]; H[k][1] = P[i][1]; k++;
    }
    k--;                                               /* the last point repeats the first */
    if (k < 3 || k > 5) { g_hf_skip++; return; }
    /* did the exe's planes leave out a vertex of the true hull? */
    for (i = 0; i < k; i++) for (j = 0; j < ng && j < 5; j++) {
        const BYTE *q = pl + 0x18 * j;
        double v = *(const float *)q * H[i][0] + *(const float *)(q + 8) * H[i][1] + *(const double *)(q + 0x10);
        if (v < worst) worst = v;
    }
    g_hf_passes++;
    if (worst < -0.5) {
        g_hf_events++;
        if (g_hf_events <= 20)
            mlog("  terrain-hull-fix: event #%lu (camera %s, mode %d): the exe's footprint hull (%d planes) left a hull point %.1f samples outside; rebuilt with %d planes; eye (%.1f %.1f) samples",
                 (unsigned long)g_hf_events, cam == (BYTE *)(DWORD_PTR)NA(0x004c2730) ? "main" : "other", *(int *)(DWORD_PTR)NA(0x004c2728), ng, -worst, k, s * ex, s * ez);
    }
    for (i = 0; i < k; i++) { gx += H[i][0]; gz += H[i][1]; }
    gx /= k; gz /= k;
    for (i = 0; i < k; i++) {
        const double *a = H[i], *b = H[(i + 1) % k];
        double nx = -(b[1] - a[1]), nz = b[0] - a[0], len = sqrt(nx * nx + nz * nz), d;
        BYTE *q = pl + 0x18 * i;
        if (len <= 0.0) { g_hf_skip++; return; }      /* cannot happen after the chain; leave the exe's planes */
        nx /= len; nz /= len; d = -(nx * a[0] + nz * a[1]);
        if (nx * gx + nz * gz + d < 0.0) { nx = -nx; nz = -nz; d = -d; }
        *(float *)q = (float)nx; *(float *)(q + 4) = 0.0f; *(float *)(q + 8) = (float)nz; *(double *)(q + 0x10) = d;
    }
    *(volatile int *)(DWORD_PTR)NA(0x006442f0) = k;
}
static int __cdecl hull_setup_wrap(BYTE *cam) {
    int r = cam_ground_setup_wrap(cam);                /* the original setup, plus the camera-under-ground lift if on */
    if (r && cam) hf_rebuild(cam);
    return r;
}
static void apply_terrain_hull_fix(void) {
    static const BYTE old[5] = { 0xe8, 0x8d, 0x1e, 0x00, 0x00 };   /* call 0x4929b0 at 0x490b1e (stock) */
    BYTE cg[5] = { 0xe8 }, w[5] = { 0xe8 }; LONG rel;
    char v[4]; DWORD n = GetEnvironmentVariableA("I76_TERRAIN_HULL_FIX", v, sizeof(v));
    if (!(n && n < sizeof(v) && v[0] == '1')) return;
    rel = (LONG)((DWORD_PTR)cam_ground_setup_wrap - (0x00490b1e + 5)); memcpy(cg + 1, &rel, 4);
    rel = (LONG)((DWORD_PTR)hull_setup_wrap - (0x00490b1e + 5)); memcpy(w + 1, &rel, 4);
    g_hf_on = patch_bytes(0x00490b1e, site_is(0x00490b1e, cg, 5) ? cg : old, w, 5, "terrain setup call (footprint hull rebuild)");
    mlog("  terrain-hull-fix: %s (QueueTerrain 0x490b1e: after the setup 0x4929b0 the footprint hull 0x644308 / [0x6442f0] is rebuilt from the eye and the four far corners; camera-under-ground lift %s)",
         g_hf_on ? "on" : "NOT applied (bytes differ)", g_cg_on ? "kept (chained)" : "off");
}
static void apply_draw_probe(void) {
    static const BYTE clip_old[7] = { 0xff, 0x14, 0x85, 0x38, 0x95, 0x4f, 0x00 };   /* call [eax*4+0x4f9538] at 0x4925a8 */
    static const BYTE ins_old[5]  = { 0xe8, 0x4f, 0xd8, 0xff, 0xff };               /* call 0x48fe10 at 0x4925bc */
    static const BYTE draw_old[5] = { 0xe8, 0x4d, 0x65, 0xf9, 0xff };               /* call 0x4260d0 at 0x48fb7e */
    BYTE w7[7] = { 0xe8, 0, 0, 0, 0, 0x90, 0x90 }, w5[5] = { 0xe8 }; LONG rel; int k = 0;
    char c[4]; DWORD n = GetEnvironmentVariableA("I76_DRAW_PROBE", c, sizeof(c));
    if (!(n && n < sizeof(c) && c[0] >= '1' && c[0] <= '3')) return;
    g_dpp_level = c[0] - '0';
    rel = (LONG)((DWORD_PTR)dp_clip_wrap - (0x004925a8 + 5)); memcpy(w7 + 1, &rel, 4);
    k += patch_bytes(0x004925a8, clip_old, w7, 7, "draw-probe terrain clip call");
    rel = (LONG)((DWORD_PTR)dp_insert_wrap - (0x004925bc + 5)); memcpy(w5 + 1, &rel, 4);
    k += patch_bytes(0x004925bc, ins_old, w5, 5, "draw-probe terrain insert call");
    rel = (LONG)((DWORD_PTR)dp_draw_wrap - (0x0048fb7e + 5)); memcpy(w5 + 1, &rel, 4);
    k += patch_bytes(0x0048fb7e, draw_old, w5, 5, "draw-probe hardware polygon draw call");
    g_dp_on = (k == 3);
    if (g_dp_on && g_dpp_level >= 2) {          /* I76_DRAW_PROBE=2/3: per-pass record around renderer_QueueTerrain */
        static const BYTE qtm_old[5] = { 0xe8, 0x57, 0xe9, 0x08, 0x00 };          /* call 0x490a00 at 0x4020a4 (main, hardware) */
        static const BYTE qtr_old[5] = { 0xe8, 0xad, 0xb0, 0x04, 0x00 };          /* call 0x490a00 at 0x44594e (rear mirror) */
        int q = 0;
        rel = (LONG)((DWORD_PTR)dpp_qt_main - (0x004020a4 + 5)); memcpy(w5 + 1, &rel, 4);
        q += patch_bytes(0x004020a4, qtm_old, w5, 5, "draw-probe main QueueTerrain call");
        rel = (LONG)((DWORD_PTR)dpp_qt_mirror - (0x0044594e + 5)); memcpy(w5 + 1, &rel, 4);
        q += patch_bytes(0x0044594e, qtr_old, w5, 5, "draw-probe mirror QueueTerrain call");
        mlog("  draw-probe: pass record level %d (%d/2 QueueTerrain calls wrapped: main 0x4020a4, mirror 0x44594e)%s",
             g_dpp_level, q, g_dpp_level >= 3 ? "; a collapsed main pass is re-run once (experiment)" : "");
    }
    mlog("  draw-probe: %s (%d/3 sites: terrain clip 0x4925a8, insert 0x4925bc, hardware draw 0x48fb7e; ZGLIDE grDrawTriangle / grLfbLock counted when ZGLIDE loads)",
         g_dp_on ? "on" : "NOT applied", k);
}

static void __stdcall tc_Swap(int interval) {
    DWORD flag = tc_zg(0x10178ea0), res = tc_zg(0x1001fd20) - g_tc_minaddr;
    double t0;
    if (g_fp_on) fp_before_swap();
    if (g_dp_on) dp_swap();                 /* I76_DRAW_PROBE: this swap's terrain draw census */
    if (g_tc_on == 2) {
        if (g_tc_shot_at && g_tc_swaps + 1 >= g_tc_shot_at) { g_tc_shot_at = 0; tc_dump("flush-back", 1); g_tc_ctl_at = g_tc_swaps + 30; }
        else if (g_tc_ctl_at && g_tc_swaps >= g_tc_ctl_at) { g_tc_ctl_at = 0; tc_dump("ctl-back", 1); }
    }
    g_tc_swaps++;
    {   /* the 2 MB boundary rule (0x10001a95): every time it fires it rewinds next-free to 2 MB and adds 2 to [0x1001f898].
           Under a TMU above 2 MB the second firing (at the 4 MB top) lands next-free on resident textures (2026-10-04) */
        static DWORD last_b = 0xffffffff; DWORD b = tc_zg(0x1001f898);
        if (b != last_b) {
            if (last_b != 0xffffffff)
                mlog("  tex-census: BOUNDARY RULE fired at swap %lu (proxy frame %lu): [0x1001f898] %lu -> %lu, next-free now 0x%lx%s",
                     (unsigned long)g_tc_swaps, (unsigned long)g_frame, (unsigned long)last_b, (unsigned long)b, (unsigned long)tc_zg(0x1001fd20),
                     b > 4 ? " - REWOUND ONTO RESIDENT TEXTURES (2..4 MB still in the slot list: wrong textures follow)" : "");
            last_b = b;
        }
    }
    if (res > g_tc_peak_res && res < 0x10000000) g_tc_peak_res = res;
    if (flag) g_tc_noslot_frames++;
    if (flag && !g_tc_last_flag) {
        g_tc_noslot++; g_tc_win_noslot++;
        mlog("  tex-census: NO-SLOT at swap %lu (proxy frame %lu, t %.0f ms): a texture found no free space and no same-size victim; resident %lu KB, TMU %lu",
             (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)(res / 1024), (unsigned long)tc_zg(0x1001f894));
    }
    g_tc_last_flag = flag;
    if (g_tc_swaps % 600 == 0) {
        mlog("  tex-census: swaps %lu (proxy frame %lu): last 600: %lu downloads %lu KB, %lu flushes, %lu no-slot; resident %lu KB (peak %lu KB), TMU %lu; totals %lu dl, %lu flushes, %lu no-slot (%lu flagged frames)",
             (unsigned long)g_tc_swaps, (unsigned long)g_frame, (unsigned long)g_tc_win_dl, (unsigned long)(g_tc_win_dlb / 1024),
             (unsigned long)g_tc_win_flush, (unsigned long)g_tc_win_noslot, (unsigned long)(res / 1024), (unsigned long)(g_tc_peak_res / 1024),
             (unsigned long)tc_zg(0x1001f894), (unsigned long)g_tc_dl, (unsigned long)g_tc_flush, (unsigned long)g_tc_noslot, (unsigned long)g_tc_noslot_frames);
        g_tc_win_dl = g_tc_win_dlb = g_tc_win_flush = g_tc_win_noslot = 0;
        if (g_fp_on) fp_window();
    }
    if (!g_fs_ms) { p_tc_Swap(interval); return; }
    t0 = tc_ms();
    p_tc_Swap(interval);
    fs_after_swap(t0);
}
static int g_sc_on; static void (__stdcall *p_sc_DrawTriangle)(const void *, const void *, const void *);
static int g_gm_mode; static void glide_mipmap_attach(HMODULE m);   /* terrainpops.c: I76_GLIDE_MIPMAP */
static void __stdcall sc_DrawTriangle(const void *a, const void *b, const void *c);   /* terrainpops.c: I76_SHADE_CENSUS */
static void tex_census_attach(HMODULE m) {
    void *o;
    g_tc_zg = m; g_tc_minc = 0; g_tc_swaps = 0;
    p_tc_CalcMem = (DWORD (__stdcall *)(int, int, int, int))GetProcAddress(GetModuleHandleA("glide2x.dll"), "_grTexCalcMemRequired@16");
#define TC_HOOK(name, hook, ptr) o = patch_iat(m, "glide2x.dll", name, (void *)hook); if (o && o != (void *)hook) *(void **)&ptr = o;
    TC_HOOK("_grTexMaxAddress@4", tc_MaxAddress, p_tc_MaxAddress)
    TC_HOOK("_grTexMinAddress@4", tc_MinAddress, p_tc_MinAddress)
    TC_HOOK("_grTexDownloadMipMap@16", tc_Download, p_tc_Download)
    TC_HOOK("_grBufferSwap@4", tc_Swap, p_tc_Swap)
    if (g_sc_on && !g_dp_on) { TC_HOOK("_grDrawTriangle@12", sc_DrawTriangle, p_sc_DrawTriangle) mlog("  shade-census: ZGLIDE grDrawTriangle %s", p_sc_DrawTriangle ? "hooked" : "NOT hooked"); }
    else if (g_sc_on) mlog("  shade-census: I76_DRAW_PROBE owns grDrawTriangle - census off");
    if (g_dp_on) {
        TC_HOOK("_grDrawTriangle@12", dp_DrawTriangle, p_dp_DrawTriangle)
        TC_HOOK("_grLfbLock@24", dp_LfbLock, p_dp_LfbLock)
        mlog("  draw-probe: ZGLIDE grDrawTriangle %s, grLfbLock %s", p_dp_DrawTriangle ? "hooked" : "NOT hooked", p_dp_LfbLock ? "hooked" : "NOT hooked");
    }
#undef TC_HOOK
    mlog("  tex-census: ZGLIDE at %p: max %s, min %s, download %s, swap %s, calcmem %s; ZGLIDE 0x1a93 = %02x %02x (75 = stock boundary rule, eb = tmufix)",
         (void *)m, p_tc_MaxAddress ? "hooked" : "NOT", p_tc_MinAddress ? "hooked" : "NOT", p_tc_Download ? "hooked" : "NOT",
         p_tc_Swap ? "hooked" : "NOT", p_tc_CalcMem ? "found" : "NOT found", ((BYTE *)m)[0x1a93], ((BYTE *)m)[0x1a94]);
}

#include "cursormap.c"   /* I76_CURSOR_MAP: menu / save-screen pointer on a window bigger than 640x480 (Deck, Mac, no u32x) */
#include "padmenu.c"     /* I76_PAD_MENU: controller moves the menu pointer (shell + Esc menu only; uses cursormap) */
#include "mpmenu.c"      /* I76_MP_MENU: MULTI MELEE HOST / JOIN straight to IPX (1, default) or IPX-only row (2) */
#include "escmenu.c"     /* I76_MENU_PTR: Esc-menu clicks from the exe's own pointer read under DxWnd (the Macs; auto) */
#include "replay.c"      /* I76_REPLAY: frame-dt replay of an emulator memory trace (lab instrument) */
#include "polish.c"      /* I76_SIGN_SOUND_RESTART / I76_FADE_NO_FLIP: owner polish 2026-10-20 (before simtick.c: st_sign_sound uses it) */
#include "simtick.c"     /* I76_SIM_TICK_MS: whole-sim fixed tick, render interpolated (lab experiment) */
#include "skymirror.c"   /* I76_SKY_MIRROR=0: the rear-view mirror's pass does not scroll the sky (opt-in; NITRO-PORT s.11) */
#include "mirrordetail.c" /* I76_MIRROR_DUMP (lab instrument), I76_MIRROR_TERRAIN_MODE: the mirror pass's terrain draw mode (rear-mirror lane 2026-10-23) */
#include "jumpnose.c"    /* I76_JUMP_NOSE=<0.5..1>: the held nose-down pitch rate scaled once at take-off (jump-pitch lane 2026-10-23, TICK-FINISH s.22.6) */
#include "mutesess.c"    /* I76_MUTE=1: the process mutes its own Windows audio session (lab harness; off by default) */
#define NMP_IN_PROXY
#include "nitro_mp.c"     /* Nitro only: ARENA+ ANet 2 layer (nitro-mp-design lane, docs/records/NITRO-MP-DESIGN-2026-10-21.md) */
#include "nitro_ai.c"     /* Nitro only: ARENA+ AI melee on top of it */

/* (I76_GLIDE_DIR, the 2026-10-03 experiment that loaded <game>\<subfolder>\Glide2x.dll before ZGLIDE so the mission
 * would read that folder's dgVoodoo.conf, was removed 2026-10-10: the menus followed the same conf, so it did not keep
 * them 4:3 (lab docs/WIDESCREEN-2D.md, "Live result, route (a)"; docs/records/PROXY-CLEANUP-2026-10-10.md).) */
static int g_zg_tmufix;                     /* I76_ZGLIDE_TMUFIX=1 */
static volatile LONG g_nsw_shell, g_nsw_zglide;   /* Nitro: nitshell / ZGLIDE attach done (hook or nitro_shell_watch) */
static HMODULE WINAPI hook_LoadLibraryA(LPCSTR name) {
    HMODULE m;
    m = p_LoadLibraryA(name);
    if (m && name) {
        const char *b = strrchr(name, '\\'); b = b ? b + 1 : name;
        cursor_map_attach(m, b);
        pad_menu_attach(m, b);    /* after cursor_map_attach: the pad filter chains onto the cursor map's shell slot */
        mp_menu_attach(m, b);     /* I76_MP_MENU: the connection row (code bytes only, no IAT slot) */
        if (g_exe == EXE_NITRO && _stricmp(b, "nitshell.dll") == 0 && InterlockedCompareExchange(&g_nsw_shell, 1, 0) == 0)
            nmp_attach_shell(m);   /* ARENA+ (nitro_mp.c); once, here or from nitro_shell_watch */
        if (_strnicmp(b, "zglide", 6) == 0 && g_zg_tmufix && InterlockedCompareExchange(&g_nsw_zglide, 1, 0) == 0) {
            /* I76_ZGLIDE_TMUFIX=1: ZGLIDE+0x1a93 `jne +0x24` (75 24) -> `jmp +0x24` (eb 24): skip the Voodoo 1 "no texture
               across 2 MB" rule. Its rewind target is the constant 2 MB, and it runs BEFORE the grTexMaxAddress check, so
               under MemorySizeOfTMU 4096 the first allocation that would pass the 4 MB top moves next-free back to 2 MB
               while the textures at 2..4 MB stay in the slot list: later uploads overwrite live textures (the owner's
               "texture exchange" with 4096, promotion 5R). Lab docs/RENDER-FREEZE-2026-10-04.md, TEXTURE-DELIVERY.md s.2. */
            /* Nitro's ZGLIDE (1998-02-28 rebuild, f28fe42b): the same rule at +0x2c9a, `jne +0x26` (read 2026-10-21) */
            DWORD zo = g_exe == EXE_NITRO ? 0x2c9a : 0x1a93; BYTE zj = g_exe == EXE_NITRO ? 0x26 : 0x24;
            BYTE *p = (BYTE *)m + zo; DWORD op;
            if (p[0] == 0x75 && p[1] == zj && VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &op)) {
                p[0] = 0xEB; VirtualProtect(p, 1, op, &op); FlushInstructionCache(GetCurrentProcess(), p, 1);
                mlog("  zglide-tmufix: ZGLIDE+0x%lx 75 %02x -> %02x %02x (2 MB boundary rule skipped)", (unsigned long)zo, zj, p[0], zj);
            } else mlog("  zglide-tmufix: ZGLIDE+0x%lx = %02x %02x, not the stock 75 %02x - not applied", (unsigned long)zo, p[0], p[1], zj);
        }
        if (_strnicmp(b, "zglide", 6) == 0 && (g_tc_on || g_sc_on) && g_exe != EXE_NITRO) tex_census_attach(m);
        if (_strnicmp(b, "zglide", 6) == 0 && g_gm_mode && g_exe != EXE_NITRO) glide_mipmap_attach(m);   /* I76_GLIDE_MIPMAP (terrainpops.c) */   /* census offsets: Gold's ZGLIDE; g_sc_on: I76_SHADE_CENSUS hooks grDrawTriangle there too */
        /* (the census and TMUFIX hook LoadLibraryA too: the refresh wrapper is only for I76_GLIDE_REFRESH / I76_GLIDE_GAMMA) */
        if (_strnicmp(b, "zglide", 6) == 0 && !p_grSstWinOpen && (g_glide_refresh_code != 0xffffffff || g_glide_gamma > 0.0f)) {
            p_grSstWinOpen = (grSstWinOpen_t)patch_iat(m, "glide2x.dll", "_grSstWinOpen@28", hook_grSstWinOpen);
            mlog("  glide-refresh: %s loaded at %p, grSstWinOpen slot %s", b, (void *)m, p_grSstWinOpen ? "repointed" : "NOT found");
        }
    }
    return m;
}

/* Nitro under DxWnd (the Macs; nitro-mac lane 2026-10-21, docs/records/NITRO-MAC-2026-10-21.md): DxWnd takes over
 * nitro.exe's KERNEL32!LoadLibraryA slot after this DllMain, as it does on Gold (mpmenu.c "TWO WAYS IN"), so the hook above
 * never sees NITSHELL.DLL or ZGLIDE.DLL load: no ARENA+ shell hooks (join list, host-form boxes), no ZGLIDE TMU fix
 * (Mac, n 1: "zglide-tmufix: armed" and nothing after). This thread polls both modules every 50 ms and, once one has been
 * resident for 750 ms and the hook has not attached it, attaches it through hook_LoadLibraryA's own code path (a
 * LoadLibraryA of the resident module: refcount + 1, same handle). On the PC the hook gets there first and nothing
 * happens here. Ends when both are done or after 30 min. */
static DWORD WINAPI nitro_shell_watch(LPVOID arg) {
    DWORD t0 = GetTickCount(), seen_s = 0, seen_z = 0;
    (void)arg;
    while (GetTickCount() - t0 < 30u * 60u * 1000u) {
        HMODULE sh = GetModuleHandleA("nitshell.dll"), zg = GetModuleHandleA("zglide.dll");
        int need_z = g_zg_tmufix && !g_nsw_zglide;
        if (g_nsw_shell && !need_z) break;
        if (!g_nsw_shell && sh) {
            if (!seen_s) seen_s = GetTickCount() | 1;
            else if (GetTickCount() - seen_s >= 750) {
                mlog("  nitro shell watch: NITSHELL.DLL resident at %p, not seen through the LoadLibraryA hook - attaching from the watch thread", (void *)sh);
                hook_LoadLibraryA("NITSHELL.DLL");
            }
        }
        if (need_z && zg) {
            if (!seen_z) seen_z = GetTickCount() | 1;
            else if (GetTickCount() - seen_z >= 750) {
                mlog("  nitro shell watch: ZGLIDE.DLL resident at %p, not seen through the LoadLibraryA hook - attaching from the watch thread", (void *)zg);
                hook_LoadLibraryA("ZGLIDE.DLL");
            }
        }
        Sleep(50);
    }
    return 0;
}

static void apply_glide_refresh(void) {
    static const struct { DWORD hz, code; } tab[] = { {60, 0}, {70, 1}, {72, 2}, {75, 3}, {80, 4}, {90, 5}, {100, 6}, {85, 7}, {120, 8}, {0, 0xff} };
    char v[8]; DWORD n; int i;
    {   char c[4]; DWORD k = env_str("I76_TEX_CENSUS", c, sizeof(c));
        if ((k && (c[0] == '1' || c[0] == '2')) || g_fs_ms) {   /* I76_FRAME_SPIKES needs the census hooks */
            g_tc_on = (k && c[0] == '2') ? 2 : 1;
            if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
            if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
            mlog("  tex-census: on, LoadLibraryA %s", p_LoadLibraryA ? "hooked" : "NOT hooked");
        }
    }
    {
        if (env_flag("I76_ZGLIDE_TMUFIX", 4, 0) == 1) {
            g_zg_tmufix = 1;
            if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
            mlog("  zglide-tmufix: armed, LoadLibraryA %s", p_LoadLibraryA ? "hooked" : "NOT hooked");
        }
    }
    {   char gv[16];
        if (env_str("I76_GLIDE_GAMMA", gv, sizeof(gv))) {
            double gd = atof(gv);
            if (gd >= 0.5 && gd <= 3.0) {
                g_glide_gamma = (float)gd;
                if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
                mlog("  glide-gamma: %s armed (applied after each grSstWinOpen); LoadLibraryA %s", gv, p_LoadLibraryA ? "hooked" : "NOT hooked");
            } else mlog("  glide-gamma: %s is outside 0.5..3.0 - not applied", gv);
        }
    }
    n = env_str("I76_GLIDE_REFRESH", v, sizeof(v));
    if (n == 0) return;
    g_glide_refresh_hz = (DWORD)atoi(v);
    for (i = 0; i < (int)(sizeof tab / sizeof tab[0]); i++) if (tab[i].hz == g_glide_refresh_hz) g_glide_refresh_code = tab[i].code;
    {   /* probe knob: I76_GLIDE_REFRESH_CODE=<n> passes a raw GrScreenRefresh_t code (Glide 2.x defines 0..8) */
        char c[8];
        if (env_str("I76_GLIDE_REFRESH_CODE", c, sizeof(c))) g_glide_refresh_code = (DWORD)strtoul(c, NULL, 0);
    }
    if (g_glide_refresh_code == 0xffffffff) { mlog("  glide-refresh: %s is not a Glide refresh (60 70 72 75 80 85 90 100 120, 0 = none) - not applied", v); return; }
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    mlog("  glide-refresh: %lu Hz (code %lu) armed; LoadLibraryA %s", (unsigned long)g_glide_refresh_hz, (unsigned long)g_glide_refresh_code,
         p_LoadLibraryA ? "hooked" : "NOT hooked");
}

/* ===========================================================================
 * TRAINER CONTROL BLOCK  (always on; I76_TRAINER=0 disables)
 * ===========================================================================
 * tools/trainer/i76trn.h is the contract: a 168-byte i76trn_ctl_t (+ the i76trn_ext_t full-state extension after it) in the shared memory Local\I76Trainer that a
 * front end (tools/trainer/i76trainer_gui.py) fills and this proxy applies on the game's own thread at the top of
 * every frame, before simclock_Update, the physics tick and the render. That placement is the point: an external
 * poke (tools/trainer/i76trainer.py) can land inside the render window, where I76_RENDER_INTERP puts the physics
 * pose back, and a hit can register in the same frame as a repair; here the hold runs first.
 *
 *   flags (held every frame)       I76TRN_F_GOD        armour / chassis / components at max, flats cleared, and
 *                                                      options_play_flags 0x18 (entity_ApplyDamage 0x465620 zeroes the
 *                                                      amount for the offline player: cheats.md section 1) forced on
 *                                  I76TRN_F_AMMO       play flag 0x04 forced on + the player's weapon instances' ammo
 *                                                      (0x5aab08 + i x 0x4c, +0x20; instance +0x18 -> vehicle record
 *                                                      whose +0 is the vehicle object) = 0x0fffffff
 *                                  I76TRN_F_NOFLATS    wheel flat flag +0x44 cleared, radius +0x1c / 0.688 (0x46dde1)
 *                                  I76TRN_F_COMPONENTS components at max only
 *                                  I76TRN_F_FREEZE_POS obj+0x40 = pos, velocity and body rates 0
 *   one-shots (req_seq != ack_seq) repair, teleport, ammo, slot ammo, play flags, stop, store state, set state
 *
 * Forced play-flag bits are remembered the first time they are forced and put back when the forcing flag is
 * released, so a session that only used the trainer leaves the Options as they were. Poking the dword does not set
 * the "cheats used" marker 0x535f78 by itself, BUT the game's own options-menu close, player_SaveDef and the
 * post-shell I76PLYR.DEF reload all turn set bits 0x1c into the marker (corrected 2026-10-04; see the CHEAT-MARKER
 * GUARD below, which hides the forced bits from those three paths so a mission won with God / Ammo held still counts).
 * The whole apply runs under SEH like the telemetry snapshot: between missions the player chain is stale, and a
 * fault must cost one frame of trainer service, never the game. */
static HANDLE g_trn_map;
static DWORD g_trn_forcing, g_trn_play_saved;

static void trn_msg(const char *s) { lstrcpynA(g_trn->msg, s, sizeof g_trn->msg); }

/* components at max: engine / suspension / brakes (slots 7..9), the six wheels, anything else that carries a
 * known class type; weapon instances (type 50) are held through the instance table below */
static void trn_components(BYTE *ent, int only_flats) {
    int i;
    for (i = 0; i < 24; i++) {
        BYTE *o = *(BYTE **)(ent + 0x3a8 + 4 * i), *c;
        int type, ho = -1, mo = -1;
        if (!o) continue;
        type = *(int *)(o + 0x6c); c = *(BYTE **)(o + 0x70);
        if (!c) continue;
        if (type == 30) {                                     /* wheel: hp +4 / max +8, flat +0x44, radius +0x1c */
            if (*(DWORD *)(c + 0x44)) { *(float *)(c + 0x1c) = *(float *)(c + 0x1c) / 0.688f; *(DWORD *)(c + 0x44) = 0; }
            if (only_flats) continue;
            ho = 4; mo = 8;
        } else if (only_flats) continue;
        else if (type == 20 || type == 21 || type == 23) { ho = 0; mo = 4; }
        else if (type == 22) { ho = 4; mo = 8; }
        else if (type == 24) { ho = 8; mo = 0xc; }
        if (ho < 0) continue;
        if (*(int *)(c + mo) > 0 && *(int *)(c + ho) != *(int *)(c + mo)) *(int *)(c + ho) = *(int *)(c + mo);
    }
}

static void trn_repair(BYTE *ent) {
    int s;
    for (s = 0; s < 4; s++) {
        int am = *(int *)(ent + 0x158 + 4 * s), cm = *(int *)(ent + 0x168 + 4 * s);
        *(int *)(ent + 0x138 + 4 * s) = am; *(int *)(ent + 0x178 + 4 * s) = am;
        *(int *)(ent + 0x148 + 4 * s) = cm; *(int *)(ent + 0x18c + 4 * s) = cm;
    }
    trn_components(ent, 0);
}

/* the player's weapon instances: ammo = value (value < 0: leave), hp to max when hp_max is set */
static int trn_weapons(BYTE *obj, int ammo, int hp_max) {
    int n = *(int *)(DWORD_PTR)NA(0x005da750), i, hit = 0;
    if (n > 150) n = 150;
    for (i = 0; i < n; i++) {
        BYTE *inst = (BYTE *)(DWORD_PTR)NA(0x005aab08) + i * 0x4c, *vrec = *(BYTE **)(inst + 0x18);
        if (!*(DWORD *)(inst + 4) || !vrec || *(BYTE **)vrec != obj) continue;
        if (ammo >= 0) *(int *)(inst + 0x20) = ammo;
        if (hp_max && *(int *)(inst + 0x14) > 0) *(int *)(inst + 0xc) = *(int *)(inst + 0x14);
        hit++;
    }
    return hit;
}

/* FULL CAR STATE (2026-10-20, owner: "the teleport ... should also teleport 6 axis position and speed when stored").
 * i76trn_ext_t follows the 168-byte block in the same mapping (i76trn.h). STORE copies, on the game thread at the top of
 * the frame (before the tick), everything the vehicle step carries from one step to the next (i76-map physics.md, the
 * veh+ / w+ table): pose (obj+0x18 rows, obj+0x40 position), motion (velocity, |v|, 1/|v|, body rates, last acceleration),
 * contact (airborne / skid / latched bits, surface, probe normal, ground g, clearance, fall-kill reference), the wheels'
 * suspension and spin history, and the engine's gear / power / rpm. SET_STATE writes it back and reads it back.
 * Not carried: the camera, AI, scripts, damage, ammo, the input. A restore onto a car of another mass skips the wheels
 * and the engine (another car's suspension history would be nonsense). Under the sim tick the restored pose differs from
 * the recorded interpolation end, so wst_swap_in draws it as written (an outside write), as it already does a teleport. */
static i76trn_ext_t *g_trn_ext;
static DWORD g_trn_hk_prev;

static BYTE *trn_wheel(BYTE *ent, int i, BYTE **wd) {
    BYTE *o = *(BYTE **)(ent + 0x3a8 + 4 * i);
    if (!o || *(int *)(o + 0x6c) != 30 || !*(BYTE **)(o + 0x70)) return 0;
    *wd = *(BYTE **)(o + 0x70);
    return o;
}

static void trn_capture(BYTE *obj, BYTE *ent, i76trn_state_t *s) {
    BYTE *eng, *o, *w;
    int i;
    memset(s, 0, sizeof *s);
    s->frame = g_frame; s->sim_frame = *(volatile DWORD *)(DWORD_PTR)NA(0x005a7e1c);
    s->mass = *(float *)(ent + 0xa4);
    memcpy(s->rot, obj + 0x18, 36); memcpy(s->pos, obj + 0x40, 24);
    memcpy(s->vel, ent + 0xbc, 12); s->speed = *(float *)(ent + 0xac); s->inv_speed = *(float *)(ent + 0xb0);
    memcpy(s->rates, ent + 0xc8, 12); memcpy(s->accel, ent + 0xd4, 12);
    s->ent_flags = *(DWORD *)(ent + EF(0x454)) & I76TRN_ST_FLAG_MASK; s->surface = *(DWORD *)(ent + EF(0x45c));
    memcpy(s->ground_normal, ent + EF(0x460), 12);
    s->ground_g = *(float *)(ent + EF(0x46c)); s->clearance = *(float *)(ent + EF(0x470)); s->last_ground_y = *(float *)(ent + EF(0x474));
    s->parts = I76TRN_ST_POSE | I76TRN_ST_MOTION | I76TRN_ST_CONTACT;
    for (i = 0; i < 6; i++) {
        i76trn_wheel_state_t *ws = &s->wheel[i];
        if ((o = trn_wheel(ent, i, &w)) == 0) continue;
        ws->present = 1;
        ws->ground_speed = *(float *)(w + 0x20); ws->susp_offset = *(float *)(w + 0x24); ws->ground_height = *(float *)(w + 0x2c);
        ws->prev_bump = *(float *)(w + 0x30); ws->prev_dbump = *(float *)(w + 0x34); ws->unloaded = *(DWORD *)(w + 0x40);
        memcpy(ws->iir, w + 0x58, 40); memcpy(&ws->local_y, o + 0x48, 8);
        s->wheel_mask |= 1u << i;
    }
    if (s->wheel_mask) s->parts |= I76TRN_ST_WHEELS;
    if ((eng = tel_comp(ent, 7, 21)) != 0) {
        s->gear = *(int *)(eng + 0x08); s->drive_power = *(float *)(eng + 0x10); s->rpm = *(float *)(eng + 0x1c); s->speedo = *(float *)(eng + 0x24);
        s->parts |= I76TRN_ST_ENGINE;
    }
    s->valid = 1;
}

#define TRN_PUT(dst, src, n) do { memcpy((dst), (src), (n)); if (memcmp((dst), (src), (n))) bad++; } while (0)
/* returns the parts restored; *bad_out = fields that did not read back as written */
static DWORD trn_restore(BYTE *obj, BYTE *ent, const i76trn_state_t *s, DWORD parts, DWORD *bad_out) {
    BYTE *eng, *o, *w;
    DWORD bad = 0, fl;
    float dm;
    int i;
    if (!s->valid) { *bad_out = 0; return 0; }
    parts = (parts ? parts : I76TRN_ST_ALL) & s->parts;
    dm = *(float *)(ent + 0xa4) - s->mass;
    if (dm > 0.5f || dm < -0.5f) parts &= ~(DWORD)(I76TRN_ST_WHEELS | I76TRN_ST_ENGINE);
    if (parts & I76TRN_ST_POSE) { TRN_PUT(obj + 0x18, s->rot, 36); TRN_PUT(obj + 0x40, s->pos, 24); }
    if (parts & I76TRN_ST_MOTION) {
        TRN_PUT(ent + 0xbc, s->vel, 12); TRN_PUT(ent + 0xac, &s->speed, 4); TRN_PUT(ent + 0xb0, &s->inv_speed, 4);
        TRN_PUT(ent + 0xc8, s->rates, 12); TRN_PUT(ent + 0xd4, s->accel, 12);
    }
    if (parts & I76TRN_ST_CONTACT) {
        fl = (*(DWORD *)(ent + EF(0x454)) & ~I76TRN_ST_FLAG_MASK) | (s->ent_flags & I76TRN_ST_FLAG_MASK);
        TRN_PUT(ent + EF(0x454), &fl, 4); TRN_PUT(ent + EF(0x45c), &s->surface, 4); TRN_PUT(ent + EF(0x460), s->ground_normal, 12);
        TRN_PUT(ent + EF(0x46c), &s->ground_g, 4); TRN_PUT(ent + EF(0x470), &s->clearance, 4); TRN_PUT(ent + EF(0x474), &s->last_ground_y, 4);
    }
    if (parts & I76TRN_ST_WHEELS) {
        for (i = 0; i < 6; i++) {
            const i76trn_wheel_state_t *ws = &s->wheel[i];
            if (!(s->wheel_mask & (1u << i)) || (o = trn_wheel(ent, i, &w)) == 0) continue;
            TRN_PUT(w + 0x20, &ws->ground_speed, 4); TRN_PUT(w + 0x24, &ws->susp_offset, 4); TRN_PUT(w + 0x2c, &ws->ground_height, 4);
            TRN_PUT(w + 0x30, &ws->prev_bump, 4); TRN_PUT(w + 0x34, &ws->prev_dbump, 4); TRN_PUT(w + 0x40, &ws->unloaded, 4);
            TRN_PUT(w + 0x58, ws->iir, 40); TRN_PUT(o + 0x48, &ws->local_y, 8);
        }
    }
    if ((parts & I76TRN_ST_ENGINE) && (eng = tel_comp(ent, 7, 21)) != 0) {
        TRN_PUT(eng + 0x08, &s->gear, 4); TRN_PUT(eng + 0x10, &s->drive_power, 4); TRN_PUT(eng + 0x1c, &s->rpm, 4); TRN_PUT(eng + 0x24, &s->speedo, 4);
    }
    *bad_out = bad;
    return parts;
}
#undef TRN_PUT

static void trn_do_store(BYTE *obj, BYTE *ent, const char *by) {
    i76trn_ext_t *x = g_trn_ext;
    char b[64];
    trn_capture(obj, ent, &x->stored);
    x->target = x->stored;
    x->store_seq++;
    wsprintfA(b, "%s: stored (%d, %d, %d) %d km/h", by, (int)x->stored.pos[0], (int)x->stored.pos[1], (int)x->stored.pos[2],
              (int)(x->stored.speed * 3.6f));
    trn_msg(b);
}

static int trn_do_restore(BYTE *obj, BYTE *ent, const char *by) {
    i76trn_ext_t *x = g_trn_ext;
    DWORD bad = 0, parts;
    char b[64];
    if (!x->target.valid) { trn_msg("restore: nothing stored"); return 0; }
    parts = trn_restore(obj, ent, &x->target, x->restore_parts, &bad);
    x->readback_bad = bad; x->restore_frame = g_frame; x->restore_seq++;
    wsprintfA(b, "%s: restored parts 0x%02x%s%s", by, (unsigned)parts,
              ((parts & I76TRN_ST_WHEELS) || !(x->target.parts & I76TRN_ST_WHEELS)) ? "" : " (other car: no wheels/engine)",
              bad ? " READBACK MISMATCH" : "");
    trn_msg(b);
    return 1;
}

static int trn_game_focused(void) {
    HWND f = GetForegroundWindow();
    DWORD pid = 0;
    if (!f) return 0;
    GetWindowThreadProcessId(f, &pid);
    return pid == GetCurrentProcessId();
}

static void trn_apply_inner(void) {
    i76trn_ctl_t *c = g_trn;
    volatile DWORD *play = (volatile DWORD *)(DWORD_PTR)NA(0x00654b98);
    BYTE *ent = 0, *obj;
    DWORD fl = c->flags, force, applied = 0;
    c->heartbeat = g_frame;
    /* play-flag forcing, with restore: the baseline is captured the first time any bit is forced, and a bit that
     * stops being forced goes back to its baseline value */
    force = ((fl & I76TRN_F_GOD) ? 0x18u : 0u) | ((fl & I76TRN_F_AMMO) ? 0x04u : 0u);
    if (force != g_trn_forcing) {
        DWORD released = g_trn_forcing & ~force;
        if (!g_trn_forcing) { g_trn_play_saved = *play; c->play_flags_saved = g_trn_play_saved; }
        if (released) *play = (*play & ~released) | (g_trn_play_saved & released);
        g_trn_forcing = force;
    }
    if (force) *play |= force;
    c->play_flags_now = *play;

    obj = tel_player(&ent);
    c->player_present = obj != 0;
    if (obj) {
        if (fl & I76TRN_F_GOD) { trn_repair(ent); trn_weapons(obj, -1, 1); applied |= I76TRN_F_GOD; }
        if (fl & I76TRN_F_COMPONENTS) { trn_components(ent, 0); trn_weapons(obj, -1, 1); applied |= I76TRN_F_COMPONENTS; }
        if (fl & I76TRN_F_NOFLATS) { trn_components(ent, 1); applied |= I76TRN_F_NOFLATS; }
        if (fl & I76TRN_F_AMMO) { trn_weapons(obj, 0x0fffffff, 0); applied |= I76TRN_F_AMMO; }
        if (fl & I76TRN_F_FREEZE_POS) {
            memcpy(obj + 0x40, c->pos, 24); memset(ent + 0xbc, 0, 12); memset(ent + 0xc8, 0, 12);
            applied |= I76TRN_F_FREEZE_POS;
        }
    }
    if (g_trn_ext && (g_trn_ext->hotkeys & I76TRN_HK_ON)) {   /* Ctrl+9 store, Ctrl+0 restore, game window focused, edge-triggered */
        DWORD now = 0;
        if (trn_game_focused() && (GetAsyncKeyState(VK_CONTROL) & 0x8000)) {
            if (GetAsyncKeyState('9') & 0x8000) now |= 1;
            if (GetAsyncKeyState('0') & 0x8000) now |= 2;
        }
        if (obj && (now & 1) && !(g_trn_hk_prev & 1)) { trn_do_store(obj, ent, "Ctrl+9"); g_trn_ext->hotkey_stores++; }
        if (obj && (now & 2) && !(g_trn_hk_prev & 2) && trn_do_restore(obj, ent, "Ctrl+0")) g_trn_ext->hotkey_restores++;
        g_trn_hk_prev = now;
    }
    if (c->req_seq != c->ack_seq) {
        DWORD cmd = c->cmd;
        c->cmd_result = 0;
        if (cmd == I76TRN_CMD_PLAYFLAGS) {
            *play = (*play & ~c->play_clear) | c->play_set;
            g_trn_play_saved = (g_trn_play_saved & ~c->play_clear) | c->play_set;   /* the user's new baseline */
            c->play_flags_now = *play; trn_msg("play flags set");
        } else if (!obj) { c->cmd_result = 1; trn_msg("no player vehicle (not in a mission?)"); }
        else switch (cmd) {
        case I76TRN_CMD_REPAIR:   trn_repair(ent); trn_weapons(obj, -1, 1); trn_msg("repaired"); break;
        case I76TRN_CMD_TELEPORT: {
            /* 2026-10-14 (box-spec harness): the speed +0xac (and 1/speed +0xb0) too. In grip the physics snaps the velocity
             * to forward x the speed it kept from the last step (i76-map physics.md "Grip vs slide"), so a velocity written
             * alone was thrown away whenever the car had been slow (the "velocity writes do not stick" of capture 014). */
            float sp = (float)sqrt((double)c->vel[0] * c->vel[0] + (double)c->vel[1] * c->vel[1] + (double)c->vel[2] * c->vel[2]);
            memcpy(obj + 0x40, c->pos, 24); memcpy(ent + 0xbc, c->vel, 12); memset(ent + 0xc8, 0, 12);
            *(float *)(ent + 0xac) = sp; *(float *)(ent + 0xb0) = sp > 0.001f ? 1.0f / sp : 0.0f;
            trn_msg("teleported"); break; }
        case I76TRN_CMD_AMMO:     { char b[64]; wsprintfA(b, "ammo set on %d weapons", trn_weapons(obj, c->ammo_value, 0)); trn_msg(b); } break;
        case I76TRN_CMD_SLOT_AMMO: {
            int n = *(int *)(DWORD_PTR)NA(0x005da750), i = c->slot_index;
            BYTE *inst = (BYTE *)(DWORD_PTR)NA(0x005aab08) + i * 0x4c;
            if (i < 0 || i >= n || i >= 150 || !*(DWORD *)(inst + 4)) { c->cmd_result = 3; trn_msg("bad weapon slot"); }
            else { *(int *)(inst + 0x20) = c->ammo_value; trn_msg("slot ammo set"); }
            break; }
        case I76TRN_CMD_STORE_STATE:
            if (!g_trn_ext) { c->cmd_result = 2; trn_msg("unknown command (no state extension)"); break; }
            trn_do_store(obj, ent, "store"); break;
        case I76TRN_CMD_SET_STATE:
            if (!g_trn_ext) { c->cmd_result = 2; trn_msg("unknown command (no state extension)"); break; }
            if (!trn_do_restore(obj, ent, "restore")) c->cmd_result = 4;
            break;
        case I76TRN_CMD_STOP:     memset(ent + 0xbc, 0, 12); memset(ent + 0xc8, 0, 12); *(float *)(ent + 0xac) = 0.0f; *(float *)(ent + 0xb0) = 0.0f;
                                  trn_msg("stopped"); break;
        default:                  c->cmd_result = 2; trn_msg("unknown command"); break;
        }
        c->ack_seq = c->req_seq;
    }
    c->applied = applied;
}

static void trn_frame(void) {
    if (!g_trn || g_trn->magic != I76TRN_MAGIC) return;
#ifdef _MSC_VER
    __try { trn_apply_inner(); }
    __except (EXCEPTION_EXECUTE_HANDLER) { g_trn->faults++; }
#else
    trn_apply_inner();
#endif
}

/* CHEAT-MARKER GUARD (2026-10-04, owner report "the trainer stops the campaign advancing"). Static reading of
 * md5 9a232dcc, the same bytes in AiO 6319abf7: the forced play bits above DID reach the cheats-used marker, through
 * the game's own code, not through a poke:
 *   - the in-mission options menu's close 0x495170 (Esc in a mission, or its close callback) writes I76PLYR.DEF from
 *     0x654b40 and sets 0x535f78 = 1 when 0x654b98 & 0x1c (0x495226);
 *   - player_SaveDef 0x497290 (mission end 0x4040f7, graphics-mode key 0x44e3a1) writes the forced bits to I76PLYR.DEF;
 *   - after every shell return 0x4970f0 reads I76PLYR.DEF back and sets the marker when the bits are there (0x497241).
 * Nothing but 'Turn off Cheater Options' (0x4976a0) clears the marker, so from then on every win in that game
 * process becomes outcome 0xb (no salvage, no vehscn.vsf, no scene advance), with or without the trainer.
 * The guard: those three call paths are redirected through wrappers that put the forced bits back to the user's
 * baseline before the game's code runs (the frame hook re-forces them on the next frame). Bits the user SET as a new
 * baseline (CMD_PLAYFLAGS) are not hidden: that is the Options switch itself, and the GUI warns about it. */
static void trn_unforce(void) {
    volatile DWORD *play = (volatile DWORD *)(DWORD_PTR)NA(0x00654b98);
    if (g_trn_forcing) *play = (*play & ~g_trn_forcing) | (g_trn_play_saved & g_trn_forcing);
}
static void trn_reforce(void) {
    if (g_trn && g_trn->magic == I76TRN_MAGIC && g_trn_forcing) *(volatile DWORD *)(DWORD_PTR)NA(0x00654b98) |= g_trn_forcing;
}
static DWORD g_trn_guard_hits;
static void __cdecl trn_savedef_wrap(void) {               /* player_SaveDef 0x497290: no args, result unused */
    trn_unforce(); g_trn_guard_hits++;
    ((void (__cdecl *)(void))(DWORD_PTR)NA(0x00497290))();
    if (*(volatile DWORD *)(DWORD_PTR)NA(0x004c2164) == 5) trn_reforce();  /* mid-mission (video-mode key) only; at mission end leave them off */
}
static void __cdecl trn_menuclose_wrap(void) {             /* 0x495170: no args (push esi / ... / pop esi; ret) */
    trn_unforce(); g_trn_guard_hits++;
    ((void (__cdecl *)(void))(DWORD_PTR)NA(0x00495170))();
    trn_reforce();
}
static int trn_install_guard(void) {
    static const DWORD save_sites[2] = { 0x004040f7, 0x0044e3a1 };   /* call 0x497290 */
    int i, ok = 0;
    for (i = 0; i < 2; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(0x00497290 - (save_sites[i] + 5)); memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)trn_savedef_wrap - (save_sites[i] + 5)); memcpy(w + 1, &rel, 4);
        ok += patch_bytes(save_sites[i], o, w, 5, "player_SaveDef call (trainer guard)");
    }
    {   /* 0x44e0c1: call 0x495170 (the menu key while the menu is open) */
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(0x00495170 - (0x0044e0c1 + 5)); memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)trn_menuclose_wrap - (0x0044e0c1 + 5)); memcpy(w + 1, &rel, 4);
        ok += patch_bytes(0x0044e0c1, o, w, 5, "options-menu close call (trainer guard)");
    }
    {   /* 0x495120: push 0x495170 (the menu's close callback, handed to 0x4953e0) - the imm32 at 0x495121 */
        DWORD o = 0x00495170, w = (DWORD)(DWORD_PTR)trn_menuclose_wrap;
        ok += patch_bytes(0x00495121, (const BYTE *)&o, (const BYTE *)&w, 4, "options-menu close callback (trainer guard)");
    }
    return ok;
}

static void apply_trainer(void) {
    if (env_flag("I76_TRAINER", 8, 1) == 0) { mlog("  trainer: disabled (I76_TRAINER=0)"); return; }
    {   /* Nitro: every address the trainer reads / writes must be mapped (nitro.c); Gold: always true */
        static const DWORD need[] = { 0x0054a264, 0x005a7e1c, 0x00654b98, 0x005da750, 0x005aab08, 0x00497290, 0x00495170, 0x004c2164 };
        if (!nitro_need("trainer", need, (int)(sizeof need / sizeof need[0]))) { mlog("  trainer: off (site map)"); return; }
    }
    char trn_nm[96];
    typedef char trn_ext_at_168[(I76TRN_EXT_OFFSET == sizeof(i76trn_ctl_t)) ? 1 : -1];
    const DWORD full = I76TRN_EXT_OFFSET + sizeof(i76trn_ext_t);
    g_trn_map = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, full, shm_name(trn_nm, sizeof trn_nm, I76TRN_SHM_NAME));
    if (g_trn_map) {
        g_trn = (i76trn_ctl_t *)MapViewOfFile(g_trn_map, FILE_MAP_ALL_ACCESS, 0, 0, full);
        if (g_trn) g_trn_ext = (i76trn_ext_t *)((BYTE *)g_trn + I76TRN_EXT_OFFSET);
        /* a front end that made the section first at the old 168 bytes (the classic window): no room for the
         * extension, so serve the version-1 block only */
        else g_trn = (i76trn_ctl_t *)MapViewOfFile(g_trn_map, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(i76trn_ctl_t));
    }
    if (!g_trn) { mlog("  trainer: shared memory %s NOT created (%lu)", trn_nm, GetLastError()); return; }
    memset(g_trn, 0, sizeof *g_trn);                          /* a front end that mapped first sees the block reset */
    if (g_trn_ext) memset(g_trn_ext, 0, sizeof *g_trn_ext);
    g_trn->version = I76TRN_VERSION; g_trn->size = sizeof(i76trn_ctl_t);
    trn_msg("proxy ready");
    install_frame_hook();
    if (g_trn_ext && g_frame_hook) {
        g_trn_ext->ext_version = I76TRN_EXT_VERSION; g_trn_ext->ext_size = sizeof(i76trn_ext_t);
        g_trn_ext->ext_magic = I76TRN_EXT_MAGIC;
    }
    g_trn->magic = g_frame_hook ? I76TRN_MAGIC : 0;           /* no hook, no service: the magic stays clear */
    mlog("  trainer: %s (%s, %u B, frame hook %s)", g_frame_hook ? "on" : "NOT applied", trn_nm,
         (unsigned)sizeof(i76trn_ctl_t), g_frame_hook ? "ok" : "missing");
    mlog("  trainer: full-state store / restore %s (%u B extension at +%u; Ctrl+9 / Ctrl+0 when a front end enables them)",
         g_trn_ext ? "on" : "OFF (the section was created at the old size by another program)",
         (unsigned)sizeof(i76trn_ext_t), (unsigned)I76TRN_EXT_OFFSET);
    if (g_frame_hook) {
        int g = trn_install_guard();
        mlog("  trainer: cheat-marker guard %d/4 sites (SaveDef x2, options-menu close x2)%s", g,
             g == 4 ? "" : " - INCOMPLETE: God / Ammo held through a menu close or a mission end can still mark the game as cheated");
    }
}

/* ===========================================================================
 * BREAKABLE BARS AS BOXES  (I76_BREAKABLE_BOX=1; off by default; MSVC build only)
 * ===========================================================================
 * 2026-10-12, lab docs/COLL-TIMING-2026-10-12.md s.1. A class-4 breakable's parts with collision kind 0 get the class
 * default 0x5000 (0x4367e0: class 4 -> 0x43689c `mov [0x52b92c], 0x5000`): a SPHERE of 0.75 x the part radius about
 * the part centre, tested against the car box grown by that radius on every side (0x440d90). For the T05 road-closed
 * barricade swend_1 the bar is 8.04 m wide and 0 m thick (SGEO half 4.02 x 0.32 x 0.00, radius 4.04): its sphere is
 * 3.03 m, so the bar is knocked off when the car's nose is still 3.03 m short of it, at any frame rate (stock too).
 * This makes only LONG, THIN, LOW default parts of breakables boxes (0x2000, the part's own mesh AABB, the 8-point
 * box-box test 0x43ff80 both ways round): horizontal length >= 2 m, horizontal thickness <= 0.25 m, and a height
 * range that overlaps 0.3..1.3 m above the part's parent origin (the car's sample points are at y 0.81 on a
 * Piranha). Sign posts (0.1 m wide) and panels (<= 1.6 m wide, 2+ m up) keep their spheres: as boxes the 8 sample
 * points (about 1 m apart) would slip past a post. The per-part read of the default, 0x436cbd `mov esi, [0x52b92c]`
 * (8B 35 2C B9 52 00, ebp = the part node; node+0x94..+0xa8 = the mesh AABB in part space, set by 0x4369c0 just
 * before the builder; node+0x40/+0x48/+0x50 = the part position doubles in its parent), goes to a thunk that keeps
 * the stock value unless all of the above hold. */
static volatile DWORD g_bbox_parts, g_bbox_box;
static int g_bbox_mode;                                      /* 1 or 2 (I76_BREAKABLE_BOX) */
static BYTE *g_bbox_node[128]; static DWORD g_bbox_node_n;   /* the part nodes bbox_pick made boxes (ring; the builder's node = the tree node) */
static float g_bbox_logged[8][3]; static int g_bbox_nlog;
static DWORD __cdecl bbox_pick(BYTE *node) {
    float ex, ey, ez, lo, hi, len, thin;
    double py = 0.0;
#ifdef _MSC_VER
    __try {
#endif
        g_bbox_parts++;
        ex = *(float *)(node + 0xa0) - *(float *)(node + 0x94);
        ey = *(float *)(node + 0xa4) - *(float *)(node + 0x98);
        ez = *(float *)(node + 0xa8) - *(float *)(node + 0x9c);
        py = *(double *)(node + 0x48);
        lo = (float)py + *(float *)(node + 0x98); hi = (float)py + *(float *)(node + 0xa4);
        len = ex > ez ? ex : ez; thin = ex > ez ? ez : ex;
        if (len >= 2.0f && thin <= 0.25f && ey >= 0.0f && lo < 1.3f && hi > 0.3f
            && (g_bbox_mode < 2 || ((lo + hi) * 0.5f >= 0.3f && (lo + hi) * 0.5f <= 1.3f))) {   /* =2: mid-height in the car band */
            g_bbox_box++;
            g_bbox_node[g_bbox_node_n++ & 127] = node;       /* the flame keeps this part's stock sphere (bbox_flame_thunk) */
            if (g_bbox_nlog < 8) { g_bbox_logged[g_bbox_nlog][0] = len; g_bbox_logged[g_bbox_nlog][1] = thin; g_bbox_logged[g_bbox_nlog][2] = (lo + hi) * 0.5f; g_bbox_nlog++; }
            return 0x2000;
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    return 0x5000;
}
#ifdef _MSC_VER
static __declspec(naked) void bbox_thunk(void) {              /* replaces `mov esi, [0x52b92c]` at 0x436cbd (+1 nop) */
    __asm {
        mov  esi, dword ptr ds:[0x0052b92c]
        cmp  esi, 0x5000                        /* only the class-4 default (0x4367e0 sets 0x5000 for class 4 only) */
        jne  done
        pushad
        push ebp                                /* the part node */
        call bbox_pick
        add  esp, 4
        mov  dword ptr [esp + 4], eax           /* pushad frame: [esp] edi, [esp+4] esi */
        popad
    done:
        ret                                     /* flags are recomputed by the `cmp esi, 0x1000` that follows */
    }
}
#endif
/* FLAME vs the boxed bars (2026-10-19 flame-box; I76_BREAKABLE_BOX_FLAME=1 default with the box switch, =0 = as before).
 * The flame's narrow test (weapon_FlameHitTest 0x4354c0 -> 0x43d770 at 0x435691) passes a pad of 0 (the push 0 at
 * 0x435674), so a box part is tested as its bare mesh AABB: the T05 bar's 8.04 x 0.64 x 0 m. The probe (flame_box_probe,
 * its replay agreeing with the real slab test on every one of 188 k calls) showed why the flame never hits it: the stream
 * never passes through that rectangle. Every rejection was "y slab behind" / "z slab behind" (the stream 1-2.7 m above
 * the bar, moving away) or "z parallel outside" (a stream along the bar, off its zero-thickness plane); none started
 * inside the box, and no rejected segment came within 1 m of the bar. The stock 0.75 r sphere (3.03 m) caught the same
 * stream on 94 % of the tests (TICK-FINISH s.12). Fix: inside a flame narrow test
 * only, a part bbox_pick made a box is read back as the stock class-4 default 0x5000 (the 0.75 r sphere, as without the
 * switch), so the flame sees the stock bar and the car / ram tests keep the box. The tree test reads the part kind at
 * 0x43da33 (`mov ebp, [ebx+0x10]; and ebp, 0xf000`, 9 bytes, ebx = the part node); that goes to this thunk. */
static int g_bbox_flame; static DWORD g_bbox_flame_n;
static DWORD __cdecl bbox_flame_kind(BYTE *node, DWORD kind) {
    DWORD i, n = g_bbox_node_n < 128 ? g_bbox_node_n : 128;
    if (!g_bbox_flame) return kind;
    for (i = 0; i < n; i++) if (g_bbox_node[i] == node) { g_bbox_flame_n++; return 0x5000; }
    return kind;
}
#ifdef _MSC_VER
static __declspec(naked) void bbox_flame_thunk(void) {        /* replaces 0x43da33 mov ebp, [ebx+0x10]; and ebp, 0xf000 (+4 nop) */
    __asm {
        mov  ebp, dword ptr [ebx + 0x10]
        and  ebp, 0xf000
        cmp  ebp, 0x2000
        jne  done
        cmp  dword ptr [g_in_flame_narrow], 0
        je   done
        pushad
        push ebp                                /* the kind */
        push ebx                                /* the part node */
        call bbox_flame_kind
        add  esp, 8
        mov  dword ptr [esp + 8], eax           /* pushad frame: [esp] edi, [esp+4] esi, [esp+8] ebp */
        popad
    done:
        ret                                     /* flags are recomputed by the `cmp ebp, 0x1000` that follows */
    }
}
#endif
static void apply_breakable_box_flame(void) {
#ifdef _MSC_VER
    static const BYTE kind_old[9] = { 0x8B, 0x6B, 0x10, 0x81, 0xE5, 0x00, 0xF0, 0x00, 0x00 };
    BYTE w[9] = { 0xE8, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90 }, *q = (BYTE *)(DWORD_PTR)NA(0x00435691), o2[5] = { 0xE8 }, w2[5] = { 0xE8 };
    LONG rel; int ok = 0, okc = 0, okp = 0;
    g_bbox_flame = env_flag("I76_BREAKABLE_BOX_FLAME", 8, 1) == 1;
    g_fbx_on = env_flag("I76_FLAME_BOX_PROBE", 8, 0) == 1;
    if (!g_bbox_flame && !g_fbx_on) { mlog("  breakable-box flame: off (I76_BREAKABLE_BOX_FLAME=0): the flame tests the boxed bars as boxes"); return; }
    if (!q) { mlog("  breakable-box flame: site not mapped - off"); return; }
    memcpy(&rel, q + 1, 4);                                   /* the flame narrow-test call -> flame_narrow_call */
    if (q[0] == 0xE8 && (DWORD)(DWORD_PTR)q + 5 + (DWORD)rel == NA(0x0043d770)) {
        LONG r0 = (LONG)(0x0043d770 - 0x00435696); memcpy(o2 + 1, &r0, 4);   /* = the bytes at q on Gold */
        rel = (LONG)((DWORD_PTR)flame_narrow_call - 0x00435696); memcpy(w2 + 1, &rel, 4);
        g_flame_narrow_next = NA(0x0043d770);                 /* = the initial value on Gold */
        okc = patch_bytes(0x00435691, o2, w2, 5, "flamer narrow test call (breakable-box flame)") && (g_exe == EXE_NITRO || memcmp(q, w2, 5) == 0);
    }
    if (okc && g_bbox_flame) {
        rel = (LONG)((DWORD_PTR)bbox_flame_thunk - (0x0043da33 + 5)); memcpy(w + 1, &rel, 4);
        ok = patch_bytes(0x0043da33, kind_old, w, 9, "tree narrow test part kind (breakable-box flame)") && (g_exe == EXE_NITRO || memcmp((void *)0x0043da33, w, 9) == 0);
    }
    if (okc && g_fbx_on && g_exe != EXE_NITRO) {              /* lab: the box-part slab test call 0x43dd3e -> flame_box_probe (Gold only) */
        BYTE *p = (BYTE *)0x0043dd3e, o3[5], w3[5] = { 0xE8 };
        memcpy(&rel, p + 1, 4);
        if (p[0] == 0xE8 && 0x0043dd43 + (DWORD)rel == 0x0043df10) {
            memcpy(o3, p, 5); rel = (LONG)((DWORD_PTR)flame_box_probe - 0x0043dd43); memcpy(w3 + 1, &rel, 4);
            okp = patch_bytes(0x0043dd3e, o3, w3, 5, "tree narrow test box call (flame box probe)");
        }
    }
    mlog("  breakable-box flame: %s (0x435691 flame narrow test wrapper %d/1, 0x43da33 part kind %d/1: boxed bars keep their stock sphere for the flame only)%s",
         g_bbox_flame && ok ? "ON" : g_bbox_flame ? "NOT applied" : "off (I76_BREAKABLE_BOX_FLAME=0)", okc, ok,
         g_fbx_on ? (okp ? "; box probe ON at 0x43dd3e (I76_FLAME_BOX_PROBE=1, lab)" : "; box probe NOT patched") : "");
#endif
}
static void apply_breakable_box(void) {
#ifdef _MSC_VER
    static const BYTE old6[6] = { 0x8B, 0x35, 0x2C, 0xB9, 0x52, 0x00 };   /* 0x436cbd mov esi, [0x52b92c] */
    BYTE w[6] = { 0xE8, 0, 0, 0, 0, 0x90 };
    LONG rel = (LONG)((DWORD_PTR)bbox_thunk - (0x00436cbd + 5));
    char v[4];
    if (GetEnvironmentVariableA("I76_BREAKABLE_BOX", v, sizeof(v)) != 1 || (v[0] != '1' && v[0] != '2' && v[0] != '3' && v[0] != '4')) return;
    g_bbox_mode = v[0] - '0';
    g_bbox_speed = g_bbox_mode >= 2;                        /* =3 keeps =2 (closing-speed score, bar box at car height) */
    if (g_bbox_mode >= 3) { install_frame_hook(); g_bbox_sweep = g_frame_hook; }
    if (g_bbox_mode == 4 && g_bbox_sweep) g_bbox_defer = 1;  /* =4 = =3 + the knock-off waits for the drawn car */
    memcpy(w + 1, &rel, 4);
    {   static const DWORD sa[1] = { 0x0052b92c };       /* the stub reads the default part kind (Nitro 0x523220) */
        if (!nitro_reloc_stub((void *)bbox_thunk, sa, 1, 32, "breakable-box stub")) { mlog("  breakable-box: NOT applied (stub)"); g_bbox_mode = 0; g_bbox_speed = g_bbox_sweep = g_bbox_defer = 0; return; } }
    mlog("  breakable-box: %d/1 (0x436cbd: long thin low default parts of class-4 breakables -> box 0x2000 instead of the 0.75 r sphere)%s",
         patch_bytes(0x00436cbd, old6, w, 6, "collision tree default part kind read"),
         g_bbox_mode == 2 ? "; =2: mid-height 0.3..1.3 m only, class-4 knock-off scored on the closing speed"
         : g_bbox_mode == 3 ? (g_bbox_sweep ? "; =3: =2 + sign-post sweep (a post the player's car box drove through that the engine never touched is scored by 0x4a7c80)"
                                            : "; =3: =2, sign-post sweep NOT applied (no frame hook)")
         : g_bbox_mode == 4 ? (g_bbox_sweep ? "; =4: =3 + every post knock-off (sweep or engine contact) waits until the DRAWN car box reaches the post (render-interp pose)"
                                            : "; =4: =2, sign-post sweep NOT applied (no frame hook)") : "");
    apply_breakable_box_flame();
#else
    if (GetEnvironmentVariableA("I76_BREAKABLE_BOX", NULL, 0)) mlog("  breakable-box: MSVC build only - not applied");
#endif
}
static void apply_breakable_speed(void) {                   /* after apply_coll_dedupe: =2 needs the 0x46f8d4 wrapper */
    static const BYTE call_damage[5] = { 0xE8, 0xA7, 0x83, 0x03, 0x00 };  /* 0x46f8d4 call 0x4a7c80 */
    BYTE w[5] = { 0xE8 };
    LONG rel = (LONG)((DWORD_PTR)coll_damage_wrap - (0x0046f8d4 + 5));
    if (!g_bbox_speed) return;
    memcpy(w + 1, &rel, 4);
    if (site_is(0x0046f8d4, w, 5)) { mlog("  breakable-speed: 1/1 (0x46f8d4 already on the collision damage wrapper)"); return; }
    mlog("  breakable-speed: %d/1 (0x46f8d4 object collision damage -> wrapper: class-4 victims scored on the closing speed)",
         patch_bytes(0x0046f8d4, call_damage, w, 5, "collision damage (objects), breakable speed"));
}
static void breakable_box_report(void) {                     /* with the start-pos read-back and at mission load lines */
    char b[200]; int i, n = 0;
    for (i = 0; i < g_bbox_nlog && n < 160; i++)
        n += wsprintfA(b + n, " %dx%dcm@%dcm", (int)(g_bbox_logged[i][0] * 100), (int)(g_bbox_logged[i][1] * 100), (int)(g_bbox_logged[i][2] * 100));
    b[n] = 0;
    mlog("  breakable-box: %lu class-4 default parts seen, %lu made boxes (length x thickness @ centre height):%s; flame tests that kept a box part's stock sphere %lu",
         g_bbox_parts, g_bbox_box, n ? b : " -", (unsigned long)g_bbox_flame_n);
    if (g_bbox_mode >= 3)
        mlog("  sign-sweep: %lu frames swept, %lu post entries into the car box, %lu the engine had hit, %lu scored by the sweep",
             g_sweep_frames, g_sweep_entries, g_sweep_engine, g_sweep_scored);
}

/* I76_BREAKABLE_BOX=3 (2026-10-12, sign-fix-2; owner on =2: "it's different signs when you teleport me to the top of
 * the hill, they are texas state road signs, but they don't respond to collisions with the fix"; lab
 * docs/SIGN-FIX-2-2026-10-12.md). =2 changes only what a contact the ENGINE found scores; a ram the engine never turns
 * into a contact (0x4349c0 -> 0x434bb0 -> 0x43f8c0 -> 0x440d90 never accepting it, for whatever reason) reaches no
 * damage call, so =2 cannot help it: the owner's =2 session logged 9 class-4 hits, all at the barricade bars, none at
 * a Texas sign. The sweep is an independent check of what the player SEES: once per frame (frame hook, after the last
 * tick and its collision pass), for every class-4 object within 40 m of the player's car, every post-like part (a
 * direct child of the root with a mesh AABB at most 0.7 m across horizontally and at least 1 m tall: sign posts, not
 * panels or bars) is tested as a vertical column against the car's own COLP box (body record +0x18 extents) swept
 * from the car's pose at the previous frame to its pose now, in the car's frame: 2-D slab entry of the column's
 * axis into the box grown by the column's half width, plus overlap of the column's height range with the box's. A
 * post that ENTERS the box and that the engine has not hit within the last 3 frames (sweep_note_engine_hit, fed by
 * the =2 wrapper on 0x46f8d4) is scored the way the engine scores a contact: 0x4a7c80(part node, car, car velocity,
 * unit velocity, contact point) - mass x |v|^2 x 6.67e-5 against the part's hit points, so a ram above ~6.3 m/s
 * knocks it off (slot 9 0x46f9a0, the stock knock-off) and a slow nudge stays a nudge. Only the player's car; AI cars
 * and every other object class are untouched; teleports (> 25 m between frames) and frames without motion skip. */
static BYTE *g_sweep_obj; static double g_sweep_prev[3]; static DWORD g_sweep_prev_frame;
static BYTE *sweep_player_box(BYTE *obj) {                  /* the player's mover record (0x52b930 list) */
    BYTE **node = *(BYTE ***)(DWORD_PTR)NA(0x0052b930); int n = 0;
    while (node && n++ < 512) {
        BYTE *body = node[2];
        if (body && *(BYTE **)body == obj) return body;
        node = (BYTE **)node[0];
    }
    return 0;
}
/* I76_BREAKABLE_BOX=4 (2026-10-12; owner on =3: "seems like the collision with the signs happens a little early again but
 * it happens 100% of the time"). Under I76_FIXED_STEP + I76_RENDER_INTERP the physics pose leads the drawn car by up to
 * one 41.7 ms step (~0.8 m at 20 m/s): =3's sweep scores the post when the PHYSICS box enters it, and an engine contact
 * (collision G accepts it over the step) is no later, so the sign falls while the car on screen is still short of it.
 * =4 keeps every detection of =3 (sweep + engine contacts, so the same 100 %) but queues the knock-off of a post-like
 * part (the sweep's criterion) by the player's car, with the arguments of the moment, and fires it in the frame hook
 * once the drawn car box - the render-interp pose of the frame just shown, advanced by its last frame-to-frame step,
 * i.e. the box the NEXT frame will show - touches the post (gap <= 0), or after 30 frames whatever happens. A queued
 * post the game has unregistered meanwhile is dropped. Logs `sign-defer:` per knock-off (first 40): frames waited,
 * the drawn gap at the knock-off (the bumper-to-post distance of the first frame drawn without the post; <= 0 = touching)
 * and the gap =3 would have had at detection. =3 logs the same drawn gap for its own knock-offs (`sign-gap:`). */
typedef struct { BYTE *root, *part; float v[3], n[3], p[3]; DWORD frame0; int src; float gap0; } sign_pend_t;
static sign_pend_t g_spend[8]; static int g_nspend;
static DWORD g_sdefer_fired, g_sdefer_timeout, g_sdefer_dropped, g_sgap_logged;
static BYTE *post_root(BYTE *part) {                        /* the class-4 tree root of a post-like part, else 0 */
    BYTE *root = part; float *a; int k = 0;
    if (!part) return 0;
    while (*(BYTE **)(root + 0x68) && k++ < 16) root = *(BYTE **)(root + 0x68);
    if (root == part || *(int *)(root + 0x6c) != 4) return 0;
    a = (float *)(part + 0x94);
    if ((a[3] - a[0]) * 0.5f > 0.35f || (a[5] - a[2]) * 0.5f > 0.35f || a[4] - a[1] < 1.0f) return 0;
    return root;
}
static void post_axis(BYTE *root, BYTE *part, double *q, float *hr) {   /* world x / z of the post's axis (the sweep's formula) */
    float *a = (float *)(part + 0x94), *RR = (float *)(root + 0x18), hx = (a[3] - a[0]) * 0.5f, hz = (a[5] - a[2]) * 0.5f;
    double lx = *(double *)(part + 0x40) + (a[0] + a[3]) * 0.5, lz = *(double *)(part + 0x50) + (a[2] + a[5]) * 0.5, ly = *(double *)(part + 0x48);
    q[0] = *(double *)(root + 0x40) + lx * RR[0] + ly * RR[3] + lz * RR[6];
    q[1] = *(double *)(root + 0x50) + lx * RR[2] + ly * RR[5] + lz * RR[8];
    *hr = hx > hz ? hx : hz;
}
static int car_box_ext(BYTE *obj, float *ext) {             /* the player's COLP box, as 0x43f510 reads it */
    BYTE *body = sweep_player_box(obj); int *bx;
    if (!body || *(int *)(body + 0x14) != 1 || !(bx = *(int **)(body + 0x18))) return 0;
    ext[0] = *(float *)&bx[3]; ext[1] = *(float *)&bx[8]; ext[2] = *(float *)&bx[0xb];
    ext[3] = *(float *)&bx[bx[0] + 2]; ext[4] = *(float *)&bx[bx[1] + 6]; ext[5] = *(float *)&bx[bx[2] + 10];
    return ext[3] > ext[0] && ext[4] > ext[1] && ext[5] > ext[2];
}
/* the gap between the post and the car box in the pose the NEXT frame will draw (render-interp pose of the frame just
 * shown + its last step; the physics pose when nothing was drawn interpolated): > 0 short of it, <= 0 touching / inside */
static float post_gap_drawn(BYTE *obj, BYTE *root, BYTE *part) {
    double q[2], C[3], x, z, lo_x, hi_x, lo_z, hi_z, ox, oz;
    float ext[6], hr, *R;
    if (!car_box_ext(obj, ext)) return 99.0f;
    post_axis(root, part, q, &hr);
    if (g_pld_obj == obj && g_pld_frame == g_frame - 1) {
        int k; for (k = 0; k < 3; k++) C[k] = g_pld_p[k] + (g_pld_p[k] - g_pld_prev[k]);
        R = g_pld_r;
    } else { memcpy(C, obj + 0x40, 24); R = (float *)(obj + 0x18); }
    x = (q[0] - C[0]) * R[0] + (q[1] - C[2]) * R[2]; z = (q[0] - C[0]) * R[6] + (q[1] - C[2]) * R[8];
    lo_x = ext[0] - hr; hi_x = ext[3] + hr; lo_z = ext[2] - hr; hi_z = ext[5] + hr;
    ox = x < lo_x ? lo_x - x : x > hi_x ? x - hi_x : 0.0; oz = z < lo_z ? lo_z - z : z > hi_z ? z - hi_z : 0.0;
    if (ox == 0.0 && oz == 0.0) {                           /* inside: minus the depth to the nearest face */
        double m = x - lo_x; if (hi_x - x < m) m = hi_x - x; if (z - lo_z < m) m = z - lo_z; if (hi_z - z < m) m = hi_z - z;
        return (float)-m;
    }
    return (float)sqrt(ox * ox + oz * oz);
}
static int post_registered(BYTE *root, BYTE *part) {        /* still on the collision static list, part still its child */
    BYTE **node; BYTE *pt; int n = 0, k = 0;
    for (node = *(BYTE ***)(DWORD_PTR)NA(0x0052b934); node && n < 8000; node = (BYTE **)node[0], n++) {
        BYTE *sb = node[2];
        if (sb && *(BYTE **)sb == root) {
            for (pt = *(BYTE **)(root + 0x64); pt && k++ < 64; pt = *(BYTE **)(pt + 0x60)) if (pt == part) return 1;
            return 0;
        }
    }
    return 0;
}
static int sign_pend_add(BYTE *root, BYTE *part, const float *v, const float *n, const float *p, int src, float gap0) {
    int i;
    for (i = 0; i < g_nspend; i++) if (g_spend[i].root == root) return 1;   /* already queued: this contact is the same ram */
    if (g_nspend >= 8) return 0;                                          /* full: let it score now */
    g_spend[g_nspend].root = root; g_spend[g_nspend].part = part;
    memcpy(g_spend[g_nspend].v, v, 12); memcpy(g_spend[g_nspend].n, n, 12); memcpy(g_spend[g_nspend].p, p, 12);
    g_spend[g_nspend].frame0 = g_frame; g_spend[g_nspend].src = src; g_spend[g_nspend].gap0 = gap0;
    g_nspend++;
    return 1;
}
static int sign_defer_engine(BYTE *victim, BYTE *source, const float *v, const float *n, const float *p) {
    BYTE **pp = *(BYTE ***)(DWORD_PTR)NA(0x0054a264), *obj = pp ? *pp : 0, *root;
#ifdef _MSC_VER
    __try {
#endif
        if (!obj || source != obj || !v || !n || !p || !(root = post_root(victim))) return 0;
        return sign_pend_add(root, victim, v, n, p, 1, post_gap_drawn(obj, root, victim));
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_bbox_defer = 0; mlog("  sign-defer: fault (engine contact) - turned off"); }
#endif
    return 0;
}
static void sign_gap_log_engine(BYTE *victim, BYTE *source) {   /* =3: an engine contact knocks a post off now */
    BYTE **pp = *(BYTE ***)(DWORD_PTR)NA(0x0054a264), *obj = pp ? *pp : 0, *root;
#ifdef _MSC_VER
    __try {
#endif
        if (!obj || source != obj || !(root = post_root(victim)) || g_sgap_logged >= 40) return;
        { char nm[9]; memcpy(nm, root, 8); nm[8] = 0; g_sgap_logged++;
          mlog("  sign-gap: %s post knocked by an engine contact, drawn gap %.2f m", nm, post_gap_drawn(obj, root, victim)); }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
}
static int sign_pend_run(BYTE *obj) {                       /* 1 = fired one (the caller stops for this frame) */
    int i;
    for (i = 0; i < g_nspend; i++) {
        sign_pend_t *e = &g_spend[i];
        float gap; DWORD waited = g_frame - e->frame0; char nm[9];
        if (!post_registered(e->root, e->part)) {           /* knocked off / freed meanwhile */
            g_sdefer_dropped++; g_spend[i] = g_spend[--g_nspend]; i--; continue;
        }
        gap = post_gap_drawn(obj, e->root, e->part);
        if (gap > 0.0f && waited < 30) continue;
        { sign_pend_t f = *e; g_spend[i] = g_spend[--g_nspend];
          memcpy(nm, f.root, 8); nm[8] = 0;
          g_sdefer_fired++; if (gap > 0.0f) g_sdefer_timeout++;
          sweep_note_engine_hit(f.root);
          if (g_sdefer_fired <= 40)
              mlog("  sign-defer: %s post knocked off after %lu frames (%s contact): drawn gap %.2f m at the knock-off (=3 would have knocked it at a drawn gap of %.2f m)%s",
                   nm, (unsigned long)waited, f.src ? "engine" : "sweep", gap, f.gap0, gap > 0.0f ? " - TIMEOUT" : "");
          if (!f.src) st_sign_sound(obj, f.root);                  /* the sweep's knock-off: the engine's post-contact sound (simtick.c, s.17) */
          ((DWORD (__cdecl *)(BYTE *, BYTE *, float *, float *, float *))(DWORD_PTR)NA(0x004a7c80))(f.part, obj, f.v, f.n, f.p); }
        return 1;
    }
    return 0;
}
static int g_sweep_tick;                                     /* sign_sweep_tick is running: the clock is the tick count */
static void sign_sweep(void) {
#ifdef _MSC_VER
    __try {
#endif
        BYTE **pp = *(BYTE ***)(DWORD_PTR)NA(0x0054a264), *obj = pp ? *pp : 0, *body, **node;
        double P0[3], P1[3], dx, dz;
        float *R, ext[6];
        int *bx, n = 0;
        if (!obj) { g_sweep_obj = 0; g_nspend = 0; return; }
        if (!g_sweep_tick && g_nspend && sign_pend_run(obj)) return;   /* =4: a queued post reached by the drawn car (one per frame) */
        memcpy(P1, obj + 0x40, 24);
        if (obj != g_sweep_obj || (g_sweep_tick ? g_st_tickno : g_frame) - g_sweep_prev_frame != 1) {   /* new car / gap: re-arm */
            g_sweep_obj = obj; memcpy(g_sweep_prev, P1, 24); g_sweep_prev_frame = g_sweep_tick ? g_st_tickno : g_frame; return;
        }
        memcpy(P0, g_sweep_prev, 24); memcpy(g_sweep_prev, P1, 24); g_sweep_prev_frame = g_sweep_tick ? g_st_tickno : g_frame;
        dx = P1[0] - P0[0]; dz = P1[2] - P0[2];
        if (dx * dx + dz * dz < 1e-8 || dx * dx + dz * dz > 625.0) return;   /* no motion (no step this frame) / teleport */
        R = (float *)(obj + 0x18);                          /* rows right / up / forward */
        if (R[4] < 0.7f) return;                            /* on its side or roof: the column test assumes upright */
        body = sweep_player_box(obj);
        if (!body || *(int *)(body + 0x14) != 1 || !(bx = *(int **)(body + 0x18))) return;   /* kind 1 = the COLP box */
        ext[0] = *(float *)&bx[3]; ext[1] = *(float *)&bx[8]; ext[2] = *(float *)&bx[0xb];     /* as 0x43f510 reads it */
        ext[3] = *(float *)&bx[bx[0] + 2]; ext[4] = *(float *)&bx[bx[1] + 6]; ext[5] = *(float *)&bx[bx[2] + 10];
        if (!(ext[3] > ext[0] && ext[4] > ext[1] && ext[5] > ext[2])) return;
        g_sweep_frames++;
        {   static DWORD logged = 0, logframe = 0;               /* a summary when something changed, at most every 600 frames */
            if (g_sweep_entries != logged && g_frame - logframe > 600) {
                logged = g_sweep_entries; logframe = g_frame;
                mlog("  sign-sweep: %lu frames swept, %lu post entries into the car box, %lu the engine had hit, %lu scored by the sweep",
                     g_sweep_frames, g_sweep_entries, g_sweep_engine, g_sweep_scored);
                if (g_bbox_defer) mlog("  sign-defer: %lu knock-offs fired at the drawn car (%lu by timeout), %lu queued posts gone before", (unsigned long)g_sdefer_fired, (unsigned long)g_sdefer_timeout, (unsigned long)g_sdefer_dropped);
            }
        }
        for (node = *(BYTE ***)(DWORD_PTR)NA(0x0052b934); node && n < 8000; node = (BYTE **)node[0], n++) {
            BYTE *sb = node[2], *root = sb ? *(BYTE **)sb : 0, *part;
            double ox, oz;
            float *RR;
            if (!root || *(int *)(root + 0x6c) != 4) continue;
            ox = *(double *)(root + 0x40) - P1[0]; oz = *(double *)(root + 0x50) - P1[2];
            if (ox * ox + oz * oz > 1600.0) continue;
            RR = (float *)(root + 0x18);
            for (part = *(BYTE **)(root + 0x64); part; part = *(BYTE **)(part + 0x60)) {
                float *a = (float *)(part + 0x94);          /* mesh AABB in part space: min xyz, max xyz */
                float hx = (a[3] - a[0]) * 0.5f, hz = (a[5] - a[2]) * 0.5f, hr = hx > hz ? hx : hz, y0, y1;
                double lx = *(double *)(part + 0x40) + (a[0] + a[3]) * 0.5, lz = *(double *)(part + 0x50) + (a[2] + a[5]) * 0.5;
                double ly = *(double *)(part + 0x48), qx, qy, qz, x0, z0, x1, z1, t0 = 0.0, t1 = 1.0, cy0, cy1, tc;
                double mnx = ext[0] - hr, mxx = ext[3] + hr, mnz = ext[2] - hr, mxz = ext[5] + hr, sx, sz;
                int k;
                if (hx > 0.35f || hz > 0.35f || a[4] - a[1] < 1.0f) continue;   /* post-like parts only */
                qx = *(double *)(root + 0x40) + lx * RR[0] + ly * RR[3] + lz * RR[6];
                qy = *(double *)(root + 0x48) + lx * RR[1] + ly * RR[4] + lz * RR[7];
                qz = *(double *)(root + 0x50) + lx * RR[2] + ly * RR[5] + lz * RR[8];
                y0 = (float)(qy + a[1]); y1 = (float)(qy + a[4]);
                /* the column axis in the car's frame (current rows) at the previous and the current pose */
                x0 = (qx - P0[0]) * R[0] + (qz - P0[2]) * R[2]; z0 = (qx - P0[0]) * R[6] + (qz - P0[2]) * R[8];
                x1 = (qx - P1[0]) * R[0] + (qz - P1[2]) * R[2]; z1 = (qx - P1[0]) * R[6] + (qz - P1[2]) * R[8];
                if (x0 >= mnx && x0 <= mxx && z0 >= mnz && z0 <= mxz) continue;   /* already inside: entered earlier */
                for (k = 0; k < 2; k++) {                   /* slab entry, x then z */
                    double p0 = k ? z0 : x0, d = k ? z1 - z0 : x1 - x0, lo = k ? mnz : mnx, hi = k ? mxz : mxx, ta, tb;
                    if (d > -1e-9 && d < 1e-9) { if (p0 < lo || p0 > hi) { t0 = 2.0; break; } continue; }
                    ta = (lo - p0) / d; tb = (hi - p0) / d;
                    if (ta > tb) { double t = ta; ta = tb; tb = t; }
                    if (ta > t0) t0 = ta;
                    if (tb < t1) t1 = tb;
                }
                if (t0 > t1 || t0 > 1.0) continue;
                tc = t0;
                cy0 = P0[1] + (P1[1] - P0[1]) * tc + ext[1]; cy1 = P0[1] + (P1[1] - P0[1]) * tc + ext[4];
                if (y1 < cy0 || y0 > cy1) continue;         /* the post is above / below the car box */
                g_sweep_entries++;
                if (sweep_engine_hit_since(root, 3)) { g_sweep_engine++; continue; }
                {
                    float st[15], *s0, v[3], nn[3], pt[3], vv;
                    char nm[9];
                    s0 = ((float *(__cdecl *)(float *, BYTE *))(DWORD_PTR)NA(0x00461ed0))(st, obj);   /* the car's state: velocity at +0x18 */
                    v[0] = s0[6]; v[1] = s0[7]; v[2] = s0[8];
                    vv = (float)sqrt((double)v[0] * v[0] + (double)v[1] * v[1] + (double)v[2] * v[2]);
                    if (vv < 0.5f) continue;
                    nn[0] = v[0] / vv; nn[1] = v[1] / vv; nn[2] = v[2] / vv;
                    sx = P0[0] + dx * tc; sz = P0[2] + dz * tc;
                    pt[0] = (float)qx; pt[1] = (float)(cy0 > y0 ? cy0 : y0); pt[2] = (float)qz;
                    memcpy(nm, root, 8); nm[8] = 0;
                    g_sweep_scored++;
                    sweep_note_engine_hit(root);
                    if (g_bbox_defer) {                     /* =4: queue it for the drawn car */
                        float g0 = post_gap_drawn(obj, root, part);
                        if (sign_pend_add(root, part, v, nn, pt, 0, g0)) {
                            if (g_sweep_scored <= 40)
                                mlog("  sign-sweep: %s post at (%.1f, %.1f) entered the car box with no engine contact - queued at %.1f m/s for the drawn car (drawn gap now %.2f m; "
                                     "entry at %.2f of the last step of %.2f m, gap from the %s pose)",
                                     nm, qx, qz, vv, g0, tc, sqrt(dx * dx + dz * dz), (g_pld_obj == obj && g_pld_frame == g_frame - 1) ? "drawn" : "PHYSICS");
                            continue;
                        }
                    }
                    if (g_sweep_scored <= 40)
                        mlog("  sign-sweep: %s post at (%.1f, %.1f) entered the car box with no engine contact - scored at %.1f m/s "
                             "(car at %.1f, %.1f; post y %.2f..%.2f, box y %.2f..%.2f; drawn gap %.2f m)", nm, qx, qz, vv, sx, sz, y0, y1, cy0, cy1,
                             post_gap_drawn(obj, root, part));
                    st_sign_sound(obj, root);               /* no engine contact: its post-contact sound (simtick.c, s.17) */
                    ((DWORD (__cdecl *)(BYTE *, BYTE *, float *, float *, float *))(DWORD_PTR)NA(0x004a7c80))(part, obj, v, nn, pt);
                    return;                                 /* a knock-off may unregister / free the object: done this frame */
                }
            }
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_bbox_sweep = 0; g_bbox_defer = 0; mlog("  sign-sweep: fault - turned off"); }
#endif
}

/* Under the whole-sim tick (2026-10-18 tick-gaps): the frame hook sweep saw a tick's motion one display frame after the
 * tick ran, and the drawn car starts down that tick's segment in the tick's own frame, so a post the step entered early
 * was already behind the drawn bumper when it was queued (T05 signs, n 2 + 2 boots, 22 knock-offs each: drawn gap at the
 * knock-off median -0.31 m vs -0.11 m under promotion 18; entry point in the step vs gap at detection: gap = 0.67 x
 * entry - 0.24 m). So under the tick the sweep runs once per tick at the end of the sim block (st_cam_wrap, before
 * that frame is drawn; P0 / P1 = the poses at the last two tick ends) and a queued knock-off is tried right away and on
 * every display frame after (frame hook), as =4 intends. */
static void sign_sweep_tick(void) {
    BYTE **pp = *(BYTE ***)(DWORD_PTR)NA(0x0054a264), *obj = pp ? *pp : 0;
    g_sweep_tick = 1; sign_sweep(); g_sweep_tick = 0;
    if (obj && g_nspend && g_bbox_defer) sign_pend_run(obj);
}
static void sign_pend_frame(void) {
#ifdef _MSC_VER
    __try {
#endif
        BYTE **pp = *(BYTE ***)(DWORD_PTR)NA(0x0054a264), *obj = pp ? *pp : 0;
        if (!obj) { g_nspend = 0; return; }
        if (g_nspend) sign_pend_run(obj);
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_bbox_sweep = 0; g_bbox_defer = 0; mlog("  sign-sweep: fault (queued knock-off) - turned off"); }
#endif
}

/* ===========================================================================
 * START POSITION  (I76_START_POS=x,y,z,yaw_deg[,delay_s]; needs I76_MISSION; off by default)
 * ===========================================================================
 * Owner request 2026-10-12: start T05 at the top of the hill before the barricades, standing still, facing down the
 * road (lab docs/COLL-TIMING-2026-10-12.md s.2). At every start of that mission, when the local player's vehicle has been live
 * in a mission (0x4c2164 == 5, tel_player) for delay_s (default 1.0) of wall time, the frame hook - top of the frame,
 * before simclock and the tick, where the trainer's TELEPORT runs - writes for 0.3 s: the rotation rows right / up /
 * forward at obj+0x18 for a yaw about +y (yaw 0 = facing +z, 90 = +x, -90 = -x; the write rate-ab-live.py face()
 * makes), the position doubles at obj+0x40, and zero velocity (ent+0xbc), body rates (ent+0xc8) and speed / 1/speed
 * (ent+0xac / +0xb0): the trainer's TELEPORT + STOP held. Then the car is released and drops onto the ground (give y as
 * the ground height + 0.5). 2026-10-17: the speed is now held at 0 too (the player is placed at 25 m/s: T05's opening
 * drives it). That alone does not keep the car on the mark: 1 s after the release it still reads ~10.7 m/s, turned,
 * 5 m off and ~16 m off after 3 s (lab twin, n 2; 86 of 88 earlier read-backs said MOVED AWAY at ~13 m/s). Open:
 * the T05 opening sequence still driving the player when the hold ends is the suspect, not yet measured.
 * 2026-10-17 (patch 2): the delay now counts only from the end of the mission's opening: the player must be live AND
 * not driven by the opening - play mode 0x4fe534 & 0x3e clear and the AI-drove-the-player latch 0x5244c0 = 0
 * (i76-map subsystems/ai.md M49a; the same test as replay.c). Placed during T05's opening, the opening's AI drive kept
 * steering and throttling the car after the release. If the latch never clears, the car is placed 60 s after it went
 * live anyway (logged).
 * The pose is read back and logged 1 s later. I76_RENDER_INTERP sees the jump (> 8 m) and resets its history.
 * Mission scripts keyed to the normal route are not re-run. 2026-10-17 (owner: "08 does not teleport"): it was once per
 * process, so Replay from the in-mission menu started at the stock spawn. Now it re-arms when a new mission load is
 * seen - simclock_Init zeroes simclock_frame_count 0x5a7e1c at the top of every mission, and this hook runs before
 * simclock_Update, so the count drops - and the loaded name 0x5049f0 is still I76_MISSION. With I76_MISSION the shell
 * is skipped (0x504c10), and every mission end except Replay exits the game, so only a replay of the same mission
 * can follow; the name check guards the rest. The Esc menu does not reload (0x4fe534 = 0x10, state stays 5). */
static double g_start_p[3];
static float g_start_yaw, g_start_delay = 1.0f;
static int g_start_state;                                    /* 0 waiting, 1 holding, 2 released, 3 done */
static DWORD g_start_t0, g_start_until, g_start_fc, g_start_n, g_start_live0, g_start_busy;
static BYTE *g_start_obj;
static char g_start_mission[32];
static void start_pos_inner(void) {
    BYTE *ent = 0, *obj = 0;
    DWORD now = GetTickCount();
    if (*(volatile int *)0x004c2164 == 5) obj = tel_player(&ent);
    if (g_start_state == 0) {
        int busy;
        if (!obj) { g_start_t0 = 0; g_start_live0 = 0; g_start_busy = 0; return; }
        if (!g_start_live0) g_start_live0 = now ? now : 1;
        busy = (*(volatile BYTE *)0x004fe534 & 0x3e) || *(volatile DWORD *)0x005244c0;   /* the opening still drives the player */
        if (busy && now - g_start_live0 < 60000) { g_start_busy++; g_start_t0 = 0; return; }
        if (!g_start_t0) {
            g_start_t0 = now ? now : 1;
            mlog("  start-pos: player live and not driven by the opening (waited %lu frames, %.1f s since live%s) - placing in %.1f s",
                 (unsigned long)g_start_busy, (now - g_start_live0) / 1000.0, busy ? "; latch still set after 60 s, placing anyway" : "",
                 g_start_delay);
            return;
        }
        if (now - g_start_t0 < (DWORD)(g_start_delay * 1000.0f)) return;
        g_start_state = 1; g_start_obj = obj; g_start_until = now + 300; g_start_n++;
        mlog("  start-pos: placing the player (obj %p) at (%.1f, %.1f, %.1f) yaw %.1f, frame %lu, was at (%.1f, %.1f, %.1f) speed %.2f m/s, placement %lu",
             (void *)obj, g_start_p[0], g_start_p[1], g_start_p[2], g_start_yaw, (unsigned long)g_frame,
             *(double *)(obj + 0x40), *(double *)(obj + 0x48), *(double *)(obj + 0x50), *(float *)(ent + 0xac),
             (unsigned long)g_start_n);
    }
    if (g_start_state == 1 || g_start_state == 2) {
        if (obj != g_start_obj) { mlog("  start-pos: the player changed during the placement - stopped"); g_start_state = 3; return; }
    }
    if (g_start_state == 1) {
        float yr = g_start_yaw * 0.017453292f, sy = sinf(yr), cy = cosf(yr);
        float r[9];
        r[0] = cy; r[1] = 0.0f; r[2] = -sy;                  /* right */
        r[3] = 0.0f; r[4] = 1.0f; r[5] = 0.0f;               /* up */
        r[6] = sy; r[7] = 0.0f; r[8] = cy;                   /* forward */
        memcpy(obj + 0x18, r, sizeof r);
        memcpy(obj + 0x40, g_start_p, sizeof g_start_p);
        memset(ent + 0xbc, 0, 12); memset(ent + 0xc8, 0, 12);
        *(float *)(ent + 0xac) = 0.0f; *(float *)(ent + 0xb0) = 0.0f;   /* the speed too, as the trainer's STOP */
        if ((LONG)(now - g_start_until) >= 0) { g_start_state = 2; g_start_until = now + 1000; }
    } else if (g_start_state == 2 && (LONG)(now - g_start_until) >= 0) {
        double dx = *(double *)(obj + 0x40) - g_start_p[0], dz = *(double *)(obj + 0x50) - g_start_p[2];
        mlog("  start-pos: read back 1 s after release: (%.1f, %.2f, %.1f), forward (%.3f, %.3f, %.3f), %.2f m from the target in x/z, speed %.2f m/s, AI latch %lu, play mode 0x%02x - %s",
             *(double *)(obj + 0x40), *(double *)(obj + 0x48), *(double *)(obj + 0x50),
             *(float *)(obj + 0x30), *(float *)(obj + 0x34), *(float *)(obj + 0x38), sqrt(dx * dx + dz * dz),
             *(float *)(ent + 0xac), (unsigned long)*(volatile DWORD *)0x005244c0, (unsigned)*(volatile BYTE *)0x004fe534,
             dx * dx + dz * dz < 25.0 ? "OK" : "MOVED AWAY");
        if (g_bbox_parts) breakable_box_report();
        g_start_state = 3;
    }
}
static void start_pos_frame(void) {
    DWORD fc = *(volatile DWORD *)0x005a7e1c;               /* simclock_frame_count: zeroed by simclock_Init per mission */
    int reload = fc < g_start_fc;
    g_start_fc = fc;
    if (reload) {
        if (lstrcmpiA((const char *)0x005049f0, g_start_mission) == 0) {
            if (g_start_state != 0) mlog("  start-pos: mission '%s' loaded again (Replay) - armed again", g_start_mission);
            g_start_state = 0; g_start_t0 = 0; g_start_obj = 0; g_start_live0 = 0; g_start_busy = 0;
        } else if (g_start_state < 4) {
            mlog("  start-pos: another mission loaded ('%.15s', not '%s') - off for the rest of the process",
                 (const char *)0x005049f0, g_start_mission);
            g_start_state = 4;
        }
    }
    if (g_start_state >= 3) return;
#ifdef _MSC_VER
    __try { start_pos_inner(); }
    __except (EXCEPTION_EXECUTE_HANDLER) { g_start_state = 3; }
#else
    start_pos_inner();
#endif
}
static void apply_start_pos(void) {
    char v[96], *p;
    double f[5];
    int n = 0;
    DWORD k = GetEnvironmentVariableA("I76_START_POS", v, sizeof(v));
    if (k == 0) return;
    if (k >= sizeof(v)) { mlog("  start-pos: I76_START_POS too long - not applied"); return; }
    if (GetEnvironmentVariableA("I76_MISSION", g_start_mission, sizeof(g_start_mission)) == 0) { mlog("  start-pos: needs I76_MISSION (the mission it belongs to) - not applied"); return; }
    g_start_mission[15] = 0;                                 /* the exe holds 16 bytes at 0x5049f0 (lstrcpynA in mission-launch) */
    for (p = v; n < 5 && *p; ) {
        f[n++] = atof(p);
        while (*p && *p != ',') p++;
        if (*p == ',') p++;
    }
    if (n < 4) { mlog("  start-pos: I76_START_POS=%s needs x,y,z,yaw_deg[,delay_s] - not applied", v); return; }
    g_start_p[0] = f[0]; g_start_p[1] = f[1]; g_start_p[2] = f[2]; g_start_yaw = (float)f[3];
    if (n == 5 && f[4] >= 0.0 && f[4] <= 60.0) g_start_delay = (float)f[4];
    install_frame_hook();
    g_start_on = g_frame_hook != 0;
    mlog("  start-pos: %s - (%.1f, %.1f, %.1f) yaw %.1f deg, %.1f s after the player is live in the mission, at every start of it (also Replay), speed held 0",
         g_start_on ? "armed" : "NOT armed (frame hook missing)", f[0], f[1], f[2], f[3], g_start_delay);
}

/* ===========================================================================
 * RETAIL HANDLING  (I76_RETAIL_HANDLING=1; off by default; lab 2026-10-16, i76-everywhere docs\records\RETAIL-HANDLING-SWITCH.md)
 * ===========================================================================
 * The emulated retail 1.0 exe (March 1997) turns about 30 % less than the Gold / GOG exe at a held 18 m/s on full
 * keyboard steer (86Box memtrace 2026-10-15: 0.94-1.00 vs 1.34-1.59 rad/s). physics_StepVehicle and its callees are the
 * SAME algorithm in both builds (every branch and constant matched, retail 0x472360 / 0x472890 / 0x473600 / 0x474bf0 /
 * 0x4759b0 / 0x475100 / 0x4754a0 against Gold 0x438fd0 / 0x43a5d0 / 0x43c310 / 0x43ce10 / 0x43c850). What differs is
 * one bit: every retail trace has entity flag 0x10000 on the player's car (20 of 20 runs), no Gold trace has it (0 of
 * 21). That is the "Arcade Phys." play option: physics_InitEntity 0x438a90 (retail 0x471df0, the same rule) sets it on
 * the player's car when options_play_flags bit 0 is on, and physics_SetPlayerArcadeMode 0x43d1a0 does when the
 * in-game options page is applied. The retail runs had it on BY ACCIDENT: their launch copied the Gold-layout
 * I76PLYR.DEF (96 B) into the retail folder, retail reads 88 B with its own layout and its option dword lands on Gold
 * bytes 01 00 8e 00 (docs\records\RETAIL-HANDLING-DIFF.md s.3). Both exes default the option to off. So this switch
 * reproduces "retail as measured on 2026-10-15", which equals our exe with Arcade Phys. ticked; it is not a 1997 default.
 * With the bit the engine:
 *   - limits the steering by grip instead of a constant: yaw = steer x min(k v, a / v) with a = 9.8 n.y^3 x suspension
 *     handling x surface grip x (sum of wheel sizes) / 4 instead of 7.84 x (sum of wheel sizes) (0x43ce10; retail traces:
 *     a = 23.4 vs Gold 31.7 m/s2 from yaw x v / steer while not sliding), and slides less;
 *   - turns a car at rest on its roof back over instead of destroying it, offline only (physics_CheckImpact 0x436ff0).
 * This switch sets the bit on the local player's car on every frame (top of the frame, before the tick: the trainer's
 * place), so a respawned car gets it too, without touching options_play_flags or I76PLYR.DEF (nothing is saved, the
 * options page is unchanged; applying the page clears the bit for one frame). AI cars are left alone (Gold and retail
 * both give it only to the player and the "taurus" script car). */
static DWORD g_rh_sets, g_rh_frames;
static void retail_handling_frame(void) {
    BYTE *ent = 0;
    if (*(volatile int *)0x004c2164 != 5 || !tel_player(&ent)) return;
    g_rh_frames++;
    if (!(*(volatile DWORD *)(ent + 0x454) & 0x10000)) {
        *(volatile DWORD *)(ent + 0x454) |= 0x10000;
        g_rh_sets++;
        if (g_rh_sets <= 4 || (g_rh_sets & (g_rh_sets - 1)) == 0)
            mlog("  retail-handling: flag 0x10000 set on the player's car (set #%lu, frame %lu, flags now 0x%08lX)",
                 (unsigned long)g_rh_sets, (unsigned long)g_frame, (unsigned long)*(volatile DWORD *)(ent + 0x454));
    }
}
static void apply_retail_handling(void) {
    if (env_flag("I76_RETAIL_HANDLING", 8, 0) != 1) return;
    install_frame_hook();
    g_rh_on = g_frame_hook != 0;
    mlog("  retail-handling: %s - the player's car drives as the 2026-10-15 retail emulator runs did (Arcade Phys., entity flag 0x10000): "
         "grip-based steering limit, roof-rest flip instead of destruction (offline)", g_rh_on ? "on" : "NOT on (frame hook missing)");
}

/* ===========================================================================
 * THE "PLEASE INSERT CD 'Interstate '76 CD 2'" PROMPT: INSTRUMENT (opt-in: I76_CD_LOG=1)
 * and I76_CD_FAKE=1 (EXPERIMENTAL mitigation)
 * ===========================================================================
 * Backlog P1-09 / MENU-USABILITY-PLAN P8 / E6. The modal fired on 6 of ~21 lab launches (i76_pristine_fix.exe,
 * sitting 1) with no known trigger. Static reading (i76-map status\tasks\m12-cd-prompt.md, re-read 2026-10-02 against
 * i76_ref.exe md5 9a232dcc):
 *
 *   The prompt text lives in exactly two places, both calling the message-box helper 0x471580 (MessageBoxA, caption
 *   "Interstate '76 Gold Edition", OK = retry, Cancel = exit(1)):
 *     (a) cd_PromptLoop 0x470d90, reached ONLY through the slot 0x6562d0 at 0x4b2faa in vfs_FindContainerForFile
 *         0x4b2e00: the file asked for lives only in a container of type 0 ("cdN" in i76.zix, or the miss8/miss16
 *         container that vfs_LoadZix 0x4b23e0 appends as type 0 when startup_IsMinimum 0x4b2220 returns 1), and that
 *         volume is not the current one (0x4fff18, init -1, set only when the drive in 0x58d92c carries a label equal
 *         to a zix volume label). The lab zix is "0 \ I76_CD2" + "DIR: i76.zfs", and the mounted ISO is I76_CD1, so
 *         0x4fff18 stays -1 on every run and (a) fires exactly when a file resolves to the miss8/miss16 container
 *         with startup_IsMinimum == 1. Once up, OK rescans the CD-ROM drives for a label starting "I76_CD2": never
 *         present here, so OK re-prompts for ever, as seen.
 *     (b) shell_cb_17 0x470f90 (the CD-2 intro-movie callback): prompts only when its arg 0 is non-zero and no drive
 *         carries I76_CD2. WinMain calls it with 1 at 0x402ce2 - ONLY when startup_IsMinimum returned 1 at 0x402ccd.
 *         The shell DLL calls the slot itself before missions.
 *   startup_IsMinimum 0x4b2220, the actual rule (re-read against the 2026-10-02 live run and measured with the same
 *   three calls from an x86 test program): RegOpenKeyExA(HKLM, "SOFTWARE\Activision", KEY_READ) fails -> 1;
 *   RegCreateKeyExA(that, "Interstate '76 Gold Edition", KEY_ALL_ACCESS) fails -> 1; value "0" -> 0; "1" -> 1;
 *   absent/other -> FindFirstFileA("miss8") relative to the cwd: found -> 0 (written back as "0"), else 1 ("1").
 *   On this machine the key exists in the real HKLM (WOW6432Node, owner Administrators, Users = ReadKey, Minimum =
 *   "0") so the KEY_ALL_ACCESS create is DENIED (err 5) for every non-elevated launch - registry virtualization
 *   (enabled: no manifest) does not redirect an existing key - and the stock function answers 1 BEFORE reading the
 *   value or looking for miss8. Elevated launches get FullControl, read "0" and answer 0. So the 6/21 split is the
 *   launcher's elevation, not its cwd (the cwd still matters afterwards: the loose miss16\ opens are cwd-relative,
 *   which is what the proxy's cwd fix is for). The AiO exe (lab i76.exe, the daily driver) has 0x4b2220 patched to
 *   `xor eax,eax; ret` - the same answer the registry would give a full install - which is why it never prompts;
 *   i76_pristine*.exe carry the stock function.
 *
 * WHAT THIS INSTALLS (every hook verifies the stock bytes first; a different exe is left alone):
 *   H1  IAT hook on MessageBoxA (slot 0x4bc35c; the import descriptor says USER32.dll on stock builds and u32x.dll
 *       on the AiO/lab build - both are tried). Cost: nothing until a box is shown. Logs caption, text, the CD
 *       globals, the game state, the frame and a return-address chain (so (a) and (b) and plain fatal errors are
 *       told apart: 0x470de9 = cd_PromptLoop, 0x471153 = shell_cb_17 whose arg 0 is read from its frame).
 *   H2  call-site hook at 0x4b2faa (FF 15 D0 62 65 00 -> E8 rel32 90): logs the file name being looked up (frame of
 *       vfs_FindContainerForFile), its file-table entry and container bitset, the wanted volume, the container
 *       and volume tables, a live GetVolumeInformationA probe of every CD-ROM drive, then calls the original.
 *       Cost: nothing until the prompt path runs.
 *   H3  entry hook on startup_IsMinimum 0x4b2220 (stock prologue 81 EC 5C 01 00 00 -> E9 rel32 90): logs each call's
 *       answer with the registry value, the cwd and the FindFirstFile("miss8") result (2..3 calls per launch; a
 *       `1` is force-logged, a `0` only under I76MUSIC_LOG). Skipped, with a note, on the AiO exe.
 *   H4  entry hook on shell_cb_17 0x470f90 (81 EC A4 00 00 00 -> E9 rel32 90): one line per call with arg 0 and the
 *       MCI state (a few calls per session).
 *
 * I76_CD_FAKE=1 (verified live 2026-10-02 on the sandbox, autotest\cd2-test.ps1, i76_pristine_fix.exe, cwd C:\Windows:
 * three startup_IsMinimum calls faked 1 -> 0, no MSGBOX, the game proceeds; with the cwd fix in DllMain): in H3, when
 * the stock function answers 1 (Minimum) but <game dir>\miss8 exists as a directory, answer 0 instead. Exact effect:
 * vfs_LoadZix marks miss8/miss16 as a local directory container (type 1), vfs_ResolveFilePath then builds
 * "miss16\<file>" as on every healthy launch, and WinMain skips its shell_cb_17(1) call - i.e. the stock behaviour
 * of a full install whose registry value reads "0", or of the AiO exe. The stock function still runs first, so its
 * own registry write (only on the value-absent path, which a denied create never reaches) happens as before. This
 * IS the right permanent mitigation for the pristine exes: the stock question "is this a full install?" is answered
 * by a registry write that a non-elevated process cannot make, and the directory the function itself falls back to
 * is the ground truth. On a genuinely minimal install (no miss8 directory) the answer is unchanged. It does nothing
 * on the AiO exe (already 0) and nothing about the shell's own shell_cb_17 calls (none seen; plan option C if any).
 */
static int    g_cd_fake;
typedef int (WINAPI *mbox_fn)(HWND, LPCSTR, LPCSTR, UINT);
static mbox_fn real_MessageBoxA;
static DWORD  g_ismin_resume = 0x004b2226;                   /* after the displaced `sub esp, 0x15c` */
static DWORD  g_cb17_resume  = 0x00470f96;                   /* after the displaced `sub esp, 0xa4` */
static int    g_ismin_calls, g_cb17_calls, g_cd_boxes;

static void sncat(char *buf, int size, int *n, const char *fmt, ...) {
    va_list ap; int k;
    if (*n >= size - 1) return;
    va_start(ap, fmt); k = _vsnprintf(buf + *n, size - *n, fmt, ap); va_end(ap);
    if (k < 0 || *n + k >= size) { *n = size - 1; buf[*n] = 0; } else *n += k;
}

static int cd_is_text(DWORD a) { return a >= 0x00401000 && a < 0x004bc000; }
/* Does a call instruction end right before `a`? (the exe keeps no frame pointers, so the chain is a stack scan) */
static int cd_call_before(DWORD a) {
    const BYTE *p = (const BYTE *)(DWORD_PTR)a;
    if (p[-5] == 0xE8) return 1;                                                        /* call rel32 */
    if (p[-6] == 0xFF && (p[-5] == 0x15 || (p[-5] & 0xF8) == 0x90)) return 1;          /* call [disp32] / [reg+disp32] */
    if (p[-3] == 0xFF && ((p[-2] & 0xF8) == 0x50 || p[-2] == 0x14)) return 1;          /* call [reg+disp8] / [sib] */
    if (p[-4] == 0xFF && p[-3] == 0x54) return 1;                                       /* call [esp+disp8] */
    if (p[-2] == 0xFF && ((p[-1] & 0xF8) == 0xD0 || (p[-1] & 0xF8) == 0x10)) return 1;  /* call reg / call [reg] */
    if (p[-7] == 0xFF && (p[-6] == 0x14 || p[-6] == 0x94)) return 1;                    /* call [idx*4+disp32] */
    return 0;
}
/* Return-address candidates above `from`, innermost first: dwords inside i76.exe .text that a call precedes.
 * 0x471580 (the message-box helper) has a 0x404-byte frame, so the scan reaches 6 KB up the stack. */
static void cd_chain(const DWORD *from, char *buf, int size) {
    DWORD lo = __readfsdword(8), hi = __readfsdword(4);      /* NT_TIB StackLimit / StackBase */
    const DWORD *p; int n = 0, hits = 0;
    buf[0] = 0;
    for (p = from; (DWORD)(DWORD_PTR)p >= lo && (DWORD)(DWORD_PTR)p + 4 <= hi && p - from < 1536 && hits < 12; p++) {
        if (!cd_is_text(*p) || !cd_call_before(*p)) continue;
        sncat(buf, size, &n, " %08lX", (unsigned long)*p);
        if (*p == 0x00471153)                                /* inside shell_cb_17: sub esp,0xa4 + 4 pushes + push eax + this
                                                                slot = 0xbc, so its arg 0 is 0xc0 above */
            sncat(buf, size, &n, "[shell_cb_17 arg0=%ld]", (long)p[0xc0 / 4]);
        hits++;
    }
}

static void cd_log_state(const char *who) {
    const BYTE *flags = (const BYTE *)0x00609520; char drives[32], cwd[MAX_PATH]; int i, n = 0, cnt;
    for (i = 0; i < 26; i++) if (flags[i]) drives[n++] = (char)('A' + i);
    drives[n] = 0;
    cwd[0] = 0; GetCurrentDirectoryA(sizeof cwd, cwd);
    flog("CD[%s]: cd2_drive 0x%02X cdrom_drives [%s] scan_idx %lu cur_cd_index %ld cd_path_flag %lu | mci open_err %lu dev %ld active %lu"
         " | state %lu frame %lu cwd \"%s\"", who,
         *(volatile BYTE *)0x0058d92c, drives, (unsigned long)*(volatile DWORD *)0x0058d930,
         (long)*(volatile DWORD *)0x004fff18, (unsigned long)*(volatile DWORD *)0x00669ee4,
         (unsigned long)*(volatile DWORD *)0x00524678, (long)*(volatile DWORD *)0x004ed890, (unsigned long)*(volatile DWORD *)0x00524674,
         (unsigned long)*(volatile DWORD *)0x004c2164, (unsigned long)g_frame, cwd);
    for (i = 0; i < 26; i++) {                               /* what every CD-ROM drive answers RIGHT NOW */
        char root[4] = "A:\\", label[64]; DWORD fs = 0;
        if (!flags[i]) continue;
        root[0] = (char)('A' + i); label[0] = 0;
        if (GetVolumeInformationA(root, label, sizeof label, NULL, NULL, &fs, NULL, 0))
            flog("CD[%s]:   drive %c: label \"%s\" (type %lu)", who, root[0], label, (unsigned long)GetDriveTypeA(root));
        else
            flog("CD[%s]:   drive %c: GetVolumeInformationA FAILS err %lu (type %lu)", who, root[0], (unsigned long)GetLastError(), (unsigned long)GetDriveTypeA(root));
    }
    cnt = *(volatile int *)0x006562cc;                       /* zix volume table */
    for (i = 0; i < cnt && i < 16; i++) {
        const char *v = (const char *)0x006562e0 + i * 0x300;
        flog("CD[%s]:   volume %d label \"%.32s\" text \"%.32s\" path \"%.64s\"", who, i, v, v + 0x100, v + 0x200);
    }
    cnt = *(volatile int *)0x006562c8;                       /* container table: name, +0x100 type (1 dir, 0 cdN), +0x104 volume, +0x108 handle */
    for (i = 0; i < cnt && i < 16; i++) {
        const BYTE *c = (const BYTE *)0x006592e0 + i * 0x10c;
        flog("CD[%s]:   container %d \"%.64s\" type %lu volume %ld handle 0x%lX", who, i, (const char *)c,
             (unsigned long)*(const DWORD *)(c + 0x100), (long)*(const DWORD *)(c + 0x104), (unsigned long)*(const DWORD *)(c + 0x108));
    }
}

/* H1: every MessageBoxA the exe shows (CD prompts, fatal errors) with the state and the chain. */
static int WINAPI hook_MessageBoxA(HWND w, LPCSTR text, LPCSTR cap, UINT type) {
    DWORD *A = (DWORD *)_AddressOfReturnAddress(); char chain[400], t[300]; int i;
    for (i = 0; text && text[i] && i < (int)sizeof t - 1; i++) t[i] = (text[i] == '\r' || text[i] == '\n') ? ' ' : text[i];
    t[i] = 0;
    g_cd_boxes++;
    flog("MSGBOX #%d: caption \"%s\" text \"%s\" type 0x%X from 0x%08lX", g_cd_boxes, cap ? cap : "(null)", t, type, (unsigned long)A[0]);
    cd_log_state("box");
    cd_chain(A, chain, sizeof chain);
    flog("MSGBOX: chain%s", chain);
    return real_MessageBoxA ? real_MessageBoxA(w, text, cap, type) : IDOK;
}

/* H2: the VFS is about to ask for a CD. Frame of vfs_FindContainerForFile 0x4b2e00 above our return slot A:
 * sub esp,0x38 + 4 pushes + 3 args = 0x58, so its own return address is A[0x58/4] and its arg 0 (the file name,
 * a 16-byte key) is A[0x5c/4]. */
typedef int (__cdecl *cd_prompt_fn)(int, const char *, const char *);
static int __cdecl hook_cd_PromptLoop(int letter, const char *label, const char *text) {
    DWORD *A = (DWORD *)_AddressOfReturnAddress();
    const char *name = (const char *)(DWORD_PTR)A[0x5c / 4];
    char chain[400]; int i, cnt;
    if (IsBadReadPtr(name, 16)) name = "(unreadable)";
    flog("CD PROMPT (vfs_FindContainerForFile returning to 0x%08lX): file \"%.16s\" wants volume %ld label \"%.32s\" text \"%.32s\" (empty -> default 'Interstate '76 CD 2') cd2_drive 0x%02X",
         (unsigned long)A[0x58 / 4], name, (long)(((DWORD_PTR)label - 0x006562e0) / 0x300), label ? label : "", text ? text : "", (unsigned)(BYTE)letter);
    cnt = *(volatile int *)0x005daccc;                       /* file table: 0x30 B records, 16 B name + 256-bit container set */
    for (i = 0; i < cnt && i < 65536; i++) {
        const BYTE *e = *(const BYTE **)0x005dacc8 + i * 0x30;
        if (_strnicmp((const char *)e, name, 16) == 0) {
            const DWORD *bits = (const DWORD *)(e + 0x10); char cl[200]; int m = 0, j;
            for (j = 0; j < 256; j++) if (bits[j >> 5] & (1u << (j & 31))) sncat(cl, sizeof cl, &m, " %d", j);
            flog("CD:   file entry %d \"%.16s\" in containers:%s", i, (const char *)e, cl);
            break;
        }
    }
    if (i >= cnt) flog("CD:   file \"%.16s\" is not in the file table (%d entries)", name, cnt);
    cd_log_state("vfs");
    cd_chain(A, chain, sizeof chain);
    flog("CD:   chain%s", chain);
    return ((cd_prompt_fn)(DWORD_PTR)*(volatile DWORD *)0x006562d0)(letter, label, text);
}

/* H3: startup_IsMinimum, with the inputs it is about to read. The stock body runs through a trampoline that
 * re-executes the displaced prologue. */
static __declspec(naked) void ismin_tramp(void) {
    __asm {
        sub esp, 0x15c
        jmp dword ptr [g_ismin_resume]
    }
}
typedef LONG (WINAPI *regopen_fn)(HKEY, LPCSTR, DWORD, REGSAM, PHKEY);
typedef LONG (WINAPI *regcreate_fn)(HKEY, LPCSTR, DWORD, LPSTR, DWORD, REGSAM, LPSECURITY_ATTRIBUTES, PHKEY, LPDWORD);
typedef LONG (WINAPI *regquery_fn)(HKEY, LPCSTR, LPDWORD, LPDWORD, LPBYTE, LPDWORD);
typedef LONG (WINAPI *regclose_fn)(HKEY);
typedef BOOL (WINAPI *opentok_fn)(HANDLE, DWORD, PHANDLE);
typedef BOOL (WINAPI *tokinfo_fn)(HANDLE, TOKEN_INFORMATION_CLASS, LPVOID, DWORD, PDWORD);
static int __cdecl hook_IsMinimum(void) {
    /* The exe's OWN sequence, call for call (a KEY_READ probe of the value would miss the point: measured 2026-10-02,
     * the stock function never reaches the value): RegOpenKeyExA(HKLM, "SOFTWARE\Activision", KEY_READ), then
     * RegCreateKeyExA(.., "Interstate '76 Gold Edition", .., KEY_ALL_ACCESS, ..) - which a non-elevated process is DENIED
     * (err 5) once the key exists in the real HKLM owned by Administrators (registry virtualization does not redirect an
     * existing key), and the function returns 1 right there. Only an elevated launch, or a machine where the key is still
     * absent, gets as far as the value / the FindFirstFile("miss8") fallback. */
    char cwd[MAX_PATH], reg[48], dir[MAX_PATH]; HKEY k = NULL, k2 = NULL; DWORD sz = sizeof reg - 1, disp = 0, attr, virt = 0, elev = 0, n;
    LONG r1 = -1, r2 = -1, r3 = -1; int r, rel; HANDLE tok;
    HMODULE adv = GetModuleHandleA("advapi32.dll");         /* the exe imports it, so it is loaded; resolved here to keep
                                                               the link line as it was */
    regopen_fn ropen = adv ? (regopen_fn)GetProcAddress(adv, "RegOpenKeyExA") : NULL;
    regcreate_fn rcreate = adv ? (regcreate_fn)GetProcAddress(adv, "RegCreateKeyExA") : NULL;
    regquery_fn rquery = adv ? (regquery_fn)GetProcAddress(adv, "RegQueryValueExA") : NULL;
    regclose_fn rclose = adv ? (regclose_fn)GetProcAddress(adv, "RegCloseKey") : NULL;
    tokinfo_fn tinfo = adv ? (tokinfo_fn)GetProcAddress(adv, "GetTokenInformation") : NULL;
    opentok_fn topen = adv ? (opentok_fn)GetProcAddress(adv, "OpenProcessToken") : NULL;
    WIN32_FIND_DATAA fd; HANDLE h;
    lstrcpynA(reg, "(not reached)", sizeof reg);
    if (ropen && rcreate && rquery && rclose) {
        r1 = ropen(HKEY_LOCAL_MACHINE, "SOFTWARE\\Activision", 0, KEY_READ, &k);
        if (r1 == 0) {
            r2 = rcreate(k, "Interstate '76 Gold Edition", 0, NULL, 0, KEY_ALL_ACCESS, NULL, &k2, &disp);   /* opens or creates,
                                                                                        exactly as the stock code is about to */
            if (r2 == 0) {
                r3 = rquery(k2, "Minimum", NULL, NULL, (BYTE *)reg, &sz);
                if (r3 == 0) reg[sz < sizeof reg ? sz : sizeof reg - 1] = 0; else _snprintf(reg, sizeof reg, "(query err %ld)", r3);
                rclose(k2);
            }
            rclose(k);
        }
    }
    if (topen && tinfo && topen(GetCurrentProcess(), TOKEN_QUERY, &tok)) {
        tinfo(tok, TokenVirtualizationEnabled, &virt, sizeof virt, &n);
        tinfo(tok, TokenElevation, &elev, sizeof elev, &n);
        CloseHandle(tok);
    }
    cwd[0] = 0; GetCurrentDirectoryA(sizeof cwd, cwd);
    h = FindFirstFileA("miss8", &fd); rel = h != INVALID_HANDLE_VALUE; if (rel) FindClose(h);
    _snprintf(dir, sizeof dir, "%s\\miss8", g_dir); attr = GetFileAttributesA(dir);
    r = ((int (__cdecl *)(void))ismin_tramp)();
    g_ismin_calls++;
    if (r) flog("CD: startup_IsMinimum #%d -> 1 (MINIMUM: miss8/miss16 become a CD container, WinMain prompts) | RegOpenKeyExA(Activision, KEY_READ) %ld,"
                " RegCreateKeyExA(Gold Edition, KEY_ALL_ACCESS) %ld%s, Minimum %s | token elevated %lu virtualization %lu | cwd \"%s\" | FindFirstFile(miss8) %s | %s %s",
                g_ismin_calls, r1, r2, r2 == 5 ? " (ACCESS_DENIED: the stock function returns 1 here, before the value)" : "", reg,
                (unsigned long)elev, (unsigned long)virt, cwd, rel ? "found" : "NOT found", dir,
                attr == INVALID_FILE_ATTRIBUTES ? "missing" : (attr & FILE_ATTRIBUTE_DIRECTORY) ? "is a directory" : "is a file");
    else   mlog("  startup_IsMinimum #%d -> 0 | RegOpenKeyExA %ld RegCreateKeyExA %ld Minimum %s | token elevated %lu virtualization %lu | cwd \"%s\" | FindFirstFile(miss8) %s",
                g_ismin_calls, r1, r2, reg, (unsigned long)elev, (unsigned long)virt, cwd, rel ? "found" : "NOT found");
    if (r && g_cd_fake && attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY)) {
        flog("CD FAKE: startup_IsMinimum answer 1 -> 0 (%s is a directory; EXPERIMENTAL I76_CD_FAKE)", dir);
        r = 0;
    }
    return r;
}

/* H4: shell_cb_17 (the CD-2 movie callback) with its arg 0 - the only thing that lets it prompt - and the MCI state. */
static __declspec(naked) void cb17_tramp(void) {
    __asm {
        sub esp, 0xa4
        jmp dword ptr [g_cb17_resume]
    }
}
static int __cdecl hook_shell_cb_17(int arg0) {
    DWORD *A = (DWORD *)_AddressOfReturnAddress(); int r;
    g_cb17_calls++;
    mlog("  shell_cb_17 #%d (arg0 %d) from 0x%08lX: mci open_err %lu dev %ld active %lu cd2_drive 0x%02X | state %lu frame %lu",
         g_cb17_calls, arg0, (unsigned long)A[0], (unsigned long)*(volatile DWORD *)0x00524678, (long)*(volatile DWORD *)0x004ed890,
         (unsigned long)*(volatile DWORD *)0x00524674, *(volatile BYTE *)0x0058d92c, (unsigned long)*(volatile DWORD *)0x004c2164, (unsigned long)g_frame);
    r = ((int (__cdecl *)(int))cb17_tramp)(arg0);
    mlog("  shell_cb_17 #%d -> %d", g_cb17_calls, r);
    return r;
}

static void apply_cd_instrument(HMODULE exe) {
    static const BYTE pl_old[6] = { 0xFF, 0x15, 0xD0, 0x62, 0x65, 0x00 };   /* call [0x6562d0] at 0x4b2faa */
    static const BYTE im_old[6] = { 0x81, 0xEC, 0x5C, 0x01, 0x00, 0x00 };   /* sub esp, 0x15c at 0x4b2220 (stock) */
    static const BYTE im_aio[6] = { 0x31, 0xC0, 0xC3, 0x90, 0x90, 0x90 };   /* xor eax,eax; ret: the AiO no-CD patch */
    static const BYTE cb_old[6] = { 0x81, 0xEC, 0xA4, 0x00, 0x00, 0x00 };   /* sub esp, 0xa4 at 0x470f90 */
    BYTE pl_new[6] = { 0xE8, 0, 0, 0, 0, 0x90 }, im_new[6] = { 0xE9, 0, 0, 0, 0, 0x90 }, cb_new[6] = { 0xE9, 0, 0, 0, 0, 0x90 };
    char v[8]; LONG rel; void *old; int n2, n3 = 0, n4; const char *mb = "USER32.dll", *im = "hooked";
    /* OPT-IN since 2026-10-02 22:xx: always-on broke the trip route. The H4 wrapper forwards one argument to
     * shell_cb_17 0x470f90; on the bookmark -> garage -> DONE path the shell calls it (from i76shell, arg0 0), the
     * wrapped call returned -1 and the shell never started the mission (exe frame counter stuck at 0, leg-b B1.9,
     * 2 of 2; the owner's option-6 run hung the same way). Melee and the direct mission boot do not take that path,
     * which is why 15 automated entries passed. Until the callback's full signature is carried through, nothing here
     * is patched unless I76_CD_LOG=1. */
    if (!GetEnvironmentVariableA("I76_CD_LOG", v, sizeof v) || v[0] == '0') return;
    g_cd_fake = GetEnvironmentVariableA("I76_CD_FAKE", v, sizeof v) > 0 && v[0] == '1';
    old = patch_iat(exe, mb, "MessageBoxA", hook_MessageBoxA);
    if (!old) { mb = "u32x.dll"; old = patch_iat(exe, mb, "MessageBoxA", hook_MessageBoxA); }   /* AiO: USER32 through u32x */
    real_MessageBoxA = (mbox_fn)old;
    rel = (LONG)((DWORD_PTR)hook_cd_PromptLoop - (0x004b2faa + 5)); memcpy(pl_new + 1, &rel, 4);
    n2 = patch_bytes(0x004b2faa, pl_old, pl_new, 6, "cd_PromptLoop call site");
    if (memcmp((const void *)0x004b2220, im_aio, 6) == 0) im = "already 0 in this exe (AiO no-CD patch), not hooked";
    else {
        rel = (LONG)((DWORD_PTR)hook_IsMinimum - (0x004b2220 + 5)); memcpy(im_new + 1, &rel, 4);
        n3 = patch_bytes(0x004b2220, im_old, im_new, 6, "startup_IsMinimum entry");
        if (!n3) im = "NOT hooked";
    }
    rel = (LONG)((DWORD_PTR)hook_shell_cb_17 - (0x00470f90 + 5)); memcpy(cb_new + 1, &rel, 4);
    n4 = patch_bytes(0x00470f90, cb_old, cb_new, 6, "shell_cb_17 entry");
    mlog("  cd-instrument: MessageBoxA %s (%s, was %p), cd_PromptLoop call %s, startup_IsMinimum %s, shell_cb_17 %s%s",
         old ? "hooked" : "NOT hooked", mb, old, n2 ? "hooked" : "NOT hooked", im, n4 ? "hooked" : "NOT hooked",
         g_cd_fake ? " | I76_CD_FAKE=1: a Minimum answer becomes 0 when <game>\\miss8 is a directory (EXPERIMENTAL)" : "");
}

/* TERRAIN DETAIL DISTANCE  (I76_TERRAIN_LOD=<factor 1..256>; off by default; EXPERIMENT, sandbox only)
 * The terrain is a quadtree rebuilt every frame (i76-map subsystems/renderer.md, 0x491341): a node becomes a leaf when
 * d2 > (2h)^2 * K, K ~ A, and otherwise splits when a midpoint height error exceeds a threshold ~ B. Nothing blends
 * between levels, so vertices snap as the camera approaches. renderer_SetTerrainResolution 0x493080 loads A [0x4fad20]
 * and B [0x4fad24] from immediates: Low 6.4 / 1/256, Medium 16 / 1/384, High 40 / 1/576.7. The switch multiplies A and
 * divides B in all three, so every split happens `factor` (A) / sqrt-ish (B) farther out. More vertices per frame:
 * the int16 vertex-index ceiling (32,767 per frame, FARCLIP-CAMERA-CRASH.md) comes closer, so soak with the far clip. */
/* TERRAIN VERTEX GUARD (2026-10-12; installed with I76_TERRAIN_LOD; I76_TERRAIN_VLIMIT=<1000..32000>, default 28000).
 * Every terrain vertex index is stored as an int16 (renderer_SplitTerrainEdge 0x4918f0 takes [0x6442ec], the frame's
 * vertex count, as the new index); past 32,767 the index wraps and the game dies (docs/records/FARCLIP-CAMERA-CRASH.md).
 * Each split of a node below size 32 passes `test ebx, ebx; je 0x4917b0` (0x4912f6, leaf when the half size is 0)
 * before its distance and height-error tests; the guard turns that into "leaf when the half size is 0 OR the frame
 * already holds more than the limit": nodes stop splitting (a coarser far patch) instead of wrapping the index. The
 * forced splits of nodes of size >= 32 (0x4912d3) are a few hundred vertices per frame and stay as they were. With the
 * stock / x8 detail the count peaks near 17,000 (binoculars at 1800 m), so the guard never fires there; it is what
 * makes a higher I76_TERRAIN_LOD safe. Counted; logged on the clutter 600-frame line when it fired. */
static DWORD g_tv_limit = 28000, g_tv_hits, g_tv_hits_logged, g_tv_on;
static DWORD g_tv_ret_split = 0x004912fe, g_tv_ret_leaf = 0x004917b0;
static __declspec(naked) void terrain_vguard_stub(void) {        /* jmp from 0x4912f6 (replaces test ebx,ebx; je 0x4917b0) */
    __asm {
        test ebx, ebx
        jz leaf
        push eax
        mov eax, dword ptr ds:[0x006442ec]
        cmp eax, g_tv_limit
        pop eax
        jg guard
        jmp dword ptr [g_tv_ret_split]
    guard:
        inc g_tv_hits
    leaf:
        jmp dword ptr [g_tv_ret_leaf]
    }
}
static void terrain_vguard_report(void) {
    if (g_tv_on && g_tv_hits != g_tv_hits_logged) {
        mlog("  terrain-vguard: %lu node splits refused so far (frame terrain vertices past %lu; int16 index ceiling 32767)",
             (unsigned long)g_tv_hits, (unsigned long)g_tv_limit);
        g_tv_hits_logged = g_tv_hits;
    }
}
static void apply_terrain_vguard(void) {
    static const BYTE old[8] = { 0x85, 0xdb, 0x0f, 0x84, 0xb2, 0x04, 0x00, 0x00 };   /* test ebx,ebx; je 0x4917b0 */
    BYTE w[8] = { 0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90 };
    LONG rel = (LONG)((DWORD_PTR)terrain_vguard_stub - (0x004912f6 + 5));
    int lim = env_int("I76_TERRAIN_VLIMIT", 8, 28000);
    if (lim < 1000 || lim > 32000) { mlog("  terrain-vguard: I76_TERRAIN_VLIMIT %d out of range (1000..32000) - using 28000", lim); lim = 28000; }
    g_tv_limit = (DWORD)lim;
    memcpy(w + 1, &rel, 4);
    {   static const DWORD sa[1] = { 0x006442ec };
        if (!nitro_reloc_stub((void *)terrain_vguard_stub, sa, 1, 64, "terrain vertex guard stub")) { mlog("  terrain-vguard: NOT applied (stub)"); return; } }
    g_tv_ret_split = NA(0x004912fe); g_tv_ret_leaf = NA(0x004917b0);   /* = the initial values on Gold */
    g_tv_on = patch_bytes(0x004912f6, old, w, 8, "terrain vertex guard");
    mlog("  terrain-vguard: %s (no node splits past %lu terrain vertices in a frame)", g_tv_on ? "on" : "NOT applied", (unsigned long)g_tv_limit);
}
/* TERRAIN LOD HYSTERESIS AND FREEZE  (I76_TERRAIN_HYST=<percent>, I76_TERRAIN_FREEZE=<far m>,<move m>; need I76_TERRAIN_LOD;
 * off by default; rc-draw lane 2026-10-20, docs/records/RC-DRAW-FPS-2026-10-20.md)
 * Owner 2026-10-20: "the distracting issue with the terrain is that it CHANGES while you are driving ... steep edges change more,
 * things further away change more." The quadtree (0x4911e0) is rebuilt every frame from the camera alone, so every node whose
 * split test sits near its threshold flips as the eye moves, and flips back. Each node of half size h < 32 passes the vertex
 * guard's stub at 0x4912f6 before its tests (distance d2 against (2h)^2 K, then the midpoint height errors against
 * exp2(d2) B); the tests read the eye only from [0x6442f8] / [0x644300] (written by QueueTerrain's setup, read nowhere else).
 * A node is named by its min corner in samples, (int)(x + 0.5) as the leaf maker 0x491810 does, and its half size. The
 * main camera's pass (the call at 0x4020a4) records every node it visits: leaf, or split once a child of it is visited.
 *  - HYST=p: a node that was split in the previous main pass is tested with the eye moved toward it so it looks p % nearer;
 *    one that was a leaf, p % farther. A split then needs the camera p % closer than the stock threshold and the merge
 *    p % farther: no flip back and forth around a threshold. Detail is unchanged on average (the band is symmetric).
 *  - FREEZE=f,m: a node farther than f metres keeps the decision it had when it was first seen (or last tested nearer than f)
 *    until it comes within f: the snapshot is refreshed from a pass once the camera has moved m metres, and that pass already
 *    holds the frozen decisions, so a refresh only adds nodes that were new. Far terrain stops changing; its splits are made
 *    up when it comes within f (measured: change beyond 300 m almost gone, near change up; RC-DRAW-FPS s.4).
 * Only the main pass is touched (the mirror's pass runs stock); after the pass the eye is put back. Counted: passes,
 * nodes biased / frozen, parent look-ups that missed (a node whose parent was not visited, expected only for size 32). */
#define TH_SLOTS 131072u
typedef struct { unsigned __int64 k; BYTE st; } th_slot_t;
static th_slot_t *g_th_tab[3];                       /* previous pass, this pass, freeze snapshot */
static DWORD g_th_gen[3];
static DWORD *g_th_used[3]; static DWORD g_th_nused[3];
static int g_th_cur = 0, g_th_prev = 1, g_th_snap = 2, g_th_snap_ok;   /* cur / prev swap each pass; snap is a copy */
static int g_th_on, g_th_main;                        /* switch on; inside the main camera's pass */
static float g_th_up = 1.0f, g_th_dn = 1.0f;          /* distance scale for was-split / was-leaf nodes */
static float g_tf_far2, g_tf_move2;                   /* in samples^2 (5 m per sample) */
static float g_th_eye[2], g_tf_eye[2]; static int g_th_eye_ok;
static DWORD g_th_passes, g_th_biased, g_th_frozen, g_th_pmiss, g_th_win_frozen, g_th_snaps;
static unsigned __int64 th_key(int x, int z, int h) { return ((unsigned __int64)(DWORD)(x & 0xffffff) << 40) | ((unsigned __int64)(DWORD)(z & 0xffffff) << 16) | (DWORD)(h & 0xffff); }
static DWORD th_hash(unsigned __int64 k) { k ^= k >> 29; k *= 0xbf58476d1ce4e5b9ull; k ^= k >> 32; return (DWORD)k & (TH_SLOTS - 1); }
static BYTE th_get(int t, unsigned __int64 k) {
    DWORD i = th_hash(k), n; th_slot_t *s = g_th_tab[t];
    for (n = 0; n < 64; n++, i = (i + 1) & (TH_SLOTS - 1)) { if (!s[i].st) return 0; if (s[i].k == k) return s[i].st; }
    return 0;
}
static void th_put(int t, unsigned __int64 k, BYTE st) {        /* st 1 leaf, 2 split; a split never goes back to leaf */
    DWORD i = th_hash(k), n; th_slot_t *s = g_th_tab[t];
    for (n = 0; n < 64; n++, i = (i + 1) & (TH_SLOTS - 1)) {
        if (!s[i].st) { if (g_th_nused[t] < TH_SLOTS) { s[i].k = k; s[i].st = st; g_th_used[t][g_th_nused[t]++] = i; } return; }
        if (s[i].k == k) { if (st > s[i].st) s[i].st = st; return; }
    }
}
static void th_clear(int t) { DWORD j; for (j = 0; j < g_th_nused[t]; j++) g_th_tab[t][g_th_used[t][j]].st = 0; g_th_nused[t] = 0; }
/* from the stub at 0x4912f6 (all registers saved): v0 = the node's min-corner vertex (x, y, z floats, samples), h = half size.
 * Returns 0 leaf, 1 split, 2 run the stock tests (with the eye possibly moved for this node). */
static int __cdecl th_node(const float *v0, int h) {
    int x, z, s, ps; float cx, cz, dx, dz, k; BYTE was = 0;
    if (!g_th_main || !v0) return 2;
    if (!g_th_eye_ok) { g_th_eye[0] = *(volatile float *)(DWORD_PTR)NA(0x006442f8); g_th_eye[1] = *(volatile float *)(DWORD_PTR)NA(0x00644300); g_th_eye_ok = 1; }
    x = (int)(v0[0] + 0.5f); z = (int)(v0[2] + 0.5f);
    th_put(g_th_cur, th_key(x, z, h), 1);
    s = h ? 2 * h : 1; ps = 2 * s;                       /* this node's size; the parent's (its half size is s) */
    if (ps <= 32) {
        unsigned __int64 pk = th_key(x & ~(ps - 1), z & ~(ps - 1), s);
        if (th_get(g_th_cur, pk)) th_put(g_th_cur, pk, 2); else g_th_pmiss++;
    }
    if (h == 0) return 2;
    cx = v0[0] + (float)h; cz = v0[2] + (float)h;
    dx = cx - g_th_eye[0]; dz = cz - g_th_eye[1];
    if (g_tf_far2 > 0.0f && g_th_snap_ok && dx * dx + dz * dz > g_tf_far2) {
        BYTE f = th_get(g_th_snap, th_key(x, z, h));
        if (f) { g_th_frozen++; g_th_win_frozen++; *(volatile float *)(DWORD_PTR)NA(0x006442f8) = g_th_eye[0]; *(volatile float *)(DWORD_PTR)NA(0x00644300) = g_th_eye[1]; return f == 2 ? 1 : 0; }
    }
    if (g_th_up != 1.0f) was = th_get(g_th_prev, th_key(x, z, h));
    k = was == 2 ? g_th_up : was == 1 ? g_th_dn : 1.0f;
    if (k != 1.0f) g_th_biased++;
    *(volatile float *)(DWORD_PTR)NA(0x006442f8) = cx - dx * k;          /* the stock tests now see the node k times as far */
    *(volatile float *)(DWORD_PTR)NA(0x00644300) = cz - dz * k;
    return 2;
}
static DWORD g_th_res, g_th_ret_forced = 0x00491802;   /* 0x491802: fstp st(0); jmp 0x49167c = the forced split of h >= 32 */
static __declspec(naked) void terrain_hyst_stub(void) {          /* jmp from 0x4912f6 (replaces test ebx,ebx; je 0x4917b0) */
    __asm {
        pushad
        push ebx
        push esi
        call th_node
        add esp, 8
        mov g_th_res, eax
        popad
        cmp g_th_res, 1
        je split
        cmp g_th_res, 0
        je leaf
        test ebx, ebx
        jz leaf
        push eax
        mov eax, dword ptr ds:[0x006442ec]
        cmp eax, g_tv_limit
        pop eax
        jg guard
        jmp dword ptr [g_tv_ret_split]
    guard:
        inc g_tv_hits
    leaf:
        jmp dword ptr [g_tv_ret_leaf]
    split:
        push eax
        mov eax, dword ptr ds:[0x006442ec]
        cmp eax, g_tv_limit
        pop eax
        jg guard
        jmp dword ptr [g_th_ret_forced]
    }
}
static void __cdecl th_qt_main(BYTE *cam) {
    int t; DWORD j;
    g_th_main = 1; g_th_eye_ok = 0;
    ((void (__cdecl *)(BYTE *))(DWORD_PTR)NA(0x00490a00))(cam);
    if (g_th_eye_ok) { *(volatile float *)(DWORD_PTR)NA(0x006442f8) = g_th_eye[0]; *(volatile float *)(DWORD_PTR)NA(0x00644300) = g_th_eye[1]; }
    g_th_main = 0; g_th_passes++;
    if (g_tf_far2 > 0.0f && g_th_eye_ok) {                    /* freeze snapshot: a copy of this pass, once the eye moved m metres */
        float mx = g_th_eye[0] - g_tf_eye[0], mz = g_th_eye[1] - g_tf_eye[1];
        if (!g_th_snap_ok || mx * mx + mz * mz > g_tf_move2) {
            th_clear(g_th_snap);
            for (j = 0; j < g_th_nused[g_th_cur]; j++) { th_slot_t *e = &g_th_tab[g_th_cur][g_th_used[g_th_cur][j]]; th_put(g_th_snap, e->k, e->st); }
            g_th_snap_ok = 1; g_tf_eye[0] = g_th_eye[0]; g_tf_eye[1] = g_th_eye[1]; g_th_snaps++;
        }
    }
    t = g_th_prev; g_th_prev = g_th_cur; g_th_cur = t; th_clear(g_th_cur);
}
static void terrain_hyst_report(void) {
    if (!g_th_on) return;
    mlog("  terrain-hyst: %lu main passes, %lu node tests biased, %lu frozen (%lu since the last line), %lu snapshots, %lu parent look-ups missed",
         (unsigned long)g_th_passes, (unsigned long)g_th_biased, (unsigned long)g_th_frozen, (unsigned long)g_th_win_frozen, (unsigned long)g_th_snaps, (unsigned long)g_th_pmiss);
    g_th_win_frozen = 0;
}
static void apply_terrain_hyst(void) {
    static const BYTE old[8] = { 0x85, 0xdb, 0x0f, 0x84, 0xb2, 0x04, 0x00, 0x00 };   /* test ebx,ebx; je 0x4917b0 */
    static const BYTE qtm_old[5] = { 0xe8, 0x57, 0xe9, 0x08, 0x00 };               /* call 0x490a00 at 0x4020a4 (main camera, hardware) */
    BYTE w[8] = { 0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90 }, w5[5] = { 0xe8 }, cur[8];
    char v[32], *c; DWORD n = env_str("I76_TERRAIN_HYST", v, sizeof(v)); int i, ok;
    float hp = n ? (float)atof(v) : 0.0f, ff = 0.0f, fm = 0.0f; LONG rel;
    if (env_str("I76_TERRAIN_FREEZE", v, sizeof(v))) { ff = (float)atof(v); c = strchr(v, ','); fm = c ? (float)atof(c + 1) : 0.0f; }
    if (hp <= 0.0f && ff <= 0.0f) return;
    if (hp < 0.0f || hp > 50.0f || (ff > 0.0f && (ff < 100.0f || fm < 1.0f || fm > 500.0f))) { mlog("  terrain-hyst: I76_TERRAIN_HYST %.1f (0..50) / I76_TERRAIN_FREEZE %.0f,%.0f (>= 100 m, 1..500 m) out of range - not applied", hp, ff, fm); return; }
    for (i = 0; i < 3; i++) {
        g_th_tab[i] = (th_slot_t *)VirtualAlloc(NULL, TH_SLOTS * sizeof(th_slot_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_th_used[i] = (DWORD *)VirtualAlloc(NULL, TH_SLOTS * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!g_th_tab[i] || !g_th_used[i]) { mlog("  terrain-hyst: no memory - not applied"); return; }
    }
    g_th_up = 1.0f / (1.0f + hp / 100.0f); g_th_dn = 1.0f + hp / 100.0f;
    if (ff > 0.0f) { g_tf_far2 = (ff / 5.0f) * (ff / 5.0f); g_tf_move2 = (fm / 5.0f) * (fm / 5.0f); }
    {   static const DWORD sa[1] = { 0x006442ec };
        if (!nitro_reloc_stub((void *)terrain_hyst_stub, sa, 1, 128, "terrain hysteresis stub")) { mlog("  terrain-hyst: NOT applied (stub)"); return; } }
    g_tv_ret_split = NA(0x004912fe); g_tv_ret_leaf = NA(0x004917b0); g_th_ret_forced = NA(0x00491802);
    rel = (LONG)((DWORD_PTR)terrain_hyst_stub - (0x004912f6 + 5)); memcpy(w + 1, &rel, 4);
    if (site_is(0x004912f6, old, 8)) ok = patch_bytes(0x004912f6, old, w, 8, "terrain hysteresis node test");
    else {                                                   /* over the vertex guard: the jmp it wrote (Gold-relative bytes) */
        BYTE vg[8] = { 0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90 }; LONG r2 = (LONG)((DWORD_PTR)terrain_vguard_stub - (0x004912f6 + 5));
        memcpy(vg + 1, &r2, 4);
        memcpy(cur, g_exe == EXE_NITRO ? vg : (const BYTE *)0x004912f6, 8);
        if (cur[0] == 0xe9 && site_is(0x004912f6, cur, 8)) ok = patch_bytes(0x004912f6, cur, w, 8, "terrain hysteresis node test (over the vertex guard)");
        else ok = 0;
    }
    rel = (LONG)((DWORD_PTR)th_qt_main - (0x004020a4 + 5)); memcpy(w5 + 1, &rel, 4);
    ok = ok && patch_bytes(0x004020a4, qtm_old, w5, 5, "terrain hysteresis main QueueTerrain call");
    g_th_on = ok;
    mlog("  terrain-hyst: %s (hysteresis %.0f %%: a split node merges %.2fx, a leaf splits at %.2fx the stock distance; freeze %s)",
         ok ? "on" : "NOT applied", hp, 1.0f / g_th_up, 1.0f / g_th_dn,
         ff > 0.0f ? "beyond the far distance below" : "off");
    if (ok && ff > 0.0f) mlog("  terrain-hyst: freeze: nodes beyond %.0f m keep their first decision until they come within it (snapshot of new nodes every %.0f m)", ff, fm);
}

#include "faredge.c"       /* I76_HAZE / I76_GLIDE_FOG / I76_EDGE_FADE: far-edge fade (far-edge lane 2026-10-23; before terrainmorph.c: its emit wrap chains fe_haze_apply) */
#include "terrainmorph.c"  /* I76_TERRAIN_MORPH / _MORPH_LOG / I76_TERRAIN_FLAT_SPLIT: geomorph + flat-tile split (TERRAIN-MORPH-2026-10-21) */
#include "terrainpops.c"   /* lab: I76_TEX_LEVEL_LOG (texture level switches per pass), I76_SHADE_CENSUS (ZGLIDE vertex colour levels) (terrain-pop lane 2026-10-23) */
static void apply_terrain_lod(void) {
    static const struct { DWORD_PTR a_site, b_site; float a, b; } lv[3] = {
        { 0x4930bb + 6, 0x4930c5 + 6, 6.4f,  0.00390625f },      /* Low */
        { 0x493094 + 6, 0x49308a + 6, 16.0f, 0.0026041667f },    /* Medium (the defaults) */
        { 0x4930a5 + 6, 0x4930af + 6, 40.0f, 0.0017342f },       /* High */
    };
    char v[16], va[16], vb[16]; DWORD n, na, nb; float f, fa, fb; int i, ok = 0;
    /* I76_TERRAIN_LOD_A / I76_TERRAIN_LOD_B (lab, 2026-10-19, lod-sweep lane; owner: "maybe lod isn't the right variable"): scale the
     * split-distance constant A and the height-error constant B on their own (each defaults to I76_TERRAIN_LOD; with LOD unset the
     * other factor is 1). I76_TERRAIN_LOD=24 alone is LOD_A=24 + LOD_B=24 as before. */
    n = env_str("I76_TERRAIN_LOD", v, sizeof(v)); na = env_str("I76_TERRAIN_LOD_A", va, sizeof(va)); nb = env_str("I76_TERRAIN_LOD_B", vb, sizeof(vb));
    if (n == 0 && na == 0 && nb == 0) return;
    f = n ? (float)atof(v) : 1.0f; fa = na ? (float)atof(va) : f; fb = nb ? (float)atof(vb) : f;
    if (f < 1.0f || f > 256.0f || fa < 1.0f || fa > 256.0f || fb < 1.0f || fb > 256.0f) { mlog("  terrain-lod: %s / %s / %s out of range (1..256) - not applied", v, va, vb); return; }
    for (i = 0; i < 3; i++) {
        float a0, b0, a1, b1;
        if (!NA((DWORD)lv[i].a_site) || !NA((DWORD)lv[i].b_site)) { mlog("  terrain-lod: level %d sites not mapped - skipped", i); continue; }
        memcpy(&a0, (const void *)(DWORD_PTR)NA((DWORD)lv[i].a_site), 4); memcpy(&b0, (const void *)(DWORD_PTR)NA((DWORD)lv[i].b_site), 4);   /* the exe's own bits */
        if (a0 < lv[i].a * 0.99f || a0 > lv[i].a * 1.01f || b0 < lv[i].b * 0.99f || b0 > lv[i].b * 1.01f) { mlog("  terrain-lod: level %d constants are not the expected values - skipped", i); continue; }
        a1 = a0 * fa; b1 = b0 / fb;
        ok += patch_bytes(lv[i].a_site, (const BYTE *)&a0, (const BYTE *)&a1, 4, "terrain-lod A");
        ok += patch_bytes(lv[i].b_site, (const BYTE *)&b0, (const BYTE *)&b1, 4, "terrain-lod B");
    }
    mlog("  terrain-lod: x%.2f, %d/6 constants patched (split distance up, height-error threshold down)%s", f, ok, (na || nb) ? "" : "");
    if (na || nb) mlog("  terrain-lod: split A x%.2f, height-error B x%.2f", fa, fb);
    apply_terrain_vguard();
    apply_terrain_hyst();     /* I76_TERRAIN_HYST / I76_TERRAIN_FREEZE (default off) */
}

/* TERRAIN TEXTURE AND OBJECT DETAIL DISTANCE  (I76_TERRAIN_TEX=<1..16>, I76_OBJECT_LOD=<1..16>; off by default;
 * EXPERIMENT, static findings in i76-uncap-lab docs/TEXTURE-AND-OBJECT-LOD.md, 2026-10-03)
 * No mipmaps under Glide: each mission carries five terrain texture sizes (256..16 px) and the leaf setup 0x4923f0
 * picks level = clamp(9 - floor(log2(W*40 / z)), 0, 6); with W = 640 the 256 px tile ends at 50 m. The switch turns
 * `lea eax,[eax+eax*4]; shl eax,3` (W*40) at 0x492458 into `imul eax,eax,40*f`: every boundary moves out by f. No
 * extra vertices or records. Objects: renderer_SelectObjectLod 0x457f40 compares radius against depth/focal times the
 * record's thresholds; both queue passes load 1.0 from 0x4bdf94 for 1/focal, so writing 1/f keeps the detailed mesh
 * (and the un-reduced vehicle) f times farther. More faces through the pools and the 2 MB texture unit: cost unmeasured. */
static void apply_detail_distance(void) {
    char v[16]; DWORD n; float f;
    n = env_str("I76_TERRAIN_TEX", v, sizeof(v));
    if (n) {
        f = (float)atof(v);
        if (f < 1.0f || f > 32.0f) mlog("  terrain-tex: %s out of range (1..32) - not applied", v);   /* 32 since 2026-10-23 (terrain-pop lane sweep 8 / 12 / 16 / 24: the main camera is 1024 wide, so x24 keeps the 256 px level to 1920 m; the same resident textures, W x 40 f fits) */
        else {
            static const BYTE expect[6] = { 0x8d, 0x04, 0x80, 0xc1, 0xe0, 0x03 };
            BYTE want[6] = { 0x69, 0xc0, 0, 0, 0, 0 };
            DWORD k = (DWORD)(40.0f * f + 0.5f);
            memcpy(want + 2, &k, 4);
            if (patch_bytes(0x492458, expect, want, 6, "terrain-tex")) mlog("  terrain-tex: x%.2f (texture level boundaries at %lu/40 x stock distance)", f, (unsigned long)k);
        }
    }
    n = env_str("I76_OBJECT_LOD", v, sizeof(v));
    if (n) {
        f = (float)atof(v);
        if (f < 1.0f || f > 16.0f) mlog("  object-lod: %s out of range (1..16) - not applied", v);
        else {
            float one = 1.0f, inv = 1.0f / f;
            if (patch_bytes(0x4bdf94, (const BYTE *)&one, (const BYTE *)&inv, 4, "object-lod")) mlog("  object-lod: x%.2f (objects and vehicles keep their detailed mesh that much farther)", f);
        }
    }
}

/* SHADOW AND ROAD DISTANCES  (I76_SHADOW_DIST=<1..16>, I76_ROAD_TEX=<1..16>, I76_ROAD_DIST=<metres 450..3000>;
 * off by default; EXPERIMENT, lab docs/TEXTURE-AND-OBJECT-LOD.md). Three .rdata floats, each read only at the sites
 * named (checked 2026-10-03 by scanning the exe for the address): 50.0 at 0x4bdfa0 = shadow view-z limit (0x4583d6,
 * 0x4584a1); 60.0 at 0x4be7bc = near road texture set (0x48ec16); 450.0 at 0x4be7b8 = road segments stop being queued
 * past this midpoint depth whatever the far clip (0x48ead7). */
static void patch_rdata_float(const char *env, DWORD_PTR va, float stock, float lo, float hi, int is_factor, const char *what) {
    char v[16]; DWORD n = env_str(env, v, sizeof(v)); float f, val;
    if (n == 0) return;
    f = (float)atof(v);
    if (f < lo || f > hi) { mlog("  %s: %s out of range (%g..%g) - not applied", what, v, lo, hi); return; }
    val = is_factor ? stock * f : f;
    if (patch_bytes(va, (const BYTE *)&stock, (const BYTE *)&val, 4, what)) mlog("  %s: %.0f -> %.0f m", what, stock, val);
}
static void apply_shadow_road_dist(void) {
    patch_rdata_float("I76_SHADOW_DIST", 0x4bdfa0, 50.0f, 1.0f, 16.0f, 1, "shadow-dist");
    patch_rdata_float("I76_ROAD_TEX", 0x4be7bc, 60.0f, 1.0f, 16.0f, 1, "road-tex");
    patch_rdata_float("I76_ROAD_DIST", 0x4be7b8, 450.0f, 450.0f, 3000.0f, 0, "road-dist");
}

/* DEPTH-BUCKET SPAN-NODE POOL  (automatic with I76_ROAD_DIST > 450 or I76_FAR_CLIP; I76_ROAD_POOL=0 off,
 * =<1..64> pool factor, default 16; lab docs/SOAK-BEST-WIDE-2026-10-03.md, ceiling #4)
 * The depth queue 0x48fe10 hands kind-1 and kind-0xb records to 0x490470(rec, z0, z1, a, b), which links one 16-byte
 * node {f32 a, f32 b, rec, next} into EVERY 1 m bucket between z0 and z1 (bucket table [0x654388]: 0xc000 B =
 * 4096 x {head, tail, count}). Nodes come from a bump cursor [0x6543b8] into one 0x1f400 B block (~8,000 nodes;
 * `push 0x1f400` at 0x48f9d6 in 0x48f9b0, base [0x6543bc]) with no end check; the flush 0x48fac0 rewinds the cursor
 * (0x48fd50) when [0x59c498] says nodes were taken. The only readers walk the lists (0x490030..0x490100), so the
 * pool size is assumed nowhere else. Roads queued out to 1800 m span hundreds of buckets each and ran the cursor off
 * the block (fault exe+0x9051B, t11 at boot 2/2). Fix: pool x16 (2 MB), and the loop head 0x4904cd (`mov eax,
 * [0x654388]`, 5 bytes) calls a stub that, when the next node would pass the pool end or the bucket index is outside
 * the table, leaves the loop through the function's own exit (0x490578: pops, sets the flag, ret): that polygon stays
 * linked into the buckets it already got, the rest are dropped. Refusals and the high water are logged every 600
 * frames (frames counted by wrapping the scene flush calls 0x401e8d / 0x40216d). */
static DWORD g_rp_maxoff = 0x1f400 - 16;    /* last node offset that still fits */
static DWORD g_rp_hw, g_rp_refused, g_rp_lost, g_rp_bucket, g_rp_frames, g_rp_refused_total;
static __declspec(naked) void road_node_stub(void) {            /* replaces `mov eax, [0x654388]` at 0x4904cd */
    __asm {
        cmp ecx, 0xc000 - 12                /* ecx = bucket index x 12 */
        ja bucket_out
        mov eax, dword ptr ds:[0x006543b8]
        sub eax, dword ptr ds:[0x006543bc]
        cmp eax, g_rp_maxoff
        ja pool_full
        cmp eax, g_rp_hw
        jbe take
        mov g_rp_hw, eax
    take:
        mov eax, dword ptr ds:[0x00654388]
        ret
    bucket_out:
        inc g_rp_bucket
        jmp refuse
    pool_full:
        inc g_rp_refused
    refuse:
        add g_rp_lost, edx                  /* buckets this polygon does not get */
        add esp, 4                          /* drop the return into the loop */
        push 0x00490578                     /* the function's exit: pop ebx, pop esi, flag = 1, pop edi, ret */
        ret
    }
}
static int g_rp_on;                         /* the span-node pool is enlarged + guarded (stats lines are about it) */
static void __cdecl road_flush_wrap(void *cam, int flag) {       /* the scene flush calls 0x401e8d / 0x40216d */
    if (g_fs_ms) fs_sample_scene();         /* I76_FRAME_SPIKES: this scene's queue, before the flush rewinds it */
    if (g_fp_on) fp_scene(cam);             /* I76_FLASH_PROBE: per-scene terrain drop detector */
    ((void (__cdecl *)(void *, int))(DWORD_PTR)NA(0x0048fac0))(cam, flag);
    if (!g_rp_on) return;                   /* installed by apply_frame_spikes alone (no road pool): no pool stats */
    if (++g_rp_frames >= 600) {
        g_rp_refused_total += g_rp_refused;
        if (g_logging)
            mlog("  road-pool: 600 frames: refused %lu polygons (%lu past the pool, %lu past bucket 4095), %lu bucket links dropped; node high water %lu KB of %lu KB; refusals since start %lu",
                 (unsigned long)(g_rp_refused + g_rp_bucket), (unsigned long)g_rp_refused, (unsigned long)g_rp_bucket,
                 (unsigned long)g_rp_lost, (unsigned long)((g_rp_hw + 16) >> 10), (unsigned long)((g_rp_maxoff + 16) >> 10),
                 (unsigned long)g_rp_refused_total);
        g_rp_frames = g_rp_hw = g_rp_refused = g_rp_lost = g_rp_bucket = 0;
    }
}
static void apply_road_pool(void) {
    static const BYTE pool_old[5]  = { 0x68, 0x00, 0xf4, 0x01, 0x00 };   /* push 0x1f400 (0x48f9d6) */
    static const BYTE head_old[5]  = { 0xa1, 0x88, 0x43, 0x65, 0x00 };   /* mov eax, [0x654388] (0x4904cd) */
    static const BYTE fl1_old[5]   = { 0xe8, 0x2e, 0xdc, 0x08, 0x00 };   /* call 0x48fac0 (0x401e8d, software scene) */
    static const BYTE fl2_old[5]   = { 0xe8, 0x4e, 0xd9, 0x08, 0x00 };   /* call 0x48fac0 (0x40216d, hardware scene) */
    static const BYTE exit_old[10] = { 0x5b, 0x5e, 0xc7, 0x05, 0x98, 0xc4, 0x59, 0x00, 0x01, 0x00 }; /* 0x490578 */
    char v[16]; DWORD n; int factor = 16, want = 0, ok = 0; float road = 450.0f; DWORD pool; LONG rel;
    BYTE pool_new[5] = { 0x68 }, w[5] = { 0xe8 };
    n = env_str("I76_ROAD_POOL", v, sizeof(v));
    if (n) {
        factor = atoi(v);
        if (factor == 0) { mlog("  road-pool: off (I76_ROAD_POOL=0)"); return; }
        if (factor < 1 || factor > 64) { mlog("  road-pool: I76_ROAD_POOL=%s out of range (0 off, 1..64) - using 16", v); factor = 16; }
        want = 1;
    }
    n = env_str("I76_ROAD_DIST", v, sizeof(v));
    if (n) { road = (float)atof(v); if (road > 450.0f) want = 1; }
    n = env_str("I76_FAR_CLIP", v, sizeof(v));
    if (n) want = 1;
    if (!want) return;
    if (!site_is(0x0048f9d6, pool_old, 5) || !site_is(0x004904cd, head_old, 5) ||
        !site_is(0x00490578, exit_old, 10)) { mlog("  road-pool: sites differ - not applied"); return; }
    {   static const DWORD sa[4] = { 0x00490578, 0x00654388, 0x006543b8, 0x006543bc };
        if (!nitro_reloc_stub((void *)road_node_stub, sa, 4, 128, "span-node guard stub")) { mlog("  road-pool: NOT applied (stub)"); return; } }
    pool = 0x1f400 * (DWORD)factor;
    memcpy(pool_new + 1, &pool, 4);
    if (!patch_bytes(0x0048f9d6, pool_old, pool_new, 5, "span-node pool")) { mlog("  road-pool: pool not enlarged - not applied"); return; }
    g_rp_maxoff = pool - 16;
    rel = (LONG)((DWORD_PTR)road_node_stub - (0x004904cd + 5)); memcpy(w + 1, &rel, 4);
    ok = patch_bytes(0x004904cd, head_old, w, 5, "span-node guard");
    rel = (LONG)((DWORD_PTR)road_flush_wrap - (0x00401e8d + 5)); memcpy(w + 1, &rel, 4);
    n = patch_bytes(0x00401e8d, fl1_old, w, 5, "road-pool frame count (sw)");
    rel = (LONG)((DWORD_PTR)road_flush_wrap - (0x0040216d + 5)); memcpy(w + 1, &rel, 4);
    n += patch_bytes(0x0040216d, fl2_old, w, 5, "road-pool frame count (hw)");
    g_rp_on = 1;
    mlog("  road-pool: span-node pool x%d (%lu KB), end guard %s, stats %s (roads %.0f m)", factor, (unsigned long)(pool >> 10),
         ok ? "on" : "NOT installed", n == 2 ? "every 600 frames" : "OFF (flush sites differ)", road);
}

/* I76_FRAME_SPIKES=<ms> (1 = 250): see FRAME SPIKE LOG in the texture census section. Runs after apply_road_pool: if the
 * road pool did not wrap the two scene flush calls (no I76_FAR_CLIP / I76_ROAD_DIST, e.g. the stock-preset control),
 * wrap them here so the scene counters are still sampled. apply_glide_refresh then turns the census hooks on. */
static void apply_frame_spikes(void) {
    static const BYTE fl1_old[5] = { 0xe8, 0x2e, 0xdc, 0x08, 0x00 };   /* call 0x48fac0 (0x401e8d) */
    static const BYTE fl2_old[5] = { 0xe8, 0x4e, 0xd9, 0x08, 0x00 };   /* call 0x48fac0 (0x40216d) */
    char v[16]; DWORD n = env_str("I76_FRAME_SPIKES", v, sizeof(v)); int ms, k = 0; BYTE w[5] = { 0xe8 }; LONG rel;
    if (n == 0) return;
    ms = atoi(v);
    if (ms <= 1) ms = 250;
    g_fs_ms = (DWORD)ms;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    if (!g_rp_on) {
        rel = (LONG)((DWORD_PTR)road_flush_wrap - (0x00401e8d + 5)); memcpy(w + 1, &rel, 4);
        k = patch_bytes(0x00401e8d, fl1_old, w, 5, "frame-spikes scene sample (sw)");
        rel = (LONG)((DWORD_PTR)road_flush_wrap - (0x0040216d + 5)); memcpy(w + 1, &rel, 4);
        k += patch_bytes(0x0040216d, fl2_old, w, 5, "frame-spikes scene sample (hw)");
    }
    {   char f[8]; DWORD k2 = env_str("I76_FLASH_PROBE", f, sizeof(f));
        if (k2 && (f[0] == '1' || f[0] == '2')) {
            char r[32]; DWORD kr = env_str("I76_FLASH_ROWS", r, sizeof(r)); int a, b, c;
            g_fp_on = f[0] - '0';
            if (kr && sscanf(r, "%d,%d,%d", &a, &b, &c) == 3 && a > 0 && a < 100 && b > 0 && b < 100 && c > 0 && c < 100) { g_fp_rows[0] = a; g_fp_rows[1] = b; g_fp_rows[2] = c; }
            mlog("  flash-probe: on (level %d: terrain counters%s)", g_fp_on, g_fp_on == 2 ? " + pixel rows" : "");
        }
    }
    apply_draw_probe();                       /* I76_DRAW_PROBE=1: terrain clip / insert / draw / triangle census */
    mlog("  frame-spikes: on, threshold %lu ms; scene counters %s; census hooks follow (glide-refresh / tex-census lines)",
         (unsigned long)g_fs_ms, g_rp_on ? "via the road-pool flush wrap" : (k == 2 ? "via its own flush wrap" : "NOT sampled (flush sites differ)"));
}

/* GROUND CLUTTER DISTANCE  (I76_CLUTTER_DIST=<metres 120..2500>, I76_CLUTTER_RISE=<metres 0..100>; off by default;
 * EXPERIMENT, static findings in i76-uncap-lab docs/CLUTTER-AND-MIRROR.md, 2026-10-03)
 * renderer_QueueTerrainClutter 0x45c380 (only with Terrain Detail on): the camera's 100 m cell is snapped to the lower
 * corner (0x4f7180 x, 0x4f7188 z; re-snapped only when the camera leaves it), and every template in list 0x54ac70 is
 * tried once per cell of a 9-entry offsets table 0x4f7190 ({dx,dz} floats, -100..100: the 3x3 block). The cell loop
 * is `mov eax, 0x4f7194` (0x45c4fa first template, 0x45c507 the others) ... `add eax, 8; cmp eax, 0x4f71dc; jl`
 * (0x45c825). Per instance: surface type (0x4927b0) must be enabled in 0x4be070; terrain height minus the camera's
 * ground height must be <= 5.0 (f64 0x4be0c8, one reference 0x45c5bf: only ABOVE the camera's ground is limited);
 * view z <= 120.00001 (f32 0x4be0d0, one reference 0x45c619); 2 m sphere frustum test 0x472c10 (call at 0x45c634).
 * Each passing instance writes one draw record per face (0x490590) into the record pool, 0x5a550 bytes allocated
 * once at startup (push at 0x48f9b5), which has NO bounds check anywhere. Off-map positions are clamped by the
 * terrain lookups (type 5, default height), so a bigger block never reads outside the map arrays.
 * The switch: view z limit -> D; the loop runs over a proxy table rebuilt once per frame (stub at 0x45c4fa, after
 * the engine has snapped the cell) holding only the cells of a (2R+1)^2 block whose centre passes the engine's own
 * transform + side/near/far test with a cell-sized sphere and view z <= D + margin, nearest first; the loop end is
 * a 5-byte call at 0x45c825 to `cmp eax, [g_cl_end]; ret` (flags survive the ret; the next instruction is a mov).
 * Rise limit 5 m -> 5 x D / 120 (the same angle above the horizon), or I76_CLUTTER_RISE. Record pool x8 (2.9 MB) and
 * the frustum call at 0x45c634 refuses further instances once the pool holds more than (pool - stock pool) bytes, so
 * everything queued after clutter keeps at least the stock pool size. Stats every 600 frames with I76MUSIC_LOG. */
#define CL_RMAX 24
static float g_cl_tab[2 * (2 * CL_RMAX + 1) * (2 * CL_RMAX + 1) + 2];
static DWORD g_cl_end;                      /* address one entry past the last used dz, compared by the loop stub */
static signed char g_cl_cand[(2 * CL_RMAX + 1) * (2 * CL_RMAX + 1)][2];
static int g_cl_ncand;
static float g_cl_dist = 120.0f, g_cl_margin = 100.0f;
static DWORD g_cl_limit;                    /* record-pool bytes in use beyond which instances are refused */
static DWORD g_cl_frames, g_cl_cells, g_cl_cells_max, g_cl_tests, g_cl_capped, g_cl_pool_max;
static LONGLONG g_cl_ticks, g_cl_ticks_max, g_cl_qpf;
/* I76_CLUTTER_FADE=<metres> (2026-10-12, with I76_CLUTTER_DIST past 600 m): full density out to the fade distance, then
 * each (template, cell) pair is kept with probability (fade / cell distance)^2, picked by a hash of the template's index
 * and the cell's ABSOLUTE 100 m index (a given bush is either always there or never, whatever the camera does; a pair
 * appears or goes only as its cell crosses the distance that keeps it). Screen-space density stays about constant with
 * distance, like a mesh LOD; the engine's whole per-instance path (two terrain lookups, the transform, the frustum, the
 * mesh transform and lighting, one draw record per face) runs only for kept pairs. The engine loops templates outside,
 * cells inside (0x45c4fa first template, 0x45c507 each next one; 0x45c825 the cell loop end), so each template gets
 * its own filtered copy of the frame's cell table, built when its loop starts. Unset = the table as before. */
static int g_cl_fade_on, g_cl_k, g_cl_ntab;
static float g_cl_fade = 0.0f, g_cl_density = 1.0f;   /* I76_CLUTTER_DENSITY: a global keep probability on every (template, cell) pair = every bush (one instance per pair: 0x45c514 places a template at its cell + the template's offset [esi+0x40/0x50]), the same hash as the fade, so the kept set is nested: a bush kept at density 0.5 beyond the fade is kept nearer too */
static float g_cl_tabT[2 * (2 * CL_RMAX + 1) * (2 * CL_RMAX + 1) + 2];
static int g_cl_ix[(2 * CL_RMAX + 1) * (2 * CL_RMAX + 1)], g_cl_iz[(2 * CL_RMAX + 1) * (2 * CL_RMAX + 1)];
static WORD g_cl_thr[(2 * CL_RMAX + 1) * (2 * CL_RMAX + 1)];
static DWORD g_cl_kept, g_cl_pairs;
/* I76_CLUTTER_ALPHA_FADE=<metres> (render-finish lane 2026-10-23; needs I76_CLUTTER_FADE or _DENSITY): a bush's alpha ramps 0 -> 1 over
 * the N metres after its admission distance - stateless, like the terrain morph: the pair (template, cell) is kept while the cell
 * distance d < d_adm = fade x sqrt(65535 x density / h16) (the keep rule above solved for d; h16 its hash), capped at I76_CLUTTER_DIST,
 * so alpha = clamp((d_adm - d) / N). The cull call 0x45c634 (per instance, its loop's entry pointer at [ebp - 8]) records, for every
 * instance that passes, the record pool's top [0x6543c0] = where its face records start, with its alpha; the hardware flush's
 * polygon draw 0x4260d0 at 0x48fb7e (chained) finds the current record [0x65439c] (type 4 = a mesh face) in those ranges and draws
 * it with faredge.c's held blend (fe_cl_begin / fe_cl_end). Main camera only (the mirror is a software render). */
#define CL_AMAX 16384
static float g_cl_afade = 0.0f, g_cl_dd[(2 * CL_RMAX + 1) * (2 * CL_RMAX + 1)], g_cl_ta[(2 * CL_RMAX + 1) * (2 * CL_RMAX + 1)], g_cla_a[CL_AMAX];
static DWORD g_cla_p[CL_AMAX], g_cla_n, g_cl_ebp, g_cl_pend, g_cl_afr = 0xffffffff, g_cl_next_draw = 0x004260d0;
static int g_cl_amain, g_cl_ntabT; static DWORD g_cl_hookfr;
static DWORD g_cl_arec, g_cl_arec_faded, g_cl_ainst, g_cl_ainst_faded, g_cl_aover;
static void __cdecl clutter_build(BYTE *cam, double ground) {
    float cx = *(float *)(DWORD_PTR)NA(0x004f7180), cz = *(float *)(DWORD_PTR)NA(0x004f7188), v[3];
    int k, n = 0, ix0 = (int)floor(cx / 100.0 + 0.5), iz0 = (int)floor(cz / 100.0 + 0.5);
    double camx = *(double *)(cam + 0x160), camz = *(double *)(cam + 0x170);
    for (k = 0; k < g_cl_ncand; k++) {
        int i = g_cl_cand[k][0], j = g_cl_cand[k][1];
        float *p = ((float *(__cdecl *)(float *, void *, double, double, double))(DWORD_PTR)NA(0x00472d30))
                   (v, cam, cx + 100.0 * i + 50.0, ground, cz + 100.0 * j + 50.0);
        if (p[2] - g_cl_margin > g_cl_dist) continue;
        p[1] = 0.0f;                        /* vertical planes ignored: bushes can sit far below the camera */
        if (((int (__cdecl *)(void *, float *, float))(DWORD_PTR)NA(0x00472c10))(cam, p, 81.0f) > 0 && (i || j)) continue;
        g_cl_tab[2 * n] = 100.0f * i; g_cl_tab[2 * n + 1] = 100.0f * j;
        if (g_cl_fade_on) {
            double dx = cx + 100.0 * i + 50.0 - camx, dz = cz + 100.0 * j + 50.0 - camz, d = sqrt(dx * dx + dz * dz), p;
            g_cl_ix[n] = ix0 + i; g_cl_iz[n] = iz0 + j;
            p = (d <= g_cl_fade ? 1.0 : (g_cl_fade / d) * (g_cl_fade / d)) * g_cl_density; g_cl_dd[n] = (float)d;
            g_cl_thr[n] = (WORD)(p >= 1.0 ? 65535 : (int)(65535.0 * p));
        }
        n++;
    }
    if (n == 0) { g_cl_tab[0] = 0.0f; g_cl_tab[1] = 0.0f; g_cl_ix[0] = ix0; g_cl_iz[0] = iz0; g_cl_thr[0] = 65535; n = 1; }   /* the loop is do-while: one entry minimum */
    g_cl_ntab = n;
    g_cl_end = (DWORD)(DWORD_PTR)&g_cl_tab[1] + 8 * n;
    g_cl_cells += n; if ((DWORD)n > g_cl_cells_max) g_cl_cells_max = n;
}
static void __cdecl clutter_template_table(void) {           /* I76_CLUTTER_FADE: this template's share of the cell table */
    int c, m = 0;
    DWORD kk = (DWORD)g_cl_k * 83492791u;
    for (c = 0; c < g_cl_ntab; c++) {
        DWORD h = 0;
        if (g_cl_thr[c] != 65535 || g_cl_afade > 0.0f) {
            h = ((DWORD)g_cl_ix[c] * 73856093u) ^ ((DWORD)g_cl_iz[c] * 19349663u) ^ kk;
            h ^= h >> 13; h *= 0x5bd1e995u; h ^= h >> 15;
            if (g_cl_thr[c] != 65535 && (h & 0xffff) >= g_cl_thr[c]) continue;
        }
        if (g_cl_afade > 0.0f) {                              /* the pair's admission distance -> its alpha now */
            DWORD h16 = h & 0xffff; double da = h16 ? (double)g_cl_fade * sqrt(65535.0 * g_cl_density / (double)h16) : 1e9, al;
            if (da > g_cl_dist) da = g_cl_dist;
            al = (da - g_cl_dd[c]) / g_cl_afade; g_cl_ta[m] = al >= 1.0 ? 1.0f : al <= 0.0 ? 0.0f : (float)al;
        }
        g_cl_tabT[2 * m] = g_cl_tab[2 * c]; g_cl_tabT[2 * m + 1] = g_cl_tab[2 * c + 1]; m++;
    }
    if (m == 0) { g_cl_tabT[0] = g_cl_tab[0]; g_cl_tabT[1] = g_cl_tab[1]; g_cl_ta[0] = 1.0f; m = 1; }   /* entry 0 is the camera's cell: never faded */
    g_cl_ntabT = m;
    g_cl_pairs += g_cl_ntab; g_cl_kept += m;
    g_cl_end = (DWORD)(DWORD_PTR)&g_cl_tabT[1] + 8 * m;
    g_cl_k++;
}
static __declspec(naked) void clutter_build_fade_stub(void) {   /* replaces `mov eax, 0x4f7194` at 0x45c4fa (fade on) */
    __asm {
        push dword ptr [ebp - 0x30]
        push dword ptr [ebp - 0x34]
        push edi
        call clutter_build
        add esp, 12
        mov g_cl_k, 0
        call clutter_template_table
        mov eax, offset g_cl_tabT
        add eax, 4
        ret
    }
}
static __declspec(naked) void clutter_next_fade_stub(void) {    /* replaces `mov eax, 0x4f7194` at 0x45c507 (fade on) */
    __asm {
        pushad
        call clutter_template_table
        popad
        mov eax, offset g_cl_tabT
        add eax, 4
        ret
    }
}
static __declspec(naked) void clutter_build_stub(void) {        /* replaces `mov eax, 0x4f7194` at 0x45c4fa */
    __asm {
        push dword ptr [ebp - 0x30]         /* camera ground height (f64 at [ebp-0x34]) */
        push dword ptr [ebp - 0x34]
        push edi                            /* camera */
        call clutter_build
        add esp, 12
        mov eax, offset g_cl_tab
        add eax, 4
        ret
    }
}
static __declspec(naked) void clutter_end_stub(void) {          /* replaces `cmp eax, 0x4f71dc` at 0x45c825 */
    __asm {
        cmp eax, g_cl_end
        ret
    }
}
static int __cdecl clutter_cull_wrap(void *cam, float *v, float r) {   /* the call at 0x45c634 */
    DWORD used = *(DWORD *)(DWORD_PTR)NA(0x006543c0) - *(DWORD *)(DWORD_PTR)NA(0x00654398); int res;
    g_cl_tests++;
    if (used > g_cl_limit) { g_cl_capped++; return 1; }
    res = ((int (__cdecl *)(void *, float *, float))(DWORD_PTR)NA(0x00472c10))(cam, v, r);
    if (res <= 0 && g_cl_amain && g_cl_ebp) {                 /* I76_CLUTTER_ALPHA_FADE: this instance's records start at the pool top */
        DWORD e = *(DWORD *)(DWORD_PTR)(g_cl_ebp - 8), b0 = (DWORD)(DWORD_PTR)&g_cl_tabT[1]; int m = e >= b0 ? (int)((e - b0) / 8) : -1;
        if (m >= 0 && m < g_cl_ntabT) {
            if (g_cla_n < CL_AMAX) { g_cla_p[g_cla_n] = *(DWORD *)(DWORD_PTR)NA(0x006543c0); g_cla_a[g_cla_n] = g_cl_ta[m]; g_cla_n++; g_cl_ainst++; if (g_cl_ta[m] < 0.996f) g_cl_ainst_faded++; }
            else g_cl_aover++;
        }
    }
    return res;
}
static __declspec(naked) void clutter_cull_stub(void) {        /* the call at 0x45c634 with the alpha fade: the loop's frame first */
    __asm {
        mov g_cl_ebp, ebp
        jmp clutter_cull_wrap
    }
}
static void *__cdecl clutter_draw_wrap(void *cam, void *v, int n, DWORD tex, DWORD mode) {   /* the hardware flush's polygon draw at 0x48fb7e */
    const BYTE *rec = *(const BYTE * volatile *)(DWORD_PTR)NA(0x0065439c); DWORD r = (DWORD)(DWORD_PTR)rec; float a = 1.0f; void *res; int held = 0;
    if (!g_cl_hookfr) { fe_probe_attach(); fe_alpha_attach(); g_cl_hookfr = g_frame + 1; }   /* hooked a frame before the first fade: ZGLIDE's later requests are seen */
    if (g_cl_afr == g_frame && g_frame > g_cl_hookfr && g_cla_n && r >= g_cla_p[0] && r < g_cl_pend && *(const int *)(rec + 0xc) == 4) {
        DWORD lo = 0, hi = g_cla_n - 1;
        while (lo < hi) { DWORD mid = (lo + hi + 1) >> 1; if (g_cla_p[mid] <= r) lo = mid; else hi = mid - 1; }
        a = g_cla_a[lo]; g_cl_arec++;
        if (a < 0.996f) held = fe_cl_begin(255.0f * a);
        if (held) g_cl_arec_faded++;
    }
    res = ((void *(__cdecl *)(void *, void *, int, DWORD, DWORD))(DWORD_PTR)g_cl_next_draw)(cam, v, n, tex, mode);
    if (held) fe_cl_end();
    return res;
}
static char g_cl_fadetxt[128];
static void terrain_vguard_report(void);
static void __cdecl clutter_frame_wrap(void *cam) {               /* the calls at 0x401e47 / 0x402111 */
    LARGE_INTEGER a, b; DWORD used;
    QueryPerformanceCounter(&a);
    if (g_cl_afade > 0.0f && cam != (void *)(DWORD_PTR)NA(0x00608c80)) { g_cla_n = 0; g_cl_amain = 1; g_cl_ebp = 0; }
    ((void (__cdecl *)(void *))(DWORD_PTR)NA(0x0045c380))(cam);
    if (g_cl_amain) { g_cl_amain = 0; g_cl_pend = *(DWORD *)(DWORD_PTR)NA(0x006543c0); g_cl_afr = g_frame; }
    QueryPerformanceCounter(&b);
    used = *(DWORD *)(DWORD_PTR)NA(0x006543c0) - *(DWORD *)(DWORD_PTR)NA(0x00654398);
    if (used > g_cl_pool_max) g_cl_pool_max = used;
    g_cl_ticks += b.QuadPart - a.QuadPart; if (b.QuadPart - a.QuadPart > g_cl_ticks_max) g_cl_ticks_max = b.QuadPart - a.QuadPart;
    if (++g_cl_frames >= 600) {
        if (g_logging && g_cl_qpf)
            mlog("  clutter: 600 frames: %.0f us avg, %.0f us max; cells %.1f avg, %lu max; instances tested %lu/frame; refused (pool) %lu; record pool high water %lu KB%s",
                 g_cl_ticks * 1e6 / g_cl_qpf / 600.0, g_cl_ticks_max * 1e6 / g_cl_qpf, g_cl_cells / 600.0,
                 (unsigned long)g_cl_cells_max, (unsigned long)(g_cl_tests / 600), (unsigned long)g_cl_capped, (unsigned long)(g_cl_pool_max >> 10),
                 g_cl_fade_on && g_cl_pairs ? (sprintf(g_cl_fadetxt, "; fade kept %.1f%% of template x cell pairs", 100.0 * g_cl_kept / g_cl_pairs), g_cl_fadetxt) : "");
        if (g_logging && g_cl_afade > 0.0f)
            mlog("  clutter-alpha: 600 frames: %lu instances (%lu fading), %lu face records drawn (%lu with the held blend), %lu triangles drawn under it, %lu instances past the list",
                 (unsigned long)g_cl_ainst, (unsigned long)g_cl_ainst_faded, (unsigned long)g_cl_arec, (unsigned long)g_cl_arec_faded, (unsigned long)g_cl_ftris, (unsigned long)g_cl_aover);
        g_cl_ainst = g_cl_ainst_faded = g_cl_arec = g_cl_arec_faded = g_cl_ftris = g_cl_aover = 0;
        terrain_vguard_report();
        terrain_hyst_report();
        terrain_morph_report();
        terrain_pops_report();
        g_cl_frames = g_cl_cells = g_cl_cells_max = g_cl_tests = g_cl_capped = g_cl_pool_max = 0; g_cl_ticks = g_cl_ticks_max = 0; g_cl_kept = g_cl_pairs = 0;
    }
}
static int cl_cmp(const void *a, const void *b) {
    const signed char *p = (const signed char *)a, *q = (const signed char *)b;
    return (p[0] * p[0] + p[1] * p[1]) - (q[0] * q[0] + q[1] * q[1]);
}
static void apply_clutter_dist(void) {
    static const BYTE tab_old[5] = { 0xb8, 0x94, 0x71, 0x4f, 0x00 };     /* mov eax, 0x4f7194 (0x45c4fa, 0x45c507) */
    static const BYTE end_old[5] = { 0x3d, 0xdc, 0x71, 0x4f, 0x00 };     /* cmp eax, 0x4f71dc (0x45c825) */
    static const BYTE cull_old[5] = { 0xe8, 0xd7, 0x65, 0x01, 0x00 };    /* call 0x472c10 (0x45c634) */
    static const BYTE frm1_old[5] = { 0xe8, 0x34, 0xa5, 0x05, 0x00 };    /* call 0x45c380 (0x401e47, software scene) */
    static const BYTE frm2_old[5] = { 0xe8, 0x6a, 0xa2, 0x05, 0x00 };    /* call 0x45c380 (0x402111, hardware scene) */
    static const BYTE pool_old[5] = { 0x68, 0x50, 0xa5, 0x05, 0x00 };    /* push 0x5a550 (0x48f9b5, record pool size) */
    static const DWORD sites[5] = { 0x45c4fa, 0x45c825, 0x45c634, 0x401e47, 0x402111 };
    static const BYTE *olds[5] = { tab_old, end_old, cull_old, frm1_old, frm2_old };
    void *targets[5];
    BYTE pool_new[5] = { 0x68 }, tab2_new[5] = { 0xb8 }, w[5];
    char v[16]; DWORD n = env_str("I76_CLUTTER_DIST", v, sizeof(v));
    float d, rise, five = 5.0f; double rise_old = 5.0, rise_new, stock_z; float z_old, z_new;
    DWORD pool = 0x5a550 * 8, a; int i, j, R, ok = 0;
    LARGE_INTEGER f;
    if (n == 0) return;
    d = (float)atof(v);
    /* 2026-10-12 (owner: "can the brush/bush draw distance ... be as far as the road draw distance"): the cap was 600 m;
     * now the far clip's own cap (2500 m). Past 600 m the record pool grows with the visible area (x8 up to 600 m,
     * x16 to 1200 m, x32 beyond: 2.9 / 5.9 / 11.8 MB, allocated once), so the refusal guard keeps its stock-pool
     * headroom; the candidate block stays capped at 49 x 49 cells (2400 m each way). */
    if (d < 120.0f || d > 2500.0f) { mlog("  clutter-dist: %s out of range (120..2500 m) - not applied", v); return; }
    if (d > 1200.0f) pool = 0x5a550 * 32; else if (d > 600.0f) pool = 0x5a550 * 16;
    rise = five * d / 120.0f;
    n = env_str("I76_CLUTTER_FADE", v, sizeof(v));
    if (n) {
        float fd = (float)atof(v);
        if (fd < 50.0f || fd > 2500.0f) mlog("  clutter-dist: I76_CLUTTER_FADE %s out of range (50..2500 m) - full density everywhere", v);
        else if (fd < d) { g_cl_fade = fd; g_cl_fade_on = 1; }
    }
    n = env_str("I76_CLUTTER_DENSITY", v, sizeof(v));
    if (n) {
        float de = (float)atof(v);
        if (de < 0.1f || de > 1.0f) mlog("  clutter-dist: I76_CLUTTER_DENSITY %s out of range (0.1..1.0) - stock density", v);
        else if (de < 1.0f) { g_cl_density = de; if (!g_cl_fade_on) { g_cl_fade = 1e9f; g_cl_fade_on = 1; } }   /* the filtered-table path, no distance fade */
    }
    n = env_str("I76_CLUTTER_ALPHA_FADE", v, sizeof(v));
    if (n) {
        float af = (float)atof(v);
        if (af == 0.0f) ;
        else if (af < 10.0f || af > 1000.0f) mlog("  clutter-dist: I76_CLUTTER_ALPHA_FADE %s out of range (10..1000 m) - off", v);
        else if (!g_cl_fade_on) mlog("  clutter-dist: I76_CLUTTER_ALPHA_FADE needs I76_CLUTTER_FADE or I76_CLUTTER_DENSITY (the admission rule it fades) - off");
        /* Nitro (nitro-owner lane 2026-10-23): the cull loop 0x45c380 = Nitro 0x45f150 (the same frame, [ebp - 8] the same slot) and the flush draw
         * 0x48fb7e = 0x498b2e (call 0x4878a0 = Gold 0x4260d0) read side by side; every exe address through NA / st_call_site */
        else { g_cl_afade = af; n = env_str("I76_CLUTTER_ALPHA_TRACE", v, sizeof(v)); if (n) g_cl_trace = atoi(v); }
    }
    n = env_str("I76_CLUTTER_RISE", v, sizeof(v));
    if (n) {
        float r = (float)atof(v);
        if (r < 0.0f || r > 100.0f) mlog("  clutter-dist: I76_CLUTTER_RISE %s out of range (0..100 m) - using %.1f", v, rise);
        else rise = r;
    }
    /* every site checked before anything is written: all or nothing */
    for (i = 0; i < 5; i++) if (!site_is(sites[i], olds[i], 5)) { mlog("  clutter-dist: site 0x%06lX differs - not applied", (unsigned long)sites[i]); return; }
    if (!site_is(0x0045c507, tab_old, 5) || !site_is(0x0048f9b5, pool_old, 5) ||
        !site_is(0x004be0c8, (const BYTE *)&rise_old, 8)) { mlog("  clutter-dist: pool/rise/table sites differ - not applied"); return; }
    if (!NA(0x004be0d0)) { mlog("  clutter-dist: view z site not mapped - not applied"); return; }
    memcpy(&z_old, (void *)(DWORD_PTR)NA(0x004be0d0), 4); stock_z = z_old;
    if (stock_z < 119.9 || stock_z > 120.1) { mlog("  clutter-dist: view z constant is not 120 - not applied"); return; }
    /* candidate cells, nearest first; R from the widest view this exe can show (Hor+ hood ~140 deg: ~3x D radially) */
    g_cl_dist = d; g_cl_margin = 71.0f + rise + 20.0f;
    R = (int)ceil((d + g_cl_margin) * 3.0 / 100.0) + 1; if (R > CL_RMAX) R = CL_RMAX;
    g_cl_ncand = 0;
    for (i = -R; i <= R; i++) for (j = -R; j <= R; j++) {
        int ai = i < 0 ? -i : i, aj = j < 0 ? -j : j; ai = ai ? ai - 1 : 0; aj = aj ? aj - 1 : 0;
        if (100.0 * sqrt((double)(ai * ai + aj * aj)) > (d + g_cl_margin) * 3.0) continue;   /* nearest point out of reach */
        g_cl_cand[g_cl_ncand][0] = (signed char)i; g_cl_cand[g_cl_ncand][1] = (signed char)j; g_cl_ncand++;
    }
    qsort(g_cl_cand, g_cl_ncand, sizeof(g_cl_cand[0]), cl_cmp);
    g_cl_tab[0] = 0.0f; g_cl_tab[1] = 0.0f; g_cl_end = (DWORD)(DWORD_PTR)&g_cl_tab[1] + 8;
    g_cl_limit = pool - 0x5a550;
    if (QueryPerformanceFrequency(&f)) g_cl_qpf = f.QuadPart;
    /* record pool first: if this fails nothing else is touched */
    memcpy(pool_new + 1, &pool, 4);
    if (!patch_bytes(0x0048f9b5, pool_old, pool_new, 5, "clutter record pool")) { mlog("  clutter-dist: record pool not enlarged - not applied"); return; }
    targets[0] = g_cl_fade_on ? (void *)clutter_build_fade_stub : (void *)clutter_build_stub; targets[1] = (void *)clutter_end_stub; targets[2] = g_cl_afade > 0.0f ? (void *)clutter_cull_stub : (void *)clutter_cull_wrap;
    targets[3] = (void *)clutter_frame_wrap; targets[4] = (void *)clutter_frame_wrap;
    for (i = 0; i < 5; i++) {
        LONG rel = (LONG)((DWORD_PTR)targets[i] - (sites[i] + 5));
        w[0] = 0xe8; memcpy(w + 1, &rel, 4);
        ok += patch_bytes(sites[i], olds[i], w, 5, "clutter call");
    }
    if (g_cl_fade_on) {                                     /* each next template: call its filtered table builder */
        LONG rel = (LONG)((DWORD_PTR)clutter_next_fade_stub - (0x0045c507 + 5));
        tab2_new[0] = 0xe8; memcpy(tab2_new + 1, &rel, 4);
    } else { a = (DWORD)(DWORD_PTR)&g_cl_tab[1]; memcpy(tab2_new + 1, &a, 4); }
    ok += patch_bytes(0x0045c507, tab_old, tab2_new, 5, "clutter table (later templates)");
    rise_new = rise;
    ok += patch_bytes(0x004be0c8, (const BYTE *)&rise_old, (const BYTE *)&rise_new, 8, "clutter rise limit");
    z_new = d;
    ok += patch_bytes(0x004be0d0, (const BYTE *)&z_old, (const BYTE *)&z_new, 4, "clutter view z limit");
    if (g_cl_afade > 0.0f) {
        if (st_call_site(0x0048fb7e, 0x004260d0, (void *)clutter_draw_wrap, &g_cl_next_draw, "hardware flush polygon draw (clutter alpha fade)"))
            mlog("  clutter-alpha: on - a bush's alpha ramps 0 -> 1 over the %.0f m after its admission distance (fade %.0f m x density %.2f rule, capped at %.0f m); blend SRC_ALPHA / ONE_MINUS_SRC_ALPHA, alpha TEXTURE x ITERATED while its face records draw", g_cl_afade, g_cl_fade < 1e8f ? g_cl_fade : 0.0f, g_cl_density, d);
        else { g_cl_afade = 0.0f; mlog("  clutter-alpha: NOT applied (flush draw site)"); }
    }
    mlog("  clutter-dist: %s, %d/8 sites; view z 120 -> %.0f m, rise limit 5 -> %.1f m, cells from a %dx%d block culled per frame, record pool %lu KB (instances refused past %lu KB)%s",
         ok == 8 ? "on" : "PARTIAL", ok, d, rise, 2 * R + 1, 2 * R + 1, (unsigned long)(pool >> 10), (unsigned long)(g_cl_limit >> 10),
         g_cl_fade_on ? (g_cl_fade < 1e8f ? sprintf(g_cl_fadetxt, "; fade: full density to %.0f m, then x (%.0f / d)^2; density x %.2f", g_cl_fade, g_cl_fade, g_cl_density) : sprintf(g_cl_fadetxt, "; no fade; density x %.2f", g_cl_density), g_cl_fadetxt) : "");
}

/* MIRROR RANGE  (I76_MIRROR_FAR=<metres 100..2500>; off by default; EXPERIMENT, lab docs/CLUTTER-AND-MIRROR.md; 600 -> 2500 on 2026-10-23, mirrordetail.c)
 * The rear mirror is a software render into a private 256x64 8-bit copy of the cockpit mirror texture (ZMIRI101.MAP),
 * re-uploaded as a Glide texture: its resolution is the texture's, not dgVoodoo's. What a constant can change is its
 * range: mirror_Init 0x445380 creates the mirror camera with far = 100 m (`push 0x42c80000` at 0x44553c; fov 30 deg,
 * camera_Create 0x472220 clamps far to 100..100000), so nothing past 100 m shows behind you. */
static void apply_mirror_far(void) {
    static const BYTE old[5] = { 0x68, 0x00, 0x00, 0xc8, 0x42 };
    BYTE want[5] = { 0x68 }; char v[16]; DWORD n = env_str("I76_MIRROR_FAR", v, sizeof(v)); float f;
    if (n == 0) return;
    f = (float)atof(v);
    if (f < 100.0f || f > 2500.0f) { mlog("  mirror-far: %s out of range (100..2500 m) - not applied", v); return; }   /* 600 -> 2500 (rear-mirror lane 2026-10-23: the mirror's own terrain / road queue runs to it; the depth buckets reach 3796 m) */
    memcpy(want + 1, &f, 4);
    if (patch_bytes(0x0044553c, old, want, 5, "mirror far clip")) mlog("  mirror-far: mirror camera far clip 100 -> %.0f m", f);
}

/* WIDESCREEN, HOR+ (I76_ASPECT=<display aspect: 2.389, 21:9, 16:9 or 3440x1440>; off by default; EXPERIMENT stage A,
 * lab docs/WIDESCREEN-FEASIBILITY.md, static only). The frame stays 640x480; the camera sees a wider horizontal field
 * and dgVoodoo must present it at the display aspect (a [Glide] Resolution of that aspect + ScalingMode stretched),
 * so 2D sprites and text come out stretched by D*3/4. camera_Init's fov is horizontal: fx = halfW*zoom/tan(fov/2),
 * fy = -aspect*fx, with the main camera's aspect computed at 0x4059b3 as 4H/(3W) from the 3.0 at 0x4bc510 (one
 * reference). Hor+: aspect constant 4/D, and every fov f -> 2*atan(0.75*D*tan(f/2)): seventeen `push 0x3fc90fda`
 * (pi/2) and the hood view's `push 0x40060a92` (2.094 = 120 deg) at 0x4075a6; the fov clamp max at 0x4be5ac
 * (2.356) is raised to stay above the widest. */
/* HUD SPRITE SQUEEZE (with I76_ASPECT; I76_HUD_SQUEEZE=0 turns it off). The frame is presented stretched by
 * k = 0.75 D, so every 2D sprite comes out k times too wide. renderer_DrawHudSprite 0x45b450 (11 callers, all HUD)
 * builds one screen-space quad in its locals (4 vertices x 6 floats, x at +0/+24/+48/+72) and hands it to the
 * polygon drawer with the single `call 0x4260d0` at 0x45b87a (Glide path; the software paths 0x471fd0 / 0x47aa50
 * are untouched). That call is repointed at hud_quad_wrap, which narrows the quad's x by 1/k about an anchor and
 * calls 0x4260d0; the texture coordinates are unchanged, so the sprite is resampled at full resolution.
 *   anchor = the quad's own centre (default): target-bracket corners 0x45b184/1a0/1bc/1d8, target health bar
 *     0x45b3cf, off-screen target marker ztarg90x 0x45b087 (all in renderer_DrawTargetBrackets 0x45af10; they sit on a
 *     projected 3D position, so each keeps its place and the bracket box keeps the target's projected size), weapon
 *     reticles zretc_1 0x45c19b / 0x45c20c / 0x45c2c4, and the bottom-centred cockpit sprite zcbh3101.tmt 0x45c314.
 *   anchor = a screen side (gauge loop 0x45c0d1 in renderer_DrawInstrumentOverlay 0x45be20, via hud_gauge_wrap):
 *     quads whose centre is in the left third scale about the view's left edge, the right third about its right
 *     edge, the middle about the view centre. Every gauge on one side shares one anchor, so a gauge and anything
 *     layered over it keep their relative layout and the cluster stays against its screen edge.
 * Nothing on this path spans the screen (no fades or full-screen overlays: those are LFB or DirectDraw), so all 11
 * callers are squeezed. LFB text, the Esc menu and the binocular mask are not on this path and stay stretched. */
static float g_hud_inv_k = 1.0f;          /* 1/k; 1 = off */
static int g_hud_side_anchor;             /* set by hud_gauge_wrap around the gauge loop's call */
static int g_hud_log_left = 24;           /* first gauge quads logged (I76MUSIC_LOG) */
static float *__cdecl hud_quad_wrap(float *cam, float *v, float *n, DWORD *tex, float *flags) {
    if (g_hud_inv_k < 1.0f && (DWORD_PTR)n == 4) {
        float xmin = v[0], xmax = v[0], a; int i;
        for (i = 1; i < 4; i++) { if (v[i * 6] < xmin) xmin = v[i * 6]; if (v[i * 6] > xmax) xmax = v[i * 6]; }
        a = 0.5f * (xmin + xmax);
        if (g_hud_side_anchor) {
            BYTE *scr = *(BYTE **)((BYTE *)cam + 0x3c);
            float w = scr ? (float)(*(int *)(scr + 0x24) - *(int *)(scr + 0x1c) + 1) : 640.0f;
            float c = a;
            a = (c < w / 3.0f) ? 0.0f : (c > 2.0f * w / 3.0f) ? w : 0.5f * w;
            if (g_hud_log_left > 0) { g_hud_log_left--; mlog("  hud-squeeze: gauge quad x %.0f..%.0f (view %.0f) -> anchor %.0f", xmin, xmax, w, a); }
        }
        for (i = 0; i < 4; i++) v[i * 6] = a + (v[i * 6] - a) * g_hud_inv_k;
    }
    return ((float *(__cdecl *)(float *, float *, float *, DWORD *, float *))(DWORD_PTR)NA(0x004260d0))(cam, v, n, tex, flags);
}
static void __cdecl hud_gauge_wrap(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g) {
    g_hud_side_anchor = 1;
    ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))(DWORD_PTR)NA(0x0045b450))(a, b, c, d, e, f, g);
    g_hud_side_anchor = 0;
}
static void apply_hud_squeeze(double k) {
    static const struct { DWORD site, target; void *wrap; const char *what; } cs[2] = {
        { 0x0045b87a, 0x004260d0, (void *)hud_quad_wrap,  "HUD sprite quad draw" },
        { 0x0045c0d1, 0x0045b450, (void *)hud_gauge_wrap, "HUD gauge loop sprite call" },
    };
    int i, n = 0;
    if (env_flag("I76_HUD_SQUEEZE", 8, 1) == 0) { mlog("  hud-squeeze: off (I76_HUD_SQUEEZE=0): HUD sprites stay stretched x%.2f", k); return; }
    if (!(k > 1.0)) return;
    for (i = 0; i < 2; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
    }
    if (n) g_hud_inv_k = (float)(1.0 / k);   /* either site alone is safe: the gauge wrap only sets the anchor flag */
    {   /* read back the quad call's target */
        LONG rel; memcpy(&rel, (const void *)(DWORD_PTR)(NA(0x0045b87a) + 1), 4);
        mlog("  hud-squeeze: %d/2 sites, quad call -> %s; HUD sprite quads x 1/%.3f (brackets, reticles, zcbh sprite about their centres; gauges about their screen side)",
             n, (DWORD_PTR)(NA(0x0045b87a) + 5 + rel) == (DWORD_PTR)hud_quad_wrap ? "wrapper" : "STOCK", k);
    }
}

static void apply_aspect(void) {
    static const DWORD push_sites[17] = { 0x405a00, 0x4069e3, 0x406eb8, 0x406faf, 0x4070d5, 0x4079f6, 0x407f46,
        0x4080cb, 0x4083f6, 0x408546, 0x408696, 0x408816, 0x4089a0, 0x408bf0, 0x4090d0, 0x409316, 0x4094e7 };
    char v[24], *sep; DWORD n = env_str("I76_ASPECT", v, sizeof(v));
    double D, k; float three = 3.0f, cst, f90, w90, wcock, f120, w120, clamp0, clamp1; int i, ok = 0;
    if (n == 0) return;
    sep = strchr(v, ':'); if (!sep) sep = strchr(v, 'x'); if (!sep) sep = strchr(v, 'X');
    D = sep ? atof(v) / atof(sep + 1) : atof(v);
    if (!(D >= 1.34 && D <= 3.6)) { mlog("  aspect: %s out of range (1.34..3.6) - not applied", v); return; }
    k = 0.75 * D;
    { static const DWORD f90_bits = 0x3fc90fda; memcpy(&f90, &f90_bits, 4); }   /* the exe's pi/2 is one ulp below (float)(pi/2) */
    if (!NA(0x4075a7) || !NA(0x4be5ac)) { mlog("  aspect: hood fov / clamp sites not mapped - not applied"); return; }
    memcpy(&f120, (const void *)(DWORD_PTR)NA(0x4075a7), 4);
    memcpy(&clamp0, (const void *)(DWORD_PTR)NA(0x4be5ac), 4);
    cst = (float)(4.0 / D);
    w90 = (float)(2.0 * atan(k * tan(f90 / 2.0)));
    w120 = (float)(2.0 * atan(k * tan(f120 / 2.0)));
    clamp1 = w120 + 0.08f > clamp0 ? w120 + 0.08f : clamp0;
    ok += patch_bytes(0x4bc510, (const BYTE *)&three, (const BYTE *)&cst, 4, "aspect constant");
    /* Cockpit view (F1 / V, level-start reset, binocular toggle back: sites 1..4): the cockpit mesh was modelled for
     * 90 deg and its right side ends inside the full Hor+ view (owner, 2026-10-03). I76_ASPECT_COCKPIT_FOV=<deg>
     * (default 0 = full Hor+; e.g. 105 narrows it; 90 = stock width) gives those four sites their own horizontal fov. */
    {
        char c[16]; double deg = 0.0;
        if (env_str("I76_ASPECT_COCKPIT_FOV", c, sizeof(c))) deg = atof(c);
        wcock = (deg <= 0.0) ? w90 : (float)(deg / 57.29578);
        if (wcock < f90) wcock = f90;
        if (wcock > w90) wcock = w90;
    }
    for (i = 0; i < 17; i++) ok += patch_bytes(push_sites[i] + 1, (const BYTE *)&f90, (const BYTE *)((i >= 1 && i <= 4) ? &wcock : &w90), 4, "aspect fov");
    ok += patch_bytes(0x4075a7, (const BYTE *)&f120, (const BYTE *)&w120, 4, "aspect hood fov");
    ok += patch_bytes(0x4be5ac, (const BYTE *)&clamp0, (const BYTE *)&clamp1, 4, "aspect fov clamp");
    mlog("  aspect: D %.3f, %d/20 sites; fov 90 -> %.1f deg (cockpit %.1f), hood 120 -> %.1f deg, clamp %.1f deg (present at %.3f:1, stretched)",
         D, ok, w90 * 57.29578, wcock * 57.29578, w120 * 57.29578, clamp1 * 57.29578, D);
    apply_hud_squeeze(k);
}

/* SOFTWARE RENDERER HIGH RESOLUTION (I76_SW_RES=<W>x<H> or 1; off by default; EXPERIMENT, lab
 * docs/SOFTWARE-RENDERER-HIRES.md). The DirectDraw software driver keeps a 10-entry mode table at 0x4f9e08 (7 dwords:
 * supported flag, 0, 0, display W, H, render W, H) that already holds 1600x1200 (slot 1) and 1280x1024 (slot 2) in
 * every build, but its EnumDisplayModes callback 0x475350 only marks a mode supported when width <= 0x400
 * (`cmp edi,0x400` 0x47535b) and height <= 0x300 (`cmp esi,0x300` 0x475366), at 8 bpp. That is the "1024x768
 * ceiling". The back buffer is a DDraw system-memory surface of the render size (0x475cd3), the span edge table
 * grows on demand (0x473760), and the screen, shadow-mask and binocular bitmaps are allocated from the mode size, so
 * nothing else is sized to 1024x768 by a constant. BUT the span records the rasteriser queues pack one span into a
 * dword: x in bits 21..31 (11 bits), length in bits 10..20 (11 bits), y in bits 0..9 (10 bits) - read back with
 * `and 0x3ff` / `shr 0xa; and 0x7ff` / `shr 0x15` in the edge code 0x473022.. and every SpanFill drawer (0x47cb63 ..).
 * So the real limits are H <= 1024 and W <= 2048. Measured 2026-10-03 (lab game-alt, dgVoodoo DDraw): 1600x1200 draws
 * the 3D view only down to row ~1024 (bottom strip black) and crashed once in two runs (heap fault in ntdll).
 *   I76_SW_RES=1        lifts the enum limits to 2048 x 1024: the stock 1280x1024 slot becomes selectable
 *                       (Options -> Graphic Detail -> Screen Resolution) when DirectDraw enumerates it at 8 bpp;
 *                       1600x1200 stays rejected.
 *   I76_SW_RES=1584x1024 also rewrites slot 1 (1600x1200) to that size and its menu label (0x4fc794 -> our string);
 *                       W <= 2048 (a multiple of 8), H <= 1024. 1584x1024 is the MacBook panel's 1.547 aspect.
 * The mode index persists as byte 0x40 of I76PLYR.DEF (1 = slot 1). The camera still assumes a 4:3 frame
 * (aspect 4H/3W): for a non-4:3 size presented with square pixels add I76_ASPECT=<W>:<H> (Hor+). */
static char g_swres_label[16];
static void apply_sw_res(void) {
    static const DWORD lim_w_stock = 0x400, lim_h_stock = 0x300, lim_w_new = 0x800, lim_h_new = 0x400;
    static const DWORD slot1_stock[4] = { 1600, 1200, 1600, 1200 };
    char v[24], *sep; DWORD n = env_str("I76_SW_RES", v, sizeof(v)); int ok = 0;
    if (n == 0 || v[0] == '0') return;
    ok += patch_bytes(0x47535d, (const BYTE *)&lim_w_stock, (const BYTE *)&lim_w_new, 4, "sw-res: enum width limit");
    ok += patch_bytes(0x475368, (const BYTE *)&lim_h_stock, (const BYTE *)&lim_h_new, 4, "sw-res: enum height limit");
    sep = strchr(v, 'x'); if (!sep) sep = strchr(v, 'X'); if (!sep) sep = strchr(v, ':');
    if (sep) {
        DWORD w = (DWORD)atoi(v), h = (DWORD)atoi(sep + 1), want[4];
        DWORD label_stock = 0x4fd7a8, label_new = (DWORD)(DWORD_PTR)g_swres_label;
        if (w < 320 || h < 200 || w > 2048 || h > 1024 || (w & 7)) {
            mlog("  sw-res: %s rejected (320..2048 x 200..1024, width a multiple of 8: span records hold y in 10 bits) - limits only", v);
        } else {
            want[0] = w; want[1] = h; want[2] = w; want[3] = h;
            wsprintfA(g_swres_label, "%lux%lu", (unsigned long)w, (unsigned long)h);
            ok += patch_bytes(0x4f9e24 + 12, (const BYTE *)slot1_stock, (const BYTE *)want, 16, "sw-res: mode slot 1");
            ok += patch_bytes(0x4fc794, (const BYTE *)&label_stock, (const BYTE *)&label_new, 4, "sw-res: slot 1 label");
        }
    }
    {   /* read back */
        const DWORD *e = (const DWORD *)(0x4f9e24 + 12);
        mlog("  sw-res: %d sites; enum limits %lu x %lu; slot 1 = %lux%lu (render %lux%lu), slot 2 = %lux%lu",
             ok, (unsigned long)*(const DWORD *)0x47535d, (unsigned long)*(const DWORD *)0x475368,
             (unsigned long)e[0], (unsigned long)e[1], (unsigned long)e[2], (unsigned long)e[3],
             (unsigned long)e[7], (unsigned long)e[8]);
    }
}

/* SECOND INSTANCE  (I76_MULTI_INSTANCE=1; off by default)
 * WinMain 0x402ca0: FindWindowA(class 0x4c2680, NULL); a hit restores that window (ShowWindow 9) and returns 0, so a
 * second copy exits at once (measured 2026-10-03: second process exit code 0). The switch turns `je 0x402ccd`
 * (found nothing -> carry on) into `jmp`, for two copies on one PC (local multiplayer tests). */
static void apply_multi_instance(void) {
    static const BYTE expect[2] = { 0x74, 0x1c }, want[2] = { 0xeb, 0x1c };
    if (!env_present("I76_MULTI_INSTANCE")) return;
    if (patch_bytes(0x402caf, expect, want, 2, "multi-instance"))   /* patch_bytes logs only a mismatch */
        mlog("  multi-instance: single-instance check skipped (0x402caf je -> jmp; read back %s)",
             *(const BYTE *)(DWORD_PTR)NA(0x402caf) == 0xeb ? "ok" : "FAILED");
}

/* NO MINIMISE ON DEACTIVATION  (I76_NO_MINIMIZE=1; off by default)
 * The game minimises ITSELF when it loses activation: WndProc WM_ACTIVATEAPP (0x1c) with wParam 0 (0x404aba) calls
 * ShowWindow(hwnd, SW_MINIMIZE) (`6a 06 51 ff 15 40 c3 4b 00` at 0x404acc), then clears the active flag [0x504c1c]
 * and sets NORMAL_PRIORITY_CLASS. Not dgVoodoo, not u32x (static read 2026-10-05; same bytes in the AiO 85de44a7,
 * i76_pristine_fix 58d9dec0 and sandbox 9a232dcc exes). Two windowed copies side by side (Nucleus) each deactivate
 * the other, and a minimised host stops answering the joiner's search (nucleus-coop README, first run). The main
 * loop keeps running frames while inactive when 0x452d20 reports a net game (0x4039e4), so only the minimise is in
 * the way. The switch turns `push 6` into `push 8` (SW_SHOWNA: show in the current state, no activation; a no-op
 * for a visible window). The active flag, the priority call and the mouse release are unchanged. */
static void apply_no_minimize(void) {
    static const BYTE expect[9] = { 0x6a, 0x06, 0x51, 0xff, 0x15, 0x40, 0xc3, 0x4b, 0x00 };
    static const BYTE want[9]   = { 0x6a, 0x08, 0x51, 0xff, 0x15, 0x40, 0xc3, 0x4b, 0x00 };
    char v[8]; DWORD k = env_str("I76_NO_MINIMIZE", v, sizeof(v));
    if (env_str("I76_KEEP_ACTIVE", v, sizeof(v)) && v[0] != '0') {
        g_keep_active = 1; install_frame_hook();
        mlog("  keep-active: the active flag is set again on every frame (an unattended run keeps ticking without the foreground)");
        k = 1; v[0] = '1';
    }
    if (k == 0 || v[0] == '0') return;
    if (patch_bytes(0x404acc, expect, want, 9, "no-minimize"))
        mlog("  no-minimize: WM_ACTIVATEAPP 0 no longer minimises the window (0x404acc push 6 -> push %d; read back %s)",
             *(const BYTE *)(DWORD_PTR)NA(0x404acd), *(const BYTE *)(DWORD_PTR)NA(0x404acd) == 0x08 ? "ok" : "FAILED");
}

/* JOYSTICK ROUTING  (I76_JOY_MAP, I76_JOY_SYNTH; both off by default; i76.exe's WINMM imports only)
 * The engine names winmm id k "joystick<k+1>" (create 0x44ff90, "joystick%d" with id+1) and polls it with
 * joyGetPosEx(id) (0x4508df). Its open step 0x450490 does NOT use the id for its caps and first poll: it passes
 * (id != 0), i.e. winmm id 0 for joystick1 and winmm id 1 for EVERY other slot (`setne cl` at 0x4504b4; static
 * read 2026-10-05). So joystick1 and joystick2 open normally, while joystick3+ open only when winmm id 1 is also
 * present, and take id 1's axis ranges. For two game copies on one PC (Nucleus), each copy binds joystick1 and this
 * switch routes engine id 0 to that copy's own pad:
 *   I76_JOY_MAP=0=4          engine id 0 -> winmm id 4 (pairs "a=b", comma-separated, ids 0..15)
 *   I76_JOY_SYNTH=1:0        TEST ONLY: (after the map) winmm id 1 reports a synthetic 2-axis, 4-button pad with
 *                            X = 0 (full left), Y centred; ":<x>" is 0..65535. Several "id:x" comma-separated.
 * Each change of a slot's result code is logged ("joy: ..."), so a run shows which ids the engine opened/polled. */
typedef MMRESULT (WINAPI *joyCapsFn)(UINT_PTR, LPJOYCAPSA, UINT);
typedef MMRESULT (WINAPI *joyPosFn)(UINT, LPJOYINFOEX);
static joyCapsFn real_joyGetDevCapsA;
static joyPosFn  real_joyGetPosEx;
static int  g_joy_map[16];
static int  g_joy_synth[16];          /* -1 = real device; else synthetic X value */
static LONG g_joy_lastrc[2][16];      /* [caps/pos][engine id], logged on change */
static LONG g_joy_polls[16];
static UINT joy_route(UINT id) { return id < 16 ? (UINT)g_joy_map[id] : id; }
static void joy_note(int kind, UINT id, UINT real, MMRESULT rc) {
    if (id >= 16) return;
    if (kind) InterlockedIncrement(&g_joy_polls[id]);
    if (InterlockedExchange(&g_joy_lastrc[kind][id], (LONG)rc) != (LONG)rc)
        mlog("  joy: %s engine id %u (joystick%u) -> winmm id %u%s: rc %u (poll #%ld)", kind ? "joyGetPosEx" : "joyGetDevCapsA",
             id, id + 1, real, (real < 16 && g_joy_synth[real] >= 0) ? " [synthetic]" : "", (unsigned)rc, g_joy_polls[id]);
}
static MMRESULT WINAPI hook_joyGetDevCapsA(UINT_PTR id, LPJOYCAPSA c, UINT sz) {
    UINT real = joy_route((UINT)id); MMRESULT rc;
    if (real < 16 && g_joy_synth[real] >= 0) {
        if (!c || sz < sizeof(JOYCAPSA)) rc = MMSYSERR_INVALPARAM;
        else {
            memset(c, 0, sz); c->wMid = 0x0FFF; c->wPid = 0x0076; lstrcpynA(c->szPname, "i76 synthetic pad", 32);
            c->wXmax = c->wYmax = c->wZmax = c->wRmax = c->wUmax = c->wVmax = 65535;
            c->wNumButtons = 4; c->wPeriodMin = 10; c->wPeriodMax = 1000; c->wMaxAxes = 6; c->wNumAxes = 2; c->wMaxButtons = 32;
            rc = JOYERR_NOERROR;
        }
    } else rc = real_joyGetDevCapsA ? real_joyGetDevCapsA(real, c, sz) : MMSYSERR_NODRIVER;
    joy_note(0, (UINT)id, real, rc);
    return rc;
}
static MMRESULT WINAPI hook_joyGetPosEx(UINT id, LPJOYINFOEX j) {
    UINT real = joy_route(id); MMRESULT rc;
    if (real < 16 && g_joy_synth[real] >= 0) {
        if (!j) rc = MMSYSERR_INVALPARAM;
        else {
            DWORD sz = j->dwSize, fl = j->dwFlags;
            memset(j, 0, sizeof(*j)); j->dwSize = sz; j->dwFlags = fl;
            j->dwXpos = (DWORD)g_joy_synth[real]; j->dwYpos = j->dwZpos = j->dwRpos = j->dwUpos = j->dwVpos = 32767;
            j->dwPOV = JOY_POVCENTERED;
            rc = JOYERR_NOERROR;
        }
    } else rc = real_joyGetPosEx ? real_joyGetPosEx(real, j) : MMSYSERR_NODRIVER;
    joy_note(1, id, real, rc);
    if (g_st_joy_rec) st_joy_note(id, j, rc);                /* I76_SIM_TICK_INPUT: what the tick's input_UpdateControls read (simtick.c) */
    return rc;
}
static void apply_joy_routing(HMODULE exe) {
    char v[128]; DWORD n; int i, any = 0; char *p;
    for (i = 0; i < 16; i++) { g_joy_map[i] = i; g_joy_synth[i] = -1; g_joy_lastrc[0][i] = g_joy_lastrc[1][i] = -1; }
    n = env_str("I76_JOY_MAP", v, sizeof(v));
    if (n) for (p = v; *p; ) {
        int a = atoi(p), b; char *eq = strchr(p, '='); if (!eq) break; b = atoi(eq + 1);
        if (a >= 0 && a < 16 && b >= 0 && b < 16) { g_joy_map[a] = b; any = 1; mlog("  joy-map: engine id %d (joystick%d) -> winmm id %d", a, a + 1, b); }
        p = strchr(eq, ','); if (!p) break; p++;
    }
    n = env_str("I76_JOY_SYNTH", v, sizeof(v));
    if (n) for (p = v; *p; ) {
        int a = atoi(p), x = 0; char *c = p; while (*c && *c != ',' && *c != ':') c++;
        if (*c == ':') x = atoi(c + 1);
        if (a >= 0 && a < 16) { g_joy_synth[a] = x < 0 ? 0 : (x > 65535 ? 65535 : x); any = 1; mlog("  joy-synth: winmm id %d is a synthetic pad, X = %d (TEST ONLY)", a, g_joy_synth[a]); }
        p = strchr(p, ','); if (!p) break; p++;
    }
    if (!any && !g_st_joy_on) return;                        /* the hooks also serve the whole-sim tick's joystick watch (simtick.c) */
    real_joyGetDevCapsA = (joyCapsFn)patch_iat(exe, g_exe == EXE_NITRO ? "WIN32.dll" : "WINMM.dll", "joyGetDevCapsA", hook_joyGetDevCapsA);
    real_joyGetPosEx    = (joyPosFn)patch_iat(exe, g_exe == EXE_NITRO ? "WIN32.dll" : "WINMM.dll", "joyGetPosEx", hook_joyGetPosEx);
    mlog("  joy-routing: IAT joyGetDevCapsA old=%p joyGetPosEx old=%p%s%s", (void *)real_joyGetDevCapsA, (void *)real_joyGetPosEx,
         (real_joyGetDevCapsA && real_joyGetPosEx) ? "" : " - NOT HOOKED (no WINMM import: i76fix exe?)", any ? "" : " (for the sim-tick joystick watch; ids unrouted)");
    simtick_joy_ready(real_joyGetPosEx ? hook_joyGetPosEx : 0, real_joyGetDevCapsA ? hook_joyGetDevCapsA : 0);
}

static void apply_flame_census(void) {
    BYTE *p = (BYTE *)0x004357c3, w[5] = { 0xE8 };
    LONG rel; DWORD tgt;
    if (env_flag("I76_FLAME_CENSUS", 8, 0) != 1) return;
    {   char v[96]; BYTE *q = (BYTE *)0x0044449b, o[5], w2[5] = { 0xE8 }; LONG r2;
        if (env_str("I76_FLAME_PROBE_AT", v, sizeof(v)) && sscanf(v, "%f,%f,%f", &g_fhp_at[0], &g_fhp_at[1], &g_fhp_at[2]) == 3 && q[0] == 0xE8) {
            memcpy(&r2, q + 1, 4);
            if (0x004444a0 + (DWORD)r2 == 0x004354c0) {
                memcpy(o, q, 5); r2 = (LONG)((DWORD_PTR)flame_hit_probe - 0x004444a0); memcpy(w2 + 1, &r2, 4);
                g_fhp_on = patch_bytes(0x0044449b, o, w2, 5, "flamer hit test call (probe)");
                {   BYTE *q2 = (BYTE *)0x00435691, o2[5], w3[5] = { 0xE8 }; LONG r3;   /* the narrow test inside the hit test */
                    memcpy(&r3, q2 + 1, 4);
                    if (q2[0] == 0xE8 && 0x00435696 + (DWORD)r3 == 0x0043d770) {
                        memcpy(o2, q2, 5); r3 = (LONG)((DWORD_PTR)flame_narrow_probe - 0x00435696); memcpy(w3 + 1, &r3, 4);
                        mlog("  flame-census: narrow-test probe at 0x435691: %s", patch_bytes(0x00435691, o2, w3, 5, "flamer narrow test call (probe)") ? "on" : "NOT patched");
                    } else if (q2[0] == 0xE8 && 0x00435696 + (DWORD)r3 == (DWORD)(DWORD_PTR)flame_narrow_call) {   /* the breakable-box flame wrapper is in: chain */
                        g_flame_narrow_next = (DWORD)(DWORD_PTR)flame_narrow_probe;
                        mlog("  flame-census: narrow-test probe at 0x435691: on (chained behind the breakable-box flame wrapper)");
                    }
                }
                mlog("  flame-census: probe at %.1f,%.1f,%.1f: %s", g_fhp_at[0], g_fhp_at[1], g_fhp_at[2], g_fhp_on ? "on" : "NOT patched");
            }
        }
    }
    {   /* hit explosions in the stock loop: a pass-through counter at 0x44471d (the grid / tick wrapper counts its own) */
        BYTE *q = (BYTE *)0x0044471d, o[5], w2[5] = { 0xE8 }; LONG r2;
        if (q[0] == 0xE8) {
            memcpy(&r2, q + 1, 4);
            if (0x00444722 + (DWORD)r2 == 0x0049ead0) {
                memcpy(o, q, 5); r2 = (LONG)((DWORD_PTR)flame_expl_count - 0x00444722); memcpy(w2 + 1, &r2, 4);
                mlog("  flame-census: hit explosions counted at 0x44471d (stock): %s", patch_bytes(0x0044471d, o, w2, 5, "flamer hit explosion (census)") ? "on" : "NOT patched");
            }
        }
    }
    if (p[0] != 0xE8) { mlog("  flame-census: 0x4357c3 is not a call - off"); return; }
    memcpy(&rel, p + 1, 4); tgt = 0x004357c8 + (DWORD)rel;
    {   /* update cadence: the mirror pass's two calls always, the main pass's two when nothing else wraps them */
        static const DWORD ms[2] = { 0x004458fe, 0x00445968 }, mn[2] = { 0x00401e23, 0x004020e8 };
        int i, nm = 0, nn = 0;
        for (i = 0; i < 2; i++) {
            BYTE *q = (BYTE *)(DWORD_PTR)ms[i], o[5], w2[5] = { 0xE8 }; LONG r2;
            if (q[0] != 0xE8) continue;
            memcpy(&r2, q + 1, 4); if (ms[i] + 5 + (DWORD)r2 != 0x00443fc0) continue;
            memcpy(o, q, 5); r2 = (LONG)((DWORD_PTR)flame_census_mirror - (ms[i] + 5)); memcpy(w2 + 1, &r2, 4);
            nm += patch_bytes(ms[i], o, w2, 5, "flamer update, mirror (census)") && memcmp(q, w2, 5) == 0;
        }
        for (i = 0; i < 2; i++) {
            BYTE *q = (BYTE *)(DWORD_PTR)mn[i], o[5], w2[5] = { 0xE8 }; LONG r2;
            if (q[0] != 0xE8) continue;
            memcpy(&r2, q + 1, 4); if (mn[i] + 5 + (DWORD)r2 != 0x00443fc0) { g_flame_wrapped = 1; continue; }   /* the grid / tick wrapper counts */
            memcpy(o, q, 5); r2 = (LONG)((DWORD_PTR)flame_census_main - (mn[i] + 5)); memcpy(w2 + 1, &r2, 4);
            nn += patch_bytes(mn[i], o, w2, 5, "flamer update, main (census)") && memcmp(q, w2, 5) == 0;
        }
        mlog("  flame-census: update cadence counted at %d/2 mirror and %d/2 main-pass calls (%s)", nm, nn, g_flame_wrapped ? "main pass wrapped by the 20 Hz grid / tick" : "stock");
    }
    if (tgt == (DWORD)(DWORD_PTR)flame_damage_wrap) { g_flc_on = 1; install_frame_hook(); mlog("  flame-census: on (counted in the flamer damage wrapper of the 20 Hz grid / sim tick)"); return; }
    if (tgt != 0x004a8240) { mlog("  flame-census: 0x4357c3 calls 0x%08lX (not stock, not ours) - off", (unsigned long)tgt); return; }
    rel = (LONG)((DWORD_PTR)flame_census_wrap - 0x004357c8); memcpy(w + 1, &rel, 4);
    {   BYTE o[5]; memcpy(o, p, 5);
    if (patch_bytes(0x004357c3, o, w, 5, "flamer damage (census)") && memcmp(p, w, 5) == 0) {
        g_flc_on = 1; install_frame_hook();
        mlog("  flame-census: on (pass-through counting wrapper at 0x4357c3, read back; stock frame loop)");
    } else mlog("  flame-census: patch did not verify - off");
    }
}

/* NITRO (nitro.exe 28b8ae27; nitro.c, docs/records/NITRO-PORT-2026-10-21.md): only the switches ported so far. Each
 * apply_* below runs the same code as on Gold; its sites go through the site map (patch_bytes -> nitro_patch_bytes, NA)
 * and a site that does not verify turns its feature off with a log line. Everything not listed here stays off on Nitro. */
static void cwd_fix(void) {
    char cwd[MAX_PATH];
    if (env_flag("I76_CWD_FIX", 8, 1) != 0) {
        GetCurrentDirectoryA(sizeof(cwd), cwd);
        if (lstrcmpiA(cwd, g_dir) != 0) {
            BOOL ok = SetCurrentDirectoryA(g_dir);
            mlog("  cwd-fix: current directory was \"%s\", %s \"%s\"", cwd, ok ? "now" : "FAILED to set", g_dir);
        }
    }
}
static void nitro_dllmain(void) {
    HMODULE exe = GetModuleHandleA(NULL);
    nitro_table_check();
    nitro_terrain_addrs();    /* nitro.c g_ta_*: the terrain renderer's globals for the terrain-look features (nitro-owner lane 2026-10-23) */
    load_orig();              /* Nitro's strlkup.dll is Gold's (NITRO-VS-RETAIL s.4) */
    apply_crash_log();
    nitro_pit_skip();         /* Wine: the PIT CPU-speed probe's privileged instructions are fatal (nitro.c) */
    apply_mute();
    cwd_fix();
    apply_mission_launch();   /* I76_MISSION / I76_SKIP_MOVIES */
    apply_multi_instance();
    apply_no_minimize();      /* also I76_KEEP_ACTIVE */
    apply_terrain_lod();      /* I76_TERRAIN_LOD / _A / _B (+ vertex guard, I76_TERRAIN_HYST / _FREEZE) */
    apply_terrain_morph();    /* I76_TERRAIN_MORPH (+ _STATELESS / _SHADE / _BIG / _NEAR / _LOG); I76_TERRAIN_FLAT_SPLIT refused (0x491556 differs) */
    apply_detail_distance();  /* I76_TERRAIN_TEX, I76_OBJECT_LOD */
    apply_shadow_road_dist(); /* I76_SHADOW_DIST, I76_ROAD_TEX, I76_ROAD_DIST */
    apply_road_pool();        /* with I76_ROAD_DIST > 450 or I76_FAR_CLIP */
    apply_clutter_dist();     /* I76_CLUTTER_DIST (+ _FADE, _RISE) */
    apply_mirror_far();       /* I76_MIRROR_FAR */
    apply_cam_ground_fix();   /* I76_CAM_GROUND_FIX */
    apply_terrain_hull_fix(); /* I76_TERRAIN_HULL_FIX */
    apply_aspect();           /* I76_ASPECT (Hor+; + HUD squeeze) */
    apply_ref_fps();
    apply_hires_clock();
    apply_breakable_box();    /* I76_BREAKABLE_BOX=1..4 (+ the sign-post sweep / deferral, the flamer's sphere) */
    apply_breakable_speed();  /* with I76_BREAKABLE_BOX >= 2 */
    apply_frame_cap();
    apply_fps_log();
    apply_frame_log();
    apply_fix_health_pct();   /* I76_FIX_HEALTH_PCT */
    apply_fix_label_table();  /* I76_FIX_LABEL_TABLE */
    apply_far_clip();         /* I76_FAR_CLIP (+ render pools x16) */
    apply_telemetry();        /* I76_TELEMETRY (snapshot, shot / explosion / impact events; I76_SOUND_EVENTS / I76_DAMAGE_EVENTS not ported) */
    apply_trainer();          /* always on (I76_TRAINER=0 off): Local\I76Trainer<suffix> */
    apply_simtick();          /* I76_SIM_TICK_MS (whole-sim tick; the 12 gates on Nitro's main loop, sites_nitro.h / manual_sites.txt) */
    apply_sky_mirror();       /* opt-in: I76_SKY_MIRROR=0 (after the tick: it may share the cloud constants) */
    apply_mirror_detail();    /* I76_MIRROR_EVERY / _LOD / _TEX / _PAL / _M16 (+ the lab dump / mode); Nitro's own refresh gate (mirrordetail.c) */
    apply_terrain_pops();     /* I76_SHADE_SMOOTH (the 17 emitters); the lab instruments stay Gold-only */
    apply_far_edge();         /* I76_GLIDE_FOG (+ _ALPHA), I76_HAZE; I76_EDGE_FADE refused (after the morph: chains its emit wrap) */
    apply_jump_nose();        /* opt-in: I76_JUMP_NOSE=<0.5..1> (one site inside 0x43a5d0, in the site map) */
    apply_sign_sound_restart(); /* I76_SIGN_SOUND_RESTART (polish.c; the stop / name through NA) */
    apply_fade_no_flip();     /* I76_FADE_NO_FLIP (polish.c) */
    apply_menu_keys();        /* default on: I76_MENU_KEYS (after the tick: chains its input gate) */
    apply_menu_draw();        /* default on: I76_MENU_DRAW (WndProc 0x404a7d -> 0x433bed, manual_sites.txt) */
    apply_font_private();     /* default on: I76_FONT_PRIVATE (nitro.exe imports GDI32 AddFontResourceA / RemoveFontResourceA) */
    nitro_font_guard();       /* default on: I76_NITRO_FONT_GUARD (nitro.c: the mission font free that faults on the second mission) */
    {   /* MUSIC (I76_MUSIC_NITRO=0 keeps GOG's own WIN32.dll / audiere CD emulation): the same hooks as Gold, on the exe's
         * WIN32.dll slots; playback through the system winmm's mpegvideo as on Gold; the virtual disc ends at the highest
         * music\N.mp3 present */
        if (env_flag("I76_MUSIC_NITRO", 8, 1) != 0) {
            char p[MAX_PATH]; int k;
            for (k = LAST_TRACK_MAX; k > FIRST_TRACK; k--) {
                _snprintf(p, sizeof p, "%s\\music\\%d.mp3", g_dir, k); p[sizeof p - 1] = 0;
                if (GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES) break;
            }
            g_last_track = k;
            mlog("--- strlkproxy: IAT patch WIN32.dll!mciSendCommandA old=%p new=%p (virtual disc tracks %d..%d) ---",
                 patch_iat(exe, "WIN32.dll", "mciSendCommandA", hook_mciSendCommandA), (void *)hook_mciSendCommandA, FIRST_TRACK, g_last_track);
            mlog("  aux patches (WIN32.dll): auxGetNumDevs=%p auxGetDevCapsA=%p auxSetVolume=%p",
                 patch_iat(exe, "WIN32.dll", "auxGetNumDevs",  hook_auxGetNumDevs),
                 patch_iat(exe, "WIN32.dll", "auxGetDevCapsA", hook_auxGetDevCapsA),
                 patch_iat(exe, "WIN32.dll", "auxSetVolume",   hook_auxSetVolume));
            if (env_flag("I76_MUSIC_GUARD", 8, 1) != 0) { CloseHandle(CreateThread(NULL, 0, music_guard, NULL, 0, NULL)); mlog("  music-guard: on"); }
            music_opts();
        } else mlog("  music: I76_MUSIC_NITRO=0 - GOG's WIN32.dll plays the CD tracks");
    }
    apply_glide_refresh();    /* I76_GLIDE_REFRESH / I76_ZGLIDE_TMUFIX / I76_GLIDE_GAMMA (LoadLibraryA hook; Nitro ZGLIDE offsets) */
    apply_cursor_map();       /* I76_CURSOR_MAP (nitro.exe's and NITSHELL.DLL's USER32 slots; Nitro has no u32x) */
    apply_joy_routing(exe);   /* Nitro's joyGetPosEx / joyGetDevCapsA are WIN32.dll imports */
    apply_nitro_mp();         /* I76_NITRO_MP (ARENA+: nitro_mp.c / nitro_ai.c; inert outside an ARENA+ session) */
    if (p_LoadLibraryA) {     /* the LoadLibraryA hook is in: watch for DxWnd taking the slot (nitro_shell_watch) */
        HANDLE th = CreateThread(NULL, 0, nitro_shell_watch, NULL, 0, NULL);
        mlog("  nitro shell watch: %s", th ? "on (NITSHELL / ZGLIDE attach if the LoadLibraryA hook never sees them)" : "NOT started");
        if (th) CloseHandle(th);
    }
    mlog("  StrLookup_Global_Object import repointed: slot was %p, now -> %p", redirect_global_import(exe), (void *)p_GlobalObj);
    mlog("nitro: %ld sites patched, %ld refused; switches not ported to Nitro are off", g_nsite_ok, g_nsite_refused);
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, g_dir, sizeof(g_dir));
        char *s = strrchr(g_dir, '\\'); if (s) *s = 0;          /* -> game folder */
        g_logging = env_present("I76MUSIC_LOG");
        exe_detect();
        if (shm_suffix()[0]) mlog("shm: suffix=%s", shm_suffix()); else mlog("shm: default names");
        if (g_exe != EXE_GOLD) mlog("exe: %s", g_exe_name);
        if (wmr_trace_on()) { HANDLE th = CreateThread(NULL, 0, wmr_census_thread, NULL, 0, NULL); if (th) CloseHandle(th); }
        wmr_apply_fix("DllMain");  /* winmmrace.c: winmmbase 26100.9549 Global* split (I76_WINMM_HEAPFIX), before any winmm call */
        if (g_exe == EXE_NITRO) { nitro_dllmain(); return TRUE; }
        load_orig();   /* must happen before the game calls any forwarded export */
        apply_crash_log();        /* always on: fault address + registers to the log */
        apply_mute();             /* lab: I76_MUTE=1 mutes this process's audio session (thread; COM off the loader lock) */
        /* WORKING DIRECTORY (always on; I76_CWD_FIX=0 disables). The exe resolves its data relative to the current
         * directory: startup_IsMinimum 0x4b2220 looks for "miss8" there and, failing, treats the mission data as a CD
         * container and WinMain raises "Please insert CD 2"; the next cwd-relative open then fails outright ("unable
         * to find required files ... check your working directory"). Both reproduced 2026-10-02 by launching the
         * pristine exe from C:\Windows. Launchers set the cwd; a bare double-click or Start-Process does not. The DLL
         * knows the game folder (it lives there), so make the cwd right before the exe's entry point runs. */
        {
            char cwd[MAX_PATH];
            if (env_flag("I76_CWD_FIX", 8, 1) != 0) {
                GetCurrentDirectoryA(sizeof(cwd), cwd);
                if (lstrcmpiA(cwd, g_dir) != 0) {
                    BOOL ok = SetCurrentDirectoryA(g_dir);
                    mlog("  cwd-fix: current directory was \"%s\", %s \"%s\"", cwd, ok ? "now" : "FAILED to set", g_dir);
                }
            }
        }
        apply_mission_launch();   /* before the exe's entry point, so before the buffer is read */
        apply_multi_instance();   /* opt-in: I76_MULTI_INSTANCE=1 */
        apply_no_minimize();      /* opt-in: I76_NO_MINIMIZE=1 */
        apply_terrain_lod();      /* experiment: I76_TERRAIN_LOD=<1..16> */
        apply_terrain_morph();    /* opt-in: I76_TERRAIN_MORPH=<band> (geomorph), I76_TERRAIN_FLAT_SPLIT=<f>[,eps] (Gold only) */
        apply_detail_distance();  /* experiment: I76_TERRAIN_TEX=<1..16>, I76_OBJECT_LOD=<1..16> */
        apply_shadow_road_dist(); /* experiment: I76_SHADOW_DIST, I76_ROAD_TEX, I76_ROAD_DIST */
        apply_road_pool();        /* with I76_ROAD_DIST > 450 or I76_FAR_CLIP: span-node pool x16 + end guard (I76_ROAD_POOL=0 off) */
        apply_frame_spikes();     /* opt-in: I76_FRAME_SPIKES=<ms> (after apply_road_pool: shares its flush wrap; before apply_glide_refresh) */
        apply_clutter_dist();     /* experiment: I76_CLUTTER_DIST=<120..2500 m> (+ I76_CLUTTER_RISE) */
        apply_mirror_far();       /* experiment: I76_MIRROR_FAR=<100..600 m> */
        apply_cam_ground_fix();   /* opt-in: I76_CAM_GROUND_FIX=1 (terrain kept when the eye dips under the ground) */
        apply_terrain_hull_fix(); /* opt-in: I76_TERRAIN_HULL_FIX=1 (terrain footprint hull rebuilt; after cam-ground, chains to it) */
        apply_aspect();           /* experiment: I76_ASPECT=<display aspect> (Hor+ widescreen, stage A) */
        apply_sw_res();           /* experiment: I76_SW_RES=<W>x<H> or 1 (software renderer above 1024x768) */
        apply_ref_fps();          /* opt-in: I76_REF_FPS=<fps> (default 20; before every frame-rate fix) */
        apply_hires_clock();      /* opt-in: I76_HIRES_CLOCK=1 */
        apply_tick_emu();         /* lab: I76_TICK_MS=<ms> (sim clock on a coarse tick; excludes I76_HIRES_CLOCK) */
        apply_engine_dt_fix();    /* opt-in: I76_ENGINE_DT_FIX=1 */
        apply_frame_cap();        /* opt-in: I76_FPS_CAP=n */
        apply_fps_log();          /* opt-in: I76_FPS_LOG=<seconds> */
        apply_frame_log();        /* lab: I76_FRAME_LOG=<file> (per-frame wall period, sim dt, player stepper) */
        apply_volume_test();      /* test knob: I76_VOLUME_TEST=<level>,<frame> */
        apply_phys_rate();        /* experiment: I76_PHYS_RATE=n */
        apply_fixed_step();       /* opt-in: I76_FIXED_STEP=n */
        apply_input_latch();      /* opt-in: I76_INPUT_LATCH=1 (after apply_fixed_step: ignition / lights keys survive step-less frames) */
        apply_breakable_box();    /* opt-in: I76_BREAKABLE_BOX=1 (long thin breakable bars as boxes, not 0.75 r spheres) */
        apply_coll_window();      /* opt-in: I76_COLL_WINDOW=1 (after apply_fixed_step: needs g_fixed_step) */
        apply_coll_dedupe();      /* with I76_FIXED_STEP: collision sound + damage once per physics step (I76_COLL_DEDUPE=0 counts only) */
        apply_breakable_speed();  /* I76_BREAKABLE_BOX=2: class-4 knock-off scored on the closing speed (after apply_coll_dedupe) */
        apply_far_engine_dt();    /* opt-in: I76_FAR_ENGINE_DT=1 (after apply_engine_dt_fix: needs its site) */
        apply_framerate_fixes();  /* opt-in: I76_FRAMERATE_FIXES=1 */
        apply_hazard_fix();       /* with I76_FRAMERATE_FIXES: stationary hazards (oil slick, fire patch, ...) step on the 20 Hz grid */
        apply_perframe_fixes();   /* with I76_FRAMERATE_FIXES: radar missile turn, WMISS click, AI skid + horn rolls */
        apply_ai_fixes();         /* opt-in: I76_AI_FIXES=1 (after apply_framerate_fixes: the dodge hold needs the 20 Hz grid) */
        apply_ai_backaway_grid(); /* opt-in: I76_AI_BACKAWAY_GRID=1 (back_away ring indexed by sim time x 20, not frames) */
        apply_ai_skid_hold();     /* opt-in: I76_AI_SKID_HOLD=1 (AI handbrake turn held to one physics step; needs I76_FIXED_STEP) */
        apply_ai_turret_hold();   /* opt-in: I76_AI_TURRET_HOLD=1 (turret outer fire roll on the AI decision grid) */
        apply_ai_throttle_ease(); /* opt-in: I76_AI_THROTTLE_EASE=1 (ai_ThrottleUpBySkill eased per second of the reference frame rate) */
        apply_ai_search_hold();   /* opt-in: I76_AI_SEARCH_HOLD=1 (path search slices on the AI decision grid) */
        apply_coop_damage();      /* opt-in: I76_COOP_DAMAGE=<factor> (humans' weapon damage in network games) */
        apply_ffb_guard();        /* default on: I76_FFB_GUARD (no I7FF_SIM_Effect call without a force-feedback device) */
        apply_mirror_rate();      /* opt-in: I76_MIRROR_RATE=1 (after apply_framerate_fixes: grid count + cloud step) */
        apply_render_interp();    /* opt-in: I76_RENDER_INTERP=1 (after apply_fixed_step) */
        apply_fix_health_pct();   /* opt-in: I76_FIX_HEALTH_PCT=1 (stock bug fix) */
        apply_fix_label_table();  /* opt-in: I76_FIX_LABEL_TABLE=1 (stock bug fix) */
        apply_far_clip();         /* opt-in: I76_FAR_CLIP=<metres> (+ render pools x16) */
        apply_telemetry();        /* opt-in: I76_TELEMETRY=<port> (after apply_fixed_step: reads g_fixed_step) */
        apply_combat_log();       /* lab: I76_COMBAT_LOG=<file> (after apply_telemetry + the AI switches: counts only) */
        apply_start_pos();        /* opt-in: I76_START_POS=x,y,z,yaw[,delay] with I76_MISSION (one placement after the start) */
        apply_retail_handling();  /* opt-in: I76_RETAIL_HANDLING=1 (the player's car keeps entity flag 0x10000 = Arcade Phys., as the retail emu runs had) */
        apply_trainer();          /* always on (I76_TRAINER=0 disables): Local\I76Trainer control block */
        apply_replay();           /* lab: I76_REPLAY=<file.rpl> (frame-dt replay of an emulator trace; replay.c) */
        apply_simtick();          /* lab: I76_SIM_TICK_MS=<ms> (whole-sim tick; after every switch that patches the frame loop; simtick.c) */
        apply_sky_mirror();       /* opt-in: I76_SKY_MIRROR=0 (after the tick and I76_FRAMERATE_FIXES: it may share the cloud constants) */
        apply_mirror_detail();    /* lab: I76_MIRROR_DUMP=<N> (mirror bitmap + census), I76_MIRROR_TERRAIN_MODE=<hex> (after apply_terrain_lod: chains the main QueueTerrain call) */
        apply_terrain_pops();     /* lab: I76_TEX_LEVEL_LOG=<csv>, I76_SHADE_CENSUS=1 (after mirror-detail: shares its picker site; terrainpops.c) */
        apply_far_edge();         /* opt-in: I76_HAZE=<start>[,<strength>], I76_GLIDE_FOG=<start>[,<colour>], I76_EDGE_FADE=1 (after the morph: chains its emit wrap; after road-pool: chains its flush wrap; faredge.c) */
        apply_jump_nose();        /* opt-in: I76_JUMP_NOSE=<0.5..1>: the held nose-down pitch rate x f once on the first airborne step (jumpnose.c) */
        apply_factor_census();    /* lab: I76_FACTOR_CENSUS=1 without the tick (the tick-factors wrappers counting only; simtick.c) */
        apply_sound_census();     /* lab: I76_SOUND_CENSUS=1 (voice starts per sim second, any frame loop; simtick.c) */
        apply_judder_census();    /* lab: I76_JUDDER_CENSUS=1 (without the tick: counts drawn-pose stalls in render_wrap) */
        apply_av_log();           /* lab: I76_AV_LOG=<path> (camera / sky / tracer / sign-sound / music cue log, any frame loop; simtick.c s.17) */
        apply_sign_sound_restart(); /* opt-in: I76_SIGN_SOUND_RESTART=1 (a new sign / barricade hit restarts vnvco3; after apply_av_log: chains its site) */
        apply_fade_no_flip();     /* opt-in: I76_FADE_NO_FLIP=1 (the palette fade presents nothing under Glide: no two-frame flicker on exit) */
        apply_menu_keys();        /* default on: I76_MENU_KEYS (the Esc menu's keys never reach the car; after apply_simtick: chains its input gate) */
        apply_menu_draw();        /* default on: I76_MENU_DRAW (re-activation with the menu up redraws the menu over the frame on screen, no fresh 3D frame) */
        apply_font_private();     /* default on: I76_FONT_PRIVATE (Lee_____.ttf registered FR_PRIVATE: no system-wide registration left behind) */
        apply_flame_census();     /* lab: I76_FLAME_CENSUS=1 (after apply_simtick / apply_framerate_fixes: counts flamer damage) */
        apply_glide_refresh();    /* opt-in: I76_GLIDE_REFRESH=<hz> (hooks LoadLibraryA; the exe's IAT is used below too) */
        apply_cursor_map();       /* opt-in: I76_CURSOR_MAP=1|ar (exe + i76shell USER32 cursor slots; stands down for u32x) */
        apply_pad_menu();         /* opt-in: I76_PAD_MENU=1 (after apply_cursor_map: chains its PeekMessageA slots) */
        apply_mp_menu();          /* default on: I76_MP_MENU=1 HOST / JOIN go straight to IPX, 2 = IPX-only row, 0 = stock */
        apply_menu_ptr();         /* default auto: I76_MENU_PTR (on only under DxWnd: the Esc menu's clicks follow the pointer) */
        apply_menu_ptr_centre();  /* default on with the cursor map: I76_MENU_PTR_CENTRE (a menu opens with the pointer mid-screen, not on the bottom edge) */
        /* i76.exe's winmm IAT is already snapped by now; redirect the mci slot. */
        HMODULE exe = GetModuleHandleA(NULL);
        /* Point the game's DATA import at the ORIGINAL's variable, not our copy -
         * see the note above redirect_global_import. Must run after load_orig. */
        mlog("  StrLookup_Global_Object import repointed: slot was %p, now -> %p",
             redirect_global_import(exe), (void *)p_GlobalObj);
        {
        void *old = patch_iat(exe, "WINMM.dll", "mciSendCommandA", hook_mciSendCommandA);
        if (!old && !patch_iat_has_dll(exe, "WINMM.dll"))
            mlog("  NOTE: this exe has no WINMM.dll import (i76fix builds route winmm through WIN32.dll): the music redirect and"
                 " the aux volume hooks cannot attach; CD audio goes to that shim instead. Use i76.exe for music.");
        mlog("--- strlkproxy: IAT patch mciSendCommandA old=%p new=%p ---", old, (void *)hook_mciSendCommandA);
        /* The aux trio is what actually gets the engine to TRY. Without these the
         * mci hook above was installed and never called even once - see the note
         * beside the aux typedefs. */
        mlog("  aux patches: auxGetNumDevs=%p auxGetDevCapsA=%p auxSetVolume=%p",
             patch_iat(exe, "WINMM.dll", "auxGetNumDevs",  hook_auxGetNumDevs),
             patch_iat(exe, "WINMM.dll", "auxGetDevCapsA", hook_auxGetDevCapsA),
             patch_iat(exe, "WINMM.dll", "auxSetVolume",   hook_auxSetVolume));
        }
        {   /* I76_MUSIC_GUARD=0 disables; see music_guard */
            char v[8]; DWORD n = GetEnvironmentVariableA("I76_MUSIC_GUARD", v, sizeof(v));
            if (!(n && v[0] == '0')) { CloseHandle(CreateThread(NULL, 0, music_guard, NULL, 0, NULL)); mlog("  music-guard: on"); }
        }
        apply_joy_routing(exe);   /* opt-in: I76_JOY_MAP=a=b / I76_JOY_SYNTH=id:x (test) */
        apply_coop_ai(exe);       /* opt-in: I76_COOP_AI=1 (host's mission cars mirrored to the joiner) */
        apply_aimelee();          /* default on with I76_COOP_AI=1 (acts only in ADDON/ai_*.lvl arenas) */
        music_opts();             /* run end / I76_MUSIC_DISC_ORDER / I76_MUSIC_SHELL: one log line */
        apply_cd_instrument(exe); /* opt-in (I76_CD_LOG=1): the "insert CD 2" prompt, logged with its cause;
                                     I76_CD_FAKE=1 is the experimental mitigation (P1-09 / P8) */
    } else if (reason == DLL_PROCESS_DETACH) {
        stop_track();
        g_tel_on = 0;
        if (g_tel_shm) { UnmapViewOfFile(g_tel_shm); g_tel_shm = 0; }
        if (g_tel_map) { CloseHandle(g_tel_map); g_tel_map = 0; }
        if (g_trn) { g_trn->magic = 0; UnmapViewOfFile(g_trn); g_trn = 0; }
        if (g_trn_map) { CloseHandle(g_trn_map); g_trn_map = 0; }
    }
    return TRUE;
}
