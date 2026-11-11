"""📈 11/11 12시 — 「코어 두 칸이 각자 판단」: S&P 칸은 S&P 신호로, 나스닥 칸은 나스닥 신호로 (🎯·💼)
  지금: 🎯·💼 의 국면(S&P500 200일선 · 3거래일 확인)과 변동성 맞춤(S&P½+나스닥½ 20일 변동성)이
        두 지수를 한 덩어리로 다룸 → 나스닥이 먼저·더 깊게 무너지는 해(2022: QQQ −33 vs SPY −18)에도 두 칸을 똑같이 덜어냄.
  시험: ① R = 국면만 각자(S&P 칸 ← S&P 200일선, 나스닥 칸 ← 나스닥100 200일선, 둘 다 3일 확인)
        ② V = 변동성 맞춤만 각자(각 칸 × min(1, 목표 ÷ 그 지수 20일 변동성))
        ③ RV = 둘 다
  발상: CFA FAJ 2026 「Best Defensive Strategies」(추세는 하락의 늦은 단계를 막음) · Alpha Architect 2026 국면별 추세 배분 ·
        「한 바구니 신호를 자산별 신호로」 — 새 신호를 더하지 않고 지금 신호를 칸마다 따로 씀
  틀 = k1028_qflow core_run(지금 실제 규칙: 월말 흐름·추세 칸 주차·하루 늦은 체결) 을 칸별 국면·배율로 넓힘 ·
       같은 위험 = 앞 구간 변동성에 맞춘 목표 · 비용 0.1% · 레버리지 없음 · ETF 만 → 생존 편향 없음 · 매수 추천 아님
→ market/lab/k1111_splitcore.json
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
from k1028_qflow import drifts, make, core_run, G_PORT, RD_PORT, G_CONC, RD_CONC

OUT = Path("market/lab/k1111_splitcore.json")


def sticky(s, k=3):
    s = s.fillna(False).astype(bool)
    out, cur, run = [], False, 0
    for v in s.values:
        if v != cur:
            run += 1
            if run >= k:
                cur, run = v, 0
        else:
            run = 0
        out.append(cur)
    return pd.Series(out, index=s.index)


def split_run(C, regS, regQ, idx, scS, scQ, sig, fs, G, Rd, bond="TLT", band=0.05):
    """core_run 과 같은 규칙 — 단 S 칸·Q 칸이 각자 국면(regS/regQ)·배율(scS/scQ). 금 칸은 두 국면 평균."""
    keys = ["SPY", "QQQ", "GLD", "TRD", "BND"]
    Cx = C.copy(); Cx["BND"] = C[bond]
    R = Cx[keys].pct_change().fillna(0.0)
    rS = regS.reindex(C.index).fillna(False).values.astype(bool)
    rQ = regQ.reindex(C.index).fillna(False).values.astype(bool)
    aS = scS.reindex(C.index).fillna(1.0).values; aQ = scQ.reindex(C.index).fillna(1.0).values
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i, s_now, f):
        bS = G if rS[i] else Rd; bQ = G if rQ[i] else Rd
        eS = bS["SPY"] * aS[i]; eQ = bQ["QQQ"] * aQ[i]
        gl = 0.5 * (bS["GLD"] + bQ["GLD"])
        e = eS + eQ; trd = 1 - e - gl; bnd = 0.0
        fS = eS / e if e > 0 else 0.5
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and f > 0:
            e += (gl + trd) * f; gl *= (1 - f); trd *= (1 - f)
        return {"SPY": e * fS, "QQQ": e * (1 - fS), "GLD": gl, "TRD": trd, "BND": bnd}
    w = last = None; lsig = 0.0
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
        fnext = float(fs.iloc[j]) if j < len(fs) else 0.0
        t = tg(i, snext, fnext)
        newm = j < len(C.index) and C.index[j].month != d.month
        tv = 0.0
        flip = (rS[i] != rS[i - 1]) or (rQ[i] != rQ[i - 1])
        if newm or snext != lsig or flip or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t); r -= tv * COST
        lsig = snext
        rets.append(r); turns.append(tv)
    return (1 + pd.Series(rets, index=idx)).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    regA = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    sigM, fsM = make(C, DM, DQ)
    rS_, rQ_ = C["SPY"].pct_change(), C["QQQ"].pct_change()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}

    def reg_of(t, L=200, k=3):
        p = C[t]
        return sticky(p > p.rolling(L).mean(), k).reindex(C.index).fillna(False)

    RQ = {L: reg_of("QQQ", L) for L in (160, 200, 240)}
    RS = {200: regA, 160: reg_of("SPY", 160), 240: reg_of("SPY", 240)}

    def vol(r, n):
        return r.rolling(n).std() * math.sqrt(252) * 100

    VM = {n: vol(0.5 * rS_ + 0.5 * rQ_, n) for n in (16, 20, 24)}
    VS = {n: vol(rS_, n) for n in (16, 20, 24)}
    VQ = {n: vol(rQ_, n) for n in (16, 20, 24)}
    PAR = {"conc": (G_CONC, RD_CONC, 22.0, 0.70), "port": (G_PORT, RD_PORT, 15.0, 0.30)}

    def go(base, tgt=None, R="", V="", L=200, n=20, raw=False):
        G, Rd, t0, floor = PAR[base]; tgt = tgt or t0
        if "S" in V:   # 각자 변동성
            scS = (tgt / VS[n]).clip(upper=1.0, lower=floor).fillna(1.0)
            scQ = (tgt / VQ[n]).clip(upper=1.0, lower=floor).fillna(1.0)
        else:
            scS = scQ = (tgt / VM[n]).clip(upper=1.0, lower=floor).fillna(1.0)
        rS = RS[L]
        rQ = RQ[L] if "S" in R else rS
        if raw:   # 원래 core_run 으로 (기준 재현 확인용)
            nav, td = core_run(C, rS, idx, scS, sigM, fsM, G, Rd)
        else:
            nav, td = split_run(C, rS, rQ, idx, scS, scQ, sigM, fsM, G, Rd)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "nav": nav}

    def dlt(a, b):
        return {q: {kk: round(float(b[q][kk] - a[q][kk]), 2) for kk in ("cagr", "mdd", "sharpe", "vol")} for q in ("is", "oos")}

    def matched(base, B, **kw):
        t0 = PAR[base][2]; lo, hi = t0 * 0.6, t0 * 1.6; best = None
        for _ in range(6):
            mm = (lo + hi) / 2; r = go(base, tgt=mm, **kw)
            if best is None or abs(r["is"]["vol"] - B["is"]["vol"]) < abs(best[1]["is"]["vol"] - B["is"]["vol"]):
                best = (mm, r)
            if r["is"]["vol"] > B["is"]["vol"]:
                hi = mm
            else:
                lo = mm
        return round(best[0], 2), best[1]

    clean = lambda r: {"is": r["is"], "oos": r["oos"]}

    def yearly(nb, nc):
        yr = {}
        for y in sorted(set(nb.index.year)):
            xb = nb[nb.index.year == y]; xc = nc[nc.index.year == y]
            if len(xb) > 20:
                pb = nb[nb.index < xb.index[0]]; pc = nc[nc.index < xc.index[0]]
                b0 = pb.iloc[-1] if len(pb) else xb.iloc[0]; c0 = pc.iloc[-1] if len(pc) else xc.iloc[0]
                yr[str(y)] = [round((xb.iloc[-1] / b0 - 1) * 100, 1), round((xc.iloc[-1] / c0 - 1) * 100, 1)]
        return yr

    for base in ("conc", "port"):
        B = go(base); Braw = go(base, raw=True)
        chk = dlt(Braw, B)
        print(base, "BASE", clean(B), "| 재현 차이", chk, flush=True)
        res = {}
        fam = {"R": dict(R="S"), "V": dict(V="S"), "RV": dict(R="S", V="S")}
        for nm, kw in fam.items():
            r = go(base, **kw); mt, mr = matched(base, B, **kw)
            res[nm] = {"raw": dlt(B, r), "raw_is": r["is"], "raw_oos": r["oos"], "tgt": mt, "m": dlt(B, mr), "m_is": mr["is"], "m_oos": mr["oos"],
                       "yr": yearly(B["nav"], r["nav"])}
            print(base, nm, "RAW", res[nm]["raw"], "| MATCH", mt, res[nm]["m"], flush=True)
        pick = max(res, key=lambda k: res[k]["m"]["is"]["sharpe"] * 10 + res[k]["m"]["is"]["cagr"])
        kw0 = fam[pick]
        sh = {}
        for vn, kx in {"L160": dict(L=160), "L240": dict(L=240), "n16": dict(n=16), "n24": dict(n=24)}.items():
            b2 = go(base, **kx); c2 = go(base, **kw0, **kx)
            mt, mr = matched(base, b2, **kw0, **kx)
            sh[vn] = {"raw": dlt(b2, c2), "m": dlt(b2, mr), "tgt": mt}
            print(base, "SHAKE", pick, vn, sh[vn], flush=True)
        out[base] = {"base": clean(B), "repro_vs_core_run": chk, "fam": res, "is_pick": pick, "shake": sh}
    out["note"] = ("R = 국면만 칸별(S&P 칸 ← SPY 200일선, 나스닥 칸 ← QQQ 200일선, 3일 확인) · V = 변동성 맞춤만 칸별 · RV = 둘 다 · "
                   "raw = 같은 목표, m = 앞 구간 변동성에 맞춘 목표(같은 위험) · 흔들기 = 200일 → 160·240, 20일 → 16·24(기준도 같이 바꿔 비교) · "
                   "🎯 목표 22·한도 70% · 💼 목표 15·한도 30%·금 5/11% · 월말 흐름·추세 칸 주차 포함 · 하루 늦은 체결 · 비용 0.1% · ETF 만 · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
