// cur: print the macOS pointer location; cur X Y warps it there (CGWarpMouseCursorPosition: no Accessibility needed,
// works over SSH on an unlocked Mac). Build on a Mac: swiftc -O -target arm64-apple-macos11.0 cur.swift -o cur
import CoreGraphics
import Foundation
let a = CommandLine.arguments
print("before", CGEvent(source: nil)?.location ?? .zero)
if a.count >= 3, let x = Double(a[1]), let y = Double(a[2]) { let r = CGWarpMouseCursorPosition(CGPoint(x: x, y: y)); print("warp rc", r.rawValue) ; usleep(200000) }
print("after", CGEvent(source: nil)?.location ?? .zero)
