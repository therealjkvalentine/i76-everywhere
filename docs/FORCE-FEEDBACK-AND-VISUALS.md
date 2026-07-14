> **STATUS: FFB is a Mac DEAD END** (Wine FFB = Linux evdev only); works on Deck/Windows. The 1024×768 software ceiling here is correct. See [README.md](README.md).

# Interstate '76: force feedback & pushing visual quality

*Deep-research synthesis (2026-07-09, 106 agents, adversarially verified). Answers two questions:
can we get force feedback to a modern wheel, and can we push resolution/detail past the in-game
menu? Short version: FFB is real in the game but has no path to a Mac wheel under Wine; and
1024x768 is the software renderer's hard ceiling.*

## Force feedback

**It's in the base GOG "Gold/Arsenal" game — not a special edition.** The Nitro Pack (bundled in
Gold, which GOG sells) added force feedback alongside the v1.2 patch and 3D acceleration. A
separate Microsoft SideWinder Force Feedback Pro pack-in edition existed but was content-identical.
So the FFB code ships in the GOG `i76.exe`.
[PCGamingWiki](https://www.pcgamingwiki.com/wiki/Interstate_'76), [MobyGames](https://www.mobygames.com/game/interstate-76/).

**But it's OFF by default on Gold — enabled by a registry rename:**
`HKLM\SOFTWARE\ACTIVISION\Interstate'76FRC` → `Interstate '76`
([PCGW "Enabling force feedback on the Gold Edition"](https://www.pcgamingwiki.com/wiki/Interstate_'76)).
Once on, the engine emits real DirectInput FFB that a modern USB wheel picks up — confirmed on a
Logitech Driving Force GT ([VOGONS](https://www.vogons.org/viewtopic.php?t=61199)). **That test was
on Windows.**

**On macOS-via-Wine, FFB is effectively a dead end — here's exactly why:**

- Wine's DirectInput layer *is* fully FFB-capable (`dlls/dinput/device.c` implements
  CreateEffect/SendForceFeedbackCommand/etc., delegating to a per-device backend).
- **But Wine's only concrete FFB backend is Linux evdev** (`effect_linuxinput.c` → `EVIOCSFF`
  ioctl on `/dev/input/event*`). **There is no macOS/IOKit code path at all.** So the effects the
  game sends have nowhere to land on a Mac.
- The whole Linux wheel-FFB ecosystem (new-lg4ff kernel module, Oversteer GUI) is Linux-only, no
  Mac equivalent.
- **Torqer** (torqer.app) is the one macOS app that bridges game FFB to a physical wheel under
  CrossOver/Sikarugir/Heroic on Apple Silicon — but it's validated **only for modern racing sims
  with native FFB**, on specific wheels (Fanatec/Moza/G29 now, G920 in beta). There is **no
  evidence it works with a 1997 DirectInput-era title** like I76, whose FFB path is very different.
  Worth watching, unproven here.
- **Streaming won't carry it:** Moonlight/GameStream passes input to the host as a virtual Xbox
  (XInput) pad only — no DirectInput state, no FFB return channel.

**Verdict & best achievable setup:**
1. **Real FFB → play on the Windows box** (native DirectInput; do the registry rename above; your
   wheel+pedals with FFB work as they did with the Sidewinder). This is the reliable answer.
2. **Linux** (evdev + new-lg4ff) would also work but isn't your setup.
3. **Mac:** enjoy it wheel-as-input (no FFB), or try Torqer as an experiment (low odds for a 1997
   title). Don't expect the shaking.

## Pushing visual quality beyond the menu

**1024x768 is the software renderer's hard ceiling — you're already at it.** The GDI/software
renderer supports up to 1024x768; the Gold Edition's Direct3D mode is hard-locked at 640x480 with
low-res textures. Research found **no config file, registry key, or hex edit** that unlocks
internal resolutions beyond 1024x768, and **no way to push Visibility/detail past the menu max**
(you already have Visibility FAR, detail HIGH — those are the engine caps). The camera is hardcoded
4:3 and physics are framerate-locked ~20 FPS, which is why nobody built a higher-res mod.
[PCGamingWiki](https://www.pcgamingwiki.com/wiki/Interstate_'76), [Shane Peelar RE writeup](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/).

**What we CAN do:**
- **DxWnd already scales your 1024x768 up to fill the screen** — that's what you're seeing. This is
  the right setup: max internal res (1024x768) scaled out with the aspect preserved.
- **The only route to *higher internal* resolution** is the game's **Glide** renderer through
  **dgVoodoo2**, which can force high 4:3 resolutions on the native 3dfx port (per the
  [CahootsMalone guide](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md)).
  That's the "voodoo" mode we explored — it renders at 1280x960+ with filtered textures and 3dfx
  color — but it reintroduces the per-launch shader warmup (see DXGI-DGVOODOO-RESEARCH.md) and is
  still 4:3. It's a genuine quality-vs-smoothness tradeoff, not a free win.
- Bottom line: for the DxWnd/software path you're on, **1024x768 + DxWnd upscale is the ceiling**,
  and it looks good. More internal detail means switching to the dgVoodoo Glide route and its
  warmup.

Open items (unresolved by research, would need hands-on RE): whether a binary patch could raise the
software renderer above 1024x768, and whether dgVoodoo Glide genuinely raises *internal* detail vs
just output resolution.