# 变更记录

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
