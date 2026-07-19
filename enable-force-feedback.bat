@echo off
rem Interstate '76 Gold - enable force feedback (FOR THE WINDOWS BOX).
rem
rem The Gold Edition ships with FFB code (Nitro Pack) but looks for its settings under
rem the key name "Interstate '76". CD-era installers wrote "Interstate'76FRC" instead,
rem so FFB stayed dormant - the classic fix copies that key under the expected name
rem (PCGamingWiki: "Enabling force feedback on the Gold Edition").
rem
rem OBSERVED 2026-07-10: GOG's own installer (Galaxy) writes the un-suffixed key
rem directly - "Interstate '76" containing just EXE=i76.exe - which is why FFB
rem "just works" on GOG-installed machines (VOGONS t=61199). So for zip/portable
rem installs with NO ACTIVISION keys at all, creating that minimal key is the fix;
rem this script now does exactly that when no FRC source key exists.
rem
rem Order of attempts (first success wins):
rem   1. Copy Interstate'76FRC -> Interstate '76 (CD installs; preserves settings)
rem   2. Create Interstate '76 with EXE=i76.exe (what the GOG installer writes)
rem Reversible either way: delete the "Interstate '76" key to revert.
rem
rem RUN AS ADMINISTRATOR (HKLM). Works on 64-bit Windows (WOW6432Node) and 32-bit.
rem NOTE: no effect on the Mac port - Wine has no macOS backend for DirectInput
rem FFB *effects* (docs/FORCE-FEEDBACK-AND-VISUALS.md). Gamepad RUMBLE is a
rem different channel and DOES work on Mac via XInputSetState (synthetic,
rem driven by i76-remap.ahk - field-confirmed 2026-07-18).

reg copy "HKLM\SOFTWARE\WOW6432Node\ACTIVISION\Interstate'76FRC" "HKLM\SOFTWARE\WOW6432Node\ACTIVISION\Interstate '76" /s /f 2>nul && (
    echo Force feedback enabled: FRC key copied ^(WOW6432Node^).
    goto :done
)
reg copy "HKLM\SOFTWARE\ACTIVISION\Interstate'76FRC" "HKLM\SOFTWARE\ACTIVISION\Interstate '76" /s /f 2>nul && (
    echo Force feedback enabled: FRC key copied.
    goto :done
)
reg add "HKLM\SOFTWARE\WOW6432Node\ACTIVISION\Interstate '76" /v EXE /t REG_SZ /d i76.exe /f 2>nul && (
    echo Force feedback enabled: key created GOG-installer-style ^(WOW6432Node^).
    goto :done
)
reg add "HKLM\SOFTWARE\ACTIVISION\Interstate '76" /v EXE /t REG_SZ /d i76.exe /f && (
    echo Force feedback enabled: key created GOG-installer-style.
) || (
    echo FAILED - is this window running as Administrator?
)
:done
echo Plug in the DirectInput FFB wheel/stick BEFORE launching the game.
pause
