#!/usr/bin/env python3
"""Local net-GT verification UI. Clean wires-only base image; the UI draws labelled
component boxes itself so the diagram and the side panel use identical labels (R2, C8...).
Edits electrical-net membership and saves to real_nets.json (scoring ignores non-electrical
pins + pin names). Run: python gt_verify_ui.py [port]."""
from __future__ import annotations
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# repo-relative paths (this file lives at wire_detection/benchmark/gt_verify_ui.py)
ROOT = Path(__file__).resolve().parents[2]
GT = ROOT / "ground_truth" / "real_nets_working.json"   # working file the UI edits (34 imgs)
CLEAN = ROOT / "ground_truth" / "net_gt_ui_overlays"     # wires-only overlays per image
META = json.loads((ROOT / "ground_truth" / "net_gt_ui_meta.json").read_text())  # bboxes
TYPE_ABBR = {
    "resistor": "R", "capacitor-unpolarized": "C", "capacitor-polarized": "C",
    "capacitor-adjustable": "C", "inductor": "L", "voltage-DC": "V", "voltage-AC": "V",
    "voltage-battery": "V", "diode": "D", "diode-LED": "LED", "transistor-BJT": "Q",
    "IC-NE555": "U",
}
ORDER = ["C20_D2_P2", "C29_D2_P4", "C84_D2_P1", "C92_D1_P3", "C138_D1_P3",
         "C109_D2_P3", "C15_D2_P2", "C22_D2_P3", "C21_D1_P3", "C28_D1_P3"]
FLAGS = {
    "C22_D2_P3_jpg": "Check R4: its bottom may actually wire to the R2+C8 group. If so, add R4 there.",
    "C21_D1_P3_jpg": "R7 is grouped with nothing (red box). A resistor wired to nothing is almost always a missed wire — trace its two ends.",
    "C28_D1_P3_jpg": "Densest one. C4, L55, L56 are grouped with nothing (red boxes). Check each.",
    "C109_D2_P3_jpg": "Fine to confirm quickly (diode in series; grouping is equivalent).",
    "C15_D2_P2_jpg": "Fine to confirm quickly (R3's top pin left loose but doesn't change anything).",
}


def load():
    return json.loads(GT.read_text())


def state():
    d = load()
    # order: to-do first (easy first), then verified, then excluded last
    def keyfn(k):
        v = d[k]
        ver = "human-verified" in v.get("source", "")
        exc = bool(v.get("excluded"))
        return (ver or exc, exc, len(v["electrical_idxs"]), k)
    keys = sorted(d.keys(), key=keyfn)
    out = []
    for k in keys:
        v = d[k]
        elec = set(v["electrical_idxs"])
        comps = {int(i): m for i, m in v["components"].items()}
        bb = META[k]["bboxes"]
        nets = []
        for net in v["nets"]:
            members = sorted({int(ci) for ci, _p in net if int(ci) in elec})
            if members:
                nets.append(members)
        out.append({
            "id": k, "name": k.replace("_jpg", ""),
            "source": v.get("source", ""),
            "verified": "human-verified" in v.get("source", ""),
            "excluded": bool(v.get("excluded")),
            "flag": FLAGS.get(k, ""),
            "components": [{"idx": i, "type": comps[i]["type"],
                           "label": TYPE_ABBR.get(comps[i]["type"], "?") + str(i),
                           "bbox": bb.get(str(i), [comps[i]["cx"] - .02, comps[i]["cy"] - .02,
                                                   comps[i]["cx"] + .02, comps[i]["cy"] + .02])}
                          for i in sorted(elec)],
            "nets": nets,
        })
    return {"images": out}


def save(img_id, nets, verified, excluded=False):
    d = load()
    if img_id not in d:
        return False
    entry = d[img_id]
    if "_nets_original" not in entry:
        entry["_nets_original"] = entry["nets"]
    clean = []
    for net in nets:
        members = sorted(set(int(i) for i in net))
        if members:
            clean.append([[i, "e"] for i in members])
    entry["nets"] = clean
    if excluded:
        entry["excluded"] = True
        entry["source"] = "excluded-bad-labels (UI)"
    else:
        entry.pop("excluded", None)
        if verified:
            entry["source"] = "human-verified (UI)"
    GT.write_text(json.dumps(d, indent=2))
    return True


HTML = r"""<!doctype html><html><head><meta charset=utf-8><title>Net-GT verify</title>
<style>
*{box-sizing:border-box} body{margin:0;font:14px system-ui;background:#181a1f;color:#e6e6e6;display:flex;height:100vh;overflow:hidden}
#list{width:160px;border-right:1px solid #2c2f36;overflow:auto;flex:none}
#list .it{padding:9px 11px;cursor:pointer;border-bottom:1px solid #24262c}
#list .it:hover{background:#23262e} #list .it.sel{background:#2d4a78}
#list .b{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:7px;vertical-align:middle}
.ok{background:#36d399} .no{background:#7a7f8a} .fl{background:#f59e42} .ex{background:#b04a4a}
#list .it.exc{opacity:.45}
#mid{flex:1;position:relative;overflow:hidden;background:#0d0e11}
#stage{position:absolute;transform-origin:0 0;left:0;top:0}
#stage img{display:block;-webkit-user-drag:none}
#cv{position:absolute;left:0;top:0;pointer-events:none}
#bar{position:absolute;top:10px;left:10px;z-index:5;background:#000c;padding:8px 10px;border-radius:8px;display:flex;gap:8px;align-items:center}
button{background:#2c2f37;color:#e6e6e6;border:1px solid #444a55;border-radius:5px;padding:5px 10px;cursor:pointer;font:13px system-ui}
button:hover{background:#3a3e48}
#side{width:340px;border-left:1px solid #2c2f36;overflow:auto;flex:none;padding:12px}
.head{font-size:17px;font-weight:600;margin-bottom:2px}
.flag{background:#4a2f12;border:1px solid #b8762a;padding:8px 10px;border-radius:6px;margin:8px 0;font-size:13px;line-height:1.45}
.help{background:#1d2733;border:1px solid #2f4a6b;padding:8px 10px;border-radius:6px;font-size:12.5px;color:#bcd;line-height:1.5;margin:8px 0}
.net{border:1px solid #3a3e48;border-radius:7px;padding:8px;margin-bottom:8px;background:#21242b}
.net.hot{border-color:#f5c451;background:#2e2a1c}
.net.done{border-color:#2c7a52;background:#19271f}
.net .t{font-size:12px;color:#9bb4d6;margin-bottom:5px;display:flex;align-items:center}
.sw{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:7px}
.ck{margin-left:auto;background:#2c2f37;border:1px solid #4a7d63;color:#9ec9b3;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer}
.ck.on{background:#1f7a4d;color:#fff;border-color:#36d399}
.kbd{color:#7a8595;font-size:11px;margin-top:6px}
.net.single .t{color:#f59e42}
.chip{display:inline-block;background:#3a3f4a;border-radius:12px;padding:3px 9px;margin:3px;cursor:pointer;font-weight:600}
.chip .x{color:#ff7676;margin-left:6px}
.chip.sel{outline:2px solid #4cc9ff}
.pal .chip.inuse{background:#1f5d3f} .pal .chip.iso{background:#7a2530}
.addbtn{background:#26553a;border-color:#36d399;color:#cfeede;font-size:12px;padding:3px 8px}
h4{margin:14px 0 6px;font-size:12px;letter-spacing:.04em;color:#8fa3c4;text-transform:uppercase}
.save{background:#1f7a4d;border-color:#36d399;font-weight:700;width:100%;padding:9px;margin-top:4px;font-size:14px}
.vrow{display:flex;align-items:center;gap:8px;margin:10px 0}
.vrow input{width:17px;height:17px}
small{color:#9aa0ab}
</style></head><body>
<div id=list></div>
<div id=mid>
  <div id=bar>
    <button id=grp>hide net lines</button>
    <button id=fit>reset view</button>
    <span id=zl style="color:#8fb"></span>
    <span style="color:#888">scroll=zoom · drag=pan · click box=select · ←/→ images · v=save+verify</span>
  </div>
  <div id=stage><img id=im><canvas id=cv></canvas></div>
</div>
<div id=side></div>
<script>
let S=null,cur=0,showLines=true,sel=null,hotNet=-1,view={x:0,y:0,s:1};
const im=document.getElementById('im'),cv=document.getElementById('cv'),stage=document.getElementById('stage'),ctx=cv.getContext('2d');
const PAL=['#4c9bff','#36d399','#f59e42','#e879f9','#fbbf24','#22d3ee','#fb7185','#a3e635','#c084fc','#2dd4bf','#f87171','#94a3b8'];
async function boot(){S=(await (await fetch('/api/state')).json()).images;drawList();load(0);}
function drawList(){
  const todo=S.filter(x=>!x.verified&&!x.excluded).length;
  document.getElementById('list').innerHTML=
   `<div style="padding:7px 10px;color:#9af;border-bottom:1px solid #2c2f36"><b>${todo}</b> to do · ${S.filter(x=>x.verified).length} done · ${S.filter(x=>x.excluded).length} excl</div>`+
   S.map((x,i)=>{
    let c=x.excluded?'ex':(x.verified?'ok':(x.flag?'fl':'no'));
    let tag=x.excluded?'· excluded':(x.verified?'· verified ✓':(x.flag?'· check':''));
    return `<div class="it ${i==cur?'sel':''} ${x.excluded?'exc':''}" onclick="load(${i})"><span class="b ${c}"></span>${x.name}<br><small>${x.components.length} parts ${tag}</small></div>`;}).join('');}
function D(){return S[cur];}
function load(i){cur=i;sel=null;hotNet=-1;drawList();im.src='/clean/'+D().name+'.png';
  im.onload=()=>{cv.width=im.naturalWidth;cv.height=im.naturalHeight;fit();redraw();};drawSide();}
document.getElementById('grp').onclick=()=>{showLines=!showLines;document.getElementById('grp').textContent=showLines?'hide net lines':'show net lines';redraw();};
document.getElementById('fit').onclick=fit;
function fit(){const m=document.getElementById('mid');const s=Math.min(m.clientWidth/im.naturalWidth,m.clientHeight/im.naturalHeight)*0.97||1;
  view={s,x:(m.clientWidth-im.naturalWidth*s)/2,y:(m.clientHeight-im.naturalHeight*s)/2};av();}
function av(){stage.style.transform=`translate(${view.x}px,${view.y}px) scale(${view.s})`;document.getElementById('zl').textContent=Math.round(view.s*100)+'%';}
let drag=null;const mid=document.getElementById('mid');
mid.addEventListener('mousedown',e=>{drag={x:e.clientX-view.x,y:e.clientY-view.y,sx:e.clientX,sy:e.clientY,moved:false};});
window.addEventListener('mousemove',e=>{if(drag){view.x=e.clientX-drag.x;view.y=e.clientY-drag.y;if(Math.abs(e.clientX-drag.sx)+Math.abs(e.clientY-drag.sy)>4)drag.moved=true;av();}});
window.addEventListener('mouseup',e=>{if(drag&&!drag.moved)clickImg(e);drag=null;});
mid.addEventListener('wheel',e=>{e.preventDefault();const r=mid.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const ix=(mx-view.x)/view.s,iy=(my-view.y)/view.s,f=e.deltaY<0?1.15:1/1.15;view.s*=f;view.x=mx-ix*view.s;view.y=my-iy*view.s;av();},{passive:false});
function clickImg(e){const r=im.getBoundingClientRect(),x=(e.clientX-r.left)/view.s/im.naturalWidth,y=(e.clientY-r.top)/view.s/im.naturalHeight;
  let hit=null;for(const c of D().components){const[a,b,cc,d]=c.bbox;if(x>=a-.01&&x<=cc+.01&&y>=b-.01&&y<=d+.01)hit=c.idx;}
  if(hit!=null){sel=(sel===hit?null:hit);drawSide();redraw();}}
function netOf(idx){const ns=[];D().nets.forEach((n,i)=>{if(n.length>=2&&n.includes(idx))ns.push(i);});return ns;}
function chk(){const d=D();if(!d._checked)d._checked=[];return d._checked;}
function isChecked(ni){return chk().includes(ni);}
function redraw(){const W=cv.width,H=cv.height;ctx.clearRect(0,0,W,H);const d=D();
  if(showLines) d.nets.forEach((net,ni)=>{if(net.length<2)return;
    const col=PAL[ni%PAL.length],done=isChecked(ni),hotn=ni==hotNet;
    const ms=net.map(i=>d.components.find(c=>c.idx==i)).filter(Boolean);
    ctx.globalAlpha=hotn?1:(done?0.92:0.28);ctx.strokeStyle=col;
    ctx.lineWidth=hotn?7:(done?5:3);ctx.setLineDash(done||hotn?[]:[12,9]);
    for(let a=0;a<ms.length;a++)for(let b=a+1;b<ms.length;b++){const p=ctr(ms[a]),q=ctr(ms[b]);ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke();}});
  ctx.globalAlpha=1;ctx.setLineDash([]);
  for(const c of d.components){const[x1,y1,x2,y2]=[c.bbox[0]*W,c.bbox[1]*H,c.bbox[2]*W,c.bbox[3]*H];
    const nets=netOf(c.idx),iso=nets.length==0,allDone=nets.length>0&&nets.every(isChecked);
    let col=iso?'#ff5b6e':(allDone?'#36d399':'#4cc9ff');
    if(hotNet>=0&&d.nets[hotNet]&&d.nets[hotNet].includes(c.idx))col='#f5c451';
    if(sel==c.idx)col='#ffffff';
    ctx.lineWidth=sel==c.idx?5:3;ctx.strokeStyle=col;ctx.strokeRect(x1,y1,x2-x1,y2-y1);
    ctx.font='bold 26px system-ui';const t=c.label,tw=ctx.measureText(t).width;
    const lx=x1,ly=y1-30>0?y1-30:y2+2;
    ctx.fillStyle='#000b';ctx.fillRect(lx,ly,tw+14,28);ctx.fillStyle=col;ctx.fillText(t,lx+7,ly+21);}
}
function ctr(c){return[(c.bbox[0]+c.bbox[2])/2*cv.width,(c.bbox[1]+c.bbox[3])/2*cv.height];}
function drawSide(){const d=D();const mn=d.nets.filter(n=>n.length>1).length;
  const done=chk().filter(i=>d.nets[i]&&d.nets[i].length>1).length;
  let h=`<div class=head>${d.name}</div><small>${d.components.length} parts · ${mn} groups · <b style="color:${mn&&done==mn?'#36d399':'#f5c451'}">${done}/${mn} reviewed</b></small>`;
  if(d.flag)h+=`<div class=flag>⚑ ${d.flag}</div>`;
  h+=`<div class=help><b>Per group:</b> hover it, confirm those parts really share a wire (and nothing's missing), then hit <b>✓</b> — its line turns solid. Red box = grouped with nothing. When all are solid, Save (or press <b>v</b>).</div>`;
  h+=`<div class=vrow><input type=checkbox id=ver ${d.verified?'checked':''}><label for=ver>mark <b>verified</b></label></div>`;
  h+=`<button class=save onclick=doSave()>SAVE &amp; next ▸</button>`;
  h+=`<button class=addbtn style="width:100%;margin-top:5px;border-color:#b04a4a;color:#f4b" onclick=doExclude()>✗ exclude (bad / unlabeled parts)</button>`;
  h+=`<h4>Groups (hover to highlight)</h4>`;
  d.nets.forEach((n,ni)=>{const single=n.length<2,dn=isChecked(ni),col=PAL[ni%PAL.length];
    h+=`<div class="net ${single?'single':''} ${ni==hotNet?'hot':''} ${dn?'done':''}" onmouseenter=hot(${ni}) onmouseleave=hot(-1)>`;
    h+=`<div class=t><span class=sw style="background:${single?'#666':col}"></span>${single?'⚠ only one part':'group '+(ni+1)}`;
    if(!single)h+=`<button class="ck ${dn?'on':''}" onclick="event.stopPropagation();toggleChk(${ni})">${dn?'✓ done':'mark ✓'}</button>`;
    h+=`</div>`;
    h+=n.map(i=>{const c=d.components.find(x=>x.idx==i);return `<span class="chip ${sel==i?'sel':''}" onclick="event.stopPropagation();pick(${i})">${c?c.label:i}<span class=x onclick="event.stopPropagation();rm(${ni},${i})">×</span></span>`;}).join('');
    h+=` <button class=addbtn onclick="event.stopPropagation();addSel(${ni})">+ add selected</button></div>`;});
  h+=`<button class=addbtn onclick=newNet()>+ new group with selected</button>`;
  h+=`<h4>All parts (click to select)</h4><div class=pal>`;
  h+=d.components.map(c=>{const iso=netOf(c.idx).length==0;return `<span class="chip ${iso?'iso':'inuse'} ${sel==c.idx?'sel':''}" onclick=pick(${c.idx})>${c.label} <small>${c.type}</small></span>`;}).join(' ');
  h+=`</div>`;
  document.getElementById('side').innerHTML=h;}
function hot(n){hotNet=n;redraw();document.querySelectorAll('.net').forEach((e,i)=>e.classList.toggle('hot',i==n));}
function pick(i){sel=(sel===i?null:i);drawSide();redraw();}
function toggleChk(ni){const c=chk(),k=c.indexOf(ni);if(k>=0)c.splice(k,1);else c.push(ni);drawSide();redraw();}
function addSel(ni){if(sel==null){alert('Click a part first (on the drawing or under "All parts").');return;}const n=D().nets[ni];if(!n.includes(sel))n.push(sel);D()._checked=[];drawSide();redraw();}
function rm(ni,i){const n=D().nets[ni];const k=n.indexOf(i);if(k>=0)n.splice(k,1);if(!n.length)D().nets.splice(ni,1);D()._checked=[];drawSide();redraw();}
function newNet(){if(sel==null){alert('Click a part first.');return;}D().nets.push([sel]);D()._checked=[];drawSide();redraw();}
async function doSave(){const d=D(),verified=document.getElementById('ver').checked;
  const r=await fetch('/api/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:d.id,nets:d.nets,verified})});
  if(!r.ok){alert('save failed');return;}
  d.verified=verified;drawList();
  if(verified){const nx=S.findIndex((x,i)=>i!=cur&&!x.verified&&!x.excluded);if(nx>=0){load(nx);return;}}
  drawSide();}
async function doExclude(){const d=D();if(!confirm('Exclude '+d.name+' from the benchmark (bad/unlabeled parts)?'))return;
  const r=await fetch('/api/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:d.id,nets:d.nets,excluded:true})});
  if(!r.ok){alert('failed');return;}
  d.excluded=true;d.verified=false;drawList();
  const nx=S.findIndex((x,i)=>i!=cur&&!x.verified&&!x.excluded);if(nx>=0)load(nx);else drawSide();}
window.addEventListener('keydown',e=>{if(e.target.tagName=='INPUT')return;
  if(e.key=='ArrowRight'&&cur<S.length-1)load(cur+1);
  else if(e.key=='ArrowLeft'&&cur>0)load(cur-1);
  else if(e.key=='v'){document.getElementById('ver').checked=true;doSave();}});
boot();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            return self._send(200, HTML.encode(), "text/html; charset=utf-8")
        if p == "/api/state":
            return self._send(200, json.dumps(state()).encode())
        if p.startswith("/clean/"):
            f = CLEAN / Path(p[len("/clean/"):]).name
            if f.exists():
                return self._send(200, f.read_bytes(), "image/png")
            return self._send(404, b"no img", "text/plain")
        self._send(404, b"404", "text/plain")

    def do_POST(self):
        if self.path == "/api/save":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n))
            ok = save(body["id"], body["nets"], body.get("verified", False), body.get("excluded", False))
            return self._send(200 if ok else 400, json.dumps({"ok": ok}).encode())
        self._send(404, b"404", "text/plain")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Net-GT verify UI -> http://127.0.0.1:{port}/   (editing {GT})")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
