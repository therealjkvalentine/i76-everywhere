<#
  gate-folder.ps1 - the unattended gate of i76-everywhere docs\records\NEW-DAILY-DRIVER-RECIPE.md section 5.1 for ONE game
  folder inside the lab (the daily-driver twin game-dd-<date>\Interstate 76, or the sandbox as the control run).
  Physical console, nobody playing: it takes the mouse, the keyboard and the screen for about 10 minutes.

    powershell -ExecutionPolicy Bypass -File gate-folder.ps1 -GameDir C:\Users\james\i76-uncap-lab\game-dd-20261003
    powershell -ExecutionPolicy Bypass -File gate-folder.ps1 -GameDir ..\game                      # control: the sandbox
    powershell -ExecutionPolicy Bypass -File gate-folder.ps1 -GameDir <dir> -Only 2,4              # only these rows
    powershell -ExecutionPolicy Bypass -File gate-folder.ps1 -GameDir <dir> -DryRun                # no game: paths, plan, read-only checks

  -GameDir   the game folder (holds i76.exe) or a twin's root (its "Interstate 76" subfolder is taken). Inside the lab
             only: lib\gamedir.ps1 refuses anything else and names the playable installs.
  -Launcher  the .bat / .ps1 row 3 starts (the twin's PLAY.bat -> PLAY-i76.ps1 -Preset best-120). Default: PLAY.bat
             beside an "Interstate 76" folder when there is one; otherwise TEST-FRAMERATE.ps1 -Mode all120 -GameDir.
  -Bookmark saveNNN -Row k   the bookmark rows 2-4 load. Default: read from the folder's savegame.dir with
             i76-save-editor.py --list (a garage-state record on the first page if there is one). Rows >= 10 are below
             the fold of the LOAD board: the scroll trick of saves\cal-probe2.ps1 is applied (leg-b / option6 -Scroll).

  Rows, in order (results: runs\gate\<ts>\results.md, a markdown table; exit code = number of FAIL rows):
    1  conf accepted   tools\graphics\conf-probe.ps1 -ClientRect with %APPDATA%\dgVoodoo\dgVoodoo.conf hidden: the
                       shell window's client must be the full-screen one, not 640x480. Then the watermark probe
                       (3DfxWatermark flipped for one t01 boot, capture saved): INFO, the logo is checked by eye.
    2  bookmark route  saves\leg-b.ps1 -Mode b1 x -RouteRuns (3): TRIP -> LOAD BOOKMARK -> row -> LOAD -> ACCEPT
                       SALVAGE -> DONE -> mission, verified by memory. Pass: every run "completed through B1.10".
    3  trip route through the launcher   option6-trip-test.ps1 -Launcher x -TripRuns (2): the same clicks after the
                       folder's own launcher started the game. Pass: engine up every run and the frame rate within 10 %
                       of -ExpectFps (trainer heartbeat; the exe frame counter when the heartbeat does not move).
    4  save screen     garage (leg-b -StopAtGarage), SAVE BOOKMARK, 10 s idle (mouse gate [shell+0x43224] must stay 1,
                       the shell mouse must still follow), row click, SAVE x2, overwrite prompt. Session A answers NO:
                       no file may change. Session B answers YES. Both sessions click a SCRATCH bookmark this script
                       appended (a copy of -Bookmark, name "GATE SCRATCH") and removes again; pass for YES: something
                       was written and no other saveNNN.cmp changed.
    5  Esc-menu Exit   test-escmenu.ps1 -Stage open (t01, Esc), the hand goes to where Exit is DRAWN, click; pass: the
                       engine leaves menu mode ([0x4fe534] != 0x10). "Drawn" = the frame the folder's conf presents
                       (a 16:10 [Glide] Resolution fills a 16:10 rectangle); if only the 4:3-picture position answers,
                       the row is INFO with both captures, for the eye.
    6  melee by menus  menu-route-test.ps1 (enter-melee.ps1: MELEE -> AUTO MELEE -> INSTANT MELEE -> ENTER AREA).
    7  input.map       python i76-everywhere\tools\lint-input-map.py <folder>; and its md5 unchanged by the gate.
    8  force feedback  i76-everywhere\tools\check-ffb.ps1 (reads only), run inside row 3's first mission.
    S  saves           the player-state files are copied out before row 1 and compared by md5 after the last row;
                       anything the runs changed is put back and compared again. Pass: byte-identical at the end.
    D  folder drift    md5 of every other top-level file before / after: pass when only logs changed.

  What the gate changes in the folder while it runs, and puts back: .console-test.lock; dgVoodoo.conf (row 1b, one
  key, restored by conf-probe); savegame.dir + one saveNNN.cmp (row 4 scratch); whatever the game itself writes on a
  bookmark load (vehscn.*, reconfig.spc, I76PLYR.DEF). STRLKUP.DLL is NOT swapped (the folder's own proxy is what is
  gated) unless -SwapDll. leg-b's save backups go to the run folder, not into the game folder.
#>
param(
    [Parameter(Mandatory)] [string]$GameDir,
    [string]$Launcher = "", [string]$LauncherArgs = "",
    [string]$Bookmark = "", [int]$Row = -1,
    [int]$RouteRuns = 3, [int]$TripRuns = 2, [double]$ExpectFps = 120,
    [string[]]$Only = @(),                                   # e.g. -Only 2,4   (1..8)
    [string]$SaveBookmarkBtn = "560,460", [string]$SaveBtn = "352,428", [string]$YesBtn = "393,258", [string]$NoBtn = "450,258",
    [string]$Exit = "432,445",                               # Esc-menu Exit, frame coordinates (MOUSE doc 5a)
    [switch]$SwapDll,                                        # the harness default instead: music-fix\Strlkup.dll installed per run
    [switch]$KeepGlobalConf,                                 # do not hide %APPDATA%\dgVoodoo\dgVoodoo.conf for the whole gate
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = "C:\Users\james\i76-everywhere"
. "$Here\lib\gamedir.ps1"
$Lab = Get-LabRoot
if ((Test-Path -LiteralPath $GameDir -PathType Container) -and -not (Test-Path -LiteralPath (Join-Path $GameDir "i76.exe")) -and (Test-Path -LiteralPath (Join-Path $GameDir "Interstate 76\i76.exe"))) {
    $GameDir = Join-Path $GameDir "Interstate 76"
}
$Game = Resolve-LabGameDir $GameDir
$I76GameDirInUse = $Game                                     # focuslib / memlib / maplib: this folder's process and conf
if (-not $Launcher -and (Split-Path -Leaf $Game) -ieq "Interstate 76") {
    $cand = Join-Path (Split-Path -Parent $Game) "PLAY.bat"
    if (Test-Path -LiteralPath $cand) { $Launcher = $cand }
}
if ($Launcher) { $Launcher = Resolve-LabLauncher $Launcher }
$Rows = @($Only | ForEach-Object { "$_" -split "," } | Where-Object { $_.Trim() } | ForEach-Object { [int]$_.Trim() })
if ($Rows.Count -eq 0) { $Rows = 1..8 }
function Want([int]$n) { return ($Rows -contains $n) }

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Run = Join-Path $Here "runs\gate\$ts"; New-Item -ItemType Directory -Force $Run | Out-Null
$LogPath = Join-Path $Run "log.txt"
function Log([string]$m, [string]$c = "Gray") { Add-Content -Path $LogPath -Value $m -Encoding UTF8; Write-Host $m -ForegroundColor $c }
$script:Results = @()
function Check([string]$row, [string]$name, $ok, [string]$detail) {
    $v = if ($ok -eq $null) { "INFO" } elseif ($ok) { "PASS" } else { "FAIL" }
    $script:Results += [pscustomobject]@{ Row = $row; Check = $name; Result = $v; Detail = ($detail -replace "\|", "/" -replace "\s+", " ").Trim() }
    $col = "Yellow"; if ($v -eq "PASS") { $col = "Green" } elseif ($v -eq "FAIL") { $col = "Red" }
    Log ("  [{0}] {1} {2}: {3}" -f $v, $row, $name, $detail) $col
}
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }
function Py {
    # python with stderr folded in; under ErrorActionPreference Stop a native stderr line would otherwise throw
    $ErrorActionPreference = "Continue"
    $enc = $env:PYTHONIOENCODING; $env:PYTHONIOENCODING = "utf-8"     # lint prints a warning sign; a cp1252 pipe would crash it
    try { $o = & python @args 2>&1 | ForEach-Object { "$_" }; $script:PyRc = $LASTEXITCODE }
    finally { if ($enc) { $env:PYTHONIOENCODING = $enc } else { Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue } }
    return @($o)
}
function Run-Child([string]$script, [string]$argLine, [string]$outName) {
    # a child powershell with its output in a file: the harness scripts use exit / throw / Write-Host freely
    $of = Join-Path $Run $outName
    cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File `"$script`" $argLine > `"$of`" 2>&1"
    return @(Get-Content $of -ErrorAction SilentlyContinue)
}
$gd = "-GameDir `"$Game`""
$keep = if ($SwapDll) { "" } else { " -KeepInstalledDll" }
$dry = if ($DryRun) { " -DryRun" } else { "" }

# ================================================================ player state: snapshot, backup, restore ==============
$StatePatterns = "savegame.dir", "save*.cmp", "*.spc", "user.*", "*.def", "*.rec", "*.fot", "nscr.dat", "input.map"
function Is-State([string]$rel) {
    if ($rel -like "ADDON\vehscn.*") { return $true }
    if ($rel -like "*\*") { return $false }
    foreach ($pat in $StatePatterns) { if ($rel -like $pat) { return $true } }
    return $false
}
function Snapshot-Folder {
    # every top-level file and ADDON\vehscn.*: rel path -> "md5" (files over 64 MB: "size:mtime", they are archives)
    $snap = @{}
    $files = @(Get-ChildItem -LiteralPath $Game -File -Force) + @(Get-ChildItem -LiteralPath (Join-Path $Game "ADDON") -File -Filter "vehscn.*" -ErrorAction SilentlyContinue)
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($Game.Length + 1)
        if ($rel -ieq ".console-test.lock") { continue }
        $snap[$rel] = if ($f.Length -gt 64MB) { "{0}:{1}" -f $f.Length, $f.LastWriteTimeUtc.Ticks } else { Md5 $f.FullName }
    }
    return $snap
}
function Backup-State([hashtable]$snap, [string]$dest) {
    New-Item -ItemType Directory -Force $dest | Out-Null
    $lines = @()
    foreach ($rel in ($snap.Keys | Sort-Object)) {
        if (-not (Is-State $rel)) { continue }
        Copy-Item -LiteralPath (Join-Path $Game $rel) -Destination (Join-Path $dest ($rel -replace "\\", "__"))
        if ((Md5 (Join-Path $dest ($rel -replace "\\", "__"))) -ne $snap[$rel]) { throw "backup of $rel does not read back with the same md5" }
        $lines += "{0}  {1}" -f $snap[$rel], $rel
    }
    $lines | Set-Content (Join-Path $dest "md5.txt") -Encoding UTF8
    return $lines.Count
}
function Restore-State([hashtable]$before, [string]$src, [string]$strayDir) {
    # put back every player-state file that differs from the backup; move state files that did not exist before out
    $changed = @(); $now = Snapshot-Folder
    foreach ($rel in ($before.Keys | Sort-Object)) {
        if (-not (Is-State $rel)) { continue }
        if ($now[$rel] -ne $before[$rel]) {
            $changed += $rel
            Copy-Item -LiteralPath (Join-Path $src ($rel -replace "\\", "__")) -Destination (Join-Path $Game $rel) -Force
        }
    }
    foreach ($rel in ($now.Keys | Sort-Object)) {
        if ((Is-State $rel) -and -not $before.ContainsKey($rel)) {
            New-Item -ItemType Directory -Force $strayDir | Out-Null
            Move-Item -LiteralPath (Join-Path $Game $rel) -Destination (Join-Path $strayDir ($rel -replace "\\", "__")) -Force
            $changed += "$rel (new: moved to $strayDir)"
        }
    }
    return $changed
}
function State-Diff([hashtable]$a, [hashtable]$b) {
    $out = @()
    foreach ($rel in (@($a.Keys) + @($b.Keys) | Sort-Object -Unique)) {
        if (-not (Is-State $rel)) { continue }
        if (-not $a.ContainsKey($rel)) { $out += "$rel (new)" } elseif (-not $b.ContainsKey($rel)) { $out += "$rel (gone)" } elseif ($a[$rel] -ne $b[$rel]) { $out += $rel }
    }
    return $out
}

# ================================================================ bookmarks ============================================
function Read-Bookmarks {
    $o = Py "$Repo\i76-save-editor.py" --dir $Game --list
    $list = @()
    foreach ($l in $o) { if ("$l" -match '^\s*(\d+)\s+(save\d+)\s+scene\s+(\d+)\s+st\s+(\d+)') { $list += [pscustomobject]@{ Row = [int]$Matches[1]; File = $Matches[2]; Scene = [int]$Matches[3]; State = [int]$Matches[4]; Line = "$l".Trim() } } }
    return $list
}
function Row-Pos([int]$r, [int]$records) {
    # the LOAD board shows 10 rows, 23 UI px apart from y 193; below the fold: scroll to the bottom first (cal-probe2.ps1)
    if ($r -lt 10) { return [pscustomobject]@{ Uy = 193 + 23 * $r; Scroll = 0 } }
    return [pscustomobject]@{ Uy = 193 + 23 * ($r - ($records - 10)); Scroll = [Math]::Max(10, $records - 10) }
}
function New-ScratchDir([int]$srcRow) {
    # savegame.dir: u32 count, then 60-byte records {u32 scene, char[32] name, char[16] file, u32 state, u32 0}; size = 4 + 60 x count
    $b = [IO.File]::ReadAllBytes((Join-Path $Game "savegame.dir"))
    $count = [BitConverter]::ToInt32($b, 0)
    if ($b.Length -ne 4 + 60 * $count) { throw "savegame.dir is $($b.Length) B for $count records (expected exactly $(4 + 60 * $count))" }
    if ($srcRow -lt 0 -or $srcRow -ge $count) { throw "row $srcRow is not in savegame.dir ($count records)" }
    $used = @(); for ($k = 0; $k -lt $count; $k++) { $fb = $b[(4 + 60 * $k + 36)..(4 + 60 * $k + 51)]; $z = [Array]::IndexOf($fb, [byte]0); if ($z -lt 0) { $z = 16 }; $used += [Text.Encoding]::ASCII.GetString($fb, 0, $z).ToLower() }
    $n = 0; do { $name = "save{0:d3}" -f $n; $n++ } while ((Test-Path (Join-Path $Game "$name.cmp")) -or ($used -contains $name))
    $nb = New-Object byte[] ($b.Length + 60); [Array]::Copy($b, 0, $nb, 0, $b.Length)
    $o = $b.Length; [Array]::Copy($b, 4 + 60 * $srcRow, $nb, $o, 60)
    for ($k = 4; $k -lt 52; $k++) { $nb[$o + $k] = 0 }
    $t = [Text.Encoding]::ASCII.GetBytes("GATE SCRATCH"); [Array]::Copy($t, 0, $nb, $o + 4, $t.Length)
    $t = [Text.Encoding]::ASCII.GetBytes($name); [Array]::Copy($t, 0, $nb, $o + 36, $t.Length)
    [Array]::Copy([BitConverter]::GetBytes([int]($count + 1)), 0, $nb, 0, 4)
    [pscustomobject]@{ Bytes = $nb; Index = $count; Records = $count + 1; File = $name; SrcFile = $used[$srcRow] }
}

# ================================================================ pre-flight ===========================================
Log "gate-folder $ts  game: $Game" "Cyan"
Log "  launcher: $(if ($Launcher) { "$Launcher $LauncherArgs" } else { 'none found: row 3 uses TEST-FRAMERATE.ps1 -Mode all120 -GameDir' })"
Log "  rows: $($Rows -join ', ')   run dir: $Run   proxy: $(if ($SwapDll) { 'music-fix build swapped in per run (-SwapDll)' } else { 'the folder''s own STRLKUP.DLL (no swap)' })$(if ($DryRun) { '   DRY RUN: no game is started' })"
Add-Type -AssemblyName System.Windows.Forms
$rdp = [System.Windows.Forms.SystemInformation]::TerminalServerSession
if ($rdp -and -not $DryRun) { throw "this is an RDP session: the game does not start here (AGENTS.md). Run the gate at the console." }
if (-not $DryRun) {
    if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76* process is running" }
    if (Test-Path "$Game\.console-test.lock") { throw "$Game\.console-test.lock exists (another test owns this folder): $(Get-Content "$Game\.console-test.lock" -Raw)" }
    if (Test-Path "$Game\STRLKUP.DLL.pretest") { throw "$Game\STRLKUP.DLL.pretest exists: a killed run left the test proxy installed. Restore it first (garage-ui.ps1 -Close -GameDir ...)." }
}
foreach ($need in "$Repo\i76-save-editor.py", "$Repo\tools\lint-input-map.py", "$Here\saves\leg-b.ps1", "$Here\saves\garage-ui.ps1", "$Here\option6-trip-test.ps1", "$Here\test-escmenu.ps1", "$Here\menu-route-test.ps1", "$Lab\tools\graphics\conf-probe.ps1") {
    if (-not (Test-Path $need)) { throw "not found: $need" }
}
foreach ($f in "i76.exe", "i76shell.dll", "u32x.dll", "STRLKUP.DLL", "dgVoodoo.conf", "savegame.dir", "input.map") {
    $p = Join-Path $Game $f
    Log ("  {0,-14} {1}" -f $f, $(if (Test-Path $p) { "md5 $(Md5 $p)  $((Get-Item $p).Length) B" } else { "ABSENT" }))
}
$mf = "$Repo\music-fix\Strlkup.dll"
if ((Test-Path $mf) -and (Test-Path "$Game\STRLKUP.DLL")) { Log "  STRLKUP.DLL is $(if ((Md5 $mf) -eq (Md5 "$Game\STRLKUP.DLL")) { 'the current music-fix build' } else { "NOT the current music-fix build ($(Md5 $mf))" }); strlkup_orig.dll present: $(Test-Path "$Game\strlkup_orig.dll")" }

$marks = @(Read-Bookmarks)
Log "  bookmarks ($($marks.Count)):"; $marks | ForEach-Object { Log "    $($_.Line)" }
if ($marks.Count -eq 0) { throw "no bookmark in $Game\savegame.dir (i76-save-editor.py --list printed none)" }
if ($Bookmark) {
    $pick = $marks | Where-Object { $_.File -ieq $Bookmark } | Select-Object -First 1
    if (-not $pick) { throw "-Bookmark $Bookmark is not in savegame.dir" }
    if ($Row -ge 0 -and $Row -ne $pick.Row) { throw "-Row $Row, but $Bookmark is row $($pick.Row) in savegame.dir" }
} elseif ($Row -ge 0) {
    $pick = $marks | Where-Object { $_.Row -eq $Row } | Select-Object -First 1
    if (-not $pick) { throw "-Row $Row is not in savegame.dir" }
} else {
    # a garage-state record (st 8: LOAD -> inventory -> garage, the route leg-b was built on), the last one on the first page
    $pick = $marks | Where-Object { $_.State -eq 8 -and $_.Row -lt 10 } | Select-Object -Last 1
    if (-not $pick) { $pick = $marks | Where-Object { $_.State -eq 8 } | Select-Object -Last 1 }
    if (-not $pick) { $pick = $marks | Where-Object { $_.Row -lt 10 } | Select-Object -Last 1 }
    if (-not $pick) { $pick = $marks | Select-Object -Last 1 }
}
$Bookmark = $pick.File; $Row = $pick.Row
if (-not (Test-Path "$Game\$Bookmark.cmp")) { throw "$Bookmark.cmp is listed in savegame.dir but not in the folder" }
$pos = Row-Pos $Row $marks.Count
Log "  bookmark for rows 2-4: $Bookmark, row $Row of $($marks.Count) (scene $($pick.Scene), state $($pick.State)) -> UI y $($pos.Uy), scroll clicks $($pos.Scroll)" "Cyan"
$routeArgs = "-WantFile $Bookmark -WantRow $Row -RowUy $($pos.Uy)" + $(if ($pos.Scroll) { " -Scroll $($pos.Scroll)" } else { "" })

$before = Snapshot-Folder
$BakDir = Join-Path $Run "saves-before"
$nBak = Backup-State $before $BakDir
Log "  player state backed up: $nBak files -> $BakDir (md5.txt beside them)"
$inputMd5 = if ($before.ContainsKey("input.map")) { $before["input.map"] } else { "ABSENT" }

# ================================================================ live helpers (only used when a game runs) ============
if (-not $DryRun) {
    . "$Here\lib\focuslib.ps1"; . "$Here\lib\inputlib.ps1"; . "$Here\lib\maplib.ps1"; . "$Here\lib\memlib.ps1"
    Add-Type -AssemblyName System.Drawing
    Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class GF {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("psapi.dll")] public static extern bool EnumProcessModulesEx(IntPtr h, IntPtr[] m, int cb, out int need, int flag);
  [DllImport("psapi.dll", CharSet=CharSet.Ansi)] public static extern int GetModuleBaseNameA(IntPtr h, IntPtr m, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool GetClipCursor(out RECT r);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public static long Base(IntPtr h, string name) {
    IntPtr[] m = new IntPtr[1024]; int need;
    if (!EnumProcessModulesEx(h, m, m.Length * IntPtr.Size, out need, 0x01)) return 0;
    int n = need / IntPtr.Size;
    for (int i = 0; i < n; i++) { var sb = new StringBuilder(260); GetModuleBaseNameA(h, m[i], sb, 260);
      if (string.Equals(sb.ToString(), name, StringComparison.OrdinalIgnoreCase)) return m[i].ToInt64(); }
    return 0;
  }
  public static int I32(IntPtr h, long a) { var b = new byte[4]; IntPtr r; if (!ReadProcessMemory(h, new IntPtr(a), b, 4, out r)) return int.MinValue; return BitConverter.ToInt32(b, 0); }
}
"@
}
function Game-Proc { $p = Get-GamePid; if ($p -and -not (Test-ProcInDir $p $Game)) { throw "the running game is $($p.Path), not in $Game" }; return $p }
function Close-Game {
    Run-Child "$Here\saves\garage-ui.ps1" "-Close $gd -OutDir `"$Run`"" "close-$(Get-Date -Format HHmmss-fff).out" | Out-Null
    Start-Sleep -Seconds 1
}
function Focus { $p = Game-Proc; if ($p) { Force-Foreground $p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 300 } }
# live geometry (vptr-test.ps1 / u32x.c arithmetic): client, the 4:3 picture inside it, the clip box and its kind
function Geo {
    $p = Game-Proc; if (-not $p) { throw "no game" }
    $h = $p.MainWindowHandle
    $rc = New-Object GF+RECT; [void][GF]::GetClientRect($h, [ref]$rc)
    $org = New-Object GF+POINT; [void][GF]::ClientToScreen($h, [ref]$org)
    $c = New-Object GF+RECT; [void][GF]::GetClipCursor([ref]$c)
    $scale = [Math]::Min($rc.R / 640.0, $rc.B / 480.0)
    $w = $c.R - $c.L; $hh = $c.B - $c.T
    $kind = if ($w -ge $rc.R -and $hh -ge $rc.B) { "free" } elseif ([Math]::Abs($w - 640) -le 1 -and [Math]::Abs($hh - 480) -le 1) { "ui" } else { "box" }
    $picL = $org.X + [int][Math]::Floor(($rc.R - 640 * $scale) / 2); $picT = $org.Y + [int][Math]::Floor(($rc.B - 480 * $scale) / 2)
    [pscustomobject]@{ Pid = $p.Id; CW = $rc.R; CH = $rc.B; Scale = $scale; PicL = $picL; PicT = $picT; ClipL = $c.L; ClipT = $c.T; ClipW = $w; ClipH = $hh; Kind = $kind
        Text = "client $($rc.R)x$($rc.B) at ($($org.X),$($org.Y)) scale $scale picture at ($picL,$picT) clip $($c.L),$($c.T)-$($c.R),$($c.B) [$kind]" }
}
# where the hand must be for the shell to read UI (ux,uy): a UI-sized clip is 1:1 from its corner, anything else is the picture
function Hand-ForUi($geo, [int]$ux, [int]$uy) {
    if ($geo.Kind -eq "ui") { return @(($geo.ClipL + $ux), ($geo.ClipT + $uy)) }
    return @(([int]($geo.PicL + $ux * $geo.Scale + $geo.Scale / 2)), ([int]($geo.PicT + $uy * $geo.Scale + $geo.Scale / 2)))
}
function Move-Hand([int]$x, [int]$y, [int]$settle = 350) { [void][GF]::SetCursorPos($x, $y); Start-Sleep -Milliseconds $settle }
function Click-Here([int]$settle = 900) { [GF]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 70; [GF]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds $settle }
function Shot([string]$name) {
    # the 4:3 picture, 640x480: one image pixel = one UI unit
    try {
        $geo = Geo; $w = [int](640 * $geo.Scale); $h = [int](480 * $geo.Scale)
        $b = New-Object Drawing.Bitmap $w, $h; $gr = [Drawing.Graphics]::FromImage($b)
        $gr.CopyFromScreen($geo.PicL, $geo.PicT, 0, 0, (New-Object Drawing.Size($w, $h)))
        $s = New-Object Drawing.Bitmap 640, 480; $g2 = [Drawing.Graphics]::FromImage($s); $g2.DrawImage($b, 0, 0, 640, 480)
        $s.Save((Join-Path $Run "$name.png"), [Drawing.Imaging.ImageFormat]::Png)
        $gr.Dispose(); $g2.Dispose(); $b.Dispose(); $s.Dispose()
    } catch { Log "    shot $name failed: $_" "Yellow" }
}
function Shot-Client([string]$name) {
    # the whole client area at 1/2 scale (the Esc menu's frame may be wider than the 4:3 picture)
    try {
        $p = Game-Proc; $rc = New-Object GF+RECT; [void][GF]::GetClientRect($p.MainWindowHandle, [ref]$rc); $org = New-Object GF+POINT; [void][GF]::ClientToScreen($p.MainWindowHandle, [ref]$org)
        $b = New-Object Drawing.Bitmap $rc.R, $rc.B; $gr = [Drawing.Graphics]::FromImage($b)
        $gr.CopyFromScreen($org.X, $org.Y, 0, 0, (New-Object Drawing.Size($rc.R, $rc.B)))
        $s = New-Object Drawing.Bitmap $b, ([int]($rc.R / 2)), ([int]($rc.B / 2))
        $s.Save((Join-Path $Run "$name.png"), [Drawing.Imaging.ImageFormat]::Png); $gr.Dispose(); $b.Dispose(); $s.Dispose()
    } catch { Log "    shot $name failed: $_" "Yellow" }
}
# the shell's own state (SCREENS.md / SAVE.md addresses, as leg-b.ps1 reads them)
function Shell-Read {
    $p = Game-Proc; if (-not $p) { return $null }
    $h = [GF]::OpenProcess(0x0410, $false, $p.Id); if ($h -eq [IntPtr]::Zero) { return $null }
    try {
        $base = [GF]::Base($h, "i76shell.dll"); if ($base -eq 0) { return $null }
        $d = $base - 0x10000000
        $scr = [GF]::I32($h, 0x100d2168 + $d); $sfn = [GF]::I32($h, 0x100d219c + $d); $mfn = [GF]::I32($h, 0x100d21a0 + $d); $modal = [GF]::I32($h, 0x100d21a4 + $d)
        $mo = [GF]::I32($h, 0x100cc514 + $d); $mx = -1; $my = -1
        if ($mo -ne 0 -and $mo -ne [int]::MinValue) { $mx = [GF]::I32($h, ([int64]$mo -band 0xFFFFFFFFL) + 0x2c); $my = [GF]::I32($h, ([int64]$mo -band 0xFFFFFFFFL) + 0x30) }
        $unre = { param($v) if ($v -eq 0 -or $v -eq [int]::MinValue) { [int64]$v } else { ([int64]$v -band 0xFFFFFFFFL) - $d } }
        $o = [pscustomobject]@{ Screen = $scr; Sfn = (& $unre $sfn); Mfn = (& $unre $mfn); Modal = $modal; MX = $mx; MY = $my
            Gate = [GF]::I32($h, 0x10043224 + $d); Slot = [GF]::I32($h, 0x10057f80 + $d); OwSlot = [GF]::I32($h, 0x10057f84 + $d); RowPicked = [GF]::I32($h, 0x10057f74 + $d); List = [GF]::I32($h, 0x10057f8c + $d); Text = "" }
        $o.Text = "screen=0x{0:X4} sfn=0x{1:x8} mfn=0x{2:x8} modal=0x{3:x8} mouse=({4},{5}) gate={6} slot={7} owSlot={8} rowPicked={9} list=0x{10:x}" -f $o.Screen, $o.Sfn, $o.Mfn, $o.Modal, $mx, $my, $o.Gate, $o.Slot, $o.OwSlot, $o.RowPicked, $o.List
        return $o
    } finally { [void][GF]::CloseHandle($h) }
}
function Place-Ui([int]$ux, [int]$uy) {
    # put the hand where the SHELL reads UI (ux,uy): no regime is assumed. Candidates, in order: the measured clip /
    # 4:3 picture rule, the raw 1:1 point, the conf-frame map of maplib (a 16:10 [Glide] Resolution); the first one the
    # shell's own mouse object reads back within 2 px is used.
    $geo = Geo; $cands = @(,(Hand-ForUi $geo $ux $uy)); $cands += ,@($ux, $uy)
    try { [void](Init-CursorMap); $cands += ,(UI-ToScreen $ux $uy) } catch {}
    $names = "clip/picture rule", "1:1", "conf frame map"
    for ($k = 0; $k -lt $cands.Count; $k++) {
        Move-Hand $cands[$k][0] $cands[$k][1] 300; $m = Shell-Read
        if ($m -and [Math]::Abs($m.MX - $ux) -le 2 -and [Math]::Abs($m.MY - $uy) -le 2) {
            return [pscustomobject]@{ X = $cands[$k][0]; Y = $cands[$k][1]; MX = $m.MX; MY = $m.MY; Ok = $true; How = "$($names[$k]) [$($geo.Kind)]" }
        }
    }
    Move-Hand $cands[0][0] $cands[0][1] 300; $m = Shell-Read
    return [pscustomobject]@{ X = $cands[0][0]; Y = $cands[0][1]; MX = $m.MX; MY = $m.MY; Ok = $false; How = "UNVERIFIED: no candidate read back as ($ux,$uy) [$($geo.Kind)]" }
}
function Click-UiPoint([string]$xy, [string]$what, [int]$settle = 900) {
    $v = $xy -split ","; $pl = Place-Ui ([int]$v[0]) ([int]$v[1]); Click-Here $settle
    Log ("    click {0} UI ({1}) hand ({2},{3}) shell-mouse ({4},{5}) {6}" -f $what, $xy, $pl.X, $pl.Y, $pl.MX, $pl.MY, $pl.How) $(if ($pl.Ok) { "Gray" } else { "Yellow" })
}
function Start-Garage([string]$tag) {
    $o = Run-Child "$Here\saves\garage-ui.ps1" "-Start $Bookmark -Row $Row -RowUy $($pos.Uy) -Scroll $($pos.Scroll) $gd$keep -BackupDir `"$Run\legb-backup-$tag`" -OutDir `"$Run`"" "garage-start-$tag.out"
    $o | Where-Object { $_ -match "B1\.|RUN ERROR|Abort|no sandbox|not in -GameDir" } | ForEach-Object { Log "    $_" }
    $p = Game-Proc; if (-not $p) { return $false }
    Focus
    $s = Shell-Read; Log "    shell: $($s.Text)"
    return ($s -and $s.Screen -eq 0xC00F -and $s.Sfn -eq 0x10003e70)
}
function Save-Files { $h = @{}; Get-ChildItem -LiteralPath $Game -File | Where-Object { $_.Name -ieq "savegame.dir" -or $_.Name -like "save*.cmp" } | ForEach-Object { $h[$_.Name.ToLower()] = Md5 $_.FullName }; return $h }
function Save-Changes([hashtable]$a, [hashtable]$b) {
    $out = @(); foreach ($k in (@($a.Keys) + @($b.Keys) | Sort-Object -Unique)) { if (-not $a.ContainsKey($k)) { $out += "$k (new)" } elseif (-not $b.ContainsKey($k)) { $out += "$k (gone)" } elseif ($a[$k] -ne $b[$k]) { $out += $k } }
    return $out
}

# ================================================================ rows =================================================
function Row1-Conf {
    Log "=== 1 conf accepted (global conf hidden) ===" "Cyan"
    $o = Run-Child "$Lab\tools\graphics\conf-probe.ps1" "-ClientRect -HideGlobal $gd$dry" "1-conf-clientrect.out"
    $o | ForEach-Object { Log "    $_" }
    if ($DryRun) { Check "1" "conf accepted (client rect)" $null "dry run: $(@($o | Select-Object -First 1))" }
    else {
        $l = @($o | Where-Object { $_ -match "^client \d+x\d+" }) | Select-Object -Last 1
        $g = @($o | Where-Object { $_ -match "global conf present" }) | Select-Object -Last 1
        Check "1" "conf accepted without the global file (client rect)" ("$l" -match "ACCEPTED") "$l; $g"
    }
    $confMd5 = Md5 "$Game\dgVoodoo.conf"
    $o = Run-Child "$Lab\tools\graphics\conf-probe.ps1" "-HideGlobal -Tag gate-$ts -OutFile `"$Run\1-conf-watermark.png`" $gd$keep$dry" "1-conf-watermark.out"
    $o | ForEach-Object { Log "    $_" }
    if (-not $DryRun) {
        Check "1" "watermark probe (3DfxWatermark = true for one boot)" $null "by eye: the 3dfx logo must be in $Run\1-conf-watermark.png (capture exists: $(Test-Path "$Run\1-conf-watermark.png")); boot: $(@($o | Where-Object { $_ -match 'in mission|CRASH|exited' }) -join ' ')"
        Check "1" "dgVoodoo.conf put back after the probe" ((Md5 "$Game\dgVoodoo.conf") -eq $confMd5 -and -not (Test-Path "$Game\dgVoodoo.conf.pre-probe")) "md5 $confMd5 -> $(Md5 "$Game\dgVoodoo.conf")"
    }
}
function Row2-Route {
    Log "=== 2 bookmark route: leg-b x $RouteRuns ($Bookmark row $Row) ===" "Cyan"
    $okN = 0; $n = if ($DryRun) { 1 } else { $RouteRuns }
    for ($i = 1; $i -le $n; $i++) {
        $o = Run-Child "$Here\saves\leg-b.ps1" "-Mode b1 $routeArgs $gd$keep -BackupDir `"$Run\legb-backup-route$i`"$dry" "2-leg-b-$i.out"
        if ($DryRun) { $o | ForEach-Object { Log "    $_" }; continue }
        $oc = @($o | Where-Object { $_ -match "OUTCOME:" }) | Select-Object -Last 1
        if ("$oc" -match "completed through B1\.10") { $okN++ }
        Log "    run ${i}: $oc"
        @($o | Where-Object { $_ -match "ABORT|RUN ERROR|B1\.6 loaded|-KeepInstalledDll|proxy installed" }) | ForEach-Object { Log "      $_" }
        if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game }
    }
    if ($DryRun) { Check "2" "bookmark route (leg-b)" $null "dry run: see 2-leg-b-1.out" }
    else { Check "2" "bookmark route (leg-b b1, $Bookmark row $Row)" ($okN -eq $RouteRuns) "$okN of $RouteRuns completed through B1.10 (logs: saves\runs\<ts>-b1, outputs 2-leg-b-*.out)" }
}
$script:Ffb = $null
function Row3-Trip {
    Log "=== 3 trip route through the launcher x $TripRuns ===" "Cyan"
    $base = "-RowUy $($pos.Uy) -Scroll $($pos.Scroll) $gd -ShotDir `"$Run`""
    if ($Launcher) { $base += " -Launcher `"$Launcher`""; if ($LauncherArgs) { $base += " -LauncherArgs `"$LauncherArgs`"" } } else { $base += " -Mode all120" }
    $up = 0; $fpsOk = 0; $det = @(); $n = if ($DryRun) { 1 } else { $TripRuns }
    for ($i = 1; $i -le $n; $i++) {
        $extra = if ($i -eq 1 -and (Want 8)) { " -CheckFfb" } else { "" }
        $o = Run-Child "$Here\option6-trip-test.ps1" "$base$extra$dry" "3-trip-$i.out"
        if ($DryRun) { $o | ForEach-Object { Log "    $_" }; continue }
        $l = @($o | Where-Object { $_ -match "engine up:" }) | Select-Object -Last 1
        Log "    run ${i}: $l"
        @($o | Where-Object { $_ -match "launcher|screenshot|sandbox:" }) | ForEach-Object { Log "      $_" }
        if ($i -eq 1) { $script:Ffb = @($o | Where-Object { $_ -match "^ffb: " }) }
        if (Test-Path "$Run\option6-launcher.png") { Move-Item "$Run\option6-launcher.png" "$Run\3-trip-$i.png" -Force }
        if (Test-Path "$Run\option6-all120.png") { Move-Item "$Run\option6-all120.png" "$Run\3-trip-$i.png" -Force }
        $isUp = ("$l" -match "engine up: True"); if ($isUp) { $up++ }
        $hb = 0.0; $ex = 0.0
        if ("$l" -match "proxy fps (-?[\d.]+)") { $hb = [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture) }
        if ("$l" -match "exe fps (-?[\d.]+)") { $ex = [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture) }
        $fps = if ($hb -gt 1) { $hb } else { $ex }; $src = if ($hb -gt 1) { "heartbeat" } else { "exe frame counter (heartbeat not moving)" }
        $inBand = ($fps -ge 0.9 * $ExpectFps -and $fps -le 1.1 * $ExpectFps); if ($isUp -and $inBand) { $fpsOk++ }
        $det += "run ${i}: up=$isUp, $fps fps by $src (heartbeat $hb, exe $ex)"
        if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game }
    }
    if ($DryRun) { Check "3" "trip route through the launcher" $null "dry run: see 3-trip-1.out"; return }
    Check "3" "trip route through $(if ($Launcher) { Split-Path -Leaf $Launcher } else { 'TEST-FRAMERATE all120' }): engine up" ($up -eq $TripRuns) "$up of $TripRuns; $($det -join '; ')"
    Check "3" "frame rate within 10 % of $ExpectFps" ($fpsOk -eq $TripRuns) "$fpsOk of $TripRuns; $($det -join '; ')"
}
function Save-Session([string]$answer, $scratch) {
    # garage -> SAVE BOOKMARK -> 10 s idle -> scratch row -> SAVE x2 -> the overwrite prompt -> $answer
    $tag = "4-$answer"
    if (-not (Start-Garage "save-$answer")) { Check "4" "save screen [$answer]: garage reached" $false "see garage-start-save-$answer.out"; return }
    try {
        Log "    geometry: $((Geo).Text)"
        # the reference for "written": savegame.dir and every saveNNN.cmp as they are in the garage, after the load
        Start-Sleep -Milliseconds 800; $prepared = Save-Files
        Click-UiPoint $SaveBookmarkBtn "SAVE BOOKMARK" 600
        $s0 = Shell-Read; Log "    after SAVE BOOKMARK: $($s0.Text)"
        # on the save screen: the menu function is SaveBookmark, or (leg-a.ps1 A9) the edit loop is live: slot -1 with a bookmark list
        $onSave = ($s0.Mfn -eq 0x10014cd0) -or ($s0.Slot -eq -1 -and $s0.List -ne 0 -and $s0.List -ne [int]::MinValue)
        if (-not $onSave) { Shot "$tag-not-on-save-screen"; Check "4" "save screen [$answer]: Save Bookmark screen up" $false $s0.Text; return }
        Log "    idle 10 s"; Start-Sleep -Seconds 10
        $s1 = Shell-Read
        $pl = Place-Ui 300 300; $s2 = Shell-Read
        if ($answer -eq "NO") {
            Check "4" "save screen: mouse gate [shell+0x43224] stays 1 over 10 s idle" ($s1.Gate -eq 1) "before $($s0.Gate), after $($s1.Gate)"
            Check "4" "save screen: the shell mouse still follows the hand after the idle" ([Math]::Abs($s2.MX - 300) -le 1 -and [Math]::Abs($s2.MY - 300) -le 1) "target (300,300) read ($($s2.MX),$($s2.MY)); $($pl.How)"
        }
        Shot "$tag-1-idle"
        $sp = Row-Pos $scratch.Index $scratch.Records
        for ($k = 0; $k -lt $sp.Scroll; $k++) { Click-UiPoint "212,422" "scroll down" 250 }
        Click-UiPoint "320,$($sp.Uy)" "scratch row $($scratch.Index) ('GATE SCRATCH')"; Shot "$tag-2-row"
        Click-UiPoint $SaveBtn "SAVE (1)"; Click-UiPoint $SaveBtn "SAVE (2)" 1500
        $s3 = Shell-Read; Log "    after SAVE x2: $($s3.Text)"; Shot "$tag-3-prompt"
        $chg = @(Save-Changes $prepared (Save-Files))
        if ($chg.Count -gt 0) { Check "4" "save screen [$answer]: overwrite prompt before anything is written" $false "SAVE x2 wrote without a prompt: $($chg -join ', ') (the row click did not select the scratch bookmark? see $tag-2-row.png); $($s3.Text)"; return }
        if ($answer -eq "NO") {
            Check "4" "save screen: SAVE x2 by mouse, nothing written before the prompt is answered" $true "$($s3.Text); scratch is slot $($scratch.Index) (owSlot above should name it); the prompt itself: capture $tag-3-prompt.png"
            Click-UiPoint $NoBtn "NO (overwrite prompt)" 1500
            Start-Sleep -Seconds 2
            $s4 = Shell-Read; Shot "$tag-4-after-no"
            $chg = @(Save-Changes $prepared (Save-Files))
            $reacted = ($s4.Text -replace "mouse=\([^)]*\)", "") -ne ($s3.Text -replace "mouse=\([^)]*\)", "")
            if ($chg.Count -gt 0) { Check "4" "save screen: NO writes nothing" $false "changed after NO: $($chg -join ', ')" }
            elseif ($reacted) { Check "4" "save screen: NO writes nothing" $true "savegame.dir and every saveNNN.cmp unchanged 3.5 s after the click; shell before: $($s3.Text) / after: $($s4.Text)" }
            else { Check "4" "save screen: NO writes nothing" $null "nothing was written, but the shell state did not change after the click at ($NoBtn): the NO button position is not verified - confirm with $tag-3-prompt.png / $tag-4-after-no.png (-NoBtn x,y)" }
        } else {
            Click-UiPoint $YesBtn "YES (overwrite prompt)" 500
            $chg = @(); for ($k = 0; $k -lt 20; $k++) { Start-Sleep -Milliseconds 250; $chg = @(Save-Changes $prepared (Save-Files)); if ($chg.Count -gt 0) { break } }
            Start-Sleep -Seconds 1
            $chg = @(Save-Changes $prepared (Save-Files)); $s4 = Shell-Read; Shot "$tag-4-after-yes"
            $other = @($chg | Where-Object { $_ -ne "savegame.dir" -and $_ -ne "$($scratch.File).cmp" })
            Check "4" "save screen: YES writes the scratch bookmark and no other" ($chg.Count -gt 0 -and $other.Count -eq 0) "changed: $(if ($chg.Count) { $chg -join ', ' } else { 'nothing' }) (scratch = $($scratch.File).cmp, slot $($scratch.Index)); shell after: $($s4.Text)"
        }
    } finally { Close-Game }
}
function Row4-Save {
    Log "=== 4 save screen (scratch bookmark; NO, then YES) ===" "Cyan"
    $scratch = New-ScratchDir $Row
    Log "    scratch: record $($scratch.Index) 'GATE SCRATCH' -> $($scratch.File).cmp, a copy of $($scratch.SrcFile).cmp; $($scratch.Records) records"
    if ($DryRun) {
        # build the scratch set beside the run and let the save editor validate it; the game folder is not written
        $tmp = Join-Path $Run "4-scratch-dryrun"; New-Item -ItemType Directory -Force $tmp | Out-Null
        Get-ChildItem -LiteralPath $Game -File -Filter "save*.cmp" | ForEach-Object { Copy-Item $_.FullName $tmp }
        Copy-Item (Join-Path $tmp "$($scratch.SrcFile).cmp") (Join-Path $tmp "$($scratch.File).cmp")
        [IO.File]::WriteAllBytes((Join-Path $tmp "savegame.dir"), $scratch.Bytes)
        $o = Py "$Repo\i76-save-editor.py" --dir $tmp --check; $rc = $script:PyRc
        $l = @(Py "$Repo\i76-save-editor.py" --dir $tmp --list) | Select-Object -Last 1
        $sp = Row-Pos $scratch.Index $scratch.Records
        Check "4" "scratch bookmark set is valid (built beside the run, not installed)" ($rc -eq 0 -and "$l" -match "GATE SCRATCH") "--check exit $rc; last row: $l; save-board click (320,$($sp.Uy)) after $($sp.Scroll) scroll clicks"
        $o = Run-Child "$Here\saves\garage-ui.ps1" "-Start $Bookmark -Row $Row -RowUy $($pos.Uy) -Scroll $($pos.Scroll) $gd$keep -BackupDir `"$Run\legb-backup-save`" -OutDir `"$Run`" -DryRun" "4-garage-dryrun.out"
        $o | ForEach-Object { Log "    $_" }
        return
    }
    $dirBefore = Md5 "$Game\savegame.dir"; $dirCopy = Join-Path $Run "4-savegame.dir.before-scratch"
    Copy-Item "$Game\savegame.dir" $dirCopy
    try {
        Copy-Item "$Game\$($scratch.SrcFile).cmp" "$Game\$($scratch.File).cmp"
        [IO.File]::WriteAllBytes("$Game\savegame.dir", $scratch.Bytes)
        $o = Py "$Repo\i76-save-editor.py" --dir $Game --check; $rc = $script:PyRc
        if ($rc -ne 0) { Check "4" "scratch bookmark installed" $false "i76-save-editor.py --check exit $rc after adding the scratch record: $(@($o | Select-Object -Last 2) -join ' / ')"; return }
        Log "    scratch installed; --check OK"
        foreach ($answer in "NO", "YES") {
            if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game }
            Save-Session $answer $scratch
        }
        $o = Py "$Repo\i76-save-editor.py" --dir $Game --check; $rc = $script:PyRc
        Check "4" "savegame.dir still exact after the save (i76-save-editor.py --check)" ($rc -eq 0) "exit $rc; savegame.dir $((Get-Item "$Game\savegame.dir").Length) B"
    } finally {
        if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game }
        Remove-Item "$Game\$($scratch.File).cmp" -ErrorAction SilentlyContinue
        Copy-Item $dirCopy "$Game\savegame.dir" -Force
        $back = ((Md5 "$Game\savegame.dir") -eq $dirBefore) -and -not (Test-Path "$Game\$($scratch.File).cmp")
        Check "4" "scratch bookmark removed, savegame.dir put back" $back "savegame.dir md5 $(Md5 "$Game\savegame.dir") (before $dirBefore); $($scratch.File).cmp present: $(Test-Path "$Game\$($scratch.File).cmp")"
    }
}
function Row5-EscMenu {
    Log "=== 5 Esc-menu Exit at the drawn position ===" "Cyan"
    if ($DryRun) { $o = Run-Child "$Here\proxy-run.ps1" "-Mission t01 -Hold 0 -KeepAlive $gd$keep -DryRun" "5-escmenu-dryrun.out"; $o | ForEach-Object { Log "    $_" }; Check "5" "Esc-menu Exit" $null "dry run: see 5-escmenu-dryrun.out"; return }
    $o = Run-Child "$Here\test-escmenu.ps1" "-Stage open -Tag gate-$ts $gd$keep" "5-escmenu-open.out"
    $o | Where-Object { $_ -match "driving:|menu:|cursor after|u32x.dll|in mission|CRASH|exited|refusing" } | ForEach-Object { Log "    $_" }
    $c = $null
    try {
        if (-not (Game-Proc)) { Check "5" "Esc menu opened" $false "test-escmenu -Stage open left no game (see 5-escmenu-open.out)"; return }
        Focus; $c = Mem-Open
        $mode = Mem-I32 $c 0x4fe534
        if ($mode -ne 0x10) { Send-Key $VK.ESC; Start-Sleep -Milliseconds 1500; $mode = Mem-I32 $c 0x4fe534 }
        if ($mode -ne 0x10) { Shot "5-not-in-menu"; Check "5" "Esc menu is up (mode 0x10)" $false ("mode 0x{0:x}" -f $mode); return }
        $geo = Geo; Log "    geometry: $($geo.Text)"
        $v = $Exit -split ","; $fx = [int]$v[0]; $fy = [int]$v[1]
        $fw = (Mem-I32 $c 0x5dcee4) - (Mem-I32 $c 0x5dcedc); $fh = (Mem-I32 $c 0x5dcee8) - (Mem-I32 $c 0x5dcee0)
        if ($fw -lt 320 -or $fh -lt 200) { $fw = 640; $fh = 480 }
        # Where the engine frame is PRESENTED depends on the conf: with a 16:10 [Glide] Resolution and stretched_ar the
        # frame fills a 16:10 rectangle (maplib's frame rect, from this folder's conf and the live client); with a 4:3
        # one it is the 4:3 picture. Candidate A = the conf's frame, B = the 4:3 picture. They coincide for a 4:3 conf.
        [void](Init-CursorMap); $fr = Get-FrameRect
        $ax = [int]($fr.X + [Math]::Floor($fx * $fr.W / $fw + 0.5)); $ay = [int]($fr.Y + [Math]::Floor($fy * $fr.H / $fh + 0.5))
        $bx = [int]($geo.PicL + [Math]::Floor($fx * 640 * $geo.Scale / $fw + 0.5)); $by = [int]($geo.PicT + [Math]::Floor($fy * 480 * $geo.Scale / $fh + 0.5))
        $same = ([Math]::Abs($ax - $bx) -le 3 -and [Math]::Abs($ay - $by) -le 3)
        Log "    Exit frame ($fx,$fy) of ${fw}x${fh}: conf frame $($fr.W)x$($fr.H) at ($($fr.X),$($fr.Y)) -> ($ax,$ay); 4:3 picture -> ($bx,$by)"
        $hit = ""; $reads = @()
        foreach ($cand in @(@("conf frame", $ax, $ay), @("4:3 picture", $bx, $by))) {
            if ($hit) { break }
            if ($cand[0] -eq "4:3 picture" -and $same) { break }
            Move-Hand $cand[1] $cand[2] 500
            $pt = New-Object GF+POINT; [void][GF]::GetCursorPos([ref]$pt)
            Shot-Client ("5-exit-before-" + ($cand[0] -replace "[^a-z0-9]", ""))
            Click-Here 300
            for ($k = 0; $k -lt 10; $k++) { if ((Mem-I32 $c 0x4fe534) -ne 0x10) { $hit = $cand[0]; break }; Start-Sleep -Milliseconds 200 }
            $reads += ("{0} ({1},{2}) pointer read back ({3},{4}): {5}" -f $cand[0], $cand[1], $cand[2], $pt.X, $pt.Y, $(if ($hit) { "HIT" } else { "no" }))
        }
        Shot-Client "5-exit-after"
        $detail = ("{0}; clip [{1}]; mode 0x10 -> 0x{2:x}; captures 5-exit-*.png (whole client, the pointer position is in the file name's candidate)" -f ($reads -join "; "), $geo.Kind, (Mem-I32 $c 0x4fe534))
        if ($hit -and ($same -or $hit -eq "conf frame")) { Check "5" "Esc-menu Exit hit from where it is drawn" $true $detail }
        elseif ($hit) { Check "5" "Esc-menu Exit hit from where it is drawn" $null ("Exit answered only from the 4:3-picture position, not from the conf-frame position: either the picture is 4:3 inside the frame (then this is a pass) or the pointer is off the drawn item by $([Math]::Abs($ax - $bx)) px under this conf. Decide by eye. " + $detail) }
        else { Check "5" "Esc-menu Exit hit from where it is drawn" $false $detail }
    } finally {
        if ($c) { Mem-Close $c }
        Run-Child "$Here\test-escmenu.ps1" "-Stage close $gd" "5-escmenu-close.out" | Out-Null
        if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Close-Game }
    }
}
function Row6-Melee {
    Log "=== 6 melee by the menus ===" "Cyan"
    $o = Run-Child "$Here\menu-route-test.ps1" "-Tag gate $gd$keep$dry" "6-melee.out"
    if ($DryRun) { $o | ForEach-Object { Log "    $_" }; Check "6" "melee by menus" $null "dry run: see 6-melee.out"; return }
    $l = @($o | Where-Object { $_ -match "enter-melee exit" }) | Select-Object -Last 1
    Log "    $l"
    Check "6" "melee by menus (menu-route-test.ps1)" ("$l" -match "enter-melee exit 0 " -and "$l" -notmatch "player 0x0 ") "$l"
}
function Row7-Lint {
    Log "=== 7 input.map ===" "Cyan"
    $o = Py "$Repo\tools\lint-input-map.py" $Game; $rc = $script:PyRc
    $o | Set-Content (Join-Path $Run "7-lint.out") -Encoding UTF8
    Check "7" "lint-input-map.py" ($rc -eq 0) "exit $rc; $(@($o | Select-Object -Last 2) -join ' / ')"
    $now = if (Test-Path "$Game\input.map") { Md5 "$Game\input.map" } else { "ABSENT" }
    Check "7" "input.map unchanged by the gate" ($now -eq $inputMd5) "md5 $inputMd5 -> $now"
}
function Row8-Ffb {
    Log "=== 8 force feedback (check-ffb.ps1, read in row 3's first mission) ===" "Cyan"
    if ($DryRun) { Check "8" "force feedback" $null "dry run: row 3 would pass -CheckFfb to option6-trip-test.ps1 (check-ffb.ps1 present: $(Test-Path "$Repo\tools\check-ffb.ps1"))"; return }
    if (-not (Want 3)) { Check "8" "force feedback" $null "not run: it rides on row 3 (include 3 in -Only)"; return }
    $t = @($script:Ffb | ForEach-Object { "$_" -replace "^ffb: ", "" } | Where-Object { $_.Trim() })
    $t | ForEach-Object { Log "    $_" }
    $txt = $t -join " / "
    if ($txt -match "FFB IS LIVE") { Check "8" "force feedback live in the mission" $true ((@($t | Where-Object { $_ -match "loaded|detected|heap|device ptr" }) -join "; ")) }
    elseif ($txt -match "MODULE LOADED BUT NO DEVICE") { Check "8" "force feedback: module loaded, NO device opened" $null "I7_SFRCE.DLL loaded and resolved, but no FF device: wheel not plugged in before launch, or held by another program. Not a folder fault by itself; hand check 5.2 item 2. $((@($t | Where-Object { $_ -match 'detected|heap|device ptr|panel' }) -join '; '))" }
    elseif ($txt -match "never loaded") { Check "8" "force feedback module loaded" $false $txt }
    else { Check "8" "force feedback" $null "check-ffb gave no verdict: $(if ($txt) { $txt } else { 'no output (the engine was not up in row 3 run 1?)' })" }
}

# ================================================================ run ==================================================
$glob = "$env:APPDATA\dgVoodoo\dgVoodoo.conf"; $globHidden = "$env:APPDATA\dgVoodoo\dgVoodoo.conf.hidden-by-gate"; $hid = $false
try {
    if (Test-Path $globHidden) { Log "  a global conf hidden by an earlier gate is still there ($globHidden): it is put back at the end" "Yellow"; $hid = $true }
    if (-not $KeepGlobalConf -and -not $DryRun -and (Test-Path $glob)) {
        if (Test-Path $globHidden) { throw "both $glob and $globHidden exist: sort that out by hand first" }
        Rename-Item $glob (Split-Path $globHidden -Leaf); $hid = $true
        Log "  global dgVoodoo.conf hidden for the gate: $globHidden"
    } elseif ($DryRun) { Log "  global dgVoodoo.conf present: $(Test-Path $glob) (a real run renames it to $(Split-Path $globHidden -Leaf) until the end)" }
    foreach ($r in $Rows) {
        if (-not $DryRun -and (Get-Process | Where-Object { $_.ProcessName -like "i76*" })) { Close-Game }
        try {
            switch ($r) {
                1 { Row1-Conf } 2 { Row2-Route } 3 { Row3-Trip } 4 { Row4-Save } 5 { Row5-EscMenu } 6 { Row6-Melee } 7 { Row7-Lint } 8 { Row8-Ffb }
                default { Check "$r" "unknown row" $false "rows are 1..8" }
            }
        } catch { Check "$r" "row ran to the end" $false "$_"; try { if (-not $DryRun) { Close-Game } } catch {} }
    }
} finally {
    try { if (-not $DryRun -and (Get-Process | Where-Object { $_.ProcessName -like "i76*" })) { Close-Game } } catch {}
    if ($hid -and (Test-Path $globHidden)) {
        if (Test-Path $glob) { Log "  CANNOT put the global conf back: $glob exists again; the hidden one stays as $globHidden" "Red" }
        else { Rename-Item $globHidden "dgVoodoo.conf"; Log "  global dgVoodoo.conf put back: $(Test-Path $glob)" }
    }
    if (-not $DryRun) { Check "1" "global dgVoodoo.conf back under its own name" (-not (Test-Path $globHidden)) "present: $(Test-Path $glob); hidden copy left: $(Test-Path $globHidden)" }
    # ---- S: the player state must end byte-identical ------------------------------------------------------------------
    Log "=== S saves: compare with the backup ===" "Cyan"
    try {
        $after = Snapshot-Folder
        $moved = @(State-Diff $before $after)
        $restored = @()
        if ($moved.Count -gt 0 -and -not $DryRun) { $restored = @(Restore-State $before $BakDir (Join-Path $Run "created-during-gate")); $after = Snapshot-Folder }
        $still = @(State-Diff $before $after)
        $detail = "$nBak files, backup $BakDir; "
        $detail += if ($moved.Count -eq 0) { "nothing differed after the runs" } else { "changed by the runs and put back: $($restored -join ', ')" }
        if ($still.Count -gt 0) { $detail += "; STILL DIFFERENT: $($still -join ', ')" }
        Check "S" "player state byte-identical to the backup (md5)" ($still.Count -eq 0) $detail
        # ---- D: everything else at the top level ----------------------------------------------------------------------
        $drift = @(); $logs = @()
        foreach ($rel in (@($before.Keys) + @($after.Keys) | Sort-Object -Unique)) {
            if (Is-State $rel) { continue }
            $what = if (-not $before.ContainsKey($rel)) { "$rel (new)" } elseif (-not $after.ContainsKey($rel)) { "$rel (gone)" } elseif ($before[$rel] -ne $after[$rel]) { $rel } else { $null }
            if (-not $what) { continue }
            if ($rel -match '(?i)\.(log|txt)$') { $logs += $what } else { $drift += $what }
        }
        Check "D" "no other top-level file changed (binaries, conf, maps)" ($drift.Count -eq 0) "$(if ($drift.Count) { 'CHANGED: ' + ($drift -join ', ') + '; ' })logs written: $(if ($logs.Count) { $logs -join ', ' } else { 'none' }); lock left: $(Test-Path "$Game\.console-test.lock"); .pretest left: $(Test-Path "$Game\STRLKUP.DLL.pretest")"
    } catch { Check "S" "player state compare ran" $false "$_" }
    # ---- the table --------------------------------------------------------------------------------------------------------
    $fail = @($script:Results | Where-Object { $_.Result -eq "FAIL" }).Count
    $pass = @($script:Results | Where-Object { $_.Result -eq "PASS" }).Count
    $info = @($script:Results | Where-Object { $_.Result -eq "INFO" }).Count
    $md = @("# gate-folder $ts$(if ($DryRun) { ' (DRY RUN: no game started)' })", "",
            "- folder: ``$Game``", "- launcher: ``$(if ($Launcher) { "$Launcher $LauncherArgs".Trim() } else { 'TEST-FRAMERATE.ps1 -Mode all120' })``",
            "- bookmark: $Bookmark, row $Row of $($marks.Count); runs: route x$RouteRuns, trip x$TripRuns; rows: $($Rows -join ', ')",
            "- proxy: $(if ($SwapDll) { 'music-fix build swapped in per run' } else { 'as installed' }); global conf hidden: $(-not $KeepGlobalConf -and -not $DryRun)",
            "- PASS $pass, FAIL $fail, INFO $info", "", "| # | check | result | detail |", "|---|---|---|---|")
    $script:Results | ForEach-Object { $md += "| {0} | {1} | {2} | {3} |" -f $_.Row, $_.Check, $_.Result, $_.Detail }
    $md | Set-Content (Join-Path $Run "results.md") -Encoding UTF8
    Log ""; $md | ForEach-Object { Log $_ }
    Log "PASS $pass  FAIL $fail  INFO $info  -> $(Join-Path $Run 'results.md')" $(if ($fail) { "Red" } else { "Green" })
}
exit $fail
