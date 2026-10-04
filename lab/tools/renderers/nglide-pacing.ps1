# nglide-pacing.ps1 - how does nGlide (D3D9 back end) pace on game-alt? Four runs on t01, frame_stats 8 s each:
# vsync off / on, each uncapped and with the proxy's I76_FPS_CAP=179. No I76_GLIDE_REFRESH. Restores the copy.
param([string]$Backend = "d3d9")
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$alt = "C:\Users\james\i76-uncap-lab\game-alt"
$fs = "C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py"
& "$Here\switch-renderer.ps1" -Renderer nglide -Source "C:\Users\james\i76-uncap-lab\refs\renderers\nglide" 2>&1 | Select-Object -Last 1
try {
    $tests = @(
        @{ n = "uncapped-vsync-off"; v = "off"; e = @{} },
        @{ n = "cap179-vsync-off"; v = "off"; e = @{ I76_FPS_CAP = "179" } },
        @{ n = "uncapped-vsync-on"; v = "on"; e = @{} },
        @{ n = "cap179-vsync-on"; v = "on"; e = @{ I76_FPS_CAP = "179" } }
    )
    foreach ($t in $tests) {
        & "$Here\nglide-settings.ps1" -Backend $Backend -Vsync $t.v 2>&1 | Out-Null
        $o = Join-Path $env:TEMP ("ng-" + $t.n + ".txt")
        if (Test-Path $o) { Clear-Content $o }
        $run = [scriptblock]::Create("python '$fs' 8 '$($t.n)' 2>&1 | Out-File '$o' -Encoding ascii")
        $r = & "$Here\..\..\autotest\proxy-run.ps1" -GameDir $alt -Mission t01 -Hold 0 -Env $t.e -Run $run 2>&1 | Out-String
        $line = if ((Test-Path $o) -and (Get-Item $o).Length -gt 0) { ((Get-Content $o) -join " ") -replace " \| bins.*", "" } else { "no result: " + ((($r -split "`n") | Select-String "CRASH|exited|not in").Line -join " ") }
        "nglide-$Backend $line"
    }
} finally {
    & "$Here\nglide-settings.ps1" -Restore 2>&1 | Select-Object -Last 1
    & "$Here\switch-renderer.ps1" -Renderer dgvoodoo 2>&1 | Select-Object -Last 1
}
