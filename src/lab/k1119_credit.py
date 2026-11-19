"""📈 11/19 12시 — k1119_credit: 🔴 국면에 「신용(하이일드 회사채) 확인」을 붙여 2022 형과 되돌아오는 급락을 가르기
  사실(11/18): 🎯 NEW 의 국면은 뒤 구간 수익 ≈0 — 2022 보험(+6.4p) ↔ 회복 해 놓침(2019 −3.6·2023 −6.9·2025 −5.8 ≈16p)
  가설: 주가만 200일선 아래고 신용(HYG÷IEF)이 멀쩡하면 대개 되돌아옴 → 🔴 을 미룸 · 신용이 먼저 회복하면 일찍 복귀
  크기 산수: 회복 해 놓친 16p / 9.9년 ≈ 연 +1.6 이 위(상한) → ✅(+3) 는 산수로 못 닿음 · 🟡 노림
  판: OR(🟢 = 지금 🟢 or 신용 좋음) · AND(🟢 = 지금 🟢 and 신용 좋음, 더 방어) · ONLY(신용만) × N 50/100/200 × k 3/5
  신용 좋음 = HYG÷IEF 가 N일 평균 위 k일 이어짐(어제 종가까지 · 다음 날 체결은 run 이 처리)
  고르기: 앞 2008-07~2016 1등 → 뒤 2017~ 시험 · 흔들기 N ±20%·k ±1 · 0.25% · 하루 늦음 · 💼 판
  틀: k1106_exectime3.run 예약 종가판 c1 (k1118_fastback 과 같은 자료·손잡이)
→ market/lab/k1119_credit.json
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
from k1028_qflow import drifts, make, edge, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS
from k1112_strongcore import yearly

OUT = Path("market/lab/k1119_credit.json")
A = math.sqrt(252) * 100


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k, None)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    hy = ydl(["HYG"], start="2006-01-01")["HYG"]["close"]
    C["CR"] = (hy.reindex(C.index).ffill() / C["IEF"])
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

    def go(nm, core, base="conc", f=0.6, sh=1, K=5, cost=0.001, tgt=None, fl=None, novol=False, noreg=False, trd_cash=False, rg=None):
        t0, fl0, G, Rd = TG[base]
        t0 = tgt or t0; fl0 = fl if fl is not None else fl0
        if novol:
            sc = pd.Series(1.0, index=C.index)
        else:
            sc = (t0 / (core.rolling(20).std() * A)).clip(upper=1.0, lower=fl0).fillna(1.0)
        sig, fs = flow(f, sh, K) if f > 0 else (pd.Series(0.0, index=C.index), pd.Series(0.0, index=C.index))
        nav, td = run(C, Z, full(core, trd_cash), allon if noreg else (reg if rg is None else rg), idx, sc, sig, fs, G, Rd, "c1", cost)
        r = {k: seg(nav, spy, a, b, td) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()}
        yr = yearly(nav)
        r.update({"yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                  "worst_is": min(v for y, v in yr.items() if y < 2017)})
        if rg is not None:
            rr = rg.reindex(idx).astype(bool)
            r["red_yr"] = {y: round(float((~rr[rr.index.year == y]).mean()) * 100, 1) for y in range(2009, idx[-1].year + 1)}
        res[nm] = r
        print(nm, "앞", r["is"]["cagr"], r["is"]["mdd"], "| 뒤", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"],
              "최악", r["worst_oos"], "| 25", yr.get(2025), "26", yr.get(2026), flush=True)


    def sticky(s, k=3):
        s = s.fillna(False).astype(bool)
        out, cur, run_ = [], False, 0
        for v in s.values:
            if v != cur:
                run_ += 1
                if run_ >= k:
                    cur, run_ = v, 0
            else:
                run_ = 0
            out.append(cur)
        return pd.Series(out, index=s.index)

    RG = {}
    def credit(mode, N, k):
        key = (mode, N, k)
        if key not in RG:
            p = C["CR"]; m = p.rolling(N).mean()
            ok = sticky((p > m) & m.notna(), k)
            r0 = reg.astype(bool)
            RG[key] = {"OR": r0 | ok, "AND": r0 & ok, "ONLY": ok}[mode].reindex(C.index).fillna(False)
        return RG[key]

    # 기준 재현
    go("NEW", rQ, f=1.0); go("P_NEW", rQ, "port", f=1.0); go("NEW_noreg", rQ, f=1.0, noreg=True)
    grid = []
    for mode in ("OR", "AND", "ONLY"):
        for N in (50, 100, 200):
            for k in (3, 5):
                nm = f"C_{mode}{N}_k{k}"
                go(nm, rQ, f=1.0, rg=credit(mode, N, k)); grid.append((nm, mode, N, k))
    best = max(grid, key=lambda g: res[g[0]]["is"]["cagr"])
    nm, mode, N, k = best
    print("앞 구간 1등", nm, flush=True)
    for N2 in (round(N * 0.8), round(N * 1.2)):
        go(f"BEST_N{N2}", rQ, f=1.0, rg=credit(mode, N2, k))
    for k2 in (max(1, k - 1), k + 1):
        go(f"BEST_k{k2}", rQ, f=1.0, rg=credit(mode, N, k2))
    go("BEST_c25", rQ, f=1.0, cost=0.0025, rg=credit(mode, N, k)); go("NEW_c25", rQ, f=1.0, cost=0.0025)
    go("BEST_s0", rQ, f=1.0, sh=0, rg=credit(mode, N, k)); go("NEW_s0", rQ, f=1.0, sh=0)
    go("P_BEST", rQ, "port", f=1.0, rg=credit(mode, N, k))
    go("P_BEST_c25", rQ, "port", f=1.0, cost=0.0025, rg=credit(mode, N, k)); go("P_NEW_c25", rQ, "port", f=1.0, cost=0.0025)
    # 앞 구간 OR·AND 각 1등도 따로 (모드별 성격)
    for md in ("OR", "AND", "ONLY"):
        g2 = max([g for g in grid if g[1] == md], key=lambda g: res[g[0]]["is"]["cagr"])
        res.setdefault("_mode_best", {})[md] = g2[0]
    # 🔴 날 비율(해별) — 지금 판정 vs 1등
    rr0 = reg.reindex(idx).astype(bool); rr1 = credit(mode, N, k).reindex(idx).astype(bool)
    res["_red_yr"] = {y: [round(float((~rr0[rr0.index.year == y]).mean()) * 100, 1), round(float((~rr1[rr1.index.year == y]).mean()) * 100, 1)]
                      for y in range(2008, idx[-1].year + 1)}
    fe = {}
    qqq = C["QQQ"].reindex(idx)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {k_: seg(spy, spy, a, b) for k_, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()},
           "qqq": {k_: seg(qqq, spy, a, b) for k_, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()},
           "spy_yr": yearly(spy), "best": nm, "res": res, "flow_edge": fe,
           "note": ("k1106_exectime3.run 예약 종가판 c1 · 비용 0.1% · 무접두 = 🎯 NEW(QQQ+흐름1.0 · 목표 22·0.70) · P_ = 💼 NEW · "
                    "C_<OR|AND|ONLY><N>_k<k> = 지금 🟢 판정과 신용 좋음(HYG÷IEF > N일 평균 k일 이어짐)을 or/and/신용만 · 앞 구간 1등만 흔들기 · "
                    "_red_yr = 해별 🔴 날 % [지금, 1등] · ETF 만, 생존 편향 없음 · 레버리지 없음 · 매수 추천 아님")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
