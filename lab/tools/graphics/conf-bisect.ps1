# conf-bisect.ps1 - find the line(s) that make dgVoodoo reject game\dgVoodoo.conf.
# Trial: install a candidate conf, hide the global %APPDATA%\dgVoodoo\dgVoodoo.conf, start i76.exe -glide, wait for
# the window, read its client size, kill. A rejected conf falls back to defaults and the shell window comes up at
# raw 640x480; an accepted one gives the borderless full-screen window. ~12 s per trial. Restores everything.
param([string]$Source = "C:\Users\james\i76-uncap-lab\game\dgVoodoo.conf", [switch]$Each)
$ErrorActionPreference = "Continue"
$G = "C:\Users\james\i76-uncap-lab\game"; $conf = "$G\dgVoodoo.conf"; $bak = "$conf.pre-bisect"
$glob = "$env:APPDATA\dgVoodoo\dgVoodoo.conf"; $globHidden = "$env:APPDATA\dgVoodoo\dgVoodoo.conf.hidden-by-bisect"
Add-Type -Name B -Namespace CB -MemberDefinition '[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r); [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }'
if (Get-Process i76* -ErrorAction SilentlyContinue) { "game running"; exit 1 }
$orig = Get-Content $Source
Copy-Item $conf $bak -Force
if (Test-Path $glob) { Rename-Item $glob (Split-Path $globHidden -Leaf) }
Set-Content "$G\.console-test.lock" "conf-bisect $PID"
function Trial([string[]]$lines, [string]$what) {
    [IO.File]::WriteAllLines($conf, $lines, [Text.Encoding]::ASCII)
    $p = Start-Process "$G\i76.exe" -ArgumentList "-glide" -WorkingDirectory $G -PassThru
    $w = 0; $h = 0
    for ($i = 0; $i -lt 14; $i++) { Start-Sleep -Seconds 1; $p.Refresh(); if ($p.HasExited) { break }
        if ($p.MainWindowHandle -ne [IntPtr]::Zero) { $r = New-Object CB.B+RECT; [void][CB.B]::GetClientRect($p.MainWindowHandle, [ref]$r); $w = $r.R; $h = $r.B; if ($i -ge 8) { break } } }
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 2
    $ok = $w -gt 1000
    Write-Host ("  trial {0,-46} {1} lines -> client {2}x{3} -> {4}" -f $what, $lines.Count, $w, $h, $(if ($ok) { "ACCEPTED" } else { "rejected" }))
    return $ok
}
try {
    $isKey = { param($l) $l -match '^\s*[A-Za-z0-9_]+\s*=' }
    $keep = { param($l) ($l -match '^\s*\[') -or ($l -match '^\s*Version\s*=') }
    if ($Each) {   # every key line alone (with Version and all section headers): lists each line dgVoodoo rejects
        $noc0 = @($orig | Where-Object { (& $isKey $_) -or (& $keep $_) })
        $bad = @()
        $base = @($noc0 | Where-Object { & $keep $_ })
        [void](Trial $base "BASELINE: Version + section headers only")
        for ($i = 0; $i -lt $noc0.Count; $i++) {
            if (& $keep $noc0[$i]) { continue }
            # sentinel: ScalingMode = stretched_ar alone is known to give the full-screen window, so a candidate that
            # still comes up 640x480 WITH the sentinel present was rejected as a whole (or legitimately resizes: check by hand)
            $cand = @(0..($noc0.Count - 1) | Where-Object { (& $keep $noc0[$_]) -or $_ -eq $i -or ($noc0[$_] -match '^ScalingMode\s*=') } | ForEach-Object { $noc0[$_] })
            if (-not (Trial $cand ("only: " + $noc0[$i].Trim()))) { $bad += $noc0[$i] }
        }
        "REJECTED LINES:"; $bad | ForEach-Object { "   $_" }
        $good = @($noc0 | Where-Object { $bad -notcontains $_ })
        if (Trial $good "all keys minus the rejected ones") { "CONFIRMED: the conf without those lines is accepted" } else { "still rejected: an interaction, not single lines" }
        return
    }
    if (Trial $orig "original") { "the original is ACCEPTED when the global conf is hidden"; return }
    $noc = @($orig | Where-Object { (& $isKey $_) -or (& $keep $_) })
    if (Trial $noc "comments and blanks stripped") { "CULPRIT: a comment / non-key line (non-ASCII or malformed)"; $orig | Where-Object { -not ((& $isKey $_) -or (& $keep $_)) -and $_.Trim() -and $_ -notmatch '^\s*;' } | ForEach-Object { "   non-comment non-key line: '$_'" }; return }
    # single-culprit bisection over key lines (headers and Version always kept)
    $idx = @(0..($noc.Count - 1) | Where-Object { -not (& $keep $noc[$_]) })
    $suspect = $idx
    while ($suspect.Count -gt 1) {
        $half = $suspect[0..([int]($suspect.Count / 2) - 1)]
        $cand = @(0..($noc.Count - 1) | Where-Object { $half -notcontains $_ } | ForEach-Object { $noc[$_] })
        if (Trial $cand ("without {0} lines ({1}..)" -f $half.Count, $noc[$half[0]].Trim().Split('=')[0].Trim())) { $suspect = $half }
        else { $suspect = @($suspect | Where-Object { $half -notcontains $_ }) }
    }
    "CULPRIT candidate: line '$($noc[$suspect[0]])'"
    $fixed = @(0..($noc.Count - 1) | Where-Object { $_ -ne $suspect[0] } | ForEach-Object { $noc[$_] })
    if (Trial $fixed "all keys except the culprit") { "CONFIRMED: removing that one line makes the conf accepted" } else { "more than one culprit - the conf without it is still rejected" }
} finally {
    Get-Process i76* -ErrorAction SilentlyContinue | Stop-Process -Force
    Copy-Item $bak $conf -Force; Remove-Item $bak
    if (Test-Path $globHidden) { Rename-Item $globHidden "dgVoodoo.conf" }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue
    "restored (conf md5 $((Get-FileHash $conf -Algorithm MD5).Hash.Substring(0,8)), global present $(Test-Path $glob))"
}
