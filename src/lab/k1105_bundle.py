"""📈 11/5 14시 2번 — 「묶음」: 오늘 뒤 구간 플러스였던 🎯 작은 개선 둘을 실전 크기(🎯 100%)로 한꺼번에
  재료 ① k1105_concport P — 🎯 위험 그대로 💼 틀(S47.5·Q47.5·금5 / 하락 31.5·31.5·금11 · 아래 한도 30%) : 같은 위험 앞 +0.89 / 뒤 +0.10
       ② k1105_ctaflow fadeDn_W5_t5 — CTA 추정 위치가 5일 새 0.5 넘게 떨어지면 다음다음 날 🧭 추세·금 칸 60% 를 주식으로 : 앞 +0.04 / 뒤 +0.62
  판: 기준(🎯 지금) · ①만 · ②만 · ①+② — 모두 앞 구간 변동성을 🎯 와 같게(목표 이분 탐색) · 같은 틀 core_run · 비용 0.1%(+0.25%)
  흔들기: ② 문턱 0.4·0.6 · W 4·6 · ① 한도 0.24·0.36 → 뒤 플러스 유지?
  판정: 앞 ≥0 · 뒤 +1%p ✅ / +0.33 🟡 · 흔들기 뒤 플러스
→ market/lab/k1105_bundle.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
import k1028_qflow as QF
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1105_ctaflow import cta_pos, cta_sig

OUT = Path("market/lab/k1105_bundle.json")


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
    msig, mfs = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    pos = cta_pos(C["SPY"])

    def sigs(cta):
        if not cta:
            return msig, mfs
        cs, cf = cta_sig(pos, "fadeDn", cta[0], cta[1], 0.6)
        return msig.where(msig != 0, cs), mfs.where(msig != 0, cf)

    def go(frame, tgt, cta=None, cost=0.001, floor=None):
        QF.COST = cost
        G, Rd, fl = (G_PORT, RD_PORT, 0.30) if frame == "P" else (G_CONC, RD_CONC, 0.70)
        if floor is not None:
            fl = floor
        sc = (tgt / rv).clip(upper=1.0, lower=fl).fillna(1.0)
        sg, fs = sigs(cta)
        nav, td = core_run(C, reg, idx, sc, sg, fs, G, Rd)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "nav": nav}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    def matched(frame, base, cta=None, cost=0.001, floor=None, lo=14.0, hi=40.0):
        best = None
        for _ in range(7):
            m = (lo + hi) / 2; r = go(frame, m, cta, cost, floor)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    res = {}
    for cost in (0.001, 0.0025):
        B = go("C", 22.0, None, cost)
        rc = {"base": {"is": B["is"], "oos": B["oos"]}, "v": {}}
        for nm, (fr, cta) in {"P": ("P", None), "CTA": ("C", (5, 0.5)), "P+CTA": ("P", (5, 0.5))}.items():
            t, r = matched(fr, B, cta, cost)
            rc["v"][nm] = {"tgt": t, "d": dlt(B, r)}
            if cost == 0.001 and nm == "P+CTA":
                yr = {}
                for y in range(2008, idx[-1].year + 1):
                    a = B["nav"][B["nav"].index.year == y]; b = r["nav"][r["nav"].index.year == y]
                    if len(a) > 5:
                        yr[str(y)] = round(float((b.iloc[-1] / b.iloc[0] - a.iloc[-1] / a.iloc[0]) * 100), 2)
                rc["v"][nm]["yr"] = yr
            print(cost, nm, t, rc["v"][nm]["d"], flush=True)
        res[str(cost)] = rc
    out["res"] = res
    B = go("C", 22.0)
    sh = {}
    for vn, (cta, fl) in {"th0.4": ((5, 0.4), None), "th0.6": ((5, 0.6), None), "W4": ((4, 0.5), None), "W6": ((6, 0.5), None),
                          "floor0.24": ((5, 0.5), 0.24), "floor0.36": ((5, 0.5), 0.36)}.items():
        t, r = matched("P", B, cta, 0.001, fl)
        sh[vn] = {"tgt": t, "d": dlt(B, r)}
        print("SHAKE", vn, sh[vn], flush=True)
    out["shake"] = sh
    d = res["0.001"]["v"]["P+CTA"]["d"]
    j = {"is": d["is"]["cagr"], "oos": d["oos"]["cagr"], "oos_sharpe": d["oos"]["sharpe"], "oos_mdd": d["oos"]["mdd"],
         "shake_ok": all(v["d"]["oos"]["cagr"] > 0 for v in sh.values()),
         "shake_min": min(v["d"]["oos"]["cagr"] for v in sh.values()),
         "cost25_oos": res["0.0025"]["v"]["P+CTA"]["d"]["oos"]["cagr"]}
    j["verdict"] = "✅" if (j["oos"] > 1.0 and j["is"] >= 0 and j["shake_ok"]) else ("🟡" if (j["oos"] >= 0.33 and j["is"] >= 0) else "❌")
    out["judge"] = j
    print("JUDGE", j, flush=True)
    out["note"] = "기준 = 지금 🎯(22%·70%·월말 흐름·🧭 추세 칸) · 판마다 앞 구간 변동성을 🎯 와 같게 · 레버리지 없음 · ETF 만 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
