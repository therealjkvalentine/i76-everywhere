<#
  hlcost-run.ps1 - headlook-cost lane 2026-10-25 (i76-everywhere docs\records\HEADLOOK-COST-2026-10-25.md).
  Gate row 9's T05 route (t05-hl.ps1 = t05-route-fps.ps1 + launcher args + a 1 Hz CPU / FT sampler) under head-look conditions on the test copy.

    hlcost-run.ps1 -Conds a,b,c,d,f,e_pt -Reps 2 [-Reverse] [-Tag run1]

  Conditions (opentrack = the owner's install, started by this script, stopped by this script):
    a   no opentrack, launcher -NoHeadTrack                      (baseline)
    b   opentrack running + tracking (game detection), launcher -NoHeadTrack   (no head-look layer)
    c   opentrack running, launcher attaches, layer ANALOG       (the owner's default)
    d   opentrack running, launcher attaches, layer DIGITAL
    e_pt / e_aruco   as b but the profile's tracker swapped (a COPY of default.ini put in place, the original restored)
    f   no opentrack; ftsim.ps1 plays FT_SharedMem (moving head); the layer (ANALOG) started by this script as the launcher does; launcher -NoHeadTrack
    f_dig  as f, DIGITAL
    g_*  c with opentrack's priority / affinity changed after its start (see $Conds)
  Console protocol: CONSOLE-LOCK.md (.fps-lock + .console-owner, queue line, idle >= 120 s, no foreign game), batches of <= 6 boots, >= 30 s between.
#>
param([string[]]$Conds = @('a','b','c','d','f','e_pt'), [int]$Reps = 2, [switch]$Reverse, [string]$Tag = 'run', [int]$IdleSec = 120, [int]$WaitMin = 240)
$ErrorActionPreference = 'Continue'
$lab = 'C:\Users\james\i76-uncap-lab'; $root = "$lab\test-gold"; $g = "$root\Interstate 76"; $here = $PSScriptRoot
$ot = 'C:\Program Files (x86)\opentrack\opentrack.exe'
$docs = [Environment]::GetFolderPath('MyDocuments'); $ini = "$docs\opentrack-2.3\default.ini"
$out = Join-Path $here ("out-{0}-{1:yyyyMMdd-HHmmss}" -f $Tag, (Get-Date)); New-Item -ItemType Directory -Force $out | Out-Null
$LogFile = "$out\run.txt"
function Log([string]$m) { $l = "{0:HH:mm:ss} {1}" -f (Get-Date), $m; Add-Content $LogFile $l; Write-Host $l }
$Conds = @($Conds | ForEach-Object { "$_" -split ',' } | Where-Object { $_ })
$camName = 'Insta360 Link 2C Pro [8_2bae1f2c_0_0000]'
# cond table: ot = start opentrack; ini = tracker swap; args = launcher args; layer = ANALOG|DIGITAL started here (f only); sim = ftsim; prio / aff = applied to opentrack after start
$Cnd = @{
  a      = @{ ot = $false; args = '-NoHeadTrack' }
  a_ns   = @{ ot = $false; args = '-NoHeadTrack'; ns = $true }
  b      = @{ ot = $true;  args = '-NoHeadTrack' }
  c      = @{ ot = $true;  args = '-HeadLookMode ANALOG' }
  d      = @{ ot = $true;  args = '-HeadLookMode DIGITAL' }
  e_pt   = @{ ot = $true;  ini = 'pt';    args = '-NoHeadTrack' }
  e_aruco= @{ ot = $true;  ini = 'aruco'; args = '-NoHeadTrack' }
  f      = @{ ot = $false; args = '-NoHeadTrack'; layer = 'ANALOG';  sim = $true }
  f_dig  = @{ ot = $false; args = '-NoHeadTrack'; layer = 'DIGITAL'; sim = $true }
  g_bn   = @{ ot = $true;  args = '-HeadLookMode ANALOG'; prio = 'BelowNormal' }
  g_idle = @{ ot = $true;  args = '-HeadLookMode ANALOG'; prio = 'Idle' }
  g_aff  = @{ ot = $true;  args = '-HeadLookMode ANALOG'; prio = 'BelowNormal'; aff = 0xF0 }
  g_aff_b= @{ ot = $true;  args = '-NoHeadTrack'; prio = 'BelowNormal'; aff = 0xF0 }
  g_idle_b= @{ ot = $true;  args = '-NoHeadTrack'; prio = 'Idle' }
  b_idle = @{ ot = $true;  args = '-NoHeadTrack'; nodet = $true }
  c_self = @{ ot = $true;  args = '-NoHeadTrack'; layer = 'ANALOG'; script = 'i76-opentrack-headlook.ahk' }
  c_fix  = @{ ot = $true;  args = '-NoHeadTrack'; layer = 'ANALOG'; script = 'i76-opentrack-headlook-fix.ahk' }
  f_fix  = @{ ot = $false; args = '-NoHeadTrack'; layer = 'ANALOG'; script = 'i76-opentrack-headlook-fix.ahk'; sim = $true }
  b_fps1 = @{ ot = $true;  args = '-NoHeadTrack'; fps = 1 }
  b_fps3 = @{ ot = $true;  args = '-NoHeadTrack'; fps = 3 }
  b_fps0 = @{ ot = $true;  args = '-NoHeadTrack'; fps = 0 }
  b_thr1 = @{ ot = $true;  args = '-NoHeadTrack'; thr = 1 }
  g_bn_b = @{ ot = $true;  args = '-NoHeadTrack'; prio = 'BelowNormal' }
}
foreach ($c in $Conds) { if (-not $Cnd.ContainsKey($c)) { throw "unknown cond $c" } }

Add-Type @'
using System; using System.Runtime.InteropServices;
public static class HlIdle { [StructLayout(LayoutKind.Sequential)] struct LII { public uint cb; public uint t; } [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p);
 public static uint Ms() { LII l = new LII(); l.cb = 8; GetLastInputInfo(ref l); return (uint)Environment.TickCount - l.t; } }
'@ -ErrorAction SilentlyContinue
$FpsLock = "$lab\.fps-lock"; $Queue = "$lab\.fps-queue"; $Owner = "$lab\.console-owner"; $Mark = "headlook-cost lane pid $PID"
function Live-Games { @(Get-Process | Where-Object { ($_.ProcessName -like 'i76*' -or $_.ProcessName -like 'nitro*') -and $_.ProcessName -notmatch 'wheel' -and -not ($_.ProcessName -like 'nitro*' -and $_.Threads.Count -le 1) }) }
function Drop-Queue { if (Test-Path $Queue) { $keep = @(Get-Content $Queue -EA SilentlyContinue | Where-Object { $_.Trim() -and $_ -notmatch 'headlook-cost' }); if ($keep.Count) { Set-Content $Queue $keep } else { Remove-Item $Queue -Force -EA SilentlyContinue } } }
$script:lastRelease = $null; $script:held = $false
function Take-Console {
    $sw = [Diagnostics.Stopwatch]::StartNew(); $lastw = ''
    while ($true) {
        if ($sw.Elapsed.TotalMinutes -gt $WaitMin) { Log "gave up waiting for the console"; return $false }
        if ($script:lastRelease -and ((Get-Date) - $script:lastRelease).TotalSeconds -lt 35) { Start-Sleep 5; continue }
        $qt = if (Test-Path $Queue) { Get-Content $Queue -Raw -EA SilentlyContinue } else { '' }
        if ("$qt" -notmatch 'headlook-cost') { Add-Content $Queue "$Mark queued $(Get-Date -Format s)"; Log 'queued in .fps-queue' }
        $ahead = @(); foreach ($ln in @("$qt" -split "`r?`n" | Where-Object { $_.Trim() })) {
            if ($ln -match 'headlook-cost') { break }
            $ts = [regex]::Matches($ln, '\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d') | Select-Object -Last 1
            $age = if ($ts) { ((Get-Date) - [datetime]$ts.Value).TotalHours } else { 0 }
            if ($age -lt 2) { $ahead += $ln } }
        if ($ahead.Count) {
            $freeNow = -not (Test-Path $FpsLock) -and -not (Test-Path $Owner) -and -not (Live-Games).Count
            if ($freeNow) { if (-not $script:freeSince) { $script:freeSince = Get-Date } } else { $script:freeSince = $null }
            if (-not ($freeNow -and ((Get-Date) - $script:freeSince).TotalSeconds -ge 90)) { if ($lastw -ne 'q') { Log "waiting: queued behind $($ahead[0])"; $lastw = 'q' }; Start-Sleep 10; continue }
            Log 'console free for 90 s with older lines queued: those lanes are not waiting in order, taking it'
        }
        if (Test-Path $Owner) { if ($lastw -ne 'o') { Log "waiting: .console-owner held ($(Get-Content $Owner -Raw -EA SilentlyContinue))"; $lastw = 'o' }; Start-Sleep 30; continue }
        if (Test-Path $FpsLock) { if ($lastw -ne 'l') { Log "waiting: .fps-lock held ($(Get-Content $FpsLock -Raw -EA SilentlyContinue))"; $lastw = 'l' }; Start-Sleep 30; continue }
        $fg = Live-Games; if ($fg.Count) { if ($lastw -ne 'g') { Log "waiting: a game runs ($(($fg | % { "$($_.Id) $($_.Path)" }) -join '; '))"; $lastw = 'g' }; Start-Sleep 30; continue }
        $idle = [HlIdle]::Ms() / 1000
        if ($idle -lt $IdleSec) { if ($lastw -ne 'i') { Log ("waiting: console input {0:N0} s ago (someone may be at the PC)" -f $idle); $lastw = 'i' }; Start-Sleep 20; continue }
        try { $fs = [IO.File]::Open($FpsLock, 'CreateNew', 'Write'); $w = New-Object IO.StreamWriter($fs); $w.Write("$Mark $(Get-Date -Format s)"); $w.Close() } catch { Start-Sleep 30; continue }
        $q = (query session 2>$null) -join "`n"; $why = ''
        if ((Live-Games).Count) { $why = 'a game runs' } elseif ($q -notmatch '>console\s+\S+\s+\d+\s+Active') { $why = 'console session not active' } elseif ($q -match 'rdp-tcp#\d+\s+\S+\s+\d+\s+Active') { $why = 'RDP active' }
        if ($why) { Remove-Item $FpsLock -Force; if ($why -ne $lastw) { Log "lock taken and released: $why"; $lastw = $why }; Start-Sleep 30; continue }
        try { New-Item -ItemType File -Path $Owner -Value "$Mark $(Get-Date -Format s)" -EA Stop | Out-Null } catch { Remove-Item $FpsLock -Force; Start-Sleep 30; continue }
        Drop-Queue; $script:held = $true; Log 'console taken'; return $true
    }
}
function Release-Console {
    if ((Test-Path $FpsLock) -and ((Get-Content $FpsLock -Raw -EA SilentlyContinue) -match 'headlook-cost')) { Remove-Item $FpsLock -Force }
    if ((Test-Path $Owner) -and ((Get-Content $Owner -Raw -EA SilentlyContinue) -match 'headlook-cost')) { Remove-Item $Owner -Force }
    Drop-Queue; Remove-Item "$g\.console-test.lock" -Force -EA SilentlyContinue
    for ($i = 0; $i -lt 3; $i++) { try { & "$lab\tools\unmute-persisted.ps1" -Exe "$g\i76.exe" 2>&1 | Out-Null; break } catch { Start-Sleep 3 } }
    $script:held = $false; $script:lastRelease = Get-Date; Log 'console released'
}
# ---- state to restore -----------------------------------------------------------------------------------------------
$iniOrig = "$out\default.ini.orig"; Copy-Item $ini $iniOrig -Force; $iniHash = (Get-FileHash $ini -Algorithm MD5).Hash
$regKey = 'HKCU:\Software\opentrack-2.3\OrganizationDefaults'; $regBefore = (Get-ItemProperty $regKey | Out-String)
Log "opentrack default.ini md5 $iniHash backed up to $iniOrig"
$glob = "$env:APPDATA\dgVoodoo\dgVoodoo.conf"; $globHidden = "$glob.hidden-by-gate"; $hid = $false
function Restore-All {
    if ($hid -and (Test-Path $globHidden) -and -not (Test-Path $glob)) { Rename-Item $globHidden 'dgVoodoo.conf' -Force; $script:hid = $false; Log 'global dgVoodoo.conf put back' }
    Copy-Item $iniOrig $ini -Force
    $h = (Get-FileHash $ini -Algorithm MD5).Hash; Log "default.ini restored, md5 $h ($(if ($h -eq $iniHash) { 'matches' } else { 'DIFFERS' }))"
}
function Set-Tracker([string]$t) {
    $x = Get-Content $iniOrig -Raw
    $x = $x -replace 'tracker-dll=neuralnet', "tracker-dll=$t"
    if ($t -eq 'pt') { $x = $x -replace '(?m)^\[tracker-pt\]\r?\ncamera-name=.*$', "[tracker-pt]`r`ncamera-name=$camName" }
    if ($t -eq 'aruco') { $x += "`r`n[tracker-aruco]`r`ncamera-name=$camName`r`n" }
    Set-Content $ini $x -Encoding ASCII
}
if (-not (Test-Path "$lab\.display-hold")) { Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"$lab\tools\keep-display.ps1",'-Hours','3','-Tag','headlook-cost' -WindowStyle Hidden -EA SilentlyContinue | Out-Null }
if (Test-Path "$lab\.display-hold") { Log "display hold: $(Get-Content "$lab\.display-hold" -Raw)" }
$env:LAB_CURSOR_FREE = '1'; $env:I76_MUTE = '1'
$order = @(); for ($r = 1; $r -le $Reps; $r++) { $cs = if ($Reverse -and ($r % 2 -eq 0)) { @($Conds[($Conds.Count - 1)..0]) } else { $Conds }; foreach ($c in $cs) { $order += [pscustomobject]@{ r = $r; c = $c } } }
Log ("plan: " + (($order | % { "$($_.c)#$($_.r)" }) -join ' '))
$inBatch = 0; $rows = @()
try {
    foreach ($job in $order) {
        if (-not $script:held -or $inBatch -ge 6) { if ($script:held) { Restore-All; Release-Console }; if (-not (Take-Console)) { break }; $inBatch = 0
            if (-not (Test-Path $globHidden) -and (Test-Path $glob)) { Rename-Item $glob (Split-Path $globHidden -Leaf); $hid = $true; Log 'global dgVoodoo.conf hidden for the batch' } }
        $spec = $Cnd[$job.c]; $name = "$($job.c)-r$($job.r)"; Log "=== $name ($($spec.args)) ==="
        $otp = $null; $sim = $null; $lay = $null; $stop = "$out\$name.simstop"
        try {
            if ((Get-Process opentrack -EA SilentlyContinue) -or (Live-Games).Count) { Log '  opentrack or a game is running that this script did not start - skipping'; continue }
            try { [IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem').Dispose(); Log '  FT_SharedMem exists before start (a reader holds it?)' } catch [IO.FileNotFoundException] {}
            if ($spec.nodet) { Set-ItemProperty $regKey -Name 'executable-detector-enabled' -Value 'false'; Log '  game detection switched OFF for this run (opentrack runs, never starts tracking)' }
            if ($spec.ini) { Set-Tracker $spec.ini; Log "  profile tracker -> $($spec.ini)" } elseif ($null -ne $spec.fps -or $null -ne $spec.thr) {
                $x = Get-Content $iniOrig -Raw
                if ($null -ne $spec.fps) { $x = $x -replace 'force-fps=\d+', "force-fps=$($spec.fps)" }
                if ($null -ne $spec.thr) { $x = $x -replace '(?m)^\[neuralnet-tracker\]', "[neuralnet-tracker]`r`nnum-threads=$($spec.thr)" }
                Set-Content $ini $x -Encoding ASCII; Log "  profile edited: fps=$($spec.fps) threads=$($spec.thr)"
            } else { Copy-Item $iniOrig $ini -Force }
            if ($spec.ot) {
                $otp = Start-Process -FilePath $ot -WindowStyle Minimized -PassThru; Start-Sleep -Seconds 6
                if ($spec.prio) { try { $otp.PriorityClass = $spec.prio } catch {} }
                if ($spec.aff) { try { $otp.ProcessorAffinity = [IntPtr]$spec.aff } catch {} }
                $otp.Refresh(); Log "  opentrack pid $($otp.Id) started, priority $($otp.PriorityClass), affinity 0x$('{0:X}' -f [int64]$otp.ProcessorAffinity)"
            }
            if ($spec.sim) {
                $sim = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$heretsim.ps1`"",'-StopFile',"`"$stop`"" -WindowStyle Hidden -PassThru
                Start-Sleep -Seconds 2
            }
            if ($spec.layer) {
                $scr = if ($spec.script) { $spec.script } else { 'i76-opentrack-headlook.ahk' }
                $env:I76_HEADLOOK_MODE = $spec.layer
                $lay = Start-Process "$g\_ahk\AutoHotkeyU32.exe" -ArgumentList "`"$g\_ahk\$scr`"" -WorkingDirectory "$g\_ahk" -PassThru
                Remove-Item Env:\I76_HEADLOOK_MODE -EA SilentlyContinue
                Log "  layer pid $($lay.Id) ($($spec.layer), $scr)$(if ($sim) { ', ftsim pid ' + $sim.Id })"
            }
            if ($spec.ns) { $env:HLCOST_NOSAMPLE = '1' } else { Remove-Item Env:HLCOST_NOSAMPLE -EA SilentlyContinue }
            $res = & powershell -NoProfile -ExecutionPolicy Bypass -File "$here\t05-hl.ps1" -GameDir $g -Launcher "$root\PLAY.bat" -OutDir $out -LaunchArgsText $spec.args 2>&1
            $res | Set-Content "$out\$name.txt"
            $res | Where-Object { "$_" -match '^t05-route|^t05-hl' } | ForEach-Object { Log "  $_" }
        } finally {
            if ($lay) { Stop-Process -Id $lay.Id -Force -EA SilentlyContinue }
            if ($sim) { 'x' | Set-Content $stop; [void]$sim.WaitForExit(5000); if (-not $sim.HasExited) { Stop-Process -Id $sim.Id -Force -EA SilentlyContinue } }
            Get-Process i76, i76wheel -EA SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith("$g\", [StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { Stop-Process -Id $_.Id -Force; Log "  stopped leftover $($_.ProcessName)" }
            # helpers the launcher started from this folder (head-look layer, other AHK layers, autostart helper)
            Get-CimInstance Win32_Process -Filter "Name='AutoHotkeyU32.exe'" -EA SilentlyContinue | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith("$g\", [StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue; Log "  stopped AHK $($_.ProcessId)" }
            if ($otp -and -not $otp.HasExited) { Stop-Process -Id $otp.Id -Force -EA SilentlyContinue; Log "  opentrack $($otp.Id) stopped" }
            Copy-Item $iniOrig $ini -Force
            if ($spec.nodet) { Set-ItemProperty $regKey -Name 'executable-detector-enabled' -Value 'true' }
            Start-Sleep -Seconds 4
        }
        $inBatch++
    }
} finally {
    Restore-All
    if ($script:held) { Release-Console }
    Remove-Item Env:LAB_CURSOR_FREE, Env:I76_MUTE -EA SilentlyContinue
    $regAfter = (Get-ItemProperty $regKey | Out-String); Log "opentrack registry settings $(if ($regAfter -eq $regBefore) { 'unchanged' } else { 'CHANGED (see run.txt)' })"
    if ($regAfter -ne $regBefore) { Add-Content $LogFile "BEFORE:`n$regBefore`nAFTER:`n$regAfter" }
    Log "output under $out"
}

