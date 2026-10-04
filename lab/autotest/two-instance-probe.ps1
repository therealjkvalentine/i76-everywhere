# two-instance-probe.ps1 - can two copies of the game run at once on this PC? Starts game\i76.exe, waits, starts
# game-alt\i76.exe, waits, reports both processes (alive, window title, responding, path) and kills them.
# No clicks, no saves touched. -Multi: installs the repo proxy in both for the run and sets I76_MULTI_INSTANCE=1.
param([switch]$Multi, [int]$Wait = 14, [string]$DirA = "C:\Users\james\i76-uncap-lab\game", [string]$DirB = "C:\Users\james\i76-uncap-lab\game-alt")
$ErrorActionPreference = "Continue"
$dirs = @($DirA, $DirB)
if (Get-Process i76* -ErrorAction SilentlyContinue) { "an i76 process is running"; exit 1 }
foreach ($d in $dirs) { if (Test-Path "$d\.console-test.lock") { "lock held in $d"; exit 1 } }
foreach ($d in $dirs) { Set-Content "$d\.console-test.lock" "two-instance-probe $PID" }
Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
try {
    if ($Multi) {
        $env:I76_MULTI_INSTANCE = "1"; $env:I76MUSIC_LOG = "1"
        foreach ($d in $dirs) { Copy-Item "$d\STRLKUP.DLL" "$d\STRLKUP.DLL.pretest" -Force; Copy-Item "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll" "$d\STRLKUP.DLL" -Force }
    }
    $procA = Start-Process "$DirA\i76.exe" -ArgumentList "-glide" -WorkingDirectory $DirA -PassThru
    Start-Sleep -Seconds $Wait
    $procB = Start-Process "$DirB\i76.exe" -ArgumentList "-glide" -WorkingDirectory $DirB -PassThru
    Start-Sleep -Seconds $Wait
    foreach ($p in $procA, $procB) {
        $q = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
        if ($q) { "pid $($q.Id) alive | title '$($q.MainWindowTitle)' | hwnd 0x{0:x} | responding $($q.Responding) | $($q.Path)" -f [int64]$q.MainWindowHandle }
        else { "pid $($p.Id) EXITED (code $($p.ExitCode))" }
    }
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object Drawing.Bitmap 3440, 1440; $gr = [Drawing.Graphics]::FromImage($bmp); $gr.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
    $out = "C:\Users\james\i76-uncap-lab\autotest\runs\two-instance"; New-Item -ItemType Directory -Force $out | Out-Null
    $small = New-Object Drawing.Bitmap $bmp, 1147, 480; $small.Save("$out\both.png"); "capture $out\both.png"
} finally {
    Get-Process i76* -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 1
    foreach ($d in $dirs) {
        if (Test-Path "$d\STRLKUP.DLL.pretest") { Copy-Item "$d\STRLKUP.DLL.pretest" "$d\STRLKUP.DLL" -Force; Remove-Item "$d\STRLKUP.DLL.pretest" }
        Remove-Item "$d\.console-test.lock" -ErrorAction SilentlyContinue
    }
}
