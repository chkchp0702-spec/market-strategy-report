"""🧭 덜어낸 현금 → 자산 추세 칸 주차 (10/28 사용자 「1번 실행해」 — Q10/28-1)

  💼 기본 · 🎯 집중 포트에서 변동성 맞춤·국면으로 덜어낸 현금(현금·단기채 칸 전부)을 PARK_FROM 부터
  13주 국채(SGOV) 대신 🧭 자산 추세 칸에 둔다. 추세 칸 규칙 = ⚡ 킥의 🧭 칸과 같음(src/kick_ideas_bt.py trend_run):
  9종(GLD USO TLT UUP SPY QQQ EFA EEM DBC) 100일 고가 돌파 → 다음 날 종가에 삼 · 50일 저가 이탈 → 다음 날 종가에 팖 ·
  60일 변동성 반비례(한 종목 35% 한도) · 안 든 몫은 SGOV · 사고팔 때 왕복 0.5%.
  근거 market/lab/k1028_bundle.json(지금 실제 규칙 위 S2→S3): 2017~ 연 +0.57%p · 2008-07~16 +0.66%p · 낙폭 거의 그대로 /
  k1026_trendpark.json 💼 +0.63·+0.70%p · 🎯 +0.38%p·낙폭 −22.8→−21.3. 레버리지 없음(비중 합 1) · 소급 없음.
"""
from __future__ import annotations
import datetime as dt

PARK_FROM = "2026-10-29"           # 이 날(미국 거래일) 수익부터 반영 — 그 전은 지금 그대로(현금·단기채)
NIN, NOUT, WMODE = 100, 50, "risk"
NAME = "🧭 자산 추세"
LAST_PX: dict = {}                 # trend_nav 가 채움: 9종 + SGOV 마지막 종가
TNAME = {"GLD": "금", "USO": "원유", "TLT": "미국 장기채", "UUP": "달러", "SPY": "S&P500", "QQQ": "나스닥100",
         "EFA": "선진국 주식", "EEM": "신흥국 주식", "DBC": "원자재", "SGOV": "단기채(빈 몫)"}


def trend_nav(start: str):
    """→ (nav: pd.Series[날짜→값], open: [{sym, d, w, r, now}], 빈 몫 비율) · 실패하면 (None, [], 1.0)"""
    import pandas as pd
    import yfinance as yf
    from src.kick_ideas_bt import TREND_U, trend_run
    st = (dt.date.fromisoformat(start) - dt.timedelta(days=500)).isoformat()
    try:
        df = yf.download(TREND_U + ["SGOV"], start=st, auto_adjust=True, progress=False, group_by="ticker", threads=True)
    except Exception as e:
        print("🧭 추세 칸 시세 실패", e)
        return None, [], 1.0
    px = {}
    for t in TREND_U + ["SGOV"]:
        try:
            x = df[t].rename(columns=str.lower)[["high", "low", "close"]].dropna()
            if len(x) > NIN + 5:
                px[t] = x
        except Exception:
            pass
    for t, x in px.items():
        LAST_PX[t] = round(float(x["close"].iloc[-1]), 2)
    sg = px.pop("SGOV", None)
    if len(px) < len(TREND_U) - 1:          # 9종 중 1개 넘게 빠지면 쓰지 않음(현금 그대로)
        print("🧭 추세 칸 시세 모자람", sorted(px))
        return None, [], 1.0
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(v.index) for v in px.values()])))
    cd = sg["close"].pct_change().reindex(allidx).fillna(0) if sg is not None else pd.Series(0.0, index=allidx)
    s, _tr, op = trend_run(px, cd, NIN, NOUT, WMODE)
    nav = (1 + s).cumprod()
    for o in op:
        c = px[o["sym"]]["close"]
        o["now"] = round(float(c.iloc[-1]), 2)
        o["name"] = TNAME.get(o["sym"], o["sym"])
    idle = max(0.0, 1 - sum(o["w"] for o in op))
    return nav, op, idle


def ret_between(nav, d0, d1) -> float:
    """nav 의 d0 종가 → d1 종가 수익 (날짜 이전 마지막 값 사용)"""
    if nav is None:
        return 0.0
    a = nav[nav.index <= d0]
    b = nav[nav.index <= d1]
    if not len(a) or not len(b):
        return 0.0
    return float(b.iloc[-1] / a.iloc[-1] - 1)
