<#
  armor-authority-test.ps1 - decide which armor representation the game actually READS.

  RUN THIS AT THE PHYSICAL MONITOR, not over RDP (the game's 3D will not init over RDP, so
  nothing can be written or observed - see AGENTS.md). Start any mission first, then run.

  Offline snapshot analysis (docs/ARMOR-INVESTIGATION.md) located armor inside the player entity
  as integer tenths (720 = 72.0), in TWO byte-identical lockstep copies plus an external mirror
  that was already proven downstream. This picks the authority by writing a distinctive value to
  each copy in turn and reporting whether it STICKS (is not overwritten next frame) and whether
  the HUD damage panel follows.

  Current[8] = ARMOR[F,L,R,Rear] then CHASSIS[F,L,R,Rear], integer tenths. Two lockstep copies:
      copy A current  +0x138 .. +0x154      copy A max  +0x158 .. +0x174
      copy B current  +0x178 .. +0x198      copy B max  +0x198 .. (+0x40 from A)

  Phases (watch the on-screen DAMAGE panel during each):
    1. damage copy A only  -> all 8 components to 100 (10.0). Does the HUD show damage? Does it stick?
    2. damage copy B only  -> same.
    3. full repair         -> set every current = its max in BOTH copies. Does the car heal?
  Every phase reverts what it wrote when it ends.
#>
param(
    [int]$Value = 100,        # tenths to write in the damage phases (100 = 10.0 armour)
    [double]$HoldSeconds = 4,
    [switch]$SkipRepair,
    [switch]$AnyInstall       # attach to whichever i76.exe is running, not just the sandbox.
                              # Memory-only in either case - no game files are touched. The
                              # offsets are for the Gold exe (MD5 60ABF7BC...), which both the
                              # sandbox and the playable install are.
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\..\autotest\lib\memlib.ps1"

# all 8 current components (ARMOR x4 then CHASSIS x4) for each copy, and copy A's max array
$FACES_A = @(0x138, 0x13C, 0x140, 0x144, 0x148, 0x14C, 0x150, 0x154)
$FACES_B = $FACES_A | ForEach-Object { $_ + 0x40 }
$MAX_A   = @(0x158, 0x15C, 0x160, 0x164, 0x168, 0x16C, 0x170, 0x174)
$MAX_B   = $MAX_A | ForEach-Object { $_ + 0x40 }

$ctx = Mem-Open -Write -RequirePath $(if ($AnyInstall) { '' } else { 'i76-uncap-lab' })
if (-not (Mem-InMission $ctx)) { throw "not in a mission - start one at the console first" }
Write-Host ("attached to {0} (pid {1})" -f $ctx.Proc.Path, $ctx.Proc.Id) -ForegroundColor DarkGray
$ent = Mem-PlayerEntity $ctx
Write-Host ("player entity @ 0x{0:X}" -f $ent) -ForegroundColor Cyan

function Read-Faces($label, $offs) {
    $v = $offs | ForEach-Object { Mem-I32 $ctx ($ent + $_) }
    Write-Host ("  {0}: {1}" -f $label, ($v -join ', '))
    return $v
}
function Write-Faces($offs, $val) { foreach ($o in $offs) { Mem-WriteI32 $ctx ($ent + $o) $val } }

Write-Host "`n== baseline ==" -ForegroundColor Yellow
$origA = Read-Faces "copy A current" $FACES_A
$origB = Read-Faces "copy B current" $FACES_B
$maxA  = Read-Faces "copy A max    " $MAX_A
Read-Faces "copy B max    " $MAX_B | Out-Null

function Hold-And-Check($name, $offs, $val, $orig) {
    Write-Host "`n== $name -> writing $val, hold ${HoldSeconds}s. WATCH THE DAMAGE PANEL ==" -ForegroundColor Yellow
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $stuck = $true
    while ($sw.Elapsed.TotalSeconds -lt $HoldSeconds) {
        Write-Faces $offs $val
        Start-Sleep -Milliseconds 200
        $now = $offs | ForEach-Object { Mem-I32 $ctx ($ent + $_) }
        if (($now | Where-Object { $_ -ne $val }).Count -gt 0) { $stuck = $false }
    }
    # read once more WITHOUT re-writing, to see if the engine overwrites it next frames
    Start-Sleep -Milliseconds 400
    $after = $offs | ForEach-Object { Mem-I32 $ctx ($ent + $_) }
    Write-Host ("  held value stuck while writing: {0}" -f $stuck)
    Write-Host ("  value 400ms after releasing   : {0}  (reverted => downstream/mirror)" -f ($after -join ', '))
    # revert
    for ($i = 0; $i -lt $offs.Count; $i++) { Mem-WriteI32 $ctx ($ent + $offs[$i]) $orig[$i] }
    Write-Host "  reverted to baseline."
}

Hold-And-Check "PHASE 1: damage copy A" $FACES_A $Value $origA
Hold-And-Check "PHASE 2: damage copy B" $FACES_B $Value $origB

if (-not $SkipRepair) {
    Write-Host "`n== PHASE 3: full repair (both copies current=max), hold ${HoldSeconds}s. Does the car HEAL? ==" -ForegroundColor Yellow
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $HoldSeconds) {
        for ($i = 0; $i -lt $FACES_A.Count; $i++) {
            Mem-WriteI32 $ctx ($ent + $FACES_A[$i]) $maxA[$i]
            Mem-WriteI32 $ctx ($ent + $FACES_B[$i]) $maxA[$i]
        }
        Start-Sleep -Milliseconds 150
    }
    Write-Host "  repair values held. If the HUD now reads full on those faces, the entity block IS the authority."
}

Mem-Close $ctx
Write-Host "`nDone. Report: which phase changed the HUD, and whether any value reverted." -ForegroundColor Green
