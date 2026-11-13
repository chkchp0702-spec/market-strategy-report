"""🌙 11/13 밤 연구 #31 — 🪢 이익 따라붙는 손절 (보유 중 최고가 대비 −x% 로 손절선을 끌어올리기)
  왜: Han·Zhou·Zhu 2016 「Taming Momentum Crashes: A Simple Stop-Loss Strategy」 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199
      — 손절을 걸면 모멘텀 최대 손실이 크게 줄고 샤프가 두 배 가까이.
      10/12 밤 출구 180조합은 고정 손절·익절·기간만 봄 → 따라붙는 손절은 아직.
  바꾸는 것(킥 돌파 칸 출구만 — 신호·순서·자리 5·칸 19% 그대로):
    trail x 5·8·10·12·15·20% : 종가가 「들어간 뒤 최고 종가 × (1−x)」 아래면 다음 날 종가에 팖
    mode  replace = 고정 −5% 손절 없애고 따라붙는 손절만 / both = 고정 −5% 도 같이
    take  +15% 익절 있음 / 없음(따라붙는 손절이 이익을 지킴)
    time  15일 지나도 최고 +3% 못 넘으면 정리 — 있음 / 없음
    = 6 × 2 × 2 × 2 = 48조합 × 무리 2
  무리: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향)
  전날 종가 판단 → 다음 날 종가 체결 · 회전율 × 0.1% · 앞 2008-07~2016 샤프로 고르고 2017~ 시험
  흔들기 = x ×0.8/×1.2 · take·time·mode 하나씩 반대
→ market/lab/k1113_trail.json
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
from k1013_trend import base_vol
from k1019_cupbrk import STK
from k1030_slip import load_ohlc
from k1105_resmom import prep

OUT = Path("market/lab/k1113_trail.json")
SIZE = 0.19
TRAILS = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
MODES = ["replace", "both"]
TAKES = [0.15, None]
TIMES = [True, False]


def kick_trail(C, idx, pre, trail=None, mode="both", stop=-0.05, take=0.15, use_time=True,
               time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    """k1105_resmom.kick(rank='rel') 와 같은 틀 + 따라붙는 손절. trail=None 이면 지금 킥 그대로."""
    U, Pv, BRK, REL, R, bil = pre["U"], pre["P"], pre["brk"], pre["rel"], pre["R"], pre["bil"]
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades = [], [], []
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
            out = False
            if trail is None or mode == "both":
                out |= g <= stop
            if trail is not None:
                out |= px <= p["max"] * (1 - trail)
            if take is not None:
                out |= g >= take
            if use_time:
                out |= (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min)
            if out:
                pend_out.append(j)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [j for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(key=lambda j: -REL[i, j])
            for j in cand[:min(free, max_new)]:
                pend_in.append(j)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades


def tr_stat(tr, a, b):
    x = [(g, h) for dd, g, h in tr if a <= dd <= b]
    if not x:
        return {"n": 0}
    g = np.array([v for v, _ in x])
    pos_, neg = g[g > 0].sum(), -g[g < 0].sum()
    return {"n": len(g), "avg": round(float(g.mean()) * 100, 2), "win": round(float((g > 0).mean()) * 100, 1),
            "pf": round(float(pos_ / neg), 2) if neg > 0 else None, "worst": round(float(g.min()) * 100, 2),
            "best": round(float(g.max()) * 100, 2), "hold_avg": round(float(np.mean([h for _, h in x])), 1)}


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

    def run(fam, trail, mode, take, use_time):
        rk, tk, tr = kick_trail(C, idx, PRE[fam], trail=trail, mode=mode, take=take, use_time=use_time)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        ks = seg((1 + rk).cumprod(), spy, OOS_START, END)
        return {"fam": fam, "trail": trail, "mode": mode, "take": take, "time": use_time,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_oos": {"cagr": ks["cagr"], "mdd": ks["mdd"], "sharpe": ks["sharpe"]},
                "tr_is": tr_stat(tr, START, IS_END), "tr_oos": tr_stat(tr, OOS_START, END)}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        cur = run(fam, None, "both", 0.15, True)
        print(fam, "지금", cur["is"]["sharpe"], cur["oos"], cur["tr_oos"], flush=True)
        grid = []
        for x in TRAILS:
            for mo in MODES:
                for tk_ in TAKES:
                    for ti in TIMES:
                        g = run(fam, x, mo, tk_, ti)
                        grid.append(g)
                        print(fam, x, mo, tk_, ti, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"],
                              g["tr_oos"].get("avg"), g["tr_oos"].get("worst"), flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        for k in (0.8, 1.2):
            x2 = round(best["trail"] * k, 3)
            g = run(fam, x2, best["mode"], best["take"], best["time"]); g["what"] = f"따라붙기 {x2*100:.1f}%"; shake.append(g)
        g = run(fam, best["trail"], best["mode"], None if best["take"] else 0.15, best["time"])
        g["what"] = "익절 " + ("없음" if g["take"] is None else "+15%"); shake.append(g)
        g = run(fam, best["trail"], best["mode"], best["take"], not best["time"])
        g["what"] = "정체 정리 " + ("있음" if g["time"] else "없음"); shake.append(g)
        g = run(fam, best["trail"], "both" if best["mode"] == "replace" else "replace", best["take"], best["time"])
        g["what"] = "고정 −5% " + ("같이" if g["mode"] == "both" else "없앰"); shake.append(g)

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
        by = {f"trail_{x}": avg("trail", x) for x in TRAILS}
        by.update({f"mode_{x}": avg("mode", x) for x in MODES})
        by.update({f"take_{x}": avg("take", x) for x in TAKES})
        by.update({f"time_{x}": avg("time", x) for x in TIMES})
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"trail": g["trail"], "mode": g["mode"], "take": g["take"], "time": g["time"],
                                "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"),
                                "tr_oos_avg": g["tr_oos"].get("avg"), "tr_oos_worst": g["tr_oos"].get("worst"),
                                "tr_oos_n": g["tr_oos"].get("n")} for g in grid]}
        print(fam, "고른", best["trail"], best["mode"], best["take"], best["time"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "trail = 들어간 뒤 최고 종가 대비 −x% 종가면 다음 날 종가에 팖 · mode replace = 고정 −5% 없앰 / both = 같이 · "
                   "take = +15% 익절 유무 · time = 15일 최고 +3% 미만 정리 유무 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
