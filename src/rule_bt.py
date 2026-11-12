"""🧩 새 신호를 규칙에 얹기 (11/12 사용자: 「규칙에 적용시켜」 — 신호 확률판·나라별 다른 자료에서 통과한 신호)

  결과 보기 전 등록한 것
  ─ 바탕 = 11/11 채택 규칙(🐻 계기판 지금 규칙)을 매일 다시 만든 것
     코스피: 하락장(K100) · 신용 경보+200일선(KC) · 버블 시계 4.5시 → 바닥 ①④ 까지 — 하나라도 켜지면 현금 100%
     코스닥: 버블 시계 6시 → 바닥 3개까지 현금 100% / S&P500: 조정 −10% → 바닥 3개 · 신용 경보+200일선 → 바닥 ①④ 까지 절반 중기국채 / 나스닥: 그냥 들기
  ─ 얹을 것 = 그 지수에서 alt_bt 를 통과한(✅) 신호만
     🚨 경고 얹기: 켜진 동안 주식 몫의 25% · 50% 를 현금(S&P500 은 중기국채)으로 — 바탕이 더 많이 뺐으면 바탕대로
     🌱 바닥 얹기: 켜진 동안 바탕 규칙의 현금을 풀어 주식으로 (전부 · 또는 절반만 풀기)
     + 가장 좋은 경고 하나 × 가장 좋은 바닥 하나 겹치기
  ─ 채택: 2012년까지·2013년부터 둘 다 바탕보다 연수익이 높고, 최대 낙폭이 바탕보다 5%p 넘게 나빠지지 않은 것 중 전체 연수익 1등 · 없으면 바탕 그대로
     그날 종가 신호 → 다음 날 비중 · 현금 연 2%(미국은 3개월 국채) · 바꿀 때 0.1% · 가격지수(미국은 SPY·QQQ 배당 포함)
  결과: market/rule_bt.json(검증) · market/rule_overlay.json(지금 켜졌나 → bear_gate 가 읽음). 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alt_bt as ab    # noqa: E402
import best_bt as BB   # noqa: E402
import bubble_bt as bb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "rule_bt.json"
LIVE = ROOT / "market" / "rule_overlay.json"
SPLIT = pd.Timestamp("2013-01-01")
# 11/12 사용자 「수익을 선택」 — 낙폭 기준(5%p)에 걸려도 수익이 앞·뒤 둘 다 나은 판을 쓰는 시장 (그 판이 계속 앞·뒤 둘 다 이기면 유지)
PREFER_RET = {"kospi"}
MK = [("kospi", "^KS11", "^KS11", "코스피"), ("kosdaq", "^KQ11", "^KQ11", "코스닥"), ("sp500", "^GSPC", "SPY", "S&P500"), ("nasdaq", "^IXIC", "QQQ", "나스닥")]


def perf(rb, ra, w, m):
    rb, ra, w = rb[m], ra[m], w[m]
    nav = bh = pn = pb = 1.0; mn = mb = 0.0; wp = w[0]; sw = 0
    for i in range(1, len(rb)):
        nav *= 1 + (1 - wp) * rb[i] + wp * ra[i]; bh *= 1 + rb[i]
        pn, pb = max(pn, nav), max(pb, bh); mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb - 1)
        if w[i] != wp: nav *= 1 - 0.001 * abs(w[i] - wp); sw += 1
        wp = w[i]
    y = max((len(rb) - 1) / 252, 1e-9)
    return {"cagr": round(float((nav ** (1 / y) - 1) * 100), 2), "mdd": round(float(mn * 100), 1), "hold": round(float((bh ** (1 / y) - 1) * 100), 2), "hold_mdd": round(float(mb * 100), 1), "sw_y": round(sw / y, 1)}


def main():
    px0 = pd.read_csv(ab.ALT / "px.csv.gz", index_col=0, parse_dates=True)
    px = {c: px0[c].dropna() for c in px0.columns}
    C = bb.cells(px); hh, comps, hf = bb.clock(C)
    F = ab.build(px0)
    A = json.loads((ROOT / "market" / "alt.json").read_text(encoding="utf-8"))
    passed = {m["key"]: {r["k"]: r for r in m["signals"] if r["good"]} for m in A["markets"]}
    res = {"at": dt.datetime.now(ab.KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "markets": []}
    live = {"at": res["at"], "markets": {}}
    for key, sig_sym, trade_sym, name in MK:
        s = px[sig_sym]; idx = s.index
        f = BB.feats(s, px["^VIX"], hf.reindex(idx).ffill().fillna(0).values, comps["💳 신용"].reindex(idx).ffill().fillna(0).values)
        f["hg"] = hh.reindex(idx).ffill().fillna(0).values
        if key == "kospi":
            a, _ = BB.current("kospi", f); base = np.maximum(a, BB.walk(f, "clock4.5", "floor14").astype(float)); alt = "cash"
        elif key == "kosdaq":
            base = BB.walk(f, "clock6", "floor3").astype(float); alt = "cash"
        elif key == "sp500":
            base = 0.5 * np.maximum(BB.walk(f, "dd10", "floor3"), BB.walk(f, "credit200", "floor14")).astype(float); alt = "bond"
        else:
            base = np.zeros(len(idx)); alt = "cash"
        t = px[trade_sym].reindex(idx).ffill(); rb = t.pct_change().fillna(0).values
        if alt == "bond":
            ra = px["VFITX"].reindex(idx).ffill().pct_change().fillna(0).values
        elif key in ("sp500", "nasdaq"):
            ra = (px["^IRX"].reindex(idx).ffill().fillna(2.0) / 100 / 252).shift(1).fillna(0).values
        else:
            ra = np.full(len(idx), 0.02 / 252)
        ok = t.notna().values & (idx >= pd.Timestamp("1999-01-01"))
        sig = {k: (nm, side, x.reindex(idx)) for k, nm, side, x in F[key] if k in passed.get(key, {})}
        w0 = np.roll(base, 1); w0[0] = 0   # 그날 신호 → 다음 날
        def mkw(arr):
            w = np.roll(arr, 1); w[0] = 0; return w
        vs = {"base": ("지금 규칙 그대로", mkw(base))}
        Wk = [k for k, v in sig.items() if v[1] == "W"]; Bk = [k for k, v in sig.items() if v[1] == "B"]
        for k in Wk:
            on = (sig[k][2].fillna(0).values > 0.5)
            for fr in (0.25, 0.5):
                vs[f"W:{k}:{fr}"] = (f"🚨 {sig[k][0]} → 주식 몫 {int(fr*100)}% {'채권형' if alt == 'bond' else '현금'}", mkw(np.maximum(base, on * fr)))
        for k in Bk:
            on = (sig[k][2].fillna(0).values > 0.5)
            vs[f"B:{k}:0"] = (f"🌱 {sig[k][0]} → 현금 풀고 주식으로", mkw(np.where(on, 0.0, base)))
            vs[f"B:{k}:h"] = (f"🌱 {sig[k][0]} → 현금 절반만 풀기", mkw(np.where(on, np.minimum(base, 0.5), base)))
        m_all, m_a, m_b = ok, ok & (idx < SPLIT), ok & (idx >= SPLIT)
        def score(w): return {"full": perf(rb, ra, w, m_all), "a": perf(rb, ra, w, m_a), "b": perf(rb, ra, w, m_b)}
        R = {k: {"name": v[0], **score(v[1])} for k, v in vs.items()}
        B0 = R["base"]
        def okk(r): return r["a"]["cagr"] > B0["a"]["cagr"] and r["b"]["cagr"] > B0["b"]["cagr"] and r["full"]["mdd"] >= B0["full"]["mdd"] - 5
        if key in PREFER_RET:
            okk = lambda r: r["a"]["cagr"] > B0["a"]["cagr"] and r["b"]["cagr"] > B0["b"]["cagr"]
        bw = max([k for k in R if k.startswith("W:") and okk(R[k])], key=lambda k: R[k]["full"]["cagr"], default=None)
        bbk = max([k for k in R if k.startswith("B:") and okk(R[k])], key=lambda k: R[k]["full"]["cagr"], default=None)
        if bw and bbk:   # 겹치기
            kw, fr = bw.split(":")[1], float(bw.split(":")[2]); kb, mode = bbk.split(":")[1], bbk.split(":")[2]
            onw = sig[kw][2].fillna(0).values > 0.5; onb = sig[kb][2].fillna(0).values > 0.5
            arr = np.maximum(base, onw * fr); arr = np.where(onb, 0.0 if mode == "0" else np.minimum(arr, 0.5), arr)
            R[f"WB:{kw}:{fr}|{kb}:{mode}"] = {"name": R[bw]["name"] + " + " + R[bbk]["name"], **score(mkw(arr))}
        if key in PREFER_RET:
            okk = lambda r: r["a"]["cagr"] > B0["a"]["cagr"] and r["b"]["cagr"] > B0["b"]["cagr"]
        cands = sorted([k for k in R if k != "base" and okk(R[k])], key=lambda k: -R[k]["full"]["cagr"])
        pick = cands[0] if cands else "base"
        # 지금 켜졌나 (오늘 종가)
        parts = []
        if pick != "base":
            for piece in pick.split(":", 1)[1].split("|") if pick.startswith("WB:") else [pick.split(":", 1)[1]]:
                k, arg = piece.split(":")
                sd = sig[k][1]; last = sig[k][2].dropna()
                parts.append({"k": k, "name": sig[k][0], "side": sd, "arg": arg, "on": bool(len(last) and last.iloc[-1] > 0.5), "asof": str(last.index[-1].date()) if len(last) else None})
        live["markets"][key] = {"pick": pick, "name": R[pick]["name"], "parts": parts, "to": "채권형" if alt == "bond" else "현금",
                                "full": R[pick]["full"], "base_full": B0["full"], "a": R[pick]["a"]["cagr"], "b": R[pick]["b"]["cagr"], "base_a": B0["a"]["cagr"], "base_b": B0["b"]["cagr"]}
        res["markets"].append({"key": key, "name": name, "base": B0, "pick": pick, "rows": R, "n_ok": len(cands)})
        print(f"\n== {name} · 바탕 연 {B0['full']['cagr']}% 낙폭 {B0['full']['mdd']}% (앞 {B0['a']['cagr']} 뒤 {B0['b']['cagr']}) · 그냥 들기 {B0['full']['hold']}% {B0['full']['hold_mdd']}% · 통과 신호 {len(sig)}개")
        for k in sorted(R, key=lambda k: -R[k]["full"]["cagr"]):
            r = R[k]
            print(f"   {'✅' if okk(r) and k != 'base' else '  '}{'👉' if k == pick else '  '} 연 {r['full']['cagr']:>6}% 낙폭 {r['full']['mdd']:>6}% | 앞 {r['a']['cagr']:>6} 뒤 {r['b']['cagr']:>6} · 1년 {r['full']['sw_y']}번 · {r['name']}")
        print("   지금:", parts)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
