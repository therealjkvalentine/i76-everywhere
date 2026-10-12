/* charts.js - small canvas charts for I76 Debug (no library). StripChart: time series (lines, or signed stacked areas)
   with a crosshair tooltip; BarChart: one value per category (the spectrum). Colors are CSS tokens (--s1..--s8). */
"use strict";
const CSS = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const SERIES = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"];
function seriesColor(i) { return CSS(SERIES[i % SERIES.length]); }
function fmt(v, d) { if (v == null || !isFinite(v)) return "-"; const a = Math.abs(v); d = d != null ? d : (a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 3); return v.toFixed(d); }

function fitCanvas(c) {
  const r = c.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  const w = Math.max(10, Math.round(r.width)), h = Math.max(10, Math.round(r.height));
  if (c.width !== w * dpr || c.height !== h * dpr) { c.width = w * dpr; c.height = h * dpr; }
  const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { g, w, h };
}

class StripChart {
  /* opts: series [{key, label, get(sample) -> number, color?}], stacked (signed stack), min/max (fixed), sym (symmetric about 0),
     window seconds (function or number), unit */
  constructor(canvas, legend, opts) {
    this.c = canvas; this.opts = opts; this.data = []; this.hover = null; this.legendEl = legend;
    this.colors = opts.series.map((s, i) => s.color || seriesColor(i));
    if (legend) this.renderLegend();
    canvas.addEventListener("mousemove", e => { const r = canvas.getBoundingClientRect(); this.hover = { x: e.clientX - r.left, cx: e.clientX, cy: e.clientY }; this.draw(); });
    canvas.addEventListener("mouseleave", () => { this.hover = null; TIP.hidden = true; this.draw(); });
  }
  setSeries(series) {
    const keys = series.map(s => s.key).join("|");
    if (keys === this.opts.series.map(s => s.key).join("|")) return;
    this.opts.series = series; this.colors = series.map((s, i) => s.color || seriesColor(i)); if (this.legendEl) this.renderLegend();
  }
  renderLegend() {
    if (this.opts.series.length < 2) { this.legendEl.innerHTML = ""; return; }
    this.legendEl.innerHTML = this.opts.series.map((s, i) => `<span><i style="background:${this.colors[i]}"></i>${s.label}</span>`).join("");
  }
  win() { const w = this.opts.window; return typeof w === "function" ? w() : (w || 30); }
  draw(data) {
    if (data) this.data = data;
    if (!this.c.offsetParent) return;                   // hidden tab
    const { g, w, h } = fitCanvas(this.c), o = this.opts, D = this.data, S = o.series;
    const padL = 44, padR = 8, padT = 6, padB = 16, pw = w - padL - padR, ph = h - padT - padB;
    g.clearRect(0, 0, w, h);
    if (!D.length) { g.fillStyle = CSS("--muted"); g.font = "12px system-ui"; g.fillText("no data", padL + 8, padT + 18); return; }
    const tEnd = D[D.length - 1].w, tStart = tEnd - this.win();
    let i0 = 0; while (i0 < D.length - 1 && D[i0].w < tStart) i0++;
    const vis = D.slice(Math.max(0, i0 - 1));
    // values (stacked: positive parts stack up, negative parts stack down)
    const vals = vis.map(d => S.map(s => { const v = s.get(d); return v == null || !isFinite(v) ? null : v; }));
    let lo = Infinity, hi = -Infinity;
    if (o.stacked) vals.forEach(r => { let p = 0, n = 0; r.forEach(v => { if (v > 0) p += v; else if (v < 0) n += v; }); hi = Math.max(hi, p); lo = Math.min(lo, n); });
    else vals.forEach(r => r.forEach(v => { if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
    if (o.min != null) lo = Math.min(o.min, lo === Infinity ? o.min : lo);
    if (o.max != null) hi = Math.max(o.max, hi === -Infinity ? o.max : hi);
    if (o.fixed) { lo = o.min; hi = o.max; }
    if (!isFinite(lo) || !isFinite(hi)) { lo = 0; hi = 1; }
    if (o.sym) { const m = Math.max(Math.abs(lo), Math.abs(hi)); lo = -m; hi = m; }
    if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
    const span = hi - lo; hi += span * 0.05; if (!o.fixed && lo !== 0) lo -= span * 0.05;
    const X = t => padL + (t - tStart) / (tEnd - tStart || 1) * pw, Y = v => padT + (hi - v) / (hi - lo) * ph;
    // grid + axis labels (recessive)
    g.strokeStyle = CSS("--grid"); g.lineWidth = 1; g.fillStyle = CSS("--muted"); g.font = "10px system-ui"; g.textAlign = "right";
    for (let k = 0; k <= 3; k++) { const v = lo + (hi - lo) * k / 3, y = Math.round(Y(v)) + 0.5; g.beginPath(); g.moveTo(padL, y); g.lineTo(w - padR, y); g.stroke(); g.fillText(fmt(v), padL - 4, y + 3); }
    if (lo < 0 && hi > 0) { g.strokeStyle = CSS("--axis"); const y = Math.round(Y(0)) + 0.5; g.beginPath(); g.moveTo(padL, y); g.lineTo(w - padR, y); g.stroke(); }
    g.textAlign = "left"; g.fillText("-" + this.win() + " s", padL, h - 3); g.textAlign = "right"; g.fillText("now", w - padR, h - 3);
    g.save(); g.beginPath(); g.rect(padL, padT, pw, ph); g.clip();
    if (o.stacked) {
      const base = vis.map(() => ({ p: 0, n: 0 }));
      S.forEach((s, si) => {
        const top = [], bot = [];
        vis.forEach((d, k) => { const v = vals[k][si] || 0, b = base[k]; if (v >= 0) { bot.push(b.p); b.p += v; top.push(b.p); } else { top.push(b.n); b.n += v; bot.push(b.n); } });
        g.beginPath();
        vis.forEach((d, k) => { const x = X(d.w), y = Y(top[k]); k ? g.lineTo(x, y) : g.moveTo(x, y); });
        for (let k = vis.length - 1; k >= 0; k--) g.lineTo(X(vis[k].w), Y(bot[k]));
        g.closePath(); g.fillStyle = this.colors[si]; g.globalAlpha = 0.85; g.fill(); g.globalAlpha = 1;
      });
    } else {
      g.lineWidth = 1.5; g.lineJoin = "round";
      S.forEach((s, si) => {
        g.strokeStyle = this.colors[si]; g.beginPath(); let pen = false;
        vis.forEach((d, k) => { const v = vals[k][si]; if (v == null) { pen = false; return; } const x = X(d.w), y = Y(v); pen ? g.lineTo(x, y) : g.moveTo(x, y); pen = true; });
        g.stroke();
      });
    }
    g.restore();
    // hover: crosshair + tooltip with every series at the nearest sample
    if (this.hover && this.hover.x >= padL && this.hover.x <= w - padR) {
      const t = tStart + (this.hover.x - padL) / pw * (tEnd - tStart);
      let best = 0; vis.forEach((d, k) => { if (Math.abs(d.w - t) < Math.abs(vis[best].w - t)) best = k; });
      const x = Math.round(X(vis[best].w)) + 0.5;
      g.strokeStyle = CSS("--muted"); g.beginPath(); g.moveTo(x, padT); g.lineTo(x, padT + ph); g.stroke();
      const rows = S.map((s, si) => `<div><i style="background:${this.colors[si]}"></i>${s.label}: <b>${fmt(vals[best][si])}</b>${o.unit ? " " + o.unit : ""}</div>`).join("");
      TIP.innerHTML = `<div style="color:var(--muted)">${fmt(vis[best].w - tEnd, 2)} s</div>${rows}`;
      TIP.hidden = false; TIP.style.left = (this.hover.cx + 14) + "px"; TIP.style.top = (this.hover.cy + 10) + "px";
      const tr = TIP.getBoundingClientRect(); if (tr.right > window.innerWidth - 8) TIP.style.left = (this.hover.cx - tr.width - 14) + "px";
    }
  }
}

class BarChart {
  constructor(canvas, opts) {
    this.c = canvas; this.opts = opts; this.labels = []; this.values = [];
    canvas.addEventListener("mousemove", e => { const r = canvas.getBoundingClientRect(); this.hover = { x: e.clientX - r.left, cx: e.clientX, cy: e.clientY }; this.draw(); });
    canvas.addEventListener("mouseleave", () => { this.hover = null; TIP.hidden = true; this.draw(); });
  }
  draw(labels, values) {
    if (labels) { this.labels = labels; this.values = values; }
    if (!this.c.offsetParent) return;
    const { g, w, h } = fitCanvas(this.c), L = this.labels, V = this.values, o = this.opts;
    const padL = 36, padR = 6, padT = 6, padB = 16, pw = w - padL - padR, ph = h - padT - padB;
    g.clearRect(0, 0, w, h);
    if (!L.length) { g.fillStyle = CSS("--muted"); g.font = "12px system-ui"; g.fillText("no data", padL + 8, padT + 18); return; }
    const hi = Math.max(o.min || 0, ...V) * 1.1 || 1, bw = pw / L.length;
    g.strokeStyle = CSS("--grid"); g.fillStyle = CSS("--muted"); g.font = "10px system-ui"; g.textAlign = "right";
    for (let k = 0; k <= 2; k++) { const v = hi * k / 2, y = Math.round(padT + ph - v / hi * ph) + 0.5; g.beginPath(); g.moveTo(padL, y); g.lineTo(w - padR, y); g.stroke(); g.fillText(fmt(v), padL - 4, y + 3); }
    g.fillStyle = CSS("--s1");
    V.forEach((v, i) => { const bh = Math.max(0, v / hi * ph), x = padL + i * bw + 1; g.beginPath(); g.roundRect ? g.roundRect(x, padT + ph - bh, Math.max(1, bw - 2), bh, [3, 3, 0, 0]) : g.rect(x, padT + ph - bh, bw - 2, bh); g.fill(); });
    g.fillStyle = CSS("--muted"); g.textAlign = "center";
    L.forEach((l, i) => { if (i % 2 === 0) g.fillText(l, padL + (i + 0.5) * bw, h - 3); });
    if (this.hover) {
      const i = Math.floor((this.hover.x - padL) / bw);
      if (i >= 0 && i < L.length) {
        TIP.innerHTML = `${L[i]}${o.unit || ""}: <b>${fmt(V[i], 4)}</b>`; TIP.hidden = false;
        TIP.style.left = (this.hover.cx + 14) + "px"; TIP.style.top = (this.hover.cy + 10) + "px";
      }
    }
  }
}
const TIP = document.getElementById("tip");
