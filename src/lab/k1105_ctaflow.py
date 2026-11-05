"""📈 11/5 10시 — 🤖 「추세 추종 펀드(CTA)가 억지로 판 뒤」 — 🎯 100% 칸에 월말 흐름과 같은 틀로 얹는 두 번째 「강제 흐름」 신호
  발상: Macrosynergy 「Estimating the positioning of trend followers」 · Goldman/UBS/BofA CTA 흐름 추정 리포트(2026 「어떤 경우에도 매도」 류)
  CTA 위치 추정 = S&P(SPY) 20·60·125·250일 수익을 60일 변동성으로 나눈 z 의 tanh 평균(−1~+1) · 흐름 F = 위치 − W일 전 위치
  가족: fade(크게 판 뒤 주식 더하기 / 크게 산 뒤 TLT 로 덜기) · fadeDn(판 뒤 더하기만) · follow(판 때 같이 덜기)
  W 5·10·20 · 문턱 th 0.3·0.5·0.8 · 옮기는 몫 f 0.6(월말 흐름과 같음) · 월말 흐름 신호가 켜진 날은 그것 먼저
  + B) 월말 흐름의 「옮길 곳」 TLT 대신 IEF · 현금(BIL) · GLD · TLT½+BIL½
  크기 산수: 🎯 100% × (월말 흐름이 낸 값 +2.3%p 와 같은 종류) → 상한 ≈1~2%p 통과 · B) 흐름 날 평균 비중 ≈14% × 옮길 곳 차 ≈3%p ≈0.4%p
  틀 = k1104_turn.run · 앞 2008-07~2016 고르고 뒤 2017~ · 비용 0.1%(판정)·0.25%(참고) · 앞 1등 ±20% 흔들기 · 같은 앞 변동성 맞춤(목표 이분 탐색)
→ market/lab/k1105_ctaflow.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from k1104_turn import run, make_sc

OUT = Path("market/lab/k1105_ctaflow.json")


def cta_pos(p: pd.Series, L=(20, 60, 125, 250)):
    lr = np.log(p).diff()
    sd = lr.rolling(60).std()
    zs = [np.tanh((np.log(p / p.shift(l))) / (sd * math.sqrt(l))) for l in L]
    return pd.concat(zs, axis=1).mean(axis=1)


def cta_sig(pos, mode, W, th, f=0.6, Lscale=1.0):
    F = pos - pos.shift(W)
    s = pd.Series(0.0, index=pos.index)
    if mode == "fade":
        s[F < -th] = -1.0; s[F > th] = 1.0
    elif mode == "fadeDn":
        s[F < -th] = -1.0
    elif mode == "follow":
        s[F < -th] = 1.0
    s = s.shift(1).fillna(0.0)          # 오늘 종가로 정하고 다음 날 반영(run 이 j=i+1 신호로 목표를 정함 → 안전하게 하루 더)
    return s, (s != 0).astype(float) * f


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
    C["TLTBIL"] = (1 + 0.5 * C["TLT"].pct_change().fillna(0) + 0.5 * C["BIL"].pct_change().fillna(0)).cumprod()
    DM, DQ = drifts(C)
    msig, mfs = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    pos = cta_pos(C["SPY"])

    def combo(cs, cf):
        sig = msig.where(msig != 0, cs); fs = mfs.where(msig != 0, cf)
        return sig, fs

    def go(kw, cost=0.001, tgt=22.0, floor=0.70):
        kw = dict(kw); bond = kw.pop("bond", "TLT")
        if "mode" in kw:
            cs, cf = cta_sig(pos, kw["mode"], kw["W"], kw["th"], kw.get("f", 0.6))
            sig, fs = combo(cs, cf)
        else:
            sig, fs = msig, mfs
        sc = make_sc(rv, tgt=tgt, floor=floor)
        nav, td, _ = run(C, reg, idx, sc, sig, fs, cost=cost, bond=bond)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        if "mode" in kw:
            on = (cs.reindex(idx) != 0)
            o["on_is"] = round(float(on[idx <= pd.Timestamp(IS_END)].mean()) * 100, 1)
            o["on_oos"] = round(float(on[idx >= pd.Timestamp(OOS_START)].mean()) * 100, 1)
        return o

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol", "turn")} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "cta": {}, "dest": {}}
    B = go({}); out["base"] = B
    print("BASE", B["is"], B["oos"], flush=True)
    VAR = {}
    for mode in ("fade", "fadeDn", "follow"):
        for W in (5, 10, 20):
            for th in (0.3, 0.5, 0.8):
                VAR[f"{mode}_W{W}_t{int(th * 10)}"] = dict(mode=mode, W=W, th=th)
    for nm, kw in VAR.items():
        r = go(kw); out["cta"][nm] = {"d": dlt(B, r), "on_is": r.get("on_is"), "on_oos": r.get("on_oos")}
        print(nm, r.get("on_is"), r.get("on_oos"), out["cta"][nm]["d"]["is"], "|", out["cta"][nm]["d"]["oos"], flush=True)
    cc = out["cta"]
    pick = max(cc, key=lambda k: cc[k]["d"]["is"]["sharpe"] + cc[k]["d"]["is"]["cagr"] / 10)
    out["pick"] = pick; P = VAR[pick]
    print("PICK", pick, cc[pick]["d"], flush=True)
    # 같은 앞 변동성: 목표 tgt 이분 탐색
    lo, hi = 14.0, 32.0; bv = B["is"]["vol"]
    if abs(go(P)["is"]["vol"] - bv) < 0.1:
        lo = hi = 22.0
    for _ in range(9 if lo != hi else 0):
        m = (lo + hi) / 2; r = go(P, tgt=m)
        if r["is"]["vol"] > bv: hi = m
        else: lo = m
    tm = round((lo + hi) / 2, 2); rr = go(P, tgt=tm)
    out["same_risk"] = {"tgt": tm, "d": dlt(B, rr)}
    print("SAMERISK", tm, out["same_risk"]["d"], flush=True)
    # 흔들기 ±20% (W·th·f)
    sh = {}
    for nm2, ch in (("W-20", dict(W=max(2, round(P["W"] * 0.8)))), ("W+20", dict(W=round(P["W"] * 1.2))),
                    ("th-20", dict(th=P["th"] * 0.8)), ("th+20", dict(th=P["th"] * 1.2)),
                    ("f-20", dict(f=0.48)), ("f+20", dict(f=0.72))):
        kw = dict(P); kw.update(ch); sh[nm2] = dlt(B, go(kw))
        print("SHAKE", nm2, sh[nm2]["is"], sh[nm2]["oos"], flush=True)
    out["shake"] = sh
    # 비용 0.25% 참고
    B25 = go({}, cost=0.0025); out["c25"] = dlt(B25, go(P, cost=0.0025))
    print("C25", out["c25"], flush=True)
    # B) 옮길 곳
    for bnd in ("IEF", "BIL", "GLD", "TLTBIL"):
        out["dest"][bnd] = dlt(B, go({"bond": bnd}))
        print("DEST", bnd, out["dest"][bnd]["is"], "|", out["dest"][bnd]["oos"], flush=True)
    out["note"] = "🎯 목표 22·한도 70·월말 흐름 켜진 지금 규칙 대비 d · 비용 0.1% · ETF 만 → 생존 편향 없음 · CTA 위치는 SPY 하나로 근사(실제 CTA 는 선물·여러 시장) · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
