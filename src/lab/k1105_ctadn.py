"""📈 11/5 10시 ② — k1105_ctaflow 에서 뒤 구간 유일하게 눈에 띈 판 fadeDn_W5_t5(앞 +0.04 / 뒤 +0.62%p, 뒤 변동성 +0.5)의 이웃 흔들기
  W 4·5·6 × th 0.4·0.5·0.6 × f 0.48·0.6·0.72 (27판) · 비용 0.1·0.25% · 같은 위험 환산 = 기준 수익 + Δ샤프 × 기준 변동성
→ market/lab/k1105_ctadn.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from k1104_turn import run, make_sc
from k1105_ctaflow import cta_pos, cta_sig

OUT = Path("market/lab/k1105_ctadn.json")


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
    msig, mfs = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    pos = cta_pos(C["SPY"]); sc = make_sc(rv)

    def go(W=None, th=None, f=0.6, cost=0.001):
        if W is None:
            sig, fs = msig, mfs
        else:
            cs, cf = cta_sig(pos, "fadeDn", W, th, f)
            sig = msig.where(msig != 0, cs); fs = mfs.where(msig != 0, cf)
        nav, td, _ = run(C, reg, idx, sc, sig, fs, cost=cost)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "grid": {}}
    for cost in (0.001, 0.0025):
        B = go(cost=cost)
        for W in (4, 5, 6):
            for th in (0.4, 0.5, 0.6):
                for f in (0.48, 0.6, 0.72):
                    r = go(W, th, f, cost)
                    d = {}
                    for p in ("is", "oos"):
                        d[p] = {k: round(float(r[p][k] - B[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")}
                        d[p]["same_risk"] = round(float((r[p]["sharpe"] - B[p]["sharpe"]) * B[p]["vol"]), 2)
                    nm = f"c{int(cost*10000)}_W{W}_t{int(th*10)}_f{int(f*100)}"
                    out["grid"][nm] = d
                    print(nm, d["is"], "|", d["oos"], flush=True)
    g = out["grid"]
    for c in ("c10", "c25"):
        ks = [k for k in g if k.startswith(c)]
        out[c + "_summary"] = {
            "oos_cagr_pos": sum(g[k]["oos"]["cagr"] > 0 for k in ks), "n": len(ks),
            "oos_same_risk_mean": round(sum(g[k]["oos"]["same_risk"] for k in ks) / len(ks), 2),
            "oos_cagr_mean": round(sum(g[k]["oos"]["cagr"] for k in ks) / len(ks), 2),
            "is_cagr_mean": round(sum(g[k]["is"]["cagr"] for k in ks) / len(ks), 2)}
        print(c, out[c + "_summary"], flush=True)
    out["note"] = "fadeDn = SPY 추정 CTA 위치가 W일 동안 th 넘게 떨어진(투매) 다음 날, 🧭 추세·금 칸의 f 몫을 주식으로 · 월말 흐름 켜진 날은 그것 먼저 · 같은 위험 = Δ샤프 × 기준 변동성"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
