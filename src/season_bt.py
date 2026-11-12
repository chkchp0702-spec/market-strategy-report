"""🧭 시장 계절 시계 (11/12 사용자: 「5개 국가 각각의 지수들을 백테스트 해서 현금 비중을 늘려야 할 때·주식 비중을 늘려야 할 때를
   시계나 보기 쉬운 그림으로 — 맞출 수 없다는 걸 알지만 확률을 높이고 싶어 · 어떻게든 방법을 찾아」)

  결과 보기 전 등록한 것
  ─ 지수(가격지수 · 12년 넘는 것만 검증): 🇰🇷 코스피·코스닥 · 🇯🇵 닛케이225·TOPIX(ETF 1306) · 🇨🇳 상해종합·심천성분·CSI300 · 🇭🇰 항셍·H주 · 🇺🇸 S&P500·나스닥
  ─ 계절 6개 (그날 종가로 기계 판정 · 시계 방향으로 돈다)
     🌱 봄        : 200일선 아래 · 50일선 위            (바닥에서 올라오는 중)
     ☀️ 여름      : 200일선 위 · 50일선 위
     🔥 늦여름    : 여름인데 200일선과의 거리가 그 지수의 지난 기록 상위 10% (과열 · 그날까지 자료로만 계산)
     🍂 가을      : 200일선 위 · 50일선 아래            (꺾이는 중)
     ❄️ 겨울      : 200일선 아래 · 50일선 아래
     🌤 늦겨울    : 겨울인데 60일 저점이 10거래일 넘게 안 깨지고 20일선 위 2일 연속 (바닥 다지기)
  ─ 비중 정하는 법 「확인된 계절만」: 그 계절에 주식이 현금(연 2%)을 이겼는지 지난 자료를 반으로 잘라 본다
     앞 절반·뒤 절반 둘 다 이김 → 주식 100% · 둘 다 짐 → 0% · 엇갈림 → 50%  (계절 표본 250거래일 미만이면 50%)
  ─ 검증 「걸어가며」: 매년 1월 첫 거래일에 그 전날까지 자료만으로 비중표를 다시 만들고 그 해에 씀(첫 8년은 배우는 기간 = 주식 100%)
     그날 종가 계절 → 다음 날 비중 · 현금 연 2% · 바꿀 때 0.1%  → 같은 기간 「그냥 들고 있기」와 비교 (연수익 · 최대 낙폭)
  ─ 확률: 계절마다 「60거래일(약 3개월) 뒤 올라 있을 확률 · 평균」 — 꾸밈 없이 그대로
  결과: market/season.json → 앱 🧭 계절 시계 · 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "season.json"
MK = [("kospi", "^KS11", "코스피", "kr"), ("kosdaq", "^KQ11", "코스닥", "kr"),
      ("nikkei", "^N225", "닛케이225", "jp"),   # TOPIX ETF(1306.T)는 야후 자료가 깨져(낙폭 −90%) 뺌
      ("shanghai", "000001.SS", "상해종합", "cn"), ("shenzhen", "399001.SZ", "심천성분", "cn"),   # CSI300 은 야후에 자료 없음
      ("hsi", "^HSI", "항셍", "hk"), ("hscei", "^HSCE", "항셍 H주", "hk"),
      ("sp500", "^GSPC", "S&P500", "us"), ("nasdaq", "^IXIC", "나스닥", "us")]
ST = ["spring", "summer", "hot", "autumn", "winter", "base"]
SN = {"spring": "🌱 봄", "summer": "☀️ 여름", "hot": "🔥 늦여름", "autumn": "🍂 가을", "winter": "❄️ 겨울", "base": "🌤 늦겨울"}
CASH = 0.02 / 252
COST = 0.001
MINN = 250


def load(sym):
    import yfinance as yf
    for _ in range(3):
        try:
            d = yf.download(sym, start="1985-01-01", auto_adjust=True, progress=False, threads=False)["Close"]
            d = (d.iloc[:, 0] if hasattr(d, "columns") else d).dropna()
            d = d[d > 0]
            if len(d):
                return d
        except Exception as e:
            print("재시도", sym, e)
    return None


def seasons(s):
    """→ 날짜별 계절 index(ST) (-1 = 아직 200일선 없음)"""
    c = s.values
    m20, m50, m200 = (s.rolling(k).mean().values for k in (20, 50, 200))
    gap = pd.Series(c / m200 - 1, index=s.index)
    q90 = gap.expanding(min_periods=500).quantile(0.9).shift(1).values
    low = s.rolling(60, min_periods=20)
    since = low.apply(lambda w: len(w) - 1 - int(np.argmin(w)), raw=True).values
    a20 = c > m20
    based = (since > 10) & a20 & np.roll(a20, 1)
    up, sh = c > m200, c > m50
    st = np.full(len(c), -1)
    ok = ~np.isnan(m200)
    st[ok & ~up & sh] = 0
    st[ok & up & sh] = 1
    st[ok & up & sh & (gap.values > q90)] = 2
    st[ok & up & ~sh] = 3
    st[ok & ~up & ~sh] = 4
    st[ok & ~up & ~sh & based] = 5
    return st


def table(lr, stp, lo, hi):
    """lo~hi(위치) 자료로 계절별 비중표 — stp = 전날 계절(그날 수익에 걸리는 계절)"""
    w = np.full(6, 1.0); info = []
    mid = lo + (hi - lo) // 2
    for k in range(6):
        ex = lr[lo:hi] - CASH
        m = stp[lo:hi] == k
        n = int(m.sum())
        pos = np.arange(lo, hi)
        a = ex[m & (pos < mid)]; b = ex[m & (pos >= mid)]
        if n < MINN or len(a) < 40 or len(b) < 40:
            w[k] = 0.5; info.append([n, None, None]); continue
        sa, sb = float(a.sum()), float(b.sum())
        w[k] = 1.0 if (sa > 0 and sb > 0) else 0.0 if (sa < 0 and sb < 0) else 0.5
        info.append([n, round(float(a.mean()) * 252 * 100, 1), round(float(b.mean()) * 252 * 100, 1)])
    return w, info


def perf(r, wd):
    """wd = 그날 주식 비중 배열 → (연수익, 낙폭, 1년 바꾼 횟수)"""
    ch = np.abs(np.diff(wd, prepend=wd[0]))
    d = wd * r + (1 - wd) * CASH - COST * ch
    nav = np.cumprod(1 + d)
    y = max(len(r) / 252, 1e-9)
    pk = np.maximum.accumulate(nav)
    return round(float((nav[-1] ** (1 / y) - 1) * 100), 2), round(float((nav / pk - 1).min() * 100), 1), round(float((ch > 0).sum() / y), 1)


def one(key, sym, name, nat, s):
    idx = s.index; c = s.values; n = len(c)
    st = seasons(s)
    r = np.zeros(n); r[1:] = c[1:] / c[:-1] - 1
    lr = np.log1p(r)
    stp = np.roll(st, 1); stp[0] = -1
    first = int(np.argmax(st >= 0))
    out = {"key": key, "name": name, "nat": nat, "sym": sym, "from": str(idx[first].date()), "to": str(idx[-1].date()), "years": round((n - first) / 252, 1)}
    # 지금
    j = n - 1
    while j > 0 and st[j - 1] == st[n - 1]: j -= 1
    m50, m200 = float(s.rolling(50).mean().iloc[-1]), float(s.rolling(200).mean().iloc[-1])
    out["now"] = {"st": ST[st[-1]] if st[-1] >= 0 else None, "since": str(idx[j].date()), "days": n - j, "px": round(float(c[-1]), 2),
                  "g200": round((c[-1] / m200 - 1) * 100, 1), "g50": round((c[-1] / m50 - 1) * 100, 1),
                  "dd": round(float(c[-1] / np.max(c[max(0, n - 252):]) - 1) * 100, 1)}
    # 계절별 3개월 뒤
    f60 = np.full(n, np.nan); f60[:-60] = c[60:] / c[:-60] - 1
    tot = int((st >= 0).sum())
    wfin, info = table(lr, stp, first + 1, n)
    rows = []
    for k in range(6):
        m = (st == k) & ~np.isnan(f60)
        ex = (lr - CASH)[stp == k]
        rows.append({"st": ST[k], "share": round(float((st == k).sum()) / max(tot, 1) * 100, 1), "n": int((st == k).sum()),
                     "up60": round(float((f60[m] > 0).mean()) * 100) if m.sum() >= 60 else None,
                     "avg60": round(float(np.mean(f60[m])) * 100, 1) if m.sum() >= 60 else None,
                     "ann": round(float(ex.mean()) * 252 * 100, 1) if len(ex) >= 60 else None,
                     "half": info[k][1:], "w": int(wfin[k] * 100)})
    out["states"] = rows
    out["w_now"] = int(wfin[st[-1]] * 100) if st[-1] >= 0 else None
    if out["years"] < 12:
        out["short"] = True
        return out
    # 걸어가며 검증
    wd = np.ones(n); learn = first + 8 * 252
    yrs = pd.Series(idx.year, index=range(n))
    tabs = {}
    for y in sorted(set(idx.year)):
        p0 = int(np.argmax(idx.year == y))
        if p0 < learn:
            continue
        w, _ = table(lr, stp, first + 1, p0)
        tabs[y] = [int(x * 100) for x in w]
        m = (idx.year == y)
        sp = stp[m]
        wd[m] = np.where(sp >= 0, w[np.clip(sp, 0, 5)], 1.0)
    t0 = min(learn, n - 1)
    def cut(lo, hi):
        if hi - lo < 252: return None
        a, b = perf(r[lo:hi], wd[lo:hi]), perf(r[lo:hi], np.ones(hi - lo))
        return {"cagr": a[0], "mdd": a[1], "sw_y": a[2], "hold_cagr": b[0], "hold_mdd": b[1], "from": str(idx[lo].date()), "to": str(idx[hi - 1].date())}
    mid = t0 + (n - t0) // 2
    out["wf"] = {"all": cut(t0, n), "a": cut(t0, mid), "b": cut(mid, n), "tabs": {str(k): v for k, v in list(tabs.items())[-3:]},
                 "stock_pct": round(float(wd[t0:].mean()) * 100)}
    # 참고: 지금 비중표를 처음부터 썼다면(답을 보고 푼 것)
    wi = np.where(stp >= 0, wfin[np.clip(stp, 0, 5)], 1.0)
    a, b = perf(r[first + 1:], wi[first + 1:]), perf(r[first + 1:], np.ones(n - first - 1))
    out["insample"] = {"cagr": a[0], "mdd": a[1], "hold_cagr": b[0], "hold_mdd": b[1]}
    # 최근 2년 계절 흐름(주말 기준) — 그림용
    wk = pd.Series(st, index=idx).iloc[-520:].resample("W").last().dropna().astype(int)
    out["trail"] = [[str(d.date()), int(v)] for d, v in wk.items()][-104:]
    return out


# ───────── 2차 (11/12 · 1차 결과를 본 뒤 등록): 날마다 계절 따라 바꾸면 1년 20번 넘게 바뀌어 9개 지수 중 7개가 보유에 졌음(상해·심천만 이김)
#   → 느린 방식 12개를 등록하고, 「해마다 그 전날까지 성적으로 방식을 골라 그 해에 씀」(걸어가며 고르기)으로 검증
#   방식(월말 종가로 정하고 다음 달 내내 유지 · ddl·floor 만 날마다)
#     hold 그냥 들고 있기 · ma10 10개월선 위 100/아래 0 · ma10h 아래 50 · mom12 1년 전보다 높으면 100/아니면 0
#     step2 (10개월선·1년 모멘텀) 켜진 수만큼 0/50/100 · step3 (10개월선·1년·6개월 모멘텀) 0/33/67/100
#     ddl 고점 −10% 50 · −20% 0 · 200일선 위+−10% 위면 100 (날마다)
#     floor 하락장(−20%)이면 0 → 바닥 다지기 33 → 50일선 위 67 → 200일선 위 100 · 신저가면 다시 0 (날마다 · 바닥 신호 계단)
#     deep ma10 인데 3년 고점 −35% 아래면 최소 50 (싸면 절반은 든다)
#     hal 11~4월 100 · 5~10월 50 · hal0 5~10월 0 (달력 계절)
#     season 월말 계절(6개)에 「확인된 계절만」 비중표
#   고르기: 매년 1월 — 그 전날까지 최대 낙폭이 보유보다 나쁘지 않은 방식 중 연수익 1등(없으면 hold) · 첫 10년은 배우는 기간(hold)
MN = {"hold": "그냥 들고 있기", "ma10": "10개월선 위면 주식 · 아래면 현금", "ma10h": "10개월선 아래면 절반만 현금", "mom12": "1년 전보다 높으면 주식 · 아니면 현금",
      "step2": "신호 2개 계단 (0·50·100)", "step3": "신호 3개 계단 (0·33·67·100)", "ddl": "고점 −10% 절반 · −20% 전부 현금", "floor": "하락장엔 현금 → 바닥 신호마다 3분의 1씩 담기",
      "deep": "10개월선 + 많이 싸면 절반은 들기", "hal": "11~4월 주식 · 5~10월엔 절반만", "hal0": "11~4월 주식 · 5~10월엔 현금",
      "halma": "11~4월 주식 · 5~10월엔 10개월선 위일 때만 절반", "halma2": "11~4월 주식 · 5~10월엔 10개월선 위일 때만 주식",
      "bear": "하락장(고점 −20%)이면 현금 · 풀리면 주식", "halbear": "11~4월이고 하락장이 아닐 때만 주식", "halbear2": "달력·하락장 판정 — 둘 다 좋으면 100 · 하나만 50 · 둘 다 나쁘면 0", "season": "계절표 (월말)"}


def to_daily(sig_m, idx):
    """월말에 정한 비중 → 다음 거래일부터 다음 월말까지"""
    last = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values
    d = pd.Series(np.nan, index=idx)
    v = sig_m.values
    for k, day in enumerate(last[:len(v)]):
        d.loc[day] = v[k]
    return d.ffill().shift(1).fillna(1.0).values


def methods(s, st, lr, stp, first):
    idx = s.index; c = s.values; n = len(c)
    m = s.groupby([idx.year, idx.month]).last()
    ma10 = m.rolling(10).mean()
    a = (m > ma10).astype(float).where(ma10.notna(), 1.0)
    b = (m / m.shift(12) > 1).astype(float).where(m.shift(12).notna(), 1.0)
    b6 = (m / m.shift(6) > 1).astype(float).where(m.shift(6).notna(), 1.0)
    dd3 = m / m.rolling(36, min_periods=12).max() - 1
    mon = pd.Series([k[1] % 12 + 1 for k in m.index], index=m.index)   # 월말에 정하는 건 「다음 달」 비중 (2차에선 한 달 밀려 있었음 — 고침)
    win = mon.isin([11, 12, 1, 2, 3, 4]).astype(float)
    W = {"hold": np.ones(n), "ma10": to_daily(a, idx), "ma10h": to_daily(0.5 + 0.5 * a, idx), "mom12": to_daily(b, idx),
         "step2": to_daily((a + b) / 2, idx), "step3": to_daily(((a + b + b6) / 3).round(2), idx),
         "deep": to_daily(np.maximum(a, (dd3 <= -0.35).astype(float) * 0.5), idx),
         "hal": to_daily(win * 0.5 + 0.5, idx), "hal0": to_daily(win, idx),
         # 3차(11/12 · 2차에서 달력이 한국·중국에서 통한 걸 보고 등록): 달력 + 추세
         "halma": to_daily(np.maximum(win, a * 0.5), idx), "halma2": to_daily(np.maximum(win, a), idx)}
    # 날마다 방식
    m20, m50, m200 = (s.rolling(k).mean().values for k in (20, 50, 200))
    hi = s.rolling(252, min_periods=60).max().values; dd = c / hi - 1
    low60 = (s <= s.rolling(60, min_periods=20).min()).values
    since = s.rolling(60, min_periods=20).apply(lambda w: len(w) - 1 - int(np.argmin(w)), raw=True).values
    a20 = c > m20
    w1 = np.ones(n); w2 = np.ones(n); w3 = np.ones(n); cur1 = 1.0; bear = False; cur2 = 1.0; bear3 = False
    for i in range(1, n):
        if m200[i] != m200[i]:
            continue
        # ddl
        if dd[i] <= -0.20: cur1 = 0.0
        elif dd[i] <= -0.10: cur1 = min(cur1, 0.5)
        if dd[i] > -0.10 and c[i] > m200[i]: cur1 = 1.0
        # floor
        if not bear and dd[i] <= -0.20:
            bear, cur2 = True, 0.0
        if bear:
            if low60[i]: cur2 = 0.0
            else:
                t = 1.0 if c[i] > m200[i] else 0.67 if c[i] > m50[i] else 0.33 if (since[i] > 10 and a20[i] and a20[i - 1]) else 0.0
                cur2 = max(cur2, t)
            if c[i] > m200[i] and dd[i] > -0.10:
                bear, cur2 = False, 1.0
        # bear (어제 🐻 계기판 코스피 K100 과 같은 판정): −20% 면 전부 현금 · −10% 위 + 200일선 위면 풀림
        if not bear3 and dd[i] <= -0.20: bear3 = True
        elif bear3 and dd[i] > -0.10 and c[i] > m200[i]: bear3 = False
        w1[i], w2[i], w3[i] = cur1, cur2, 0.0 if bear3 else 1.0
    W["ddl"] = np.roll(w1, 1); W["ddl"][0] = 1; W["floor"] = np.roll(w2, 1); W["floor"][0] = 1
    # 4차(11/12 · 달력은 「지금 주식」, 어제 하락장 규칙은 「지금 현금」 으로 엇갈려서 — 둘을 겹쳐 봄)
    W["bear"] = np.roll(w3, 1); W["bear"][0] = 1
    # 11/12 사용자 「실제 달력 부분은 빼자」 → 달력 방식(hal·hal0·halma·halma2·halbear·halbear2)은 겨루지 않음 · 주가 흐름 방식만
    for k in ("hal", "hal0", "halma", "halma2"):
        W.pop(k, None)
    # 월말 계절표(걸어가며)
    stm = pd.Series(st, index=idx).groupby([idx.year, idx.month]).last()
    sm = to_daily(stm.astype(float), idx).astype(int)   # 그날 걸리는 월말 계절
    sm[:first + 1] = -1
    ws = np.ones(n)
    for y in sorted(set(idx.year)):
        p0 = int(np.argmax(idx.year == y))
        if p0 < first + 5 * 252: continue
        w, _ = table(lr, sm, first + 1, p0)
        mk = idx.year == y
        ws[mk] = np.where(sm[mk] >= 0, w[np.clip(sm[mk], 0, 5)], 1.0)
    W["season"] = ws
    return W


def meta(idx, r, W, first):
    n = len(r); learn = first + 10 * 252
    wd = np.ones(n); pick = {}
    for y in sorted(set(idx.year)):
        p0 = int(np.argmax(idx.year == y))
        if p0 < learn: continue
        hc, hm, _ = perf(r[first:p0], W["hold"][first:p0])
        best, bc = "hold", hc
        for k, w in W.items():
            cg, md, _ = perf(r[first:p0], w[first:p0])
            if md >= hm and cg > bc:
                best, bc = k, cg
        pick[y] = best
        mk = idx.year == y
        wd[mk] = W[best][mk]
    return wd, pick, min(learn, n - 1)


def one2(o, s):
    idx = s.index; c = s.values; n = len(c)
    st = seasons(s)
    r = np.zeros(n); r[1:] = c[1:] / c[:-1] - 1
    lr = np.log1p(r); stp = np.roll(st, 1); stp[0] = -1
    first = int(np.argmax(st >= 0))
    W = methods(s, st, lr, stp, first)
    wd, pick, t0 = meta(idx, r, W, first)
    mid = t0 + (n - t0) // 2
    def cut(w, lo, hi):
        if hi - lo < 252: return None
        a, b = perf(r[lo:hi], w[lo:hi]), perf(r[lo:hi], np.ones(hi - lo))
        return {"cagr": a[0], "mdd": a[1], "sw_y": a[2], "hold_cagr": b[0], "hold_mdd": b[1], "from": str(idx[lo].date()), "to": str(idx[hi - 1].date())}
    o["meta"] = {"all": cut(wd, t0, n), "a": cut(wd, t0, mid), "b": cut(wd, mid, n), "pick_now": pick.get(int(idx[-1].year)), "picks": {str(k): v for k, v in list(pick.items())[-6:]},
                 "w_now": int(round(float(W[pick.get(int(idx[-1].year), "hold")][-1]) * 100)), "stock_pct": round(float(wd[t0:].mean()) * 100)}
    # 내일 비중(오늘 종가 기준) — 월말 방식은 이번 달 비중 그대로
    rows = []
    for k, w in W.items():
        A, B_, F = cut(w, t0, mid), cut(w, mid, n), cut(w, t0, n)
        if not F: continue
        rows.append({"k": k, "name": MN[k], "cagr": F["cagr"], "mdd": F["mdd"], "sw_y": F["sw_y"], "a": A["cagr"] - A["hold_cagr"] if A else None, "b": B_["cagr"] - B_["hold_cagr"] if B_ else None,
                     "both": bool(A and B_ and A["cagr"] > A["hold_cagr"] and B_["cagr"] > B_["hold_cagr"]), "w_now": int(round(float(w[-1]) * 100))})
    for x in rows:
        for q in ("a", "b"):
            if x[q] is not None: x[q] = round(x[q], 2)
    o["methods"] = sorted(rows, key=lambda x: -x["cagr"])
    # 달력: 달마다 평균·오른 비율 (앞·뒤 절반도)
    mm = s.groupby([idx.year, idx.month]).last(); mr = mm.pct_change().dropna()
    yrs = np.array([k[0] for k in mr.index]); mons = np.array([k[1] for k in mr.index]); v = mr.values
    ymid = int(np.median(yrs))
    cal = []
    for k in range(1, 13):
        x = v[mons == k]; xa = v[(mons == k) & (yrs <= ymid)]; xb = v[(mons == k) & (yrs > ymid)]
        cal.append({"m": k, "avg": round(float(x.mean()) * 100, 2), "up": round(float((x > 0).mean()) * 100), "n": int(len(x)),
                    "a": round(float(xa.mean()) * 100, 2) if len(xa) else None, "b": round(float(xb.mean()) * 100, 2) if len(xb) else None})
    o["cal"] = cal
    wv, sv = v[np.isin(mons, [11, 12, 1, 2, 3, 4])], v[~np.isin(mons, [11, 12, 1, 2, 3, 4])]
    o["halves"] = {"winter": round(float(wv.mean()) * 600, 1), "summer": round(float(sv.mean()) * 600, 1), "ymid": ymid}
    # 채택 후보: 앞·뒤 둘 다 보유를 이긴 방식 중 전체 연수익 1등 (없으면 hold)
    ok = [x for x in o["methods"] if x["both"] and x["mdd"] >= o["meta"]["all"]["hold_mdd"]]
    o["best"] = ok[0] if ok else next(x for x in o["methods"] if x["k"] == "hold")
    # 그림: 분기마다 (걸어가며 고른 것 vs 보유) 자산 곡선
    ch = np.abs(np.diff(wd, prepend=wd[0]))
    nav = np.cumprod(1 + (wd * r + (1 - wd) * CASH - COST * ch)[t0:]); bh = np.cumprod(1 + r[t0:])
    q = pd.DataFrame({"m": nav, "h": bh}, index=idx[t0:]).resample("QE").last().dropna()
    o["curve"] = [[str(d.date())[:7], round(float(a), 3), round(float(b), 3)] for d, a, b in zip(q.index, q["m"], q["h"])]
    return o


def main():
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "states": ST, "method_names": MN, "markets": []}
    for key, sym, name, nat in MK:
        s = load(sym)
        if s is None or len(s) < 300:
            print("시세 없음", sym); continue
        o = one(key, sym, name, nat, s)
        if o.get("short"):
            print("짧음", name); res["markets"].append(o); continue
        o = one2(o, s)
        res["markets"].append(o)
        nw = o["now"]; M = o["meta"]
        print(f"\n== {name} {o['from']}~{o['to']} 지금 {SN.get(nw['st'])} {nw['days']}일째 · 올해 방식 {M['pick_now']} → 주식 {M['w_now']}%  최근 고른 방식 {M['picks']}")
        for x in o["states"]:
            print(f"   {SN[x['st']]:<7} 날 {x['share']:>5}% | 3개월 뒤 오를 확률 {x['up60']}% 평균 {x['avg60']}%")
        for nm, k in (("전체", "all"), ("앞", "a"), ("뒤", "b")):
            w = M[k]
            if w: print(f"   걸어가며 고르기 {nm} {w['from']}~{w['to']}: 연 {w['cagr']}% 낙폭 {w['mdd']}% | 보유 {w['hold_cagr']}% {w['hold_mdd']}% · 1년 {w['sw_y']}번")
        print("   달력:", " ".join(f"{c['m']}월 {c['avg']:+.1f}({c['up']}%)" for c in o["cal"]), "| 11~4월 합", o["halves"]["winter"], "5~10월 합", o["halves"]["summer"])
        print("   채택 후보:", o["best"]["k"], o["best"]["cagr"], o["best"]["mdd"], "지금", o["best"]["w_now"])
        for x in o["methods"]:
            print(f"     {x['k']:>6} 연 {x['cagr']:>6}% 낙폭 {x['mdd']:>6}% 1년 {x['sw_y']:>4}번 | 보유 대비 앞 {x['a']} 뒤 {x['b']} {'✅' if x['both'] else ''} · 지금 {x['w_now']}%")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
