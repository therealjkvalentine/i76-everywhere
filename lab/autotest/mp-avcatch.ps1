# avcatch.ps1 -TargetPid N -Out file : attach as a debugger, on the first access violation dump the WOW64 context and 0x800 bytes of stack, then detach.
param([int]$TargetPid, [string]$Out, [int]$Seconds = 120)
Add-Type @"
using System; using System.IO; using System.Runtime.InteropServices; using System.Text;
public static class AvCatch {
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool DebugActiveProcess(int pid);
  [DllImport("kernel32.dll")] static extern bool DebugActiveProcessStop(int pid);
  [DllImport("kernel32.dll")] static extern bool DebugSetProcessKillOnExit(bool k);
  [DllImport("kernel32.dll")] static extern bool WaitForDebugEvent(byte[] ev, int ms);
  [DllImport("kernel32.dll")] static extern bool ContinueDebugEvent(int pid, int tid, uint status);
  [DllImport("kernel32.dll")] static extern IntPtr OpenThread(int access, bool inherit, int tid);
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(int access, bool inherit, int pid);
  [DllImport("kernel32.dll")] static extern bool Wow64GetThreadContext(IntPtr h, byte[] ctx);
  [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  public static string Run(int pid, int seconds) {
    var sb = new StringBuilder();
    if (!DebugActiveProcess(pid)) return "DebugActiveProcess failed " + Marshal.GetLastWin32Error();
    DebugSetProcessKillOnExit(false);
    var ev = new byte[4096]; var until = DateTime.Now.AddSeconds(seconds);
    while (DateTime.Now < until) {
      if (!WaitForDebugEvent(ev, 500)) continue;
      int code = BitConverter.ToInt32(ev, 0), p = BitConverter.ToInt32(ev, 4), t = BitConverter.ToInt32(ev, 8);
      uint cont = 0x00010002; // DBG_CONTINUE
      if (code == 1) {
        uint ex = BitConverter.ToUInt32(ev, 16); long addr = BitConverter.ToInt64(ev, 32);
        if (ex == 0xC0000005) {
          sb.AppendFormat("AV at 0x{0:x} tid {1}\r\n", addr, t);
          IntPtr th = OpenThread(0x1FFFFF, false, t), ph = OpenProcess(0x0410, false, pid);
          var ctx = new byte[716]; BitConverter.GetBytes(0x10007).CopyTo(ctx, 0);
          if (Wow64GetThreadContext(th, ctx)) {
            uint eip = BitConverter.ToUInt32(ctx, 0xB8), esp = BitConverter.ToUInt32(ctx, 0xC4), ebp = BitConverter.ToUInt32(ctx, 0xB4);
            sb.AppendFormat("eip {0:x8} esp {1:x8} ebp {2:x8} eax {3:x8} ebx {4:x8} ecx {5:x8} edx {6:x8} esi {7:x8} edi {8:x8}\r\n", eip, esp, ebp,
              BitConverter.ToUInt32(ctx, 0xB0), BitConverter.ToUInt32(ctx, 0xA4), BitConverter.ToUInt32(ctx, 0xAC), BitConverter.ToUInt32(ctx, 0xA8), BitConverter.ToUInt32(ctx, 0xA0), BitConverter.ToUInt32(ctx, 0x9C));
            var st = new byte[0x800]; IntPtr r;
            if (ReadProcessMemory(ph, new IntPtr(esp), st, st.Length, out r))
              for (int i = 0; i < st.Length; i += 4) { if (i % 32 == 0) sb.AppendFormat("\r\n{0:x8}:", esp + i); sb.AppendFormat(" {0:x8}", BitConverter.ToUInt32(st, i)); }
            sb.Append("\r\n");
            // strings the stack words point at
            for (int i = 0; i < st.Length; i += 4) { uint v = BitConverter.ToUInt32(st, i); if (v < 0x10000) continue; var s = new byte[48];
              if (ReadProcessMemory(ph, new IntPtr(v), s, 48, out r)) { int n = 0; while (n < 48 && s[n] >= 0x20 && s[n] < 0x7f) n++; if (n >= 4) sb.AppendFormat("  [esp+0x{0:x}] {1:x8} -> '{2}'\r\n", i, v, Encoding.ASCII.GetString(s, 0, n)); } }
          } else sb.Append("Wow64GetThreadContext failed\r\n");
          CloseHandle(th); CloseHandle(ph);
          ContinueDebugEvent(p, t, 0x80010001); DebugActiveProcessStop(pid); return sb.ToString();
        }
        if (ex != 0x80000003 && ex != 0x4000001F) cont = 0x80010001; // not handled
      }
      if (code == 5) { sb.Append("process exited\r\n"); ContinueDebugEvent(p, t, cont); return sb.ToString(); }
      ContinueDebugEvent(p, t, cont);
    }
    DebugActiveProcessStop(pid); sb.Append("timeout, detached\r\n"); return sb.ToString();
  }
}
"@
$r = [AvCatch]::Run($TargetPid, $Seconds)
Set-Content $Out $r
