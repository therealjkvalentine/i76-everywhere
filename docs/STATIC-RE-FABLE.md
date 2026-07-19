# Static RE findings (fable-static-re branch, 2026-07-18)

Complementary to the live-scanning main thread: these come from DISASSEMBLING
i76.exe on disk (tools/exe-xref.py + exe-disasm.py), not from value scanning.
They explain WHY the live scan for ammo kept failing and answer the music
question by reading the code instead of inferring.

## 1. Ammo lives in per-weapon SUB-OBJECTS, not the flat car struct

The real `ammoLesser` C function (0x40be60) walks the vehicle's weapon list:
```
mov  eax, [ebx + 0xa718]      ; weapon COUNT
lea  edi, [ebx + 0xa71c]      ; weapon-pointer ARRAY (dword ptrs, stride 4)
mov  ecx, [edi]               ; ecx = pointer to weapon OBJECT i
... iterate esi=0..count ...
```
So `car+0xa718` = weapon count, `car+0xa71c` = an array of POINTERS to
heap-allocated weapon objects. **The ammo count is a field INSIDE each pointed-to
weapon object** — it is NOT contiguous in the car struct.

**This is exactly why the main thread's value-scan for ammo failed at stable
addresses**: the HUD number (3721) is read through car -> ptr[i] -> weapon.ammo,
and the weapon objects are separate allocations. A flat scan can still find the
weapon-object field, but the robust path is a POINTER walk (car base ->
+0xa71c -> [i] -> +ammo_off) or a "find what accesses this address" watchpoint.
The weapon-object ammo-field offset is the one value left to pin (main thread /
the struct agent's Open76 cross-check will give it).

The engine is heavily SCRIPT-DRIVEN: `ammoLesser`, `isCBEmpty`, `playScene`,
`setUserRadar`, `SET_SPEED_*` are mission-script VM opcodes (matched in strcmp
tables, dispatched by bytecode). Many "functions" are opcode names, not C
symbols — a trap when xref-ing by string.

## 2. MUSIC state — answers "know exactly when music plays" (no inferring)

Music is MCI (`mciSendCommandA`, 2 call sites: 0x423f8d play/open, 0x424aea).
The stop path (0x423f8d) does:
```
call mciSendCommandA          ; MCI_CLOSE (0x804)
mov  [0x4ed890], 0xffffffff   ; MCI device handle = none
mov  [0x524674], 0            ; <-- MUSIC-ACTIVE FLAG cleared
```
and the play/update path (0x423fb0) gates on it:
```
mov  eax, [0x524674]          ; if zero, skip -> no music playing
test eax, eax
je   ...
mov  ecx, [0x4ed890]          ; MCI device handle
... mciSendCommandA MCI_STATUS/MCI_PLAY (0x814) ...
```
**Read `0x524674` live: nonzero = music is playing, 0 = stopped.** That is the
exact "is music supposed to be playing" signal, straight from the engine — no
more inferring from the launcher. Companion globals: `0x4ed890` = MCI device
handle (0xffffffff when closed), `0x4ed894` = aux/volume device id.

### Music VOLUME can be set from memory (instead of re-encoding the mp3s)
`auxSetVolume` (0x424ba2) is fed a 0-0xffff level computed from the in-game
"Music Level" setting, sent to device `[0x4ed894]`. So the earlier "turn music
down 10%" could be done live by writing the music-level global + re-invoking the
volume set, rather than re-encoding every track. (The exact level global is the
Audio-Control menu's backing var — a follow-up trace; the mechanism is proven.)

## 3. FFB param block (rumble-mirror groundwork, Win/Deck)
The FFB init (0x445a60) zeroes the 0x16c-byte effect param block at 0x4f2328
and sets flags (0x52bbd4=1 init-done, 0x52bbd0=0 present). The per-frame force
fill (physics -> magnitude) is a separate tick writer (0x4460e2/0x446120 region,
inside the I7FF_SIM_Effect send path) — the value to mirror into XInput rumble
on Windows/Deck. Not filled on Mac (no DI-FFB device), consistent with our
synthetic-rumble decision.

## 4. Methodology to crack the ammo encoding (see docs/RE-METHODOLOGY.md)
The winning approach, ranked (RE-methodology research):
1. **Unknown-value scan driven by firing** — no encoding assumptions; catches an
   up-counter / down-counter / fixed-point alike. Scriptable in AHK RPM today
   (snapshot all -> fire -> keep addresses that changed -> repeat).
2. **"Find what writes this address" watchpoint** — reads the encoding straight
   off the disassembly AND yields the base-register+offset for the pointer path.
   Needs a debugger — and the key enabler below.
3. Multi-width exact scans: test 3721 as int16 and float32, and 3721*65536 as
   int32 (1997 titles love int16 and 16.16 fixed-point).
4. Struct dissection once a base pointer is known.

### THE practical unlock for this setup
Native Cheat-Engine-to-Wine attach is flaky, BUT running **cheatengine.exe (or
x32dbg) INSIDE the same wineprefix** as the game (our Sikarugir wrapper) works —
both are then Windows processes in one prefix, so attach + watchpoints + pointer
scanner all function. That gives us technique #2 (the conclusive one), which
pure AHK RPM cannot do. Install CE into drive_c of the prefix and launch it via
wine, same as our AHK tools.

## 5. CONCLUSION — the ammo/armor encoding, cracked (disasm + Open76 source)

Combining this branch's disassembly with the Open76/renscreations reimplementation
source (docs/MW2-I76-STRUCTS.md) resolves the main thread's stuck scan:

**Ammo = plain signed int32, a CURRENT-ROUNDS COUNTDOWN**, one per weapon
instance (`--weapon.Ammo` per shot in Open76's WeaponsController; GDF `AmmoCount`
int32 at offset 94). NOT fixed-point, NOT a fired-up-counter. It lives inside the
per-weapon heap sub-object that this branch located via `car+0xa71c[i]`
(disasm §1). Why the main thread's scan missed it: (a) the far-apart dumps
diffed a Δ18 across too much noise; (b) the weapon sub-object is a separate
heap allocation. **Fix: fire exactly ONE shot and diff for a −1 int delta**
between two CLOSE snapshots (the countdown is unambiguous), or pointer-walk
`car -> +0xa71c -> [weapon_idx] -> +ammo_off`.

**Armor = 8 contiguous per-facet INTEGERS (4 armor + 4 chassis), in TENTHS.**
This matches BOTH the save editor's "game shows tenths" note AND Open76's
integer-subtraction damage model: stored = HUD ×10 (front 91.0 -> 910). The
earlier live scan for 910/570/700 found nothing not because the encoding is
wrong but because of dump timing / struct-not-yet-populated. **Fix: take a hit,
then tight-loop scan for 910 → new value; the 8 facets are contiguous so one
hit locates the whole block.**

**Sim runs at a fixed ~20 fps tick** (Peelar + Roanish `world_tick`): combat
ints mutate on tick boundaries — step by ticks when correlating a shot to a
delta, don't sample mid-frame.

**The conclusive tool (from RE-METHODOLOGY.md):** install `cheatengine.exe`
into the prefix's drive_c and launch it via wine (same as our AHK tools) so it's
a Windows process in the same prefix → "find what writes this address" on a
found ammo/armor byte reads the offset + base register straight off the
disassembly, giving the permanent pointer path (`[[static]+o1]+o2`) that
survives relaunch. Pure AHK RPM can't set watchpoints; CE-in-prefix can.

## 6. KEYSTONE — the static player-car pointer chain (survives relaunch)

The input-apply function (0x44f1c6, reads throttle 0x5367cc / steer 0x5367d4 and
writes them into the player car) reaches the player car like this:
```
mov eax, [0x54a264]     ; 0x457530(): world/context root  (STATIC .data global)
mov esi, eax
mov eax, [esi]          ; -> sub-object A = [[0x54a264]]
mov edi, [eax + 0x70]   ; player_car = [[[0x54a264]] + 0x70]
```
**`player_car = [[[0x54a264]] + 0x70]`** — a 3-hop pointer chain rooted at the
STATIC global **0x54a264** (loads at a fixed address, no ASLR). This is the
permanent root the whole vehicle map hangs off; unlike raw heap addresses it
survives every relaunch. `0x457530` is the world-context accessor (`return
[0x54a264]`), called all over (camera init 0x405ac1, input apply, etc.).

### Player-car field offsets confirmed so far (from disasm)
| offset | field | source |
|---|---|---|
| car + 0xe0  | steer input applied (float) | 0x44f2a2 |
| car + 0xe4  | throttle input applied (float) | 0x44f290 |
| car + 0x3c  | component COUNT (int) | component-finder 0x4b6900 |
| car + 0x40  | component ARRAY (stride 0x20, type-tag @+0) — armor/engine/tire/brake, int TENTHS | 0x4b6900 |
| car + 0xa718 | weapon COUNT (int) | ammoLesser 0x40be a5 |
| car + 0xa71c | weapon-pointer ARRAY (stride 4) -> weapon obj -> +ammo (int32 countdown) | ammoLesser |

### The permanent reader (for the trainer / any tool)
```
world   = read_u32(0x54a264)
subobj  = read_u32(world)
car     = read_u32(subobj + 0x70)
throttle_out = read_f32(car + 0xe4)      # applied control
wcount  = read_u32(car + 0xa718)
warray  = read_u32(car + 0xa71c)         # then warray[i] -> weapon -> +ammo
ccount  = read_u32(car + 0x3c)
carray  = car + 0x40                     # component[i] = carray + i*0x20
```
This turns every heap-relocating value (ammo, armor, speed, gear) into a stable
`base+offset` read. The remaining unknowns (exact ammo offset in the weapon obj,
health offset in the 0x20 component record) are a few bytes to pin with the
component/weapon record dumped via this chain — or a CE watchpoint.
