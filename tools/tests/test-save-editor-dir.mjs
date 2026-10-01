// node tools/tests/test-save-editor-dir.mjs [savegame.dir]
// Runs the browser editor's savegame.dir functions (extracted from i76-save-editor.html) against a game-written
// directory. For the lab file (2026-10-01): scenes 1,2,3,5,6,6 and the display name "s" on save005.
import fs from "node:fs";
const html = fs.readFileSync(new URL("../../i76-save-editor.html", import.meta.url), "utf8");
const grab = (start, end) => {
  const i = html.indexOf(start); const j = html.indexOf(end, i);
  if (i < 0 || j < 0) throw new Error("missing " + start);
  return html.slice(i, j);
};
const src = [grab("function cstr(", "\n"), grab("function u32(", "\n"), grab("const DIR_HDR=", "const sceneOf="),
  grab("function padDir(", "/* set an existing slot's scene dword"), grab("function dirSetScene(", "function dirWithSlot("),
  grab("function dirWithSlot(", "/* set/clear the 32-byte display name"), grab("function dirSetName(", "const isLate="),
  grab("function dirRemoveSlot(", "const $=id=>")].join("\n");
const td = new TextDecoder();
const api = new Function("td", src + "\nreturn {parseDir,padDir,dirSetScene,dirWithSlot,dirSetName,dirRemoveSlot};")(td);
const file = process.argv[2] || "C:/Users/james/i76-uncap-lab/game/savegame.dir";
const buf = new Uint8Array(fs.readFileSync(file)).buffer;
const show = (label, b) => {
  const d = api.parseDir(b);
  console.log(label, new DataView(b).getUint32(0, true), "records,", b.byteLength, "bytes:",
    Object.entries(d).map(([k, v]) => `${k}=${v.scene}${v.name ? "(" + v.name + ")" : ""}/${v.state}`).join(" "));
  return d;
};
let fail = 0;
const check = (c, m) => { if (!c) { fail++; console.log("FAIL", m); } };
const d = show("game file  ", buf);
check(d.save000?.scene === 1 && d.save005?.scene === 6 && d.save005?.name === "s" && d.save003?.scene === 5, "expected scenes 1,2,3,5,6,6 and name s");
const b2 = api.dirSetScene(buf, "save003", 9); const d2 = show("set 003->9 ", b2);
check(d2.save003.scene === 9 && d2.save004.scene === 6 && d2.save002.scene === 3 && b2.byteLength === buf.byteLength, "set scene must touch only save003");
const b3 = api.dirWithSlot(buf, "save006", 7, "AUTOSAVE1"); const d3 = show("add 006    ", b3);
check(b3.byteLength === 4 + 60 * 7 && d3.save006.scene === 7 && d3.save006.name === "AUTOSAVE1" && d3.save006.state === 1 && d3.save005.scene === 6, "new record framing");
const b4 = api.dirRemoveSlot(b3, "save001"); const d4 = show("drop 001   ", b4);
check(b4.byteLength === 4 + 60 * 6 && !d4.save001 && d4.save002.scene === 3 && d4.save006.scene === 7 && d4.save005.name === "s", "remove keeps the other records whole");
const b5 = api.dirSetName(buf, "save000", "Hello"); const d5 = show("name 000   ", b5);
check(d5.save000.name === "Hello" && d5.save000.scene === 1 && d5.save001.scene === 2, "set name must not move the scene");
console.log(fail ? `${fail} FAILED` : "all checks passed");
process.exit(fail ? 1 : 0);
