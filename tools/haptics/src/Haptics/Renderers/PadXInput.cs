using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using Haptics.Core;
using Haptics.Effects;

namespace Haptics.Renderers
{
    /// <summary>
    /// Pad.XInput: two ERM motors from the bus. Left = heavy / low (weight, body, impacts), right = light / high
    /// (texture, scrub, judder, weapon, ticks) - the texture-vs-weight split of HAPTICS-ARCHITECTURE 6.3 (the pad's
    /// right ERM is the only Pacinian-band actuator in the rig). Every effect file says what it sends to which motor
    /// ("routing.pad" taps); the legacy taps reproduce Mix-RenderPad's coefficients.
    ///
    /// mode "max" (default, SIM-RUMBLE-RESEARCH Part E): per-motor MAX of all taps, a new peak is held for at least
    /// min_pulse_ms (ERM spin-up 20-30 ms; "longest one-shot wins"), then the ERM dead-zone lift
    /// out = deadzone + level x (1 - deadzone) for anything above silence_below. One SetState per change.
    /// mode "sum": Mix-RenderPad exactly (sum, clamp to 1, no lift) plus chain voices, for A/B against the old mixer.
    /// File sink: CSV (t, L, R, xinput L, xinput R). Live (--live): XInputSetState on the rig's slot.
    /// </summary>
    public sealed class PadXInput : IRenderer
    {
        public string Type => "Pad.XInput";
        RendererContext _ctx;
        StreamWriter _csv;
        string _mode = "max";
        double _dead = 0.30, _minPulse = 40, _silence = 0.02;
        readonly List<(char motor, double gain, string from)> _taps = new List<(char, double, string)>();
        double _holdL, _holdR, _holdLt = -1, _holdRt = -1;
        ushort _lastL = 0xffff, _lastR = 0xffff;
        int _slot; bool _live;
        public int Writes, Frames; public double PeakL, PeakR;
        public string CsvPath;
        public (double L, double R) Last;

        [StructLayout(LayoutKind.Sequential)] struct XINPUT_VIBRATION { public ushort wLeftMotorSpeed, wRightMotorSpeed; }
        [DllImport("xinput1_4.dll")] static extern uint XInputSetState(uint dwUserIndex, ref XINPUT_VIBRATION v);

        public void Open(RendererContext ctx)
        {
            _ctx = ctx;
            _mode = ctx.Str("mode") ?? "max";
            _dead = ctx.Num("deadzone", 0.30); _minPulse = ctx.Num("min_pulse_ms", 40); _silence = ctx.Num("silence_below", 0.02);
            _slot = (int)ctx.Num("slot", 0);
            if (ctx.Effects != null)
                foreach (var e in ctx.Effects.Effects)
                    if (e.IsLegacy && e.Enabled)
                        foreach (var p in e.Pad) _taps.Add((p.Motor, p.Gain, p.From));
            _live = ctx.Live;
            if (ctx.OutDir != null)
            {
                CsvPath = Path.Combine(ctx.OutDir, ctx.Tag + ".pad.csv");
                Directory.CreateDirectory(ctx.OutDir);
                _csv = new StreamWriter(CsvPath);
                _csv.WriteLine("t,L,R,xinput_L,xinput_R,mode");
            }
        }

        public static double Signal(Bus b, string from)
        {
            switch (from)
            {
                case "bus.steady": return Math.Abs(b.Steady);
                case "lfe.engine_amp": return b.Lfe.EngineAmp;
                case "lfe.road_amp": return b.Lfe.RoadAmp;
                case "transient.impact": return Math.Abs(b.TransientImpact);
                case "transient.weapon": return Math.Abs(b.TransientWeapon);
                case "transient.shift": return Math.Abs(b.TransientShift);
                case "tactile.texture": return b.Tactile[0].Amp;
                case "tactile.scrub": return b.Tactile[1].Amp;
                case "tactile.judder": return b.Tactile[2].Amp;
                default: return 0;
            }
        }

        public (double L, double R) Mix(CoreStep s)
        {
            var b = s.Bus;
            double L = 0, R = 0;
            if (_mode == "sum")
            {
                var leg = ReferenceMixer.RenderPadLegacy(b);
                L = leg.Left; R = leg.Right;
                foreach (var v in b.Voices) { L += v.PadL; R += v.PadR; }
                return (Math.Round(Math.Min(1, L), 4), Math.Round(Math.Min(1, R), 4));
            }
            foreach (var t in _taps)
            {
                double x = t.gain * Signal(b, t.from);
                if (t.motor == 'L') L = Math.Max(L, x); else R = Math.Max(R, x);
            }
            foreach (var v in b.Voices) { L = Math.Max(L, v.PadL); R = Math.Max(R, v.PadR); }
            L = Math.Min(1, L); R = Math.Min(1, R);
            // minimum pulse: a new peak is held min_pulse_ms so a 1-frame spike still spins the ERM up
            Hold(ref L, ref _holdL, ref _holdLt, s.T); Hold(ref R, ref _holdR, ref _holdRt, s.T);
            return (Lift(L), Lift(R));
        }

        /// <summary>A rise starts a hold of the new peak for min_pulse_ms; below the held peak inside the window the peak is kept; outside it the input passes.</summary>
        void Hold(ref double x, ref double held, ref double since, double t)
        {
            bool inHold = since >= 0 && (t - since) * 1000.0 < _minPulse;
            if (inHold) { if (x > held) { held = x; since = t; } else x = held; }
            else if (x > held && x > 0) { held = x; since = t; }      // a rise: hold this peak
            else held = x;                                            // window over: follow the signal down
        }

        double Lift(double x) => x < _silence ? 0.0 : _dead + x * (1.0 - _dead);

        public void Render(CoreStep s)
        {
            var (L, R) = Mix(s);
            Last = (L, R); Frames++;
            PeakL = Math.Max(PeakL, L); PeakR = Math.Max(PeakR, R);
            ushort l16 = (ushort)Math.Round(L * 65535), r16 = (ushort)Math.Round(R * 65535);
            _csv?.WriteLine(string.Format(CultureInfo.InvariantCulture, "{0:0.####},{1:0.####},{2:0.####},{3},{4},{5}", s.T, L, R, l16, r16, _mode));
            if (l16 != _lastL || r16 != _lastR)
            {
                Writes++;
                if (_live) { var v = new XINPUT_VIBRATION { wLeftMotorSpeed = l16, wRightMotorSpeed = r16 }; XInputSetState((uint)_slot, ref v); }
                _lastL = l16; _lastR = r16;
            }
        }

        public void Close()
        {
            if (_live) { var v = new XINPUT_VIBRATION(); try { XInputSetState((uint)_slot, ref v); } catch { } }
            _csv?.Dispose(); _csv = null;
        }
        public string Summary() => string.Format(CultureInfo.InvariantCulture, "Pad.XInput ({0}): {1} updates, {2} SetState, peak L {3:0.00} R {4:0.00} -> {5}",
            _mode, Frames, Writes, PeakL, PeakR, _live ? "XInput slot " + _slot : CsvPath);
        public void Dispose() => Close();
    }
}
