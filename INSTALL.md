# 安装说明

在一台新电脑上把这套流水线装到能跑的程度，分四步：取代码、装 Python 环境、装出图工具（可选）、把 skill 交给 Claude。Windows 是主要目标平台，macOS / Linux 也能跑除出图以外的全部阶段。

## 0 需要准备什么

| 项目 | 必需 | 说明 |
|---|---|---|
| 仓库代码 | 是 | `git clone` 或下载 zip |
| Python 3.10 以上 | 是 | Windows 上由 `setup.cmd` 通过 uv 自动安装，不需要系统 Python |
| 中文字体 | 是 | Windows 自带微软雅黑即可；Linux 装 `fonts-noto-cjk`；macOS 自带苹方 |
| 联网 | 是 | Nominatim、Overpass、Open-Meteo、Wikimedia Commons，均为公开接口，不需要密钥 |
| Codex（ChatGPT 登录）+ codex-imagegen-cli | 出图时 | 阶段 5 风格化底图与阶段 8 出示意图用；不装也能跑到分镜与小抄（小抄里没有示意图） |
| Claude Code 或 Claude 桌面版 | 用 skill 时 | 阶段 2、6、7、9、11 由 Claude 按 skill 执行 |

## 1 取代码

```bash
git clone https://github.com/utopiabelmont/xiezhen-shoot-pipeline.git
cd xiezhen-shoot-pipeline
```

没有 git 的机器：GitHub 页面「Code → Download ZIP」，解压到一个路径里没有中文的目录。下文用 `<root>` 指这个目录。

## 2 Python 环境

### Windows（推荐路径）

1. 安装 uv（只需一次）。PowerShell 里执行：
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   离线机器可以把 `uv.exe` 直接放到 `<root>\bin\`，`setup.cmd` 会优先找这里。
2. 双击 `<root>\setup.cmd`。它会装 Python 3.12 到 `<root>\.venv`，装依赖，跑 `check_env.py`，用离线样本跑三条自测（spots / sun / osm_geometry），最后把仓库路径登记到 `%USERPROFILE%\.xiezhen-pipeline\config.json`（第 4 节）。
3. 看 `<root>\setup_log.txt`。最后几行应当是 `== done ==`，并且 `setup_done.txt` 已生成。`check_env.py` 那一段里七个依赖都要是 `OK`。

以后所有脚本都用 `<root>\.venv\Scripts\python.exe`，与系统 Python 无关。

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python check_env.py
python pipeline.py register
```

Linux 另装字体：`sudo apt install fonts-noto-cjk`（小抄与太阳图要用）。

### 验证

```bash
python pipeline.py init selftest --place "箱根ガラスの森美術館" --date 2026-09-28 --arrive 13:00 --hours 12-18 --elev-m 657
python pipeline.py spots selftest --fixture
python pipeline.py sun selftest --fixture
python pipeline.py basemap selftest --fixture overpass_geom_pola.json --center 35.25666,139.02120 --meters 260
python pipeline.py status selftest
```

四条都不报错、`plans/selftest/` 里出现 `spots.md`、`sun.md`、`sun_path.png`、`basemaps/main_osm.png`，环境就可用了。把 `--fixture` 去掉再跑一遍，能验证联网接口。

## 3 出图工具（可选）

只有阶段 5（底图风格化）和阶段 8（示意图）需要。用的是 ChatGPT 订阅里的 Codex 额度，不走 API 计费。

1. 装 Codex 并登录一次（桌面版或 `codex login` 都行）。`codex login status` 应显示 ChatGPT 登录；凭据在 `~/.codex/auth.json`。
   若提示不是文件式凭据，在 `~/.codex/config.toml` 加一行 `cli_auth_credentials_store = "file"` 后重新登录。
2. 装 [codex-imagegen-cli](https://github.com/jdmnk/codex-imagegen-cli)：
   ```bash
   git clone https://github.com/jdmnk/codex-imagegen-cli.git
   cd codex-imagegen-cli
   uv sync
   uv tool install -e .
   uv tool update-shell
   ```
   重开终端，`codex-imagegen --version` 应输出 0.2.0 或更高。Windows 下可执行文件在 `%USERPROFILE%\.local\bin\codex-imagegen.exe`，`pipeline.py` 找不到 PATH 时会自动去这个位置找。
3. 再跑一次 `python check_env.py`，`codex-imagegen` 与 `Codex 登录文件` 两行都要是 `OK`。

## 4 把 skill 交给 Claude

`skill/xiezhen-shoot-planner/SKILL.md` 是 Claude 用的流程说明。三种装法任选：

- Claude Code：复制到项目或用户的 skills 目录
  ```bash
  mkdir -p ~/.claude/skills
  cp -r skill/xiezhen-shoot-planner ~/.claude/skills/
  ```
  Windows 对应 `%USERPROFILE%\.claude\skills\`。
- Claude 桌面版 / claude.ai：在 skills 设置里新建，把 SKILL.md 内容贴进去。
- 在 Claude 对话里把 SKILL.md 作为附件发给它，说「把这个存成 skill」。

skill 里不写死仓库路径。Claude 找仓库的顺序是：对话里你指定的路径 → 连接给它的文件夹里含 `pipeline.py` 的目录 → `~/.xiezhen-pipeline/config.json` 里登记的 `root`。Windows 上 `setup.cmd` 最后一步已自动登记；macOS / Linux 或换了目录后手动跑一次：

```bash
python pipeline.py register            # 登记当前仓库；--root <路径> 可指定别处；--show 查看
```

登记文件在 `%USERPROFILE%\.xiezhen-pipeline\config.json`（Windows）或 `~/.xiezhen-pipeline/config.json`，记录 root、venv 的 python 路径、系统与日期。想放别处用环境变量 `XIEZHEN_CONFIG` 指定。

它依赖另一个 skill [nuyoah-xiezhen-prompt](https://github.com/nuyoah-ai-works/nuyoah-xiezhen-prompt)（分镜编译成 prompt 用），一并装上。

## 5 第一次正式跑

```bash
python pipeline.py init   asakusa-1003 --place "浅草寺" --date 2026-10-03 --arrive 10:00 --hours 9-15
python pipeline.py spots  asakusa-1003
python pipeline.py sun    asakusa-1003
python pipeline.py basemap asakusa-1003 --meters 300 --name north --center 35.7148,139.7967
python pipeline.py stylize asakusa-1003 --name north      # 需要第 3 步
# Claude：SNS 调研 → shotlist.json → prompts.md
python pipeline.py lint   asakusa-1003
python pipeline.py jobs   asakusa-1003
python pipeline.py shots  asakusa-1003                     # 需要第 3 步
python pipeline.py cards  asakusa-1003 --images out/asakusa-1003
```

或者直接对 Claude 说「10 月 3 日上午十点去浅草寺，α7 V + 24-105 F4，做拍摄脚本」，其余由 skill 驱动。

## 6 Windows 上由 Claude 远程执行

Claude 通过桌面版连接本机时只能点击、不能在终端打字，约定是：Claude 把要跑的命令写进 `<root>\job.ps1`（UTF-8 with BOM），双击 `run_job.cmd`，轮询 `job_done.txt`，读 `job_log.txt`。细节与已知坑（BOM、PYTHONUTF8、资源管理器双击）见 [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md)。

## 7 更新

```bash
git pull
pip install -r requirements.txt      # Windows：再双击一次 setup.cmd
```

`plans/`、`out/`、`inbox/` 不入库，更新不会碰到你的企划。仓库挪了位置就再跑一次 `python pipeline.py register`。skill 有改动时（见 `docs/CHANGELOG.md`）把新的 SKILL.md 重新装一次。

## 常见问题

- `找不到中文字体`：Linux 装 `fonts-noto-cjk`；Windows 确认 `C:\Windows\Fonts\msyh.ttc` 存在。
- `Overpass 504` / `timeout`：脚本会重试 3 次，仍失败就过几分钟再跑；或用 `--fixture` 先走通其它阶段。
- `codex-imagegen 未找到`：重开终端让 PATH 生效；或确认 `%USERPROFILE%\.local\bin` 里有可执行文件。
- `stylize` 后底图把马路画成了河：加 `--prompt-extra "图中没有任何河流、运河或水面，所有灰色道路都画成浅灰米色的路面"` 重跑。
- 双击 `run_job.cmd` 窗口一闪而过、没有日志：`job.ps1` 不是 UTF-8 with BOM，用记事本另存为「UTF-8（带 BOM）」。
