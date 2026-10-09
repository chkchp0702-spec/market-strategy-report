"""💼 포트 — 「시황리포트대로 투자했다면」 (10/9 사용자 요청)
  · 장부(ledger.json) allocation = 리포트의 자산 배분표. 바뀔 때마다 market/port_log.json 에 날짜와 함께 쌓는다.
  · 칸마다 따라 사기 쉬운 대표 상품(미국 ETF / 한국 상장 ETF)을 정하고, 미국 상품 종가로 하루하루 성적을 계산한다.
    - 리포트(한국 아침) D 의 배분은 미국 D 거래일(전날 종가 → D 종가)부터 적용 (리포트 뒤에 살 수 있는 첫 장)
    - 매일 비중을 맞춘다고 가정(리밸런싱 비용·세금·환율 제외)
  · 비교: S&P500(SPY) · 코스피 · 주식60/채권40(AOR)
  → market/port.json (앱 💼 포트 탭)
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger" / "ledger.json"
LOG = ROOT / "market" / "port_log.json"
OUT = ROOT / "market" / "port.json"
START = "2026-10-02"        # 장부 집계 시작일 (첫 배분표)

# 칸 이름에 이 말이 있으면 → 성적 계산·따라하기용 미국 상품 (없으면 instruments 에서 미국 티커를 읽음)
US_PICK = [
    ("현금", ["SGOV"]), ("단기채", ["SGOV"]),
    ("전력", ["XLU", "GEV"]), ("인프라", ["XLU", "GEV"]), ("원자력", ["NLR"]),
    ("에너지", ["XLE"]), ("금융", ["KBWB"]), ("반도체", ["SOXX"]), ("금", ["GLD"]),
    ("장기채", ["TLT"]), ("소프트웨어", None), ("광통신", None),
]
NOT_TICKER = {"TIGER", "RISE", "KODEX", "ACE", "SOL", "PLUS", "KRX", "CD", "AI", "HBM", "ETF", "KIS", "TOP", "S", "KB",
              "HANARO", "KBSTAR", "ARIRANG", "KOSEF", "NH", "SK", "LG", "OIL"}
BENCH = {"SPY": "S&P500", "^KS11": "코스피", "AOR": "주식60·채권40"}


def us_of(name: str, inst: str) -> list[str]:
    for k, v in US_PICK:
        if k in name and v:
            return v
    toks = re.findall(r"(?<![A-Za-z0-9])([A-Z]{2,5})(?![A-Za-z0-9])", inst)
    out = []
    for t in toks:
        if t not in NOT_TICKER and t not in out:
            out.append(t)
    return out[:4]


def kr_of(inst: str) -> list[dict]:
    out = []
    for nm, code in re.findall(r"([^·/]+?)\s+([0-9][0-9A-Z]{5})(?![0-9A-Z])", inst):
        nm = re.sub(r"^\s*(국내 참고|국내)\s*", "", nm).strip()
        out.append({"code": code, "name": nm, "etf": bool(re.match(r"(TIGER|RISE|KODEX|ACE|SOL|PLUS|HANARO|KBSTAR|ARIRANG)", nm))})
    return out[:4]


def update_log(now) -> list[dict]:
    L = json.loads(LEDGER.read_text(encoding="utf-8"))
    alloc = [{"pct": a["pct"], "name": a["name"], "instruments": a.get("instruments", "")} for a in L.get("allocation", [])]
    try:
        log = json.loads(LOG.read_text(encoding="utf-8"))
    except Exception:
        log = []
    sig = lambda a: [(x["pct"], x["name"]) for x in a]
    today = now.strftime("%Y-%m-%d")
    if not log:
        log = [{"date": START, "alloc": alloc, "why": "장부 시작 배분표"}]
    elif sig(log[-1]["alloc"]) != sig(alloc):
        old = {x["name"]: x["pct"] for x in log[-1]["alloc"]}
        ch = [f"{x['name']} {old.get(x['name'], 0)}→{x['pct']}%" for x in alloc if old.get(x["name"]) != x["pct"]]
        ch += [f"{n} {p}→0%" for n, p in old.items() if n not in {x["name"] for x in alloc}]
        entry = {"date": today, "alloc": alloc, "why": " · ".join(ch)}
        if log[-1]["date"] == today:
            log[-1] = entry
        else:
            log.append(entry)
    else:
        log[-1]["alloc"] = alloc          # 상품 글자만 바뀐 경우 최신으로
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return log


def main() -> int:
    now = dt.datetime.now(KST)
    log = update_log(now)
    import yfinance as yf
    import pandas as pd

    tick = set(BENCH) | {"KRW=X"}
    for e in log:
        for a in e["alloc"]:
            tick |= set(us_of(a["name"], a["instruments"]))
    kr_codes = {k["code"] for a in log[-1]["alloc"] for k in kr_of(a["instruments"]) if k["code"].isdigit()}
    start = (dt.date.fromisoformat(START) - dt.timedelta(days=10)).isoformat()
    df = yf.download(sorted(tick) + [c + ".KS" for c in kr_codes], start=start, interval="1d", auto_adjust=True, progress=False,
                     group_by="ticker", threads=True)
    C = {}
    for t in list(tick) + [c + ".KS" for c in kr_codes]:
        try:
            s = df[t]["Close"].dropna()
            if len(s):
                C[t] = s
        except Exception:
            pass
    miss = sorted(t for t in tick if t not in C)
    # 미국 거래일 달력 (SPY 기준)
    days = [d for d in C["SPY"].index if d.strftime("%Y-%m-%d") >= START]
    base_i = list(C["SPY"].index).index(days[0]) - 1      # START 전날 종가 = 출발점
    cal = list(C["SPY"].index)[base_i:]

    def ret(t, d0, d1):
        s = C.get(t)
        if s is None:
            return None
        a = s[s.index <= d0]
        b = s[s.index <= d1]
        if not len(a) or not len(b):
            return None
        return float(b.iloc[-1] / a.iloc[-1] - 1)

    def alloc_on(d):
        ds = d.strftime("%Y-%m-%d")
        cur = log[0]
        for e in log:
            if e["date"] <= ds:
                cur = e
        return cur

    nav, bn = [1.0], {k: [1.0] for k in BENCH}
    contrib, series_d = {}, [cal[0].strftime("%Y-%m-%d")]
    daily = []
    for i in range(1, len(cal)):
        d0, d1 = cal[i - 1], cal[i]
        e = alloc_on(d1)
        r_tot, parts = 0.0, {}
        for a in e["alloc"]:
            us = us_of(a["name"], a["instruments"])
            rs = [x for x in (ret(t, d0, d1) for t in us) if x is not None]
            r = sum(rs) / len(rs) if rs else 0.0
            c = a["pct"] / 100 * r
            r_tot += c
            parts[a["name"]] = c
            contrib[a["name"]] = contrib.get(a["name"], 0) + c * nav[-1]
        nav.append(nav[-1] * (1 + r_tot))
        for k in BENCH:
            r = ret(k, d0, d1)
            bn[k].append(bn[k][-1] * (1 + (r or 0)))
        series_d.append(d1.strftime("%Y-%m-%d"))
        daily.append({"d": d1.strftime("%Y-%m-%d"), "r": round(r_tot * 100, 2), "spy": round((ret("SPY", d0, d1) or 0) * 100, 2)})

    peak, mdd = 1.0, 0.0
    for v in nav:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    fx = float(C["KRW=X"].iloc[-1]) if "KRW=X" in C else None

    # 지금 담을 것 (따라하기)
    cur = log[-1]
    hold = []
    for a in cur["alloc"]:
        us = us_of(a["name"], a["instruments"])
        kr = kr_of(a["instruments"])
        for k in kr:
            s = C.get(k["code"] + ".KS")
            if s is not None and len(s):
                k["px"] = round(float(s.iloc[-1]))
        chk = []
        for t in us:
            sr = C.get(t)
            if sr is None or len(sr) < 25:
                continue
            last = float(sr.iloc[-1]); m20 = float(sr.iloc[-20:].mean())
            r5 = (last / float(sr.iloc[-6]) - 1) * 100; r20 = (last / float(sr.iloc[-21]) - 1) * 100
            spy = C["SPY"]; s5 = (float(spy.iloc[-1]) / float(spy.iloc[-6]) - 1) * 100; s20 = (float(spy.iloc[-1]) / float(spy.iloc[-21]) - 1) * 100
            chk.append({"t": t, "r5": round(r5, 2), "r20": round(r20, 2), "rs5": round(r5 - s5, 2), "rs20": round(r20 - s20, 2), "above20": last >= m20})
        sig = ""
        if chk:
            a20 = sum(1 for c in chk if c["above20"]) / len(chk)
            rs20 = sum(c["rs20"] for c in chk) / len(chk); rs5 = sum(c["rs5"] for c in chk) / len(chk)
            sig = ("약함 — 20일선 아래·S&P보다 약함 → 줄일 후보" if a20 < .5 and rs20 < -2 else
                   "강함 — S&P보다 강하고 20일선 위 → 유지·늘릴 후보" if a20 >= .5 and rs20 > 2 and rs5 > -1 else
                   "꺾이는 중 — 5일 약세 → 지켜보기" if rs5 < -3 else "보통")
        hold.append({"name": a["name"], "pct": a["pct"], "instruments": a["instruments"], "check": chk, "sig": sig,
                     "us": [{"t": t, "px": round(float(C[t].iloc[-1]), 2) if t in C else None,
                             "r1": round((ret(t, cal[-2], cal[-1]) or 0) * 100, 2) if t in C and len(cal) > 1 else None,
                             "since": round((ret(t, cal[0], cal[-1]) or 0) * 100, 2) if t in C else None} for t in us],
                     "kr": kr, "contrib": round(contrib.get(a["name"], 0) * 100, 2)})
    prev = log[-2]["alloc"] if len(log) > 1 else None
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"), "start": START, "asof": cal[-1].strftime("%Y-%m-%d"), "fx": round(fx, 1) if fx else None,
        "dates": series_d, "nav": [round((v - 1) * 100, 2) for v in nav],
        "bench": {BENCH[k]: [round((v - 1) * 100, 2) for v in bn[k]] for k in BENCH},
        "stat": {"ret": round((nav[-1] - 1) * 100, 2), "spy": round((bn["SPY"][-1] - 1) * 100, 2),
                 "kospi": round((bn["^KS11"][-1] - 1) * 100, 2), "mix": round((bn["AOR"][-1] - 1) * 100, 2),
                 "mdd": round(mdd * 100, 2), "days": len(cal) - 1,
                 "win": sum(1 for x in daily if x["r"] > x["spy"]),
                 "best": max(daily, key=lambda x: x["r"]) if daily else None,
                 "worst": min(daily, key=lambda x: x["r"]) if daily else None},
        "daily": daily[-30:], "hold": hold, "changes": [{"date": e["date"], "why": e.get("why", "")} for e in log][::-1],
        "prev": prev, "miss": miss,
        "note": "리포트 배분표를 그대로 따랐다면의 계산. 매일 비중 유지 가정 · 수수료·세금·환율 제외 · 미국 대표 상품 종가 기준. 매수 추천 아님.",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"포트 {out['stat']['ret']:+.2f}% vs S&P {out['stat']['spy']:+.2f}% · {out['stat']['days']}거래일 · 빠진 시세 {miss}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
