"""🧰 나라별 「시세 말고 다른 자료」 받기 (11/12 사용자: 「각 국의 쓸 수 있는, 할 수 있는 검증은 다 해」)
   받아지는 것만 market/lab/alt/*.csv 로 저장 → src/alt_bt.py 가 검증. 하나가 막혀도 나머지는 계속.
   🇰🇷 KRX 지수 PER·PBR · 네이버 예탁금·신용잔고 · 다음 투자자별 순매수 / 🇺🇸 multpl CAPE·PER·배당·PBR · FINRA 신용융자 · FRED · AAII
   🇯🇵 닛케이 PER·PBR / 🇨🇳🇭🇰 akshare(PE·PB·융자잔고·후강퉁) / 전부: 야후 시세 묶음(px.csv.gz)"""
from __future__ import annotations
import datetime as dt
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "lab" / "alt"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Accept-Language": "ko,en;q=0.8"}
LOG = {}
ONLY = set(a for a in sys.argv[1:] if not a.startswith("-"))


def save(name, df):
    df.to_csv(OUT / f"{name}.csv", index=False)
    LOG[name] = {"rows": int(len(df)), "cols": list(map(str, df.columns))[:12], "first": str(df.iloc[0, 0]), "last": str(df.iloc[-1, 0])}
    print(f"✅ {name}: {len(df)}행 · {df.iloc[0, 0]} ~ {df.iloc[-1, 0]} · {list(map(str, df.columns))[:10]}")
    print(df.tail(2).to_string()[:400])


def run(name, fn):
    if ONLY and name not in ONLY:
        return
    try:
        fn()
    except Exception as e:
        LOG[name] = {"err": f"{type(e).__name__}: {str(e)[:300]}"}
        print(f"❌ {name}: {type(e).__name__}: {str(e)[:500]}")
        traceback.print_exc(limit=2)


def get(u, **kw):
    h = dict(UA); h.update(kw.pop("headers", {}))
    r = requests.get(u, headers=h, timeout=kw.pop("timeout", 30), **kw); r.raise_for_status(); return r


# ───────── 🇰🇷
def krx_fund():
    rows = []
    for idx_name, i1, i2 in (("kospi", "1", "001"), ("kosdaq", "2", "001")):
        y = 2001
        while y <= dt.date.today().year:
            d = {"bld": "dbms/MDC/STAT/standard/MDCSTAT00702", "locale": "ko_KR", "searchType": "P", "indTpCd": i1, "indTpCd2": i2, "indIdx": i1, "indIdx2": i2,
                 "strtDd": f"{y}0101", "endDd": f"{min(y + 1, dt.date.today().year)}1231", "csvxls_isNo": "false", "share": "1", "money": "1"}
            r = requests.post("http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", data=d, headers={**UA, "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201010106"}, timeout=40)
            j = r.json() if r.text.strip().startswith("{") else {}
            out = j.get("output") or []
            if y == 2001:
                print("krx 첫 응답", idx_name, r.status_code, r.text[:200])
            for x in out:
                rows.append({"date": x.get("TRD_DD", "").replace("/", "-"), "idx": idx_name, "per": x.get("WT_PER"), "pbr": x.get("WT_STKPRC_NETASST_RTO"), "div": x.get("DIV_YD"), "close": x.get("CLSPRC_IDX")})
            y += 2; time.sleep(0.4)
    if not rows:
        raise RuntimeError("KRX 응답 없음(로그인 필요?)")
    df = pd.DataFrame(rows).sort_values(["idx", "date"]); save("kr_fund", df)


def pykrx_fund():
    from pykrx import stock
    fr = []
    for nm, tk in (("kospi", "1001"), ("kosdaq", "2001")):
        d = stock.get_index_fundamental("20010101", dt.date.today().strftime("%Y%m%d"), tk)
        d = d.reset_index(); d.columns = [str(c) for c in d.columns]; d.insert(1, "idx", nm); fr.append(d)
    df = pd.concat(fr); df.rename(columns={df.columns[0]: "date"}, inplace=True); save("kr_fund_pykrx", df)


def naver_deposit():
    rows = []; seen = set()
    for pg in range(1, 260):
        j = None
        for host in ("https://finance.naver.com", "https://m.stock.naver.com"):
            try:
                j = get(f"{host}/api/domestic/market/trendDeposit?page={pg}&pageSize=60", headers={"Referer": "https://finance.naver.com/sise/sise_deposit.naver"}).json(); break
            except Exception as e:
                last = e
        if j is None:
            if pg == 1: raise last
            break
        L = j if isinstance(j, list) else next((v for v in j.values() if isinstance(v, list)), []) if isinstance(j, dict) else []
        if isinstance(j, dict) and not L:
            for v in j.values():
                if isinstance(v, dict):
                    L = next((w for w in v.values() if isinstance(w, list)), [])
                    if L: break
        if pg == 1: print("deposit 첫 행", str(L[:1])[:400])
        new = 0
        for r in L:
            k = json.dumps(r, sort_keys=True)
            if k in seen: continue
            seen.add(k); rows.append(r); new += 1
        if not new: break
        time.sleep(0.15)
    df = pd.DataFrame(rows)
    dc = next(c for c in df.columns if "date" in c.lower() or c.lower() in ("bizdate", "dt"))
    df.insert(0, "date", df.pop(dc)); df = df.sort_values("date"); save("kr_deposit", df)


def daum_investor():
    fr = []
    for mk in ("KOSPI", "KOSDAQ"):
        rows = []
        for pg in range(1, 330):
            try:
                j = get(f"https://finance.daum.net/api/investor/{mk}/days?page={pg}&perPage=30", headers={"Referer": "https://finance.daum.net/domestic/investors/" + mk, "Accept": "application/json"}).json()
            except Exception as e:
                if pg == 1: raise
                print("daum 멈춤", mk, pg, str(e)[:80]); break
            L = j.get("data") or []
            if pg == 1: print("daum 첫 행", mk, str(L[:1])[:500], "· totalPages", j.get("totalPages"))
            if not L: break
            rows += L; time.sleep(0.12)
        d = pd.DataFrame(rows); d.insert(0, "mk", mk); fr.append(d)
    df = pd.concat(fr); df.insert(0, "date", df.pop("date").astype(str).str[:10]); df = df.sort_values(["mk", "date"]); save("kr_investor", df)


# ───────── 🇺🇸
def multpl():
    fr = None
    for nm, slug in (("cape", "shiller-pe"), ("pe", "s-p-500-pe-ratio"), ("divy", "s-p-500-dividend-yield"), ("pb", "s-p-500-price-to-book"), ("ey", "s-p-500-earnings-yield")):
        try:
            t = pd.read_html(io.StringIO(get(f"https://www.multpl.com/{slug}/table/by-month").text))[0]
            t.columns = ["date", nm]; t["date"] = pd.to_datetime(t["date"]).dt.strftime("%Y-%m-%d")
            t[nm] = pd.to_numeric(t[nm].astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
            fr = t if fr is None else fr.merge(t, on="date", how="outer"); time.sleep(0.5)
        except Exception as e:
            print("multpl", nm, "실패", str(e)[:120])
    if fr is None: raise RuntimeError("multpl 전부 실패")
    save("us_multpl", fr.sort_values("date"))


def finra_margin():
    last = None
    for u in ("https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx", "https://www.finra.org/sites/default/files/margin-statistics.xlsx"):
        try:
            b = get(u).content; df = pd.read_excel(io.BytesIO(b)); break
        except Exception as e:
            last = e; df = None
    if df is None: raise last
    df.columns = [str(c).strip() for c in df.columns]; df.insert(0, "date", df.pop(df.columns[0]).astype(str)); save("us_margin", df.sort_values("date"))


def fred():
    fr = None
    for sid in ("UNRATE", "BAA10Y", "T10Y3M", "NFCI", "ICSA", "UMCSENT", "BAMLH0A0HYM2", "SAHMREALTIME"):
        try:
            t = pd.read_csv(io.StringIO(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=25).text)); t.columns = ["date", sid]
            fr = t if fr is None else fr.merge(t, on="date", how="outer")
        except Exception as e:
            print("FRED", sid, "실패", str(e)[:100])
    if fr is None: raise RuntimeError("FRED 전부 실패")
    save("us_fred", fr.sort_values("date"))


def aaii():
    b = get("https://www.aaii.com/files/surveys/sentiment.xls", headers={"Referer": "https://www.aaii.com/sentimentsurvey/sent_results"}).content
    df = pd.read_excel(io.BytesIO(b), skiprows=3).iloc[:, :4]; df.columns = ["date", "bull", "neutral", "bear"]
    df = df[pd.to_datetime(df["date"], errors="coerce").notna()]; df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"); save("us_aaii", df)


# ───────── 🇯🇵
def nikkei_val():
    fr = []
    for kind in ("per", "pbr"):
        r = get(f"https://indexes.nikkei.co.jp/nkave/archives/data?list={kind}", headers={"Referer": "https://indexes.nikkei.co.jp/nkave/archives/data"})
        print("nikkei", kind, r.status_code, len(r.text), r.text[:300].replace("\n", " "))
        try:
            for t in pd.read_html(io.StringIO(r.text)):
                t.insert(0, "kind", kind); fr.append(t)
        except Exception as e:
            print("nikkei 표 없음", kind, str(e)[:100])
    if not fr: raise RuntimeError("닛케이 표 없음")
    df = pd.concat(fr); df.insert(0, "date", df.pop(df.columns[1]).astype(str)); save("jp_nikkei_val", df)


# ───────── 🇨🇳 🇭🇰 (akshare)
def ak_try(name, call):
    def f():
        import akshare as ak
        df = call(ak)
        if df is None or not len(df): raise RuntimeError("빈 표")
        df = df.copy(); df.columns = [str(c) for c in df.columns]
        df.iloc[:, 0] = df.iloc[:, 0].astype(str); df = df.sort_values(df.columns[0]); save(name, df)
    run(name, f)


def px_panel():
    import yfinance as yf
    syms = ["^KS11", "^KQ11", "^N225", "000001.SS", "399001.SZ", "^HSI", "^HSCE", "^GSPC", "^IXIC", "^VIX", "^TNX", "^IRX", "^SOX", "RSP", "VWEHX", "VFITX", "VUSTX", "VBMFX",
            "BZ=F", "CL=F", "GC=F", "HG=F", "DX-Y.NYB", "KRW=X", "JPY=X", "CNY=X", "HKD=X", "XLP", "XLV", "XLU", "XLK", "^NDX", "^NYA", "SPY", "QQQ", "EWY", "EWJ", "FXI", "^TPX", "000300.SS", "^KS200"]
    cols = {}
    for s in syms:
        for _ in range(3):
            try:
                d = yf.download(s, start="1985-01-01", auto_adjust=True, progress=False, threads=False)["Close"]
                d = (d.iloc[:, 0] if hasattr(d, "columns") else d).dropna()
                if len(d): cols[s] = d; break
            except Exception as e:
                print("재시도", s, str(e)[:60])
        if s not in cols: print("시세 없음", s)
    df = pd.DataFrame(cols).round(4); df.index.name = "date"
    df.to_csv(OUT / "px.csv.gz", compression="gzip")
    LOG["px"] = {"rows": int(len(df)), "cols": list(df.columns)}
    print("✅ px", df.shape, {c: str(df[c].first_valid_index().date()) for c in df.columns})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    run("px", px_panel)
    run("kr_fund", krx_fund); run("kr_fund_pykrx", pykrx_fund); run("kr_deposit", naver_deposit); run("kr_investor", daum_investor)
    run("us_multpl", multpl); run("us_margin", finra_margin); run("us_fred", fred); run("us_aaii", aaii)
    run("jp_nikkei_val", nikkei_val)
    ak_try("cn_pe_sh", lambda ak: ak.stock_market_pe_lg(symbol="上证"))
    ak_try("cn_pe_sz", lambda ak: ak.stock_market_pe_lg(symbol="深证"))
    ak_try("cn_pb_sh", lambda ak: ak.stock_market_pb_lg(symbol="上证"))
    ak_try("cn_pe_all", lambda ak: ak.stock_a_ttm_lyr())
    ak_try("cn_pb_all", lambda ak: ak.stock_a_all_pb())
    ak_try("cn_ebs", lambda ak: ak.stock_ebs_lg())
    ak_try("cn_buffett", lambda ak: ak.stock_buffett_index_lg())
    ak_try("cn_margin_sse", lambda ak: ak.stock_margin_sse(start_date="20100331", end_date=dt.date.today().strftime("%Y%m%d")))
    ak_try("cn_margin_macro", lambda ak: ak.macro_china_market_margin_sh())
    ak_try("cn_north", lambda ak: ak.stock_hsgt_hist_em(symbol="北向资金"))
    ak_try("hk_south", lambda ak: ak.stock_hsgt_hist_em(symbol="南向资金"))
    ak_try("cn_csi300_pe", lambda ak: ak.stock_index_pe_lg(symbol="沪深300"))
    ak_try("cn_csi300_pb", lambda ak: ak.stock_index_pb_lg(symbol="沪深300"))
    ak_try("hk_hsi_val", lambda ak: ak.stock_hk_index_value_name_em() if hasattr(ak, "stock_hk_index_value_name_em") else None)
    ak_try("cn_newacct", lambda ak: ak.stock_account_statistics_em())
    (OUT / "_log.json").write_text(json.dumps({"at": dt.datetime.now().isoformat()[:16], "log": LOG}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n요약:", json.dumps({k: (v.get("rows") or v.get("err", "")[:60]) for k, v in LOG.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
