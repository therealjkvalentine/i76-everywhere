# ftsim.ps1 - a stand-in for opentrack's freetrack output (no camera, no tracker): creates FT_SharedMem and publishes a moving head
# at -Hz (default 60): yaw +-0.55 rad (4 s period), pitch +-0.2 rad (6 s). Runs until -StopFile appears. Refuses if FT_SharedMem exists.
param([double]$Hz = 60, [Parameter(Mandatory)][string]$StopFile)
try { [IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem').Dispose(); 'FT_SharedMem exists - not running'; exit 1 } catch [IO.FileNotFoundException] {}
$mmf = [IO.MemoryMappedFiles.MemoryMappedFile]::CreateNew('FT_SharedMem', 256); $acc = $mmf.CreateViewAccessor(0, 256)
$id = 0; $sw = [Diagnostics.Stopwatch]::StartNew(); $step = 1000.0 / $Hz; $n = 0
while (-not (Test-Path $StopFile)) {
    $t = $sw.Elapsed.TotalSeconds; $id++
    $acc.Write(12, [single](0.55 * [math]::Sin(2 * [math]::PI * $t / 4))); $acc.Write(16, [single](0.2 * [math]::Sin(2 * [math]::PI * $t / 6)))
    $acc.Write(0, [uint32]$id)
    $n++; $w = $n * $step - $sw.ElapsedMilliseconds; if ($w -gt 0) { Start-Sleep -Milliseconds ([int]$w) }
}
$acc.Dispose(); $mmf.Dispose()
