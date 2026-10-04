<#
  find-weapon-slots.ps1 — locate the player's equipped-weapon slots in memory.

  Two-level search, because slots do NOT hold pointers to the static definition table (checked:
  zero hits in the entity and the logic object). The live form is a per-weapon INSTANCE object
  on the heap; the slot points at that, and the instance is what links back to the definition.

  So: for every plausible heap pointer in the player's structures, follow it and ask "does the
  target look like a weapon instance?" - i.e. does it contain a pointer into the definition
  table, or an ASCII name matching one of the definitions loaded this mission.

  Window sizes are deliberately generous: an older note guessed weapon arrays at logic +0xa71c,
  which is past a 0x4000 scan, so a short window would have silently missed them.
#>
param(
    [int]$EntityBytes = 0x2000,
    [int]$LogicBytes  = 0x14000,
    [int64]$TableBase = 0x5D8800,
    [int]$Stride      = 0xD8,
    [int]$MaxRecords  = 64,
    [int]$ProbeBytes  = 0x200
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System; using System.Runtime.InteropServices;
public class WS2 {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int c);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$proc = Get-Process i76 -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { throw "i76 not running" }
$h = [WS2]::OpenProcess(0x410, $false, $proc.Id)
function RdBlk([int64]$a, [int]$n) { $b = New-Object byte[] $n; $r = 0
    if (-not [WS2]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r)) { return $null }
    if ($r -lt $n) { return $null }; return $b }
function Rd32([int64]$a) { $b = RdBlk $a 4; if ($null -eq $b) { return 0 }; return [BitConverter]::ToInt32($b,0) }
function StrAt($buf, [int]$off, [int]$max = 20) {
    $s = ''
    for ($i = $off; $i -lt [math]::Min($off+$max, $buf.Length); $i++) {
        $c = $buf[$i]; if ($c -eq 0) { break }
        if ($c -lt 32 -or $c -gt 126) { return '' }; $s += [char]$c }
    return $s }

# definitions loaded this mission
$defs = @{}; $names = @{}
for ($i = 0; $i -lt $MaxRecords; $i++) {
    $va = $TableBase + $i * $Stride
    $b = RdBlk $va 24; if ($null -eq $b) { continue }
    $n = StrAt $b 0; if (-not $n) { continue }
    $defs[[int64]$va] = $n; $names[$n] = $true
}
Write-Host "definitions loaded: $($defs.Count)" -ForegroundColor Cyan
$lo = $TableBase; $hi = $TableBase + $MaxRecords * $Stride

$player = Rd32 ((Rd32 (Rd32 0x54A264)) + 0x70)
$logic  = Rd32 ($player + 0x108)
Write-Host "player=0x$('{0:X}' -f $player)  logic=0x$('{0:X}' -f $logic)" -ForegroundColor Cyan

# does an address look like a live weapon instance?
function Classify([int64]$addr) {
    $b = RdBlk $addr $ProbeBytes
    if ($null -eq $b) { return $null }
    $why = @()
    for ($o = 0; $o -lt ($ProbeBytes - 4); $o += 4) {
        $v = [BitConverter]::ToInt32($b, $o)
        if ($v -ge $lo -and $v -lt $hi -and $defs.ContainsKey([int64]$v)) {
            $why += ("+0x{0:X}->def '{1}'" -f $o, $defs[[int64]$v]) }
    }
    for ($o = 0; $o -lt ($ProbeBytes - 4); $o += 1) {
        $s = StrAt $b $o
        if ($s.Length -ge 5 -and $names.ContainsKey($s)) { $why += ("+0x{0:X}='{1}'" -f $o, $s) }
    }
    if ($why.Count) { return ($why | Select-Object -First 4) -join ', ' }
    return $null
}

function Scan([string]$label, [int64]$base, [int]$len) {
    if ($base -eq 0) { return }
    Write-Host "`n=== $label  0x$('{0:X}' -f $base) +0x$('{0:X}' -f $len) ===" -ForegroundColor Green
    $buf = RdBlk $base $len
    if ($null -eq $buf) { Write-Host "  (unreadable)" -ForegroundColor DarkYellow; return }
    $hits = 0; $seen = @{}
    for ($o = 0; $o -lt ($len - 4); $o += 4) {
        $v = [BitConverter]::ToInt32($buf, $o)
        if ($v -le 0x00400000 -or $v -ge 0x40000000) { continue }   # plausible heap pointer only
        if ($seen.ContainsKey($v)) { continue }
        $c = Classify $v
        if ($c) { $seen[$v] = $true
            "  +0x{0:X4} -> 0x{1:X8}   {2}" -f $o, $v, $c
            $hits++ }
    }
    if ($hits -eq 0) { Write-Host "  (nothing that dereferences to a weapon-like object)" -ForegroundColor DarkYellow }
}
Scan 'PLAYER ENTITY' $player $EntityBytes
Scan 'VEHICLE LOGIC' $logic  $LogicBytes
[void][WS2]::CloseHandle($h)
