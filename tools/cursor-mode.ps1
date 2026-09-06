<#
  cursor-mode.ps1 - switch how the mouse pointer is drawn and mapped.

  There are two things that can map the pointer, and they must not both do it:

    dgVoodoo   CaptureMouse=true makes dgVoodoo draw an EMULATED cursor and map screen
               coordinates into the app's 640x480 space itself.
    u32x       our USER32 proxy translates screen->UI in GetCursorPos / mouse messages,
               and maps the game's ClipCursor(0,0,640,480) onto the real on-screen UI rect.

  Symptom when they disagree: CLICKS land in the right place but the pointer is DRAWN
  somewhere else - "the cursor display is on the old coordinates". u32x detects which regime
  is live via GetClipCursor (pointer_is_confined) and steps back when dgVoodoo is confining,
  so the two are meant to coexist - this script is how to test that they actually do.

  Modes:
    emulated  CaptureMouse=true,  FreeMouse=false   dgVoodoo draws and maps the cursor.
    free      CaptureMouse=false, FreeMouse=false   pointer roams; u32x does the mapping.
                                                    (This is what shipped 2026-09-05; it fixed
                                                    the pointer being trapped in the top-left
                                                    640x480 corner, before u32x mapped
                                                    ClipCursor.)
    raw       CaptureMouse=false, FreeMouse=true    dgVoodoo keeps its hands off the mouse
                                                    entirely.

  Usage:  pwsh -File tools\cursor-mode.ps1 -Mode emulated -GameDir "C:\...\Interstate 76"
          pwsh -File tools\cursor-mode.ps1 -Show      -GameDir "..."
#>
param(
    [ValidateSet('emulated', 'free', 'raw')] [string]$Mode,
    [switch]$Show,
    [string]$GameDir = 'C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76'
)
$ErrorActionPreference = 'Stop'

$conf = Join-Path $GameDir 'dgVoodoo.conf'
if (-not (Test-Path $conf)) { throw "no dgVoodoo.conf in $GameDir" }

function Write-ConfNoBom([string]$Path, [string[]]$Lines) {
    # NEVER Set-Content -Encoding utf8 here: PowerShell 5.1 writes a UTF-8 BOM, dgVoodoo
    # cannot parse the file, and it silently falls back to its own defaults - watermark on,
    # aspect ratio uncorrected, every setting here lost, with no error anywhere. Measured
    # 2026-09-06. UTF8Encoding($false) is the no-BOM constructor.
    $enc = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, (($Lines -join "`r`n") + "`r`n"), $enc)
    $head = [IO.File]::ReadAllBytes($Path)[0..2]
    if ($head[0] -eq 0xEF -and $head[1] -eq 0xBB -and $head[2] -eq 0xBF) {
        throw "wrote a BOM to $Path - dgVoodoo would ignore the whole file"
    }
}

function Current {
    $t = Get-Content $conf
    $cap  = ($t | Where-Object { $_ -match '^\s*CaptureMouse\s*=' }) -replace '.*=\s*', ''
    $free = ($t | Where-Object { $_ -match '^\s*FreeMouse\s*=' })    -replace '.*=\s*', ''
    [pscustomobject]@{ CaptureMouse = $cap.Trim(); FreeMouse = $free.Trim() }
}

if ($Show -or -not $Mode) {
    $c = Current
    $name = switch ("$($c.CaptureMouse)/$($c.FreeMouse)") {
        'true/false'  { 'emulated' }
        'false/false' { 'free' }
        'false/true'  { 'raw' }
        default       { 'custom' }
    }
    Write-Host ("  CaptureMouse = {0}`n  FreeMouse    = {1}`n  -> mode: {2}" -f $c.CaptureMouse, $c.FreeMouse, $name)
    if (-not $Mode) { exit 0 }
}

if (Get-Process i76 -EA SilentlyContinue) { throw "close the game first - it reads dgVoodoo.conf at startup" }

$want = switch ($Mode) {
    'emulated' { @{ CaptureMouse = 'true';  FreeMouse = 'false' } }
    'free'     { @{ CaptureMouse = 'false'; FreeMouse = 'false' } }
    'raw'      { @{ CaptureMouse = 'false'; FreeMouse = 'true'  } }
}

$backup = "$conf.pre-cursor-mode"
if (-not (Test-Path $backup)) { Copy-Item $conf $backup }

$text = Get-Content $conf
$text = $text -replace '^(\s*CaptureMouse\s*=\s*).*', ('${1}' + $want.CaptureMouse)
$text = $text -replace '^(\s*FreeMouse\s*=\s*).*',    ('${1}' + $want.FreeMouse)
Write-ConfNoBom $conf $text

$c = Current      # read back from disk - never trust the write
if ($c.CaptureMouse -ne $want.CaptureMouse -or $c.FreeMouse -ne $want.FreeMouse) {
    throw ("write did not stick: CaptureMouse={0} FreeMouse={1}" -f $c.CaptureMouse, $c.FreeMouse)
}
Write-Host ("cursor mode -> {0}  (CaptureMouse={1}, FreeMouse={2}). Relaunch the game." -f $Mode, $c.CaptureMouse, $c.FreeMouse) -ForegroundColor Green
