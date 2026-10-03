# One command: check the control sources against each other, regenerate the quick reference
# (HTML + the table in docs\CONTROLS.md), lint the shipped map, and print the PDF.
#
#   powershell -ExecutionPolicy Bypass -File tools\controls-sheet\build.ps1
#   ... -Exe "D:\Games\Interstate 76\i76.exe"   the exe the lint checks tokens against
#   ... -NoPdf                                   stop after the HTML
#   ... -Png                                     also write one PNG per page next to the HTML
#                                                (needs the Python package PyMuPDF; for looking
#                                                at the result, the PNGs are not committed)
#
# Starts no game and no AutoHotkey script. Exit code 0 = everything agrees and the files are
# written; 1 = the consistency check or the lint has findings (listed above the exit).
param(
    [string]$Exe = "",
    [switch]$NoPdf,
    [switch]$Png
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$repo = Split-Path (Split-Path $here -Parent) -Parent
$map  = Join-Path $repo 'controls\input.map'
$html = Join-Path $here 'controls-sheet.html'
$pdf  = Join-Path $repo 'docs\Interstate76-Controls-Quick-Reference.pdf'

# Python: the py launcher, else python (the Microsoft Store stub answers --version with an error).
$py = $null; $pyPre = @()
foreach ($cand in @(@('py', '-3'), @('python'), @('python3'))) {
    $cmd = Get-Command $cand[0] -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    $pre = @($cand | Select-Object -Skip 1)
    try { $null = & $cmd.Source @pre --version } catch { continue }
    if ($LASTEXITCODE -eq 0) { $py = $cmd.Source; $pyPre = $pre; break }
}
if (-not $py) { Write-Host "Python 3 not found (py / python). It is the only requirement." -ForegroundColor Red; exit 1 }

# 1. lint the shipped map against an exe's string table (needs a game exe; none is in the repo)
if (-not $Exe) {
    $Exe = @($env:I76_EXE,
             (Join-Path $repo '..\i76-uncap-lab\game\i76.exe'),
             'C:\GOG Games\Interstate 76\i76.exe',
             'C:\Games\Interstate 76\i76.exe') |
        Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if ($Exe -and (Test-Path $Exe)) {
    & $py @pyPre (Join-Path $repo 'tools\lint-input-map.py') $map $Exe
    if ($LASTEXITCODE -ne 0) { Write-Host "lint: findings in controls\input.map (above). Nothing built." -ForegroundColor Red; exit 1 }
} else {
    Write-Host "lint SKIPPED: no i76.exe found (pass -Exe <path>, or set I76_EXE). The consistency check still runs." -ForegroundColor Yellow
}

# 2. consistency check + HTML + the generated table in docs\CONTROLS.md
& $py @pyPre (Join-Path $here 'build_sheet.py')
if ($LASTEXITCODE -ne 0) { Write-Host "controls-sheet: inconsistent sources (listed above). Nothing built." -ForegroundColor Red; exit 1 }

# 3. PDF through headless Edge (ships with Windows 10 / 11)
if ($NoPdf) { exit 0 }
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { Write-Host "Microsoft Edge not found: HTML written, PDF not. Open $html and print it to PDF (Letter, landscape, background graphics on)." -ForegroundColor Yellow; exit 0 }
$tmp = Join-Path $env:TEMP ("i76-sheet-" + [guid]::NewGuid().ToString('N') + ".pdf")
$profileDir = Join-Path $env:TEMP 'i76-sheet-edge-profile'
$url = ([Uri]$html).AbsoluteUri
$p = Start-Process -FilePath $edge -Wait -PassThru -ArgumentList @(
    '--headless', '--disable-gpu', "--user-data-dir=`"$profileDir`"", "--print-to-pdf=`"$tmp`"", '--no-pdf-header-footer', $url)
if (-not (Test-Path $tmp) -or (Get-Item $tmp).Length -lt 1000) { Write-Host "Edge did not produce a PDF (exit $($p.ExitCode))." -ForegroundColor Red; exit 1 }
Move-Item $tmp $pdf -Force
Write-Host "wrote $pdf ($((Get-Item $pdf).Length) bytes)"

if ($Png) {
    $code = @'
import sys
try:
    import fitz
except ImportError:
    print("PyMuPDF not installed: no PNGs (pip install pymupdf)"); sys.exit(0)
doc = fitz.open(sys.argv[1])
for i, page in enumerate(doc, 1):
    out = "%s-page%d.png" % (sys.argv[2], i)
    page.get_pixmap(dpi=110).save(out)
    print("wrote", out, "(%d x %d pt)" % (page.rect.width, page.rect.height))
print("pages:", len(doc))
'@
    $script = Join-Path $env:TEMP 'i76-sheet-png.py'
    Set-Content $script $code -Encoding ascii
    & $py @pyPre $script $pdf (Join-Path $here 'controls-sheet')
}
exit 0
