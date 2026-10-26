# nitro-tick42 (nitro-port lane 2026-10-21, lab tools\nitro-port\nitro-tick42.psd1; moved into the repo 2026-10-23 for
# tools\Build-From-GOG.ps1 -Game Nitro): the release candidate's tick19-42 preset limited to the switches ported to Nitro
# (docs/records/NITRO-PORT-2026-10-21.md); everything else in tick19-42 stays off on Nitro. I76_ASPECT is rewritten for the
# display by tools\Make-Wide-Conf.ps1 at setup. Replace with the nitro lane's owner preset once it is settled.
@{
    Name = 'nitro-tick42'
    Summary = 'Nitro: tick 41.667, hires clock, 1200 m view, terrain / object / road / shadow detail, ground + hull fixes, Hor+'
    Verified = '[lab 2026-10-21] nitro-port lane console rows (NITRO-PORT s.9); not promoted'
    Env  = @{
        I76_HIRES_CLOCK = '1'; I76_SIM_TICK_MS = '41.667'; I76_SIM_TICK_INPUT = '1'
        I76_FAR_CLIP = '1200'; I76_ROAD_DIST = '1200'; I76_CAM_GROUND_FIX = '1'; I76_TERRAIN_HULL_FIX = '1'
        I76_TERRAIN_LOD = '24'; I76_TERRAIN_LOD_A = '96'; I76_TERRAIN_LOD_B = '24'; I76_TERRAIN_TEX = '8'; I76_OBJECT_LOD = '8'
        I76_SHADOW_DIST = '4'; I76_ROAD_TEX = '8'; I76_CLUTTER_DIST = '1200'; I76_CLUTTER_FADE = '300'; I76_MIRROR_FAR = '300'
        I76_FIX_HEALTH_PCT = '1'; I76_FIX_LABEL_TABLE = '1'; I76_ZGLIDE_TMUFIX = '1'; I76_GLIDE_REFRESH = '120'
        I76_ASPECT = '3440x1440'
        I76_CURSOR_MAP = '1'; I76_CURSOR_MAP_DGV = 'aw'; I76_CURSOR_MAP_SHELL = 'aw'   # NITRO-PORT s.10 (faff357): Nitro imports USER32 directly, the proxy maps both
        I76_MUSIC_RETAIL = '1'; I76_MUSIC_RESUME = '1'
    }
}
