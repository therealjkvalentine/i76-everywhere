# Interstate '76 - swap the Glide renderer between dgVoodoo2 and OpenGLide-HD.
#
#   dgVoodoo   - the daily driver: 3x windowed, 8x MSAA, LSFG-friendly.
#   openglide  - the OpenGLide-HD fork build: TRUE high-resolution texture
#                replacement (hdtex\ pack) + dumping (hdtex\dump\), at native
#                640x480 window. See docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md.
#
# OpenGLide-HD notes (hard-won; see FINDINGS doc for the full saga):
#   - OpenGLid.ini MUST keep TextureMemorySize=2 (and FrameBufferMemorySize=2):
#     I76 crashes on >2MB TMU reports - same engine bug dgVoodoo works around
#     with MemorySizeOfTMU=2048 (VOGONS t=70951), reconfirmed at wrapper level.
#   - The game needs 8-bit DDraw palettes or it crashes at sim entry
#     (i76.exe 0x475a01 = IDirectDrawPalette::SetEntries on a NULL palette;
#     GOG's own OpenGLide build crashes identically on bare system ddraw).
#     dgVoodoo's DDraw wrapper provides palettes BUT collides with OpenGLide's
#     GL window at boot (deterministic winmmbase crash) - so OpenGLide mode
#     instead uses the Windows 256COLOR compatibility layer (registry, HKCU)
#     on i76.exe and parks dgVoodoo's DDraw. dgVoodoo mode restores DDraw and
#     clears the compat flag. The two fixes are mode-specific and this script
#     owns the switching.
#
# Usage: powershell -ExecutionPolicy Bypass -File swap-renderer.ps1 dgvoodoo|openglide
#          [-GameDir "C:\Games\Interstate 76"]

param(
    [Parameter(Mandatory=$true)][ValidateSet('dgvoodoo','openglide')][string]$Renderer,
    [string]$GameDir = "C:\Games\Interstate 76"
)
$ErrorActionPreference = 'Stop'
$bk = Join-Path $GameDir '_openglide-backup'

if (Get-Process i76 -ErrorAction SilentlyContinue) {
    Write-Host "i76.exe is running - close the game first." -ForegroundColor Red
    exit 1
}

if ($Renderer -eq 'dgvoodoo') {
    if (-not (Test-Path "$GameDir\Glide2x.dll.dgvoodoo")) {
        Write-Host "No dgVoodoo backup found (Glide2x.dll.dgvoodoo)." -ForegroundColor Red; exit 1
    }
    Copy-Item "$GameDir\Glide2x.dll.dgvoodoo" "$GameDir\Glide2x.dll" -Force
    foreach ($d in 'DDraw.dll','D3DImm.dll') {
        if (-not (Test-Path "$GameDir\$d") -and (Test-Path "$bk\$d.dgvoodoo")) {
            Copy-Item "$bk\$d.dgvoodoo" "$GameDir\$d" -Force
        }
    }
    Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers' `
        -Name "$GameDir\i76.exe" -ErrorAction SilentlyContinue
    Write-Host "Renderer: dgVoodoo2 (3x windowed, MSAA; DDraw wrapping restored, compat flag cleared)."
} else {
    $dll = "$env:USERPROFILE\openglide-hd\glide2x.dll"
    if (-not (Test-Path $dll)) {
        Write-Host "OpenGLide-HD build not found at $dll - build it first (tools\openglide-hd\README.md)." -ForegroundColor Red; exit 1
    }
    if ((Test-Path "$GameDir\Glide2x.dll") -and -not (Test-Path "$GameDir\Glide2x.dll.dgvoodoo")) {
        Copy-Item "$GameDir\Glide2x.dll" "$GameDir\Glide2x.dll.dgvoodoo" -Force
    }
    Copy-Item $dll "$GameDir\Glide2x.dll" -Force
    # park dgVoodoo's DDraw (collides with OpenGLide GL at boot) and use the
    # Windows 256-color compat layer for the game's palette needs instead
    foreach ($d in 'DDraw.dll','D3DImm.dll') {
        if (Test-Path "$GameDir\$d") { Move-Item "$GameDir\$d" "$bk\$d.dgvoodoo" -Force }
    }
    Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers' `
        -Name "$GameDir\i76.exe" -Value '~ 256COLOR DISABLEDXMAXIMIZEDWINDOWEDMODE' -Force
    # enforce the 2MB TMU requirement
    $ini = "$GameDir\OpenGLid.ini"
    if (Test-Path $ini) {
        (Get-Content $ini) -replace 'TextureMemorySize=\d+','TextureMemorySize=2' `
                           -replace 'FrameBufferMemorySize=\d+','FrameBufferMemorySize=2' | Set-Content $ini
    }
    Write-Host "Renderer: OpenGLide-HD (hdtex\ replacement pack active if present)."
    Write-Host "Dump mode: create '$GameDir\hdtex\dump' to harvest textures while playing."
}
