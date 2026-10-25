<#
  record-window.ps1 - launch-video lane: record the game window the OWNER is driving (no launch, no input, no lock taken:
  the owner holds the console). For shots a script cannot drive: combat with FFB, head look with opentrack, the jump.

    powershell -ExecutionPolicy Bypass -File record-window.ps1 -Tag combat -Seconds 90
    (start the game first, e.g.  PLAY.bat --windowed 1920x1080  so the window is 1080p; the countdown gives 5 s to click back in)

  Output: <lab>\captures\launch-video\raw\owner-<tag>\<stamp>\video.mp4 (60 fps, the window rect only, ffmpeg ddagrab +
  h264_mf) and capture.json. A beep at the start and at the end.
#>
param([string]$Tag = 'take', [int]$Seconds = 60, [int]$Countdown = 5, [string]$Rect = '')   # -Rect 'x,y,w,h' records that screen area instead (game + FFB panel side by side: '0,0,1920,1080')
. (Join-Path $PSScriptRoot 'lv-lib.ps1')
$FF = Get-LvFfmpeg
$g = Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
if (-not $g) { Write-Host "no game window found - start the game first" -ForegroundColor Red; exit 1 }
Add-Type -Namespace LvO -Name U -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L, T, R, B; }
"@
$r = New-Object LvO.U+RECT; [void][LvO.U]::GetWindowRect($g.MainWindowHandle, [ref]$r)
$x = [math]::Max(0, $r.L); $y = [math]::Max(0, $r.T); $w = ($r.R - $x) -band -2; $h = ($r.B - $y) -band -2
if ($Rect) {
    $n = @($Rect -split '[,\s]+' | Where-Object { $_ -ne '' } | ForEach-Object { [int]$_ })
    if ($n.Count -ne 4) { Write-Host "-Rect needs x,y,w,h (got '$Rect') - nothing recorded" -ForegroundColor Red; exit 2 }
    $x, $y, $w, $h = $n
}
$Out = Join-Path $script:LvCap ("raw\owner-$Tag\" + (Get-Date -Format 'yyyyMMdd-HHmmss')); New-Item -ItemType Directory -Force $Out | Out-Null
Write-Host "recording $($g.ProcessName) pid $($g.Id) window ${w}x${h} at $x,$y for $Seconds s -> $Out" -ForegroundColor Cyan
for ($i = $Countdown; $i -gt 0; $i--) { Write-Host "  $i"; Start-Sleep -Seconds 1 }
[console]::Beep(880, 200)
$vf = "ddagrab=output_idx=0:framerate=60:draw_mouse=0:offset_x=${x}:offset_y=${y}:video_size=${w}x${h},hwdownload,format=bgra,format=nv12"
$t0 = [DateTimeOffset]::Now.ToUnixTimeMilliseconds() / 1000.0
@{ shot = "owner-$Tag"; capture_start_host_t = $t0; rect = @($x, $y, $w, $h); still = 0; drive = $Seconds; owner = $true; pid = $g.Id } | ConvertTo-Json | Set-Content "$Out\capture.json"
& $FF.ffmpeg -hide_banner -loglevel warning -y -f lavfi -i $vf -t $Seconds -c:v h264_mf -hw_encoding 1 -b:v 40M -maxrate 60M "$Out\video.mp4"
[console]::Beep(660, 300)
& $FF.ffprobe -v error -count_frames -show_entries stream=width,height,nb_read_frames,duration -of compact "$Out\video.mp4"
