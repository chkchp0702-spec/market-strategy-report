"""📈 11/9 16시 — k1109_bundle: 💼 「묶음」 — 뒤 구간 플러스였던 작은 재료 둘을 실전 크기(💼 100%)로 한꺼번에
  기준 = 💼 Q11/6-3 예약 종가판(s1·c1 · t15 · 아래 0.3 · 월말 흐름 · 🧭 추세 칸 주차) — Q11/6-3 몫은 다시 세지 않음
         (참고로 지금 실제 s0 도 같이 적음)
  재료 ① Q11/4-1 S25Q75 — 주식 칸 안 SPY:QQQ = 25:75 (S칸을 SPY½·QQQ½ 합성으로) · 변동성 자도 같은 섞음으로
       ② Q11/5-1 CTA 투매 뒤 더하기 fadeDn(W5·th0.5·f0.6) — 월말 흐름 신호가 없는 날만
  판: 기준 · ①만 · ②만 · ①+② — 모두 앞 구간 변동성을 기준과 같게(목표 이분 탐색) → 「위험만 늘린 몫」 뺀 숫자
  비용 0.1% · 0.25% · 흔들기(①+②): QQQ 몫 0.70·0.80 · th 0.4·0.6 · W 4·6 · 해별
  판정: 앞 ≥0 · 뒤 +1%p ✅ / +0.33 🟡 · 흔들기 뒤 플러스 · ETF 만(생존 편향 없음) · 레버리지 없음
→ market/lab/k1109_bundle.json
"""

from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_PORT, RD_PORT
from k1105_ctaflow import cta_pos, cta_sig
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1109_bundle.json")
A = math.sqrt(252) * 100


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {}
    for k in ["SPY", "QQQ", "GLD"]:
        O[k] = px.pop(k)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    O["TLT"] = px["TLT"]
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
    ms1, mf1 = msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0)
    pos = cta_pos(C["SPY"])
    G, Rd = G_PORT, RD_PORT

    ON0 = pd.DataFrame(0.0, index=C.index, columns=KEYS); CC0 = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        ON0[k] = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        CC0[k] = C[src].pct_change().fillna(0.0)
    CC0["TRD"] = C["TRD"].pct_change().fillna(0.0)

    def frame(qs):
        """주식 칸 SPY:QQQ = (1-qs):qs → run 의 SPY 키(e/2)를 SPY·QQQ 합성으로: 합성 안 QQQ 몫 = 2qs-1"""
        a = 2 * qs - 1
        ON = ON0.copy(); CC = CC0.copy()
        ON["SPY"] = (1 - a) * ON0["SPY"] + a * ON0["QQQ"]
        CC["SPY"] = (1 - a) * CC0["SPY"] + a * CC0["QQQ"]
        ID = (1 + CC) / (1 + ON) - 1
        ID["TRD"] = CC0["TRD"]
        rv = ((1 - qs) * CC0["SPY"] + qs * CC0["QQQ"]).rolling(20).std() * A
        rv = rv.where(rv > 0)
        return ON, ID, rv

    FR = {0.5: frame(0.5)}

    def sigs(base_s, base_f, cta):
        if not cta:
            return base_s, base_f
        cs, cf = cta_sig(pos, "fadeDn", cta[0], cta[1], 0.6)
        return base_s.where(base_s != 0, cs), base_f.where(base_s != 0, cf)

    def go(t, qs=0.5, cta=None, cost=0.001, s1=True):
        if qs not in FR:
            FR[qs] = frame(qs)
        ON, ID, rv = FR[qs]
        sc = (t / rv).clip(upper=1.0, lower=0.30).fillna(1.0)
        bs, bf = (ms1, mf1) if s1 else (msig, mfs)
        sg, fs = sigs(bs, bf, cta)
        nav, td = run(C, ON, ID, reg, idx, sc, sg, fs, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        r = nav.pct_change().dropna()
        a["vol"] = round(float(r[(r.index >= START) & (r.index <= IS_END)].std() * A), 3)
        b["vol"] = round(float(r[r.index >= OOS_START].std() * A), 3)
        return {"is": a, "oos": b, "nav": nav}

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol") if k in a[p]} for p in ("is", "oos")}

    def matched(base, qs, cta, cost, lo=9.0, hi=22.0):
        best = None
        for _ in range(7):
            m = (lo + hi) / 2; r = go(m, qs, cta, cost)
            if best is None or abs(r["is"]["vol"] - base["is"]["vol"]) < abs(best[1]["is"]["vol"] - base["is"]["vol"]):
                best = (m, r)
            if r["is"]["vol"] > base["is"]["vol"]:
                hi = m
            else:
                lo = m
        return round(best[0], 2), best[1]

    def yrs(a, b):
        yr = {}
        for y in range(2008, idx[-1].year + 1):
            x = a[a.index.year == y]; z = b[b.index.year == y]
            if len(x) > 5:
                yr[str(y)] = round(float((z.iloc[-1] / z.iloc[0] - x.iloc[-1] / x.iloc[0]) * 100), 2)
        return yr

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    res = {}
    for cost in (0.001, 0.0025):
        B = go(15.0, cost=cost)
        NOW = go(15.0, cost=cost, s1=False)
        rc = {"base_s1": {"is": B["is"], "oos": B["oos"]}, "now_s0": {"is": NOW["is"], "oos": NOW["oos"]}, "v": {}}
        for nm, (qs, cta) in {"S25Q75": (0.75, None), "CTA": (0.5, (5, 0.5)), "S25Q75+CTA": (0.75, (5, 0.5))}.items():
            raw = go(15.0, qs, cta, cost)
            t, r = matched(B, qs, cta, cost)
            rc["v"][nm] = {"tgt": t, "raw": dlt(B, raw), "d": dlt(B, r), "vs_now": dlt(NOW, r)}
            if cost == 0.001 and nm == "S25Q75+CTA":
                rc["v"][nm]["yr"] = yrs(B["nav"], r["nav"])
            print(cost, nm, t, rc["v"][nm]["d"], flush=True)
        res[str(cost)] = rc
    out["res"] = res
    B = go(15.0)
    sh = {}
    for vn, (qs, cta) in {"q0.70": (0.70, (5, 0.5)), "q0.80": (0.80, (5, 0.5)), "th0.4": (0.75, (5, 0.4)),
                          "th0.6": (0.75, (5, 0.6)), "W4": (0.75, (4, 0.5)), "W6": (0.75, (6, 0.5))}.items():
        t, r = matched(B, qs, cta, 0.001)
        sh[vn] = {"tgt": t, "d": dlt(B, r)}
        print("SHAKE", vn, sh[vn], flush=True)
    out["shake"] = sh
    d = res["0.001"]["v"]["S25Q75+CTA"]["d"]
    j = {"is": d["is"]["cagr"], "oos": d["oos"]["cagr"], "oos_sharpe": d["oos"]["sharpe"], "oos_mdd": d["oos"]["mdd"],
         "shake_ok": all(v["d"]["oos"]["cagr"] > 0 for v in sh.values()),
         "shake_min": min(v["d"]["oos"]["cagr"] for v in sh.values()),
         "shake_is_min": min(v["d"]["is"]["cagr"] for v in sh.values()),
         "cost25_oos": res["0.0025"]["v"]["S25Q75+CTA"]["d"]["oos"]["cagr"],
         "cost25_is": res["0.0025"]["v"]["S25Q75+CTA"]["d"]["is"]["cagr"]}
    j["verdict"] = "✅" if (j["oos"] > 1.0 and j["is"] >= 0 and j["shake_ok"]) else ("🟡" if (j["oos"] >= 0.33 and j["is"] >= 0) else "❌")
    out["judge"] = j
    print("JUDGE", j, flush=True)
    out["note"] = "기준 = 💼 Q11/6-3 예약 종가판(t15·0.3·월말 흐름·🧭 주차) · 판마다 앞 구간 변동성을 기준과 같게 · 레버리지 없음 · ETF 만 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
