#!/usr/bin/env python3
"""
spots.py　真实景点 → 地理编码、周边可拍点（OSM）、公开照片分布（Wikimedia Commons）、网页调研清单。

用法：
  python tools/spots.py --place "箱根ガラスの森美術館" --radius 1500 --out plans/hakone-1003
  python tools/spots.py --lat 35.2662 --lon 139.0177 --place "箱根玻璃之森" --out plans/x
  --fixture 用离线样本（测试用）

产物：spots.md、spots.json
数据源（都不需要密钥）：
  Nominatim  地理编码（OSM）            https://nominatim.org/release-docs/latest/api/Search/
  Overpass   周边 POI（OSM）            https://overpass-api.de/
  Commons    带坐标的公开照片（看别人在哪拍） https://commons.wikimedia.org/w/api.php
备注：小红书、Instagram、Google Maps 照片没有公开免费接口；这一层由 Claude 在会话内用网页搜索完成，
     本脚本末尾给出应搜索的关键词清单。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo_common import bearing, compass, geocode, haversine_m, http_json  # noqa: E402

CATS = {
    ("tourism", "viewpoint"): "观景点", ("tourism", "attraction"): "景点", ("tourism", "museum"): "美术馆/博物馆",
    ("tourism", "gallery"): "画廊", ("tourism", "artwork"): "公共艺术", ("tourism", "hotel"): "酒店", ("tourism", "hostel"): "旅舍",
    ("amenity", "cafe"): "咖啡馆", ("leisure", "park"): "公园", ("leisure", "garden"): "庭园", ("historic", "*"): "历史建筑",
    ("man_made", "bridge"): "桥", ("natural", "water"): "水面", ("natural", "wood"): "树林",
}
PHOTO_PRIORITY = ["观景点", "景点", "公共艺术", "庭园", "公园", "美术馆/博物馆", "画廊", "桥", "水面", "咖啡馆", "历史建筑", "树林", "酒店", "旅舍"]


def overpass(lat, lon, radius, *, fixture=False) -> list[dict]:
    q = (f'[out:json][timeout:25];('
         f'nwr["tourism"](around:{radius},{lat},{lon});'
         f'nwr["amenity"="cafe"](around:{radius},{lat},{lon});'
         f'nwr["leisure"~"park|garden"](around:{radius},{lat},{lon});'
         f'nwr["historic"](around:{radius},{lat},{lon});'
         f'nwr["tourism"="artwork"](around:{radius},{lat},{lon});'
         f'nwr["man_made"="bridge"](around:{radius},{lat},{lon});'
         f');out center tags 80;')
    j = http_json("https://overpass-api.de/api/interpreter", data=("data=" + urllib.parse.quote(q)).encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"},
                  fixture="overpass.json" if fixture else None, timeout=60)
    out = []
    for e in j.get("elements", []):
        t = e.get("tags", {})
        la = e.get("lat") or e.get("center", {}).get("lat")
        lo = e.get("lon") or e.get("center", {}).get("lon")
        if la is None:
            continue
        cat = None
        for (k, v), label in CATS.items():
            if t.get(k) and (v == "*" or t.get(k) == v):
                cat = label
                break
        if not cat:
            cat = t.get("tourism") or t.get("amenity") or t.get("leisure") or t.get("historic") or "其他"
        out.append({"name": t.get("name") or t.get("name:en") or "(无名)", "name_en": t.get("name:en", ""),
                    "cat": cat, "lat": la, "lon": lo, "dist_m": round(haversine_m(lat, lon, la, lo)),
                    "bearing": round(bearing(lat, lon, la, lo)), "osm": f"{e['type']}/{e['id']}"})
    out.sort(key=lambda x: (PHOTO_PRIORITY.index(x["cat"]) if x["cat"] in PHOTO_PRIORITY else 99, x["dist_m"]))
    return out


def commons(lat, lon, radius, *, fixture=False, limit=30) -> list[dict]:
    url = (f"https://commons.wikimedia.org/w/api.php?action=query&list=geosearch&gscoord={lat}%7C{lon}"
           f"&gsradius={min(radius, 10000)}&gslimit={limit}&gsnamespace=6&gsprimary=all&format=json")
    j = http_json(url, fixture="commons_geosearch.json" if fixture else None)
    rows = []
    for g in j.get("query", {}).get("geosearch", []):
        title = g["title"]
        rows.append({"title": title.replace("File:", ""), "dist_m": round(g["dist"]), "lat": g["lat"], "lon": g["lon"],
                     "bearing": round(bearing(lat, lon, g["lat"], g["lon"])),
                     "url": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title),
                     "thumb": "https://commons.wikimedia.org/w/index.php?title=Special:FilePath/"
                              + urllib.parse.quote(title.replace("File:", "")) + "&width=800"})
    return rows


def research_queries(place: str, lat: float, lon: float) -> dict:
    return {
        "日文": [f"{place} 撮影スポット", f"{place} 写真映え", f"{place} 見どころ 庭園", f"{place} 紅葉 見頃 OR ススキ 見頃",
               f"{place} ポートレート 撮影 許可"],
        "中文": [f"{place} 拍照 机位", f"{place} 出片 攻略", f"{place} 人像 写真 小红书"],
        "英文": [f"{place} photo spots", f"{place} best time to visit photography", f"{place} instagram spots"],
        "官方与规则": [f"{place} 公式サイト（見どころ／庭園／撮影に関する注意）", f"{place} 三脚 禁止 OR 撮影 禁止"],
        "地图": [f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
               f"https://www.openstreetmap.org/#map=17/{lat}/{lon}"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--radius", type=int, default=1500, help="搜索半径（米）")
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.lat is None or a.lon is None:
        if not a.place:
            sys.exit("需要 --place 或 --lat/--lon")
        g = geocode(a.place, fixture=a.fixture)
        a.lat, a.lon, place, geo_note = g["lat"], g["lon"], g["name"], g["display_name"]
    else:
        place, geo_note = a.place or f"{a.lat:.4f},{a.lon:.4f}", ""

    pois = overpass(a.lat, a.lon, a.radius, fixture=a.fixture)
    photos = commons(a.lat, a.lon, a.radius, fixture=a.fixture)
    queries = research_queries(place, a.lat, a.lon)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = {"place": place, "geocode": geo_note, "lat": a.lat, "lon": a.lon, "radius_m": a.radius,
            "pois": pois, "commons_photos": photos, "research_queries": queries,
            "generated": dt.datetime.now().isoformat(timespec="seconds"), "fixture": a.fixture}
    (out / "spots.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# 出片点调研　{place}", "", f"- 坐标 {a.lat:.5f}, {a.lon:.5f}" + (f"　（{geo_note}）" if geo_note else ""),
         f"- 半径 {a.radius} m　数据：OSM/Overpass {len(pois)} 个 POI，Commons {len(photos)} 张带坐标照片"
         + ("　（离线样本）" if a.fixture else ""), "",
         "## 周边可拍点（OSM）", "", "| 类别 | 名称 | 距离 | 方向 | 坐标 |", "|---|---|---|---|---|"]
    for p in pois:
        nm = p["name"] + (f"（{p['name_en']}）" if p["name_en"] and p["name_en"] != p["name"] else "")
        L.append(f"| {p['cat']} | {nm} | {p['dist_m']} m | {compass(p['bearing'])} {p['bearing']}° | {p['lat']:.5f},{p['lon']:.5f} |")
    L += ["", "## 别人在哪里拍（Wikimedia Commons 带坐标照片）", "",
          "看缩略图能直接判断常见构图与季节；标题里的 rain / night / November 之类是有用的时段线索。", "",
          "| 距离 | 方向 | 文件 | 缩略图 |", "|---|---|---|---|"]
    for ph in photos:
        L.append(f"| {ph['dist_m']} m | {compass(ph['bearing'])} | [{ph['title']}]({ph['url']}) | {ph['thumb']} |")
    L += ["", "## 网页调研清单（由 Claude 在会话内用 WebSearch/WebFetch 完成）", ""]
    for k, qs in queries.items():
        L.append(f"**{k}**")
        for q in qs:
            L.append(f"- {q}")
        L.append("")
    L += ["调研时要记录：spot 名称与在园内的位置、朝向（背景在哪个方位）、最佳季节与时段、是否允许人像/三脚架、人流高峰。",
          "把结果填进 shotlist 模板的「地点」「背景方位」「注意事项」三栏。"]
    (out / "spots.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"完成 → {out/'spots.md'}（POI {len(pois)}，照片 {len(photos)}）")


if __name__ == "__main__":
    main()
