# GRAPHICS TIER MAC FAST (M5 Pro class) (2026-10-24, owner: "machines differ"; i76-everywhere docs\records\LAUNCHERS-2026-10-24.md).
# NOT a preset to launch on its own: it holds only the graphics keys. To tune THIS machine copy it to presets\local.psd1 in
# the game folder and edit; PLAY-i76.ps1 loads the launcher's preset (PLAY.bat: OWNER-2300-ALL) and then local.psd1 over it
# (its keys replace the preset's; a key set to '' removes it = the game's stock value), and logs every key it took from there
# to <game>\play-i76.log. local.psd1 is per machine: never shipped in a pack, gitignored. Preset stock (PLAY-VANILLA.bat) ignores it.
# Guard: I76_TERRAIN_LOD above 1 needs I76_FAR_CLIP (the launcher refuses otherwise).
# Per-Mac sweep (docs/records/MAC-GRAPHICS-TUNE-2026-10-24.md): an M5 Pro carries the x8 detail and roads to 1800 m; everything else stock.
@{
    Name        = 'graphics-mac-fast'
    Summary     = 'Graphics tier, fast Macs (M5 Pro class): detail x8 + roads to 1800 m, everything else stock'
    Verified    = '[per-Mac sweep 2026-10-24, MAC-GRAPHICS-TUNE-2026-10-24.md] measured parts; this file as a set not booted'
    Env         = @{
        I76_ROAD_DIST       = '1800'
        I76_TERRAIN_TEX     = '8'
        I76_OBJECT_LOD      = '8'
        I76_ROAD_TEX        = '8'
        I76_SHADOW_DIST     = '4'
        I76_FAR_CLIP        = ''
        I76_CLUTTER_DIST    = ''
        I76_TERRAIN_LOD     = ''
        I76_TERRAIN_MORPH   = ''
        I76_TERRAIN_MORPH_STATELESS = ''
        I76_TERRAIN_MORPH_SHADE = ''
        I76_TERRAIN_MORPH_NEAR = ''
        I76_SHADE_SMOOTH    = ''
        I76_MIRROR_FAR      = ''
        I76_MIRROR_LOD      = ''
        I76_MIRROR_EVERY    = ''
        I76_MIRROR_M16      = ''
        I76_MIRROR_M16_SKY  = ''
        I76_MIRROR_TEX      = ''
        I76_MIRROR_PAL      = ''
        I76_CLUTTER_FADE    = ''
        I76_CLUTTER_DENSITY = ''
        I76_CLUTTER_ALPHA_FADE = ''
        I76_GLIDE_FOG       = ''
        I76_GLIDE_FOG_ALPHA = ''
        I76_SKY_MIRROR      = ''
    }
}
