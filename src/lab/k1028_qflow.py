"""📈 10/28 16시 — 「분기말 연기금은 더 세게 판다」 + 🎯 집중에도 월말 흐름
  바깥 재료: 미국 연기금 분기말 리밸런싱 추정 기사(Wells Fargo·GS 「분기말 $260~300억 주식 매도」), NBER w28028(TDF 리밸런싱),
  NBER w33554(리밸런싱의 대가). 연기금은 대개 분기마다 맞추므로 분기 마지막 달엔 「석 달치 쏠림」이 한꺼번에 나올 것이라는 가설.
  ① 맞대기: 분기 마지막 달 창(석 달 쏠림) vs 그 밖 달 창(한 달 쏠림) 하루당 bp
  ② 💼: 지금 적용된 월말 흐름(B1, K5·±0.5%p·60%·TLT·하루 늦게) 위에 분기 변형 얹기
  ③ 🎯 conc(목표 22%·아래 한도 70%): 흐름 없음(C0) vs 월말 흐름(C1) vs 분기 변형
  ④ ±20% 흔들기 · 해마다(2024~2026) 차이
  하루 늦은 체결(drift.shift(2)) · 비용 0.1% · 레버리지 없음 · 매수 추천 아님
→ market/lab/k1028_qflow.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg, COST
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U

OUT = Path("market/lab/k1028_qflow.json")
G_PORT = {"SPY": .475, "QQQ": .475, "GLD": .05}
RD_PORT = {"SPY": .315, "QQQ": .315, "GLD": .11}
G_CONC = {"SPY": .5, "QQQ": .5, "GLD": 0.0}
RD_CONC = {"SPY": .25, "QQQ": .25, "GLD": 0.0}


def drifts(C):
    S = C["SPY"].pct_change().fillna(0.0); B = C["IEF"].pct_change().fillna(0.0)
    idx = C.index
    dm = pd.Series(0.0, index=idx); dq = pd.Series(0.0, index=idx)
    ms = mb = qs = qb = 1.0
    for i, d in enumerate(idx):
        newm = i == 0 or idx[i - 1].month != d.month
        if newm:
            ms, mb = 0.6, 0.4
            if d.month in (1, 4, 7, 10):
                qs, qb = 0.6, 0.4
        ms *= 1 + S.iloc[i]; mb *= 1 + B.iloc[i]; qs *= 1 + S.iloc[i]; qb *= 1 + B.iloc[i]
        dm.iloc[i] = ms / (ms + mb) - 0.6; dq.iloc[i] = qs / (qs + qb) - 0.6
    return dm, dq


def rfe(idx):
    mon = pd.Series(idx.month, index=idx)
    return mon.groupby((mon != mon.shift()).cumsum()).cumcount(ascending=False)


def make(C, DM, DQ, K=5, th=0.005, f=0.6, mode="M", fq=None, Kq=None, lag=2):
    """돌려줌: 부호 신호 sig(+1 = 펀드가 주식 팔 차례), 그날 옮길 몫 fs"""
    idx = C.index; r = rfe(idx)
    qm = pd.Series(idx.month.isin([3, 6, 9, 12]), index=idx)
    fq = f if fq is None else fq; Kq = K if Kq is None else Kq
    pm, pq = DM.shift(lag).fillna(0.0), DQ.shift(lag).fillna(0.0)
    sig = pd.Series(0.0, index=idx); fs = pd.Series(0.0, index=idx)
    for nm, use_q, months, KK, ff in (("m", False, ~qm, K, f), ("q", mode in ("QM", "Q"), qm, Kq, fq)):
        if nm == "m" and mode == "Q":
            continue
        dsrc = pq if use_q else pm
        if nm == "q" and mode == "M":
            dsrc = pm
        w = months & (r < KK)
        up = w & (dsrc > th); dn = w & (dsrc < -th)
        sig[up] = 1.0; sig[dn] = -1.0; fs[up | dn] = ff
    return sig, fs


def edge(C, sig, mask, a, b, bond="TLT"):
    r = (C["SPY"].pct_change() - C[bond].pct_change()).fillna(0.0)
    m = (sig.index >= a) & (sig.index <= b) & (sig != 0) & mask
    x = (-sig[m] * r[m]) * 1e4
    if len(x) < 5:
        return {"n": int(len(x))}
    return {"n": int(len(x)), "bp": round(float(x.mean()), 1), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2)}


def core_run(C, reg, idx, sc, sig, fs, G, Rd, bond="TLT", band=0.05):
    keys = ["SPY", "QQQ", "GLD", "TRD", "BND"]
    Cx = C.copy(); Cx["BND"] = C[bond]
    R = Cx[keys].pct_change().fillna(0.0)
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
    w = last = None; lsig = 0.0
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1, 0.0, 0.0); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        j = i + 1
        snext = float(sig.iloc[j]) if j < len(sig) else 0.0
        fnext = float(fs.iloc[j]) if j < len(fs) else 0.0
        t = tg(i, snext, fnext)
        newm = j < len(C.index) and C.index[j].month != d.month
        tv = 0.0
        if newm or snext != lsig or regv.iloc[i] != regv.iloc[i - 1] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t); r -= tv * COST
        lsig = snext
        rets.append(r); turns.append(tv)
    return (1 + pd.Series(rets, index=idx)).cumprod(), pd.Series(turns, index=idx)


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}

    # ① 맞대기
    qmask = pd.Series(C.index.month.isin([3, 6, 9, 12]), index=C.index)
    ls = {}
    for nm, kw in {"M": dict(mode="M"), "QM": dict(mode="QM")}.items():
        sg, _ = make(C, DM, DQ, **kw)
        for part, mk in (("qmonths", qmask), ("other", ~qmask)):
            ls[f"{nm}_{part}"] = {p: edge(C, sg, mk, a, b) for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END))}
    out["ls"] = ls
    print("LS", ls, flush=True)

    def go(base="port", tgt=None, floor=None, **kw):
        G, Rd = (G_PORT, RD_PORT) if base == "port" else (G_CONC, RD_CONC)
        tgt = tgt or (15.0 if base == "port" else 22.0); floor = floor or (0.30 if base == "port" else 0.70)
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        if kw.get("none"):
            sig = fs = pd.Series(0.0, index=C.index)
        else:
            sig, fs = make(C, DM, DQ, **kw)
        nav, td = core_run(C, reg, idx, sc, sig, fs, G, Rd)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        yr = {}
        for y in (2022, 2023, 2024, 2025, 2026):
            n = nav[nav.index.year == y]
            if len(n) > 5:
                prev = nav[nav.index < n.index[0]]
                b0 = prev.iloc[-1] if len(prev) else n.iloc[0]
                yr[y] = round(float(n.iloc[-1] / b0 - 1) * 100, 2)
        o["yr"] = yr
        return o

    def dlt(a, b):
        d = {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}
        d["yr"] = {y: round(b["yr"][y] - a["yr"][y], 2) for y in b["yr"]}
        d["turn_oos"] = b["oos"].get("turn")
        return d

    # ② 💼
    P0 = go(none=True); P1 = go()
    out["port"] = {"B0_none": P0, "B1_now": P1, "B1_vs_B0": dlt(P0, P1)}
    print("PORT B1 vs B0", out["port"]["B1_vs_B0"], flush=True)
    VAR = {"QM_f0.6": dict(mode="QM"), "QM_fq0.8": dict(mode="QM", fq=0.8), "QM_fq1.0": dict(mode="QM", fq=1.0),
           "M_fq1.0": dict(mode="M", fq=1.0), "QM_Kq8": dict(mode="QM", Kq=8), "QM_Kq8_fq0.8": dict(mode="QM", Kq=8, fq=0.8),
           "Qonly_f0.6": dict(mode="Q")}
    pv = {}
    for nm, kw in VAR.items():
        pv[nm] = dlt(P1, go(**kw)); print("PORT", nm, pv[nm], flush=True)
    out["port"]["var_vs_B1"] = pv
    best = max((k for k in pv if k != "Qonly_f0.6"), key=lambda k: pv[k]["is"]["sharpe"] + pv[k]["is"]["cagr"] / 10)
    out["port"]["is_pick"] = best
    # 흔들기: 지금 규칙(B1) 자체 ±20% (B0 대비) + 고른 분기 변형(B1 대비, 같은 흔들기)
    SH = {"f0.48": dict(f=0.48), "f0.72": dict(f=0.72), "th0.004": dict(th=0.004), "th0.006": dict(th=0.006),
          "K4": dict(K=4), "K6": dict(K=6), "tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0)}
    shB1, shQ = {}, {}
    for nm, kw in SH.items():
        base_kw = {k: v for k, v in kw.items() if k in ("tgt",)}
        sig_kw = {k: v for k, v in kw.items() if k not in ("tgt",)}
        b0 = go(none=True, **base_kw); b1 = go(**base_kw, **sig_kw)
        shB1[nm] = dlt(b0, b1)
        bq = go(**base_kw, **{**VAR[best], **sig_kw})
        shQ[nm] = dlt(b1, bq)
        print("SHAKE", nm, shB1[nm]["is"]["cagr"], shB1[nm]["oos"]["cagr"], "|", shQ[nm]["is"]["cagr"], shQ[nm]["oos"]["cagr"], flush=True)
    out["port"]["shake_B1_vs_B0"] = shB1; out["port"]["shake_pick_vs_B1"] = shQ

    # ③ 🎯 conc
    C0 = go(base="conc", none=True); C1 = go(base="conc")
    out["conc"] = {"C0_none": C0, "C1_month": C1, "C1_vs_C0": dlt(C0, C1)}
    print("CONC C1 vs C0", out["conc"]["C1_vs_C0"], flush=True)
    cv = {}
    for nm in ("QM_f0.6", best):
        cv[nm] = dlt(C0, go(base="conc", **VAR[nm]))
    out["conc"]["var_vs_C0"] = cv
    shc = {}
    for nm, kw in {"f0.48": dict(f=0.48), "f0.72": dict(f=0.72), "th0.004": dict(th=0.004), "th0.006": dict(th=0.006),
                   "K4": dict(K=4), "K6": dict(K=6), "tgt18": dict(tgt=18.0), "tgt26": dict(tgt=26.0)}.items():
        base_kw = {k: v for k, v in kw.items() if k == "tgt"}; sig_kw = {k: v for k, v in kw.items() if k != "tgt"}
        shc[nm] = dlt(go(base="conc", none=True, **base_kw), go(base="conc", **base_kw, **sig_kw))
        print("CONC SHAKE", nm, shc[nm]["is"]["cagr"], shc[nm]["oos"]["cagr"], flush=True)
    out["conc"]["shake_C1_vs_C0"] = shc
    out["note"] = ("B0 = 💼 지금 규칙(추세 주차 포함, 월말 흐름 없음) · B1 = + 적용된 월말 흐름 · 🎯 = conc 목표 22%·한도 70% · "
                   "하루 늦은 체결 · 비용 0.1% · 레버리지 없음 · ETF 만 써서 생존 편향 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
