<#
  soak-phases.ps1 - the in-mission half of preset-soak.ps1 (run from proxy-run's -Run once the player exists).
  One full-desktop screenshot, cockpit idle, hood view (F6), back to cockpit (F1), binoculars (B) and off,
  the four pilot glances, then cockpit with throttle held (Grey arrows, sent as EXTENDED scan codes). Every phase is
  measured by lib\phase_stats.py (frame times + peak terrain vertices + camera mode); a phase that sees the game die
  ends the sequence, so the last line names the view it died in.
  Keys are raw VKs on purpose: inputlib's $VK table has no F6 ($VK.F6 is $null and Send-Key sends VK 0), which is
  why farclip-soak.ps1's 2026-10-02 "hood (F6)" column never left the cockpit.
#>
param([Parameter(Mandatory)] [string]$Out, [string]$Shot = "", [int]$Cockpit = 20, [int]$View = 5, [int]$Glance = 2)
. (Join-Path $PSScriptRoot "lib\inputlib.ps1")
. (Join-Path $PSScriptRoot "lib\focuslib.ps1")
$ps = Join-Path $PSScriptRoot "lib\phase_stats.py"
$g = Get-GamePid; $gpid = $g.Id
function Phase([double]$sec, [string]$label) {
    $line = (& python $ps $gpid $sec $label 2>&1 | Out-String).Trim()
    Add-Content $Out $line; Write-Host "  $line"
    return ($line -notmatch "DIED")
}
function Fg { try { $g.Refresh(); [void](Force-Foreground $g.MainWindowHandle) } catch {} }
function ExtKey([byte]$vk, [bool]$down) {
    $scan = [Inp]::MapVirtualKey($vk, 0)
    $f = 0x8 -bor 0x1; if (-not $down) { $f = $f -bor 0x2 }
    [Inp]::keybd_event($vk, $scan, $f, [IntPtr]::Zero)
}
$half = [int]($Cockpit / 2)
# views first, from the mission's start position (it faces down the route: the longest sight line the mission sets up);
# driving last, so the car is not nose-into a wall when the binoculars go up
$ok = $true
if ($Shot) {
    Fg; Start-Sleep -Milliseconds 800
    Add-Type -AssemblyName System.Drawing
    $b = New-Object Drawing.Bitmap 3440, 1440; $gr = [Drawing.Graphics]::FromImage($b); $gr.CopyFromScreen(0, 0, 0, 0, $b.Size)
    $b.Save($Shot); $s = New-Object Drawing.Bitmap $b, 1147, 480; $s.Save(($Shot -replace "\.png$", "-view.png")); $gr.Dispose(); $b.Dispose(); $s.Dispose()
}
if ($ok) { Fg; $ok = Phase ($Cockpit - $half) "cockpit" }
if ($ok) { Fg; Send-Key ([byte]0x75); Start-Sleep -Milliseconds 500; $ok = Phase $View "hood"; Fg; Send-Key ([byte]0x70); Start-Sleep -Milliseconds 500 }   # F6 hood, F1 back
if ($ok) { Fg; Send-Key ([byte]0x42); Start-Sleep -Milliseconds 500; $ok = Phase $View "binoc"; Fg; Send-Key ([byte]0x42); Start-Sleep -Milliseconds 500 }  # B on / off
foreach ($gl in @(@{ n = "glance-left"; vk = 0x25 }, @{ n = "glance-right"; vk = 0x27 }, @{ n = "glance-up"; vk = 0x26 }, @{ n = "glance-down"; vk = 0x28 })) {
    if (-not $ok) { break }
    Fg; ExtKey ([byte]$gl.vk) $true
    $ok = Phase $Glance $gl.n
    if ($ok -and $Shot -and $gl.n -eq 'glance-left') { Add-Type -AssemblyName System.Drawing; $b = New-Object Drawing.Bitmap 3440, 1440; $gr = [Drawing.Graphics]::FromImage($b); $gr.CopyFromScreen(0, 0, 0, 0, $b.Size); $s2 = New-Object Drawing.Bitmap $b, 1147, 480; $s2.Save(($Shot -replace '\.png$', '-glance-left.png')); $gr.Dispose(); $b.Dispose(); $s2.Dispose() }   # proves the glance key landed
    ExtKey ([byte]$gl.vk) $false
}
if ($ok) { Fg; Key-Down $VK.W; $ok = Phase $half "cockpit-drive"; Key-Up $VK.W }
