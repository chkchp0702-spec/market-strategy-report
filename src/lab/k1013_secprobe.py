"""SEC·대체 자료원 접속 점검 (Q16-5) → market/lab/k1013_secprobe.json"""
import json, requests
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
U = ["https://www.sec.gov/files/company_tickers.json",
     "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.20261009.idx",
     "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/2025q2_form345.zip",
     "https://data.sec.gov/submissions/CIK0000320193.json",
     "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"]
UAS = ["CH-Investing-Research research-bot@users.noreply.github.com", "Mozilla/5.0 (compatible; CHInvestingBot/1.0; +https://github.com/chkchp0702-spec)",
       "CH Investing research-bot@users.noreply.github.com"]
out = []
for u in U:
    for ua in UAS:
        try:
            r = requests.get(u, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate", "Host": u.split("/")[2]}, timeout=40, stream=True)
            b = next(r.iter_content(300), b"")
            out.append({"u": u[:90], "ua": ua[:30], "code": r.status_code, "head": b[:160].decode("latin1")})
        except Exception as e:
            out.append({"u": u[:90], "ua": ua[:30], "err": repr(e)[:150]})
(ROOT / "market" / "lab" / "k1013_secprobe.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
