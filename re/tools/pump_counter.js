// pump_counter.js - Frida script: count message-pump calls (PeekMessageA) for the paused canary (H4, G-ATTEST).
//
// Loaded by tools\snapshot.py --pump (frida.attach, never spawn: H10). Parameters come in through
// rpc.exports.start(cfg): { slot: "0x4bc350", text_lo: "0x401000", text_hi: "0x4bbe55",
//                           fallback_module: "user32.dll", fallback_export: "PeekMessageA" }.
// The slot is the IAT entry named PeekMessageA in symbols\imports.tsv (class iat). The hook target is
// the function the slot points to (whatever module resolved it: user32 or the u32x proxy), read from the
// live process; when the slot is not inside a loaded module (a throwaway process such as notepad) the
// export named by fallback_module/fallback_export is hooked instead, and the record says so.
// Calls whose return address lies in the exe's .text are the exe's own pump (`text`); every other caller
// (shell, dgVoodoo, CRT) is `other`. Nothing is written into the target.
var counts = { text: 0, other: 0 };
var sites = {};
var info = { installed: false };

rpc.exports = {
  start: function (cfg) {
    var lo = ptr(cfg.text_lo), hi = ptr(cfg.text_hi);
    var target = null, how = null;
    try {
      var slot = ptr(cfg.slot);
      var m = Process.findModuleByAddress(slot);
      if (m !== null) {
        var t = slot.readPointer();
        var tm = Process.findModuleByAddress(t);
        if (tm !== null) { target = t; how = 'iat-slot ' + cfg.slot + ' -> ' + tm.name + '+' + t.sub(tm.base).toString(); }
      }
    } catch (e) { info.slot_error = '' + e; }
    if (target === null) {
      var mod = Process.findModuleByName(cfg.fallback_module);
      if (mod === null) { info.error = 'fallback module ' + cfg.fallback_module + ' not loaded'; return info; }
      target = mod.findExportByName(cfg.fallback_export);
      if (target === null) { info.error = 'export ' + cfg.fallback_export + ' not found'; return info; }
      how = 'fallback export ' + cfg.fallback_module + '!' + cfg.fallback_export + ' (slot not in a loaded module)';
    }
    Interceptor.attach(target, {
      onEnter: function (args) {
        var ra = this.returnAddress;
        if (ra.compare(lo) >= 0 && ra.compare(hi) < 0) {
          counts.text++;
          var k = ra.toString();
          sites[k] = (sites[k] || 0) + 1;
        } else {
          counts.other++;
        }
      }
    });
    info.installed = true;
    info.target = target.toString();
    info.how = how;
    info.arch = Process.arch;
    return info;
  },
  counts: function () { return { text: counts.text, other: counts.other, sites: sites }; },
  info: function () { return info; }
};
