#!/usr/bin/env python3
"""
route.py　园内游览路线：把分镜按停留点顺序串起来，沿底图里的步道算步行路径，画成小抄 PDF 的「路线页」。

  python tools/route.py --plan plans/<plan> --out plans/<plan>/cards [--speed 1.0]

输入：
  plans/<plan>/shotlist.json    meta.route_stops = [{"name": "光之回廊", "shots": ["02","21","23","03","04","24"], "note": "..."}, ...]
                                （按官网/攻略给的顺路排；没有时按每条分镜的 time 起点自动排）
                                meta.route_source 写依据（官网页面、小红书帖）；meta.arrive 是起点时刻
  plans/<plan>/basemaps/<name>_geometry.json + _meta.json + _styled.png（v1 手工格式与 v2 分层格式都能读）
输出：
  plans/<plan>/route.json  停留点顺序、每段步行距离/分钟、到达/离开时刻、总时长
  plans/<plan>/route.md    同上，给人读
  cards/route_01.png       底图上画路线与编号站点 + 右侧时间表（1600×1067，与小抄同版式）
停留时间按介质：still 8 分钟、burst 4、video 4、live 1（每站再加 2 分钟机动）；步行速度默认 1.0 m/s，雨天 --speed 0.85。
分镜的 subject_latlon 会吸附到最近的步道；两站之间在步道图上找最短路，找不到就画直线并标「概略」。
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_cards import W, H, BG, GREEN, INK, MUTED, PANEL, LINE, GOLD, font, panel, text_block, latlon_to_px  # noqa: E402

DWELL = {"still": 8, "burst": 4, "video": 4, "live": 1}
STOP_EXTRA = 2
ROUTE_COLOR = (176, 98, 40)


def meters(a, b):
    kx = 111320 * math.cos(math.radians((a[0] + b[0]) / 2)); ky = 110540
    return math.hypot((a[1] - b[1]) * kx, (a[0] - b[0]) * ky)


def polylines_from_geometry(g: dict):
    """返回 [[(lat,lon),...], ...]，兼容 v1 手工格式与 v2 layers 格式。"""
    lines = []
    L = g.get("layers", g)
    for key, val in L.items():
        if key in ("wood", "water", "buildings", "terrace", "terraces", "points", "clearing", "grass"):
            continue
        if isinstance(val, dict):          # v2: {"paths": [{"line": [...]}]} 已在 layers 里；buildings dict 已跳过
            continue
        if not isinstance(val, list) or not val:
            continue
        first = val[0]
        if isinstance(first, dict) and "line" in first:
            lines += [[tuple(p) for p in item["line"]] for item in val if len(item.get("line", [])) >= 2]
        elif isinstance(first, (list, tuple)) and first and isinstance(first[0], (int, float)):
            lines.append([tuple(p) for p in val])            # 单条折线
        elif isinstance(first, (list, tuple)):
            lines += [[tuple(p) for p in pl] for pl in val if len(pl) >= 2]
    return lines


class Graph:
    def __init__(self, lines, snap_m=8.0):
        self.nodes = []      # (lat,lon)
        self.adj = {}        # i -> {j: dist}
        for pl in lines:
            prev = None
            for p in pl:
                i = self._node(p)
                if prev is not None and prev != i:
                    self._edge(prev, i, meters(self.nodes[prev], self.nodes[i]))
                prev = i
        # 折线端点之间 8 m 内视为连通（OSM 常常差一点没接上）
        n = len(self.nodes)
        for i in range(n):
            for j in range(i + 1, n):
                if j in self.adj.get(i, {}):
                    continue
                d = meters(self.nodes[i], self.nodes[j])
                if d <= snap_m:
                    self._edge(i, j, d)

    def _node(self, p):
        for i, q in enumerate(self.nodes):
            if abs(q[0] - p[0]) < 1e-7 and abs(q[1] - p[1]) < 1e-7:
                return i
        self.nodes.append((float(p[0]), float(p[1])))
        return len(self.nodes) - 1

    def _edge(self, i, j, d):
        self.adj.setdefault(i, {})[j] = d
        self.adj.setdefault(j, {})[i] = d

    def snap(self, p):
        """把点吸附到最近的边上：新建节点并接入该边两端。返回节点 id 与吸附距离。"""
        best = (None, 1e18, None)
        for i, nb in self.adj.items():
            for j in nb:
                if j < i:
                    continue
                a, b = self.nodes[i], self.nodes[j]
                t = self._proj_t(p, a, b)
                q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                d = meters(p, q)
                if d < best[1]:
                    best = ((i, j, q), d, None)
        if best[0] is None:
            k = self._node(p); return k, 0.0
        (i, j, q), d, _ = best
        k = self._node(q)
        if k not in (i, j):
            self._edge(i, k, meters(self.nodes[i], q)); self._edge(k, j, meters(q, self.nodes[j]))
        return k, d

    @staticmethod
    def _proj_t(p, a, b):
        ax, ay = 0.0, 0.0
        kx = 111320 * math.cos(math.radians(a[0])); ky = 110540
        bx, by = (b[1] - a[1]) * kx, (b[0] - a[0]) * ky
        px, py = (p[1] - a[1]) * kx, (p[0] - a[0]) * ky
        L2 = bx * bx + by * by
        if L2 == 0:
            return 0.0
        return max(0.0, min(1.0, (px * bx + py * by) / L2))

    def path(self, s, t):
        dist = {s: 0.0}; prev = {}; pq = [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == t:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, w in self.adj.get(u, {}).items():
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
        if t not in dist:
            return None, None
        seq = [t]
        while seq[-1] != s:
            seq.append(prev[seq[-1]])
        return [self.nodes[i] for i in reversed(seq)], dist[t]


def hhmm(m):
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def parse_hhmm(s):
    import re
    m = re.search(r"(\d{1,2}):(\d{2})", s or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 13 * 60


def auto_stops(shots):
    """没有 route_stops 时：按 time 起点排序，同一 spot 合并成一站。"""
    order = sorted(shots, key=lambda s: parse_hhmm(s.get("time", "")))
    stops = []
    for s in order:
        if stops and stops[-1]["name"] == s.get("spot", "")[:12]:
            stops[-1]["shots"].append(s["id"])
        else:
            stops.append({"name": s.get("spot", s["title"])[:12], "shots": [s["id"]]})
    return stops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--speed", type=float, default=1.0, help="步行 m/s")
    ap.add_argument("--basemap", default="main")
    a = ap.parse_args()
    plan = Path(a.plan); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    data = json.loads((plan / "shotlist.json").read_text(encoding="utf-8"))
    meta, shots = data["meta"], {s["id"]: s for s in data["shots"]}
    bm = plan / "basemaps"
    geo = json.loads((bm / f"{a.basemap}_geometry.json").read_text(encoding="utf-8"))
    bmeta = json.loads((bm / f"{a.basemap}_meta.json").read_text(encoding="utf-8"))
    styled = bm / f"{a.basemap}_styled.png"
    base = Image.open(styled if styled.exists() else bm / f"{a.basemap}_osm.png").convert("RGB")

    stops = meta.get("route_stops") or auto_stops([s for s in shots.values() if s.get("basemap", "main") == a.basemap and not s.get("optional")])
    G = Graph(polylines_from_geometry(geo))
    # 每站取第一条分镜的 subject_latlon 作站点位置
    t = parse_hhmm(meta.get("arrive", "13:00"))
    rows = []; polylines = []; total_walk = 0.0; prev_node = None; prev_pt = None; prev_snap = 0.0
    for k, st in enumerate(stops):
        ids = [i for i in st["shots"] if i in shots]
        if not ids:
            continue
        pt = tuple(shots[ids[0]]["subject_latlon"])
        node, snapd = G.snap(pt)
        walk_m, approx, line = 0.0, False, None
        if prev_node is not None:
            if node == prev_node:
                walk_m, line = meters(prev_pt, pt), [prev_pt, pt]
            else:
                line, walk_m = G.path(prev_node, node)
                if line is None:
                    walk_m = meters(prev_pt, pt) * 1.3; approx = True; line = [prev_pt, pt]
                else:
                    walk_m += prev_snap + snapd            # 从站点走到步道、再从步道走到下一站
                    line = [prev_pt] + line + [pt]
            walk_m = max(walk_m, meters(prev_pt, pt))   # 不短于直线距离
        walk_min = walk_m / a.speed / 60 if walk_m else 0
        arrive = t + walk_min
        dwell = sum(DWELL.get(shots[i].get("medium", "still"), 8) for i in ids) + STOP_EXTRA
        leave = arrive + dwell
        rows.append({"seq": k + 1, "name": st["name"], "shots": ids, "note": st.get("note", ""), "latlon": list(pt),
                     "walk_m": round(walk_m), "walk_min": round(walk_min, 1), "approx": approx,
                     "arrive": hhmm(arrive), "leave": hhmm(leave), "dwell_min": dwell})
        if line:
            polylines.append((line, approx))
        total_walk += walk_m; t = leave; prev_node, prev_pt, prev_snap = node, pt, snapd
    result = {"basemap": a.basemap, "speed_mps": a.speed, "source": meta.get("route_source", ""), "start": meta.get("arrive", ""),
              "end": rows[-1]["leave"] if rows else "", "total_walk_m": round(total_walk), "stops": rows,
              "order": [i for r in rows for i in r["shots"]]}
    (plan / "route.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    # route.md
    md = [f"# 游览路线 · {meta.get('place','')} {meta.get('date','')}", "",
          f"依据：{meta.get('route_source','（未写 route_source）')}", "",
          f"起点 {result['start']}，终点 {result['end']}，步行合计约 {result['total_walk_m']} m（{a.speed} m/s）。", "",
          "| 序 | 停留点 | 分镜 | 步行 | 到达 | 停留 | 离开 | 备注 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['seq']} | {r['name']} | {'、'.join(r['shots'])} | {r['walk_m']} m / {r['walk_min']} min{'（概略）' if r['approx'] else ''} | {r['arrive']} | {r['dwell_min']} min | {r['leave']} | {r['note']} |")
    (plan / "route.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # 路线页
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    f_title, f_h, f_s, f_t = font(44, True), font(24, True), font(18), font(15)
    d.text((40, 26), "路线", font=font(52, True), fill=GREEN)
    d.line([(158, 34), (158, 84)], fill=GREEN, width=3)
    d.text((176, 30), f"园内游览与拍摄顺序（{len(rows)} 站，步行约 {result['total_walk_m']} m）", font=f_title, fill=GREEN)
    sub = f"{meta.get('place','').split('（')[0]}　{meta.get('date','')}"
    d.text((W - 40 - d.textlength(sub, font=f_s), 52), sub, font=f_s, fill=MUTED)
    # 地图：整张风格化底图缩放到左侧面板
    mx0, my0, mx1, my1 = 40, 110, 900, H - 60
    scale_img = min((mx1 - mx0) / base.width, (my1 - my0) / base.height)
    mw, mh = int(base.width * scale_img), int(base.height * scale_img)
    ox, oy = mx0 + (mx1 - mx0 - mw) // 2, my0 + (my1 - my0 - mh) // 2
    img.paste(base.resize((mw, mh), Image.LANCZOS), (ox, oy))
    d.rectangle((ox - 1, oy - 1, ox + mw, oy + mh), outline=LINE)
    s_img = base.width / bmeta["size"]

    def P(lat, lon):
        x, y = latlon_to_px(bmeta, lat, lon, s_img)
        return ox + x * scale_img, oy + y * scale_img
    for line, approx in polylines:
        pts = [P(*p) for p in line]
        if len(pts) >= 2:
            if approx:
                for i in range(0, len(pts) - 1):
                    d.line([pts[i], pts[i + 1]], fill=ROUTE_COLOR, width=3)
            else:
                d.line(pts, fill=(255, 255, 255), width=9); d.line(pts, fill=ROUTE_COLOR, width=5)
    for r in rows:
        x, y = P(*r["latlon"])
        d.ellipse((x - 15, y - 15, x + 15, y + 15), fill=ROUTE_COLOR, outline=(255, 255, 255), width=3)
        lab = str(r["seq"]); tw = d.textlength(lab, font=font(18, True))
        d.text((x - tw / 2, y - 11), lab, font=font(18, True), fill=(255, 255, 255))
    d.rectangle((ox + 6, oy + 6, ox + 34, oy + 46), fill=(255, 255, 255))
    d.line([(ox + 20, oy + 42), (ox + 20, oy + 20)], fill=MUTED, width=2); d.text((ox + 14, oy + 26), "北", font=f_t, fill=MUTED)
    # 右侧表
    rx0, rx1 = 930, W - 40
    y = panel(d, (rx0, 110, rx1, H - 60), "停留点 · 分镜 · 时刻", f_h)
    cols = [(rx0 + 12, "序"), (rx0 + 44, "停留点"), (rx0 + 220, "分镜"), (rx0 + 430, "步行"), (rx0 + 500, "到达"), (rx0 + 560, "离开")]
    for x, hdr in cols:
        d.text((x, y), hdr, font=font(15, True), fill=GREEN)
    y += 24
    for r in rows:
        vals = [str(r["seq"]), r["name"][:11], None, f"{r['walk_m']}m{'~' if r['approx'] else ''}", r["arrive"], r["leave"]]
        for (x, _), v in zip(cols, vals):
            if v is not None:
                d.text((x, y), v, font=f_t, fill=INK)
        y2 = text_block(d, (cols[2][0], y), " ".join(r["shots"]), f_t, 200, spacing=1)
        y = max(y + 22, y2 + 2)
        if r.get("note"):
            y = text_block(d, (rx0 + 44, y), r["note"], font(13), rx1 - rx0 - 60, fill=MUTED, spacing=1) + 2
        if y > H - 150:
            d.text((rx0 + 12, y), "…（其余见 route.md）", font=f_t, fill=MUTED); break
    y = max(y + 8, H - 130)
    text_block(d, (rx0 + 12, y), "依据：" + (meta.get("route_source") or "按分镜时段自动排序") + f"\n步行 {a.speed} m/s；停留按介质估算（静态 8 / 连拍 4 / 短片 4 / 实况 1 分钟，每站加 2 分钟）；橙线为步道上的最短路，细线为概略。", font(13), rx1 - rx0 - 24, fill=MUTED, spacing=2)
    d.text((40, H - 42), "路线页由 tools/route.py 按底图步道计算；现场封闭或人流变化时按到场清单调整。", font=f_t, fill=MUTED)
    img.save(out / "route_01.png", quality=92)
    print(f"路线：{len(rows)} 站，步行 {result['total_walk_m']} m，{result['start']} → {result['end']}；→ {plan/'route.json'}, {out/'route_01.png'}")


if __name__ == "__main__":
    main()
