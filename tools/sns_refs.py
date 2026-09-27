#!/usr/bin/env python3
"""
sns_refs.py　SNS 参考机位：把 plans/<plan>/sns_refs.json 里逐帖记录的机位卡画成拍摄脚本的「参考机位」页。

  python tools/sns_refs.py --plan plans/<plan> --out plans/<plan>/cards

输出：
  cards/sns_01.png        参考机位分布图（风格化底图上画每帖的相机位置与朝向，颜色按可复现度）+ 一览表
  cards/sns_02.png ...    （--cards 时）单独的机位卡页，每页 3 张；默认不出，机位卡已并入对应分镜页：构图示意、俯视小图、机位要素、视觉拆解、可复现度与本组用法、原帖链接
  sns_refs.md             同内容的文字版
只记链接与观察，不保存、不嵌入原帖图片；构图示意按记录的 frame 字段画剪影。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_cards import W, H, BG, GREEN, INK, MUTED, PANEL, LINE, font, panel, text_block, latlon_to_px  # noqa: E402
from geo_common import compass  # noqa: E402

LEVEL_COL = {"高": (46, 110, 70), "中": (176, 98, 40), "低": (140, 140, 132)}
GAZE = {"camera": "看镜头", "away": "看别处", "down": "低头", "closed": "闭眼", "back": "背影"}
POSE = {"stand": "站", "walk": "走", "sit": "坐", "lean": "倚靠", "back": "背影", "crouch": "蹲"}


def offset(latlon, bearing, meters):
    lat, lon = latlon
    b = math.radians(bearing)
    return (lat + meters * math.cos(b) / 110540, lon + meters * math.sin(b) / (111320 * math.cos(math.radians(lat))))


def arrow(d, p0, p1, col, w=3, head=10, dashed=False):
    if dashed:
        n = max(2, int(math.dist(p0, p1) / 8))
        for i in range(0, n, 2):
            a = (p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n)
            b = (p0[0] + (p1[0] - p0[0]) * (i + 1) / n, p0[1] + (p1[1] - p0[1]) * (i + 1) / n)
            d.line([a, b], fill=col, width=w)
    else:
        d.line([p0, p1], fill=col, width=w)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        a = ang + math.pi - s * 0.45
        d.line([p1, (p1[0] + head * math.cos(a), p1[1] + head * math.sin(a))], fill=col, width=w)


def chip(d, x, y, text, col, f):
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((x, y, x + tw + 16, y + f.size + 10), radius=9, fill=col)
    d.text((x + 8, y + 4), text, font=f, fill=(255, 255, 255))
    return x + tw + 24


def load_basemap(plan: Path, name="main"):
    st = plan / "basemaps" / f"{name}_styled.png"
    mt = plan / "basemaps" / f"{name}_meta.json"
    if not st.exists():
        st = plan / "basemaps" / f"{name}_osm.png"
    if not (st.exists() and mt.exists()):
        return None, None
    return Image.open(st).convert("RGB"), json.loads(mt.read_text(encoding="utf-8"))


def render_map(plan, R, stops_order, out):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 26), "参考机位", font=font(52, True), fill=GREEN)
    d.line([(262, 34), (262, 84)], fill=GREEN, width=3)
    d.text((280, 30), "SNS 上的出片机位与本组分镜的关系", font=font(40, True), fill=GREEN)
    d.text((W - 40 - d.textlength(R.get("browsed", "")[:16], font=font(18)), 52), R.get("browsed", "")[:16], font=font(18), fill=MUTED)
    base, meta = load_basemap(plan)
    mx0, my0, side = 40, 110, 880
    refs = R["refs"]
    if base is not None:
        scale = base.width / meta["size"]
        pts = []
        for r in refs:
            pts.append(latlon_to_px(meta, *r["latlon"], scale))
            pts.append(latlon_to_px(meta, *offset(r["latlon"], r["cam_bearing"], r["cam_dist"]), scale))
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.25 + 80
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        pad = Image.new("RGB", (base.width + 4000, base.height + 4000), (243, 238, 222))
        pad.paste(base, (2000, 2000))
        crop = pad.crop((int(cx - span / 2) + 2000, int(cy - span / 2) + 2000, int(cx + span / 2) + 2000, int(cy + span / 2) + 2000)).resize((side, side), Image.LANCZOS)
        img.paste(crop, (mx0, my0))
        k = side / span
        X = lambda p: (mx0 + (p[0] - (cx - span / 2)) * k, my0 + (p[1] - (cy - span / 2)) * k)
        d.rectangle((mx0, my0, mx0 + side, my0 + side), outline=LINE, width=2)
        for r in refs:
            col = LEVEL_COL.get(r["reproducible"]["level"], MUTED)
            s = X(latlon_to_px(meta, *r["latlon"], scale))
            c = X(latlon_to_px(meta, *offset(r["latlon"], r["cam_bearing"], r["cam_dist"]), scale))
            if math.dist(s, c) < 26:                       # 近距离机位放大一点，箭头才看得见
                ang = math.atan2(c[1] - s[1], c[0] - s[0])
                c = (s[0] + 26 * math.cos(ang), s[1] + 26 * math.sin(ang))
            arrow(d, c, s, col, w=4, head=11, dashed=r.get("location_confidence") == "低")
            d.ellipse((s[0] - 5, s[1] - 5, s[0] + 5, s[1] + 5), fill=col)
            d.ellipse((c[0] - 15, c[1] - 15, c[0] + 15, c[1] + 15), fill=col, outline=(255, 255, 255), width=2)
            lab = r["id"][1:]
            tw = d.textlength(lab, font=font(15, True))
            d.text((c[0] - tw / 2, c[1] - 10), lab, font=font(15, True), fill=(255, 255, 255))
        m_per_px = meta["m_per_px"] / scale
        bar = 10 / m_per_px * k
        d.rectangle((mx0 + 10, my0 + side - 40, mx0 + 30 + bar, my0 + side - 10), fill=(255, 255, 255))
        d.line([(mx0 + 20, my0 + side - 18), (mx0 + 20 + bar, my0 + side - 18)], fill=INK, width=3)
        d.text((mx0 + 22, my0 + side - 38), "10 m", font=font(13), fill=INK)
        d.rectangle((mx0 + side - 34, my0 + 6, mx0 + side - 6, my0 + 46), fill=(255, 255, 255))
        arrow(d, (mx0 + side - 20, my0 + 42), (mx0 + side - 20, my0 + 20), MUTED, 2, 7)
        d.text((mx0 + side - 26, my0 + 26), "北", font=font(13), fill=MUTED)
    # 右：一览
    rx0, rx1 = 940, W - 40
    y = panel(d, (rx0, 110, rx1, 790), "一览（按游览顺序）", font(24, True))
    for r in refs:
        col = LEVEL_COL.get(r["reproducible"]["level"], MUTED)
        d.ellipse((rx0 + 12, y + 2, rx0 + 40, y + 30), fill=col)
        tw = d.textlength(r["id"][1:], font=font(14, True))
        d.text((rx0 + 26 - tw / 2, y + 6), r["id"][1:], font=font(14, True), fill=(255, 255, 255))
        d.text((rx0 + 52, y), r["title"], font=font(17, True), fill=INK)
        sub = f"{r['platform']} · {r['posted']} · {r['stop']} · 对应分镜 {'、'.join(r.get('shots', []))} · 可复现 {r['reproducible']['level']}"
        d.text((rx0 + 52, y + 24), sub, font=font(14), fill=MUTED)
        y += 60
    y = panel(d, (rx0, 804, rx1, H - 50), "看图方法", font(24, True))
    for t in ["圆圈是相机位置，箭头指向人物；数字是参考编号。",
              "颜色：绿 = 9/28 可复现度高，橙 = 中，灰 = 低；虚线 = 位置推测，需现场核对。",
              "机位按照片内容推算，只作找位参考；原帖截图与本组示意并排放在对应分镜页，链接见核对表。"]:
        y = text_block(d, (rx0 + 14, y), t, font(15), rx1 - rx0 - 28, spacing=3) + 4
    d.text((40, H - 32), "原帖截图只存本机 sns_private/，仅作个人拍摄参考，不进公开版与仓库。", font=font(15), fill=MUTED)
    img.save(out, quality=92)


def silhouette(img, box, fr, col_top=(214, 204, 186), col_bot=(92, 72, 58)):
    """在独立画布上画竖幅构图剪影再贴回，超出画框的部分自然裁掉。"""
    x0, y0, x1, y1 = [int(v) for v in box]
    fw, fh = x1 - x0, y1 - y0
    im = Image.new("RGB", (fw, fh), (232, 229, 220))
    d = ImageDraw.Draw(im)
    top, feet = fh * fr.get("top", 0.3), fh * fr.get("feet", 0.95)
    hgt = feet - top
    cx = fw * fr.get("x", 0.5)
    r, bw = hgt * 0.07, hgt * 0.22
    d.ellipse((cx - r, top, cx + r, top + 2 * r), fill=(90, 70, 55))
    waist = top + hgt * 0.42
    d.polygon([(cx - bw * 0.4, top + 2 * r), (cx + bw * 0.4, top + 2 * r), (cx + bw * 0.45, waist), (cx - bw * 0.45, waist)], fill=col_top)
    d.polygon([(cx - bw * 0.42, waist), (cx + bw * 0.42, waist), (cx + bw * 0.6, feet), (cx - bw * 0.6, feet)], fill=col_bot)
    for k in (1, 2):
        d.line([(fw * k / 3, 0), (fw * k / 3, fh)], fill=(255, 255, 255), width=1)
        d.line([(0, fh * k / 3), (fw, fh * k / 3)], fill=(255, 255, 255), width=1)
    img.paste(im, (x0, y0))
    ImageDraw.Draw(img).rectangle((x0, y0, x1, y1), outline=INK, width=2)


def mini_top(d, box, r):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 6
    d.rectangle(box, fill=(240, 236, 226), outline=LINE)
    R = (min(x1 - x0, y1 - y0) / 2 - 22)
    b = math.radians(r["cam_bearing"])
    c = (cx + R * math.sin(b), cy - R * math.cos(b))
    col = LEVEL_COL.get(r["reproducible"]["level"], MUTED)
    arrow(d, c, (cx, cy), col, w=3, head=9, dashed=r.get("location_confidence") == "低")
    d.rectangle((c[0] - 9, c[1] - 7, c[0] + 9, c[1] + 7), fill=col)
    d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=GREEN)
    d.text((x0 + 6, y0 + 4), "北↑", font=font(12), fill=MUTED)
    lab = f"{r['cam_dist']:g} m"
    d.text(((c[0] + cx) / 2 + 6, (c[1] + cy) / 2 - 8), lab, font=font(13), fill=INK)


def render_card(img, box, r, cols):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    col = LEVEL_COL.get(r["reproducible"]["level"], MUTED)
    d.rounded_rectangle(box, radius=10, fill=PANEL, outline=LINE, width=2)
    d.rounded_rectangle((x0, y0, x1, y0 + 46), radius=10, fill=GREEN)
    d.rectangle((x0, y0 + 24, x1, y0 + 46), fill=GREEN)
    d.text((x0 + 16, y0 + 8), f"{r['id']}  {r['title']}", font=font(22, True), fill=(255, 255, 255))
    meta = f"{r['platform']} · {r['posted']}"
    d.text((x1 - 16 - d.textlength(meta, font=font(16)), y0 + 13), meta, font=font(16), fill=(225, 232, 226))
    # 左列：构图示意 + 俯视
    fx0, fy0 = x0 + 16, y0 + 60
    d.text((fx0, fy0), "构图示意", font=font(14, True), fill=GREEN)
    silhouette(img, (fx0, fy0 + 22, fx0 + 150, fy0 + 222), r.get("frame", {}), *cols)
    d = ImageDraw.Draw(img)
    d.text((fx0 + 170, fy0), "机位（俯视）", font=font(14, True), fill=GREEN)
    mini_top(d, (fx0 + 170, fy0 + 22, fx0 + 330, fy0 + 182), r)
    d.text((fx0 + 170, fy0 + 190), f"相机在人物{compass(r['cam_bearing'])}侧", font=font(13), fill=MUTED)
    # 中列：机位要素
    mx0, mx1 = x0 + 370, x0 + 900
    y = y0 + 60
    rows = [("位置", f"{r['spot']}（停留点：{r['stop']}）" + ("　位置推测，需现场核对" if r.get("location_confidence") == "低" else "")),
            ("机位", f"{compass(r['cam_bearing'])} {r['cam_bearing']}° · {r['cam_dist']:g} m · 机高 {r['cam_h']} · {r['lens_est']} · {r['kind']}"),
            ("时段光线", f"{r['time_light']}（{r['weather']}）"),
            ("姿势视线", f"{POSE.get(r['pose'], r['pose'])} · {GAZE.get(r['gaze'], r['gaze'])}；{r.get('pose_note', '')}"),
            ("前景背景", r["fg_bg"]), ("穿搭", r["outfit"]), ("对应分镜", "、".join(r.get("shots", [])) or "无")]
    for lab, val in rows:
        d.text((mx0, y), lab, font=font(14, True), fill=GREEN)
        y = text_block(d, (mx0 + 72, y), val, font(14), mx1 - mx0 - 80, spacing=2) + 4
    # 右列：视觉拆解 + 可复现 + 用法 + 链接
    rx0, rx1 = x0 + 920, x1 - 16
    y = y0 + 60
    v = r.get("visual", {})
    for lab, key in (("光线", "light"), ("色调", "tone"), ("构图", "composition")):
        if v.get(key):
            d.text((rx0, y), lab, font=font(14, True), fill=GREEN)
            y = text_block(d, (rx0 + 44, y), v[key], font(14), rx1 - rx0 - 48, spacing=2) + 4
    y += 2
    nx = chip(d, rx0, y, f"可复现 {r['reproducible']['level']}", col, font(13, True))
    y = text_block(d, (nx, y + 2), r["reproducible"]["why"], font(13), rx1 - nx, fill=MUTED, spacing=2) + 6
    ub = y
    y = text_block(d, (rx0 + 12, y + 8), "本组：" + r["use"], font(14, True), rx1 - rx0 - 24, fill=INK, spacing=2) + 8
    d.rectangle((rx0, ub, rx0 + 4, y), fill=col)
    url = r["url"].replace("https://", "")
    d.text((rx0, y1 - 26), url, font=font(12), fill=MUTED)


def outfit_cols(plan):
    try:
        o = json.loads((plan / "outfit.json").read_text(encoding="utf-8"))
        hx = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
        cs = o.get("colors", [])
        low = [c for c in cs if any(k in c.get("part", "") for k in ("裙", "裤"))]
        return (hx(cs[0]["hex"]), hx(low[0]["hex"]) if low else (92, 72, 58))
    except Exception:
        return ((214, 204, 186), (92, 72, 58))


def write_md(plan, R):
    L = [f"# SNS 参考机位　{R.get('plan', '')}", "", f"{R.get('browsed', '')}；来源：{'；'.join(R.get('sources', []))}", "",
         R.get("fields_note", ""), ""]
    for r in R["refs"]:
        L += [f"## {r['id']} {r['title']}", "",
              f"- 原帖：{r['url']}（{r['platform']}，{r['posted']}）",
              f"- 位置：{r['spot']}；停留点 {r['stop']}；对应分镜 {'、'.join(r.get('shots', []))}" + ("（位置推测，需现场核对）" if r.get("location_confidence") == "低" else ""),
              f"- 机位：人物的{compass(r['cam_bearing'])}侧 {r['cam_bearing']}°，{r['cam_dist']:g} m，机高 {r['cam_h']}，{r['lens_est']}，{r['kind']}",
              f"- 时段光线：{r['time_light']}（{r['weather']}）",
              f"- 姿势视线：{POSE.get(r['pose'], r['pose'])}，{GAZE.get(r['gaze'], r['gaze'])}；{r.get('pose_note', '')}",
              f"- 前景背景：{r['fg_bg']}", f"- 穿搭：{r['outfit']}",
              f"- 视觉：光线 {r['visual'].get('light', '')}；色调 {r['visual'].get('tone', '')}；构图 {r['visual'].get('composition', '')}",
              f"- 可复现度：{r['reproducible']['level']}，{r['reproducible']['why']}",
              f"- 本组用法：{r['use']}"] + [f"  - 分镜 {k}：{v}" for k, v in (r.get("use_by_shot") or {}).items()] + [""]
    (plan / "sns_refs.md").write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out")
    ap.add_argument("--cards", action="store_true", help="另出单独的机位卡页（默认不出：机位卡内容已并入对应分镜页）")
    a = ap.parse_args()
    plan = Path(a.plan)
    out = Path(a.out or plan / "cards"); out.mkdir(parents=True, exist_ok=True)
    R = json.loads((plan / "sns_refs.json").read_text(encoding="utf-8"))
    order = []
    rj = plan / "route.json"
    if rj.exists():
        order = [s["name"] for s in json.loads(rj.read_text(encoding="utf-8")).get("stops", [])]
    R["refs"].sort(key=lambda r: (order.index(r["stop"]) if r["stop"] in order else 99, r["id"]))
    for old in out.glob("sns_*.png"):
        old.unlink()
    render_map(plan, R, order, out / "sns_01.png")
    cols = outfit_cols(plan)
    n = 1
    per = 3
    for i in range(0, len(R["refs"]) if a.cards else 0, per):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((40, 26), "参考机位卡", font=font(44, True), fill=GREEN)
        d.text((310, 44), "左：构图示意与俯视机位；中：机位要素；右：视觉拆解、可复现度与本组用法", font=font(18), fill=MUTED)
        for j, r in enumerate(R["refs"][i:i + per]):
            render_card(img, (40, 100 + j * 312, W - 40, 100 + j * 312 + 300), r, cols)
        d.text((40, H - 32), "构图示意按照片推算的人物位置与大小画剪影，不是原图；原帖请用链接查看。", font=font(15), fill=MUTED)
        n += 1
        img.save(out / f"sns_{n:02d}.png", quality=92)
    write_md(plan, R)
    print(f"参考机位：{len(R['refs'])} 条，{n} 页 → {out}")


if __name__ == "__main__":
    main()
