<#
  PromoteLib.ps1 - shared helpers for future promote-N scripts (added 2026-10-10, docs/CLEANUP-PLAN-2026-10-10.md s.7.1).

    . (Join-Path $PSScriptRoot 'PromoteLib.ps1')

  The existing promote-1..16 scripts are records of what ran and keep their own inline copies; do not rewrite them.
  Nothing here writes to the daily driver or the golden copy: helpers only read those two folders and write into a
  stage directory. The single writer stays Promote-To-Driver.ps1.

    Get-Md5 <path>                                   lower-case md5 of a file
    Assert-BinaryMd5 -Path <file> -Want <8+ hex>     throw unless the file's md5 starts with the gated prefix
    Assert-DriverEqualsGolden -Rel <relative path>   throw unless driver and golden hold byte-identical copies
    Add-PresetLine -Preset <name.psd1> -AnchorKey <I76_X> -Line <text>[,...] -StageDir <dir> [-Expect @{K='v'}]
        stage <driver>\Interstate 76\presets\<name.psd1> with the line(s) inserted after the AnchorKey line (same
        indent, same newline style), read it back with Import-PowerShellDataFile and check every key of each
        inserted line plus -Expect; refuses if driver != golden for that preset or a key is already set.
        Returns the staged file's path.
#>

$script:PromoteDriver = (Join-Path $env:USERPROFILE 'Games\Interstate76-2026-10-03')
$script:PromoteGolden = (Join-Path $env:USERPROFILE 'Games\Interstate76-golden-2026-10-03')

function Get-Md5([Parameter(Mandatory = $true)][string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm MD5).Hash.ToLower()
}

function Assert-BinaryMd5 {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Want)
    if (-not (Test-Path -LiteralPath $Path)) { throw "REFUSED: missing $Path" }
    $have = Get-Md5 $Path
    if (-not $have.StartsWith($Want.ToLower())) { throw "REFUSED: $Path is $($have.Substring(0, 8)), not the gated $Want" }
    $have
}

function Assert-DriverEqualsGolden {
    param([Parameter(Mandatory = $true)][string]$Rel,
          [string]$Driver = $script:PromoteDriver, [string]$Golden = $script:PromoteGolden)
    $d = Join-Path $Driver $Rel; $g = Join-Path $Golden $Rel
    foreach ($p in $d, $g) { if (-not (Test-Path -LiteralPath $p)) { throw "REFUSED: missing $p" } }
    if ((Get-Md5 $d) -ne (Get-Md5 $g)) { throw "REFUSED: $Rel differs between driver and golden" }
    $d
}

function Add-PresetLine {
    param([Parameter(Mandatory = $true)][string]$Preset,
          [Parameter(Mandatory = $true)][string]$AnchorKey,
          [Parameter(Mandatory = $true)][string[]]$Line,
          [Parameter(Mandatory = $true)][string]$StageDir,
          [hashtable]$Expect = @{},
          [string]$Driver = $script:PromoteDriver, [string]$Golden = $script:PromoteGolden)
    $src = Assert-DriverEqualsGolden -Rel "Interstate 76\presets\$Preset" -Driver $Driver -Golden $Golden
    $t = [IO.File]::ReadAllText($src)
    $want = @{}
    foreach ($l in $Line) {
        $m = [regex]::Match($l, "^\s*(I76_\w+)\s*=\s*'([^']*)'")
        if (-not $m.Success) { throw "REFUSED: line is not KEY = 'value': $l" }
        $k = $m.Groups[1].Value
        if ($t -match "(?m)^\s*$k\s*=") { throw "REFUSED: $Preset already sets $k" }
        $want[$k] = $m.Groups[2].Value
    }
    foreach ($k in $Expect.Keys) { $want[$k] = $Expect[$k] }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $a = [regex]::Match($t, "(?m)^([ \t]*)$AnchorKey[ \t]*=[^\r\n]*")
    if (-not $a.Success) { throw "REFUSED: $Preset has no $AnchorKey line to anchor on" }
    $t = $t.Insert($a.Index + $a.Length, (($Line | ForEach-Object { $nl + $a.Groups[1].Value + $_.Trim() }) -join ''))
    New-Item -ItemType Directory -Force $StageDir | Out-Null
    $out = Join-Path $StageDir $Preset
    [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $e = (Import-PowerShellDataFile $out).Env
    foreach ($k in $want.Keys) {
        if ("$($e[$k])" -ne "$($want[$k])") { throw "REFUSED: staged $Preset reads $k = '$($e[$k])', want '$($want[$k])'" }
    }
    $out
}
