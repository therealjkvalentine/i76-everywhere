<#
  vptr-test.ps1 - the pass criteria of milestone A1 "one pointer" (i76-everywhere docs\records\MENU-REBUILD-DESIGN.md section 7;
  docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md section 9) for a u32x build with the vptr block, run on the SANDBOX
  (C:\Users\james\i76-uncap-lab\game) from the physical console with nobody playing. It takes the mouse, the keyboard
  and the screen for 10-15 minutes (-Stage all).

    powershell -ExecutionPolicy Bypass -File vptr-test.ps1                      # everything, src\u32x_new.dll
    powershell -ExecutionPolicy Bypass -File vptr-test.ps1 -Stage shell,escmenu # only these stages
    powershell -ExecutionPolicy Bypass -File vptr-test.ps1 -Dll ..\src\u32x_newlog.dll -Stage shell   # log build (captures\save\u32x.log)
    powershell -ExecutionPolicy Bypass -File vptr-test.ps1 -Extra "I76_U32X_VPTR_WIDEN=1" -Stage shell # an experiment switch on top

  GROUND TRUTH SINCE 2026-10-02 (late): game\dgVoodoo.conf is accepted by dgVoodoo now (it was being rejected and the
  2020 global conf ran instead). Mission and Esc menu: the clip is the whole client and the pointer is free, so the
  hand is ON the drawn item there (frame map; the computed box is gone from u32x). Shell: dgVoodoo holds a 640x480
  corner clip (1:1) and takes it back when it is moved (run 20261002-234050: moving it by default made the regime
  flap and broke leg-b 2 of 3), so the shell mode is explicit: hand in the corner box, drawn pointer (the shell's
  pencil and the u32xVptr cursor window) on the picture. The script still measures the clip before every move and
  never assumes a regime. "One pointer" passes in either form: the OS arrow already on the drawn point (no cursor
  window), or the u32xVptr cursor window on it.

  Stages (each launches and closes the game itself; all but "control" run with I76_U32X_VPTR=1):
    shell    garage via saves\garage-ui.ps1 -Start; 8 UI targets: the OS pointer is put where the measured box says the
             hand must be (the drawn position when the clip is the picture rect or free), the shell's mouse object
             [[0x100cc514]+0x2c/+0x30] is read back (pass: within 1 px, 8 of 8), and a visible pointer must be on the
             picture position of the target: the hand itself (within 1 UI unit) or the u32xVptr window (within 2 px);
             a 640x480 capture is saved per target (the pencil is checked by eye), then the pointer-speed measurement
             (300 px of hand -> UI delta, 100 +-1 when the box is picture-sized). -Runs times (default 2).
    widen    NOT in "all": the shell stage once with the experiment I76_U32X_VPTR_WIDEN=1 (clip moved onto the picture).
    save     MOUSE doc Test B: SAVE BOOKMARK, 10 s idle, gate [shell+0x43224] must stay 1, row click, SAVE twice, YES;
             pass: savegame.dir rewritten. The save set is copied first and put back afterwards.
    route    saves\leg-b.ps1 -WantFile save003 -WantRow 3 -RowUy 262, -RouteRuns times (default 3); pass: every run
             completes through B1.10. The last run stays in the mission: the cursor window must be hidden there.
    option6  option6-trip-test.ps1 -Mode all120; pass: "engine up: True".
    escmenu  test-escmenu.ps1 -Stage open (t01, Esc); for Play Options and Exit the hand goes to the DRAWN item
             (or to the box position if a clip box was measured while driving), a visible pointer must be on the drawn
             item (hand or cursor window, within 3 px), then the click is made; pass: Exit takes [0x4fe534] out of 0x10.
    melee    menu-route-test.ps1 (MELEE -> INSTANT MELEE through the menus); pass: enter-melee exit 0.
    control  I76_U32X_VPTR unset, once: no cursor window exists, the shell reads the OS pointer as before (1:1 in the
             corner clip), and the Esc-menu Exit is hit from the drawn position (frame map; from the box position only
             if a box was measured).

  The build under test is copied over game\u32x.dll for the run and the previous file is put back at the end (verified
  by md5) unless -KeepDll. -NoInstall tests whatever is installed. Results: runs\vptr\<timestamp>\log.txt, captures
  beside it, a PASS / FAIL / INFO table at the end; the exit code is the number of FAIL rows.

  Not verified offline (this script was written without running the game): the Save Bookmark screen's row and SAVE
  button coordinates (-SaveRow / -SaveBtn; the defaults are the Load Bookmark screen's) and the memory signature of
  "Play Options opened" (reported as INFO with a capture, not as a pass or a fail).
#>
param(
    [string[]]$Stage = @("all"),
    [string]$Dll = "C:\Users\james\i76-uncap-lab\src\u32x_new.dll",
    [string]$Bookmark = "save003", [int]$Row = 3, [int]$RowUy = 262,
    [int]$Runs = 2, [int]$RouteRuns = 3,
    [string]$Extra = "",                       # e.g. "I76_U32X_VPTR_WIDEN=1;I76_U32X_VPTR_HIDEOS=0"
    [string]$SaveRow = "320,262", [string]$SaveBtn = "352,428", [string]$YesBtn = "393,258",
    [string]$PlayOptions = "240,170", [string]$Exit = "432,445",   # Esc-menu items, frame coordinates (MOUSE doc 5a)
    [switch]$NoInstall, [switch]$KeepDll, [switch]$KeepSaves
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Lab = "C:\Users\james\i76-uncap-lab"; $G = Join-Path $Lab "game"
$SS = "C:\Users\james\i76-map\shell\tools\shellstate.ps1"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Run = Join-Path $Here "runs\vptr\$ts"; New-Item -ItemType Directory -Force $Run | Out-Null
$LogPath = Join-Path $Run "log.txt"
$valid = "all", "shell", "widen", "save", "route", "option6", "escmenu", "melee", "control"
$Stage = @($Stage | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ })
foreach ($s in $Stage) { if ($valid -notcontains $s) { throw "unknown stage '$s' (one of: $($valid -join ', '))" } }
if ($Stage -contains "all") { $Stage = "shell", "save", "route", "option6", "escmenu", "melee", "control" }

function Log([string]$m, [string]$c = "Gray") { Add-Content -Path $LogPath -Value $m -Encoding UTF8; Write-Host $m -ForegroundColor $c }
$script:Results = @()
function Check([string]$name, $ok, [string]$detail) {
    $v = if ($ok -eq $null) { "INFO" } elseif ($ok) { "PASS" } else { "FAIL" }
    $script:Results += [pscustomobject]@{ Check = $name; Result = $v; Detail = $detail }
    $col = "Yellow"; if ($v -eq "PASS") { $col = "Green" } elseif ($v -eq "FAIL") { $col = "Red" }
    Log ("  [{0}] {1}: {2}" -f $v, $name, $detail) $col
}

# ---- refuse the wrong session / a busy sandbox ----------------------------------------------------------------------
Add-Type -AssemblyName System.Windows.Forms
if ([System.Windows.Forms.SystemInformation]::TerminalServerSession) { throw "this is an RDP session: the game does not start here (AGENTS.md). Run it at the console." }
if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76* process is running" }
if (Test-Path "$G\.console-test.lock") { throw "$G\.console-test.lock exists (another test owns the sandbox)" }
if (-not (Test-Path $SS)) { throw "shellstate.ps1 not found at $SS" }

. "$Here\lib\focuslib.ps1"; . "$Here\lib\inputlib.ps1"; . "$Here\lib\maplib.ps1"; . "$Here\lib\memlib.ps1"
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class VP {
  public delegate bool EP(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EP cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern int GetClassNameA(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool GetClipCursor(out RECT r);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorInfo(ref CURSORINFO ci);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [StructLayout(LayoutKind.Sequential)] public struct CURSORINFO { public int cbSize; public int flags; public IntPtr hCursor; public POINT pt; }
  // the u32x cursor window of process pid: class "u32xVptr" (owned by the game window, so it is not MainWindowHandle)
  public static IntPtr FindVptr(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint p; GetWindowThreadProcessId(h, out p); if (p != pid) return true;
      var sb = new StringBuilder(64); GetClassNameA(h, sb, 64);
      if (sb.ToString() == "u32xVptr") { found = h; return false; }
      return true; }, IntPtr.Zero);
    return found;
  }
  public static bool OsCursorShowing() { var ci = new CURSORINFO(); ci.cbSize = Marshal.SizeOf(typeof(CURSORINFO)); GetCursorInfo(ref ci); return (ci.flags & 1) != 0; }
}
"@

function Md5([string]$p) { (Get-FileHash $p -Algorithm MD5).Hash.ToLower() }
function Run-Child([string]$script, [string]$argLine, [string]$outName) {
    # a child powershell with its output in a file: the harness scripts use exit / throw / Write-Host freely
    $of = Join-Path $Run $outName
    cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File `"$script`" $argLine > `"$of`" 2>&1"
    return @(Get-Content $of -ErrorAction SilentlyContinue)
}
function Set-Switches([bool]$on, [string]$more = "") {
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76_U32X_*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    Remove-Item Env:U32X_TEST_ENV -ErrorAction SilentlyContinue
    if ($on) {
        $pairs = @("I76_U32X_VPTR=1") + @(($Extra + ";" + $more) -split ";" | Where-Object { $_ -match "^I76_U32X_\w+=" })
        foreach ($kv in $pairs) { $a = $kv -split "=", 2; Set-Item "Env:$($a[0])" $a[1] }
        $env:U32X_TEST_ENV = $pairs -join ";"          # leg-b.ps1 scrubs I76* and re-applies this
    }
    Log ("switches: " + ((Get-ChildItem Env: | Where-Object { $_.Name -like "I76_U32X_*" } | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join " ") + $(if (-not $on) { "(none: VPTR off)" }))
}
function Game { Get-GamePid }
function Close-Game { Run-Child "$Here\saves\garage-ui.ps1" "-Close" "close-$(Get-Date -Format HHmmss).out" | Out-Null; Start-Sleep -Seconds 1 }
function Focus { $p = Game; if ($p) { Force-Foreground $p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 300 } }

# live geometry: client, picture (4:3 letterbox), clip box and its kind - the same arithmetic as u32x.c
function Geo {
    $p = Game; if (-not $p) { throw "no game" }
    $h = $p.MainWindowHandle
    $rc = New-Object VP+RECT; [void][VP]::GetClientRect($h, [ref]$rc)
    $org = New-Object VP+POINT; [void][VP]::ClientToScreen($h, [ref]$org)
    $c = New-Object VP+RECT; [void][VP]::GetClipCursor([ref]$c)
    $scale = [Math]::Min($rc.R / 640.0, $rc.B / 480.0)
    $w = $c.R - $c.L; $hh = $c.B - $c.T
    $kind = if ($w -ge $rc.R -and $hh -ge $rc.B) { "free" } elseif ([Math]::Abs($w - 640) -le 1 -and [Math]::Abs($hh - 480) -le 1) { "ui" } else { "box" }
    [pscustomobject]@{ Pid = $p.Id; Hwnd = $h; CW = $rc.R; CH = $rc.B; OX = $org.X; OY = $org.Y; Scale = $scale
        PicL = $org.X + [int][Math]::Floor(($rc.R - 640 * $scale) / 2); PicT = $org.Y + [int][Math]::Floor(($rc.B - 480 * $scale) / 2)
        Clip = $c; ClipW = $w; ClipH = $hh; Kind = $kind
        Text = "client $($rc.R)x$($rc.B) at ($($org.X),$($org.Y)) scale $scale picture x $($org.X + [int][Math]::Floor(($rc.R - 640 * $scale) / 2)) clip $($c.L),$($c.T)-$($c.R),$($c.B) [$kind]" }
}
# where the hand must be for the shell to read UI (ux,uy): the inverse of vptr_shell_getpos (VPTR on), or of the
# regime rule (VPTR off: a UI-sized clip is 1:1, anything else is the picture map)
function Hand-ForUi($geo, [int]$ux, [int]$uy, [bool]$vptr) {
    if ($geo.Kind -eq "ui") { return @(($geo.Clip.L + $ux), ($geo.Clip.T + $uy)) }
    if ($geo.Kind -eq "box" -and $vptr) {
        return @(($geo.Clip.L + [int][Math]::Floor(($ux * $geo.ClipW + $geo.ClipW / 2) / 640)), ($geo.Clip.T + [int][Math]::Floor(($uy * $geo.ClipH + $geo.ClipH / 2) / 480)))
    }
    return @(([int]($geo.PicL + $ux * $geo.Scale + $geo.Scale / 2)), ([int]($geo.PicT + $uy * $geo.Scale + $geo.Scale / 2)))
}
function Pic-ForUi($geo, [double]$ux, [double]$uy) { return @(([int][Math]::Floor($geo.PicL + $ux * $geo.Scale + 0.5)), ([int][Math]::Floor($geo.PicT + $uy * $geo.Scale + 0.5))) }
function Vptr-Win($geo) {
    $h = [VP]::FindVptr([uint32]$geo.Pid)
    if ($h -eq [IntPtr]::Zero) { return [pscustomobject]@{ Exists = $false; Visible = $false; X = -1; Y = -1; W = 0; H = 0 } }
    $r = New-Object VP+RECT; [void][VP]::GetWindowRect($h, [ref]$r)
    [pscustomobject]@{ Exists = $true; Visible = [VP]::IsWindowVisible($h); X = $r.L; Y = $r.T; W = $r.R - $r.L; H = $r.B - $r.T }
}
function Shell-State {
    $l = & $SS -Once 2>$null | Where-Object { "$_" -match "mouse=\(" } | Select-Object -First 1
    if (-not $l) { return $null }
    $x = -1; $y = -1; if ("$l" -match "mouse=\((-?\d+),(-?\d+)\)") { $x = [int]$Matches[1]; $y = [int]$Matches[2] }
    $top = ""; if ("$l" -match "top=(\S+)") { $top = $Matches[1] }
    [pscustomobject]@{ X = $x; Y = $y; Top = $top; Text = ("$l" -replace "\s+", " ").Trim() }
}
function Shell-I32([int64]$va) {      # a dword of i76shell.dll at its preferred-base VA (needs [SS] from shellstate.ps1)
    $p = Game; $h = [SS]::OpenProcess(0x0410, $false, $p.Id); if ($h -eq [IntPtr]::Zero) { return $null }
    try { $b = [SS]::Base($h, "i76shell.dll"); if ($b -eq 0) { return $null }; return [SS]::I32($h, $va + ($b - 0x10000000)) } finally { [void][SS]::CloseHandle($h) }
}
function Move-Hand([int]$x, [int]$y, [int]$settle = 350) { [void][VP]::SetCursorPos($x, $y); Start-Sleep -Milliseconds $settle }
function Click-Here([int]$settle = 900) { [VP]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 70; [VP]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds $settle }
function Click-UiPoint($geo, [string]$xy, [bool]$vptr, [string]$what, [int]$settle = 900) {
    $v = $xy -split ","; $hnd = Hand-ForUi $geo ([int]$v[0]) ([int]$v[1]) $vptr
    Move-Hand $hnd[0] $hnd[1]; $m = Shell-State; Click-Here $settle
    Log ("    click {0} UI ({1}) hand ({2},{3}) shell-mouse ({4},{5})" -f $what, $xy, $hnd[0], $hnd[1], $m.X, $m.Y)
}
function Start-Garage([string]$tag) {
    $o = Run-Child "$Here\saves\garage-ui.ps1" "-Start $Bookmark -Row $Row" "garage-start-$tag.out"
    $o | Where-Object { $_ -match "B1\.|RUN ERROR|Abort|no sandbox" } | ForEach-Object { Log "    $_" }
    $p = Game; if (-not $p) { return $false }
    Focus; Init-CursorMap | Out-Null
    $s = Shell-State; Log "    shell: $($s.Text)"
    return ($s -and $s.Text -match "garage")
}

# ============================================================== stages ==============================================
$Targets = @(@(40, 40), @(320, 240), @(610, 60), @(625, 455), @(100, 450), @(258, 48), @(470, 300), @(560, 130))

function Stage-Shell([string]$n, [string]$more = "") {
    Log "=== shell, run $n (VPTR=1 $more) ===" "Cyan"
    Set-Switches $true $more
    if (-not (Start-Garage "shell$n")) { Check "shell r$n garage reached" $false "garage-ui -Start did not reach the garage (see garage-start-shell$n.out)"; Close-Game; return }
    try {
        Start-Sleep -Milliseconds 1200          # let u32x move the corner clip (3 attempts, 250 ms apart) or give up
        $geo = Geo; Log "    geometry: $($geo.Text)"
        $hit = 0; $drawn = 0; $byHand = 0; $byWin = 0; $worst = 0
        foreach ($t in $Targets) {
            $geo = Geo                                # the clip is measured before every move: no regime is assumed
            $hnd = Hand-ForUi $geo $t[0] $t[1] $true
            Move-Hand $hnd[0] $hnd[1]
            $m = Shell-State; $w = Vptr-Win $geo; $e = Pic-ForUi $geo $t[0] $t[1]
            $pt = New-Object VP+POINT; [void][VP]::GetCursorPos([ref]$pt)
            $d = [Math]::Max([Math]::Abs($m.X - $t[0]), [Math]::Abs($m.Y - $t[1]))
            $dh = [Math]::Max([Math]::Abs($pt.X - $e[0]), [Math]::Abs($pt.Y - $e[1]))     # the real arrow vs the drawn point
            $dw = if ($w.Visible) { [Math]::Max([Math]::Abs($w.X - $e[0]), [Math]::Abs($w.Y - $e[1])) } else { 9999 }
            $handOn = ($dh -le [Math]::Ceiling($geo.Scale) + 1)
            if ($d -le 1) { $hit++ }
            if ($handOn -and -not $w.Visible) { $drawn++; $byHand++ } elseif ($dw -le 2) { $drawn++; $byWin++ }
            $worst = [Math]::Max($worst, $d)
            Log ("    target ({0},{1}) [{14}] hand ({2},{3}) shell-mouse ({4},{5}) d={6} | drawn point ({10},{11}): hand off by {12}, cursor window visible={7} at ({8},{9}) | os arrow showing={13}" -f `
                $t[0], $t[1], $pt.X, $pt.Y, $m.X, $m.Y, $d, $w.Visible, $w.X, $w.Y, $e[0], $e[1], $dh, [VP]::OsCursorShowing(), $geo.Kind)
            if ("$n" -eq "1" -or "$n" -eq "widen") { Capture-UI (Join-Path $Run ("shell-{0}-{1}_{2}.png" -f $n, $t[0], $t[1])) | Out-Null }
        }
        Check "shell r$n hit point = target (within 1 px)" ($hit -eq $Targets.Count) "$hit of $($Targets.Count), worst $worst px, box [$($geo.Kind)] $($geo.ClipW)x$($geo.ClipH)"
        Check "shell r$n one pointer on the drawn point" ($drawn -eq $Targets.Count) "$drawn of $($Targets.Count): $byHand by the OS arrow itself (no cursor window), $byWin by the cursor window (within 2 px)"
        if ($more -match "WIDEN=1") { Check "shell r$n experiment WIDEN=1: hand on the drawn item" $null "box [$($geo.Kind)] $($geo.ClipW)x$($geo.ClipH) at the end; $byHand of $($Targets.Count) by the OS arrow, $byWin by the cursor window ([ui] = dgVoodoo took the clip back)" }
        else { Check "shell r$n shell mode: hand in the corner box, cursor window on the picture" ($geo.Kind -eq "ui" -and $byWin -eq $Targets.Count) "box [$($geo.Kind)] $($geo.ClipW)x$($geo.ClipH), cursor window on $byWin of $($Targets.Count) drawn points" }
        if ("$n" -eq "1" -or "$n" -eq "widen") { Check "shell r$n pencil hot spot = target (within 2 px)" $null "by eye: $Run\shell-$n-<x>_<y>.png, 1 image px = 1 UI unit" }
        # pointer speed: 300 px of hand inside the box
        $geo = Geo
        if ($geo.Kind -ne "free" -and $geo.ClipW -ge 420) {
            $y = $geo.Clip.T + [int]($geo.ClipH / 2); $x0 = $geo.Clip.L + 60
            Move-Hand $x0 $y; $a = Shell-State; Move-Hand ($x0 + 300) $y; $b = Shell-State
            $delta = $b.X - $a.X; $expect = [Math]::Round(300 * 640.0 / $geo.ClipW, 1)
            $detail = "300 px of hand -> UI delta $delta (this box, $($geo.ClipW) px wide, gives $expect; the milestone's 100 +-1 needs a picture-sized box)"
            if ([Math]::Abs($delta - 100) -le 1) { Check "shell r$n pointer speed 1 picture px per px of hand" $true $detail }
            elseif ($geo.Kind -eq "ui") { Check "shell r$n pointer speed 1 picture px per px of hand" $null ("NOT MET in the 640x480 corner box - the shell mode under this conf, by design: " + $detail) }
            else { Check "shell r$n pointer speed 1 picture px per px of hand" $false $detail }
        } else { Check "shell r$n pointer speed" $null "not measured: clip is [$($geo.Kind)] $($geo.ClipW)x$($geo.ClipH)" }
        $s = Shell-State; Check "shell r$n still in the garage after the moves" ($s.Text -match "garage") $s.Text
    } finally { Close-Game }
}

function Stage-Save {
    Log "=== save screen (VPTR=1; MOUSE doc Test B) ===" "Cyan"
    Set-Switches $true
    $bak = Join-Path $Run "saveset"; New-Item -ItemType Directory -Force $bak | Out-Null
    $files = @(Get-ChildItem $G -File | Where-Object { $_.Name -ieq "savegame.dir" -or $_.Name -imatch "^save.*\.cmp$" })
    $files | ForEach-Object { Copy-Item $_.FullName $bak }
    Log "    save set copied: $($files.Count) files -> $bak"
    try {
        if (-not (Start-Garage "save")) { Check "save: garage reached" $false "see garage-start-save.out"; return }
        $geo = Geo; Log "    geometry: $($geo.Text)"
        $dir0 = (Get-Item (Join-Path $G "savegame.dir")).LastWriteTime
        Click-UiPoint $geo "560,460" $true "SAVE BOOKMARK" 600
        $gate0 = Shell-I32 0x10043224
        Log "    idle 10 s (gate [0x10043224] = $gate0)"; Start-Sleep -Seconds 10
        $gate1 = Shell-I32 0x10043224
        Check "save: mouse gate [0x10043224] stays 1 over 10 s idle" ($gate1 -eq 1) "before $gate0, after $gate1"
        $hnd = Hand-ForUi $geo 300 300 $true; Move-Hand $hnd[0] $hnd[1]; $m = Shell-State
        Check "save: shell mouse still follows the hand" ([Math]::Abs($m.X - 300) -le 1 -and [Math]::Abs($m.Y - 300) -le 1) "target (300,300) read ($($m.X),$($m.Y)); $($m.Top)"
        Capture-UI (Join-Path $Run "save-1-idle.png") | Out-Null
        Click-UiPoint $geo $SaveRow $true "bookmark row"; Capture-UI (Join-Path $Run "save-2-row.png") | Out-Null
        Click-UiPoint $geo $SaveBtn $true "SAVE (1)"; Click-UiPoint $geo $SaveBtn $true "SAVE (2)" 1500
        $s = Shell-State; Log "    after SAVE x2: $($s.Text)"; Capture-UI (Join-Path $Run "save-3-after-save.png") | Out-Null
        # the overwrite prompt reads top=menu, not popup (run 20261002-234050, save-3-after-save.png): if nothing was
        # written yet, answer YES where it is drawn
        if ((Get-Item (Join-Path $G "savegame.dir")).LastWriteTime -le $dir0) { Click-UiPoint $geo $YesBtn $true "YES (overwrite prompt)" 2000 }
        Start-Sleep -Seconds 1
        $dir1 = (Get-Item (Join-Path $G "savegame.dir")).LastWriteTime; $s = Shell-State
        Capture-UI (Join-Path $Run "save-4-end.png") | Out-Null
        Check "save: bookmark written by mouse alone" ($dir1 -gt $dir0) "savegame.dir $($dir0.ToString('HH:mm:ss.fff')) -> $($dir1.ToString('HH:mm:ss.fff')); shell: $($s.Text). If this fails with the gate at 1, check -SaveRow/-SaveBtn against save-2-row.png (coordinates not verified offline)"
    } finally {
        Close-Game
        if (-not $KeepSaves -and -not (Get-Process | Where-Object { $_.ProcessName -like "i76*" })) {
            Get-ChildItem $G -File | Where-Object { $_.Name -imatch "^save.*\.cmp$" -and -not (Test-Path (Join-Path $bak $_.Name)) } | ForEach-Object { Remove-Item $_.FullName; Log "    removed new $($_.Name)" }
            Get-ChildItem $bak -File | ForEach-Object { Copy-Item $_.FullName (Join-Path $G $_.Name) -Force }
            Log "    save set restored from $bak"
        }
    }
}

function Stage-Route {
    Log "=== bookmark route: leg-b x $RouteRuns (VPTR=1) ===" "Cyan"
    Set-Switches $true
    $okN = 0
    for ($i = 1; $i -le $RouteRuns; $i++) {
        $last = ($i -eq $RouteRuns)
        $argLine = "-WantFile $Bookmark -WantRow $Row -RowUy $RowUy" + $(if ($last) { " -NoQuit" } else { "" })
        $o = Run-Child "$Here\saves\leg-b.ps1" $argLine "leg-b-$i.out"
        $oc = @($o | Where-Object { $_ -match "OUTCOME:" }) | Select-Object -Last 1
        $envl = @($o | Where-Object { $_ -match " env: " }) | Select-Object -First 1
        $ok = ("$oc" -match "completed through B1\.10"); if ($ok) { $okN++ }
        Log "    run ${i}: $oc"; Log "    run ${i}:$envl"
        if ("$envl" -notmatch "I76_U32X_VPTR=1") { Check "route r$i ran with the switch" $false "leg-b's env line has no I76_U32X_VPTR=1 (U32X_TEST_ENV pass-through missing?)" }
        if ($last) {
            try {
                $p = Game
                if (-not $ok) { Check "cursor window hidden in the mission" $null "not measured: the last leg-b run did not reach the mission ($oc)" }
                elseif ($p) {
                    Focus; Start-Sleep -Seconds 2
                    $geo = Geo; $w = Vptr-Win $geo; $c = Mem-Open; $ent = Mem-PlayerEntity $c; $mode = Mem-I32 $c 0x4fe534; Mem-Close $c
                    Check "cursor window hidden in the mission" (($ent -ne 0) -and (-not $w.Visible)) ("player 0x{0:x} mode 0x{1:x} window exists={2} visible={3}; {4}" -f $ent, $mode, $w.Exists, $w.Visible, $geo.Text)
                } else { Check "cursor window hidden in the mission" $null "the game was not running after the last leg-b run" }
            } finally { Close-Game }
        }
    }
    Check "bookmark route (leg-b $Bookmark row $Row)" ($okN -eq $RouteRuns) "$okN of $RouteRuns completed through B1.10"
}

function Stage-Option6 {
    Log "=== option 6 (TEST-FRAMERATE all120 through the trip menus, VPTR=1) ===" "Cyan"
    Set-Switches $true
    $o = Run-Child "$Here\option6-trip-test.ps1" "-Mode all120 -RowUy $RowUy" "option6.out"
    $l = @($o | Where-Object { $_ -match "engine up:" }) | Select-Object -Last 1
    Check "option 6 via the trip menus" ("$l" -match "engine up: True") "$l"
    Close-Game
}

# frame point -> picture (where the item is drawn) and -> hand. u32x uses a clip box only if one was MEASURED while
# driving (larger than UI size, smaller than the client); otherwise the frame map, i.e. the hand is on the drawn item.
$script:DriveBox = $null
function Menu-Points($geo, $c, [string]$fxy) {
    $v = $fxy -split ","; $fx = [int]$v[0]; $fy = [int]$v[1]
    $fw = (Mem-I32 $c 0x5dcee4) - (Mem-I32 $c 0x5dcedc); $fh = (Mem-I32 $c 0x5dcee8) - (Mem-I32 $c 0x5dcee0)
    if ($fw -lt 320 -or $fh -lt 200) { $fw = 640; $fh = 480 }
    $picW = 640 * $geo.Scale; $picH = 480 * $geo.Scale
    $px = [int]($geo.PicL + [Math]::Floor($fx * $picW / $fw + 0.5)); $py = [int]($geo.PicT + [Math]::Floor($fy * $picH / $fh + 0.5))
    $hx = $px; $hy = $py; $via = "frame map (hand on the drawn item)"
    $b = $script:DriveBox
    if ($b) { $hx = [int]($b[0] + [Math]::Floor($fx * ($b[2] - $b[0]) / $fw + 0.5)); $hy = [int]($b[1] + [Math]::Floor($fy * ($b[3] - $b[1]) / $fh + 0.5)); $via = "measured box $($b -join ',')" }
    [pscustomobject]@{ HandX = $hx; HandY = $hy; PicX = $px; PicY = $py; Frame = "${fw}x${fh}"; Via = $via }
}
# "one pointer on the drawn item": the OS arrow itself (no cursor window) or the cursor window, within $tol px
function Pointer-On($geo, $pts, [int]$tol) {
    $w = Vptr-Win $geo; $pt = New-Object VP+POINT; [void][VP]::GetCursorPos([ref]$pt)
    $dh = [Math]::Max([Math]::Abs($pt.X - $pts.PicX), [Math]::Abs($pt.Y - $pts.PicY))
    $dw = if ($w.Visible) { [Math]::Max([Math]::Abs($w.X - $pts.PicX), [Math]::Abs($w.Y - $pts.PicY)) } else { 9999 }
    $ok = (($dh -le $tol + [Math]::Ceiling($geo.Scale)) -and -not $w.Visible) -or ($dw -le $tol)
    [pscustomobject]@{ Ok = $ok; Text = ("drawn at ({0},{1}); hand ({2},{3}) off by {4}; cursor window visible={5} at ({6},{7}); os arrow showing={8}; {9}" -f $pts.PicX, $pts.PicY, $pt.X, $pt.Y, $dh, $w.Visible, $w.X, $w.Y, [VP]::OsCursorShowing(), $pts.Via) }
}
function Menu-Reads($c) {
    $menu = Mem-I32 $c 0x654a20; $sel = if ($menu) { Mem-I32 $c ($menu + 0x20) } else { -1 }
    "mode 0x{0:x} menu 0x{1:x} sel {2} page [{3}]" -f (Mem-I32 $c 0x4fe534), $menu, $sel, ((0x654a3c, 0x654a40, 0x654a44, 0x654a48 | ForEach-Object { Mem-I32 $c $_ }) -join " ")
}
function Open-EscMenu([string]$tag) {
    $o = Run-Child "$Here\test-escmenu.ps1" "-Stage open -Tag $tag" "escmenu-open-$tag.out"
    $o | Where-Object { $_ -match "driving:|menu:|cursor after|u32x.dll" } | ForEach-Object { Log "    $_" }
    $p = Game; if (-not $p) { return $false }
    Focus; Init-CursorMap | Out-Null
    # the clip while driving (test-escmenu prints it): a box only if larger than UI size and smaller than the client
    $script:DriveBox = $null; $geo = Geo
    $d = @($o | Where-Object { $_ -match "^driving:" }) | Select-Object -First 1
    if ("$d" -match "osclip (-?\d+),(-?\d+)-(-?\d+),(-?\d+)") {
        $b = @([int]$Matches[1], [int]$Matches[2], [int]$Matches[3], [int]$Matches[4]); $bw = $b[2] - $b[0]; $bh = $b[3] - $b[1]
        if ($bw -gt 704 -and $bh -gt 544 -and -not ($bw -ge $geo.CW -and $bh -ge $geo.CH)) { $script:DriveBox = $b }
        Log "    clip while driving: $($b -join ',') -> $(if ($script:DriveBox) { 'a measured BOX: u32x maps box -> page' } else { 'no box: frame map, hand on the drawn item' })"
    }
    return $true
}
function Stage-EscMenu([bool]$vptr) {
    $tag = if ($vptr) { "vptr" } else { "ctl" }
    Log "=== Esc menu ($(if ($vptr) { 'VPTR=1' } else { 'control, VPTR off' })) ===" "Cyan"
    Set-Switches $vptr
    if (-not (Open-EscMenu $tag)) { Check "escmenu[$tag] opened" $false "test-escmenu -Stage open left no game (see escmenu-open-$tag.out)"; Close-Game; return }
    $c = Mem-Open
    try {
        $geo = Geo; Log "    geometry: $($geo.Text)"; Log "    $(Menu-Reads $c)"
        if ((Mem-I32 $c 0x4fe534) -ne 0x10) { Check "escmenu[$tag] menu is up" $false (Menu-Reads $c); return }
        if ($vptr) {
            # Play Options: cursor shown on the drawn item, then clicked from there
            $po = Menu-Points $geo $c $PlayOptions
            Move-Hand $po.HandX $po.HandY 500; $on = Pointer-On $geo $po 3
            Check "escmenu one pointer on the drawn Play Options (within 3 px)" $on.Ok $on.Text
            Capture-UI (Join-Path $Run "escmenu-playoptions-before.png") | Out-Null
            $r0 = Menu-Reads $c; Click-Here 900; $r1 = Menu-Reads $c
            Capture-UI (Join-Path $Run "escmenu-playoptions-after.png") | Out-Null
            Check "escmenu Play Options opens from where the cursor is shown" $null "before: $r0 | after: $r1 | confirm with escmenu-playoptions-after.png"
            Send-Key $VK.ESC; Start-Sleep -Milliseconds 1200
            if ((Mem-I32 $c 0x4fe534) -ne 0x10) { Send-Key $VK.ESC; Start-Sleep -Milliseconds 1500 }
            Log "    back on the menu: $(Menu-Reads $c)"
            if ((Mem-I32 $c 0x4fe534) -ne 0x10) { Check "escmenu back on the main page for the Exit test" $false (Menu-Reads $c); return }
        }
        $ex = Menu-Points $geo $c $Exit
        Move-Hand $ex.HandX $ex.HandY 500; $w = Vptr-Win $geo
        if ($vptr) {
            $on = Pointer-On $geo $ex 3
            Check "escmenu one pointer on the drawn Exit (within 3 px)" $on.Ok $on.Text
        } else {
            Check "control: no cursor window in the Esc menu" (-not $w.Exists) "u32xVptr window exists=$($w.Exists) visible=$($w.Visible); os arrow showing=$([VP]::OsCursorShowing())"
        }
        Capture-UI (Join-Path $Run "escmenu-$tag-exit-before.png") | Out-Null
        $r0 = Menu-Reads $c; Click-Here 300
        $left = $false; for ($i = 0; $i -lt 10; $i++) { if ((Mem-I32 $c 0x4fe534) -ne 0x10) { $left = $true; break }; Start-Sleep -Milliseconds 200 }
        $r1 = Menu-Reads $c
        Check "escmenu[$tag] Exit hit from hand ($($ex.HandX),$($ex.HandY)), drawn at ($($ex.PicX),$($ex.PicY))" $left "$($ex.Via) | before: $r0 | after: $r1"
        if ($vptr) { Start-Sleep -Milliseconds 800; $w = Vptr-Win $geo; Check "escmenu cursor window after the menu closed" $null "mode 0x$('{0:x}' -f (Mem-I32 $c 0x4fe534)) visible=$($w.Visible) (hidden expected unless a shell screen came up)" }
    } finally {
        Mem-Close $c
        Run-Child "$Here\test-escmenu.ps1" "-Stage close" "escmenu-close-$tag.out" | Out-Null
        Close-Game
    }
}

function Stage-Melee {
    Log "=== melee route through the menus (VPTR=1) ===" "Cyan"
    Set-Switches $true                           # menu-route-test scrubs a fixed list that has no I76_U32X_* name in it
    $o = Run-Child "$Here\menu-route-test.ps1" "-Tag vptr" "melee.out"
    $l = @($o | Where-Object { $_ -match "enter-melee exit" }) | Select-Object -Last 1
    Check "melee route (menu-route-test.ps1)" ("$l" -match "enter-melee exit 0 " -and "$l" -notmatch "player 0x0 ") "$l"
}

function Stage-Control {
    Log "=== control: VPTR off (today's regime must return) ===" "Cyan"
    Set-Switches $false
    if (-not (Start-Garage "control")) { Check "control: garage reached" $false "see garage-start-control.out"; Close-Game }
    else {
        try {
            $geo = Geo; Log "    geometry: $($geo.Text)"
            $hit = 0; $pts = @(@(40, 40), @(320, 240), @(625, 455))
            foreach ($t in $pts) {
                $hnd = Hand-ForUi $geo $t[0] $t[1] $false; Move-Hand $hnd[0] $hnd[1]; $m = Shell-State
                if ([Math]::Abs($m.X - $t[0]) -le 1 -and [Math]::Abs($m.Y - $t[1]) -le 1) { $hit++ }
                Log ("    target ({0},{1}) hand ({2},{3}) shell-mouse ({4},{5})" -f $t[0], $t[1], $hnd[0], $hnd[1], $m.X, $m.Y)
            }
            $w = Vptr-Win $geo
            Check "control: shell regime as before (box [$($geo.Kind)])" ($hit -eq $pts.Count) "$hit of $($pts.Count) read back within 1 px; $($geo.Text)"
            Check "control: no cursor window in the shell" (-not $w.Exists) "u32xVptr window exists=$($w.Exists) visible=$($w.Visible)"
        } finally { Close-Game }
    }
    Stage-EscMenu $false
}

# ============================================================== run =================================================
$bakDll = "$G\u32x.dll.pre-vptr-test"; $installed = $false
Log "vptr-test $ts stages: $($Stage -join ', ') | run dir $Run" "Cyan"
try {
    if (-not $NoInstall) {
        if (-not (Test-Path $Dll)) { throw "build not found: $Dll" }
        Copy-Item "$G\u32x.dll" $bakDll -Force
        Copy-Item $Dll "$G\u32x.dll" -Force; $installed = $true
        Log "game\u32x.dll <- $Dll (md5 $(Md5 "$G\u32x.dll")); previous kept as u32x.dll.pre-vptr-test (md5 $(Md5 $bakDll))"
    } else { Log "testing the installed game\u32x.dll (md5 $(Md5 "$G\u32x.dll"))" }
    foreach ($s in $Stage) {
        if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game }
        try {
            switch ($s) {
                "shell"   { for ($i = 1; $i -le $Runs; $i++) { Stage-Shell "$i" } }
                "widen"   { Stage-Shell "widen" "I76_U32X_VPTR_WIDEN=1" }
                "save"    { Stage-Save }
                "route"   { Stage-Route }
                "option6" { Stage-Option6 }
                "escmenu" { Stage-EscMenu $true }
                "melee"   { Stage-Melee }
                "control" { Stage-Control }
            }
        } catch { Check "stage $s ran to the end" $false "$_"; try { Close-Game } catch {} }
    }
} finally {
    try { if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game } } catch {}
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76_U32X_*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    Remove-Item Env:U32X_TEST_ENV -ErrorAction SilentlyContinue
    if ($installed -and -not $KeepDll) {
        Copy-Item $bakDll "$G\u32x.dll" -Force
        if ((Md5 "$G\u32x.dll") -eq (Md5 $bakDll)) { Remove-Item $bakDll; Log "game\u32x.dll restored (md5 $(Md5 "$G\u32x.dll"))" }
        else { Log "RESTORE MISMATCH: game\u32x.dll is not the previous build; it is kept as $bakDll" "Red" }
    } elseif ($installed) { Log "-KeepDll: game\u32x.dll stays the build under test (md5 $(Md5 "$G\u32x.dll")); previous: $bakDll" "Yellow" }
    Log ""; Log "RESULTS" "Cyan"
    $script:Results | ForEach-Object { Log ("| {0} | {1} | {2} |" -f $_.Result, $_.Check, $_.Detail) }
    $fail = @($script:Results | Where-Object { $_.Result -eq "FAIL" }).Count
    $pass = @($script:Results | Where-Object { $_.Result -eq "PASS" }).Count
    $info = @($script:Results | Where-Object { $_.Result -eq "INFO" }).Count
    Log "PASS $pass  FAIL $fail  INFO $info  -> $LogPath" $(if ($fail) { "Red" } else { "Green" })
}
exit $fail
