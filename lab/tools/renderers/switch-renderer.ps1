<#
  switch-renderer.ps1 - choose which Glide / DirectDraw wrapper set a renderer TEST COPY uses.

  Works only on <lab>\game-<name> folders made by make-renderer-copy.ps1 (default ..\..\game-alt). It refuses
  <lab>\game and anything outside the lab. Nothing is downloaded: every set comes from files already on disk or
  from a -Source folder you unpacked yourself. docs: i76-everywhere\docs\records\RENDERER-ALTERNATIVES.md.

    .\switch-renderer.ps1 -Status                               # what is installed, md5 + version of every slot
    .\switch-renderer.ps1 -Renderer dgvoodoo                    # back to the copy's baseline (as copied from game\)
    .\switch-renderer.ps1 -Renderer dgvoodoo -Source C:\dl\dgVoodoo2_87_5     # another dgVoodoo version
    .\switch-renderer.ps1 -Renderer nglide -Source C:\dl\nglide210            # folder with nGlide's glide2x.dll
    .\switch-renderer.ps1 -Renderer openglide-gog               # GOG's bundled OpenGLide (i76-map\sandbox-gog)
    .\switch-renderer.ps1 -Renderer openglide -Source C:\Users\james\openglide-hd
    .\switch-renderer.ps1 -Renderer custom -Source <folder>     # copies every file whose name is a slot name
    .\switch-renderer.ps1 -Renderer dgvoodoo -Overlay dxvk -OverlaySource C:\dl\dxvk-2.7.1\x32
    .\switch-renderer.ps1 -Renderer dgvoodoo -Overlay reshade -OverlaySource C:\dl\reshade    # ReShade32.dll -> dxgi.dll
    .\switch-renderer.ps1 -Renderer nglide -Source ... -Overlay reshade -ReShadeAs d3d9 -OverlaySource ...
    .\switch-renderer.ps1 -Renderer nglide -Source ... -DDraw ddrawcompat -DDrawSource C:\dl\DDrawCompat-v0.7.1
    .\switch-renderer.ps1 -Restore                              # baseline + remove the compat-layer value if we set it

  How it stays reversible: on first use the current content of every renderer SLOT (the file names in $Slots) is
  saved to <copy>\_renderer-baseline\ with md5s. Every switch first puts the slots back to that baseline, then
  applies the chosen set, so sets never stack by accident. Each run appends one line to
  <copy>\.renderer-switch.jsonl: what was asked, and for every slot that changed its md5 before and after.

  -DDraw keep        leave the baseline DDraw.dll / D3DImm.dll (dgVoodoo's: the 2D shell and its 8-bit palettes)
  -DDraw park        remove them (the default for openglide*: dgVoodoo's DDraw collides with OpenGLide's GL window
                     at boot, i76-everywhere docs\records\FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md). The game then needs
                     8-bit palettes from somewhere else: see -CompatLayer.
  -DDraw ddrawcompat install DDrawCompat's ddraw.dll from -DDrawSource instead
  -CompatLayer       set the Windows 256COLOR compatibility layer for THIS COPY's i76.exe only (an HKCU registry
                     value named by the full exe path; the only thing this script writes outside the copy; recorded
                     and removed again by -Restore / -Renderer dgvoodoo)
#>
param(
    [string]$GameDir = "",
    [ValidateSet("", "dgvoodoo", "nglide", "openglide-gog", "openglide", "custom")] [string]$Renderer = "",
    [string]$Source = "",
    [ValidateSet("", "dxvk", "reshade")] [string]$Overlay = "",
    [string]$OverlaySource = "",
    [ValidateSet("dxgi", "d3d9", "opengl32")] [string]$ReShadeAs = "dxgi",
    [ValidateSet("", "keep", "park", "ddrawcompat")] [string]$DDraw = "",
    [string]$DDrawSource = "",
    [switch]$CompatLayer,
    [switch]$NoVerify,
    [switch]$Status,
    [switch]$Restore
)
$ErrorActionPreference = "Stop"
$Lab = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $GameDir) { $GameDir = Join-Path $Lab "game-alt" }
if (-not (Test-Path $GameDir)) { throw "$GameDir does not exist - run make-renderer-copy.ps1 first" }
$G = (Resolve-Path $GameDir).Path.TrimEnd('\')
if ((Split-Path $G -Parent).TrimEnd('\') -ne $Lab.TrimEnd('\') -or (Split-Path $G -Leaf) -notmatch '^game-[A-Za-z0-9][A-Za-z0-9-]*$') {
    throw "refusing $G : only <lab>\game-<name> test copies (never game\, never the playable install)"
}
if (-not (Test-Path (Join-Path $G "i76.exe"))) { throw "no i76.exe in $G" }

# every file name a wrapper set may own. Case-insensitive on NTFS; the names are written as listed.
$Slots = "Glide.dll", "Glide2x.dll", "Glide3x.dll", "glide2x.ovl", "DDraw.dll", "D3DImm.dll", "D3D8.dll", "D3D9.dll",
         "d3d11.dll", "d3d10core.dll", "dxgi.dll", "opengl32.dll", "dgVoodoo.conf", "dgVoodooCpl.exe", "OpenGLid.ini",
         "ReShade.ini", "DDrawCompat.ini", "dxvk.conf", "nglide_config.exe", "nglide_readme.txt"
$Base = Join-Path $G "_renderer-baseline"
$StateFile = Join-Path $G ".renderer-state.json"
$LogFile = Join-Path $G ".renderer-switch.jsonl"
$LayerKey = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
$Exe = Join-Path $G "i76.exe"

function Md5($p) { if (Test-Path -LiteralPath $p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() } else { $null } }
function Ver($p) { if (Test-Path -LiteralPath $p) { $v = (Get-Item -LiteralPath $p).VersionInfo; (("{0} {1} {2}" -f $v.FileDescription, $v.ProductName, $v.FileVersion).Trim() -replace '\s+', ' ') } else { "" } }
function Snapshot { $h = [ordered]@{}; foreach ($s in $Slots) { $h[$s] = Md5 (Join-Path $G $s) }; $h }
function Layer { try { (Get-ItemProperty -Path $LayerKey -Name $Exe -ErrorAction Stop).$Exe } catch { $null } }
function First-Existing([string[]]$c) { foreach ($p in $c) { if ($p -and (Test-Path -LiteralPath $p)) { return (Resolve-Path -LiteralPath $p).Path } }; $null }
function Find-In([string]$dir, [string[]]$rel) { First-Existing ($rel | ForEach-Object { Join-Path $dir $_ }) }

if ($Status -or (-not $Renderer -and -not $Restore)) {
    $st = if (Test-Path $StateFile) { Get-Content $StateFile -Raw | ConvertFrom-Json } else { $null }
    "copy     : $G"
    "state    : " + $(if ($st) { "$($st.renderer)" + $(if ($st.overlay) { " + $($st.overlay)" }) + " ddraw=$($st.ddraw) (set $($st.time))" } else { "baseline (never switched)" })
    $bj = if (Test-Path "$Base\baseline.json") { Get-Content "$Base\baseline.json" -Raw | ConvertFrom-Json } else { $null }
    foreach ($s in $Slots) {
        $p = Join-Path $G $s; $m = Md5 $p
        $b = if ($bj) { $bj.md5.$s } else { $m }
        if (-not $m -and -not $b) { continue }
        $mark = if ($m -eq $b) { " " } elseif (-not $m) { "-" } elseif (-not $b) { "+" } else { "*" }
        "{0} {1,-18} {2,-10} {3}" -f $mark, $s, $(if ($m) { $m.Substring(0, 8) } else { "(absent)" }), (Ver $p)
    }
    "legend   : ' ' as baseline, '*' replaced, '+' added, '-' removed"
    $l = Layer; if ($l) { "compat   : $l  (HKCU AppCompatFlags\Layers for $Exe)" }
    return
}

if (Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "$G\*" }) { throw "a game process is running from $G - close it first" }
if (Test-Path (Join-Path $G ".console-test.lock")) { throw "$G\.console-test.lock is held - a test run is in progress" }
if ($Restore) { $Renderer = "dgvoodoo"; $Source = ""; $Overlay = ""; $DDraw = "keep" }
if (-not $DDraw) { $DDraw = if ($Renderer -like "openglide*") { "park" } else { "keep" } }

# --- baseline, once
if (-not (Test-Path "$Base\baseline.json")) {
    New-Item -ItemType Directory -Force $Base | Out-Null
    $snap = Snapshot
    foreach ($s in $Slots) { if ($snap[$s]) { Copy-Item -LiteralPath (Join-Path $G $s) -Destination (Join-Path $Base $s) } }
    [ordered]@{ created = (Get-Date).ToString("s"); md5 = $snap } | ConvertTo-Json -Depth 3 | Set-Content "$Base\baseline.json" -Encoding ascii
    "baseline : saved $(@($snap.Values | Where-Object { $_ }).Count) slot files to $Base"
}
$bj = Get-Content "$Base\baseline.json" -Raw | ConvertFrom-Json
foreach ($s in $Slots) { if ($bj.md5.$s -and (Md5 (Join-Path $Base $s)) -ne $bj.md5.$s) { throw "baseline file $s does not match baseline.json - not touching anything" } }

# --- resolve the sources BEFORE changing anything (a missing file must not leave a half-switched copy)
$install = [ordered]@{}      # slot name -> source path
$remove = New-Object System.Collections.ArrayList
$notes = New-Object System.Collections.ArrayList
function Need($p, $what) { if (-not $p) { throw "$what not found. Nothing was changed. See i76-everywhere docs\records\RENDERER-ALTERNATIVES.md for the download list." }; $p }

switch ($Renderer) {
    "dgvoodoo" {
        if ($Source) {
            $src = (Resolve-Path $Source).Path
            foreach ($s in "Glide.dll", "Glide2x.dll", "Glide3x.dll") { $p = Find-In $src @("3Dfx\x86\$s", $s); if ($p) { $install[$s] = $p } }
            foreach ($s in "DDraw.dll", "D3DImm.dll", "D3D8.dll", "D3D9.dll") { $p = Find-In $src @("MS\x86\$s", $s); if ($p) { $install[$s] = $p } }
            $p = Find-In $src @("dgVoodooCpl.exe"); if ($p) { $install["dgVoodooCpl.exe"] = $p }
            [void](Need $install["Glide2x.dll"] "dgVoodoo Glide2x.dll (3Dfx\x86\Glide2x.dll) under $src")
            if (-not $NoVerify -and (Ver $install["Glide2x.dll"]) -notmatch 'dgVoodoo') { throw "$($install['Glide2x.dll']) is not a dgVoodoo DLL ($(Ver $install['Glide2x.dll'])); -NoVerify to force" }
            [void]$notes.Add("dgVoodoo.conf is kept from the baseline; a newer dgVoodoo reads the older conf")
        }
    }
    "nglide" {
        $src = First-Existing @($Source, (Join-Path $Lab "refs\renderers\nglide"))
        [void](Need $src "nGlide folder (-Source, or $Lab\refs\renderers\nglide)")
        $install["Glide2x.dll"] = Need (Find-In $src @("glide2x.dll")) "glide2x.dll in $src"
        foreach ($pair in @(@("Glide.dll", "glide.dll"), @("Glide3x.dll", "glide3x.dll"), @("nglide_config.exe", "nglide_config.exe"), @("nglide_readme.txt", "nglide_readme.txt"))) {
            $p = Find-In $src @($pair[1]); if ($p) { $install[$pair[0]] = $p }
        }
        # nGlide 2.10's version resource reads "3Dfx Interactive, Inc. Glide DLL 2.61" (it poses as the real driver), so
        # identify it by its settings key string instead (found in the 2.10 DLL, 2026-10-02)
        if (-not $NoVerify) {
            $txt = [Text.Encoding]::GetEncoding(28591).GetString([IO.File]::ReadAllBytes($install["Glide2x.dll"]))
            if (-not $txt.Contains('Software\Zeus Software\nGlide2')) { throw "$($install['Glide2x.dll']) does not identify as nGlide 2.x (no 'Software\Zeus Software\nGlide2' string; version resource: $(Ver $install['Glide2x.dll'])); -NoVerify to force" }
        }
        foreach ($s in "D3D8.dll", "D3D9.dll") { [void]$remove.Add($s) }     # or nGlide's D3D9 back end would load dgVoodoo's D3D9.dll from this folder
        [void]$notes.Add("nGlide settings: HKCU\Software\Zeus Software\nGlide2 (REG_SZ numbers, per user) - tools\renderers\nglide-settings.ps1 sets / restores them; NGLIDE_BACKEND / _RESOLUTION / _ASPECT / _REFRESH / _VSYNC / _GAMMA / _SPLASH environment variables override per process")
        [void]$notes.Add("nGlide's glide2x.dll also calls DirectDrawCreate (ddraw.dll): with -DDraw keep that is dgVoodoo's DDraw.dll in this folder")
    }
    "openglide-gog" {
        $src = First-Existing @($Source, "C:\Users\james\i76-map\sandbox-gog\main\app")
        [void](Need $src "GOG reference install (i76-map\sandbox-gog\main\app)")
        $install["Glide2x.dll"] = Need (Find-In $src @("glide2x.dll")) "glide2x.dll in $src"
        if (-not $bj.md5.'OpenGLid.ini') { $p = Find-In $src @("OpenGLid.INI"); if ($p) { $install["OpenGLid.ini"] = $p } }
        foreach ($s in "Glide.dll", "Glide3x.dll", "D3D8.dll", "D3D9.dll") { [void]$remove.Add($s) }
    }
    "openglide" {
        $src = First-Existing @($Source, "C:\Users\james\openglide-hd", (Join-Path $Lab "refs\renderers\openglide"))
        [void](Need $src "OpenGLide build folder (-Source)")
        $install["Glide2x.dll"] = Need (Find-In $src @("glide2x.dll")) "glide2x.dll in $src"
        $p = Find-In $src @("glide3x.dll"); if ($p) { $install["Glide3x.dll"] = $p } else { [void]$remove.Add("Glide3x.dll") }
        $p = Find-In $src @("OpenGLid.ini"); if ($p -and -not $bj.md5.'OpenGLid.ini') { $install["OpenGLid.ini"] = $p }
        foreach ($s in "Glide.dll", "D3D8.dll", "D3D9.dll") { [void]$remove.Add($s) }
    }
    "custom" {
        $src = Need (First-Existing @($Source)) "-Source folder"
        foreach ($s in $Slots) { $p = Find-In $src @($s); if ($p) { $install[$s] = $p } }
        if ($install.Count -eq 0) { throw "no slot-named file in $src (slots: $($Slots -join ', '))" }
    }
}
if ($DDraw -eq "park") { foreach ($s in "DDraw.dll", "D3DImm.dll") { [void]$remove.Add($s); $install.Remove($s) } }
elseif ($DDraw -eq "ddrawcompat") {
    $ds = Need (First-Existing @($DDrawSource, (Join-Path $Lab "refs\renderers\ddrawcompat"))) "DDrawCompat folder (-DDrawSource)"
    $install["DDraw.dll"] = Need (Find-In $ds @("ddraw.dll")) "ddraw.dll in $ds"
    if (-not $NoVerify -and (Ver $install["DDraw.dll"]) -notmatch 'DDrawCompat') { throw "$($install['DDraw.dll']) does not identify as DDrawCompat; -NoVerify to force" }
    [void]$remove.Add("D3DImm.dll")
}
if ($Overlay -eq "dxvk") {
    if ($Renderer -ne "dgvoodoo") { throw "the dxvk overlay sits under dgVoodoo's D3D11 output: use it with -Renderer dgvoodoo" }
    $os = Need (First-Existing @($OverlaySource, (Join-Path $Lab "refs\renderers\dxvk"))) "DXVK folder (-OverlaySource: the x32 folder of a DXVK release)"
    $install["d3d11.dll"] = Need (Find-In $os @("x32\d3d11.dll", "d3d11.dll")) "32-bit d3d11.dll in $os"
    $install["dxgi.dll"] = Need (Find-In $os @("x32\dxgi.dll", "dxgi.dll")) "32-bit dxgi.dll in $os"
    $p = Find-In $os @("x32\d3d10core.dll", "d3d10core.dll"); if ($p) { $install["d3d10core.dll"] = $p }
    $p = Find-In $os @("dxvk.conf"); if ($p) { $install["dxvk.conf"] = $p }
} elseif ($Overlay -eq "reshade") {
    $os = Need (First-Existing @($OverlaySource, (Join-Path $Lab "refs\renderers\reshade"))) "ReShade folder (-OverlaySource: where ReShade32.dll was extracted)"
    $install["$ReShadeAs.dll"] = Need (Find-In $os @("ReShade32.dll")) "ReShade32.dll in $os"
    $p = Find-In $os @("ReShade.ini"); if ($p) { $install["ReShade.ini"] = $p }
    [void]$notes.Add("ReShade32.dll installed as $ReShadeAs.dll (dxgi = dgVoodoo's D3D11 output, d3d9 = nGlide's D3D9 back end, opengl32 = OpenGLide)")
}
# 32-bit check on every DLL about to go in (a 64-bit DLL fails to load with a misleading error box)
foreach ($k in @($install.Keys)) {
    $p = $install[$k]; if ($p -notmatch '\.dll$') { continue }
    $fs = [IO.File]::OpenRead($p); try { $br = New-Object IO.BinaryReader($fs); $fs.Position = 0x3c; $pe = $br.ReadInt32(); $fs.Position = $pe + 4; $mach = $br.ReadUInt16() } finally { $fs.Close() }
    if ($mach -ne 0x14c) { throw ("{0} is not a 32-bit x86 DLL (machine 0x{1:x}). Nothing was changed." -f $p, $mach) }
}

# --- apply: baseline first, then the set
$before = Snapshot
foreach ($s in $Slots) {
    $p = Join-Path $G $s
    if ($bj.md5.$s) { if ((Md5 $p) -ne $bj.md5.$s) { Copy-Item -LiteralPath (Join-Path $Base $s) -Destination $p -Force } }
    elseif (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
}
foreach ($s in $remove) { $p = Join-Path $G $s; if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force } }
foreach ($k in $install.Keys) { Copy-Item -LiteralPath $install[$k] -Destination (Join-Path $G $k) -Force }
if ($Renderer -like "openglide*") {
    # I'76 crashes when a wrapper reports more than 2 MB per TMU (same bug dgVoodoo's MemorySizeOfTMU=2048 dodges)
    $ini = Join-Path $G "OpenGLid.ini"
    if (Test-Path $ini) {
        $t = Get-Content $ini
        $t2 = $t -replace '^TextureMemorySize=\d+', 'TextureMemorySize=2' -replace '^FrameBufferMemorySize=\d+', 'FrameBufferMemorySize=2'
        if (($t -join "`n") -ne ($t2 -join "`n")) { Set-Content $ini $t2 -Encoding ascii; [void]$notes.Add("OpenGLid.ini: TextureMemorySize / FrameBufferMemorySize forced to 2") }
    } else { [void]$notes.Add("no OpenGLid.ini: create one with TextureMemorySize=2 and FrameBufferMemorySize=2 before running") }
}
$after = Snapshot

# verify every write landed
foreach ($k in $install.Keys) { if ((Md5 (Join-Path $G $k)) -ne (Md5 $install[$k]) -and $k -ne "OpenGLid.ini") { throw "write did not land: $k" } }
foreach ($s in $remove) { if (Test-Path -LiteralPath (Join-Path $G $s)) { throw "remove did not land: $s" } }

# --- compat layer (the one write outside the copy; keyed by this copy's exe path)
$layerBefore = Layer; $st0 = if (Test-Path $StateFile) { Get-Content $StateFile -Raw | ConvertFrom-Json } else { $null }
$weSet = [bool]($st0 -and $st0.compat_layer_set_by_us)
if ($CompatLayer) {
    if (-not (Test-Path $LayerKey)) { New-Item -Path $LayerKey -Force | Out-Null }
    Set-ItemProperty -Path $LayerKey -Name $Exe -Value '~ 256COLOR' -Force
    if ((Layer) -ne '~ 256COLOR') { throw "compat layer write did not land" }
    $weSet = $true
} elseif ($weSet -and $layerBefore) {
    Remove-ItemProperty -Path $LayerKey -Name $Exe -ErrorAction SilentlyContinue; $weSet = $false
}
$layerAfter = Layer

$changed = foreach ($s in $Slots) { if ($before[$s] -ne $after[$s]) { [ordered]@{ slot = $s; before = $before[$s]; after = $after[$s]; from = $install[$s] } } }
$entry = [ordered]@{
    time = (Get-Date).ToString("s"); renderer = $Renderer; overlay = $Overlay; ddraw = $DDraw; source = $Source; overlay_source = $OverlaySource
    changed = @($changed); compat_layer_before = $layerBefore; compat_layer_after = $layerAfter
}
Add-Content $LogFile ($entry | ConvertTo-Json -Depth 5 -Compress) -Encoding ascii
[ordered]@{ time = $entry.time; renderer = $Renderer; overlay = $Overlay; ddraw = $DDraw; compat_layer_set_by_us = $weSet; md5 = $after } |
    ConvertTo-Json -Depth 3 | Set-Content $StateFile -Encoding ascii

"renderer : $Renderer" + $(if ($Overlay) { " + $Overlay" }) + "  ddraw=$DDraw  in $G"
foreach ($c in @($changed)) {
    "  {0,-18} {1,-10} -> {2,-10} {3}" -f $c.slot, $(if ($c.before) { $c.before.Substring(0, 8) } else { "(absent)" }), $(if ($c.after) { $c.after.Substring(0, 8) } else { "(removed)" }), (Ver (Join-Path $G $c.slot))
}
if (-not @($changed).Count) { "  (no slot changed)" }
if ($layerBefore -ne $layerAfter) { "  compat layer: '$layerBefore' -> '$layerAfter'" }
foreach ($n in $notes) { "note     : $n" }
if ($DDraw -eq "park" -and -not $layerAfter) { "note     : DDraw parked and no 256COLOR layer: the game is expected to crash at sim entry (NULL palette, i76.exe 0x475a01). Re-run with -CompatLayer, or use -DDraw ddrawcompat." }
if ($Renderer -ne "dgvoodoo") { "note     : I76_GLIDE_REFRESH only matters to dgVoodoo's pacing; with another wrapper pace with -Env @{ I76_FPS_CAP = '179' } and compare with it unset" }
"log      : $LogFile"
