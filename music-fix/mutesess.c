/* mutesess.c - I76_MUTE=1 (off by default; lab test harness): the process mutes its OWN Windows audio session.
 *
 * Why: automated runs on the PC share the sound device with whoever sits at it. Until 2026-10-19 the lab muted the
 * game from outside, with a watcher process (lab tools\mute-proc.ps1 -Watch) that polls the audio sessions and mutes
 * any i76.exe one it sees; that leaves a window between the game's first buffer and the watcher's next pass, and it
 * needs the watcher to be running at all. With this switch the kickoff script only sets a variable.
 *
 * How: a thread started from DllMain (COM must not run under the loader lock; the thread body starts once DllMain has
 * returned, still before WinMain opens any sound) does CoInitializeEx (MTA), MMDeviceEnumerator ->
 * GetDefaultAudioEndpoint(eRender, role) for eConsole and eMultimedia -> Activate(IAudioSessionManager) ->
 * GetSimpleAudioVolume(NULL = the process's default session, 0 = not cross-process) -> SetMute(TRUE), and reads it back
 * with GetMute. The game's DirectSound buffers and the music player (audiere) open their streams in that default
 * session, so the session is muted before it plays anything. The ISimpleAudioVolume references are kept for the life
 * of the process (a session nobody references may be dropped and re-created unmuted); the thread checks again at 3, 15
 * and 60 s and mutes again if anything unmuted it. ole32 is loaded at run time (no import, no link change).
 * Log: "mute: session muted = 1/0 (...)". The Windows mixer shows the game muted; unmute there if wanted. */

#include <mmdeviceapi.h>
#include <audiopolicy.h>

static const GUID MS_CLSID_MMDeviceEnumerator = { 0xBCDE0395, 0xE52F, 0x467C, { 0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E } };
static const GUID MS_IID_IMMDeviceEnumerator  = { 0xA95664D2, 0x9614, 0x4F35, { 0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6 } };
static const GUID MS_IID_IAudioSessionManager = { 0xBFA971F1, 0x4D5E, 0x40BB, { 0x93, 0x5E, 0x96, 0x70, 0x39, 0xBF, 0xBE, 0xE4 } };

typedef HRESULT (WINAPI *ms_CoInitializeEx_t)(LPVOID, DWORD);
typedef HRESULT (WINAPI *ms_CoCreateInstance_t)(REFCLSID, LPUNKNOWN, DWORD, REFIID, LPVOID *);

static ISimpleAudioVolume *g_ms_vol[2];   /* kept for the life of the process */
static int g_ms_n;

/* one pass: mute every held session (getting them first if needed); returns how many read back muted */
static int ms_pass(ms_CoCreateInstance_t cci, const char *when) {
    static const ERole roles[2] = { eConsole, eMultimedia };
    int i, muted = 0, held = 0;
    HRESULT hr;
    if (!g_ms_n) {
        IMMDeviceEnumerator *en = NULL;
        hr = cci(&MS_CLSID_MMDeviceEnumerator, NULL, CLSCTX_ALL, &MS_IID_IMMDeviceEnumerator, (void **)&en);
        if (FAILED(hr) || !en) { mlog("  mute: session muted = 0 (%s: MMDeviceEnumerator failed, hr 0x%08lX)", when, (unsigned long)hr); return 0; }
        for (i = 0; i < 2; i++) {
            IMMDevice *dev = NULL; IAudioSessionManager *sm = NULL; ISimpleAudioVolume *v = NULL;
            hr = en->lpVtbl->GetDefaultAudioEndpoint(en, eRender, roles[i], &dev);
            if (FAILED(hr) || !dev) { mlog("  mute: no default render endpoint for role %d (hr 0x%08lX)", (int)roles[i], (unsigned long)hr); continue; }
            hr = dev->lpVtbl->Activate(dev, &MS_IID_IAudioSessionManager, CLSCTX_ALL, NULL, (void **)&sm);
            dev->lpVtbl->Release(dev);
            if (FAILED(hr) || !sm) { mlog("  mute: Activate(IAudioSessionManager) failed for role %d (hr 0x%08lX)", (int)roles[i], (unsigned long)hr); continue; }
            hr = sm->lpVtbl->GetSimpleAudioVolume(sm, NULL, 0, &v);
            sm->lpVtbl->Release(sm);
            if (FAILED(hr) || !v) { mlog("  mute: GetSimpleAudioVolume failed for role %d (hr 0x%08lX)", (int)roles[i], (unsigned long)hr); continue; }
            g_ms_vol[g_ms_n++] = v;
        }
        en->lpVtbl->Release(en);
    }
    for (i = 0; i < g_ms_n; i++) {
        BOOL m = FALSE;
        g_ms_vol[i]->lpVtbl->GetMute(g_ms_vol[i], &m);
        if (!m) g_ms_vol[i]->lpVtbl->SetMute(g_ms_vol[i], TRUE, NULL);
        m = FALSE; g_ms_vol[i]->lpVtbl->GetMute(g_ms_vol[i], &m);
        muted += m ? 1 : 0; held++;
    }
    mlog("  mute: session muted = %d (%s; default render session, %d/%d endpoint role(s) read back muted)",
         held && muted == held ? 1 : 0, when, muted, held);
    return muted;
}

static DWORD WINAPI ms_thread(LPVOID p) {
    static const DWORD again[3] = { 3000, 12000, 45000 };   /* -> 3, 15, 60 s after the first pass */
    static const char *const label[3] = { "check at 3 s", "check at 15 s", "check at 60 s" };
    HMODULE ole = LoadLibraryA("ole32.dll");
    ms_CoInitializeEx_t ci = ole ? (ms_CoInitializeEx_t)GetProcAddress(ole, "CoInitializeEx") : NULL;
    ms_CoCreateInstance_t cci = ole ? (ms_CoCreateInstance_t)GetProcAddress(ole, "CoCreateInstance") : NULL;
    int i;
    (void)p;
    if (!ci || !cci) { mlog("  mute: session muted = 0 (ole32 not available)"); return 0; }
    ci(NULL, COINIT_MULTITHREADED);
    ms_pass(cci, "at attach");
    for (i = 0; i < 3; i++) { Sleep(again[i]); ms_pass(cci, label[i]); }
    return 0;   /* no CoUninitialize: the held session references stay valid in the process's MTA */
}

static void apply_mute(void) {
    HANDLE t;
    if (env_flag("I76_MUTE", 8, 0) != 1) return;
    t = CreateThread(NULL, 0, ms_thread, NULL, 0, NULL);
    if (t) CloseHandle(t); else mlog("  mute: session muted = 0 (thread not started)");
}
