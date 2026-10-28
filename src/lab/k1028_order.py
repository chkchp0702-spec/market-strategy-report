"""🌙 10/28 밤 연구 #21 — 🥇 지금 신호(E+P+C) 그대로, 순서만 바꾸기
  10/27 밤: E+P+C 같은 순위 샤프 1.14·연 15.40% vs 「실적 갭 먼저」(P>C>E) 1.18·16.03% · 섞는 26조합 평균 prio 1.14 > tie 1.13.
  질문: 지금 kick_params pri(nh52·pead·cup 모두 10 = 같은 순위)에서 순서만 바꾸면 S&P 를 안전하게 이기나.
  틀은 10/13~27 그대로: C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 자리 5 · 하루 새 진입 2 · 출구 −5%·+15%·15일 정체 · 빈 자리 BIL
  신호 무리 = E ETF 52주 돌파 · P 실적 갭(5%·2배) · C 컵 돌파(손잡이 4일↑·RS 50%↑) — P·C 는 미국 대형주 102개 대용
  격자: 순서 6가지(E·P·C 줄 세우기) × 덤 크기(엄격 = 앞 무리를 무조건 먼저 / 부드럽게 = 63일 상대강도에 0.05·0.10·0.20 씩 더함) + 같은 순위(지금) = 25조합
  앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1% · 흔들기 = 실적 갭·컵 손잡이 ±20% (+ 부드러운 덤이면 덤 ±20%)
→ market/lab/k1028_order.json
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1014_volw import kick_vw
from k1019_cupbrk import STK, cup_state
from k1024_pead import kick_x, dq_of

OUT = Path("market/lab/k1028_order.json")
SIZE = 0.19
FAM = ["E", "P", "C", "G"]
NAME = {"E": "ETF 돌파", "P": "실적 갭", "C": "컵 돌파", "G": "돌파 갭"}
BONUS = 100.0
DEF = {"pg": 0.05, "pv": 2.0, "ch": 4, "crs": 0.5, "glo": 4.0, "ghi": 8.0, "gv": 6.0}


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre_etf = prep(C)
    Ue, Pe, BRKe, RELe, Re, bil = pre_etf
    df = yf.download(STK, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    got = [t for t in STK if t in df.columns.get_level_values(0)]
    S = pd.DataFrame({t: df[t]["Close"] for t in got}).reindex(C.index)
    S = S.dropna(axis=1, how="all"); U = list(S.columns)
    O = pd.DataFrame({t: df[t]["Open"] for t in U}).reindex(C.index)
    H = pd.DataFrame({t: df[t]["High"] for t in U}).reindex(C.index)
    V = pd.DataFrame({t: df[t]["Volume"] for t in U}).reindex(C.index)
    Sf = S.ffill(limit=5)
    ns, ne, nd = len(U), len(Ue), len(C.index)
    print("종목", ns, "ETF", ne, flush=True)

    # P 실적 갭
    season = np.array([8 <= dq_of(d) <= 55 for d in C.index])
    vavg = V.shift(1).rolling(20, min_periods=15).mean()
    hi60 = S.shift(1).rolling(60, min_periods=50).max()
    gapr = O / S.shift(1) - 1

    def sig_P(g, v):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = (gapr >= g) & (O > H.shift(1)) & (V >= v * vavg) & (S > hi60)
        return np.nan_to_num(m.values, nan=0).astype(bool) & season[:, None]

    # C 컵 돌파 (k1019 brk 와 같은 식)
    Pv = Sf.values
    Hs, PIVs = [], []
    for j in range(ns):
        h, pv = cup_state(Pv[:, j]); Hs.append(h); PIVs.append(pv)
    Hc = np.column_stack(Hs); PIV = np.column_stack(PIVs)
    Hp = np.vstack([np.full((1, ns), np.nan), Hc[:-1]])
    PIVp = np.vstack([np.full((1, ns), np.nan), PIV[:-1]])
    RS = (Sf / Sf.shift(126)).rank(axis=1, pct=True).values

    def sig_C(hmin, rs):
        with np.errstate(invalid="ignore"):
            s = (Hp >= hmin) & (Pv > PIVp) & (Pv <= PIVp * 1.05) & (RS >= rs)
        return np.nan_to_num(s, nan=0).astype(bool)

    # G 돌파 갭 (k1020 sig, 확인 없음)
    with np.errstate(invalid="ignore", divide="ignore"):
        GAP = (gapr * 100).values
        GBRK = (O > S.shift(1).rolling(60, min_periods=50).max()).values
        VR = (V / vavg).values

    def sig_G(lo, hi, v):
        with np.errstate(invalid="ignore"):
            g = (GAP >= lo) & (GAP < hi) & GBRK & (VR < v)
        return np.nan_to_num(g, nan=0).astype(bool)

    RELs = (Sf / Sf.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    Rs = Sf.pct_change().fillna(0.0).values
    P = np.hstack([Pe, Pv]); R = np.hstack([Re, Rs])
    BRK = np.nan_to_num(BRKe.astype(float), nan=0).astype(bool)
    zE = np.zeros((nd, ne), bool); zS = np.zeros((nd, ns), bool)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def go(fams, mode="tie", order=None, kw=None, bstep=BONUS):
        k = dict(DEF, **(kw or {}))
        fs = {"E": BRK if "E" in fams else zE,
              "P": sig_P(k["pg"], k["pv"]) if "P" in fams else zS,
              "C": sig_C(k["ch"], k["crs"]) if "C" in fams else zS,
              "G": sig_G(k["glo"], k["ghi"], k["gv"]) if "G" in fams else zS}
        sigS = fs["P"] | fs["C"] | fs["G"]
        SIG = np.hstack([fs["E"], sigS])
        if mode == "prio" and order:
            bon = {f: bstep * (len(order) - r) for r, f in enumerate(order)}
            be = bon.get("E", 0.0)
            bs = np.zeros((nd, ns))
            for f in ("P", "C", "G"):
                if f in fams:
                    bs = np.where(fs[f], np.maximum(bs, bon[f]), bs)
            REL = np.hstack([RELe + be, RELs + bs])
        else:
            REL = np.hstack([RELe, RELs])
        rk, tk, tr, hd = kick_x(C, idx, P, SIG, REL, R, bil)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        oosm = C.index >= pd.Timestamp(OOS_START)
        return {"fams": "".join(f for f in FAM if f in fams), "mode": mode, "order": "".join(order) if order else "", "bstep": bstep if mode == "prio" else 0,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "sig_oos": {f: int(fs[f][oosm].sum()) for f in FAM if f in fams}}

    # 지난 밤들 「지금 킥」 대용(ETF 돌파·변동성 맞춤 자리)
    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    etf_vw = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "tr_oos": tstat(kk[2], OOS_START, END)}

    F3 = {"E", "P", "C"}
    STEPS = [BONUS, 0.05, 0.10, 0.20]
    grid = []
    cur = go(F3, "tie"); grid.append(cur)
    print("지금(같은 순위)", cur["is"]["sharpe"], "|", cur["oos"], cur["tr_oos"], flush=True)
    for od in itertools.permutations(["E", "P", "C"]):
        for b in STEPS:
            r = go(F3, "prio", list(od), None, b); grid.append(r)
            print("격자", r["order"], b, r["is"]["sharpe"], r["is"]["cagr"], "|", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)

    best = max(grid, key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    ref_sh = max(etf_vw["oos"]["sharpe"], cur["oos"]["sharpe"])
    pce_strict = next(r for r in grid if r["order"] == "PCE" and r["bstep"] == BONUS)

    shake = []
    bmode = best["mode"]; bord = list(best["order"]) or None; bb = best["bstep"] or BONUS
    knobs = [("실적 갭 4%", {"pg": 0.04}, bb), ("실적 갭 6%", {"pg": 0.06}, bb), ("거래 1.6배", {"pv": 1.6}, bb), ("거래 2.4배", {"pv": 2.4}, bb),
             ("손잡이 3일", {"ch": 3}, bb), ("손잡이 5일", {"ch": 5}, bb), ("RS 40%", {"crs": 0.4}, bb), ("RS 60%", {"crs": 0.6}, bb)]
    if bmode == "prio" and bb < BONUS:
        knobs += [("덤 ×0.8", None, round(bb * 0.8, 4)), ("덤 ×1.2", None, round(bb * 1.2, 4))]
    for what, kw, b in knobs:
        r = go(F3, bmode, bord, kw, b); r["what"] = what; shake.append(r)
        print("흔들기", what, r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)
    # 같은 흔들기를 지금(같은 순위)에도 — 순서 효과가 손잡이와 상관없이 남는지
    shake_cur = []
    for what, kw, b in knobs[:8]:
        r = go(F3, "tie", None, kw); r["what"] = what; shake_cur.append(r)
        print("흔들기(지금)", what, r["oos"]["cagr"], r["oos"]["sharpe"], flush=True)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref_sh)}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([r["is"]["sharpe"] for r in grid]).rank().corr(pd.Series([r["oos"]["sharpe"] for r in grid]).rank()))
    by_first = {f: round(float(np.mean([r["oos"]["sharpe"] for r in grid if r["mode"] == "prio" and r["order"][0] == f])), 3) for f in "EPC"}
    by_step = {str(b): round(float(np.mean([r["oos"]["sharpe"] for r in grid if r["mode"] == "prio" and r["bstep"] == b])), 3) for b in STEPS}
    pair = [{"what": a["what"], "new_sh": a["oos"]["sharpe"], "cur_sh": c["oos"]["sharpe"], "new_cagr": a["oos"]["cagr"], "cur_cagr": c["oos"]["cagr"]}
            for a, c in zip(shake[:8], shake_cur)]
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_stocks": ns, "n_etf": ne, "trials": len(grid), "names": NAME,
           "spy": spy_row, "etf_current_vw": etf_vw, "current_EPC_tie": cur, "pce_strict": pce_strict, "best": best,
           "ref_sharpe": ref_sh, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "oos_sh_by_first": by_first, "oos_sh_by_step": by_step,
           "grid_beat_ref_oos": f"{sum(1 for r in grid if r['oos']['sharpe'] > ref_sh)}/{len(grid)}",
           "grid_beat_spy05_oos": f"{sum(1 for r in grid if r['oos']['ex'] >= 0.5)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for r in grid if all(ok(r['oos']).values()))}/{len(grid)}",
           "shake": [{"what": s["what"], "oos": s["oos"], "tr_oos": s["tr_oos"]} for s in shake],
           "shake_vs_current": pair,
           "grid": [{k: r[k] for k in ("fams", "mode", "order", "bstep", "tr_is", "tr_oos")} |
                    {"is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"], "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"],
                     "oos_mdd": r["oos"]["mdd"], "oos_ex": r["oos"]["ex"], "oos_turn": r["oos"].get("turn")} for r in grid],
           "note": "킥 칸 대용 = ETF 52주 돌파 + 미국 대형주 102개(실적 갭·컵 — 생존 편향·대형주만·실적 갭은 진짜 실적일 아님) · 실제 킥의 다른 신호(lead·cup_eye·고래 등)는 못 넣음 · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 빈 자리 BIL · 덤 100 = 엄격한 순서 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("ETF vw", etf_vw["oos"])
    print("지금 EPC tie", cur["oos"])
    print("고른", best["order"], best["bstep"], best["is"]["sharpe"], best["oos"], best["tr_oos"])
    print("첫 무리별", by_first, "덤별", by_step, "순위상관", round(rank_cor, 2))
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
