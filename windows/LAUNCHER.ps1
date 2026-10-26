<#
  LAUNCHER.ps1 - one window showing every setting this project changes from stock, and what
  state the installed game is actually in.

  Why this exists: the interesting settings live in three unrelated places - dgVoodoo.conf,
  PLAY-i76.ps1's switches, and bytes patched into the game's own binaries - so nothing showed
  you the whole picture, and a setting you changed days ago was invisible. Everything that is
  NOT stock is marked, so the window answers "what is different about this install?" at a
  glance rather than requiring you to remember.

  Nothing here is required to play: PLAY-i76.ps1 remains the real entry point and this only
  builds a command line for it.

  Frame-rate preset (2026-10-02): the drop-down in "This session" lists presets\*.psd1 and
  feeds PLAY-i76.ps1 -Preset <name>; the variables go to the game process only. 'stock' is the
  old behaviour. What is NOT here yet: showing the proxy's mciproxy.log lines after a run
  (backlog P2-03 wanted that too) - read <game dir>\mciproxy.log by hand for now.

      powershell -ExecutionPolicy Bypass -File LAUNCHER.ps1 -GameDir "<folder with i76.exe>"

  -GameDir has no built-in default onto the playable install (2026-10-02, backlog P3-12): with
  none given it takes $env:I76_GAME_DIR, then an install this script sits in or beside, then the
  lab sandbox (..\i76-uncap-lab\game). The window title names the folder it is looking at.
#>
param(
    [string]$GameDir = ''
)
$ErrorActionPreference = 'Stop'
if (-not $GameDir) {
    # No built-in default onto the playable install (AGENTS.md "never test on the playable
    # install"; backlog P3-12 - this parameter used to default to the daily driver's path).
    # Order: $env:I76_GAME_DIR, the folder this script sits in or beside (an installed copy),
    # then the lab sandbox. Anything else has to be named with -GameDir.
    $cands = @($env:I76_GAME_DIR, $PSScriptRoot, (Join-Path $PSScriptRoot 'Interstate 76'),
               (Join-Path $PSScriptRoot '..\i76-uncap-lab\game'))
    $GameDir = $cands | Where-Object { $_ -and (Test-Path (Join-Path $_ 'i76.exe')) } | Select-Object -First 1
    if (-not $GameDir) { throw "No game folder: pass -GameDir <folder with i76.exe> or set I76_GAME_DIR." }
    $GameDir = (Resolve-Path $GameDir).Path
}
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$RepoRoot = $PSScriptRoot
$script:GameDir = $GameDir

# ---------------------------------------------------------------- reading the real state ---
# Every value below is read from disk each time Refresh runs. Nothing is cached or assumed,
# because the whole point is to show what is actually installed right now.

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

function Get-Conf {
    $p = Join-Path $script:GameDir 'dgVoodoo.conf'
    if (-not (Test-Path $p)) { return @{} }
    $h = @{}
    foreach ($line in Get-Content $p) {
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$') { $h[$Matches[1]] = $Matches[2] }
    }
    $h
}

function Set-Conf([hashtable]$pairs) {
    $p = Join-Path $script:GameDir 'dgVoodoo.conf'
    $bak = "$p.pre-launcher"
    if (-not (Test-Path $bak)) { Copy-Item $p $bak }
    $text = Get-Content $p
    foreach ($k in $pairs.Keys) {
        $text = $text -replace ('^(\s*{0}\s*=\s*).*' -f [regex]::Escape($k)), ('${1}' + $pairs[$k])
    }
    Write-ConfNoBom $p $text
    # read back - a silent write failure would otherwise look like a working toggle
    $now = Get-Conf
    foreach ($k in $pairs.Keys) {
        if ("$($now[$k])" -ne "$($pairs[$k])") {
            [System.Windows.Forms.MessageBox]::Show(
                ("{0} did not stick (still '{1}'). Is the game running, or the file read-only?" -f $k, $now[$k]),
                'Write failed') | Out-Null
            return $false
        }
    }
    $true
}

function Get-CursorMode {
    $c = Get-Conf
    switch ("$($c.CaptureMouse)/$($c.FreeMouse)") {
        'true/false'  { 'emulated' }
        'false/false' { 'free' }
        'false/true'  { 'raw' }
        default       { 'custom' }
    }
}

# Health checks. Each returns: name, state text, and ok/warn/bad for colouring.
function Get-Health {
    $g = $script:GameDir
    $out = @()

    $u = Join-Path $g 'u32x.dll'
    if (Test-Path $u) {
        $len = (Get-Item $u).Length
        # the U32X_LOG build is much larger and writes a file on every call
        $isLog = $len -gt 90000
        $out += , @('USER32 proxy (u32x.dll)',
                    $(if ($isLog) { "LOGGING BUILD - $len bytes, slow" } else { "ship build - $len bytes" }),
                    $(if ($isLog) { 'warn' } else { 'ok' }))
    } else { $out += , @('USER32 proxy (u32x.dll)', 'MISSING - menus will mis-map the mouse', 'bad') }

    $sh = Join-Path $g 'i76shell.dll'
    if (Test-Path $sh) {
        $b = [IO.File]::ReadAllBytes($sh)
        if ($b.Length -gt 0x1B535) {
            $fixed = ($b[0x1B52C] -eq 0x41 -and $b[0x1B535] -eq 0x08)
            $out += , @('Shell text entry',
                        $(if ($fixed) { 'repaired - bookmark names typeable' }
                          else { 'BROKEN - only one character will type (tools\fix-shell-textentry.ps1)' }),
                        $(if ($fixed) { 'ok' } else { 'bad' }))
        }
    }

    $dir = Join-Path $g 'savegame.dir'
    if (Test-Path $dir) {
        # savegame.dir = u32 count, then 60-byte records at 4 + 60k:
        #   { u32 scene, char name[32], char file[16], u32 state (1 post-mission / 8 garage), u32 0 }
        # A game-written file is exactly 4 + 60*count bytes (the shell's dir_WriteAndSave; 15 of
        # 15 game-written files on this machine). The "0x28 header, 36 bytes short" model this
        # check used until 2026-10-02 was the save editor's misframe (AGENTS.md; backlog P3-04).
        # Longer is fine - older launchers padded with zeros and the reader stops at count.
        $d = [IO.File]::ReadAllBytes($dir)
        if ($d.Length -lt 4) {
            $out += , @('Save index', "UNREADABLE - $($d.Length) bytes, no record count", 'bad')
        } else {
            $n = [BitConverter]::ToUInt32($d, 0)
            $want = 4 + $n * 60
            $ok = $d.Length -ge $want
            $badState = 0
            if ($ok) {
                for ($k = 0; $k -lt $n; $k++) {
                    $st = [BitConverter]::ToUInt32($d, 4 + 60 * $k + 52)
                    if ($st -ne 1 -and $st -ne 8) { $badState++ }
                }
            }
            $txt = if (-not $ok) { "SHORT - $($d.Length) bytes, $n records need $want (4 + 60 x count)" }
                   elseif ($badState) { "$n bookmarks; $badState with a state other than 1/8 (i76-save-editor.py --check)" }
                   elseif ($d.Length -gt $want) { "$n bookmarks, index intact (+$($d.Length - $want) bytes of padding, harmless)" }
                   else { "$n bookmarks, index intact" }
            $out += , @('Save index', $txt, $(if ($ok -and -not $badState) { 'ok' } else { 'warn' }))
        }
    } else { $out += , @('Save index', 'no savegame.dir - no bookmarks installed', 'warn') }

    $music = Join-Path $g 'Strlkup.dll'
    $out += , @('Music (MCI CD-audio proxy)',
                $(if (Test-Path $music) { 'proxy installed' } else { 'MISSING - the game will be silent' }),
                $(if (Test-Path $music) { 'ok' } else { 'warn' }))

    $out += , @('Mouse wheel (i76wheel.exe)',
                $(if (Test-Path (Join-Path $g 'i76wheel.exe')) { 'present' } else { 'not installed' }),
                $(if (Test-Path (Join-Path $g 'i76wheel.exe')) { 'ok' } else { 'warn' }))
    $out
}

# ------------------------------------------------------------------------------- the form ---
$form                 = New-Object Windows.Forms.Form
$form.Text            = "Interstate '76 - launcher - $($script:GameDir)"
$form.Size            = New-Object Drawing.Size(880, 720)
$form.StartPosition   = 'CenterScreen'
$form.Font            = New-Object Drawing.Font('Segoe UI', 9)

function New-Group($text, $x, $y, $w, $h) {
    $gb = New-Object Windows.Forms.GroupBox
    $gb.Text = $text; $gb.Location = New-Object Drawing.Point($x, $y)
    $gb.Size = New-Object Drawing.Size($w, $h)
    $form.Controls.Add($gb); $gb
}
function New-Label($parent, $text, $x, $y, $w) {
    $l = New-Object Windows.Forms.Label
    $l.Text = $text; $l.Location = New-Object Drawing.Point($x, $y)
    $l.Size = New-Object Drawing.Size($w, 18); $l.AutoEllipsis = $true
    $parent.Controls.Add($l); $l
}
function New-Check($parent, $text, $x, $y, $w) {
    $c = New-Object Windows.Forms.CheckBox
    $c.Text = $text; $c.Location = New-Object Drawing.Point($x, $y)
    $c.Size = New-Object Drawing.Size($w, 22)
    $parent.Controls.Add($c); $c
}

# ---- graphics / mouse (dgVoodoo.conf) ----
$gGfx = New-Group 'Graphics and mouse  (dgVoodoo.conf - applied on Play)' 12 10 840 168

New-Label $gGfx 'Cursor mode' 14 28 90 | Out-Null
$cbCursor = New-Object Windows.Forms.ComboBox
$cbCursor.Location = New-Object Drawing.Point(110, 25)
$cbCursor.Size = New-Object Drawing.Size(140, 22)
$cbCursor.DropDownStyle = 'DropDownList'
[void]$cbCursor.Items.AddRange(@('emulated', 'free', 'raw'))
$gGfx.Controls.Add($cbCursor)
$lblCursor = New-Label $gGfx '' 260 28 560
$lblCursor.ForeColor = [Drawing.Color]::DimGray
# Each mode currently trades one problem for another; say so here rather than letting it be
# rediscovered. "free" is the only mode in which saving over an existing bookmark is known to
# work (verified end to end 2026-09-06); "emulated" confines the pointer to the 640x480 corner,
# which is the old "cannot click YES on the overwrite prompt" fault. "raw" is UNTESTED.
$cursorHelp = @{
    'emulated' = 'Cursor is drawn where you click - but confined to the 640x480 corner. Overwrite prompt reported broken.'
    'free'     = 'Clicks land correctly everywhere (overwrite prompt verified working) - but the drawn cursor is misplaced.'
    'raw'      = 'UNTESTED. dgVoodoo keeps its hands off the mouse entirely - may give correct clicks AND a correct cursor.'
    'custom'   = 'CaptureMouse/FreeMouse are set to a combination this launcher does not name.'
}
$cbCursor.Add_SelectedIndexChanged({ $lblCursor.Text = $cursorHelp[[string]$cbCursor.SelectedItem] })

New-Label $gGfx 'FPS limit' 14 60 90 | Out-Null
$tbFps = New-Object Windows.Forms.TextBox
$tbFps.Location = New-Object Drawing.Point(110, 57); $tbFps.Size = New-Object Drawing.Size(140, 22)
$gGfx.Controls.Add($tbFps)
(New-Label $gGfx '19.2 matches the 1997 sim tick. Raising it is what the frame-rate work is about.' 260 60 560).ForeColor = [Drawing.Color]::DimGray

New-Label $gGfx 'Glide resolution' 14 92 90 | Out-Null
$tbRes = New-Object Windows.Forms.TextBox
$tbRes.Location = New-Object Drawing.Point(110, 89); $tbRes.Size = New-Object Drawing.Size(140, 22)
$gGfx.Controls.Add($tbRes)

New-Label $gGfx 'Scaling' 14 124 90 | Out-Null
$cbScale = New-Object Windows.Forms.ComboBox
$cbScale.Location = New-Object Drawing.Point(110, 121); $cbScale.Size = New-Object Drawing.Size(140, 22)
$cbScale.DropDownStyle = 'DropDownList'
[void]$cbScale.Items.AddRange(@('stretched_ar', 'stretched', 'centered', 'unspecified'))
$gGfx.Controls.Add($cbScale)
(New-Label $gGfx 'stretched_ar keeps 4:3 - the UI is hit-tested in 640x480, so aspect changes move every button.' 260 124 560).ForeColor = [Drawing.Color]::DimGray

# ---- session options (PLAY-i76.ps1 switches) ----
$gPlay = New-Group 'This session  (PLAY-i76.ps1 switches - not saved)' 12 186 840 196

$ckMusic     = New-Check $gPlay 'Music (restores the stock CD soundtrack)'        14 24 330
$ckMissOnly  = New-Check $gPlay 'Music only during missions'                      14 50 330
$ckSkipMov   = New-Check $gPlay 'Skip intro/credits movies (with a mission)'      14 76 330
$ckFfb       = New-Check $gPlay 'Force feedback (opt-in - gains not hand-tuned)'  14 102 330
$ckStick     = New-Check $gPlay 'CH Fighterstick HOTAS layer'                     14 128 330
$ckLossless  = New-Check $gPlay 'Lossless Scaling frame generation'               390 24 330
$ckOpenTrack = New-Check $gPlay 'opentrack head tracking'                         390 50 330

New-Label $gPlay 'Boot straight to mission' 390 80 160 | Out-Null
$tbMission = New-Object Windows.Forms.TextBox
$tbMission.Location = New-Object Drawing.Point(555, 77); $tbMission.Size = New-Object Drawing.Size(120, 22)
$gPlay.Controls.Add($tbMission)
(New-Label $gPlay 'e.g. t01.msn - blank for the normal menus' 390 104 330).ForeColor = [Drawing.Color]::DimGray

New-Label $gPlay 'Music volume' 390 130 160 | Out-Null
$tbVol = New-Object Windows.Forms.TextBox
$tbVol.Location = New-Object Drawing.Point(555, 127); $tbVol.Size = New-Object Drawing.Size(120, 22)
$gPlay.Controls.Add($tbVol)

# Frame-rate preset: one entry per presets\*.psd1 (a data file - Import-PowerShellDataFile runs
# no code). The game process gets the preset's I76_* variables; this window and the shell do not.
New-Label $gPlay 'Frame-rate preset' 14 162 120 | Out-Null
$cbPreset = New-Object Windows.Forms.ComboBox
$cbPreset.Location = New-Object Drawing.Point(140, 159); $cbPreset.Size = New-Object Drawing.Size(170, 22)
$cbPreset.DropDownStyle = 'DropDownList'
$gPlay.Controls.Add($cbPreset)
$lblPreset = New-Label $gPlay '' 320 162 505
$lblPreset.ForeColor = [Drawing.Color]::DimGray
$presetInfo = @{}
foreach ($f in (Get-ChildItem (Join-Path $RepoRoot 'presets\*.psd1') -ErrorAction SilentlyContinue | Sort-Object Name)) {
    try { $d = Import-PowerShellDataFile $f.FullName } catch { continue }
    if (-not $d.Env) { $d.Env = @{} }
    $vars = if ($d.Env.Count) { ($d.Env.Keys | Sort-Object | ForEach-Object { "$_=$($d.Env[$_])" }) -join ' ' } else { 'no engine switches' }
    $presetInfo[$f.BaseName] = "$($d.Summary)  |  $vars  |  $($d.Verified)"
    [void]$cbPreset.Items.Add($f.BaseName)
}
if (-not $cbPreset.Items.Contains('stock')) { [void]$cbPreset.Items.Insert(0, 'stock'); $presetInfo['stock'] = 'no engine switches (the pre-preset behaviour)' }
$cbPreset.Add_SelectedIndexChanged({ $lblPreset.Text = $presetInfo[[string]$cbPreset.SelectedItem]; Update-Cmd })

# ---- install health ----
$gHealth = New-Group 'What is installed  (read-only)' 12 390 840 214
$lvHealth = New-Object Windows.Forms.ListView
$lvHealth.Location = New-Object Drawing.Point(12, 22)
$lvHealth.Size = New-Object Drawing.Size(816, 182)
$lvHealth.View = 'Details'; $lvHealth.FullRowSelect = $true; $lvHealth.GridLines = $false
[void]$lvHealth.Columns.Add('Component', 250)
[void]$lvHealth.Columns.Add('State', 550)
$gHealth.Controls.Add($lvHealth)

# ---- buttons ----
$btnPlay = New-Object Windows.Forms.Button
$btnPlay.Text = 'Play'; $btnPlay.Location = New-Object Drawing.Point(700, 616)
$btnPlay.Size = New-Object Drawing.Size(150, 42); $btnPlay.Font = New-Object Drawing.Font('Segoe UI', 11, [Drawing.FontStyle]::Bold)
$form.Controls.Add($btnPlay)

$btnRefresh = New-Object Windows.Forms.Button
$btnRefresh.Text = 'Refresh'; $btnRefresh.Location = New-Object Drawing.Point(580, 616)
$btnRefresh.Size = New-Object Drawing.Size(100, 42)
$form.Controls.Add($btnRefresh)

$lblCmd = New-Label $form '' 14 618 550
$lblCmd.Size = New-Object Drawing.Size(550, 40)
$lblCmd.ForeColor = [Drawing.Color]::DimGray

# ------------------------------------------------------------------------------ behaviour ---
function Refresh-All {
    $c = Get-Conf
    $cbCursor.SelectedItem = Get-CursorMode
    $tbFps.Text   = "$($c.FPSLimit)"
    $tbRes.Text   = "$($c.Resolution)"
    $cbScale.SelectedItem = "$($c.ScalingMode)"
    $lblCursor.Text = $cursorHelp[(Get-CursorMode)]

    $lvHealth.Items.Clear()
    foreach ($row in Get-Health) {
        $it = New-Object Windows.Forms.ListViewItem($row[0])
        [void]$it.SubItems.Add($row[1])
        $it.ForeColor = switch ($row[2]) {
            'ok'   { [Drawing.Color]::FromArgb(0, 120, 0) }
            'warn' { [Drawing.Color]::FromArgb(180, 110, 0) }
            'bad'  { [Drawing.Color]::FromArgb(190, 0, 0) }
        }
        [void]$lvHealth.Items.Add($it)
    }
    Update-Cmd
}

function Get-PlayArgs {
    $a = @('-GameDir', ('"{0}"' -f $script:GameDir))
    if (-not $ckMusic.Checked)   { $a += '-NoMusic' }
    if ($ckMissOnly.Checked)     { $a += '-MusicMissionOnly' }
    if ($ckFfb.Checked)          { $a += '-Ffb' }
    if (-not $ckStick.Checked)   { $a += '-NoStick' }
    if ($tbMission.Text.Trim())  { $a += @('-Mission', $tbMission.Text.Trim()) }
    if ($ckSkipMov.Checked)      { $a += '-SkipMovies' }
    if ($tbVol.Text.Trim() -and $tbVol.Text.Trim() -ne '550') { $a += @('-MusicVolume', $tbVol.Text.Trim()) }
    $preset = [string]$cbPreset.SelectedItem
    if ($preset -and $preset -ne 'stock') { $a += @('-Preset', $preset) }
    # these two are paths, and "" is how PLAY-i76.ps1 is told to skip them
    if (-not $ckLossless.Checked)  { $a += @('-LosslessScaling', '""') }
    if (-not $ckOpenTrack.Checked) { $a += @('-OpenTrack', '""') }
    $a
}

function Update-Cmd { $lblCmd.Text = 'PLAY-i76.ps1 ' + ((Get-PlayArgs) -join ' ') }

foreach ($c in @($ckMusic, $ckMissOnly, $ckSkipMov, $ckFfb, $ckStick, $ckLossless, $ckOpenTrack)) {
    $c.Add_CheckedChanged({ Update-Cmd })
}
$tbMission.Add_TextChanged({ Update-Cmd })
$tbVol.Add_TextChanged({ Update-Cmd })
$btnRefresh.Add_Click({ Refresh-All })

$btnPlay.Add_Click({
    if (Get-Process i76 -EA SilentlyContinue) {
        [System.Windows.Forms.MessageBox]::Show('The game is already running.', 'Already running') | Out-Null
        return
    }
    # dgVoodoo.conf is read at startup, so write it before launching, not while running
    $pairs = @{}
    switch ([string]$cbCursor.SelectedItem) {
        'emulated' { $pairs['CaptureMouse'] = 'true';  $pairs['FreeMouse'] = 'false' }
        'free'     { $pairs['CaptureMouse'] = 'false'; $pairs['FreeMouse'] = 'false' }
        'raw'      { $pairs['CaptureMouse'] = 'false'; $pairs['FreeMouse'] = 'true'  }
    }
    if ($tbFps.Text.Trim())   { $pairs['FPSLimit'] = $tbFps.Text.Trim() }
    if ($tbRes.Text.Trim())   { $pairs['Resolution'] = $tbRes.Text.Trim() }
    if ($cbScale.SelectedItem) { $pairs['ScalingMode'] = [string]$cbScale.SelectedItem }
    if (-not (Set-Conf $pairs)) { return }

    $play = Join-Path $RepoRoot 'PLAY-i76.ps1'
    Start-Process -FilePath 'powershell' -ArgumentList (
        @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $play)) + (Get-PlayArgs))
    $form.WindowState = 'Minimized'
})

# defaults that match PLAY-i76.ps1's own
$ckMusic.Checked = $true; $ckStick.Checked = $true
$ckLossless.Checked = $true; $ckOpenTrack.Checked = $true
$tbVol.Text = '550'
$cbPreset.SelectedItem = 'stock'

Refresh-All
[void]$form.ShowDialog()
