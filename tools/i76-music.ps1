<#
  i76-music.ps1 - play Interstate '76's soundtrack, because the game cannot.

  ---------------------------------------------------------------------------
  WHY THIS IS NEEDED (measured, 2026-08-04)
  ---------------------------------------------------------------------------
  I'76 plays its music as RED BOOK CD AUDIO through MCI. On a machine with no
  optical drive there is no cdaudio device to open, so the engine's music init
  fails and you get silence. Confirmed three ways:

    * `mciSendString("open cdaudio")` returns 266 - FAILS for ANY app on this
      machine, not just the game. Win32_CDROMDrive reports no drives at all.
    * the engine's own MCI handles at 0x4ed890 / 0x4ed894 both read 0xFFFFFFFF
      (-1, never opened) and its music-active flag at 0x524674 reads 0.
    * `win32.dll` and `audiere.dll` - GOG's music bridge - are NOT LOADED into
      the running process. Verified by enumerating modules from 32-bit
      PowerShell; a 64-bit host reports 0 modules for a 32-bit process, which is
      the false negative documented in docs/FFB-LAPTOP-RECON.md.

  GOG ships the soundtrack as music\2.mp3 .. 17.mp3 - the original CD's audio
  track numbers, with no 1.mp3 because track 1 was the data track - but does not
  wire them into the engine. They are files beside the game, not game audio.

  THE PROPER FIX would be a winmm.dll proxy that intercepts the game's MCI
  cdaudio calls and redirects them to those MP3s. That needs a C compiler, which
  this machine does not have. So this plays them alongside the game instead.

  WHAT THIS IS NOT: it is not synchronised to the game. The engine cannot tell it
  which track a mission wants. But the original simply played CD tracks in
  sequence, so sequential playback is closer to faithful than it sounds.

  ---------------------------------------------------------------------------
  USE
  ---------------------------------------------------------------------------
      tools\i76-music.ps1                       # play while the game runs
      tools\i76-music.ps1 -Shuffle -Volume 600
      tools\i76-music.ps1 -MissionOnly          # silent at menus
      tools\i76-music.ps1 -Once                 # one track, then exit (a test)

  Uses MCI through winmm directly - no external player, nothing to install.
  Exits on its own when the game exits, so the launcher can start it and forget.
#>
param(
    [string]$MusicDir = "",
    [switch]$Shuffle,
    # MCI volume, 0..1000. 1000 is full; the soundtrack is mastered loud and the
    # game's own effects have no volume relationship to it, so this defaults low
    # enough to sit under gunfire rather than over it.
    [int]$Volume = 550,
    # Only play while a mission is loaded, using the same player-entity pointer the
    # FFB tools use. Mirrors the original, which was quiet in the menus.
    [switch]$MissionOnly,
    [switch]$Once,
    # Start on a given CD track number (the MP3s are named by track: 2..17), then
    # continue in order. The engine cannot tell this script which track a mission
    # wants - it drives music through an MCI cdaudio device that does not exist
    # here - so if you are mid-campaign and want the right music, name it.
    # 0 = start at the first track.
    [int]$StartTrack = 0,
    # Seconds to wait for the game at startup, so launch ordering does not matter.
    [int]$WaitForGame = 60
)
$ErrorActionPreference = 'Continue'

if (-not ('MciMus' -as [type])) {
    Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class MciMus {
  [DllImport("winmm.dll", CharSet=CharSet.Ansi)]
  public static extern int mciSendStringA(string cmd, StringBuilder ret, int len, IntPtr hwnd);
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
}

function Mci {
    param([string]$Cmd)
    $sb = New-Object System.Text.StringBuilder 512
    $rc = [MciMus]::mciSendStringA($Cmd, $sb, 512, [IntPtr]::Zero)
    return [pscustomobject]@{ Rc = $rc; Text = $sb.ToString() }
}

# ---- locate the game and its music ---------------------------------------
$proc = $null
$deadline = (Get-Date).AddSeconds($WaitForGame)
while (-not $proc -and (Get-Date) -lt $deadline) {
    $proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { Start-Sleep -Milliseconds 700 }
}
if (-not $proc) { Write-Host "Game did not appear within $WaitForGame s - nothing to accompany." -ForegroundColor Yellow; exit 1 }

if (-not $MusicDir) {
    try { $MusicDir = Join-Path (Split-Path $proc.Path) 'music' } catch { }
}
if (-not $MusicDir -or -not (Test-Path $MusicDir)) {
    Write-Host "No music folder found (looked in '$MusicDir')." -ForegroundColor Red
    exit 1
}

# Sorted NUMERICALLY, not lexically: as strings, 10.mp3 sorts before 2.mp3 and the
# soundtrack would play in a nonsense order.
$tracks = @(Get-ChildItem (Join-Path $MusicDir '*.mp3') |
    Sort-Object { [int]([System.IO.Path]::GetFileNameWithoutExtension($_.Name) -replace '\D', '0') })
if (-not $tracks.Count) { Write-Host "No .mp3 files in $MusicDir" -ForegroundColor Red; exit 1 }
if ($Shuffle) { $tracks = @($tracks | Sort-Object { Get-Random }) }

# Rotate so playback begins on the requested CD track, keeping the rest in order.
$startIdx = 0
if ($StartTrack -gt 0) {
    for ($k = 0; $k -lt $tracks.Count; $k++) {
        $num = [int]([System.IO.Path]::GetFileNameWithoutExtension($tracks[$k].Name) -replace '\D', '0')
        if ($num -eq $StartTrack) { $startIdx = $k; break }
    }
    if ($startIdx -eq 0 -and (([int](([System.IO.Path]::GetFileNameWithoutExtension($tracks[0].Name)) -replace '\D','0')) -ne $StartTrack)) {
        Write-Host ("  track $StartTrack not found - starting at {0}" -f $tracks[0].Name) -ForegroundColor DarkYellow
    }
}

Write-Host ("i76-music: {0} tracks from {1}" -f $tracks.Count, $MusicDir) -ForegroundColor Cyan
Write-Host ("game pid {0}; volume {1}/1000{2}" -f $proc.Id, $Volume,
    $(if ($MissionOnly) { "; mission-only" } else { "" })) -ForegroundColor DarkGray

# ---- mission detection (optional) ----------------------------------------
$hProc = [IntPtr]::Zero
if ($MissionOnly) { $hProc = [MciMus]::OpenProcess(0x38, $false, $proc.Id) }
function In-Mission {
    if ($hProc -eq [IntPtr]::Zero) { return $true }
    $b = New-Object byte[] 4; $n = 0
    function Rd([int64]$a) {
        if ([MciMus]::ReadProcessMemory($hProc, [IntPtr]$a, $b, 4, [ref]$n)) { return [BitConverter]::ToInt32($b, 0) }
        return 0
    }
    $w = Rd 0x54a264
    if ($w -eq 0) { return $false }
    $s = Rd $w
    if ($s -eq 0) { return $false }
    return ((Rd ($s + 0x70)) -ne 0)
}

$alias = "i76mus"
$playing = $false
try {
    $i = $startIdx
    while (-not $proc.HasExited) {
        $t = $tracks[$i % $tracks.Count]
        $i++

        # Wait for a mission before starting a track, rather than opening one and
        # immediately pausing it - MCI is happier not being poked while idle.
        while ($MissionOnly -and -not (In-Mission) -and -not $proc.HasExited) {
            Start-Sleep -Milliseconds 800
            $proc.Refresh()
        }
        if ($proc.HasExited) { break }

        $null = Mci "close $alias"
        $open = Mci ("open `"{0}`" type mpegvideo alias {1}" -f $t.FullName, $alias)
        if ($open.Rc -ne 0) {
            Write-Host ("  skip {0} (MCI open rc {1})" -f $t.Name, $open.Rc) -ForegroundColor DarkYellow
            continue
        }
        $null = Mci "setaudio $alias volume to $Volume"
        $null = Mci "play $alias"
        $playing = $true
        Write-Host ("  playing {0}" -f $t.Name) -ForegroundColor DarkGray

        # Poll rather than using MCI notify: notification needs a window and a
        # message pump, and this script has neither by design.
        while ($true) {
            Start-Sleep -Milliseconds 500
            $proc.Refresh()
            if ($proc.HasExited) { break }
            $mode = (Mci "status $alias mode").Text
            if ($mode -notmatch 'playing') { break }
            if ($MissionOnly -and -not (In-Mission)) {
                $null = Mci "pause $alias"
                while ($MissionOnly -and -not (In-Mission) -and -not $proc.HasExited) {
                    Start-Sleep -Milliseconds 800
                    $proc.Refresh()
                }
                if (-not $proc.HasExited) { $null = Mci "resume $alias" }
            }
        }
        $null = Mci "close $alias"
        $playing = $false
        if ($Once) { break }
    }
}
finally {
    # Leaving an MCI device open holds the file and can wedge later playback, so
    # close unconditionally - the same discipline as releasing the wheel.
    if ($playing) { $null = Mci "stop $alias" }
    $null = Mci "close $alias"
    if ($hProc -ne [IntPtr]::Zero) { [void][MciMus]::CloseHandle($hProc) }
    Write-Host "i76-music: stopped." -ForegroundColor Cyan
}
