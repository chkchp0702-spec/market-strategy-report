"""📈 11/6 12시 — k1106_exectime3: 한국에서 할 수 있는 체결(다음 날 시가 23:30)로 맞춘 판
  월말 흐름 신호는 이틀 전 종가 쏠림이라 하루 일찍 알 수 있음 → sig.shift(-s) 로 앞당겨 시가 체결(o1)
  (원래: k1106_exectime 분해: 어느 칸(국면·변동성·월말 흐름·추세 칸 TRD)이 「같은 종가 vs 다음 종가」 차이를 만드나
  (원래 설명) (체결 시점 = 실전 칸 100%)
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

OUT = Path("market/lab/k1106_exectime3.json")
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
        r1, w = drift(w, ON, d)          # 밤 몫은 옛 비중으로 (11/6 고침: 처음엔 체결을 밤 앞에 둬서 o1 = c0 이 됐음)
        # 시가 체결
        for p in [p for p in pend if p[0] == i and p[1] == "o"]:
            w, tv = trade(w, p[2], p[3]); tv_tot += tv
        pend = [p for p in pend if not (p[0] == i and p[1] == "o")]
        r2, w = drift(w, ID, d)
        r = (1 + r1) * (1 + r2) - 1 - tv_tot * cost * (1 + r1)
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
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
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
    z = pd.Series(0.0, index=C.index); one = pd.Series(1.0, index=C.index); allon = pd.Series(True, index=C.index)
    res = {}
    def go(nm, s_, g_, a_, f_, m, cost=0.001):
        nav, td = run(C, ON, ID, g_, idx, s_, a_, f_, G_CONC, RD_CONC, m, cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        res[nm] = {"is": a, "oos": b}
        print(nm, a["cagr"], b["cagr"], b["mdd"], b["turn"], flush=True)
    for sh in (0, 1, 2):
        a_ = msig.shift(-sh).fillna(0.0); f_ = mfs.shift(-sh).fillna(0.0)
        for m in ("c0", "o1", "c1"):
            go(f"full_s{sh}_{m}", sc, reg, a_, f_, m)
            go(f"flow_s{sh}_{m}", one, allon, a_, f_, m)
    go("noflow_o1", sc, reg, z, z, "o1"); go("noflow_c0", sc, reg, z, z, "c0")
    go("full_s1_o1_c25", sc, reg, msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0), "o1", 0.0025)
    go("full_s0_c0_c25", sc, reg, msig, mfs, "c0", 0.0025)
    # 흔들기: 월말 창 K 4·6 · 쏠림 문턱 0.4·0.6%
    for K_, th in ((4, 0.005), (6, 0.005), (5, 0.004), (5, 0.006)):
        s2, f2 = make(C, DM, DQ, K=K_, th=th)
        go(f"shake_K{K_}_th{th}_s1_o1", sc, reg, s2.shift(-1).fillna(0.0), f2.shift(-1).fillna(0.0), "o1")
        go(f"shake_K{K_}_th{th}_s0_c0", sc, reg, s2, f2, "c0")
    out["res"] = res
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
