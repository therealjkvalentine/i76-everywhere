<#
  selftest-stimuli.ps1 - exercise stimuli.ps1 against a throwaway 32-bit process (SysWOW64 notepad), never the game.

      powershell -ExecutionPolicy Bypass -File tools\harness\selftest-stimuli.ps1 [-CapturesRoot <scratch dir>]

  What it proves: dot-source parses; Open-Stim attaches by -ProcName; every read of a game address against a
  process that has nothing mapped there returns $null (not 0); the -DryRun stimuli send NO keys and still
  write their manifest entries; Add-ManifestEntry's read-back counts; Close-Stim detaches. Exit 0 = pass.
  It cannot prove the game-side predictions (needs the console sitting).
#>
param([string]$CapturesRoot = (Join-Path $env:TEMP 'stimuli-selftest'))
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\stimuli.ps1"
$np = Start-Process -FilePath "$env:WINDIR\SysWOW64\notepad.exe" -PassThru -WindowStyle Minimized
Start-Sleep -Milliseconds 800
$fails = @()
try {
    $s = Open-Stim -CaptureId ("selftest-" + (Get-Date -Format "yyyyMMdd-HHmmss")) -ProcName notepad -RequirePath '' -CapturesRoot $CapturesRoot
    if ($s.Proc.Id -ne $np.Id) { $fails += "attached to pid $($s.Proc.Id), expected $($np.Id)" }
    # Read the null correctly: notepad's heap MAY or may not be mapped at the game's addresses (it was on the
    # second run of this test: 0x5a7e1c read 6488109), so those reads are informational. What must hold:
    # an unmapped page fails to $null (never 0), and a mapped page reads (MZ at the image base).
    $c = Get-Canary $s
    Write-Host ("  game addresses on notepad: frame counter {0}, input block {1}, ammo {2} (informational: depends on heap placement)" -f $c.frame_counter_0x5a7e1c, $(if (Read-InputBlock $s) { 'mapped' } else { 'null' }), $(if (Read-Ammo $s) { 'mapped' } else { 'null' }))
    if ((Read-Bytes $s 0x10 4) -ne $null) { $fails += "read of the null page (0x10) returned data; a failed read must be null" }
    if ((Read-I32 $s 0x10) -ne $null) { $fails += "Read-I32 of the null page returned a number, expected null (0 would mask a failed read)" }
    $mz = Read-Bytes $s ([int64]$s.Proc.MainModule.BaseAddress) 2
    if (-not $mz -or $mz[0] -ne 0x4d -or $mz[1] -ne 0x5a) { $fails += "could not read MZ at notepad's image base (ReadProcessMemory path broken)" }
    $f = Invoke-FireHold $s -HoldMs 200 -SampleMs 50 -PostSamples 1 -DryRun
    if (-not $f.dry_run) { $fails += "fire-hold dry_run flag not set" }
    if ($f.n_held_samples -lt 2) { $fails += "fire-hold took $($f.n_held_samples) samples, expected >= 2" }
    if ($f.os_key_seen -ne 0) { $fails += "fire-hold saw the key down at the OS in dry-run ($($f.os_key_seen)) - a key WAS sent or is physically held" }
    if ($f.stimulus_fired) { $fails += "fire-hold reported fired on notepad" }
    $t = Invoke-ThrottleHold $s -HoldMs 200 -SampleMs 50 -DryRun
    if ($t.stimulus_fired) { $fails += "throttle-hold reported fired on notepad" }
    $d = Invoke-SelfDestructMarker $s -WaitSeconds 1 -DryRun
    if ($d.stimulus_fired) { $fails += "self-destruct reported fired on notepad" }
    $k = Invoke-DebugKey $s -Letter M -Control -Name MONO_DEBUG_TOGGLE -DryRun
    if ($k.chord -ne 'Control+M') { $fails += "debug-key chord '$($k.chord)', expected Control+M" }
    if ($k.screenshot.error) { Write-Host ("  screenshot not available in this session: {0} (expected over RDP; the console has a desktop)" -f $k.screenshot.error) -ForegroundColor Yellow }
    elseif (-not (Test-Path $k.screenshot.file)) { $fails += "debug-key screenshot file missing" }
    $m = (Get-Content -Raw (Join-Path $s.Dir 'manifest.json')) | ConvertFrom-Json
    if (@($m.stimuli).Count -ne 4) { $fails += "manifest has $(@($m.stimuli).Count) stimuli entries, expected 4" }
    $jl = @(Get-Content (Join-Path $s.Dir 'stimuli.jsonl')).Count
    if ($jl -ne 4) { $fails += "stimuli.jsonl has $jl lines, expected 4" }
    $bom = [IO.File]::ReadAllBytes((Join-Path $s.Dir 'manifest.json'))[0..2]
    if ($bom[0] -eq 0xEF -and $bom[1] -eq 0xBB -and $bom[2] -eq 0xBF) { $fails += "manifest.json has a UTF-8 BOM (G-ENC)" }
    try { Invoke-AmmoPositiveControl $s | Out-Null; $fails += "positive control ran without -Write" } catch { Write-Host "  positive control refused without -Write: OK" }
    Close-Stim $s
    Write-Host ("manifest at {0}" -f $s.Dir)
} finally {
    Stop-Process -Id $np.Id -Force -ErrorAction SilentlyContinue
}
if ($fails.Count) { $fails | ForEach-Object { Write-Host ("FAIL: " + $_) -ForegroundColor Red }; exit 1 }
Write-Host "stimuli self-test: PASS (notepad pid $($np.Id); no keys were sent)" -ForegroundColor Green
exit 0
