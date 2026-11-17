"""🌙 11/17 밤 연구 #36 — 📆 큰 경제 발표 날 프리미엄 (물가 CPI·고용 발표 날 현금 → S&P/나스닥)
  왜: Savor·Wilson 2013 「How Much Do Investors Care About Macroeconomic Risk? Evidence from Scheduled Economic Announcements」
      (JFQA 48(2)) https://doi.org/10.1017/S0022109013000227 — 물가·고용·FOMC 같은 정해진 발표 날 주식 초과수익이 평소보다 큼.
      11/14 밤: FOMC 하루만은 1년 8번이라 드묾·2017~ S&P 에선 사라짐 → 1년 ~24번으로 날짜 늘리기.
  날짜: src/lab/k1117_dates.txt = BLS 공식 보관 목록의 실제 발표일 — 발표 일정은 미리 공지(미래 자료 아님).
        시장 쉬는 날(성금요일 등) 발표는 다음 거래일로. 겹치는 날은 한 번만(날 표시 방식).
  바꾸는 것(지금 킥 틀 위 덧씌우기 — 기본 칸·킥 칸 그대로):
    set    cpi / nfp(고용) / macro(둘 다) / all(둘 다 + FOMC)
    x      옮길 크기 10·20·30%·있는 현금 전부(1.0)
    win    t = 전날 종가→발표일 종가 / pre2 = 이틀 전 종가→발표일 종가 / post = 전날 종가→다음 날 종가
    asset  SPY / QQQ  ·  src cash / cashgld   = 4 × 4 × 3 × 2 × 2 = 192조합
  회전율 × 0.1% · 앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 흔들기 크기 ×0.8/×1.2·자산 반대·창 바꾸기(참고)·비용 0.2% · 가짜 날짜 ±5·±10거래일
→ market/lab/k1117_macro.json
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
import k1114_fomc
from k1114_fomc import FOMC

OUT = Path("market/lab/k1117_macro.json")
SIZE = 0.19
_D = {}
for line in (Path(__file__).resolve().parent / "k1117_dates.txt").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#"):
        p = line.split()
        _D[p[0]] = p[1:]
CPI, NFP = _D["CPI"], _D["NFP"]
SETS = {"cpi": CPI, "nfp": NFP, "macro": CPI + NFP, "all": CPI + NFP + FOMC}
XS = [0.10, 0.20, 0.30, 1.0]
WINS = {"t": (0, 0), "pre2": (-1, 0), "post": (0, 1)}
ASSETS = ["SPY", "QQQ"]
SRCS = ["cash", "cashgld"]
REG = None


def to_trade(idx, strs):
    """발표일 → 그날 또는 다음 거래일 위치(겹치면 한 번)"""
    out = set()
    for s in strs:
        ts = pd.Timestamp(s)
        k = int(idx.searchsorted(ts))
        if 0 <= k < len(idx) and (idx[k] - ts).days <= 4:
            out.add(k)
    return sorted(out)


def overlay(C, idx, base_r, base_t, ks, x, win, asset, src, cw, gw, cost=COST):
    R = C[[asset, "BIL", "GLD"]].pct_change().reindex(idx).fillna(0.0)
    a, b = WINS[win]
    held = np.zeros(len(idx), bool)
    n = 0
    for k in ks:
        lo, hi = k + a, k + b
        if lo < 2 or hi >= len(idx):
            continue
        held[lo:hi + 1] = True
        n += 1
    xc = np.where(held, np.minimum(x, cw), 0.0)
    xg = np.where(held, np.minimum(np.maximum(x - xc, 0.0), gw), 0.0) if src == "cashgld" else np.zeros(len(idx))
    ra, rbil, rg = R[asset].values, R["BIL"].values, R["GLD"].values
    add = xc * (ra - rbil) + xg * (ra - rg)
    tot = xc + xg
    nxt = np.concatenate([held[1:], [False]])
    prv = np.concatenate([[False], held[:-1]])
    tvv = np.where(held & ~prv, tot, 0.0) + np.where(held & ~nxt, tot, 0.0)   # 들어갈 때(전날 종가 체결, 보수적으로 첫날 비용) + 나올 때
    r = base_r + pd.Series(add - tvv * cost, index=idx)
    t = base_t + pd.Series(tvv, index=idx)
    mv = tot[held]
    return r, t, {"n": n, "days": int(held.sum()), "avg_moved": round(float(mv.mean()) * 100, 1) if len(mv) else 0.0}


def ev_stats(C, idx, ks):
    R = C[["SPY", "QQQ", "BIL"]].pct_change().reindex(idx).fillna(0.0)
    out = {}
    for nm, lo_, hi_ in (("is", START, IS_END), ("oos", OOS_START, str(idx[-1].date()))):
        m = np.asarray((idx >= pd.Timestamp(lo_)) & (idx <= pd.Timestamp(hi_)))
        for asset in ("SPY", "QQQ"):
            ex = (R[asset] - R["BIL"]).values
            v = np.array([ex[k] for k in ks if m[k]])
            allm = ex[m]
            out[f"{nm}_{asset}"] = {"n": int(len(v)), "avg_bp": round(float(v.mean()) * 1e4, 1),
                                    "allday_bp": round(float(allm.mean()) * 1e4, 1),
                                    "win": round(float((v > 0).mean()) * 100, 1),
                                    "t_vs_allday": round(float((v.mean() - allm.mean()) / (v.std(ddof=1) / math.sqrt(len(v)))), 2)}
    return out


def main():
    global REG
    C, _, _ = load_ohlc()
    REG = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    k1114_fomc.REG = REG
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    K = {s: to_trade(idx, v) for s, v in SETS.items()}
    print("날 수", {s: len(v) for s, v in K.items()}, flush=True)
    cw, gw = k1114_fomc.base_weights(C, REG)
    cw = (cw.reindex(idx).fillna(0.0) * (1 - SIZE)).values
    gw = (gw.reindex(idx).fillna(0.0) * (1 - SIZE)).values
    rb, tb = base_vol(C, REG, idx)
    pre = prep(C, UNIV)
    rk, tk, _ = kick_trail(C, idx, pre, trail=None)
    nav0, td0 = run_mix(rb, tb, (rk, tk, None), REG, SIZE, SIZE)
    base_r = nav0.pct_change().fillna(0.0)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    cur = {"is": seg(nav0, spy, START, IS_END, td0), "oos": seg(nav0, spy, OOS_START, END, td0)}
    print("지금", cur["is"]["sharpe"], cur["oos"], flush=True)

    def run(st, x, win, asset, src, ks=None, cost=COST):
        r, t, info = overlay(C, idx, base_r, td0, K[st] if ks is None else ks, x, win, asset, src, cw, gw, cost)
        nav = (1 + r).cumprod()
        return {"set": st, "x": x, "win": win, "asset": asset, "src": src, "ev": info,
                "is": seg(nav, spy, START, IS_END, t), "oos": seg(nav, spy, OOS_START, END, t)}

    grid = []
    for st in SETS:
        for x in XS:
            for w in WINS:
                for a in ASSETS:
                    for s in SRCS:
                        g = run(st, x, w, a, s)
                        grid.append(g)
                        print(st, x, w, a, s, g["ev"], g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"]["ex"], flush=True)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    ref = cur["oos"]["sharpe"]
    B = (best["set"], best["x"], best["win"], best["asset"], best["src"])
    shake = []
    for k in (0.8, 1.2):
        x2 = round(best["x"] * k, 3)
        g = run(B[0], x2, B[2], B[3], B[4]); g["what"] = f"크기 {x2 * 100:.0f}%"; shake.append(g)
    g = run(B[0], B[1], B[2], "QQQ" if B[3] == "SPY" else "SPY", B[4]); g["what"] = "자산 " + g["asset"]; shake.append(g)
    g = run(B[0], B[1], B[2], B[3], B[4], cost=0.002); g["what"] = "비용 0.2%"; shake.append(g)
    ref_shake = []
    for w in WINS:
        if w != B[2]:
            g = run(B[0], B[1], w, B[3], B[4]); g["what"] = "창 " + w; ref_shake.append(g)
    for st in SETS:
        if st != B[0]:
            g = run(st, B[1], B[2], B[3], B[4]); g["what"] = "날짜 묶음 " + st; ref_shake.append(g)
    plac = []
    for sh in (-10, -5, 5, 10):
        ks = [k + sh for k in K[B[0]] if 2 <= k + sh < len(idx)]
        g = run(B[0], B[1], B[2], B[3], B[4], ks=ks); g["what"] = f"가짜 날짜 {sh:+d}거래일"; plac.append(g)

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
    by = {f"set_{s}": avg("set", s) for s in SETS}
    by.update({f"x_{x}": avg("x", x) for x in XS})
    by.update({f"win_{w}": avg("win", w) for w in WINS})
    by.update({f"asset_{a}": avg("asset", a) for a in ASSETS})
    ev = {s: ev_stats(C, idx, K[s]) for s in SETS}
    best_oos = max(grid, key=lambda g: g["oos"]["sharpe"])
    peek = {k: best_oos[k] for k in ("set", "x", "win", "asset", "src")}
    peek["oos"] = best_oos["oos"]
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(grid), "n_days": {s: len(v) for s, v in K.items()}, "spy": spy_row, "current": cur,
           "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict, "shake": shake,
           "shake_ref_only": ref_shake, "placebo": plac, "best_if_oos_peek": peek,
           "is_oos_rank_cor": round(rc, 2), "by": by, "event_day": ev,
           "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
           "grid": [{"set": g["set"], "x": g["x"], "win": g["win"], "asset": g["asset"], "src": g["src"], "days": g["ev"]["days"],
                     "moved": g["ev"]["avg_moved"], "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"], "oos_sh": g["oos"]["sharpe"],
                     "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn")} for g in grid],
           "note": "지금 킥 = C안 뼈대 × 변동성 맞춤 + 킥 칸 19%(섹터·테마 ETF 52주 돌파 대용, 빈 자리 BIL — 실전 🅿️ park 빼고) · "
                   "덧씌우기 = BLS 실제 CPI·고용 발표일(·FOMC) 무렵 x 만큼 현금(·금)을 SPY/QQQ 로, 한도는 이틀 전 목표의 현금(·금) · "
                   "회전율×0.1% · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 매수 추천 아님"}
    for s in shake + ref_shake + plac:
        print("  ", s["what"], s["ev"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    print("이벤트", json.dumps(ev, ensure_ascii=False))
    print("고른", B, best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
