// node tools/tests/test-save-editor-cmp.mjs [--json] <save*.cmp | *.spc | savegame.dir>...
//
// Runs the browser editor's .cmp / savegame.dir parsers (extracted verbatim from i76-save-editor.html)
// over real files.  Without --json: self-checks (frame, round-trip identity of withRepairQueue on an
// unedited file, queue rebuild after a state edit) and exit 1 on any failure.  With --json: prints the
// same shape i76-save-editor.py --json prints, so tests/test_save_editor.py can diff the two parsers
// field by field (the HTML and the Python must stay in lockstep).
import fs from "node:fs";
import path from "node:path";
const html = fs.readFileSync(new URL("../../i76-save-editor.html", import.meta.url), "utf8");
const grab = (start, end) => {
  const i = html.indexOf(start); const j = html.indexOf(end, i);
  if (i < 0 || j < 0) throw new Error("missing " + start);
  return html.slice(i, j);
};
const src = [
  grab("function cstr(", "\n"), grab("function u32(", "\n"), grab("const REC=", "\n"),
  grab("const HDR_LEN=", "/* the editable inventory"),            // HDR_LEN, N_*, R_*, parseCmp
  grab("function scan(buf)", "\n"),
  grab("function recInfo(", "/* Section C must"),                 // recInfo, stateAt/setState/setCond, writeIdentity
  grab("function withRepairQueue(", "function parseHeader("),
  grab("function parseHeader(", "/* car block"),
  grab("const ARMOR_OFF=", "/* ---- equipped swaps"),             // ARMOR_OFF, ARMOR_LABELS, parseCar
  grab("const DIR_HDR=", "const sceneOf="),                        // DIR_*, dirRec, parseDir
].join("\n");
const td = new TextDecoder("latin1");
const api = new Function("td", src + "\nreturn {parseCmp,scan,recInfo,stateAt,setState,setCond,withRepairQueue,parseHeader,parseCar,parseDir,REC,HDR_LEN};")(td);

const args = process.argv.slice(2);
const asJson = args.includes("--json");
const files = args.filter(a => a !== "--json");
if (!files.length) { console.error("usage: node test-save-editor-cmp.mjs [--json] files..."); process.exit(2); }

const rec = (buf, o) => { const r = api.recInfo(buf, o); return { name: r.name, type: r.type, cls: r.cls, dfl: r.dfl, full: r.full, wt: Math.round(r.wt * 1000) / 1000, cond: r.cond, state: r.state, u22: r.u22, u48: r.u48 }; };
const toBuf = f => { const b = fs.readFileSync(f); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const multiset = (buf, offs) => offs.map(o => { const r = api.recInfo(buf, o); return `${r.name}|${r.cond}|${r.dfl}`; }).sort().join("\n");

let fail = 0; const out = [];
const check = (c, m) => { if (!c) { fail++; console.log("FAIL", m); } };
for (const f of files) {
  const buf = toBuf(f), base = path.basename(f);
  if (/\.dir$/i.test(f)) {
    const d = api.parseDir(buf);
    const count = new DataView(buf).getUint32(0, true);
    if (asJson) out.push({ file: base, size: buf.byteLength, count, records: d });
    else { check(Object.keys(d).length <= count, `${base}: more records than count`); console.log(`${base}: ${count} records, ${buf.byteLength} B${buf.byteLength === 4 + 60 * count ? "" : " (+slack)"}`); }
    continue;
  }
  let p;
  try { p = api.parseCmp(buf); } catch (e) { if (asJson) out.push({ file: base, size: buf.byteLength, error: e.message }); else check(false, `${base}: ${e.message}`); continue; }
  if (asJson) {
    const h = api.parseHeader(buf), car = api.parseCar(buf);
    out.push({ file: base, size: buf.byteLength, car: h.car, variant: h.variant, nA: p.a.length, nC: p.c.length,
      armor: car.armor, equipped: car.eq, a: p.a.map(o => rec(buf, o)), c: p.c.map(o => rec(buf, o)) });
    continue;
  }
  // self-checks
  check(buf.byteLength === api.HDR_LEN + 8 + api.REC * (p.a.length + p.c.length), `${base}: size formula`);
  const same = api.withRepairQueue(buf) === buf;
  const queueOk = multiset(buf, p.c) === multiset(buf, p.a.filter(o => api.stateAt(buf, o) === 3));
  check(same === queueOk, `${base}: withRepairQueue identity (${same}) must follow queue consistency (${queueOk})`);
  // edit: queue one van part -> C grows by one copy of it; un-queue one -> shrinks
  const v = p.a.find(o => api.stateAt(buf, o) === 2);
  if (v !== undefined) {
    const b2 = buf.slice(0); api.setState(b2, v, 3);
    const b3 = api.withRepairQueue(b2), p3 = api.parseCmp(b3);
    const a3 = p3.a.filter(o => api.stateAt(b3, o) === 3);
    check(p3.c.length === a3.length && multiset(b3, p3.c) === multiset(b3, a3), `${base}: queue rebuilt after state edit`);
    check(b3.byteLength === api.HDR_LEN + 8 + api.REC * (p3.a.length + p3.c.length), `${base}: rebuilt size formula`);
    const vk = (r => `${r.name}|${r.cond}|${r.dfl}`)(api.recInfo(b3, v));
    check(api.recInfo(b3, v).state === 3 && p3.c.some(o => { const r = api.recInfo(b3, o); return `${r.name}|${r.cond}|${r.dfl}` === vk; }), `${base}: queued part copied into C`);
  }
  // cond edit lands on the same record (the old frame wrote it one record down)
  const b4 = buf.slice(0); api.setCond(b4, p.a[0], 4242);
  check(api.recInfo(b4, p.a[0]).cond === 4242 && (p.a.length < 2 || api.recInfo(b4, p.a[1]).cond === api.recInfo(buf, p.a[1]).cond), `${base}: setCond on record 0 only`);
  console.log(`${base}: nA ${p.a.length} nC ${p.c.length} ${same ? "queue consistent" : "queue INCONSISTENT (editor-touched file; withRepairQueue would rebuild it)"}`);
}
if (asJson) { console.log(JSON.stringify(out)); process.exit(0); }
console.log(fail ? `${fail} FAILED` : "all checks passed");
process.exit(fail ? 1 : 0);
