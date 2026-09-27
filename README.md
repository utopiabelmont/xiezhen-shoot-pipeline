# xiezhen-shoot-pipeline

真实景点、真实日期的人像外拍规划流水线：查出片点 → 算太阳与天气 → 画园区底图 → 写分镜 → 编译写真 prompt → Codex 出示意图 → 合成每张一页的拍摄小抄。

输入一个景点名、一个日期、到场时段和器材，输出：

- `sun.md`　逐时太阳方位/高度/影长、地形遮挡后的实际直射截止、天气光质（硬光/薄云/阴天）
- `spots.md`　周边 POI、公开照片分布、网页与社交平台调研清单
- `basemaps/`　OSM 几何渲染的俯视底图，以及 Codex 重绘的水彩风格版本
- `shotlist.json / shotlist.md`　≥ 9 条分镜：景别、焦段、机位、站位朝向、光型、动作引导、晴天/阴天/雨天备选
- `prompts.md` → `inbox/<plan>.jsonl` → `out/<plan>/*.png`　每张分镜的示意图（Codex Image，走 ChatGPT 订阅内的 Codex 额度）
- `cards/card_XX.png` + `拍摄小抄.pdf`　每张一页：示意图、相机设置、俯视站位与光向图、姿势引导、注意事项
- `timeline.md / model_sheet.md / arrival_checklist.md`　当天时间线、模特一页纸、到场核对清单

示例产物见 [`examples/hakone-0928-v2/`](examples/hakone-0928-v2/)（箱根ガラスの森美術館，2026-09-28，13 张）。

![拍摄小抄示例](examples/hakone-0928-v2/cards/card_02.jpg)

## 工作流

```
 阶段            工具 / 执行者                          产物
 ─────────────── ────────────────────────────────────── ─────────────────────────────
 0 立项          pipeline.py init                       plans/<plan>/plan.json + 模板
 1 出片点        pipeline.py spots  (Nominatim/Overpass/Commons)   spots.md, spots.json
 2 SNS 调研      Claude in Chrome（小红书/IG/抖音/TikTok，人工级） spots_social.md
 3 光线          pipeline.py sun    (astral+pvlib, Open-Meteo)     sun.md, sun.json, sun_path.png
 4 底图          pipeline.py basemap (Overpass out geom)           basemaps/<name>_osm.png, _meta.json
 5 底图风格化    pipeline.py stylize (codex-imagegen edit)         basemaps/<name>_styled.png
 6 分镜          Claude 按 templates/shotlist_template.md         shotlist.json, shotlist.md
 7 prompt        nuyoah-xiezhen-prompt（系列母版 + 同系列变体）    prompts.md
 8 出图          pipeline.py jobs → shots (run_shots.py)          inbox/<plan>.jsonl, out/<plan>/
 9 检查          nuyoah-xiezhen-prompt 第六步 + 光向核对           generation_log.jsonl（status test/failed）
10 小抄          pipeline.py cards (make_cards.py)                cards/, 拍摄小抄.pdf
11 当天资料      Claude 按模板                                    timeline.md, model_sheet.md, arrival_checklist.md
```

每一步的输入、输出、验收标准写在 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)。

## 快速开始

```bash
pip install -r requirements.txt          # Windows 没有系统 Python 时见 docs/WINDOWS_SETUP.md
python check_env.py

python pipeline.py init   hakone-0928 --place "箱根ガラスの森美術館" --date 2026-09-28 --arrive 13:00 --hours 12-18 --elev-m 657
python pipeline.py spots  hakone-0928
python pipeline.py sun    hakone-0928
python pipeline.py basemap hakone-0928 --meters 130
python pipeline.py stylize hakone-0928           # 需要本机 codex-imagegen
#   …人工阶段：SNS 调研、分镜、prompt（见 docs/WORKFLOW.md）…
python pipeline.py jobs   hakone-0928
python pipeline.py shots  hakone-0928
python pipeline.py cards  hakone-0928
python pipeline.py status hakone-0928
```

不联网自测：`spots` / `sun` 加 `--fixture`，`basemap` 加 `--fixture overpass_geom_pola.json --center 35.25666,139.02120`。

## 目录

```
pipeline.py            统一入口（init/spots/sun/basemap/stylize/jobs/shots/cards/status）
run_shots.py           inbox/*.jsonl → codex-imagegen → out/<批次>/ + log.jsonl
check_env.py           依赖与工具自检
tools/
  geo_common.py        地理编码、方位、距离、HTTP（含离线 fixture）
  spots.py             周边 POI + Commons 照片 + 调研关键词
  sun_light.py         太阳位置、地形遮挡、天气光质
  osm_geometry.py      Overpass → 分层几何 → 底图
  basemap.py           几何渲染（v1/v2 格式都能读）
  make_cards.py        小抄页面合成（多底图、室内、园外）
  fixtures/            离线样本
templates/             分镜模板与 JSON Schema、词链模板、SNS 调研表、时间线/清单/模特页模板、底图风格指令
scripts/               Windows：setup.ps1、job.example.ps1（一次性任务模板）
setup.cmd run_job.cmd run_shots.cmd   Windows 双击入口
skill/xiezhen-shoot-planner/SKILL.md  给 Claude 用的流程 skill
docs/                  WORKFLOW（SOP）、WINDOWS_SETUP、CARD_SPEC、CAMERA_NOTES、CHANGELOG
examples/hakone-0928-v2/   完整示例
plans/ inbox/ out/ refs/   运行时目录（out/ 不入库）
```

## 依赖与数据源

| 用途 | 来源 | 说明 |
|---|---|---|
| 太阳位置 | astral、pvlib | 离线计算，两者交叉验证一致（0.05° 内） |
| 天气、高程 | Open-Meteo | 云量、直射/散射辐射、降水概率（16 天预报）；90 m DEM 估算地形遮挡角 |
| 地理编码 | Nominatim | ≤ 1 次/秒，脚本自带 User-Agent |
| 园区几何、POI | Overpass API（OpenStreetMap，ODbL） | `out geom`，`osm_geometry.py` 分层 |
| 公开照片分布 | Wikimedia Commons geosearch | 看常见机位与季节 |
| 社交平台 | 小红书 / Instagram / 抖音 / TikTok | 无公开接口，由 Claude 在已登录的 Chrome 里人工级浏览，记录到 `spots_social.md` |
| 出图 | [codex-imagegen-cli](https://github.com/jdmnk/codex-imagegen-cli)（Codex 内部接口） | 用 Codex 桌面版/CLI 的 ChatGPT 登录；模型由服务端决定 |
| prompt 规则 | [nuyoah-xiezhen-prompt](https://github.com/nuyoah-ai-works/nuyoah-xiezhen-prompt) | 系列母版、同系列变体、第六步检查 |

## 已知限制

- Codex 内部图片接口属 alpha，尺寸不保证（1152x1536 会返回 1086x1448），不能指定模型；要指定模型请改用官方 Images API。
- Open-Meteo 预报只到 16 天，更早的日期只有天文数据；出发前一天再跑一次 `sun`。
- OSM 里没有的步道（例如 Pola 美术馆的森の遊歩道）用 `--extra` 手工补概略线，小抄上要注明「概略」。
- 地形遮挡按 DEM 估算，园内树木与建筑遮挡要现场判断。
- 生成图只是示意，小抄页脚固定写「AI 拍摄示意，非现场实拍」。

## 许可

MIT。OSM 数据遵循 ODbL，Commons 图片各自许可，社交平台内容只记录文字线索不保存图片。
