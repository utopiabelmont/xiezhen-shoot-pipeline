"""move_gif.py　把运镜的逐帧示意图合成动图：左边俯视图上相机与人物沿轨迹移动，右边是 Codex 按文字画的竖幅画面，关键帧之间交叉淡化。

两种用法：
  python tools/move_gif.py --library <帧目录> --out docs/img/moves
      运镜库（tools/moves_library_prompts.py 出的图）：裁切型用母版 <序号>m-<type>.png 按取景窗口连续平移缩放；
      其余用 <序号><a-d>-<type>.png 四帧（b–d 以起幅 a 为参考图生成）淡入淡出。每种运镜一张 GIF，另出一张总览 GIF。
  python tools/move_gif.py --plan plans/<plan> [--out plans/<plan>/cards]
      企划：短片的 move_frames/<id><a-c>-*.png，每条短片一张 move_<id>.gif（核对表与分享用）。
帧数不限（2–6 张），按文件名里的字母顺序排；关键帧在运镜进度上平均分布。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moves as M  # noqa: E402
from make_cards import BG, GREEN, INK, MUTED, PANEL, LINE, font  # noqa: E402

FADE = 4            # 相邻关键帧之间的过渡帧数
HOLD_MS = 700       # 关键帧停留
FADE_MS = 110


def crop916(im, w, h):
    im = im.convert("RGB")
    r = w / h
    if im.width / im.height > r:
        cw = int(im.height * r)
        im = im.crop(((im.width - cw) // 2, 0, (im.width - cw) // 2 + cw, im.height))
    else:
        ch = int(im.width / r)
        im = im.crop((0, (im.height - ch) // 2, im.width, (im.height - ch) // 2 + ch))
    return im.resize((w, h), Image.LANCZOS)


def top_base(P, w, h):
    """俯视轨迹底图（静态部分），并返回世界坐标 → 像素的函数，供逐帧画移动的图标。"""
    img = Image.new("RGB", (w, h), PANEL)
    M.draw_top(img, (0, 0, w, h), P, small=True)
    # 与 draw_top 相同的取景计算
    ts = [i / 20 for i in range(21)]
    S = [M.state(P, t) for t in ts]
    pts = [s["cam"] for s in S] + [s["subj"] for s in S]
    if P["type"] in ("tilt_down_reveal", "static_walk_out"):
        pts.append((0, P["walk"] * 1.6 + 0.6))
    if S[0]["obst"]:
        o = S[0]["obst"]; pts += [(o[0] - o[2], o[1] - o[2]), (o[0] + o[2], o[1] + o[2])]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 2.5) * 1.35
    sc = min(w, h) / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    X = lambda p: (w / 2 + (p[0] - cx) * sc, h / 2 - (p[1] - cy) * sc)
    return img, X


def live_marks(base, X, P, u):
    """在俯视图上画当前时刻的相机（带视野线）与人物。"""
    im = base.copy()
    d = ImageDraw.Draw(im)
    s = M.state(P, u)
    c, p = X(s["cam"]), X(s["subj"])
    half = math.degrees(math.atan(12 / P["f"]))
    L = s["dist"] * 1.1
    for sgn in (-1, 1):
        a = math.radians(s["yaw"] + sgn * half)
        d.line([c, X((s["cam"][0] + math.sin(a) * L, s["cam"][1] + math.cos(a) * L))], fill=M.CAM, width=2)
    r = 9
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=M.CAM, outline=(255, 255, 255), width=2)
    d.ellipse((p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8), fill=GREEN, outline=(255, 255, 255), width=2)
    fa = math.radians(s["face"])
    d.line([p, (p[0] + math.sin(fa) * 16, p[1] - math.cos(fa) * 16)], fill=GREEN, width=3)
    return im


def ease(x):
    return x * x * (3 - 2 * x)


def tile(title, sub, base, X, P, photo, u, lab, n_keys, tw, pw, ph):
    """动图的一帧：标题、俯视图（当前时刻的相机与人物）、竖幅画面、进度条。"""
    th = 44 + ph + 22
    topw = tw - pw - 34
    im = Image.new("RGB", (tw, th), BG)
    d = ImageDraw.Draw(im)
    d.text((12, 8), title, font=font(20, True), fill=GREEN)
    d.text((tw - 12 - d.textlength(sub, font=font(13)), 14), sub, font=font(13), fill=MUTED)
    im.paste(live_marks(base, X, P, u), (12, 44))
    d.rectangle((12, 44, 12 + topw, 44 + ph), outline=LINE)
    px = tw - 12 - pw
    im.paste(photo, (px, 44))
    d.rectangle((px - 1, 43, px + pw, 44 + ph), outline=INK, width=2)
    d.rectangle((px, 44, px + 24, 64), fill=M.VIDEO)
    d.text((px + 6, 45), lab, font=font(13, True), fill=(255, 255, 255))
    by = 44 + ph + 9
    d.rectangle((12, by, tw - 12, by + 5), fill=(222, 216, 204))
    d.rectangle((12, by, 12 + (tw - 24) * u, by + 5), fill=M.CAM)
    for j in range(n_keys):
        tx = 12 + (tw - 24) * j / max(1, n_keys - 1)
        d.ellipse((tx - 4, by - 2, tx + 4, by + 7), fill=M.CAM if j / max(1, n_keys - 1) <= u + 1e-6 else (200, 192, 178))
    return im


def build_frames(title, sub, P, photos, tw=480, pw=198, ph=352):
    """交叉淡化型：若干关键帧（同一人物与场景的连续画面），相邻两帧之间淡入淡出。返回 [(图, 毫秒)]。"""
    base, X = top_base(P, tw - pw - 34, ph)
    keys = [crop916(Image.open(f), pw, ph) for f in photos]
    n = len(keys)
    seq = []
    for k in range(n):
        steps = [(k, 0.0, HOLD_MS)]
        if k < n - 1:
            steps += [(k, (j + 1) / (FADE + 1), FADE_MS) for j in range(FADE)]
        for kk, a, ms in steps:
            u = (kk + a) / (n - 1) if n > 1 else 0.0
            photo = keys[kk] if a == 0 else Image.blend(keys[kk], keys[kk + 1], ease(a))
            lab = "起" if (kk == 0 and a == 0) else ("止" if kk == n - 1 else "中")
            seq.append((tile(title, sub, base, X, P, photo, ease(u), lab, n, tw, pw, ph), ms))
    return seq


def window(master, cx, cy, hf, pw, ph):
    """在母版上取 9:16 窗口：中心 (cx, cy) 与高度 hf 都按母版尺寸的比例，超出边界时推回图内。"""
    W, H = master.size
    h = hf * H
    w = h * pw / ph
    if w > W:
        w = W; h = w * ph / pw
    x0 = min(max(cx * W - w / 2, 0), W - w)
    y0 = min(max(cy * H - h / 2, 0), H - h)
    return master.resize((pw, ph), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h))


def build_crop(title, sub, P, master_path, path, tw=480, pw=198, ph=352, steps=18):
    """裁切型：在一张母版上按取景窗口路径连续平移、缩放，镜头运动是连续的。path = [(u, cx, cy, hf), ...]。"""
    base, X = top_base(P, tw - pw - 34, ph)
    master = Image.open(master_path).convert("RGB")

    def at(u):
        for (u0, *a), (u1, *b) in zip(path, path[1:]):
            if u0 <= u <= u1:
                s = ease((u - u0) / (u1 - u0)) if u1 > u0 else 0
                return [x + (y - x) * s for x, y in zip(a, b)]
        return path[-1][1:]

    seq = [(tile(title, sub, base, X, P, window(master, *at(0.0), pw, ph), 0.0, "起", 3, tw, pw, ph), HOLD_MS)]
    for k in range(1, steps):
        u = k / steps
        seq.append((tile(title, sub, base, X, P, window(master, *at(u), pw, ph), u, "中", 3, tw, pw, ph), 70))
    seq.append((tile(title, sub, base, X, P, window(master, *at(1.0), pw, ph), 1.0, "止", 3, tw, pw, ph), HOLD_MS + 300))
    return seq


def save_gif(seq, path, colors=192):
    ims = [im.convert("P", palette=Image.ADAPTIVE, colors=colors) for im, _ in seq]
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=[ms for _, ms in seq], loop=0, optimize=True, disposal=1)


def grid(seqs, cols, path, title=None, scale=0.66, step=130):
    """多个运镜并排成一张总览动图：按时间轴对齐（每 step 毫秒取各条当时的画面），短的一条停在末帧直到最长的一条播完。"""
    seqs = [[(im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS), ms) for im, ms in s] for s in seqs]
    tw, th = seqs[0][0][0].size
    head = 70 if title else 0
    rows = math.ceil(len(seqs) / cols)
    total = max(sum(ms for _, ms in s) for s in seqs)

    def frame_at(s, t):
        acc = 0
        for im, ms in s:
            acc += ms
            if t < acc:
                return im
        return s[-1][0]

    out = []
    t = 0
    while t < total:
        im = Image.new("RGB", (cols * tw + (cols + 1) * 10, head + rows * th + (rows + 1) * 10), BG)
        d = ImageDraw.Draw(im)
        if title:
            d.text((14, 12), title, font=font(26, True), fill=GREEN)
            d.text((14, 46), "左：俯视轨迹，橙点为相机、绿点为人物；右：同一人物与场景随运镜变化的竖幅画面，起 → 止", font=font(14), fill=MUTED)
        for k, s in enumerate(seqs):
            im.paste(frame_at(s, t), (10 + (k % cols) * (tw + 10), head + 10 + (k // cols) * (th + 10)))
        out.append((im, step))
        t += step
    out[-1] = (out[-1][0], 900)
    save_gif(out, path, colors=160)


LIB_SUB = {mt: f"{ex['lens'].split()[0]} · {ex['clip']['mode']} · {ex['clip']['dur_s']} s" for mt, ex in M.LIB_EXAMPLES.items()}


def library(frames_dir: Path, out: Path):
    """frames_dir 里：裁切型的母版 <序号>m-<type>.png；交叉淡化型的 <序号><a-d>-<type>.png（a 为起幅，b–d 以 a 为参考图）。"""
    import moves_library_prompts as L
    out.mkdir(parents=True, exist_ok=True)
    seqs = []
    for i, mt in enumerate(M.ORDER):
        ex = dict(M.LIB_EXAMPLES[mt]); ex["clip"] = dict(ex["clip"]); ex["clip"]["move_type"] = mt; ex["clip"]["move"] = M.TYPES[mt][0]
        ex.setdefault("kind", "全身")
        P = M.params(ex)
        master = frames_dir / f"{i + 1:02d}m-{mt}.png"
        if mt in L.RECIPES and master.exists():
            seq = build_crop(M.TYPES[mt][0], LIB_SUB[mt], P, master, L.RECIPES[mt])
            kind = "母版连续取景"
        else:
            photos = sorted(frames_dir.glob(f"{i + 1:02d}[a-f]-{mt}.png"))
            if len(photos) < 2:
                print("缺帧，跳过", mt)
                continue
            seq = build_frames(M.TYPES[mt][0], LIB_SUB[mt], P, photos)
            kind = f"{len(photos)} 帧淡入淡出"
        save_gif(seq, out / f"{i + 1:02d}_{mt}.gif")
        seqs.append(seq)
        print("gif", mt, kind)
    if seqs:
        grid(seqs, 3, out / "moves_library.gif", title="运镜库")
        print("总览", out / "moves_library.gif")


def plan(plan_dir: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    SL = json.loads((plan_dir / "shotlist.json").read_text(encoding="utf-8"))
    fd = plan_dir / "move_frames"
    for s in SL["shots"]:
        if s.get("medium") != "video" or not s.get("clip"):
            continue
        photos = sorted(fd.glob(f"{s['id']}[a-f]-*.png"))
        if len(photos) < 2:
            continue
        P = M.params(s)
        sub = f"{s.get('lens', '').split()[0]} · {s['clip'].get('mode', '')} · {s['clip'].get('dur_s', '')} s"
        seq = build_frames(f"{s['id']} {P['move']}", sub, P, photos)
        save_gif(seq, out / f"move_{s['id']}.gif")
        print("gif", s["id"], len(photos), "帧")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", help="运镜库逐帧图目录")
    ap.add_argument("--plan", help="企划目录（用 move_frames/）")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.library:
        library(Path(a.library), Path(a.out or "docs/img/moves"))
    elif a.plan:
        plan(Path(a.plan), Path(a.out or Path(a.plan) / "cards"))
    else:
        ap.error("给 --library 或 --plan")


if __name__ == "__main__":
    main()
