"""📈 10/28 10시 수익률 전략 — 「묶음」 첫 실험: 앞·뒤 모두 플러스였던 작은 개선 둘을 한꺼번에
  ① k1026: 💼(·🎯) 변동성 맞춤·국면으로 덜어낸 현금 → 이미 ✅ 인 🧭 자산 추세 칸(9종 100/50 돌파 · 변동성 반비례)에 주차
  ② k1019: ⚡ 킥 칸(19%) 안에서 신호 없어 빈 돈 → 현금 대신 💼 기본 칸과 똑같이 굴림
  묶음 = ① 로 바뀐 기본 칸을 ② 의 주차처로 씀(빈 킥 돈도 결국 「기본 칸 + 추세 주차」로)
  지금 규칙: 기본 = C안 뼈대 + 변동성 맞춤(목표 15% · 아래 한도 30%, port.json vol_rule) · 킥 칸 19% · 킥 대용 = 섹터·테마 ETF 52주 돌파
  비교: S0 지금 · S1 ①만 · S2 ②만 · S3 ①+② 함께 (함께 돌린 숫자로 판정)
  흔들기(±20%): 목표 12/18 · 아래 한도 24/36% · 킥 칸 15/23% · 추세 칸 80/40 · 120/60
  전날 종가까지 판단 → 다음 날 체결 · 회전율 × 0.1% · 앞 2008-07~2016 / 뒤 2017~ · 레버리지 없음(비중 합 1)
→ market/lab/k1028_bundle.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import math
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg, COST
from k1012_exits import prep, tstat
from k1014_volw import kick_vw
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1026_trendpark import run as core_run

OUT = Path("market/lab/k1028_bundle.json")


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
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    pos_i = {d: i for i, d in enumerate(C.index)}
    n = len(C.index)
    U, Pv, BRK, REL, R, bil = prep(C)
    VOL = np.full_like(Pv, np.nan, dtype=float)

    TRN = {}

    def trend_nav(nin, nout):
        k = (nin, nout)
        if k not in TRN:
            s, _, _ = trend_run(px, cdl, nin, nout, "risk", start=str(common.date()))
            TRN[k] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
        return TRN[k]

    def core(base, tgt, floor, mode, tr=(100, 50)):
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        Cx = C.copy(); Cx["TRD"] = trend_nav(*tr)
        nav, td, ex, tw = core_run(Cx, reg, idx, sc, base, mode)
        r = nav.pct_change(); r.iloc[0] = nav.iloc[0] - 1
        return r, td, nav

    def arr(rs):
        a = np.zeros(n)
        for d, v in rs.items():
            a[pos_i[d]] = v
        return a

    def total(rb, tb, park, size):
        if park is None:
            kk = kick_vw(C, idx, (U, Pv, BRK, REL, R, bil), VOL); ex = 0
        else:
            kk = kick_vw(C, idx, (U, Pv, BRK, REL, R, park), VOL); ex = 1
        rk = kk[0] - kk[1] * COST * ex
        nav, td = run_mix(rb, tb, (rk, kk[1] * (1 + ex), None), reg, size, size)
        return nav, td

    def row(nav, td):
        yr = {}
        for y in range(2009, idx[-1].year + 1):
            a = nav[nav.index.year == y]
            if len(a) > 20:
                yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "yr": yr}

    def four(tgt=15.0, floor=0.30, size=0.19, tr=(100, 50)):
        r0, t0, _ = core("port", tgt, floor, "now", tr)
        r1, t1, _ = core("port", tgt, floor, "apark", tr)
        o = {}
        o["S0_now"] = row(*total(r0, t0, None, size))
        o["S1_trendpark"] = row(*total(r1, t1, None, size))
        o["S2_kickpark"] = row(*total(r0, t0, arr(r0), size))
        o["S3_bundle"] = row(*total(r1, t1, arr(r1), size))
        # 기본 칸 혼자(킥 없이)
        o["core_now"] = row((1 + r0).cumprod(), t0)
        o["core_tp"] = row((1 + r1).cumprod(), t1)
        return o

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}
    base = four()
    out["base"] = base
    for k, v in base.items():
        print(k, "IS", v["is"], "| OOS", v["oos"])
    # 🎯 집중 (킥 없음) — 참고
    rc0, tc0, _ = core("conc", 22.0, 0.70, "now")
    rc1, tc1, _ = core("conc", 22.0, 0.70, "apark")
    out["conc"] = {"now": row((1 + rc0).cumprod(), tc0), "tp": row((1 + rc1).cumprod(), tc1)}
    print("conc", out["conc"]["now"]["oos"], out["conc"]["tp"]["oos"])

    shakes = {"tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0), "floor24": dict(floor=0.24), "floor36": dict(floor=0.36),
              "kick15": dict(size=0.15), "kick23": dict(size=0.23), "tr80_40": dict(tr=(80, 40)), "tr120_60": dict(tr=(120, 60))}
    sh = {}
    for nm, kw in shakes.items():
        o = four(**kw)
        sh[nm] = {k: {"is": o[k]["is"], "oos": o[k]["oos"]} for k in ("S0_now", "S3_bundle")}
        d_is = o["S3_bundle"]["is"]["cagr"] - o["S0_now"]["is"]["cagr"]
        d_oos = o["S3_bundle"]["oos"]["cagr"] - o["S0_now"]["oos"]["cagr"]
        sh[nm]["d_cagr"] = {"is": round(d_is, 2), "oos": round(d_oos, 2)}
        sh[nm]["d_mdd"] = {"is": round(o["S3_bundle"]["is"]["mdd"] - o["S0_now"]["is"]["mdd"], 2),
                          "oos": round(o["S3_bundle"]["oos"]["mdd"] - o["S0_now"]["oos"]["mdd"], 2)}
        print("shake", nm, sh[nm]["d_cagr"], sh[nm]["d_mdd"])
    out["shake"] = sh
    b0, b3 = base["S0_now"], base["S3_bundle"]
    d = {p: round(b3[p]["cagr"] - b0[p]["cagr"], 2) for p in ("is", "oos")}
    dm = {p: round(b3[p]["mdd"] - b0[p]["mdd"], 2) for p in ("is", "oos")}
    shake_ok = all(v["d_cagr"]["is"] > 0 and v["d_cagr"]["oos"] > 0 for v in sh.values())
    big = d["oos"] >= 1.0 and d["is"] >= 1.0
    mdd_third = all(b3[p]["mdd"] >= b0[p]["mdd"] * (2 / 3) for p in ("is", "oos"))
    out["judge"] = {"d_cagr": d, "d_mdd": dm, "shake_ok": shake_ok, "size_cagr": big, "size_mdd_third": mdd_third,
                    "verdict": "✅ 통과" if (big or mdd_third) and shake_ok else ("🟡 근접" if shake_ok and d["oos"] > 0 and d["is"] > 0 else "❌")}
    print("JUDGE", out["judge"])
    out["note"] = "묶음 = 덜어낸 현금 자산 추세 칸 주차(k1026) + 킥 빈 칸 기본 칸처럼(k1019) · 킥 대용 ETF 돌파 · 레버리지 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
