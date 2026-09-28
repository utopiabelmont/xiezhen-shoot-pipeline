# 变更记录

## 1.6.1 — 2026-09-28

- 运镜库动图：`tools/moves_library_prompts.py` 写 11 种运镜 × 4 帧的逐帧 prompt（同一原创人物、服装与虚构庭园），Codex 纯文字出图；`tools/move_gif.py --library` 合成每种运镜一张 GIF 和一张总览 GIF（左俯视图相机与人物同步移动，右竖幅画面交叉淡化），README 的运镜库换成动图。
- `move_gif.py --plan`：企划有 `move_frames/` 时，`cards` 阶段另出每条短片的 `cards/move_<id>.gif`。

## 1.6.0 — 2026-09-28

- SNS 素材驱动的分镜（`docs/SNS_NOTES.md`）：调研时把出过片的机位帖、姿势帖与平台汇总逐条写进 `sns_refs.json`（编号 S / X+P / Q），机位、构图、人物位置比例、前景背景、姿势、穿搭都写成文字；分镜从素材出发设计同款，每张写 `src`（schema 已加），素材覆盖不到的再补。
- 原帖图片不抓取、不截图、不交给生图模型；生图只用文字描述。用户自己保存的原图放进 `sns_inbox/`，`pipeline.py sns-import` 按编号归到 `sns_private/`（gitignore，公开版不放）。
- 分镜卡：有 `src` 时左侧一张示意图，中间一栏来源（素材类型与可复现度、平台日期、原帖标题、二维码、照搬了什么、同款姿势、现场差异、链接）；补充分镜标「无 SNS 素材」。分镜都带 `src` 时不再出 SNS 汇总页与姿势参考页。没有 `src` 的旧企划：原帖位置显示私用截图，或按文字重画的构图线稿（`sns_sketch/`）加二维码，或二维码占位。
- 核对表：每条分镜下面一行来源，点开原帖。
- `pipeline.py renumber`（`tools/renumber.py`）：编号按游览路线重排，时段按停留点均分，同步 `outfit.json`、`sns_refs.json`、`prompts.md`，写 `id_map.json`，列出正文里的旧编号引用。
- 运镜页：`move_prompts.md` → `pipeline.py jobs/shots --moves` 出起 / 中 / 止三帧，放进 `move_frames/` 后替换线稿三帧并放大画面变化区；短片一览只进核对表，不进 PDF。
- `jobs`：id 里的 `/` 等文件名非法字符自动替换。
- 箱根示例 v5：38 张（25 张有 SNS 来源、13 张补充），编号按路线，PDF 47 页。

## 1.5.1 — 2026-09-28

- 短片一览页：本组全部短片按游览顺序汇成一页（每条俯视轨迹 + 起中止三帧 + 看图方法），PDF 放在路线页之后、分镜之前；核对表加「短片运镜一览」展开项（单列竖版）。
- `moves.py` 在路线之后运行，一览与运镜页按 `route.json` 的游览顺序；箱根示例 PDF 43 页。

## 1.5.0 — 2026-09-28

- 运镜示意页：`tools/moves.py`（`cards` 阶段自动）给每条短片在分镜卡后插一页，含以人物为中心的俯视轨迹（相机与人物起止位置、每秒位置、终点视野）、侧视机高与俯仰、操作要点、起 / 中 / 止三帧竖幅画面（按焦段、距离、机高与俯仰推算，叠三分线与 90% 安全框，柱子与树作背景参照）、时间条与 S&Q 成片时长。
- 支持 11 种运镜：下摇揭示、遮挡揭示、侧跟、后跟、前跟、固定微推、1/4 环绕、固定转身回眸、固定升格、后拉上摇、固定人走远；`clip.move_type` 可显式指定，另有 `cam_h`、`walk_m`、`tilt_start`、`tilt_end`、`orbit_side`、`cam_dist_start/end`。
- 核对表的短片条目加「运镜示意」展开项（手机竖版 `movem_<id>.png`）；`docs/img/moves_library.jpg` 运镜库总览；箱根示例 v3.5，PDF 42 页。

## 1.4.0 — 2026-09-27

- 产物改名：PDF 由「拍摄小抄」改为 `<日期>_<地点>_拍摄脚本[_vN].pdf`；`cards` 会清掉旧名的 PDF；示例 PDF 同步改名。
- 行程页加「当天天气」：按行程起止时刻截取 `sun.json` 的逐时天气（天气、降水量、降水概率、气温与体感、风速），加日落与地形遮挡后的直射截止；`trip.json` 新增可选 `weather.summary` / `weather.notes`。
- `sun`：Open-Meteo 请求加气温、体感、降水量、风速、湿度与全天最高最低温、累计降水；`--weather-only` 只刷新已有 `sun.json` 的预报（出发前一天用）；`--weather-json` 读入浏览器等途径取回的响应。
- 新增核对表：`tools/checklist.py`（`pipeline.py checklist`，`cards` 阶段自动生成）输出单文件 `<日期>_<地点>_拍摄核对表.html`，器材按分镜介质自动列、服装道具、行程、到场核对、分镜按路线分组可勾选（缩略图、展开细节、按介质筛选、总进度），勾选存在浏览器本地。
- 箱根示例升到 v3.4：9/27 23:27 刷新预报（上午大雨，到馆后小雨转毛毛雨，风 4 m/s），行程页天气栏、到场清单与 `meta.forecast` 同步。

## 1.3.0 — 2026-09-27

- 路线：`tools/route.py`（`pipeline.py route`）按 `meta.route_stops` 沿底图步道算游览路线，输出 `route.json` / `route.md` / `cards/route_01.png`；PDF 分镜改为按路线顺序排。
- 行程：`tools/trip.py`（`pipeline.py trip`）按 `trip.json` 画一日多景点行程页 `cards/trip_01.png`；PDF 顺序 行程 → 穿搭 → 路线 → 分镜。
- `docs/ROUTE_NOTES.md`、`templates/trip_template.md`、schema 加 `route_stops` / `route_source` / `route_speed_mps`；箱根示例升到 v3.3（14 站路线页 + 行程页，37 页）。

## 1.2.1 — 2026-09-27

- `skill/xiezhen-shoot-planner/SKILL.md` 与已保存的 skill 同步（描述加穿搭与动态素材，交付项加 lint 结果与剪辑单）；新增 `skill/README.md` 阶段总览。
- 动态素材配比改为 短片 ≥ 5 条、实况 ≥ 6 条（lint 提示）；箱根示例升到 v3.2：5 短片 / 6 实况 / 2 连拍。

## 1.2.0 — 2026-09-27

- 阶段 2b「穿搭」：`pipeline.py palette` 从 Commons 场地照抽 6 个主色（`tools/palette.py`）；`docs/OUTFIT_GUIDE.md` 穿搭基本法；`outfit.json` → `tools/make_outfit_page.py` 渲染成小抄 PDF 第一页；`lint` 检查主色 ≤ 3 与服装色/场地色 ΔE ≥ 12。
- 动态素材：分镜 `medium`（still / burst / video / live）与 `burst` / `clip` / `live` 字段；`docs/VIDEO_NOTES.md`（α7 V 连拍与预拍、S-Log3 曝光基准与 ND、24p 实时 ≤ 5 s 与 S&Q 升格、运镜库、iPhone 实况）；小抄按介质换「相机设置」块与页脚徽章；PDF 顺序 穿搭页 → 静态 → 动态；`lint` 提示连拍 < 2；短片/实况不计入 9 张与景别配比；`supplement: true` 补充条目不参与顺序检查。
- `jobs --missing` 只排还没出图的分镜；`templates/outfit_template.md`、`templates/clips_template.md`；SNS 调研模板加「穿搭观察」。
- 示例 `examples/hakone-0928-v3` 升到 v3.1：穿搭页 2 张 + 原 20 张静态 + 2 连拍 / 3 短片 / 2 实况。

## 1.1.2 — 2026-09-27

- `pipeline.py register [--root] [--show]`：把仓库路径登记到 `~/.xiezhen-pipeline/config.json`（可用 `XIEZHEN_CONFIG` 改位置）；`setup.cmd` 最后一步自动调用。
- skill 不再写死本机路径，改为「对话指定 → 已连接文件夹 → config.json」三级查找；INSTALL.md 第 4 节同步。

## 1.1.1 — 2026-09-27

- 新增 `INSTALL.md`：新电脑安装（Windows / macOS / Linux、codex-imagegen、skill 安装、自测、更新、常见问题）；README 快速开始与目录同步。
- 新增示例 `examples/hakone-0928-v3`：按分镜基本法重做的箱根 20 张（19 主线 + 1 备选），lint 无提示，作为当前规则下的标准参考。
- README 增加 v3 示意图一览。

## 1.1.0 — 2026-09-27

- 新增 `docs/SHOT_DESIGN.md` 分镜基本法（叙事角色、景别配比、寄り/引き 节奏、姿态与视线、裁切、光线、一致性）与 `pipeline.py lint`；`jobs` 阶段先 lint，硬性项不过不生成任务。
- `shotlist.json` 新增 `role` / `hero` / `pose` / `gaze` / `optional` 字段；两个示例已补字段（示例分镜早于本规则，lint 仍有若干提示项，作为改版参考保留）。
- SNS 调研补充各平台的可行路径（小红书在首页搜索框输入、抖音搜索 URL、TikTok 报错点「もう一度」、Instagram 关键词页）。

## 1.0.2 — 2026-09-27

- 小抄 PDF 改为 `<出行日期>_<地点>_拍摄小抄[_vN].pdf`（按 `meta.date` / `meta.place` / `meta.version` 自动命名），`cards` 阶段会清掉旧命名的副本；示例与文档同步。

## 1.0.1 — 2026-09-27

- `osm_geometry.py`：底图只保留地标类点位（雕塑、观景点、历史点、寺社、塔），上限 60 个，密集城区不再一片黑点。
- `geo_common.http_json`：5xx / 超时自动重试 3 次（Overpass 偶发 504）。
- `stylize --prompt-extra`：可追加指令，例如城区底图「没有河流，宽道路仍画成路面」。
- 新增示例 `examples/asakusa-0928`：浅草寺雨天上午 12 张，南北两张底图。

## 1.0.0 — 2026-09-27

- 首个规范化版本：`pipeline.py` 统一入口，阶段 0–11 SOP（docs/WORKFLOW.md）。
- `tools/osm_geometry.py`：Overpass `out geom` → 分层几何 → 底图；支持 `--extra` 手工补线、`--fixture` 离线。
- `tools/basemap.py`：v2 分层格式 + v1 手工格式兼容。
- `tools/make_cards.py`：多底图（`basemap` 字段）、室内（`indoor`）、园外窗口（`map_window_m`）、`alt_time` 半点太阳表、说明文字自动截断、页脚移到照片下方。
- `templates/`：分镜 JSON Schema 与示例、词链模板、SNS 调研表、时间线/清单/模特页模板、底图风格指令。
- `scripts/`：Windows 部署（uv + venv）、一次性任务模板（UTF-8 BOM）。
- `examples/hakone-0928-v2`：箱根ガラスの森美術館 13 张完整示例（含 Pola 美术馆园外备选的独立底图）。

## 0.x — 2026-09-27（会话内迭代）

- 验证 codex-imagegen-cli 路线（ChatGPT 订阅内 Codex 额度）10 + 4 张出图。
- sun_light（astral/pvlib/Open-Meteo/地形）、spots（Nominatim/Overpass/Commons）。
- 小抄 v1（通用示意图）→ v2（OSM 底图 + Codex 水彩风格化 + 精确叠加）。
- 纳入小红书 / Instagram / 抖音 / TikTok 调研，分镜 10 → 13 张。
