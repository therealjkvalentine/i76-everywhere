<#
  make-renderer-copy.ps1 - build a SECOND sandbox copy of the game for renderer experiments.

  The live sandbox (..\..\game) is only ever READ. The copy goes to <lab>\game-alt (or -Dest <lab>\game-<name>),
  which keeps "i76-uncap-lab" in the path, so autotest\lib\memlib.ps1 / focuslib.ps1 find its process and
  autotest\proxy-run.ps1 -GameDir ..\game-alt can drive it. docs: i76-everywhere\docs\records\RENDERER-ALTERNATIVES.md.

    .\make-renderer-copy.ps1 -Plan                       # print what would be copied, touch nothing
    .\make-renderer-copy.ps1                             # full copy to ..\..\game-alt (about 520 MB)
    .\make-renderer-copy.ps1 -HardLinkAssets             # hard-link the big read-only data (smk\, music\, I76.ZFS,
                                                         #   DATABASE.MW2: about 420 MB), copy everything else
    .\make-renderer-copy.ps1 -Renderer openglide-gog     # ... then call switch-renderer.ps1 on the new copy
    .\make-renderer-copy.ps1 -Renderer nglide -RendererSource D:\dl\nglide210
    .\make-renderer-copy.ps1 -Dest ..\..\game-ngl -Force # another copy; -Force replaces an existing one

  What is NOT copied: save-backup-*\, save-probes-*\, *.log, .console-test.lock, dgVoodoo.conf.graphics-variant.
  A run in progress in the source (STRLKUP.DLL.pretest present) is handled: the copy gets the sandbox's own
  STRLKUP.DLL (the .pretest file), not the test build. A graphics variant in progress (dgVoodoo.conf.pre-graphics
  + .graphics-variant marker) likewise: the copy gets the pre-graphics conf.

  HARD LINKS: a hard-linked file is the SAME file as the one in game\. Anything that rewrites it in place
  (Copy-Item over it, the game saving) would change game\ too. So only data the game never writes is linked, and
  only on request; every DLL, exe, conf, map and save is always a real copy.

  Writes <dest>\.renderer-copy.json (source, counts, mode, md5 of every top-level dll/exe/conf/ini).
#>
param(
    [string]$Source = "",
    [string]$Dest = "",
    [switch]$HardLinkAssets,
    [switch]$Force,
    [switch]$Plan,
    [string]$Renderer = "",
    [string]$RendererSource = ""
)
$ErrorActionPreference = "Stop"
$Lab = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Source) { $Source = Join-Path $Lab "game" }
if (-not $Dest) { $Dest = Join-Path $Lab "game-alt" }
$Source = (Resolve-Path $Source).Path
$Dest = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($Dest)) { $Dest } else { Join-Path (Get-Location).Path $Dest }))

# --- guards: the destination is a sibling of game\ inside the lab, never game\ itself, never the playable install
$leaf = Split-Path $Dest -Leaf
if ((Split-Path $Dest -Parent).TrimEnd('\') -ne $Lab.TrimEnd('\')) { throw "Dest must be directly inside the lab ($Lab): $Dest" }
if ($leaf -notmatch '^game-[A-Za-z0-9][A-Za-z0-9-]*$') { throw "Dest folder name must be game-<name> (got '$leaf'); 'game' itself is never a destination" }
if ($Dest -like "*\Downloads\*" -or $Source -like "*\Downloads\*") { throw "the playable install is not a source or a destination" }
if (-not (Test-Path (Join-Path $Source "i76.exe"))) { throw "no i76.exe in $Source" }

$skipDir = '^(save-backup-.*|save-probes-.*)$'
$skipFile = '(\.log$|^\.console-test\.lock$|^dgVoodoo\.conf\.graphics-variant$|^\.renderer-.*\.json$)'
$linkRel = '^(smk\\.*|music\\.*|I76\.ZFS|DATABASE\.MW2)$'      # read-only game data, the bulk of the size

$busy = Test-Path (Join-Path $Source ".console-test.lock")
$pretest = Test-Path (Join-Path $Source "STRLKUP.DLL.pretest")
$variant = (Test-Path (Join-Path $Source "dgVoodoo.conf.graphics-variant")) -and (Test-Path (Join-Path $Source "dgVoodoo.conf.pre-graphics"))

$files = Get-ChildItem $Source -Recurse -File -Force | ForEach-Object {
    $rel = $_.FullName.Substring($Source.Length + 1)
    $top = ($rel -split '\\')[0]
    if ($rel.Contains('\') -and $top -match $skipDir) { return }
    if ($_.Name -match $skipFile) { return }
    if ($pretest -and $rel -ieq "STRLKUP.DLL.pretest") { return }
    [pscustomobject]@{ Rel = $rel; Full = $_.FullName; Length = $_.Length; Link = ($HardLinkAssets -and $rel -match $linkRel) }
}
$all = Get-ChildItem $Source -Recurse -File -Force | Measure-Object Length -Sum
$sum = ($files | Measure-Object Length -Sum).Sum
$lsum = ($files | Where-Object Link | Measure-Object Length -Sum).Sum
"source   : $Source  ({0:N0} files, {1:N1} MB on disk)" -f $all.Count, ($all.Sum / 1MB)
"dest     : $Dest"
"to place : {0:N0} files, {1:N1} MB ({2:N1} MB hard-linked, {3:N1} MB copied)" -f @($files).Count, ($sum / 1MB), ($lsum / 1MB), (($sum - $lsum) / 1MB)
"free on {0}: {1:N1} GB" -f (Split-Path $Dest -Qualifier), ((Get-PSDrive (Split-Path $Dest -Qualifier).TrimEnd(':')).Free / 1GB)
if ($busy) { "note     : the source has .console-test.lock (a test run is in progress); the copy is still read-only on the source" }
if ($pretest) { "note     : STRLKUP.DLL.pretest present - the copy's STRLKUP.DLL is taken from it (the sandbox's own DLL, not the test build)" }
if ($variant) { "note     : a graphics variant is installed in the source - the copy's dgVoodoo.conf is taken from dgVoodoo.conf.pre-graphics" }
if ($Plan) { "plan only: nothing written"; return }

if (Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "$Dest\*" }) { throw "a game process is running from $Dest" }
if (Test-Path $Dest) {
    if (-not $Force) { throw "$Dest exists; pass -Force to replace it" }
    # hard links in an old copy share data with game\: deleting a link is safe (it only drops this name)
    Remove-Item $Dest -Recurse -Force
}
New-Item -ItemType Directory -Force $Dest | Out-Null
$n = 0
foreach ($f in $files) {
    $src = $f.Full
    if ($pretest -and $f.Rel -ieq "STRLKUP.DLL") { $src = Join-Path $Source "STRLKUP.DLL.pretest" }
    if ($variant -and $f.Rel -ieq "dgVoodoo.conf") { $src = Join-Path $Source "dgVoodoo.conf.pre-graphics" }
    $dst = Join-Path $Dest $f.Rel
    $dir = Split-Path $dst -Parent
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    if ($f.Link) { New-Item -ItemType HardLink -Path $dst -Target $src | Out-Null }
    else { Copy-Item -LiteralPath $src -Destination $dst }
    $n++
}
# empty folders the game expects (hdtex\dump etc. are optional; keep the tree shape of the top level)
Get-ChildItem $Source -Directory -Force | Where-Object { $_.Name -notmatch $skipDir } | ForEach-Object {
    $d = Join-Path $Dest $_.Name; if (-not (Test-Path $d)) { New-Item -ItemType Directory $d | Out-Null }
}

$md5 = [ordered]@{}
Get-ChildItem $Dest -File -Force | Where-Object { $_.Extension -match '^\.(dll|exe|conf|ini|ovl|map)$' } | Sort-Object Name | ForEach-Object {
    $md5[$_.Name] = (Get-FileHash $_.FullName -Algorithm MD5).Hash.ToLower()
}
$manifest = [ordered]@{
    created = (Get-Date).ToString("s"); source = $Source; dest = $Dest; files = $n; bytes = $sum
    hardlinked_bytes = $lsum; hardlink_pattern = $(if ($HardLinkAssets) { $linkRel } else { "" })
    source_busy = $busy; strlkup_from_pretest = $pretest; conf_from_pre_graphics = $variant; md5 = $md5
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Dest ".renderer-copy.json") -Encoding ascii
"copied   : $n files -> $Dest ; manifest .renderer-copy.json ($($md5.Count) md5s)"

# verify the copy against the source for the files that matter (a silent short copy would test the wrong thing)
$bad = 0
foreach ($name in "i76.exe", "ZGLIDE.DLL", "Glide2x.dll", "u32x.dll", "DDraw.dll", "i76shell.dll") {
    $a = Join-Path $Source $name; $b = Join-Path $Dest $name
    if (-not (Test-Path $a)) { continue }
    if ((Get-FileHash $a -Algorithm MD5).Hash -ne (Get-FileHash $b -Algorithm MD5).Hash) { "MISMATCH $name"; $bad++ }
}
if ($bad) { throw "$bad file(s) differ from the source after the copy" } else { "verified : key binaries match the source by md5" }

if ($Renderer) {
    $a = @{ GameDir = $Dest; Renderer = $Renderer }
    if ($RendererSource) { $a.Source = $RendererSource }
    & (Join-Path $PSScriptRoot "switch-renderer.ps1") @a
}
"next     : ..\..\autotest\proxy-run.ps1 -GameDir `"$Dest`"   (physical console, no other i76 running)"
