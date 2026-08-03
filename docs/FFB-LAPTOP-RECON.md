# FFB recon: what differs between the machine where it works and the one where it doesn't

Force feedback works on one Windows machine (a laptop) and not on another
(desktop). Everything on the desktop side has been traced already; what is left
is a **diff**. Run the prompt below on the WORKING machine and bring the output
back.

## What is already established on the BROKEN machine

Do not re-derive these — they are settled by disassembly of the Gold exe
(`i76.exe`, MD5 `60abf7bc699da72476128ddce991a3d1`):

- FFB init at `0x445A60` is called **unconditionally** from `0x402F93` at startup.
- It calls `0x446020`, which builds `"I7_SFRCE.DLL"`, `LoadLibrary`s it, resolves
  three exports, then calls `I7FF_InitSystem`.
- **There is no registry gate.** The only `SOFTWARE\Activision` access sits beside
  `Minimum` / `miss8` / `miss16` (mission texture resolution).
  `enable-force-feedback.bat` is a CD-era fix that does **not** gate this exe.
- On the broken machine the DLL **is** loaded and resolved: `0x52bbdc`
  (I7FF_InitSystem ptr) reads nonzero. So `LoadLibrary` is not the problem.
- The failure is `I7FF_InitSystem` → *"Failed to open FF Joystick. Try again next
  time."* FFB wants DirectInput **exclusive** acquisition and tries **once** at
  startup. `0x52bbd0` (FF-detected flag) stays 0 and `0x52bbcc` (effect object)
  stays null.

Already ruled out on the broken machine: Lossless Scaling / frame generation
(fails identically without it), the Thrustmaster control panel being open, the
registry key, and a stale winmm axis calibration.

Known differences to confirm or eliminate: **Windows 11 (working) vs Windows 10
(broken)**; the broken box has **two virtual joysticks** the laptop does not
(vJoy and a 3Dconnexion KMJ Emulator); and the working copy may be a **GOG
installed** copy vs a **portable/zip** copy.

## Prompt to run on the WORKING laptop

> I need to work out why Interstate '76 force feedback works on this machine but
> not on another Windows box. Please gather the following and give me the raw
> output — do not fix anything, this is recon only.
>
> 1. **Confirm FFB actually works here.** Start the game, get **into a mission**
>    (not the menu — the FF device is opened at startup but only meaningful once
>    playing), and run `tools\check-ffb.ps1` from the i76-everywhere repo. I want
>    the FF-detected flag at `0x52bbd0` and the effect object at `0x52bbcc`.
>    If you don't have the repo, read those two DWORDs out of `i76.exe` yourself.
>
> 2. **Windows + driver versions.** `[Environment]::OSVersion`, the build number,
>    and the Thrustmaster driver version. Which PID does the wheel enumerate as —
>    `VID_044F&PID_B66E` (properly driven) or `PID_B65D` (generic pre-init)?
>
> 3. **Every joystick this machine exposes**, in enumeration order. For winmm:
>    `joyGetDevCaps` for ids 0-15, with name, axis count, button count. For
>    DirectInput/HID: `Get-PnpDevice -Class HIDClass`. **I specifically need to
>    know whether any VIRTUAL joysticks exist here (vJoy, 3Dconnexion KMJ
>    emulator, x360ce, ViGEm)** — the broken machine has two and this one may
>    have none, which would change DirectInput enumeration order.
>
> 4. **Which winmm slot is the wheel**, and the matching registry:
>    `HKCU\System\CurrentControlSet\Control\MediaResources\Joystick\DINPUT.DLL`
>    — both `CurrentJoystickSettings` and `JoystickSettings\<VID&PID>`.
>
> 5. **Install type and files.** Is this a GOG-installed copy or a portable/zip
>    copy? MD5 of `i76.exe` and `i7_sfrce.dll`, and whether `force\*.frc` (14
>    files) are present.
>
> 6. **Registry:** everything under `HKLM\SOFTWARE\WOW6432Node\ACTIVISION` and
>    `HKLM\SOFTWARE\ACTIVISION`, values included.
>
> 7. **Config:** the `steer` and `throttle` blocks from `input.map`, and the
>    `FPSLimit` / `Resolution` / `FullScreenMode` / `ScalingMode` lines from
>    `dgVoodoo.conf`.
>
> 8. **How the game is launched here** — which .bat/shortcut, whether Lossless
>    Scaling is used, and whether the wheel is always connected before launch.
>
> 9. **Thrustmaster control panel settings**: rotation angle (is 300 degrees
>    actually applied and does it persist when the panel is closed?), and whether
>    pedals are set to COMBINED or SEPARATE.

## The one local test worth doing first on the broken machine

Disable the two virtual joysticks and relaunch — if DirectInput enumeration order
is the cause, this fixes it without needing the laptop at all:

```powershell
# Administrator PowerShell
Get-PnpDevice | Where-Object { $_.FriendlyName -match '^vJoy Device$|3Dconnexion KMJ Emulator' } | Disable-PnpDevice -Confirm:$false
```

vJoy is safe to disable — head tracking moved to freetrack shared memory and no
longer uses it. Re-enable with `Enable-PnpDevice` the same way.
