#!/usr/bin/env python3
"""
pipeline.py　外拍规划流水线的统一入口。每个阶段一个子命令，产物固定落在 plans/<plan>/ 下。

  python pipeline.py init    <plan> --place "箱根ガラスの森美術館" --date 2026-09-28 --arrive 13:00 --hours 12-18 [--lat --lon] [--elev-m 657] [--gear "..."]
  python pipeline.py spots   <plan> [--radius 1500]                       → spots.md / spots.json
  python pipeline.py sun     <plan> [--step 30] [--weather-only] [--weather-json f]  → sun.md / sun.json / sun_path.png（--weather-only 只刷新预报）
  python pipeline.py palette <plan> [--images dir] [--n 12]               → palette.json / palette.png（场地主色，阶段 2b 穿搭依据）
  python pipeline.py outfit  <plan>                                       → 按 outfit.json 渲染 cards/outfit_01.png（cards 阶段也会自动做）
  python pipeline.py route   <plan> [--speed 1.0] [--basemap main]        → 按 meta.route_stops 沿底图步道算游览路线 → route.json / route.md / cards/route_01.png
  python pipeline.py trip    <plan>                                       → 按 trip.json 画一日多景点行程页 cards/trip_01.png（cards 阶段也会自动做）
  python pipeline.py basemap <plan> [--name main] [--meters 130] [--center lat,lon] [--extra x.json]
                                                                          → basemaps/<name>_geometry.json / _osm.png / _meta.json
  python pipeline.py stylize <plan> [--name main]                         → basemaps/<name>_styled.png（需本机 codex-imagegen）
  python pipeline.py lint    <plan>                                       → 按 docs/SHOT_DESIGN.md 检查 shotlist.json（景别配比、叙事角色、节奏、姿态视线）
  python pipeline.py jobs    <plan> [--missing]                           → inbox/<plan>.jsonl（从 prompts.md 与 shotlist.json；--missing 只排还没出图的）
  python pipeline.py shots   <plan>                                       → out/<plan>/<id>.png + log.jsonl（run_shots.py）
  python pipeline.py cards   <plan> [--images out/<plan>]                 → cards/card_<id>.png + <日期>_<地点>_拍摄脚本.pdf
  python pipeline.py checklist <plan> [--no-thumbs]                      → <日期>_<地点>_拍摄核对表.html（现场勾选用；cards 阶段也会自动做）
  python pipeline.py sns-import <plan> [--list]                          → 把 sns_inbox/ 里自己保存的原帖图片按编号收进 sns_private/
  python pipeline.py status  <plan>                                       → 各阶段产物清单
  python pipeline.py register [--root PATH] [--show]                      → 把仓库路径登记到 ~/.xiezhen-pipeline/config.json（skill 据此找到本机仓库）

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
    """PDF 文件名：<出行日期>_<地点>_拍摄脚本[_vN].pdf。地点取 meta.place 括号前的部分，去掉文件名非法字符。"""
    place = re.split(r"[（(]", meta.get("place", "plan"))[0].strip()
    place = re.sub(r'[\\/:*?"<>|\s]+', "", place) or "plan"
    date = meta.get("date", "").strip() or "undated"
    m = re.search(r"\bv(\d+)", meta.get("version", ""))
    ver = f"_v{m.group(1)}" if m and int(m.group(1)) >= 2 else ""
    return f"{date}_{place}_拍摄脚本{ver}.pdf"


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
    if a.weather_only:
        cmd.append("--weather-only")
    if a.weather_json:
        cmd += ["--weather-json", a.weather_json]
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
    if cmd_lint(a) != 0 and not getattr(a, "force", False):
        raise SystemExit("分镜未通过基本法硬性检查；修正后再生成任务，或加 --force 跳过")
    d = PLANS / a.plan
    shots = {s["id"]: s for s in json.loads((d / "shotlist.json").read_text(encoding="utf-8"))["shots"]}
    md = (d / "prompts.md").read_text(encoding="utf-8")
    # 每张：## <id>-<title> 标题后跟 ```text ... ``` 代码块
    blocks = re.findall(r"^##\s+(\S+)[^\n]*\n(?:.*?\n)*?```text\n(.*?)```", md, flags=re.M | re.S)
    if not blocks:
        raise SystemExit("prompts.md 里没有找到 `## <id>-<title>` + ```text 块")
    (ROOT / "inbox").mkdir(exist_ok=True)
    out = ROOT / "inbox" / f"{a.plan}.jsonl"
    done = {p.name[:2] for p in (ROOT / "out" / a.plan).glob("*.png")} if getattr(a, "missing", False) else set()
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for head, prompt in blocks:
            sid = head.split("-")[0]
            if sid in done:
                continue
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
    rc = run([PY, TOOLS / "make_cards.py", "--plan", d, "--images", images, "--out", d / "cards"] + (["--public"] if getattr(a, "public", False) else []))
    if rc == 0 and (d / "outfit.json").exists():
        run([PY, TOOLS / "make_outfit_page.py", "--plan", d, "--out", d / "cards"])
    if rc == 0 and (d / "trip.json").exists():
        run([PY, TOOLS / "trip.py", "--plan", d, "--out", d / "cards"])
    plan = json.loads((d / "shotlist.json").read_text(encoding="utf-8"))
    if rc == 0 and plan.get("meta", {}).get("route_stops"):
        run([PY, TOOLS / "route.py", "--plan", d, "--out", d / "cards", "--speed", str(plan["meta"].get("route_speed_mps", 1.0))])
    per_shot_src = any("src" in x for x in plan.get("shots", []))   # 分镜各自带来源（v5 起）时，不再单出参考机位汇总页
    if per_shot_src:
        for old in (d / "cards").glob("sns_[0-9]*.png"):
            old.unlink()
    if rc == 0 and (d / "sns_refs.json").exists() and not per_shot_src:
        run([PY, TOOLS / "sns_refs.py", "--plan", d, "--out", d / "cards"])    # SNS 参考机位页（在路线之后跑，按游览顺序）
    if rc == 0 and (d / "pose_refs.json").exists():
        run([PY, TOOLS / "poses.py", "--plan", d, "--out", d / "cards"] + (["--public"] if getattr(a, "public", False) else []))   # 姿势参考页
    if rc == 0 and any(x.get("medium") == "video" for x in plan.get("shots", [])):
        run([PY, TOOLS / "moves.py", "--plan", d, "--out", d / "cards"])      # 短片运镜示意页与短片一览（在路线之后跑，一览按游览顺序）
    if rc == 0:
        try:
            from PIL import Image
            import PIL.JpegImagePlugin  # noqa: F401  注册 JPEG 保存器
            medium = {s["id"]: s.get("medium", "still") for s in plan["shots"]}
            cards = {p.stem[5:]: p for p in (d / "cards").glob("card_*.png")}
            moves = {p.stem[5:]: p for p in (d / "cards").glob("move_*.png")}
            order = []
            if (d / "route.json").exists():                # 有路线：全部分镜按游览顺序
                order = [i for i in json.loads((d / "route.json").read_text(encoding="utf-8")).get("order", []) if i in cards]
            rest = [i for i in sorted(cards) if i not in order]
            rest = [i for i in rest if medium.get(i, "still") == "still"] + [i for i in rest if medium.get(i, "still") != "still"]
            pngs = (sorted((d / "cards").glob("trip_*.png")) + sorted((d / "cards").glob("outfit_*.png"))
                    + sorted((d / "cards").glob("route_*.png")) + sorted((d / "cards").glob("sns_[0-9]*.png"))
                    + sorted((d / "cards").glob("poses_[0-9]*.png")) + sorted((d / "cards").glob("poses_src.png"))
                    + [q for i in order + rest for q in [cards[i], moves.get(i)] if q])   # 行程 → 穿搭 → 路线 → 参考机位 → 姿势参考 → 分镜（按路线顺序，短片卡后接运镜页；无路线则静态在前）；短片一览只进核对表
            if pngs:
                meta = plan.get("meta", {})
                name = pdf_name(meta)
                ims = [Image.open(p).convert("RGB") for p in pngs]
                ims[0].save(d / name, save_all=True, append_images=ims[1:], resolution=150)
                for old in [*d.glob("*拍摄脚本*.pdf"), *d.glob("*拍摄脚本*.pdf")]:   # 只保留当前命名的一份（含 1.3 以前的旧名）
                    if old.name != name:
                        old.unlink()
                print(name, len(ims), "页")
        except Exception as e:  # PDF 只是附带产物
            print("PDF 未生成：", e)
        run([PY, TOOLS / "checklist.py", "--plan", d, "--images", images] + (["--public"] if getattr(a, "public", False) else []))   # 现场核对表（HTML）
    return rc


def cmd_checklist(a):
    d = PLANS / a.plan
    cmd = [PY, TOOLS / "checklist.py", "--plan", d]
    if getattr(a, "images", None):
        cmd += ["--images", a.images]
    if getattr(a, "no_thumbs", False):
        cmd.append("--no-thumbs")
    return run(cmd)


def cmd_palette(a):
    d = PLANS / a.plan
    cmd = [PY, TOOLS / "palette.py", "--plan", d, "--n", str(a.n)]
    if a.images:
        cmd += ["--images", a.images]
    if a.offline:
        cmd.append("--offline")
    return run(cmd)


def cmd_route(a):
    d = PLANS / a.plan
    return run([PY, TOOLS / "route.py", "--plan", d, "--out", d / "cards", "--speed", str(a.speed), "--basemap", a.basemap])


def cmd_trip(a):
    d = PLANS / a.plan
    if not (d / "trip.json").exists():
        raise SystemExit(f"缺少 {d / 'trip.json'}（模板：templates/trip_template.md）")
    return run([PY, TOOLS / "trip.py", "--plan", d, "--out", d / "cards"])


def cmd_outfit(a):
    d = PLANS / a.plan
    if not (d / "outfit.json").exists():
        raise SystemExit(f"缺少 {d / 'outfit.json'}（模板：templates/outfit_template.md）")
    return run([PY, TOOLS / "make_outfit_page.py", "--plan", d, "--out", d / "cards"])


# ---------- lint：分镜基本法（docs/SHOT_DESIGN.md） ----------

KIND_ORDER = ["远景", "全身", "七分", "半身", "近景", "特写"]


def kind_of(shot: dict) -> str:
    k = shot.get("kind", "")
    if "远景" in k or "环境" in k and "全身" not in k:
        return "远景"
    for key, name in (("特写", "特写"), ("近景", "近景"), ("半身", "半身"), ("七分", "七分"), ("中景", "七分"), ("全身", "全身")):
        if key in k:
            return name
    return "其它"


def focal_band(shot: dict) -> str:
    m = re.search(r"(\d{2,3})\s*(?:[–-]\s*(\d{2,3}))?\s*mm", shot.get("lens", ""))
    if not m:
        return "?"
    f = int(m.group(1))
    return "广" if f <= 35 else ("标" if f < 70 else "中长")


def outfit_checks(d: Path):
    """docs/OUTFIT_GUIDE.md 的两条可算规则：服装色 ≤ 3 色；主色与场地主色的 ΔE 不能太近。"""
    sys.path.insert(0, str(TOOLS))
    from palette import rgb_to_lab, delta_e  # type: ignore
    o = json.loads((d / "outfit.json").read_text(encoding="utf-8"))
    out = []
    cols = o.get("colors", [])
    if len([c for c in cols if not c.get("accent")]) > 3:
        out.append(f"穿搭主色 {len(cols)} 个，全身不超过 3 色（点缀色标 accent: true 不计）")
    if (d / "palette.json").exists():
        pal = json.loads((d / "palette.json").read_text(encoding="utf-8")).get("colors", [])[:4]
        for c in cols:
            h = c["hex"].lstrip("#"); lab = rgb_to_lab(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
            de, sc = min(((delta_e(lab, p["lab"]), p) for p in pal), key=lambda t: t[0])
            if de < 12 and not c.get("blend_ok"):
                out.append(f"穿搭「{c.get('name', c['hex'])}」与场地主色 {sc['name']} ΔE {de:.0f}，会融进背景（有意为之就标 blend_ok: true）")
    return out


def cmd_lint(a):
    d = PLANS / a.plan
    plan = json.loads((d / "shotlist.json").read_text(encoding="utf-8"))
    all_shots = plan["shots"]
    hard, soft = [], []
    MEDIA = ("still", "burst", "video", "live")
    for s in all_shots:
        m = s.get("medium", "still")
        if m not in MEDIA:
            hard.append(f"{s['id']} medium「{m}」不在 {MEDIA}")
        if m == "video":
            c = s.get("clip", {})
            for k in ("mode", "move", "start", "end"):
                if not c.get(k):
                    hard.append(f"{s['id']} 短片缺 clip.{k}")
            if c.get("mode") and c["mode"] not in ("24p", "sq60", "sq120"):
                hard.append(f"{s['id']} clip.mode 只能是 24p / sq60 / sq120")
    # 短片与手机实况是补充素材，不计入张数、景别配比与顺序；连拍出的是照片，计入
    shots = [s for s in all_shots if s.get("medium", "still") in ("still", "burst")]
    extras = [s for s in all_shots if s.get("medium", "still") in ("video", "live")]
    main = [s for s in shots if not s.get("optional") and not s.get("supplement")]   # 备选与补充分镜不参与首尾与相邻检查
    n = len(shots)
    bursts = [s["id"] for s in shots if s.get("medium") == "burst"]
    if len(bursts) < 2:
        soft.append(f"连拍抓动态（medium: burst）只有 {len(bursts)} 张，建议至少 2 张给组图加动感")
    nv = sum(1 for s in extras if s.get("medium") == "video"); nl = sum(1 for s in extras if s.get("medium") == "live")
    if nv < 5:
        soft.append(f"短片（medium: video）只有 {nv} 条，建议至少 5 条（六个叙事角色各一）")
    if nl < 6:
        soft.append(f"手机实况（medium: live）只有 {nl} 条，建议至少 6 条（过渡、候场、室内、主要机位）")
    if (d / "outfit.json").exists():
        try:
            soft += outfit_checks(d)
        except Exception as e:  # noqa: BLE001
            soft.append(f"outfit.json 检查失败：{e}")
    if n < 9:
        hard.append(f"张数 {n} < 9")
    roles = [s.get("role", "") for s in main]
    if not roles or roles[0] != "opening":
        hard.append("第一张的 role 应为 opening（开场：交代环境）")
    if not roles or roles[-1] != "closing":
        hard.append("最后一张的 role 应为 closing（收尾：背影/远眺/离开）")
    heroes = [s["id"] for s in shots if s.get("hero") or s.get("role") == "hero"]
    if not heroes:
        hard.append("没有主图：至少一张 hero: true")
    if roles.count("interaction") < 2:
        hard.append(f"interaction（互动/动作）只有 {roles.count('interaction')} 张，至少 2")
    if roles.count("detail") < 1:
        hard.append("没有 detail（细节/特写）")
    kinds = [kind_of(s) for s in shots]
    cover = {k for k in kinds if k in KIND_ORDER}
    if len(cover) < 4:
        hard.append(f"景别只覆盖 {sorted(cover)}，至少 4 类")
    for k in KIND_ORDER:
        c = kinds.count(k)
        if c > 0.4 * n:
            hard.append(f"景别「{k}」占 {c}/{n}，超过 40%")
    mins = {"远景": 1, "全身": 2, "半身": 2, "近景": 1, "特写": 1}
    for k, m in mins.items():
        if kinds.count(k) < m:
            soft.append(f"景别「{k}」{kinds.count(k)} 张，建议至少 {m}")
    if kinds.count("七分") < 1:
        soft.append("没有七分/中景，建议至少 1 张")
    bands = {focal_band(s) for s in shots} - {"?"}
    if len(bands) < 3:
        hard.append(f"焦段只有 {sorted(bands)}，需要 广(≤35)/标(50)/中长(70–105) 三档")
    poses = {s.get("pose", "") for s in shots} - {""}
    if len(poses) < 3:
        hard.append(f"姿态只有 {sorted(poses)}，至少三种（stand/walk/sit/lean/back/crouch）")
    gazes = [s.get("gaze", "") for s in shots]
    if "camera" not in gazes or not any(g in ("away", "down", "closed", "back") for g in gazes):
        hard.append("视线要同时有看镜头（camera）和不看镜头（away/down/closed/back）")
    elif gazes.count("camera") > 0.6 * n:
        soft.append(f"看镜头 {gazes.count('camera')}/{n}，超过 60%")
    mk = [kind_of(s) for s in main]
    for i in range(1, len(main)):
        if mk[i] == mk[i - 1] and mk[i] != "其它":
            soft.append(f"{main[i-1]['id']}→{main[i]['id']} 相邻景别相同（{mk[i]}），寄り/引き 交替")
        if focal_band(main[i]) == focal_band(main[i - 1]) and abs(main[i].get("cam_bearing", 0) - main[i - 1].get("cam_bearing", 0)) < 30:
            soft.append(f"{main[i-1]['id']}→{main[i]['id']} 相邻焦段档与机位方向都相同")
    if not any(("俯" in s.get("camera", "") or "仰" in s.get("camera", "")) for s in shots):
        soft.append("没有俯拍或仰拍机位，至少一张非眼平")
    if sum(1 for s in shots if s.get("fg_bg") and "前景" in s["fg_bg"] and "前景空" not in s["fg_bg"]) < 2:
        soft.append("有前景层次的分镜少于 2 张")
    if not any(("逆光" in s.get("light", "")) for s in shots):
        soft.append("没有逆光/侧逆光（晴天版也算），建议至少 1 张")
    print(f"分镜 lint：{a.plan}，{n} 张照片（主线 {len(main)}，备选 {n - len(main)}，连拍 {len(bursts)}）"
          + (f"，另有 短片 {sum(1 for s in extras if s.get('medium') == 'video')} 条 / 实况 {sum(1 for s in extras if s.get('medium') == 'live')} 条" if extras else ""))
    print("  景别：" + "，".join(f"{k} {kinds.count(k)}" for k in KIND_ORDER if kinds.count(k)) + (f"，其它 {kinds.count('其它')}" if kinds.count("其它") else ""))
    print("  焦段档：" + "，".join(sorted(bands)) + "　姿态：" + "，".join(sorted(poses)) + "　主图：" + ",".join(heroes))
    for h in hard:
        print("  [硬] " + h)
    for w in soft:
        print("  [提示] " + w)
    if not hard and not soft:
        print("  通过，无提示")
    return 1 if hard else 0


def cmd_sns_import(a):
    return run([PY, TOOLS / "sns_import.py", "--plan", PLANS / a.plan] + (["--list"] if a.list else []))


def cmd_status(a):
    d = PLANS / a.plan
    items = [("plan.json", "init"), ("spots.md", "spots"), ("spots_social.md", "SNS 调研（人工）"), ("palette.json", "palette（场地色）"), ("outfit.json", "穿搭（Claude）"), ("sun.md", "sun"), ("route.json", "路线（route）"), ("trip.json", "行程（Claude）"),
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
    pdfs = sorted(d.glob("*拍摄脚本*.pdf"))
    print(f"  [{'x' if pdfs else ' '}] {'PDF':28s} {pdfs[0].name if pdfs else '<日期>_<地点>_拍摄脚本.pdf'}")
    hts = sorted(d.glob("*拍摄核对表*.html"))
    print(f"  [{'x' if hts else ' '}] {'核对表':28s} {hts[0].name if hts else '<日期>_<地点>_拍摄核对表.html'}")
    jobs = ROOT / "inbox" / f"{a.plan}.jsonl"
    print(f"  [{'x' if jobs.exists() else ' '}] {'jobs':28s} inbox/{a.plan}.jsonl")
    out = ROOT / "out" / a.plan
    print(f"  [{'x' if out.exists() else ' '}] {'shots':28s} out/{a.plan}/ ({len(list(out.glob('*.png'))) if out.exists() else 0} 张)")


CONFIG = Path(os.environ.get("XIEZHEN_CONFIG") or Path.home() / ".xiezhen-pipeline" / "config.json")


def cmd_register(a):
    """登记本机仓库路径。setup.cmd 结束时自动调用；换目录后重新跑一次即可。"""
    import datetime, platform
    if a.show:
        if CONFIG.exists():
            print(CONFIG); print(CONFIG.read_text(encoding="utf-8"))
        else:
            print(f"未登记：{CONFIG} 不存在。先跑 python pipeline.py register")
        return 0 if CONFIG.exists() else 1
    root = Path(a.root).expanduser().resolve() if a.root else ROOT
    if not (root / "pipeline.py").exists():
        print(f"{root} 下没有 pipeline.py，不是仓库根目录"); return 1
    venv = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    cfg = {"root": str(root), "python": str(venv if venv.exists() else Path(PY).resolve()),
           "platform": platform.system(), "registered_at": datetime.date.today().isoformat()}
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已登记 → {CONFIG}")
    for k, v in cfg.items(): print(f"  {k:14s} {v}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("plan"); s.add_argument("--place", required=True); s.add_argument("--date", required=True)
    s.add_argument("--arrive", default=""); s.add_argument("--hours", default="8-18"); s.add_argument("--lat", type=float); s.add_argument("--lon", type=float)
    s.add_argument("--elev-m", type=float); s.add_argument("--gear", default="全画幅机身 + 24-105mm F4"); s.add_argument("--body", default="")
    s.add_argument("--flash", default=""); s.add_argument("--people", default="1 位成年女性"); s.add_argument("--outfit", default=""); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("spots"); s.add_argument("plan"); s.add_argument("--radius", type=int, default=1500); s.add_argument("--fixture", action="store_true"); s.set_defaults(fn=cmd_spots)
    s = sub.add_parser("sun"); s.add_argument("plan"); s.add_argument("--step", type=int, default=30); s.add_argument("--fixture", action="store_true"); s.add_argument("--weather-only", action="store_true"); s.add_argument("--weather-json"); s.set_defaults(fn=cmd_sun)
    s = sub.add_parser("basemap"); s.add_argument("plan"); s.add_argument("--name", default="main"); s.add_argument("--meters", type=float, default=200)
    s.add_argument("--size", type=int, default=1024); s.add_argument("--center"); s.add_argument("--extra"); s.add_argument("--fixture"); s.set_defaults(fn=cmd_basemap)
    s = sub.add_parser("stylize"); s.add_argument("plan"); s.add_argument("--name", default="main"); s.add_argument("--prompt-extra", default=""); s.set_defaults(fn=cmd_stylize)
    s = sub.add_parser("jobs"); s.add_argument("plan"); s.add_argument("--force", action="store_true"); s.add_argument("--missing", action="store_true"); s.set_defaults(fn=cmd_jobs)
    s = sub.add_parser("shots"); s.add_argument("plan"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_shots)
    s = sub.add_parser("cards"); s.add_argument("plan"); s.add_argument("--images"); s.add_argument("--public", action="store_true", help="公开版：不放 sns_private 原帖截图（放进 examples / 推到 GitHub 前用）"); s.set_defaults(fn=cmd_cards)
    s = sub.add_parser("lint"); s.add_argument("plan"); s.set_defaults(fn=cmd_lint)
    s = sub.add_parser("checklist"); s.add_argument("plan"); s.add_argument("--images"); s.add_argument("--no-thumbs", action="store_true"); s.set_defaults(fn=cmd_checklist)
    s = sub.add_parser("palette"); s.add_argument("plan"); s.add_argument("--images"); s.add_argument("--n", type=int, default=12); s.add_argument("--offline", action="store_true"); s.set_defaults(fn=cmd_palette)
    s = sub.add_parser("outfit"); s.add_argument("plan"); s.set_defaults(fn=cmd_outfit)
    s = sub.add_parser("route"); s.add_argument("plan"); s.add_argument("--speed", type=float, default=1.0); s.add_argument("--basemap", default="main"); s.set_defaults(fn=cmd_route)
    s = sub.add_parser("trip"); s.add_argument("plan"); s.set_defaults(fn=cmd_trip)
    s = sub.add_parser("sns-import"); s.add_argument("plan"); s.add_argument("--list", action="store_true"); s.set_defaults(fn=cmd_sns_import)
    s = sub.add_parser("status"); s.add_argument("plan"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("register"); s.add_argument("--root"); s.add_argument("--show", action="store_true"); s.set_defaults(fn=cmd_register)

    a = ap.parse_args()
    rc = a.fn(a)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
