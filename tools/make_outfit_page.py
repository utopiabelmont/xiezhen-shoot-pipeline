#!/usr/bin/env python3
"""
make_outfit_page.py　把 outfit.json（+ palette.json）渲染成「穿搭页」，放在小抄 PDF 最前面。

  python tools/make_outfit_page.py --plan plans/<plan> --out plans/<plan>/cards
产物：cards/outfit_01.png（主页：场地色卡、服装色与分离度、主方案、替换方案、道具、妆发）
      cards/outfit_02.png（逐张分镜的着装提醒，条目多时才生成）
outfit.json 结构见 templates/outfit_template.md。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_cards import W, H, BG, GREEN, INK, MUTED, PANEL, LINE, font, panel, text_block, page_header  # noqa: E402
from i18n import tr  # noqa: E402
from palette import rgb_to_lab, delta_e  # noqa: E402


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def swatch_row(d, x, y, items, w=92, h=54, f=None, ft=None):
    """items: [(hex, label, sub)]，返回底部 y。"""
    for hx, label, sub in items:
        d.rectangle((x, y, x + w, y + h), fill=hex_rgb(hx), outline=LINE)
        d.text((x, y + h + 4), label, font=f, fill=INK)
        if sub:
            t = sub = tr(sub)
            while t and d.textlength(t + "…", font=ft) > w + 6:
                t = t[:-1]
            d.text((x, y + h + 22), t + ("…" if t != sub else ""), font=ft, fill=MUTED)
        x += w + 10
    return y + h + 44


def separation(outfit_colors, scene_colors):
    """每个服装色与最接近的场地主色之间的 ΔE（CIE76）。"""
    rows = []
    for oc in outfit_colors:
        lab = rgb_to_lab(hex_rgb(oc["hex"]))
        best = min(((delta_e(lab, sc["lab"]), sc) for sc in scene_colors), key=lambda t: t[0]) if scene_colors else (None, None)
        rows.append((oc, best[0], best[1]))
    return rows


def page_main(o, pal, meta, out):
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    f_title, f_h, f_b, f_s, f_t = font(44, True), font(24, True), font(20), font(18), font(15)
    sub = f"{tr(meta.get('place','').split('（')[0])}　{meta.get('date','')}"
    page_header(d, tr("穿搭"), tr(o.get("title") or "本次出行的服装方案"), sub)

    # 左栏：色卡与分离度
    lx0, lx1 = 40, 760
    y = panel(d, (lx0, 110, lx1, 470), "场地主色（Commons 照片抽样）与服装色", f_h)
    scene = (pal or {}).get("colors", [])
    if scene:
        y = swatch_row(d, lx0 + 16, y + 4, [(c["hex"], f"{c['hex']}  {int(c['share']*100)}%", c["name"]) for c in scene[:6]], f=f_t, ft=f_t)
    else:
        d.text((lx0 + 16, y + 4), "（未跑 palette，场地色缺）", font=f_s, fill=MUTED); y += 40
    oc = o.get("colors", [])
    d.text((lx0 + 16, y), "服装色", font=f_s, fill=GREEN); y += 26
    y = swatch_row(d, lx0 + 16, y, [(c["hex"], c.get("name", c["hex"]), c.get("part", "")) for c in oc[:6]], f=f_t, ft=f_t)
    rows = separation(oc, scene)
    lines = []
    for c, de, sc in rows:
        if de is None:
            continue
        verdict = "会融进背景" if de < 12 else ("偏近，靠明度拉开" if de < 22 else "分离清楚")
        lines.append(f"{c.get('name', c['hex'])} ↔ 场地 {sc['name']}  ΔE {de:.0f}  {verdict}")
    if lines:
        text_block(d, (lx0 + 16, y), "\n".join(lines), f_t, lx1 - lx0 - 32, fill=INK, spacing=3)

    y = panel(d, (lx0, 484, lx1, 800), "为什么这样搭", f_h)
    text_block(d, (lx0 + 16, y), "路线：" + o.get("route", "") + "\n" + "\n".join("· " + r for r in o.get("rationale", [])), f_s, lx1 - lx0 - 32, spacing=4)
    y = panel(d, (lx0, 814, lx1, H - 60), "道具 · 妆发", f_h)
    text_block(d, (lx0 + 16, y), "道具：" + "、".join(o.get("props", [])) + "\n妆发：" + o.get("hair_makeup", ""), f_s, lx1 - lx0 - 32, spacing=4)

    # 右栏：方案
    rx0, rx1 = 790, W - 40
    y = panel(d, (rx0, 110, rx1, 430), "主方案", f_h)
    m = o.get("main", {})
    labels = (("top", "上装"), ("bottom", "下装"), ("layer", "外层"), ("shoes", "鞋"), ("accessories", "配饰"), ("bag", "包"))
    kw = max([66] + [d.textlength(tr(lb), font=f_t) + 12 for _, lb in labels])     # 标签列按译文加宽
    for k, label in labels:
        if m.get(k):
            d.text((rx0 + 14, y), label, font=f_t, fill=GREEN)
            y = text_block(d, (rx0 + 14 + kw, y), m[k], f_t, rx1 - rx0 - 34 - kw, spacing=2) + 2
    if o.get("fit_notes"):
        y += 4
        y = text_block(d, (rx0 + 14, y), o["fit_notes"], f_t, rx1 - rx0 - 28, fill=MUTED, spacing=2)
    y = panel(d, (rx0, 444, rx1, 700), "替换方案", f_h)
    alts = o.get("alternatives", {})
    txt = "\n".join(f"{k}：{v}" for k, v in alts.items())
    text_block(d, (rx0 + 14, y), txt, f_t, rx1 - rx0 - 28, spacing=3)
    y = panel(d, (rx0, 714, rx1, 850), "避免", f_h)
    text_block(d, (rx0 + 14, y), "、".join(o.get("avoid", [])), f_t, rx1 - rx0 - 28, spacing=3)
    y = panel(d, (rx0, 864, rx1, H - 22), "SNS 与场地观察", f_h)
    text_block(d, (rx0 + 14, y), o.get("sns_notes", "（spots_social.md 的穿搭栏）"), f_t, rx1 - rx0 - 28, spacing=3)
    y = H
    d.text((40, H - 42), "穿搭依据：docs/OUTFIT_GUIDE.md；场地色来自公开照片抽样，现场以实景为准。", font=f_t, fill=MUTED)
    img.save(out / "outfit_01.png", quality=92)


def page_shots(o, meta, out):
    per = o.get("per_shot") or {}
    if not per:
        return None
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    f_h, f_t = font(24, True), font(16)
    page_header(d, tr("穿搭"), tr("逐张着装提醒"))
    items = sorted(per.items())
    cols = 2 if len(items) > 12 else 1
    colw = (W - 80 - (cols - 1) * 20) // cols
    per_col = (len(items) + cols - 1) // cols
    for ci in range(cols):
        x0 = 40 + ci * (colw + 20)
        y = panel(d, (x0, 110, x0 + colw, H - 60), "分镜 · 提醒", f_h)
        for sid, note in items[ci * per_col:(ci + 1) * per_col]:
            d.text((x0 + 14, y), sid, font=font(16, True), fill=GREEN)
            y = text_block(d, (x0 + 56, y), note, f_t, colw - 76, spacing=2) + 4
            if y > H - 90:
                break
    d.text((40, H - 42), "提醒对应 shotlist.json 的 id；现场按天气与场地实际调整。", font=f_t, fill=MUTED)
    img.save(out / "outfit_02.png", quality=92)
    return out / "outfit_02.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    plan = Path(a.plan); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    o = json.loads((plan / "outfit.json").read_text(encoding="utf-8"))
    pal = json.loads((plan / "palette.json").read_text(encoding="utf-8")) if (plan / "palette.json").exists() else None
    meta = json.loads((plan / "shotlist.json").read_text(encoding="utf-8")).get("meta", {})
    page_main(o, pal, meta, out)
    p2 = page_shots(o, meta, out)
    print("outfit 页：", out / "outfit_01.png", p2 or "")


if __name__ == "__main__":
    main()
