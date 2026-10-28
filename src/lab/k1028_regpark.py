"""📈 10/28 12시 둘째 실험 — 추세 주차(Q10/28-1)가 켜진 지금, 하락 국면 「현금 26%」 칸이 아직 제 몫을 하나
  배경: 국면 현금은 10/12 ✅(그땐 덜어낸 돈 = 국채). 지금은 덜어낸 돈이 🧭 자산 추세 칸으로 가므로 위험 줄이는 장치가 겹칠 수 있음.
  B0 = 지금 실제 💼(뼈대 + 변동성 맞춤 15%/30% + 현금 → 추세 칸) · 하락 국면 S&P 31.5·나스닥 31.5·금 11·(현금 26 → 추세 칸)
  R1 국면 끔: 늘 상승 국면 뼈대(47.5·47.5·금 5) — 위험은 변동성 맞춤만
  R2 반만: 하락 국면 39.5·39.5·금 8 (현금 13 → 추세 칸)
  R3 국면 땐 주식 대신 「추세 칸」만 키우고 금은 5 그대로: 31.5·31.5·금 5·추세 32
  🎯 집중(하락 25·25) 도 R1·R2 대응으로 참고 · 흔들기 ±20%: 목표 12/18 · 한도 24/36 · 추세 80/40·120/60
→ market/lab/k1028_regpark.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg, COST
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U

OUT = Path("market/lab/k1028_regpark.json")
G_PORT = {"SPY": .475, "QQQ": .475, "GLD": .05}
RD = {"B0": {"SPY": .315, "QQQ": .315, "GLD": .11}, "R1": G_PORT, "R2": {"SPY": .395, "QQQ": .395, "GLD": .08},
      "R3": {"SPY": .315, "QQQ": .315, "GLD": .05}}
G_CONC = {"SPY": .5, "QQQ": .5, "GLD": 0.0}
RDC = {"B0": {"SPY": .25, "QQQ": .25, "GLD": 0.0}, "R1": G_CONC, "R2": {"SPY": .375, "QQQ": .375, "GLD": 0.0},
       "R3": {"SPY": .25, "QQQ": .25, "GLD": 0.0}}


def core_run(C, reg, idx, sc, G, Rd, band=0.05):
    R = C[["SPY", "QQQ", "GLD", "TRD"]].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i):
        b = G if bool(regv.iloc[i]) else Rd
        e = (b["SPY"] + b["QQQ"]) * float(sc.iloc[i])
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": b["GLD"], "TRD": 1 - e - b["GLD"]}
    w = last = None
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        t = tg(i - 1); tv = 0.0
        if C.index[i - 1].month != d.month or regv.iloc[i - 1] != regv.iloc[i - 2] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t); r -= tv * COST
        rets.append(r); turns.append(tv)
    return (1 + pd.Series(rets, index=idx)).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    TRN = {}

    def tnav(nin, nout):
        if (nin, nout) not in TRN:
            s, _, _ = trend_run(px, cdl, nin, nout, "risk", start=str(common.date()))
            TRN[(nin, nout)] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
        return TRN[(nin, nout)]

    def go(v, base="port", tgt=15.0, floor=0.30, tr=(100, 50)):
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        Cx = C.copy(); Cx["TRD"] = tnav(*tr)
        G, Rd = (G_PORT, RD[v]) if base == "port" else (G_CONC, RDC[v])
        nav, td = core_run(Cx, reg, idx, sc, G, Rd)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "red_share": round(float((~reg.reindex(idx).fillna(False)).mean()) * 100, 1),
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}
    B0 = go("B0"); out["B0"] = B0
    print("B0", B0, flush=True)
    for v in ("R1", "R2", "R3"):
        o = go(v); o["d"] = dlt(B0, o); out[v] = o
        print(v, o["d"], flush=True)
    shakes = {"tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0), "floor24": dict(floor=0.24), "floor36": dict(floor=0.36),
              "tr80_40": dict(tr=(80, 40)), "tr120_60": dict(tr=(120, 60))}
    sh = {}
    for v in ("R1", "R2", "R3"):
        sh[v] = {}
        for nm, kw in shakes.items():
            sh[v][nm] = dlt(go("B0", **kw), go(v, **kw))
        print("흔들기", v, {k: (x["is"]["cagr"], x["oos"]["cagr"], x["oos"]["mdd"]) for k, x in sh[v].items()}, flush=True)
    out["shake"] = sh
    c0 = go("B0", base="conc", tgt=22.0, floor=0.70)
    out["conc"] = {"B0": c0}
    for v in ("R1", "R2", "R3"):
        o = go(v, base="conc", tgt=22.0, floor=0.70); out["conc"][v] = {**o, "d": dlt(c0, o)}
        print("conc", v, out["conc"][v]["d"], flush=True)
    out["note"] = "B0 = 지금 실제 💼(추세 주차 포함) · 기본 칸만(킥 없음) · 국면 = conc_bt regimes A · 레버리지 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
