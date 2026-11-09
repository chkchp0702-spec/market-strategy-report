"""📈 11/9 10시 — k1109_portmenu: 🎚 💼 기본 포트 위험 선택지(이번 주 첫 메뉴) — 목표 변동성 × 아래 한도
  틀 = k1106_portexec2 그대로(💼 = S&P 47.5·나스닥 47.5·금 5 / 하락 31.5·31.5·금 11 + 🧭 추세 칸 주차 + 🔄 월말 흐름)
  판: 목표 12·13.5·15(지금)·16.5·18·20·22 × 아래 한도 0.3(지금)·0.5 · 위 한도 1.0 그대로(레버리지 없음)
  흐름 = 지금 실제(s0_c1: 알림 하루 늦음·다음 날 종가) · 고른 판은 Q11/6-3 예약 종가판(s1_c1)·비용 0.25% 로도
→ market/lab/k1109_portmenu.json
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
from k1028_qflow import drifts, make, rfe, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1109_portmenu.json")
A = math.sqrt(252) * 100


def tstat(x):
    x = x.dropna()
    if len(x) < 5 or x.std() == 0:
        return {"n": int(len(x)), "bp": 0.0, "t": 0.0, "sum": 0.0}
    return {"n": int(len(x)), "bp": round(float(x.mean()) * 1e4, 2), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2),
            "sum": round(float(x.sum()) * 100, 2)}


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {}
    for k in ["SPY", "QQQ", "GLD"]:
        O[k] = px.pop(k)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    O["TLT"] = px["TLT"]
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
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * A
    G, Rd = G_PORT, RD_PORT

    ON = pd.DataFrame(0.0, index=C.index, columns=KEYS); ID = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ON[k] = on; ID[k] = (1 + cc) / (1 + on) - 1
    ID["TRD"] = C["TRD"].pct_change().fillna(0.0)

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    res = {}
    def sh(a, k):
        return a.shift(-k).fillna(0.0)
    def go(nm, t, lo, a_, f_, m="c1", cost=0.001):
        sc = (t / rv).clip(upper=1.0, lower=lo).fillna(1.0)
        nav, td = run(C, ON, ID, reg, idx, sc, a_, f_, G, Rd, m, cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        r = nav.pct_change().dropna()
        vi = float(r[(r.index >= START) & (r.index <= IS_END)].std() * A); vo = float(r[r.index >= OOS_START].std() * A)
        ex = sc.shift(1).reindex(idx)
        res[nm] = {"t": t, "lo": lo, "is": a, "oos": b, "vol_is": round(vi, 2), "vol_oos": round(vo, 2),
                   "expo_is": round(float(ex[ex.index <= IS_END].mean()), 3), "expo_oos": round(float(ex[ex.index >= OOS_START].mean()), 3)}
        print(nm, a["cagr"], b["cagr"], b["mdd"], round(vo, 2), flush=True)
    for t in (12.0, 13.5, 15.0, 16.5, 18.0, 20.0, 22.0):
        for lo in (0.30, 0.50):
            go(f"t{t}_lo{lo}", t, lo, msig, mfs)
    for t in (15.0, 18.0, 20.0):
        go(f"t{t}_lo0.3_s1", t, 0.30, sh(msig, 1), sh(mfs, 1))
        go(f"t{t}_lo0.3_s1_c25", t, 0.30, sh(msig, 1), sh(mfs, 1), "c1", 0.0025)
    out["res"] = res
    out["spy"] = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    out["note"] = "🎚 위험 선택지 — 수익 개선 아님 · 위 한도 1.0(레버리지 없음) · ETF 만(생존 편향 없음) · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
