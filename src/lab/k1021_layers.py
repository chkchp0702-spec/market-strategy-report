"""📈 10/21 11시 수익률 전략 검증 — 방어 두 겹 · 덜어내는 순서 · 덜어낸 몫 주차장
  지금: 국면(200일선) 꺼짐 비중 × 변동성 맞춤 배율 — 두 방어가 곱해짐.
  바꿈 후보 (판단은 그날 종가 → 다음 날부터, 비용 회전 × 0.1%, 레버리지 없음):
   once   : 주식 = 켜짐 주식 × min(국면 비율, 변동성 배율) — 같은 위험을 두 번 막지 않기
   iv     : 주식 총량은 그대로, S&P·나스닥 나누기를 20일 변동성 반비례로(덜어낼 땐 나스닥부터)
   once_iv: 둘 다
   defpark: 변동성으로 덜어낸 몫만 현금 대신 필수소비재·유틸리티·헬스케어(XLP·XLU·XLV 1/3씩)
  💼 기본(방어형 15%·한도 30%)과 🎯 집중(공격형 22%·한도 70%) 둘 다 · 2008-07~2016(앞)/2017~(뒤)
→ market/lab/k1021_layers.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg, COST

OUT = Path("market/lab/k1021_layers.json")


def run(C, reg, idx, sc, base, mode, ivw, band=0.05):
    if base == "port":
        G = {"SPY": .475, "QQQ": .475, "GLD": .05}
        Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    else:
        G = {"SPY": .5, "QQQ": .5, "GLD": 0.0}
        Rd = {"SPY": .25, "QQQ": .25, "GLD": 0.0}
    C = C.copy()
    C["DEF"] = (1 + C[["XLP", "XLU", "XLV"]].pct_change().fillna(0).mean(axis=1)).cumprod()
    keys = ["SPY", "QQQ", "GLD", "BIL", "DEF"]
    R = C[keys].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}
    g_eq = G["SPY"] + G["QQQ"]

    def tg(i):
        on = bool(regv.iloc[i])
        b = G if on else Rd
        s = float(sc.iloc[i])
        rr = (b["SPY"] + b["QQQ"]) / g_eq
        if mode in ("once", "once_iv"):
            e = g_eq * min(rr, s)
        else:
            e = (b["SPY"] + b["QQQ"]) * s
        fs = 0.5
        if mode in ("iv", "once_iv"):
            fs = float(ivw.iloc[i]) if not math.isnan(ivw.iloc[i]) else 0.5
        dpk = 0.0
        if mode == "defpark":
            dpk = (b["SPY"] + b["QQQ"]) * (1 - s)
        return {"SPY": e * fs, "QQQ": e * (1 - fs), "GLD": b["GLD"], "DEF": dpk, "BIL": 1 - e - b["GLD"] - dpk}
    w, last = None, None
    rets, turns, expo = [], [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        t = tg(i - 1)
        newm = C.index[i - 1].month != d.month
        tv = 0.0
        if newm or regv.iloc[i - 1] != regv.iloc[i - 2] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t)
            r -= tv * COST
        rets.append(r); turns.append(tv); expo.append(w["SPY"] + w["QQQ"])
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx), float(np.mean(expo))


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rs, rq = C["SPY"].pct_change(), C["QQQ"].pct_change()
    rv = (0.5 * rs + 0.5 * rq).rolling(20).std() * math.sqrt(252) * 100
    vs, vq = rs.rolling(20).std(), rq.rolling(20).std()
    ivw = (1 / vs) / (1 / vs + 1 / vq)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}, "res": {}}
    for base, tgt, floor in (("port", 15.0, 0.30), ("conc", 22.0, 0.70)):
        res = {}
        for tg_mult in (1.0, 0.8, 1.2):
            sc = (tgt * tg_mult / rv).clip(upper=1.0, lower=floor).fillna(1.0)
            for mode in ("now", "once", "iv", "once_iv", "defpark"):
                if tg_mult != 1.0 and mode not in ("now", "once", "once_iv"):
                    continue
                k = mode if tg_mult == 1.0 else f"{mode}@{tg_mult}"
                nav, td, ex = run(C, reg, idx, sc, base, mode, ivw)
                yr = {}
                for y in range(2009, idx[-1].year + 1):
                    a = nav[nav.index.year == y]
                    if len(a) > 20:
                        yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
                res[k] = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "expo": round(ex * 100, 1), "yr": yr}
                print(base, k, "IS", res[k]["is"], "| OOS", res[k]["oos"], "| expo", res[k]["expo"])
        out["res"][base] = res
    out["note"] = "방어 두 겹 한 번만 · 덜어낼 땐 나스닥부터 · 덜어낸 몫 방어 업종 주차 — 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    for base in out["res"]:
        print(base, "yr now", out["res"][base]["now"]["yr"])
        print(base, "yr once", out["res"][base]["once"]["yr"])


if __name__ == "__main__":
    main()
