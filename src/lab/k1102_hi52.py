"""🌙 11/02 밤 연구 #23 — 📏 52주 고점 근접도: 「돌파한 날」 대신 52주 고점에 가장 가까운 섹터·테마 ETF 상위 N 개를 늘 담기
  근거: George·Hwang 2004 「The 52-Week High and Momentum Investing」 https://doi.org/10.1111/j.1540-6261.2004.00695.x
        — 고점 근접도(지금가 ÷ 52주 최고가)가 과거 수익 모멘텀보다 앞날을 잘 설명 · 10/29 밤: 수익 모멘텀은 칸 낙폭 −33~36% 로 샤프가 깎임
  틀은 10/13~29 그대로: 기본 = C안 뼈대 × 변동성 맞춤(base_vol) · 킥 칸 19% · 「지금 킥」 = ETF 52주 돌파 대용(kick_vw, 빈 자리 BIL)
  새 킥 칸: UNIV 중 그날까지 역사 lb 일 있는 ETF 의 근접도 = 전날 종가 ÷ 전날까지 lb 일 최고 종가 · 근접도 ≥ 1 − thr 인 것만 후보,
           근접도 큰 순(같으면 63일 수익 큰 순) 상위 N 같은 비중 · 후보가 N 보다 적으면 남는 몫 BIL · 교체 = 매달 첫 거래일(M) 또는 5거래일마다(W) 종가
           mode: rep = 돌파 대신 전부 / mix = 반은 돌파·반은 근접도(매일 반반 근사)
  격자: thr(3·5·10%·없음) × N(3·5) × 교체(M·W) × mode(rep·mix) = 32 (lb 252)
  앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1% · 흔들기 = thr ×0.8/×1.2 · N ±1 · lb 202/302 · 교체일 밀기
  한계: 개별 종목이 아닌 ETF · 늦게 생긴 ETF 는 생긴 뒤 lb 일부터 후보 · 매수 추천 아님
→ market/lab/k1102_hi52.json
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

OUT = Path("market/lab/k1102_hi52.json")
SIZE = 0.19
THRS = [0.03, 0.05, 0.10, 1.0]
NS = [3, 5]
FREQS = ["M", "W"]
MODES = ["rep", "mix"]


def hi_account(C, idx, thr, n, freq, lb=252, offset=0):
    U = [t for t in UNIV if t in C.columns]
    P = C[U]
    Pv = P.values
    HI = P.rolling(lb, min_periods=lb).max().values
    R = P.pct_change().fillna(0.0).values
    bil = C["BIL"].pct_change().fillna(0.0).values
    pos_i = {d: i for i, d in enumerate(C.index)}
    if freq == "M":
        months = pd.Series(C.index, index=C.index).groupby([C.index.year, C.index.month])
        rb_days = {g.iloc[offset] for _, g in months if len(g) > offset}
    else:
        rb_days = {d for j, d in enumerate(idx) if j % 5 == offset % 5}
    w = np.zeros(len(U)); wc = 1.0
    rets, turns, nheld = [], [], []
    for d in idx:
        i = pos_i[d]
        r = float(np.nansum(w * R[i])) + wc * bil[i]
        w = w * (1 + R[i]); wc = wc * (1 + bil[i])
        tot = w.sum() + wc
        if tot > 0:
            w = w / tot; wc = wc / tot
        tv = 0.0
        if d in rb_days:
            k = i - 1
            new = np.zeros(len(U))
            if k >= 63:
                with np.errstate(invalid="ignore", divide="ignore"):
                    prox = Pv[k] / HI[k]
                    m63 = Pv[k] / Pv[k - 63] - 1
                cand = [(prox[j], 0.0 if np.isnan(m63[j]) else m63[j], j) for j in range(len(U))
                        if not np.isnan(prox[j]) and prox[j] >= 1 - thr]
                cand.sort(reverse=True)
                for _, _, j in cand[:n]:
                    new[j] = 1.0 / n
            newc = max(0.0, 1.0 - new.sum())
            tv = float(np.abs(new - w).sum() + abs(newc - wc)) / 2
            w, wc = new, newc
        r -= tv * COST
        rets.append(r); turns.append(tv); nheld.append(int((w > 0).sum()))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), float(np.mean(nheld)) / n


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

    cur = full(rkb, tkb); cur["what"] = "지금 킥(ETF 돌파)"
    ksl = (1 + rkb).cumprod()
    cur["sleeve_oos"] = seg(ksl, spy, OOS_START, END, tkb)
    print("지금", cur["oos"], cur["sleeve_oos"], flush=True)
    cache = {}

    def go(thr, n, freq, mode, lb=252, offset=0):
        key = (round(thr, 4), n, freq, lb, offset)
        if key not in cache:
            cache[key] = hi_account(C, idx, thr, n, freq, lb, offset)
        rm, tm, fill = cache[key]
        rk, tk = (rm, tm) if mode == "rep" else (0.5 * rkb + 0.5 * rm, 0.5 * tkb + 0.5 * tm)
        o = full(rk, tk)
        sl = (1 + rm).cumprod()
        o.update({"thr": thr, "n": n, "freq": freq, "mode": mode, "lb": lb, "offset": offset, "fill": round(fill, 3),
                  "sleeve_oos": seg(sl, spy, OOS_START, END, tm), "sleeve_is": seg(sl, spy, START, IS_END, tm)})
        return o

    grid = []
    for th in THRS:
        for n in NS:
            for fq in FREQS:
                for mo in MODES:
                    r = go(th, n, fq, mo); grid.append(r)
                    print("격자", th, n, fq, mo, r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], r["fill"], flush=True)
    best = max(grid, key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    b = best; ref_sh = cur["oos"]["sharpe"]
    base = dict(thr=b["thr"], n=b["n"], freq=b["freq"], mode=b["mode"], lb=252, offset=0)
    sh_list = [(f"lb 202일", dict(lb=202)), (f"lb 302일", dict(lb=302)),
               (f"N {max(1, b['n'] - 1)}", dict(n=max(1, b["n"] - 1))), (f"N {b['n'] + 1}", dict(n=b["n"] + 1)),
               ("교체일 밀기", dict(offset=9 if b["freq"] == "M" else 2))]
    if b["thr"] < 1.0:
        sh_list += [(f"thr {b['thr'] * 0.8:.3f}", dict(thr=b["thr"] * 0.8)), (f"thr {b['thr'] * 1.2:.3f}", dict(thr=b["thr"] * 1.2))]
    shake = []
    for what, kw in sh_list:
        kw2 = dict(base); kw2.update(kw)
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
                "sleeve_mdd": round(float(np.mean([r["sleeve_oos"]["mdd"] for r in g])), 2),
                "fill": round(float(np.mean([r["fill"] for r in g])), 3),
                "is_sh": round(float(np.mean([r["is"]["sharpe"] for r in g])), 3)}
    by = {"rep": avg(lambda r: r["mode"] == "rep"), "mix": avg(lambda r: r["mode"] == "mix"),
          "M": avg(lambda r: r["freq"] == "M"), "W": avg(lambda r: r["freq"] == "W"),
          **{f"thr{t}": avg(lambda r, t=t: r["thr"] == t) for t in THRS},
          **{f"n{n}": avg(lambda r, n=n: r["n"] == n) for n in NS}}
    keys = ("thr", "n", "freq", "mode", "lb", "offset", "fill", "is", "oos", "sleeve_oos", "sleeve_is")
    slim = lambda r: {k: r[k] for k in keys if k in r} | ({"what": r["what"]} if "what" in r else {})
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(grid), "spy": spy_row, "current": cur, "best": slim(best), "ref_sharpe": ref_sh,
           "check": chk, "shake_ok": shake_ok, "verdict": verdict, "is_oos_rank_cor": round(rank_cor, 2), "by": by,
           "grid_beat_ref_oos": f"{sum(1 for r in grid if r['oos']['sharpe'] > ref_sh)}/{len(grid)}",
           "grid_beat_spy05_oos": f"{sum(1 for r in grid if r['oos']['ex'] >= 0.5)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for r in grid if all(ok(r['oos']).values()))}/{len(grid)}",
           "shake": [slim(s) for s in shake],
           "grid": [{"thr": r["thr"], "n": r["n"], "freq": r["freq"], "mode": r["mode"], "fill": r["fill"],
                     "is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"], "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"],
                     "oos_mdd": r["oos"]["mdd"], "oos_ex": r["oos"]["ex"], "oos_turn": r["oos"].get("turn"),
                     "sleeve_oos_cagr": r["sleeve_oos"]["cagr"], "sleeve_oos_mdd": r["sleeve_oos"]["mdd"]} for r in grid],
           "note": "기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19% · 지금 킥 = ETF 52주 돌파 대용(빈 자리 BIL) · 새 킥 = 섹터·테마 ETF 52주 고점 근접도 상위 N(근접 thr 안만, 모자라면 BIL) · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · ETF 대용 한계 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("고른", base, best["is"]["sharpe"], best["oos"], best["sleeve_oos"], best["fill"])
    print("묶음", by)
    print("순위상관", round(rank_cor, 2), out["grid_beat_ref_oos"], out["grid_beat_spy05_oos"], out["grid_all3_oos"])
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
