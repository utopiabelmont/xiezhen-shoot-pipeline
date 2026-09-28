"""renumber.py　分镜编号按游览路线重排：01 是路线上的第一张，依次往后；路线外的备选排在最后。

读：shotlist.json（必需）、route.json（先跑 pipeline.py route）。
改：shotlist.json（id、排序、meta.route_stops、按每站到达 / 离开时刻均分的 time）、
    outfit.json 的 per_shot、sns_refs.json 的 shots / use_by_shot、prompts.md 与 move_prompts.md 的 `## <id>-` 标题、
    move_frames/ 里 <id>a/b/c-*.png 的文件名。
写：id_map.json（新编号 → 旧编号），并列出正文里仍可能引用旧编号的字段（「同 09」「改 16」这类），需要手改。
已生成的示意图不改名：out/<plan>/ 里的图按旧编号，改完编号后重跑 jobs 与 shots，或用 --rename-images 一起改名。
"""
import argparse
import json
import re
from pathlib import Path


TMP = "__renum__"                                    # 两步改名，避免新旧编号互相覆盖


def tm(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def fm(x):
    return f"{int(x) // 60:02d}:{int(x) % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--images", help="示意图目录（默认 out/<plan>）；配合 --rename-images")
    ap.add_argument("--rename-images", action="store_true", help="把示意图文件名前两位也换成新编号")
    ap.add_argument("--keep-times", action="store_true", help="不按路线时刻重写每条的 time")
    a = ap.parse_args()
    d = Path(a.plan)
    SL = json.loads((d / "shotlist.json").read_text(encoding="utf-8"))
    shots = SL["shots"]
    R = json.loads((d / "route.json").read_text(encoding="utf-8"))
    order = [i for i in R.get("order", []) if any(s["id"] == i for s in shots)]
    rest = [s["id"] for s in shots if s["id"] not in order]
    new_of = {old: f"{k + 1:02d}" for k, old in enumerate(order + rest)}
    if all(k == v for k, v in new_of.items()):
        print("编号已经是路线顺序，不用改")
        return

    # 1. 分镜与路线停留点
    byold = {s["id"]: s for s in shots}
    for s in shots:
        s["id"] = new_of[s["id"]]
    shots.sort(key=lambda s: s["id"])
    for st in SL["meta"].get("route_stops", []):
        st["shots"] = [new_of.get(i, i) for i in st.get("shots", [])]
    if not a.keep_times:                               # 每站的到达—离开时段按分镜数均分
        for st in R.get("stops", []):
            ids = [new_of[i] for i in st.get("shots", []) if i in new_of]
            if not ids or not st.get("arrive") or not st.get("leave"):
                continue
            t0, t1 = tm(st["arrive"]), tm(st["leave"])
            step = (t1 - t0) / len(ids)
            for k, i in enumerate(ids):
                s = next(x for x in shots if x["id"] == i)
                s["time"] = f"{fm(round(t0 + k * step))}–{fm(round(t0 + (k + 1) * step))}"
    (d / "shotlist.json").write_text(json.dumps(SL, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "id_map.json").write_text(json.dumps({v: k for k, v in new_of.items()}, indent=1), encoding="utf-8")

    # 2. 按编号索引的附属文件
    p = d / "outfit.json"
    if p.exists():
        o = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(o.get("per_shot"), dict):
            o["per_shot"] = dict(sorted((new_of.get(k, k), v) for k, v in o["per_shot"].items()))
            p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    p = d / "sns_refs.json"
    if p.exists():
        sr = json.loads(p.read_text(encoding="utf-8"))
        for r in sr.get("refs", []):
            r["shots"] = sorted(new_of.get(i, i) for i in r.get("shots", []))
            if isinstance(r.get("use_by_shot"), dict):
                r["use_by_shot"] = {new_of.get(k, k): v for k, v in r["use_by_shot"].items()}
        p.write_text(json.dumps(sr, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in ("prompts.md", "move_prompts.md"):
        p = d / name
        if p.exists():
            txt = p.read_text(encoding="utf-8")
            txt = re.sub(r"^## (\d{2})([a-c]?)-", lambda m: f"## {new_of.get(m.group(1), m.group(1))}{m.group(2)}-", txt, flags=re.M)
            p.write_text(txt, encoding="utf-8")
    mf = d / "move_frames"
    if mf.exists():
        moves = [(f, new_of.get(f.name[:2], f.name[:2]) + f.name[2:]) for f in mf.glob("[0-9][0-9][a-c]-*.png")]
        for f, n in moves:
            f.rename(f.with_name(TMP + n))
        for f in mf.glob(TMP + "*"):
            f.rename(f.with_name(f.name[len(TMP):]))
    if a.rename_images:
        img = Path(a.images) if a.images else d.parent.parent / "out" / d.name
        pairs = [(f, new_of.get(f.name[:2], f.name[:2]) + f.name[2:]) for f in img.glob("[0-9][0-9]-*.*")]
        for f, n in pairs:
            f.rename(f.with_name(TMP + n))
        for f in img.glob(TMP + "*"):
            f.rename(f.with_name(f.name[len(TMP):]))

    # 3. 正文里可能引用旧编号的地方
    refs = []
    for s in shots:
        for k, v in s.items():
            if isinstance(v, str) and k not in ("id", "time", "alt_time", "size", "lens", "shutter") \
                    and re.search(r"(同|改|接|见|相机版是|改拍|换成)\s?\d{2}(?!\d|:|\s?(m|mm|秒|分|张|°))", v):
                refs.append(f"  {s['id']}.{k}：{v[:60]}")
    moved = sum(1 for k, v in new_of.items() if k != v)
    print(f"已按路线重排编号：{moved} 条换了号，对照表 id_map.json（新 → 旧）")
    if refs:
        print("以下字段里的编号可能还是旧的，请手改：")
        print("\n".join(refs))
    print("之后重跑：pipeline.py route / jobs / cards")


if __name__ == "__main__":
    main()
