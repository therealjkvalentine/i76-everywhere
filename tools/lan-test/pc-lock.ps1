# pc-lock.ps1 -Take | -Release : the lab console lock (i76-uncap-lab\CONSOLE-LOCK.md) for the PC cells of the LAN matrix.
# -Take polls every 20 s for up to -WaitMin minutes; it takes the lock only when .console-owner is absent, no i76.exe runs
# and no <folder>\.console-test.lock exists in game, game-alt, game-dd-20261003.
param([switch]$Take, [switch]$Release, [int]$WaitMin = 60, [string]$Who = "lan-test (LAN-MATRIX-2026-10-18)")
$lab = "C:\Users\james\i76-uncap-lab"; $f = Join-Path $lab ".console-owner"
if ($Release) { if ((Test-Path $f) -and ((Get-Content $f -Raw) -like "$Who*")) { Remove-Item $f -Force; "released" } else { "not ours / absent: $(if (Test-Path $f) { Get-Content $f -Raw })" }; exit 0 }
$end = (Get-Date).AddMinutes($WaitMin)
while ((Get-Date) -lt $end) {
  $busy = (Test-Path $f) -or (Get-Process i76 -ErrorAction SilentlyContinue) -or
          (@("game","game-alt","game-dd-20261003") | Where-Object { Test-Path (Join-Path $lab "$_\.console-test.lock") })
  if (-not $busy) {
    try { $s = [IO.File]::Open($f, 'CreateNew', 'Write'); $b = [Text.Encoding]::ASCII.GetBytes("$Who pid $PID $(Get-Date -Format s)"); $s.Write($b, 0, $b.Length); $s.Close(); "TAKEN $(Get-Date -Format s)"; exit 0 } catch { }
  }
  Start-Sleep -Seconds 20
}
"TIMEOUT (holder: $(if (Test-Path $f) { Get-Content $f -Raw }))"; exit 1
