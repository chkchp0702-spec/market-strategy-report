"""📈 11/9 14시 — 🎯·💼 「위험 예산 채우기(레버리지 없이)」 — 조용한 장에 S칸을 나스닥·기술로 옮겨 목표 변동성까지 채우기
  문제: 🎯 목표 22%·💼 15% 인데 S&P½·나스닥½ 의 20일 변동성이 목표보다 낮은 날(위 한도 1.0 에 막힘)엔 포트가 목표보다 덜 흔들림
        → 레버리지 대신 「더 흔들리는 1배 자산」으로 남는 위험 예산을 채우면? (AQR Asness·Frazzini·Pedersen 2012 「레버리지 회피」:
          레버리지 못 쓰는 투자자는 고베타를 사서 위험을 채움 → 이론상 위험 대비 손해. 우리 자료로 어느 쪽인지 잼)
  규칙: raw = 목표 / rv0 (rv0 = 원래 S½·Q½ 20일 변동성 · 전날 종가까지) · raw > 1 인 날 S칸 안에서 몫 q 를 채움 자산으로
        q = clip(k × (raw − 1), 0, 1) 를 0.25 계단으로(회전 줄임) · 하루 늦게 적용 · S칸 안 갈아타기 회전 × 0.1% 비용 따로 뺌
  가족: 채움 자산 QQQ·XLK × k 0.5·1·2·∞(막힌 날 통째로) = 8판 + 비교용 고정 S25Q75·Q100(늘 채운 것)
  틀 = k1104_core 그대로(국면·월말 흐름 신호는 진짜 SPY · 같은 위험 = 앞 구간 변동성 맞춘 목표 · 앞 1등만 ±20% 흔들기(목표·한도·k))
  💼 = k1028_park2 틀(월말 흐름 없는 옛 기준판 — k1104_core 와 같은 기준) · 하루 늦은 체결 · 비용 0.1% · 레버리지 없음 · ETF 라 생존 편향 없음
→ market/lab/k1109_fill.json
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
from k1028_qflow import drifts, make, core_run as conc_run, G_CONC, RD_CONC
from k1028_park2 import core_run as port_run

OUT = Path("market/lab/k1109_fill.json")
COST = 0.001
FILL = ["QQQ", "XLK"]
KS = {"k0.5": 0.5, "k1": 1.0, "k2": 2.0, "kinf": 99.0}


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "XLK"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    C["A_XLK"] = px.pop("XLK")["close"].reindex(C.index).ffill(limit=5)
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
    R = pd.DataFrame({"SPY": C["SPY"].pct_change(), "QQQ": C["QQQ"].pct_change(), "XLK": C["A_XLK"].pct_change()}).fillna(0.0)
    rv0 = (0.5 * R["SPY"] + 0.5 * R["QQQ"]).rolling(20).std() * math.sqrt(252) * 100
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}}

    def mkS(tgt, k, fa, static=None):
        """S칸 합성 가격 · 채운 몫 q 평균 반환"""
        if static is not None:
            q = pd.Series(static, index=C.index)
        elif k is None:
            q = pd.Series(0.0, index=C.index)
        else:
            raw = (tgt / rv0)
            q = (k * (raw - 1)).clip(0, 1).fillna(0.0)
            q = (q * 4).round() / 4
        ql = q.shift(1).fillna(0.0)   # 전날 종가에 정하고 다음 날부터
        r = (1 - ql) * R["SPY"] + ql * R[fa] - ql.diff().abs().fillna(0.0) * COST
        Cx = C.copy(); Cx["SPY"] = (1 + r).cumprod()
        return Cx, float(q.reindex(idx).mean())

    def go(port, tgt=None, floor=None, k=None, fa="QQQ", static=None):
        if port == "conc":
            tgt = 22.0 if tgt is None else tgt; floor = 0.70 if floor is None else floor
        else:
            tgt = 15.0 if tgt is None else tgt; floor = 0.30 if floor is None else floor
        Cx, qm = mkS(tgt, k, fa, static)
        rv = (0.5 * Cx["SPY"].pct_change() + 0.5 * Cx["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        if port == "conc":
            nav, td = conc_run(Cx, reg, idx, sc, sigM, fsM, G_CONC, RD_CONC)
        else:
            nav, td, _ = port_run(Cx, reg, idx, sc, "port")
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "q": round(qm * 100, 1),
                "cap": round(float((tgt / rv0).reindex(idx).gt(1).mean()) * 100, 1)}

    def dlt(a, b):
        return {p: {kk: round(float(b[p][kk] - a[p][kk]), 2) for kk in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    def matched(port, base, tgt0, **kw):
        lo, hi = tgt0 * 0.5, tgt0 * 1.3
        best = None
        for _ in range(6):
            m = (lo + hi) / 2; r = go(port, tgt=m, **kw)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    res = {}
    for port, tgt0 in (("conc", 22.0), ("port", 15.0)):
        B = go(port)
        res[port] = {"base": B, "cands": {}}
        print(port, "BASE", B, flush=True)
        cands = {f"{fa}_{kn}": dict(k=kv, fa=fa) for fa in FILL for kn, kv in KS.items()}
        cands["S25Q75"] = dict(static=0.5, fa="QQQ"); cands["Q100"] = dict(static=1.0, fa="QQQ")
        for nm, kw in cands.items():
            raw = go(port, **kw)
            mt, mr = matched(port, B, tgt0, **kw)
            res[port]["cands"][nm] = {"raw": dlt(B, raw), "raw_q": raw["q"], "tgt": mt, "m": dlt(B, mr), "m_is": mr["is"], "m_oos": mr["oos"], "m_q": mr["q"]}
            print(port, nm, "RAW", res[port]["cands"][nm]["raw"]["oos"], "q", raw["q"], "| MATCH", mt, res[port]["cands"][nm]["m"], flush=True)
        cc = {k: v for k, v in res[port]["cands"].items() if k not in ("S25Q75", "Q100")}
        pick = max(cc, key=lambda k: cc[k]["m"]["is"]["sharpe"] + cc[k]["m"]["is"]["cagr"] / 10)
        res[port]["is_pick"] = pick
        kw0 = cands[pick]; fl0 = 0.70 if port == "conc" else 0.30
        sh = {}
        for vn, ex in {"tgt-20": dict(tgt=tgt0 * .8), "tgt+20": dict(tgt=tgt0 * 1.2), "floor-20": dict(floor=fl0 * .8),
                       "floor+20": dict(floor=fl0 * 1.2), "k-20": dict(kmul=.8), "k+20": dict(kmul=1.2)}.items():
            kmul = ex.pop("kmul", 1.0)
            kw = dict(kw0); kw["k"] = kw0["k"] * kmul if kw0["k"] < 50 else kw0["k"]
            b0 = go(port, **ex)
            t_ = ex.get("tgt", tgt0)
            mt, mr = matched(port, b0, t_, floor=ex.get("floor"), **kw)
            sh[vn] = {"raw": dlt(b0, go(port, **ex, **kw)), "m": dlt(b0, mr)}
            print(port, "SHAKE", vn, sh[vn]["m"], flush=True)
        res[port]["shake"] = sh
        # 해별 (고른 판 같은 위험 vs 기준)
        print(port, "PICK", pick, cc[pick]["m"], flush=True)
    out["res"] = res
    out["note"] = ("raw = 같은 목표(위험 더 짐), m = 앞 구간 변동성 맞춘 목표(같은 위험) — 판정은 m · q = S칸 중 채움 자산 평균 몫(%) · cap = 50/50 이 목표보다 덜 흔들린 날 비율 · "
                   "💼 는 k1104_core 와 같은 옛 기준판(월말 흐름 없음) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
