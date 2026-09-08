<#
  LAYERS.ps1 - run Interstate '76 as plain vanilla GOG, and add our modifications back ONE AT
  A TIME until something breaks.

  WHY THIS EXISTS
  ---------------
  Two days of debugging happened on top of a stack of accumulated modifications - a patched
  exe, a patched shell, a USER32 proxy, a Glide wrapper, a music proxy, three AutoHotkey
  layers - with no way to say which of them any given symptom belonged to. Several "bugs"
  turned out to be one of those layers, and at least one (bookmark names dropping every
  character) was a two-byte patch someone else shipped. So: start from stock and re-add.

  EVERY LAYER IS OFF BY DEFAULT. With nothing ticked, game\ is byte-for-byte the GOG release:

      i76.exe       9a232dcc   stock GOG
      i76shell.dll  deb41008   stock GOG (NOT the portable's "orig", which is patched)
      STRLKUP.DLL   e5951e0f   stock
      glide2x.dll   c319a4f3   GOG's own Glide wrapper (NOT dgVoodoo)

  This install is separate from the daily driver on purpose (AGENTS.md: NEVER TEST ON THE
  PLAYABLE INSTALL). Nothing here touches ..\Downloads\...\Interstate 76.

      powershell -ExecutionPolicy Bypass -File LAYERS.ps1          # the window
      powershell -ExecutionPolicy Bypass -File LAYERS.ps1 -Status  # text, no window
      powershell -ExecutionPolicy Bypass -File LAYERS.ps1 -Apply 02-dgvoodoo -Play
#>
param(
    [switch]$Status,
    [string[]]$Apply,
    [string[]]$Remove,
    [switch]$Play,
    [switch]$Reset,         # back to pure vanilla
    [switch]$Fast,          # 640x480 window + no sound, for quick iteration
    [switch]$Normal         # undo -Fast
)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Game = Join-Path $Root 'game'
$Mods = Join-Path $Root 'mods'

# ---------------------------------------------------------------------------------------
# Each layer: the files it swaps in, plus (optionally) a byte patch. "needs" is advisory -
# the UI warns rather than refusing, because finding out what breaks is the point.
# ---------------------------------------------------------------------------------------
$LAYERS = @(
    @{ Id='01-exe-framepatch'; Name='Frame/PIT patched exe'
       Desc='i76.exe with the frame-pacing patches (immi101 i76fix family). The stock exe runs its sim off the PIT and misbehaves on modern hardware.'
       Needs=@() }
    @{ Id='02-dgvoodoo';       Name='dgVoodoo renderer'
       Desc='Replaces GOG''s glide2x with dgVoodoo (D3D11) plus its ddraw/d3d8/d3d9 wrappers and dgVoodoo.conf. This is what gives high resolution, aspect correction and the FPS limit - and it also owns the mouse cursor.'
       Needs=@() }
    @{ Id='03-u32x';           Name='u32x USER32 proxy'
       Desc='Retargets i76.exe''s USER32 imports to u32x.dll, which translates cursor coordinates between the game''s 640x480 space and the real screen. Needed for menu clicks to land when dgVoodoo is stretching the image.'
       Needs=@('02-dgvoodoo') }
    @{ Id='04-music';          Name='Music (MCI CD-audio proxy)'
       Desc='Strlkup.dll proxy that answers the engine''s CD-audio calls with music\*.mp3. Also makes the in-game AUDIO CONTROL slider work (auxSetVolume -> setaudio).'
       Needs=@() }
    @{ Id='05-shell-textentry'; Name='Shell text-entry fix (2 bytes)'
       Desc='Restores stock bytes at 0x1B52C/0x1B535 so ToAscii''s output word is zeroed. Without it you can type at most one character into a bookmark name. NOTE: only meaningful if a PATCHED shell is in use - stock GOG already has these bytes.'
       Needs=@() ; Patch=$true }
    @{ Id='06-u32x-ghosting';  Name='u32x + DWM ghosting fix'
       Desc='u32x built from the shipped revision plus one call, DisableProcessWindowsGhosting(). Stops the Save Bookmark screen dying ~5.9s after it opens. Replaces the u32x.dll from layer 03.'
       Needs=@('03-u32x') }
    @{ Id='07-ahk';            Name='AutoHotkey layers'
       Desc='_ahk\ - controller remap, CH Fighterstick HOTAS layer, cursor overlay, opentrack autostart. Files only; the launcher decides which to run.'
       Needs=@() }
    @{ Id='09-patched-shell';  Name='Patched i76shell.dll (the third-party one)'
       Desc='The shell the portable install ships - and which it misleadingly keeps as "i76shell.dll.orig". It is NOT pristine: bytes 0x1B52C/0x1B535 are 40/0c, which stops ToAscii''s output word being zeroed, so bookmark names drop every character but (occasionally) the first. Apply this to REPRODUCE that bug; then apply 05 to fix it.'
       Needs=@() }
    @{ Id='10-silent';         Name='Silence (DirectSound stub)'
       Desc='A dsound.dll beside the exe that answers DirectSoundCreate with DSERR_NODRIVER, so the engine takes its own no-sound-card path. i76.exe imports exactly one DirectSound function, so this is the whole of it. Loader prefers the application directory, so nothing outside this folder is affected.'
       Needs=@() }
    @{ Id='08-extras';         Name='Mouse wheel binder'
       Desc='i76wheel.exe - translates the mouse wheel to keystrokes, since the engine''s mouse device has no wheel channel.'
       Needs=@() }
)

# the two-byte shell patch (layer 05)
$PATCH_SITES = @(
    @{ Off = 0x1B52C; Stock = 0x41; Patched = 0x40 },
    @{ Off = 0x1B535; Stock = 0x08; Patched = 0x0C }
)

function Md5($p) { if (Test-Path $p) { (Get-FileHash $p -Algorithm MD5).Hash.Substring(0,8).ToLower() } else { $null } }

function Is-Applied($layer) {
    $dir = Join-Path $Mods $layer.Id
    if ($layer.Patch) {
        $sh = Join-Path $Game 'i76shell.dll'
        if (-not (Test-Path $sh)) { return $false }
        $b = [IO.File]::ReadAllBytes($sh)
        return ($b[$PATCH_SITES[0].Off] -eq $PATCH_SITES[0].Stock -and $b[$PATCH_SITES[1].Off] -eq $PATCH_SITES[1].Stock)
    }
    if (-not (Test-Path $dir)) { return $false }
    $files = Get-ChildItem $dir -File -Recurse -EA SilentlyContinue
    if (-not $files) { return $false }
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($dir.Length + 1)
        $dst = Join-Path $Game $rel
        if (-not (Test-Path $dst)) { return $false }
        if ((Md5 $dst) -ne (Md5 $f.FullName)) { return $false }
    }
    $true
}

function Apply-Layer($layer) {
    $dir = Join-Path $Mods $layer.Id
    if ($layer.Patch) {
        $sh = Join-Path $Game 'i76shell.dll'
        $b = [IO.File]::ReadAllBytes($sh)
        foreach ($s in $PATCH_SITES) { $b[$s.Off] = $s.Stock }
        [IO.File]::WriteAllBytes($sh, $b)
        return
    }
    Get-ChildItem $dir -File -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring($dir.Length + 1)
        $dst = Join-Path $Game $rel
        $dd = Split-Path $dst -Parent
        if (-not (Test-Path $dd)) { New-Item -ItemType Directory -Path $dd -Force | Out-Null }
        Copy-Item $_.FullName $dst -Force
    }
}

function Remove-Layer($layer) {
    $dir = Join-Path $Mods $layer.Id
    $van = Join-Path $Mods '00-vanilla'
    if ($layer.Patch) {
        $sh = Join-Path $Game 'i76shell.dll'
        $b = [IO.File]::ReadAllBytes($sh)
        foreach ($s in $PATCH_SITES) { $b[$s.Off] = $s.Patched }
        [IO.File]::WriteAllBytes($sh, $b)
        return
    }
    Get-ChildItem $dir -File -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring($dir.Length + 1)
        $dst = Join-Path $Game $rel
        $orig = Join-Path $van (Split-Path $rel -Leaf)
        if (Test-Path $orig) { Copy-Item $orig $dst -Force }   # restore the stock file
        elseif (Test-Path $dst) { Remove-Item $dst -Force }    # purely additive - just delete
    }
}

function Reset-Vanilla {
    foreach ($l in ($LAYERS | Sort-Object { $_.Id } -Descending)) {
        if (Is-Applied $l) { Remove-Layer $l }
    }
    Get-ChildItem (Join-Path $Mods '00-vanilla') -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $Game $_.Name) -Force
    }
}

# ---------------------------------------------------------------------------------------
# -Fast : a small windowed, silent instance for iterating quickly.
#
# 640x480 windowed matters for more than screen area: the engine hit-tests its UI in 640x480
# coordinates, so at native size a screen pixel IS a UI pixel and menu coordinates need no
# translation at all - which removes the single biggest source of wrong answers in this
# project's automation (a 25 px error once cost most of a day). Silence matters because a
# test instance shares the sound device with whoever is at the machine.
#
# This edits dgVoodoo.conf in place rather than shipping a second conf as a layer, so it
# composes with 02-dgvoodoo instead of fighting it over the same file.
# ---------------------------------------------------------------------------------------
$FAST_KEYS = @{
    FullScreenMode     = 'false'
    WindowedAttributes = 'border'
    # Without this the game stays full-screen no matter what FullScreenMode says: with
    # AppControlledScreenMode=true the APP picks the screen mode, and I'76 asks for
    # fullscreen. Measured 2026-09-08 - forcing the resolution and unforcing it both left
    # a 3440x1440 window until this was turned off.
    AppControlledScreenMode = 'false'      # a real title bar, so it can be moved and closed
    ScalingMode        = 'unspecified' # no stretching: 1 screen px == 1 UI px
    # 'unforced' - NOT '640x480'. dgVoodoo SNAPS a forced value to a real enumerated
    # display mode, so 640x480 became the desktop mode and the window filled the screen.
    # The conf's own note records the opposite behaviour: left unforced, the window comes
    # up at the raw 640x480 the game actually asks for. Measured again 2026-09-08.
    Resolution         = 'unforced'
}

function Write-ConfNoBom([string]$Path, [string[]]$Lines) {
    # NEVER Set-Content -Encoding utf8: PowerShell 5.1 writes a UTF-8 BOM, dgVoodoo then
    # cannot parse the file and SILENTLY falls back to its own defaults - watermark on,
    # aspect uncorrected, every setting lost, with no error anywhere. Measured 2026-09-06.
    $enc = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, (($Lines -join "`r`n") + "`r`n"), $enc)
    $h = [IO.File]::ReadAllBytes($Path)[0..2]
    if ($h[0] -eq 0xEF -and $h[1] -eq 0xBB -and $h[2] -eq 0xBF) { throw "wrote a BOM to $Path" }
}

function Set-Fast([bool]$on) {
    $conf = Join-Path $Game 'dgVoodoo.conf'
    if (-not (Test-Path $conf)) {
        Write-Host "  dgVoodoo.conf not present - apply 02-dgvoodoo first (the window is dgVoodoo's)."
        return
    }
    $bak = "$conf.pre-fast"
    if ($on) {
        if (-not (Test-Path $bak)) { Copy-Item $conf $bak }
        $t = Get-Content $conf
        foreach ($k in $FAST_KEYS.Keys) {
            $t = $t -replace ('^(\s*{0}\s*=\s*).*' -f [regex]::Escape($k)), ('${1}' + $FAST_KEYS[$k])
        }
        Write-ConfNoBom $conf $t
        $l = $LAYERS | Where-Object Id -eq '10-silent'
        if ($l -and -not (Is-Applied $l)) { Apply-Layer $l }
        Write-Host "  fast mode ON  - 640x480 window, silent."
    } else {
        if (Test-Path $bak) { Copy-Item $bak $conf -Force; Remove-Item $bak -Force }
        $l = $LAYERS | Where-Object Id -eq '10-silent'
        if ($l -and (Is-Applied $l)) { Remove-Layer $l }
        Write-Host "  fast mode OFF - previous dgVoodoo.conf restored, sound back."
    }
}

function Get-FastState {
    $conf = Join-Path $Game 'dgVoodoo.conf'
    if (-not (Test-Path $conf)) { return $false }
    (Test-Path "$conf.pre-fast")
}

function Show-Status {
    Write-Host ""
    Write-Host "  Interstate '76 - bisect install: $Game"
    Write-Host ""
    foreach ($l in $LAYERS) {
        $on = Is-Applied $l
        $mark = if ($on) { '[x]' } else { '[ ]' }
        $col  = if ($on) { 'Green' } else { 'DarkGray' }
        Write-Host ("  {0} {1,-20} {2}" -f $mark, $l.Id, $l.Name) -ForegroundColor $col
    }
    Write-Host ""
    foreach ($f in 'i76.exe','i76shell.dll','STRLKUP.DLL','glide2x.dll') {
        Write-Host ("      {0,-14} {1}" -f $f, (Md5 (Join-Path $Game $f)))
    }
    Write-Host ""
    Write-Host ("      fast mode (640x480 window, silent): {0}" -f $(if (Get-FastState) { 'ON' } else { 'off' }))
    Write-Host ""
    Write-Host "      vanilla fingerprints: i76.exe 9a232dcc  i76shell.dll deb41008  STRLKUP.DLL e5951e0f  glide2x.dll c319a4f3"
    Write-Host ""
}

Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)] public struct WRECT { public int L,T,R,B; }
public class WinSz {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out WRECT r);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);
  [DllImport("user32.dll")] public static extern int GetWindowLongA(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern int SetWindowLongA(IntPtr h, int i, int v);
  [DllImport("user32.dll")] public static extern bool AdjustWindowRect(ref WRECT r, int style, bool menu);
}
'@ -ErrorAction SilentlyContinue

function Resize-GameWindow([int]$Width, [int]$Height) {
    # dgVoodoo's windowed settings do NOT size this game in Glide mode - forced resolution,
    # unforced, AppControlledScreenMode off, centered scaling and FullscreenAttributes=real
    # were all measured and all produced a 3440x1440 client. The window belongs to the game.
    # Resizing it from outside does work, and the render follows (verified: the Options Menu
    # draws correctly, letterboxed, at 640x480).
    #
    # NOTE the variable is $wnd, not $h - PowerShell variable names are CASE-INSENSITIVE, and
    # a $h here silently overwrote the $Height parameter, asking for a 9898198-pixel window.
    $proc = $null
    for ($i = 0; $i -lt 40; $i++) {
        $proc = Get-Process i76 -EA SilentlyContinue
        if ($proc -and $proc.MainWindowHandle -ne 0) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $proc -or $proc.MainWindowHandle -eq 0) { Write-Host "  (no window to resize)"; return }
    $wnd = $proc.MainWindowHandle
    $GWL_STYLE = -16
    $style = [WinSz]::GetWindowLongA($wnd, $GWL_STYLE)
    [void][WinSz]::SetWindowLongA($wnd, $GWL_STYLE, ($style -bor 0x00C00000 -bor 0x00080000))
    $want = New-Object WRECT; $want.L = 0; $want.T = 0; $want.R = $Width; $want.B = $Height
    [void][WinSz]::AdjustWindowRect([ref]$want, [WinSz]::GetWindowLongA($wnd, $GWL_STYLE), $false)
    [void][WinSz]::SetWindowPos($wnd, [IntPtr]::Zero, 60, 60,
        ($want.R - $want.L), ($want.B - $want.T), 0x34)   # NOZORDER|FRAMECHANGED|NOACTIVATE
    $c = New-Object WRECT; [void][WinSz]::GetClientRect($wnd, [ref]$c)
    Write-Host ("  window resized to {0}x{1}" -f ($c.R - $c.L), ($c.B - $c.T))
}

function Start-Game {
    if (Get-Process i76 -EA SilentlyContinue) { Write-Host "  a copy of i76 is already running"; return }
    Start-Process -FilePath (Join-Path $Game 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $Game
    Write-Host "  launched."
    if (Get-FastState) { Start-Sleep -Seconds 12; Resize-GameWindow 640 480 }
}

# --------------------------------------------------------------------------- CLI paths ---
if ($Fast)   { Set-Fast $true;  Show-Status; if ($Play) { Start-Game }; exit }
if ($Normal) { Set-Fast $false; Show-Status; if ($Play) { Start-Game }; exit }
if ($Reset)  { Reset-Vanilla; Write-Host "  reset to vanilla."; Show-Status; if ($Play) { Start-Game }; exit }
if ($Remove) { foreach ($id in $Remove) { $l = $LAYERS | Where-Object Id -eq $id; if ($l) { Remove-Layer $l; Write-Host "  removed $id" } else { Write-Host "  unknown layer: $id" } } }
if ($Apply)  { foreach ($id in $Apply)  { $l = $LAYERS | Where-Object Id -eq $id; if ($l) { Apply-Layer  $l; Write-Host "  applied $id" } else { Write-Host "  unknown layer: $id" } } }
if ($Status -or $Apply -or $Remove) { Show-Status; if ($Play) { Start-Game }; exit }
if ($Play -and -not $Status) { Show-Status; Start-Game; exit }

# ------------------------------------------------------------------------------- the UI ---
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object Windows.Forms.Form
$form.Text = "Interstate '76 - layer bisect  (everything OFF = stock GOG)"
$form.Size = New-Object Drawing.Size(940, 660)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object Drawing.Font('Segoe UI', 9)

$lbl = New-Object Windows.Forms.Label
$lbl.Text = "Nothing ticked = the GOG release, unmodified. Tick ONE thing, play, and see what changes."
$lbl.Location = New-Object Drawing.Point(14, 10)
$lbl.Size = New-Object Drawing.Size(890, 20)
$form.Controls.Add($lbl)

$checks = @{}
$y = 40
foreach ($l in $LAYERS) {
    $cb = New-Object Windows.Forms.CheckBox
    $cb.Text = "$($l.Id)   -   $($l.Name)"
    $cb.Location = New-Object Drawing.Point(18, $y)
    $cb.Size = New-Object Drawing.Size(520, 22)
    $cb.Tag = $l
    $form.Controls.Add($cb)
    $checks[$l.Id] = $cb

    $d = New-Object Windows.Forms.Label
    $d.Text = $l.Desc
    $d.Location = New-Object Drawing.Point(38, ($y + 21))
    $d.Size = New-Object Drawing.Size(860, 32)
    $d.ForeColor = [Drawing.Color]::DimGray
    $form.Controls.Add($d)
    $y += 60
}

$state = New-Object Windows.Forms.TextBox
$state.Multiline = $true; $state.ReadOnly = $true; $state.ScrollBars = 'Vertical'
$state.Font = New-Object Drawing.Font('Consolas', 8.5)
$state.Location = New-Object Drawing.Point(18, ($y + 6))
$state.Size = New-Object Drawing.Size(880, 90)
$form.Controls.Add($state)

function Refresh-UI {
    foreach ($l in $LAYERS) { $checks[$l.Id].Checked = (Is-Applied $l) }
    $lines = @("game: $Game", "")
    foreach ($f in 'i76.exe','i76shell.dll','STRLKUP.DLL','glide2x.dll') {
        $lines += ("  {0,-14} {1}" -f $f, (Md5 (Join-Path $Game $f)))
    }
    $lines += ""
    $lines += "  vanilla = i76.exe 9a232dcc | i76shell.dll deb41008 | STRLKUP.DLL e5951e0f | glide2x.dll c319a4f3"
    $state.Text = ($lines -join "`r`n")
}

$btnApply = New-Object Windows.Forms.Button
$btnApply.Text = 'Apply ticked'; $btnApply.Location = New-Object Drawing.Point(18, ($y + 104))
$btnApply.Size = New-Object Drawing.Size(130, 36)
$btnApply.Add_Click({
    if (Get-Process i76 -EA SilentlyContinue) {
        [Windows.Forms.MessageBox]::Show('Close the game first.','Running') | Out-Null; return }
    foreach ($l in $LAYERS) {
        $want = $checks[$l.Id].Checked
        $have = Is-Applied $l
        if ($want -and -not $have) { Apply-Layer $l }
        elseif (-not $want -and $have) { Remove-Layer $l }
    }
    Refresh-UI
})
$form.Controls.Add($btnApply)

$btnReset = New-Object Windows.Forms.Button
$btnReset.Text = 'Reset to vanilla'; $btnReset.Location = New-Object Drawing.Point(158, ($y + 104))
$btnReset.Size = New-Object Drawing.Size(130, 36)
$btnReset.Add_Click({
    if (Get-Process i76 -EA SilentlyContinue) {
        [Windows.Forms.MessageBox]::Show('Close the game first.','Running') | Out-Null; return }
    Reset-Vanilla; Refresh-UI })
$form.Controls.Add($btnReset)

$btnPlay = New-Object Windows.Forms.Button
$btnPlay.Text = 'Play'; $btnPlay.Location = New-Object Drawing.Point(760, ($y + 104))
$btnPlay.Size = New-Object Drawing.Size(138, 36)
$btnPlay.Font = New-Object Drawing.Font('Segoe UI', 11, [Drawing.FontStyle]::Bold)
$btnPlay.Add_Click({ Start-Game })
$form.Controls.Add($btnPlay)

Refresh-UI
[void]$form.ShowDialog()
