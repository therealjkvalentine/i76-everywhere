# ipx-setup.ps1 - put IPXWrapper 0.7.2 into the two lab copies for the IPX two-instance test (B4, 2026-10-03). NOT RUN YET.
#   -Install  copies ipxwrapper.dll, wsock32.dll, mswsock.dll (refs\ipxwrapper\bin\ipxwrapper-0.7.2) into game\ and game-alt\.
#             game-alt gets a copy of ipxwrapper.dll with two bytes changed so the two processes do not share IPXWrapper state:
#               "ipxwrapper_socket_%hu" -> "ipxwrapperBsocket_%hu"  (named mutex that makes IPX socket 0x52A3 exclusive per session)
#               "Software\IPXWrapper"   -> "Software\IPXWrappeB"    (HKCU key holding the wildcard interface's node number)
#             so B binds the same IPX socket as A and gets its own random node. Each byte is read back.
#   -Remove   deletes exactly those three files from both folders (refuses if a file there is not one we put in).
# Notes: IPXWrapper writes HKCU\Software\IPXWrapper (A) and HKCU\Software\IPXWrappeB (B) on first use (node numbers).
#        Lab copies only. Do not run while another agent is testing in game\ (check CONSOLE-LOCK.md first).
param([switch]$Install, [switch]$Remove)
$Lab = "C:\Users\james\i76-uncap-lab"
$Src = "$Lab\refs\ipxwrapper\bin\ipxwrapper-0.7.2"
$files = "ipxwrapper.dll", "wsock32.dll", "mswsock.dll"
$patch = @(@{ Off = 0x1BEAC; From = [byte][char]'_'; To = [byte][char]'B' }, @{ Off = 0x1CB7C; From = [byte][char]'r'; To = [byte][char]'B' })
function Md5($p) { (Get-FileHash $p -Algorithm MD5).Hash }
$stockB = "$env:TEMP\ipxwrapper-instB.dll"
if ($Install) {
    $bytes = [IO.File]::ReadAllBytes("$Src\ipxwrapper.dll")
    foreach ($p in $patch) { if ($bytes[$p.Off] -ne $p.From) { "byte at 0x$('{0:X}' -f $p.Off) is 0x$('{0:X2}' -f $bytes[$p.Off]), expected 0x$('{0:X2}' -f $p.From) - refusing"; exit 1 }; $bytes[$p.Off] = $p.To }
    [IO.File]::WriteAllBytes($stockB, $bytes)
    foreach ($d in "game", "game-alt") {
        foreach ($f in $files) { if (Test-Path "$Lab\$d\$f") { "$d\$f already exists - refusing (nothing copied)"; exit 1 } }
    }
    foreach ($d in "game", "game-alt") {
        foreach ($f in $files) { Copy-Item "$Src\$f" "$Lab\$d\$f" }
        if ($d -eq "game-alt") { Copy-Item $stockB "$Lab\$d\ipxwrapper.dll" -Force }
        $rb = [IO.File]::ReadAllBytes("$Lab\$d\ipxwrapper.dll")
        "$d ipxwrapper.dll md5 $((Md5 "$Lab\$d\ipxwrapper.dll").Substring(0,8)) mutex '$([Text.Encoding]::ASCII.GetString($rb, 0x1BEA2, 21))' key '$([Text.Encoding]::ASCII.GetString($rb, 0x1CB6A, 19))'"
        if (-not (Test-Path "$Lab\$d\ipxwrapper.ini")) { Set-Content "$Lab\$d\ipxwrapper.ini" "; B4 IPX test`r`nlogging = debug" -Encoding ascii; "$d ipxwrapper.ini (logging = debug)" }
    }
}
if ($Remove) {
    $logs = "$Lab\autotest\runs\mp\ipx"; New-Item -ItemType Directory -Force $logs | Out-Null
    foreach ($d in "game", "game-alt") {
        if (Test-Path "$Lab\$d\ipxwrapper.log") { Move-Item "$Lab\$d\ipxwrapper.log" "$logs\$d-ipxwrapper-$(Get-Date -Format HHmmss).log"; "moved $d\ipxwrapper.log to $logs" }
        if ((Test-Path "$Lab\$d\ipxwrapper.ini") -and ((Get-Content "$Lab\$d\ipxwrapper.ini" -TotalCount 1) -eq "; B4 IPX test")) { Remove-Item "$Lab\$d\ipxwrapper.ini"; "removed $d\ipxwrapper.ini" }
    }
}
if ($Remove) {
    $ok = @((Md5 "$Src\ipxwrapper.dll"), (Md5 "$Src\wsock32.dll"), (Md5 "$Src\mswsock.dll"))
    if (Test-Path $stockB) { $ok += Md5 $stockB }
    foreach ($d in "game", "game-alt") { foreach ($f in $files) {
        $p = "$Lab\$d\$f"; if (-not (Test-Path $p)) { continue }
        if ($ok -contains (Md5 $p)) { Remove-Item $p; "removed $d\$f" } else { "$d\$f is not an IPXWrapper file we installed - left in place" }
    } }
}
