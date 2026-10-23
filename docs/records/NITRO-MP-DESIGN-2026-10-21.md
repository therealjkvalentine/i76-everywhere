# Our multiplayer on Nitro, behind one separate menu entry (design, 2026-10-21)

Lane `nitro-mp-design`. Owner ruling, 2026-10-21 (verbatim): *"from a multiplayer perspective we'd want nitro to be the
basis instead of gold so we'll have some rebuilding to do there. let's try to do it nondestructively, so that community
play of nitro multiplayer is unperturbed. perhaps it's a new menu item we'd add separately but not sure what we'd call it
ai drop in coop something"*. Plan: [ARSENAL-PLAN-2026-10-21.md](../ARSENAL-PLAN-2026-10-21.md) section 2.

**Everything here is static** (Ghidra decompilation and capstone on the pristine GOG files; no game was started). RE notes
with every address: `C:\Users\james\i76-map\nitro-net\README.md` (new track; headless exports of nitshell, WIPX2, WINETS2;
tools `callers.py`, `ndis.py`, `sitemap.py`). Hook-list skeleton: `music-fix/nitro_mp.c` (not built, not included).

Files: `nitro.exe` 28b8ae27, `nitshell.dll` f804f50d, `anet2.dll` a21c2baa, `dll\WIPX2.DLL` 70f35031, `dll\WINETS2.DLL`
b91eccee (all from `i76-map\sandbox-gog\nitro-full\app`).

## Answer in six lines

**Revised the same day (section 0):** items 2 and 5 are superseded. The entry is now the owner's **ARENA+** options as
check boxes on the host form (AI DROP-IN, DROP-IN / DROP-OUT, CO-OP SCENES on Nitro's own missions), with no Gold content.
The separate button of item 2 is kept as the fallback.

1. **Receive path:** Nitro's pump `0x448d80` calls `dpReceive` through the import slot **ANET2.DLL!dpReceive 0x4c13cc** with
   the same six arguments as Gold, and **drops any packet type it does not know** after updating "last heard". Our Gold
   method (hook the import, read our 2-letter packets after the real call) carries over unchanged. No packet types are
   registered anywhere; ANet 2 only adds the system packet 'd9' (session lost).
2. **Menu insertion:** Nitro's main menu is one button table (ids 0..0x12, layout `0x10009610`) with one click dispatch,
   `cmp esi, 0x12; ja default` at `0x1000887b`. A new button **id 0x13** in the melee group, routed by changing only that
   `ja` target to a stub, adds the entry without moving any stock button.
3. **Isolation:** the shell hosts and lists sessions of ANet **sessionType 604** (`[0x10046cb0]`, = anet.inf). In our
   entry the proxy swaps that one word for our own value, so **our sessions never appear in a stock JOIN list and stock
   sessions never appear in ours**. Belt and braces: our host reports version "6.04+" so a stray stock joiner gets the
   stock "version does not match" box.
4. **Stock sessions stay stock:** with the entry unused, the proxy keeps every multiplayer switch off; a stock joiner of
   a patched host passes the host's vehicle check (`0x446120`, re-runs the car CRC from the host's own files) and its own
   version / mission-CRC check, as long as the host's car and mission files are stock (they are: we change none).
5. **Lists:** Nitro builds its arena list from files only (`*.cbt` in the game's files, then `addon\*.cbt`), no fixed
   table. The 15 original arenas are already there (N51-N65, terrain byte-identical); our AI fill works on every combat
   arena by memory injection (no new files). The 17 co-op scenes and 7 scenarios need the Gold mission files, placed in a
   folder only our entry's list reads.
6. **Estimate:** about **15 lane-days** in 8 pieces, the shell entry and the ANet 2 layer first.

## 0. REVISION (2026-10-21, owner rulings): ARENA+ as options on the host form, not a new menu button

Owner (verbatim): *"it seems like the right place for the ai drop-in option is a checkbox inside the network play
configuration, maybe a few of them for other features we've added (human drop-in, etc). tricky though since we haven't
done any modifications to menus successfully yet."*, *"we don't have to bend over backwards to combine them"* [original
and Nitro content], *"looks like we get unhandled exceptions when we try to modify menus for now"*, and on the name:
*"we should call it arena+ with that description that is good"*.

**This section replaces section 2 (entry point), section 3.4 (lists) and the name table of section 4.** The separate
button of section 2 stays as the **fallback** if the host-form route fails its proof of concept. Sections 1, 3.1-3.3 and
5 stand, with the changes in 0.6.

### 0.1 What ARENA+ is

- **Group label** on the host form: **ARENA+**. Description (owner-approved, unchanged): *"Every arena plus the original
  '76 missions, with AI filling the open slots."* What it can deliver on Nitro: every Nitro combat arena, of which
  N51-N65 are the original '76 arenas (same terrain). **The original '76 story missions (T01-T17) and scenarios (S01-S07)
  are not loadable under Nitro without combining Gold's files, which the owner dropped.** The text stays as approved;
  this record states the gap here.
- **Options under it** (each a per-session choice of the host; all off = a stock session):

  | option (label) | what it turns on | Gold source |
  |---|---|---|
  | **AI DROP-IN** | AI cars fill every empty slot (fill N = NO. DRIVERS - humans), AI respawn, AI score rows | aimelee + mpfill pool (AI-MELEE-RESPAWN) |
  | **DROP-IN / DROP-OUT** | humans join and leave any time; a leaving human's slot goes to an AI on his team, and back when someone joins | mpfill teams (MP-TEAMS); needs AI DROP-IN |
  | **CO-OP SCENES** | Nitro's own campaign missions P01-P19 as co-op scenes with per-joiner scaling and the scene chain | co-op chain + COOP_SCALE; **Nitro content only** (built from nitro.zfs, not Gold's T-missions) |

  Difficulty-driven AI skill stays the options-screen setting (not on the form).
- **Session type:** any option on -> our species (sessionType, section 1.1); all off -> 604. A patched JOIN list asks
  for both species and shows ours with the prefix "ARENA+ " in the game-name column. A stock JOIN list never sees ours.

### 0.2 The host form, mapped (nitshell f804f50d)

The network entry form (message 0xc026) is **not** built from button widgets like the main menu. The labels and boxes
are in the background picture. The form is a static table of **hit rectangles**, plus code that draws the variable texts.

| piece | address | detail |
|---|---|---|
| constructor | `0x100318e0` | background picture by provider (`0x10012780`), fill and text calls for the game name, arena title, car lines, max drivers ("%2.2d"), game-type text (`[0x10045894 + type*4]`: Combat, Racing, C.T.F. (2/3/4)); sets the frame handler `[0x10047044] = 0x10033770` (redraw) and the click handler `0x10001f40(0x10031ff0)` |
| hit table | **`0x10045a80`, 16 records of 0x14 bytes `{id, x0, x1, y0, y1}`** (ids 0..15), copied into the list `[0x10179ea8]` by `0x10031e50` (records from 0x10045ae4 on are left out for some join providers). The list is a growable pointer list (`0x1000e000(0x10)`, append `0x1000e100`), built once per process (`if [0x10179ea8] == 0`) | hit test `0x1000e2e0(list, x, y)`: strict `x0 < x < x1`, `y0 < y < y1`, returns the record's id or -1 |
| click handler | `0x10031ff0` | mouse object `[0x10130484]`: +0x2c x, +0x30 y, +0x10 click state (getter `0x1000ccb0`); `call 0x1000e2e0` at `0x10032140`; **`cmp ebx, 0xf; ja 0x10032054; jmp [0x1003365c + ebx*4]` at `0x10032198`** |
| redraw | `0x10033770` (the constructor's text part again) | |
| the form data ("save") | **`0x10179fa8`, 0xe4 bytes**: what BROADCAST passes to `0x1002e4c0(provider, form, 0, arena record)` and what the host publishes as player data key 5. [0x32] = `0x1017a070` max drivers, [0x35] = `0x1017a07c` game-type bit, [0x36] / [0x37] = `0x1017a080` / `0x1017a084` limit kind / value, **[0x38] = `0x1017a088` team game** | `0x1002f3c0` turns them into the session flags (section 1.6) |
| BROADCAST / JOIN | id 14 (x 229-369, y 453-471), handler `0x100332e4`: a C.T.F. type or `[0x1017a088]` opens the team popup `0x10022e00`, then `0x1002e4c0(provider, 0x10179fa8, 0, arena)` | |

Ids by rectangle and handler [labels inferred; the art was not seen]: 0 game-name box (170-214, 44-58); **1 game-type
popup arrow (200-215, 68-85)**, popup descriptor `0x100459d8` (draw `0x10034250`, click `0x100341e0`, list
`[0x1017a090]`); 2 arena list (9-215, 166-251), 3 / 4 its scroll arrows; 5, 6, 11, 12 further popups (`[0x1017a0a0]`,
`[0x1017a0a4]` (depends on the game type), `[0x1017a094]`, `[0x1017a098]`); 7; 8; 9 / 10 max drivers up / down
(199-212 / 152-165, y 423-436); 13; 14 BROADCAST / JOIN; 15 cancel (489-630, 453-471).

**Nitro's form has no TEAM PLAY check box, and the shell has no check-box code at all**: every option is a popup list.
"Team game" is form [0x38] (`0x1017a088`): the game-type change code sets it to 1 for C.T.F. (`0x100342e2`) and clears
it on a type change (`0x100342ab`). Whether Combat offers a team choice inside the type popup is to be seen on screen.
So "next to TEAM PLAY" becomes "in the left column of the form".

### 0.3 How three check boxes are added without moving a stock control

1. **Hit records.** Three records `{0x10, ...}`, `{0x11, ...}`, `{0x12, ...}` in proxy memory, appended to the list
   `[0x10179ea8]` with the shell's own `0x1000e100(list, rec, 0)` right after `0x10031e50` returns (its call in the
   constructor `0x100318e0` is wrapped), host providers only (`[0x1004701c]` 2..5). The 16 stock records and their
   order are untouched. The hit test walks the list in order, so ours can only win where no stock rectangle is.
2. **Click.** Only the target of the `ja 0x10032054` at `0x1003219b` (6 bytes `0f 87 rel32`) changes, to a stub: ids
   0x10..0x12 toggle the `g_arena_opt` bits, recompute the species word, redraw our boxes, then `jmp 0x10032054` (the
   stock "nothing hit" exit). Any other id above 15 goes to `0x10032054` as before. The jump table and ids 0..15 run
   unchanged.
3. **Draw.** After the constructor and after every `0x10033770` redraw: the frame-handler pointer `[0x10047044]` that
   the constructor sets is replaced by a wrapper that calls `0x10033770` and then ours. Each box is filled with the
   form's own `0x10012a50(display, x, y, w, h)`, and the label / an "X" is written with `0x10012dc0(display, x, y,
   [[0x1013049c] + 0x408], text, 0)`: the two calls the form uses for every text it draws. No new picture.
4. **Save.** Nothing is added to the 0xe4 form block (stock joiners read it as key 5). The options live in the proxy
   (`g_arena_opt`). BROADCAST is wrapped at `0x1002e4c0` to (a) set the species word `[0x10046cb0]` (ours if any bit is
   on, 604 if none) just before `dpOpen` and (b) start the ARENA+ session state. A joiner learns the options from the
   host's 'AH' hello (section 3.2), not from the form. Back to the main menu, cancel (id 15) or session end -> options
   cleared, 604 restored.
5. **Where.** Free space by the table: the left column between the arena list's lower arrow (y 252-272) and id 5 (y
   310-326), about 37 px, for the ARENA+ label and one row of three 12-px boxes with short labels ("AI", "DROP",
   "CO-OP"). Full labels go on a second line only if the PoC shows the art leaves room. The exact pixels come from the
   PoC's frame-buffer read (the art may have decoration there).
6. **Join list.** `0x1002dfb0` (dpEnumSessions with species 604) is wrapped to enumerate a second time with our species
   into the same callback `0x1002e060`; a callback wrapper prefixes "ARENA+ " to our sessions' names.

### 0.4 Why the edited SCENARIO.DAT crashes (static, quick look), and what it says about these tables

`addon\scenario.dat` is parsed by `0x1001c3b0` into **fixed arrays of 4 characters x 20 missions**. Mission records of
0x60 bytes sit at `0x10134720 + (character * 20 + k) * 0x60` (4 x 20 x 0x60 = 0x1e00 bytes, ending exactly at
`0x10136520`); the character records (name + count, 0x24 bytes) at `0x1013653c`. **The parser bounds neither count.** A
fifth character ("Groove" in `nitro-plus-original`) writes its 17 mission records from `0x10136520` on: over the shell's
own globals there (`0x10136520`, `0x10136524`, `0x10136534` with 49 references, ...) and over the character table
itself. That is a sufficient cause for the "Unhandled Exception" [inferred from the decompilation; not run]. A
SCENARIO.DAT with at most 4 characters and at most 20 missions each stays inside the arrays (e.g. put "Original
Mission 1-17" under one of the four existing characters, at most 20 lines).

What it says: the shell's tables are fixed-size and unchecked (the scenario arrays, the 16-record hit table, the popup
lists), so **data-only edits that grow a table are the fragile route**. The design never grows a shell table in place:
it appends to a growable list through the shell's own append call and keeps its records and state in proxy memory.

### 0.5 Proof of concept, step 1 (defined; to run on the lab copy exp-nitro-mp)

**Goal:** one check box (AI DROP-IN, id 0x10) drawn, toggled and read back by the proxy, **n 3** boots, plus 1 control.

Copy: `C:\Users\james\i76-uncap-lab\exp-nitro-mp` = a copy of `i76-map\sandbox-gog\nitro-full\app` + dgVoodoo (as
`exp-nitro-base`, which reached the shell headless) + a lab proxy build with only the PoC code behind the lab switch
below. No IPX and no second copy: the form opens from HOST > IPX without a network session.

Rules: headless only, on a private desktop (the console is held by a gate); never stop a process this lane did not
start (check pid and exe path); no boot while `.fps-lock` exists; wait while any i76.exe / nitro.exe outside the lab
copies runs; mute the process (`tools\mute-proc.ps1`), clear the mutes at the end.

Proxy (lab build, `I76_LAB_ARENA_POC=1`):
1. When nitshell is resident: check the bytes at `0x1003219b` (`0f 87 b3 fe ff ff`), the `call 0x10031e50` in
   `0x100318e0`, the `[0x10047044] = 0x10033770` store, and `[0x10046cb0] == 0x025c`. Log each; refuse on any difference.
2. Navigate by state, not by clicks: the lab block does what the provider button does (provider `[0x1004701c]` := 3,
   `0x10031320`, message 0xc026 posted to the shell window), so the form opens without a mouse.
3. **Drawn:** after the form's first redraw, read the shell's 640x480 8-bit frame buffer (`[[0x10130488] + 0x44]`, the
   buffer the shell clears with 0x12c00 dwords) over the box rectangle. Pass: the pixels differ from a read of the same
   rectangle taken just before our draw call and equal the fill colour inside the box.
4. **Toggled:** write the mouse object (`[0x10130484]` +0x2c = box centre x, +0x30 = y, +0x10 = the click state the
   handler waits for) for one frame, as a click would. Pass: the stock hit test returns 0x10 (logged by the stub) and
   the stub flips the bit.
5. **Read back:** the proxy logs `g_arena_opt`, the species word `[0x10046cb0]` (ours after the toggle, 0x025c after a
   second toggle), the box pixels again ("X" drawn / cleared), and the list `[0x10179ea8]` count (16 stock + 1) with the
   16 stock records unchanged (compared with the static table).
6. Pass = steps 3-5 in 3 of 3 boots with no exception, and a control boot without the switch shows count 16, species
   0x025c and no change in the box rectangle.

Step 2 (after the pass): the other two boxes, the join-list double enumeration, and one IPX check with a stock joiner
(the ARENA+ session must not be listed, a stock session must be).

### 0.5.1 Proof of concept, step 1: RESULT (2026-10-21, lab copy exp-nitro-mp, headless, n 3 + 1 control)

**Pass, 3 of 3, and the control is clean.** The first menu change on Nitro that held: one ARENA+ / AI DROP-IN box on the
INTERNET host form, drawn, toggled by a scripted click through the shell's own input polling, and read back.

Setup: `i76-uncap-lab\exp-nitro-mp` = `sandbox-gog\nitro-full\app` unmodified + dgVoodoo files (as exp-nitro-base) + the
stock strlkup.dll as `strlkorg.dll` + the lab instrument **nmpdrv** as `Strlkup.dll` (md5 aebf8d72; `tools\nitro-mp\nmpdrv`
= the nitro-base lane's nbdrv, unchanged, + `arena_poc.c`; no proxy file of the repo, `sites_nitro.h` not used). Harness
`tools\nitro-mp\nmprun.py` (nbrun on the new copy): private desktop, process mute watcher (persisted mute cleared after
each run, log `<tag>.mute.txt`), `.fps-lock` and foreign-game checks before each boot, only its own process stopped. Env
`NB_ACTIVE=1 NB_SKIP_MOVIES=1`, `-glide`, `NMP_POC=1` (PoC) or `2` (control: same navigation and readings, nothing added
or patched). Evidence `i76-uncap-lab\captures\nitro-mp-20261021\{poc-r1,poc-r2,poc-r3,control-c1}.log`.

What the instrument did (all signature-checked first: the `ja` bytes, six function entries, species word 0x025c; all OK
in every boot; nitshell was mapped at 0x02FA0000, not its preferred base, so every address went through the relocation):
1. When nitshell loads: nitshell's `GetCursorPos` / `GetAsyncKeyState` imports answer a scripted UI point / left button;
   (PoC only) the `ja 0x10032054` at `0x1003219b` -> a stub (ids 0x10 toggle, everything else to the stock exit).
2. Shell up 3 s -> the shell window subclassed (for main-thread work), the shell's own active flag `[0x1004067c]` held at 1
   (a private-desktop window is never activated, and the shell only polls the mouse while active).
3. **Navigation by clicks through the stock menu**: main menu id 1 (469,311) -> id 9 (417,351) -> HOST id 10 (389,379)
   -> INTERNET id 15 (430,406). The shell's mouse object read every point exactly (client 640 x 480). This confirms the
   button reading of section 2 for ids 1, 9, 10, 15.
4. On message 0xc026: the hit list is prebuilt (`0x10031e50`) so the first-entry lobby-server popup does not open (the
   only deviation from the stock flow, needed because no lobby is reachable headless), then the stock constructor runs.
5. (PoC) append the record `{0x10, 10, 34, 284, 300}` with the shell's `0x1000e100`, install the redraw wrapper, draw
   "ARENA+" and "[ ] AI DROP-IN" (erase `0x10012a50` + text `0x10012dc0`, the form's own calls) at x 12, y 273 / 286.
6. Two scripted clicks on the box (18,292), a read-back after each (in the shell's thread).

| reading | poc-r1 | poc-r2 | poc-r3 | control-c1 |
|---|---|---|---|---|
| form up, provider | 4 | 4 | 4 | 4 |
| hit list count before / after | 16 / 17 | 16 / 17 | 16 / 17 | 16 / 16 |
| 16 stock records (pointers, order, bytes) | unchanged (every read) | unchanged | unchanged | unchanged |
| label / box text width (px) | 60 / 130 | 60 / 130 | 60 / 130 | - |
| box pixels (checksum of the 12 x 12 box in the locked DirectDraw back surface) before draw -> after | 65719c24 -> a8e843b8 | same | same | 65719c24 throughout |
| click 1: stock hit test returned id 0x10, stub toggled | yes: ON, species 0x7676, box -> afa33159 ("[X]") | yes, same | yes, same | no hit, nothing changed |
| click 2 | OFF, species back to 0x025c, box back to a8e843b8 | same | same | same as click 1 |
| redraw pointer | ours (wrapper) | ours | ours | stock 0x10033770 |
| exceptions other than the game's own handled ones | 0 | 0 | 0 | 0 |

(Every boot logs the game's own first-chance exceptions, all handled by the game and present in the control too:
c0000096 privileged instruction at `nitro.exe+0x9acb7..` - the PIT measurement i76fix patches - and C++ e06d7363 from
another module once a second. None came from the PoC code.)

What it shows: appending to the hit list through the shell's own call and rerouting the one `ja` is enough for a new
control to be hit-tested and dispatched by the stock click handler, without touching the 16 stock records; the species
word follows the box. What it does not show yet: the box on a real screen (headless; the pixels were read from the back
surface the shell presents, not seen), the redraw wrapper being called (no popup was opened over the form), the label
position against the art (needs one look at the console), BROADCAST with the box on, the join list (step 2).

Found on the way: nitshell keeps a **second species**, `[0x10046cb4]` = 0x296c (10604), which `0x1002f260` puts in place of
604 when the setup block has bit 2. Our lab species 0x7676 avoids both; the ARENA+ species must too.

### 0.5.2 Step 2: RESULT - ARENA+ sessions over IPX, both directions (2026-10-21, two lab copies, headless, n 2 per cell)

**Final ARENA+ species: 0x7676 (30326).** Not 604 (`[0x10046cb0]`, anet.inf `SessionType`) and not 10604 (`[0x10046cb4]`,
the shell's second species). It is what our host writes into the session record's sessionType (+0xd) at `dpOpen` while
any ARENA+ box is on.

**Setup.** Copies `exp-nitro-mp` (host) and `exp-nitro-mp-b` (JOIN list), identical, instrument nmpdrv (md5 fb7bf974 for
every cell except c2-r1, 57782eb0, which differs only in the patched joiner's enumeration hook, not used in c2).
**IPXWrapper 0.7.2 instances L and M** (`tools\nitro-mp\ipx-instances.ps1`; mutex `ipxwrapperLsocket` / `...M...`, keys
`HKCU\Software\IPXWrappeL` / `M`; previously used instances: B, E, F, G, H, K): UDP **port 54830** (E-H use 54800, K 54810),
only the Hyper-V Default Switch adapter enabled (00:15:5D:71:9A:4E, 172.30.160.1/20), fixed nodes 02:4C:00:00:76:01 /
02:4D:00:00:76:02. Checked in the IPXWrapper debug logs over all cells: every send went to 172.30.175.255:54830, every
packet came from 172.30.160.1. (An `ipxwrapper.ini` in the game folder makes IPXWrapper ignore the registry: the first
try used port 54792 that way; the ini was removed.) Driver `tools\nitro-mp\pair.py`: host boot, BROADCAST through the
stock form by scripted clicks (HOST > IPX; box clicked first when ON), holds 75 s in its arena; 20 s later the JOIN boot
(JOIN > IPX) reads the shell's own session list every 2 s for 30 s (count `[0x1015b038]`, rows of 0xe4 bytes at
`0x101593b8`: name, session record, players). `NMP_MULTI=1` answers nitro.exe's single-instance `FindWindowA` with NULL
(the two copies also run on different private desktops).

| cell | host | JOIN list (box code) | result, every read (15 per boot) | n |
|---|---|---|---|---|
| c1 | ARENA+ box ON: `dpOpen` species **7676**, "Evening Stroll" | patched (enumerates 604 + 7676, names ours "ARENA+ ") | **1 session: "ARENA+ Evening Stroll", species 7676, 1/4** | 2 |
| c2 | box ON, species 7676 | **stock** (no box code, no hooks) | **0 sessions** | 2 |
| c3 | box OFF: species **604** (stock session from the patched copy) | **stock** | **1 session: "Evening Stroll", species 025c, 1/4** | 2 |
| c4 | box OFF, 604 | patched | 1 session "Evening Stroll", species 025c (no prefix) | 1 |

Hosts stayed in their arena (state 5, net 1, own id = host id) for the whole hold, joiners stayed in the JOIN form; no
crash or exception from our code in the counted runs. Two failed runs before the count, both from the instrument: the
first patched JOIN list ended in **0xC0000409** both times because the enumeration callback wrapper was declared cdecl -
the shell's callback `0x1002e060` is **stdcall (`ret 0x10`)**, ANet calls it that way; fixed, then c1 passed.

What it shows: the session-type swap keeps ARENA+ and stock sessions apart in both directions on a real ANet 2 / WIPX2
session, and a patched copy hosting a stock session is listed by a stock copy as before. Not covered: an actual JOIN
(only the lists), the lobby route (below), the screen.

### 0.5.3 anet2.dll read from a running copy (estimate item 1, done)

The loader stub maps the real code **in place**: a boot of `exp-nitro-mp` with `NMP_DUMP` wrote anet2's image (loaded at
0x020F0000; `dpReceive` 0x020FA420, `dpSend` 0x020FB1A0, `dpEnumSessions` 0x020F8A20, `dpOpen` 0x020F6BA0, all inside the
image), turned into a loadable PE by `i76-map\nitro-net\tools\unmap_pe.py` and exported by Ghidra (343 functions,
`i76-map\nitro-net\ghidra\export-anet2-unpacked`; addresses are for base 0x020F0000). Findings:

- **Packet size limit: payload <= 249 bytes unreliable (flag 0), <= 244 reliable (flag 1)**: dpSend appends a 6-byte
  trailer and the transport sends refuse `len + 6 > 255` (unreliable, `0x020ff500`) / `> 250` (reliable, `0x020ff600`) with
  error 4. So 'AT' stays at 2 records (208 B); 3 (308 B) would be refused - the Gold measurement (5 records never
  arrived) has its cause.
- **dpSend writes 6 bytes past the payload** (`from, to, session word` in place; ANet 1 wrote 4): every send buffer needs
  >= 6 spare bytes (the proxy's COOP_DP_SLACK 16 covers it).
- **Reliable sends exist**: dpSend's flag 1 takes the reliable path. 'AK' / 'AM' / 'AH' can use it instead of 3 copies.
- **dpReceive**: a packet whose first byte is 'd' is ANet's own (handled inside, mostly not returned); anything else
  is returned to the game after the 6-byte trailer check (known sender, sender != target, session word). So any app
  tag not starting with 'd' reaches nitro.exe's pump - ours do ('A...').
- **Species filtering is the client's**: `dpEnumSessions` lists sessions from its tables whose species equals the
  requested one, **0 = any species** (synchronously, then asynchronously until the timeout via the stored callback,
  `0x020f36b0`); a new call first ends the previous enumeration with a NULL callback. Simpler than the two-pass hook of
  the PoC: one call with species 0, filtered to {604, 7676} in the callback.
- **Lobby (game server)**: `dpSetGameServer` logs in with the app's species from anet.inf (604) and subscribes to the
  server's session table under the key {table, species} (`0x020f6480`). A lobby therefore serves sessions **per species**:
  stock clients subscribed to 604 never receive 7676 sessions (the isolation holds on a lobby too); a patched joiner must
  add a second subscription for 7676 (same call, our species) to list ARENA+ sessions there, and whether a community
  server keeps a table for an unregistered species is the server's business (not in this client code). Risk R3 stands,
  now narrowed to that one question.

### 0.5.4 Step 3: the ANet 2 layer (`music-fix/nitro_mp.c`) - a real ARENA+ join, hello and 'AT' both ways (2026-10-21, n 3 + 2 stock)

**Pass: 3 of 3 ARENA+ joins and 2 of 2 stock joins.** `music-fix/nitro_mp.c` (commit 7fc8196) is the ANet 2 layer of the
design, on the nitro-port lane's `sites_nitro.h` (read-only; every looked-up Nitro address is checked against this
lane's own reading, plus byte signatures for the two functions it calls). It is not in `strlkproxy.c` yet (shared file;
the integration is one `#include` after `nitro.c`, `nmp_attach_exe()` in `nitro_dllmain`, `nmp_attach_shell()` where the
proxy sees nitshell load). For the proof it was compiled into the lab instrument nmpdrv (md5 9847690e, `NMP_NET=1`),
which keeps the ARENA+ box of steps 1-2 (arena_poc.c) and now hands the session hooks (list, dpOpen) to nitro_mp.c.

What nitro_mp.c does: hooks nitro.exe's `ANET2.DLL!dpReceive` import (real call first, then our tags, pump-driven);
sends through a 16-byte-slack buffer capped at 249 B unreliable / 244 B reliable; mode = the species of the session
nitshell opened (0x7676 ARENA+, 604 stock - in a stock session it reads nothing and sends nothing); 'AH' hello
(reliable) from the host to the group until every joiner answered, each joiner answers once per seq; 'AT' in Gold's
format, at most 2 records (here a lab self-test: after the hello each side sends one 'AT' with its OWN car, packed by
net_PackVehicleState 0x463660, and the receiver compares the record's position with its mirror of that car); nitshell's
list = one `dpEnumSessions` with species 0, filtered to 604 + 0x7676 (ARENA+ named "ARENA+ <name>"); the lobby
subscription is a stub.

Runs (`tools/nitro-mp/pair.py --join-role joinplay --net 1`, summary `tools/nitro-mp/joinsum.py`, lab repo): the host boots,
ticks the box (or not), BROADCAST; 20 s later the joiner boots, JOIN > IPX, waits for the session in the list, clicks row 0
and JOIN GAME, then both stay in the arena (host 110 s, joiner 60 s) writing a status line every 5 s (session species,
role, ids, our packet counters, and every player-table row with its car position). IPX as in step 2 (instances L / M,
port 54830, Hyper-V adapter; every packet in the logs went to / came from 172.30.160.1 or 172.30.175.255:54830).

| run | session | joiner listed / joined | hello | 'AT' host -> joiner / joiner -> host | both tables, last common status line | n |
|---|---|---|---|---|---|---|
| j1-r1, r2, r3 | 7676 ("ARENA+ Evening Stroll") | yes / yes (state 5, ids 40 host, 44 joiner) | host sent 3 (reliable), joiner answered 1, host counted 1 answer | 1 / 1, each receiver: "record position AGREES" with its mirror (floats 7..9 = x, y, z) | **agree**: same 2 ids, each car within 1 m on both (e.g. 40 at 2937.5,48842.5 and 44 at 3392.5,48877.5) | 3 |
| s1-r1, r2 | 604 ("Evening Stroll", box off) | yes / yes | **none sent, none received** (stock session: pass-through) | 0 / 0 | **agree** | 2 |

No access violation or other exception from our code in any of the 10 boots (only the game's own handled ones, as
before); every persisted mute cleared. The stock-join cells ran with nitro_mp.c present but passive; a join with the
code absent was not run again here (step 2 c3 listed a stock session from a stock copy).

Notes from the runs: the joiner opens the session with the record nitshell keeps, whose name carries our "ARENA+ "
prefix (`dpOpen ... 'ARENA+ Evening Stroll'`); ANet 2 joins it all the same (the join does not match by name). The
record position of an 'AT' sits at floats 7..9 (x, y, z) of net_PackVehicleState's 0x60 bytes.

### 0.5.5 Item 4: AI melee in an ARENA+ session on Nitro (`music-fix/nitro_ai.c`) - measured (2026-10-21, two lab copies, headless)

**Result: every asked cell passes.** `music-fix/nitro_ai.c` (commits 3296cba, 71b18da) ports the
AI lane's aimelee.c sections 1, 2, 4, 6, 7, 8, mpfill.c's fill and the co-op AI sync of strlkproxy.c to nitro.exe,
through the nitro-port lane's `sites_nitro.h` (read-only; 28 addresses looked up and each checked against this lane's
reading; their files not edited). It sits on nitro_mp.c (two hook pointers added there) and is compiled into the lab
instrument (nmpdrv md5 54a53371 for the kill runs c1-c8; a54e1108 / 275976b7 for x1, a1-a4, b1-b4, s1-s2, which differ only in the LAB shooter; `NMP_NET=1 NMP_AI=1`); not in strlkproxy.c yet. Full design notes in the file header.

What runs, only in an ARENA+ session (species 0x7676) of a combat arena (*.cbt), on every machine:
- **Pool**: 7 car records through the OBJ handler 0x4b3660 right after the ODEF walk (call 0x4bd4bf), class-1, team 7
  (Men In Black - the 8th name in Nitro's team list too), parked at -9000,-9000; the same labels on host and joiner
  (N01: labels 2-8 on both).
- **Fill**: AI in play = NO. DRIVERS (host form 0x1017a070) - humans, humans counted after 1.5 s unchanged; a joining
  human parks one (wreck first), a leaving one brings one back at the free spawn point (team-0 spawn table 0x5414f8).
- **Sync**: 'AT' in Gold's format, **2 cars per packet (208 B, under the 249 B limit)**, 10 per second, parked cars every
  2 s; joiner mirror 0x463a20, ai_FrameTick skipped on joiners (0x432e24), the 5 object_ClassDamage calls guarded, AI
  trigger pulls replayed.
- **Host tick** at 0x4079a2: attack the nearest live human (sticky), skill once per car from Nitro's DEF difficulty
  byte 0x5fb0fc with difficulty.c's mapping (the copies are on Wimp: skill 4, logged), attacker cap 8 on the host car.
- **Kills** at 0x46332e: 'AK' **reliable** (one copy), "<AI> was destroyed by <player>" on every screen, the killer's
  machine credits its own row (stock formula).
- **Respawn**: dead AI back after 5 s by the spawner 0x44c930 at the free spawn point (joiners rebuild their copy from
  the host's 'AT'); dead humans ask for the stock respawn 0x44caf0(1).
- **Rows**: each AI in play holds a row of the 16 x 0x50 table (id 0x7E00 + n, name, flags team 7 << 16 | 2, +0x30
  latency -1, +0x44 1.0, +0x48 team 7), owner id entity +0x484 = row id; the host keeps the AI rows' kills / deaths.

Runs: `tools\nitro-mp\aimatrix*.sh` on `pair.py` (host boots, picks the arena and NO. DRIVERS on the stock form, box on,
BROADCAST; 20 s later the joiner boots, JOIN > IPX, joins). LAB switches for kills (never in a pack): `NMP_LAB_AI_HP=1`
(AI armour 0, chassis 1 %), `NMP_LAB_SHOOT=<s>` (every s seconds the local car keeps 10 m behind the nearest AI for 3 s with
Nitro's weapon_fire byte 0x53490b held - nitro.exe does not read held keys through GetAsyncKeyState, so the Gold LAB's
key hook does nothing here), `NMP_LAB_OWN_HP=5` (local car cut, so the AI kill it). Status line every 5 s on the same
wall-clock grid on both copies; summaries `tools\nitro-mp\aisum.py`. Evidence `captures\nitro-mp-20261021\ai-*.log`.

| cell (asked) | result | n |
|---|---|---|
| AI count, 4 drivers | host alone: 3 in play; joiner in: 2 in play on **both** screens (every stamp after the 1.5 s settle) | 15 runs (N01 8, N51 7) |
| AI count, 2 drivers | host alone: 1; joiner in: 0 on both screens | 2 (a3 N01, a4 N51) |
| a joiner takes an AI's slot | "parked AI #k ... 2 humans, 2 of 7 AI wanted" on the host, the AI gone from both screens and its row given back on both | every join, 17 runs |
| AI deaths respawned on both screens | host respawned **30** dead AI cars; the joiner rebuilt its copy from the host's 'AT' **27** times (the other 3 came back after the joiner's boot had ended) | 10 asked |
| kill credit: host kills an AI | credited on the host, the same message and row on the joiner | **15** (c1 3, c3 3, c4 2, c6 2, c7 3, c8 2) |
| kill credit: joiner kills an AI | the host's kill hook names the joiner (`+N to player 44`), 'AK' reaches the joiner, credited there, rows agree | **4** (c3 1, c6 1, c7 2) |
| kill credit: AI kills a human | the AI row gets +1 kill and the stock score on the host, the joiner's mirror shows it | **17** (the host's car 7, the joiner's car 10) |
| AI kills an AI (same team) | "X was destroyed by Y - own team: no score" (stock team-kill rule) | 2 (seen in b1, c1) |
| rows agree at the phase end (last common 5 s stamp) | **agree** on every id, kills / deaths / score, in every run | 17 |
| sync quality (MP-OVERNIGHT's measure) | over 1,135 AI-in-play samples (host vs joiner, same 5 s stamps, the stamp after a park / bring-in left out): **median 0.00 m, p90 1.46 m, p99 3.19 m, max 20.0 m (1 sample)** | 15 runs (4-driver runs) |
| crashes | 0 (no access violation or other exception from our code) | 40 boots |
| stock session (box off), same arenas | "'N01.CBT' outside an ARENA+ session - stock arena, no AI pool" on both copies, join OK, both tables agree, nothing of ours sent | 2 (s1 N01, s2 N51) |

Notes:
- 'AK' sent / received differ by one in five runs: every one of those was a kill after the joiner's boot had ended
  (joiner hold 240 s, host 300 s) - not a loss.
- Joiners show the AI cars at 100 % health (the mirror carries only "destroyed"), as on Gold (cosmetic).
- The AI play on Wimp's skill 4 here (the lab copies' DEF byte is 0); `I76_AIMELEE_SKILL` overrides.
- The ANet player names read "Unknown" in the lab (fresh DEF); names come from the player's DEF.
- Not ported (s.3.1 list stands): co-op scenes and scaling, waves, the fill's teams ledger, host-migration reconcile,
  the scoreboard box size (8 rows: enough for the default fill of <= 8 cars), 'AV'.

### 0.5.6 Item 6: host migration in an ARENA+ AI session (2026-10-21, N01, n 3)

**Pass, 3 of 3.** When the host leaves, Nitro's own election makes the joiner the host (0x446ea0, "You are now the
host"); nitro_mp.c sees its role change from joiner to host in an ARENA+ session, starts a new hello round (the new
host's 'AH' goes to the group; it now also carries NO. DRIVERS in options bits 8..15, which joiners keep for exactly this
case) and calls nitro_ai.c's reconcile: the pool's parked / in-play split stays as the old host's last 'AT' said, the AI
rows stay (a joiner already holds them with their numbers), the AI cars are skilled again (their brains now run here),
old targets and death timers are dropped, the humans are recounted - so the fill brings back the car the leaving human's
slot had taken. The hello's human count no longer counts AI rows (it used to keep re-sending to them every 2 s).

Run: `pair.py` (lab), N01, NO. DRIVERS 4, host leaves by the stock end-of-session exit at 60 s of mission time
(`NMP_LAB_LEAVE_AT=60`: game state 3, as the Gold overnight harness did), joiner stays 160 s. Summary `tools/nitro-mp/migsum.py` (lab).

| run | migration on the survivor | reconcile (from the old host's last 'AT') | survivor, last status line | survivor in the arena at its end | crashes |
|---|---|---|---|---|---|
| mg-r1 | at 57.4 s, id 44 is the host | 2 in play, 0 dead, 5 parked, rows 3, NO. DRIVERS 4 | 1 human, **3 AI in play (4 - 1)**, rows 1 human + 3 AI | state 5 at 155 s | 0 / 0 |
| mg-r2 | 57.3 s | same | same | same | 0 / 0 |
| mg-r3 | 57.2 s | same | same | same | 0 / 0 |

The new host then runs the AI (orders, 'AT', respawn, kill credit) as a host from the start. Not measured: a third copy
receiving the new host's hello (two lab copies only), a hard exit of the host (ANet's time-out path).

### 0.5.7 Integration into the proxy (2026-10-21)

Commit 4fbbba1: `strlkproxy.c` gains 5 lines and nothing else - the include of `nitro_mp.c` / `nitro_ai.c` (with
`NMP_IN_PROXY`) after `mutesess.c`, `nmp_attach_shell()` in `hook_LoadLibraryA` for NITSHELL.DLL (Nitro only), and
`apply_nitro_mp()` in `nitro_dllmain` (Nitro only; it installs the LoadLibraryA hook if no other switch did). Switches
`I76_NITRO_MP` / `I76_NITRO_AI` (default on; README Nitro table). On Gold none of it is reached; on Nitro it is inert
outside an ARENA+ session, and the shipped proxy cannot create one yet (the host-form boxes live in the lab instrument),
so a shipped build carries the code dormant.

Build **4d82427e** (MSVC /O2, the music-fix tree at 4fbbba1's content; lab `builds/nitro-mp-integ/`), base = HEAD before
the integration built the same way, **0b17a8c8**. Smokes with the nitro-port lane's harness on this lane's own copies
(`tools/nitro-mp/np-run-mp.ps1`, `gold-smoke-mp.ps1`, made from theirs by `mk_nprun.py`):
- **Nitro**, P01 straight boot, n 2: "nitro-mp: ON", "nitro-ai: ON (all 12 sites)", "nitro: 11 sites patched, 0 refused",
  nitshell hooks attached, P01 running with the player car at 20 s; crash log: only the usual first-chance 0xC0000096 at
  0x49acb7 (the PIT read the game handles itself; every Nitro log has it, NITRO-PORT s.7).
- **Gold**, t01 with the release-candidate tick19-42 preset, n 2: **the same 129-line set as the base, 0 CRASH lines**
  (compare_logs.py "same line set", integ r2 + r3 against base r1 + r2). Integ r1 differed by one log line split in two by
  two threads writing at once (the cursor-map thread's "2 cursor pointer(s) taken" line); a third run was taken.
- **Re-run with the co-op code (e516e34 + 8e14a74, tree = HEAD ea3b250): build e4005491** (`builds/nitro-mp-integ/coop/`),
  Nitro P01 straight boot, n 2 (coop-p01-r1, -r2): the same log lines as 4d82427e plus the two co-op lines ("co-op: 7/7
  player-spawn calls ...", "nitshell co-op mission check 2/2 sites"); P01 running with the player car at 20 s; crash log:
  only the PIT first-chance 0xC0000096 at 0x49acb7. The lab copy's own proxy (d167eebe) was put back after each run.
- **Sim rate, measured on the side:** the evening runs advanced 0.856 sim-s per wall-s (11-21 s), the 12:56 runs 1.052.
  Not the build: an interleaved control at 20:23-20:54 (4d82427e, e4005491, base 0b17a8c8; n 2 each, `ratectl.sh`)
  gave 0.856 for all six, the base without any nitro-mp code included. nitplyr.def is byte-identical to the other Nitro
  copies; the cause is outside this lane (machine state between 13:00 and 19:48) and is left to whoever owns Nitro timing.

### 0.5.8 Item 7(d): lobby isolation - answered by prior art, without touching the live lobby

**Answer (2026-10-21, coordinator, from prior art):** I26 (vahokif, github.com/vahokif/I26, a C# / Godot
reimplementation of I'76 multiplayer) registers its OWN ANet species **18726 (0x4926)** on the stock lobbies
alink.bz911.net and alink.iondriver.com, and its INTERNET list works. So the community lobby keeps and serves a session
table for an unregistered species, per species, exactly as this lane read from anet2.dll (s.0.5.3): risk R3 is retired and
stock Nitro clients (subscribed to 604) never receive another species' sessions. Read-only check of I26's decompiled
client (`Downloads\i26-0.6.0\decompiled\I76.Net\I76.Net.Anet\`, AnetWire.cs / AnetClient.cs; nothing copied) agrees
with anet2's own code: login packet `'e1'` + species (u16), session table key {1, species lo, species hi}, table
subscription `'d^'` + key length + key (anet2 `0x020f6480`, base 0x020F0000).

**Consequence for ARENA+**: the lobby route needs no server change. A patched client on a lobby subscribes a SECOND session
table, key {1, 0x76, 0x76}, beside the stock one {1, 0x5c, 0x02}; ARENA+ hosts register their sessions under 0x7676 as
they already do (dpOpen with our species). `nmp_lobby_subscribe()` stays a stub until it is written against the open
source ANet 0.10 (Dan Kegel's anet, LGPL 2.1: dptab_requestSubscription, the session record, login) rather than the
anet2.dll dump; it is not measured, and no lab session was ever put on the live lobby. Until then ARENA+ is used on IPX /
LAN (and virtual LANs); the lobby test stays an owner-approved step (a session on the live community server is visible
to its players).

### 0.5.9 Item 5: CO-OP SCENES on Nitro's own P01 (2026-10-21; owner: no Gold missions)

**P01 with host + joiner: pass, 4 of 4 (cp-r5 added 21:00). The box-off control on P01, n 2: the stock refusal, as expected (end of section).**

Code (commit e516e34, `nitro_ai.c` co-op block; lab list entries in arena_poc.c `NMP_LAB_COOP_LIST`):
- **List**: with CO-OP SCENES on, the host form lists Nitro's own P01-P19 (`miss16\Pnn.MSN`, loose files of every
  Nitro install); the stock list is not touched otherwise.
- **The shell's mission check** (0x1002fda0) knows only arena extensions and answers "Mission file p01.msn not found" for a
  .msn (seen in the first try, cp-x1). In an ARENA+ session on pNN.msn its two calls (host create 0x1002fadc, join reply
  0x10030106) are answered with the file's CRC-32 on both sides (`caada4fd` for P01 on host and joiner, every run).
- **Spawn points**: a campaign mission has no team-0 spawn points; 4 are written beside the mission player object at load.
- **The host drives the mission's own player object** (adopted at the 7 player-spawn calls, linked with 0x446a90, as
  Gold's coop_spawn), so the script watches the host; on the joiner that object is the host's remote car.
- **Script and AI on the host only**: joiners skip ai_FrameTick; every mission vehicle goes to them in 'AT' (2 per packet)
  and is mirrored; damage to them is computed on the host; their trigger pulls are replayed.
- Not ported: CB radio ('AC'), objectives ('AO'), the scene chain ('AM'), per-joiner scaling.

| run | mission check (host / joiner) | host drives the player object / joiner shows it | both in P01 | mission cars, host vs joiner (same 5 s stamps, first 10 s after the join left out) | crashes |
|---|---|---|---|---|---|
| cp-x2 | caada4fd / caada4fd | yes / yes | yes (joiner in for its whole 80 s) | 120 samples, median 0.00 m, max 0.6 m | 0 / 0 |
| cp-r1 | same | yes / yes | yes (100 s) | 152, median 0.00, max 3.7 | 0 / 0 |
| cp-r2 | same | yes / yes | yes (100 s) | 152, median 0.00, max 1.7 | 0 / 0 |
| cp-r5 | same | yes / yes | yes (100 s) | 151, median 0.00, max 0.0 | 0 / 0 |

Over the four: 575 samples, median 0.00 m, p90 0.58 m, max 3.7 m (the first three alone: 424, 0.00, 0.61, 3.7). Two cp-r runs
lost their joiner to an .fps-lock taken in the 2 s between the two boots (the joiner's runner waits, the host plays alone):
cp-r3 and cp-r4; neither is counted. `cpretry.sh` counts a cell only when both logs exist. (cpsum.py's own line skips
one 5 s stamp, not two, and so shows cp-r2 with a 969.6 m outlier at the stamp right after the join; the table uses the
10 s rule above for every run.)

**Stock behaviour on P01 (the control asked for).** A stock Nitro session cannot be on P01 at all: the stock shell refuses
a .msn at BROADCAST ("Mission file p01.msn not found", the stock check, seen in cp-x1 before the co-op check existed). With
the box off our check passes straight to that stock code (it acts only on the ARENA+ species), and single-player P01 with the
integrated proxy ran unchanged (s.0.5.7, n 2). **The box-off pair runs, cp-s1 and cp-s2 (19:09-19:25,
`cpmatrix2.sh`):** the same host steps with the box off: the session went out as species 0x025c (604, stock), the co-op
mission check never ran (no CRC line on either side), the stock shell answered "Mission file p01.msn not found" in both
runs, no player object adopted, no 'AT', 0 / 0 access violations. So with the box off P01 behaves exactly as stock Nitro.

### 0.5.10 The host-form boxes in the shipped proxy (2026-10-21 evening, owner's request; `music-fix/nitro_form.c`, commit 6760b24)

**First look at the console** (consoleshot.ps1: lab copy on the physical desktop, .fps-lock + .console-owner for the
boot, a real screen capture): `i76-uncap-lab\captures\nitro-mp-20261021\arena-plus-hostform.png` is the lab
instrument's box of s.0.5.1. **It sat on the art**: "ARENA+" over the arena list's lower arrow and "[X] AI DROP-IN" over
the OPTIONS header. The strip under the list (s.0.3 item 5) is not free. The free parchment is the **middle of the car
panel** (between the front view, ending at y ~172, and the side view, starting at y ~307, left of the WEAPONS / PARTS
column at x 457); no stock hit rectangle lies there (s.0.2).

**Shipped form** (`arena-plus-hostform-shipped.png`, the same console, both boxes ticked by the lab driver's clicks): at
x 232, y 182-295 in form pixels: the label ARENA+, the owner's description unchanged and wrapped over four lines
("Every arena plus the / original '76 missions, / with AI filling the / open slots."), then `[X] ARENA+` (hit id 0x10)
and `[X] CO-OP SCENES` (0x11). Text widths measured at the first draw: 60, 174, 173, 163, 98, 90, 152 px (free width 218).
- ARENA+ on: species word 0x7676 (the session is ARENA+, AI fill the open slots). CO-OP SCENES on: Nitro's own P01-P19
  appended to the arena list (24 -> 43 entries on the copy), ARENA+ forced on; ARENA+ off clears both.
- Both off (the default, and again on every new entry into the network menus, i.e. a fresh hit list): nothing is
  written - the species word stays 604, the arena list untouched; a stock session.
- Sites (nitshell f804f50d, each byte-checked, all or the feature is OFF): the constructor call 0x10001531 (our hit
  records once per hit list, first draw), the click `ja` 0x1003219b (ids 0x10 / 0x11, then the stock exit), the redraw
  0x10033770 through the constructor's frame-pointer immediate 0x100318f7 and its three direct calls 0x1002e740 /
  0x10037a0e / 0x10037c45 (stock redraw, then ours). Drawing uses the form's own erase 0x10012a50 and text 0x10012dc0
  with the form font. `I76_NITRO_FORM=0` leaves the form stock. Log: `nitro-form: ON - 6/6 nitshell sites ...`.

**Isolation cells c1-c4 again (step 2 of s.0.5.2), n 2, on this code** (`tools\nitro-mp\isocells.sh`; the instrument as
control, NMP_POC=2, only drives the menus; the boxes are nitro_form.c's, clicked at 240,261; nmpdrv b577183c):

| cell | host | JOIN list | every read (15 per boot) | runs |
|---|---|---|---|---|
| f1 | box ON: `click id 0x10 -> ARENA+ on; species 7676`, `dpOpen species 7676` | patched | 1 session "ARENA+ Evening Stroll", species 7676, 1/4 | r2, r3 (r1 passed at 22:01; its logs were overwritten by a stray retry of this lane's own, so r3 was taken) |
| f2 | box ON, 7676 | stock (no hooks) | 0 sessions | r1, r2 |
| f3 | box OFF: `dpOpen species 025c` | stock | 1 session "Evening Stroll", species 025c, 1/4 | r1, r2 |
| f4 | box OFF, 025c | patched | 1 session "Evening Stroll", species 025c (no prefix) | r1, r2 |

0 access violations on either side in every counted run. The shipped proxy built from 6760b24, **0ea7922e**, P01 straight
boot n 2 (form-p01-r1/-r2): `nitro-form: ON - 6/6`, nitro-mp / nitro-ai ON, P01 running at 20 s, only the PIT
first-chance 0xC0000096.

### 0.5.11 ARENA+ under the whole-sim tick (commit 91d2b14; the nitro-mac lane's finding)

With `I76_SIM_TICK_MS` on, simtick.c's gate takes `call 0x4076f0` at 0x432e24 (ai_FrameTick) before nitro_ai.c, and
nai_call refused the site ("not `call 0x4076f0` - OFF"), so a joiner would have run its own AI under the tick (the Macs
ran a 24 fps cap instead). Fix, in nitro_ai.c only (simtick.c not touched): `nai_call_chain` keeps the site's current
target as the next hop - the tick's gate 7, which runs ai_FrameTick on tick frames - and our wrapper runs first (joiner:
skip; host: the next hop). If the tick patches after us, st_call_site already chains to us. The wrapper now also passes
ai_FrameTick's one cdecl argument (it called it with none before). Log: `nitro-ai: site ai_FrameTick at 0x432e24 already
calls 0x6d648060 (stock 0x4076f0) - chained` and `nitro-ai: ON (all 12 sites)` next to `sim-tick: ON - whole sim every
41.667 ms ... 12/12 sim gates`.

Measured on the **shipped proxy itself, 5cb92ac2** (= 91d2b14), on both lab copies: the instrument in chain mode
(`NMP_CHAIN=strlkprx.dll`: it drives the shell and logs; the proxy runs ARENA+, AI, the form and the tick;
`tools\nitro-mp\aitick.sh`), item 4's cell ai-c7 (N01, NO. DRIVERS 4, AI armour 1 %, host shoots every 7 s, joiner every
5 s, host 300 s, joiner 240 s):

| run | tick | AI in play (host alone / with joiner, both screens) | AI kills (host-credited / joiner-credited), respawns, joiner rebuilds | rows at the last common stamp | AI sync host vs joiner | AV host / joiner |
|---|---|---|---|---|---|---|
| ai-t1 | 41.667 | 3 / 2 | 41 (27 / 14), 43, 38 | agree | 55 samples, median 0.00 m, max 1.3 | 0 / 0 |
| ai-t2 | 41.667 | 3 / 2 | 25 (7 / 18), 25, 25 | agree | 44, 0.00, 1.4 | 2 / 0 (*) |
| ai-t3 | 41.667 | 3 / 2 | 45 (24 / 20), 46, 40 | agree | 53, 0.28, 1.4 | 0 / 0 |
| ai-o1 | off | 3 / 2 | 15 (11 / 4), 15, 13 | agree | 79, 0.00, p90 0.00, max 401.7 (one stamp) | 0 / 0 |

Every run: the joiner took an AI slot (one parked on the join, three brought back), and the AI killed a human 0-2 times.
(*) ai-t2 host, t 218.8 s: a first-chance access violation in **`nai_lab_tick` + 0x30b** (the LAB shooter,
`NMP_LAB_SHOOT`, never set outside the lab: it follows a target pointer that a respawn can free), then one in anet2.dll
+0x14d6; the game handled both and played to the end of the hold, rows still agreeing. A lab-switch bug, not a
shipped path; to be guarded before the next lab run with the shooter.

### 0.5.12 Cross-machine pass (PC host, Mac joiner): ready, waiting for hands at a Mac

The nitro-mac lane installed Nitro + proxy ad904941 on the three Macs (same wire format as 91d2b14: the hello's option
byte is the only new content, and joiners only log it). No Mac can be put on the JOIN list unattended (two locked, the
third hit-tests the real macOS pointer), so the pass runs when the owner or one of the boys is at a Mac:
- PC host: lab copy exp-nitro-mp, `builds\nitro-mp-form\host\Strlkup.dll` (5cb92ac2; README + MD5SUMS there), IPXWrapper
  instance N on the real LAN adapter (`tools\nitro-mp\ipx-lan.ps1 -Use N`: UDP 54792, Ethernet B0:6E:BF:38:13:31 =
  192.168.1.81 only, net 00000001, node 02:4e:00:00:76:03 - the Macs' defaults; broadcast 192.168.1.255). The firewall
  allows the copy's nitro.exe on the Private profile, which the Ethernet network is. Host by hand (HOST > IPX, tick
  ARENA+, BROADCAST) or by `tools\nitro-mp\xhost.sh <tag>` (the lab driver, N01, 4 drivers, 300 s).
- Mac: open "Interstate 76 Nitro", MULTIPLAYER > MELEE > JOIN > IPX, pick "ARENA+ <name>", JOIN GAME.
- Measure item 4's cells, n 3: AI count on both screens, the joiner takes a slot, respawn, kills both ways, rows
  agree, 0 crashes; the PC log plus the Mac's mciproxy.log lines (`nitro-ai: t ...`) go through aisum.py.

### 0.5.13 Cross-machine pass, first try (2026-10-22 05:21-06:01): PC host up and advertising, no Mac joined

**Result: no joiner, because neither Mac was running Nitro.** The PC side worked as planned. The owner had been told the
boys were waiting on JOIN > IPX, but a read-only process list over ssh (via the laptop, 100.66.69.126) at 05:23,
05:35 and 05:52 showed no nitro.exe and no Wine game process on Andrew's Mac (.205: only a winedevice.exe left over
from Oct 17) or on Michael's (.226: no Wine process at all); both were logged in at the console.

PC host (`tools\nitro-mp\xlan.sh`, two sessions of 20 min, the second a restart as the brief allowed):
- lab copy exp-nitro-mp, the shipped host build **5cb92ac2** (= 91d2b14, `builds\nitro-mp-form\host`) as `strlkprx.dll`
  under the menu driver in chain mode (nmpdrv be8803c6). The driver only clicks the menus: HOST > IPX, the shipped
  `[X] ARENA+` box (`nitro-form: click id 0x10 -> ARENA+ on, CO-OP SCENES off; species 7676`), BROADCAST GAME.
  No LAB switches; NO. DRIVERS 6; arena N01 "Evening Stroll"; mute watcher on (the game plays on the console speakers).
- `nitro-mp: dpOpen species 7676 'Evening Stroll' -> 0 (ARENA+)` both times; the host's hello went to the group.
- IPXWrapper instance N on Ethernet only (B0:6E:BF:38:13:31, 192.168.1.81), UDP 54792, net 00000001, node
  02:4E:00:00:76:03: **303 session broadcasts per session to 192.168.1.255:54792** (every 4 s), each looped back
  from 192.168.1.81 as expected.
- **Received from the Macs: nothing.** No packet from 192.168.1.205 / .226 / .116 and no node 52:E0:94:CB:EC:D3 or
  AF:8D:65:E0:5D:84 in either session's IPXWrapper log. The Macs answer ARP (both present on the LAN; ping is
  dropped, macOS stealth mode).
- The game ran: humans 1 at every 5 s stamp (478 stamps), 5 AI in play throughout (NO. DRIVERS 6 - 1 human), the AI
  killed each other and respawned (22 and 6 respawns), no access violation, only the PIT first-chance 0xC0000096
  in the crash log. Both sessions ended by the driver's hold (1200 s) and the process stop; the copy went back to the
  lab DLL (b577183c) and instance L (1ca45be0) after each.

What the Macs have to see once Nitro runs there: on MULTIPLAYER > MELEE > JOIN > IPX, within a few seconds, a row
"ARENA+ Evening Stroll" (1/6, combat). If a Mac's enumeration requests reach the PC but the row never lists there, the
likely cause is Michael's macOS firewall (the nitro-mac lane: entries only for the Gold app's wine / wineserver, none
for the Nitro app; macOS asks on his screen the first time the app opens UDP 54792).

Next try: the same `xlan.sh` (hands at a Mac first: confirm `nitro.exe` runs there before the PC boots).

**Feasibility (owner's question, no build): ARENA+ and co-op as entries of the stock GAME TYPE list.** The list is
nitshell's own: a static table of 5 string pointers at `0x10045898` (Combat, Racing, C.T.F. (2) / (3) / (4),
NULL-terminated at `0x100458ac`), drawn by the popup routines (`0x100341e0` draws the rows, `0x10034250` the popup) with the bound `5`
hard-coded twice (`cmp ebx, 5`, `cmp esi, 0x100458ac`). Choosing type t sets `[0x10045860] = t`, the form's
one-bit game-type mask `[0x1017a07c]` (`1 << cl`) (form byte 0x35: the session's player data key 5, which every joiner
reads to show the type) and the team flag for C.T.F., then a 5-way jump table at `0x100346f8` rebuilds the arena
list for the type (Combat 0x10035800 = *.cbt, Racing 0x10035a50 = *.rac, C.T.F. 0x10035c40(n)). Two entries
("Arena Drop-In + AI", "Co-Op") can be added behind a switch without moving a stock widget (the popup is drawn only
while open): our 7-entry table, the two bounds and the popup height patched, the jump table's range check widened
to our two handlers (Combat's list + species 7676; P01-P19 + species 7676). The cost is on the joiner side: the
type bits 0x20 / 0x40 reach every joiner in key 5, and a stock Nitro indexes its 5-entry tables with them; it never
sees a 7676 session, but a patched joiner must carry the same table to show the type. About 2-3 days (popup geometry
and click range, type -> list / species, joiner display, the isolation cells and item 4's cells again). The boxes
stay as they are until the owner rules.

### 0.5.14 Michael's session (2026-10-22 07:12-07:20): the PC host never came up

Nitro ran on Michael's Mac (.226) from 07:12:32 (`Interstate 76 Nitro.app`, `nitro.exe -glide`, ssh process list at
07:14). Its IPXWrapper bound node 00:00:00:01/AF:8D:65:E0:5D:84 (port 21156). The PC host (`xlan.sh x-lan3`, 07:14:21)
waited for `.fps-lock`, which the terrain-geomorph lane's queue held (MORPH-BASE r1, 07:18); no PC game ran, so
nothing was advertised and nothing from .226 reached the PC. Michael's nitro.exe was gone by 07:20; his proxy log ends
at 07:14 in the shell (state 6) with no CRASH / EXCEPTION line, and the newest macOS crash report is from 05:06, so it
reads as a quit, not a crash. x-lan3 was stopped (this lane's processes only); the copy went back to b577183c /
instance L. Lesson for the next live pass: hold `.fps-lock` from the moment a human is waiting, not from the boot.

### 0.5.15 Headless cross-machine pass: the Mac joiner works; the join is broken by the PC's Tailscale route

**The headless joiner** (owner's ruling: no person at the Mac). `tools\nitro-mp\xmac.sh <tag> [laptop | user@mac]`:
the PC hosts through `xlan.sh` (exp-nitro-mp, instance N, shipped proxy 5cb92ac2, the ARENA+ box, N01, 6 drivers);
once the host's `dpOpen species 7676` is logged, the Mac joiner starts over ssh (`xmac-join.sh`; a boy's Mac through
the laptop, `xmac-hop.sh`). On the Mac: a lab clone `~/i76-nitro-mp-lab/Interstate 76 Nitro MP Lab.app`, made by the
repo's `tools/mac-test-clone.sh` (APFS clone of the Mac's Nitro app, own bundle id, Wine null audio, movies skipped);
its game folder holds the driver nmpdrv **a090f021** as Strlkup.dll in chain mode in front of the proxy 5cb92ac2
(strlkprx.dll); started with `open -n --env ...` (NMP_POC=2, NMP_ROLE=joinplay, NMP_RAWPT=1, NB_ACTIVE, NB_SKIP_MOVIES).
The shipped Nitro and Gold apps are untouched (ad904941 read back on both Macs). Driver changes for Wine + DxWnd:
a NITSHELL watch thread (DxWnd holds the LoadLibraryA slot), the scripted point handed raw to nitshell's GetCursorPos
with its ScreenToClient import passing it through while scripted, and a two-point calibration of the shell's mouse
object before navigating. No macOS pointer, no AppleScript, no sudo.
- Laptop smoke (mtest3): the shell up 4 s after start (the null audio removes the 40 s+ DirectSound wait on the EVO4),
  calibration 1:1, every click read back exactly (469,311 / 417,351 / 439,379 / 364,406), JOIN > IPX list reached.

| run | Mac | listed | JOIN GAME | joiner `dpOpen` | host saw the joiner | in game |
|---|---|---|---|---|---|---|
| x-mac1 | laptop (node D6:FB:E1:0B:F6:6C, 192.168.1.241) | "ARENA+ Evening Stroll" 7676 1/6 | clicked | none logged | enumeration only (Mac IPX log level 0) | no |
| x-mac2 | laptop | same | clicked | `-> 0 (ARENA+)` | yes: "humans 1 -> 2", an AI parked for the joiner, then "2 -> 1" | no (shell, net 0) |
| x-mac-a1 | Andrew (52:E0:94:CB:EC:D3, .205) | same | clicked | `-> 0 (ARENA+)` | enumeration only | no |

**Why the join stops: the PC sends its unicasts through Tailscale.** The PC's Tailscale accepts subnet routes
(`RouteAll: true`) and holds `192.168.1.0/24 via 100.100.100.100`, metric 0, ahead of the Ethernet on-link route
(metric 256). `Find-NetRoute 192.168.1.241` answers Tailscale. Broadcasts leave on the Ethernet (the session lists on
every Mac), but every PC -> Mac unicast goes out through Tailscale to the subnet router 192.168.1.141 (MAC 90:09:d0,
a Synology) and reaches the Mac with that source address: the laptop's IPXWrapper log shows the host's replies "from
02:4E:00:00:76:03 (192.168.1.141)", and the laptop answered 18 times to 192.168.1.141:54925 and 3 times to
192.168.1.81:54925. Andrew's Mac never got a host unicast at all and sent its 11 join packets to 192.168.1.81:61363 (the
host socket's source port, learned from the broadcasts), none of which the PC logged. So listing works and the
session handshake does not. Fix (the owner's network, not this lane's: no admin here): `tailscale set
--accept-routes=false` on the PC (at home the LAN is direct anyway), or as admin a 192.168.1.0/24 route on the Ethernet
with a lower metric. Then x-mac laptop n 2 and Andrew again. Andrew's direct 192.168.1.81:61363 packets may also need
a look at the PC firewall afterwards if they still do not arrive.

### 0.5.16 Cross-machine pass after the route fix: the Mac's missing data-path key, found and fixed; first Mac joins (2026-10-22)

**Route.** Main ran `tailscale set --accept-routes=false` (owner's approval); `Find-NetRoute 192.168.1.241` now answers
Ethernet. In x-mac3 every host packet reached the laptop from 192.168.1.81 (177 / 177, none from .141), traffic both ways.

**The next blocker was the Mac prefix, not the network.** The joiner's main thread sat in a USER32 modal loop called
from NITSHELL+0x2ffab (x-mac4: `win32u / USER32 x4 / NITSHELL.DLL+2ffab`), the error box of the shell's mission-file
check 0x1002fda0 ("Mission file %s not found."). With nitshell's file opens logged (x-mac6) the joiner looked for
`addon\N01.CBT` and `\N01.CBT` only. The base path comes from ShellMain's interface [0x1004e840]: +0x78 = nitro.exe
0x4be830 and +0x70 = 0x468340 (the CD drive letter byte [0x590a74]). 0x4be830 asks 0x4be700, which opens
`HKLM\SOFTWARE\Activision` and reads `Interstate '76 Nitro Pack\Minimum`: key absent -> "use the CD" -> `Install\data\miss8`
on drive letter 0 -> "\N01.CBT" (the driver's probe on the Mac: `+0x78 -> 1 'Install\data\miss8'; +0x70 -> 0`); value "0"
-> local `miss8`. The PC has the key through UAC's VirtualStore (`HKCU\Software\Classes\VirtualStore\MACHINE\SOFTWARE\
WOW6432Node\Activision\Interstate '76 Nitro Pack`, Minimum = 0); no Mac prefix has any Activision key (the shipped apps on
the laptop and Andrew's: 0 lines). A workaround answering the check for every ARENA+ mission (build 0cf952e6, x-mac7) got
the joiner past the box and into the arena, where it faulted at **nitro+0x9785b** `mov cx, [eax + edx*2]`, eax 0 - the
crash the owner reported (owner-mac-join-crash-1.txt; same registers as x-mac7's CRASH line; strlkprx.dll loaded and
Darwin 25.6.0, so it was the laptop's lab clone, not Andrew's and not a shipped app). 0x497790(x, z), called from
0x406cf8 for an object's +0x40 / +0x50, reads the terrain cell word from the row table **0x5fb660** (16384 row pointers
of 128 words), which the mission's terrain load fills: with the data path on a non-existent CD the terrain never loads.
The workaround was dropped (diff kept in `builds\nitro-mp-macjoin\crc-workaround.diff`); the cause is fixed instead:
**`"Minimum"="0"` under `[Software\\Activision\\Interstate '76 Nitro Pack]` and its Wow6432Node twin in the prefix's
system.reg** (`tools\nitro-mp\xmac-minimum.py`), written to the lab clones on the laptop and Andrew's Mac.

| run | session | proxy (both sides) | Mac | listed | joiner in the arena | host | rows | crashes |
|---|---|---|---|---|---|---|---|---|
| x-mac8 | **stock 604** (box off) | 5cb92ac2 | laptop + key | "Evening Stroll" 025c | **yes**: t+5 s state 5, net 1, me 44, host 40, players 2 | joined | (stock: no AI rows) | 0 / 0 |
| x-mac9 | ARENA+ | 5cb92ac2 | laptop + key | - | no: the Mac boot faulted in wined3d (0 at wined3d+0x162430, frame 0) before the shell - the first-boot flake of NITRO-MAC s.1 | - | - | Mac 1 (boot) |
| x-mac10 | ARENA+ | 5cb92ac2 | laptop + key | "ARENA+ Evening Stroll" 7676 1/6 | **yes**: t+5 s state 5, net 1, me 44, host 40, players 6; in play to t+115 s (its log ends there) | humans 1 -> 2, an AI parked; 2 -> 1 later | **agree**: the host's last line before the leave and the joiner's last line hold the same rows (40 0/0/0, 44 0/2/0, AI 32259 3/0/3786, 32258 0/1/0, 32257 0/0/0, 32260 0/1/0) | 0 / 0 |
| x-mac11 | ARENA+ | 5cb92ac2 | laptop + key | same | no: JOIN GAME clicked, no dpOpen followed (not explained yet) | - | - | 0 / 0 |

Laptop ARENA+ joins: 1 of 2 counted runs (x-mac10); x-mac11 to be explained. In x-mac10 the joiner took a slot, the
AI were mirrored ('AT' applied 2004) and killed the joiner twice (its row 0/2/0 on both sides), the host's shooter
credited one kill; the joiner's LAB shooter never fired on the Mac ("fire keys read 0 times"), so kills by the joiner
were not measured. The time-matched sync / row stamps of aisum.py do not apply across machines (two clocks); rows were
compared by content. **Andrew's Mac (n 2) was not run**: the lock window closed (11:50). The 5 s stamp grid, the Mac
shooter and x-mac11 are open.

**For the boys' apps** (staged, not installed: `builds\nitro-mac-update\`, README + MD5SUMS): (1) required for any join,
stock or ARENA+: the registry key above in the app's prefix (no DLL); (2) optional: Strlkup.dll ad904941 -> 5cb92ac2 (the
host form + the tick-safe AI skip; 91d2b14 includes the Mac fixes of 3d7c3e0). Stock 604 joins on the Macs hit the same
box without (1) - x-mac8 confirms the key alone fixes a stock join.

### 0.5.17 GAME TYPE entries instead of the boxes, phase 1: host side (2026-10-23, game-types lane; owner ruling of the day)

Owner ruling: the ARENA+ / CO-OP SCENES boxes become two entries of Nitro's stock GAME TYPE popup, **"Arena Drop-In + AI"**
and **"Co-Op"**. Phase 1 = host side, lab only. Code: `music-fix/nitro_form.c` behind **`I76_NITRO_GAMETYPES=1`** (unset =
the boxes, unchanged), commits b0a2420, c8b6d33. Lab: copy **`exp-nitro-types`** (of exp-nitro-mp), tooling and builds in
`i76-uncap-lab\builds\nitro-gametypes-20261023` (lab 1446ea5, b26e76f).

**Design as built** (static RE of nitshell f804f50d; 16 sites, each byte-checked, all or nothing; header G1-G6 in the file):
type 6 = "Arena Drop-In + AI" (form mask `1 << 5` = 0x20), type 7 = "Co-Op" (mask 0x40). The stock code sets both from the
popup row by itself (`0x100342bf`). Mask 0x20 / 0x40 gives the session no mode flag (`0x1002fbff`: 1 -> 0x10, 2 -> 0x20,
4 / 8 / 16 -> 0x40, else none), and 0x10 has no exe reader, so the exe runs a combat game. The team flag stays 0.
- G1 the popup-open call `0x10032391` -> 7 rows on provider 3 / 4 (the modem forms keep their 3 stock rows), our row draw.
- G2 the type-change switch (`cmp eax, 4` 0x100342f7 -> 6; `jmp [eax*4 + 0x100346f8]` -> stub): 6 = Combat's list + species
  7676 + options ARENA+; 7 = P01-P19 as the whole list + 7676 + ARENA+ / CO-OP SCENES; 1..5 = stock, species 604.
- G3 the limit popup's two type switches (0x10032771 / 0x1003277a, 0x10036f36 / 0x10036f3f): 7-entry copies, 6 / 7 = Combat.
- G4 the six reads of the form-field name table 0x10045894 -> our table; field names "Arena + AI" / "Co-Op". The field is
  100 px wide (erase 105,68,100,18) and the long name measures 162 px, so the field shows the short name.
- G5 the prefs save `0x100320aa` stores 6 / 7 as Combat. The type is saved in the prefs block 0x1015b950 and restored at the
  next entry (`0x10031420`), and a stock shell (or the switch unset) would then index its 5-entry tables with a 6 or 7.
- G6 the mode-string lookup `0x1002e978` (key "Unknown" for an unrecognised mask) -> our names. This is for phase 2 and
  has not been observed in a run yet.
- The constructor re-derives the options and species from the type on every form construction. A new entry into the
  network menus restores a type of 5 or below, so the species goes back to 604.
- Bug fixed on the way (box mode too): the co-op list records now come from the shell heap `[0x1004d630]`. Every list
  rebuild frees the items with HeapFree (`0x1000e080`), and 6760b24 had handed it static records.

**Headless results** (private desktop, nmpdrv instrument as control with `NMP_POC=2` + `NMP_NET=1` + `NMP_AI=1`, 4 drivers,
IPX host, `NMP_LAB_TYPE=<row>` clicks the stock arrow 207,76 and the row; read back from the log at dpOpen;
`captures\nitro-mp-20261021\gt-*.log`):

| cells | type chosen | read back at dpOpen | after 35 s | n |
|---|---|---|---|---|
| a4 a5 a6 | row 5 "Arena Drop-In + AI" | type 6, mask 20, team 0, options 01, **species 7676**, list 24 (Combat's) | state 5, net 1, **players 4** (host + 3 AI fill) | 3 |
| c4 c5 c6 c7 | row 6 "Co-Op" | type 7, mask 40, options 03, **species 7676**, list 19 (first "Co-op P01") | state 5, P01 as a co-op scene (host drives the mission player `vagrapl1`) | 4 |
| s2 | row 0 Combat (switch on) | type 1, mask 01, options 00, species 025c | state 5, players 1 | 1 |
| s0 | row 0 Combat, switch unset (boxes) | species 025c; popup 5 of 5 rows, 172 x 152 | state 5 | 1 |
| a1-a3, c1-c3, s1 (first build, no `NMP_AI`) | as above | the same type / mask / species readings | arena host in state 5; co-op host stayed in the shell (state 6). Cause: nitro_ai.c's co-op mission-file answer is not attached without `NMP_AI` (the shipped proxy always attaches it) | 3 + 3 + 1 |

0 access violations in all 16 boots. Only the known first-chance exceptions occurred: PIT 0xC0000096 at boot and the
periodic e06d7363 that the earlier lanes' logs also show. a4 / c4 / c5 ran before G6, and the rest ran on the final code
(proxy p3 3be2c330, instrument b14f3ae7).

**Seen (frame buffer, not PrintWindow: PrintWindow returns black frames on the private desktop):** the 8-bit back buffer
dumped at the open popup (`shots\gt-c4\popup-index-masks.png`, one mask per palette index):
- Index 15 holds all seven rows: Combat, Racing, C.T.F. (2) / (3) / (4), Arena Drop-In + AI, Co-Op.
- The type field after the choice reads "Arena + AI" / "Co-Op" (`field-a4-c4.png`).
- **Open: the popup art.** Index 225 shows that the popup's frame is **picture 0x24**, a fixed 172 x 152 bitmap. It holds the
  "GAME TYPE" header, 5 row boxes and a button at the bottom (the lower hit record, y 124-140). G1's taller and wider
  geometry only moves the drop shadow and the lower hit record, so rows 6-7 draw over the art's bottom and its button.
  The function is right, but the popup does not look right yet. Options:
  - (a) Borrow a taller stock list picture. Picture 6 (229 x 236, 9 rows, used by the form's id-11 popup and `0x1002b9fd`)
    needs one look at its header art first.
  - (b) Extend picture 0x24 in the back buffer after each art draw: copy a row band and move the button down. This needs
    the popup module's redraw path (`0x10012000` / `0x1002211b`) mapped first, so the surgery is not applied twice.
  - (c) Keep 5 visible rows and add scroll records (ids 0 / 1). This popup has no arrow art.

  (a) is the cheapest next step: one boot that opens popup id 11 and dumps the buffer.

**Phase 2 (planned, not run):**
1. Popup art: one of (a)-(c) above, then re-run a / c / s, n 3 each.
2. Joiner display: a patched joiner runs the same G4 / G6 tables. The joiner's lobby builds the mode text from the host's
   key-5 mask at `0x1002e8b8` (G6, unobserved so far), and the other readers of the joined mask (`0x1015b8cc`: 0x1002e216,
   0x100302d6, 0x10030b76) still need auditing for 5-entry indexing. Test: pair cells host type 6 / 7 x patched joiner,
   n 3 each, checking the joiner's list row and lobby text and that it joins the 7676 session. The stock-joiner cell (never
   lists a 7676 session) is the existing f2 cell, which stays valid because the species path is unchanged.
3. Mac cross-machine pass with the same cells (PC host, Mac joiner), once phase 2 passes on the PC.
4. Then make the entries the default, delete the box code (F2 / F3 sites, hit records, draw) and update s.0.5.10.

### 0.5.18 GAME TYPE entries, phase 2 (2026-10-23, game-types lane): popup art, patched joiner, Mac pass

**Popup art (option (a) of s.0.5.17, built):** the 7-row popup borrows the form's own 9-row list picture (6, 229 x 236,
the id-11 popup's geometry: rows from +22,+48, list hit 16-214 / 47-198, button 146-215 / 209-225) in place of the 5-row
picture 0x24 (`nft_popup`, commit 2481d87). The popup module adds the popup origin into the descriptor's row origin at open
(`0x10021fa9`), which the lab driver's first row click added twice (gt-pa1: 530,469; fixed in lab 6130732).

**Joiner side, static audit of the readers of the joined type mask** (`[0x1015b8cc]` / lobby struct +0xd4): `0x100302d6`
(mask -> session flags: 0x20 / 0x40 set no mode flag, as on the host), `0x10030b76` (team popup: only 4 / 8 / 16),
`0x1002e216` and `0x1002ed9a` (team-name table choice: only `== 1`), `0x1002e8b8` (the lobby mode text: 1 / 2 / 4 / 8 / 16,
else the key "Unknown" -> G6 answers our names). The JOIN list rows (0xe4 B at 0x101593b8) carry name, session record and
player counts only, no type. So a patched joiner needs nothing beyond G4 / G6 (which `nft_attach` installs on every
nitshell, host or joiner, under the switch).

**Screenshots:** PrintWindow gives black frames on the private desktops, so the instrument dumps the shell's 8-bit back
buffer and its palette (`0x10131790`, 256 x 8-bit RGB, the table the shell's palette routine `0x10011730` is handed; the
PALETTEENTRY table `0x100413ac` stays zero on the DirectDraw path);
`builds\nitro-gametypes-20261023\fb2png.py` makes the PNG.

**Popup art, as shipped:** picture 6's header reads MAKE / MODEL with a CANCEL button (gt-pa1 dump), so the popup keeps
picture 0x24 and stretches it in the 8-bit surface from the first row draw (`nft_stretch`, commit 0e77d5e): the bottom
band (button) down by two rows, row boxes 4-5 copied into the gap, then 24 columns added at x 30 from the plain columns
20-29 so "Arena Drop-In + AI" (162 px) ends inside its box; once per open (7 of 7 rows visible, no scroll redraw); the
hit records and the module's drop shadow follow. Screenshot (the shell's own surface + palette, 2x):
`captures\nitro-mp-20261021\shots\gametypes-popup-final.png` (gt-pa2 host); the host form after the choice:
`gametypes-hostform-arena.png` / `-coop.png`; the joiner's roster screen: `gametypes-joiner-arena.png` / `-coop.png`.

**PC-to-PC pairs** (`gt_pair.py`: host exp-nitro-types on IPXWrapper L, joiner exp-nitro-types-b on M, both the
instrument with the working-tree proxy, `NMP_AI=1`, 4 drivers; the joiner JOINs row 0; `gt-p*-host/-join.log`):

| pair | host chose | joiner listed | joined | after 50 s (joiner) / 90 s (host) |
|---|---|---|---|---|
| pa1, pa2 | "Arena Drop-In + AI" (type 6, mask 20, 7676) | 'ARENA+ Evening Stroll' 7676 | yes, hello options 0401 | state 5, **players 4** on both sides (2 humans + 2 AI) |
| pc1, pc2 | "Co-Op" (type 7, mask 40, 7676) | 'ARENA+ Evening Stroll' 7676 | yes, options 0003, P01 CO-OP SCENE on the joiner | state 5, players 2 on both sides |

0 access violations in the 8 boots (the known first-chance exceptions only). A first pa1 try was void: nmprun's own
foreign-process wait held the joiner 20 min past the host (the owner's daily driver came back); the runner now
re-queues a pair whose joiner saw no session.

**Where an IPX joiner would show the type:** the stock shell's only session-type text for a joiner is the mode line of
`0x1002e7c0` (called once from `0x1002f0dc` after the join reply; G6 answers "Unknown" there with our names). In these
4 joins the host was already in the mission and the joiner went straight in ("STAND BY..." then state 5), so that line
was never drawn; the JOIN list and the roster screen carry the game name only. G6 stays in, unobserved.

**Mac pass** (`gt_xmac.sh`: PC host exp-nitro-mp on IPXWrapper N over the LAN with this lane's instrument + the proxy p6
3ef77e9d as strlkprx.dll in chain mode, the GAME TYPE row chosen, 6 drivers, 300 s hold; Mac joiner = the lab clone
`Interstate 76 Nitro MP Lab.app` with the same proxy and `I76_NITRO_GAMETYPES=1` (xmac-join.sh arg 6), 150 s hold, null
audio, nobody at the Mac; Michael's Mac has no lab clone folder (`~/i76-nitro-mp-lab` absent) and was not used):

| run | Mac | host chose | Mac listed / joined | after 120 s (both sides) |
|---|---|---|---|---|
| gt-mac-a1, a2 | laptop | Arena Drop-In + AI | 'ARENA+ Evening Stroll' 7676, joined, hello options 0601 | state 5, **players 6** (2 humans + 4 AI) |
| gt-mac-c1 | laptop | Co-Op | joined, P01 CO-OP SCENE on the Mac | state 5, players 2 |
| gt-and-a1, a2 | Andrew | Arena Drop-In + AI | joined | state 5, players 6 |
| gt-and-c2 | Andrew | Co-Op | joined, P01 CO-OP SCENE on the Mac | state 5, players 2 |
| gt-mac-c2, gt-and-c1 | laptop, Andrew | Co-Op | **void**: the Mac's game reported state 5 with an empty mission buffer 46 ms after the driver attached and never reached the shell (the x-mac9 boot flake; the host side was fine) | - |
| gt-mac-c3 | laptop | Co-Op | **void on the PC side**: another lane took .fps-lock seconds after this script's pre-check; pair.py waited for it until gt_xlan's 900 s timeout, and the "session open" wait ran out without a failure exit, so the Mac (which reached the shell this time) listed 0 sessions. Script fix pending: a failure exit after that wait, a longer xlan timeout | - |
| gt-and-c3 | Andrew | Co-Op | not run (queued behind the scott-build gate run from 12:08; stopped at 13:10) | - |

The Mac's proxy log shows `nitro-types: ON - 16/16 nitshell sites` under Wine on every run (the same nitshell). 0 exceptions
in every counted Mac joiner log. Tally: arena join n 2 per Mac (laptop, Andrew), co-op join n 1 per Mac; the two co-op
misses are a Mac boot flake and a PC lock race, neither in the type code.

**Step 4 (entries as the default, boxes behind `I76_NITRO_GAMETYPES=0` for one release): not done.** The owner's gate was
(1)-(3) passing with n 2 per Mac; co-op stands at n 1 per Mac, so the switch stays opt-in (`I76_NITRO_GAMETYPES=1`) and
the box code stays. The flip is a two-line change in `nf_attach` (test `v[0] == '0'` instead of `'1'`), built and
checked as p7 8d4d50b6 but not committed. Left: one co-op join per Mac (`gt_xmac.sh gt-mac-c4 c laptop`,
`gt_xmac.sh gt-and-c3 c andrewvalentine@192.168.1.205` after the script fix above), then the flip, then the box code can go.

Lab copies: `exp-nitro-types` (host, IPXWrapper L) and `exp-nitro-types-b` (joiner, M), both with the instrument
a3889d8f / 8ba38c6a (`builds
itro-gametypes-20261023\drv`); proxies p1-p7 in that folder (p6 3ef77e9d = the code as
committed in 0e77d5e).

### 0.6 Changes to sections 3.4, 4 and 5

- **Lists (3.4):** dropped: the 17 Gold co-op scenes and the 7 Gold scenarios (combined content, owner ruling), the
  `addon\nmp\` Gold files and the radio-voice dependency. Kept: every Nitro combat arena with AI by memory injection
  (N51-N65 = the original arenas). Added: P01-P19 as co-op scenes behind CO-OP SCENES (Nitro's own files, listed only
  while that box is on), built like `coop-install.py` but from nitro.zfs; until they are built and measured, CO-OP
  SCENES stays off the form.
- **Name (4):** **ARENA+**, the owner's pick; the five-name table is kept as history.
- **Estimate (5):** piece 2 (shell entry, 2.5 days) becomes **host-form options + join list, 3 days, risk
  medium-high** (the first menu change on Nitro that has to hold; PoC step 1 is 0.5 day of it). Piece 5 (Gold co-op
  scenes + scenarios, 3 days, high) becomes **Nitro P-missions as co-op scenes, 2 days, medium**. Total **15**
  lane-days. Order: 1 (anet2 dump) -> PoC step 1 -> 3 (ANet 2 layer) -> PoC step 2 + gate 7(a-c) -> 4 -> 6 -> 5 ->
  7(d) -> 8.

## 1. ANet 2 map (nitro.exe + nitshell.dll)

### 1.1 Session create / join / list, lobby vs direct IPX

| step | where | what (decompiled; addresses in the RE notes) |
|---|---|---|
| provider | nitshell main menu ids 13..16 -> `[0x1004701c]` (host 2..5, join 6..9), `0x1002e4c0` | same numbering as Gold's shell (2 modem, 3 IPX, 4 internet, 5 null modem; +4 to join) |
| game server (lobby) | `0x10038610`: `dpCreate`, `dpEnumApp`, reads `internet.lst` / `lobby.dat`; `dpSetGameServer` at `0x1002e620`, `0x1002f2d0`, `0x10038610` | INTERNET only. IPX has no server: broadcast enumeration through WIPX2 |
| host | `0x1002f3c0`: `dpOpen(dp, &session, 0, 0)`, session record 0x5f bytes, **+0xd sessionType = 604**, +0x11 max players, +0x15 flags 0x41, +0x17 name; `dpCreatePlayer`; player data keys **1** team pick, **2** session name, **3** car block 0x198, **4** car CRC, **5** host form 0xe4; `dpCreateGroup("SIM")`; the setup block for the exe (0x324 B) | |
| list | `0x1002dfb0`: `dpEnumSessions(dp, {sessionType 604}, 0, 2000 ms, cb 0x1002e060)` | **the list asks for species 604 only** |
| join | `0x100307a0` (dpOpen of the picked session, dpCreatePlayer, keys); 'RE' resent every 500 ms with the password; 'JO' / 'JD' handled in `0x1002ffd0` | 'JO' checks: version "6.04" (`0x10045810`) and the mission file's CRC for `.cbt .rac .cf2-4 .lvl` (case-insensitive; Gold tested `.lvl` case-sensitively) |
| exe takes over | WinMain `0x431760` -> net init `0x448640` (dp `0x53f258`, me `0x53f25c`, net flag `0x53f264`), session options `0x4486d0` (flags word -> `0x53f228`, limits, password) | |

### 1.2 Receive path (the dpReceive we hook on Gold)

`net_Pump 0x448d80` (Gold 0x4532c0), called once per frame from WinMain at `0x432884`:

```c
while (DAT_006522ac == 0) {                       // pump-exit flag
  do { size = 0x200;
       r = dpReceive(DAT_0053f258, &from, &to, 0, &pkt, &size);   // IAT 0x4c13cc
  } while (r == 2 && ++tries < 3);
  if (r != 0) break;
  if ((short)from == 0) {                         // ANet system packets
    'd2' 0x3264 delete player / me -> pump exit;  'd1' 0x3164 add player;  'd5' 0x3564 added to group;
    'd9' 0x3964 "*** SESSION LOST - GAME OVER ***" (new in Nitro)
  } else if ((pkt.type & 0x8000) == 0) {
    FUN_00446bb0(from);                           // last heard
    switch (pkt.type) { 'RE','SC','SH','CH','BO','FL','SR','SP','ST','XX','YY' -> handlers }
    // any other type: nothing - read and dropped
  }
}
```

Other dpReceive callers: the join handshake `0x448950` (same as Gold 0x452f20), `0x446270` (wait for group + enum
players at load), `0x449400` (shutdown). The shell has its own receive loops (`0x1002ffd0`, `0x1002e620`, `0x1002f2d0`)
before the exe takes over.

**Consequence:** `patch_iat(exe, "anet2.dll", "dpReceive", hook)` (the import descriptor reads `ANET2.DLL`; patch_iat
compares with `lstrcmpiA`) gives the same position as Gold's hook: after the real call, before the pump's switch.
Sends go through `[0x4c13c0]` (dpSend). Every stock send uses flag 0 (unreliable), as on Gold.

### 1.3 Packet types, player table, slot flags

| item | Gold | Nitro |
|---|---|---|
| registration | none (2-letter app tags, `dppt_MAKE` order) | none; same tags + **'FL'** (flag) and system 'd9' |
| player table | 0x541070, 16 x 0x48 | **0x53ed08, 16 x 0x50**; new +0x44 float (init 1.0) and **+0x48 team int**; count 0x53ed00 |
| slot flags +0x1c | bit 0 joining, 1 team read, bits 16..18 team | same, plus bit 2 "team member announced", bit 3 "car team set" (`0x446390`) |
| team play | bool 0x541010 | **no bool**: team game = flags 0x53f228 & 0x40 (CTF) or & 0x2000 (TEAM PLAY), `0x4487e0` |
| host / group | 0x541064 / 0x541060 | 0x53ecfc / 0x53ecf8 |
| entity owner / dead bit | +0x480 / +0x454 & 0x20 | **+0x484 / +0x458 & 0x20** |

**Note for the port lane:** `sites_nitro.h` maps Gold 0x541010 -> 0x53f228 by vote. The address is right but the meaning
is not: 0x53f228 is a flag word (bit 0x8 is always set), so `aim_team_rule`'s `*(int *)0x541010 != 0` would read "team
play on" in every Nitro session. And Gold 0x452d9f (scoreboard create) is mapped to 0x4486b3, which calls 0x449730; the
scoreboard is `push 0; call 0x449ef0` at **0x4486ab** (Nitro passes an argument).

### 1.4 The 'ST' score path, host migration, the flag packet

- **Scores ride in 'ST'** as on Gold: the mirror `0x463a20` ends with `net_SetPlayerScore 0x447050` at **0x464409**
  (Gold 0x465267, unmapped in the port table). Kill credit 0x447140, death 0x4472e0.
- **Host migration** is the game's, not ANet's, and has Gold's shape: lowest id wins the handshake; a host change runs
  `0x446ea0` ("You are now the host!" / "%s is now the host!"), and the new host **republishes player data keys 2, 3, 5**
  (session name, car block, host form) under its own id (`0x4476c0`). CTF re-sends the flag state.
- **'FL'** `0x4451d0`: per team a state 0..5 (home, returned, dropped + x,y,z, captured by team, carried by player,
  carrier lost), messages "flag has been taken / returned / Team %s has captured %s's flag!", capture credit. CTF only;
  not touched by this design.

### 1.5 Vehicle validation: what a stock joiner of a patched host meets

On the **host**, `0x446120` runs from 'SR' (`0x445b99`) and from the first 'ST' of an unknown car (`0x445e13`):

```c
if (!hacks /*0x526a68, -hacks*/) if (dpGetPlayerData(dp, id, 4, &claimed_crc, &4, 0)) return 0;
v = parse_vcf(bytes, size);                       // key 0: the joiner's .vcf
if (!hacks && v) { ok = ValidateVcf(file_of(v), budget, &crc);   // 0x4b7bf0, the host's OWN .vdf/.wdf/.gdf/.cdf
                   if (!ok || crc != claimed_crc) { send 'BO' reason 1; "*** %s has tried to join with a hacked vehicle!";
                                                    dpDestroyPlayer(); } }
```

On the **joiner**, the shell checks the host's version string ("6.04") and the mission file CRC. Nothing checks the
host's exe or proxy. So a stock player joins a patched host's stock session exactly when the host's **car files and
mission files are stock** - which they are: this design changes no file the stock list or the car check reads (our
extra missions live in their own folder, our AI is injected in memory).

### 1.6 How races / CTF pick their mode

Not from the extension in the exe. The shell's game-type selector `[0x10045860]` (1 combat, 2 race, 3..5 CTF 2..4 teams)
picks **which files** the arena list reads (`*.cbt`, `*.rac`, `*.cf2..4`, each also from `addon\`), and the host form
sets the session flags the exe reads: 0x10 combat, 0x20 race (`0x448810`), 0x40 CTF (`0x448800`), 0x2000 team play,
0x100 / 0x200 / 0x400 / 0x800 / 0x1000 limit kinds. Bits 0x4000 / 0x8000 are never set and never tested (byte search of
every reference to 0x53f228 and the bit tests of its whole-word getter's 23 callers). This closes the open item in
`i76-map\data\notes\nitro.md` ("which setup bit the exe reads ... not traced").

### 1.7 anet2.dll itself: a loader stub (read since: section 0.5.3)

`anet2.dll`'s `.text` has 0xa00 file bytes for 0x15a00 in memory: an entry stub (`.dllent`) maps the real code from a
75 KB overlay. Ghidra sees the stub only. A 32-bit LoadLibrary-and-dump tool (`i76-map\nitro-net\tools\anetdump`) gets
error 1114 outside the game (n 3). ANet 2's internals (species filter on a game server, reliable send, its packet size
limit) are therefore **not read**; the design takes them from the exe / shell side and from Gold's measurements (2 'AT'
records = 208 B per packet arrive, 508 B did not). First item for the nitro-mp lane's first lab boot: dump the mapped
anet2 image from a running lab nitro.exe.

## 2. Nitro shell: the menu, the lists, where the entry goes (FALLBACK since section 0)

| piece | finding |
|---|---|
| screens | window messages (as Gold): 0xc00e main menu `0x10008690`, 0xc021 `0x1002a610` (single-player melee form, also `*.cbt`), 0xc024 single player (`addon\scenario.dat`), **0xc026 network entry form** `0x100318e0` |
| main menu | 19 buttons `Button_Init 0x1000e410(id, record, x, y, sprites, w, h, sprite, parent)` in `0x10009610`; sprites, no text strings. By layout and handlers [inferred, not seen on screen]: id 1 opens the melee group (ids 9 and 0xc at y 0x154), **id 9 = multiplayer melee** (shows HOST 10 / JOIN 11 at y 0x170), id 0xc = the single-player melee form (0xc021), ids 13..16 the providers at y 0x18b (each: provider := n, arena list, 0xc026), id 17 setup |
| click dispatch | `0x10008770`: `cmp esi, 0x12; ja 0x100092e6; jmp [0x1000933c + esi*4]` at `0x1000887b` |
| arena list | `0x10031320`, by game type; records title[32] + file[20] in a growable list; title = the WRLD title through exe callback +0x58 |
| what the entry passes to the exe | nothing has to cross: shell and exe are one process with one `Strlkup.dll`, so the proxy's own flag `g_nmp_mode` is read by both halves. (A setup-block bit would also be safe - 0x4000 is never tested - but is not needed.) |

**Insertion without moving stock buttons:**
1. A new widget record with **id 0x13** (proxy memory), built with `0x1000e410` in the melee group, in the free slot
   beside / under id 0xc (x 0x1d7, y 0x170 [inferred free]); shown and hidden with the group (`0x10009610` / the
   redraw `0x10009c10` get one extra call through a wrapper).
2. Click: only the `ja 0x100092e6` target at `0x1000887b` changes, to a stub: id 0x13 -> `g_nmp_mode = 1`, then the
   id-9 path (HOST / JOIN, providers, the 0xc026 form) runs unchanged; any other id -> the stock default.
3. While `g_nmp_mode = 1`: sessionType word `[0x10046cb0]` = ours, the 'JO' version = "6.04+", the arena list also reads
   our folder. Back to the main menu (0xc00e), session end or `dpClose` -> mode 0, all three restored.
4. Label: the shell has no text buttons; either draw the label with the shell's text call (as I76_ARENA_FIT draws titles
   on Gold) over an empty plate, or add one sprite to the shell's image set. The first needs no data file.

## 3. Design

### 3.1 What carries over, what needs ANet 2 work

| feature (Gold source) | netcode-independent? | Nitro work |
|---|---|---|
| injected AI pool records (`aim_odef`) | yes | site `0x4bd4bf` (ODEF handler `0x4bd4b0` -> `0x4b3630`, Gold 0x4b45bf); only combat `.cbt` arenas in our entry |
| parked / teleport pool (`mpfill.c`) | yes | **per-team spawn tables** in Nitro ("no spawn points for team %d"): trace their layout (Gold: one table 0x53fd88, count 0x540d98) |
| aimelee host tick, skill, cap (`aimelee.c` 1) | yes | `0x4079a2`; fsm_SetSkill / SetMaxAttackers / SetBehaviour matched "same" (`0x418400`, `0x418710`, `0x415490`) |
| teams | mostly | team = slot +0x48 and flags bits 16..18; team game from 0x53f228 & 0x2040 (not a bool) |
| difficulty skill (`difficulty.c`) | yes | re-address only |
| respawn (humans: `0x44caf0` = Gold 0x451570; AI: spawner `0x44c930` = Gold 0x4513c0) | yes | spawner "changed" (per-team spawn) |
| score rows (AI rows in the player table) | yes, but layout | **0x50 stride; fill +0x44 = 1.0f and +0x48 = team**; ids 0x7E00+n never reach ANet (rows are local, as on Gold) |
| 'AT' AI state sync, fire mask, damage block | needs the ANet 2 hook | packet unchanged (`net_PackVehicleState 0x463660` = Gold 0x4644d0 "same", 0x60-byte record) |
| 'AK' kill credit | ANet 2 hook | unchanged |
| 'AM' reload / next scene (co-op chain) | ANet 2 hook + WinMain sites | `0x433165`, `0x433717`; join CRC slot `0x52676c` |
| 'AC' / 'AO' (CB lines, objectives) | ANet 2 hook | CB voices: Nitro does not open I76.ZFS (NITRO-BASE): the original radio voices are missing until the nitro-base lane adds a voice path |
| slot settle (team read, 1.5 s / 3 s holds) | ANet 2 player data | same keys (1 = team pick) |
| host migration reconcile | ANet 2 | Nitro elects like Gold; add an **'AH' hello** from the new host so joiners confirm the pool / rows before the new host acts |

### 3.2 Packet design on ANet 2: piggyback, not a registered type

There is nothing to register: ANet 2 hands every app packet to the pump, the pump dispatches by its 2-letter tag and
drops the rest (section 1.2). So **keep the Gold scheme**: our tags 'AT' 'AK' 'AM' 'AC' 'AO' 'AV' plus one new 'AH'
(hello: protocol version, flags, pool CRC; sent by the host on each join and after a migration), read in the dpReceive
hook after the real call. Rules: sent **only while `g_nmp_mode = 1`** (and only to our species' sessions, which stock
games cannot join); payload <= 2 records (208 B) until the anet2 dump shows the real limit; 16 spare bytes after every
send buffer (ANet 1 wrote 4 past the payload; ANet 2 unchecked); 'AK' / 'AM' keep 3 copies + sequence numbers (ANet 2
probably has a reliable flag, unread). Even if one leaked, a stock Nitro pump drops it (decomp above) - but none may.

### 3.3 The non-destructive guarantee

A player who never opens our entry plays stock Nitro; a stock Nitro player can join a stock session hosted by a
patched game; a stock player never sees or joins one of ours. Concretely:

1. **Mode 0 at every boot**; mode 1 only from the button; back to 0 on the main menu, session end, `dpClose`.
2. **Forced off in mode 0** (whatever the environment says): `I76_COOP_AI`, `I76_COOP_CHAIN`, `I76_COOP_DAMAGE`,
   `I76_COOP_SCALE` (+ `_MAX`, `_TEST`), `I76_COOP_CB`, `I76_COOP_ADOPT`, `I76_COOP_HOSTMODEL`, `I76_AIMELEE` and every
   `I76_AIMELEE_*` (`_FILL`, `_FILL_TEAM`, `_RESPAWN`, `_RESPAWN_AI`, `_SCORE_ROWS`, `_TEAMS`, `_WAVE`, `_ARENAS`,
   `_BOX_LINES`, `_SKILL`, `_CAP`, all `_TEST*`), `I76_DIFFICULTY_AI` in network games, `I76_MPF_LOG` (harmless, but
   off). `I76_MP_MENU` / `I76_ARENA_FIT` are Gold-shell patches and never attach to nitshell. Lab-only `I76_LAB_*` never
   ship.
3. **Not touched in mode 0:** the dpReceive hook passes through (returns the real result, reads nothing), no extra
   sends, no AI injection, no score rows, sessionType 604, version "6.04", the stock arena list.
4. **Files:** nothing in `addon\` that the stock list reads (`addon\*.cbt|*.rac|*.cf2..4`) and no `.vdf/.wdf/.gdf/.cdf`
   override; our missions in `addon\nmp\` (a mission name "nmp\coop01.cbt" fits the 20-byte record; that the exe's VFS and
   the joiner's `addon\%s` CRC path accept a sub-folder is **to be checked**, fallback: the proxy maps the name).
5. **Local-only proxy features stay on** in stock sessions (far clip, terrain, music, cursor, telemetry): they change
   nothing another machine sees. **Own-car physics changes** (whole-sim tick) are the open question: they change only
   the patched player's car, but a community game should get the same car as everyone else; recommendation: in network
   games outside our entry, the tick runs at the setting measured equal to retail (gold-standard rule), never a
   handling change.
6. **Gate (before anything ships):** two lab copies, IPX: (a) patched host, stock Nitro joiner, every game type
   (combat, race, CTF 2) - join, play, leave, migrate; (b) stock host, patched joiner; (c) our entry hosting while a
   stock copy lists: not listed; (d) the same over the bz911 lobby with our species (risk R3); n 3 per cell.

### 3.4 List entries under the new entry (superseded by section 0.6)

| group | count | source | how |
|---|---|---|---|
| Nitro combat arenas with AI fill | every `*.cbt` the stock list shows (data track: 24 `.cbt` in the corpus, incl. N51-N65) | stock files | memory injection of 7 parked AI at load (Gold's AI-MELEE-RESPAWN phase 2), fill = NO. DRIVERS - humans |
| the 15 original arenas | 15 | **already in Nitro as N51-N65** (same terrain) | as above; nothing to add. (The owner's `nitro-plus-original` copy also has M01-M15 as `.CBT`: in our entry they would duplicate N51-N65; leave them out) |
| co-op scenes 1-17 | 17 | Gold T01-T17 (`coop-install.py` output, owner's Gold install) | `addon\nmp\coopNN.cbt`, combat type, title "Co-op Scene N"; voices missing until a voice path exists |
| scenarios S01-S07 | 7 | Gold S01-S07 (`autoNN`) | `addon\nmp\autoNN.cbt` |
| races / CTF with AI | - | - | out of scope (AI would need race / flag logic) |

The brief's "Nitro's 36 arenas" did not match a count here (the corpus has 24 `.cbt`, 17 `.cf2-4`, 13 `.rac`); the rule
"every combat arena of the stock list" covers whatever the install holds.

## 4. Names for the entry (owner picked ARENA+, section 0)

Each name with the one-line description the shell would show beside it (on the button's hover / the form title).

| # | name | description line |
|---|---|---|
| 1 | **AI DROP-IN** | Melee with computer drivers in every empty seat; friends drop in or out any time. |
| 2 | **CO-OP / AI MELEE** | Team up against computer cars: every arena, the '76 scenes and scenarios. |
| 3 | **ARENA+** | Every arena plus the original '76 missions, with AI filling the open slots. |
| 4 | **CONVOY** | Roll out together: co-op scenes and AI-filled arenas, join whenever you like. |
| 5 | **NET AUTO MELEE** | Auto Melee over the network: AI drivers fight beside and against your friends. |

Width: the plate beside "auto melee" holds about 106 px (the id 0xc button); every name fits in the shell's 12-px hand
font (CO-OP / AI MELEE is the longest, about 100 px [estimated from Gold's font measurement in mpmenu.c]).

## 5. Estimate and order (lane-days, one lane; revised in section 0.6)

| # | piece | days | risk | why |
|---|---|---|---|---|
| 0 | prerequisite: the nitro-port lane's foundations (exe detection, site table, logging, cursor / shell map) | - | - | not counted here |
| 1 | anet2 dump from a lab boot + read species filtering, reliable flag, size limit | 0.5 | low | one boot, one dump, one export |
| 2 | shell entry: button id 0x13, click stub, text label, mode flag, species / version / list swaps, reset paths | 2.5 | **medium** | widget internals (show / hide with the group) only read statically |
| 3 | ANet 2 layer: dpReceive hook, sends, role / host / group, 'AT' sync + fire + damage block + score skip, re-addressed globals (0x50 rows, +0x484 / +0x458) | 2 | low-medium | same pump shape, packets unchanged |
| 4 | AI melee on Nitro: host tick, kill credit, skill, respawn, score rows (0x50 layout), pool injection at 0x4bd4bf, per-team spawn tables, teams on the flags word | 4 | **medium** | per-team spawns and the new row fields are new ground |
| 5 | co-op scenes + scenarios: chain sites, 'AM' / 'AC' / 'AO', `addon\nmp\` list + VFS sub-folder check, files from Gold | 3 | **high** | Gold missions on Nitro measured for P01 only in our exe, never in nitro.exe; radio voices missing |
| 6 | host migration: 'AH' hello, reconcile pool / rows on the new host, co-op restart | 1 | medium | as on Gold, but new packet |
| 7 | non-destructive gate (3.3 item 6), incl. the lobby with our species | 1.5 | medium (R3) | needs two lab copies and the lobby |
| 8 | cross-machine pass (PC + a Mac) and pack | 1 | medium | Wine + Nitro never run here |
| | **total** | **15.5** | | |

Order: 1 -> 2 -> 3 -> 7(a-c) early (prove the entry is invisible to stock before any AI work) -> 4 -> 6 -> 5 -> 7(d) -> 8.

**Risks.** R1 anet2 internals unread (piece 1 retires it). R2 the shell's button / group code is read, not run. R3 a
lobby server may refuse or hide an unknown species: our entry would then be IPX / LAN only until a species the lobby
lists is agreed with the community (the bz911 operators); stock play is unaffected either way. R4 Gold co-op missions in
nitro.exe (scripts, FMV hooks, missing voices) - the nitro-base lane's owner check answers part of it. R5 the port lane's
two mapping slips in section 1.3 must be fixed before any team / scoreboard code runs on Nitro.

## 6. What was not done

- No game was started (no stock Nitro menu or IPX session observed): the button meanings in section 2 are inferred from
  the layout and the handlers. First lab boot should confirm them (screenshot of the main menu with the melee group open).
- anet2.dll internals (section 1.7).
- Nitro's per-team spawn table layout, the VFS sub-folder question (3.3 item 4).
