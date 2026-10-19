"""한국 심리 원천: ① 외국인·개인·기관 선물/현물 일별 1년치 backfill ② 증시자금동향 JS 에서 API 주소 찾기 → market/lab/"""
import urllib.request, re, json, datetime as dt, time
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Referer":"https://m.stock.naver.com/"}
def g(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15).read().decode("utf-8","ignore")
rows={}
d=dt.date(2026,10,19)
for i in range(560):
    day=d-dt.timedelta(days=i)
    if day.weekday()>=5: continue
    b=day.strftime("%Y%m%d"); r={}
    for k in ("FUT","KOSPI"):
        try:
            j=json.loads(g(f"https://m.stock.naver.com/api/index/{k}/trend?bizdate={b}"))
            if j.get("bizdate")!=b: continue
            f=lambda x:int(str(j.get(x) or "0").replace(",","").replace("+",""))
            r[k]=[f("personalValue"),f("foreignValue"),f("institutionalValue")]
        except Exception as e: r[k+"_err"]=str(e)[:60]
    if "FUT" in r or "KOSPI" in r: rows[day.isoformat()]=r
    time.sleep(0.05)
json.dump(rows,open("market/lab/kr_flow_hist.json","w"),separators=(",",":"))
out=[f"flow rows {len(rows)}"]
t=g("https://finance.naver.com/sise/sise_deposit.naver")
js=[u for u in re.findall(r'src="([^"]+\.js)"',t) if "deposit" in u or "page" in u]
for u in js[:6]:
    try:
        s=g(u)
        for m in re.findall(r'["`\']([^"`\']*(?:api|front-api|deposit|credit)[^"`\']*)["`\']',s)[:40]: out.append(u.split('/')[-1]+" :: "+m[:200])
    except Exception as e: out.append(u+" ERR "+str(e)[:80])
for u in ["https://m.stock.naver.com/front-api/market/deposit?page=1","https://m.stock.naver.com/api/market/deposit","https://finance.naver.com/api/sise/deposit","https://m.stock.naver.com/front-api/stock/domestic/deposit"]:
    try: out.append(u+" => "+g(u)[:300])
    except Exception as e: out.append(u+" ERR "+str(e)[:80])
open("market/lab/sent_probe.txt","w").write("\n".join(out))
