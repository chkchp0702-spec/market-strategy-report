"""📈 10/19 11시 수익률 전략 검증 — 「킥 빈 칸 돈을 현금 대신 지수에 주차」
  틀은 k1014_volw 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 킥 대용 = 섹터·테마 ETF 52주 신고가 돌파
  지금: 킥 칸 안에서 신호가 없어 비어 있는 돈 = 현금(BIL)
  바꿈: 비어 있는 돈 = ① 💼 기본 칸과 똑같이(변동성 맞춤·국면 현금 포함) ② S&P½+나스닥½ 그대로
        신호가 오면 주차한 지수를 팔아 삼 → 사고팔 때 지수 쪽 비용 한 번 더(회전 × 0.1%)
  비어 있는 비율 = 주차 수익을 아주 작은 상수로 바꿔 돌린 차이로 잼
  2008-07~2016(앞) / 2017~(뒤) 둘 다 보고 · 킥 칸 크기 15%·23%로 흔들기
→ market/lab/k1019_park.json
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
from k1011_size import load, run_mix, seg, COST
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1014_volw import kick_vw

OUT = Path("market/lab/k1019_park2.json")


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre = prep(C)
    U, Pv, BRK, REL, R, bil = pre
    VOL = np.full_like(Pv, np.nan, dtype=float)
    pos_i = {d: i for i, d in enumerate(C.index)}
    n = len(C.index)
    core = np.zeros(n)
    for d, v in rb.items():
        core[pos_i[d]] = v
    eq = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).fillna(0.0).values
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    # 비어 있는 비율 재기
    eps = 1e-6
    k0 = kick_vw(C, idx, (U, Pv, BRK, REL, R, np.zeros(n)), VOL)
    k1 = kick_vw(C, idx, (U, Pv, BRK, REL, R, np.full(n, eps)), VOL)
    idle = (k1[0] - k0[0]) / eps
    idle_is = float(idle[idle.index <= IS_END].mean()); idle_oos = float(idle[idle.index >= OOS_START].mean())

    def run(park, extra_cost, size):
        kk = kick_vw(C, idx, (U, Pv, BRK, REL, R, park), VOL)
        rk = kk[0] - kk[1] * COST * extra_cost
        nav, td = run_mix(rb, tb, (rk, kk[1] * (1 + extra_cost), None), reg, size, size)
        knav = (1 + rk).cumprod()
        yr = {}
        for y in range(2009, idx[-1].year + 1):
            a = nav[nav.index.year == y]
            if len(a) > 20:
                yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, kk[1]), "kick_oos": seg(knav, spy, OOS_START, END, kk[1]),
                "tr_oos": tstat(kk[2], OOS_START, END), "yr": yr}

    regv = reg.reindex(C.index).fillna(False).shift(1).fillna(False).values.astype(bool)
    eq_reg = np.where(regv, eq, bil)
    core_reg = np.where(regv, core, bil)
    half = 0.5 * core + 0.5 * bil
    gld = C["GLD"].pct_change().fillna(0.0).values
    mixg = 0.8 * core + 0.2 * gld
    res = {}
    for size in (0.19, 0.15, 0.23):
        res[f"{size}"] = {"cash": run(bil, 0, size), "core": run(core, 1, size), "eq5050": run(eq, 1, size),
                          "eq_reg": run(eq_reg, 1, size), "core_reg": run(core_reg, 1, size), "half": run(half, 0.5, size), "core_gld": run(mixg, 1, size)}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "idle_pct": {"is": round(idle_is * 100, 1), "oos": round(idle_oos * 100, 1)},
           "spy": spy_row, "res": res,
           "note": "킥 빈 칸 돈 주차 — cash=지금(BIL) · core=💼 기본 칸과 똑같이 · eq5050=S&P½+나스닥½ · 주차분 사고팔 때 비용 한 번 더 · 킥 대용 = 섹터·테마 ETF 신고가 돌파(한계) · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("idle", out["idle_pct"])
    print("SPY", spy_row)
    for s, d in res.items():
        for k, v in d.items():
            print(s, k, "IS", v["is"], "| OOS", v["oos"], "| KICK_OOS", v["kick_oos"])
    print("yr cash ", res["0.19"]["cash"]["yr"])
    print("yr core ", res["0.19"]["core"]["yr"]); print("yr eqreg", res["0.19"]["eq_reg"]["yr"])


if __name__ == "__main__":
    main()
