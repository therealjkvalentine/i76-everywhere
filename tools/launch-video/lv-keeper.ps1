# lv-keeper.ps1 - keeps the game window at X,Y W x H for the life of the game (the exe sizes its popup to the whole screen at
# start and on mode changes). The same loop as PLAY-i76.ps1's -Windowed keeper, but the position is held too (the capture
# region is fixed). Started hidden by record-shot.ps1.
param([int]$GamePid, [int]$X = 0, [int]$Y = 0, [int]$W = 1920, [int]$H = 1080)
Add-Type -Namespace LvW -Name U -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
public delegate bool EnumProc(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
public struct RECT { public int L, T, R, B; }
"@
$p = Get-Process -Id $GamePid -ErrorAction SilentlyContinue
while ($p -and -not $p.HasExited) {
    $script:best = [IntPtr]::Zero; $script:area = 0; $script:rb = $null
    $cb = [LvW.U+EnumProc]{ param($h, $l)
        $o = 0; [void][LvW.U]::GetWindowThreadProcessId($h, [ref]$o)
        if ($o -eq $GamePid -and [LvW.U]::IsWindowVisible($h)) {
            $r = New-Object LvW.U+RECT; [void][LvW.U]::GetWindowRect($h, [ref]$r)
            $a = ($r.R - $r.L) * ($r.B - $r.T)
            if ($a -gt $script:area) { $script:area = $a; $script:best = $h; $script:rb = $r }
        }
        $true }
    [void][LvW.U]::EnumWindows($cb, [IntPtr]::Zero)
    if ($script:best -ne [IntPtr]::Zero) {
        $rb = $script:rb
        if ($rb.L -ne $X -or $rb.T -ne $Y -or ($rb.R - $rb.L) -ne $W -or ($rb.B - $rb.T) -ne $H) {
            [void][LvW.U]::SetWindowPos($script:best, [IntPtr]::Zero, $X, $Y, $W, $H, 0x0014)   # NOZORDER | NOACTIVATE
        }
    }
    Start-Sleep -Milliseconds 250
}
