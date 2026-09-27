# trip.json 模板（一日多景点行程页）

一天去多个景点时写 `plans/<主plan>/trip.json`，`pipeline.py cards` 会把它渲染成 PDF 第一页（`cards/trip_01.png`），也可单独 `pipeline.py trip <plan>`。每个景点各有自己的 plan（分镜、底图、路线页），行程页只管景点之间的顺序、交通与时刻。

```json
{
 "title": "箱根一日：玻璃之森为主，Pola 为雨天备选",
 "date": "2026-09-28",
 "stops": [
  {"name": "箱根湯本駅", "latlon": [35.2320, 139.1057], "role": "origin", "leave": "12:38", "note": "桃源台線[T] 始发站"},
  {"name": "箱根ガラスの森美術館", "latlon": [35.2662, 139.0175], "plan": "hakone-0928-v3", "arrive": "13:00", "leave": "16:45", "note": "主拍摄地，园内路线见下一页"},
  {"name": "ポーラ美術館", "latlon": [35.2574, 139.0210], "arrive": "16:55", "leave": "17:30", "optional": true, "note": "雨天备选"},
  {"name": "箱根湯本駅", "latlon": [35.2320, 139.1057], "role": "end", "arrive": "17:36"}
 ],
 "legs": [
  {"from": 0, "to": 1, "mode": "bus", "line": "箱根登山バス 桃源台線[T]", "minutes": 22, "depart": "12:38", "arrive": "13:00", "source": "NAVITIME 2026-09-27"},
  {"from": 1, "to": 3, "mode": "bus", "line": "桃源台線[T]", "minutes": 22, "depart": "17:14", "arrive": "17:36", "source": "NAVITIME 2026-09-27", "note": "错过就 17:29"}
 ],
 "sources": ["NAVITIME 时刻（查询日期）", "各景点官网营业时间"]
}
```

- `stops` 按当天顺序；`plan` 指向有分镜的企划；`optional: true` 的备选画成灰点。
- `legs` 的 `mode`：bus / train / walk / taxi / car / ropeway / ship；`minutes` 与班次由 Claude 按 NAVITIME、官网或 Google Maps 查询后填，`source` 写来源与查询日期。
- 景点之间的顺序按：营业时间与最后入场 → 光线（逆光时段的景点排在对应时刻）→ 交通班次 → 地理顺路；写在 `sources` 或每站 `note` 里。
- 景点内部的顺序由各 plan 的 `meta.route_stops` 决定（见 `docs/ROUTE_NOTES.md`）。
