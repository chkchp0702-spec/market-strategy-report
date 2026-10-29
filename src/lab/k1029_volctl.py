"""📈 10/29 10시 — 🎚 「변동성 맞춤 펀드(vol-control)가 이틀 뒤 억지로 사고팔 몫 앞지르기」
  발상: S&P 위험 관리(Risk Control) 지수·변동성 맞춤 펀드는 노출 = 목표 변동성 ÷ 실현 변동성(상한 150%)
    · 실현 변동성 = 지수 가중 0.94·0.97 중 큰 값 · **관측 뒤 이틀 늦게 리밸런싱**(TradingView 「Vol-Control Fund Positioning」·
    Milliman vol control 자료·골드만/노무라 「vol-control 매도 예상」 기사들)
    → 오늘 종가로 「앞으로 이틀 동안 그들이 사야/팔아야 할 몫」을 미리 셀 수 있음(가격과 무관하게 나오는 억지 흐름)
  신호(전날 종가까지만): E_t = 1/3·[EWMA 설계 + 21일 + 63일] 노출(목표 10%·상한 1.5) · F_t = E_t − E_{t−k}(아직 안 집행된 몫)
    체결은 하루 늦게: j일 보유는 F_{j−2} 로 정함(j−1 종가에 바꿈)
    F > +th(그들이 살 차례) → 💼 금·🧭추세 칸 f 를 주식으로 · F < −th(팔 차례) → 주식 칸 f 를 채권(TLT/IEF)으로
  기준점 = 지금 실제 💼(C안 뼈대 + 변동성 맞춤 15%/30% + 🧭추세 주차 + 🔄 월말 흐름 K5·±0.5%p·60%·TLT·하루 늦음)
    월말 흐름 신호가 켜진 날은 그쪽이 우선(겹치면 새 신호 안 씀)
  대조군: 같은 창의 SPY 수익 부호(단기 추세/반전) 신호 · 판정: 앞 2008-07~2016 고르고 뒤 2017~ 시험 · ±20% 흔들기 · 회전 × 0.1%
  덤: 🔄 월말 흐름 2026 올해 달별 손익 분해(어제 16시 계획 ①)
→ market/lab/k1029_volctl.json
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
from k1011_size import load, seg, COST
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_rebalflow4 import sig_lag

OUT = Path("market/lab/k1029_volctl.json")


def exposure(spy_r, tgt=0.10, cap=1.5, designs=("ewma", "m1", "m3")):
    r = spy_r.fillna(0.0)
    ex = []
    if "ewma" in designs:
        v94 = (r ** 2).ewm(alpha=1 - 0.94, adjust=False).mean()
        v97 = (r ** 2).ewm(alpha=1 - 0.97, adjust=False).mean()
        sg = np.sqrt(np.maximum(v94, v97) * 252)
        ex.append((tgt / sg).clip(upper=cap))
    if "m1" in designs:
        ex.append((tgt / (r.rolling(21).std() * math.sqrt(252))).clip(upper=cap))
    if "m3" in designs:
        ex.append((tgt / (r.rolling(63).std() * math.sqrt(252))).clip(upper=cap))
    return pd.concat(ex, axis=1).mean(axis=1)


def vsig(C, k=2, th=0.10, tgt=0.10, lag=2, designs=("ewma", "m1", "m3"), side="sym"):
    E = exposure(C["SPY"].pct_change(), tgt=tgt, designs=designs)
    F = (E - E.shift(k)).shift(lag).fillna(0.0)
    out = pd.Series(0.0, index=C.index)
    if side in ("sym", "buy"):
        out[F > th] = -1.0          # −1 = 주식 쪽(월말 흐름과 같은 부호 약속: +1 = 채권 쪽)
    if side in ("sym", "sell"):
        out[F < -th] = 1.0
    return out, F


def ctrl_sig(C, k=2, lag=2, th=0.0):
    r = C["SPY"].pct_change(k).shift(lag).fillna(0.0)
    out = pd.Series(0.0, index=C.index)
    out[r > th] = -1.0; out[r < -th] = 1.0
    return out


def edge(C, sig, a, b, bond="IEF"):
    r = (C["SPY"].pct_change() - C[bond].pct_change()).fillna(0.0)
    out = {}
    for nm, m0 in (("all", sig != 0), ("buy", sig < 0), ("sell", sig > 0)):
        m = (sig.index >= a) & (sig.index <= b) & m0
        x = (-sig[m] * r[m]) * 1e4
        if len(x) < 5:
            out[nm] = {"n": int(len(x))}; continue
        out[nm] = {"n": int(len(x)), "bp": round(float(x.mean()), 1), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2)}
    return out


def core_run2(C, reg, idx, sc, sig, fser, bond="TLT", band=0.05):
    G = {"SPY": .475, "QQQ": .475, "GLD": .05}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    keys = ["SPY", "QQQ", "GLD", "TRD", "BND"]
    Cx = C.copy(); Cx["BND"] = C[bond]
    R = Cx[keys].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i, s_now, f):
        b = G if bool(regv.iloc[i]) else Rd
        s = float(sc.iloc[i])
        e = (b["SPY"] + b["QQQ"]) * s
        gl = b["GLD"]; trd = 1 - e - gl; bnd = 0.0
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and f > 0:
            mv = (gl + trd) * f
            e += mv; gl *= (1 - f); trd *= (1 - f)
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": gl, "TRD": trd, "BND": bnd}
    w, last, lsig = None, None, 0.0
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1, 0.0, 0.0); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        j = i + 1
        snext = float(sig.iloc[j]) if j < len(sig) else 0.0
        fn = float(fser.iloc[j]) if j < len(fser) else 0.0
        t = tg(i, snext, fn)
        newm = j < len(C.index) and C.index[j].month != d.month
        tv = 0.0
        if newm or snext != lsig or regv.iloc[i] != regv.iloc[i - 1] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t)
            r -= tv * COST
        lsig = snext
        rets.append(r); turns.append(tv)
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "to": END}

    # ① 맞대기(SPY−IEF / SPY−TLT) — 메커니즘이 우리 자료에 있나
    ls = {}
    for k in (1, 2, 3, 5):
        for th in (0.05, 0.10, 0.15):
            sg, _ = vsig(C, k=k, th=th)
            ls[f"k{k}_th{th}"] = {"is": edge(C, sg, START, IS_END), "oos": edge(C, sg, OOS_START, END),
                                 "oos_TLT": edge(C, sg, OOS_START, END, "TLT")}
            print("LS", k, th, ls[f"k{k}_th{th}"], flush=True)
    for k in (2, 3):
        cs = ctrl_sig(C, k=k)
        ls[f"CTRL_ret_k{k}"] = {"is": edge(C, cs, START, IS_END), "oos": edge(C, cs, OOS_START, END)}
        print("CTRL", k, ls[f"CTRL_ret_k{k}"], flush=True)
    sg, _ = vsig(C, k=2, th=0.10, lag=1)
    ls["sameclose_k2_th0.1"] = {"is": edge(C, sg, START, IS_END), "oos": edge(C, sg, OOS_START, END)}
    out["ls"] = ls

    # ② 💼 위에 얹기
    MF = sig_lag(C, 5, 0.005, 2)          # 지금 적용된 🔄 월말 흐름
    SC = {}

    def scf(tgt=15.0, floor=0.30):
        if (tgt, floor) not in SC:
            SC[(tgt, floor)] = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        return SC[(tgt, floor)]
    VS = {}

    def go(mf=True, k=2, th=0.10, f=0.0, side="sym", bond="TLT", vt=0.10, tgt=15.0, floor=0.30, ret_nav=False):
        sig = MF.copy() if mf else pd.Series(0.0, index=C.index)
        fs = pd.Series(0.6 if mf else 0.0, index=C.index)
        fs[sig == 0] = 0.0
        if f > 0:
            key = (k, th, side, vt)
            if key not in VS:
                VS[key] = vsig(C, k=k, th=th, tgt=vt, side=side)[0]
            v = VS[key]
            m = (sig == 0) & (v != 0)
            sig[m] = v[m]; fs[m] = f
        nav, td = core_run2(C, reg, idx, scf(tgt, floor), sig, fs, bond)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        return (o, nav) if ret_nav else o

    def dlt(a, b):
        return {p: {"cagr": round(b[p]["cagr"] - a[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - a[p]["mdd"], 2),
                    "sharpe": round(b[p]["sharpe"] - a[p]["sharpe"], 2)} for p in ("is", "oos")}

    B0, nav0 = go(mf=False, ret_nav=True)
    B1, nav1 = go(ret_nav=True)
    out["B0_noflow"] = B0; out["B1_now"] = B1
    print("B0", B0, "\nB1", B1, flush=True)
    # 덤: 월말 흐름 해마다·2026 달별
    d1 = nav1.pct_change().fillna(0); d0 = nav0.pct_change().fillna(0)
    yr = {}
    for y in range(2008, idx[-1].year + 1):
        m = d1.index.year == y
        yr[y] = round(((1 + d1[m]).prod() - (1 + d0[m]).prod()) * 100, 2)
    mo = {}
    for mth in range(1, 13):
        m = (d1.index.year == idx[-1].year) & (d1.index.month == mth)
        if m.sum():
            sgm = MF[(MF.index.year == idx[-1].year) & (MF.index.month == mth)]
            mo[mth] = {"d_pct": round(((1 + d1[m]).prod() - (1 + d0[m]).prod()) * 100, 2),
                       "side": int(sgm[sgm != 0].iloc[0]) if (sgm != 0).any() else 0}
    out["mflow_years"] = yr; out["mflow_2026_months"] = mo
    print("MFLOW yr", yr, "\n2026", mo, flush=True)

    res = {}
    for k in (2, 3, 5):
        for th in (0.05, 0.10, 0.15):
            for f in (0.3, 0.6):
                for side in ("sym", "buy", "sell"):
                    o = go(k=k, th=th, f=f, side=side); nm = f"k{k}_th{th}_f{f}_{side}"
                    res[nm] = {"d": dlt(B1, o), "turn_oos": o["oos"]["turn"]}
                    print(nm, res[nm], flush=True)
    out["grid"] = res
    oos = sorted(v["d"]["oos"]["cagr"] for v in res.values()); iss = sorted(v["d"]["is"]["cagr"] for v in res.values())
    out["median"] = {"is": iss[len(iss) // 2], "oos": oos[len(oos) // 2], "oos_pos": f"{sum(1 for x in oos if x > 0)}/{len(oos)}",
                     "is_pos": f"{sum(1 for x in iss if x > 0)}/{len(iss)}"}
    best = max(res, key=lambda q: res[q]["d"]["is"]["sharpe"] + res[q]["d"]["is"]["cagr"] / 10)
    out["is_pick"] = {"name": best, **res[best]}
    print("MEDIAN", out["median"], "PICK", best, res[best], flush=True)
    # ±20% 흔들기 (뽑힌 것 기준)
    p = best.split("_"); k0 = int(p[0][1:]); th0 = float(p[1][2:]); f0 = float(p[2][1:]); sd = p[3]
    shk = {}
    for nm, kw in {"th-20": dict(th=th0 * 0.8), "th+20": dict(th=th0 * 1.2), "f-20": dict(f=f0 * 0.8), "f+20": dict(f=f0 * 1.2),
                   "vt8": dict(vt=0.08), "vt12": dict(vt=0.12), "k-1": dict(k=max(1, k0 - 1)), "k+1": dict(k=k0 + 1),
                   "IEF": dict(bond="IEF"), "tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0)}.items():
        a = dict(k=k0, th=th0, f=f0, side=sd); a.update(kw)
        base = B1 if "tgt" not in kw else go(tgt=kw["tgt"])
        o = go(**a)
        shk[nm] = {"d": dlt(base, o), "turn_oos": o["oos"]["turn"]}
        print("SHK", nm, shk[nm], flush=True)
    out["shake"] = shk
    # 뽑힌 것 해마다
    o, navp = go(k=k0, th=th0, f=f0, side=sd, ret_nav=True)
    out["pick_abs"] = o
    dp = navp.pct_change().fillna(0)
    out["pick_years"] = {y: round(((1 + dp[dp.index.year == y]).prod() - (1 + d1[d1.index.year == y]).prod()) * 100, 2)
                         for y in range(2008, idx[-1].year + 1)}
    print("PICK yrs", out["pick_years"], flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
