"""실험실 시험 — 야후에서 SPY 받아 최근 값만 적음 (lab.yml 이 도는지 확인용)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yfinance as yf
from src.conc_bt import START, OOS_START   # 공통 틀이 불러와지는지
d = yf.download("SPY", period="10d", progress=False, auto_adjust=True)
out = {"ok": True, "last": str(d.index[-1].date()), "start": START, "oos": OOS_START}
Path("market/lab/k1011_smoke.json").write_text(json.dumps(out, ensure_ascii=False))
print(out)
