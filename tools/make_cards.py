#!/usr/bin/env python3
"""
make_cards.py　把分镜表 + 示意图 + 光线数据合成为「拍摄脚本」卡片（1600×1067 PNG，每张一页）。

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


NO_LINE_START = set("，。、；：！？）」』】》〉”’・…·%）,.;:!?)]}°")
NO_LINE_END = set("（「『【《〈“‘([{")


WORD_CH = set("._-/:–~×°%+")


def _wordish(c):
    return (c.isascii() and c.isalnum()) or c in WORD_CH


def wrap(draw, text, f, width):
    """按宽度折行；行首不放闭合标点，行尾不留开括号（避头尾），英文单词、数字与时间不从中间断开，
    末行不留单个孤字。"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if draw.textlength(cur + ch, font=f) > width and cur:
            if ch in NO_LINE_START and not _wordish(ch):  # 闭合标点挂在上一行末尾（允许略超）
                cur += ch
                continue
            carry = ""
            while cur and cur[-1] in NO_LINE_END:     # 开括号带到下一行
                carry = cur[-1] + carry; cur = cur[:-1]
            if _wordish(ch):                          # 英文、数字、时间整体换行
                k = len(cur)
                while k > 0 and _wordish(cur[k - 1]):
                    k -= 1
                if 0 < k < len(cur) and len(cur) - k < 16:
                    carry = cur[k:] + carry; cur = cur[:k].rstrip()
            lines.append(cur.rstrip()); cur = (carry + ch).lstrip()
        else:
            cur += ch
    if cur:
        lines.append(cur)
    # 行尾不留“空格 + 单个汉字”，数字不和紧随的单位（cm、m、s、mm）分行
    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        if len(a) > 4 and a[-2] == " " and not _wordish(a[-1]) and a[-1] not in NO_LINE_START \
                and draw.textlength(a[-1] + b, font=f) <= width:
            lines[i], lines[i + 1] = a[:-2], a[-1] + b
            continue
        m_unit = re.match(r"^([a-zA-Z]{1,3})(?=\s|$|[，。；、）])", b)
        m_num = re.search(r"(?:^|\s)([0-9][0-9.–~×/-]*)$", a)
        if m_unit and m_num and len(a) - len(m_num.group(1)) > 4 \
                and draw.textlength(m_num.group(1) + " " + b, font=f) <= width:
            n = m_num.group(1)
            lines[i], lines[i + 1] = a[:-len(n)].rstrip(), n + " " + b
    # 孤字：末行只剩 1–2 个字时，从上一行挪两个字下来（不让标点落行首、不拆英文数字）
    if len(lines) >= 2 and len(lines[-1].strip()) <= 2 and len(lines[-2]) > 6:
        prev, last = lines[-2], lines[-1]
        k = len(prev) - 2
        while k > 2 and (prev[k] in NO_LINE_START or prev[k - 1] in NO_LINE_END or prev[k] == " "
                         or (_wordish(prev[k]) and _wordish(prev[k - 1]))):
            k -= 1
        if k > 2 and prev[k - 2] == " " and not _wordish(prev[k - 1]):   # 别在空格后只留一个汉字
            k -= 1
        if len(prev) - k <= 5:
            sep = " " if (_wordish(prev[-1]) != _wordish(last[:1])) else ""
            lines[-2], lines[-1] = prev[:k].rstrip(), prev[k:].lstrip() + sep + last
    return lines


def text_block(draw, xy, text, f, width, fill=INK, spacing=6):
    x, y = xy
    for ln in wrap(draw, text, f, width):
        draw.text((x, y), ln, font=f, fill=fill)
        y += f.size + spacing
    return y


def fit_block(draw, xy, text, width, bottom, sizes=(15, 14, 13), fill=INK):
    """在 bottom 之前放下整段文字：先按字号从大到小试，仍放不下就截断加省略号。"""
    for sz in sizes:
        f = font(sz); sp = 2 if sz >= 14 else 1
        lines = wrap(draw, text, f, width)
        if xy[1] + len(lines) * (sz + sp) <= bottom:
            break
    maxl = max(1, int((bottom - xy[1]) // (sz + sp)))
    if len(lines) > maxl:
        lines = lines[:maxl]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=f) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    y = xy[1]
    for ln in lines:
        draw.text((xy[0], y), ln, font=f, fill=fill)
        y += sz + sp
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


def _hit(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _seg_boxes(p0, p1, r=5, step=10):
    n = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / step))
    return [(p0[0] + (p1[0] - p0[0]) * i / n - r, p0[1] + (p1[1] - p0[1]) * i / n - r,
             p0[0] + (p1[0] - p0[0]) * i / n + r, p0[1] + (p1[1] - p0[1]) * i / n + r) for i in range(n + 1)]


def _place(d, text, f, anchors, box, occ, fill, bg=(255, 255, 255)):
    """在候选左上角里挑第一个不与已占区域重叠、且在框内的位置；都不行就取重叠最少的。"""
    x0, y0, x1, y1 = box
    tw = d.textlength(text, font=f); th = f.size + 4
    best, best_n = None, None
    for ax, ay in anchors:
        ax = min(max(ax, x0 + 4), x1 - tw - 6); ay = min(max(ay, y0 + 4), y1 - th - 4)
        r = (ax - 3, ay - 1, ax + tw + 3, ay + th)
        n = sum(_hit(r, o) for o in occ)
        if best is None or n < best_n:
            best, best_n = (ax, ay, r), n
        if n == 0:
            break
    ax, ay, r = best
    d.rectangle(r, fill=bg); d.text((ax, ay), text, font=f, fill=fill)
    occ.append(r)


def draw_topview_map(img, box, shot, sun, weather_note, f_small, f_tiny):
    """风格化底图裁切（以人物为中心）+ 程序叠加：人物、相机、距离、背景标签、太阳箭头、指北。
    标签最后统一摆放，彼此以及与图标、连线互不遮挡。"""
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
    th = f_tiny.size + 4
    occ = []
    # 顶部天气说明与右上角指北
    maxw = (x1 - 40) - (x0 + 10)
    note = weather_note
    while note and d.textlength(note + "…", font=f_tiny) > maxw:
        note = note[:-1]
    if note != weather_note:
        note += "…"
    tw = d.textlength(note, font=f_tiny)
    note_box = (x0 + 4, y0 + 4, x0 + 10 + tw, y0 + 8 + th)
    occ += [note_box, (x1 - 34, y0 + 4, x1 - 6, y0 + 44)]
    # 相机
    vis_d = max(shot["cam_dist"] * ppm, 70)
    camx, camy = pol(cx, cy, shot["cam_bearing"], vis_d)
    d.line([(camx, camy), (cx, cy)], fill=INK, width=2)
    d.rectangle((camx - 11, camy - 8, camx + 11, camy + 8), fill=INK)
    d.ellipse((camx - 5, camy - 5, camx + 5, camy + 5), fill=(220, 220, 220))
    occ += [(camx - 13, camy - 10, camx + 13, camy + 10)] + _seg_boxes((camx, camy), (cx, cy), 3)
    # 人物与朝向
    d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=(120, 90, 70), outline=(255, 255, 255), width=2)
    fx, fy = pol(cx, cy, shot["face_bearing"], 20)
    arrow(d, (cx, cy), (fx, fy), (120, 90, 70), 3, 8)
    occ += [(cx - 13, cy - 13, cx + 13, cy + 13)] + _seg_boxes((cx, cy), (fx, fy), 4)
    # 太阳（晴天版）；室内分镜不画。箭头起点收在框内
    sun_lab = None
    if shot.get("indoor"):
        sun = None
    if sun:
        az, el = sun
        a = math.radians(az)
        dx, dy = math.sin(a), -math.cos(a)
        lim = min((bw / 2 - 16) / abs(dx) if abs(dx) > 1e-6 else 1e9,
                  (bh / 2 - 16) / abs(dy) if abs(dy) > 1e-6 else 1e9)
        s0 = (cx + dx * lim, cy + dy * lim); s1 = pol(cx, cy, az, 30)
        arrow(d, s0, s1, GOLD, 5, 14)
        occ += _seg_boxes(s0, s1, 4)
        sun_lab = (s0, f"晴天版 {shot.get('alt_time') or shot['time'][:5]} 太阳 {int(az)}°/{int(el)}°")
    # 以下是文字，统一避让
    d.rectangle(note_box, fill=(255, 255, 255)); d.text((x0 + 7, y0 + 5), note, font=f_tiny, fill=BLUE)
    d.rectangle((x1 - 34, y0 + 4, x1 - 6, y0 + 44), fill=(255, 255, 255))
    arrow(d, (x1 - 20, y0 + 40), (x1 - 20, y0 + 18), MUTED, 2, 7); d.text((x1 - 26, y0 + 26), "北", font=f_tiny, fill=MUTED)
    tw = d.textlength("人物", font=f_tiny)
    _place(d, "人物", f_tiny, [(cx - tw - 16, cy - th - 8), (cx + 16, cy - th - 8), (cx - tw - 16, cy + 8), (cx + 16, cy + 8),
                               (cx - tw / 2, cy - th - 16), (cx - tw / 2, cy + 16)], box, occ, INK)
    lab = f"摄影者 {shot['cam_dist']} m"
    tw = d.textlength(lab, font=f_tiny)
    _place(d, lab, f_tiny, [(camx - tw / 2, camy + 14), (camx - tw / 2, camy - th - 14), (camx + 16, camy - th / 2),
                            (camx - tw - 16, camy - th / 2), (camx + 16, camy + 10), (camx - tw - 16, camy + 10),
                            (camx + 16, camy - th - 10), (camx - tw - 16, camy - th - 10)], box, occ, INK)
    if sun_lab:
        (lx, ly), lab = sun_lab
        tw = d.textlength(lab, font=f_tiny)
        _place(d, lab, f_tiny, [(lx - tw / 2, ly - th - 10 if ly > cy else ly + 10), (lx - tw / 2, ly + 10 if ly > cy else ly - th - 10),
                                (lx + 12, ly - th / 2), (lx - tw - 12, ly - th / 2),
                                (lx - tw / 2, ly - 2 * th - 14 if ly > cy else ly + th + 14),
                                (lx + 12, ly - th - 14), (lx - tw - 12, ly - th - 14), (lx + 12, ly + 12), (lx - tw - 12, ly + 12)],
               box, occ, GOLD)
    bx, by = pol(cx, cy, shot["bg_bearing"], min(14, win_w_m / 2 - 6) * ppm)
    tw = d.textlength(shot["bg_label"], font=f_tiny)
    _place(d, shot["bg_label"], f_tiny, [(bx - tw / 2, by - th / 2), (bx - tw / 2, by - th - 12), (bx - tw / 2, by + 12),
                                         (bx + 12, by - th / 2), (bx - tw - 12, by - th / 2),
                                         (bx - tw / 2, by - 2 * th - 16), (bx - tw / 2, by + th + 16),
                                         (bx + 12, by - th - 14), (bx - tw - 12, by - th - 14), (bx + 12, by + 12), (bx - tw - 12, by + 12),
                                         (bx - tw / 2, by - 3 * th - 20), (bx - tw / 2, by + 2 * th + 20)], box, occ, GREEN)


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
    medium = shot.get("medium", "still")
    badge = MEDIUM_BADGE.get(medium)
    if badge:
        bx = 136 + d.textlength(shot["title"], font=f_title) + 18
        bw = d.textlength(badge, font=f_h) + 24
        d.rounded_rectangle((bx, 40, bx + bw, 76), radius=8, fill=MEDIUM_COLOR.get(medium, GOLD))
        d.text((bx + 12, 45), badge, font=f_h, fill=(255, 255, 255))
    sub = f"{meta['place'].split('（')[0]}　{meta['date']}　{meta['gear'].split('+')[-1].strip().split('，')[0]}"
    d.text((W - 40 - d.textlength(sub, font=f_s), 52), sub, font=f_s, fill=MUTED)
    # 照片：有 SNS 参考时左为 AI 示意、中为原帖，下方为对照说明；
    # AI 示意是横图时改为上下排：横图占满左两栏，下方左为原帖、右为对照说明
    refs = [SNS_REFS[i] for i in SNS_BY_SHOT.get(shot["id"], []) if i in SNS_REFS]
    refs.sort(key=lambda r: {"高": 0, "中": 1, "低": 2}.get(r["reproducible"]["level"], 3))
    refs = refs[:2]
    ph = Image.open(photo_path).convert("RGB") if (photo_path and photo_path.exists()) else None
    wide = bool(refs) and ph is not None and ph.width > ph.height
    px0, py0, px1, py1 = 40, 110, 940, H - 60
    if refs:
        px1, py1 = (950, 110 + 500) if wide else (595, 850)
    photo_bottom = py1
    if ph is not None:
        if wide:                                    # 横图裁成面板比例，铺满
            tw_, th_ = px1 - px0, py1 - py0
            r0 = tw_ / th_
            if ph.width / ph.height > r0:
                cw = int(ph.height * r0); ph = ph.crop(((ph.width - cw) // 2, 0, (ph.width - cw) // 2 + cw, ph.height))
            else:
                ch = int(ph.width / r0); ph = ph.crop((0, (ph.height - ch) // 2, ph.width, (ph.height - ch) // 2 + ch))
            ph = ph.resize((tw_, th_), Image.LANCZOS)
        else:
            ph.thumbnail((px1 - px0, py1 - py0))
        bx = px0 + (px1 - px0 - ph.width) // 2
        img.paste(ph, (bx, py0))
        d.rectangle((bx - 1, py0 - 1, bx + ph.width, py0 + ph.height), outline=LINE)
        photo_bottom = py0 + ph.height
    else:
        d.rectangle((px0, py0, px1, py1), fill=(230, 226, 214))
        d.text((px0 + 30, py0 + 30), "（示意图待生成）", font=f_b, fill=MUTED)
    if refs:
        tag = "本组 AI 示意"
        d.rectangle((px0, py0, px0 + d.textlength(tag, font=font(13, True)) + 12, py0 + 22), fill=GREEN)
        d.text((px0 + 6, py0 + 3), tag, font=font(13, True), fill=(255, 255, 255))
        n = len(refs)
        if wide:
            top = photo_bottom + 14
            sw = (px1 - px0 - 18) // (n + 1)         # 原帖各占一格，说明占一格
            for k, r in enumerate(refs):
                draw_sns_slot(img, (px0 + k * (sw + 9), top, px0 + k * (sw + 9) + sw, H - 60), r)
            nx0 = px0 + n * (sw + 9)
            note_box = (nx0, top, px1, H - 60)
        else:
            sx0, sx1 = 613, 950
            slot = (H - 60 - 110) // n
            for k, r in enumerate(refs):
                draw_sns_slot(img, (sx0, 110 + k * slot, sx1, 110 + (k + 1) * slot - (12 if k < n - 1 else 0)), r)
            note_box = (px0, photo_bottom + 12, px1, H - 60)
        d = ImageDraw.Draw(img)
        if n > 1 and not wide:
            yl = 110 + slot - 6
            d.line([(sx0, yl), (sx1, yl)], fill=LINE, width=1)
        # 对照说明
        nx0, ny0, nx1, ny1 = note_box
        yb = panel(d, note_box, "对照 SNS 参考", font(20, True))
        f14 = font(14)
        room = (ny1 - 8 - yb) // 19
        per = max(2, room // n)
        for r in refs:
            lines = fit_lines(d, f"{r['id']}：" + r.get('use_by_shot', {}).get(shot['id'], r['use']), f14, nx1 - nx0 - 28, per)
            if per - len(lines) >= 5:                   # 空间富余时补上时段光线、姿势与可复现理由
                extra = (f"时段光线：{r.get('time_light', '')}（{r.get('weather', '')}）\n"
                         f"姿势：{r.get('pose_note', '')}\n"
                         f"可复现{r['reproducible']['level']}：{r['reproducible']['why']}")
                lines += fit_lines(d, extra, f14, nx1 - nx0 - 28, per - len(lines))
            for ln in lines:
                d.text((nx0 + 14, yb), ln, font=f14, fill=INK)
                yb += 19
    # 右栏
    rx0, rx1 = 970, W - 40
    y = panel(d, (rx0, 110, rx1, 318), SETTINGS_TITLE.get(medium, "相机设置"), f_h)
    rows = settings_rows(shot, medium)
    for k, v in rows:
        d.text((rx0 + 14, y), k, font=f_t, fill=GREEN)
        y = text_block(d, (rx0 + 100, y), v, f_t, rx1 - rx0 - 118, spacing=2)
        y += 1
    y = panel(d, (rx0, 330, rx1, 690), "机位与光线示意（俯视图，北在上）", f_h)
    draw_topview(img, (rx0 + 10, 384, rx1 - 10, 680), shot, sun_for_shot, shot.get("topview_note") or meta_weather_note(meta), f_s, f_t)
    d = ImageDraw.Draw(img)
    split = rx0 + int((rx1 - rx0) * 0.4)
    y = panel(d, (rx0, 702, split - 6, 912), "姿势与引导", f_h)
    pz = POSES_BY_SHOT.get(shot["id"], [])
    ptxt = ("\n参考姿势：" + "、".join(f"{p['id']} {p['name']}" for p in pz)) if pz else ""
    fit_block(d, (rx0 + 12, y), shot["subject"] + "\n" + shot["action"] + ptxt, split - rx0 - 30, 904)
    y = panel(d, (split + 6, 702, rx1, 912), "光线与备选", f_h)
    fit_block(d, (split + 18, y), shot["light"] + "\n备选：" + shot["alt"], rx1 - split - 32, 904)
    y = panel(d, (rx0, 924, rx1, H - 22), "时段 · 地点 · 注意", f_h)
    ref_txt = ""                                   # SNS 参考已在左侧对照显示，这里不重复
    fit_block(d, (rx0 + 14, y), f"{shot['time']}　{shot['spot']}　注意：{shot['note']}{ref_txt}", rx1 - rx0 - 28, H - 30)
    foot = FOOT.get(medium, "AI 拍摄示意，非现场实拍；布局与站位以现场条件为准。光向按 sun.md 计算。")
    d.text((40, H - 42), foot, font=f_t, fill=MUTED)
    img.save(out_path, quality=92)


SNS_BY_SHOT: dict = {}
POSES_BY_SHOT: dict = {}                              # pose_refs.json：分镜 id → 适用的小红书姿势
SNS_REFS: dict = {}
SNS_DIR: Path | None = None
PUBLIC = False                                        # 公开版（examples / GitHub / 发布页）不放原帖截图
LEVEL_COL = {"高": (46, 110, 70), "中": (176, 98, 40), "低": (140, 140, 132)}
COMPASS16 = ["北", "北北东", "东北", "东北东", "东", "东南东", "东南", "南南东", "南", "南南西", "西南", "西南西", "西", "西北西", "西北", "北北西"]


def fit_lines(d, text, f, width, max_lines):
    """按宽度折行，超过 max_lines 时截断并加省略号。"""
    lines = wrap(d, text, f, width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and d.textlength(lines[-1] + "…", font=f) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def sns_image(ref):
    if PUBLIC or SNS_DIR is None:
        return None
    for ext in ("png", "jpg", "jpeg", "webp"):
        f = SNS_DIR / f"{ref['id']}.{ext}"
        if f.exists():
            return f
    return None


def sketch(size, fr):
    """原帖截图缺失时的构图剪影（按记录的人物位置与大小）。"""
    fw, fh = size
    im = Image.new("RGB", (fw, fh), (232, 229, 220))
    d = ImageDraw.Draw(im)
    top, feet = fh * fr.get("top", 0.3), fh * fr.get("feet", 0.95)
    hgt = feet - top
    cx = fw * fr.get("x", 0.5)
    r, bw = hgt * 0.07, hgt * 0.22
    d.ellipse((cx - r, top, cx + r, top + 2 * r), fill=(90, 70, 55))
    waist = top + hgt * 0.42
    d.polygon([(cx - bw * 0.4, top + 2 * r), (cx + bw * 0.4, top + 2 * r), (cx + bw * 0.45, waist), (cx - bw * 0.45, waist)], fill=(214, 204, 186))
    d.polygon([(cx - bw * 0.42, waist), (cx + bw * 0.42, waist), (cx + bw * 0.6, feet), (cx - bw * 0.6, feet)], fill=(92, 72, 58))
    for k in (1, 2):
        d.line([(fw * k / 3, 0), (fw * k / 3, fh)], fill=(255, 255, 255), width=1)
        d.line([(0, fh * k / 3), (fw, fh * k / 3)], fill=(255, 255, 255), width=1)
    return im


def qr_image(url, size):
    """原帖链接的二维码（手机扫码直接打开）；没装 qrcode 库时返回 None。"""
    try:
        import qrcode
    except ImportError:
        return None
    q = qrcode.QRCode(border=2, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(url); q.make(fit=True)
    return q.make_image(fill_color=(40, 60, 45), back_color=(255, 255, 255)).convert("RGB").resize((size, size), Image.NEAREST)


def sns_sketch(ref):
    """按文字描述重画的原帖构图线稿（plans/<plan>/sns_sketch/<Sxx>*.png）；原创插画，公开版也可用。"""
    if SNS_DIR is None:
        return None
    hits = sorted((SNS_DIR.parent / "sns_sketch").glob(f"{ref['id']}*.png"))
    return hits[0] if hits else None


def pending_card(size, ref):
    """原帖截图还没补时的占位：二维码 + 编号 + 该存成的文件名，取代抽象的人形剪影。"""
    fw, fh = size
    im = Image.new("RGB", (fw, fh), (238, 235, 226))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, fw - 1, fh - 1), outline=LINE, width=2)
    d.text((14, 14), "原图待补", font=font(22, True), fill=GREEN)
    d.text((14, 44), f"{ref['id']} · {ref['platform']} · {ref.get('posted', '')}", font=font(14), fill=MUTED)
    qs = min(fw - 60, fh - 190, 240)
    q = qr_image(ref["url"], qs) if qs > 60 else None
    y = 76
    if q:
        im.paste(q, ((fw - qs) // 2, y)); y += qs + 12
    lines = ["1. 手机扫码，在 App 里打开原帖", "2. 长按图片保存（或截图）",
             f"3. 放进 sns_inbox/ 或存成 sns_private/{ref['id']}.jpg", "4. 重跑 cards，这里换成原图"]
    for ln in lines:
        for t in fit_lines(d, ln, font(13), fw - 28, 2):
            if y > fh - 18:
                break
            d.text((14, y), t, font=font(13), fill=INK); y += 18
    return im


def draw_sns_slot(img, box, ref):
    """SNS 栏的一格：编号与来源、原帖截图（或构图剪影）、机位一句话、链接。"""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    col = LEVEL_COL.get(ref["reproducible"]["level"], MUTED)
    f13, f14b = font(13), font(14, True)
    head = f"{ref['id']} · {ref['platform']} · {ref['posted']}"
    d.text((x0, y0), head, font=f14b, fill=GREEN)
    lv = f"可复现 {ref['reproducible']['level']}"
    lw = d.textlength(lv, font=font(12, True)) + 14
    d.rounded_rectangle((x1 - lw, y0 - 1, x1, y0 + 19), radius=8, fill=col)
    d.text((x1 - lw + 7, y0 + 1), lv, font=font(12, True), fill=(255, 255, 255))
    dr = COMPASS16[int((ref["cam_bearing"] % 360) / 22.5 + 0.5) % 16]
    info = f"机位：人物{dr}侧 {ref['cam_dist']:g} m · {ref['lens_est']} · {ref['kind']}" + ("（位置推测）" if ref.get("location_confidence") == "低" else "")
    comp = "构图：" + ref.get("visual", {}).get("composition", "")
    url = ref["url"].replace("https://www.", "").replace("https://", "")
    info_lines = fit_lines(d, info, f13, x1 - x0, 2)
    comp_lines = fit_lines(d, comp, f13, x1 - x0, 2) if (y1 - y0) > 420 else []
    text_h = (len(info_lines) + len(comp_lines)) * 17 + 18
    iy0, iy1 = y0 + 26, y1 - text_h - 4
    bw, bh = x1 - x0, iy1 - iy0
    src = sns_image(ref)
    sk = sns_sketch(ref)
    if src:
        ph = Image.open(src).convert("RGB")
        ph.thumbnail((bw, bh))
        tag = "原帖截图 · 仅个人参考"
    elif sk:
        ph = Image.open(sk).convert("RGB")
        ph.thumbnail((bw, bh))
        q = qr_image(ref["url"], max(56, min(84, ph.width // 4)))
        if q:                                       # 右下角放原帖二维码，现场扫码看原图
            ph.paste(q, (ph.width - q.width - 6, ph.height - q.height - 26))
        tag = "原帖构图线稿（按文字描述，扫码看原图）"
    else:
        ph = pending_card((bw, bh), ref)
        tag = "原图待补 · 扫码打开原帖"
    px = x0 + (bw - ph.width) // 2
    img.paste(ph, (px, iy0))
    d = ImageDraw.Draw(img)
    d.rectangle((px - 1, iy0 - 1, px + ph.width, iy0 + ph.height), outline=LINE)
    tw = d.textlength(tag, font=font(12))
    d.rectangle((px, iy0 + ph.height - 20, px + tw + 10, iy0 + ph.height), fill=(0, 0, 0))
    d.text((px + 5, iy0 + ph.height - 18), tag, font=font(12), fill=(255, 255, 255))
    ty = iy0 + ph.height + 6
    for ln in info_lines + comp_lines:
        d.text((x0, ty), ln, font=f13, fill=INK)
        ty += 17
    d.text((x0, ty + 1), url if d.textlength(url, font=font(11)) <= x1 - x0 else url[:44] + "…", font=font(11), fill=MUTED)
MEDIUM_BADGE = {"burst": "连拍抓动态", "video": "短片", "live": "手机实况"}
MEDIUM_COLOR = {"burst": (176, 98, 40), "video": (70, 96, 150), "live": (110, 110, 105)}
SETTINGS_TITLE = {"burst": "相机设置（连拍）", "video": "相机设置（S-Log3 短片）", "live": "iPhone 设置（实况）"}
FOOT = {"video": "关键帧 AI 示意，非现场实拍；运镜轨迹与三帧画面变化见下一页，曝光基准见 docs/VIDEO_NOTES.md。",
        "burst": "AI 示意为连拍中要选的那一帧；连拍与预拍设置见 docs/VIDEO_NOTES.md。",
        "live": "AI 示意，非现场实拍；手机实况图用于过渡与小红书，不占相机时间。"}
CLIP_MODE = {"24p": "動画位 4K 24p（实时，≤5 s）", "sq60": "S&Q 60→24p（2.5 倍慢）", "sq120": "S&Q 120→24p（5 倍慢，裁 1.52×）"}


def settings_rows(shot, medium):
    """右上「相机设置」块按 medium 换内容；每行 (标签, 文本)，面板高度只够 6 行，文本要短。"""
    if medium == "video":
        c = shot.get("clip", {})
        return [("焦段光圈", shot["lens"]),
                ("模式快门", f"{CLIP_MODE.get(c.get('mode', '24p'), c.get('mode', ''))}　{shot.get('shutter', '')}"),
                ("曝光 ND", f"{c.get('exposure', '脸放斑马 52%')}　ND {c.get('nd', '按现场')}"),
                ("运镜", f"{c.get('move', '')}　{c.get('dur_s', 5)} s"),
                ("起 / 止", f"{c.get('start', '')} → {c.get('end', '')}"),
                ("机位", shot["camera"])]
    if medium == "burst":
        b = shot.get("burst", {})
        return [("焦段光圈", shot["lens"]),
                ("连拍", f"{'电子 30' if b.get('fps', 30) >= 20 else '机械 10'} 张/秒 · 预拍 {b.get('precap_s', 0.5)} s · AF-C 人物"),
                ("快门 ISO", shot["shutter"]),
                ("创意外观", shot.get("look", "")),
                ("动作", b.get("action", shot.get("action", ""))),
                ("机位", shot["camera"])]
    if medium == "live":
        l = shot.get("live", {})
        return [("设备", l.get("device", "iPhone 14 Pro 实况（3 s）")),
                ("镜头", l.get("lens", "主摄 24mm")),
                ("曝光", l.get("exposure", "长按锁 AE/AF，滑块按脸")),
                ("动作", l.get("action", shot.get("action", ""))),
                ("景别", shot["kind"]),
                ("机位", shot["camera"])]
    return [("焦段光圈", shot["lens"]), ("快门 ISO", shot["shutter"]), ("创意外观", shot.get("look", "")), ("闪光灯", shot.get("flash", "")),
            ("景别", shot["kind"]), ("机位", shot["camera"])]


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
    ap.add_argument("--public", action="store_true", help="公开版：不放 sns_private 里的原帖截图")
    a = ap.parse_args()
    plan = json.load(open(Path(a.plan) / "shotlist.json", encoding="utf-8"))
    global SNS_DIR, PUBLIC
    PUBLIC = a.public
    SNS_DIR = Path(a.plan) / "sns_private"
    sr = Path(a.plan) / "sns_refs.json"
    if sr.exists():                                   # SNS 参考机位：分镜卡左侧并排显示原帖与对照说明
        for r in json.load(open(sr, encoding="utf-8")).get("refs", []):
            SNS_REFS[r["id"]] = r
            for sid in r.get("shots", []):
                SNS_BY_SHOT.setdefault(sid, []).append(r["id"])
    pr = Path(a.plan) / "pose_refs.json"
    if pr.exists():
        for p in json.load(open(pr, encoding="utf-8")).get("poses", []):
            for sid in p.get("shots", []):
                POSES_BY_SHOT.setdefault(sid, []).append(p)
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
