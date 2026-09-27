"""环境自检：python check_env.py"""
import importlib, shutil, sys, os, zoneinfo
print("Python", sys.version.split()[0])
for m in ["astral", "matplotlib", "pvlib", "pandas", "timezonefinder", "tzdata", "PIL"]:
    try:
        importlib.import_module(m); print(f"  依赖 {m:14s} OK")
    except Exception as e:
        print(f"  依赖 {m:14s} 缺失 → pip install {m}")
try:
    zoneinfo.ZoneInfo("Asia/Tokyo"); print("  时区数据          OK")
except Exception:
    print("  时区数据          缺失 → pip install tzdata")
for exe in ["codex", "codex-imagegen", "git", "uv"]:
    p = shutil.which(exe); print(f"  命令 {exe:14s} {'OK  ' + p if p else '未找到（出图步骤才需要 codex-imagegen / uv）'}")
auth = os.path.expanduser("~/.codex/auth.json")
print("  Codex 登录文件    ", "OK" if os.path.exists(auth) else "未找到 " + auth + "（出图步骤才需要）")
