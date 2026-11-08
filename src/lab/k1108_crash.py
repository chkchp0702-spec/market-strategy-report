"""🌙 11/08 밤 연구 #27 — 💥 모멘텀 붕괴 막기 (하락장 뒤 출렁이는 구간에 킥 돌파 칸 줄이기)
  왜: Daniel·Moskowitz 2016 「Momentum Crashes」(J. Financial Economics 122(2)) https://doi.org/10.1016/j.jfineco.2015.12.002
      — 모멘텀 손실은 시장이 오래 내린 뒤(지난 24개월 −) 변동성이 큰 때, 급반등하며 몰림(2009·2020 같은 때).
  바꾸는 것(킥 칸 크기만 — 신호·출구 −5·+15·15일 그대로):
    「위험 구간」 = S&P 지난 L일 수익 < 0  AND  (S&P 63일 실현 변동성 > v%  — v 없음이면 이 조건 끔)  · 전날 종가로 판단, 다음 날부터
    위험 구간에는 킥 칸 19% × scale(0·0.5) 로 줄이고, 덜어낸 돈은 dest = base(💼 기본 칸) / cash(현금 BIL)
    L 252·504 × v 없음·20·25·30 × scale 0·0.5 × dest base·cash = 32조합
  무리 2개: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향)
  틀: C안 뼈대 × 변동성 맞춤 + 킥 칸 19%·자리 5 · 매월 첫날·국면·위험 구간 바뀐 날 다시 맞춤 · 회전율 × 0.1%
  앞 2008-07~2016 샤프로 무리마다 고르고 2017~ 시험 · 흔들기 = L·v ×0.8/×1.2 · scale 옆값 · dest 반대
→ market/lab/k1108_crash.json
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
from k1011_size import seg, UNIV, COST
from k1013_trend import base_vol
from k1019_cupbrk import STK
from k1030_slip import load_ohlc
from k1105_resmom import prep, kick

OUT = Path("market/lab/k1108_crash.json")
SIZE = 0.19
LS = [252, 504]
VS = [None, 20.0, 25.0, 30.0]
SCALES = [0.0, 0.5]
DESTS = ["base", "cash"]


def state_of(C, idx, L, v):
    spy = C["SPY"]
    bear = spy / spy.shift(L) - 1 < 0
    st = bear
    if v is not None:
        rv = spy.pct_change().rolling(63).std() * math.sqrt(252) * 100
        st = st & (rv > v)
    return st.fillna(False).reindex(idx).fillna(False).astype(bool)


def mix_dyn(rb, tb, rk, tk, bil, reg, state, scale, dest):
    """기본·킥·(현금) 섞기 — 국면·위험 구간은 전날 값으로 (다음 날부터)"""
    regv = reg.reindex(rb.index).fillna(False).shift(1).fillna(False)
    stv = state.reindex(rb.index).fillna(False).shift(1).fillna(False)

    def tgt(on):
        k = SIZE * (scale if on else 1.0)
        cut = SIZE - k
        if dest == "base":
            return 1 - k, k, 0.0
        return 1 - SIZE, k, cut
    b0, k0, x0 = tgt(stv.iloc[0])
    B, K, X = b0, k0, x0
    navs, turns = [], []
    prev_m, prev_reg, prev_st = rb.index[0].month, regv.iloc[0], stv.iloc[0]
    for k, d in enumerate(rb.index):
        B *= 1 + rb.iloc[k]; K *= 1 + rk.iloc[k]; X *= 1 + bil.iloc[k]
        T = B + K + X
        tv = (B / T) * tb.iloc[k] + (K / T) * tk.iloc[k]
        g, s = regv.iloc[k], stv.iloc[k]
        if d.month != prev_m or g != prev_reg or s != prev_st:
            tb_, tk_, tx_ = tgt(s)
            rv = (abs(B / T - tb_) + abs(K / T - tk_) + abs(X / T - tx_)) / 2
            tv += rv
            T *= 1 - rv * COST
            B, K, X = T * tb_, T * tk_, T * tx_
        prev_m, prev_reg, prev_st = d.month, g, s
        navs.append(B + K + X); turns.append(tv)
    return pd.Series(navs, index=rb.index), pd.Series(turns, index=rb.index)


def days_on(state, a, b):
    s = state[(state.index >= a) & (state.index <= b)]
    return int(s.sum()), int(len(s))


def main():
    C, _, _ = load_ohlc()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    bil = C["BIL"].pct_change().fillna(0.0).reindex(idx).fillna(0.0)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    PRE = {"E": prep(C, UNIV), "S": prep(C, list(STK))}
    print("무리 크기", {k: len(v["U"]) for k, v in PRE.items()}, flush=True)
    KS = {}
    for fam in PRE:
        rk, tk, _, _ = kick(C, idx, PRE[fam], rank="rel", cap=None, lb=63)
        KS[fam] = (rk, tk)
    ST = {}

    def st(L, v):
        if (L, v) not in ST:
            ST[(L, v)] = state_of(C, idx, L, v)
        return ST[(L, v)]

    # 위험 구간에서 킥 칸 − 기본 칸 하루 평균 (bp) — 정말 붕괴가 몰리나
    diag = {}
    for L in LS:
        for v in VS:
            s = st(L, v).shift(1).fillna(False).astype(bool)
            row = {"is_days": days_on(st(L, v), START, IS_END), "oos_days": days_on(st(L, v), OOS_START, END)}
            for fam in PRE:
                dd = KS[fam][0] - rb
                for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
                    m = (dd.index >= a) & (dd.index <= b)
                    on, off = dd[m & s.values], dd[m & ~s.values]
                    row[f"{fam}_{nm}_bp_on"] = round(float(on.mean()) * 1e4, 2) if len(on) else None
                    row[f"{fam}_{nm}_bp_off"] = round(float(off.mean()) * 1e4, 2) if len(off) else None
            diag[f"L{L}_v{v}"] = row
            print("진단", L, v, row, flush=True)

    def run(fam, L, v, scale, dest):
        rk, tk = KS[fam]
        if L is None:
            state = pd.Series(False, index=idx)
        else:
            state = st(L, v)
        nav, td = mix_dyn(rb, tb, rk, tk, bil, reg, state, scale, dest)
        return {"fam": fam, "L": L, "v": v, "scale": scale, "dest": dest,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        cur = run(fam, None, None, 1.0, "base")
        grid = []
        for L in LS:
            for v in VS:
                for sc in SCALES:
                    for de in DESTS:
                        g = run(fam, L, v, sc, de)
                        grid.append(g)
                        print(fam, L, v, sc, de, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        for k in (0.8, 1.2):
            L2 = int(round(best["L"] * k))
            g = run(fam, L2, best["v"], best["scale"], best["dest"]); g["what"] = f"L {L2}일"; shake.append(g)
        if best["v"] is not None:
            for k in (0.8, 1.2):
                v2 = round(best["v"] * k, 1)
                g = run(fam, best["L"], v2, best["scale"], best["dest"]); g["what"] = f"변동성 {v2}%"; shake.append(g)
        sc2 = [0.2] if best["scale"] == 0.0 else [0.4, 0.6]
        for s2 in sc2:
            g = run(fam, best["L"], best["v"], s2, best["dest"]); g["what"] = f"줄이는 배수 {s2}"; shake.append(g)
        g = run(fam, best["L"], best["v"], best["scale"], "cash" if best["dest"] == "base" else "base")
        g["what"] = "덜어낸 돈 " + g["dest"]; shake.append(g)

        def ok(o):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}
        chk = ok(best["oos"])
        shake_ok = all(all(ok(s["oos"]).values()) for s in shake)
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))

        def avg(key, val):
            xs = [g for g in grid if g[key] == val]
            return {"n": len(xs), "oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in xs])), 3),
                    "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in xs])), 2),
                    "oos_mdd": round(float(np.mean([g["oos"]["mdd"] for g in xs])), 2),
                    "is_sh": round(float(np.mean([g["is"]["sharpe"] for g in xs])), 3)}
        by = {f"L_{x}": avg("L", x) for x in LS}
        by.update({f"v_{x}": avg("v", x) for x in VS})
        by.update({f"scale_{x}": avg("scale", x) for x in SCALES})
        by.update({f"dest_{x}": avg("dest", x) for x in DESTS})
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"L": g["L"], "v": g["v"], "scale": g["scale"], "dest": g["dest"], "is_sh": g["is"]["sharpe"],
                                "is_cagr": g["is"]["cagr"], "is_mdd": g["is"]["mdd"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn")} for g in grid]}
        print(fam, "고른", best["L"], best["v"], best["scale"], best["dest"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "diag": diag, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "위험 구간 = S&P 지난 L일 수익<0 AND 63일 변동성>v% (전날 종가 판단) · scale = 위험 구간 킥 칸 배수 · dest = 덜어낸 돈 base(기본 칸)/cash(BIL) · "
                   "diag = 위험 구간 안/밖 「킥 칸 − 기본 칸」 하루 평균 bp · 출구 −5·+15·15일 그대로 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
