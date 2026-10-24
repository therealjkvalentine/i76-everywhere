# Interstate '76 Patch Kit (i76-everywhere)

Tester build, first tested by one tester on 2026-10-23.

This is the i76-everywhere Interstate '76 project, written by its developer, packed so it installs over **your own GOG copy** of the game.
It contains none of the game itself - only our fixes, launchers and two helper programs - and it patches your
copy in place, keeping the original of every file it touches. Everything stays inside the game folder.

What it gives you, in one line each:

- **Smooth 120 fps play with the 1997 feel**: the car is still simulated 24 times a second as it was in 1997
  (so the physics, the jumps and the AI behave as the game was tuned), but the picture is drawn at your monitor's
  refresh rate, in between those steps.
- **Any monitor shape**: ultrawide, 16:9, 16:10 or 4:3 - the launcher reads your monitor and sizes the picture. The
  3D view is wider on a wide screen (you see more, nothing is stretched); the menus stay 4:3 with bars.
- **Three times the draw distance** (1.8 km instead of 600 m), with roads and bushes all the way out, more terrain
  detail, shadows and textures farther away, a rear-view mirror that sees 300 m.
- **Menus that work with a modern mouse** (the pointer lands where you click), a save screen you can type in, and
  keyboard shortcuts for the popups (Enter / Space / Y / N).
- **A WASD-style keyboard layout** (the full table is below) plus gamepad and wheel support.
- A second launcher with the **graphics experiments** the developer is working on right now (smoother terrain, 2.3 km view
  fading out at the far edge). That one is unpolished on purpose - he wants your eyes on it.

## What you need

- **Interstate '76 from GOG** (the "Arsenal" / Gold Windows version), installed with GOG Galaxy or the offline
  installer. GOG has shipped two slightly different `i76.exe` builds over the years; both are handled, and the
  setup tells you which one you have.
- Windows 10 or 11 (64-bit) and any graphics card from the last ten years. (the developer plays on a GTX 1080 Ti at
  3440x1440 with the picture rendered at 2x; a weaker card gets the `--no-supersample` option below.)
- Optional: an Xbox-style gamepad or a wheel - **plug it in before you start the game**, the 1997 engine only looks
  for controllers at startup. Python 3 is only needed for the debug dashboard (DEBUG.bat), which you can ignore.
- Not needed: administrator rights, registry changes, GOG Galaxy running, anything outside the game folder.

## Install (three steps)

1. **Find the game folder.** In GOG Galaxy: select the game, click the settings icon next to PLAY, *Manage
   installation* -> *Show folder*. It is usually `C:\GOG Games\Interstate 76` or
   `C:\Program Files (x86)\GOG Galaxy\Games\Interstate 76`. It is the folder that contains `i76.exe`.
2. **Unzip this file INTO that folder**, so that `PLAY.bat` ends up next to `i76.exe`. (Right-click the zip ->
   *Properties* -> tick *Unblock* if that box is shown -> OK. Then right-click -> *Extract All...* and set the
   destination to the game folder.) The unzip itself overwrites nothing of the game. (If you forget *Unblock*,
   Windows asks once more when you start `PLAY.bat` - *More info* -> *Run anyway* - and the launcher then clears the
   download mark from the folder's files itself.)
3. **Double-click `PLAY.bat`.** The first run does a one-time setup in a black window (about ten seconds): it
   lists every file it changes and where it kept the original. A yellow line saying `i76.exe MD5 ... NOT the GOG
   2019 build` is normal on a Galaxy install. Then the game starts. Later runs skip the setup.

The game shows **PLEASE STAND BY** for up to a minute while it loads, then the intro movie - **Esc** skips it. If
`PLAY.bat` ever refuses to start the game it says why and waits for a key.

If the game lives under `C:\Program Files (x86)` and the setup reports *access denied*, run `PLAY.bat` once with
right-click -> *Run as administrator*, or (better) tell Galaxy to install the game somewhere like `C:\Games`.

## The launchers

| file | what it starts |
|---|---|
| **`PLAY.bat`** | **STABLE.** Exactly the set the developer plays every day: the 1997 timing at 120 fps, widescreen, 1.8 km view, every fix that has passed his testing. |
| **`PLAY-PREVIEW.bat`** | **EXPERIMENTAL GRAPHICS PREVIEW.** The same base plus the developer's current graphics picks: smoother terrain shading and terrain that morphs in instead of popping, a 2.3 km view whose last quarter fades out to transparent (no fog colour), bushes at half density carried farther out, a rear-view mirror that sees 1 km with the main view's ground textures, a slightly softer nose-dive on jumps. Not finished, not gated - it exists so you can compare it with `PLAY.bat`. |
| `PLAY-T05.bat` / `PLAY-PREVIEW-T05.bat` | The same two, but they boot **straight into mission 5** (the long ridge road down to the barn) with a stock car, skipping the menus and movies. The quickest way to look at the terrain. |
| `PLAY-16x10.bat`, `PLAY-balanced.bat`, `PLAY-stock.bat`, `PLAY-i76.bat` | Written by the setup. `PLAY-16x10.bat` = the older tested 16:10 picture (a fallback if the widescreen one looks wrong); `PLAY-stock.bat` = the game with none of our engine changes (a control); the other two are variants of the stable set. |
| `UNINSTALL-i76e.bat` | Puts your folder back the way GOG installed it (see the end). |

Options you can add after the launcher name (open a command window in the folder, or edit a shortcut):

- `PLAY.bat --no-supersample` - lighter on the graphics card: the 3D is rendered at your monitor's size instead
  of twice that. Use it if the frame rate drops under ~60 or the card is weak / integrated.
- `PLAY.bat --display 1920x1080` - size the picture for this monitor size instead of the one Windows reports
  (for example when the game opens on the wrong monitor).
- `PLAY.bat --setup` - run the setup / display step only, without starting the game.

## Your monitor

Every start reads the size of your **main** monitor and, when it changed, rewrites the display settings for it:
the 3D is rendered at twice your monitor's size (a real supersample, no shimmer) and shown at your monitor's own
shape - 21:9, 16:9, 16:10 and 4:3 all come out right, nothing is stretched. The 640x480 menus, garage and movies
are shown 4:3 with side bars. The game runs in a borderless window the size of the screen, so Alt-Tab works.

The developer has only ever played this at 3440x1440. On other sizes the numbers are computed; they were checked on his
PC with the game set to 1920x1080 and 2560x1440 (the picture came out 16:9, nothing stretched, and the mouse
pointer landed on the menu buttons all the way from TRIP to the garage's DONE), not on a real 16:9 monitor - so **if the picture looks off-centre, stretched, or the mouse pointer does not land on the menu
buttons, that is exactly what we want to hear about.**
Tell us your monitor size and send a screenshot (Win+PrtScn saves one to Pictures\Screenshots).

## Keys

This is *our* layout, not the 1997 one (which had the arrow keys driving and Space firing). The printable sheet
with the gamepad and wheel pages is `_i76e\repo\docs\Interstate76-Controls-Quick-Reference.pdf`.

**Driving**

| key | does |
|---|---|
| `W` / `S` | accelerate / brake |
| `A` / `D` | steer left / right |
| `Space` | handbrake |
| `X` | reverse (toggle) |
| `I` | ignition - start the engine (you need it after a stall or at a mission start) |
| `,` / `.` | gear down / up (automatic otherwise) |
| `H` | headlights |
| `G` | horn |

**Weapons and targeting**

| key | does |
|---|---|
| `Enter` or left mouse button | fire the selected weapon |
| `Tab` (or `C`) | select the next weapon |
| `F` | link / unlink weapons (stock I'76 used `L`; here `L` fires hardpoint 3). Linked, `Enter` fires the group |
| `1` `2` `3` `4` `5`, also `J` `K` `L` `;` for 1-4 | fire hardpoint 1-5 directly (right mouse button = hardpoint 2) |
| `6` `7` `8` | special 1 / 2 / 3 (nitrous is usually `6`) |
| `Q` | target the car in front of you |
| `Y` / `T` | next target / nearest enemy |
| `U` | clear the target |
| `E` | look at the target |
| `R` | radar range |
| `O` | radar camera |

**Views and looking around**

| key | does |
|---|---|
| `F1` | cockpit (press again: cockpit without the dashboard) |
| `F6` | hood view - the view the developer uses to judge the terrain |
| `F3` | chase camera; `F2` `F7` `F8` `F9` `F10` other outside views |
| `V` | combat view (toggle) |
| `B` | binoculars |
| arrow keys (or middle mouse button = look left) | glance up / down / left / right |
| `Page Up` / `Page Down` / `End` | zoom out / in / reset (view, map and camera) |
| `Shift` + arrows | move the outside camera / pan the map |
| `Ctrl`+`Alt`+`H` | head look (only with a head tracker and `PLAY-i76.ps1 -HeadTrack`, which a normal set does not use): cycles ANALOG (start) > DIGITAL > OFF, shown on screen; holding a glance key overrides it |
| `M` | map |
| `N` | notepad (the mission briefing) |
| `P` | poetry |
| `Esc` | pause menu in a mission (resume / options / abort); skip a movie |

**Menus, saving, loading**

- The menus are mouse-driven; the pointer should land where you click. If a popup appears ("YOU NEED AN ENGINE",
  "REMEMBER TO SAVE") press **Enter** or **Space** to close it. The *overwrite this bookmark?* prompt answers to
  **Y** / **N**. **Never use the in-game Control Configuration menu** - it corrupts the key map (a 1997 bug);
  ask us instead if you want a key changed.
- Save in the garage with **SAVE BOOKMARK**; load from the main menu with **TRIP -> LOAD BOOKMARK**. If you have
  no saves of your own the setup copies in a set of ours (every campaign scene from 2 to 15) so you can jump
  anywhere. Your existing saves are not touched. Those bookmarks are real play-throughs: a few start with a part
  missing (the garage's DONE then says e.g. *CAN'T GET VERY FAR WITHOUT BRAKES* - fit one from the parts list).
- The mouse wheel selects the next weapon (up) and fires hardpoint 5 (down).
- Gamepad: left stick steers and drives, right stick glances, triggers fire, LB is a shift layer (the PDF has
  the diagram). Wheels: steer and pedals work as analog axes.

## What to look at, and what to tell us

Send your answers, screenshots and `mciproxy.log` to whoever gave you this kit.

1. **Terrain popping** (the main thing we want checked). Start `PLAY-T05.bat`, press `F6` for the hood view and drive
   the road up over the ridge and down to the barn (about two minutes; `I` starts the engine if it is off). Watch
   the ground a few hundred metres ahead: do hills change shape, "step" or pop as you approach? Does the far edge
   of the world look odd? Then do the same drive with `PLAY-PREVIEW-T05.bat`. Is it smoother? Do you see any
   sliding or wobbling of the far ground, flicker in the shading, or does the fade-out at the far edge look wrong?
   Which of the two would you rather play?
2. **Smoothness and feel.** Does `PLAY.bat` feel like Interstate '76 (handling, the mission 5 canyon jump near the
   start, how fast the AI cars react, how fast damage comes)? Any stutter, especially when new terrain appears?
3. **Menus.** Does the pointer land on the buttons? Does saving a bookmark (typing a name, overwriting) work? Does
   the music play in missions? Does your controller work?
4. **Your monitor.** Size, whether the picture fills it correctly (see above).

When you report, include: your monitor size and graphics card, which launcher, and the log file the game writes
in its folder on every start - **`mciproxy.log`** (what our fixes did, the display and pointer mapping, and any
crash). Screenshots help a lot.

Two things are different on the GOG Galaxy build of the game (the setup tells you which build you have): the
music comes from GOG's own player rather than our fix, and a gamepad / wheel input can lag up to one simulation
step (42 ms) behind a key press. Both are expected; we would still like to hear whether you notice the second.

## If something goes wrong

| symptom | what it usually is, and what to do |
|---|---|
| Black window, a tiny 4:3 window, or a 3dfx logo at start | dgVoodoo (the graphics layer) ignored our settings and used a global file. Delete `%APPDATA%\dgVoodoo\dgVoodoo.conf` (press Win+R, type `%APPDATA%\dgVoodoo`, Enter) and start again. |
| PLEASE STAND BY forever | You are on Remote Desktop (the 3D cannot start there - use the PC itself), or something else grabbed the screen. Close it from Task Manager, start again, send `mciproxy.log`. |
| Picture stretched / off-centre / pointer misses the buttons | `PLAY.bat --display WxH` with your monitor's real size; or try `PLAY-16x10.bat`. Tell us either way. |
| Low frame rate | `PLAY.bat --no-supersample`. Also close GOG Galaxy's overlay and any screen-recording / RGB software. There is no fps counter in the game; "smooth or not" is what we want to hear. |
| No music in missions | On the Galaxy build of the game GOG's own music player is used (our fix cannot attach there): check that the game folder has a `music` folder with `2.mp3` ... `17.mp3`, and the AUDIO slider in the game's options. On the other build our fix plays the tracks. |
| Gamepad / wheel has no buttons | Plug it in before starting. The button layer needs our key layout (the default). |
| The game crashes | Send `mciproxy.log` - a line starting `CRASH:` says where. (One harmless `CRASH ... exe+0x99997` line at the very start is normal on the Galaxy build: a 1997 CPU-speed probe that Windows refuses; the game handles it itself.) |
| Windows SmartScreen / antivirus complains | The scripts are unsigned: *More info* -> *Run anyway*. Some scanners flag dgVoodoo's DLLs - a known false positive; the files are byte-identical to Dege's release (hashes in `_i76e\MD5SUMS`). |
| "Access denied" during the setup | The folder is under Program Files: run `PLAY.bat` as administrator once, or install the game somewhere you own. |

## Uninstall

Run `UNINSTALL-i76e.bat` (close the game first). It restores the original `i76.exe`, `i76shell.dll`, `Strlkup.dll`,
`input.map`, `I76PLYR.DEF` (the options) and GOG's Glide files from the copies the setup kept, and removes what the setup added (tested: after it,
every one of the GOG install's 371 files is byte-identical to a fresh install). Then delete the `PLAY*.bat` files,
`README-PATCH-KIT.md` and the `_i76e` folder yourself. The backups it kept (`i76.exe.u32xorig`, `i76shell.dll.orig`,
`i76shell.dll.pre-i76e-keys`, `input.map.stock-*`) are safe to delete. Bookmarks stay: if the setup copied in our
set because you had none, those `save*.cmp` files and `savegame.dir` are left for you to keep or delete. GOG Galaxy's *verify / repair* does the same
job from GOG's side if you prefer.

## What is inside, and what it does to your copy

`_i76e\VERSION.txt` names the build (the repo commit) and `_i76e\MD5SUMS` every file. In the zip: our proxy DLL
(`Strlkup.dll`, the engine fixes), our mouse DLL (`u32x.dll`), our launchers, presets, key map and scripts; dgVoodoo
2.87.5 (Dege's Glide-to-Direct3D layer, unmodified, shipped as its readme allows; needed on Windows 11 build 26100.9711 and later. 2.87.3 is kept in `_i76e\dgVoodoo-2.87.3` as a fallback: to swap back, delete `_i76e\dgVoodoo`, rename the fallback folder to `dgVoodoo`, run `UNINSTALL-i76e.bat`, then `PLAY.bat --resetup`) and AutoHotkey 1.1 (GPL, for the
controller layer). Nothing from the game. The setup renames one import in your `i76.exe` and `i76shell.dll` (so
the mouse DLL can sit in between), applies our keyboard patches to `i76shell.dll`, swaps GOG's Glide DLL for
dgVoodoo's, renames GOG's 20 fps limiter DLL (`I76PATCH.DLL`, where present) to `.disabled`, replaces the key map,
sets the game's *Graphic Detail* options to the levels the developer plays with when they are still GOG's defaults (GOG's
default rear-view mirror shows only cars on a plain sky colour; the developer's shows the road and the terrain; original kept as
`I76PLYR.DEF.pre-i76e`; *Options -> Graphic Detail* in the game changes them any time), and keeps every original next to
the file it changed. The project itself: https://github.com/therealjkvalentine/i76-everywhere
