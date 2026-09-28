#!/usr/bin/env python3
"""
sns_import.py　把用户自己保存的原帖图片收进 plans/<plan>/sns_private/，按编号改名。

用法：把图片丢进 plans/<plan>/sns_inbox/（手机保存后传到电脑、Win+Shift+S 截图另存都行），然后
  python pipeline.py sns-import <plan>            # 或 python tools/sns_import.py --plan plans/<plan>

对号规则：
  1. 文件名里带编号的（S06、s07_xxx、P03 截图.png）按编号收；
  2. 其余文件按保存时间先后，依次补给还缺原图的机位参考 S（姿势参考 P 已有线稿，只按文件名收），并打印对照表；
  3. --list 只列出还缺哪些、各自的链接，不移动文件。
收好的文件统一存成 <编号>.jpg（长边不超过 2000 px），原文件移到 sns_inbox/_done/。sns_private 已在 .gitignore 里。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image

EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp"}


def wanted(plan: Path) -> list[tuple[str, str, str]]:
    """(编号, 标题, 链接)：先 sns_refs 的 S，再 pose_refs 里各姿势对应的来源帖 P。"""
    out = []
    sr = plan / "sns_refs.json"
    if sr.exists():
        for r in json.loads(sr.read_text(encoding="utf-8")).get("refs", []):
            out.append((r["id"], r.get("title", ""), r.get("url", "")))
    pr = plan / "pose_refs.json"
    if pr.exists():
        d = json.loads(pr.read_text(encoding="utf-8"))
        posts = {p["id"]: p for p in d.get("posts", [])}
        for p in d.get("poses", []):
            post = posts.get(p.get("src"), {})
            out.append((p["id"], f"{p['name']}（{post.get('title', '')}）", post.get("url", "")))
    return out


def have(plan: Path, pid: str) -> bool:
    return any((plan / "sns_private" / f"{pid}{e}").exists() for e in (".jpg", ".jpeg", ".png", ".webp"))


def save_as(src: Path, dst: Path):
    im = Image.open(src)
    im = im.convert("RGB")
    im.thumbnail((2000, 2000))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    plan = Path(a.plan)
    W = wanted(plan)
    ids = {w[0] for w in W}
    missing = [w for w in W if not have(plan, w[0])]
    if a.list:
        ms = [w for w in missing if w[0].startswith("S")]
        mp = [w for w in missing if w[0].startswith("P")]
        print(f"分镜页还缺原图 {len(ms)} 张（机位参考，分镜卡上现在是二维码占位）：")
        for pid, title, url in ms:
            print(f"  {pid}  {title}  {url}")
        if mp:
            print(f"可选：姿势参考 {len(mp)} 个（已有线稿；想换原图时文件名要带编号，如 P09.jpg）：")
            for pid, title, url in mp:
                print(f"  {pid}  {title}  {url}")
        return
    inbox = plan / "sns_inbox"
    inbox.mkdir(exist_ok=True)
    files = sorted([f for f in inbox.iterdir() if f.is_file() and f.suffix.lower() in EXT], key=lambda f: f.stat().st_mtime)
    if not files:
        print(f"{inbox} 里没有图片。把保存好的原帖图片放进去再运行；还缺 {len(missing)} 张（加 --list 看清单）。")
        return
    done = inbox / "_done"; done.mkdir(exist_ok=True)
    queue = [w[0] for w in missing if w[0].startswith("S")]   # 没带编号的文件只补机位参考；姿势参考要在文件名里写编号
    moved = []
    rest = []
    for f in files:
        m = re.search(r"(?i)(?<![A-Za-z])([SP])(\d{2})(?!\d)", f.stem)
        pid = f"{m.group(1).upper()}{m.group(2)}" if m else None
        if pid in ids:
            rest_q = [q for q in queue if q != pid]
            queue = rest_q
            save_as(f, plan / "sns_private" / f"{pid}.jpg"); shutil.move(str(f), done / f.name)
            moved.append((f.name, pid, "按文件名"))
        else:
            rest.append(f)
    for f in rest:
        if not queue:
            print(f"  {f.name}：没有缺图的编号可对，留在 sns_inbox/")
            continue
        pid = queue.pop(0)
        save_as(f, plan / "sns_private" / f"{pid}.jpg"); shutil.move(str(f), done / f.name)
        moved.append((f.name, pid, "按保存顺序"))
    titles = {w[0]: w[1] for w in W}
    for name, pid, how in moved:
        print(f"  {name} → sns_private/{pid}.jpg（{how}）{titles.get(pid, '')}")
    left = [w for w in W if not have(plan, w[0])]
    print(f"收进 {len(moved)} 张；还缺 {len(left)} 张。接着运行：python pipeline.py cards {plan.name}")


if __name__ == "__main__":
    main()
