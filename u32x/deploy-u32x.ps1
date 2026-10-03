<#
  deploy-u32x.ps1 - install (or remove) the USER32 proxy in a game directory.

  Two steps, both reversible, with backups, each read back after it is written:
    1. copies u32x.dll beside the game (the previous one, if different, is kept as
       u32x.dll.pre-<md5 prefix>)
    2. retargets the USER32.dll import descriptor of i76shell.dll AND i76.exe to u32x.dll
       (backups: i76shell.dll.orig, i76.exe.u32xorig). Both are needed: the engine, not the
       shell, owns the cursor in the menus (measured 2026-08-16).

  Guards, because a proxy that lacks one imported name stops the game loading at all:
    * every function the target imports from USER32 must be exported by the DLL being deployed
      (checked from the two PE files before anything is written);
    * the DLL must be 32-bit;
    * the DLL's md5 must be the recorded live-verified build unless -AllowUnverified is given.

  This is the repo's port of ..\i76-uncap-lab\tools\instruments\deploy-shellfix.ps1 (which
  string-searched for "USER32.dll"; this one patches the import descriptor's own name).

      u32x\deploy-u32x.ps1 -GameDir <dir>                 # install the committed u32x.dll (minimal build)
      u32x\deploy-u32x.ps1 -GameDir <dir> -U32xDll u32x\u32x_full.dll   # the daily driver's build
      u32x\deploy-u32x.ps1 -GameDir <dir> -Status
      u32x\deploy-u32x.ps1 -GameDir <dir> -Restore        # put the original binaries back
      u32x\deploy-u32x.ps1 -GameDir <dir> -U32xDll <path> -AllowUnverified   # a test build

  -GameDir is mandatory on purpose: there is no default that could land on the install being
  played on (AGENTS.md "never test on the playable install").
#>
param(
    [Parameter(Mandatory = $true)][string]$GameDir,
    [string]$U32xDll = (Join-Path $PSScriptRoot 'u32x.dll'),
    [string]$Exe = 'i76.exe',
    [switch]$AllowUnverified,
    [switch]$Restore,
    [switch]$Status
)
$ErrorActionPreference = 'Stop'

# The builds that have been run live and may be installed without -AllowUnverified.
# md5 -> what it is. Source and provenance: u32x\README.md.
$KnownGood = @{
    'a5927cea02697657ce2102be766b5616' = 'u32x_min: 2026-08-16 build + DisableProcessWindowsGhosting (sandbox-verified 2026-10-02)'
    # u32x_full.dll in this folder (source u32x_full.c = lab src\u32x.c at lab commit 68a8a39;
    # the lab keeps the same binary as src\u32x_gated_054fb411.dll). The 2026-10-03 daily
    # driver runs this one, and setup-windows.ps1 installs it by default.
    '054fb411d57c275f9a6ebcf9a99893e6' = 'gated 2026-10-02/03: leg-b 3/3, trip route 120 fps, save screen, Esc-menu Exit, melee'
}

$TARGETS = @(
    @{ Name = 'i76shell.dll'; Path = (Join-Path $GameDir 'i76shell.dll'); Backup = (Join-Path $GameDir 'i76shell.dll.orig') },
    @{ Name = $Exe;           Path = (Join-Path $GameDir $Exe);           Backup = (Join-Path $GameDir "$Exe.u32xorig") }
)
$proxyDst = Join-Path $GameDir 'u32x.dll'
$enc = [Text.Encoding]::ASCII

# ---- minimal PE reader (PE32 only) ---------------------------------------------------------
function Get-PE([byte[]]$b) {
    if ($b.Length -lt 0x100 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) { throw "not a PE file" }
    $pe = [BitConverter]::ToInt32($b, 0x3c)
    if ([BitConverter]::ToUInt32($b, $pe) -ne 0x4550) { throw "no PE signature" }
    $machine = [BitConverter]::ToUInt16($b, $pe + 4)
    $nsec    = [BitConverter]::ToUInt16($b, $pe + 6)
    $optSize = [BitConverter]::ToUInt16($b, $pe + 20)
    $opt     = $pe + 24
    if ([BitConverter]::ToUInt16($b, $opt) -ne 0x10b) { throw "not PE32" }
    $secs = @()
    $st = $opt + $optSize
    for ($i = 0; $i -lt $nsec; $i++) {
        $o = $st + 40 * $i
        $secs += , @{ VSize = [BitConverter]::ToUInt32($b, $o + 8);  VA  = [BitConverter]::ToUInt32($b, $o + 12)
                      RSize = [BitConverter]::ToUInt32($b, $o + 16); Raw = [BitConverter]::ToUInt32($b, $o + 20) }
    }
    @{ Machine = $machine; Opt = $opt; Secs = $secs
       ExportRva = [BitConverter]::ToUInt32($b, $opt + 96); ImportRva = [BitConverter]::ToUInt32($b, $opt + 104) }
}
function Rva-Off($pe, [uint32]$rva) {
    foreach ($s in $pe.Secs) {
        $span = [Math]::Max($s.VSize, $s.RSize)
        if ($rva -ge $s.VA -and $rva -lt ($s.VA + $span)) { return [int]($rva - $s.VA + $s.Raw) }
    }
    throw ("RVA 0x{0:X} is in no section" -f $rva)
}
function Read-CStr([byte[]]$b, [int]$off) {
    $e = $off; while ($e -lt $b.Length -and $b[$e] -ne 0) { $e++ }
    $enc.GetString($b, $off, $e - $off)
}
# Import descriptors: name, file offset of the name string, imported function names.
function Get-Imports([byte[]]$b) {
    $pe = Get-PE $b
    $out = @()
    if (-not $pe.ImportRva) { return $out }
    $d = Rva-Off $pe $pe.ImportRva
    while ($true) {
        $oft = [BitConverter]::ToUInt32($b, $d); $nameRva = [BitConverter]::ToUInt32($b, $d + 12)
        $ft  = [BitConverter]::ToUInt32($b, $d + 16)
        if ($nameRva -eq 0 -and $ft -eq 0) { break }
        $nameOff = Rva-Off $pe $nameRva
        $thunk = Rva-Off $pe $(if ($oft) { $oft } else { $ft })
        $funcs = @()
        while ($true) {
            $v = [BitConverter]::ToUInt32($b, $thunk); if ($v -eq 0) { break }
            if ($v -band 0x80000000) { $funcs += ('#{0}' -f ($v -band 0xFFFF)) }
            else { $funcs += (Read-CStr $b ((Rva-Off $pe $v) + 2)) }
            $thunk += 4
        }
        $out += , @{ Name = (Read-CStr $b $nameOff); NameOff = $nameOff; Funcs = $funcs }
        $d += 20
    }
    $out
}
function Get-ExportNames([byte[]]$b) {
    $pe = Get-PE $b
    if (-not $pe.ExportRva) { return @() }
    $e = Rva-Off $pe $pe.ExportRva
    $n = [BitConverter]::ToUInt32($b, $e + 24)
    $names = Rva-Off $pe ([BitConverter]::ToUInt32($b, $e + 32))
    $out = @()
    for ($i = 0; $i -lt $n; $i++) { $out += (Read-CStr $b (Rva-Off $pe ([BitConverter]::ToUInt32($b, $names + 4 * $i)))) }
    $out
}
function Get-Md5([string]$p) { (Get-FileHash $p -Algorithm MD5).Hash.ToLower() }
function Import-State([string]$path) {
    # 'u32x' / 'user32' / 'none'
    $imps = Get-Imports ([IO.File]::ReadAllBytes($path))
    if ($imps | Where-Object { $_.Name -ieq 'u32x.dll' })   { return 'u32x' }
    if ($imps | Where-Object { $_.Name -ieq 'USER32.dll' }) { return 'user32' }
    'none'
}

# ---- status -----------------------------------------------------------------------------
if ($Status) {
    foreach ($t in $TARGETS) {
        if (-not (Test-Path $t.Path)) { "{0,-13}: MISSING" -f $t.Name; continue }
        $s = Import-State $t.Path
        "{0,-13}: {1}" -f $t.Name, $(switch ($s) { 'u32x' { 'PATCHED (imports u32x.dll)' } 'user32' { 'stock (imports USER32.dll)' } default { 'no USER32 import found' } })
    }
    if (Test-Path $proxyDst) {
        $m = Get-Md5 $proxyDst
        "{0,-13}: present, md5 {1} ({2})" -f 'u32x.dll', $m, $(if ($KnownGood.ContainsKey($m)) { $KnownGood[$m] } else { 'not a recorded verified build' })
    } else { "{0,-13}: absent" -f 'u32x.dll' }
    exit 0
}

$running = Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "$GameDir*" }
if ($running) { throw "the game in $GameDir is running - close it first" }

# ---- restore ----------------------------------------------------------------------------
if ($Restore) {
    foreach ($t in $TARGETS) {
        if (Test-Path $t.Backup) {
            Copy-Item $t.Backup $t.Path -Force
            if ((Get-Md5 $t.Backup) -ne (Get-Md5 $t.Path)) { throw "restore of $($t.Name) did not land" }
            "restored $($t.Name) from $(Split-Path $t.Backup -Leaf)"
        } else { "no backup found for $($t.Name)" }
    }
    "u32x.dll left in place (nothing imports it now)"
    exit 0
}

# ---- install: check everything before writing anything --------------------------------------
if (-not (Test-Path $U32xDll)) { throw "u32x DLL not found: $U32xDll" }
$dllBytes = [IO.File]::ReadAllBytes($U32xDll)
if ((Get-PE $dllBytes).Machine -ne 0x14c) { throw "$U32xDll is not a 32-bit DLL" }
$dllMd5 = Get-Md5 $U32xDll
if (-not $KnownGood.ContainsKey($dllMd5)) {
    if (-not $AllowUnverified) {
        throw "$U32xDll (md5 $dllMd5) is not a recorded live-verified build. Pass -AllowUnverified to install it on a TEST copy."
    }
    Write-Host "WARNING: installing an unverified u32x build (md5 $dllMd5)." -ForegroundColor Yellow
} else { "u32x.dll: md5 $dllMd5 = $($KnownGood[$dllMd5])" }
$exports = @{}; foreach ($n in (Get-ExportNames $dllBytes)) { $exports[$n] = $true }

$plan = @()
foreach ($t in $TARGETS) {
    if (-not (Test-Path $t.Path)) { throw "$($t.Name) not found in $GameDir" }
    $bytes = [IO.File]::ReadAllBytes($t.Path)
    $imps = Get-Imports $bytes
    $d = $imps | Where-Object { $_.Name -ieq 'USER32.dll' -or $_.Name -ieq 'u32x.dll' } | Select-Object -First 1
    if (-not $d) { throw "$($t.Name) has no USER32.dll import descriptor - unexpected variant, nothing written" }
    $missing = @($d.Funcs | Where-Object { -not $exports.ContainsKey($_) })
    if ($missing.Count) {
        throw "$($t.Name) imports $($missing.Count) USER32 function(s) the proxy does not export ($($missing -join ', ')) - it would not load. Nothing written."
    }
    $plan += , @{ T = $t; Bytes = $bytes; Desc = $d }
}

# ---- write, reading each write back -------------------------------------------------------
if ((Test-Path $proxyDst) -and (Get-Md5 $proxyDst) -ne $dllMd5) {
    $keep = "$proxyDst.pre-$((Get-Md5 $proxyDst).Substring(0, 8))"
    if (-not (Test-Path $keep)) { Copy-Item $proxyDst $keep; "kept the previous u32x.dll as $(Split-Path $keep -Leaf)" }
}
Copy-Item $U32xDll $proxyDst -Force
if ((Get-Md5 $proxyDst) -ne $dllMd5) { throw "u32x.dll copy did not land (md5 mismatch)" }
"deployed u32x.dll ($dllMd5)"

$new = $enc.GetBytes("u32x.dll`0`0")      # same length as "USER32.dll", NUL-padded
foreach ($p in $plan) {
    $t = $p.T
    if ($p.Desc.Name -ieq 'u32x.dll') { "$($t.Name): already imports u32x.dll"; continue }
    if (-not (Test-Path $t.Backup)) { Copy-Item $t.Path $t.Backup; "backed up $($t.Name) -> $(Split-Path $t.Backup -Leaf)" }
    $bytes = $p.Bytes
    for ($j = 0; $j -lt $new.Length; $j++) { $bytes[$p.Desc.NameOff + $j] = $new[$j] }
    [IO.File]::WriteAllBytes($t.Path, $bytes)
    if ((Import-State $t.Path) -ne 'u32x') { throw "$($t.Name): patch did not land (read-back still shows USER32.dll)" }
    "patched $($t.Name): USER32.dll -> u32x.dll (import descriptor name at file offset 0x{0:X})" -f $p.Desc.NameOff
}
