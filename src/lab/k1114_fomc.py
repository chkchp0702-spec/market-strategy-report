"""🌙 11/14 밤 연구 #34 — 🏛️ FOMC 발표 전날 표류 (연준 회의 발표 무렵 하루~이틀만 현금 → S&P/나스닥)
  왜: Lucca·Moench 2015 「The Pre-FOMC Announcement Drift」(J. Finance 70(1)) https://doi.org/10.1111/jofi.12196
      — 1994~2011 미국 주식 초과수익의 큰 몫이 연준 발표 전 24시간에 몰림.
      11/11·11/12 밤: 「빈 자리에 날짜로 정한 짧은 자리」만 통했지만 회전 2배라 비용에 무너짐 → 1년 8번뿐인 날짜로.
  회의 날짜(정기 회의 발표일)는 미리 공지됨 → 미래 자료 아님. 2020-03 정기 회의는 취소(긴급 회의로 대체)라 뺌.
  바꾸는 것(지금 킥 틀 위에 덧씌우기 — 기본 칸·킥 칸 그대로):
    x      발표 무렵 옮길 크기(전체 대비) 10·20·30%·「있는 현금 전부」(1.0) — 있는 현금(기본 칸 BIL 몫) 넘게는 못 옮김
    win    t = 발표 전날 종가 매수 → 발표일 종가 매도 / pre2 = 이틀 전 종가 → 발표일 종가 / post = 전날 종가 → 다음 날 종가
    asset  SPY / QQQ
    src    cash = 현금에서만 / cashgld = 현금 + 금 칸에서도
    = 4 × 3 × 2 × 2 = 48조합
  비교: 지금 킥(섹터·테마 ETF 52주 돌파 대용, C안 뼈대 × 변동성 맞춤, 킥 칸 19%) · S&P
  확인: 같은 덧씌우기를 발표일 ±10거래일 「가짜 날짜」로 · 발표일 S&P 하루 초과수익 앞/뒤 구간
  회전율 × 0.1%(드나들 때 모두) · 앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 흔들기 x ×0.8/×1.2 · 자산 반대 · 비용 0.2%
→ market/lab/k1114_fomc.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import run_mix, seg, UNIV, COST
from k1013_trend import base_vol
from k1030_slip import load_ohlc
from k1105_resmom import prep
from k1113_trail import kick_trail

OUT = Path("market/lab/k1114_fomc.json")
SIZE = 0.19

FOMC = """
2008-01-30 2008-03-18 2008-04-30 2008-06-25 2008-08-05 2008-09-16 2008-10-29 2008-12-16
2009-01-28 2009-03-18 2009-04-29 2009-06-24 2009-08-12 2009-09-23 2009-11-04 2009-12-16
2010-01-27 2010-03-16 2010-04-28 2010-06-23 2010-08-10 2010-09-21 2010-11-03 2010-12-14
2011-01-26 2011-03-15 2011-04-27 2011-06-22 2011-08-09 2011-09-21 2011-11-02 2011-12-13
2012-01-25 2012-03-13 2012-04-25 2012-06-20 2012-08-01 2012-09-13 2012-10-24 2012-12-12
2013-01-30 2013-03-20 2013-05-01 2013-06-19 2013-07-31 2013-09-18 2013-10-30 2013-12-18
2014-01-29 2014-03-19 2014-04-30 2014-06-18 2014-07-30 2014-09-17 2014-10-29 2014-12-17
2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09
""".split()

XS = [0.10, 0.20, 0.30, 1.0]
WINS = {"t": (0, 0), "pre2": (-1, 0), "post": (0, 1)}   # 발표일 기준 보유하는 날(하루 수익이 잡히는 날) 범위
ASSETS = ["SPY", "QQQ"]
SRCS = ["cash", "cashgld"]


def base_weights(C, reg, lb=20, tgt=18.0, floor=0.5):
    """base_vol 목표 비중(전날 기준) — 그날 옮길 수 있는 현금·금 몫"""
    G = {"SPY": .475, "QQQ": .475, "GLD": .05}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(lb).std() * math.sqrt(252) * 100
    sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
    regv = reg.reindex(C.index).fillna(False)
    gld = regv.map({True: G["GLD"], False: Rd["GLD"]}).astype(float)
    eq = regv.map({True: G["SPY"] + G["QQQ"], False: Rd["SPY"] + Rd["QQQ"]}).astype(float) * sc
    bil = (1 - eq - gld).clip(lower=0)
    return bil.shift(2), gld.shift(2)   # 들어가기 전날 종가 기준(이틀 전 목표)로 보수적으로


def overlay(C, idx, base_r, base_t, days, x, win, asset, src, cost=COST):
    """발표일 목록(days) 주변 win 날 동안 x 를 현금(·금)에서 asset 으로 — 하루 수익·회전 더하기"""
    R = C[[asset, "BIL", "GLD"]].pct_change().reindex(idx).fillna(0.0)
    cw, gw = base_weights(C, REG)
    cw = cw.reindex(idx).fillna(0.0) * (1 - SIZE)
    gw = gw.reindex(idx).fillna(0.0) * (1 - SIZE)
    pos = {d: i for i, d in enumerate(idx)}
    r = base_r.copy()
    t = base_t.copy()
    a, b = WINS[win]
    n_ev, moved = 0, []
    for d in days:
        if d not in pos:
            continue
        k = pos[d]
        lo, hi = k + a, k + b
        if lo < 2 or hi >= len(idx):
            continue
        xc = min(x, float(cw.iloc[lo]))
        xg = min(max(x - xc, 0.0), float(gw.iloc[lo])) if src == "cashgld" else 0.0
        if xc + xg <= 0:
            continue
        n_ev += 1; moved.append(xc + xg)
        for j in range(lo, hi + 1):
            r.iloc[j] += xc * (R[asset].iloc[j] - R["BIL"].iloc[j]) + xg * (R[asset].iloc[j] - R["GLD"].iloc[j])
        tv = 2 * (xc + xg)   # 들어갈 때·나올 때
        r.iloc[hi] -= tv * cost
        t.iloc[hi] += tv
    return r, t, {"n": n_ev, "avg_moved": round(float(np.mean(moved)) * 100, 1) if moved else 0.0}


def ev_stats(C, idx, days, a, b):
    """발표일 무렵 SPY − BIL 초과수익(이벤트당) 앞/뒤"""
    R = C[["SPY", "QQQ", "BIL"]].pct_change().reindex(idx).fillna(0.0)
    pos = {d: i for i, d in enumerate(idx)}
    out = {}
    for nm, lo_, hi_ in (("is", START, IS_END), ("oos", OOS_START, str(idx[-1].date()))):
        for asset in ("SPY", "QQQ"):
            v = []
            for d in days:
                if d not in pos or not (lo_ <= str(d.date()) <= hi_):
                    continue
                k = pos[d]
                if k + a < 1 or k + b >= len(idx):
                    continue
                g = float(np.prod([1 + R[asset].iloc[j] for j in range(k + a, k + b + 1)]) -
                          np.prod([1 + R["BIL"].iloc[j] for j in range(k + a, k + b + 1)]))
                v.append(g)
            v = np.array(v)
            out[f"{nm}_{asset}"] = {"n": int(len(v)), "avg_bp": round(float(v.mean()) * 1e4, 1) if len(v) else None,
                                    "win": round(float((v > 0).mean()) * 100, 1) if len(v) else None,
                                    "t": round(float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))), 2) if len(v) > 2 else None}
    # 모든 날 평균(비교)
    for nm, lo_, hi_ in (("is", START, IS_END), ("oos", OOS_START, str(idx[-1].date()))):
        m = (R.index >= lo_) & (R.index <= hi_)
        out[f"{nm}_allday_SPY_bp"] = round(float((R["SPY"][m] - R["BIL"][m]).mean()) * 1e4 * (b - a + 1), 1)
    return out


REG = None


def main():
    global REG
    C, _, _ = load_ohlc()
    REG = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    days_all = [pd.Timestamp(s) for s in FOMC]
    miss = [str(d.date()) for d in days_all if d not in set(C.index) and d <= idx[-1]]
    days = [d for d in days_all if d in set(idx)]
    print("발표일", len(days), "거래일 아님", miss, flush=True)
    rb, tb = base_vol(C, REG, idx)
    pre = prep(C, UNIV)
    rk, tk, _ = kick_trail(C, idx, pre, trail=None)
    nav0, td0 = run_mix(rb, tb, (rk, tk, None), REG, SIZE, SIZE)
    base_r = nav0.pct_change().fillna(0.0)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    cur = {"is": seg(nav0, spy, START, IS_END, td0), "oos": seg(nav0, spy, OOS_START, END, td0)}
    print("지금", cur["is"]["sharpe"], cur["oos"], flush=True)

    def run(x, win, asset, src, dd=None, cost=COST):
        r, t, info = overlay(C, idx, base_r, td0, dd if dd is not None else days, x, win, asset, src, cost)
        nav = (1 + r).cumprod()
        return {"x": x, "win": win, "asset": asset, "src": src, "ev": info,
                "is": seg(nav, spy, START, IS_END, t), "oos": seg(nav, spy, OOS_START, END, t)}

    grid = []
    for x in XS:
        for w in WINS:
            for a in ASSETS:
                for s in SRCS:
                    g = run(x, w, a, s)
                    grid.append(g)
                    print(x, w, a, s, g["ev"], g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"]["ex"], flush=True)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    ref = cur["oos"]["sharpe"]
    shake = []
    for k in (0.8, 1.2):
        x2 = round(min(best["x"] * k, 1.0), 3) if best["x"] < 1.0 else round(best["x"] * k, 3)
        g = run(x2, best["win"], best["asset"], best["src"]); g["what"] = f"크기 {x2*100:.0f}%"; shake.append(g)
    g = run(best["x"], best["win"], "QQQ" if best["asset"] == "SPY" else "SPY", best["src"]); g["what"] = "자산 " + g["asset"]; shake.append(g)
    g = run(best["x"], best["win"], best["asset"], best["src"], cost=0.002); g["what"] = "비용 0.2%"; shake.append(g)
    # 가짜 날짜(±10거래일)
    pos = {d: i for i, d in enumerate(idx)}
    plac = []
    for sh in (-10, 10):
        dd = [idx[pos[d] + sh] for d in days if 0 <= pos[d] + sh < len(idx)]
        g = run(best["x"], best["win"], best["asset"], best["src"], dd=dd); g["what"] = f"가짜 날짜 {sh:+d}거래일"; plac.append(g)

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
                "oos_ex_vs_cur": round(float(np.mean([g["oos"]["cagr"] for g in xs])) - cur["oos"]["cagr"], 2),
                "is_sh": round(float(np.mean([g["is"]["sharpe"] for g in xs])), 3)}
    by = {f"x_{x}": avg("x", x) for x in XS}
    by.update({f"win_{w}": avg("win", w) for w in WINS})
    by.update({f"asset_{a}": avg("asset", a) for a in ASSETS})
    by.update({f"src_{s}": avg("src", s) for s in SRCS})
    ev = {w: ev_stats(C, idx, days, *WINS[w]) for w in WINS}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(grid), "n_days": len(days), "not_trading_days": miss, "spy": spy_row, "current": cur,
           "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict, "shake": shake, "placebo": plac,
           "is_oos_rank_cor": round(rc, 2), "by": by, "event": ev,
           "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
           "grid": [{"x": g["x"], "win": g["win"], "asset": g["asset"], "src": g["src"], "n": g["ev"]["n"], "moved": g["ev"]["avg_moved"],
                     "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"], "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"],
                     "oos_mdd": g["oos"]["mdd"], "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn")} for g in grid],
           "note": "지금 킥 = C안 뼈대 × 변동성 맞춤 + 킥 칸 19%(섹터·테마 ETF 52주 돌파 대용, 빈 자리 BIL — 실전 🅿️ park 는 빼고 계산) · "
                   "덧씌우기 = 정기 FOMC 발표일 무렵 x 만큼 현금(·금)을 SPY/QQQ 로, 옮길 수 있는 몫은 이틀 전 목표 비중의 현금(·금) 한도 · "
                   "win t = 전날 종가→발표일 종가 · pre2 = 이틀 전 종가→발표일 종가 · post = 전날 종가→다음 날 종가 · "
                   "회전율×0.1% · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 매수 추천 아님"}
    for s in shake + plac:
        print("  ", s["what"], s["ev"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    print("이벤트", json.dumps(ev, ensure_ascii=False))
    print("고른", best["x"], best["win"], best["asset"], best["src"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
