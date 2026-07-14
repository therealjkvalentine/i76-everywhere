// Interstate '76 DxWnd settings stub (Interstate 76 - DxWnd Settings.app).
//
// Opens the DxWnd GUI (no /R:1 autorun) so you can tweak the profile: select the
// "Interstate 76" row -> Edit for options (Main tab: position/aspect/terminate-on-
// close; DirectX tab: renderer/filters; see docs/DXWND-TUNING.md for what each does).
// Double-click the row to launch the game from here for quick A/B testing.
//
// Changes save to C:\dxwnd\dxwnd.ini (live profile). To make a good config permanent
// in the repo, copy it over games/interstate-76/interstate-76.dxw.
//
// On GUI exit: if you launched the game from the GUI and it's still running, we wait
// for it before reaping, so closing the GUI never yanks a live game.
// Build:  swiftc -O -o /tmp/settings i76-settings-stub.swift
import Foundation

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
p.arguments = ["C:\\dxwnd\\dxwnd.exe"]
p.currentDirectoryURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/prefix/drive_c/dxwnd")
try! p.run()
p.waitUntilExit()
// GUI closed - but never kill a game the user launched from it.
while running("i76\\.exe") { Thread.sleep(forTimeInterval: 2) }
let k = Process()
k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
k.arguments = ["-k"]
try? k.run(); k.waitUntilExit()
Thread.sleep(forTimeInterval: 1)
// Skip the sweep if the user already relaunched something from this wrapper.
if !running("i76\\.exe") && !running("dxwnd\\.exe") {
    let s = Process()
    s.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    s.arguments = ["-9", "-f", A + "/Contents/SharedSupport"]
    try? s.run(); s.waitUntilExit()
}
