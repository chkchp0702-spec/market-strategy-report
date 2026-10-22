"""🧾 시도 장부 (10/22 사용자 「다 진행」 — 퀀트 운용사 조사 ①)

  여러 조합을 시험해 1등을 고르면, 아무 실력이 없어도 1등은 좋아 보인다(Bailey·López de Prado).
  그래서 지금까지 시험한 조합 수를 전부 세고, 실험마다 「운만으로도 나올 수 있는 앞 구간 1등 샤프」(운 막대)를 적는다.
  · 조합 수: market/lab/*.json · market/*_bt.json 에서 grid/rows/trials 를 읽어 저절로 셈 (새 실험은 "trials" 키를 쓰면 그대로 씀)
  · 운 막대 E[max SR] ≈ √(1/Y) × ((1−γ)·Z(1−1/N) + γ·Z(1−1/(N·e)))  — Y = 앞 구간 햇수, N = 조합 수, γ = 0.5772
    → 샤프가 0인 전략 N개를 Y년 돌려도 1등은 평균 이만큼 나온다. 조합끼리 비슷하면 실제 몫은 더 작다(보수적인 막대).
  · 백테스트 깎기: CFM(Harvey·Liu 등) 관행대로 과거 검증의 초과수익·샤프는 절반으로 깎아서 본다 → haircut 0.5
→ market/trials.json (앱 성적표 🧪 검증 카드 아래 한 줄)
"""
from __future__ import annotations
import datetime as dt
import glob
import json
import math
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "trials.json"
KST = dt.timezone(dt.timedelta(hours=9))
GAMMA = 0.5772156649
IS_YEARS = 8.5          # 대부분 실험의 앞 구간 2008-07~2016
HAIRCUT = 0.5
Z = NormalDist().inv_cdf
# 단타 학습(stock-screener learn.py)은 다른 저장소 — 그쪽 learned.json 의 grid 를 lab 워크플로가 가져오지 않으므로 이름만 남김


def emax(n: int, years: float) -> float | None:
    """샤프 0인 전략 n개를 years 년 돌렸을 때 1등 샤프의 기댓값 (연율)"""
    if n < 2 or years <= 0:
        return None
    return round(math.sqrt(1 / years) * ((1 - GAMMA) * Z(1 - 1 / n) + GAMMA * Z(1 - 1 / (n * math.e))), 2)


def count(d) -> int | None:
    if not isinstance(d, dict):
        return None
    if isinstance(d.get("trials"), int):
        return d["trials"]
    for k in ("grid", "rows"):
        v = d.get(k)
        if isinstance(v, (list, dict)) and len(v) > 1:
            return len(v)
    if isinstance(d.get("n"), int) and d.get("rows"):
        return d["n"]
    sub = [len(v["grid"]) for v in d.values() if isinstance(v, dict) and isinstance(v.get("grid"), (list, dict))]
    return sum(sub) or None


def verdict_of(d):
    v = d.get("verdict") if isinstance(d, dict) else None
    return v if isinstance(v, str) else None


def main() -> int:
    rows = []
    for f in sorted(glob.glob(str(ROOT / "market" / "lab" / "*.json")) + glob.glob(str(ROOT / "market" / "*_bt.json"))):
        p = Path(f)
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        n = count(d)
        if not n:
            continue
        yrs = IS_YEARS
        if isinstance(d.get("is"), list) and len(d["is"]) == 2:
            try:
                a, b = (dt.date.fromisoformat(str(x)[:10]) for x in d["is"])
                yrs = max(0.5, (b - a).days / 365.25)
            except Exception:
                pass
        if p.stem.startswith("k1021_whale5"):
            yrs = 0.75                                    # 13F 목록 앞 3분기
        rows.append({"name": p.stem, "where": "lab" if "/lab/" in f.replace("\\", "/") else "bt", "n": n, "is_years": round(yrs, 1),
                     "luck_sharpe": emax(n, yrs), "verdict": verdict_of(d), "at": d.get("at") or d.get("made")})
    total = sum(r["n"] for r in rows)
    adopted = [r for r in rows if (r["verdict"] or "").startswith(("✅", "🧪"))]
    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "total": total, "experiments": len(rows), "adopted": len(adopted),
           "haircut": HAIRCUT, "luck_total": emax(total, IS_YEARS),
           "line": (f"🧾 지금까지 시험한 규칙 조합 {total:,}개 ({len(rows)}개 실험) — 이만큼 고르면 운만으로도 앞 구간 1등 샤프가 "
                    f"{emax(total, IS_YEARS)} 정도 나와요. 그래서 채택은 뒤 구간(2017~)으로만 판정하고, 과거 검증의 초과수익은 절반으로 깎아 봐요."),
           "rows": sorted(rows, key=lambda r: -r["n"]),
           "note": "운 막대 = 샤프 0인 조합 N개를 앞 구간 Y년 돌렸을 때 1등의 기댓값(Bailey·López de Prado). 조합끼리 비슷할수록 실제로는 더 작음 — 보수적 기준."}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out["line"])
    for r in out["rows"][:12]:
        print(f"  {r['name']:20} {r['n']:>5}조합 · 앞 {r['is_years']}년 · 운 막대 샤프 {r['luck_sharpe']} · {r['verdict'] or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
