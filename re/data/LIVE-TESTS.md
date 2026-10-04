# Live tests: edits whose in-game effect still needs confirming

Every claim in FORMATS.md / VEHICLES.md / FSM.md rests on static evidence: the instruction that reads a field.
These tests turn the most useful of them into falsifiable, measured predictions. The data track never launches the
game, so the session that owns the console runs these. Each test has a pre-built artefact.

## Protocol (applies to every test)

1. **Test copy only.** Install into `C:\Users\james\i76-uncap-lab\game` (AGENTS.md: never the playable install).
   Each `data\out\livetests\<T>\manifest.json` lists every file, its md5, its install path and the md5 of the file it
   replaces there. Back that file up (`<name>.pre-<T>`), install, run, restore, and check the restored md5.
2. **Build the artefacts:** `python data\mod\stage_livetests.py`. It is deterministic from the pristine sandbox, the
   archive and (T1 only) the test copy's `ADDON\valepre4.orig`, and every file is re-parsed after it is written.
3. **Session check first** (AGENTS.md RDP section): `[System.Windows.Forms.SystemInformation]::TerminalServerSession`
   must be False. Silence the instance (dsound stub).
4. **Read, don't watch.** Use `i76-uncap-lab\autotest\lib\memlib.ps1`. `Mem-PlayerEntity $ctx` returns the vehicle
   class-data block `veh` (the block the armour and mass offsets below are relative to).
5. **A/A first** (method gate H1): run the stock condition twice and record the spread before the edited run. Report n.
6. **Verify the write landed:** after install, compare the installed file's md5 with the manifest before launching.

```powershell
. C:\Users\james\i76-uncap-lab\autotest\lib\memlib.ps1
$ctx = Mem-Open; $v = Mem-PlayerEntity $ctx
0..7 | % { Mem-I32 $ctx ($v + 0x138 + 4*$_) }       # armour + chassis bank 1
Mem-F32 $ctx ($v + 0xa4)                             # total mass
```

## T1: armour chain, file to live entity (artefact `T1-armour-chain`)

- **Edit:** `ADDON\valepre4.vcf` (the shell-written player car) with armour 611/622/633/644 and chassis
  655/666/677/688.
- **Run:** AirBase melee (the capture-012 route, `enter-melee.ps1`). Read veh+0x138..+0x1a0.
- **Prediction:** +0x138 = 1222 1244 1266 1288 and +0x148 = 1310 1332 1354 1376. +0x158/+0x168 and +0x178/+0x18c hold
  the same values. The VCFC handler copies ×1 (0x4adac1..0x4adb69), then 0x463120 doubles for a non-network game.
- **Falsified if:** any other factor appears, or the banks differ.
- **Also proves:** the mod CLI's VCF writer produces a file the game accepts.

## T2: .vsf restore reaches which bank (no artefact yet; needs a `.vsf` context)

- **Question:** the in-game VCST handler (0x4b0350) writes saved armour to +0x138/+0x158 only, yet the live armour
  that destroys the car is +0x178 (capture 012 A/B).
- **Prediction:** after a state restore, +0x138 changes and +0x178 does not. That would mean saved damage is not
  restored to the value the damage model uses.
- **How:** find when `[0x6562c4]==2` (the .vsf path at 0x4ad7dd) and trigger it. Open item; listed so it is not lost.

## T3: total mass (no file change)

- **Prediction:** f32 veh+0xa4 equals `vehicles.csv` `mass_total` for the car driven. That is VDFC mass + ENGN + BRAK
  + SUSP masses + 2×wheel mass per wheel slot + mounted weapon masses (VEHICLES.md section 7). Jade's Piranha
  (`vppirna1.vcf`) is 1951.0.
- **Falsified if:** veh+0xa4 differs by more than float rounding. Then one of the eight additions (0x4adf0d,
  0x4b0dea, 0x4b0e3f, 0x4b0d86, 0x4ae8ec, 0x4af1b7) does something else.

## T4: far clip (artefact `T4-far-clip`, T01 with far_clip 1200)

- **Run:** TRIP mission 1 (`enter-trip1.ps1`).
- **Prediction:** f32 `[0x4c271c]` == 1200.0 once the mission is loaded; the stock value is 600.0. With the detail
  option that sets byte 0x654b8a, visible terrain reaches twice as far. Without it, the camera uses 150.
- **Falsified if:** `[0x4c271c]` stays 600, which would mean the loose `miss16\T01.MSN` is not the file loaded.

## T5: time of day (artefact `T5-hour`, T01 with hour 21)

- **Prediction:** i32 `[0x58db00]` == 7, from `((21+2)%24)*8/24`. The stock hour is listed in the manifest. The sky
  switches to night, and LOBJ lights (headlights) appear, because `light_Add` skips lights when the daylight flag is set.
- **Falsified if:** `[0x58db00]` is unchanged.

## T6: mission script injection (artefact `T6-fsm-inject`)

- **Edit:** T01 with `push 0 / arga 1 / action successAll / drop 1` at machine 0's entry, assembled by
  `fsm.assemble`. All 4,712 original instructions keep their relative jump targets; this is checked by the stager.
- **Prediction:** within about 1 s of the mission starting, i32 `[0x5244e4]` == 1, and the mission ends as won
  (fsm_RunMachines 0x4149f0 copies it into the game state).
- **Control:** stock T01 keeps `[0x5244e4]` == 0 for 60 s.
- **Falsified if:** the mission runs normally, which would mean the script chunk is not re-read or the assembler's
  output is rejected. A crash would instead point at a frame/stack error in the injection.

## T7: weapon ammo through the rebuilt archive (artefact `T7-ammo-archive`)

- **Edit:** `I76.ZFS` with `gmmedium.gdf` ammo = 1234, stored uncompressed. The other 6,115 entries are
  byte-identical and still compressed; the stager decodes and compares all of them.
- **Prediction:** a car carrying gmmedium starts with 1234 rounds. Weapon instance +0x20 (table 0x5aab08, stride 0x4c)
  == 1234, and the HUD counter shows 1234. The stock value is in the manifest.
- **Also proves:** the engine accepts a stored (method 0) entry in the middle of an otherwise LZO archive
  (loader 0x4b9bd0: `flags & 6 == 0` means raw).
- **Falsified if:** the stock ammo appears, or the archive fails to open (the hybrid repack would be wrong).

## T8: loose file over archive (artefact `T8-loose-precedence`)

- **Setup:** T7's archive plus a loose `ADDON\gmmedium.gdf` with ammo 777.
- **Prediction:** 777. The ZIX container 0 is hard-wired to `addon` (vfs_LoadZix 0x4b23e0).
- **Falsified if:** 1234, meaning the archive wins. Loose overrides would then only work for names the ZIX lists
  under container 0, and archive repacking becomes the only route for most files.

## T9: terrain height (artefact `T9-terrain-height`)

- **Edit:** `ADDON\t01.ter`, every sample +500 raw.
- **Prediction:** the player's Y at the T01 spawn is 50.0 ± 0.2 higher than stock. Height = raw × 0.1
  (terrain_GetHeightBilinear 0x493550, `fmul [0x4be8a8]`). The ZONE handler tries `addon\` first (0x4939fd).
- **Falsified if:** Y is unchanged (the addon override is not taken) or the offset is not 50 (the scale is wrong).

## T10: surface grip (artefact `T10-surface-grip`, T01 with every surface grip × 0.25)

- **Prediction:** f32 `[0x644220 + 20*i]` == 0.25 × stock for i = 0..7. From rest at full throttle, 0→20 m/s takes
  clearly longer than the stock runs (n ≥ 3 each, A/A spread reported), and 20 m/s corners slide.
- **Falsified if:** the floats read back as stock (the WRLD copy at 0x4b8b26 did not happen), or acceleration is
  unchanged within the A/A spread. That would mean surfaces[].grip is not the tyre grip the name assumes (its name is
  inferred from the formula at 0x43d240).

## Results

| test | date | n | observed | verdict |
|---|---|---|---|---|
| T1 armour chain | 2026-09-05 | 1 run (capture `012-armour`) | entity 0xc3058c0 in the AirBase melee held the eight predicted fields at +0x138..+0x1a0, each equal to the modded ADDON `.vcf` dword x2 (the sandbox loads the user's modded ADDON file: `../i76-everywhere/docs/SAVES-STATE-AND-TEST-PLAN.md:23`), engine 200 where the loader stores 100; zeroing +0x178[0] was followed by the vehicle's destruction (`status/tasks/armour-hunt.md:60-66`) | layout and values confirmed live; `armour` vs `armour_hud` naming still waits on the A/B control |
| T3 mass | 2026-10-01 | 1 | telemetry v2 read mass 1951.0 (ent+0xa4) on the sandbox Piranha, alongside engine_power 193960, drag 0.0003, health_pct 100 (`../i76-everywhere` commit `5f1d388`) | read live; the poke-and-observe half not run |
| T2, T4..T10 | | | | not run (data track does not drive the console) |
