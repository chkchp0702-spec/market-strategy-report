"""📈 11/5 16시 — 🎯 변동성 맞춤 「무엇으로 재나」 가족 실험 (14시 다음 회차 계획)
  지금 🎯 : 주식 칸 크기 = 목표 22 ÷ (S½·Q½ 20일 실현 변동성), 위 1.0·아래 0.70 · 월말 흐름·국면·🧭 추세 칸 그대로
  바꾸는 것은 「재는 자」 하나뿐 — 13판:
    rv10·rv40·rv60 · 10/60 평균 · max(20,60) · EWMA λ0.94·0.97 · max(EWMA .94,.97)(S&P 위험 관리 지수식)
    하방 변동성(내린 날만, ×√2) 20·60일 · VIX · VIX½+VXN½(내재 변동성 = 시장이 부르는 앞으로의 흔들림)
  판마다 앞 구간(2008-07~2016) 변동성을 🎯 와 같게(목표 이분 탐색) → 「위험만 늘린 몫」을 뺀 숫자로 비교
  앞 1등을 고르고 뒤(2017~)에서 시험 · 앞 1등 이웃 흔들기(창·λ ±20%) · 비용 0.1%(+앞 1등 0.25%)
  판정: 앞 ≥0 · 뒤 +1%p ✅ / +0.33 🟡 · 흔들기 뒤 플러스
→ market/lab/k1105_volmeas.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
import k1028_qflow as QF
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC

OUT = Path("market/lab/k1105_volmeas.json")
A = math.sqrt(252) * 100


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "^VIX", "^VXN"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    vix = px.pop("^VIX")["close"].reindex(C.index).ffill()
    vxn = px.pop("^VXN")["close"].reindex(C.index).ffill()
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    msig, mfs = make(C, DM, DQ)
    r = 0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()

    def rvw(w):
        return r.rolling(w).std() * A

    def ew(lam):
        return np.sqrt((r ** 2).ewm(alpha=1 - lam, adjust=False).mean()) * A

    def dn(w):
        return np.sqrt((r.clip(upper=0) ** 2).rolling(w).mean() * 2) * A

    MEAS = {
        "rv20(지금)": lambda: rvw(20), "rv10": lambda: rvw(10), "rv40": lambda: rvw(40), "rv60": lambda: rvw(60),
        "avg10_60": lambda: 0.5 * (rvw(10) + rvw(60)), "max20_60": lambda: np.maximum(rvw(20), rvw(60)),
        "ewma94": lambda: ew(0.94), "ewma97": lambda: ew(0.97), "ewmaMax": lambda: np.maximum(ew(0.94), ew(0.97)),
        "down20": lambda: dn(20), "down60": lambda: dn(60),
        "vix": lambda: vix, "vix_vxn": lambda: 0.5 * vix + 0.5 * vxn.fillna(vix),
    }
    SHAKE = {"rv10": [8, 12], "rv40": [32, 48], "rv60": [48, 72], "down20": [16, 24], "down60": [48, 72],
             "ewma94": [0.928, 0.952], "ewma97": [0.964, 0.976], "ewmaMax": [(0.928, 0.964), (0.952, 0.976)],
             "avg10_60": [(8, 48), (12, 72)], "max20_60": [(16, 48), (24, 72)], "vix": [("vixlag", 3), ("vixlag", 5)],
             "vix_vxn": [("vvlag", 3), ("vvlag", 5)]}

    def shake_meas(name, p):
        if name in ("rv10", "rv40", "rv60"):
            return rvw(p)
        if name in ("down20", "down60"):
            return dn(p)
        if name in ("ewma94", "ewma97"):
            return ew(p)
        if name == "ewmaMax":
            return np.maximum(ew(p[0]), ew(p[1]))
        if name == "avg10_60":
            return 0.5 * (rvw(p[0]) + rvw(p[1]))
        if name == "max20_60":
            return np.maximum(rvw(p[0]), rvw(p[1]))
        if name == "vix":
            return vix.rolling(p[1]).mean()
        if name == "vix_vxn":
            return (0.5 * vix + 0.5 * vxn.fillna(vix)).rolling(p[1]).mean()

    def go(meas, tgt, cost=0.001):
        QF.COST = cost
        sc = (tgt / meas).clip(upper=1.0, lower=0.70).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, msig, mfs, G_CONC, RD_CONC)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "nav": nav,
                "on": round(float((sc.reindex(idx) < 0.999).mean() * 100), 1)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol", "turn")} for p in ("is", "oos")}

    def matched(meas, base, cost=0.001, lo=8.0, hi=60.0):
        best = None
        for _ in range(8):
            m = (lo + hi) / 2; rr = go(meas, m, cost)
            if best is None or abs(rr["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, rr)
            if rr["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    B = go(rvw(20), 22.0)
    out["base"] = {"is": B["is"], "oos": B["oos"], "on_pct": B["on"]}
    print("BASE", B["is"], B["oos"], flush=True)
    grid = {}
    for nm, f in MEAS.items():
        if nm.startswith("rv20"):
            continue
        t, rr = matched(f(), B)
        grid[nm] = {"tgt": t, "on_pct": rr["on"], "d": dlt(B, rr)}
        print(nm, t, grid[nm]["d"], flush=True)
    out["grid"] = grid
    pick = max(grid, key=lambda k: grid[k]["d"]["is"]["cagr"])
    out["pick_is"] = pick
    t, rr = matched(MEAS[pick](), B)
    yr = {}
    for y in range(2008, idx[-1].year + 1):
        a = B["nav"][B["nav"].index.year == y]; b = rr["nav"][rr["nav"].index.year == y]
        if len(a) > 5:
            yr[str(y)] = round(float((b.iloc[-1] / b.iloc[0] - a.iloc[-1] / a.iloc[0]) * 100), 2)
    out["pick_yr"] = yr
    B25 = go(rvw(20), 22.0, 0.0025)
    t25, r25 = matched(MEAS[pick](), B25, 0.0025)
    out["pick_cost25"] = dlt(B25, r25)
    sh = {}
    for p in SHAKE.get(pick, []):
        t2, r2 = matched(shake_meas(pick, p), B)
        sh[str(p)] = {"tgt": t2, "d": dlt(B, r2)}
        print("SHAKE", p, sh[str(p)], flush=True)
    out["shake"] = sh
    oos_pos = sum(1 for v in grid.values() if v["d"]["oos"]["cagr"] > 0)
    d = grid[pick]["d"]
    j = {"pick": pick, "is": d["is"]["cagr"], "oos": d["oos"]["cagr"], "oos_sharpe": d["oos"]["sharpe"],
         "oos_mdd": d["oos"]["mdd"], "oos_vol": d["oos"]["vol"], "oos_pos_of": f"{oos_pos}/{len(grid)}",
         "shake_ok": bool(sh) and all(v["d"]["oos"]["cagr"] > 0 for v in sh.values()),
         "shake_min": min((v["d"]["oos"]["cagr"] for v in sh.values()), default=None),
         "cost25_oos": out["pick_cost25"]["oos"]["cagr"]}
    j["verdict"] = "✅" if (j["oos"] > 1.0 and j["is"] >= 0 and j["shake_ok"]) else ("🟡" if (j["oos"] >= 0.33 and j["is"] >= 0) else "❌")
    out["judge"] = j
    print("JUDGE", j, flush=True)
    out["note"] = "기준 = 지금 🎯(목표 22·아래 0.70·월말 흐름·국면·🧭 추세 칸) · 재는 자만 바꿈 · 판마다 앞 구간 변동성 같게 · 레버리지 없음 · ETF·지수만, 생존 편향 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
