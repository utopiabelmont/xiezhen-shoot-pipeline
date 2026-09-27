# 变更记录

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
