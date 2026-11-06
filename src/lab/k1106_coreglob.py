"""📈 11/6 10시 — 🎯·💼 코어 「무엇을 담나」 2탄: 「미국 대형주 밖으로 넓히기」 가족 14판 · 같은 위험 맞대기
  11/4 k1104_core 는 미국 대형주 안의 지수형(동일가중·품질·자사주·성장 등)만 쟀음 → 이번엔 2026 「넓어지는 장」 재료:
  전 세계(VT·ACWI)·선진국(EFA)·신흥국(EEM)·한국(EWY)·중형(IJH)·소형(IWM)·가치(IVE)·고배당(DVY·SDY)·커버드콜(PBP)·저변동(USMV, 2011~ 앞은 SPY 로 채움)
  판 = S칸(S&P 쪽 ½)을 통째로 / 반만 바꿈 · Q칸(나스닥)은 그대로 — 나스닥 동일가중(QQEW=QQQE 와 같은 지수)은 11/4 에 이미 ❌
  크기 산수: 코어 ½(🎯 50%·💼 47.5%) × 칸 차이 같은 위험 1~2%p ≈ 0.5~1.0%p → 근접 상한 통과
  틀은 k1104_core 그대로(국면·월말 흐름은 진짜 SPY · 앞 구간 변동성 맞춘 목표로 판정 · 앞 1등만 ±20% 흔들기)
→ market/lab/k1106_coreglob.json
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
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, core_run as conc_run, G_CONC, RD_CONC
from k1028_park2 import core_run as port_run

OUT = Path("market/lab/k1106_coreglob.json")
ALT = ["VT", "ACWI", "EFA", "EEM", "EWY", "IJH", "IWM", "IVE", "DVY", "SDY", "PBP", "USMV"]
CANDS = {}
for _a in ["VT", "ACWI", "EFA", "EEM", "EWY", "IJH", "IWM", "IVE", "DVY", "SDY", "PBP", "USMV"]:
    CANDS[_a + "_S"] = ({_a: 1}, {"QQQ": 1})
for _a in ["VT", "EFA", "IJH", "IVE", "PBP"]:
    CANDS[_a + "_halfS"] = ({_a: .5, "SPY": .5}, {"QQQ": 1})
CANDS["EFA_IJH_S"] = ({"EFA": .5, "IJH": .5}, {"QQQ": 1})


def blend(R, mix, fb):
    r = sum(R[t].fillna(R[fb]) * w for t, w in mix.items()) / sum(mix.values())
    return (1 + r.fillna(0.0)).cumprod()


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U + ALT, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    got = [a for a in ALT if a in px]
    for a in got:
        C["A_" + a] = px[a]["close"].reindex(C.index).ffill(limit=5)
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
    R = pd.DataFrame({"SPY": C["SPY"].pct_change(), "QQQ": C["QQQ"].pct_change(),
                      **{a: C["A_" + a].pct_change() for a in got}})
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "got": got, "first": {a: str(px[a].index[0].date()) for a in got},
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}
    print("GOT", got, out["first"], flush=True)

    def mkC(sm, qm, part=1.0):
        Cx = C.copy()
        sS = blend(R, sm, "SPY"); sQ = blend(R, qm, "QQQ")
        if part != 1.0:   # 바꾸는 몫만큼만 섞기
            sS = blend(pd.DataFrame({"a": sS.pct_change(), "b": R["SPY"]}), {"a": part, "b": 1 - part}, "b")
            sQ = blend(pd.DataFrame({"a": sQ.pct_change(), "b": R["QQQ"]}), {"a": part, "b": 1 - part}, "b")
        Cx["SPY"] = sS; Cx["QQQ"] = sQ
        rv = (0.5 * Cx["SPY"].pct_change() + 0.5 * Cx["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
        return Cx, rv

    def go(port, Cx, rv, tgt=None, floor=None):
        if port == "conc":
            tgt = 22.0 if tgt is None else tgt; floor = 0.70 if floor is None else floor
            sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
            nav, td = conc_run(Cx, reg, idx, sc, sigM, fsM, G_CONC, RD_CONC)
        else:
            tgt = 15.0 if tgt is None else tgt; floor = 0.30 if floor is None else floor
            sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
            nav, td, _ = port_run(Cx, reg, idx, sc, "port")
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "eq": round(float(sc.reindex(idx).mean()) * 100, 1)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    def matched(port, Cx, rv, base, tgt0, floor=None):
        lo, hi = tgt0 * 0.5, tgt0 * 1.6
        best = None
        for _ in range(5):
            m = (lo + hi) / 2; r = go(port, Cx, rv, tgt=m, floor=floor)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    C0, rv0 = mkC({"SPY": 1}, {"QQQ": 1})
    res = {}
    for port, tgt0 in (("conc", 22.0), ("port", 15.0)):
        B = go(port, C0, rv0)
        res[port] = {"base": B, "cands": {}}
        print(port, "BASE", B["is"], B["oos"], flush=True)
        for nm, (sm, qm) in CANDS.items():
            if any(t not in R.columns for t in list(sm) + list(qm)):
                continue
            Cx, rv = mkC(sm, qm)
            raw = go(port, Cx, rv)
            mt, mr = matched(port, Cx, rv, B, tgt0)
            res[port]["cands"][nm] = {"raw": dlt(B, raw), "tgt": mt, "m": dlt(B, mr), "m_is": mr["is"], "m_oos": mr["oos"], "eq": mr["eq"]}
            print(port, nm, "RAW", res[port]["cands"][nm]["raw"]["oos"], "| MATCH", mt, res[port]["cands"][nm]["m"]["is"], res[port]["cands"][nm]["m"]["oos"], flush=True)
        cc = res[port]["cands"]
        pick = max(cc, key=lambda k: cc[k]["m"]["is"]["sharpe"] + cc[k]["m"]["is"]["cagr"] / 10)
        res[port]["is_pick"] = pick
        # 흔들기 (기준도 같은 손잡이로)
        sm, qm = CANDS[pick]
        sh = {}
        fl0 = 0.70 if port == "conc" else 0.30
        for vn, kw in {"tgt-20": dict(tgt=tgt0 * .8), "tgt+20": dict(tgt=tgt0 * 1.2), "floor-20": dict(floor=fl0 * .8),
                       "floor+20": dict(floor=fl0 * 1.2), "part40": dict(part=.4), "part60": dict(part=.6)}.items():
            part = kw.pop("part", 1.0)
            Cx, rv = mkC(sm, qm, part)
            b0 = go(port, C0, rv0, **kw)
            t_ = kw.get("tgt", tgt0)
            mt, mr = matched(port, Cx, rv, b0, t_, floor=kw.get("floor"))
            sh[vn] = {"raw": dlt(b0, go(port, Cx, rv, **kw)), "m": dlt(b0, mr)}
            print(port, "SHAKE", vn, sh[vn]["m"]["is"], sh[vn]["m"]["oos"], flush=True)
        res[port]["shake"] = sh
        print(port, "PICK", pick, cc[pick]["m"], flush=True)
    out["res"] = res
    out["note"] = ("🎯 = 목표 22%·한도 70%·덜어낸 몫 🧭 추세 칸·월말 흐름 · 💼 = C안(S 47.5·Q 47.5·금 5 / 하락 31.5·31.5·금 11) 목표 15%·한도 30%·추세 칸 주차 · "
                   "국면·흐름 신호는 진짜 SPY 로 그대로 · raw = 같은 목표, m = 앞 구간 변동성 맞춘 목표(같은 위험) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
