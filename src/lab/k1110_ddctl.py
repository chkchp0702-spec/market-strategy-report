"""📈 11/10 16시 — 🎯 「그림자 낙폭 손잡이」 + 「분산 역수 모양」 — 🎯 뒤 구간 최대낙폭 1/3 줄이기 시험
  문제: 🎯 뒤 구간(2017~) 최대낙폭 −24.7%(2020·2022) — 200일선 국면 + 변동성 맞춤(22%·아래 70%) 뒤에도 남는 낙폭
  ① 그림자 낙폭(드로다운 컨트롤 · Grossman-Zhou 1993 / CPPI 계열): 지금 규칙 🎯 의 「손잡이 없는」 그림자 순자산이
     고점보다 a% 넘게 빠지면 주식 칸 × m = clip(1 − (낙폭 − a) / b, lo, 1) · 그날 종가까지로 정하고 다음 날부터 · 덜어낸 몫은 추세·현금 칸
  ② 분산 역수 모양(Moreira-Muir 2017 「volatility-managed」): 주식 × min(1, (22 / 변동성)^p) · p 1.5·2 (지금 p=1)
  틀 = k1109_fill 의 🎯(k1028_qflow core_run · 월말 흐름 있는 옛 기준판) · 같은 위험 = 앞 구간 변동성 맞춘 목표 · 비용 0.1% · 레버리지 없음 · ETF 라 생존 편향 없음
  판정: 뒤 낙폭 1/3(−24.7 → −16.5 안쪽) 또는 같은 위험 뒤 +1%p · 앞 ≥0 · ±20% 흔들기
→ market/lab/k1110_ddctl.json
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
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, core_run as conc_run, G_CONC, RD_CONC

OUT = Path("market/lab/k1110_ddctl.json")


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    sigM, fsM = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}

    def scale(tgt, floor, p):
        return ((tgt / rv) ** p).clip(upper=1.0, lower=floor).fillna(1.0)

    shadow_cache = {}

    def shadow(tgt, floor):
        k = (round(tgt, 3), round(floor, 3))
        if k not in shadow_cache:
            nav, _ = conc_run(C, reg, idx, scale(tgt, floor, 1.0), sigM, fsM, G_CONC, RD_CONC)
            shadow_cache[k] = nav
        return shadow_cache[k]

    def go(tgt=22.0, floor=0.70, p=1.0, dd=None):
        sc = scale(tgt, floor, p)
        if dd is not None:
            a, b, lo = dd
            nav0 = shadow(22.0, 0.70)   # 그림자 = 지금 규칙 🎯(손잡이 없음) — 고정
            ddv = (1 - nav0 / nav0.cummax()) * 100
            m = (1 - (ddv - a).clip(lower=0) / b).clip(lower=lo, upper=1.0)
            sc = (sc * m.reindex(C.index).fillna(1.0)).clip(upper=1.0)
        nav, td = conc_run(C, reg, idx, sc, sigM, fsM, G_CONC, RD_CONC)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "nav": nav}

    def dlt(a, b):
        return {q: {kk: round(float(b[q][kk] - a[q][kk]), 2) for kk in ("cagr", "mdd", "sharpe", "vol")} for q in ("is", "oos")}

    def matched(base, tgt0, **kw):
        lo, hi = tgt0 * 0.6, tgt0 * 1.6
        best = None
        for _ in range(6):
            mm = (lo + hi) / 2; r = go(tgt=mm, **kw)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (mm, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = mm
            else:
                lo = mm
        return round(best[0], 2), best[1]

    clean = lambda r: {"is": r["is"], "oos": r["oos"]}
    B = go()
    print("BASE", clean(B), flush=True)
    cands = {}
    for a in (5, 10, 15):
        for b in (10, 20):
            cands[f"dd_a{a}_b{b}"] = dict(dd=(a, b, 0.4))
    cands["p1.5"] = dict(p=1.5); cands["p2"] = dict(p=2.0)
    res = {}
    for nm, kw in cands.items():
        raw = go(**kw)
        mt, mr = matched(B, 22.0, **kw)
        res[nm] = {"raw": dlt(B, raw), "raw_is": raw["is"], "raw_oos": raw["oos"], "tgt": mt, "m": dlt(B, mr), "m_is": mr["is"], "m_oos": mr["oos"]}
        print(nm, "RAW", res[nm]["raw"], "| MATCH", mt, res[nm]["m"], flush=True)
    # 앞 구간에서 고르기: 같은 위험 앞 샤프 + 앞 낙폭 개선
    pick = max(res, key=lambda k: res[k]["m"]["is"]["sharpe"] + res[k]["raw"]["is"]["mdd"] / 20)
    kw0 = cands[pick]
    sh = {}
    if "dd" in kw0:
        a, b, lo = kw0["dd"]
        vars_ = {"a-20": dict(dd=(a * .8, b, lo)), "a+20": dict(dd=(a * 1.2, b, lo)), "b-20": dict(dd=(a, b * .8, lo)),
                 "b+20": dict(dd=(a, b * 1.2, lo)), "lo-20": dict(dd=(a, b, lo * .8)), "lo+20": dict(dd=(a, b, lo * 1.2))}
    else:
        pp = kw0["p"]
        vars_ = {"p-20": dict(p=1 + (pp - 1) * .8), "p+20": dict(p=1 + (pp - 1) * 1.2)}
    for vn, kw in vars_.items():
        raw = go(**kw); mt, mr = matched(B, 22.0, **kw)
        sh[vn] = {"raw": dlt(B, raw), "m": dlt(B, mr)}
        print("SHAKE", vn, sh[vn], flush=True)
    # 해별 (고른 판 raw vs 기준)
    nb, nc = B["nav"], go(**kw0)["nav"]
    yr = {}
    for y in sorted(set(nb.index.year)):
        xb = nb[nb.index.year == y]; xc = nc[nc.index.year == y]
        if len(xb) > 20:
            yr[str(y)] = [round((xb.iloc[-1] / xb.iloc[0] - 1) * 100, 1), round((xc.iloc[-1] / xc.iloc[0] - 1) * 100, 1)]
    out.update({"base": clean(B), "cands": res, "is_pick": pick, "shake": sh, "yr_pick": yr,
                "note": "raw = 같은 목표 22(덜 흔들림), m = 앞 구간 변동성 맞춘 목표(같은 위험) · 그림자 = 지금 규칙 🎯 순자산(손잡이 없음)의 고점 대비 낙폭 · 🎯 는 k1028_qflow 옛 기준판(예약 종가 아님) · 매수 추천 아님"})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
