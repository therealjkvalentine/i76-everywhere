#!/bin/sh
# Interstate '76 - add MOUSE driving + Xbox-pad bindings to the ACTIVE input.map.
#
# Research-grounded (see docs/VERIFIED-FIXES.md "Input"):
#  - I76 has NATIVE mouse support: analog channels `mouse Left/Right` (steer) and
#    `mouse Down/Up` (throttle), buttons LeftBtn/RightBtn/MiddleBtn. Exactly three
#    mouse buttons exist in the engine - weapon 4 stays on the keyboard.
#  - The game polls winmm joyGetPosEx (no DirectInput). Wine 10 serves that from
#    any HID pad; this prefix has already enumerated an Xbox Wireless Controller
#    (VID 045E PID 0B20). GOG shipped input.map bound to a phantom "joystick5"
#    (the packager's machine!) - under Wine the first pad is joystick1.
#  - Syntax notes: inside a block, multiple `+` lines form a CHORD (all at once),
#    `- Keyboard Shift` = must-NOT-hold modifier, `- <device> <channel>` in an
#    analog sink = analog source. Alternative bindings = separate blocks.
#  - DO NOT use the in-game Control Configuration menu - community-confirmed
#    append/wrong-device/crash bugs. Edit input.map directly (this script).
#
# All input methods coexist: keyboard stays, mouse + pad are added.
# Pad axes: left stick = steer (X) / throttle (Y) per the game's own
# JOYSTICK.MAP template. If you'd rather throttle on the triggers, change
# "Down/Up" to "Throttle" (winmm Z axis - both triggers share it, resting
# center: RT pushes +, LT pushes -). Probe axes with: wine control joy.cpl
set -e
GAME="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"
MAP="$GAME/input.map"
[ -f "$MAP" ] || { echo "input.map not found: $MAP"; exit 1; }
[ -f "$MAP.pre-mouse-pad" ] || cp "$MAP" "$MAP.pre-mouse-pad"

python3 - "$MAP" <<'EOF'
import re, sys
p = sys.argv[1]
t = open(p).read()

# 1. analog sinks: replace the stale joystick5 lines with joystick1 + mouse
t = re.sub(r"throttle \{[^}]*\}",
           "throttle {\n   - joystick1  Down/Up\n   - mouse      Down/Up\n}", t, count=1)
t = re.sub(r"steer \{[^}]*\}",
           "steer {\n   - joystick1  Left/Right\n   - mouse      Left/Right\n}", t, count=1)
# 2. the other stale joystick5 reference (special weapon on pad button 2)
t = t.replace("+ joystick5  Button2", "+ joystick1  Button2")

# 3. mouse weapons + pad bindings (separate blocks = alternative bindings,
#    NOT chords). Weapon 1/2/3 on MB1/MB2/MB3; weapon 4 stays on keyboard Four.
ADD = """
# --- Mouse + gamepad additions (setup-mouse-and-pad.sh) ---
hardpoint1_fire {
   + mouse      LeftBtn
}
hardpoint2_fire {
   + mouse      RightBtn
}
hardpoint3_fire {
   + mouse      MiddleBtn
}
weapon_fire {
   + joystick1  Button1
}
weapon_cycle {
   + joystick1  Button3
}
e_brake {
   + joystick1  Button4
}
pilot_glance_up {
   + joystick1  HatUp
}
pilot_glance_down {
   + joystick1  HatDown
}
pilot_glance_left {
   + joystick1  HatLeft
}
pilot_glance_right {
   + joystick1  HatRight
}
"""
if "setup-mouse-and-pad.sh" not in t:
    t = t.rstrip() + "\n" + ADD
open(p, "w").write(t)
print("input.map patched: mouse steer/throttle + MB1/MB2/MB3 weapons 1/2/3,")
print("pad joystick1 (left stick drive, B1 fire, B3 cycle, B4 e-brake, hat glances)")
EOF
echo "Backup: input.map.pre-mouse-pad. Connect the pad BEFORE launching (the game"
echo "enumerates joysticks only at startup). Weapon 4 stays on keyboard 'Four'."

# NOTE: right-click fires ALL weapons - the input.map gains extra RightBtn blocks
# for weapon_fire + hardpoint1/3/4_fire (hardpoint2 already has it). Applied live 2026-07-13.
