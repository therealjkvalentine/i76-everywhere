// Interstate '76 NITRO launch stub - the main executable of the standalone "Interstate 76 Nitro.app"
// (Contents/MacOS/Sikarugir), nitro-mac lane 2026-10-21 (docs/records/NITRO-MAC-2026-10-21.md).
//
// The app is a clone of the Gold wrapper ("Interstate 76.app": same Wine, DxWnd, OpenGLide-HD, CoreAudio prefix) with
// its OWN prefix holding only the GOG Nitro Pack at C:\GOG Games\Interstate 76 Nitro (stock nitro.exe 28b8ae27, our
// proxy as Strlkup.dll, GOG's strlkup.dll as strlkup_orig.dll, IPXWrapper beside the exe). DxWnd profile 1 (ini index 0)
// runs `nitro.exe -glide`. The Gold app and its prefix are never touched by this stub: every path below is derived
// from this bundle's own location, wineserver -k acts on this bundle's WINEPREFIX only, and the final process sweep
// names this bundle's paths and the Nitro exe's Windows path (not dxwnd.exe / AutoHotkey, which the Gold app shares).
//
// Derived from i76-launch-stub.swift (same env, same quit detection, same bounded reap); differences: waits on
// nitro.exe, no savegame.dir healing (Nitro has no save files), no AutoHotkey remapper.
// Build: swiftc -O -o Sikarugir i76-nitro-app-stub.swift
import Foundation
import CoreGraphics

func largeWineWindows() -> Int {
    guard let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]]
    else { return 99 }
    var n = 0
    for w in list {
        let owner = (w[kCGWindowOwnerName as String] as? String ?? "").lowercased()
        let b = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
        if owner.contains("wine") && (b["Width"] ?? 0) > 600 && (b["Height"] ?? 0) > 400 { n += 1 }
    }
    return n
}

let exe = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath()
let A = exe.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().path

func setupEnv(_ A: String) {
    let gv = A + "/Contents/Frameworks/GStreamer.framework/Versions/1.0"
    setenv("DYLD_FALLBACK_LIBRARY_PATH",
           A + "/Contents/Frameworks:" + gv + "/lib:" + A + "/Contents/SharedSupport/wine/lib", 1)
    setenv("WINEPREFIX", A + "/Contents/SharedSupport/prefix", 1)
    setenv("WINEESYNC", "1", 1); setenv("WINEMSYNC", "1", 1)
    setenv("GST_PLUGIN_PATH", gv + "/lib/gstreamer-1.0", 1)
    setenv("GST_PLUGIN_SYSTEM_PATH_1_0", gv + "/lib/gstreamer-1.0", 1)
    setenv("GST_PLUGIN_SCANNER_1_0", gv + "/libexec/gstreamer-1.0/gst-plugin-scanner", 1)
    setenv("GST_REGISTRY_1_0", A + "/Contents/SharedSupport/prefix/gst-registry.bin", 1)
}

func rx(_ s: String) -> String { NSRegularExpression.escapedPattern(for: s) }

func pids(_ pattern: String) -> [Int32] {
    let t = Process()
    t.executableURL = URL(fileURLWithPath: "/usr/bin/pgrep")
    t.arguments = ["-f", pattern]
    let pipe = Pipe(); t.standardOutput = pipe; t.standardError = FileHandle.nullDevice
    guard (try? t.run()) != nil else { return [] }
    t.waitUntilExit()
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return String(data: data, encoding: .utf8)?.split(separator: "\n").compactMap { Int32($0) } ?? []
}
func running(_ pattern: String) -> Bool { !pids(pattern).isEmpty }

// This app's game process. Wine rewrites argv to the Windows command line, so the Windows path identifies it
// (the old satellite "Interstate 76 Nitro (DxWnd).app" runs C:\GOG Games\Interstate 76 Nitro Pack\nitro.exe, a
// different folder name, so it never matches).
let NITRO = "C:\\\\GOG Games\\\\Interstate 76 Nitro\\\\nitro\\.exe"

var reaped = false
let reapLock = NSLock()
func reap(_ A: String) {
    reapLock.lock(); if reaped { reapLock.unlock(); return }; reaped = true; reapLock.unlock()
    DispatchQueue.global().asyncAfter(deadline: .now() + 30) { Foundation.exit(0) }   // never orphan (2026-07-14)
    let k = Process()
    k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
    k.arguments = ["-k"]                                   // this bundle's WINEPREFIX only (setupEnv)
    try? k.run()
    let kDeadline = Date().addingTimeInterval(12)
    while k.isRunning && Date() < kDeadline { Thread.sleep(forTimeInterval: 0.2) }
    if k.isRunning { k.terminate() }
    for _ in 0..<8 {
        Thread.sleep(forTimeInterval: 1)
        if !running(NITRO) { break }
    }
    let myPid = ProcessInfo.processInfo.processIdentifier
    let otherStubs = pids(rx(A + "/Contents/MacOS/Sikarugir")).filter { $0 != myPid }
    if !otherStubs.isEmpty { return }                      // a relaunch of this app owns a new session
    let s = Process()
    s.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    s.arguments = ["-9", "-f", rx(A + "/Contents/SharedSupport")]
    try? s.run(); s.waitUntilExit()
    let w = Process()
    w.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    w.arguments = ["-9", "-f", NITRO]
    try? w.run(); w.waitUntilExit()
}

// OpenGLide under DxWnd: render size from the main display and the profile's shape (as i76-launch-stub.swift).
func setGlideViewport(_ A: String) {
    let reg = A + "/Contents/SharedSupport/prefix/user.reg"
    let ini = A + "/Contents/SharedSupport/prefix/drive_c/dxwnd/dxwnd.ini"
    guard var txt = try? String(contentsOfFile: reg, encoding: .utf8), txt.contains("\"OGL_OUTPUT\"=\"parent\""),
          let dx = try? String(contentsOfFile: ini, encoding: .isoLatin1) else { return }
    func iniInt(_ k: String) -> Double? {
        for l in dx.components(separatedBy: .newlines) where l.hasPrefix(k + "=") {
            return Double(l.dropFirst(k.count + 1).trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return nil
    }
    let b = CGDisplayBounds(CGMainDisplayID())
    guard let sx = iniInt("sizx0"), let sy = iniInt("sizy0"), sx > 0, sy > 0, b.width > 0, b.height > 0 else { return }
    var w = b.width, h = b.height
    if w / h > sx / sy { w = (h * sx / sy).rounded() } else { h = (w * sy / sx).rounded() }
    let want = "\"OGL_VIEWPORT\"=\"\(Int(w))x\(Int(h))\""
    if let r = txt.range(of: "\"OGL_VIEWPORT\"=\"[^\"]*\"", options: .regularExpression) {
        if txt[r] == want { return }
        txt.replaceSubrange(r, with: want)
    } else { return }
    try? txt.write(toFile: reg, atomically: true, encoding: .utf8)
}

setupEnv(A)
setGlideViewport(A)

var signalSources: [DispatchSourceSignal] = []
for sig in [SIGTERM, SIGINT] {
    signal(sig, SIG_IGN)
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .global())
    src.setEventHandler { reap(A); exit(0) }
    src.resume()
    signalSources.append(src)
}

let p = Process()
p.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wine")
p.arguments = ["C:\\dxwnd\\dxwnd.exe", "/R:1"]          // profile 1 = nitro.exe -glide
p.currentDirectoryURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/prefix/drive_c/dxwnd")
try! p.run()

var booted = false
for _ in 0..<120 {
    Thread.sleep(forTimeInterval: 1)
    if running(NITRO) { booted = true; break }
    if !p.isRunning && !running(rx(A + "/Contents/SharedSupport")) { break }
}
var sawTwo = false
var lowStreak = 0
while booted {
    Thread.sleep(forTimeInterval: 2)
    if !running(NITRO) { break }
    let n = largeWineWindows()
    if n >= 2 { sawTwo = true; lowStreak = 0 }
    else if sawTwo {
        lowStreak += 1
        if lowStreak >= 3 { break }
    }
}
reap(A)
