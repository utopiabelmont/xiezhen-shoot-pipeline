#!/usr/bin/env python3
"""
nav.py　分镜站位的谷歌地图步行导航链接（1.9.0 起）。

每条分镜都能算出一个「走过去的目标点」：
  - 缺省用 `subject_latlon`（人物站位）；
  - 分镜里写 `walk_to` 时按它来：
      {"to": "camera"}                       → 导航到机位（由 subject_latlon + cam_bearing + cam_dist 推算，长焦远机位用）
      {"latlon": [lat, lon], "label": "..."} → 导航到指定点（例如店门、出站口）
      {"place_id": "ChIJ...", "label": "..."}→ 同时带 Google 地点 ID（店内分镜导航到店铺本身，楼层写在 label）
链接格式用 Google Maps URLs（https://developers.google.com/maps/documentation/urls/get-started）：
  https://www.google.com/maps/dir/?api=1&destination=<lat>,<lon>&travelmode=walking[&destination_place_id=<id>]
手机点开直接进入步行导航；电脑上打开是路线规划页。

用法（自检）：python tools/nav.py --plan plans/<plan>     → 列出每条分镜的导航目标与链接
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from urllib.parse import urlencode

R_EARTH = 6371008.8


def offset_latlon(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    """从 (lat, lon) 沿方位角 bearing（正北 0，顺时针）走 dist 米后的坐标（小范围球面近似）。"""
    b = math.radians(bearing_deg)
    dlat = dist_m * math.cos(b) / R_EARTH
    dlon = dist_m * math.sin(b) / (R_EARTH * math.cos(math.radians(lat)))
    return lat + math.degrees(dlat), lon + math.degrees(dlon)


def maps_url(lat: float, lon: float, place_id: str | None = None, mode: str = "walking") -> str:
    q = {"api": "1", "destination": f"{lat:.6f},{lon:.6f}", "travelmode": mode}
    if place_id:
        q["destination_place_id"] = place_id
    return "https://www.google.com/maps/dir/?" + urlencode(q)


def camera_latlon(shot: dict) -> tuple[float, float] | None:
    ll = shot.get("subject_latlon")
    if not ll or shot.get("cam_bearing") is None or shot.get("cam_dist") is None:
        return None
    return offset_latlon(ll[0], ll[1], float(shot["cam_bearing"]), float(shot["cam_dist"]))


def nav_target(shot: dict) -> dict | None:
    """返回 {"url", "label", "latlon", "to"}；没有坐标时返回 None。"""
    w = shot.get("walk_to") or {}
    to = w.get("to", "subject")
    ll = w.get("latlon")
    if ll is None:
        if to == "camera":
            ll = camera_latlon(shot)
        else:
            ll = shot.get("subject_latlon")
    if not ll:
        return None
    lat, lon = float(ll[0]), float(ll[1])
    default_label = {"camera": "机位（摄影者站位）", "subject": "人物站位"}.get(to, "目标点")
    if shot.get("indoor") and not w:
        default_label = "室内站位（导航到所在建筑）"
    return {"url": maps_url(lat, lon, w.get("place_id")), "label": w.get("label") or default_label,
            "latlon": [round(lat, 6), round(lon, 6)], "to": to}


def stop_target(stop: dict, shots_by_id: dict) -> dict | None:
    """路线停留点的导航目标：站内第一条分镜的目标（停留点自己写 walk_to 时优先）。"""
    if stop.get("walk_to"):
        return nav_target({"walk_to": stop["walk_to"], "subject_latlon": stop["walk_to"].get("latlon")})
    for sid in stop.get("shots", []):
        s = shots_by_id.get(sid)
        if s:
            t = nav_target(s)
            if t:
                return t
    return None


def add_pdf_links(pdf_path: Path, page_pngs: list[Path], links_json: Path, dpi: int = 150) -> int:
    """给 PIL 拼出来的 PDF 补上可点击的链接（PIL 存 PDF 不带链接）。
    links_json：{"card_01.png": [[x0, y0, x1, y1, url], ...]}，坐标是卡片 PNG 的像素。需要 pypdf，没装时跳过。"""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Link
    except Exception:
        print("未安装 pypdf：PDF 不加可点击链接（二维码仍可扫）。安装：pip install pypdf")
        return 0
    if not links_json.exists():
        return 0
    links = json.loads(links_json.read_text(encoding="utf-8"))
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append(reader)
    k = 72.0 / dpi
    n = 0
    for i, png in enumerate(page_pngs):
        if i >= len(writer.pages):
            break
        page_h = float(writer.pages[i].mediabox.height)
        for x0, y0, x1, y1, url in links.get(Path(png).name, []):
            rect = (x0 * k, page_h - y1 * k, x1 * k, page_h - y0 * k)
            writer.add_annotation(page_number=i, annotation=Link(rect=rect, url=url))
            n += 1
    tmp = pdf_path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    tmp.replace(pdf_path)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    a = ap.parse_args()
    plan = json.load(open(Path(a.plan) / "shotlist.json", encoding="utf-8"))
    for s in plan["shots"]:
        t = nav_target(s)
        print(s["id"], s["title"], "→", (f"{t['label']} {t['latlon']}\n    {t['url']}" if t else "无坐标"))


if __name__ == "__main__":
    main()
