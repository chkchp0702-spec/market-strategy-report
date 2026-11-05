"""🌙 11/05 밤 연구 #26 — 🧮 잔차 모멘텀 (시장 몫을 뺀 모멘텀)
  왜: Blitz·Huij·Martens 2011 「Residual Momentum」(J. Empirical Finance 18(3)) https://doi.org/10.1016/j.jempfin.2011.01.003
      — 시장 움직임(베타)을 뺀 나머지 수익 ÷ 그 흔들림으로 고르면 수익 비슷·변동성 절반, 모멘텀 붕괴 덜함.
  바꾸는 것(돌파 후보 고르는 순서·거르기만, 출구 −5·+15·15일 그대로):
    rank: rel = 지금(63일 S&P 대비 상대 강도 큰 순) / res = 잔차 점수 큰 순 / mix = 두 순위 합
    gate: 끔 / 잔차 점수 > 0 인 것만(시장 덕분에만 오른 것 빼기)
    lb  : 베타·잔차 재는 기간 63·126·252일 (그날 종가까지 판단, 체결은 다음 날)
  잔차 점수 = [기간 합(r) − β·기간 합(SPY)] ÷ (잔차 하루 흔들림 × √기간), β = 기간 cov(r,SPY)/var(SPY)
  무리 2개: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(실전에 더 가까움, 생존 편향)
  틀: C안 뼈대 × 변동성 맞춤 + 킥 칸 19%·자리 5 · 회전율 × 0.1%
  앞 2008-07~2016 샤프로 무리마다 고르고 2017~ 시험 · 흔들기 = lb ×0.8/×1.2 (+ gate 반대)
→ market/lab/k1105_resmom.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import run_mix, seg, UNIV, COST
from k1012_exits import tstat
from k1013_trend import base_vol
from k1019_cupbrk import STK
from k1030_slip import load_ohlc

OUT = Path("market/lab/k1105_resmom.json")
SIZE = 0.19
RANKS = ["rel", "res", "mix"]
CAPS = [None, 0.0]   # None = 끔 · 0.0 = 잔차 점수 > 0 만
LBS = [63, 126, 252]


def prep(Cl, U):
    U = [t for t in U if t in Cl.columns]
    P = Cl[U]
    hi = P.shift(1).rolling(252, min_periods=252).max()
    brk = (P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))
    rel = (P / P.shift(63)).sub(Cl["SPY"] / Cl["SPY"].shift(63), axis=0)
    ret = P.pct_change()
    return {"U": U, "P": P.values, "brk": brk.values, "rel": rel.values, "ret": ret,
            "m": Cl["SPY"].pct_change(), "R": ret.fillna(0.0).values, "bil": Cl["BIL"].pct_change().fillna(0.0).values, "vol": {}}


def vol_of(pre, lb):
    """잔차 점수 (Blitz·Huij·Martens 2011) — 그날 종가까지 (체결은 다음 날)"""
    if lb not in pre["vol"]:
        r = pre["ret"]
        m = pre["m"].reindex(r.index)
        mp = int(lb * 0.8)
        mm = m.rolling(lb, min_periods=mp).mean()
        vm = m.rolling(lb, min_periods=mp).var()
        rm = r.rolling(lb, min_periods=mp).mean()
        vr = r.rolling(lb, min_periods=mp).var()
        cov = r.mul(m, axis=0).rolling(lb, min_periods=mp).mean().sub(rm.mul(mm, axis=0)) * (lb / (lb - 1))
        beta = cov.div(vm, axis=0)
        ve = (vr - cov.pow(2).div(vm, axis=0)).clip(lower=1e-10)
        resid_sum = (rm - beta.mul(mm, axis=0)) * lb
        v = resid_sum / (np.sqrt(ve) * np.sqrt(lb))
        pre["vol"][lb] = (v.values, beta.values)
    return pre["vol"][lb]


def kick(C, idx, pre, rank="rel", cap=None, lb=63, stop=-0.05, take=0.15, time_d=15, time_min=0.03,
         slots=5, max_new=2, reentry=10):
    U, Pv, BRK, REL, R, bil = pre["U"], pre["P"], pre["brk"], pre["rel"], pre["R"], pre["bil"]
    V, BETA = vol_of(pre, lb)
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades, vols_in = [], [], [], []
    for d in idx:
        i = pos_i[d]
        r = cash * bil[i]
        for j, p in pos.items():
            r += p["w"] * R[i, j]
            p["w"] *= 1 + R[i, j]
        cash *= 1 + bil[i]
        tot = cash + sum(p["w"] for p in pos.values())
        cash /= tot
        for p in pos.values():
            p["w"] /= tot
        tv = 0.0
        for j in pend_out:
            if j in pos:
                p = pos.pop(j)
                trades.append((str(C.index[p["ent_i"]].date()), Pv[i, j] / p["entry"] - 1))
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(1.0 / slots, cash)
            if w <= 0 or np.isnan(Pv[i, j]):
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i}
            cash -= w; tv += w
        pend_in, pend_out = [], []
        c = tv * COST
        r -= c; cash -= c
        rets.append(r); turns.append(tv)
        for j, p in pos.items():
            if p["ent_i"] == i:
                continue
            px = Pv[i, j]
            if np.isnan(px):
                continue
            p["held"] += 1
            p["max"] = max(p["max"], px)
            g = px / p["entry"] - 1
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min):
                pend_out.append(j)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = []
            for j in range(len(U)):
                if not BRK[i, j] or j in pos or (j in last_exit and i - last_exit[j] < reentry) or np.isnan(REL[i, j]):
                    continue
                if np.isnan(V[i, j]):
                    continue
                if cap is not None and not V[i, j] > cap:
                    continue
                cand.append(j)
            if cand:
                if rank == "rel":
                    key = {j: -REL[i, j] for j in cand}
                elif rank == "res":
                    key = {j: -V[i, j] for j in cand}
                else:
                    rr = pd.Series({j: -REL[i, j] for j in cand}).rank()
                    vv = pd.Series({j: -V[i, j] for j in cand}).rank()
                    key = (rr + vv).to_dict()
                cand.sort(key=lambda j: key[j])
                for j in cand[:min(free, max_new)]:
                    pend_in.append(j); vols_in.append((str(d.date()), float(BETA[i, j])))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, vols_in


def vstat(vs, a, b):
    x = [v for d, v in vs if a <= d <= b]
    return round(float(np.median(x)), 3) if x else None


def worst(tr, a, b):
    x = [g for d, g in tr if a <= d <= b]
    return round(float(min(x)) * 100, 2) if x else None


def main():
    C, _, _ = load_ohlc()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    PRE = {"E": prep(C, UNIV), "S": prep(C, list(STK))}
    print("무리 크기", {k: len(v["U"]) for k, v in PRE.items()}, flush=True)

    def run(fam, rank, cap, lb):
        rk, tk, tr, vs = kick(C, idx, PRE[fam], rank=rank, cap=cap, lb=lb)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "rank": rank, "cap": cap, "lb": lb,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "worst_oos": worst(tr, OOS_START, END), "beta_in_oos": vstat(vs, OOS_START, END)}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        cur = run(fam, "rel", None, 63)
        grid = []
        for rk in RANKS:
            for cp in CAPS:
                for lb in LBS:
                    g = cur if (rk == "rel" and cp is None and lb == 63) else run(fam, rk, cp, lb)
                    grid.append(g)
                    print(fam, rk, cp, lb, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"],
                          g["tr_oos"], g["worst_oos"], flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        for k in (0.8, 1.2):
            lb2 = int(round(best["lb"] * k))
            g = run(fam, best["rank"], best["cap"], lb2); g["what"] = f"기간 {lb2}일"; shake.append(g)
        if best["rank"] != "rel" or best["cap"] is not None:
            g = run(fam, best["rank"], None if best["cap"] is not None else 0.0, best["lb"])
            g["what"] = "잔차>0 거르기 " + ("끔" if best["cap"] is not None else "켬"); shake.append(g)

        def ok(o):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}
        chk = ok(best["oos"])
        shake_ok = all(all(ok(s["oos"]).values()) for s in shake) if shake else False
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))

        def avg(key, val):
            xs = [g for g in grid if g[key] == val]
            return {"n": len(xs), "oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in xs])), 3),
                    "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in xs])), 2),
                    "oos_mdd": round(float(np.mean([g["oos"]["mdd"] for g in xs])), 2),
                    "is_sh": round(float(np.mean([g["is"]["sharpe"] for g in xs])), 3)}
        by = {f"rank_{r}": avg("rank", r) for r in RANKS}
        by.update({f"cap_{c}": avg("cap", c) for c in CAPS})
        by.update({f"lb_{l}": avg("lb", l) for l in LBS})
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"rank": g["rank"], "cap": g["cap"], "lb": g["lb"], "is_sh": g["is"]["sharpe"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"), "tr_oos": g["tr_oos"],
                                "worst_oos": g["worst_oos"], "beta_in_oos": g["beta_in_oos"]} for g in grid]}
        print(fam, "고른", best["rank"], best["cap"], best["lb"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "rank rel = 상대 강도 순(지금) / res = 잔차 점수 큰 순 / mix = 두 순위 합 · cap 0.0 = 잔차 점수 > 0 만 · lb = 베타·잔차 기간 · beta_in_oos = 들어간 종목 베타 가운데 · "
                   "출구 −5·+15·15일 그대로 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
