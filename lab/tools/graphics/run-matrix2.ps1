# run-matrix2.ps1 - graphics variants around the FIXED sandbox conf (fake fullscreen, 4:3 picture 1920x1440 on the
# 3440x1440 panel), through try-conf.ps1 overrides: internal resolution 1x / 1.5x / 2x / 3x of the picture, MSAA,
# downscale filter. One boot each at 120 Hz, car frozen at the same spot, full-desktop screenshot + frame stats + GPU.
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$v = [ordered]@{
    "01-current-2x-msaa4"  = ""
    "02-1x-noaa"           = "Glide.Resolution=1920x1440;Glide.Antialiasing=off"
    "03-1x-noaa-repeat"    = "Glide.Resolution=1920x1440;Glide.Antialiasing=off"
    "04-1x-msaa8"          = "Glide.Resolution=1920x1440;Glide.Antialiasing=8x"
    "05-1.5x-msaa4"        = "Glide.Resolution=2880x2160;Glide.Antialiasing=4x"
    "06-2x-noaa"           = "Glide.Resolution=3840x2880;Glide.Antialiasing=off"
    "07-2x-msaa8"          = "Glide.Resolution=3840x2880;Glide.Antialiasing=8x"
    "08-2x-msaa4-bicubic"  = "GeneralExt.Resampling=bicubic"
    "09-2x-msaa4-lanczos3" = "GeneralExt.Resampling=lanczos-3"
    "10-3x-noaa"           = "Glide.Resolution=5760x4320;Glide.Antialiasing=off"
    "11-3x-msaa4"          = "Glide.Resolution=5760x4320;Glide.Antialiasing=4x"
    "12-3x-msaa4-lanczos3" = "Glide.Resolution=5760x4320;Glide.Antialiasing=4x;GeneralExt.Resampling=lanczos-3"
    "13-2x-msaa4-tmu-app"  = "Glide.TMUFiltering=appdriven"
    "14-current-repeat"    = ""
}
foreach ($k in $v.Keys) { & "$Here\try-conf.ps1" -Tag $k -Set $v[$k] -NoPin 2>&1 | Where-Object { "$_" -match "^\[$k\]|BOOT PROBLEM|NOT FOUND" } | ForEach-Object { "$_" } }
"[matrix2] captures in C:\Users\james\i76-uncap-lab\captures\graphics\try"
