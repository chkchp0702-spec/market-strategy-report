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


def _who(n: str) -> str:
    """'에드 야데니 (패널 12)' → '에드야데니' — 괄호·공백 빼고 사람만"""
    return re.sub(r"\s+", "", re.sub(r"\(.*?\)|·.*$", "", n or ""))


def duel_check(day: dict, path: Path) -> int:
    """⚔️ 10/15 사용자: "오늘의 1:1 대결도 가장 흥미로운 걸로 매일 바꾸고 있는 거 맞아?" — 10/6~10/15 열흘 같은 대결이 복사됐음.
    최근 7개 판에 같은 두 사람(순서 무관) 또는 같은 제목이 있으면 실패."""
    du = day.get("duel") or {}
    if not du or du.get("none"):
        print("⚔️ 1:1 대결 없음 — 오늘 갈린 두 사람을 찾아 채우세요 (RULES 3-A)"); return 1
    pair, title = frozenset((_who(du.get("left_name")), _who(du.get("right_name")))), (du.get("title") or "").strip()
    prev = sorted(p for p in (ROOT / "data").glob("20*.json") if p.stem < path.stem)[-7:]
    for p in reversed(prev):
        try:
            o = json.loads(p.read_text(encoding="utf-8")).get("duel") or {}
        except Exception:
            continue
        if frozenset((_who(o.get("left_name")), _who(o.get("right_name")))) == pair or (o.get("title") or "").strip() == title:
            print(f"⚔️ 1:1 대결이 {p.stem} 와 같아요 ({du.get('left_name')} vs {du.get('right_name')} · {title}) — 최근 7판 안에 없던 새 대결로 바꾸세요 (RULES 3-A)")
            return 1
    print(f"⚔️ 1:1 대결 새로움 OK — {du.get('left_name')} vs {du.get('right_name')}")
    return 0


def main() -> int:
    day = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    dbad = duel_check(day, Path(sys.argv[1]))
    dbad = max(dbad, forecast_check(day, Path(sys.argv[1])))
    mp = ROOT / "market" / "latest.json"
    if not mp.exists():
        print("market/latest.json 없음 — 자동 수집치가 아직 없어 대조를 건너뜁니다 (출처 2개 이상으로 직접 확인).")
        return dbad
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
    return 1 if (bad or dbad) else 0


# ---------- 🎯 예고 규칙 (10/28 사용자 「다 고쳐」 — RULES 1-F) ----------
def _keytoks(t: str) -> set[str]:
    """예고 한 줄의 「무엇을·어디에 걸었나」: 날짜(10/28)·괄호 설명을 빼고 남은 티커·숫자."""
    t = re.sub(r"<[^>]+>", "", str(t or "")).split(". ")[0]
    t = re.sub(r"^\s*(어제\s*)?예고\s*[①-⑩0-9]*\s*", "", t)
    t = re.sub(r"\b\d{1,2}/\d{1,2}(\(\S\))?", " ", t)
    nums = {n.replace(",", "") for n in re.findall(r"\d[\d,]*\.?\d*", t)}
    tick = set(re.findall(r"[A-Z]{2,6}", t)) | set(re.findall(r"(코스피|코스닥|브렌트|WTI|10년|2년|30년|외국인|금|환율|원/달러|달러)", t))
    return nums | tick


def forecast_check(day: dict, path: Path) -> int:
    bad = 0
    msgs = []
    checks = day.get("checks") or []
    ps = day.get("forecasts_p") or []
    bs = day.get("forecasts_base")
    how = day.get("forecasts_base_how") or []
    iw = day.get("forecasts_if_wrong") or []
    n = len(checks)
    # ① 기저율 — 아무 생각 없이 찍어도 맞는 「공짜 문제」 금지
    if not isinstance(bs, list) or len(bs) != n or any(b is None for b in bs):
        msgs.append(f"forecasts_base 가 없음 — 예고 {n}개마다 `python -m src.fcbase …` 로 잰 기저율(0~1)을 적으세요"); bad += 1
    else:
        for i, b in enumerate(bs):
            if b > 0.65:
                msgs.append(f"예고 {i + 1} 기저율 {b:.2f} > 0.65 — 공짜 문제(지금 값 근처에 선 긋기). 방향·상대강도처럼 반반짜리로 바꾸세요"); bad += 1
            if i < len(ps) and ps[i] is not None and ps[i] < b:
                msgs.append(f"예고 {i + 1} 확률 {ps[i]:.2f} < 기저율 {b:.2f} — 반대쪽으로 거는 게 맞습니다"); bad += 1
    if len(how) != n or any(not str(h).strip() for h in how):
        msgs.append("forecasts_base_how 가 없음 — 기저율을 잰 명령(예: `python -m src.fcbase ^TNX up`)을 예고마다 적으세요"); bad += 1
    # ② 틀리면 무엇을 바꾸나 — 예고가 판단과 이어져야 함
    if len(iw) != n or any(len(str(x).strip()) < 6 for x in iw):
        msgs.append("forecasts_if_wrong 가 없음 — 예고마다 「틀리면 무엇을 바꾸나」(🧭 섹터 칸·비중·논지)를 한 줄씩"); bad += 1
    # ③ 걸어 둔 예고는 못 바꿈 — 장부의 어제 예고 그대로 채점
    try:
        led = json.loads((ROOT / "ledger" / "ledger.json").read_text(encoding="utf-8"))
        fc = (led.get("forecasts") or {}).get("items") or []
        gr = day.get("yesterday_grades") or []
        if fc and gr and str((led.get("forecasts") or {}).get("from", "")).split(" ")[0] != day.get("date"):
            if len(gr) != len(fc):
                msgs.append(f"어제 예고 {len(fc)}개인데 채점 {len(gr)}개 — 하나도 빼지 말고 그대로 채점"); bad += 1
            for i, (f, g) in enumerate(zip(fc, gr)):
                want = {k for k in _keytoks(f) if not re.fullmatch(r"\d", k)}
                have = _keytoks(g.get("title", "")) | _keytoks(g.get("text", ""))
                miss = want - have
                if want and len(miss) > len(want) / 2:
                    msgs.append(f"채점 {i + 1} 「{re.sub(r'<[^>]+>', '', g.get('title', ''))[:40]}」이 장부의 어제 예고 「{f[:40]}」와 다름 — 예고를 바꾸면 안 됨(바꿨다면 원래 예고를 ✗로)"); bad += 1
            # 보류(아직 날짜가 안 옴)로 넘긴 예고는 오늘 checks 에 그대로 남아야 함 — 10/25 CIBR→IGV 처럼 슬쩍 바꾸기 금지
            ck = [_keytoks(c) for c in checks]
            for i, (f, g) in enumerate(zip(fc, gr)):
                if g.get("cls") == "hold":
                    want = {k for k in _keytoks(f) if not re.fullmatch(r"\d", k)}
                    if want and not any(len(want - c) <= len(want) / 2 for c in ck):
                        msgs.append(f"보류한 예고 「{f[:40]}」가 오늘 예고에서 사라짐 — 날짜가 올 때까지 그대로 들고 가서 채점"); bad += 1
    except Exception as e:
        print("예고 잠금 대조 못 함", e)
    # ④ 같은 예고 사흘 연속 금지
    prev = sorted(p for p in path.parent.glob("20*.json") if p.name < path.name)[-2:]
    if len(prev) == 2:
        olds = []
        for p in prev:
            try:
                olds.append([_keytoks(c) for c in json.loads(p.read_text(encoding="utf-8")).get("checks", [])])
            except Exception:
                olds.append([])
        for i, c in enumerate(checks):
            k = _keytoks(c)
            if k and all(any(k == o for o in day_old) for day_old in olds):
                msgs.append(f"예고 {i + 1} 「{re.sub(r'<[^>]+>', '', c)[:40]}」 — 사흘 연속 같은 예고. 새 문제를 내세요"); bad += 1
    print("\n🎯 예고 규칙: " + ("통과" if not bad else f"{bad}건"))
    for m in msgs:
        print("  ✗ " + m)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
