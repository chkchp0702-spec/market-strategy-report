"""🌙 10/14 밤 연구 #4 — 변동성 맞춤 비중: 킥 종목별 20일 변동성에 반비례해서 담기
  틀은 10/13 그대로: 기본 = C안 뼈대 + 변동성 맞춤(10/13~) · 킥 칸 19% · 출구 −5%·+15%·15일
  킥 칸 대용 = 섹터·테마 ETF 52주 신고가 돌파 (개별 종목 신호는 긴 역사가 없음 → 한계: ETF 는 변동성 차이가 개별 종목보다 작음)
  지금: 새 자리 하나 = 킥 칸의 1/5(20%) 같은 크기
  새 규칙: 자리 크기 = 1/5 × min(상한배, 목표변동성 ÷ 그 종목 20일 변동성) — 남는 돈은 현금(BIL)
  손잡이: 목표변동성 T(10·15·20·25·30·40%) × 상한배 cap(1.0·1.5·2.0) = 18조합
  판단은 그날 종가까지 → 다음 날 종가 체결 · 회전율 × 0.1% 비용 · 2008-07~2016 샤프로 고르고 2017~ 에서 시험
→ market/lab/k1014_volw.json
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
from k1011_size import load, run_mix, seg, COST
from k1012_exits import prep, tstat
from k1013_trend import base_vol

OUT = Path("market/lab/k1014_volw.json")
SIZE = 0.19
TS = [10, 15, 20, 25, 30, 40]
CAPS = [1.0, 1.5, 2.0]


def kick_vw(C, idx, pre, VOL, T=None, cap=1.0, stop=-0.05, take=0.15, time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    """k1013 kick_gate(문 없음) + 진입 크기 = 1/slots × min(cap, T/20일변동성) (T=None 이면 지금 규칙 = 같은 크기)"""
    U, Pv, BRK, REL, R, bil = pre
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades, sizes = [], [], [], []
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
        for j, want in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(want, cash)
            if w <= 0:
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i}
            sizes.append(w)
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
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min):
                pend_out.append(j)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [(REL[i, j], j) for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            for _, j in cand[:min(free, max_new)]:
                if T is None:
                    want = 1.0 / slots
                else:
                    v = VOL[i, j]
                    k = cap if (np.isnan(v) or v <= 0) else min(cap, T / v)
                    want = k / slots
                pend_in.append((j, want))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, sizes


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre = prep(C)
    U = pre[0]
    VOL = (C[U].pct_change().rolling(20, min_periods=20).std() * math.sqrt(252) * 100).values
    vol_med = float(np.nanmedian(VOL[np.searchsorted(C.index.values, np.datetime64(pd.Timestamp(START))):]))
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def run(T=None, cap=1.0):
        kk = kick_vw(C, idx, pre, VOL, T=T, cap=cap)
        nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
        knav = (1 + kk[0]).cumprod()
        sz = kk[3]
        return {"T": T, "cap": cap,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, kk[1]), "kick_oos": seg(knav, spy, OOS_START, END, kk[1]),
                "tr_is": tstat(kk[2], START, IS_END), "tr_oos": tstat(kk[2], OOS_START, END),
                "avg_size": round(float(np.mean(sz)) * 100, 1) if sz else None}

    cur = run()
    grid = [run(T, c) for T in TS for c in CAPS]
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    shake = []
    for key, vals in (("T", [best["T"] * 0.8, best["T"] * 1.2]), ("cap", [best["cap"] * 0.8, best["cap"] * 1.2])):
        for v in vals:
            if key == "cap" and v < 1.0 and best["cap"] == 1.0:
                v = 0.8
            kw = {"T": best["T"], "cap": best["cap"], key: round(v, 2)}
            g = run(**kw); g["what"] = f"{key}={round(v, 2)}"
            shake.append(g)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > cur["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(all(all(ok(s["oos"]).values()) for s in shake))
    if all(chk.values()) and shake_ok:
        verdict = "✅ 통과"
    elif any(chk.values()):
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    rank_cor = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
    beat_cur = sum(1 for g in grid if g["oos"]["sharpe"] > cur["oos"]["sharpe"])
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "size": SIZE, "etf_vol_median": round(vol_med, 1), "spy": spy_row, "current": cur, "best": best,
           "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "grid_beat_current_oos": f"{beat_cur}/{len(grid)}",
           "shake": shake,
           "grid": [{"T": g["T"], "cap": g["cap"], "avg_size": g["avg_size"], "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"], "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_turn": g["oos"].get("turn")} for g in grid],
           "note": "킥 신호 대신 섹터·테마 ETF 52주 신고가 돌파 · 기본 = C안 뼈대 + 변동성 맞춤(10/13~) · 킥 칸 19% · 자리 크기 = 1/5 × min(상한, 목표÷20일 변동성) · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("현재", cur["oos"], cur["tr_oos"], cur["avg_size"])
    print("ETF 20일 변동성 가운데", vol_med)
    print("고른", best["T"], best["cap"], best["is"]["sharpe"], best["oos"], best["tr_oos"], best["avg_size"])
    print("순위상관", round(rank_cor, 2), "현재보다 나은 조합", beat_cur, "/", len(grid))
    for g in grid:
        print(g["T"], g["cap"], g["avg_size"], "IS", g["is"]["sharpe"], g["is"]["cagr"], "| OOS", g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"].get("turn"))
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
