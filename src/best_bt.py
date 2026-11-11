"""🏁 시장별 최선 방식 찾기 (11/11 사용자: 「어떤 방식이 각 시장의 최선인지 다 백테스트 해서 알아보고 수익률 제일 좋았던 방식을 채택해」)

  결과 보기 전 등록한 것
  ─ 시장: 🇰🇷 코스피(^KS11) · 코스닥(^KQ11) — 가격지수 · 현금 연 2% / 🇺🇸 S&P500(SPY) · 나스닥100(QQQ) — 배당 포함 · 현금 = 3개월 국채
     바꿀 때 0.1% · 그날 종가 신호 → 다음 날 비중 · 1999~ (대리 버블 시계가 생기는 날부터)
  ─ 방식 = 들어가기 × 나오기 × 옮기는 몫 × 피난처
     들어가기: 고점 −10% · −15% · −20% · 200일선 아래 · 버블 시계 4.5시 · 6시(순서 문 없는 대리 시계) · 신용 경보+200일선 아래
     나오기  : 판정 풀림(고점 −10% 위 + 200일선 위) · 바닥 신호 3개(신저가 뒤) · 바닥 ①④(신저가 뒤) · 200일선 위로 · 들어가기 신호 꺼짐
               (바닥 신호로 나오는 판: 신저가 없이 판정 풀림이 먼저 오면 그때 나옴 · 나온 뒤 −10% 아래에서 신저가가 또 나오면 다시 들어감)
     옮기는 몫: 50% · 100%     피난처: 현금 · (🇺🇸만) 중기국채(VFITX)
     + 그냥 들고 있기 · 지금 규칙(코스피 K100+신용 경보 / S&P500 B50 / 나스닥 OFF / 코스닥 REF)
  ─ 고르는 법 (사용자 기준 「수익률 제일 좋았던」 + 우연 거르기)
     ① 앞(~2012)·뒤(2013~) 둘 다 그냥 들고 있기보다 연수익이 높은 방식만 후보
     ② 후보 중 전체 기간 연수익 1등을 채택 · 후보가 없으면 「그냥 들고 있기」가 그 시장의 최선
  결과: market/best_bt.json · 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bubble_bt as bb   # noqa: E402

OUT = bb.ROOT / "market" / "best_bt.json"
SPLIT = pd.Timestamp("2013-01-01")
ENT = ["dd10", "dd15", "dd20", "ma200", "clock4.5", "clock6", "credit200"]
EXT = ["release", "floor3", "floor14", "ma200up", "off"]
NM = {"dd10": "고점 −10%", "dd15": "고점 −15%", "dd20": "고점 −20%", "ma200": "200일선 아래", "clock4.5": "버블 시계 4.5시", "clock6": "버블 시계 6시", "credit200": "신용 경보+200일선 아래",
      "release": "판정 풀림", "floor3": "바닥 신호 3개", "floor14": "바닥 ①④", "ma200up": "200일선 위로", "off": "신호 꺼짐", "cash": "현금", "bond": "중기국채"}


def feats(s, vix, h, cred):
    c = s.values
    f = {"c": c, "dd": c / s.rolling(252, min_periods=60).max().values - 1}
    for k in (20, 50, 200):
        f[f"m{k}"] = s.rolling(k).mean().values
    f["low60"] = (s <= s.rolling(60, min_periods=20).min()).values
    f["since"] = s.rolling(60, min_periods=20).apply(lambda w: len(w) - 1 - int(np.argmin(w)), raw=True).values
    v = vix.reindex(s.index).ffill().values
    b1 = f["since"] > 10; b2 = (c > f["m20"]) & (np.roll(c, 1) > np.roll(f["m20"], 1)); b3 = v < 20; b4 = c > f["m50"]
    f["nb"] = b1.astype(int) + b2 + b3 + b4; f["b14"] = b1 & b4
    f["h"] = h; f["cred"] = cred
    return f


def entry(f, e):
    c, dd, m200, h, cr = f["c"], f["dd"], f["m200"], f["h"], f["cred"]
    below = c < m200
    if e.startswith("dd"):
        t = -int(e[2:]) / 100; return dd <= t, dd <= t + 0.05
    if e == "ma200":
        return below, below
    if e.startswith("clock"):
        T = float(e[5:]); return h >= T, h >= T - 1.5
    return (cr >= 0.75) & below, (cr > 0) & below


def walk(f, e, x):
    on_, hold = entry(f, e)
    c, dd, m200, low60, nb, b14 = f["c"], f["dd"], f["m200"], f["low60"], f["nb"], f["b14"]
    n = len(c); a = np.zeros(n, bool); inn = False; seen = False; armed = True; byb = False
    for i in range(1, n):
        rel = dd[i] > -0.10 and m200[i] == m200[i] and c[i] > m200[i]
        if not inn:
            if on_[i] and armed:
                inn, seen, armed, byb = True, bool(low60[i]), False, False
            elif byb and low60[i] and dd[i] <= -0.10:
                inn, seen, byb = True, True, False
            if not hold[i]:
                armed = True
            if rel:
                byb = False
        else:
            seen = seen or bool(low60[i])
            if x == "release":
                out = rel
            elif x == "ma200up":
                out = m200[i] == m200[i] and c[i] > m200[i]
            elif x == "off":
                out = not hold[i]
            else:
                bot = nb[i] >= 3 if x == "floor3" else b14[i]
                out = (seen and bot) or (not seen and rel)
                if out and seen and bot:
                    byb = True
            if out:
                inn = False
        a[i] = inn
    return a


def sim(rb, ra, on, frac, m):
    rb, ra, on = rb[m], ra[m], on[m]
    nav = bh = pn = pb = 1.0; mn = mb = 0.0; w = 0.0; sw = 0
    for i in range(1, len(rb)):
        nav *= 1 + (1 - w) * rb[i] + w * ra[i]; bh *= 1 + rb[i]
        pn, pb = max(pn, nav), max(pb, bh); mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb - 1)
        nw = frac if on[i] else 0.0
        if nw != w:
            nav *= 1 - 0.001 * abs(nw - w); sw += 1
        w = nw
    y = max((len(rb) - 1) / 252, 1e-9)
    return {"cagr": round(float((nav ** (1 / y) - 1) * 100), 2), "mdd": round(float(mn * 100), 1),
            "hold_cagr": round(float((bh ** (1 / y) - 1) * 100), 2), "hold_mdd": round(float(mb * 100), 1), "sw_y": round(sw / y, 1)}


def current(key, f, cl_kr_clock=None):
    """지금 규칙의 매일 상태(주식에서 뺀 몫 1.0/0.5/0) — 비교용"""
    c, dd, m200 = f["c"], f["dd"], f["m200"]; n = len(c)
    if key in ("nasdaq", "kosdaq"):
        return np.zeros(n), "cash"
    if key == "sp500":
        return walk(f, "dd10", "floor3").astype(float) * 0.5, "bond"
    a = np.zeros(n); bear = False; kc = False; h = f["cred"]
    for i in range(1, n):
        if not bear and dd[i] <= -0.20: bear = True
        elif bear and dd[i] > -0.10 and c[i] > m200[i]: bear = False
        below = c[i] < m200[i]
        if not kc and h[i] >= 0.999 and below: kc = True   # KC: 대리 시계 ≥3시 = 신용 단계 다 울음(점수 1)
        elif kc and (h[i] < 0.5 or (not below and h[i] < 0.999)): kc = False   # 1.5시 아래 = 신용 점수 ½ 아래
        a[i] = 1.0 if (bear or kc) else 0.0
    return a, "cash"


def main():
    bb.SYMS += ["SPY", "QQQ", "^VIX", "^KQ11"]
    px = bb.load()
    C = bb.cells(px)
    hh, comps, hf = bb.clock(C)
    start = C.dropna(subset=["credit", "breadth", "flow"]).index[0]
    vix = px["^VIX"]
    res = {"at": dt.datetime.now(bb.KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "markets": []}
    for key, sym, name, nat in (("kospi", "^KS11", "코스피", "kr"), ("kosdaq", "^KQ11", "코스닥", "kr"), ("sp500", "SPY", "S&P500", "us"), ("nasdaq", "QQQ", "나스닥100", "us")):
        s0 = px.get(sym)
        if s0 is None:
            print("시세 없음", sym); continue
        s = s0[s0.index >= start - pd.Timedelta(days=400)]
        idx = s.index
        h = hf.reindex(idx).ffill().fillna(0).values
        cred = comps["💳 신용"].reindex(idx).ffill().fillna(0).values
        f = feats(s, vix, h, cred)
        m0 = idx >= start
        rb = s.pct_change().fillna(0).values
        if nat == "us":
            cash = (px["^IRX"].reindex(idx).ffill().fillna(2.0) / 100 / 252).shift(1).fillna(0).values
            alts = {"cash": cash, "bond": px["VFITX"].reindex(idx).ffill().pct_change().fillna(0).values}
        else:
            alts = {"cash": np.full(len(idx), 0.02 / 252)}
        mf, mb = m0 & (idx < SPLIT), m0 & (idx >= SPLIT)
        rows = []
        for e in ENT:
            for x in EXT:
                on = walk(f, e, x)
                for an, ra in alts.items():
                    for frac in (0.5, 1.0):
                        F, B, A = sim(rb, ra, on, frac, mf), sim(rb, ra, on, frac, mb), sim(rb, ra, on, frac, m0)
                        rows.append({"id": f"{e}|{x}|{an}|{int(frac*100)}", "ent": e, "exit": x, "alt": an, "frac": frac, "front": F, "back": B, "full": A,
                                     "cand": bool(F["cagr"] > F["hold_cagr"] and B["cagr"] > B["hold_cagr"]), "now_on": bool(on[-1])})
        cw, ca = current(key, f)
        ra = alts[ca]
        def simw(m):   # 비중 배열(0~1) 그대로
            rb_, ra_, w_ = rb[m], ra[m], cw[m]; nav = bh = pn = pb = 1.0; mn = mb = 0.0; wp = 0.0; sw = 0
            for i in range(1, len(rb_)):
                nav *= 1 + (1 - wp) * rb_[i] + wp * ra_[i]; bh *= 1 + rb_[i]
                pn, pb = max(pn, nav), max(pb, bh); mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb - 1)
                if w_[i] != wp: nav *= 1 - 0.001 * abs(w_[i] - wp); sw += 1
                wp = w_[i]
            y = (len(rb_) - 1) / 252
            return {"cagr": round(float((nav ** (1 / y) - 1) * 100), 2), "mdd": round(float(mn * 100), 1), "hold_cagr": round(float((bh ** (1 / y) - 1) * 100), 2), "hold_mdd": round(float(mb * 100), 1), "sw_y": round(sw / y, 1)}
        cur = {"front": simw(mf), "back": simw(mb), "full": simw(m0)}
        hold = {"cagr": rows[0]["full"]["hold_cagr"], "mdd": rows[0]["full"]["hold_mdd"], "front": rows[0]["front"]["hold_cagr"], "back": rows[0]["back"]["hold_cagr"]}
        cands = sorted([r for r in rows if r["cand"]], key=lambda r: -r["full"]["cagr"])
        best = cands[0] if cands else None
        top = sorted(rows, key=lambda r: -r["full"]["cagr"])[:10]
        res["markets"].append({"key": key, "name": name, "n": len(rows), "n_cand": len(cands), "hold": hold, "current": cur, "best": best, "cands": cands[:15], "top_full": top})
        P = lambda r: f"{NM[r['ent']]:>14} → {NM[r['exit']]:<8} {NM[r['alt']]:<4} {int(r['frac']*100):>3}% | 전체 {r['full']['cagr']:>6} 낙폭 {r['full']['mdd']:>6} | 앞 {r['front']['cagr']:>6}(보유 {r['front']['hold_cagr']}) 뒤 {r['back']['cagr']:>6}(보유 {r['back']['hold_cagr']}) · 1년 {r['full']['sw_y']}번 · 지금 {'켜짐' if r['now_on'] else '꺼짐'} {'✅' if r['cand'] else ''}"
        print(f"\n== {name} 판 {len(rows)} · 후보(앞·뒤 모두 보유 이김) {len(cands)} · 보유 전체 {hold['cagr']} 낙폭 {hold['mdd']} (앞 {hold['front']} 뒤 {hold['back']})")
        print(f"   지금 규칙: 전체 {cur['full']['cagr']} 낙폭 {cur['full']['mdd']} | 앞 {cur['front']['cagr']} 뒤 {cur['back']['cagr']} · 1년 {cur['full']['sw_y']}번")
        print("   채택:", P(best) if best else "그냥 들고 있기")
        for r in cands[1:8]:
            print("   후보:", P(r))
        for r in top[:5]:
            print("   전체 1~5등:", P(r))
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
