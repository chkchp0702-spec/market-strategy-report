"""🌙 11/12 밤 연구 #33 — 📣 #29 「실적 발표 직전」 실전 다리
  11/11 #29 통과(ETF 무리) — 그러나 회전 336→721%, 비용은 0.1% 가정, 예정일은 「작년 거래량 최대일 +364일」 추정(±3일 적중 51%).
  ① 비용 0.1·0.2·0.3% 로 다시 — 모든 매매(기본 칸 포함)에 같은 비용, 지금 킥도 같은 비용으로 비교
     고른 것(k2·e0·v0·fill) + 흔들기 k1·k3·e1 을 비용마다 · 판정은 시험 구간(2017~) 숫자
  ② 실제 실적 발표일(야후 get_earnings_dates) — 대형주 102개 최근 분기: 추정 반응일이 실제 반응일과 ±0·1·3 거래일 안에 맞은 비율
     실제 반응일 = 장 마감 뒤 발표면 다음 거래일, 장 전/장중이면 그날
     같은 사건에서 「추정일 창」 vs 「실제일 창」(k2·e0) 의 S&P 대비 초과수익 비교 → 실제 달력을 쓰면 나아지나
  한계: 대형주 102개(생존 편향) · 야후 발표일은 최근 몇 년뿐 · 손절 없음(날짜로만)
→ market/lab/k1112_pebridge.json
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
import k1011_size
import k1013_trend
import k1111_preearn
from k1011_size import run_mix, seg, UNIV
from k1012_exits import tstat
from k1019_cupbrk import STK
from k1111_preearn import load_cv, find_events, est_events, kick_pe, SIZE

OUT = Path("market/lab/k1112_pebridge.json")
COSTS = [0.001, 0.002, 0.003]


def set_cost(c):
    for m in (k1011_size, k1013_trend, k1111_preearn):
        m.COST = c


def actual_dates(stks, C):
    """야후 실적 발표일 → 실제 반응일 위치 목록"""
    dates = C.index
    out, fail = {}, []
    for t in stks:
        try:
            df = yf.Ticker(t).get_earnings_dates(limit=40)
            if df is None or len(df) == 0:
                fail.append(t); continue
            pos = []
            for ts in df.index:
                ts = pd.Timestamp(ts)
                try:
                    ts_et = ts.tz_convert("America/New_York") if ts.tzinfo else ts
                except Exception:
                    ts_et = ts
                day = pd.Timestamp(ts_et.date())
                after = ts_et.hour >= 16 or (ts_et.hour == 0 and ts_et.minute == 0 and False)
                j = int(dates.searchsorted(day))
                if j >= len(dates):
                    continue
                if after and dates[j] == day:
                    j += 1
                if j < len(dates):
                    pos.append(j)
            out[t] = sorted(set(pos))
        except Exception as e:
            fail.append(t)
    return out, fail


def main():
    C, Vo = load_cv()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    E_U = [t for t in UNIV if t in C.columns]
    S_U = [t for t in STK if t in C.columns]
    U = list(dict.fromkeys(E_U + S_U)); col = {t: j for j, t in enumerate(U)}
    P = C[U]; hi = P.shift(1).rolling(252, min_periods=252).max()
    BRK = ((P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))).values
    REL = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    R = P.pct_change().fillna(0.0).values; Pv = P.values
    bil = C["BIL"].pct_change().fillna(0.0).values
    ev = find_events(C, Vo, S_U)
    est, acc, acc_n = est_events(C, ev)
    brk_ok = [col[t] for t in E_U]

    def sig(k, e):
        d = {}
        for t, lst in est.items():
            j = col[t]
            for g, vr in lst:
                s = g - k - 1
                if s < 0 or g + e >= len(C.index):
                    continue
                d.setdefault(s, []).append((j, g + e, vr))
        return d

    # ① 비용
    cost_rows = []
    for c in COSTS:
        set_cost(c)
        rb, tb = k1013_trend.base_vol(C, reg, idx)
        res = {}
        for name, pin in (("지금", {}), ("k2·e0 (고른 것)", sig(2, 0)), ("k1", sig(1, 0)), ("k3", sig(3, 0)), ("k2·e1", sig(2, 1))):
            rk, tk, tr, ptr = kick_pe(C, idx, U, Pv, R, bil, BRK, REL, brk_ok, pin, None, "fill")
            nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
            res[name] = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                         "pe_oos": tstat(ptr, OOS_START, END)}
            print(f"비용 {c}", name, res[name]["is"]["sharpe"], res[name]["oos"], flush=True)
        ref = res["지금"]["oos"]["sharpe"]

        def ok(o):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}
        chk = {n: ok(r["oos"]) for n, r in res.items() if n != "지금"}
        cost_rows.append({"cost_pct": c * 100, "rows": res, "check": chk,
                          "best_ok": all(chk["k2·e0 (고른 것)"].values()),
                          "shake_ok": all(all(chk[n].values()) for n in ("k1", "k3", "k2·e1"))})
    set_cost(0.001)

    # ② 실제 발표일
    act, fail = actual_dates(S_U, C)
    print("야후 발표일 받음", len(act), "실패", len(fail), flush=True)
    spyv = C["SPY"].values
    last = len(C.index) - 1
    hits = {0: 0, 1: 0, 3: 0}; n = 0; offs = []
    pair_est, pair_act = [], []
    act_first = None
    for t, al in act.items():
        al = [a for a in al if a <= last]
        if not al:
            continue
        a0 = min(al)
        act_first = a0 if act_first is None else min(act_first, a0)
        j = col[t]
        for g, vr in est.get(t, []):
            if g < a0 - 10 or g > last:
                continue
            near = [a for a in al if abs(a - g) <= 15]
            if not near:
                continue
            a = min(near, key=lambda x: abs(x - g))
            d = g - a; n += 1; offs.append(d)
            for w in hits:
                if abs(d) <= w:
                    hits[w] += 1

            def win(x):
                s0, s1 = x - 2, x
                if s0 < 1 or s1 > last or np.isnan(Pv[s0, j]) or np.isnan(Pv[s1, j]):
                    return None
                return (Pv[s1, j] / Pv[s0, j] - 1) - (spyv[s1] / spyv[s0] - 1)
            we, wa = win(g), win(a)
            if we is not None and wa is not None:
                pair_est.append(we); pair_act.append(wa)
    # 실제 발표일 전부 (추정과 짝 없어도) k2·e0 창
    all_act = []
    for t, al in act.items():
        j = col[t]
        for a in al:
            if a - 2 < 1 or a > last or np.isnan(Pv[a - 2, j]) or np.isnan(Pv[a, j]):
                continue
            all_act.append((Pv[a, j] / Pv[a - 2, j] - 1) - (spyv[a] / spyv[a - 2] - 1))

    def st(x):
        return {"n": len(x), "ex_avg_pct": round(float(np.mean(x)) * 100, 3) if x else None,
                "hit_pct": round(float(np.mean([v > 0 for v in x])) * 100, 1) if x else None}
    cal = {"tickers_ok": len(act), "tickers_fail": len(fail), "from": str(C.index[act_first].date()) if act_first is not None else None,
           "pairs": n, "hit_pct": {f"±{w}일": round(hits[w] / n * 100, 1) if n else None for w in hits},
           "offset_median": float(np.median(offs)) if offs else None,
           "win_est": st(pair_est), "win_act": st(pair_act), "win_act_all": st(all_act),
           "old_est_accuracy_within3d": acc, "old_est_n": acc_n}
    print("달력", cal, flush=True)
    verdict = "✅ 통과" if all(r["best_ok"] and r["shake_ok"] for r in cost_rows) else (
        "➖ 애매" if any(r["best_ok"] for r in cost_rows) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": 5 * len(COSTS), "spy": spy_row, "cost": cost_rows, "calendar": cal, "verdict": verdict,
           "note": "E 무리 = 섹터·테마 ETF 돌파(지금 킥 대용) + 빈 자리에 대형주 102개(생존 편향) 발표 전 자리 · 비용은 기본 칸 포함 모든 매매 · "
                   "실제 반응일 = 야후 발표 시각 16시 이후면 다음 거래일 · 앞 2008-07~2016 / 뒤 2017~ · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("종합", verdict)


if __name__ == "__main__":
    main()
