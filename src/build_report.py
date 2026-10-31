"""시황리포트 빌더.

사용법:
  python -m src.build_report data/2026-10-03.json            # PDF 2개 + 카톡 텍스트 생성
  python -m src.build_report data/2026-10-03.json --commit   # + 장부(ledger.json)에 그날 줄 반영

출력:
  reports/<date>_<edition>/Market_Strategy_Report_<date>_<ed>.pdf   (전체본 6쪽 — 10/15 전략가 패널 쪽 뺌, 기록은 장부에)
  reports/<date>_<edition>/Market_Strategy_Summary_<date>_<ed>.pdf  (요약본 1쪽)
  reports/<date>_<edition>/kakao.txt                               (카톡 붙여넣기용)
  reports/<date>_<edition>/*.html                                   (원본)

규칙 (RULES.md):
  - 누적·카운트·그림은 장부에서만 온다.
  - 전체본은 정확히 6쪽, 요약본은 정확히 1쪽. 어떤 쪽도 푸터를 넘으면 빌드 실패.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import ledger as L
from .charts import foreign_flow_svg, us10y_svg, kick_svg, sectors_svg
from .render import html_to_pdf, check_overflow
from .kakao_text import kakao_text
from .scoring import calibration_stats, rerank_panel, leaderboard

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "templates"
OUT = ROOT / "reports"
MARGIN_PX = 40  # 푸터 위 최소 여유


def build(day_path: Path, commit: bool = False, strict: bool = True, rerank: bool = False) -> Path:
    d = json.loads(day_path.read_text(encoding="utf-8"))
    led = L.load()
    if rerank and d["date"] not in led.get("_applied", []):
        moves = rerank_panel(led, d["date"])
        print(f"패널 재정렬: {len(moves)}명 이동 " + " · ".join(f'{m["name"]} {m["from"]}→{m["to"]}' for m in moves[:8]))
        if commit:
            L.save(led)
    cal = calibration_stats(led)
    board = leaderboard(led)

    # ---- 장부에서 파생되는 것들 ----
    foreign_svg, foreign_cap = foreign_flow_svg(led["series"]["foreign_kospi"])
    band = next(c for c in led["conditions"] if c["id"] == "us10y_band20")
    us_svg, us_cap = us10y_svg(led["series"]["us10y"], count=f'{band["count"]}/{band["of"]}')
    charts = {
        "foreign_svg": foreign_svg, "foreign_cap": foreign_cap, "foreign_n": min(len(led["series"]["foreign_kospi"]), 20),
        "us10y_svg": us_svg, "us10y_cap": us_cap, "us10y_n": min(len(led["series"]["us10y"]), 20),
        "kick_svg": kick_svg(d.get("kick") or {}),
    }
    # 🔥 섹터·테마 레이더 (src/sectors.py 가 아침마다 market/sectors.json 을 만든다)
    try:
        sec = json.loads((ROOT / "market" / "sectors.json").read_text(encoding="utf-8"))
    except Exception:
        sec = {}
    charts["sectors_svg"] = sectors_svg(sec)
    # 🎯 오늘의 집중 (src/focus.py → market/focus.json)
    try:
        focus = json.loads((ROOT / "market" / "focus.json").read_text(encoding="utf-8"))
    except Exception:
        focus = {}
    panel_rows = L.panel_view(led, d.get("panel_today", []))
    panel_groups = L.group_rows(panel_rows)
    omap = {o["name"]: o for o in d.get("outside_today", [])}
    outside_rows = [{**o, **omap.get(o["name"], {})} for o in led["outside_panel"]]
    # 성적표 누적 = 장부 + 오늘(아직 commit 전이면 더해서 보여줌)
    sc_rows = list(led["scorecard"])
    if d["date"] not in led.get("_applied", []):
        sc_rows += [{"date": d["date"], **r} for r in d.get("scorecard_today", [])]
    scorecard_total = L.totals_line(L.scorecard_totals(sc_rows))
    seen = d.get("allocation_seen") or []
    # 10/11: 배분표 칸이 바뀐 날 옛 data 를 다시 그리면 「어제 본 것」이 엉뚱한 칸에 붙음 → 칸 수가 다르면 비움
    base_rows = [{**a, **s} for a, s in zip(led["allocation"], seen)] if len(seen) == len(led["allocation"]) else [dict(a) for a in led["allocation"]]
    sv = led.get("sector_views") or {}
    views_line = ""
    # ⚡ 킥 포함 = 실제 포트 (10/28 사용자 「여전히 그대로잖아 · 킥포트를 넣으라니까」)
    #   배분표 자체를 「실제로 들고 있는 것」으로: 💼 기본 칸은 ⚡ 킥 몫만큼 같은 비율로 줄이고(빈 자리 돈은 기본 칸 그대로 굴림 — kick.json park),
    #   🧭 섹터 칸은 sector_views 비율대로 칸별 실제 %를, ⚡ 킥은 한 줄로(보유 종목·수익률) 넣는다.
    kick_alloc = None
    short = lambda x: re.sub(r",? (Inc\.?|Corp\.?|Corporation|Company|Ltd\.?|plc|CORP)\b.*$|( Common Stock| Ordinary Shares).*$", "", str(x or ""), flags=re.I)
    try:
        K = json.loads((ROOT / "market" / "kick.json").read_text(encoding="utf-8"))
        H = K.get("hold") or []
        kw = round(sum(h.get("w") or 0 for h in H), 1)
        kick_alloc = {"kw": kw, "stat": K.get("stat", {}),
                      "open": [{"name": (h.get("tags") or "") + short(h.get("name")), "w": round(h.get("w") or 0, 1), "r": h.get("r")}
                               for h in sorted(H, key=lambda h: -(h.get("w") or 0))]}
    except Exception:
        kw = 0.0
    k = (100 - kw) / 100
    views = [v for v in (sv.get("views") or []) if float(v.get("pct") or 0) > 0]
    alloc_rows = []
    for a in base_rows:
        r = dict(a)
        r["base"] = a["pct"]
        r["pct"] = round(float(a["pct"]) * k, 1)
        if a.get("sleeve"):
            tot = sum(float(v["pct"]) for v in views) or 1
            r["name"] = "🧭 섹터 칸"
            r["instruments"] = " · ".join(f'{v["name"]} {float(a["pct"]) * k * float(v["pct"]) / tot:.1f}%' for v in views)
            r.setdefault("seen", "리포트 섹터 판단 비율(sector_views)대로 실제 돈")
            r.setdefault("verdict", "판단대로"); r.setdefault("verdict_cls", "gd")
            r.setdefault("rule", "비율은 매일 리포트가 고침 · 12/23 코어와 비교 판정")
        alloc_rows.append(r)
    if kick_alloc and kw > 0:
        st = kick_alloc["stat"]
        alloc_rows.insert(0, {"pct": kw, "base": 0, "name": "⚡ 공격 몫 (신호 종목)", "kick": True,
                              "instruments": " · ".join(f'{o["name"]} {o["w"]}%({"%+.1f" % o["r"] if o.get("r") is not None else "–"}%)' for o in kick_alloc["open"][:12])
                                             + (f' 외 {len(kick_alloc["open"]) - 12}개' if len(kick_alloc["open"]) > 12 else ""),
                              "seen": f'누적 ⚡ 공격 포트 {st.get("kick", 0):+.2f}% · 💼 기본 {st.get("base", 0):+.2f}% · S&P {st.get("spy", 0):+.2f}%',
                              "verdict": "신호대로", "verdict_cls": "gd",
                              "rule": "🐋 분기 보유 · −30% 정리 / 🧭 50일 저가 이탈 · ☕📈 손절·익절·보유기간"})

    css = (TPL / "base.css").read_text(encoding="utf-8")
    env = Environment(loader=FileSystemLoader(str(TPL)), autoescape=select_autoescape(default=False))
    ctx = dict(d=d, led=led, css=css, charts=charts, panel_rows=panel_rows, panel_groups=panel_groups,
               outside_rows=outside_rows, scorecard_total=scorecard_total, alloc_rows=alloc_rows, kick_alloc=kick_alloc, views_line=views_line,
               panel_n=len(panel_rows), cal=cal, board=board, sec=sec, focus=focus)

    tag = f'{d["date"]}_{d["edition"]}'
    out = OUT / tag
    out.mkdir(parents=True, exist_ok=True)
    stem_r = f'Market_Strategy_Report_{d["date"].replace("-", "_")}_{d["edition"]}'
    stem_s = f'Market_Strategy_Summary_{d["date"].replace("-", "_")}_{d["edition"]}'

    html_r = env.get_template("report.html.j2").render(**ctx)
    html_s = env.get_template("summary.html.j2").render(**ctx)
    (out / f"{stem_r}.html").write_text(html_r, encoding="utf-8")
    (out / f"{stem_s}.html").write_text(html_s, encoding="utf-8")

    ok = True
    for stem, pages in ((stem_r, 6), (stem_s, 1)):   # 10/15: 전략가 패널 쪽 뺌 → 6쪽
        pdf = out / f"{stem}.pdf"
        res = html_to_pdf(out / f"{stem}.html", pdf)
        bad = check_overflow(res, pages, MARGIN_PX)
        print(f"[{stem}] pages={len(res)} " + " ".join(f"p{i}:{m - b:+d}px" for i, b, m in res))
        if bad:
            ok = False
            for i, b, m in bad:
                print(f"  !! page {i}: content bottom {b} vs footer {m} (여유 {m-b}px < {MARGIN_PX})", file=sys.stderr)

    (out / "kakao.txt").write_text(kakao_text(d), encoding="utf-8")

    if not ok and strict:
        print("빌드 실패: 넘침. data 파일의 글을 줄이거나 템플릿을 조정하세요.", file=sys.stderr)
        sys.exit(2)

    if commit:
        L.save(L.commit(led, d))
        print(f"장부 갱신: ledger/ledger.json ({d['date']})")
    print(f"완료 → {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("day", help="data/YYYY-MM-DD.json")
    ap.add_argument("--commit", action="store_true", help="장부에 그날 줄 반영")
    ap.add_argument("--no-strict", action="store_true", help="넘침이 있어도 PDF를 남긴다")
    ap.add_argument("--rerank", action="store_true", help="패널을 적중률 순으로 재정렬 (매월 첫 리포트)")
    a = ap.parse_args()
    build(Path(a.day), commit=a.commit, strict=not a.no_strict, rerank=a.rerank)


if __name__ == "__main__":
    main()
