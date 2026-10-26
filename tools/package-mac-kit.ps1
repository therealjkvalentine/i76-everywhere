<#
  package-mac-kit.ps1 - the "I'76 Mac Kit (i76-everywhere)" zip: Mac users build Interstate 76 Gold.app / Nitro.app themselves
  from their own GOG copy (owner 2026-10-25: "What about end users building the Mac version?"; record docs\records\MAC-KIT-2026-10-25.md).
  The sibling of package-patch-kit.ps1 (Windows): nothing of the game is inside, and every third-party download (Sikarugir
  Wine runtime, DxWnd, IPXWrapper) is fetched on the Mac from its own site, pinned by SHA-256 (tools\mac-kit\pins.txt).

  ONE zip with one folder, Interstate76-Mac-Kit\:
    BUILD-I76-APPS.command, i76-mac-kit.sh, README.md (= tools\mac-kit\README.md), pins.txt, VERSION.txt, MD5SUMS, LICENSE, THIRD-PARTY.md
    stubs\     the launch stubs (tools\mac-kit\stubs: our Swift sources, fixed Mach-O UUIDs, ad-hoc signed)
    payload\   env\ + dxwnd-profile.ini (tools\mac-kit\payload), graphics\base.env / fast.env (from shared\presets\graphics-mac*.psd1),
               patches\ (tools\mac-kit\make-patches.py output: BSDIFF40 patches, our bytes only), gold\ (the Gold proxy as STRLKUP.DLL,
               u32x.dll, shared\controls\input.map, the cutscene-music proxy SMACKW32.DLL, the rumble proxy i7_sfrce.dll + rumble-envelopes.ini),
               nitro\Strlkup.dll, openglide\ (OpenGLide-HD glide2x.dll + OpenGLid.INI), ahk\ (AutoHotkeyU32.exe 1.1 GPL + licence + i76-remap.ahk)

    tools\package-mac-kit.ps1 -GoldProxy <Strlkup.dll> -NitroProxy <Strlkup.dll> -MacPayloadDir <dir> -PatchesDir <dir>
                              [-GogGold <pristine GOG Gold folder>] [-GogNitro <pristine GOG Nitro folder>]   (content guard)
                              [-OutDir <lab>\downloads\mac-kit] [-Version 0.8.0]
  -MacPayloadDir holds the family Macs' own Mac-only binaries, md5-pinned below (lab builds\mac-kit-20261025\mac-payload).
  Writes <OutDir>\Interstate76-Mac-Kit-i76-everywhere-v<Version>-<sha>.zip (+ .MD5SUMS); the stage is kept for inspection.
#>
param(
    [Parameter(Mandatory)][string]$GoldProxy,
    [Parameter(Mandatory)][string]$NitroProxy,
    [Parameter(Mandatory)][string]$MacPayloadDir,
    [Parameter(Mandatory)][string]$PatchesDir,
    [string]$GogGold = (Join-Path $env:USERPROFILE 'i76-map\sandbox-gog\main\app'),
    [string]$GogNitro = (Join-Path $env:USERPROFILE 'i76-map\sandbox-gog\nitro-full\app'),
    [string]$OutDir = (Join-Path $env:USERPROFILE 'i76-uncap-lab\downloads\mac-kit'),
    [string]$Version = '0.8.0',
    [string]$Stage = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$kit = Join-Path $repo 'tools\mac-kit'
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "package-mac-kit: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$sha = (git -C $repo rev-parse --short HEAD).Trim()
$dirty = @(git -C $repo status --porcelain -- tools/mac-kit shared/controls/input.map u32x/u32x_full.dll shared/presets/graphics-mac.psd1 shared/presets/graphics-mac-fast.psd1)
if ($dirty.Count) { Say "WARNING: uncommitted changes in shipped files:`n  $($dirty -join "`n  ")" 'Yellow' }
if (-not $Stage) { $Stage = Join-Path $env:TEMP "mac-kit-stage-$sha" }
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
$top = Join-Path $Stage 'Interstate76-Mac-Kit'; $pay = Join-Path $top 'payload'
New-Item -ItemType Directory -Force $top | Out-Null
function Put([string]$from, [string]$rel) {
    if (-not (Test-Path -LiteralPath $from)) { Die "missing: $from" }
    $to = Join-Path $top $rel; New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to -Force
}

# ---- the kit's own files --------------------------------------------------------------------------------------------
foreach ($n in 'BUILD-I76-APPS.command', 'i76-mac-kit.sh', 'README.md', 'pins.txt') { Put (Join-Path $kit $n) $n }
Put (Join-Path $repo 'LICENSE') 'LICENSE'; Put (Join-Path $repo 'THIRD-PARTY.md') 'THIRD-PARTY.md'
Get-ChildItem -LiteralPath (Join-Path $kit 'stubs') -File | ForEach-Object { Put $_.FullName "stubs\$($_.Name)" }
Get-ChildItem -LiteralPath (Join-Path $kit 'payload\env') -File | ForEach-Object { Put $_.FullName "payload\env\$($_.Name)" }
Put (Join-Path $kit 'payload\dxwnd-profile.ini') 'payload\dxwnd-profile.ini'
# stubs: the committed md5s must match (they are what keeps the Local Network answer)
foreach ($l in Get-Content (Join-Path $kit 'stubs\STUBS.md5')) {
    $h, $n = $l -split '\s+', 2
    if ((Md5 (Join-Path $kit "stubs\$n")) -ne $h) { Die "stub $n does not match STUBS.md5" }
}

# ---- graphics tiers from the presets (one source): KEY=VALUE, an empty value = the key removed (stock) -----------------
New-Item -ItemType Directory -Force (Join-Path $pay 'graphics') | Out-Null
foreach ($pair in @(@('graphics-mac', 'base'), @('graphics-mac-fast', 'fast'))) {
    $p = Import-PowerShellDataFile (Join-Path $repo "shared\presets\$($pair[0]).psd1")
    $lines = @("# from presets\$($pair[0]).psd1 (repo $sha): $($p.Summary)") + @($p.Env.Keys | Sort-Object | ForEach-Object { "$_=$($p.Env[$_])" })
    [IO.File]::WriteAllText((Join-Path $pay "graphics\$($pair[1]).env"), (($lines -join "`n") + "`n"))
}

# ---- binaries: ours (proxies, u32x, stubs) and the family Macs' Mac-only set, md5-pinned ---------------------------------
$goldMd5 = Md5 $GoldProxy; $nitroMd5 = Md5 $NitroProxy
if (-not $goldMd5.StartsWith('5d6f9828')) { Say "NOTE: Gold proxy $goldMd5 is not the family LAN build 5d6f9828 (LAN joins need the same proxy on every machine)" 'Yellow' }
if (-not $nitroMd5.StartsWith('3f27c797')) { Say "NOTE: Nitro proxy $nitroMd5 is not the family LAN build 3f27c797" 'Yellow' }
Put $GoldProxy 'payload\gold\STRLKUP.DLL'; Put $NitroProxy 'payload\nitro\Strlkup.dll'
Put (Join-Path $repo 'u32x\u32x_full.dll') 'payload\gold\u32x.dll'
Put (Join-Path $repo 'shared\controls\input.map') 'payload\gold\input.map'
$macPins = [ordered]@{
    'Glide2x.dll'          = @('429e6e949a0c06f1f0ce8f7ce4fe54dd', 'payload\openglide\glide2x.dll')   # OpenGLide-HD (tools\openglide-hd patches, LGPL)
    'OpenGLid.INI'         = @('4b9f29cce81dd9edcbf7f907a1d5ded2', 'payload\openglide\OpenGLid.INI')
    'SMACKW32.DLL'         = @('3dd72cfc823d95b2a560276f07d0fb90', 'payload\gold\SMACKW32.DLL')       # smack-music-fix (ours)
    'i7_sfrce.dll'         = @('3b7b0fe8effd5d44cf74dfe1975475ae', 'payload\gold\i7_sfrce.dll')       # the rumble proxy (ours)
    'rumble-envelopes.ini' = @('362bd617', 'payload\gold\rumble-envelopes.ini')
    'AutoHotkeyU32.exe'    = @('b6af97aa32c636c3c4e87bb768a3ceb7', 'payload\ahk\AutoHotkeyU32.exe')   # AutoHotkey 1.1.37.02, GPL v2
    'license.txt'          = @('e3f2ad7733f3166fe770e4dc00af6c45', 'payload\ahk\license.txt')
    'i76-remap.ahk'        = @('098fdde95b891669d991aabb75927a98', 'payload\ahk\i76-remap.ahk')       # the Mac apps' remapper (mouse 4/5, wheel)
}
foreach ($n in $macPins.Keys) {
    $from = Join-Path $MacPayloadDir $n; if (-not (Test-Path -LiteralPath $from)) { Die "Mac payload file missing: $from" }
    $m = Md5 $from; if (-not $m.StartsWith($macPins[$n][0])) { Die "$n md5 $m is not the pinned $($macPins[$n][0])" }
    Put $from $macPins[$n][1]
}
foreach ($f in Get-ChildItem -LiteralPath $PatchesDir -File) { Put $f.FullName "payload\patches\$($f.Name)" }
if (-not (Test-Path -LiteralPath (Join-Path $pay 'patches\patches.txt'))) { Die "no patches.txt in $PatchesDir (tools\mac-kit\make-patches.py)" }

# ---- the game-byte guard: no staged file may be a GOG file (by md5), and no GOG name except our own proxies -------------
$gogMd5 = @{}
foreach ($d in $GogGold, $GogNitro) { if ($d -and (Test-Path -LiteralPath $d)) { Get-ChildItem -LiteralPath $d -Recurse -File | ForEach-Object { $gogMd5[(Md5 $_.FullName)] = $_.FullName } } }
if (-not $gogMd5.Count) { Say 'WARNING: no pristine GOG folder given: only the name guard runs' 'Yellow' }
$ours = @('STRLKUP.DLL', 'Strlkup.dll', 'SMACKW32.DLL', 'i7_sfrce.dll', 'glide2x.dll', 'OpenGLid.INI', 'input.map', 'u32x.dll')
$guard = '(?i)^(i76|nitro|splash)\.exe$|^(i76shell|nitshell)|\.(zfs|zix|mw2|def|smk|mp3|wav|pcx|fnt|ttf|cur|ovl|msn|lvl|vcf|ter|cbt)$|^strlkup_orig|^smackorg|^i7_sfrce_org|^(goggame|win32|audiere|anetdll|zglide|zdx5draw|zredline)'
foreach ($f in Get-ChildItem -LiteralPath $Stage -Recurse -File) {
    if ($gogMd5.ContainsKey((Md5 $f.FullName))) { Die "$($f.FullName) is byte-identical to GOG's $($gogMd5[(Md5 $f.FullName)]) - NOT packed" }
    if ($f.Name -match $guard -and $f.Name -notin $ours -and $f.Extension -ne '.bsdiff') { Die "game-like file name in the stage: $($f.FullName)" }
}

# ---- VERSION.txt + MD5SUMS, then the zip (Python zipfile: keeps the unix exec bits the .command / .sh / stubs need) --------
@(
    "mac-kit-v$Version $sha",
    "I'76 Mac Kit (i76-everywhere), packed $(Get-Date -Format 'yyyy-MM-dd HH:mm') by tools\package-mac-kit.ps1 from repo commit $sha",
    "Gold proxy STRLKUP.DLL $goldMd5; Nitro proxy Strlkup.dll $nitroMd5; u32x $(Md5 (Join-Path $repo 'u32x\u32x_full.dll'))",
    "stubs: $(((Get-Content (Join-Path $kit 'stubs\STUBS.md5')) | ForEach-Object { ($_ -split '\s+')[1] + ' ' + ($_ -split '\s+')[0].Substring(0, 8) }) -join ', ')",
    "downloads on the Mac (pins.txt): Sikarugir Template 1.0.11 + Wine 10.0_6, DxWnd 2.06.14, IPXWrapper 0.7.2"
) | Set-Content -LiteralPath (Join-Path $top 'VERSION.txt') -Encoding ascii
$sums = Get-ChildItem -LiteralPath $top -Recurse -File | Sort-Object FullName | ForEach-Object { "$(Md5 $_.FullName)  $($_.FullName.Substring($top.Length + 1).Replace('\', '/'))" }
[IO.File]::WriteAllText((Join-Path $top 'MD5SUMS'), (($sums -join "`n") + "`n"))
New-Item -ItemType Directory -Force $OutDir | Out-Null
$zip = Join-Path $OutDir "Interstate76-Mac-Kit-i76-everywhere-v$Version-$sha.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
$py = @'
import os, sys, zipfile
stage, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for d, _, fs in os.walk(stage):
        for f in sorted(fs):
            p = os.path.join(d, f); rel = os.path.relpath(p, stage).replace(os.sep, '/')
            zi = zipfile.ZipInfo.from_file(p, rel); zi.create_system = 3
            ex = f.endswith(('.sh', '.command')) or f.startswith('Sikarugir-')
            zi.external_attr = ((0o100755 if ex else 0o100644) << 16); zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, open(p, 'rb').read())
'@
$pyf = Join-Path $env:TEMP 'mac-kit-zip.py'; Set-Content -LiteralPath $pyf -Value $py -Encoding ascii
& python -I $pyf $Stage $zip; if ($LASTEXITCODE) { Die 'zip failed' }
Set-Content -LiteralPath "$zip.MD5SUMS" -Value $sums -Encoding ascii
$n = @(Get-ChildItem -LiteralPath $top -Recurse -File).Count
Say ("packed {0}: {1} files, {2:N1} MB, md5 {3}" -f $zip, $n, ((Get-Item -LiteralPath $zip).Length / 1MB), (Md5 $zip)) 'Green'
Say "stage kept at $Stage"
