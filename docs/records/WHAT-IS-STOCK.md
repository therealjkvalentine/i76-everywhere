# What "stock" means for Interstate '76 (2026-10-13)

The owner asked: "Didn't the stock game run at different fps depending on hardware? Why 24 fps in particular (20 was said
to be right at some point; we used 19.x to get jumps working)? How do we know what stock behaviour is at all, since our
hardware is so different from the 1997 target?"

Full write-up, sources and data: lab `docs/AI-COMBAT-PARITY-2026-10-13.md` (sections 1-3 and 6). This page is the summary.

## Short answers

1. **Different fps on different hardware: yes.**
   - The engine has no frame cap. WinMain renders as fast as it can, and the whole simulation runs off one clock read per
     frame: `GetTickCount`, the Windows millisecond counter.
   - So the 1997 game ran at whatever the machine managed. Every cap anybody uses (20, 24, 25, 30) was added later, by the
     community or by us.
2. **Why 24.** It is not a 1997 number. It comes from this PC's clock.
   - On Windows 10, GetTickCount only moves in steps of 15.625 ms.
   - Capped at 20 fps (what we played under GOG's I76PATCH.DLL until 2026-10-03), each 50 ms frame reads as 46.9 or 62.5 ms.
     The engine cuts frames into physics steps of at most 50 ms. Measured 2026-09-27 (i76-map capture 014), that comes to
     **24 physics steps a second**, averaging 41.7 ms.
   - That is why `I76_FIXED_STEP=24` matches the jumps and the chassis feel of "stock 20". The first try, 40 steps a
     second, landed jumps short.
3. **"stock24" and "stock20" are two names for nearly the same physics.**
   - Later lab work used `stock24` (no switches, a 24 fps cap) as "the 1997 game as played". That name was wrong: nothing
     ties 24 fps to 1997.
   - On this clock, a 24 fps cap gives the **same physics step stream** as a 20 fps cap: 46.9 / 31.25 ms steps in the same
     2:1 mix.
   - What differs is what runs once per FRAME. At 24 fps the AI makes 24 decisions a second, at 20 fps it makes 20, and the
     frame-to-frame clock pattern the AI steers by is different.
   - The lab now uses **stock20** (the capped game we actually played) as the reference.
   - `stock24` stays as a bracketing profile. The measured difference between the two is in the lab doc, section 6.
4. **19.2 fps** came from the Mac build (DxWnd, 52 ms frame delay), where it cleared the Mission 5 canyon jump.
   - On Windows, the dgVoodoo `FPSLimit 19.2` was found to do nothing. I76PATCH was the real cap, and the lab cleared the
     same jump at 60 fps.
   - The jump turned out to depend on the physics **step size**, which is what `I76_FIXED_STEP=24` fixes.
5. **What the 1997 machines really did is not measured.**
   - No period benchmark of this game was found.
   - Anecdotes suggest a Pentium 166 with a Voodoo 1 was "playable with slowdowns" (roughly 15-25 fps, varying by scene),
     and software rendering was slower.
   - Windows 95's GetTickCount is believed to tick at about **55 ms** (the PC's 18.2 Hz timer), but that is not confirmed.
     Windows 98 may tick at 10 ms or at 55 ms. NT ticks at 10 or 15.6 ms.
   - With a 55 ms tick, a 20 fps game reads most frames as 55 ms and some as 0 ms (which the engine turns into 1 ms). That
     is a very different clock from ours.

## Measured on an emulated 1997 PC (86Box, 2026-10-15)

First-hand numbers from the lab's 86Box rig. Details: `EMU-1997-PLAN.md` (run of 2026-10-14/15) and lab
`emu/results/RESULTS.md`. The rig: Windows 95 RTM 4.00.950, ASUS P/I-P55T2P4, 32 MB, S3 Trio64 + Voodoo Graphics,
86Box 6.0.

- **Windows 95's GetTickCount ticks in 1 ms steps, not 55 ms.**
  - Measured with TICKPRB, n = 3 on each of P90, P133 and P166, under both of 86Box's PIT models.
  - The step is 1 ms with and without `timeBeginPeriod`. `Sleep(1)` is the coarse part: about 13 ms without a period.
  - So item 5's "about 55 ms" and the R-1997a/b profiles' 55 ms tick are not what this Windows 95 does.
  - This is still an emulator: a real 1997 board would make it final.
- **Frame rate, Gold exe, Instant Melee (60 s starting 10 s into the mission, n = 3 unless noted):**

  | machine | Glide (Voodoo Graphics) | software renderer |
  |---|---|---|
  | P90 | 16.7 fps | 7.1 fps (n=2) |
  | P133 | 26.2 fps | 10.0 fps |
  | P166 | 31.7 fps | 13.3 fps (n=1) |

  Both paths scale with the CPU clock, so they are CPU-bound.
- **Not yet measured:**
  - the March 1997 retail exe in a mission (it asks for disc 2, which is not here);
  - T04 / T13 / T05.

## Reference profiles the lab can now reproduce on this PC

`I76_FPS_CAP` sets the frame rate. The new lab switch `I76_TICK_MS` sets the clock tick: the proxy rounds the sim clock
down to that tick in place of GetTickCount.

| profile | switches | what it stands for |
|---|---|---|
| **stock20** (the reference) | `I76_FPS_CAP=20` | stock exe, Windows 10 clock, 20 fps: GOG's I76PATCH as James played it to 2026-10-03 |
| stock24 | `I76_FPS_CAP=24` | same clock at 24 fps (lab convention 10-08..10-13) |
| R-1997a | `I76_FPS_CAP=20` + `I76_TICK_MS=55` | Windows 95 clock (if 55 ms), ~20 fps (P166 + Voodoo 1 class) |
| R-1997b | `I76_FPS_CAP=30` + `I76_TICK_MS=55` | Windows 95 clock, ~30 fps (faster 3D card) |
| R-1997c | `I76_FPS_CAP=30` + `I76_TICK_MS=10` | Windows 98 / NT 10 ms clock, ~30 fps |
| control | `I76_FPS_CAP=20` + `I76_TICK_MS=15.625` | must behave as stock20 (checks the emulation) |

## What the measurements say (lab twin, n = 5-9 per condition)

- **The emulation works.** The control profile behaves as the real clock does.
- **stock24 vs stock20:**
  - T04 racers are 0.7-1.8 s a lap slower at 24 fps;
  - the t13 attacker stays about 190 m farther away;
  - the AI makes 24 fire decisions a second instead of 20.
  The choice of reference matters.
- **Windows 95 clock (55 ms), measured on this PC:**
  - **R-1997a** (55 ms tick at 20 fps): racers lap 8 s slower, and the AI steering wobbles about 4x as much.
  - **R-1997b** (55 ms tick at 30 fps): racers barely finish a lap in 150 s. Combat AI drives at two thirds of the speed
    and hardly fires. Every second frame reads 0 ms, and the AI's one-frame steering then saturates.
  - **Conclusion:** if 1997 machines had that clock and ran above about 18 fps, the AI would have been visibly broken.
    Reviews do not describe that, so either the clock was finer or the machines ran slower. Either way, the 55 ms profiles
    are not a target.
- **R-1997c** (10 ms tick at 30 fps) is close to stock20, apart from its 30 decisions a second.
- **Decision.** **"Stock" for parity work = stock20.** The AI clock emulation (`I76_AI_STOCK_CLOCK`) now emulates the
  15.625 ms tick at 20 fps (`I76_AI_STOCK_CLOCK_FPS=20`). With it, the T04 racers lap within 0.7 s of stock20; the 24 fps
  version of this morning was 1.3-1.9 s slower.
- **The AI combat parity set** (owner test 40, `TEST-combat-parity.bat` in the lab copy) brings the AI's per-second
  decision rates back to stock20's: hazard checks, handbrake turns (whose handbrake now reaches the car), throttle ease and
  route search.

## Development hardware and targets (research 2026-10-14)

Question: what did Activision's team build and test the game on, and what frame rate did they aim for? Research only
(web, Wayback, archive.org magazine OCR, the original 1997 CD image from archive.org read offline); no game launches,
no code changes. Rule: exact quotes only where the text was read first-hand; "not found" where it was not.

### Short answer

- **No developer ever named a frame-rate number.** The only target statement is producer Scott Krager's (1996): an
  "acceptable frame rate for the minimum platform", the platform being a **Pentium 90**. Nothing from Vesce, Norman,
  Stanfill, Arnlund or Meissner names an fps figure, a physics rate, or a timer API.
- **The team's own machines are not documented anywhere found.** What exists is the shipping spec (P90 minimum, P133
  recommended), the 1997 Technical Help ("designed for use on a Intel Pentium processor"), and period user reports:
  software rendering in June 1997 was "smooth as silk" on a P166/32 MB (trip missions, all options on) and "very jerky
  and slow" on a P133 with a Matrox Millennium; the first 3Dfx/D3D build (July 1997 beta, patch 1.08b) was still "SO SLOW
  and JERKY" in cockpit view on a P166 + 3Dfx.
- **The March 1997 release had no 3D-card support at all** (software renderer, 320x240 / 480x360 / 640x480). D3D and
  3Dfx came with the summer-1997 patch series and the Gold/Nitro releases; Rendition and PowerVR with Gold/Nitro. No
  3Dfx launch-title or Voodoo bundle for I'76 was found; the one 1997 card bundle found is an **S3 ViRGE/GX** board (STB
  Nitro 3D, PC Format July 1997).
- **The 20/24/25 fps caps are all community numbers (2017-2019).** Their authors say the physics was not intentionally
  frame-tied; 24 came from folklore, 20 was chosen because the 7.62 mm MG sound breaks at 24, 25 was immi101's pick.
- **The 55 ms Windows 95 tick is corroborated only second-hand.** No Microsoft page reachable today (Learn 2025, MSDN
  2004 and 2008 captures) carries the per-OS table; it survives only in forum quotes of an older MSDN text.
- **Two corrections to the section above:** (1) the "P166 ... 22-24 fps" recollection that floats around (VOGONS 2014) is
  about **Jedi Knight**, not I'76; (2) "P166 + Voodoo 1 playable with slowdowns" has no traceable 1997 source. Nothing
  found measures the 1997 fps of this game.

### Every statement found

| # | Source (URL) | Date | Who | Quote or close paraphrase | Says about hardware / fps / timing |
|---|---|---|---|---|---|
| 1 | Gamezilla interview, mirrored at localditch.com/interstate-76/articles/gamezilla.html | 1996 (pre-release; "scheduled to ship in the last week of March") | Scott Krager (producer; Local Ditch's title) | "One major goal that we set for ourselves was to ensure that we had an acceptable frame rate for the minimum platform." "The game will run smoothly on a P90 as well as the higher-end systems." "We have devoted a lot of time to code optimization for this very reason." "Out of the box, the game will not support any specific 3D cards/devices." "we are investigating accelerated versions for after the game ships." | **The only target statement.** Minimum platform = P90; no fps number; no 3D card at ship. |
| 2 | Online Gaming Review interview, mirrored at localditch.com/interstate-76/articles/ogr.html | 1997-06-26 | Scott Krager | Engine "much faster to allow for fully textured worlds"; "We have been working on the D3D patch for a few weeks and hope to release it by May." | D3D was a post-ship patch; no hardware or fps. |
| 3 | Games Domain preview, mirrored at localditch.com/interstate-76/articles/gamesdomain.html | 1997-02 | Edward Fielding; unattributed team answers | "We used the Mech engine as a starting point"; "a new state-of-the-art real-time 3D engine that goes beyond MechWarrior." | Engine heritage only. |
| 4 | Designer's Notebook (Gamasutra / gamedeveloper.com), "Interstate '76 and the Principles of Harmony" | 1999-01-15 | Ernest Adams interviewing Sean Vesce (director) | ~23 core team in four groups, seven programmers, "programming led by Dan Stanfil"; audience "owned a high-end PC"; "re-use the Mech Warrior 2 engine to cut down on production time"; cinematics streamed from CD. | Team shape; no fps or test machines. |
| 5 | vesce.net/home/1997/03/11/interstate-76-1997/ | undated page | Sean Vesce | "We delivered the game in just under 18 months with a scrappy but amazingly talented team of 23"; "We planned to use the MechWarrior 2 engine." | Schedule; nothing on hardware. |
| 6 | Kurt Arnlund blog, potm.org/.../category-i76.php | post dated 28/03/97 (written later; site (c) 1994-2012) | Kurt Arnlund (programmer; lead on the expansions) | "We worked on I'76 for about 9 months as I remember, because that was the default production schedule in those days."; nearly done by E3 1996; wrote weapons, explosions, cockpit displays, the collision blur ("wiggle-burger"). Expansion post (18/04/98): Nitro Pack added "Direct 3D support, Glide, Rendition, and force feedback". | 3D APIs arrived with the expansions; no fps/timer. |
| 7 | MobyGames bio, mobygames.com/person/30089/kurt-arnlund/ (via Wayback) | undated | MobyGames (Arnlund-sourced) | "Along with an external contractor, Kurt made changes to allow I'76 to run on a hot new peripheral called a 3D cards which were just starting to catch on back then." | 3D support was retrofitted. |
| 8 | gameai.com games page (Wayback 2004-04-04) | c. 1997-98 | Karl Meissner (AI programmer), e-mails to Steve Woodcock | FSM script VM: "The overhead of the virtual machine is probably less than 1/2% of the CPU time so it is efficient." | Only CPU-budget remark from a programmer; no fps. |
| 9 | MobyGames credits, mobygames.com/game/347/interstate-76/credits/windows/ (via Wayback) | 1997 | credits | Directed by Sean Vesce; Produced by Scott Krager; Lead Designed/Written by Zachary Norman; **Lead Programmer Dan Stanfill**; programmers Kurt Arnlund, Scott T. Etherton, Patrick Griffith, Julio Jerez, Karl Meissner, Jean-Marc Morel, John Northan, Marshall Robin, David White, Henry Yu; QA lead Jason Wong, 14 testers, ~260 named external testers. | Names used for the search; the external test pool was large. |
| 10 | Dev Game Club ep. 427 show notes, devgameclub.com (2025-04-23) | 2025-04-23 | Sean Vesce, Zack Norman (audio interview) | Topics listed: "getting enough memory to run the games", "high polygon counts", "optimizing and making things up as you go along", engine development. | **Not listened to** (audio only, no transcript). Best remaining lead for first-hand hardware talk. |
| 11 | Original CD #1, README.HLP ("Technical Help"; archive.org item interstate-76-activision-1997, read offline) | 1997-03 (file dates 1997-03-08..13) | Activision | "Minimum System Requirements for Interstate '76 ... Processor Type: Pentium 90MHz"; 640x480 colour, card with 1 MB; "4X speed CD-ROM drive (600K/second sustained transfer rate)"; "80MB ... for minimum install and 110MB for recommended install"; "Additional 40MB ... for virtual memory if you have less than 32MB RAM"; "You may experience slower performance when playing the game using a Cyrix processor. This is partially due to the fact that Interstate '76 is designed for use on a Intel Pentium processor. Try adjusting the settings in the Graphic Detail menu within the game to get better performance."; "Orchid Righteous 3D will not play in 320x 240 mode. It should work fine in 640 x 480 and higher resolutions."; Win95 only (DOS, NT, OS/2 unsupported). | Design target = Intel Pentium; performance knob = Graphic Detail; a Voodoo card is mentioned only as a 2D pass-through issue. |
| 12 | Original CD #1, HELP.HLP and README.TXT | 1997-03 | Activision | HELP.HLP: "How can I improve performance? Close all other programs while playing."; screen savers "may loss performance"; NexGen processor workaround "will not degrade game performance". README.TXT: Matrox Millennium issue "In Full Screen mode in 320x240 or 480x360 mode". | Shipping render modes 320x240 / 480x360 / 640x480. No fps. |
| 13 | GOG install strings.txt, C:\Users\james\i76-map\sandbox-gog\main\app\strings.txt | Gold/Nitro era | Activision | "This option enables I'76 to use Direct3D function calls to speed up the game. This option was made available when you chose to install the 3D-accelerated version of the I'76 Upgrade ... if you have a Rendition or 3Dfx based 3D-graphics card, you may be able to do even better by choosing the 3Dfx or Rendition options." Same text for PowerVR. | 3D paths are an "Upgrade"; the GOG copy carries no Technical Help file (only Customer_support.htm, Manual.pdf, BUILDER.DOC). |
| 14 | Computer Gaming World #155 review (archive.org OCR, Computer_Gaming_World_Issue_155) | June 1997 | Jeff Green | Spec box: "P90, Windows 95, 16MB RAM, 80MB hard drive space, 256-color SVGA graphics, VESA Local Bus or PCI video w/1MB RAM, 4x CD-ROM"; "the forthcoming Direct 3D patch (not available as of this writing) should improve things even more"; "The 3D graphics are a generation above MechWarrior 2's"; "In the 1.0 release, gamers were randomly dropped back to Win 95 without warning. However, the game's first patch seemed to fix these crashes."; "The computer opponents, for once, seem unusually smart and agile". Designers listed: Vesce, Norman, Stanfill. | No fps, no test machine. AI praised, which matters for the 55 ms question below. |
| 15 | CGW #156 (Computer_Gaming_World_Issue_156) | July 1997 | CGW | "Interstate 76 V1.05: More than a dozen fixes make this the hippest, baddest multi-melee around-especially since the host no longer gets double kills." | Patch 1.05 = multiplayer fixes; no timing. |
| 16 | PC Gamer UK #44 cover-disc notes (archive.org OCR) | June 1997 | PC Gamer UK | Demo spec: "P100 (P133 recommended), 16Mb RAM (32Mb RAM recommended), Windows 95". | Only period source giving a **recommended** CPU in print: P133. |
| 17 | PC Format (UK) July 1997 (archive.org OCR, pcformat-1997-07) | July 1997 | PC Format | STB Nitro 3D (S3 ViRGE/GX) review: "Four games are bundled, including Interstate '76 and MechWarrior 2..."; price list cites "Interstate 76 (PCF 70, 77%)". | The only card bundle found; an S3 card, not 3Dfx. PCF #70 review not on archive.org. |
| 18 | Next Generation #23 (archive.org OCR, NextGeneration23Nov1996) | Nov 1996 | Next Generation | "Interstate '76 (see page 147) uses the MechWarrior 2 3D technology in a driving combat game."; cover: "delivers all the thrills of MechWarrior 2 with muscle cars ... protagonists remain in full polygonal glory, even in the cut-scenes". Page 147 body is missing from the OCR. | Engine heritage; preview body (Norman quotes cited by Wikipedia) not retrievable. Issues 28/29 OCR have no I'76 hit. |
| 19 | Activision I'76 Discussion Board, activision.com/cgi-bin/i76-bbs-lo.cgi?read=1200 (Wayback 1997-06-06) | 1997-06-03 | user "3mta3(go wings!)" | "playing on a P166 with 32 megs of ram. trip missions,(single player),run smooth as silk even with every graphic option maxed out. play over the net is another story. gameplay is extremly jerky" | Software renderer, P166: smooth to a 1997 eye. |
| 20 | same board, read=1203 | 1997-06-04 | user Dale Huhtala | "I'm running a P133 with a Millenium video card and I'm finding things very jerky and slow. The patch for the voodoo chip should easily take care of this" | Software renderer, P133: jerky. |
| 21 | same board, read=1216 | 1997-06-04 | user "Mr. Kotter" | "I didn't have my Monster 3D card or know that I76 would choke along with a P90 and 16 MB RAM." | P90/16 MB (the box minimum) chokes. |
| 22 | same board, read=1218 | 1997-06-04 | user Jake Roberts, relaying a Krager post on a 3Dfx board | "they are taking so long with the patch because they now have to size to a power of two all textures in the game! He even admits it was an error on their part!!" | Why 3Dfx support was late: non-power-of-two textures. Krager's original post not archived. |
| 23 | same board, read=1223 | 1997-06-05 | Derek Johnstone (Activision, non-programmer) | "I've seen the D3D patches for i76 and Mercs and they're in testing right now." | Only Activision voice archived on the board. |
| 24 | same board, read=1711, 1719, 1725, 1727 (Wayback 1997-07-07) | 1997-07-03..05 | users John Capozzi, Davo, LUX, Sundawn | Capozzi: D3D beta = "1.08b patch", tested on "PPro 200" and "K6 200"; Davo: mission 14 "really need to use the cockpit view, and it's SO SLOW and JERKY (even the D3D version with a 3Dfx and P166!!)"; LUX: on a Monster 3D "the d3d patch looks like it is going to be very helpfull in running i76 smoothly and with much more textures on my soon to be outdated p100"; Sundawn: beta has "no transparency, no mip-mapping". | First 3Dfx build, July 1997: faster but still jerky on P166 in cockpit view. |
| 25 | thecomputershow.com review/preview (Wayback) | 1996-97 | Al Giovetti | "Smooth, unjerky animation frame rate will only be achieved on the highest speed pentiums, when all graphic options are turned on." | Period expectation; no number. |
| 26 | GameSpot review, gamespot.com/reviews/interstate-76-review/1900-2535517/ (Wayback) | 1997-04-01 | Ron Dulin | "The environments and vehicles, even on the lowest detail settings, are strikingly realistic." | No fps, no hardware. |
| 27 | VOGONS "Crazy system requirements" t=40679 (Wayback) | 2014-09-09 | leileilol; filipetolhuizen | leileilol: "I recall Interstate '76 vaguely demanding for a Pentium 200-class machine when the demo out in early '97 ... the game wasn't really smooth on the P200 either." filipetolhuizen: "I could only squeeze max framerates on US Navy and derivates on a PII-PIV in 800x600 or 1024x768. Ditto for Interstate '76. They could've at least taken advantage of the MMX technology at the time, but didn't." | Recollections, 17 years after. **The "P166 ... 22-24fps" line in this thread is F2bnp answering AlphaWing about Jedi Knight, not I'76.** |
| 28 | VOGONS t=68384, UCyborg AiO patch | 2019-08-01 and later | UCyborg | "Added frame rate limiter which defaults to limiting the game to run at 20 FPS to workaround bugs that occur at higher frame-rates."; "Fixed an issue with laggy physics simulation that occurs when the system has been running for several days."; "Skipped some unnecessary CPU checking code containing privileged instructions"; "Obviously, when the game was made, nobody was talking about frame rates as game physics isn't intentionally tied to frame-rate. Devs just write code, overlook some details when implementing it and leave it at that if it appears to work correctly."; "my issue with the supposedly magic 24 FPS is that 7.62 MM MG firing sound is being interrupted at regular intervals while it sounds fine at 20 FPS, hence why I set the limit to 20 FPS." | Origin of the 20 fps cap (GOG's I76PATCH lineage). No timer API named. |
| 29 | github.com/immi101/i76fix README | 2017 | immi101 | "limits framerate to 25fps which prevents wonky physics that occur on higher framerates"; "disable ancient cpu measurement code which doesn't run as normal user on NT based system". WineHQ bug 21924: "privileged instructions used in attempt to measure the CPU speed". | 25 fps cap; the exe measures CPU speed at start-up with privileged instructions (rdtsc/rdmsr-class). |
| 30 | inbetweennames.net blog, 2021-05-04 | 2021-05-04 | Shane Peelar | Game "is really dependent on it's framerate for the physics simulations to work properly"; 30 fps trampoline: "some parts of the game still weren't working quite right"; "We tried 24 FPS which was an improvement"; UCyborg found "20 was about as high as you could go before negative effects started to set in." | How 30 -> 24 -> 20 was arrived at, empirically. |
| 31 | Microsoft Learn, GetTickCount (updated 2025-07-01); MSDN captures 2004-12 and 2008-11 (Wayback) | 2004-2025 | Microsoft | Learn: "The resolution of the GetTickCount function is limited to the resolution of the system timer, which is typically in the range of 10 milliseconds to 16 milliseconds." 2004 MSDN: only the 49.7-day wrap remark; 2008 MSDN: "The resolution is limited to the resolution of the system timer." | **No per-OS table on any Microsoft page reached.** |
| 32 | Forum quotes of an older MSDN table (codeproject.com post 1404180; delphipraxis.net 576420); comp.lang.ada / SDL list threads | 1998-2000s | second-hand | "Windows Me/98/95: The system timer runs at approximately 55ms"; a 1998 Microsoft developer's list post: timeGetTime "is accurate to 1ms, whereas GetTickCount can be as many as 55ms off". | 55 ms on Win9x is well attested second-hand, not from a primary page. |
| 33 | Wikipedia / PCGamingWiki / Manual.pdf (already checked by the lead) | - | - | Minimum P90, 16 MB; recommended P133, 32 MB, "Voodoo 3DFX or equivalent" (PCGW); PCGW: "The initial retail release only supports software rendering"; D3D 5 in the Gold version (1998-02-20). | Consistent with 11, 14, 16. |

Not found, after looking: a 3Dfx or Activision press release naming I'76 (3dfx.com 1996-98 CDX returned nothing); any Voodoo/Voodoo Rush bundle of I'76; the Next Generation p.147 preview body; the PC Gamer US June 1997 review text (93%); the PC Format #70 review; any Usenet thread with fps figures (Google Groups not indexed by the search tools used); Scott Krager's own 1997 posts (the Activision board's "Official Dates" replies by "Dave Georgeson", 2-3 July 1997, were never captured: CDX lists only read=1187-1241 and 1708-1731); any statement by a developer about GetTickCount, timeGetTime, a frame cap or a physics rate; any period benchmark (fps on named hardware) of this game.

### Confidence

- **High:** release spec (P90 min, P133/32 MB recommended), Win95-only, software-only renderer at launch at 320x240 /
  480x360 / 640x480, 3D support arriving with the summer-1997 1.08 patch line and Gold/Nitro, "designed for use on a
  Intel Pentium", the P90 "acceptable frame rate" goal, the community origin of every fps cap.
- **Medium:** the June/July 1997 board reports (first-hand, dated, but subjective: "smooth as silk" in 1997 could be
  anything from 15 to 25 fps). The Krager power-of-two-textures explanation (relayed by a user).
- **Low:** anything numeric about 1997 fps. None exists in a source found. The lab's existing "P166 + Voodoo 1 playable
  with slowdowns (15-25 fps)" line should be read as an estimate, not a citation.
- **Unconfirmed:** the 55 ms GetTickCount step on Windows 95 (second-hand only).

### Recommendation for the reference profile

1. **Keep stock20 as the parity reference.** Nothing from 1997 pins a frame rate, so a measured, reproducible profile
   beats a reconstructed one; and stock20 is what James played.
2. **Period bracket to emulate, if one is wanted:** Intel **Pentium 133-166**, 32 MB, **software renderer** (the game as
   reviewed and sold March-June 1997), Windows 95. A 3Dfx Voodoo Graphics (Monster 3D) profile is a *second* bracket
   representing the game from July 1997 (1.08 beta) and Gold onward, not the launch game.
3. **Expected fps for that bracket: not found.** Treat it as a range to sweep, roughly the teens on P133 up to the low
   twenties on P166 in software mode, with the explicit note that these are inferences from "jerky" vs "smooth" reports,
   not measurements. Do not quote 22-24 fps for I'76; that number belongs to Jedi Knight.
4. **Clock tick:** run `I76_TICK_MS=55` only as a sensitivity test, not as "the 1997 clock". The lab already measured
   that 55 ms steps break the AI above about 18 fps, while CGW's June 1997 reviewer called the AI "unusually smart and
   agile" on an unaccelerated 1997 PC. One of three things is true: the Win95 GetTickCount step was finer than 55 ms,
   the machines ran below ~18 fps, or the engine read a different clock in 1997 (the exe does also measure CPU speed at
   start-up, items 28-29). The first and third can be settled by the data track (the clock call sites are known) or by
   a Win95 run in 86Box with a GetTickCount probe; that test is the one piece of work that would close this question.
5. **Follow-ups that could still yield first-hand hardware statements:** listen to Dev Game Club ep. 427 (Vesce and
   Norman, 2025; topics include memory and polygon budgets); the Next Generation Nov 1996 preview on paper (p.147);
   the PC Gamer US June 1997 review; Google Groups for comp.sys.ibm.pc.games.action, March-July 1997.

Working files for this research (BBS captures, OCR text, decoded help topics) are in `C:\Users\james\AppData\Local\Temp\i76research` on this PC (a temp folder; copy out anything worth keeping);
the CD image itself was read from archive.org item `interstate-76-activision-1997` and was not installed or run.

## Box requirements (Arsenal box, photo from the owner, 2026-10-15)

The *Interstate '76 Arsenal* box (the later bundle; it requires "the latest Windows 95 drivers that can fully support
Microsoft's DirectX 5", so it describes the Gold-era game) lists, under Minimum System Requirements
([photo](img/arsenal-box-sysreq.jpg)):

- 100% IBM PC-compatible Pentium 90 MHz computer (**Pentium 133 or higher for 3-D acceleration**)
- U.S. Windows 95; 16 MB RAM (32 MB or higher recommended); 135 MB for a full install, 80 MB minimum
- VESA local bus or PCI video card with 2 MB RAM; 16-bit High Color; double-speed CD-ROM; Sound Blaster-compatible
  sound card; Microsoft-compatible mouse; joystick or gamepad optional
- Optional Direct3D acceleration ("some of these cards may require a processor faster than a Pentium 90"); the 3D
  partner badges include 3Dfx, Rendition and Matrox.

Read against the 86Box measurements of the Gold exe (emu `results\RESULTS.md`, 2026-10-15; Windows 95 RTM
GetTickCount step measured at 1 ms, not 55 ms): the box's 3-D spec (P133 + Voodoo) ran about 26 fps in Instant Melee
(25.7 / 26.4), and P133 software about 10 fps (9.7 / 10.1). The box minimum (P90, software) was not measured; it is
slower than P133 software. These are emulator numbers for one melee arena; mission runs and the gameplay check are
pending.
