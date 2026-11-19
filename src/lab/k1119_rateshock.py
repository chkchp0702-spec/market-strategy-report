"""📈 11/19 16시 — k1119_rateshock: 🔴 국면을 「금리 충격 🔴」과 「보통 🔴」으로 갈라 보통 🔴 에선 주식을 더 들기
  사실(11/18·11/19): 🎯 NEW 국면은 뒤 수익 ≈0 — 2022 보험(+6.4p) ↔ 회복 해 놓침(2019·2023·2025 ≈16p)
                     신용(HYG÷IEF)은 2022 금리 충격을 못 봄(k1119_credit) → 금리 자체를 표지로
  가설: 2022 형 = 「🔴 이면서 10년 금리 급등(또는 긴 국채 TLT 급락)」 · 나머지 🔴(2019·2023·2025 의 흔들림)는 되돌아옴
  처방 판: 🔴 & 충격 → 주식 50%(지금 그대로) · 🔴 & 충격 아님 → 주식 X(75% 또는 100%)
           충격 = ^TNX 63일 변화 > θ(0.5·0.75·1.0 %p) 또는 TLT 63일 수익 < −θ(5·8·10%) · 3일 이어짐
           +DD 판: 충격 or SPY 252일 고점 대비 −20% 아래(2008 형 깊은 하락도 막기)
  구현: run 의 🔴 무게(25/25)는 「🟢 무게 × 0.5」와 같음(나머지는 추세 칸) → 보통 🔴 날은 🟢 로 두고 변동성 배수 sc × X
  크기 산수: 회복 해 놓친 16p / 9.9년 = 상한 연 +1.6(X=100%) → 🟡 노림 · 앞 구간 2008(금리 내림)은 손해 볼 위험
  틀: k1106_exectime3.run 예약 종가판 c1 (k1119_credit 와 같은 자료·손잡이) · 앞 2008-07~2016 1등 → 뒤 2017~
→ market/lab/k1119_rateshock.json
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

OUT = Path("market/lab/k1119_rateshock.json")
A = math.sqrt(252) * 100


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


def main():
    C = load()
    px = ydl(["^IRX", "^TNX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    tnx = px.pop("^TNX")["close"].reindex(C.index).ffill()
    if float(tnx.dropna().median()) > 20:   # 옛 야후 표기(×10) 대비
        tnx = tnx / 10
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k, None)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False).astype(bool)
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

    def full(e):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e; D["QQQ"] = e
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rQ = C["QQQ"].pct_change().fillna(0.0)
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}
    res = {}

    # 충격 표지
    SH = {}
    def shock(src, th, dd=False, k=3):
        key = (src, th, dd, k)
        if key not in SH:
            if src == "TNX":
                raw = (tnx - tnx.shift(63)) > th
            else:
                raw = (C["TLT"] / C["TLT"].shift(63) - 1) < -th / 100
            if dd:
                raw = raw | (C["SPY"] / C["SPY"].rolling(252, min_periods=200).max() - 1 < -0.20)
            SH[key] = sticky(raw.reindex(C.index), k)
        return SH[key]

    def go(nm, base="conc", f=1.0, sh=1, cost=0.001, X=None, sk=None):
        t0, fl0, G, Rd = TG[base]
        sc = (t0 / (rQ.rolling(20).std() * A)).clip(upper=1.0, lower=fl0).fillna(1.0)
        rg = reg
        mild = pd.Series(False, index=C.index)
        if X is not None:
            mild = (~reg) & (~sk)               # 보통 🔴 → 🟢 무게 × X (base=port 면 G_PORT 기준)
            rg = reg | mild
            sc = sc.where(~mild, sc * X)
        sig, fs = flow(f, sh, 5)
        nav, td = run(C, Z, full(rQ), rg, idx, sc, sig, fs, G, Rd, "c1", cost)
        r = {k: seg(nav, spy, a, b, td) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()}
        yr = yearly(nav)
        r.update({"yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                  "worst_is": min(v for y, v in yr.items() if y < 2017)})
        rr = reg.reindex(idx); mm = mild.reindex(idx)
        r["mild_yr"] = {y: [round(float((~rr[rr.index.year == y]).mean()) * 100, 1), round(float(mm[mm.index.year == y].mean()) * 100, 1)]
                        for y in range(2008, idx[-1].year + 1)}
        res[nm] = r
        print(nm, "앞", r["is"]["cagr"], r["is"]["mdd"], "| 뒤", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"],
              "최악", r["worst_oos"], "| 22", yr.get(2022), "23", yr.get(2023), "25", yr.get(2025), flush=True)

    go("NEW"); go("P_NEW", "port")
    go("ALLMILD75", X=0.75, sk=pd.Series(False, index=C.index))     # 충격 없이 🔴 = 75% (참고)
    grid = []
    for src, ths in (("TNX", (0.5, 0.75, 1.0)), ("TLT", (5, 8, 10))):
        for th in ths:
            for dd in (False, True):
                for X in (0.75, 1.0):
                    nm = f"R_{src}{th}{'_DD' if dd else ''}_X{int(X*100)}"
                    go(nm, X=X, sk=shock(src, th, dd)); grid.append((nm, src, th, dd, X))
    best = max(grid, key=lambda g: res[g[0]]["is"]["cagr"])
    nm, src, th, dd, X = best
    print("앞 구간 1등", nm, flush=True)
    for th2 in (th * 0.8, th * 1.2):
        go(f"BEST_th{round(th2, 2)}", X=X, sk=shock(src, th2, dd))
    for X2 in (max(0.5, X - 0.2), min(1.0, X + 0.2)):
        if X2 != X:
            go(f"BEST_X{int(X2*100)}", X=X2, sk=shock(src, th, dd))
    go("BEST_k5", X=X, sk=shock(src, th, dd, 5))
    go("BEST_c25", cost=0.0025, X=X, sk=shock(src, th, dd)); go("NEW_c25", cost=0.0025)
    go("BEST_s0", sh=0, X=X, sk=shock(src, th, dd)); go("NEW_s0", sh=0)
    go("P_BEST", "port", X=X, sk=shock(src, th, dd))
    # 뒤 1등도 기록(고르기 운 확인용)
    bo = max(grid, key=lambda g: res[g[0]]["oos"]["cagr"])
    qqq = C["QQQ"].reindex(idx)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {k_: seg(spy, spy, a, b) for k_, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()},
           "qqq": {k_: seg(qqq, spy, a, b) for k_, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END)}.items()},
           "spy_yr": yearly(spy), "best": nm, "best_oos": bo[0], "res": res,
           "note": ("k1106_exectime3.run 예약 종가판 c1 · 비용 0.1% · 무접두 = 🎯 NEW(QQQ+흐름1.0 · 목표 22·0.70) · P_ = 💼 NEW · "
                    "R_<TNX θ%p|TLT θ%>[_DD]_X<주식%> = 🔴 & 충격 아님 날은 주식 X% · 충격 = 63일 10년 금리 +θ 또는 TLT −θ% (3일 이어짐) · "
                    "_DD = 충격 or SPY 고점 −20% · mild_yr = 해별 [🔴 날 %, 보통 🔴 로 푼 날 %] · ETF 만, 생존 편향 없음 · 레버리지 없음 · 매수 추천 아님")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
