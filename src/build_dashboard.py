"""휴대폰용 대시보드 한 장: docs/index.html (GitHub Pages) + docs/artifact.html (Claude 아티팩트용 본문).

재료: 가장 최근 data/*.json · ledger/ledger.json · market/latest.json(있으면) · reports/ 목록.
사용: python -m src.build_dashboard
"""
from __future__ import annotations
import csv, json, html
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import ledger as L
from .charts import foreign_flow_svg, us10y_svg
from .scoring import calibration_stats, leaderboard

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "chkchp0702-spec/market-strategy-report"
KST = timezone(timedelta(hours=9))
E = html.escape

CSS = """
<style>
/* 레이아웃: 한 열, 위에서 아래로 '오늘 → 그림 → 포트폴리오 → 사람들 → 기록'. 숫자는 표 정렬. */
:root{--bg:#f6f4ef;--card:#fffdf8;--fg:#1c2230;--mute:#6b7280;--line:#e3ded3;--navy:#13294b;--navy2:#2c5fa0;
 --up:#c8372d;--dn:#2457b5;--ok:#1f7a4d;--warn:#d98a1a;--cream:#fbf3df;--chip:#eef2f8;
 --f-body:"Noto Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;--f-num:"IBM Plex Sans","Noto Sans KR",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#12161f;--card:#1a2030;--fg:#e8eaf0;--mute:#9aa3b5;--line:#2a3345;--navy:#dfe6f5;--navy2:#8db0e8;--up:#ff6b5e;--dn:#6fa4ff;--ok:#4fc08a;--warn:#f0b052;--cream:#2a2614;--chip:#232b3c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12161f;--card:#1a2030;--fg:#e8eaf0;--mute:#9aa3b5;--line:#2a3345;--navy:#dfe6f5;--navy2:#8db0e8;--up:#ff6b5e;--dn:#6fa4ff;--ok:#4fc08a;--warn:#f0b052;--cream:#2a2614;--chip:#232b3c;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--f-body);font-size:15px;line-height:1.5}
.wrap{max-width:720px;margin:0 auto;padding-block:14px 48px;padding-inline:16px}
h1{font-size:22px;margin:0;color:var(--navy);letter-spacing:-.01em}.sub{color:var(--mute);font-size:13px;margin-top:2px}
h2{font-size:15px;margin:22px 0 8px;color:var(--navy);text-transform:uppercase;letter-spacing:.04em;font-weight:800}
.grades{display:flex;flex-direction:column;gap:6px;margin-top:12px}
.g{border-radius:8px;padding:8px 10px;font-size:13.5px;background:var(--chip);border-left:5px solid var(--mute)}
.g.ok{border-left-color:var(--ok)}.g.no{border-left-color:var(--up)}.g.hold{border-left-color:var(--warn)}
.one{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-top:12px;font-size:16px;font-weight:600;line-height:1.45}
.one em{font-style:normal;color:var(--up)}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}@media(min-width:520px){.kpis{grid-template-columns:repeat(3,1fr)}}
.k{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 11px;min-width:0}
.k .l{font-size:12px;color:var(--mute)}.k .v{font-family:var(--f-num);font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.2}
.k .c{font-size:12.5px;font-variant-numeric:tabular-nums}.k .s{font-size:12px;color:var(--fg);opacity:.85;margin-top:4px;border-top:1px dashed var(--line);padding-top:4px}
.up{color:var(--up)}.dn{color:var(--dn)}.wn{color:var(--warn)}
.chart{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 10px 6px;margin-bottom:8px}
.chart svg{width:100%;height:auto;display:block}.chart .cap{font-size:12px;color:var(--mute);margin-top:4px}
.badge{display:inline-block;background:var(--navy);color:#fff;border-radius:6px;padding:3px 9px;font-weight:800;font-size:13px;margin-right:6px}
.bar{display:flex;height:22px;border-radius:6px;overflow:hidden;margin:8px 0 4px}.bar div{color:#fff;font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center;white-space:nowrap;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}th,td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:11.5px;color:var(--mute);font-weight:700;text-transform:uppercase;letter-spacing:.03em}td.n,th.n{text-align:right;white-space:nowrap}
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 8px}
.pill{display:inline-block;border-radius:999px;padding:1px 8px;font-size:11.5px;font-weight:700;background:var(--chip)}
.pill.on{background:var(--up);color:#fff}.pill.half{background:var(--warn);color:#fff}.pill.off{color:var(--mute)}
ul.s{margin:0;padding-left:18px}ul.s li{margin-bottom:4px;font-size:13.5px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin-top:8px}summary{cursor:pointer;font-weight:700;font-size:14px}
.links a{display:block;padding:7px 0;border-bottom:1px solid var(--line);color:var(--navy2);text-decoration:none;font-size:14px}
.foot{margin-top:28px;font-size:11.5px;color:var(--mute);line-height:1.5;border-top:1px solid var(--line);padding-top:8px}
.live{font-size:12px;color:var(--mute)}
a:focus-visible,summary:focus-visible{outline:2px solid var(--navy2);outline-offset:2px}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
"""

COLORS = ['#13294b', '#2c5fa0', '#1f7a4d', '#5b3f93', '#c8372d', '#d98a1a', '#6f93c9', '#9aa6b4']


def latest_data() -> dict:
    files = sorted(p for p in (ROOT / "data").glob("20*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8"))


def market_rows() -> tuple[list[dict], str]:
    p = ROOT / "market" / "latest.json"
    if not p.exists():
        return [], ""
    m = json.loads(p.read_text(encoding="utf-8"))
    order = ["sp500", "nasdaq", "us10y_tsy", "us10y", "us30y_tsy", "usdkrw", "wti", "brent", "gold", "kospi", "kosdaq", "foreign_kospi", "samsung", "hynix", "micron", "vix"]
    rows = []
    for k in order:
        it = m["items"].get(k)
        if not it:
            continue
        rows.append(it)
    return rows, m.get("fetched_kst", "")


def fmt(v, nd=2):
    if v is None:
        return "—"
    return f"{v:,.{nd}f}" if isinstance(v, float) else f"{v:,}"


def report_links() -> list[tuple[str, str]]:
    out = []
    for d in sorted((ROOT / "reports").glob("20*"), reverse=True)[:14]:
        for pdf in sorted(d.glob("*.pdf")):
            kind = "요약" if "Summary" in pdf.name else "전체본"
            out.append((f"{d.name} · {kind}", f"https://github.com/{REPO}/blob/main/reports/{d.name}/{pdf.name}"))
    return out


def body(d: dict, led: dict) -> str:
    fsvg, fcap = foreign_flow_svg(led["series"]["foreign_kospi"])
    band = next(c for c in led["conditions"] if c["id"] == "us10y_band20")
    usvg, ucap = us10y_svg(led["series"]["us10y"], count=f'{band["count"]}/{band["of"]}')
    cal = calibration_stats(led)
    board = leaderboard(led, 8)
    sc = L.totals_line(L.scorecard_totals(led["scorecard"]))
    mrows, fetched = market_rows()
    s = d.get("summary", {})
    h = []
    h.append(f'<div class="wrap"><h1>시황 대시보드</h1><div class="sub"><b>{E(d["date"].replace("-", "."))} ({E(d["weekday"])}) {E(d["edition_label"])}</b> · {E(d["basis"])}</div>')
    h.append('<div class="grades">' + "".join(f'<div class="g {E(g["cls"])}"><b>{E(g["title"].replace("어제 예고 ", ""))}</b> {E(g["mark"])} · {E(g["text"].split(".")[0])}</div>' for g in d["yesterday_grades"]) + "</div>")
    h.append(f'<div class="one">{d["one_liner"]}</div>')
    k = d.get("kick") or {}
    if k:
        h.append(f'<div class="one" style="border-color:#d98a1a;background:#fff8ec;font-size:14.5px"><b style="color:#b06a00">⚡ 킥</b> ' + (f'오늘은 킥 없음 — {k.get("why", "")}' if k.get("none") else f'{k.get("title", "")} <span style="color:#5a6472;font-weight:500">→ {k.get("so", "")}</span>') + '</div>')
    h.append('<h2>숫자</h2><div class="kpis">')
    for i in s.get("kpis_pick", range(6)):
        k = d["kpis"][i]
        h.append(f'<div class="k"><div class="l">{E(k["label"])}</div><div class="v {E(k.get("cls",""))}">{E(k["value"])}</div><div class="c {E(k.get("change_cls") or "")}">{E(k["change"])}</div><div class="s">{E(k["so"])}</div></div>')
    h.append("</div>")
    if mrows:
        h.append(f'<h2>지금 시세 <span class="live">자동 수집 {E(fetched)} KST</span></h2><div class="tw"><table><tr><th>항목</th><th class="n">값</th><th class="n">전일비</th><th>기준</th></tr>')
        for it in mrows:
            ch = it.get("change_pct"); cls = "up" if (ch or 0) > 0 else "dn" if (ch or 0) < 0 else ""
            nd = 3 if "10y" in it.get("src", "") + it.get("name", "") or "금리" in it.get("name", "") else 2
            chs = f'{ch:+.2f}%' if ch is not None else (f'{it["value"]:+,}억' if "foreign" in it.get("name", "") else "—")
            h.append(f'<tr><td>{E(it["name"])}</td><td class="n">{fmt(it["value"], 0 if it.get("unit")=="억원" or it["value"]>10000 else nd)}</td><td class="n {cls}">{E(chs)}</td><td class="live">{E(it.get("asof_kst") or it.get("date",""))}</td></tr>')
        h.append("</table></div>")
    h.append(f'<h2>그림 둘</h2><div class="chart">{fsvg}<div class="cap">{E(fcap)}</div></div><div class="chart">{usvg}<div class="cap">{E(ucap)}</div></div>')
    h.append('<h2>내 포트폴리오</h2><div>' + "".join(f'<span class="badge">{E(b)}</span>' for b in d["decision"]["badges"]) + f' <span style="font-size:13.5px">{s.get("decision_line","")}</span></div>')
    h.append('<div class="bar">' + "".join(f'<div style="width:{a["pct"]}%;background:{COLORS[i]}" title="{E(a["name"])}">{E(a["name"].split(" ")[0].split("·")[0]) + " " + str(a["pct"]) if a["pct"]>=10 else (str(a["pct"]) if a["pct"]>=5 else "")}</div>' for i, a in enumerate(led["allocation"])) + "</div>")
    h.append('<div class="live">' + " · ".join(f'{E(a["name"])} {a["pct"]}' for a in led["allocation"]) + "</div>")
    h.append('<div style="margin-top:8px;font-size:13.5px"><b>경우의 수:</b> ' + " · ".join(f'{E(sc_["label"])} <b>{sc_["pct"]}%</b>' for sc_ in led["scenarios"]) + "</div>")
    h.append(f'<div style="font-size:13px;margin-top:6px"><b>담는 것:</b> {E(s.get("instruments_line",""))}</div>')
    h.append('<h2>비중 바꾸는 조건</h2><div class="tw"><table><tr><th>조건</th><th>상태</th><th>그러면</th></tr>')
    for c in led["conditions"]:
        st = c.get("state", ""); cls = "on" if "발동" in st and "미발동" not in st else "half" if ("진행" in st or "절반" in st or "시험" in st) else "off"
        cnt = f' {c["count"]}/{c["of"]}' if c.get("of") else ""
        h.append(f'<tr><td>{E(c["cond"])}<div class="live">{E(c.get("now",""))}</div></td><td><span class="pill {cls}">{E(st)}{cnt}</span></td><td>{E(c["then"])}</td></tr>')
    h.append("</table></div>")
    h.append(f'<h2>전략가 적중률</h2><div class="tw"><table><tr><th>#</th><th>이름</th><th class="n">맞:틀</th><th class="n">적중</th></tr>')
    h += [f'<tr><td>{b["n"]}</td><td>{E(b["name"])}<div class="live">{E(b["group"])}</div></td><td class="n">{b["win"]}:{b["loss"]}</td><td class="n"><b>{b["rate"]}%</b></td></tr>' for b in board] or ['<tr><td colspan="4">아직 판정 없음</td></tr>']
    h.append("</table></div>")
    h.append('<details><summary>패널 31명 전체 — 세 질문 입장</summary><div style="overflow-x:auto"><table><tr><th>#</th><th>이름</th><th>① 금리 꼭대기</th><th>② AI 이익</th><th>③ 한국</th><th class="n">맞:틀</th></tr>')
    for p in led["panel"]:
        la = p.get("last", {})
        h.append(f'<tr><td>{p["n"]}</td><td>{E(p["name"])}<div class="live">{E(la.get("date",""))}</div></td><td>{E(la.get("q1","") or "—")}</td><td>{E(la.get("q2","") or "—")}</td><td>{E(la.get("q3","") or "—")}</td><td class="n">{p["win"]}:{p["loss"]}</td></tr>')
    h.append("</table></div></details>")
    h.append(f'<h2>내 성적표</h2><div style="font-size:14px"><b>누적 (10/2~):</b> {E(sc)}</div><div style="font-size:13px;margin-top:4px">{E(cal["line"])}</div>')
    recent = led["scorecard"][-6:][::-1]
    h.append('<details><summary>최근 판정</summary><ul class="s">' + "".join(f'<li>[{E(r["date"][5:])}] {E(r["wrote"])} → {E(r["result"])} <b>{E(r["verdict"])}</b></li>' for r in recent) + "</ul></details>")
    fc = led.get("forecasts", {})
    ps = fc.get("p") or []
    h.append(f'<h2>다음에 볼 것 <span class="live">{E(fc.get("from",""))}에서 예고</span></h2><ul class="s">' + "".join(f'<li>{E(t)}' + (f' <span class="pill">{int(ps[i]*100)}%</span>' if i < len(ps) else "") + "</li>" for i, t in enumerate(fc.get("items", []))) + "</ul>")
    h.append('<h2>리포트 PDF</h2><div class="links">' + "".join(f'<a href="{u}">{E(t)}</a>' for t, u in report_links()) + "</div>")
    h.append(f'<div class="foot">출처: {E(d.get("sources",""))}<br>정보 제공 목적이며 투자자문이 아님 · 비중·확률·조건·채점은 작성자 판단 · 종목·ETF는 예시이며 매수 추천 아님 · 원금 손실 가능 · 투자 판단의 책임은 본인에게 있음<br>갱신 {datetime.now(KST).strftime("%Y-%m-%d %H:%M")} KST · 자동 생성 (src/build_dashboard.py)</div></div>')
    return "\n".join(h)


def main():
    d = latest_data()
    led = L.load()
    DOCS.mkdir(exist_ok=True)
    fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;800&family=IBM+Plex+Sans:wght@600;700&display=swap">'
    frag = f"<title>시황 대시보드</title>\n{fonts}\n{CSS}\n{body(d, led)}"
    (DOCS / "artifact.html").write_text(frag, encoding="utf-8")
    full = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'{frag}</head><body></body></html>')
    # 본문은 head 뒤에 와야 하므로 다시 조립
    full = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>시황 대시보드</title>{fonts}{CSS}</head><body>{body(d, led)}</body></html>')
    (DOCS / "index.html").write_text(full, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"완료 → {DOCS/'index.html'} ({d['date']} {d['edition']})")


if __name__ == "__main__":
    main()
