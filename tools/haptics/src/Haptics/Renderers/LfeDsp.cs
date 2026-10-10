using System;
using System.Collections.Generic;

namespace Haptics.Renderers
{
    // =====================================================================================================
    // Lifted UNCHANGED from tools/ffb/LfeSynth.ps1 (LfeCore + LfeSmoother, commit 560dcd2), so the WAV this
    // host writes is the signal ffb-lfe-live.ps1 streams. The only addition is the `extra` argument of Step:
    // chain-effect voices summed in before the filters (0 when there are none, which keeps the output
    // sample-identical to LfeSynth.ps1 - asserted by tests against ffb-lfe-probe.ps1's own WAVs).
    // The design rationale is in LfeSynth.ps1's comments.
    // =====================================================================================================
    public sealed class LfeCore
    {
        double engPh, roadPh, impPh, wpnPh, jitPh, carPh, noiseLp, noiseLp2, noiseLp3;
        double noiseLp4, noiseLp5, noiseLp6;
        double scrPh, scrRough, expPh;
        double lpA, lpB, lpC, hpA, hpB, hpPrevIn, hpPrevIn2;
        readonly double kLp, aHp, kN2;
        readonly Random rnd = new Random(1976);
        readonly int rate;
        readonly double jitter, impHz, wpnHz, carHz, compMax;
        public double ScrubHz = 62.0;
        public double ExplodeHz = 22.0;
        readonly double[] rHz, rRel;
        public double PeakAbs = 0; public long Limited = 0, Samples = 0;
        public double RawSum;
        public double Knee = 0.8;
        public int Tap = 2;

        public LfeCore(int rate, double jitter, double impHz, double wpnHz, double carHz,
                       double hpHz, double lpHz, double[] rHz, double[] rRel, double compMax,
                       double scrubHz, double explodeHz)
        {
            this.ScrubHz = scrubHz; this.ExplodeHz = explodeHz;
            this.rate = rate; this.jitter = jitter;
            this.impHz = impHz; this.wpnHz = wpnHz; this.carHz = carHz;
            this.rHz = rHz; this.rRel = rRel; this.compMax = compMax;
            kLp = 1.0 - Math.Exp(-2.0 * Math.PI * (lpHz * 1.35) / rate);
            kN2 = 1.0 - Math.Exp(-2.0 * Math.PI * 70.0 / rate);
            double rcHp = 1.0 / (2.0 * Math.PI * hpHz);
            aHp = rcHp / (rcHp + 1.0 / rate);
        }

        public double Comp(double hz)
        {
            if (rHz == null || rHz.Length < 2 || compMax <= 1.0) return 1.0;
            double rel;
            if (hz <= rHz[0]) rel = rRel[0];
            else if (hz >= rHz[rHz.Length - 1]) rel = rRel[rHz.Length - 1];
            else
            {
                int k = 0; while (k < rHz.Length - 2 && rHz[k + 1] < hz) k++;
                double lo = Math.Log(rHz[k]), hi = Math.Log(rHz[k + 1]);
                double u = (Math.Log(hz) - lo) / (hi - lo);
                rel = rRel[k] + (rRel[k + 1] - rRel[k]) * u;
            }
            const double floorRel = 0.08;
            if (rel <= 0.0) return 0.0;
            if (rel < floorRel) return (rel / floorRel) * Math.Min(1.0 / floorRel, compMax);
            double g = 1.0 / rel;
            return g > compMax ? compMax : g;
        }

        public double Limit(double v)
        {
            Samples++;
            double a = Math.Abs(v);
            if (a > PeakAbs) PeakAbs = a;
            if (a <= Knee) return v;
            Limited++;
            double room = 1.0 - Knee;
            return (v < 0 ? -1.0 : 1.0) * (Knee + room * Math.Tanh((a - Knee) / room));
        }

        public double Step(double engF, double engA, double roadF, double roadA,
                           double impA, double wpnA, double hvA, double scrA, double expA, double extra = 0.0)
        {
            jitPh += 2 * Math.PI * 0.7 / rate;
            double engFj = engF * (1.0 + jitter * Math.Sin(jitPh));
            engPh += 2 * Math.PI * engFj / rate;
            double sig = engA * Comp(engFj) * Math.Sin(engPh);
            sig += engA * 0.18 * Comp(engFj * 2) * Math.Sin(engPh * 2);

            double white = rnd.NextDouble() * 2.0 - 1.0;
            double kN = 1.0 - Math.Exp(-2.0 * Math.PI * roadF / rate);
            noiseLp += kN * (white - noiseLp);
            noiseLp2 += kN * (noiseLp - noiseLp2);
            noiseLp3 += kN * (noiseLp2 - noiseLp3);
            noiseLp4 += kN2 * (noiseLp3 - noiseLp4);
            noiseLp5 += kN2 * (noiseLp4 - noiseLp5);
            noiseLp6 += kN2 * (noiseLp5 - noiseLp6);
            roadPh += 2 * Math.PI * roadF / rate;
            sig += roadA * Comp(roadF) * (0.55 * noiseLp6 * 26.0 + 0.45 * Math.Sin(roadPh));

            impPh += 2 * Math.PI * impHz / rate;
            sig += impA * Comp(impHz) * Math.Sin(impPh);
            wpnPh += 2 * Math.PI * wpnHz / rate;
            sig += wpnA * Comp(wpnHz) * Math.Sin(wpnPh);

            carPh += 2 * Math.PI * carHz / rate;
            sig += hvA * Comp(carHz) * Math.Sin(carPh);

            if (expA > 0.0)
            {
                expPh += 2 * Math.PI * ExplodeHz / rate;
                sig += expA * Comp(ExplodeHz) * Math.Sin(expPh);
            }

            if (scrA > 0.0)
            {
                scrRough += 0.06 * ((rnd.NextDouble() * 2.0 - 1.0) - scrRough);
                scrPh += 2 * Math.PI * ScrubHz / rate;
                sig += scrA * Comp(ScrubHz) * Math.Sin(scrPh) * (0.65 + 0.35 * scrRough * 3.0);
            }

            if (extra != 0.0) sig += extra;   // chain-effect voices (haptics host addition)

            if (Tap == 0) { RawSum = sig; }
            double h1 = aHp * (hpA + sig - hpPrevIn); hpPrevIn = sig; hpA = h1;
            double h2 = aHp * (hpB + h1 - hpPrevIn2); hpPrevIn2 = h1; hpB = h2;
            lpA += kLp * (h2 - lpA);
            lpB += kLp * (lpA - lpB);
            lpC += kLp * (lpB - lpC);
            if (Tap == 0) return RawSum;
            if (Tap == 1) return h2;
            return lpC;
        }
    }

    public sealed class LfeSmoother
    {
        public double sEngF = 25, sEngA, sRoadF = 60, sRoadA, sImpA, sWpnA, sHvA, sScrA, sExpA;
        readonly double dImp, dWpn, dExp;
        readonly double kAmp, kFrq, kHv;
        public LfeSmoother(int rate)
        {
            kAmp = 1.0 - Math.Exp(-1.0 / (0.006 * rate));
            kFrq = 1.0 - Math.Exp(-1.0 / (0.025 * rate));
            kHv = 1.0 - Math.Exp(-1.0 / (0.040 * rate));
            dImp = Math.Exp(-1.0 / (0.130 * rate));
            dWpn = Math.Exp(-1.0 / (0.070 * rate));
            dExp = Math.Exp(-1.0 / (0.450 * rate));
        }
        public void Advance(double eF, double eA, double rF, double rA, double iA, double wA, double hA, double scA, double exA)
        {
            sEngA += kAmp * (eA - sEngA); sRoadA += kAmp * (rA - sRoadA);
            if (iA > sImpA) { sImpA = iA; } else { sImpA *= dImp; }
            if (wA > sWpnA) { sWpnA = wA; } else { sWpnA *= dWpn; }
            if (exA > sExpA) { sExpA = exA; } else { sExpA *= dExp; }
            sHvA += kHv * (hA - sHvA); sScrA += kAmp * (scA - sScrA);
            sEngF += kFrq * (eF - sEngF); sRoadF += kFrq * (rF - sRoadF);
        }
    }

    /// <summary>
    /// Chain-effect voices on the shaker: one sine per voice id at its own frequency, rig-compensated, with the same
    /// peak-hold-then-decay smoothing LfeSmoother gives the reference transients (so a 60 Hz parameter stream does not
    /// zipper). Voices that vanish decay out over their tail.
    /// </summary>
    public sealed class LfeVoiceBank
    {
        sealed class V { public double Ph, Amp, Hz, HzT, Target; public bool Seen; }
        readonly Dictionary<string, V> _v = new Dictionary<string, V>();
        readonly int _rate; readonly double _decay, _kFrq;
        public LfeVoiceBank(int rate, double tailSeconds = 0.10)
        {
            _rate = rate; _decay = Math.Exp(-1.0 / (tailSeconds * rate)); _kFrq = 1.0 - Math.Exp(-1.0 / (0.025 * rate));
        }
        public int Count => _v.Count;
        public void SetTargets(IEnumerable<Core.Voice> voices)
        {
            foreach (var x in _v.Values) { x.Seen = false; x.Target = 0; }
            foreach (var vo in voices)
            {
                if (vo.LfeAmp <= 0) continue;
                if (!_v.TryGetValue(vo.Id, out var v)) { v = new V { Hz = vo.LfeHz }; _v[vo.Id] = v; }
                v.Target = vo.LfeAmp; v.Seen = true; v.HzT = vo.LfeHz;
            }
        }
        public double Sample(LfeCore comp)
        {
            double s = 0;
            List<string> dead = null;
            foreach (var kv in _v)
            {
                var v = kv.Value;
                if (v.Target > v.Amp) v.Amp = v.Target; else v.Amp *= _decay;
                if (v.HzT > 0) v.Hz += _kFrq * (v.HzT - v.Hz);
                v.Ph += 2 * Math.PI * v.Hz / _rate;
                s += v.Amp * comp.Comp(v.Hz) * Math.Sin(v.Ph);
                if (!v.Seen && v.Amp < 1e-5) (dead ?? (dead = new List<string>())).Add(kv.Key);
            }
            if (dead != null) foreach (var k in dead) _v.Remove(k);
            return s;
        }
    }
}
