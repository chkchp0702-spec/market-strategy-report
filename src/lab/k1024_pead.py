"""🌙 10/24 밤 연구 #7 — 📊 실적 갭 보유 기간 (실적 발표 뒤 표류: 큰 갭 뒤 수십 일 더 오른다는 연구 → 15일보다 오래 들고 가면 나은가)
  틀은 10/13~23 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 슬롯 5 · 하루 새 진입 2 · 다시 사기 10일 뒤
  킥 칸 대용 = 미국 대형주 102개(k1019 와 같은 목록) 실적 갭: 시가 갭 ≥ 5% · 시가 > 전날 고가 · 거래량 ≥ 앞 20일 평균 2배 ·
     종가 > 앞 60일 최고 종가 · 실적 철(분기 끝 +8~55일) — src/kick_ideas_bt.py 「말한 그대로」 신호 (진짜 실적일 아님 · 생존 편향 · 대형주만)
  신호는 고정, 바꾸는 건 출구만:
     지금 = 손절 −5% · 익절 +15% · 15일 지나도 +3% 못 넘었으면 정리 (상한 없음)
     새 = 손절 s × 익절 t × 최대 보유 H일(그날 무조건 정리) · 15일 정체 정리 켬/끔
  손잡이: s(−5·−8·−12%) × t(+15·+25·없음) × H(15·20·30·40·60·없음) × 정체(켬·끔) = 108조합 · 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1%
→ market/lab/k1024_pead.json
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
from k1011_size import load, run_mix, seg, COST
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1014_volw import kick_vw
from k1019_cupbrk import STK

OUT = Path("market/lab/k1024_pead.json")
SIZE = 0.19
STOPS = [-0.05, -0.08, -0.12]
TAKES = [0.15, 0.25, None]
HOLDS = [15, 20, 30, 40, 60, None]
STALLS = [True, False]


def dq_of(d: pd.Timestamp) -> int:
    q_end_m = ((d.month - 1) // 3) * 3
    qe = pd.Timestamp(d.year - 1, 12, 31) if q_end_m == 0 else pd.Timestamp(d.year, q_end_m, 1) + pd.offsets.MonthEnd(0)
    return int((d - qe).days)


def kick_x(C, idx, P, SIG, REL, R, bil, stop=-0.05, take=0.15, hold=None, stall=True, time_d=15, time_min=0.03,
           slots=5, max_new=2, reentry=10):
    """신호 다음 날 종가 매수(전날 종가까지로 판단) · 손절/익절/최대 보유/정체 정리 → 다음 날 종가 정리"""
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades, helds = [], [], [], []
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
                trades.append((str(C.index[p["ent_i"]].date()), P[i, j] / p["entry"] - 1))
                helds.append(p["held"])
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j, want in pend_in:
            if j in pos or len(pos) >= slots or np.isnan(P[i, j]):
                continue
            w = min(want, cash)
            if w <= 0:
                continue
            pos[j] = {"w": w, "entry": P[i, j], "max": P[i, j], "held": 0, "ent_i": i}
            cash -= w; tv += w
        pend_in, pend_out = [], []
        c = tv * COST
        r -= c; cash -= c
        rets.append(r); turns.append(tv)
        for j, p in pos.items():
            if p["ent_i"] == i:
                continue
            px = P[i, j]
            if np.isnan(px):
                continue
            p["held"] += 1
            p["max"] = max(p["max"], px)
            g = px / p["entry"] - 1
            out = g <= stop or (take is not None and g >= take) or (hold is not None and p["held"] >= hold) \
                or (stall and p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min)
            if out:
                pend_out.append(j)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [(REL[i, j], j) for j in np.flatnonzero(SIG[i]) if j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            for _, j in cand[:min(free, max_new)]:
                pend_in.append((j, 1.0 / slots))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, helds


def fwd_stats(SIG, P, dates, a, b, hs=(5, 10, 15, 20, 30, 40, 60)):
    """신호 다음 날 종가에 샀다면 h일 뒤 수익 평균(비용 0.2% 왕복 뺌) — 표류가 언제까지 이어지나"""
    o = {}
    ii, jj = np.nonzero(SIG)
    for h in hs:
        x = []
        for i, j in zip(ii, jj):
            d = str(dates[i].date())
            if not (a <= d <= b) or i + 1 + h >= len(dates):
                continue
            e, f = P[i + 1, j], P[i + 1 + h, j]
            if np.isnan(e) or np.isnan(f):
                continue
            x.append(f / e - 1 - 0.002)
        o[h] = {"n": len(x), "avg": round(float(np.mean(x)) * 100, 2) if x else None,
                "win": round(float(np.mean([v > 0 for v in x])) * 100) if x else None}
    return o


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre_etf = prep(C)
    bil = pre_etf[5]
    df = yf.download(STK, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    got = [t for t in STK if t in df.columns.get_level_values(0)]
    S = pd.DataFrame({t: df[t]["Close"] for t in got}).reindex(C.index)
    S = S.dropna(axis=1, how="all"); U = list(S.columns)
    O = pd.DataFrame({t: df[t]["Open"] for t in U}).reindex(C.index)
    H = pd.DataFrame({t: df[t]["High"] for t in U}).reindex(C.index)
    V = pd.DataFrame({t: df[t]["Volume"] for t in U}).reindex(C.index)
    Sf = S.ffill(limit=5)
    season = np.array([8 <= dq_of(d) <= 55 for d in C.index])
    with np.errstate(invalid="ignore", divide="ignore"):
        g = ((O / S.shift(1) - 1) >= 0.05) & (O > H.shift(1)) \
            & (V >= 2 * V.shift(1).rolling(20, min_periods=15).mean()) \
            & (S > S.shift(1).rolling(60, min_periods=50).max())
    SIG = np.nan_to_num(g.values, nan=0).astype(bool) & season[:, None]
    REL = (Sf / Sf.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    R_ = Sf.pct_change().fillna(0.0).values
    P = Sf.values
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    fwd = {"is": fwd_stats(SIG, P, C.index, START, IS_END), "oos": fwd_stats(SIG, P, C.index, OOS_START, END)}

    def go(stop, take, hold, stall):
        rk, tk, tr, hd = kick_x(C, idx, P, SIG, REL, R_, bil, stop, take, hold, stall)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "avg_hold": round(float(np.mean(hd)), 1) if hd else None}

    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    etf = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "tr_oos": tstat(kk[2], OOS_START, END)}
    cur = go(-0.05, 0.15, None, True)
    grid = []
    for s in STOPS:
        for t in TAKES:
            for h in HOLDS:
                for st in STALLS:
                    r = go(s, t, h, st); r.update({"stop": s, "take": t, "hold": h, "stall": st}); grid.append(r)
                    print("격자", s, t, h, st, r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["sharpe"], r["tr_oos"], r["avg_hold"], flush=True)
    best = max(grid, key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    s0, t0, h0, st0 = best["stop"], best["take"], best["hold"], best["stall"]
    shake = []
    sh_list = [(f"손절 {s0 * 0.8:.3f}", (s0 * 0.8, t0, h0, st0)), (f"손절 {s0 * 1.2:.3f}", (s0 * 1.2, t0, h0, st0))]
    if t0:
        sh_list += [(f"익절 {t0 * 0.8:.3f}", (s0, t0 * 0.8, h0, st0)), (f"익절 {t0 * 1.2:.3f}", (s0, t0 * 1.2, h0, st0))]
    if h0:
        sh_list += [(f"보유 {round(h0 * 0.8)}", (s0, t0, round(h0 * 0.8), st0)), (f"보유 {round(h0 * 1.2)}", (s0, t0, round(h0 * 1.2), st0))]
    for what, kw in sh_list:
        r = go(*kw); r["what"] = what; shake.append(r)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > etf["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([r["is"]["sharpe"] for r in grid]).rank().corr(pd.Series([r["oos"]["sharpe"] for r in grid]).rank()))
    beat_cur = sum(1 for r in grid if r["oos"]["sharpe"] > etf["oos"]["sharpe"])
    beat_pead_cur = sum(1 for r in grid if r["oos"]["sharpe"] > cur["oos"]["sharpe"])
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_stocks": len(U), "events_is": int(SIG[(C.index >= pd.Timestamp(START)) & (C.index <= pd.Timestamp(IS_END))].sum()),
           "events_oos": int(SIG[C.index >= pd.Timestamp(OOS_START)].sum()), "trials": len(grid),
           "spy": spy_row, "etf_current": etf, "pead_current_exits": cur, "best": best, "forward": fwd,
           "check": chk, "shake_ok": shake_ok, "verdict": verdict, "is_oos_rank_cor": round(rank_cor, 2),
           "grid_beat_etf_current_oos": f"{beat_cur}/{len(grid)}", "grid_beat_pead_current_oos": f"{beat_pead_cur}/{len(grid)}",
           "shake": shake,
           "grid": [{k: r[k] for k in ("stop", "take", "hold", "stall", "avg_hold", "tr_is", "tr_oos")} |
                    {"is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"], "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"],
                     "oos_mdd": r["oos"]["mdd"], "oos_turn": r["oos"].get("turn")} for r in grid],
           "note": "킥 칸 대용 = 미국 대형주 102개 실적 갭(갭≥5%·전날 고가 위·거래 2배·60일 최고 위·분기 끝 +8~55일) — 진짜 실적일 아님·생존 편향·대형주만 · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 「지금 킥」= ETF 52주 돌파 대용(10/13~23 과 같음) · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("종목", len(U), "신호 앞/뒤", out["events_is"], out["events_oos"])
    print("SPY", spy_row["oos"])
    print("ETF 지금", etf["oos"], etf["tr_oos"])
    print("실적갭 지금 출구", cur["oos"], cur["tr_is"], cur["tr_oos"], cur["avg_hold"])
    print("고른", s0, t0, h0, st0, best["is"]["sharpe"], best["oos"], best["tr_oos"], best["avg_hold"])
    print("표류", fwd)
    print("순위상관", round(rank_cor, 2), "ETF 지금보다", beat_cur, "실적갭 지금보다", beat_pead_cur, "/", len(grid))
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
