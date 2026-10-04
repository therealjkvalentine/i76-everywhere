/*
 * inject.exe <pid> <dllpath> - classic CreateRemoteThread(LoadLibraryA) injector.
 * Build (32-bit, to match i76.exe): cl /nologo /O2 inject.c
 */
#include <windows.h>
#include <stdio.h>

int main(int argc, char** argv) {
    if (argc < 3) { printf("usage: inject <pid> <dllpath>\n"); return 1; }
    DWORD pid = strtoul(argv[1], 0, 0);
    char full[MAX_PATH];
    GetFullPathNameA(argv[2], MAX_PATH, full, 0);
    size_t len = strlen(full) + 1;

    HANDLE p = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE |
                           PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, FALSE, pid);
    if (!p) { printf("OpenProcess failed %lu\n", GetLastError()); return 1; }

    void* remote = VirtualAllocEx(p, 0, len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote) { printf("VirtualAllocEx failed %lu\n", GetLastError()); return 1; }
    SIZE_T wrote = 0;
    WriteProcessMemory(p, remote, full, len, &wrote);

    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    FARPROC load = GetProcAddress(k32, "LoadLibraryA");   /* same address in the target (kernel32 shared) */

    HANDLE t = CreateRemoteThread(p, 0, 0, (LPTHREAD_START_ROUTINE)load, remote, 0, 0);
    if (!t) { printf("CreateRemoteThread failed %lu\n", GetLastError()); return 1; }
    WaitForSingleObject(t, 10000);
    DWORD code = 0; GetExitCodeThread(t, &code);
    printf("injected '%s' into pid %lu, LoadLibrary returned 0x%08lX %s\n",
           full, pid, code, code ? "(module handle - OK)" : "(NULL - load failed)");
    VirtualFreeEx(p, remote, 0, MEM_RELEASE);
    CloseHandle(t); CloseHandle(p);
    return code ? 0 : 2;
}
