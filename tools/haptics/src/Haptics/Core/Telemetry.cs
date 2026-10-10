using System;
using System.Collections.Generic;
using System.Text;

namespace Haptics.Core
{
    /// <summary>
    /// One decoded i76tel frame. Values are kept by i76tel.py's flattened field name ("speed", "pos_1",
    /// "wheel3_flat", ...) so a field added in a later header version is simply one more key: nothing here has
    /// to change for v3 to decode. Typed accessors cover what Derive reads.
    /// </summary>
    public sealed class TelFrame
    {
        public readonly Dictionary<string, double> V = new Dictionary<string, double>(StringComparer.Ordinal);
        public byte[] WeaponName = new byte[8];
        public int Version, Size;

        public double this[string k] { get => V.TryGetValue(k, out var d) ? d : 0.0; set => V[k] = value; }
        public bool Has(string k) => V.ContainsKey(k);

        public uint Seq => (uint)this["seq"];
        public uint SimFrame => (uint)this["frame"];
        public uint ProxyFrame => (uint)this["proxy_frame"];
        public double SimTime => this["sim_time"];
        public double SimDt => this["sim_dt"];
        public bool PlayerPresent => this["player_present"] != 0;
        public double Speed => this["speed"];
        public double Steer => this["steer"];
        public double Throttle => this["throttle"];
        public double YawRate => this["yaw_rate"];
        public double PitchRate => this["pitch_rate"];
        public double RollRate => this["roll_rate"];
        public double Rpm => this["rpm"];
        public int Gear => (int)this["gear"];
        public uint Flags => (uint)this["flags"];
        public uint Surface => (uint)this["surface"];
        public uint EventSeq => (uint)this["event_seq"];
        public uint EventCount => (uint)this["event_count"];
        public double Vel(int i) => this["velocity_" + i];
        public double Pos(int i) => this["pos_" + i];
        public double Rot(int i) => this["rot_" + i];
        public double Accel(int i) => this["accel_" + i];
        public bool WheelFlat(int w) => this["wheel" + w + "_flat"] != 0;
        public bool WheelPresent(int w) => this["wheel" + w + "_present"] != 0;
        public double WheelSusp(int w) => this["wheel" + w + "_susp_offset"];
        public string WeaponNameString { get { int n = Array.IndexOf(WeaponName, (byte)0); return Encoding.ASCII.GetString(WeaponName, 0, n < 0 ? 8 : n); } }

        public const uint FlagEngineRunning = 0x1, FlagSkid = 0x2, FlagAirborne = 0x4, FlagStarting = 0x8, FlagDestroyed = 0x20,
                          FlagOil = 0x400, FlagNitrous = 0x800, FlagGripLimit = 0x2000, FlagCritical = 0x4000, FlagWreck = 0x8000;

        public TelFrame Clone()
        {
            var f = new TelFrame { Version = Version, Size = Size, WeaponName = (byte[])WeaponName.Clone() };
            foreach (var kv in V) f.V[kv.Key] = kv.Value;
            return f;
        }
    }

    /// <summary>One raw i76tel event (36 bytes in v2, 56 in v3).</summary>
    public sealed class TelEvent
    {
        public uint Seq, Frame, Type;
        public double[] F = new double[6];   // v3: f[6] (v2 used f[0..3])
        public int[] I = new int[5];         // v3: i[5] (v2 used i[0..1])
        public const uint Shot = 1, Explosion = 2, Impact = 3, SoundStart = 4, SoundStop = 5, DamageSide = 6, WeaponUi = 7;

        public string Name8
        {
            get
            {
                var b = new byte[8];
                BitConverter.GetBytes(I[0]).CopyTo(b, 0); BitConverter.GetBytes(I[1]).CopyTo(b, 4);
                int n = Array.IndexOf(b, (byte)0);
                return Encoding.ASCII.GetString(b, 0, n < 0 ? 8 : n);
            }
        }
        public static (int lo, int hi) PackName(string s)
        {
            var b = new byte[8];
            var src = Encoding.ASCII.GetBytes(s ?? "");
            Array.Copy(src, b, Math.Min(8, src.Length));
            return (BitConverter.ToInt32(b, 0), BitConverter.ToInt32(b, 4));
        }
    }

    /// <summary>
    /// The host-side canonical event effects match on (HAPTICS-ARCHITECTURE 4.1): a type name, the engine time,
    /// named numeric fields and an optional name. Both proxy events and host-derived edges arrive as these.
    /// </summary>
    public sealed class HapticEvent
    {
        public string Type, Name;
        public double T; public uint Frame;
        public readonly Dictionary<string, double> F = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        public double this[string k] { get => F.TryGetValue(k, out var d) ? d : 0.0; set => F[k] = value; }
        public override string ToString()
        {
            var sb = new StringBuilder(Type);
            if (Name != null) sb.Append(" '").Append(Name).Append('\'');
            foreach (var kv in F) sb.Append(' ').Append(kv.Key).Append('=').Append(Fmt.G(kv.Value, "0.###"));
            return sb.ToString();
        }
    }
}
