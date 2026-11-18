"""📈 11/18 12시 — k1118_portattack: Q11/17-1(⚔️ QQQ 코어 + 월말 흐름 몫 1.0, 🎯 에 ✅ 11/18 적용) 을 💼 기본 포트에도 붙이면?
  + 새 기준(🎯 NEW)이 2025·2026 에 SPY 에 뒤진 원인 분해(국면 끔 · 변동성 맞춤 끔 · 흐름 끔 · 추세 칸 대신 현금)
  크기 산수: 💼 = 🎯 와 같은 뼈대(상관 0.98) · k1117_attack2 💼 판 19.79 vs 16.68 = +3.11 (흔들기·해별·0.25%·하루 늦음 미확인) → 실험
  틀: k1106_exectime3.run (예약 종가판 c1) · k1117_attack2 와 같은 자료·손잡이
→ market/lab/k1118_portattack.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS
from k1112_strongcore import yearly

OUT = Path("market/lab/k1118_portattack.json")
A = math.sqrt(252) * 100


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k, None)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    CASH = cdl.reindex(C.index).fillna(0.0)
    DM, DQ = drifts(C)
    FL = {}

    def flow(f=0.6, sh=1, K=5):
        key = (f, sh, K)
        if key not in FL:
            ms_, fs_ = make(C, DM, DQ, f=f, K=K)
            FL[key] = (ms_.shift(-sh).fillna(0.0), fs_.shift(-sh).fillna(0.0))
        return FL[key]

    def full(e, trd_cash=False):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e; D["QQQ"] = e
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = CASH if trd_cash else C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    mix = 0.5 * rS + 0.5 * rQ
    allon = pd.Series(True, index=C.index)
    G_PNG = {"SPY": .5, "QQQ": .5, "GLD": 0.0}; RD_PNG = {"SPY": .315, "QQQ": .315, "GLD": 0.0}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT),
          "port_ng": (15.0, 0.30, G_PNG, RD_PNG)}
    res = {}

    def go(nm, core, base="conc", f=0.6, sh=1, K=5, cost=0.001, tgt=None, fl=None, novol=False, noreg=False, trd_cash=False):
        t0, fl0, G, Rd = TG[base]
        t0 = tgt or t0; fl0 = fl if fl is not None else fl0
        if novol:
            sc = pd.Series(1.0, index=C.index)
        else:
            sc = (t0 / (core.rolling(20).std() * A)).clip(upper=1.0, lower=fl0).fillna(1.0)
        sig, fs = flow(f, sh, K) if f > 0 else (pd.Series(0.0, index=C.index), pd.Series(0.0, index=C.index))
        nav, td = run(C, Z, full(core, trd_cash), allon if noreg else reg, idx, sc, sig, fs, G, Rd, "c1", cost)
        r = {k: seg(nav, spy, a, b, td) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()}
        yr = yearly(nav)
        r.update({"yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                  "worst_is": min(v for y, v in yr.items() if y < 2017)})
        res[nm] = r
        print(nm, "앞", r["is"]["cagr"], r["is"]["mdd"], "| 뒤", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"],
              "최악", r["worst_oos"], "| 25", yr.get(2025), "26", yr.get(2026), flush=True)

    # ① 💼 에 Q11/17-1 붙이기 (재현: k1117_attack2 port_base 16.68 · NEW__port 19.79)
    go("P_base", mix, "port"); go("P_NEW", rQ, "port", f=1.0)
    go("P_Q", rQ, "port"); go("P_F", mix, "port", f=1.0)
    go("P_NEW_f08", rQ, "port", f=0.8)
    go("P_NEW_t12", rQ, "port", f=1.0, tgt=12.0); go("P_NEW_t18", rQ, "port", f=1.0, tgt=18.0)
    go("P_NEW_l24", rQ, "port", f=1.0, fl=0.24); go("P_NEW_l36", rQ, "port", f=1.0, fl=0.36)
    go("P_NEW_K4", rQ, "port", f=1.0, K=4); go("P_NEW_K6", rQ, "port", f=1.0, K=6)
    go("P_base_c25", mix, "port", cost=0.0025); go("P_NEW_c25", rQ, "port", f=1.0, cost=0.0025)
    go("P_base_s0", mix, "port", sh=0); go("P_NEW_s0", rQ, "port", f=1.0, sh=0)
    go("P_NEW_ng", rQ, "port_ng", f=1.0)        # 💼 금 5%(🔴 11%) 칸 빼기 — 방어 칸 줄이기
    # ② 🎯 NEW 2025·2026 원인 분해 (재현: base 17.66 · NEW 21.50)
    go("base", mix); go("NEW", rQ, f=1.0)
    go("NEW_noreg", rQ, f=1.0, noreg=True)       # 국면 끔(늘 🟢)
    go("NEW_novol", rQ, f=1.0, novol=True)       # 변동성 맞춤 끔(늘 1.0)
    go("NEW_noflow", rQ, f=0.0)                  # 월말 흐름 끔
    go("NEW_trdcash", rQ, f=1.0, trd_cash=True)  # 추세 칸 자리 = 현금
    go("NEW_bare", rQ, f=0.0, novol=True, noreg=True)   # 다 끔 ≈ QQQ 그냥(체결 비용만)
    go("P_NEW_noreg", rQ, "port", f=1.0, noreg=True); go("P_NEW_novol", rQ, "port", f=1.0, novol=True)
    go("P_NEW_noflow", rQ, "port", f=0.0); go("P_NEW_trdcash", rQ, "port", f=1.0, trd_cash=True)

    qqq = C["QQQ"].reindex(idx); trd = C["TRD"].reindex(idx)
    regd = reg.reindex(idx)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {k: seg(spy, spy, a, b) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()},
           "qqq": {k: seg(qqq, spy, a, b) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()},
           "spy_yr": yearly(spy), "qqq_yr": yearly(qqq), "trd_yr": yearly(trd),
           "red_days_yr": {y: round(float((~regd[regd.index.year == y].astype(bool)).mean()) * 100, 1)
                           for y in range(2009, idx[-1].year + 1)},
           "res": res,
           "note": ("k1106_exectime3.run 예약 종가판 c1 · 비용 0.1% · P_ = 💼(목표 15·아래 0.30·금 5%/🔴 11%) · 무접두 = 🎯(목표 22·0.70) · "
                    "NEW = 코어 QQQ 100% + 월말 흐름 몫 1.0 · Q = QQQ 만 · F = 흐름 1.0 만 · s0 = 하루 늦은 알림 · ng = 금 칸 없앰 · "
                    "noreg/novol/noflow/trdcash = 국면·변동성 맞춤·흐름 끔·추세 칸 자리 현금 · ETF 만, 생존 편향 없음 · 레버리지 없음 · 매수 추천 아님")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
