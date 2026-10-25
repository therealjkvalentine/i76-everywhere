# GRAPHICS TIER MAC (and other ~60 fps machines) (2026-10-24, owner: "machines differ"; i76-everywhere docs\records\LAUNCHERS-2026-10-24.md).
# NOT a preset to launch on its own: it holds only the graphics keys. To tune THIS machine copy it to presets\local.psd1 in
# the game folder and edit; PLAY-i76.ps1 loads the launcher's preset (PLAY.bat: OWNER-2300-ALL) and then local.psd1 over it
# (its keys replace the preset's; a key set to '' removes it = the game's stock value), and logs every key it took from there
# to <game>\play-i76.log. local.psd1 is per machine: never shipped in a pack, gitignored. Preset stock (PLAY-VANILLA.bat) ignores it.
# Guard: I76_TERRAIN_LOD above 1 needs I76_FAR_CLIP (the launcher refuses otherwise).
# The Mac graphics lane (MacBook, Wine): far 2300 m cost the most (21 fps), the x8 detail keys next (37 fps); the morph, smooth-shade,
# mirror and bush keys cost nothing measurable there, so they stay as on the ALL set.
@{
    Name        = 'graphics-mac'
    Summary     = 'Graphics tier for slower machines: 1800 m distances, stock object / texture detail, no fog; morph / smooth shade / mirror / sparse bushes kept'
    Verified    = '[untested as a set] the Mac graphics lane measured the parts on the MacBook (2300 m -> 21 fps; x8 detail -> 37 fps; morph / smooth / mirror / clutter keys free there)'
    Env         = @{
        I76_FAR_CLIP        = '1800'   # ALL: 2300
        I76_ROAD_DIST       = '1800'   # ALL: 2300
        I76_CLUTTER_DIST    = '1800'   # ALL: 2300
        I76_TERRAIN_LOD     = '24'
        I76_TERRAIN_TEX     = ''       # stock detail (ALL: x8)
        I76_OBJECT_LOD      = ''       # stock (ALL: x8)
        I76_SHADOW_DIST     = ''       # stock (ALL: x4)
        I76_ROAD_TEX        = ''       # stock (ALL: x8)
        I76_GLIDE_FOG       = ''       # no fog / feather fade (ALL: '0.75,hzd')
        I76_GLIDE_FOG_ALPHA = ''
        I76_TERRAIN_MORPH   = '0.25'
        I76_TERRAIN_MORPH_STATELESS = '1'
        I76_TERRAIN_MORPH_SHADE = '3'
        I76_TERRAIN_MORPH_NEAR = '100'
        I76_SKY_MIRROR      = '0'
        I76_SHADE_SMOOTH    = '1'
        I76_MIRROR_FAR      = '1000'
        I76_MIRROR_LOD      = '1'
        I76_MIRROR_EVERY    = '2'
        I76_MIRROR_M16      = '1'
        I76_MIRROR_M16_SKY  = '0'
        I76_MIRROR_TEX      = '2'
        I76_MIRROR_PAL      = '1'
        I76_CLUTTER_FADE    = '450'
        I76_CLUTTER_DENSITY = '0.5'
        I76_CLUTTER_ALPHA_FADE = '150'
    }
}
