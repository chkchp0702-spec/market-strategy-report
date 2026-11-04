"""📈 11/4 14시 — 🎯·💼 코어(S&P½·나스닥½) 「무엇을 담나」 — 지수형 ETF 가족 20판 · 같은 위험 맞대기
  크기 산수: 코어는 🎯 100%·💼 95% → 한 칸(½)만 바꿔도 칸 차이 2%p × ½ × 평균 주식 ≈0.85 ≈ 0.85%p, 두 칸이면 상한 1.5%p↑ → 통과
  바깥 재료: S&P 동일가중(RSP)·나스닥 동일가중(QQEW) 「집중 위험」 글(2026 회전 기사·Voya·Robeco) · S&P 매출가중(RWL, Indexology 2025) ·
             품질(SPHQ) · 자사주(PKW) · 배당성장(VIG) · 모멘텀(PDP) · 성장(SPYG·IWF·MGK) · 초대형(XLG·OEF) · 기술(XLK·VGT) · S&P:나스닥 비율
  틀: 국면 판정(200일선 A)·월말 흐름 신호는 그대로(진짜 SPY·IEF 로) → 칸에 담는 ETF 만 바꿈, 변동성 맞춤은 바뀐 코어의 20일 변동으로
      같은 위험 = 앞 구간(2008-07~2016) 변동성이 기준과 같아지게 목표 변동성을 맞춘 판(k1103_vrp2 틀) — 판정은 이 숫자로
      고르기 = 앞 구간 맞춘 판 샤프 + 연수익/10 1등 → 뒤(2017~) 시험 · ±20% 흔들기(목표·한도·바꾸는 몫 40/60%)
  하루 늦은 체결 · 비용 0.1% · 레버리지 없음 · ETF 라 생존 편향 없음(단, 후보 ETF 고르기 자체에 「지금 아는 것」 편향 — 앞 구간 1등만 판정)
→ market/lab/k1104_core.json
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

OUT = Path("market/lab/k1104_core.json")
ALT = ["RSP", "QQEW", "RWL", "SPHQ", "PKW", "VIG", "PDP", "SPYG", "IWF", "MGK", "XLG", "OEF", "XLK", "VGT"]
# 판 = (S칸 섞기, Q칸 섞기) — 원래 S칸 = SPY, Q칸 = QQQ
CANDS = {
    "RSP_S": ({"RSP": 1}, {"QQQ": 1}), "QQEW_Q": ({"SPY": 1}, {"QQEW": 1}), "EW_both": ({"RSP": 1}, {"QQEW": 1}),
    "RWL_S": ({"RWL": 1}, {"QQQ": 1}), "SPHQ_S": ({"SPHQ": 1}, {"QQQ": 1}), "PKW_S": ({"PKW": 1}, {"QQQ": 1}),
    "VIG_S": ({"VIG": 1}, {"QQQ": 1}), "PDP_S": ({"PDP": 1}, {"QQQ": 1}), "SPYG_S": ({"SPYG": 1}, {"QQQ": 1}),
    "IWF_S": ({"IWF": 1}, {"QQQ": 1}), "MGK_S": ({"MGK": 1}, {"QQQ": 1}), "XLG_S": ({"XLG": 1}, {"QQQ": 1}),
    "OEF_S": ({"OEF": 1}, {"QQQ": 1}), "XLK_Q": ({"SPY": 1}, {"XLK": 1}), "VGT_Q": ({"SPY": 1}, {"VGT": 1}),
    "Q100": ({"QQQ": 1}, {"QQQ": 1}), "S25Q75": ({"SPY": .5, "QQQ": .5}, {"QQQ": 1}),
    "S75Q25": ({"SPY": 1}, {"SPY": .5, "QQQ": .5}), "S100": ({"SPY": 1}, {"SPY": 1}),
    "SPHQ_RWL_S": ({"SPHQ": .5, "RWL": .5}, {"QQQ": 1}),
}


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
