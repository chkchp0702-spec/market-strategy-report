"""🌙 10/11 밤 연구 #1 — 킥 칸 크기: 기본 포트에서 킥 신호에 떼는 비율(0~30%)과 국면(🟢/🔴)에 따라 바꾸기
  기본 = C안 뼈대 (🟢 SPY 47.5·QQQ 47.5·금 5 / 🔴 31.5·31.5·금 11·현금 26, 판정 = S&P 200일선, 3일 이어져야 인정)
  킥 칸 대용 = 섹터·테마 ETF 26개의 52주 신고가 돌파 (개별 종목 신호는 긴 역사가 없음 → ETF 로 대신 — 한계)
     슬롯 5 · 하루 새 진입 최대 2 · 손절 −5% · 익절 +15% · 15일 지나도 최고 +3% 못 넘으면 정리 · 판 뒤 10일 재진입 금지
     돌파일 종가가 직전 고점 +12% 넘게 뻗었으면 제외 · 후보 많으면 S&P 대비 3개월 강한 순
  판단은 그날 종가까지 → 다음 날 종가에 체결 · 회전율 × 0.1% 비용 · 매월 첫날·국면 바뀐 날 기본/킥 비율 다시 맞춤
  2008-07~2016 에서 (🟢 크기, 🔴 크기 비율) 고르고 2017~ 에서 시험. 「지금 킥」 = 늘 19% (돌파 9% + 고래 10% — 고래 바스켓은 역사가 없어 돌파로 대신)
→ market/lab/k1011_size.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
import yfinance as yf
from src.conc_bt import SECT, THEME, START, IS_END, OOS_START, stats, regimes

OUT = Path("market/lab/k1011_size.json")
COST = 0.001
UNIV = SECT + [t for t in THEME if t not in ("QQQ", "GLD")]
ALL = sorted(set(UNIV + ["SPY", "QQQ", "GLD", "BIL"]))


def load():
    df = yf.download(ALL, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in ALL if t in df.columns.get_level_values(0)})
    C = C.dropna(subset=["SPY", "QQQ", "GLD", "BIL"]).ffill(limit=5)
    return C


def kick_account(C, idx, stop=-0.05, take=0.15, time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10, ext=0.12):
    """킥 칸만 따로 굴린 계좌 — 일별 수익률·회전(일별)·거래 목록"""
    U = [t for t in UNIV if t in C.columns]
    P = C[U]
    hi = P.shift(1).rolling(252, min_periods=252).max()
    brk = (P > hi) & (P <= hi * (1 + ext)) & ~(P.shift(1) > hi.shift(1))   # 오늘 처음 돌파
    rel = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0)
    R = C.pct_change()
    pos = {}   # t → dict(w, entry, max, held, ent_i)
    cash = 1.0  # 비중(킥 계좌 안)
    pend_in, pend_out = [], []
    last_exit = {}
    rets, turns, trades = [], [], []
    Pv, BRK, REL = P.values, brk.values, rel.values
    col = {t: j for j, t in enumerate(U)}
    pos_i = {d: i for i, d in enumerate(C.index)}
    for d in idx:
        i = pos_i[d]
        # 1) 오늘 수익 반영 (어제 종가 → 오늘 종가)
        r = cash * R.at[d, "BIL"]
        for t, p in pos.items():
            rt = R.at[d, t]
            rt = 0.0 if pd.isna(rt) else rt
            r += p["w"] * rt
            p["w"] *= 1 + rt
        cash *= 1 + R.at[d, "BIL"]
        tot = cash + sum(p["w"] for p in pos.values())
        cash /= tot
        for p in pos.values():
            p["w"] /= tot
        # 2) 어제 정한 주문을 오늘 종가에 체결
        tv = 0.0
        for t in pend_out:
            if t in pos:
                p = pos.pop(t)
                px = Pv[i, col[t]]
                trades.append({"t": t, "in": str(C.index[p["ent_i"]].date()), "out": str(d.date()), "r": round(px / p["entry"] - 1, 4)})
                cash += p["w"]; tv += p["w"]; last_exit[t] = i
        for t in pend_in:
            if t in pos or len(pos) >= slots:
                continue
            w = min(1.0 / slots, cash)
            if w <= 0:
                continue
            pos[t] = {"w": w, "entry": Pv[i, col[t]], "max": Pv[i, col[t]], "held": 0, "ent_i": i}
            cash -= w; tv += w
        pend_in, pend_out = [], []
        c = tv * COST
        r -= c
        cash -= c
        rets.append(r); turns.append(tv)
        # 3) 오늘 종가로 판단 → 내일 체결
        for t, p in pos.items():
            if p["ent_i"] == i:
                continue
            px = Pv[i, col[t]]
            p["held"] += 1
            p["max"] = max(p["max"], px)
            g = px / p["entry"] - 1
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min):
                pend_out.append(t)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [(REL[i, j], t) for t, j in col.items() if BRK[i, j] and t not in pos and not (t in last_exit and i - last_exit[t] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            pend_in = [t for _, t in cand[:min(free, max_new)]]
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades


def base_account(C, reg, idx):
    G = {"SPY": .475, "QQQ": .475, "GLD": .05, "BIL": 0.0}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11, "BIL": .26}
    R = C[list(G)].pct_change()
    w = None; rets, turns = [], []
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = dict(G if regv.iloc[i - 1] else Rd)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s = sum(nw.values()); w = {k: v / s for k, v in nw.items()}
        # 어제 종가 판정 → 오늘 종가 체결 (국면 바뀌었거나 달 첫날)
        tv = 0.0
        tgt = G if regv.iloc[i - 1] else Rd
        newm = i > 0 and C.index[i - 1].month != d.month
        if newm or regv.iloc[i - 1] != regv.iloc[i - 2]:
            tv = sum(abs(tgt[k] - w[k]) for k in w) / 2
            w = dict(tgt)
            r -= tv * COST
        rets.append(r); turns.append(tv)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx)


def mix(rb, rk, tb, tk, reg, sg, sr):
    """기본·킥 두 계좌 섞기 — 매월 첫날·국면 바뀐 날 목표 크기로 다시 맞춤"""
    regv = reg.reindex(rb.index).fillna(False).shift(1).fillna(False)
    navs, turn = [], 0.0
    s0 = sg if regv.iloc[0] else sr
    B, K = 1 - s0, s0
    prev_m, prev_reg = rb.index[0].month, regv.iloc[0]
    for k, d in enumerate(rb.index):
        B *= 1 + rb.iloc[k]; K *= 1 + rk.iloc[k]
        T = B + K
        turn += (B / T) * tb.iloc[k] + (K / T) * tk.iloc[k] if T > 0 else 0
        g = regv.iloc[k]
        if d.month != prev_m or g != prev_reg:
            s = sg if g else sr
            tv = abs(K / T - s)
            turn += tv
            T *= 1 - tv * COST
            B, K = T * (1 - s), T * s
        prev_m, prev_reg = d.month, g
        navs.append(B + K)
    nav = pd.Series(navs, index=rb.index)
    return nav, turn


def seg(nav, spy, a, b, turn_s=None):
    n = nav[(nav.index >= a) & (nav.index <= b)]
    s = spy[(spy.index >= a) & (spy.index <= b)]
    o = stats(n / n.iloc[0], s / s.iloc[0])
    o.pop("yr", None)
    if turn_s is not None:
        tt = turn_s[(turn_s.index >= a) & (turn_s.index <= b)].sum()
        o["turn"] = round(tt / ((n.index[-1] - n.index[0]).days / 365.25) * 100)
    return o


def run_mix(rb, tb, kick, reg, sg, sr):
    rk, tk, _ = kick
    nav, _ = mix(rb, rk, tb, tk, reg, sg, sr)
    # 일별 회전(근사): 그날 목표 크기로 기본·킥 회전을 가중
    regv = reg.reindex(rb.index).fillna(False).shift(1).fillna(False)
    s = regv.map({True: sg, False: sr})
    tdaily = (1 - s) * tb + s * tk
    return nav, tdaily


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_account(C, reg, idx)
    kick0 = kick_account(C, idx)
    tr = kick0[2]

    def tstat(a, b):
        x = [t["r"] for t in tr if a <= t["in"] <= b]
        if not x:
            return {}
        w = [v for v in x if v > 0]; l = [v for v in x if v <= 0]
        return {"n": len(x), "avg": round(np.mean(x) * 100, 2), "win": round(len(w) / len(x) * 100), "pf": round(sum(w) / -sum(l), 2) if l and sum(l) < 0 else None}

    knav = (1 + kick0[0]).cumprod()
    res = {"kick_only": {"is": seg(knav, spy, START, IS_END, kick0[1]), "oos": seg(knav, spy, OOS_START, END, kick0[1])},
           "trades": {"is": tstat(START, IS_END), "oos": tstat(OOS_START, END)}}
    SG = [0, .05, .10, .15, .20, .25, .30]
    RR = [0, .5, 1.0]
    grid = []
    for sg in SG:
        for rr in RR:
            if sg == 0 and rr > 0:
                continue
            nav, td = run_mix(rb, tb, kick0, reg, sg, sg * rr)
            grid.append({"sg": sg, "sr": round(sg * rr, 3), "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)})
    # 고르기: 앞 구간 샤프 최고 (같으면 작은 칸)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], -g["sg"]))
    rr_b = best["sr"] / best["sg"] if best["sg"] else 0
    nav_cur, td_cur = run_mix(rb, tb, kick0, reg, .19, .19)
    current = {"sg": .19, "sr": .19, "is": seg(nav_cur, spy, START, IS_END, td_cur), "oos": seg(nav_cur, spy, OOS_START, END, td_cur)}
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    # ±20% 흔들기 — 크기, 그리고 손절·익절
    shake = []
    for f in (0.8, 1.2):
        sg = best["sg"] * f
        nav, td = run_mix(rb, tb, kick0, reg, sg, sg * rr_b)
        shake.append({"what": f"크기 ×{f}", "sg": round(sg, 3), "sr": round(sg * rr_b, 3), "oos": seg(nav, spy, OOS_START, END, td)})
    for name, kw in (("손절 −4%", {"stop": -0.04}), ("손절 −6%", {"stop": -0.06}), ("익절 +12%", {"take": 0.12}), ("익절 +18%", {"take": 0.18})):
        k2 = kick_account(C, idx, **kw)
        nav, td = run_mix(rb, tb, k2, reg, best["sg"], best["sr"])
        shake.append({"what": name, "sg": best["sg"], "sr": best["sr"], "oos": seg(nav, spy, OOS_START, END, td)})

    def ok(o, c):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > c["oos"]["sharpe"])}
    chk = ok(best["oos"], current)
    shake_ok = bool(all(all(ok(s["oos"], current).values()) for s in shake))
    if all(chk.values()) and shake_ok:
        verdict = "✅ 통과"
    elif any(chk.values()):
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": spy_row, "current": current, "best": best, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "shake": shake, "grid": grid, **res,
           "note": "킥 신호 대신 섹터·테마 ETF 52주 신고가 돌파 · 기본 = C안 뼈대 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 고래 바스켓·실적 갭·컵 등 실제 신호는 역사 없음 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("현재", current["oos"])
    print("고른", best["sg"], best["sr"], best["is"]["sharpe"], best["oos"])
    print("킥만", res)
    for g in grid:
        print(g["sg"], g["sr"], "IS", g["is"]["cagr"], g["is"]["mdd"], g["is"]["sharpe"], "| OOS", g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"].get("turn"))
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
