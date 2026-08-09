# Asset Bible — `basic/index`

*Interstate '76 / '77 Complete Asset Bible, 4th edition. Credit: **original Asset Bible writer and DIVER**, "Happy Nitrous Delivery Services -the Ruins Project-". Source: <https://route380.stars.ne.jp/i76/resource_i76/> (`i76cab4.zip`). Converted by `tools/asset-bible-to-md.py`; see [COMMUNITY-RESOURCES.md](../COMMUNITY-RESOURCES.md).*

Original file: `basic/index.html`

---


**[T]errain Tools : to make a terrain wall or something. / - - - - - - - - - - / ( )Raise Terrain / ( )Lower Terrain / [ 0 ] : value = probably a percentage to base height of a terrain. / - - - - - - - - - - / ( )Paint Terrain / ( )Erase Terrain / [ 0 ] : value = real number of height which you want to make. / - - - - - - - - - - / / You better use Paint/Erase Terrain (must be checked to paint/erase) to edit a terrain. / You can use Erase Terrain function to restore hills which you created with [E] : Elevation Tool. / / A box in upper left shows you the height of terrain where your mouse cursor is. / / Burushes: burush type on left draw flat top terrain. / Burush type on right draw a cliffy terrain. but it works so badly... / / Function of Detail ( ) High : by default, you can not understand Height differences of terrain easily. / Check Detail:( )High and press Repaint button, it shows you height differences by colours. / / Function of Starting Display Height : Input a value and press repaint key. / The editor can handle terrain height upto 4094 but it can show you the heights only in between 0 to 1999. If you want to edit a terrain height more than 2000, input 1900 or 1800 then press repaint. / It re-draw the terrain from the height you input upto +1999 height. Area which is more than 1999 or lower than the height you input will be draw by a pattern of checker. / / Function of Grading : / from left to right [straight line] [flexible line] [move line] [make a curve] [delete line]. / Place grading line where you want to make a SLOPE automatically. / Or place grading line upon a road to make it much more smooth. / Turn on [E]:Elevation Tools and press triple circle button. It makes a smooth slope/road between start and finish point. / /**


**[S]urface Attributes / To change/paint surface, enable [S]urface Attributes and turn on [S]± ,it shows you current surface condition. / Change surface type and select a brush, paint some as you wish. Each surface type has it's own colour. / / Roughness : add an effect like you were driving on rocky surface. / DDR/sec : damage rate per second when you drive on this surface. / / Always press PEPAINT button, after you changed a value. / / A blank button in right end of brushes let you paint rectangular area by left-click and drag.with selected surface type. / /**

|  | [P]ath Toolbox : I'76 team disabled this function. Nobody can use this option. |
|---|---|

|  | You must use this function refering to complete asset bible. / To create an object, press a button in the left end then click on a terrain. Refer to the asset bible, Imput a class name (into object class file) and select Class ID. |
|---|---|
| You can input any words into Object Label to identify objects if necessary. / / Q: How to make regen point? / A: You can find the REGEN bunker in the asset bible but it is a structure. / It never work as REGEN point by itself. Please refer to [V]ehicle Layer shown below. / Bunker (regen point for melee). Class name is anbunkr1 ,Class ID is Struct 1 / X:Z=20/25 this is regen structure. |  |

|  |
|---|
| [V]ehicle Layer / Vehicle label : to identify which is what. input any words if necessary. / Vehicle class file : input a vehicle code here. / Vechicle Code : spawn is start/spawn point where you respawn when you were killed. / We need at least 1 spawn. Input regen to make repair/regen spot. / regen and spawn these are not a visible objects in a game. / Vehicle Control Source Should be checked in AI control. / / NitroPack only: To make a check point, input [check1,check2,check3..(with lower case)] for class file name. when a player drives through checks all in order, it counts up how many laps a player drove. |

| Set [W]orld Defs. |  |
|---|---|
|  | Level Discription = Mission name within 15 letters. It will be shown on a map list / For each options, please refer to World Def pages. / Music Track = Number of musick track which you want to listen in a game / Time of Day = value is 0 to 23 / Far clip dist = how far you can see in this map. |

