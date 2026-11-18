"""🌙 11/18 밤 연구 #37 — 🧷 파는 문턱 늦추기 (팔 이유가 생겨도 「아직 순위 안」이면 계속 들기)
  왜: Gârleanu·Pedersen 2013 「Dynamic Trading with Predictable Returns and Transaction Costs」(J. Finance 68(6))
      https://doi.org/10.1111/jofi.12080 — 비용이 있으면 목표로 한 번에 가지 말고, 띠 안에선 그대로 두기.
      11/15 밤: 비용 0.2% 면 지금 킥 대용이 S&P −0.72%p · 출구를 통째로 바꾸면(익절·정체 없앰) 「들고 있기」가 되어 낙폭 −18→−22%.
  바꾸는 것(킥 돌파 칸 출구만 — 신호·순서·자리 5·칸 19% 그대로, −5% 손절은 늘 그대로):
    keep  = 「아직 순위 안」 기준
            rank K : 63일 S&P 대비 수익 순위가 무리 안 상위 K (K 5·10·15·20·30)
            near y : 종가가 52주 고점의 (1−y) 위 (y 3·5·8·10%)
    apply = 늦추는 출구 take(+15% 익절만) / time(15일 정체 정리만) / both
    cap   = 늦춰도 최대 보유 60거래일 / 없음
    = 9 × 3 × 2 = 54조합 × 무리 2
  비용: 회전율 × 0.1% 로 고르고 시험(작업 규칙) · 0.2% 로 다시 확인(이 연구의 동기)
  무리: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용, 판정 기준) · S = 미국 대형주 102개(생존 편향, 참고)
  전날 종가 판단 → 다음 날 종가 체결 · 앞 2008-07~2016 샤프로 고르고 2017~ 시험
  흔들기 = K·y ×0.8/×1.2 · cap 반대 · 비용 0.2%
→ market/lab/k1118_holdband.json
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
import k1011_size
import k1013_trend
from k1011_size import run_mix, seg, UNIV
from k1019_cupbrk import STK
from k1030_slip import load_ohlc
from k1105_resmom import prep
from k1113_trail import tr_stat

OUT = Path("market/lab/k1118_holdband.json")
SIZE = 0.19
KEEPS = [("rank", 5), ("rank", 10), ("rank", 15), ("rank", 20), ("rank", 30),
         ("near", 0.03), ("near", 0.05), ("near", 0.08), ("near", 0.10)]
APPLIES = ["take", "time", "both"]
CAPS = [60, None]
COST = 0.001


def set_cost(c):
    global COST
    COST = c
    for m in (k1011_size, k1013_trend):
        m.COST = c


def add_keep(C, pre):
    P = C[pre["U"]]
    rel = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0)
    pre["rk"] = rel.rank(axis=1, ascending=False).values      # 1 = 가장 강함
    hi = P.rolling(252, min_periods=200).max()
    pre["near"] = (P / hi).values                             # 그날 종가 / 52주 고점(그날 포함)
    return pre


def kick_band(C, idx, pre, keep=None, apply="both", cap=None, stop=-0.05, take=0.15,
              time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    """k1113_trail.kick_trail(trail=None) 와 같은 틀 + 파는 문턱 늦추기. keep=None 이면 지금 킥 그대로."""
    U, Pv, BRK, REL, R, bil = pre["U"], pre["P"], pre["brk"], pre["rel"], pre["R"], pre["bil"]
    RK, NEAR = pre["rk"], pre["near"]
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades = [], [], []
    kept_days = 0
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
                trades.append((str(C.index[p["ent_i"]].date()), Pv[i, j] / p["entry"] - 1, p["held"]))
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
            hard = g <= stop
            soft_take = g >= take
            soft_time = p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min
            out = hard
            if keep is not None and (soft_take or soft_time):
                kind, v = keep
                if kind == "rank":
                    still = (not np.isnan(RK[i, j])) and RK[i, j] <= v
                else:
                    still = (not np.isnan(NEAR[i, j])) and NEAR[i, j] >= 1 - v
                if cap is not None and p["held"] >= cap:
                    still = False
                late_take = apply in ("take", "both")
                late_time = apply in ("time", "both")
                if soft_take and not (late_take and still):
                    out = True
                if soft_time and not (late_time and still):
                    out = True
                if not out:
                    kept_days += 1
            else:
                out |= soft_take or soft_time
            if out:
                pend_out.append(j)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [j for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(key=lambda j: -REL[i, j])
            for j in cand[:min(free, max_new)]:
                pend_in.append(j)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, kept_days


def main():
    C, _, _ = load_ohlc()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    PRE = {"E": add_keep(C, prep(C, UNIV)), "S": add_keep(C, prep(C, list(STK)))}
    print("무리 크기", {k: len(v["U"]) for k, v in PRE.items()}, flush=True)
    BASE = {}

    def base(c):
        set_cost(c)
        if c not in BASE:
            BASE[c] = k1013_trend.base_vol(C, reg, idx)
        return BASE[c]

    def run(fam, cost, keep, apply, cap):
        rb, tb = base(cost)
        rk, tk, tr, kd = kick_band(C, idx, PRE[fam], keep=keep, apply=apply, cap=cap)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "cost": cost, "keep": list(keep) if keep else None, "apply": apply, "cap": cap,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_oos": tr_stat(tr, OOS_START, END), "kept_days": kd}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        curs = {c: run(fam, c, None, "both", None) for c in (0.001, 0.002)}
        for c, r in curs.items():
            print(fam, "지금", c, r["oos"], r["tr_oos"], flush=True)
        grid = []
        for kp in KEEPS:
            for ap in APPLIES:
                for cp in CAPS:
                    g = run(fam, 0.001, kp, ap, cp)
                    grid.append(g)
                    print(fam, kp, ap, cp, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"],
                          g["oos"].get("turn"), g["tr_oos"].get("n"), flush=True)
        trials += len(grid)
        cur = curs[0.001]
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]

        def ok(o, r=ref):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > r)}

        kind, v = best["keep"]
        shake = []
        for k in (0.8, 1.2):
            v2 = max(1, round(v * k)) if kind == "rank" else round(v * k, 3)
            g = run(fam, 0.001, (kind, v2), best["apply"], best["cap"]); g["what"] = f"{kind} {v2}"; shake.append(g)
        g = run(fam, 0.001, (kind, v), best["apply"], None if best["cap"] else 60)
        g["what"] = "상한 " + ("없음" if g["cap"] is None else "60일"); shake.append(g)
        if best["cap"]:
            for c2 in (48, 72):
                g = run(fam, 0.001, (kind, v), best["apply"], c2); g["what"] = f"상한 {c2}일"; shake.append(g)
        for s in shake:
            s["ok"] = ok(s["oos"])
        g2 = run(fam, 0.002, (kind, v), best["apply"], best["cap"])
        g2["ok"] = ok(g2["oos"], curs[0.002]["oos"]["sharpe"])
        g2["ex_vs_cur_pp"] = round(g2["oos"]["cagr"] - curs[0.002]["oos"]["cagr"], 2)
        shake_ok = all(all(s["ok"].values()) for s in shake)
        chk = ok(best["oos"])
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))

        def avg(f):
            xs = [g for g in grid if f(g)]
            return {"n": len(xs), "oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in xs])), 3),
                    "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in xs])), 2),
                    "oos_mdd": round(float(np.mean([g["oos"]["mdd"] for g in xs])), 2),
                    "oos_turn": round(float(np.mean([g["oos"].get("turn") or 0 for g in xs])))}
        by = {f"apply_{a}": avg(lambda g, a=a: g["apply"] == a) for a in APPLIES}
        by.update({f"cap_{c}": avg(lambda g, c=c: g["cap"] == c) for c in CAPS})
        by.update({"keep_rank": avg(lambda g: g["keep"][0] == "rank"), "keep_near": avg(lambda g: g["keep"][0] == "near")})
        out_f[fam] = {"current_by_cost": {str(c): {"oos": r["oos"], "is_sh": r["is"]["sharpe"], "tr_oos": r["tr_oos"]} for c, r in curs.items()},
                      "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake, "cost_0.2": g2,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"keep": g["keep"], "apply": g["apply"], "cap": g["cap"],
                                "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"),
                                "tr_oos_avg": g["tr_oos"].get("avg"), "tr_oos_n": g["tr_oos"].get("n"),
                                "hold_avg": g["tr_oos"].get("hold_avg")} for g in grid]}
        print(fam, "고른", best["keep"], best["apply"], best["cap"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
        print("  비용 0.2%", g2["oos"], g2["ok"], g2["ex_vs_cur_pp"])
    verdict = out_f["E"]["verdict"]
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용, 판정 기준) · S = 미국 대형주 102개(생존 편향, 참고) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "keep rank K = 63일 S&P 대비 수익 무리 안 상위 K 면 계속 들기 · near y = 52주 고점 −y% 안이면 계속 들기 · "
                   "apply = 늦추는 출구(+15% 익절 / 15일 정체 / 둘 다) · −5% 손절은 늘 그대로 · cap = 최대 보유일 · "
                   "비용 회전율 × 0.1%(고르기·시험)·0.2% 확인 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
