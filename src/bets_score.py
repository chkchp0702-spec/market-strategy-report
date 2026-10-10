"""🧠 선제 아이디어(bets) 자동 채점 — 10/10 자가 업그레이드
  문제: 두뇌 세션은 야후 시세가 막혀 entry 를 못 정하고(「10/12 시가로 확정」), 열린 한도 10 에 걸리면
        entry 없는 bets 부터 「미진입 ±0」으로 닫았다 → 10/9~10/10 bets 19개 중 9개가 채점 한 번 없이 사라짐(0승 0패).
  해결: GitHub Actions(시세 됨)가 매시간 brain/state.json 의 bets 를 읽어
        ① entry_rule 의 날짜·시가/종가로 entry 를 정하고 ② 그 뒤 고가·저가로 target/stop/기한을 판정해
        market/bets_score.json 에 쓴다. state.json 은 건드리지 않는다(두뇌가 매시간 덮어쓰는 파일이라 충돌 방지).
        두뇌·아침 리포트가 이 파일을 읽어 bets 의 entry·status·res 와 scorecard.bets 를 옮겨 적는다.
  판정: 오름 — 고가 ≥ target 이김 · 저가 ≤ stop 짐 (같은 날 둘 다면 짐, 보수적) / 내림은 반대.
        기한(3일·1주=5·2주=10 거래일, entry 날 포함)이 지나면 마지막 종가로 「기한 ±x%」.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "brain" / "state.json"
OUT = ROOT / "market" / "bets_score.json"
HORIZON = {"1일": 1, "2일": 2, "3일": 3, "5일": 5, "1주": 5, "2주": 10, "3주": 15, "1달": 21, "1개월": 21}
LIVE = {"열림", "대기"}


def horizon_n(h) -> int:
    h = str(h or "1주").replace(" ", "")
    if h in HORIZON:
        return HORIZON[h]
    m = re.match(r"(\d+)(일|주)", h)
    return (int(m.group(1)) * (5 if m.group(2) == "주" else 1)) if m else 5


def entry_plan(b: dict, year: int) -> tuple[dt.date | None, str]:
    """entry 를 정할 날짜와 시가/종가. entry_rule(없으면 note 의 'entry = 10/12 시가')에 날짜가 없으면
    만든 날 다음 첫 거래일 시가(만든 시각에 이미 진행 중인 봉으로 정하지 않음)."""
    rule = str(b.get("entry_rule") or "")
    if not re.search(r"\d{1,2}/\d{1,2}", rule):
        m = re.search(r"entry\s*=\s*([^.·—]*)", str(b.get("note") or ""))
        rule = m.group(1) if m else ""
    m = re.search(r"(\d{1,2})/(\d{1,2})", rule)
    # 시가/종가는 날짜 바로 뒤 첫 말로 정한다 ('10/12 시가로 확정(… 10/8 종가 미확인)' → 시가)
    k = re.search(r"시가|종가", rule[m.end():] if m else rule)
    kind = "close" if k and k.group(0) == "종가" else "open"
    if m:
        try:
            return dt.date(year, int(m.group(1)), int(m.group(2))), kind
        except ValueError:
            pass
    try:
        return dt.datetime.strptime(str(b.get("made"))[:10], "%Y-%m-%d").date() + dt.timedelta(days=1), "open"
    except ValueError:
        return None, kind


def level(v, entry: float) -> float | None:
    """target/stop: 숫자 또는 'entry −5%' 같은 글."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("−", "-").replace("＋", "+").replace(" ", "")
    m = re.search(r"entry([+-]\d+(?:\.\d+)?)%", s)
    if m:
        return entry * (1 + float(m.group(1)) / 100)
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", s)
    return float(m.group(0).replace(",", "")) if m else None


def judge(b: dict, bars: list[dict], year: int) -> dict:
    """bars: [{'d': date, 'o','h','l','c'}] 날짜순. 결과 dict."""
    out = {"id": b.get("id"), "t": b.get("t"), "dir": b.get("dir")}
    entry = b.get("entry")
    if isinstance(entry, str):
        entry = level(entry, 0)
    plan_d, kind = entry_plan(b, year)
    if entry and re.search(r"\d{1,2}/\d{1,2}", str(b.get("entry_rule") or "")):
        # 두뇌가 값을 적었고 날짜 규칙도 있으면 그 날 봉부터 (시가 진입이면 그 날 고가·저가 포함)
        k = next((i for i, x in enumerate(bars) if x["d"] >= plan_d), None)
        if k is None:
            return {**out, "st": "대기", "res": f"{plan_d.month}/{plan_d.day} 봉 기다림"}
        idx = list(range(k if kind == "open" else k + 1, len(bars)))
        out.update(entry=round(float(entry), 4), entry_d=bars[k]["d"].isoformat(), entry_by="두뇌")
    elif entry:
        try:
            d0 = dt.datetime.strptime(str(b.get("entry_d") or b.get("made"))[:10], "%Y-%m-%d").date()
        except ValueError:
            d0 = None
        # 만든 시각 이후 첫 봉부터 본다 (만든 날 이미 지난 고가·저가로 판정하지 않음)
        idx = [i for i, x in enumerate(bars) if d0 is None or x["d"] > d0]
        out.update(entry=round(float(entry), 4), entry_by="두뇌")
    else:
        d = plan_d
        if d is None:
            return {**out, "st": "대기", "res": "entry 규칙을 못 읽음"}
        k = next((i for i, x in enumerate(bars) if x["d"] >= d), None)
        if k is None:
            return {**out, "st": "대기", "res": f"{d.month}/{d.day} {'종가' if kind == 'close' else '시가'} 기다림"}
        entry = bars[k]["o" if kind == "open" else "c"]
        if not entry:
            return {**out, "st": "대기", "res": "entry 값 없음"}
        out.update(entry=round(float(entry), 4), entry_d=bars[k]["d"].isoformat(),
                   entry_by=("시가" if kind == "open" else "종가"))
        idx = list(range(k if kind == "open" else k + 1, len(bars)))
    up = str(b.get("dir")) != "내림"
    tgt, stp = level(b.get("target"), entry), level(b.get("stop"), entry)
    n = horizon_n(b.get("horizon"))
    sign = 1 if up else -1
    last = None
    for j, i in enumerate(idx[:n]):
        x = bars[i]
        last = x
        hit_s = stp is not None and ((x["l"] <= stp) if up else (x["h"] >= stp))
        hit_t = tgt is not None and ((x["h"] >= tgt) if up else (x["l"] <= tgt))
        if hit_s:
            r = sign * (stp / entry - 1) * 100
            return {**out, "st": "닫힘", "win": False, "r": round(r, 2), "d1": x["d"].isoformat(),
                    "res": f"짐 {r:+.1f}% (손절 닿음 {x['d'].month}/{x['d'].day})"}
        if hit_t:
            r = sign * (tgt / entry - 1) * 100
            return {**out, "st": "닫힘", "win": True, "r": round(r, 2), "d1": x["d"].isoformat(),
                    "res": f"이김 {r:+.1f}% (목표 닿음 {x['d'].month}/{x['d'].day})"}
    if last is None:
        return {**out, "st": "열림", "r": 0.0, "res": "진입 · 아직 다음 봉 없음"}
    r = sign * (last["c"] / entry - 1) * 100
    if len(idx) >= n:
        return {**out, "st": "닫힘", "win": r > 0, "r": round(r, 2), "d1": last["d"].isoformat(),
                "res": f"기한 {r:+.1f}% ({n}거래일)"}
    return {**out, "st": "열림", "r": round(r, 2), "now": round(float(last["c"]), 4),
            "res": f"진행 {r:+.1f}% ({len(idx)}/{n}거래일)"}


def fetch(tickers: list[str], start: dt.date) -> dict[str, list[dict]]:
    import yfinance as yf
    out: dict[str, list[dict]] = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(start=start.isoformat(), interval="1d", auto_adjust=False)
        except Exception as e:  # noqa: BLE001
            print("시세 실패", t, e, file=sys.stderr)
            continue
        rows = []
        for idx, r in h.iterrows():
            if r["Close"] != r["Close"]:
                continue
            rows.append({"d": idx.date(), "o": float(r["Open"]), "h": float(r["High"]), "l": float(r["Low"]), "c": float(r["Close"])})
        out[t] = rows
    return out


def main() -> int:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    now = dt.datetime.now(KST)
    bets = [b for b in st.get("bets", []) if b.get("status") in LIVE and b.get("t")]
    if not bets:
        print("채점할 bets 없음")
        return 0
    start = min(dt.datetime.strptime(str(b.get("made"))[:10], "%Y-%m-%d").date() for b in bets) - dt.timedelta(days=3)
    bars = fetch(sorted({b["t"] for b in bets}), start)
    rows = []
    for b in bets:
        bs = bars.get(b["t"]) or []
        rows.append(judge(b, bs, now.year) if bs else {"id": b.get("id"), "t": b.get("t"), "st": "대기", "res": "시세 없음"})
    done = [r for r in rows if r.get("st") == "닫힘"]
    wins = [r for r in done if r.get("win")]
    out = {"at": now.strftime("%Y-%m-%d %H:%M"),
           "note": "두뇌·아침 리포트가 이 결과를 brain/state.json bets(entry·status·res)와 scorecard.bets 로 옮긴다. 자동 계산 · 매수 추천 아님.",
           "sum": {"live": len(rows), "closed": len(done), "win": len(wins), "loss": len(done) - len(wins),
                   "avg": round(sum(r["r"] for r in done) / len(done), 2) if done else None},
           "bets": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"bets {len(rows)} · 판정 {len(done)} (이김 {len(wins)}) → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
