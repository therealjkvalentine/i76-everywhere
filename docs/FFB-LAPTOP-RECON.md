# SOLVED: I76 force feedback dies if other joysticks are installed

> **ANSWER (2026-08-02): remove the extra/virtual joysticks and reboot.** Force
> feedback worked on one Windows box and not another. The difference was not
> Windows version, not the exe, not the registry, not frame generation — it was
> **other joystick devices present on the machine**. Uninstalling them and
> restarting made FFB work immediately.

## The symptom

The game runs fine. The wheel steers, the pedals work, every button works. There
is simply **no force feedback**, and — if you have wired firing to something that
produces effects — the first shot can crash the game in `I7_SFRCE.DLL` at fault
offset `0x2505`, because the effect object was never created and gets
dereferenced anyway.

`tools\check-ffb.ps1`, run **while in a mission**, reports the tell exactly:

```
I7_SFRCE.DLL loaded     : yes
FF device detected flag : 0
FF effect object ptr    : 0x00000000
  -> MODULE LOADED BUT NO DEVICE
```

That combination — module resolved, device not — is the whole diagnosis. It means
`I7FF_InitSystem` ran and failed to open a force-feedback device:
*"Failed to open FF Joystick. Try again next time."*

## Why other joysticks break it

Settled by disassembly of the Gold exe (`i76.exe`, MD5
`60abf7bc699da72476128ddce991a3d1`):

- FFB init at `0x445A60` is called **unconditionally** from `0x402F93` at startup.
- It calls `0x446020`, which builds `"I7_SFRCE.DLL"`, `LoadLibrary`s it, resolves
  three exports, then calls `I7FF_InitSystem`.
- The DLL loads fine — `0x52bbdc` (the `I7FF_InitSystem` pointer) reads nonzero
  even on the broken machine. **`LoadLibrary` was never the problem.**
- `I7FF_InitSystem` wants DirectInput **exclusive** acquisition and tries
  **once**, at startup ("try again next time" is not a retry — it is a give-up).
- `0x52bbd0` (FF-detected flag) stays `0`; `0x52bbcc` (effect object) stays null.

A 1997 title enumerating DirectInput devices does not go looking for *your* wheel.
Add other joysticks — especially **virtual** ones that are always present — and
the one-shot acquire lands on the wrong device and gives up.

**On the machine that failed:** two virtual joysticks — **vJoy** (winmm id 3) and a
**3Dconnexion KMJ Emulator** (id 7) — sharing the list with the wheel. Removing the
**3Dconnexion KMJ Emulator** and rebooting fixed FFB immediately, and afterwards
`joystick1` was the only winmm device. First success ever recorded on that box:

```
FF device detected flag : 1
FF effect object ptr    : 0x0B900000
```

**The signature worth remembering: input worked the whole time, FFB did not.** Input comes
through **winmm**, where the wheel was always correctly at `joystick1` — steering, pedals and
buttons all fine. Force feedback is opened through **DirectInput**, which enumerates
*separately* and needs exclusive acquisition. So *"input works but FFB doesn't"* points at
DirectInput enumeration, never at the wheel.

**On the machine that worked:** zero enumerable joysticks besides the wheel. Note
it *does* have a **Nefarius Virtual Gamepad Emulation Bus** (ViGEm) installed —
but `DEVPKEY_Device_Children` is empty, so the bus instantiates no pads and
contributes nothing to enumeration. **A dormant bus is harmless; what matters is
whether a joystick DEVICE is enumerated.** Check children, not just presence.

## Fix

```powershell
# Administrator PowerShell - list what is actually there first
Get-PnpDevice | Where-Object { $_.FriendlyName -match '(?i)vJoy|3Dconnexion|KMJ|x360ce|ViGEm' }

# then disable (or uninstall) the virtual ones, and REBOOT
Get-PnpDevice | Where-Object { $_.FriendlyName -match '^vJoy Device$|3Dconnexion KMJ Emulator' } |
    Disable-PnpDevice -Confirm:$false
```

Reboot matters — a disable alone may not re-order enumeration for an already
running session.

Re-enable later with `Enable-PnpDevice` the same way. (vJoy in particular is safe
to remove here — head tracking moved to freetrack shared memory and no longer
uses it.)

## Ruled OUT — do not spend time on these

Each of these was checked and is **not** the cause:

| Suspected | Verdict |
|---|---|
| `enable-force-feedback.bat` / the ACTIVISION registry key | **There is no registry gate in this exe.** The only `SOFTWARE\Activision` access sits beside `Minimum`/`miss8`/`miss16` (mission texture resolution). That .bat is a CD-era fix that does not gate the Gold build. |
| The FFB module failing to load | It loads. `0x52bbdc` is nonzero on the broken machine. |
| Missing `force\*.frc` effect files | 14 present on both. |
| A different `i76.exe` build | Same MD5 `60abf7bc699da72476128ddce991a3d1` on both machines. |
| Lossless Scaling / frame generation | Fails identically with it disabled. |
| Windows 10 vs 11 | Different on the two boxes, but not the cause. |
| Stale winmm axis calibration | Checked and irrelevant to FFB. |
| GOG-installed vs portable copy | Not the cause. |

**One thing that IS a real, separate cause:** the **Thrustmaster control panel
being open** takes the DirectInput device exclusively, producing the identical
"module loaded, no device" state. Close it before launching — its own UI says so
on every tab. See [WHEEL-T300.md](WHEEL-T300.md).

Likewise, if FFB has already failed once, relaunching may not recover it: a
crashed process can leave the device unreleased. **Power-cycle the wheel.**

## The general lesson

> A 1997 game that acquires a DirectInput device **once at startup** has no
> tolerance for a crowded device list. Anything that adds a permanent phantom
> joystick — vJoy, x360ce, KMJ emulators, instantiated ViGEm pads — can silently
> take the slot. The symptom is never "your joystick software is wrong", it is
> "the game's force feedback is broken".

## Tools

- [`tools/check-ffb.ps1`](../tools/check-ffb.ps1) — reads the engine's own FFB
  state out of the live process. **Run it while in a mission**: the FF device is
  opened at startup but only meaningful in play, and checking at the title screen
  reports "not loaded" on a perfectly healthy setup.
- [`tools/ffb-recon.ps1`](../tools/ffb-recon.ps1) — dumps the machine-side facts
  (virtual joysticks and their children, winmm enumeration, the joystick
  registry, file hashes) in a fixed order, so two machines can be diffed
  mechanically rather than compared by eye. That is how this was found.

Both read only. Neither opens the Thrustmaster control panel, deliberately.

## The false negative that cost the most time

`i76.exe` is **32-bit**. From 64-bit tooling, `$proc.Modules` and `tasklist /m` both report
`I7_SFRCE.DLL` as **absent** while it is loaded and working, and a `LoadLibrary` test from
64-bit PowerShell returns a meaningless error 126. That sends you hunting a load failure that
never happened.

**Read `0x52bbdc` instead** — the exe's own `GetProcAddress` result, written only after
`LoadLibrary` *and* `GetProcAddress` both succeed. Nonzero means loaded and resolved.
`tools/check-ffb.ps1` does this.
