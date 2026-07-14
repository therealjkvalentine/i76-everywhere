// Interstate '76 "Voodoo" launch stub - the dgVoodoo Glide mode (Interstate 76 - Glide-dgVoodoo-DXVK-Metal.app).
//
// Launches the game inside a COMMAND-LINE Wine virtual desktop:
//   wine explorer /desktop=I76Voodoo,1280x960 i76.exe -glide
// Why: with -glide the game's 2D shell (menus/cutscenes) runs DirectDraw exclusive-
// fullscreen -> a borderless whole-screen window that Wine hard-minimizes on every
// focus loss. The virtual desktop contains it in a real, movable, title-barred
// 1280x960 window instead - and 1280x960 exactly matches dgVoodoo's Resolution=2x
// sim output, so the 3D fills the same window. Using /desktop on the command line
// (not registry AppDefaults) keeps the DxWnd default mode desktop-free.
// Belt+braces: HKCU\...\AppDefaults\i76.exe\Mac Driver\WindowsFloatWhenInactive=all
// (set by setup-voodoo.sh) so the window floats rather than vanishes when unfocused.
//
// Render chain: i76.exe -glide -> dgVoodoo 2.78.2 Glide2x.dll (game dir) ->
// D3D11 FL10.1 -> DXVK (engine i386-windows) -> Vulkan -> MoltenVK -> Metal.
// Bright 3dfx color, 2x internal res, filtered textures - the pretty mode.
//
// TRADEOFF vs the DxWnd default: first-seen effects compile GPU pipelines - a
// one-time "break-in". THE CEILING (researched 2026-07-11, cited in
// docs/DXGI-DGVOODOO-RESEARCH.md): our patched DXVK persists MoltenVK's SPIRV->MSL
// translation across runs (banked), BUT MoltenVK CANNOT persist the compiled *Metal*
// pipeline - VkPipelineCache stores MSL only; MTLBinaryArchive persistence is
// unimplemented (KhronosGroup/MoltenVK#1765, Apple-blocked) and absent even in our
// 1.4.1 (latest). So a small ~0.3-1.0s Metal compile is re-paid every fresh launch;
// zero warmup is impossible, only reducible/front-loadable. Mitigations wired here:
//   - dxvk.conf enableAsync (dyasync): compiles on background threads; first-EVER
//     pipeline of a shader family has no placeholder, so a startup burst can still
//     read as one brief freeze.
//   - MVK_CONFIG_USE_METAL_PRIVATE_API=1 + SHOULD_MAXIMIZE_CONCURRENT_COMPILATION=1:
//     the private-API flag is REQUIRED for the concurrent-compile knob to actually
//     engage (drains the compile queue in parallel instead of serially).
//   - DXVK state cache (i76.dxvk-cache) + persisted VkPipelineCache (i76.vkpipeline-
//     cache) precompile the MSL side during boot/menu. Play a mission once to bank
//     it; later runs skip SPIRV->MSL and only re-pay the (small) Metal compile.
//   NOTE: MSAA multiplies the pipeline count -> multiplies BOTH caches AND the
//   per-launch Metal compile. Turn MSAA off (dgVoodoo CPL / Antialiasing) for the
//   smallest warmup.
//
// CWD must be the game dir: dgVoodoo.conf discovery is CWD-relative, and the DXVK
// state cache lands next to the exe. Same GStreamer/msync env as the main stub.
// Reap on GAME exit (poll i76.exe - the explorer desktop process outlives it).
// Build:  swiftc -O -o /tmp/voodoo i76-voodoo-stub.swift
import Foundation

// Satellite app: the wrapper bundle lives at a fixed place, not inside us.
let A = FileManager.default.homeDirectoryForCurrentUser.path
        + "/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
let gv = A + "/Contents/Frameworks/GStreamer.framework/Versions/1.0"
setenv("DYLD_FALLBACK_LIBRARY_PATH",
       A + "/Contents/Frameworks:" + gv + "/lib:" + A + "/Contents/SharedSupport/wine/lib", 1)
setenv("WINEPREFIX", A + "/Contents/SharedSupport/prefix", 1)
setenv("WINEESYNC", "1", 1); setenv("WINEMSYNC", "1", 1)
setenv("GST_PLUGIN_PATH", gv + "/lib/gstreamer-1.0", 1)
setenv("GST_PLUGIN_SYSTEM_PATH_1_0", gv + "/lib/gstreamer-1.0", 1)
setenv("GST_PLUGIN_SCANNER_1_0", gv + "/libexec/gstreamer-1.0/gst-plugin-scanner", 1)
setenv("GST_REGISTRY_1_0", A + "/Contents/SharedSupport/prefix/gst-registry.bin", 1)
// Pipeline-compile mitigations (see header). USE_METAL_PRIVATE_API MUST precede/pair
// with MAXIMIZE_CONCURRENT_COMPILATION or the concurrent-compile knob is a no-op.
setenv("MVK_CONFIG_USE_METAL_PRIVATE_API", "1", 1)
setenv("MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION", "1", 1)
// FAST_MATH forced on (default 2 = per-shader opt-out): marginally simpler codegen,
// slightly faster Metal compile. IEEE NaN/Inf edge cases are irrelevant for a '97 game.
setenv("MVK_CONFIG_FAST_MATH_ENABLED", "1", 1)
// Keep submits SYNCHRONOUS on the calling thread (=1, the default). We tried the
// decoupled/async path (=0) and it measured slightly SLOWER here (worse pacing), so
// synchronous wins on this stack. Set explicitly to pin it.
setenv("MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS", "1", 1)
setenv("DXVK_STATE_CACHE", "1", 1)

func running(_ pattern: String) -> Bool {
    let t = Process()
    t.executableURL = URL(fileURLWithPath: "/usr/bin/pgrep")
    t.arguments = ["-f", pattern]
    t.standardOutput = FileHandle.nullDevice
    t.standardError = FileHandle.nullDevice
    guard (try? t.run()) != nil else { return false }
    t.waitUntilExit()
    return t.terminationStatus == 0
}

let p = Process()
p.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wine")
// Virtual desktop = the OUTPUT window. Its aspect IS the final aspect (dgVoodoo.conf
// ScalingMode=stretched fills it). 1920x1234 = 14:9 (1.556) = "halfway between 4:3
// and 16:9" - the look the user prefers on all platforms. Want pillarboxed 4:3
// instead? use 1920x1440 here + ScalingMode=centered_ar in dgVoodoo.conf.
p.arguments = ["explorer", "/desktop=I76Voodoo,1920x1234",
               "C:\\GOG Games\\Interstate 76\\i76.exe", "-glide"]
p.currentDirectoryURL = URL(fileURLWithPath:
    A + "/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76")
try! p.run()

// Boot: give the game up to 2 min to appear; then wait for it to exit.
var booted = false
for _ in 0..<120 {
    Thread.sleep(forTimeInterval: 1)
    if running("i76\\.exe") { booted = true; break }
    if !p.isRunning { break }  // launch failed outright
}
while booted && running("i76\\.exe") {
    Thread.sleep(forTimeInterval: 2)
}
// Reap the wine session + sweep anything still referencing this bundle
// (explorer desktop, winedevice, ...). Skip the sweep if the user already
// relaunched - a stale sweep would murder the fresh session.
let k = Process()
k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
k.arguments = ["-k"]
try? k.run(); k.waitUntilExit()
Thread.sleep(forTimeInterval: 1)
if !running("i76\\.exe") && !running("dxwnd\\.exe") {
    let s = Process()
    s.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    s.arguments = ["-9", "-f", A + "/Contents/SharedSupport"]
    try? s.run(); s.waitUntilExit()
}
