using System.Globalization;
using System.IO;
using Haptics.Core;

namespace Haptics.Renderers
{
    /// <summary>
    /// Motion.FileSink: the example / no-op motion renderer. Writes the VehicleState motion interface per core step
    /// to CSV so the motion workstream has recorded, declared-unit input to develop against.
    ///
    /// TODO(motion): motion cueing, washout filters and packet formats (Forza Data Out, LFS OutSim/OutGauge, FlyPT
    /// generic) are deliberately NOT here - see docs/MOTION-OUTPUT.md (separate workstream). A motion renderer
    /// implements IRenderer, reads CoreStep.State (+ CoreStep.Events for kicks) and registers itself with
    /// RendererRegistry.Register("Motion.&lt;name&gt;", ...); a rig selects it with "outputs": {"motion": {"renderer": ...}}.
    /// The previous OutSim/OutGauge sender is tools/ffb/ffb-telemetry-udp.ps1 (memory-scanner input, pitch/roll zero).
    /// </summary>
    public sealed class MotionFileSink : IRenderer
    {
        public string Type => "Motion.FileSink";
        StreamWriter _csv; public string CsvPath; int _n;
        public void Open(RendererContext ctx)
        {
            if (ctx.OutDir == null) return;
            Directory.CreateDirectory(ctx.OutDir);
            CsvPath = Path.Combine(ctx.OutDir, ctx.Tag + ".motion.csv");
            _csv = new StreamWriter(CsvPath);
            _csv.WriteLine("t,ticked,present,has_orientation,pos_x,pos_y,pos_z,vel_body_x,vel_body_y,vel_body_z,acc_body_x,acc_body_y,acc_body_z," +
                           "acc_world_x,acc_world_y,acc_world_z,pitch,roll,heading,pitch_rate,yaw_rate,roll_rate,speed,rpm,gear,airborne,events");
        }
        public void Render(CoreStep s)
        {
            if (_csv == null) return;
            var v = s.State; _n++;
            var ev = s.Events == null || s.Events.Count == 0 ? "" : string.Join(";", s.Events.ConvertAll(e => e.Type));
            _csv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0:0.####},{1},{2},{3},{4:0.###},{5:0.###},{6:0.###},{7:0.###},{8:0.###},{9:0.###},{10:0.###},{11:0.###},{12:0.###},{13:0.###},{14:0.###},{15:0.###},{16:0.#####},{17:0.#####},{18:0.#####},{19:0.####},{20:0.####},{21:0.####},{22:0.###},{23:0},{24},{25},{26}",
                s.T, v.Ticked ? 1 : 0, v.Present ? 1 : 0, v.HasOrientation ? 1 : 0, v.PosWorld.X, v.PosWorld.Y, v.PosWorld.Z,
                v.VelBody.X, v.VelBody.Y, v.VelBody.Z, v.AccBody.X, v.AccBody.Y, v.AccBody.Z, v.AccWorld.X, v.AccWorld.Y, v.AccWorld.Z,
                v.Pitch, v.Roll, v.Heading, v.PitchRate, v.YawRate, v.RollRate, v.Speed, v.Rpm, v.Gear, v.Airborne ? 1 : 0, ev));
        }
        public void Close() { _csv?.Dispose(); _csv = null; }
        public string Summary() => "Motion.FileSink: " + _n + " rows -> " + (CsvPath ?? "(no out dir)") + "  (cueing/packets: docs/MOTION-OUTPUT.md)";
        public void Dispose() => Close();
    }
}
