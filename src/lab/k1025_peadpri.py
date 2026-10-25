"""🌙 10/25 밤 연구 #19 — 📊 실적 갭을 킥 돌파 칸의 주 신호로 (우선순위 올리기)
  10/24 밤 덤 발견: 대형주 대용 실적 갭 + 지금 출구가 ETF 돌파(지금 킥 대용)보다 두 구간 모두 샤프가 나음 → 둘을 섞을 때 누구를 먼저 담나
  틀은 10/13~24 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 슬롯 5 · 하루 새 진입 2 · 다시 사기 10일 뒤 · 출구 −5%·+15%·15일 정체(+3%)
  신호 두 무리:
     ETF = 섹터·테마 ETF 52주 신고가 돌파(k1012 prep) · 실적 갭 = 미국 대형주 102개(k1019 목록) 갭 ≥ g · 시가 > 전날 고가 ·
     거래량 ≥ 앞 20일 평균 v배 · 종가 > 앞 60일 최고 · 분기 끝 +8~55일 (진짜 실적일 아님 · 생존 편향 · 대형주만)
  방식: etf(ETF만 = 지난 밤들 「지금 킥」 대용) · pead(실적 갭만) · pead_first(실적 갭 먼저, 남는 자리에 ETF) ·
        tie(같은 순위, 63일 상대강도 순 — 지금 kick_params pri nh52 10 = pead 10 과 가장 가까움) · etf_first(ETF 먼저)
  손잡이: 방식 4 × g(4·5·6%) × v(1.5·2·3배) + etf 1 = 37조합 · 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1%
  빈 자리 돈은 지난 밤들과 같이 BIL(현금) — 10/19 부터 실제 킥은 기본 칸 비중으로 굴림(park), 비교는 같은 조건끼리
→ market/lab/k1025_peadpri.json
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
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1014_volw import kick_vw
from k1019_cupbrk import STK
from k1024_pead import kick_x, dq_of

OUT = Path("market/lab/k1025_peadpri.json")
SIZE = 0.19
MODES = ["pead", "pead_first", "tie", "etf_first"]
GAPS = [0.04, 0.05, 0.06]
VOLS = [1.5, 2.0, 3.0]
BONUS = 100.0


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
    season = np.array([8 <= dq_of(d) <= 55 for d in C.index])
    vavg = V.shift(1).rolling(20, min_periods=15).mean()
    hi60 = S.shift(1).rolling(60, min_periods=50).max()
    gap = O / S.shift(1) - 1

    def pead_sig(g, v):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = (gap >= g) & (O > H.shift(1)) & (V >= v * vavg) & (S > hi60)
        return np.nan_to_num(m.values, nan=0).astype(bool) & season[:, None]

    RELs = (Sf / Sf.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    Rs = Sf.pct_change().fillna(0.0).values
    Ps = Sf.values
    ne, ns = len(Ue), len(U)
    P = np.hstack([Pe, Ps]); R = np.hstack([Re, Rs])
    BRK = np.nan_to_num(BRKe.astype(float), nan=0).astype(bool)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def go(mode, g=0.05, v=2.0):
        sp = pead_sig(g, v) if mode != "etf" else np.zeros((len(C.index), ns), bool)
        se = BRK if mode != "pead" else np.zeros_like(BRK)
        SIG = np.hstack([se, sp])
        be = BONUS if mode == "etf_first" else 0.0
        bs = BONUS if mode == "pead_first" else 0.0
        REL = np.hstack([RELe + be, RELs + bs])
        rk, tk, tr, hd = kick_x(C, idx, P, SIG, REL, R, bil)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        n_p = sum(1 for _ in tr)
        return {"mode": mode, "gap": g, "vol": v,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "sig_oos": int(sp[C.index >= pd.Timestamp(OOS_START)].sum()), "n_tr": n_p}

    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    etf_vw = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "tr_oos": tstat(kk[2], OOS_START, END)}
    etf = go("etf")
    print("ETF(vw)", etf_vw["oos"], "ETF(x)", etf["oos"], flush=True)
    grid = [etf]
    for m in MODES:
        for g in GAPS:
            for v in VOLS:
                r = go(m, g, v); grid.append(r)
                print("격자", m, g, v, r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], r["tr_oos"], flush=True)
    cur = next(r for r in grid if r["mode"] == "tie" and r["gap"] == 0.05 and r["vol"] == 2.0)
    best = max(grid, key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    ref_sh = max(etf_vw["oos"]["sharpe"], cur["oos"]["sharpe"])
    shake = []
    if best["mode"] != "etf":
        m0, g0, v0 = best["mode"], best["gap"], best["vol"]
        for what, kw in [(f"갭 {g0 * 0.8:.3f}", (m0, g0 * 0.8, v0)), (f"갭 {g0 * 1.2:.3f}", (m0, g0 * 1.2, v0)),
                         (f"거래 {v0 * 0.8:.2f}배", (m0, g0, v0 * 0.8)), (f"거래 {v0 * 1.2:.2f}배", (m0, g0, v0 * 1.2))]:
            r = go(*kw); r["what"] = what; shake.append(r)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref_sh)}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([r["is"]["sharpe"] for r in grid]).rank().corr(pd.Series([r["oos"]["sharpe"] for r in grid]).rank()))
    by_mode = {}
    for m in ["etf"] + MODES:
        rs = [r for r in grid if r["mode"] == m]
        by_mode[m] = {"is_sh": round(float(np.mean([r["is"]["sharpe"] for r in rs])), 3),
                      "oos_sh": round(float(np.mean([r["oos"]["sharpe"] for r in rs])), 3),
                      "oos_cagr": round(float(np.mean([r["oos"]["cagr"] for r in rs])), 2),
                      "oos_mdd": round(float(np.mean([r["oos"]["mdd"] for r in rs])), 2)}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_stocks": ns, "n_etf": ne, "trials": len(grid),
           "spy": spy_row, "etf_current_vw": etf_vw, "etf_only": etf, "tie_current": cur, "best": best,
           "ref_sharpe": ref_sh, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "by_mode": by_mode,
           "grid_beat_ref_oos": f"{sum(1 for r in grid if r['oos']['sharpe'] > ref_sh)}/{len(grid)}",
           "grid_beat_spy05_oos": f"{sum(1 for r in grid if r['oos']['ex'] >= 0.5)}/{len(grid)}",
           "shake": shake,
           "grid": [{k: r[k] for k in ("mode", "gap", "vol", "tr_is", "tr_oos", "sig_oos")} |
                    {"is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"], "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"],
                     "oos_mdd": r["oos"]["mdd"], "oos_ex": r["oos"]["ex"], "oos_turn": r["oos"].get("turn")} for r in grid],
           "note": "킥 칸 대용 = ETF 52주 돌파 + 미국 대형주 102개 실적 갭(진짜 실적일 아님·생존 편향·대형주만) · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 빈 자리 BIL · 「지금 킥」 비교 = ETF 돌파 대용(vw)과 tie 5%·2배 중 샤프 높은 쪽 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("tie 지금", cur["oos"], cur["tr_oos"])
    print("고른", best["mode"], best["gap"], best["vol"], best["is"]["sharpe"], best["oos"], best["tr_oos"])
    print("방식별", by_mode)
    print("순위상관", round(rank_cor, 2))
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
