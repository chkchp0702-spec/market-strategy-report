"""🔄 연기금 월말 리밸런싱 앞지르기 (10/28 사용자 「2번 연기금 실행해」 — Q10/28-2)

  💼 기본 포트 + 🎯 집중 포트(10/28 Q10/28-3, src/conc_port.py · 근거 lab k1028_qflow) · ⚡ 킥 기본 칸은 그대로. 매달 마지막 K=5 미국 거래일 동안:
   그달 첫 거래일부터 「보유일 이틀 전 종가」까지 SPY·IEF 로 셈한 60/40 펀드 주식 비중 쏠림 drift
   (= 0.6(1+rS) / (0.6(1+rS)+0.4(1+rB)) − 0.6) 을 봄 — 검증과 같은 「하루 늦은 체결」(lab k1028_rebalflow4 lag2)
   · drift > +0.5%p (펀드가 주식 팔 차례) → 💼 주식 칸(현금·금 아닌 칸)의 60% 를 미국 장기채(TLT) 칸으로
   · drift < −0.5%p (펀드가 주식 살 차례) → 금·🧭 추세·현금 칸의 60% 를 주식 칸으로(지금 비중대로 나눔)
   · 그 밖의 날은 지금 규칙 그대로 · 레버리지 없음(비중 합 1) · 소급 없음(FLOW_FROM 부터)
  근거: market/lab/k1028_rebalflow4.json(💼 2017~ 연 +2.45%p·샤프 1.17→1.32·낙폭 −16.4→−15.3 / 2008-07~16 +3.67%p) ·
        k1028_rebalflow2.json(대조군 「마지막 5일 늘 주식/채권」 0 근처 → 달력 효과 아님) · 발상 NBER w33554
"""
from __future__ import annotations
import datetime as dt

FLOW_FROM = "2026-10-29"     # 이 날(미국 거래일) 수익부터 반영
K, TH, F = 5, 0.005, 0.60
NAME = "🔄 월말 흐름(장기채)"
BOND = "TLT"
SIG_EQ, SIG_BD = "SPY", "IEF"


def _nyse_holidays(y: int) -> set:
    """뉴욕증시 휴장일(주요 규칙) — 앞으로 며칠 거래일 셈에만 씀(지난 날은 실제 SPY 달력)"""
    def obs(d):
        return d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d

    def nth(m, wd, n):
        d = dt.date(y, m, 1)
        while d.weekday() != wd:
            d += dt.timedelta(days=1)
        return d + dt.timedelta(weeks=n - 1)

    def last(m, wd):
        d = dt.date(y, m + 1, 1) - dt.timedelta(days=1) if m < 12 else dt.date(y, 12, 31)
        while d.weekday() != wd:
            d -= dt.timedelta(days=1)
        return d
    # 부활절(그레고리력) → 성금요일
    a = y % 19; b = y // 100; c = y % 100; d_ = b // 4; e = b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d_ - g + 15) % 30; i = c // 4; k = c % 4; l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451; mo = (h + l_ - 7 * m + 114) // 31; da = ((h + l_ - 7 * m + 114) % 31) + 1
    gf = dt.date(y, mo, da) - dt.timedelta(days=2)
    return {obs(dt.date(y, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), gf, last(5, 0), obs(dt.date(y, 6, 19)),
            obs(dt.date(y, 7, 4)), nth(9, 0, 1), nth(11, 3, 4), obs(dt.date(y, 12, 25))}


def _is_td(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in _nyse_holidays(d.year)


def left_in_month(d1, cal_dates: set) -> int:
    """d1 뒤로 그달에 남은 거래일 수(d1 제외). 0 이면 d1 이 그달 마지막 거래일"""
    d = d1.date() if hasattr(d1, "date") else d1
    n, x = 0, d + dt.timedelta(days=1)
    while x.month == d.month:
        if (x in cal_dates) if x <= max(cal_dates) else _is_td(x):
            n += 1
        x += dt.timedelta(days=1)
    return n


def drift_at(C, cal, d1):
    """보유일 d1 에 쓸 쏠림: 그달 첫 거래일 전날 종가 → d1 이틀 전 거래일 종가 (없으면 None)"""
    import pandas as pd
    eq, bd = C.get(SIG_EQ), C.get(SIG_BD)
    if eq is None or bd is None:
        return None
    d1 = pd.Timestamp(d1)
    past = [d for d in cal if d < d1]
    if len(past) < 2:
        return None
    t = past[-2]                                   # 하루 늦은 체결: d1 직전 거래일(d0) 의 하루 전
    m0 = [d for d in eq.index if d < pd.Timestamp(d1.year, d1.month, 1)]
    if not m0 or t < pd.Timestamp(d1.year, d1.month, 1):
        return None
    b = m0[-1]
    try:
        rs = float(eq[eq.index <= t].iloc[-1] / eq[eq.index <= b].iloc[-1] - 1)
        rb = float(bd[bd.index <= t].iloc[-1] / bd[bd.index <= b].iloc[-1] - 1)
    except Exception:
        return None
    ws, wb = 0.6 * (1 + rs), 0.4 * (1 + rb)
    return ws / (ws + wb) - 0.6


def state(C, cal, d1):
    """→ (sig: +1 채권 쪽 · −1 주식 쪽 · 0, drift, 남은 거래일)"""
    ds = d1.strftime("%Y-%m-%d")
    cd = {d.date() for d in cal}
    left = left_in_month(d1, cd)
    if ds < FLOW_FROM or left >= K:
        return 0, None, left
    dr = drift_at(C, cal, d1)
    if dr is None:
        return 0, None, left
    return (1 if dr > TH else -1 if dr < -TH else 0), dr, left


def apply(w: dict, sig: int, is_eq, is_side) -> dict:
    """w: {칸: 비중%} → 월말 흐름 반영한 새 dict. is_eq(name) 주식 칸 · is_side(name) 금·추세·현금 칸"""
    w = dict(w)
    if sig > 0:
        mv = 0.0
        for k in list(w):
            if is_eq(k):
                x = w[k] * F; w[k] -= x; mv += x
        w[NAME] = w.get(NAME, 0.0) + mv
    elif sig < 0:
        eqk = [k for k in w if is_eq(k) and w[k] > 0]
        tot = sum(w[k] for k in eqk)
        if tot > 0:
            mv = 0.0
            for k in list(w):
                if is_side(k):
                    x = w[k] * F; w[k] -= x; mv += x
            for k in eqk:
                w[k] += mv * w[k] / tot
    return w
