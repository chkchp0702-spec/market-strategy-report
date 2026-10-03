"""7. 주간판 통계 · 10. 월간 회고 골격.

주간판 (일요일, edition WK):
  python -m src.review weekly [--date 2026-10-05]
  → 장부에서 지난 7일 집계를 뽑아 reviews/weekly_YYYY-MM-DD.json 과 .md 로 저장.
    일요일 리포트는 이 집계를 2쪽 「무슨 일이 있었나」와 4쪽 성적표에 쓴다 (새 뉴스가 적은 날의 본문).

월간 회고 (매월 1일):
  python -m src.review monthly [--month 2026-10]
  → reviews/YYYY-MM.md 골격: 틀린 예고 전부 · 성적표 틀림 · 패널 순위 변화 · 확률 채점 · 조건 발동 이력.
    "왜 틀렸나" 칸은 비워 두고 리포트 작성자가 채운다. 규칙을 고쳤으면 RULES.md 이력에도 적는다.
"""
from __future__ import annotations
import argparse, json
from datetime import date, timedelta
from pathlib import Path

from . import ledger as L
from .scoring import calibration_stats, leaderboard

ROOT = Path(__file__).resolve().parent.parent
REV = ROOT / "reviews"


def _iso(d: str, ref: date) -> str:
    """장부 발언 날짜는 '10/2' 같은 짧은 꼴도 있다. 올해 기준 ISO 로 바꾼다. 못 바꾸면 ''."""
    import re
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or ""):
        return d
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", d or "")
    if m:
        y = ref.year if int(m.group(1)) <= ref.month else ref.year - 1
        return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def _between(rows, key, start, end):
    return [r for r in rows if start <= r.get(key, "") <= end]


def weekly(led: dict, end: date) -> dict:
    start = end - timedelta(days=6)
    s, e = start.isoformat(), end.isoformat()
    sc = _between(led["scorecard"], "date", s, e)
    totals = L.scorecard_totals(sc)
    cal_rows = [c for c in led.get("calibration", []) if s <= c.get("graded", "") <= e and c.get("outcome") is not None]
    hist = [h for h in led.get("scenario_history", []) if h["date"] <= e]
    first = next((h for h in hist if h["date"] >= s), hist[0] if hist else None)
    last = hist[-1] if hist else None
    scen_delta = ({k: last[k] - first.get(k, 0) for k in ("A", "B2", "C", "B") if k in last} if first and last else {})
    panel_new = [p for p in led["panel"] if s <= _iso(p.get("last", {}).get("date", ""), end) <= e]
    series = {k: [x for x in v if s <= x["date"] <= e] for k, v in led["series"].items()}
    conds = [{"id": c["id"], "cond": c["cond"], "state": c.get("state"), "count": c.get("count"), "of": c.get("of")} for c in led["conditions"]]
    out = {
        "week": f"{s} ~ {e}", "days_applied": [d for d in led.get("_applied", []) if s <= d <= e],
        "scorecard": {"rows": sc, "totals": totals, "line": L.totals_line(totals)},
        "calibration_week": {"n": len(cal_rows), "brier": (round(sum((c["p"] - c["outcome"]) ** 2 for c in cal_rows) / len(cal_rows), 3) if cal_rows else None)},
        "calibration_total": calibration_stats(led),
        "scenarios": {"start": first, "end": last, "delta": scen_delta},
        "panel_new_quotes": [{"n": p["n"], "name": p["name"], "date": p["last"]["date"], "q1": p["last"].get("q1", ""), "q2": p["last"].get("q2", ""), "q3": p["last"].get("q3", "")} for p in panel_new],
        "leaderboard": leaderboard(led, 10),
        "series": series, "conditions": conds,
        "foreign_week_sum": sum(x["value"] for x in series.get("foreign_kospi", [])) if series.get("foreign_kospi") else None,
        "us10y_week": ([series["us10y"][0]["value"], series["us10y"][-1]["value"]] if series.get("us10y") else None),
    }
    return out


def weekly_md(w: dict) -> str:
    L_ = [f"# 주간 집계 {w['week']}", "", f"- 리포트 낸 날: {', '.join(w['days_applied']) or '없음'}",
          f"- 내 성적표(이번 주): {w['scorecard']['line']}",
          f"- 확률 채점(이번 주): {w['calibration_week']['n']}건 · 브라이어 {w['calibration_week']['brier']}",
          f"- 확률 채점(누적): {w['calibration_total']['line']}",
          f"- 경우의 수 변화: {w['scenarios']['delta']}",
          f"- 외국인 주간 합계: {w['foreign_week_sum']} 억 · 미 10년: {w['us10y_week']}", "", "## 이번 주 새 발언"]
    L_ += [f"- {p['n']} {p['name']} ({p['date']}): ① {p['q1']} ② {p['q2']} ③ {p['q3']}" for p in w["panel_new_quotes"]] or ["- 없음"]
    L_ += ["", "## 적중률 순위 (판정 있는 사람)"] + [f"- {b['rate']}% ({b['win']}:{b['loss']}) {b['name']}" for b in w["leaderboard"]]
    L_ += ["", "## 조건 상태"] + [f"- {c['cond']}: {c['state']}" + (f" {c['count']}/{c['of']}" if c.get("of") else "") for c in w["conditions"]]
    return "\n".join(L_) + "\n"


def monthly(led: dict, month: str) -> str:
    s, e = f"{month}-01", f"{month}-31"
    wrong = [r for r in _between(led["scorecard"], "date", s, e) if r["verdict"] == "틀림"]
    half = [r for r in _between(led["scorecard"], "date", s, e) if r["verdict"] == "반반"]
    cal = [c for c in led.get("calibration", []) if s <= c.get("graded", "") <= e]
    miss = [c for c in cal if c.get("outcome") == 0]
    totals = L.scorecard_totals(_between(led["scorecard"], "date", s, e))
    ranks = [h for h in led.get("panel_rank_history", []) if s <= h["date"] <= e]
    hist = [h for h in led.get("scenario_history", []) if s <= h["date"] <= e]
    out = [f"# 월간 회고 {month}", "", "> 틀린 것만 모았다. 「왜 틀렸나」와 「규칙을 어떻게 고쳤나」는 사람이 채운다. 고친 규칙은 RULES.md 7. 이력에도 적는다.", "",
           f"## 1. 한 달 성적표: {L.totals_line(totals)}", "", "## 2. 틀린 예고 (어제 예고 ✗)"]
    for c in miss:
        out += [f"- [{c['graded']}] (확률 {int(c['p']*100)}%) {c['text']}", "  - 왜 틀렸나: ", "  - 규칙 수정: "]
    if not miss:
        out.append("- 없음")
    out += ["", "## 3. 성적표 「틀림」"]
    for r in wrong:
        out += [f"- [{r['date']}] 썼던 것: {r['wrote']} → 결과: {r['result']}", "  - 왜 틀렸나: ", "  - 규칙 수정: "]
    if not wrong:
        out.append("- 없음")
    out += ["", "## 4. 「반반」 (절반만 맞은 것)"] + [f"- [{r['date']}] {r['wrote']} → {r['result']}" for r in half] or ["- 없음"]
    cs = calibration_stats(led)
    out += ["", f"## 5. 확률 채점 (누적): {cs['line']}", "", "## 6. 경우의 수 확률이 움직인 날"]
    out += [f"- {h['date']}: A {h.get('A')} · B2 {h.get('B2')} · C {h.get('C')} · B {h.get('B')}" + (f" — {h['why']}" if h.get("why") else "") for h in hist] or ["- 없음"]
    out += ["", "## 7. 패널 재정렬"]
    for h in ranks:
        out += [f"- {h['date']}: 순위 대상 {h['ranked']}명 · 이동 {len(h['moves'])}명"] + [f"  - {m['name']} {m['from']}→{m['to']}" for m in h["moves"][:15]]
    if not ranks:
        out.append("- 이번 달 재정렬 없음")
    out += ["", "## 8. 규칙에 구멍이 있었나", "- (예: 10/3 고용지표 — 약세 쪽 규칙이 없어 즉석에서 추가) ", "", "## 9. 다음 달에 바꿀 것", "- "]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["weekly", "monthly"])
    ap.add_argument("--date", help="주간: 끝나는 날(일요일) YYYY-MM-DD, 기본 오늘")
    ap.add_argument("--month", help="월간: YYYY-MM, 기본 지난달")
    a = ap.parse_args()
    led = L.load()
    REV.mkdir(exist_ok=True)
    if a.kind == "weekly":
        end = date.fromisoformat(a.date) if a.date else date.today()
        w = weekly(led, end)
        (REV / f"weekly_{end.isoformat()}.json").write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
        p = REV / f"weekly_{end.isoformat()}.md"
        p.write_text(weekly_md(w), encoding="utf-8")
    else:
        if a.month:
            m = a.month
        else:
            t = date.today().replace(day=1) - timedelta(days=1)
            m = t.strftime("%Y-%m")
        p = REV / f"{m}.md"
        if p.exists():
            print(f"이미 있음: {p} (덮어쓰지 않음)")
            return
        p.write_text(monthly(led, m), encoding="utf-8")
    print(f"완료 → {p}")


if __name__ == "__main__":
    main()
