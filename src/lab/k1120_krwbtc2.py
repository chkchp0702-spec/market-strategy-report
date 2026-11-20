"""📈 11/20 16시 뒤(사용자 「네 생각대로 해」 → Q11/20-2 보류·다시 재기) — k1120_krwbtc2: 김프 과열 끄개 BTC 칸을 지금 실제 🎯 NEW(QQQ 코어 + 월말 흐름 1.0) 위에서
  k1120_krwbtc 는 옛 틀(S½Q½·흐름 기본)이라 기준이 달랐음 → NEW 기준 재현(뒤 2017~ 21.49 근처) 확인 후 같은 판
  더한 것(검토자 지적): 고정 칸 0.25% 짝 · 필터 순수 몫 해별 · 💼 NEW 판 · 과열 때 칸 절반(H) 판 · 손잡이는 BTC 시대 앞(2017-11~2020)에서 다시 고름
  나머지 설명은 k1120_krwbtc 와 같음(업비트 원화 BTC ÷ KRW=X · 이틀 전 김프 k일 평균 > θ · 달 첫 거래일 맞춤 · 레버리지 없음)
→ market/lab/k1120_krwbtc2.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS
from k1112_strongcore import yearly

OUT = Path("market/lab/k1120_krwbtc2.json")
A = math.sqrt(252) * 100
H1A, H1B, H2A = "2017-11-01", "2020-12-31", "2021-01-01"


def upbit():
    import urllib.request, time as _t
    rows, to = {}, None
    for _ in range(40):
        url = "https://api.upbit.com/v1/candles/days?market=KRW-BTC&count=200" + (f"&to={to}" if to else "")
        js = None
        for att in range(4):
            try:
                req = urllib.request.Request(url, headers={"accept": "application/json", "User-Agent": "Mozilla/5.0"})
                js = json.loads(urllib.request.urlopen(req, timeout=20).read())
                break
            except Exception as e:
                print("upbit retry", att, e, flush=True); _t.sleep(2 + 3 * att)
        if not js:
            break
        for r in js:
            rows[r["candle_date_time_utc"][:10]] = float(r["trade_price"])
        old = min(r["candle_date_time_utc"] for r in js)
        if len(js) < 200:
            break
        to = old + "Z"
        _t.sleep(0.25)
    s = pd.Series(rows).sort_index(); s.index = pd.to_datetime(s.index)
    return s


def main():
    up = upbit()
    print("upbit", len(up), up.index[0].date() if len(up) else None, up.index[-1].date() if len(up) else None, flush=True)
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD", "BTC-USD", "KRW=X"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k, None)
    btc_raw = px.pop("BTC-USD")["close"]
    fx_raw = px.pop("KRW=X")["close"]
    fx_raw = fx_raw[(fx_raw > 800) & (fx_raw < 2000)]          # 야후 KRW=X 튀는 값 거르기
    U = up.index.union(btc_raw.index).union(fx_raw.index)
    fxU = fx_raw.reindex(U).ffill(); btcU = btc_raw.reindex(U).ffill(); upU = up.reindex(U)
    prem = (upU / (btcUsd := btcU * fxU) - 1).dropna()
    prem = prem[(prem > -0.3) & (prem < 0.8)]
    upusd = (upU / fxU).dropna()
    def onC(s):
        return s.reindex(C.index.union(s.index)).ffill().reindex(C.index)
    C["UPB"] = onC(upusd); C["BTC"] = onC(btc_raw); C["FX"] = onC(fx_raw); C["PREM"] = onC(prem)
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
    msig, mfs = make(C, DM, DQ, f=1.0, K=5)
    sig1, fs1 = msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0)

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    have = C["UPB"].notna() & C["UPB"].shift(20).notna()
    pm = prem[prem.index >= "2017-10-01"]
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "upbit_first": str(up.index[0].date()), "upbit_n": int(len(up)),
           "prem": {"mean": round(float(pm.mean()) * 100, 2), "max": round(float(pm.max()) * 100, 1), "min": round(float(pm.min()) * 100, 1),
                    "max_date": str(pm.idxmax().date()),
                    "yr": {int(y): {"mean": round(float(v.mean()) * 100, 2), "max": round(float(v.max()) * 100, 1), "min": round(float(v.min()) * 100, 1),
                                    "days_gt5": int((v > 0.05).sum())} for y, v in pm.groupby(pm.index.year)}}}
    print("PREM", out["prem"], flush=True)
    # 김프 높을 때 다음 BTC 수익(달러, 63일) — 거품 표지인가
    bt = btc_raw; fwd = (bt.shift(-63) / bt - 1).reindex(pm.index)
    tab = {}
    for lo, hi in [(-1, 0), (0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 1)]:
        m = (pm > lo) & (pm <= hi)
        f = fwd[m].dropna()
        tab[f"{lo}~{hi}"] = {"days": int(m.sum()), "fwd63": round(float(f.mean()) * 100, 1) if len(f) else None,
                             "h1_days": int(m[(m.index <= H1B)].sum()), "h2_days": int(m[m.index >= H2A].sum())}
    out["prem_fwd63"] = tab; print("FWD", tab, flush=True)
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}
    fxI = C["FX"].reindex(idx).ffill().bfill()

    def go(nm, base, core, cost=0.001):
        t_, fl, G, Rd = TG[base]
        sc = (t_ / (core.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0)
        nav, td = run(C, Z, full(core, core), reg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        r = {k: seg(nav, spy, a, b, td) for k, (a, b) in
             {"is": (START, IS_END), "oos": (OOS_START, END), "h1": (H1A, H1B), "h2": (H2A, END)}.items()}
        nk = nav * fxI
        r["krw_h1"] = seg(nk, spy, H1A, H1B); r["krw_h2"] = seg(nk, spy, H2A, END)
        yr = yearly(nav)
        r.update({"yr": yr, "worst_h2": min(v for y, v in yr.items() if y >= 2021)})
        res[nm] = r
        print(nm, "앞", r["is"]["cagr"], "뒤17", r["oos"]["cagr"], r["oos"]["mdd"], "| h1", r["h1"]["cagr"], r["h1"]["mdd"], "| h2", r["h2"]["cagr"], r["h2"]["mdd"], r["h2"]["sharpe"],
              "| 원화 h2", r["krw_h2"]["cagr"], r["krw_h2"]["mdd"], "| 최악", r["worst_h2"], flush=True)
        return nav

    mix = rQ                                      # 🎯 NEW 코어 = QQQ
    month = pd.Series(C.index.to_period("M"), index=C.index)
    first = (month != month.shift(1)).values
    premS = C["PREM"].shift(2)                      # 이틀 전 김프(전날 판단 → 다음 날 체결)

    def W_fix(w, theta=None, k=1, hot_w=0.0):
        W = have.astype(float) * w
        if theta is not None:
            hot = (premS.rolling(k).mean() > theta).fillna(False)
            W = W.where(~hot, w * hot_w)
        return W

    def sleeve(W, cost, asset="UPB", coreS=None, monthly=True):
        rB = C[asset].pct_change().fillna(0.0).values
        cs = (mix if coreS is None else coreS).values; Wv = W.values
        o = np.zeros(len(cs)); wb = 0.0
        for i in range(len(cs)):
            c = 0.0
            if (not monthly) or first[i] or (wb == 0.0 and Wv[i] > 0) or (Wv[i] == 0.0 and wb > 0):
                c = abs(Wv[i] - wb) * cost; wb = Wv[i]
            g = (1 - wb) * cs[i] + wb * rB[i]
            o[i] = g - c
            if wb > 0:
                wb = wb * (1 + rB[i]) / (1 + g) if (1 + g) != 0 else wb
        return pd.Series(o, index=C.index)

    def offd(W):
        x = W.reindex(idx); h = have.reindex(idx)
        return {"h1": round(float(((x == 0) & h)[(x.index >= H1A) & (x.index <= H1B)].mean()) * 100, 1),
                "h2": round(float(((x == 0) & h)[x.index >= H2A].mean()) * 100, 1)}

    go("base", "conc", mix)                 # 🎯 NEW
    go("port_base", "port", mix)            # 💼 NEW
    go("base__c25", "conc", mix, cost=0.0025)
    go("port_base__c25", "port", mix, cost=0.0025)
    for w in (0.10, 0.20):
        go(f"U_FIX{int(w*100)}", "conc", sleeve(W_fix(w), 0.001))
    go("U_FIX20__c25", "conc", sleeve(W_fix(0.20), 0.0025), cost=0.0025)
    go("U_FIX20__port", "port", sleeve(W_fix(0.20), 0.001))
    go("U_FIX20__port_c25", "port", sleeve(W_fix(0.20), 0.0025), cost=0.0025)
    off = {}
    for th in (0.04, 0.06, 0.08, 0.10):
        for k in (1, 5):
            nm = f"U_P{int(th*100)}_k{k}"; W = W_fix(0.20, th, k)
            go(nm, "conc", sleeve(W, 0.001)); off[nm] = offd(W)
    for th in (0.06, 0.08):
        go(f"U_H{int(th*100)}_k5", "conc", sleeve(W_fix(0.20, th, 5, 0.5), 0.001))
    out["off_days_pct"] = off
    cand = [k for k in res if k.startswith("U_P")]
    pick = max(cand, key=lambda k: res[k]["h1"]["cagr"]); out["pick"] = pick; print("PICK", pick, flush=True)
    th = int(pick[3:].split("_")[0]) / 100; k = int(pick.split("_k")[1])
    sh = {}
    for tag, (t2, w2, k2) in {"th-20": (th*.8, .2, k), "th+20": (th*1.2, .2, k), "w16": (th, .16, k), "w24": (th, .24, k),
                              "k3": (th, .2, 3)}.items():
        go(f"{pick}__{tag}", "conc", sleeve(W_fix(w2, t2, k2), 0.001)); sh[tag] = f"{pick}__{tag}"
    W = W_fix(0.20, th, k)
    go(f"{pick}__c25", "conc", sleeve(W, 0.0025), cost=0.0025); sh["c25"] = f"{pick}__c25"
    go(f"{pick}__port", "port", sleeve(W, 0.001)); sh["port"] = f"{pick}__port"
    go(f"{pick}__port_c25", "port", sleeve(W, 0.0025), cost=0.0025); sh["port_c25"] = f"{pick}__port_c25"
    go("P8_k5_fixed", "conc", sleeve(W_fix(0.20, 0.08, 5), 0.001))   # 16시 고른 손잡이 그대로
    go("P8_k5_fixed__port", "port", sleeve(W_fix(0.20, 0.08, 5), 0.001))
    out["filter_yr"] = {y: round(res[pick]["yr"][y] - res["U_FIX20"]["yr"][y], 1) for y in res[pick]["yr"] if int(y) >= 2017}
    print("FILTER_YR", out["filter_yr"], flush=True)
    out["shake"] = sh; out["res"] = res
    out["note"] = ("🎯 NEW 틀(k1106_exectime3.run 예약 종가판 c1 · QQQ 코어 · 흐름 1.0)에서 코어만 바꿈 · U = 업비트 원화 BTC(÷KRW=X 달러 값) · Y = BTC-USD · "
                   "P{θ}_k{k} = 이틀 전 김프 k일 평균 > θ 면 BTC 칸 0 · 달 첫 거래일 맞춤 + 켜고 끌 때 맞춤 · krw_* = nav×원/달러 · "
                   "BTC 를 넣은 것 자체가 이긴 걸 아는 고르기 · 과세·거래소 위험 미반영 · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
