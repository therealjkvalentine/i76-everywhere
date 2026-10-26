# GRAPHICS TIER MID (mid-range GPUs) (2026-10-25, render-keys lane; i76-everywhere docs\records\RENDER-KEYS-2026-10-25.md).
# NOT a preset to launch on its own: it holds only the graphics keys. To tune THIS machine copy it to presets\local.psd1 in
# the game folder and edit; PLAY-i76.ps1 loads the launcher's preset (PLAY.bat: OWNER-2300-ALL) and then local.psd1 over it
# (its keys replace the preset's; a key set to '' removes it = the game's stock value), and logs every key it took from there
# to <game>\play-i76.log. local.psd1 is per machine: never shipped in a pack, gitignored. Preset stock (PLAY-VANILLA.bat) ignores it.
# Guard: I76_TERRAIN_LOD above 1 needs I76_FAR_CLIP (the launcher refuses otherwise).
# = graphics-balanced with the render target at the display's own size (I76_RENDER_SCALE 1: a quarter of the pixels of the 2x
# supersample) and 4x MSAA. Every other key is balanced's.
# TODO(render-keys): set I76_RENDER_SCALE / I76_AA (and whether any distance key should drop) from
# docs\records\SUPERSAMPLE-COST-2026-10-25.md when that lane's measurement lands; until then the 1 / 4 pick is not measured.
@{
    Name        = 'graphics-mid'
    Summary     = 'Graphics tier for mid-range GPUs: the ALL set, rendered at the display size (no supersample), 4x MSAA'
    Verified    = '[NOT MEASURED] the ALL keys are gated (RC 2026-10-24); render scale 1 / AA 4 not booted as a set - SUPERSAMPLE-COST-2026-10-25.md pending'
    Env         = @{
        I76_FAR_CLIP        = '2300'
        I76_ROAD_DIST       = '2300'
        I76_CLUTTER_DIST    = '2300'
        I76_TERRAIN_LOD     = '24'
        I76_TERRAIN_TEX     = '8'
        I76_OBJECT_LOD      = '8'
        I76_SHADOW_DIST     = '4'
        I76_ROAD_TEX        = '8'
        I76_GLIDE_FOG       = '0.75,hzd'
        I76_GLIDE_FOG_ALPHA = '1'
        I76_GLIDE_REFRESH   = '120'
        I76_TERRAIN_MORPH   = '0.5'   # 0.5: carried snaps >4 px halved vs 0.25 (TERRAIN-STATIC-PLAN s.4.1, laptop n 2), fps same
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
        # Render target + MSAA (2026-10-25, owner: "Supersampling and AA probably need to be in the graphics setting options"):
        # read by PLAY-i76.ps1, not the proxy; it rewrites dgVoodoo.wide.conf ([Glide] Resolution / Antialiasing) when they change
        # (docs\records\RENDER-KEYS-2026-10-25.md). I76_RENDER_SCALE 1 | 1.5 | 2 = render at that many times the display per axis;
        # I76_AA 0 | 2 | 4 | 8 = MSAA off / 2x / 4x / 8x.
        I76_RENDER_SCALE    = '1'      # balanced: 2 (1 = the display's size, 3440x1440 on 3440x1440)
        I76_AA              = '4'
        # Field of view (2026-10-25, owner: "FOV should be configurable in the graphics config too"): read by the proxy. The 4:3
        # base the widescreen (Hor+) maths widens for the panel: 90 -> about 122 deg on 21:9, 106 on 16:9. Stock 90 / 120 (hood).
        I76_FOV             = '90'
        I76_FOV_HOOD        = '120'
    }
}
