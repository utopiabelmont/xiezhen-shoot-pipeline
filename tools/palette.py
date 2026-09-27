#!/usr/bin/env python3
"""
palette.py　从场地照片抽主色，给阶段 2b「穿搭」当依据。

  python tools/palette.py --plan plans/<plan> [--n 12] [--images <目录>] [--offline]

来源优先级：--images 指定的本地目录 → plans/<plan>/palette/ 里已下载的图 → spots.json 的 commons_photos（下载 ≤ n 张 480px 缩略图）。
输出：plans/<plan>/palette.json（6 个主色的 hex / 占比 / Lab / 简单命名）与 palette.png（色卡）。
主色计算：每张图缩到 160px，去掉接近纯白/纯黑的像素（天空过曝与阴影），全部像素合并后 k=6 量化（PIL 中位切分），按占比排序。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

UA = "xiezhen-shoot-pipeline/1.2 (palette; contact via GitHub utopiabelmont)"


def fetch(url: str, dst: Path, timeout=30) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dst.write_bytes(r.read())
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  下载失败 {url[:80]}… {e}", file=sys.stderr)
        return False


def rgb_to_lab(rgb):
    r, g, b = [c / 255.0 for c in rgb]
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.0
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return [round(116 * fy - 16, 1), round(500 * (fx - fy), 1), round(200 * (fy - fz), 1)]


def delta_e(lab1, lab2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def name_color(lab):
    """粗略命名，给穿搭文案用。"""
    L, a, b = lab
    c = math.hypot(a, b)
    h = (math.degrees(math.atan2(b, a)) + 360) % 360
    if c < 9:
        return "深灰/近黑" if L < 30 else ("浅灰/米白" if L > 75 else "中灰")
    if c < 18:
        base = "灰"
    else:
        base = ""
    if 20 <= h < 70:
        hue = "橙/土黄" if L < 65 else "米黄"
    elif 70 <= h < 110:
        hue = "黄绿/橄榄"
    elif 110 <= h < 170:
        hue = "绿"
    elif 170 <= h < 250:
        hue = "青/蓝灰"
    elif 250 <= h < 300:
        hue = "蓝"
    elif 300 <= h < 350:
        hue = "紫/藕"
    else:
        hue = "红/砖红" if L < 60 else "粉"
    tone = "深" if L < 35 else ("浅" if L > 70 else "")
    return f"{tone}{base}{hue}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--images")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    plan = Path(a.plan)
    pdir = plan / "palette"; pdir.mkdir(parents=True, exist_ok=True)
    files = []
    if a.images:
        files = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not files:
        files = sorted(p for p in pdir.glob("img_*.jpg"))
    if not files and not a.offline:
        spots = json.loads((plan / "spots.json").read_text(encoding="utf-8"))
        photos = spots.get("commons_photos") or []
        for i, ph in enumerate(photos[: a.n]):
            url = ph.get("thumb") or ph.get("url")
            if not url:
                continue
            url = url.replace("width=800", "width=480")
            dst = pdir / f"img_{i:02d}.jpg"
            if fetch(url, dst):
                files.append(dst)
        print(f"下载 {len(files)} 张 Commons 缩略图")
    if not files:
        raise SystemExit("没有可用图片：用 --images 指定目录，或先跑 spots 取得 commons_photos")

    pixels = []
    used = []
    for f in files:
        try:
            im = Image.open(f).convert("RGB")
        except Exception:
            continue
        im.thumbnail((160, 160))
        data = list(im.tobytes())
        px = [(data[i], data[i + 1], data[i + 2]) for i in range(0, len(data), 3) if 18 < (data[i] + data[i + 1] + data[i + 2]) / 3 < 238]
        pixels.extend(px); used.append(f.name)
    if not pixels:
        raise SystemExit("图片像素为空")
    sheet = Image.new("RGB", (len(pixels), 1)); sheet.putdata(pixels)
    q = sheet.quantize(colors=a.k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: a.k * 3]
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    colors = []
    for cnt, idx in counts:
        rgb = tuple(pal[idx * 3: idx * 3 + 3])
        lab = rgb_to_lab(rgb)
        colors.append({"hex": "#%02x%02x%02x" % rgb, "rgb": list(rgb), "lab": lab,
                       "share": round(cnt / total, 3), "name": name_color(lab)})
    out = {"source": used, "k": a.k, "colors": colors}
    (plan / "palette.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 色卡
    W = 900; H = 200
    img = Image.new("RGB", (W, H), (247, 244, 236)); d = ImageDraw.Draw(img)
    x = 0
    for c in colors:
        w = max(60, int(W * c["share"]))
        d.rectangle((x, 0, x + w, 140), fill=tuple(c["rgb"]))
        x += w
    try:
        from make_cards import font  # type: ignore
        f = font(16)
    except Exception:
        f = ImageFont.load_default()
    x = 0
    for c in colors:
        w = max(60, int(W * c["share"]))
        d.text((x + 6, 150), f"{c['hex']} {int(c['share']*100)}%", font=f, fill=(40, 40, 40))
        d.text((x + 6, 172), c["name"], font=f, fill=(90, 90, 85))
        x += w
    img.save(plan / "palette.png")
    print("主色：" + "，".join(f"{c['hex']}({c['name']} {int(c['share']*100)}%)" for c in colors))
    print("→", plan / "palette.json", plan / "palette.png")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
