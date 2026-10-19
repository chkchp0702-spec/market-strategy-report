"""한국 심리 원천 주소 탐색 (1회용) → market/lab/sent_probe.txt"""
import urllib.request, datetime as dt
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Referer":"https://finance.naver.com/"}
d=dt.datetime.utcnow()+dt.timedelta(hours=9)
U=["https://finance.naver.com/sise/sise_deposit.naver","https://finance.naver.com/sise/sise_deposit.nhn",
"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=%s&sosok=03"%d.strftime('%Y%m%d'),
"https://finance.naver.com/sise/investorDealTrendDay.nhn?bizdate=%s&sosok=03"%d.strftime('%Y%m%d'),
"https://finance.naver.com/sise/sise_trans_style.naver?sosok=03",
"https://m.stock.naver.com/api/index/KOSPI/trend","https://m.stock.naver.com/api/index/KPI200/trend",
"https://m.stock.naver.com/api/index/FUT/trend","https://m.stock.naver.com/api/futures/FUT/trend",
"https://m.stock.naver.com/api/index/KOSPI/investorTrend","https://m.stock.naver.com/front-api/marketIndex/investorTrend?category=futures",
"https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd","https://freesis.kofia.or.kr/"]
out=[]
for u in U:
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15); b=r.read()
        for enc in ("utf-8","euc-kr"):
            try: t=b.decode(enc); break
            except: t=b.decode("utf-8","ignore")
        import re
        i=t.find("신용"); j=t.find("외국인")
        out.append(f"## {u}\nOK {r.status} {len(b)}\nHEAD: {t[:600]!r}\n신용@{i}: {t[max(0,i-200):i+1200]!r}\n외국인@{j}: {t[max(0,j-200):j+800]!r}\n")
    except Exception as e:
        out.append(f"## {u}\nERR {str(e)[:200]}\n")
open("market/lab/sent_probe.txt","w").write("\n".join(out))
