# Asset Bible — `tutorial/index`

*Interstate '76 / '77 Complete Asset Bible, 4th edition. Credit: **original Asset Bible writer and DIVER**, "Happy Nitrous Delivery Services -the Ruins Project-". Source: <https://route380.stars.ne.jp/i76/resource_i76/> (`i76cab4.zip`). Converted by `tools/asset-bible-to-md.py`; see [COMMUNITY-RESOURCES.md](../COMMUNITY-RESOURCES.md).*

Original file: `tutorial/index.html`

---

| Step 2 / / You see a green area in the upper left of the editor now 8 boxes shown in red are spawns. |  |
|---|---|
|  | If you need more than 1 area for your map, you can add areas with [T]errain Tool. / In the terrain tools window, mark the ( )Lower Terrain and choose the smallest brush, then click the white area. / It turns to green. Green square means it is enabled to play in. / / To delete an area, press button. / then click a square which you want to delete. (roads and grading lines remains.) / CAUTION : both of the map editor(I76edit.exe/arsedit.exe) do not support undo/redo. |


**Step 5 / We need some structures on a map. / All Object Codes are listed up on this I'76-I'77 complete asset bible. / Enable [O]bject Layer. / Here are some object codes from asset bible. Let's place one of them on your map.**


**(example)DINING STRUCTURES**

| Object Name |  | Class Name | X DIM | Z DIM | Class ID |
|---|---|---|---|---|---|
| Bar-D Tavern |  | bdbard1 | 28 | 23 | Struct1 |
| *Foxy Cat Topless bar |  | bdfoxy1 | 50 | 50 | Struct1 |
| Real-Lite Donuts |  | bddonut1 | 40 | 30 | Struct1 |
| Mondo Burger |  | bdmight1 | 75 | 60 | Struct1 |


**Place/move objects shown in a picture left. / Move Bar-D near the end of Unpaved Road (Green line) , place mondo burger at the end of Riverbed Road (Yellow line) / and move spawns to where 3 roads cross. / If you link roads of different type, one of a surface will disappear. / (linking paved road and unpaved one will make one paved or unpaved road.)**


**Forcus on [O]bject layer. / To move an object, press this button , then click and drag it. / To rotate an object, press then click-drag / / Now lets make a thrill-show ramp at the end of Paved Road (Red line) / Here is a sample again from Asset Bible.**


**BRIDGES AND RAMPS (notch is high end of ramp)**

| Object Name |  | Class Name | X DIM | Z DIM | Class ID |
|---|---|---|---|---|---|
| "Thrill Show" ramp(16m high) |  | aaramp1 | 20 | 42 | Ramp |
| Steel ramp (11m high) |  | aaramp2 | 20 | 36 | Ramp |
| Wood ramp (2m high) |  | aaramp3 | 20 | 15 | Ramp |
| Water tower (collapses into ramp) |  | awater1 | 5 | 5 | Ramp |

| Step 6 / Now your map has 3 roads, Bar-D, Mondo and thrill show ramp. / All spawns are came closer. / / Let's make hills/slopes with height differences. / Turn on [T]errain Tools / check ( )Paint Terrain and input 800, select the largest brush. then paint around the thrill show ramp as like right picture shows. / Also check Detail : ( ) High and press repaint button to see the height differences. |  |
|---|---|
| Paint around Mondo Burger and Bar-D with height 300 and 600. / Be sure to paint the end of a road too. plus height number 20 for where spawns are. / / Here is a grading tool (in this terrain tools), it makes similar line to road layer. / Place grading lines upon 3 roads. Grading lines are also drawn in green. / Grading makes more smooth slopes than which is made by roads. |  |


**After you placed grading lines upon roads, turn on [E]levation Toolbox / and press button. This tools can also make slopes between different heights. Your map has slopes now like a picture on the right. /**

| Let's make some mountains or hills. / Turn on * icon in Elevation toolbox and click somewhere. but do not click on glid lines. / Turn off * icon and left-click on a mountain top to change it's height from 1000 to 400 around. Once again, press this button to generate hills. |  |  |
|---|---|---|

