# winet-portsplit.ps1 - port-split experiment for two lab copies on one PC (B4, 2026-10-03).
#   -Apply   back up both DLL\WINET.DLL to runs\mp\bak-winet, then patch:
#              A (game)     : destination port byte (file 0xC10) A5 -> A6  => typed addresses go to :21158, bind stays 21157
#              B (game-alt) : bind port byte        (file 0x8CB) A5 -> A6  => binds 21158, typed addresses go to :21157
#            each byte is read back after the write.
#   -Restore put the backups back and md5-compare against the stock md5 6edfea77.
# Lab copies only. Never the daily driver, the golden copy or game-dd-*.
param([switch]$Apply, [switch]$Restore)
$Lab = "C:\Users\james\i76-uncap-lab"
$Bak = "$Lab\autotest\runs\mp\bak-winet"
$stock = "6EDFEA775E3478FE3F1234E5AA54BCDC"
$plan = @(@{ Dir = "$Lab\game"; Off = 0xC10; Name = "A" }, @{ Dir = "$Lab\game-alt"; Off = 0x8CB; Name = "B" })
function Md5($p) { (Get-FileHash $p -Algorithm MD5).Hash }
if ($Apply) {
    New-Item -ItemType Directory -Force $Bak | Out-Null
    foreach ($p in $plan) {
        $f = "$($p.Dir)\DLL\WINET.DLL"
        if ((Md5 $f) -ne $stock) { "$($p.Name): WINET.DLL is not stock ($(Md5 $f)) - refusing"; exit 1 }
        $b = "$Bak\$($p.Name)-WINET.DLL"; if (-not (Test-Path $b)) { Copy-Item $f $b }
        $bytes = [IO.File]::ReadAllBytes($f)
        if ($bytes[$p.Off] -ne 0xA5) { "$($p.Name): byte at 0x$('{0:X}' -f $p.Off) is 0x$('{0:X2}' -f $bytes[$p.Off]), expected A5 - refusing"; exit 1 }
        $bytes[$p.Off] = 0xA6; [IO.File]::WriteAllBytes($f, $bytes)
        $rb = [IO.File]::ReadAllBytes($f)[$p.Off]
        "$($p.Name): $f 0x$('{0:X}' -f $p.Off) now 0x$('{0:X2}' -f $rb) md5 $((Md5 $f).Substring(0,8))"
    }
}
if ($Restore) {
    foreach ($p in $plan) {
        $f = "$($p.Dir)\DLL\WINET.DLL"; $b = "$Bak\$($p.Name)-WINET.DLL"
        if (Test-Path $b) { Copy-Item $b $f -Force }
        $m = Md5 $f; "$($p.Name): $f md5 $($m.Substring(0,8)) $(if ($m -eq $stock) { 'STOCK' } else { 'NOT STOCK' })"
    }
}
