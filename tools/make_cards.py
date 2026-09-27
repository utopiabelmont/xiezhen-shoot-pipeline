#!/usr/bin/env python3
"""
make_cards.py　把分镜表 + 示意图 + 光线数据合成为「拍摄小抄」卡片（1600×1067 PNG，每张一页）。

用法：
  python tools/make_cards.py --plan plans/hakone-0928 --images out/20260928-箱根玻璃之森 --out plans/hakone-0928/cards
需要：plans/<批次>/shotlist.json（含 meta 与 shots）、示意图 png（文件名以 shot id 开头）。
俯视图由程序按分镜表里的 cam_bearing / cam_dist / bg_bearing / face_bearing 与 sun 数据绘制，北在上。
"""
from __future__ import annotations

import argparse
import json
import re
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 1067
BG = (247, 244, 236)
GREEN = (46, 82, 58)
INK = (40, 40, 40)
MUTED = (110, 110, 105)
PANEL = (255, 255, 253)
LINE = (215, 210, 198)
GOLD = (196, 146, 52)
BLUE = (112, 150, 190)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/meiryo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/PingFang.ttc",
]


def find_fonts():
    import glob
    reg = bold = None
    for c in FONT_CANDIDATES + glob.glob("/usr/share/fonts/**/*CJK*", recursive=True):
        if Path(c).exists():
            if ("bd" in c.lower() or "bold" in c.lower()) and bold is None:
                bold = c
            elif reg is None:
                reg = c
    reg = reg or bold
    bold = bold or reg
    if not reg:
        raise SystemExit("找不到中文字体，请安装 Noto Sans CJK 或在 Windows 上运行")
    return reg, bold


REG, BOLD = find_fonts()


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else REG, size)
    except Exception:
        return ImageFont.truetype(REG, size)


def wrap(draw, text, f, width):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if draw.textlength(cur + ch, font=f) > width:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def text_block(draw, xy, text, f, width, fill=INK, spacing=6):
    x, y = xy
    for ln in wrap(draw, text, f, width):
        draw.text((x, y), ln, font=f, fill=fill)
        y += f.size + spacing
    return y


def panel(draw, box, title, tf):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=10, fill=PANEL, outline=LINE, width=2)
    draw.rounded_rectangle((x0, y0, x1, y0 + 40), radius=10, fill=GREEN)
    draw.rectangle((x0, y0 + 20, x1, y0 + 40), fill=GREEN)
    draw.text((x0 + 14, y0 + 7), title, font=tf, fill=(255, 255, 255))
    return y0 + 52


def pol(cx, cy, bearing, r):
    a = math.radians(bearing)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def arrow(draw, p0, p1, fill, width=4, head=12):
    draw.line([p0, p1], fill=fill, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        q = (p1[0] - head * math.cos(ang - s * 0.5), p1[1] - head * math.sin(ang - s * 0.5))
        draw.line([p1, q], fill=fill, width=width)


BASEMAPS = {}   # name -> (Image, meta)，由 main 装载；shot["basemap"] 选用，缺省 "main"


def basemap_for(shot):
    return BASEMAPS.get(shot.get("basemap", "main"))


def latlon_to_px(meta, lat, lon, scale):
    import math as _m
    kx = 111320 * _m.cos(_m.radians(meta["lat0"])); ky = 110540
    x = meta["size"] / 2 + (lon - meta["lon0"]) * kx / meta["m_per_px"]
    y = meta["size"] / 2 - (lat - meta["lat0"]) * ky / meta["m_per_px"]
    return x * scale, y * scale


def draw_topview_map(img, box, shot, sun, weather_note, f_small, f_tiny):
    """风格化底图裁切（以人物为中心）+ 程序叠加：人物、相机、距离、背景标签、太阳箭头、指北。"""
    base, meta = basemap_for(shot)
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    scale = base.width / meta["size"]              # 风格图相对原底图的缩放
    mpp = meta["m_per_px"] / scale                 # 风格图上 米/像素
    win_w_m = float(shot.get("map_window_m", 84.0))
    win_w = win_w_m / mpp; win_h = win_w * bh / bw
    sx, sy = latlon_to_px(meta, *shot["subject_latlon"], scale)
    pad = Image.new("RGB", (base.width + 2000, base.height + 2000), (243, 238, 222))
    pad.paste(base, (1000, 1000))
    crop = pad.crop((int(sx - win_w / 2) + 1000, int(sy - win_h / 2) + 1000, int(sx + win_w / 2) + 1000, int(sy + win_h / 2) + 1000)).resize((bw, bh), Image.LANCZOS)
    img.paste(crop, (x0, y0))
    d = ImageDraw.Draw(img)
    d.rectangle(box, outline=LINE, width=2)
    k = bw / win_w                                  # 面板像素 / 风格图像素
    ppm = k / mpp                                   # 面板像素 / 米
    cx, cy = x0 + bw / 2, y0 + bh / 2
    def P(bearing, meters):
        return pol(cx, cy, bearing, meters * ppm)
    # 背景标签
    bx, by = P(shot["bg_bearing"], min(14, win_w_m / 2 - 6))
    tw = d.textlength(shot["bg_label"], font=f_tiny)
    bx = min(max(bx - tw / 2, x0 + 4), x1 - tw - 4); by = min(max(by - 9, y0 + 4), y1 - 22)
    d.rectangle((bx - 4, by - 2, bx + tw + 4, by + 18), fill=(255, 255, 255))
    d.text((bx, by), shot["bg_label"], font=f_tiny, fill=GREEN)
    # 相机
    vis_d = max(shot["cam_dist"] * ppm, 58)
    camx, camy = pol(cx, cy, shot["cam_bearing"], vis_d)
    d.line([(camx, camy), (cx, cy)], fill=INK, width=2)
    d.rectangle((camx - 11, camy - 8, camx + 11, camy + 8), fill=INK)
    d.ellipse((camx - 5, camy - 5, camx + 5, camy + 5), fill=(220, 220, 220))
    lab = f"摄影者 {shot['cam_dist']} m"
    tw = d.textlength(lab, font=f_tiny)
    lx = min(max(camx - tw / 2, x0 + 4), x1 - tw - 4); ly = camy + 11 if camy < y1 - 32 else camy - 30
    d.rectangle((lx - 3, ly - 1, lx + tw + 3, ly + 17), fill=(255, 255, 255)); d.text((lx, ly), lab, font=f_tiny, fill=INK)
    # 人物与朝向
    d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=(120, 90, 70), outline=(255, 255, 255), width=2)
    fx, fy = pol(cx, cy, shot["face_bearing"], 20)
    arrow(d, (cx, cy), (fx, fy), (120, 90, 70), 3, 8)
    d.rectangle((cx - 48, cy - 30, cx - 12, cy - 12), fill=(255, 255, 255)); d.text((cx - 46, cy - 29), "人物", font=f_tiny, fill=INK)
    # 太阳（晴天版）；室内分镜不画
    if shot.get("indoor"):
        sun = None
    if sun:
        az, el = sun
        s0 = P(az, win_w_m / 2 - 3); s1 = pol(cx, cy, az, 30)
        arrow(d, s0, s1, GOLD, 5, 14)
        lab = f"晴天版 {shot.get('alt_time') or shot['time'][:5]} 太阳 {int(az)}°/{int(el)}°"
        tw = d.textlength(lab, font=f_tiny)
        lx, ly = s0
        lx = min(max(lx - tw / 2, x0 + 4), x1 - tw - 4); ly = min(max(ly - 24 if s0[1] > cy else ly + 8, y0 + 26), y1 - 22)
        d.rectangle((lx - 3, ly - 2, lx + tw + 3, ly + 18), fill=(255, 255, 255)); d.text((lx, ly), lab, font=f_tiny, fill=GOLD)
    # 指北 + 图例
    d.rectangle((x1 - 34, y0 + 4, x1 - 6, y0 + 44), fill=(255, 255, 255))
    arrow(d, (x1 - 20, y0 + 40), (x1 - 20, y0 + 18), MUTED, 2, 7); d.text((x1 - 26, y0 + 26), "北", font=f_tiny, fill=MUTED)
    maxw = (x1 - 40) - (x0 + 10)                   # 给右上角指北留位
    note = weather_note
    while note and d.textlength(note + "…", font=f_tiny) > maxw:
        note = note[:-1]
    if note != weather_note:
        note += "…"
    tw = d.textlength(note, font=f_tiny)
    d.rectangle((x0 + 4, y0 + 4, x0 + 10 + tw, y0 + 22), fill=(255, 255, 255)); d.text((x0 + 7, y0 + 5), note, font=f_tiny, fill=BLUE)


def draw_topview(img, box, shot, sun, weather_note, f_small, f_tiny):
    if basemap_for(shot) and shot.get("subject_latlon"):
        return draw_topview_map(img, box, shot, sun, weather_note, f_small, f_tiny)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=8, fill=(236, 233, 222), outline=LINE)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 + 6
    R = min(x1 - x0, y1 - y0) // 2 - 26
    # 指北
    d.text((cx - 8, y0 + 6), "北", font=f_small, fill=MUTED)
    arrow(d, (cx, y0 + 40), (cx, y0 + 26), MUTED, 2, 7)
    # 背景大形（弧）
    bb = shot["bg_bearing"]
    p = [pol(cx, cy, b, R) for b in range(int(bb) - 40, int(bb) + 41, 5)]
    d.line(p, fill=(150, 170, 140), width=14)
    lbx, lby = pol(cx, cy, bb, R - 34)
    tw = d.textlength(shot["bg_label"], font=f_tiny)
    d.rectangle((lbx - tw / 2 - 4, lby - 11, lbx + tw / 2 + 4, lby + 9), fill=(255, 255, 255))
    d.text((lbx - tw / 2, lby - 9), shot["bg_label"], font=f_tiny, fill=GREEN)
    # 人物
    d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=(120, 90, 70), outline=INK)
    fx, fy = pol(cx, cy, shot["face_bearing"], 22)
    d.line([(cx, cy), (fx, fy)], fill=INK, width=3)
    d.text((cx + 14, cy - 8), "人物", font=f_tiny, fill=INK)
    # 相机
    scale = R * 0.75 / max(shot["cam_dist"], 2.5)
    camx, camy = pol(cx, cy, shot["cam_bearing"], min(R * 0.8, shot["cam_dist"] * scale))
    d.rectangle((camx - 10, camy - 7, camx + 10, camy + 7), fill=INK)
    d.ellipse((camx - 5, camy - 5, camx + 5, camy + 5), fill=(200, 200, 200))
    d.line([(camx, camy), (cx, cy)], fill=INK, width=1)
    mx, my = (camx + cx) / 2, (camy + cy) / 2
    d.text((mx + 6, my - 8), f"约 {shot['cam_dist']} 米", font=f_tiny, fill=INK)
    d.text((camx - 16, camy + 10), "摄影者", font=f_tiny, fill=INK)
    # 光（室内分镜不画日照与散射箭头）
    if shot.get("indoor"):
        sun = None
    if sun:
        az, el = sun
        sx, sy = pol(cx, cy, az, R + 10)
        ex, ey = pol(cx, cy, az, 30)
        arrow(d, (sx, sy), (ex, ey), GOLD, 5, 14)
        m = re.search(r"\d{1,2}:\d{2}", shot.get("alt_time") or shot["time"])
        lab = f"晴天版 {m.group(0) if m else ''} 太阳 {int(az)}°/{int(el)}°"
        tw = d.textlength(lab, font=f_tiny)
        lx, ly = x0 + 8, y1 - 44
        d.rectangle((lx - 3, ly - 2, lx + tw + 3, ly + 18), fill=(255, 255, 255))
        d.text((lx, ly), lab, font=f_tiny, fill=GOLD)
    # 阴天：四周小箭头
    for b in (() if shot.get("indoor") else (0, 90, 180, 270)):
        s0 = pol(cx, cy, b, R + 4); s1 = pol(cx, cy, b, R - 14)
        arrow(d, s0, s1, BLUE, 2, 6)
    d.text((x0 + 8, y1 - 22), weather_note, font=f_tiny, fill=BLUE)


def make_card(shot, meta, photo_path: Path, out_path: Path, sun_for_shot):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title, f_h, f_b, f_s, f_t = font(46, True), font(24, True), font(21), font(18), font(15)
    # 标题
    d.text((40, 26), shot["id"], font=font(52, True), fill=GREEN)
    d.line([(118, 34), (118, 84)], fill=GREEN, width=3)
    d.text((136, 30), shot["title"], font=f_title, fill=GREEN)
    sub = f"{meta['place'].split('（')[0]}　{meta['date']}　{meta['gear'].split('+')[-1].strip().split('，')[0]}"
    d.text((W - 40 - d.textlength(sub, font=f_s), 52), sub, font=f_s, fill=MUTED)
    # 照片
    px0, py0, px1, py1 = 40, 110, 940, H - 60
    if photo_path and photo_path.exists():
        ph = Image.open(photo_path).convert("RGB")
        ph.thumbnail((px1 - px0, py1 - py0))
        bx = px0 + (px1 - px0 - ph.width) // 2
        img.paste(ph, (bx, py0))
        d.rectangle((bx - 1, py0 - 1, bx + ph.width, py0 + ph.height), outline=LINE)
    else:
        d.rectangle((px0, py0, px1, py1), fill=(230, 226, 214))
        d.text((px0 + 30, py0 + 30), "（示意图待生成）", font=f_b, fill=MUTED)
    # 右栏
    rx0, rx1 = 970, W - 40
    y = panel(d, (rx0, 110, rx1, 318), "相机设置", f_h)
    rows = [("焦段光圈", shot["lens"]), ("快门 ISO", shot["shutter"]), ("创意外观", shot.get("look", "")), ("闪光灯", shot.get("flash", "")),
            ("景别", shot["kind"]), ("机位", shot["camera"])]
    for k, v in rows:
        d.text((rx0 + 14, y), k, font=f_t, fill=GREEN)
        y = text_block(d, (rx0 + 100, y), v, f_t, rx1 - rx0 - 118, spacing=2)
        y += 1
    y = panel(d, (rx0, 330, rx1, 690), "机位与光线示意（俯视图，北在上）", f_h)
    draw_topview(img, (rx0 + 10, 384, rx1 - 10, 680), shot, sun_for_shot, shot.get("topview_note") or meta_weather_note(meta), f_s, f_t)
    d = ImageDraw.Draw(img)
    split = rx0 + int((rx1 - rx0) * 0.4)
    y = panel(d, (rx0, 702, split - 6, 912), "姿势与引导", f_h)
    text_block(d, (rx0 + 12, y), shot["subject"] + "\n" + shot["action"], f_t, split - rx0 - 30, spacing=2)
    y = panel(d, (split + 6, 702, rx1, 912), "光线与备选", f_h)
    text_block(d, (split + 18, y), shot["light"] + "\n备选：" + shot["alt"], f_t, rx1 - split - 32, spacing=2)
    y = panel(d, (rx0, 924, rx1, H - 22), "时段 · 地点 · 注意", f_h)
    text_block(d, (rx0 + 14, y), f"{shot['time']}　{shot['spot']}　注意：{shot['note']}", f_t, rx1 - rx0 - 28, spacing=2)
    foot = "AI 拍摄示意，非现场实拍；布局与站位以现场条件为准。光向按 sun.md 计算。"
    d.text((40, H - 42), foot, font=f_t, fill=MUTED)
    img.save(out_path, quality=92)


def meta_weather_note(meta):
    return "预报阴雨：散射光无方向；金色箭头为放晴时的太阳方位"


def sun_at(meta, time_str):
    """取分镜起始时刻最近的整点/半点太阳数据。"""
    m = re.search(r"(\d{1,2}):(\d{2})", time_str or "")
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    key = f"{hh:02d}:{'30' if mm >= 30 else '00'}"
    sun = meta.get("sun", {})
    if key in sun:
        return sun[key]
    key2 = f"{hh:02d}:00"
    return sun.get(key2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    plan = json.load(open(Path(a.plan) / "shotlist.json", encoding="utf-8"))
    meta = plan["meta"]
    global BASEMAPS
    bm = Path(a.plan) / "basemap_styled.png"; bmeta = Path(a.plan) / "basemap_meta.json"
    if bm.exists() and bmeta.exists():
        BASEMAPS["main"] = (Image.open(bm).convert("RGB"), json.load(open(bmeta)))
    for st in sorted((Path(a.plan) / "basemaps").glob("*_styled.png")):
        name = st.name[:-len("_styled.png")]
        mt = st.with_name(f"{name}_meta.json")
        if mt.exists():
            BASEMAPS[name] = (Image.open(st).convert("RGB"), json.load(open(mt)))
    for name, (im, _) in BASEMAPS.items():
        print("使用风格化底图", name, im.size)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    imgs = {p.name[:2]: p for p in sorted(Path(a.images).glob("*.png"))}
    for s in plan["shots"]:
        sun = sun_at(meta, s.get("alt_time") or s["time"])
        make_card(s, meta, imgs.get(s["id"]), out / f"card_{s['id']}.png", sun)
        print("card", s["id"], "photo:", imgs.get(s["id"]).name if imgs.get(s["id"]) else "无")


if __name__ == "__main__":
    main()
