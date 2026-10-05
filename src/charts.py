"""장부의 시계열로 고정 그림 2개(SVG)를 그린다.

① 외국인 코스피 순매수 20거래일 막대 + 누적선
② 미국 10년 국채금리 20거래일 선 + 5.0~5.3% 띠 + 5.30 선
빈 날은 그리지 않는다 (데이터가 쌓이는 대로 채워짐).
"""
from __future__ import annotations

NAVY, BLUE, RED, WARN, MUTE, GRID = "#13294b", "#2c5fa0", "#c8372d", "#d98a1a", "#8a93a1", "#eef1f5"


def _md(date: str) -> str:
    """'2026-10-02' -> '10/2'"""
    y, m, d = date.split("-")
    return f"{int(m)}/{int(d)}"


def _fmt_jo(v: float) -> str:
    """억원 -> '−2.9조' / '−0.13조' 식"""
    jo = v / 10000
    s = f"{abs(jo):.2f}".rstrip("0").rstrip(".")
    return ("−" if v < 0 else "+") + s + "조"


def foreign_flow_svg(series: list[dict], days: int = 20) -> tuple[str, str]:
    """막대 + 누적 점선. returns (svg, caption)"""
    pts = series[-days:]
    if not pts:
        return "<svg viewBox='0 0 340 170'></svg>", "데이터 없음"
    W, H, L, R, T, B = 340, 170, 48, 330, 20, 140
    vals = [p["value"] for p in pts]
    lo = min(min(vals), 0)
    hi = max(max(vals), 0)
    span = max(hi - lo, 1)
    # 눈금: 1조 단위
    step = 10000
    while span / step > 6:
        step *= 2
    def y(v):  # 값 -> y
        return T + (hi - v) / span * (B - T)
    n = len(pts)
    slot = (R - L) / max(n, 1)
    bw = min(40, slot * 0.6)
    g = []
    # grid
    tick = (hi // step) * step
    while tick >= lo - step:
        yy = y(tick)
        if T - 1 <= yy <= B + 1:
            g.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{R}" y2="{yy:.1f}" stroke="{GRID if tick else "#cfd5de"}"/>')
            lab = "0" if tick == 0 else _fmt_jo(tick).replace("+", "")
            g.append(f'<text x="{L-4}" y="{yy+3:.1f}" font-size="9" fill="{MUTE}" text-anchor="end">{lab}</text>')
        tick -= step
    # bars + labels + cumulative
    cum, cpts = 0, []
    for i, p in enumerate(pts):
        cx = L + slot * (i + 0.5)
        v = p["value"]
        y0, y1 = y(0), y(v)
        top, h = (min(y0, y1), abs(y1 - y0))
        color = BLUE if v < 0 else RED
        g.append(f'<rect x="{cx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(h,1.5):.1f}" rx="2" fill="{color}"/>')
        if n <= 10:
            g.append(f'<text x="{cx:.1f}" y="{B+12}" font-size="9" font-weight="700" fill="{NAVY}" text-anchor="middle">{_md(p["date"])}</text>')
            g.append(f'<text x="{cx:.1f}" y="{B+24}" font-size="8.5" font-weight="700" fill="{color}" text-anchor="middle">{_fmt_jo(v)}</text>')
        elif i % 5 == 0 or i == n - 1:
            g.append(f'<text x="{cx:.1f}" y="{B+12}" font-size="8.5" fill="{NAVY}" text-anchor="middle">{_md(p["date"])}</text>')
        cum += v
        cpts.append((cx, v))
    # 추세 점선 (막대 끝 연결)
    if n >= 2:
        pl = " ".join(f"{x:.1f},{y(v):.1f}" for x, v in cpts)
        g.append(f'<polyline points="{pl}" fill="none" stroke="{RED}" stroke-width="2" stroke-dasharray="4 3"/>')
    trend = "매도 줄어드는 중" if n >= 2 and vals[-1] > vals[-2] else ("매도 커지는 중" if n >= 2 and vals[-1] < vals[-2] else "")
    if trend:
        g.append(f'<text x="{R}" y="{y(vals[-1])-8:.1f}" font-size="8.5" fill="{RED}" font-weight="700" text-anchor="end">{trend}</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block">' + "".join(g) + "</svg>"
    cap = f"{n}일 누적 {_fmt_jo(cum)}. 20일 그림은 장부에 데이터가 쌓이는 대로 채워집니다 (지금 {n}/20)."
    return svg, cap


def us10y_svg(series: list[dict], days: int = 20, band=(5.0, 5.3), line=5.30, count: str = "") -> tuple[str, str]:
    pts = series[-days:]
    if not pts:
        return "<svg viewBox='0 0 340 170'></svg>", "데이터 없음"
    W, H, L, R, T, B = 340, 170, 48, 330, 14, 134
    vals = [p["value"] for p in pts]
    lo = min(min(vals), band[0]) - 0.15
    hi = max(max(vals), band[1]) + 0.05
    def y(v):
        return T + (hi - v) / (hi - lo) * (B - T)
    g = []
    # band
    g.append(f'<rect x="{L}" y="{y(band[1]):.1f}" width="{R-L}" height="{y(band[0])-y(band[1]):.1f}" fill="#fdf3e7"/>')
    for v in (band[1], (band[0]+band[1])/2, band[0], round(lo + 0.1, 1)):
        yy = y(v)
        g.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{R}" y2="{yy:.1f}" stroke="{"#e8c9a0" if v in band else GRID}"/>')
        g.append(f'<text x="{L-4}" y="{yy+3:.1f}" font-size="9" fill="{MUTE}" text-anchor="end">{v:.2f}</text>')
    g.append(f'<line x1="{L}" y1="{y(line):.1f}" x2="{R}" y2="{y(line):.1f}" stroke="{RED}" stroke-dasharray="4 3" stroke-width="1.3"/>')
    g.append(f'<text x="{R-2}" y="{y(line)-4:.1f}" font-size="8.5" fill="{RED}" text-anchor="end" font-weight="700">{line:.2f} = B 기각선</text>')
    g.append(f'<text x="{L+4}" y="{y(band[0])-4:.1f}" font-size="8" fill="#b06f0e">{band[0]}~{band[1]} 띠 (20일이면 현금 40%) · 지금 {count}</text>')
    n = len(pts)
    slot = (R - L) / max(n, 1)
    xs = [L + slot * (i + 0.5) for i in range(n)]
    pl = " ".join(f"{x:.1f},{y(v):.1f}" for x, v in zip(xs, vals))
    g.append(f'<polyline points="{pl}" fill="none" stroke="{NAVY}" stroke-width="2.5"/>')
    for i, (x, p) in enumerate(zip(xs, pts)):
        last = i == n - 1
        g.append(f'<circle cx="{x:.1f}" cy="{y(p["value"]):.1f}" r="{4 if last else 3.5}" fill="{RED if last else NAVY}"/>')
        if n <= 10 or i % 5 == 0 or last:
            g.append(f'<text x="{x:.1f}" y="{B+16}" font-size="9" font-weight="700" fill="{NAVY}" text-anchor="middle">{_md(p["date"])}</text>')
            lab = f'{p["value"]:.2f}'.rstrip("0").rstrip(".") if p["value"] != round(p["value"], 2) else f'{p["value"]:.2f}'
            if p.get("range"):
                lab += "*"
            g.append(f'<text x="{x:.1f}" y="{B+29}" font-size="9" font-weight="700" fill="{RED if last else NAVY}" text-anchor="middle">{lab}</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block">' + "".join(g) + "</svg>"
    ranges = [p for p in pts if p.get("range")]
    cap = ("*표시는 출처별 범위(" + " · ".join(f'{_md(p["date"])} {p["range"]}' for p in ranges) + "), 중간값 표시. 미 재무부 공식치로 교체 예정. " if ranges else "")
    below = sum(1 for v in vals if v < line)
    cap += f"{line:.2f} 선 아래에 {below}일째."
    return svg, cap


def kick_svg(kick: dict) -> str:
    """오늘의 한 장 — 엇갈림 그림.
    kick.rows = [{label, text, dir(+1/-1), hi}]  : 기대와 다르게 움직인 것(hi)을 강조한 화살표 줄
    kick.lines = {labels:[...], a:{name, vals}, b:{name, vals}} : 두 흐름(시작=100으로 맞춤)이 갈라지는 그림
    """
    if not kick:
        return ""
    if kick.get("lines"):
        L_ = kick["lines"]
        a, b, labs = L_["a"], L_["b"], L_.get("labels", [])
        def norm(v):
            v = [x for x in v]
            return [x / v[0] * 100 if v and v[0] else x for x in v]
        va, vb = norm(a["vals"]), norm(b["vals"])
        allv = va + vb
        lo, hi = min(allv), max(allv)
        span = (hi - lo) or 1
        W, H, Lp, Rp, T, B = 340, 120, 34, 330, 14, 100
        n = max(len(va), len(vb))
        x = lambda i: Lp + (Rp - Lp) * i / max(1, n - 1)
        y = lambda v: T + (hi - v) / span * (B - T)
        def path(vs):
            return " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs))
        g = [f'<line x1="{Lp}" y1="{y(100):.1f}" x2="{Rp}" y2="{y(100):.1f}" stroke="#cfd5de" stroke-dasharray="3 3"/>' if lo <= 100 <= hi else ""]
        g.append(f'<polyline points="{path(va)}" fill="none" stroke="{NAVY}" stroke-width="2.2"/>')
        g.append(f'<polyline points="{path(vb)}" fill="none" stroke="{RED}" stroke-width="2.2"/>')
        g.append(f'<text x="{Lp}" y="{H - 4}" font-size="8.5" fill="{MUTE}">{labs[0] if labs else ""}</text><text x="{Rp}" y="{H - 4}" font-size="8.5" fill="{MUTE}" text-anchor="end">{labs[-1] if labs else ""}</text>')
        g.append(f'<rect x="{Lp}" y="2" width="9" height="3" fill="{NAVY}"/><text x="{Lp + 12}" y="8" font-size="8.5" fill="{NAVY}">{a["name"]}</text>')
        g.append(f'<rect x="{Lp + 150}" y="2" width="9" height="3" fill="{RED}"/><text x="{Lp + 162}" y="8" font-size="8.5" fill="{RED}">{b["name"]}</text>')
        return f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto">{"".join(g)}</svg>'
    rows = kick.get("rows") or []
    if not rows:
        return ""
    W, rh = 340, 26
    H = rh * len(rows) + 4
    g = []
    for i, r in enumerate(rows):
        yy = 2 + i * rh
        up = (r.get("dir") or 0) > 0
        col = RED if up else BLUE
        hi = r.get("hi")
        if hi:
            g.append(f'<rect x="0" y="{yy}" width="{W}" height="{rh - 3}" rx="6" fill="#fff4e0" stroke="{WARN}"/>')
        g.append(f'<text x="10" y="{yy + 16}" font-size="10" font-weight="{800 if hi else 600}" fill="{NAVY}">{r["label"]}</text>')
        g.append(f'<text x="200" y="{yy + 17}" font-size="13" font-weight="900" fill="{col}" text-anchor="middle">{"▲" if up else "▼"}</text>')
        g.append(f'<text x="{W - 10}" y="{yy + 16}" font-size="10.5" font-weight="800" fill="{col}" text-anchor="end">{r["text"]}</text>')
        if hi:
            g.append(f'<text x="235" y="{yy + 16}" font-size="8.5" font-weight="800" fill="{WARN}">← 엇갈림</text>')
    return f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto">{"".join(g)}</svg>'
