using System;
using System.Collections.Generic;
using System.Linq;
using Haptics.Core;

namespace Haptics.Transport
{
    /// <summary>One scripted SOUND_START (and optional SOUND_STOP) for <see cref="SyntheticSound"/>.</summary>
    public sealed class SoundCue
    {
        public string Name;
        public double At, StopAt = -1;       // seconds; StopAt &lt; 0 = no SOUND_STOP
        public double Hz = 11025, Vol = 100;
        public int Mode;                      // 0 one-shot, 1 loop, 2 sustained loop
        public bool Player;
        public double Dist = -1;              // metres along +x from the player; &lt; 0 = a 2D sound (no position)
        public int Voice;                     // voice address (pairs START with STOP); 0 = auto
        public int StopReason = 1;
    }

    /// <summary>
    /// Scripted v3 sessions made of SOUND_START / SOUND_STOP events, encoded as real datagrams (so the decoder and Derive
    /// compute dist / is_player / voice exactly as for a recording). The player sits still at the origin, engine running,
    /// no other events: everything the shaker gets comes from the cues (and Lfe.Synth's idle engine, if enabled).
    /// </summary>
    public static class SyntheticSound
    {
        /// <param name="rpm">engine rpm per frame time (default 1050: the pitch law's idle, so a player engine loop sits at 8268.75 Hz)</param>
        public static IEnumerable<(double t, byte[] data)> Session(IList<SoundCue> cues, double seconds, double fps = 50.0, bool playerPresent = true, Func<double, double> rpm = null)
        {
            var L = I76TelLayout.V3;
            uint seq = 0, evSeq = 0;
            int n = (int)Math.Round(seconds * fps);
            double dt = 1.0 / fps;
            for (int c = 0; c < cues.Count; c++) if (cues[c].Voice == 0) cues[c].Voice = 0x6000 + 0x40 * c;
            for (int i = 0; i < n; i++)
            {
                double t = i * dt;
                var f = new TelFrame();
                var evs = new List<TelEvent>();
                void Ev(uint type, Action<TelEvent> fill) { var e = new TelEvent { Seq = ++evSeq, Frame = (uint)i, Type = type }; fill(e); evs.Add(e); }
                bool Due(double at) => at >= 0 && at >= t - 1e-9 && at < t + dt - 1e-9;
                foreach (var q in cues)
                {
                    var nm = TelEvent.PackName(q.Name);
                    if (Due(q.At))
                        Ev(TelEvent.SoundStart, e =>
                        {
                            e.F[0] = (float)q.Hz; e.F[1] = (float)q.Vol;
                            if (q.Dist >= 0) { e.F[2] = (float)q.Dist; e.F[3] = 0; e.F[4] = 0; }
                            e.I[0] = nm.lo; e.I[1] = nm.hi;
                            e.I[2] = (q.Mode & 0xff) | (q.Player ? 0x100 : 0) | (q.Dist >= 0 ? 0x200 : 0) | (50 << 16);
                            e.I[3] = q.Dist >= 0 ? (q.Player ? 0x1000 : 0x3000) : 0; e.I[4] = q.Voice;
                        });
                    if (Due(q.StopAt))
                        Ev(TelEvent.SoundStop, e =>
                        {
                            e.F[0] = (float)(q.StopAt - q.At); e.I[0] = nm.lo; e.I[1] = nm.hi;
                            e.I[2] = (q.StopReason & 0xffff) | (q.Player ? 0x10000 : 0); e.I[3] = q.Dist >= 0 ? (q.Player ? 0x1000 : 0x3000) : 0; e.I[4] = q.Voice;
                        });
                }
                f["seq"] = ++seq; f["frame"] = i + 1; f["proxy_frame"] = i; f["sim_time"] = t; f["sim_dt"] = dt; f["dt"] = dt;
                f["step_count"] = 1; f["player_present"] = playerPresent ? 1 : 0; f["obj_addr"] = 0x1000; f["ent_addr"] = 0x2000;
                double[] rot = { 1, 0, 0, 0, 1, 0, 0, 0, 1 };
                for (int k = 0; k < 9; k++) f["rot_" + k] = rot[k];
                f["flags"] = TelFrame.FlagEngineRunning; f["gear"] = 1; f["rpm"] = rpm?.Invoke(t) ?? 1050; f["surface"] = 5; f["ground_normal_1"] = 1; f["clearance"] = 0.3;
                for (int w = 0; w < 6; w++) { bool pr = w != 2 && w != 3; f["wheel" + w + "_present"] = pr ? 1 : 0; f["wheel" + w + "_hp"] = 100; f["wheel" + w + "_hp_max"] = 100; f["wheel" + w + "_grip"] = 1.0; }
                f["mass"] = 1800; f["inv_mass"] = 1 / 1800.0; f["health_pct"] = 100; f["event_hooks"] = 0x18;
                f["event_seq"] = evSeq;
                yield return (t, TelCodec.Encode(f, evs, L));
            }
        }
    }
}
