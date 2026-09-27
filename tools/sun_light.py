#!/usr/bin/env python3
"""
sun_light.py　真实地点 + 真实日期 → 太阳方位/高度、黄金时刻、阴影、地形遮挡、天气光质，
输出可直接写进拍摄脚本与写真 prompt 的「光线摘要」。

用法：
  python tools/sun_light.py --place "箱根ガラスの森美術館" --date 2026-10-03 --out plans/hakone-1003
  python tools/sun_light.py --lat 35.2662 --lon 139.0177 --date 2026-10-03 --hours 10-17 --step 30 --out plans/x
  加 --weather 拉取 Open-Meteo 逐小时云量/直射比（预报只覆盖未来约 16 天）
  加 --terrain 用 Open-Meteo 高程 API 采样周围地形，估算各方位的地形遮挡角
  加 --fixture 用 tools/fixtures 里的离线样本代替联网（测试用）

产物（写到 --out 目录）：sun.md、sun.json、sun_path.png
依赖：pip install astral matplotlib   （可选：pvlib 交叉验证、timezonefinder 自动时区）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import zoneinfo
from pathlib import Path

from astral import Observer, SunDirection
from astral.sun import azimuth, elevation, golden_hour, blue_hour, sun as sun_times

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo_common import compass, destination, geocode, http_json  # noqa: E402

WMO = {0: "晴", 1: "基本晴", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇", 51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
       61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 81: "阵雨", 82: "强阵雨",
       95: "雷雨", 96: "雷雨冰雹", 99: "雷雨冰雹"}


# ---------- 天文 ----------
def sun_state(obs: Observer, t: dt.datetime) -> dict:
    az, el = azimuth(obs, t), elevation(obs, t)
    shadow = (1 / math.tan(math.radians(el))) if el > 0.5 else None
    return {"time": t.strftime("%H:%M"), "azimuth": round(az, 1), "elevation": round(el, 1),
            "from": compass(az), "shadow_ratio": round(shadow, 2) if shadow else None,
            "quality": sun_quality(el)}


def sun_quality(el: float) -> str:
    if el <= -6:
        return "夜"
    if el <= 0:
        return "蓝调时刻（太阳在地平线下，冷色散射光）"
    if el < 6:
        return "黄金时刻（暖色、极低角度、长影，人物易被地形或建筑挡光）"
    if el < 20:
        return "低角度暖光（侧光/逆光塑形好，阴影长）"
    if el < 40:
        return "中等高度（顺光会有眼窝阴影，宜侧光或找遮荫）"
    return "高角度顶光（正午硬光，眼窝和鼻下阴影重，优先树荫、建筑阴影或阴天）"


def facing_table(az_sun: float) -> list[dict]:
    """人物面朝各方向时的光型。相对角 = 人物朝向 − 太阳方位。"""
    rows = []
    for name, face in [("北", 0), ("东北", 45), ("东", 90), ("东南", 135), ("南", 180), ("西南", 225), ("西", 270), ("西北", 315)]:
        d = abs(((face - az_sun) + 180) % 360 - 180)
        kind = "顺光（脸全亮，易眯眼）" if d < 30 else "前侧光（经典塑形）" if d < 70 else "侧光（明暗各半）" if d < 110 \
            else "后侧光（轮廓光，脸需补光/反射）" if d < 150 else "逆光（发丝光，脸靠环境回填，注意眩光）"
        rows.append({"facing": name, "rel_deg": round(d), "light": kind})
    return rows


# ---------- 地形遮挡 ----------
def terrain_horizon(lat, lon, *, fixture=False, dists=(500, 1000, 2000, 4000, 8000), step=15) -> dict:
    """采样周围环形高程，算每个方位的地形遮挡角（度）。返回 {azimuth: horizon_deg}。"""
    if fixture:
        fx = http_json("", fixture="elevation_ring.json")
        center, elev, dists, step = fx["center"], fx["elevation"], fx["distances_m"], fx["azimuth_step"]
    else:
        pts = [destination(lat, lon, az, d) for d in dists for az in range(0, 360, step)]
        elev = []
        for i in range(0, len(pts), 100):
            chunk = pts[i:i + 100]
            url = ("https://api.open-meteo.com/v1/elevation?latitude=" + ",".join(f"{p[0]:.5f}" for p in chunk)
                   + "&longitude=" + ",".join(f"{p[1]:.5f}" for p in chunk))
            elev += http_json(url)["elevation"]
        center = http_json(f"https://api.open-meteo.com/v1/elevation?latitude={lat:.5f}&longitude={lon:.5f}")["elevation"][0]
    n = 360 // step
    horizon = {}
    for k in range(n):
        az = k * step
        angs = [math.degrees(math.atan2(elev[j * n + k] - center, dists[j])) for j in range(len(dists))]
        horizon[az] = round(max(angs), 1)
    return {"center_elevation_m": center, "horizon": horizon, "step": step}


def horizon_at(h: dict, az: float) -> float:
    step = h["step"]
    k = int(round((az % 360) / step)) % (360 // step)
    return h["horizon"][k * step]


# ---------- 天气 ----------
def fetch_weather(lat, lon, date: dt.date, tz: str, *, fixture=False, raw: dict | None = None) -> dict | None:
    today = dt.date.today()
    if raw is None and not fixture and not (today - dt.timedelta(days=1) <= date <= today + dt.timedelta(days=15)):
        return {"note": f"{date} 超出 Open-Meteo 预报范围（约 16 天），本次只给天文数据；临近再跑一次。"}
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
           f"&hourly=cloud_cover,direct_radiation,diffuse_radiation,weather_code,precipitation_probability,"
           f"temperature_2m,apparent_temperature,precipitation,wind_speed_10m,relative_humidity_2m"
           f"&daily=sunrise,sunset,weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
           f"&wind_speed_unit=ms&timezone={tz}&start_date={date}&end_date={date}")
    j = raw if raw is not None else http_json(url, fixture="open_meteo_forecast.json" if fixture else None)
    H = j["hourly"]
    opt = lambda k, i: (H.get(k) or [None] * (i + 1))[i]          # 旧样本没有气温、风等字段时留空
    rows = []
    for i, t in enumerate(H["time"]):
        if not t.startswith(str(date)):
            continue
        dr, df = H["direct_radiation"][i], H["diffuse_radiation"][i]
        tot = dr + df
        ratio = dr / tot if tot > 5 else None
        cc = H["cloud_cover"][i]
        if ratio is None:
            light = "无日光"
        elif ratio >= 0.5 and cc < 60:
            light = "晴天硬光（直射为主）"
        elif ratio >= 0.5:
            light = "高云/薄云透光，直射时强时弱（晴、阴两套站位都要准备）"
        elif ratio >= 0.2:
            light = "薄云柔光（直射与散射并存）"
        else:
            light = "阴天散射光（无明显方向，柔和低反差）"
        rows.append({"time": t[11:], "cloud": H["cloud_cover"][i], "direct": dr, "diffuse": df,
                     "direct_ratio": round(ratio, 2) if ratio is not None else None,
                     "rain_prob": H["precipitation_probability"][i],
                     "wmo": WMO.get(H["weather_code"][i], str(H["weather_code"][i])), "light": light,
                     "temp": opt("temperature_2m", i), "feels": opt("apparent_temperature", i),
                     "precip_mm": opt("precipitation", i), "wind_ms": opt("wind_speed_10m", i),
                     "humidity": opt("relative_humidity_2m", i)})
    daily = j.get("daily", {})
    k = daily.get("time", []).index(str(date)) if str(date) in daily.get("time", []) else None
    return {"rows": rows, "sunrise_om": daily["sunrise"][k][11:] if k is not None else None,
            "sunset_om": daily["sunset"][k][11:] if k is not None else None,
            "t_max": (daily.get("temperature_2m_max") or [None] * 9)[k] if k is not None else None,
            "t_min": (daily.get("temperature_2m_min") or [None] * 9)[k] if k is not None else None,
            "precip_sum": (daily.get("precipitation_sum") or [None] * 9)[k] if k is not None else None,
            "fetched": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "Open-Meteo（离线样本）" if fixture else "Open-Meteo（浏览器取回）" if raw is not None else "Open-Meteo"}


# ---------- 出图 ----------
def draw(out_png: Path, place: str, date: dt.date, rows: list[dict], key: dict, horizon: dict | None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    cjk = [f for f in ["Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK JP", "Microsoft YaHei", "Meiryo",
                       "Yu Gothic", "PingFang SC", "Hiragino Sans"] if any(f == x.name for x in font_manager.fontManager.ttflist)]
    if cjk:
        plt.rcParams["font.family"] = cjk[0]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(11, 5.2), dpi=150)
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(90, 0)                       # 圆心=天顶(90°)，外圈=地平线(0°)
    ax.set_rticks([0, 15, 30, 45, 60, 75])
    ax.set_rlabel_position(135)
    ax.set_xticks([math.radians(a) for a in range(0, 360, 45)])
    ax.set_xticklabels(["北", "东北", "东", "东南", "南", "西南", "西", "西北"] if cjk else ["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    ax.grid(alpha=.35)
    if horizon:
        azs = sorted(horizon["horizon"])
        th = [math.radians(a) for a in azs] + [math.radians(azs[0])]
        r = [horizon["horizon"][a] for a in azs] + [horizon["horizon"][azs[0]]]
        ax.fill_between(th, 0, r, color="#7a8f6a", alpha=.35, label="地形遮挡" if cjk else "terrain")
    day = [x for x in rows if x["elevation"] > 0]
    ax.plot([math.radians(x["azimuth"]) for x in day], [x["elevation"] for x in day], color="#d9a441", lw=2)
    for x in day:
        if x["time"].endswith(":00"):
            ax.scatter(math.radians(x["azimuth"]), x["elevation"], s=28, color="#c2701d", zorder=3)
            ax.annotate(x["time"], (math.radians(x["azimuth"]), x["elevation"]), fontsize=7,
                        xytext=(4, 4), textcoords="offset points")
    title = f"{place}\n{date}  太阳轨迹（俯视，圆心为正上方）" if cjk else f"{place}\n{date} sun path (top view)"
    ax.set_title(title, fontsize=9, pad=14)
    if horizon:
        ax.legend(loc="lower left", fontsize=7, bbox_to_anchor=(-0.15, -0.12))

    ax2 = fig.add_subplot(1, 2, 2)
    hrs = [int(x["time"][:2]) + int(x["time"][3:]) / 60 for x in rows]
    ax2.plot(hrs, [x["elevation"] for x in rows], color="#c2701d", lw=2, label="太阳高度角" if cjk else "elevation")
    if horizon:
        ax2.plot(hrs, [horizon_at(horizon, x["azimuth"]) for x in rows], color="#7a8f6a", lw=1.5, ls="--",
                 label="该方位地形遮挡角" if cjk else "terrain horizon")
    for k_, c in [("golden_am", "#f2d28a"), ("golden_pm", "#f2d28a"), ("blue_pm", "#9fb7d9"), ("blue_am", "#9fb7d9")]:
        if key.get(k_):
            a, b = key[k_]
            ax2.axvspan(_h(a), _h(b), color=c, alpha=.35)
    ax2.axhline(0, color="#999", lw=.8)
    ax2.set_xlim(4, 20)
    ax2.set_ylim(-10, 90)
    ax2.set_xlabel("当地时间" if cjk else "local time")
    ax2.set_ylabel("角度 (°)" if cjk else "deg")
    ax2.set_title("高度角与地形遮挡（黄=黄金时刻，蓝=蓝调）" if cjk else "elevation vs terrain (gold/blue hours)", fontsize=9)
    ax2.grid(alpha=.3)
    ax2.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _h(s: str) -> float:
    return int(s[:2]) + int(s[3:]) / 60


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", help="地点名（用于地理编码与标题）")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--tz", help="IANA 时区，默认自动（timezonefinder）或 Asia/Tokyo")
    ap.add_argument("--hours", default="6-19", help="输出时段，如 9-17")
    ap.add_argument("--step", type=int, default=30, help="分钟步长")
    ap.add_argument("--elev-m", type=float, default=0.0, help="观测点海拔（米），影响日出日落几分钟")
    ap.add_argument("--weather", action="store_true")
    ap.add_argument("--terrain", action="store_true")
    ap.add_argument("--fixture", action="store_true", help="离线样本测试")
    ap.add_argument("--weather-only", action="store_true", help="只刷新已有 sun.json 的天气（出发前一天用，不重算地形）")
    ap.add_argument("--weather-json", help="用浏览器等其他途径取回的 Open-Meteo 响应 JSON，代替联网请求")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    raw = json.loads(Path(a.weather_json).read_text(encoding="utf-8")) if a.weather_json else None
    if a.weather_only:
        f = Path(a.out) / "sun.json"
        if not f.exists():
            sys.exit("--weather-only 需要先跑过一次完整的 sun")
        data = json.loads(f.read_text(encoding="utf-8"))
        data["weather"] = fetch_weather(data["lat"], data["lon"], dt.date.fromisoformat(data["date"]), data["tz"],
                                        fixture=a.fixture, raw=raw)
        data["generated"] = dt.datetime.now().isoformat(timespec="seconds")
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        (Path(a.out) / "sun.md").write_text(render_md(data), encoding="utf-8")
        print(f"天气已刷新 → {f}")
        return

    if a.lat is None or a.lon is None:
        if not a.place:
            sys.exit("需要 --place 或 --lat/--lon")
        try:
            g = geocode(a.place, fixture=a.fixture)
        except Exception as e:
            sys.exit(f"地理编码失败（{e.__class__.__name__}）。请改用 --lat/--lon 直接给坐标。")
        a.lat, a.lon = g["lat"], g["lon"]
        place = g["name"]
        geo_note = g["display_name"]
    else:
        place, geo_note = a.place or f"{a.lat:.4f},{a.lon:.4f}", ""

    tzname = a.tz
    if not tzname:
        try:
            from timezonefinder import TimezoneFinder
            tzname = TimezoneFinder().timezone_at(lat=a.lat, lng=a.lon) or "Asia/Tokyo"
        except Exception:
            tzname = "Asia/Tokyo"
    tz = zoneinfo.ZoneInfo(tzname)
    date = dt.date.fromisoformat(a.date)
    obs = Observer(a.lat, a.lon, a.elev_m)

    st = sun_times(obs, date=date, tzinfo=tz)
    key = {"sunrise": st["sunrise"].strftime("%H:%M"), "sunset": st["sunset"].strftime("%H:%M"),
           "solar_noon": st["noon"].strftime("%H:%M"), "civil_dawn": st["dawn"].strftime("%H:%M"),
           "civil_dusk": st["dusk"].strftime("%H:%M"),
           "noon_elevation": round(elevation(obs, st["noon"]), 1)}
    for nm, fn, d in [("golden_am", golden_hour, SunDirection.RISING), ("golden_pm", golden_hour, SunDirection.SETTING),
                      ("blue_am", blue_hour, SunDirection.RISING), ("blue_pm", blue_hour, SunDirection.SETTING)]:
        try:
            s, e = fn(obs, date, d, tz)
            key[nm] = (s.strftime("%H:%M"), e.strftime("%H:%M"))
        except Exception:
            key[nm] = None

    h0, h1 = (int(x) for x in a.hours.split("-"))
    rows = []
    t = dt.datetime(date.year, date.month, date.day, h0, 0, tzinfo=tz)
    while t <= dt.datetime(date.year, date.month, date.day, h1, 0, tzinfo=tz):
        rows.append(sun_state(obs, t))
        t += dt.timedelta(minutes=a.step)

    horizon = None
    if a.terrain:
        try:
            horizon = terrain_horizon(a.lat, a.lon, fixture=a.fixture)
        except Exception as e:  # 联网失败不影响天文部分
            print(f"地形高程获取失败，跳过地形遮挡：{e}")
    if horizon:
        for r in rows:
            hz = horizon_at(horizon, r["azimuth"])
            r["terrain_horizon"] = hz
            r["blocked_by_terrain"] = bool(0 < r["elevation"] <= hz)
        vis = [r for r in rows if r["elevation"] > 0 and not r["blocked_by_terrain"]]
        key["terrain_last_direct_light"] = vis[-1]["time"] if vis else None
        key["terrain_first_direct_light"] = vis[0]["time"] if vis else None

    weather = None
    if a.weather:
        try:
            weather = fetch_weather(a.lat, a.lon, date, tzname, fixture=a.fixture, raw=raw)
        except Exception as e:
            weather = {"note": f"天气获取失败（{e.__class__.__name__}），本次只给天文数据。"}
            print("天气获取失败：", e)

    try:
        import pvlib, pandas as pd  # noqa
        times = pd.DatetimeIndex([dt.datetime(date.year, date.month, date.day, 12, 0, tzinfo=tz)])
        sp = pvlib.solarposition.get_solarposition(times, a.lat, a.lon, altitude=a.elev_m)
        key["crosscheck_pvlib_noon12"] = {"azimuth": round(float(sp["azimuth"].iloc[0]), 1),
                                          "elevation": round(float(sp["apparent_elevation"].iloc[0]), 1),
                                          "astral": sun_state(obs, times[0].to_pydatetime())}
    except Exception:
        pass

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = {"place": place, "geocode": geo_note, "lat": a.lat, "lon": a.lon, "tz": tzname, "date": str(date),
            "key_times": key, "rows": rows, "terrain": horizon, "weather": weather,
            "generated": dt.datetime.now().isoformat(timespec="seconds")}
    (out / "sun.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "sun.md").write_text(render_md(data), encoding="utf-8")
    try:
        draw(out / "sun_path.png", place, date, rows, key, horizon)
    except Exception as e:  # 出图失败不影响文本交付
        print("画图失败：", e)
    print(f"完成 → {out/'sun.md'}")


def render_md(d: dict) -> str:
    k = d["key_times"]
    L = [f"# 光线摘要　{d['place']}　{d['date']}", ""]
    L.append(f"- 坐标 {d['lat']:.5f}, {d['lon']:.5f}　时区 {d['tz']}" + (f"　（{d['geocode']}）" if d["geocode"] else ""))
    L.append(f"- 日出 {k['sunrise']}　太阳正午 {k['solar_noon']}（高度角 {k['noon_elevation']}°）　日落 {k['sunset']}")
    L.append(f"- 民用晨昏：{k['civil_dawn']} / {k['civil_dusk']}")
    if k.get("golden_am"):
        L.append(f"- 早黄金时刻 {k['golden_am'][0]}–{k['golden_am'][1]}　晚黄金时刻 {k['golden_pm'][0]}–{k['golden_pm'][1]}")
    if k.get("blue_pm"):
        L.append(f"- 早蓝调 {k['blue_am'][0]}–{k['blue_am'][1]}　晚蓝调 {k['blue_pm'][0]}–{k['blue_pm'][1]}")
    if d.get("terrain"):
        hz = d["terrain"]["horizon"]
        worst = sorted(hz.items(), key=lambda x: -x[1])[:3]
        L.append(f"- 地形遮挡（观测点海拔 {d['terrain']['center_elevation_m']} m）：最高遮挡方位 "
                 + "、".join(f"{compass(float(a))}{a}° 约{v}°" for a, v in worst)
                 + f"；受地形影响，直射光实际可用到约 **{k.get('terrain_last_direct_light')}**（几何日落 {k['sunset']}）")
    if k.get("crosscheck_pvlib_noon12"):
        c = k["crosscheck_pvlib_noon12"]
        L.append(f"- 交叉验证（12:00）：astral 方位 {c['astral']['azimuth']}°/高度 {c['astral']['elevation']}°，"
                 f"pvlib 方位 {c['azimuth']}°/高度 {c['elevation']}°")
    L += ["", "## 逐时太阳位置", "", "| 时间 | 太阳方位 | 来光方向 | 高度角 | 影长/身高 | 光质 |" + (" 地形遮挡 |" if d.get("terrain") else ""),
          "|---|---|---|---|---|---|" + ("---|" if d.get("terrain") else "")]
    for r in d["rows"]:
        if r["elevation"] <= -6:
            continue
        row = f"| {r['time']} | {r['azimuth']}° | {r['from']} | {r['elevation']}° | {r['shadow_ratio'] if r['shadow_ratio'] else '—'} | {r['quality']} |"
        if d.get("terrain"):
            row += (" 被挡 |" if r.get("blocked_by_terrain") else f" 通过（遮挡角 {r['terrain_horizon']}°） |")
        L.append(row)
    W = d.get("weather")
    if W:
        L += ["", "## 天气与光质（" + W.get("source", "") + "）", ""]
        if W.get("note"):
            L.append(W["note"])
        else:
            f1 = lambda v, u="": "—" if v is None else f"{v:.0f}{u}" if isinstance(v, (int, float)) else f"{v}{u}"
            if W.get("t_max") is not None:
                L.append(f"全天 {f1(W.get('t_min'))}–{f1(W.get('t_max'))} °C，累计降水 {W.get('precip_sum')} mm"
                         + (f"（{W['fetched']} 拉取）" if W.get("fetched") else "") + "\n")
            L.append("| 时间 | 天气 | 降水概率 | 降水 mm | 气温（体感）°C | 风 m/s | 湿度 | 云量 | 直射比 | 现场光判断 |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            for r in W["rows"]:
                if 6 <= int(r["time"][:2]) <= 18:
                    tt = f"{f1(r.get('temp'))}（{f1(r.get('feels'))}）" if r.get("temp") is not None else "—"
                    L.append(f"| {r['time']} | {r['wmo']} | {r['rain_prob']}% | {r.get('precip_mm', '—') if r.get('precip_mm') is not None else '—'} | {tt} | "
                             f"{'—' if r.get('wind_ms') is None else round(r['wind_ms'], 1)} | {f1(r.get('humidity'), '%')} | {r['cloud']}% | "
                             f"{r['direct_ratio'] if r['direct_ratio'] is not None else '—'} | {r['light']} |")
            if W.get("sunrise_om"):
                L.append(f"\nOpen-Meteo 给出的日出/日落：{W['sunrise_om']} / {W['sunset_om']}（与上面天文计算差几分钟属正常，海拔与大气折射口径不同）")
    # 关键时段的人物朝向表
    picks = [r for r in d["rows"] if r["elevation"] > 0 and r["time"] in ("10:00", "12:00", "14:00", "16:00")]
    if picks:
        L += ["", "## 人物面朝方向与光型（按时段）", ""]
        for r in picks:
            L.append(f"**{r['time']}**　太阳在{r['from']}（{r['azimuth']}°），高度 {r['elevation']}°")
            L.append("")
            L.append("| 人物面朝 | 与太阳夹角 | 光型 |")
            L.append("|---|---|---|")
            for f in facing_table(r["azimuth"]):
                L.append(f"| {f['facing']} | {f['rel_deg']}° | {f['light']} |")
            L.append("")
    L += ["", "## 写进 prompt 的光线句（示例，按分镜时段替换）", ""]
    for r in picks[:2]:
        if W and not W.get("note"):
            wr = next((x for x in W["rows"] if x["time"] == r["time"]), None)
            wtxt = f"，{wr['light']}，云量 {wr['cloud']}%" if wr else ""
        else:
            wtxt = ""
        L.append(f"- {r['time']}：太阳位于{r['from']}方向、高度角 {r['elevation']}°{wtxt}；"
                 f"人物面朝{_best_facing(r['azimuth'])}时为前侧光，脸部亮侧朝太阳一侧，影长约为身高的 {r['shadow_ratio']} 倍。")
    return "\n".join(L) + "\n"


def _best_facing(az_sun: float) -> str:
    # 前侧光：人物朝向与太阳方位差约 45°
    return compass(az_sun + 45) + "或" + compass(az_sun - 45)


if __name__ == "__main__":
    main()
