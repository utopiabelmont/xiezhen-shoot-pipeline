#!/usr/bin/env python3
"""
pipeline.py　外拍规划流水线的统一入口。每个阶段一个子命令，产物固定落在 plans/<plan>/ 下。

  python pipeline.py init    <plan> --place "箱根ガラスの森美術館" --date 2026-09-28 --arrive 13:00 --hours 12-18 [--lat --lon] [--elev-m 657] [--gear "..."]
  python pipeline.py spots   <plan> [--radius 1500]                       → spots.md / spots.json
  python pipeline.py sun     <plan> [--step 30]                           → sun.md / sun.json / sun_path.png
  python pipeline.py basemap <plan> [--name main] [--meters 130] [--center lat,lon] [--extra x.json]
                                                                          → basemaps/<name>_geometry.json / _osm.png / _meta.json
  python pipeline.py stylize <plan> [--name main]                         → basemaps/<name>_styled.png（需本机 codex-imagegen）
  python pipeline.py jobs    <plan>                                       → inbox/<plan>.jsonl（从 prompts.md 与 shotlist.json）
  python pipeline.py shots   <plan>                                       → out/<plan>/<id>.png + log.jsonl（run_shots.py）
  python pipeline.py cards   <plan> [--images out/<plan>]                 → cards/card_<id>.png + <日期>_<地点>_拍摄小抄.pdf
  python pipeline.py status  <plan>                                       → 各阶段产物清单

所有子命令都可加 --fixture 走离线样本（仅 spots / sun / basemap）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"
PLANS = ROOT / "plans"
PY = sys.executable


def plan_dir(name: str) -> Path:
    p = PLANS / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_plan(name: str) -> dict:
    f = PLANS / name / "plan.json"
    if not f.exists():
        raise SystemExit(f"缺少 {f}，先运行：python pipeline.py init {name} --place ... --date ...")
    return json.loads(f.read_text(encoding="utf-8"))


def run(cmd: list[str]) -> int:
    print("$", " ".join(str(c) for c in cmd))
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.call([str(c) for c in cmd], env=env)


def geo_args(plan: dict) -> list[str]:
    if plan.get("lat") is not None and plan.get("lon") is not None:
        return ["--lat", str(plan["lat"]), "--lon", str(plan["lon"]), "--place", plan["place"]]
    return ["--place", plan["place"]]


def pdf_name(meta: dict) -> str:
    """小抄 PDF 文件名：<出行日期>_<地点>_拍摄小抄[_vN].pdf。地点取 meta.place 括号前的部分，去掉文件名非法字符。"""
    place = re.split(r"[（(]", meta.get("place", "plan"))[0].strip()
    place = re.sub(r'[\\/:*?"<>|\s]+', "", place) or "plan"
    date = meta.get("date", "").strip() or "undated"
    m = re.search(r"\bv(\d+)", meta.get("version", ""))
    ver = f"_v{m.group(1)}" if m and int(m.group(1)) >= 2 else ""
    return f"{date}_{place}_拍摄小抄{ver}.pdf"


# ---------- stages ----------

def cmd_init(a):
    d = plan_dir(a.plan)
    plan = {"name": a.plan, "place": a.place, "date": a.date, "arrive": a.arrive, "hours": a.hours,
            "lat": a.lat, "lon": a.lon, "elev_m": a.elev_m, "gear": a.gear, "body": a.body, "flash": a.flash,
            "people": a.people, "outfit": a.outfit, "created": __import__("datetime").datetime.now().isoformat(timespec="seconds")}
    (d / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    for src, dst in [("shotlist_template.md", "shotlist_draft.md"), ("sns_research.md", "spots_social.md"),
                     ("timeline_template.md", "timeline.md"), ("arrival_checklist_template.md", "arrival_checklist.md"),
                     ("model_sheet_template.md", "model_sheet.md")]:
        s = ROOT / "templates" / src
        if s.exists() and not (d / dst).exists():
            shutil.copy(s, d / dst)
    print("plan.json 已写入", d)


def cmd_spots(a):
    plan = load_plan(a.plan)
    cmd = [PY, TOOLS / "spots.py", *geo_args(plan), "--radius", str(a.radius), "--out", PLANS / a.plan]
    if a.fixture:
        cmd.append("--fixture")
    return run(cmd)


def cmd_sun(a):
    plan = load_plan(a.plan)
    cmd = [PY, TOOLS / "sun_light.py", *geo_args(plan), "--date", plan["date"], "--hours", plan.get("hours") or "8-18",
           "--step", str(a.step), "--weather", "--terrain", "--out", PLANS / a.plan]
    if plan.get("elev_m") is not None:
        cmd += ["--elev-m", str(plan["elev_m"])]
    if a.fixture:
        cmd.append("--fixture")
    return run(cmd)


def cmd_basemap(a):
    plan = load_plan(a.plan)
    out = PLANS / a.plan / "basemaps"
    cmd = [PY, TOOLS / "osm_geometry.py", "--meters", str(a.meters), "--size", str(a.size), "--out", out, "--name", a.name]
    if a.center:
        lat, lon = a.center.split(",")
        cmd += ["--lat", lat, "--lon", lon]
    else:
        cmd += geo_args(plan)
    if a.extra:
        cmd += ["--extra", a.extra]
    if a.fixture:
        cmd += ["--fixture", a.fixture]
    return run(cmd)


def find_codex_imagegen() -> str | None:
    p = shutil.which("codex-imagegen")
    if p:
        return p
    for c in (Path.home() / ".local/bin/codex-imagegen.exe", Path.home() / ".local/bin/codex-imagegen"):
        if c.exists():
            return str(c)
    return None


def cmd_stylize(a):
    cli = find_codex_imagegen()
    if not cli:
        raise SystemExit("未找到 codex-imagegen，见 docs/WINDOWS_SETUP.md 出图安装一节")
    bm = PLANS / a.plan / "basemaps"
    src = bm / f"{a.name}_osm.png"
    if not src.exists():
        raise SystemExit(f"缺少 {src}，先运行 basemap 阶段")
    prompt = (ROOT / "templates" / "basemap_style_prompt.txt").read_text(encoding="utf-8").strip()
    if a.prompt_extra:
        prompt += " " + a.prompt_extra.strip()
    return run([cli, "edit", "--image", src, "--prompt", prompt, "--out", bm / f"{a.name}_styled.png",
                "--size", "1024x1024", "--quality", "high", "--input-max-edge", "1024", "--size-policy", "warn", "--force"])


def cmd_jobs(a):
    d = PLANS / a.plan
    shots = {s["id"]: s for s in json.loads((d / "shotlist.json").read_text(encoding="utf-8"))["shots"]}
    md = (d / "prompts.md").read_text(encoding="utf-8")
    # 每张：## <id>-<title> 标题后跟 ```text ... ``` 代码块
    blocks = re.findall(r"^##\s+(\S+)[^\n]*\n(?:.*?\n)*?```text\n(.*?)```", md, flags=re.M | re.S)
    if not blocks:
        raise SystemExit("prompts.md 里没有找到 `## <id>-<title>` + ```text 块")
    (ROOT / "inbox").mkdir(exist_ok=True)
    out = ROOT / "inbox" / f"{a.plan}.jsonl"
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for head, prompt in blocks:
            sid = head.split("-")[0]
            shot = shots.get(sid, {})
            job = {"id": head, "prompt": " ".join(prompt.split()), "size": shot.get("size", "1152x1536"), "quality": "high"}
            if shot.get("images"):
                job["images"] = shot["images"]; job["mode"] = "edit"
            f.write(json.dumps(job, ensure_ascii=False) + "\n"); n += 1
    print(f"{out}：{n} 条")


def cmd_shots(a):
    jobs = ROOT / "inbox" / f"{a.plan}.jsonl"
    if not jobs.exists():
        raise SystemExit(f"缺少 {jobs}，先运行 jobs 阶段")
    return run([PY, ROOT / "run_shots.py", "--jobs", jobs] + (["--dry-run"] if a.dry_run else []))


def cmd_cards(a):
    d = PLANS / a.plan
    images = Path(a.images) if a.images else ROOT / "out" / a.plan
    rc = run([PY, TOOLS / "make_cards.py", "--plan", d, "--images", images, "--out", d / "cards"])
    if rc == 0:
        try:
            from PIL import Image
            import PIL.JpegImagePlugin  # noqa: F401  注册 JPEG 保存器
            pngs = sorted((d / "cards").glob("card_*.png"))
            if pngs:
                meta = json.loads((d / "shotlist.json").read_text(encoding="utf-8")).get("meta", {})
                name = pdf_name(meta)
                ims = [Image.open(p).convert("RGB") for p in pngs]
                ims[0].save(d / name, save_all=True, append_images=ims[1:], resolution=150)
                for old in d.glob("*拍摄小抄*.pdf"):        # 只保留当前命名的一份
                    if old.name != name:
                        old.unlink()
                print(name, len(ims), "页")
        except Exception as e:  # PDF 只是附带产物
            print("PDF 未生成：", e)
    return rc


def cmd_status(a):
    d = PLANS / a.plan
    items = [("plan.json", "init"), ("spots.md", "spots"), ("spots_social.md", "SNS 调研（人工）"), ("sun.md", "sun"),
             ("basemaps/main_osm.png", "basemap"), ("basemaps/main_styled.png", "stylize"), ("shotlist.json", "分镜（人工/Claude）"),
             ("prompts.md", "prompt（nuyoah-xiezhen-prompt）"), ("timeline.md", "时间线"), ("model_sheet.md", "模特一页纸"),
             ("arrival_checklist.md", "到场清单"), ("cards", "cards")]
    tmpl = {"spots_social.md": "sns_research.md", "timeline.md": "timeline_template.md",
            "model_sheet.md": "model_sheet_template.md", "arrival_checklist.md": "arrival_checklist_template.md"}
    for f, stage in items:
        p = d / f
        ok = p.exists() and (any(p.iterdir()) if p.is_dir() else p.stat().st_size > 0)
        mark = "x" if ok else " "
        if ok and f in tmpl and (ROOT / "templates" / tmpl[f]).exists() and p.read_bytes() == (ROOT / "templates" / tmpl[f]).read_bytes():
            mark = "-"   # 还是模板原样，未填写
        print(f"  [{mark}] {stage:28s} {f}")
    print("  [x] 已完成  [-] 仍是模板未填写  [ ] 缺失")
    pdfs = sorted(d.glob("*拍摄小抄*.pdf"))
    print(f"  [{'x' if pdfs else ' '}] {'PDF':28s} {pdfs[0].name if pdfs else '<日期>_<地点>_拍摄小抄.pdf'}")
    jobs = ROOT / "inbox" / f"{a.plan}.jsonl"
    print(f"  [{'x' if jobs.exists() else ' '}] {'jobs':28s} inbox/{a.plan}.jsonl")
    out = ROOT / "out" / a.plan
    print(f"  [{'x' if out.exists() else ' '}] {'shots':28s} out/{a.plan}/ ({len(list(out.glob('*.png'))) if out.exists() else 0} 张)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("plan"); s.add_argument("--place", required=True); s.add_argument("--date", required=True)
    s.add_argument("--arrive", default=""); s.add_argument("--hours", default="8-18"); s.add_argument("--lat", type=float); s.add_argument("--lon", type=float)
    s.add_argument("--elev-m", type=float); s.add_argument("--gear", default="全画幅机身 + 24-105mm F4"); s.add_argument("--body", default="")
    s.add_argument("--flash", default=""); s.add_argument("--people", default="1 位成年女性"); s.add_argument("--outfit", default=""); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("spots"); s.add_argument("plan"); s.add_argument("--radius", type=int, default=1500); s.add_argument("--fixture", action="store_true"); s.set_defaults(fn=cmd_spots)
    s = sub.add_parser("sun"); s.add_argument("plan"); s.add_argument("--step", type=int, default=30); s.add_argument("--fixture", action="store_true"); s.set_defaults(fn=cmd_sun)
    s = sub.add_parser("basemap"); s.add_argument("plan"); s.add_argument("--name", default="main"); s.add_argument("--meters", type=float, default=200)
    s.add_argument("--size", type=int, default=1024); s.add_argument("--center"); s.add_argument("--extra"); s.add_argument("--fixture"); s.set_defaults(fn=cmd_basemap)
    s = sub.add_parser("stylize"); s.add_argument("plan"); s.add_argument("--name", default="main"); s.add_argument("--prompt-extra", default=""); s.set_defaults(fn=cmd_stylize)
    s = sub.add_parser("jobs"); s.add_argument("plan"); s.set_defaults(fn=cmd_jobs)
    s = sub.add_parser("shots"); s.add_argument("plan"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_shots)
    s = sub.add_parser("cards"); s.add_argument("plan"); s.add_argument("--images"); s.set_defaults(fn=cmd_cards)
    s = sub.add_parser("status"); s.add_argument("plan"); s.set_defaults(fn=cmd_status)

    a = ap.parse_args()
    rc = a.fn(a)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
