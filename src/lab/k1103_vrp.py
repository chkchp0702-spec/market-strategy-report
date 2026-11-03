"""📈 11/3 10시 — 「보험료가 비쌀 때(VIX ≫ 실제 변동) 🎯 집중은 덜 덜어낸다」 변동성 위험 프리미엄(VRP)
  바깥 재료: 변동성 위험 프리미엄이 앞으로의 주식 수익을 예측한다(Bollerslev·Tauchen·Zhou 2009, RFS) ·
  arXiv 2606.09025 「V자 급락 브레이크·느린 꼬리 보상」(200일선형 걸름이 V자 바닥 뒤 늦게 돌아오는 구멍) ·
  0DTE·옵션 딜러 흐름 글(SpotGamma·FlashAlpha) — 「헤지하는 사람이 억지로 풋을 비싸게 사는 때」 = 위험을 떠안는 쪽이 보상받는 때.
  우리 🎯 는 실제 변동(20일)만 보고 덜어냄 → VIX 가 실제보다 훨씬 높으면(공포 보험료 큼) 덜어내지 않거나,
  200일선 아래(🔴)라도 보험료가 크게 벌어지면(바닥 뒤 V자) 상승장 비중으로 일찍 돌아오는지 시험.
  기준 = 지금 🎯 규칙(목표 22%·아래 한도 70%·덜어낸 몫 🧭 추세 칸·월말 흐름 C1) · 하루 늦은 체결 · 비용 0.1% · 레버리지 없음
  ETF·지수만 → 생존 편향 없음 · 매수 추천 아님
→ market/lab/k1103_vrp.json
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
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC

OUT = Path("market/lab/k1103_vrp.json")


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "^VIX"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    vix = px.pop("^VIX")["close"].reindex(C.index).ffill()
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    rvs = C["SPY"].pct_change().rolling(20).std() * math.sqrt(252) * 100
    vrp = (vix - rvs)                          # VIX − S&P 20일 실제 변동 (%p)
    vrp_sm = vrp.rolling(5).mean()             # 하루 튐 줄이기
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    sigM, fsM = make(C, DM, DQ)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}

    # VRP 분포·단순 예측력(앞/뒤): 다음 20일 SPY 수익 vs VRP 오분위
    f20 = C["SPY"].pct_change(20).shift(-20) * 100
    dist = {}
    for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
        m = (vrp_sm.index >= a) & (vrp_sm.index <= b)
        v = vrp_sm[m].dropna(); f = f20.reindex(v.index)
        q = pd.qcut(v, 5, labels=False, duplicates="drop")
        dist[p] = {"q_edges": [round(float(x), 2) for x in v.quantile([.2, .4, .6, .8])],
                   "fwd20_by_q": {int(k): round(float(f[q == k].mean()), 2) for k in sorted(q.unique())}}
    out["dist"] = dist
    print("DIST", dist, flush=True)

    def go(mode="base", th=4.0, tgt=22.0, floor=0.70, lb=5, regth=None):
        vv = vrp if lb <= 1 else vrp.rolling(lb).mean()
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        rg = reg.copy()
        if mode in ("skip", "both"):        # 보험료 크면 덜어내지 않음
            sc = sc.where(~(vv > th), 1.0)
        if mode in ("cut", ):               # 보험료가 마이너스(실제 > VIX, 패닉)일 때만 덜어냄 — 나머지는 100%
            sc = sc.where(vv < -th, 1.0)
        if mode in ("reent", "both"):       # 🔴 이라도 보험료 크게 벌어지면 상승장 비중
            t2 = th if regth is None else regth
            rg = rg | (vv > t2)
        nav, td = core_run(C, rg, idx, sc, sigM, fsM, G_CONC, RD_CONC)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        yr = {}
        for y in range(2008, 2027):
            n = nav[nav.index.year == y]
            if len(n) > 5:
                prev = nav[nav.index < n.index[0]]
                b0 = prev.iloc[-1] if len(prev) else n.iloc[0]
                yr[y] = round(float(n.iloc[-1] / b0 - 1) * 100, 2)
        o["yr"] = yr
        on_days = None
        if mode != "base":
            on_days = round(float(((vv > th) if mode != "cut" else (vv < -th)).reindex(idx).mean()) * 100, 1)
        o["on_pct"] = on_days
        return o

    def dlt(a, b):
        d = {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}
        d["yr"] = {y: round(b["yr"][y] - a["yr"][y], 2) for y in b["yr"]}
        return d

    B = go("base")
    out["base"] = B
    print("BASE", B["is"], B["oos"], flush=True)
    grid = {}
    for mode in ("skip", "reent", "both", "cut"):
        ths = (0.0, 2.0, 4.0, 6.0, 8.0) if mode != "cut" else (0.0, 2.0, 4.0)
        for th in ths:
            k = f"{mode}_th{th:g}"
            r = go(mode, th=th)
            grid[k] = {"is": r["is"], "oos": r["oos"], "d": dlt(B, r), "on_pct": r["on_pct"]}
            print(k, "IS", grid[k]["d"]["is"], "OOS", grid[k]["d"]["oos"], "on", r["on_pct"], flush=True)
    out["grid"] = grid
    # 앞(IS)에서만 고르기: 샤프 + 연수익/10
    pick = max(grid, key=lambda k: grid[k]["d"]["is"]["sharpe"] + grid[k]["d"]["is"]["cagr"] / 10)
    out["is_pick"] = pick
    mode, th = pick.split("_th")[0], float(pick.split("_th")[1])
    print("PICK", pick, grid[pick]["d"], flush=True)
    out["pick_detail"] = go(mode, th=th)
    out["pick_vs_base_yr"] = dlt(B, out["pick_detail"])["yr"]
    # ±20% 흔들기 (문턱·평활 기간·목표 변동성) — 기준도 같은 목표로
    sh = {}
    variants = {"th-20": dict(th=th * 0.8 if th else -0.5), "th+20": dict(th=th * 1.2 if th else 0.5),
                "lb4": dict(lb=4), "lb6": dict(lb=6), "lb1": dict(lb=1), "lb10": dict(lb=10),
                "tgt18": dict(tgt=18.0), "tgt26": dict(tgt=26.0), "floor56": dict(floor=0.56), "floor84": dict(floor=0.84)}
    for nm, kw in variants.items():
        base_kw = {k: v for k, v in kw.items() if k in ("tgt", "floor")}
        kk = {"th": th, **kw}
        b0 = go("base", **base_kw); r = go(mode, **kk)
        sh[nm] = dlt(b0, r)
        print("SHAKE", nm, sh[nm]["is"], sh[nm]["oos"], flush=True)
    out["shake"] = sh
    out["note"] = ("기준 = 🎯 지금 규칙(200일선 판정 A · 목표 22% · 아래 한도 70% · 덜어낸 몫 🧭 추세 칸 · 월말 흐름) · "
                   "VRP = VIX − S&P 20일 실제 변동(연율 %p), 5일 평균 · 신호는 그날 종가 → 다음 날부터 · 비용 0.1% · 레버리지 없음 · "
                   "ETF·지수만(생존 편향 없음) · skip=보험료>문턱이면 안 덜어냄 · reent=🔴 이라도 보험료>문턱이면 상승장 비중 · "
                   "both=둘 다 · cut=보험료<−문턱일 때만 덜어냄 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
