// Interstate '76 launch stub - installed AS the wrapper .app's main executable
// (Contents/MacOS/Sikarugir; original launcher kept as Sikarugir.orig).
//
// Double-click the .app -> straight into the game via `dxwnd.exe /R:1` (DxWnd wraps
// the software renderer into a big 4:3 window; our profile has Desktop coords +
// KeepAspectRatio + HideDesktop). /R:1 = run target #1 (1-based -> ini index 0).
//
// CRITICAL env we must set because we bypass the stock Sikarugir launcher:
//  - GStreamer plugin paths: Wine's winegstreamer decodes the game's in-mission MP3
//    music (music/10.mp3..) via these. WITHOUT them, MCI-MP3 open fails, the game
//    retries in a tight loop -> multi-second freezes -> stack overflow crash, AND no
//    in-mission music. (The stock launcher sets GST_PLUGIN_PATH; we must too.)
//  - DYLD includes GStreamer.framework libs so those plugins can be dlopen'd.
//  - WINEESYNC+WINEMSYNC: msync (esync-only pins every wine proc at 100% CPU on macOS).
//
// Launch wine as a CHILD Process, not execv - execv breaks winemac GUI activation
// under LaunchServices.
//
// CLOSE-FOR-REAL: we must reap when the GAME exits, not when dxwnd.exe exits - the
// DxWnd host stays resident after the game dies, so waiting on it never returns and
// the HideDesktop black backdrop window lingers (the "black wine window" that needed
// force-quit). So: wait for i76.exe to appear (boot), wait for it to vanish (quit or
// window-X via DxWnd's Terminate-on-close), then wineserver -k + sweep every process
// still referencing this bundle (dxwnd host, backdrop owner, winedevice, explorer).
// Build:  swiftc -O -o /tmp/stub i76-launch-stub.swift
import Foundation
import CoreGraphics

// Count large wine-owned windows on screen. During play there are TWO (the game's
// render window + DxWnd's full-desktop "hider" backdrop); on in-game EXIT the render
// window closes to the black hider (count drops to 1) while i76.exe often HANGS
// mid-shutdown - so process-exit alone never fires. Owner name + bounds are readable
// WITHOUT Screen Recording permission (window titles are not, so we key off size).
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
    // GStreamer: let winegstreamer find the bundled codecs (MP3 in-mission music)
    setenv("GST_PLUGIN_PATH", gv + "/lib/gstreamer-1.0", 1)
    setenv("GST_PLUGIN_SYSTEM_PATH_1_0", gv + "/lib/gstreamer-1.0", 1)
    setenv("GST_PLUGIN_SCANNER_1_0", gv + "/libexec/gstreamer-1.0/gst-plugin-scanner", 1)
    setenv("GST_REGISTRY_1_0", A + "/Contents/SharedSupport/prefix/gst-registry.bin", 1)
}

// pgrep/pkill -f patterns are EXTENDED REGEX - the app path's "(DxWnd)" parens
// are metacharacters, so raw paths silently match NOTHING (the sweep and the
// relaunch check were no-ops until 2026-07-14; wineserver -k happened to cover
// cleanup). Escape any literal string before using it as a pattern.
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

// Reap runs once - from the play-loop exit (game quit) OR the signal handler (app
// quit / cmd-Q). Guard against double-run.
var reaped = false
let reapLock = NSLock()
func reap(_ A: String) {
    reapLock.lock(); if reaped { reapLock.unlock(); return }; reaped = true; reapLock.unlock()
    // WATCHDOG: no wait below may hang the stub indefinitely. A wedged
    // `wineserver -k` did exactly that on 2026-07-14 - a 5h15m orphaned stub
    // that kept LaunchServices thinking the app was open, so the game wouldn't
    // relaunch ("not responding"). Guarantee this process dies within 30s no
    // matter which call blocks. asyncAfter runs on a background queue, so it
    // fires even if the main thread is stuck in a Process wait below.
    DispatchQueue.global().asyncAfter(deadline: .now() + 30) { Foundation.exit(0) }
    let k = Process()
    k.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wineserver")
    k.arguments = ["-k"]
    try? k.run()
    // Bound the -k wait: it can wedge on a wine proc stuck unkillable. Poll for
    // exit up to 12s, then terminate it and fall through to the pkill sweep,
    // which force-kills whatever -k couldn't. (Was: k.waitUntilExit() = ∞ block.)
    let kDeadline = Date().addingTimeInterval(12)
    while k.isRunning && Date() < kDeadline { Thread.sleep(forTimeInterval: 0.2) }
    if k.isRunning { k.terminate() }
    // wineserver -k can take a few seconds; POLL for the session to actually die
    // rather than bail early (the old bug: dxwnd mid-death read as "still up").
    for _ in 0..<8 {
        Thread.sleep(forTimeInterval: 1)
        if !running("dxwnd\\.exe") && !running("i76\\.exe") { break }
    }
    // Only skip the bundle sweep for a genuine RELAUNCH - i.e. a SECOND stub (new
    // Sikarugir process) is now managing a fresh session. dxwnd being slow to die is
    // NOT a relaunch. Sweep otherwise so nothing (dxwnd host, hider backdrop,
    // winedevice, explorer) is ever left on screen.
    let myPid = ProcessInfo.processInfo.processIdentifier
    let otherStubs = pids(rx(A + "/Contents/MacOS/Sikarugir")).filter { $0 != myPid }
    if !otherStubs.isEmpty { return }
    let s = Process()
    s.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    s.arguments = ["-9", "-f", rx(A + "/Contents/SharedSupport")]
    try? s.run(); s.waitUntilExit()
}

setupEnv(A)

// Reap on app-quit too (cmd-Q / Dock quit / LaunchServices logout sends SIGTERM;
// SIGINT for good measure). Without this, quitting the .app while the game runs
// would orphan the wine session + leave the window. DispatchSource handlers run on
// a queue (safe to spawn Process, unlike a raw C signal handler).
var signalSources: [DispatchSourceSignal] = []
for sig in [SIGTERM, SIGINT] {
    signal(sig, SIG_IGN)  // ignore default action; the source handles it
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .global())
    src.setEventHandler { reap(A); exit(0) }
    src.resume()
    // keep the source alive for the process lifetime
    signalSources.append(src)
}

let p = Process()
p.executableURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/wine/bin/wine")
p.arguments = ["C:\\dxwnd\\dxwnd.exe", "/R:1"]
p.currentDirectoryURL = URL(fileURLWithPath: A + "/Contents/SharedSupport/prefix/drive_c/dxwnd")
try! p.run()

// Input remapper: AutoHotkey inside the prefix turns mouse buttons 4/5 + wheel
// into keys the engine can bind (it only knows three buttons). Optional -
// skipped silently unless setup-input-remapper.sh installed it. #SingleInstance
// Force in the script dedupes on relaunch; reap() kills it with the session
// (wineserver -k + the SharedSupport pkill sweep both cover it).
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
_ = ahkProc  // keep a reference for the process lifetime

// Boot phase: give wine + DxWnd + the game up to 2 min to get i76.exe running.
var booted = false
for _ in 0..<120 {
    Thread.sleep(forTimeInterval: 1)
    if running("i76\\.exe") { booted = true; break }
    if !p.isRunning && !running("dxwnd\\.exe") { break }  // launch failed outright
}
// Play phase: reap when the game is DONE by either signal -
//  (a) i76.exe fully exits (clean quit), OR
//  (b) the game's render window vanishes (leaving only the black "hider") while
//      i76.exe hangs on shutdown - the "EXIT -> black screen -> force-quit" bug.
// (b) is why cmd-Q "just went to the menu": the window is owned by winemac's "wine"
// app, not us, so our SIGTERM never fired - now we watch the window directly.
var sawTwo = false
var lowStreak = 0
while booted {
    Thread.sleep(forTimeInterval: 2)
    if !running("i76\\.exe") { break }                 // (a) process gone
    let n = largeWineWindows()
    if n >= 2 { sawTwo = true; lowStreak = 0 }
    else if sawTwo {                                    // (b) render window closed
        lowStreak += 1
        if lowStreak >= 3 { break }                     // ~6s sustained -> reap the hung session
    }
}
reap(A)
