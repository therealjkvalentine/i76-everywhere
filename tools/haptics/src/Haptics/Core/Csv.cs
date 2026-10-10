using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;

namespace Haptics.Core
{
    /// <summary>Plain comma-separated tables (no quoting: none of the repo's telemetry CSVs use it).</summary>
    public sealed class CsvTable
    {
        public string[] Header;
        public readonly List<string[]> Rows = new List<string[]>();
        readonly Dictionary<string, int> _ix = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        public static CsvTable Load(string path)
        {
            var t = new CsvTable();
            using (var r = new StreamReader(path))
            {
                string line = r.ReadLine();
                if (line == null) throw new InvalidDataException("empty CSV " + path);
                t.Header = line.TrimStart('﻿').Split(',');
                for (int i = 0; i < t.Header.Length; i++) t._ix[t.Header[i].Trim()] = i;
                while ((line = r.ReadLine()) != null)
                {
                    if (line.Length == 0) continue;
                    t.Rows.Add(line.Split(','));
                }
            }
            return t;
        }

        public bool Has(string col) => _ix.ContainsKey(col);
        public int Col(string col) => _ix.TryGetValue(col, out var i) ? i : -1;

        public string S(int row, string col)
        {
            int i = Col(col);
            if (i < 0 || i >= Rows[row].Length) return "";
            return Rows[row][i];
        }
        public double D(int row, string col, double dflt = 0.0)
        {
            var s = S(row, col);
            return s.Length == 0 ? dflt : double.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture);
        }
        public double? N(int row, string col)
        {
            var s = S(row, col);
            return s.Length == 0 ? (double?)null : double.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture);
        }
    }

    public static class Fmt
    {
        public static string R(double d) => d.ToString("R", CultureInfo.InvariantCulture);
        public static string G(double d, string f = "0.####") => d.ToString(f, CultureInfo.InvariantCulture);
    }
}
