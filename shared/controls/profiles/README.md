# shared/controls/profiles/: personal control maps

Maps here are **never installed by the setup or the kit**. `shared/controls/input.map` stays the one map the kit ships
and every player gets. A profile is one player's own layout, kept in the repo so it travels between machines.

To use one, copy it over `input.map` in your game folder. The setup then treats it as your own map and never replaces it.
The pad / wheel key layers stay on.

| File | What it is |
|---|---|
| `owner-i26.input.map` | The owner's layout (2026-11-03), taken from the owner's I26 map: the kit map with gears also on `[` `]`. `,` `.` stay gears because the key layers type them. I26's pistol keys are left out because the original game has no such action. Linted clean against the Gold and Nitro exes (`tools/lint-input-map.py`). |
