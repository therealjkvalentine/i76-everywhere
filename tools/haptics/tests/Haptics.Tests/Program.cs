using System;
using System.Linq;
using Haptics.Core;

namespace Haptics.Tests
{
    static class Program
    {
        static int Main(string[] args)
        {
            T.Verbose = args.Contains("-v");
            string only = args.FirstOrDefault(a => !a.StartsWith("-"));
            bool Want(string s) => only == null || s.IndexOf(only, StringComparison.OrdinalIgnoreCase) >= 0;

            if (Want("golden")) GoldenTests.Run(Tune.Defaults, "Tune.Defaults oracle");
            if (Want("core")) CoreTests.Run();
            if (Want("transport")) TransportTests.Run();
            if (Want("renderer")) RendererTests.Run();
            if (Want("motion")) MotionTests.Run();

            Console.WriteLine();
            Console.ForegroundColor = T.Fail == 0 ? ConsoleColor.Green : ConsoleColor.Red;
            Console.WriteLine("=== {0} passed, {1} failed, {2} skipped ===", T.Pass, T.Fail, T.Skip);
            Console.ResetColor();
            foreach (var f in T.Failures) Console.WriteLine("  failed: " + f);
            return T.Fail == 0 ? 0 : 1;
        }
    }
}
