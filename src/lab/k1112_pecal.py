"""🌙 11/12 밤 연구 #33 둘째 — 📣 발표 전 자리를 「실제 실적 발표일(야후 달력)」로
  k1112_pebridge 결과: 추정일(작년+364일) ±3일 적중 63% · 같은 사건에서 k2·e0 창 초과수익 추정일 +0.17% vs 실제일 +0.31%
  → 실제 달력이면 비용 0.2·0.3% 를 견디나? (발표일은 보통 몇 주 전 공지 → k일 전에 아는 정보, 미래 자료 아님)
  손잡이는 새로 고르지 않음 — 11/11 에 고른 k2·e0·fill 그대로 + 흔들기 k1·k3·e1, 비용 0.1·0.2·0.3%
  한계: 대형주 102개(생존 편향) · 야후 달력 앞쪽 해는 빠진 종목 있음(해마다 사건 수 같이 적음) · 발표 시각 16시 이후 = 다음 거래일 반응
→ market/lab/k1112_pecal.json
"""
from __future__ import annotations
import datetime as dt, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
import k1011_size, k1013_trend, k1111_preearn
from k1011_size import run_mix, seg, UNIV
from k1012_exits import tstat
from k1019_cupbrk import STK
from k1111_preearn import load_cv, kick_pe, SIZE

OUT = Path("market/lab/k1112_pecal.json")
COSTS = [0.001, 0.002, 0.003]


def set_cost(c):
    for m in (k1011_size, k1013_trend, k1111_preearn):
        m.COST = c


def actual(stks, dates):
    out = {}
    for t in stks:
        try:
            df = yf.Ticker(t).get_earnings_dates(limit=80)
        except Exception:
            df = None
        pos = []
        if df is not None:
            for ts in df.index:
                ts = pd.Timestamp(ts)
                if ts.tzinfo:
                    ts = ts.tz_convert("America/New_York")
                day = pd.Timestamp(ts.date())
                j = int(dates.searchsorted(day))
                if j < len(dates) and ts.hour >= 16 and dates[j] == day:
                    j += 1
                if j < len(dates):
                    pos.append(j)
        out[t] = sorted(set(pos))
    return out


def main():
    C, Vo = load_cv()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    E_U = [t for t in UNIV if t in C.columns]; S_U = [t for t in STK if t in C.columns]
    U = list(dict.fromkeys(E_U + S_U)); col = {t: j for j, t in enumerate(U)}
    P = C[U]; hi = P.shift(1).rolling(252, min_periods=252).max()
    BRK = ((P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))).values
    REL = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    R = P.pct_change().fillna(0.0).values; Pv = P.values
    bil = C["BIL"].pct_change().fillna(0.0).values
    act = actual(S_U, C.index)
    per_year = {}
    for t, al in act.items():
        for a in al:
            y = C.index[a].year
            per_year[y] = per_year.get(y, 0) + 1
    print("해마다 실제 발표 수", dict(sorted(per_year.items())), flush=True)
    brk_ok = [col[t] for t in E_U]

    def sig(k, e):
        d = {}
        for t, al in act.items():
            j = col[t]
            for g in al:
                s = g - k - 1
                if s < 0 or g + e >= len(C.index):
                    continue
                d.setdefault(s, []).append((j, g + e, 0.0))
        return d

    rows = []
    for c in COSTS:
        set_cost(c)
        rb, tb = k1013_trend.base_vol(C, reg, idx)
        res = {}
        for name, pin in (("지금", {}), ("k2·e0 실제 달력", sig(2, 0)), ("k1", sig(1, 0)), ("k3", sig(3, 0)), ("k2·e1", sig(2, 1))):
            rk, tk, tr, ptr = kick_pe(C, idx, U, Pv, R, bil, BRK, REL, brk_ok, pin, None, "fill")
            nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
            res[name] = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                         "pe_is": tstat(ptr, START, IS_END), "pe_oos": tstat(ptr, OOS_START, END)}
            print(f"비용 {c}", name, res[name]["is"]["sharpe"], res[name]["oos"], res[name]["pe_oos"], flush=True)
        ref = res["지금"]["oos"]["sharpe"]

        def ok(o):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}
        chk = {n: ok(r["oos"]) for n, r in res.items() if n != "지금"}
        rows.append({"cost_pct": c * 100, "rows": res, "check": chk, "best_ok": all(chk["k2·e0 실제 달력"].values()),
                     "shake_ok": all(all(chk[n].values()) for n in ("k1", "k3", "k2·e1"))})
    set_cost(0.001)
    verdict = "✅ 통과" if all(r["best_ok"] and r["shake_ok"] for r in rows[:2]) else (
        "➖ 애매" if any(r["best_ok"] for r in rows) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": 5 * len(COSTS), "spy": spy_row, "events_per_year": per_year, "cost": rows, "verdict": verdict,
           "verdict_rule": "비용 0.1%·0.2% 둘 다 세 조건 + 흔들기 유지면 통과",
           "note": "E 무리 = 섹터·테마 ETF 돌파(지금 킥 대용) + 빈 자리에 대형주 102개(생존 편향) 실제 발표일 k일 전 종가 매수 → 반응일+e 종가 매도 · "
                   "야후 get_earnings_dates · 손잡이 새로 안 고름(11/11 고른 값) · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("종합", verdict)


if __name__ == "__main__":
    main()
