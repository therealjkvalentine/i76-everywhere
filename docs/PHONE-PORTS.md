# Interstate '76 on a phone — Android (real) vs iPhone (stream/emulate)

*The last stop on the "everywhere" tour. Two very different answers: **Android is the Steam Deck
recipe again** (Wine → DXVK → Vulkan, which we already ship), so I76 is an unusually strong
candidate; **iOS has no translation layer**, so the honest port is game-streaming, with a QEMU VM
as a distant second.*

> **STATUS: RESEARCH / UNTESTED (2026-07-14).** Nobody has run this on real phone hardware yet.
> This is a playbook derived from (a) our working Deck build — same Wine→DXVK→Vulkan chain — and
> (b) the current state of the Android/iOS scene. Treat every "should" here as a hypothesis to
> field-test, exactly like the Deck doc was before the Deck install. When a device is in hand,
> promote the verified parts into a proper step-by-step and delete the hedges.

Why I76 specifically is a good phone candidate (both platforms): it's a **1997 game hard-capped at
20 FPS** with a Pentium-era CPU footprint. Every technique on a phone — CPU instruction translation
(Box64), x86 emulation (QEMU), video streaming — pays a per-frame tax that murders modern titles
but is a rounding error on this one. The 20 FPS ceiling that annoys us elsewhere is the single
biggest reason the phone paths are viable.

---

## Android — the real port (high confidence, untested)

The Android scene runs **exactly the stack we already ship on the Deck**:
[**Winlator**](https://github.com/brunodev85/winlator) glues together
[Wine](https://www.winehq.org/) (Windows API → Linux),
[**Box64/Box86**](https://github.com/ptitSeb/box64) (x86/x86-64 → ARM64, real-time),
[**DXVK**](https://github.com/doitsujin/dxvk) (DirectX → Vulkan), and
[**Turnip**](https://docs.mesa3d.org/drivers/freedreno.html) (Mesa's open Vulkan driver for Qualcomm
Adreno GPUs) — the same Wine→DXVK→Vulkan chain as our `-glide` Deck launcher, minus MoltenVK.

- **Current release:** Winlator **11.1** (June 2026, brunodev85, LGPL-2.1). Ships **Glibc** (broad
  compatibility, the safe default) and **Bionic** (Android-native libc, lower overhead, occasional
  game-specific breakage) builds. Community forks worth knowing: `shishiwow/winlator-glibc`
  (rolling Glibc), `WinlatorMali` forks (Mali/Exynos support), `WinlatorXR` (standalone OpenXR
  headsets — i.e. Quest, same stack).

### Both of our render paths have an Android equivalent

| Our path (Mac/Deck) | Android equivalent | Notes |
|---|---|---|
| **Software renderer** (DxWnd wraps 1997 DirectDraw) | **cnc-ddraw** | Winlator bundles it; same job as DxWnd — wrap legacy DirectDraw for a modern display. The low-risk first attempt. |
| **Glide path** (dgVoodoo 2.78.2 → DXVK → Metal) | **dgVoodoo 2.78.2 `Glide2x.dll` + our [`dgVoodoo.conf`](../dgVoodoo.conf)** → DXVK → Turnip | **Literally the Deck recipe.** Drop the same Glide wrapper + config into the container; DXVK/Turnip do the rest. This is the path most likely to look great. |

The Glide path is the one to bet on: it's the *identical* wrapper and config file we already tuned
for the Deck (gamma + 4× MSAA + 32-bit), and Turnip on Adreno is a genuine Vulkan driver — no
MoltenVK shader-persistence wall (the reason [Voodoo is parked on the Mac](VOODOO-PARKED.md)).

### Concrete container settings (starting point)

- **Graphics driver:** newest **Turnip** (or Turnip+Zink) — on Snapdragon this is the single
  highest-impact setting. Install a recent driver from file; don't rely on the stock one.
- **DX wrapper:** try **cnc-ddraw** (software path) first; for the pretty path, install
  dgVoodoo `Glide2x.dll` + our conf and launch the Glide renderer.
- **`MESA_EXTENSION_MAX_YEAR=2003`** in Container Settings → Environment Variables — the standard
  Winlator fix for "very old game won't open / renders garbage." I76 is a prime candidate.
- **Input API = DirectInput** (Winlator 11.x lets you pick DirectInput vs XInput per game).
  I76 is winmm/DirectInput-era, not XInput — same lesson as the Mac gamepad work.
- **FPS:** set **`FPSLimit=20`** in `dgVoodoo.conf` (already in ours). The
  [frame-rate ↔ jump-distance rule](VERIFIED-FIXES.md) is engine-level and applies on *every*
  platform — Mission 5's canyon jump misses above ~20 FPS no matter the hardware.

### Hardware reality

- **Snapdragon / Adreno = first-class** (Turnip is built for it). This is the device to use.
- **Mali / Exynos = second-class** — the `WinlatorMali` forks exist but rendering is rougher and
  driver support lags. Set expectations accordingly.
- **Meta Quest** works via `WinlatorXR` (same stack, standalone headset) — a curiosity, not a plan.

### What we'd copy straight from this repo

| Repo asset | Phone use |
|---|---|
| [`dgVoodoo.conf`](../dgVoodoo.conf) + dgVoodoo 2.78.2 `Glide2x.dll` | Drop into the Winlator container for the Glide path — unchanged. |
| [`input.map`](input.map.reference) | Wine's winmm joystick path serves a Bluetooth controller the same way it does on Mac/Deck. Start from our reference and adapt bindings. |
| [`smack-music-fix/`](../smack-music-fix/) + [`setup-music.sh`](../setup-music.sh) | The MCI/redbook mission-music problem **and** the cutscene-music-bleed bug both exist under Wine on Android too — our virtual-CD setup + `SMACKW32.DLL` proxy port directly. |
| [`i76-save-editor.html`](../i76-save-editor.html) | **Works on a phone today** — open the page in any mobile browser, drag in a `.cmp`, edit, download. No install. (The `.command` launcher/server is desktop-only; the page's drag-and-drop mode is not.) |
| [`deck/`](../deck/) install tooling | The closest existing analog to a Winlator setup script — the config-application logic is reusable in spirit. |

### Proposed next step

If a **Snapdragon** device (phone, tablet, or Quest) is available, write `docs/ANDROID.md` as a
real step-by-step: exact container settings, which files to copy where, the `MESA_EXTENSION_MAX_YEAR`
and DirectInput toggles, controller layout, and software-vs-Glide comparison screenshots — then
field-test it the way the Deck build was tested. Everything above is a hypothesis until then.

---

## iPhone / iPad — no translation layer (three options, ranked)

iOS has **no Wine/Box64 equivalent** — Apple's platform rules foreclosed that whole category, and no
Winlator-for-iOS exists or can exist under App Store terms. So the "port" is one of three
work-arounds:

1. **Stream it — the pragmatic port (recommended).**
   [**Sunshine**](https://github.com/LizardByte/Sunshine) host on your Mac or the Windows box +
   [**Moonlight**](https://moonlight-stream.org/) client on the iPhone + a Bluetooth controller.
   Full native quality, works tonight, and because the game is locked at 20 FPS, streaming latency
   and compression cost the experience almost nothing. This is what I'd actually do. (The host runs
   *our* build — Mac DxWnd or the Windows max-graphics setup — so every fix in this repo applies
   unchanged; the phone is just a screen + gamepad.)

2. **UTM SE — emulate a Windows VM (App Store, no jailbreak).**
   [UTM SE](https://apps.apple.com/us/app/utm-se-retro-pc-emulator/id1564628856) ("slow edition")
   uses a threaded interpreter — slower than JIT, but a 20 FPS software-rendered 1997 game is the
   single best case for it. Realistic verdict: **playable-ish, not smooth.** A **Win95/98** guest
   is the natural target; **WinXP** actually runs lighter on iPhone and is worth trying too.
   - Faster variant: the full **[UTM](https://github.com/utmapp/UTM)** (not SE) sideloaded via
     **AltStore** with **"Enable JIT for UTM"** turned on — JIT closes most of the speed gap, at the
     cost of a sideloading setup. Still emulation, so still no Glide (software renderer only inside
     the VM).

3. **Native reimplementation — the someday answer.**
   [Open76](https://github.com/rob518183/Open76) (Unity) could target iOS/Android **natively** if it
   ever reaches playability — but it's a work-in-progress engine, not a game (see
   [MODERN-PORTS-AND-VR.md](MODERN-PORTS-AND-VR.md)). Log it; don't wait for it.

**Bottom line for iOS:** stream from a machine that already runs our build. The VM route is a fun
experiment, not a daily driver.

---

## Summary

| Platform | Path | Verdict | Effort |
|---|---|---|---|
| **Android (Snapdragon)** | Winlator: cnc-ddraw *or* dgVoodoo→DXVK→Turnip | **Real port** — Deck recipe transfers; I76 is an ideal candidate | Weekend test on real hardware |
| **Android (Mali/Exynos)** | Winlator (Mali forks) | Works, rougher | Same, lower payoff |
| **Quest (standalone)** | WinlatorXR | Same stack, curiosity | Low priority |
| **iPhone/iPad** | Sunshine + Moonlight stream | **Best iOS experience** — 20 FPS makes streaming ~lossless | Works today, no port |
| **iPhone/iPad** | UTM SE / UTM+JIT VM | Playable-ish, not smooth | Experiment |
| **Both** | Open76 native (WIP) | Not yet a game | Watch, don't wait |

*Repo assets that already work on a phone with zero effort: the **[save editor](../i76-save-editor.html)**
(any mobile browser). Everything else is a copy-the-Deck-files exercise waiting on a test device.*

---

### Sources (2026-07)

- Winlator — [github.com/brunodev85/winlator](https://github.com/brunodev85/winlator) (v11.1,
  June 2026; Glibc/Bionic builds; DirectInput/XInput selector, controller vibration in 11.x)
- Box64/Box86 — [github.com/ptitSeb/box64](https://github.com/ptitSeb/box64)
- Turnip / Mesa Freedreno — [docs.mesa3d.org](https://docs.mesa3d.org/drivers/freedreno.html);
  driver-choice guidance: [winlator.dev/best-gpu-drivers](https://winlator.dev/best-gpu-drivers/)
- `MESA_EXTENSION_MAX_YEAR=2003` old-game fix — Winlator README / setup guides
- UTM & UTM SE — [github.com/utmapp/UTM](https://github.com/utmapp/UTM),
  [getutm.app](https://getutm.app/) (SE = threaded interpreter, no JIT/jailbreak; full UTM + AltStore
  JIT is faster)
- Moonlight / Sunshine game streaming — [moonlight-stream.org](https://moonlight-stream.org/),
  [github.com/LizardByte/Sunshine](https://github.com/LizardByte/Sunshine)
- Reimplementations (Open76) — see [MODERN-PORTS-AND-VR.md](MODERN-PORTS-AND-VR.md)
