using System;
using System.Collections.Generic;
using System.IO;

namespace Haptics.Tests
{
    /// <summary>Minimal assertion harness: PASS/FAIL lines and a total, like tools/ffb/ffb-mixer-test.ps1.</summary>
    static class T
    {
        public static int Pass, Fail, Skip;
        public static readonly List<string> Failures = new List<string>();

        public static void Section(string name)
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine();
            Console.WriteLine("=== " + name + " ===");
            Console.ResetColor();
        }

        public static bool Check(string name, bool cond, string detail = "")
        {
            if (cond)
            {
                Pass++;
                Console.ForegroundColor = ConsoleColor.Green; Console.Write("  PASS  "); Console.ResetColor();
                Console.WriteLine(name + (detail.Length > 0 && Verbose ? "  (" + detail + ")" : ""));
            }
            else
            {
                Fail++;
                Failures.Add(name + (detail.Length > 0 ? "  (" + detail + ")" : ""));
                Console.ForegroundColor = ConsoleColor.Red; Console.Write("  FAIL  "); Console.ResetColor();
                Console.WriteLine(name + (detail.Length > 0 ? "  (" + detail + ")" : ""));
            }
            return cond;
        }

        public static void Skipped(string name, string why)
        {
            Skip++;
            Console.ForegroundColor = ConsoleColor.Yellow; Console.Write("  SKIP  "); Console.ResetColor();
            Console.WriteLine(name + "  (" + why + ")");
        }

        public static bool Verbose;

        public static string HapticsRoot
        {
            get
            {
                var d = new DirectoryInfo(AppContext.BaseDirectory);
                while (d != null && !File.Exists(Path.Combine(d.FullName, "haptics.ps1"))) d = d.Parent;
                if (d == null) throw new Exception("cannot find tools/haptics (haptics.ps1) above " + AppContext.BaseDirectory);
                return d.FullName;
            }
        }

        public static string TempDir(string name)
        {
            var p = Path.Combine(HapticsRoot, "tests", "out", name);
            Directory.CreateDirectory(p);
            return p;
        }
    }
}
