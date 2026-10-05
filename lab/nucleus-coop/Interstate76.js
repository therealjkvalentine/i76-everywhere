// Nucleus Co-op handler for Interstate '76 Gold Edition (GOG). First run 2026-10-05 (README, section Runs). Written 2026-10-03 against Nucleus Co-op
// v2.4.2 (SplitScreen-Me/splitscreenme-nucleus, GPL-3.0; unpacked in ..\refs\nucleus\app, source in ..\refs\nucleus\src).
// Every option name is cited to where it was verified:
//   [MH n]    refs\nucleus\app\handlers\MasterHandler.js line n
//   [RM n]    refs\nucleus\app\readme.txt line n
//   [PI n]    refs\nucleus\app\readme Proto Input.txt line n
//   [SRC f:n] refs\nucleus\src\<f> line n (repo HEAD, fetched 2026-10-03)
//   [HUB x]   a published hub handler using it (refs\nucleus\hub\all\<id>.nc). SM64 = Super Mario 64 rbTfwX2jB3G9MbMtW
//             (Glide + dgVoodoo, windowed, per-instance dgVoodoo.conf); RV = Re-Volt/RVGL Z6mco7mynDaqp8xrm (LAN racer)
// Design notes, open unknowns and the first-run test plan: README.md beside this file. Lab copies only.
//
// Facts this handler rests on:
// - Single instance: WinMain FindWindowA(class) -> exit. The STRLKUP.DLL proxy switch I76_MULTI_INSTANCE=1 skips it
//   [measured, lab]. Nucleus's own answers (HookInit, ProtoInput FindWindowHook) need startup injection, which
//   CMDLaunch does not do [SRC GenericGameHandler.cs:1669] [PI 136-138].
// - Joystick: the engine is WinMM-only (joyGetNumDevs/joyGetPosEx; no DirectInput or XInput import in i76.exe or
//   i76shell.dll; DINPUT is used only by i7_sfrce.dll for force feedback) [static, 2026-10-03]. Nucleus and Proto Input
//   hook XInput/DirectInput only, so NOTHING in Nucleus can route a pad to an instance. joystickN = winmm id N-1
//   (create 0x44ff90, "joystick%d" with id+1), but the open step uses winmm id (id != 0) for its caps and first poll,
//   so only joystick1/joystick2 open on their own [static 2026-10-05; live: README step 2]. Each instance keeps
//   joystick1 and gets I76_JOY_MAP=0=<its pad's winmm id> (proxy switch). Set JOY_WINMM below.
// - Keyboard: GetAsyncKeyState / GetKeyState through u32x.dll -> USER32 [static]. Global: every instance sees every
//   key unless Proto Input's key-state hooks are installed (input lock, End key).
// - Network: IPX via IPXWrapper 0.7.2 (WIPX socket 0x52A3, 5 s self-echo broadcast). Instance 2+ needs its own mutex
//   and HKCU key: one byte each in ipxwrapper.dll, patched per instance below [measured for 2 copies, lab doc 8.6].

// ---- owner settings ------------------------------------------------------------------------------------------
var JOY_WINMM = [15, 0, 1, 2]; // winmm id of each instance's pad (instance 0..3); 15 = none (the keyboard player).
                               // Every instance keeps input.map's joystick1; the proxy (I76_JOY_MAP=0=<id>, STRLKUP.DLL
                               // built 2026-10-05 or later) routes engine id 0 to this pad. Not joystickN per instance:
                               // the engine opens joystick2+ with winmm id 1's caps and first poll (0x4504b4, id != 0),
                               // so joystick3+ fail unless id 1 is present (README step 2). Plug the pads in, then list
                               // the ids (deck\probe, or README step 2's winmm one-liner).
var STOCK_JADE = true;         // lab copies carry a modded ADDON\valepre4.vcf that fails ValidateVcf
                               // (..\docs\MULTIPLAYER-CAR-CHECK.md); put ADDON\valepre4.orig (stock) in its place
var IPX_LOG_DEBUG = true;      // ipxwrapper.ini "logging = debug" per instance (first runs)
var BEST120 = [                // i76-everywhere\presets\best-120.psd1, Env block verbatim
  "I76_HIRES_CLOCK=1", "I76_FIXED_STEP=24", "I76_FRAMERATE_FIXES=1", "I76_ENGINE_DT_FIX=1", "I76_RENDER_INTERP=1",
  "I76_FIX_HEALTH_PCT=1", "I76_FIX_LABEL_TABLE=1", "I76_FAR_CLIP=1800", "I76_GLIDE_REFRESH=120",
  "I76_COLL_DEDUPE=0", "I76_AI_ROLL_HOLD=0"
];

// ---- game info -----------------------------------------------------------------------------------------------
Game.ExecutableName = "i76.exe";                       // [MH 28] [RM 19]
Game.ExecutableContext = ["i76shell.dll", "I76.ZFS"];  // [MH 1]
Game.BinariesFolder = "";                             // [MH 34] must be set: with CMDBatchBefore, Nucleus does exeFolder.Substring(0, len - BinariesFolder.Length) and a null value throws NullReferenceException (first run 2026-10-05; GenericGameHandler.cs:1904)
Game.GUID = "Interstate76";                            // [MH 30] letters only
Game.GameName = "Interstate '76 Gold Edition";         // [MH 31]
Game.MaxPlayers = 4;                                   // [MH 32] info only
Game.MaxPlayersOneMonitor = 4;                         // [MH 33] info only
Game.HandlerInterval = 100;                            // [MH 24]
Game.PauseBetweenStarts = 20;                          // [MH 54] [HUB RV 20, SM64 40]
Game.PromptBetweenInstances = true;                    // [RM 288] [HUB SM64]: start B only once A sits in its menu
Game.Description = "Lab handler. IPX LAN: instance 1 HOST > IPX > BROADCAST GAME, the others JOIN > IPX. " +
  "Walk the menus with input unlocked, then press End to lock input. Pads are chosen per instance by " +
  "(JOY_WINMM -> I76_JOY_MAP), not by the Nucleus device screen."; // [RM 305]

// ---- files: symlinked game; real copies of everything an instance writes or Game.Play edits ----------------------
Game.SymlinkGame = true;                               // [MH 25] [RM 45]
Game.SymlinkExe = false;                               // [MH 26] copy the exe
Game.SymlinkFolders = false;                           // [RM 47] folders created per instance, their files linked
Game.KeepSymLinkOnExit = true;                         // [RM 48] keep instance folders (saves) between runs
Game.FileSymlinkCopyInstead = [                        // [MH 18] [RM 56] [HUB SM64] real copies, not links
  "savegame.dir", "I76PLYR.DEF", "multicar.def", "input.map", "STRLKUP.DLL", "user.mel",
  "save000.cmp", "save001.cmp", "save002.cmp", "save003.cmp", "save004.cmp",
  "save005.cmp", "save006.cmp", "save007.cmp", "save008.cmp", "save009.cmp"
];
Game.FileSymlinkExclusions = [                         // [MH 13] [RM 55]; excluded = neither linked nor copied
  "dgVoodoo.conf",                                     //   [RM 1109]; Game.Play writes these per instance
  "ipxwrapper.dll", "wsock32.dll", "mswsock.dll", "ipxwrapper.ini", "ipxwrapper.log",
  "mciproxy.log"                                       //   the proxy's log: each instance writes its own (first run: one
];                                                     //   was written through a link into the source folder)

// ---- launch through cmd, so each instance gets its environment -----------------------------------------------
// Nucleus has no per-instance environment option. With CMDLaunch it writes one .cmd per instance: the
// NUCLEUS_* `set` lines (whenever CMDBatchBefore is non-empty), every CMDBatchBefore line ("i|line" = instance i
// only, 0-based), then `<CMDOptions[i]> "<exe>" <args>`, and runs it with cmd /c
// [SRC GenericGameHandler.cs:1849-1951, 2088-2106]. So `set` lines reach the game's environment.
Game.CMDLaunch = true;                                 // [RM 309]
Game.CMDStartArgsInside = true;                        // [RM 316] -> start "" /D "<dir>" "<exe>" -glide [SRC 1932-1941]
Game.CMDOptions = [                                    // [RM 310] one per instance; `start` returns at once
  "start \"\" /D \"%NUCLEUS_INST_EXE_FOLDER%\"", "start \"\" /D \"%NUCLEUS_INST_EXE_FOLDER%\"",
  "start \"\" /D \"%NUCLEUS_INST_EXE_FOLDER%\"", "start \"\" /D \"%NUCLEUS_INST_EXE_FOLDER%\""
];
Game.StartArguments = "-glide";                        // [MH 37]
Game.CMDBatchBefore = (function () {                   // [RM 311] [RM 515-521 for the NUCLEUS_* variables]
  var l = ["set I76_MULTI_INSTANCE=1",
           // the game minimises itself on WM_ACTIVATEAPP 0 (0x404acc); a minimised host is not found by the joiner.
           // Proxy switch (STRLKUP.DLL 2026-10-05 or later, i76-everywhere music-fix README); logs "no-minimize: ..."
           "set I76_NO_MINIMIZE=1",
           // the trainer's shared block has one name (Local\I76Trainer): two instances would open the same one
           "set I76_TRAINER=0"];
  for (var i = 0; i < BEST120.length; i++) l.push("set " + BEST120[i]);
  // per-instance values (I76_ASPECT) from the file Game.Play writes into this instance's folder:
  l.push("for /f \"usebackq eol=# tokens=1* delims==\" %%a in (\"%NUCLEUS_INST_EXE_FOLDER%\\i76-nucleus.env\") do set \"%%a=%%b\"");
  return l;
})();
Game.ForceProcessSearch = true;                        // [RM 295] (CMDLaunch forces a search anyway [SRC 2360])

// ---- windows -------------------------------------------------------------------------------------------------
Game.SupportsPositioning = true;                       // [MH 41]
Game.Hook.ForceFocus = false;                          // [MH 42] no x360ce custom dll
Game.Hook.ForceFocusWindowName = "Interstate '76 Gold Edition"; // [MH 43] string in i76.exe; live title UNVERIFIED
Game.HasDynamicWindowTitle = true;                     // [RM 110] [HUB SM64] match on that text, not 1:1
Game.SetWindowHook = true;                             // [RM 129] stop the game/dgVoodoo resizing back
Game.ResetWindows = true;                              // [RM 138] [HUB SM64]
Game.KeepAspectRatio = false;                          // [RM 137]
Game.ProtoInput.SetWindowPosHook = true;               // [RM 384]

// ---- input ---------------------------------------------------------------------------------------------------
// Pads: no Nucleus hook reaches winmm (see top). The device screen still wants one device per screen; DInput and
// XInput are enabled only so pads show up there. No x360ce, XInputPlus, devreorder (a dinput8 wrapper).
Game.Hook.DInputEnabled = true;                        // [MH 44] [HUB RV, SM64]
Game.Hook.DInputForceDisable = false;                  // [MH 45]
Game.Hook.XInputEnabled = true;                        // [MH 46]
Game.Hook.XInputReroute = false;                       // [MH 47]
Game.Hook.CustomDllEnabled = false;                    // [MH 53] [HUB RV, SM64]
Game.UseDevReorder = false;                            // [RM 167]
Game.SupportsKeyboard = true;                          // [MH 27] [RM 161] one keyboard player
Game.KeyboardPlayerFirst = true;                       // [RM 163] keyboard player = instance 0 = the IPX host
Game.SupportsMultipleKeyboardsAndMice = true;          // [PI 59] [PI 254]
// Proto Input, after the template at [PI 254-281]: runtime injection (startup injection is skipped with CMDLaunch),
// key-state hooks only while input is locked so the menus can be walked with the real mouse first.
Game.HookSetCursorPos = false; Game.HookGetCursorPos = false; Game.HookGetKeyState = false;   // [PI 255]: deprecated
Game.HookGetAsyncKeyState = false; Game.HookGetKeyboardState = false; Game.HookFilterRawInput = false; // options,
Game.HookFilterMouseMessages = false; Game.HookUseLegacyInput = false;                         // must be false
Game.HookDontUpdateLegacyInMouseMsg = false; Game.HookMouseVisibility = false;
Game.SendNormalMouseInput = false; Game.SendNormalKeyboardInput = false; Game.SendScrollWheel = false;
Game.ForwardRawKeyboardInput = false; Game.ForwardRawMouseInput = false; Game.DrawFakeMouseCursor = false;
Game.LockInputAtStart = false;                         // [PI 256]
Game.LockInputToggleKey = 0x23;                        // [PI 256] [RM 376] End
Game.ProtoInput.FreezeExternalInputWhenInputNotLocked = true; // [PI 64] [PI 256]
Game.ProtoInput.InjectStartup = false;                 // [PI 257]
Game.ProtoInput.InjectRuntime_EasyHookMethod = true;   // [PI 257] [SRC GenericGameHandler.cs:2621-2630]
Game.ProtoInput.InjectRuntime_RemoteLoadMethod = false;
Game.ProtoInput.InjectRuntime_EasyHookStealthMethod = false;
Game.ProtoInput.RegisterRawInputHook = true;           // [PI 71] [PI 258]
Game.ProtoInput.GetRawInputDataHook = true;            // [PI 74] [PI 259]
Game.ProtoInput.MessageFilterHook = true;              // [PI 77] [PI 260]
Game.ProtoInput.ClipCursorHook = true;                 // [PI 99] lab doc s.5/8.3: two copies fought over ClipCursor
Game.ProtoInput.ClipCursorHookCreatesFakeClip = true;  // [PI 100]
Game.ProtoInput.FocusHooks = true;                     // [PI 103]
Game.ProtoInput.SendKeyboardButtonMessages = true;     // [PI 261]
Game.ProtoInput.DrawFakeCursor = false;                // [PI 263]
Game.ProtoInput.BlockedMessages = [0x0008];            // [PI 264] WM_KILLFOCUS
Game.ProtoInput.XinputHook = false;                    // [PI 110] the game has no XInput
Game.ProtoInput.OnInputLocked = function () {          // [PI 270-273], trimmed to keyboard + focus
  for (var i = 0; i < PlayerList.Count; i++) {
    var p = PlayerList[i];
    ProtoInput.InstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.GetKeyStateHookID);
    ProtoInput.InstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.GetAsyncKeyStateHookID);
    ProtoInput.InstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.GetKeyboardStateHookID);
    ProtoInput.InstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.FocusHooksHookID);
    ProtoInput.EnableMessageFilter(p.ProtoInputInstanceHandle, ProtoInput.Values.KeyboardButtonFilterID);
    ProtoInput.EnableMessageFilter(p.ProtoInputInstanceHandle, ProtoInput.Values.WindowActivateFilterID);
    ProtoInput.EnableMessageFilter(p.ProtoInputInstanceHandle, ProtoInput.Values.WindowActivateAppFilterID);
    ProtoInput.StartFocusMessageLoop(p.ProtoInputInstanceHandle, 5, true, true, true, true, true);
    ProtoInput.SetRawInputBypass(p.ProtoInputInstanceHandle, false);
  }
};
Game.ProtoInput.OnInputUnlocked = function () {        // [PI 275-281]
  for (var i = 0; i < PlayerList.Count; i++) {
    var p = PlayerList[i];
    ProtoInput.UninstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.GetKeyStateHookID);
    ProtoInput.UninstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.GetAsyncKeyStateHookID);
    ProtoInput.UninstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.GetKeyboardStateHookID);
    ProtoInput.UninstallHook(p.ProtoInputInstanceHandle, ProtoInput.Values.FocusHooksHookID);
    ProtoInput.DisableMessageFilter(p.ProtoInputInstanceHandle, ProtoInput.Values.KeyboardButtonFilterID);
    ProtoInput.DisableMessageFilter(p.ProtoInputInstanceHandle, ProtoInput.Values.WindowActivateFilterID);
    ProtoInput.DisableMessageFilter(p.ProtoInputInstanceHandle, ProtoInput.Values.WindowActivateAppFilterID);
    ProtoInput.StopFocusMessageLoop(p.ProtoInputInstanceHandle);
    ProtoInput.SetRawInputBypass(p.ProtoInputInstanceHandle, true);
  }
};

// ---- per instance, before its launch (Play runs before launch unless GamePlayAfterLaunch [SRC 1535-1567]) --------
Game.Play = function () {
  var dir = Context.GetFolder(Nucleus.Folder.InstancedGameFolder);   // [MH 81] [RM 401]
  var id = Context.PlayerID;                                         // [RM 249] [SRC GenericContext.cs:59] 0-based
  var w = Context.Width, h = Context.Height;                         // [MH 65] [SRC GenericContext.cs:141-142]
  Context.Log("I76: instance " + id + " dir " + dir + " " + w + "x" + h + " handler folder " + Game.Folder); // [RM 471]

  // 1. dgVoodoo: the windowed, borderless template (handler folder; copy pattern [MH 91-93], [HUB SM64]) with the
  //    Glide buffer = this window. Wider than 4:3 -> Hor+ (I76_ASPECT, range 1.34..3.6 in strlkproxy.c apply_aspect)
  //    and plain stretch; otherwise stock 4:3 field, stretched_ar.
  var conf = dir + "\\dgVoodoo.conf";
  System.IO.File.Copy(System.IO.Path.Combine(Game.Folder, "dgVoodoo.conf"), conf, true);
  var wide = (w / h) >= 1.34;
  Context.EditTextFile(conf,                                         // [RM 475] [SRC GenericContext.cs:1441-1482]
    ["Resolution                          = 3840x2880", "ScalingMode"],
    ["Resolution                          = " + w + "x" + h,
     "ScalingMode                          = " + (wide ? "stretched" : "stretched_ar")],
    "us-ascii");                                                     // "utf-8" would write a BOM

  // 2. this instance's own environment, read by the for /f line in CMDBatchBefore
  var env = ["# Interstate76.js, instance " + id];
  if (wide) env.push("I76_ASPECT=" + w + "x" + h);
  env.push("I76_JOY_MAP=0=" + JOY_WINMM[id]);                  // this instance's pad -> its joystick1
  Context.WriteTextFile(dir + "\\i76-nucleus.env", env);             // [RM 241] [SRC GenericContext.cs:1082] (no BOM)

  // 3. input.map (a real copy) stays as it is: every instance binds joystick1; I76_JOY_MAP (step 2) picks the pad.

  // 4. IPXWrapper 0.7.2 from the handler folder. Instance id > 0 gets its own named-mutex prefix and HKCU key:
  //    "ipxwrapper_socket_%hu" (file 0x1BEAC '_') and "Software\IPXWrapper" (file 0x1CB7C 'r') -> letter 'A'+id.
  //    id 1 -> 'B' = exactly the lab's autotest\ipx-setup.ps1 patch. Read back; abort the instance on a mismatch.
  var ipxFiles = ["ipxwrapper.dll", "wsock32.dll", "mswsock.dll"];
  for (var f = 0; f < ipxFiles.length; f++)
    System.IO.File.Copy(System.IO.Path.Combine(Game.Folder, ipxFiles[f]), dir + "\\" + ipxFiles[f], true); // [MH 93]
  var ipx = dir + "\\ipxwrapper.dll";
  var b = System.IO.File.ReadAllBytes(ipx);
  if (b[0x1BEAC] != 0x5F || b[0x1CB7C] != 0x72) throw "I76: ipxwrapper.dll is not stock 0.7.2 (md5 06a01d0f)";
  if (id > 0) {
    var letter = 0x41 + id;
    Context.HexEdit(ipx, "1BEAC", [letter]);                         // [RM 456] [SRC GenericContext.cs:1621-1637]
    Context.HexEdit(ipx, "1CB7C", [letter]);
    b = System.IO.File.ReadAllBytes(ipx);
    if (b[0x1BEAC] != letter || b[0x1CB7C] != letter) throw "I76: ipxwrapper.dll patch did not land";
  }
  Context.WriteTextFile(dir + "\\ipxwrapper.ini",
    ["; Interstate76.js instance " + id, IPX_LOG_DEBUG ? "logging = debug" : "logging = info"]);

  // 5. car data that passes ValidateVcf. Delete the link first, then copy: copying onto a symlink would write
  //    through to the source install.
  if (STOCK_JADE) {
    var vcf = dir + "\\ADDON\\valepre4.vcf", orig = dir + "\\ADDON\\valepre4.orig";
    if (System.IO.File.Exists(orig)) {
      if (System.IO.File.Exists(vcf)) System.IO.File.Delete(vcf);
      System.IO.File.Copy(orig, vcf, true);
    } else Context.Log("I76: ADDON\\valepre4.orig missing; car data left as it is");
  }
};
