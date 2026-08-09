# The Complete Asset Bible — object class names, dimensions and types

Source: **DIVER, 2000** — *"More information than you would ever want to know..."*  
Mirrored from `asset.doc`. The online copy at <https://interstate76.com/resources/diver/index.html> is a nested frameset that cannot be fetched in one go, so this local parse is the usable form.

**What it is for:** levels reference objects by CLASS NAME. This table turns those codes into a real object, its footprint, and its type — which is how you read a level's contents without rendering it. `greg-kennedy/i76render` cites it for the same reason. See [COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md).

`X DIM` / `Z DIM` are the footprint in metres. `Class ID` is the engine's object class (`Struct1`, `Bridge`, `Ramp`, `Paved`, `Dirt`, …).

**Ramps carry their height in the object name** — the single most useful thing here for jump/ballistics work, since it gives a known launch height per ramp.

Parsed 224 objects across 10 categories (`tools/parse-asset-bible.py`).

---


## Commercial Structures

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Industrial park building (large) | `BCAIK[1-8]` | 65 | 30 | Struct1 |
| Industrial park building (small) | `BCAIK_S[1-8]` | 25 | 25 | Struct1 |
| 1st Bank of West Texas | `BCBANK1` | 22 | 16 | Struct1 |
| Generic general store | `BCBANK2` | 22 | 16 | Struct1 |
| Red Deacon Fireworks | `BCFIREW1` | 10 | 5 | Struct1 |
| Santana's Auto Repair | `BCGARAG1` | 30 | 35 | Struct1 |
| Krager Mags | `BCGARAG2` | 30 | 35 | Struct1 |
| State DOT garage | `BCGARAG3` | 30 | 35 | Struct1 |
| Ghost town hotel | `BCHOTEL1` | 12 | 17 | Struct1 |
| Silver Eagle Trading Post | `BCINDIA1` | 15 | 10 | Struct1 |
| Real estate office | `BCINDIA2` | 15 | 10 | Struct1 |
| Ghost town livery stable | `BCLIVRY1` | 12 | 20 | Struct1 |
| Catch-E-Na Inn | `BCNOFCB3` | 31 | 37 | Struct1 |
| AutoKare Centre | `BCOFCB3` | 35 | 36 | Struct1 |
| Post Office (Seagraves, TX) | `BCPOST1` | 18 | 21 | Struct1 |
| Empty storefront | `BCPOST2` | 18 | 21 | Struct1 |
| Dave's Tattoos | `BCTATTO1` | 15 | 10 | Struct1 |
| Generic bar | `BCTATTO2` | 15 | 10 | Struct1 |
| Warehouse (Bertoldo Imports Inc.) | `BCWWHSE1` | 24 | 42 | Struct1 |
| Warehouse (generic tan, for lease) | `BCWWHSE2` | 24 | 42 | Struct1 |
| Warehouse (Dear Jane Tractors) | `BCXWHSE1` | 24 | 41 | Struct1 |
| Warehouse (generic tan/orange) | `BCXWHSE2` | 24 | 41 | Struct1 |
| Hangar (Airfield) | `BCXWHSE5` | 35 | 41 | Struct1 |
| Warehouse (Fletcher & Sons) | `BCYWHSE1` | 24 | 41 | Struct1 |
| Warehouse (generic gray) | `BCYWHSE2` | 24 | 41 | Struct1 |
| Warehouse (JC Fasteners) | `BCYWHSE3` | 24 | 41 | Struct1 |
| Warehouse (Arnuld Petroleum Svc.) | `BCYWHSE4` | 24 | 41 | Struct1 |
| Autowerks compound gate | `BCAIKGAT` | 10 | 5 | Gate |
| Autowerks wall piece (open ends) | `BCAIKWL1` | 30 | 5 | Struct1 |
| Autowerks wall piece | `BCAIKWL2` | 30 | 5 | Struct1 |
| Autowerks wall piece "L" shaped | `BCAIKWL3` | 40 | 40 | Struct1 |
| Autowerks wall piece with sign | `BCAIKWL4` | 30 | 5 | Struct1 |
| Autowerks wall piece | `BCAIKWL5` | 10 | 5 | Struct1 |
| Autowerks wall piece (pillar) | `BCAIKWL6` | 5 | 5 | Struct1 |
| Spectator stands | `BCSTRAK1` | 75 | 30 | Struct1 |
| Pit garages | `BCSTRAK2` | 60 | 30 | Struct1 |
| Race track gate | `BCSTRAK4` | 20 | 5 | Struct1 |
| Race track corrugated metal tower | `BCSTRAK5` | 10 | 7 | Struct1 |
| Race track wall (low) | `BCSTRAK6` | 25 | 5 | Struct1 |
| Race track wall (high) | `BCSTRAK7` | 25 | 5 | Struct1 |

## Dining Structures

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Bar-D Tavern | `BDBARD1` | 28 | 23 | Struct1 |
| Intersection, dirt, branch right | `IGD27_1` | 24 | 25 | Dirt |
| Intersection, dirt, branch left | `ILD27_1` | 25 | 25 | Dirt |
| Intersection, dirt, Y junction | `IYD27_1` | 30 | 45 | Dirt |
| Intersection, dirt, trans. to nothing | `IJD27T1` | 10 | 10 | Dirt |
| Intersection, wash, branch right | `IGW29_1` | 24 | 25 | Wash |
| Intersection, wash, branch left | `ILW29_1` | 25 | 25 | Wash |
| Runway end, 03  North | `RERWEND1` | 20 | 25 | Paved |
| Runway end, 21  South | `RERWEND2` | 20 | 25 | Paved |
| Runway end, 17  North | `RERWEND3` | 20 | 25 | Paved |
| Runway end, 35  South | `RERWEND4` | 20 | 25 | Paved |
| Runway | `RMRWMID1` | 20 | 200 | Paved |

## Ambient Objects

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Barrel | `ABARREL1` | 5 | 5 | Struct2 |
| Trash can | `ACTRASH1` | 5 | 5 | Struct2 |
| Dumpster | `ADUMPST1` | 5 | 5 | Struct2 |
| End-of-road berm | `AENDRD1` | 20 | 10 | Struct2 |
| Barbed-wire fence | `AFENCE1` | 5 | 10 | String |
| Split-rail fence | `AFENCE2` | 5 | 10 | String |
| Guardrail | `AFENCE3` | 5 | 10 | String |
| Concrete barrier | `AFENCE4` | 5 | 5 | Struct2 |
| Roadblock barrier | `AFENCE5` | 30 | 5 | Struct2 |
| Stack of tires | `AITIRE1` | 5 | 5 | Struct2 |
| Car hulk | `AKWRECK1` | 5 | 10 | Struct2 |
| Car hulk on fire | `AKWRECK2` | 5 | 10 | Struct2 |
| Taurus' car, wrecked | `AKWRECK3` | 5 | 10 | Struct2 |
| Walker beam oil pump | `AMOILPM2` | 5 | 15 | Struct1 |
| Bunker (regen point for melee) | `ANBUNKR1` | 20 | 25 | Struct1 |
| Billboard (PotMan Cigarettes billboard) | `AOBILBD0` | 10 | 5 | Struct2 |
| Billboard (KSCK-FM) | `AOBILBD1` | 10 | 5 | Struct2 |
| Billboard (Manta) | `AOBILBD2` | 10 | 5 | Struct2 |
| Billboard (Gas Parade/Ropesville) | `AOBILBD3` | 10 | 5 | Struct2 |
| Billboard (Bar-D) | `AOBILBD4` | 10 | 5 | Struct2 |
| Billboard (Aces & Eights/Plains) | `AOBILBD5` | 10 | 5 | Struct2 |
| Billboard (Milky Way Motel/Plains) | `AOBILBD6` | 10 | 5 | Struct2 |
| Billboard (Giant Robot/54 mi.) | `AOBILBD7` | 10 | 5 | Struct2 |
| Billboard (Entering Texas) | `AOBILBD8` | 10 | 5 | Struct2 |
| Billboard (Entering New Mexico) | `AOBILBD9` | 10 | 5 | Struct2 |
| Phone booth | `APHONEB1` | 5 | 5 | Struct2 |
| Propane tank | `ARPROPN1` | 10 | 5 | Struct2 |
| Telephone pole | `ATPOLE1` | 5 | 5 | Struct2 |
| Hay bales | `AYHAY1` | 5 | 10 | Struct2 |
| Parking lot | `AXLOT1` | 20 | 20 | Lot |

## Signs

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| 4-way intersection sign | `SDXIN_1` | 5 | 5 | SIGN |
| "T" intersection sign | `SDTIN_1` | 5 | 5 | SIGN |
| Left pointing "T" intersection sign | `SDTIN_2` | 5 | 5 | SIGN |
| Right pointing "T" intersection sign | `SDTIN_3` | 5 | 5 | SIGN |
| "Y" intersection ahead | `SDYIN_1` | 5 | 5 | SIGN |
| Curve right | `SDTRN_1` | 5 | 5 | SIGN |
| Curve left | `SDTRN_2` | 5 | 5 | SIGN |
| "S" curve sign | `SDCRV_1` | 5 | 5 | SIGN |
| "This way out" sign | `SETWO_1` | 5 | 5 | SIGN |
| Stop sign | `SSTOP_1` | 5 | 5 | SIGN |
| Stop sign ahead sign | `SDSTP_1` | 5 | 5 | SIGN |
| County line | `SMCTY_1` | 5 | 5 | SIGN |
| Dead end sign | `SDDED_1` | 5 | 5 | SIGN |
| School zone ahead | `SDSCH_1` | 5 | 5 | SIGN |
| Speed limit 35 sign | `SL35X_1` | 5 | 5 | SIGN |
| Speed limit 50 sign | `SL50X_1` | 5 | 5 | SIGN |
| Speed limit 55 sign | `SL55X_1` | 5 | 5 | SIGN |
| Speed limit 55 sign (night) | `SL55X_2` | 5 | 5 | SIGN |
| Speed Zone ahead | `SLZON_1` | 5 | 5 | SIGN |
| Speed checked by aircraft | `SLACF_1` | 5 | 5 | SIGN |
| Armadillo X-ing | `SDARM_1` | 5 | 5 | SIGN |
| Landslide area | `SDROC_1` | 5 | 5 | SIGN |
| Landslide road closed horse | `SDRCL_1` | 5 | 5 | SIGN |
| Road construction 500 ft sign | `SDCON_1` | 5 | 5 | SIGN |
| Detour arrow horse | `SEDET_1` | 5 | 5 | SIGN |
| Black/yellow construction horse | `SWEND_1` | 5 | 5 | SIGN |
| Bridge out horse | `SDBRD_1` | 5 | 5 | SIGN |
| Bauxite Road | `SEBAU_1` | 5 | 5 | SIGN |
| Kerosine Road | `SEKER_1` | 5 | 5 | SIGN |
| Oilwell Road | `SEOIL_1` | 5 | 5 | SIGN |
| Texas rt. sign (South 114) | `SH11S_1` | 5 | 5 | SIGN |
| Texas rt. sign (North 114) | `SH11N_1` | 5 | 5 | SIGN |
| Texas rt. sign (East 125) | `SH12E_1` | 5 | 5 | SIGN |
| Texas rt. sign (West 125) | `SH12W_1` | 5 | 5 | SIGN |
| Texas rt. sign (North 137) | `SH13N_1` | 5 | 5 | SIGN |
| Texas rt. sign (South 137) | `SH13S_1` | 5 | 5 | SIGN |
| Texas rt. sign (North 214) | `SH21N_1` | 5 | 5 | SIGN |
| Texas rt. sign (South 214) (night) | `SH21S_1` | 5 | 5 | SIGN |
| N. Mexico rt. sign (North 125) | `SH12N_1` | 5 | 5 | SIGN |
| N. Mexico rt. sign (South 125) | `SH12S_1` | 5 | 5 | SIGN |
| N. Mexico rt. sign (North 206) | `SH20N_1` | 5 | 5 | SIGN |
| N. Mexico rt. sign (South 206) | `SH20S_1` | 5 | 5 | SIGN |
| US. Rt. (North 285) | `SH28N_1` | 5 | 5 | SIGN |
| US. Rt. (South 285) | `SH28N_1` | 5 | 5 | SIGN |
| US. Rt. (East 380) | `SH38E_1` | 5 | 5 | SIGN |
| US. Rt. (East 380) (night) | `SH38E_2` | 5 | 5 | SIGN |
| US. Rt. (North 380) | `SH38N_1` | 5 | 5 | SIGN |
| US. Rt. (South 380) | `SH38S_1` | 5 | 5 | SIGN |
| US. Rt. (West 380) | `SH38W_1` | 5 | 5 | SIGN |
| US. Rt. (West 380) (night) | `SH38W_2` | 5 | 5 | SIGN |
| US. Rt. (East 62) | `SH62E_1` | 5 | 5 | SIGN |
| US. Rt. (West 62) | `SH62E_1` | 5 | 5 | SIGN |
| US. Rt. (East 82) | `SH82E_1` | 5 | 5 | SIGN |
| US. Rt. (East 82) (night) | `SH82W_2` | 5 | 5 | SIGN |
| US. Rt. (West 82) | `SH82W_1` | 5 | 5 | SIGN |
| US. Rt. (West 82) (night) | `SH82W_2` | 5 | 5 | SIGN |
| US. Rt. (North 87) | `SH87N_1` | 5 | 5 | SIGN |
| US. Rt. (South 87) | `SH87S_1` | 5 | 5 | SIGN |
| Distance to 4 cities | `SMSEA_1` | 5 | 5 | SIGN |
| Distance to Browning | `SMBRN_1` | 5 | 5 | SIGN |
| Distance to Carlsbad | `SMCAR_1` | 5 | 5 | SIGN |
| Distance to Junction 87 | `SMJ87_1` | 5 | 5 | SIGN |
| Distance to Malachio's HQ | `SMMAL_1` | 5 | 5 | SIGN |
| Distance to Morton | `SEMOR_1` | 5 | 5 | SIGN |
| Distance to Plains | `SMPLN_1` | 5 | 5 | SIGN |
| Distance to Roswell | `SCROS_1` | 5 | 5 | SIGN |
| Distance to Seminole | `SESEM_1` | 5 | 5 | SIGN |
| Welcome to Brownfield | `SWBRN_1` | 5 | 5 | SIGN |
| Welcome to Plains | `SWPLA_1` | 5 | 5 | SIGN |
| Welcome to Ropesville | `SWROP_1` | 5 | 5 | SIGN |
| Welcome to Seagraves | `SWSEA_1` | 5 | 5 | SIGN |
| Welcome to Seminole | `SWSEM_1` | 5 | 5 | SIGN |
| Welcome to Tatum, NM. (now go home) | `SWTAT_1` | 5 | 5 | SIGN |
| Welcome to Whiteface | `SWWHT_1` | 5 | 5 | SIGN |
| Historic Pecos River Bridge | `SWPEC_1` | 5 | 5 | SIGN |
| Hope Springs rec. area | `SEHOP_1` | 5 | 5 | SIGN |
| Hot Springs arrow | `SMHOT_1` | 5 | 5 | SIGN |
| Ft. Davis ahead | `SEFTD_1` | 5 | 5 | SIGN |
| Ft. Davis arrow | `SMFTD_1` | 5 | 5 | SIGN |
| Federal stock area | `SWFED_1` | 5 | 5 | SIGN |
| Restricted area | `SWMTR_1` | 5 | 5 | SIGN |
| Danger dog on duty | `SWDOG_1` | 5 | 5 | SIGN |
| Spanners truck stop ahead | `SESPN_1` | 5 | 5 | SIGN |
| Wagon Wheel diner ahead | `SEWGW_1` | 5 | 5 | SIGN |
| Real-lite Donuts ahead | `SEDON_1` | 5 | 5 | SIGN |
| Gas/food next exit | `SEG50_1` | 5 | 5 | SIGN |
| Ranch for sale | `SMFIS_1` | 5 | 5 | SIGN |

## Miscellaneous Objects

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Parking lot floodlight | `BCZLITE1` | 2 | 1 | Struct2 |
| Streetlight | `BCZLITE2` | 1 | 5 | Struct2 |
| Area floodlight (no vis. geometry) | `BCZLITE3` | 1 | 1 | Struct2 |

## Nature

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Armadillo | `NADILLO1` | 5 | 5 | Struct2 |
| Pine tree | `NPINETR1` | 5 | 5 | Struct2 |
| Saguaro cactus | `NSAGUAR1` | 5 | 5 | Struct2 |
| Mondo Burger | `BDMIGHT1` | 75 | 60 | Struct1 |
| Ghost town saloon | `BDSALOO1` | 10 | 15 | Struct1 |
| Wagon Wheel | `BDWGNWL1` | 70 | 70 | Struct1 |
| Quick-ee Freeze | `BDZFREZ1` | 70 | 60 | Struct1 |
| Chicken stand | `BDZFREZ2` | 70 | 60 | Struct1 |
| Race track snack bar | `BCSTRAK3` | 20 | 30 | Struct1 |

## Filling Stations

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Gas4Cash | `BFGASTF1` | 70 | 50 | Struct1 |
| Spanner's Truck Stop | `BFNSPAN1` | 120 | 75 | Struct1 |
| Gas Parade | `BFPARAD1` | 110 | 65 | Struct1 |
| Gas Parade (night version) | `BFPARAD2` | 110 | 65 | Struct1 |
| Sincere Gas | `BFSINCE1` | 60 | 45 | Struct1 |

## Housing Structures

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Barn (red, closed) | `BHBARN1` | 14 | 27 | Struct1 |
| Barn (old wood, open) | `BHBARN2` | 14 | 27 | Struct1 |
| Slipstream trailer | `BHTSLIP1` | 5 | 10 | Struct1 |
| Mobile home (single, blue) | `BHGSGLW1` | 5 | 15 | Struct1 |
| Mobile home (single, green) | `BHGSGLW2` | 5 | 15 | Struct1 |
| House (1-story shotgun, yellow) | `BHHOUSE1` | 7 | 20 | Struct1 |
| House (1-story shotgun, white) | `BHHOUSE2` | 7 | 20 | Struct1 |
| House (airfield office) | `BHHOUSE4` | 7 | 20 | Struct1 |
| House (1-story w/porch) | `BHIHOUS1` | 12 | 20 | Struct1 |
| House (1-story ranch, tan) | `BHJHOUS1` | 35 | 30 | Struct1 |
| Farmhouse (2-story, white) | `BHMFARM1` | 19 | 20 | Struct1 |
| Airfield control tower | `BHWTOWR1` | 9 | 9 | Struct1 |
| Valdes County Sheriff's Substation | `BHESHER1` | 50 | 35 | Struct1 |
| Ft. Davis | `BHFTDAV1` | 100 | 75 | Struct1 |
| Jim Bowie Elementary School | `BHSCHOL1` | 55 | 70 | Struct1 |

## Bridges And Ramps

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Truss bridge (short) | `BEBRIDG1` | 10 | 100 | Bridge |
| Highway bridge (long) | `BEBRIDG2` | 10 | 80 | Bridge |
| Highway bridge (short) | `BEBRIDG3` | 10 | 60 | Bridge |
| Truss bridge (long) | `BEBRIDG4` | 10 | 160 | Bridge |
| Overpass | `BEOVRPS1` | 30 | 125 | Bridge |
| "Thrill Show" ramp (16m high) | `AARAMP1` | 20 | 42 | Ramp |
| Steel ramp (11m high) | `AARAMP2` | 20 | 36 | Ramp |
| Wood ramp (2m high) | `AARAMP3` | 20 | 15 | Ramp |
| Unfinished overpass (7m high) | `AARAMP4` | 30 | 25 | Ramp |
| Broken wooden bridge (7m high) | `AARAMP5` | 10 | 25 | Ramp |
| Unfinished overpass (7m high) Night? | `AARAMP6` | 30 | 25 | Ramp |
| Grain hopper (collapses into ramp) | `BCRHOPR1` | 10 | 10 | Ramp |
| Water tower (collapses into ramp) | `AWATERT1` | 5 | 5 | Ramp |
| Abandoned shack (collapses into ramp) | `ASHACK1` | 5 | 5 | Ramp |
| Hut (collapses into ramp) | `AHUT1` | 5 | 5 | Ramp |
| Lean-to (collapses into ramp) | `ALEANTO1` | 5 | 5 | Ramp |

## Roads & Intersections

| object | class name | X | Z | class ID |
|---|---|---:|---:|---|
| Intersection, asphalt, 4-way | `IXA21_1` | 10 | 10 | Paved |
| Intersection, asphalt, 3-way | `ITA21_1` | 10 | 10 | Paved |
| Intersection, asphalt, cul-de-sac | `ICA21_1` | 20 | 20 | Paved |
| Intersection, asphalt, branch right | `IGA21_1` | 24 | 25 | Paved |
| Intersection, asphalt, branch left | `ILA21_1` | 25 | 25 | Paved |
| Intersection, asphalt, trans. to dirt | `IJA2171` | 10 | 20 | Paved |
| Intersection, dirt, 4-way | `IXD27_1` | 10 | 10 | Dirt |
