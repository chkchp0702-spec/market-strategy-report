"""🔎 ⑤ 고래 신규 + 50일선 위 후보의 야후 임원 매수 — 0건이 맞는지 확인"""
import urllib.request, json, os, sys
R = "https://raw.githubusercontent.com/chkchp0702-spec/"
get = lambda u: urllib.request.urlopen(u, timeout=30).read().decode()
os.makedirs("/tmp/sc", exist_ok=True)
open("/tmp/sc/screens.py", "w").write(get(R + "daily-app/main/opdb/screens.py")); open("/tmp/sc/subsec.py", "w").write(get(R + "daily-app/main/subsec.py"))
os.makedirs("/tmp/w/data/days", exist_ok=True)
api = json.loads(get("https://api.github.com/repos/chkchp0702-spec/whale40/contents/data/days"))
last = sorted(x["name"] for x in api if x["name"].startswith("20"))[-1]
open("/tmp/w/data/days/" + last, "w").write(get(R + "whale40/main/data/days/" + last)); open("/tmp/w/data/signals.json", "w").write(get(R + "whale40/main/data/signals.json"))
sys.path.insert(0, "/tmp/sc"); import screens, yfinance as yf
W = screens.whale_new("/tmp/w"); syms = sorted(W); print("고래 신규", len(syms), last)
px = yf.download(syms, period="6mo", progress=False, group_by="ticker", auto_adjust=False)
cand = []
for s in syms:
    try:
        c = px[s]["Close"].dropna()
        if len(c) > 50 and c.iloc[-1] > c.iloc[-50:].mean(): cand.append(s)
    except Exception: pass
print("50일선 위", len(cand), cand)
import time; t = time.time()
r = screens.insider_yahoo(cand); print("임원 매수", len(r), json.dumps(r, ensure_ascii=False), f"{time.time()-t:.0f}s")
n0 = sum(1 for s in cand[:15] if yf.Ticker(s).insider_transactions is not None)
print("내부자 표 받은 수 (앞 15개 중)", n0)
