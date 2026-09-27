"""公共函数：地理编码、方位换算、HTTP 请求（带离线 fixture 回退）。"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "xiezhen-pipeline/0.2 (personal shoot planning; contact via GitHub)"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

COMPASS16 = ["北", "北北东", "东北", "东北东", "东", "东南东", "东南", "南南东",
             "南", "南南西", "西南", "西南西", "西", "西北西", "西北", "北北西"]


def http_json(url: str, *, data: bytes | None = None, headers: dict | None = None,
              fixture: str | None = None, timeout: int = 30):
    """GET/POST 并解析 JSON。fixture 给定时直接读本地文件（离线测试用）。"""
    if fixture:
        return json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(place: str, *, fixture: bool = False) -> dict:
    """Nominatim 地理编码，返回 {name, lat, lon, display_name, osm}。使用政策：≤1 次/秒，需 UA。"""
    q = urllib.parse.quote(place)
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=jsonv2&limit=1&accept-language=ja,zh,en"
    res = http_json(url, fixture="nominatim.json" if fixture else None)
    if not res:
        raise SystemExit(f"地理编码没有结果：{place}。请改用 --lat/--lon 直接给坐标。")
    r = res[0]
    time.sleep(1.0)
    return {"name": r.get("name") or place, "lat": float(r["lat"]), "lon": float(r["lon"]),
            "display_name": r.get("display_name", ""), "osm": f"{r.get('osm_type')}/{r.get('osm_id')}"}


def compass(az: float) -> str:
    return COMPASS16[int((az % 360) / 22.5 + 0.5) % 16]


def bearing(lat1, lon1, lat2, lon2) -> float:
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def destination(lat, lon, bearing_deg, dist_m):
    R = 6371000.0
    br, la, lo = math.radians(bearing_deg), math.radians(lat), math.radians(lon)
    la2 = math.asin(math.sin(la) * math.cos(dist_m / R) + math.cos(la) * math.sin(dist_m / R) * math.cos(br))
    lo2 = lo + math.atan2(math.sin(br) * math.sin(dist_m / R) * math.cos(la),
                          math.cos(dist_m / R) - math.sin(la) * math.sin(la2))
    return math.degrees(la2), math.degrees(lo2)
