# Multiplayer car check (ValidateVcf, exe 0x4b35a0): what it checks, who fails, how to play

2026-10-03. This is a static read only; the game was not launched. Inputs:
- lab `game\i76.exe` (md5 85de44a7) and `i76shell.dll` (fd96f871);
- the pristine control `i76-map\sandbox-gog\main\app` (exe 9a232dcc, shell deb41008);
- the daily driver `Games\Interstate76-2026-10-03\Interstate 76` (exe 6319abf7, shell fd96f871), read-only.

The check code is byte-identical in all three exes: 0x4b35a0..0x4b4300 and the tables 0x500050..0x500390. The shell
call sites match the pristine shell (0x1002e69c.., 0x1002f368.., 0x10028418.., 0x1001e2f0.., 0x1002d2d0..,
0x10008c50..). Existing notes agree: i76-map `data\VEHICLES.md` section 1/2, `data\notes\vcf-chain.md`,
`shell\CALLBACKS.md` rows 25-26.

## 0. Answer

- **What it checks.** It runs the legality rules on the car's own `.vcf` (points budget, banned wheels, weapons and
  mounts, duplicate specials). It also takes a CRC32 of the files the car references: `.vdf`, the three `.wdf`, every
  weapon `.gdf`, and `compnent.cdf`. There is no table of stock CRCs inside the exe. The CRC is compared between the
  two players' machines, not against stock values.
- **Daily driver: it passes.** Its `ADDON\valepre4.vcf` ("Jade's Car", md5 de680a86) is byte-identical to the lab's
  `valepre4.orig`, the unmodded file: 400x4 armour, 360x4 chassis, 160 spare = 3200 = 1600x2. Its
  `ADDON\vmxmarx3.vcf` ("Limited") is the file GOG ships in ADDON. All 68 multiplayer car variants pass the emulated
  rules as the daily driver resolves them (ADDON first).
- **The lab copies fail.** In `game` and `game-alt`, `ADDON\valepre4.vcf` (md5 83003018, armour 711..744, chassis
  755..788) adds up to 6156 points instead of 3200, so it trips flag 0x400. That car is the default (PICARD PIRANHA /
  JADE'S CAR). This explains the 8.6 freeze. The memory note about "modded ADDON car data" is true of the lab copies,
  not of the daily driver.
- **How the owner and Andrew can play.** Use the daily driver as it is. Andrew's car-related game data has to match
  byte for byte: a stock GOG `I76.ZFS` (md5 6dd57b16) and no `.vdf/.wdf/.gdf/.cdf` overrides in ADDON. Copying the
  `Interstate 76` folder does that. Nothing needs to be moved aside, and no patch is needed.

## 1. What ValidateVcf does (exe 0x4b35a0)

`int ValidateVcf(char *vcf, int enforce, u32 out[2])`. It zeroes `out`, builds a CRC32 table (MSB-first, poly
0x04C11DB7) and seeds `out[1] = 0xFFFFFFFF`. It then parses the `.vcf` with the handler table 0x500050: VCFC 0x4b3650,
SPEC 0x4b3a10, WEPN 0x4b3aa0, EXIT. It returns 1 only if the parse succeeded and the legal flag `0x5dacd0` is still 1.
`out[0]` collects the violation bits and `out[1]` the inverted CRC.

The rules below apply when `enforce != 0`. In retail, enforce is always 1 (see section 3).

| bit | rule | site |
|---|---|---|
| 0x400 | `spare + sum(armour[4]) + sum(chassis[4]) == 1600 * s`, where s = VDFC.size (+0x18 of the .vdf; 6 counts as 10, 5 as 4) | 0x4b3919 |
| 0x800 | every armour/chassis facet `>= 1600*s/32` (= 50*s) | 0x4b38da |
| 0x1000 | no front/mid/rear wheel from {wdilo_1a, wctnk_1a, wdtnk_1a, wetnk_1a, wdumy_1a, w3m113_1, wxtcf_1a, wytcb_1a}.wdf. Truck wheels {wftck_1a, wbtck_1a} are allowed only on {vmxmarx, vmxmoth, vxbus, vxmilk, vmtanker, vmcargo, vmloadms}.vdf | 0x4b3650.. (tables 0x5001c0 / 0x5001e0 / 0x5001e8) |
| 0x7f / 0x380 | a weapon whose GDFC (class, sub) is on the **host's banned-weapon list** (count -1 bans every weapon); the same SPEC id twice | WEPN 0x4b3b0b..0x4b3b5b; SPEC 0x4b3a10 |
| 0x2000 | no gtktank.gdf, gtptank.gdf or tthowitz.gdf (tank guns, howitzer) | 0x4b3b8x..0x4b3bcc |
| 0x4000 | at most one turret weapon (GDFC sub >= 100) | 0x4b3bd6 |
| 0x8000 | a dropper (GDFC class 6) must sit on an HLOC mesh-type-4 mount, and nothing else may; a turret weapon needs mount type 1 | 0x4b3bfe..0x4b3c52 |

- The banned-weapon list is set just before the check by shell_cb_25 0x4b3570 (`SetWeaponWhitelist` in CALLBACKS.md,
  but the code treats a match as a violation). Its source is the host's rules block: dword +4 is the count, +8 the
  (class, sub) pairs. The host's weapon-restriction setting can therefore reject a car that is otherwise legal.
- A WEPN whose hardpoint is not in the .vdf HLOC list, or whose gdf is `null`, is skipped. It is not flagged.
- **The CRC covers**, in order:
  - the `.vdf` (VCFC +0x10);
  - the front `.wdf` (+0x36), then the mid (+0x43, skipped when `null`) and rear (+0x50);
  - `compnent.cdf` (engines, brakes and suspension; whole file);
  - each weapon's `.gdf`.

  The files are read through the VFS (0x46ffc0), so an ADDON override counts. The `.vcf` itself and the `.vtf`
  paint are not CRC'd: the `.vcf` travels over the network and is rule-checked on arrival.

## 2. Who runs it, and against which files

1. **On each player's own PC, in the shell, before anything is sent.**
   - Host: `Net_HostSession` 0x1002f368 calls ValidateVcf at 0x1002f3d6, before `dpOpen`.
   - Joiner: 0x1002e487 calls it at 0x1002e6f5.

   The car path is `"%s%d" + ".vcf"`: an i76car.def stem plus the variant number (0x1002d2d0). A failure shows
   `Modal_VehicleRejected` 0x1000b980 and stops there. The CRC (`out[1]`, at 0x100f3554) is published as 4 bytes of
   player data (0x1002e862 / 0x1002f8b2).
2. **On the receiving exe, in game.** 0x456fb0 writes the received `.vcf` blob to `NVCL\nvcl%x.vcf` (0x455e60) and
   runs ValidateVcf on it with the session rules (0x457072). That recomputes the CRC from **the receiver's own**
   vdf/wdf/gdf/cdf. If the rules fail or `crc != the sender's published CRC`, it prints `*** %s has tried to join with
   a hacked vehicle!` and calls `dpDestroyPlayer`.

So:
- **Identical mods on both PCs pass the CRC**, because it compares the two machines and never compares against stock.
- The rules are absolute, though. A `.vcf` that breaks the budget fails everywhere, even when both PCs have it.

**Player-built cars from a save** (campaign garage, `vppt*`, `vehscn.vcf`) cannot be selected in multiplayer, so they
are never sent or checked. The multiplayer list is i76car.def's 23 stems plus numbered variants. At load, the shell
(0x10008c50) extends each stem's variant count while `addon\<stem><n+1>.vcf` exists. That is how ADDON
`valepre4.vcf` becomes a fourth valepre variant. As it happens, the daily driver's `vehscn.vcf` ("Stock (Orange)",
4800 points) and all 17 stock `vppt01..17` would fail 0x400.

## 3. No built-in bypass

- The shell's enforce flag is `0x100f1db8 = (0x100d218c == 0)` (0x10028437). `0x100d218c` is bit 5 of ShellMain
  arg 10, which the exe sets from `0x504c18` (0x4031b7).
- The exe-side check also runs only when `0x504c18 == 0`. `0x504c18` is in .bss (zero at load), and no code writes it.
  No data pointer to it was found either. It is a dead debug switch, so the check is always on.

## 4. Daily driver ADDON (read-only listing, md5)

| file | md5 | vs reference | multiplayer check |
|---|---|---|---|
| valepre4.vcf "Jade's Car" (vppirnha.vdf) | de680a8611c31ade4491d31f6aca33a5 | = lab `valepre4.orig`; not in the ZFS (stock has valepre1..3) | **pass** (3200 = 1600x2) |
| vmxmarx3.vcf "Limited" (vmxmoth.vdf) | e1a1249dc3e65887fd48e89ec6c0e5ab | = GOG pristine ADDON copy; differs from the ZFS vmxmarx3.vcf (7621f5aa) | **pass** (6400 = 1600x4, size 5 -> 4) |
| vehscn.vcf "Stock (Orange)" | 4134132951ad0c4c706c2374b0c4b2c9 | shell garage scratch file, changes with play | not selectable in multiplayer (would fail 0x400) |
| vehscn.vsf | 9f947839c897886740ebfdedbf8f52bf | garage damage state | not checked |
| a2fnsg1m.cbk, i2ayj_13.map, fullres.lst, loadgame.pcx, loadscr.pcx, DUMMY.TXT | as in MANIFEST.md | art | not checked |

- Also: `NVCL\nvcl0.vcf` (9c1c2d4f) is a leftover received car (vazamz, 3200). It passes and is overwritten per session.
- `I76.ZFS` 6dd57b16 and `I76.ZIX` baf1976e equal the GOG pristine. No `.vdf/.wdf/.gdf/.cdf` sits in ADDON, so every
  CRC'd file is stock.

Lab copies for comparison: `game\ADDON\valepre4.vcf` and `game-alt\ADDON\valepre4.vcf` are both 83003018. Their
points total 6156 against a budget of 3200, so they fail flag 0x400. The CRC is unaffected.

**Method.** Emulating the rules above on the extracted stock corpus (`i76-upscale-work\extract`, 293 .vcf) passes 179.
On the budget rules alone it passes 185 (VEHICLES.md says 187; the 2-file gap is in edge size mappings and was not
chased). The failures are AI/mission vehicles (tanks, turrets, howitzer, tractors, vppt trip cars). All 68
i76car.def variants pass: 23 stems, ADDON first.
- This is static only (n = 0 live runs). The prediction "the lab passes once valepre4 is swapped" is untested.

## 5. Guidance

**Owner + Andrew (recommended)**
1. Play from the daily driver as it is. Its car data passes, and every car in the multiplayer list passes too.
2. Andrew needs byte-identical `.vdf/.wdf/.gdf/compnent.cdf`. The simplest way is a copy of the `Interstate 76`
   folder. A GOG install of his own also works, if its `I76.ZFS` md5 is 6dd57b16 and his ADDON holds no
   vdf/wdf/gdf/cdf. A different release (CD 1.0, Nitro) may differ in gdf/cdf. The host would then drop him with
   "hacked vehicle" after he joins, rather than show the rejected box.
   - Do not copy `Lossless Scaling` or other licensed tools along with the folder.
3. The `.vcf` itself does not need to match: each car is sent over the network. Custom ADDON variants on one side only
   are fine as long as they are legal.
4. Leave the host's weapon restrictions at default, or know that a restricted weapon rejects the car.

**If armour mods return to the daily driver.** Keep them budget-legal: armour + chassis + spare = 1600 x size, each
facet >= 50 x size. Points can be moved between facets freely, so the stock Jade's Car can become 520/400/400/440 +
360x4. Note that single-player doubles armour anyway (0x463120), and multiplayer does not. If an over-budget mod is
wanted offline, the least invasive fix is a `PLAY-multiplayer.bat` that renames that one `ADDON\<car>.vcf` to `.mp-off`
before launch and back after exit, verifying the rename both ways. A copy of the stock file then has to stand in its
place, because removing `valepre4.vcf` removes the variant.

**Lab IPX rerun (8.7).**
- In both `game` and `game-alt`, swap `ADDON\valepre4.vcf` with `valepre4.orig` for the run and restore it after. The
  alternative is to pick another car in the host form.
- A proxy switch that makes slot 26 return 1 only removes the local box. The receiving exe (0x456fb0) still checks the
  rules and the CRC and drops the player, so a bypass would have to patch both the shell site and the exe check on
  every PC. Not recommended for play with Andrew.
