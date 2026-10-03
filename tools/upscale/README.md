# tools/upscale - texture-upscaling experiment harness

Code only. Decoded game art, model weights, runs and scores are copyrighted or third-party and live outside the
repo, in a local work dir (default `C:\Users\james\i76-upscale-work`, override with `--work` or env
`I76_UPSCALE_WORK`). Never commit images or weights here; `.gitignore` in this folder blocks the usual suspects.

Plan this serves: the owner's "Interstate 76 Texture Upscaling - Research & Experiment Plan" (2026-10-03),
section 9 (24-tile benchmark, LPIPS/DISTS + sharpness scoring, blind A/B, CSV logging).

| file | does |
| --- | --- |
| `build_bench.py` | decodes the 24-tile benchmark (8 classes x 3) from an extracted I76.ZFS with `../i76img.py` into `WORK/src/<class>/<name>.png` + `.mask.png`, writes `src/manifest.csv` and a 4x contact sheet |
| `upscale_run.py` | manifest + YAML/JSON recipe -> `WORK/runs/<id>/{4x,final,mask}` + `run.json`. spandrel, so any arch spandrel / spandrel_extra_arches loads (ESRGAN, Compact, DAT, RGT, RealPLKSR, SPAN...). Per class: model, optional pre-model, overscale 4/8/16 (multi-pass), target scale, downscale filter, alpha mode (combined / separate + edge bleed / threshold, optional alpha model), wrap/reflect padding, colour match, palette lock, tiled inference |
| `score.py` | LPIPS + DISTS (pyiqa) of the final downscaled back to native vs the original, mean CIEDE2000 on opaque pixels, Laplacian variance of final and of a bicubic baseline; appends `WORK/runs/scores.csv` |
| `contact_sheet.py` | rows = tiles, columns = original + runs, labelled, optional scores under each cell |
| `ab_viewer.py` | tkinter blind A/B (sides randomised), Left/Right/Down=equal, appends `WORK/runs/picks.csv` |
| `upscale_common.py` | manifest/IO helpers shared by the above |
| `recipes/` | example recipes (`smoke-anime-4to2.yaml`) |

Environment: Python 3.12 venv with torch 2.5.1+cu121 (has sm_61 for the GTX 1080 Ti), spandrel 0.4.2,
spandrel_extra_arches 0.2.0, pyiqa 0.1.16, opencv-python, pillow, numpy, pyyaml. Extract the archive with
`../zfs_extract.py` (Windows: `LZO2_DLL` pointing at a 64-bit lzo2.dll, e.g. anaconda's `Library\bin\lzo2.dll`).

Quick start:

```
PY=C:\Users\james\i76-upscale-work\.venv\Scripts\python.exe
%PY% build_bench.py
%PY% upscale_run.py --recipe recipes\smoke-anime-4to2.yaml --id my-run
%PY% score.py my-run
%PY% contact_sheet.py my-run other-run --scores
%PY% ab_viewer.py my-run other-run
```

Instrument checks done when it was built (2026-10-03): a nearest-2x "identity" run scores LPIPS 0, DISTS 0,
dE 0 on all 24 tiles; palette lock output is a strict subset of the source tile's colours; threshold alpha is
binary; terrain with wrap padding keeps the tile-edge seam near the original's own (seam/inner-gradient ratio
1.3-1.8 vs 0.9-2.2 for the originals) while `pad: none` gives 5-9.

Caveats: `lapvar` rewards blockiness as well as detail (a nearest-neighbour 2x scores higher than most models),
so read it next to LPIPS/DISTS, not alone. Billboard/sign tiles are stored flipped in the game data and are left
that way.
