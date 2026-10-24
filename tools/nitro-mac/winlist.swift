// winlist: print every Wine-owned window macOS reports (CGWindowListCopyWindowInfo, .optionAll): owner pid, owner name,
// bounds, on-screen flag, layer. No Screen Recording permission needed (titles are not read). nitro-mac lane 2026-10-22,
// to see what the launch stubs' quit detection sees. Usage: winlist [seconds [interval]]
// Build: swiftc -O -target arm64-apple-macos11.0 winlist.swift -o winlist
import CoreGraphics
import Foundation
let a = CommandLine.arguments
let secs = a.count > 1 ? Double(a[1]) ?? 0 : 0, step = a.count > 2 ? Double(a[2]) ?? 2 : 2
let t0 = Date()
repeat {
    var rows: [String] = []
    if let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] {
        for w in list {
            let owner = w[kCGWindowOwnerName as String] as? String ?? ""
            guard owner.lowercased().contains("wine") else { continue }
            let pid = w[kCGWindowOwnerPID as String] as? Int ?? -1
            let b = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
            let on = (w[kCGWindowIsOnscreen as String] as? Bool) ?? false
            let layer = w[kCGWindowLayer as String] as? Int ?? 0
            rows.append("pid \(pid) \(owner) \(Int(b["X"] ?? 0)),\(Int(b["Y"] ?? 0)) \(Int(b["Width"] ?? 0))x\(Int(b["Height"] ?? 0)) on \(on ? 1 : 0) layer \(layer)")
        }
    } else { rows.append("CGWindowListCopyWindowInfo returned nil") }
    print(String(format: "t+%.0f s: %d wine window(s)", Date().timeIntervalSince(t0), rows.count))
    for r in rows { print("  " + r) }
    fflush(stdout)
    if secs > 0 { Thread.sleep(forTimeInterval: step) }
} while Date().timeIntervalSince(t0) < secs
