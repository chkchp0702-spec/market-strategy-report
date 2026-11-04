"""📈 11/4 16시 — 🎯 집중 포트 「언제 고쳐 담나」 — 회전 몫 줄이기 30여 판
  크기 산수: 🎯 100% · 뒤 회전 ≈1,104%/년 × 비용 0.1% ≈ 1.1%p/년 (실제 국내 증권사 해외 ETF 는 수수료+환전 ≈0.25% 면 2.8%p) → 통과
  바깥 재료: NBIM 「no-trade band」(밴드 끝까지만 사기) · Dimensional 「한 번에 vs 조금씩」 · arXiv 2212.07288 「Smoothing volatility targeting」
             (변동성 맞춤 비중을 부드럽게 해 회전을 줄임) · Newfound 리밸런스 시점 운 · 국내 「월·분기·밴드」 실측 글
  틀 = k1028_qflow.core_run 복사 + 손잡이:
      band(다시 맞추는 문턱) · monthly(월초 강제 다시 맞춤 켜/끔) · half(문턱 넘으면 목표까지 전부 vs 일부만) ·
      edge(밴드 끝까지만 — no-trade band) · smooth(변동성 비중 sc 를 N일 EMA) · step(sc 를 0.05·0.10 계단) · weekly(sc 를 주 1회만 갱신)
  국면·월말 흐름 신호는 그대로(신호가 바뀌는 날은 늘 다시 맞춤) · 하루 늦은 체결 · 비용 0.1%(판정) / 0.25%(참고)
  판정: 앞 2008-07~2016 에서 고르고 → 뒤 2017~ · ±20% 흔들기 · 같은 위험(앞 변동성 맞춘 목표) 판
  ETF 라 생존 편향 없음 · 레버리지 없음
→ market/lab/k1104_turn.json
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

OUT = Path("market/lab/k1104_turn.json")
G = {"SPY": .5, "QQQ": .5, "GLD": 0.0}
RD = {"SPY": .25, "QQQ": .25, "GLD": 0.0}
KEYS = ["SPY", "QQQ", "GLD", "TRD", "BND"]


def make_sc(rv, tgt=22.0, floor=0.70, smooth=0, step=0.0, weekly=False):
    sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
    if smooth:
        sc = sc.ewm(span=smooth, adjust=False).mean()
    if step:
        sc = (np.floor(sc / step + 1e-9) * step).clip(lower=floor, upper=1.0)
    if weekly:
        wk = pd.Series(sc.index.to_period("W"), index=sc.index)
        first = wk != wk.shift(1)
        sc = sc.where(first).ffill()
    return sc


def run(C, reg, idx, sc, sig, fs, band=0.05, monthly=True, half=1.0, edge=False, cost=0.001, bond="TLT"):
    Cx = C.copy(); Cx["BND"] = C[bond]
    R = Cx[KEYS].pct_change().fillna(0.0).values
    regv = reg.reindex(C.index).fillna(False).values.astype(bool)
    scv = sc.reindex(C.index).fillna(1.0).values
    sigv = sig.reindex(C.index).fillna(0.0).values
    fsv = fs.reindex(C.index).fillna(0.0).values
    months = C.index.month.values
    pos = {d: i for i, d in enumerate(C.index)}
    n = len(C.index)

    def tg(i, s_now, f):
        b = G if regv[i] else RD
        e = (b["SPY"] + b["QQQ"]) * scv[i]
        gl = b["GLD"]; trd = 1 - e - gl; bnd = 0.0
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and f > 0:
            e += (gl + trd) * f; gl *= (1 - f); trd *= (1 - f)
        return np.array([e / 2, e / 2, gl, trd, bnd])
    i0 = pos[idx[0]]
    w = tg(i0 - 1, 0.0, 0.0); last = w.copy(); lsig = 0.0
    rets = np.zeros(len(idx)); turns = np.zeros(len(idx))
    why = {"month": 0.0, "sig": 0.0, "reg": 0.0, "band": 0.0}
    for k, d in enumerate(idx):
        i = pos[d]
        r = float(w @ R[i])
        nw = w * (1 + R[i]); w = nw / nw.sum()
        j = i + 1
        snext = sigv[j] if j < n else 0.0
        fnext = fsv[j] if j < n else 0.0
        t = tg(i, snext, fnext)
        newm = j < n and months[j] != months[i]
        hard = snext != lsig or regv[i] != regv[i - 1]
        drift = np.abs(t - last).max() > band if not edge else np.abs(t - w).max() > band
        tv = 0.0
        if hard or (monthly and newm) or drift:
            if hard:
                nwt = t
            elif edge:      # 밴드 끝까지만: 각 칸을 목표 ±band 안으로만 끌어옴
                nwt = np.clip(w, t - band, t + band); nwt = nwt / nwt.sum()
            else:
                nwt = w + half * (t - w)
            tv = float(np.abs(nwt - w).sum() / 2)
            key = "sig" if snext != lsig else ("reg" if regv[i] != regv[i - 1] else ("month" if (monthly and newm) else "band"))
            why[key] += tv
            w = nwt; last = t.copy(); r -= tv * cost
        lsig = snext
        rets[k] = r; turns[k] = tv
    return (1 + pd.Series(rets, index=idx)).cumprod(), pd.Series(turns, index=idx), why


VARIANTS = {
    "base": {},
    "band03": dict(band=0.03), "band08": dict(band=0.08), "band10": dict(band=0.10), "band15": dict(band=0.15), "band20": dict(band=0.20),
    "noM": dict(monthly=False), "noM_band10": dict(monthly=False, band=0.10), "noM_band15": dict(monthly=False, band=0.15),
    "half50": dict(half=0.5), "half50_noM": dict(half=0.5, monthly=False),
    "edge05": dict(edge=True), "edge05_noM": dict(edge=True, monthly=False), "edge10_noM": dict(edge=True, monthly=False, band=0.10),
    "sm5": dict(smooth=5), "sm10": dict(smooth=10), "sm20": dict(smooth=20),
    "step05": dict(step=0.05), "step10": dict(step=0.10), "weekly": dict(weekly=True),
    "sm10_band10": dict(smooth=10, band=0.10), "sm10_noM": dict(smooth=10, monthly=False),
    "sm10_noM_band10": dict(smooth=10, monthly=False, band=0.10), "step10_noM": dict(step=0.10, monthly=False),
    "weekly_noM_band10": dict(weekly=True, monthly=False, band=0.10), "sm20_noM_band15": dict(smooth=20, monthly=False, band=0.15),
    "edge05_sm10_noM": dict(edge=True, smooth=10, monthly=False),
    "fixed_sc1": dict(fixed=True),   # 참고: 변동성 맞춤 없이(sc=1) — 회전 원천 확인용
}
SC_KEYS = ("smooth", "step", "weekly", "tgt", "floor")


def main():
    from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
    from k1011_size import load, seg
    from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
    from k1028_qflow import drifts, make
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
    sig, fs = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100

    def go(kw, cost=0.001):
        kw = dict(kw)
        if kw.pop("fixed", False):
            sc = pd.Series(1.0, index=C.index)
        else:
            sc = make_sc(rv, **{k: kw.pop(k) for k in list(kw) if k in SC_KEYS})
        nav, td, why = run(C, reg, idx, sc, sig, fs, cost=cost, **kw)
        tot = sum(why.values()) or 1
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "why": {k: round(v / tot * 100) for k, v in why.items()}, "eq": round(float(sc.reindex(idx).mean()) * 100, 1)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol", "turn")} for p in ("is", "oos")}

    def matched(kw, base, cost=0.001):
        lo, hi = 22.0 * 0.6, 22.0 * 1.5; best = None
        for _ in range(6):
            m = (lo + hi) / 2; r = go({**kw, "tgt": m}, cost)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}, "res": {}}
    for cost in (0.001, 0.0025):
        B = go({}, cost)
        res = {"base": B, "cands": {}}
        print(cost, "BASE", B["is"], B["oos"], B["why"], flush=True)
        for nm, kw in VARIANTS.items():
            if nm == "base":
                continue
            r = go(kw, cost)
            res["cands"][nm] = {"d": dlt(B, r), "is": r["is"], "oos": r["oos"], "why": r["why"], "eq": r["eq"]}
            print(cost, nm, res["cands"][nm]["d"]["is"], "|", res["cands"][nm]["d"]["oos"], flush=True)
        cc = {k: v for k, v in res["cands"].items() if k != "fixed_sc1"}
        pick = max(cc, key=lambda k: cc[k]["d"]["is"]["sharpe"] + cc[k]["d"]["is"]["cagr"] / 10)
        res["is_pick"] = pick
        if cost == 0.001:
            kw = VARIANTS[pick]
            mt, mr = matched(kw, B, cost)
            res["matched"] = {"tgt": mt, "d": dlt(B, mr)}
            print("MATCH", pick, mt, res["matched"]["d"], flush=True)
            sh = {}
            for p in ("band", "smooth", "half"):
                if p in kw:
                    for f_ in (0.8, 1.2):
                        k2 = dict(kw); v = kw[p] * f_
                        k2[p] = int(round(v)) if p == "smooth" else min(v, 1.0)
                        sh[f"{p}x{f_}"] = dlt(B, go(k2, cost))
            for nm2, extra in (("tgt-20", {"tgt": 22 * .8}), ("tgt+20", {"tgt": 22 * 1.2}), ("floor-20", {"floor": .56}), ("floor+20", {"floor": .84})):
                b0 = go(extra, cost); sh[nm2] = dlt(b0, go({**kw, **extra}, cost))
            res["shake"] = sh
            for k_, v_ in sh.items():
                print("SHAKE", k_, v_["is"], v_["oos"], flush=True)
        out["res"][f"c{int(cost * 10000)}"] = res
        print(cost, "PICK", pick, res["cands"][pick]["d"], flush=True)
    out["note"] = ("🎯 = 목표 22%·한도 70%·덜어낸 몫 🧭 추세 칸·월말 흐름(신호 바뀌는 날·국면 바뀌는 날은 늘 다시 맞춤) · "
                   "c10 = 비용 0.1%(판정) · c25 = 0.25%(국내 증권사 해외 ETF 수수료+환전 근사, 참고) · d = 기준 대비 차이 · why = 회전 원인 비율(%) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
