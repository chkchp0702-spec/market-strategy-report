"""📈 11/6 12시 — 🎯 「언제 체결하나」 실험 (체결 시점 = 실전 칸 100%)
  지금 백테스트: 종가 d 까지 보고 → 같은 종가 d 에 바꿈(c0). 한국에서 실제로는 결정이 아침 6시(미국 마감 뒤)라
  같은 종가 체결이 불가능 → 실제 선택지는 다음 날 시가(o1, 한국 밤 23:30 장 시작) · 다음 날 종가(c1) · 반반(h1)
  · 이틀 뒤 시가(o2, 하루 더 늦게 확인 후)
  규칙(목표 22·위 1.0·아래 0.70·월말 흐름·국면·🧭 추세 칸)·결정 시점은 그대로, 체결 시점만 바꿈
  밤 몫 = 시가/전날 종가, 낮 몫 = 종가/시가 (SPY·QQQ·GLD·TLT 실제 시가) · 🧭 추세 칸(TRD)은 시가 없음 → 낮 몫에 통째로
  비용 0.1%·0.25% · 앞 2008-07~2016 / 뒤 2017~ · 판정 기준은 c1(현실적 기본값) 대비 o1
→ market/lab/k1106_exectime.json
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
import k1028_qflow as QF
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC

OUT = Path("market/lab/k1106_exectime.json")
A = math.sqrt(252) * 100
KEYS = ["SPY", "QQQ", "GLD", "TRD", "BND"]


def run(C, ON, ID, reg, idx, sc, sig, fs, G, Rd, mode, cost, band=0.05):
    """mode: c0 같은 종가 · o1 다음 시가 · c1 다음 종가 · h1 반은 시가 반은 종가 · o2 이틀 뒤 시가"""
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i, s_now, f):
        b = G if bool(regv.iloc[i]) else Rd
        e = (b["SPY"] + b["QQQ"]) * float(sc.iloc[i])
        gl = b["GLD"]; trd = 1 - e - gl; bnd = 0.0
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and f > 0:
            e += (gl + trd) * f; gl *= (1 - f); trd *= (1 - f)
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": gl, "TRD": trd, "BND": bnd}

    def trade(w, t, frac=1.0):
        nw = {k: w[k] + frac * (t[k] - w[k]) for k in w}
        tv = sum(abs(nw[k] - w[k]) for k in w) / 2
        return nw, tv

    def drift(w, R, d):
        rr = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values())
        return rr, {k: v / s_ for k, v in nw.items()}

    w = last = None; lsig = 0.0
    pend = []   # (실행할 날 index, 시점 'o'/'c', 목표, 비율)
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1, 0.0, 0.0); last = dict(w)
        tv_tot = 0.0
        # 시가 체결
        for p in [p for p in pend if p[0] == i and p[1] == "o"]:
            w, tv = trade(w, p[2], p[3]); tv_tot += tv
        pend = [p for p in pend if not (p[0] == i and p[1] == "o")]
        r1, w = drift(w, ON, d)
        r1 -= tv_tot * cost
        r2, w = drift(w, ID, d)
        r = (1 + r1) * (1 + r2) - 1
        tv_c = 0.0
        for p in [p for p in pend if p[0] == i and p[1] == "c"]:
            w, tv = trade(w, p[2], p[3]); tv_c += tv
        pend = [p for p in pend if not (p[0] == i and p[1] == "c")]
        # 결정 (종가 d)
        j = i + 1
        snext = float(sig.iloc[j]) if j < len(sig) else 0.0
        fnext = float(fs.iloc[j]) if j < len(fs) else 0.0
        t = tg(i, snext, fnext)
        newm = j < len(C.index) and C.index[j].month != d.month
        if newm or snext != lsig or regv.iloc[i] != regv.iloc[i - 1] or max(abs(t[k] - last[k]) for k in t) > band:
            last = dict(t)
            if pend:   # 밀린 주문이 있으면 목표만 새 결정으로 바꾸고 체결 날은 그대로(계속 미뤄지지 않게)
                pend = [(p[0], p[1], t, p[3]) for p in pend]
            elif mode == "c0":
                w, tv = trade(w, t); tv_c += tv
            elif mode == "o1":
                pend.append((i + 1, "o", t, 1.0))
            elif mode == "c1":
                pend.append((i + 1, "c", t, 1.0))
            elif mode == "h1":
                pend.append((i + 1, "o", t, 0.5)); pend.append((i + 1, "c", t, 1.0))
            elif mode == "o2":
                pend.append((i + 2, "o", t, 1.0))
        lsig = snext
        r -= tv_c * cost
        rets.append(r); turns.append(tv_tot + tv_c)
    return (1 + pd.Series(rets, index=idx)).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    O = {}
    for k in ["SPY", "QQQ", "GLD"]:
        O[k] = px.pop(k)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    O["TLT"] = px["TLT"]
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
    r = 0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()
    sc = (22.0 / (r.rolling(20).std() * A)).clip(upper=1.0, lower=0.70).fillna(1.0)

    # 밤·낮 몫 (야후 조정 시가·종가 · 총수익은 C 종가 기준으로 맞춤: 낮 = 종가 수익 ÷ 밤)
    ON = pd.DataFrame(0.0, index=C.index, columns=KEYS); ID = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ON[k] = on; ID[k] = (1 + cc) / (1 + on) - 1
    ID["TRD"] = C["TRD"].pct_change().fillna(0.0)

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    # 확인: c0 가 원래 core_run 과 같은지
    QF.COST = 0.001
    nav0, td0 = core_run(C, reg, idx, sc, msig, mfs, G_CONC, RD_CONC)
    out["check_core_run"] = {"is": seg(nav0, spy, START, IS_END, td0), "oos": seg(nav0, spy, OOS_START, END, td0)}
    print("CHECK", out["check_core_run"], flush=True)
    # 밤·낮 몫 크기
    out["on_share"] = {k: {"on_ann": round(float(ON[k][idx].mean() * 25200), 2), "id_ann": round(float(ID[k][idx].mean() * 25200), 2)} for k in ["SPY", "QQQ", "GLD", "BND"]}
    res = {}
    for cost in (0.001, 0.0025):
        rc = {}
        for m in ("c0", "o1", "c1", "h1", "o2"):
            nav, td = run(C, ON, ID, reg, idx, sc, msig, mfs, G_CONC, RD_CONC, m, cost)
            rc[m] = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
            yr = {}
            for y in range(2008, idx[-1].year + 1):
                a = nav[nav.index.year == y]
                if len(a) > 5:
                    yr[str(y)] = round(float((a.iloc[-1] / a.iloc[0] - 1) * 100), 2)
            rc[m]["yr"] = yr
            print(cost, m, rc[m]["is"], rc[m]["oos"], flush=True)
        res[str(cost)] = rc
    out["res"] = res

    def d(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}
    R1 = res["0.001"]
    out["delta"] = {f"{b}_vs_{a}": d(R1[a], R1[b]) for a, b in [("c0", "c1"), ("c0", "o1"), ("c1", "o1"), ("c1", "h1"), ("c1", "o2")]}
    R2 = res["0.0025"]
    out["delta25"] = {"o1_vs_c1": d(R2["c1"], R2["o1"]), "c1_vs_c0": d(R2["c0"], R2["c1"])}
    j = out["delta"]["o1_vs_c1"]
    jj = {"is": j["is"]["cagr"], "oos": j["oos"]["cagr"], "oos_mdd": j["oos"]["mdd"], "oos_vol": j["oos"]["vol"],
          "cost25_oos": out["delta25"]["o1_vs_c1"]["oos"]["cagr"],
          "lag_cost_c1": out["delta"]["c1_vs_c0"]["oos"]["cagr"], "lag_cost_o1": out["delta"]["o1_vs_c0"]["oos"]["cagr"]}
    jj["verdict"] = "✅" if (jj["oos"] > 1.0 and jj["is"] >= 0 and jj["cost25_oos"] > 0) else ("🟡" if (jj["oos"] >= 0.33 and jj["is"] >= 0) else "❌")
    out["judge"] = jj
    print("JUDGE", jj, flush=True)
    out["note"] = "규칙·결정은 지금 🎯 그대로, 체결 시점만 바꿈 · 🧭 추세 칸 시가 없음(낮 몫에 통째로) · ETF 만, 생존 편향 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
