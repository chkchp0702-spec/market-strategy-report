"""🌙 10/27 밤 연구 #20 — 🧹 킥 돌파 칸 신호 종류 줄이기
  10/25 밤: ETF 돌파만 샤프 1.13 · 실적 갭만 1.19 · 둘을 같은 순위로 섞으면 1.08(회전 334→374%) — 지금 kick_params 는 신호 여러 종을 같은 순위로 섞음.
  질문: 신호 무리 몇 개를 쓰면 가장 좋은가 · 섞는다면 「같은 순위」 대신 「앞 구간에서 거래 성적 좋은 무리 먼저」가 나은가
  틀은 10/13~25 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 자리 5 · 하루 새 진입 2 · 다시 사기 10일 뒤 · 출구 −5%·+15%·15일 정체(+3%) · 빈 자리 BIL
  신호 무리 4개(긴 역사가 없는 개별 종목 신호는 미국 대형주 102개 대용 — 생존 편향·대형주만):
     E = 섹터·테마 ETF 52주 신고가 돌파 (k1012 prep)
     P = 실적 갭 5%·거래 2배·전날 고가 위·60일 최고 위·분기 끝 +8~55일 (k1025, 진짜 실적일 아님)
     C = 컵 돌파: 손잡이 ≥ 4일·종가 > 기준·기준+5% 안·RS(126일) 상위 50% (kick_params cup_min_handle 4·cup_min_rs 50)
     G = 돌파 갭 4~8%·거래 6배 미만·시가 > 앞 60일 최고 (kick_params gap_min/max/max_vol · 10/19 부터 꺼짐)
  방식: 무리 조합 15개 × (tie = 63일 상대강도 같은 순위 / prio = 앞 구간 혼자 돌린 거래 평균 순서로 먼저) — 하나짜리는 방식 같음 → 26조합
  「지금 킥」 = E+P+C tie (지금 pri: nh52·pead·cup 10 같음, gap 0) · 앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1%
→ market/lab/k1027_sigmix.json
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

OUT = Path("market/lab/k1027_sigmix.json")
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

    def go(fams, mode="tie", order=None, kw=None):
        k = dict(DEF, **(kw or {}))
        fs = {"E": BRK if "E" in fams else zE,
              "P": sig_P(k["pg"], k["pv"]) if "P" in fams else zS,
              "C": sig_C(k["ch"], k["crs"]) if "C" in fams else zS,
              "G": sig_G(k["glo"], k["ghi"], k["gv"]) if "G" in fams else zS}
        sigS = fs["P"] | fs["C"] | fs["G"]
        SIG = np.hstack([fs["E"], sigS])
        if mode == "prio" and order:
            bon = {f: BONUS * (len(order) - r) for r, f in enumerate(order)}
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
        return {"fams": "".join(f for f in FAM if f in fams), "mode": mode, "order": "".join(order) if order else "",
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "sig_oos": {f: int(fs[f][oosm].sum()) for f in FAM if f in fams}}

    # 지난 밤들 「지금 킥」 대용(ETF 돌파·변동성 맞춤 자리)
    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    etf_vw = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "tr_oos": tstat(kk[2], OOS_START, END)}

    grid = []
    single = {}
    for f in FAM:
        r = go({f}); grid.append(r); single[f] = r
        print("혼자", f, r["is"]["sharpe"], r["tr_is"], "|", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], r["tr_oos"], flush=True)

    def tmean(t):
        if isinstance(t, dict):
            for key in ("avg", "mean", "ret"):
                if key in t and t[key] is not None:
                    return float(t[key])
        return -9.0
    order_all = sorted(FAM, key=lambda f: -tmean(single[f]["tr_is"]))   # 앞 구간 거래 평균만으로 순서
    print("앞 구간 순서", order_all, flush=True)
    for n in (2, 3, 4):
        for comb in itertools.combinations(FAM, n):
            fams = set(comb)
            r = go(fams, "tie"); grid.append(r)
            print("격자", r["fams"], "tie", r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)
            od = [f for f in order_all if f in fams]
            r = go(fams, "prio", od); grid.append(r)
            print("격자", r["fams"], "prio", r["order"], r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)

    cur = next(r for r in grid if r["fams"] == "EPC" and r["mode"] == "tie")
    best = max(grid, key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    ref_sh = max(etf_vw["oos"]["sharpe"], cur["oos"]["sharpe"])

    # 흔들기 ±20%: 고른 조합에 든 무리의 손잡이 + 자리 수 대신 킥 칸은 고정
    shake = []
    bf = set(best["fams"]); bmode = best["mode"]; bord = list(best["order"]) or None
    knobs = []
    if "P" in bf:
        knobs += [("실적 갭 4%", {"pg": 0.04}), ("실적 갭 6%", {"pg": 0.06}), ("거래 1.6배", {"pv": 1.6}), ("거래 2.4배", {"pv": 2.4})]
    if "C" in bf:
        knobs += [("손잡이 3일", {"ch": 3}), ("손잡이 5일", {"ch": 5}), ("RS 40%", {"crs": 0.4}), ("RS 60%", {"crs": 0.6})]
    if "G" in bf:
        knobs += [("갭 3.2~6.4%", {"glo": 3.2, "ghi": 6.4}), ("갭 4.8~9.6%", {"glo": 4.8, "ghi": 9.6}), ("갭 거래 4.8배", {"gv": 4.8}), ("갭 거래 7.2배", {"gv": 7.2})]
    for what, kw in knobs:
        r = go(bf, bmode, bord, kw); r["what"] = what; shake.append(r)
        print("흔들기", what, r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref_sh)}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([r["is"]["sharpe"] for r in grid]).rank().corr(pd.Series([r["oos"]["sharpe"] for r in grid]).rank()))
    by_n = {}
    for n in (1, 2, 3, 4):
        rs = [r for r in grid if len(r["fams"]) == n]
        by_n[str(n)] = {"oos_sh": round(float(np.mean([r["oos"]["sharpe"] for r in rs])), 3),
                        "oos_cagr": round(float(np.mean([r["oos"]["cagr"] for r in rs])), 2),
                        "oos_turn": round(float(np.mean([r["oos"].get("turn") or 0 for r in rs])), 1)}
    by_mode = {m: round(float(np.mean([r["oos"]["sharpe"] for r in grid if r["mode"] == m and len(r["fams"]) > 1])), 3) for m in ("tie", "prio")}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_stocks": ns, "n_etf": ne, "trials": len(grid), "names": NAME, "is_order": order_all,
           "spy": spy_row, "etf_current_vw": etf_vw, "current_EPC_tie": cur, "best": best, "single": single,
           "ref_sharpe": ref_sh, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "by_n_families": by_n, "multi_by_mode_oos_sh": by_mode,
           "grid_beat_ref_oos": f"{sum(1 for r in grid if r['oos']['sharpe'] > ref_sh)}/{len(grid)}",
           "grid_beat_spy05_oos": f"{sum(1 for r in grid if r['oos']['ex'] >= 0.5)}/{len(grid)}",
           "shake": [{"what": s["what"], "oos": s["oos"], "tr_oos": s["tr_oos"]} for s in shake],
           "grid": [{k: r[k] for k in ("fams", "mode", "order", "tr_is", "tr_oos", "sig_oos")} |
                    {"is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"], "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"],
                     "oos_mdd": r["oos"]["mdd"], "oos_ex": r["oos"]["ex"], "oos_turn": r["oos"].get("turn")} for r in grid],
           "note": "킥 칸 대용 = ETF 52주 돌파 + 미국 대형주 102개(실적 갭·컵·돌파 갭 — 생존 편향·대형주만·실적 갭은 진짜 실적일 아님) · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 빈 자리 BIL · 「지금 킥」 = E+P+C 같은 순위와 ETF 돌파(vw) 중 샤프 높은 쪽 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("ETF vw", etf_vw["oos"])
    print("지금 EPC tie", cur["oos"], cur["tr_oos"])
    print("고른", best["fams"], best["mode"], best["order"], best["is"]["sharpe"], best["oos"], best["tr_oos"])
    print("무리 수별", by_n, "방식별", by_mode, "순위상관", round(rank_cor, 2))
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
