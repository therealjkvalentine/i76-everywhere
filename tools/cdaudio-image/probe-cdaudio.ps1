<#
  probe-cdaudio.ps1 - can MCI see and play CD audio from a mounted virtual drive?

  THIS IS THE LOAD-BEARING UNKNOWN for the virtual-CD route to I'76 music. The game
  plays its soundtrack through MCI's `cdaudio` device (docs/MUSIC.md). A virtual
  drive definitely presents the DATA track to Windows - that is what mounting is
  for - but whether it exposes CD-DA in a way MCI can enumerate and PLAY is a
  property of the specific virtual-drive driver, not something that follows from
  mounting working.

  So: validate it against a 4-second test image BEFORE building a 400 MB one and
  before touching the game.

      tools\cdaudio-image\probe-cdaudio.ps1

  Expected on success: `open cdaudio` returns 0, two tracks are reported, and you
  HEAR a 440 Hz tone. Then the game will work too, because that is the same call it
  makes and the same device.

  If `open cdaudio` still returns 266 with an audio disc mounted, this route is
  dead for that driver and the injection route in docs/MUSIC.md is the remaining
  option.
#>
param([int]$Track = 1, [int]$PlaySeconds = 3)
$ErrorActionPreference = 'Continue'

Add-Type -ErrorAction SilentlyContinue @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class MciProbe {
  [DllImport("winmm.dll", CharSet=CharSet.Ansi)]
  public static extern int mciSendStringA(string cmd, StringBuilder ret, int len, IntPtr hwnd);
}
"@
function Mci {
    param([string]$c)
    $sb = New-Object System.Text.StringBuilder 256
    $rc = [MciProbe]::mciSendStringA($c, $sb, 256, [IntPtr]::Zero)
    return [pscustomobject]@{ Rc = $rc; Text = $sb.ToString() }
}

Write-Host "=== optical drives Windows can see ===" -ForegroundColor Cyan
$d = Get-CimInstance Win32_CDROMDrive -ErrorAction SilentlyContinue
if ($d) {
    $d | ForEach-Object { "  {0}  {1}  media loaded: {2}" -f $_.Drive, $_.Caption, $_.MediaLoaded }
} else {
    Write-Host "  NONE - mount the image first, or the driver is not installed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== MCI cdaudio ===" -ForegroundColor Cyan
$o = Mci "open cdaudio alias cd shareable"
Write-Host ("  open cdaudio -> rc {0} {1}" -f $o.Rc, $(if ($o.Rc -eq 0) { "SUCCESS" } else { "FAILED" }))
if ($o.Rc -ne 0) {
    if ($o.Rc -eq 266) {
        Write-Host "  rc 266 = no CD-audio device. Either nothing is mounted, or the" -ForegroundColor Yellow
        Write-Host "  driver does not expose CD-DA to MCI. This is the exact failure the" -ForegroundColor Yellow
        Write-Host "  game hits." -ForegroundColor Yellow
    }
    $e = Mci "sysinfo cdaudio quantity"
    Write-Host ("  MCI reports {0} cdaudio device(s)" -f $e.Text)
    exit 2
}

try {
    $null = Mci "set cd time format tmsf"
    $n = Mci "status cd number of tracks"
    Write-Host ("  number of tracks : {0}" -f $n.Text)
    $md = Mci "status cd media present"
    Write-Host ("  media present    : {0}" -f $md.Text)
    $len = Mci "status cd length"
    Write-Host ("  disc length      : {0}" -f $len.Text)
    for ($i = 1; $i -le [Math]::Min(4, [int]($n.Text -as [int])); $i++) {
        $tl = Mci "status cd length track $i"
        $tt = Mci "status cd type track $i"
        Write-Host ("    track {0}: length {1}  type {2}" -f $i, $tl.Text, $tt.Text)
    }

    Write-Host ""
    Write-Host ("  playing track {0} for {1}s - LISTEN" -f $Track, $PlaySeconds) -ForegroundColor Green
    $p = Mci "play cd from $Track"
    Write-Host ("  play -> rc {0}" -f $p.Rc)
    Start-Sleep -Seconds $PlaySeconds
    $m = Mci "status cd mode"
    Write-Host ("  mode while playing: {0}" -f $m.Text)
    $null = Mci "stop cd"

    Write-Host ""
    if ($p.Rc -eq 0 -and $m.Text -match 'playing') {
        Write-Host "VERDICT: MCI can enumerate AND play CD audio from this drive." -ForegroundColor Green
        Write-Host "The game makes exactly these calls, so the virtual-CD route will work." -ForegroundColor Green
    } elseif ($p.Rc -eq 0) {
        Write-Host "VERDICT: play was accepted but the device never reported 'playing'." -ForegroundColor Yellow
        Write-Host ("mode was '{0}'. Did you hear the tone? If yes this is fine; if no," -f $m.Text) -ForegroundColor Yellow
        Write-Host "the drive enumerates audio tracks but cannot play them." -ForegroundColor Yellow
    } else {
        Write-Host "VERDICT: enumeration works, PLAYBACK does not." -ForegroundColor Red
    }
}
finally { $null = Mci "close cd" }
