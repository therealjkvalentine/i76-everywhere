# Weapon stats — published values, and how they match memory

Source: **Local Ditch**, https://www.localditch.com/interstate-76/weapons.html — mirrored here
so it is available offline and greppable. Indexed from
[COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md).

`*` = late-game only.

## Slug throwers

| weapon | rnd/min | range m | speed m/s | weight lb | ammo | dmg/rnd | dmg/sec |
|---|---|---|---|---|---|---|---|
| 30cal Machine Gun | 600 | 150 | 900 | 32 | **2000** | 0.89 | 8.9 |
| 50cal Machine Gun | 400 | 300 | 1200 | 47 | **2000** | 1.44 | 14.2 |
| 7.62mm Machine Gun | 200 | 500 | 1500 | 91 | 4000 | 0.63 | 12.34 |
| 20mm Cannon | 60 | 150 | 400 | 69 | **350** | 4.8 | 19.12 |
| 25mm Cannon | 50 | 300 | 600 | 89 | **300** | 5.62 | 16.77 |
| 30mm Cannon | 45 | 500 | 800 | 150 | 250 | 12.82 | 25.85 |
| Hades Cannon `*` | 38 | 600 | 600 | 160 | 200 | — | — |

## SPP pods (rockets / missiles)

| weapon | rnd/min | range m | speed m/s | weight lb | ammo | dmg/rnd | dmg/sec |
|---|---|---|---|---|---|---|---|
| FireRite Rocket | 120 | 1000 | 300 | 94 | 60 | 11.9 | 23.8 |
| AIM-Nein Missile | 30 | 2000 | 900 | 169 | 15 | 22.5 | 10.67 |
| DrRadar Missile | 12 | 3000 | 200 | 208 | 10 | 38 | 8.23 |
| Cherub Missile | 12 | 4000 | 200 | 217 | 2 | — | — |

## Flamethrowers

| weapon | range m | weight lb | ammo | time to kill a bus |
|---|---|---|---|---|
| Flamethrower | 40 | 40 | 800 | 3.8 s |
| Gas Launcher | 35 | 60 | **700** | 3.3 s |
| Napalm Hose | 30 | 102 | 600 | 2.6 s |
| Pyro-Tomic `*` | 30 | 120 | 500 | — |

## Mortars

| weapon | rnd/min | range m | speed m/s | weight lb | ammo |
|---|---|---|---|---|---|
| HE Mortar | 60 | 100 | 20 | 70 | 80 |
| WP Mortar | 50 | 100 | 20 | 89 | 70 |
| Cluster Bomb | 40 | 100 | 20 | 109 | 30 |
| EZKill Mortar `*` | 30 | 100 | 20 | 123 | 40 |

## Droppers

| weapon | weight lb | ammo |
|---|---|---|
| Oil Slick | 46 | **2000** |
| Fire Dropper | 70 | 2000 |
| Land Mines | 60 | **25** |
| Blox Dropper | 139 | **10** |
| Car-E-Racer `*` | 80 | 5 |

## Hand held

| weapon | range m | speed m/s | ammo | notes |
|---|---|---|---|---|
| 45cal Automatic | 45 | 70 | 300 | five shots kill a driver (red car). Only fires while looking out of the window, using the generic weapon-fire input — not a hardpoint |

---

## Cross-check against live memory — **every value matched**

The **bold** ammo figures above were compared with the engine's own weapon definition table
(`0x005D8800`, stride `0xD8`, default ammo at `+0x7C`) and the in-mission HUD:

| weapon | published | read from the game | source |
|---|---|---|---|
| 30cal MG | 2000 | 2000 | definition table |
| 50cal MG | 2000 | 2000 | HUD |
| 25mm Cannon | 300 | 300 / 0300 | definition table + HUD |
| 20mm Cannon | 350 | 350 | definition table |
| Gas Launcher | 700 | 0700 | HUD |
| Land Mines | 25 | 0025 | HUD |
| Oil Slick | 2000 | 2000 | definition table + HUD |
| Blox Dropper | 10 | 10 | definition table |

**Eight for eight.** That is mutual corroboration: it confirms Local Ditch's numbers are taken
from the real data, and independently confirms we are reading the right structure at
`0x005D8800`. See [`i76-uncap-lab/docs/WEAPONS-MEMORY.md`](../../i76-uncap-lab/docs/WEAPONS-MEMORY.md)
for the memory layout, the live ammo array, and the GDF-name ↔ weapon mapping
(`gmlight` = 30cal MG, `gmmedium` = 50cal MG, `gcmedium` = 25mm Cannon, `gfmedium` = Gas
Launcher, `glandmin` = Land Mines, `goilslck` = Oil Slick).

**Use these tables as a search oracle.** When hunting an unknown field, the published number
tells you what value to look for — that is exactly how the ammo array was confirmed. Weight is
the obvious next lever: the CHASSIS CONFIGURATION FORM's "total weight" (2002 lb stock ABX
Leprechaun, 4301 lb for a Piranha with 90.0 armor) should decompose into chassis + these weapon
weights + armor, which would pin the armor→weight coefficient.
