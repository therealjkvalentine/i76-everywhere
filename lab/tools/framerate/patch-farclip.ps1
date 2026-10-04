<#
  patch-farclip.ps1 — extend the draw distance (far clip) AND enlarge the render pools it needs.

  WHAT WAS FOUND (docs/DRAW-DISTANCE.md in i76-everywhere):
    * Every mission's .MSN carries a far-clip field in its WDEF/WRLD chunk (u32 at WRLD+0x13F);
      ALL stock missions say 600. The official mission-builder manual: "Typically the far clip
      distance is set to 600, which is the recommended distance."
    * The WRLD parser (0x4B8A10) does `fild [WRLD+0x13F]` / `fstp [0x4C271C]` — one global.
    * ONE reader: the projection setup at 0x4059DE does `mov eax,[0x4C271C]` and builds the
      camera with near=1.0, far=THAT, FOV=90°. The camera constructor (0x472220) clamps far to
      [100 .. 100000]. `mov eax,[imm]` and `mov eax,imm32` are the same 5 bytes -> in-place patch.
    * THE CRASH CEILING: the render pipeline bump-allocates 12-byte records from a fixed pool
      with NO bounds check (the bump at 0x491A11 is where 0xc0000005 fires). Pools, allocated
      once at renderer init (0x402F98..0x402FD9 via the VirtualAlloc wrapper 0x498940):
         [0x5DD320]  0x1A5E0 bytes, split at +0xD2F0 (two transformed-vertex halves)
         [0x5DD324]  0x80000 bytes  (the 12-byte record arena; cursor [0x654380])
      Measured (training desert): far=600 uses 20,720 arena bytes; far=1800 uses 53,704
      (sub-linear growth — terrain LOD). BUT the menu ATTRACT scene at far=5000 needed
      >585,736 bytes and crashed the stock 512K pool (peak read live at death; count 44,237
      ~= the exact 43,690-record capacity). So any far override also enlarges the pools 16x.

  Patched bytes (file offset = VA - 0x400C00), all verified unique:
      0x2399  alloc1 arg2   0x40000 -> 0x400000
      0x239E  alloc1 size   0x1A5E0 -> 0x1A5E00     (16x)
      0x23C6  half marker   0xD2F0  -> 0xD2F00      (16x, must match alloc1 scaling)
      0x23CB  arena arg2    0x80000 -> 0x800000     (16x)
      0x23D0  arena size    0x80000 -> 0x800000     (16x)
      0x4DDE  far-clip read A1 1C 27 4C 00 -> B8 <float FarMeters>

  Usage (SANDBOX FIRST):
    tools\framerate\patch-farclip.ps1 -GameDir <dir> -FarMeters 1800
    tools\framerate\patch-farclip.ps1 -GameDir <dir> -Restore     # stock everything
    tools\framerate\patch-farclip.ps1 -GameDir <dir> -Status
#>
param(
    [Parameter(Mandatory = $true)][string]$GameDir,
    [double]$FarMeters = 1800,
    [int]$PoolMultiplier = 0,     # 0 = auto-scale from FarMeters (see below)
    [switch]$Restore,
    [switch]$Status
)
$ErrorActionPreference = 'Stop'
$exe  = Join-Path $GameDir 'i76.exe'
$orig = "$exe.farorig"

$FO_FAR = 0x4DDE
$STOCK_FAR = [byte[]](0xA1, 0x1C, 0x27, 0x4C, 0x00)   # mov eax, [0x4C271C]

# Pool cost does NOT grow linearly with distance (measured, training desert):
#   far  600 -> 20,720 B   1800 -> 53,704 B (2.6x for 3x)   5000 -> 648,508 B (12x for 2.8x)
# It accelerates at range, so the multiplier scales with FarMeters rather than sitting at 16x.
# These are VirtualAlloc-backed, so even 64x is trivial (arena 512K -> 32M) on any modern box.
if ($PoolMultiplier -le 0) {
    $PoolMultiplier = if     ($FarMeters -le 2000)  { 16 }
                      elseif ($FarMeters -le 6000)  { 32 }
                      elseif ($FarMeters -le 15000) { 64 }
                      else                          { 128 }
}
# {fileOffset, stockValue} - enlarged value is stock * PoolMultiplier
$POOLS = @(
    @{ off = 0x2399; stock = 0x40000 },   # alloc1 arg2
    @{ off = 0x239E; stock = 0x1A5E0 },   # alloc1 size
    @{ off = 0x23C6; stock = 0xD2F0  },   # half marker (must scale WITH alloc1)
    @{ off = 0x23CB; stock = 0x80000 },   # arena arg2
    @{ off = 0x23D0; stock = 0x80000 }    # arena size
)
foreach ($p in $POOLS) { $p.big = [uint32]($p.stock * $PoolMultiplier) }

if (-not (Test-Path $exe)) { throw "i76.exe not found in $GameDir" }
$bytes = [IO.File]::ReadAllBytes($exe)

function RdU32([int]$o) { [BitConverter]::ToUInt32($bytes, $o) }
function WrU32([int]$o, [uint32]$v) { $b=[BitConverter]::GetBytes($v); for($j=0;$j -lt 4;$j++){ $script:bytes[$o+$j]=$b[$j] } }

$farCur = $bytes[$FO_FAR..($FO_FAR+4)]

# current multiplier = value/stock, and it must be the SAME whole number on every field
function CurrentMultiplier {
    $ms = foreach ($p in $POOLS) {
        $v = RdU32 $p.off
        if ($v -lt $p.stock -or ($v % $p.stock) -ne 0) { return $null }
        [int]($v / $p.stock)
    }
    if (($ms | Select-Object -Unique).Count -eq 1) { $ms[0] } else { $null }
}

function Describe {
    $far = if ($farCur[0] -eq 0xA1) { "STOCK (mission value; all stock missions = 600)" }
           elseif ($farCur[0] -eq 0xB8) { "PATCHED -> {0} m" -f [BitConverter]::ToSingle($farCur,1) }
           else { "UNRECOGNIZED" }
    $m = CurrentMultiplier
    $pool = if ($null -eq $m) { "MIXED/UNRECOGNIZED - restore before re-patching" }
            elseif ($m -eq 1) { "stock (512K arena)" }
            else { "ENLARGED {0}x (arena {1:N0} MB)" -f $m, (0x80000 * $m / 1MB) }
    "far-clip: $far`nrender pools: $pool"
}

if ($Status) { Describe; exit 0 }

if (Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$GameDir*" }) {
    throw "the game in $GameDir is running - close it first"
}

if ($Restore) {
    for ($j = 0; $j -lt 5; $j++) { $bytes[$FO_FAR + $j] = $STOCK_FAR[$j] }
    foreach ($p in $POOLS) { WrU32 $p.off $p.stock }
    [IO.File]::WriteAllBytes($exe, $bytes)
    "restored: stock far-clip read (600) + stock pool sizes"
    exit 0
}

if ($FarMeters -lt 100 -or $FarMeters -gt 100000) {
    throw "FarMeters must be within the engine's own clamp range 100..100000"
}
if ($null -eq (CurrentMultiplier)) {
    throw "render-pool constants are not a consistent multiple of stock - run -Restore first"
}
if (-not (($farCur[0] -eq 0xA1) -or ($farCur[0] -eq 0xB8))) { throw "unexpected bytes at the far-clip read - wrong exe variant?" }
if (-not (Test-Path $orig)) { Copy-Item $exe $orig; "backed up -> i76.exe.farorig" }

foreach ($p in $POOLS) { WrU32 $p.off $p.big }
$imm = [BitConverter]::GetBytes([single]$FarMeters)
$bytes[$FO_FAR] = 0xB8
for ($j = 0; $j -lt 4; $j++) { $bytes[$FO_FAR + 1 + $j] = $imm[$j] }
[IO.File]::WriteAllBytes($exe, $bytes)
("patched: far clip -> {0} m, render pools {1}x (arena {2:N0} MB)" -f [single]$FarMeters, $PoolMultiplier, (0x80000 * $PoolMultiplier / 1MB))
