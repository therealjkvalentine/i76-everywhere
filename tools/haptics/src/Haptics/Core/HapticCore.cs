using System;
using System.Collections.Generic;
using System.Linq;
using Haptics.Effects;

namespace Haptics.Core
{
    /// <summary>Everything one core update produced: what every renderer consumes.</summary>
    public sealed class CoreStep
    {
        public double T;                       // core time (engine sim time + sub-frame host offset)
        public MixOut Mix;                     // the reference model's output (Force, Channels, Notes, Bus)
        public Bus Bus => Mix.Bus;             // + Voices from chain effects, beds ducked by them
        public VehicleState State;             // the motion interface
        public List<HapticEvent> Events;       // events consumed this update (empty on sub-frame updates)
        public Dictionary<string, double> Duck;
        public Dictionary<string, double> Vars;  // the named frame variables (what effect expressions saw)
        public bool NewFrame;
    }

    /// <summary>
    /// The pure middle layer: Derive.Result in, CoreStep out. Reference model (FfbMixer.ps1 port, tune from the
    /// effect files) + chain effects + ducking + the shaker voice budget. No I/O, no clock: the caller supplies time.
    /// </summary>
    public sealed class HapticCore
    {
        public EffectSet Set { get; private set; }
        public ReferenceMixer Mixer { get; private set; }
        public EffectEngine Engine { get; private set; }
        public ISet<string> Solo = new HashSet<string>(), Mute = new HashSet<string>();
        public int MaxLfeVoices = 3;

        public HapticCore(EffectSet set) { Load(set, true); }

        /// <summary>(Re)load effect files. The reference model keeps its running state across a hot reload.</summary>
        public void Load(EffectSet set, bool fresh = false)
        {
            Set = set;
            var tune = set.BuildTune();
            if (fresh || Mixer == null) Mixer = new ReferenceMixer(tune); else Mixer.Tune = tune;
            if (Engine == null) Engine = new EffectEngine(set.Effects); else Engine.Reload(set.Effects);
            Engine.Solo = Solo; Engine.Mute = Mute;
            MaxLfeVoices = (int)set.Rig.Num("lfe", "max_voices", 3);
        }

        /// <summary>Apply effects/*.json values that Derive reads (weapon shot magnitude, explosion reach).</summary>
        public void Configure(Derive d)
        {
            var w = Set.Get("weapon.fire")?.Json?["source"] as System.Text.Json.Nodes.JsonObject;
            var sm = EffectDef.Str(w, "shot_mag"); if (sm != null) d.ShotMag = new Expr(sm);
            var x = Set.Get("explosion.blast")?.Json?["source"] as System.Text.Json.Nodes.JsonObject;
            d.ExplosionReach = EffectDef.Num(x, "reach_m", 100.0);
            d.ExplodeMag = Mixer.Tune["LfeExplodeMag"];
        }

        static readonly Dictionary<string, string> LfeOwner = new Dictionary<string, string>
        {
            ["EngineAmp"] = "engine.vibration", ["RoadAmp"] = "road.texture", ["ImpulseAmp"] = "impact.collision", ["HeaveAmp"] = "body.heave",
            ["WeaponAmp"] = "weapon.fire", ["ScrubAmp"] = "slip.scrub", ["ExplodeAmp"] = "explosion.blast",
        };

        bool LegacyOn(string id)
        {
            var e = Set.Get(id);
            if (e != null && !e.Enabled) return false;
            if (Mute.Contains(id)) return false;
            return Solo.Count == 0 || Solo.Contains(id) || (id == "impact.collision" && Solo.Contains("gear.shift"));
        }

        public CoreStep Step(Derive.Result d, IList<HapticEvent> events, double t)
        {
            var s = d.Sample;
            if (Math.Abs(s.T - t) > 0) { s = s.Clone(); s.T = t; }
            var mix = Mixer.Update(s, Set.LegacyActive(Solo, Mute));
            var bus = mix.Bus;
            // legacy LFE / tactile sources follow solo, mute and "enabled" too (the wheel channels are gated inside the model)
            var L = bus.Lfe;
            if (!LegacyOn("engine.vibration")) L.EngineAmp = 0;
            if (!LegacyOn("road.texture")) { L.RoadAmp = 0; bus.Tactile[0].Amp = 0; }
            if (!LegacyOn("impact.collision")) L.ImpulseAmp = 0;
            if (!LegacyOn("body.heave")) L.HeaveAmp = 0;
            if (!LegacyOn("weapon.fire")) L.WeaponAmp = 0;
            if (!LegacyOn("slip.scrub")) { L.ScrubAmp = 0; bus.Tactile[1].Amp = 0; }
            if (!LegacyOn("explosion.blast")) L.ExplodeAmp = 0;
            if (!LegacyOn("brake.judder")) bus.Tactile[2].Amp = 0;
            if (!LegacyOn("steer.center") && !LegacyOn("steer.corner") && !LegacyOn("brake.weight") && !LegacyOn("slip.oversteer")) bus.Steady = 0;

            // fill the motion block from the full vehicle state (FfbMixer's bus had no orientation)
            var m = bus.Motion; var st = d.State;
            m.HasOrientation = st.HasOrientation; m.PitchAngle = st.Pitch; m.RollAngle = st.Roll; m.Heading = st.Heading;
            m.PitchRate = st.PitchRate; m.RollRate = st.RollRate; m.PosX = st.PosWorld.X; m.PosY = st.PosWorld.Y; m.PosZ = st.PosWorld.Z;
            m.VelX = st.VelWorld.X; m.VelY = st.VelWorld.Y; m.VelZ = st.VelWorld.Z; m.AccX = st.AccWorld.X; m.AccY = st.AccWorld.Y; m.AccZ = st.AccWorld.Z;
            m.Rpm = st.Rpm; m.Gear = st.Gear; m.Throttle = st.Throttle; m.Steer = st.Steer;

            var voices = Engine.Step(t, events, d.Vars, st);
            var duck = Engine.ApplyDuck(voices);
            if (duck.TryGetValue("engine", out var de)) L.EngineAmp *= de;
            if (duck.TryGetValue("road", out var dr)) L.RoadAmp *= dr;
            if (duck.TryGetValue("slip", out var ds)) L.ScrubAmp *= ds;
            if (duck.TryGetValue("heave", out var dh)) L.HeaveAmp *= dh;

            // shaker voice budget: keep the highest-priority (then loudest) chain voices with LFE content
            var lfeVoices = voices.Where(v => v.LfeAmp > 0).OrderByDescending(v => v.Priority).ThenByDescending(v => v.LfeAmp).ToList();
            for (int i = MaxLfeVoices; i < lfeVoices.Count; i++) lfeVoices[i].LfeAmp = 0;

            bus.Voices = voices;
            bus.VoiceWheel = voices.Sum(v => v.Wheel);
            return new CoreStep { T = t, Mix = mix, State = st, Events = events as List<HapticEvent> ?? events?.ToList() ?? new List<HapticEvent>(), Duck = duck, Vars = d.Vars };
        }
    }
}
