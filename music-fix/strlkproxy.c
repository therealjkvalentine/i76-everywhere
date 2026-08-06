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
    return strstr(ret, "playing") != NULL;
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
    mlog(e ? "  str FAIL(%lu): %s" : "  str ok: %s", (unsigned long)e, cmd);
}

static void stop_track(void) {
    if (!g_open) return;
    char cmd[64]; _snprintf(cmd, sizeof(cmd), "close %s", g_alias);
    mci_str(cmd); g_open = 0;
}

/* CD-audio track N -> music\N.mp3 (track 1 was the data track; there is no 1.mp3) */
static MCIERROR play_track(int track) {
    char mp3[MAX_PATH], cmd[MAX_PATH + 64];
    _snprintf(mp3, sizeof(mp3), "%s\\music\\%d.mp3", g_dir, track);
    if (GetFileAttributesA(mp3) == INVALID_FILE_ATTRIBUTES) {
        mlog("  track %d MISSING: %s", track, mp3); return MCIERR_FILE_NOT_FOUND;
    }
    stop_track();
    _snprintf(cmd, sizeof(cmd), "open \"%s\" type mpegvideo alias %s", mp3, g_alias); mci_str(cmd);
    g_open = 1;
    _snprintf(cmd, sizeof(cmd), "play %s", g_alias); mci_str(cmd);
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
        mlog("MCI_PLAY flags=0x%lX from=%ld -> track %d",
             (unsigned long)flags, p ? (long)p->dwFrom : -1, track);
        g_curTrack = track;
        return play_track(track);
    }
    case MCI_STOP: case MCI_PAUSE: case MCI_CLOSE: stop_track(); return 0;
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
        mlog("  mission-launch: %s at 0x%08lX has UNEXPECTED bytes - not patching", what, (unsigned long)va);
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

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, g_dir, sizeof(g_dir));
        char *s = strrchr(g_dir, '\\'); if (s) *s = 0;          /* -> game folder */
        g_logging = GetEnvironmentVariableA("I76MUSIC_LOG", NULL, 0) > 0;
        load_orig();   /* must happen before the game calls any forwarded export */
        apply_mission_launch();   /* before the exe's entry point, so before the buffer is read */
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
    }
    return TRUE;
}
