---
name: "xiezhen-shoot-planner"
description: "真实景点+真实日期的人像外拍规划：出片点与 SNS 机位调研、穿搭方案、太阳/地形/天气光线、园区底图、≥9 张分镜（含连拍/短片/实况）与拍摄小抄，再经 nuyoah-xiezhen-prompt 写 prompt、codex-imagegen 出示意图。触发：外拍规划、拍摄小抄、出片点、光线角度、分镜、穿搭、写真出图。"
---

# 外拍规划与写真出图接力

代码仓库：GitHub `utopiabelmont/xiezhen-shoot-pipeline`，安装见仓库 `INSTALL.md`。下文用 `<root>` 指仓库根目录，按这个顺序确定：① 用户本次对话指定的路径；② 已连接的文件夹里含 `pipeline.py` 的目录；③ 本机 `~/.xiezhen-pipeline/config.json`（Windows 为 `%USERPROFILE%\.xiezhen-pipeline\config.json`）里的 `root`，同文件的 `python` 是要用的解释器（Windows 通常是 `<root>\.venv\Scripts\python.exe`）。三处都没有就问用户一次，得到后让用户跑 `python pipeline.py register --root <路径>` 登记（或代为写进 job.ps1）。云端会话里没有本机时 `git clone` 到工作目录再用。统一入口 `python <root>/pipeline.py <阶段> <plan>`；每个阶段的输入、输出、验收标准在 `<root>/docs/WORKFLOW.md`，不确定时以它为准。

## 输入

用户给出：景点名（或坐标）、日期（可多日）、到场时段、器材（机身、镜头焦段范围、有无闪光/反光板）、人物数与服装方向。缺日期或器材时先问一次；其余按默认继续（默认：全画幅 + 24-105mm F4，一位成年女性，服装由 Claude 按季节与场地提议并在分镜 meta 里写明）。

## 网络与执行位置

- 脚本要联网（Nominatim、Overpass、Open-Meteo、Commons）。云端容器通常拉不到这些接口：能用本机时把命令写进 `<root>\job.ps1`（UTF-8 with BOM，模板 `scripts/job.example.ps1`），双击 `run_job.cmd`，轮询 `job_done.txt`，读 `job_log.txt`；没有本机时用 Claude in Chrome 在页面里 fetch（Overpass 在 overpass-api.de 页面内 POST `/api/interpreter`），把结果存成 `tools/fixtures/*.json` 后加 `--fixture` 跑。
- 出图（`stylize`、`shots`）只能在装了 codex-imagegen 且 Codex 已 ChatGPT 登录的本机上跑。Overpass 504 与 Codex 连接重置都是偶发，重跑一次即可；重跑底图时 geometry / meta / styled 三个文件必须来自同一次 basemap，否则叠加会错位。
- 回传同名文件时每次用新的暂存文件名。资源管理器里先点空白处再双击图标。

## 流程（阶段号与 WORKFLOW.md 一致）

0. **立项**　`pipeline.py init <plan> --place ... --date ... --arrive ... --hours ... [--lat --lon] [--elev-m] [--gear] [--body] [--flash] [--outfit]`。`<plan>` 用「地点缩写-月日」。
1. **出片点**　`pipeline.py spots <plan>`，读 `spots.md`，按末尾关键词做网页调研（官方见どころ页、日文/中文攻略、拍摄规则、票价、开放时间、人流时段）。
2. **SNS 调研**　用户已在 Chrome 登录小红书 / Instagram / 抖音 / TikTok 时，人工级浏览并填 `spots_social.md`（模板 `templates/sns_research.md`）；不批量抓取、不保存图片。各平台路径（2026-09-27 实测）：小红书直接开 `search_result?keyword=` 常空白，要在 `/explore` 首页搜索框里输入关键词回车，先读结果页右侧「点点」AI 对 30 篇笔记的机位汇总，再点 1–3 篇高赞帖（用 JS 跳 `/explore/<id>` 会触发 300031 风控，拦一次就停）；抖音 `douyin.com/search/<词>` 可用，等 10 秒以上再读；TikTok `tiktok.com/search?q=` 首次常报「不明なエラー」，点「もう一度お試しください」即出；Instagram `explore/search/keyword/?q=%23<标签>` 读图片 alt。顺带看近期活动（祭典、灯笼祭、投影、临时封闭）。末尾必须写「对分镜的影响」：与主流机位重合的、本组差异化机位、新增备选、需现场核实的。
2b. **穿搭**　`pipeline.py palette <plan>`（从 Commons 场地照抽 6 个主色；也可 `--images` 用现场照），再按 `docs/OUTFIT_GUIDE.md` 与 `templates/outfit_template.md` 写 `plans/<plan>/outfit.json` 与 `outfit.md`：先按场地前三主色选路线（同系色融 / 邻近色稳 / 补色点缀跳），全身 ≤ 3 色加一处点缀，服装色与场地主色 ΔE ≥ 12（有意融入标 `blend_ok`），红叶季亮一档、阴天脸旁放亮色、强色背景避纯白纯黑、避细条纹与反光面料、裙长配动作、一套主装 + 一件可换层次 + 道具；写替换方案（雨/晴/冷/园外备选）、道具妆发、逐张提醒、SNS 穿搭观察（`spots_social.md` 穿搭栏）。`meta.outfit`、prompt 的 OUTFIT 词链、`model_sheet.md` 都从它来；`cards` 阶段把它渲染成 PDF 第一页。
3. **光线**　`pipeline.py sun <plan>`，读 `sun.md`：逐半小时方位/高度/影长、地形遮挡后的实际直射截止、天气光质（直射比≥0.5 且云量<60% 晴天硬光；≥0.5 高云透光；0.2–0.5 薄云；<0.2 阴天）、人物朝向与光型表。日期超出 16 天只用天文数据，临近再跑；出发前一天必跑一次。
4. **底图**　`pipeline.py basemap <plan> --meters <园区最长边×1.2> [--center lat,lon]`；密集城区或长条形场地拆成两张（`--name north/south`，各 260–300 m）；园外备选点另做 `--name <x> --center ...`；OSM 缺失的步道用 `--extra`（`templates/geometry_extra_example.json`），`approx: true` 的线在小抄上注明「概略」。分镜的 `subject_latlon` 要落在所选底图范围内，边缘留 60 m。
5. **风格化**　`pipeline.py stylize <plan> [--name] [--prompt-extra "..."]`（codex-imagegen edit，指令 `templates/basemap_style_prompt.txt`）。与 `_osm.png` 并排核对几何未漂移；城区宽马路被画成运河时加 `--prompt-extra "图中没有任何河流、运河或水面，所有灰色道路都画成浅灰米色的路面"` 重跑。
6. **分镜**　先读 `docs/SHOT_DESIGN.md`（分镜基本法，见下节摘要），按 `templates/shotlist_template.md` 与 `templates/shotlist_schema.json` 写 `plans/<plan>/shotlist.json`，导出 `shotlist.md`；每条写 `role`、`pose`、`gaze`，主图 `hero: true`，备选 `optional: true`。动态素材按 `docs/VIDEO_NOTES.md` 加在静态分镜之后（标 `supplement: true`）：`medium: burst` 连拍 ≥ 2 张（30 张/秒、预拍 0.5 s、1/500 以上，动作有起止，连拍只选 1 张，出的是照片、计入组图）；`medium: video` 短片 ≥ 5 条、六个角色各一（S-Gamut3/S-Log3、ISO 800、斑马 52% 看脸 95% 看高光、180° 快门配 ND、竖幅；`clip.mode` 24p 实时 ≤ 5 s 或 sq60 / sq120 升格实录 2–3 s；`clip.move` 从运镜库选一种：opening 下摇揭示或遮挡揭示、context 侧跟/后跟/前跟、interaction 固定微推或 1/4 环绕、portrait 固定转身回眸、detail 固定升格、closing 后拉上摇；写 `start` / `end` / `nd` / `exposure`，起止各留 1 秒静止）；`medium: live` iPhone 实况 ≥ 6 条放在过渡、候场、室内与主要机位。短片与实况不计入 9 张与景别配比。写完跑 `pipeline.py lint <plan>`：硬性项不过就改分镜（`jobs` 阶段会拒绝生成任务），提示项能改则改。硬性要求：≥ 9 条；景别覆盖特写、近景、半身、全身、环境远景中至少 4 种；焦段只从器材里选；每条写太阳方位、光型、人物朝向、机位距离、晴天/阴天/雨天备选；同组内动作、视线、机位不重复；每条有 `subject_latlon`、`cam_bearing`、`cam_dist`、`face_bearing`、`bg_bearing`、`bg_label`、`size`、`look`、`flash`；室内 `indoor: true`；多底图时每条写 `basemap`；`alt_time` 指晴天版时刻；`meta.sun` 从 `sun.json` 的 rows 取整点与半点；`meta.date` 与 `meta.place` 必填（PDF 命名用）。SNS 结论要体现在分镜上并写进 `meta.sns`。
7. **prompt**　用 `nuyoah-xiezhen-prompt`「系列母版 + 同系列变体」：全组固定风格词链、成像词链、人物与服装（`templates/prompt_chains.md`），每张只改取景与机位、动作与视线、环境与光线；光线引用 `sun.md`，按「来源—落点—结果」写；服装与道具分开写；无参考图时写「本张重新生成一位「…」类型的成年原创女性」。输出 `plans/<plan>/prompts.md`：每张 `## <id>-<标题>` 后接一个 ```text 代码块（`jobs` 阶段靠此解析）。短片与实况写「关键帧」：成像词链换成对应介质的观感（S-Log3 还原后的柔和影调 / iPhone 实况观感），运动部位写轻微动态模糊，风格、人物、服装词链不变。
8. **出图**　`pipeline.py jobs <plan>` → `inbox/<plan>.jsonl`（追加分镜后用 `--missing` 只排还没出图的）；`pipeline.py shots <plan>`（只跑本企划的 jsonl，不用 `run_shots.cmd` 以免重跑 inbox 里的旧批次）。每条只提交一次，失败只记录，不改词不重试。尺寸 3:4 → 1152x1536，4:5 → 1216x1520，横幅 1536x1152；后端改成 1086x1448 属正常；单张 30–120 秒。
9. **检查**　逐张按 nuyoah-xiezhen-prompt 第六步检查，另核对光向与 `sun.md`、背景方位与底图一致。状态只写 test / failed，用户确认后才 final；重做回到原始分镜重新编译，不用上一轮生成图做输入。把 `out/<plan>/log.jsonl` 复制为 `plans/<plan>/generation_log.jsonl`。
10. **小抄**　`pipeline.py cards <plan> [--images out/<plan>]`（图片按文件名前两位匹配分镜 id），逐页检查：文字溢出、标签重叠、太阳箭头方向、页脚「AI 拍摄示意，非现场实拍」。产物 `cards/card_<id>.png`、`cards/outfit_0*.png` 与 PDF；PDF 顺序固定为 穿搭页 → 静态分镜 → 连拍 / 短片 / 实况，连拍与短片的「相机设置」块会自动换成连拍或 S-Log3 短片的内容。**PDF 文件名固定为 `<出行日期>_<地点>_拍摄小抄.pdf`**（例 `2026-09-28_浅草寺_拍摄小抄.pdf`，改版加 `_v2`），由 `pipeline.py` 按 `shotlist.json` 的 `meta.date` 与 `meta.place`（括号前的部分）自动命名；交付给用户、同步到本机、放进 examples 的文件都用这个名字，不用「拍摄小抄.pdf」这类无日期无地点的名字。
11. **当天资料**　`timeline.md`（交通班次注明来源与查询日期、每张时段、分岔点、最后入场、回程后续 3 班）、`model_sheet.md`（服装/道具/妆发/每张一句话）、`arrival_checklist.md`（到场 10 分钟核对项）、有短片时 `clips.md`（剪辑顺序与转场遮挡物，模板 `templates/clips_template.md`；时间线每条 video 加 1.5 分钟）。

改版：复制为 `<plan>-v2`，只重做变动的分镜，复用图片记 `img_from`，新增分镜单独出图，最后统一重跑 `cards`，`generation_log.jsonl` 合并两轮。

## 分镜基本法（docs/SHOT_DESIGN.md 摘要，lint 按此检查）

- 叙事：一组 9–13 张是一段有开头、高潮、结尾的故事。角色 `role`：`opening` 开场（交代环境，排第一）、`context` 环境（人与场地，走动穿行）、`interaction` 互动（人在做什么，≥ 2）、`portrait` 肖像（情绪与身份）、`detail` 细节（手、道具、局部，≥ 1，给节奏换气）、`closing` 收尾（背影、远眺、俯瞰，排最后）；主图 `hero: true` ≥ 1。每张只讲一件事，两张讲同一件事就删一张。
- 景别配比：远景定氛围 ≥ 1、全身定状态 ≥ 2、七分/中景讲日常 ≥ 1、半身 ≥ 2、近景抓情绪 ≥ 1、特写提质感 ≥ 1；单一景别 ≤ 40%，至少覆盖 4 类。
- 节奏：寄り/引き 交替，相邻两张景别不同，相邻两张焦段档或机位方向不同；焦段覆盖 广(≤35)/标(50)/中长(70–105) 三档；至少一张俯或仰。拍摄顺序按动线，成片顺序按叙事。
- 姿态 `pose` 至少三种（stand/walk/sit/lean/back/crouch）；视线 `gaze` 看镜头（camera）不超过 60%，其余 away/down/closed/back；正面看镜头、侧面看远处、背影靠手部小动作；动作只做一半。
- 裁切不在颈、肘、腕、膝、踝；人朝向景物，人景比例 2:3 或 5:5；至少两张有前景层次，至少一张用框（门洞、拱廊、柱子）。
- 光：阴天靠来源方向造差异（檐下背光、拱廊开口侧光、窗光、店灯）；晴天版至少一张逆光/侧逆光；正午硬光优先门楼、回廊、树荫。
- 一致性：一人一套服装（道具可换）、一种创意外观与白平衡、一个色彩主题；主图是竖幅、构图完整、脸清楚、背景最有辨识度的一张。

## 相机与闪光灯的默认策略（Sony α7 V + HVL-F60RM2）

短片：動画位 4K 24p S-Log3，S&Q 位 60→24 与 120→24 两个预设，斑马 52%/95%，伽马显示辅助开，WB 固定 5600K，三分线网格与 90% 安全框，Dynamic Active，晴天 ND64–256 / 薄云 ND16–32 / 阴天 ND4–8；曝光补偿与测光按每条 `clip.exposure`（逆光以脸为准让背景过曝，白墙水面 +0.3～0.7，深色背景 −0.3）。连拍 H+ 电子 30 张/秒预拍 0.5 s，横向走动果冻明显换机械 10 张/秒。

全组固定一种创意外观（阴雨低饱和用 IN；要保留朱红、靶蓝这类对比色用 FL），WB 固定阴天预设或 5600K，RAW+JPEG；记忆位 M1 散射 / M2 逆光 / M3 黄昏闪光。闪光灯阴天默认关，只在黄昏收尾（后帘同步，TTL −1 EV，1/60）或晴天后侧光补脸（TTL −1.3 EV，HSS）时用；展厅、寺社内堂一律关。细节见 `docs/CAMERA_NOTES.md`。

## 交付

对话中给：调研摘要（spot 列表与来源链接、SNS 结论）、光线摘要（关键时刻与实际直射截止）、分镜表与 lint 结果、每张完整 prompt、图片路径、质量状态与 `generation_log.jsonl`、穿搭方案（`outfit.md`）、小抄 PDF（`<日期>_<地点>_拍摄小抄.pdf`，穿搭页在前、动态在后）、时间线/模特页/到场清单/剪辑单，以及需要现场核实的事项。写作不用设问式标题、「不是A，是B」式对举与破折号金句。
