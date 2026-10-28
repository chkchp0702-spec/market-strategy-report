"""📈 10/28 14시 수익률 전략 — 🔄 「연기금·60/40 펀드의 억지 리밸런싱 앞지르기」
  발상: Harvey·Mazzoleni·Melone 「The Unintended Consequences of Rebalancing」(NBER w33554, 2025)
    60/40 펀드들은 주식이 채권보다 많이 올라 비중이 넘치면(달 마지막 주 · 또는 비중이 띠를 벗어난 날) 주식을 팔고 채권을 삼
    → 그 다음 날 「주식 − 채권」 수익이 약 17bp 낮아짐(2주 안에 사라짐) · 모멘텀·VIX 등을 넣어도 그대로
  우리 쪽 적용: 지금 실제 💼(B0 = C안 뼈대 + 변동성 맞춤 + 덜어낸 현금 → 🧭 추세 칸, Q10/28-1 포함) 위에
    신호 날 = 주식 칸의 f 만큼을 채권 ETF(IEF/TLT)로 잠깐 옮김 (반대 신호면 sym=True 일 때 금·추세 칸 f 만큼을 주식으로)
  신호(전날 종가까지만):
    cal  — 그 달 마지막 K 거래일 동안, 이번 달 SPY·IEF 수익으로 셈한 60/40 주식 비중 쏠림이 +th 넘으면 → 채권 쪽
    thr  — 날마다 60/40 을 따라가다 주식 비중이 60±b 를 벗어난 날(그날 리밸런싱) → 다음 H 거래일 반대 쪽
  먼저 「주식 − 채권」 맞대기(롱숏) 순수 성적으로 메커니즘이 우리 자료에서도 있는지 확인(앞·뒤)
  판정: 앞(2008-07~2016)에서 고르고 뒤(2017~)에서 시험 · 흔들기 ±20% · 회전 × 0.1% · 레버리지 없음(비중 합 1)
→ market/lab/k1028_rebalflow.json
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
from k1011_size import load, seg, COST
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U

OUT = Path("market/lab/k1028_rebalflow.json")


def signals(C, kind, K=5, th=0.005, b=0.02, H=2):
    """+1 = 주식 넘침(펀드가 주식 팖 → 채권 쪽) · −1 = 주식 모자람 · 값은 「그날 들고 있을 방향」(전날 종가까지로 정함)"""
    S = C["SPY"].pct_change().fillna(0.0)
    B = C["IEF"].pct_change().fillna(0.0)
    idx = C.index
    out = pd.Series(0.0, index=idx)
    if kind == "cal":
        mon = pd.Series(idx.month, index=idx)
        # 그 달 마지막 K 거래일 표시(거래 달력은 미리 앎)
        rank_from_end = mon.groupby((mon != mon.shift()).cumsum()).cumcount(ascending=False)
        lastK = rank_from_end < K
        ws = wb = None
        drift = pd.Series(0.0, index=idx)
        for i, d in enumerate(idx):
            if i == 0 or idx[i - 1].month != d.month:
                ws, wb = 0.6, 0.4
            ws *= 1 + S.iloc[i]; wb *= 1 + B.iloc[i]
            drift.iloc[i] = ws / (ws + wb) - 0.6
        prev = drift.shift(1).fillna(0.0)
        # 달 첫날의 prev 는 지난달 쏠림 → 달 마지막 K 일 안에서만 쓰므로 문제 없음(K < 달 길이)
        out[lastK & (prev > th)] = 1.0
        out[lastK & (prev < -th)] = -1.0
    else:
        w = 0.6
        ev = pd.Series(0.0, index=idx)
        for i in range(1, len(idx)):
            s, bb = w * (1 + S.iloc[i]), (1 - w) * (1 + B.iloc[i])
            w = s / (s + bb)
            if w - 0.6 > b:
                ev.iloc[i] = 1.0; w = 0.6
            elif w - 0.6 < -b:
                ev.iloc[i] = -1.0; w = 0.6
        for h in range(1, H + 1):
            sh = ev.shift(h).fillna(0.0)
            out = out.where(out != 0, sh)
    return out


def ls_edge(C, sig, a, b):
    """맞대기: 신호 날 −sig × (SPY − IEF) 일 수익(bp)"""
    r = (C["SPY"].pct_change() - C["IEF"].pct_change()).fillna(0.0)
    m = (sig.index >= a) & (sig.index <= b) & (sig != 0)
    x = (-sig[m] * r[m]) * 1e4
    if len(x) < 5:
        return {"n": int(len(x))}
    return {"n": int(len(x)), "bp": round(float(x.mean()), 1), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2),
            "hit": round(float((x > 0).mean()) * 100), "yr_bp": round(float(x.sum()) / ((pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25), 0)}


def core_run(C, reg, idx, sc, sig, f=0.0, bond="IEF", sym=False, band=0.05):
    G = {"SPY": .475, "QQQ": .475, "GLD": .05}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    keys = ["SPY", "QQQ", "GLD", "TRD", "BND"]
    Cx = C.copy(); Cx["BND"] = C[bond]
    R = Cx[keys].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i, s_now):
        b = G if bool(regv.iloc[i]) else Rd
        s = float(sc.iloc[i])
        e = (b["SPY"] + b["QQQ"]) * s
        gl = b["GLD"]
        trd = 1 - e - gl
        bnd = 0.0
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and sym and f > 0:
            mv = (gl + trd) * f
            e += mv; gl *= (1 - f); trd *= (1 - f)
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": gl, "TRD": trd, "BND": bnd}
    w, last, lsig = None, None, 0.0
    rets, turns = [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1, 0.0); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        # 다음 날 들고 있을 것: 다음 날 신호(전날=오늘 종가까지로 정해짐)
        j = i + 1
        snext = float(sig.iloc[j]) if j < len(sig) else 0.0
        t = tg(i, snext)
        newm = j < len(C.index) and C.index[j].month != d.month
        tv = 0.0
        if newm or snext != lsig or regv.iloc[i] != regv.iloc[i - 1] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t)
            r -= tv * COST
        lsig = snext
        rets.append(r); turns.append(tv)
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx)


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
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    SIG = {}

    def gsig(kind, **kw):
        k = (kind, tuple(sorted(kw.items())))
        if k not in SIG:
            SIG[k] = signals(C, kind, **kw)
        return SIG[k]

    def go(kind="cal", skw=None, f=0.0, bond="IEF", sym=False, tgt=15.0, floor=0.30):
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        sig = gsig(kind, **(skw or {}))
        nav, td = core_run(C, reg, idx, sc, sig, f, bond, sym)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "days_on": round(float((sig.reindex(idx) != 0).mean()) * 100, 1)}

    def dlt(a, b):
        return {p: {"cagr": round(b[p]["cagr"] - a[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - a[p]["mdd"], 2),
                    "sharpe": round(b[p]["sharpe"] - a[p]["sharpe"], 2)} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "src": "Harvey·Mazzoleni·Melone, The Unintended Consequences of Rebalancing (NBER w33554, 2025)",
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}
    # 1) 메커니즘 확인: 맞대기 순수 성적
    ls = {}
    for nm, (kind, kw) in {"cal_K5_th0.5": ("cal", dict(K=5, th=0.005)), "cal_K3_th0.5": ("cal", dict(K=3, th=0.005)),
                           "cal_K5_th1.0": ("cal", dict(K=5, th=0.010)), "thr_b2_H1": ("thr", dict(b=0.02, H=1)),
                           "thr_b2_H2": ("thr", dict(b=0.02, H=2)), "thr_b1_H1": ("thr", dict(b=0.01, H=1)),
                           "thr_b3_H2": ("thr", dict(b=0.03, H=2))}.items():
        sg = gsig(kind, **kw)
        ls[nm] = {"is": ls_edge(C, sg, START, IS_END), "oos": ls_edge(C, sg, OOS_START, END), "pre2008": ls_edge(C, sg, "2006-03-01", "2008-06-30")}
        print("LS", nm, ls[nm], flush=True)
    out["ls_edge"] = ls
    # 2) 💼 위에 얹기
    B0 = go(f=0.0); out["B0_now"] = B0
    print("B0", B0["is"], "|", B0["oos"], flush=True)
    grid = {}
    for kind, kw in (("cal", dict(K=5, th=0.005)), ("cal", dict(K=3, th=0.005)), ("thr", dict(b=0.02, H=2)), ("thr", dict(b=0.01, H=1))):
        for f in (0.3, 0.6):
            for bond in ("IEF", "TLT"):
                for sym in (False, True):
                    nm = f"{kind}_{'_'.join(f'{k}{v}' for k, v in kw.items())}_f{f}_{bond}_{'sym' if sym else 'one'}"
                    o = go(kind, kw, f, bond, sym); o["d"] = dlt(B0, o); o["kw"] = dict(kind=kind, skw=kw, f=f, bond=bond, sym=sym)
                    grid[nm] = o
                    print(nm, o["d"], o["days_on"], flush=True)
    out["grid"] = {k: {kk: vv for kk, vv in v.items()} for k, v in grid.items()}
    best = max(grid, key=lambda k: (grid[k]["is"]["sharpe"], grid[k]["is"]["cagr"]))
    BK = grid[best]["kw"]; BUN = grid[best]
    out["is_pick"] = best
    print("앞 구간으로 고른", best, BUN["d"], flush=True)
    # 3) 흔들기
    sh = {}
    kind, skw, f = BK["kind"], BK["skw"], BK["f"]
    var = [("f×0.8", dict(f=round(f * 0.8, 3))), ("f×1.2", dict(f=round(f * 1.2, 3)))]
    if kind == "cal":
        var += [("th×0.8", dict(skw={**skw, "th": skw["th"] * 0.8})), ("th×1.2", dict(skw={**skw, "th": skw["th"] * 1.2})),
                ("K-1", dict(skw={**skw, "K": skw["K"] - 1})), ("K+1", dict(skw={**skw, "K": skw["K"] + 1}))]
    else:
        var += [("b×0.8", dict(skw={**skw, "b": skw["b"] * 0.8})), ("b×1.2", dict(skw={**skw, "b": skw["b"] * 1.2})),
                ("H+1", dict(skw={**skw, "H": skw["H"] + 1}))]
    for nm, kw in var:
        b = go(**{**BK, **kw}); sh[nm] = dlt(B0, b)
        print("흔들기", nm, sh[nm], flush=True)
    for nm, kw in {"tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0), "floor24": dict(floor=0.24), "floor36": dict(floor=0.36)}.items():
        a = go(**kw); b = go(**{**BK, **kw}); sh[nm] = dlt(a, b)
        print("흔들기", nm, sh[nm], flush=True)
    out["shake"] = sh
    d = BUN["d"]
    shake_ok = all(v["is"]["cagr"] > 0 and v["oos"]["cagr"] > 0 for v in sh.values())
    big = d["is"]["cagr"] >= 1.0 and d["oos"]["cagr"] >= 1.0
    mdd3 = all(BUN[p]["mdd"] >= B0[p]["mdd"] * (2 / 3) for p in ("is", "oos"))
    out["judge"] = {"pick": best, "d": d, "shake_ok": shake_ok, "size_cagr": big, "size_mdd_third": mdd3,
                    "verdict": "✅ 통과" if (big or mdd3) and shake_ok else
                    ("🟡 근접" if shake_ok and d["is"]["cagr"] > 0 and d["oos"]["cagr"] > 0 else "❌")}
    print("JUDGE", out["judge"], flush=True)
    out["note"] = "B0 = 지금 실제 💼(추세 주차 포함) · 킥 없음 · 레버리지 없음 · 지수 ETF 만 써서 생존 편향 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
