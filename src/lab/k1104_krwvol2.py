"""📈 11/4 12시 (2) — 시차 보정판: 원/달러 KRW=X 는 미국 종가보다 먼저 닫힘 → 미국 종가(t)를 다음 한국일 환율(t+1)로 환산해 변동성 계산(한국 투자자가 실제로 보는 원화 값, 결정은 t+1 미국 종가 체결 전이라 미래 정보 아님) + 5일 묶음 수익 변동성 판 · 💱🦴 「원화로 재는 변동성」: 변동성 맞춤을 달러 변동성 대신 원화 환산 변동성으로 재면?
발상: 우리 계좌는 원화. 미국 주식이 급락할 때 원/달러는 보통 뛰어(달러 강세) 원화 손실이 덜하다.
  지금 규칙은 「달러로 잰 S&P½+나스닥½ 20일 변동성」이 높으면 주식을 덜어냄 → 원화 투자자에게는 실제보다 겁먹고 덜어내는 셈일 수 있음.
  규칙: 주식 × min(1, 목표 ÷ 원화 환산 20일 변동성), 아래 한도 그대로.
비교 (모두 원화 기준 성적 · 지금 규칙 = 🧭 추세 주차 + 🔄 월말 흐름 위):
  ① 🎯 집중(목표 22·한도 70%) / 💼 기본(목표 15·한도 30%) — 💼 는 뼈대 손잡이 닫힘 → 참고로만
  ② 원화 변동성 · 같은 목표
  ③ 원화 변동성 · 앞 구간 평균 주식 비중이 지금과 같아지는 목표(= 같은 평균 위험량, 고르기는 앞 구간만)
  ④ ③ ±20% 흔들기
  ⑤ 같은 위험 맞대기: 달러 변동성 규칙의 목표를 올려 앞 구간 원화 변동성을 ③과 맞춘 판 → 「위험만 늘린 몫」 걸러 냄
앞 2008-07~2016 / 뒤 2017~ · 그날 종가 판단·다음 날부터 · 회전 × 0.1% · 레버리지 없음 · ETF·환율만(생존 편향 없음)
→ market/lab/k1104_krwvol2.json
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

OUT = Path("market/lab/k1104_krwvol2.json")


def kst(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 60:
        return {}
    nav = (1 + r).cumprod()
    yrs = len(r) / 252
    cagr = nav.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * math.sqrt(252)
    return {"cagr": round(cagr * 100, 2), "vol": round(vol * 100, 1),
            "mdd": round(float((nav / nav.cummax() - 1).min()) * 100, 1),
            "sharpe": round(r.mean() * 252 / vol, 2) if vol > 0 else None}


def main():
    from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
    from k1011_size import load
    from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
    from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC, G_PORT, RD_PORT
    C = load()
    px = ydl(["^IRX", "IEF", "KRW=X"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    krw = px.pop("KRW=X")["close"].sort_index()
    ch = krw.pct_change()
    krw[(ch.abs() > 0.08)] = np.nan
    fx = krw.ffill().reindex(C.index).ffill()
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    END = str(idx[-1].date())
    eq = 0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()
    fxr = fx.pct_change().fillna(0.0)
    rv_usd = eq.rolling(20).std() * math.sqrt(252) * 100
    fxn = fx.shift(-1).ffill()
    fxr = fxn.pct_change().fillna(0.0)
    lk = np.log((1 + eq).fillna(1.0)) + np.log((1 + fxr))
    rv_krw = lk.rolling(20).std() * math.sqrt(252) * 100
    rv_krw5 = lk.rolling(5).sum().rolling(60).std() * math.sqrt(252 / 5) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    sigM, fsM = make(C, DM, DQ)
    fxi = fxr.reindex(idx).fillna(0.0)
    isd = idx <= pd.Timestamp(IS_END)

    def scale(rv, tgt, fl):
        return (tgt / rv).clip(upper=1.0, lower=fl).fillna(1.0)

    def run(G, Rd, rv, tgt, fl):
        sc = scale(rv, tgt, fl)
        nav, td = core_run(C, reg, idx, sc, sigM, fsM, G, Rd)
        ru = nav.pct_change().fillna(0.0)
        rk = (1 + ru) * (1 + fxi) - 1
        o = {"tgt": round(tgt, 2)}
        for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
            m = (idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b))
            o[nm] = {"krw": kst(rk[m]), "usd": kst(ru[m]), "eq": round(float(sc.reindex(idx)[m].mean()) * 100, 1),
                     "turn": round(float(td[m].sum()) / (m.sum() / 252) * 100)}
        rk_ = pd.Series(rk.values, index=idx)
        o["y"] = {str(y): round(((1 + rk_[rk_.index.year == y]).prod() - 1) * 100, 1) for y in (2008, 2011, 2015, 2018, 2020, 2022, 2025, 2026)}
        o["eq_now"] = round(float(scale(rv, tgt, fl).reindex(idx).iloc[-1]) * 100, 1)
        return o

    def dl(a, b):
        return {p: {"cagr": round(a[p]["krw"]["cagr"] - b[p]["krw"]["cagr"], 2),
                    "sharpe": round(a[p]["krw"]["sharpe"] - b[p]["krw"]["sharpe"], 2),
                    "mdd": round(a[p]["krw"]["mdd"] - b[p]["krw"]["mdd"], 1)} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "rv_now": {"usd": round(float(rv_usd.iloc[-1]), 1), "krw": round(float(rv_krw.iloc[-2]), 1)},
           "rv_avg_is": {"usd": round(float(rv_usd.reindex(idx)[isd].mean()), 1), "krw": round(float(rv_krw.reindex(idx)[isd].mean()), 1)},
           "corr_eq_fx": round(float(eq.reindex(idx).corr(fxi)), 2), "res": {}}
    spyk = (1 + C["SPY"].pct_change().reindex(idx).fillna(0)) * (1 + fxi) - 1
    out["spy_krw"] = {"is": kst(spyk[isd]), "oos": kst(spyk[~isd])}
    for nm, G, Rd, tgt0, fl, rv_krw in (("conc", G_CONC, RD_CONC, 22.0, 0.70, rv_krw), ("conc_w5", G_CONC, RD_CONC, 22.0, 0.70, rv_krw5), ("port", G_PORT, RD_PORT, 15.0, 0.30, rv_krw)):
        R = {}
        R["base_usd"] = run(G, Rd, rv_usd, tgt0, fl)
        R["krw_same"] = run(G, Rd, rv_krw, tgt0, fl)
        # ③ 앞 구간 평균 주식 배율이 같아지는 원화 목표 (앞 구간만 보고 고름)
        base_eq = float(scale(rv_usd, tgt0, fl).reindex(idx)[isd].mean())
        grid = np.arange(tgt0 * 0.6, tgt0 * 1.2, 0.25)
        gap = [abs(float(scale(rv_krw, t, fl).reindex(idx)[isd].mean()) - base_eq) for t in grid]
        tm = float(grid[int(np.argmin(gap))])
        R["krw_match"] = run(G, Rd, rv_krw, tm, fl)
        R["krw_m80"] = run(G, Rd, rv_krw, tm * 0.8, fl)
        R["krw_m120"] = run(G, Rd, rv_krw, tm * 1.2, fl)
        # ⑤ 같은 위험 맞대기: 달러 규칙 목표를 올려 앞 구간 원화 변동성을 krw_same 에 맞춤
        target_vol = R["krw_same"]["is"]["krw"]["vol"]
        best = None
        for t in np.arange(tgt0, tgt0 * 1.6, 1.0):
            o = run(G, Rd, rv_usd, float(t), fl)
            g = abs(o["is"]["krw"]["vol"] - target_vol)
            if best is None or g < best[0]:
                best = (g, o)
            if o["is"]["krw"]["vol"] > target_vol + 0.3:
                break
        R["usd_samerisk"] = best[1]
        D = {k: dl(R[k], R["base_usd"]) for k in R if k != "base_usd"}
        D["krw_same_vs_usd_samerisk"] = dl(R["krw_same"], R["usd_samerisk"])
        out["res"][nm] = {"runs": R, "delta": D, "match_tgt": round(tm, 2)}
        print(nm, json.dumps(D, ensure_ascii=False), flush=True)
    out["doc"] = __doc__
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
