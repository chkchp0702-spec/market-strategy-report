"""8. 패널 적중률 재정렬 · 9. 내 예고 확률 채점(캘리브레이션).

패널 재정렬 (매월 첫 리포트):
  적중률 = win / (win+loss), 판정 2건 이상인 사람만 순위 대상.
  판정이 부족한 사람은 기존 순서 유지한 채 뒤에 붙는다(그룹은 유지). 결과는 ledger.panel_rank_history 에 남긴다.

확률 채점:
  data.forecasts_p = [0.7, 0.6, 0.8]  — 「오늘 볼 것 3개」각각에 대한 "그렇게 될 것" 확률.
  다음 리포트의 yesterday_grades 가 ✓(ok)=1 · ✗(no)=0 · 보류=제외 로 결과를 준다.
  Brier = 평균 (p - 결과)^2  (0 완벽 · 0.25 동전 던지기).
  구간별: 60%대라고 한 것들이 실제로 몇 % 맞았나.
"""
from __future__ import annotations
from collections import defaultdict


# ---------- 9. 확률 채점 ----------

def record_calibration(led: dict, day: dict) -> None:
    """어제 예고(장부 forecasts)에 적어 둔 확률 p 와 오늘 채점(yesterday_grades)을 짝지어 장부에 쌓는다."""
    fc = led.get("forecasts", {})
    ps = fc.get("p") or []
    grades = day.get("yesterday_grades", [])
    if not ps or not grades:
        return
    cal = led.setdefault("calibration", [])
    src = fc.get("from", "")
    for i, (p, g) in enumerate(zip(ps, grades)):
        if any(c["from"] == src and c["i"] == i for c in cal):
            continue
        cls = g.get("cls")
        outcome = 1 if cls == "ok" else 0 if cls == "no" else None
        cal.append({"from": src, "i": i, "p": p, "outcome": outcome, "graded": day["date"],
                    "text": fc.get("items", [""] * 3)[i] if i < len(fc.get("items", [])) else ""})


def calibration_stats(led: dict) -> dict:
    rows = [c for c in led.get("calibration", []) if c.get("outcome") is not None]
    if not rows:
        return {"n": 0, "brier": None, "buckets": [], "line": "확률 채점 — 아직 자료 없음"}
    brier = sum((c["p"] - c["outcome"]) ** 2 for c in rows) / len(rows)
    b = defaultdict(lambda: [0, 0])
    for c in rows:
        k = min(int(c["p"] * 10) * 10, 90)
        b[k][0] += c["outcome"]; b[k][1] += 1
    buckets = [{"bucket": f"{k}%대", "hit": v[0], "n": v[1], "rate": round(100 * v[0] / v[1])} for k, v in sorted(b.items())]
    bias = sum(c["p"] for c in rows) / len(rows) - sum(c["outcome"] for c in rows) / len(rows)
    tone = "자신감 과잉" if bias > 0.1 else "자신감 부족" if bias < -0.1 else "대체로 맞춤"
    line = (f"확률 채점 {len(rows)}건 · 브라이어 {brier:.2f} (0 완벽·0.25 동전) · "
            + " · ".join(f"{x['bucket']} {x['hit']}/{x['n']}" for x in buckets) + f" → {tone}")
    return {"n": len(rows), "brier": round(brier, 3), "buckets": buckets, "bias": round(bias, 2), "tone": tone, "line": line}


# ---------- 8. 패널 재정렬 ----------

def hit_rate(p: dict) -> float | None:
    n = p["win"] + p["loss"]
    return None if n < 2 else p["win"] / n


def rerank_panel(led: dict, date: str, min_decisions: int = 2) -> list[dict]:
    """그룹 안에서 적중률 내림차순(동률이면 기존 순서). 판정 부족자는 그룹 뒤에 기존 순서로."""
    panel = led["panel"]
    groups: dict[str, list[dict]] = defaultdict(list)
    order = []
    for p in panel:
        if p["group"] not in groups:
            order.append(p["group"])
        groups[p["group"]].append(p)
    new = []
    for g in order:
        rows = groups[g]
        ranked = [p for p in rows if (p["win"] + p["loss"]) >= min_decisions]
        rest = [p for p in rows if (p["win"] + p["loss"]) < min_decisions]
        ranked.sort(key=lambda p: (-(p["win"] / (p["win"] + p["loss"])), -(p["win"] + p["loss"]), p["n"]))
        new += ranked + rest
    moves = []
    for i, p in enumerate(new, 1):
        if p["n"] != i:
            moves.append({"name": p["name"], "from": p["n"], "to": i})
        p["prev_n"] = p["n"]
        p["n"] = i
    led["panel"] = new
    led.setdefault("panel_rank_history", []).append({"date": date, "moves": moves,
                                                     "ranked": sum(1 for p in new if (p["win"] + p["loss"]) >= min_decisions)})
    return moves


def leaderboard(led: dict, top: int = 10) -> list[dict]:
    """대시보드·주간판용: 판정 있는 사람만 적중률 순."""
    rows = [p for p in led["panel"] if p["win"] + p["loss"] > 0]
    rows.sort(key=lambda p: (-(p["win"] / (p["win"] + p["loss"])), -(p["win"] + p["loss"])))
    return [{"n": p["n"], "name": p["name"], "group": p["group"], "win": p["win"], "loss": p["loss"],
             "rate": round(100 * p["win"] / (p["win"] + p["loss"]))} for p in rows[:top]]
