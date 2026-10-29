"""📈 10/29 16시 2번 — 🎚 위험 선택지 메뉴 (이번 주 첫 번째) · 지금 실제 규칙(🧭 추세 주차 + 🔄 월말 흐름) 위에서
  💼: 목표 변동성 12·15(지금)·18·22·30%  × 아래 한도 30%(지금)·50%
  🎯: 목표 변동성 18·22(지금)·26·30%     × 아래 한도 50·70%(지금)
  각 칸: 앞 2008-07~16 / 뒤 2017~ 연수익·변동성·낙폭·샤프 · 2008·2020·2022 해 성적 · 회전
  레버리지 없음(주식 칸 최대 = 원래 비중) — 사용자가 고를 「위험 결정」 메뉴이지 성과 개선 주장 아님
→ market/lab/k1029_riskmenu.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import G_PORT, RD_PORT, G_CONC, RD_CONC, drifts, make, core_run

OUT = Path("market/lab/k1029_riskmenu.json")


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
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    sig, fs = make(C, DM, DQ)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}

    def go(G, Rd, tgt, floor):
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, sig, fs, G, Rd)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
             "full": seg(nav, spy, START, END, td)}
        d = nav.pct_change().fillna(0)
        o["y"] = {y: round(((1 + d[d.index.year == y]).prod() - 1) * 100, 1) for y in (2008, 2011, 2018, 2020, 2022, 2025, 2026)}
        o["eq_avg"] = round(float(((sc.reindex(idx)) * 100).mean()), 1)
        o["eq_now"] = round(float(sc.reindex(idx).iloc[-1] * 100), 1)
        return o
    out["port"] = {}
    for tgt in (12.0, 15.0, 18.0, 22.0, 30.0):
        for fl in (0.3, 0.5):
            k = f"t{int(tgt)}_f{int(fl * 100)}"
            out["port"][k] = go(G_PORT, RD_PORT, tgt, fl)
            print("PORT", k, out["port"][k]["is"], out["port"][k]["oos"], out["port"][k]["y"], flush=True)
    out["conc"] = {}
    for tgt in (18.0, 22.0, 26.0, 30.0):
        for fl in (0.5, 0.7):
            k = f"t{int(tgt)}_f{int(fl * 100)}"
            out["conc"][k] = go(G_CONC, RD_CONC, tgt, fl)
            print("CONC", k, out["conc"][k]["is"], out["conc"][k]["oos"], out["conc"][k]["y"], flush=True)
    sp = spy.pct_change().fillna(0)
    out["spy"] = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END),
                  "y": {y: round(((1 + sp[sp.index.year == y]).prod() - 1) * 100, 1) for y in (2008, 2011, 2018, 2020, 2022, 2025, 2026)}}
    out["now"] = {"port": "t15_f30", "conc": "t22_f70", "rv20": round(float(rv.iloc[-1]), 1)}
    out["doc"] = __doc__
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
