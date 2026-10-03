"""2. 검산: data/YYYY-MM-DD.json 에 적은 숫자를 market/latest.json(자동 수집치)과 대조한다.

사용: python -m src.verify data/2026-10-06.json
출력: 항목별 [입력값 | 수집값 | 차이 | 판정]. 차이가 허용치를 넘으면 exit 1 (리포트 작성자가 다시 확인).
숫자는 kpis[].value / change, ledger_commit.series_add 에서 뽑는다. 못 찾은 항목은 '대조 불가'로만 표시한다.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# kpi 라벨에 들어 있는 말 → 수집 key, 허용 오차(절대값), 소수 자리
MAP = [
    (r"10년", "us10y", 0.03, 2), (r"30년", "us30y", 0.04, 2), (r"S&P", "sp500", 15, 0), (r"나스닥", "nasdaq", 60, 0),
    (r"다우", "dow", 120, 0), (r"달러/원|환율", "usdkrw", 12, 1), (r"WTI", "wti", 0.8, 2), (r"브렌트", "brent", 0.8, 2),
    (r"\b금\b|금값|금 ", "gold", 20, 0), (r"코스피", "kospi", 15, 0), (r"코스닥", "kosdaq", 8, 0), (r"VIX", "vix", 0.6, 1),
    (r"삼성", "samsung", 800, 0), (r"하이닉스", "hynix", 3000, 0), (r"마이크론", "micron", 3, 1), (r"외국인", "foreign_kospi", 150, 0),
]


def _num(s: str) -> float | None:
    s = s.replace(",", "").replace("−", "-").replace("~", " ")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def _range(s: str) -> tuple[float, float] | None:
    s = s.replace(",", "").replace("−", "-")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*~\s*(-?\d+(?:\.\d+)?)", s)
    return (float(m.group(1)), float(m.group(2))) if m else None


def main() -> int:
    day = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    mp = ROOT / "market" / "latest.json"
    if not mp.exists():
        print("market/latest.json 없음 — 자동 수집치가 아직 없어 대조를 건너뜁니다 (출처 2개 이상으로 직접 확인).")
        return 0
    items = json.loads(mp.read_text(encoding="utf-8"))["items"]
    rows, bad = [], 0
    checked = set()
    for k in day.get("kpis", []):
        label, val = k["label"], k["value"]
        # 라벨에 여러 항목이 있으면("나스닥 / S&P500") 먼저 나오는 항목 = 첫 숫자
        cands = sorted(((m.start(), pat, key, tol, nd) for pat, key, tol, nd in MAP if key not in checked for m in [re.search(pat, label)] if m), key=lambda x: x[0])
        for _, pat, key, tol, nd in cands[:1]:
            if True:
                it = items.get(key) or items.get(key + "_tsy")
                if key == "us10y" and items.get("us10y_tsy"):
                    it = items["us10y_tsy"]
                mine = _num(val)
                rng = _range(val) or _range(k.get("change", ""))
                if not it or mine is None:
                    rows.append((label, val, "—", "—", "대조 불가"))
                else:
                    got = it["value"]
                    # "+1.19%" 처럼 등락률로 적은 카드는 수집치의 등락률과 비교 (금리 카드는 수준 그대로)
                    if "%" in val and key not in ("us10y", "us30y", "us2y") and it.get("change_pct") is not None:
                        got, tol, nd = it["change_pct"], 0.15, 2
                    diff = mine - got
                    ok = abs(diff) <= tol or (rng and rng[0] - tol <= got <= rng[1] + tol)
                    bad += 0 if ok else 1
                    rows.append((label, val, f"{got:,.{nd}f} ({it.get('asof_kst') or it.get('date','')})", f"{diff:+.{nd}f}", "OK" if ok else "확인!"))
                checked.add(key)
                break
    sa = day.get("ledger_commit", {}).get("series_add", {})
    for key, tol, nd in (("foreign_kospi", 150, 0), ("us10y", 0.03, 2)):
        if key in sa:
            it = items.get("us10y_tsy") if key == "us10y" else items.get(key)
            if it:
                diff = sa[key]["value"] - it["value"]
                ok = abs(diff) <= tol
                bad += 0 if ok else 1
                rows.append((f"series {key} {sa[key]['date']}", str(sa[key]["value"]), f"{it['value']:,.{nd}f} ({it.get('date') or it.get('asof_kst','')})", f"{diff:+.{nd}f}", "OK" if ok else "확인!"))
    w = max(len(r[0]) for r in rows) if rows else 10
    print(f"{'항목':<{w}}  {'입력':<18} {'수집':<28} {'차이':<10} 판정")
    for r in rows:
        print(f"{r[0]:<{w}}  {r[1]:<18} {r[2]:<28} {r[3]:<10} {r[4]}")
    print(f"\n어긋남 {bad}건" + (" — 입력값이나 수집값 중 어느 쪽이 맞는지 출처를 하나 더 보고 고치세요. 날짜가 다르면(수집은 장중, 입력은 종가) 그 사실을 리포트에 적습니다." if bad else " — 통과"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
