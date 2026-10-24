// pidpath: print pid, executable path (proc_pidpath) and command line of every process whose command contains ARG.
// nitro-mac lane 2026-10-22: which test tells a Wine process's app (the launch stubs' own-process rule).
import Darwin
import Foundation
let want = CommandLine.arguments.count > 1 ? CommandLine.arguments[1].lowercased() : ".exe"
let t = Process(); t.executableURL = URL(fileURLWithPath: "/bin/ps"); t.arguments = ["-A", "-ww", "-o", "pid=,command="]
let pipe = Pipe(); t.standardOutput = pipe; try! t.run()
let data = pipe.fileHandleForReading.readDataToEndOfFile(); t.waitUntilExit()
for line in (String(data: data, encoding: .utf8) ?? "").split(separator: "\n") {
    let s = line.trimmingCharacters(in: .whitespaces)
    guard s.lowercased().contains(want), let sp = s.firstIndex(of: " "), let pid = Int32(s[..<sp]) else { continue }
    var buf = [CChar](repeating: 0, count: 4096)
    let n = proc_pidpath(pid, &buf, UInt32(buf.count))
    print(pid, n > 0 ? String(cString: buf) : "?", "|", s[s.index(after: sp)...])
}
