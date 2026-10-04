<#
.SYNOPSIS
  launch.ps1 - H0 launcher for the Interstate '76 sandbox (method doc section 4.5, gates H0/H10). Task 1.

.DESCRIPTION
  Refuses unless the target exe's md5 is the pristine 9a232dcc2c164648cff20c414c1f9698, or the
  pristine+i76fix-p1 file 58d9dec00c18a5383820e77e51850b74 (the only exe bytes that run on Windows 10
  19045: captures\001-smoke), or -AllowPatched is given (then the run is stamped patched-build-only).
  -StrictPristine refuses the +i76fix-p1 file too.
  Refuses when the session is RDP: parses `query session` (its exit code is 255/1 even on success and
  $env:SESSIONNAME is empty in agent shells - AGENTS.md), requires the current-marked line to be
  'console ... Active', no 'rdp-tcp#N' session Active, TerminalServerSession false, and this process's
  SessionId equal to WTSGetActiveConsoleSessionId.
  First log line: 'launched <path> md5 <md5> launch.ps1 <version>'. After -SettleSeconds it calls
  tools\which_build.py --pid <pid> --out captures\<CaptureId>\manifest.json --stamp <class>.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\launch.ps1 -CaptureId 000-live-check
  powershell -ExecutionPolicy Bypass -File tools\launch.ps1 -Exe i76.exe -DryRun          # refused (md5)
  powershell -ExecutionPolicy Bypass -File tools\launch.ps1 -Exe i76.exe -AllowPatched     # patched-build-only
  powershell -ExecutionPolicy Bypass -File tools\launch.ps1 -CaptureId 008-builtin-renderer -GameArgs @()   # no -glide

  Exit codes: 0 launched and H0 passed; 1 launched but which_build reported H0 FAIL; 3 refused (md5);
  4 refused (session); 5 process exited before the settle time; 6 dry run (nothing launched); 2 error.
#>
[CmdletBinding()]
param(
    [string]$GameDir = "C:\Users\james\i76-uncap-lab\game",
    # -Exe: file name inside -GameDir; the default is the only exe that runs on this host (H0, console-smoke)
    [string]$Exe = "i76_pristine_fix.exe",
    # -GameArgs @() is accepted (0.2): the no -glide run of item 008 no longer bypasses the launcher
    [string[]]$GameArgs = @("-glide"),
    [string]$CaptureId = ("launch-" + (Get-Date -Format "yyyyMMdd-HHmmss")),
    [string]$MapRoot = "C:\Users\james\i76-map",
    [int]$SettleSeconds = 8,
    [switch]$AllowPatched,
    [switch]$StrictPristine,
    [switch]$DryRun,
    # test hook: read `query session` output from this file instead of running it (parser test only;
    # the TerminalServerSession and SessionId checks still run, so it cannot make an RDP session pass)
    [string]$SessionProbeFile = ""
)

$Version = "0.2"
$PristineMd5 = "9a232dcc2c164648cff20c414c1f9698"
$PristineFixMd5 = "58d9dec00c18a5383820e77e51850b74"
$ErrorActionPreference = "Stop"

$exePath = Join-Path $GameDir $Exe
$capDir = Join-Path (Join-Path $MapRoot "captures") $CaptureId
$logPath = Join-Path $capDir "launch.log"
$script:LogLines = @()

function Log([string]$s) {
    $script:LogLines += $s
    Write-Output $s
}
function Flush-Log {
    if (-not (Test-Path $capDir)) { New-Item -ItemType Directory -Force -Path $capDir | Out-Null }
    Set-Content -Path $logPath -Value $script:LogLines -Encoding utf8
}

if (-not (Test-Path $exePath)) { Write-Output "ERROR: $exePath not found"; exit 2 }
$md5 = (Get-FileHash -Algorithm MD5 -Path $exePath).Hash.ToLower()

# ---- md5 gate (H0) ----
$class = $null
if ($md5 -eq $PristineMd5) { $class = "pristine" }
elseif ($md5 -eq $PristineFixMd5 -and -not $StrictPristine) { $class = "pristine+i76fix-p1" }
elseif ($AllowPatched) { $class = "patched-build-only" }

if ($null -eq $class) {
    Log "refused $exePath md5 $md5 launch.ps1 $Version reason=md5-not-pristine (want $PristineMd5 or $PristineFixMd5; pass -AllowPatched to stamp patched-build-only)"
    Flush-Log
    exit 3
}

# ---- session gate (H10): never launch over RDP ----
$qs = @()
if ($SessionProbeFile -ne "") {
    $qs = Get-Content -Path $SessionProbeFile | ForEach-Object { "$_" }
} else {
    try { $qs = & query session 2>&1 | ForEach-Object { "$_" } } catch { $qs = @("query session failed: $_") }
}
$rows = @()
foreach ($line in $qs) {
    if ($line -match '^\s*SESSIONNAME' -or $line.Trim() -eq '') { continue }
    $current = $line.StartsWith('>')
    $parts = ($line.Substring(1) -split '\s+') | Where-Object { $_ -ne '' }
    if ($parts.Count -lt 2) { continue }
    $idIdx = -1
    for ($i = 0; $i -lt $parts.Count; $i++) { if ($parts[$i] -match '^\d+$') { $idIdx = $i; break } }
    if ($idIdx -lt 0) { continue }
    $state = if ($idIdx + 1 -lt $parts.Count) { $parts[$idIdx + 1] } else { '' }
    $rows += [pscustomobject]@{ Session = $parts[0]; Id = [int]$parts[$idIdx]; State = $state; Current = $current }
}
$consoleRow = $rows | Where-Object { $_.Session -ieq 'console' } | Select-Object -First 1
$currentRow = $rows | Where-Object { $_.Current } | Select-Object -First 1
$rdpActive = @($rows | Where-Object { $_.Session -imatch '^rdp-tcp#' -and $_.State -ieq 'Active' }).Count -gt 0
Add-Type -AssemblyName System.Windows.Forms
$tss = [System.Windows.Forms.SystemInformation]::TerminalServerSession
$sig = '[DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();'
try { Add-Type -MemberDefinition $sig -Name K32 -Namespace LaunchH0 -ErrorAction SilentlyContinue } catch {}
$consoleId = [LaunchH0.K32]::WTSGetActiveConsoleSessionId()
$mySession = (Get-Process -Id $PID).SessionId

$reasons = @()
if ($tss) { $reasons += "TerminalServerSession=True" }
if ($rdpActive) { $reasons += "an rdp-tcp# session is Active" }
if ($null -eq $consoleRow) { $reasons += "no console row in query session" }
elseif ($consoleRow.State -ine 'Active') { $reasons += "console session state is '$($consoleRow.State)' not Active" }
if ($null -ne $currentRow -and $currentRow.Session -ine 'console') { $reasons += "current session is '$($currentRow.Session)' not console" }
if ($mySession -ne $consoleId) { $reasons += "this process SessionId $mySession != console session $consoleId" }
$sessionSummary = "session: mine=$mySession console=$consoleId tss=$tss current=$(if ($currentRow) { $currentRow.Session } else { '(none marked)' }) consoleState=$(if ($consoleRow) { $consoleRow.State } else { 'n/a' }) rdpActive=$rdpActive"

if ($reasons.Count -gt 0) {
    Log "refused $exePath md5 $md5 launch.ps1 $Version reason=session ($($reasons -join '; '))"
    Log $sessionSummary
    foreach ($l in $qs) { Log "  query session: $l" }
    Flush-Log
    exit 4
}

if ($DryRun) {
    Log "dry-run $exePath md5 $md5 launch.ps1 $Version class=$class args=[$($GameArgs -join ' ')] capture=$CaptureId (nothing launched)"
    Log $sessionSummary
    Flush-Log
    exit 6
}

# ---- launch ----
Log "launched $exePath md5 $md5 launch.ps1 $Version"
Log "class=$class args=[$($GameArgs -join ' ')] capture=$CaptureId time=$(Get-Date -Format o)"
Log $sessionSummary
Flush-Log
# PowerShell 5.1 rejects Start-Process -ArgumentList @() ("Cannot validate argument ... empty collection"),
# so the no-argument run (item 008, built-in renderer: no -glide) branches (Phase 0 blocker 44).
if ($GameArgs.Count -eq 0) {
    Log "no game arguments: Start-Process without -ArgumentList (built-in render path, no -glide)"
    $proc = Start-Process -FilePath $exePath -WorkingDirectory $GameDir -PassThru
} else {
    $proc = Start-Process -FilePath $exePath -ArgumentList $GameArgs -WorkingDirectory $GameDir -PassThru
}
Log "pid=$($proc.Id) started=$(Get-Date -Format o)"
Start-Sleep -Seconds $SettleSeconds
$proc.Refresh()
if ($proc.HasExited) {
    Log "process exited before settle: exit code $($proc.ExitCode) (0x$('{0:x}' -f $proc.ExitCode)) after $SettleSeconds s"
    Flush-Log
    exit 5
}
$wb = Join-Path (Join-Path $MapRoot "tools") "which_build.py"
$manifest = Join-Path $capDir "manifest.json"
Log "which_build: python $wb --pid $($proc.Id) --game-dir $GameDir --out $manifest --stamp $class"
$wbOut = & python $wb --pid $proc.Id --game-dir $GameDir --out $manifest --stamp $class 2>&1 | ForEach-Object { "$_" }
$wbRc = $LASTEXITCODE
foreach ($l in $wbOut) { Log "  $l" }
Log "which_build exit=$wbRc (0 = H0 pass)"
Flush-Log
if ($wbRc -eq 0) { exit 0 } else { exit 1 }
