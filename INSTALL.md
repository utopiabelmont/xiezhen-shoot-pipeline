# 安装说明

在一台新电脑上把这套流水线装到能跑的程度，分四步：取代码、装 Python 环境、装出图工具（可选）、安装 skill。支持 **纯 Codex（桌面版 / CLI）**，也保留 Claude + Codex 出图的用法。Windows 是主要验证平台；macOS / Linux 可用相同 Python 入口，出图取决于 codex-imagegen-cli 在对应环境的可用性。

## 0 需要准备什么

| 项目 | 必需 | 说明 |
|---|---|---|
| 仓库代码 | 是 | `git clone` 或下载 zip |
| Python 3.10 以上 | 是 | Windows 上由 `setup.cmd` 通过 uv 自动安装，不需要系统 Python |
| 中文字体 | 是 | Windows 自带微软雅黑即可；Linux 装 `fonts-noto-cjk`；macOS 自带苹方 |
| 联网 | 是 | Nominatim、Overpass、Open-Meteo、Wikimedia Commons，均为公开接口，不需要密钥 |
| Codex（ChatGPT 登录）+ codex-imagegen-cli | 出图时 | 阶段 5 风格化底图与阶段 8 出示意图用；不装也能跑到分镜与小抄（小抄里没有示意图） |
| Codex 桌面版 / CLI，或 Claude Code / 桌面版 | 用 skill 时 | 任选一种执行调研、分镜、prompt 与检查；纯 Codex 不需要 Claude |

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

安装前先了解三点：

- codex-imagegen-cli 是第三方工具（[jdmnk/codex-imagegen-cli](https://github.com/jdmnk/codex-imagegen-cli)，Apache-2.0），不是 OpenAI 官方产品。它用你的 Codex ChatGPT 登录调用 Codex 内部的图片接口；这个接口没有公开文档，Codex 更新后可能失效，出图用量计入你自己的 ChatGPT 账号。
- 它要求 Codex 把登录凭据存成文件。`~/.codex/auth.json`（Windows 为 `%USERPROFILE%\.codex\auth.json`）里是明文的 access token 与 refresh token，拿到这个文件就能以你的账号使用 ChatGPT。不要把它放进 OneDrive、iCloud 等同步文件夹，不要复制进任何仓库，也不要发给别人或贴进 issue；本仓库的 `.gitignore` 已排除 `auth.json`。怀疑泄露时，在 ChatGPT 的安全设置里退出所有设备，再重新 `codex login`。
- 下面固定安装 0.2.0（提交 `bf126f9`）。2026-09-30 看过这一版的代码：令牌只发往 `chatgpt.com/backend-api/codex` 与 `auth.openai.com/oauth/token`，刷新后的令牌写回 `auth.json`，除此之外只调用 `codex --version`。不要设置 `CODEX_IMAGEGEN_BASE_URL`、`CODEX_IMAGEGEN_REFRESH_URL` 这两个环境变量，它们会改变令牌的发送地址。升级时先看上游的改动，再换提交号重装。

1. 装 Codex 并登录一次（桌面版或 `codex login` 都行）。`codex login status` 应显示 ChatGPT 登录。
   若提示不是文件式凭据，在 `~/.codex/config.toml` 加一行 `cli_auth_credentials_store = "file"` 后重新登录。
2. 装 codex-imagegen-cli，固定到看过的版本，并且不用 editable 安装（`-e`），这样克隆目录里之后的 `git pull` 不会改变已安装的代码：
   ```bash
   git clone https://github.com/jdmnk/codex-imagegen-cli.git
   cd codex-imagegen-cli
   git checkout bf126f9052723a93ed2dada138df08b66d10d560
   uv tool install .
   uv tool update-shell
   ```
   重开终端，`codex-imagegen --version` 应输出 0.2.0。Windows 下可执行文件在 `%USERPROFILE%\.local\bin\codex-imagegen.exe`，`pipeline.py` 找不到 PATH 时会自动去这个位置找。
   以前按旧说明用 `uv tool install -e .` 装过的，在克隆目录里先 `uv tool uninstall codex-imagegen-cli`，再执行上面的 `git checkout` 与 `uv tool install .`。
3. 再跑一次 `python check_env.py`，`codex-imagegen` 与 `Codex 登录文件` 两行都要是 `OK`。

## 4 安装 skill（纯 Codex 推荐）

`skill/xiezhen-shoot-planner/` 是 Codex 与 Claude 共用的流程 skill。它需要完整仓库里的脚本、模板与文档；只装 `SKILL.md` 不能替代第 1–2 步的运行时安装。

### A. 纯 Codex：一条命令安装并登记

完成第 1–2 步后，在仓库根目录执行（不需要安装 Claude）：

Windows PowerShell：

```powershell
& .\.venv\Scripts\python.exe .\scripts\install_skill.py
```

macOS / Linux（第 2 步创建的 venv）：

```bash
.venv/bin/python scripts/install_skill.py
```

脚本只用 Python 标准库，默认将整个 skill 复制到 `~/.agents/skills/xiezhen-shoot-planner/`（Windows 为 `%USERPROFILE%\.agents\skills\xiezhen-shoot-planner\`），并用同一解释器调用 `pipeline.py register` 登记仓库与 Python 路径。目录依据 [Codex 官方 skill 文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。如果已在 `~/.codex/skills` 或其他位置装过同名 skill，迁移时只保留一份有效安装，避免选择器中重复。

其他安装方式（以下 `python` 指本仓库 venv 的解释器）：

```bash
python scripts/install_skill.py --scope project    # 本仓库的 .agents/skills/
python scripts/install_skill.py --scope project --project-dir /path/to/project
python scripts/install_skill.py --skills-dir /path/to/skills  # 指定 skills 父目录
python scripts/install_skill.py --force            # 更新：先备份已有版本
python scripts/install_skill.py --no-register      # 仅复制 skill，保留已有运行环境登记
```

更新备份位于 skills 父目录旁的 `.xiezhen-skill-backups/`，不会留在 skill 扫描目录里。安装不下载其它 skill，不修改 Codex 的模型、权限、登录或 `config.toml`。`--project-dir` 选择 skill 的发现位置，运行时仍是当前安装脚本所属仓库。

在 Codex 桌面版中把仓库添加为本地项目；CLI 在仓库目录启动 `codex`。然后发送：

```text
$xiezhen-shoot-planner 10 月 3 日上午十点去浅草寺，α7 V + 24-105 F4，做拍摄脚本。
```

新 skill 未出现时重启 Codex。Codex 在终端里直接执行脚本，不需要 Claude in Chrome、`job.ps1` 或另一位代理。项目安装的 skill 只在该项目目录范围内发现；云端 Codex 须在云端另装运行时，不能自动使用本机路径与凭据。

### B. 保留 Claude 安装

也可用同一安装脚本：

```bash
python scripts/install_skill.py --agent claude      # ~/.claude/skills/
python scripts/install_skill.py --agent claude --scope project
```

原来的手工装法仍可用：

- Claude Code：复制到项目或用户的 skills 目录
  ```bash
  mkdir -p ~/.claude/skills
  cp -r skill/xiezhen-shoot-planner ~/.claude/skills/
  ```
  Windows 对应 `%USERPROFILE%\.claude\skills\`。
- Claude 桌面版 / claude.ai：在 skills 设置里新建，把 SKILL.md 内容贴进去。
- 在 Claude 对话里把 SKILL.md 作为附件发给它，说「把这个存成 skill」。

### 仓库定位与可选能力

skill 里不写死仓库路径。Codex / Claude 找仓库的顺序是：对话指定路径 → 当前工作区里含 `pipeline.py` 的目录 → `XIEZHEN_CONFIG` 指向的文件或 `~/.xiezhen-pipeline/config.json` 里登记的 `root`。Windows 上 `setup.cmd` 最后一步与安装脚本都可登记；手工复制 skill 或换了目录后跑一次：

```bash
python pipeline.py register            # 登记当前仓库；--root <路径> 可指定别处；--show 查看
```

登记文件在 `%USERPROFILE%\.xiezhen-pipeline\config.json`（Windows）或 `~/.xiezhen-pipeline/config.json`，记录 root、venv 的 python 路径、系统与日期。想放别处用环境变量 `XIEZHEN_CONFIG` 指定。

- prompt：可以另装 [nuyoah-xiezhen-prompt](https://github.com/nuyoah-ai-works/nuyoah-xiezhen-prompt)；没装时直接使用仓库的 `templates/prompt_chains.md` 和 skill 第 9 阶段检查项，仍能完成流程。
- SNS：需要当前会话有浏览器工具并能读取登录平台。纯 Codex CLI 不保证有这种能力；没有时采用实际可读的公开网页或用户文字资料，记录调研缺口，没有可靠素材的分镜标「无 SNS 素材」，不编造原帖与构图。
- 出图：仍使用第 3 节的 codex-imagegen-cli，不需要 Claude。没装时跳过 `stylize` / `shots`，用 OSM 底图完成分镜、prompt、无示意图的 PDF 与 HTML。第三方内部图片接口的可用性不由 skill 保证。

## 5 第一次正式跑

```bash
python pipeline.py init   asakusa-1003 --place "浅草寺" --date 2026-10-03 --arrive 10:00 --hours 9-15
python pipeline.py spots  asakusa-1003
python pipeline.py sun    asakusa-1003
python pipeline.py basemap asakusa-1003 --meters 300 --name north --center 35.7148,139.7967
python pipeline.py stylize asakusa-1003 --name north      # 需要第 3 步
# Codex / Claude：SNS 调研 → shotlist.json → prompts.md
python pipeline.py lint   asakusa-1003
python pipeline.py jobs   asakusa-1003
python pipeline.py shots  asakusa-1003                     # 需要第 3 步
python pipeline.py cards  asakusa-1003 --images out/asakusa-1003
```

或者直接对 Codex / Claude 说「10 月 3 日上午十点去浅草寺，α7 V + 24-105 F4，做拍摄脚本」，其余由 skill 驱动。

## 6 Windows 上由 Claude 远程执行

仅在 Claude 等会话没有终端工具、但能连接本机并点击时使用此桥接方式：Claude 把要跑的命令写进 `<root>\job.ps1`（UTF-8 with BOM），双击 `run_job.cmd`，轮询 `job_done.txt`，读 `job_log.txt`。细节与已知坑（BOM、PYTHONUTF8、资源管理器双击）见 [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md)。

## 7 更新

```bash
git pull
pip install -r requirements.txt      # Windows：再双击一次 setup.cmd
```

`plans/`、`out/`、`inbox/` 不入库，更新不会碰到你的企划。仓库挪了位置就再跑一次 `python pipeline.py register`。skill 有改动时（见 `docs/CHANGELOG.md`）运行 `python scripts/install_skill.py --force`；原来用 Claude、项目范围或自定义目录安装的，更新时保留对应的 `--agent` / `--scope` / `--skills-dir` 参数。手工安装则重新复制完整 skill 目录。

## 常见问题

- `找不到中文字体`：Linux 装 `fonts-noto-cjk`；Windows 确认 `C:\Windows\Fonts\msyh.ttc` 存在。
- `Overpass 504` / `timeout`：脚本会重试 3 次，仍失败就过几分钟再跑；或用 `--fixture` 先走通其它阶段。
- `codex-imagegen 未找到`：重开终端让 PATH 生效；或确认 `%USERPROFILE%\.local\bin` 里有可执行文件。
- `stylize` 后底图把马路画成了河：加 `--prompt-extra "图中没有任何河流、运河或水面，所有灰色道路都画成浅灰米色的路面"` 重跑。
- 双击 `run_job.cmd` 窗口一闪而过、没有日志：`job.ps1` 不是 UTF-8 with BOM，用记事本另存为「UTF-8（带 BOM）」。
