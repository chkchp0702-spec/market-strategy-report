"""🛡 미국 방패 2차 — 「경고 신호에 채권형으로, 바닥 신호에 다시 주식」 (11/11 사용자: 「버블·하락장 시그널이 나오면 전체나 일부를 채권형에 넣었다가
   바닥 시그널이 나오면 다시 주식 비중을 늘리는 전략을 쓰면 되지 않아?」)

  결과 보기 전 등록한 것
  ─ 바탕: SPY · QQQ (배당 포함) · 바꿀 때 0.1% · 그날 종가 신호 → 다음 날 비중
  ─ 들어가는(주식→채권) 신호
     시계6 / 시계4.5 : 순서 문 없는 대리 버블 시계 ≥ 6시 / 4.5시
     조정 / 하락장   : 1년 고점 대비 −10% / −20% 이하 (🐻 계기판 판정과 같음)
     시계6|하락장    : 둘 중 하나
     신용+200        : 신용 단계 ¾ 이상 + 200일선 아래
  ─ 나오는(채권→주식) 바닥 신호 = 🐻 계기판 4개: ① 60일 저점이 10거래일 넘게 안 깨짐 ② 20일선 위 2일 연속 ③ VIX 20 아래 ④ 50일선 위
     ①④ / ①②④ / ③④ / 3개 이상 / (비교용) 판정 풀림 = 고점 −10% 위 + 200일선 위
     · 바닥 신호는 들어간 뒤 60일 신저가가 한 번이라도 나온 다음부터 셈(안 빠졌는데 「바닥」이라고 바로 나오지 않게)
     · 신저가 없이 들어가는 신호가 꺼지면(시계는 T−1.5 아래) 그냥 나옴 · 바닥 신호로 나온 뒤 60일 신저가가 또 나오고 신호가 살아 있으면 다시 들어감
  ─ 채권형: 종합채권(VBMFX) · 중기국채(VFITX) · 장기국채(VUSTX) · 옮기는 몫 50% / 100%
  ─ 합격선(1차와 같음) 「방패」: 앞(~2012)·뒤(2013~) 둘 다 연수익 −0.5%p 안쪽 + 최대 낙폭 5%p 넘게 얕음 · 「이김」: 앞·뒤 둘 다 연수익이 보유보다 높음
  결과: market/us_floor_bt.json · 연구용. 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bubble_bt as bb          # noqa: E402
from us_shield_bt import sim    # noqa: E402

OUT = bb.ROOT / "market" / "us_floor_bt.json"
SPLIT = pd.Timestamp("2013-01-01")
BN = {"agg": "종합채권", "mid": "중기국채", "long": "장기국채"}


def states(ent_on, ent_hold, bot, low60):
    n = len(ent_on); a = np.zeros(n, bool); inn = False; armed = True; seen = False; byb = False
    for i in range(n):
        if not inn:
            if ent_on[i] and armed:
                inn, seen, armed, byb = True, bool(low60[i]), False, False
            elif byb and low60[i] and ent_hold[i]:
                inn, seen, byb = True, True, False
            if not ent_hold[i]:
                armed, byb = True, False
        else:
            seen = seen or bool(low60[i])
            if seen and bot[i]:
                inn, byb = False, True
            elif not seen and not ent_hold[i]:
                inn, armed = False, True
        a[i] = inn
    return a


def main():
    bb.SYMS += ["SPY", "QQQ", "^VIX", "VBMFX", "VUSTX"]
    px = bb.load()
    C = bb.cells(px)
    _, comps, hf = bb.clock(C)
    start = C.dropna(subset=["credit", "breadth", "flow"]).index[0]
    idx = hf.index[hf.index >= start]
    A = lambda s: px[s].reindex(hf.index).ffill()
    cut = lambda s: s.reindex(idx)
    h = cut(hf).values; cred = cut(comps["💳 신용"]).values
    vix = cut(A("^VIX")).values
    bonds = {"agg": cut(A("VBMFX").pct_change()).fillna(0).values, "mid": cut(A("VFITX").pct_change()).fillna(0).values, "long": cut(A("VUSTX").pct_change()).fillna(0).values}
    res = {"at": dt.datetime.now(bb.KST).strftime("%Y-%m-%d %H:%M"), "from": str(idx[0].date()), "to": str(idx[-1].date()),
           "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "markets": []}
    mf, mb_ = (idx < SPLIT), (idx >= SPLIT)
    for key, sym, name in (("sp500", "SPY", "S&P500"), ("nasdaq", "QQQ", "나스닥100")):
        s0 = A(sym); s = cut(s0); ok0 = s.notna().values
        c = s.values; rb = s.pct_change().fillna(0).values
        ma = lambda n: cut(s0.rolling(n).mean()).values
        m20, m50, m200 = ma(20), ma(50), ma(200)
        dd = cut(s0 / s0.rolling(252, min_periods=60).max() - 1).values
        low60 = cut(s0 <= s0.rolling(60, min_periods=20).min()).fillna(False).values
        since_low = cut(s0.rolling(60, min_periods=20).apply(lambda w: len(w) - 1 - int(np.argmin(w)), raw=True)).values
        b1 = since_low > 10
        a20 = c > m20; b2 = a20 & np.roll(a20, 1)
        b3 = vix < 20
        b4 = c > m50
        nb = b1.astype(int) + b2 + b3 + b4
        exits = {"①④": b1 & b4, "①②④": b1 & b2 & b4, "③④": b3 & b4, "3개 이상": nb >= 3, "판정 풀림": (dd > -0.10) & (c > m200)}
        below = c < m200
        ents = {"시계6": (h >= 6, h >= 4.5), "시계4.5": (h >= 4.5, h >= 3), "조정": (dd <= -0.10, dd <= -0.10), "하락장": (dd <= -0.20, dd <= -0.10),
                "시계6|하락장": ((h >= 6) | (dd <= -0.20), (h >= 4.5) | (dd <= -0.10)), "신용+200": ((cred >= 0.75) & below, (cred > 0) & below)}
        grid = []
        for en, (eo, eh) in ents.items():
            for xn, bot in exits.items():
                on = states(eo, eh, bot, low60) & ok0
                for bn, ra in bonds.items():
                    for frac in (0.5, 1.0):
                        f, b, a = sim(rb, ra, on, frac, mf & ok0), sim(rb, ra, on, frac, mb_ & ok0), sim(rb, ra, on, frac, ok0)
                        ef, eb = round(f["cagr"] - f["hold_cagr"], 2), round(b["cagr"] - b["hold_cagr"], 2)
                        df_, db = round(f["mdd"] - f["hold_mdd"], 1), round(b["mdd"] - b["hold_mdd"], 1)
                        grid.append({"ent": en, "exit": xn, "bond": bn, "frac": frac, "front": f, "back": b, "full": a, "edge_front": ef, "edge_back": eb,
                                     "mdd_front": df_, "mdd_back": db, "shield": bool(ef >= -0.5 and eb >= -0.5 and df_ >= 5 and db >= 5), "win": bool(ef > 0 and eb > 0),
                                     "calmar_front": round(f["cagr"] / max(abs(f["mdd"]), 1e-9), 3)})
        fam = []
        for en in ents:
            for xn in exits:
                g = [x for x in grid if x["ent"] == en and x["exit"] == xn]
                fam.append({"ent": en, "exit": xn, "n": len(g), "shield": sum(x["shield"] for x in g), "win": sum(x["win"] for x in g),
                            "edge_front": round(float(np.mean([x["edge_front"] for x in g])), 2), "edge_back": round(float(np.mean([x["edge_back"] for x in g])), 2),
                            "mdd_front": round(float(np.mean([x["mdd_front"] for x in g])), 1), "mdd_back": round(float(np.mean([x["mdd_back"] for x in g])), 1),
                            "sw_y": g[0]["full"]["sw_y"], "on_pct": g[0]["full"]["on_pct"]})
        pick = max(grid, key=lambda x: x["calmar_front"])
        sh = sorted([x for x in grid if x["shield"]], key=lambda x: -x["edge_back"])
        res["markets"].append({"key": key, "name": name, "n": len(grid), "n_shield": len(sh), "n_win": sum(x["win"] for x in grid), "pick": pick, "shields": sh[:15], "families": fam, "grid": grid})
        P = lambda x: f"{x['ent']:>8} → {x['exit']:<6} {BN[x['bond']]} {int(x['frac']*100):>3}% | 앞 {x['edge_front']:+.2f}%p 낙폭 {x['front']['mdd']}({x['mdd_front']:+.1f}) | 뒤 {x['edge_back']:+.2f}%p 낙폭 {x['back']['mdd']}({x['mdd_back']:+.1f}) | 전체 {x['full']['cagr']} vs {x['full']['hold_cagr']} 낙폭 {x['full']['mdd']} vs {x['full']['hold_mdd']} · 1년 {x['full']['sw_y']}번 · 채권 날 {x['full']['on_pct']}% {'🛡' if x['shield'] else ''}{'🏆' if x['win'] else ''}"
        print("\n==", name, "판", len(grid), "방패 합격", len(sh), "이김", sum(x["win"] for x in grid))
        print("앞에서 고른 판:", P(pick))
        for x in sh[:15]:
            print("방패:", P(x))
        for x in sorted(grid, key=lambda x: -x["edge_back"])[:5]:
            print("뒤 수익 상위:", P(x))
        for x in fam:
            print(f"묶음: {x['ent']:>8} → {x['exit']:<6} 방패 {x['shield']}/{x['n']} 이김 {x['win']} | 평균 앞 {x['edge_front']:+.2f}%p 낙폭 {x['mdd_front']:+.1f} | 뒤 {x['edge_back']:+.2f}%p 낙폭 {x['mdd_back']:+.1f} | 1년 {x['sw_y']}번 · 채권 날 {x['on_pct']}%")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
