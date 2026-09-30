#!/usr/bin/env python3
"""
写真提示词 → Codex 生图 接力脚本

用法：
  python run_shots.py                         # 处理 inbox/ 下全部 *.jsonl
  python run_shots.py --jobs inbox/x.jsonl    # 只处理一个批次
  python run_shots.py --watch                 # 常驻，每 15 秒扫描 inbox/
  python run_shots.py --dry-run               # 只打印命令，不出图

jsonl 每行一个任务：
  {"id":"P01","prompt":"...","size":"1152x1536","quality":"high",
   "images":["refs/a.jpg","refs/b.jpg"],"mode":"edit"}
  id 必填；prompt 必填；size 默认 1152x1536（3:4）；quality 默认 high；
  images 存在时默认走 edit（参考图生图），最多 5 张。

规则：每条 prompt 只提交一次，失败只记录，不改词、不自动重试。
产物：out/<批次名>/<id>.png、<id>.txt（本张完整 prompt）、log.jsonl（追溯记录）。
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INBOX, OUT, DONE = ROOT / "inbox", ROOT / "out", ROOT / "done"
DEFAULT_SIZE, DEFAULT_QUALITY = "1152x1536", "high"


def load_jobs(path: Path):
    jobs = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            j = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"  [跳过] 第 {n} 行不是合法 JSON：{e}")
            continue
        if not j.get("id") or not str(j.get("prompt", "")).strip():
            print(f"  [跳过] 第 {n} 行缺少 id 或 prompt")
            continue
        jobs.append(j)
    return jobs


def build_cmd(cli: str, job: dict, out_png: Path, prompt_file: Path):
    images = [ROOT / p for p in job.get("images") or []]
    mode = job.get("mode") or ("edit" if images else "generate")
    cmd = [cli, mode, "--prompt-file", str(prompt_file), "--out", str(out_png),
           "--size", job.get("size", DEFAULT_SIZE),
           "--quality", job.get("quality", DEFAULT_QUALITY),
           "--size-policy", "warn", "--force"]
    if mode == "edit":
        if not 1 <= len(images) <= 5:
            raise ValueError("edit 模式需要 1–5 张参考图")
        for im in images:
            if not im.exists():
                raise FileNotFoundError(f"参考图不存在：{im}")
            cmd += ["--image", str(im)]
    return cmd, mode


def run_batch(jobs_file: Path, cli: str, dry: bool):
    batch_dir = OUT / jobs_file.stem
    batch_dir.mkdir(parents=True, exist_ok=True)
    log = batch_dir / "log.jsonl"
    jobs = load_jobs(jobs_file)
    print(f"批次 {jobs_file.name}：{len(jobs)} 个任务 → {batch_dir}")
    for job in jobs:
        jid = str(job["id"])
        out_png = batch_dir / f"{jid}.png"
        prompt_file = batch_dir / f"{jid}.txt"
        prompt_file.write_text(job["prompt"].strip() + "\n", encoding="utf-8")
        rec = {"id": jid, "batch": jobs_file.stem, "out": out_png.relative_to(ROOT).as_posix(),
               "images": job.get("images") or [], "size": job.get("size", DEFAULT_SIZE),
               "quality": job.get("quality", DEFAULT_QUALITY),
               "generated_image_inputs": job.get("images") or "none", "status": "", "seconds": 0.0, "note": ""}
        try:
            cmd, mode = build_cmd(cli, job, out_png, prompt_file)
        except Exception as e:
            rec.update(status="failed", note=str(e))
            print(f"  {jid}: 未提交（{e}）")
            log.open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
            continue
        rec["mode"] = mode
        if dry:
            print("  " + " ".join(cmd))
            continue
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        rec["seconds"] = round(time.time() - t0, 1)
        # 日志只记相对路径，不把本机绝对路径（含用户名）写进可入库的文件
        tail = [ln.replace(str(ROOT), "<root>") for ln in (r.stderr or "").strip().splitlines()[-3:]]
        if r.returncode == 0 and out_png.exists():
            rec["status"] = "test"        # 生成成功，待检查；用户确认后才改 final
            rec["note"] = " | ".join(tail)
            print(f"  {jid}: 已生成 {out_png.name}（{rec['seconds']}s）")
        else:
            rec["status"] = "failed"
            rec["note"] = f"rc={r.returncode} " + " | ".join(tail)
            print(f"  {jid}: 失败 rc={r.returncode}\n     " + "\n     ".join(tail))
        log.open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
    if not dry:
        DONE.mkdir(exist_ok=True)
        shutil.move(str(jobs_file), DONE / jobs_file.name)
    print(f"完成。追溯记录：{log}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=Path)
    ap.add_argument("--cli", default="codex-imagegen")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and shutil.which(a.cli) is None:
        # uv tool install 的默认位置（PATH 未刷新时）
        for c in (Path.home() / ".local/bin/codex-imagegen.exe", Path.home() / ".local/bin/codex-imagegen"):
            if c.exists():
                a.cli = str(c); break
        else:
            sys.exit(f"找不到 {a.cli}。按 INSTALL.md 第 3 节安装（固定提交 bf126f9，在 codex-imagegen-cli 目录执行 uv tool install .）")
    while True:
        files = [a.jobs] if a.jobs else sorted(INBOX.glob("*.jsonl"))
        for f in files:
            run_batch(f, a.cli, a.dry_run)
        if not a.watch or a.jobs:
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
