"""📈 11/16 12시 — k1116_btcsleeve: 「지수·섹터·종목 밖의 센 자산」 — 비트코인(BTC) 칸을 🎯·💼 코어 안에
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

OUT = Path("market/lab/k1116_btcsleeve.json")
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

    def sleeve(w, L, cost, coreS=None, trend=True):
        """코어 = (1−w)·지수 + w·BTC(추세 켜짐일 때) · 꺼지면 그 몫도 지수 · 판단 = 이틀 전 종가 vs L일 평균"""
        cs = mix if coreS is None else coreS
        if trend:
            ma = C["BTC"].rolling(L, min_periods=L).mean()
            on = (C["BTC"] > ma).shift(2).fillna(False).astype(bool) & have
        else:
            on = have & have.shift(L).fillna(False).astype(bool)   # 고정 칸(자료 L일 쌓인 뒤부터)
        wt = on.astype(float) * w
        ch = wt.diff().abs().fillna(0.0)
        return (1 - wt) * cs + wt * rB - ch * cost, on

    go("base", "conc", mix)
    go("Q100", "conc", rQ)
    go("port_base", "port", mix)
    go("base__c25", "conc", mix, cost=0.0025)
    go("port_base__c25", "port", mix, cost=0.0025)

    onshare = {}
    for w in (0.05, 0.10, 0.15, 0.20):
        core, _ = sleeve(w, 200, 0.001, trend=False)
        go(f"FIX{int(w*100)}", "conc", core)
        for L in (100, 200, 300):
            core, on = sleeve(w, L, 0.001)
            onshare[L] = round(float(on.reindex(idx[idx >= pd.Timestamp(H1A)]).mean()) * 100, 1)
            go(f"TR{int(w*100)}_L{L}", "conc", core)
    out["btc_on_share_pct_since_2015-07"] = onshare

    # 고르기: BTC 시대 앞 반(2015-07~2020) 1등 · 조건: 표준 뒤 낙폭이 SPY 뒤 낙폭보다 얕음은 판정에서 보고만, 고르기는 h1 수익만
    spy_mdd = out["spy"]["oos"]["mdd"]
    picks = {}
    for f, pre in {"TR": "TR", "FIX": "FIX"}.items():
        c = [k for k in res if k.startswith(pre) and "__" not in k]
        picks[f] = max(c, key=lambda k: res[k]["h1"]["cagr"])
    # 위험 한도 안 1등도 따로(뒤 낙폭 ≥ SPY 뒤 낙폭)
    c = [k for k in res if k.startswith("TR") and "__" not in k and res[k]["h1"]["mdd"] > -25]
    if c:
        picks["TR_dd25"] = max(c, key=lambda k: res[k]["h1"]["cagr"])
    out["picks"] = picks
    print("PICKS", picks, flush=True)

    shake = {}
    done = {}
    for f, nm in picks.items():
        if nm in done:
            shake[f] = shake[done[nm]]; continue
        done[nm] = f
        sh = {}
        if nm.startswith("TR"):
            w = int(nm[2:].split("_")[0]) / 100; L = int(nm.split("_L")[1])
            for tag, (w2, L2) in {"w-20": (w * .8, L), "w+20": (w * 1.2, L), "L-20": (w, int(L * .8)), "L+20": (w, int(L * 1.2))}.items():
                core, _ = sleeve(w2, L2, 0.001); go(f"{nm}__{tag}", "conc", core); sh[tag] = f"{nm}__{tag}"
            core, _ = sleeve(w, L, 0.0025); go(f"{nm}__c25", "conc", core, cost=0.0025); sh["c25"] = f"{nm}__c25"
            core, _ = sleeve(w, L, 0.001); go(f"{nm}__port", "port", core); sh["port"] = f"{nm}__port"
            core, _ = sleeve(w, L, 0.0025); go(f"{nm}__port_c25", "port", core, cost=0.0025); sh["port_c25"] = f"{nm}__port_c25"
            core, _ = sleeve(w, L, 0.001, coreS=rQ); go(f"{nm}__onQ100", "conc", core); sh["onQ100"] = f"{nm}__onQ100"
        else:
            w = int(nm[3:]) / 100
            for tag, w2 in {"w-20": w * .8, "w+20": w * 1.2}.items():
                core, _ = sleeve(w2, 200, 0.001, trend=False); go(f"{nm}__{tag}", "conc", core); sh[tag] = f"{nm}__{tag}"
            core, _ = sleeve(w, 200, 0.001, trend=False); go(f"{nm}__port", "port", core); sh["port"] = f"{nm}__port"
        shake[f] = sh
    out["shake"] = shake
    out["res"] = res
    out["note"] = ("🎯 틀(목표 22·아래 0.70·국면·월말 흐름 c1 예약 종가·🧭 추세 칸)에서 코어 두 칸만 바꿈 · 변동성 맞춤은 바뀐 코어의 20일 변동성 · "
                   "FIX = BTC 고정 칸(자료 200일 쌓인 2015-07 무렵부터) · TR = 이틀 전 BTC 종가 > L일 평균일 때만 칸, 꺼지면 지수 · 켜고 끌 때 비용 · "
                   "2015 이전엔 BTC 칸 0(표준 앞 구간은 사실상 지금 규칙) · 레버리지 없음 · BTC 를 넣은 것 자체가 「이긴 걸 아는」 고르기 · 김치 프리미엄·환전·거래소 위험 미반영 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
