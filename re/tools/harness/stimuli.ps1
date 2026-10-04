<#
  stimuli.ps1 - Task 10 stimuli that carry their own proof of firing (gate G-STIM), for the console sitting.
  Task p3-harness-pause. Dot-source from a PowerShell 5.1 window in C:\Users\james\i76-map:

      . .\tools\harness\stimuli.ps1
      $s = Open-Stim -CaptureId 005-stimuli          # attach read-only to i76_pristine_fix (never spawns, H10); -Write for the positive control
      Get-Canary $s                                  # frame counter 0x5a7e1c / game time 0x5a7e74 (bss) / dt 0x4fe428 (init), one bulk read
      Read-InputBlock $s                             # the 86-channel state block 0x536770-0x536820 (bss), one bulk read (G-TORN)
      Invoke-FireHold $s -HoldMs 1500                # G-STIM: ENTER held; bytes 0x5367db/0x5367d0/0x5367de + GetAsyncKeyState + ammo delta
      Invoke-ThrottleHold $s -HoldMs 2000            # W held: int 0x5367cc / byte 0x5367d0 + entity +0xE4 (applied throttle) / +0xAC (speed)
      Invoke-SelfDestructMarker $s                   # CTRL+ALT+X (cheatlib): the ledger/respawn marker; player-entity pointer before/after (L053)
      Invoke-AmmoPositiveControl $s -Value 1234      # needs -Write: three-horizon read-back at 0x5aab28 (G-POS row; moves L060 on 58d9dec0)
      Save-Screenshot $s -Name after-fire            # maplib Capture-UI -> captures\<id>\<name>.png, md5 read back
      Close-Stim $s

  Every function appends one JSON line to captures\<id>\stimuli.jsonl and merges the same object into
  captures\<id>\manifest.json under "stimuli" (then re-reads the file and checks the count grew: H3).
  Every entry carries: the canary (frame counter, game time) before and after, every duration in ms with the
  tick estimate (G-UNITS), the raw bytes read (hex), and `stimulus_fired` with the observables that decided it
  (G-STIM). Reads are one ReadProcessMemory per struct (G-TORN); a failed read is recorded as null, never as 0.

  -DryRun on the stimulus functions skips every keyboard/mouse injection (the notepad self-test uses it; it
  also lets you rehearse the manifest path without touching the game).

  Addresses (class tags per gate A; the channel table 0x4f2860 init, 86 rows x 32 B, decoded 2026-09-05):
    0x5367cc bss int32  throttle (row 0)      0x5367d0 bss byte throttle_up (row 1)   0x5367d1 throttle_down
    0x5367d4 bss int32  steer (row 3)         0x5367d8/d9/da steer_reset/right/left
    0x5367db bss byte   weapon_fire (row 7)   0x5367dc weapon_cycle  0x5367dd weapon_link
    0x5367de bss byte   hardpoint1_fire (10)  0x5367df hardpoint2_fire ... 0x5367e2 hardpoint5_fire   0x5367e9 e_brake
    0x5aab0c bss        live ammo array, stride 0x4c, ammo at +0x1c -> slot0 0x5aab28 (L060, ported-static)
    0x54a264 bss        world root; player entity = [[[0x54a264]]+0x70]; entity +0xAC speed, +0xE0 steer, +0xE4 throttle (L033)
    0x5a7e1c bss uint32 frame counter; 0x5a7e74 bss float game time; 0x4fe428 init float dt (globals.tsv, supported)
  Bound keys (sandbox input.map, read from the blocks, never the comment header): weapon_fire = Enter (VK 0x0D) or mouse
  LeftBtn; throttle_up = W (0x57); hardpoint1_fire has NO keyboard binding in the sandbox file.
#>
$ErrorActionPreference = 'Stop'
$AutotestLib = "C:\Users\james\i76-uncap-lab\autotest\lib"
. "$AutotestLib\inputlib.ps1"
. "$AutotestLib\cheatlib.ps1"
. "$AutotestLib\focuslib.ps1"
. "$AutotestLib\maplib.ps1"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Stim {
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vk);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@

$script:StimMap = @{
    InputBase   = 0x536770; InputLen = 0xB0          # bss: rows 29.. (pilot_yaw_delta) up to menu_abort 0x536817
    Throttle    = 0x5367cc; ThrottleUp = 0x5367d0; ThrottleDown = 0x5367d1
    Steer       = 0x5367d4; SteerReset = 0x5367d8; SteerRight = 0x5367d9; SteerLeft = 0x5367da
    WeaponFire  = 0x5367db; WeaponCycle = 0x5367dc; WeaponLink = 0x5367dd
    Hardpoint1  = 0x5367de; Hardpoint2 = 0x5367df; EBrake = 0x5367e9
    AmmoBase    = 0x5aab0c; AmmoStride = 0x4c; AmmoOff = 0x1c; AmmoSlots = 16
    WorldRoot   = 0x54a264; EntityOff = 0x70; OffSpeed = 0xAC; OffSteer = 0xE0; OffThrottle = 0xE4
    FrameCounter = 0x5a7e1c; GameTime = 0x5a7e74; Dt = 0x4fe428
}
function Get-StimMap { return $script:StimMap }

# ---- attach / detach ---------------------------------------------------------------------------------
function Open-Stim {
    param([string]$CaptureId = ("stim-" + (Get-Date -Format "yyyyMMdd-HHmmss")),
          [string]$ProcName = 'i76_pristine_fix', [string]$RequirePath = 'i76-uncap-lab',
          [string]$CapturesRoot = "C:\Users\james\i76-map\captures", [switch]$Write)
    $proc = Get-Process -Name $ProcName -ErrorAction SilentlyContinue |
            Where-Object { -not $RequirePath -or ($_.Path -and $_.Path -like "*$RequirePath*") } | Select-Object -First 1
    if (-not $proc) { throw "game not running ($ProcName under *$RequirePath*); launch with tools\launch.ps1 first (agents never launch)" }
    $access = 0x410; if ($Write) { $access = 0x438 }     # QUERY|VM_READ (+VM_WRITE|VM_OPERATION)
    $h = [Stim]::OpenProcess($access, $false, $proc.Id)
    if ($h -eq [IntPtr]::Zero) { throw ("OpenProcess({0}) failed, win32 error {1}" -f $proc.Id, [Runtime.InteropServices.Marshal]::GetLastWin32Error()) }
    $dir = Join-Path $CapturesRoot $CaptureId
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $ctx = [pscustomobject]@{ Proc = $proc; H = $h; CaptureId = $CaptureId; Dir = $dir; ProcName = $ProcName
                              Write = [bool]$Write; TickMs = 48.0; ExePath = $proc.Path }
    # tick estimate from the sim's own dt when it reads sane (else the dgVoodoo FPSLimit=21 default, 47.6 ms)
    $dt = Read-F32 $ctx $script:StimMap.Dt
    if ($dt -ne $null -and $dt -gt 0.001 -and $dt -lt 1.0) { $ctx.TickMs = [math]::Round($dt * 1000.0, 2) }
    Write-Host ("attached pid {0} ({1}) capture {2}; tick estimate {3} ms; write={4}" -f $proc.Id, $proc.Path, $dir, $ctx.TickMs, $ctx.Write) -ForegroundColor Cyan
    return $ctx
}
function Close-Stim { param($Ctx) if ($Ctx -and $Ctx.H -ne [IntPtr]::Zero) { [void][Stim]::CloseHandle($Ctx.H); $Ctx.H = [IntPtr]::Zero } }

# ---- reads (one call per struct; $null on failure, never 0) -----------------------------------------
function Read-Bytes { param($Ctx, [int64]$Addr, [int]$Len)
    $b = New-Object byte[] $Len; $n = 0
    if ([Stim]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $b, $Len, [ref]$n) -and $n -eq $Len) { return ,$b }
    return $null }
function Read-I32 { param($Ctx, [int64]$Addr) $b = Read-Bytes $Ctx $Addr 4; if ($b) { [BitConverter]::ToInt32($b, 0) } else { $null } }
function Read-U32 { param($Ctx, [int64]$Addr) $b = Read-Bytes $Ctx $Addr 4; if ($b) { [BitConverter]::ToUInt32($b, 0) } else { $null } }
function Read-F32 { param($Ctx, [int64]$Addr) $b = Read-Bytes $Ctx $Addr 4; if ($b) { [BitConverter]::ToSingle($b, 0) } else { $null } }
function Hex([byte[]]$b) { if ($b) { ($b | ForEach-Object { $_.ToString('x2') }) -join '' } else { $null } }

function Get-Canary { param($Ctx)
    # 0x5a7e1c..0x5a7e78 in one read: frame counter at +0, game time at +0x58
    $b = Read-Bytes $Ctx $script:StimMap.FrameCounter 0x5c
    $frame = $null; $time = $null
    if ($b) { $frame = [BitConverter]::ToUInt32($b, 0); $time = [BitConverter]::ToSingle($b, 0x58) }
    [pscustomobject]@{ frame_counter_0x5a7e1c = $frame; game_time_0x5a7e74 = $time; dt_0x4fe428 = (Read-F32 $Ctx $script:StimMap.Dt)
                       t = (Get-Date -Format o) }
}
function Read-InputBlock { param($Ctx)
    $b = Read-Bytes $Ctx $script:StimMap.InputBase $script:StimMap.InputLen
    if (-not $b) { return $null }
    $o = { param($a) $a - $script:StimMap.InputBase }
    [pscustomobject]@{
        throttle_0x5367cc     = [BitConverter]::ToInt32($b, (& $o $script:StimMap.Throttle))
        throttle_up_0x5367d0  = [int]$b[(& $o $script:StimMap.ThrottleUp)]
        throttle_down_0x5367d1= [int]$b[(& $o $script:StimMap.ThrottleDown)]
        steer_0x5367d4        = [BitConverter]::ToInt32($b, (& $o $script:StimMap.Steer))
        steer_right_0x5367d9  = [int]$b[(& $o $script:StimMap.SteerRight)]
        steer_left_0x5367da   = [int]$b[(& $o $script:StimMap.SteerLeft)]
        weapon_fire_0x5367db  = [int]$b[(& $o $script:StimMap.WeaponFire)]
        weapon_cycle_0x5367dc = [int]$b[(& $o $script:StimMap.WeaponCycle)]
        hardpoint1_fire_0x5367de = [int]$b[(& $o $script:StimMap.Hardpoint1)]
        hardpoint2_fire_0x5367df = [int]$b[(& $o $script:StimMap.Hardpoint2)]
        e_brake_0x5367e9      = [int]$b[(& $o $script:StimMap.EBrake)]
        raw_0x5367cc_0x5367f0 = (Hex $b[(& $o 0x5367cc)..((& $o 0x5367f0) - 1)])
    }
}
function Read-Ammo { param($Ctx, [int]$Slots = 16)
    # slots 0..15 of the live ammo array in one read (0x5aab0c .. + 16*0x4c)
    $b = Read-Bytes $Ctx $script:StimMap.AmmoBase ($Slots * $script:StimMap.AmmoStride)
    if (-not $b) { return $null }
    $out = New-Object int[] $Slots
    for ($i = 0; $i -lt $Slots; $i++) { $out[$i] = [BitConverter]::ToInt32($b, $i * $script:StimMap.AmmoStride + $script:StimMap.AmmoOff) }
    return ,$out
}
function Get-PlayerEntity { param($Ctx)
    $w = Read-I32 $Ctx $script:StimMap.WorldRoot; if (-not $w) { return 0 }
    $s = Read-I32 $Ctx $w; if (-not $s) { return 0 }
    $e = Read-I32 $Ctx ($s + $script:StimMap.EntityOff); if ($e -eq $null) { return 0 }; return $e }
function Get-PlayerState { param($Ctx)
    $e = Get-PlayerEntity $Ctx
    if (-not $e) { return [pscustomobject]@{ entity = 0; speed = $null; steer = $null; throttle = $null } }
    $b = Read-Bytes $Ctx ($e + $script:StimMap.OffSpeed) ($script:StimMap.OffThrottle + 4 - $script:StimMap.OffSpeed)   # +0xAC..+0xE8 in one read
    if (-not $b) { return [pscustomobject]@{ entity = $e; speed = $null; steer = $null; throttle = $null } }
    [pscustomobject]@{ entity = $e; speed = [BitConverter]::ToSingle($b, 0)
                       steer = [BitConverter]::ToSingle($b, $script:StimMap.OffSteer - $script:StimMap.OffSpeed)
                       throttle = [BitConverter]::ToSingle($b, $script:StimMap.OffThrottle - $script:StimMap.OffSpeed) }
}
function Test-KeyDownOS([int]$Vk) { return (([Stim]::GetAsyncKeyState($Vk) -band 0x8000) -ne 0) }
function Test-GameForeground { param($Ctx) return ([Stim]::GetForegroundWindow() -eq $Ctx.Proc.MainWindowHandle) }
function Ensure-Foreground { param($Ctx)
    if (Test-GameForeground $Ctx) { return $true }
    if (-not (Test-WindowPumping $Ctx.Proc.MainWindowHandle)) { Write-Warning "game window not pumping - not focusing (H10 rule)"; return $false }
    return (Force-Foreground $Ctx.Proc.MainWindowHandle)
}

# ---- manifest lines (append-only; every write read back, H3) ---------------------------------------
function Add-ManifestEntry { param($Ctx, $Entry)
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $line = ($Entry | ConvertTo-Json -Depth 8 -Compress)
    $jsonl = Join-Path $Ctx.Dir 'stimuli.jsonl'
    [IO.File]::AppendAllText($jsonl, $line + "`n", $utf8)
    $mpath = Join-Path $Ctx.Dir 'manifest.json'
    $m = $null
    if (Test-Path $mpath) { $m = (Get-Content -Raw -Path $mpath) | ConvertFrom-Json }
    if (-not $m) { $m = [pscustomobject]@{ capture = $Ctx.CaptureId } }
    if (-not ($m.PSObject.Properties.Name -contains 'stimuli')) { $m | Add-Member -NotePropertyName stimuli -NotePropertyValue @() }
    $before = @($m.stimuli).Count
    $m.stimuli = @($m.stimuli) + @($Entry)
    [IO.File]::WriteAllText($mpath, ($m | ConvertTo-Json -Depth 12), $utf8)
    $back = (Get-Content -Raw -Path $mpath) | ConvertFrom-Json          # read-back
    $after = @($back.stimuli).Count
    if ($after -ne $before + 1) { throw "manifest read-back: stimuli count $before -> $after (expected $($before + 1))" }
    $jl = @(Get-Content -Path $jsonl).Count
    Write-Host ("manifest: {0} stimuli entries ({1} jsonl lines) -> {2}" -f $after, $jl, $mpath) -ForegroundColor DarkGray
    return $after
}
function New-Entry { param($Ctx, [string]$Kind)
    [ordered]@{ kind = $Kind; t = (Get-Date -Format o); pid = $Ctx.Proc.Id; exe = $Ctx.ExePath; tick_ms = $Ctx.TickMs
                foreground = (Test-GameForeground $Ctx); canary_before = (Get-Canary $Ctx) }
}

# ---- stimulus 1: fire-key hold (G-STIM; settles L031/C2) -------------------------------------------
function Invoke-FireHold {
    param($Ctx, [int]$Vk = 0x0D, [int]$HoldMs = 1500, [int]$SampleMs = 50, [int]$PostSamples = 4, [switch]$DryRun, [string]$Label = 'fire-hold-enter')
    $e = New-Entry $Ctx 'fire-hold'
    $e.label = $Label; $e.vk = ('0x{0:x2}' -f $Vk); $e.hold_ms = $HoldMs; $e.sample_ms = $SampleMs; $e.dry_run = [bool]$DryRun
    $e.binding = 'weapon_fire { + keyboard Enter } (sandbox input.map block; hardpoint1_fire has no keyboard binding)'
    $e.prediction = '0x5367db=1 on every held sample; 0x5367d0=0 throughout (no throttle_up pressed); 0x5367de=0; ammo slot0 decreases'
    $ammo0 = Read-Ammo $Ctx; $e.ammo_before = $ammo0
    if (-not $DryRun) { $e.focused = (Ensure-Foreground $Ctx) } else { $e.focused = $null }
    $samples = New-Object System.Collections.ArrayList
    $sw = [Diagnostics.Stopwatch]::StartNew()
    if (-not $DryRun) { Key-Down ([byte]$Vk) }
    try {
        while ($sw.Elapsed.TotalMilliseconds -lt $HoldMs) {
            if (-not $DryRun) { Key-Down ([byte]$Vk) }          # re-assert like Hold-Key (autorepeat-safe)
            $ib = Read-InputBlock $Ctx; $am = Read-Ammo $Ctx 1; $fr = Read-U32 $Ctx $script:StimMap.FrameCounter
            [void]$samples.Add([ordered]@{ ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1); held = $true
                os_key_down = (Test-KeyDownOS $Vk); frame = $fr
                fire_db = $(if ($ib) { $ib.weapon_fire_0x5367db } else { $null })
                throttle_up_d0 = $(if ($ib) { $ib.throttle_up_0x5367d0 } else { $null })
                hp1_de = $(if ($ib) { $ib.hardpoint1_fire_0x5367de } else { $null })
                ammo0 = $(if ($am) { $am[0] } else { $null }) })
            Start-Sleep -Milliseconds $SampleMs
        }
    } finally { if (-not $DryRun) { Key-Up ([byte]$Vk) } }
    for ($i = 0; $i -lt $PostSamples; $i++) {
        Start-Sleep -Milliseconds 100
        $ib = Read-InputBlock $Ctx; $am = Read-Ammo $Ctx 1; $fr = Read-U32 $Ctx $script:StimMap.FrameCounter
        [void]$samples.Add([ordered]@{ ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1); held = $false
            os_key_down = (Test-KeyDownOS $Vk); frame = $fr
            fire_db = $(if ($ib) { $ib.weapon_fire_0x5367db } else { $null })
            throttle_up_d0 = $(if ($ib) { $ib.throttle_up_0x5367d0 } else { $null })
            hp1_de = $(if ($ib) { $ib.hardpoint1_fire_0x5367de } else { $null })
            ammo0 = $(if ($am) { $am[0] } else { $null }) })
    }
    $ammo1 = Read-Ammo $Ctx; $e.ammo_after = $ammo1
    $held = @($samples | Where-Object { $_.held })
    $e.samples = $samples
    $e.n_held_samples = $held.Count
    $e.n_read_failures = @($samples | Where-Object { $_.fire_db -eq $null }).Count
    $e.os_key_seen = @($held | Where-Object { $_.os_key_down }).Count
    $e.fire_db_1_while_held = @($held | Where-Object { $_.fire_db -eq 1 }).Count
    $e.throttle_up_d0_1_while_held = @($held | Where-Object { $_.throttle_up_d0 -eq 1 }).Count
    $e.hp1_de_1_while_held = @($held | Where-Object { $_.hp1_de -eq 1 }).Count
    $e.fire_db_after_release = @($samples | Where-Object { -not $_.held } | ForEach-Object { $_.fire_db })
    $e.ammo_delta_slot0 = $(if ($ammo0 -and $ammo1) { $ammo1[0] - $ammo0[0] } else { $null })
    $e.ammo_delta_all = $(if ($ammo0 -and $ammo1) { 0..15 | ForEach-Object { $ammo1[$_] - $ammo0[$_] } } else { $null })
    $e.canary_after = Get-Canary $Ctx
    $e.frames_advanced = $(if ($e.canary_before.frame_counter_0x5a7e1c -ne $null -and $e.canary_after.frame_counter_0x5a7e1c -ne $null) { [int64]$e.canary_after.frame_counter_0x5a7e1c - [int64]$e.canary_before.frame_counter_0x5a7e1c } else { $null })
    # G-STIM verdict: the OS saw the key AND the engine's own byte followed it AND something downstream moved
    $e.stimulus_fired = (($e.os_key_seen -gt 0) -and ($e.fire_db_1_while_held -gt 0) -and (($e.ammo_delta_slot0 -ne $null -and $e.ammo_delta_slot0 -ne 0) -or ($e.ammo_delta_all -and (@($e.ammo_delta_all | Where-Object { $_ -ne 0 }).Count -gt 0))))
    $e.verdict = $(if ($DryRun) { 'dry-run (no keys sent)' }
                   elseif ($e.frames_advanced -le 0) { 'VOID: sim canary did not advance (paused/menu/unfocused)' }
                   elseif ($e.os_key_seen -eq 0) { 'VOID: GetAsyncKeyState never saw the key - injection failed' }
                   elseif ($e.fire_db_1_while_held -eq 0) { 'key seen by OS but 0x5367db never 1 - binding or focus (check input.map block, foreground)' }
                   elseif (-not $e.stimulus_fired) { 'engine byte followed the key but no ammo moved - weapon empty/no weapon selected/hold too short' }
                   else { 'fired: L031 prediction ' + $(if ($e.throttle_up_d0_1_while_held -eq 0) { 'holds (0x5367d0 stayed 0)' } else { 'CONTRADICTED (0x5367d0 went 1 with only Enter held)' }) })
    Write-Host ("fire-hold: held samples {0}, os_key {1}, db=1 {2}, d0=1 {3}, de=1 {4}, ammo0 delta {5}, frames {6} -> {7}" -f $e.n_held_samples, $e.os_key_seen, $e.fire_db_1_while_held, $e.throttle_up_d0_1_while_held, $e.hp1_de_1_while_held, $e.ammo_delta_slot0, $e.frames_advanced, $e.verdict) -ForegroundColor $(if ($e.stimulus_fired) { 'Green' } else { 'Yellow' })
    [void](Add-ManifestEntry $Ctx $e)
    return [pscustomobject]$e
}

# ---- stimulus 2: throttle hold -----------------------------------------------------------------------
function Invoke-ThrottleHold {
    param($Ctx, [int]$Vk = 0x57, [int]$HoldMs = 2000, [int]$SampleMs = 100, [switch]$DryRun, [string]$Label = 'throttle-hold-w')
    $e = New-Entry $Ctx 'throttle-hold'
    $e.label = $Label; $e.vk = ('0x{0:x2}' -f $Vk); $e.hold_ms = $HoldMs; $e.sample_ms = $SampleMs; $e.dry_run = [bool]$DryRun
    $e.binding = 'throttle_up { + keyboard W } (sandbox input.map block; notched throttle)'
    $e.prediction = '0x5367d0=1 while held; 0x5367cc (int throttle) and entity +0xE4 rise; +0xAC speed rises; 0x5367db stays 0'
    $e.player_before = Get-PlayerState $Ctx
    if (-not $DryRun) { $e.focused = (Ensure-Foreground $Ctx) } else { $e.focused = $null }
    $samples = New-Object System.Collections.ArrayList
    $sw = [Diagnostics.Stopwatch]::StartNew()
    if (-not $DryRun) { Key-Down ([byte]$Vk) }
    try {
        while ($sw.Elapsed.TotalMilliseconds -lt $HoldMs) {
            if (-not $DryRun) { Key-Down ([byte]$Vk) }
            $ib = Read-InputBlock $Ctx; $ps = Get-PlayerState $Ctx; $fr = Read-U32 $Ctx $script:StimMap.FrameCounter
            [void]$samples.Add([ordered]@{ ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1); os_key_down = (Test-KeyDownOS $Vk); frame = $fr
                throttle_cc = $(if ($ib) { $ib.throttle_0x5367cc } else { $null }); throttle_up_d0 = $(if ($ib) { $ib.throttle_up_0x5367d0 } else { $null })
                fire_db = $(if ($ib) { $ib.weapon_fire_0x5367db } else { $null })
                ent_throttle_e4 = $ps.throttle; ent_speed_ac = $ps.speed })
            Start-Sleep -Milliseconds $SampleMs
        }
    } finally { if (-not $DryRun) { Key-Up ([byte]$Vk) } }
    $e.samples = $samples
    $e.player_after = Get-PlayerState $Ctx
    $e.os_key_seen = @($samples | Where-Object { $_.os_key_down }).Count
    $e.throttle_up_d0_1 = @($samples | Where-Object { $_.throttle_up_d0 -eq 1 }).Count
    $e.fire_db_1 = @($samples | Where-Object { $_.fire_db -eq 1 }).Count
    $e.throttle_cc_max = ($samples | ForEach-Object { $_.throttle_cc } | Where-Object { $_ -ne $null } | Measure-Object -Maximum).Maximum
    $e.ent_throttle_max = ($samples | ForEach-Object { $_.ent_throttle_e4 } | Where-Object { $_ -ne $null } | Measure-Object -Maximum).Maximum
    $e.canary_after = Get-Canary $Ctx
    $e.frames_advanced = $(if ($e.canary_before.frame_counter_0x5a7e1c -ne $null -and $e.canary_after.frame_counter_0x5a7e1c -ne $null) { [int64]$e.canary_after.frame_counter_0x5a7e1c - [int64]$e.canary_before.frame_counter_0x5a7e1c } else { $null })
    $e.stimulus_fired = (($e.os_key_seen -gt 0) -and ($e.throttle_up_d0_1 -gt 0) -and (($e.ent_throttle_max -ne $null -and $e.ent_throttle_max -gt 0) -or ($e.throttle_cc_max -ne $null -and $e.throttle_cc_max -gt 0)))
    $e.verdict = $(if ($DryRun) { 'dry-run (no keys sent)' } elseif ($e.stimulus_fired) { 'fired' } else { 'not proven: see os_key_seen / throttle_up_d0_1 / ent_throttle_max' })
    Write-Host ("throttle-hold: os_key {0}, d0=1 {1}, db=1 {2}, cc max {3}, +0xE4 max {4}, frames {5} -> {6}" -f $e.os_key_seen, $e.throttle_up_d0_1, $e.fire_db_1, $e.throttle_cc_max, $e.ent_throttle_max, $e.frames_advanced, $e.verdict) -ForegroundColor $(if ($e.stimulus_fired) { 'Green' } else { 'Yellow' })
    [void](Add-ManifestEntry $Ctx $e)
    return [pscustomobject]$e
}

# ---- stimulus 3: self-destruct marker (ledger / respawn; L053) -------------------------------------
function Invoke-SelfDestructMarker {
    param($Ctx, [int]$WaitSeconds = 20, [int]$PollMs = 250, [switch]$DryRun, [string]$Label = 'self-destruct')
    $e = New-Entry $Ctx 'self-destruct-marker'
    $e.label = $Label; $e.dry_run = [bool]$DryRun
    $e.binding = 'SELF_DESTRUCT Control+ALT+X (sandbox gamekey.map; cheatlib Send-SelfDestruct: scancode chord, reverse release)'
    $e.prediction = 'player entity [[[0x54a264]]+0x70] changes or drops to 0 within the wait (death/respawn); records whether the pointer changes (L053)'
    $ent0 = Get-PlayerEntity $Ctx; $e.entity_before = ('0x{0:x}' -f $ent0)
    if (-not $DryRun) { $e.focused = (Ensure-Foreground $Ctx) } else { $e.focused = $null }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    if (-not $DryRun) { Send-SelfDestruct }
    $e.sent_ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
    $timeline = New-Object System.Collections.ArrayList
    $last = $ent0; [void]$timeline.Add([ordered]@{ ms = 0; entity = ('0x{0:x}' -f $ent0); frame = (Read-U32 $Ctx $script:StimMap.FrameCounter) })
    $changed = $false
    while ($sw.Elapsed.TotalSeconds -lt $WaitSeconds) {
        Start-Sleep -Milliseconds $PollMs
        $cur = Get-PlayerEntity $Ctx
        if ($cur -ne $last) { [void]$timeline.Add([ordered]@{ ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1); entity = ('0x{0:x}' -f $cur); frame = (Read-U32 $Ctx $script:StimMap.FrameCounter) }); $last = $cur; $changed = $true }
        if ($DryRun) { break }
    }
    $e.entity_timeline = $timeline
    $e.entity_after = ('0x{0:x}' -f $last)
    $e.entity_pointer_changed = $changed
    $e.canary_after = Get-Canary $Ctx
    $e.frames_advanced = $(if ($e.canary_before.frame_counter_0x5a7e1c -ne $null -and $e.canary_after.frame_counter_0x5a7e1c -ne $null) { [int64]$e.canary_after.frame_counter_0x5a7e1c - [int64]$e.canary_before.frame_counter_0x5a7e1c } else { $null })
    $e.stimulus_fired = $changed
    $e.verdict = $(if ($DryRun) { 'dry-run (no keys sent)' } elseif ($changed) { 'fired: entity pointer moved (see timeline)' } else { "not proven: entity pointer unchanged for $WaitSeconds s (chord not seen, or death does not touch the pointer - then use the ammo/HUD as the marker)" })
    Write-Host ("self-destruct: entity {0} -> {1}, changed={2}, frames {3} -> {4}" -f $e.entity_before, $e.entity_after, $changed, $e.frames_advanced, $e.verdict) -ForegroundColor $(if ($changed) { 'Green' } else { 'Yellow' })
    [void](Add-ManifestEntry $Ctx $e)
    return [pscustomobject]$e
}

# ---- positive control: ammo write with three-horizon read-back (G-POS; H2 display + H3) -------------
function Invoke-AmmoPositiveControl {
    param($Ctx, [int]$Slot = 0, [int]$Value = 1234, [switch]$Screenshot, [switch]$KeepValue, [string]$Label = 'ammo-positive-control')
    if (-not $Ctx.Write) { throw "Open-Stim -Write is required for the positive control (VM_WRITE|VM_OPERATION)" }
    $addr = $script:StimMap.AmmoBase + $Slot * $script:StimMap.AmmoStride + $script:StimMap.AmmoOff
    $e = New-Entry $Ctx 'ammo-positive-control'
    $e.label = $Label; $e.addr = ('0x{0:x}' -f $addr); $e.addr_class = 'bss'; $e.slot = $Slot; $e.value_written = $Value
    $e.prediction = 'immediate read-back == value; the HUD ammo digits show the value (H2 channel 1); classify sticks / clobbered-per-tick / clobbered-later'
    $orig = Read-I32 $Ctx $addr; $e.original = $orig
    if ($orig -eq $null) { throw "read of $($e.addr) failed; not writing" }
    $buf = [BitConverter]::GetBytes([int]$Value); $w = 0
    $ok = [Stim]::WriteProcessMemory($Ctx.H, [IntPtr]$addr, $buf, 4, [ref]$w)
    $e.write_ok = [bool]$ok; $e.bytes_written = $w; $e.win32_error = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    $e.readback_immediate = Read-I32 $Ctx $addr
    Start-Sleep -Milliseconds ([int][math]::Ceiling($Ctx.TickMs))
    $e.readback_plus1_tick = Read-I32 $Ctx $addr
    Start-Sleep -Milliseconds ([int][math]::Ceiling(4 * $Ctx.TickMs))
    $e.readback_plus5_ticks = Read-I32 $Ctx $addr
    $e.horizon_ms = @(0, [math]::Ceiling($Ctx.TickMs), [math]::Ceiling(5 * $Ctx.TickMs))
    $e.classification = $(if ($e.readback_immediate -ne $Value) { 'write-did-not-land' }
                          elseif ($e.readback_plus1_tick -ne $Value) { 'clobbered-per-tick' }
                          elseif ($e.readback_plus5_ticks -ne $Value) { 'clobbered-on-event-or-later' }
                          else { 'sticks' })
    if ($Screenshot) { $e.screenshot = (Save-Screenshot $Ctx -Name ("ammo-{0}-{1}" -f $Slot, $Value) -NoManifest) }
    if (-not $KeepValue) {
        $rb = [BitConverter]::GetBytes([int]$orig); $w2 = 0
        [void][Stim]::WriteProcessMemory($Ctx.H, [IntPtr]$addr, $rb, 4, [ref]$w2)
        $e.restored_readback = Read-I32 $Ctx $addr; $e.restored_ok = ($e.restored_readback -eq $orig)
    }
    $e.canary_after = Get-Canary $Ctx
    $e.stimulus_fired = ($e.classification -eq 'sticks')
    Write-Host ("ammo positive control {0}: orig {1} -> wrote {2}: immediate {3}, +1 tick {4}, +5 ticks {5} => {6}" -f $e.addr, $orig, $Value, $e.readback_immediate, $e.readback_plus1_tick, $e.readback_plus5_ticks, $e.classification) -ForegroundColor $(if ($e.stimulus_fired) { 'Green' } else { 'Yellow' })
    [void](Add-ManifestEntry $Ctx $e)
    return [pscustomobject]$e
}

# ---- item 007: a gamekey chord (Control/Alt + letter) with a screenshot and canary (M06) -------------
function Invoke-DebugKey {
    param($Ctx, [Parameter(Mandatory = $true)][string]$Letter, [string]$Name = '', [switch]$Control, [switch]$Alt, [switch]$Shift,
          [int]$HoldMs = 90, [int]$SettleMs = 700, [switch]$DryRun)
    $vk = [int][char]$Letter.ToUpper()[0]
    $mods = @(); if ($Control) { $mods += 'Control' }; if ($Alt) { $mods += 'Alt' }; if ($Shift) { $mods += 'Shift' }
    $chord = (($mods + $Letter.ToUpper()) -join '+')
    $e = New-Entry $Ctx 'debug-key'
    $e.name = $Name; $e.chord = $chord; $e.vk = ('0x{0:x2}' -f $vk); $e.dry_run = [bool]$DryRun
    $e.binding = 'sandbox gamekey.map (tools\harness\gamekey.map.007-debug-keys via apply-gamekey-007.ps1); parser 0x44d460, _stricmp, "+"-split'
    $e.prediction = 'expected null: the sandbox gamekey.map header says debug keys "Don''t function in release build"; a rendered overlay falsifies it'
    if (-not $DryRun) {
        $e.focused = (Ensure-Foreground $Ctx)
        if ($Control) { Key-Down ([byte]0x11); Start-Sleep -Milliseconds 40 }
        if ($Alt)     { Key-Down ([byte]0x12); Start-Sleep -Milliseconds 40 }
        if ($Shift)   { Key-Down ([byte]0x10); Start-Sleep -Milliseconds 40 }
        Key-Down ([byte]$vk); Start-Sleep -Milliseconds $HoldMs; Key-Up ([byte]$vk); Start-Sleep -Milliseconds 30
        if ($Shift)   { Key-Up ([byte]0x10); Start-Sleep -Milliseconds 30 }
        if ($Alt)     { Key-Up ([byte]0x12); Start-Sleep -Milliseconds 30 }
        if ($Control) { Key-Up ([byte]0x11) }
        Start-Sleep -Milliseconds $SettleMs
    } else { $e.focused = $null }
    $shotName = $(if ($Name) { $Name } else { $chord.Replace('+', '-') })
    $e.screenshot = (Save-Screenshot $Ctx -Name $shotName -NoManifest)
    $e.canary_after = Get-Canary $Ctx
    $e.stimulus_fired = $null    # decided by eye from the screenshot: rendered / nothing / crash -> debug-keys.md
    Write-Host ("debug key {0} ({1}) -> {2}" -f $chord, $Name, $e.screenshot.file) -ForegroundColor DarkGray
    [void](Add-ManifestEntry $Ctx $e)
    return [pscustomobject]$e
}

# ---- screenshot helper (maplib Capture-UI; 1 px == 1 UI unit) --------------------------------------
function Save-Screenshot {
    param($Ctx, [string]$Name = ("shot-" + (Get-Date -Format "HHmmss")), [switch]$NoManifest)
    $path = Join-Path $Ctx.Dir ($Name + '.png')
    $fg = Test-GameForeground $Ctx
    if (-not $fg) { Write-Warning "game is not the foreground window: the frame may be stale unless EnableInactiveAppState is set in [General]" }
    $e = [ordered]@{ kind = 'screenshot'; t = (Get-Date -Format o); file = $path; bytes = $null; md5 = $null; foreground = $fg
                     ui_rect = (Get-UIRect); canary = (Get-Canary $Ctx); error = $null }
    try {
        [void](Capture-UI $path)
        $fi = Get-Item $path
        $e.bytes = $fi.Length; $e.md5 = (Get-FileHash -Algorithm MD5 -Path $path).Hash.ToLower()      # read-back (H3)
        Write-Host ("screenshot {0} ({1} B, md5 {2}, foreground={3})" -f $path, $fi.Length, $e.md5, $fg) -ForegroundColor DarkGray
    } catch {
        # CopyFromScreen throws Win32Exception "The handle is invalid" when the session has no desktop to grab
        # (RDP; AGENTS.md). Record it instead of losing the calling stimulus's manifest entry.
        $e.error = $_.Exception.Message; $e.file = $null
        Write-Warning ("screenshot failed: {0} (no console desktop? the sitting must run at the physical monitor)" -f $e.error)
    }
    if (-not $NoManifest) { [void](Add-ManifestEntry $Ctx $e) }
    return [pscustomobject]$e
}

Write-Host "stimuli.ps1 loaded: Open-Stim, Get-Canary, Read-InputBlock, Read-Ammo, Get-PlayerState, Invoke-FireHold, Invoke-ThrottleHold, Invoke-SelfDestructMarker, Invoke-AmmoPositiveControl, Invoke-DebugKey, Save-Screenshot, Close-Stim" -ForegroundColor DarkGray
