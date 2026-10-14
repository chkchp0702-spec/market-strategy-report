"""🔎 아침 거르기 ⑤ 임원 매수 자료 확인: 야후 내부자 거래 · OpenInsider 접속"""
import urllib.request, importlib.util, os, json
u = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/opdb/screens.py"
src = urllib.request.urlopen(u, timeout=30).read().decode()
os.makedirs("/tmp/sc", exist_ok=True); open("/tmp/sc/screens.py", "w").write(src); open("/tmp/sc/subsec.py", "w").write(urllib.request.urlopen(u.replace("opdb/screens.py", "subsec.py")).read().decode())
import sys; sys.path.insert(0, "/tmp/sc")
import screens
print("openinsider", None if (r := screens.insider_buys()) is None else len(r))
syms = ["VST", "CDW", "COF", "AMD", "APP", "BKNG", "BE", "AEP", "CTVA", "BBY", "COO", "APA"]
r = screens.insider_yahoo(syms)
print("yahoo", json.dumps(r, ensure_ascii=False))
import yfinance as yf
print(yf.Ticker("COO").insider_transactions.head(5).to_string())
