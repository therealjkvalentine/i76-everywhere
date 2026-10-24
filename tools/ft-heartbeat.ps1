# Is opentrack's freetrack output LIVE? (not merely: does FT_SharedMem exist)
#
# A named mapping outlives its writer while any reader holds a handle (the head-look layer keeps one
# open), so existence proves nothing. FreeTrackData starts with DataID (u32), which opentrack bumps on
# every pose it publishes; live = DataID advances within the window.
#
#   tools\ft-heartbeat.ps1 [-Seconds 1.5]    -> prints "live <n> updates" / "stale" / "absent", exit 0 / 1 / 2
#   . tools\ft-heartbeat.ps1 -Library        -> defines Test-FtLive / Get-FtSample for other scripts
param([double]$Seconds = 1.5, [switch]$Library)

function Get-FtSample {
    # returns @{ DataID; Yaw; Pitch } or $null when the mapping does not exist
    try { $m = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem', 'Read') } catch { return $null }
    try {
        $v = $m.CreateViewAccessor(0, 24, 'Read')
        $s = @{ DataID = $v.ReadUInt32(0); Yaw = $v.ReadSingle(12); Pitch = $v.ReadSingle(16) }
        $v.Dispose()
        return $s
    } finally { $m.Dispose() }
}

function Test-FtLive([double]$Seconds = 1.5) {
    # 'absent' | 'stale' | 'live'
    $a = Get-FtSample
    if (-not $a) { return 'absent' }
    $end = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $end) {
        Start-Sleep -Milliseconds 100
        $b = Get-FtSample
        if (-not $b) { return 'absent' }
        if ($b.DataID -ne $a.DataID) { return 'live' }
    }
    return 'stale'
}

if ($Library) { return }
$a = Get-FtSample
$r = Test-FtLive $Seconds
$b = Get-FtSample
if ($r -eq 'live') {
    "live  DataID {0} -> {1}  yaw {2:N3} pitch {3:N3}" -f $a.DataID, $b.DataID, $b.Yaw, $b.Pitch
    exit 0
}
$r
if ($r -eq 'stale') { exit 1 } else { exit 2 }
