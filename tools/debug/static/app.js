/* app.js - I76 Debug front end. One SSE stream (/api/stream) feeds a local store; the visible tab redraws at ~15 Hz.
   Trainer controls POST to /api/trainer. Everything is read from the local server (127.0.0.1). */
"use strict";
const $ = id => document.getElementById(id);
function H(id, html) { const el = $(id); if (el._h !== html) { el._h = html; el.innerHTML = html; return true; } return false; }
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const DEG = 180 / Math.PI;
const MAXS = 7200;
const S = { samples: [], hsamples: [], events: [], hap_events: [], log_tail: [], overview: null, ev: null, hap: null, log: null, trainer: null,
            trail: [], markers: [], connected: false };
let TAB = (location.hash || "#overview").slice(1);
let dirty = true;

// ------------------------------------------------------------------ helpers
function table(head, rows, cls) {
  return `<table class="${cls || ""}"><tr>${head.map(h => `<th class="${/^#|num/.test(h) ? "num" : ""}">${esc(h.replace(/^#/, ""))}</th>`).join("")}</tr>` +
    rows.map(r => `<tr>${r.map((c, i) => `<td class="${/^#/.test(head[i] || "") ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("") + `</table>`;
}
function meter(label, v, max, opts) {
  opts = opts || {}; const f = Math.max(0, Math.min(1, (v || 0) / (max || 1)));
  const pk = opts.peak != null ? `<div class="pk" style="left:calc(${Math.min(1, opts.peak / (max || 1)) * 100}% - 1px)"></div>` : "";
  return `<div class="meter"><div class="lab"><span>${esc(label)}</span><span>${opts.text != null ? opts.text : fmt(v)}</span></div>` +
    `<div class="track"><div class="fill" style="width:${f * 100}%;background:${opts.color || "var(--s1)"}"></div>${pk}</div></div>`;
}
function smeter(label, v, max, color, text) {
  const f = Math.max(-1, Math.min(1, (v || 0) / (max || 1)));
  const left = f >= 0 ? 50 : 50 + f * 50, width = Math.abs(f) * 50;
  return `<div class="meter signed"><div class="lab"><span>${esc(label)}</span><span>${text != null ? text : fmt(v)}</span></div>` +
    `<div class="track"><div class="fill" style="left:${left}%;width:${width}%;background:${color || "var(--s1)"}"></div><div class="zero"></div></div></div>`;
}
function tile(k, v, s) { return `<div class="tile"><div class="k">${esc(k)}</div><div class="v">${v}</div><div class="s">${s || "&nbsp;"}</div></div>`; }
function status(ok, text) { return `<span class="${ok === true ? "ok" : ok === false ? "bad" : "warn"}">${esc(text)}</span>`; }
const winSec = () => +$("win").value;
// The haptics tabs' state line: why there is no host data and the one click that fixes it (debug_haptics.py, /api/haptics).
let hapLive = false, hapMsg = "";
function hapExplain(o) {
  const c = o && o.hap_ctl;
  if (!c) return status(null, "No haptics host data (" + (o ? o.hap_src : "?") + "): this dashboard's haptics port is off (--haptics-port 0).");
  const telNote = o.tel_live ? "" : " Note: no telemetry from the game right now (start it with I76_TELEMETRY=1), so the host would have nothing to work on.";
  const tail = (c.log_tail || []).length ? `<pre class="mono">${esc(c.log_tail.join("\n"))}</pre>` : "";
  const last = hapMsg ? `<div class="note">${esc(hapMsg)}</div>` : "";
  if (c.running) return status(null, `Haptics host started by this dashboard (pid ${c.pid}, ${c.live ? "driving the devices" : "dry run: drives nothing"}, ${c.uptime || 0} s) - waiting for its first --debug-udp datagram on ${o.hap_src}.` + telNote) +
    ` <button data-hap="stop">Stop it</button>` + tail + last;
  let h = "";
  if (c.exited != null) h += status(false, `The haptics host this dashboard started has exited (code ${c.exited}).`) + tail;
  if (!c.host) return h + status(null, "No haptics host data: the haptics host is not running, and it is not part of this folder - it is tools\\haptics in the i76-everywhere repo (.NET 8). Set I76_HAPTICS_HOST to its folder, then press Start.") + ` <button data-hap="start" data-force="1">Start</button>` + last;
  if (!c.devices.length) return h + status(null, "No haptics host data: the haptics host is not running. No wheel or gamepad was found (winmm joysticks 0, XInput pads 0), so it has nothing to drive." + telNote) +
    ` <button data-hap="start" data-force="1">Start anyway (dry run: computes and shows its outputs, drives nothing)</button>` + last;
  return h + status(null, `No haptics host data: the haptics host is not running. Found: ${c.devices.join("; ")}.` + telNote) +
    ` <button data-hap="start">Start haptics host</button> <label><input type="checkbox" id="hap-live-${Math.random().toString(36).slice(2, 7)}" class="hap-live"> drive the devices (--live: wheel force, pad motors, shaker audio - leave off while the game's own force feedback runs)</label>` +
    `<div class="note">Same as <b>DEBUG.bat --haptics</b> (dry run) / <b>--haptics-live</b>. It runs ${esc(c.host)}${c.built ? "" : " (builds it first)"} with --debug-udp, fed by this dashboard's telemetry tee to port ${c.tee}.</div>` + last;
}
function needHap() {
  const o = S.overview, live = !!(o && o.hap_live);
  const key = live ? "live" : JSON.stringify([o && o.hap_ctl, o && o.tel_live, hapMsg]);
  if (key !== needHap.key) {
    needHap.key = key;
    const html = live ? "" : hapExplain(o);
    document.querySelectorAll(".need-hap").forEach(el => { if (el._h !== html) { el._h = html; el.innerHTML = html; } });
  }
  hapLive = live;
  return live;
}
document.addEventListener("click", async e => {
  const b = e.target.closest("button[data-hap]"); if (!b) return;
  const box = b.parentElement.querySelector(".hap-live");
  const body = { op: b.dataset.hap, force: b.dataset.force === "1", live: !!(box && box.checked) };
  if (body.live && !confirm("Drive the real devices (wheel force, pad motors, shaker audio)?\n\nLeave this off while the game's own force feedback is on: the wheel would get two force sources.")) return;
  try {
    const r = await fetch("/api/haptics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json(); hapMsg = j.msg || j.error || "";
    if (j.hap_ctl && S.overview) S.overview.hap_ctl = j.hap_ctl;
  } catch (err) { hapMsg = String(err); }
  needHap.key = null; dirty = true; needHap();
});

// ------------------------------------------------------------------ tabs
function showTab(t) {
  TAB = t; document.querySelectorAll(".tab").forEach(s => s.classList.toggle("on", s.id === "tab-" + t));
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === t));
  if (location.hash !== "#" + t) history.replaceState(null, "", "#" + t);
  dirty = true; if (t === "log") renderLog(true);
}
document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => showTab(b.dataset.tab));
window.addEventListener("hashchange", () => showTab((location.hash || "#overview").slice(1)));

// ------------------------------------------------------------------ charts
const W = () => winSec();
const T = s => s.speed != null;
const C = {
  ovdt: new StripChart($("ch-ov-dt"), $("lg-ov-dt"), { window: 60, min: 0, unit: "ms", series: [
    { key: "dt", label: "frame dt", get: s => s.dt }, { key: "sdt", label: "sim dt", get: s => s.sdt }] }),
  speed: new StripChart($("ch-speed"), $("lg-speed"), { window: W, min: 0, unit: "km/h", series: [{ key: "v", label: "speed", get: s => s.speed * 3.6 }] }),
  rpm: new StripChart($("ch-rpm"), $("lg-rpm"), { window: W, min: 0, series: [{ key: "rpm", label: "rpm", get: s => s.rpm }] }),
  inputs: new StripChart($("ch-inputs"), $("lg-inputs"), { window: W, min: -1, max: 1, series: [
    { key: "thr", label: "throttle", get: s => s.thr }, { key: "str", label: "steer", get: s => s.str }] }),
  accel: new StripChart($("ch-accel"), $("lg-accel"), { window: W, sym: true, unit: "m/s²", series: [
    { key: "ax", label: "x (lateral)", get: s => s.ax }, { key: "ay", label: "y (vertical)", get: s => s.ay }, { key: "az", label: "z (longitudinal)", get: s => s.az }] }),
  angles: new StripChart($("ch-angles"), $("lg-angles"), { window: W, sym: true, unit: "deg", series: [
    { key: "p", label: "pitch", get: s => s.pitch * DEG }, { key: "r", label: "roll", get: s => s.roll * DEG }] }),
  rates: new StripChart($("ch-rates"), $("lg-rates"), { window: W, sym: true, unit: "deg/s", series: [
    { key: "pr", label: "pitch rate", get: s => s.pr * DEG }, { key: "yr", label: "yaw rate", get: s => s.yr * DEG }, { key: "rr", label: "roll rate", get: s => s.rr * DEG }] }),
  susp: new StripChart($("ch-susp"), $("lg-susp"), { window: W, unit: "m", series: ["FL", "FR", "ML", "MR", "RL", "RR"].map((n, i) => ({ key: n, label: n, get: s => s.susp && s.susp[i] })) }),
  grip: new StripChart($("ch-grip"), $("lg-grip"), { window: W, min: 0, series: [
    { key: "grip", label: "grip sum", get: s => s.grip }, { key: "gcap", label: "grip cap", get: s => s.gcap }, { key: "gg", label: "ground g", get: s => s.gg }, { key: "clr", label: "clearance (m)", get: s => s.clr }] }),
  steps: new StripChart($("ch-steps"), $("lg-steps"), { window: W, min: 0, series: [
    { key: "st", label: "steps / frame", get: s => s.steps }, { key: "sdt", label: "sim dt (ms)", get: s => s.sdt }] }),
  ffb: new StripChart($("ch-ffb"), $("lg-ffb"), { window: W, sym: true, series: [
    { key: "model", label: "reference model", get: s => s.model }, { key: "voice", label: "effect voices", get: s => s.voice }, { key: "dev", label: "device (after gate / clamp)", get: s => s.dev }] }),
  ffbstack: new StripChart($("ch-ffbstack"), $("lg-ffbstack"), { window: W, stacked: true, sym: true, series: [] }),
  rumble: new StripChart($("ch-rumble"), $("lg-rumble"), { window: W, min: 0, max: 1, fixed: true, series: [
    { key: "pl", label: "L (heavy)", get: s => s.ppl }, { key: "pr", label: "R (texture)", get: s => s.ppr }] }),
  lfe: new StripChart($("ch-lfe"), $("lg-lfe"), { window: W, min: 0, series: [{ key: "rms", label: "RMS", get: s => s.rms }, { key: "pk", label: "peak", get: s => s.lpk }] }),
  motion: new StripChart($("ch-motion"), $("lg-motion"), { window: W, sym: true, unit: "m/s²", series: [
    { key: "su", label: "surge", get: s => s.ms && (s.ms[0] + (s.mc ? s.mc[0] : 0)) }, { key: "sw", label: "sway", get: s => s.ms && (s.ms[1] + (s.mc ? s.mc[1] : 0)) },
    { key: "he", label: "heave", get: s => s.ms && (s.ms[2] + (s.mc ? s.mc[2] : 0)) }] }),
  motionr: new StripChart($("ch-motionr"), $("lg-motionr"), { window: W, sym: true, unit: "rad/s", series: [
    { key: "rr", label: "roll rate", get: s => s.ms && s.ms[3] }, { key: "pr", label: "pitch rate", get: s => s.ms && s.ms[4] }, { key: "yr", label: "yaw rate", get: s => s.ms && s.ms[5] }] }),
  coll: new StripChart($("ch-coll"), $("lg-coll"), { window: () => Math.max(300, (((S.log || {}).coll || {}).hist || []).length * 30), min: 0, unit: "tests", series: [
    { key: "w", label: "widened (a body steps this frame)", get: s => s.widened }, { key: "s", label: "stock window", get: s => s.stock }, { key: "f", label: "no pair window", get: s => s.fallback }] }),
  spec: new BarChart($("lfe-spec"), { unit: " Hz", min: 0.05 }),
};
const FFB_CH = ["center", "corner", "oversteer", "brake", "texture", "scrub", "judder", "impact", "weapon", "shift"];
// eight categorical slots in their fixed order, then two neutral inks for the last two channels (never a generated hue); voices white
const FFB_COLORS = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"].map(CSS).concat(["#c3c2b7", "#6f6e69"]);

// ------------------------------------------------------------------ renderers per tab
function renderOverview() {
  const o = S.overview; if (!o) return;
  const f = o.frame || {}, live = o.tel_live;
  const kmh = f.speed != null ? fmt(f.speed * 3.6, 0) : "-";
  const lfps = S.log && S.log.fps;
  $("ov-tiles").innerHTML = [
    tile("fps (telemetry)", live ? fmt(o.fps, 1) : "-", lfps ? "proxy log: " + fmt(lfps.fps, 1) + " fps, work " + fmt(lfps.work_avg, 2) + " ms" : (live ? "" : "telemetry not live")),
    tile("frame time", o.dt_p50 != null ? fmt(o.dt_p50, 1) + " ms" : "-", o.dt_p99 != null ? "p99 " + fmt(o.dt_p99, 1) + " ms" : ""),
    tile("physics steps / frame", f.step_count != null ? f.step_count : "-", S.log && S.log.fixed_step ? "fixed step " + S.log.fixed_step.hz + " /s" : "sim dt " + fmt((f.sim_dt || 0) * 1000, 1) + " ms"),
    tile("player", f.player_present ? "in mission" : (live ? "menu / loading" : "-"), f.frame != null ? "frame " + f.frame + ", t " + fmt(f.sim_time, 1) + " s" : ""),
    tile("speed", kmh + " km/h", f.speed != null ? fmt(f.speed, 1) + " m/s" : ""),
    tile("rpm / gear", f.rpm != null ? fmt(f.rpm, 0) + " / " + esc(o.gear_str) : "-", f.throttle != null ? "throttle " + fmt(f.throttle, 2) + ", steer " + fmt(f.steer, 2) : ""),
    tile("health", f.health_pct != null ? fmt(f.health_pct, 0) + " %" : "-", f.engine_hp != null ? "engine " + f.engine_hp + "/" + f.engine_hp_max : ""),
    tile("weapon", f.weapon_name ? esc(f.weapon_name) : "-", f.weapon_ammo != null ? "ammo " + (f.weapon_ammo >= 0x0fffffff ? "unlimited" : f.weapon_ammo) : ""),
  ].join("");
  if (f.speed != null) {
    const sides = ["front", "left", "right", "back"];
    $("ov-vehicle").innerHTML = sides.map((s, i) => meter("armour " + s, o.armour[i], o.armour_max[i] || 1, { text: o.armour[i] + " / " + o.armour_max[i], color: "var(--s1)" })).join("") +
      sides.map((s, i) => meter("chassis " + s, o.chassis[i], o.chassis_max[i] || 1, { text: o.chassis[i] + " / " + o.chassis_max[i], color: "var(--s3)" })).join("") +
      meter("engine", f.engine_hp, f.engine_hp_max || 1, { text: f.engine_hp + " / " + f.engine_hp_max, color: "var(--s4)" }) +
      meter("suspension", f.susp_hp, f.susp_hp_max || 1, { text: f.susp_hp + " / " + f.susp_hp_max, color: "var(--s4)" }) +
      meter("brakes", f.brake_hp, f.brake_hp_max || 1, { text: f.brake_hp + " / " + f.brake_hp_max, color: "var(--s4)" }) +
      `<div class="note">wheels: ${o.wheels.map((w, i) => ["FL", "FR", "ML", "MR", "RL", "RR"][i] + " " + (w.present ? (w.flat ? "FLAT" : w.hp + "/" + w.hp_max) : "-")).join(" &middot; ")}</div>` +
      `<div class="note">flags ${esc(o.flags_str)} &middot; surface ${f.surface} &middot; music track ${f.music_track} &middot; voices ${f.sound_voices} &middot; hooks 0x${(f.event_hooks || 0).toString(16)}</div>`;
  } else $("ov-vehicle").innerHTML = `<div class="note">no telemetry frame yet</div>`;
  const g = o.game || {}, lg = S.log || {};
  $("ov-sources").innerHTML = table(["source", "state"], [
    ["telemetry", status(live, (live ? "live, " : "not live, ") + o.tel_src) + (o.tel_version ? ` <span class="note">v${o.tel_version}, ${o.tel_frames} frames</span>` : "")],
    ["haptics host", status(o.hap_live, (o.hap_live ? "live, " : "no data, ") + o.hap_src) + (o.hap_count ? ` <span class="note">${o.hap_count} datagrams</span>` : "")],
    ["game folder", esc(g.dir || "-") + ` <span class="note">(${esc(g.from || "")})</span>`],
    ["proxy DLL", g.dll ? esc(g.dll.split(/[\\/]/).pop()) + " md5 <b>" + esc((g.dll_md5 || "").slice(0, 8)) + "</b>" + ` <span class="note">${esc(g.dll_md5 || "")}</span>` : "not found"],
    ["proxy log", status(g.log_exists, g.log || "-") + (lg.lines ? ` <span class="note">${lg.lines} lines this start</span>` : "")],
    ["trainer", S.trainer ? esc(S.trainer.mode + " - " + S.trainer.pdetail) : "off"],
  ], "wrap");
  const feats = lg.features || [];
  $("ov-switches").innerHTML = (lg.switches_from_log && lg.switches_from_log.length ? `<div class="flagrow">${lg.switches_from_log.map(s => `<span class="on">${esc(s)}</span>`).join("")}</div>` : "") +
    (feats.length ? table(["feature", "applied", "log line"], feats.map(x => [esc(x.name), status(x.applied, x.applied ? "yes" : x.applied === false ? "NO" : "partly"), esc(x.text)]), "wrap")
      : `<div class="note">no proxy start in the log yet (${esc(g.log || "no log")})</div>`) +
    (lg.not_applied && lg.not_applied.length ? `<h3>Not applied</h3>` + lg.not_applied.map(l => `<div class="bad">${esc(l)}</div>`).join("") : "");
  C.ovdt.draw(S.samples);
}

function renderTelemetry() {
  for (const k of ["speed", "rpm", "inputs", "accel", "angles", "rates", "susp", "grip", "steps"]) C[k].draw(S.samples);
  drawMap();
  const f = S.overview && S.overview.frame;
  if (f) $("tel-facts").innerHTML = table(["mass", "wheelbase", "front track", "steer gain", "engine power", "ffb present", "position (x, y, z)"],
    [[fmt(f.mass, 0), fmt(f.wheelbase, 2) + " m", fmt(f.front_track, 2) + " m", fmt(f.steer_gain, 3), fmt(f.engine_power, 1), f.ffb_present, fmt(f.pos_0, 1) + ", " + fmt(f.pos_1, 1) + ", " + fmt(f.pos_2, 1)]]);
}

function drawMap() {
  const c = $("map"); if (!c.offsetParent) return;
  const { g, w, h } = fitCanvas(c); g.clearRect(0, 0, w, h);
  const tr = S.trail, f = S.overview && S.overview.frame;
  if (!tr.length || !f) { g.fillStyle = CSS("--muted"); g.font = "12px system-ui"; g.fillText("no position yet", 12, 20); return; }
  const cx = f.pos_0, cz = f.pos_2;
  let r = 60; tr.forEach(p => { r = Math.max(r, Math.abs(p[0] - cx), Math.abs(p[1] - cz)); }); r = Math.min(r * 1.1, 1500);
  const sc = Math.min(w, h) / 2 / r, X = x => w / 2 + (x - cx) * sc, Y = z => h / 2 - (z - cz) * sc;
  g.strokeStyle = CSS("--grid"); g.lineWidth = 1;
  const step = Math.pow(10, Math.floor(Math.log10(r))) ; for (let k = -10; k <= 10; k++) { const gx = Math.round(X(Math.round(cx / step) * step + k * step)) + 0.5, gy = Math.round(Y(Math.round(cz / step) * step + k * step)) + 0.5; g.beginPath(); g.moveTo(gx, 0); g.lineTo(gx, h); g.moveTo(0, gy); g.lineTo(w, gy); g.stroke(); }
  g.strokeStyle = CSS("--s1"); g.lineWidth = 2; g.beginPath(); tr.forEach((p, i) => { i ? g.lineTo(X(p[0]), Y(p[1])) : g.moveTo(X(p[0]), Y(p[1])); }); g.stroke();
  const now = S.overview.now;
  S.markers.forEach(m => {
    const age = now - m.w; if (age > 60) return;
    g.globalAlpha = Math.max(0.2, 1 - age / 60); g.fillStyle = m.kind === "explosion" ? CSS("--s2") : CSS("--s4");
    g.beginPath(); g.arc(X(m.x), Y(m.z), m.kind === "explosion" ? 5 : 3, 0, 7); g.fill();
  });
  g.globalAlpha = 1;
  const hd = S.overview.angles ? S.overview.angles[2] : 0, px = X(cx), py = Y(cz);
  g.fillStyle = CSS("--text"); g.save(); g.translate(px, py); g.rotate(-hd + Math.PI); g.beginPath(); g.moveTo(0, 9); g.lineTo(-5, -6); g.lineTo(5, -6); g.closePath(); g.fill(); g.restore();
  g.fillStyle = CSS("--muted"); g.font = "10px system-ui"; g.fillText("north = +z, east = +x, grid " + step + " m", 8, h - 8);
  $("map-note").innerHTML = `<span style="color:var(--s2)">&#9679;</span> explosion &nbsp; <span style="color:var(--s4)">&#9679;</span> positioned sound start (last 60 s). Other vehicles are not in the telemetry.`;
}

const EV_TYPES = ["SHOT", "EXPLOSION", "IMPACT", "DAMAGE_SIDE", "SOUND_START", "SOUND_STOP", "WEAPON_UI"];
const evShow = Object.fromEntries(EV_TYPES.map(t => [t, t !== "SOUND_STOP"]));
$("ev-filter").innerHTML = EV_TYPES.map(t => `<label><input type="checkbox" data-ev="${t}" ${evShow[t] ? "checked" : ""}> ${t}</label>`).join(" ");
$("ev-filter").addEventListener("change", e => { evShow[e.target.dataset.ev] = e.target.checked; renderFeed(); });
function renderFeed() {
  const ev = S.events.filter(e => evShow[e.type] !== false).slice(-250).reverse();
  $("ev-feed").innerHTML = ev.map(e => `<div><span class="ty">${esc(e.type)}</span>${esc(e.text.replace(/^ev #\d+\s+/, ""))}</div>`).join("") || `<div class="note">no events yet</div>`;
  $("hev-feed").innerHTML = S.hap_events.slice(-150).reverse().map(e => `<div><span class="ty">${esc(e.type)}</span>${esc(e.name ? "'" + e.name + "' " : "")}${esc(Object.entries(e.f || {}).map(([k, v]) => k + "=" + fmt(v)).join(" "))}</div>`).join("") || `<div class="note">no haptics host events (the host is not publishing)</div>`;
}
function renderEvents() {
  const v = S.ev; if (!v) return;
  $("ev-tiles").innerHTML = EV_TYPES.map(t => tile(t, v.count[t] || 0, "")).join("");
  drawCar(v.damage_sides);
  const ds = v.damage_sides;
  $("ev-sides").innerHTML = table(["side", "#hits", "#hp lost"], Object.entries(ds).filter(([k, x]) => x.hits).map(([k, x]) => [k, x.hits, fmt(x.hp, 0)])) +
    `<div class="note">zones ${esc(Object.entries(v.damage_zones).map(([k, n]) => k + ":" + n).join(" ") || "-")} &middot; other targets: ${v.damage_other.hits} hits, ${fmt(v.damage_other.hp, 0)} hp, ${v.damage_other.kills} killed (${v.damage_other.by_player} by the player)</div>`;
  $("ev-impacts").innerHTML = table(["", "#count"], [["player hit", v.impacts.player], ["other targets", v.impacts.other], ["player hp lost", fmt(v.impacts.player_hp, 0)]]) +
    table(["source class", "#count"], Object.entries(v.impacts.by_source).map(([k, n]) => [esc(k), n]));
  $("ev-shots").innerHTML = table(["weapon (hud row, name when selected)", "#rounds"], Object.entries(v.shots).sort((a, b) => b[1] - a[1]).map(([k, n]) => [esc(k), n])) +
    `<div class="note">weapon UI: ${esc(Object.entries(v.weapon_ui).map(([k, n]) => k + " " + n).join(", ") || "-")}</div>`;
  $("ev-expl").innerHTML = table(["template", "#m from player", "position"], v.explosions.slice().reverse().slice(0, 12).map(e => [esc(e.name), e.dist >= 0 ? fmt(e.dist, 1) : "-", e.pos.map(x => fmt(x, 0)).join(", ")]));
  $("ev-sounds").innerHTML = table(["name", "#starts"], Object.entries(v.sounds).slice(0, 16).map(([k, n]) => [esc(k), n]));
  $("ev-active").innerHTML = table(["name", "#Hz", "#vol %", "mode", "player"], v.sounds_active.slice(-16).reverse().map(s => [esc(s.name), fmt(s.hz, 0), fmt(s.vol, 0), esc(s.mode), s.player ? "yes" : ""]));
}
function drawCar(ds) {
  const c = $("ev-car"); if (!c.offsetParent) return;
  const { g, w, h } = fitCanvas(c); g.clearRect(0, 0, w, h);
  const cw = 60, chh = 110, x0 = w / 2 - cw / 2, y0 = h / 2 - chh / 2;
  const mx = Math.max(1, ...Object.values(ds).map(d => d.hp));
  const heat = v => { const a = v / mx; return `rgba(208,59,59,${0.15 + 0.85 * a})`; };
  const side = (k, x, y, ww, hh) => { const d = ds[k] || { hp: 0, hits: 0 }; g.fillStyle = d.hits ? heat(d.hp) : CSS("--grid"); g.fillRect(x, y, ww, hh);
    g.fillStyle = CSS("--text-2"); g.font = "10px system-ui"; g.textAlign = "center"; g.fillText(k + (d.hits ? " " + fmt(d.hp, 0) : ""), x + ww / 2, y + hh / 2 + 3); };
  side("front", x0, y0 - 24, cw, 20); side("back", x0, y0 + chh + 4, cw, 20);
  side("left", x0 - 64, y0, 60, chh); side("right", x0 + cw + 4, y0, 60, chh); side("top", x0, y0, cw, chh);
}

function renderFfb() {
  needHap();
  const hp = S.hap; C.ffb.draw(S.hsamples);
  const voiceIds = new Set(); S.hsamples.slice(-600).forEach(s => Object.keys(s.vw || {}).forEach(k => voiceIds.add(k)));
  C.ffbstack.setSeries(FFB_CH.map((k, i) => ({ key: k, label: k, color: FFB_COLORS[i], get: s => s.ch ? s.ch[k] : null }))
    .concat([...voiceIds].sort().map(id => ({ key: "v:" + id, label: id + " (voice)", color: "#e6e6e6", get: s => s.vw && s.vw[id] ? s.vw[id] * 10000 : 0 }))));
  C.ffbstack.draw(S.hsamples);
  if (!hp) return;
  const wl = hp.wheel || {};
  $("ffb-tiles").innerHTML = [tile("device force", wl.device, "peak since last " + fmt(wl.peak, 0)), tile("reference model", wl.model, "steady " + wl.steady + ", osc " + wl.osc),
    tile("effect voices", fmt(wl.voice, 0), (hp.voices || []).length + " sounding"), tile("ramp / duck", fmt(wl.ramp, 2) + " / " + fmt(wl.duck, 2), "rough " + fmt(wl.rough, 2)),
    tile("grip %", wl.channels ? wl.channels["grip%"] : "-", (wl.notes || []).join(" ") || "no notes")].join("");
  $("ffb-now").innerHTML = FFB_CH.map((k, i) => smeter(k, (wl.channels || {})[k], 10000, FFB_COLORS[i], String((wl.channels || {})[k] || 0))).join("") +
    smeter("total (model + voices)", wl.total, 10000, "var(--text-2)", fmt(wl.total, 0));
  $("ffb-voices").innerHTML = (hp.voices || []).length ? table(["voice", "group", "#level", "#wheel", "#age ms"], hp.voices.map(v => [esc(v.id), esc(v.group), fmt(v.level, 2), fmt(v.wheel, 3), fmt(v.age_ms, 0)])) : `<div class="note">no effect-file voice is sounding</div>`;
}

function renderRumble() {
  needHap(); C.rumble.draw(S.hsamples);
  const hp = S.hap; if (!hp) return;
  const p = hp.pad || {}, b = hp.bus || {};
  $("rb-meters").innerHTML = (p.open ? "" : `<div class="note">no pad sink open in the host: showing the reference down-mix it would send</div>`) +
    meter("L motor (heavy)", p.l, 1, { peak: p.peak_l, color: "var(--s1)" }) + meter("R motor (texture)", p.r, 1, { peak: p.peak_r, color: "var(--s2)" });
  const vs = (hp.voices || []).filter(v => v.pad_l || v.pad_r);
  $("rb-drivers").innerHTML = table(["bus signal", "#value"], [["transient impact", fmt(b.impact)], ["transient weapon", fmt(b.weapon)], ["transient shift", fmt(b.shift)],
      ["steady (|wheel|)", fmt(Math.abs(b.steady || 0))], ["engine amp", fmt((b.lfe || {}).engine)], ["road amp", fmt((b.lfe || {}).road)]]
    .concat((b.tactile || []).map(t => ["tactile " + esc(t.name) + " " + fmt(t.hz, 0) + " Hz", fmt(t.amp)]))) +
    (vs.length ? table(["effect voice", "#L", "#R"], vs.map(v => [esc(v.id), fmt(v.pad_l), fmt(v.pad_r)])) : `<div class="note">no effect voice on the pad right now</div>`);
}

function renderLfe() {
  needHap(); C.lfe.draw(S.hsamples);
  const hp = S.hap; if (!hp) return;
  const l = hp.lfe || {}, src = (hp.bus || {}).lfe || {};
  $("lfe-meter").innerHTML = (l.open ? "" : `<div class="note">no lfe sink open in the host (add lfe-wav to --sinks)</div>`) +
    meter("RMS", l.rms, 1, { peak: l.peak, color: "var(--s3)", text: l.rms != null ? (20 * Math.log10(Math.max(1e-5, l.rms))).toFixed(1) + " dBFS (peak " + fmt(l.peak, 2) + ")" : "-" }) +
    `<div class="note">${l.samples ? l.samples + " samples @ " + l.rate + " Hz" : ""}${l.synth_gain != null ? " &middot; synth gain " + fmt(l.synth_gain, 2) : ""}</div>`;
  if (l.spectrum) C.spec.draw(l.spectrum_hz.map(String), l.spectrum);
  const names = [["engine", "engine_hz"], ["road", "road_hz"], ["impulse", "impulse_hz"], ["heave", "carrier_hz"], ["weapon", "weapon_hz"], ["scrub", null], ["explode", null]];
  const lv = (hp.voices || []).filter(v => v.lfe > 0);
  $("lfe-src").innerHTML = names.map(([k, hz], i) => meter(k + (hz && src[hz] ? " (" + fmt(src[hz], 0) + " Hz)" : ""), src[k], 1, { color: seriesColor(i) })).join("") +
    (lv.length ? `<h3>Effect-file voices on the shaker</h3>` + lv.map(v => meter(v.id + " (" + fmt(v.lfe_hz, 0) + " Hz)", v.lfe, 1, { color: "var(--s7)" })).join("") : "");
  const st = l.stems || {};
  $("lfe-stems").innerHTML = st.on ? (table(["stem", "class", "#gain"], (st.voices || []).map(v => [esc(v.name), ["", "far", "near / 2D", "player"][v.cls] || v.cls, fmt(v.gain, 3)])) +
      `<div class="note">started ${st.started}, missed ${st.missed}, dropped ${st.dropped}, stolen ${st.stolen}; mix gain ${fmt(st.mix_gain, 2)}</div>`)
    : `<div class="note">stems off: ${esc(st.why || "no data")}</div>`;
}

const MSTATUS = [[1, "live"], [2, "airborne"], [4, "skid"], [8, "destroyed"], [16, "paused"], [32, "neutral (fail-to-neutral)"], [64, "interpolated"], [128, "cues"], [0x80000000, "shutting down"]];
function renderMotion() {
  needHap(); C.motion.draw(S.hsamples); C.motionr.draw(S.hsamples);
  const hp = S.hap; drawRig(hp && hp.motion_out);
  if (!hp) return;
  const m = hp.motion_out || {};
  if (!m.open) { $("mo-dof").innerHTML = `<div class="note">no motion-udp sink open in the host (add motion-udp to --sinks)</div>`; $("mo-status").innerHTML = ""; $("mo-targets").innerHTML = ""; return; }
  $("mo-dof").innerHTML = smeter("surge (+ cue " + fmt(m.cue_surge, 2) + ")", (m.surge || 0) + (m.cue_surge || 0), 15, "var(--s1)") +
    smeter("sway (+ cue " + fmt(m.cue_sway, 2) + ")", (m.sway || 0) + (m.cue_sway || 0), 15, "var(--s2)") +
    smeter("heave (+ cue " + fmt(m.cue_heave, 2) + ")", (m.heave || 0) + (m.cue_heave || 0), 15, "var(--s3)") +
    smeter("roll " + fmt((m.roll || 0) * DEG, 1) + " deg", m.roll_rate, 2, "var(--s4)", fmt(m.roll_rate, 3) + " rad/s") +
    smeter("pitch " + fmt((m.pitch || 0) * DEG, 1) + " deg", m.pitch_rate, 2, "var(--s5)", fmt(m.pitch_rate, 3) + " rad/s") +
    smeter("yaw (heading " + fmt((m.heading || 0) * DEG, 0) + " deg)", m.yaw_rate, 2, "var(--s7)", fmt(m.yaw_rate, 3) + " rad/s") +
    meter("gain (startup / fail-to-neutral ramp)", m.gain, 1, { color: "var(--s6)" });
  const st = m.status >>> 0;
  $("mo-status").innerHTML = `<div class="flagrow">${MSTATUS.map(([b, n]) => `<span class="${(st & b) >>> 0 ? "on" : ""}">${n}</span>`).join("")}</div>` +
    `<div class="note">0x${st.toString(16)} &middot; surface ${(st >>> 8) & 0xff} &middot; gear ${(st >>> 16) & 0xff} &middot; frame seq ${m.seq} &middot; ${m.ticks} ticks (${m.neutral_ticks} neutral) &middot; ${m.sending ? "SENDING UDP" : "files only (not sending)"}</div>` +
    `<div class="note">cues: ${esc(Object.entries(m.cues || {}).map(([k, n]) => k + " " + n).join(", ") || "none")}</div>`;
  $("mo-targets").innerHTML = table(["target", "streams", "#packets", "#packets/s", "#bytes", "#errors", "last error"], (m.targets || []).map(t => [esc(t.name), esc(t.streams), t.packets, fmt(t.rate, 1), t.bytes, t.errors, esc(t.error || "")]));
}
function drawRig(m) {
  const c = $("rig"); if (!c.offsetParent) return;
  const { g, w, h } = fitCanvas(c); g.clearRect(0, 0, w, h);
  const roll = m ? (m.roll || 0) : 0, pitch = m ? (m.pitch || 0) : 0, heave = m ? Math.max(-1, Math.min(1, ((m.heave || 0) + (m.cue_heave || 0)) / 15)) : 0;
  const surge = m ? Math.max(-1, Math.min(1, ((m.surge || 0) + (m.cue_surge || 0)) / 15)) : 0, gain = m ? (m.gain == null ? 1 : m.gain) : 0;
  const yaw = 0.6, tilt = 0.45, s = Math.min(w, h) / 5;
  const P = (x, y, z) => { // rotate by pitch (about x) and roll (about z), then view
    let y1 = y * Math.cos(pitch * gain) - z * Math.sin(pitch * gain), z1 = y * Math.sin(pitch * gain) + z * Math.cos(pitch * gain);
    let x2 = x * Math.cos(roll * gain) - y1 * Math.sin(roll * gain), y2 = x * Math.sin(roll * gain) + y1 * Math.cos(roll * gain);
    y2 += heave * 0.25; z1 += surge * 0.25;
    const xv = x2 * Math.cos(yaw) - z1 * Math.sin(yaw), zv = x2 * Math.sin(yaw) + z1 * Math.cos(yaw);
    return [w / 2 + xv * s, h * 0.58 - (y2 * Math.cos(tilt) - zv * Math.sin(tilt)) * s];
  };
  const poly = (pts, fill, stroke) => { g.beginPath(); pts.forEach((p, i) => { const q = P(...p); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.closePath(); if (fill) { g.fillStyle = fill; g.fill(); } if (stroke) { g.strokeStyle = stroke; g.stroke(); } };
  // base (fixed) and actuators
  const base = [[-1.3, -1, -1.3], [1.3, -1, -1.3], [1.3, -1, 1.3], [-1.3, -1, 1.3]];
  g.beginPath(); base.forEach((p, i) => { const vx = w / 2 + (p[0] * Math.cos(yaw) - p[2] * Math.sin(yaw)) * s, vz = p[0] * Math.sin(yaw) + p[2] * Math.cos(yaw); const vy = h * 0.58 - (-1 * Math.cos(tilt) - vz * Math.sin(tilt)) * s; i ? g.lineTo(vx, vy) : g.moveTo(vx, vy); }); g.closePath(); g.fillStyle = CSS("--grid"); g.fill();
  g.strokeStyle = CSS("--muted"); g.lineWidth = 2;
  [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([x, z]) => {
    const b = [w / 2 + (x * Math.cos(yaw) - z * Math.sin(yaw)) * s, h * 0.58 - (-1 * Math.cos(tilt) - (x * Math.sin(yaw) + z * Math.cos(yaw)) * Math.sin(tilt)) * s];
    const t = P(x, 0, z); g.beginPath(); g.moveTo(b[0], b[1]); g.lineTo(t[0], t[1]); g.stroke();
  });
  g.lineWidth = 1;
  poly([[-1.2, 0, -1.2], [1.2, 0, -1.2], [1.2, 0, 1.2], [-1.2, 0, 1.2]], CSS("--surface"), CSS("--s1"));
  poly([[-0.5, 0.05, -0.4], [0.5, 0.05, -0.4], [0.5, 0.05, 1.0], [-0.5, 0.05, 1.0]], CSS("--s1"), null);   // seat / car body, nose = +z
  const nose = P(0, 0.06, 1.15); g.fillStyle = CSS("--s2"); g.beginPath(); g.arc(nose[0], nose[1], 5, 0, 7); g.fill();
  g.fillStyle = CSS("--muted"); g.font = "11px system-ui";
  g.fillText(m ? `roll ${fmt(roll * DEG, 1)} deg  pitch ${fmt(pitch * DEG, 1)} deg  heave ${fmt(heave * 15, 1)}  surge ${fmt(surge * 15, 1)} m/s²  gain ${fmt(gain, 2)}` : "no motion data", 10, h - 10);
  g.fillText("orange dot = nose", 10, 16);
}

function renderCollision() {
  const L = S.log || {}, co = L.coll || {}, sf = co.stepframe, v3 = co.v3, bb = L.bbox || {}, ev = S.ev || { count: {}, impacts: { by_source: {} } };
  $("co-tiles").innerHTML = [tile("pair tests (last 30 s)", sf ? sf.pairs : "-", sf ? "when=stepframe" : "no stepframe report"),
    tile("widened", sf ? sf.widened : "-", sf && sf.pairs ? fmt(100 * sf.widened / sf.pairs, 0) + " % of pair tests" : ""),
    tile("stock window", sf ? sf.stock : "-", "tests left at the stock accept window"),
    tile("sphere->slab (v3)", v3 ? v3.tests : "-", v3 ? "widened " + v3.widened : ""),
    tile("breakable boxes", bb.report ? bb.boxes + " / " + bb.parts : "-", bb.status ? esc(bb.status.slice(0, 40)) : "off"),
    tile("IMPACT events", ev.count.IMPACT || 0, "player " + ((ev.impacts || {}).player || 0))].join("");
  $("co-window").innerHTML = (co.status && co.status.length ? co.status.map(s => `<div class="mono">${esc(s)}</div>`).join("") : `<div class="note">no coll-window lines in this proxy start (I76_COLL_WINDOW off?)</div>`) +
    (v3 ? `<div class="note">v3 part classes seen: ${esc(v3.classes)}, other ${v3.other}</div>` : "") +
    `<div class="note">"Misses" are not logged by the proxy; the closest measure is the stock-window share (pair tests the widened window did not cover). Contacts below are the telemetry's collision-damage calls.</div>`;
  $("co-bbox").innerHTML = bb.status || bb.report ? `<div class="mono">${esc(bb.status || "")}</div><div class="mono">${esc(bb.report || "")}</div>` : `<div class="note">no breakable-box line (I76_BREAKABLE_BOX not set)</div>`;
  C.coll.draw((co.hist || []).map((d, i) => ({ ...d, w: i * 30 })));
  $("co-contacts").innerHTML = S.events.filter(e => e.type === "IMPACT").slice(-60).reverse().map(e => `<div>${e.player ? "PLAYER" : "other "} source ${esc(e.source)} |${fmt(e.mag, 1)}| lost ${fmt(e.hp, 0)} hp <span class="note">frame ${e.frame}</span></div>`).join("") || `<div class="note">no contacts yet</div>`;
}

function renderTerrain() {
  const L = S.log || {}, fl = L.flash, tx = L.tex;
  $("te-tiles").innerHTML = [tile("camera lifts", L.lift_count || 0, fl ? fl.refused + " refused" : ""), tile("COCKPIT-UNDER", L.cockpit_count || 0, "cockpit eye under terrain"),
    tile("TERRAIN-DROP", (L.terrain_drops || []).length, fl ? "probe totals " + fl.events : "flash probe off?"),
    tile("draw losses", (L.draw_losses || []).length, L.draw ? "terrain " + L.draw.terrain_losses + ", triangles " + L.draw.triangle_losses : "draw probe off?"), tile("tex flushes", (L.flushes || []).length, tx ? "resident " + tx.resident_kb + " KB" : ""),
    tile("NO-SLOT", (L.tex_noslot || []).length, ""), tile("render interp", L.render_interp ? (/not applied|off/.test(L.render_interp) ? "off" : "on") : "-", esc((L.render_interp || "").slice(0, 40)))].join("");
  $("te-drops").innerHTML = (L.terrain_drops || []).length ? table(["#", "#frame", "#vertices", "#prev", "#eye above terrain m", "#terrain h", "#moved m", "cam mode", "camera"],
    L.terrain_drops.slice().reverse().map(d => [d.n, d.frame, d.vertices, d.prev, fmt(d.eye_above, 3), fmt(d.terrain, 2), fmt(d.moved, 2), d.cam_mode, d.camera.map(x => fmt(x, 1)).join(", ")]))
    : `<div class="note">no TERRAIN-DROP in this proxy start</div>`;
  if (fl) $("te-drops").innerHTML += `<div class="note">last 600 swaps: ${fl.scenes} scenes, min terrain vertices ${fl.vmin}, ${fl.zero} zero-terrain, ${fl.drops} drops, ${fl.pix} pixel flashes</div>`;
  $("te-lifts").innerHTML = ((L.lifts || []).length ? table(["#", "camera", "#mode", "#eye under m", "#terrain h", "setup"], L.lifts.slice(-12).reverse().map(l => [l.n, esc(l.which), l.mode == null ? "" : l.mode, fmt(l.depth, 3), fmt(l.terrain, 2), esc(l.setup)])) : `<div class="note">no camera lifts</div>`) +
    ((L.cockpit_under || []).length ? `<h3>COCKPIT-UNDER</h3>` + table(["#", "#eye under m", "#terrain h"], L.cockpit_under.slice(-8).reverse().map(c => [c.n, fmt(c.depth, 3), fmt(c.terrain, 2)])) : "");
  $("te-tex").innerHTML = (tx ? table(["last 600 swaps", "#downloads", "#KB", "#flushes", "#no-slot", "#resident KB", "#peak KB"], [["", tx.dl, tx.dl_kb, tx.flushes, tx.noslot, tx.resident_kb, tx.peak_kb]]) +
      `<div class="note">totals: ${tx.total_dl} downloads, ${tx.total_flushes} flushes, ${tx.total_noslot} no-slot (swap ${tx.swaps})</div>` : `<div class="note">no tex-census summary (I76_TEX_CENSUS off?)</div>`) +
    ((L.flushes || []).length ? `<h3>Flushes</h3>` + table(["#", "#swap", "#frame", "#downloads", "#KB", "#resident before KB"], L.flushes.slice(-10).reverse().map(f => [f.n, f.swap, f.frame, f.downloads, f.kb, f.resident_kb])) : "") +
    ((L.tex_noslot || []).length ? `<h3>NO-SLOT</h3>` + L.tex_noslot.slice(-5).map(s => `<div class="mono bad">${esc(s)}</div>`).join("") : "");
  const dw = L.draw, dl = L.draw_losses || [];
  $("te-draw").innerHTML = (dw ? `<div class="note">last 600 swaps (at swap ${dw.swaps}): main terrain polygons drawn min ${dw.drawn_min}, triangles min ${dw.tris_min}, LFB locks ${dw.lfb}, clipped away ${dw.clipped}, below the floor ${dw.below_floor}, past 4096 ${dw.past_4096}; totals ${dw.terrain_losses} terrain losses, ${dw.triangle_losses} triangle losses, ${dw.textures} terrain textures</div>`
      : `<div class="note">no draw-probe summary (I76_DRAW_PROBE off?)</div>`) +
    (dl.length ? table(["kind", "#", "#frame", "cam", "#drawn", "#previous", "detail"], dl.slice().reverse().slice(0, 15).map(d => [esc(d.kind), d.n, d.frame, d.cam_mode, d.drawn, d.prev,
      esc(d.kind === "TERRAIN-LOSS" ? `emitted ${d.emitted}, clipped ${d.clipped}, below floor ${d.below_floor} (floor ${d.floor}), past 4096 ${d.past_4096}, queued ${d.queued}` : `triangles ${d.triangles} (previous ${d.prev_triangles}), LFB locks ${d.lfb}`)]), "wrap") : "");
  const r = L.road, cl = L.clutter;
  $("te-pools").innerHTML = table(["", "value"], [
    ["road pool", r ? `${r.refused} polygons refused / ${r.frames} frames, node high water ${r.high_kb} of ${r.pool_kb} KB, refusals since start ${r.refusals_total}` : "-"],
    ["clutter", cl ? `${cl.us_avg} us avg, ${cl.us_max} us max, cells ${cl.cells_avg} avg, ${cl.tested} instances/frame, refused ${cl.refused}, pool ${cl.pool_kb} KB` : "-"],
    ["fixed step", L.fixed_step ? `${L.fixed_step.hz} steps/s (${L.fixed_step.ms} ms) ${L.fixed_step.state}` : "-"],
    ["render interp", esc(L.render_interp || "-")],
    ["fps (log)", L.fps ? `${L.fps.fps} fps, work ${L.fps.work_avg} ms avg / ${L.fps.work_max} max, cap wait ${L.fps.cap_wait} ms` : "-"],
  ].map(x => [x[0], esc(x[1])]), "wrap") + ((L.start_pos || []).length ? `<h3>Start position</h3>` + L.start_pos.map(s => `<div class="mono">${esc(s)}</div>`).join("") : "") +
    ((L.crashes || []).length ? `<h3>CRASH lines</h3>` + L.crashes.map(s => `<div class="mono bad">${esc(s)}</div>`).join("") : "");
}

// ------------------------------------------------------------------ trainer
let trBuilt = false;
async function trPost(body) {
  try {
    const r = await fetch("/api/trainer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json(); if (j.trainer) { S.trainer = j.trainer; renderTrainer(); }
  } catch (e) { console.error(e); }
}
function buildTrainer() {
  const t = S.trainer; if (!t || trBuilt) return; trBuilt = true;
  const holds = [["GOD", "God mode (armour, chassis, components, flats; play bits 0x18 - see campaign note)"], ["AMMO", "Unlimited ammo (play bit 0x04 + every slot 0x0fffffff - see campaign note)"],
    ["NOFLATS", "No flats (wheel flag +0x44 cleared, radius restored)"], ["COMPONENTS", "Components invulnerable (engine / susp / brakes / wheels / weapons at max)"],
    ["FREEZE_POS", "Freeze position (held where the car is, zero velocity)"]];
  $("tr-holds").innerHTML = holds.map(([k, l]) => `<div><label><input type="checkbox" data-hold="${k}"> ${esc(l)}</label></div>`).join("");
  $("tr-holds").addEventListener("change", e => { const k = e.target.dataset.hold; if (k) trPost({ action: "flags", flags: { [k]: e.target.checked } }); });
  $("tr-play").innerHTML = t.play_bits.map(b => `<label><input type="checkbox" data-bit="${b.bit}"> ${esc(b.name)} 0x${b.bit.toString(16).padStart(2, "0")}</label>`).join(" ");
  $("tr-hk").onchange = e => trPost({ action: "hotkeys", on: e.target.checked });
  $("tr-presets").innerHTML = t.presets.map(p => `<div class="bar"><button data-preset="${p.key}">Teleport: ${esc(p.label)}</button><span class="note">(${p.xyz.join(", ")}) ${esc(p.note)}</span></div>`).join("");
  document.querySelector("#tab-trainer").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.preset) return trPost({ action: "preset", key: b.dataset.preset });
    if (b.dataset.wp) return trPost({ action: b.dataset.wpact, i: +b.dataset.wp, still: b.dataset.still === "1" });
    const a = b.dataset.act; if (!a) return;
    const bits = [...document.querySelectorAll("#tr-play input:checked")].reduce((s, x) => s | +x.dataset.bit, 0);
    if (a === "ammo") return trPost({ action: "ammo", value: $("tr-ammo").value });
    if (a === "slot_ammo") return trPost({ action: "slot_ammo", slot: $("tr-slot").value, value: $("tr-slot-ammo").value });
    if (a === "teleport") return trPost({ action: "teleport", xyz: [$("tr-x").value, $("tr-y").value, $("tr-z").value] });
    if (a === "use_current") return trPost({ action: "use_current" }).then(() => setXyz(true));
    if (a === "play_set") {
      let ok = true;
      if (bits & 0x1c) ok = confirm("ammo / armour / chassis are the game's own cheater options. Once set, the game marks itself as cheated at the next Esc-menu close or mission end, saves them in I76PLYR.DEF, and refuses to advance the campaign after any won mission until you use 'Turn off cheater options'.\n\nFor the campaign, use the God / Unlimited ammo holds or the one-shots instead.\n\nSet them anyway?");
      return ok ? trPost({ action: "playflags", bits, on: true, confirmed: true }) : null;
    }
    if (a === "play_clear") return trPost({ action: "playflags", bits, on: false });
    if (a === "restore_still") return trPost({ action: "restore", still: true });
    return trPost({ action: a });
  });
}
function stateLine(m) {
  return `(${m.pos.map(x => x.toFixed(1)).join(", ")}) ${m.kmh.toFixed(0)} km/h, heading ${m.heading.toFixed(0)}, pitch ${m.pitch.toFixed(1)}, roll ${m.roll.toFixed(1)}${m.airborne ? ", airborne" : ""}`;
}
let xyzSeeded = false;
function setXyz(force) {
  const t = S.trainer; if (!t) return;
  if (force || !xyzSeeded) { $("tr-x").value = t.xyz[0]; $("tr-y").value = t.xyz[1]; $("tr-z").value = t.xyz[2]; xyzSeeded = true; }
}
let trLogId = 0;
function renderTrainer() {
  const t = S.trainer; const pill = $("pill-trn");
  if (!t) { pill.className = "pill"; $("tr-attach").innerHTML = `<div class="note">trainer disabled (--no-trainer)</div>`; return; }
  pill.className = "pill " + (t.mode === "none" ? "" : "live"); pill.textContent = "trainer: " + t.mode;
  buildTrainer(); setXyz(false);
  const attachChanged = H("tr-attach", `<div class="bar"><button data-act="attach">Attach</button>
    <label><input type="checkbox" id="tr-any" ${t.allow_any ? "checked" : ""}> allow non-sandbox game (the daily driver - read AGENTS.md first)</label>
    <span>${t.attached ? "pid " + t.pid + " " + esc(t.path) + (t.not_sandbox ? ' <b class="warn">NOT THE SANDBOX</b>' : "") : esc(t.attach_error || (t.attach_enabled ? "not attached" : "attach disabled (--no-attach)"))}</span></div>
    <div class="note">sandbox: ${esc(t.sandbox)} &middot; mode <b>${esc(t.mode)}</b> - ${esc(t.pdetail)}</div>`);
  if (attachChanged) $("tr-any").onchange = e => trPost({ action: "allow_any", on: e.target.checked });
  document.querySelectorAll("#tr-holds input").forEach(i => { i.checked = !!t.flags[i.dataset.hold]; });
  const st = t.status, L = [];
  if (t.proxy) L.push(`proxy    applied 0x${t.proxy.applied.toString(16).padStart(4, "0")}  player_present ${t.proxy.player_present}  faults ${t.proxy.faults}  last cmd ${t.proxy.cmd_result}  msg: ${t.proxy.msg || "-"}`);
  L.push("source   " + (t.tel_live ? "telemetry (I76 Debug's stream)" : t.attached ? "direct reads" : "nothing attached"));
  if (t.play_flags != null) L.push(`play     0x${(t.play_flags || 0).toString(16).padStart(2, "0")}: ${t.play_names.join(", ") || "none"}   cheats-used marker 0x535f78 = ${t.cheat_marker}${t.cheat_marker ? "  <- WINS WILL NOT ADVANCE THE CAMPAIGN: 'Turn off cheater options'" : ""}`);
  if (!st.present) L.push("player   absent (menu, loading, or no mission)");
  else {
    L.push(`player   present   pos ${st.pos.map(x => x.toFixed(1)).join(" ")}   speed ${st.speed.toFixed(1)} m/s (${(st.speed * 3.6).toFixed(0)} km/h)`);
    for (const k of ["armour", "chassis"]) L.push(k.padEnd(9) + ["F", "L", "R", "B"].map((n, i) => `${n} ${st[k][i]}/${st[k + "_max"][i]}`).join("  ") + (st[k + "_hud"] ? `   hud ${st[k + "_hud"].slice(0, 4).join(" ")} side4 ${st[k + "_hud"][4]}` : ""));
    L.push(`engine   ${st.engine.join("/")}   susp ${st.susp.join("/")}   brake ${st.brake.join("/")}`);
    L.push("wheels   " + st.wheels.map(w => w.name + " " + (w.present ? (w.flat ? "FLAT" : w.hp + "/" + w.max) : "-")).join("  "));
    L.push(st.weapon != null ? `weapon   ${st.weapon}  ammo ${st.weapon_ammo}` : "weapon   (selected weapon needs telemetry; the slot list below is live)");
  }
  if (t.slots.length) L.push("slots    " + t.slots.map(s => `${s.slot}:${s.name}=${s.ammo === "unlimited" ? "inf" : s.ammo}`).join("  "));
  $("tr-status").textContent = L.join("\n");
  $("tr-campaign").textContent = t.campaign;
  const sel = $("tr-slot"), want = t.slots.map(s => `${s.slot}: ${s.name} (${s.ammo})`).join("|");
  if (sel.dataset.v !== want) { const cur = sel.value; sel.innerHTML = t.slots.map(s => `<option value="${s.slot}">${s.slot}: ${esc(s.name)} (${s.ammo})</option>`).join(""); if (cur) sel.value = cur; sel.dataset.v = want; }
  $("tr-hk").checked = !!t.hotkeys;
  const q = t.quick, ex = t.ext;
  H("tr-quick", `full state: ${esc(t.full_state)}` + (ex ? ` &middot; in-game keys ${ex.hotkeys & 1 ? "ON" : "off"} (served: ${ex.hotkey_stores} stores, ${ex.hotkey_restores} restores)` : "") +
    `<br>quick slot: ${q ? esc(stateLine(q)) : "- empty - (Store now, or Ctrl+9 in the game)"}`);
  H("tr-wps", t.waypoints.map((w, i) => `<div class="bar">waypoint ${i + 1} <span class="note" style="min-width:330px">${w ? esc((w.summary ? stateLine(w.summary) : `(${w.x.toFixed(1)}, ${w.y.toFixed(1)}, ${w.z.toFixed(1)}) position only`) + " " + (w.saved || "")) : "- empty -"}</span>
    <button data-wp="${i}" data-wpact="wp_save">Save here</button><button data-wp="${i}" data-wpact="wp_go">Go</button><button data-wp="${i}" data-wpact="wp_go" data-still="1">Go stopped</button><button data-wp="${i}" data-wpact="wp_from_quick" title="copy the quick slot (Ctrl+9) into this waypoint">&larr; quick</button></div>`).join(""));
  const last = t.log.length ? t.log[t.log.length - 1].id : 0;
  if (last !== trLogId) { trLogId = last; const el = $("tr-log"); el.innerHTML = t.log.map(l => `<div>${esc(l.t)} ${esc(l.text)}</div>`).join(""); el.scrollTop = el.scrollHeight; }
}

// ------------------------------------------------------------------ log
const QUICK = ["fps:", "coll-window", "breakable", "cam-ground", "TERRAIN-DROP", "draw-probe", "tex-census", "start-pos", "not applied", "telemetry", "trainer", "CRASH"];
$("log-quick").innerHTML = QUICK.map(q => `<button data-q="${esc(q)}">${esc(q)}</button>`).join("") + `<button data-q="">all</button>`;
$("log-quick").onclick = e => { const b = e.target.closest("button"); if (b) { $("log-q").value = b.dataset.q; renderLog(true); } };
$("log-q").oninput = () => renderLog(true);
function renderLog(full) {
  const q = $("log-q").value.toLowerCase(), el = $("log-lines");
  const lines = (q ? S.log_tail.filter(l => l.text.toLowerCase().includes(q)) : S.log_tail).slice(-1500);
  el.innerHTML = lines.map(l => `<div class="${/not applied|FAILED|CRASH|refused/.test(l.text) ? "bad" : ""}">${esc(l.text)}</div>`).join("") || `<div class="note">no log lines</div>`;
  if ($("log-follow").checked) el.scrollTop = el.scrollHeight;
  $("log-path").textContent = S.log ? (S.log.path || "") : "";
}

// ------------------------------------------------------------------ logger (header pill + buttons on every tab, card on Trainer)
async function lgPost(body) {
  try {
    const r = await fetch("/api/logger", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json(); if (j.logger) S.logger = j.logger; if (j.msg) S.lgMsg = j.msg; renderLogger();
  } catch (e) { console.error(e); }
}
function renderLogger() {
  const l = S.logger, p = $("pill-lg");
  if (!l) { p.className = "pill"; p.textContent = "logger off"; return; }
  p.className = "pill " + (l.recording ? "live" : "");
  p.textContent = l.recording ? `logging ${fmt(l.seconds, 0)} s, ${l.rows} rows${l.missed ? ", " + l.missed + " missed" : ""}${l.marks ? ", " + l.marks + " marks" : ""}` : (l.auto ? "logger: auto (armed)" : "logger: idle");
  $("lg-toggle").textContent = l.recording ? "Stop log" : "Log";
  const a = $("lg-auto"); if (a && document.activeElement !== a) a.checked = !!l.auto;
  const hk = l.hotkeys && l.hotkeys.registered ? Object.entries(l.hotkeys.registered).map(([k, v]) => k + " = " + v).join(", ") : "off (start with --hotkeys)";
  const he = l.hotkeys && l.hotkeys.errors && Object.keys(l.hotkeys.errors).length ? "\nhotkey errors: " + Object.values(l.hotkeys.errors).join("; ") : "";
  const last = (l.history || []).slice(-3).map(h => `  ${h.dir}  ${h.seconds} s, ${h.frames} frames, ${h.rows} rows, ${h.missed} missed, ${h.marks} marks`).join("\n");
  const el = $("lg-status");
  if (el) el.textContent = `${l.recording ? "RECORDING " + l.dir + "  (" + l.started_by + ", phase " + l.phase + ")" : "idle"}${S.lgMsg ? "\nlast: " + S.lgMsg : ""}
${l.note || ""}
reader (slow fields, read-only): ${l.reader}${l.reader_check ? "  check " + JSON.stringify(l.reader_check) : ""}${l.arcade ? "\nARCADE PHYS. flag 0x10000 on " + l.arcade + " rows" : ""}
hotkeys: ${hk}${he}
folder: ${l.rundir || l.root}
${l.summary || ""}${last ? "\nfinished:\n" + last : ""}`;
}
document.addEventListener("click", e => {
  const id = e.target && e.target.id;
  if (id === "lg-toggle") lgPost({ op: "toggle" });
  else if (id === "lg-start") lgPost({ op: "start" });
  else if (id === "lg-stop") lgPost({ op: "stop" });
  else if (id === "lg-mark") lgPost({ op: "mark", label: ($("lg-label") || {}).value || "" });
  else if (id === "lg-mark2") lgPost({ op: "mark", label: $("lg-label").value || "" });
  else if (id === "lg-auto") lgPost({ op: "auto", on: e.target.checked });
});

// ------------------------------------------------------------------ store + stream
function apply(d, snap) {
  if (snap) { S.samples = d.samples || []; S.hsamples = d.hsamples || []; S.events = d.events || []; S.hap_events = d.hap_events || []; S.log_tail = d.log_tail || []; }
  else {
    if (d.samples && d.samples.length) S.samples = S.samples.concat(d.samples).slice(-MAXS);
    if (d.hsamples && d.hsamples.length) S.hsamples = S.hsamples.concat(d.hsamples).slice(-MAXS);
    if (d.events && d.events.length) S.events = S.events.concat(d.events).slice(-1000);
    if (d.hap_events && d.hap_events.length) S.hap_events = S.hap_events.concat(d.hap_events).slice(-300);
    if (d.log_tail && d.log_tail.length) { S.log_tail = S.log_tail.concat(d.log_tail).slice(-4000); if (TAB === "log") renderLog(); }
  }
  for (const k of ["overview", "ev", "hap", "log", "trainer", "trail", "markers", "logger"]) if (d[k] !== undefined) S[k] = d[k];
  if ((d.events && d.events.length) || (d.hap_events && d.hap_events.length) || snap) S.feedDirty = true;
  dirty = true;
}
function pills() {
  const o = S.overview; if (!o) return;
  const set = (id, live, txt, title) => { const p = $(id); p.className = "pill " + (live ? "live" : (txt ? "stale" : "")); p.textContent = txt || p.textContent; if (title) p.title = title; };
  set("pill-tel", o.tel_live, "telemetry" + (o.tel_live ? " " + fmt(o.fps, 0) + " fps" : ""), o.tel_src);
  set("pill-hap", o.hap_live, "haptics", o.hap_src);
  set("pill-log", S.log && S.log.lines > 0, "log", S.log ? S.log.path : "");
}
function connect() {
  const es = new EventSource("/api/stream?hz=20");
  es.addEventListener("snapshot", e => { apply(JSON.parse(e.data), true); S.connected = true; });
  es.onmessage = e => apply(JSON.parse(e.data), false);
  es.onerror = () => { S.connected = false; document.title = "I76 Debug (disconnected)"; };
  es.onopen = () => { document.title = "I76 Debug"; };
}
const RENDER = { overview: renderOverview, telemetry: renderTelemetry, events: renderEvents, ffb: renderFfb, rumble: renderRumble, lfe: renderLfe,
                 motion: renderMotion, collision: renderCollision, terrain: renderTerrain, trainer: renderTrainer, log: () => {} };
let lastDraw = 0;
function frame(ts) {
  requestAnimationFrame(frame);
  if (!dirty || ts - lastDraw < 66 || $("pause").checked) return;
  lastDraw = ts; dirty = false;
  pills();
  try {
    renderLogger();
    RENDER[TAB] && RENDER[TAB]();
    if (TAB === "events" && S.feedDirty) { renderFeed(); S.feedDirty = false; }
    if (TAB !== "trainer" && S.trainer) { const p = $("pill-trn"); p.className = "pill " + (S.trainer.mode === "none" ? "" : "live"); p.textContent = "trainer: " + S.trainer.mode; }
  } catch (e) { console.error(e); }
}
window.addEventListener("resize", () => { dirty = true; });
// ?poll=1: poll /api/state instead of the event stream (a proxy that buffers SSE, a headless capture)
async function poll() {
  try { const r = await fetch("/api/state?history=1800"); apply(await r.json(), true); document.title = "I76 Debug"; }
  catch (e) { document.title = "I76 Debug (disconnected)"; }
  setTimeout(poll, 500);
}
showTab(RENDER[TAB] ? TAB : "overview");
if (/[?&]poll=1/.test(location.search)) poll(); else connect();
requestAnimationFrame(frame);
