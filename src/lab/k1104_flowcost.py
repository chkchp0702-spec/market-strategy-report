"""📈 11/4 16시 ② — 🎯 회전의 87% 는 「월말 흐름」 신호 자체(k1104_turn) → 그 신호가 비용 0.1%·0.25% 에서 값을 하나
  크기 산수: 🎯 100% · 흐름 신호 회전 ≈960%/년 × 0.1% ≈ 0.96%p (0.25% 면 2.4%p) → 통과
  판: 신호 끔 · 옮기는 몫 f 0.6→0.45·0.3 · 마지막 K 일 5→3 · 문턱 th 0.005→0.01·0.02 · 한쪽만(+1 주식 덜기만 / −1 주식 더하기만)
  틀 = k1104_turn.run(= k1028_qflow.core_run 같은 규칙) · 앞 2008-07~2016 고르고 뒤 2017~ · ±20% · 비용 0.1%(판정)·0.25%(참고)
→ market/lab/k1104_flowcost.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from k1104_turn import run, make_sc

OUT = Path("market/lab/k1104_flowcost.json")
VAR = {"base": {}, "off": {"off": 1}, "f45": dict(f=0.45), "f30": dict(f=0.30), "f75": dict(f=0.75), "K3": dict(K=3), "K4": dict(K=4),
       "th10": dict(th=0.01), "th20": dict(th=0.02), "upOnly": {"side": 1}, "dnOnly": {"side": -1},
       "th10_f45": dict(th=0.01, f=0.45), "K3_f45": dict(K=3, f=0.45)}


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
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100

    def go(kw, cost, tgt=22.0, floor=0.70):
        kw = dict(kw); side = kw.pop("side", 0)
        if kw.pop("off", 0):
            sig = fs = pd.Series(0.0, index=C.index)
        else:
            sig, fs = make(C, DM, DQ, **kw)
            if side:
                m = sig != side; sig = sig.where(~m, 0.0); fs = fs.where(~m, 0.0)
        sc = make_sc(rv, tgt=tgt, floor=floor)
        nav, td, why = run(C, reg, idx, sc, sig, fs, cost=cost)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol", "turn")} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "res": {}}
    for cost in (0.001, 0.0025, 0.004):
        B = go({}, cost); res = {"base": B, "cands": {}}
        print(cost, "BASE", B["is"]["cagr"], B["oos"]["cagr"], B["oos"]["sharpe"], B["oos"]["turn"], flush=True)
        for nm, kw in VAR.items():
            if nm == "base":
                continue
            r = go(kw, cost); res["cands"][nm] = {"d": dlt(B, r), "is": r["is"], "oos": r["oos"]}
            print(cost, nm, res["cands"][nm]["d"]["is"], "|", res["cands"][nm]["d"]["oos"], flush=True)
        cc = res["cands"]
        pick = max(cc, key=lambda k: cc[k]["d"]["is"]["sharpe"] + cc[k]["d"]["is"]["cagr"] / 10)
        res["is_pick"] = pick
        sh = {}
        for nm2, ex in (("tgt-20", dict(tgt=17.6)), ("tgt+20", dict(tgt=26.4)), ("floor-20", dict(floor=.56)), ("floor+20", dict(floor=.84))):
            sh[nm2] = dlt(go({}, cost, **ex), go(VAR[pick], cost, **ex))
            print(cost, "SHAKE", pick, nm2, sh[nm2]["is"], sh[nm2]["oos"], flush=True)
        res["shake"] = sh
        out["res"][f"c{int(cost * 10000)}"] = res
        print(cost, "PICK", pick, cc[pick]["d"], flush=True)
    out["note"] = "🎯 목표 22·한도 70 · d = 같은 비용의 지금 규칙 대비 · c10/c25/c40 = 비용 0.1/0.25/0.4% · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
