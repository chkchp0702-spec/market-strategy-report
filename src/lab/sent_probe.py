"""한국 심리 원천 주소 탐색 (1회용) → market/lab/sent_probe.txt"""
import urllib.request, re
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Referer":"https://finance.naver.com/"}
t=urllib.request.urlopen(urllib.request.Request("https://finance.naver.com/sise/sise_deposit.naver",headers=UA),timeout=15).read().decode("utf-8","ignore")
out=[]
i=t.find("<tbody"); out.append("TBODY: "+t[i:i+5000])
for k in ("credit","Credit","deposit","Deposit","loan"):
    for m in list(re.finditer(k,t))[:3]:
        out.append(f"KEY {k}@{m.start()}: "+t[max(0,m.start()-300):m.start()+700])
for m in list(re.finditer(r'20\d\d[.\-]?\d\d[.\-]?\d\d',t))[:5]:
    out.append(f"DATE@{m.start()}: "+t[max(0,m.start()-200):m.start()+500])
for u in ["https://m.stock.naver.com/api/index/FUT/trend?bizdate=20261016","https://m.stock.naver.com/api/index/KOSPI/trend?bizdate=20261016","https://m.stock.naver.com/api/index/CALL/trend","https://m.stock.naver.com/api/index/PUT/trend","https://m.stock.naver.com/api/index/KPI200/price?pageSize=3&page=1"]:
    try: out.append(u+" => "+urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15).read().decode()[:400])
    except Exception as e: out.append(u+" ERR "+str(e)[:100])
open("market/lab/sent_probe.txt","w").write("\n\n".join(out))
