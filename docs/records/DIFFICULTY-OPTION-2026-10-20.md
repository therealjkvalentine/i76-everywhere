# Difficulty option: the game's own setting, wired to the melee AI (2026-10-20 night)

Owner, 2026-10-20 night: "Is the difficulty of the ai cars correct or is it tuned to the difficulty of the game menu setting ...?
Seem to be spanking all these guys", then "Shouldn't the game difficulty setting change it in the melee mode too?"

**Status.** The setting already exists in the game we ship, so no menu row was built. The proxy now reads it (code: commits
`0d3265f` and `e8e66b6`). The new mapping was measured on the host's memory, n 1 per value; the old mapping's runs measured
the same code path. The joiner check is n 1. The player-damage factor the setting already applies offline was measured,
n 2-3 per value. One proxy is staged and installed nowhere: lab `builds\difficulty-20261020\stage\STRLKUP.DLL`, md5
`5b003fd2`.

## 1. What the shipped game already has

The exe we ship, `i76.exe` `6319abf7`, is the GOG AiO descendant of Gold 1.2. It is not retail 1.0. With it ships the
shell `i76shell.dll` `a300db63`. Both carry the Gold difficulty option.

- **Main menu > OPTIONS > Play Options.** The 7th row is "Difficulty Level", drawn as Wimp / Champion / Badass. This is
  shell widget table `0x10047200`:
  - label record `0x10047410`, at x 222 / y 415;
  - value record `0x1004743c`, at x 205 / y 416, w 300 / h 12;
  - drawer `0x100141d0`: the names table `0x100471f0`, drawn at x 398;
  - click handler `0x10014250`: cycles 0 -> 1 -> 2 -> 0. The row takes clicks only, not keys, as do the other rows on
    that screen.

  The shell keeps the value in its byte `0x100477b8`:
  - `PlayerDef_Load` `0x10016f70` reads it from I76PLYR.DEF;
  - Done (`PlayOptions_Frame` `0x10014410` -> `PlayerDef_Save` `0x10017050`) writes it to **I76PLYR.DEF +0x5c**. Only one
    byte is written; +0x5d..+0x5f are stack garbage, and every reader masks with 0xff. That is why the DEFs read `00 d2 5a 13`
    and similar.
- **Pause menu > Play Options** (the exe's own Esc menu). Its handler is `0x495e40`:
  - msg 6 reads `0x654b9c`;
  - msg 7 writes it;
  - msg 8 / 9 commit to / revert from the saved copy `0x654bfc`.

  The exe loads the DEF into `0x654b40` (`player_LoadPlyrDef` `0x4970f0`, after every shell return) and saves it at
  mission end (`player_SaveDef` `0x497290`). **The pause-menu setting and the DEF byte are the same byte.** Measured
  agreement: in all 17 offline boots the live `0x654b9c` matched the DEF byte the harness wrote before boot (0, 1 and 2).
- **What the exe does with the setting.** The only code that reads `0x654b9c` (an absolute-address scan of `.text`:
  6 sites) is:
  - the handler above;
  - the player bullet factor (`weapon_BuildImpactDamage` 0x4a76a0, read at 0x4a76e8);
  - the player flame factor (0x4443a9).

  Both factors apply only when the shooter is the player (`object_IsPlayer` 0x458bf0) **and** `net_IsNetworkGame`
  0x452d20 is 0: x2.0 at Wimp, x1.0 at Champ, x0.75 at Badass. The setting does not change AI skill, aim or armour,
  and it does nothing in a network game (melee or co-op). Caveat: a read through a register base (e.g. `[0x654b40+0x5c]`)
  would not show in that scan; none is known.

### 1.1 Measured: the player's damage per hit (offline, T13)

Harness: lab `tools\difficulty\dif-run.ps1` + `dmg_probe.py`.
- Lab copy `exp-difficulty`, a copy of the release candidate, booted headless on a private desktop with preset
  tick19-42.
- The DEF byte is set before boot and restored after.
- The opening is skipped; the nearest AI-driven car is pinned 15 m in front of the player's nose; the fire byte is held.
- Every change of the target's armour + chassis is recorded.

T13 is used, not T01, because T01's opening never cleared under the harness (boot timeout, n 1). Runs where the target
never crossed the line of fire (0 hits) say nothing and are left out; 9 runs had 0 hits.

| byte | name | runs with hits | damage per hit (modal), counts | other drops |
|---|---|---|---|---|
| 0 | Wimp | 3 | **50** (4, 4, 3 hits) | 189 (1, a ram or a burst), 30 (1) |
| 1 | Champ | 2 | **25** (8, 7 hits) | 197, 3, 5 (1 each) |
| 2 | Badass | 2 | **18** (11, 10 hits) | 2 (2) |

- The default gun does 25 per round.
- 50 / 25 / 18 is x2.0 / x1.0 / x0.75, with 18.75 truncated to 18. This is exactly the factor the code applies.
- Captures: lab `captures\difficulty-20261020\t13*-d*-r*.json`.

### 1.2 What the owner has been playing on

| copy | I76PLYR.DEF +0x5c |
|---|---|
| daily driver (`Games\I76\daily-driver`) | **0 = Wimp** |
| LAN copy (`Games\I76\lan`) | **0 = Wimp** (the rest of the DEF differs from the driver's) |
| release candidate | 0 = Wimp |
| golden | 1 = Champ |

What follows from the Wimp byte:
- **Campaign.** The owner's campaign has been at Wimp: his own bullets and flame do **double** damage. That is part of
  "spanking all these guys" in single player, and it bears on any damage-balance number taken on the driver, the LAN copy
  or the release candidate since 2026-10-03.
- **Earlier lanes.** AI-DAMAGE-BALANCE's host runs (`game-aidr`) read Champ, so their numbers stand.
- **Network melee.** In AI melee the setting did nothing until now: the factor is off in network games, and the AI ran
  at the fixed skill 3. The owner's wins over AI cars in network melee are not a Wimp effect.

## 2. What this lane adds: the setting sets the melee AI skill

`music-fix/difficulty.c`, included before `aimelee.c`, provides `difficulty_ai_skill(int aim_skill)`. aimelee.c calls it
from one marked line (the DIFFICULTY HOOK, below) when it sets an AI car's skill on the host.

| byte | name | stock setSkill level | throttle / steering / aim / fire skill (read back live) |
|---|---|---|---|
| 0 | Wimp | **4** | 0.5 / 0.5 / 0.4 / 0.7 |
| 1 | Champ | **3** (unchanged: the M1 default) | 0.6 / 0.6 / 0.6 / 0.8 |
| 2 | Badass | **1** | 1.0 / 1.0 / 1.0 / 1.0 |
| any other | read as Champ (as the exe's factor does) | 3 | |

**The stock skill scale runs backwards: level 1 is the best driver and shooter, and 5 is the worst.**
- 5 is also the AI block's default.
- The constants are at 0x40bc70, filled by 0x40bd90 into ai+0xa81c / +0xa820 / +0xa824 / +0xa828 (i76-map
  `subsystems/ai.md` M23).
- **The brief's first table was backwards.** It said Wimp 2 / Champ 3 / Badass 5, which would have made Wimp the
  hardest and Badass the softest. It was built that way first (`0d3265f`). The host read-back showed level 2 = 0.8 0.8
  0.8 0.9 and level 5 = 0.4 0.4 0.2 0.6. Commit `e8e66b6` turned it round and kept the brief's step sizes: one step
  easier than Champ, two harder.
- **For the AI lane:** "skill 4-5 for a closer, rammier mix" means *weaker* drivers and shooters on this scale.
- The table `g_diff_map` is the one place to change the mapping.

Rules:
- **The host's setting rules.** Only the host runs aimelee's skill code. A joiner's DEF changes nothing on the host. A
  joiner's mirrored AI cars keep the block default (they read level 5 on the joiner, n 2), which steers nothing because
  the host drives them.
- **`I76_AIMELEE_SKILL=<1..5>`**, when set, overrides the byte (lab use; `PLAY-LAN.bat --ai-skill N` sets it, AI lane
  `4341d06`).
- **`I76_DIFFICULTY_AI=0`** gives aimelee's own value (3) whatever the byte says. The default is 1.
- **Log line**, once per arena and whenever byte, source or skill changes:
  `difficulty: <Wimp|Champ|Badass> -> AI skill N (source: DEF | env | off)`.
- **Campaign and offline Instant Melee: unchanged.** The new code is called only from the network AI tick. The
  `I76_DIFFICULTY_CAMPAIGN` switch in the brief was not built: Gold's player-damage rule is already live in the campaign
  of our exe, at whatever the DEF says. A switch would have been inert. Its useful opposite would be "campaign at x1.0
  whatever the menu says", which needs a ruling first (open item 2).

### 2.1 The hook the AI lane must keep (aimelee.c, `aim_tick`, the once-per-car skill block)

```c
            int s = difficulty_ai_skill(g_aim_skill), s0 = s;     /* DIFFICULTY HOOK (difficulty.c): Play Options byte, env overrides */
            ((void (__cdecl *)(BYTE *, int *, int *))0x0040bd90)(o, &s, &s);
            *(int *)(*(BYTE **)(*(BYTE **)(o + 0x70) + 0x108) + 0xa818) = s0 - 1;
```

- `g_aim_skill` keeps meaning "I76_AIMELEE_SKILL or 3". difficulty.c checks whether the env is set by itself.
- aimelee's start-up line still prints `skill 3` (that is g_aim_skill); the per-arena `difficulty:` line is the
  effective value.
- `strlkproxy.c` has one `#include "difficulty.c"` line before `#include "aimelee.c"`.

### 2.2 Measured (lab copies exp-difficulty = host, exp-difficulty-b = joiner)

Setup: Hope Springs 6 (`ai_hs6.lvl`, 6 AI cars), hosted headless on IPXWrapper instance E / F (UDP 54800), lab twin
`Strlkup-lab4` (`579c48aa` = `e8e66b6` + lab blocks). Harness: lab `tools\difficulty\dif_mp.py`.

| run | host DEF | joiner DEF | host log | host's 6 AI cars, level (floats) |
|---|---|---|---|---|
| m4-h0 | 0 | - | `difficulty: Wimp -> AI skill 4 (source: DEF)` | 4 (0.5 0.5 0.4 0.7), 6/6 |
| m4-h1 | 1 | - | `Champ -> AI skill 3 (source: DEF)` | 3 (0.6 0.6 0.6 0.8), 6/6 |
| m4-h2-j0 | 2 | 0 (joined) | `Badass -> AI skill 1 (source: DEF)`; joiner logs no `difficulty:` line | 1 (1.0 1.0 1.0 1.0), 6/6 |
| m4-h0-env1b | 0 | - | `Wimp -> AI skill 1 (source: env)` (I76_AIMELEE_SKILL=1) | 1, 6/6 |

- n 1 per value, n 1 for the joiner check, 0 CRASH lines.
- The first mapping (lab2) ran the same path: n 4 (Wimp 2, Champ 3, Badass 5, env 4), a joiner at Badass under a Wimp
  host, and the floats read back for 2 and 5.
- Harness trouble, not the proxy: 5 runs did not reach the host form or the main menu. The first MELEE / HOST click is
  sometimes not taken headless. These were retried and are not counted.

### 2.3 The row persists (stock shell, headless)

Harness: lab `tools\difficulty\dif_shell.py`, on exp-difficulty-b.
- Each cycle: boot, open Play Options, click the Difficulty value once, press Done, read the DEF on disk, kill, boot,
  read the shell byte after `PlayerDef_Load`.
- Play Options was opened by the shell's own pending-menu request (index 4) plus a WM_NULL to the window. A private
  desktop delivers no window messages, and `ShellWindowProc` 0x1001da10 consumes menu requests only on one. The
  OPTIONS button click set the request (0x100d21ac = 1) but it was never consumed.

Results:
- **Every click that landed is persisted:** 0 -> 1 n 2, 1 -> 2 n 2, 2 -> 0 (wrap) n 1. Disk +0x5c equalled the shell
  byte after Done. The next boot's shell byte equalled the disk byte, 5/5.
- Not counted: one click missed and one menu-open was not consumed; both were harness misses, with the byte unchanged.

**No screenshot:** private desktops capture black, and the console was not taken while the owner may play. The row's
position and drawing are the stock shell's (the widget table above).

## 3. Open

1. **Owner:** play a network AI melee at Badass and at Champ through a pack carrying this proxy. Is Badass (level 1)
   too much? Wimp is level 4, not 5 (5 = the block default: aim 0.2).
2. **Ruling wanted:** the driver, LAN copy and release candidate are at Wimp (x2 player damage offline). Set them to
   Champ, which is the reference that AI-DAMAGE-BALANCE used? Or leave them, since it is the owner's choice in the menu?
   This lane changed no player copy.
3. Not measured:
   - the factor's absence in network games (static: `net_IsNetworkGame`);
   - flame damage per tick by difficulty (static: the same factor at 0x4443a9);
   - the pause-menu cycle live (static: handler 0x495e40, same byte);
   - two machines.
4. The AI respawn path (`aim_respawn_tick` -> `g_aim_skilled[j] = 0`) goes through the same hook. It is not measured
   separately.

## 4. Files

- Repo:
  - `music-fix/difficulty.c`;
  - the hook in `music-fix/aimelee.c`;
  - the include in `music-fix/strlkproxy.c`;
  - the `music-fix/README.md` row `I76_DIFFICULTY_AI`;
  - a dated note in `AI-DAMAGE-METRICS.md`.
- Lab:
  - `tools\difficulty\` (build.sh, which builds from a commit; insert-ha.py; labblock\; dif-run.ps1 + dmg_probe.py;
    dif_mp.py; dif_shell.py; nudge.py);
  - `builds\difficulty-20261020\` (stage\STRLKUP.DLL `5b003fd2` = b1 = b2, from `e8e66b6`; lab twins; MD5SUMS; README);
  - `captures\difficulty-20261020\`;
  - copies `exp-difficulty`, `exp-difficulty-b` (VERSION.md).
