<#
  ffb-watch-effects.ps1 - watch the engine's OWN force feedback decisions live.

  This reads the game's effect requests at the source, instead of guessing at
  them from input flags.

      tools\ffb\ffb-watch-effects.ps1              # live, with change detection
      tools\ffb\ffb-watch-effects.ps1 -Dump        # full 364-byte block, once
      tools\ffb\ffb-watch-effects.ps1 -Log fx.csv  # record every change

  ---------------------------------------------------------------------------
  HOW THIS WORKS, AND WHY IT BEATS READING AN INPUT FLAG
  ---------------------------------------------------------------------------
  I7_SFRCE.DLL exports exactly three functions: I7FF_InitSystem, I7FF_ExitSystem
  and I7FF_SIM_Effect. Every force feedback event the engine plays - weapon fire,
  explosions, tyre blowouts, engine start - goes through that ONE entry point.
  Disassembly of the dispatcher at 0x446110:

      mov  eax, [0x52bbe4]              ; the resolved I7FF_SIM_Effect pointer
      test eax, eax
      je   0x446155                     ; the engine tolerates a null pointer
      push 0x4f2328                     ; ONE argument: a parameter block
      mov  dword ptr [0x4f2328], 0x16c  ; 364 = sizeof(struct), a classic dwSize
      call eax

  So the whole FFB API surface is "fill a 364-byte struct at 0x4f2328 and call
  one function". Polling that struct therefore shows what the engine DECIDED,
  after all input handling, weapon logic and damage rules have run. An input flag
  only shows what a button did; this shows what the game concluded.

  It is also why the interposer now zeroes 0x52bbe4 rather than 0x52bbd0. Both
  stop the crash at I7_SFRCE.DLL+0x2505, but zeroing the flag made the callers
  bail before ever filling the block; zeroing the POINTER lets every effect be
  built and merely skips the call into the DLL. The engine keeps thinking; we get
  to read it.

  The four dispatch sites, from static analysis:
      0x445B58 / 0x445B76 / 0x445B98   enable / disable toggles (sustained state)
      0x445E83                          the parameter builder - reads the player
                                        entity at +0x70, so this is the per-event
                                        path where weapon and impact effects live

  Field semantics inside the block are mostly NOT yet decoded - which is exactly
  what this tool is for. Fire a weapon, blow a tyre, hit a wall, and see which
  dwords move.

  ONE FIELD IS NOW DECODED: +0x0C is ENGINE RPM (0x4f2334). Found by
  ffb-find-rpm-wide.ps1, which alternated idle/full-revs/idle/full-revs in
  neutral and watched the whole of memory: it read 1050 -> 5998 -> 1050 -> 5999
  against a dashboard tach showing roughly 1.4k -> 6.1k, and nothing else among
  794 survivors read in rpm units.

  That it lives HERE is the interesting part. This block is the game's own force
  feedback input, so the native FFB has been reading engine speed all along -
  and every scan of the vehicle entity was bound to miss it, because RPM is not
  in the entity.

  -Tach prints just that number, big and repeatedly, so it can be checked against
  the needle without the interposer taking over the wheel:

      tools\ffb\ffb-watch-effects.ps1 -Tach
#>

param(
    [switch]$Dump,
    [switch]$Tach,
    [string]$Log = "",
    [int]$HZ = 60,
    [int]$Seconds = 0
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')

$BLOCK = 0x4f2328
$SIZE  = 0x16c          # 364, the size the engine writes into the first field

$ctx = Tel-Open
Write-Host ("telemetry OK - entity 0x{0:X8}" -f $ctx.Ent) -ForegroundColor Green
$ptr = Tel-ReadInt $ctx 0x52bbe4
Write-Host ("I7FF_SIM_Effect pointer (0x52bbe4) = 0x{0:X8}  {1}" -f $ptr,
    $(if ($ptr -eq 0) { "- bypassed, so effects are BUILT but not played (safe)" }
      else { "- LIVE, the DLL will be called" })) -ForegroundColor $(if ($ptr -eq 0) { 'Green' } else { 'Yellow' })
if ($ptr -ne 0) {
    Write-Host "  Firing with the interposer holding the wheel will crash the game." -ForegroundColor Yellow
    Write-Host "  Run the interposer first (it bypasses the call), or do not fire." -ForegroundColor Yellow
}
Write-Host ""

$buf = New-Object byte[] $SIZE
$n = 0
if (-not [I76Tel]::ReadProcessMemory($ctx.H, [IntPtr]$BLOCK, $buf, $SIZE, [ref]$n)) {
    Write-Host "could not read the parameter block" -ForegroundColor Red; exit 1
}

if ($Dump) {
    Write-Host ("=== 0x{0:X6} .. 0x{1:X6} ({2} bytes) ===" -f $BLOCK, ($BLOCK+$SIZE), $SIZE) -ForegroundColor Cyan
    for ($o = 0; $o -lt $SIZE; $o += 16) {
        $line = "  +0x{0:X3}  " -f $o
        for ($k = 0; $k -lt 16 -and ($o+$k) -lt $SIZE; $k += 4) {
            $line += ("{0,11} " -f [BitConverter]::ToInt32($buf, $o+$k))
        }
        $line += "  |  "
        for ($k = 0; $k -lt 16 -and ($o+$k) -lt $SIZE; $k += 4) {
            $line += ("{0,10:0.###} " -f [BitConverter]::ToSingle($buf, $o+$k))
        }
        Write-Host $line
    }
    Tel-Close $ctx; return
}

# ---- -Tach: just the number, so the needle can confirm it ------------------
# RPM was identified by a memory scan rather than a decompile, so the dashboard
# tachometer is the only thing that can actually verify it. This reads the same
# block as everything else here and never opens the wheel, so it can run
# alongside a normal game session with no risk of holding the FFB device.
if ($Tach) {
    Write-Host "Live RPM from 0x4f2334 (block +0x0C). Compare with the dashboard tach." -ForegroundColor Yellow
    Write-Host "Ctrl+C to stop." -ForegroundColor Yellow
    Write-Host ""
    $lo = [int]::MaxValue; $hi = [int]::MinValue
    while ($true) {
        $n2 = 0
        if ([I76Tel]::ReadProcessMemory($ctx.H, [IntPtr]$BLOCK, $buf, $SIZE, [ref]$n2)) {
            $rpm = [BitConverter]::ToInt32($buf, 0x0C)
            if ($rpm -ge 0 -and $rpm -le 20000) {
                if ($rpm -lt $lo) { $lo = $rpm }
                if ($rpm -gt $hi) { $hi = $rpm }
                # A bar as well as the number: a needle is easier to compare
                # against something that also sweeps.
                $bars = [int]([math]::Min(1.0, $rpm / 7000.0) * 50)
                Write-Host ("`r  {0,5} rpm  [{1}{2}]  seen {3}..{4}   " -f `
                    $rpm, ('#' * $bars), ('.' * (50 - $bars)), $lo, $hi) -NoNewline
            }
        }
        Start-Sleep -Milliseconds ([int](1000 / $HZ))
    }
}

$prev = $buf.Clone()
$hits = @{}
$sw = New-Object System.IO.StreamWriter($Log, $false) -ErrorAction SilentlyContinue
if ($Log) { $sw.WriteLine("t,offset,oldInt,newInt,oldFloat,newFloat") }

Write-Host "WATCHING. Do things and see what moves:" -ForegroundColor Yellow
Write-Host "  fire a weapon   drop a mine   hit a wall   blow a tyre   handbrake slide" -ForegroundColor Yellow
Write-Host "Ctrl+C to stop. A summary prints on exit." -ForegroundColor Yellow
Write-Host ""

$clock = [System.Diagnostics.Stopwatch]::StartNew()
try {
    while ($true) {
        if ($Seconds -gt 0 -and $clock.Elapsed.TotalSeconds -gt $Seconds) { break }
        if ($ctx.Proc.HasExited) { Write-Host "`nthe game exited." -ForegroundColor Cyan; break }
        if ([I76Tel]::ReadProcessMemory($ctx.H, [IntPtr]$BLOCK, $buf, $SIZE, [ref]$n)) {
            for ($o = 0; $o -lt $SIZE; $o += 4) {
                $a = [BitConverter]::ToInt32($prev, $o)
                $c = [BitConverter]::ToInt32($buf, $o)
                if ($a -eq $c) { continue }
                # +0x000 is the dwSize the engine rewrites every call - constant noise
                if ($o -eq 0) { continue }
                $fa = [BitConverter]::ToSingle($prev, $o); $fc = [BitConverter]::ToSingle($buf, $o)
                $t = $clock.Elapsed.TotalSeconds
                if (-not $hits.ContainsKey($o)) { $hits[$o] = 0 }
                $hits[$o]++
                Write-Host ("  {0,7:0.00}s  +0x{1:X3}   {2,12} -> {3,-12}   ({4:0.###} -> {5:0.###})" -f `
                    $t, $o, $a, $c, $fa, $fc)
                if ($Log) { $sw.WriteLine("$([math]::Round($t,3)),$o,$a,$c,$fa,$fc") }
            }
            [Array]::Copy($buf, $prev, $SIZE)
        }
        Start-Sleep -Milliseconds ([int](1000 / $HZ))
    }
}
finally {
    if ($Log -and $sw) { $sw.Flush(); $sw.Close(); Write-Host "log -> $Log" -ForegroundColor Cyan }
    Write-Host ""
    if ($hits.Count) {
        Write-Host "=== fields that changed, by how often ===" -ForegroundColor Green
        foreach ($o in ($hits.Keys | Sort-Object { -$hits[$_] })) {
            Write-Host ("  +0x{0:X3}   {1} changes" -f $o, $hits[$o])
        }
        Write-Host ""
        Write-Host "A field that changes ONCE PER SHOT is the weapon trigger. One that" -ForegroundColor Gray
        Write-Host "changes continuously is a sustained effect (engine rumble, surface)." -ForegroundColor Gray
    } else {
        Write-Host "Nothing changed. Either no effect fired, or the engine's FFB never" -ForegroundColor Yellow
        Write-Host "initialised this session - check that 0x52bbdc is non-zero in a mission." -ForegroundColor Yellow
    }
    Tel-Close $ctx
}
