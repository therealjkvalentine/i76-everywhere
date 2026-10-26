// Interstate '76 NITRO launch stub - the main executable of the standalone "Interstate 76 Nitro.app"
// (Contents/MacOS/Sikarugir), nitro-mac lane 2026-10-21 (docs/records/NITRO-MAC-2026-10-21.md).
//
// The app is a clone of the Gold wrapper ("Interstate 76 Gold.app": same Wine, DxWnd, OpenGLide-HD, CoreAudio prefix) with
// its OWN prefix holding only the GOG Nitro Pack at C:\GOG Games\Interstate 76 Nitro (stock nitro.exe 28b8ae27, our
// proxy as Strlkup.dll, GOG's strlkup.dll as strlkup_orig.dll, IPXWrapper beside the exe). DxWnd profile 1 (ini index 0)
// runs `nitro.exe -glide`. The Gold app and its prefix are never touched by this stub: every path below is derived
// from this bundle's own location, wineserver -k acts on this bundle's WINEPREFIX only, and the quit detection and the final
// kill see only processes whose image is this bundle's own Wine (ownProcs, s.8 of the record: 2026-10-22 fix of a boot
// loop that never saw "nitro.exe" and reaped every game after 120 s, and of a sweep that killed every Nitro app's game).
//
// Derived from i76-launch-stub.swift (same env, same quit detection, same bounded reap); differences: waits on
// nitro.exe, no savegame.dir healing (Nitro has no save files). Since 2026-10-26 (docs/records/MAC-NITRO-108-106-2026-10-26.md) it
// starts the same AutoHotkey remapper as the Gold app when the prefix has it (pad buttons / triggers / right stick, mouse 4 / 5).
// The arm64 build keeps Mach-O UUID 03B81E57-0956-3BBA-8D89-3C8EDF8713C4 (tools/mac-kit/build-stubs.sh).
// Build: swiftc -O -o Sikarugir i76-nitro-app-stub.swift
import Foundation
import CoreGraphics

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
let GAME = "nitro.exe"

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
        if !ownGameRunning(PFX, GAME) { break }
    }
    let myPid = ProcessInfo.processInfo.processIdentifier
    let otherStubs = pids(rx(A + "/Contents/MacOS/Sikarugir")).filter { $0 != myPid }
    if !otherStubs.isEmpty { return }                      // a relaunch of this app owns a new session
    killOwn(PFX)                                           // this prefix's processes only, never another app's game
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

// Input remapper, as the Gold stub: AutoHotkey inside this prefix turns the pad's XInput buttons / triggers / right stick and
// mouse buttons 4 / 5 into the keys input.map binds. Skipped unless the prefix has C:\AutoHotkey\AutoHotkeyU32.exe and
// i76-remap.ahk. #SingleInstance Force dedupes a relaunch; reap() ends it with the session (wineserver -k, killOwn).
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

var booted = false
for _ in 0..<120 {
    Thread.sleep(forTimeInterval: 1)
    if ownGameRunning(PFX, GAME) { booted = true; break }
    if !p.isRunning && ownProcs(PFX).isEmpty { break }
}
var sawTwo = false
var lowStreak = 0
while booted {
    Thread.sleep(forTimeInterval: 2)
    if !ownGameRunning(PFX, GAME) { break }
    let n = ownLargeWindows(PFX)
    if n >= 2 { sawTwo = true; lowStreak = 0 }
    else if sawTwo {
        lowStreak += 1
        if lowStreak >= 3 { break }
    }
}
reap(A)
