# nucleus-stop.ps1 - end a Nucleus Co-op session cleanly (2026-10-05). Must run elevated (Nucleus and the games are
# elevated): through the bridge, `nucleus-q.ps1 -Cmd "& C:\Users\james\i76-uncap-lab\autotest\nucleus-stop.ps1"`.
#
# Why not the obvious ways (first run, 2026-10-05; Nucleus v2.4.2 source):
#  - Ctrl+Q / Ctrl+E: HotkeyListener.WndProc drops EVERY WM_HOTKEY while input is locked (End key) and shows
#    "Unlock Inputs First" (only the cutscene key and pass-through custom keys get through). The run had locked input.
#  - Process.CloseMainWindow(): it posts WM_CLOSE to the process's first visible top-level window. During a session
#    that is an OSD window or a pending prompt (the run's call dismissed the "install post hooks" prompt), not the
#    main form, which is hidden (rect Empty).
# What works without unlocking: WM_CLOSE to the form titled "Nucleus Co-op". MainWindowFunc.MainForm_Closed calls
# I_GameHandlerEndFunc("OnFormClosed", false) -> GenericGameHandler.End(false), which skips the input-lock check
# (only fromStopButton=true is refused while locked), kills the game processes, runs CMDBatchClose and restores
# windows. Debug log: "----------------- SHUTTING DOWN -----------------".
# Stop-Process is the fallback only after -TimeoutSec, and the output says so.
param([int]$TimeoutSec = 30, [switch]$NoFallback)
Add-Type @"
using System; using System.Runtime.InteropServices; using System.Text;
public class NS { public delegate bool EP(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool EnumWindows(EP f, IntPtr l);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
[DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l); }
"@
$nc = @(Get-Process NucleusCoop -ErrorAction SilentlyContinue)
if (-not $nc) { "no NucleusCoop process"; Get-Process i76 -ErrorAction SilentlyContinue | Select-Object Id, Path; exit 0 }
$pids = @{}; $nc | ForEach-Object { $pids[[uint32]$_.Id] = 1 }
$forms = New-Object Collections.ArrayList
[NS]::EnumWindows({ param($h, $l) $p = 0; [void][NS]::GetWindowThreadProcessId($h, [ref]$p)
    if ($pids.ContainsKey($p)) { $sb = New-Object Text.StringBuilder 200; [void][NS]::GetWindowText($h, $sb, 200)
        if ($sb.ToString() -eq "Nucleus Co-op") { [void]$forms.Add($h) } }; $true }, [IntPtr]::Zero) | Out-Null
"Nucleus pid(s) $($pids.Keys -join ','); 'Nucleus Co-op' form(s): $($forms -join ',')"
$games = @(Get-Process i76 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*\refs\nucleus\run\content\*" })
"session games: $(($games | ForEach-Object { "$($_.Id)" }) -join ',')"
$watch = @($nc | ForEach-Object { $_.Id }) + @($games | ForEach-Object { $_.Id })
foreach ($h in $forms) { "WM_CLOSE -> $h : $([NS]::PostMessage($h, 0x10, [IntPtr]::Zero, [IntPtr]::Zero))" }
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    $left = @(Get-Process -Id $watch -ErrorAction SilentlyContinue)
    if (-not $left) { "clean stop: Nucleus and the session games exited after $([int]$sw.Elapsed.TotalSeconds) s"; exit 0 }
    Start-Sleep -Milliseconds 500
}
$left = @(Get-Process -Id $watch -ErrorAction SilentlyContinue)
"after $TimeoutSec s still running: $(($left | ForEach-Object { "$($_.ProcessName) $($_.Id)" }) -join ', ')"
if (-not $NoFallback) { $left | Stop-Process -Force -ErrorAction SilentlyContinue; "FALLBACK: Stop-Process on the above (not a clean stop)" }
