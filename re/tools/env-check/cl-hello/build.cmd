@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
cd /d "%~dp0"
where cl
cl /nologo /arch:IA32 /fp:precise /O2 /Oy /FAs /Fahello.asm hello.c /Fe:hello.exe /link /MACHINE:X86
echo cl_exit=%ERRORLEVEL%
hello.exe
echo run_exit=%ERRORLEVEL%
