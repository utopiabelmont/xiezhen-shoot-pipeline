#!/usr/bin/env python3
"""
poses.py　姿势参考页：读 plans/<plan>/pose_refs.json，出 cards/poses_<n>.png（每页 8 个姿势）与 cards/poses_src.png（来源、平台汇总与拍摄提示）。

每个姿势的图按顺序取：
  1. plans/<plan>/sns_private/<Pxx>.jpg|png   用户自己从 App 保存的原帖截图（仅个人参考，--public 时不用）
  2. plans/<plan>/poses/<Pxx>*.png            codex-imagegen 按姿势描述画的线稿示意（原创，不含原帖人物）
  3. 都没有时画一个占位框
pose_refs.json 结构见 templates/pose_refs_example.json（posts / poses / summaries / tips）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_cards import W, H, BG, GREEN, INK, MUTED, LINE, PANEL, font, panel, wrap, fit_lines  # noqa: E402

PER_PAGE = 8


def pose_image(plan: Path, pid: str, public: bool):
    if not public:
        for ext in ("jpg", "jpeg", "png", "webp"):
            f = plan / "sns_private" / f"{pid}.{ext}"
            if f.exists():
                return f, "原帖截图 · 仅个人参考"
    hits = sorted((plan / "poses").glob(f"{pid}*.png"))
    if hits:
        return hits[0], "姿势线稿（AI 示意）"
    return None, ""


def render_pages(plan: Path, out: Path, data: dict, shots: dict, public: bool) -> list[Path]:
    posts = {p["id"]: p for p in data.get("posts", [])}
    poses = data.get("poses", [])
    pages = []
    for pi in range(0, len(poses), PER_PAGE):
        chunk = poses[pi:pi + PER_PAGE]
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((40, 26), "姿势参考", font=font(40, True), fill=GREEN)
        d.line([(222, 34), (222, 78)], fill=GREEN, width=3)
        n0, n1 = pi + 1, pi + len(chunk)
        d.text((240, 34), f"小红书姿势帖整理 · {n0}–{n1} / {len(poses)}", font=font(28, True), fill=GREEN)
        sub = "编号后是适用分镜；链接见来源页与核对表"
        d.text((W - 40 - d.textlength(sub, font=font(17)), 46), sub, font=font(17), fill=MUTED)
        cols, rows = 4, 2
        gx0, gy0, gap = 40, 100, 16
        cw = (W - 80 - gap * (cols - 1)) // cols
        ch = (H - 60 - gy0 - gap * (rows - 1)) // rows
        for k, p in enumerate(chunk):
            x0 = gx0 + (k % cols) * (cw + gap)
            y0 = gy0 + (k // cols) * (ch + gap)
            d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=10, fill=PANEL, outline=LINE, width=2)
            ih = ch - 132
            src, tag = pose_image(plan, p["id"], public)
            box = (x0 + 8, y0 + 8, x0 + cw - 8, y0 + 8 + ih)
            if src:
                ph = Image.open(src).convert("RGB")
                bw, bh = box[2] - box[0], box[3] - box[1]
                r = min(bw / ph.width, bh / ph.height)
                ph = ph.resize((int(ph.width * r), int(ph.height * r)), Image.LANCZOS)
                img.paste(ph, (box[0] + (bw - ph.width) // 2, box[1] + (bh - ph.height) // 2))
                d = ImageDraw.Draw(img)
                tw = d.textlength(tag, font=font(11))
                d.rectangle((box[0], box[3] - 18, box[0] + tw + 10, box[3]), fill=(60, 60, 60))
                d.text((box[0] + 5, box[3] - 16), tag, font=font(11), fill=(255, 255, 255))
            else:
                d.rectangle(box, fill=(232, 229, 220)); d.text((box[0] + 10, box[1] + 10), "（示意待生成）", font=font(14), fill=MUTED)
            ty = y0 + 8 + ih + 8
            d.text((x0 + 10, ty), p["id"], font=font(18, True), fill=GREEN)
            d.text((x0 + 58, ty), p["name"], font=font(18, True), fill=INK)
            use = "用于 " + " · ".join(p.get("shots", []))
            uw = d.textlength(use, font=font(13, True))
            d.rounded_rectangle((x0 + cw - uw - 20, ty + 1, x0 + cw - 8, ty + 22), radius=8, fill=GREEN)
            d.text((x0 + cw - uw - 14, ty + 3), use, font=font(13, True), fill=(255, 255, 255))
            ty += 28
            for ln in fit_lines(d, p["how"], font(13), cw - 20, 4):
                d.text((x0 + 10, ty), ln, font=font(13), fill=INK); ty += 17
            s = posts.get(p.get("src"), {})
            srcl = f"{p.get('src', '')} {s.get('title', '')} · {s.get('likes', '')} 赞"
            d.text((x0 + 10, y0 + ch - 20), fit_lines(d, srcl, font(11), cw - 20, 1)[0], font=font(11), fill=MUTED)
        d.text((40, H - 42), "姿势来自小红书公开帖子的整理；线稿为按文字描述生成的原创示意，原帖图片请点链接查看。", font=font(15), fill=MUTED)
        f = out / f"poses_{pi // PER_PAGE + 1}.png"
        img.save(f, quality=92)
        pages.append(f)
    return pages


def render_sources(out: Path, data: dict) -> Path:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 26), "姿势参考", font=font(40, True), fill=GREEN)
    d.line([(222, 34), (222, 78)], fill=GREEN, width=3)
    d.text((240, 34), "来源帖子、平台汇总与雨天拍摄提示", font=font(28, True), fill=GREEN)
    lx1 = 800
    y = panel(d, (40, 100, lx1, 600), "来源帖子（小红书）", font(22, True))
    for p in data.get("posts", []):
        d.text((54, y), f"{p['id']}  {p['title']}", font=font(16, True), fill=INK)
        y += 22
        d.text((54, y), f"{p.get('posted', '')} · {p.get('likes', '')} 赞 · {p['url'].replace('https://www.', '')}", font=font(12), fill=MUTED)
        y += 18
        for ln in fit_lines(d, p.get("note", ""), font(13), lx1 - 70, 2):
            d.text((54, y), ln, font=font(13), fill=INK); y += 17
        y += 8
    y = panel(d, (40, 612, lx1, H - 60), "想在脚本里看原帖图片", font(22, True))
    for t in ["1. 在小红书 App 打开帖子（核对表里点链接），长按图片「保存图片」或截图。",
              "2. 传到电脑，放进 plans/<plan>/sns_private/，按姿势编号命名：P01.jpg、P02.jpg……（机位参考用 S01.jpg……）。",
              "3. 重跑 python pipeline.py cards <plan>：有原图的姿势会替换线稿，标「原帖截图 · 仅个人参考」。",
              "sns_private 不进仓库、不进公开版核对表；公开版（--public）只放线稿和链接。"]:
        for ln in wrap(d, t, font(14), lx1 - 70):
            d.text((54, y), ln, font=font(14), fill=INK); y += 19
        y += 4
    rx0 = 820
    y = panel(d, (rx0, 100, W - 40, 520), "平台汇总（小红书「问点点」）", font(22, True))
    for s in data.get("summaries", []):
        for ln in fit_lines(d, s["source"], font(13, True), W - 40 - rx0 - 28, 2):
            d.text((rx0 + 14, y), ln, font=font(13, True), fill=GREEN); y += 17
        for pt in s["points"]:
            for ln in wrap(d, "· " + pt, font(13), W - 40 - rx0 - 28):
                d.text((rx0 + 14, y), ln, font=font(13), fill=INK); y += 17
        y += 8
    y = panel(d, (rx0, 532, W - 40, H - 60), "雨天拍摄提示", font(22, True))
    for t in data.get("tips", []):
        for ln in wrap(d, f"{t['src']}：{t['text']}", font(13), W - 40 - rx0 - 28):
            d.text((rx0 + 14, y), ln, font=font(13), fill=INK); y += 17
        y += 6
    d.text((40, H - 42), "只记链接与文字观察；原帖图片不保存。想在脚本里看原图，自己在 App 保存到 sns_private/Pxx.jpg 后重跑 cards。", font=font(15), fill=MUTED)
    f = out / "poses_src.png"
    img.save(f, quality=92)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--public", action="store_true")
    a = ap.parse_args()
    plan, out = Path(a.plan), Path(a.out)
    data = json.loads((plan / "pose_refs.json").read_text(encoding="utf-8"))
    shots = {s["id"]: s for s in json.loads((plan / "shotlist.json").read_text(encoding="utf-8"))["shots"]}
    missing = sorted({sid for p in data.get("poses", []) for sid in p.get("shots", []) if sid not in shots})
    if missing:
        print("注意：pose_refs.json 里引用了不存在的分镜", missing)
    pages = render_pages(plan, out, data, shots, a.public)
    src = render_sources(out, data)
    print(f"姿势参考：{len(data.get('poses', []))} 个姿势，{len(pages)} 页 + 来源页 → {out}")


if __name__ == "__main__":
    main()
