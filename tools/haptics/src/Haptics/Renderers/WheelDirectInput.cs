using System;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using Haptics.Core;

namespace Haptics.Renderers
{
    /// <summary>
    /// Wheel.DirectInput: the reference model's force (+ chain voices) -> Mix-RenderWheel (belt-drive MinForce lift,
    /// clamp) -> ONE infinite constant force rewritten with DIEP_TYPESPECIFICPARAMS only (tools/ffb/FfbCore.ps1: the T300
    /// refuses periodic effects, and extra DIEP flags double the USB traffic, SDL#12511).
    /// File sink: CSV (t, model force, voice force, total, device force). Live (--live): FfbCore's DirectInput path,
    /// exclusive + background, autocentre off, re-acquire on loss, zero force on close.
    /// Wheel ownership (HAPTICS-ARCHITECTURE 3.3): mode A (host owns) needs 0x52bbe4 zeroed in the game, which this
    /// renderer does NOT do (the host writes nothing into the game process); use tools/ffb/ffb-interposer.ps1's
    /// Tel-SetEngineFfb for that until mode C exists.
    /// </summary>
    public sealed class WheelDirectInput : IRenderer
    {
        public string Type => "Wheel.DirectInput";
        RendererContext _ctx;
        StreamWriter _csv;
        double _minForce, _gate, _clamp; bool _onlyOnChange;
        int _last = int.MinValue;
        DiWheel _dev;
        public int Frames, Writes, Peak; public long Errors;
        public string CsvPath;
        public int LastDevice;

        public void Open(RendererContext ctx)
        {
            _ctx = ctx;
            _minForce = ctx.Num("min_force", ctx.Tune["MinForce"]); _gate = ctx.Num("min_force_gate", ctx.Tune["MinForceGate"]);
            _clamp = ctx.Num("clamp", ctx.Tune["Clamp"]);
            _onlyOnChange = !(ctx.Config?["update_only_on_change"] is System.Text.Json.Nodes.JsonValue v && v.TryGetValue<bool>(out var b) && !b);
            if (ctx.OutDir != null)
            {
                Directory.CreateDirectory(ctx.OutDir);
                CsvPath = Path.Combine(ctx.OutDir, ctx.Tag + ".wheel.csv");
                _csv = new StreamWriter(CsvPath);
                _csv.WriteLine("t,model_force,voice_force,total,device_force");
            }
            if (ctx.Live)
            {
                try { _dev = DiWheel.Open(ctx.Str("device_match")); ctx.Log.WriteLine("Wheel.DirectInput: acquired " + _dev.Name); }
                catch (Exception ex) { ctx.Log.WriteLine("Wheel.DirectInput live: " + ex.Message + " - file sink only"); _dev = null; }
            }
        }

        public static int DeviceForce(CoreStep s, double minForce, double gate, double clamp)
        {
            double voice = s.Bus.VoiceWheel * 10000.0 * s.Mix.Ramp;
            double total = s.Mix.Force + voice;
            if (total > clamp) total = clamp; if (total < -clamp) total = -clamp;
            return ReferenceMixer.RenderWheelLegacy(ReferenceMixer.PsInt(total), minForce, gate, clamp);
        }

        public void Render(CoreStep s)
        {
            Frames++;
            double voice = s.Bus.VoiceWheel * 10000.0 * s.Mix.Ramp;
            int dev = DeviceForce(s, _minForce, _gate, _clamp);
            LastDevice = dev;
            Peak = Math.Max(Peak, Math.Abs(dev));
            _csv?.WriteLine(string.Format(CultureInfo.InvariantCulture, "{0:0.####},{1},{2:0},{3:0},{4}", s.T, s.Mix.Force, voice, s.Mix.Force + voice, dev));
            if (_onlyOnChange && dev == _last) return;
            _last = dev; Writes++;
            if (_dev != null)
            {
                int hr = _dev.Constant(dev);
                if (hr < 0) { Errors++; _dev.Reacquire(); }
            }
        }

        public void Close()
        {
            if (_dev != null) { try { _dev.Constant(0); _dev.Close(); } catch { } _dev = null; }
            _csv?.Dispose(); _csv = null;
        }
        public string Summary() => string.Format(CultureInfo.InvariantCulture, "Wheel.DirectInput: {0} updates, {1} device writes, peak {2}, errors {3} -> {4}",
            Frames, Writes, Peak, Errors, _dev != null ? _dev.Name : CsvPath);
        public void Dispose() => Close();
    }

    /// <summary>tools/ffb/FfbCore.ps1's DirectInput8 vtable walk, in C#. Only ever created from live mode.</summary>
    public sealed class DiWheel
    {
        [DllImport("dinput8.dll")] static extern int DirectInput8Create(IntPtr hinst, uint ver, ref Guid riid, out IntPtr ppv, IntPtr punk);
        [DllImport("kernel32.dll", CharSet = CharSet.Ansi)] static extern IntPtr LoadLibraryA(string n);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr CreateWindowExW(int ex, string cls, string name, int style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr inst, IntPtr p);
        [DllImport("user32.dll")] static extern bool DestroyWindow(IntPtr h);

        static Guid IID_IDirectInput8W = new Guid("BF798031-483A-4DA2-AA99-5D64ED369700");
        static Guid GUID_ConstantForce = new Guid("13541C20-8E33-11D0-9AD0-00A0C9A06E35");
        static Guid GUID_XAxis = new Guid("A36D02E0-C9F3-11CF-BFC7-444553540000");

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        struct DIDEVICEINSTANCEW
        {
            public uint dwSize; public Guid guidInstance; public Guid guidProduct; public uint dwDevType;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string tszInstanceName;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string tszProductName;
            public Guid guidFFDriver; public ushort wUsagePage, wUsage;
        }
        [StructLayout(LayoutKind.Sequential)] struct DIOBJECTDATAFORMAT { public IntPtr pguid; public uint dwOfs, dwType, dwFlags; }
        [StructLayout(LayoutKind.Sequential)] struct DIDATAFORMAT { public uint dwSize, dwObjSize, dwFlags, dwDataSize, dwNumObjs; public IntPtr rgodf; }
        [StructLayout(LayoutKind.Sequential)]
        struct DIEFFECT
        {
            public uint dwSize, dwFlags, dwDuration, dwSamplePeriod, dwGain, dwTriggerButton, dwTriggerRepeatInterval, cAxes;
            public IntPtr rgdwAxes, rglDirection, lpEnvelope; public uint cbTypeSpecificParams; public IntPtr lpvTypeSpecificParams; public uint dwStartDelay;
        }
        [StructLayout(LayoutKind.Sequential)] struct DIPROPDWORD { public uint dwSize, dwHeaderSize, dwObj, dwHow, dwData; }

        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int EnumCb(ref DIDEVICEINSTANCEW d, IntPtr pv);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Enum(IntPtr self, uint type, EnumCb cb, IntPtr pv, uint flags);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Create(IntPtr self, ref Guid g, out IntPtr dev, IntPtr punk);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Fmt(IntPtr self, ref DIDATAFORMAT df);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Coop(IntPtr self, IntPtr hwnd, uint flags);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Self(IntPtr self);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Prop(IntPtr self, IntPtr guid, ref DIPROPDWORD p);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_CreateEff(IntPtr self, ref Guid g, ref DIEFFECT e, out IntPtr eff, IntPtr punk);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_SetParams(IntPtr self, ref DIEFFECT e, uint flags);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int D_Start(IntPtr self, uint iter, uint flags);

        static T Fn<T>(IntPtr obj, int slot) => Marshal.GetDelegateForFunctionPointer<T>(Marshal.ReadIntPtr(Marshal.ReadIntPtr(obj), slot * IntPtr.Size));

        IntPtr _di, _dev, _eff, _hwnd, _tp, _axes, _dir, _odf, _guidX;
        DIEFFECT _e;
        public string Name;

        public static DiWheel Open(string match)
        {
            var w = new DiWheel();
            IntPtr hinst = LoadLibraryA("dinput8.dll");
            var iid = IID_IDirectInput8W;
            int hr = DirectInput8Create(hinst, 0x0800, ref iid, out w._di, IntPtr.Zero);
            if (hr != 0) throw new Exception("DirectInput8Create 0x" + hr.ToString("X8"));
            Guid pick = Guid.Empty; string pickName = null;
            EnumCb cb = (ref DIDEVICEINSTANCEW d, IntPtr pv) =>
            {
                if (pickName == null && (string.IsNullOrEmpty(match) || d.tszProductName.IndexOf(match, StringComparison.OrdinalIgnoreCase) >= 0))
                { pick = d.guidInstance; pickName = d.tszProductName; }
                return 1;
            };
            hr = Fn<D_Enum>(w._di, 4)(w._di, 4 /*GAMECTRL*/, cb, IntPtr.Zero, 0x1 | 0x100 /*ATTACHED|FORCEFEEDBACK*/);
            GC.KeepAlive(cb);
            if (pickName == null) throw new Exception("no force-feedback device" + (string.IsNullOrEmpty(match) ? "" : " matching '" + match + "'"));
            w.Name = pickName;
            hr = Fn<D_Create>(w._di, 3)(w._di, ref pick, out w._dev, IntPtr.Zero);
            if (hr != 0) throw new Exception("CreateDevice 0x" + hr.ToString("X8"));
            w._guidX = Marshal.AllocHGlobal(16); Marshal.Copy(GUID_XAxis.ToByteArray(), 0, w._guidX, 16);
            w._odf = Marshal.AllocHGlobal(Marshal.SizeOf<DIOBJECTDATAFORMAT>());
            Marshal.StructureToPtr(new DIOBJECTDATAFORMAT { pguid = w._guidX, dwOfs = 0, dwType = 0x00000003 | 0x00FFFF00 }, w._odf, false);
            var df = new DIDATAFORMAT { dwSize = (uint)Marshal.SizeOf<DIDATAFORMAT>(), dwObjSize = (uint)Marshal.SizeOf<DIOBJECTDATAFORMAT>(), dwFlags = 1, dwDataSize = 4, dwNumObjs = 1, rgodf = w._odf };
            hr = Fn<D_Fmt>(w._dev, 11)(w._dev, ref df);
            if (hr != 0) throw new Exception("SetDataFormat 0x" + hr.ToString("X8"));
            w._hwnd = CreateWindowExW(0, "STATIC", "i76-haptics-ffb", 0, 0, 0, 0, 0, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
            hr = Fn<D_Coop>(w._dev, 13)(w._dev, w._hwnd, 0x1 | 0x8 /*EXCLUSIVE|BACKGROUND*/);
            if (hr != 0) throw new Exception("SetCooperativeLevel 0x" + hr.ToString("X8"));
            var prop = new DIPROPDWORD { dwSize = (uint)Marshal.SizeOf<DIPROPDWORD>(), dwHeaderSize = 16, dwObj = 0, dwHow = 0, dwData = 0 };
            Fn<D_Prop>(w._dev, 6)(w._dev, (IntPtr)5 /*DIPROP_AUTOCENTER*/, ref prop);
            hr = Fn<D_Self>(w._dev, 7)(w._dev);
            if (hr < 0) throw new Exception("Acquire 0x" + hr.ToString("X8") + " - something else holds the device (the game?)");
            w._tp = Marshal.AllocHGlobal(4); Marshal.WriteInt32(w._tp, 0);
            w._axes = Marshal.AllocHGlobal(4); Marshal.WriteInt32(w._axes, 0);
            w._dir = Marshal.AllocHGlobal(4); Marshal.WriteInt32(w._dir, 0);
            w._e = new DIEFFECT
            {
                dwSize = (uint)Marshal.SizeOf<DIEFFECT>(), dwFlags = 0x10 | 0x2, dwDuration = 0xFFFFFFFF, dwGain = 10000, dwTriggerButton = 0xFFFFFFFF,
                cAxes = 1, rgdwAxes = w._axes, rglDirection = w._dir, cbTypeSpecificParams = 4, lpvTypeSpecificParams = w._tp,
            };
            var g = GUID_ConstantForce;
            hr = Fn<D_CreateEff>(w._dev, 18)(w._dev, ref g, ref w._e, out w._eff, IntPtr.Zero);
            if (hr != 0) throw new Exception("CreateEffect(ConstantForce) 0x" + hr.ToString("X8"));
            Fn<D_Start>(w._eff, 7)(w._eff, 1, 0);
            return w;
        }

        public int Constant(int mag)
        {
            Marshal.WriteInt32(_tp, Math.Max(-10000, Math.Min(10000, mag)));
            return Fn<D_SetParams>(_eff, 6)(_eff, ref _e, 0x100 /*DIEP_TYPESPECIFICPARAMS only*/);
        }
        public bool Reacquire()
        {
            if (Fn<D_Self>(_dev, 7)(_dev) < 0) return false;
            Fn<D_SetParams>(_eff, 6)(_eff, ref _e, 0x100 | 0x20000000);
            return true;
        }
        public void Close()
        {
            if (_eff != IntPtr.Zero) { Fn<D_Self>(_eff, 8)(_eff); Fn<D_Self>(_eff, 2)(_eff); _eff = IntPtr.Zero; }
            if (_dev != IntPtr.Zero) { Fn<D_Self>(_dev, 8)(_dev); Fn<D_Self>(_dev, 2)(_dev); _dev = IntPtr.Zero; }
            if (_di != IntPtr.Zero) { Fn<D_Self>(_di, 2)(_di); _di = IntPtr.Zero; }
            if (_hwnd != IntPtr.Zero) DestroyWindow(_hwnd);
            foreach (var p in new[] { _tp, _axes, _dir, _odf, _guidX }) if (p != IntPtr.Zero) Marshal.FreeHGlobal(p);
        }
    }
}
