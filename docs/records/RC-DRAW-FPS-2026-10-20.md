# RC draw distance, frame rate and terrain churn on T05 (2026-10-20 evening, rc-draw lane)

Owner, after playing the release candidate's PLAY-TICK set (on the lab twin, which carries the same presets): "i don't love that
we lost 120 fps and are around 99 now and the edges of the hills are still moving ... i used to be able to see the edge of the map
and barn from the top of the hill in t05 and now it doesn't draw yet from there". Redirect the same evening: "we're looking for
[the terrain] to change less not to be more granular ... it CHANGES while you are driving ... steep edges change more, things
further away change more. i think we tanked the framerate without addressing our actual problem ... the whole t05 is 99 not just
the top of the hill." Owner ruling: the tick is 41.667 ms; everything below is measured at 41.667 (P18 rows: per-frame patches,
no tick).

## Verdict

- **The missing barn and map edge come from the far clip, which is 1200 m in the RC.** The tick presets were generated from
  promotion 18's *best-wide-balanced* (I76_FAR_CLIP / ROAD_DIST / CLUTTER_DIST 1200); the owner's PLAY.bat is *best-wide*
  (1800). It wasn't the wrong variable, it was the wrong base. From the hill top (7972, 44035) the barn (T05.MSN object `bhbarn1`,
  6385, 43305) is 1747 m away, 1587 m deep in view at the stock heading. At 1800 m it is drawn; at 1200 m the ground ends short
  of it (`captures\rcdraw-20261020\shots\barn-zoom-rc1200-vs-thf1800.png`). The map edge (T05's ZMAP tile border) lies inside
  the far plane over about 21 deg of the 122 deg cockpit view at 1200 m and 33 deg at 1800 m.
- **The frame rate cost is the RC's terrain split x96 (I76_TERRAIN_LOD_A 96) together with the far distance.** On the owner's T05
  route, LOD_A 96 at 1800 m runs a 107.7 mean / 68.4 1 % low against 117.9 / 81.1 for LOD 24 at 1800 m (headless, n 3 each). Terrain
  vertices peak at 9,970 vs 7,460. At 1200 m (the RC as played) it costs nothing measurable headless (119.1 mean).
- **LOD_A 96 makes the complaint worse.** It does not reduce change; it moves it outward. Near change drops (the near
  ground is already fully split), while change at 300-900 m rises 1.6x and beyond 900 m 2x. Measured as split / merge events
  per second and as their size on screen (below), that is exactly "things further away change more".
- **What reduces the change** (all at 1800 m, tick 41.667, proxy switches default off, built from tick19g's source):
  `I76_TERRAIN_FREEZE=300,40` stops the terrain beyond 300 m from changing at all (605 -> 17 px/s on screen), and
  `I76_TERRAIN_LOD_B=4` (a 6x larger height-error threshold, fewer splits) plus `I76_TERRAIN_HYST=20` (no flip-flop around a
  threshold) halve the events again. Together (`tbf3`): 16.8 split / merge events per second instead of 40.1 (-58 %), 17 % of
  frames change shape instead of 28 %, about 1 px/s beyond 300 m instead of 605, total on-screen change -19 %. Price: the
  ground within 300 m changes 18 % more (the deferred splits are made as it comes near), and the terrain is coarser than
  LOD 24 (fewer vertices, 6.0k peak vs 7.5k). Frame rate on the hill leg (n 3, clean): median 120.1, mean 119.4, 1 % low 84.5, lowest 1 s 95: better than P18 as played (115.2 / 76.2), equal to the RC as played at 1200 m (119.1 / 85.7), far above the RC's terrain at 1800 m (107.7 / 68.4).
- **The change that remains is the near ground** (about 1,300-1,600 px/s within 300 m, every condition). Each node splits once
  as the car approaches; no threshold trick removes that. The real fix is to blend new vertices in over distance
  (geomorphing). Proposed, not built (s.7).
- **Why the gate said "120":** gate row 3 (trip route) loads bookmark save007 (T05) and reads the frame rate for 3 s right after
  DONE, while T05's scripted opening still shows the outside camera on the canyon road. On the console that view read 104.7-117
  fps on the tick launchers today (PLAY-TICK-42: 113.7 / 112), and the row passes anything within 10 % of 120. It never sees the
  cockpit on T05's long views. **New gate row 9** (`autotest\t05-route-fps.ps1`, wired into `gate-folder.ps1`) drives this
  lane's T05 route in the cockpit through the folder's own launcher and fails below 90 % of 120 on the hill leg.
- **The owner's 99 is not reproduced** by the headless runs (RC as played: 119.1 mean). Headless reads high: in the same view
  (T05's opening, PLAY-TICK-42's preset) the console gate read 112-114 and headless 120.0 (n 5), and the 120 cap hides any
  headroom. So the headless numbers rank the conditions; they are not the console's numbers. Row 9 on the console (owner away)
  will give the console's figure; where the owner reads "99" (which overlay) is open.

## 1. Setup

- Lab copy `i76-uncap-lab\exp-rcdraw` = a copy of `Games\I76\release-candidate` (robocopy, 17:04; the release candidate was only
  read). The copy's proxy stays STRLKUP-tick19g adc4fd49 and is read back before and after every boot.
- Every boot: private desktop (`tools\whole-sim-tick\deskrun.py`), I76_MUTE=1 + per-pid mute watcher, I76_SHM_SUFFIX=exp-rcdraw,
  the copy's `dgVoodoo.wide.conf` copied in as the launchers do, preset env exactly as PLAY-i76.ps1 passes it + I76MUSIC_LOG,
  plus I76_MISSION t05, I76_START_POS, I76_KEEP_ACTIVE, I76_TRAINER (god flag only), I76_FRAME_LOG.
- **Proxies.** Driving on a private desktop needs the lab drive block (keys written into the input bytes), which only the lab
  twin has, so the route boots run `builds\rc-draw-20261020\Strlkup-rcd2-lab.dll`: tick19g's source (from
  `builds\_archive\tick-range-20261020.zip`) + the lab drive block + the two new terrain switches + the lab census / shot block
  (census and shots only when asked). The release build `STRLKUP-rcd.dll` 65a62504 = tick19g's source + the two switches; built
  twice, identical apart from the PE time stamp (`run2\`, pecmp SAME). With both switches off it patches nothing that tick19g
  does not.
- **Route** (`tools\rc-draw\t05-route.json`, from T05.MSN's RSEG road data): (R) 15 s east along the canyon road from the end of
  the scripted opening (the ridge behind the intro road), then I76_START_POS puts the car on road segment 3 at (8945, 44070)
  facing west and (H) it drives segments 3 -> 4 over the hill top, past the road-closed bars, to (6895, 43910), 2.6 km toward
  the barn, at about 22 m/s. A road follower steers with duty-cycled A / D (mean 3.5 m from the road centre, max 9-10 m). Segment
  5 (to the barn) starts 150 m on, past a bridge that is not in the road data (the car fell off it in a test run).
- **fps:** the frame log's wall periods between the phase marks, 0.5 s dropped at both ends; median, mean, 1 % low (99th-percentile
  period), fewest frames in any 1 s. fps boots run without the census and with the machine to themselves (.fps-lock, no other
  i76; a boot that saw another i76 start beside it is dropped and re-run).
- **Churn** (`I76_LEAF_CENSUS`, lab twin only): after each main terrain pass the quadtree's leaf list ([0x59c560]; a leaf record
  made by 0x491810 holds its corner and size) is compared with the previous pass. A split is a leaf replaced by smaller leaves at
  its corner, a merge the reverse; leaves that enter or leave the view are not counted. Each split / merge is sized on screen as
  the coarse leaf's largest midpoint height error (heights from 0x493160) over its distance, in cockpit pixels (3440 px over
  121.7 deg), only for leaves inside the view and at least 20 m away, capped at one screen height per pass and band. Repeatability:
  the two census boots of a condition agree within about 1 %.
- Raw: `i76-uncap-lab\captures\rcdraw-20261020\runs\` (per boot: env, frame log, phase marks, samples, leaf census, proxy log,
  drive log), queue log, `shots\`, `pairs\`. Scripts: `i76-uncap-lab\tools\rc-draw\` (rcd-run.ps1, rcd_drive.py, rcd_tab.py,
  rcd_agg.py, rcd_pairs.py, rcd_zoom.py, rcd-queue.ps1, stage.ps1).

## 2. Table (T05 route, headless, tick 41.667 unless P18; each cell mean [min..max] over n boots)

**hill leg** (road segments 3 + 4 from (8945, 44070) over the hill top toward the barn, 2.6 km, ~117 s)

| condition | what | fps n | median fps | mean fps | 1 % low | lowest 1 s | terrain verts peak | churn n | splits+merges /s | frames changing % | change px/s near <300 m | mid 300-900 | far >900 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p18 | P18 as played: per-frame patches, 1800/1800/1800, LOD 24 | 3 | 119.5 [118.6..120.0] | 115.2 [111.3..118.0] | 76.2 [71.9..81.3] | 86 [80..95] | 7472 [7460..7496] | 2 | 39.7 [39.7..39.7] | 28.2 [27.9..28.6] | 1308 [1304..1312] | 516 [516..517] | 81 [80..81] | 1905 [1902..1909] |
| rc | RC as is: tick 41.667, 1200/1200/1200, LOD_A 96 / B 24 | 3 | 120.1 [120.1..120.1] | 119.1 [118.1..119.6] | 85.7 [82.3..89.4] | 101 [100..103] | 6340 [6328..6352] | 2 | 40.2 [40.2..40.2] | 28.5 [28.3..28.6] | 403 [402..403] | 842 [841..842] | 117 [117..117] | 1361 [1361..1362] |
| t24 | tick 41.667, 1800 m, LOD 24 only (P18's terrain) | 3 | 120.0 [120.0..120.1] | 117.9 [117.1..119.3] | 81.1 [78.4..85.5] | 97 [91..107] | 7461 [7451..7468] | 2 | 40.1 [39.9..40.4] | 28.3 [28.1..28.5] | 1332 [1323..1341] | 522 [520..524] | 82 [81..83] | 1936 [1924..1947] |
| t96 | tick 41.667, 1800 m, LOD_A 96 / B 24 (RC's terrain) | 3 | 112.6 [110.5..116.5] | 107.7 [105.9..111.0] | 68.4 [66.2..72.4] | 80 [73..91] | 9971 [9953..9983] | 2 | 43.5 [43.4..43.7] | 32.6 [32.3..32.9] | 416 [410..422] | 856 [855..856] | 164 [164..165] | 1436 [1429..1442] |
| tb8 | t24 with LOD_B 8 (height-error threshold 3x larger) | 2 | 120.1 [120.1..120.1] | 119.5 [119.1..119.9] | 85.8 [83.8..87.7] | 108 [105..111] | 6918 [6913..6924] | 2 | 30.9 [30.9..30.9] | 22.4 [22.4..22.5] | 1237 [1236..1238] | 502 [502..503] | 86 [86..87] | 1826 [1824..1827] |
| tb4 | t24 with LOD_B 4 (6x larger) | 0 | - | - | - | - | - | 2 | 26.6 [26.6..26.6] | 19.6 [19.5..19.6] | 1277 [1276..1278] | 440 [439..441] | 77 [77..77] | 1794 [1794..1795] |
| th20 | t24 + I76_TERRAIN_HYST 20 | 2 | 120.0 [120.0..120.1] | 118.1 [117.7..118.4] | 80.6 [80.2..81.0] | 92 [90..95] | 6894 [6884..6904] | 2 | 30.6 [30.6..30.7] | 22.6 [22.4..22.9] | 1378 [1377..1378] | 490 [488..493] | 40 [39..42] | 1908 [1904..1913] |
| th40 | t24 + I76_TERRAIN_HYST 40 | 0 | - | - | - | - | - | 2 | 25.4 [25.2..25.6] | 19.1 [19.1..19.1] | 1768 [1753..1782] | 100 [98..102] | 40 [38..42] | 1908 [1894..1922] |
| tf | t24 + I76_TERRAIN_FREEZE 600,50 | 1 | 119.8 | 114.3 | 74.0 | 64 | 7219 | 2 | 33.0 [32.9..33.0] | 24.0 [23.8..24.2] | 1335 [1330..1339] | 459 [459..459] | 5 [5..6] | 1799 [1796..1803] |
| tf3 | t24 + I76_TERRAIN_FREEZE 300,40 | 3 | 119.8 [119.7..119.8] | 116.2 [116.1..116.4] | 78.0 [77.7..78.3] | 92 [89..94] | 7119 [7098..7153] | 2 | 27.1 [27.0..27.2] | 27.7 [27.2..28.2] | 1619 [1618..1620] | 14 [11..16] | 3 [3..3] | 1635 [1634..1637] |
| thf | t24 + HYST 20 + FREEZE 600,50 | 2 | 120.0 [119.9..120.1] | 117.8 [117.2..118.5] | 80.4 [78.7..82.1] | 92 [85..99] | 6916 [6912..6919] | 3 | 27.2 [27.0..27.3] | 20.5 [20.3..20.7] | 1361 [1350..1371] | 472 [471..473] | 2 [1..3] | 1835 [1824..1844] |
| th40f | t24 + HYST 40 + FREEZE 600,50 | 0 | - | - | - | - | - | 2 | 22.2 [22.2..22.3] | 23.8 [23.3..24.3] | 1734 [1726..1743] | 84 [80..87] | 2 [1..3] | 1820 [1816..1824] |
| thb4 | t24 + LOD_B 4 + HYST 20 | 0 | - | - | - | - | - | 2 | 21.0 [20.9..21.1] | 20.3 [19.7..20.9] | 1436 [1418..1455] | 302 [299..305] | 28 [27..28] | 1766 [1746..1787] |
| tb4hf | t24 + LOD_B 4 + HYST 20 + FREEZE 600,50 | 2 | 120.2 [120.1..120.2] | 119.5 [119.4..119.5] | 85.0 [84.9..85.0] | 98 [96..99] | 6014 [6011..6017] | 2 | 19.2 [19.2..19.3] | 19.2 [18.7..19.7] | 1435 [1428..1441] | 274 [273..275] | 1 [1..1] | 1710 [1702..1717] |
| tbf3 | t24 + LOD_B 4 + HYST 20 + FREEZE 300,40 | 3 | 120.1 [120.1..120.1] | 119.4 [118.9..119.6] | 84.5 [83.7..85.4] | 95 [90..100] | 6001 [5996..6004] | 2 | 16.8 [16.8..16.8] | 17.1 [16.6..17.5] | 1573 [1566..1579] | 1 [1..1] | 0 [0..1] | 1574 [1568..1581] |

**ridge leg** (canyon road east from the mission start, 15 s, ~330 m)

| condition | what | fps n | median fps | mean fps | 1 % low | lowest 1 s | terrain verts peak | churn n | splits+merges /s | frames changing % | change px/s near <300 m | mid 300-900 | far >900 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p18 | P18 as played: per-frame patches, 1800/1800/1800, LOD 24 | 3 | 120.0 [120.0..120.1] | 120.0 [119.8..120.1] | 91.7 [87.9..97.3] | 116 [114..119] | 6493 [6491..6494] | 2 | 36.0 [35.7..36.3] | 25.9 [25.6..26.2] | 164 [163..166] | 321 [317..325] | 62 [61..63] | 548 [541..555] |
| rc | RC as is: tick 41.667, 1200/1200/1200, LOD_A 96 / B 24 | 3 | 120.0 [120.0..120.0] | 120.0 [120.0..120.0] | 108.5 [106.0..111.6] | 120 [120..120] | 4570 [4554..4592] | 2 | 44.5 [44.5..44.5] | 30.9 [30.9..31.0] | 140 [140..140] | 542 [540..545] | 159 [158..159] | 841 [838..844] |
| t24 | tick 41.667, 1800 m, LOD 24 only (P18's terrain) | 3 | 120.0 [120.0..120.0] | 120.0 [119.9..120.0] | 94.6 [91.3..99.7] | 116 [112..119] | 6491 [6488..6494] | 2 | 36.8 [36.6..37.0] | 26.5 [25.9..27.1] | 167 [166..168] | 333 [333..333] | 63 [63..63] | 563 [562..564] |
| t96 | tick 41.667, 1800 m, LOD_A 96 / B 24 (RC's terrain) | 3 | 120.0 [118.8..120.9] | 116.7 [112.1..119.9] | 80.3 [77.3..83.9] | 103 [96..115] | 8224 [8223..8225] | 2 | 46.3 [46.3..46.4] | 32.5 [32.1..33.0] | 145 [144..145] | 555 [550..560] | 165 [165..165] | 864 [858..870] |
| tb8 | t24 with LOD_B 8 (height-error threshold 3x larger) | 2 | 120.0 [120.0..120.0] | 120.0 [120.0..120.0] | 105.8 [105.8..105.9] | 120 [119..120] | 5835 [5835..5835] | 2 | 26.5 [26.4..26.7] | 20.1 [19.9..20.4] | 258 [258..259] | 277 [275..278] | 79 [79..80] | 614 [613..615] |
| tb4 | t24 with LOD_B 4 (6x larger) | 0 | - | - | - | - | - | 2 | 21.8 [21.6..22.0] | 16.9 [16.7..17.0] | 367 [362..373] | 246 [246..246] | 91 [89..94] | 705 [696..714] |
| th20 | t24 + I76_TERRAIN_HYST 20 | 2 | 120.0 [120.0..120.0] | 120.0 [120.0..120.0] | 94.9 [91.8..98.0] | 118 [116..119] | 6226 [6224..6228] | 2 | 26.4 [25.8..27.0] | 20.0 [19.5..20.5] | 226 [222..230] | 262 [261..263] | 27 [27..27] | 514 [509..519] |
| th40 | t24 + I76_TERRAIN_HYST 40 | 0 | - | - | - | - | - | 2 | 21.6 [21.5..21.6] | 16.2 [16.1..16.3] | 353 [352..354] | 70 [70..70] | 12 [12..12] | 434 [434..435] |
| tf | t24 + I76_TERRAIN_FREEZE 600,50 | 1 | 120.0 | 120.0 | 91.3 | 119 | 6364 | 2 | 33.0 [32.9..33.2] | 24.7 [24.3..25.1] | 167 [166..167] | 306 [306..306] | 0 [0..0] | 473 [472..473] |
| tf3 | t24 + I76_TERRAIN_FREEZE 300,40 | 3 | 120.0 [120.0..120.1] | 120.0 [119.8..120.1] | 90.7 [89.4..93.0] | 114 [111..117] | 6318 [6317..6319] | 1 | 28.3 | 28.6 | 330 | 0 | 0 | 330 |
| thf | t24 + HYST 20 + FREEZE 600,50 | 2 | 120.0 [120.0..120.1] | 120.0 [120.0..120.0] | 94.9 [88.9..100.9] | 118 [118..119] | 6205 [6203..6207] | 3 | 25.2 [24.5..26.1] | 19.5 [18.9..20.1] | 225 [222..230] | 252 [251..252] | 0 [0..0] | 476 [473..482] |
| th40f | t24 + HYST 40 + FREEZE 600,50 | 0 | - | - | - | - | - | 1 | 21.7 | 20.0 | 356 | 76 | 0 | 432 |
| thb4 | t24 + LOD_B 4 + HYST 20 | 0 | - | - | - | - | - | 2 | 16.5 [16.4..16.6] | 16.1 [15.0..17.1] | 531 [526..536] | 136 [136..136] | 14 [14..14] | 682 [676..687] |
| tb4hf | t24 + LOD_B 4 + HYST 20 + FREEZE 600,50 | 2 | 119.9 [119.9..119.9] | 120.0 [120.0..120.0] | 102.3 [100.8..103.8] | 119 [119..119] | 5299 [5297..5301] | 2 | 15.9 [15.8..16.0] | 14.2 [13.7..14.7] | 531 [526..536] | 127 [126..127] | 0 [0..0] | 658 [652..663] |
| tbf3 | t24 + LOD_B 4 + HYST 20 + FREEZE 300,40 | 3 | 120.0 [119.9..120.0] | 120.0 [120.0..120.0] | 105.0 [99.7..108.3] | 118 [115..120] | 5309 [5309..5309] | 2 | 13.4 [13.3..13.4] | 14.6 [14.1..15.2] | 534 [531..536] | 0 [0..0] | 0 [0..0] | 534 [531..536] |

Notes: fps rows are fps boots only (census off, machine to itself; three boots that saw another lab game start beside them were
dropped and re-run: p18 f3, tb4 f1, tf f1). Churn rows are census boots (no burst). tb4 / th40 / th40f / thb4 have no clean fps
boot; their census boots that ran alone read the same as the fps boots of their neighbours (census on / off made no difference
where both exist: t24 118.8 vs 117.9 mean, th20 118.2 vs 118.1, thf 117.9 vs 117.8). The ridge leg's churn is n 1 for tf3 and th40f
(their other ridge leg started away from the canyon road under contention; the hill legs are unaffected). Per-run rows:
`i76-uncap-lab	ools
c-draw
esults
cdraw-runs.tsv`.

## 3. The barn and the map edge (hill top, cockpit, car held by the trainer's freeze flag)

| far clip | barn (1747 m, view depth 1587 m at yaw -90) | map edge in view | picture |
|---|---|---|---|
| 1200 (RC) | not drawn: the ground ends before it | over ~21 deg of 122 (the sides; nearest edge 646 m deep) | `shots\barn-rc-look.png` |
| 1800 | drawn (the red speck at the centre of the crop, inside the hood ornament's ring), with the plain behind it and the far ridge on the left | over ~33 deg | `shots\barn-thf-look.png`, crop `shots\barn-zoom-rc1200-vs-thf1800.png` |

The shots are front-buffer dumps (the lab twin's I76_RCD_SHOT: glide2x grLfbReadRegion, 640x480, stretched back to 21:9); a
desktop capture of a private desktop is black. Binoculars were not measured: writing camera mode 2 to 0x4c2728 gives the full-dash
view, not the binoculars.

## 4. Terrain change while driving

Where it changes (hill leg, LOD 24): about 70 % of the on-screen change is within 300 m. The near ground splits as the car
reaches it. The RC's x96 moves the splits outward (near 1,330 -> 400 px/s, mid 520 -> 840, far 82 -> 117, events 40 -> 40 at
1200 m and 43 at 1800 m).

- **Hysteresis** (`I76_TERRAIN_HYST=p`): a node that was split in the previous pass is tested as if p % nearer, a leaf as if p %
  farther, so a node near its threshold no longer flips back and forth. HYST 20: events -24 %, far change halved. HYST 40: mid
  change -80 %, but the splits move nearer (near +33 %).
- **Freeze** (`I76_TERRAIN_FREEZE=f,m`): a node beyond f metres keeps the decision it had when first seen until it comes within f
  (the snapshot is refreshed every m metres of travel, and the refresh only adds nodes that were new). 600,50: far change ~0;
  300,40: mid + far ~0, near +21 %. The proxy comment first described a stepwise refresh every m metres; corrected in 74fb9f4.
- **Height-error threshold** (`I76_TERRAIN_LOD_B` below 24: fewer, not more, splits): B 8 events -23 %, B 4 -34 %; B 4 also
  trims the vertex peak 14 % and raises the 1 % low.
- **Frame pairs** (`pairs\`): `t24-route-b2-far1-zoom.png` shows two frames 17 ms apart on the hill road at LOD 24: the canyon
  wall's step and the ledge above it jump (4 splits at 300-900 m). The `*-seq.gif` files are the 5 s bursts (every 2nd frame)
  from 150 m before the hill top, for LOD 24, the RC's x96 and the candidate.

## 5. Recommendation (staged, not installed): `i76-uncap-lab\builds\rc-draw-20261020\stage\`

**Recommended (`stage\`):** every `tick19-*.psd1` of the release candidate with

| key | RC | staged | why (measured on the T05 route, hill leg) |
|---|---|---|---|
| I76_FAR_CLIP / I76_ROAD_DIST / I76_CLUTTER_DIST | 1200 | **1800** | the barn and the map edge from the hill top, as PLAY.bat |
| I76_TERRAIN_LOD_A | 96 | **removed** (= LOD 24, as promotion 18) | x96 at 1800 m: mean 107.7 vs 117.9, 1 % low 68 vs 81, mid / far change 1.6x / 2x |
| I76_TERRAIN_LOD_B | 24 | **4** | fewer splits: events -34 %, vertex peak -14 %, 1 % low up |
| I76_TERRAIN_HYST | - | **20** | no flip-flop around a threshold: events -24 % |
| I76_TERRAIN_FREEZE | - | **300,40** | terrain beyond 300 m keeps its first shape: change beyond 300 m 605 -> ~1 px/s |

plus `Interstate 76\STRLKUP.DLL` = STRLKUP-rcd 65a62504 (tick19g's source + the two switches; with the switches off it behaves as
tick19g). `stage\DIFF.txt` lists every changed line per file; `MD5SUMS.txt`. Result against the RC as played and P18 (hill leg):

| | P18 as played | RC as played (1200 m) | **staged** |
|---|---|---|---|
| view | 1800 m, barn drawn | 1200 m, no barn | **1800 m, barn drawn** |
| median / mean fps, 1 % low (headless) | 119.5 / 115.2, 76 | 120.1 / 119.1, 86 | **120.1 / 119.4, 84.5** |
| split / merge events per s | 39.7 | 40.2 | **16.8** (-58 %) |
| frames whose terrain changes | 28 % | 29 % | **17 %** |
| on-screen change beyond 300 m (px/s) | 597 | 959 | **~1** |
| on-screen change within 300 m (px/s) | 1308 | 403 | **1573** |

What the owner gives up: the ground within 300 m changes somewhat more than under P18 (+20 %; the far terrain's splits are made
up as it comes near), terrain more than 300 m away keeps the shape it had when first seen until it comes within 300 m (no
refinement while approaching), and the ground is coarser than LOD 24 (6.0k vertices peak vs 7.5k; small mounds flatter). The
canyon ridge detail that x96 was added for (lod-sweep lane) goes again.

**Alternative (`stage-alt\`):** the same without LOD_B 4 and HYST (LOD 24 as promotion 18, FREEZE 300,40 only): terrain detail as
P18 near the car, events 27.1 / s (-32 %), change beyond 300 m ~17 px/s, near +21 %, mean 116.2 / 1 % low 78.0 (n 3). Choose this
if the B 4 ground looks too flat.

**If the owner wants neither switch:** the minimal fix for both complaints of the first report is the far clip back to 1800 and
LOD_A removed (row t24 = promotion 18's terrain on the tick: mean 117.9, change as P18).

Not done here (main's job after the owner's word): installing into the release candidate, PLAY-TICK.bat = 41.667 (the owner's
ruling; the staged presets keep each launcher's tick), the console gate (rows 1-9) on the installed set.

## 6. Gate row 9

`autotest\t05-route-fps.ps1 -GameDir <folder> -Launcher <bat>` boots the launcher's own preset into T05 (PLAY-i76.ps1 -Mission
t05.msn, the folder's own STRLKUP.DLL), adds I76_START_POS / I76_FRAME_LOG / I76_TRAINER, drives this lane's route with real keys
(rcd_drive.py --input keys; the console must be free) and reports each leg's median, 1 % low and lowest 1 s. `gate-folder.ps1` row
9 (now in the default rows 1..9) fails when the hill leg's median is below 90 % of -ExpectFps or the leg covers under 2,000 m.
Dry-run only here (this lane may not take the console): `t05-route: folder ..., preset tick19-42, conf dgVoodoo.wide.conf`.

## 7. Open

- **The console's figure** for these conditions: gate row 9 at the console (owner away), at least for the RC as is, P18 and the
  staged set. Where the owner reads 99.
- **Geomorphing** (blend each new vertex from the parent's interpolated height to its own over the distance band in which its
  node splits): the only remedy for the near-ground change that is ~70-100 % of what remains. Needs the split margin per node
  at 0x4918f0; not started.
- **The look of LOD_B 4** (coarser ground, flatter small mounds) needs the owner's eyes; the alternative without it is in s.5.
- **A latent tick19g fault in a log path:** with I76_FPS_LOG set, `coop_ai_log` -> `coop_ai_object` read a stale mission-car
  object and faulted (one boot, Strlkup.dll+0x15818, frame 16356, car stuck after a fall). The owner's launchers do not set
  I76_FPS_LOG; this lane's boots stopped setting it.
- **Lab hygiene seen tonight:** while this lane held `.fps-lock`, exp-airespawn (22:51) and exp-jump (20:08) started games; the
  affected fps boots were dropped and re-run. The cleanup lane zipped `builds\tick-range-20261020` mid-run (this lane's restore
  source); the needed files were taken from the zip into `builds\rc-draw-20261020\base\`.
