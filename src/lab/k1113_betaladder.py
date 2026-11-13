"""📈 11/13 12시 — k1113_betaladder: 「낙폭 예산 다 쓰기」 — QQQ 로 바꾸기(+2.36) 위에 남은 계단이 있나
  사용자 11/11 16시: 레버리지·곱버스 금지 · 위험 키우기 허용(뒤 낙폭이 SPY ≈ −34 보다 깊지 않으면 됨)
  출발 숫자(k1112_strongcore): 🎯 지금 뒤 18.03 · 낙폭 −18.7 / Q100 뒤 20.39 · 낙폭 −21.6 / QQQ 그냥 들기 뒤 20.27 · 낙폭 −35.1
    → 레버리지 없이 「+3(뒤 21.03)」 은 QQQ 그냥 들기보다 더 벌어야 닿음 = 코어에 QQQ 보다 센 것이 들어가야 함
  크기 산수
    ① 🔁 회복 부스터(🔴→🟢 뒤 H일만 코어 QQQ 100%) — 회복 날 비중 ≈30% × SPY 칸 ½ × (회복기 QQQ−SPY ≈ +10%p) ≈ 1.5 → 근접 상한
    ② 🪜 SPY↔QQQ 상대 모멘텀 1등 100% — 상한 ≈ Q100(+2.4) + 2022·2016 피하기 ≈ 2.5~3
    ③ 🔩 반도체(SOXX) 칸 — 코어 ⅓~½ × (SOXX−QQQ 뒤 ≈ +8~10%p) ≈ 3~5 → 통과 · ⚠️ 「반도체가 이긴 걸 아는」 고르기 편향 → 앞 구간(2008-07~16)에서도 이겼는지가 시험
    ④ 🪜 {SPY·QQQ·SOXX} 상대 모멘텀 1등 — 규칙으로 반도체를 「쌀 때만」 담기 · 상한 ③과 비슷
  틀: k1106_exectime3.run (예약 종가판 · c1) · k1112_strongcore 와 같은 go() — 코어 두 칸(SPY·QQQ 자리)의 일수익만 바꿈
      판단은 전날 종가까지(국면 = reg.shift(1) · 모멘텀 = 21일 뺀 LB) · 다음 체결 · 칸 안 바꿈엔 비용 매김(0.1%·0.25%)
→ market/lab/k1113_betaladder.json
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
from k1112_strongcore import basket, yearly

OUT = Path("market/lab/k1113_betaladder.json")
A = math.sqrt(252) * 100


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD", "SOXX"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for k in ["SPY", "QQQ", "GLD"]:
        px.pop(k)
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
    msig, mfs = make(C, DM, DQ)
    sig1, fs1 = msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0)

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0); rX = C["SOXX"].pct_change().fillna(0.0)
    soxx = C["SOXX"].reindex(idx).dropna()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END), "yr": yearly(spy)},
           "qqq": {"is": seg(C["QQQ"].reindex(idx), spy, START, IS_END), "oos": seg(C["QQQ"].reindex(idx), spy, OOS_START, END),
                   "yr": yearly(C["QQQ"].reindex(idx))},
           "soxx": {"is": seg(soxx, spy.reindex(soxx.index), START, IS_END), "oos": seg(soxx, spy.reindex(soxx.index), OOS_START, END),
                    "yr": yearly(soxx)}}
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}

    def go(nm, base, e1, e2, cost=0.001, volon=True, tgt=None):
        t_, fl, G, Rd = TG[base]
        t_ = tgt or t_
        rr = 0.5 * e1 + 0.5 * e2
        sc = (t_ / (rr.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0) if volon else pd.Series(1.0, index=C.index)
        nav, td = run(C, Z, full(e1, e2), reg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        yr = yearly(nav)
        res[nm] = {"is": a, "oos": b, "yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                   "worst_is": min(v for y, v in yr.items() if y < 2017), "eq_up": round(float(sc.reindex(idx).mean()) * 100, 1)}
        print(nm, "앞", a["cagr"], a["mdd"], "| 뒤", b["cagr"], b["mdd"], b["sharpe"], "최악", res[nm]["worst_oos"], flush=True)
        return nav

    go("base", "conc", rS, rQ)
    go("Q100", "conc", rQ, rQ)
    go("port_base", "port", rS, rQ)
    go("base__c25", "conc", rS, rQ, cost=0.0025)
    go("port_base__c25", "port", rS, rQ, cost=0.0025)

    # ① 🔁 회복 부스터: 🟢 로 넘어간 뒤 H 거래일 동안 SPY 칸도 QQQ (판단은 전날 국면)
    regy = reg.shift(1).fillna(False).astype(bool)
    on_edge = regy & ~regy.shift(1).fillna(False).astype(bool)
    grp = on_edge.cumsum()
    since = regy.groupby(grp).cumsum()               # 🟢 로 넘어간 뒤 며칠째(🟢 동안)

    def rec(H, cost):
        flag = regy & (since <= H) & (grp > 0)
        ch = flag.astype(int).diff().abs().fillna(0.0)
        return pd.Series(np.where(flag, rQ, rS), index=C.index) - ch * cost, flag

    rec_share = {}
    for H in (63, 126, 252):
        e1, fl = rec(H, 0.001)
        rec_share[H] = round(float(fl.reindex(idx).mean()) * 100, 1)
        go(f"REC_{H}", "conc", e1, rQ)
    out["rec_share_pct"] = rec_share

    # ② 🪜 SPY↔QQQ 상대 모멘텀 1등(달 1회) · ④ {SPY·QQQ·SOXX} 1등
    LAD = {"RS2": ["SPY", "QQQ"], "RS3": ["SPY", "QQQ", "SOXX"]}
    for un, U in LAD.items():
        for lb in (126, 252):
            br, _, _ = basket(C, U, lb, 1, 0.001)
            go(f"{un}_L{lb}", "conc", br, br)            # 코어 전부 1등
            go(f"{un}_L{lb}_halfQ", "conc", rQ, br)     # QQQ 반 + 1등 반

    # ③ 🔩 반도체 칸 고정 비중(코어 안) — 매일 맞춤 근사
    for nm, wx in {"SX33": 1 / 3, "SX50": 0.5, "SX67": 2 / 3}.items():
        core = (1 - wx) * rQ + wx * rX
        go(nm, "conc", core, core)

    # 고르기: 앞 구간 1등(앞 낙폭이 SPY 앞 낙폭보다 얕은 것) — 갈래마다
    spy_is_mdd = out["spy"]["is"]["mdd"]
    fam = {"REC": "REC_", "RS2": "RS2_", "RS3": "RS3_", "SX": "SX"}
    picks = {}
    for f, pre in fam.items():
        c = [k for k in res if k.startswith(pre) and "__" not in k and res[k]["is"]["mdd"] > spy_is_mdd]
        if c:
            picks[f] = max(c, key=lambda k: res[k]["is"]["cagr"])
    out["picks"] = picks
    print("PICKS", picks, flush=True)

    shake = {}
    for f, nm in picks.items():
        sh = {}
        if f == "REC":
            H = int(nm.split("_")[1])
            for tag, h2 in {"h-20": int(H * .8), "h+20": int(H * 1.2)}.items():
                e1, _ = rec(h2, 0.001); go(f"{nm}__{tag}", "conc", e1, rQ); sh[tag] = f"{nm}__{tag}"
            e1, _ = rec(H, 0.0025); go(f"{nm}__c25", "conc", e1, rQ, cost=0.0025); sh["c25"] = f"{nm}__c25"
            e1, _ = rec(H, 0.001); go(f"{nm}__port", "port", e1, rQ); sh["port"] = f"{nm}__port"
            go(f"{nm}__novol", "conc", e1, rQ, volon=False); sh["novol"] = f"{nm}__novol"
        elif f in ("RS2", "RS3"):
            lb = int(nm.split("_L")[1].split("_")[0]); half = nm.endswith("_halfQ"); U = LAD[f]
            for tag, lb2 in {"lb-20": int(lb * .8), "lb+20": int(lb * 1.2)}.items():
                br, _, _ = basket(C, U, lb2, 1, 0.001); go(f"{nm}__{tag}", "conc", rQ if half else br, br); sh[tag] = f"{nm}__{tag}"
            br25, _, _ = basket(C, U, lb, 1, 0.0025)
            go(f"{nm}__c25", "conc", rQ if half else br25, br25, cost=0.0025); sh["c25"] = f"{nm}__c25"
            br, _, _ = basket(C, U, lb, 1, 0.001)
            go(f"{nm}__port", "port", rQ if half else br, br); sh["port"] = f"{nm}__port"
            go(f"{nm}__novol", "conc", rQ if half else br, br, volon=False); sh["novol"] = f"{nm}__novol"
        else:
            wx = {"SX33": 1 / 3, "SX50": 0.5, "SX67": 2 / 3}[nm]
            for tag, w2 in {"w-20": wx * .8, "w+20": min(1.0, wx * 1.2)}.items():
                core = (1 - w2) * rQ + w2 * rX; go(f"{nm}__{tag}", "conc", core, core); sh[tag] = f"{nm}__{tag}"
            core = (1 - wx) * rQ + wx * rX
            go(f"{nm}__c25", "conc", core, core, cost=0.0025); sh["c25"] = f"{nm}__c25"
            go(f"{nm}__port", "port", core, core); sh["port"] = f"{nm}__port"
            go(f"{nm}__novol", "conc", core, core, volon=False); sh["novol"] = f"{nm}__novol"
        shake[f] = sh
    out["shake"] = shake
    out["res"] = res
    out["note"] = ("🎯 틀(목표 22·아래 0.70·국면 25/25·월말 흐름 s1·c1 예약 종가·🧭 추세 칸) 에서 코어 두 칸만 바꿈 · 변동성 맞춤은 바뀐 코어의 20일 변동성 · "
                   "REC = 🟢 넘어간 뒤 H 거래일 SPY 칸도 QQQ(전날 국면) · RS = 21일 뺀 LB 수익 1등 100% 달 1회 · SX = 코어 안 SOXX 고정 비중(매일 맞춤 근사·칸 안 회전 비용 안 매김) · "
                   "레버리지 없음 · ETF 라 종목 생존 편향은 없음, 단 반도체(SOXX)를 무리에 넣은 것 자체가 지금 아는 고르기(앞 구간으로 확인) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
