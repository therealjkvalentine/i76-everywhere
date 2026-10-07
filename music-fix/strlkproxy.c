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
#endif
#include "../tools/telemetry/i76tel.h"   /* telemetry export layout, shared with tools/telemetry/i76tel.py */
#include "../tools/trainer/i76trn.h"     /* trainer control block layout, shared with tools/trainer/i76trainer_gui.py */

#define FAKE_CD_ID 0xC0DE

static char     g_dir[MAX_PATH];
static char     g_alias[16] = "i76cd";
static int      g_open = 0;
static int      g_logging = 0;

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
/* Original layout: track 1 DATA, tracks 2..17 AUDIO. GOG's music\N.mp3 numbering
 * follows the CD track numbers, so no translation is needed. */
#define FIRST_TRACK 2
#define LAST_TRACK  17

static DWORD g_timeFormat = MCI_FORMAT_MSF;
static int   g_curTrack = 0;
static int   g_playingTrack = 0;   /* what is REALLY on the head right now */
/* The engine never asks for one track: every MCI_PLAY carries MCI_FROM|MCI_TO (flags 0xC in every field log), the
 * run N..15 built by 0x424190 from the TOC table (i76-map sound.md; docs/MUSIC-TRACK-MAP.md). Until 2026-10-01 the
 * proxy read only dwFrom, so the mpegvideo device stopped after one song, the exe's status poll (0x424550, every
 * 5 s in a mission) saw playing -> stopped and re-issued the same track: one song looping with gaps. g_runStart /
 * g_runEnd hold the requested run; playing_now() advances to the next track when the current one ends. */
static int   g_runStart = 0, g_runEnd = 0;
/* I76_MUSIC_RESUME (default on; =0 = the old stop-and-restart): the engine STOPs / PAUSEs / CLOSEs the CD whenever it
 * leaves the driving view (the in-mission menu, a cutscene, the shell) and later re-issues MCI_PLAY for the same run,
 * which a real CD player - and this proxy until 2026-10-04 - answered by starting the song again from 0:00 (owner:
 * "music should continue, not restart, when I go back into the game from a menu"). Now a stop pauses the mp3 where it
 * is, and a PLAY of the same run resumes it; a PLAY of anything else closes it and starts the new track as before. */
static int   g_resumeOn = -1, g_paused = 0, g_pausedRunStart = 0, g_pausedRunEnd = 0;
static int resume_on(void) {
    if (g_resumeOn < 0) { char v[8]; DWORD n = GetEnvironmentVariableA("I76_MUSIC_RESUME", v, sizeof(v)); g_resumeOn = !(n && v[0] == '0'); }
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
static int g_toIncl = -1, g_discOrder = 0, g_shell1997 = 0;
static int g_runForce = 0, g_playingForce = 0, g_pausedForce = 0;   /* 1 = the run is a shell-1997 remap */
static void music_opts(void) {
    char v[16]; DWORD n;
    if (g_toIncl >= 0) return;
    n = GetEnvironmentVariableA("I76_MUSIC_TO_INCLUSIVE", v, sizeof(v)); g_toIncl  = (n && n < sizeof(v) && v[0] == '1');
    n = GetEnvironmentVariableA("I76_MUSIC_DISC_ORDER", v, sizeof(v));   g_discOrder = (n && n < sizeof(v) && v[0] == '1');
    n = GetEnvironmentVariableA("I76_MUSIC_SHELL", v, sizeof(v));        g_shell1997 = (n && n < sizeof(v) && lstrcmpA(v, "1997") == 0);
    mlog("  music: run end %s, disc order %s, shell %s, resume %s",
         g_toIncl ? "INCLUSIVE (I76_MUSIC_TO_INCLUSIVE=1, old)" : "exclusive",
         g_discOrder ? "ON {3:16,15:17,16:15,17:3}" : "off (N -> N.mp3)",
         g_shell1997 ? "1997 (13 -> disc 15, 8 -> disc 16, one track)" : "as asked", resume_on() ? "on" : "off");
}
/* disc track -> music\N.mp3 number */
static int disc_file(int trk, int force) {
    if (g_discOrder || force) switch (trk) { case 3: return 16; case 15: return 17; case 16: return 15; case 17: return 3; }
    return trk;
}
static DWORD game_state(void) {
    return IsBadReadPtr((void *)0x004c2164, 4) ? 0xFFFFFFFFu : *(volatile DWORD *)0x004c2164;
}
static MCIERROR play_track(int track);
static DWORD g_lenCache[LAST_TRACK + 1];   /* ms, 0 = not yet queried */

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
    if (g_playingTrack && g_playingTrack >= g_runStart && g_playingTrack < g_runEnd) {   /* song ended: next in the run */
        int next = g_playingTrack + 1;
        mlog("  run %d..%d: track %d ended -> %d (t=%lu)", g_runStart, g_runEnd, g_playingTrack, next, (unsigned long)GetTickCount());
        return play_track(next) == 0;
    }
    return 0;
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
    /* Log EVERY call, including ones we pass straight through. Two rounds were lost
     * to logs that recorded only cdaudio traffic: "no lines" then means either "the
     * game never called this" or "it called about something else", and those need
     * different fixes. Now the absence of a line is real evidence. */
    mlog("mciSendCommandA(id=%u msg=0x%X flags=0x%lX)", (unsigned)id, msg, (unsigned long)flags);
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
                to = g_toIncl ? tt : (tt > track ? tt - 1 : track);   /* MCI_TO = end position: stops BEFORE track tt */
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
            g_runStart = track; g_runEnd = to;
        }
        g_curTrack = track;
        if (g_paused) {
            g_paused = 0;
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
    case MCI_STOP: case MCI_PAUSE: case MCI_CLOSE:
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
            case MCI_STATUS_MODE:             p->dwReturn = playing_now() ? MCI_MODE_PLAY : MCI_MODE_STOP; break;
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
            void **slot = iat_slot(exe, "WINMM.dll", h[i].name);
            if (!slot || *slot == h[i].hook) continue;
            if (logged[i] < 3) {                                 /* who took it */
                HMODULE m = NULL; char who[MAX_PATH] = "?", *b = who, *q;
                if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                       (LPCSTR)*slot, &m) && m) GetModuleFileNameA(m, who, sizeof(who));
                for (q = who; *q; q++) if (*q == '\\' || *q == '/') b = q + 1;
                mlog("  music-guard: WINMM!%s slot held by %s (%p) - re-claimed", h[i].name, b, *slot);
                logged[i]++;
            }
            patch_iat(exe, "WINMM.dll", h[i].name, h[i].hook);
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
    DWORD n = GetEnvironmentVariableA("I76_MISSION", mission, sizeof(mission));
    static const BYTE clr1_old[6] = { 0x88, 0x0D, 0xF0, 0x49, 0x50, 0x00 };
    static const BYTE clr1_nop[6] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    static const BYTE clr2_old[3] = { 0xC6, 0x00, 0x00 };
    static const BYTE clr2_nop[3] = { 0x90, 0x90, 0x90 };
    int ok1, ok2;
    if (n == 0 || n >= sizeof(mission)) return;      /* not requested */

    ok1 = patch_bytes(0x00402d33, clr1_old, clr1_nop, 6, "pre-parse clear");
    ok2 = patch_bytes(0x0049d1e0, clr2_old, clr2_nop, 3, "parser clear");
    if (!ok1 || !ok2) {
        mlog("  mission-launch ABORTED (%d/%d patches applied) - booting to the menu", ok1 + ok2, 2);
        return;
    }
    lstrcpynA((char *)0x005049f0, mission, 16);
    /* 2026-09-27: the name alone no longer skips the menus (six boots across both exe builds, three shell DLLs and
     * the Aug 8 proxy binary all sat in the shell with the buffer intact). WinMain runs the shell unless the dword
     * at 0x504c10 is nonzero (cmp at 0x403197, jne 0x403201 past the shell_RunAndGetChoice call at 0x4031f5); the
     * mission-name path at 0x402d82 leaves that dword alone, and nothing in the exe sets it, so set it here. */
    *(volatile DWORD *)0x00504c10 = 1;

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
    if (GetEnvironmentVariableA("I76_SKIP_MOVIES", NULL, 0) > 0) {
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
    if (GetEnvironmentVariableA("I76_HIRES_CLOCK", NULL, 0) == 0) return;
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
static int g_in_far;                                        /* inside physics_StepVehicleFar (I76_FAR_ENGINE_DT, below) */
static int g_engine_dt_on;
static float __cdecl engine_substep_dt(void) {
    float sim_dt, rate; int count;
    /* I76_FAR_ENGINE_DT: the far path applies the engine update once per frame, where the stock whole-frame dt is right */
    if (g_in_far) return *(volatile float *)0x004fe428;    /* simclock_dt, what simclock_GetDt returns */
    /* I76_FIXED_STEP: stock at 20 fps hands the engine the whole frame's dt (~50 ms) on every substep; keep that */
    if (g_fixed_step > 0.0f) return 0.05f;
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
    if (GetEnvironmentVariableA("I76_ENGINE_DT_FIX", NULL, 0) == 0) return;
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
    if (GetEnvironmentVariableA("I76_FAR_ENGINE_DT", NULL, 0) == 0) return;
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
static float g_grid_acc, g_grid_win = 0.05f;                 /* time since the last grid frame; on a grid frame, the window it closes */
static float g_turn_k = 1.0f, g_turn_g = 1.0f;               /* per-step turn scales (radar missiles): min(dt x 20, 1) and its gain form */
static int g_coll_dup;                                       /* collision pass: the contact just found repeats last frame's (below) */
static void radar_ping_flush(void);
static DWORD g_frame;                                        /* proxy frame counter, advanced by the frame hook */
static DWORD g_voltest_frame; static int g_voltest_level;    /* I76_VOLUME_TEST */
static int g_tel_on;                                         /* I76_TELEMETRY: publish the completed frame (below, with the telemetry export) */
static void tel_frame(void);
static i76trn_ctl_t *g_trn;                                  /* trainer control block (below, with apply_trainer) */
static void trn_frame(void);
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
static void __cdecl frame_cap_then_clock(void) {
    LARGE_INTEGER now, fl_in = {0}, fl_cap = {0};
    if (g_fl_period) QueryPerformanceCounter(&fl_in);
    /* The frame just rendered is complete here (ticks, post-ticks, camera, render, Flip): publish it before any cap
     * wait, so the datagram leaves as soon as the frame is on screen. */
    if (g_tel_on) tel_frame();
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
    g_frame++;
    if (g_voltest_frame && g_frame == g_voltest_frame) {    /* I76_VOLUME_TEST=<level>,<frame>: call sound_SetCdVolume on the
                                                               game's own thread, as the Options slider does (test knob) */
        mlog("  volume-test: sound_SetCdVolume(%d) at frame %lu", g_voltest_level, (unsigned long)g_frame);
        ((void (__cdecl *)(int))0x00424b60)(g_voltest_level);
    }
    if (g_trn) trn_frame();                                 /* trainer control block: hold / one-shots, before the tick */
    ((void (__cdecl *)(void))0x0049c920)();                /* simclock_Update */
    if (g_hires_on) {
        /* The hires clock still hands simclock whole milliseconds (it stands in for GetTickCount), so at 60 fps the
         * frame dt reads 16 or 17 ms while the display shows 16.67: everything drawn advances 1 ms too little or too
         * much, alternately. Measured as 0.024 m/frame^2 of jitter on a car at 28 m/s under a static script camera
         * (capture 014, scam24b). Offline (sim_dt == dt) replace both with the exact QPC interval. simclock_time keeps
         * its own ms sum, which tracks real time either way. */
        LARGE_INTEGER q;
        QueryPerformanceCounter(&q);
        if (g_prev_q.QuadPart) {
            float dts = (float)((double)(q.QuadPart - g_prev_q.QuadPart) / (double)g_qpf.QuadPart);
            volatile float *sim_dt = (volatile float *)0x004fe420, *sim_rate = (volatile float *)0x004fe424;
            volatile float *dt = (volatile float *)0x004fe428, *rate = (volatile float *)0x004fe42c;
            if (*sim_dt == *dt && dts >= 0.001f && dts <= 0.2f) { *dt = *sim_dt = dts; *rate = *sim_rate = 1.0f / dts; }
        }
        g_prev_q = q;
    }
    if (g_ratefix) {
        /* constants the engine applies once per frame / per render pass, rescaled so their effect per SECOND is
         * what it was at 20 fps: value x (frame dt / 0.05). simclock_dt 0x4fe428 is this frame's clamped dt. */
        float k = *(volatile float *)0x004fe428 * 20.0f;
        g_cloud_u = 1.0f * k; g_cloud_v = -1.0f * k; g_cam_rate = -0.017453292f * k; g_zoom_rate = -0.01f * k;
        g_thr_up = -0.4f * k; g_thr_dn = 0.5f * k;
        g_acc20 += *(volatile float *)0x004fe428;
        g_grid_acc += *(volatile float *)0x004fe428;
        g_tick20 = g_acc20 >= 0.049f;                        /* 1 ms tolerance: n x dt lands a hair under 0.05 */
        if (g_tick20) {
            g_acc20 -= 0.05f; if (g_acc20 > 0.05f || g_acc20 < -0.01f) g_acc20 = 0.0f; g_tick20_n++; radar_ping_flush();
            g_grid_win = g_grid_acc; g_grid_acc = 0.0f;      /* what a per-frame step skipped since the last grid frame has to cover */
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
    char v[32]; DWORD n = GetEnvironmentVariableA("I76_VOLUME_TEST", v, sizeof(v));
    if (n == 0 || n >= sizeof(v)) return;
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
            volatile BYTE *b = (volatile BYTE *)0x004039b8;           /* our call, or did something rewrite it? */
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
                 *(volatile LONG *)0x004c2164, (unsigned long)g_frame, b[0], b[1], b[2], b[3], b[4],
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
static void apply_fps_log(void) {
    char v[16]; DWORD n = GetEnvironmentVariableA("I76_FPS_LOG", v, sizeof(v)); int sec;
    if (n == 0 || n >= sizeof(v) || (sec = atoi(v)) < 1 || sec > 600) return;
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
    char v[16]; int fps;
    LONG rel = (LONG)((DWORD_PTR)frame_cap_then_clock - (0x004039b8 + 5));
    DWORD n = GetEnvironmentVariableA("I76_FPS_CAP", v, sizeof(v));
    if (n == 0 || n >= sizeof(v) || (fps = atoi(v)) < 5 || fps > 1000) return;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    g_cap_period.QuadPart = g_qpf.QuadPart / fps;
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
    mlog("  fps-cap: %d fps%s", fps, g_frame_hook ? "" : " (hook failed: no cap)");
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
static float __cdecl ai_rate20(void) { return 20.0f; }
/* AI steering (ai_SteerToHeading 0x40fe80): steer = skill x heading error / (sim_dt x k x v), the yaw rate that closes the
 * heading error in one frame (i76-map subsystems/ai.md). The sim_dt read at 0x40fed9 is used only as that divisor, so it
 * gets the 20 fps value. */
static float __cdecl ai_dt20(void) { return 0.05f; }

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
static DWORD g_ping_frame;
static int __cdecl radar_ping_wrap(const char *name, BYTE *obj, int flag) {
    g_idbg_ping_req++;
    if (g_ping_req_last != g_frame) { g_ping_req_last = g_frame; g_idbg_ping_frames++; }
    if (!g_tick20) { g_ping_name = name; g_ping_obj = obj; g_ping_flag = flag; g_ping_pending = 1; return 0; }
    if (g_ping_frame == g_frame) return 0;                   /* one per grid frame */
    g_ping_frame = g_frame; g_ping_pending = 0; g_idbg_ping_play++;
    return ((int (__cdecl *)(const char *, BYTE *, int))0x004250f0)(name, obj, flag);
}
static void radar_ping_flush(void) {                        /* from the frame hook, on grid frames */
    if (g_ping_pending && g_ping_frame != g_frame) {
        g_ping_pending = 0; g_ping_frame = g_frame; g_idbg_ping_play++;
        ((int (__cdecl *)(const char *, BYTE *, int))0x004250f0)(g_ping_name, g_ping_obj, g_ping_flag);
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
static float __cdecl step20_dt(void) { float dt = *(volatile float *)0x004fe428; return dt > 0.05f ? dt : 0.05f; }
static void __cdecl flame_age_wrap(void) { if (g_tick20) ((void (__cdecl *)(void))0x00443e90)(); }
static void __cdecl flame_update_main(BYTE *cam) {
    g_flame_dmg_ok = g_tick20;
    ((void (__cdecl *)(BYTE *))0x00443fc0)(cam);
    g_flame_dmg_ok = 0;
}
typedef struct { DWORD d[6]; } dmgrec_t;                    /* passed by value: owner, kind 4, ..., amount at d[4] */
static void __cdecl flame_damage_wrap(DWORD target, dmgrec_t rec, DWORD extra) {
    g_idbg_flame_hits++;
    if (!g_flame_dmg_ok) return;
    g_idbg_flame_dmg++;
    ((void (__cdecl *)(DWORD, dmgrec_t, DWORD))0x004a8240)(target, rec, extra);
}

/* The flame-hit explosion (entity_SpawnExplosion 0x49ead0 from 0x44471d: the ORDF car-impact xdf, xflht1 for stock
 * flamers, blast damage 0) is spawned on every update call that has a contact, the mirror pass included: held to the
 * same main-pass grid frames as the damage. 7 dword arguments, result unused. */
static void __cdecl flame_expl_wrap(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g) {
    if (g_flame_dmg_ok)
        ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))0x0049ead0)(a, b, c, d, e, f, g);
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
    if (g_aifire_cache && !g_tick20) {
        for (n = 0; n < 1024; n++, i = (i + 1) & 1023) {
            if (g_aifire[i].key == rec) return g_aifire[i].tick == g_tick20_n ? g_aifire[i].res : 0;
            if (!g_aifire[i].key) break;
        }
        return 0;                                           /* not decided in this window */
    }
    r = ((int (__cdecl *)(DWORD, DWORD, float, float, DWORD, DWORD, int *, DWORD))0x00418200)(a, b, c, d, e, f, rec, h);
    g_idbg_aifire_calls++; if (r) g_idbg_aifire_yes++;
    if (g_aifire_cache) {
        for (n = 0; n < 1024; n++, i = (i + 1) & 1023)
            if (g_aifire[i].key == rec || !g_aifire[i].key) { g_aifire[i].key = rec; g_aifire[i].tick = g_tick20_n; g_aifire[i].res = r; break; }
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
    if (g_tick20) { ((void (__cdecl *)(BYTE *))0x004414a0)(cam); return; }
    if (!*(volatile int *)0x0052ba34) return;
    t = g_acc20 - 0.05f;                                    /* the update draws before it moves: last tick drew P0 */
    if (t > 0.0f) t = 0.0f; if (t < -0.05f) t = -0.05f;
    for (p = *(BYTE **)0x0052ba30; p; p = *(BYTE **)(p + 0x40)) {
        if (*(int *)(p + 4) >= 20) continue;                /* expired: freed on the next grid frame, not drawn */
        memcpy(save, p + 0x28, sizeof(save));
        for (k = 0; k < 3; k++) ((double *)(p + 0x28))[k] = save[k] + (double)(((float *)(p + 0x10))[k] * t);
        ((void (__cdecl *)(BYTE *, BYTE *))0x00441930)(cam, p);
        memcpy(p + 0x28, save, sizeof(save));
    }
}

/* Missile smoke trails (renderer_QueueSmokeTrails 0x442ba0, once per render): in a trail's last 2 s each call drops up
 * to 4 tail segments (0x442bd6), so at 60 fps trails vanish 3x as fast. Between grid frames a trail inside that window
 * gets its expiry (+0xc) moved just past now + 2 for the duration of the call, then restored. */
static void __cdecl trails_wrap(BYTE *cam) {
    BYTE *head = *(BYTE **)0x0052bae8, *r;
    float saved[256]; int n = 0;
    if (!g_tick20 && head) {
        float now = ((float (__cdecl *)(void))0x0049c8c0)(), lim = now + 2.0f;
        lim += lim * 1e-6f;
        r = head;
        do {
            float *e = (float *)(r + 0xc);
            if (n < 256) { saved[n++] = *e; if (*e >= now && *e < lim) *e = lim; }
            r = *(BYTE **)r;
        } while (r && r != head);
    }
    ((void (__cdecl *)(BYTE *))0x00442ba0)(cam);
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
    if (GetEnvironmentVariableA("I76_FRAMERATE_FIXES", NULL, 0) == 0) return;
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
        LONG rel = (LONG)((DWORD_PTR)ai_rate20 - (0x0040fa15 + 5)); memcpy(a_new + 1, &rel, 4);
        n += patch_bytes(0x0040fa15, a1_old, a_new, 5, "AI throttle gain (type 9)");
        rel = (LONG)((DWORD_PTR)ai_rate20 - (0x0040fa8d + 5)); memcpy(a_new + 1, &rel, 4);
        n += patch_bytes(0x0040fa8d, a2_old, a_new, 5, "AI throttle gain (vehicles)");
        {
            static const BYTE s_old[5] = { 0xE8, 0xC2, 0xC8, 0x08, 0x00 };  /* call simclock_GetSimDt at 0x40fed9 */
            BYTE s_new[5] = { 0xE8 };
            rel = (LONG)((DWORD_PTR)ai_dt20 - (0x0040fed9 + 5)); memcpy(s_new + 1, &rel, 4);
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
    { char v[8]; DWORD k = GetEnvironmentVariableA("I76_AI_FIRE_CACHE", v, sizeof(v)); if (k && k < sizeof(v) && v[0] == '0') g_aifire_cache = 0; }
    g_ratefix = 1;
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
    volatile float *sim_dt = (volatile float *)0x004fe420, *sim_rate = (volatile float *)0x004fe424;
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
        return ((DWORD (__cdecl *)(BYTE *, float))0x004ac800)(proj, dt);
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
    if (g_ai_roll_hold && !g_tick20) return 1;
    g_idbg_skid_rolls++;
    return (*(int (__cdecl **)(void))0x004bc20c)();         /* the exe's own rand (MSVCRT import) */
}
static int __cdecl ai_horn_rand(void) {
    if (g_ai_roll_hold && !g_tick20) return 1;
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
    { char v[8]; DWORD k = GetEnvironmentVariableA("I76_AI_ROLL_HOLD", v, sizeof(v)); if (k && k < sizeof(v) && v[0] == '0') g_ai_roll_hold = 0; }
    mlog("  perframe-fixes: %d/5 sites repointed (radar missile turn x2 scaled by dt x 20, WMISS click on the 20 Hz grid, AI skid-turn and horn rolls %s)",
         n, g_ai_roll_hold ? "held to the 20 Hz grid" : "counted, every frame");
}

static int __cdecl ai_dodge_wrap(DWORD a, DWORD b, DWORD c, DWORD d) {
    int r;
    if (g_dodge_hold && !g_tick20) return 0;
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
    int i, n = 0, first = 0;
    if (GetEnvironmentVariableA("I76_AI_FIXES", NULL, 0) == 0) return;
    if (!g_ratefix) { mlog("  ai-fixes: dodge hold needs I76_FRAMERATE_FIXES (the 20 Hz grid) - horizon pins only"); first = 1; }
    for (i = first; i < (int)(sizeof(cs) / sizeof(cs[0])); i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(cs[i].target - (cs[i].site + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)cs[i].wrap - (cs[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(cs[i].site, o, w, 5, cs[i].what);
    }
    { char v[8]; DWORD k = GetEnvironmentVariableA("I76_AI_DODGE_HOLD", v, sizeof(v)); if (k && k < sizeof(v) && v[0] == '0') g_dodge_hold = 0; }
    mlog("  ai-fixes: %d/6 sites repointed (dodge check %s, avoidance horizon pinned to 50 ms: prediction dt, rate x2, probe dt x2)",
         n, first ? "skipped" : g_dodge_hold ? "held to the 20 Hz grid" : "counted, passed through");
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
static void apply_ai_backaway_grid(void) {
    static const BYTE old[5] = { 0xE8, 0x75, 0x83, 0xFF, 0xFF };   /* call 0x415600 at 0x41d286 */
    BYTE w[5] = { 0xE8 };
    LONG rel;
    char v[8]; DWORD k = GetEnvironmentVariableA("I76_AI_BACKAWAY_GRID", v, sizeof(v));
    if (k == 0 || k >= sizeof(v) || v[0] == '0') return;
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
static void apply_coop_damage(void) {
    static const struct { DWORD site, target; void *stub; const char *what; } s[4] = {
        { 0x004a76c5, 0x00458bf0, (void *)coop_is_human,        "impact: is-player" },
        { 0x004a76d1, 0x00452d20, (void *)coop_net_impact_stub, "impact: network factor" },
        { 0x00444393, 0x00458bf0, (void *)coop_is_human,        "flamer: is-player" },
        { 0x0044439f, 0x00452d20, (void *)coop_net_flame_stub,  "flamer: network factor" },
    };
    char v[16]; float f; int i, n = 0;
    DWORD k = GetEnvironmentVariableA("I76_COOP_DAMAGE", v, sizeof(v));
    if (k == 0 || k >= sizeof(v)) return;
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
 * sent, and AI cars carry owner id 0 into the mirror's score bookkeeping. */
typedef int (__cdecl *dprecv_fn)(void *, void *, void *, int, void *, void *);
typedef int (__cdecl *dpsend_fn)(void *, int, int, int, void *, int);
static dprecv_fn real_dpReceive;
static volatile LONG g_coop_ai_sent, g_coop_ai_applied, g_coop_ai_role, g_coop_ai_senderr, g_coop_ai_rx;
static DWORD g_coop_ai_last;
static float g_coop_ai_seen[2048];
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
    if (!o || *(int *)(o + 0x6c) != 1 || !*(BYTE **)(o + 0x70) || (o[0x10] & 0x10)) return NULL;
    for (k = 0; k < 16; k++) { BYTE *p = (BYTE *)0x00541070 + k * 0x48; if (*(WORD *)p && *(BYTE **)(p + 0x28) == o) return NULL; }
    return o;
}
static void coop_ai_host_send(void) {
    BYTE pkt[512]; BYTE *tab; int count, i, n = 0;
    DWORD now = GetTickCount();
    if (now - g_coop_ai_last < 100 || !coop_ai_in_mission()) return;
    g_coop_ai_last = now;
    tab = *(BYTE **)(0x0054a178 + 4); count = *(int *)(0x0054a178 + 8);
    if (!tab || count <= 0 || count > 2048) return;
    for (i = 0; i <= count; i++) {
        BYTE *o = i < count ? coop_ai_object(i, count, tab) : NULL;
        if (o) {
            BYTE *r = pkt + 8 + n * 100;
            int w8[8], m = coop_ai_weapon_mask(o, w8);
            *(WORD *)r = (WORD)i; r[2] = (BYTE)(m < 0 ? 0 : m); r[3] = 0;
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
        if (!o || t <= g_coop_ai_seen[i]) continue;
        g_coop_ai_seen[i] = t;
        g_coop_ai_mask[i] = r[2]; g_coop_ai_until[i] = GetTickCount() + 150;
        ((void (__cdecl *)(BYTE *, float *))0x00464890)(o, (float *)(r + 4));
        g_coop_ai_applied++;
    }
}
static int g_coop_chain = 0;                                /* I76_COOP_CHAIN (see "CO-OP CAMPAIGN CHAIN" below) */
static volatile LONG g_coop_chain_sent, g_coop_chain_got;
static void coop_ai_log(void) {                            /* after each fps line: role, counts, first two mission cars */
    BYTE *tab; int count, i, shown = 0; char buf[512]; int len;
    if (!real_dpReceive) return;
    len = sprintf(buf, "  coop-ai: role %s, sent %ld (send errors %ld), packets in %ld, applied %ld, fire pulls %ld, local damage blocked %ld",
                  g_coop_ai_role == 1 ? "host" : g_coop_ai_role == 2 ? "joiner" : "none", g_coop_ai_sent, g_coop_ai_senderr, g_coop_ai_rx,
                  g_coop_ai_applied, g_coop_ai_shots, g_coop_ai_blocked);
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
static int __cdecl coop_ai_class_damage(BYTE *o, int a, int rec) {   /* replaces `call object_ClassDamage 0x462040` x5 */
    if (coop_ai_role() == 2 && coop_ai_is_mirrored(o)) { g_coop_ai_blocked++; return 0; }
    return ((int (__cdecl *)(BYTE *, int, int))0x00462040)(o, a, rec);
}
#define COOP_AM_PKT 0x4d41                                   /* 'AM' (co-op chain, below) */
static void coop_chain_receive(BYTE *pkt, int size);
static LONG g_coop_rx_run, g_coop_rx_logged;                /* diagnostics: packets in one unbroken pump loop */
static WORD g_coop_rx_types[64], g_coop_rx_from[64]; static int g_coop_rx_n;
static int __cdecl coop_dpReceive(void *dp, void *from, void *to, int flags, void *buf, void *size) {
    int r = real_dpReceive(dp, from, to, flags, buf, size);
    int role = coop_ai_role();
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
    if (role == 1) coop_ai_host_send();
    else if (role == 2) coop_ai_joiner_fire();
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AI_PKT) { g_coop_ai_rx++; coop_ai_apply((BYTE *)buf, *(int *)size); }
    if (role == 2 && r == 0 && buf && size && *(WORD *)buf == COOP_AM_PKT) coop_chain_receive((BYTE *)buf, *(int *)size);
    return r;
}
/* CO-OP CAMPAIGN CHAIN (I76_COOP_CHAIN=1 with I76_COOP_AI=1, both machines). A network game tears its in-game network
 * state down at mission end and goes back to the shell, which owns the connection. The Replay path (game state 7)
 * reloads WITHOUT the shell, and the reload runs net setup 0x452d40 again with the same session handle, so a mission
 * can be swapped in place. The co-op missions are installed as m41..m57 (= T01..T17, tools/coop-mission.py) and
 * m01 ("The Crater") is T01 as the entry point. At `call 0x461810` 0x404110 (first call after the mission loop,
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
static void __cdecl coop_netflag(int v) {                   /* replaces `call 0x452d30` (net flag := v) at 0x404662 */
    if (g_coop_reload_pending) { v = 1; g_coop_reload_pending = 0; mlog("  coop-chain: teardown keeps the network flag for the reload"); }
    ((void (__cdecl *)(int))0x00452d30)(v);
}
static int coop_chain_next(const char *cur, char *out) {    /* m01 -> m42, m41..m56 -> +1, m57 -> none */
    int n;
    if ((cur[0] | 0x20) != 'm' || cur[1] < '0' || cur[1] > '9' || cur[2] < '0' || cur[2] > '9') return 0;
    n = (cur[1] - '0') * 10 + (cur[2] - '0');
    if (n == 1) n = 42; else if (n >= 41 && n < 57) n++; else return 0;
    sprintf(out, "m%02d.msn", n);
    return 1;
}
static void coop_chain_send(int kind, const char *name) {
    BYTE pkt[20]; int i;
    memset(pkt, 0, sizeof(pkt));
    *(WORD *)pkt = COOP_AM_PKT; pkt[3] = (BYTE)kind; strncpy((char *)pkt + 4, name, 15);
    for (i = 0; i < 3; i++)
        if (((dpsend_fn) * (void **)0x004bc38c)(*(void **)0x00541024, *(volatile WORD *)0x00541028,
                                                ((WORD (__cdecl *)(void))0x00454e10)(), 0, pkt, sizeof(pkt)) == 0) g_coop_chain_sent++;
}
static void __cdecl coop_chain_at_end(char *winmain_esp) {
    volatile int *state = (volatile int *)0x004c2164;
    char *setup_name = winmain_esp + 0x2b9, *cur = (char *)0x005049f0;
    int role = coop_ai_role();
    if (role == 1 && (*state == 1 || *state == 0 || *state == 0xb)) {
        char next[16];
        int won = *state == 1;
        if (won && !coop_chain_next(cur, next)) { mlog("  coop-chain: '%s' won and it is the last mission - normal end", cur); return; }
        if (!won) { strncpy(next, cur, 15); next[15] = 0; }
        coop_chain_send(won, next);
        strncpy(g_coop_next, next, 15); g_coop_next[15] = 0;
        *state = 7;
        mlog("  coop-chain: host %s '%s' -> loading '%s' in the same session (AM sent x%ld)", won ? "won" : "lost", cur, next, g_coop_chain_sent);
    }
    if (*state == 7 && g_coop_next[0]) {
        g_coop_reload_pending = 1;
        strncpy(setup_name, g_coop_next, 15); setup_name[15] = 0;
        strncpy(cur, g_coop_next, 15); cur[15] = 0;
        mlog("  coop-chain: %s reloads as '%s'", role == 1 ? "host" : "joiner", g_coop_next);
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
static void coop_chain_receive(BYTE *pkt, int size) {      /* joiner, in the pump */
    if (size < 20 || !g_coop_chain || *(volatile int *)0x004c2164 != 5) return;
    strncpy(g_coop_next, (char *)pkt + 4, 15); g_coop_next[15] = 0;
    *(volatile int *)0x004c2164 = 7;
    g_coop_chain_got++;
}
static int __cdecl coop_ai_frametick(int a) {              /* replaces `call ai_FrameTick 0x40a320` at 0x403ddf */
    if (coop_ai_role() == 2 && coop_ai_in_mission()) return 0;
    return ((int (__cdecl *)(int))0x0040a320)(a);
}
static void apply_coop_ai(HMODULE exe) {
    BYTE old[5] = { 0xE8 }, w[5] = { 0xE8 }; LONG r0, r1;
    char v[8]; DWORD k = GetEnvironmentVariableA("I76_COOP_AI", v, sizeof(v));
    if (k == 0 || k >= sizeof(v) || v[0] != '1') return;
    real_dpReceive = (dprecv_fn)patch_iat(exe, "anetdll.dll", "dpReceive", (void *)coop_dpReceive);
    r0 = (LONG)(0x0040a320 - (0x00403ddf + 5)); r1 = (LONG)((DWORD_PTR)coop_ai_frametick - (0x00403ddf + 5));
    memcpy(old + 1, &r0, 4); memcpy(w + 1, &r1, 4);
    mlog("  coop-ai: dpReceive %s, ai_FrameTick call %s (host sends mission cars as 'AT', joiner mirrors them)",
         real_dpReceive ? "hooked" : "NOT hooked",
         patch_bytes(0x00403ddf, old, w, 5, "coop-ai: ai_FrameTick") ? "repointed" : "NOT repointed");
    {   /* AI trigger pulls (host records them) and the damage entry (joiner blocks it for mirrored cars) */
        static const struct { DWORD site, target; void *stub; } c[6] = {
            { 0x00414f86, 0x004a3560, (void *)coop_ai_trigger },
            { 0x00465e5a, 0x00462040, (void *)coop_ai_class_damage }, { 0x0046648f, 0x00462040, (void *)coop_ai_class_damage },
            { 0x0046aae4, 0x00462040, (void *)coop_ai_class_damage }, { 0x004a81d3, 0x00462040, (void *)coop_ai_class_damage },
            { 0x004a8266, 0x00462040, (void *)coop_ai_class_damage },
        };
        int i, n = 0;
        for (i = 0; i < 6; i++) {
            BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 };
            LONG a0 = (LONG)(c[i].target - (c[i].site + 5)), a1 = (LONG)((DWORD_PTR)c[i].stub - (c[i].site + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            if (patch_bytes(c[i].site, o5, w5, 5, "coop-ai: trigger/damage")) n++;
        }
        mlog("  coop-ai: %d/6 trigger + damage sites repointed", n);
    }
    {   char c8[8]; DWORD kk = GetEnvironmentVariableA("I76_COOP_CHAIN", c8, sizeof(c8));
        if (kk && kk < sizeof(c8) && c8[0] == '1') {
            BYTE o5[5] = { 0xE8 }, w5[5] = { 0xE8 };
            LONG a0 = (LONG)(0x00461810 - (0x00404110 + 5)), a1 = (LONG)((DWORD_PTR)coop_chain_stub - (0x00404110 + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            g_coop_chain = patch_bytes(0x00404110, o5, w5, 5, "coop-chain: loop exit");
            a0 = (LONG)(0x00452d30 - (0x00404662 + 5)); a1 = (LONG)((DWORD_PTR)coop_netflag - (0x00404662 + 5));
            memcpy(o5 + 1, &a0, 4); memcpy(w5 + 1, &a1, 4);
            if (!patch_bytes(0x00404662, o5, w5, 5, "coop-chain: teardown net flag")) g_coop_chain = 0;
            mlog("  coop-chain: %s (won -> next co-op mission, lost -> retry, same session)", g_coop_chain ? "on" : "NOT installed");
        }
    }
    if (!real_dpReceive) { mlog("  coop-ai: no dpReceive import - off"); }
}

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
    {   char mv[4]; DWORD mk = GetEnvironmentVariableA("I76_MIRROR_RATE", mv, sizeof(mv));
        if (mk == 0 || mk >= sizeof(mv) || mv[0] == '0') return;
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
    if (memcmp((void *)0x0040b6e3, old_jmp, 7) != 0 || memcmp((void *)0x004bc620, k100, 4) != 0 ||
        memcmp((void *)0x0040b6f0, old_clamp, 6) != 0 || memcmp((void *)0x0040b5f5, old_sides, 6) != 0) {
        mlog("  fix-health-pct: bytes differ at 0x40b6e3 / 0x4bc620 / 0x40b6f0 / 0x40b5f5 - not applied"); return;
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
    if (GetEnvironmentVariableA("I76_FIX_LABEL_TABLE", NULL, 0) == 0) return;
    memset(blk, 0x90, sizeof(blk));
    blk[0] = 0x56;                                          /* push esi (the table record) */
    blk[1] = 0xE8; rel = (LONG)((DWORD_PTR)label_grow - (0x004ad466 + 5)); memcpy(blk + 2, &rel, 4);
    blk[6] = 0x83; blk[7] = 0xC4; blk[8] = 0x04;            /* add esp, 4 */
    blk[9] = 0x85; blk[10] = 0xC0;                          /* test eax, eax */
    blk[11] = 0x74; blk[12] = 0x19;                         /* je 0x4ad48b (return 0) */
    blk[13] = 0xEB; blk[14] = 0x33;                         /* jmp 0x4ad4a7 (insert) */
    ok = patch_bytes(0x004ad465, old_blk, blk, sizeof(blk), "label table grow");
    mlog("  fix-label-table: %s", ok ? "on" : "NOT applied");
    if (ok && GetEnvironmentVariableA("I76_LABEL_TEST", NULL, 0)) {
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
    n = GetEnvironmentVariableA("I76_FAR_CLIP", v, sizeof(v));
    if (n == 0 || n >= sizeof(v)) return;
    far_m = (float)atof(v);
    /* Third ceiling (docs/records/FARCLIP-CAMERA-CRASH.md, 2026-10-02): the terrain tessellator stores vertex indices as int16
     * (renderer_SplitTerrainEdge 0x4918f0); past ~32,767 terrain vertices in a frame the index wraps and the game dies.
     * The hood view (120 deg) and binoculars (8x) reach that between 2500 and 2750 m on t01, so 2500 is the cap. */
    if (far_m < 100.0f || far_m > 2500.0f) { mlog("  far-clip: %s out of the safe range (100..2500 m: int16 terrain vertex indices, see FARCLIP-CAMERA-CRASH.md) - not applied", v); return; }
    /* An exe already file-patched by tools/framerate/patch-farclip.ps1 (the sandbox is) carries the pools at x16 and
     * `mov eax, imm32 <float>` at the read site. Recognise that, report the file value, and still take over the read
     * so the environment value wins (2026-10-02: "pool constant 0 differs - not applied" hid that the 1800 m came from
     * the file, not the switch). */
    for (i = 0; i < 5; i++) if (*(DWORD *)(DWORD_PTR)pool[i].va == pool[i].old * 16) filepatched++;
    if (filepatched == 5 && *(BYTE *)0x004059de == 0xB8) {
        BYTE imm_old[5]; float file_m;
        memcpy(imm_old, (void *)0x004059de, 5); memcpy(&file_m, imm_old + 1, 4);
        g_far_clip = far_m;
        a = (DWORD)(DWORD_PTR)&g_far_clip; memcpy(rd_new + 1, &a, 4);
        ok = patch_bytes(0x004059de, imm_old, rd_new, 5, "far clip read (file-patched exe)");
        mlog("  far-clip: exe is file-patched (%g m, pools x16); %s (%g m from I76_FAR_CLIP)", file_m, ok ? "read site repointed" : "NOT repointed", far_m);
        return;
    }
    for (i = 0; i < 5; i++) if (*(DWORD *)(DWORD_PTR)pool[i].va != pool[i].old) { mlog("  far-clip: pool constant %d differs - not applied", i); return; }
    if (memcmp((void *)0x004059de, rd_old, 5) != 0) { mlog("  far-clip: read site differs - not applied"); return; }
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
    depth++;
    mlog("CRASH: code 0x%08lX at 0x%08lX (exe+0x%lX) %s addr 0x%08lX | eax %08lX ebx %08lX ecx %08lX edx %08lX esi %08lX edi %08lX ebp %08lX esp %08lX | frame %lu state %lu cam cb 0x%08lX mode %lu",
         (unsigned long)r->ExceptionCode, (unsigned long)(DWORD_PTR)r->ExceptionAddress,
         (unsigned long)((DWORD_PTR)r->ExceptionAddress - (DWORD_PTR)GetModuleHandleA(NULL)),
         r->ExceptionCode == EXCEPTION_ACCESS_VIOLATION ? (r->ExceptionInformation[0] ? "write" : "read") : "",
         (unsigned long)(r->NumberParameters > 1 ? r->ExceptionInformation[1] : 0),
         (unsigned long)c->Eax, (unsigned long)c->Ebx, (unsigned long)c->Ecx, (unsigned long)c->Edx, (unsigned long)c->Esi,
         (unsigned long)c->Edi, (unsigned long)c->Ebp, (unsigned long)c->Esp,
         (unsigned long)*(volatile DWORD *)0x005a7e1c, (unsigned long)*(volatile DWORD *)0x004c2164,
         (unsigned long)*(volatile DWORD *)0x004c2720, (unsigned long)*(volatile DWORD *)0x004c2728);
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
    DWORD n = GetEnvironmentVariableA("I76_PHYS_RATE", v, sizeof(v));
    if (n == 0 || n >= sizeof(v) || (rate = atoi(v)) < 10 || rate > 2000) return;
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
static struct { void *s; float acc; int n; DWORD frame; } g_step_acc[64];

static int step_slot(void *stepper, int add) {
    int i, slot = -1;
    for (i = 0; i < 64; i++) {
        if (g_step_acc[i].s == stepper) return i;
        if (slot < 0 && g_step_acc[i].s == 0) slot = i;
    }
    if (!add) return -1;
    if (slot < 0) slot = (int)(((DWORD_PTR)stepper >> 4) & 63);   /* table full: reuse a slot */
    g_step_acc[slot].s = stepper; g_step_acc[slot].acc = 0.0f;
    return slot;
}

static void __cdecl fixed_stepper_begin(float *stepper) {
    float sim_dt = *(volatile float *)0x004fe420;          /* simclock_sim_dt */
    int slot = step_slot(stepper, 1), n;
    g_step_acc[slot].acc += sim_dt;
    n = (int)(g_step_acc[slot].acc / g_fixed_step);
    if (n > 20) { n = 20; g_step_acc[slot].acc = 0.0f; } else g_step_acc[slot].acc -= (float)n * g_fixed_step;
    g_step_acc[slot].n = n; g_step_acc[slot].frame = g_frame;   /* for render interpolation */
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
    if (GetEnvironmentVariableA("I76_INPUT_LATCH", NULL, 0) == 0) {
        if (g_fixed_step > 0.0f)
            mlog("  input-latch: off - with I76_FIXED_STEP the ignition (I) and lights keys are lost on frames without a physics step; I76_INPUT_LATCH=1 keeps them");
        return;
    }
    n = patch_bytes(0x0044f4cf, ign_old, ign_new, 6, "ignition request copy (input latch)")
      + patch_bytes(0x0044f4dc, lgt_old, lgt_new, 6, "lights request copy (input latch)");
    mlog("  input-latch: %d/2 sites (ignition, lights requests held until the next physics step)%s", n,
         g_fixed_step > 0.0f ? "" : " - note: without I76_FIXED_STEP every frame steps, so this changes nothing");
}

static void apply_fixed_step(void) {
    static const BYTE old_entry[6] = { 0xD9, 0x05, 0x20, 0xE4, 0x4F, 0x00 };   /* fld [0x4fe420] at 0x49cc20 */
    BYTE jmp[6] = { 0xE9, 0, 0, 0, 0, 0x90 };
    char v[16]; double rate;
    LONG rel = (LONG)((DWORD_PTR)fixed_stepper_begin - (0x0049cc20 + 5));
    DWORD n = GetEnvironmentVariableA("I76_FIXED_STEP", v, sizeof(v));
    if (n == 0 || n >= sizeof(v) || (rate = atof(v)) < 10.0 || rate > 1000.0) return;   /* fractional rates allowed */
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
static void apply_coll_window(void) {
    static const struct { DWORD site; BYTE old[5]; const char *what; } s[3] = {
        { 0x004349da, { 0xE8, 0xC1, 0x7D, 0x06, 0x00 }, "collision sweep dt (driver 0x4349c0)" },        /* -> [esp+0x10], the xz AABB sweep extent */
        { 0x00434c70, { 0xE8, 0x2B, 0x7B, 0x06, 0x00 }, "collision sweep dt (pair test 0x434bb0)" },     /* pushed to the swept-sphere test 0x434f00 */
        { 0x0043f9e1, { 0xE8, 0xBA, 0xCD, 0x05, 0x00 }, "collision sweep dt (scenery tree 0x43f8c0)" },  /* pushed to the node sweep */
    };
    int i, n = 0;
    if (GetEnvironmentVariableA("I76_COLL_WINDOW", NULL, 0) == 0) return;
    if (g_fixed_step <= 0.0f) { mlog("  coll-window: needs I76_FIXED_STEP - not applied"); return; }
    for (i = 0; i < 3; i++) {
        BYTE w[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)coll_dt - (s[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(s[i].site, s[i].old, w, 5, s[i].what);
    }
    mlog("  coll-window: %d/3 sweep dt reads -> max(sim_dt, fixed step %.1f ms)", n, g_fixed_step * 1000.0f);
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
    int r = ((int (__cdecl *)(BYTE **, BYTE **, void *, void *))0x0043f510)(ra, rb, ca, cb), i, slot = 0;
    BYTE *a, *b;
    DWORD oldest = 0xffffffff;
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
    return ((int (__cdecl *)(const char *, BYTE *, int))0x004231f0)(name, obj, flag);
}
static DWORD __cdecl coll_damage_wrap(DWORD victim, DWORD source, DWORD v, DWORD n, DWORD p) {
    if (g_coll_dup) return 1;                                                  /* "victim still there"; both callers ignore it */
    return ((DWORD (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD))0x004a7c80)(victim, source, v, n, p);
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
    { char v[8]; DWORD k = GetEnvironmentVariableA("I76_COLL_DEDUPE", v, sizeof(v)); if (k && k < sizeof(v) && v[0] == '0') g_coll_dedupe = 0; }
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
static void mark_live(void) {                                /* which of this frame's vehicles are still live objects */
    BYTE *node = *(BYTE **)0x0054b204;
    int i, guard = 0;
    for (i = 0; i < 64; i++) g_ie[i].live = 0;
    while (node && guard++ < 4096) {
        BYTE *o = ((BYTE *(__cdecl *)(DWORD, const char *))0x0045f0f0)(*(DWORD *)(node + 8), (const char *)0x004f7c5c);
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
    if (GetEnvironmentVariableA("I76_RENDER_INTERP", NULL, 0) == 0) return;
    {
        char sv[8];
        DWORD k = GetEnvironmentVariableA("I76_INTERP_SMOOTH", sv, sizeof(sv));
        if (k > 0 && k < sizeof(sv)) g_smooth = atoi(sv);
    }
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
 * Static reading only - NOT yet verified live.
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

static void tel_event(DWORD type, float f0, float f1, float f2, float f3, int i0, int i1) {
    DWORD seq = ++g_tel_ev_seq;
    i76tel_event_t *e = &g_tel_ring[seq % I76TEL_RING];
    e->seq = seq; e->frame = g_frame; e->type = type;
    e->f[0] = f0; e->f[1] = f1; e->f[2] = f2; e->f[3] = f3;
    e->i[0] = i0; e->i[1] = i1;
}

/* the local player's object and entity, or 0 */
static BYTE *tel_player(BYTE **ent_out) {
    BYTE **rec = *(BYTE ***)0x0054a264, *obj, *ent;
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
    t->frame = *(DWORD *)0x005a7e1c;                         /* simclock_frame_count */
    t->proxy_frame = g_frame;
    t->sim_time = *(float *)0x005a7e74;                      /* simclock_time */
    t->sim_dt = *(float *)0x004fe420;                        /* simclock_sim_dt */
    t->dt = *(float *)0x004fe428;                            /* simclock_dt */
    t->step_count = -1;
    t->ffb_present = *(DWORD *)0x0052bbd0;
    t->ffb_rpm = *(int *)0x004f2334;
    t->ffb_engine_running = *(DWORD *)0x004f2338;
    t->ffb_engine_starting = *(DWORD *)0x004f233c;
    t->ffb_gear_changed = *(DWORD *)0x004f2340;
    t->ffb_nitrous = *(DWORD *)0x004f2344;
    memcpy(t->accel_body, (void *)0x004f2418, 12);
    t->ffb_list_ordnance = *(DWORD *)0x004f2478;
    t->ffb_list_concussion = *(DWORD *)0x004f247c;
    t->ffb_list_collision = *(DWORD *)0x004f2484;
    t->ffb_dt = *(float *)0x004f2488;
    t->event_seq = g_tel_ev_seq;
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
    t->health_pct = ((float (__cdecl *)(BYTE *))0x0040b450)(obj);                        /* object_HealthFraction, pure read */
    t->flags = *(DWORD *)(ent + 0x454); t->surface = *(DWORD *)(ent + 0x45c);
    memcpy(t->ground_normal, ent + 0x460, sizeof t->ground_normal);
    t->clearance = *(float *)(ent + 0x470); t->state_timer = *(float *)(ent + 0x450);
    memcpy(t->armour, ent + 0x138, 16); memcpy(t->armour_max, ent + 0x158, 16);
    memcpy(t->chassis, ent + 0x148, 16); memcpy(t->chassis_max, ent + 0x168, 16);
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
    n = *(int *)0x005da78c;
    if (n > 150) n = 150;                                     /* 0x5be4d8..0x5d88d8 holds 151 records at most */
    for (i = 0; i < n; i++) {
        BYTE *rec = (BYTE *)0x005be4d8 + i * 0x2c8;
        int row;
        if (*(BYTE **)rec != obj) continue;
        row = *(int *)(rec + 4);
        t->weapon_row = row;
        if (row >= 0 && row < 7) {
            int idx = *(int *)(rec + 0x58 + row * 0x58 + 0x50);   /* slot+0x50 is an INDEX into the instance table
                                                                       (I76_WeaponSlot; live: 2/3/1 on the sandbox car) */
            BYTE *inst = (idx >= 0 && idx < *(int *)0x005da750 && idx < 150) ? (BYTE *)0x005aab08 + idx * 0x4c : 0, *root;
            if (inst) {
                t->weapon_def = *(int *)(inst + 0x30); t->weapon_ammo = *(int *)(inst + 0x20); t->weapon_hp = *(int *)(inst + 0xc);
                root = *(BYTE **)(inst + 8);
                if (root) memcpy(t->weapon_name, root, 8);
            }
        }
        break;
    }
    if (g_fixed_step > 0.0f) {                               /* substeps the fixed stepper ran in the frame just completed */
        int st = step_slot(ent + 0x444, 0);
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
    ((void (__cdecl *)(BYTE *, BYTE *, int, float))0x004a6e90)(inst, wdef, count, dt_left);   /* weapon_FireShot */
    if (!inst) return;
    vrec = *(BYTE ***)(inst + 0x18);                         /* I76_WeaponInstance.vrec -> +0 vehicle object */
    veh = vrec ? *vrec : 0;
    if (veh && ((int (__cdecl *)(BYTE *))0x00458bf0)(veh))   /* object_IsPlayer */
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
    int is_player = target && ((int (__cdecl *)(BYTE *))0x00458bf0)(target) != 0;
    int before = is_player ? tel_health_sum(target) : 0, r;
    float v[3] = { 0.0f, 0.0f, 0.0f };
    if (impact) { v[0] = impact[0]; v[1] = impact[1]; v[2] = impact[2]; }
    r = ((int (__cdecl *)(BYTE *, BYTE *, float *, float *, float *))g_tel_coll_tramp)(target, source, normal, impact, dir);
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
    if (!g_tel_tramp) g_tel_tramp = (BYTE *)VirtualAlloc(NULL, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_tel_tramp || g_tel_tramp_used + n + 5 > 64 || n > 11 || memcmp((void *)entry, expect, n) != 0) {
        mlog("  patch: %s at 0x%08lX has UNEXPECTED bytes (or no trampoline room) - not patching", what, (unsigned long)entry);
        return 0;
    }
    tr = g_tel_tramp + g_tel_tramp_used;
    memcpy(tr, expect, n);
    tr[n] = 0xE9; rel = (LONG)((entry + n) - ((DWORD_PTR)tr + n + 5)); memcpy(tr + n + 1, &rel, 4);
    memset(patch, 0x90, sizeof patch);
    patch[0] = 0xE9; rel = (LONG)((DWORD_PTR)hook - (entry + 5)); memcpy(patch + 1, &rel, 4);
    if (!patch_bytes(entry, expect, patch, n, what)) return 0;
    g_tel_tramp_used += n + 5;
    return tr;
}

static void apply_telemetry(void) {
    static const BYTE expl_old[8] = { 0x8B, 0x44, 0x24, 0x04, 0x8B, 0x4C, 0x24, 0x08 };   /* 0x49ead0: mov eax,[esp+4]; mov ecx,[esp+8] */
    static const BYTE coll_old[6] = { 0x81, 0xEC, 0xD0, 0x00, 0x00, 0x00 };               /* 0x4a7c80: sub esp, 0xd0 */
    static const DWORD fire_sites[2] = { 0x004a6b16, 0x004a6d43 };                          /* call 0x4a6e90 in weapon_UpdateInstanceFiring */
    char v[16]; int port, hooks = 0, i;
    DWORD n = GetEnvironmentVariableA("I76_TELEMETRY", v, sizeof(v));
    if (n == 0 || n >= sizeof(v)) return;
    port = atoi(v);
    if (port == 1) port = I76TEL_PORT;
    if (port < 1 || port > 65535) { mlog("  telemetry: '%s' is not a port - off", v); return; }
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
    g_tel_map = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(i76tel_shm_t), I76TEL_SHM_NAME);
    if (g_tel_map) {
        g_tel_shm = (i76tel_shm_t *)MapViewOfFile(g_tel_map, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(i76tel_shm_t));
        if (g_tel_shm) { memset(g_tel_shm, 0, sizeof *g_tel_shm); g_tel_shm->size = sizeof(i76tel_shm_t); }
    }
    /* events */
    for (i = 0; i < 2; i++) {
        BYTE o[5] = { 0xE8 }, w[5] = { 0xE8 };
        LONG rel = (LONG)(0x004a6e90 - (fire_sites[i] + 5));
        memcpy(o + 1, &rel, 4);
        rel = (LONG)((DWORD_PTR)tel_fire_wrap - (fire_sites[i] + 5)); memcpy(w + 1, &rel, 4);
        hooks += patch_bytes(fire_sites[i], o, w, 5, "weapon_FireShot call (telemetry)");
    }
    g_tel_expl_tramp = tel_detour(0x0049ead0, expl_old, 8, (void *)tel_expl_hook, "entity_SpawnExplosion entry (telemetry)");
    g_tel_coll_tramp = tel_detour(0x004a7c80, coll_old, 6, (void *)tel_coll_hook, "physics_ApplyCollisionDamage entry (telemetry)");
    hooks += (g_tel_expl_tramp != 0) + (g_tel_coll_tramp != 0);
    g_tel_on = 1;
    mlog("  telemetry: on - udp 127.0.0.1:%d %s, shm %s %s, %d/4 event hooks (FireShot call sites x2, SpawnExplosion entry, ApplyCollisionDamage entry), frame %u B + events %u B, ring %d",
         port, g_tel_sock != INVALID_SOCKET ? "open" : "FAILED", I76TEL_SHM_NAME, g_tel_shm ? "mapped" : "FAILED",
         hooks, (unsigned)sizeof(i76tel_frame_t), (unsigned)sizeof(i76tel_event_t), I76TEL_RING);
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

static DWORD __stdcall hook_grSstWinOpen(DWORD hwnd, DWORD res, DWORD refresh, DWORD cfmt, DWORD origin, int ncol, int naux) {
    DWORD r;
    mlog("  glide-refresh: grSstWinOpen(res %lu, refresh %lu -> %lu (%lu Hz), cfmt %lu, origin %lu, %d/%d buffers)",
         (unsigned long)res, (unsigned long)refresh, (unsigned long)g_glide_refresh_code, (unsigned long)g_glide_refresh_hz,
         (unsigned long)cfmt, (unsigned long)origin, ncol, naux);
    r = p_grSstWinOpen(hwnd, res, g_glide_refresh_code, cfmt, origin, ncol, naux);
    mlog("  glide-refresh: context %lu", (unsigned long)r);
    if (!r) {   /* dgVoodoo rejects codes above 8 (measured 2026-10-02: code 9 -> context 0, then the exe faults at
                   0x42e209): never leave the game without a window - fall back to what the renderer asked for */
        r = p_grSstWinOpen(hwnd, res, refresh, cfmt, origin, ncol, naux);
        mlog("  glide-refresh: code %lu rejected - reopened with the renderer's own refresh %lu, context %lu",
             (unsigned long)g_glide_refresh_code, (unsigned long)refresh, (unsigned long)r);
    }
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
    DWORD v = *(volatile DWORD *)0x006442ec, cur = *(volatile DWORD *)0x00654380, base = *(volatile DWORD *)0x005dd324;
    DWORD nc = *(volatile DWORD *)0x006543b8, nb = *(volatile DWORD *)0x006543bc;
    g_fs_scenes++;
    g_fs_vcount = v; g_fs_recs = *(volatile DWORD *)0x0059c568;
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
             (unsigned long)g_fs_spikes, (unsigned long)g_tc_swaps, (unsigned long)g_frame, t1, (unsigned long)*(volatile DWORD *)0x004c2164,
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
    int r = ((int (__cdecl *)(BYTE *))0x004929b0)(cam);
    if (r == 0 && g_cg_on && cam) {
        double *py = (double *)(cam + 0x168), y0 = *py;
        double h = ((double (__cdecl *)(double, double))0x00493550)(*(double *)(cam + 0x160), *(double *)(cam + 0x170));
        if (h > -1.0e6 && h < 1.0e6 && h + 0.05 > y0 && h + 0.05 - y0 < 50.0) {
            *py = h + 0.05;
            r = ((int (__cdecl *)(BYTE *))0x004929b0)(cam);
            *py = y0;
            g_cg_lifts++;
            if (!r) g_cg_fail++;
            if (g_cg_lifts <= 20 || !r)
                mlog("  cam-ground-fix: lift #%lu (camera %p, %s): eye %.3f m under the terrain height %.2f; setup %s",
                     (unsigned long)g_cg_lifts, (void *)cam, cam == (BYTE *)0x004c2730 ? "main" : "other", h - y0, h, r ? "ok, terrain queued" : "STILL refused");
        }
    }
    return r;
}
static void apply_cam_ground_fix(void) {
    static const BYTE old[5] = { 0xe8, 0x8d, 0x1e, 0x00, 0x00 };   /* call 0x4929b0 at 0x490b1e */
    BYTE w[5] = { 0xe8 }; LONG rel; char c[4]; DWORD k = GetEnvironmentVariableA("I76_CAM_GROUND_FIX", c, sizeof(c));
    if (!(k && k < sizeof(c) && c[0] == '1')) return;
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
    DWORD v = *(volatile DWORD *)0x006442ec; BYTE *cam = *(BYTE **)0x006442d4; double p[3] = { 0, 0, 0 }, mv = 0.0, gh = 0.0;
    g_fp_scenes++;
    if (!g_fp_logged_cam) { g_fp_logged_cam = 1; mlog("  flash-probe: first main scene: flush camera %p, QueueTerrain camera %p", cam_arg, (void *)cam); }
    if (cam) { memcpy(p, cam + 0x160, sizeof p); }
    { double dx = p[0] - g_fp_prev_pos[0], dy = p[1] - g_fp_prev_pos[1], dz = p[2] - g_fp_prev_pos[2]; mv = sqrt(dx * dx + dy * dy + dz * dz); }
    if (v < g_fp_win_vmin) g_fp_win_vmin = v;
    if (g_fp_prev_v > 500 && (v == 0 || (v * 10 < g_fp_prev_v * 3 && mv < 2.0))) {
        float *pl = (float *)0x0054e11c;
        g_fp_events++; if (v == 0) { g_fp_zero++; g_fp_win_zero++; } else { g_fp_drop++; g_fp_win_drop++; }
        if (cam) gh = ((double (__cdecl *)(double, double))0x00493550)(p[0], p[2]);
        if (g_fp_events <= 300)
            mlog("  flash-probe: TERRAIN-DROP #%lu at swap %lu (proxy frame %lu, t %.0f ms, state %lu, cam mode %lu): terrain vertices %lu (previous scene %lu) | camera (%.2f, %.2f, %.2f), %.3f m above the terrain height %.2f, moved %.2f m since the previous scene | player (%.1f, %.1f, %.1f) | records %lu",
                 (unsigned long)g_fp_events, (unsigned long)g_tc_swaps, (unsigned long)g_frame, tc_ms(), (unsigned long)*(volatile DWORD *)0x004c2164,
                 (unsigned long)*(volatile DWORD *)0x004c2728, (unsigned long)v, (unsigned long)g_fp_prev_v, p[0], p[1], p[2], p[1] - gh, gh, mv,
                 pl[0], pl[1], pl[2], (unsigned long)*(volatile DWORD *)0x0059c568);
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
    if (*(volatile DWORD *)0x004c2164 != 5) { g_fp_prev_flag = 0; return; }     /* missions only */
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
                     (unsigned long)*(volatile DWORD *)0x004c2728, r[0], r[1], r[2], g_fp_rows[1], a[0], a[1], a[2], ma, g_fp_rows[2], b[0], b[1], b[2], mb,
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

static void __stdcall tc_Swap(int interval) {
    DWORD flag = tc_zg(0x10178ea0), res = tc_zg(0x1001fd20) - g_tc_minaddr;
    double t0;
    if (g_fp_on) fp_before_swap();
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
static void tex_census_attach(HMODULE m) {
    void *o;
    g_tc_zg = m; g_tc_minc = 0; g_tc_swaps = 0;
    p_tc_CalcMem = (DWORD (__stdcall *)(int, int, int, int))GetProcAddress(GetModuleHandleA("glide2x.dll"), "_grTexCalcMemRequired@16");
#define TC_HOOK(name, hook, ptr) o = patch_iat(m, "glide2x.dll", name, (void *)hook); if (o && o != (void *)hook) *(void **)&ptr = o;
    TC_HOOK("_grTexMaxAddress@4", tc_MaxAddress, p_tc_MaxAddress)
    TC_HOOK("_grTexMinAddress@4", tc_MinAddress, p_tc_MinAddress)
    TC_HOOK("_grTexDownloadMipMap@16", tc_Download, p_tc_Download)
    TC_HOOK("_grBufferSwap@4", tc_Swap, p_tc_Swap)
#undef TC_HOOK
    mlog("  tex-census: ZGLIDE at %p: max %s, min %s, download %s, swap %s, calcmem %s; ZGLIDE 0x1a93 = %02x %02x (75 = stock boundary rule, eb = tmufix)",
         (void *)m, p_tc_MaxAddress ? "hooked" : "NOT", p_tc_MinAddress ? "hooked" : "NOT", p_tc_Download ? "hooked" : "NOT",
         p_tc_Swap ? "hooked" : "NOT", p_tc_CalcMem ? "found" : "NOT found", ((BYTE *)m)[0x1a93], ((BYTE *)m)[0x1a94]);
}

/* I76_GLIDE_DIR=<subfolder> (EXPERIMENT, lab docs/WIDESCREEN-2D.md): menus and cutscenes are 640x480 DirectDraw (dgVoodoo's
 * DDraw.dll), missions are Glide (its Glide2x.dll), and each dgVoodoo DLL looks for dgVoodoo.conf in its own folder
 * first. Loading <game>\<subfolder>\Glide2x.dll before ZGLIDE binds ZGLIDE's glide2x.dll import to that copy, so the
 * mission can take that folder's conf (widescreen, stretched) while the shell keeps the game folder's (4:3). */
static char g_glide_dir[MAX_PATH];
static int g_zg_tmufix;                     /* I76_ZGLIDE_TMUFIX=1 */
static HMODULE WINAPI hook_LoadLibraryA(LPCSTR name) {
    HMODULE m;
    if (name && g_glide_dir[0]) {
        const char *b0 = strrchr(name, '\\'); b0 = b0 ? b0 + 1 : name;
        if (_strnicmp(b0, "zglide", 6) == 0 && !GetModuleHandleA("glide2x.dll")) {
            char path[MAX_PATH]; HMODULE g;
            wsprintfA(path, "%s\\%s\\Glide2x.dll", g_dir, g_glide_dir);
            g = p_LoadLibraryA(path);
            mlog("  glide-dir: %s %s", path, g ? "loaded before ZGLIDE" : "FAILED to load - the game folder's Glide2x.dll will be used");
        }
    }
    m = p_LoadLibraryA(name);
    if (m && name) {
        const char *b = strrchr(name, '\\'); b = b ? b + 1 : name;
        if (_strnicmp(b, "zglide", 6) == 0 && g_zg_tmufix) {
            /* I76_ZGLIDE_TMUFIX=1: ZGLIDE+0x1a93 `jne +0x24` (75 24) -> `jmp +0x24` (eb 24): skip the Voodoo 1 "no texture
               across 2 MB" rule. Its rewind target is the constant 2 MB, and it runs BEFORE the grTexMaxAddress check, so
               under MemorySizeOfTMU 4096 the first allocation that would pass the 4 MB top moves next-free back to 2 MB
               while the textures at 2..4 MB stay in the slot list: later uploads overwrite live textures (the owner's
               "texture exchange" with 4096, promotion 5R). Lab docs/RENDER-FREEZE-2026-10-04.md, TEXTURE-DELIVERY.md s.2. */
            BYTE *p = (BYTE *)m + 0x1a93; DWORD op;
            if (p[0] == 0x75 && p[1] == 0x24 && VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &op)) {
                p[0] = 0xEB; VirtualProtect(p, 1, op, &op); FlushInstructionCache(GetCurrentProcess(), p, 1);
                mlog("  zglide-tmufix: ZGLIDE+0x1a93 75 24 -> %02x 24 (2 MB boundary rule skipped)", p[0]);
            } else mlog("  zglide-tmufix: ZGLIDE+0x1a93 = %02x %02x, not the stock 75 24 - not applied", p[0], p[1]);
        }
        if (_strnicmp(b, "zglide", 6) == 0 && g_tc_on) tex_census_attach(m);
        /* (the census alone hooks LoadLibraryA too: the refresh wrapper is only for the two switches that did before) */
        if (_strnicmp(b, "zglide", 6) == 0 && !p_grSstWinOpen && (g_glide_dir[0] || g_glide_refresh_code != 0xffffffff)) {
            p_grSstWinOpen = (grSstWinOpen_t)patch_iat(m, "glide2x.dll", "_grSstWinOpen@28", hook_grSstWinOpen);
            mlog("  glide-refresh: %s loaded at %p, grSstWinOpen slot %s", b, (void *)m, p_grSstWinOpen ? "repointed" : "NOT found");
        }
    }
    return m;
}

static void apply_glide_refresh(void) {
    static const struct { DWORD hz, code; } tab[] = { {60, 0}, {70, 1}, {72, 2}, {75, 3}, {80, 4}, {90, 5}, {100, 6}, {85, 7}, {120, 8}, {0, 0xff} };
    char v[8]; DWORD n; int i;
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_TEX_CENSUS", c, sizeof(c));
        if ((k && k < sizeof(c) && (c[0] == '1' || c[0] == '2')) || g_fs_ms) {   /* I76_FRAME_SPIKES needs the census hooks */
            g_tc_on = (k && k < sizeof(c) && c[0] == '2') ? 2 : 1;
            if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
            if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
            mlog("  tex-census: on, LoadLibraryA %s", p_LoadLibraryA ? "hooked" : "NOT hooked");
        }
    }
    {   char c[4]; DWORD k = GetEnvironmentVariableA("I76_ZGLIDE_TMUFIX", c, sizeof(c));
        if (k && k < sizeof(c) && c[0] == '1') {
            g_zg_tmufix = 1;
            if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
            mlog("  zglide-tmufix: armed, LoadLibraryA %s", p_LoadLibraryA ? "hooked" : "NOT hooked");
        }
    }
    {   DWORD k = GetEnvironmentVariableA("I76_GLIDE_DIR", g_glide_dir, sizeof(g_glide_dir));
        if (k == 0 || k >= sizeof(g_glide_dir)) g_glide_dir[0] = 0;
        else if (!p_LoadLibraryA) {
            p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
            mlog("  glide-dir: %s, LoadLibraryA %s", g_glide_dir, p_LoadLibraryA ? "hooked" : "NOT hooked");
        }
    }
    n = GetEnvironmentVariableA("I76_GLIDE_REFRESH", v, sizeof(v));
    if (n == 0 || n >= sizeof(v)) return;
    g_glide_refresh_hz = (DWORD)atoi(v);
    for (i = 0; i < (int)(sizeof tab / sizeof tab[0]); i++) if (tab[i].hz == g_glide_refresh_hz) g_glide_refresh_code = tab[i].code;
    {   /* probe knob: I76_GLIDE_REFRESH_CODE=<n> passes a raw GrScreenRefresh_t code (Glide 2.x defines 0..8) */
        char c[8]; DWORD kc = GetEnvironmentVariableA("I76_GLIDE_REFRESH_CODE", c, sizeof(c));
        if (kc && kc < sizeof(c)) g_glide_refresh_code = (DWORD)strtoul(c, NULL, 0);
    }
    if (g_glide_refresh_code == 0xffffffff) { mlog("  glide-refresh: %s is not a Glide refresh (60 70 72 75 80 85 90 100 120, 0 = none) - not applied", v); return; }
    if (!p_LoadLibraryA) p_LoadLibraryA = (HMODULE (WINAPI *)(LPCSTR))patch_iat(GetModuleHandleA(NULL), "KERNEL32.dll", "LoadLibraryA", hook_LoadLibraryA);
    mlog("  glide-refresh: %lu Hz (code %lu) armed; LoadLibraryA %s", (unsigned long)g_glide_refresh_hz, (unsigned long)g_glide_refresh_code,
         p_LoadLibraryA ? "hooked" : "NOT hooked");
}

/* ===========================================================================
 * TRAINER CONTROL BLOCK  (always on; I76_TRAINER=0 disables)
 * ===========================================================================
 * tools/trainer/i76trn.h is the contract: a 192-byte i76trn_ctl_t in the shared memory Local\I76Trainer that a
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
 *   one-shots (req_seq != ack_seq) repair, teleport, ammo, slot ammo, play flags, stop
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
    int n = *(int *)0x005da750, i, hit = 0;
    if (n > 150) n = 150;
    for (i = 0; i < n; i++) {
        BYTE *inst = (BYTE *)0x005aab08 + i * 0x4c, *vrec = *(BYTE **)(inst + 0x18);
        if (!*(DWORD *)(inst + 4) || !vrec || *(BYTE **)vrec != obj) continue;
        if (ammo >= 0) *(int *)(inst + 0x20) = ammo;
        if (hp_max && *(int *)(inst + 0x14) > 0) *(int *)(inst + 0xc) = *(int *)(inst + 0x14);
        hit++;
    }
    return hit;
}

static void trn_apply_inner(void) {
    i76trn_ctl_t *c = g_trn;
    volatile DWORD *play = (volatile DWORD *)0x00654b98;
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
        case I76TRN_CMD_TELEPORT: memcpy(obj + 0x40, c->pos, 24); memcpy(ent + 0xbc, c->vel, 12); memset(ent + 0xc8, 0, 12);
                                  trn_msg("teleported"); break;
        case I76TRN_CMD_AMMO:     { char b[64]; wsprintfA(b, "ammo set on %d weapons", trn_weapons(obj, c->ammo_value, 0)); trn_msg(b); } break;
        case I76TRN_CMD_SLOT_AMMO: {
            int n = *(int *)0x005da750, i = c->slot_index;
            BYTE *inst = (BYTE *)0x005aab08 + i * 0x4c;
            if (i < 0 || i >= n || i >= 150 || !*(DWORD *)(inst + 4)) { c->cmd_result = 3; trn_msg("bad weapon slot"); }
            else { *(int *)(inst + 0x20) = c->ammo_value; trn_msg("slot ammo set"); }
            break; }
        case I76TRN_CMD_STOP:     memset(ent + 0xbc, 0, 12); memset(ent + 0xc8, 0, 12); trn_msg("stopped"); break;
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
    volatile DWORD *play = (volatile DWORD *)0x00654b98;
    if (g_trn_forcing) *play = (*play & ~g_trn_forcing) | (g_trn_play_saved & g_trn_forcing);
}
static void trn_reforce(void) {
    if (g_trn && g_trn->magic == I76TRN_MAGIC && g_trn_forcing) *(volatile DWORD *)0x00654b98 |= g_trn_forcing;
}
static DWORD g_trn_guard_hits;
static void __cdecl trn_savedef_wrap(void) {               /* player_SaveDef 0x497290: no args, result unused */
    trn_unforce(); g_trn_guard_hits++;
    ((void (__cdecl *)(void))0x00497290)();
    if (*(volatile DWORD *)0x004c2164 == 5) trn_reforce();  /* mid-mission (video-mode key) only; at mission end leave them off */
}
static void __cdecl trn_menuclose_wrap(void) {             /* 0x495170: no args (push esi / ... / pop esi; ret) */
    trn_unforce(); g_trn_guard_hits++;
    ((void (__cdecl *)(void))0x00495170)();
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
    char v[8];
    DWORD k = GetEnvironmentVariableA("I76_TRAINER", v, sizeof(v));
    if (k && k < sizeof(v) && v[0] == '0') { mlog("  trainer: disabled (I76_TRAINER=0)"); return; }
    g_trn_map = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(i76trn_ctl_t), I76TRN_SHM_NAME);
    if (g_trn_map) g_trn = (i76trn_ctl_t *)MapViewOfFile(g_trn_map, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(i76trn_ctl_t));
    if (!g_trn) { mlog("  trainer: shared memory %s NOT created (%lu)", I76TRN_SHM_NAME, GetLastError()); return; }
    memset(g_trn, 0, sizeof *g_trn);                          /* a front end that mapped first sees the block reset */
    g_trn->version = I76TRN_VERSION; g_trn->size = sizeof(i76trn_ctl_t);
    trn_msg("proxy ready");
    install_frame_hook();
    g_trn->magic = g_frame_hook ? I76TRN_MAGIC : 0;           /* no hook, no service: the magic stays clear */
    mlog("  trainer: %s (%s, %u B, frame hook %s)", g_frame_hook ? "on" : "NOT applied", I76TRN_SHM_NAME,
         (unsigned)sizeof(i76trn_ctl_t), g_frame_hook ? "ok" : "missing");
    if (g_frame_hook) {
        int g = trn_install_guard();
        mlog("  trainer: cheat-marker guard %d/4 sites (SaveDef x2, options-menu close x2)%s", g,
             g == 4 ? "" : " - INCOMPLETE: God / Ammo held through a menu close or a mission end can still mark the game as cheated");
    }
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

/* TERRAIN DETAIL DISTANCE  (I76_TERRAIN_LOD=<factor 1..16>; off by default; EXPERIMENT, sandbox only)
 * The terrain is a quadtree rebuilt every frame (i76-map subsystems/renderer.md, 0x491341): a node becomes a leaf when
 * d2 > (2h)^2 * K, K ~ A, and otherwise splits when a midpoint height error exceeds a threshold ~ B. Nothing blends
 * between levels, so vertices snap as the camera approaches. renderer_SetTerrainResolution 0x493080 loads A [0x4fad20]
 * and B [0x4fad24] from immediates: Low 6.4 / 1/256, Medium 16 / 1/384, High 40 / 1/576.7. The switch multiplies A and
 * divides B in all three, so every split happens `factor` (A) / sqrt-ish (B) farther out. More vertices per frame:
 * the int16 vertex-index ceiling (32,767 per frame, FARCLIP-CAMERA-CRASH.md) comes closer, so soak with the far clip. */
static void apply_terrain_lod(void) {
    static const struct { DWORD_PTR a_site, b_site; float a, b; } lv[3] = {
        { 0x4930bb + 6, 0x4930c5 + 6, 6.4f,  0.00390625f },      /* Low */
        { 0x493094 + 6, 0x49308a + 6, 16.0f, 0.0026041667f },    /* Medium (the defaults) */
        { 0x4930a5 + 6, 0x4930af + 6, 40.0f, 0.0017342f },       /* High */
    };
    char v[16]; DWORD n; float f; int i, ok = 0;
    n = GetEnvironmentVariableA("I76_TERRAIN_LOD", v, sizeof(v));
    if (n == 0 || n >= sizeof(v)) return;
    f = (float)atof(v);
    if (f < 1.0f || f > 16.0f) { mlog("  terrain-lod: %s out of range (1..16) - not applied", v); return; }
    for (i = 0; i < 3; i++) {
        float a0, b0, a1, b1;
        memcpy(&a0, (const void *)lv[i].a_site, 4); memcpy(&b0, (const void *)lv[i].b_site, 4);   /* the exe's own bits */
        if (a0 < lv[i].a * 0.99f || a0 > lv[i].a * 1.01f || b0 < lv[i].b * 0.99f || b0 > lv[i].b * 1.01f) { mlog("  terrain-lod: level %d constants are not the expected values - skipped", i); continue; }
        a1 = a0 * f; b1 = b0 / f;
        ok += patch_bytes(lv[i].a_site, (const BYTE *)&a0, (const BYTE *)&a1, 4, "terrain-lod A");
        ok += patch_bytes(lv[i].b_site, (const BYTE *)&b0, (const BYTE *)&b1, 4, "terrain-lod B");
    }
    mlog("  terrain-lod: x%.2f, %d/6 constants patched (split distance up, height-error threshold down)", f, ok);
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
    n = GetEnvironmentVariableA("I76_TERRAIN_TEX", v, sizeof(v));
    if (n && n < sizeof(v)) {
        f = (float)atof(v);
        if (f < 1.0f || f > 16.0f) mlog("  terrain-tex: %s out of range (1..16) - not applied", v);
        else {
            static const BYTE expect[6] = { 0x8d, 0x04, 0x80, 0xc1, 0xe0, 0x03 };
            BYTE want[6] = { 0x69, 0xc0, 0, 0, 0, 0 };
            DWORD k = (DWORD)(40.0f * f + 0.5f);
            memcpy(want + 2, &k, 4);
            if (patch_bytes(0x492458, expect, want, 6, "terrain-tex")) mlog("  terrain-tex: x%.2f (texture level boundaries at %lu/40 x stock distance)", f, (unsigned long)k);
        }
    }
    n = GetEnvironmentVariableA("I76_OBJECT_LOD", v, sizeof(v));
    if (n && n < sizeof(v)) {
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
    char v[16]; DWORD n = GetEnvironmentVariableA(env, v, sizeof(v)); float f, val;
    if (n == 0 || n >= sizeof(v)) return;
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
    ((void (__cdecl *)(void *, int))0x0048fac0)(cam, flag);
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
    n = GetEnvironmentVariableA("I76_ROAD_POOL", v, sizeof(v));
    if (n && n < sizeof(v)) {
        factor = atoi(v);
        if (factor == 0) { mlog("  road-pool: off (I76_ROAD_POOL=0)"); return; }
        if (factor < 1 || factor > 64) { mlog("  road-pool: I76_ROAD_POOL=%s out of range (0 off, 1..64) - using 16", v); factor = 16; }
        want = 1;
    }
    n = GetEnvironmentVariableA("I76_ROAD_DIST", v, sizeof(v));
    if (n && n < sizeof(v)) { road = (float)atof(v); if (road > 450.0f) want = 1; }
    n = GetEnvironmentVariableA("I76_FAR_CLIP", v, sizeof(v));
    if (n && n < sizeof(v)) want = 1;
    if (!want) return;
    if (memcmp((void *)0x0048f9d6, pool_old, 5) || memcmp((void *)0x004904cd, head_old, 5) ||
        memcmp((void *)0x00490578, exit_old, 10)) { mlog("  road-pool: sites differ - not applied"); return; }
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
    char v[16]; DWORD n = GetEnvironmentVariableA("I76_FRAME_SPIKES", v, sizeof(v)); int ms, k = 0; BYTE w[5] = { 0xe8 }; LONG rel;
    if (n == 0 || n >= sizeof(v)) return;
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
    {   char f[8]; DWORD k2 = GetEnvironmentVariableA("I76_FLASH_PROBE", f, sizeof(f));
        if (k2 && k2 < sizeof(f) && (f[0] == '1' || f[0] == '2')) {
            char r[32]; DWORD kr = GetEnvironmentVariableA("I76_FLASH_ROWS", r, sizeof(r)); int a, b, c;
            g_fp_on = f[0] - '0';
            if (kr && kr < sizeof(r) && sscanf(r, "%d,%d,%d", &a, &b, &c) == 3 && a > 0 && a < 100 && b > 0 && b < 100 && c > 0 && c < 100) { g_fp_rows[0] = a; g_fp_rows[1] = b; g_fp_rows[2] = c; }
            mlog("  flash-probe: on (level %d: terrain counters%s)", g_fp_on, g_fp_on == 2 ? " + pixel rows" : "");
        }
    }
    mlog("  frame-spikes: on, threshold %lu ms; scene counters %s; census hooks follow (glide-refresh / tex-census lines)",
         (unsigned long)g_fs_ms, g_rp_on ? "via the road-pool flush wrap" : (k == 2 ? "via its own flush wrap" : "NOT sampled (flush sites differ)"));
}

/* GROUND CLUTTER DISTANCE  (I76_CLUTTER_DIST=<metres 120..600>, I76_CLUTTER_RISE=<metres 0..100>; off by default;
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
static void __cdecl clutter_build(BYTE *cam, double ground) {
    float cx = *(float *)0x004f7180, cz = *(float *)0x004f7188, v[3];
    int k, n = 0;
    for (k = 0; k < g_cl_ncand; k++) {
        int i = g_cl_cand[k][0], j = g_cl_cand[k][1];
        float *p = ((float *(__cdecl *)(float *, void *, double, double, double))0x00472d30)
                   (v, cam, cx + 100.0 * i + 50.0, ground, cz + 100.0 * j + 50.0);
        if (p[2] - g_cl_margin > g_cl_dist) continue;
        p[1] = 0.0f;                        /* vertical planes ignored: bushes can sit far below the camera */
        if (((int (__cdecl *)(void *, float *, float))0x00472c10)(cam, p, 81.0f) > 0 && (i || j)) continue;
        g_cl_tab[2 * n] = 100.0f * i; g_cl_tab[2 * n + 1] = 100.0f * j; n++;
    }
    if (n == 0) { g_cl_tab[0] = 0.0f; g_cl_tab[1] = 0.0f; n = 1; }   /* the loop is do-while: one entry minimum */
    g_cl_end = (DWORD)(DWORD_PTR)&g_cl_tab[1] + 8 * n;
    g_cl_cells += n; if ((DWORD)n > g_cl_cells_max) g_cl_cells_max = n;
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
    DWORD used = *(DWORD *)0x006543c0 - *(DWORD *)0x00654398;
    g_cl_tests++;
    if (used > g_cl_limit) { g_cl_capped++; return 1; }
    return ((int (__cdecl *)(void *, float *, float))0x00472c10)(cam, v, r);
}
static void __cdecl clutter_frame_wrap(void *cam) {               /* the calls at 0x401e47 / 0x402111 */
    LARGE_INTEGER a, b; DWORD used;
    QueryPerformanceCounter(&a);
    ((void (__cdecl *)(void *))0x0045c380)(cam);
    QueryPerformanceCounter(&b);
    used = *(DWORD *)0x006543c0 - *(DWORD *)0x00654398;
    if (used > g_cl_pool_max) g_cl_pool_max = used;
    g_cl_ticks += b.QuadPart - a.QuadPart; if (b.QuadPart - a.QuadPart > g_cl_ticks_max) g_cl_ticks_max = b.QuadPart - a.QuadPart;
    if (++g_cl_frames >= 600) {
        if (g_logging && g_cl_qpf)
            mlog("  clutter: 600 frames: %.0f us avg, %.0f us max; cells %.1f avg, %lu max; instances tested %lu/frame; refused (pool) %lu; record pool high water %lu KB",
                 g_cl_ticks * 1e6 / g_cl_qpf / 600.0, g_cl_ticks_max * 1e6 / g_cl_qpf, g_cl_cells / 600.0,
                 (unsigned long)g_cl_cells_max, (unsigned long)(g_cl_tests / 600), (unsigned long)g_cl_capped, (unsigned long)(g_cl_pool_max >> 10));
        g_cl_frames = g_cl_cells = g_cl_cells_max = g_cl_tests = g_cl_capped = g_cl_pool_max = 0; g_cl_ticks = g_cl_ticks_max = 0;
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
    char v[16]; DWORD n = GetEnvironmentVariableA("I76_CLUTTER_DIST", v, sizeof(v));
    float d, rise, five = 5.0f; double rise_old = 5.0, rise_new, stock_z; float z_old, z_new;
    DWORD pool = 0x5a550 * 8, a; int i, j, R, ok = 0;
    LARGE_INTEGER f;
    if (n == 0 || n >= sizeof(v)) return;
    d = (float)atof(v);
    if (d < 120.0f || d > 600.0f) { mlog("  clutter-dist: %s out of range (120..600 m) - not applied", v); return; }
    rise = five * d / 120.0f;
    n = GetEnvironmentVariableA("I76_CLUTTER_RISE", v, sizeof(v));
    if (n && n < sizeof(v)) {
        float r = (float)atof(v);
        if (r < 0.0f || r > 100.0f) mlog("  clutter-dist: I76_CLUTTER_RISE %s out of range (0..100 m) - using %.1f", v, rise);
        else rise = r;
    }
    /* every site checked before anything is written: all or nothing */
    for (i = 0; i < 5; i++) if (memcmp((void *)(DWORD_PTR)sites[i], olds[i], 5) != 0) { mlog("  clutter-dist: site 0x%06lX differs - not applied", (unsigned long)sites[i]); return; }
    if (memcmp((void *)0x0045c507, tab_old, 5) || memcmp((void *)0x0048f9b5, pool_old, 5) ||
        memcmp((void *)0x004be0c8, &rise_old, 8)) { mlog("  clutter-dist: pool/rise/table sites differ - not applied"); return; }
    memcpy(&z_old, (void *)0x004be0d0, 4); stock_z = z_old;
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
    if (!patch_bytes(0x0048f9b5, pool_old, pool_new, 5, "clutter record pool x8")) { mlog("  clutter-dist: record pool not enlarged - not applied"); return; }
    targets[0] = (void *)clutter_build_stub; targets[1] = (void *)clutter_end_stub; targets[2] = (void *)clutter_cull_wrap;
    targets[3] = (void *)clutter_frame_wrap; targets[4] = (void *)clutter_frame_wrap;
    for (i = 0; i < 5; i++) {
        LONG rel = (LONG)((DWORD_PTR)targets[i] - (sites[i] + 5));
        w[0] = 0xe8; memcpy(w + 1, &rel, 4);
        ok += patch_bytes(sites[i], olds[i], w, 5, "clutter call");
    }
    a = (DWORD)(DWORD_PTR)&g_cl_tab[1]; memcpy(tab2_new + 1, &a, 4);
    ok += patch_bytes(0x0045c507, tab_old, tab2_new, 5, "clutter table (later templates)");
    rise_new = rise;
    ok += patch_bytes(0x004be0c8, (const BYTE *)&rise_old, (const BYTE *)&rise_new, 8, "clutter rise limit");
    z_new = d;
    ok += patch_bytes(0x004be0d0, (const BYTE *)&z_old, (const BYTE *)&z_new, 4, "clutter view z limit");
    mlog("  clutter-dist: %s, %d/8 sites; view z 120 -> %.0f m, rise limit 5 -> %.1f m, cells from a %dx%d block culled per frame, record pool %lu KB (instances refused past %lu KB)",
         ok == 8 ? "on" : "PARTIAL", ok, d, rise, 2 * R + 1, 2 * R + 1, (unsigned long)(pool >> 10), (unsigned long)(g_cl_limit >> 10));
}

/* MIRROR RANGE  (I76_MIRROR_FAR=<metres 100..600>; off by default; EXPERIMENT, lab docs/CLUTTER-AND-MIRROR.md)
 * The rear mirror is a software render into a private 256x64 8-bit copy of the cockpit mirror texture (ZMIRI101.MAP),
 * re-uploaded as a Glide texture: its resolution is the texture's, not dgVoodoo's. What a constant can change is its
 * range: mirror_Init 0x445380 creates the mirror camera with far = 100 m (`push 0x42c80000` at 0x44553c; fov 30 deg,
 * camera_Create 0x472220 clamps far to 100..100000), so nothing past 100 m shows behind you. */
static void apply_mirror_far(void) {
    static const BYTE old[5] = { 0x68, 0x00, 0x00, 0xc8, 0x42 };
    BYTE want[5] = { 0x68 }; char v[16]; DWORD n = GetEnvironmentVariableA("I76_MIRROR_FAR", v, sizeof(v)); float f;
    if (n == 0 || n >= sizeof(v)) return;
    f = (float)atof(v);
    if (f < 100.0f || f > 600.0f) { mlog("  mirror-far: %s out of range (100..600 m) - not applied", v); return; }
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
    return ((float *(__cdecl *)(float *, float *, float *, DWORD *, float *))0x004260d0)(cam, v, n, tex, flags);
}
static void __cdecl hud_gauge_wrap(DWORD a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g) {
    g_hud_side_anchor = 1;
    ((void (__cdecl *)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD))0x0045b450)(a, b, c, d, e, f, g);
    g_hud_side_anchor = 0;
}
static void apply_hud_squeeze(double k) {
    static const struct { DWORD site, target; void *wrap; const char *what; } cs[2] = {
        { 0x0045b87a, 0x004260d0, (void *)hud_quad_wrap,  "HUD sprite quad draw" },
        { 0x0045c0d1, 0x0045b450, (void *)hud_gauge_wrap, "HUD gauge loop sprite call" },
    };
    char v[8]; DWORD m = GetEnvironmentVariableA("I76_HUD_SQUEEZE", v, sizeof(v)); int i, n = 0;
    if (m && m < sizeof(v) && v[0] == '0') { mlog("  hud-squeeze: off (I76_HUD_SQUEEZE=0): HUD sprites stay stretched x%.2f", k); return; }
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
        LONG rel; memcpy(&rel, (const void *)(0x0045b87a + 1), 4);
        mlog("  hud-squeeze: %d/2 sites, quad call -> %s; HUD sprite quads x 1/%.3f (brackets, reticles, zcbh sprite about their centres; gauges about their screen side)",
             n, (DWORD_PTR)(0x0045b87a + 5 + rel) == (DWORD_PTR)hud_quad_wrap ? "wrapper" : "STOCK", k);
    }
}

static void apply_aspect(void) {
    static const DWORD push_sites[17] = { 0x405a00, 0x4069e3, 0x406eb8, 0x406faf, 0x4070d5, 0x4079f6, 0x407f46,
        0x4080cb, 0x4083f6, 0x408546, 0x408696, 0x408816, 0x4089a0, 0x408bf0, 0x4090d0, 0x409316, 0x4094e7 };
    char v[24], *sep; DWORD n = GetEnvironmentVariableA("I76_ASPECT", v, sizeof(v));
    double D, k; float three = 3.0f, cst, f90, w90, wcock, f120, w120, clamp0, clamp1; int i, ok = 0;
    if (n == 0 || n >= sizeof(v)) return;
    sep = strchr(v, ':'); if (!sep) sep = strchr(v, 'x'); if (!sep) sep = strchr(v, 'X');
    D = sep ? atof(v) / atof(sep + 1) : atof(v);
    if (!(D >= 1.34 && D <= 3.6)) { mlog("  aspect: %s out of range (1.34..3.6) - not applied", v); return; }
    k = 0.75 * D;
    { static const DWORD f90_bits = 0x3fc90fda; memcpy(&f90, &f90_bits, 4); }   /* the exe's pi/2 is one ulp below (float)(pi/2) */
    memcpy(&f120, (const void *)0x4075a7, 4);
    memcpy(&clamp0, (const void *)0x4be5ac, 4);
    cst = (float)(4.0 / D);
    w90 = (float)(2.0 * atan(k * tan(f90 / 2.0)));
    w120 = (float)(2.0 * atan(k * tan(f120 / 2.0)));
    clamp1 = w120 + 0.08f > clamp0 ? w120 + 0.08f : clamp0;
    ok += patch_bytes(0x4bc510, (const BYTE *)&three, (const BYTE *)&cst, 4, "aspect constant");
    /* Cockpit view (F1 / V, level-start reset, binocular toggle back: sites 1..4): the cockpit mesh was modelled for
     * 90 deg and its right side ends inside the full Hor+ view (owner, 2026-10-03). I76_ASPECT_COCKPIT_FOV=<deg>
     * (default 0 = full Hor+; e.g. 105 narrows it; 90 = stock width) gives those four sites their own horizontal fov. */
    {
        char c[16]; DWORD m = GetEnvironmentVariableA("I76_ASPECT_COCKPIT_FOV", c, sizeof(c)); double deg = 0.0;
        if (m && m < sizeof(c)) deg = atof(c);
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
    char v[24], *sep; DWORD n = GetEnvironmentVariableA("I76_SW_RES", v, sizeof(v)); int ok = 0;
    if (n == 0 || n >= sizeof(v) || v[0] == '0') return;
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
    if (GetEnvironmentVariableA("I76_MULTI_INSTANCE", NULL, 0) == 0) return;
    if (patch_bytes(0x402caf, expect, want, 2, "multi-instance"))   /* patch_bytes logs only a mismatch */
        mlog("  multi-instance: single-instance check skipped (0x402caf je -> jmp; read back %s)",
             *(const BYTE *)0x402caf == 0xeb ? "ok" : "FAILED");
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
    char v[8]; DWORD k = GetEnvironmentVariableA("I76_NO_MINIMIZE", v, sizeof(v));
    if (k == 0 || k >= sizeof(v) || v[0] == '0') return;
    if (patch_bytes(0x404acc, expect, want, 9, "no-minimize"))
        mlog("  no-minimize: WM_ACTIVATEAPP 0 no longer minimises the window (0x404acc push 6 -> push %d; read back %s)",
             *(const BYTE *)0x404acd, *(const BYTE *)0x404acd == 0x08 ? "ok" : "FAILED");
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
    return rc;
}
static void apply_joy_routing(HMODULE exe) {
    char v[128]; DWORD n; int i, any = 0; char *p;
    for (i = 0; i < 16; i++) { g_joy_map[i] = i; g_joy_synth[i] = -1; g_joy_lastrc[0][i] = g_joy_lastrc[1][i] = -1; }
    n = GetEnvironmentVariableA("I76_JOY_MAP", v, sizeof(v));
    if (n && n < sizeof(v)) for (p = v; *p; ) {
        int a = atoi(p), b; char *eq = strchr(p, '='); if (!eq) break; b = atoi(eq + 1);
        if (a >= 0 && a < 16 && b >= 0 && b < 16) { g_joy_map[a] = b; any = 1; mlog("  joy-map: engine id %d (joystick%d) -> winmm id %d", a, a + 1, b); }
        p = strchr(eq, ','); if (!p) break; p++;
    }
    n = GetEnvironmentVariableA("I76_JOY_SYNTH", v, sizeof(v));
    if (n && n < sizeof(v)) for (p = v; *p; ) {
        int a = atoi(p), x = 0; char *c = p; while (*c && *c != ',' && *c != ':') c++;
        if (*c == ':') x = atoi(c + 1);
        if (a >= 0 && a < 16) { g_joy_synth[a] = x < 0 ? 0 : (x > 65535 ? 65535 : x); any = 1; mlog("  joy-synth: winmm id %d is a synthetic pad, X = %d (TEST ONLY)", a, g_joy_synth[a]); }
        p = strchr(p, ','); if (!p) break; p++;
    }
    if (!any) return;
    real_joyGetDevCapsA = (joyCapsFn)patch_iat(exe, "WINMM.dll", "joyGetDevCapsA", hook_joyGetDevCapsA);
    real_joyGetPosEx    = (joyPosFn)patch_iat(exe, "WINMM.dll", "joyGetPosEx", hook_joyGetPosEx);
    mlog("  joy-routing: IAT joyGetDevCapsA old=%p joyGetPosEx old=%p%s", (void *)real_joyGetDevCapsA, (void *)real_joyGetPosEx,
         (real_joyGetDevCapsA && real_joyGetPosEx) ? "" : " - NOT HOOKED (no WINMM import: i76fix exe?)");
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, g_dir, sizeof(g_dir));
        char *s = strrchr(g_dir, '\\'); if (s) *s = 0;          /* -> game folder */
        g_logging = GetEnvironmentVariableA("I76MUSIC_LOG", NULL, 0) > 0;
        load_orig();   /* must happen before the game calls any forwarded export */
        apply_crash_log();        /* always on: fault address + registers to the log */
        /* WORKING DIRECTORY (always on; I76_CWD_FIX=0 disables). The exe resolves its data relative to the current
         * directory: startup_IsMinimum 0x4b2220 looks for "miss8" there and, failing, treats the mission data as a CD
         * container and WinMain raises "Please insert CD 2"; the next cwd-relative open then fails outright ("unable
         * to find required files ... check your working directory"). Both reproduced 2026-10-02 by launching the
         * pristine exe from C:\Windows. Launchers set the cwd; a bare double-click or Start-Process does not. The DLL
         * knows the game folder (it lives there), so make the cwd right before the exe's entry point runs. */
        {
            char v[8], cwd[MAX_PATH]; DWORD k = GetEnvironmentVariableA("I76_CWD_FIX", v, sizeof(v));
            if (!(k && k < sizeof(v) && v[0] == '0')) {
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
        apply_detail_distance();  /* experiment: I76_TERRAIN_TEX=<1..16>, I76_OBJECT_LOD=<1..16> */
        apply_shadow_road_dist(); /* experiment: I76_SHADOW_DIST, I76_ROAD_TEX, I76_ROAD_DIST */
        apply_road_pool();        /* with I76_ROAD_DIST > 450 or I76_FAR_CLIP: span-node pool x16 + end guard (I76_ROAD_POOL=0 off) */
        apply_frame_spikes();     /* opt-in: I76_FRAME_SPIKES=<ms> (after apply_road_pool: shares its flush wrap; before apply_glide_refresh) */
        apply_clutter_dist();     /* experiment: I76_CLUTTER_DIST=<120..600 m> (+ I76_CLUTTER_RISE) */
        apply_mirror_far();       /* experiment: I76_MIRROR_FAR=<100..600 m> */
        apply_cam_ground_fix();   /* opt-in: I76_CAM_GROUND_FIX=1 (terrain kept when the eye dips under the ground) */
        apply_aspect();           /* experiment: I76_ASPECT=<display aspect> (Hor+ widescreen, stage A) */
        apply_sw_res();           /* experiment: I76_SW_RES=<W>x<H> or 1 (software renderer above 1024x768) */
        apply_hires_clock();      /* opt-in: I76_HIRES_CLOCK=1 */
        apply_engine_dt_fix();    /* opt-in: I76_ENGINE_DT_FIX=1 */
        apply_frame_cap();        /* opt-in: I76_FPS_CAP=n */
        apply_fps_log();          /* opt-in: I76_FPS_LOG=<seconds> */
        apply_volume_test();      /* test knob: I76_VOLUME_TEST=<level>,<frame> */
        apply_phys_rate();        /* experiment: I76_PHYS_RATE=n */
        apply_fixed_step();       /* opt-in: I76_FIXED_STEP=n */
        apply_input_latch();      /* opt-in: I76_INPUT_LATCH=1 (after apply_fixed_step: ignition / lights keys survive step-less frames) */
        apply_coll_window();      /* opt-in: I76_COLL_WINDOW=1 (after apply_fixed_step: needs g_fixed_step) */
        apply_coll_dedupe();      /* with I76_FIXED_STEP: collision sound + damage once per physics step (I76_COLL_DEDUPE=0 counts only) */
        apply_far_engine_dt();    /* opt-in: I76_FAR_ENGINE_DT=1 (after apply_engine_dt_fix: needs its site) */
        apply_framerate_fixes();  /* opt-in: I76_FRAMERATE_FIXES=1 */
        apply_hazard_fix();       /* with I76_FRAMERATE_FIXES: stationary hazards (oil slick, fire patch, ...) step on the 20 Hz grid */
        apply_perframe_fixes();   /* with I76_FRAMERATE_FIXES: radar missile turn, WMISS click, AI skid + horn rolls */
        apply_ai_fixes();         /* opt-in: I76_AI_FIXES=1 (after apply_framerate_fixes: the dodge hold needs the 20 Hz grid) */
        apply_ai_backaway_grid(); /* opt-in: I76_AI_BACKAWAY_GRID=1 (back_away ring indexed by sim time x 20, not frames) */
        apply_coop_damage();      /* opt-in: I76_COOP_DAMAGE=<factor> (humans' weapon damage in network games) */
        apply_mirror_rate();      /* opt-in: I76_MIRROR_RATE=1 (after apply_framerate_fixes: grid count + cloud step) */
        apply_render_interp();    /* opt-in: I76_RENDER_INTERP=1 (after apply_fixed_step) */
        apply_fix_health_pct();   /* opt-in: I76_FIX_HEALTH_PCT=1 (stock bug fix) */
        apply_fix_label_table();  /* opt-in: I76_FIX_LABEL_TABLE=1 (stock bug fix) */
        apply_far_clip();         /* opt-in: I76_FAR_CLIP=<metres> (+ render pools x16) */
        apply_telemetry();        /* opt-in: I76_TELEMETRY=<port> (after apply_fixed_step: reads g_fixed_step) */
        apply_trainer();          /* always on (I76_TRAINER=0 disables): Local\I76Trainer control block */
        apply_glide_refresh();    /* opt-in: I76_GLIDE_REFRESH=<hz> (hooks LoadLibraryA; the exe's IAT is used below too) */
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
