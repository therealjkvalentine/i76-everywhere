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

static void mlog(const char *fmt, ...) {
    if (!g_logging) return;
    char path[MAX_PATH]; _snprintf(path, sizeof(path), "%s\\mciproxy.log", g_dir);
    FILE *f = fopen(path, "a"); if (!f) return;
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f); fclose(f);
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

/* --- aux hooks ------------------------------------------------------------ */
/* mci_str is defined below; hook_auxSetVolume needs it to push the volume onto the
 * playing alias. Forward-declared rather than moving these hooks further down, so
 * the aux code stays beside the comment explaining why it exists. */
static void mci_str(const char *cmd);

/* Claim one CD-audio aux device only when the system genuinely has none, so a
 * machine WITH real aux hardware keeps its own behaviour untouched. */
static UINT WINAPI hook_auxGetNumDevs(void) {
    UINT n;
    ensure_real();
    n = real_auxGetNumDevs ? real_auxGetNumDevs() : 0;
    mlog("auxGetNumDevs called (real=%u) -> %u", n, n ? n : 1);
    if (n == 0) return 1;
    return n;
}

static MMRESULT WINAPI hook_auxGetDevCapsA(UINT_PTR id, LPAUXCAPSA caps, UINT size) {
    UINT n;
    ensure_real();
    n = real_auxGetNumDevs ? real_auxGetNumDevs() : 0;
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
    n = real_auxGetNumDevs ? real_auxGetNumDevs() : 0;
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
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, trk);
    if (GetFileAttributesA(mp3) == INVALID_FILE_ATTRIBUTES) return 0;
    ensure_real();
    if (!real_mciSendStringA) return 0;
    _snprintf(cmd, sizeof(cmd), "open \"%s\" type mpegvideo alias i76len", mp3);
    if (real_mciSendStringA(cmd, NULL, 0, NULL) != 0) return 0;
    ret[0] = 0;
    if (real_mciSendStringA("status i76len length", ret, sizeof(ret), NULL) == 0)
        g_lenCache[trk] = (DWORD)strtoul(ret, NULL, 10);
    real_mciSendStringA("close i76len", NULL, 0, NULL);
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
    if (real_mciSendStringA(cmd, ret, sizeof(ret), NULL) != 0) return 0;
    return (DWORD)strtoul(ret, NULL, 10);
}

static int playing_now(void) {
    char cmd[64], ret[64];
    if (!g_open) return 0;
    ensure_real();
    if (!real_mciSendStringA) return 0;
    _snprintf(cmd, sizeof(cmd), "status %s mode", g_alias);
    ret[0] = 0;
    if (real_mciSendStringA(cmd, ret, sizeof(ret), NULL) != 0) return 0;
    if (strstr(ret, "playing") != NULL) return 1;
    if (g_playingTrack && g_playingTrack >= g_runStart && g_playingTrack < g_runEnd) {   /* song ended: next in the run */
        int next = g_playingTrack + 1;
        mlog("  run %d..%d: track %d ended -> %d", g_runStart, g_runEnd, g_playingTrack, next);
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
    MCIERROR e = real_mciSendStringA ? real_mciSendStringA(cmd, NULL, 0, NULL) : 1;
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
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, trk);
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
    if (real_mciSendStringA("status i76cd mode", ret, sizeof(ret), NULL) != 0) return 0;
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
    if (track == g_runStart && g_playingTrack > g_runStart && g_playingTrack <= g_runEnd && still_playing()) {
        mlog("  PLAY track %d re-issued while its run is on track %d - kept", track, g_playingTrack);
        return 0;
    }
    if (track == g_playingTrack && still_playing()) {
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
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, track);
    stop_track();
    _snprintf(cmd, sizeof(cmd), "open \"%s\" type mpegvideo alias %s", mp3, g_alias); mci_str(cmd);
    g_open = 1;
    _snprintf(cmd, sizeof(cmd), "setaudio %s volume to %lu", g_alias, (unsigned long)g_volume); mci_str(cmd);   /* the exe sets the
                                                                   slider once (0x423d50), not per track: re-apply it (M2) */
    _snprintf(cmd, sizeof(cmd), "play %s", g_alias); mci_str(cmd);
    g_playingTrack = track;
    mlog("  PLAY track %d", track);
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
        {
            int to = track;
            if (p && (flags & MCI_TO)) { DWORD t = (DWORD)p->dwTo; to = (t & 0xFF) ? (int)(t & 0xFF) : (int)t; }
            if (to < track) to = track;
            if (to > LAST_TRACK) to = LAST_TRACK;
            g_runStart = track; g_runEnd = to;
            mlog("MCI_PLAY flags=0x%lX from=%ld to=%ld -> run %d..%d",
                 (unsigned long)flags, p ? (long)p->dwFrom : -1, p ? (long)p->dwTo : -1, track, to);
        }
        g_curTrack = track;
        return play_track(track);
    }
    case MCI_STOP: case MCI_PAUSE: case MCI_CLOSE: g_runStart = g_runEnd = 0; stop_track(); return 0;
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
static float __cdecl engine_substep_dt(void) {
    /* I76_FIXED_STEP: stock at 20 fps hands the engine the whole frame's dt (~50 ms) on every substep; keep that */
    if (g_fixed_step > 0.0f) return 0.05f;
    float sim_dt = *(volatile float *)0x004fe420;          /* simclock_sim_dt */
    float rate = 1.0f / 0.05f;                              /* stepper rate set by entity_InitVehicle */
    int count = (int)(sim_dt * rate) + 1;                   /* truncation, as _ftol at 0x49cc2d */
    if (count > 20) count = 20;
    return 2.0f * (sim_dt / (float)count);
}

static void apply_engine_dt_fix(void) {
    static const BYTE old_call[5] = { 0xE8, 0x78, 0x25, 0x03, 0x00 };   /* call 0x49c8b0 (simclock_GetDt) at 0x46a333 */
    BYTE new_call[5] = { 0xE8, 0, 0, 0, 0 };
    LONG rel = (LONG)((DWORD_PTR)engine_substep_dt - (0x0046a333 + 5));
    if (GetEnvironmentVariableA("I76_ENGINE_DT_FIX", NULL, 0) == 0) return;
    memcpy(new_call + 1, &rel, 4);
    mlog("  engine-dt-fix: %d/1 call site repointed (0x46a333 -> %p)",
         patch_bytes(0x0046a333, old_call, new_call, 5, "engine update simclock_GetDt call"), (void *)engine_substep_dt);
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
static void radar_ping_flush(void);
static DWORD g_frame;                                        /* proxy frame counter, advanced by the frame hook */
static int g_tel_on;                                         /* I76_TELEMETRY: publish the completed frame (below, with the telemetry export) */
static void tel_frame(void);
static void __cdecl frame_cap_then_clock(void) {
    LARGE_INTEGER now;
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
    g_frame++;
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
        g_tick20 = g_acc20 >= 0.049f;                        /* 1 ms tolerance: n x dt lands a hair under 0.05 */
        if (g_tick20) { g_acc20 -= 0.05f; if (g_acc20 > 0.05f || g_acc20 < -0.01f) g_acc20 = 0.0f; g_tick20_n++; radar_ping_flush(); }
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

static void apply_frame_cap(void) {
    static const BYTE old_call[5] = { 0xE8, 0x63, 0x8F, 0x09, 0x00 };   /* call 0x49c920 at 0x4039b8 */
    BYTE new_call[5] = { 0xE8, 0, 0, 0, 0 };
    char v[16]; int fps;
    LONG rel = (LONG)((DWORD_PTR)frame_cap_then_clock - (0x004039b8 + 5));
    DWORD n = GetEnvironmentVariableA("I76_FPS_CAP", v, sizeof(v));
    if (n == 0 || n >= sizeof(v) || (fps = atoi(v)) < 5 || fps > 1000) return;
    if (!g_qpf.QuadPart) QueryPerformanceFrequency(&g_qpf);
    g_cap_period.QuadPart = g_qpf.QuadPart / fps;
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
 * STOCK BUG: HEALTH PERCENT  (I76_FIX_HEALTH_PCT=1; off by default - changes stock play)
 * ===========================================================================
 * object_HealthFraction 0x40b450 returns a vehicle's health in percent: 28 + 72 x (worst armour/chassis side ratio)
 * while engine, suspension and brakes are all >= 99.99%. As soon as one of them is below that, it returns the worst
 * component ratio UNSCALED (0..1): the switch at 0x40b6e3 (table 0x40b7b8, all four entries 0x40b6f0) jumps
 * straight to the clamp. A 99% engine therefore reads as 0.99 "percent". Confirmed live (i76-map damage.md: a 99%
 * engine starts the heaviest damage smoke). Callers that see it: damage smoke, entity_DamageComponent's < 33 test
 * (handgun hits go to component 6), fsm_HpLesser (script hpLesser), ai_ShouldFleeWhenHurt (AI flees below
 * 30 + 17 x skill), the target-bracket readout and the network state packers.
 * The fix repoints the four table entries at a stub that multiplies by 100 (the constant at 0x4bc620) and continues
 * at 0x40b6f0. Missions may have been tuned around the stock behaviour, so this is opt-in. */
static DWORD g_hf_cont = 0x0040b6f0;
static __declspec(naked) void hf_scale_stub(void) {
    __asm {
        fmul dword ptr ds:[0x004bc620]
        jmp dword ptr [g_hf_cont]
    }
}
static void apply_fix_health_pct(void) {
    static const BYTE old_tab[16] = { 0xF0, 0xB6, 0x40, 0x00, 0xF0, 0xB6, 0x40, 0x00, 0xF0, 0xB6, 0x40, 0x00, 0xF0, 0xB6, 0x40, 0x00 };
    static const BYTE old_jmp[7] = { 0xFF, 0x24, 0x9D, 0xB8, 0xB7, 0x40, 0x00 };   /* jmp [ebx*4 + 0x40b7b8] at 0x40b6e3 */
    static const BYTE k100[4] = { 0x00, 0x00, 0xC8, 0x42 };                          /* 100.0f at 0x4bc620 */
    BYTE new_tab[16]; DWORD a = (DWORD)(DWORD_PTR)hf_scale_stub; int i;
    if (GetEnvironmentVariableA("I76_FIX_HEALTH_PCT", NULL, 0) == 0) return;
    if (memcmp((void *)0x0040b6e3, old_jmp, 7) != 0 || memcmp((void *)0x004bc620, k100, 4) != 0) {
        mlog("  fix-health-pct: bytes differ at 0x40b6e3 / 0x4bc620 - not applied"); return;
    }
    for (i = 0; i < 4; i++) memcpy(new_tab + 4 * i, &a, 4);
    mlog("  fix-health-pct: %s", patch_bytes(0x0040b7b8, old_tab, new_tab, 16, "health percent switch table") ? "on (component branch x100)" : "NOT applied");
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
                DWORD ping_req, ping_play, ping_frames, flame_hits, flame_dmg, aifire_calls, aifire_yes, tick20_n; } g_idbg;   /* every frame, for samplers that miss some */

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
 * state (docs/FFB-DATA-AUDIT.md section 4.2, row 8 of section 6). Once per
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
            BYTE *inst = *(BYTE **)(rec + 0x58 + row * 0x58 + 0x50), *root;
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

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, g_dir, sizeof(g_dir));
        char *s = strrchr(g_dir, '\\'); if (s) *s = 0;          /* -> game folder */
        g_logging = GetEnvironmentVariableA("I76MUSIC_LOG", NULL, 0) > 0;
        load_orig();   /* must happen before the game calls any forwarded export */
        apply_mission_launch();   /* before the exe's entry point, so before the buffer is read */
        apply_hires_clock();      /* opt-in: I76_HIRES_CLOCK=1 */
        apply_engine_dt_fix();    /* opt-in: I76_ENGINE_DT_FIX=1 */
        apply_frame_cap();        /* opt-in: I76_FPS_CAP=n */
        apply_phys_rate();        /* experiment: I76_PHYS_RATE=n */
        apply_fixed_step();       /* opt-in: I76_FIXED_STEP=n */
        apply_framerate_fixes();  /* opt-in: I76_FRAMERATE_FIXES=1 */
        apply_render_interp();    /* opt-in: I76_RENDER_INTERP=1 (after apply_fixed_step) */
        apply_fix_health_pct();   /* opt-in: I76_FIX_HEALTH_PCT=1 (stock bug fix) */
        apply_fix_label_table();  /* opt-in: I76_FIX_LABEL_TABLE=1 (stock bug fix) */
        apply_telemetry();        /* opt-in: I76_TELEMETRY=<port> (after apply_fixed_step: reads g_fixed_step) */
        /* i76.exe's winmm IAT is already snapped by now; redirect the mci slot. */
        HMODULE exe = GetModuleHandleA(NULL);
        /* Point the game's DATA import at the ORIGINAL's variable, not our copy -
         * see the note above redirect_global_import. Must run after load_orig. */
        mlog("  StrLookup_Global_Object import repointed: slot was %p, now -> %p",
             redirect_global_import(exe), (void *)p_GlobalObj);
        {
        void *old = patch_iat(exe, "WINMM.dll", "mciSendCommandA", hook_mciSendCommandA);
        mlog("--- strlkproxy: IAT patch mciSendCommandA old=%p new=%p ---", old, (void *)hook_mciSendCommandA);
        /* The aux trio is what actually gets the engine to TRY. Without these the
         * mci hook above was installed and never called even once - see the note
         * beside the aux typedefs. */
        mlog("  aux patches: auxGetNumDevs=%p auxGetDevCapsA=%p auxSetVolume=%p",
             patch_iat(exe, "WINMM.dll", "auxGetNumDevs",  hook_auxGetNumDevs),
             patch_iat(exe, "WINMM.dll", "auxGetDevCapsA", hook_auxGetDevCapsA),
             patch_iat(exe, "WINMM.dll", "auxSetVolume",   hook_auxSetVolume));
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        stop_track();
        g_tel_on = 0;
        if (g_tel_shm) { UnmapViewOfFile(g_tel_shm); g_tel_shm = 0; }
        if (g_tel_map) { CloseHandle(g_tel_map); g_tel_map = 0; }
    }
    return TRUE;
}
