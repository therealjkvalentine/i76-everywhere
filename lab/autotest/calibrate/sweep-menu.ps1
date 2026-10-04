<#
  sweep-menu.ps1 — find the OS-cursor -> menu-item mapping by detecting highlight.

  The game maps the mouse into its internal resolution in the screen's upper-left, with a
  scale we can't derive from config. So sweep the OS cursor across an upper-left grid, take a
  screenshot at each point, and let analyze-sweep.py measure the brightness of each menu
  item's text box. When an item lights up (gray -> bright), that cursor point is over it.

  Saves one PNG per grid point + grid.csv (idx,cursorX,cursorY). analyze-sweep.py does the rest.
#>
param(
    [string]$OutDir = "$PSScriptRoot\..\..\captures\sweep",
    [int]$XMax = 1700, [int]$YMax = 1150, [int]$Step = 150,
    [int]$SettleMs = 120
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"; . "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing; Add-Type -AssemblyName System.Windows.Forms
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force
function Shot($p){$vs=[Windows.Forms.SystemInformation]::VirtualScreen;$bmp=New-Object Drawing.Bitmap $vs.Width,$vs.Height;$g=[Drawing.Graphics]::FromImage($bmp);try{$g.CopyFromScreen($vs.X,$vs.Y,0,0,$bmp.Size);$bmp.Save($p,[Drawing.Imaging.ImageFormat]::Png)}finally{$g.Dispose();$bmp.Dispose()}}
$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
$rows = @('idx,cx,cy')
$i = 0
for ($y = 0; $y -le $YMax; $y += $Step) {
    for ($x = 0; $x -le $XMax; $x += $Step) {
        [Inp]::SetCursorPos($x, $y) | Out-Null
        Start-Sleep -Milliseconds $SettleMs
        Shot (Join-Path $OutDir ("g{0:D3}.png" -f $i))
        $rows += ("{0},{1},{2}" -f $i, $x, $y)
        $i++
    }
}
$rows | Set-Content (Join-Path $OutDir 'grid.csv')
Write-Host ("swept {0} points -> {1}" -f $i, (Resolve-Path $OutDir)) -ForegroundColor Green
