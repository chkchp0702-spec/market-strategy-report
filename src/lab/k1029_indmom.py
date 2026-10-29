"""🌙 10/29 밤 연구 #17 — 🔄 산업 모멘텀: 섹터·테마 ETF 의 과거 수익 상위 N개를 매달 돌려 담기 (ETF 돌파 대신 또는 반반)
  근거: Moskowitz·Grinblatt 1999 「Do Industries Explain Momentum?」 https://doi.org/10.1111/0022-1082.00146
        — 돌파 신호는 드물어 킥 칸이 자주 비고(평균 현금 ~23%), 산업 모멘텀은 늘 꽉 참.
  틀은 10/13~28 그대로: 기본 = C안 뼈대 × 변동성 맞춤(base_vol) · 킥 칸 19% · 「지금 킥」 = ETF 52주 돌파 대용(kick_vw, 빈 자리 BIL)
  새 킥 칸: 섹터·테마 ETF(UNIV, 그날까지 역사 252일 있는 것만) 중 lookback 수익(최근 skip 일 뺌) 상위 N개 같은 비중,
           매달 첫 거래일 종가에 교체 — 판단은 전날(전달 마지막 날) 종가까지 · 절대 필터 켜면 수익 ≤ 0(또는 BIL 이하)인 자리는 BIL
           mode: rep = 돌파 대신 전부 모멘텀 / mix = 킥 칸 반은 돌파·반은 모멘텀(매일 반반 근사)
  격자: lookback(126·189·252일) × skip(0·21일) × N(3·4·5) × 절대 필터(끔·켬) × mode(rep·mix) = 72
  앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1% · 흔들기 = lookback·skip ×0.8/×1.2 · N ±1 · 교체일을 달 중간(10번째 거래일)으로
  한계: 개별 종목이 아닌 ETF · XLC·PAVE·CIBR 등 늦게 생긴 ETF 는 생긴 뒤 1년부터 후보
→ market/lab/k1029_indmom.json
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
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg, UNIV, COST
from k1012_exits import prep
from k1013_trend import base_vol
from k1014_volw import kick_vw

OUT = Path("market/lab/k1029_indmom.json")
SIZE = 0.19
LBS = [126, 189, 252]
SKIPS = [0, 21]
NS = [3, 4, 5]
ABS = [False, True]
MODES = ["rep", "mix"]


def mom_account(C, idx, lb, skip, n, absf, offset=0):
    """산업 모멘텀 계좌 — (일 수익, 일 회전) · 판단 = 교체일 전날 종가, 체결 = 교체일 종가"""
    U = [t for t in UNIV if t in C.columns]
    P = C[U]
    Pv = P.values
    R = P.pct_change().fillna(0.0).values
    bil = C["BIL"].pct_change().fillna(0.0).values
    bilv = C["BIL"].values
    pos_i = {d: i for i, d in enumerate(C.index)}
    # 교체일: 달마다 offset 번째 거래일
    months = pd.Series(C.index, index=C.index).groupby([C.index.year, C.index.month])
    rb_days = set()
    for _, g in months:
        if len(g) > offset:
            rb_days.add(g.iloc[offset])
    w = np.zeros(len(U)); wc = 1.0
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        r = float(np.nansum(w * R[i])) + wc * bil[i]
        w = w * (1 + R[i]); wc = wc * (1 + bil[i])
        tot = w.sum() + wc
        if tot > 0:
            w = w / tot; wc = wc / tot
        tv = 0.0
        if d in rb_days:
            k = i - 1  # 전날 종가까지
            a, b = k - skip, k - lb
            new = np.zeros(len(U)); newc = 0.0
            if b >= 0:
                with np.errstate(invalid="ignore", divide="ignore"):
                    m = Pv[a] / Pv[b] - 1
                    hist_ok = ~np.isnan(Pv[b]) & ~np.isnan(Pv[a]) & ~np.isnan(Pv[k])
                    bm = bilv[a] / bilv[b] - 1
                cand = [(m[j], j) for j in range(len(U)) if hist_ok[j] and not np.isnan(m[j])]
                cand.sort(reverse=True)
                pick = cand[:n]
                for mv, j in pick:
                    if absf and mv <= bm:
                        newc += 1.0 / n
                    else:
                        new[j] = 1.0 / n
                newc += max(0.0, 1.0 - new.sum() - newc)
            else:
                newc = 1.0
            tv = float(np.abs(new - w).sum() + abs(newc - wc)) / 2
            w, wc = new, newc
        c = tv * COST
        r -= c
        rets.append(r); turns.append(tv)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx)


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre = prep(C)
    kk = kick_vw(C, idx, pre, None)
    rkb, tkb = kk[0], kk[1]
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def full(rk, tk):
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    cur = full(rkb, tkb)
    cur["what"] = "지금 킥(ETF 돌파)"
    print("지금", cur["oos"], flush=True)

    cache = {}

    def go(lb, skip, n, absf, mode, offset=0):
        key = (lb, skip, n, absf, offset)
        if key not in cache:
            cache[key] = mom_account(C, idx, lb, skip, n, absf, offset)
        rm, tm = cache[key]
        if mode == "rep":
            rk, tk = rm, tm
        else:
            rk, tk = 0.5 * rkb + 0.5 * rm, 0.5 * tkb + 0.5 * tm
        o = full(rk, tk)
        sleeve = (1 + rm).cumprod()
        o.update({"lb": lb, "skip": skip, "n": n, "abs": absf, "mode": mode, "offset": offset,
                  "sleeve_oos": seg(sleeve, spy, OOS_START, END, tm), "sleeve_is": seg(sleeve, spy, START, IS_END, tm)})
        return o

    grid = []
    for lb in LBS:
        for sk in SKIPS:
            for n in NS:
                for a in ABS:
                    for mo in MODES:
                        r = go(lb, sk, n, a, mo); grid.append(r)
                        print("격자", lb, sk, n, a, mo, r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)
    best = max(grid, key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    ref_sh = cur["oos"]["sharpe"]
    b = best
    shake = []
    for what, kw in [(f"lookback {round(b['lb'] * 0.8)}일", dict(lb=round(b["lb"] * 0.8))),
                     (f"lookback {round(b['lb'] * 1.2)}일", dict(lb=round(b["lb"] * 1.2))),
                     (f"N {max(1, b['n'] - 1)}", dict(n=max(1, b["n"] - 1))),
                     (f"N {b['n'] + 1}", dict(n=b["n"] + 1)),
                     ("교체일 달 중간(10번째 거래일)", dict(offset=9))] + \
                    ([(f"skip {round(b['skip'] * 0.8)}일", dict(skip=round(b["skip"] * 0.8))),
                      (f"skip {round(b['skip'] * 1.2)}일", dict(skip=round(b["skip"] * 1.2)))] if b["skip"] else
                     [("skip 5일", dict(skip=5))]):
        kw2 = dict(lb=b["lb"], skip=b["skip"], n=b["n"], absf=b["abs"], mode=b["mode"], offset=0)
        kw2.update(kw)
        r = go(**kw2); r["what"] = what; shake.append(r)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref_sh)}
    chk = ok(best["oos"])
    shake_ok = all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([r["is"]["sharpe"] for r in grid]).rank().corr(pd.Series([r["oos"]["sharpe"] for r in grid]).rank()))

    def avg(f):
        g = [r for r in grid if f(r)]
        return {"n": len(g), "oos_sh": round(float(np.mean([r["oos"]["sharpe"] for r in g])), 3),
                "oos_cagr": round(float(np.mean([r["oos"]["cagr"] for r in g])), 2),
                "oos_mdd": round(float(np.mean([r["oos"]["mdd"] for r in g])), 2),
                "is_sh": round(float(np.mean([r["is"]["sharpe"] for r in g])), 3)}
    by = {"mode_rep": avg(lambda r: r["mode"] == "rep"), "mode_mix": avg(lambda r: r["mode"] == "mix"),
          "abs_off": avg(lambda r: not r["abs"]), "abs_on": avg(lambda r: r["abs"]),
          **{f"lb{l}": avg(lambda r, l=l: r["lb"] == l) for l in LBS},
          **{f"n{n}": avg(lambda r, n=n: r["n"] == n) for n in NS}}
    slim = lambda r: {k: r[k] for k in ("lb", "skip", "n", "abs", "mode", "offset", "is", "oos", "sleeve_oos", "sleeve_is") if k in r} | ({"what": r["what"]} if "what" in r else {})
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(grid), "spy": spy_row, "current": cur, "best": slim(best), "ref_sharpe": ref_sh,
           "check": chk, "shake_ok": shake_ok, "verdict": verdict, "is_oos_rank_cor": round(rank_cor, 2), "by": by,
           "grid_beat_ref_oos": f"{sum(1 for r in grid if r['oos']['sharpe'] > ref_sh)}/{len(grid)}",
           "grid_beat_spy05_oos": f"{sum(1 for r in grid if r['oos']['ex'] >= 0.5)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for r in grid if all(ok(r['oos']).values()))}/{len(grid)}",
           "shake": [slim(s) for s in shake],
           "grid": [{"lb": r["lb"], "skip": r["skip"], "n": r["n"], "abs": r["abs"], "mode": r["mode"],
                     "is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"], "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"],
                     "oos_mdd": r["oos"]["mdd"], "oos_ex": r["oos"]["ex"], "oos_turn": r["oos"].get("turn"),
                     "sleeve_oos_cagr": r["sleeve_oos"]["cagr"], "sleeve_oos_mdd": r["sleeve_oos"]["mdd"]} for r in grid],
           "note": "기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19% · 지금 킥 = ETF 52주 돌파 대용(빈 자리 BIL) · 새 킥 = 섹터·테마 ETF 산업 모멘텀 상위 N 매달 교체(rep 전부 / mix 돌파와 반반, 매일 반반 근사) · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · ETF 대용 한계 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("고른", best["lb"], best["skip"], best["n"], best["abs"], best["mode"], best["is"]["sharpe"], best["oos"], best["sleeve_oos"])
    print("묶음", by)
    print("순위상관", round(rank_cor, 2), out["grid_beat_ref_oos"], out["grid_beat_spy05_oos"], out["grid_all3_oos"])
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
