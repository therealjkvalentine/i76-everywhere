<#
  test-escmenu.ps1 - Test A of docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md: the exe's in-mission Esc menu and the mouse.

  -Stage open   : proxy-run into t01 (kept alive), press Esc, read the engine mode / page rect / clip, pin test
                  (move the OS cursor to the far right, read it back), capture the menu to runs\escmenu\<tag>-menu.png
  -Stage click  : click UI/screen point(s) given as -Click "x,y" (screen pixels of the capture frame: the capture is
                  the 4:3 UI area, 1 px = 1 UI unit -> Click-UI), read [[0x654a20]+0x20] before/after, capture
  -Stage close  : WM_CLOSE / kill, restore STRLKUP.DLL and the lock
  -Dll <path>   : before -Stage open, copy this u32x build over game\u32x.dll (the Aug-16 one is kept as u32x.dll.aug16)
  -RestoreDll   : put u32x.dll.aug16 back (after close)
#>
param([ValidateSet("open", "click", "close")] [string]$Stage = "open", [string]$Tag = "a0", [string]$Click, [string]$Dll, [switch]$RestoreDll,
      [string]$GameDir = "C:\Users\james\i76-uncap-lab\game", [string]$GameArgs = "-glide",   # -GameDir ..\game-alt: the renderer test copy
      [switch]$KeepInstalledDll)                                                               # -Stage open: proxy-run without the DLL swap
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Here\lib\gamedir.ps1"
$G = Resolve-LabGameDir $GameDir       # inside the lab only; the playable installs are refused by name
$I76GameDirInUse = $G                  # focuslib / memlib / maplib: prefer this folder's process and conf
$Out = Join-Path $Here "runs\escmenu"; New-Item -ItemType Directory -Force $Out | Out-Null
. "$Here\lib\focuslib.ps1"; . "$Here\lib\inputlib.ps1"; . "$Here\lib\maplib.ps1"; . "$Here\lib\memlib.ps1"
Add-Type -Name U -Namespace EM -MemberDefinition '[DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p); [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y); [DllImport("user32.dll")] public static extern bool GetClipCursor(out RECT r); [DllImport("user32.dll")] public static extern bool PostMessageA(IntPtr h, uint m, IntPtr w, IntPtr l); [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; } [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }'
function Reads($c) {
    $mode = Mem-I32 $c 0x4fe534; $vm = Mem-I32 $c 0x5dd360
    $row = (3..6 | ForEach-Object { Mem-I32 $c (0x4f9e08 + 28 * $vm + 4 * $_) }) -join " "
    $page = (0x654a3c, 0x654a40, 0x654a44, 0x654a48 | ForEach-Object { Mem-I32 $c $_ }) -join " "
    $disp = (0x5dcedc, 0x5dcee0, 0x5dcee4, 0x5dcee8 | ForEach-Object { Mem-I32 $c $_ }) -join " "
    $menu = Mem-I32 $c 0x654a20; $sel = if ($menu) { Mem-I32 $c ($menu + 0x20) } else { "-" }
    $clip = (0x609300, 0x609304, 0x609308, 0x60930c | ForEach-Object { Mem-I32 $c $_ }) -join " "
    $r = New-Object EM.U+RECT; [void][EM.U]::GetClipCursor([ref]$r)
    "mode 0x{0:x} vmode {1} row[{2}] page[{3}] disp[{4}] sel {5} armed {6} cur_en {7} reclip {8} engclip[{9}] osclip {10},{11}-{12},{13} client {14}x{15}" -f $mode, $vm, $row, $page, $disp, $sel, (Mem-I32 $c 0x654b1c), (Mem-I32 $c 0x535f6c), (Mem-I32 $c 0x535f70), $clip, $r.L, $r.T, $r.R, $r.B, (Mem-I32 $c 0x5dcf2c), (Mem-I32 $c 0x5dcf30)
}
if ($Stage -eq "open") {
    if ($Dll) {
        if (-not (Test-Path "$G\u32x.dll.aug16")) { Copy-Item "$G\u32x.dll" "$G\u32x.dll.aug16" }
        Copy-Item $Dll "$G\u32x.dll" -Force; "u32x.dll <- $Dll (md5 $((Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.Substring(0,8)))"
    } else { "u32x.dll md5 $((Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.Substring(0,8))" }
    & "$Here\proxy-run.ps1" -Mission t01 -Hold 0 -KeepAlive -GameDir $G -GameArgs $GameArgs -KeepInstalledDll:$KeepInstalledDll | Select-String "in mission|CRASH|exited"
    $p = Get-GamePid; if (-not $p) { throw "no game" }
    Force-Foreground $p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 500
    $c = Mem-Open
    "driving: " + (Reads $c)
    Send-Key $VK.ESC; Start-Sleep -Milliseconds 1500
    "menu:    " + (Reads $c)
    # pin test: push the OS cursor to the far right of the desktop and read it back
    [void][EM.U]::SetCursorPos(3400, 700); Start-Sleep -Milliseconds 300
    $pt = New-Object EM.U+POINT; [void][EM.U]::GetCursorPos([ref]$pt); "cursor after SetCursorPos(3400,700): ($($pt.X),$($pt.Y))"
    [void][EM.U]::SetCursorPos(1720, 700); Start-Sleep -Milliseconds 300
    [void][EM.U]::GetCursorPos([ref]$pt); "cursor after SetCursorPos(1720,700): ($($pt.X),$($pt.Y))"
    Capture-UI (Join-Path $Out "$Tag-menu.png"); "shot $Out\$Tag-menu.png"
    Mem-Close $c
} elseif ($Stage -eq "click") {
    $p = Get-GamePid; if (-not $p) { throw "no game" }
    Force-Foreground $p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 300
    $c = Mem-Open
    "before: " + (Reads $c)
    foreach ($xy in ($Click -split ";")) {
        $v = $xy -split ","; Click-UI ([int]$v[0]) ([int]$v[1]) 700
        $pt = New-Object EM.U+POINT; [void][EM.U]::GetCursorPos([ref]$pt)
        "clicked UI ($($v[0]),$($v[1])) os cursor ($($pt.X),$($pt.Y)): " + (Reads $c)
    }
    Capture-UI (Join-Path $Out "$Tag-after.png"); "shot $Out\$Tag-after.png"
    Mem-Close $c
} else {
    $p = Get-GamePid
    if ($p) { [void][EM.U]::PostMessageA($p.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero); Start-Sleep -Seconds 4 }
    Get-Process | Where-Object { $_.ProcessName -like "i76*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1
    if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest"; "STRLKUP.DLL restored" }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue
    if ($RestoreDll -and (Test-Path "$G\u32x.dll.aug16")) { Copy-Item "$G\u32x.dll.aug16" "$G\u32x.dll" -Force; "u32x.dll restored to the Aug-16 build (md5 $((Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.Substring(0,8)))" }
    "closed"
}
