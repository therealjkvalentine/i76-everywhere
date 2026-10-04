<#
  nglide-settings.ps1 - set / show / restore nGlide 2.10's per-user settings for a renderer test.

  nGlide keeps its settings in HKCU\Software\Zeus Software\nGlide2 as REG_SZ decimal numbers (its glide2x.dll reads
  each value into a 255-byte buffer and sscanf("%d")s it; found by disassembly of the 2.10 DLL, 2026-10-02, the
  configurator was never run). The same DLL then reads NGLIDE_<NAME> environment variables, which override the
  registry for that process. Value meanings below are STATIC findings (the configurator's combo-box fill order and
  the DLL's range checks / fallback defaults), not yet confirmed by a run:

    Backend     0 Automatic (default)   1 DirectX (Direct3D 9)   2 Vulkan
    Resolution  0 By app (default)      1 By desktop             2.. fixed sizes, ascending from 640x480
    Aspect      0 Entire screen (default)  1 Aspect correction (4:3)  2 Integer rendering  3 Integer scaling
    Refresh     0 By app (default)      1 By desktop             2.. 60 70 72 75 85 90 100 120 144 Hz
    Vsync       0 Off                   1 On (default)
    Gamma       0..10 = 0.5..1.5, 5 = 1.0 (default)
    Splash      0 Off                   1 On (default)

    .\nglide-settings.ps1 -Show                       # current registry values (or "key absent")
    .\nglide-settings.ps1 -Backend vulkan             # the test set: vsync off, resolution by desktop, aspect 4:3,
    .\nglide-settings.ps1 -Backend d3d9               #   refresh by app, splash off, back end as given
    .\nglide-settings.ps1 -Backend vulkan -Vsync on   # variants: -Vsync on|off, -Refresh app|desktop, -Aspect 4x3|fill
    .\nglide-settings.ps1 -Restore                    # put back what was there before the first set (removes the key
                                                      #   if it did not exist)
    .\nglide-settings.ps1 -Backend vulkan -EnvOnly    # write nothing; output the hashtable for proxy-run.ps1 -Env

  The state before the first set is saved to %LOCALAPPDATA%\i76-uncap-lab\nglide-settings-before.json; -Restore uses
  and deletes it. Every write is read back. Nothing here touches a game folder.
#>
param(
    [ValidateSet("", "vulkan", "d3d9", "auto")] [string]$Backend = "",
    [ValidateSet("off", "on")] [string]$Vsync = "off",
    [ValidateSet("app", "desktop")] [string]$Refresh = "app",
    [ValidateSet("4x3", "fill")] [string]$Aspect = "4x3",
    [ValidateSet("desktop", "app")] [string]$Resolution = "desktop",
    [switch]$EnvOnly,
    [switch]$Show,
    [switch]$Restore
)
$ErrorActionPreference = "Stop"
$Key = 'HKCU:\Software\Zeus Software\nGlide2'
$Names = "Backend", "Resolution", "Aspect", "Refresh", "Vsync", "Gamma", "Splash"
$SaveDir = Join-Path $env:LOCALAPPDATA "i76-uncap-lab"
$Save = Join-Path $SaveDir "nglide-settings-before.json"

function Read-State {
    if (-not (Test-Path $Key)) { return $null }
    $h = [ordered]@{}; $p = Get-ItemProperty -Path $Key
    foreach ($n in $Names) { if ($null -ne $p.$n) { $h[$n] = [string]$p.$n } }
    $h
}
function Show-State($s) { if ($null -eq $s) { "HKCU\Software\Zeus Software\nGlide2 : key absent (nGlide uses its defaults)" } else { "HKCU\Software\Zeus Software\nGlide2 : " + (($s.Keys | ForEach-Object { "$_=$($s[$_])" }) -join " ") } }

if ($Show -or (-not $Backend -and -not $Restore)) { Show-State (Read-State); return }

if ($Restore) {
    if (-not (Test-Path $Save)) { "nothing to restore (no $Save)"; Show-State (Read-State); return }
    $b = Get-Content $Save -Raw | ConvertFrom-Json
    if (-not $b.existed) {
        if (Test-Path $Key) { Remove-Item $Key -Recurse -Force }
        $parent = 'HKCU:\Software\Zeus Software'
        if ($b.parent_existed -eq $false -and (Test-Path $parent) -and -not (Get-ChildItem $parent) -and -not (Get-Item $parent).Property) { Remove-Item $parent -Force }
        if (Test-Path $Key) { throw "restore did not land: $Key still exists" }
    } else {
        foreach ($n in $Names) {
            $v = $b.values.$n
            if ($null -ne $v) { Set-ItemProperty -Path $Key -Name $n -Value ([string]$v) -Type String }
            else { Remove-ItemProperty -Path $Key -Name $n -ErrorAction SilentlyContinue }
        }
        $now = Read-State
        foreach ($n in $Names) { if ([string]$now[$n] -ne [string]$b.values.$n) { throw "restore did not land: $n" } }
    }
    Remove-Item $Save -Force
    "restored: " + (Show-State (Read-State))
    return
}

$want = [ordered]@{
    Backend    = @{ auto = "0"; d3d9 = "1"; vulkan = "2" }[$Backend]
    Resolution = @{ app = "0"; desktop = "1" }[$Resolution]
    Aspect     = @{ fill = "0"; "4x3" = "1" }[$Aspect]
    Refresh    = @{ app = "0"; desktop = "1" }[$Refresh]
    Vsync      = @{ off = "0"; on = "1" }[$Vsync]
    Splash     = "0"
}
if ($EnvOnly) {
    $e = @{}; foreach ($n in $want.Keys) { $e["NGLIDE_" + $n.ToUpper()] = $want[$n] }
    return $e
}
if (-not (Test-Path $Save)) {
    New-Item -ItemType Directory -Force $SaveDir | Out-Null
    $before = Read-State
    [ordered]@{ time = (Get-Date).ToString("s"); existed = ($null -ne $before); parent_existed = (Test-Path 'HKCU:\Software\Zeus Software'); values = $before } |
        ConvertTo-Json -Depth 3 | Set-Content $Save -Encoding ascii
}
if (-not (Test-Path $Key)) { New-Item -Path $Key -Force | Out-Null }
foreach ($n in $want.Keys) { Set-ItemProperty -Path $Key -Name $n -Value $want[$n] -Type String }
$now = Read-State
foreach ($n in $want.Keys) { if ($now[$n] -ne $want[$n]) { throw "registry write did not land: $n (wanted $($want[$n]), read $($now[$n]))" } }
"set: backend=$Backend resolution=$Resolution aspect=$Aspect refresh=$Refresh vsync=$Vsync splash=off"
Show-State $now
"undo: $($MyInvocation.MyCommand.Path) -Restore"
