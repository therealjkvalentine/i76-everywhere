# sampler.ps1 - headlook-cost lane 2026-10-25. Every second: system CPU (GetSystemTimes) + FT_SharedMem DataID/yaw/pitch.
# Every 5 s: cumulative CPU (kernel+user, CIM) of EVERY process, command line for new AutoHotkey / python / powershell / opentrack pids.
# Ends when -GamePid exits. Rows: n,ms_epoch,kind,id,name,detail,value
param([Parameter(Mandatory)][int]$GamePid, [Parameter(Mandatory)][string]$Out)
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class Sys { [DllImport("kernel32.dll")] public static extern bool GetSystemTimes(out long idle, out long kern, out long user); }
'@
$cmd = @{}; $ft = $null
"t,ms_epoch,kind,id,name,detail,cpu_100ns" | Set-Content $Out
$sw = [Diagnostics.Stopwatch]::StartNew(); $n = 0
while ($true) {
    if (-not (Get-Process -Id $GamePid -ErrorAction SilentlyContinue)) { break }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds(); $rows = New-Object System.Collections.ArrayList
    [long]$i=0; [long]$k=0; [long]$u=0; [void][Sys]::GetSystemTimes([ref]$i,[ref]$k,[ref]$u)
    [void]$rows.Add("$n,$now,sys,0,sys,idle=$i;kern=$k,$u")
    if ($n % 5 -eq 0) {
        $all = Get-CimInstance Win32_Process -Property ProcessId,Name,KernelModeTime,UserModeTime -ErrorAction SilentlyContinue
        $need = @($all | Where-Object { $_.Name -match '^(AutoHotkey|python|powershell|opentrack)' -and -not $cmd.ContainsKey([int]$_.ProcessId) })
        if ($need.Count) { foreach ($q in (Get-CimInstance Win32_Process -Property ProcessId,CommandLine -ErrorAction SilentlyContinue | Where-Object { $need.ProcessId -contains $_.ProcessId })) { $cmd[[int]$q.ProcessId] = ((("$($q.CommandLine)" -replace '[",]','') -replace '\\','\') -replace '(?i)^.*?(AutoHotkeyU32\.exe|python[\w.]*\.exe|powershell\.exe|opentrack\.exe)\s*','$1 ') } }
        foreach ($p in $all) { $v = [long]$p.KernelModeTime + [long]$p.UserModeTime; if ($v -gt 0) { $d = $cmd[[int]$p.ProcessId]; [void]$rows.Add("$n,$now,proc,$($p.ProcessId),$($p.Name -replace '\.exe$',''),$d,$v") } }
    }
    try {
        if (-not $ft) { $ft = [IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem', 'Read') }
        $v = $ft.CreateViewAccessor(0, 24, 'Read'); [void]$rows.Add("$n,$now,ft,0,ft,yaw=$($v.ReadSingle(12));pitch=$($v.ReadSingle(16)),$($v.ReadUInt32(0))"); $v.Dispose()
    } catch { $ft = $null }
    Add-Content $Out $rows
    $n++
    $wait = ($n * 1000) - $sw.ElapsedMilliseconds; if ($wait -gt 0) { Start-Sleep -Milliseconds $wait }
}
