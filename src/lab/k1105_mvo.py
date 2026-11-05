"""📈 11/5 14시 — 🎯 뼈대를 「달마다 다시 짜는 주식·채권·금 최적 배분」으로 바꾸면? (Boyd 외 2026, arXiv 2609.07946)
  발상: Stanford Boyd 팀 「Simple Dynamic Stock/Bond/Gold Portfolios」(2006~2026) — 매달 말
        기대수익 = 자산별 일 수익의 지수가중 평균(반감기 252일) × 21, 위험 = 최근 11일 공분산,
        「기대수익 최대 · 예상 변동성 ≤ 목표 · 레버리지 없음(합 ≤1, 나머지 현금)」 → 60/40 변동성 맞춤 샤프 0.71 → 0.91.
  우리 판: 자산 묶음 3가지(SPY·QQQ·TLT·GLD / +IEF / +🧭 추세 칸 TRD) × 반감기 126·252·504 × 공분산 창 11·21·63 = 27판
           + 고정 비율 40/40/10/10 변동성 맞춤(VC) 1판 · 각 판의 목표 변동성을 이분 탐색해 앞 구간 변동성을 🎯 와 같게(같은 위험)
           + 묶음: 🎯 반 + 최적 배분 반(매일 반반)도 같은 위험으로.
  해 찾기: 5% 눈금 전수 탐색(scipy 없이) · 월말 종가까지 자료 → 이틀째 수익부터 반영(다음 날 체결) · 회전 × 0.1%
  판정: 앞 2008-07~16 ≥0 · 뒤 2017~ +1%p(🟡 +0.33) · 흔들기(반감기·창 ±20%, 눈금 10%) 뒤 플러스 · 비용 0.25% 도 봄
→ market/lab/k1105_mvo.json
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import math
import sys
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

OUT = Path("market/lab/k1105_mvo.json")
SETS = {"A4": ["SPY", "QQQ", "TLT", "GLD"], "A5": ["SPY", "QQQ", "TLT", "GLD", "IEF"], "A4T": ["SPY", "QQQ", "TLT", "GLD", "TRD"]}


def grid(n, step):
    k = int(round(1 / step))
    out = [c for c in itertools.product(range(k + 1), repeat=n) if sum(c) <= k]
    return np.array(out, dtype=float) * step


class Opt:
    """월말마다 후보 비중 전부의 (기대 초과수익, 예상 변동성)을 미리 계산 → 목표만 바꿔 바로 고름"""

    def __init__(self, R, cash, assets, hl, win, step, mdays):
        self.assets = assets
        X = R[assets]
        ex = X.sub(cash, axis=0)
        mu = ex.ewm(halflife=hl, min_periods=126).mean() * 252
        self.W = grid(len(assets), step)
        self.mdays = mdays
        self.MU, self.VOL = [], []
        for d in mdays:
            m = mu.loc[d].values
            win_df = X.loc[:d].iloc[-win:]
            S = np.cov(win_df.values.T) * 252
            if np.isnan(m).any() or np.isnan(S).any():
                self.MU.append(None); self.VOL.append(None); continue
            self.MU.append(self.W @ m)
            self.VOL.append(np.sqrt(np.einsum("ij,jk,ik->i", self.W, S, self.W)) * 100)

    def weights(self, cap):
        out = {}
        for d, mu, vol in zip(self.mdays, self.MU, self.VOL):
            if mu is None:
                continue
            ok = vol <= cap
            if not ok.any():
                out[d] = np.zeros(len(self.assets)); continue
            j = np.argmax(np.where(ok, mu, -1e9))
            out[d] = self.W[j] if mu[j] > 0 else np.zeros(len(self.assets))
        return out


def simulate(R, cash, assets, wts, idx, cost):
    """월말 d 에 정한 비중 → d 다음다음 날 수익부터(다음 날 종가 체결) · 그사이 비중은 흘러감"""
    pos_i = {d: i for i, d in enumerate(R.index)}
    eff = {}
    for d, w in wts.items():
        i = pos_i[d] + 2
        if i < len(R.index):
            eff[R.index[i]] = w
    A = R[assets].values; cs = cash.values
    w = None; rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        tv = 0.0
        if d in eff:
            nw = eff[d]
            if w is None:
                tv = nw.sum()
            else:
                tv = (np.abs(nw - w).sum() + abs((1 - nw.sum()) - (1 - w.sum()))) / 2
            w = nw.copy()
        if w is None:
            rets.append(0.0); turns.append(0.0); continue
        a = A[i]; a = np.where(np.isnan(a), 0.0, a)
        c0 = 1 - w.sum()
        r = float(w @ a + c0 * cs[i]) - tv * cost
        v = w * (1 + a); tot = v.sum() + c0 * (1 + cs[i])
        w = v / tot
        rets.append(r); turns.append(tv)
    return (1 + pd.Series(rets, index=idx)).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
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
    sigM, fsM = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    R = C[["SPY", "QQQ", "TLT", "GLD", "IEF", "TRD"]].pct_change()
    cash = cdl.reindex(C.index).ffill().fillna(0.0)

    def conc(cost=0.001, tgt=22.0):
        QF.COST = cost
        sc = (tgt / rv).clip(upper=1.0, lower=0.70).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, sigM, fsM, G_CONC, RD_CONC)
        return nav, td

    def pack(nav, td):
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    me = pd.Series(C.index, index=C.index)
    mdays = [d for d in me.groupby([C.index.year, C.index.month]).last().values if d >= pd.Timestamp("2008-03-01")]
    mdays = [pd.Timestamp(d) for d in mdays]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    BN, BT = conc()
    B = pack(BN, BT)
    out["base"] = B
    print("BASE", B["is"]["vol"], B["is"]["cagr"], B["oos"]["cagr"], flush=True)
    target_vol = B["is"]["vol"]

    def matched(make_nav, lo=4.0, hi=40.0):
        best = None
        for _ in range(8):
            m = (lo + hi) / 2; nav, td = make_nav(m); r = pack(nav, td)
            if best is None or abs(r["is"]["vol"] - target_vol) < abs(best[1]["is"]["vol"] - target_vol):
                best = (m, r, nav, td)
            if r["is"]["vol"] > target_vol:
                hi = m
            else:
                lo = m
        return best

    cache = {}

    def get_opt(st, hl, win, step=0.05):
        k = (st, hl, win, step)
        if k not in cache:
            cache[k] = Opt(R, cash, SETS[st], hl, win, step, mdays)
        return cache[k]

    def mvo_nav(st, hl, win, step=0.05, cost=0.001):
        o = get_opt(st, hl, win, step)
        return lambda cap: simulate(R, cash, SETS[st], o.weights(cap), idx, cost)

    res = {}
    for st in SETS:
        for hl in (126, 252, 504):
            for win in (11, 21, 63):
                cap, r, nav, td = matched(mvo_nav(st, hl, win))
                nm = f"{st}_h{hl}_w{win}"
                avgw = None
                res[nm] = {"cap": round(cap, 2), "d": dlt(B, r), "is": r["is"], "oos": r["oos"]}
                print(nm, round(cap, 2), res[nm]["d"], flush=True)
    # 고정 비율 변동성 맞춤 (Boyd 의 VC 비교판)
    base_w = np.array([.4, .4, .1, .1])

    def vc_nav(cap, cost=0.001):
        X = R[SETS["A4"]]
        wts = {}
        for d in mdays:
            S = np.cov(X.loc[:d].iloc[-21:].values.T) * 252
            v = math.sqrt(base_w @ S @ base_w) * 100
            wts[d] = base_w * min(1.0, cap / v) if v > 0 else base_w
        return simulate(R, cash, SETS["A4"], wts, idx, cost)
    cap, r, nav, td = matched(vc_nav)
    res["VC_40_40_10_10"] = {"cap": round(cap, 2), "d": dlt(B, r), "is": r["is"], "oos": r["oos"]}
    print("VC", res["VC_40_40_10_10"]["d"], flush=True)
    out["res"] = res

    cand = {k: v for k, v in res.items() if not k.startswith("VC")}
    pick = max(cand, key=lambda k: cand[k]["d"]["is"]["cagr"])
    out["is_pick"] = pick
    st, h, w = pick.split("_"); hl = int(h[1:]); win = int(w[1:])
    d = res[pick]["d"]
    # 연도별
    cap, r, PN, PT = matched(mvo_nav(st, hl, win))
    yr = {}
    for y in range(2008, idx[-1].year + 1):
        a = BN[BN.index.year == y]; b = PN[PN.index.year == y]
        if len(a) > 5:
            yr[str(y)] = round(float((b.iloc[-1] / b.iloc[0] - a.iloc[-1] / a.iloc[0]) * 100), 2)
    out["pick_yr"] = yr
    # 평균 비중
    o = get_opt(st, hl, win)
    W = pd.DataFrame(o.weights(cap)).T
    W.columns = SETS[st]
    out["pick_avg_w"] = {p: {c: round(float(W.loc[(W.index >= a) & (W.index <= b), c].mean()), 3) for c in W.columns}
                         for p, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()}
    out["pick_last_w"] = {c: round(float(W.iloc[-1][c]), 2) for c in W.columns}
    # 상관
    rb, rp = BN.pct_change(), PN.pct_change()
    out["corr"] = {"is": round(float(rb[:IS_END].corr(rp[:IS_END])), 3), "oos": round(float(rb[OOS_START:].corr(rp[OOS_START:])), 3)}
    # 비용 0.25%
    BN2, BT2 = conc(0.0025)
    B2 = pack(BN2, BT2)
    tv0 = target_vol; target_vol = B2["is"]["vol"]
    _, r2, _, _ = matched(lambda c: simulate(R, cash, SETS[st], o.weights(c), idx, 0.0025))
    out["cost25"] = dlt(B2, r2)
    target_vol = tv0
    # 묶음: 🎯 반 + 최적 배분 반 (같은 위험)
    def blend_nav(cap):
        n2, t2 = simulate(R, cash, SETS[st], o.weights(cap), idx, 0.001)
        rr = 0.5 * BN.pct_change().fillna(0) + 0.5 * n2.pct_change().fillna(0)
        return (1 + rr).cumprod(), 0.5 * BT + 0.5 * t2
    capb, rbl, _, _ = matched(blend_nav)
    out["blend50"] = {"cap": round(capb, 2), "d": dlt(B, rbl), "is": rbl["is"], "oos": rbl["oos"]}
    print("BLEND", out["blend50"]["d"], flush=True)
    # 흔들기
    sh = {}
    for vn, (h2, w2, s2) in {"hl-20": (int(hl * .8), win, .05), "hl+20": (int(hl * 1.2), win, .05),
                              "win-20": (hl, max(5, int(round(win * .8))), .05), "win+20": (hl, int(round(win * 1.2)), .05),
                              "step10": (hl, win, .10)}.items():
        _, rs, _, _ = matched(mvo_nav(st, h2, w2, s2))
        sh[vn] = dlt(B, rs)
        print("SHAKE", vn, sh[vn], flush=True)
    out["shake"] = sh
    j = {"pick": pick, "is": d["is"]["cagr"], "oos": d["oos"]["cagr"], "oos_mdd": d["oos"]["mdd"],
         "shake_ok": all(v["oos"]["cagr"] > 0 for v in sh.values()), "cost25_oos": out["cost25"]["oos"]["cagr"],
         "oos_pos": sum(1 for v in cand.values() if v["d"]["oos"]["cagr"] > 0), "n": len(cand),
         "is_pos": sum(1 for v in cand.values() if v["d"]["is"]["cagr"] >= 0)}
    j["verdict"] = "✅" if (j["oos"] > 1.0 and j["is"] >= 0 and j["shake_ok"]) else ("🟡" if (j["oos"] >= 0.33 and j["is"] >= 0) else "❌")
    out["judge"] = j
    print("JUDGE", j, flush=True)
    out["note"] = "기준 = 지금 🎯(22%·70%·월말 흐름·🧭 추세 칸) · 최적 배분판은 목표 변동성을 이분 탐색해 앞 구간 변동성을 🎯 와 같게 · 레버리지 없음(합 ≤1) · ETF 만 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
