# Save format: what we READ vs what the GAME reads

*The part-by-part reconciliation of `save004.cmp` bytes against the in-game **Build and
Repair Form** + **Field Salvage** screenshots (user field run, 2026-07-14). Ground truth =
the screenshots. Statements below are graded ✅ verified / 🔧 corrected / ❓ open.*

## ✅ Verified exactly (byte ↔ screen)

| Piece | Evidence |
|---|---|
| **Armor @2044, 8×u32 tenths, order F/R/L/Rear armor then chassis** | 910,570,570,700,700,400,400,550 ↔ form shows 91/57/57/70 armor + 70/40/40/55 chassis. Perfect. |
| **Equipped-by-name block @1024 (14×30)** | Every (C) row and every PARTS/WEAPONS/SPCL form line matches a slot name, incl. wheels ("14in Rally" ↔ `wauto_1b`) |
| **Hardpoint slot map** (slot7=dropper `PP1_GDB1`, 8=#1 Top, 9=#2 Top, 10=#1 Rear) | Slot names ↔ form rows 1:1 (form lists Rear ABOVE Dropper — display order only) |
| **Empty hardpoint = literal string `"Empty"`** | slot8 = `'Empty'` ↔ form "#1 Top: EMPTY" |
| **Repair Order = the TRAILING section** after a count dword (`06`), records duplicated out of the main pool; **the game truncates the final record at EOF** (same quirk as savegame.dir) | Trailing section = 305ci V-8, 25mm, Gas Launcher, HE Mortar, 4-Wheel Disc, 4-Wheel Disc(truncated: name/type/cls/dur=150/wt=17.0 present, cond/loc cut) ↔ the form's six repair rows exactly |
| **Mr. Damage registry = the game's damage panel**, and its 2nd/3rd dwords are the panel x,y coords | WHL FR (408,119), FL (270,119), BR (408,312), BL (270,312) — a 2×2 grid |
| **Special 1/2/3 = REGISTRY order, not @1024 slot order** | Registry: X-Aust, Nitrous, Structo ↔ form Special 1/2/3 exactly; @1024 slots hold them in a different order. (Also matches field test: button 5 → key `7` fired nitrous = Special 2 ✓) |
| **Hand weapon (.45 CAL)** is implicit — nowhere in the save | No record, no slot |

## 🔧 Corrected (the old model was wrong)

| Old belief | Corrected reading |
|---|---|
| loc flag: 1/2=(C) car, 3=(R), 4=(V) van | **4 = FIELD SALVAGE** (the user-identified 4th state; scrollable lists, loc4 count 26 fits), **2 = van-ish**, 1 = car-ish. **(C) rows are NOT loc-1 records — they're the equipped-name slots**; equipping consumes records by name, and un-consumed loc-1 leftovers (e.g. a ghost `20mm Cannon 0/200` from the now-empty hardpoint) surface in SALVAGE |
| "First record train = van, later trains = repair" | One big main pool + the count-prefixed trailing repair section. Main-pool loc=3 items are NOT the repair order |
| Repair bench cap 13 (then ≥14) | The "(R)" rows in the inventory panel ARE the repair-order items (same six). The old 13/14 counts mixed in salvage records — bench cap still unknown but small (form shows ~13 visible lines) |
| Specials behave like parts | **Specials always display (V) unless equipped** (salvage specials box empty, repair shows none; non-equipped specials sit at loc 2/3/4 indiscriminately). Their cond field (15/41/100/300 with dur=0) means something else — ❓ charges/uses? |
| +104 = 12 zero bytes | Often nonzero — it mirrors the NEXT record's registry-style type code for a stretch of records = more saved runtime garbage, not semantics |

**Inventory caps (from the game's own panels, user-verified):** engines 3, suspensions 4,
brakes 4, specials 9, weapons 11, wheels 11 — counting C+V+R together; salvage is separate
and scrolls. Same-axle wheels must match (fits the save's front/rear `wauto` pair).

## ❓ Open — the calibration saves answer these (see below)

1. **Condition→color thresholds.** Percent-only bands are DISPROVEN: a no-highlight (C)
   Aim-Nein sits at 50% while a red (V) Aim-Nein sits at 0%, and salvage rows contradict any
   single cutoff. Possibly cond is not always points-vs-durability (some records hold cond >
   dur: 200/100, 300/200, 400/300...).
2. **V vs S rule for normal parts.** loc2↔(V) fits weapons/wheels/engines counts, but one
   (V) "Stock" suspension has no loc2 record — some rule beyond loc is in play.
3. ~~Weight formula~~ **SOLVED (field-calibrated 2026-07-14 with two builds):**
   `total = 2910 (Piranha chassis + driver + hand gun) + Σ mounted part weights +
   1.0 lb × armor points`. Derived from Reconfig (3986 lbs / 480 pts / 596 lbs parts) vs
   WEIGHT CAL (3727 lbs / 490 pts / 327 lbs parts); exact on both, and the editor's Weight
   box reproduces the game's 3986 on save005 byte-for-byte. The vdf@76 value (1320) is NOT
   the chassis weight. Note: the game weighs AFTER load-time mount validation — saves with
   non-fitting equipped names weigh less in-game than their stored loadout implies.
4. **@1956 triple (2,3,1), dir +16 (1 vs 8), spc cond values, the corrupt-looking
   NitrousOxide record @9588** (its tail is shifted 4 bytes — likely the same write bug
   family as the EOF truncation).

## savegame.dir: entry fully decoded (2026-07-14, second field run)

60-byte entries @0x28+60k: `file[16] | u32 (+16: 1 or 8, unknown) | u32 | u32 scene (+24) |
char[32] DISPLAY NAME (+28)`. The name is the LOAD board's line text (found live:
"Reconfig"). **Blank names are legal** — the game's own bookmarks are unnamed and get a
default "SCENE N." label (whose N doesn't always match the dword — default-label semantics
unchased; typed names supersede them, which retires the earlier label-vs-dword mystery).

**Live-observed game bug:** saving to a fresh slot wrote the dir entry as `save005` but the
file as **`save-01.cmp`** (`sprintf("save%03d", -1)` — the slot allocator returned
not-found), orphaning the bookmark: the LOAD board points at a file that doesn't exist.
Likely provoked by dir entries the editor added without the fields the allocator walks
(now written in full, including names). Repair: rename the orphan file to match its entry,
complete the truncated entry, move `save-01.cmp` out of the game's glob.

The editor now reads/writes the name field everywhere (pad labels, a Name box on the diner
check, restore recovers names from dir history), and the calibration saves land as slots
006 "COLOR CAL" / 007 "WEIGHT CAL" (save005 = the user's recovered in-game save).

**RETRACTION + the real bug (third board screenshot, 2026-07-14):** the "game drops the
last dir entry" theory was WRONG — no row was ever dropped. The 32-byte display name
**precedes** its entry (`name(save_k) @ 0x08+60k`, before `file[16] @ 0x28+60k`); writing
names at entry+28 made every board row wear the *previous* entry's name, which looked like
a missing final row (and made "COLOR CAL" load save007's bytes — confirmed by the 101.0
front-armor fingerprint). All writers corrected; the launcher-stub boot padding stays as
harmless insurance against the game's own truncating writes (a truncated final entry loses
its scene dword on disk either way — the editor completes those on save).

**Load-time mount validation:** loading a save whose equipped names don't fit the chassis
(e.g. turret-class guns on the Piranha) makes the game silently UNMOUNT them to Empty —
the equipped block is a request, not a guarantee. The stripped-car case also shows (C)
rows for records the equipped block doesn't name, so the C/V/S bucket rule is still open.

**Condition colors — the panes are NOT equal (v2 readback, 2026-07-14):**
- **Field Salvage colors are RE-ROLLED at load, not stored state.** Proven: identical
  save006 bytes produced all-red 13in Stocks in one session and green/green/red/red in the
  next. No formula against the record fields can ever fit that pane — stop trying.
- **Car/Van inventory colors ARE stable across loads** (same (R)/(V) colors in every
  session) → stored-state-derived; Repair Order colors likely encode the panel's own
  REPAIR TIME semantics rather than raw condition.
- The game **auto-mounts** mountable pool weapons into empty validated hardpoints on load
  (v2's 7.62/WP/Cluster showed up (C) uninvited) — bucket rule: (C) = post-validation,
  post-auto-fill mounted set.
- gdf fact: **offset 76 of every weapon .gdf = max HP** (same +76 position as in save
  records — the record embeds the def's field). All catalog durabilities verified correct.
- **COLOR CAL v3** targets the stable pane: seven unique TURRET-class weapons (unmountable
  on the Piranha, so they stay (V)) in the van at 10/25/40/55/70/85/100%. Readback maps
  van colors → thresholds directly.

## The calibration saves (game-as-oracle protocol)

Generated by [`../i76-calibration-saves.py`](../i76-calibration-saves.py) from save004:

- **save005 "COLOR CAL"**: the 7 salvage-pool guns are rewritten to identical `50cal MG`s
  with conditions 10/25/40/55/70/85/100%, and two salvage wheels set to 120% and 200%.
  *Field read:* open Field Salvage, list the weapon colors top to bottom (and the two odd
  wheels). One glance = the full threshold curve + the over-100% rendering. Also: the four
  salvage-pool suspensions got distinct conditions (Stock 27.5/52.5/77.5%, Sway Bars 12.5%)
  — note which ONE shows in the van (V) vs salvage → cracks the V/S rule.
- **save006 "WEIGHT CAL"**: byte-identical to save004 except FRONT armor 91.0 → 101.0.
  *Field read:* the form's total weight. (4100 + 10×k → k = armor lbs/point; chassis follows.)

Both slots got savegame.dir entries (scene 7). The old deleted save005/006 contents remain
in their timestamped backups.

## Sample saves from the wild (research, 2026-07-14)

- **Best: "Lightfoot's I'76 Save Games"** — 14 campaign `.cmp` files (missions 2–15) from
  the defunct interstate76.com, preserved raw by the Wayback Machine (Nov 2007 captures,
  `id_` URLs). Imported to `game-data/downloads/lightfoot-saves/`. ~1.3–2.6 KB each —
  notably smaller than our 6–10 KB GOG saves; likely the pre-Gold format. No savegame.dir
  archived (we can synthesize one).
- SavesForGames.com hosts a claimed 100%-complete save (RAR, no provenance); TheTechGame
  id 63063 (29 KB zip) is plausibly the same Lightfoot set repacked. Both skipped — fetch
  only if the Wayback set proves insufficient.
- Verified absent: GameFAQs (no PC saves), archive.org software items, VOGONS, GOG forums,
  ModDB. **No Nitro Riders / melee / non-Piranha saves exist publicly.** Best ask-venues:
  the VOGONS AiO-patch thread (zirkoni), Shane Peelar (I76 reverse engineer), GOG
  `interstate_series` board. GOG Galaxy cloud saves: feature doesn't exist for I76.
