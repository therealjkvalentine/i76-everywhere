using System;
using System.Collections.Generic;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// Motion.Cues (docs/MOTION-OUTPUT.md 4.1): event spikes, kept OUT of the physics channels (i76motion cue_surge / cue_sway /
    /// cue_heave) so a consumer can scale or drop them. Each cue is a body-frame vector with an exponential decay from the
    /// moment it was raised, evaluated at the output tick time (never late by a physics step). Overlapping cues combine
    /// as the per-axis signed maximum, never the sum (cue budget "max"); impact-class cues (IMPACT events and the a_diff
    /// residual) are rate-limited to one per min_gap_ms; every cue is capped at cue_max.
    ///
    ///  IMPACT (player only): body(impact vector) unit x min(hp_lost / 60, 1) x impact_peak x impact_gain, tau impact_tau_ms;
    ///          source class 0x33 (ordnance) at half gain.
    ///  a_diff residual: (dv/dt across the step) - (integrator accel), above impulse_threshold, x impulse_gain (the wall
    ///          hits / car hits / kerbs the integrator vector omits); not on takeoff / landing steps.
    ///  LANDING: heave + landing_k x |v_y before touchdown|, tau landing_tau_ms.
    ///  EXPLOSION: heave + explosion_gain / max(d, explosion_min_dist)^2 (capped), plus a horizontal push away from the
    ///          blast of explosion_push x that, tau explosion_tau_ms.
    ///  SHOT: surge - shot_recoil x rounds (default 0 = off).
    /// </summary>
    public sealed class Cues
    {
        sealed class Cue { public double T0, S, W, H, Tau; public string Kind; }
        readonly List<Cue> _active = new List<Cue>();
        readonly MotionParams P;
        double _lastImpact = double.NegativeInfinity;
        public int Raised, Dropped;
        public readonly Dictionary<string, int> ByKind = new Dictionary<string, int>();

        public Cues(MotionParams p) { P = p; }

        void Add(string kind, double t0, double s, double w, double h, double tauMs, bool impactClass)
        {
            double mag = Math.Sqrt(s * s + w * w + h * h);
            if (!(mag > 1e-9)) return;
            if (impactClass)
            {
                if (t0 - _lastImpact < P.MinGapMs / 1000.0 - 1e-9) { Dropped++; return; }
                _lastImpact = t0;
            }
            if (mag > P.CueMax) { double k = P.CueMax / mag; s *= k; w *= k; h *= k; }
            _active.Add(new Cue { T0 = t0, S = s, W = w, H = h, Tau = Math.Max(1e-3, tauMs / 1000.0), Kind = kind });
            Raised++; ByKind[kind] = (ByKind.TryGetValue(kind, out var n) ? n : 0) + 1;
        }

        static double Len(double x, double y, double z) => Math.Sqrt(x * x + y * y + z * z);

        /// <summary>Events that arrived at motion time t, with the newest physics state for orientation / position.</summary>
        public void OnEvents(IList<HapticEvent> evs, double t, PhysicsSample s)
        {
            if (evs == null || s == null) return;
            // collect impact-class candidates of this instant first, so the budget keeps the strongest of them (max, not first)
            Cue best = null; double bestMag = 0;
            foreach (var e in evs)
            {
                switch (e.Type)
                {
                    case "IMPACT":
                    {
                        if (e["is_player"] < 0.5) break;
                        double x = e["impact_x"], y = e["impact_y"], z = e["impact_z"];
                        double level = Math.Min(Math.Max(e["hp_lost"], 0) / 60.0, 1.0) * P.ImpactPeak * P.ImpactGain;
                        if ((int)e["source_class"] == 0x33) level *= 0.5;
                        double m = Len(x, y, z);
                        double bs, bw, bh;
                        if (m > 1e-6) { var b = s.ToBody(x / m, y / m, z / m); bw = b.r * level; bh = b.u * level; bs = b.f * level; }
                        else { bs = -level; bw = bh = 0; }            // no direction: a jolt against travel
                        double mag = Len(bs, bw, bh);
                        if (mag > bestMag) { bestMag = mag; best = new Cue { S = bs, W = bw, H = bh, Tau = P.ImpactTauMs, Kind = "impact" }; }
                        break;
                    }
                    case "EXPLOSION":
                    {
                        double d = e["dist"];
                        if (d < 0) break;
                        double heave = P.ExplosionGain / Math.Pow(Math.Max(d, P.ExplosionMinDist), 2);
                        heave = Math.Min(heave, P.CueMax);
                        double dx = s.PosWorld[0] - e["x"], dz = s.PosWorld[2] - e["z"], dm = Math.Sqrt(dx * dx + dz * dz);
                        double ps = 0, pw = 0;
                        if (dm > 1e-6) { var b = s.ToBody(dx / dm, 0, dz / dm); pw = b.r * heave * P.ExplosionPush; ps = b.f * heave * P.ExplosionPush; }
                        Add("explosion", t, ps, pw, heave, P.ExplosionTauMs, false);
                        break;
                    }
                    case "SHOT":
                        if (P.ShotRecoil > 0) Add("shot", t, -P.ShotRecoil * Math.Max(1, e["rounds"]), 0, 0, P.ShotTauMs, false);
                        break;
                }
            }
            if (best != null) Add(best.Kind, t, best.S, best.W, best.H, best.Tau, true);
        }

        /// <summary>A new physics state: landing cue and the a_diff residual impulse.</summary>
        public void OnPhysics(PhysicsSample s, double t, string accelSource)
        {
            if (s.LandingEdge)
            {
                // LandingVy = the previous physics state's world vertical velocity (set by MotionCore before this call)
                double vy = Math.Abs(LandingVy);
                if (vy > 1e-6) Add("landing", t, 0, 0, P.LandingK * vy, P.LandingTauMs, false);
                return;
            }
            if (s.TakeoffEdge || s.Airborne) return;
            if (accelSource == "differentiated") return;     // the impulse is already in the steady channel
            double rs = s.ADiffSurge - s.Surge, rw = s.ADiffSway - s.Sway, rh = s.ADiffHeave - s.Heave;
            double m = Len(rs, rw, rh);
            if (m > P.ImpulseThreshold) Add("impulse", t, rs * P.ImpulseGain, rw * P.ImpulseGain, rh * P.ImpulseGain, P.ImpactTauMs, true);
        }

        public double LandingVy;

        /// <summary>The combined cue vector at time t (per-axis signed max), and whether any cue is live.</summary>
        public (double s, double w, double h, bool any) At(double t)
        {
            double S = 0, W = 0, H = 0; bool any = false;
            for (int i = _active.Count - 1; i >= 0; i--)
            {
                var c = _active[i];
                double age = t - c.T0;
                if (age < 0) continue;
                if (age > 6 * c.Tau) { _active.RemoveAt(i); continue; }
                double k = Math.Exp(-age / c.Tau);
                if (Math.Abs(c.S * k) > Math.Abs(S)) S = c.S * k;
                if (Math.Abs(c.W * k) > Math.Abs(W)) W = c.W * k;
                if (Math.Abs(c.H * k) > Math.Abs(H)) H = c.H * k;
                any = true;
            }
            return (S, W, H, any);
        }

        public void Clear() { _active.Clear(); }
    }
}
