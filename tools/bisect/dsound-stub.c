/* dsstub.c - a DirectSound that politely reports "no sound driver".
 *
 * i76.exe imports exactly one function from DSOUND.dll: DirectSoundCreate. Returning
 * DSERR_NODRIVER makes the engine take its own no-sound-card path, which is a case it has
 * handled since 1997. Dropped in the TEST install's folder only (the loader prefers the
 * application directory), so the player's install and the machine's audio are untouched -
 * this exists so an isolated automated instance does not make noise at the user's desk. */
#include <windows.h>
#define DSERR_NODRIVER 0x88780078L
HRESULT WINAPI DirectSoundCreate(void *guid, void **out, void *unk)
{
    (void)guid; (void)unk;
    if (out) *out = 0;
    return DSERR_NODRIVER;
}
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID v) { (void)h;(void)r;(void)v; return TRUE; }
