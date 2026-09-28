# skill/

`xiezhen-shoot-planner/SKILL.md` 是给 Claude 用的流程 skill，与 `docs/WORKFLOW.md` 的阶段号一致，随仓库版本同步更新（版本记录见 `docs/CHANGELOG.md`）。

安装方式见根目录 `INSTALL.md` 第 4 节：复制到 `~/.claude/skills/`，或在 Claude 的 skills 设置里新建并粘贴内容，或把文件发给 Claude 说「存成 skill」。仓库更新后把新的 SKILL.md 重新装一次。

skill 覆盖的流程（1.6.0）：

| 阶段 | 内容 | 由谁做 |
|---|---|---|
| 0 立项 | `pipeline.py init` | 脚本 |
| 1 出片点 | `pipeline.py spots` + 网页调研 | 脚本 + Claude |
| 2 SNS 调研 | 小红书 / Instagram / 抖音 / TikTok，人工级浏览；机位帖、姿势帖、平台汇总写成文字记进 `sns_refs.json`，不存原帖图片；含穿搭观察 | Claude in Chrome |
| 2b 穿搭 | `pipeline.py palette` 抽场地色 → `outfit.json`（路线、≤3 色、ΔE ≥ 12、替换方案、逐张提醒） | 脚本 + Claude |
| 3 光线 | `pipeline.py sun`：太阳、地形遮挡、天气光质 | 脚本 |
| 4–5 底图 | `basemap` → `stylize`（Codex 水彩风格化） | 脚本 + 本机 Codex |
| 6 分镜 | 每条 SNS 素材设计一张同款（`src`），不够再补；分镜基本法（角色、景别配比、节奏、姿态视线）+ 动态素材（连拍 ≥ 2、短片 ≥ 5、实况 ≥ 6）→ `pipeline.py lint` | Claude + 脚本 |
| 6b 路线 | `meta.route_stops` + `trip.json` → `pipeline.py route` / `trip`：园内步道最短路与时刻、一日行程页；`pipeline.py renumber` 编号改成游览顺序 | Claude + 脚本 |
| 7 prompt | `scene_bible.md` + nuyoah-xiezhen-prompt 系列母版 + 变体，取景段用对原帖构图的文字描述；短片/实况写关键帧，`move_prompts.md` 写起中止三帧 | Claude |
| 8–9 出图与检查 | `jobs [--missing]` → `shots`，`jobs --moves` → `shots --moves` → 逐张检查 | 脚本 + 本机 Codex + Claude |
| 10 拍摄脚本 | `pipeline.py cards`：行程 → 穿搭 → 路线 → 分镜（每页一张示意图 + SNS 来源栏与二维码，短片卡后接运镜页），`<日期>_<地点>_拍摄脚本.pdf` + `<日期>_<地点>_拍摄核对表.html` | 脚本 |
| 11 当天资料 | 时间线、模特页、到场清单、剪辑单 | Claude |
