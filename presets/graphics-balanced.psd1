# GRAPHICS TIER BALANCED (the ALL set as it is) (2026-10-24, owner: "machines differ"; i76-everywhere docs\records\LAUNCHERS-2026-10-24.md).
# NOT a preset to launch on its own: it holds only the graphics keys. To tune THIS machine copy it to presets\local.psd1 in
# the game folder and edit; PLAY-i76.ps1 loads the launcher's preset (PLAY.bat: OWNER-2300-ALL) and then local.psd1 over it
# (its keys replace the preset's; a key set to '' removes it = the game's stock value), and logs every key it took from there
# to <game>\play-i76.log. local.psd1 is per machine: never shipped in a pack, gitignored. Preset stock (PLAY-VANILLA.bat) ignores it.
# Guard: I76_TERRAIN_LOD above 1 needs I76_FAR_CLIP (the launcher refuses otherwise).
# Copying this unchanged changes nothing on PLAY.bat; it is here to edit one value at a time.
@{
    Name        = 'graphics-balanced'
    Summary     = 'Graphics tier = the ALL set as shipped (2300 m, LOD 24, detail x8, feather fade at 0.75): a starting point to edit'
    Verified    = '[RC 2026-10-24] these are the OWNER-2300-ALL values (gated on rc-twin-20261024, desktop 120 fps)'
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
        # Render target + MSAA (2026-10-25, owner: "Supersampling and AA probably need to be in the graphics setting options"):
        # read by PLAY-i76.ps1, not the proxy; it rewrites dgVoodoo.wide.conf ([Glide] Resolution / Antialiasing) when they change
        # (docs\records\RENDER-KEYS-2026-10-25.md). I76_RENDER_SCALE 1 | 1.5 | 2 = render at that many times the display per axis;
        # I76_AA 0 | 2 | 4 | 8 = MSAA off / 2x / 4x / 8x.
        I76_RENDER_SCALE    = '2'      # = what PLAY.bat has rendered since 2026-10-12 (6880x2880 on 3440x1440)
        I76_AA              = '4'      # = 4x, as shipped
        # Field of view (2026-10-25, owner: "FOV should be configurable in the graphics config too"): read by the proxy. The 4:3
        # base the widescreen (Hor+) maths widens for the panel: 90 -> about 122 deg on 21:9, 106 on 16:9. Stock 90 / 120 (hood).
        I76_FOV             = '90'
        I76_FOV_HOOD        = '120'
    }
}
