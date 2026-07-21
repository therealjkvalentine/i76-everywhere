# OpenGLide-HD — true high-resolution texture replacement for I76

The patch series that turns [voyageur/openglide](https://github.com/voyageur/openglide)
into **OpenGLide-HD**: hash-based texture dump/replace at arbitrary resolution —
the only route past the engine's fixed texture dimensions (the dgVoodoo/ADDON
pipeline is same-size "enhanced" only). Background and bring-up saga:
[docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](../../docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md) §7.1.

What the patches add (~300 lines + vendored stb single-file libs):

- `0001` — the HD hook in `PGTexture::MakeReady`: every texture the game
  downloads is content-hashed (FNV-1a 64); `hdtex\dump\<hash>.png` harvests the
  original, and a matching `hdtex\<hash>.png` uploads **in its place at any
  resolution**. Directory presence is the only config. Includes `build-hd.ps1`
  and `README-HD.md`.
- `0002` — passthrough output window (input-transparent GL child shown only
  during 3D present) + a `WinOpenDelayMS` race guard at boot.

## Rebuild from scratch

```powershell
git clone https://github.com/voyageur/openglide.git
cd openglide
git am path\to\i76-everywhere\tools\openglide-hd\*.patch
./build-hd.ps1     # added by patch 0001; needs w64devkit x86 (32-bit GCC) on PATH
```

Output: `glide2x.dll` (32-bit). Deploy with
[`swap-renderer.ps1 openglide`](../../swap-renderer.ps1), which also owns the two
load-bearing companions (never skip them):

- `OpenGLid.ini` **must** keep `TextureMemorySize=2` / `FrameBufferMemorySize=2`
  — I76 crashes on >2 MB TMU reports (same engine bug dgVoodoo dodges with
  `MemorySizeOfTMU=2048`).
- The Windows **256COLOR** compat flag on `i76.exe` (HKCU AppCompatFlags) — the
  game needs 8-bit DDraw palettes or it crashes at sim entry; dgVoodoo's DDraw
  wrapper can't be used here (collides with OpenGLide's GL window at boot).

## Status (2026-07-10)

Builds clean, boots, stays alive. The dump→upscale→replace loop is implemented
but **not yet verified end-to-end in-game** — the remaining step is a
human-driven melee run to harvest `hdtex\dump\`, then:

```
realesrgan-ncnn-vulkan -i hdtex\dump -o hdtex -n realesrgan-x4plus-anime
```

(folder mode keeps the hash filenames — that output IS the pack).
dgVoodoo remains the daily driver; swap back with `swap-renderer.ps1 dgvoodoo`.
