<#
  memlib.ps1 — read (and optionally write) Interstate '76 game state from memory.

  Reading memory is ~1000x cheaper and faster than screenshots, and it's exact. Use this
  for all automated verification; use screenshots only when you need to see rendering.

  All addresses are Gold i76.exe (MD5 60ABF7BC...), image base 0x400000, no ASLR, so the
  static VAs below are live process addresses.

  Dot-source, then:
      $ctx = Mem-Open                    # attach to the sandbox game
      Mem-InMission $ctx                 # $true when a mission is loaded
      $p = Mem-Player $ctx               # player speed/velocity/controls
      $e = Mem-Entities $ctx             # ALL vehicles: index, position, radius
      Mem-Close $ctx
#>
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class I76Mem {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@

# ---- the map (see docs/ENGINE-LOOP-MAP.md for how each was found) --------------
$script:I76 = @{
    WorldRoot     = 0x54A264   # [[[0x54a264]]+0x70] = player entity
    EntityOffset  = 0x70
    PosTable      = 0x54E11C   # world positions, stride 0x20: [x,y,z][radius] - ALL entities
    PosStride     = 0x20
    PosSlots      = 16
    EyeXform      = 0x5FCDC4   # static transform that drives the view (pos + 3x3 matrix)
    FrameCounter  = 0x5A7E1C   # ++ once per main-loop iteration (render frame)
    # player entity struct offsets
    OffSpeed      = 0xAC       # float |velocity|
    OffVel        = 0xBC       # float3 world velocity (y at +0xC0 = FALL SPEED)
    OffAngVel     = 0xC8       # float3 angular velocity (yaw rate at +0xCC)
    OffSteer      = 0xE0       # float applied steer
    OffThrottle   = 0xE4       # float applied throttle
    # input state block (writable - lets you drive without sending keys)
    InThrottle    = 0x5367CC
    InSteer       = 0x5367D4
    InFire        = 0x5367D0
}
function Mem-Map { return $script:I76 }

function Mem-Open {
    param([string]$RequirePath = 'i76-uncap-lab', [switch]$Write)
    $cands = @(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" })
    $proc = $cands | Select-Object -First 1
    # prefer the process of the caller's -GameDir ($I76GameDirInUse, lib\gamedir.ps1); not set = first match, as before
    if ($I76GameDirInUse -and $cands.Count -gt 0) {
        $want = "$I76GameDirInUse".TrimEnd('\') + '\'
        $mine = @($cands | Where-Object { $_.Path.StartsWith($want, [StringComparison]::OrdinalIgnoreCase) })
        if ($mine.Count -gt 0) { $proc = $mine[0] }
    }
    if (-not $proc) { throw "Interstate '76 (path *$RequirePath*) is not running." }
    $access = if ($Write) { 0x38 } else { 0x10 }   # VM_OP|VM_READ|VM_WRITE : VM_READ
    $h = [I76Mem]::OpenProcess($access, $false, $proc.Id)
    if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed (same user as the game?)." }
    [pscustomobject]@{ Proc = $proc; H = $h; Buf4 = (New-Object byte[] 4) }
}
function Mem-Close { param($Ctx) if ($Ctx) { [void][I76Mem]::CloseHandle($Ctx.H) } }

function Mem-I32 { param($Ctx, [int64]$Addr)
    $n = 0
    if ([I76Mem]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $Ctx.Buf4, 4, [ref]$n) -and $n -eq 4) { [BitConverter]::ToInt32($Ctx.Buf4, 0) } else { 0 } }
function Mem-F32 { param($Ctx, [int64]$Addr)
    $n = 0
    if ([I76Mem]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $Ctx.Buf4, 4, [ref]$n) -and $n -eq 4) { [BitConverter]::ToSingle($Ctx.Buf4, 0) } else { [float]::NaN } }
function Mem-WriteI32 { param($Ctx, [int64]$Addr, [int]$Val)
    $b = [BitConverter]::GetBytes($Val); $n = 0
    [void][I76Mem]::WriteProcessMemory($Ctx.H, [IntPtr]$Addr, $b, 4, [ref]$n) }
function Mem-WriteF32 { param($Ctx, [int64]$Addr, [single]$Val)
    $b = [BitConverter]::GetBytes($Val); $n = 0
    [void][I76Mem]::WriteProcessMemory($Ctx.H, [IntPtr]$Addr, $b, 4, [ref]$n) }

# Orientation, read from the render-consumed eye transform at 0x5FCDC4:
#   [0..2] position  [3..5] right  [6..8] forward  [9..11] up  [12..14] scale
# The chassis world matrix is NOT in the entity struct (only local part transforms are), so
# this global is the only place the car's actual attitude can be read. Roll is the tilt of the
# up vector about the forward axis, measured against world-up projected perpendicular to it.
function Mem-EyeAngles {
    param($Ctx)
    $v = Mem-Floats $Ctx 0x5FCDC4 12
    if (-not $v) { return $null }
    $fx,$fy,$fz = $v[6],$v[7],$v[8]
    $ux,$uy,$uz = $v[9],$v[10],$v[11]
    $fl = [math]::Sqrt($fx*$fx + $fy*$fy + $fz*$fz)
    if ($fl -lt 0.5) { return $null }          # transform not populated this frame
    $fx/=$fl; $fy/=$fl; $fz/=$fl
    $px = -$fx*$fy; $py = 1 - $fy*$fy; $pz = -$fz*$fy
    $pl = [math]::Sqrt($px*$px + $py*$py + $pz*$pz)
    if ($pl -lt 1e-6) { return $null }
    $px/=$pl; $py/=$pl; $pz/=$pl
    $c = [math]::Max(-1.0, [math]::Min(1.0, ($ux*$px + $uy*$py + $uz*$pz)))
    $sx = $py*$fz - $pz*$fy; $sy = $pz*$fx - $px*$fz; $sz = $px*$fy - $py*$fx
    $sign = if (($ux*$sx + $uy*$sy + $uz*$sz) -lt 0) { -1 } else { 1 }
    $R = 180.0 / [math]::PI
    [pscustomobject]@{
        Pitch = [math]::Asin([math]::Max(-1.0,[math]::Min(1.0,$fy))) * $R
        Yaw   = [math]::Atan2($fx, $fz) * $R
        Roll  = $sign * [math]::Acos($c) * $R
        PX = $v[0]; PY = $v[1]; PZ = $v[2]
    }
}

# Bulk read. Reading a matrix one float at a time takes a dozen separate calls spread over
# several milliseconds, so a moving camera is half-updated by the time the last one lands and
# the "matrix" comes back non-orthonormal. Always read a struct in ONE call.
function Mem-Floats {
    param($Ctx, [int64]$Addr, [int]$Count)
    $b = New-Object byte[] ($Count * 4); $n = 0
    if (-not ([I76Mem]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $b, $b.Length, [ref]$n)) -or $n -ne $b.Length) { return $null }
    $v = New-Object double[] $Count
    for ($i = 0; $i -lt $Count; $i++) { $v[$i] = [BitConverter]::ToSingle($b, $i * 4) }
    return $v
}

function Mem-PlayerEntity { param($Ctx)
    $w = Mem-I32 $Ctx $script:I76.WorldRoot; if (-not $w) { return 0 }
    $s = Mem-I32 $Ctx $w;                    if (-not $s) { return 0 }
    return (Mem-I32 $Ctx ($s + $script:I76.EntityOffset)) }
function Mem-InMission { param($Ctx) return ((Mem-PlayerEntity $Ctx) -ne 0) }

function Mem-Player {
    param($Ctx)
    $e = Mem-PlayerEntity $Ctx
    if (-not $e) { return $null }
    [pscustomobject]@{
        Entity   = $e
        Speed    = Mem-F32 $Ctx ($e + $script:I76.OffSpeed)
        VX       = Mem-F32 $Ctx ($e + $script:I76.OffVel)
        VY       = Mem-F32 $Ctx ($e + $script:I76.OffVel + 4)   # fall speed
        VZ       = Mem-F32 $Ctx ($e + $script:I76.OffVel + 8)
        YawRate  = Mem-F32 $Ctx ($e + $script:I76.OffAngVel + 4)
        Steer    = Mem-F32 $Ctx ($e + $script:I76.OffSteer)
        Throttle = Mem-F32 $Ctx ($e + $script:I76.OffThrottle)
        X        = Mem-F32 $Ctx $script:I76.PosTable
        Y        = Mem-F32 $Ctx ($script:I76.PosTable + 4)
        Z        = Mem-F32 $Ctx ($script:I76.PosTable + 8)
        Frame    = Mem-I32 $Ctx $script:I76.FrameCounter
    }
}

# Every vehicle/object in the world. Slot 0 is the player; others are AI cars etc.
function Mem-Entities {
    param($Ctx, [switch]$IncludeEmpty)
    $out = @()
    for ($i = 0; $i -lt $script:I76.PosSlots; $i++) {
        $va = $script:I76.PosTable + $i * $script:I76.PosStride
        $x = Mem-F32 $Ctx $va; $y = Mem-F32 $Ctx ($va + 4); $z = Mem-F32 $Ctx ($va + 8); $r = Mem-F32 $Ctx ($va + 12)
        $live = -not ([double]::IsNaN($x)) -and ([math]::Abs($x) -gt 0.01 -or [math]::Abs($z) -gt 0.01)
        if ($live -or $IncludeEmpty) {
            $out += [pscustomobject]@{ Index = $i; VA = ('0x{0:X}' -f $va); X = $x; Y = $y; Z = $z; Radius = $r; Live = $live }
        }
    }
    return $out
}
function Mem-Distance { param($A, $B) [math]::Sqrt((($A.X-$B.X)*($A.X-$B.X)) + (($A.Y-$B.Y)*($A.Y-$B.Y)) + (($A.Z-$B.Z)*($A.Z-$B.Z))) }

# Drive by writing the input block directly (deterministic - no key timing jitter).
# throttle/steer are ints in the live input array; range roughly -128..127 (60 = centre for steer).
function Mem-SetThrottle { param($Ctx, [int]$V) Mem-WriteI32 $Ctx $script:I76.InThrottle $V }
function Mem-SetSteer    { param($Ctx, [int]$V) Mem-WriteI32 $Ctx $script:I76.InSteer $V }
