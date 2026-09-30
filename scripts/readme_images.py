#!/usr/bin/env python3
"""
readme_images.py　重出 README 用的配图（中文 / 英文 / 日文）。

  python scripts/readme_images.py --lang en            → docs/img/en/
  python scripts/readme_images.py --lang ja            → docs/img/ja/
  python scripts/readme_images.py --lang zh --out tmp  → 中文版（检查用；README 的中文配图在 docs/img/）

需要本机已有企划与出图结果：plans/hakone-0928-v5、plans/asakusa-0928、out/hakone-0928-v5、out/asakusa-0928、
out/moves-library-v2（运镜库逐帧图）。文字翻译查 locales/<lang>*.json（见 tools/i18n.py）。
示意图总览（hakone_v5_contact.jpg）与底图对比（basemap_before_after.jpg）没有文字，各语言共用 docs/img/ 里的原图。

Rebuilds the README figures in Chinese, English or Japanese from the local plans and generated images.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PY = sys.executable
BG = (247, 244, 236)

V5, ASAKUSA = "hakone-0928-v5", "asakusa-0928"
V5_GALLERY = ["03", "07", "10", "25"]
V5_HERO, V5_SUPPLEMENT, V5_MOVE = "07", "01", "11"
ASAKUSA_GALLERY = ["01", "04", "07", "11"]


def run(args, env, only=None):
    e = dict(env)
    if only:
        e["XIEZHEN_ONLY"] = ",".join(only)
    r = subprocess.run([PY, *map(str, args)], env=e, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-4000:])
        raise SystemExit(f"失败：{args[0]}")


def gallery(paths, cell, gap, out):
    from PIL import Image
    cw, ch = cell
    im = Image.new("RGB", (2 * cw + gap, 2 * ch + gap), BG)
    for k, p in enumerate(paths):
        c = Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS)
        im.paste(c, ((k % 2) * (cw + gap), (k // 2) * (ch + gap)))
    im.save(out, quality=88)


def jpg(src, out, size=None):
    from PIL import Image
    im = Image.open(src).convert("RGB")
    if size:
        im = im.resize(size, Image.LANCZOS)
    im.save(out, quality=88)


def checklist_shots(html_path, out, lang):
    """手机宽度两屏截图并排：左为开头（勾选几项），右为某一站展开一条短片的细节。"""
    from playwright.sync_api import sync_playwright
    from PIL import Image
    tmp = out.parent / "_cl"
    tmp.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 432, "height": 880}, device_scale_factor=1.55)
        pg.goto(html_path.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("""() => {
            const boxes = [...document.querySelectorAll('input[type=checkbox]')];
            [0, 1].forEach(i => boxes[i] && boxes[i].click());
        }""")
        pg.screenshot(path=str(tmp / "a.png"))
        pg.evaluate("""() => {
            const vids = [...document.querySelectorAll('details')].filter(d => /S&Q|24p/.test(d.textContent));
            const d = vids[0] || document.querySelector('details');
            if (d) { d.open = true; }
            const card = d ? d.closest('li') || d : null;
            const sec = d ? d.closest('section') : null;
            const boxes = [...(sec || document).querySelectorAll('input[type=checkbox]')];
            boxes.slice(0, 2).forEach(b => b.click());
            if (card) { card.scrollIntoView({block: 'start'}); }
            const bar = document.querySelector('.bar, nav, .filters');
            window.scrollBy(0, -((bar && bar.getBoundingClientRect().height) || 0) - 170);
        }""")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(tmp / "b.png"))
        b.close()
    a, c = Image.open(tmp / "a.png"), Image.open(tmp / "b.png")
    im = Image.new("RGB", (a.width + c.width + 3 * 16, a.height + 2 * 16), (232, 226, 214))
    im.paste(a, (16, 16)); im.paste(c, (a.width + 32, 16))
    im.save(out, quality=88)
    shutil.rmtree(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["zh", "en", "ja"])
    ap.add_argument("--out", help="默认 docs/img/<lang>/")
    ap.add_argument("--skip", default="", help="逗号分隔：cards,checklist,sun,moves")
    a = ap.parse_args()
    out = Path(a.out) if a.out else ROOT / "docs" / "img" / a.lang
    out.mkdir(parents=True, exist_ok=True)
    skip = set(filter(None, a.skip.split(",")))
    env = dict(os.environ, XIEZHEN_LANG=a.lang, PYTHONUTF8="1")
    work = ROOT / "out" / f"_readme-{a.lang}"
    work.mkdir(parents=True, exist_ok=True)
    pv5, pas = ROOT / "plans" / V5, ROOT / "plans" / ASAKUSA

    if "cards" not in skip:
        w5, wa = work / V5, work / ASAKUSA
        run([TOOLS / "make_cards.py", "--plan", pv5, "--images", ROOT / "out" / V5, "--out", w5, "--public"], env,
            only=sorted(set(V5_GALLERY + [V5_HERO, V5_SUPPLEMENT])))
        run([TOOLS / "make_outfit_page.py", "--plan", pv5, "--out", w5], env)
        run([TOOLS / "trip.py", "--plan", pv5, "--out", w5], env)
        speed = json.loads((pv5 / "shotlist.json").read_text(encoding="utf-8"))["meta"].get("route_speed_mps", 1.0)
        run([TOOLS / "route.py", "--plan", pv5, "--out", w5, "--speed", speed], env)
        run([TOOLS / "moves.py", "--plan", pv5, "--out", w5], env, only=[V5_MOVE])
        run([TOOLS / "make_cards.py", "--plan", pas, "--images", ROOT / "out" / ASAKUSA, "--out", wa, "--public"], env,
            only=ASAKUSA_GALLERY)
        gallery([w5 / f"card_{i}.png" for i in V5_GALLERY], (1000, 669), 0, out / "cards_gallery_v5.jpg")
        gallery([wa / f"card_{i}.png" for i in ASAKUSA_GALLERY], (800, 533), 10, out / "cards_gallery_asakusa.jpg")
        jpg(w5 / f"card_{V5_HERO}.png", out / "card_v5.jpg")
        jpg(w5 / f"card_{V5_SUPPLEMENT}.png", out / "card_v5_supplement.jpg")
        jpg(w5 / f"move_{V5_MOVE}.png", out / "move_page.jpg")
        jpg(w5 / "trip_01.png", out / "trip_page.jpg", (1400, 934))
        jpg(w5 / "route_01.png", out / "route_page.jpg")
        jpg(w5 / "outfit_01.png", out / "outfit_page.jpg", (1400, 934))
        from PIL import Image
        Image.open(w5 / f"card_{V5_HERO}.png").convert("RGB").crop((962, 322, 1562, 692)).save(out / "topview_detail.jpg", quality=90)

    if "checklist" not in skip:
        html = work / "checklist.html"
        run([TOOLS / "checklist.py", "--plan", pv5, "--images", ROOT / "out" / V5, "--public", "--out", html], env)
        checklist_shots(html, out / "checklist.jpg", a.lang)

    if "sun" not in skip:
        code = (
            "import json,sys,datetime as dt;sys.path.insert(0,r'%s');import sun_light as S;"
            "d=json.load(open(r'%s',encoding='utf-8'));t=d.get('terrain') or {};"
            "h=({**t,'horizon':{int(k):v for k,v in t['horizon'].items()}} if t.get('horizon') else None);"
            "S.draw(__import__('pathlib').Path(r'%s'),d['place'],dt.date.fromisoformat(d['date']),"
            "[r for r in d['rows'] if '12:00'<=r['time']<='18:00'],d['key_times'],h)"
        ) % (TOOLS, pv5 / "sun.json", out / "sun_path.png")
        r = subprocess.run([PY, "-c", code], env=env, cwd=TOOLS, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(r.stderr[-3000:])
        from PIL import Image
        sp = Image.open(out / "sun_path.png")
        sp.resize((1200, round(sp.height * 1200 / sp.width)), Image.LANCZOS).save(out / "sun_path.png")

    if "moves" not in skip:
        mv = out / "moves"
        mv.mkdir(exist_ok=True)
        run([TOOLS / "move_gif.py", "--library", ROOT / "out" / "moves-library-v2", "--out", mv], env)

    print("完成：", out)


if __name__ == "__main__":
    main()
