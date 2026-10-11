"""🧪 포트 규칙 검증 (규칙 ⑦ 「과거 검증 → 그림자 운용 → 편입」의 첫 단계)
  같은 규칙(src/rules7.py)을 2008년 이후 미국 섹터 ETF 9개 + 금(GLD) + 현금(BIL)에 매일 적용해 본다.
  비교: 같은 비중(현금 10%) · S&P500(SPY) / 규칙: ① 국면 현금 ③ 칸 기울이기 ④ 추세 브레이크 — 하나씩, 그리고 다 같이
  판단은 전날 종가까지, 수수료·세금 제외(대신 1년 평균 회전율을 같이 적음). 국면 점수의 무게는 같은 기간에서 정한 값이라 ①은 실제보다 좋게 나올 수 있음.
  → market/rules_bt.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.rules7 import rule_weights   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "rules_bt.json"
ASSETS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "GLD"]
NAMES = {"XLB": "소재", "XLE": "에너지", "XLF": "금융", "XLI": "산업재", "XLK": "기술", "XLP": "필수소비재", "XLU": "유틸리티", "XLV": "헬스케어", "XLY": "임의소비재", "GLD": "금"}
START = "2008-07-01"
STRATS = [("same", "같은 비중 (현금 10%)", ()), ("cash", "① 국면 현금 · 킥 포트에 켬", ("cash",)), ("tilt", "③ 칸 기울이기", ("tilt",)),
          ("brake", "④ 추세 브레이크", ("brake",)), ("tb", "③+④", ("tilt", "brake")), ("all", "①+③+④ 전부", ("cash", "tilt", "brake"))]


def main() -> int:
    import numpy as np
    import pandas as pd
    import yfinance as yf
    df = yf.download(ASSETS + ["SPY", "BIL"], start="2006-06-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in ASSETS + ["SPY", "BIL"]}).dropna(how="all").ffill()
    C = C[C.index >= "2007-06-01"].dropna()
    try:
        RH = json.loads(urllib.request.urlopen("https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/archive/x/regime_hist.json", timeout=60).read())["rows"]
    except Exception as e:
        print("국면 기록 못 받음", e); RH = []
    rq = pd.Series({pd.Timestamp(r[0]): r[3] for r in RH if r[3]}).sort_index()
    m50, m200 = C.rolling(50).mean(), C.rolling(200).mean()
    r63, r126 = C / C.shift(63) - 1, C / C.shift(126) - 1
    idx = [d for d in C.index if d >= pd.Timestamp(START)]
    pos0 = list(C.index).index(idx[0])
    ret = C.pct_change()
    base = [(t, 9.0) for t in ASSETS] + [("현금", 10.0)]
    state = {k: {"nav": 1.0, "prev": None, "turn": 0.0, "navs": []} for k, _, _ in STRATS}
    rqi = rq.index
    for i in range(pos0, len(C.index) - 1):
        d0, d1 = C.index[i], C.index[i + 1]
        st = {}
        for t in ASSETS:
            if pd.isna(m200.at[d0, t]) or pd.isna(r126.at[d0, t]):
                continue
            last = C.at[d0, t]
            rel63 = r63.at[d0, t] - r63.at[d0, "SPY"]; rel126 = r126.at[d0, t] - r126.at[d0, "SPY"]
            st[t] = {"rel63": rel63, "rel126": rel126, "mom": (rel63 + rel126) / 2, "below50": last < m50.at[d0, t], "below200": last < m200.at[d0, t]}
        j = rqi.searchsorted(d0, side="right") - 1
        qd = rq.iloc[j] if j >= 0 else None
        for key, lab, use in STRATS:
            S = state[key]
            w, _, _ = rule_weights(base, st, qd, use)
            r = sum(w[t] / 100 * ret.at[d1, t] for t in ASSETS) + w["현금"] / 100 * ret.at[d1, "BIL"]
            if S["prev"]:
                S["turn"] += sum(abs(w[k] - S["prev"][k]) for k in w) / 200
            S["prev"] = w
            S["nav"] *= 1 + r
            S["navs"].append((d1, S["nav"]))
    res = {k: (lab, pd.Series({d: v for d, v in state[k]["navs"]}), state[k]["turn"]) for k, lab, _ in STRATS}
    spy = C["SPY"][C.index >= idx[0]]; spy = spy / spy.iloc[0]
    bil = C["BIL"][C.index >= idx[0]]; bil = bil / bil.iloc[0]

    def met(s, turn=None):
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        cagr = s.iloc[-1] ** (1 / yrs) - 1
        dr = s.pct_change().dropna()
        vol = dr.std() * np.sqrt(252)
        mdd = (s / s.cummax() - 1).min()
        ex = dr - bil.pct_change().reindex(dr.index).fillna(0)
        sharpe = ex.mean() / ex.std() * np.sqrt(252) if ex.std() else None
        yr = s.resample("YE").last(); sy = spy.resample("YE").last()
        yr_r = yr.pct_change(); yr_r.iloc[0] = yr.iloc[0] - 1
        sy_r = sy.pct_change(); sy_r.iloc[0] = sy.iloc[0] - 1
        beat = int((yr_r > sy_r).sum())
        def back(n):
            t = s.index[-1] - pd.Timedelta(days=int(365.25 * n)); a = s[s.index <= t]
            return round((s.iloc[-1] / a.iloc[-1]) ** (1 / n) * 100 - 100, 2) if len(a) else None
        return {"cagr": round(cagr * 100, 2), "vol": round(vol * 100, 1), "mdd": round(mdd * 100, 1), "sharpe": round(float(sharpe), 2) if sharpe is not None else None,
                "beat_years": beat, "years": len(yr), "y1": back(1), "y3": back(3), "y5": back(5),
                "turn": round(turn / yrs * 100) if turn is not None else None,
                "yr": {str(d.year): round(v * 100, 1) for d, v in yr_r.items()}}
    rows = [{"k": "spy", "lab": "S&P500 (SPY)", **met(spy)}] + [{"k": k, "lab": lab, **met(s, t)} for k, (lab, s, t) in res.items()]
    # 판정: 같은 비중 대비 무엇이 나아졌나
    b = next(r for r in rows if r["k"] == "same")
    for r in rows:
        if r["k"] in ("spy", "same"):
            continue
        r["vs_same"] = {"cagr": round(r["cagr"] - b["cagr"], 2), "mdd": round(r["mdd"] - b["mdd"], 1), "sharpe": round((r["sharpe"] or 0) - (b["sharpe"] or 0), 2)}
        r["verdict"] = ("✅ 나아짐" if r["vs_same"]["sharpe"] > 0.05 and r["vs_same"]["cagr"] > -0.5 else "➖ 비슷" if abs(r["vs_same"]["sharpe"]) <= 0.05 else "❌ 나빠짐")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": idx[0].strftime("%Y-%m-%d"),
           "to": C.index[-1].strftime("%Y-%m-%d"), "assets": [NAMES[a] for a in ASSETS], "regime_weeks": len(rq), "rows": rows,
           "note": "미국 섹터 ETF 9개 + 금, 같은 비중 9%씩 + 현금 10%에 규칙을 매일(전날 종가까지 자료로) 적용 · 수수료·세금 제외 · "
                   "회전율 = 1년에 포트를 몇 % 바꿨나 · ① 국면 점수의 무게는 같은 기간에서 정한 값이라 실제보다 좋게 나올 수 있음 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['lab']:24s} 연 {r['cagr']:+6.2f}% · 변동 {r['vol']}% · 최대낙폭 {r['mdd']}% · 샤프 {r['sharpe']} · S&P 이긴 해 {r['beat_years']}/{r['years']} · 회전 {r.get('turn')}% {r.get('verdict', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
