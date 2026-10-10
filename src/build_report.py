"""시황리포트 빌더.

사용법:
  python -m src.build_report data/2026-10-03.json            # PDF 2개 + 카톡 텍스트 생성
  python -m src.build_report data/2026-10-03.json --commit   # + 장부(ledger.json)에 그날 줄 반영

출력:
  reports/<date>_<edition>/Market_Strategy_Report_<date>_<ed>.pdf   (전체본 7쪽 — 2쪽 = 🔥 섹터·테마 레이더)
  reports/<date>_<edition>/Market_Strategy_Summary_<date>_<ed>.pdf  (요약본 1쪽)
  reports/<date>_<edition>/kakao.txt                               (카톡 붙여넣기용)
  reports/<date>_<edition>/*.html                                   (원본)

규칙 (RULES.md):
  - 누적·카운트·그림은 장부에서만 온다.
  - 전체본은 정확히 7쪽, 요약본은 정확히 1쪽. 어떤 쪽도 푸터를 넘으면 빌드 실패.
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
    alloc_rows = [{**a, **s} for a, s in zip(led["allocation"], d["allocation_seen"])]
    # ⚡ 킥 포함 자산 배분 (10/10 사용자: "시황에 킥 자산배분 넣고") — market/kick.json
    kick_alloc = None
    try:
        K = json.loads((ROOT / "market" / "kick.json").read_text(encoding="utf-8"))
        kw = round(sum(o.get("w") or 0 for o in K.get("open", [])), 1)
        cash = next((a["pct"] for a in led["allocation"] if "현금" in a["name"]), None)
        short = lambda x: re.sub(r",? (Inc\.?|Corp\.?|Corporation|Company|Ltd\.?|plc|CORP)\b.*$|( Common Stock| Ordinary Shares).*$", "", str(x or ""), flags=re.I)
        kick_alloc = {"kw": kw, "cash": cash, "cash_k": round(cash - kw, 1) if cash is not None else None, "stat": K.get("stat", {}),
                      "open": [{"name": short(o.get("name")), "code": o.get("code"), "w": round(o.get("w") or 0, 1), "r": o.get("r"),
                                "src": re.sub(r"\(.*\)", "", str(o.get("src") or "")).strip()} for o in K.get("open", [])]}
        H = K.get("hold") or []
        if H:
            kw = round(sum(h.get("w") or 0 for h in H), 1)
            kick_alloc.update({"kw": kw, "cash_k": round(cash - kw, 1) if cash is not None else None,
                               "open": [{"name": (h.get("tags") or "") + short(h.get("name")), "w": round(h.get("w") or 0, 1), "r": h.get("r")} for h in H]})
    except Exception:
        pass

    css = (TPL / "base.css").read_text(encoding="utf-8")
    env = Environment(loader=FileSystemLoader(str(TPL)), autoescape=select_autoescape(default=False))
    ctx = dict(d=d, led=led, css=css, charts=charts, panel_rows=panel_rows, panel_groups=panel_groups,
               outside_rows=outside_rows, scorecard_total=scorecard_total, alloc_rows=alloc_rows, kick_alloc=kick_alloc,
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
    for stem, pages in ((stem_r, 7), (stem_s, 1)):
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
