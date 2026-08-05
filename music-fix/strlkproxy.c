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
    if (n == 0) { mlog("auxGetNumDevs -> 1 (fake CD-audio device)"); return 1; }
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
        mlog("auxGetDevCapsA(%u) -> fake CD-audio caps", (unsigned)id);
        return MMSYSERR_NOERROR;
    }
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

static int wants_cdaudio(DWORD_PTR flags, MCI_OPEN_PARMSA *p) {
    if (!(flags & MCI_OPEN_TYPE) || !p || (flags & MCI_OPEN_TYPE_ID)) return 0;
    return p->lpstrDeviceType && lstrcmpiA(p->lpstrDeviceType, "cdaudio") == 0;
}

static MCIERROR WINAPI hook_mciSendCommandA(MCIDEVICEID id, UINT msg, DWORD_PTR flags, DWORD_PTR param) {
    ensure_real();
    if (msg == MCI_OPEN) {
        MCI_OPEN_PARMSA *p = (MCI_OPEN_PARMSA *)param;
        if (wants_cdaudio(flags, p)) { p->wDeviceID = FAKE_CD_ID; mlog("MCI_OPEN cdaudio -> virtual"); return 0; }
        return real_mciSendCommandA ? real_mciSendCommandA(id, msg, flags, param) : MCIERR_DEVICE_OPEN;
    }
    if (id != FAKE_CD_ID)
        return real_mciSendCommandA ? real_mciSendCommandA(id, msg, flags, param) : MCIERR_INVALID_DEVICE_ID;

    switch (msg) {
    case MCI_SET:   return 0;   /* accept any time format / door command */
    case MCI_PLAY: {
        MCI_PLAY_PARMS *p = (MCI_PLAY_PARMS *)param;
        int track = 1;
        if (p && (flags & MCI_FROM)) {
            DWORD from = (DWORD)p->dwFrom;          /* TMSF: track in the low byte */
            track = (from & 0xFF) ? (int)(from & 0xFF) : (int)from;
        }
        mlog("MCI_PLAY flags=0x%lX from=%ld -> track %d",
             (unsigned long)flags, p ? (long)p->dwFrom : -1, track);
        return play_track(track);
    }
    case MCI_STOP: case MCI_PAUSE: case MCI_CLOSE: stop_track(); return 0;
    case MCI_STATUS: {
        MCI_STATUS_PARMS *p = (MCI_STATUS_PARMS *)param;
        if (p && (flags & MCI_STATUS_ITEM)) {
            switch (p->dwItem) {
            case MCI_STATUS_MEDIA_PRESENT:    p->dwReturn = TRUE; break;   /* a disc IS present */
            case MCI_STATUS_MODE:             p->dwReturn = g_open ? MCI_MODE_PLAY : MCI_MODE_STOP; break;
            case MCI_STATUS_NUMBER_OF_TRACKS: p->dwReturn = 17; break;
            case MCI_STATUS_READY:            p->dwReturn = TRUE; break;
            default:                          p->dwReturn = 0; break;
            }
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

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, g_dir, sizeof(g_dir));
        char *s = strrchr(g_dir, '\\'); if (s) *s = 0;          /* -> game folder */
        g_logging = GetEnvironmentVariableA("I76MUSIC_LOG", NULL, 0) > 0;
        /* i76.exe's winmm IAT is already snapped by now; redirect the mci slot. */
        HMODULE exe = GetModuleHandleA(NULL);
        void *old = patch_iat(exe, "WINMM.dll", "mciSendCommandA", hook_mciSendCommandA);
        mlog("--- strlkproxy: IAT patch mciSendCommandA old=%p new=%p ---", old, (void *)hook_mciSendCommandA);
        /* The aux trio is what actually gets the engine to TRY. Without these the
         * mci hook above was installed and never called even once - see the note
         * beside the aux typedefs. */
        mlog("  aux patches: auxGetNumDevs=%p auxGetDevCapsA=%p auxSetVolume=%p",
             patch_iat(exe, "WINMM.dll", "auxGetNumDevs",  hook_auxGetNumDevs),
             patch_iat(exe, "WINMM.dll", "auxGetDevCapsA", hook_auxGetDevCapsA),
             patch_iat(exe, "WINMM.dll", "auxSetVolume",   hook_auxSetVolume));
    } else if (reason == DLL_PROCESS_DETACH) {
        stop_track();
    }
    return TRUE;
}
