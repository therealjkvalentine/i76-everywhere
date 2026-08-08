<#
  CH Products Fighterstick -> Interstate '76.

  WHAT THIS IS. A HOTAS layer for a 1997 driving game. The stick's BUTTONS follow
  F-16 grip convention (trigger fires, castle hat looks around, the 4-way hats do
  target and display management), and the stick's own DEFLECTION becomes the
  gearbox and the handbrake:

      push forward   -> shift up          (sequential gate: recentre between shifts)
      pull back      -> shift down
      yank left      -> handbrake         (held while deflected)
      push right     -> reverse

  WHY A SEPARATE TOOL, rather than input.map. The engine's binding file maps an
  analog axis only to an ANALOG sink - `steer` and `throttle`. There is no syntax
  for "when this axis passes 60%, press a button", so an axis can never drive
  shift_up. That conversion has to happen outside the engine, which is what this
  is: read the stick through winmm, synthesise the keystroke the game already
  binds. It needs no change to input.map at all.

  Synthesising KEYSTROKES rather than feeding a virtual joystick also sidesteps
  an open question - whether this 1997 engine polls a SECOND winmm joystick at
  all. The wheel is joystick1; the game may never look at joystick2. Keys are
  read the same way no matter which device produced them, so this works either
  way, and the wheel keeps joystick1 to itself for steering, pedals and FFB.

  Usage:
      tools\fighterstick.ps1                 # run it (game should be focused)
      tools\fighterstick.ps1 -Learn          # press buttons; prints their numbers
      tools\fighterstick.ps1 -WhatIf         # show actions, send no keys
      tools\fighterstick.ps1 -Device 3       # if the stick is not joystick2

  The button NUMBERS below are CH's documented default layout, not measured on
  this unit - the CH mode switch also renumbers everything. If a button does the
  wrong thing, run -Learn and correct the table; it is a plain hashtable at the
  top of this file.
#>
param(
    # winmm device, 1-based like input.map's joystickN. The Fighterstick enumerated
    # as joystick2 here (VID 068E / PID 00F3); the T300 wheel is joystick1.
    [int]$Device = 2,
    [switch]$Learn,
    [switch]$WhatIf,
    # Deflection needed to trigger, as a fraction from centre. Release happens at
    # RelFrac - the gap between them is the hysteresis, and without it a stick
    # resting near the threshold machine-guns the action.
    [double]$Threshold = 0.55,
    [double]$RelFrac   = 0.35,
    [int]$Hz = 60,
    # Exercise the axis state machine and the normalisation without the stick.
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)]
public struct JOYCAPS {
  public ushort wMid, wPid;
  [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string szPname;
  public uint wXmin,wXmax,wYmin,wYmax,wZmin,wZmax,wNumButtons,wPeriodMin,wPeriodMax;
  public uint wRmin,wRmax,wUmin,wUmax,wVmin,wVmax,wCaps,wMaxAxes,wNumAxes,wMaxButtons;
  [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)]  public string szRegKey;
  [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)] public string szOEMVxD;
}
[StructLayout(LayoutKind.Sequential)]
public struct JOYINFOEX {
  public int dwSize, dwFlags, dwXpos, dwYpos, dwZpos, dwRpos, dwUpos, dwVpos;
  public int dwButtons, dwButtonNumber, dwPOV, dwReserved1, dwReserved2;
}
public class FS {
  [DllImport("winmm.dll")] public static extern uint joyGetDevCapsA(int id, ref JOYCAPS c, int cb);
  [DllImport("winmm.dll")] public static extern uint joyGetPosEx(int id, ref JOYINFOEX i);
  // keybd_event, not SendInput: no struct marshalling to get wrong across 32/64-bit,
  // and it is the path a 1997 DirectInput title is most likely to see.
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
'@

# --- keys -------------------------------------------------------------------
# SCAN CODES, not virtual keys. A 1997 engine reading DirectInput sees scan codes;
# VK injection is the thing that silently does nothing in games of this era.
# `ext` marks the grey/extended cluster - the arrow keys the game calls GreyUpArrow
# and friends are the dedicated cluster, NOT the numpad, and they need the 0xE0
# prefix or the game reads them as numpad digits instead.
$SCAN = @{
    Enter=0x1C; Tab=0x0F; Space=0x39; Period=0x34; Comma=0x33; Esc=0x01
    A=0x1E; B=0x30; D=0x20; E=0x12; G=0x22; I=0x17; K=0x25; M=0x32; N=0x31
    P=0x19; Q=0x10; R=0x13; S=0x1F; T=0x14; U=0x16; V=0x2F; W=0x11; X=0x2D; Y=0x15
    One=0x02; Two=0x03; Three=0x04; Four=0x05; Five=0x06; Six=0x07; Seven=0x08; Eight=0x09
    GreyUpArrow=0x48; GreyDownArrow=0x50; GreyLeftArrow=0x4B; GreyRightArrow=0x4D
}
$EXTENDED = @('GreyUpArrow','GreyDownArrow','GreyLeftArrow','GreyRightArrow')

# --- the mapping ------------------------------------------------------------
# F-16 grip convention on the left, what I'76 calls it on the right. The key is
# whatever input.map already binds that action to, read out of the live file.
#
#   trigger        gun                  -> weapon_fire      Enter
#   pickle (thumb) weapon release       -> special1         Six
#   thumb          -                    -> weapon_cycle     Tab
#   pinky/paddle   NWS / AR disconnect  -> HONK_HORN        G
#   castle hat     view / head-look     -> pilot_glance_*   grey arrows
#   TMS  4-way     target management    -> target actions   T Y U Q
#   DMS  4-way     display management   -> map/radar/optics M R B V
#
# CH's documented default numbering: 1 trigger, 2-4 thumb buttons, then the 4-way
# hats in blocks of four. Verify with -Learn; the mode switch renumbers these.
$BUTTON = @{
     1 = 'Enter'          #  trigger        -> weapon_fire
     2 = 'Six'            #  pickle         -> special1  (rockets / special weapon)
     3 = 'Tab'            #  thumb          -> weapon_cycle
     4 = 'G'              #  pinky          -> HONK_HORN
     # --- hat 1, Target Management Switch ---
     5 = 'T'              #  TMS up         -> TARGET_NEAREST_ENEMY
     6 = 'Y'              #  TMS right      -> NEXT_TARGET
     7 = 'U'              #  TMS down       -> RESET_TARGET
     8 = 'Q'              #  TMS left       -> frontal_target
     # --- hat 2, Display Management Switch ---
     9 = 'M'              #  DMS up         -> SHOW_MAP
    10 = 'R'              #  DMS right      -> RADAR_RANGE_TOGGLE
    11 = 'V'              #  DMS down       -> toggle_cmbt_view
    12 = 'B'              #  DMS left       -> TOGGLE_BINOCULARS
    # --- hat 3, Countermeasures-position switch ---
    13 = 'Seven'          #  CMS up         -> special2
    14 = 'Eight'          #  CMS right      -> special3
    15 = 'E'              #  CMS down       -> pilot_glance_target
    16 = 'I'              #  CMS left       -> start_engine
}

# The 8-way POV ("castle") hat is head-look, exactly as it is on a real grip.
# winmm reports it in centidegrees: 0 = up, 9000 = right, 65535 = centred.
$POV = @{ Up='GreyUpArrow'; Right='GreyRightArrow'; Down='GreyDownArrow'; Left='GreyLeftArrow' }

# --- the ADC: stick deflection -> discrete actions --------------------------
# EDGE vs LEVEL is the whole design, and getting it wrong makes the stick unusable:
#
#   shift_up/shift_down are EDGE - one gearchange per movement. The stick must
#   return through the release threshold before it will shift again, which is
#   precisely how a sequential gearbox behaves: you cannot hold it forward and
#   climb through the gears.
#
#   e_brake is LEVEL - the key is held down for as long as the stick is deflected
#   and released when it recentres. A handbrake you had to tap would be useless.
$AXIS = @(
    @{ Axis='Y'; Dir=-1; Key='Period'; Mode='edge';  Name='shift_up'          }
    @{ Axis='Y'; Dir= 1; Key='Comma';  Mode='edge';  Name='shift_down'        }
    @{ Axis='X'; Dir=-1; Key='Space';  Mode='level'; Name='e_brake'           }
    @{ Axis='X'; Dir= 1; Key='X';      Mode='edge';  Name='reverse_direction' }
)

# Normalise an axis to -1..+1 using the range the DEVICE reports, not a guess.
# Defined here rather than beside the other helpers because -SelfTest runs before
# any hardware is touched and needs it.
function Get-Norm([int]$raw, [uint32]$lo, [uint32]$hi) {
    if ($hi -le $lo) { return 0.0 }
    $mid  = ($hi + $lo) / 2.0
    $half = ($hi - $lo) / 2.0
    return [Math]::Max(-1.0, [Math]::Min(1.0, ($raw - $mid) / $half))
}

# The axis state machine, kept as a PURE function of (deflection, state) so it can
# be exercised without the hardware - see -SelfTest. This is the part that is easy
# to get subtly wrong and impossible to debug halfway through a mission.
#
# Returns one of: 'down' | 'up' | 'pulse' | $null, and mutates $State.
function Step-Axis {
    param(
        [double]$Defl,      # deflection in this action's direction, -1..1
        [hashtable]$State,  # { Held = $false; Armed = $true }
        [string]$Mode,      # 'edge' | 'level'
        [double]$On,
        [double]$Off
    )
    $on  = $Defl -ge $On
    $off = $Defl -lt $Off
    if ($Mode -eq 'level') {
        if ($on -and -not $State.Held)      { $State.Held = $true;  return 'down' }
        elseif ($off -and $State.Held)      { $State.Held = $false; return 'up'   }
        return $null
    }
    # edge: one event per excursion. Re-arms only after coming back through $Off,
    # which is what stops a held-forward stick from climbing through every gear.
    if ($on -and $State.Armed)  { $State.Armed = $false; return 'pulse' }
    elseif ($off)               { $State.Armed = $true }
    return $null
}

if ($SelfTest) {
    $fail = 0
    function Check($what, $got, $want) {
        $ok = ($got -eq $want) -or ($null -eq $got -and $null -eq $want)
        if (-not $ok) { $script:fail++ }
        $tag = if ($ok) { 'ok  ' } else { 'FAIL' }
        $col = if ($ok) { 'DarkGray' } else { 'Red' }
        Write-Host ("  {0} {1,-52} got '{2}' want '{3}'" -f $tag, $what, $got, $want) -ForegroundColor $col
    }
    Write-Host "`nADC state machine" -ForegroundColor Cyan

    # EDGE - a sequential gate. One shift per movement, no repeats while held.
    $s = @{ Held = $false; Armed = $true }
    Check "edge: centred does nothing"            (Step-Axis 0.00 $s 'edge' 0.55 0.35) $null
    Check "edge: crossing threshold shifts"       (Step-Axis 0.60 $s 'edge' 0.55 0.35) 'pulse'
    Check "edge: HELD forward does NOT shift again" (Step-Axis 0.90 $s 'edge' 0.55 0.35) $null
    Check "edge: still held, still nothing"       (Step-Axis 0.70 $s 'edge' 0.55 0.35) $null
    Check "edge: inside hysteresis does not re-arm" (Step-Axis 0.45 $s 'edge' 0.55 0.35) $null
    Check "edge: back past release re-arms"       (Step-Axis 0.10 $s 'edge' 0.55 0.35) $null
    Check "edge: now it shifts again"             (Step-Axis 0.60 $s 'edge' 0.55 0.35) 'pulse'

    # LEVEL - a handbrake. Held down for as long as the stick is over.
    $s = @{ Held = $false; Armed = $true }
    Check "level: centred does nothing"           (Step-Axis 0.00 $s 'level' 0.55 0.35) $null
    Check "level: crossing pulls the key down"    (Step-Axis 0.60 $s 'level' 0.55 0.35) 'down'
    Check "level: staying over holds it"          (Step-Axis 0.95 $s 'level' 0.55 0.35) $null
    Check "level: inside hysteresis stays held"   (Step-Axis 0.45 $s 'level' 0.55 0.35) $null
    Check "level: recentring releases"            (Step-Axis 0.10 $s 'level' 0.55 0.35) 'up'
    Check "level: staying centred does nothing"   (Step-Axis 0.00 $s 'level' 0.55 0.35) $null

    Write-Host "`nAxis normalisation (device range 0-65535)" -ForegroundColor Cyan
    Check "centre reads ~0"    ([Math]::Round((Get-Norm 32768 0 65535), 2)) 0
    Check "full left  = -1"    ([Math]::Round((Get-Norm 0     0 65535), 2)) -1
    Check "full right = +1"    ([Math]::Round((Get-Norm 65535 0 65535), 2)) 1
    Check "resting 33028 is inside the deadzone" ([bool]([Math]::Abs((Get-Norm 33028 0 65535)) -lt 0.35)) $true
    Check "degenerate range does not divide by zero" (Get-Norm 100 5 5) 0

    Write-Host ""
    if ($fail) { Write-Host "$fail FAILED" -ForegroundColor Red; exit 1 }
    Write-Host "all passed" -ForegroundColor Green
    exit 0
}

# --- plumbing ---------------------------------------------------------------
$id = $Device - 1
$caps = New-Object JOYCAPS
$sz = [Runtime.InteropServices.Marshal]::SizeOf($caps)
if ([FS]::joyGetDevCapsA($id, [ref]$caps, $sz) -ne 0) {
    Write-Host "joystick$Device is not present at the winmm layer." -ForegroundColor Red
    Write-Host "  plug the stick in, or pass -Device N. Devices winmm can see:" -ForegroundColor DarkGray
    foreach ($n in 0..15) {
        $c2 = New-Object JOYCAPS
        if ([FS]::joyGetDevCapsA($n, [ref]$c2, $sz) -eq 0 -and $c2.szPname) {
            Write-Host ("    joystick{0}  {1}  ({2} buttons, {3} axes)" -f ($n+1), $c2.szPname, $c2.wNumButtons, $c2.wNumAxes)
        }
    }
    exit 1
}
Write-Host ("joystick{0}: {1} - {2} buttons, {3} axes, VID {4:X4} PID {5:X4}" -f `
    $Device, $caps.szPname, $caps.wNumButtons, $caps.wNumAxes, $caps.wMid, $caps.wPid) -ForegroundColor Green
if ($caps.wMid -eq 0x068E) { Write-Host "  CH Products device" -ForegroundColor DarkGray }

function Read-Stick {
    $j = New-Object JOYINFOEX
    $j.dwSize = [Runtime.InteropServices.Marshal]::SizeOf($j)
    $j.dwFlags = 0xFF   # JOY_RETURNALL
    if ([FS]::joyGetPosEx($id, [ref]$j) -ne 0) { return $null }
    return $j
}

function Send-Key([string]$name, [bool]$down) {
    if (-not $SCAN.ContainsKey($name)) { Write-Host "  no scan code for '$name'" -ForegroundColor Yellow; return }
    if ($WhatIf) { return }
    $flags = 0x8                                     # KEYEVENTF_SCANCODE
    if ($EXTENDED -contains $name) { $flags = $flags -bor 0x1 }
    if (-not $down)                { $flags = $flags -bor 0x2 }
    [FS]::keybd_event(0, [byte]$SCAN[$name], [uint32]$flags, [UIntPtr]::Zero)
}

# --- learn mode -------------------------------------------------------------
if ($Learn) {
    Write-Host "`nPress each control one at a time. Ctrl+C when done.`n" -ForegroundColor Cyan
    Write-Host "  (hats usually report as buttons; the castle hat reports as POV)`n" -ForegroundColor DarkGray
    $prev = 0; $prevPov = 65535
    while ($true) {
        $j = Read-Stick
        if ($j) {
            $changed = $j.dwButtons -bxor $prev
            if ($changed) {
                foreach ($b in 0..31) {
                    $mask = 1 -shl $b
                    if (($changed -band $mask) -and ($j.dwButtons -band $mask)) {
                        $mapped = if ($BUTTON.ContainsKey($b+1)) { $BUTTON[$b+1] } else { '(unmapped)' }
                        Write-Host ("  Button{0,-3} -> currently sends '{1}'" -f ($b+1), $mapped) -ForegroundColor White
                    }
                }
                $prev = $j.dwButtons
            }
            if ($j.dwPOV -ne $prevPov -and $j.dwPOV -ne 65535) {
                Write-Host ("  POV hat  {0} deg" -f ($j.dwPOV / 100)) -ForegroundColor White
                $prevPov = $j.dwPOV
            } elseif ($j.dwPOV -eq 65535) { $prevPov = 65535 }
        }
        Start-Sleep -Milliseconds 20
    }
}

# --- run --------------------------------------------------------------------
Write-Host ""
Write-Host "  stick forward/back = shift up/down    left = handbrake    right = reverse" -ForegroundColor Cyan
Write-Host ("  threshold {0:P0} on, {1:P0} off   {2} Hz" -f $Threshold, $RelFrac, $Hz) -ForegroundColor DarkGray
if ($WhatIf) { Write-Host "  -WhatIf: showing actions, sending NO keys" -ForegroundColor Yellow }
Write-Host "  Ctrl+C to stop.`n" -ForegroundColor DarkGray

$held  = @{}   # key name -> $true while we are holding it down
$state = @{}   # axis action name -> the Step-Axis state for that action
foreach ($a in $AXIS) { $state[$a.Name] = @{ Held = $false; Armed = $true } }
$prevBtn   = 0
$prevPovIx = -1
$delay     = [int](1000 / $Hz)

try {
    while ($true) {
        $j = Read-Stick
        if ($null -eq $j) { Start-Sleep -Milliseconds 200; continue }

        # --- buttons: straight through, held for as long as they are held ---
        $changed = $j.dwButtons -bxor $prevBtn
        if ($changed) {
            foreach ($b in 0..31) {
                $mask = 1 -shl $b
                if (-not ($changed -band $mask)) { continue }
                $key = $BUTTON[$b + 1]
                if (-not $key) { continue }
                $down = [bool]($j.dwButtons -band $mask)
                Send-Key $key $down
                if ($down) { Write-Host ("  Button{0} -> {1}" -f ($b+1), $key) -ForegroundColor DarkCyan }
            }
            $prevBtn = $j.dwButtons
        }

        # --- castle hat: head-look, held while deflected ---
        # 4 sectors centred on the cardinals, so the 8-way diagonals fall through
        # to whichever neighbour they are closer to rather than doing nothing.
        $povIx = -1
        if ($j.dwPOV -ne 65535 -and $j.dwPOV -ge 0) {
            $povIx = [int]([Math]::Round($j.dwPOV / 9000.0)) % 4
        }
        if ($povIx -ne $prevPovIx) {
            $names = @('Up','Right','Down','Left')
            if ($prevPovIx -ge 0) { Send-Key $POV[$names[$prevPovIx]] $false }
            if ($povIx     -ge 0) {
                Send-Key $POV[$names[$povIx]] $true
                Write-Host ("  hat {0} -> glance" -f $names[$povIx]) -ForegroundColor DarkCyan
            }
            $prevPovIx = $povIx
        }

        # --- the ADC ---
        $nx = Get-Norm $j.dwXpos $caps.wXmin $caps.wXmax
        $ny = Get-Norm $j.dwYpos $caps.wYmin $caps.wYmax
        foreach ($a in $AXIS) {
            $v = if ($a.Axis -eq 'X') { $nx } else { $ny }
            $ev = Step-Axis ($v * $a.Dir) $state[$a.Name] $a.Mode $Threshold $RelFrac
            switch ($ev) {
                'down'  { Send-Key $a.Key $true;  $held[$a.Key] = $true
                          Write-Host ("  {0} ON" -f $a.Name) -ForegroundColor Yellow }
                'up'    { Send-Key $a.Key $false; $held[$a.Key] = $false
                          Write-Host ("  {0} off" -f $a.Name) -ForegroundColor DarkGray }
                'pulse' { Send-Key $a.Key $true; Start-Sleep -Milliseconds 30; Send-Key $a.Key $false
                          Write-Host ("  {0}" -f $a.Name) -ForegroundColor Green }
            }
        }
        Start-Sleep -Milliseconds $delay
    }
}
finally {
    # Never leave a key stuck down - a held Space is a handbrake the player cannot
    # release, and it survives this script exiting.
    foreach ($k in @($held.Keys)) { if ($held[$k]) { Send-Key $k $false } }
    if ($prevPovIx -ge 0) { Send-Key $POV[@('Up','Right','Down','Left')[$prevPovIx]] $false }
    Write-Host "`nstopped; all keys released." -ForegroundColor DarkGray
}
