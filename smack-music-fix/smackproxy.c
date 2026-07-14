/* SMACKW32.DLL proxy for Interstate '76 - "stop the music when a movie starts".
 *
 * WHY: I76 never stops CD music for FMV cutscenes - on a 1997 CD-ROM the drive
 * physically couldn't stream data + redbook at once, so opening a movie silenced
 * the music as a hardware side effect. File-based music (GOG win32.dll/audiere,
 * DxWnd dxwplay virtual CD) has no such limit, so the last mission/menu track
 * bleeds over every cutscene's own baked-in score. This proxy recreates the
 * original behavior at the exact same trigger point: SmackOpen() = movie start.
 *
 * i76.exe imports SMACKW32.DLL BY ORDINAL, so ordinals here must match the real
 * DLL exactly (they do - generated from its export table). All 39 exports are
 * forwarded to the renamed original (smackorg.dll); only _SmackOpen@12 (ord 14)
 * does extra work: broadcast MCI_STOP to every open MCI device on every layer
 * that could be playing music, then forward.
 *
 * Build: build.sh (i686-w64-mingw32-gcc). Install: ../setup-cutscene-music-fix.sh
 */
#include <windows.h>
#include <mmsystem.h>

static HMODULE g_real;

/* freestanding build: no CRT, so provide the DLL entry point ourselves */
BOOL WINAPI DllMainCRTStartup(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)inst; (void)reason; (void)reserved;
    return TRUE;
}

static FARPROC real_fn(const char *decorated)
{
    if (!g_real)
        g_real = LoadLibraryA("smackorg.dll");
    return g_real ? GetProcAddress(g_real, decorated) : NULL;
}

/* Stop CD-audio music on every plausible playback layer. All calls are
 * idempotent and harmless when nothing is playing / no device exists.
 *  - static winmm import: gets IAT-patched by DxWnd (Mac: routes to dxwplay)
 *  - win32.dll: GOG's audiere-based MCI shim on the Windows release */
static void stop_cd_music(void)
{
    mciSendCommandA(MCI_ALL_DEVICE_ID, MCI_STOP, 0, 0);
    mciSendStringA("stop cdaudio", NULL, 0, NULL);
    HMODULE shim = GetModuleHandleA("win32.dll");
    if (shim) {
        typedef MCIERROR (WINAPI *cmd_t)(MCIDEVICEID, UINT, DWORD_PTR, DWORD_PTR);
        typedef MCIERROR (WINAPI *str_t)(LPCSTR, LPSTR, UINT, HANDLE);
        cmd_t c = (cmd_t)GetProcAddress(shim, "mciSendCommandA");
        str_t s = (str_t)GetProcAddress(shim, "mciSendStringA");
        if (c) c(MCI_ALL_DEVICE_ID, MCI_STOP, 0, 0);
        if (s) s("stop cdaudio", NULL, 0, NULL);
    }
}


typedef DWORD (WINAPI *pSmackBufferString)(DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferString(DWORD a0, DWORD a1)
{
    pSmackBufferString f = (pSmackBufferString)real_fn("_SmackBufferString@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackBufferOpen)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferOpen(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5)
{
    pSmackBufferOpen f = (pSmackBufferOpen)real_fn("_SmackBufferOpen@24");
    return f ? f(a0, a1, a2, a3, a4, a5) : 0;
}

typedef DWORD (WINAPI *pSmackBufferBlit)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferBlit(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD a6, DWORD a7)
{
    pSmackBufferBlit f = (pSmackBufferBlit)real_fn("_SmackBufferBlit@32");
    return f ? f(a0, a1, a2, a3, a4, a5, a6, a7) : 0;
}

typedef DWORD (WINAPI *pSmackBufferFocused)(DWORD);
DWORD WINAPI proxy_SmackBufferFocused(DWORD a0)
{
    pSmackBufferFocused f = (pSmackBufferFocused)real_fn("_SmackBufferFocused@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackBufferNewPalette)(DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferNewPalette(DWORD a0, DWORD a1, DWORD a2)
{
    pSmackBufferNewPalette f = (pSmackBufferNewPalette)real_fn("_SmackBufferNewPalette@12");
    return f ? f(a0, a1, a2) : 0;
}

typedef DWORD (WINAPI *pSmackBufferClose)(DWORD);
DWORD WINAPI proxy_SmackBufferClose(DWORD a0)
{
    pSmackBufferClose f = (pSmackBufferClose)real_fn("_SmackBufferClose@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackBufferSetPalette)(DWORD);
DWORD WINAPI proxy_SmackBufferSetPalette(DWORD a0)
{
    pSmackBufferSetPalette f = (pSmackBufferSetPalette)real_fn("_SmackBufferSetPalette@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackBufferClear)(DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferClear(DWORD a0, DWORD a1)
{
    pSmackBufferClear f = (pSmackBufferClear)real_fn("_SmackBufferClear@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackSetSystemRes)(DWORD);
DWORD WINAPI proxy_SmackSetSystemRes(DWORD a0)
{
    pSmackSetSystemRes f = (pSmackSetSystemRes)real_fn("_SmackSetSystemRes@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackBufferToBuffer)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferToBuffer(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD a6, DWORD a7)
{
    pSmackBufferToBuffer f = (pSmackBufferToBuffer)real_fn("_SmackBufferToBuffer@32");
    return f ? f(a0, a1, a2, a3, a4, a5, a6, a7) : 0;
}

typedef DWORD (WINAPI *pSmackBufferToBufferTrans)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferToBufferTrans(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD a6, DWORD a7, DWORD a8)
{
    pSmackBufferToBufferTrans f = (pSmackBufferToBufferTrans)real_fn("_SmackBufferToBufferTrans@36");
    return f ? f(a0, a1, a2, a3, a4, a5, a6, a7, a8) : 0;
}

typedef DWORD (WINAPI *pSmackBufferFromScreen)(DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferFromScreen(DWORD a0, DWORD a1, DWORD a2, DWORD a3)
{
    pSmackBufferFromScreen f = (pSmackBufferFromScreen)real_fn("_SmackBufferFromScreen@16");
    return f ? f(a0, a1, a2, a3) : 0;
}

typedef DWORD (WINAPI *pSmackBufferCopyPalette)(DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackBufferCopyPalette(DWORD a0, DWORD a1, DWORD a2)
{
    pSmackBufferCopyPalette f = (pSmackBufferCopyPalette)real_fn("_SmackBufferCopyPalette@12");
    return f ? f(a0, a1, a2) : 0;
}

typedef DWORD (WINAPI *pSmackOpen)(DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackOpen(DWORD a0, DWORD a1, DWORD a2)
{
    stop_cd_music();   /* movie starting: silence the CD track, like real hardware did */
    pSmackOpen f = (pSmackOpen)real_fn("_SmackOpen@12");
    return f ? f(a0, a1, a2) : 0;
}

typedef DWORD (WINAPI *pSmackSimulate)(DWORD);
DWORD WINAPI proxy_SmackSimulate(DWORD a0)
{
    pSmackSimulate f = (pSmackSimulate)real_fn("_SmackSimulate@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackFrameRate)(DWORD);
DWORD WINAPI proxy_SmackFrameRate(DWORD a0)
{
    pSmackFrameRate f = (pSmackFrameRate)real_fn("_SmackFrameRate@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackSoundOnOff)(DWORD, DWORD);
DWORD WINAPI proxy_SmackSoundOnOff(DWORD a0, DWORD a1)
{
    pSmackSoundOnOff f = (pSmackSoundOnOff)real_fn("_SmackSoundOnOff@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackClose)(DWORD);
DWORD WINAPI proxy_SmackClose(DWORD a0)
{
    pSmackClose f = (pSmackClose)real_fn("_SmackClose@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackDoFrame)(DWORD);
DWORD WINAPI proxy_SmackDoFrame(DWORD a0)
{
    pSmackDoFrame f = (pSmackDoFrame)real_fn("_SmackDoFrame@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackSummary)(DWORD, DWORD);
DWORD WINAPI proxy_SmackSummary(DWORD a0, DWORD a1)
{
    pSmackSummary f = (pSmackSummary)real_fn("_SmackSummary@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackNextFrame)(DWORD);
DWORD WINAPI proxy_SmackNextFrame(DWORD a0)
{
    pSmackNextFrame f = (pSmackNextFrame)real_fn("_SmackNextFrame@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackToScreen)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackToScreen(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5)
{
    pSmackToScreen f = (pSmackToScreen)real_fn("_SmackToScreen@24");
    return f ? f(a0, a1, a2, a3, a4, a5) : 0;
}

typedef DWORD (WINAPI *pSmackToBuffer)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackToBuffer(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD a6)
{
    pSmackToBuffer f = (pSmackToBuffer)real_fn("_SmackToBuffer@28");
    return f ? f(a0, a1, a2, a3, a4, a5, a6) : 0;
}

typedef DWORD (WINAPI *pSmackColorTrans)(DWORD, DWORD);
DWORD WINAPI proxy_SmackColorTrans(DWORD a0, DWORD a1)
{
    pSmackColorTrans f = (pSmackColorTrans)real_fn("_SmackColorTrans@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackColorRemap)(DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackColorRemap(DWORD a0, DWORD a1, DWORD a2, DWORD a3)
{
    pSmackColorRemap f = (pSmackColorRemap)real_fn("_SmackColorRemap@16");
    return f ? f(a0, a1, a2, a3) : 0;
}

typedef DWORD (WINAPI *pSmackGetTrackData)(DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackGetTrackData(DWORD a0, DWORD a1, DWORD a2)
{
    pSmackGetTrackData f = (pSmackGetTrackData)real_fn("_SmackGetTrackData@12");
    return f ? f(a0, a1, a2) : 0;
}

typedef DWORD (WINAPI *pSmackGoto)(DWORD, DWORD);
DWORD WINAPI proxy_SmackGoto(DWORD a0, DWORD a1)
{
    pSmackGoto f = (pSmackGoto)real_fn("_SmackGoto@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackToBufferRect)(DWORD, DWORD);
DWORD WINAPI proxy_SmackToBufferRect(DWORD a0, DWORD a1)
{
    pSmackToBufferRect f = (pSmackToBufferRect)real_fn("_SmackToBufferRect@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackSoundInTrack)(DWORD, DWORD);
DWORD WINAPI proxy_SmackSoundInTrack(DWORD a0, DWORD a1)
{
    pSmackSoundInTrack f = (pSmackSoundInTrack)real_fn("_SmackSoundInTrack@8");
    return f ? f(a0, a1) : 0;
}

typedef DWORD (WINAPI *pSmackVolumePan)(DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackVolumePan(DWORD a0, DWORD a1, DWORD a2, DWORD a3)
{
    pSmackVolumePan f = (pSmackVolumePan)real_fn("_SmackVolumePan@16");
    return f ? f(a0, a1, a2, a3) : 0;
}

typedef DWORD (WINAPI *pSmackSoundCheck)(void);
DWORD WINAPI proxy_SmackSoundCheck(void)
{
    pSmackSoundCheck f = (pSmackSoundCheck)real_fn("_SmackSoundCheck@0");
    return f ? f() : 0;
}

typedef DWORD (WINAPI *pSmackWait)(DWORD);
DWORD WINAPI proxy_SmackWait(DWORD a0)
{
    pSmackWait f = (pSmackWait)real_fn("_SmackWait@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackSoundUseMSS)(DWORD);
DWORD WINAPI proxy_SmackSoundUseMSS(DWORD a0)
{
    pSmackSoundUseMSS f = (pSmackSoundUseMSS)real_fn("_SmackSoundUseMSS@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackSoundUseDW)(DWORD, DWORD, DWORD);
DWORD WINAPI proxy_SmackSoundUseDW(DWORD a0, DWORD a1, DWORD a2)
{
    pSmackSoundUseDW f = (pSmackSoundUseDW)real_fn("_SmackSoundUseDW@12");
    return f ? f(a0, a1, a2) : 0;
}

typedef DWORD (WINAPI *pdonemarker)(DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_donemarker(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4)
{
    pdonemarker f = (pdonemarker)real_fn("_donemarker@20");
    return f ? f(a0, a1, a2, a3, a4) : 0;
}

typedef DWORD (WINAPI *pTimerFunc)(DWORD, DWORD, DWORD, DWORD, DWORD);
DWORD WINAPI proxy_TimerFunc(DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4)
{
    pTimerFunc f = (pTimerFunc)real_fn("_TimerFunc@20");
    return f ? f(a0, a1, a2, a3, a4) : 0;
}

typedef DWORD (WINAPI *pSetDirectSoundHWND)(DWORD);
DWORD WINAPI proxy_SetDirectSoundHWND(DWORD a0)
{
    pSetDirectSoundHWND f = (pSetDirectSoundHWND)real_fn("_SetDirectSoundHWND@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackSoundUseDirectSound)(DWORD);
DWORD WINAPI proxy_SmackSoundUseDirectSound(DWORD a0)
{
    pSmackSoundUseDirectSound f = (pSmackSoundUseDirectSound)real_fn("_SmackSoundUseDirectSound@4");
    return f ? f(a0) : 0;
}

typedef DWORD (WINAPI *pSmackSoundUseWin)(void);
DWORD WINAPI proxy_SmackSoundUseWin(void)
{
    pSmackSoundUseWin f = (pSmackSoundUseWin)real_fn("_SmackSoundUseWin@0");
    return f ? f() : 0;
}
