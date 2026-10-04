<#
  renderer-matrix.ps1 - run every staged renderer candidate on the TEST COPY (<lab>\game-alt) and write one table.

  For each candidate: switch-renderer.ps1 (and nglide-settings.ps1 for nGlide), then
  autotest\proxy-run.ps1 -GameDir <game-alt> -Mission t01 with the candidate's environment, and while in the mission:
    1. full-desktop screenshot                      -> <out>\<candidate>-drive.png
    2. tools\telemetry\frame_stats.py for 8 s       -> fps, dt mean / sd / p99
    3. pointer pin test while driving               -> SetCursorPos to 4 desktop points, GetCursorPos back, GetClipCursor
    4. Esc (in-mission menu), the pin test again    -> + <out>\<candidate>-menu.png
  then the game is killed (proxy-run), the copy goes back to its baseline (switch-renderer -Restore) and nGlide's
  registry values are put back (nglide-settings -Restore). Results: <out>\results.md (+ one .log per candidate).

  Run at the PHYSICAL CONSOLE with no other i76 running. It never touches <lab>\game or the playable install:
  switch-renderer.ps1 and proxy-run.ps1 both refuse those paths.

    .\renderer-matrix.ps1 -DryRun                    # print every command, resolve every source file, change nothing
    .\renderer-matrix.ps1 -SwitchOnly                # switch + status + restore for every candidate, never start the game
    .\renderer-matrix.ps1                            # the whole matrix (about 1 minute per candidate)
    .\renderer-matrix.ps1 -Only nglide-vk-cap179,dxvk
    .\renderer-matrix.ps1 -Repeat 2                  # every candidate twice (the repeat is the noise floor)

  Candidates (all with I76_GLIDE_REFRESH=120 unless stated):
    dgvoodoo            the copy's baseline (control)
    nglide-vk           nGlide 2.10, Vulkan, vsync off, resolution by desktop, 4:3
    nglide-vk-cap179    the same WITHOUT I76_GLIDE_REFRESH, with I76_FPS_CAP=179
    nglide-d3d9         nGlide 2.10, Direct3D 9
    nglide-d3d9-cap179  the same WITHOUT I76_GLIDE_REFRESH, with I76_FPS_CAP=179
    dxvk                dgVoodoo + DXVK 2.7.1 (d3d11.dll, dxgi.dll, d3d10core.dll)
    reshade             dgVoodoo + ReShade 6.8.0 as dxgi.dll, CAS + SMAA only
    ddrawcompat         dgVoodoo Glide + DDrawCompat 0.7.1 as the DirectDraw provider (dgVoodoo's D3DImm.dll removed)
#>
param(
    [string]$GameDir = "",
    [string]$Mission = "t01",
    [string[]]$Only = @(),
    [int]$Seconds = 8,
    [int]$Repeat = 1,
    [int]$WaitMinutes = 5,          # how long to wait for another i76 run (the integrator's) to finish before each candidate
    [string]$Out = "",
    [switch]$DryRun,
    [switch]$SwitchOnly
)
$ErrorActionPreference = "Stop"
$Lab = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $GameDir) { $GameDir = Join-Path $Lab "game-alt" }
$Switch = Join-Path $PSScriptRoot "switch-renderer.ps1"
$NgSet = Join-Path $PSScriptRoot "nglide-settings.ps1"
$Proxy = Join-Path $Lab "autotest\proxy-run.ps1"
$FrameStats = "C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py"
$Refs = Join-Path $Lab "refs\renderers"
if (-not $Out) { $Out = Join-Path $Lab ("autotest\runs\renderers\" + (Get-Date -Format "yyyyMMdd-HHmmss")) }

$R120 = @{ I76_GLIDE_REFRESH = "120" }
$Cap179 = @{ I76_FPS_CAP = "179" }
$Candidates = @(
    @{ Name = "dgvoodoo";           Switch = @{ Renderer = "dgvoodoo" };                                                                          Env = $R120 }
    @{ Name = "nglide-vk";          Switch = @{ Renderer = "nglide"; Source = "$Refs\nglide" };  NGlide = "vulkan";                               Env = $R120 }
    @{ Name = "nglide-vk-cap179";   Switch = @{ Renderer = "nglide"; Source = "$Refs\nglide" };  NGlide = "vulkan";                               Env = $Cap179 }
    @{ Name = "nglide-d3d9";        Switch = @{ Renderer = "nglide"; Source = "$Refs\nglide" };  NGlide = "d3d9";                                 Env = $R120 }
    @{ Name = "nglide-d3d9-cap179"; Switch = @{ Renderer = "nglide"; Source = "$Refs\nglide" };  NGlide = "d3d9";                                 Env = $Cap179 }
    @{ Name = "dxvk";               Switch = @{ Renderer = "dgvoodoo"; Overlay = "dxvk"; OverlaySource = "$Refs\dxvk\dxvk-2.7.1" };               Env = $R120 }
    @{ Name = "reshade";            Switch = @{ Renderer = "dgvoodoo"; Overlay = "reshade"; ReShadeAs = "dxgi"; OverlaySource = "$Refs\reshade" }; Env = $R120; ReShade = $true }
    @{ Name = "ddrawcompat";        Switch = @{ Renderer = "dgvoodoo"; DDraw = "ddrawcompat"; DDrawSource = "$Refs\ddrawcompat" };                Env = $R120 }
)
if ($Only.Count) {
    $unknown = $Only | Where-Object { $_ -notin $Candidates.Name }
    if ($unknown) { throw "unknown candidate(s): $($unknown -join ', ') (known: $($Candidates.Name -join ', '))" }
    $Candidates = $Candidates | Where-Object { $_.Name -in $Only }
}
# files each candidate needs (checked before anything is switched; -DryRun prints them)
function Needs($c) {
    $n = @()
    if ($c.Switch.Renderer -eq "nglide") { $n += "$Refs\nglide\glide2x.dll" }
    if ($c.Switch.Overlay -eq "dxvk") { $n += "$Refs\dxvk\dxvk-2.7.1\x32\d3d11.dll", "$Refs\dxvk\dxvk-2.7.1\x32\dxgi.dll" }
    if ($c.Switch.Overlay -eq "reshade") { $n += "$Refs\reshade\ReShade32.dll", "$Refs\reshade\Shaders\CAS.fx", "$Refs\reshade\Shaders\SMAA.fx", "$Refs\reshade\Shaders\SMAA.fxh", "$Refs\reshade\Shaders\ReShade.fxh", "$Refs\reshade\Shaders\ReShadeUI.fxh", "$Refs\reshade\Textures\AreaTex.png", "$Refs\reshade\Textures\SearchTex.png", "$PSScriptRoot\reshade\ReShade.ini", "$PSScriptRoot\reshade\i76-cas-smaa.ini" }
    if ($c.Switch.DDraw -eq "ddrawcompat") { $n += "$Refs\ddrawcompat\ddraw.dll" }
    $n
}
function ArgText($h) { ($h.Keys | Sort-Object | ForEach-Object { "-$_ `"$($h[$_])`"" }) -join " " }
function EnvText($h) { "@{ " + (($h.Keys | Sort-Object | ForEach-Object { "$_ = `"$($h[$_])`"" }) -join "; ") + " }" }
function Run-Env($c) {
    $e = @{}; foreach ($k in $c.Env.Keys) { $e[$k] = $c.Env[$k] }
    if ($c.NGlide) { $ne = & $NgSet -Backend $c.NGlide -EnvOnly; foreach ($k in $ne.Keys) { $e[$k] = $ne[$k] } }
    $e
}
$LeakVars = "I76_GLIDE_REFRESH", "I76_FPS_CAP", "NGLIDE_BACKEND", "NGLIDE_RESOLUTION", "NGLIDE_ASPECT", "NGLIDE_REFRESH", "NGLIDE_VSYNC", "NGLIDE_GAMMA", "NGLIDE_SPLASH"
function Clear-RunEnv { foreach ($v in $LeakVars) { Remove-Item "Env:$v" -ErrorAction SilentlyContinue } }   # proxy-run clears its own list, not these

"matrix   : $($Candidates.Count) candidate(s) x $Repeat on $GameDir, mission $Mission, frame_stats $Seconds s"
"out      : $Out"
$missing = 0
foreach ($c in $Candidates) {
    "--- $($c.Name)"
    "  switch : $Switch -GameDir `"$GameDir`" $(ArgText $c.Switch)"
    if ($c.NGlide) { "  nglide : $NgSet -Backend $($c.NGlide)      (HKCU\Software\Zeus Software\nGlide2; the same values also go in as NGLIDE_* env)" }
    if ($c.ReShade) { "  reshade: copy $PSScriptRoot\reshade\{ReShade.ini,i76-cas-smaa.ini} -> $Refs\reshade\ (fresh preset each run)" }
    "  run    : $Proxy -GameDir `"$GameDir`" -Mission $Mission -Hold 0 -Env $(EnvText (Run-Env $c)) -Run { screenshot; frame_stats.py $Seconds; pin test; Esc; pin test; screenshot }"
    "  restore: $Switch -GameDir `"$GameDir`" -Restore" + $(if ($c.NGlide) { " ; $NgSet -Restore" })
    foreach ($f in (Needs $c)) { if (Test-Path -LiteralPath $f) { "  ok     : $f" } else { "  MISSING: $f"; $missing++ } }
}
foreach ($f in $Switch, $NgSet, $Proxy, $FrameStats) { if (-not (Test-Path $f)) { "MISSING: $f"; $missing++ } }
if (-not (Test-Path (Join-Path $GameDir "i76.exe"))) { "MISSING: $GameDir\i76.exe (run make-renderer-copy.ps1 -HardLinkAssets)"; $missing++ }
if ($DryRun) {
    if (Test-Path (Join-Path $GameDir "i76.exe")) { "--- current state of the copy"; & $Switch -GameDir $GameDir -Status }
    "dry run  : nothing switched, nothing started. missing files: $missing"
    return
}
if ($missing) { throw "$missing required file(s) missing - see the list above" }

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
if (-not ("RM.U" -as [type])) {
    Add-Type -Name U -Namespace RM -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern bool GetClipCursor(out RECT r);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
[StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
'@
}
[void][RM.U]::SetProcessDPIAware()
function Shot([string]$path) {
    $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $vs.Width, $vs.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try { $g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $bmp.Size); $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png) } finally { $g.Dispose(); $bmp.Dispose() }
    "$($vs.Width)x$($vs.Height)"
}
# pin test: ask for four desktop points (far right, 4:3 right edge on a 3440 panel, centre, far left), read back where
# the pointer really is, and the OS clip rectangle. Raw numbers only: what counts as "pinned" depends on the wrapper.
function Pin {
    $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $pts = @(@(($vs.Right - 40), 700), @(2600, 700), @([int]($vs.X + $vs.Width / 2), 700), @(($vs.X + 40), 700))
    $o = foreach ($p in $pts) {
        [void][RM.U]::SetCursorPos($p[0], $p[1]); Start-Sleep -Milliseconds 300
        $q = New-Object RM.U+POINT; [void][RM.U]::GetCursorPos([ref]$q); "$($p[0]),$($p[1])->$($q.X),$($q.Y)"
    }
    $r = New-Object RM.U+RECT; [void][RM.U]::GetClipCursor([ref]$r)
    ($o -join " ") + " clip $($r.L),$($r.T)-$($r.R),$($r.B)"
}
function WinRect {
    $p = Get-GamePid; if (-not $p) { return "no window" }
    $w = New-Object RM.U+RECT; $c = New-Object RM.U+RECT; $o = New-Object RM.U+POINT
    [void][RM.U]::GetWindowRect($p.MainWindowHandle, [ref]$w); [void][RM.U]::GetClientRect($p.MainWindowHandle, [ref]$c); [void][RM.U]::ClientToScreen($p.MainWindowHandle, [ref]$o)
    "window $($w.L),$($w.T)-$($w.R),$($w.B) client $($c.R)x$($c.B) at $($o.X),$($o.Y)"
}
function Busy { @(Get-Process | Where-Object { $_.ProcessName -like "i76*" -or $_.ProcessName -like "nitro*" }).Count -gt 0 -or (Test-Path (Join-Path $GameDir ".console-test.lock")) }
function Wait-Free {
    $until = (Get-Date).AddMinutes($WaitMinutes)
    while (Busy) { if ((Get-Date) -gt $until) { return $false }; Write-Host "  waiting: another i76 run / lock ..." -ForegroundColor Yellow; Start-Sleep -Seconds 10 }
    $true
}

if (-not $SwitchOnly -and [System.Windows.Forms.SystemInformation]::TerminalServerSession) { throw "this is an RDP session: Glide will not initialise. Run at the physical console (tools\rdp-to-console.cmd)." }
New-Item -ItemType Directory -Force $Out | Out-Null
$rows = New-Object System.Collections.ArrayList
$hz0 = (Get-CimInstance Win32_VideoController | Select-Object -First 1).CurrentRefreshRate

foreach ($c in $Candidates) {
    for ($rep = 1; $rep -le $Repeat; $rep++) {
        $tag = if ($Repeat -gt 1) { "$($c.Name)-r$rep" } else { $c.Name }
        Write-Host "=== $tag" -ForegroundColor Cyan
        $M = @{ boot = ""; stats = ""; pinDrive = ""; pinMenu = ""; win = ""; shot = ""; note = "" }
        $log = Join-Path $Out "$tag.log"
        if (-not (Wait-Free)) { $M.note = "skipped: another i76 run or the copy's lock was still there after $WaitMinutes min"; [void]$rows.Add(@{ tag = $tag; M = $M; hz = "" }); continue }
        $hz = (Get-CimInstance Win32_VideoController | Select-Object -First 1).CurrentRefreshRate
        try {
            if ($c.ReShade) { Copy-Item "$PSScriptRoot\reshade\ReShade.ini", "$PSScriptRoot\reshade\i76-cas-smaa.ini" "$Refs\reshade\" -Force }
            $sw = $c.Switch
            (& $Switch -GameDir $GameDir @sw) | Tee-Object -FilePath $log | ForEach-Object { "  $_" }
            if ($c.NGlide) { (& $NgSet -Backend $c.NGlide) | Add-Content $log }
            (& $Switch -GameDir $GameDir -Status) | Add-Content $log
            if ($SwitchOnly) { $M.note = "switch only"; continue }
            Clear-RunEnv
            $block = {
                Start-Sleep -Seconds 4
                $M.win = WinRect
                $M.shot = Shot (Join-Path $Out "$tag-drive.png")
                $M.stats = (& python $FrameStats $Seconds $tag 2>&1 | Out-String).Trim()
                $M.pinDrive = Pin
                Send-Key $VK.ESC; Start-Sleep -Milliseconds 1500
                $M.pinMenu = Pin
                [void](Shot (Join-Path $Out "$tag-menu.png"))
            }
            $e = Run-Env $c
            $o = & $Proxy -GameDir $GameDir -Mission $Mission -Hold 0 -Env $e -Run $block *>&1 | ForEach-Object { "$_" }
            $o | Add-Content $log
            $M.boot = (($o | Where-Object { $_ -match "in mission after|exited during boot|not in a mission|refusing|already running|lock held" }) -join "; ") -replace '\[proxy-run\] ', ''
            $bad = $o | Where-Object { $_ -match "CRASH|UNEXPECTED" }
            if ($bad) { $M.note = (($bad | Select-Object -First 2) -join "; ").Trim() }
            foreach ($f in "u32x.log", "DDrawCompat-i76.log", "ReShade.log", "i76_d3d11.log", "i76_dxgi.log") {
                $p = Join-Path $GameDir $f; if (Test-Path $p) { Copy-Item $p (Join-Path $Out "$tag-$f") -Force }
            }
        } catch {
            $M.note = ("ERROR: " + $_.Exception.Message + " " + $M.note).Trim()
            Write-Host "  $($M.note)" -ForegroundColor Red
        } finally {
            Clear-RunEnv
            Get-Process | Where-Object { $_.ProcessName -like "i76*" -and $_.Path -like "$GameDir\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
            try { (& $Switch -GameDir $GameDir -Restore) | Add-Content $log } catch { $M.note += " RESTORE FAILED: $($_.Exception.Message)"; Write-Host "  restore failed: $($_.Exception.Message)" -ForegroundColor Red }
            if ($c.NGlide) { try { (& $NgSet -Restore) | Add-Content $log } catch { $M.note += " NGLIDE RESTORE FAILED: $($_.Exception.Message)" } }
            [void]$rows.Add(@{ tag = $tag; M = $M; hz = $hz })
        }
    }
}

# --- markdown
function Cell($s) { ("$s" -replace '\|', '/' -replace '\r?\n', ' ').Trim() }
$md = New-Object System.Collections.ArrayList
[void]$md.Add("# Renderer matrix $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
[void]$md.Add("")
[void]$md.Add("Copy: ``$GameDir``; mission $Mission; frame_stats $Seconds s; n = $Repeat per candidate; desktop refresh at start $hz0 Hz." + $(if ($SwitchOnly) { " **Switch only: the game was not started.**" }))
[void]$md.Add('Pin test: `asked->got` for four desktop points, then the OS clip rectangle. Screenshots and per-candidate logs are beside this file.')
[void]$md.Add("")
[void]$md.Add("| candidate | Hz | boot | fps | dt mean / sd / p99 (ms) | window | pin, driving | pin, Esc menu | notes |")
[void]$md.Add("|---|---|---|---|---|---|---|---|---|")
foreach ($r in $rows) {
    $m = $r.M; $fps = ""; $dt = ""
    if ($m.stats -match '= ([\d.]+) fps \| dt mean ([\d.]+) ms sd ([\d.]+) p99 ([\d.]+)') { $fps = $Matches[1]; $dt = "$($Matches[2]) / $($Matches[3]) / $($Matches[4])" }
    elseif ($m.stats) { $dt = $m.stats }
    [void]$md.Add("| $($r.tag) | $($r.hz) | $(Cell $m.boot) | $fps | $(Cell $dt) | $(Cell $m.win) | $(Cell $m.pinDrive) | $(Cell $m.pinMenu) | $(Cell $m.note) |")
}
[void]$md.Add("")
[void]$md.Add("Final state of the copy:")
[void]$md.Add('```')
(& $Switch -GameDir $GameDir -Status) | ForEach-Object { [void]$md.Add($_) }
(& $NgSet -Show) | ForEach-Object { [void]$md.Add($_) }
[void]$md.Add('```')
$res = Join-Path $Out "results.md"
Set-Content $res $md -Encoding utf8
$md
"results  : $res"
