"""📈 11/5 12시 2번 — (다) 칸 배분 재설계: 💼 와 🎯 를 「한 원화 계좌」로 섞으면 같은 위험에서 각각보다 나은가
  10시 계획. 크기 산수: 두 포트 샤프 비슷(뒤 1.17·1.19) → 반반 섞기 샤프 배수 ≈ √(2/(1+ρ)) · ρ 0.85~0.95 면 +1.3~4% → 연 +0.2~0.6%p
    → 근접 상한 근처 · 싼 실험(이미 있는 틀)이라 상관 ρ 를 재서 숫자로 닫는다.
  💼 = C안(S 47.5·Q 47.5·금 5 / 하락 31.5·31.5·금 11) 목표 15%·한도 30%·덜어낸 몫 🧭 추세 칸·월말 흐름
  🎯 = 50·50 / 하락 25·25 목표 22%·한도 70%·🧭 추세 칸·월말 흐름 (둘 다 k1028_qflow.core_run, 비용 0.1%)
  섞기: w(🎯 몫) 0~1 · 매달 첫날 다시 맞춤(비용 0.1% × 옮긴 양) + 「60일 변동성 거꾸로」 동적 섞기
  같은 위험: 🎯 단독을 현금(^IRX)과 섞어 그 판의 앞 구간 변동성에 맞춘 것과 비교(레버리지 없음)
→ market/lab/k1105_blend.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC, G_PORT, RD_PORT

OUT = Path("market/lab/k1105_blend.json")


def mix(rA, rB, w, monthly=True, cost=0.001):
    """A=💼, B=🎯, w=B 몫. 매달 첫날 다시 맞춤."""
    idx = rA.index; a, b = 1 - w, w; out = []
    for i, d in enumerate(idx):
        if i > 0 and idx[i - 1].month != d.month:
            t = abs(a / (a + b) - (1 - w)); a, b = (1 - w), w; c = t * 2 * cost / 2
        else:
            c = 0.0
            s_ = a + b; a, b = a / s_, b / s_
        r = a * rA.iloc[i] + b * rB.iloc[i] - c
        a *= 1 + rA.iloc[i]; b *= 1 + rB.iloc[i]
        out.append(r)
    return pd.Series(out, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
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
    sigM, fsM = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    scP = (15.0 / rv).clip(upper=1.0, lower=0.30).fillna(1.0)
    scK = (22.0 / rv).clip(upper=1.0, lower=0.70).fillna(1.0)
    nP, _ = core_run(C, reg, idx, scP, sigM, fsM, G_PORT, RD_PORT)
    nK, _ = core_run(C, reg, idx, scK, sigM, fsM, G_CONC, RD_CONC)
    rP = nP.pct_change().fillna(0.0); rK = nK.pct_change().fillna(0.0)
    cash = cdl.reindex(idx).fillna(0.0) if isinstance(cdl, pd.Series) else pd.Series(0.0, index=idx)

    def st(r):
        nav = (1 + r).cumprod()
        return {"is": seg(nav, spy, START, IS_END), "oos": seg(nav, spy, OOS_START, END)}

    def per(r, a, b):
        return r[(r.index >= a) & (r.index <= b)]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "corr": {"is": round(float(per(rP, START, IS_END).corr(per(rK, START, IS_END))), 3),
                    "oos": round(float(per(rP, OOS_START, END).corr(per(rK, OOS_START, END))), 3)},
           "cash_ann": round(float(cash.mean() * 252 * 100), 2)}
    print("CORR", out["corr"], "cash", out["cash_ann"], flush=True)
    SP, SK = st(rP), st(rK)
    out["port"] = SP; out["conc"] = SK
    rows = {}
    for w in np.round(np.arange(0, 1.01, 0.1), 1):
        rb = mix(rP, rK, float(w))
        Sb = st(rb)
        # 같은 위험 대조: 🎯 × k + 현금 × (1−k), k = 앞 변동성 맞춤
        k = min(1.0, Sb["is"]["vol"] / SK["is"]["vol"])
        rc = k * rK + (1 - k) * cash
        Sc = st(rc)
        rows[str(w)] = {"is": Sb["is"], "oos": Sb["oos"], "k": round(k, 3),
                        "vs_conc_same_risk": {p: {m: round(float(Sb[p][m] - Sc[p][m]), 2) for m in ("cagr", "vol", "mdd", "sharpe")} for p in ("is", "oos")}}
        print(w, rows[str(w)]["is"]["cagr"], rows[str(w)]["oos"]["cagr"], rows[str(w)]["oos"]["sharpe"], rows[str(w)]["vs_conc_same_risk"], flush=True)
    out["blend"] = rows
    # 동적: 60일 변동성 거꾸로(위험 반반)
    vP = rP.rolling(60).std(); vK = rK.rolling(60).std()
    wK = (1 / vK) / (1 / vK + 1 / vP)
    wK = wK.shift(1).fillna(0.5)
    wm = wK.groupby([wK.index.year, wK.index.month]).transform("first")
    rd = (1 - wm) * rP + wm * rK - (wm.diff().abs().fillna(0.0) * 0.001)
    Sd = st(rd); k = min(1.0, Sd["is"]["vol"] / SK["is"]["vol"]); Sc = st(k * rK + (1 - k) * cash)
    out["invvol"] = {"is": Sd["is"], "oos": Sd["oos"], "w_mean": round(float(wm.mean()), 2),
                     "vs_conc_same_risk": {p: {m: round(float(Sd[p][m] - Sc[p][m]), 2) for m in ("cagr", "vol", "mdd", "sharpe")} for p in ("is", "oos")}}
    print("INVVOL", out["invvol"], flush=True)
    # 앞에서 고르기: 같은 위험 대비 앞 샤프 차 1등(w 0.1~0.9)
    cand = {k_: v for k_, v in rows.items() if k_ not in ("0.0", "1.0")}
    pick = max(cand, key=lambda k_: cand[k_]["vs_conc_same_risk"]["is"]["sharpe"] + cand[k_]["vs_conc_same_risk"]["is"]["cagr"] / 10)
    out["is_pick"] = pick
    sh = {}
    for wv in (round(float(pick) * 0.8, 2), round(min(0.95, float(pick) * 1.2), 2)):
        rb = mix(rP, rK, wv); Sb = st(rb); kk = min(1.0, Sb["is"]["vol"] / SK["is"]["vol"]); Sc = st(kk * rK + (1 - kk) * cash)
        sh[str(wv)] = {p: {m: round(float(Sb[p][m] - Sc[p][m]), 2) for m in ("cagr", "mdd", "sharpe")} for p in ("is", "oos")}
    out["shake"] = sh
    print("PICK", pick, rows[pick], sh, flush=True)
    out["note"] = "레버리지 없음 · ETF 만, 생존 편향 없음 · ⚡ 킥(고래 15·돌파 4)은 💼 뼈대 81% 라 💼 로 대신 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
