// node dir_set_scene.mjs <in savegame.dir> <slotBase e.g. save006> <scene> <out file>
// Leg B2 helper: applies the browser editor's CORRECTED dirSetScene (i76-save-editor.html, frame 4 + 60k, file name at +36)
// to a copy of a game-written directory. Same extraction as tools/tests/test-save-editor-dir.mjs. Prints the records
// before and after and the byte offsets that changed; exits 1 unless exactly the 4 scene bytes of that record differ.
import fs from "node:fs";
const html = fs.readFileSync("C:/Users/james/i76-everywhere/i76-save-editor.html", "utf8");
const grab = (start, end) => {
  const i = html.indexOf(start); const j = html.indexOf(end, i);
  if (i < 0 || j < 0) throw new Error("missing " + start);
  return html.slice(i, j);
};
const src = [grab("function cstr(", "\n"), grab("function u32(", "\n"), grab("const DIR_HDR=", "const sceneOf="),
  grab("function padDir(", "/* set an existing slot's scene dword"), grab("function dirSetScene(", "function dirWithSlot(")].join("\n");
const td = new TextDecoder();
const api = new Function("td", src + "\nreturn {parseDir,padDir,dirSetScene};")(td);
const [inFile, slot, sceneStr, outFile] = process.argv.slice(2);
const scene = Number(sceneStr);
const buf = new Uint8Array(fs.readFileSync(inFile)).buffer;
const show = (label, b) => {
  const d = api.parseDir(b);
  console.log(label, new DataView(b).getUint32(0, true), "records,", b.byteLength, "bytes:",
    Object.entries(d).map(([k, v]) => `${k}=${v.scene}${v.name ? "(" + v.name + ")" : ""}/${v.state}`).join(" "));
  return d;
};
const d0 = show("before", buf);
const out = api.dirSetScene(buf, slot, scene);
const d1 = show("after ", out);
const a = new Uint8Array(buf), b = new Uint8Array(out);
const diffs = [];
for (let i = 0; i < Math.max(a.length, b.length); i++) if (a[i] !== b[i]) diffs.push(i);
// the record index by its file-name field at +36
const count = new DataView(buf).getUint32(0, true); let k = -1;
for (let i = 0; i < count; i++) { const r = 4 + 60 * i; const nm = td.decode(a.slice(r + 36, r + 52)).split("\0")[0]; if (nm === slot) k = i; }
console.log(`record k=${k} (offset ${4 + 60 * k}); changed byte offsets: [${diffs.join(",")}]`);
const expect = k >= 0 ? [0, 1, 2, 3].map(o => 4 + 60 * k + o).filter(o => a[o] !== b[o]) : [];
const ok = k >= 0 && d1[slot]?.scene === scene && diffs.length === expect.length && diffs.every((o, i) => o === expect[i]) &&
  b.length === a.length && Object.keys(d0).every(s => s === slot || (d0[s].scene === d1[s].scene && d0[s].name === d1[s].name && d0[s].state === d1[s].state));
fs.writeFileSync(outFile, Buffer.from(b));
console.log(ok ? "OK: only the scene dword of " + slot + " changed; wrote " + outFile : "FAIL: unexpected diff");
process.exit(ok ? 0 : 1);
