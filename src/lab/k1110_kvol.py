"""🌙 11/10 밤 연구 #30 — 🎚️ 킥 칸 「자기 흔들림」 맞추기 (킥 돌파 칸 스스로의 실현 변동성으로 칸 크기 조절)
  왜: Barroso·Santa-Clara 2015 「Momentum Has Its Moments」(J. Financial Economics 116(1)) https://doi.org/10.1016/j.jfineco.2014.11.010
      — 모멘텀 자체 변동성은 예측 가능하고, 그것으로 크기를 맞추면 붕괴가 거의 사라짐.
      11/08 밤(#27): 시장 국면(24개월 하락)으로는 붕괴 날이 너무 드물어 못 잡음 → 칸 스스로의 흔들림으로.
  바꾸는 것(킥 칸 크기만 — 신호·출구 −5·+15·15일 그대로):
    배수 s = min(상한, 목표 ÷ 킥 칸 지난 L일 실현 변동성(연))  · 전날 종가까지로 계산, 매월 첫날·국면 바뀐 날 다시 맞출 때 적용
    킥 칸 = 19% × s · s<1 이면 덜어낸 돈 dest = base(기본 칸)/cash(BIL) · s>1 이면 기본 칸에서 떼어 옴
    L 63·126·252 × 목표 10·15·20·25% × 상한 1.0·1.5 × dest base·cash = 48조합
  무리 2개: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향)
  앞 2008-07~2016 샤프로 무리마다 고르고 2017~ 시험 · 흔들기 = L·목표 ×0.8/×1.2 · 상한 반대 · dest 반대 · 회전율 × 0.1%
→ market/lab/k1110_kvol.json
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

OUT = Path("market/lab/k1110_kvol.json")
SIZE = 0.19
LS = [63, 126, 252]
TGTS = [10.0, 15.0, 20.0, 25.0]
CAPS = [1.0, 1.5]
DESTS = ["base", "cash"]


def scale_of(rk, L, tgt, cap):
    rv = rk.rolling(L, min_periods=max(20, L // 2)).std() * math.sqrt(252) * 100
    s = (tgt / rv).clip(upper=cap)
    return s.fillna(1.0).clip(lower=0.0)


def mix_scale(rb, tb, rk, tk, bil, reg, scale, dest):
    """기본·킥·(현금) 섞기 — 국면·배수는 전날 값 (다음 날부터) · 다시 맞추기 = 매월 첫날·국면 바뀐 날"""
    regv = reg.reindex(rb.index).fillna(False).shift(1).fillna(False)
    sv = scale.reindex(rb.index).shift(1).fillna(1.0)

    def tgt(s):
        k = SIZE * s
        if s >= 1.0 or dest == "base":
            return 1 - k, k, 0.0
        return 1 - SIZE, k, SIZE - k
    B, K, X = tgt(float(sv.iloc[0]))
    navs, turns, ks = [], [], []
    prev_m, prev_reg = rb.index[0].month, regv.iloc[0]
    for k, d in enumerate(rb.index):
        B *= 1 + rb.iloc[k]; K *= 1 + rk.iloc[k]; X *= 1 + bil.iloc[k]
        T = B + K + X
        tv = (B / T) * tb.iloc[k] + (K / T) * tk.iloc[k]
        g = regv.iloc[k]
        if d.month != prev_m or g != prev_reg:
            tb_, tk_, tx_ = tgt(float(sv.iloc[k]))
            rv = (abs(B / T - tb_) + abs(K / T - tk_) + abs(X / T - tx_)) / 2
            tv += rv
            T *= 1 - rv * COST
            B, K, X = T * tb_, T * tk_, T * tx_
        prev_m, prev_reg = d.month, g
        navs.append(B + K + X); turns.append(tv); ks.append(K / (B + K + X))
    return pd.Series(navs, index=rb.index), pd.Series(turns, index=rb.index), pd.Series(ks, index=rb.index)


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

    # 진단: 킥 칸 변동성이 앞날 변동성·손실을 예측하나 (126일 변동성 상위 1/3 날 vs 나머지, 다음 21일)
    diag = {}
    for fam in PRE:
        rk = KS[fam][0]
        rv = rk.rolling(126, min_periods=63).std() * math.sqrt(252) * 100
        fwd_v = rk[::-1].rolling(21).std()[::-1].shift(-1) * math.sqrt(252) * 100
        fwd_r = (1 + rk).rolling(21).apply(np.prod, raw=True).shift(-21) - 1
        row = {}
        for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
            m = (rv.index >= a) & (rv.index <= b) & rv.notna() & fwd_v.notna() & fwd_r.notna()
            x, fv, fr = rv[m], fwd_v[m], fwd_r[m]
            q = x.quantile(2 / 3)
            hi = x > q
            row[nm] = {"vol_now_mid": round(float(x.median()), 1),
                       "corr_now_fwdvol": round(float(x.corr(fv)), 2),
                       "fwd21_ret_hi": round(float(fr[hi].mean()) * 100, 2), "fwd21_ret_lo": round(float(fr[~hi].mean()) * 100, 2),
                       "fwd21_vol_hi": round(float(fv[hi].mean()), 1), "fwd21_vol_lo": round(float(fv[~hi].mean()), 1)}
        diag[fam] = row
        print("진단", fam, row, flush=True)

    SC = {}

    def run(fam, L, t, cap, dest):
        rk, tk = KS[fam]
        if L is None:
            s = pd.Series(1.0, index=idx)
        else:
            key = (fam, L, t, cap)
            if key not in SC:
                SC[key] = scale_of(rk, L, t, cap)
            s = SC[key]
        nav, td, kw = mix_scale(rb, tb, rk, tk, bil, reg, s, dest)
        o = {"fam": fam, "L": L, "tgt": t, "cap": cap, "dest": dest,
             "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        mo = (kw.index >= pd.Timestamp(OOS_START))
        o["oos_kick_w_avg"] = round(float(kw[mo].mean()) * 100, 1)
        return o

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        cur = run(fam, None, None, None, "base")
        grid = []
        for L in LS:
            for t in TGTS:
                for cap in CAPS:
                    for de in DESTS:
                        g = run(fam, L, t, cap, de)
                        grid.append(g)
                        print(fam, L, t, cap, de, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos_kick_w_avg"], flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        for k in (0.8, 1.2):
            L2 = int(round(best["L"] * k))
            g = run(fam, L2, best["tgt"], best["cap"], best["dest"]); g["what"] = f"L {L2}일"; shake.append(g)
        for k in (0.8, 1.2):
            t2 = round(best["tgt"] * k, 1)
            g = run(fam, best["L"], t2, best["cap"], best["dest"]); g["what"] = f"목표 {t2}%"; shake.append(g)
        g = run(fam, best["L"], best["tgt"], 1.5 if best["cap"] == 1.0 else 1.0, best["dest"]); g["what"] = f"상한 {g['cap']}"; shake.append(g)
        g = run(fam, best["L"], best["tgt"], best["cap"], "cash" if best["dest"] == "base" else "base")
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
        by.update({f"tgt_{x}": avg("tgt", x) for x in TGTS})
        by.update({f"cap_{x}": avg("cap", x) for x in CAPS})
        by.update({f"dest_{x}": avg("dest", x) for x in DESTS})
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"L": g["L"], "tgt": g["tgt"], "cap": g["cap"], "dest": g["dest"], "is_sh": g["is"]["sharpe"],
                                "is_cagr": g["is"]["cagr"], "is_mdd": g["is"]["mdd"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"), "oos_kick_w": g["oos_kick_w_avg"]} for g in grid]}
        print(fam, "고른", best["L"], best["tgt"], best["cap"], best["dest"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "diag": diag, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "배수 = min(상한, 목표 ÷ 킥 칸 지난 L일 실현 변동성) 전날 값, 매월 첫날·국면 바뀐 날 적용 · dest = 덜어낸 돈 base/cash · "
                   "diag = 킥 칸 126일 변동성 상위 1/3 날 vs 나머지의 다음 21일 수익·변동성 · 출구 −5·+15·15일 그대로 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
