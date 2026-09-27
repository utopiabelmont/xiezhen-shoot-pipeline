---
name: xiezhen-shoot-planner
description: 真实景点 + 真实日期的人像外拍规划：查出片点与社交平台机位、算太阳方位/地形遮挡/天气光质、画园区底图、产出至少 9 张带焦段/景别/姿势/机位/光线的分镜表与拍摄小抄，再经 nuyoah-xiezhen-prompt 写 prompt、由 codex-imagegen 出示意图。触发：外拍规划、拍摄小抄、出片点、光线角度、写真出图、接力生图、分镜。
---

# 外拍规划与写真出图接力

仓库 = xiezhen-shoot-pipeline（本机路径见 README；下文用 `<root>`）。统一入口 `python <root>/pipeline.py <阶段> <plan>`；SOP 与验收标准在 `<root>/docs/WORKFLOW.md`，遇到不确定的地方以它为准。

## 输入

用户给出：景点名（或坐标）、日期（可多日）、到场时段、器材（机身、镜头焦段范围、有无闪光/反光板）、人物数与服装方向。缺日期或器材时先问一次；其余按默认继续。

## 流程（阶段号与 WORKFLOW.md 一致）

0. **立项**　`pipeline.py init <plan> --place ... --date ... --arrive ... --hours ... [--elev-m] [--gear] [--body] [--flash]`。
1. **出片点**　`pipeline.py spots <plan>`，读 `spots.md`，按末尾关键词做网页调研（官方见どころ页、日文/中文攻略、拍摄规则、票价、开放时间）。
2. **SNS 调研**　用户已在 Chrome 登录小红书 / Instagram / 抖音 / TikTok 时，人工级浏览并填 `spots_social.md`（模板 `templates/sns_research.md`）；不批量抓取、不保存图片。末尾必须写「对分镜的影响」。
3. **光线**　`pipeline.py sun <plan>`，读 `sun.md`：逐时方位/高度/影长、地形遮挡后的实际直射截止、天气光质、人物朝向与光型表。日期超出 16 天只用天文数据，临近再跑。
4. **底图**　`pipeline.py basemap <plan> --meters <园区最长边×1.2>`；园外备选点另做 `--name <x> --center lat,lon`；OSM 缺失的步道用 `--extra`。
5. **风格化**　`pipeline.py stylize <plan> [--name]`（本机 codex-imagegen）。并排核对几何未漂移。
6. **分镜**　按 `templates/shotlist_template.md` 与 `shotlist_schema.json` 写 `shotlist.json`，导出 `shotlist.md`。硬性要求：≥ 9 条；景别至少 4 种；焦段只从器材里选；每条写太阳方位、光型、人物朝向、机位距离、晴天/阴天/雨天备选；同组内动作、视线、机位不重复；每条有 `subject_latlon` 与方位字段；室内 `indoor: true`；园外 `basemap`；`meta.sun` 从 `sun.json` 取整点与半点。SNS 结论要体现在分镜上并写进 `meta.sns`。
7. **prompt**　`nuyoah-xiezhen-prompt` 系列母版 + 同系列变体：固定风格词链、成像词链、人物与服装（`templates/prompt_chains.md`），每张只改取景与机位、动作与视线、环境与光线；光线引用 `sun.md`，写「来源—落点—结果」；无参考图时写「本张重新生成一位「…」类型的成年原创女性」。输出 `prompts.md`（`## <id>-<标题>` + ```text 块）。
8. **出图**　`pipeline.py jobs <plan>` → `pipeline.py shots <plan>`。每条只提交一次，失败只记录。
9. **检查**　逐张按 nuyoah-xiezhen-prompt 第六步检查，另核对光向与 `sun.md`、背景方位与底图一致。状态只写 test / failed，用户确认后才 final；重做回到原始分镜重新编译，不用上一轮生成图做输入。把 `out/<plan>/log.jsonl` 复制为 `plans/<plan>/generation_log.jsonl`。
10. **小抄**　`pipeline.py cards <plan>`，逐页检查（文字溢出、标签重叠、太阳箭头方向、页脚「AI 拍摄示意，非现场实拍」）。PDF 文件名固定为 `<出行日期>_<地点>_拍摄小抄.pdf`（例 `2026-09-28_浅草寺_拍摄小抄.pdf`，改版加 `_v2`），由 `pipeline.py` 按 `shotlist.json` 的 `meta.date` 与 `meta.place` 自动命名；交付给用户的文件也用这个名字，不用「拍摄小抄.pdf」这类无日期无地点的名字。
11. **当天资料**　`timeline.md`（交通班次注明来源与查询日期）、`model_sheet.md`、`arrival_checklist.md`；出发前一天重跑 `sun`。

改版：复制为 `<plan>-v2`，只重做变动的分镜，复用图片记 `img_from`，新增分镜单独出图，最后统一重跑 `cards`。

## Windows 远程执行

只能点击、不能打字时：把命令写进 `<root>/job.ps1`（UTF-8 with BOM，模板 `scripts/job.example.ps1`），双击 `run_job.cmd`，轮询 `job_done.txt`，读 `job_log.txt`。回传同名文件用新的暂存文件名。坑清单在 `docs/WINDOWS_SETUP.md` 第 5 节。

## 交付

对话中给：调研摘要（spot 列表与来源链接、SNS 结论）、光线摘要（关键时刻与实际直射截止）、分镜表、每张完整 prompt、图片路径、质量状态与 `generation_log.jsonl` 追溯记录、小抄 PDF、时间线/模特页/到场清单，以及需要现场核实的事项。
