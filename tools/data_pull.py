"""시세 받기 도구 — 입력한 티커들의 일봉(종가·수정종가)을 CSV 로 만든다. 저장소에 커밋하지 않고 Actions 결과물(artifact)로만 남긴다.
   python tools/data_pull.py "^GSPC,SPY" 1950-01-01 out/
"""
import sys, os
import pandas as pd
import yfinance as yf

ticks = [t.strip() for t in sys.argv[1].split(",") if t.strip()]
start, out = sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
for t in ticks:
    try:
        h = yf.Ticker(t).history(start=start, interval="1d", auto_adjust=False, actions=True)
        if len(h):
            h.index = h.index.tz_localize(None) if h.index.tz is not None else h.index
            h.to_csv(os.path.join(out, t.replace("^", "_").replace("=", "_") + ".csv"))
            print(t, len(h), h.index[0].date(), h.index[-1].date(), round(float(h["Close"].iloc[-1]), 2))
        else:
            print(t, "없음")
    except Exception as e:
        print(t, "실패", e)
    try:
        info = yf.Ticker(t).fast_info
        print("  last", t, getattr(info, "last_price", None))
    except Exception:
        pass
