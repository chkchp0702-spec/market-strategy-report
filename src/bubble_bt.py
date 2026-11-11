"""🕰 버블 시계 과거 재현 백테스트 (11/11 사용자: 「몇 시가 되면 현금화를 시작해야 돼?」 → 「다 해」)

  앱 버블 시계(daily-app/ux1110b.js)와 같은 계산을 1999년부터 매일 다시 돌려
  「시계가 ○시를 넘으면 주식 몫을 현금으로」 했다면 그냥 들고 있기보다 나았는지 본다.

  결과 보기 전 등록한 것 (바꾸려면 이 글과 bubble_bt.json rules 를 같이 고친다)
  ─ 시계 계산 = 앱과 같음: 칸 점수 🔴1 · 🟠½ · 🟢0 → 단계 점수 = 칸 평균 · 단계마다 3시간 · 앞 단계가 ¾ 넘어야 다음 단계
  ─ 손 칸(빅테크 FCF·회사채 발행·AI CDS·규제)은 과거 자료가 없어 기계 칸으로만 다시 만든 「대리 시계」:
     💳 신용   ① 하이일드÷국채 = 뱅가드 하이일드(VWEHX) ÷ 중기국채(VFITX) — 앱의 HYG/IEF 와 같은 규칙(20일 −1.5%↓ 또는 60일 −3%↓ 🔴 · 20일 −0.5%↓ 🟠)
               ② 하이일드 펀드 1년 고점 대비 −5%↓ 🔴 · −2%↓ 🟠 (앱의 회사채·CDS 칸 대신)
     📈 금리   ③ 10년물 5% 위 5일 연속 🔴 · 4.75%↑ 🟠 (앱과 같음)   ④ 유가 브렌트(없으면 WTI) 100$ 🔴 · 90$ 🟠 (앱과 같음)
     🧊 속살   ⑤ 동일가중 S&P(RSP · 2003년 전엔 NYSE 종합 ^NYA) 1년 고점 −15% 🔴 · −8% 🟠
               ⑥ 방어 3종 − 기술 20일 +3%p 🟠 · 나스닥100 하루 −5%↓ + 방어주도 하락 + 신용 20일 하락이 최근 20일 안에 🔴 (앱과 같음)
     🛟 완충   ⑦ 장단기 금리차(10년 − 3개월) 1년 안에 뒤집혔다가 지금 +0.5%p 넘게 다시 벌어짐 🔴 · 지금 뒤집힘 🟠 (경기침체 칸 대신)
               ⑧ 3개월 금리가 6개월 새 1%p 넘게 내렸는데(급히 내림) S&P 가 200일선 아래 🔴 · 200일선 아래만 🟠 (반등 완충 칸 대신)
  ─ 매매: 그날 종가로 시계 → 다음 날 비중 · 시계 ≥ T 면 주식 몫의 c% 를 현금 · 시계가 T − 1.5시간 아래로 내려오면 다시 다 삼
          T ∈ {3, 4.5, 6, 7.5, 9} · c ∈ {50, 100} · 추가로 「T 넘고 + 지수가 200일선 아래일 때만」(확인형) 판
          현금 연 2% · 비중 바꿀 때 0.1% · 가격지수(배당 제외) — 🐻 계기판 백테스트와 같은 조건
  ─ 고르는 법: 2012년까지(앞)에서 고르고 2013년부터(뒤)에서 확인 — 앞·뒤 둘 다 보유를 이겨야 「검증됨」
  ─ 시장: S&P500 · 나스닥 · 코스피(미국 버블 신호를 한국에 쓰면?)
  결과: market/bubble_bt.json → 앱 버블 경보판 「🕰 과거엔?」 · 🐻 계기판 연결 여부는 이 결과로 정한다. 매수·매도 추천 아님.
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
OUT = ROOT / "market" / "bubble_bt.json"
SYMS = ["VWEHX", "VFITX", "^TNX", "^IRX", "BZ=F", "CL=F", "RSP", "^NYA", "XLP", "XLV", "XLU", "XLK", "^NDX", "^GSPC", "^IXIC", "^KS11"]
MKTS = [("sp500", "^GSPC", "S&P500"), ("nasdaq", "^IXIC", "나스닥"), ("kospi", "^KS11", "코스피")]
TS, CS = [3, 4.5, 6, 7.5, 9], [50, 100]
SPLIT = "2013-01-01"
STAGES = [("💳 신용", ["credit", "hydd"]), ("📈 금리·유가", ["rate", "oil"]), ("🧊 주식 속살·현금 도피", ["breadth", "flow"]), ("🛟 완충 꺼짐", ["curve", "buffer"])]
CRISES = [("닷컴 2000~02", "1999-06-01", "2002-12-31"), ("금융위기 2007~09", "2007-01-01", "2009-06-30"),
          ("유럽 2011", "2011-01-01", "2011-12-31"), ("코로나 2020", "2020-01-01", "2020-06-30"), ("긴축 2022", "2021-10-01", "2022-12-31"),
          ("관세 2025", "2025-01-01", "2025-06-30"), ("지금 2026", "2026-06-01", "2026-12-31")]


def load():
    import yfinance as yf
    px = {}
    for s in SYMS:   # 하나씩(동시 받기는 야후 캐시 잠김으로 ^TNX 가 빠졌음)
        for _ in range(3):
            try:
                d = yf.download(s, start="1997-01-01", auto_adjust=True, progress=False, threads=False)["Close"]
                d = (d.iloc[:, 0] if hasattr(d, "columns") else d).dropna()
                if len(d):
                    px[s] = d; break
            except Exception as e:
                print("시세 재시도", s, e)
        if s not in px:
            print("시세 실패", s)
    return px


def cells(px):
    """날짜 × 칸 → 1(🔴) · 0.5(🟠) · 0(🟢) · NaN(자료 없음)"""
    idx = px["^GSPC"].index
    A = lambda s: px[s].reindex(idx).ffill() if s in px else pd.Series(np.nan, index=idx)
    C = pd.DataFrame(index=idx)
    # ① 신용
    r = (A("VWEHX") / A("VFITX"))
    c20, c60 = r.pct_change(20) * 100, r.pct_change(60) * 100
    C["credit"] = np.where((c20 <= -1.5) | (c60 <= -3), 1, np.where(c20 <= -0.5, 0.5, 0.0))
    C.loc[r.isna() | c60.isna(), "credit"] = np.nan
    # ② 하이일드 낙폭
    hy = A("VWEHX"); dd = (hy / hy.rolling(252, min_periods=120).max() - 1) * 100
    C["hydd"] = np.where(dd <= -5, 1, np.where(dd <= -2, 0.5, 0.0)); C.loc[dd.isna(), "hydd"] = np.nan
    # ③ 10년물
    t = A("^TNX"); t = t.where(t < 20, t / 10)
    C["rate"] = np.where(t.rolling(5).min() >= 5, 1, np.where(t >= 4.75, 0.5, 0.0)); C.loc[t.isna(), "rate"] = np.nan
    # ④ 유가
    oil = A("BZ=F").combine_first(A("CL=F"))
    C["oil"] = np.where(oil >= 100, 1, np.where(oil >= 90, 0.5, 0.0)); C.loc[oil.isna(), "oil"] = 0.0   # 2000년 8월 전 유가 30$ 안팎 → 🟢
    # ⑤ 속살
    eq = A("RSP"); ny = A("^NYA")
    ddr = (eq / eq.rolling(252, min_periods=200).max() - 1) * 100
    ddn = (ny / ny.rolling(252, min_periods=200).max() - 1) * 100
    b = ddr.combine_first(ddn)
    C["breadth"] = np.where(b <= -15, 1, np.where(b <= -8, 0.5, 0.0)); C.loc[b.isna(), "breadth"] = np.nan
    # ⑥ 순환 vs 도피
    dfn = sum(A(k).pct_change(20) for k in ("XLP", "XLV", "XLU")) / 3 * 100
    tec = A("XLK").pct_change(20) * 100
    q1 = A("^NDX").pct_change() * 100
    d1 = sum(A(k).pct_change() for k in ("XLP", "XLV", "XLU")) / 3
    crash = ((q1 <= -5) & (d1 < 0)).astype(float).rolling(20, min_periods=1).max() > 0
    C["flow"] = np.where(crash & (c20 < 0), 1, np.where(dfn - tec >= 3, 0.5, 0.0)); C.loc[tec.isna(), "flow"] = np.nan
    # ⑦ 장단기 금리차
    irx = A("^IRX"); sp = (t - irx)
    inv1y = (sp < 0).astype(float).rolling(252, min_periods=60).max() > 0
    C["curve"] = np.where(inv1y & (sp > 0.5), 1, np.where(sp < 0, 0.5, 0.0)); C.loc[sp.isna(), "curve"] = np.nan
    # ⑧ 완충
    g = A("^GSPC"); below = g < g.rolling(200).mean()
    cut = (irx.shift(126) - irx) >= 1
    C["buffer"] = np.where(cut & below, 1, np.where(below, 0.5, 0.0))
    return C


def clock(C):
    h = pd.Series(0.0, index=C.index)
    go = pd.Series(True, index=C.index)
    comps = {}
    for nm, ks in STAGES:
        comp = C[ks].mean(axis=1, skipna=True).fillna(0)
        comps[nm] = comp
        h = h + np.where(go, 3 * comp, 0)
        go = go & (comp >= 0.75)
    return (np.round(h * 2) / 2).astype(float), comps


def run(cl, hh, T, cpct, confirm=False, lo=None, hi=None):
    """다음 날 비중 · 현금 연 2% · 바꿀 때 0.1% → (cagr, mdd, 바꾼 횟수/년, 현금 날 비율)"""
    ma = cl.rolling(200).mean()
    d = cl.index
    m = (d >= (lo or d[0])) & (d < (hi or d[-1] + pd.Timedelta(days=1)))
    c, h, a = cl[m].values, hh[m].values, ma[m].values
    nav, bh, pn, pb, mn, mb, w, sw, cd, on = 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0, 0, False
    for i in range(1, len(c)):
        r1 = c[i] / c[i - 1] - 1
        nav *= 1 + w * r1 + (1 - w) * 0.02 / 252
        bh *= 1 + r1
        pn, pb = max(pn, nav), max(pb, bh)
        mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb - 1)
        if not on and h[i] >= T and (not confirm or (a[i] == a[i] and c[i] < a[i])):
            on = True
        elif on and (h[i] < T - 1.5 or (confirm and a[i] == a[i] and c[i] > a[i] and h[i] < T)):
            on = False
        nw = 1 - cpct / 100 if on else 1.0
        if nw != w:
            nav *= 1 - 0.001 * abs(nw - w); sw += 1
        w = nw; cd += on
    yrs = max((len(c) - 1) / 252, 1e-9)
    return {"cagr": round((nav ** (1 / yrs) - 1) * 100, 2), "mdd": round(mn * 100, 1),
            "hold_cagr": round((bh ** (1 / yrs) - 1) * 100, 2), "hold_mdd": round(mb * 100, 1),
            "sw_y": round(sw / yrs, 1), "cash_pct": round(cd / max(len(c) - 1, 1) * 100, 1)}


def first_reach(hh, cl, lo, hi):
    """구간 안에서 처음 3·6·9시 닿은 날과 그날 지수 고점 대비 · 그 뒤 바닥까지"""
    s = hh[(hh.index >= lo) & (hh.index <= hi)]
    c = cl.reindex(s.index).ffill()
    if not len(s):
        return None
    pk = cl[cl.index <= hi].rolling(504, min_periods=1).max().reindex(s.index)
    out = {"max": float(s.max()), "max_d": str(s.idxmax().date())}
    trough_d = c.idxmin()
    out["trough"] = {"d": str(trough_d.date()), "dd": round((float(c.min()) / float(pk.loc[trough_d]) - 1) * 100, 1)}
    for T in (3, 6, 9):
        hit = s[s >= T]
        if len(hit):
            d0 = hit.index[0]
            later = c[c.index >= d0]
            out[str(T)] = {"d": str(d0.date()), "dd": round((float(c.loc[d0]) / float(pk.loc[d0]) - 1) * 100, 1),
                           "then": round((float(later.min()) / float(c.loc[d0]) - 1) * 100, 1)}
    return out


def main():
    px = load()
    C = cells(px)
    hh, comps = clock(C)
    start = C.dropna(subset=["credit", "breadth", "flow"]).index[0]
    hh = hh[hh.index >= start]
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "from": str(start.date()), "to": str(hh.index[-1].date()),
           "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(),
           "now": {"h": float(hh.iloc[-1]), "cells": {k: (None if pd.isna(v) else float(v)) for k, v in C.iloc[-1].items()}},
           "dist": {str(T): round(float((hh >= T).mean() * 100), 1) for T in TS}, "markets": [], "crises": []}
    gsp = px["^GSPC"]
    for nm, lo, hi in CRISES:
        fr = first_reach(hh, gsp, pd.Timestamp(lo), pd.Timestamp(hi))
        if fr:
            res["crises"].append({"name": nm, **fr})
    for key, sym, name in MKTS:
        cl = px.get(sym)
        if cl is None:
            continue
        cl = cl[cl.index >= start]
        h2 = hh.reindex(cl.index).ffill().fillna(0)
        grid = []
        for confirm in (False, True):
            for T in TS:
                for c in CS:
                    a = run(cl, h2, T, c, confirm, hi=pd.Timestamp(SPLIT))
                    b = run(cl, h2, T, c, confirm, lo=pd.Timestamp(SPLIT))
                    f = run(cl, h2, T, c, confirm)
                    grid.append({"T": T, "c": c, "confirm": confirm, "front": a, "back": b, "full": f,
                                 "edge_front": round(a["cagr"] - a["hold_cagr"], 2), "edge_back": round(b["cagr"] - b["hold_cagr"], 2),
                                 "ok": bool(a["cagr"] > a["hold_cagr"] and b["cagr"] > b["hold_cagr"])})
        best = max(grid, key=lambda g: g["edge_front"])   # 앞에서 고른 판
        res["markets"].append({"key": key, "name": name, "grid": grid,
                               "pick": {"T": best["T"], "c": best["c"], "confirm": best["confirm"],
                                        "edge_front": best["edge_front"], "edge_back": best["edge_back"], "ok": best["ok"],
                                        "full": best["full"]},
                               "n_ok": int(sum(g["ok"] for g in grid))})
    # 시계 흐름(월말) — 앱 그림용
    mo = hh.resample("ME").max()
    res["monthly"] = [[str(d.date())[:7], float(v)] for d, v in mo.items()]
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    print("지금 대리 시계", res["now"]["h"], res["now"]["cells"])
    print("시계 분포 ≥T 날 비율", res["dist"])
    for c in res["crises"]:
        print(c)
    for m in res["markets"]:
        print(m["name"], "앞에서 고른 판", m["pick"], "앞·뒤 둘 다 이긴 판", m["n_ok"], "/", len(m["grid"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
