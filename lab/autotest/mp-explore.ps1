# mp-explore.ps1 - WORK IN PROGRESS (stopped 2026-10-03, see docs\MULTIPLAYER-LOCAL-TEST.md). Not the finished mp-two-instance driver.
# Step-at-a-time helper for two lab copies (game = A, game-alt = B) running at once with the repo proxy and I76_MULTI_INSTANCE=1.
#   -Start                      lock both folders, back up state files, install music-fix\Strlkup.dll, launch A then B
#   -Inst A|B -Click "x,y;x,y"  guarded click(s) in UI coordinates on that instance (waits for the 640x480 cursor clip, refuses if another window is under the point)
#   -Inst A|B -Key ESC,ENTER / -Type "127.0.0.1" / -Shot name [-Full] / -State [-Buttons]
#   -Close                      kill both, restore STRLKUP.DLL, remove locks, put back any changed state file (incl. internet.lst)
# It never clicks or types into a window that is not the chosen game (a Windows Firewall prompt is reported, not touched).
param([switch]$Start, [ValidateSet("A","B")][string]$Inst = "A", [string]$Click, [string]$Shot, [string]$Key, [string]$Type, [switch]$State, [switch]$Buttons, [switch]$Close,
      [int]$Settle = 900, [switch]$OnlyA, [switch]$Full,
      # 2026-10-05: other lab pairs (game-nucleus / game-mpb for the gate-0 IPX run) and another proxy build
      [string]$DirA = "C:\Users\james\i76-uncap-lab\game", [string]$DirB = "C:\Users\james\i76-uncap-lab\game-alt",
      [string]$Proxy = "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll",
      # 2026-10-05 (no-minimize A/B): extra env "K=V;K=V" for the copies launched, B launched later on its own
      # (-LaunchB, after -Start -OnlyA), and -Wins: each game window's folder / iconic / foreground state
      [string]$Env, [switch]$LaunchB, [switch]$Wins)
function Set-RunEnv {
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    $env:I76_MULTI_INSTANCE = "1"; $env:I76MUSIC_LOG = "1"
    if ($Env) { foreach ($kv in ($Env -split ";")) { $k, $v = $kv -split "=", 2; Set-Item "Env:$k" $v; "env $k=$v" } }
}
$ErrorActionPreference = "Continue"
$Lab = "C:\Users\james\i76-uncap-lab"
$dirs = @($DirA, $DirB)
$Out = "$Lab\autotest\runs\mp\explore"; New-Item -ItemType Directory -Force $Out | Out-Null
$Bak = "$Lab\autotest\runs\mp\bak"     # state files copied here at -Start (once), compared and put back at -Close; delete the folder after a clean -Close
$stateFiles = { param($d) Get-ChildItem $d -File -Force | Where-Object { $_.Name -match '(?i)^(savegame\.dir|save.*\.cmp|internet\.lst|.*\.def|.*\.spc|input\.map)$' } }
if ($Start) {
    if (Get-Process i76* -ErrorAction SilentlyContinue) { "an i76 process is running"; exit 1 }
    foreach ($d in $dirs) { if (Test-Path "$d\.console-test.lock") { "lock held in $d"; exit 1 } }
    foreach ($d in $dirs) {
        Set-Content "$d\.console-test.lock" "mp-explore $PID"
        $bd = Join-Path $Bak (Split-Path -Leaf $d)
        if (-not (Test-Path $bd)) { New-Item -ItemType Directory -Force $bd | Out-Null; & $stateFiles $d | ForEach-Object { Copy-Item $_.FullName $bd } ; "backed up $((Get-ChildItem $bd).Count) files of $d" }
        Copy-Item "$d\STRLKUP.DLL" "$d\STRLKUP.DLL.pretest" -Force; Copy-Item $Proxy "$d\STRLKUP.DLL" -Force
    }
    Set-RunEnv
    $pa =Start-Process "$DirA\i76.exe" -ArgumentList "-glide" -WorkingDirectory $DirA -PassThru
    "A pid $($pa.Id)"
    if (-not $OnlyA) { Start-Sleep -Seconds 12; $pb = Start-Process "$DirB\i76.exe" -ArgumentList "-glide" -WorkingDirectory $DirB -PassThru; "B pid $($pb.Id)" }
    Start-Sleep -Seconds 10
    exit 0
}
if ($LaunchB) {
    if (-not (Test-Path "$DirB\.console-test.lock")) { "B folder not prepared by -Start"; exit 1 }
    Set-RunEnv
    $pb = Start-Process "$DirB\i76.exe" -ArgumentList "-glide" -WorkingDirectory $DirB -PassThru; "B pid $($pb.Id)"; Start-Sleep -Seconds 10; exit 0
}
if ($Wins) {
    Add-Type @"
using System;using System.Runtime.InteropServices;
public class MPW { [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h); [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); }
"@
    $fg = [MPW]::GetForegroundWindow()
    Get-Process i76 -ErrorAction SilentlyContinue | ForEach-Object { "pid $($_.Id) $(Split-Path -Leaf (Split-Path $_.Path)) hwnd $($_.MainWindowHandle) iconic $([MPW]::IsIconic($_.MainWindowHandle)) foreground $($_.MainWindowHandle -eq $fg) responding $($_.Responding)" }
    exit 0
}
$G = if ($Inst -eq "A") { $DirA } else { $DirB }
$I76GameDirInUse = $G
. "$Lab\autotest\lib\gamedir.ps1"; . "$Lab\autotest\lib\focuslib.ps1"; . "$Lab\autotest\lib\inputlib.ps1"; . "$Lab\autotest\lib\maplib.ps1"
if ($Close) {
    Get-Process | Where-Object { $_.ProcessName -like "i76*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2
    foreach ($d in $dirs) {
        if (Test-Path "$d\STRLKUP.DLL.pretest") { Copy-Item "$d\STRLKUP.DLL.pretest" "$d\STRLKUP.DLL" -Force; Remove-Item "$d\STRLKUP.DLL.pretest" }
        Remove-Item "$d\.console-test.lock" -ErrorAction SilentlyContinue
        "$d STRLKUP $((Get-FileHash "$d\STRLKUP.DLL" -Algorithm MD5).Hash.Substring(0,8))"
        $bd = Join-Path $Bak (Split-Path -Leaf $d)
        $now = & $stateFiles $d
        foreach ($f in Get-ChildItem $bd -File) {
            $cur = Join-Path $d $f.Name
            if (-not (Test-Path $cur)) { "  MISSING $($f.Name) -> restored"; Copy-Item $f.FullName $cur; continue }
            if ((Get-FileHash $cur -Algorithm MD5).Hash -ne (Get-FileHash $f.FullName -Algorithm MD5).Hash) { "  CHANGED $($f.Name) -> restored"; Copy-Item $f.FullName $cur -Force }
        }
        foreach ($f in $now) { if (-not (Test-Path (Join-Path $bd $f.Name))) { "  NEW $($f.Name) -> removed"; Remove-Item $f.FullName -Force } }
    }
    "closed"; exit 0
}
Add-Type @"
using System;using System.Runtime.InteropServices;
public class MPX { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
[StructLayout(LayoutKind.Sequential)] public struct POINT { public int X,Y; }
[DllImport("user32.dll")] public static extern bool GetClipCursor(out RECT r);
[DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
[DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint f);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid); }
"@
function Clip-Confined { $cl = New-Object MPX+RECT; [void][MPX]::GetClipCursor([ref]$cl); return ((($cl.R - $cl.L) -le 704) -and (($cl.B - $cl.T) -le 544)) }
function Safe-Click([int]$ux, [int]$uy, $gp) {
    for ($try = 0; $try -lt 4; $try++) {
        # wait for a fresh confined window: see it released (or 1.5 s of steady confinement), then confined
        $sw = [Diagnostics.Stopwatch]::StartNew(); $sawFree = $false; $conf = $false
        while ($sw.ElapsedMilliseconds -lt 6000) {
            $c = Clip-Confined
            if (-not $c) { $sawFree = $true } elseif ($sawFree -or $sw.ElapsedMilliseconds -gt 2500) { $conf = $true; break }
            Start-Sleep -Milliseconds 20
        }
        if ($conf) { $sx = $ux; $sy = $uy } else { $o = UI-ToScreen $ux $uy; $sx = $o[0]; $sy = $o[1] }
        $pt = New-Object MPX+POINT; $pt.X = $sx; $pt.Y = $sy
        $w = [MPX]::GetAncestor([MPX]::WindowFromPoint($pt), 2); $wp = [uint32]0; [void][MPX]::GetWindowThreadProcessId($w, [ref]$wp)
        if ($wp -ne $gp.Id) { return "REFUSED click UI ($ux,$uy) -> screen ($sx,$sy): the window there belongs to pid $wp, not the game $($gp.Id)" }
        [Inp]::SetCursorPos($sx, $sy) | Out-Null; Start-Sleep -Milliseconds 150
        if ((Clip-Confined) -ne $conf) { continue }
        [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 70; [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 60
        $still = ((Clip-Confined) -eq $conf)
        return "clicked UI ($ux,$uy) screen ($sx,$sy) $(if ($conf) { 'confined' } else { 'free' }) try $try sawFree=$sawFree stable=$still"
    }
    return "REFUSED: the cursor regime kept flipping"
}
$proc = Get-GamePid
if (-not $proc -or -not (Test-ProcInDir $proc $G)) { "instance $Inst not running"; exit 1 }
$al = Get-Process | Where-Object { $_.MainWindowTitle -match 'Windows Security Alert|Windows Defender Firewall' }
if ($al) { "FIREWALL PROMPT PRESENT: '$($al.MainWindowTitle)' pid $($al.Id) - not touching it" }
if ($Click -or $Key -or $Type -or $Shot) { $ok = Force-Foreground $proc.MainWindowHandle; if (-not $ok -or ([Fg]::GetForegroundWindow() -ne $proc.MainWindowHandle)) { "focus FAILED for $Inst - no input sent"; exit 1 }; Start-Sleep -Milliseconds 300; Init-CursorMap | Out-Null }
if ($Click) { foreach ($c in ($Click -split ";")) { $xy = $c -split ","; $r = Safe-Click ([int]$xy[0]) ([int]$xy[1]) $proc; "[$Inst] $r"; if ($r -notmatch "^clicked") { exit 1 }; Start-Sleep -Milliseconds $Settle } }
if ($Key) { foreach ($k in ($Key -split ",")) { Send-Key $VK[$k]; Start-Sleep -Milliseconds 300 }; Start-Sleep -Milliseconds $Settle; "[$Inst] key $Key" }
if ($Type) {
    foreach ($ch in $Type.ToCharArray()) {
        $vk = if ($ch -eq '.') { 0xBE } elseif ($ch -eq ' ') { 0x20 } else { [byte][char]([string]$ch).ToUpper() }
        Send-Key ([byte]$vk) 50; Start-Sleep -Milliseconds 120
    }
    Start-Sleep -Milliseconds $Settle; "[$Inst] typed '$Type'"
}
if ($Shot) {
    Start-Sleep -Milliseconds 300
    if ($Full) { Add-Type -AssemblyName System.Drawing; $bmp = New-Object Drawing.Bitmap 3440, 1440; $gr = [Drawing.Graphics]::FromImage($bmp); $gr.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $small = New-Object Drawing.Bitmap $bmp, 1147, 480; $small.Save("$Out\$Shot.png") }
    else { Capture-UI (Join-Path $Out "$Shot.png") | Out-Null }
    "shot $Out\$Shot.png"
}
if ($State -or $Click -or $Key) {
    $a = @("-ExecutionPolicy","Bypass","-File","C:\Users\james\i76-map\shell\tools\shellstate.ps1","-ProcessId",$proc.Id,"-Once"); if ($Buttons) { $a += "-Buttons" }
    & powershell @a 2>$null | Select-Object -Skip 1 | ForEach-Object { "[$Inst] " + ($_ -replace "\s+", " ") }
}




