# Force feedback deep dive — i76.exe (GOG Gold) + i7_sfrce.dll (2026-07-19)

Static RE, capstone disasm via tools/exe-disasm.py / exe-xref.py. Every claim
below is backed by quoted instructions. Confidence tags: DIRECT (disasm shown),
INFERRED (multiple corroborating sites), GUESS (marked).

The headline: **the entire FFB subsystem is a plugin architecture.** The exe
computes a 364-byte "force state" block every sim tick and hands it to an
external DLL (`i7_SFRCE.DLL`, present in the GOG install, 82944 bytes) which
maps it to DirectInput effects. The DLL is the ONLY thing that touches
DirectInput — i76.exe itself has **no DINPUT.DLL import at all**. Faking that
DLL gives us the game's full physics-driven force stream with three tiny
stdcall functions.

---

## 1. MODULE LOADING (Q1) — DIRECT

### Strings (.data of i76.exe, hexdump)

```
004f2494  "Unable to get SWForce object!"
004f24b4  "Error loading i7_SFRCE.dll"
004f24d0  "I7FF_SIM_Effect"
004f24e0  "I7FF_ExitSystem"
004f24f0  "I7FF_InitSystem"
004f2500  "I7_SFRCE.DLL"                      <- the module name template
004f2510  "I7FF_SIM_Effect() failed. Return code: %lX\n"
004f253c  "Unable to Exit from SWForce object!"
```

The module is **`i7_SFRCE.DLL` in the game directory** (it IS there in the GOG
install, alongside a `force/` directory of 14 `.FRC` effect files:
CANNON1-4, ENGSTART, EXPLOSN, MISSIL45, MISSILE2, MISSILE5, TIREBLWL,
TIREBLWR, WPNCYCLE, WPNLINK, WPNUNLNK). No path, no registry lookup — plain
`GetModuleHandleA`/`LoadLibraryA` on the bare name (LoadLibrary default search
= exe directory first).

### Loader fn 0x446020 (whole function) — DIRECT

```
0x00446020  sub    esp, 0x10
0x00446023  mov    ecx, dword ptr [0x4f2504]      ; 'FRCE.DLL'   <-- dword 2 of "I7_SFRCE.DLL"
0x00446029  mov    eax, dword ptr [0x4f2500]      ; 'I7_SFRCE.DLL'
0x0044602e  mov    edx, dword ptr [0x4f2508]      ; '.DLL'
0x00446034  mov    dword ptr [esp + 4], ecx        ; builds the 13-byte name on the stack
0x00446039  mov    dword ptr [esp + 4], eax        ;   (dword/dword/dword/byte copy)
0x0044603d  mov    al, byte ptr [0x4f250c]
0x00446042  lea    ecx, [esp + 4]
0x00446047  push   ecx
0x00446050  call   dword ptr [0x4bc0ec]            ; KERNEL32!GetModuleHandleA
0x00446056  mov    esi, eax
0x00446058  test   esi, esi
0x0044605a  jne    0x446070
0x0044605c  lea    edx, [esp + 8]
0x00446060  push   edx
0x00446061  call   dword ptr [0x4bc0b0]            ; KERNEL32!LoadLibraryA
0x00446067  mov    esi, eax
0x00446069  cmp    esi, 0x20                       ; HMODULE must be > 0x20
0x0044606c  jae    0x446073
0x0044606e  jmp    0x4460ba                        ; -> fail
0x00446070  cmp    esi, 0x20
0x00446073  jbe    0x4460ba
0x00446075  mov    edi, dword ptr [0x4bc0a0]       ; KERNEL32!GetProcAddress
0x0044607b  push   0x4f24f0                        ; "I7FF_InitSystem"
0x00446080  push   esi
0x00446081  call   edi
0x00446083  push   0x4f24e0                        ; "I7FF_ExitSystem"
0x00446088  push   esi
0x00446089  mov    dword ptr [0x52bbdc], eax       ; 0x52bbdc = InitSystem ptr
0x0044608e  call   edi
0x00446090  push   0x4f24d0                        ; "I7FF_SIM_Effect"
0x00446095  push   esi
0x00446096  mov    dword ptr [0x52bbe0], eax       ; 0x52bbe0 = ExitSystem ptr
0x0044609b  call   edi
0x0044609d  mov    ecx, dword ptr [0x52bbdc]
0x004460a3  mov    dword ptr [0x52bbe4], eax       ; 0x52bbe4 = SIM_Effect ptr
0x004460a8  test   ecx, ecx                        ; all three must be non-NULL
...
0x004460c0  push   0x4f24b4                        ; "Error loading i7_SFRCE.dll"
0x004460c5  call   dword ptr [0x4bc0f4]            ; KERNEL32!OutputDebugStringA (errors go to ODS only)
...
0x004460d3  mov    eax, dword ptr [0x52bbdc]       ; on success: call I7FF_InitSystem
0x004460d8  mov    esi, 0x8004050f                 ; default error if ptr NULL
0x004460e1  push   0x4f2328                        ; &param block
0x004460e6  mov    dword ptr [0x4f2328], 0x16c     ; block[0] = sizeof = 364
0x004460f0  call   eax                             ; I7FF_InitSystem(&block)  — NO add esp: stdcall
0x004460f4  test   esi, esi
0x004460f6  jge    0x446103                        ; HRESULT >= 0 = success
0x004460f8  push   0x4f2494                        ; "Unable to get SWForce object!"
...
0x00446106  test   esi, esi
0x00446108  setge  al                              ; returns bool success
```

**Corrections to prior docs (GHIDRA-MEMORY-MAP PART 4/5):**
- The fn-ptr/name mapping was reversed: `0x52bbdc` = **InitSystem**,
  `0x52bbe0` = **ExitSystem**, `0x52bbe4` = **SIM_Effect** (names at
  0x4f24f0/0x4f24e0/0x4f24d0 respectively).
- `[0x4bc110]` is **KERNEL32!HeapCreate**, not an FFB-object factory.
  `0x52bbcc` is therefore a **private Win32 heap handle** (created
  `HeapCreate(0,0,0)` at 0x445af3, used by HeapAlloc/HeapFree for the impact
  event nodes, destroyed via `[0x4bc10c]`=HeapDestroy at shutdown 0x445b24).
  There is no "SWForce object pointer" in the exe; "SWForce object" in the
  error strings refers to the DLL-side device.
- The "FRC" xref at 0x446025 is a **red herring**: the operand 0x4f2504 is
  simply the second dword of the "I7_SFRCE.DLL" string ("FRCE.DLL"). There is
  **no FRC registry key check anywhere in the Gold FFB path** (see §2).

### DirectInput lives only in the DLL

i76.exe import table (pefile): `Strlkup.dll, KERNEL32, USER32, GDI32, MSVCRT,
anetdll.dll, ADVAPI32, WINMM, DSOUND, smackw32, DDRAW, IMM32, ole32` —
**no DINPUT.DLL**. i7_sfrce.dll imports `DINPUT.dll!DirectInputCreateA` (its
only DirectInput import) plus KERNEL32/USER32 CRT noise.

i7_sfrce.dll exports (pefile): ord 1 `I7FF_ExitSystem` @0x10001d00,
ord 2 `I7FF_InitSystem` @0x10001b30, ord 3 `I7FF_SIM_Effect` @0x100036d0.

---

## 2. ACTIVATION GATING (Q2) — DIRECT

### The init chain, in order

1. **0x402f93** — `call 0x445a60` from the one-time game startup sequence.
   **Unconditional**: no registry read, no config flag, no device pre-check
   guards it (disasm of 0x402f30-0x402f98 shows it sandwiched between generic
   init calls). The exe's only Activision registry access
   (0x4b2226: `RegOpenKeyExA(HKLM, "SOFTWARE\Activision")` +
   `"Interstate '76 Gold Edition"` / value `"Minimum"`) is the
   minimum-install/CD check, unrelated to FFB. **The old
   "Interstate'76FRC registry key enables FFB" lore does not apply to this
   binary.**

2. **ffb_init 0x445a60** (DIRECT, full fn):
   ```
   0x00445a68  mov dword ptr [0x52bbd4], 1        ; init-done flag
   0x00445a72  mov dword ptr [0x4f2328], 0x16c    ; block size
   0x00445a7f  mov dword ptr [0x52bbd0], esi(=0)  ; FFB-present = 0
   0x00445a85  mov dword ptr [0x4f2490], eax      ; block+0x168 = [0x5dcf7c] (HINSTANCE, see §3)
   0x00445a8a  mov dword ptr [0x4f248c], 0x5dcf3c ; block+0x164 = &struct (unused by DLL)
   ...zeroes block +0x150..+0x15c (event lists), +0x148/+0x14c, +4, +8, +0x160
   0x00445aca  call 0x446020                       ; load module + InitSystem (see §1)
   0x00445acf  test eax, eax
   0x00445ad1  je   0x445b08                       ; failed -> stay off FOREVER (no retry)
   0x00445add  mov dword ptr [0x52bbd0], 1        ; *** FFB ACTIVE ***
   0x00445ae7  call dword ptr [0x4bc234]           ; MSVCRT!sprintf(localbuf, "Forcefeed") (vestigial)
   0x00445af3  call dword ptr [0x4bc110]           ; HeapCreate(0,0,0)
   0x00445af9  mov dword ptr [0x52bbcc], eax      ; private event heap
   0x00445afe  mov dword ptr [0x4f2314], -1       ; engine-id sentinel
   ```

3. **Inside I7FF_InitSystem (DLL 0x10001b30)** — all must hold:
   - `block[0] == 0x16c` else 0x80070057 ("Invalid Structure Size").
   - not already initialized (`[0x100138c8]==0`) else 0x8004050e.
   - **device open 0x10003850** succeeds, which requires (DIRECT, disasm at
     0x10003850-0x100039f5):
     - `DirectInputCreateA(hinst = block+0x168, version 0x500, &lpdi, 0)`
       (`push ebp(0); push edi; push 0x500; push eax; call [thunk]`)
     - `IDirectInput::EnumDevices(4 /*DIDEVTYPE_JOYSTICK*/, cb=0x10003a10,
       &out, 0x100 /*DIEDFL_FORCEFEEDBACK*/)` — the callback (0x10003a10)
       accepts a device only if `byte(DIDEVICEINSTANCE+0x24) == 4`
       (dwDevType primary byte = joystick), i.e. **the enumeration only sees
       force-feedback joysticks; one must exist**.
     - `CreateDevice`, `QueryInterface(IID @0x1000d2e0 = IDirectInputDevice2A)`,
       `SetDataFormat(@0x10005300 = c_dfDIJoystick)`,
       `SetCooperativeLevel(hwnd=[0x100138c4], flags=9 =
       DISCL_EXCLUSIVE|DISCL_BACKGROUND)`,
       `SetProperty(DIPROP_AUTOCENTER(9), {sz 0x14,0x10,0,0, data 0})` = OFF,
       `Acquire` — each checked `jl fail`.
     - failure returns 0x8004050e; debug string "I7FF_InitSystem Failed to
       open FF Joystick.  Try again next time."
   - The `.frc` effect-template loads (fns 0x10001310/0x100013c0/0x10001490/
     0x100014e0, feature flags 0x10013948/4c/50/54) are attempted here but
     **their failure does NOT fail InitSystem** — only logged.

4. Result propagates back: `0x446020` returns `setge al` of the HRESULT →
   `0x52bbd0 = 1` only if module + all 3 exports + InitSystem OK.

**Net activation condition on Windows/Deck:** i7_SFRCE.DLL loadable beside the
exe AND a DirectInput (DX5 interface) device enumerable under
DIEDFL_FORCEFEEDBACK at process start. Nothing else. One shot at boot; if it
fails, FFB is off until relaunch (exe never re-calls init — SIM_Effect's
internal lazy re-init at 0x100036f3 is unreachable because the exe gates every
call on 0x52bbd0).

**What a Mac/any shim must fake:** replace i7_SFRCE.DLL with our own —
then there is NO DirectInput requirement at all; the three exports just have
to return HRESULT >= 0. (Setting 0x52bbd0=1 externally without the DLL is NOT
enough: 0x52bbe4 would be NULL and the send fn falls back to error
0x8004050f — see 0x446110 below — plus the tick fn would run fine but nothing
would consume the block.)

### Runtime on/off (the master switch, not activation)

`0x52bbd8` + block+8 (0x4f2330) is a **forces-on/off toggle**, set 1 by
0x445b40/0x445b80 and 0 by 0x445b60, each followed by an immediate
`jmp 0x446110` (send). Callers (rel32 scan): 0x4038db/0x4038e0, 0x404587/8c,
0x404aa7/0x404afb, 0x45e37f/0x45e76a, 0x495324/0x495688, 0x499fc3/0x49a094,
0x49a878, 0x49aad9, 0x49ce64/0x49cfb4, 0x49d06c/0x49d0ba, 0x49d169/0x49d1a5 —
i.e. sprinkled through sim-enter/leave, pause, video, shell transitions.
DLL side: when block+8 goes 0 while active it issues
`SendForceFeedbackCommand(DISFFC_STOPALL)` and releases every live effect
(0x1000373d-0x100037fd).

---

## 3. THE FORCE STREAM (Q3)

### Who writes, who sends

- **ffb_tick = 0x445ba0**, called from **0x46396c** (main sim frame loop).
  Signature: one stack arg, a context struct; `[arg+0x70]` = player vehicle
  entity (`esi` below), `[arg+0x18]` = orientation matrix, `[arg+0x2c..]`
  scratch. Early-outs if `0x52bbd0==0`, and skips vehicle sections if
  `[arg+0x70]==0` or `[[veh+0x3c4]+0x70]==0` (engine sub-object missing).
  Ends with `call 0x446110` (send) then prunes the four event lists.
- **ffb_send = 0x446110**: `mov eax,[0x52bbe4]; push 0x4f2328;
  mov [0x4f2328],0x16c; call eax` — **I7FF_SIM_Effect(&block), stdcall**, no
  caller stack cleanup. On HRESULT<0: wsprintfA("I7FF_SIM_Effect() failed.
  Return code: %lX\n") → OutputDebugStringA.
- **Event/impact writers**: one damage-application fn (body ~0x4a7f24-0x4a81b7)
  appends nodes to the four lists; three one-shot writers 0x4a5e16/0x4a602c/
  0x4a634d set the weapon-UI flags; a hardpoint-state cluster 0x4a66f4-0x4a6e06
  maintains the six per-hardpoint records.

### The 364-byte block — full field map (base 0x4f2328)

DLL-side reads verified in the six SIM_Effect sub-handlers:
`0x100032f0` impacts, `0x10002090` weapons, `0x10001d90` engine,
`0x100027d0` vehicle X/Y forces, `0x100029e0` tires/skid, `0x10002f80` terrain.

| off | VA | type | exe writes (site) | meaning / DLL use |
|---|---|---|---|---|
| +0x000 | 0x4f2328 | u32 | `0x16c` (init, every send) | struct size; DLL rejects otherwise |
| +0x004 | 0x4f232c | u32 | 0 at init | reset flag; DLL clears if set (vestigial) |
| +0x008 | 0x4f2330 | u32 | 0/1 by 0x445b40/60/80 | **master forces on/off**; 0 → DISFFC_STOPALL + release all |
| +0x00c | 0x4f2334 | int | 0x445c86: `(int)fn_0x46a790(engine)` | engine pitch value; DLL vibration **freq = 8 − round(v*k1*k2)** |
| +0x010 | 0x4f2338 | u32 | 0x445c6d: `[veh+0x454] & 1` | **engine running** — gates ENGINE VIBRATION periodic effect |
| +0x014 | 0x4f233c | u32 | 0x445c18: `([veh+0x454]>>3) & 1` | **engine starting** — one-shot ENGSTART.FRC, DLL clears |
| +0x018 | 0x4f2340 | u32 | 0x445c97: `[engine+8] != [0x4f2314]` | engine object changed (new car/engine) — effect re-parameterize |
| +0x01c | 0x4f2344 | u32 | 0x445c51: `[veh+0x454]&0x800` if mount type==2 | adds +2500 to lateral force in 0x100027d0 (GUESS: heavy special mount) |
| +0x020 | 0x4f2348 | u32 | 0x445c39: 1 if mount type==3 | rescales small forces in 0x100027d0 (mount scan: 3 slots at [veh+0x3ec..0x3f4], typed by fn 0x467790) |
| +0x024 | 0x4f234c | u32 | 0x4a5e16: =1 | **weapon CYCLING** one-shot → WPNCYCLE.FRC ("CYCLING: Triggered"), DLL clears |
| +0x028 | 0x4f2350 | u32 | 0x4a634d: =1 | **weapon LINK** one-shot → WPNLINK.FRC |
| +0x02c | 0x4f2354 | u32 | 0x4a602c: =1 | **weapon UNLINK** one-shot → WPNUNLNK.FRC |
| +0x030..+0xd3 | 0x4f2358.. | 6 × 0x1c | cluster 0x4a66f4-0x4a6e06 | **hardpoint records** (see below) |
| +0x0d8..+0xe0 | 0x4f2400-08 | 3×i32 | zeroed 0x445d81-97 | DLL scratch: computed DI force x/y ints |
| +0x0e4..+0xec | 0x4f240c-14 | 3×u32 | 0x445da9-c9: `[veh+0xbc]` ×3 | **not read by this DLL** (vestigial) |
| +0x0f0..+0xf8 | 0x4f2418-20 | 3×f32 | 0x445dd2-df: out of `0x43a320(&out, veh+0xd4, arg+0x18)` | **body-frame force/G vector**; +0xf0→ForceX (steering kick, ±0x320 bias, "Vehicle Force: ForceX"), +0xf4/+0xf8→ForceY (mag=2*sqrt(x²+y²) signed, "ForceY") |
| +0x0fc | 0x4f2424 | u32 | 0x445cdb-ec: `[veh+0xe4] > 0.15` | steering right (steer input beyond dead zone) |
| +0x100 | 0x4f2428 | u32 | 0x445cf8-d0b: `[veh+0xe4] < −0.15` | steering left |
| +0x104 | 0x4f242c | f32 | 0x445d0f-5f: `fn_0x46a7b0(engine)` clamped ≤165.0 | **speed** (mph); drives terrain gain, engine gain (0x14−spd/2), XFriction/XSpring |
| +0x108..+0x114 | 0x4f2430-3c | 4×i32 | 0x445e33-7e: `0x46de10([veh+0x3a8/3ac/3b8/3bc])` | **tire status FL/FR/RL/RR** → Flat Tire effect (DLL threshold 3000, "Flat Tire: gain%d") |
| +0x118..+0x124 | 0x4f2444-50… | 4×i32 | — | DLL prev-frame tire status |
| +0x128 | 0x4f2450 | u32 | 0x445dfb: `[veh+0x454]&0x004` | **Airborne** |
| +0x12c | — | u32 | — | DLL prev |
| +0x130 | 0x4f2458 | u32 | 0x445e0b: `[veh+0x454]&0x002` | **Skidding** |
| +0x134 | — | u32 | — | DLL prev |
| +0x138 | 0x4f2460 | u32 | 0x445e1d: `[veh+0x454]&0x2000` | **Sliding** |
| +0x13c | — | u32 | — | DLL prev |
| +0x140 | 0x4f2468 | u32 | 0x445e2d: `[veh+0x454]&0x400` | **OilSlick** |
| +0x144 | — | u32 | — | DLL prev |
| +0x148 | 0x4f2470 | u32 | 0x445d25-36: speed>0 ? `[veh+0x45c]+1` : 0 | **surface type + 1** (0 = stopped); DLL terrain table: I7_DIRT_INTERSECTION, I7_PARKING_LOT, I7_ROCKY, I7_WASH_ROAD, I7_DIRT_ROAD, I7_PAVED_ROAD, I7_LIGHT_VEGETATION, I7_PACKED_DIRT, I7_STOPPED, I7_IN_AIR (string order; exact id order = h_2f80 jump table, GUESS) |
| +0x14c | 0x4f2474 | u32 | 0 at init | DLL prev surface |
| +0x150 | 0x4f2478 | node* | event fn (gate `[esp+0x28]>0`) | **Ordnance-impact** event list (weapon hits on player) |
| +0x154 | 0x4f247c | node* | (gate `[esp+0x2c]>0`) | **Concussion-collision** event list (uses EXPLOSN.FRC template, fn 0x10001930) |
| +0x158 | 0x4f2480 | node* | (gate `[esp+0x30]>0`) | written by exe, **never read by this DLL** (dead category; nodes reaped by exe next tick) |
| +0x15c | 0x4f2484 | node* | (gate `[esp+0x34]>0`) | **Impact-collision** event list |
| +0x160 | 0x4f2488 | f32 | 0x445bd3: `fstp` of `call 0x49c8b0` | **frame dt (s)**; DLL requires 0<dt≤0.95 for impact decay |
| +0x164 | 0x4f248c | ptr | const 0x5dcf3c | exe-side struct ptr; **unused by DLL** |
| +0x168 | 0x4f2490 | u32 | `[0x5dcf7c]` | **HINSTANCE** → DirectInputCreateA's first arg |

Key tick-writer excerpts backing the above:

```
0x00445cd5  fcom qword [0x4bd388]        ; 0.15 (double)
0x00445cdb  mov dword [0x4f2424], 1      ; steer-right = ([veh+0xe4] > 0.15)
0x00445cf2  fcomp qword [0x4bd390]       ; -0.15
0x00445d10  call 0x46a7b0                 ; speed(engineobj)
0x00445d25  mov edx, [esi + 0x45c]        ; surface id
0x00445d2b  inc edx
0x00445d2c  mov [0x4f2470], edx           ; block+0x148 = surface+1 (if speed>0)
0x00445d3a  fcom dword [0x4bd398]         ; 165.0f clamp
0x00445d59  fstp dword [0x4f242c]         ; block+0x104 = speed
0x00445d69  call 0x43a320                 ; (&out, veh+0xd4, arg+0x18) -> 3 floats
0x00445dd2  mov [0x4f2418], ecx / +41c / +420   ; block+0xf0..f8 force vector
0x00445e01  mov eax,[esi+0x454]; and eax,2; mov [0x4f2458],eax   ; Skidding
0x00445e3a  call 0x46de10                 ; tire status per [veh+0x3a8/3ac/3b8/3bc]
0x00445e83  call 0x446110                 ; send I7FF_SIM_Effect(&block)
```

### Hardpoint records (+0x30, six slots, stride 0x1c) — DIRECT

DLL loop (0x100022c1 `add esi,0x3c` then per-iteration `add esi,0x1c`,
6 iterations bounded by the parallel DLL arrays 0x100139f0..0x10013a20):

| rec off | hp0 VA | meaning |
|---|---|---|
| +0x00 | 0x4f2358 | firing count/flag (nonzero = trigger held, effect started) |
| +0x04 | 0x4f235c | event flag → misfire ("Misfire: Triggered") |
| +0x08 | 0x4f2360 | event flag → second misfire-ish trigger (jammed/dry, GUESS) |
| +0x0c | 0x4f2364 | **WpnId** — indexes DLL table 0x1000f148 (stride 16: create-fn ptr + gain-mode flag); ids 0x0d..0x10 are missiles (direction jitter via rand); templates CANNON1-4.FRC, MISSILE2/5.FRC, MISSIL45.FRC |
| +0x10 | 0x4f2368 | f32 firing freq (DLL: ×const 0x1000d4f8) |
| +0x14 | 0x4f236c | int gain ("Weapon: Hardpoint:%d WpnId:%d Freq:%d Gain:%d Direction:%d") |
| +0x18 | — | DLL prev/active marker |

### Impact event nodes — DIRECT

Alloc fn 0x445f70: `HeapAlloc(heap 0x52bbcc, 0, 0x20)`, zero-init, link at
list head. Node layout:

| off | writer | meaning |
|---|---|---|
| +0x00 | exe 0x4a7fc4: `fstp` of `0x4ba370(&{0,0,1.0f}, &impact_vec3)` | **direction angle (deg)** of impact relative to car nose |
| +0x04 | exe 0x4a7fdd: `fild qword` of category damage int | **magnitude** (damage points) |
| +0x08 | DLL | DI direction = `(int)(dir*100)` (DirectInput hundredths of degrees) |
| +0x0c | DLL | DI magnitude, then per-tick decay |
| +0x10 | DLL | started flag |
| +0x14 | DLL | IDirectInputEffect* |
| +0x18/+0x1c | both | next/prev; exe tick (0x445e88-0x445f66) frees nodes whose +0x10 and +0x14 are both 0 (HeapFree via [0x4bc104]) |

DLL magnitude formulas (h_32f0, consts .rdata):
- Ordnance: `mag = (40.0 + 0.6667*dmg) * 100`
- Concussion: `mag = (35.0 + 0.6667*dmg) * 100`
- Impact collision: `mag = (55.0 + 0.5625*dmg) * 100`
- Decay per tick using block+0x160 dt; effect stopped when mag < −1500
  (`ebp = 0xfffffa24`).

The one damage fn (0x4a7f24-0x4a81b7) takes four per-category damage amounts
(`[esp+0x28]/[esp+0x2c]/[esp+0x30]/[esp+0x34]`) plus an impact direction
vector and conditionally appends one node per non-zero category. **Only one
active node per list is effect-started** (list-head check `cmp eax, esi`).

### What triggers force output (summary for the rumble map)

Continuous, per-frame: engine vibration (running + pitch + speed), terrain
rumble (surface id + speed), X centering spring / friction (speed), constant
X/Y force from the physics vector (+0xf0..f8), flat-tire shake, skid/slide/
oil/airborne modifiers, per-hardpoint firing vibration while trigger held.
One-shots: engine start, weapon cycle/link/unlink, misfire, and the three
impact categories (ordnance hit, collision, concussion/explosion) with
direction + decaying magnitude.

---

## 4. SHIM SPEC (Q4) — build a fake i7_SFRCE.DLL

### ABI (all verified in disasm)

```c
// All stdcall ("ret 4" at 0x100036e3/0x10003702/0x10001b65; plain "ret" +
// caller-no-cleanup for ExitSystem). Exported undecorated by NAME
// (GetProcAddress("I7FF_InitSystem") etc.). 32-bit x86 PE.

typedef struct I7FF_BLOCK {           // 0x16c bytes, see §3 field map
    uint32_t size;                    // must be 0x16c — VALIDATE, return 0x80070057 otherwise
    uint32_t reset;                   // +0x04
    uint32_t forces_on;               // +0x08  master switch
    /* ... §3 map ... */
} I7FF_BLOCK;                         // game passes the SAME static block (0x4f2328) every call

HRESULT __stdcall I7FF_InitSystem(I7FF_BLOCK *b);   // called ONCE at boot; >=0 = "FF device present"
HRESULT __stdcall I7FF_ExitSystem(void);             // 0 args; called at shutdown (0x44617c: bare `call eax`)
HRESULT __stdcall I7FF_SIM_Effect(I7FF_BLOCK *b);    // called EVERY SIM TICK (from 0x445e83) and
                                                     // immediately after every forces-on/off toggle
```

Contract details the exe relies on:
- Return value: only the **sign** is checked (`test esi,esi; setge al`).
  Return 0.
- InitSystem success ⇒ exe sets 0x52bbd0=1 and streams forever. Failure ⇒ FFB
  dead until relaunch.
- The exe builds/keeps the impact lists itself; the shim must emulate the real
  DLL's node protocol if it wants impact events to *retire*: the exe frees a
  node only when node+0x10 and node+0x14 are both zero, **so the shim must,
  for each consumed impact node, do its rumble and then leave +0x10/+0x14 = 0**
  (i.e. simply *read* node+0x00/+0x04 and not mark it started) — the exe then
  frees it next tick. Simplest correct policy: treat a node as fresh, fire a
  decaying rumble internally, leave the node untouched. (The real DLL instead
  sets +0x10=1/+0x14=ptr to keep it alive while the DI effect decays.)
- No other side effects expected: the real DLL never writes exe state other
  than clearing the one-shot flags (+0x14, +0x24, +0x28, +0x2c, per-hardpoint
  +0x04/+0x08) and its own prev-state slots inside the block. **The shim
  SHOULD clear the one-shots too** after acting on them, mirroring lines like
  `0x1000214e mov [esi+0x24], ebp(0)` — otherwise a one-shot retriggers every
  tick.
- Threading: everything is called from the sim thread; no reentrancy needed.
- The exe never calls FreeLibrary on it except… (FreeLibrary import exists but
  no FFB-path call was found; shutdown is ExitSystem + HeapDestroy).

### Rumble mapping starter (from the DLL's own math)

- Big kicks: impact lists — magnitude `(35..55 + ~0.6*dmg)` → low-frequency
  motor, direction node+0 if the pad does stereo L/R.
- Engine: gain `0x14 − min(speed/2, 0x14)` (loudest idle), freq `8 − k*pitch`.
- Terrain: surface-id table × speed — map ROCKY/WASH_ROAD/DIRT high,
  PAVED_ROAD near zero, I7_IN_AIR/STOPPED zero.
- Weapon fire: per-hardpoint gain (+0x14) while firing flag (+0x00) set.
- Flat tire: any of +0x108..+0x114 abnormal (DLL compares vs 3000).

### Route comparison

- **Fake-module route (this): HIGH confidence.** Surface = 3 stdcall exports +
  one well-mapped struct; loader checks are trivial (HMODULE, 3 names,
  HRESULT sign). Exactly the smack-music-fix SMACKW32 proxy pattern, but we
  don't even need to forward anything — the real DLL is dispensable.
  On Deck/Windows we can even keep it honest: shim consumes the stream and
  drives XInput/SDL rumble. On Mac/Wine builtin-override the DLL in the
  prefix.
- **dinput-proxy route: LOW-MEDIUM.** Must implement IDirectInput(A) v0x500,
  FF-capable EnumDevices, IDirectInputDevice2 with SetDataFormat/
  SetCooperativeLevel/SetProperty/Acquire/CreateEffect + IDirectInputEffect
  (Download/Start/Stop/SetParameters), plus the .frc template loads go through
  CreateEffect with file-derived parameter blocks. 10-20× the surface for the
  same data, and it only exists because the real i7_sfrce.dll demands it.
  Only advantage: keeps the authentic DI effects on real FF wheels — but real
  wheels already work through the real DLL.

---

## 5. Corrections & confirmations for the standing docs

1. 0x52bbcc = **HeapCreate(0,0,0) handle** (event-node heap), not the FFB
   object. [0x4bc110]=HeapCreate, [0x4bc10c]=HeapDestroy, [0x4bc108]=HeapAlloc,
   [0x4bc104]=HeapFree, [0x4bc0f4]=OutputDebugStringA, [0x4bc0ec]=
   GetModuleHandleA, [0x4bc234]=sprintf, [0x4bc2fc]=wsprintfA.
2. Fn-ptr mapping: 0x52bbdc=InitSystem, 0x52bbe0=ExitSystem,
   0x52bbe4=SIM_Effect (prior note had names/pointers cross-matched).
3. "FRC" xref at 0x446025 = string-copy artifact of "I7_SFRCE.DLL"; **no
   registry gate for FFB in Gold**; the game-side FFB init is unconditional.
4. i76.exe has **no DirectInput import**; joystick input presumably WINMM
   (winmm is imported), FFB exclusively via the DLL.
5. 0x4f2314 sentinel tracks `[engine_obj+8]` (engine identity), feeding
   block+0x18 "engine changed", not an effect handle per se.
6. TIREBLWL/TIREBLWR.FRC exist in force/ but are referenced by **no string in
   this DLL** — flat-tire effect is built programmatically; the files are
   likely FRC-edition leftovers.
7. Vehicle flags word `[veh+0x454]` decoded bits: 0=engine running,
   1=skidding, 2=airborne, 3=engine starting, 10=oil slick, 13=sliding,
   11=special-mount modifier (GUESS on 11's game meaning).
8. New helper-fn labels (exe): 0x49c8b0=frame-dt (float, s);
   0x46a7b0(engine)=speed mph; 0x46a790(engine)=engine pitch/freq value;
   0x46de10(tire)=tire status int; 0x43a320=world→body vector transform;
   0x4ba370(v1,v2)=angle between vectors (deg); 0x467790(obj)=mount type code.

## 6. Open questions (for a runtime session)

- Exact surface-id → I7_* name order in h_2f80's dispatch (ids 1..10; string
  order listed in §3 is the .data layout, almost certainly the switch order —
  verify live by driving on pavement vs dirt with a logging shim).
- Block +0xe4..+0xec ([veh+0xbc]×3) and +0x158 list: written, never read —
  vestigial vs FRC-edition features.
- What [veh+0xe4] is exactly (steer input vs lateral slip) — DLL only booleans
  it at ±0.15; a logging shim answers this immediately.
- hwnd source [0x100138c4] inside the DLL (set in DllMain region, not chased)
  — irrelevant for the fake module.
