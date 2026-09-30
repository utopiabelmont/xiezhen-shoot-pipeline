#!/usr/bin/env python3
"""Install the planner for Codex or Claude using only the Python standard library."""
from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
NAME = "xiezhen-shoot-planner"


def install(skills_dir: Path, *, force: bool = False) -> Path:
    source = ROOT / "skill" / NAME
    skills_dir = skills_dir.expanduser().resolve()
    target = skills_dir / NAME
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("安装目录不能覆盖仓库中的 skill 源目录")
    if target.is_symlink():
        raise ValueError(f"安装目标是符号链接，请另选目录：{target}")
    if target.exists() and not force:
        raise FileExistsError(f"已存在：{target}；更新请加 --force（先备份旧版本）")
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"缺少 {source / 'SKILL.md'}，请下载完整仓库")
    skills_dir.mkdir(parents=True, exist_ok=True)
    # Stage the complete copy before moving the existing install out of the way.
    with tempfile.TemporaryDirectory(prefix="xiezhen-install-", dir=skills_dir.parent) as tmp:
        staged = Path(tmp) / NAME
        shutil.copytree(source, staged)
        backup = None
        if target.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = skills_dir.parent / ".xiezhen-skill-backups" / f"{NAME}-{stamp}-{uuid.uuid4().hex[:8]}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
        if backup is not None:
            print(f"旧版备份：{backup}")
    print(f"已安装：{target}")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("codex", "claude"), default="codex")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-dir", type=Path, help="项目安装的根目录，默认仓库根目录")
    parser.add_argument("--skills-dir", type=Path, help="自定义 skills 父目录，优先于 scope")
    parser.add_argument("--force", action="store_true", help="备份已有版本后更新")
    parser.add_argument("--no-register", action="store_true", help="只装 skill，不更新运行环境登记")
    args = parser.parse_args(argv)
    base = Path.home() if args.scope == "user" else (args.project_dir or ROOT)
    skills_dir = args.skills_dir or base / (".agents" if args.agent == "codex" else ".claude") / "skills"
    try:
        install(skills_dir, force=args.force)
        if not args.no_register:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            subprocess.run([sys.executable, str(ROOT / "pipeline.py"), "register", "--root", str(ROOT)],
                           check=True, env=env)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"安装失败：{exc}", file=sys.stderr)
        return 1
    print("在 Codex 中使用 $xiezhen-shoot-planner；未出现时重启 Codex。" if args.agent == "codex"
          else "Claude skill 已就绪。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
