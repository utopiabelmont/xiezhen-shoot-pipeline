# 工作流 SOP

一次企划 = `plans/<plan>/` 一个目录。`<plan>` 用「地点缩写-月日」，改版加 `-v2`。
下面每个阶段写清：执行者、命令、输入、输出、验收。阶段 0–5、8、10 是脚本；2、6、7、9、11 是 Codex / Claude（或人）按模板做。

Codex 直接在当前终端运行脚本；安装与能力边界见 `INSTALL.md` 第 4 节。无 SNS 浏览器访问时按下面第 2 节记录缺口；无出图工具时跳过 stylize / shots，保留 OSM 底图并生成无示意图的脚本。离线 fixture 只用于自测，不当作真实出行数据。

## 0 立项

- 执行：`python pipeline.py init <plan> --place "<景点>" --date YYYY-MM-DD --arrive HH:MM --hours 8-18 [--lat --lon] [--elev-m] [--gear "..."] [--body] [--flash] [--outfit]`
- 输入：景点名（或坐标）、日期、到场时段、器材（机身、镜头焦段范围、有无闪光）、人物数与服装方向。缺日期或器材先问一次，其余按默认。
- 输出：`plan.json`；同时把 `templates/` 里的 SNS 调研表、时间线、到场清单、模特页复制为待填模板。
- 验收：`plan.json` 有 place / date / hours / gear。

## 1 出片点

- 执行：`python pipeline.py spots <plan> [--radius 1500]`
- 输出：`spots.md`（POI 表、Commons 照片分布、网页调研关键词）、`spots.json`
- 接着由 Codex / Claude 按 `spots.md` 末尾的关键词做网页调研：官方见どころ页、日文/中文摄影攻略、拍摄规则、票价、开放时间。记录到 `spots.md` 末尾或 `spots_social.md`。
- 验收：至少 6 个候选机位，每个有园内位置、背景方位、季节/人流线索。

## 2 社交平台调研

- 执行：当前代理的浏览器工具（Codex 或 Claude，工具可用时），用户已登录的账号，人工级浏览（不批量抓取、不下载图片）。
- 平台与检索词：小红书「<中文名>」「<中文名> 机位」；Instagram `#<日文名>`；抖音「<中文名> 拍照机位」；TikTok「<日文名>」+ 官方账号。
- 各平台在 Chrome（用户已登录）里的可行路径（2026-09-27 实测）：
  - 小红书：直接打开 `search_result?keyword=` 常常空白；要在 `/explore` 首页的搜索框里输入关键词回车，结果页右侧的「点点」AI 会汇总 30 篇左右笔记的机位与时段，先读它，再点 1–3 篇高赞帖看正文（视频帖正文很短）。用 JS 直接跳转 `/explore/<id>` 会触发 300031 风控，拦一次就停。
  - 抖音：`https://www.douyin.com/search/<关键词>` 可用，等 10 秒以上再读页面文字；图文帖的文案含机位说明。
  - TikTok：`https://www.tiktok.com/search?q=<关键词>` 首次常报「不明なエラー」，点「もう一度お試しください」即出结果；未登录也能看列表。
  - Instagram：`https://www.instagram.com/explore/search/keyword/?q=%23<标签>` 可用，读图片 alt 文本（含器材与参数的帖子最有用）。
- 平台最新动态也要看：祭典、灯笼祭、投影活动、临时封闭（TikTok/抖音的近期帖最快）。
- 记录：`spots_social.md`（模板 `templates/sns_research.md`）：机位、朝向、时段、人流、规则、票价、交通；每条附标题/作者/赞数便于回查。另记「穿搭」栏：出片帖里主流穿什么颜色、场地着装限制、当季游客色彩倾向（给阶段 2b）。
- 素材表：出过片的机位帖、姿势帖与平台汇总逐条记进 `sns_refs.json`（编号 S / X+P / Q，字段见 `docs/SNS_NOTES.md`）。看图写字：机位、构图、人物在画面里的位置与大小、前景背景、姿势、穿搭、天气光线都写成文字；不下载、不截图原帖图片，也不把原帖图片交给生图模型。用户想在私用版里看原图时自己用手机保存，放进 `sns_inbox/` 后跑 `pipeline.py sns-import <plan>`。
- 验收：末尾「对分镜的影响」写清：与主流机位重合的、本组差异化机位、新增备选（雨天/室内/园外）、需现场核实的。

无法访问登录平台时，在 `spots_social.md` 记录平台、日期、原因与未验证项；只采用实际可读的公开页面或用户的文字资料。未看过原帖就不记录其构图、点赞数或设备为事实；没有 SNS 素材的分镜用 `src.kind="无 SNS 素材"`，`meta.sns` 写明缺口，继续其余阶段。

## 2b 穿搭

- 执行：`python pipeline.py palette <plan> [--n 12]`（从阶段 1 的 Commons 照片抽 6 个场地主色 → `palette.json` / `palette.png`；也可 `--images <目录>` 用自己的现场照）。然后 Codex / Claude 按 `docs/OUTFIT_GUIDE.md` 与 `templates/outfit_template.md` 写 `outfit.json`（路线、色、主方案、替换方案、道具妆发、逐张提醒、SNS 观察），导出 `outfit.md`。
- 输入：`palette.json`、`spots_social.md` 的穿搭栏、`sun.md` 的天气与季节、分镜动作需求（走/坐/蹲/背影/撑伞）、场地规则。
- 输出：`outfit.json`、`outfit.md`；阶段 10 会把它渲染成 PDF 第一页；`meta.outfit`、prompt 的 OUTFIT 词链、`model_sheet.md` 都从它来。
- 验收：`lint` 的两条：主色 ≤ 3（点缀 `accent: true` 不计）；主色与场地前四个主色 ΔE ≥ 12（有意融入标 `blend_ok: true`）。

## 3 光线

- 执行：`python pipeline.py sun <plan> [--step 30] [--weather-only] [--weather-json f]`（内部：astral + pvlib 交叉验证；Open-Meteo 天气与高程；地形遮挡环采样 500–8000 m）
- 输出：`sun.md`、`sun.json`（rows：time / azimuth / elevation / shadow_ratio / quality / terrain_horizon / blocked）、`sun_path.png`
- 规则：日期超出 16 天预报范围时只用天文数据，临近再跑；出发当天早上再跑一次。
- 天气光质判定：直射比 ≥ 0.5 且云量 < 60% → 晴天硬光；≥ 0.5 → 高云透光；0.2–0.5 → 薄云；< 0.2 → 阴天。
- 验收：`sun.md` 有逐时表、实际直射截止时刻、人物朝向与光型表。

## 4 底图

- 执行：`python pipeline.py basemap <plan> [--name main] [--meters 130] [--center lat,lon] [--extra x.json]`
- 输出：`basemaps/<name>_geometry.json`（分层：wood / clearing / grass / water / buildings / roads / paths / points）、`<name>_osm.png`（北在上、无文字）、`<name>_meta.json`（中心与米/像素）
- `--meters` 取园区最长边的 1.2 倍；园外备选点另做一张底图（`--name pola --center ...`）。
- OSM 缺失的步道/装置用 `--extra`（格式 `templates/geometry_extra_example.json`），`approx: true` 的线在小抄上注明「概略」。
- 验收：打开 `<name>_osm.png`，水面、建筑、步道与官方园内图方向一致。

## 5 底图风格化

- 执行：`python pipeline.py stylize <plan> [--name main]`（codex-imagegen `edit`，指令在 `templates/basemap_style_prompt.txt`）
- 输出：`basemaps/<name>_styled.png`（1254×1254，几何保持不变）
- 验收：与 `_osm.png` 并排对比，形状位置未漂移；无文字、箭头、指北针。漂移则重跑一次，仍漂移则改指令里的元素描述。

## 6 分镜

- 执行：Codex / Claude 按 `templates/shotlist_template.md` 与 `templates/shotlist_schema.json` 写 `shotlist.json`，再导出 `shotlist.md`。
- 硬性要求：≥ 9 条；景别覆盖特写、近景、半身、全身、环境远景中至少 4 种；焦段只从器材里选；每条写太阳方位、光型、人物朝向、机位距离；每条给晴天/阴天/雨天备选；同组内动作、视线、机位不重复。
- 俯视图字段：`subject_latlon`、`cam_bearing`、`cam_dist`、`face_bearing`、`bg_bearing`、`bg_label`；园外点加 `basemap`，室内点加 `indoor: true`；`alt_time` 指晴天版时刻；`meta.sun` 从 `sun.json` 取整点与半点。
- 步行导航字段（1.9.0）：`subject_latlon` 要精确到站位（5 位小数约 1 m），用 OSM 节点、Google 地图或底图核对；长焦远机位写 `walk_to: {"to": "camera"}`，室内写 `walk_to: {"place_id": "...", "label": "<店名> <楼层>"}`，终点巴士站等写 `walk_to: {"latlon": [...], "label": "..."}`。每页分镜卡与核对表据此生成谷歌地图步行导航链接与二维码（见 `docs/CARD_SPEC.md`）。
- SNS 驱动：分镜从 `sns_refs.json` 的素材出发，每条机位帖、每个姿势各设计一张同款（机位、焦段、构图、姿势照原帖），每张写 `src`（来源、照搬了什么、同款姿势）；素材覆盖不到的开场、过渡、细节、连拍、短片、实况再补，`src.kind` 写「无 SNS 素材」。`meta.sns` 一句话记录素材的使用情况。细则见 `docs/SNS_NOTES.md`。
- 基本法：每条写 `role`（opening/context/interaction/portrait/detail/closing）、`pose`、`gaze`，主图 `hero: true`，备选 `optional: true`；景别配比、节奏、姿态视线规则见 `docs/SHOT_DESIGN.md`。
- 动态素材：每条可写 `medium`（still / burst / video / live，缺省 still），规则与字段见 `docs/VIDEO_NOTES.md`。连拍出的照片计入组图；短片与实况不计入张数与景别配比。作为补充加在静态分镜之后的条目标 `supplement: true`（不参与首尾与相邻检查）。一组要求 ≥ 2 张 burst、≥ 5 条 video、≥ 6 条 live（lint 提示项）。
- 验收：`python pipeline.py lint <plan>` 硬性项全部通过（`jobs` 阶段会先跑 lint，不过不生成任务）；提示项逐条看，能改就改。

## 6b 路线

- 执行：在 `shotlist.json` 的 `meta.route_stops` 写停留点顺序（每站的分镜 id 与备注）、`meta.route_source`、`meta.route_speed_mps`；`python pipeline.py route <plan>`（`cards` 阶段也会自动跑）。一天多景点另写 `trip.json`（模板 `templates/trip_template.md`），`pipeline.py trip <plan>`。
- 依据与规则见 `docs/ROUTE_NOTES.md`：官网設施顺序 / 順路 → 攻略「先拍哪里」→ 天气 → 地理最短路；交通班次注明来源与查询日期。
- 输出：`route.json` / `route.md` / `cards/route_01.png`（底图上的步道路线与编号站点、到达离开时刻）；`trip.md` / `cards/trip_01.png`（一日行程示意与时刻表）。
- 编号：路线定下来后跑 `python pipeline.py renumber <plan>`，分镜编号改成游览顺序（01 是路线上的第一张，备选排最后），每张的时段按停留点的到达—离开时刻均分，同时改 `outfit.json` 的 per_shot、`sns_refs.json`、`prompts.md` 标题，写 `id_map.json`（新 → 旧）；脚本列出的旧编号引用手改。已出的图用 `--rename-images` 一起改名，或改完编号再出图。
- 验收：路线不穿建筑与水面（穿了就改底图 `--extra` 补步道）；终点在出口附近；总时长不超过营业时间；`timeline.md` 的班次与之一致。

## 7 prompt

- 先写 `scene_bible.md`：场地的真实样子（建筑材质颜色、桥与栏杆形制、标志物的高度形状与位置、当季植被）和容易被画错的东西，场景词链与负面词从它来。
- 执行：已安装的 `nuyoah-xiezhen-prompt`，未安装时直接用 `templates/prompt_chains.md` 的「系列母版 + 同系列变体」：全组固定风格词链、成像词链、人物与服装（`templates/prompt_chains.md`），每张只改取景与机位、动作与视线、环境与光线。有 `src` 的分镜，取景段直接用 `sns_refs.json` 里对原帖构图的文字描述（人物位置比例、前景背景的先后），姿势段用 `src.pose_how`；只用文字，不加参考图。
- 光线模块直接引用 `sun.md` 的方位、高度、光质与影长，按「来源—落点—结果」写；无参考图时写「本张重新生成一位「…」类型的成年原创女性」。
- 输出：`prompts.md`，每张一节：`## <id>-<标题>` 后接一个 ```text 代码块（`pipeline.py jobs` 靠这个格式解析；标题会成为文件名，不要带 `/`）。
- 短片三帧：每条短片另写 `move_prompts.md`，`## <id>a-起幅` / `## <id>b-中间` / `## <id>c-落幅` 三节，人物、服装、场景、光线沿用该短片的词链，只换每一帧的取景与动作，并写「主体放在画面中间约七成宽度内」（运镜页会裁成 9:16）。
- 验收：每条 prompt 含画幅、焦段、机位、景别、人物、动作、服装、环境、光线、成像、负面十段。

## 8 出图

- 执行：`python pipeline.py jobs <plan>`（追加分镜后用 `--missing` 只排还没出图的） → `inbox/<plan>.jsonl`；`python pipeline.py shots <plan>`（`run_shots.py`：每条只提交一次，失败只记录，不改词不重试）
- 输出：`out/<plan>/<id>.png`、`<id>.txt`（本张完整 prompt）、`log.jsonl`
- 尺寸：3:4 → 1152x1536；4:5 → 1216x1520；1:1 → 1024x1024；横幅 → 1536x1152。后端会改成 1086x1448 等，属正常。
- 短片三帧：`python pipeline.py jobs <plan> --moves` → `inbox/<plan>-moves.jsonl`，`python pipeline.py shots <plan> --moves` → `out/<plan>-moves/`；挑好的三帧放进 `plans/<plan>/move_frames/`（没有这个目录时直接读 `out/<plan>-moves/`）。
- 验收：`log.jsonl` 每条 status 为 test 或 failed，`generated_image_inputs: none`。

## 9 检查

- 执行：Codex / Claude 逐张看图，按本节检查项；已安装 nuyoah-xiezhen-prompt 时另按其第六步（人物、服装与道具分离、光线来源落点结果、景别焦段是否吻合、畸形与水印），另加：光向是否与 `sun.md` 该时段一致、背景方位是否与底图一致、构图与 `sns_refs.json` 对原帖的描述是否一致（人物位置、朝向、前景背景）。短片三帧看起中止之间的变化是否符合运镜（人物大小、俯仰、朝向）。
- 记录：把 `out/<plan>/log.jsonl` 复制为 `plans/<plan>/generation_log.jsonl`；复用旧版图片的分镜加 `img_from` 与 `reused_from_v1: true`。
- 规则：状态只写 test / failed，用户确认后才 final；重做时回到原始分镜与参考重新编译，不把上一轮生成图作为输入。

## 10 拍摄脚本与核对表

- 执行：`python pipeline.py cards <plan> [--images out/<plan>]`（`make_cards.py`；图片按文件名前两位 = 分镜 id 匹配）
- 输出：`cards/card_<id>.png`（1600×1067）、`<出行日期>_<地点>_拍摄脚本.pdf`（例：`2026-09-28_浅草寺_拍摄脚本.pdf`；改版加 `_v2`）
- PDF 顺序：行程页（有 `trip.json`）→ 穿搭页（有 `outfit.json`）→ 路线页（有 `route_stops`）→ 分镜按路线顺序（静态与动态穿插，短片卡后接运镜页）；没有路线时静态在前、动态在后。短片与实况的示意图是关键帧，页脚会注明。
- 每张分镜卡右下「时段 · 地点 · 步行导航」：坐标、谷歌地图步行导航链接与二维码；PDF 里二维码与导航行可直接点按（需要 pypdf）。
- 分镜卡：有 `src` 时左侧一张示意图，中间一栏 SNS 来源（素材类型与可复现度、平台日期、原帖标题、二维码、照搬了什么、同款姿势、现场差异、链接），补充分镜写「无 SNS 素材」；分镜都带 `src` 时不再出 SNS 汇总页与姿势参考页。没有 `src` 的旧企划仍是示意图与原帖对照的版式。
- 有短片时，每条短片的分镜卡后面插一页运镜示意（`tools/moves.py`，`cards/move_<id>.png`：俯视轨迹、侧视高度与俯仰、操作要点、起中止三帧、时间条），另出手机竖版 `cards/movem_<id>.png` 给核对表用。起中止三帧优先用 `move_frames/` 里 Codex 按文字画的三张（缺一张就退回按焦段与距离推算的线稿），此时画面变化区放大。全部短片的「短片一览」只放进核对表（`moves_overview_m.png`），不进 PDF。有 `move_frames/` 时同时出每条短片的运镜动图 `cards/move_<id>.gif`（`tools/move_gif.py`：俯视图上相机与人物同步移动，右侧三帧交叉淡化），可直接发给同伴看。
- 同时生成 `<出行日期>_<地点>_拍摄核对表.html`（`tools/checklist.py`，也可单独 `pipeline.py checklist <plan>`）：器材（按分镜的焦段与介质自动列）、服装道具妆发（`outfit.json`）、行程（`trip.json`）、到场核对（`arrival_checklist.md` 第一个二级标题之前的列表）、分镜按路线停留点分组（缩略图取 `out/<plan>/`，`--no-thumbs` 不嵌；有 `src` 时每条下面一行来源，点开原帖）、短片运镜一览、收尾。单文件，手机离线可用，勾选状态存在浏览器本地。
- 页面规范见 `docs/CARD_SPEC.md`。俯视图里的太阳箭头必须与 `meta.sun` 该时刻一致；室内不画太阳；园外用各自底图。
- 验收：逐页看：文字不溢出、俯视图标签不重叠、页脚「AI 拍摄示意，非现场实拍」在。

## 11 当天资料

- `timeline.md`：交通班次（NAVITIME 等，注明查询日期）、每张分镜的时段、分岔点、最后入馆、回程后续 3 班。
- `model_sheet.md`（可再合成一张长图）：服装、道具、妆发、每张「对你说的一句话」。
- `clips.md`（有短片时）：剪辑顺序、转场遮挡物（模板 `templates/clips_template.md`）；时间线里每条 video 加 1.5 分钟。
- `arrival_checklist.md`：到场 10 分钟走一圈要核对的事项（装置在不在、站位能不能站、室内规则、天空状态、相机记忆位）。
- 出发前一天：`pipeline.py sun <plan> --weather-only` 只刷新预报（不重算地形；本机不能联网时用浏览器取回 Open-Meteo 响应存成 JSON，加 `--weather-json <文件>`）。预报变了就在 `shotlist.json` 的 `meta.forecast` 与 `trip.json` 的 `weather.summary` / `notes` 记录，决定用晴天版还是阴天版，然后重跑 `cards`（行程页天气栏、PDF、核对表一起更新）。

## 改版（v2）流程

同一企划纳入新情报（SNS、现场踩点）时，复制目录为 `<plan>-v2`，只重做变动的分镜：保留可复用的图片（`img_from`），新增分镜单独出图（`inbox/<plan>-v2-新增.jsonl`），最后统一重跑 `cards`。`generation_log.jsonl` 合并两轮记录。

## Windows 双击执行

没有终端权限时（例如由 Codex / Claude 远程操作），把要跑的命令写进根目录 `job.ps1`（模板 `scripts/job.example.ps1`，必须 UTF-8 with BOM），双击 `run_job.cmd`，看 `job_log.txt` 与 `job_done.txt`。详见 `docs/WINDOWS_SETUP.md`。
