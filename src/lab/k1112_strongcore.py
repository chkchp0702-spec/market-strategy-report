"""📈 11/12 12시 — k1112_strongcore: 「위험 키우기 허용」 첫 회차 — 🎯·💼 코어를 지수(S&P½·나스닥½) 대신 「강한 것 몰기」로
  사용자 11/11 16시: 레버리지·곱버스 금지 · 더 집중된 섹터·테마·모멘텀 · 주식 비중 키우기 허용 · 낙폭은 같이 보여 주기
  크기 산수: 🎯 코어 100% × (섹터·테마 상위 N 의 지수 대비 초과 ≈ 3~6%p, Moskowitz·Grinblatt 1999 산업 모멘텀) × 주식 평균 0.85 ≈ 2.5~5%p → 통과
  틀: k1106_exectime3.run (예약 종가판 = s1 흐름 · c1 다음 날 종가 체결) 그대로 · 국면(S&P 200일선)·월말 흐름·🧭 추세 칸·금 그대로
      바꾸는 것 = 코어 두 칸(SPY·QQQ 자리)에 담는 것 + 변동성 맞춤을 그 바구니의 20일 변동성으로(목표·한도 그대로) / 끈 판(sc=1)
  바구니 MOM = 무리 안 ETF 의 과거 수익(LB 일, 최근 21일 뺌) 상위 N 같은 비중 · 달 마지막 거래일 전날 종가로 고르고 마지막 날 종가 체결 · 달 안은 그냥 들고 있기
      무리 SECT = SPDR 9섹터(앞 구간부터 다 있음 · 고르기 편향 가장 적음)
      무리 WIDE = 9섹터 + 테마(SOXX·IGV·IBB·ITA·XHB·KRE·XME·XOP·IYT·TAN·SKYY·CIBR·XLRE·XLC·PAVE — 그날 LB+21일 자료 있는 것만) + QQQ
  판: 고르기 = 앞 2008-07~2016 연수익(낙폭이 SPY 앞 낙폭보다 얕은 것만) → 뒤 2017~ 시험 · 흔들기 LB ±20%·N ±1 · 비용 0.1%·0.25% · 해별 · 최악의 해
  레버리지 없음(주식 최대 100%) · ETF 만이라 생존 편향 없음, 단 테마 ETF 목록 자체는 지금 아는 것(WIDE 는 고르기 편향 있음 — SECT 와 나란히 봄)
→ market/lab/k1112_strongcore.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, THEME, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1112_strongcore.json")
A = math.sqrt(252) * 100
WIDE_T = ["SOXX", "IGV", "IBB", "ITA", "XHB", "KRE", "XME", "XOP", "IYT", "TAN", "SKYY", "CIBR", "XLRE", "XLC", "PAVE", "QQQ"]


def basket(C, univ, lb, n, cost):
    """달마다 상위 n 같은 비중 · 달 마지막 거래일 전날 종가로 고름 → 마지막 날 종가 체결 · 바구니 일별 수익(회전 비용 뺀 것)·회전·보유표"""
    U = [t for t in univ if t in C.columns]
    P = C[U]
    R = P.pct_change()
    mom = P.shift(21) / P.shift(21 + lb) - 1          # 최근 21일 뺀 LB 일 수익
    idx = C.index
    last = pd.Series(idx.month, index=idx)
    is_last = last != last.shift(-1)                  # 달 마지막 거래일
    w = {}
    rets, turns, hold = [], [], {}
    for i, d in enumerate(idx):
        r = 0.0
        if w:
            rr = {k: (0.0 if pd.isna(R.at[d, k]) else R.at[d, k]) for k in w}
            r = sum(w[k] * rr[k] for k in w)
            nw = {k: w[k] * (1 + rr[k]) for k in w}; s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        tv = 0.0
        if is_last.iloc[i] and i >= 1:
            m = mom.iloc[i - 1].dropna()                # 전날 종가까지
            if len(m) >= n:
                pick = list(m.sort_values(ascending=False).index[:n])
                t = {k: 1.0 / n for k in pick}
                keys = set(t) | set(w)
                tv = sum(abs(t.get(k, 0) - w.get(k, 0)) for k in keys) / 2 if w else 1.0
                w = t; hold[str(d.date())] = pick
                r -= tv * cost
        rets.append(r); turns.append(tv)
    return pd.Series(rets, index=idx).fillna(0.0), pd.Series(turns, index=idx), hold


def yearly(nav, y0=2009):
    o = {}
    for y in range(y0, nav.index[-1].year + 1):
        m = nav.index.year == y
        if m.sum() > 20:
            prev = nav[nav.index < nav[m].index[0]]
            b0 = prev.iloc[-1] if len(prev) else nav[m].iloc[0]
            o[y] = round(float(nav[m].iloc[-1] / b0 - 1) * 100, 1)
    return o


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {k: px.pop(k) for k in ["SPY", "QQQ", "GLD"]}
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill(); O["TLT"] = px["TLT"]
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    msig, mfs = make(C, DM, DQ)
    sig1, fs1 = msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0)

    # 기준 재현용: 진짜 밤·낮 몫
    ONr = pd.DataFrame(0.0, index=C.index, columns=KEYS); IDr = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ONr[k] = on; IDr[k] = (1 + cc) / (1 + on) - 1
    IDr["TRD"] = C["TRD"].pct_change().fillna(0.0)
    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END), "yr": yearly(spy)},
           "qqq": {"is": seg(C["QQQ"].reindex(idx), spy, START, IS_END), "oos": seg(C["QQQ"].reindex(idx), spy, OOS_START, END),
                   "yr": yearly(C["QQQ"].reindex(idx))}}
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}

    def go(nm, base, e1, e2, cost=0.001, volon=True, ON=None, ID=None, tgt=None):
        t_, fl, G, Rd = TG[base]
        t_ = tgt or t_
        rr = 0.5 * e1 + 0.5 * e2
        sc = (t_ / (rr.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0) if volon else pd.Series(1.0, index=C.index)
        ID_ = full(e1, e2) if ID is None else ID
        ON_ = Z if ON is None else ON
        nav, td = run(C, ON_, ID_, reg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        yr = yearly(nav)
        res[nm] = {"is": a, "oos": b, "yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                   "worst_is": min(v for y, v in yr.items() if y < 2017), "eq_up": round(float(sc.reindex(idx).mean()) * 100, 1)}
        print(nm, "앞", a["cagr"], a["mdd"], "| 뒤", b["cagr"], b["mdd"], b["sharpe"], "최악", res[nm]["worst_oos"], flush=True)
        return nav

    # 0) 기준 재현: 진짜 밤·낮 vs 통째 일수익(c1 이면 같아야)
    go("base_real", "conc", rS, rQ, ON=ONr, ID=IDr)
    go("base", "conc", rS, rQ)
    out["repro_diff"] = {p: round(res["base"][p]["cagr"] - res["base_real"][p]["cagr"], 3) for p in ("is", "oos")}
    go("port_base", "port", rS, rQ)
    go("base_novol", "conc", rS, rQ, volon=False)
    go("Q100", "conc", rQ, rQ)
    go("Q100_novol", "conc", rQ, rQ, volon=False)

    univs = {"SECT": list(SECT), "WIDE": list(SECT) + WIDE_T}
    holds = {}
    BK = {}
    for un, U in univs.items():
        for lb in (126, 252):
            for n in (2, 3, 4):
                br, bt, hd = basket(C, U, lb, n, 0.001)
                BK[(un, lb, n)] = br
                holds[f"{un}_{lb}_{n}"] = dict(list(hd.items())[-6:])
                go(f"{un}_L{lb}_N{n}", "conc", br, br)           # 코어 전부 바구니
                go(f"{un}_L{lb}_N{n}_halfQ", "conc", rQ, br)    # 나스닥 반 + 바구니 반
    out["holds_recent"] = holds

    # 고르기: 앞 구간 연수익 1등(앞 낙폭이 SPY 앞 낙폭보다 얕은 것) — 무리마다 · 꼴(전부/반반)마다
    spy_is_mdd = out["spy"]["is"]["mdd"]
    picks = {}
    for un in univs:
        for form in ("", "_halfQ"):
            c = [k for k in res if k.startswith(un + "_L") and k.endswith(form) and (form or not k.endswith("_halfQ"))
                 and res[k]["is"]["mdd"] > spy_is_mdd]
            if c:
                picks[f"{un}{form or '_full'}"] = max(c, key=lambda k: res[k]["is"]["cagr"])
    out["picks"] = picks
    print("PICKS", picks, flush=True)

    # 흔들기·비용·변동성 끔·💼 판 — 고른 판마다
    shake = {}
    for pk, nm in picks.items():
        un = nm.split("_")[0]; lb = int(nm.split("_L")[1].split("_")[0]); n = int(nm.split("_N")[1].split("_")[0]); half = nm.endswith("_halfQ")
        sh = {}
        for tag, (lb2, n2) in {"lb-20": (int(lb * .8), n), "lb+20": (int(lb * 1.2), n), "n-1": (lb, max(1, n - 1)), "n+1": (lb, n + 1)}.items():
            br, _, _ = basket(C, univs[un], lb2, n2, 0.001)
            go(f"{nm}__{tag}", "conc", rQ if half else br, br); sh[tag] = f"{nm}__{tag}"
        br25, _, _ = basket(C, univs[un], lb, n, 0.0025)
        go(f"{nm}__c25", "conc", rQ if half else br25, br25, cost=0.0025); sh["c25"] = f"{nm}__c25"
        br = BK[(un, lb, n)]
        go(f"{nm}__novol", "conc", rQ if half else br, br, volon=False); sh["novol"] = f"{nm}__novol"
        go(f"{nm}__port", "port", rQ if half else br, br); sh["port"] = f"{nm}__port"
        shake[pk] = sh
    go("base__c25", "conc", rS, rQ, cost=0.0025)
    go("port_base__c25", "port", rS, rQ, cost=0.0025)
    out["shake"] = shake
    out["res"] = res
    out["note"] = ("🎯 틀(목표 22·아래 0.70·국면 25/25·월말 흐름 s1·c1 예약 종가·🧭 추세 칸) 에서 코어 두 칸만 바꿈 · 변동성 맞춤은 바뀐 코어의 20일 변동성 · "
                   "바구니 = LB 일(최근 21일 뺌) 상위 N 같은 비중 달 1회 · 비용 0.1%(c25 = 0.25%, 바구니 회전에도) · 레버리지 없음 · ETF 라 생존 편향 없음, "
                   "WIDE 무리 목록은 지금 아는 것(고르기 편향) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
