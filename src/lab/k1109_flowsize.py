"""📈 11/9 12시 — k1109_flowsize: 🔄 월말 흐름 「얼마나 옮기나 · 누구 쏠림을 재나」
  10시 계획(분기 말 크게)은 k1028_qflow 에서 이미 ❌(뒤 −0.8~−1.1) → 대신 아직 안 잰 두 갈래를 한 실험에:
  (A) 크기 비례: 지금은 쏠림이 ±0.5%p 만 넘으면 늘 60% 옮김 → 쏠림이 클수록 많이(f = 0.6 × |쏠림|/k, 0.3~1.0)
      — 연기금이 실제로 파는 양은 쏠림에 비례(NBER w33554 · EDHEC SSRN 5122748)
  (B) 쏠림 재는 자: SPY/IEF(지금) · SPY/TLT · SPY/AGG · 세계 주식(SPY½+EFA½)/IEF · ACWI/AGG
  틀 = k1109_portmenu(💼 t15·아래 0.3 · 추세 칸 주차) · 흐름 체결 = 지금 실제(s0_c1) 와 Q11/6-3 예약 종가(s1_c1) 둘 다
  앞 2008-07~2016 에서 고르고 뒤 2017~ 시험 · 고른 판 ±20% 흔들기 · 비용 0.1·0.25% · 해별
→ market/lab/k1109_flowsize.json
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
from k1028_qflow import rfe, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1109_flowsize.json")
A = math.sqrt(252) * 100


def drift60(S, B):
    """매달 1일 60/40 에서 시작해 그날까지 주식 비중 − 0.6 (벡터화)"""
    rs = S.pct_change().fillna(0.0); rb = B.pct_change().fillna(0.0)
    g = pd.Series(S.index.to_period("M"), index=S.index)
    cs = (1 + rs).groupby(g).cumprod(); cb = (1 + rb).groupby(g).cumprod()
    return 0.6 * cs / (0.6 * cs + 0.4 * cb) - 0.6


def make2(idx, D, K=5, th=0.005, f=0.6, k=None, lo=0.3, hi=1.0, lag=2):
    r = rfe(idx)
    d = D.shift(lag).fillna(0.0)
    w = r < K
    up = w & (d > th); dn = w & (d < -th)
    sig = pd.Series(0.0, index=idx); sig[up] = 1.0; sig[dn] = -1.0
    if k is None:
        fs = pd.Series(0.0, index=idx); fs[up | dn] = f
    else:
        fs = (f * d.abs() / k).clip(lower=lo, upper=hi).where(up | dn, 0.0)
    return sig, fs


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD", "EFA", "AGG", "ACWI"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    for x in ("IEF", "EFA", "AGG", "ACWI"):
        if x in px:
            C[x] = px.pop(x)["close"].reindex(C.index).ffill()
    O = {}
    for x in ["SPY", "QQQ", "GLD"]:
        O[x] = px.pop(x)
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
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * A
    sc = (15.0 / rv).clip(upper=1.0, lower=0.3).fillna(1.0)
    G, Rd = G_PORT, RD_PORT

    ON = pd.DataFrame(0.0, index=C.index, columns=KEYS); ID = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for kk, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ON[kk] = on; ID[kk] = (1 + cc) / (1 + on) - 1
    ID["TRD"] = C["TRD"].pct_change().fillna(0.0)

    eq_g = (C["SPY"].pct_change().fillna(0) * 0.5 + C["EFA"].pct_change().fillna(0) * 0.5).add(1).cumprod() if "EFA" in C else C["SPY"]
    SRC = {"spy_ief": (C["SPY"], C["IEF"]), "spy_tlt": (C["SPY"], C["TLT"])}
    if "AGG" in C:
        SRC["spy_agg"] = (C["SPY"], C["AGG"])
    if "EFA" in C:
        SRC["glob_ief"] = (eq_g, C["IEF"])
    if "ACWI" in C and "AGG" in C:
        SRC["acwi_agg"] = (C["ACWI"].bfill(), C["AGG"])
    DR = {k: drift60(a, b) for k, (a, b) in SRC.items()}

    # 쏠림 크기 분포(신호 난 날)
    d0 = DR["spy_ief"].shift(2).reindex(idx)
    trig = d0[(rfe(C.index).reindex(idx) < 5) & (d0.abs() > 0.005)].abs()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "drift_pct": {q: round(float(trig.quantile(q)) * 100, 2) for q in (0.25, 0.5, 0.75, 0.9)}}
    res = {}

    def sh(a, k):
        return a.shift(-k).fillna(0.0)

    def go(nm, src="spy_ief", s1=True, cost=0.001, **kw):
        sig, fs = make2(C.index, DR[src], **kw)
        if s1:
            sig, fs = sh(sig, 1), sh(fs, 1)
        nav, td = run(C, ON, ID, reg, idx, sc, sig, fs, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        r = nav.pct_change().dropna()
        vo = float(r[r.index >= OOS_START].std() * A)
        yr = {int(y): round(float((1 + g).prod() - 1) * 100, 2) for y, g in r.groupby(r.index.year)}
        res[nm] = {"is": a, "oos": b, "vol_oos": round(vo, 2), "yr": yr,
                   "favg": round(float(fs[fs > 0].mean()), 3) if (fs > 0).any() else 0}
        print(nm, a["cagr"], b["cagr"], b["mdd"], round(vo, 2), flush=True)
        return a, b

    go("none_s1", f=0.0)
    go("base_s0", s1=False)
    go("base_s1")
    # (B) 재는 자
    for src in SRC:
        if src != "spy_ief":
            go(f"src_{src}", src=src)
    # (A) 크기 비례
    for k in (0.0075, 0.01, 0.0125, 0.015, 0.02):
        go(f"size_k{k}", k=k)
    go("size_k0.01_lo0.6", k=0.01, lo=0.6)
    go("flat_f1.0", f=1.0)
    # 앞 구간에서 고르기(샤프 + 연수익/10) — 지금 판 제외
    cand = [n for n in res if n.startswith(("src_", "size_", "flat_"))]
    best = max(cand, key=lambda n: res[n]["is"]["sharpe"] + res[n]["is"]["cagr"] / 10)
    out["best"] = best
    # 흔들기 ±20% (고른 판 기준: f·th·K, 크기 판이면 k 도)
    bk = {}
    if best.startswith("size_"):
        bk["k"] = float(best.split("_k")[1].split("_")[0])
        if best.endswith("lo0.6"):
            bk["lo"] = 0.6
    elif best.startswith("flat_"):
        bk["f"] = 1.0
    bsrc = best[4:] if best.startswith("src_") else "spy_ief"
    shake = {}
    for nm, kw in {"f-20": {"f": 0.48}, "f+20": {"f": 0.72}, "th-20": {"th": 0.004}, "th+20": {"th": 0.006},
                   "K4": {"K": 4}, "K6": {"K": 6}}.items():
        kw2 = dict(bk); kw2.update(kw)
        if "f" in bk and "f" in kw:
            kw2["f"] = bk["f"] * (0.8 if nm == "f-20" else 1.2)
            kw2["f"] = min(kw2["f"], 1.0)
        a, b = go(f"shake_{nm}", src=bsrc, **kw2)
        base_kw = {}; base_kw.update(kw)
        a0, b0 = go(f"shakebase_{nm}", **base_kw)
        shake[nm] = {"best_is": a["cagr"], "best_oos": b["cagr"], "base_is": a0["cagr"], "base_oos": b0["cagr"],
                     "d_is": round(a["cagr"] - a0["cagr"], 2), "d_oos": round(b["cagr"] - b0["cagr"], 2)}
    if "k" in bk:
        for m, tag in ((0.8, "k-20"), (1.2, "k+20")):
            kw2 = dict(bk); kw2["k"] = bk["k"] * m
            a, b = go(f"shake_{tag}", **kw2)
            shake[tag] = {"best_is": a["cagr"], "best_oos": b["cagr"], "d_is": round(a["cagr"] - res["base_s1"]["is"]["cagr"], 2),
                          "d_oos": round(b["cagr"] - res["base_s1"]["oos"]["cagr"], 2)}
    out["shake"] = shake
    # 비용 0.25% · 지금 실제(s0) 체결로도
    go("best_c25", src=bsrc, cost=0.0025, **bk)
    go("base_s1_c25", cost=0.0025)
    go("best_s0", src=bsrc, s1=False, **bk)
    out["res"] = res
    b0 = res["base_s1"]
    out["vs_base_s1"] = {n: {"d_is": round(v["is"]["cagr"] - b0["is"]["cagr"], 2), "d_oos": round(v["oos"]["cagr"] - b0["oos"]["cagr"], 2),
                             "d_mdd_oos": round(v["oos"]["mdd"] - b0["oos"]["mdd"], 2), "d_vol_oos": round(v["vol_oos"] - b0["vol_oos"], 2),
                             "d_sh_oos": round(v["oos"]["sharpe"] - b0["oos"]["sharpe"], 3)}
                         for n, v in res.items() if not n.startswith("shake")}
    out["spy"] = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    out["note"] = "💼 t15 · 흐름 몫 상한 1.0(레버리지 없음) · ETF 만(생존 편향 없음) · ACWI 는 2008-03~ · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
