"""📈 11/17 12시 — k1117_attack: 「위험 허용」 기준으로 다시 잰 🎯 공격 손잡이 묶음
  사용자 11/11 16시: 레버리지·곱버스 금지 · 위험 키우기 허용(뒤 낙폭이 SPY ≈ −34 보다 깊지 않으면 됨) · 같은 위험 맞대기는 참고만
  왜 다시 여나: 아래 셋은 예전에 「같은 위험이면 ≈0」 으로 접혔음 — 이제 판정 기준이 연수익(낙폭 한도 안)이라 다시 잼
    ① 코어 QQQ 100% (Q11/12-1, 뒤 +2.36 · 🎯 에서만 잼)
    ② 🔄 월말 흐름 옮기는 몫 0.6 → 0.8·1.0 (Q11/9-2, 💼 에서만 잼 · 🎯 에선 처음)
    ③ 🔴 국면 방어 줄이기 — 🔴 때 주식 50% → 75%·100% (현금 칸 줄이기)
    ④ 변동성 맞춤 목표 22 → 30 · 끔 (위 한도 1.0 그대로 = 레버리지 없음)
  서로 뺏어 먹는지(k1109_bundle 교훈)를 묶음 안에서 같이 잼 · 덤: 2022 형 표지(SPY·TLT 63일 둘 다 마이너스면 🔴 로 봄)
  틀: k1106_exectime3.run (예약 종가판 · c1) · k1113_betaladder 와 같은 go() — 코어 두 칸 일수익·목표·국면 비중·흐름 몫만 바꿈
  고르기: 앞 2008-07~2016 연수익 1등(앞 낙폭이 SPY 앞 낙폭보다 얕은 것) → 뒤 2017~ 시험 · ±20% 흔들기 · 비용 0.25% · 💼 판 · 해별
→ market/lab/k1117_attack.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys, itertools
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

OUT = Path("market/lab/k1117_attack.json")
A = math.sqrt(252) * 100


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
    FL = {}
    for f in (0.48, 0.6, 0.8, 1.0):
        ms_, fs_ = make(C, DM, DQ, f=f)
        FL[f] = (ms_.shift(-1).fillna(0.0), fs_.shift(-1).fillna(0.0))

    # 2022 형 표지: 전날 종가 기준 SPY 63일·TLT 63일 수익 둘 다 마이너스
    both = ((C["SPY"].pct_change(63) < 0) & (C["TLT"].pct_change(63) < 0)).fillna(False)
    reg22 = (reg & ~both).astype(bool)

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    qqq = C["QQQ"].reindex(idx)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END), "yr": yearly(spy)},
           "qqq": {"is": seg(qqq, spy, START, IS_END), "oos": seg(qqq, spy, OOS_START, END), "yr": yearly(qqq)},
           "both_share_pct": round(float(both.reindex(idx).mean()) * 100, 1)}
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}

    def go(nm, base="conc", core="B", f=0.6, tgt=None, rd=None, cost=0.001, rg=None):
        t0, fl, G, Rd = TG[base]
        Rd = dict(Rd)
        if rd is not None:          # 🔴 때 주식 몫(SPY+QQQ 합) — GLD 는 그대로
            Rd["SPY"] = Rd["QQQ"] = rd / 2
        e1, e2 = (rS, rQ) if core == "B" else (rQ, rQ)
        rr = 0.5 * e1 + 0.5 * e2
        tt = t0 if tgt is None else tgt
        sc = pd.Series(1.0, index=C.index) if tt == 0 else (tt / (rr.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0)
        sig1, fs1 = FL[f]
        nav, td = run(C, Z, full(e1, e2), reg if rg is None else rg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        yr = yearly(nav)
        res[nm] = {"is": a, "oos": b, "yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                   "worst_is": min(v for y, v in yr.items() if y < 2017), "eq_up": round(float(sc.reindex(idx).mean()) * 100, 1)}
        print(nm, "앞", a["cagr"], a["mdd"], "| 뒤", b["cagr"], b["mdd"], b["sharpe"], "최악", res[nm]["worst_oos"], flush=True)

    go("base")                                   # 지금 🎯 (재현 확인: k1113 base 와 같아야)
    go("Q100", core="Q")
    go("port_base", base="port")
    go("base__c25", cost=0.0025)

    grid = {}
    for core, f, tgt, rd in itertools.product(("B", "Q"), (0.6, 0.8, 1.0), (22.0, 30.0, 0), (0.5, 0.75, 1.0)):
        nm = f"G_{core}_f{f}_t{int(tgt)}_r{rd}"
        go(nm, core=core, f=f, tgt=tgt, rd=rd); grid[nm] = (core, f, tgt, rd)
    spy_is_mdd = out["spy"]["is"]["mdd"]; spy_oos_mdd = out["spy"]["oos"]["mdd"]
    ok = [k for k in grid if res[k]["is"]["mdd"] > spy_is_mdd]
    pick = max(ok, key=lambda k: res[k]["is"]["cagr"])
    # 같은 코어 안에서 「흐름 몫만」·「국면만」·「목표만」 바꾼 한 손잡이 판 (뺏어 먹기 확인용)
    out["pick"] = pick
    # 앞 2등·3등도 기록(고르기 운 확인)
    out["rank_is"] = sorted(ok, key=lambda k: -res[k]["is"]["cagr"])[:8]
    print("PICK", pick, flush=True)
    core, f, tgt, rd = grid[pick]
    sh = {}
    f2 = {"f-20": round(f * 0.8, 2)}
    if f * 1.2 <= 1.0001: f2["f+20"] = round(f * 1.2, 2)
    for tag, fv in f2.items():
        if fv not in FL:
            ms_, fs_ = make(C, DM, DQ, f=fv); FL[fv] = (ms_.shift(-1).fillna(0.0), fs_.shift(-1).fillna(0.0))
        go(f"{pick}__{tag}", core=core, f=fv, tgt=tgt, rd=rd); sh[tag] = f"{pick}__{tag}"
    if tgt:
        for tag, tv in {"t-20": tgt * 0.8, "t+20": tgt * 1.2}.items():
            go(f"{pick}__{tag}", core=core, f=f, tgt=tv, rd=rd); sh[tag] = f"{pick}__{tag}"
    else:
        go(f"{pick}__t36", core=core, f=f, tgt=36.0, rd=rd); sh["t36"] = f"{pick}__t36"
    for tag, rv in {"r-20": rd * 0.8, "r+20": min(1.0, rd * 1.2)}.items():
        go(f"{pick}__{tag}", core=core, f=f, tgt=tgt, rd=rv); sh[tag] = f"{pick}__{tag}"
    go(f"{pick}__c25", core=core, f=f, tgt=tgt, rd=rd, cost=0.0025); sh["c25"] = f"{pick}__c25"
    go(f"{pick}__port", base="port", core=core, f=f, tgt=tgt, rd=rd); sh["port"] = f"{pick}__port"
    go(f"{pick}__r22", core=core, f=f, tgt=tgt, rd=rd, rg=reg22); sh["reg22"] = f"{pick}__r22"
    out["shake"] = sh
    # 2022 표지 덤: 지금 🎯·Q100 위
    go("base__r22", rg=reg22); go("Q100__r22", core="Q", rg=reg22)
    # Q100 위 한 손잡이씩 (뺏어 먹기)
    go("Q_f1.0_only", core="Q", f=1.0); go("Q_r1.0_only", core="Q", rd=1.0); go("Q_t0_only", core="Q", tgt=0)
    go("B_f1.0_only", f=1.0)
    out["spy_mdd"] = {"is": spy_is_mdd, "oos": spy_oos_mdd}
    out["res"] = res
    out["note"] = ("🎯 틀(아래 0.70·월말 흐름 s1·c1 예약 종가·🧭 추세 칸) · core B = S&P½·나스닥½ / Q = QQQ 100% · f = 월말 흐름 옮기는 몫 · "
                   "t = 변동성 맞춤 목표(0 = 끔, 위 한도 1.0 = 레버리지 없음) · r = 🔴 때 주식 몫(지금 0.5) · reg22 = SPY·TLT 63일 둘 다 마이너스면 🔴 · "
                   "ETF 만이라 종목 생존 편향 없음 · 단 QQQ 를 고른 것 자체는 앞 구간에서도 이긴 고르기(앞 QQQ>SPY) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
