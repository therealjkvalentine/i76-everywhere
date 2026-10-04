// ledger.js - runbook item 005 (allocation ledger). Loaded by tools/frida_run.py into an ALREADY RUNNING
// 32-bit process (attach, never spawn: H10). Read-only instrument: nothing here writes game memory.
//
// Hooks (installed by the driver through `hook`): kernel32 HeapCreate/HeapAlloc/HeapReAlloc/HeapFree/
// HeapDestroy (the export addresses the IAT slots 0x4bc110/0x4bc108/0x4bc0e4/0x4bc104/0x4bc10c resolve to;
// on Windows 10 kernel32!HeapAlloc is a forwarder to ntdll!RtlAllocateHeap, so the hook sits in ntdll and
// sees every heap allocation in the process), msvcrt malloc/free/realloc, operator new ??2@YAPAXI@Z /
// delete ??3@YAXPAX@Z, and in-exe functions: pool_Reserve 0x498940, pool_Free 0x498a00, the HeapAlloc
// wrapper heap_5a7cc0_alloc 0x499ce0 and any other heap_*_alloc wrapper the driver lists.
//
// Every record is written by C (CModule): on_enter stores the arguments in per-invocation data and bumps
// the hook's fired counter (G-ATTEST); on_leave takes a ring slot with `lock xadd` and writes
// {seq, src, key, size, extra, result, ra, frame, tid}. `frame` is *(u32*)frame_addr (0x5a7e1c, bss) read
// at on_leave time. When only_text=1 a record whose return address lies outside [text_lo, text_hi) is not
// written (it is counted in the hook's `fired_other` counter): that drops the ntdll/msvcrt-internal
// HeapAlloc calls under malloc/new so each game allocation appears once at its outermost game call site
// (wrappers such as 0x499ce0 still yield a nested pair; ledger_types.py collapses those).
//
// The JS side drains the ring every drain_ms and sends the new records as bytes (36 B each) with the host
// time, the frame counter, game time and the optional `watch` cells (pool watermarks 0x6442ec / 0x654380).
//
// rpc API: init({frame_addr, time_addr, ring_records, drain_ms, only_text, text_lo, text_hi, watch: [..]})
//          hook([{id, name, addr, kind}])  -> {attached, errors}
//          start() / stop() -> {drains, written, dropped, fired: [{id, name, fired, fired_other}]}
//          detachAll()
'use strict';

var KIND = {           // argument layout per source kind (see on_enter)
  'heap-create': 1,    // HeapCreate(flOptions, dwInitialSize, dwMaximumSize) -> handle
  'heap-alloc': 2,     // HeapAlloc(hHeap, dwFlags, dwBytes) -> ptr
  'heap-realloc': 3,   // HeapReAlloc(hHeap, dwFlags, lpMem, dwBytes) -> ptr
  'heap-free': 4,      // HeapFree(hHeap, dwFlags, lpMem) -> BOOL
  'heap-destroy': 5,   // HeapDestroy(hHeap) -> BOOL
  'malloc': 6,         // malloc(size) -> ptr
  'free': 7,           // free(ptr)
  'realloc': 8,        // realloc(ptr, size) -> ptr
  'new': 9,            // operator new(size) -> ptr
  'delete': 10,        // operator delete(ptr)
  'pool-reserve': 11,  // pool_Reserve(size, minsize) -> base (VirtualAlloc reserve+commit)
  'pool-free': 12,     // pool_Free(base)
  'wrapper-alloc': 13, // heap_<handle>_alloc(size) -> ptr; key = *(u32*)key_addr (the heap handle global)
};

var C_SRC = [
  '#include <gum/guminterceptor.h>',
  'typedef struct { unsigned int seq, src, key, size, extra, result, ra, frame, tid; } rec_t;   /* 36 B */',
  'typedef struct { unsigned int id, kind, key_addr, fired, fired_other, pad; } hook_t;',
  'extern rec_t ring[];',
  'extern unsigned int ring_w;',
  'extern unsigned int ring_mask;',
  'extern unsigned int frame_addr;',
  'extern unsigned int only_text;',
  'extern unsigned int text_lo;',
  'extern unsigned int text_hi;',
  '',
  'static unsigned int arg(GumInvocationContext *ic, unsigned int i) {',
  '  return (unsigned int) gum_invocation_context_get_nth_argument(ic, i);',
  '}',
  '',
  'void on_enter(GumInvocationContext *ic) {',
  '  hook_t *h = (hook_t *) gum_invocation_context_get_listener_function_data(ic);',
  '  unsigned int *d = (unsigned int *) gum_invocation_context_get_listener_invocation_data(ic, 16);',
  '  unsigned int *f = &h->fired;',
  '  __asm__ __volatile__("lock incl (%0)" : : "r"(f) : "memory");',
  '  d[0] = (unsigned int) gum_invocation_context_get_return_address(ic);',
  '  d[1] = 0; d[2] = 0; d[3] = 0;',
  '  switch (h->kind) {',
  '    case 1:  d[2] = arg(ic, 1); d[3] = arg(ic, 2); break;',
  '    case 2:  d[1] = arg(ic, 0); d[2] = arg(ic, 2); break;',
  '    case 3:  d[1] = arg(ic, 0); d[2] = arg(ic, 3); d[3] = arg(ic, 2); break;',
  '    case 4:  d[1] = arg(ic, 0); d[3] = arg(ic, 2); break;',
  '    case 5:  d[1] = arg(ic, 0); break;',
  '    case 6:  d[2] = arg(ic, 0); break;',
  '    case 7:  d[3] = arg(ic, 0); break;',
  '    case 8:  d[3] = arg(ic, 0); d[2] = arg(ic, 1); break;',
  '    case 9:  d[2] = arg(ic, 0); break;',
  '    case 10: d[3] = arg(ic, 0); break;',
  '    case 11: d[2] = arg(ic, 0); d[3] = arg(ic, 1); break;',
  '    case 12: d[3] = arg(ic, 0); break;',
  '    case 13: d[2] = arg(ic, 0); if (h->key_addr) d[1] = *(unsigned int *) h->key_addr; break;',
  '    default: break;',
  '  }',
  '}',
  '',
  'void on_leave(GumInvocationContext *ic) {',
  '  hook_t *h = (hook_t *) gum_invocation_context_get_listener_function_data(ic);',
  '  unsigned int *d = (unsigned int *) gum_invocation_context_get_listener_invocation_data(ic, 16);',
  '  unsigned int ra = d[0];',
  '  if (only_text && (ra < text_lo || ra >= text_hi)) {',
  '    unsigned int *fo = &h->fired_other;',
  '    __asm__ __volatile__("lock incl (%0)" : : "r"(fo) : "memory");',
  '    return;',
  '  }',
  '  unsigned int i = 1;',
  '  unsigned int *w = &ring_w;',
  '  __asm__ __volatile__("lock xaddl %0, (%1)" : "+r"(i) : "r"(w) : "memory");',
  '  rec_t *r = &ring[i & ring_mask];',
  '  r->seq = i; r->src = h->id; r->key = d[1]; r->size = d[2]; r->extra = d[3];',
  '  r->result = (unsigned int) gum_invocation_context_get_return_value(ic);',
  '  r->ra = ra;',
  '  r->frame = frame_addr ? *(unsigned int *) frame_addr : 0;',
  '  r->tid = (unsigned int) gum_invocation_context_get_thread_id(ic);',
  '}',
].join('\n');

var REC = 36, HOOK = 24;
var cfg = null, cm = null;
var ring = null, ringW = null, ringMask = null, frameCell = null, onlyText = null, textLo = null, textHi = null;
var hooks = [];       // {id, name, addr, kind, data(NativePointer), listener}
var hookMem = null;
var timer = null;
var readIdx = 0;      // next seq to read
var drains = 0, written = 0, dropped = 0;
var t_start = 0;

function readU32(a) { try { return ptr(a).readU32(); } catch (e) { return null; } }
function readF32(a) { try { return ptr(a).readFloat(); } catch (e) { return null; } }

function drain(final_) {
  var t = Date.now();
  var w = ringW.readU32();
  var n = w - readIdx;
  var lost = 0;
  if (n > cfg.ring_records) { lost = n - cfg.ring_records; readIdx = w - cfg.ring_records; n = cfg.ring_records; }
  dropped += lost;
  var watch = [];
  for (var i = 0; i < cfg.watch.length; i++) watch.push(readU32(cfg.watch[i]));
  var head = { type: 'led', drain: drains, t_ms: t, frame: cfg.frame_addr ? readU32(cfg.frame_addr) : null,
               gtime: cfg.time_addr ? readF32(cfg.time_addr) : null, r: readIdx, w: w, n: n, dropped_now: lost,
               watch: watch, final: !!final_ };
  if (n === 0) { send(head, null); drains++; return; }
  // copy [readIdx, w) which may wrap
  var a = readIdx & (cfg.ring_records - 1), b = w & (cfg.ring_records - 1);
  var bytes;
  if (a < b || (a === b && n === cfg.ring_records && a === 0)) {
    bytes = ring.add(a * REC).readByteArray(n * REC);
  } else {
    var first = ring.add(a * REC).readByteArray((cfg.ring_records - a) * REC);
    var second = ring.readByteArray(b * REC);
    var joined = new Uint8Array(first.byteLength + second.byteLength);
    joined.set(new Uint8Array(first), 0); joined.set(new Uint8Array(second), first.byteLength);
    bytes = joined.buffer;
  }
  readIdx = w;
  written += n;
  send(head, bytes);
  drains++;
}

rpc.exports = {
  init: function (c) {
    cfg = c;
    cfg.ring_records = cfg.ring_records || 65536;
    if ((cfg.ring_records & (cfg.ring_records - 1)) !== 0) throw new Error('ring_records must be a power of two');
    cfg.watch = cfg.watch || [];
    ring = Memory.alloc(REC * cfg.ring_records);
    ringW = Memory.alloc(4); ringW.writeU32(0);
    ringMask = Memory.alloc(4); ringMask.writeU32(cfg.ring_records - 1);
    frameCell = Memory.alloc(4); frameCell.writeU32(cfg.frame_addr ? ptr(cfg.frame_addr).toUInt32() : 0);
    onlyText = Memory.alloc(4); onlyText.writeU32(cfg.only_text ? 1 : 0);
    textLo = Memory.alloc(4); textLo.writeU32(ptr(cfg.text_lo || '0').toUInt32());
    textHi = Memory.alloc(4); textHi.writeU32(ptr(cfg.text_hi || '0').toUInt32());
    hookMem = Memory.alloc(HOOK * 64);
    var t0 = Date.now();
    cm = new CModule(C_SRC, { ring: ring, ring_w: ringW, ring_mask: ringMask, frame_addr: frameCell,
                              only_text: onlyText, text_lo: textLo, text_hi: textHi });
    return { arch: Process.arch, ring: ring.toString(), ring_bytes: REC * cfg.ring_records, cmodule_ms: Date.now() - t0,
             on_enter: cm.on_enter.toString(), on_leave: cm.on_leave.toString() };
  },

  resolveExport: function (module, name) {
    try { return Process.getModuleByName(module).getExportByName(name).toString(); }
    catch (e) { return null; }
  },

  hook: function (list) {
    var errors = [], attached = 0;
    for (var i = 0; i < list.length; i++) {
      var h = list[i];
      if (hooks.length >= 64) { errors.push({ id: h.id, addr: h.addr, error: 'hook table full (64)' }); continue; }
      var kind = KIND[h.kind];
      if (!kind) { errors.push({ id: h.id, addr: h.addr, error: 'unknown kind ' + h.kind }); continue; }
      var data = hookMem.add(HOOK * hooks.length);
      data.writeU32(h.id); data.add(4).writeU32(kind);
      data.add(8).writeU32(h.key_addr ? ptr(h.key_addr).toUInt32() : 0);
      data.add(12).writeU32(0); data.add(16).writeU32(0); data.add(20).writeU32(0);
      try {
        var l = Interceptor.attach(ptr(h.addr), { onEnter: cm.on_enter, onLeave: cm.on_leave }, data);
        hooks.push({ id: h.id, name: h.name, addr: h.addr, kind: h.kind, data: data, listener: l });
        attached++;
      } catch (e) {
        errors.push({ id: h.id, addr: h.addr, error: String(e) });
      }
    }
    Interceptor.flush();
    return { attached: attached, errors: errors };
  },

  start: function () {
    if (timer !== null) return { already: true };
    t_start = Date.now();
    timer = setInterval(function () { drain(false); }, cfg.drain_ms || 250);
    return { started_ms: t_start };
  },

  fired: function () {
    return hooks.map(function (h) {
      return { id: h.id, name: h.name, addr: h.addr, kind: h.kind, fired: h.data.add(12).readU32(), fired_other: h.data.add(16).readU32() };
    });
  },

  stop: function () {
    if (timer !== null) { clearInterval(timer); timer = null; }
    drain(true);
    return { drains: drains, written: written, dropped: dropped, ring_w: ringW.readU32(),
             seconds: (Date.now() - t_start) / 1000, fired: this.fired() };
  },

  detachAll: function () { Interceptor.detachAll(); hooks = []; return true; },

  // notepad self-test: allocate/free through the process heap and msvcrt so the ring has known content
  testAlloc: function (n) {
    var k32 = Process.getModuleByName('kernel32.dll');
    var gph = new NativeFunction(k32.getExportByName('GetProcessHeap'), 'pointer', []);
    var HA = new NativeFunction(k32.getExportByName('HeapAlloc'), 'pointer', ['pointer', 'uint', 'uint']);
    var HF = new NativeFunction(k32.getExportByName('HeapFree'), 'int', ['pointer', 'uint', 'pointer']);
    var heap = gph();
    var ptrs = [];
    for (var i = 0; i < n; i++) ptrs.push(HA(heap, 0, 64 + (i % 4) * 16));
    for (var j = 0; j < ptrs.length; j += 2) HF(heap, 0, ptrs[j]);   // free every other one
    var m = Process.findModuleByName('msvcrt.dll');
    var crt = 0;
    if (m) {
      var ma = new NativeFunction(m.getExportByName('malloc'), 'pointer', ['uint']);
      var fr = new NativeFunction(m.getExportByName('free'), 'void', ['pointer']);
      for (var q = 0; q < n; q++) { var p = ma(100 + q); fr(p); crt++; }
    }
    return { heap: heap.toString(), heap_allocs: n, heap_frees: Math.ceil(n / 2), crt_pairs: crt };
  },
};
