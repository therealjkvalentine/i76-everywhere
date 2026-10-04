# Data track: Interstate '76 game-data formats

This track decodes every file format i76.exe reads, with byte-exact parsers and a small modding kit. It is separate
from the other two tracks:

- the main session owns the exe symbol tables and the console;
- the shell track owns `shell\`, the menus and the saves;
- this track proposes exe names only through `exe-proposals.tsv`.

| file | what |
|---|---|
| FORMATS.md | the format reference: coverage per format, layouts, meanings, open unknowns |
| FORMATS-tables.md | generated layout tables (`fmt\gendoc.py`) |
| FSM.md | the mission scripting language |
| VEHICLES.md | every car stat, traced to where the game reads it |
| LIVE-TESTS.md | falsifiable in-game tests with pre-built artefacts (`mod\stage_livetests.py`) |
| exe-proposals.tsv | proposed exe function names with instruction evidence (`fmt\proposals.py`) |
| roundtrip.json | gate R over the full corpus (`fmt\roundtrip.py`) |
| vehicles.csv | every vehicle variant resolved through the load chain (`fmt\vehicle_sheet.py`) |
| notes\*.md | tracing notes behind every citation |
| out\fsm\*.fsm | every mission script, disassembled and annotated |
| out\mw2db\ | DATABASE.MW2 extracted: menu backgrounds, sprite frames, font sheets (PNG), sounds, `manifest.json` (`fmt\mw2tool.py`; the art is git-ignored game data, the manifest is tracked) |

## Tools

```
python data\fmt\roundtrip.py                    # gate R: decode -> encode -> byte compare + coverage, all formats
python data\fmt\fsmtool.py dis miss16\T01.MSN     # mission script -> text
python data\fmt\fsmtool.py asm my.fsm in.msn data\out\T01.MSN
python data\mod\i76mod.py show zfs:vppirna1.vcf VCFC
python data\mod\i76mod.py alias zfs:gmmedium.gdf  # named stats for this file type
python data\mod\i76mod.py car zfs:vppirna1.vcf armour.front=900 weapon1.gdf=gmheavy.gdf --zfs
python data\mod\stage_livetests.py
python data\fmt\mw2tool.py extract sandbox-gog\main\app\DATABASE.MW2   # shell art -> data\out\mw2db (PNG + manifest.json)
python data\fmt\mw2tool.py repack data\out\mw2db\manifest.json             # rebuild DATABASE.MW2 from the extracted files
```

`i76mod.py` writes only under `data\out`, refuses game folders, reads every output back and re-parses it. `--zfs`
rebuilds I76.ZFS with the edited entry stored uncompressed and every other entry byte-identical. It verifies that
all 6,116 entries decode to the expected bytes.

The parsers import `tools\i76fmt` (the BWD2 container, ZFS, LZO) and never modify it.
