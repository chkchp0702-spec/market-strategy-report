"""📈 10/29 16시 — 🌍 「글로벌 주식 펀드가 월말에 억지로 사고팔 쪽」 (미국 ↔ 미국 밖 주식)
  발상: 미국 연기금·글로벌(ACWI 형) 펀드는 월말·분기말에 「주식 ↔ 채권」만이 아니라 「미국 주식 ↔ 미국 밖 주식」도
        정해진 비중(대략 60/40)으로 되돌린다(Gulfnews·Investing.com 「연기금 리밸런싱이 국채와 국제 주식을 띄울 수 있다」).
        → 그달 미국(SPY)이 미국 밖(EFA)보다 많이 앞섰으면, 마지막 며칠 동안 미국 팔고 미국 밖 살 차례.
  적용 중인 🔄 월말 흐름(SPY↔IEF, Q10/28-2)과 다른 짝(주식 안의 나라 짝) — 그 위에 얹어 잰다.
  ① 맞대기: 마지막 K 거래일, 그저께까지 쏠림(60/40 SPY·X) > th → (X − SPY) 하루 평균 bp · 반대 쏠림 · 창 밖 대조군
  ② 💼 위에 얹기: 기준점 = 지금 실제 💼(월말 흐름 TLT 판 포함) · 신호 + 인 날 💼 주식 칸 g 만큼 X 로 (하루 늦은 체결)
     격자 X∈{EFA,EEM,VEU} × K∈{3,5} × th∈{0.5,1.0%p} × g∈{0.3,0.6} → 앞 2008-07~16 에서 샤프 차 1등 → 뒤 2017~ 시험 · ±20% 흔들기
  ETF 만 써서 생존 편향 없음 · 회전 × 0.1%
→ market/lab/k1029_intlflow.json
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
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg, COST
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_rebalflow4 import sig_lag

OUT = Path("market/lab/k1029_intlflow.json")
XS = ["EFA", "EEM", "VEU"]


def sig_x(C, X, K=5, th=0.005, lag=2, wus=0.6):
    S = C["SPY"].pct_change().fillna(0.0); B = C[X].pct_change().fillna(0.0)
    idx = C.index
    mon = pd.Series(idx.month, index=idx)
    rfe = mon.groupby((mon != mon.shift()).cumsum()).cumcount(ascending=False)
    win = rfe < K
    drift = pd.Series(0.0, index=idx); ws = wb = 1
    for i, d in enumerate(idx):
        if i == 0 or idx[i - 1].month != d.month:
            ws, wb = wus, 1 - wus
        ws *= 1 + S.iloc[i]; wb *= 1 + B.iloc[i]
        drift.iloc[i] = ws / (ws + wb) - wus
    prev = drift.shift(lag).fillna(0.0)
    out = pd.Series(0.0, index=idx)
    out[win & (prev > th)] = 1.0; out[win & (prev < -th)] = -1.0
    return out, win


def edge(C, X, sig, win, a, b):
    r = (C[X].pct_change() - C["SPY"].pct_change()).fillna(0.0)
    m0 = (sig.index >= a) & (sig.index <= b)
    o = {}
    for nm, m in {"up": m0 & (sig > 0), "dn": m0 & (sig < 0), "win_all": m0 & win, "out": m0 & ~win}.items():
        x = r[m] * 1e4
        if nm == "dn":
            x = -x
        o[nm] = {"n": int(len(x))} if len(x) < 5 else {"n": int(len(x)), "bp": round(float(x.mean()), 1),
                                                       "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2)}
    return o


def core_run3(C, reg, idx, sc, sig, fser, sig2, g, X, bond="TLT", band=0.05):
    G = {"SPY": .475, "QQQ": .475, "GLD": .05}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    keys = ["SPY", "QQQ", "GLD", "TRD", "BND", "XX"]
    Cx = C.copy(); Cx["BND"] = C[bond]; Cx["XX"] = C[X] if X else C["SPY"]
    R = Cx[keys].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i, s_now, f, s2):
        b = G if bool(regv.iloc[i]) else Rd
        s = float(sc.iloc[i])
        e = (b["SPY"] + b["QQQ"]) * s
        gl = b["GLD"]; trd = 1 - e - gl; bnd = 0.0; xx = 0.0
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and f > 0:
            mv = (gl + trd) * f
            e += mv; gl *= (1 - f); trd *= (1 - f)
        if s2 > 0 and g > 0:
            xx = e * g; e -= xx
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": gl, "TRD": trd, "BND": bnd, "XX": xx}
    w, last, lsig, lsig2 = None, None, 0.0, 0.0
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1, 0.0, 0.0, 0.0); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        j = i + 1
        snext = float(sig.iloc[j]) if j < len(sig) else 0.0
        fn = float(fser.iloc[j]) if j < len(fser) else 0.0
        s2n = float(sig2.iloc[j]) if j < len(sig2) else 0.0
        t = tg(i, snext, fn, s2n)
        newm = j < len(C.index) and C.index[j].month != d.month
        tv = 0.0
        if newm or snext != lsig or s2n != lsig2 or regv.iloc[i] != regv.iloc[i - 1] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t)
            r -= tv * COST
        lsig = snext; lsig2 = s2n
        rets.append(r); turns.append(tv)
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + XS + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for t in ["TLT"] + XS:
        if t in px:
            C[t] = px[t]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    sc = (15.0 / rv).clip(upper=1.0, lower=0.30).fillna(1.0)
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "to": END,
           "has": [x for x in XS if x in C.columns]}
    xs = out["has"]

    # ① 맞대기
    out["edge"] = {}
    for X in xs:
        for K in (3, 5):
            for th in (0.005, 0.01):
                sg, win = sig_x(C, X, K, th)
                key = f"{X}_K{K}_th{th}"
                out["edge"][key] = {"is": edge(C, X, sg, win, START, IS_END), "oos": edge(C, X, sg, win, OOS_START, END),
                                    "pre": edge(C, X, sg, win, "2003-01-01", "2008-06-30")}
                print("edge", key, out["edge"][key]["is"]["up"], out["edge"][key]["oos"]["up"], flush=True)

    # ② 💼 위에 얹기
    s1 = sig_lag(C, 5, 0.005, 2)
    f1 = pd.Series(0.6, index=C.index); f1[s1 == 0] = 0.0
    zero = pd.Series(0.0, index=C.index)

    def res(nav, td):
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        d = nav.pct_change().fillna(0)
        o["y"] = {y: round(((1 + d[d.index.year == y]).prod() - 1) * 100, 2) for y in range(2008, idx[-1].year + 1)}
        return o
    nb, tb = core_run3(C, reg, idx, sc, s1, f1, zero, 0.0, None)
    B = res(nb, tb)
    out["B"] = {k: B[k] for k in ("is", "oos")}
    print("B", out["B"], flush=True)

    def dlt(b):
        r = {p: {"cagr": round(b[p]["cagr"] - B[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - B[p]["mdd"], 2),
                 "sharpe": round(b[p]["sharpe"] - B[p]["sharpe"], 2), "turn": b[p].get("turn")} for p in ("is", "oos")}
        r["y"] = {y: round(b["y"][y] - B["y"][y], 2) for y in B["y"] if y >= 2017}
        return r

    def run(X, K, th, g, wus=0.6):
        sg, _ = sig_x(C, X, K, th, 2, wus)
        sg2 = sg.clip(lower=0.0)
        n, t = core_run3(C, reg, idx, sc, s1, f1, sg2, g, X)
        return dlt(res(n, t))
    grid = {}
    for X in xs:
        for K in (3, 5):
            for th in (0.005, 0.01):
                for g in (0.3, 0.6):
                    k = f"{X}_K{K}_th{th}_g{g}"
                    grid[k] = run(X, K, th, g)
                    print(k, grid[k]["is"], grid[k]["oos"], flush=True)
    out["grid"] = grid
    best = max(grid, key=lambda k: (grid[k]["is"]["sharpe"], grid[k]["is"]["cagr"]))
    out["pick"] = best
    out["grid_oos_pos"] = f"{sum(1 for k in grid if grid[k]['oos']['cagr'] > 0)}/{len(grid)}"
    out["grid_both_pos"] = f"{sum(1 for k in grid if grid[k]['oos']['cagr'] > 0 and grid[k]['is']['cagr'] > 0)}/{len(grid)}"
    X, Ks, ths, gs = best.split("_")
    K = int(Ks[1:]); th = float(ths[2:]); g = float(gs[1:])
    wig = {}
    for nm, kw in {"K-": dict(K=max(2, round(K * 0.8))), "K+": dict(K=round(K * 1.2) + (1 if K == 3 else 0)),
                   "th-": dict(th=th * 0.8), "th+": dict(th=th * 1.2), "g-": dict(g=g * 0.8), "g+": dict(g=g * 1.2),
                   "w55": dict(wus=0.55), "w65": dict(wus=0.65)}.items():
        a = dict(X=X, K=K, th=th, g=g); a.update(kw)
        wig[nm] = run(**a)
        print("wig", nm, wig[nm]["is"], wig[nm]["oos"], flush=True)
    out["wiggle"] = wig
    out["doc"] = __doc__
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("pick", best, grid[best], out["grid_oos_pos"], out["grid_both_pos"])


if __name__ == "__main__":
    main()
