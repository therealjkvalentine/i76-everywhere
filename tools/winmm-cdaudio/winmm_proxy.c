/*
 * winmm_proxy.c - pretend Interstate '76 has a CD-audio drive.
 *
 * ===========================================================================
 * WHY
 * ===========================================================================
 * I'76 plays its soundtrack as Red Book CD audio through MCI. On a machine with
 * no optical drive there is no `cdaudio` device to open, so the engine's music
 * init fails and you get silence. GOG ships the tracks as music\2.mp3..17.mp3
 * but never wires them into the game. See docs/MUSIC.md.
 *
 * This DLL sits in the game folder and is loaded INSTEAD of the system winmm,
 * because the application directory is searched first and winmm is not a
 * KnownDLL (both verified on this machine). It forwards everything to the real
 * winmm except the MCI calls, where it emulates a CD-audio device backed by
 * those MP3 files.
 *
 * The game therefore drives its own music - it asks for the track it wants,
 * when it wants it - so this is SYNCHRONISED, unlike playing the MP3s
 * alongside the game (tools/i76-music.ps1, the stopgap this replaces).
 *
 * ===========================================================================
 * WHAT THE GAME ACTUALLY IMPORTS  (parsed from i76.exe's import table)
 * ===========================================================================
 *   mciSendCommandA  mciGetErrorStringA          <- music. Intercepted.
 *   joyGetDevCapsA   joyGetNumDevs  joyGetPosEx  <- INPUT. Forwarded verbatim.
 *   auxGetDevCapsA   auxGetNumDevs  auxSetVolume <- CD volume. Intercepted.
 *   timeGetTime                                  <- Forwarded verbatim.
 *
 * Nine functions, so this proxy is small. It matters that joy* is among them:
 * the 1997 engine reads the steering wheel through winmm, so a proxy that got
 * those wrong would break input. They are passed straight through, untouched.
 *
 * ===========================================================================
 * THE ONE THING THAT WOULD BREAK EVERYTHING
 * ===========================================================================
 * Never LoadLibrary("winmm.dll") by name from here - the application directory
 * is searched first, so we would load OURSELVES and recurse until the stack
 * dies. The real DLL is always opened by ABSOLUTE PATH from GetSystemDirectoryA
 * (which, for a 32-bit process on 64-bit Windows, resolves to SysWOW64).
 *
 * ===========================================================================
 * HOW PLAYBACK WORKS
 * ===========================================================================
 * We do not decode MP3. We call the REAL winmm's mciSendStringA and ask it to
 * play the file with its `mpegvideo` device - verified working on this machine
 * (open 2.mp3 -> rc 0, length 158018 ms). So this translates CD-audio
 * semantics into ordinary MCI file playback, and adds no audio code at all.
 *
 * ===========================================================================
 * LOGGING
 * ===========================================================================
 * Set I76_CDAUDIO_LOG=1 to append every intercepted call to
 * winmm-cdaudio.log beside the DLL. This exists because the emulation is
 * written against what the engine is EXPECTED to ask for; the log is how we
 * find out what it actually asks for. Off by default (it is a hot path).
 *
 * Build: tools\winmm-cdaudio\build.ps1
 */

#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdlib.h>

#define MAX_TRACKS 100

static HMODULE g_real = NULL;
static CRITICAL_SECTION g_lock;
static int g_logging = 0;
static char g_dir[MAX_PATH];        /* folder this DLL lives in */
static char g_logpath[MAX_PATH];

/* ---- real winmm entry points we need -------------------------------------- */
typedef MCIERROR (WINAPI *pfn_mciSendStringA)(LPCSTR, LPSTR, UINT, HWND);
typedef MCIERROR (WINAPI *pfn_mciSendCommandA)(MCIDEVICEID, UINT, DWORD_PTR, DWORD_PTR);
typedef BOOL     (WINAPI *pfn_mciGetErrorStringA)(MCIERROR, LPSTR, UINT);
typedef MMRESULT (WINAPI *pfn_joyGetDevCapsA)(UINT_PTR, LPJOYCAPSA, UINT);
typedef UINT     (WINAPI *pfn_joyGetNumDevs)(void);
typedef MMRESULT (WINAPI *pfn_joyGetPosEx)(UINT, LPJOYINFOEX);
typedef MMRESULT (WINAPI *pfn_auxGetDevCapsA)(UINT_PTR, LPAUXCAPSA, UINT);
typedef UINT     (WINAPI *pfn_auxGetNumDevs)(void);
typedef MMRESULT (WINAPI *pfn_auxSetVolume)(UINT, DWORD);
typedef DWORD    (WINAPI *pfn_timeGetTime)(void);

static pfn_mciSendStringA     real_mciSendStringA;
static pfn_mciSendCommandA    real_mciSendCommandA;
static pfn_mciGetErrorStringA real_mciGetErrorStringA;
static pfn_joyGetDevCapsA     real_joyGetDevCapsA;
static pfn_joyGetNumDevs      real_joyGetNumDevs;
static pfn_joyGetPosEx        real_joyGetPosEx;
static pfn_auxGetDevCapsA     real_auxGetDevCapsA;
static pfn_auxGetNumDevs      real_auxGetNumDevs;
static pfn_auxSetVolume       real_auxSetVolume;
static pfn_timeGetTime        real_timeGetTime;

/* ---- our fake CD ---------------------------------------------------------- */
/* Track N is music\N.mp3. The original disc had track 1 as DATA and audio from
 * track 2, which is exactly how GOG named the files, so the numbering lines up
 * with no translation. */
static struct {
    int   present;          /* file exists */
    DWORD ms;               /* length, milliseconds (queried once, cached) */
    char  path[MAX_PATH];
} g_track[MAX_TRACKS];

static int  g_firstTrack = 0, g_lastTrack = 0, g_numTracks = 0;
static MCIDEVICEID g_fakeId = 0xCDA0;   /* the id we hand back for "cdaudio" */
static int  g_open = 0;
static DWORD g_timeFormat = MCI_FORMAT_MSF;
static int  g_curTrack = 0;
static int  g_playing = 0, g_paused = 0;
static DWORD g_volume = 1000;
static char g_alias[32] = "i76cda";

static void logf(const char *fmt, ...)
{
    FILE *f;
    va_list ap;
    if (!g_logging) return;
    f = fopen(g_logpath, "a");
    if (!f) return;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}

/* ---- scan music\ and cache track lengths --------------------------------- */
static DWORD query_length_ms(const char *path)
{
    char cmd[MAX_PATH + 128], ret[128];
    DWORD ms = 0;
    /* A private alias so this never collides with playback in progress. */
    sprintf(cmd, "open \"%s\" type mpegvideo alias i76len", path);
    if (real_mciSendStringA(cmd, NULL, 0, NULL) != 0) return 0;
    ret[0] = 0;
    if (real_mciSendStringA("status i76len length", ret, sizeof(ret), NULL) == 0)
        ms = (DWORD)strtoul(ret, NULL, 10);
    real_mciSendStringA("close i76len", NULL, 0, NULL);
    return ms;
}

static void scan_tracks(void)
{
    int i;
    char path[MAX_PATH];
    g_numTracks = 0; g_firstTrack = 0; g_lastTrack = 0;
    for (i = 1; i < MAX_TRACKS; i++) {
        sprintf(path, "%s\\music\\%d.mp3", g_dir, i);
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) continue;
        g_track[i].present = 1;
        strcpy(g_track[i].path, path);
        g_track[i].ms = query_length_ms(path);
        if (!g_firstTrack) g_firstTrack = i;
        g_lastTrack = i;
        g_numTracks++;
        logf("  track %d: %s (%lu ms)", i, path, (unsigned long)g_track[i].ms);
    }
    logf("scan_tracks: %d tracks, first %d, last %d", g_numTracks, g_firstTrack, g_lastTrack);
}

/* ---- MSF / TMSF helpers -------------------------------------------------- */
static DWORD ms_to_msf(DWORD ms)
{
    DWORD m = ms / 60000, s = (ms / 1000) % 60, f = (ms % 1000) * 75 / 1000;
    return MCI_MAKE_MSF(m, s, f);
}
static DWORD ms_to_tmsf(int track, DWORD ms)
{
    DWORD m = ms / 60000, s = (ms / 1000) % 60, f = (ms % 1000) * 75 / 1000;
    return MCI_MAKE_TMSF(track, m, s, f);
}
/* Total disc length: audio tracks laid end to end. */
static DWORD disc_length_ms(void)
{
    int i; DWORD t = 0;
    for (i = 1; i < MAX_TRACKS; i++) if (g_track[i].present) t += g_track[i].ms;
    return t;
}

/* ---- playback ------------------------------------------------------------ */
static void stop_playback(void)
{
    char cmd[64];
    sprintf(cmd, "close %s", g_alias);
    real_mciSendStringA(cmd, NULL, 0, NULL);
    g_playing = 0; g_paused = 0;
}

static MCIERROR start_track(int track)
{
    char cmd[MAX_PATH + 128];
    MCIERROR rc;
    if (track < 1 || track >= MAX_TRACKS || !g_track[track].present) {
        logf("start_track %d: no such track", track);
        return MCIERR_OUTOFRANGE;
    }
    stop_playback();
    sprintf(cmd, "open \"%s\" type mpegvideo alias %s", g_track[track].path, g_alias);
    rc = real_mciSendStringA(cmd, NULL, 0, NULL);
    if (rc) { logf("start_track %d: open failed rc %lu", track, (unsigned long)rc); return rc; }
    sprintf(cmd, "setaudio %s volume to %lu", g_alias, (unsigned long)g_volume);
    real_mciSendStringA(cmd, NULL, 0, NULL);
    sprintf(cmd, "play %s", g_alias);
    rc = real_mciSendStringA(cmd, NULL, 0, NULL);
    if (rc) { logf("start_track %d: play failed rc %lu", track, (unsigned long)rc); return rc; }
    g_curTrack = track; g_playing = 1; g_paused = 0;
    logf("start_track %d: playing", track);
    return 0;
}

/* Is the file still playing? Asked of the real MCI rather than tracked by a
 * timer, so a track that ends is reported as stopped and the game can decide
 * what to do next - which is how a real CD player behaves. */
static int is_playing(void)
{
    char cmd[64], ret[64];
    if (!g_playing) return 0;
    sprintf(cmd, "status %s mode", g_alias);
    ret[0] = 0;
    if (real_mciSendStringA(cmd, ret, sizeof(ret), NULL) != 0) return 0;
    return (strstr(ret, "playing") != NULL);
}

static DWORD position_ms(void)
{
    char cmd[64], ret[64];
    sprintf(cmd, "status %s position", g_alias);
    ret[0] = 0;
    if (real_mciSendStringA(cmd, ret, sizeof(ret), NULL) != 0) return 0;
    return (DWORD)strtoul(ret, NULL, 10);
}

/* ---- the interception --------------------------------------------------- */
static int is_cdaudio_open(UINT flags, MCI_OPEN_PARMSA *p)
{
    if (!p) return 0;
    if (flags & MCI_OPEN_TYPE) {
        if (flags & MCI_OPEN_TYPE_ID)
            return (LOWORD((DWORD_PTR)p->lpstrDeviceType) == MCI_DEVTYPE_CD_AUDIO);
        if (p->lpstrDeviceType && _stricmp(p->lpstrDeviceType, "cdaudio") == 0)
            return 1;
    }
    return 0;
}

MCIERROR WINAPI i76_mciSendCommandA(MCIDEVICEID id, UINT msg, DWORD_PTR flags, DWORD_PTR param)
{
    /* MCI_OPEN for cdaudio: claim it. This is the call that fails on a machine
     * with no optical drive, and the whole reason this DLL exists. */
    if (msg == MCI_OPEN) {
        MCI_OPEN_PARMSA *p = (MCI_OPEN_PARMSA *)param;
        if (is_cdaudio_open((UINT)flags, p)) {
            EnterCriticalSection(&g_lock);
            if (!g_numTracks) scan_tracks();
            g_open = 1;
            g_timeFormat = MCI_FORMAT_MSF;
            g_curTrack = g_firstTrack;
            p->wDeviceID = g_fakeId;
            LeaveCriticalSection(&g_lock);
            logf("MCI_OPEN cdaudio -> granted id 0x%X, %d tracks", g_fakeId, g_numTracks);
            return g_numTracks ? 0 : MCIERR_DEVICE_NOT_READY;
        }
        return real_mciSendCommandA(id, msg, flags, param);   /* not ours */
    }

    if (id != g_fakeId || !g_open)
        return real_mciSendCommandA(id, msg, flags, param);   /* not ours */

    EnterCriticalSection(&g_lock);
    switch (msg) {

    case MCI_SET: {
        MCI_SET_PARMS *p = (MCI_SET_PARMS *)param;
        if ((flags & MCI_SET_TIME_FORMAT) && p) {
            g_timeFormat = p->dwTimeFormat;
            logf("MCI_SET time format %lu", (unsigned long)g_timeFormat);
        }
        LeaveCriticalSection(&g_lock);
        return 0;
    }

    case MCI_STATUS: {
        MCI_STATUS_PARMS *p = (MCI_STATUS_PARMS *)param;
        DWORD item;
        if (!p) { LeaveCriticalSection(&g_lock); return MCIERR_MISSING_PARAMETER; }
        item = p->dwItem;
        p->dwReturn = 0;
        switch (item) {
        case MCI_STATUS_NUMBER_OF_TRACKS: p->dwReturn = g_numTracks; break;
        case MCI_STATUS_CURRENT_TRACK:    p->dwReturn = g_curTrack;  break;
        case MCI_STATUS_MEDIA_PRESENT:    p->dwReturn = TRUE;        break;
        case MCI_STATUS_READY:            p->dwReturn = TRUE;        break;
        case MCI_STATUS_MODE:
            p->dwReturn = is_playing() ? MCI_MODE_PLAY
                        : (g_paused ? MCI_MODE_PAUSE : MCI_MODE_STOP);
            break;
        case MCI_STATUS_LENGTH:
            if (flags & MCI_TRACK) {
                int t = (int)p->dwTrack;
                DWORD ms = (t > 0 && t < MAX_TRACKS && g_track[t].present) ? g_track[t].ms : 0;
                p->dwReturn = (g_timeFormat == MCI_FORMAT_MILLISECONDS) ? ms : ms_to_msf(ms);
            } else {
                DWORD ms = disc_length_ms();
                p->dwReturn = (g_timeFormat == MCI_FORMAT_MILLISECONDS) ? ms : ms_to_msf(ms);
            }
            break;
        case MCI_STATUS_POSITION: {
            DWORD ms = position_ms();
            if (g_timeFormat == MCI_FORMAT_TMSF)      p->dwReturn = ms_to_tmsf(g_curTrack, ms);
            else if (g_timeFormat == MCI_FORMAT_MILLISECONDS) p->dwReturn = ms;
            else                                     p->dwReturn = ms_to_msf(ms);
            break;
        }
        /* A CD player reports whether each track is audio or data. Every file we
         * serve is audio; saying otherwise would make the engine skip them. */
        case MCI_CDA_STATUS_TYPE_TRACK: p->dwReturn = MCI_CDA_TRACK_AUDIO; break;
        default:
            logf("MCI_STATUS unhandled item %lu - returning 0", (unsigned long)item);
            break;
        }
        LeaveCriticalSection(&g_lock);
        return 0;
    }

    case MCI_PLAY: {
        MCI_PLAY_PARMS *p = (MCI_PLAY_PARMS *)param;
        int track = g_curTrack;
        if (p && (flags & MCI_FROM)) {
            /* The track lives in the low byte for TMSF. For MSF the engine is
             * addressing the disc as one timeline, so map elapsed time onto the
             * track it lands in. */
            if (g_timeFormat == MCI_FORMAT_TMSF) {
                track = MCI_TMSF_TRACK(p->dwFrom);
            } else if (g_timeFormat == MCI_FORMAT_MSF) {
                DWORD want = (MCI_MSF_MINUTE(p->dwFrom) * 60000UL)
                           + (MCI_MSF_SECOND(p->dwFrom) * 1000UL);
                DWORD acc = 0; int i;
                track = g_firstTrack;
                for (i = 1; i < MAX_TRACKS; i++) {
                    if (!g_track[i].present) continue;
                    if (want < acc + g_track[i].ms) { track = i; break; }
                    acc += g_track[i].ms;
                    track = i;
                }
            } else {
                track = (int)p->dwFrom;
            }
        }
        logf("MCI_PLAY flags 0x%lX from 0x%lX -> track %d",
             (unsigned long)flags, p ? (unsigned long)p->dwFrom : 0UL, track);
        {
            MCIERROR rc = start_track(track);
            LeaveCriticalSection(&g_lock);
            return rc;
        }
    }

    case MCI_STOP:
        logf("MCI_STOP");
        stop_playback();
        LeaveCriticalSection(&g_lock);
        return 0;

    case MCI_PAUSE: {
        char cmd[64];
        sprintf(cmd, "pause %s", g_alias);
        real_mciSendStringA(cmd, NULL, 0, NULL);
        g_paused = 1;
        logf("MCI_PAUSE");
        LeaveCriticalSection(&g_lock);
        return 0;
    }

    case MCI_RESUME: {
        char cmd[64];
        sprintf(cmd, "resume %s", g_alias);
        real_mciSendStringA(cmd, NULL, 0, NULL);
        g_paused = 0;
        logf("MCI_RESUME");
        LeaveCriticalSection(&g_lock);
        return 0;
    }

    case MCI_SEEK:
        logf("MCI_SEEK (accepted, no-op)");
        LeaveCriticalSection(&g_lock);
        return 0;

    case MCI_CLOSE:
        logf("MCI_CLOSE");
        stop_playback();
        g_open = 0;
        LeaveCriticalSection(&g_lock);
        return 0;

    default:
        logf("unhandled MCI msg 0x%X (accepted)", msg);
        LeaveCriticalSection(&g_lock);
        return 0;
    }
}

/* ---- aux: the CD-audio volume slider ------------------------------------ */
/* On 90s hardware CD audio was mixed in analogue and its volume set through an
 * `aux` device. With no CD there is no such device, so the engine's music
 * volume control would do nothing. Advertise one and route it to our player,
 * which makes the in-game music slider work. */
MMRESULT WINAPI i76_auxGetNumDevs(void)
{
    UINT n = real_auxGetNumDevs ? real_auxGetNumDevs() : 0;
    if (n == 0) return 1;          /* offer exactly our fake CD-audio aux */
    return n;
}

MMRESULT WINAPI i76_auxGetDevCapsA(UINT_PTR id, LPAUXCAPSA caps, UINT size)
{
    UINT n = real_auxGetNumDevs ? real_auxGetNumDevs() : 0;
    if (n == 0 && caps && size >= sizeof(AUXCAPSA)) {
        memset(caps, 0, size);
        caps->wMid = 1; caps->wPid = 1; caps->vDriverVersion = 0x0100;
        strcpy(caps->szPname, "I76 CD Audio");
        caps->wTechnology = AUXCAPS_CDAUDIO;
        caps->dwSupport = AUXCAPS_VOLUME;
        return MMSYSERR_NOERROR;
    }
    return real_auxGetDevCapsA(id, caps, size);
}

MMRESULT WINAPI i76_auxSetVolume(UINT id, DWORD vol)
{
    /* aux volume is two 16-bit channels; MCI wants 0..1000. */
    DWORD lo = LOWORD(vol), hi = HIWORD(vol);
    DWORD peak = (hi > lo) ? hi : lo;
    EnterCriticalSection(&g_lock);
    g_volume = (peak * 1000UL) / 0xFFFFUL;
    if (g_playing) {
        char cmd[64];
        sprintf(cmd, "setaudio %s volume to %lu", g_alias, (unsigned long)g_volume);
        real_mciSendStringA(cmd, NULL, 0, NULL);
    }
    LeaveCriticalSection(&g_lock);
    logf("auxSetVolume 0x%lX -> %lu/1000", (unsigned long)vol, (unsigned long)g_volume);
    if (real_auxGetNumDevs && real_auxGetNumDevs() > 0) return real_auxSetVolume(id, vol);
    return MMSYSERR_NOERROR;
}

/* ---- straight pass-through ---------------------------------------------- */
/* joy* is the game's STEERING WHEEL path. Untouched, deliberately. */
MMRESULT WINAPI i76_joyGetDevCapsA(UINT_PTR id, LPJOYCAPSA c, UINT n) { return real_joyGetDevCapsA(id, c, n); }
UINT     WINAPI i76_joyGetNumDevs(void)                               { return real_joyGetNumDevs(); }
MMRESULT WINAPI i76_joyGetPosEx(UINT id, LPJOYINFOEX pi)              { return real_joyGetPosEx(id, pi); }
DWORD    WINAPI i76_timeGetTime(void)                                 { return real_timeGetTime(); }
BOOL     WINAPI i76_mciGetErrorStringA(MCIERROR e, LPSTR s, UINT n)   { return real_mciGetErrorStringA(e, s, n); }

/* ---- init --------------------------------------------------------------- */
static int load_real(void)
{
    char path[MAX_PATH];
    UINT n = GetSystemDirectoryA(path, MAX_PATH);
    if (!n || n > MAX_PATH - 16) return 0;
    /* ABSOLUTE path. Loading "winmm.dll" by name would find THIS dll (the app
     * directory is searched first) and recurse until the stack dies. */
    strcat(path, "\\winmm.dll");
    g_real = LoadLibraryA(path);
    if (!g_real) return 0;

#define BIND(f) real_##f = (pfn_##f)GetProcAddress(g_real, #f); if (!real_##f) return 0;
    BIND(mciSendStringA)
    BIND(mciSendCommandA)
    BIND(mciGetErrorStringA)
    BIND(joyGetDevCapsA)
    BIND(joyGetNumDevs)
    BIND(joyGetPosEx)
    BIND(auxGetDevCapsA)
    BIND(auxGetNumDevs)
    BIND(auxSetVolume)
    BIND(timeGetTime)
#undef BIND
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char *p;
        DisableThreadLibraryCalls(hinst);
        InitializeCriticalSection(&g_lock);

        GetModuleFileNameA(hinst, g_dir, MAX_PATH);
        p = strrchr(g_dir, '\\');
        if (p) *p = 0;
        sprintf(g_logpath, "%s\\winmm-cdaudio.log", g_dir);
        g_logging = (GetEnvironmentVariableA("I76_CDAUDIO_LOG", NULL, 0) > 0);

        if (!load_real()) {
            /* Without the real winmm the game cannot run at all - it needs
             * joystick input and timing from it. Say so loudly rather than
             * failing in a way that looks like a game bug. */
            MessageBoxA(NULL,
                "winmm proxy could not load the real winmm.dll.\n\n"
                "Delete winmm.dll from the Interstate '76 folder to restore normal operation.",
                "I76 CD-audio proxy", MB_OK | MB_ICONERROR);
            return FALSE;
        }
        logf("--- winmm-cdaudio attached, dir %s ---", g_dir);
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_playing) stop_playback();
    }
    return TRUE;
}
