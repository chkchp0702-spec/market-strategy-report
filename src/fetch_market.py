"""시세 자동 수집 (GitHub Actions에서 매일 07:00 KST + 장중 매시간 실행).

출력:
  market/latest.json   — 종목별 최근 종가·전일 대비·시각·출처
  market/history.csv   — 날짜별 종가 누적 (대시보드·그림용)
  feeds/james_lee.json — James Lee 블로그 RSS 새 글 목록

원칙: 못 받은 값은 null 로 남긴다. 숫자를 만들지 않는다.
출처: Yahoo Finance(chart API) 1차 · 미 재무부(10년·30년 일별 확정치) · 네이버 금융(외국인 순매수, 되면)
"""
from __future__ import annotations
import csv, json, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MK = ROOT / "market"
FEEDS = ROOT / "feeds"
KST = timezone(timedelta(hours=9))
ERRORS: dict[str, str] = {}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "*/*"}

# key: (yahoo symbol, 한글 이름, 소수 자리)
TICKERS = {
    "sp500":   ("^GSPC", "S&P 500", 2),
    "nasdaq":  ("^IXIC", "나스닥", 2),
    "dow":     ("^DJI", "다우", 2),
    "vix":     ("^VIX", "VIX", 2),
    "us10y":   ("^TNX", "미 10년 금리", 3),
    "us30y":   ("^TYX", "미 30년 금리", 3),
    "us2y":    ("2YY=F", "미 2년 금리(선물)", 3),
    "usdkrw":  ("KRW=X", "달러/원", 1),
    "dxy":     ("DX-Y.NYB", "달러지수", 2),
    "wti":     ("CL=F", "WTI", 2),
    "brent":   ("BZ=F", "브렌트", 2),
    "gold":    ("GC=F", "금", 1),
    "kospi":   ("^KS11", "코스피", 2),
    "kosdaq":  ("^KQ11", "코스닥", 2),
    "samsung": ("005930.KS", "삼성전자", 0),
    "hynix":   ("000660.KS", "SK하이닉스", 0),
    "micron":  ("MU", "마이크론", 2),
    "nvidia":  ("NVDA", "엔비디아", 2),
    "kbe":     ("KBE", "미 은행 ETF(KBE)", 2),
    "tlt":     ("TLT", "미 장기채 ETF(TLT)", 2),
}


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def yahoo(symbol: str) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1mo&interval=1d"
    for host in ("query1", "query2"):
        try:
            j = json.loads(_get(url.replace("query1", host)))
            res = j["chart"]["result"][0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            closes = [(datetime.fromtimestamp(t, tz=timezone.utc), c) for t, c in zip(ts, q["close"]) if c is not None]
            if len(closes) < 2:
                return None
            (d1, c1), (d0, c0) = closes[-1], closes[-2]
            meta = res.get("meta", {})
            return {"value": c1, "prev": c0, "change": c1 - c0, "change_pct": (c1 / c0 - 1) * 100,
                    "asof_utc": d1.isoformat(), "asof_kst": d1.astimezone(KST).strftime("%m/%d %H:%M"),
                    "market_state": meta.get("marketState"), "src": f"Yahoo Finance {symbol}",
                    "history": [(d.astimezone(KST).strftime("%Y-%m-%d"), round(c, 4)) for d, c in closes]}
        except Exception as e:  # noqa
            err = e
            time.sleep(1)
    print(f"  yahoo {symbol}: 실패 ({err})", file=sys.stderr)
    ERRORS[f"yahoo {symbol}"] = str(err)[:200]
    return stooq(symbol)


STOOQ = {"^GSPC": "^spx", "^IXIC": "^ndq", "^DJI": "^dji", "^TNX": "10yusy.b", "^TYX": "30yusy.b", "2YY=F": "2yusy.b",
         "KRW=X": "usdkrw", "DX-Y.NYB": "usd_i", "CL=F": "cl.f", "BZ=F": "cb.f", "GC=F": "gc.f", "^KS11": "^kospi",
         "MU": "mu.us", "NVDA": "nvda.us", "KBE": "kbe.us", "TLT": "tlt.us", "^VIX": "vi.f"}


def stooq(symbol: str) -> dict | None:
    """Yahoo 가 막힐 때 2차: stooq.com 일별 CSV."""
    code = STOOQ.get(symbol)
    if not code:
        return None
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(code)}&i=d"
    try:
        txt = _get(url).decode("utf-8", "ignore").strip().splitlines()
        rows = [r.split(",") for r in txt[1:] if r.count(",") >= 4]
        closes = [(r[0], float(r[4])) for r in rows[-25:] if r[4] not in ("", "N/D")]
        if len(closes) < 2:
            ERRORS[f"stooq {code}"] = f"rows={len(rows)}"
            return None
        (d0, c0), (d1, c1) = closes[-2], closes[-1]
        return {"value": c1, "prev": c0, "change": c1 - c0, "change_pct": (c1 / c0 - 1) * 100, "asof_utc": d1,
                "asof_kst": d1[5:] + " 종가", "market_state": "CLOSED", "src": f"stooq {code}", "history": closes}
    except Exception as e:
        ERRORS[f"stooq {code}"] = str(e)[:200]
        return None


def treasury() -> dict:
    """미 재무부 일별 수익률 곡선 (확정치). 10년·30년·2년."""
    out = {}
    now = datetime.now(KST)
    months = [now.strftime("%Y%m"), (now.replace(day=1) - timedelta(days=1)).strftime("%Y%m")]
    rows = []
    for m in months:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
               f"?data=daily_treasury_yield_curve&field_tdr_date_value_month={m}")
        try:
            root = ET.fromstring(_get(url))
        except Exception as e:
            print(f"  treasury {m}: 실패 ({e})", file=sys.stderr); ERRORS[f"treasury {m}"] = str(e)[:200]
            continue
        ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
              "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
        for e in root.findall(".//a:entry", ns):
            p = e.find(".//m:properties", ns)
            if p is None:
                continue
            g = lambda k: (p.findtext(f"d:{k}", default="", namespaces=ns) or "").strip()
            if g("NEW_DATE"):
                rows.append({"date": g("NEW_DATE")[:10], "us2y": g("BC_2YEAR"), "us10y": g("BC_10YEAR"), "us30y": g("BC_30YEAR")})
    rows = sorted({r["date"]: r for r in rows}.values(), key=lambda r: r["date"])
    if rows:
        last = rows[-1]
        for k in ("us2y", "us10y", "us30y"):
            try:
                out[k] = {"value": float(last[k]), "date": last["date"], "src": "미 재무부 일별 확정치",
                          "history": [(r["date"], float(r[k])) for r in rows if r[k]]}
            except ValueError:
                pass
    return out


def naver_foreign() -> dict | None:
    """코스피 외국인 순매수(억원). 네이버 금융 투자자별 매매동향. 막히면 None."""
    url = "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=&sosok=01"
    try:
        html = _get(url).decode("euc-kr", "ignore")
    except Exception as e:
        print(f"  naver foreign: 실패 ({e})", file=sys.stderr); ERRORS["naver foreign"] = str(e)[:200]
        return None
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = [re.sub(r"<[^>]+>", "", t).strip().replace(",", "") for t in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) >= 4 and re.match(r"\d{2}\.\d{2}\.\d{2}", tds[0]):
            try:
                y = "20" + tds[0][:2]
                rows.append({"date": f"{y}-{tds[0][3:5]}-{tds[0][6:8]}", "individual": int(tds[1]), "foreign": int(tds[2]), "institution": int(tds[3])})
            except ValueError:
                pass
    if not rows:
        return None
    rows.sort(key=lambda r: r["date"])
    last = rows[-1]
    return {"value": last["foreign"], "date": last["date"], "unit": "억원", "src": "네이버 금융 투자자별 매매동향(코스피)",
            "history": [(r["date"], r["foreign"]) for r in rows[-30:]]}


def naver_rss(blog_id: str = "james_lee_advisors") -> list[dict]:
    url = f"https://rss.blog.naver.com/{blog_id}.xml"
    try:
        root = ET.fromstring(_get(url))
    except Exception as e:
        print(f"  rss {blog_id}: 실패 ({e})", file=sys.stderr); ERRORS[f"rss {blog_id}"] = str(e)[:200]
        return []
    items = []
    for it in root.iter("item"):
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        items.append({"title": (it.findtext("title") or "").strip(), "link": (it.findtext("link") or "").strip(),
                      "pubDate": (it.findtext("pubDate") or "").strip(), "summary": re.sub(r"\s+", " ", desc).strip()[:1500]})
    return items


def main() -> int:
    MK.mkdir(exist_ok=True)
    FEEDS.mkdir(exist_ok=True)
    now = datetime.now(KST)
    latest = {"fetched_kst": now.strftime("%Y-%m-%d %H:%M"), "items": {}}
    hist_rows: dict[str, dict[str, float]] = {}

    print("Yahoo…")
    for key, (sym, name, nd) in TICKERS.items():
        r = yahoo(sym)
        if r:
            for d, c in r.pop("history"):
                hist_rows.setdefault(d, {})[key] = c
            r["name"] = name
            r["value"] = round(r["value"], nd); r["prev"] = round(r["prev"], nd)
            r["change"] = round(r["change"], nd); r["change_pct"] = round(r["change_pct"], 2)
        latest["items"][key] = r

    print("Treasury…")
    tr = treasury()
    for k, v in tr.items():
        for d, c in v.pop("history"):
            hist_rows.setdefault(d, {})[k + "_tsy"] = c
        latest["items"][k + "_tsy"] = {"name": TICKERS.get(k, (None, k))[1] + " (재무부 확정)", **v}

    print("Naver 외국인…")
    nf = naver_foreign()
    if nf:
        for d, c in nf.pop("history"):
            hist_rows.setdefault(d, {})["foreign_kospi"] = c
    latest["items"]["foreign_kospi"] = ({"name": "코스피 외국인 순매수(억원)", **nf} if nf else None)

    print("RSS…")
    posts = naver_rss()
    if posts:
        prev = {}
        f = FEEDS / "james_lee.json"
        if f.exists():
            prev = {p["link"]: p for p in json.loads(f.read_text(encoding="utf-8")).get("posts", [])}
        new = [p for p in posts if p["link"] not in prev]
        f.write_text(json.dumps({"fetched_kst": latest["fetched_kst"], "new_since_last": [p["link"] for p in new],
                                 "posts": posts}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  새 글 {len(new)}개")

    latest["errors"] = ERRORS
    (MK / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=1), encoding="utf-8")

    # history.csv 병합 (있는 값만 덮어씀)
    hp = MK / "history.csv"
    merged: dict[str, dict] = {}
    if hp.exists():
        with hp.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                merged[row["date"]] = {k: v for k, v in row.items() if k != "date" and v != ""}
    for d, vals in hist_rows.items():
        merged.setdefault(d, {}).update({k: str(v) for k, v in vals.items()})
    cols = sorted({k for v in merged.values() for k in v})
    with hp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date"] + cols)
        for d in sorted(merged):
            w.writerow([d] + [merged[d].get(c, "") for c in cols])

    got = sum(1 for v in latest["items"].values() if v)
    print(f"완료: {got}/{len(latest['items'])} 항목 · history {len(merged)}일")
    return 0 if got else 1


if __name__ == "__main__":
    sys.exit(main())
