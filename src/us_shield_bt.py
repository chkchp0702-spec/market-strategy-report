"""🛡 미국 방패 연구 (11/11 사용자: 「미국은 아무리 경고등이 울려도 지수를 들고 있으라는 얘기야? 대책이 있어야 — 방법을 연구해봐」)

  지금까지: 🇺🇸 은 「현금으로 빼기」 판이 2013년 뒤 모두 보유에 짐(bear_gate lab · bubble_bt). 그래서 「현금」 말고 다른 대책을 본다.

  결과 보기 전 등록한 것
  ─ 바탕: SPY · QQQ (배당 포함 수정주가) · 현금 이자 = 3개월 국채(^IRX) · 바꿀 때 0.1% · 그날 종가 신호 → 다음 날 비중
  ─ 신호 (시계 = 순서 문 없는 대리 버블 시계 = 네 단계 점수 × 3시간 합)
     clock T      : 시계 ≥ T 켜짐 · T − 1.5 아래 꺼짐                    (T = 4.5 · 6 · 7.5)
     clock T+200  : 시계 ≥ T 이고 200일선 아래 켜짐 · 시계 T − 1.5 아래 또는 (200일선 위 + 시계 T 아래) 꺼짐
     credit+200   : 신용 단계 ¾ 이상 울고 200일선 아래 켜짐 · 신용 단계 0 또는 (200일선 위 + 신용 ¾ 아래) 꺼짐
     200          : 200일선 아래/위 (시계 없는 단순 추세 — 비교 기준)
  ─ 대책 (켜진 동안 주식 몫의 50% 또는 100% 를)
     현금 · 중기국채(VFITX) · 금(GC=F) · 방어 3종(XLP·XLV·XLU 평균) · (QQQ 만) S&P500 으로
  ─ 합격선 「방패」: 앞(~2012)·뒤(2013~) 둘 다 ① 연수익이 보유보다 0.5%p 넘게 깎이지 않고 ② 최대 낙폭이 보유보다 5%p 넘게 얕음
     「이김」: 앞·뒤 둘 다 연수익이 보유보다 높음
  ─ 고르는 법: 앞에서 수익÷낙폭이 가장 좋은 판을 고르고 뒤에서 확인. 판이 많으니(시장마다 60여 개) 합격 수도 같이 본다.
  결과: market/us_shield_bt.json · 연구용 — 규칙 연결은 사용자 결정 뒤. 매수·매도 추천 아님.
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

OUT = bb.ROOT / "market" / "us_shield_bt.json"
SPLIT = pd.Timestamp("2013-01-01")
ALT_NM = {"cash": "현금", "bond": "중기국채", "gold": "금", "def": "방어주 3종", "spy": "S&P500"}


def signals(h, cred, c, ma):
    """→ {이름: bool 배열}"""
    n = len(c); out = {}
    def loop(on_f, off_f):
        a = np.zeros(n, bool); on = False
        for i in range(n):
            if not on and on_f(i): on = True
            elif on and off_f(i): on = False
            a[i] = on
        return a
    below = lambda i: ma[i] == ma[i] and c[i] < ma[i]
    above = lambda i: ma[i] == ma[i] and c[i] > ma[i]
    for T in (4.5, 6, 7.5):
        out[f"clock{T:g}"] = loop(lambda i: h[i] >= T, lambda i: h[i] < T - 1.5)
        out[f"clock{T:g}+200"] = loop(lambda i: h[i] >= T and below(i), lambda i: h[i] < T - 1.5 or (above(i) and h[i] < T))
    out["credit+200"] = loop(lambda i: cred[i] >= 0.75 and below(i), lambda i: cred[i] == 0 or (above(i) and cred[i] < 0.75))
    out["200"] = loop(below, above)
    return out


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
            "hold_cagr": round(float((bh ** (1 / y) - 1) * 100), 2), "hold_mdd": round(float(mb * 100), 1),
            "sw_y": round(sw / y, 1), "on_pct": round(float(on.mean() * 100), 1)}


def main():
    bb.SYMS += ["SPY", "QQQ", "GC=F"]
    px = bb.load()
    C = bb.cells(px)
    _, comps, hf = bb.clock(C)
    start = C.dropna(subset=["credit", "breadth", "flow"]).index[0]
    idx = hf.index[hf.index >= start]
    A = lambda s: px[s].reindex(idx).ffill()
    cash = (A("^IRX").fillna(2.0) / 100 / 252).shift(1).fillna(0).values
    ret = lambda s: s.pct_change().fillna(0).values
    alts = {"cash": cash, "bond": ret(A("VFITX")), "def": ret((A("XLP").pct_change() + A("XLV").pct_change() + A("XLU").pct_change()).div(3).add(1).cumprod())}
    g = A("GC=F"); gr = g.pct_change(); alts["gold"] = np.where(gr.isna(), cash, gr.fillna(0).values)
    res = {"at": dt.datetime.now(bb.KST).strftime("%Y-%m-%d %H:%M"), "from": str(idx[0].date()), "to": str(idx[-1].date()),
           "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "markets": []}
    mf, mb_ = (idx < SPLIT), (idx >= SPLIT)
    all_ = np.ones(len(idx), bool)
    for key, sym, name in (("sp500", "SPY", "S&P500"), ("nasdaq", "QQQ", "나스닥100")):
        s = A(sym); ok0 = s.notna().values
        c = s.values; ma = s.rolling(200).mean().values; rb = s.pct_change().fillna(0).values
        sg = signals(hf.reindex(idx).values, comps["💳 신용"].reindex(idx).values, c, ma)
        al = dict(alts)
        if key == "nasdaq":
            al["spy"] = ret(A("SPY"))
        grid = []
        for sn, on in sg.items():
            on = on & ok0
            for an, ra in al.items():
                for frac in (0.5, 1.0):
                    f, b, a = sim(rb, ra, on, frac, mf & ok0), sim(rb, ra, on, frac, mb_ & ok0), sim(rb, ra, on, frac, all_ & ok0)
                    ef, eb = round(f["cagr"] - f["hold_cagr"], 2), round(b["cagr"] - b["hold_cagr"], 2)
                    df_, db = round(f["mdd"] - f["hold_mdd"], 1), round(b["mdd"] - b["hold_mdd"], 1)
                    grid.append({"sig": sn, "alt": an, "frac": frac, "front": f, "back": b, "full": a, "edge_front": ef, "edge_back": eb, "mdd_front": df_, "mdd_back": db,
                                 "shield": bool(ef >= -0.5 and eb >= -0.5 and df_ >= 5 and db >= 5), "win": bool(ef > 0 and eb > 0),
                                 "calmar_front": round(f["cagr"] / max(abs(f["mdd"]), 1e-9), 3)})
        pick = max(grid, key=lambda x: x["calmar_front"])
        sh = sorted([x for x in grid if x["shield"]], key=lambda x: -(x["edge_back"]))
        res["markets"].append({"key": key, "name": name, "n": len(grid), "n_shield": len(sh), "n_win": sum(x["win"] for x in grid),
                               "pick": pick, "shields": sh[:12], "grid": grid})
        print("\n==", name, "판", len(grid), "방패 합격", len(sh), "이김", sum(x["win"] for x in grid))
        P = lambda x: f"{x['sig']:>13} {ALT_NM[x['alt']]:<6} {int(x['frac']*100):>3}% | 앞 {x['edge_front']:+.2f}%p 낙폭 {x['front']['mdd']}({x['mdd_front']:+.1f}) | 뒤 {x['edge_back']:+.2f}%p 낙폭 {x['back']['mdd']}({x['mdd_back']:+.1f}) | 전체 {x['full']['cagr']} vs {x['full']['hold_cagr']} 낙폭 {x['full']['mdd']} vs {x['full']['hold_mdd']} · 1년 {x['full']['sw_y']}번 · 켜진 날 {x['full']['on_pct']}% {'🛡' if x['shield'] else ''}{'🏆' if x['win'] else ''}"
        print("앞에서 고른 판:", P(pick))
        for x in sh[:12]:
            print("방패:", P(x))
        for x in sorted(grid, key=lambda x: -x["edge_back"])[:6]:
            print("뒤 수익 상위:", P(x))
        for x in [x for x in grid if x["frac"] == 1.0 and x["alt"] == "cash"]:
            print("현금 100%:", P(x))
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
