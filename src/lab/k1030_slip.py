"""🌙 10/30 밤 연구 #22 — 🩸 손절 미끄러짐: 손절을 「어떻게 체결하나」와 「얼마나 넓게」 바꾸면 결과가 어떻게 되나
  왜: 실제 킥 장부 6건(표본 부족) — 손절 −5% 를 걸었는데 실현 손실 평균 −9.15%(−14.22%·−11.19% 포함).
      실전 kick_sleeve 는 「종가가 −5% 아래면 그 종가에 정리」 → 하루에 크게 빠지면 −5% 를 한참 넘어 팔림.
      지금까지 실험 틀(kick_vw)은 「종가 −5% 아래 → 다음 날 종가」 체결.
  체결 방식 3가지:
    close_next = 종가가 손절선 아래 → 다음 날 종가 (지금 실험 틀)
    close_open = 종가가 손절선 아래 → 다음 날 시가 (조금 빠른 정리)
    intraday   = 손절선에 미리 걸어 둔 주문 — 그날 저가가 손절선 아래면 min(시가, 손절선) 에 체결 (시가가 이미 아래면 시가 = 미끄러짐)
  손절 폭: −4·−5·−6·−7·−8·−10·−12·−15% · 손절 없음 (익절 +15%·15일 정체 정리는 모두 지금 그대로 = 종가 판단 → 다음 날 종가)
  신호 무리 2개: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용, 10/11~ 같은 틀) · S = 미국 대형주 102개 52주 돌파(개별 종목 — 실전 킥에 더 가까움, 하루 낙폭이 큼)
  틀: C안 뼈대 × 변동성 맞춤 + 킥 칸 19%·자리 5 · 판단은 전날까지(손절 주문선은 진입가로 미리 정해짐) · 회전율 × 0.1%
  앞 2008-07~2016 샤프로 무리마다 고르고 2017~ 시험 · 흔들기 = 고른 손절 ×0.8/×1.2 · 익절 ×0.8/×1.2
  한계: 대형주 102개는 지금 살아남은 종목(생존 편향) · 시가·저가도 배당 맞춤 값 · 장중 체결가 = 손절선 그대로(호가 미끄러짐 없음)
→ market/lab/k1030_slip.json
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
from k1011_size import run_mix, seg, UNIV, COST, ALL
from k1012_exits import tstat
from k1013_trend import base_vol
from k1019_cupbrk import STK

OUT = Path("market/lab/k1030_slip.json")
SIZE = 0.19
MODES = ["close_next", "close_open", "intraday"]
STOPS = [-0.04, -0.05, -0.06, -0.07, -0.08, -0.10, -0.12, -0.15, None]


def load_ohlc():
    tk = sorted(set(ALL + STK))
    df = yf.download(tk, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    have = [t for t in tk if t in df.columns.get_level_values(0)]
    Cl = pd.DataFrame({t: df[t]["Close"] for t in have})
    O = pd.DataFrame({t: df[t]["Open"] for t in have})
    L = pd.DataFrame({t: df[t]["Low"] for t in have})
    Cl = Cl.dropna(subset=["SPY", "QQQ", "GLD", "BIL"])
    O, L = O.reindex(Cl.index), L.reindex(Cl.index)
    Cl = Cl.ffill(limit=5)
    return Cl, O, L


def prep_u(Cl, O, L, U):
    U = [t for t in U if t in Cl.columns]
    P = Cl[U]
    hi = P.shift(1).rolling(252, min_periods=252).max()
    brk = (P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))
    rel = (P / P.shift(63)).sub(Cl["SPY"] / Cl["SPY"].shift(63), axis=0)
    R = P.pct_change().fillna(0.0).values
    bil = Cl["BIL"].pct_change().fillna(0.0).values
    return U, P.values, O[U].values, L[U].values, brk.values, rel.values, R, bil


def kick_slip(C, idx, pre, mode="close_next", stop=-0.05, take=0.15, time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    U, Pv, Ov, Lv, BRK, REL, R, bil = pre
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, pend_open, last_exit = [], [], [], {}
    rets, turns, trades, stops = [], [], [], []
    for d in idx:
        i = pos_i[d]
        r = cash * bil[i]
        now_out = []   # 오늘 장중(시가·손절선)에 나간 것: (j, 체결가, 손절?)
        for j, p in pos.items():
            prev = Pv[i - 1, j]
            o, lo = Ov[i, j], Lv[i, j]
            fill = None
            if j in pend_open:
                fill = o if not np.isnan(o) else Pv[i, j]
            elif mode == "intraday" and stop is not None and p["ent_i"] < i and not np.isnan(lo):
                lv = p["entry"] * (1 + stop)
                if lo <= lv:
                    fill = min(o, lv) if not np.isnan(o) else lv
            if fill is not None and not np.isnan(prev) and prev > 0:
                rt = fill / prev - 1
                now_out.append((j, fill, True))
            else:
                rt = R[i, j]
            r += p["w"] * rt
            p["w"] *= 1 + rt
        cash *= 1 + bil[i]
        tot = cash + sum(p["w"] for p in pos.values())
        cash /= tot
        for p in pos.values():
            p["w"] /= tot
        tv = 0.0
        for j, fill, isstop in now_out:
            p = pos.pop(j)
            g = fill / p["entry"] - 1
            trades.append((str(C.index[p["ent_i"]].date()), g)); stops.append((str(d.date()), g))
            cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j, why in pend_out:
            if j in pos:
                p = pos.pop(j)
                g = Pv[i, j] / p["entry"] - 1
                trades.append((str(C.index[p["ent_i"]].date()), g))
                if why == "stop":
                    stops.append((str(d.date()), g))
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(1.0 / slots, cash)
            if w <= 0 or np.isnan(Pv[i, j]):
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i}
            cash -= w; tv += w
        pend_in, pend_out, pend_open = [], [], []
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
            if stop is not None and mode != "intraday" and g <= stop:
                if mode == "close_open":
                    pend_open.append(j)
                else:
                    pend_out.append((j, "stop"))
            elif g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min):
                pend_out.append((j, "other"))
        free = slots - len(pos) + len(pend_out) + len(pend_open)
        if free > 0:
            cand = [(REL[i, j], j) for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            for _, j in cand[:min(free, max_new)]:
                pend_in.append(j)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, stops


def sstat(st, a, b):
    x = [g for d, g in st if a <= d <= b]
    if not x:
        return {"n": 0}
    return {"n": len(x), "avg": round(float(np.mean(x)) * 100, 2), "worst": round(float(min(x)) * 100, 2),
            "p10": round(float(np.percentile(x, 10)) * 100, 2)}


def main():
    C, O, L = load_ohlc()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    PRE = {"E": prep_u(C, O, L, UNIV), "S": prep_u(C, O, L, STK)}
    print("무리 크기", {k: len(v[0]) for k, v in PRE.items()}, flush=True)

    def run(fam, mode, stop, take=0.15):
        rk, tk, tr, st = kick_slip(C, idx, PRE[fam], mode=mode, stop=stop, take=take)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "mode": mode, "stop": stop, "take": take,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
                "stop_is": sstat(st, START, IS_END), "stop_oos": sstat(st, OOS_START, END)}

    out_f = {}
    trials = 0
    for fam in ("E", "S"):
        cur = run(fam, "close_next", -0.05)
        grid = []
        for m in MODES:
            for s in STOPS:
                if s is None and m != "close_next":
                    continue
                g = cur if (m == "close_next" and s == -0.05) else run(fam, m, s)
                grid.append(g)
                print(fam, m, s, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["stop_oos"], flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        bs = best["stop"]
        if bs is not None:
            for k in (0.8, 1.2):
                g = run(fam, best["mode"], round(bs * k, 3)); g["what"] = f"손절 {round(bs * k * 100, 1)}%"; shake.append(g)
        for k in (0.8, 1.2):
            g = run(fam, best["mode"], bs, take=round(0.15 * k, 3)); g["what"] = f"익절 +{round(15 * k)}%"; shake.append(g)

        def ok(o):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}
        chk = ok(best["oos"])
        shake_ok = all(all(ok(s["oos"]).values()) for s in shake)
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
        by_mode = {m: {"oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in grid if g["mode"] == m and g["stop"] is not None])), 3),
                       "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in grid if g["mode"] == m and g["stop"] is not None])), 2),
                       "oos_mdd": round(float(np.mean([g["oos"]["mdd"] for g in grid if g["mode"] == m and g["stop"] is not None])), 2)} for m in MODES}
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by_mode": by_mode, "shake": shake,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"mode": g["mode"], "stop": g["stop"], "is_sh": g["is"]["sharpe"], "oos_sh": g["oos"]["sharpe"],
                                "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"),
                                "tr_oos": g["tr_oos"], "stop_oos": g["stop_oos"], "stop_is": g["stop_is"]} for g in grid]}
        print(fam, "고른", best["mode"], best["stop"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개 52주 돌파(생존 편향) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · "
                   "체결: close_next 종가→다음 날 종가 / close_open 종가→다음 날 시가 / intraday 손절선 주문 min(시가, 손절선) · 익절·정체는 모두 종가→다음 종가 · "
                   "stop_oos = 시험 구간 손절로 나간 거래의 실현 손익 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
