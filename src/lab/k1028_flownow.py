"""🔄 Q10/28-2 오늘 상태 점검: 10월 60/40 쏠림(SPY·IEF, 9/30 종가 → 마지막 종가) → market/lab/k1028_flownow.json"""
import json
from pathlib import Path
import yfinance as yf
df = yf.download(["SPY", "IEF", "TLT"], start="2026-09-20", auto_adjust=True, progress=False)["Close"].dropna()
b = df[df.index < "2026-10-01"].iloc[-1]
rows = []
for d, r in df[df.index >= "2026-10-01"].iterrows():
    rs, rb = r["SPY"] / b["SPY"] - 1, r["IEF"] / b["IEF"] - 1
    ws, wb = 0.6 * (1 + rs), 0.4 * (1 + rb)
    rows.append({"d": str(d.date()), "spy": round(rs * 100, 2), "ief": round(rb * 100, 2), "drift": round((ws / (ws + wb) - 0.6) * 100, 3)})
    print(rows[-1], flush=True)
Path("market/lab/k1028_flownow.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
