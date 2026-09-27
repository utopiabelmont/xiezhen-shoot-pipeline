#!/usr/bin/env python3
"""
basemap.py　把园区几何（geometry.json）渲染成干净的俯视底图（北在上，无文字），
供 codex-imagegen 的 edit 模式重绘成手绘风格；同时输出 <name>_meta.json（比例尺与中心），
make_cards.py 用它把经纬度换算成像素、在风格化底图上叠加准确的站位与光向。

几何文件两种格式都能读：
  v2（osm_geometry.py 生成）：{"center":[lat,lon], "layers": {...}}
  v1（早期手工整理的 hakone 格式）：{"wood","water","footways","buildings",...}

用法：
  python tools/basemap.py --geometry plans/x/basemaps/pola_geometry.json --out plans/x/basemaps --name pola --size 1024 --meters 260
  python tools/basemap.py --plan plans/hakone-0928 --center 35.26615,139.01745 --size 1024 --meters 130   # v1 兼容
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

PAPER = (232, 226, 210)
WOOD = (150, 176, 130)
GRASS = (196, 208, 172)
CLEARING = (204, 214, 180)
WATER = (168, 200, 215)
WATER_EDGE = (120, 160, 185)
PATH = (205, 198, 182)
ROAD = (190, 186, 176)
BUILDING = (236, 228, 208)
BUILDING_EDGE = (150, 140, 120)
TERRACE = (222, 210, 186)
BRIDGE = (245, 242, 232)
BRIDGE_EDGE = (190, 185, 200)
POINT = (120, 110, 100)

ROAD_WIDTH = {"motorway": 22, "trunk": 20, "primary": 18, "secondary": 16, "tertiary": 14,
              "unclassified": 12, "residential": 12, "service": 9, "living_street": 10}
PATH_WIDTH = {"footway": 7, "path": 6, "steps": 7, "pedestrian": 9, "track": 7, "bridleway": 6, "cycleway": 7,
              "boardwalk": 8, "approx": 6}


class Proj:
    def __init__(self, lat0, lon0, size, meters):
        self.lat0, self.lon0, self.size = lat0, lon0, size
        self.mpp = meters / size                       # 米/像素
        self.kx = 111320 * math.cos(math.radians(lat0))  # 米/经度
        self.ky = 110540                                 # 米/纬度

    def xy(self, lat, lon):
        dx = (lon - self.lon0) * self.kx / self.mpp
        dy = (lat - self.lat0) * self.ky / self.mpp
        return self.size / 2 + dx, self.size / 2 - dy

    def to_dict(self):
        return {"lat0": self.lat0, "lon0": self.lon0, "size": self.size, "m_per_px": self.mpp}


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def legacy_to_layers(geo: dict) -> dict:
    """v1 hakone 手工格式 → v2 layers。"""
    L = {"wood": [geo["wood"]] if geo.get("wood") else [], "water": [geo["water"]] if geo.get("water") else [],
         "grass": [], "clearing": [], "buildings": [], "roads": [], "paths": [], "points": [], "terraces": []}
    for fw in geo.get("footways", []):
        L["paths"].append({"cls": "footway", "line": fw})
    if geo.get("road_north"):
        L["roads"].append({"cls": "unclassified", "line": geo["road_north"]})
    for name, poly in geo.get("buildings", {}).items():
        L["buildings"].append({"name": name, "poly": poly})
    if geo.get("terrace"):
        L["terraces"].append(geo["terrace"])
    if geo.get("corridor"):
        L["paths"].append({"cls": "bridge", "line": geo["corridor"], "bridge": True})
    for k, ll in geo.get("points", {}).items():
        L["points"].append({"name": k, "kind": "chandelier" if k == "chandelier" else "poi", "latlon": ll})
    L["lawn_hull"] = True   # 用步道凸包外扩作草地大形
    return L


def load_layers(path: Path) -> tuple[dict, dict]:
    geo = json.load(open(path, encoding="utf-8"))
    if "layers" in geo:
        return geo["layers"], geo
    return legacy_to_layers(geo), geo


def render(L: dict, proj: Proj) -> Image.Image:
    img = Image.new("RGB", (proj.size, proj.size), PAPER)
    d = ImageDraw.Draw(img)
    P = lambda pts: [proj.xy(a, b) for a, b in pts]
    if L.get("wood_fill_all"):
        d.rectangle((0, 0, proj.size, proj.size), fill=WOOD)
    for poly in L.get("wood", []):
        if len(poly) >= 3:
            d.polygon(P(poly), fill=WOOD)
    for poly in L.get("clearing", []):
        if len(poly) >= 3:
            d.polygon(P(poly), fill=CLEARING)
    if L.get("lawn_hull"):
        pts = [proj.xy(a, b) for p in L.get("paths", []) for a, b in p["line"]]
        hull = convex_hull(pts)
        if len(hull) >= 3:
            cx = sum(x for x, _ in hull) / len(hull); cy = sum(y for _, y in hull) / len(hull)
            hull = [(cx + (x - cx) * 1.25, cy + (y - cy) * 1.25) for x, y in hull]
            d.polygon(hull, fill=GRASS)
    for poly in L.get("grass", []):
        if len(poly) >= 3:
            d.polygon(P(poly), fill=GRASS)
    for poly in L.get("water", []):
        if len(poly) >= 3:
            d.polygon(P(poly), fill=WATER, outline=WATER_EDGE)
    for r in L.get("roads", []):
        if len(r["line"]) >= 2:
            d.line(P(r["line"]), fill=ROAD, width=ROAD_WIDTH.get(r.get("cls"), 12), joint="curve")
    for p in L.get("paths", []):
        if len(p["line"]) < 2:
            continue
        if p.get("bridge"):
            d.line(P(p["line"]), fill=BRIDGE, width=10, joint="curve")
            d.line(P(p["line"]), fill=BRIDGE_EDGE, width=2, joint="curve")
        else:
            d.line(P(p["line"]), fill=PATH, width=PATH_WIDTH.get(p.get("cls"), 7), joint="curve")
    for poly in L.get("terraces", []):
        if len(poly) >= 3:
            d.polygon(P(poly), fill=TERRACE, outline=BUILDING_EDGE)
    for b in L.get("buildings", []):
        if len(b["poly"]) >= 3:
            d.polygon(P(b["poly"]), fill=BUILDING, outline=BUILDING_EDGE)
    for pt in L.get("points", []):
        x, y = proj.xy(*pt["latlon"])
        if pt.get("kind") == "chandelier":
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(240, 240, 250), outline=(90, 80, 70))
        elif pt.get("kind") in ("poi", "landmark"):
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=POINT, outline=(90, 80, 70))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geometry", help="v2 geometry.json（含 center）")
    ap.add_argument("--plan", help="v1 兼容：读 <plan>/osm_geometry.json，输出到 <plan>/basemap_*.png")
    ap.add_argument("--center", help="lat,lon（v1 必填；v2 缺省用 geometry 里的 center）")
    ap.add_argument("--out", help="输出目录（v2）")
    ap.add_argument("--name", default="main", help="底图名（v2）：输出 <name>_osm.png / <name>_meta.json")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--meters", type=float, default=200, help="画幅覆盖的实际宽度（米）")
    a = ap.parse_args()
    if a.geometry:
        L, geo = load_layers(Path(a.geometry))
        lat0, lon0 = (float(x) for x in a.center.split(",")) if a.center else geo["center"]
        out = Path(a.out or Path(a.geometry).parent); out.mkdir(parents=True, exist_ok=True)
        png, meta = out / f"{a.name}_osm.png", out / f"{a.name}_meta.json"
    else:
        if not (a.plan and a.center):
            raise SystemExit("v1 模式需要 --plan 与 --center")
        L, geo = load_layers(Path(a.plan) / "osm_geometry.json")
        lat0, lon0 = (float(x) for x in a.center.split(","))
        png, meta = Path(a.plan) / "basemap_osm.png", Path(a.plan) / "basemap_meta.json"
    proj = Proj(lat0, lon0, a.size, a.meters)
    img = render(L, proj)
    img.save(png)
    json.dump(proj.to_dict(), open(meta, "w"))
    print(png.name, img.size, f"{proj.mpp:.3f} m/px")


if __name__ == "__main__":
    main()
