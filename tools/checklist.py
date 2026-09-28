#!/usr/bin/env python3
"""
checklist.py　把一个企划的主要内容做成现场用的核对表（单文件 HTML，手机打开即可勾选）。

  python tools/checklist.py --plan plans/<plan> [--images out/<plan>] [--no-thumbs] [--fragment out.html]

读：shotlist.json（必需）、route.json、trip.json、sun.json、outfit.json、plan.json、arrival_checklist.md（有就用）。
出：plans/<plan>/<出行日期>_<地点>_拍摄核对表[_vN].html

内容顺序：出发前准备（器材按分镜介质自动列、服装道具妆发）→ 行程 → 到场核对 → 分镜（按路线停留点分组，
每条可勾选，带缩略图与展开细节）→ 收尾。勾选状态存在浏览器本地（localStorage，按企划名区分），
不联网、不上传；换设备或清浏览器数据会丢。出行当天打开时，按当前时刻标出「进行中」的停留点。
--fragment 另存一份不带 <html>/<head>/<body> 外壳的版本，给需要自己套外壳的托管页面用。
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIUM = {"still": "静态", "burst": "连拍", "video": "短片", "live": "实况"}
CLIP = {"24p": "24p 实时", "sq60": "S&Q 60→24", "sq120": "S&Q 120→24"}
KIND_ORDER = ["still", "burst", "video", "live"]


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def out_name(meta: dict) -> str:
    place = re.split(r"[（(]", meta.get("place", "plan"))[0].strip()
    place = re.sub(r'[\\/:*?"<>|\s]+', "", place) or "plan"
    date = meta.get("date", "").strip() or "undated"
    m = re.search(r"\bv(\d+)", meta.get("version", ""))
    ver = f"_v{m.group(1)}" if m and int(m.group(1)) >= 2 else ""
    return f"{date}_{place}_拍摄核对表{ver}.html"


def thumb(images: Path, sid: str, width=220) -> str | None:
    cands = sorted(images.glob(f"{sid}*.png")) + sorted(images.glob(f"{sid}*.jpg"))
    if not cands:
        return None
    try:
        from PIL import Image
        im = Image.open(cands[0]).convert("RGB")
        im.thumbnail((width, width * 2))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=68, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def move_img(p: Path, width=900) -> str | None:
    if not p.exists():
        return None
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
        im.thumbnail((width, width))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def md_list(p: Path) -> list[str]:
    """arrival_checklist.md 第一个二级标题之前的编号 / 列表项。"""
    if not p.exists():
        return []
    items = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            break
        m = re.match(r"\s*(?:\d+[.、]|[-*])\s+(.*)", ln)
        if m:
            items.append(m.group(1).strip())
    return items


def md_section(p: Path, head: str) -> list[str]:
    if not p.exists():
        return []
    out, on = [], False
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            on = head in ln
            continue
        if on:
            m = re.match(r"\s*[-*]\s+(.*)", ln)
            if m:
                out.append(m.group(1).strip())
    return out


def gear_items(plan: dict, shots: list[dict], meta: dict) -> list[tuple[str, str]]:
    media = {s.get("medium", "still") for s in shots}
    lenses = sorted({s.get("lens", "").split()[0] for s in shots if s.get("lens") and s.get("medium", "still") != "live"},
                    key=lambda x: int(re.sub(r"\D", "", x) or 0))
    look = next((s.get("look") for s in shots if s.get("look")), "")
    rain = "雨" in (meta.get("forecast") or "") or "雨" in json.dumps(meta.get("weather", ""), ensure_ascii=False)
    items = []
    body = plan.get("body") or ""
    items.append((f"{body} {plan.get('gear', '')}".strip() or "机身与镜头", "用到的焦段：" + "、".join(lenses) if lenses else ""))
    items.append(("电池 2 块以上、存储卡清空", "短片与连拍耗电和卡容量都比静态多" if media & {"video", "burst"} else ""))
    if look:
        items.append((f"外观与白平衡：{look}", "全组固定，现场不改"))
    fl = [s.get("flash", "") for s in shots if s.get("flash") and s.get("flash") != "关"]
    if plan.get("flash") and fl:
        items.append((f"{plan['flash']}（柔光罩、电池）", f"{len(fl)} 张用闪光"))
    if "burst" in media:
        items.append(("连拍：电子快门 30 张/秒，预拍 0.5 秒，AF-C 人物识别", "快门 1/500 以上"))
    if "video" in media:
        items.append(("短片：動画位 S-Log3 24p、S&Q 60→24 / 120→24 两个预设", "斑马 52% / 95%，180° 快门，WB 固定 K 值，竖幅"))
        nds = sorted({s["clip"].get("nd", "") for s in shots if s.get("clip", {}).get("nd")})
        items.append(("可变 ND（77 mm）", "；".join(nds[:2]) if nds else ""))
    if "live" in media:
        items.append(("iPhone：实况开、网格开、电量满", "长按锁 AE/AF 在脸上"))
    if rain:
        items.append(("机身防雨罩、镜头布两块", "每条短片前擦一次前镜"))
    return items


def outfit_items(o: dict) -> list[tuple[str, str]]:
    if not o:
        return []
    items = []
    for k, lab in (("top", "上衣"), ("layer", "外层"), ("bottom", "下装"), ("shoes", "鞋"), ("accessories", "配饰"), ("bag", "包")):
        v = (o.get("main") or {}).get(k)
        if v:
            head, _, rest = v.partition("，")
            items.append((f"{lab}：{head}", rest))
    for p in o.get("props", []):
        items.append((f"道具：{p}", ""))
    if o.get("hair_makeup"):
        items.append(("妆发", o["hair_makeup"]))
    return items


def shot_detail(s: dict) -> list[tuple[str, str]]:
    rows = [("机位", s.get("camera")), ("人物", s.get("subject")), ("光线", s.get("light")),
            ("前景 / 背景", s.get("fg_bg")), ("备选", s.get("alt")), ("注意", s.get("note"))]
    m = s.get("medium", "still")
    if m == "video" and s.get("clip"):
        c = s["clip"]
        rows.insert(0, ("短片", f"{CLIP.get(c.get('mode'), c.get('mode', ''))} · {c.get('move', '')} · 实录 {c.get('dur_s', '?')} 秒"))
        rows.insert(1, ("起止", f"{c.get('start', '')} → {c.get('end', '')}"))
        rows.insert(2, ("曝光", f"{c.get('exposure', '')}；ND {c.get('nd', '')}"))
    elif m == "burst" and s.get("burst"):
        b = s["burst"]
        rows.insert(0, ("连拍", f"{b.get('fps', 30)} 张/秒，预拍 {b.get('precap_s', 0.5)} 秒；{b.get('action', '')}"))
    elif m == "live" and s.get("live"):
        lv = s["live"]
        rows.insert(0, ("实况", f"{lv.get('device', 'iPhone')} {lv.get('lens', '')}；{lv.get('exposure', '')}；{lv.get('action', '')}"))
    else:
        rows.insert(0, ("曝光", s.get("shutter")))
    return [(k, v) for k, v in rows if v]


CSS = r"""
:root{
  --paper:#f5f2ea; --surface:#fffdf8; --ink:#26302a; --muted:#6d716a; --line:#dcd6c8;
  --green:#2e523a; --green-soft:#e4ece4; --on-green:#ffffff;
  --burst:#a85a22; --video:#3f5f93; --live:#6d716a; --hero:#8a3b30;
  --done-bg:#eef1ea; --warn:#a85a22; --focus:#3f5f93;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#141915; --surface:#1c231e; --ink:#e3e6df; --muted:#9aa196; --line:#343d36;
    --green:#8fbf9c; --green-soft:#223128; --on-green:#10170f;
    --burst:#e09a63; --video:#8fb0e6; --live:#a7ada3; --hero:#e38f82;
    --done-bg:#1a211c; --warn:#e09a63; --focus:#8fb0e6;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --paper:#141915; --surface:#1c231e; --ink:#e3e6df; --muted:#9aa196; --line:#343d36;
  --green:#8fbf9c; --green-soft:#223128; --on-green:#10170f;
  --burst:#e09a63; --video:#8fb0e6; --live:#a7ada3; --hero:#e38f82;
  --done-bg:#1a211c; --warn:#e09a63; --focus:#8fb0e6;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.55 "Hiragino Sans","PingFang SC","Noto Sans CJK SC","Noto Sans SC","Microsoft YaHei",system-ui,sans-serif;
  -webkit-text-size-adjust:100%}
.wrap{max-width:760px;margin:0 auto;padding-inline:16px;padding-block:20px 64px}
h1{font-size:22px;margin:0;color:var(--green);letter-spacing:.02em;text-wrap:balance}
.sub{color:var(--muted);font-size:13px;margin-top:2px}
.num{font-variant-numeric:tabular-nums}
.summary{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;align-items:center;margin:16px 0 8px}
.big{font-size:30px;font-weight:700;color:var(--green)}
.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--green);transition:width .25s}
.counts{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--muted)}
.counts b{color:var(--ink);font-weight:600}
.wx{margin:12px 0 4px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);font-size:13px}
.wx p{margin:0 0 6px}
.wxt{overflow-x:auto}
.wxt table{border-collapse:collapse;font-size:12px;min-width:100%}
.wxt td,.wxt th{padding:2px 8px;text-align:center;white-space:nowrap}
.wxt th{color:var(--muted);font-weight:500;text-align:left}
.wxt .heavy{color:var(--warn);font-weight:700}
.tools{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--paper);
  display:flex;flex-wrap:wrap;gap:6px;padding:10px 0;border-bottom:1px solid var(--line);margin-bottom:6px}
.tools button{font:inherit;font-size:13px;padding:5px 11px;border-radius:15px;border:1px solid var(--line);
  background:var(--surface);color:var(--ink);cursor:pointer}
.tools button[aria-pressed="true"]{background:var(--green);border-color:var(--green);color:var(--on-green)}
.tools .sep{flex:1}
.tools .danger{color:var(--hero)}
button:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
section{margin-top:22px}
h2{font-size:16px;margin:0 0 6px;display:flex;gap:10px;align-items:baseline}
h2 .prog{font-size:12px;color:var(--muted);font-weight:400;margin-left:auto}
.stop{margin-top:16px;border-top:1px solid var(--line);padding-top:10px}
.stop h3{font-size:15px;margin:0;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}
.stop h3 .seq{color:var(--green);font-variant-numeric:tabular-nums}
.stop h3 .t{font-size:13px;color:var(--muted);font-weight:400}
.stop h3 .prog{margin-left:auto;font-size:12px;color:var(--muted);font-weight:400}
.stop .note{font-size:12.5px;color:var(--muted);margin:2px 0 4px}
.stop.now{border-top:2px solid var(--green)}
.stop.now h3::after{content:"进行中";font-size:11px;color:var(--on-green);background:var(--green);padding:1px 7px;border-radius:9px}
ul.items{list-style:none;margin:0;padding:0}
.it{display:grid;grid-template-columns:28px 1fr;gap:4px 8px;padding:8px 6px;border-radius:8px;align-items:start}
.it+.it{border-top:1px dashed var(--line)}
.it input{width:22px;height:22px;margin:1px 0 0;accent-color:var(--green)}
.it .h{font-weight:500}
.shot .h{font-weight:650}
.stop,section{scroll-margin-top:110px}
.it .d{font-size:13px;color:var(--muted)}
.it.done{background:var(--done-bg)}
.it.done .h{text-decoration:line-through;text-decoration-color:var(--muted);color:var(--muted)}
.shot{grid-template-columns:28px 76px 1fr}
.shot img,.shot .ph{width:76px;aspect-ratio:3/4;object-fit:cover;border-radius:5px;background:var(--line);display:block;max-width:100%}
.shot .ph{display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--muted)}
.shot .h .id{color:var(--green);font-variant-numeric:tabular-nums;margin-right:4px}
.chips{display:inline-flex;flex-wrap:wrap;gap:4px;margin-left:4px;vertical-align:1px}
.chip{font-size:11px;font-weight:600;padding:0 6px;border-radius:9px;border:1px solid currentColor;line-height:17px}
.c-hero{color:var(--hero)} .c-burst{color:var(--burst)} .c-video{color:var(--video)} .c-live{color:var(--live)} .c-opt{color:var(--muted)}
.say{font-size:13.5px;margin-top:2px}
details{margin-top:4px;font-size:13px}
details summary{cursor:pointer;color:var(--green);width:max-content}
details.mv{grid-column:1/-1;margin-top:2px}
details.refs{margin:2px 0 6px;font-size:13px}
details.refs summary{cursor:pointer;color:var(--green)}
details.refs ul{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:8px}
details.refs li{border-left:3px solid var(--line);padding-left:8px}
details.refs a{color:var(--green);font-weight:600}
details.refs .use{margin-top:2px}
.pose{font-size:13px;margin-top:3px}
.pose a{color:var(--green);font-weight:600;text-decoration:none;border-bottom:1px dotted var(--green);margin-right:6px}
.poses{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.poses li{background:var(--panel,#fff);border:1px solid var(--line);border-radius:8px;padding:6px;font-size:12.5px;line-height:1.45}
.poses img{display:block;width:100%;height:auto;border-radius:6px;margin-bottom:4px}
.poses b{color:var(--green)}
details.refs .snsimg{display:block;width:100%;max-width:260px;height:auto;border-radius:6px;margin:2px 0 6px;border:1px solid var(--line)}
.chip.lv-hi{color:var(--green)} .chip.lv-mid{color:var(--burst)} .chip.lv-lo{color:var(--muted)}
img.overview{display:block;width:100%;max-width:560px;height:auto;margin:8px 0;border-radius:6px;border:1px solid var(--line)}
details.ov summary{cursor:pointer;color:var(--green)}
details.ov .d{font-size:12.5px;color:var(--muted);margin:4px 0 0}
.shot img.move{display:block;width:100%;max-width:480px;height:auto;aspect-ratio:auto;object-fit:contain;margin:8px 0 4px;border-radius:6px;border:1px solid var(--line);background:#fffdf8}
dl{display:grid;grid-template-columns:max-content 1fr;gap:3px 10px;margin:6px 0 0}
dt{color:var(--muted)} dd{margin:0}
.confirm{display:flex;gap:6px;align-items:center;font-size:13px}
.foot{margin-top:28px;font-size:12px;color:var(--muted)}
.hide{display:none!important}
@media (max-width:420px){ .shot{grid-template-columns:26px 60px 1fr} .shot img,.shot .ph{width:60px} .big{font-size:26px} }
@media (prefers-reduced-motion:reduce){ .bar i{transition:none} }
"""

JS = r"""
(function(){
  var KEY = document.body.getAttribute('data-key');
  var state = {};
  try { state = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch(e) { state = {}; }
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch(e) {} }
  var boxes = Array.prototype.slice.call(document.querySelectorAll('input[type=checkbox][data-id]'));
  function mark(b){ var li = b.closest('.it'); if (li) li.classList.toggle('done', b.checked); }
  boxes.forEach(function(b){ b.checked = !!state[b.dataset.id]; mark(b);
    b.addEventListener('change', function(){ if (b.checked) state[b.dataset.id] = Date.now(); else delete state[b.dataset.id];
      save(); mark(b); refresh(); }); });
  function cnt(sel){ var a = document.querySelectorAll(sel), n = 0; for (var i=0;i<a.length;i++) if (a[i].checked) n++; return [n, a.length]; }
  function refresh(){
    var s = cnt('.shot input'); document.getElementById('done-n').textContent = s[0];
    document.getElementById('done-bar').style.width = (s[1] ? 100*s[0]/s[1] : 0) + '%';
    ['still','burst','video','live'].forEach(function(m){ var el = document.getElementById('cnt-'+m); if (!el) return;
      var c = cnt('.shot[data-medium="'+m+'"] input'); el.textContent = c[0] + ' / ' + c[1]; });
    document.querySelectorAll('[data-prog]').forEach(function(el){
      var c = cnt(el.getAttribute('data-prog')); el.textContent = c[0] + ' / ' + c[1]; });
    applyFilter();
  }
  var filter = 'all';
  function applyFilter(){
    document.querySelectorAll('.shot').forEach(function(li){
      var m = li.getAttribute('data-medium'), done = li.querySelector('input').checked, show = true;
      if (filter === 'todo') show = !done; else if (filter !== 'all') show = (m === filter);
      li.classList.toggle('hide', !show); });
    document.querySelectorAll('.stop').forEach(function(st){
      st.classList.toggle('hide', !st.querySelector('.shot:not(.hide)')); });
    document.querySelectorAll('.side').forEach(function(sec){ sec.classList.toggle('hide', filter !== 'all' && filter !== 'todo'); });
  }
  document.querySelectorAll('[data-filter]').forEach(function(btn){
    btn.addEventListener('click', function(){ filter = btn.getAttribute('data-filter');
      document.querySelectorAll('[data-filter]').forEach(function(x){ x.setAttribute('aria-pressed', x === btn ? 'true' : 'false'); });
      applyFilter(); }); });
  var open = false, tog = document.getElementById('toggle-details');
  tog.addEventListener('click', function(){ open = !open;
    document.querySelectorAll('.shot details').forEach(function(d){ d.open = open; });
    tog.textContent = open ? '收起细节' : '展开细节'; });
  var clr = document.getElementById('clear'), cf = document.getElementById('confirm');
  clr.addEventListener('click', function(){ cf.classList.remove('hide'); clr.classList.add('hide'); });
  document.getElementById('confirm-no').addEventListener('click', function(){ cf.classList.add('hide'); clr.classList.remove('hide'); });
  document.getElementById('confirm-yes').addEventListener('click', function(){ state = {}; save();
    boxes.forEach(function(b){ b.checked = false; mark(b); }); cf.classList.add('hide'); clr.classList.remove('hide'); refresh(); });
  // 出行当天：按当前时刻标出进行中的停留点
  var day = document.body.getAttribute('data-date'), now = new Date();
  var today = now.getFullYear() + '-' + ('0'+(now.getMonth()+1)).slice(-2) + '-' + ('0'+now.getDate()).slice(-2);
  if (day === today) { var mins = now.getHours()*60 + now.getMinutes();
    document.querySelectorAll('.stop[data-from]').forEach(function(st){
      var a = st.getAttribute('data-from').split(':'), b = st.getAttribute('data-to').split(':');
      var f = +a[0]*60 + +a[1], t = +b[0]*60 + +b[1];
      if (mins >= f && mins < t) st.classList.add('now'); }); }
  refresh();
})();
"""


def item(cid: str, head: str, desc: str = "") -> str:
    return (f'<li class="it"><input type="checkbox" id="{esc(cid)}" data-id="{esc(cid)}">'
            f'<label for="{esc(cid)}"><div class="h">{esc(head)}</div>'
            + (f'<div class="d">{esc(desc)}</div>' if desc else "") + "</label></li>")


def build(plan_dir: Path, images: Path, thumbs=True, public=False) -> tuple[str, str, str]:
    SL = load(plan_dir / "shotlist.json")
    meta, shots = SL["meta"], SL["shots"]
    byid = {s["id"]: s for s in shots}
    P = load(plan_dir / "plan.json", {}) or {}
    R = load(plan_dir / "route.json")
    T = load(plan_dir / "trip.json")
    S = load(plan_dir / "sun.json", {}) or {}
    O = load(plan_dir / "outfit.json")
    PR = load(plan_dir / "pose_refs.json", {}) or {}
    PPOST = {x["id"]: x for x in PR.get("posts", [])}
    PBY = {}
    for pz in PR.get("poses", []):
        for sid in pz.get("shots", []):
            PBY.setdefault(sid, []).append(pz)

    def pose_img(pid):
        if not thumbs:
            return None
        if not public:
            src = thumb(plan_dir / "sns_private", pid, width=300)
            if src:
                return src
        return thumb(plan_dir / "poses", pid, width=300)

    place = re.split(r"[（(]", meta.get("place", P.get("place", "")))[0].strip()
    date = meta.get("date", P.get("date", ""))
    key = f"xiezhen-check:{plan_dir.name}"

    # 分组：有路线按停留点，没有按介质
    groups = []
    if R and R.get("stops"):
        seen = set()
        for st in R["stops"]:
            ids = [i for i in st.get("shots", []) if i in byid]
            seen.update(ids)
            groups.append({"name": st["name"], "from": st.get("arrive"), "to": st.get("leave"),
                           "walk": st.get("walk_m"), "note": st.get("note", ""), "ids": ids})
        rest = [s["id"] for s in shots if s["id"] not in seen]
        if rest:
            groups.append({"name": "未排进路线", "ids": rest, "note": "备选或园外分镜"})
    else:
        for m in KIND_ORDER:
            ids = [s["id"] for s in shots if s.get("medium", "still") == m]
            if ids:
                groups.append({"name": MEDIUM[m], "ids": ids})

    def shot_li(s):
        m = s.get("medium", "still")
        chips = []
        if s.get("hero"):
            chips.append('<span class="chip c-hero">主图</span>')
        if m == "video":
            chips.append(f'<span class="chip c-video">短片 {esc(CLIP.get(s.get("clip", {}).get("mode"), ""))}</span>')
        elif m != "still":
            chips.append(f'<span class="chip c-{m}">{MEDIUM[m]}</span>')
        if s.get("optional"):
            chips.append('<span class="chip c-opt">备选</span>')
        src = thumb(images, s["id"]) if thumbs else None
        pic = (f'<img src="{src}" alt="{esc(s["id"])} 示意图" loading="lazy">' if src else '<div class="ph">待生成</div>')
        line = " · ".join(x for x in [s.get("lens"), s.get("kind"),
                                      {"camera": "看镜头", "away": "看别处", "down": "低头", "closed": "闭眼", "back": "背影"}.get(s.get("gaze"), "")] if x)
        dl = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in shot_detail(s))
        mv = ""
        if m == "video" and thumbs:
            src_mv = move_img(plan_dir / "cards" / f"movem_{s['id']}.png", width=720)
            if src_mv:
                mv = (f'<details class="mv"><summary>运镜示意（俯视轨迹 + 起中止三帧）</summary>'
                      f'<img class="move" src="{src_mv}" alt="{esc(s["id"])} 运镜示意：俯视轨迹、起中止三帧与时间条" loading="lazy"></details>')
        cid = f"shot-{s['id']}"
        return (f'<li class="it shot" data-medium="{m}"><input type="checkbox" id="{cid}" data-id="{cid}">'
                f'<label for="{cid}">{pic}</label><div>'
                f'<label for="{cid}" class="h"><span class="id">{esc(s["id"])}</span>{esc(s.get("title", ""))}</label>'
                f'<span class="chips">{"".join(chips)}</span>'
                f'<div class="d">{esc(line)}</div>'
                + (f'<div class="say">{esc(s.get("action"))}</div>' if s.get("action") else "")
                + (('<div class="pose">参考姿势：' + "".join(
                    f'<a href="{esc(PPOST.get(pz["src"], {}).get("url", "#"))}" target="_blank" rel="noopener">{esc(pz["id"])} {esc(pz["name"])}</a>'
                    for pz in PBY.get(s["id"], [])) + '</div>') if PBY.get(s["id"]) else "")
                + f'<details><summary>细节</summary><dl>{dl}</dl></details></div>{mv}</li>')

    ver = re.search(r"v\d+(?:\.\d+)?", meta.get("version", ""))
    H = []
    H.append(f'<div class="wrap"><header><h1>{esc(place)} 拍摄核对表</h1>'
             f'<div class="sub num">{esc(date)}{" · " + esc(ver.group(0)) if ver else ""} · {len(shots)} 条分镜'
             + (f' · 路线 {len(R["stops"])} 站，步行约 {R.get("total_walk_m", "?")} m' if R else "") + "</div></header>")
    counts = []
    for m in KIND_ORDER:
        n = sum(1 for s in shots if s.get("medium", "still") == m)
        if n:
            counts.append(f'<span>{MEDIUM[m]} <b id="cnt-{m}" class="num">0 / {n}</b></span>')
    H.append(f'<div class="summary"><div class="big num"><span id="done-n">0</span> / {len(shots)}</div>'
             f'<div class="bar" aria-hidden="true"><i id="done-bar"></i></div><div class="counts">{"".join(counts)}</div></div>')

    # 天气
    W = S.get("weather") or {}
    wsum = (T or {}).get("weather", {}).get("summary") or meta.get("forecast")
    if wsum or W.get("rows"):
        H.append('<div class="wx">')
        if wsum:
            H.append(f"<p>{esc(wsum)}</p>")
        rows = W.get("rows") or []
        if rows and R:
            h0, h1 = int(R["start"][:2]), int(R["end"][:2])
            rows = [r for r in rows if h0 <= int(r["time"][:2]) <= h1]
        if rows:
            def cell(r, k):
                v = r.get(k)
                if v is None:
                    return "—"
                if k == "temp":
                    return f"{v:.0f}"
                return f"{v:.1f}" if isinstance(v, float) else str(v)
            H.append('<div class="wxt"><table><tr><th>时刻</th>' + "".join(f'<td class="num">{esc(r["time"])}</td>' for r in rows) + "</tr>")
            H.append("<tr><th>天气</th>" + "".join(
                f'<td class="{"heavy" if (r.get("precip_mm") or 0) >= 3 else ""}">{esc(r["wmo"])}</td>' for r in rows) + "</tr>")
            H.append("<tr><th>降水 mm</th>" + "".join(f'<td class="num">{cell(r, "precip_mm")}</td>' for r in rows) + "</tr>")
            H.append("<tr><th>气温 °C</th>" + "".join(f'<td class="num">{cell(r, "temp")}</td>' for r in rows) + "</tr>")
            H.append("<tr><th>风 m/s</th>" + "".join(f'<td class="num">{cell(r, "wind_ms")}</td>' for r in rows) + "</tr></table></div>")
        H.append("</div>")

    H.append('<nav class="tools" aria-label="筛选">'
             '<button data-filter="all" aria-pressed="true">全部</button><button data-filter="todo" aria-pressed="false">未完成</button>'
             + "".join(f'<button data-filter="{m}" aria-pressed="false">{MEDIUM[m]}</button>'
                       for m in KIND_ORDER if any(s.get("medium", "still") == m for s in shots))
             + '<span class="sep"></span><button id="toggle-details">展开细节</button>'
             '<button id="clear" class="danger">清空勾选</button>'
             '<span id="confirm" class="confirm hide">清空全部勾选？<button id="confirm-yes" class="danger">清空</button>'
             '<button id="confirm-no">取消</button></span></nav>')

    # 出发前
    prep = gear_items(P, shots, meta)
    if prep:
        H.append('<section class="side"><h2>出发前 · 器材<span class="prog num" data-prog="#sec-gear input"></span></h2><ul class="items" id="sec-gear">'
                 + "".join(item(f"gear-{i}", h, d) for i, (h, d) in enumerate(prep)) + "</ul></section>")
    oi = outfit_items(O)
    if oi:
        H.append(f'<section class="side"><h2>出发前 · 服装与道具<span class="prog num" data-prog="#sec-outfit input"></span></h2>'
                 + (f'<div class="d" style="margin-bottom:4px;color:var(--muted);font-size:13px">{esc(O.get("title", ""))}</div>' if O.get("title") else "")
                 + '<ul class="items" id="sec-outfit">' + "".join(item(f"outfit-{i}", h, d) for i, (h, d) in enumerate(oi)) + "</ul></section>")

    # 行程
    if T and T.get("stops"):
        stops, legs = T["stops"], T.get("legs", [])
        li = []
        for i, st in enumerate(stops):
            tt = " → ".join(x for x in [st.get("arrive"), st.get("leave")] if x)
            li.append(item(f"trip-s{i}", f"{tt}　{st['name']}" + ("（备选）" if st.get("optional") else ""), st.get("note", "")))
            for j, lg in enumerate(legs):
                if lg["from"] == i:
                    opt = "（备选）" if stops[lg["to"]].get("optional") or st.get("optional") else ""
                    li.append(item(f"trip-l{j}", f"{lg.get('depart', '')} 发　{lg.get('line', '')}{opt}",
                                   f"到 {stops[lg['to']]['name']} {lg.get('arrive', '')}，{lg.get('minutes', '?')} 分钟" + (f"；{lg['note']}" if lg.get("note") else "")))
        H.append('<section class="side"><h2>行程<span class="prog num" data-prog="#sec-trip input"></span></h2><ul class="items" id="sec-trip">'
                 + "".join(li) + "</ul></section>")

    # 到场核对
    arr = md_list(plan_dir / "arrival_checklist.md")
    if arr:
        H.append('<section class="side"><h2>到场核对<span class="prog num" data-prog="#sec-arr input"></span></h2><ul class="items" id="sec-arr">'
                 + "".join(item(f"arr-{i}", a) for i, a in enumerate(arr)) + "</ul></section>")

    # 短片一览
    ov = move_img(plan_dir / "cards" / "moves_overview_m.png", width=780)
    if ov:
        n_v = sum(1 for s in shots if s.get("medium") == "video")
        H.append(f'<section class="side"><h2>短片运镜一览</h2>'
                 f'<details class="ov"><summary>展开 {n_v} 条短片的轨迹与起中止三帧</summary>'
                 f'<img class="overview" src="{ov}" alt="本组短片的运镜轨迹与画面变化一览" loading="lazy">'
                 '<p class="d">橙线为相机轨迹（圆点为每秒位置），绿线为人物移动；三帧为起 / 中 / 止的竖幅画面。每条的完整说明在下面对应短片的「运镜示意」里。</p>'
                 '</details></section>')

    # SNS 参考机位（按停留点挂到分镜分组里）
    SR = load(plan_dir / "sns_refs.json", {}) or {}
    refs_by_stop = {}
    for r in SR.get("refs", []):
        refs_by_stop.setdefault(r.get("stop", ""), []).append(r)
    DIRS = ["北", "北北东", "东北", "东北东", "东", "东南东", "东南", "南南东", "南", "南南西", "西南", "西南西", "西", "西北西", "西北", "北北西"]

    def use_html(r):
        ub = r.get("use_by_shot") or {}
        if not ub:
            return f'<div class="use">本组：{esc(r["use"])}</div>'
        return "".join(f'<div class="use">本组{"" if sid in t else " " + esc(sid)}：{esc(t)}</div>' for sid, t in ub.items())

    def refs_html(stop):
        rs = refs_by_stop.get(stop, [])
        if not rs:
            return ""
        li = []
        for r in rs:
            lv = r["reproducible"]["level"]
            dr = DIRS[int((r["cam_bearing"] % 360) / 22.5 + 0.5) % 16]
            src = None if (public or not thumbs) else thumb(plan_dir / "sns_private", r["id"], width=360)
            if not src and thumbs:                      # 没有原帖截图时用按文字重画的构图线稿（原创，公开版也放）
                src = thumb(plan_dir / "sns_sketch", r["id"], width=360)
            pic = f'<img class="snsimg" src="{src}" alt="{esc(r["id"])} 原帖截图（仅个人参考）" loading="lazy">' if src else ""
            li.append(f'<li>{pic}<a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["id"])} {esc(r["title"])}</a>'
                      f' <span class="chip lv-{ {"高": "hi", "中": "mid", "低": "lo"}.get(lv, "lo") }">可复现 {esc(lv)}</span>'
                      f'<div class="d">{esc(r["platform"])} · {esc(r["posted"])} · 相机在人物{dr}侧 {r["cam_dist"]:g} m · {esc(r["lens_est"])} · {esc(r["kind"])}'
                      + ("（位置推测）" if r.get("location_confidence") == "低" else "") + '</div>'
                      + use_html(r) + '</li>')
        return (f'<details class="refs"><summary>SNS 参考机位（{len(rs)}）</summary><ul>{"".join(li)}</ul>'
                '<p class="d">点标题在新页面打开原帖；机位为按照片推算，现场以实际为准。</p></details>')

    # 姿势参考（小红书）
    if PR.get("poses"):
        li = []
        for pz in PR["poses"]:
            src = pose_img(pz["id"])
            post = PPOST.get(pz.get("src"), {})
            li.append(f'<li>' + (f'<img src="{src}" alt="{esc(pz["id"])} {esc(pz["name"])} 姿势示意" loading="lazy">' if src else "")
                      + f'<b>{esc(pz["id"])} {esc(pz["name"])}</b>　用于 {esc(" · ".join(pz.get("shots", [])))}<br>{esc(pz["how"])}<br>'
                      + f'<a href="{esc(post.get("url", "#"))}" target="_blank" rel="noopener">{esc(post.get("title", pz.get("src", "")))}</a></li>')
        tips = "".join(f'<p class="d">{esc(t["text"])}</p>' for t in PR.get("tips", []))
        H.append('<section><h2>姿势参考（小红书）</h2><details><summary>'
                 f'{len(PR["poses"])} 个姿势，点开看线稿与要领；原帖点链接</summary><ul class="poses">{"".join(li)}</ul>{tips}</details></section>')

    # 分镜
    H.append(f'<section><h2>分镜{"（按游览路线）" if R else ""}</h2>')
    for gi, g in enumerate(groups):
        attrs = f' data-from="{esc(g["from"])}" data-to="{esc(g["to"])}"' if g.get("from") and g.get("to") else ""
        tt = f'{g["from"]}–{g["to"]}' if g.get("from") else ""
        walk = f' · 步行 {g["walk"]} m' if g.get("walk") else ""
        H.append(f'<div class="stop"{attrs}><h3><span class="seq">{gi + 1:02d}</span>{esc(g["name"])}'
                 f'<span class="t num">{esc(tt)}{esc(walk)}</span><span class="prog num" data-prog="#g{gi} input"></span></h3>'
                 + (f'<div class="note">{esc(g["note"])}</div>' if g.get("note") else "")
                 + refs_html(g["name"])
                 + f'<ul class="items" id="g{gi}">' + "".join(shot_li(byid[i]) for i in g["ids"]) + "</ul></div>")
    H.append("</section>")

    # 收尾
    end = ["数一遍勾选：主图与短片是否都有，漏拍的在离场前补", "存储卡与电池收好，湿的伞与防雨罩单独装袋"]
    if T and T.get("stops") and T["stops"][-1].get("note"):
        end.append(f"回程：{T['stops'][-1]['note']}")
    H.append('<section class="side"><h2>收尾<span class="prog num" data-prog="#sec-end input"></span></h2><ul class="items" id="sec-end">'
             + "".join(item(f"end-{i}", e) for i, e in enumerate(end)) + "</ul></section>")
    H.append(f'<p class="foot">由 xiezhen-shoot-pipeline 生成（{dt.datetime.now():%Y-%m-%d %H:%M}）。勾选只保存在这台设备的浏览器里。'
             "示意图为 AI 拍摄示意，非现场实拍。</p></div>")

    title = f"{place} 拍摄核对表"
    body = "\n".join(H)
    return title, body, key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--images")
    ap.add_argument("--no-thumbs", action="store_true")
    ap.add_argument("--fragment", help="另存一份无外壳版本到此路径")
    ap.add_argument("--public", action="store_true", help="公开版：不嵌 sns_private 原帖截图（发布页、examples 用）")
    a = ap.parse_args()
    plan = Path(a.plan)
    images = Path(a.images) if a.images else ROOT / "out" / plan.name
    title, body, key = build(plan, images, thumbs=not a.no_thumbs, public=a.public)
    meta = load(plan / "shotlist.json")["meta"]
    date = meta.get("date", "")
    inner = (f"<title>{esc(title)}</title>\n<style>{CSS}</style>\n"
             f'<div id="app" data-key="{esc(key)}" data-date="{esc(date)}">{body}</div>\n')
    js = JS.replace("document.body.getAttribute('data-key')", "document.getElementById('app').getAttribute('data-key')") \
           .replace("document.body.getAttribute('data-date')", "document.getElementById('app').getAttribute('data-date')")
    inner += f"<script>{js}</script>\n"
    full = ("<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
            + inner.replace("</style>\n", "</style>\n</head><body>\n", 1) + "</body></html>\n")
    for old in plan.glob("*拍摄核对表*.html"):
        old.unlink()
    out = plan / out_name(meta)
    out.write_text(full, encoding="utf-8")
    if a.fragment:
        Path(a.fragment).write_text(inner, encoding="utf-8")
    print("核对表：", out, f"{out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
