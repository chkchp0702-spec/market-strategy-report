"""🌙 11/15 밤 연구 #35 — 💸 비용에 강한 출구 (매매 비용 0.2·0.3% 에서 출구 다시 고르기)
  왜: Novy-Marx·Velikov 2016 「A Taxonomy of Anomalies and Their Trading Costs」(RFS 29(1)) https://doi.org/10.1093/rfs/hhv063
      — 회전 큰 전략은 비용을 빼면 초과수익이 대부분 사라짐.
      11/12 밤: 실전 비용은 0.1% 보다 큼(0.2% 에서 #29 무너짐) · 11/13 밤: 따라붙는 손절은 회전이 절반(336→175%).
  바꾸는 것: 킥 돌파 칸 출구만(신호·순서·자리 5·칸 19% 그대로) — 11/13 출구 틀(k1113_trail.kick_trail) 재사용
    trail 없음(고정 −5% 만) · 5·8·10·12·15·20% × mode replace/both × 익절 +15%/없음 × 15일 정체 정리 있음/없음 = 52조합
  비용: 모든 매매(기본 칸 포함, 지금 킥도 같은 비용)에 회전율 × 0.2% 로 고르고 시험 · 0.3% 로 다시 확인 · 0.1% 참고
  무리: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개(생존 편향)
  전날 종가 판단 → 다음 날 종가 체결 · 앞 2008-07~2016 샤프로 고르고 2017~ 시험
  흔들기 = trail ×0.8/×1.2 · 익절·정체 하나씩 반대 · 비용 0.3%
→ market/lab/k1115_costexit.json
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
import k1113_trail
from k1011_size import run_mix, seg, UNIV
from k1019_cupbrk import STK
from k1030_slip import load_ohlc
from k1105_resmom import prep
from k1113_trail import kick_trail, tr_stat

OUT = Path("market/lab/k1115_costexit.json")
SIZE = 0.19
TRAILS = [None, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
MODES = ["replace", "both"]
TAKES = [0.15, None]
TIMES = [True, False]
PICK_COST = 0.002


def set_cost(c):
    for m in (k1011_size, k1013_trend, k1113_trail):
        m.COST = c


def combos():
    out = []
    for x in TRAILS:
        for mo in (["both"] if x is None else MODES):
            for tk_ in TAKES:
                for ti in TIMES:
                    out.append((x, mo, tk_, ti))
    return out


def main():
    C, _, _ = load_ohlc()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    PRE = {"E": prep(C, UNIV), "S": prep(C, list(STK))}
    print("무리 크기", {k: len(v["U"]) for k, v in PRE.items()}, flush=True)
    BASE = {}

    def base(c):
        if c not in BASE:
            set_cost(c)
            BASE[c] = k1013_trend.base_vol(C, reg, idx)
        set_cost(c)
        return BASE[c]

    def run(fam, cost, trail, mode, take, use_time):
        rb, tb = base(cost)
        rk, tk, tr = kick_trail(C, idx, PRE[fam], trail=trail, mode=mode, take=take, use_time=use_time)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "cost": cost, "trail": trail, "mode": mode, "take": take, "time": use_time,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_oos": tr_stat(tr, OOS_START, END)}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        curs = {c: run(fam, c, None, "both", 0.15, True) for c in (0.001, 0.002, 0.003)}
        for c, r in curs.items():
            print(fam, "지금", c, r["oos"], flush=True)
        grid = []
        for (x, mo, tk_, ti) in combos():
            g = run(fam, PICK_COST, x, mo, tk_, ti)
            grid.append(g)
            print(fam, x, mo, tk_, ti, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"],
                  g["oos"].get("turn"), flush=True)
        trials += len(grid)
        cur = curs[PICK_COST]
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]

        def ok(o, r=ref):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > r)}

        shake = []
        if best["trail"] is not None:
            for k in (0.8, 1.2):
                x2 = round(best["trail"] * k, 3)
                g = run(fam, PICK_COST, x2, best["mode"], best["take"], best["time"]); g["what"] = f"따라붙기 {x2*100:.1f}%"; shake.append(g)
        g = run(fam, PICK_COST, best["trail"], best["mode"], None if best["take"] else 0.15, best["time"])
        g["what"] = "익절 " + ("없음" if g["take"] is None else "+15%"); shake.append(g)
        g = run(fam, PICK_COST, best["trail"], best["mode"], best["take"], not best["time"])
        g["what"] = "정체 정리 " + ("있음" if g["time"] else "없음"); shake.append(g)
        for s in shake:
            s["ok"] = ok(s["oos"])
        # 비용 0.3% · 0.1% 에서 같은 출구 vs 같은 비용의 지금 킥
        at_cost = {}
        for c in (0.001, 0.003):
            g = run(fam, c, best["trail"], best["mode"], best["take"], best["time"])
            g["ok"] = ok(g["oos"], curs[c]["oos"]["sharpe"])
            at_cost[str(c)] = g
        shake_ok = all(all(s["ok"].values()) for s in shake) and all(at_cost["0.003"]["ok"].values())
        chk = ok(best["oos"])
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
        # 회전 낮은 절반 vs 높은 절반 (시험 구간 평균)
        tv = sorted(grid, key=lambda g: g["oos"].get("turn") or 0)
        h = len(tv) // 2

        def mean_of(xs):
            return {"oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in xs])), 3),
                    "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in xs])), 2),
                    "turn": round(float(np.mean([g["oos"].get("turn") or 0 for g in xs])))}
        out_f[fam] = {"current_by_cost": {str(c): {"oos": r["oos"], "is_sh": r["is"]["sharpe"]} for c, r in curs.items()},
                      "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "shake": shake, "at_cost": at_cost,
                      "low_turn_half": mean_of(tv[:h]), "high_turn_half": mean_of(tv[h:]),
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"trail": g["trail"], "mode": g["mode"], "take": g["take"], "time": g["time"],
                                "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"),
                                "tr_oos_avg": g["tr_oos"].get("avg"), "tr_oos_n": g["tr_oos"].get("n")} for g in grid]}
        print(fam, "고른", best["trail"], best["mode"], best["take"], best["time"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
        for c, g in at_cost.items():
            print("  비용", c, g["oos"], g["ok"])
    verdict = "✅ 통과" if out_f["E"]["verdict"] == "✅ 통과" else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "pick_cost_pct": PICK_COST * 100, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용, 판정 기준) · S = 미국 대형주 102개(생존 편향, 참고) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "비용 = 모든 매매 회전율 × 0.2%(고르기·시험) · 0.3%·0.1% 확인 · trail None = 지금 고정 −5% 출구 · "
                   "앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
