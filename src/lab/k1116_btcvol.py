"""📈 11/16 16시 — k1116_btcvol: 12시 Q11/16-1(BTC 고정 칸) 이어서 — 「같은 위험 예산 칸」(변동성 거꾸로 크기) + 달 1회 맞춤
  출발(k1116_btcsleeve): FIX20 BTC 시대 뒤 반(2021~) +2.93 · 그러나 2017·2018 처럼 BTC 변동성 클 때 칸이 커서 낙폭·운 몫이 큼
  가설: 칸 크기 = B ÷ BTC 변동성(이틀 전까지 LB일) → 변동성 큰 해(2017~18·2021~22)엔 작게, 잔잔한 해(2023~26)엔 크게
        → 같은 위험으로 더 많이(위험 예산 고르게) · 달 1회만 맞춤(첫 거래일) · 그 사이 칸은 값 따라 흘러감 · 비용 = 맞춘 몫 × cost
  크기 산수: 뒤 반 BTC 변동성 ≈57 · B 0.10 → 평균 칸 ≈18~20% · 잔잔한 2023~24(BTC +150%·+120%)에 칸 ≈25~30% → FIX20 +2.9 위로 +0.5~1.5 가능
(아래는 12시 원본 설명 그대로)
📈 11/16 12시 — k1116_btcsleeve: 「지수·섹터·종목 밖의 센 자산」 — 비트코인(BTC) 칸을 🎯·💼 코어 안에
  사용자 11/11 16시: 레버리지·곱버스 금지 · 위험 키우기 허용(뒤 낙폭이 SPY ≈ −34 보다 깊지 않으면 됨)
  출발(k1113_betaladder): 레버리지 없이 🎯 +3 은 코어에 「QQQ 보다 센 자산」이 들어가야만 닿음 ·
    지수·섹터·종목 규칙 갈래는 모두 닫힘(k1112_strongcore·k1112_megamom·k1113_pitsleeve) → 주식 밖의 센 자산은 미확인
  크기 산수: 칸 w=10% × (BTC − 코어 뒤 초과 ≈ +30~40%p/연) ≈ +3~4 → 통과 후보 · 단 BTC 낙폭 −75~−83(2018·2022)
    → 「200일선 위에서만 들기」(시계열 추세 · crypto TSMOM)로 낙폭을 줄인 판이 본판
  틀: k1106_exectime3.run (예약 종가판 · c1) · k1113_betaladder 와 같은 go() — 코어 두 칸(SPY·QQQ 자리)의 일수익만 바꿈
      BTC-USD 종가는 미국 거래일 종가에 맞춤(ffill) · 추세 판단은 이틀 전 종가(전날 판단 → 다음 날 체결 몫) · 칸 켜고 끌 때 비용 w×cost
  나눔: 표준(앞 2008-07~2016 / 뒤 2017~) + BTC 시대 반반(앞 2015-07~2020 / 뒤 2021~) · 손잡이는 BTC 시대 앞 반에서 고름
  ⚠️ BTC 를 무리에 넣은 것 자체가 「이긴 걸 아는」 고르기(생존 편향 같은 것) — 앞 반(2015~20)도 BTC 가 이긴 구간이라 이 편향은 못 지움
→ market/lab/k1116_btcsleeve.json
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

OUT = Path("market/lab/k1116_btcvol.json")
A = math.sqrt(252) * 100
H1A, H1B, H2A = "2015-07-01", "2020-12-31", "2021-01-01"


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD", "BTC-USD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k, None)
    btc_raw = px.pop("BTC-USD")["close"]
    C["BTC"] = btc_raw.reindex(C.index.union(btc_raw.index)).ffill().reindex(C.index)
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

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    rB = C["BTC"].pct_change().fillna(0.0)
    have = C["BTC"].notna()
    btc = C["BTC"].reindex(idx).dropna()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "btc_first": str(btc_raw.index[0].date()),
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END),
                   "h1": seg(spy, spy, H1A, H1B), "h2": seg(spy, spy, H2A, END), "yr": yearly(spy)},
           "qqq": {"is": seg(C["QQQ"].reindex(idx), spy, START, IS_END), "oos": seg(C["QQQ"].reindex(idx), spy, OOS_START, END),
                   "h1": seg(C["QQQ"].reindex(idx), spy, H1A, H1B), "h2": seg(C["QQQ"].reindex(idx), spy, H2A, END)},
           "btc": {"h1": seg(btc, spy.reindex(btc.index), H1A, H1B), "h2": seg(btc, spy.reindex(btc.index), H2A, END),
                   "oos": seg(btc, spy.reindex(btc.index), OOS_START, END), "yr": yearly(btc, 2015)}}
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}

    def go(nm, base, core, cost=0.001, volon=True):
        t_, fl, G, Rd = TG[base]
        sc = (t_ / (core.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0) if volon else pd.Series(1.0, index=C.index)
        nav, td = run(C, Z, full(core, core), reg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        r = {k: seg(nav, spy, a, b, td) for k, (a, b) in
             {"is": (START, IS_END), "oos": (OOS_START, END), "h1": (H1A, H1B), "h2": (H2A, END)}.items()}
        yr = yearly(nav)
        r.update({"yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                  "worst_is": min(v for y, v in yr.items() if y < 2017),
                  "eq_up": round(float(sc.reindex(idx).mean()) * 100, 1)})
        res[nm] = r
        print(nm, "앞", r["is"]["cagr"], r["is"]["mdd"], "| 뒤", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"],
              "| h1", r["h1"]["cagr"], "h2", r["h2"]["cagr"], r["h2"]["mdd"], "최악", r["worst_oos"], flush=True)
        return nav

    mix = 0.5 * rS + 0.5 * rQ
    rBv = rB.values; month = pd.Series(C.index.to_period("M"), index=C.index)
    first = (month != month.shift(1)).values

    def W_fix(w):
        return (have & have.shift(200).fillna(False).astype(bool)).astype(float) * w

    def W_iv(B, LB, wmax=0.30):
        sd = rB.where(have).rolling(LB, min_periods=LB).std() * math.sqrt(252)
        w = (B / sd).clip(upper=wmax).shift(2)
        return w.where(have.shift(200).fillna(False).astype(bool) & have, 0.0).fillna(0.0)

    def sleeve(W, cost, coreS=None, monthly=True):
        cs = (mix if coreS is None else coreS).values; Wv = W.values
        out_ = np.zeros(len(cs)); wb = 0.0
        for i in range(len(cs)):
            c = 0.0
            if (not monthly) or first[i] or (wb == 0.0 and Wv[i] > 0) or (Wv[i] == 0.0 and wb > 0):
                c = abs(Wv[i] - wb) * cost; wb = Wv[i]
            g = (1 - wb) * cs[i] + wb * rBv[i]
            out_[i] = g - c
            if wb > 0:
                wb = wb * (1 + rBv[i]) / (1 + g) if (1 + g) != 0 else wb
        return pd.Series(out_, index=C.index)

    def avgw(W):
        x = W.reindex(idx)
        return {"h1": round(float(x[(x.index >= H1A) & (x.index <= H1B)].mean()) * 100, 1),
                "h2": round(float(x[x.index >= H2A].mean()) * 100, 1),
                "yr": {int(y): round(float(v) * 100, 1) for y, v in x[x.index >= H1A].groupby(x[x.index >= H1A].index.year).mean().items()}}

    go("base", "conc", mix)
    go("port_base", "port", mix)
    go("base__c25", "conc", mix, cost=0.0025)
    go("port_base__c25", "port", mix, cost=0.0025)
    go("FIX20d", "conc", sleeve(W_fix(0.20), 0.001, monthly=False))   # 12시 FIX20 재현(매일 맞춤)
    wts = {}
    for w in (0.10, 0.15, 0.20):
        go(f"FIX{int(w*100)}m", "conc", sleeve(W_fix(w), 0.001)); wts[f"FIX{int(w*100)}m"] = avgw(W_fix(w))
    for B in (0.06, 0.08, 0.10, 0.12):
        for LB in (60, 120):
            W = W_iv(B, LB); nm = f"IV{int(B*100)}_{LB}"
            go(nm, "conc", sleeve(W, 0.001)); wts[nm] = avgw(W)
    out["avg_w"] = wts
    cand = [k for k in res if k.startswith("IV") and "__" not in k]
    pick = max(cand, key=lambda k: res[k]["h1"]["cagr"])
    # 같은 평균 칸 FIX 짝(공정 비교): h2 평균 칸에 가장 가까운 FIX
    out["pick"] = pick
    print("PICK", pick, flush=True)
    B = int(pick[2:].split("_")[0]) / 100; LB = int(pick.split("_")[1])
    sh = {}
    for tag, (b2, l2, wm) in {"B-20": (B*.8, LB, .3), "B+20": (B*1.2, LB, .3), "LB-20": (B, int(LB*.8), .3),
                              "LB+20": (B, int(LB*1.2), .3), "cap24": (B, LB, .24), "cap36": (B, LB, .36)}.items():
        W = W_iv(b2, l2, wm); go(f"{pick}__{tag}", "conc", sleeve(W, 0.001)); sh[tag] = f"{pick}__{tag}"; wts[f"{pick}__{tag}"] = avgw(W)
    W = W_iv(B, LB)
    go(f"{pick}__c25", "conc", sleeve(W, 0.0025), cost=0.0025); sh["c25"] = f"{pick}__c25"
    go(f"{pick}__daily", "conc", sleeve(W, 0.001, monthly=False)); sh["daily"] = f"{pick}__daily"
    go(f"{pick}__port", "port", sleeve(W, 0.001)); sh["port"] = f"{pick}__port"
    go(f"{pick}__port_c25", "port", sleeve(W, 0.0025), cost=0.0025); sh["port_c25"] = f"{pick}__port_c25"
    go(f"{pick}__onQ100", "conc", sleeve(W, 0.001, coreS=rQ)); sh["onQ100"] = f"{pick}__onQ100"
    go("FIX20m__c25", "conc", sleeve(W_fix(0.20), 0.0025), cost=0.0025)
    out["shake"] = sh
    out["res"] = res
    out["note"] = ("🎯 틀(k1106_exectime3.run 예약 종가판 c1 · 목표 22·아래 0.70·국면·월말 흐름·🧭 추세 칸)에서 코어 두 칸만 바꿈 · "
                   "IV = 칸 B÷BTC 변동성(이틀 전까지 LB일·위 한도 30%) · m = 달 첫 거래일에만 맞춤(그 사이 값 따라 흘러감) · 비용 = 맞춘 몫 × cost · "
                   "BTC 자료 200일 쌓인 2015-07 무렵부터 · BTC 를 넣은 것 자체가 「이긴 걸 아는」 고르기 · 김치 프리미엄·환전·거래소·과세 미반영 · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
