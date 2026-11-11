"""🌱 코스피·코스닥 바닥 신호 다시 담기 (11/11 사용자: 「코스피나 코스닥도 바닥 신호 나오면 알려주고 비중 담게 하자」)

  지금 🇰🇷 코스피 K100 = 🐻 하락장(고점 −20%)이면 주식 몫 전부 현금 → 판정 풀릴 때(고점 −10% 위 + 200일선 위)까지 기다림.
  그 사이 바닥 신호로 먼저 다시 담으면 나았는지 본다.

  결과 보기 전 등록한 것
  ─ 지수: 코스피(^KS11) · 코스닥(^KQ11) 가격지수 · 현금 연 2% · 바꿀 때 0.1% · 그날 종가 → 다음 날 비중 (🐻 계기판 백테스트와 같은 조건)
  ─ 바닥 신호 = 🐻 계기판 4개 · ④는 옛 외국인 자료가 없어 50일선 위로 대신 · ③ VIX 20 아래
  ─ 판
     K100      : 기준 (지금 규칙)
     F-①④     : 🐻 동안 60일 신저가가 한 번 나온 뒤 ①④ 켜지면 주식 100% 다시 · 그 뒤 🐻 안에서 신저가가 또 나오면 다시 현금 100%
     F-①②④    : 같은 걸음 · ①②④
     F-3개      : 같은 걸음 · 4개 중 3개 이상
     S-계단     : ①④ → 주식 50% · ①②④ → 100% (신저가 또 나오면 다시 0%)
     S-계단3    : ①④ → 50% · 3개 이상 → 100%
  ─ 합격: 앞(~2012)·뒤(2013~) 둘 다 K100 보다 연수익이 높고, 최대 낙폭이 K100 보다 5%p 넘게 나빠지지 않음
  결과: market/kr_floor_bt.json · 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "kr_floor_bt.json"
SPLIT = pd.Timestamp("2013-01-01")


def load(sym):
    import yfinance as yf
    for _ in range(3):
        try:
            d = yf.download(sym, start="1997-01-01", auto_adjust=True, progress=False, threads=False)["Close"]
            d = (d.iloc[:, 0] if hasattr(d, "columns") else d).dropna()
            if len(d):
                return d
        except Exception as e:
            print("재시도", sym, e)
    return None


def weights(cl, vix, mode):
    s = cl
    c = s.values; n = len(c)
    hi = s.rolling(252, min_periods=60).max().values; dd = c / hi - 1
    m20, m50, m200 = (s.rolling(k).mean().values for k in (20, 50, 200))
    low60 = (s <= s.rolling(60, min_periods=20).min()).values
    since = s.rolling(60, min_periods=20).apply(lambda w: len(w) - 1 - int(np.argmin(w)), raw=True).values
    v = vix.reindex(s.index).ffill().values
    w = np.ones(n); bear = False; seen = False; cur = 1.0
    for i in range(1, n):
        if not bear and dd[i] <= -0.20:
            bear, seen, cur = True, bool(low60[i]), 0.0
        elif bear and dd[i] > -0.10 and m200[i] == m200[i] and c[i] > m200[i]:
            bear, cur = False, 1.0
        if bear and mode != "K100":
            if low60[i]:
                seen, cur = True, 0.0
            elif seen:
                b1 = since[i] > 10; b2 = c[i] > m20[i] and c[i - 1] > m20[i - 1]; b3 = v[i] == v[i] and v[i] < 20; b4 = c[i] > m50[i]
                nb = int(b1) + int(b2) + int(b3) + int(b4)
                if mode == "F-①④" and b1 and b4: cur = 1.0
                elif mode == "F-①②④" and b1 and b2 and b4: cur = 1.0
                elif mode == "F-3개" and nb >= 3: cur = 1.0
                elif mode == "S-계단":
                    cur = max(cur, 1.0 if (b1 and b2 and b4) else 0.5 if (b1 and b4) else cur)
                elif mode == "S-계단3":
                    cur = max(cur, 1.0 if nb >= 3 else 0.5 if (b1 and b4) else cur)
        w[i] = cur
    return w


def sim(c, w, m):
    c, w = c[m], w[m]
    nav = bh = pn = pb = 1.0; mn = mb = 0.0; wp = w[0]; sw = 0
    for i in range(1, len(c)):
        r = c[i] / c[i - 1] - 1
        nav *= 1 + wp * r + (1 - wp) * 0.02 / 252; bh *= 1 + r
        pn, pb = max(pn, nav), max(pb, bh); mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb - 1)
        if w[i] != wp:
            nav *= 1 - 0.001 * abs(w[i] - wp); sw += 1
        wp = w[i]
    y = max((len(c) - 1) / 252, 1e-9)
    return {"cagr": round((nav ** (1 / y) - 1) * 100, 2), "mdd": round(mn * 100, 1), "hold_cagr": round((bh ** (1 / y) - 1) * 100, 2), "hold_mdd": round(mb * 100, 1), "sw_y": round(sw / y, 1)}


def episodes(s, w):
    """🐻 마다: 들어간 날 · 처음 다시 담은 날 · 바닥 · K100 이 다시 산 날"""
    out = []; d = s.index; i = 1
    while i < len(w):
        if w[i] < 1 and w[i - 1] >= 1:
            j = i
            while j < len(w) and w[j] < 1: j += 1
            seg = s.iloc[i:j]
            out.append({"in": str(d[i].date()), "out": str(d[min(j, len(w) - 1)].date()), "low": str(seg.idxmin().date()) if len(seg) else None})
            i = j
        i += 1
    return out[-8:]


def main():
    vix = load("^VIX")
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "markets": []}
    MODES = ["K100", "F-①④", "F-①②④", "F-3개", "S-계단", "S-계단3"]
    for key, sym, name in (("kospi", "^KS11", "코스피"), ("kosdaq", "^KQ11", "코스닥")):
        s = load(sym)
        if s is None:
            print("시세 없음", sym); continue
        s = s[s.index >= "1998-01-01"]
        c = s.values; mf = (s.index < SPLIT); mb = ~mf; al = np.ones(len(c), bool)
        rows = {}
        for md in MODES:
            w = weights(s, vix, md)
            rows[md] = {"front": sim(c, w, mf), "back": sim(c, w, mb), "full": sim(c, w, al), "eps": episodes(s, w), "now": float(w[-1])}
        base = rows["K100"]
        for md in MODES[1:]:
            r = rows[md]
            r["d_front"] = round(r["front"]["cagr"] - base["front"]["cagr"], 2); r["d_back"] = round(r["back"]["cagr"] - base["back"]["cagr"], 2)
            r["ok"] = bool(r["d_front"] > 0 and r["d_back"] > 0 and r["full"]["mdd"] >= base["full"]["mdd"] - 5)
        res["markets"].append({"key": key, "name": name, "from": str(s.index[0].date()), "rows": rows})
        print("\n==", name, s.index[0].date(), "~", s.index[-1].date())
        for md in MODES:
            r = rows[md]
            print(f"{md:>8} | 앞 {r['front']['cagr']:>6} 낙폭 {r['front']['mdd']:>6} | 뒤 {r['back']['cagr']:>6} 낙폭 {r['back']['mdd']:>6} | 전체 {r['full']['cagr']} 낙폭 {r['full']['mdd']} (보유 {r['full']['hold_cagr']} / {r['full']['hold_mdd']}) · 1년 {r['full']['sw_y']}번"
                  + (f" | K100 대비 앞 {r['d_front']:+.2f} 뒤 {r['d_back']:+.2f} {'✅' if r['ok'] else ''}" if md != "K100" else "") + f" · 지금 주식 {r['now']:.0%}")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
