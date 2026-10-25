# shots.psd1 - the game shots record-shot.ps1 can capture headless (docs/LAUNCH-VIDEO-2026-10-25.md s.1 has the full shot list).
# Each shot = one boot of the launch-video twin (lab launchvid-20261025, a twin of test-gold) in a 1920x1080 window at the top left
# of the primary screen (dgVoodoo.lv1080.conf: [Glide] 3840x2160 supersample, AppControlledScreenMode false; I76_ASPECT 1920x1080 for
# the non-stock presets), captured with ffmpeg ddagrab (the window rect only) at 60 fps.
#   Preset  : a preset file of the twin (presets\<name>.psd1); 'stock' = no I76_* key (PLAY-VANILLA.bat's set, 20 fps I76PATCH cap)
#   Strip   : keys removed from the preset (the "before" of a single feature)
#   Keys    : keys added / overridden
#   Start   : I76_START_POS (x,y,z,heading,?) or '' = the mission start
#   Still   : seconds held (handbrake + S) after capture starts;  Drive: seconds of W after that;  Steer: @( @(t0, t1, 'A'|'D') ... ) relative to drive start
@{
    'route-stock' = @{ Mission = 't05'; Preset = 'stock'; Patch20 = $true; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 22; Note = 'PLAY-VANILLA set: stock 600 m far clip, 20 fps' }
    'route-all'   = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 22; Note = 'PLAY.bat set: 2300 m, tick 41.667 ms, 120 fps' }
    'fade-before' = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 14
                       Strip = @('I76_GLIDE_FOG', 'I76_GLIDE_FOG_ALPHA'); Note = 'far edge: hard cut at 2300 m' }
    'morph-before'= @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 14
                       Strip = @('I76_TERRAIN_MORPH', 'I76_TERRAIN_MORPH_STATELESS', 'I76_TERRAIN_MORPH_SHADE', 'I76_TERRAIN_MORPH_NEAR', 'I76_SHADE_SMOOTH'); Note = 'terrain LOD splits pop' }
    'mirror-before' = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = ''; Still = 3; Drive = 14
                       Strip = @('I76_MIRROR_FAR', 'I76_MIRROR_LOD', 'I76_MIRROR_EVERY', 'I76_MIRROR_M16', 'I76_MIRROR_M16_SKY', 'I76_MIRROR_TEX', 'I76_MIRROR_PAL'); Note = 'stock mirror: 100 m, 8-bit art' }
    'mirror-after'  = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = ''; Still = 3; Drive = 14; Note = 'mirror 1000 m, main-view art' }
    'mirror-stock'  = @{ Mission = 't05'; Preset = 'stock'; Patch20 = $true; Start = ''; Still = 3; Drive = 14; Note = 'the whole stock picture at the canyon start' }
    'route-stock43' = @{ Mission = 't05'; Preset = 'stock'; Patch20 = $true; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 22; W = 1440; H = 1080; Conf = 'dgVoodoo.lv43-640.conf'; Note = 'the 1997 look: 640x480 Glide, 4:3, GOG 20 fps limiter' }
    # v2 (owner feedback 2026-10-25): the T05 opening fly-in (sweeps the valley: 600 m popping vs 2300 m morph), smoothness slalom, glances
    'opening-stock43' = @{ Mission = 't05'; Preset = 'stock'; Patch20 = $true; Opening = $true; Start = ''; Still = 70; Drive = 0; W = 1440; H = 1080; Conf = 'dgVoodoo.lv43-640.conf'; Note = 'T05 scripted opening, stock 4:3 20 fps' }
    'opening-all'     = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Opening = $true; Start = ''; Still = 70; Drive = 0; Note = 'T05 scripted opening, PLAY.bat set' }
    'slalom-stock43'  = @{ Mission = 't05'; Preset = 'stock'; Patch20 = $true; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 14; W = 1440; H = 1080; Conf = 'dgVoodoo.lv43-640.conf'
                         Steer = @(@(3.0, 3.8, 'A'), @(4.6, 5.4, 'D'), @(6.2, 7.0, 'A'), @(7.8, 8.6, 'D'), @(9.4, 10.2, 'A')); Note = 'fast weave, 20 fps' }
    'slalom-all'      = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 14
                         Steer = @(@(3.0, 3.8, 'A'), @(4.6, 5.4, 'D'), @(6.2, 7.0, 'A'), @(7.8, 8.6, 'D'), @(9.4, 10.2, 'A')); Note = 'fast weave, tick + interpolated display' }
    'glance-all'      = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = '7972,101.8,44035,-90,6'; Still = 3; Drive = 14
                         Steer = @(@(4.0, 5.5, 'LEFT'), @(7.0, 8.5, 'RIGHT'), @(10.0, 11.5, 'DOWN')); Note = 'glance keys left / right / back while driving (beside route-all = the fixed view)' }
    'sky-twopass'   = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = ''; Still = 10; Drive = 0; Keys = @{ I76_SKY_MIRROR = '1' }; Note = 'sky scrolled by the mirror pass too' }
    'sky-onepass'   = @{ Mission = 't05'; Preset = 'OWNER-2300-ALL'; Start = ''; Still = 10; Drive = 0; Note = 'one-pass sky (owner pick)' }
}
