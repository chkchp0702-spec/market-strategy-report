"""📈 11/5 12시 3번 — k1105_blend 에서 나온 질문: 「🎯 는 💼 보다 위험 한 단위당 덜 번다(상관 0.98)」
  → 🎯 의 위험 크기(앞 구간 변동성)를 그대로 두고, 담는 틀만 💼 식(아래 한도 30%·금 칸)으로 바꾸면 같은 위험에서 더 버나?
  판:
    P_T   — 💼 틀(S47.5·Q47.5·금5 / 하락 31.5·31.5·금11 · 한도 30%) + 목표 T(🎯 앞 변동성에 맞춤, 이분 탐색)
    F30_T — 🎯 틀(50·50 / 25·25, 금 없음) + 한도 30% + 목표 T 맞춤
    G_T   — 🎯 틀 + 금 칸(💼 비율) + 한도 70% + 목표 T 맞춤
  모두 월말 흐름·🧭 추세 칸·국면 그대로 · 비용 0.1%(+0.25%) · 하루 늦은 체결 · 레버리지 없음
  판정: 앞 2008-07~16 에서 변동성 맞춘 판 앞 연수익 ≥0 · 뒤 2017~ 연 +1%p(🟡 +0.33) · 흔들기(한도 ±20%·목표 ±20% — 기준도 같은 목표 흔들기)
→ market/lab/k1105_concport.json
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
import k1028_qflow as QF
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC, G_PORT, RD_PORT

OUT = Path("market/lab/k1105_concport.json")
G_CG = {"SPY": .475, "QQQ": .475, "GLD": .05}
RD_CG = {"SPY": .25, "QQQ": .25, "GLD": .11}


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

    def go(G, Rd, tgt, floor, cost=0.001):
        QF.COST = cost
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, sigM, fsM, G, Rd)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "nav": nav}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    def clean(r):
        return {"is": r["is"], "oos": r["oos"]}

    def matched(G, Rd, floor, base, cost=0.001, lo=14.0, hi=40.0):
        best = None
        for _ in range(7):
            m = (lo + hi) / 2; r = go(G, Rd, m, floor, cost)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    VARS = {"P": (G_PORT, RD_PORT, 0.30), "F30": (G_CONC, RD_CONC, 0.30), "G": (G_CG, RD_CG, 0.70),
            "F50": (G_CONC, RD_CONC, 0.50), "PG70": (G_PORT, RD_PORT, 0.70)}
    res = {}
    for cost in (0.001, 0.0025):
        B = go(G_CONC, RD_CONC, 22.0, 0.70, cost)
        rc = {"base": clean(B), "v": {}}
        for nm, (G, Rd, fl) in VARS.items():
            t, r = matched(G, Rd, fl, B, cost)
            rc["v"][nm] = {"tgt": t, "d": dlt(B, r), "is": r["is"], "oos": r["oos"]}
            print(cost, nm, t, rc["v"][nm]["d"], flush=True)
            if cost == 0.001:
                yr = {}
                for y in range(2008, idx[-1].year + 1):
                    a = B["nav"][B["nav"].index.year == y]; b = r["nav"][r["nav"].index.year == y]
                    if len(a) > 5:
                        yr[str(y)] = round(float((b.iloc[-1] / b.iloc[0] - a.iloc[-1] / a.iloc[0]) * 100), 2)
                rc["v"][nm]["yr"] = yr
        res[str(cost)] = rc
    out["res"] = res
    cand = res["0.001"]["v"]
    pick = max(cand, key=lambda k: cand[k]["d"]["is"]["sharpe"] + cand[k]["d"]["is"]["cagr"] / 10)
    out["is_pick"] = pick
    G, Rd, fl = VARS[pick]
    sh = {}
    for vn, (tf, ff) in {"tgt-20": (0.8, 1.0), "tgt+20": (1.2, 1.0), "floor-20": (1.0, 0.8), "floor+20": (1.0, 1.2)}.items():
        B2 = go(G_CONC, RD_CONC, 22.0 * tf, 0.70 * ff if vn.startswith("floor") else 0.70)
        t, r = matched(G, Rd, fl * ff, B2)
        sh[vn] = {"tgt": t, "d": dlt(B2, r)}
        print("SHAKE", vn, sh[vn], flush=True)
    out["shake"] = sh
    d = cand[pick]["d"]
    out["judge"] = {"pick": pick, "is": d["is"]["cagr"], "oos": d["oos"]["cagr"],
                    "shake_ok": all(v["d"]["oos"]["cagr"] > 0 for v in sh.values()),
                    "cost25_oos": res["0.0025"]["v"][pick]["d"]["oos"]["cagr"]}
    j = out["judge"]
    j["verdict"] = "✅" if (j["oos"] > 1.0 and j["is"] >= 0 and j["shake_ok"]) else ("🟡" if (j["oos"] >= 0.33 and j["is"] >= 0) else "❌")
    print("JUDGE", j, flush=True)
    out["note"] = "기준 = 지금 🎯(22%·70%·월말 흐름·🧭 추세 칸) · 판마다 앞 구간 변동성을 🎯 와 같게(같은 위험) · 레버리지 없음 · ETF 만 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
