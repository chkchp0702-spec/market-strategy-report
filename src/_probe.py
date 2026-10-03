"""수집 경로 탐색용 (일회성). 결과를 market/_probe.json 에 남긴다."""
import json, urllib.request, urllib.parse, http.cookiejar, sys, re
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"*/*","Accept-Language":"ko,en;q=0.8"}
out={}
def get(url,hdr=None,opener=None):
    req=urllib.request.Request(url,headers={**UA,**(hdr or {})})
    o=opener or urllib.request.build_opener()
    with o.open(req,timeout=20) as r: return r.status, r.read()
def probe(name,url,hdr=None,opener=None):
    try:
        st,b=get(url,hdr,opener); out[name]={"status":st,"len":len(b),"head":b[:300].decode("utf-8","ignore")}
    except Exception as e: out[name]={"error":str(e)[:200]}
# yahoo crumb flow
try:
    cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try: op.open(urllib.request.Request("https://fc.yahoo.com",headers=UA),timeout=20)
    except Exception: pass
    st,crumb=get("https://query2.finance.yahoo.com/v1/test/getcrumb",opener=op); crumb=crumb.decode()
    out["yahoo_crumb"]={"status":st,"crumb_len":len(crumb)}
    probe("yahoo_v7_quote",f"https://query2.finance.yahoo.com/v7/finance/quote?symbols=%5EGSPC,KRW%3DX&crumb={urllib.parse.quote(crumb)}",opener=op)
    probe("yahoo_v8_chart_cookie","https://query2.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5d&interval=1d",opener=op)
except Exception as e: out["yahoo_crumb"]={"error":str(e)[:200]}
probe("stooq_light","https://stooq.com/q/l/?s=^spx,usdkrw,10yusy.b,cl.f,cb.f,gc.f,^kospi,^ndq&f=sd2t2ohlcv&h&e=csv")
probe("stooq_pl","https://stooq.pl/q/d/l/?s=^spx&i=d")
probe("naver_nhn","https://finance.naver.com/sise/investorDealTrendDay.nhn?bizdate=20261002&sosok=01")
probe("naver_sise_day","https://finance.naver.com/sise/sise_index_day.naver?code=KOSPI")
probe("naver_m_price","https://m.stock.naver.com/api/index/KOSPI/price?pageSize=5&page=1")
probe("naver_m_basic","https://m.stock.naver.com/api/index/KOSPI/basic")
probe("naver_m_investor","https://m.stock.naver.com/api/index/KOSPI/investor")
probe("naver_m_trend","https://m.stock.naver.com/api/index/KOSPI/trend?pageSize=5")
probe("naver_api_stock","https://api.stock.naver.com/index/KOSPI/investor")
probe("naver_polling","https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI")
probe("naver_world","https://api.stock.naver.com/index/.INX/basic")
probe("fred_dgs10","https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
probe("cnbc_quote","https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=.SPX|.KS11|KRW=|@CL.1|@LCO.1|@GC.1&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
probe("investing","https://api.investing.com/api/financialdata/historical/166?start-date=2026-09-01&end-date=2026-10-03&time-frame=Daily&add-missing-rows=false",{"domain-id":"kr"})
probe("wsj_marketdata","https://www.wsj.com/market-data/quotes/index/XX/SPX")
probe("ecos","https://ecos.bok.or.kr/api/")
probe("krx_json","http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd")
try:
    import subprocess; subprocess.run([sys.executable,"-m","pip","install","-q","yfinance"],check=False)
    import yfinance as yf
    df=yf.download(["^GSPC","KRW=X","^KS11","^TNX","CL=F","GC=F"],period="5d",progress=False,threads=False)
    out["yfinance"]={"shape":list(df.shape),"tail":df.tail(2).to_string()[:600]}
except Exception as e: out["yfinance"]={"error":str(e)[:300]}
json.dump(out,open("market/_probe.json","w"),ensure_ascii=False,indent=1)
print(json.dumps(out,ensure_ascii=False,indent=1))
