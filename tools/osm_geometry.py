#!/usr/bin/env python3
"""
osm_geometry.py　从 OpenStreetMap（Overpass）拉取某个坐标周边的建筑、道路、步道、水面、树林、草地、POI，
整理成 basemap.py 能直接渲染的 geometry.json（v2 格式），并顺手渲染 <name>_osm.png / <name>_meta.json。

用法：
  python tools/osm_geometry.py --place "ポーラ美術館" --meters 260 --out plans/x/basemaps --name pola
  python tools/osm_geometry.py --lat 35.25666 --lon 139.02120 --meters 260 --out plans/x/basemaps --name pola
  python tools/osm_geometry.py --lat ... --lon ... --fixture overpass_geom_pola.json ...     # 离线样本
  --extra extra.json   手工补充（OSM 缺失的木栈道、装置点等），格式见 templates/geometry_extra_example.json

数据来源：Overpass API（https://overpass-api.de/），使用政策：低频、带 User-Agent。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from geo_common import geocode, http_json  # noqa: E402
from basemap import Proj, render  # noqa: E402

ROAD_CLS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "living_street"}
PATH_CLS = {"footway", "path", "steps", "pedestrian", "track", "bridleway", "cycleway"}


def overpass_geom(lat, lon, radius, *, fixture=None):
    q = f"""[out:json][timeout:60];
(
  way(around:{radius},{lat},{lon})["building"];
  way(around:{radius},{lat},{lon})["highway"];
  way(around:{radius},{lat},{lon})["natural"];
  way(around:{radius},{lat},{lon})["landuse"];
  way(around:{radius},{lat},{lon})["leisure"];
  way(around:{radius},{lat},{lon})["amenity"];
  way(around:{radius},{lat},{lon})["tourism"];
  way(around:{radius},{lat},{lon})["waterway"];
  way(around:{radius},{lat},{lon})["man_made"];
  node(around:{radius},{lat},{lon})["tourism"];
  node(around:{radius},{lat},{lon})["amenity"];
  node(around:{radius},{lat},{lon})["name"];
  relation(around:{radius},{lat},{lon})["natural"];
  relation(around:{radius},{lat},{lon})["landuse"];
  relation(around:{radius},{lat},{lon})["leisure"];
  relation(around:{radius},{lat},{lon})["building"];
);
out geom;"""
    j = http_json("https://overpass-api.de/api/interpreter", data=("data=" + urllib.parse.quote(q)).encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"},
                  fixture=fixture, timeout=90)
    return j.get("elements", [])


def _pts(geom):
    """Overpass geometry：[{lat,lon}] 或样本里的 [[lat,lon]] 都接受。"""
    out = []
    for p in geom or []:
        if isinstance(p, dict):
            out.append([p["lat"], p["lon"]])
        else:
            out.append([p[0], p[1]])
    return out


def _inside(pt, lat, lon, half_lat, half_lon):
    return abs(pt[0] - lat) <= half_lat and abs(pt[1] - lon) <= half_lon


def build_layers(elements, lat, lon, meters):
    """把 Overpass 元素分层。窗口外的点保留（渲染时自然裁掉），但整块在窗口外的多边形丢弃。"""
    half_lat = meters / 110540 * 0.75
    half_lon = meters / (111320 * __import__("math").cos(__import__("math").radians(lat))) * 0.75
    L = {"wood_fill_all": False, "wood": [], "clearing": [], "grass": [], "water": [], "buildings": [],
         "roads": [], "paths": [], "terraces": [], "points": []}
    seen_building_ids = set()

    def any_inside(pts):
        return any(_inside(p, lat, lon, half_lat, half_lon) for p in pts)

    for e in elements:
        t = e.get("tags", {}) or {}
        if e["type"] == "node":
            if not _inside([e["lat"], e["lon"]], lat, lon, half_lat, half_lon):
                continue
            name = t.get("name") or t.get("amenity") or t.get("tourism")
            kind = "poi" if (t.get("tourism") or t.get("amenity") in ("cafe", "restaurant", "parking", "taxi", "toilets")) else "label"
            L["points"].append({"name": name, "kind": kind, "latlon": [e["lat"], e["lon"]], "tags": {k: v for k, v in t.items() if k in ("amenity", "tourism", "highway", "name", "name:en")}})
            continue
        if e["type"] == "way":
            pts = _pts(e.get("geometry"))
            if len(pts) < 2 or not any_inside(pts):
                continue
            closed = pts[0] == pts[-1]
            if "building" in t or t.get("building:part"):
                if closed and e["id"] not in seen_building_ids:
                    seen_building_ids.add(e["id"])
                    L["buildings"].append({"name": t.get("name", ""), "poly": pts, "osm": f"way/{e['id']}"})
            elif "highway" in t:
                cls = t["highway"]
                if cls in ROAD_CLS:
                    L["roads"].append({"cls": cls, "line": pts, "name": t.get("name", "")})
                elif cls in PATH_CLS:
                    L["paths"].append({"cls": cls, "line": pts, "bridge": t.get("bridge") == "yes", "name": t.get("name", "")})
            elif t.get("natural") in ("wood", "forest") or t.get("landuse") == "forest":
                if closed:
                    L["wood"].append(pts)
            elif t.get("natural") == "water" or t.get("waterway") in ("riverbank", "dock") or t.get("landuse") in ("reservoir", "basin"):
                if closed:
                    L["water"].append(pts)
            elif t.get("landuse") in ("grass", "meadow", "village_green", "recreation_ground") or t.get("leisure") in ("park", "garden", "pitch") or t.get("natural") in ("grassland", "heath", "scrub"):
                if closed:
                    L["grass"].append(pts)
            elif t.get("amenity") == "parking" and closed:
                L["terraces"].append(pts)
            elif t.get("man_made") in ("pier", "bridge") and not closed:
                L["paths"].append({"cls": "boardwalk", "line": pts, "bridge": True, "name": t.get("name", "")})
            continue
        if e["type"] == "relation":
            members = e.get("members", []) or []
            outers = [_pts(m.get("geometry")) for m in members if m.get("role") == "outer"]
            inners = [_pts(m.get("geometry")) for m in members if m.get("role") == "inner"]
            outers = [o for o in outers if len(o) >= 3]
            inners = [i for i in inners if len(i) >= 3]
            if t.get("natural") in ("wood", "forest") or t.get("landuse") == "forest":
                if outers and any(any_inside(o) for o in outers):
                    L["wood"].extend(outers)
                elif inners and any(any_inside(i) for i in inners):
                    # 外环整块在窗口外、内环在窗口内：说明窗口整体处于林地，内环是林中空地
                    L["wood_fill_all"] = True
                L["clearing"].extend(i for i in inners if any_inside(i))
            elif t.get("natural") == "water":
                L["water"].extend(o for o in outers if any_inside(o))
            elif t.get("leisure") in ("park", "garden") or t.get("landuse") in ("grass", "meadow"):
                L["grass"].extend(o for o in outers if any_inside(o))
            elif t.get("type") == "building" or "building" in t:
                for m in members:
                    if m.get("role") == "outline" and m.get("ref") not in seen_building_ids:
                        pts = _pts(m.get("geometry"))
                        if len(pts) >= 3 and any_inside(pts):
                            seen_building_ids.add(m.get("ref"))
                            L["buildings"].append({"name": t.get("name", ""), "poly": pts, "osm": f"relation/{e['id']}"})
    return L


def merge_extra(L, extra: dict):
    """手工补充：{"paths":[{"cls":"boardwalk","line":[[lat,lon],...],"name":"..."}], "points":[...], "water":[...], "buildings":[...]}"""
    for k, v in extra.items():
        if k in L and isinstance(L[k], list):
            L[k].extend(v)
        elif k == "note":
            L["extra_note"] = v
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--place")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--meters", type=float, default=260, help="底图覆盖宽度（米）")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="main")
    ap.add_argument("--fixture", help="tools/fixtures 下的离线 Overpass 样本文件名")
    ap.add_argument("--extra", help="手工补充几何 JSON")
    a = ap.parse_args()
    if a.lat is None or a.lon is None:
        if not a.place:
            raise SystemExit("需要 --place 或 --lat/--lon")
        g = geocode(a.place)
        a.lat, a.lon = g["lat"], g["lon"]
        print("geocode:", g["display_name"], a.lat, a.lon)
    radius = int(a.meters * 0.8)
    elements = overpass_geom(a.lat, a.lon, radius, fixture=a.fixture)
    L = build_layers(elements, a.lat, a.lon, a.meters)
    if a.extra:
        L = merge_extra(L, json.load(open(a.extra, encoding="utf-8")))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    geo = {"name": a.name, "place": a.place, "center": [a.lat, a.lon], "meters": a.meters,
           "source": "OpenStreetMap contributors (ODbL) via Overpass API" + ("（离线样本）" if a.fixture else ""),
           "counts": {k: (len(v) if isinstance(v, list) else v) for k, v in L.items()}, "layers": L}
    (out / f"{a.name}_geometry.json").write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
    proj = Proj(a.lat, a.lon, a.size, a.meters)
    img = render(L, proj)
    img.save(out / f"{a.name}_osm.png")
    json.dump(proj.to_dict(), open(out / f"{a.name}_meta.json", "w"))
    print(f"{a.name}_geometry.json", geo["counts"])
    print(f"{a.name}_osm.png", img.size, f"{proj.mpp:.3f} m/px")


if __name__ == "__main__":
    main()
