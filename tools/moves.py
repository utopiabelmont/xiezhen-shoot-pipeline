#!/usr/bin/env python3
"""
moves.py　短片分镜的运镜示意页：俯视轨迹、侧视高度与俯仰、起/中/止三帧画面变化、时间条与操作要点。

  python tools/moves.py --plan plans/<plan> --out plans/<plan>/cards        → cards/move_<id>.png（每条 medium=video 一页）
  python tools/moves.py --library docs/img/moves_library.jpg               → 运镜库总览图（每种运镜一格）

运镜类型按 clip.move_type，没写时从 clip.move 的文字判断（下摇 / 后拉上摇 / 前跟 / 后跟 / 侧跟 / 环绕 / 微推 / 遮挡 / 转身 / 走远 / 固定）。
距离取 shot.cam_dist，另从 camera / clip.start / clip.end 文字里读「从 4 m 退到 8 m」「半径 2 m」；机位高度从 camera 文字读
（胸口 1.3 m、眼平 1.55 m、腰 1.0 m、低机位 0.6 m、高处 2.2 m）。可在 clip 里直接写 cam_h、walk_m、tilt_start、tilt_end、orbit_side（left/right）覆盖。
三帧画面按焦段（S&Q 120 乘 1.52 裁切）、距离、机位高度与俯仰角估算人物在竖幅画面里的大小和位置，叠三分线与 90% 安全框。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_cards import W, H, BG, GREEN, INK, MUTED, PANEL, LINE, font, panel, text_block  # noqa: E402

CAM = (176, 98, 40)          # 相机轨迹
SUBJ = GREEN                 # 人物轨迹
VIDEO = (70, 96, 150)
SKY = (222, 229, 234)
GROUND = (226, 219, 201)
GRID = (232, 228, 218)

TYPES = {
    "tilt_down_reveal": ("下摇揭示", ["下摇"]),
    "pull_back_tilt_up": ("后拉上摇", ["后拉", "上摇"]),
    "track_front": ("前跟（相机倒退）", ["前跟", "倒退"]),
    "track_behind": ("后跟", ["后跟"]),
    "track_side": ("侧跟", ["侧跟", "平行"]),
    "orbit_quarter": ("1/4 环绕", ["环绕"]),
    "push_in": ("固定微推", ["微推", "前推", "推进"]),
    "wipe_reveal": ("遮挡揭示", ["遮挡", "横移"]),
    "static_turn": ("固定 · 转身回眸", ["转身", "回眸"]),
    "static_walk_out": ("固定 · 人走远", ["走远", "走出", "出画"]),
    "static": ("固定机位升格", ["固定"]),
}
ORDER = ["tilt_down_reveal", "wipe_reveal", "track_side", "track_behind", "track_front", "push_in",
         "orbit_quarter", "static_turn", "static", "pull_back_tilt_up", "static_walk_out"]

HOWTO = {
    "tilt_down_reveal": ["机位固定，镜头从上方约 {tilt0}° 匀速下摇到人物，{move} 秒内到位。",
                         "只动手腕与肘，机身贴胸，下摇到人物落在下三分线附近停住。",
                         "到位后停 {hold} 秒，再让她迈步；剪辑时这一条做片头。"],
    "pull_back_tilt_up": ["从 {d} m 边退边抬镜头，退到 {d2} m 时上摇到 +{tilt1}° 左右。",
                          "后退用小碎步，脚跟先落地；后退和上摇同时开始、同时结束。",
                          "她保持不动，最后一两秒再向前走一步；做全片收尾。"],
    "track_front": ["相机在她正前方倒退走，与她同速，距离保持 {d} m。",
                    "机身贴胸、膝盖微屈走碎步；同伴扶你的肩看路。",
                    "她停步抬头时你也停，最后 {hold} 秒不动；人物大小不变，背景在后退。"],
    "track_behind": ["跟在她身后同速走，距离保持 {d} m，人放在画面中线。",
                     "碎步、机身贴胸，不要比她快；到转角或门口时停下让她走出去。",
                     "起止各停 {hold} 秒。"],
    "track_side": ["与她平行走，相机侧对她，距离保持 {d} m。",
                   "人放在一侧三分线上，运动方向的前方留空。",
                   "脚步和她同频，机身不转；起止各停 {hold} 秒。"],
    "orbit_quarter": ["以她为圆心、半径 {d} m 走 90° 弧，从{side}侧面走到正面。",
                      "边走边转机身，人始终在画面中线附近；前景（芒草、水晶穗）擦过镜头更有层次。",
                      "走到正面的那一刻她抬眼看镜头，弧线走完即停。"],
    "push_in": ["固定站位，肘部抵住身体，身体前倾推进约 10 cm。",
                "推进和她的手部动作同时开始，匀速，不要推到对焦面外。",
                "起止各停 {hold} 秒。"],
    "wipe_reveal": ["镜头贴近遮挡物（柱子、伞沿、树干）起幅，画面先是一片虚化的遮挡物。",
                    "横移 50–80 cm 露出她，横移速度均匀；遮挡物放在开头，剪辑时两条用同一遮挡物接。",
                    "露出后停 {hold} 秒。"],
    "static_turn": ["机位不动，她先侧身，听到提示后转过来看镜头，只转一半就停。",
                    "焦点放在脸上，转身中不要追焦跑焦。",
                    "起止各停 {hold} 秒。"],
    "static": ["机位固定（倚柱或肘部抵身），只拍被拨动的物体或局部动作。",
               "动作起手前 0.5 秒开机，动作停下后再录 {hold} 秒。",
               "前景留一点虚化，焦点在最先动的那一处。"],
    "static_walk_out": ["机位固定，她从画面中间走远，直到走出 90% 安全框。",
                        "出框后再录 {hold} 秒，给剪辑留尾巴。",
                        "适合做段落结尾。"],
}


def classify(clip: dict) -> str:
    if clip.get("move_type") in TYPES:
        return clip["move_type"]
    txt = clip.get("move", "")
    if "后拉" in txt or ("上摇" in txt and "下摇" not in txt):
        return "pull_back_tilt_up"
    for key in ["tilt_down_reveal", "track_front", "track_behind", "track_side", "orbit_quarter", "push_in",
                "wipe_reveal", "static_turn", "static_walk_out", "static"]:
        if any(k in txt for k in TYPES[key][1]):
            return key
    return "static"


def nums_m(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*m(?![a-z])", text or "")]


def params(shot: dict) -> dict:
    c = shot.get("clip", {})
    mt = classify(c)
    txt = " ".join([shot.get("camera", ""), c.get("start", ""), c.get("end", ""), c.get("move", "")])
    ms = nums_m(txt)
    d = float(shot.get("cam_dist") or (ms[0] if ms else 3))
    d2 = max(ms) if len(ms) >= 2 else d * 2
    m = re.search(r"半径\s*(\d+(?:\.\d+)?)", txt)
    if m:
        d = float(m.group(1))
    cam_txt = shot.get("camera", "")
    h = 1.3
    for k, v in (("眼平", 1.55), ("胸口", 1.3), ("腰", 1.0), ("低机位", 0.6), ("蹲", 0.8), ("高处", 2.2), ("举高", 2.1)):
        if k in cam_txt:
            h = v
            break
    f = float(re.search(r"(\d+)\s*mm", shot.get("lens", "35mm")).group(1))
    mode = c.get("mode", "24p")
    if mode == "sq120":
        f *= 1.52
    dur = float(c.get("dur_s", 5))
    hold = 1.0 if mode == "24p" else 0.5
    move_s = max(0.8, dur - 2 * hold)
    detail = shot.get("kind", "") in ("特写",) or d < 1.5
    return {"type": mt, "d": float(c.get("cam_dist_start", d)), "d2": float(c.get("cam_dist_end", d2)), "h": float(c.get("cam_h", h)),
            "f": f, "mode": mode, "dur": dur, "hold": hold, "move_s": move_s,
            "walk": float(c.get("walk_m", 0.8 * move_s)),          # 慢走约 0.8 m/s，按实录的运动秒数
            "tilt0": float(c.get("tilt_start", 35)), "tilt1": float(c.get("tilt_end", 22)),
            "side": c.get("orbit_side", "right"), "detail": detail, "start": c.get("start", ""), "end": c.get("end", ""),
            "move": c.get("move", TYPES[mt][0])}


def yaw_of(vx, vy):
    return math.degrees(math.atan2(vx, vy))


def aim_pitch(h, dist, z=1.0):
    return math.degrees(math.atan2(z - h, max(dist, 0.3)))


def aim_z(P, dist):
    """取景中心高度：画面能装下全身时对准身体中部，否则让头落在上三分线附近。"""
    if P["detail"]:
        return 1.35
    vis = 36 * dist / P["f"]
    return 0.95 if vis >= 2.0 else 1.62 - vis * 0.42


def state(P: dict, t: float) -> dict:
    """t∈[0,1] 为运动段进度。坐标米制：人物终点在原点附近，相机终点在 (0, -d)，页面上方 = +y。"""
    mt, d, h = P["type"], P["d"], P["h"]
    s = max(0.6, P["walk"])
    face = 180.0
    subj = (0.0, 0.0)
    cam = (0.0, -d)
    pitch = None
    obst = None
    if mt == "track_front":
        subj = (0.0, s * (1 - t)); cam = (0.0, s * (1 - t) - d)
    elif mt == "track_behind":
        subj = (0.0, s * t); cam = (0.0, s * t - d); face = 0
    elif mt == "track_side":
        subj = (-s / 2 + s * t, 0.0); cam = (subj[0], -d); face = 90
    elif mt == "orbit_quarter":
        sgn = 1 if P["side"] == "right" else -1
        phi = math.radians(90 * (1 - t)) * sgn
        cam = (d * math.sin(phi), -d * math.cos(phi))
    elif mt == "push_in":
        cam = (0.0, -d + 0.12 * t)
    elif mt == "pull_back_tilt_up":
        dd = d + (P["d2"] - d) * t
        cam = (0.0, -dd); face = 0
        subj = (0.0, 0.4 * max(0.0, t - 0.6) / 0.4)
        p0 = aim_pitch(h, d, aim_z(P, d))
        pitch = p0 + (P["tilt1"] - p0) * t
    elif mt == "tilt_down_reveal":
        face = 0
        p1 = aim_pitch(h, d, 1.1)
        pitch = P["tilt0"] + (p1 - P["tilt0"]) * t
    elif mt == "wipe_reveal":
        cam = (-0.75 * (1 - t), -d)
        obst = (-0.62, -d + 0.45, 0.3)
    elif mt == "static_turn":
        face = 90 + 70 * t
    elif mt == "static_walk_out":
        subj = (0.0, s * 1.6 * t); face = 0
    vx, vy = subj[0] - cam[0], subj[1] - cam[1]
    yaw = yaw_of(vx, vy)
    if mt in ("tilt_down_reveal", "static_walk_out", "static_turn", "static", "push_in", "pull_back_tilt_up"):
        yaw = 0.0
    if mt == "wipe_reveal":
        yaw = 0.0
    if mt == "track_side":
        yaw = 0.0
    dist = math.hypot(vx, vy)
    if pitch is None:
        pitch = aim_pitch(h, dist, aim_z(P, dist))
    return {"cam": cam, "subj": subj, "yaw": yaw, "face": face, "pitch": pitch, "dist": dist, "obst": obst}


def landmarks(P):
    """画面里的参照物（世界坐标，米）：让三帧看得出背景怎么动。返回 [(类型, x, y)]。"""
    mt = P["type"]
    far = max(state(P, 0)["subj"][1], state(P, 1)["subj"][1])
    if mt == "tilt_down_reveal":
        return [("tree", -2.6, 3.0), ("tree", 2.4, 5.0), ("tree", 0.4, 9.0)]
    if P["detail"]:
        return []
    ys = [far + 2.5, far + 5.5]
    if mt in ("track_front", "track_behind", "pull_back_tilt_up", "static_walk_out"):
        ys = [far - 1.5, far + 1.5, far + 4.5]
    out = []
    for y in ys:
        out += [("pillar", -1.4, y), ("pillar", 1.4, y)]
    return out


def project(s, P, x, y, z):
    """针孔投影：返回 (横向占比, 纵向占比, 深度)，竖幅画面宽 24 mm、高 36 mm。"""
    a = math.radians(s["yaw"])
    fx, fy = math.sin(a), math.cos(a)
    rx, ry = x - s["cam"][0], y - s["cam"][1]
    depth = rx * fx + ry * fy
    lat = rx * fy - ry * fx
    if depth < 0.25:
        return None
    u = 0.5 + P["f"] * lat / depth / 24
    v = 0.5 - P["f"] * math.tan(math.atan2(z - P["h"], depth) - math.radians(s["pitch"])) / 36
    return u, v, depth


# ---------------- 俯视轨迹 ----------------

def arrow(d, p0, p1, col, w=4, head=12):
    d.line([p0, p1], fill=col, width=w)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        a = ang + math.pi - s * 0.45
        d.line([p1, (p1[0] + head * math.cos(a), p1[1] + head * math.sin(a))], fill=col, width=w)


def cam_icon(d, p, yaw, col, filled=True, size=16):
    """相机图标：矩形机身 + 朝向的镜头三角。"""
    a = math.radians(yaw)
    fx, fy = math.sin(a), -math.cos(a)          # 页面坐标里的前方
    rx, ry = -fy, fx
    s = size
    body = [(p[0] + (-rx * s - fx * s * 0.7), p[1] + (-ry * s - fy * s * 0.7)),
            (p[0] + (rx * s - fx * s * 0.7), p[1] + (ry * s - fy * s * 0.7)),
            (p[0] + (rx * s + fx * s * 0.3), p[1] + (ry * s + fy * s * 0.3)),
            (p[0] + (-rx * s + fx * s * 0.3), p[1] + (-ry * s + fy * s * 0.3))]
    lens = [(p[0] + (-rx * s * 0.5 + fx * s * 0.3), p[1] + (-ry * s * 0.5 + fy * s * 0.3)),
            (p[0] + (rx * s * 0.5 + fx * s * 0.3), p[1] + (ry * s * 0.5 + fy * s * 0.3)),
            (p[0] + fx * s * 1.1, p[1] + fy * s * 1.1)]
    if filled:
        d.polygon(body, fill=col); d.polygon(lens, fill=col)
    else:
        d.polygon(body, outline=col, width=3); d.polygon(lens, outline=col, width=3)


def person_top(d, p, face, col, filled=True, r=13):
    if filled:
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col, outline=(255, 255, 255), width=2)
    else:
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), outline=col, width=3)
    a = math.radians(face)
    d.line([p, (p[0] + math.sin(a) * r * 2.1, p[1] - math.cos(a) * r * 2.1)], fill=col, width=4)


def draw_top(img, box, P, shot=None, small=False):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    ts = [i / 20 for i in range(21)]
    S = [state(P, t) for t in ts]
    pts = [s["cam"] for s in S] + [s["subj"] for s in S]
    if P["type"] == "tilt_down_reveal" or P["type"] == "static_walk_out":
        pts.append((0, P["walk"] * 1.6 + 0.6))
    if S[0]["obst"]:
        o = S[0]["obst"]; pts += [(o[0] - o[2], o[1] - o[2]), (o[0] + o[2], o[1] + o[2])]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 2.5) * 1.35
    sc = min(x1 - x0, y1 - y0) / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    X = lambda p: (x0 + (x1 - x0) / 2 + (p[0] - cx) * sc, y0 + (y1 - y0) / 2 - (p[1] - cy) * sc)
    # 1 m 网格
    gx = math.floor(cx - span / 2)
    while gx <= cx + span / 2:
        px = X((gx, 0))[0]
        if x0 < px < x1:
            d.line([(px, y0), (px, y1)], fill=GRID, width=1)
        gx += 1
    gy = math.floor(cy - span / 2)
    while gy <= cy + span / 2:
        py = X((0, gy))[1]
        if y0 < py < y1:
            d.line([(x0, py), (x1, py)], fill=GRID, width=1)
        gy += 1
    for kind, lx, ly in landmarks(P):
        q = X((lx, ly))
        if x0 < q[0] < x1 and y0 < q[1] < y1:
            r = 0.15 * sc if kind == "pillar" else 0.6 * sc
            d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=(208, 214, 200) if kind == "tree" else (200, 194, 182))
    # 视野（终点）
    e = S[-1]
    half = math.degrees(math.atan(12 / P["f"]))
    for sgn in (-1, 1):
        a = math.radians(e["yaw"] + sgn * half)
        L = e["dist"] * 1.25
        d.line([X(e["cam"]), X((e["cam"][0] + math.sin(a) * L, e["cam"][1] + math.cos(a) * L))], fill=(214, 196, 170), width=2)
    if e["obst"]:
        o = e["obst"]; a, b = X((o[0] - o[2] / 2, o[1] + o[2] / 2)), X((o[0] + o[2] / 2, o[1] - o[2] / 2))
        d.rectangle((a[0], a[1], b[0], b[1]), fill=(160, 150, 135))
        if not small:
            d.text((b[0] + 6, a[1]), "遮挡物", font=font(14), fill=MUTED)
    # 人物轨迹
    sp = [X(s["subj"]) for s in S]
    if math.dist(sp[0], sp[-1]) > 4:
        for i in range(0, len(sp) - 1, 2):
            d.line([sp[i], sp[i + 1]], fill=SUBJ, width=3)
        arrow(d, sp[-3], sp[-1], SUBJ, w=3, head=10)
    if P["type"] in ("tilt_down_reveal",):
        a0 = sp[-1]; a1 = X((0, P["walk"] + 0.6))
        for i in range(6):
            q0 = (a0[0] + (a1[0] - a0[0]) * i / 6, a0[1] + (a1[1] - a0[1]) * i / 6)
            q1 = (a0[0] + (a1[0] - a0[0]) * (i + 0.5) / 6, a0[1] + (a1[1] - a0[1]) * (i + 0.5) / 6)
            d.line([q0, q1], fill=SUBJ, width=3)
        if not small:
            d.text((a1[0] + 10, a1[1] - 8), "到位后迈步", font=font(14), fill=SUBJ)
    # 相机轨迹 + 秒刻度
    cp = [X(s["cam"]) for s in S]
    if math.dist(cp[0], cp[-1]) > 4:
        d.line(cp, fill=CAM, width=5)
        arrow(d, cp[-2], cp[-1], CAM, w=5, head=14)
        n = int(P["move_s"])
        for k in range(1, n + 1):
            t = min(1.0, k / P["move_s"])
            q = X(state(P, t)["cam"])
            d.ellipse((q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4), fill=(255, 255, 255), outline=CAM, width=2)
            if not small:
                d.text((q[0] + 8, q[1] - 18), f"{k}s", font=font(13), fill=CAM)
    # 起止图标
    s0, s1 = S[0], S[-1]
    person_top(d, X(s0["subj"]), s0["face"], SUBJ, filled=False)
    person_top(d, X(s1["subj"]), s1["face"], SUBJ, filled=True)
    cam_icon(d, X(s0["cam"]), s0["yaw"], CAM, filled=False)
    cam_icon(d, X(s1["cam"]), s1["yaw"], CAM, filled=True)
    fl = font(15 if not small else 13, True)
    if math.dist(cp[0], cp[-1]) > 40:
        d.text((cp[0][0] + 18, cp[0][1] + 6), "机·起", font=fl, fill=CAM)
        d.text((cp[-1][0] + 18, cp[-1][1] + 6), "机·止", font=fl, fill=CAM)
    elif math.dist(cp[0], cp[-1]) > 4:
        d.text((cp[-1][0] + 20, cp[-1][1] + 6), "相机（微移）", font=fl, fill=CAM)
    else:
        d.text((cp[-1][0] + 20, cp[-1][1] + 6), "相机（不动）", font=fl, fill=CAM)
    if math.dist(sp[0], sp[-1]) > 4:
        d.text((sp[0][0] - 58, sp[0][1] + 6), "人·起", font=fl, fill=SUBJ)
        d.text((sp[-1][0] + 18, sp[-1][1] - 22), "人·止", font=fl, fill=SUBJ)
    else:
        d.text((sp[-1][0] + 18, sp[-1][1] - 22), "人物", font=fl, fill=SUBJ)
    if P["type"] == "orbit_quarter":
        d.text((X((0, 0))[0] - 40, X((0, 0))[1] + 20), f"半径 {P['d']:g} m", font=font(14), fill=MUTED)
    if not small:
        # 距离标注与比例尺
        mid = ((cp[-1][0] + sp[-1][0]) / 2, (cp[-1][1] + sp[-1][1]) / 2)
        lab = f"{s1['dist']:.1f} m".replace(".0 m", " m")
        d.text((mid[0] - 14 - d.textlength(lab, font=font(14)), mid[1] - 8), lab, font=font(14), fill=INK)
        d.line([(x0 + 14, y1 - 16), (x0 + 14 + sc, y1 - 16)], fill=INK, width=3)
        d.text((x0 + 14, y1 - 38), "1 m", font=font(13), fill=INK)


# ---------------- 侧视 ----------------

def draw_side(img, box, P):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    s0, s1 = state(P, 0), state(P, 1)
    dist0, dist1 = s0["dist"], s1["dist"]
    back = max(0.0, math.dist(s0["cam"], s1["cam"])) if P["type"] == "pull_back_tilt_up" else 0.0
    total = max(dist0, dist1) + 1.2
    sc = min((x1 - x0 - 60) / total, (y1 - y0 - 30) / 2.6)
    gy = y1 - 18
    X = lambda x: x0 + 40 + (x + back) * sc
    Y = lambda z: gy - z * sc
    d.line([(x0 + 10, gy), (x1 - 10, gy)], fill=MUTED, width=2)
    # 人物（侧视剪影），站在距离 dist0 处（起点相机在 0）
    px = X(dist0)
    if P["detail"]:
        d.line([(px, Y(1.55)), (px, Y(1.2))], fill=SUBJ, width=3)
        for k in range(4):
            yy = Y(1.5 - k * 0.09)
            d.ellipse((px - 5, yy - 5, px + 5, yy + 5), fill=(170, 190, 200), outline=SUBJ)
        d.text((px + 12, Y(1.45)), "拍摄对象", font=font(14), fill=SUBJ)
    else:
        d.rounded_rectangle((px - 0.14 * sc, Y(1.42), px + 0.14 * sc, gy), radius=6, fill=(205, 196, 176), outline=SUBJ, width=2)
        r = 0.11 * sc
        d.ellipse((px - r, Y(1.62) - 0, px + r, Y(1.62) + 2 * r), fill=(90, 70, 55))
    # 相机起止
    ch = Y(P["h"])
    c0x, c1x = X(0), X(-back)
    for cx, pitch, dashed, lab in ((c0x, s0["pitch"], True, "起"), (c1x, s1["pitch"], False, "止")):
        if lab == "止" and abs(cx - c0x) < 2 and abs(s1["pitch"] - s0["pitch"]) < 1:
            continue
        a = math.radians(pitch)
        L = (x1 - x0) * 0.42
        if math.sin(a) > 0:
            L = min(L, (ch - y0 - 18) / math.sin(a))
        elif math.sin(a) < 0:
            L = min(L, (gy - ch - 4) / -math.sin(a))
        p1 = (cx + math.cos(a) * L, ch - math.sin(a) * L)
        if dashed:
            n = 10
            for i in range(0, n, 2):
                d.line([(cx + (p1[0] - cx) * i / n, ch + (p1[1] - ch) * i / n),
                        (cx + (p1[0] - cx) * (i + 1) / n, ch + (p1[1] - ch) * (i + 1) / n)], fill=MUTED, width=2)
        else:
            arrow(d, (cx, ch), p1, CAM, w=3, head=10)
        d.text((p1[0] + 4, p1[1] - 10), f"{lab} {pitch:+.0f}°", font=font(14, True), fill=MUTED if dashed else CAM)
    for cx, filled in ((c0x, back == 0), (c1x, True)):
        d.rectangle((cx - 12, ch - 9, cx + 8, ch + 9), fill=CAM if filled else None, outline=CAM, width=2)
        d.polygon([(cx + 8, ch - 5), (cx + 18, ch - 8), (cx + 18, ch + 8), (cx + 8, ch + 5)], fill=CAM if filled else None, outline=CAM)
        d.line([(cx - 2, ch + 9), (cx - 2, gy)], fill=LINE, width=2)
    if back:
        arrow(d, (c0x, ch + 26), (c1x, ch + 26), CAM, w=3, head=9)
        d.text((min(c0x, c1x) + 4, ch + 30), f"后退 {back:.1f} m".replace(".0 m", " m"), font=font(13), fill=CAM)
    d.text((c1x - 30, gy + 2), f"机高 {P['h']:.2g} m", font=font(13), fill=MUTED)
    d.text((px - 30, gy + 2), f"{dist0:.1f} m".replace(".0 m", " m"), font=font(13), fill=MUTED)


# ---------------- 画面变化（竖幅三帧） ----------------

def outfit_cols(outfit):
    top, bottom = (214, 204, 186), (92, 72, 58)
    try:
        cs = outfit.get("colors", [])
        hx = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
        if cs:
            top = hx(cs[0]["hex"])
        low = [c for c in cs if any(k in c.get("part", "") for k in ("裙", "裤", "下"))]
        if low:
            bottom = hx(low[0]["hex"])
    except Exception:
        pass
    return top, bottom


def draw_frame(P, t, fw, fh, cols):
    s = state(P, t)
    im = Image.new("RGB", (fw, fh), SKY)
    d = ImageDraw.Draw(im)
    f = P["f"]
    pitch = s["pitch"]
    # 地平线
    hy = fh * (0.5 + f * math.tan(math.radians(pitch)) / 36)
    if hy < fh:
        d.rectangle((0, max(0, hy), fw, fh), fill=GROUND)
    for kind, lx, ly in sorted(landmarks(P), key=lambda k: -math.hypot(k[1] - s["cam"][0], k[2] - s["cam"][1])):
        if kind == "pillar":
            b, tp = project(s, P, lx, ly, 0.0), project(s, P, lx, ly, 3.2)
            if b and tp:
                w = fw * P["f"] * 0.3 / b[2] / 24
                d.rectangle((b[0] * fw - w / 2, tp[1] * fh, b[0] * fw + w / 2, b[1] * fh), fill=(196, 188, 172))
        else:
            c, tp = project(s, P, lx, ly, 4.2), project(s, P, lx, ly, 0.0)
            if c and tp:
                r = fw * P["f"] * 1.6 / c[2] / 24
                d.line([(tp[0] * fw, tp[1] * fh), (c[0] * fw, c[1] * fh)], fill=(120, 100, 80), width=max(1, int(r / 8)))
                d.ellipse((c[0] * fw - r, c[1] * fh - r * 0.8, c[0] * fw + r, c[1] * fh + r * 0.8), fill=(150, 172, 138))
    sky_lab = {"tilt_down_reveal": "树冠 / 天空", "pull_back_tilt_up": "拱顶 / 天空"}.get(P["type"])
    if sky_lab and hy > fh * 0.35:
        d.text((8, 28), sky_lab, font=font(12), fill=MUTED)
    vx, vy = s["subj"][0] - s["cam"][0], s["subj"][1] - s["cam"][1]
    dist = max(0.3, s["dist"])
    rel = math.degrees(math.atan2(vx, vy)) - s["yaw"]
    rel = (rel + 180) % 360 - 180
    xc = fw * (0.5 + f * math.tan(math.radians(rel)) / 24)
    if P["type"] == "track_side":
        xc -= fw / 6
    Yz = lambda z: fh * (0.5 - f * math.tan(math.atan2(z - P["h"], dist) - math.radians(pitch)) / 36)
    px_per_m = fh * f / 36 / dist
    if P["detail"]:
        # 细节：垂下的水晶串 + 摆动弧
        swing = math.sin(t * math.pi * 3) * 0.06 if P["type"] == "static" else 0
        top = (xc, Yz(1.62))
        for k in range(6):
            z = 1.58 - k * 0.06
            x = xc + swing * px_per_m * (k / 5)
            r = max(3, 0.018 * px_per_m)
            d.line([top, (x, Yz(z))], fill=(150, 150, 150), width=1)
            d.ellipse((x - r, Yz(z) - r, x + r, Yz(z) + r), fill=(200, 215, 225), outline=(120, 140, 150))
        hx0 = xc + 0.05 * px_per_m
        d.ellipse((hx0 - 0.05 * px_per_m, Yz(1.25) - 0.03 * px_per_m, hx0 + 0.06 * px_per_m, Yz(1.25) + 0.05 * px_per_m), fill=(225, 190, 165))
    else:
        w_body = 0.36 * px_per_m
        top_y, waist, feet = Yz(1.42), Yz(0.95), Yz(0.0)
        d.polygon([(xc - w_body * 0.4, top_y), (xc + w_body * 0.4, top_y), (xc + w_body * 0.45, waist), (xc - w_body * 0.45, waist)], fill=cols[0])
        d.polygon([(xc - w_body * 0.42, waist), (xc + w_body * 0.42, waist), (xc + w_body * 0.62, feet), (xc - w_body * 0.62, feet)], fill=cols[1])
        r = 0.115 * px_per_m
        hc = (xc, Yz(1.53))
        a = (s["face"] - (math.degrees(math.atan2(vx, vy)))) % 360      # 180 = 面向相机
        hair = (78, 58, 44)
        d.ellipse((hc[0] - r, hc[1] - r, hc[0] + r, hc[1] + r), fill=hair)
        if 120 <= a <= 240:
            d.ellipse((hc[0] - r * 0.72, hc[1] - r * 0.45, hc[0] + r * 0.72, hc[1] + r * 0.95), fill=(234, 205, 182))
        elif 45 < a < 135 or 225 < a < 315:
            sgn = 1 if 45 < a < 135 else -1
            fx0 = hc[0] + (r * 0.1 if sgn > 0 else -r * 1.0)
            d.ellipse((fx0, hc[1] - r * 0.4, fx0 + r * 0.9, hc[1] + r * 0.95), fill=(234, 205, 182))
    if s["obst"]:
        o = s["obst"]
        q = project(s, P, o[0], o[1], P["h"])
        if q:
            ow = fw * f * o[2] / q[2] / 24
            d.rectangle((q[0] * fw - ow / 2, 0, q[0] * fw + ow / 2, fh), fill=(150, 140, 125))
    # 三分线与 90% 安全框
    for k in (1, 2):
        d.line([(fw * k / 3, 0), (fw * k / 3, fh)], fill=(255, 255, 255), width=1)
        d.line([(0, fh * k / 3), (fw, fh * k / 3)], fill=(255, 255, 255), width=1)
    mx, my = fw * 0.05, fh * 0.05
    for i in range(0, int(fw - 2 * mx), 8):
        d.line([(mx + i, my), (mx + i + 4, my)], fill=(255, 255, 255)); d.line([(mx + i, fh - my), (mx + i + 4, fh - my)], fill=(255, 255, 255))
    for i in range(0, int(fh - 2 * my), 8):
        d.line([(mx, my + i), (mx, my + i + 4)], fill=(255, 255, 255)); d.line([(fw - mx, my + i), (fw - mx, my + i + 4)], fill=(255, 255, 255))
    return im


def draw_frames(img, x, y, P, fw, fh, gap, cols, captions=True):
    d = ImageDraw.Draw(img)
    labs = [("起", 0.0), ("中", 0.5), ("止", 1.0)]
    for i, (lab, t) in enumerate(labs):
        fx = x + i * (fw + gap)
        img.paste(draw_frame(P, t, fw, fh, cols), (fx, y))
        d.rectangle((fx, y, fx + fw, y + fh), outline=INK, width=2)
        d.rectangle((fx, y, fx + 26, y + 22), fill=VIDEO)
        d.text((fx + 6, y + 2), lab, font=font(14, True), fill=(255, 255, 255))
        if i < 2:
            arrow(d, (fx + fw + 4, y + fh / 2), (fx + fw + gap - 4, y + fh / 2), MUTED, w=2, head=7)
        if captions:
            txt = {"起": P["start"], "中": "运动中", "止": P["end"]}[lab]
            text_block(d, (fx, y + fh + 6), txt, font(13), fw, fill=INK, spacing=1)


def draw_timeline(d, x, y, w, P):
    total = P["dur"]
    hold, mv = P["hold"], P["move_s"]
    segs = [("静止", hold, (205, 200, 188)), ("运镜", mv, CAM), ("静止", hold, (205, 200, 188))]
    cx = x
    for lab, sec, col in segs:
        ww = w * sec / total
        d.rectangle((cx, y, cx + ww, y + 26), fill=col)
        tw = d.textlength(f"{lab} {sec:g}s", font=font(13, True))
        if ww > tw + 6:
            d.text((cx + (ww - tw) / 2, y + 4), f"{lab} {sec:g}s", font=font(13, True), fill=(255, 255, 255) if col == CAM else INK)
        cx += ww
    for k in range(int(total) + 1):
        tx = x + w * k / total
        d.line([(tx, y + 26), (tx, y + 32)], fill=MUTED, width=1)
        d.text((tx - 4, y + 33), f"{k}", font=font(12), fill=MUTED)
    slow = {"24p": 1, "sq60": 2.5, "sq120": 5}.get(P["mode"], 1)
    note = f"实录 {total:g} 秒" + (f"，S&Q 慢放 {slow:g} 倍，成片约 {total * slow:g} 秒" if slow > 1 else "，实时")
    d.text((x, y + 52), note, font=font(15), fill=INK)


FRAME_NOTE = {
    "track_front": "人物大小基本不变，背景向后退。",
    "track_behind": "人物大小基本不变，前方景物迎面而来。",
    "track_side": "人物停在一侧三分线上，背景横向流过。",
    "orbit_quarter": "人物从侧面转到正面，背景在身后横移约 90°。",
    "push_in": "人物略变大，推进幅度很小。",
    "pull_back_tilt_up": "人物变小并下移，画面上方露出拱顶。",
    "tilt_down_reveal": "先是树冠与天空，人物从画面下方升上来。",
    "wipe_reveal": "遮挡物从画面中移开，人物露出。",
    "static_turn": "构图不变，人物由侧脸转向镜头。",
    "static": "构图不变，只有被拨动的物体在动。",
    "static_walk_out": "人物越走越小，走出安全框。",
}


def render_page(shot, meta, outfit, out_path):
    P = params(shot)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 26), shot["id"], font=font(52, True), fill=GREEN)
    tx = 40 + d.textlength(shot["id"], font=font(52, True)) + 16
    d.line([(tx - 8, 34), (tx - 8, 84)], fill=GREEN, width=3)
    title = f"运镜示意 · {P['move']}"
    d.text((tx + 6, 30), title, font=font(40, True), fill=GREEN)
    bx = tx + 6 + d.textlength(title, font=font(40, True)) + 16
    d.rounded_rectangle((bx, 40, bx + 74, 76), radius=6, fill=VIDEO)
    d.text((bx + 10, 44), "短片", font=font(24, True), fill=(255, 255, 255))
    sub = f"{shot.get('title', '')}　{shot.get('lens', '')}　{ {'24p': '24p 实时', 'sq60': 'S&Q 60→24', 'sq120': 'S&Q 120→24（裁 1.52×）'}.get(P['mode'], P['mode']) }"
    d.text((W - 40 - d.textlength(sub, font=font(18)), 52), sub, font=font(18), fill=MUTED)

    y = panel(d, (40, 110, 760, 640), "俯视轨迹（以人物为中心，1 格 = 1 m）", font(24, True))
    draw_top(img, (52, y, 748, 628), P, shot)
    y = panel(d, (780, 110, W - 40, 400), "侧视：机位高度与俯仰", font(24, True))
    draw_side(img, (792, y, W - 52, 390), P)
    y = panel(d, (780, 414, W - 40, 640), "操作要点", font(24, True))
    fmt = {"d": f"{P['d']:g}", "d2": f"{P['d2']:g}", "hold": f"{P['hold']:g}", "move": f"{P['move_s']:g}",
           "tilt0": f"{P['tilt0']:g}", "tilt1": f"{P['tilt1']:g}", "side": "右" if P["side"] == "right" else "左"}
    for k, line in enumerate(HOWTO[P["type"]]):
        d.text((796, y), f"{k + 1}", font=font(16, True), fill=CAM)
        y = text_block(d, (820, y), line.format(**fmt), font(16), W - 40 - 820 - 16, spacing=3) + 4
    y = panel(d, (40, 652, W - 40, 1030), "画面变化（竖幅 9:16，三分线 + 90% 安全框）", font(24, True))
    fw, fh, gap = 150, 267, 34
    draw_frames(img, 60, y, P, fw, fh, gap, outfit_cols(outfit))
    rx = 60 + 3 * fw + 2 * gap + 50
    d.text((rx, y), "时间条", font=font(18, True), fill=GREEN)
    draw_timeline(d, rx, y + 30, W - 70 - rx, P)
    yy = y + 120
    for lab, val in (("起幅", P["start"]), ("落幅", P["end"]), ("画面", FRAME_NOTE[P["type"]]), ("曝光", shot.get("clip", {}).get("exposure", "")),
                     ("ND", shot.get("clip", {}).get("nd", ""))):
        if not val:
            continue
        d.text((rx, yy), lab, font=font(16, True), fill=GREEN)
        yy = text_block(d, (rx + 56, yy), val, font(16), W - 70 - rx - 56, spacing=3) + 6
    d.text((40, H - 32), "运镜示意：距离与机高按分镜估算，三帧按焦段、距离和俯仰角推算人物在画面里的大小与位置，现场以取景器为准。",
           font=font(15), fill=MUTED)
    img.save(out_path, quality=92)
    return out_path


def render_compact(shot, outfit, out_path):
    """手机竖版（核对表用）：俯视轨迹在上，三帧与时间条在下。"""
    P = params(shot)
    Wc = 720
    img = Image.new("RGB", (Wc, 1010), PANEL)
    d = ImageDraw.Draw(img)
    d.text((20, 14), f"{shot['id']}  {P['move']}", font=font(30, True), fill=GREEN)
    d.text((20, 56), f"{shot.get('lens', '')} · {P['mode']} · 实录 {P['dur']:g} s · 1 格 = 1 m", font=font(18), fill=MUTED)
    draw_top(img, (16, 90, Wc - 16, 470), P, shot)
    fw, fh, gap = 196, 348, 26
    draw_frames(img, 20, 490, P, fw, fh, gap, outfit_cols(outfit))
    draw_timeline(d, 20, 900, Wc - 40, P)
    img.save(out_path, quality=90)
    return out_path


LIB_EXAMPLES = {
    "tilt_down_reveal": {"lens": "24mm F4", "cam_dist": 8, "camera": "胸口高度", "clip": {"mode": "24p", "dur_s": 5, "start": "树冠", "end": "背影"}},
    "wipe_reveal": {"lens": "35mm F4", "cam_dist": 3, "camera": "胸口高度", "clip": {"mode": "24p", "dur_s": 4, "start": "柱子虚化", "end": "人物露出"}},
    "track_side": {"lens": "35mm F4", "cam_dist": 3, "camera": "胸口高度", "clip": {"mode": "sq60", "dur_s": 3, "start": "迈步", "end": "停步"}},
    "track_behind": {"lens": "24mm F4", "cam_dist": 3, "camera": "胸口高度", "clip": {"mode": "sq60", "dur_s": 3, "start": "背影迈步", "end": "走到门口"}},
    "track_front": {"lens": "24mm F4", "cam_dist": 3, "camera": "胸口高度", "clip": {"mode": "sq60", "dur_s": 3, "start": "迎面走来", "end": "停步抬头"}},
    "push_in": {"lens": "85mm F4", "cam_dist": 2, "camera": "眼平", "clip": {"mode": "sq120", "dur_s": 2, "start": "手碰物件", "end": "略推近"}},
    "orbit_quarter": {"lens": "50mm F4", "cam_dist": 2, "camera": "眼平", "clip": {"mode": "sq60", "dur_s": 3, "start": "侧面", "end": "正面抬眼"}},
    "static_turn": {"lens": "85mm F4", "cam_dist": 3, "camera": "眼平", "clip": {"mode": "sq120", "dur_s": 2, "start": "侧脸", "end": "回眸"}},
    "static": {"lens": "70mm F4", "cam_dist": 1.2, "camera": "眼平", "kind": "特写", "clip": {"mode": "sq120", "dur_s": 2, "start": "拨动", "end": "摆回"}},
    "pull_back_tilt_up": {"lens": "24mm F4", "cam_dist": 4, "camera": "眼平，从 4 m 退到 8 m", "clip": {"mode": "24p", "dur_s": 5, "start": "背影", "end": "拱顶"}},
    "static_walk_out": {"lens": "35mm F4", "cam_dist": 4, "camera": "胸口高度", "clip": {"mode": "24p", "dur_s": 5, "start": "背影", "end": "走出画"}},
}


def render_library(out_path, outfit=None):
    cols = outfit_cols(outfit or {})
    tw, th = 780, 330
    ncol = 2
    rows = math.ceil(len(ORDER) / ncol)
    img = Image.new("RGB", (40 + ncol * (tw + 20), 110 + rows * (th + 20)), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "运镜库示意", font=font(44, True), fill=GREEN)
    d.text((300, 50), "橙线为相机轨迹（圆点为每秒位置），绿线为人物移动；右侧三帧为起 / 中 / 止的竖幅画面。", font=font(18), fill=MUTED)
    for i, mt in enumerate(ORDER):
        ex = dict(LIB_EXAMPLES[mt]); ex["clip"] = dict(ex["clip"]); ex["clip"]["move_type"] = mt; ex["clip"]["move"] = TYPES[mt][0]
        ex.setdefault("kind", "全身")
        P = params(ex)
        x = 40 + (i % ncol) * (tw + 20); y = 100 + (i // ncol) * (th + 20)
        d.rounded_rectangle((x, y, x + tw, y + th), radius=10, fill=PANEL, outline=LINE, width=2)
        d.text((x + 16, y + 10), TYPES[mt][0], font=font(22, True), fill=GREEN)
        d.text((x + 16, y + 40), f"{ex['lens'].split()[0]} · {ex['clip']['mode']} · {ex['clip']['dur_s']} s", font=font(14), fill=MUTED)
        draw_top(img, (x + 12, y + 64, x + 340, y + th - 12), P, small=True)
        fw, fh, gap = 116, 206, 22
        draw_frames(img, x + 360, y + 40, P, fw, fh, gap, cols, captions=True)
    img.save(out_path, quality=88)
    return out_path


LEGEND = ["橙线：相机轨迹，圆点为每秒位置；空心图标为起点，实心为终点。",
          "绿线：人物移动；圆点上的短线是人物朝向。浅色扇形是终点时的视野。",
          "三帧：起 / 中 / 止的竖幅画面，按焦段、距离、机高和俯仰推算，白线为三分线，虚线为 90% 安全框。",
          "每条起止各停 0.5–1 秒；同一动作最多拍两条。详细做法见各条短片后面的运镜页。"]


def _tile(img, x, y, tw, th, label, sub, P, cols):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x, y, x + tw, y + th), radius=10, fill=PANEL, outline=LINE, width=2)
    d.text((x + 16, y + 10), label, font=font(22, True), fill=GREEN)
    fw, fh, gap = 110, 196, 18
    frames_w = 3 * fw + 2 * gap
    room = tw - frames_w - 50
    f14 = font(14)
    while sub and d.textlength(sub, font=f14) > room:
        sub = sub[:-2] + "…" if not sub.endswith("…") else sub[:-2] + "…"
    d.text((x + 16, y + 40), sub, font=f14, fill=MUTED)
    draw_top(img, (x + 12, y + 64, x + tw - frames_w - 30, y + th - 12), P, small=True)
    draw_frames(img, x + tw - frames_w - 14, y + 40, P, fw, fh, gap, cols, captions=True)


def render_overview(shots, outfit, out_dir, prefix="moves_overview"):
    """本组短片一览：横版（PDF，每页 5 条 + 图例）与竖版（核对表，单列）。返回生成的文件列表。"""
    cols = outfit_cols(outfit or {})
    made = []
    items = []
    for sh in shots:
        P = params(sh)
        c = sh.get("clip", {})
        mode = {"24p": "24p 实时", "sq60": "S&Q 60→24", "sq120": "S&Q 120→24"}.get(P["mode"], P["mode"])
        items.append((f"{sh['id']}  {P['move']}", f"{sh.get('lens', '').split()[0]} · {mode} · 实录 {P['dur']:g} s · {sh.get('title', '')}", P))
    per = 5
    tw, th = 750, 300
    for pg in range(0, len(items), per):
        chunk = items[pg:pg + per]
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((40, 26), "短片一览", font=font(46, True), fill=GREEN)
        d.text((270, 46), f"本组 {len(items)} 条短片的运镜轨迹与画面变化，按游览顺序排列" + (f"（{pg // per + 1}/{math.ceil(len(items) / per)}）" if len(items) > per else ""),
               font=font(18), fill=MUTED)
        for i, (lab, sub, P) in enumerate(chunk):
            _tile(img, 40 + (i % 2) * (tw + 20), 100 + (i // 2) * (th + 12), tw, th, lab, sub, P, cols)
        i = len(chunk)
        x, y = 40 + (i % 2) * (tw + 20), 100 + (i // 2) * (th + 12)
        if i < 6:
            d.rounded_rectangle((x, y, x + tw, y + th), radius=10, fill=PANEL, outline=LINE, width=2)
            d.text((x + 16, y + 12), "看图方法", font=font(22, True), fill=GREEN)
            yy = y + 52
            for k, t in enumerate(LEGEND):
                d.text((x + 16, yy), f"{k + 1}", font=font(16, True), fill=CAM)
                yy = text_block(d, (x + 40, yy), t, font(16), tw - 60, spacing=3) + 8
        d.text((40, H - 32), "短片一览：轨迹与三帧为估算示意，现场以取景器为准。", font=font(15), fill=MUTED)
        f = out_dir / f"{prefix}_{pg // per + 1}.png"
        img.save(f, quality=92)
        made.append(f)
    # 竖版单列（核对表）
    tw2 = 760
    img = Image.new("RGB", (tw2 + 20, 20 + len(items) * (th + 12)), BG)
    for i, (lab, sub, P) in enumerate(items):
        _tile(img, 10, 10 + i * (th + 12), tw2, th, lab, sub, P, cols)
    f = out_dir / f"{prefix}_m.png"
    img.save(f, quality=90)
    made.append(f)
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan")
    ap.add_argument("--out")
    ap.add_argument("--library")
    a = ap.parse_args()
    if a.library:
        print("运镜库：", render_library(a.library))
        return
    plan = Path(a.plan)
    out = Path(a.out or plan / "cards"); out.mkdir(parents=True, exist_ok=True)
    SL = json.loads((plan / "shotlist.json").read_text(encoding="utf-8"))
    outfit = {}
    if (plan / "outfit.json").exists():
        outfit = json.loads((plan / "outfit.json").read_text(encoding="utf-8"))
    for old in [*out.glob("move_*.png"), *out.glob("movem_*.png"), *out.glob("moves_overview_*.png")]:
        old.unlink()
    vids = [s for s in SL["shots"] if s.get("medium") == "video" and s.get("clip")]
    rj = plan / "route.json"
    if rj.exists():                                   # 一览按游览顺序
        order = json.loads(rj.read_text(encoding="utf-8")).get("order", [])
        vids.sort(key=lambda s: order.index(s["id"]) if s["id"] in order else 999)
    for s in vids:
        render_page(s, SL["meta"], outfit, out / f"move_{s['id']}.png")
        render_compact(s, outfit, out / f"movem_{s['id']}.png")
    if vids:
        render_overview(vids, outfit, out)
    print(f"运镜示意：{len(vids)} 页 + 短片一览 → {out}")


if __name__ == "__main__":
    main()
