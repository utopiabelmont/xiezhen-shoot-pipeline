# Windows 本机部署

以 2026-09-27 在一台没有系统 Python、没有 Git 的 Windows 11 机器上跑通的做法为准。

## 1 目录

把仓库放到一个没有中文、空格也尽量少的路径（有空格也能跑，脚本都加了引号）。下文用 `<root>` 指仓库根目录。

## 2 Python：用 uv 管理

1. 安装 uv：PowerShell 里执行
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   或把 `uv.exe` 直接放到 `<root>\bin\`（离线机器可从别处拷；zip 解压即可）。
2. 双击 `setup.cmd`。它会：
   - 用 uv 装 Python 3.12 并建 `<root>\.venv`
   - `uv pip install -r requirements.txt`
   - 跑 `check_env.py` 与三条离线自测（spots / sun / osm_geometry 用 fixtures）
   - 检查 codex、codex-imagegen、git 是否在 PATH
   - `pipeline.py register`：把仓库路径写到 `%USERPROFILE%\.xiezhen-pipeline\config.json`，Claude 的 skill 靠它找到本机仓库
   结果在 `setup_log.txt`，结束标记 `setup_done.txt`。

以后所有脚本都用 `<root>\.venv\Scripts\python.exe`，不依赖系统 Python。

## 3 出图：codex-imagegen-cli

需要 Codex 的 ChatGPT 登录（桌面版或 CLI 登录过即可，凭据在 `%USERPROFILE%\.codex\auth.json`）。codex-imagegen-cli 是第三方工具，调用 Codex 未公开的图片接口；`auth.json` 是明文登录凭据，不要放进同步文件夹或任何仓库。说明与注意事项见 [INSTALL.md 第 3 节](../INSTALL.md#3-出图工具可选)。

```
codex login status                        # 应显示 ChatGPT 登录
git clone https://github.com/jdmnk/codex-imagegen-cli.git
cd codex-imagegen-cli
git checkout bf126f9052723a93ed2dada138df08b66d10d560
uv tool install .
uv tool update-shell
```

重开终端：`codex-imagegen --version`（0.2.0）。固定这个提交并且不用 `-e`，克隆目录之后的 `git pull` 不会改变已安装的代码；以前用 `uv tool install -e .` 装过的，先 `uv tool uninstall codex-imagegen-cli` 再按上面重装。没有 git 的机器下载 `https://github.com/jdmnk/codex-imagegen-cli/archive/bf126f9052723a93ed2dada138df08b66d10d560.zip`，解压后在目录里 `uv tool install .`。安装后可执行文件在 `%USERPROFILE%\.local\bin\codex-imagegen.exe`，`pipeline.py` 与 `run_shots.py` 找不到 PATH 时会自动找这个位置。

若 `codex login status` 提示不是文件式凭据，在 `%USERPROFILE%\.codex\config.toml` 加一行 `cli_auth_credentials_store = "file"` 后重新 `codex login`。

## 4 双击入口

| 文件 | 作用 | 输出 |
|---|---|---|
| `setup.cmd` | 安装与自检 | `setup_log.txt`, `setup_done.txt` |
| `run_job.cmd` | 执行根目录 `job.ps1`（不存在时从 `scripts/job.example.ps1` 复制一份） | `job_log.txt`, `job_done.txt` |
| `run_shots.cmd` | 跑 `inbox/` 下全部批次出图 | `run_shots_log.txt`, `run_shots_done.txt`, `out/<批次>/` |

`job.ps1` 是「一次性任务」：把要跑的 `pipeline.py` 子命令写进去，双击 `run_job.cmd`。这也是远程由 Claude 操作时的标准做法（Claude 只能在资源管理器里点击，不能打字）。

## 5 已知坑

- **`.ps1` 必须存成 UTF-8 with BOM。** PowerShell 5.1 把无 BOM 的 UTF-8 当 ANSI 读，中文字符串会把引号弄坏，脚本可能一行都不执行、窗口一闪而过。`scripts/*.ps1` 已带 BOM；自己改 `job.ps1` 时用记事本「另存为 → 编码 UTF-8（带 BOM）」，或 Python `open(f, "w", encoding="utf-8-sig")`。
- **Python 输出编码。** 在 `.ps1` 里先 `$env:PYTHONUTF8 = "1"`，再用 `cmd /c """$py"" tools\x.py ... > ""$log"" 2>&1"` 重定向；不要写 `set PYTHONUTF8=1 && python ...`（`&&` 前的空格会进入变量值，Python 报「invalid PYTHONUTF8」直接退出）。
- **远程写入同名文件。** 通过 Claude 的文件回传更新 `job.ps1` 时，每次用新的暂存文件名（job_v5.ps1 → job.ps1），同一暂存名再次提交可能拿到缓存内容。
- **资源管理器双击。** 先点一下列表空白处清掉选中，再双击文件图标；直接双击已选中项的文件名会进入重命名。
- `uv.exe` 单文件 42 MB 超过远程回传 20 MB 限制时，传 zip 再 `Expand-Archive`。
- Overpass 用 POST（`Content-Type: application/x-www-form-urlencoded`），GET 可能 406。偶发超时重跑一次即可。
- Codex 图片接口的尺寸不保证（1152x1536 → 1086x1448），`--size-policy warn` 接受即可。

## 6 一次完整跑法（示例 job.ps1）

```powershell
cmd /c """$py"" pipeline.py init hakone-0928 --place ""箱根ガラスの森美術館"" --date 2026-09-28 --arrive 13:00 --hours 12-18 --elev-m 657 > ""$log"" 2>&1"
cmd /c """$py"" pipeline.py spots hakone-0928 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py sun hakone-0928 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py basemap hakone-0928 --meters 130 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py stylize hakone-0928 >> ""$log"" 2>&1"
# 人工阶段：SNS 调研、分镜、prompt
cmd /c """$py"" pipeline.py jobs hakone-0928 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py shots hakone-0928 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py cards hakone-0928 >> ""$log"" 2>&1"
```
