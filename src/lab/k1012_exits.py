"""🌙 10/12 밤 연구 #2 — 손절·익절·보유 기간 손잡이 (지금 −5%·+15%·15일)
  틀은 10/11 #1(src/lab/k1011_size.py) 그대로: 기본 = C안 뼈대 · 킥 칸 19%(🟢·🔴 같게)
  킥 칸 대용 = 섹터·테마 ETF 52주 신고가 돌파 (개별 종목 신호는 긴 역사가 없음 → 한계)
  손절 6 × 익절 6 × 보유 기간 5 = 180 조합을 2008-07~2016 샤프로 고르고 2017~ 에서 시험
  판단은 그날 종가까지 → 다음 날 종가 체결 · 회전율 × 0.1% 비용
→ market/lab/k1012_exits.json
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
from k1011_size import load, base_account, run_mix, seg, UNIV, COST

OUT = Path("market/lab/k1012_exits.json")
SIZE = 0.19
CUR = {"stop": -0.05, "take": 0.15, "time_d": 15}
STOPS = [-0.03, -0.04, -0.05, -0.07, -0.10, -0.15]
TAKES = [0.10, 0.12, 0.15, 0.20, 0.25, 1.00]      # 1.00 = 사실상 익절 없음
TIMES = [10, 15, 20, 30, 999]                     # 999 = 보유 기간 제한 없음


def prep(C):
    U = [t for t in UNIV if t in C.columns]
    P = C[U]
    hi = P.shift(1).rolling(252, min_periods=252).max()
    brk = (P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))
    rel = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0)
    R = C[U].pct_change().fillna(0.0).values
    bil = C["BIL"].pct_change().fillna(0.0).values
    return U, P.values, brk.values, rel.values, R, bil


def kick_fast(C, idx, pre, stop=-0.05, take=0.15, time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    U, Pv, BRK, REL, R, bil = pre
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades = [], [], []
    for d in idx:
        i = pos_i[d]
        r = cash * bil[i]
        for j, p in pos.items():
            rt = R[i, j]
            r += p["w"] * rt
            p["w"] *= 1 + rt
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
            if w <= 0:
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
            cand = [(REL[i, j], j) for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            pend_in = [j for _, j in cand[:min(free, max_new)]]
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades


def tstat(tr, a, b):
    x = [r for d, r in tr if a <= d <= b]
    if not x:
        return {}
    w = [v for v in x if v > 0]; l = [v for v in x if v <= 0]
    return {"n": len(x), "avg": round(float(np.mean(x)) * 100, 2), "win": round(len(w) / len(x) * 100),
            "pf": round(sum(w) / -sum(l), 2) if l and sum(l) < 0 else None}


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_account(C, reg, idx)
    pre = prep(C)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def run(**kw):
        k = kick_fast(C, idx, pre, **kw)
        nav, td = run_mix(rb, tb, k, reg, SIZE, SIZE)
        knav = (1 + k[0]).cumprod()
        return {**{a: kw[a] for a in ("stop", "take", "time_d")},
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, k[1]), "kick_oos": seg(knav, spy, OOS_START, END, k[1]),
                "tr_is": tstat(k[2], START, IS_END), "tr_oos": tstat(k[2], OOS_START, END)}

    grid = []
    for s in STOPS:
        for t in TAKES:
            for h in TIMES:
                grid.append(run(stop=s, take=t, time_d=h))
    cur = next(g for g in grid if g["stop"] == CUR["stop"] and g["take"] == CUR["take"] and g["time_d"] == CUR["time_d"])
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    # 앞 구간 1등 둘레(이웃 손잡이) 평균 — 봉우리인지 고원인지
    si, ti, hi = STOPS.index(best["stop"]), TAKES.index(best["take"]), TIMES.index(best["time_d"])
    nb = [g for g in grid if abs(STOPS.index(g["stop"]) - si) <= 1 and abs(TAKES.index(g["take"]) - ti) <= 1 and abs(TIMES.index(g["time_d"]) - hi) <= 1]
    plateau = {"n": len(nb), "is_sharpe": round(float(np.mean([g["is"]["sharpe"] for g in nb])), 3),
               "oos_sharpe": round(float(np.mean([g["oos"]["sharpe"] for g in nb])), 3),
               "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in nb])), 2)}
    # ±20% 흔들기 (한 손잡이씩)
    shake = []
    base_kw = {"stop": best["stop"], "take": best["take"], "time_d": best["time_d"]}
    for key in ("stop", "take", "time_d"):
        for f in (0.8, 1.2):
            kw = dict(base_kw)
            kw[key] = round(kw[key] * f, 4) if key != "time_d" else max(1, int(round(kw[key] * f)))
            g = run(**kw)
            g["what"] = f"{key} ×{f}"
            shake.append(g)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > cur["oos"]["sharpe"])}
    same = best is cur
    chk = ok(best["oos"])
    shake_ok = bool(all(all(ok(s["oos"]).values()) for s in shake))
    if same:
        verdict = "➖ 애매 (지금 값이 그대로 1등)"
    elif all(chk.values()) and shake_ok:
        verdict = "✅ 통과"
    elif any(chk.values()):
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    # 축별 평균 (다른 두 손잡이 평균) — 어느 쪽이 좋은 방향인지
    axis = {}
    for key, vals in (("stop", STOPS), ("take", TAKES), ("time_d", TIMES)):
        axis[key] = [{"v": v, "is": round(float(np.mean([g["is"]["sharpe"] for g in grid if g[key] == v])), 3),
                      "oos": round(float(np.mean([g["oos"]["sharpe"] for g in grid if g[key] == v])), 3)} for v in vals]
    rank_cor = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "size": SIZE, "spy": spy_row, "current": cur, "best": best, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "plateau": plateau, "axis": axis, "is_oos_rank_cor": round(rank_cor, 2), "shake": shake,
           "grid": [{k: g[k] for k in ("stop", "take", "time_d")} | {"is_sh": g["is"]["sharpe"], "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"]} for g in grid],
           "note": "킥 신호 대신 섹터·테마 ETF 52주 신고가 돌파 · 기본 = C안 뼈대 · 킥 칸 19% · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 손절은 종가 기준(장중 손절보다 늦음) · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("현재", cur["stop"], cur["take"], cur["time_d"], cur["is"]["sharpe"], cur["oos"], cur["tr_oos"])
    print("고른", best["stop"], best["take"], best["time_d"], best["is"]["sharpe"], best["oos"], best["tr_oos"])
    print("고원", plateau, "순위상관", round(rank_cor, 2))
    for k, v in axis.items():
        print(k, v)
    for s in shake:
        print(s["what"], s["stop"], s["take"], s["time_d"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
