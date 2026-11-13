"""📈 11/13 16시 — k1113_pitsleeve: Q11/13-1(🎯 코어 QQQ ⅔ + 반도체 SOXX ⅓, 뒤 +5.36) 의 「고르기 편향」을 숫자로
  12시 검토: 반도체를 「이긴 걸 아는 지금」 고름 → 🟡. 이번 시험 세 가지
  ① 🗓 그 때 알 수 있던 규칙으로 센 칸 고르기 — 매 해 첫 거래일, 전날 종가까지 지난 LB(756·1008·1260·1512일) 수익 1등(또는 1·2등) 섹터·테마 ETF 를 ⅓ 칸에
       (반도체를 미리 지정하지 않음) · 무리 SECT(SPDR 9) / WIDE(9 + 테마 · 그날 LB+1 자료 있는 것만) · 칸 안은 달 1회 맞춤 + 비용
  ② 🧨 닷컴 뒤 구간(2001-07 SOXX 시작 ~ 2008-06) 「앞 구간 밖」 시험 — 단순 틀(S&P 200일선 아래면 코어 절반 · 목표 22 변동성 맞춤 · 다음 날 체결 · 나머지 현금 0)
       같은 단순 틀을 2008-07~ 에도 돌려 순위가 전체 틀과 같은지 맞춰 봄
  ③ 🔧 SX33 칸 안 맞춤 비용 — 매일 공짜 맞춤(12시) vs 달 1회 맞춤 + 비용 0.1%·0.25%
  크기 산수: ① ⅓ × (5년 1등 섹터의 다음 해 QQQ 대비 초과 ≈ 0~5) ≈ 0~1.7 + Q 전환 몫 2.4 → 근접~통과 경계
  틀: k1106_exectime3.run 예약 종가판(c1) · k1113_betaladder go() 와 같음 · 코어 두 칸 수익만 바꿈 · 레버리지 없음
→ market/lab/k1113_pitsleeve.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes, stats
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS
from k1112_strongcore import yearly

OUT = Path("market/lab/k1113_pitsleeve.json")
A = math.sqrt(252) * 100
THEMES = ["SOXX", "IGV", "IBB", "XBI", "ITA", "XHB", "KRE", "XME", "XOP", "OIH", "IYT", "IYR", "GDX", "FDN", "TAN",
          "SKYY", "CIBR", "XLRE", "XLC", "PAVE", "QQQ"]


def core_ret(R, tgt, freq, cost):
    """tgt: DataFrame(일별 목표 비중, 그날 종가에 맞춤 → 다음 날부터 적용) · freq 'D' 매일 · 'M' 달 마지막 날 + 목표 바뀐 날"""
    cols = list(tgt.columns)
    Rv = R[cols].fillna(0.0).values
    T = tgt.values
    idx = tgt.index
    mo = pd.Series(idx.month, index=idx)
    last = (mo != mo.shift(-1)).values
    w = np.zeros(len(cols)); out = np.zeros(len(idx)); turn = np.zeros(len(idx))
    for i in range(len(idx)):
        if w.sum() > 0:
            r = float(w @ Rv[i]); out[i] = r
            nw = w * (1 + Rv[i]); w = nw / nw.sum()
        t = T[i]
        if t.sum() <= 0:
            continue
        chg = (i == 0) or not np.allclose(t, T[i - 1])
        if freq == "D" or last[i] or chg or w.sum() == 0:
            tv = np.abs(t - w).sum() / 2 if w.sum() > 0 else 0.0
            out[i] -= tv * cost; turn[i] = tv; w = t.copy()
    return pd.Series(out, index=idx), pd.Series(turn, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k)
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
    msig, mfs = make(C, DM, DQ)
    sig1, fs1 = msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0)

    # 긴 자료(1999~) — 5년 수익 재기·닷컴 구간
    U = sorted(set(SECT + THEMES + ["SPY"]))
    LP = ydl(U, start="1998-01-01")
    L = pd.DataFrame({k: v["close"] for k, v in LP.items()}).sort_index()
    got = [k for k in U if k in L.columns]
    print("받음", len(got), "/", len(U), "빠짐", [k for k in U if k not in got], flush=True)
    for k in got:
        if k not in C.columns or C[k].isna().all():
            C[k] = L[k].reindex(C.index).ffill()
    R = C.pct_change()

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rS = R["SPY"].fillna(0.0); rQ = R["QQQ"].fillna(0.0)
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}

    def go(nm, base, core, cost=0.001, e1=None):
        t_, fl, G, Rd = TG[base]
        e1 = core if e1 is None else e1
        rr = 0.5 * e1 + 0.5 * core
        sc = (t_ / (rr.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0)
        nav, td = run(C, Z, full(e1, core), reg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        yr = yearly(nav)
        res[nm] = {"is": a, "oos": b, "yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017)}
        print(nm, "앞", a["cagr"], a["mdd"], "| 뒤", b["cagr"], b["mdd"], b["sharpe"], "최악", res[nm]["worst_oos"], flush=True)

    go("base", "conc", rQ, e1=rS)
    go("Q100", "conc", rQ)
    go("base__c25", "conc", rQ, cost=0.0025, e1=rS)
    rX = R["SOXX"].fillna(0.0)
    go("SX33_daily_free", "conc", (2 / 3) * rQ + (1 / 3) * rX)   # 12시 재현(23.36 나와야 함)

    # ③ SX33 달 1회 맞춤 + 비용
    tgx = pd.DataFrame({"QQQ": 2 / 3, "SOXX": 1 / 3}, index=C.index)
    for cst, tag in ((0.001, "c10"), (0.0025, "c25")):
        cr, tv = core_ret(R, tgx, "M", cst)
        go(f"SX33_M_{tag}", "conc", cr, cost=cst)
    res["_sx33_m_turn_pct_yr"] = round(float(core_ret(R, tgx, "M", 0.001)[1].reindex(idx).sum()) / ((idx[-1] - idx[0]).days / 365.25) * 100, 1)

    # ① 그 때 알 수 있던 1등 칸(해 첫 거래일 · 전날 종가까지 LB 수익)
    UNI = {"SECT": [t for t in SECT if t in L.columns], "WIDE": [t for t in SECT + THEMES if t in L.columns and t != "QQQ"]}
    yfirst = pd.Series(C.index.year, index=C.index); yfirst = (yfirst != yfirst.shift(1)).values
    holds = {}

    def pit_tgt(un, lb, n):
        cols = sorted(set(UNI[un] + ["QQQ"]))
        T = pd.DataFrame(0.0, index=C.index, columns=cols)
        cur = None; hd = {}
        for i, d in enumerate(C.index):
            if (yfirst[i] or cur is None) and i >= 1:
                prev = C.index[i - 1]
                Lp = L.loc[:prev, UNI[un]]
                if len(Lp) > lb:
                    m = (Lp.iloc[-1] / Lp.iloc[-1 - lb] - 1)
                    ok = Lp.iloc[-1 - lb].notna() & Lp.iloc[-1].notna()
                    m = m[ok].sort_values(ascending=False)
                    if len(m) >= n:
                        cur = list(m.index[:n]); hd[str(d.year)] = cur
            if cur is None:
                T.iloc[i, T.columns.get_loc("QQQ")] = 1.0
            else:
                T.iloc[i, T.columns.get_loc("QQQ")] = 2 / 3
                for k in cur:
                    T.iloc[i, T.columns.get_loc(k)] += (1 / 3) / n
        return T, hd

    cache = {}
    for un in UNI:
        for lb in (756, 1008, 1260, 1512):
            for n in (1, 2):
                nm = f"PIT_{un}_L{lb}_N{n}"
                T, hd = pit_tgt(un, lb, n); cache[nm] = T
                holds[nm] = {y: v for y, v in hd.items() if int(y) >= 2008}
                cr, _ = core_ret(R, T, "M", 0.001)
                go(nm, "conc", cr)
    spy_is_mdd = seg(spy, spy, START, IS_END)["mdd"]
    cand = [k for k in res if k.startswith("PIT_") and res[k]["is"]["mdd"] > spy_is_mdd]
    pick = max(cand, key=lambda k: res[k]["is"]["cagr"]) if cand else None
    print("PICK", pick, flush=True)
    shake = {}
    if pick:
        _, un, l, nn = pick.split("_"); lb = int(l[1:]); n = int(nn[1:])
        for tag, lb2 in {"lb-20": int(lb * .8), "lb+20": int(lb * 1.2)}.items():
            T, _ = pit_tgt(un, lb2, n); cr, _ = core_ret(R, T, "M", 0.001); go(f"{pick}__{tag}", "conc", cr); shake[tag] = f"{pick}__{tag}"
        cr, _ = core_ret(R, cache[pick], "M", 0.0025); go(f"{pick}__c25", "conc", cr, cost=0.0025); shake["c25"] = f"{pick}__c25"
        cr, _ = core_ret(R, cache[pick], "M", 0.001); go(f"{pick}__port", "port", cr); shake["port"] = f"{pick}__port"
        go("port_base", "port", rQ, e1=rS)

    # ② 단순 틀 — 닷컴 뒤(2001-07~2008-06) vs 2008-07~
    def simple(core, sp, a, b):
        core = core[(core.index >= pd.Timestamp(a) - pd.Timedelta(days=400)) & (core.index <= b)].fillna(0.0)
        s_ = sp.reindex(core.index).ffill()
        up = (s_ > s_.rolling(200).mean()).shift(1).fillna(True)
        sc = (22.0 / (core.rolling(20).std() * A)).clip(upper=1.0, lower=0.70).fillna(1.0).shift(1).fillna(1.0)
        e = sc * np.where(up, 1.0, 0.5)
        ch = pd.Series(e, index=core.index).diff().abs().fillna(0.0)
        r = e * core - ch * 0.001
        nav = (1 + r).cumprod(); nav = nav[nav.index >= a]
        st = stats(nav / nav.iloc[0]); st.pop("yr", None)
        return st, yearly(nav, nav.index[0].year)

    LR = L.pct_change()
    sp = L["SPY"]
    cores = {"base": 0.5 * LR["SPY"] + 0.5 * LR["QQQ"], "Q100": LR["QQQ"], "SX33": (2 / 3) * LR["QQQ"] + (1 / 3) * LR["SOXX"],
             "SPY_hold": None}
    dot = {}
    for per, (a, b) in {"dot_2001_2008": ("2001-07-16", "2008-06-30"), "is_2008_2016": ("2008-07-01", IS_END),
                        "oos_2017": (OOS_START, END)}.items():
        dot[per] = {}
        for k, cr in cores.items():
            if cr is None:
                n_ = sp[(sp.index >= a) & (sp.index <= b)]; st = stats(n_ / n_.iloc[0]); st.pop("yr", None)
                dot[per][k] = {"st": st, "yr": yearly(n_, n_.index[0].year)}
            else:
                st, yr = simple(cr, sp, a, b); dot[per][k] = {"st": st, "yr": yr}
            print(per, k, dot[per][k]["st"], flush=True)
        for k in ("QQQ", "SOXX"):
            n_ = L[k][(L.index >= a) & (L.index <= b)].dropna(); st = stats(n_ / n_.iloc[0]); st.pop("yr", None)
            dot[per][k + "_hold"] = {"st": st}
    # 닷컴 앞 시기에 5년 1등 규칙이 무엇을 골랐을지(참고)
    pre = {}
    for y in range(2002, 2009):
        d0 = L.index[L.index.year == y][0]; Lp = L.loc[:d0, UNI["WIDE"]].iloc[:-1]
        if len(Lp) > 1260:
            m = (Lp.iloc[-1] / Lp.iloc[-1 - 1260] - 1).dropna().sort_values(ascending=False)
            pre[str(y)] = [f"{k} {round(v*100)}%" for k, v in m.head(3).items()]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)},
           "pick": pick, "shake": shake, "holds": holds, "pre2008_top3_L1260": pre, "simple": dot, "res": res,
           "note": ("🎯 틀(예약 종가판 c1)에서 코어 두 칸만 바꿈 · PIT = 해 첫 거래일 전날 종가까지 LB 수익 1등(N 개) ETF 를 코어 ⅓(같은 비중) · QQQ ⅔ · 칸 안 달 1회 맞춤 + 비용 · "
                    "무리 목록(테마 ETF 이름)은 지금 아는 것 — SECT 는 편향 가장 적음 · 단순 틀은 금·추세 칸·월말 흐름 없음(현금 0%) — 순위 비교용 · 레버리지 없음 · 매수 추천 아님")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
