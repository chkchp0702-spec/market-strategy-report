"""🌙 11/11 밤 연구 #29 확인 — 📣 발표 전 자리가 「실적 때문」인지 「빈 자리를 대형주로 채워서」인지 가르기
  k1111_preearn E 고른 것(k2·e0·v0·fill) 을 기준으로:
    가짜 날짜(placebo) = 추정 반응일을 ±30거래일 옮긴(발표 없는 한가운데) 같은 길이 자리
    park = 발표 전 자리 없이 빈 자리 현금을 S&P(SPY) 로 (10/19 적용된 park 대용)
    park + 발표 전 = 둘 다 · 흔들기 k 1·3일
→ market/lab/k1111_preearn2.json
"""
from __future__ import annotations
import datetime as dt, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import run_mix, seg, UNIV
from k1012_exits import tstat
from k1013_trend import base_vol
from k1019_cupbrk import STK
from k1111_preearn import load_cv, find_events, est_events, kick_pe, SIZE

OUT = Path("market/lab/k1111_preearn2.json")


def main():
    C, Vo = load_cv()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    E_U = [t for t in UNIV if t in C.columns]; S_U = [t for t in STK if t in C.columns]
    U = list(dict.fromkeys(E_U + S_U)); col = {t: j for j, t in enumerate(U)}
    P = C[U]; hi = P.shift(1).rolling(252, min_periods=252).max()
    BRK = ((P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))).values
    REL = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    R = P.pct_change().fillna(0.0).values; Pv = P.values
    bil = C["BIL"].pct_change().fillna(0.0).values
    spyr = C["SPY"].pct_change().fillna(0.0).values
    est, acc, _ = est_events(C, find_events(C, Vo, S_U))
    brk_ok = [col[t] for t in E_U]

    def sig(k, e, off=0):
        d = {}
        for t, lst in est.items():
            j = col[t]
            for g, vr in lst:
                g2 = g + off
                s = g2 - k - 1
                if s < 0 or g2 + e >= len(C.index):
                    continue
                d.setdefault(s, []).append((j, g2 + e, vr))
        return d

    def run(name, pin, park=False):
        rk, tk, tr, ptr = kick_pe(C, idx, U, Pv, R, spyr if park else bil, BRK, REL, brk_ok, pin, None, "fill")
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        o = {"name": name, "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
             "pe_is": tstat(ptr, START, IS_END), "pe_oos": tstat(ptr, OOS_START, END)}
        print(name, o["is"]["sharpe"], o["oos"], o["pe_oos"], flush=True)
        return o

    rows = [run("지금(빈 자리 현금)", {}), run("발표 전 k2·e0 (고른 것)", sig(2, 0)),
            run("흔들기 k1", sig(1, 0)), run("흔들기 k3", sig(3, 0)),
            run("가짜 날짜 −30거래일", sig(2, 0, -30)), run("가짜 날짜 +30거래일", sig(2, 0, 30)),
            run("park(빈 자리 S&P)", {}, park=True), run("park + 발표 전 k2·e0", sig(2, 0), park=True),
            run("park + 가짜 −30", sig(2, 0, -30), park=True)]
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(rows), "spy": spy_row, "rows": rows,
           "note": "E = 섹터·테마 ETF 돌파 + 빈 자리에 대형주 102개(생존 편향) 발표 전 자리 · 가짜 날짜 = 추정 반응일 ±30거래일 · park = 빈 자리 수익을 SPY 로 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
