// census.js - runbook item 004 (call census). Loaded by tools/frida_run.py into an ALREADY RUNNING
// 32-bit process (attach, never spawn: H10). Nothing here writes to game memory.
//
// Method: one Interceptor hook per target function whose onEnter is a CModule (TinyCC) callback that does
// `lock incl [counter]` on a preallocated per-function u32 (no JavaScript on the hot path). Every
// `snapshot_ms` the timer reads the whole counter block plus the sim frame counter (0x5a7e1c, class bss,
// u32) and game time (0x5a7e74, class bss, f32) and sends them to the driver, which writes
// census/snapshots.csv + census/counts.csv; tools/census_classify.py turns deltas per snapshot into rate
// classes per sim frame.
//
// rpc API (called by the driver):
//   init({n, frame_addr, time_addr, snapshot_ms})  allocate n counters, compile the CModule
//   attach([[idx, "0x..."], ...])                   hook a batch; returns {attached, errors:[{idx,addr,error}], ms}
//   start() / stop()                                 snapshot timer; stop() sends a final snapshot and returns totals
//   counters()                                       current per-slot counts (array of n u32)
//   reset()                                          zero the counters (self-test, after bench)
//   detachAll()                                      Interceptor.detachAll()
//   pickExports([[module, prefix, n], ...])         test targets (notepad): exported functions of a module
//   bench(addr, n)                                   call addr n times via NativeFunction (overhead probe)
//   testSetup({tick_ms, per_tick, per_frame_x3, event_every, fn})  fake frame/time cells + a synthetic
//                                                    tick that calls hooked functions at known rates (G-POS)
'use strict';

var C_SRC = [
  '#include <gum/guminterceptor.h>',
  '',
  'void on_enter(GumInvocationContext *ic) {',
  '  unsigned int *c = (unsigned int *) gum_invocation_context_get_listener_function_data(ic);',
  '  __asm__ __volatile__("lock incl (%0)" : : "r"(c) : "memory");',
  '}',
].join('\n');

var cfg = null;
var counters = null;   // NativePointer to n * u32
var cm = null;
var listeners = {};    // idx -> InvocationListener
var timer = null;
var snapIndex = 0;
var t_start = 0;

function readFrame() {
  if (!cfg.frame_addr) return null;
  try { return ptr(cfg.frame_addr).readU32(); } catch (e) { return null; }
}
function readTime() {
  if (!cfg.time_addr) return null;
  try { return ptr(cfg.time_addr).readFloat(); } catch (e) { return null; }
}

function snapshot(final_) {
  var t = Date.now();
  var frame = readFrame();
  var gtime = readTime();
  var bytes = counters.readByteArray(4 * cfg.n);
  send({ type: 'snap', snap: snapIndex, t_ms: t, frame: frame, gtime: gtime, final: !!final_ }, bytes);
  snapIndex++;
}

rpc.exports = {
  init: function (c) {
    cfg = c;
    if (!(cfg.n > 0)) throw new Error('init: n must be > 0');
    counters = Memory.alloc(4 * cfg.n);
    // Memory.alloc pages are zeroed; make it explicit.
    counters.writeByteArray(new Array(4 * cfg.n).fill(0));
    var t0 = Date.now();
    cm = new CModule(C_SRC);
    return { arch: Process.arch, pointerSize: Process.pointerSize, counters: counters.toString(),
             on_enter: cm.on_enter.toString(), cmodule_ms: Date.now() - t0, n: cfg.n };
  },

  attach: function (batch) {
    var t0 = Date.now();
    var errors = [];
    var attached = 0;
    for (var i = 0; i < batch.length; i++) {
      var idx = batch[i][0], addr = batch[i][1];
      try {
        listeners[idx] = Interceptor.attach(ptr(addr), cm.on_enter, counters.add(4 * idx));
        attached++;
      } catch (e) {
        errors.push({ idx: idx, addr: addr, error: String(e) });
      }
    }
    Interceptor.flush();
    return { attached: attached, errors: errors, ms: Date.now() - t0 };
  },

  start: function () {
    if (timer !== null) return { already: true };
    t_start = Date.now();
    snapshot(false);
    timer = setInterval(function () { snapshot(false); }, cfg.snapshot_ms || 1000);
    return { started_ms: t_start };
  },

  stop: function () {
    if (timer !== null) { clearInterval(timer); timer = null; }
    snapshot(true);
    var counts = this.counters();
    var total = 0, nonzero = 0;
    for (var i = 0; i < counts.length; i++) { total += counts[i]; if (counts[i] > 0) nonzero++; }
    return { snapshots: snapIndex, fired_total: total, hooks_fired_nonzero: nonzero, seconds: (Date.now() - t_start) / 1000 };
  },

  counters: function () {
    var out = new Array(cfg.n);
    for (var i = 0; i < cfg.n; i++) out[i] = counters.add(4 * i).readU32();
    return out;
  },

  reset: function () {
    // zero every counter (used after the overhead bench in the notepad self-test)
    counters.writeByteArray(new Array(4 * cfg.n).fill(0));
    return true;
  },

  detachAll: function () {
    Interceptor.detachAll();
    listeners = {};
    return true;
  },

  pickExports: function (specs) {
    // specs: [[module, prefix, n]]; returns [{addr, name, module}] for exported *functions* only.
    var out = [];
    var seen = {};
    for (var s = 0; s < specs.length; s++) {
      var m = Process.getModuleByName(specs[s][0]);
      var prefix = specs[s][1] || '';
      var n = specs[s][2];
      var exps = m.enumerateExports();
      exps.sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });
      var k = 0;
      for (var i = 0; i < exps.length && k < n; i++) {
        var e = exps[i];
        if (e.type !== 'function') continue;
        if (prefix && e.name.indexOf(prefix) !== 0) continue;
        var key = e.address.toString();
        if (seen[key]) continue;   // forwarders / aliases resolve to one address
        seen[key] = true;
        out.push({ addr: key, name: m.name + '!' + e.name, module: m.name });
        k++;
      }
    }
    return out;
  },

  bench: function (addr, n) {
    var f = new NativeFunction(ptr(addr), 'uint32', []);
    var t0 = Date.now();
    for (var i = 0; i < n; i++) f();
    return { n: n, ms: Date.now() - t0 };
  },

  testSetup: function (o) {
    // Synthetic tick for the notepad self-test: a fake frame counter (u32) and game time (f32) that
    // advance every tick_ms, and hooked functions called at known rates: per_tick once per tick,
    // per_frame_x3 three times per tick, event a burst of 20 calls every `event_every` ticks.
    var frameCell = Memory.alloc(8);
    frameCell.writeU32(0); frameCell.add(4).writeFloat(0.0);
    cfg.frame_addr = frameCell.toString();
    cfg.time_addr = frameCell.add(4).toString();
    var fns = {};
    ['per_tick', 'per_frame_x3', 'event'].forEach(function (k) {
      if (o[k]) fns[k] = new NativeFunction(ptr(o[k]), 'uint32', []);
    });
    var tick = 0;
    var dt = (o.tick_ms || 50) / 1000.0;
    setInterval(function () {
      tick++;
      frameCell.writeU32(tick);
      frameCell.add(4).writeFloat(tick * dt);
      if (fns.per_tick) fns.per_tick();
      if (fns.per_frame_x3) { fns.per_frame_x3(); fns.per_frame_x3(); fns.per_frame_x3(); }
      if (fns.event && (tick % (o.event_every || 45)) === 0) { for (var b = 0; b < 20; b++) fns.event(); }  // burst of 20
    }, o.tick_ms || 50);
    return { frame_addr: cfg.frame_addr, time_addr: cfg.time_addr };
  },
};
