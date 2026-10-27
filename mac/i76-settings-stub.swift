// Interstate '76 DxWnd settings stub (Interstate 76 - DxWnd Settings.app).
//
// Opens the DxWnd GUI (no /R:1 autorun) so you can tweak the profile: select the
// "Interstate 76" row -> Edit for options (Main tab: position/aspect/terminate-on-
// close; DirectX tab: renderer/filters; see docs/guides/DXWND-TUNING.md for what each does).
// Double-click the row to launch the game from here for quick A/B testing.
//
// Changes save to C:\dxwnd\dxwnd.ini (live profile). To make a good config permanent
// in the repo, copy it over games/interstate-76/interstate-76.dxw.
//
// On GUI exit: if you launched the game from the GUI and it's still running, we wait
// for it before reaping, so closing the GUI never yanks a live game.
// Build:  swiftc -O -o /tmp/settings i76-settings-stub.swift
import Foundation
import CoreGraphics

let A = FileManager.default.homeDirectoryForCurrentUser.path
        + "/Applications/Sikarugir/Interstate 76 Gold.app"
let gv = A + "/Contents/Frameworks/GStreamer.framework/Versions/1.0"
setenv("DYLD_FALLBACK_LIBRARY_PATH",
       A + "/Contents/Frameworks:" + gv + "/lib:" + A + "/Contents/SharedSupport/wine/lib", 1)
setenv("WINEPREFIX", A + "/Contents/SharedSupport/prefix", 1)
setenv("WINEESYNC", "1", 1); setenv("WINEMSYNC", "1", 1)
setenv("GST_PLUGIN_PATH", gv + "/lib/gstreamer-1.0", 1)
setenv("GST_PLUGIN_SYSTEM_PATH_1_0", gv + "/lib/gstreamer-1.0", 1)
setenv("GST_PLUGIN_SCANNER_1_0", gv + "/libexec/gstreamer-1.0/gst-plugin-scanner", 1)
setenv("GST_REGISTRY_1_0", A + "/Contents/SharedSupport/prefix/gst-registry.bin", 1)

// ---- THIS APP's processes and windows (nitro-mac lane 2026-10-22; corrected 2026-10-23 night, docs/records/NITRO-MAC-2026-10-21.md s.8) ----
// Several I'76 apps can run at once on a Mac (Gold, Nitro, lab clones), and Wine rewrites every Windows process's argv to its
// Windows command line ("nitro.exe -glide", no path), so neither a bare exe name nor an exe path tells whose game a process is.
// The rewrite also overwrites the environment block that `ps -E` reads: on a live boot nitro.exe showed no WINEPREFIX at all,
// only wineserver did (laptop 2026-10-23, so the 2026-10-22 environment rule never saw its own game). What does tell: the
// executable image. Every app carries its own copy of Wine, and every Wine process of that app (nitro.exe, dxwnd.exe,
// explorer.exe, services, wineserver) runs <bundle>/Contents/SharedSupport/wine/... (proc_pidpath, unaffected by the argv
// rewrite; tools/nitro-mac/pidpath.swift). So "ours" = processes whose image path starts with this bundle's SharedSupport
// folder; the quit detection counts only windows those processes own, and the reap kills only them.
func ownProcs(_ root: String) -> [(pid: Int32, cmd: String)] {
    let t = Process()
    t.executableURL = URL(fileURLWithPath: "/bin/ps")
    t.arguments = ["-A", "-ww", "-o", "pid=,command="]
    let pipe = Pipe(); t.standardOutput = pipe; t.standardError = FileHandle.nullDevice
    guard (try? t.run()) != nil else { return [] }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    t.waitUntilExit()
    let me = ProcessInfo.processInfo.processIdentifier
    var out: [(pid: Int32, cmd: String)] = []
    var buf = [CChar](repeating: 0, count: 4096)
    for line in (String(data: data, encoding: .utf8) ?? "").split(separator: "\n") {
        let s = line.trimmingCharacters(in: .whitespaces)
        guard let sp = s.firstIndex(of: " "), let pid = Int32(s[..<sp]), pid != me else { continue }
        guard proc_pidpath(pid, &buf, UInt32(buf.count)) > 0, String(cString: buf).hasPrefix(root) else { continue }
        out.append((pid: pid, cmd: String(s[s.index(after: sp)...])))
    }
    return out
}
// Our game process: an own process whose Windows command line names the exe (case-insensitive; the env part of the line
// never contains ".exe" names of ours).
func ownGameRunning(_ prefix: String, _ exe: String) -> Bool {
    ownProcs(prefix).contains { $0.cmd.lowercased().contains(exe) }
}
// Large windows owned by our own processes (owner pid + bounds need no Screen Recording permission).
func ownLargeWindows(_ prefix: String) -> Int {
    let mine = Set(ownProcs(prefix).map { Int($0.pid) })
    guard let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]]
    else { return 99 }
    var n = 0
    for w in list {
        guard let pid = w[kCGWindowOwnerPID as String] as? Int, mine.contains(pid) else { continue }
        let b = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
        if (b["Width"] ?? 0) > 600 && (b["Height"] ?? 0) > 400 { n += 1 }
    }
    return n
}
func killOwn(_ prefix: String) {
    for p in ownProcs(prefix) { kill(p.pid, SIGKILL) }
}
let PFX = A + "/Contents/SharedSupport/"   // own processes: image under this folder (ownProcs)

let p = Process()
p.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wine")
p.arguments = ["C:\\dxwnd\\dxwnd.exe"]
p.currentDirectoryURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/prefix/drive_c/dxwnd")
try! p.run()
p.waitUntilExit()
// GUI closed - but never kill a game the user launched from it.
while ownGameRunning(PFX, "i76.exe") { Thread.sleep(forTimeInterval: 2) }
let k = Process()
k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
k.arguments = ["-k"]
try? k.run(); k.waitUntilExit()
Thread.sleep(forTimeInterval: 1)
// Skip the sweep if the user already relaunched something from this wrapper.
if !ownGameRunning(PFX, "i76.exe") && !ownGameRunning(PFX, "dxwnd.exe") {
    killOwn(PFX)   // 2026-10-22/23: this bundle's Wine processes only
}
