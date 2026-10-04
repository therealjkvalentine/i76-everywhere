#include <windows.h>
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r){
    if(reason==DLL_PROCESS_ATTACH) OutputDebugStringA("i76uncap hello DLL attached\n");
    return TRUE;
}
__declspec(dllexport) int i76uncap_probe(void){ return 0x60; }
