"""📈 10/20 11시 수익률 전략 검증 — 「공포가 풀리는 날 덜어낸 몫 바로 돌려놓기」
  지금 변동성 맞춤: 주식 칸 × min(1, 목표 ÷ 지난 20일 실현 변동성) — 폭락 뒤 반등장에서 20일 변동성이 늦게 식어 덜어낸 채로 반등을 놓침.
  바꿈 후보 (판단은 그날 종가 → 다음 날부터, 비용 회전 × 0.1%, 레버리지 없음):
   V1 relief20: VIX 가 VIX3M 위(겁 역전)에 있다가 아래로 돌아온 날부터 20거래일 동안 배율 1 (다시 역전되면 끝)
   V2 contango: VIX < VIX3M 인 날은 배율 1, 역전된 날만 실현 변동성 배율
   V3 implied : 배율 = min(1, 목표 ÷ VIX3M) (실현 대신 3개월 내재 변동성)
   V4 relief10: V1 을 10거래일로
  💼 기본(방어형 15%·한도 30%)과 🎯 집중(공격형 22%·한도 70%) 둘 다 · 2008-07~2016(앞)/2017~(뒤)
→ market/lab/k1020_relief.json
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
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg, COST

OUT = Path("market/lab/k1020_relief.json")


def run(C, reg, idx, sc, base="port", band=0.05):
    if base == "port":
        G = {"SPY": .475, "QQQ": .475, "GLD": .05, "BIL": 0.0}
        Rd = {"SPY": .315, "QQQ": .315, "GLD": .11, "BIL": .26}
    else:
        G = {"SPY": .5, "QQQ": .5, "GLD": 0.0, "BIL": 0.0}
        Rd = {"SPY": .25, "QQQ": .25, "GLD": 0.0, "BIL": .5}
    R = C[list(G)].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i):
        b = G if regv.iloc[i] else Rd
        s = float(sc.iloc[i])
        e = (b["SPY"] + b["QQQ"]) * s
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": b["GLD"], "BIL": 1 - e - b["GLD"]}
    w, last_eq = None, None
    rets, turns, expo = [], [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1); last_eq = w["SPY"] + w["QQQ"]
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        t = tg(i - 1)
        newm = C.index[i - 1].month != d.month
        tv = 0.0
        if newm or regv.iloc[i - 1] != regv.iloc[i - 2] or abs(t["SPY"] + t["QQQ"] - last_eq) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last_eq = t["SPY"] + t["QQQ"]
            r -= tv * COST
        rets.append(r); turns.append(tv); expo.append(w["SPY"] + w["QQQ"])
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx), float(np.mean(expo))


def main():
    C = load()
    vx = yf.download(["^VIX", "^VIX3M"], start="2006-01-01", interval="1d", auto_adjust=False, progress=False)["Close"]
    vx = vx.reindex(C.index).ffill(limit=5)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    inv = (vx["^VIX"] > vx["^VIX3M"]).fillna(False)
    relief_day = (~inv) & inv.shift(1).fillna(False)

    def relief(n):
        on = np.zeros(len(C), bool); k = 0
        for i in range(len(C)):
            if relief_day.iloc[i]:
                k = n
            if inv.iloc[i]:
                k = 0
            on[i] = k > 0
            k = max(0, k - 1)
        return pd.Series(on, index=C.index)
    rel20, rel10 = relief(20), relief(10)
    n_relief = {"is": int(relief_day[(relief_day.index >= START) & (relief_day.index <= IS_END)].sum()),
                "oos": int(relief_day[relief_day.index >= OOS_START].sum())}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_relief": n_relief, "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}, "res": {}}
    for base, tgt, floor in (("port", 15.0, 0.30), ("conc", 22.0, 0.70)):
        sc0 = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        variants = {
            "now": sc0,
            "relief20": sc0.where(~rel20, 1.0),
            "relief10": sc0.where(~rel10, 1.0),
            "contango": sc0.where(inv, 1.0),
            "implied": (tgt / vx["^VIX3M"]).clip(upper=1.0, lower=floor).fillna(1.0),
            "novol": pd.Series(1.0, index=C.index),
        }
        res = {}
        for k, sc in variants.items():
            nav, td, ex = run(C, reg, idx, sc, base)
            yr = {}
            for y in range(2009, idx[-1].year + 1):
                a = nav[nav.index.year == y]
                if len(a) > 20:
                    yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
            res[k] = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "expo": round(ex * 100, 1), "yr": yr}
            print(base, k, "IS", res[k]["is"], "| OOS", res[k]["oos"], "| expo", res[k]["expo"])
        out["res"][base] = res
    out["note"] = "변동성 맞춤 + 겁 풀림(VIX<VIX3M 복귀) 뒤 덜어낸 몫 돌려놓기 — 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("n_relief", n_relief)
    for base in out["res"]:
        print(base, "yr now", out["res"][base]["now"]["yr"])
        print(base, "yr rel20", out["res"][base]["relief20"]["yr"])


if __name__ == "__main__":
    main()
