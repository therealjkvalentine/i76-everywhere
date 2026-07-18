// Interstate '76 NITRO launch stub - satellite app "Interstate 76 Nitro (DxWnd).app".
//
// The Nitro Pack (nitro.exe) is a STANDALONE expansion installed alongside the base
// game in the SAME wrapper prefix (drive_c/GOG Games/Interstate 76 Nitro Pack). This
// launcher is a small satellite bundle (like the DxWnd Settings app): it holds no wine
// of its own - it points at the main "Interstate 76 - Software (DxWnd).app" wrapper and
// runs `dxwnd.exe /R:2` (DxWnd profile 1 = Nitro, cloned from the base profile so it
// inherits the same aspect/letterbox/FPS-cap/primary-surface/virtual-CD settings).
//
// Mirrors i76-launch-stub.swift: same env (GStreamer/msync/DYLD), same optional AHK
// remapper, same window-watching quit detection, same HARDENED reap (bounded waits +
// 30s watchdog so the stub can never orphan - see the 2026-07-14 5h-hang).
//
// NOTE: base game and Nitro share ONE wine prefix, so run one at a time - reaping a
// session is prefix-wide (wineserver -k). Normal usage (one game at a time) is clean.
// Build: swiftc -O -o /tmp/nitro i76-nitro-stub.swift
import Foundation
import CoreGraphics

// The main wrapper (this satellite carries no prefix of its own).
let A = FileManager.default.homeDirectoryForCurrentUser.path
        + "/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"

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

// Heal Nitro's savegame.dir before the game reads it - same lost-bookmark bug as the
// base game (the engine's LOAD reader over-reads the final entry; its writer truncates
// the newest one). Pad 56 zero bytes of slack past the last entry each boot; the game's
// next write re-truncates and we re-pad. No-op until the user has saved (file absent).
func padSaveDir(_ A: String) {
    let p = A + "/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76 Nitro Pack/savegame.dir"
    guard var d = FileManager.default.contents(atPath: p), d.count >= 4 else { return }
    let count = d.withUnsafeBytes { $0.load(fromByteOffset: 0, as: UInt32.self) }
    let need = 0x28 + 60 * Int(count) + 56
    if d.count < need {
        d.append(Data(count: need - d.count))
        try? d.write(to: URL(fileURLWithPath: p))
    }
}

var reaped = false
let reapLock = NSLock()
func reap(_ A: String) {
    reapLock.lock(); if reaped { reapLock.unlock(); return }; reaped = true; reapLock.unlock()
    // Watchdog: never let the stub orphan (the 5h-hang lesson). Force-exit in 30s
    // no matter which blocking call below wedges.
    DispatchQueue.global().asyncAfter(deadline: .now() + 30) { Foundation.exit(0) }
    let k = Process()
    k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
    k.arguments = ["-k"]
    try? k.run()
    let kDeadline = Date().addingTimeInterval(12)
    while k.isRunning && Date() < kDeadline { Thread.sleep(forTimeInterval: 0.2) }
    if k.isRunning { k.terminate() }
    for _ in 0..<8 {
        Thread.sleep(forTimeInterval: 1)
        if !running("dxwnd\\.exe") && !running("nitro\\.exe") { break }
    }
    // Skip the bundle sweep only for a genuine relaunch (another satellite/main stub
    // now owns a session). Otherwise sweep so no dxwnd host / hider backdrop lingers.
    let myPid = ProcessInfo.processInfo.processIdentifier
    let otherStubs = pids(rx("Interstate 76 Nitro (DxWnd).app/Contents/MacOS")).filter { $0 != myPid }
    if !otherStubs.isEmpty { return }
    let s = Process()
    s.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    s.arguments = ["-9", "-f", rx(A + "/Contents/SharedSupport")]
    try? s.run(); s.waitUntilExit()
}

// In-session heal: the game re-truncates the dir on every save and re-reads it
// when the save/load board opens, so pad-on-boot alone leaves the newest bookmark
// invisible until next launch (parity with the base-game stub, 2026-07-18).
// Only pad when the file has been quiet >3s - never race the game's own write.
func padSaveDirIfQuiescent(_ A: String) {
    let p = A + "/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76 Nitro Pack/savegame.dir"
    guard let attrs = try? FileManager.default.attributesOfItem(atPath: p),
          let m = attrs[.modificationDate] as? Date,
          Date().timeIntervalSince(m) > 3 else { return }
    padSaveDir(A)
}

setupEnv(A)
padSaveDir(A)

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
p.arguments = ["C:\\dxwnd\\dxwnd.exe", "/R:2"]   // profile 2 (1-based) = Nitro
p.currentDirectoryURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/prefix/drive_c/dxwnd")
try! p.run()

// Optional input remapper (shared with the base game - same prefix, same AHK script).
let ahkDir = A + "/Contents/SharedSupport/prefix/drive_c/AutoHotkey"
var ahkProc: Process? = nil
if FileManager.default.fileExists(atPath: ahkDir + "/AutoHotkeyU32.exe"),
   FileManager.default.fileExists(atPath: ahkDir + "/i76-remap.ahk") {
    let ahk = Process()
    ahk.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wine")
    ahk.arguments = ["C:\\AutoHotkey\\AutoHotkeyU32.exe", "C:\\AutoHotkey\\i76-remap.ahk"]
    try? ahk.run()
    ahkProc = ahk
}
_ = ahkProc

// Boot: up to 2 min for nitro.exe to appear.
var booted = false
for _ in 0..<120 {
    Thread.sleep(forTimeInterval: 1)
    if running("nitro\\.exe") { booted = true; break }
    if !p.isRunning && !running("dxwnd\\.exe") { break }
}
// Play: reap when nitro.exe exits OR the render window closes to the black hider.
var sawTwo = false
var lowStreak = 0
while booted {
    Thread.sleep(forTimeInterval: 2)
    if !running("nitro\\.exe") { break }
    padSaveDirIfQuiescent(A)                           // keep the newest bookmark loadable mid-session
    let n = largeWineWindows()
    if n >= 2 { sawTwo = true; lowStreak = 0 }
    else if sawTwo { lowStreak += 1; if lowStreak >= 3 { break } }
}
reap(A)
