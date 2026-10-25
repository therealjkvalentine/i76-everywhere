# lv-lib.ps1 - shared helpers for the launch-video pipeline (docs/LAUNCH-VIDEO-2026-10-25.md). Dot-source it.
#   Get-LvFfmpeg            ffmpeg.exe / ffprobe.exe (winget Gyan.FFmpeg 9.0.2 on this PC; PATH or the winget package folder)
#   Wait-LvConsole -Tag x   CONSOLE-LOCK.md protocol: waits (queue line in .fps-queue, poll 10 s) until no i76 / nitro runs,
#                           .console-owner and .fps-lock are free, then takes both with an exclusive create. Returns $true / $false.
#   Exit-LvConsole          frees what Wait-LvConsole took (call in a finally)
$script:LvLab  = (Join-Path $env:USERPROFILE 'i76-uncap-lab')
$script:LvRepo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:LvCap  = Join-Path $script:LvLab 'captures\launch-video'
$script:LvTwin = Join-Path $script:LvLab 'launchvid-20261025\Interstate 76'   # twin of test-gold (CONSOLE-LOCK.md "Copies")

function Get-LvFfmpeg {
    $c = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($c) { $ff = $c.Source } else {
        $ff = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $ff) { throw "ffmpeg not found: winget install --id Gyan.FFmpeg -e" }
    [pscustomobject]@{ ffmpeg = $ff; ffprobe = (Join-Path (Split-Path $ff) 'ffprobe.exe') }
}

$script:LvHeld = @()
function Wait-LvConsole([string]$Tag = 'launch-video', [int]$MaxWaitMin = 240) {
    $owner = Join-Path $script:LvLab '.console-owner'; $fps = Join-Path $script:LvLab '.fps-lock'; $queue = Join-Path $script:LvLab '.fps-queue'
    $mark = "launch-video lane $Tag pid $PID"
    $t0 = Get-Date; $queued = $false
    while ($true) {
        $busy = @()
        if (Get-Process i76, nitro -ErrorAction SilentlyContinue) { $busy += 'a game is running' }
        if (Test-Path $owner) { $busy += "console-owner: $((Get-Content $owner -Raw -ErrorAction SilentlyContinue).Trim())" }
        if (Test-Path $fps) { $busy += "fps-lock: $((Get-Content $fps -Raw -ErrorAction SilentlyContinue).Trim())" }
        if (-not $busy) {
            # queue order: wait behind older live lines (younger than 6 h) of other lanes
            $ahead = @()
            if (Test-Path $queue) {
                foreach ($l in Get-Content $queue) {
                    if ($l -match 'launch-video lane') { break }
                    if ($l -match '(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\s*$' -and ((Get-Date) - [datetime]$Matches[1]).TotalHours -lt 6) { $ahead += $l }
                }
            }
            if (-not $ahead -or ((Get-Date) - $t0).TotalMinutes -gt 30) {
                try {
                    $fs = [IO.File]::Open($owner, 'CreateNew', 'Write'); $w = New-Object IO.StreamWriter($fs)
                    $w.Write("$mark $(Get-Date -Format s)"); $w.Close()
                    try { $fs2 = [IO.File]::Open($fps, 'CreateNew', 'Write'); $w2 = New-Object IO.StreamWriter($fs2); $w2.Write("$mark $(Get-Date -Format s)"); $w2.Close() }
                    catch { Remove-Item $owner -Force; Start-Sleep 5; continue }
                    $script:LvHeld = @($owner, $fps)
                    if (Test-Path $queue) { $rest = @(Get-Content $queue | Where-Object { $_ -notmatch 'launch-video lane' }); if ($rest) { Set-Content $queue $rest } else { Remove-Item $queue -Force } }
                    return $true
                } catch { }
            }
        }
        if (-not $queued -or -not (Select-String -Path $queue -Pattern ([regex]::Escape($mark)) -Quiet -ErrorAction SilentlyContinue)) {
            if (-not $queued) { $qt = Get-Date -Format s }; Add-Content $queue "$mark queued for $Tag $qt"; $queued = $true }   # re-added if another lane rewrote the file
        if (((Get-Date) - $t0).TotalMinutes -gt $MaxWaitMin) { Write-Host "[lv] gave up waiting for the console after $MaxWaitMin min: $($busy -join '; ')" -ForegroundColor Yellow; return $false }
        Write-Host ("[lv] {0:HH:mm:ss} waiting for the console: {1}" -f (Get-Date), ($busy -join '; ')) -ForegroundColor DarkGray
        Start-Sleep -Seconds 10
    }
}
function Exit-LvConsole {
    foreach ($f in $script:LvHeld) { $c = Get-Content $f -Raw -ErrorAction SilentlyContinue; if ($c -match "launch-video lane .* pid $PID") { Remove-Item $f -Force -ErrorAction SilentlyContinue } }
    $script:LvHeld = @()
}
