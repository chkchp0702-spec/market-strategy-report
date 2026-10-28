"""📈 10/28 14시 — k1028_rebalflow 결과(✅ 숫자) 의심 점검: 정말 「리밸런싱 흐름」인가, 달력·채권 강세·위험 늘리기인가
  ① 맞대기를 방향별로(주식 넘침 → 채권 쪽 / 주식 모자람 → 주식 쪽) · 앞·뒤·2002-07~2008-06(더 앞, 표본 밖)·2023~
  ② 대조군: 쏠림과 상관없이 「마지막 5일 늘 채권 쪽」 / 「늘 주식 쪽」 / 신호 방향 뒤집기
  ③ 달 마지막 날(달력 효과 날)을 빼고 2~5번째 날만
  ④ 해마다 맞대기 손익(몇 해가 플러스인지)
  ⑤ 💼 위에: 고른 것(cal K5 th0.5% f0.6 TLT sym) 을 해마다 + 마지막 날 뺀 판
→ market/lab/k1028_rebalflow2.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.kick_ideas_bt import ydl

OUT = Path("market/lab/k1028_rebalflow2.json")


def make(C, K=5, th=0.005, skip_last=0, mode="sig"):
    S = C["SPY"].pct_change().fillna(0.0); B = C["IEF"].pct_change().fillna(0.0)
    idx = C.index
    mon = pd.Series(idx.month, index=idx)
    rfe = mon.groupby((mon != mon.shift()).cumsum()).cumcount(ascending=False)
    win = (rfe < K) & (rfe >= skip_last)
    drift = pd.Series(0.0, index=idx); ws = wb = 1
    for i, d in enumerate(idx):
        if i == 0 or idx[i - 1].month != d.month:
            ws, wb = 0.6, 0.4
        ws *= 1 + S.iloc[i]; wb *= 1 + B.iloc[i]
        drift.iloc[i] = ws / (ws + wb) - 0.6
    prev = drift.shift(1).fillna(0.0)
    out = pd.Series(0.0, index=idx)
    if mode == "sig":
        out[win & (prev > th)] = 1.0; out[win & (prev < -th)] = -1.0
    elif mode == "flip":
        out[win & (prev > th)] = -1.0; out[win & (prev < -th)] = 1.0
    elif mode == "always_bond":
        out[win] = 1.0
    elif mode == "always_stock":
        out[win] = -1.0
    return out


def edge(C, sig, a, b, bond="IEF", only=None):
    r = (C["SPY"].pct_change() - C[bond].pct_change()).fillna(0.0)
    m = (sig.index >= a) & (sig.index <= b) & (sig != 0)
    if only is not None:
        m &= (sig == only)
    x = (-sig[m] * r[m]) * 1e4
    if len(x) < 5:
        return {"n": int(len(x))}
    yrs = (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25
    return {"n": int(len(x)), "bp": round(float(x.mean()), 1), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2),
            "hit": round(float((x > 0).mean()) * 100), "yr_bp": round(float(x.sum()) / yrs)}


def main():
    px = ydl(["SPY", "IEF", "TLT"], start="2002-07-25")
    C = pd.DataFrame({k: px[k]["close"] for k in px}).dropna()
    END = str(C.index[-1].date())
    P = {"pre": ("2002-08-01", "2008-06-30"), "is": ("2008-07-01", "2016-12-31"), "oos": ("2017-01-01", END),
         "y23": ("2023-01-01", END)}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "to": END}
    V = {"sig": make(C), "sig_skiplast": make(C, skip_last=1), "flip": make(C, mode="flip"),
         "always_bond": make(C, mode="always_bond"), "always_stock": make(C, mode="always_stock"),
         "sig_th1.0": make(C, th=0.01)}
    res = {}
    for nm, sg in V.items():
        res[nm] = {}
        for p, (a, b) in P.items():
            res[nm][p] = {"all": edge(C, sg, a, b), "TLT": edge(C, sg, a, b, "TLT")}
            if nm.startswith("sig"):
                res[nm][p]["dir+1_sellstock"] = edge(C, sg, a, b, only=1.0)
                res[nm][p]["dir-1_buystock"] = edge(C, sg, a, b, only=-1.0)
        print(nm, json.dumps(res[nm], ensure_ascii=False), flush=True)
    out["edge"] = res
    # 해마다
    r = (C["SPY"].pct_change() - C["IEF"].pct_change()).fillna(0.0)
    yr = {}
    for nm in ("sig", "sig_skiplast", "always_bond", "always_stock"):
        x = (-V[nm] * r) * 1e4
        g = x.groupby(x.index.year).sum().round(0)
        yr[nm] = {int(k): float(v) for k, v in g.items()}
        pos = int((g > 0).sum())
        print("YR", nm, pos, "/", len(g), yr[nm], flush=True)
        yr[nm + "_pos"] = f"{pos}/{len(g)}"
    out["yearly_bp"] = yr
    # 방향별로 SPY·채권 각각(누가 움직이나)
    sg = V["sig"]
    for p, (a, b) in P.items():
        m = (sg.index >= a) & (sg.index <= b)
        o = {}
        for dval, nm in ((1.0, "sellstock"), (-1.0, "buystock")):
            mm = m & (sg == dval)
            o[nm] = {"spy_bp": round(float(C["SPY"].pct_change()[mm].mean() * 1e4), 1),
                     "ief_bp": round(float(C["IEF"].pct_change()[mm].mean() * 1e4), 1),
                     "tlt_bp": round(float(C["TLT"].pct_change()[mm].mean() * 1e4), 1)}
        o["all_days_spy_bp"] = round(float(C["SPY"].pct_change()[m].mean() * 1e4), 1)
        out.setdefault("legs", {})[p] = o
        print("LEGS", p, o, flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
