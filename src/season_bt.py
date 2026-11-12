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
      ("nikkei", "^N225", "닛케이225", "jp"), ("topix", "1306.T", "TOPIX", "jp"),
      ("shanghai", "000001.SS", "상해종합", "cn"), ("shenzhen", "399001.SZ", "심천성분", "cn"), ("csi300", "000300.SS", "CSI300", "cn"),
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


def main():
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "states": ST, "markets": []}
    for key, sym, name, nat in MK:
        s = load(sym)
        if s is None or len(s) < 300:
            print("시세 없음", sym); continue
        o = one(key, sym, name, nat, s)
        res["markets"].append(o)
        nw = o["now"]
        print(f"\n== {name} {o['from']}~{o['to']} ({o['years']}년) 지금 {SN.get(nw['st'])} {nw['days']}일째 · 200일선 {nw['g200']:+}% · 권장 주식 {o['w_now']}%")
        for x in o["states"]:
            print(f"   {SN[x['st']]:<7} 날 {x['share']:>5}% | 3개월 뒤 오를 확률 {x['up60']}% 평균 {x['avg60']}% | 현금 대비 연 {x['ann']}%p (앞·뒤 {x['half']}) → 주식 {x['w']}%")
        if o.get("wf") and o["wf"]["all"]:
            for nm, k in (("전체", "all"), ("앞", "a"), ("뒤", "b")):
                w = o["wf"][k]
                if w: print(f"   걸어가며 {nm} {w['from']}~{w['to']}: 연 {w['cagr']}% 낙폭 {w['mdd']}% | 보유 {w['hold_cagr']}% {w['hold_mdd']}% · 1년 {w['sw_y']}번")
            print(f"   참고(답 보고): {o['insample']} · 평균 주식 비중 {o['wf']['stock_pct']}%")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
