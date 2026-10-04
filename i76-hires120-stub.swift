// Interstate '76 "HiRes120" TEST launch stub - installed AS the test wrapper's main
// executable (Interstate 76 - HiRes120 TEST.app/Contents/MacOS/Sikarugir).
//
// The Mac port of the Windows daily driver's best-wide set (2026-10-03):
//   i76.exe -glide -> dgVoodoo 2.78.2 Glide2x.dll -> D3D11 FL10.1 -> DXVK -> MoltenVK -> Metal
//   + music-fix/Strlkup.dll (the proxy carrying the I76_* engine switches below)
//   + I76PATCH.DLL renamed (it is GOG's 20 fps cap)
// Render target = the panel's native pixels: Wine RetinaMode=y in this prefix (so Wine
// sees 3456x2234, not 1728x1117 points), a virtual desktop of exactly that size (explorer
// makes a screen-sized desktop a borderless popup, i.e. fullscreen), and dgVoodoo
// [Glide] Resolution = h:3456, v:2234 with ScalingMode = stretched.
//
// This is a SEPARATE wrapper (an APFS clone of the DxWnd one) so the daily Mac install is
// never touched. Both share the same Windows paths inside their prefixes, so pgrep cannot
// tell their i76.exe apart: this stub refuses to start while any i76.exe is running, and
// on exit it only reaps ITS OWN prefix (wineserver -k with this WINEPREFIX, then a sweep
// of this bundle's path). Never the Windows-path sweep the DxWnd stub uses - that one
// would kill the other install's game.
//
// Parked-mode caveat (docs/VOODOO-PARKED.md): MoltenVK re-compiles Metal pipelines on
// every launch; expect a short hitch the first time each effect appears in a session.
// Build:  swiftc -O -o /tmp/hires i76-hires120-stub.swift
import Foundation

let exe = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath()
let A = exe.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().path
let game = A + "/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"

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
// pgrep/pkill patterns are extended regex: escape the bundle path.
func rx(_ s: String) -> String {
    var o = ""
    for c in s { if "\\^$.|?*+()[]{}".contains(c) { o.append("\\") }; o.append(c) }
    return o
}

// The GAME process only: Wine rewrites argv to the Windows command line, and the
// explorer desktop's own command line also contains "i76.exe" (it is the program to
// start), so an unanchored pattern would also match a desktop process.
let gameProc = "^\"?C:\\\\GOG Games\\\\Interstate 76\\\\i76\\.exe"

// The other install may still be shutting down (or hung on exit - a known DxWnd-mode bug):
// give it 10 s, then say so. NSAlert cannot show from this bundle (NSBGOnly=1: the first
// version sat forever behind an invisible modal), so the message goes through osascript.
var waited = 0
while running(gameProc) && waited < 10 { Thread.sleep(forTimeInterval: 1); waited += 1 }
if running(gameProc) {
    let o = Process()
    o.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    o.arguments = ["-e", "display alert \"Interstate '76 is already running\" message \"Quit the other copy first (if it hung on exit, force-quit it). The HiRes120 test and the DxWnd install cannot run at the same time.\""]
    try? o.run(); o.waitUntilExit()
    exit(1)
}

let gv = A + "/Contents/Frameworks/GStreamer.framework/Versions/1.0"
setenv("DYLD_FALLBACK_LIBRARY_PATH",
       A + "/Contents/Frameworks:" + gv + "/lib:" + A + "/Contents/SharedSupport/wine/lib", 1)
setenv("WINEPREFIX", A + "/Contents/SharedSupport/prefix", 1)
setenv("WINEESYNC", "1", 1); setenv("WINEMSYNC", "1", 1)
setenv("GST_PLUGIN_PATH", gv + "/lib/gstreamer-1.0", 1)
setenv("GST_PLUGIN_SYSTEM_PATH_1_0", gv + "/lib/gstreamer-1.0", 1)
setenv("GST_PLUGIN_SCANNER_1_0", gv + "/libexec/gstreamer-1.0/gst-plugin-scanner", 1)
setenv("GST_REGISTRY_1_0", A + "/Contents/SharedSupport/prefix/gst-registry.bin", 1)
// MoltenVK / DXVK compile mitigations, as the parked Voodoo stub (i76-voodoo-stub.swift).
setenv("MVK_CONFIG_USE_METAL_PRIVATE_API", "1", 1)
setenv("MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION", "1", 1)
setenv("MVK_CONFIG_FAST_MATH_ENABLED", "1", 1)
setenv("MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS", "1", 1)
setenv("DXVK_STATE_CACHE", "1", 1)

// The proxy's switches: presets/best-wide.psd1, with I76_ASPECT set to this panel and the
// Windows-only u32x key dropped. A launch-time override file wins over these defaults:
// <game>/hires120.env, one NAME=VALUE per line (# comments), so a switch can be flipped
// without rebuilding this stub.
var env: [(String, String)] = [
    ("I76_HIRES_CLOCK", "1"), ("I76_FIXED_STEP", "24"), ("I76_FRAMERATE_FIXES", "1"),
    ("I76_ENGINE_DT_FIX", "1"), ("I76_RENDER_INTERP", "1"),
    ("I76_FIX_HEALTH_PCT", "1"), ("I76_FIX_LABEL_TABLE", "1"),
    ("I76_FAR_CLIP", "1800"),
    ("I76_GLIDE_REFRESH", "120"), ("I76_FPS_CAP", "120"),
    ("I76_ASPECT", "3456x2234"),
    ("I76_TERRAIN_LOD", "8"), ("I76_TERRAIN_TEX", "8"), ("I76_OBJECT_LOD", "8"),
    ("I76_SHADOW_DIST", "4"), ("I76_ROAD_TEX", "8"),
    ("I76_CLUTTER_DIST", "300"), ("I76_MIRROR_FAR", "300"),
    ("I76_COLL_DEDUPE", "0"), ("I76_AI_ROLL_HOLD", "0"),
    // diagnostics for the first Mac runs: mciproxy.log gets every switch's n/n site line,
    // and the census logs swaps (= frames) every 600, i.e. the frame rate.
    ("I76MUSIC_LOG", "1"), ("I76_TEX_CENSUS", "1"),
]
if let txt = try? String(contentsOfFile: game + "/hires120.env", encoding: .utf8) {
    for line in txt.split(whereSeparator: \.isNewline) {
        let l = line.trimmingCharacters(in: .whitespaces)
        guard !l.isEmpty, !l.hasPrefix("#"), let eq = l.firstIndex(of: "=") else { continue }
        let k = String(l[..<eq]).trimmingCharacters(in: .whitespaces)
        let v = String(l[l.index(after: eq)...]).trimmingCharacters(in: .whitespaces)
        env.removeAll { $0.0 == k }
        env.append((k, v))
    }
}
// HIRES_DESKTOP=WxH sets the Wine virtual desktop (the output window) instead of the
// panel's full pixel size; it is read here, not passed to the game.
var desktop = "3456x2234"
if let d = env.first(where: { $0.0 == "HIRES_DESKTOP" }) { desktop = d.1 }
env.removeAll { $0.0 == "HIRES_DESKTOP" }
for (k, v) in env where !v.isEmpty { setenv(k, v, 1) }

let wine = A + "/Contents/SharedSupport/wine/bin/wine"
let p = Process()
p.executableURL = URL(fileURLWithPath: wine)
p.arguments = ["explorer", "/desktop=I76HiRes," + desktop,
               "C:\\GOG Games\\Interstate 76\\i76.exe", "-glide"]
p.currentDirectoryURL = URL(fileURLWithPath: game)   // dgVoodoo.conf discovery is cwd-relative
// Wine's own output (crashes, missing DLLs, DXVK/MoltenVK errors) -> hires120-wine.log,
// rewritten each launch. The stub is headless, so this is the only place it shows.
FileManager.default.createFile(atPath: game + "/hires120-wine.log", contents: nil)
if let h = FileHandle(forWritingAtPath: game + "/hires120-wine.log") {
    p.standardOutput = h; p.standardError = h
}
try! p.run()

// Pad layer, as the main stub.
let ahkDir = A + "/Contents/SharedSupport/prefix/drive_c/AutoHotkey"
if FileManager.default.fileExists(atPath: ahkDir + "/AutoHotkeyU32.exe"),
   FileManager.default.fileExists(atPath: ahkDir + "/i76-remap.ahk") {
    let ahk = Process()
    ahk.executableURL = URL(fileURLWithPath: wine)
    ahk.arguments = ["C:\\AutoHotkey\\AutoHotkeyU32.exe", "C:\\AutoHotkey\\i76-remap.ahk"]
    try? ahk.run()
}

var booted = false
for _ in 0..<120 {
    Thread.sleep(forTimeInterval: 1)
    if running(gameProc) { booted = true; break }
    if !p.isRunning { break }
}
while booted && running(gameProc) { Thread.sleep(forTimeInterval: 2) }

// Reap THIS prefix only.
let k = Process()
k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
k.arguments = ["-k"]
try? k.run(); k.waitUntilExit()
Thread.sleep(forTimeInterval: 1)
let s = Process()
s.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
s.arguments = ["-9", "-f", rx(A + "/Contents/SharedSupport")]
try? s.run(); s.waitUntilExit()
