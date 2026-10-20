"""🌙 10/20 밤 연구 #10 — 📈 돌파 갭: 「갭 lo~hi% · 거래량 v배 미만 · 다음 날 갭 안 메움」만 + 갭 메우면(종가 < 갭 전날 종가) 바로 정리
  틀은 10/13~19 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 출구 −5%·+15%·15일(+3% 못 넘으면 정리) · 슬롯 5·하루 새 진입 2
  킥 칸 대용 = 미국 대형주 102개(k1019 와 같은 목록) 시가·저가·종가·거래량으로 찾은 돌파 갭 (스캐너 장부는 2026-10 이후뿐 → 긴 역사 없음 ·
     지금 살아남은 대형주라 생존 편향 · 대형주는 갭이 드물고 작음 · 일본·한국·소형주 못 봄)
  갭 날 g: 시가/전날 종가 −1 = 갭 · 시가 > 앞 60일 최고 종가(돌파) · 거래량 ÷ 앞 20일 평균 = 거래 배수
  지금(바꾸기 전 kick_params) = 갭 4~8% · 거래 6배 미만 · 갭 날 종가에 판단 → 다음 날 종가 매수 · 갭 메우면 정리(gap_fill_exit)
  새 규칙 = 갭 lo~hi% · 거래 v배 미만 · (확인 켜면) 다음 날 저가 > 갭 전날 종가(안 메움)일 때 그날 종가 판단 → 그다음 날 종가 매수 · 갭 메우면 정리
  손잡이: lo(3·4·5) × hi(7·8·10) × v(2·3·4·6) × 확인(끔·켬) = 72조합 · 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1% 비용
→ market/lab/k1020_gap.json
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

OUT = Path("market/lab/k1020_gap.json")
SIZE = 0.19
LOS = [3, 4, 5]
HIS = [7, 8, 10]
VS = [2, 3, 4, 6]


def kick_gap(C, idx, U, Pv, SIG, FL, REL, R, bil, fill_exit=True, stop=-0.05, take=0.15, time_d=15, time_min=0.03,
             slots=5, max_new=2, reentry=10):
    """kick_vw(같은 크기) + 갭 메움 정리: 진입 신호 때 정한 바닥(갭 전날 종가) 아래로 종가가 내려가면 다음 날 정리"""
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades = [], [], []
    nfill = 0
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
        for j, want, fl in pend_in:
            if j in pos or len(pos) >= slots or np.isnan(Pv[i, j]):
                continue
            w = min(want, cash)
            if w <= 0:
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i, "fl": fl}
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
            filled = fill_exit and not np.isnan(p["fl"]) and px < p["fl"]
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min) or filled:
                pend_out.append(j)
                if filled and not (g <= stop):
                    nfill += 1
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [(REL[i, j], j) for j in np.flatnonzero(SIG[i]) if j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            for _, j in cand[:min(free, max_new)]:
                pend_in.append((j, 1.0 / slots, FL[i, j]))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, nfill


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
    O = pd.DataFrame({t: df[t]["Open"] for t in got}).reindex(C.index)
    Lo = pd.DataFrame({t: df[t]["Low"] for t in got}).reindex(C.index)
    V = pd.DataFrame({t: df[t]["Volume"] for t in got}).reindex(C.index)
    S = S.dropna(axis=1, how="all"); U = list(S.columns)
    O, Lo, V = O[U], Lo[U], V[U]
    Sf = S.ffill(limit=5)
    Cp = S.shift(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        GAP = ((O / Cp - 1) * 100).values
        BRK = (O > S.shift(1).rolling(60, min_periods=50).max()).values
        VR = (V / V.shift(1).rolling(20, min_periods=15).mean()).values
        HOLD = (Lo > Cp.shift(1)).values           # 다음 날(오늘) 저가 > 갭 전날 종가 = 안 메움
    CP = Cp.values
    CP2 = Cp.shift(1).values
    REL = (Sf / Sf.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    R_ = Sf.pct_change().fillna(0.0).values
    P = Sf.values
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def sig(lo, hi, v, conf):
        with np.errstate(invalid="ignore"):
            g = (GAP >= lo) & (GAP < hi) & BRK & (VR < v)
        g = np.nan_to_num(g, nan=0).astype(bool)
        if not conf:
            return g, CP
        gp = np.vstack([np.zeros((1, g.shape[1]), bool), g[:-1]])
        return gp & np.nan_to_num(HOLD, nan=0).astype(bool), CP2

    def go(lo, hi, v, conf, fill_exit=True):
        s, fl = sig(lo, hi, v, conf)
        rk, tk, tr, nf = kick_gap(C, idx, U, P, s, fl, REL, R_, bil, fill_exit)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        knav = (1 + rk).cumprod()
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_oos": seg(knav, spy, OOS_START, END, tk),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END), "fill_exits": nf,
                "events": int(s[(C.index >= pd.Timestamp(START))].sum())}

    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    etf = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "tr_oos": tstat(kk[2], OOS_START, END)}
    cur = go(4, 8, 6, False)
    grid = []
    for lo in LOS:
        for hi in HIS:
            for v in VS:
                for cf in (False, True):
                    g = go(lo, hi, v, cf); g.update({"lo": lo, "hi": hi, "v": v, "conf": cf}); grid.append(g)
                    print("격자", lo, hi, v, cf, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["sharpe"], g["tr_oos"], flush=True)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    lo0, hi0, v0, cf0 = best["lo"], best["hi"], best["v"], best["conf"]
    shake = []
    for what, kw in ((f"lo={lo0 * 0.8:.1f}", (lo0 * 0.8, hi0, v0, cf0)), (f"lo={lo0 * 1.2:.1f}", (lo0 * 1.2, hi0, v0, cf0)),
                     (f"hi={hi0 * 0.8:.1f}", (lo0, hi0 * 0.8, v0, cf0)), (f"hi={hi0 * 1.2:.1f}", (lo0, hi0 * 1.2, v0, cf0)),
                     (f"v={v0 * 0.8:.1f}", (lo0, hi0, v0 * 0.8, cf0)), (f"v={v0 * 1.2:.1f}", (lo0, hi0, v0 * 1.2, cf0))):
        if kw[0] >= kw[1]:
            continue
        g = go(*kw); g["what"] = what; shake.append(g)
    nofill = go(lo0, hi0, v0, cf0, fill_exit=False)
    hyp = go(4, 8, 3, True)   # 후보 표에 적힌 그대로(4~8%·3배 미만·안 메움)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > etf["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(all(all(ok(s["oos"]).values()) for s in shake))
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
    beat_cur = sum(1 for g in grid if g["oos"]["sharpe"] > etf["oos"]["sharpe"])
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_stocks": len(U), "spy": spy_row, "etf_current": etf, "gap_current": cur, "best": best, "hypothesis_4_8_v3_hold": hyp,
           "best_no_fill_exit": nofill, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "grid_beat_etf_current_oos": f"{beat_cur}/{len(grid)}", "shake": shake,
           "grid": [{"lo": g["lo"], "hi": g["hi"], "v": g["v"], "conf": g["conf"], "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"],
                     "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_turn": g["oos"].get("turn"),
                     "tr_is": g["tr_is"], "tr_oos": g["tr_oos"], "fill_exits": g["fill_exits"], "events": g["events"]} for g in grid],
           "note": "킥 칸 대용 = 미국 대형주 102개 돌파 갭(시가 > 앞 60일 최고 종가) · 생존 편향·대형주라 갭 드묾·해외/소형 없음 · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 비교 「지금 킥」= ETF 52주 돌파 대용(10/13~19 와 같음) · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("종목", len(U))
    print("SPY", spy_row["oos"])
    print("ETF 지금", etf["oos"], etf["tr_oos"])
    print("갭 지금(4~8·6배·확인없음)", cur["oos"], cur["tr_is"], cur["tr_oos"], cur["events"])
    print("가설(4~8·3배·안 메움)", hyp["oos"], hyp["tr_oos"])
    print("고른", lo0, hi0, v0, cf0, best["is"]["sharpe"], best["oos"], best["tr_is"], best["tr_oos"])
    print("메움 정리 끔", nofill["oos"], nofill["tr_oos"])
    print("순위상관", round(rank_cor, 2), "ETF 지금보다 나은 조합", beat_cur, "/", len(grid))
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
