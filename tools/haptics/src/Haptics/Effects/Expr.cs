using System;
using System.Collections.Generic;
using System.Globalization;

namespace Haptics.Effects
{
    /// <summary>
    /// The tiny expression language effect files use for "level" and "channel":
    /// numbers, variable names (frame channels or event fields), + - * / ( ), unary minus,
    /// and clamp(x,lo,hi) min(a,b) max(a,b) abs(x) sqrt(x) pow(a,b). Compiled once into a delegate.
    /// An unknown variable evaluates to 0 and is listed in <see cref="Variables"/> so the linter can flag it.
    /// </summary>
    public sealed class Expr
    {
        public readonly string Text;
        public readonly HashSet<string> Variables = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        readonly Func<Func<string, double>, double> _f;

        public Expr(string text)
        {
            Text = text ?? "0";
            _pos = 0; _s = Text;
            _f = ParseExpr();
            SkipWs();
            if (_pos != _s.Length) throw new FormatException("unexpected '" + _s.Substring(_pos) + "' in expression '" + Text + "'");
        }

        public double Eval(Func<string, double> vars)
        {
            double v = _f(vars);
            return double.IsNaN(v) || double.IsInfinity(v) ? 0.0 : v;
        }

        public override string ToString() => Text;

        // ---- recursive descent ----
        string _s; int _pos;
        void SkipWs() { while (_pos < _s.Length && char.IsWhiteSpace(_s[_pos])) _pos++; }
        bool Eat(char c) { SkipWs(); if (_pos < _s.Length && _s[_pos] == c) { _pos++; return true; } return false; }

        Func<Func<string, double>, double> ParseExpr()
        {
            var a = ParseTerm();
            while (true)
            {
                if (Eat('+')) { var l = a; var r = ParseTerm(); a = v => l(v) + r(v); }
                else if (Eat('-')) { var l = a; var r = ParseTerm(); a = v => l(v) - r(v); }
                else return a;
            }
        }
        Func<Func<string, double>, double> ParseTerm()
        {
            var a = ParseUnary();
            while (true)
            {
                if (Eat('*')) { var l = a; var r = ParseUnary(); a = v => l(v) * r(v); }
                else if (Eat('/')) { var l = a; var r = ParseUnary(); a = v => { double d = r(v); return d == 0 ? 0.0 : l(v) / d; }; }
                else return a;
            }
        }
        Func<Func<string, double>, double> ParseUnary()
        {
            if (Eat('-')) { var x = ParseUnary(); return v => -x(v); }
            if (Eat('+')) return ParseUnary();
            return ParsePrimary();
        }
        Func<Func<string, double>, double> ParsePrimary()
        {
            SkipWs();
            if (Eat('(')) { var e = ParseExpr(); if (!Eat(')')) throw new FormatException("missing ')' in '" + Text + "'"); return e; }
            int start = _pos;
            if (_pos < _s.Length && (char.IsDigit(_s[_pos]) || _s[_pos] == '.'))
            {
                while (_pos < _s.Length && (char.IsDigit(_s[_pos]) || _s[_pos] == '.' || _s[_pos] == 'e' || _s[_pos] == 'E' ||
                       ((_s[_pos] == '-' || _s[_pos] == '+') && (_s[_pos - 1] == 'e' || _s[_pos - 1] == 'E')))) _pos++;
                double num = double.Parse(_s.Substring(start, _pos - start), CultureInfo.InvariantCulture);
                return v => num;
            }
            while (_pos < _s.Length && (char.IsLetterOrDigit(_s[_pos]) || _s[_pos] == '_' || _s[_pos] == '.')) _pos++;
            if (_pos == start) throw new FormatException("expected a value at '" + _s.Substring(start) + "' in '" + Text + "'");
            string id = _s.Substring(start, _pos - start);
            if (Eat('('))
            {
                var args = new List<Func<Func<string, double>, double>>();
                if (!Eat(')'))
                {
                    do args.Add(ParseExpr()); while (Eat(','));
                    if (!Eat(')')) throw new FormatException("missing ')' after " + id + "( in '" + Text + "'");
                }
                return Fn(id.ToLowerInvariant(), args);
            }
            Variables.Add(id);
            return v => v(id);
        }
        Func<Func<string, double>, double> Fn(string id, List<Func<Func<string, double>, double>> a)
        {
            void N(int n) { if (a.Count != n) throw new FormatException(id + " takes " + n + " argument(s) in '" + Text + "'"); }
            switch (id)
            {
                case "clamp": N(3); return v => Math.Max(a[1](v), Math.Min(a[2](v), a[0](v)));
                case "min": N(2); return v => Math.Min(a[0](v), a[1](v));
                case "max": N(2); return v => Math.Max(a[0](v), a[1](v));
                case "abs": N(1); return v => Math.Abs(a[0](v));
                case "sqrt": N(1); return v => Math.Sqrt(Math.Max(0, a[0](v)));
                case "pow": N(2); return v => Math.Pow(a[0](v), a[1](v));
                default: throw new FormatException("unknown function " + id + " in '" + Text + "'");
            }
        }
    }
}
