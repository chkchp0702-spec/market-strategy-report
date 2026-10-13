"""🌙 10/13 밤 연구 #3 — 추세 필터: S&P 가 N일선 아래면 킥 신규 진입 멈춤 (또는 갖고 있던 것도 정리)
  틀은 10/11·10/12 그대로: 기본 = C안 뼈대 · 킥 칸 19%(🟢·🔴 같게) · 출구 −5%·+15%·15일
  킥 칸 대용 = 섹터·테마 ETF 52주 신고가 돌파 (개별 종목 신호는 긴 역사가 없음 → 한계)
  10/13부터 켜진 변동성 맞춤(기본 칸 주식 × min(1, 18% ÷ 20일 변동성), 아래 한도 50%, 5%p 넘게 바뀔 때만)도 넣은 판을 주 판으로
  손잡이: 이동평균 길이 N(50·100·150·200·250) × 확인 일수 k(1·3·5) × 방식(진입만 멈춤 / 진입 멈춤 + 보유도 정리)
  판단은 그날 종가까지 → 다음 날 종가 체결 · 회전율 × 0.1% 비용 · 2008-07~2016 샤프로 고르고 2017~ 에서 시험
→ market/lab/k1013_trend.json
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
from k1011_size import load, base_account, run_mix, seg, COST
from k1012_exits import prep, tstat

OUT = Path("market/lab/k1013_trend.json")
SIZE = 0.19
LENS = [50, 100, 150, 200, 250]
KS = [1, 3, 5]
MODES = ["entry", "exit"]


def sticky(s, k):
    s = s.fillna(False).astype(bool)
    if k <= 1:
        return s
    out, cur, run = [], bool(s.iloc[0]), 0
    for v in s.values:
        if v != cur:
            run += 1
            if run >= k:
                cur, run = v, 0
        else:
            run = 0
        out.append(cur)
    return pd.Series(out, index=s.index)


def gate_of(C, n, k):
    spy = C["SPY"]
    return sticky(spy > spy.rolling(n, min_periods=n).mean(), k).values


def base_vol(C, reg, idx, lb=20, tgt=18.0, floor=0.5, band=0.05):
    """C안 뼈대 + 변동성 맞춤 (주식 칸 × min(1, 목표/실현), 아래 한도) — 덜어낸 만큼 BIL"""
    G = {"SPY": .475, "QQQ": .475, "GLD": .05, "BIL": 0.0}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11, "BIL": .26}
    R = C[list(G)].pct_change().fillna(0.0)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(lb).std() * math.sqrt(252) * 100
    sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i):
        b = G if regv.iloc[i] else Rd
        s = float(sc.iloc[i])
        e = (b["SPY"] + b["QQQ"]) * s
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": b["GLD"], "BIL": 1 - e - b["GLD"]}
    w, last_eq = None, None
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1); last_eq = w["SPY"] + w["QQQ"]
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        t = tg(i - 1)
        newm = C.index[i - 1].month != d.month
        tv = 0.0
        if newm or regv.iloc[i - 1] != regv.iloc[i - 2] or abs(t["SPY"] + t["QQQ"] - last_eq) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last_eq = t["SPY"] + t["QQQ"]
            r -= tv * COST
        rets.append(r); turns.append(tv)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx)


def kick_gate(C, idx, pre, gate=None, mode="entry", stop=-0.05, take=0.15, time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    """k1012 kick_fast + 추세 문(gate[i]=False 면 새 진입 없음, mode=exit 이면 갖고 있던 것도 다음 날 정리)"""
    U, Pv, BRK, REL, R, bil = pre
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades = [], [], []
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
                trades.append((str(C.index[p["ent_i"]].date()), Pv[i, j] / p["entry"] - 1, p["up"]))
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(1.0 / slots, cash)
            if w <= 0:
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i, "up": UP200[i - 1]}
            cash -= w; tv += w
        pend_in, pend_out = [], []
        c = tv * COST
        r -= c; cash -= c
        rets.append(r); turns.append(tv)
        open_ = True if gate is None else bool(gate[i])
        for j, p in pos.items():
            if p["ent_i"] == i:
                continue
            px = Pv[i, j]
            if np.isnan(px):
                continue
            p["held"] += 1
            p["max"] = max(p["max"], px)
            g = px / p["entry"] - 1
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min) or (mode == "exit" and not open_):
                pend_out.append(j)
        if not open_:
            continue
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [(REL[i, j], j) for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            pend_in = [j for _, j in cand[:min(free, max_new)]]
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades


UP200 = None


def main():
    global UP200
    C = load()
    UP200 = gate_of(C, 200, 3)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    bases = {"vol": base_vol(C, reg, idx), "plain": base_account(C, reg, idx)}
    pre = prep(C)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def run(n=None, k=None, mode=None, base="vol"):
        gate = None if n is None else gate_of(C, n, k)
        kk = kick_gate(C, idx, pre, gate=gate, mode=mode or "entry")
        rb, tb = bases[base]
        nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
        knav = (1 + kk[0]).cumprod()
        tr2 = [(a, b) for a, b, _ in kk[2]]
        return {"n": n, "k": k, "mode": mode, "base": base,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, kk[1]), "kick_oos": seg(knav, spy, OOS_START, END, kk[1]),
                "tr_is": tstat(tr2, START, IS_END), "tr_oos": tstat(tr2, OOS_START, END), "_tr": kk[2]}

    cur = run()
    cur_plain = run(base="plain")
    # 하락장 신호 성적 — 지금 규칙 거래를 진입 전날 S&P 200일선 위/아래로 나눠
    split = {}
    for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
        for up in (True, False):
            split[f"{nm}_{'up' if up else 'down'}"] = tstat([(x, r) for x, r, u in cur["_tr"] if u == up], a, b)
    grid = [run(n, k, m) for n in LENS for k in KS for m in MODES]
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    shake = []
    for key, vals in (("n", [int(round(best["n"] * 0.8)), int(round(best["n"] * 1.2))]),
                      ("k", sorted({max(1, int(round(best["k"] * 0.8))), int(round(best["k"] * 1.2)) + (1 if best["k"] == 1 else 0)}))):
        for v in [v for v in vals if v != best[key]]:
            kw = {"n": best["n"], "k": best["k"], "mode": best["mode"], key: v}
            g = run(**kw); g["what"] = f"{key}={v}"
            shake.append(g)
    g = run(best["n"], best["k"], "exit" if best["mode"] == "entry" else "entry"); g["what"] = "방식 반대"
    shake.append(g)
    best_plain = run(best["n"], best["k"], best["mode"], base="plain")

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > cur["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(all(all(ok(s["oos"]).values()) for s in shake if s["what"] != "방식 반대"))
    if all(chk.values()) and shake_ok:
        verdict = "✅ 통과"
    elif any(chk.values()):
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    rank_cor = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
    beat_cur = sum(1 for g in grid if g["oos"]["sharpe"] > cur["oos"]["sharpe"])
    strip = lambda g: {k: v for k, v in g.items() if k != "_tr"}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "size": SIZE, "spy": spy_row, "current": strip(cur), "current_plain": strip(cur_plain), "best": strip(best),
           "best_plain": strip(best_plain), "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "regime_split": split, "is_oos_rank_cor": round(rank_cor, 2), "grid_beat_current_oos": f"{beat_cur}/{len(grid)}",
           "shake": [strip(s) for s in shake],
           "grid": [{k: g[k] for k in ("n", "k", "mode")} | {"is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"], "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_turn": g["oos"].get("turn")} for g in grid],
           "note": "킥 신호 대신 섹터·테마 ETF 52주 신고가 돌파 · 기본 = C안 뼈대 + 변동성 맞춤(10/13~) · 킥 칸 19% · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("현재(vol)", cur["oos"], cur["tr_oos"])
    print("현재(plain)", cur_plain["oos"])
    print("국면별 거래", split)
    print("고른", best["n"], best["k"], best["mode"], best["is"]["sharpe"], best["oos"], best["tr_oos"])
    print("고른(plain)", best_plain["oos"])
    print("순위상관", round(rank_cor, 2), "현재보다 나은 조합", beat_cur, "/", len(grid))
    for g in grid:
        print(g["n"], g["k"], g["mode"], "IS", g["is"]["sharpe"], g["is"]["cagr"], "| OOS", g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"].get("turn"))
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
