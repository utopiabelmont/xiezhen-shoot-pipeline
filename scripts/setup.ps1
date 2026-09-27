# setup.ps1  Windows 本机部署：uv 管理的 Python 3.12 + .venv + 依赖 + 自检 + 离线测试
# 仓库根目录 = 本文件上两级；本机没有系统 Python 也能跑（需先把 uv.exe 放到 bin\）
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $root
Remove-Item "$root\setup_done.txt" -ErrorAction SilentlyContinue
Start-Transcript -Path "$root\setup_log.txt" -Force | Out-Null

"== 1 uv =="
$uv = "$root\bin\uv.exe"
if (-not (Test-Path $uv)) { $c = Get-Command uv -ErrorAction SilentlyContinue; if ($c) { $uv = $c.Source } }
if (-not (Test-Path $uv)) { "未找到 uv：先 powershell -ExecutionPolicy ByPass -c ""irm https://astral.sh/uv/install.ps1 | iex""，或把 uv.exe 放到 bin\"; Stop-Transcript | Out-Null; exit 1 }
& $uv --version

"== 2 Python 3.12 + .venv =="
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) { & $uv venv --python 3.12 "$root\.venv" }
$py = "$root\.venv\Scripts\python.exe"
& $py --version

"== 3 依赖 =="
& $uv pip install --python $py -r "$root\requirements.txt" 2>&1 | Select-Object -Last 3

"== 4 自检 =="
cmd /c """$py"" check_env.py 2>&1"

"== 5 离线测试（不联网） =="
cmd /c """$py"" tools\spots.py --place ""箱根ガラスの森美術館"" --fixture --out plans\selftest 2>&1"
cmd /c """$py"" tools\sun_light.py --place ""箱根ガラスの森美術館"" --date 2026-09-27 --hours 8-18 --step 30 --elev-m 657 --weather --terrain --fixture --out plans\selftest 2>&1"
cmd /c """$py"" tools\osm_geometry.py --lat 35.25666 --lon 139.02120 --meters 260 --fixture overpass_geom_pola.json --out plans\selftest\basemaps --name pola 2>&1"

"== 6 出图工具 =="
foreach ($c in "codex","codex-imagegen","git") {
  $p = Get-Command $c -ErrorAction SilentlyContinue
  if ($p) { "$c OK  $($p.Source)" } else { "$c 未找到" }
}
"codex-imagegen (uv tool): " + (Test-Path "$env:USERPROFILE\.local\bin\codex-imagegen.exe")
"auth.json exists: " + (Test-Path "$env:USERPROFILE\.codex\auth.json")
"== 7 登记仓库路径（skill 据此找到本机仓库） =="
cmd /c """$py"" pipeline.py register 2>&1"
"== done =="
Stop-Transcript | Out-Null
"done" | Out-File "$root\setup_done.txt"
