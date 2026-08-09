# Master sitemap — every known Interstate '76 community site and its contents

A complete, per-site inventory so a question like *"has anyone already published X?"* can be
answered by grepping this file instead of re-crawling the web.

Companion to [COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md), which organises the same
material **by problem**. This file is the raw inventory.

**Mirrored** = we hold a local copy. Binaries live in `refs/` (git-ignored); converted text
lives in `docs/`.

Last crawled: **2026-08-09**.

---

## 1. I'76 Terrarium — `route380.stars.ne.jp`

<https://route380.stars.ne.jp/i76/resource_i76/> · author **DIVER**, "Happy Nitrous Delivery
Services -the Ruins Project-" (formerly `h2.dion.ne.jp/~ruins/`)

**The richest single source found.** Custom maps, editing tools, patches, and the Asset Bible.

### Install rules (from the site)

| edition | how |
|---|---|
| Classic I'76 | `.lvl`, `.ter`, `.npt` into `ADDON` |
| **Gold** | rename `.cbt` / `.rac` / `.cfx` → `.lvl`, put with `.ter` into `ADDON` |
| NitroPack | mission files into `miss8` **and** `miss16`; terrain into `ADDON` |

### Tools and documentation

| file | size | contents | mirrored |
|---|---|---|---|
| `i76cab4.zip` | 6.3 MB | **Complete Asset Bible 4th ed.** — 1045 files, objects + footprints + class IDs + images, 46 top-down level maps, vehicle codes | ✅ → [docs/asset-bible/](asset-bible/INDEX.md) |
| `asset.zip` | 7 KB | Asset Bible (original `asset.doc`) | ✅ → [ASSET-BIBLE.md](ASSET-BIBLE.md) |
| `i76mp_v015.zip` | 1.7 MB | **i76map printer** — renders mission files to bitmaps (`i76map_print.exe`) | ✅ *(not executed)* |
| `i76_hme_v20260321.zip` | 968 KB | HeightMap Editor for Microsoft Excel | ✅ *(not executed)* |
| `i76palette.zip` | 24 KB | per-mission palette files (M15, P01–P05, T01–T06 …) | ✅ |
| `I76edit.zip` | — | MultiPlayer Mission Builder, classic I'76 | ✅ |
| `NITRO.ZIP` | — | I'76 Arsenal Mission Builder (NitroPack) | ✅ |

### Patches / misc

| file | contents | mirrored |
|---|---|---|
| `patch_obj76.zip` | texture patch, original i76 | ✅ |
| `patch_8bit_roads.zip` | road texture patch, Nitro/Gold | ✅ |
| `i76-anti-loser.zip` | anti-cheat file detection | ✅ |
| `poem.txt` | poems, NitroPack | ✅ |

### Maps — all 40 mirrored to `refs/route380/maps/`

**★ = contains a `regen` (repair) spot** — see the count from `tools/find-regen-maps.py`.
33 of 40 have one.

| file | name | ★ regen hits |
|---|---|---|
| `drivingpark.zip` | Driving Park | ★ 17 |
| `p15race.zip` | RACE | ★ 16 |
| `b01skyd1.zip` | SkyDrag | ★ 9 |
| `nearly73km.zip` | nearly 73km | ★ 7 |
| `p15groovechasm.zip` | Groove Chasm | ★ 7 |
| `windtrail12.zip` | Wind and Trail | ★ 7 |
| `b01bdbd1.zip` | Birdie, Bar-D (hole in) 1 | ★ 6 |
| **`dojo.zip`** | **the Dojo** — duel/fight, `.cbt` + `.ter` | ★ 6 |
| `greatoval12.zip` | Great Oval v1.2 | ★ 6 |
| `nr380.zip` | Nitro Route 380 | ★ 6 |
| `p15texas.zip` | Texas v1.03 | ★ 6 |
| `slipstream12.zip` | SlipStream v1.2 | ★ 6 |
| `narrowed.zip` | narrowed road | ★ 5 |
| `p15motrx.zip` | MotorX | ★ 5 |
| `skydrag2.zip` | SkyDrag2 | ★ 5 |
| `p15frappe.zip` | Frappe Rally | ★ 4 |
| `scratch.zip` | scratch | ★ 4 |
| `b01snowdrive.zip` | Snow Drive | ★ 3 |
| `p15AppalachiaDrag.zip` | AppalachiaDrag | ★ 3 |
| `p15lonchlge.zip` | Lone's Challenge | ★ 3 |
| `GunsOnlyfixed.zip` | GunsOnly — `.cbt` + `.ter` | ★ 2 |
| `b01isle.zip` | isle | ★ 2 |
| `b01yesdg.zip` | Yes! Dog!! | ★ 2 |
| `nowhere.zip` | Nowhere N.M. — `.cbt` + `.ter` | ★ 2 |
| `ruins.zip` | Ruins | ★ 2 |
| `rustbelt.zip` | rust belt | ★ 2 |
| `suburbs.zip` | Suburbs | ★ 2 |
| `NightDD8.zip` | Night Driver DayBreak (D8) | ★ 1 |
| `p15ThunderValley.zip` | Thunder Valley | ★ 1 |
| `pitfall.zip` | pitfall (nest of Venom) | ★ 1 |
| `soccer-4n.zip` | soccer, NitroPack | ★ 1 |
| `soccer-f5.zip` | soccer, classic i76 | ★ 1 |
| `tokachi.zip` | Tokachi MuscleCar Laboratory | ★ 1 |
| `i76storymaps.zip` | **the campaign levels as `.lvl`** — A01, S01–S07, T01–T14+ | — |
| `ncrossing.zip` | nCrossing+ | — |
| `3miles.zip` | 3 miles | — |
| `b01snowdrive.zip` | Snow Drive | — |
| `GR.zip` | GR v1.2 | — |
| `oval.zip` | oval | — |
| `p15autodrom.zip` | AutoDrome | — |
| `p15Sanctuary.zip` | Sanctuary | — |
| `p15stunt1.zip` | Stunt Race | — |
| `dojo.zip` … | *(see above)* | |

---

## 2. Local Ditch — `localditch.com`

<https://www.localditch.com/interstate-76/> — the best *written* reference. Covers I'76,
Nitro Pack (8 pages) and Interstate '82 (6 pages).

| page | URL | mirrored |
|---|---|---|
| **Weapons** | `/interstate-76/weapons.html` | ✅ → [WEAPON-STATS.md](WEAPON-STATS.md) |
| Cars index | `/interstate-76/cars/index.html` | — *(23 per-car pages, stats are on the detail pages, not the index)* |
| Maps (community downloads) | `/interstate-76/maps.html` | — *(catalogue only, **no images**)* |
| Downloads | `/interstate-76/downloads.html` | — |
| Walkthrough | `/interstate-76/walkthrough.html` | — |
| FAQ | `/interstate-76/faq.html` | — |
| Story & features | `/interstate-76/story.html` | — |
| Codes & cheats | `/interstate-76/codes.html` | — |
| Trivia | `/interstate-76/trivia.html` | — |
| Screenshots | `/interstate-76/screenshots.html` | — |
| Pre-release pictures | `/interstate-76/pre-release.html` | — |
| Characters | `/interstate-76/characters.html` | — |
| Music | `/interstate-76/music.html` | — |
| Poems | `/interstate-76/poems.html` | — |
| Real locations | `/interstate-76/locations.html` | — |
| Links | `/interstate-76/links.html` | — |
| Message boards | `/interstate-76/message-boards.html` | — |
| Strategy: tips | `/interstate-76/strategy/tips.html` | — |
| Strategy: **lag aiming** | `/interstate-76/strategy/lag-aiming.html` | — |
| Strategy: **lag racing** | `/interstate-76/strategy/lag-racing.html` | — |
| Strategy: Q&A | `/interstate-76/strategy/questions.html` | — |
| Articles (5, dev interviews) | `/interstate-76/articles/` | — |
| Site index | `/sitemap/` | — |

## 3. Asset Bible online — `interstate76.com`

<https://interstate76.com/resources/diver/index.html> — the same Bible DIVER wrote, served as a
**nested frameset**. `index.html` → `0E1.htm`/`0E2.htm` → `0E3.html` → … A single fetch returns
only the frame wrapper. **Use the `i76cab4.zip` mirror instead**, which is a superset (4th ed.,
with images).

## 4. That Tony — `hackingonspace.blogspot.com`

| post | URL |
|---|---|
| Even More I76 Levels and Heightmaps | `/2016/08/even-more-i76-levels-and-heightmaps.html` |
| Those I76 Level Heightmaps in 3D | `/2016/08/those-i76-level-heightmaps-in-3d.html` |

The original level-format reverse engineering that `i76render` is built on.
**Gotcha:** blogspot 302-redirects to a `blogger.com/blogin` interstitial; request the redirect
target explicitly or use an archive mirror.

## 5. Code — GitHub

| project | URL | what |
|---|---|---|
| `greg-kennedy/i76render` | <https://github.com/greg-kennedy/i76render> | Perl → POV-Ray renderer. Parses `.MSN`, `.CBT`, `.RAC`, `.CF2`; emits 16-bit heightmaps for terrain, paved and dirt roads |

## 6. Video

| URL | what |
|---|---|
| <https://www.youtube.com/watch?v=-XtaR4I6U5I> | community 3D map reconstruction |
| <https://www.youtube.com/watch?v=RWRZQ53QLFo> | community 3D map reconstruction |

---

## Crawl notes (so nobody repeats the dead ends)

- **localditch `maps.html` is not a level gallery** — it is a download catalogue with no
  images. The overhead level pictures people remember are (a) the 46 `ZMAP3*/zmap6*` images
  inside `i76cab4.zip`, and (b) That Tony's heightmap renders.
- **localditch cars index has no numbers** — each of the 23 cars has its own page.
- **interstate76.com Asset Bible is un-fetchable in one request** (nested frames).
- **blogspot redirects** to a login interstitial on a plain fetch.
- Asset Bible HTML is **Japanese-authored**: decode utf-8 → cp932 → latin-1, or full-width
  punctuation turns to mojibake.

## Not yet crawled

- The 23 per-car stat pages on localditch.
- Nitro Pack and Interstate '82 sections on localditch.
- localditch `downloads.html` contents (the controls references live here).
- Whatever is at the root of `route380.stars.ne.jp/i76/` above `resource_i76/`.
