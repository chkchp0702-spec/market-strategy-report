"""📈 11/5 16시 2번 — 🎚 🎯 위험 선택지 메뉴(이번 주 첫 메뉴): 목표 변동성 18·20·22(지금)·24·26 × 아래 한도 0.6·0.7(지금)·0.8
  재는 자 = 지금 20일 실현 변동성 그대로 · 레버리지 없음(위 한도 1.0) · 비용 0.1% · 앞 2008-07~2016 / 뒤 2017~
  수익 개선이 아니라 「얼마나 흔들릴지」 고르는 표 — 판정 없음
→ market/lab/k1105_riskmenu.json
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

OUT = Path("market/lab/k1105_riskmenu.json")
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
    rv = r.rolling(20).std() * A
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END, "menu": {}}
    QF.COST = 0.001
    for tgt in (18.0, 20.0, 22.0, 24.0, 26.0):
        for fl in (0.6, 0.7, 0.8):
            sc = (tgt / rv).clip(upper=1.0, lower=fl).fillna(1.0)
            nav, td = core_run(C, reg, idx, sc, msig, mfs, G_CONC, RD_CONC)
            o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
            out["menu"][f"t{int(tgt)}_f{fl}"] = o
            print(tgt, fl, o["is"]["cagr"], o["is"]["vol"], o["is"]["mdd"], "|", o["oos"]["cagr"], o["oos"]["vol"], o["oos"]["mdd"], o["oos"]["sharpe"], flush=True)
    out["note"] = "지금 🎯 = t22_f0.7 · 위험 크기 선택 표(레버리지 아님) · ETF·지수만 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
