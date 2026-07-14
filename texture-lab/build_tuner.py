#!/usr/bin/env python3
"""Build a self-contained interactive HTML tuner for dashboard texture processing.
Embeds each panel's ORIGINAL (native) + ESRGAN 4x (rich source) as data URIs, then
lets you dial downscale filter, luminance-sharpen amount/radius, and 3-way blend
weights (original / esrgan / sharpen) live, at native + cockpit-display size.
The ESRGAN 4x is pre-baked (the one step a browser can't do); everything else -
downscale, unsharp, blend - runs live in-canvas exactly like the Python pipeline.

Usage: python build_tuner.py STUDY_DIR OUT_HTML
"""
import os, sys, base64, glob, json

study, out_html = sys.argv[1:3]

def b64(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

PANELS = []
for label, tex in [("Radar", "zradf000"), ("Weapons", "zwpe"), ("Mr Damage", "zsy_")]:
    orig = glob.glob(os.path.join(study, f"*_{tex}_original_*.png"))[0]
    esr = glob.glob(os.path.join(study, f"*_{tex}_esrgan4x_*.png"))[0]
    PANELS.append({"label": label, "tex": tex, "orig": b64(orig), "esrgan": b64(esr)})

DATA = json.dumps(PANELS)

HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>I76 Dashboard Texture Tuner</title>
<style>
 body{margin:0;background:#14161a;color:#dfe3ea;font:14px/1.5 system-ui,sans-serif}
 header{padding:14px 20px;background:#1c1f26;border-bottom:1px solid #2a2f3a}
 h1{margin:0;font-size:17px} .sub{color:#8b93a3;font-size:12px;margin-top:3px}
 .wrap{display:flex;gap:20px;padding:20px;flex-wrap:wrap}
 .controls{flex:0 0 300px;background:#1c1f26;border:1px solid #2a2f3a;border-radius:8px;padding:16px}
 .stage{flex:1 1 620px;min-width:420px}
 label.row{display:block;margin:14px 0 4px;font-size:12px;color:#aeb6c6}
 input[type=range]{width:100%} .val{float:right;color:#e8c56a;font-variant-numeric:tabular-nums}
 select,button{background:#262b34;color:#dfe3ea;border:1px solid #3a4150;border-radius:6px;padding:7px 10px;font-size:13px}
 button{cursor:pointer} button:hover{background:#2f3542}
 .panestrip{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px}
 .pane{background:#0e1013;border:1px solid #2a2f3a;border-radius:8px;padding:10px}
 .pane h3{margin:0 0 8px;font-size:12px;color:#8b93a3;font-weight:600;letter-spacing:.04em}
 canvas{image-rendering:pixelated;display:block;background:#000;border-radius:4px}
 .readout{margin-top:14px;padding:10px;background:#0e1013;border:1px solid #2a2f3a;border-radius:6px;
   font:12px/1.5 ui-monospace,monospace;color:#9fd0a0;white-space:pre-wrap}
 .hint{color:#8b93a3;font-size:11px;margin-top:6px}
 .presets{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
 .presets button{padding:5px 8px;font-size:11px}
</style></head><body>
<header>
 <h1>Interstate '76 &mdash; Dashboard Texture Tuner</h1>
 <div class="sub">ESRGAN 4x is pre-baked; downscale &middot; luminance-sharpen &middot; 3-way blend run live. Native size is the engine ceiling &mdash; the "display" view is how the cockpit stretches it.</div>
</header>
<div class="wrap">
 <div class="controls">
  <label class="row">Panel</label>
  <select id="panel"></select>

  <label class="row">Downscale filter <span class="val" id="vfilter">high</span></label>
  <select id="filter" style="width:100%">
   <option value="high">smooth (bilinear/HQ)</option>
   <option value="pixelated">nearest (crisp/pixel)</option>
  </select>

  <label class="row">Sharpen amount <span class="val" id="vsharp">40%</span></label>
  <input type="range" id="sharp" min="0" max="200" value="40">
  <label class="row">Sharpen radius <span class="val" id="vrad">1.0</span></label>
  <input type="range" id="rad" min="1" max="30" value="10">
  <div class="hint">luminance-only &mdash; no colour fringing on the hazard stripes / red bars</div>

  <label class="row">Blend weight &mdash; ORIGINAL <span class="val" id="vwo">33%</span></label>
  <input type="range" id="wo" min="0" max="100" value="33">
  <label class="row">Blend weight &mdash; ESRGAN <span class="val" id="vwe">33%</span></label>
  <input type="range" id="we" min="0" max="100" value="33">
  <label class="row">Blend weight &mdash; SHARPEN <span class="val" id="vws">33%</span></label>
  <input type="range" id="ws" min="0" max="100" value="34">
  <div class="hint">weights auto-normalise to 100%</div>

  <div class="presets">
   <button data-p="orig">Original only</button>
   <button data-p="esrgan">ESRGAN only</button>
   <button data-p="sharp">Sharpen only</button>
   <button data-p="333">33/33/33</button>
   <button data-p="radar">Radar-safe</button>
  </div>

  <div class="readout" id="readout"></div>
  <div class="hint">Match in Python: reencode_all uses the same downscale+unsharp+blend. Tell me these numbers and I'll bake the whole dashboard with them.</div>
 </div>

 <div class="stage">
  <div class="panestrip">
   <div class="pane"><h3>ORIGINAL (native x3)</h3><canvas id="cOrig"></canvas></div>
   <div class="pane"><h3>RESULT (native x3)</h3><canvas id="cNative"></canvas></div>
  </div>
  <div class="panestrip">
   <div class="pane"><h3>ORIGINAL &mdash; cockpit display size</h3><canvas id="cOrigBig"></canvas></div>
   <div class="pane"><h3>RESULT &mdash; cockpit display size</h3><canvas id="cBig"></canvas></div>
  </div>
 </div>
</div>
<script>
const PANELS = __DATA__;
const $ = id => document.getElementById(id);
const sel = $('panel');
PANELS.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=p.label+' ('+p.tex+')';sel.appendChild(o);});

let W=256,H=128, orig=null, esr4x=null;
const NZ=3, DZ=5;   // native zoom, display zoom

function loadPanel(i){
 const p=PANELS[i];
 orig=new Image(); esr4x=new Image();
 let n=0; const done=()=>{ if(++n===2){ W=orig.width; H=orig.height; render(); } };
 orig.onload=done; esr4x.onload=done; orig.src=p.orig; esr4x.src=p.esrgan;
}
function ctx(w,h){const c=document.createElement('canvas');c.width=w;c.height=h;return c.getContext('2d',{willReadFrequently:true});}

function downscaleESRGAN(filter){
 const c=ctx(W,H);
 c.imageSmoothingEnabled = filter!=='pixelated';
 c.imageSmoothingQuality='high';
 c.drawImage(esr4x,0,0,W,H);
 return c.getImageData(0,0,W,H);
}
function origData(){const c=ctx(W,H);c.drawImage(orig,0,0);return c.getImageData(0,0,W,H);}

// separable box-ish blur on luminance, returns Float32 Y and blurred Y
function lumSharpen(img, amount, radius){
 const d=img.data, n=W*H, Y=new Float32Array(n);
 for(let i=0;i<n;i++){Y[i]=0.299*d[i*4]+0.587*d[i*4+1]+0.114*d[i*4+2];}
 const r=Math.max(1,Math.round(radius));
 const tmp=new Float32Array(n), Yb=new Float32Array(n);
 // horizontal
 for(let y=0;y<H;y++){for(let x=0;x<W;x++){let s=0,c=0;for(let k=-r;k<=r;k++){const xx=x+k;if(xx>=0&&xx<W){s+=Y[y*W+xx];c++;}}tmp[y*W+x]=s/c;}}
 // vertical
 for(let y=0;y<H;y++){for(let x=0;x<W;x++){let s=0,c=0;for(let k=-r;k<=r;k++){const yy=y+k;if(yy>=0&&yy<H){s+=tmp[yy*W+x];c++;}}Yb[y*W+x]=s/c;}}
 const out=new ImageData(W,H); const o=out.data; const a=amount/100;
 for(let i=0;i<n;i++){
  const delta=a*(Y[i]-Yb[i]);
  for(let ch=0;ch<3;ch++){ o[i*4+ch]=Math.max(0,Math.min(255, d[i*4+ch]+delta)); }
  o[i*4+3]=d[i*4+3];
 }
 return out;
}
function blend3(a,b,c,wa,wb,wc){
 const out=new ImageData(W,H),o=out.data,da=a.data,db=b.data,dc=c.data,n=W*H;
 const s=wa+wb+wc||1; wa/=s;wb/=s;wc/=s;
 for(let i=0;i<n*4;i++){o[i]=da[i]*wa+db[i]*wb+dc[i]*wc;}
 for(let i=0;i<n;i++){o[i*4+3]=da[i*4+3];} // keep original alpha
 return out;
}
function paint(cv,img,zoom,smooth){
 cv.width=W*zoom; cv.height=H*zoom;
 const tc=ctx(W,H); tc.putImageData(img,0,0);
 const g=cv.getContext('2d'); g.imageSmoothingEnabled=smooth; g.imageSmoothingQuality='high';
 g.drawImage(tc.canvas,0,0,W*zoom,H*zoom);
}
function render(){
 const filter=$('filter').value;
 const amt=+$('sharp').value, rad=+$('rad').value/10;
 let wo=+$('wo').value, we=+$('we').value, ws=+$('ws').value;
 const od=origData(), ed=downscaleESRGAN(filter), sd=lumSharpen(ed,amt,rad);
 const res=blend3(od,ed,sd,wo,we,ws);
 paint($('cOrig'),od,NZ,false);
 paint($('cNative'),res,NZ,false);
 paint($('cOrigBig'),od,DZ,true);
 paint($('cBig'),res,DZ,true);
 $('vfilter').textContent=filter==='pixelated'?'nearest':'high';
 $('vsharp').textContent=amt+'%'; $('vrad').textContent=rad.toFixed(1);
 const s=(wo+we+ws)||1;
 $('vwo').textContent=Math.round(wo/s*100)+'%';
 $('vwe').textContent=Math.round(we/s*100)+'%';
 $('vws').textContent=Math.round(ws/s*100)+'%';
 $('readout').textContent=
  'downscale : '+(filter==='pixelated'?'nearest':'bilinear/HQ')+'\n'+
  'sharpen   : '+amt+'%  radius '+rad.toFixed(1)+'  (luminance)\n'+
  'blend     : orig '+Math.round(wo/s*100)+'%  esrgan '+Math.round(we/s*100)+'%  sharp '+Math.round(ws/s*100)+'%';
}
const PRESETS={
 orig:[40,10,100,0,0], esrgan:[40,10,0,100,0], sharp:[40,10,0,0,100],
 '333':[40,10,33,33,34], radar:[25,15,60,15,25]
};
document.querySelectorAll('.presets button').forEach(b=>b.onclick=()=>{
 const [a,r,wo,we,ws]=PRESETS[b.dataset.p];
 $('sharp').value=a; $('rad').value=r; $('wo').value=wo; $('we').value=we; $('ws').value=ws; render();
});
['filter','sharp','rad','wo','we','ws'].forEach(id=>$(id).addEventListener('input',render));
sel.addEventListener('change',()=>loadPanel(+sel.value));
loadPanel(0);
</script></body></html>"""

open(out_html, "w", encoding="utf-8").write(HTML.replace("__DATA__", DATA))
print("wrote", out_html, f"({os.path.getsize(out_html)//1024} KB)")
