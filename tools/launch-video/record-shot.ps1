<#
  record-shot.ps1 - launch-video lane: record ONE game shot headless at 1920x1080 / 60 fps (docs/LAUNCH-VIDEO-2026-10-25.md).

    .\record-shot.ps1 -Shot route-all            # a shot from shots.psd1
    .\record-shot.ps1 -Shot route-all -DryRun    # print env / paths, touch nothing

  What one run does:
   1. waits for the lab console per CONSOLE-LOCK.md (no i76 / nitro running, .console-owner + .fps-lock free, .fps-queue order),
      takes both, starts keep-display if nobody holds the display;
   2. boots the launch-video twin (lab launchvid-20261025, a twin of test-gold; dgVoodoo.lv1080.conf = windowed, 3840x2160 Glide
      supersample) straight into the shot's mission through autotest\proxy-run.ps1 (-KeepInstalledDll -Set stock: only the env
      below; I76_MUTE + the per-pid mute watch + own I76_SHM_SUFFIX come from proxy-run);
      env = the preset's keys - Strip + Keys + I76_TELEMETRY=<port> + I76_FPS_LOG=2 + I76_NO_MINIMIZE=1 (+ I76_ASPECT 1920x1080 and
      I76_U32X_MENU_ASPECT 1920:1080 for every preset except stock: the stock game has no aspect key) + I76_START_POS;
      Patch20 = the GOG 20 fps limiter I76PATCH.DLL is put in place for this boot only (stock as GOG ships it);
   3. holds the window at 0,0 1920x1080 (lv-keeper.ps1), logs telemetry with the host clock (tel-udp.py), starts ffmpeg ddagrab on
      the window rect (60 fps, h264 via Media Foundation hardware), and drives: handbrake + S for Still s, then W for Drive s;
   4. writes captures\launch-video\raw\<shot>\<stamp>\ : video.mp4, tel.csv, capture.json (capture start host time, rect, env),
      boot.txt, mciproxy-run.log, summary.txt (render fps from the log windows and from telemetry, distance driven).
#>
param([Parameter(Mandatory)][string]$Shot, [switch]$DryRun, [int]$MaxWaitMin = 240, [int]$TelPort = 27760, [switch]$HaveLock)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'lv-lib.ps1')
$S = (Import-PowerShellDataFile (Join-Path $PSScriptRoot 'shots.psd1'))[$Shot]
if (-not $S) { Write-Host "no shot '$Shot' in shots.psd1" -ForegroundColor Red; exit 2 }
$T = $script:LvTwin; $Lab = $script:LvLab; $AT = "$Lab\autotest"
$FF = Get-LvFfmpeg
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Out = Join-Path $script:LvCap "raw\$Shot\$stamp"

# ---- environment
$E = [ordered]@{}
if ($S.Preset -ne 'stock') {
    $pe = (Import-PowerShellDataFile "$T\presets\$($S.Preset).psd1").Env
    foreach ($k in $pe.Keys) { $E[$k] = "$($pe[$k])" }
    $E['I76_ASPECT'] = '1920x1080'; $E['I76_U32X_MENU_ASPECT'] = '1920:1080'
}
foreach ($k in @($S.Strip)) { if ($k) { $E.Remove($k) } }
if ($S.Keys) { foreach ($k in $S.Keys.Keys) { $E[$k] = "$($S.Keys[$k])" } }
$E['I76_TELEMETRY'] = "$TelPort"; $E['I76_FPS_LOG'] = '2'; $E['I76_NO_MINIMIZE'] = '1'
if ($S.Start) { $E['I76_START_POS'] = $S.Start }
$dur = [int]$S.Still + [int]$S.Drive + 1
$WW = if ($S.W) { [int]$S.W } else { 1920 }; $WH = if ($S.H) { [int]$S.H } else { 1080 }
$Conf = if ($S.Conf) { $S.Conf } else { 'dgVoodoo.lv1080.conf' }
if ($DryRun) {
    "record-shot DRY RUN: shot=$Shot window=${WW}x${WH} conf=$Conf twin=$T mission=$($S.Mission) preset=$($S.Preset) patch20=$([bool]$S.Patch20) capture ${dur}s -> $Out"
    $E.Keys | ForEach-Object { "  $_=$($E[$_])" }
    "ffmpeg: $($FF.ffmpeg)"; exit 0
}
New-Item -ItemType Directory -Force $Out | Out-Null
($E.Keys | ForEach-Object { "$_=$($E[$_])" }) -join "`n" | Set-Content "$Out\env.txt"

if (-not $HaveLock) { if (-not (Wait-LvConsole -Tag $Shot -MaxWaitMin $MaxWaitMin)) { "NOT RUN: console" | Set-Content "$Out\summary.txt"; exit 3 } }
$holdMine = $false; $patched = $false; $keeper = $null; $tel = $null
try {
    if (-not (Test-Path "$Lab\.display-hold")) {
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$Lab\tools\keep-display.ps1`" -Hours 1 -Tag launch-video" -WindowStyle Hidden
        $holdMine = $true; Start-Sleep -Seconds 2
    }
    if ($S.Patch20) { Copy-Item "$T\I76PATCH.DLL.disabled" "$T\I76PATCH.DLL" -Force; $patched = $true }
    Copy-Item "$T\$Conf" "$T\dgVoodoo.conf" -Force
    $log = Join-Path $T 'mciproxy.log'; $logLen = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
    Get-ChildItem Env: | Where-Object { $_.Name -like 'I76*' } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    $tel = Start-Process python -ArgumentList "-I `"$PSScriptRoot\tel-udp.py`" --port $TelPort --out `"$Out\tel.csv`" --seconds 900 --stop-file `"$Out\stop`"" -WindowStyle Hidden -PassThru

    Add-Type -Namespace LvR -Name U -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L, T, R, B; }
"@ -ErrorAction SilentlyContinue
    $drive = {
        . "$AT\lib\inputlib.ps1"; . "$AT\lib\focuslib.ps1"
        $g = Get-GamePid
        $kp = Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\lv-keeper.ps1`" -GamePid $($g.Id) -W $WW -H $WH" -WindowStyle Hidden -PassThru; Set-Content "$Out\keeper.pid" $kp.Id
        function Fg { try { $g.Refresh(); [void](Force-Foreground $g.MainWindowHandle) } catch {} }
        $rect = $null
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 250; $g.Refresh(); $r = New-Object LvR.U+RECT
            if ([LvR.U]::GetWindowRect($g.MainWindowHandle, [ref]$r) -and ($r.R - $r.L) -eq $WW -and ($r.B - $r.T) -eq $WH) { $rect = $r; break }
        }
        if (-not $rect) { $r = New-Object LvR.U+RECT; [void][LvR.U]::GetWindowRect($g.MainWindowHandle, [ref]$r); Write-Host "[lv] window not ${WW}x${WH}: $($r.L),$($r.T),$($r.R),$($r.B)" -ForegroundColor Yellow; $rect = $r }
        Fg; Start-Sleep -Milliseconds 1500
        # hold the car before the capture starts so the first frame is not a lurch
        Key-Down $VK.SPACE; Key-Down $VK.S
        $w = $rect.R - $rect.L; $h = $rect.B - $rect.T
        $vf = "ddagrab=output_idx=0:framerate=60:draw_mouse=0:offset_x=$($rect.L):offset_y=$($rect.T):video_size=${w}x${h},hwdownload,format=bgra,format=nv12"
        $ffArgs = "-hide_banner -loglevel warning -y -f lavfi -i `"$vf`" -t $dur -c:v h264_mf -hw_encoding 1 -b:v 40M -maxrate 60M `"$Out\video.mp4`""
        $t0 = [DateTimeOffset]::Now.ToUnixTimeMilliseconds() / 1000.0
        $ff = Start-Process $FF.ffmpeg -ArgumentList $ffArgs -WindowStyle Hidden -PassThru -RedirectStandardError "$Out\ffmpeg.err.txt"
        @{ shot = $Shot; capture_start_host_t = $t0; rect = @($rect.L, $rect.T, $w, $h); still = $S.Still; drive = $S.Drive; preset = $S.Preset
           strip = @($S.Strip); keys = $S.Keys; patch20 = [bool]$S.Patch20; mission = $S.Mission; start = $S.Start } | ConvertTo-Json -Depth 4 | Set-Content "$Out\capture.json"
        $sw = [Diagnostics.Stopwatch]::StartNew(); $rel = $false
        while ($sw.Elapsed.TotalSeconds -lt ($S.Still + $S.Drive) -and -not $g.HasExited) {
            $t = $sw.Elapsed.TotalSeconds
            if (-not $rel -and $t -ge $S.Still) { Key-Up $VK.SPACE; Key-Up $VK.S; if ($S.Drive -gt 0) { Fg; Key-Down $VK.W }; $rel = $true }
            foreach ($st in @($S.Steer)) { if ($st -and $st.Count -eq 3) {
                $k = $VK[[string]$st[2]]
                $td = $t - $S.Still
                if ($td -ge $st[0] -and $td -lt $st[1]) { Key-Down $k } elseif ($td -ge $st[1] -and $td -lt $st[1] + 0.2) { Key-Up $k } } }
            Start-Sleep -Milliseconds 50
        }
        Key-Up $VK.W; Key-Up $VK.SPACE; Key-Up $VK.S; foreach ($st in @($S.Steer)) { if ($st -and $st.Count -eq 3) { Key-Up $VK[[string]$st[2]] } }
        [void]$ff.WaitForExit(15000)
    }
    if ($S.Opening) {
        # the mission's scripted opening (fly-in) must play: no proxy-run (it presses Esc to skip it); launch, size, capture Still s, stop
        . "$AT\lib\focuslib.ps1"
        $lock = Join-Path $T '.console-test.lock'; Set-Content $lock "launch-video record-shot $Shot pid $PID $(Get-Date -Format s)"
        $p = $null
        try {
            foreach ($k in $E.Keys) { Set-Item "Env:$k" $E[$k] }
            $env:I76_MISSION = "$($S.Mission).msn"; $env:I76_SKIP_MOVIES = '1'; $env:I76_MUTE = '1'; $env:I76MUSIC_LOG = '1'
            & "$Lab\tools\set-shm-suffix.ps1" -GameDir $T | Out-Null
            Add-Type -Name M2 -Namespace LvW2 -MemberDefinition '[DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, UIntPtr e);' -ErrorAction SilentlyContinue
            [LvW2.M2]::mouse_event(1, 5, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 200; [LvW2.M2]::mouse_event(1, -5, 0, 0, [UIntPtr]::Zero)
            $p = Start-Process (Join-Path $T 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $T -PassThru
            & "$Lab\tools\start-mute-watch.ps1" -Pid $p.Id
            $kp = Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\lv-keeper.ps1`" -GamePid $($p.Id) -W $WW -H $WH" -WindowStyle Hidden -PassThru; Set-Content "$Out\keeper.pid" $kp.Id
            $rect = $null
            for ($i = 0; $i -lt 240 -and -not $p.HasExited; $i++) {
                Start-Sleep -Milliseconds 250; $p.Refresh()
                if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
                    $r = New-Object LvR.U+RECT
                    if ([LvR.U]::GetWindowRect($p.MainWindowHandle, [ref]$r) -and ($r.R - $r.L) -eq $WW -and ($r.B - $r.T) -eq $WH) { $rect = $r; break }
                }
            }
            if ($rect) {
                [void](Force-Foreground $p.MainWindowHandle)
                $vf = "ddagrab=output_idx=0:framerate=60:draw_mouse=0:offset_x=$($rect.L):offset_y=$($rect.T):video_size=${WW}x${WH},hwdownload,format=bgra,format=nv12"
                $t0 = [DateTimeOffset]::Now.ToUnixTimeMilliseconds() / 1000.0
                $ffp = Start-Process $FF.ffmpeg -ArgumentList "-hide_banner -loglevel warning -y -f lavfi -i `"$vf`" -t $dur -c:v h264_mf -hw_encoding 1 -b:v 40M -maxrate 60M `"$Out\video.mp4`"" -WindowStyle Hidden -PassThru -RedirectStandardError "$Out\ffmpeg.err.txt"
                @{ shot = $Shot; capture_start_host_t = $t0; rect = @($rect.L, $rect.T, $WW, $WH); still = $S.Still; drive = $S.Drive; preset = $S.Preset; opening = $true
                   strip = @($S.Strip); keys = $S.Keys; patch20 = [bool]$S.Patch20; mission = $S.Mission } | ConvertTo-Json -Depth 4 | Set-Content "$Out\capture.json"
                $sw = [Diagnostics.Stopwatch]::StartNew()
                while ($sw.Elapsed.TotalSeconds -lt $dur -and -not $p.HasExited) { Start-Sleep -Milliseconds 500; if ($sw.Elapsed.TotalSeconds -lt 20) { [void](Force-Foreground $p.MainWindowHandle) } }
                [void]$ffp.WaitForExit(15000)
                "opening captured $dur s" | Set-Content "$Out\boot.txt"
            } else { "window never reached ${WW}x${WH}" | Set-Content "$Out\boot.txt" }
        } finally {
            if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force; [void]$p.WaitForExit(10000) }
            Remove-Item $lock -Force -ErrorAction SilentlyContinue
        }
    } else {
    $boot = & "$AT\proxy-run.ps1" -GameDir $T -KeepInstalledDll -Set stock -Mission $S.Mission -Hold 0 -BootTimeout 240 -Env ([hashtable]$E) -Run $drive *>&1 | Out-String
    $boot | Set-Content "$Out\boot.txt"
    }
    Start-Sleep -Seconds 2
} finally {
    Set-Content "$Out\stop" 'stop'
    if ($tel) { [void]$tel.WaitForExit(5000); if (-not $tel.HasExited) { Stop-Process -Id $tel.Id -Force -ErrorAction SilentlyContinue } }
    if (Test-Path "$Out\keeper.pid") { Stop-Process -Id ([int](Get-Content "$Out\keeper.pid")) -Force -ErrorAction SilentlyContinue }
    if ($patched) { for ($i = 0; $i -lt 20; $i++) { try { Remove-Item "$T\I76PATCH.DLL" -Force -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 500 } } }
    if (-not $HaveLock) { Exit-LvConsole }
    if ($holdMine) { Remove-Item "$Lab\.display-hold" -Force -ErrorAction SilentlyContinue }
}

# ---- summary
$new = ''; if (Test-Path $log) { $b = [IO.File]::ReadAllBytes($log); $skip = if ($b.Length -lt $logLen) { 0 } else { $logLen }; if ($b.Length -gt $skip) { $new = [Text.Encoding]::GetEncoding(28591).GetString($b, $skip, $b.Length - $skip) } }
$new | Set-Content "$Out\mciproxy-run.log"
$w = @(foreach ($m in [regex]::Matches($new, 'fps: ([0-9.]+) \((\d+) frames / ([0-9.]+) s\)')) { [double]$m.Groups[1].Value })
$aspect = ([regex]::Match($new, '(?m)^.*aspect.*$')).Value.Trim()
$tick = ([regex]::Match($new, 'sim-tick: ON - whole sim every [0-9.]+ ms')).Value
$sum = & python -I "$PSScriptRoot\shot-stats.py" "$Out" 2>&1 | Out-String
$vid = if (Test-Path "$Out\video.mp4") { & $FF.ffprobe -v error -count_frames -show_entries stream=width,height,nb_read_frames,duration -of compact "$Out\video.mp4" } else { 'NO VIDEO' }
@("shot $Shot ($stamp) preset $($S.Preset) strip $(@($S.Strip) -join ',') keys $(if ($S.Keys) { ($S.Keys.Keys | % { "$_=$($S.Keys[$_])" }) -join ',' }) patch20 $([bool]$S.Patch20)",
  "video: $vid", "proxy fps windows: $($w -join ' ')", "aspect line: $aspect", "tick: $tick", $sum.Trim()) | Tee-Object -FilePath "$Out\summary.txt"
