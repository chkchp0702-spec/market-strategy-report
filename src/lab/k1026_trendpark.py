"""📈 10/26 11시 수익률 전략 검증 — 덜어낸 몫 「위기 때 버는 칸」(자산 추세 9종) 주차
  질문: 💼·🎯 의 변동성 맞춤(·국면)으로 덜어낸 현금을, 현금 대신 이미 ✅ 인 🧭 자산 추세 슬리브(GLD USO TLT UUP SPY QQQ EFA EEM DBC,
        N일 고가 돌파 매수 · M일 저가 이탈 매도, 빈 몫은 13주 국채)에 두면 나은가. 레버리지 없음(비중 합 1).
  모드: now = 지금 · vpark = 변동성으로 덜어낸 몫만 추세 칸 · apark = 현금 전부(국면 현금 포함) 추세 칸
  추세 변형: (55/20 · 100/50) × (eq · risk) — 앞(2008-07~16) 샤프로 하나 고르고 뒤(2017~) 시험, 나머지는 흔들기
  비용: 기본 칸 회전 × 0.1% · 추세 칸 안쪽 사고팔기 0.5%(왕복) — 추세 칸 비중 바뀔 때도 회전 × 0.1%
→ market/lab/k1026_trendpark.json
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

OUT = Path("market/lab/k1026_trendpark.json")


def run(C, reg, idx, sc, base, mode, band=0.05):
    if base == "port":
        G = {"SPY": .475, "QQQ": .475, "GLD": .05}
        Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    else:
        G = {"SPY": .5, "QQQ": .5, "GLD": 0.0}
        Rd = {"SPY": .25, "QQQ": .25, "GLD": 0.0}
    keys = ["SPY", "QQQ", "GLD", "BIL", "TRD"]
    R = C[keys].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i):
        on = bool(regv.iloc[i])
        b = G if on else Rd
        s = float(sc.iloc[i])
        e = (b["SPY"] + b["QQQ"]) * s
        cash = 1 - e - b["GLD"]
        if mode == "vpark":
            trd = (b["SPY"] + b["QQQ"]) * (1 - s)
        elif mode == "apark":
            trd = cash
        else:
            trd = 0.0
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": b["GLD"], "TRD": trd, "BIL": cash - trd}
    w, last = None, None
    rets, turns, expo, tw = [], [], [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        t = tg(i - 1)
        newm = C.index[i - 1].month != d.month
        tv = 0.0
        if newm or regv.iloc[i - 1] != regv.iloc[i - 2] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t)
            r -= tv * COST
        rets.append(r); turns.append(tv); expo.append(w["SPY"] + w["QQQ"]); tw.append(w["TRD"])
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx), float(np.mean(expo)), pd.Series(tw, index=idx)


def main():
    C = load()
    px = ydl(["^IRX"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rs, rq = C["SPY"].pct_change(), C["QQQ"].pct_change()
    rv = (0.5 * rs + 0.5 * rq).rolling(20).std() * math.sqrt(252) * 100
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trend_data_from": str(common.date()),
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}, "res": {}}
    # 추세 칸 NAV 들
    TR = {}
    for nin, nout in ((55, 20), (100, 50)):
        for wm in ("eq", "risk"):
            s, tr, op = trend_run(px, cdl, nin, nout, wm, start=str(common.date()))
            s = s.reindex(C.index).fillna(0.0)
            TR[f"{nin}/{nout}|{wm}"] = (1 + s).cumprod()
            sl = (1 + s.reindex(idx)).cumprod()
            out.setdefault("sleeve", {})[f"{nin}/{nout}|{wm}"] = {"is": seg(sl, spy, START, IS_END), "oos": seg(sl, spy, OOS_START, END)}
            # 위기 구간 성적
            cr = {}
            for nm, a, b in (("2008", "2008-09-01", "2009-03-09"), ("2011", "2011-07-22", "2011-10-03"), ("2015", "2015-08-10", "2016-02-11"),
                             ("2018Q4", "2018-10-01", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"),
                             ("2025apr", "2025-02-19", "2025-04-08")):
                q = sl[(sl.index >= a) & (sl.index <= b)]
                p_ = spy[(spy.index >= a) & (spy.index <= b)]
                if len(q) > 5:
                    cr[nm] = [round((q.iloc[-1] / q.iloc[0] - 1) * 100, 1), round((p_.iloc[-1] / p_.iloc[0] - 1) * 100, 1)]
            out["sleeve"][f"{nin}/{nout}|{wm}"]["crisis"] = cr
            print("sleeve", nin, nout, wm, out["sleeve"][f"{nin}/{nout}|{wm}"])
    for base, tgt, floor in (("port", 15.0, 0.30), ("conc", 22.0, 0.70)):
        res = {}
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        for tk, nav_t in TR.items():
            Cx = C.copy(); Cx["TRD"] = nav_t
            for mode in ("now", "vpark", "apark"):
                if mode == "now" and res.get("now"):
                    continue
                nav, td, ex, tw = run(Cx, reg, idx, sc, base, mode)
                k = "now" if mode == "now" else f"{mode}|{tk}"
                yr = {}
                for y in range(2009, idx[-1].year + 1):
                    a = nav[nav.index.year == y]
                    if len(a) > 20:
                        yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
                res[k] = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "expo": round(ex * 100, 1),
                          "trd_avg": round(float(tw.mean()) * 100, 1), "yr": yr}
                print(base, k, "IS", res[k]["is"], "| OOS", res[k]["oos"], "| expo", res[k]["expo"], "trd", res[k]["trd_avg"])
        # 앞 구간 샤프로 고르기
        cands = [k for k in res if k != "now"]
        best = max(cands, key=lambda k: (res[k]["is"].get("sharpe") or -9, res[k]["is"].get("cagr") or -99))
        beat = sum(1 for k in cands if (res[k]["oos"].get("sharpe") or -9) > (res["now"]["oos"].get("sharpe") or -9))
        res["_chosen"] = best
        res["_beat_oos_sharpe"] = f"{beat}/{len(cands)}"
        out["res"][base] = res
        print(base, "chosen", best, res[best]["oos"], "vs now", res["now"]["oos"], "beat", beat, len(cands))
    out["note"] = "덜어낸 몫 자산 추세 칸 주차 · 레버리지 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
