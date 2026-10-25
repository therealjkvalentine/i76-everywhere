using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using Haptics;
using Haptics.Core;
using Haptics.Effects;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics.Tests
{
    /// <summary>--debug-udp: the debug publisher for tools/debug (DebugPublisher.cs). Loopback only, files only.</summary>
    static class DebugTests
    {
        public static void Run()
        {
            Spec();
            Spectrum();
            Publish();
        }

        static void Spec()
        {
            T.Section("debug publisher: endpoint parsing, loopback only");
            using (var d = DebugPublisher.FromSpec(null)) T.Check("default endpoint 127.0.0.1:17680", d.Endpoint == "127.0.0.1:17680", d.Endpoint);
            using (var d = DebugPublisher.FromSpec("17999")) T.Check("a bare port", d.Endpoint == "127.0.0.1:17999", d.Endpoint);
            using (var d = DebugPublisher.FromSpec("localhost:18001")) T.Check("localhost:port", d.Endpoint == "127.0.0.1:18001", d.Endpoint);
            bool refused = false;
            try { DebugPublisher.FromSpec("192.0.2.20:17680").Dispose(); } catch (ArgumentException) { refused = true; }
            T.Check("a non-loopback address is refused", refused);
        }

        static void Spectrum()
        {
            T.Section("debug publisher: shaker tap and spectrum");
            var tap = new SampleTap(8192, 16000);
            for (int i = 0; i < 20000; i++) tap.Add((short)(16000 * Math.Sin(2 * Math.PI * 40 * i / 16000.0)));
            var x = tap.Last(4096);
            var sp = SampleTap.Spectrum(x, 16000, DebugPublisher.SpectrumHz);
            int peak = Array.IndexOf(sp, sp.Max());
            T.Check("a 40 Hz sine peaks in the 40 Hz bin, at about its amplitude (0.49)", DebugPublisher.SpectrumHz[peak] == 40 && Math.Abs(sp[peak] - 16000 / 32768.0) < 0.05,
                "peak " + DebugPublisher.SpectrumHz[peak] + " Hz = " + sp[peak].ToString("0.000"));
            T.Check("bins two steps away are far smaller (Hann window)", sp[peak - 2] < sp[peak] * 0.1 && sp[peak + 2] < sp[peak] * 0.1, sp[peak - 2].ToString("0.0000") + " / " + sp[peak + 2].ToString("0.0000"));
            T.Check("Since() returns what was written after a mark, capped at the ring", tap.Since(19990, out var now).Length == 10 && now == 20000 && tap.Since(0, out _).Length == 8192);
            T.Check("10..120 Hz in 5 Hz steps (23 bins)", DebugPublisher.SpectrumHz.Length == 23 && DebugPublisher.SpectrumHz[0] == 10 && DebugPublisher.SpectrumHz[22] == 120);
        }

        static (Pipeline p, MotionUdpRenderer mr) Build(string dir, string tag)
        {
            var set = EffectSet.Load();
            var p = Session.Build(set, new[] { "wheel-file", "pad-file", "lfe-wav" }, dir, tag, false, 250);
            var mr = new MotionUdpRenderer();
            mr.Open(new RendererContext { OutputName = "motion_udp", Config = new System.Text.Json.Nodes.JsonObject { ["select"] = "native" }, Rig = set.Rig, Effects = set, Tune = p.Core.Mixer.Tune, OutDir = dir, Tag = tag, CoreHz = 250, Log = TextWriter.Null });
            p.Renderers.Add(mr);
            return (p, mr);
        }

        static void RunSession(Pipeline p)
        {
            var d = new Derive(); p.Core.Configure(d);
            p.Run(Sources.FromDatagrams(Synthetic.Session(3), d, TelCodec.Default()));
            foreach (var r in p.Renderers) r.Close();
        }

        static void Publish()
        {
            T.Section("debug publisher: a synthetic session with every output, datagrams decoded");
            var dir = T.TempDir("debug-pub");
            // reference: no publisher
            var (p0, _) = Build(dir, "off");
            RunSession(p0);
            // with the publisher, received on a loopback socket
            using var rx = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
            int port = ((IPEndPoint)rx.Client.LocalEndPoint).Port;
            rx.Client.ReceiveBufferSize = 8 << 20;
            var (p1, mr1) = Build(dir, "on");
            var dbg = new DebugPublisher("127.0.0.1", port, 60);
            dbg.Attach(p1);
            var sent = new List<byte[]>();
            dbg.OnDatagram = b => sent.Add(b);
            long events = 0;
            p1.OnStep = s => events += s.Events?.Count ?? 0;
            RunSession(p1);
            dbg.Dispose();
            var got = new List<JsonDocument>();
            rx.Client.ReceiveTimeout = 200;
            try { while (true) { var ep = new IPEndPoint(IPAddress.Any, 0); got.Add(JsonDocument.Parse(rx.Receive(ref ep))); } } catch (SocketException) { }

            T.Check("off: Pipeline.Debug and LfeSynthRenderer.Tap stay null without --debug-udp", p0.Debug == null && p0.Renderers.OfType<LfeSynthRenderer>().All(r => r.Tap == null));
            bool same = File.ReadAllBytes(Path.Combine(dir, "off.lfe.wav")).Skip(44).SequenceEqual(File.ReadAllBytes(Path.Combine(dir, "on.lfe.wav")).Skip(44))
                     && File.ReadAllText(Path.Combine(dir, "off.wheel.csv")) == File.ReadAllText(Path.Combine(dir, "on.wheel.csv"))
                     && File.ReadAllText(Path.Combine(dir, "off.pad.csv")) == File.ReadAllText(Path.Combine(dir, "on.pad.csv"));
            T.Check("the publisher changes no output: lfe.wav, wheel.csv, pad.csv byte-identical with and without it", same);
            T.Check("every datagram sent arrived on loopback, none failed", got.Count == sent.Count && dbg.Errors == 0 && dbg.Published == sent.Count, got.Count + " received / " + sent.Count + " sent");
            var docs = sent.Select(b => JsonDocument.Parse(b)).ToList();
            double t0 = docs.First().RootElement.GetProperty("t").GetDouble(), t1 = docs.Last().RootElement.GetProperty("t").GetDouble();
            double rate = (docs.Count - 1) / Math.Max(1e-9, t1 - t0);
            T.Check("at most 60 datagrams per second of core time (core grid 250 Hz)", rate <= 60.5 && rate > 40, rate.ToString("0.0") + " /s over " + (t1 - t0).ToString("0.0") + " s");
            var ts = docs.Select(d => d.RootElement.GetProperty("t").GetDouble()).ToList();
            T.Check("core time increases datagram to datagram", ts.Zip(ts.Skip(1), (a, b) => b > a).All(x => x));
            long evTotal = docs.Sum(d => d.RootElement.GetProperty("ev_count").EnumerateObject().Sum(x => x.Value.GetInt64()));
            long lastTotal = docs.Last().RootElement.GetProperty("ev_total").EnumerateObject().Sum(x => x.Value.GetInt64());
            T.Check("events: ev_count per datagram sums to the running ev_total; only the last 1/60 s (after the final datagram) is uncounted",
                evTotal == lastTotal && evTotal > 0 && events - evTotal >= 0 && events - evTotal < 50, evTotal + " counted / " + events + " consumed");
            var last = docs.Last().RootElement;
            T.Check("schema 1, kind i76haptics", last.GetProperty("schema").GetInt32() == 1 && last.GetProperty("kind").GetString() == "i76haptics");
            T.Check("wheel: model / voice / device + the reference model's channel breakdown",
                last.GetProperty("wheel").TryGetProperty("device", out _) && last.GetProperty("wheel").GetProperty("channels").TryGetProperty("center", out _));
            T.Check("some datagram carries a non-zero device force and a sounding effect voice",
                docs.Any(d => d.RootElement.GetProperty("wheel").GetProperty("device").GetInt32() != 0) && docs.Any(d => d.RootElement.GetProperty("voices").GetArrayLength() > 0));
            T.Check("pad: the open pad renderer's L / R, some non-zero", last.GetProperty("pad").GetProperty("open").GetBoolean() && docs.Any(d => d.RootElement.GetProperty("pad").GetProperty("l").GetDouble() > 0));
            var lfe = last.GetProperty("lfe");
            T.Check("lfe: tap level and a 23-bin spectrum, some non-zero RMS", lfe.GetProperty("spectrum").GetArrayLength() == 23 && docs.Any(d => d.RootElement.GetProperty("lfe").GetProperty("rms").GetDouble() > 0));
            var mo = last.GetProperty("motion_out");
            T.Check("motion: the latest MotionFrame (status word, gain, channels) and the native target's packet count",
                mo.GetProperty("open").GetBoolean() && mo.GetProperty("frames").GetInt64() > 100 && mo.TryGetProperty("status", out _) && mo.GetProperty("targets")[0].GetProperty("packets").GetInt64() > 100 && !mo.GetProperty("sending").GetBoolean());
            T.Check("datagrams stay well under one UDP payload", sent.Max(b => b.Length) < 16000, "max " + sent.Max(b => b.Length) + " B");
            T.Check("Dispose detaches the tap and the motion hook", p1.Renderers.OfType<LfeSynthRenderer>().All(r => r.Tap == null));
        }

    }
}
