"""📈 11/5 12시 — 🎯 에 「두 번째 억지 리밸런싱 = 띠 이탈(threshold) 리밸런서」 얹기
  발상: Harvey·Mazzoleni·Melone 「The Unintended Consequences of Rebalancing」 2026-03 EDHEC 판(SSRN 5122748)
    60/40 펀드 리밸런싱은 ① 달력(월말) ② 띠 이탈(주식 비중이 60% ± δ 를 벗어나면 그때 맞춤) 두 갈래 · 둘 다 함께 넣어도 유의
    (띠 신호 1SD → 다음 날 주식 −16bp·채권 +4bp · t>4 · 예측력 δ≈2%p 근처 최고 · 효과는 4일째 바닥, 9일 뒤 사라짐 · 분기 마지막 달 가장 셈)
  우리 쪽: 🎯 에는 ① 달력(월말 흐름 K5·±0.5%p·60%·TLT)만 적용 중(Q10/28-3 ✅) · ② 띠 이탈은 10/28 💼 위에서 같은 날 종가 체결로만 잼(뒤 +0.4~0.85)
           → 🎯 위에서, 월말 흐름과 함께, 하루 늦은 체결(lag 2)로는 처음.
  크기 산수: 🎯 100% × (띠 신호 날 ≈11번/년 × 옮김 0.6 × 주식−채권 ≈30bp/일 × H일) − 회전 비용 ≈ 0.6~1.5%p → 통과
  신호(그저께 종가까지):
    band δ  — SPY·IEF 60/40 을 날마다 굴리다 주식 비중이 0.6±δ 를 벗어난 날 그 펀드가 리밸런싱(0.6 으로 되돌림)
              → 이탈 날 d 다음 체결 가능 날부터 H 거래일 동안 반대 쪽(넘침 → 주식 칸 f 를 TLT · 모자람 → 추세·현금 칸 f 를 주식)
    avg     — 논문식: δ 0~2.5%p(0.1 간격) 펀드 26개의 「그날 맞출 양」 평균(연속값) · |평균| > th 면 신호
  월말 흐름이 켜진 날은 월말 흐름이 먼저(같은 칸) · 국면·변동성 맞춤 그대로 · 비용 0.1%(+0.25% 판) · 레버리지 없음
  판정: 앞 2008-07~16 에서 고르고(샤프+연수익/10) 뒤 2017~ 시험 · 같은 위험(앞 변동성 맞춘 목표) · ±20% 흔들기 · 해마다
→ market/lab/k1105_thrflow.json
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
import k1028_qflow as QF
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC

OUT = Path("market/lab/k1105_thrflow.json")


def band_events(S, B, d):
    """60/40 띠 이탈 리밸런서: 돌려줌 ev(+1 넘침 리밸런싱 날 / −1 모자람 / 0), dev(그날 맞출 양)"""
    s = S.values; b = B.values
    n = len(s); ev = np.zeros(n); dev = np.zeros(n)
    ws, wb = 0.6, 0.4
    for i in range(n):
        ws *= 1 + s[i]; wb *= 1 + b[i]
        w = ws / (ws + wb) - 0.6
        if abs(w) > d:
            ev[i] = 1.0 if w > 0 else -1.0; dev[i] = w
            ws, wb = 0.6, 0.4
            tot = 1.0
            ws, wb = 0.6 * tot, 0.4 * tot
    return ev, dev


def thr_signal(C, kind, d=0.02, H=3, th=0.005, lag=2):
    S = C["SPY"].pct_change().fillna(0.0); B = C["IEF"].pct_change().fillna(0.0)
    idx = C.index
    if kind == "band":
        ev, _ = band_events(S, B, d)
        e = pd.Series(ev, index=idx)
    else:   # avg — 논문식 연속 신호
        tot = np.zeros(len(idx))
        for dd in np.arange(0.0, 0.0251, 0.001):
            _, dv = band_events(S, B, dd)
            tot += dv
        a = pd.Series(tot / 26.0, index=idx)
        e = pd.Series(np.where(a > th, 1.0, np.where(a < -th, -1.0, 0.0)), index=idx)
    e = e.shift(lag).fillna(0.0)          # 그저께 종가까지 → sig[j] (j 날 보유)
    sig = pd.Series(0.0, index=idx)
    for h in range(H):                     # 이탈 뒤 H 거래일 지속(겹치면 나중 것)
        sh = e.shift(h).fillna(0.0)
        sig = sig.where(sh == 0, sh)
    return sig


def combine(sigM, fsM, sigT, f):
    sig = sigM.copy(); fs = fsM.copy()
    m = (sigM == 0) & (sigT != 0)
    sig[m] = sigT[m]; fs[m] = f
    return sig, fs


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

    def go(sig, fs, tgt=22.0, floor=0.70, cost=0.001):
        QF.COST = cost
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, sig, fs, G_CONC, RD_CONC)
        return nav, td

    def st(nav, td):
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    def yearly(n0, n1):
        o = {}
        for y in range(2017, idx[-1].year + 1):
            a = n0[n0.index.year == y]; b = n1[n1.index.year == y]
            if len(a) > 5:
                o[str(y)] = round(float((b.iloc[-1] / b.iloc[0] - a.iloc[-1] / a.iloc[0]) * 100), 2)
        return o

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "src": "Harvey·Mazzoleni·Melone, The Unintended Consequences of Rebalancing (EDHEC/SSRN 5122748, 2026-03 판)"}
    # 0) 맞대기: 띠 신호 날 (−sig) × (SPY − TLT) bp (월말 창 밖만)
    r_ls = (C["SPY"].pct_change() - C["TLT"].pct_change()).fillna(0.0)
    ls = {}
    for d in (0.01, 0.015, 0.02, 0.025):
        for H in (1, 2, 3, 5):
            sg = thr_signal(C, "band", d=d, H=H)
            m0 = (sg != 0) & (sigM == 0)
            row = {}
            for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
                m = m0 & (sg.index >= a) & (sg.index <= b)
                x = (-sg[m] * r_ls[m]) * 1e4
                row[p] = {"n": int(len(x)), "bp": round(float(x.mean()), 1) if len(x) else None,
                          "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2) if len(x) > 5 else None}
            ls[f"b{d}_H{H}"] = row
    out["ls"] = ls
    print("LS", json.dumps(ls), flush=True)

    n0, t0 = go(sigM, fsM); B0 = st(n0, t0)
    nC, tC = go(sigM * 0, fsM * 0); out["no_flow"] = dlt(B0, st(nC, tC))
    out["base"] = B0
    print("BASE", B0, flush=True)
    grid = {}
    cands = {}
    for d in (0.01, 0.015, 0.02, 0.025):
        for H in (2, 3, 5):
            for f in (0.3, 0.6):
                cands[f"band_d{d}_H{H}_f{f}"] = dict(kind="band", d=d, H=H, f=f)
    for th in (0.005, 0.01):
        for H in (2, 3):
            cands[f"avg_th{th}_H{H}_f0.6"] = dict(kind="avg", th=th, H=H, f=0.6)
    sig_cache = {}
    for nm, kw in cands.items():
        key = (kw["kind"], kw.get("d"), kw.get("th"), kw["H"])
        if key not in sig_cache:
            sig_cache[key] = thr_signal(C, kw["kind"], d=kw.get("d", 0.02), H=kw["H"], th=kw.get("th", 0.005))
        sg, fs = combine(sigM, fsM, sig_cache[key], kw["f"])
        n1, t1 = go(sg, fs)
        R1 = st(n1, t1)
        grid[nm] = {"d": dlt(B0, R1), "turn": [R1["is"].get("turn"), R1["oos"].get("turn")],
                    "on_days": int((sig_cache[key] != 0).sum())}
        print(nm, grid[nm], flush=True)
    out["grid"] = grid
    pick = max(grid, key=lambda k: grid[k]["d"]["is"]["sharpe"] + grid[k]["d"]["is"]["cagr"] / 10)
    out["is_pick"] = pick
    kw = cands[pick]
    out["oos_pos"] = sum(1 for k in grid if grid[k]["d"]["oos"]["cagr"] > 0)
    out["oos_med"] = round(float(np.median([grid[k]["d"]["oos"]["cagr"] for k in grid])), 2)
    out["is_pos"] = sum(1 for k in grid if grid[k]["d"]["is"]["cagr"] > 0)

    def run_pick(kw, cost=0.001, tgt=22.0, floor=0.70):
        sgT = thr_signal(C, kw["kind"], d=kw.get("d", 0.02), H=kw["H"], th=kw.get("th", 0.005))
        sg, fs = combine(sigM, fsM, sgT, kw["f"])
        return go(sg, fs, tgt=tgt, floor=floor, cost=cost)

    n1, t1 = run_pick(kw); P = st(n1, t1)
    out["pick"] = {"raw": dlt(B0, P), "is": P["is"], "oos": P["oos"], "yr": yearly(n0, n1)}
    # 같은 위험: 앞 변동성 맞춘 목표
    lo, hi = 14.0, 30.0; best = None
    for _ in range(6):
        m = (lo + hi) / 2; nm_, tm_ = run_pick(kw, tgt=m); Rm = st(nm_, tm_)
        if best is None or abs(Rm["is"]["vol"] - B0["is"]["vol"]) < abs(best[1]["is"]["vol"] - B0["is"]["vol"]):
            best = (m, Rm)
        if Rm["is"]["vol"] > B0["is"]["vol"]:
            hi = m
        else:
            lo = m
    out["pick"]["matched_tgt"] = round(best[0], 2); out["pick"]["matched"] = dlt(B0, best[1])
    # 비용 0.25%
    nb, tb = go(sigM, fsM, cost=0.0025); Bc = st(nb, tb)
    nc, tc = run_pick(kw, cost=0.0025); out["pick"]["cost25"] = dlt(Bc, st(nc, tc))
    # 흔들기 ±20%
    sh = {}
    vars_ = {"f-20": dict(f=kw["f"] * 0.8), "f+20": dict(f=kw["f"] * 1.2)}
    if kw["kind"] == "band":
        vars_.update({"d-20": dict(d=round(kw["d"] * 0.8, 4)), "d+20": dict(d=round(kw["d"] * 1.2, 4)),
                      "H-1": dict(H=max(1, kw["H"] - 1)), "H+1": dict(H=kw["H"] + 1)})
    else:
        vars_.update({"th-20": dict(th=kw["th"] * 0.8), "th+20": dict(th=kw["th"] * 1.2)})
    for vn, ch in vars_.items():
        k2 = dict(kw); k2.update(ch)
        n2, t2 = run_pick(k2); sh[vn] = dlt(B0, st(n2, t2))
        print("SHAKE", vn, sh[vn], flush=True)
    for vn, kk in {"tgt-20": dict(tgt=22 * .8), "tgt+20": dict(tgt=22 * 1.2)}.items():
        nb2, tb2 = go(sigM, fsM, tgt=kk["tgt"]); b2 = st(nb2, tb2)
        n2, t2 = run_pick(kw, tgt=kk["tgt"]); sh[vn] = dlt(b2, st(n2, t2))
    out["shake"] = sh
    oos = out["pick"]["matched"]["oos"]["cagr"]; isd = out["pick"]["matched"]["is"]["cagr"]
    ok_shake = all(v["oos"]["cagr"] > 0 for v in sh.values())
    out["judge"] = {"is_ge0": isd >= 0, "oos_matched": oos, "shake_ok": ok_shake,
                    "verdict": "✅" if (oos > 1.0 and isd >= 0 and ok_shake) else ("🟡" if (oos >= 0.33 and isd >= 0) else "❌")}
    print("PICK", pick, out["pick"], out["judge"], flush=True)
    out["note"] = ("기준 = 지금 🎯(국면·변동성 맞춤 22%/70%·🧭 추세 칸·월말 흐름) · 띠 신호는 월말 흐름 없는 날만 · 하루 늦은 체결(lag 2) · "
                   "ETF 만, 생존 편향 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
