<#
  gamedir.ps1 - one guard for every harness script that takes -GameDir. Dot-source it.

      . "$PSScriptRoot\lib\gamedir.ps1"
      $G = Resolve-LabGameDir $GameDir          # "" = the sandbox, <lab>\game
      $I76GameDirInUse = $G                     # BEFORE dot-sourcing focuslib / memlib / maplib

  Resolve-LabGameDir returns the full path of a game folder (one that holds i76.exe) or throws. It accepts only a
  folder INSIDE the lab (C:\Users\james\i76-uncap-lab): the sandbox `game`, `game-alt`, and twins such as
  `game-dd-20261003\Interstate 76` (the lab ignores game-*/). It refuses, by name, the playable installs
  (AGENTS.md "NEVER TEST ON THE PLAYABLE INSTALL"), anything else outside the lab, and a path that reaches the lab
  through a junction or symlink (a link inside the lab could point at the playable folder).

  $I76GameDirInUse: Get-GamePid (focuslib), Mem-Open (memlib) and Init-CursorMap (maplib) read this variable from
  the caller's scope. When it is set and several lab game processes exist they take the one whose exe is in that
  folder; when it is not set they behave as before (first process whose path contains 'i76-uncap-lab').
#>
$script:LabRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path.TrimEnd('\')

function Get-LabRoot { return $script:LabRoot }

function Resolve-LabGameDir {
    param([string]$GameDir = "", [switch]$AllowMissingExe)
    if (-not $GameDir) { $GameDir = Join-Path $script:LabRoot "game" }
    $playable = '(?i)\\Downloads\\|i76-everywhere-portable|\\Games\\Interstate76|Interstate76-golden'
    if ($GameDir -match $playable) { throw "refusing -GameDir '$GameDir': this is a PLAYABLE install (or its golden copy). The harness only drives copies inside $($script:LabRoot)." }
    if (-not (Test-Path -LiteralPath $GameDir -PathType Container)) { throw "refusing -GameDir '$GameDir': no such folder" }
    $full = (Resolve-Path -LiteralPath $GameDir).Path.TrimEnd('\')
    # the playable installs, named: the July portable in Downloads and the new daily driver / golden copy in Games
    if ($full -match $playable) {
        throw "refusing -GameDir '$full': this is a PLAYABLE install (or its golden copy). The harness only drives copies inside $($script:LabRoot)."
    }
    if (-not ($full + '\').StartsWith($script:LabRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $full -ieq $script:LabRoot) {
        throw "refusing -GameDir '$full': not a game folder inside $($script:LabRoot)"
    }
    # no junction / symlink between the lab root and the folder
    $p = $full
    while ($p -and $p.Length -gt $script:LabRoot.Length) {
        if ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "refusing -GameDir '$full': '$p' is a junction or symlink" }
        $p = Split-Path -Parent $p
    }
    if (-not $AllowMissingExe -and -not (Test-Path -LiteralPath (Join-Path $full "i76.exe"))) { throw "refusing -GameDir '$full': no i76.exe in it (for a daily-driver twin pass its 'Interstate 76' subfolder)" }
    return $full
}

# A launcher (.bat / .ps1) is accepted on the same terms: the file must be inside the lab.
function Resolve-LabLauncher {
    param([Parameter(Mandatory)] [string]$Launcher)
    if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) { throw "refusing -Launcher '$Launcher': no such file" }
    $full = (Resolve-Path -LiteralPath $Launcher).Path
    if ($full -notmatch '(?i)\.(bat|cmd|ps1)$') { throw "refusing -Launcher '$full': a .bat, .cmd or .ps1 is expected" }
    $dir = Split-Path -Parent $full
    if ($dir -ine $script:LabRoot) { [void](Resolve-LabGameDir $dir -AllowMissingExe) }     # same refusals, applied to its folder
    return $full
}

# True when the process' exe is in $Dir (or below it)
function Test-ProcInDir($Proc, [string]$Dir) {
    if (-not $Proc -or -not $Proc.Path -or -not $Dir) { return $false }
    return ($Proc.Path).StartsWith($Dir.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}
