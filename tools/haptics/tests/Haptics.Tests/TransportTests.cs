using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using Haptics;
using Haptics.Core;
using Haptics.Transport;

namespace Haptics.Tests
{
    static class TransportTests
    {
        public static void Run()
        {
            T.Section("i76tel layouts");
            var v2 = I76TelLayout.V2; var v3 = I76TelLayout.V3;
            T.Check("frozen v2: frame 628 B, event 36 B, version 2", v2.Frame.Size == 628 && v2.Event.Size == 36 && v2.Version == 2, v2.Frame.Size + "/" + v2.Event.Size);
            T.Check("frozen v3 (proxy agent 80e1667): frame 664 B, event 56 B, version 3", v3.Frame.Size == 664 && v3.Event.Size == 56 && v3.Version == 3, v3.Frame.Size + "/" + v3.Event.Size);
            bool same = v2.Frame.Fields.All(f => v3.Frame[f.Name] != null && v3.Frame[f.Name].Offset == f.Offset);
            T.Check("every v2 frame field keeps its offset in v3 (appended, not moved)", same, "");
            T.Check("i76tel.py naming: pos_1, rot_7, wheel3_flat, armour_max_2", v2.Frame["pos_1"] != null && v2.Frame["rot_7"] != null && v2.Frame["wheel3_flat"] != null && v2.Frame["armour_max_2"] != null, "");
            var live = I76TelLayout.TryLoadLive();
            Console.WriteLine("    live header: " + (live == null ? "not found" : live.Source + " (version " + live.Version + ", frame " + live.Frame.Size + ")"));

            T.Section("codec: v2 and v3 round trip, tolerance");
            var codec = new TelCodec(null);
            foreach (var L in new[] { v2, v3 })
            {
                var f = new TelFrame();
                f["seq"] = 7; f["frame"] = 99; f["sim_time"] = 12.5; f["speed"] = 21.25; f["gear"] = 3; f["flags"] = 0x2001; f["rpm"] = 4321;
                f["wheel4_flat"] = 1; f["event_seq"] = 42; f["pos_0"] = 1234.5;
                if (L.Version == 3) { f["wheelbase"] = 2.9; f["grip_cap"] = 31.36; f["music_track"] = 5; }
                var evs = new List<TelEvent> { new TelEvent { Seq = 41, Frame = 9, Type = 3 }, new TelEvent { Seq = 42, Frame = 9, Type = L.Version == 3 ? 4u : 1u } };
                evs[0].F[0] = 1.5f; evs[0].F[3] = 40; evs[0].I[0] = 1; evs[0].I[1] = 1;
                if (L.Version == 3) { evs[1].F[5] = 0.25f; evs[1].I[4] = 0x5000; var nm = TelEvent.PackName("whcan"); evs[1].I[0] = nm.lo; evs[1].I[1] = nm.hi; }
                var bytes = TelCodec.Encode(f, evs, L);
                var dg = codec.Decode(bytes);
                bool ok = dg != null && dg.Frame.Version == L.Version && dg.Frame.SimTime == 12.5 && dg.Frame.Speed == 21.25 && dg.Frame.Gear == 3 &&
                          dg.Frame.Flags == 0x2001 && dg.Frame.WheelFlat(4) && dg.Frame.EventSeq == 42 && dg.Frame.Pos(0) == 1234.5 && dg.Events.Count == 2 &&
                          dg.Events[0].F[3] == 40 && dg.Events[0].I[1] == 1;
                if (L.Version == 3) ok &= Math.Abs(dg.Frame["grip_cap"] - 31.36) < 1e-4 && dg.Frame["music_track"] == 5 && dg.Events[1].F[5] == 0.25f && dg.Events[1].I[4] == 0x5000 && dg.Events[1].Name8 == "whcan";
                T.Check("v" + L.Version + " datagram encodes and decodes field for field (" + bytes.Length + " B)", ok, dg?.Warning ?? "");
            }
            // a v3 frame read by a host whose live header is still v2 must still decode (frozen v3 embedded)
            var codecV2Only = new TelCodec(I76TelLayout.V2);
            var f3 = new TelFrame(); f3["speed"] = 5; f3["grip_cap"] = 7;
            var d3 = codecV2Only.Decode(TelCodec.Encode(f3, new List<TelEvent> { new TelEvent { Type = 6, Seq = 1 } }, v3));
            T.Check("v3 datagram decodes with a v2-only live header (56-byte event sized from the datagram)", d3 != null && d3.Frame.Speed == 5 && d3.Frame["grip_cap"] == 7 && d3.Events.Count == 1 && d3.Events[0].Type == 6, "");
            // a v2 frame with a v3 live header: v2 layout, v3-only fields absent (0)
            var f2 = new TelFrame(); f2["speed"] = 3;
            var d2 = new TelCodec(v3).Decode(TelCodec.Encode(f2, new List<TelEvent> { new TelEvent { Type = 1, Seq = 1 } }, v2));
            T.Check("v2 datagram decodes with a v3 live header (v2 layout chosen by the version field)", d2 != null && d2.Frame.Version == 2 && d2.Frame.Speed == 3 && !d2.Frame.Has("grip_cap") && d2.Events.Count == 1, "");
            T.Check("garbage is rejected, not decoded", codec.Decode(new byte[100]) == null, "");
            var shortb = TelCodec.Encode(new TelFrame(), null, v2).Take(300).ToArray();
            var ds = codec.Decode(shortb);
            T.Check("a truncated frame decodes the fields that fit and warns", ds != null && ds.Warning != null, ds?.Warning ?? "null");

            T.Section("shared memory: seqlock splice of the event ring");
            {
                var L = v3; int ring = 64;
                var shm = new byte[8 + L.Frame.Size + ring * L.Event.Size];
                BitConverter.GetBytes(10u).CopyTo(shm, 0); BitConverter.GetBytes((uint)shm.Length).CopyTo(shm, 4);
                var fr = new TelFrame(); fr["speed"] = 9; fr["event_seq"] = 70;
                var frameBytes = TelCodec.Encode(fr, null, L);
                Array.Copy(frameBytes, 0, shm, 8, frameBytes.Length);
                for (uint s = 60; s <= 70; s++)
                {
                    var e = TelCodec.Encode(new TelFrame(), new List<TelEvent> { new TelEvent { Seq = s, Type = 2 } }, L).Skip(L.Frame.Size).ToArray();
                    Array.Copy(e, 0, shm, 8 + L.Frame.Size + (int)(s % ring) * L.Event.Size, e.Length);
                }
                uint lastEv = 65; bool primed = true;
                var dg = ShmReader.Splice(shm, ref lastEv, ref primed);
                var dec = codec.Decode(dg);
                T.Check("splice yields exactly the 5 events new since the last read, in order", dec.Events.Count == 5 && dec.Events.Select(e => e.Seq).SequenceEqual(new uint[] { 66, 67, 68, 69, 70 }) && lastEv == 70, string.Join(",", dec.Events.Select(e => e.Seq)));
                uint le2 = 0; bool pr2 = false;
                var first = codec.Decode(ShmReader.Splice(shm, ref le2, ref pr2));
                T.Check("joining mid-session does not replay the old ring", first.Events.Count == 0 && le2 == 70, first.Events.Count.ToString());
                using (var r = new ShmReader(@"Local\I76Telemetry-haptics-test-" + Environment.ProcessId))
                    T.Check("the reader never creates the mapping (open-existing only)", !r.TryOpen() && r.Poll() == null, "");
            }

            T.Section("UDP listener (loopback, ephemeral port)");
            using (var u = new UdpListener(0))
            using (var tx = new UdpClient())
            {
                var payload = TelCodec.Encode(new TelFrame { V = { } }, null, v2);
                tx.Send(payload, payload.Length, new IPEndPoint(IPAddress.Loopback, u.Port));
                var got = u.Receive(1000);
                T.Check("a datagram sent to 127.0.0.1 arrives intact", got != null && got.SequenceEqual(payload), got == null ? "nothing" : got.Length + " B");
                // the live loop drains with Receive(0): it must poll, not block (ReceiveTimeout 0 = infinite in .NET)
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var none = u.Receive(0);
                T.Check("Receive(0) with nothing queued returns null at once (the live loop's drain must not block)", none == null && sw.ElapsedMilliseconds < 100, sw.ElapsedMilliseconds + " ms");
                tx.Send(payload, payload.Length, new IPEndPoint(IPAddress.Loopback, u.Port));
                System.Threading.Thread.Sleep(50);
                var q = u.Receive(0);
                T.Check("Receive(0) returns a queued datagram", q != null && q.SequenceEqual(payload), q == null ? "nothing" : q.Length + " B");
            }

            T.Section(".i76rec recorder / replayer");
            var path = Path.Combine(T.TempDir("transport"), "roundtrip.i76rec");
            var dgs = Synthetic.Session(3).ToList();
            using (var w = new RecordingWriter(path, "{\"test\":1}")) foreach (var (t, d) in dgs) w.Add(t, d);
            var rec = RecordingReader.Load(path);
            T.Check("synthetic session (1200 datagrams) round-trips byte for byte", rec.Records.Count == dgs.Count && rec.Records.Zip(dgs, (x, y) => x.t == y.t && x.data.SequenceEqual(y.data)).All(b => b) && rec.Meta == "{\"test\":1}", rec.Records.Count.ToString());
            File.WriteAllBytes(path + ".cut", File.ReadAllBytes(path).Take((int)new FileInfo(path).Length - 100).ToArray());
            T.Check("a truncated recording (recorder killed) keeps every whole record", RecordingReader.Load(path + ".cut").Records.Count == dgs.Count - 1, "");

            T.Section("Derive on the synthetic session (v3 and v2)");
            foreach (int ver in new[] { 3, 2 })
            {
                var derive = new Derive();
                var all = Sources.FromDatagrams(Synthetic.Session(ver), derive, new TelCodec(null)).ToList();
                var evs = all.SelectMany(f => f.Events).ToList();
                int Count(string ty) => evs.Count(e => e.Type == ty);
                T.Check("v" + ver + ": 1200 frames decoded", all.Count == 1200, all.Count.ToString());
                T.Check("v" + ver + ": two upshifts (2->3, 3->4) as Shift +1; R/N changes are GEAR events but not shifts",
                    all.Count(f => f.D.Sample.Shift == 1) == 2 && all.Count(f => f.D.Sample.Shift == -1) == 0 && Count("GEAR") == 4, all.Count(f => f.D.Sample.Shift == 1) + " / " + Count("GEAR"));
                var land = evs.FirstOrDefault(e => e.Type == "LANDING");
                T.Check("v" + ver + ": one TAKEOFF and one LANDING with the pre-landing vertical speed and airtime",
                    Count("TAKEOFF") == 1 && land != null && land["vy_before"] < -5 && Math.Abs(land["airtime"] - 0.6) < 0.05, land?.ToString() ?? "none");
                T.Check("v" + ver + ": ENGINE_START, GRIP_LIMIT, SKID, FLAT(wheel 1) edges", Count("ENGINE_START") == 1 && Count("GRIP_LIMIT") == 1 && Count("SKID") == 1 && evs.Count(e => e.Type == "FLAT" && e["wheel"] == 1) == 1, "");
                T.Check("v" + ver + ": 10 SHOT, 1 IMPACT (player, 40 hp), 1 EXPLOSION at 30 m", Count("SHOT") == 10 && evs.Count(e => e.Type == "IMPACT" && e["hp_lost"] == 40 && e["is_player"] == 1) == 1 && evs.Count(e => e.Type == "EXPLOSION" && e["dist"] == 30) == 1, "");
                var imp = all.First(f => f.Events.Any(e => e.Type == "IMPACT"));
                T.Check("v" + ver + ": the sideways velocity step shows as a jolt above the impact trigger (5.6 m/s^2)", imp.D.Sample.Jolt > 5.6 * 10, imp.D.Sample.Jolt.ToString("0.0"));
                T.Check("v" + ver + ": SHOT feeds the reference model's FxEvent/FxFired; EXPLOSION a blast magnitude >= LfeExplodeMag",
                    all.Count(f => f.D.Sample.FxEvent == true) == 10 && all.Any(f => f.D.Sample.FxFired != null && f.D.Sample.FxFired.Any(x => x.Mag >= 40)), "");
                if (ver == 3)
                {
                    var snd = evs.First(e => e.Type == "SOUND_START" && e.Name == "whcan");
                    T.Check("v3: SOUND_START unpacked (name, is_player 0, has_pos, prio 60) with host-computed distance 40 m", snd["is_player"] == 0 && snd["has_pos"] == 1 && snd["prio"] == 60 && Math.Abs(snd["dist"] - 40) < 0.5, snd.ToString());
                    var dmg = evs.First(e => e.Type == "DAMAGE_SIDE");
                    T.Check("v3: DAMAGE_SIDE (side 2 right, amount 30, player bit) and WEAPON_UI and SOUND_STOP", dmg["side"] == 2 && dmg["amount"] == 30 && dmg["is_player"] == 1 && Count("WEAPON_UI") == 1 && Count("SOUND_STOP") == 1, dmg.ToString());
                }
                else T.Check("v2: no v3 events appear", Count("SOUND_START") + Count("DAMAGE_SIDE") + Count("WEAPON_UI") == 0, "");
                var mid = all[8 * 60].D.State;
                T.Check("v" + ver + ": VehicleState body frame: forward body velocity = speed when gripped (heading from rot)",
                    mid.HasOrientation && Math.Abs(mid.VelBody.Z - mid.Speed) < 0.01 && Math.Abs(mid.VelBody.X) < 0.01, mid.VelBody.ToString() + " speed " + mid.Speed);
            }
        }
    }
}
