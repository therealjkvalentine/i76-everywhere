<#
  i76e-extras.ps1 - the Patch Kit's OPTIONAL extras (INSTALL-EXTRAS.bat runs it; content-installer lane 2026-10-25,
  docs/records/CONTENT-INSTALLER-2026-10-25.md). Nothing here is needed to play; every option says what it enables first.

    1  community maps   the 10 maps of docs/CONTENT-FEASIBILITY-2026-10-25.md s.3 (5 Gold arenas into ADDON\, 5 Nitro arenas into
                        a Nitro Pack folder): downloaded from the sites that host them (Local Ditch, Lightfoot's Stolen Maps on
                        interstate76.com - linked, not rehosted), sha256-checked, the 1997 Gold files converted to the layout Gold
                        reads (the 13-byte horizon field the 1998 editor adds; tools/content-archive/arena-pack.py, ported here),
                        every output checked against the bytes the lab tested, credits shown and written to COMMUNITY-MAPS.txt
    2  opentrack        head look: opentrack 2026.1.0 portable from its GitHub release (sha256-pinned; unpacked with 7-Zip's
                        7zr.exe, also from its official GitHub release) into _tools\opentrack, plus the head-look layer in _ahk\
    3  AutoHotkey       already in the kit (_i76e\AutoHotkey); explained here, nothing to download
    4  Python           Python 3.12 (python.org's embeddable package, sha256-pinned) into _tools\python, for DEBUG.bat / TRAINER.bat
    5  German voices    from YOUR German retail Interstate '76 (CD 1 or its install folder): the German voice lines, unpacked into
                        voices-de\; PLAY.bat --voices de plays them (the proxy's I76_VOICES), PLAY.bat alone stays English
    6  extra music      PRIVATE: a folder of your own .mp3 / .wav shuffled in with the game's tracks (the proxy's I76_MUSIC_EXTRA);
                        nothing is downloaded or copied - the launcher reads your folder where it is

    i76e-extras.ps1                         the menu (asks about each option)
    i76e-extras.ps1 -Maps [-NitroDir <Nitro Pack folder>] [-Offline <folder with the zips>] [-Yes]
    i76e-extras.ps1 -OpenTrack | -Python [-Yes]
    i76e-extras.ps1 -GermanVoices <German retail folder or CD> [-Default]
    i76e-extras.ps1 -MusicExtra <folder> [-Every 3] | -MusicExtra off
    i76e-extras.ps1 -List                   what is installed;    -Uninstall   remove everything this script installed
  -GameDir <folder> (default: the folder above _i76e) may be a Gold folder (i76.exe) or a Nitro Pack folder (nitro.exe); maps go to
  whichever game it is (and -NitroDir). Writes only inside the game folder(s); originals of replaced files are kept as
  <file>.pre-i76e-extras; every file it writes is listed in _i76e\extras-installed.txt (what -Uninstall removes).
#>
param(
    [string]$GameDir = '',
    [switch]$Maps, [string]$NitroDir = '', [string]$Offline = '', [string[]]$Only = @(),
    [switch]$OpenTrack, [switch]$Python,
    [string]$GermanVoices = '', [switch]$Default,
    [string]$MusicExtra = '', [int]$Every = 3,
    [switch]$List, [switch]$Uninstall, [switch]$Yes, [switch]$KeepDownloads
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'      # PS 5.1's progress bar makes Invoke-WebRequest ~10x slower
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$here = $PSScriptRoot
$Only = @($Only | ForEach-Object { $_ -split ',' } | Where-Object { $_ })   # -File hands '-Only a,b' over as one string
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Fail([string]$m) { Write-Host "i76e-extras: $m" -ForegroundColor Red; exit 1 }
function Sha([byte[]]$b) { $h = [Security.Cryptography.SHA256]::Create(); try { return ([BitConverter]::ToString($h.ComputeHash($b)) -replace '-', '').ToLower() } finally { $h.Dispose() } }
function ShaFile([string]$p) { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() }
function Ask([string]$q) { if ($Yes) { return $true }; $a = Read-Host "$q [y/N]"; return ($a -match '^(y|yes|j|ja)$') }

# ---- where ---------------------------------------------------------------------------------------------------------
if (-not $GameDir) { $GameDir = Split-Path -Parent $here }
$GameDir = (Resolve-Path -LiteralPath $GameDir).Path
function Game-Kind([string]$d) { if (Test-Path -LiteralPath (Join-Path $d 'nitro.exe')) { 'nitro' } elseif (Test-Path -LiteralPath (Join-Path $d 'i76.exe')) { 'gold' } else { '' } }
$kind = Game-Kind $GameDir
if (-not $kind) { Fail "no i76.exe or nitro.exe in $GameDir - pass -GameDir <your Interstate '76 folder>" }
$state = Join-Path $GameDir '_i76e'; New-Item -ItemType Directory -Force $state | Out-Null
$ledger = Join-Path $state 'extras-installed.txt'
$envFile = Join-Path $state 'extras.env'
$dlDir = Join-Path $state 'downloads'
$manifest = Get-Content -LiteralPath (Join-Path $here 'extras.json') -Raw | ConvertFrom-Json
$repo = Join-Path $here 'repo'                 # the kit's copy of the repo pieces (absent when run from the repo itself)
if (-not (Test-Path -LiteralPath $repo)) { $repo = Split-Path -Parent (Split-Path -Parent $here) }
foreach ($g in @(Get-Process i76, nitro -ErrorAction SilentlyContinue)) {
    if ($g.Path -and ($g.Path.StartsWith($GameDir + '\', [StringComparison]::OrdinalIgnoreCase) -or ($NitroDir -and $g.Path.StartsWith($NitroDir + '\', [StringComparison]::OrdinalIgnoreCase)))) { Fail "the game is running from this folder - close it first" }
}

# ---- the ledger: every file this script wrote, so -Uninstall can take exactly that back ---------------------------------
function Ledger-Add([string]$path, [string]$sha, [string]$backup) { Add-Content -LiteralPath $ledger -Value "$path|$sha|$backup" -Encoding UTF8 }
function Ledger-Rows { if (Test-Path -LiteralPath $ledger) { @(Get-Content -LiteralPath $ledger -Encoding UTF8 | Where-Object { $_ -match '\|' } | ForEach-Object { $p = $_ -split '\|'; [pscustomobject]@{ Path = $p[0]; Sha = $p[1]; Backup = $p[2] } }) } else { @() } }
function Write-Owned([string]$dest, [byte[]]$bytes) {
    $sha = Sha $bytes
    New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
    $backup = ''
    if (Test-Path -LiteralPath $dest) {
        if ((ShaFile $dest) -eq $sha) { if (-not (Ledger-Rows | Where-Object { $_.Path -ieq $dest })) { Ledger-Add $dest $sha '' }; return 'same' }
        $backup = "$dest.pre-i76e-extras"
        if (-not (Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $dest -Destination $backup }
    }
    [IO.File]::WriteAllBytes($dest, $bytes)
    if ((ShaFile $dest) -ne $sha) { Fail "write did not read back: $dest" }
    Ledger-Add $dest $sha $backup
    return $(if ($backup) { 'replaced (original kept)' } else { 'new' })
}
function Env-Set([string]$key, [string]$value) {
    $rows = @(); if (Test-Path -LiteralPath $envFile) { $rows = @(Get-Content -LiteralPath $envFile | Where-Object { $_ -notmatch "^$([regex]::Escape($key))=" }) }
    if ($value -ne '') { $rows += "$key=$value" }
    if ($rows.Count) { Set-Content -LiteralPath $envFile -Value $rows -Encoding ascii } else { Remove-Item -LiteralPath $envFile -Force -ErrorAction SilentlyContinue }
}

# ---- downloads: the original site, size + sha256 pinned; -Offline looks for the same file (by name and hash) first -------
function Get-Pinned([string]$url, [string]$sha, [long]$size, [string]$what) {
    $name = [IO.Path]::GetFileName(([uri]$url).AbsolutePath)
    if ($Offline) {
        $hit = Get-ChildItem -LiteralPath $Offline -Recurse -File -Filter $name -ErrorAction SilentlyContinue | Where-Object { $_.Length -eq $size -and (ShaFile $_.FullName) -eq $sha } | Select-Object -First 1
        if ($hit) { Say "  ${what}: $name from $($hit.FullName) (sha256 ok)" 'DarkGray'; return $hit.FullName }
    }
    New-Item -ItemType Directory -Force $dlDir | Out-Null
    $out = Join-Path $dlDir $name
    if ((Test-Path -LiteralPath $out) -and (Get-Item -LiteralPath $out).Length -eq $size -and (ShaFile $out) -eq $sha) { Say "  ${what}: $name already downloaded (sha256 ok)" 'DarkGray'; return $out }
    Say "  ${what}: downloading $url ($([math]::Round($size / 1MB, 2)) MB)"
    try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out -UserAgent 'i76-everywhere-patch-kit' } catch { Say "  ${what}: download failed: $($_.Exception.Message)" 'Yellow'; return $null }
    $got = ShaFile $out
    if ($got -ne $sha) { Remove-Item -LiteralPath $out -Force; Say "  ${what}: sha256 $got is not the pinned $sha - NOT used (the file on the server changed; tell the kit's maintainer)" 'Yellow'; return $null }
    Say "  ${what}: sha256 ok" 'DarkGray'
    return $out
}

# ---- zip members, including one nested level ("miss16.zip/repo.cbt") ---------------------------------------------------
function Read-Member([string]$zipPath, [string]$member) {
    $parts = $member -split '/'
    $fs = [IO.File]::OpenRead($zipPath)
    try {
        $z = New-Object IO.Compression.ZipArchive($fs, [IO.Compression.ZipArchiveMode]::Read)
        $want = $member.Replace('\', '/')
        $e = $z.Entries | Where-Object { $_.FullName.Replace('\', '/') -ieq $want } | Select-Object -First 1
        if (-not $e -and $parts.Count -ge 2) {      # nested zip
            $inner = $z.Entries | Where-Object { $_.FullName.Replace('\', '/') -ieq $parts[0] } | Select-Object -First 1
            if ($inner) {
                $ms = New-Object IO.MemoryStream; $s = $inner.Open(); $s.CopyTo($ms); $s.Dispose(); $ms.Position = 0
                $z2 = New-Object IO.Compression.ZipArchive($ms, [IO.Compression.ZipArchiveMode]::Read)
                $rest = ($parts[1..($parts.Count - 1)] -join '/')
                $e = $z2.Entries | Where-Object { $_.FullName.Replace('\', '/') -ieq $rest } | Select-Object -First 1
            }
        }
        if (-not $e) { return $null }
        $ms2 = New-Object IO.MemoryStream; $s2 = $e.Open(); $s2.CopyTo($ms2); $s2.Dispose()
        return , $ms2.ToArray()
    } finally { $fs.Dispose() }
}

# ---- the 1997 -> Gold layout conversion (arena-pack.py's `convert`, byte for byte) ---------------------------------------
# A BWD2 file is 'BWD2', u32 header size, then chunks {tag[4], u32 size incl. the 8-byte header, body}; WDEF holds its own
# chunk list (WREV, WRLD, ...). The 1997 I76EDIT layout (WREV 8) has a 318-byte WRLD without the 13-byte horizon .hzd name at
# body +0x86 that Gold / Nitro (WREV 9, 331 bytes) read at fixed offsets; insert it (the stock miss8 horizon of the same
# palette), set WREV 9, grow WRLD and WDEF by 13. Every other byte stays.
$StockHzd = @{ t17 = 'p01.HZD'; t09 = 'p01.HZD'; t06 = 'p04.HZD'; t02 = 'p01.HZD'; t01 = 'p01.HZD'; t08 = 'p04.HZD'; t03 = 'p01.HZD'; t11 = 'p01.HZD'
               t12 = 'p04.HZD'; t15 = 'p02.HZD'; m05 = 'n02.HZD'; m15 = ''; t04 = 't01.hzd'; t05 = 't05.HZD'; t07 = 't07.HZD'; t10 = 't10.HZD'
               t13 = 't13.HZD'; t14 = 't14.HZD'; t16 = 'p02.hzd' }
function U32([byte[]]$b, [int]$o) { return [BitConverter]::ToUInt32($b, $o) }
function Walk([byte[]]$b, [int]$start, [int]$end) {   # strict: the chunks must tile [start, end) exactly
    $out = @(); $p = $start
    while ($p -lt $end) {
        if ($p + 8 -gt $end) { return $null }
        $size = [int](U32 $b ($p + 4))
        if ($size -lt 8 -or $p + $size -gt $end) { return $null }
        $out += [pscustomobject]@{ Tag = [Text.Encoding]::ASCII.GetString($b, $p, 4).TrimEnd([char]0); Off = $p; Size = $size }
        $p += $size
    }
    return , $out
}
function CStr([byte[]]$b, [int]$o, [int]$max) { $n = 0; while ($n -lt $max -and $o + $n -lt $b.Length -and $b[$o + $n] -ne 0) { $n++ }; return [Text.Encoding]::ASCII.GetString($b, $o, $n) }
function Convert-Wrev9([byte[]]$b) {
    if ($b.Length -lt 16 -or [Text.Encoding]::ASCII.GetString($b, 0, 4) -ne 'BWD2') { throw 'not a BWD2 file' }
    $top = Walk $b ([int](U32 $b 4)) $b.Length
    if (-not $top) { throw 'the chunk list does not tile the file' }
    $wdef = $top | Where-Object { $_.Tag -eq 'WDEF' } | Select-Object -First 1
    if (-not $wdef) { throw 'no WDEF chunk' }
    $kids = Walk $b ($wdef.Off + 8) ($wdef.Off + $wdef.Size)
    if (-not $kids) { throw 'WDEF does not tile' }
    $wrev = $kids | Where-Object { $_.Tag -eq 'WREV' } | Select-Object -First 1
    $wrld = $kids | Where-Object { $_.Tag -eq 'WRLD' } | Select-Object -First 1
    if (-not $wrev -or -not $wrld) { throw 'no WREV / WRLD in WDEF' }
    $rev = U32 $b ($wrev.Off + 8); $blen = $wrld.Size - 8; $body = $wrld.Off + 8
    if ($blen -eq 331 -or $blen -eq 347) { if ($rev -ne 9) { throw "WRLD $blen B with WREV $rev" }; return , @{ Bytes = $b; Note = 'WREV 9 already (unchanged)'; Title = (CStr $b ($body + 0x13b) 31) } }
    if ($blen -ne 318 -or $rev -ne 8) { throw "WRLD body is $blen bytes, WREV $rev (expected 318 / 8 or 331 / 9)" }
    $pal = [IO.Path]::GetFileNameWithoutExtension((CStr $b ($body + 0x1e) 13).ToLower())
    $hzd = if ($StockHzd.ContainsKey($pal)) { $StockHzd[$pal] } else { '' }
    $ins = New-Object byte[] 13; $hb = [Text.Encoding]::ASCII.GetBytes($hzd); [Array]::Copy($hb, $ins, $hb.Length)
    $at = $body + 0x86
    $o = New-Object byte[] ($b.Length + 13)
    [Array]::Copy($b, 0, $o, 0, $at); [Array]::Copy($ins, 0, $o, $at, 13); [Array]::Copy($b, $at, $o, $at + 13, $b.Length - $at)
    [BitConverter]::GetBytes([uint32]($wdef.Size + 13)).CopyTo($o, $wdef.Off + 4)
    [BitConverter]::GetBytes([uint32]($wrld.Size + 13)).CopyTo($o, $wrld.Off + 4)
    [BitConverter]::GetBytes([uint32]9).CopyTo($o, $wrev.Off + 8)       # WREV sits before WRLD: its offset is unchanged
    return , @{ Bytes = $o; Note = "WREV 8 -> 9, horizon '$hzd' inserted"; Title = (CStr $o ($body + 0x13b) 31) }
}

# ---- 1: maps ---------------------------------------------------------------------------------------------------------------
function Install-Maps {
    $targets = @{}
    if ($kind -eq 'gold') { $targets['gold'] = $GameDir } else { $targets['nitro'] = $GameDir }
    if ($NitroDir) {
        if ((Game-Kind $NitroDir) -ne 'nitro') { Fail "-NitroDir: no nitro.exe in $NitroDir" }
        $targets['nitro'] = (Resolve-Path -LiteralPath $NitroDir).Path
    }
    $sel = @($manifest.maps | Where-Object { $targets.ContainsKey($_.game) -and (-not $Only.Count -or $Only -contains $_.id) })
    if (-not $sel.Count) { Say '  no map for this folder (Gold maps need a Gold folder, Nitro maps -NitroDir <Nitro Pack folder>)' 'Yellow'; return }
    Say ''
    Say 'Community maps - made by players in 1997-2002, kept online by Local Ditch and Lightfoot''s Stolen Maps (interstate76.com).' 'Cyan'
    Say 'Each is downloaded from that site (nothing is rehosted), checked, and installed with its readme. The 1997 Gold maps are'
    Say 'converted to the layout Gold reads (one 13-byte field added, as the official 1998 editor does when it re-saves one).'
    foreach ($m in $sel) { Say ("  {0,-6} {1}" -f $m.game, $m.credit) }
    if (-not (Ask "Download and install these $($sel.Count) maps?")) { Say '  maps: skipped'; return }
    $credits = @{}
    $ok = 0
    foreach ($m in $sel) {
        $root = $targets[$m.game]
        Say "  == $($m.title)" 'Cyan'
        $zip = Get-Pinned $m.url $m.zip_sha256 ([long]$m.zip_size) $m.id
        if (-not $zip) { Say "  $($m.title): NOT installed (no verified download)" 'Yellow'; continue }
        $staged = @(); $bad = $false
        foreach ($f in $m.files) {
            $bytes = Read-Member $zip $f.member
            if ($null -eq $bytes) { Say "  $($f.member) is not in the zip" 'Yellow'; $bad = $true; break }
            $note = ''
            if ($f.convert -eq 'wrev9') { try { $r = Convert-Wrev9 $bytes; $bytes = $r.Bytes; $note = "$($r.Note), title '$($r.Title)'" } catch { Say "  $($f.member): $($_.Exception.Message)" 'Yellow'; $bad = $true; break } }
            if ($f.sha256 -and (Sha $bytes) -ne $f.sha256) { Say "  $($f.to): sha256 $(Sha $bytes) is not the tested $($f.sha256) - map NOT installed" 'Yellow'; $bad = $true; break }
            $staged += , @($f, $bytes, $note)
        }
        if ($bad) { continue }
        foreach ($s in $staged) {
            $dest = Join-Path $root ($s[0].to.Replace('/', '\'))
            if ($s[0].to -like 'ADDON/*' -and -not (Test-Path -LiteralPath (Join-Path $root 'ADDON'))) { $dest = Join-Path $root ('addon\' + (Split-Path -Leaf $s[0].to)) }
            $res = Write-Owned $dest $s[1]
            Say ("    {0} {1}{2}" -f $dest.Substring($root.Length + 1), $res, $(if ($s[2]) { " ($($s[2]))" }))
        }
        if (-not $credits.ContainsKey($root)) { $credits[$root] = @() }
        $credits[$root] += "$($m.title): $($m.credit). From $($m.url) ($($m.page))."
        $ok++
    }
    foreach ($root in $credits.Keys) {
        $lines = @("Community maps installed by the i76-everywhere Patch Kit ($(Get-Date -Format yyyy-MM-dd)). Thank you to every author.", '') + $credits[$root]
        if ((Game-Kind $root) -eq 'gold') { $lines += @('', 'These 1997 maps were converted for Gold: a 13-byte horizon field was inserted and the layout revision set to 9, as the',
                                                         'official 1998 editor does when it re-saves an old map. Every other byte is the author''s. The original readmes are in ADDON\.') }
        else { $lines += @('', 'Installed unchanged (miss8\, miss16\, addon\). The original readmes are in addon\.') }
        $lines += 'Every machine in a LAN game needs the same map files.'
        $cf = Join-Path $root 'COMMUNITY-MAPS.txt'
        [void](Write-Owned $cf ([Text.Encoding]::UTF8.GetBytes(($lines -join "`r`n") + "`r`n")))
        Say "  credits: $cf" 'DarkGray'
    }
    Say "maps: $ok of $($sel.Count) installed. Gold: MELEE > the arena list shows them by title. Nitro: HOST > COMBAT arena list." 'Green'
}

# ---- 2: opentrack ----------------------------------------------------------------------------------------------------------
function Install-OpenTrack {
    $a = $manifest.apps.opentrack
    Say ''
    Say 'opentrack - HEAD LOOK. Turn your head and the in-car view turns with it, the way a real driver glances into a corner.' 'Cyan'
    Say 'opentrack reads a tracker - a webcam (its "neuralnet" face tracker needs nothing else), a phone app, or an IR clip - and the'
    Say 'kit''s head-look layer (an AutoHotkey script) turns that into the game''s glance keys. The arrow keys still win while held.'
    Say "This downloads opentrack $($a.version) (portable, $([math]::Round($a.size / 1MB)) MB) from its GitHub release and 7-Zip's 7zr.exe (to unpack it),"
    Say 'both sha256-checked, into _tools\opentrack. Afterwards: run OPENTRACK.bat, pick your tracker, set Output = "freetrack 2.0 Enhanced",'
    Say 'press Start, then PLAY.bat - the launcher attaches to a running opentrack. Ctrl+Alt+H cycles head look ANALOG > DIGITAL > OFF.'
    if (-not (Ask 'Install opentrack?')) { Say '  opentrack: skipped'; return }
    $layer = @('i76-opentrack-headlook.ahk', 'i76-opentrack-autostart.ps1', 'i76-opentrack-autostart.ahk')
    foreach ($n in $layer) { if (-not (Test-Path -LiteralPath (Join-Path $repo $n))) { Fail "the head-look layer $n is missing from $repo" } }
    $u = $a.unpacker
    $z7 = Get-Pinned $u.url $u.sha256 ([long]$u.size) '7zr'
    if (-not $z7) { Say '  opentrack: NOT installed (7zr.exe)' 'Yellow'; return }
    $ark = Get-Pinned $a.url $a.sha256 ([long]$a.size) 'opentrack'
    if (-not $ark) { Say '  opentrack: NOT installed (download)' 'Yellow'; return }
    $tmp = Join-Path $GameDir '_tools\opentrack-unpack'
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    $global:LASTEXITCODE = 0
    & $z7 x -y "-o$tmp" $ark | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "7zr could not unpack $ark (exit $LASTEXITCODE)" }
    $exe = Get-ChildItem -LiteralPath $tmp -Recurse -Filter 'opentrack.exe' | Select-Object -First 1
    if (-not $exe) { Fail 'opentrack.exe not found in the archive' }
    $dest = Join-Path $GameDir '_tools\opentrack'
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
    Move-Item -LiteralPath $exe.DirectoryName -Destination $dest
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Set-Content -LiteralPath (Join-Path $dest 'INSTALLED-BY-i76e.txt') -Value "opentrack $($a.version) portable from $($a.url) (sha256 $($a.sha256)), unpacked $(Get-Date -Format s)" -Encoding ascii
    Ledger-Add $dest 'dir' ''
    $ahk = Join-Path $GameDir '_ahk'
    foreach ($n in $layer) { [void](Write-Owned (Join-Path $ahk $n) ([IO.File]::ReadAllBytes((Join-Path $repo $n)))) }
    $bat = "@echo off`r`nREM opentrack (head look) for Interstate '76 - installed by the i76-everywhere Patch Kit. Start it, press Start, then PLAY.bat.`r`nstart `"`" `"%~dp0_tools\opentrack\opentrack.exe`"`r`n"
    [void](Write-Owned (Join-Path $GameDir 'OPENTRACK.bat') ([Text.Encoding]::ASCII.GetBytes($bat)))
    if (-not $KeepDownloads -and $ark.StartsWith($dlDir, [StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $ark -Force -ErrorAction SilentlyContinue }
    $v = (Get-Item (Join-Path $dest 'opentrack.exe')).VersionInfo.ProductVersion
    Say "opentrack: installed in $dest (opentrack.exe $v); head-look layer in _ahk\; OPENTRACK.bat starts it." 'Green'
}

# ---- 3: AutoHotkey (bundled) --------------------------------------------------------------------------------------------------
function Show-Ahk {
    Say ''
    Say 'AutoHotkey - ALREADY IN THE KIT (_i76e\AutoHotkey, AutoHotkey 1.1, GPL). It runs the controller layer: an Xbox-style pad''s' 'Cyan'
    Say 'triggers, the LB shift layer and the right stick become the game''s keys (the 1997 engine only knows a 4-button joystick),'
    Say 'the CH Fighterstick layer, and the head-look layer above. PLAY.bat starts it with the game and stops it afterwards. Nothing to do.'
    $p = Join-Path $GameDir '_ahk\AutoHotkeyU32.exe'
    Say ("  {0}" -f $(if (Test-Path -LiteralPath $p) { "deployed: $p" } else { 'not deployed yet: the first PLAY.bat puts it in _ahk\' }))
}

# ---- 4: Python ----------------------------------------------------------------------------------------------------------------
function Install-Python {
    $a = $manifest.apps.python
    Say ''
    Say "Python $($a.version) - for DEBUG.bat (the debug dashboard in your browser: frame rate, physics steps, telemetry charts, the trainer" 'Cyan'
    Say 'with repair / ammo / teleport and car-state store / restore) and TRAINER.bat. The game itself never needs it. This downloads'
    Say "python.org's embeddable package ($([math]::Round($a.size / 1MB, 1)) MB, sha256-checked) into _tools\python: no installer, nothing outside the game folder,"
    Say 'and DEBUG.bat uses it when no other Python 3 is installed.'
    if (-not (Ask 'Install Python?')) { Say '  python: skipped'; return }
    $zip = Get-Pinned $a.url $a.sha256 ([long]$a.size) 'python'
    if (-not $zip) { Say '  python: NOT installed' 'Yellow'; return }
    $dest = Join-Path $GameDir '_tools\python'
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $dest)
    # the embeddable package's ._pth file switches off the script folder on sys.path (DEBUG.bat's modules sit beside the script):
    # without it Python computes the usual path (the script folder + the bundled pythonXY.zip standard library)
    Get-ChildItem -LiteralPath $dest -Filter 'python*._pth' | ForEach-Object { Rename-Item -LiteralPath $_.FullName -NewName ($_.Name + '.off') }
    Set-Content -LiteralPath (Join-Path $dest 'INSTALLED-BY-i76e.txt') -Value "Python $($a.version) embeddable from $($a.url) (sha256 $($a.sha256)), $(Get-Date -Format s); ._pth renamed .off" -Encoding ascii
    Ledger-Add $dest 'dir' ''
    $global:LASTEXITCODE = 0
    $out = & (Join-Path $dest 'python.exe') -c "import sys, ctypes, http.server, json; print(sys.version.split()[0])" 2>&1
    if ($LASTEXITCODE -ne 0) { Say "  python: installed but the check failed: $out" 'Yellow' } else { Say "python: $out in $dest - DEBUG.bat / TRAINER.bat use it." 'Green' }
}

# ---- 5: German voices ------------------------------------------------------------------------------------------------------------
function Read-Zfs([string]$path, [switch]$Names) {   # ZFSF v1: 28-byte header, then blocks of {u32 next, 100 x 36-byte entries}
    $fs = [IO.File]::OpenRead($path)
    try {
        $br = New-Object IO.BinaryReader($fs)
        if ([Text.Encoding]::ASCII.GetString($br.ReadBytes(4)) -ne 'ZFSF') { throw "$path is not a ZFS archive" }
        [void]$br.ReadUInt32(); $nl = $br.ReadUInt32(); $per = $br.ReadUInt32(); [void]$br.ReadUInt32(); $xor = $br.ReadUInt32(); $off = $br.ReadUInt32()
        if ($nl -ne 16) { throw 'unsupported ZFS name length' }
        $ents = @{}; $seen = @{}
        while ($off -and -not $seen.ContainsKey($off)) {
            $seen[$off] = 1; $fs.Position = $off; $next = $br.ReadUInt32()
            for ($i = 0; $i -lt $per; $i++) {
                $nb = $br.ReadBytes(16); $eo = $br.ReadUInt32(); [void]$br.ReadUInt32(); $es = $br.ReadUInt32(); [void]$br.ReadUInt32(); $fl = $br.ReadUInt32()
                if ($nb[0] -eq 0) { continue }
                $n = [Text.Encoding]::ASCII.GetString($nb).Split([char]0)[0].ToLower()
                $ents[$n] = [pscustomobject]@{ Offset = $eo; Size = $es; Method = ($fl -band 0xff); USize = ($fl -shr 8) }
            }
            $off = $next
        }
        if ($Names) { return $ents }
        return @{ Entries = $ents; Xor = $xor }
    } finally { $fs.Dispose() }
}
function Install-GermanVoices([string]$src) {
    if ($kind -ne 'gold') { Fail 'German voices: a Gold folder (i76.exe) only' }
    Say ''
    Say 'German voices - Groove, Taurus, Skeeter and the rest in the 1997 German dub, from YOUR German retail Interstate ''76.' 'Cyan'
    Say 'The voice lines are unpacked from its I76.ZFS into voices-de\ (only lines this game also has); nothing of the game itself'
    Say 'changes. PLAY.bat --voices de plays them, PLAY.bat on its own stays English. Private use: your own disc, your own copy.'
    if (-not (Test-Path -LiteralPath $src)) { Fail "-GermanVoices: $src not found" }
    $zfs = Get-ChildItem -LiteralPath $src -Recurse -Depth 2 -File -Filter 'I76.ZFS' -ErrorAction SilentlyContinue | Select-Object -First 1
    $goldZfs = Join-Path $GameDir 'I76.ZFS'
    if (-not (Test-Path -LiteralPath $goldZfs)) { Fail "no I76.ZFS in $GameDir" }
    if ($zfs -and $zfs.FullName -ieq (Resolve-Path -LiteralPath $goldZfs).Path) { Fail '-GermanVoices points at this game''s own (English) folder' }
    $gold = Read-Zfs $goldZfs -Names
    $files = @{}
    if ($zfs) {
        Say "  reading $($zfs.FullName)"
        $z = Read-Zfs $zfs.FullName
        $fs = [IO.File]::OpenRead($zfs.FullName)
        try {
            $skip = 0
            foreach ($n in $z.Entries.Keys) {
                if (-not $n.EndsWith('.wav') -or -not $gold.ContainsKey($n)) { continue }
                $e = $z.Entries[$n]
                if (($e.Method -band 6) -ne 0) { $skip++; continue }       # stored entries only (the German CD stores every .wav)
                $buf = New-Object byte[] $e.Size; $fs.Position = $e.Offset; [void]$fs.Read($buf, 0, $e.Size)
                if ($z.Xor) { for ($i = 0; $i + 3 -lt $buf.Length; $i += 4) { [BitConverter]::GetBytes(([BitConverter]::ToUInt32($buf, $i) -bxor $z.Xor)).CopyTo($buf, $i) } }
                $files[$n] = $buf
            }
            if ($skip) { Say "  $skip compressed .wav entries skipped" 'Yellow' }
        } finally { $fs.Dispose() }
    } else {
        foreach ($f in Get-ChildItem -LiteralPath $src -File -Filter '*.wav') { $n = $f.Name.ToLower(); if ($gold.ContainsKey($n)) { $files[$n] = [IO.File]::ReadAllBytes($f.FullName) } }
    }
    $differ = @($files.Keys | Where-Object { $gold[$_].USize -ne $files[$_].Length }).Count
    Say "  $($files.Count) voice lines share a name with this game's; $differ of them differ in length from the English take"
    if ($files.Count -lt 300 -or $differ -lt ($files.Count / 2)) { Fail "that does not look like the German voice set (expected about 495 shared lines, most of them different) - nothing installed" }
    if (-not (Ask "Install $($files.Count) German voice lines into voices-de\?")) { Say '  German voices: skipped'; return }
    $dest = Join-Path $GameDir 'voices-de'
    New-Item -ItemType Directory -Force $dest | Out-Null
    foreach ($n in ($files.Keys | Sort-Object)) { [void](Write-Owned (Join-Path $dest $n) $files[$n]) }
    [void](Write-Owned (Join-Path $dest 'SOURCE.txt') ([Text.Encoding]::ASCII.GetBytes("German voice lines unpacked by the i76-everywhere Patch Kit from $(if ($zfs) { $zfs.FullName } else { $src }) on $(Get-Date -Format s): $($files.Count) files. Private use.`r`n")))
    if ($Default) { Env-Set 'I76_VOICES' 'de'; Say '  German voices are now the default (PLAY.bat --voices en for English)' }
    Say "German voices: $($files.Count) lines in $dest. Start with PLAY.bat --voices de$(if ($Default) { ' (or just PLAY.bat: default)' })." 'Green'
}

# ---- 6: extra music (private) ------------------------------------------------------------------------------------------------
function Set-MusicExtra([string]$dir) {
    Say ''
    Say 'Extra music - PRIVATE. Songs of your own (for example unreleased recordings you own) shuffled in with the game''s own tracks:' 'Cyan'
    Say 'one song start in N plays the next song of your folder instead (default N = 3); missions, pause and resume work as before.'
    Say 'Nothing is downloaded, copied or shared: the launcher hands the game the folder where it is. Only for music you may play.'
    if ($dir -eq 'off') { Env-Set 'I76_MUSIC_EXTRA' ''; Env-Set 'I76_MUSIC_EXTRA_EVERY' ''; Say 'extra music: off' 'Green'; return }
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) { Fail "-MusicExtra: $dir is not a folder" }
    $dir = (Resolve-Path -LiteralPath $dir).Path
    $n = @(Get-ChildItem -LiteralPath $dir -File -Recurse -Depth 1 | Where-Object { $_.Extension -match '^\.(mp3|wav)$' }).Count
    if (-not $n) { Fail "-MusicExtra: no .mp3 / .wav in $dir (or its direct sub-folders)" }
    if ($Every -lt 1 -or $Every -gt 20) { Fail '-Every: 1..20' }
    Env-Set 'I76_MUSIC_EXTRA' $dir; Env-Set 'I76_MUSIC_EXTRA_EVERY' "$Every"
    Say "extra music: $n songs in $dir, one song start in $Every (PLAY.bat --music-extra off for one launch without)." 'Green'
}

# ---- list / uninstall --------------------------------------------------------------------------------------------------------
if ($List) {
    $rows = Ledger-Rows
    Say "installed by i76e-extras in $GameDir$(if ($NitroDir) { " / $NitroDir" }): $($rows.Count) entries"
    $rows | ForEach-Object { Say ("  {0}{1}" -f $_.Path, $(if ($_.Backup) { "  (original: $($_.Backup))" })) }
    if (Test-Path -LiteralPath $envFile) { Say 'launcher defaults (_i76e\extras.env):'; Get-Content -LiteralPath $envFile | ForEach-Object { Say "  $_" } }
    exit 0
}
if ($Uninstall) {
    $rows = @(Ledger-Rows); [array]::Reverse($rows); $n = 0
    foreach ($r in $rows) {
        if ($r.Sha -eq 'dir') { if (Test-Path -LiteralPath $r.Path) { Remove-Item -LiteralPath $r.Path -Recurse -Force; $n++ }; continue }
        if (-not (Test-Path -LiteralPath $r.Path)) { continue }
        if ((ShaFile $r.Path) -ne $r.Sha) { Say "  kept (changed since it was installed): $($r.Path)" 'Yellow'; continue }
        Remove-Item -LiteralPath $r.Path -Force; $n++
        if ($r.Backup -and (Test-Path -LiteralPath $r.Backup)) { Move-Item -LiteralPath $r.Backup -Destination $r.Path -Force; Say "  restored $($r.Path)" }
    }
    foreach ($d in (Join-Path $GameDir 'voices-de')) { if ((Test-Path -LiteralPath $d) -and -not (Get-ChildItem -LiteralPath $d -Force)) { Remove-Item -LiteralPath $d -Force } }
    Remove-Item -LiteralPath $ledger, $envFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $dlDir -Recurse -Force -ErrorAction SilentlyContinue
    Say "extras removed: $n entries" 'Green'
    exit 0
}

# ---- run ---------------------------------------------------------------------------------------------------------------------
$any = $Maps -or $OpenTrack -or $Python -or $GermanVoices -or $MusicExtra
if (-not $any) {
    Say "=== i76-everywhere Patch Kit: optional extras for $GameDir ($kind) ===" 'Cyan'
    Say 'Each option below says what it adds and asks first. Nothing here is needed to play.'
    Install-Maps
    if ($kind -eq 'gold') { Install-OpenTrack; Show-Ahk; Install-Python }
    if ($kind -eq 'gold' -and -not $Yes) {
        Say ''
        $g = Read-Host 'German voices: the folder of your German retail Interstate ''76 (CD 1 or its install folder), or Enter to skip'
        if ($g) { Install-GermanVoices $g }
        $mx = Read-Host 'Extra music (private): a folder of your own .mp3 / .wav to shuffle in, or Enter to skip'
        if ($mx) { Set-MusicExtra $mx }
    }
    Say ''; Say 'done. INSTALL-EXTRAS.bat --list shows what was installed; UNINSTALL-i76e.bat removes it with the rest.' 'Green'
    exit 0
}
if ($Maps) { Install-Maps }
if ($OpenTrack) { Install-OpenTrack }
if ($Python) { Install-Python }
if ($GermanVoices) { Install-GermanVoices $GermanVoices }
if ($MusicExtra) { Set-MusicExtra $MusicExtra }
exit 0
