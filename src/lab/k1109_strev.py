"""🌙 11/09 밤 연구 #28 — ↩️ 단기 되돌림 거르기 (최근 며칠 이미 크게 오른 돌파 후보는 빼거나 뒤로)
  왜: Jegadeesh 1990 「Evidence of Predictable Behavior of Security Returns」(J. Finance 45(3))
      https://doi.org/10.1111/j.1540-6261.1990.tb05110.x — 지난 한 달 많이 오른 종목은 다음 달 되돌림.
      실제 킥 장부 닫힌 거래는 거의 손절(표본 부족) — 추격 매수가 원인인지 긴 역사로 확인.
  바꾸는 것(돌파 후보 고르기만 — 출구 −5·+15·15일·자리 5·킥 칸 19% 그대로):
    n   : 최근 수익 재는 기간 5·10·21거래일 (그날 종가까지 판단, 체결은 다음 날)
    x   : 그 기간 수익이 +x% 넘으면 「급등 후보」 — 3·5·8·12%
    mode: drop = 급등 후보 빼기 / back = 급등 후보는 다른 후보 뒤로(자리가 남을 때만)
    = 24조합 + 지금(거르기 없음)
  무리 2개: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향)
  틀: C안 뼈대 × 변동성 맞춤 + 킥 칸 19%·자리 5 · 회전율 × 0.1%
  앞 2008-07~2016 샤프로 무리마다 고르고 2017~ 시험 · 흔들기 = n·x ×0.8/×1.2 · mode 반대
→ market/lab/k1109_strev.json
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
from k1105_resmom import prep

OUT = Path("market/lab/k1109_strev.json")
SIZE = 0.19
NS = [5, 10, 21]
XS = [3.0, 5.0, 8.0, 12.0]
MODES = ["drop", "back"]


def short_ret(pre, Cl, n):
    key = ("sr", n)
    if key not in pre["vol"]:
        P = Cl[pre["U"]]
        pre["vol"][key] = (P / P.shift(n) - 1).values
    return pre["vol"][key]


def kick(C, idx, pre, n=None, x=None, mode="drop", stop=-0.05, take=0.15, time_d=15, time_min=0.03,
         slots=5, max_new=2, reentry=10):
    U, Pv, BRK, REL, R, bil = pre["U"], pre["P"], pre["brk"], pre["rel"], pre["R"], pre["bil"]
    SR = short_ret(pre, C, n) if n else None
    thr = (x or 0) / 100.0
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades, hot_trades = [], [], [], []
    seen = {"cand": 0, "hot": 0}
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
                g = Pv[i, j] / p["entry"] - 1
                trades.append((str(C.index[p["ent_i"]].date()), g))
                if p.get("hot"):
                    hot_trades.append((str(C.index[p["ent_i"]].date()), g))
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j, hot in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(1.0 / slots, cash)
            if w <= 0 or np.isnan(Pv[i, j]):
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i, "hot": hot}
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
                cand.append(j)
            if cand:
                hot = {}
                for j in cand:
                    h = False
                    if SR is not None:
                        v = SR[i, j]
                        h = bool(not np.isnan(v) and v > thr)
                    hot[j] = h
                seen["cand"] += len(cand); seen["hot"] += sum(hot.values())
                if mode == "drop":
                    cand = [j for j in cand if not hot[j]]
                cand.sort(key=lambda j: (hot[j] if mode == "back" else False, -REL[i, j]))
                for j in cand[:min(free, max_new)]:
                    pend_in.append((j, hot[j]))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, hot_trades, seen


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

    def run(fam, n, x, mode):
        rk, tk, tr, hot_tr, seen = kick(C, idx, PRE[fam], n=n, x=x, mode=mode)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "n": n, "x": x, "mode": mode,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "hot_tr_oos": tstat(hot_tr, OOS_START, END), "hot_tr_is": tstat(hot_tr, START, IS_END),
                "hot_share": round(seen["hot"] / seen["cand"] * 100, 1) if seen["cand"] else None}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        cur = run(fam, None, None, "drop")
        # 진단: 지금 규칙 그대로(mode="tag" = 빼지도 미루지도 않고 표시만), 산 것 중 급등 후보였던 것의 거래 성적
        diag = {}
        for n in NS:
            for x in (5.0, 8.0):
                rk, tk, tr, hot_tr, seen = kick(C, idx, PRE[fam], n=n, x=x, mode="tag")
                cold = [t for t in tr if t not in hot_tr]
                diag[f"n{n}_x{x}"] = {"hot_is": tstat(hot_tr, START, IS_END), "cold_is": tstat(cold, START, IS_END),
                                      "hot_oos": tstat(hot_tr, OOS_START, END), "cold_oos": tstat(cold, OOS_START, END),
                                      "hot_share_cand": round(seen["hot"] / seen["cand"] * 100, 1) if seen["cand"] else None}
                print("진단", fam, n, x, diag[f"n{n}_x{x}"], flush=True)
        grid = []
        for n in NS:
            for x in XS:
                for md in MODES:
                    g = run(fam, n, x, md)
                    grid.append(g)
                    print(fam, n, x, md, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"],
                          g["tr_oos"], flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        for k in (0.8, 1.2):
            n2 = int(round(best["n"] * k))
            g = run(fam, n2, best["x"], best["mode"]); g["what"] = f"기간 {n2}일"; shake.append(g)
        for k in (0.8, 1.2):
            x2 = round(best["x"] * k, 1)
            g = run(fam, best["n"], x2, best["mode"]); g["what"] = f"급등 기준 +{x2}%"; shake.append(g)
        g = run(fam, best["n"], best["x"], "back" if best["mode"] == "drop" else "drop")
        g["what"] = "방식 " + g["mode"]; shake.append(g)

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
        by = {f"n_{v}": avg("n", v) for v in NS}
        by.update({f"x_{v}": avg("x", v) for v in XS})
        by.update({f"mode_{v}": avg("mode", v) for v in MODES})
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake, "diag": diag,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"n": g["n"], "x": g["x"], "mode": g["mode"], "is_sh": g["is"]["sharpe"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"), "tr_oos": g["tr_oos"],
                                "hot_share": g["hot_share"]} for g in grid]}
        print(fam, "고른", best["n"], best["x"], best["mode"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "n = 최근 수익 기간(거래일) · x = 급등 기준(+%) · mode drop = 급등 후보 빼기 / back = 뒤로 · diag = 지금 규칙이 산 것을 급등/아님으로 나눈 거래 성적 · "
                   "출구 −5·+15·15일 그대로 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
