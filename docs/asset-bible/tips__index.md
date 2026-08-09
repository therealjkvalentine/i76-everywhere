# Asset Bible — `tips/index`

*Interstate '76 / '77 Complete Asset Bible, 4th edition. Credit: **original Asset Bible writer and DIVER**, "Happy Nitrous Delivery Services -the Ruins Project-". Source: <https://route380.stars.ne.jp/i76/resource_i76/> (`i76cab4.zip`). Converted by `tools/asset-bible-to-md.py`; see [COMMUNITY-RESOURCES.md](../COMMUNITY-RESOURCES.md).*

Original file: `tips/index.html`

---

| Index |  |  |
|---|---|---|
| Diameter of Lap Counter | Regen Object | Intersections |
| Raise/Lower Terrain | Tunnel and Wall | Poem in NitroPack |

| [][][] Raise/Lower Terrain [][][] |  |
|---|---|
| Place objects to aim with paint brush. / the Effect of Raise/Lower terrain. / / Object size and size of paint brush / 15*15 in 25*25 is as equal to middle size paint brush / 20*20 in 35*35 is as equal to 2nd largest paint brush / 25*25 in 45*45 is as equal to the largest paint brush / / / You can easily make a road with Road layer and grading tool, but we might need some more natural path or a surface. / This time we also use Objects to clarify where we should aim and how large the paint brush is. / Size of the largest paint brush is 45*45 (as object size), and minimum size of a paint brush is 1 dot which is as same as 5*5 object measure (in these pictures, white dots are the smallest size.). / When you make a path by this method, place lot of objects as like it draws a road. / Then choose a correct brush. This time I did lower terrain 20 (=20% to original terrain). You might noticed that the center of a large object is signed by smaller object. Aim and click on where the white dot is in the picture. Oh wait. Before you click the center spot, click on somewhere, this prevent you from double-clicking that happens so often with raise/lower terrain. / When you scroll a window, changed a brush, input new value, click on somewhere before doing raise/lower terrain. / Raise/lower function does double-clicking selfishly soooo often. I'76editor never supports undo/redo, but here is the deal, use ERASE terrain. Erasing terrain recovers generated terrain such as mountains/hills. / / Using this method allow you to make a small mountain in a (original) mountain, or down-sized hillside in the middle of a hillside while maintaining a figure of terrain. |  |
|  |  |

| [][][] Diameter of Lap Counter [][][] |  |
|---|---|
| First of all, Object size in i76 game play is as same as which is drawn in the i76editor perfectly. / / + Red car icon in both of the editor and In-Game F10 view is Vehicle Object as Lap Counter [ check1 ]. Size of it is 10*15 / + Green Circle stands for the Area of a Lap Counter in both of the editor and your game play. / + Yellow objects are [ ixa23_1 ] paved 4way intersection. Size is 10*10 / + Red lines across a image are paved roads. Width of 2 lane road is 10 and it matches with intersection. / + Small Orange something in the middle of F10 view is Stryder. / Pictures below are much more easier to understand/make. / According to the images above, diameter of Lap Counter Circle is 55. Let's make it simple, create a single object [ bdfoxy1 ]. It is Foxy Cat Topless bar. Size of the bar is defined to 50*50 but input 55*55. Also select Paved Intersection for Class ID. It shows only surface of the bar. / Yes, it matches with the circle. / Sadly, you do or not, size of an object is defined not in i76editor. No matter what value you input in the editor, it will appear as 50*50 in your game. Compared to intersections above, [ bdfoxy1 ] appeard as 50*50. Editor image on left = 50*50. / You better input 55*55 for [ bdfoxy1 ] to figure out the area of every checkpoints in both of the editor and F10view. |  |
| / This picture shows relationship between height and zone of lap counter. / Lap Counter was placed on height Zero. Roads you see in this picture are Bridges. / This time, I drive above the counter by using bridges. Length of a bridge is 80, width of them is same as a road =10.. / From outer to inner circle, these bridges were placed on +50 +100 +150 +200 +250 +280 terrain. / Picture shows higher you drive through the lapcounter on 0 height, zone of lap counter will be smaller. / [ check* ] is probably a closed ball or alike. / It covers 280 terrain measure up and low. / But when you drive through the area where 280 terrain measure up from a lap counter, the area has only 15 object measure and for 280 low from the counter, you have only 5 object measure space to be counted. Which is the same width of half a road. / minimum terrain measure (1 square) is as equal as 5*5 object measure. / Diameter of lap counter is 55 object measure so I said in this article, but it covers +/-280 hight.... 55 and 280 is not same I know. Probably, measure of Height and width of terrain is not same in I'76. / As a conclusion you might knew, we better place check points at a BLANCH. not at a complex. / / |  |

| [][][] Road and Intersection [][][] / |  |  |
|---|---|---|
| / 4 lane road = 2 lane *2 roads / / |  |  |
|  | Q : How to make intersection? / / Make IXISECT1 (10*10) object in the editor (its asphalt / 4-way4 intersection), then make 4 linked 2 lane road. / Drag point 1 on a border of IXISECT1 / Drag others on different border. |  |
|  | You can place roads / without linking another. / |  |
|  | Now, delete point 2. / / It's the intersection. / / Don't misuse ClassID. |  |

| [][][] Regen [][][] / |  |  |
|---|---|---|
| As a conclusion, regen (Vehicle object) covers about 20*20 object measure. (maybe 18*18 around) / 2 yellow objects are [ anbunkr1 ] (regen bunker 20*25), red one is regen. / dot shows actual (in game) regen area. / Picture below is left one. In a game, the regen works inside the bunker. / |  |  |

| [][][] Tunnel and Wall [][][] / |  |
|---|---|
|  | +Tunnel (short) [ betunnl1 ] 80*105 Struct2 / +Wooden bridge [ bewdbrg2 ] 10*80 Bridge / +wall height is 300 in surface tools. / |
|  |  |
| You might know that a wall of a tunnel can be easily destroyed and loses its role. / (I deleted a bridge before I taking a pic.) / To make a wall for a tunnel, draw terrain as like left picture shows. / But you have to avoid painting terrain for bottom left corner(marked) of an object, or it appears on 300 height wall. / Road width is 3points with the smallest paint bursh of terrain tools. / |  |

| [][][] Taurus's Poem in NitroPack [][][] / |  |
|---|---|
| Driver skin/voice is assigned by file names. / |  |
|  | Taurus / Map name start with N or n , enables Taurus. / example : nihon.cbt / |
|  | Jade / Map name start with b01 enables Jade. / example : b01race.rac / but file name MUST within 8 characters and 3 for file extention. |
|  | Skeeter / Map name start with p11 enables Skeeter. / example : p11rench.cf2 / File name have to be within 8+3, so you can not use p14wrench.cf2 (it's 9+3) |
|  | Natty Dread / Map name start with p15 enables Natty Dread. / example : p15happy.cbt / You can use only 5 alphabets free. |
|  | Groove / File name start NOT with N and other assigned words enables Groove. / Groove do NOT have a voice in NitroPack. |
| In miss8/16 folders, there are many original maps those have names start with p01 etc. / Not to let people overwrite them with your custom levels, you better name a map start with assinged 3words listed above + 5words freely + 3 for extension(.rac/.cbt). / Why do I have to use 8+3 file name? / Reason is simple, i76editor can not handle file name more than 8. If you saved ***.i76 palette file with a name more than 8letters, for example b01yoyoyo.i76, the editor will never export ***.ter (terrain file). This is not a bug, just in a specification. / / File names for C key in NitroPack / [ Jade ] rljad01.wav rljad02.wav rljad03.wav rljad04.wav rljad05.wav / { Natty Dread } rlnat01.wav rlnat02.wav rlnat03.wav rlnat04.wav rlnat05.wav / [ Skeeter ] rlske01.wav rlske02.wav rlske03.wav rlske04.wav rlske05.wav / { Taurus } rltau01.wav rltau02.wav rltau03.wav rltau04.wav rltau05.wav / / Unpack Taurus's Poem from I76.ZFS and rename them to the file name above, then drop them into addon folder of nitropack. If a map had an assigned file name, you can listen poems by hitting C key also in Multi-Melee. |  |

