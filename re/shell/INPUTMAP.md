# Why the in-game Control Configuration menu corrupts `input.map`

AGENTS.md records the field case of 2026-08-02: after the in-game menu rewrote `input.map`, a working wheel went
dead. The signature was that the `steer`/`throttle` blocks were gone, there were zero `joystick1` references, every
button pointed at `joystick8`, and the file was markedly smaller. The rule since has been "never rebind in the menu"
plus a lint. This file is the mechanism, in the pristine shell (`deb41008`), found by naming batch B and re-verified
at the instructions marked ✓.

## The pieces

| function | role |
|---|---|
| `InputMap_Read` 0x1000f390 | parses `input.map` into a fixed table when Control Configuration opens (called at 0x1000ece9) |
| `InputMap_Write` 0x1000fd30 | rewrites `input.map` from the table; called only by the Done button (region 3, 0x1000efe8). Esc leaves without writing (0x1000f05f). |
| `InputMap_ScanDevices` 0x100102d0 | names the devices the writer prints |
| `ControlConfig_CaptureBinding` 0x10010790, `ControlConfig_ApplyListPick` 0x10010ad0 | edit the table when you rebind |

Table: **40 actions × 0x58 bytes at 0x100450a8**. Record: +0 device class (0 none, 1 keyboard, 2 joystick, 3 mouse),
+4 skip flag, +8 action name, +0x28 key text, +0x48 hit rectangle. Record k is at 0x100450a8 + 0x58·k: throttle 0,
throttle_up 1 (0x10045100), throttle_down 2 (0x10045158), …

## Loss mechanisms (each one alone loses bindings)

1. **The reader keeps one line per block.** It stores the first binding and skips to `}` (0x1000fa4f–0x1000facd),
   so a second source in the same block (a mouse line under `steer`, say) is lost.
2. **The reader drops unknown blocks.** A block name not among the 40 actions is dropped (lookup 0x1000f48b–0x1000f4b1).
3. **The reader keeps only the device class.** It takes the first letter of the device token ('m', 'j', else
   keyboard; 0x1000f565–0x1000f5a2). **The `1` in `joystick1` is discarded.**
4. **One bad line aborts the parse** (0x1000fb2e returns 0). Every later action keeps its static default, device 0.
5. **An axis binding zeroes the keyboard driving keys** ✓: loading a joystick throttle sets throttle_up/down to device 0
   (`mov [0x10045100],ebx` / `mov [0x10045158],ebx` at 0x1000f627 / 0x1000f62d). Steer does the same (0x1000f85b / 0x1000f861).
6. **Rebinding zeroes the axis** ✓: capturing any `throttle*` or `steer*` action writes device 0 into the axis record
   (`mov [0x100450a8],ebp` at 0x1001083c; also 0x100108f4, 0x10010c74, 0x1001106a), and clears any other action with the
   same key text (0x10010810, 0x10010b49).
7. **The writer skips device-0 records** ✓ (`cmp [..],0` at 0x1000fd87 / 0x1000fd90). Together with 5 and 6, **the
   `steer` and `throttle` blocks are not written at all.** That is the "steer and throttle blocks GONE" signature.
8. **The writer skips one extra record after each axis block** ✓ (+0x58 added to all cursors at 0x100101e2–0x100101fa).
   That drops `throttle_up` / `steer_left` even when they hold a binding.
9. **One device name per class** ✓: `InputMap_ScanDevices` copies each enumerated device's name into its class's single
   slot (`mov edi,[0x100462b0]; rep movsd` at 0x1001036c–0x10010375), so the **last** joystick enumerated names every
   joystick binding. That is the "every button re-pointed at `joystick8`" signature (joystick8 was the last device, a
   3Dconnexion emulator). The copy has no length bound into a 20-byte slot (0x10010331–0x100103b8).
10. **Axis signs are forced to "-"** (0x100101a5 / 0x100101bd / 0x100101cf). The body is always `- … Down/Up`,
    `- … Left/Right` or `- dev key`.
11. **Modifier lines are added.** Every keyboard binding except Shift and Control is written with
    `- Keyboard Shift` and `- Keyboard Control` lines (0x1001008b–0x100100c4), so holding Shift or Ctrl disables it.
12. **`input.def` is appended verbatim** (0x1001025c–0x1001029c). Anything else the user had in `input.map` is gone,
    hence "markedly smaller".

## Consequences and recommendations

- The AGENTS.md rule stands and now has a reason: the round trip is lossy by design (1–4, 9–12), and editing any
  driving control destroys the axis blocks (5–8).
- **Opening** Control Configuration and leaving with **Esc** does not write the file (0x1000f05f). Leaving with **Done** does,
  even with no changes. That is testable: LIVE-TESTS T7.
- **Recommended protection (no binary patch):** make `input.map` read-only on the installs, which the lint and the
  launcher can do. `InputMap_Write` then fails at `fopen("w")` (0x1000fd41) and writes nothing. Whether it does so
  cleanly (null check after 0x1000fd47) is T7's second question.
- **Binary option (proposed, not built):** turn Done into Esc for the file write by jumping over the call at
  0x1000efe8, the equivalent of `ControlConfig_Frame` never writing. That is one 5-byte NOP and makes the menu view-only.
  It is a policy call for James, since some players rebind in the menu.

## Possible crash (static, needs T7)

`InputMap_Read` at 0x1000f644/0x1000f649 and 0x1000f878/0x1000f87d reads `[[0x10056c2c]]` (the last clicked action,
written only in `ControlConfig_Frame` 0x1000f037/0x1000f0c6) where it looks like it should use the record being
parsed. On the first open in a session that global is null. So a `throttle` or `steer` block whose first line is
keyboard or mouse would fault when the menu opens. The project's own `joystick1` file takes the joystick branch and is
safe.
