"""🧪 포트 규칙 7가지 중 「숫자로 정하는」 3가지 — 킥 포트에 10/12(첫 거래일)부터 적용 (10/11 사용자: "다 진행하고 킥 포트까지 바꿔봐, S&P500 이기는지 보게")
  ① 현금 = 국면 신호판 사분면으로 (2000년 이후 그 국면 뒤 3개월 S&P 성적·−10% 확률로 정한 표)
  ③ 칸 기울이기 = 칸마다 S&P 대비 3·6개월 수익 순위 → 위 1/3 ×1.25 · 아래 1/3 ×0.75 (업종 모멘텀)
  ④ 추세 브레이크 = 칸 상품이 200일선 아래면 0 · 50일선 아래이면서 S&P보다 약하면(3개월) ½ → 덜어낸 만큼 현금
  모든 판단은 「전날 종가까지」 자료로만 (미래 자료 안 씀). 검증: src/rules_bt.py (2008년 이후 섹터 ETF로).
"""
from __future__ import annotations

RULE_FROM = "2026-10-12"          # 킥 포트에 규칙을 켜는 날 (이전은 원래 계산 그대로 — 소급하지 않음)
# 국면 → 현금 % (regime.json quad_all: 3개월 S&P 평균·−10% 넘게 빠진 비율 순으로)
CASH_BY_QUAD = {"상승 국면": 5, "시장 우위": 5, "경기 속 조정": 10, "경기 우위": 15, "후반부 · 천장 조심": 15,
                "시장 약세": 15, "엇갈림": 25, "경기 약세": 35, "하락 국면": 40}
# 10/12 사용자 「ㅇㅇ」: 킥 포트 ① 현금도 🎯 판정(S&P500 200일선 위·3일 확인)으로 — src/base_bt.py 검증(상승장 현금 10%p = 연 약 −0.6%p)
CASH_BY_QUAD.update({"🟢 상승장": 0, "🔴 상승장 아님": 26})
TILT_UP, TILT_DN = 1.25, 0.75

# 🦴 변동성 맞춤 비중 (10/12 사용자 결정: "변동성 맞춤도 넣어. 늘 방어도 중요해. 기본·킥·집중에 따라 다르게") — 검증 src/skel_bt.py roles
#   주식 칸(금·현금 빼고) × 배율, 배율 = min(1, 목표 ÷ S&P500½+나스닥100½ 의 최근 lb일 실현 변동성(연율)), 아래 한도 floor · 1배 넘게 안 실음
#   덜어낸 만큼 현금·단기채 칸 · 배율은 5%p 넘게 바뀔 때만 따라감(hold_band) · 2026-10-13(다음 거래일)부터, 그 전 성적은 소급 안 함
VOL_FROM = "2026-10-13"
VOL_BAND = 0.05
# 앞 기간(2008-07~2016)에서만 고름 (market/skel_bt.json roles): 기본 = 낙폭 최소(CAGR 손해 2%p 이내) · 킥 = 샤프 1등 · 집중 = 낙폭 3%p↑ 줄인 것 중 CAGR 손해 최소
VOL_ROLES = {"base": {"role": "방어형", "lb": 20, "target": 15, "floor": 0.3},
             "kick": {"role": "중간", "lb": 20, "target": 18, "floor": 0.5},
             "conc": {"role": "공격형", "lb": 20, "target": 22, "floor": 0.7}}


def vol_line(spy, qqq, lb):
    """S&P500½+나스닥100½ 하루 수익의 lb일 실현 변동성(연율, 소수) — pandas Series"""
    r = 0.5 * spy.pct_change() + 0.5 * qqq.pct_change()
    return r.rolling(lb).std() * (252 ** 0.5)


def held_scale_line(spy, qqq, p):
    """→ (변동성 Series, 밴드 걸린 배율 Series) · p = VOL_ROLES[...]"""
    import pandas as pd
    idx = spy.index.intersection(qqq.index)
    v = vol_line(spy.reindex(idx), qqq.reindex(idx), p["lb"])
    raw = [raw_scale(x, p["target"], p["floor"]) for x in v.values]
    return v, pd.Series(hold_band(raw), index=idx)


def raw_scale(vol, target, floor):
    """vol: 연율 소수(0.14) · target: % 숫자(15) → 배율 0~1"""
    if vol is None or vol != vol or vol <= 0:
        return 1.0
    return max(floor, min(1.0, target / 100 / vol))


def hold_band(vals, band=VOL_BAND):
    """배율 줄 → 5%p 넘게 바뀔 때만 따라가는 줄 (잦은 매매 막기)"""
    out, cur = [], None
    for v in vals:
        if cur is None or abs(v - cur) >= band - 1e-9:
            cur = v
        out.append(cur)
    return out


def is_gold(name: str) -> bool:
    return name.strip() == "금" or name.startswith("금 ") or "금현물" in name


def quad(c, t):
    """daily-app regime.py 의 quad 와 같은 경계"""
    if c is None or t is None:
        return "엇갈림"
    if c >= 10 and t >= 10:
        return "상승 국면"
    if c >= 10 and t <= -10:
        return "경기 속 조정"
    if c <= -10 and t >= 10:
        return "후반부 · 천장 조심"
    if c <= -10 and t <= -10:
        return "하락 국면"
    if t >= 10:
        return "시장 우위"
    if t <= -10:
        return "시장 약세"
    if c >= 10:
        return "경기 우위"
    if c <= -10:
        return "경기 약세"
    return "엇갈림"


def is_cash(name: str) -> bool:
    return any(k in name for k in ("현금", "단기채"))


def stats_of(series_list, spy):
    """칸의 상품들(그날까지 잘린 종가 Series들) → {mom, rel63, below50, below200}. 자료가 모자라면 None"""
    rows = []
    for s in series_list:
        if s is None or len(s) < 64:
            continue
        last = float(s.iloc[-1])
        r63 = last / float(s.iloc[-64]) - 1
        r126 = last / float(s.iloc[-127]) - 1 if len(s) >= 127 else None
        m50 = float(s.iloc[-50:].mean())
        m200 = float(s.iloc[-200:].mean()) if len(s) >= 200 else None
        rows.append((r63, r126, last < m50, (last < m200) if m200 else False))
    if not rows or spy is None or len(spy) < 127:
        return None
    s63 = float(spy.iloc[-1]) / float(spy.iloc[-64]) - 1
    s126 = float(spy.iloc[-1]) / float(spy.iloc[-127]) - 1
    rel63 = sum(r[0] for r in rows) / len(rows) - s63
    r126s = [r[1] for r in rows if r[1] is not None]
    rel126 = (sum(r126s) / len(r126s) - s126) if r126s else rel63
    return {"rel63": rel63, "rel126": rel126, "mom": (rel63 + rel126) / 2,
            "below50": sum(r[2] for r in rows) / len(rows) > 0.5, "below200": sum(r[3] for r in rows) / len(rows) > 0.5}


def rule_weights(alloc, stats, qd, use=("cash", "tilt", "brake"), vol_scale=None):
    """alloc: [(이름, 비중%)] · stats: 이름 → stats_of 결과 · qd: 국면 이름 → ({이름: 새 비중}, {이름: 이유}, 현금 목표)"""
    cash_names = [n for n, _ in alloc if is_cash(n)]
    eq = [(n, p) for n, p in alloc if not is_cash(n)]
    c0 = sum(p for n, p in alloc if is_cash(n))
    T = CASH_BY_QUAD.get(qd, c0) if ("cash" in use and qd) else c0
    why = {}
    w = {n: float(p) for n, p in eq}
    if "tilt" in use:
        ranked = sorted([n for n, _ in eq if stats.get(n)], key=lambda n: -stats[n]["mom"])
        k = len(ranked) // 3
        if k:
            for n in ranked[:k]:
                w[n] *= TILT_UP; why[n] = f"강한 칸 ×{TILT_UP} (S&P 대비 3·6개월 {stats[n]['mom'] * 100:+.1f}%p)"
            for n in ranked[-k:]:
                w[n] *= TILT_DN; why[n] = f"약한 칸 ×{TILT_DN} (S&P 대비 3·6개월 {stats[n]['mom'] * 100:+.1f}%p)"
    tot = sum(w.values()) or 1
    w = {n: v / tot * (100 - T) for n, v in w.items()}
    freed = 0.0
    if "brake" in use:
        for n in list(w):
            s = stats.get(n)
            if not s:
                continue
            f = 0.0 if s["below200"] else (0.5 if s["below50"] and s["rel63"] < 0 else 1.0)
            if f < 1:
                freed += w[n] * (1 - f)
                w[n] *= f
                why[n] = ("🛑 200일선 아래 → 0" if f == 0 else "⚠️ 50일선 아래·S&P보다 약함 → ½") + (" · " + why[n] if n in why else "")
    vfreed = 0.0
    if "vol" in use and vol_scale is not None and vol_scale < 1:
        for n in list(w):
            if is_gold(n):
                continue
            vfreed += w[n] * (1 - vol_scale)
            w[n] *= vol_scale
    out = {n: round(v, 1) for n, v in w.items()}
    cash_total = round(100 - sum(out.values()), 1)
    if cash_names:
        out[cash_names[0]] = cash_total
        for n in cash_names[1:]:
            out[n] = 0.0
        why[cash_names[0]] = f"국면 「{qd}」 → 현금 {T}%" + (f" + 브레이크로 덜어낸 {freed:.1f}%p" if freed > 0.05 else "") + (f" + 🦴 변동성 맞춤으로 덜어낸 {vfreed:.1f}%p (주식 칸 ×{vol_scale:.2f})" if vfreed > 0.05 else "")
    return out, why, T
