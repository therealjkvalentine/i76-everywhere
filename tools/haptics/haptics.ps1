<#
  haptics.ps1 - the one entry point for the I'76 haptics host (tools/haptics).

      tools\haptics\haptics.ps1 build                    # dotnet build (Release) of the host + tests
      tools\haptics\haptics.ps1 test                     # golden (FfbMixer.ps1) + C# tests + Python design tests
      tools\haptics\haptics.ps1 replay <file> --sinks wheel-file,pad-file,lfe-wav --out <dir>
      tools\haptics\haptics.ps1 motion <scenario|all|file|synthetic> [--targets flypt,native] [--send] [--repeat N] [--check]
                                                         # motion simulator output (motion\README.md): a synthetic scenario
                                                         # (braking accelerating turn crest jump impact dropout, or all) or a
                                                         # recording -> packet logs in out\motion; --send also sends UDP to
                                                         # the targets on 127.0.0.1, in real time
      tools\haptics\haptics.ps1 <any host command>       # passed straight to the host; `help` lists them

  Everything except an explicit --live run is offline: no game, no device is opened. See README.md.
#>
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfg = 'Release'
$hostProj = Join-Path $here 'src\Host\Host.csproj'
$testProj = Join-Path $here 'tests\Haptics.Tests\Haptics.Tests.csproj'
$hostExe = Join-Path $here "src\Host\bin\$cfg\net8.0\i76haptics.exe"
$testExe = Join-Path $here "tests\Haptics.Tests\bin\$cfg\net8.0\Haptics.Tests.exe"

function Build-All {
    & dotnet build $hostProj -c $cfg --nologo -v q | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "host build failed" }
    & dotnet build $testProj -c $cfg --nologo -v q | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "test build failed" }
}

$cmd = if ($args.Count -gt 0) { [string]$args[0] } else { 'help' }
$rest = @(); if ($args.Count -gt 1) { $rest = $args[1..($args.Count - 1)] }

switch ($cmd) {
    'build' { Build-All; exit 0 }
    'test' {
        Build-All
        $real = Join-Path (Resolve-Path (Join-Path $here '..\..')) 'tools\ffb'
        # drive2.csv / drive3.csv are gitignored captures: a worktree has none. I76_REAL_DRIVES points at a folder that does
        # (e.g. the main checkout's tools\ffb); without them the two real-drive golden checks are simply not generated.
        $drives = if ($env:I76_REAL_DRIVES) { $env:I76_REAL_DRIVES } else { $real }
        Write-Host "--- golden: running tools/ffb/FfbMixer.ps1 over the synthetic drives ---" -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'tests\golden\make-golden.ps1') -RealDrives $drives
        if ($LASTEXITCODE -ne 0) { throw "make-golden failed" }
        Write-Host "--- probe WAVs: tools/ffb/ffb-lfe-probe.ps1 renders the reference shaker signal (files only, nothing plays) ---" -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $real 'ffb-lfe-probe.ps1') -OutDir (Join-Path $here 'tests\out\probe') | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "ffb-lfe-probe failed" }
        Write-Host "--- C# tests ---" -ForegroundColor Cyan
        & $testExe @rest
        $csharp = $LASTEXITCODE
        Write-Host "--- Python design tests ---" -ForegroundColor Cyan
        & python (Join-Path $here 'design\test_design.py')
        $py = $LASTEXITCODE
        Write-Host "--- Python motion tests (validator, scenarios, host end to end; files only, no UDP) ---" -ForegroundColor Cyan
        & python (Join-Path $here 'motion\test_motion.py')
        if ($LASTEXITCODE -ne 0) { $py = $LASTEXITCODE }
        Write-Host ("C# tests exit {0}, Python tests exit {1}" -f $csharp, $py)
        if ($csharp -ne 0 -or $py -ne 0) { exit 1 }
        exit 0
    }
    'motion' {
        # haptics.ps1 motion <scenario|all|file|synthetic> [host motion options] [--check]
        if (-not (Test-Path $hostExe)) { Build-All }
        $scen = @('braking', 'accelerating', 'turn', 'crest', 'jump', 'impact', 'dropout')
        $src = if ($rest.Count -gt 0) { [string]$rest[0] } else { 'braking' }
        $opts = @(); if ($rest.Count -gt 1) { $opts = @($rest[1..($rest.Count - 1)]) }
        $check = $opts -contains '--check'
        $opts = @($opts | Where-Object { $_ -ne '--check' })
        $names = if ($src -eq 'all') { $scen } elseif ($scen -contains $src) { @($src) } else { @() }
        $rc = 0
        if ($names.Count -gt 0) {
            & python (Join-Path $here 'motion\make_synthetic.py') @names
            if ($LASTEXITCODE -ne 0) { throw "make_synthetic failed" }
            foreach ($n in $names) {
                $rec = Join-Path $here "replays\synth-$n.i76rec"
                & $hostExe motion $rec @opts
                if ($LASTEXITCODE -ne 0) { $rc = $LASTEXITCODE; continue }
                if ($check) {
                    $outDir = Join-Path $here 'out\motion'
                    $i = [array]::IndexOf($opts, '--out'); if ($i -ge 0 -and $i + 1 -lt $opts.Count) { $outDir = $opts[$i + 1] }
                    $log = Join-Path $outDir "synth-$n.native.i76motion.i76rec"
                    if (Test-Path $log) {
                        & python (Join-Path $here 'motion\i76motion.py') --check $log --expect (Join-Path $here "replays\synth-$n.expect.json") --quiet
                        if ($LASTEXITCODE -ne 0) { $rc = 1 }
                    } else { Write-Host "  --check: no native i76motion log ($log); include the 'native' target" -ForegroundColor Yellow }
                }
            }
        } else {
            & $hostExe motion $src @opts
            $rc = $LASTEXITCODE
        }
        exit $rc
    }
    default {
        if (-not (Test-Path $hostExe)) { Build-All }
        & $hostExe @args
        exit $LASTEXITCODE
    }
}
