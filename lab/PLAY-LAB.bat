@echo off
rem PLAY-LAB.bat - launch the SANDBOX Interstate '76 (i76-uncap-lab\game), frame rate uncapped.
rem
rem   * Run at the PHYSICAL CONSOLE, not over RDP - the game's 3D will not init over RDP
rem     and it hangs forever on "PLEASE STAND BY" (see AGENTS.md).
rem   * This is the lab copy: nothing here touches the playable install.
rem   * Uncapped currently means ~60 fps - the remaining ceiling is suspected to be the
rem     NVIDIA driver profile (docs\framerate\README.md section 6).
rem
rem Double-click it, or run from anywhere:  C:\Users\james\i76-uncap-lab\PLAY-LAB.bat

cd /d "%~dp0game"

if exist I76PATCH.DLL (
    echo [PLAY-LAB] I76PATCH.DLL found - disabling it so the frame rate is uncapped.
    ren I76PATCH.DLL I76PATCH.DLL.disabled
) else (
    echo [PLAY-LAB] I76PATCH.DLL already disabled - uncapped.
)

echo [PLAY-LAB] launching sandbox i76.exe -glide from %CD%
start "" i76.exe -glide
