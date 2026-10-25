# GRAPHICS TIER MAC baseline (M2 class and up) (2026-10-24, owner: "machines differ"; i76-everywhere docs\records\LAUNCHERS-2026-10-24.md).
# NOT a preset to launch on its own: it holds only the graphics keys. To tune THIS machine copy it to presets\local.psd1 in
# the game folder and edit; PLAY-i76.ps1 loads the launcher's preset (PLAY.bat: OWNER-2300-ALL) and then local.psd1 over it
# (its keys replace the preset's; a key set to '' removes it = the game's stock value), and logs every key it took from there
# to <game>\play-i76.log. local.psd1 is per machine: never shipped in a pack, gitignored. Preset stock (PLAY-VANILLA.bat) ignores it.
# Guard: I76_TERRAIN_LOD above 1 needs I76_FAR_CLIP (the launcher refuses otherwise).
# Per-Mac sweep (docs/records/MAC-GRAPHICS-TUNE-2026-10-24.md): 1800 m alone = 27 fps on an M5 Pro, 17 on an M2; terrain LOD 24 costs
# another 22-26 fps. So the far clip, roads, bushes and terrain LOD stay STOCK here ('' = removed from the ALL preset), as do the mirror,
# the fog / feather fade and the sky key. Kept: the terrain morph keys, smooth shade, detail x2.
@{
    Name        = 'graphics-mac'
    Summary     = 'Graphics tier, Mac baseline: stock distances / LOD / mirror / bushes / fog; terrain morph + smooth shade + detail x2'
    Verified    = '[per-Mac sweep 2026-10-24, MAC-GRAPHICS-TUNE-2026-10-24.md] the parts measured on the Macs; this file as a set not booted'
    Env         = @{
        I76_ROAD_DIST       = ''
        I76_FAR_CLIP        = ''
        I76_CLUTTER_DIST    = ''
        I76_TERRAIN_LOD     = ''
        I76_TERRAIN_TEX     = '2'      # ALL: 8
        I76_OBJECT_LOD      = '2'      # ALL: 8
        I76_ROAD_TEX        = '2'      # ALL: 8
        I76_SHADOW_DIST     = '2'      # ALL: 4 (1 = stock also fine)
        I76_TERRAIN_MORPH   = '0.25'
        I76_TERRAIN_MORPH_STATELESS = '1'
        I76_TERRAIN_MORPH_SHADE = '3'
        I76_TERRAIN_MORPH_NEAR = '100'
        I76_SHADE_SMOOTH    = '1'
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
        # Render size on the Mac (2026-10-25, docs\records\RENDER-KEYS-2026-10-25.md): the Macs run OpenGLide, not dgVoodoo, so
        # I76_RENDER_SCALE / I76_AA (the Windows keys) do nothing there. NO Mac render-size key exists yet: in the Gold app
        # (OGL_OUTPUT=parent under DxWnd) OpenGLide renders at OGL_VIEWPORT, which the launcher stub computes from the display at
        # every start (= the window: 2228x1440 on the 3440x1440 monitor, OpenGLid.log 2026-10-25); OpenGLid.INI's Resolution=1488
        # is overridden and has no effect. A smaller or larger render target needs an OpenGLide-HD patch (render to an FBO, scale
        # it to the window at swap) - the record says where. Mac antialiasing = the prefix's user.reg [Environment] OGL_MSAA (4).
        # I76_RENDER_WIDTH is reserved for that key; PLAY-i76.ps1 ignores it on Windows.
    }
}
