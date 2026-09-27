#!/usr/bin/env python3
"""
trip.py　一日多景点的行程页：起点、各景点、点间交通、到达/离开时刻，画成小抄 PDF 的「行程页」。

  python tools/trip.py --plan plans/<plan> --out plans/<plan>/cards

输入 plans/<plan>/trip.json（Claude 按官网班次 / NAVITIME / 小红书攻略填）：
{
 "title": "箱根一日：玻璃之森 + Pola",
 "date": "2026-09-28",
 "stops": [
  {"name": "箱根湯本駅", "latlon": [35.2320, 139.1057], "role": "origin", "leave": "12:38"},
  {"name": "箱根ガラスの森美術館", "latlon": [35.2662, 139.0175], "plan": "hakone-0928-v3", "arrive": "13:00", "leave": "17:00", "note": "主拍摄地，14 站，路线页见下"},
  {"name": "ポーラ美術館", "latlon": [35.2574, 139.0210], "arrive": "17:10", "leave": "17:40", "optional": true, "note": "雨天备选 20"},
  {"name": "箱根湯本駅", "latlon": [35.2320, 139.1057], "role": "end", "arrive": "18:20"}
 ],
 "legs": [
  {"from": 0, "to": 1, "mode": "bus", "line": "箱根登山バス 桃源台線[T]", "minutes": 22, "depart": "12:38", "arrive": "13:00", "source": "NAVITIME 2026-09-27"},
  ...
 ],
 "sources": ["..."]
}
输出：trip.md 与 cards/trip_01.png（左：按真实经纬度的示意地图，直线连接并标交通方式与分钟；右：时刻表）。
点间直线距离按经纬度算；道路距离没有路网时按直线 × 1.3 估算，标「估」。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_cards import W, H, BG, GREEN, INK, MUTED, PANEL, LINE, font, panel, text_block  # noqa: E402

MODE = {"bus": "巴士", "train": "电车", "walk": "步行", "taxi": "出租车", "car": "自驾", "ropeway": "缆车", "ship": "船"}
ACCENT = (176, 98, 40)


def meters(a, b):
    kx = 111320 * math.cos(math.radians((a[0] + b[0]) / 2)); ky = 110540
    return math.hypot((a[1] - b[1]) * kx, (a[0] - b[0]) * ky)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    plan = Path(a.plan); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    T = json.loads((plan / "trip.json").read_text(encoding="utf-8"))
    stops, legs = T["stops"], T.get("legs", [])
    for lg in legs:
        lg["km"] = round(meters(stops[lg["from"]]["latlon"], stops[lg["to"]]["latlon"]) / 1000, 1)

    md = [f"# 行程 · {T.get('title','')} {T.get('date','')}", "", "| 序 | 地点 | 到达 | 离开 | 备注 |", "|---|---|---|---|---|"]
    for i, s in enumerate(stops):
        md.append(f"| {i+1} | {s['name']}{'（备选）' if s.get('optional') else ''} | {s.get('arrive','')} | {s.get('leave','')} | {s.get('note','')} |")
    md += ["", "| 段 | 方式 | 线路 | 发 | 到 | 分钟 | 直线 km | 来源 |", "|---|---|---|---|---|---|---|---|"]
    for lg in legs:
        md.append(f"| {stops[lg['from']]['name']} → {stops[lg['to']]['name']} | {MODE.get(lg.get('mode',''), lg.get('mode',''))} | {lg.get('line','')} | {lg.get('depart','')} | {lg.get('arrive','')} | {lg.get('minutes','')} | {lg['km']} | {lg.get('source','')} |")
    if T.get("sources"):
        md += ["", "来源：" + "；".join(T["sources"])]
    (plan / "trip.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    f_title, f_h, f_s, f_t = font(44, True), font(24, True), font(18), font(15)
    d.text((40, 26), "行程", font=font(52, True), fill=GREEN)
    d.line([(158, 34), (158, 84)], fill=GREEN, width=3)
    d.text((176, 30), T.get("title", "一日行程"), font=f_title, fill=GREEN)
    d.text((W - 40 - d.textlength(T.get("date", ""), font=f_s), 52), T.get("date", ""), font=f_s, fill=MUTED)

    # 左：示意地图（真实经纬度等比，北在上）
    mx0, my0, mx1, my1 = 40, 110, 900, H - 60
    d.rounded_rectangle((mx0, my0, mx1, my1), radius=10, fill=(236, 233, 222), outline=LINE)
    lats = [s["latlon"][0] for s in stops]; lons = [s["latlon"][1] for s in stops]
    lat0, lon0 = (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2
    kx = 111320 * math.cos(math.radians(lat0)); ky = 110540
    xs = [(s["latlon"][1] - lon0) * kx for s in stops]; ys = [(s["latlon"][0] - lat0) * ky for s in stops]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 500) * 1.35
    sc = min(mx1 - mx0, my1 - my0) / span
    cx, cy = (mx0 + mx1) / 2, (my0 + my1) / 2
    P = [(cx + x * sc, cy - y * sc) for x, y in zip(xs, ys)]
    # 比例尺
    for km in (10, 5, 2, 1, 0.5):
        if km * 1000 * sc < (mx1 - mx0) * 0.4:
            break
    d.line([(mx0 + 20, my1 - 24), (mx0 + 20 + km * 1000 * sc, my1 - 24)], fill=INK, width=3)
    d.text((mx0 + 20, my1 - 46), f"{km} km", font=f_t, fill=INK)
    d.rectangle((mx1 - 34, my0 + 6, mx1 - 6, my0 + 46), fill=(255, 255, 255))
    d.line([(mx1 - 20, my0 + 42), (mx1 - 20, my0 + 20)], fill=MUTED, width=2); d.text((mx1 - 26, my0 + 26), "北", font=f_t, fill=MUTED)
    for lg in legs:
        p0, p1 = P[lg["from"]], P[lg["to"]]
        n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 14))
        for i in range(0, n, 2):
            q0 = (p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n)
            q1 = (p0[0] + (p1[0] - p0[0]) * (i + 1) / n, p0[1] + (p1[1] - p0[1]) * (i + 1) / n)
            d.line([q0, q1], fill=ACCENT, width=4)
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        lab = f"{MODE.get(lg.get('mode',''), lg.get('mode',''))} {lg.get('minutes','?')} min · {lg['km']} km"
        tw = d.textlength(lab, font=f_t)
        d.rectangle((mid[0] - tw / 2 - 4, mid[1] - 10, mid[0] + tw / 2 + 4, mid[1] + 10), fill=(255, 255, 255))
        d.text((mid[0] - tw / 2, mid[1] - 9), lab, font=f_t, fill=ACCENT)
    drawn = {}
    for i, (s, p) in enumerate(zip(stops, P)):
        key = (round(s["latlon"][0], 4), round(s["latlon"][1], 4))
        if key in drawn:                                  # 同一地点（起点=终点）合并成一个圆点，标 1·4
            j = drawn[key]; q = P[j]
            lab = f"{j+1}·{i+1}"; tw = d.textlength(lab, font=font(14, True))
            d.ellipse((q[0] - 18, q[1] - 14, q[0] + 18, q[1] + 14), fill=INK, outline=(255, 255, 255), width=3)
            d.text((q[0] - tw / 2, q[1] - 9), lab, font=font(14, True), fill=(255, 255, 255))
            continue
        drawn[key] = i
        col = MUTED if s.get("optional") else (GREEN if s.get("plan") else INK)
        d.ellipse((p[0] - 14, p[1] - 14, p[0] + 14, p[1] + 14), fill=col, outline=(255, 255, 255), width=3)
        lab = str(i + 1); tw = d.textlength(lab, font=font(16, True))
        d.text((p[0] - tw / 2, p[1] - 10), lab, font=font(16, True), fill=(255, 255, 255))
        name = s["name"] + ("（备选）" if s.get("optional") else "")
        tw = d.textlength(name, font=f_s)
        nx = min(max(p[0] + 18, mx0 + 8), mx1 - tw - 8); ny = min(max(p[1] - 12, my0 + 8), my1 - 30)
        d.rectangle((nx - 3, ny - 2, nx + tw + 3, ny + 22), fill=(255, 255, 255)); d.text((nx, ny), name, font=f_s, fill=col)

    # 右：时刻表
    rx0, rx1 = 930, W - 40
    y = panel(d, (rx0, 110, rx1, 620), "地点与时刻", f_h)
    for i, s in enumerate(stops):
        d.text((rx0 + 12, y), f"{i+1}", font=font(15, True), fill=GREEN)
        d.text((rx0 + 40, y), s["name"] + ("（备选）" if s.get("optional") else ""), font=f_s, fill=INK)
        tt = f"{s.get('arrive','')}{' → ' if s.get('arrive') and s.get('leave') else ''}{s.get('leave','')}"
        d.text((rx1 - 14 - d.textlength(tt, font=f_s), y), tt, font=f_s, fill=INK)
        y += 26
        if s.get("note"):
            y = text_block(d, (rx0 + 40, y), s["note"], font(13), rx1 - rx0 - 60, fill=MUTED, spacing=1) + 4
    y = panel(d, (rx0, 634, rx1, 900), "点间交通", f_h)
    for lg in legs:
        line = f"{stops[lg['from']]['name']} → {stops[lg['to']]['name']}：{MODE.get(lg.get('mode',''), lg.get('mode',''))} {lg.get('line','')} {lg.get('depart','')}发 {lg.get('arrive','')}到，{lg.get('minutes','?')} 分钟"
        y = text_block(d, (rx0 + 12, y), line, f_t, rx1 - rx0 - 24, spacing=2)
        if lg.get("note"):
            y = text_block(d, (rx0 + 12, y), lg["note"], font(13), rx1 - rx0 - 24, fill=MUTED, spacing=1)
        y += 4
    y = panel(d, (rx0, 914, rx1, H - 60), "来源", f_h)
    text_block(d, (rx0 + 12, y), "；".join(T.get("sources", [])) or "（trip.json 未填 sources）", font(13), rx1 - rx0 - 24, fill=MUTED, spacing=2)
    d.text((40, H - 42), "行程页：地点按真实经纬度等比示意，连线为直线不代表道路；班次以出发当天查询为准。", font=f_t, fill=MUTED)
    img.save(out / "trip_01.png", quality=92)
    print("行程页：", out / "trip_01.png", plan / "trip.md")


if __name__ == "__main__":
    main()
