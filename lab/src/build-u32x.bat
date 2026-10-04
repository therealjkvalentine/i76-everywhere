@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars32.bat" >nul 2>&1
cd /d "C:\Users\james\i76-uncap-lab\src"
cl /nologo /O2 /LD u32x.c /link /DEF:u32x.def user32.lib /OUT:u32x_new.dll
