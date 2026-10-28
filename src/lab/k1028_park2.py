"""📈 10/28 12시 수익률 전략 — 이미 ✅ 적용된 「덜어낸 현금 → 🧭 자산 추세 칸 주차」(Q10/28-1) 위에 얹을 둘째 재료 찾기
  새 기준(B0) = 지금 실제 💼: C안 뼈대(S&P 47.5·나스닥 47.5·금 5 / 하락 국면 31.5·31.5·금 11·현금 26) + 변동성 맞춤(목표 15%·아래 한도 30%)
               + 현금 몫 전부 → 🧭 자산 추세 9종(100일 고가 돌파·50일 저가 이탈·변동성 반비례)
  재료:
   T1 주차 칸 기울이기 — 추세 칸을 9종 대신 「위기 때 버는 칸」만(TLT·GLD·UUP) / 5종(TLT·GLD·UUP·DBC·USO, 주식 ETF 빼기)
   T2 금 5%(하락 국면 11%) 고정 칸 → 그 몫도 추세 칸(금은 추세 칸 안에서 신호 날 때만)
   T3 주식 칸의 x%(5·10·15%)를 늘 추세 칸에 (변동성 맞춤은 남은 주식 칸에만)
  판정: 각 재료를 B0 위에 따로 → 앞(2008-07~2016)·뒤(2017~) 모두 플러스인 것만 묶어서 함께 다시(함께 돌린 숫자로)
  흔들기(±20%): 목표 12/18 · 아래 한도 24/36% · 추세 80/40 · 120/60
  전날 종가까지 판단 → 다음 날 체결 · 기본 칸 회전 × 0.1% · 추세 칸 안 사고팔기 왕복 0.5% · 레버리지 없음(비중 합 1)
  🎯 집중(목표 22%·한도 70%, 금 없음)도 같은 재료로 참고
→ market/lab/k1028_park2.json
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

OUT = Path("market/lab/k1028_park2.json")
SETS = {"all9": TREND_U, "def3": ["TLT", "GLD", "UUP"], "nostk5": ["TLT", "GLD", "UUP", "DBC", "USO"]}


def core_run(C, reg, idx, sc, base, gold2trd=False, perm=0.0, band=0.05):
    if base == "port":
        G = {"SPY": .475, "QQQ": .475, "GLD": .05}
        Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    else:
        G = {"SPY": .5, "QQQ": .5, "GLD": 0.0}
        Rd = {"SPY": .25, "QQQ": .25, "GLD": 0.0}
    keys = ["SPY", "QQQ", "GLD", "TRD"]
    R = C[keys].pct_change().fillna(0.0)
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i):
        b = G if bool(regv.iloc[i]) else Rd
        s = float(sc.iloc[i])
        eq0 = (b["SPY"] + b["QQQ"]) * (1 - perm)
        e = eq0 * s
        gl = 0.0 if gold2trd else b["GLD"]
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": gl, "TRD": 1 - e - gl}
    w, last = None, None
    rets, turns, tw = [], [], []
    for d in idx:
        i = pos_i[d]
        if w is None:
            w = tg(i - 1); last = dict(w)
        r = sum(w[k] * R.at[d, k] for k in w)
        nw = {k: w[k] * (1 + R.at[d, k]) for k in w}
        s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        t = tg(i - 1)
        newm = C.index[i - 1].month != d.month
        tv = 0.0
        if newm or regv.iloc[i - 1] != regv.iloc[i - 2] or max(abs(t[k] - last[k]) for k in t) > band:
            tv = sum(abs(t[k] - w[k]) for k in w) / 2
            w = dict(t); last = dict(t)
            r -= tv * COST
        rets.append(r); turns.append(tv); tw.append(w["TRD"])
    rs = pd.Series(rets, index=idx)
    return (1 + rs).cumprod(), pd.Series(turns, index=idx), pd.Series(tw, index=idx)


def main():
    C = load()
    px = ydl(["^IRX"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    TRN = {}

    def tnav(sset, nin, nout):
        k = (sset, nin, nout)
        if k not in TRN:
            sub = {s: px[s] for s in SETS[sset] if s in px}
            s, _, _ = trend_run(sub, cdl, nin, nout, "risk", start=str(common.date()))
            TRN[k] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
        return TRN[k]

    def go(base="port", tgt=15.0, floor=0.30, sset="all9", gold2trd=False, perm=0.0, tr=(100, 50)):
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        Cx = C.copy(); Cx["TRD"] = tnav(sset, *tr)
        nav, td, tw = core_run(Cx, reg, idx, sc, base, gold2trd, perm)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
             "trd_avg": round(float(tw.mean()) * 100, 1)}
        yr = {}
        for y in range(2009, idx[-1].year + 1):
            a = nav[nav.index.year == y]
            if len(a) > 20:
                yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
        o["yr"] = yr
        return o

    def dlt(a, b):
        return {p: {"cagr": round(b[p]["cagr"] - a[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - a[p]["mdd"], 2),
                    "sharpe": round(b[p]["sharpe"] - a[p]["sharpe"], 2)} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}
    B0 = go()
    out["B0_now"] = B0
    print("B0", B0["is"], "|", B0["oos"], B0["trd_avg"], flush=True)
    ing = {"T1_def3": dict(sset="def3"), "T1_nostk5": dict(sset="nostk5"), "T2_gold2trd": dict(gold2trd=True),
           "T3_perm05": dict(perm=0.05), "T3_perm10": dict(perm=0.10), "T3_perm15": dict(perm=0.15)}
    single = {}
    for nm, kw in ing.items():
        o = go(**kw); o["d"] = dlt(B0, o); single[nm] = o
        print(nm, o["d"], o["trd_avg"], flush=True)
    out["single"] = single
    # 앞 구간(IS) 기준으로만 고르기: 각 갈래에서 IS 샤프 가장 좋은 것, 그리고 IS·OOS 둘 다 플러스면 묶음 재료
    pick = {}
    for fam in ("T1", "T2", "T3"):
        cands = [k for k in single if k.startswith(fam)]
        best = max(cands, key=lambda k: (single[k]["is"]["sharpe"], single[k]["is"]["cagr"]))
        pick[fam] = best
    out["is_pick"] = pick
    good = [pick[f] for f in pick if single[pick[f]]["d"]["is"]["cagr"] > 0 and single[pick[f]]["d"]["oos"]["cagr"] > 0]
    out["bundle_parts"] = good
    print("앞 구간으로 고른", pick, "묶음 재료", good, flush=True)
    bkw = {}
    for g in good:
        bkw.update(ing[g])
    BUN = go(**bkw) if bkw else B0
    BUN["d"] = dlt(B0, BUN)
    out["bundle"] = {"kw": bkw, **BUN}
    print("묶음", bkw, BUN["d"], flush=True)

    # 흔들기
    shakes = {"tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0), "floor24": dict(floor=0.24), "floor36": dict(floor=0.36),
              "tr80_40": dict(tr=(80, 40)), "tr120_60": dict(tr=(120, 60))}
    # 재료 손잡이 ±20% (perm 은 값 자체를 ±)
    sh = {}
    for nm, kw in shakes.items():
        a = go(**kw); b = go(**{**bkw, **kw}) if bkw else a
        sh[nm] = dlt(a, b)
        print("흔들기", nm, sh[nm], flush=True)
    if "perm" in bkw:
        p = bkw["perm"]
        for f in (0.8, 1.2):
            b = go(**{**bkw, "perm": round(p * f, 3)}); sh[f"perm×{f}"] = dlt(B0, b)
            print("흔들기 perm", f, sh[f"perm×{f}"], flush=True)
    out["shake"] = sh
    # 같은 변동성으로 맞춘 비교(위험만 늘린 몫인지): 묶음의 OOS 변동성을 B0 와 같게 목표 조정
    if bkw:
        v0 = B0["oos"]["vol"]; vb = BUN["oos"]["vol"]
        if vb and v0:
            t2 = 15.0 * v0 / vb
            m = go(**{**bkw, "tgt": round(t2, 2)}); m["d"] = dlt(B0, m); m["tgt"] = round(t2, 2)
            out["bundle_samevol"] = m
            print("같은 변동성", m["tgt"], m["d"], flush=True)
    # 🎯 집중 참고
    c0 = go(base="conc", tgt=22.0, floor=0.70)
    cb = go(base="conc", tgt=22.0, floor=0.70, **{k: v for k, v in bkw.items() if k != "gold2trd"})
    out["conc"] = {"now": c0, "bundle": cb, "d": dlt(c0, cb)}
    print("conc", out["conc"]["d"], flush=True)

    d = BUN["d"]
    shake_ok = bool(sh) and all(v["is"]["cagr"] > 0 and v["oos"]["cagr"] > 0 for v in sh.values())
    big = d["is"]["cagr"] >= 1.0 and d["oos"]["cagr"] >= 1.0
    mdd3 = all(BUN[p]["mdd"] >= B0[p]["mdd"] * (2 / 3) for p in ("is", "oos"))
    out["judge"] = {"d": d, "shake_ok": shake_ok, "size_cagr": big, "size_mdd_third": mdd3,
                    "verdict": "✅ 통과" if (big or mdd3) and shake_ok and bkw else
                    ("🟡 근접" if bkw and shake_ok and d["is"]["cagr"] > 0 and d["oos"]["cagr"] > 0 else "❌")}
    print("JUDGE", out["judge"], flush=True)
    out["note"] = "B0 = 지금 실제 💼(Q10/28-1 추세 주차 포함) · 킥 없음(기본 칸만) · 레버리지 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
