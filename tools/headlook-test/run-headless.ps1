<#
  Head-look layer, headless test: no game, no opentrack, no camera.

  It plays opentrack's part itself (creates FT_SharedMem and writes yaw / pitch the way the freetrack
  protocol does), makes a key-logger window the foreground "game" (I76_HEADLOOK_EXE=keylog.exe), plays
  the user's part with keybd_event (a held glance arrow, Ctrl+Alt+H), and checks the result from two
  independent records: the key logger (the OS's logical key state, 2 ms poll) and the layer's own trace.

  It takes the foreground for ~25 s and types arrow keys into the key-logger window: run it under the
  console lock (CONSOLE-LOCK.md), never while a game or opentrack runs (it refuses both).

    run-headless.ps1 [-Ahk <AutoHotkeyU32.exe>] [-Script <i76-opentrack-headlook.ahk>] [-Map <input.map>]
  Exit 0 = every check passed. Output: builds-style folder under $env:TEMP unless -Out.
#>
param(
    [string]$Ahk = (Join-Path $env:USERPROFILE 'i76-uncap-lab\exp-polish2\Interstate 76\_ahk\AutoHotkeyU32.exe'),
    [string]$Script = (Join-Path $PSScriptRoot '..\..\i76-opentrack-headlook.ahk'),
    [string]$Map = (Join-Path $env:USERPROFILE 'i76-uncap-lab\rc-twin-20261024\Interstate 76\input.map'),
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
if (Get-Process opentrack -ErrorAction SilentlyContinue) { throw 'opentrack runs - it owns FT_SharedMem; not running' }
if (Get-Process i76 -ErrorAction SilentlyContinue) { throw 'a game runs - not running' }
try { [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem').Dispose(); throw 'FT_SharedMem exists (a reader holds it?) - not running' } catch [System.IO.FileNotFoundException] { }

if (-not $Out) { $Out = Join-Path $env:TEMP ("i76-headlook-test-{0:yyyyMMdd-HHmmss}" -f (Get-Date)) }
$work = Join-Path $Out 'game'; New-Item -ItemType Directory -Force (Join-Path $work '_ahk') | Out-Null
Copy-Item $Script (Join-Path $work '_ahk\i76-opentrack-headlook.ahk') -Force
Copy-Item $Map (Join-Path $work 'input.map') -Force
Copy-Item $Ahk (Join-Path $work '_ahk\keylog.exe') -Force
$keyLog = Join-Path $Out 'keylog.txt'; $trace = Join-Path $Out 'trace.txt'

Add-Type -Name Kb -Namespace HlTest -MemberDefinition @'
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, System.UIntPtr extra);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("kernel32.dll")] public static extern uint GetTickCount();
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h, out uint pid);
'@
$script:klPid = 0; $script:blocked = 0
function Key([byte]$vk, [bool]$down) {
    # a key-DOWN goes out only while the key-logger window is in front (a shared desktop must never get typed into);
    # key-ups always go out
    if ($down -and $script:klPid) {
        $fp = 0; [void][HlTest.Kb]::GetWindowThreadProcessId([HlTest.Kb]::GetForegroundWindow(), [ref]$fp)
        if ($fp -ne $script:klPid) { $script:blocked++; Mark "BLOCKED key $vk (foreground pid $fp)"; return }
    }
    $f = 0; if ($vk -ge 0x25 -and $vk -le 0x28) { $f = 1 }; if (-not $down) { $f = $f -bor 2 }
    [HlTest.Kb]::keybd_event($vk, 0, $f, [UIntPtr]::Zero)
}
$events = New-Object System.Collections.ArrayList
function Mark($s) { [void]$events.Add(("{0} {1}" -f [HlTest.Kb]::GetTickCount(), $s)) }

# ---- opentrack's part ---------------------------------------------------------------------------
$mmf = [System.IO.MemoryMappedFiles.MemoryMappedFile]::CreateNew('FT_SharedMem', 256)
$acc = $mmf.CreateViewAccessor(0, 256)
$script:dataId = 0
function Head([double]$yaw, [double]$pitch) {   # freetrack radians, BEFORE the layer's inversion
    $script:dataId++
    $acc.Write(12, [single]$yaw); $acc.Write(16, [single]$pitch); $acc.Write(0, [uint32]$script:dataId)
    Mark ("head yaw {0} pitch {1}" -f $yaw, $pitch)
}
function Hold([int]$ms) {   # keep the "tracker" publishing while we wait
    $end = (Get-Date).AddMilliseconds($ms)
    while ((Get-Date) -lt $end) { $script:dataId++; $acc.Write(0, [uint32]$script:dataId); Start-Sleep -Milliseconds 20 }
}

$kl = $null; $hl = $null
try {
    Head 0 0
    $kl = Start-Process (Join-Path $work '_ahk\keylog.exe') -ArgumentList "`"$PSScriptRoot\keylog.ahk`"", "`"$keyLog`"" -PassThru
    $script:klPid = $kl.Id
    Start-Sleep -Milliseconds 1200
    $env:I76_HEADLOOK_EXE = 'keylog.exe'; $env:I76_HEADLOOK_TRACE = $trace; $env:I76_HEADLOOK_BEEP = '0'; $env:I76_HEADLOOK_MODE = 'DIGITAL'
    $hl = Start-Process $Ahk -ArgumentList "`"$(Join-Path $work '_ahk\i76-opentrack-headlook.ahk')`"" -PassThru
    Remove-Item Env:\I76_HEADLOOK_EXE, Env:\I76_HEADLOOK_TRACE, Env:\I76_HEADLOOK_BEEP, Env:\I76_HEADLOOK_MODE
    Start-Sleep -Milliseconds 800
    $kl.Refresh()
    $null = (New-Object -ComObject WScript.Shell).AppActivate($kl.Id)
    Start-Sleep -Milliseconds 300
    [void][HlTest.Kb]::SetForegroundWindow($kl.MainWindowHandle)
    Start-Sleep -Milliseconds 500
    Mark "foreground $([HlTest.Kb]::GetForegroundWindow()) keylog $($kl.MainWindowHandle)"

    # A. DIGITAL: head right -> Right held
    Head -0.40 0; Hold 600
    # B. the user holds Left (a glance out of the left window): the layer must let go of Right
    Mark 'user Left down'; Key 0x25 $true; Hold 700
    Mark 'user Left up'; Key 0x25 $false; Hold 700
    # C. head back to centre, then a nod down (RC map: look down = Up)
    Head 0 0; Hold 400
    Head 0 0.20; Hold 500
    Head 0 0; Hold 400
    # D. the middle mouse button (pilot_glance_left) also overrides
    Head -0.40 0; Hold 500
    Mark 'user MButton down'
    Add-Type -Name Ms -Namespace HlTest -MemberDefinition '[DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, System.UIntPtr e);' -ErrorAction SilentlyContinue
    $fp = 0; [void][HlTest.Kb]::GetWindowThreadProcessId([HlTest.Kb]::GetForegroundWindow(), [ref]$fp)
    if ($fp -eq $script:klPid) { [HlTest.Ms]::mouse_event(0x20, 0, 0, 0, [UIntPtr]::Zero) } else { $script:blocked++; Mark 'BLOCKED MButton' }
    Hold 500
    Mark 'user MButton up'; [HlTest.Ms]::mouse_event(0x40, 0, 0, 0, [UIntPtr]::Zero); Hold 600
    Head 0 0; Hold 300
    # E. Ctrl+Alt+H: DIGITAL -> OFF (head right must do nothing) -> ANALOG (keylog.exe is not the game:
    #    the sites do not verify, so it must act DIGITAL and say so)
    foreach ($n in 1..2) {
        Mark "user Ctrl+Alt+H #$n"
        Key 0x11 $true; Key 0x12 $true; Key 0x48 $true; Start-Sleep -Milliseconds 60; Key 0x48 $false; Key 0x12 $false; Key 0x11 $false
        Hold 500
        Head -0.40 0; Hold 600
        Head 0 0; Hold 400
    }
} finally {
    if ($hl -and -not $hl.HasExited) { Stop-Process -Id $hl.Id -Force }
    foreach ($vk in 0x25..0x28) { Key $vk $false }
    [HlTest.Kb]::keybd_event(0x11, 0, 2, [UIntPtr]::Zero); [HlTest.Kb]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
    if ($kl -and -not $kl.HasExited) { Stop-Process -Id $kl.Id -Force }
    $acc.Dispose(); $mmf.Dispose()
}

# ---- one timeline, relative ms --------------------------------------------------------------------
$rows = @()
foreach ($l in $events) { $p = $l -split ' ', 2; $rows += [pscustomobject]@{ t = [int64]$p[0]; src = 'test '; s = $p[1] } }
if (Test-Path $keyLog) { foreach ($l in Get-Content $keyLog | Where-Object { $_ -match '^\d+ ' }) { $p = $l -split ' ', 2; $rows += [pscustomobject]@{ t = [int64]$p[0]; src = 'OS   '; s = $p[1] } } }
if (Test-Path $trace)  { foreach ($l in Get-Content $trace | Where-Object { $_ -match '^\d+ ' })  { $p = $l -split ' ', 2; $rows += [pscustomobject]@{ t = [int64]$p[0]; src = 'layer'; s = $p[1] } } }
$rows = $rows | Sort-Object t
$t0 = ($rows | Select-Object -First 1).t
$lines = $rows | ForEach-Object { "{0,6} {1} {2}" -f ($_.t - $t0), $_.src, $_.s }
$lines | Set-Content (Join-Path $Out 'timeline.txt')
$lines

# ---- checks -----------------------------------------------------------------------------------------
function T($what) { ($rows | Where-Object { $_.s -eq $what } | Select-Object -First 1).t }
function After($t, $src, $pat) { ($rows | Where-Object { $_.t -ge $t -and $_.src -eq $src -and $_.s -match $pat } | Select-Object -First 1) }
$fails = 0
function Check($name, $ok, $detail) { $script:fails += [int](-not $ok); $mark = if ($ok) { 'ok  ' } else { 'FAIL' }; "{0}  {1}  {2}" -f $mark, $name, $detail }
"`nchecks:"
$tr = Get-Content $trace -ErrorAction SilentlyContinue
Check 'keys resolved from input.map (RC: down=Up)' ([bool]($tr -match 'glance keys \(input.map\): down=Up up=Down')) ''
$ld = T 'user Left down'; $lu = T 'user Left up'
$r1 = After 0 'OS   ' '^Right down'
Check 'A head right -> Right held (OS)' ([bool]$r1 -and $r1.t -lt $ld) ''
$ru = After $ld 'OS   ' '^Right up'
Check 'B user Left -> layer releases Right' ([bool]$ru -and $ru.t -lt $lu -and ($ru.t - $ld) -lt 100) ("{0} ms after Left down" -f ($ru.t - $ld))
$ov = After $ld 'layer' '^override on'
Check 'B override announced in trace' ([bool]$ov) ''
$rd2 = After $lu 'OS   ' '^Right down'
Check 'B release -> Right again after the 150 ms ease' ([bool]$rd2 -and ($rd2.t - $lu) -ge 140 -and ($rd2.t - $lu) -lt 400) ("{0} ms after Left up" -f ($rd2.t - $lu))
$between = $rows | Where-Object { $_.t -gt $ld -and $_.t -lt $lu -and $_.src -eq 'layer' -and $_.s -match ' down$' }
Check 'B no layer key-down while the user holds Left' (-not $between) ''
$nod = T 'head yaw 0 pitch 0.2'
$up = After $nod 'OS   ' '^Up down'
$dn = $rows | Where-Object { $_.t -ge $nod -and $_.t -lt ($nod + 500) -and $_.src -eq 'OS   ' -and $_.s -match '^Down down' }
Check 'C nod down sends Up (pilot_glance_down on this map), not Down' ([bool]$up -and -not $dn) ''
$md = T 'user MButton down'; $mu = T 'user MButton up'
$ru3 = After $md 'OS   ' '^Right up'
Check 'D middle button overrides' ([bool]$ru3 -and $ru3.t -lt $mu) ''
$h1 = T 'user Ctrl+Alt+H #1'; $h2 = T 'user Ctrl+Alt+H #2'
Check 'E Ctrl+Alt+H -> OFF' ([bool](After $h1 'layer' '^mode OFF')) ''
$offKeys = $rows | Where-Object { $_.t -gt $h1 -and $_.t -lt $h2 -and $_.src -eq 'OS   ' -and $_.s -match ' down$' }
Check 'E OFF: head right sends nothing' (-not $offKeys) ''
Check 'E Ctrl+Alt+H -> ANALOG' ([bool](After $h2 'layer' '^mode ANALOG')) ''
Check 'E toasts shown for each change' (@($rows | Where-Object { $_.src -eq 'layer' -and $_.s -match '^toast' }).Count -ge 3) ''
Check 'E ANALOG on a non-game exe: sites refused, acts DIGITAL' ([bool](After $h2 'layer' 'did not verify') -and [bool](After $h2 'OS   ' '^Right down')) ''
Check 'no key blocked by the foreground guard' ($script:blocked -eq 0) "$($script:blocked) blocked"
"`n$(if ($fails) { "FAIL $fails" } else { 'PASS' })  (output $Out)"
exit $fails
