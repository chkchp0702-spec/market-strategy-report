"""📈 11/17 16시 — k1117_attack2: 12시 Q11/17-1(⚔️ 🎯 QQQ 코어 + 월말 흐름 몫 1.0, 사용자 ✅ 11/18 적용) 의 빈 곳 + 그 위에 또 얹기
  ① 빈 곳: 지금 실제(하루 늦은 알림 s0) 판 · 날짜 창 ±1일(신호 s0·s2 · 창 K 4·6) · 비용 0.25% · 💼 판
  ② 새 기준(QQQ+흐름1.0) 위에 「주식 밖 센 자산」 BTC 고정 칸(Q11/16-1) 이 또 더해지나 — BTC 시대 반반(앞 2015-07~20 고르기 / 뒤 2021~ 시험)
  ③ 같은 새 기준 위에 반도체 SOXX ⅓ 칸(Q11/13-1 🟡) 이 또 더해지나 — 표준 앞/뒤
  크기 산수: BTC FIX20 지금 🎯 위 뒤 반 +2.82(k1116_btcvol) · SOXX⅓ 지금 🎯 위 뒤 +5.36 중 규칙 근거 없는 몫 ≈1.9(k1113_pitsleeve) →
             새 기준 위 뺏어 먹기 반이면 BTC ≈+1.4~2.8 · SOXX ≈+1~2 → 실험
  틀: k1106_exectime3.run (예약 종가판 · c1) · k1117_attack 의 go() + k1116_btcvol 의 sleeve(달 1회 맞춤)
→ market/lab/k1117_attack2.json
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

OUT = Path("market/lab/k1117_attack2.json")
A = math.sqrt(252) * 100
H1A, H1B, H2A = "2015-07-01", "2020-12-31", "2021-01-01"


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD", "BTC-USD", "SOXX"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k, None)
    btc_raw = px.pop("BTC-USD")["close"]
    C["BTC"] = btc_raw.reindex(C.index.union(btc_raw.index)).ffill().reindex(C.index)
    C["SOXX"] = px.pop("SOXX")["close"].reindex(C.index).ffill()
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
    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    rB = C["BTC"].pct_change().fillna(0.0); rX = C["SOXX"].pct_change().fillna(0.0)
    have = C["BTC"].notna()
    mix = 0.5 * rS + 0.5 * rQ
    month = pd.Series(C.index.to_period("M"), index=C.index)
    first = (month != month.shift(1)).values

    def sleeve(core, other, W, cost, monthly=True):
        cs = core.values; ov = other.values; Wv = W.values
        o = np.zeros(len(cs)); wb = 0.0
        for i in range(len(cs)):
            c = 0.0
            if (not monthly) or first[i] or (wb == 0.0 and Wv[i] > 0) or (Wv[i] == 0.0 and wb > 0):
                c = abs(Wv[i] - wb) * cost; wb = Wv[i]
            g = (1 - wb) * cs[i] + wb * ov[i]
            o[i] = g - c
            if wb > 0 and (1 + g) != 0:
                wb = wb * (1 + ov[i]) / (1 + g)
        return pd.Series(o, index=C.index)

    def W_btc(w):
        return (have & have.shift(200).fillna(False).astype(bool)).astype(float) * w

    def W_const(w):
        return pd.Series(w, index=C.index)

    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}
    res = {}

    def go(nm, core, base="conc", f=0.6, sh=1, K=5, cost=0.001):
        t0, fl, G, Rd = TG[base]
        sc = (t0 / (core.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0)
        sig, fs = flow(f, sh, K)
        nav, td = run(C, Z, full(core), reg, idx, sc, sig, fs, G, Rd, "c1", cost)
        r = {k: seg(nav, spy, a, b, td) for k, (a, b) in
             {"is": (START, IS_END), "oos": (OOS_START, END), "h1": (H1A, H1B), "h2": (H2A, END)}.items()}
        yr = yearly(nav)
        r.update({"yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                  "worst_h2": min(v for y, v in yr.items() if y >= 2021),
                  "worst_is": min(v for y, v in yr.items() if y < 2017)})
        res[nm] = r
        print(nm, "앞", r["is"]["cagr"], r["is"]["mdd"], "| 뒤", r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"],
              "| h1", r["h1"]["cagr"], "h2", r["h2"]["cagr"], r["h2"]["mdd"], "최악", r["worst_oos"], flush=True)

    # 기준점: 지금 🎯(재현 확인 k1117_attack base 17.66) · 새 기준 Q100+흐름1.0(재현 21.50)
    go("base", mix)
    go("NEW", rQ, f=1.0)
    # ① 빈 곳
    go("base__s0", mix, sh=0)                 # 지금 실제 알림 타이밍(하루 늦음)
    go("NEW__s0", rQ, f=1.0, sh=0)
    go("NEW__s2", rQ, f=1.0, sh=2)            # 날짜 창 하루 더 일찍
    go("NEW__K4", rQ, f=1.0, K=4); go("NEW__K6", rQ, f=1.0, K=6)
    go("base__c25", mix, cost=0.0025); go("NEW__c25", rQ, f=1.0, cost=0.0025)
    go("port_base", mix, base="port"); go("NEW__port", rQ, base="port", f=1.0)
    go("Q100_f06", rQ)                        # QQQ 만(흐름 그대로) — 흐름 없이 실행할 경우 기준
    # ② BTC 칸 on 새 기준 · 지금 🎯
    for w in (0.10, 0.15, 0.20):
        go(f"NEW_B{int(w*100)}", sleeve(rQ, rB, W_btc(w), 0.001), f=1.0)
    for w in (0.10, 0.20):
        go(f"base_B{int(w*100)}", sleeve(mix, rB, W_btc(w), 0.001))
    bc = [k for k in res if k.startswith("NEW_B")]
    pickB = max(bc, key=lambda k: res[k]["h1"]["cagr"])
    wB = int(pickB[5:]) / 100
    shB = {}
    for tag, wv in {"w-20": wB * 0.8, "w+20": wB * 1.2}.items():
        go(f"{pickB}__{tag}", sleeve(rQ, rB, W_btc(wv), 0.001), f=1.0); shB[tag] = f"{pickB}__{tag}"
    go(f"{pickB}__c25", sleeve(rQ, rB, W_btc(wB), 0.0025), f=1.0, cost=0.0025); shB["c25"] = f"{pickB}__c25"
    go(f"{pickB}__s0", sleeve(rQ, rB, W_btc(wB), 0.001), f=1.0, sh=0); shB["s0"] = f"{pickB}__s0"
    go(f"{pickB}__port", sleeve(rQ, rB, W_btc(wB), 0.001), base="port", f=1.0); shB["port"] = f"{pickB}__port"
    # ③ SOXX 칸 on 새 기준
    for w in (0.20, 0.33, 0.50):
        go(f"NEW_X{int(w*100)}", sleeve(rQ, rX, W_const(w), 0.001), f=1.0)
    xc = [k for k in res if k.startswith("NEW_X")]
    pickX = max(xc, key=lambda k: res[k]["is"]["cagr"] if res[k]["is"]["mdd"] > res["NEW"]["is"]["mdd"] - 10 else -99)
    wX = int(pickX[5:]) / 100
    shX = {}
    for tag, wv in {"w-20": wX * 0.8, "w+20": min(1.0, wX * 1.2)}.items():
        go(f"{pickX}__{tag}", sleeve(rQ, rX, W_const(wv), 0.001), f=1.0); shX[tag] = f"{pickX}__{tag}"
    go(f"{pickX}__c25", sleeve(rQ, rX, W_const(wX), 0.0025), f=1.0, cost=0.0025); shX["c25"] = f"{pickX}__c25"
    go(f"{pickX}__port", sleeve(rQ, rX, W_const(wX), 0.001), base="port", f=1.0); shX["port"] = f"{pickX}__port"
    # 둘 다(BTC + SOXX) 얹기
    go("NEW_B_X", sleeve(sleeve(rQ, rX, W_const(wX), 0.001), rB, W_btc(wB), 0.001), f=1.0)

    qqq = C["QQQ"].reindex(idx); btc = C["BTC"].reindex(idx).dropna(); soxx = C["SOXX"].reindex(idx).dropna()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {k: seg(spy, spy, a, b) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END), "h1": (H1A, H1B), "h2": (H2A, END)}.items()},
           "qqq": {k: seg(qqq, spy, a, b) for k, (a, b) in {"is": (START, IS_END), "oos": (OOS_START, END), "h1": (H1A, H1B), "h2": (H2A, END)}.items()},
           "btc": {"h1": seg(btc, spy.reindex(btc.index), H1A, H1B), "h2": seg(btc, spy.reindex(btc.index), H2A, END)},
           "soxx": {"is": seg(soxx, spy.reindex(soxx.index), START, IS_END), "oos": seg(soxx, spy.reindex(soxx.index), OOS_START, END)},
           "spy_yr": yearly(spy), "pickB": pickB, "pickX": pickX, "shakeB": shB, "shakeX": shX, "res": res,
           "note": ("🎯 틀(k1106_exectime3.run 예약 종가판 c1 · 목표 22·아래 0.70·국면·🧭 추세 칸) · NEW = 코어 QQQ 100% + 월말 흐름 몫 1.0(Q11/17-1) · "
                    "s0 = 하루 늦은 알림(지금 실제) · s2 = 하루 더 일찍 · K = 월말 창 길이 · B = BTC 고정 칸(달 1회 맞춤, 200일 자료 뒤) · "
                    "X = SOXX 고정 칸(달 1회) · BTC·SOXX 를 무리에 넣은 것 자체가 「이긴 걸 아는」 고르기 · 레버리지 없음 · 매수 추천 아님")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
