"""📰 내 피드 — 매일 보는 네이버 블로그 + 텔레그램 채널 모으기 (10/9 사용자 요청)
  · 네이버 블로그: rss.blog.naver.com/{id}.xml → 글마다 본문(모바일 글 보기)까지 시도, 안 되면 RSS 요약
  · 텔레그램 공개 채널: t.me/s/{채널} 미리보기 페이지 (로그인 불필요)
  → feeds/my_feed.json  (최근 7일, 출처마다 최대 40개)
  앱 「📰 피드」 탭이 읽고, 아침 시황리포트가 근거로 인용한다.
  출처 추가/삭제는 SOURCES 만 고치면 됨.
"""
from __future__ import annotations
import datetime as dt
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "feeds" / "my_feed.json"

SOURCES = [
    # kind, id, 이름, 누가
    ("blog", "james_lee_advisors", "James Lee Advisors", "거시경제 Letter"),
    ("blog", "tosoha1", "이것 또한 지나가리라", "농구천재"),
    ("blog", "pillion21", "알바트로스의 파생 이야기", "알바트로스 · 파생·수급"),
    ("blog", "jeunkim", "피우스의 책도둑 & 매거진", "피우스 · 시장·경제 공부"),
    ("blog", "pokara61", "포카라의 실전투자", "포카라 · 증권·경제"),
    ("tg", "egzion", "이그전 (이은택의 그림 전략)", "KB증권 리서치 전략"),
    ("tg", "HANAchina", "하나 중국/신흥국 전략", "하나증권 김경환"),
    ("tg", "globalmktinsight", "미래에셋증권 시황", "미래에셋 김석환"),
    ("tg", "YeouidoStory2", "여의도스토리", "뉴스·증권사 리포트·글로벌 경제"),
    ("tg", "sunstudy1111", "선진짱 주식공부방", "종목·시황 공부"),
    ("tg", "kwusa", "키움증권 미국주식 톡톡", "키움 미국주식 리서치"),
    ("tg", "kimu_nim", "김현석 (자본주의 바이어스)", "김현석 · 글로벌 시장"),
    ("tg", "meritz_research", "메리츠증권 리서치", "메리츠 리서치센터"),
]
# 🌐 미리 정한 피드 밖의 뉴스·전략·경제 글 (10/10 사용자: "피드에 없는 뉴스·자료·전략·경제·주식 글도 다 검색해서 넣어")
GN = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{lang}"
import urllib.parse as _up
NEWS = [
    # id, 이름, 설명, url
    ("gn_kr_mkt", "뉴스 · 국내 증시", "구글 뉴스 검색", GN.format(q=_up.quote("코스피+OR+코스닥+OR+증시+when:1d", safe="+:"), hl="ko", gl="KR", lang="ko")),
    ("gn_kr_macro", "뉴스 · 금리·환율·경제", "구글 뉴스 검색", GN.format(q=_up.quote("금리+OR+환율+OR+연준+OR+물가+OR+경기+when:1d", safe="+:"), hl="ko", gl="KR", lang="ko")),
    ("gn_kr_sector", "뉴스 · 반도체·AI·업종", "구글 뉴스 검색", GN.format(q=_up.quote("반도체+OR+HBM+OR+AI+OR+전력+OR+조선+주가+when:1d", safe="+:"), hl="ko", gl="KR", lang="ko")),
    ("gn_kr_strat", "뉴스 · 증권사 전략·리포트", "구글 뉴스 검색", GN.format(q=_up.quote("증권사+전략+OR+목표주가+OR+리포트+OR+투자전략+when:1d", safe="+:"), hl="ko", gl="KR", lang="ko")),
    ("gn_us_mkt", "News · US markets", "Google News", GN.format(q="stock+market+OR+S%26P+500+OR+Nasdaq+OR+Treasury+yields+when:1d", hl="en-US", gl="US", lang="en")),
    ("gn_us_fed", "News · Fed·macro", "Google News", GN.format(q="Federal+Reserve+OR+inflation+OR+jobs+report+OR+earnings+when:1d", hl="en-US", gl="US", lang="en")),
    ("hankyung", "한국경제 증권", "언론사 RSS", "https://www.hankyung.com/feed/finance"),
    ("mk", "매일경제 증권", "언론사 RSS", "https://www.mk.co.kr/rss/50200011/"),
    ("cnbc", "CNBC Markets", "언론사 RSS", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
    ("yahoo", "Yahoo Finance", "언론사 RSS", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,%5EIXIC,%5EDJI,NVDA,AAPL&region=US&lang=en-US"),
    ("cnbc_top", "CNBC Top News", "언론사 RSS", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("investing_kr", "인베스팅닷컴 뉴스", "언론사 RSS", "https://kr.investing.com/rss/news.rss"),
    # 블룸버그 (10/10 사용자: "피드에 블룸버그 뉴스도 들어가고 있니?") — 본문은 유료라 제목·요약까지
    ("bbg_mkt", "Bloomberg Markets", "블룸버그 RSS", "https://feeds.bloomberg.com/markets/news.rss"),
    ("bbg_tech", "Bloomberg Technology", "블룸버그 RSS", "https://feeds.bloomberg.com/technology/news.rss"),
    ("bbg_econ", "Bloomberg Economics", "블룸버그 RSS", "https://feeds.bloomberg.com/economics/news.rss"),
    ("gn_bbg", "News · Bloomberg 전체", "Google News (bloomberg.com)", GN.format(q="site:bloomberg.com+when:1d", hl="en-US", gl="US", lang="en")),
    ("gn_kr_bbg", "뉴스 · 블룸버그 인용", "구글 뉴스 검색 (한국 언론이 전한 블룸버그)", GN.format(q=_up.quote("블룸버그+when:1d", safe="+:"), hl="ko", gl="KR", lang="ko")),
]
FIN = re.compile(r"주|증시|코스피|코스닥|지수|금리|환율|달러|채권|국채|연준|Fed|물가|경기|경제|수출|실적|매출|이익|투자|펀드|ETF|반도체|HBM|AI|전력|조선|방산|원전|배터리|IPO|공모|상장|외국인|기관|목표가|리포트|전략|시장|무역|관세|유가|원유|금값|비트|증권|은행|M&A|인수|합병")
AI_FOUND = ROOT / "feeds" / "ai_found.json"     # 🧠 매시간 두뇌가 웹에서 찾아 넣는 글
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
      "Accept-Language": "ko-KR,ko;q=0.9"}
KEEP_DAYS = 7
DEBUG: list[str] = []


def get(url, t=25, ref=None):
    h = dict(UA)
    if ref:
        h["Referer"] = ref
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t) as r:
        return r.read().decode("utf-8", "ignore")


def clean(x: str) -> str:
    x = re.sub(r"<br\s*/?>", "\n", x, flags=re.I)
    x = re.sub(r"</(p|div|li|h\d)>", "\n", x, flags=re.I)
    x = re.sub(r"<[^>]+>", " ", x)
    x = html.unescape(x).replace("​", "")
    x = re.sub(r"[ \t\xa0]+", " ", x)
    x = re.sub(r"\n\s*\n+", "\n", x)
    return x.strip()


# ---------- 네이버 블로그 ----------
def blog_body(bid: str, log: str) -> tuple[str, list[str]]:
    """글 보기 페이지에서 본문 글자 + 그림 몇 장 (모바일 → PC 순서로 시도)"""
    for url, ref in ((f"https://m.blog.naver.com/PostView.naver?blogId={bid}&logNo={log}", "https://m.blog.naver.com/"),
                     (f"https://blog.naver.com/PostView.naver?blogId={bid}&logNo={log}&redirect=Dlog&widgetTypeCall=true", "https://blog.naver.com/")):
        try:
            x = get(url, ref=ref)
        except Exception as e:
            DEBUG.append(f"{bid} 글보기 실패 {str(e)[:50]}")
            continue
        paras = re.findall(r'<p class="se-text-paragraph[^"]*"[^>]*>(.*?)</p>', x, re.S)
        txt = "\n".join(t for t in (clean(p) for p in paras) if t)
        if not txt:
            m = re.search(r'id="postViewArea"[^>]*>(.*?)<div class="post_footer', x, re.S)
            txt = clean(m.group(1)) if m else ""
        if len(txt) > 80:
            imgs = [html.unescape(u).split("?")[0] + "?type=w773" for u in re.findall(r'data-lazy-src="(https://[^"]+)"', x)[:4]]
            return txt, imgs
        head = re.sub(r"\s+", " ", x[:60])
        DEBUG.append(f"{bid} 글보기 길이 {len(x)} se:{'se-main-container' in x} 앞:{head}")
    return "", []


def blog(bid: str) -> list[dict]:
    root = ET.fromstring(get(f"https://rss.blog.naver.com/{bid}.xml").encode("utf-8"))
    out = []
    for it in list(root.iter("item"))[:15]:
        link = (it.findtext("link") or "").strip()
        m = re.search(r"/(\d{9,})", link)
        log = m.group(1) if m else ""
        try:
            at = parsedate_to_datetime((it.findtext("pubDate") or "").strip()).astimezone(KST)
        except Exception:
            at = dt.datetime.now(KST)
        summ = clean(it.findtext("description") or "")
        out.append({"id": f"{bid}/{log}", "title": clean(it.findtext("title") or ""), "at": at.strftime("%Y-%m-%d %H:%M"),
                    "link": f"https://m.blog.naver.com/{bid}/{log}" if log else link, "text": summ[:1500], "imgs": [],
                    "tags": [s.strip() for s in (it.findtext("tag") or "").split(",") if s.strip()][:8]})
    return out


def blog_fill(items: list[dict], bid: str, prev: dict):
    """본문은 새 글만 한 번 가져와 둔다 (이전에 가져온 건 재사용)"""
    n = 0
    for it in items:
        old = prev.get(it["id"])
        if old and old.get("full"):
            if old["text"].startswith(it["title"]):
                old["text"] = old["text"][len(it["title"]):].lstrip(" .\n")
            it.update({"text": old["text"], "imgs": old.get("imgs", []), "full": 1})
            continue
        if n >= 8:
            continue
        try:
            txt, imgs = blog_body(bid, it["id"].split("/")[1])
            n += 1
            if txt.startswith(it["title"]):
                txt = txt[len(it["title"]):].lstrip(" .\n")
            if len(txt) > 80:
                it.update({"text": txt[:6000], "imgs": imgs, "full": 1})
        except Exception as e:
            DEBUG.append(f"{bid} 본문 실패 {str(e)[:60]}")


# ---------- 텔레그램 공개 채널 ----------
def tg(ch: str, pages: int = 3) -> list[dict]:
    out, before = [], None
    for _ in range(pages):
        x = get(f"https://t.me/s/{ch}" + (f"?before={before}" if before else ""))
        blocks = re.split(r'(?=<div class="tgme_widget_message_wrap)', x)[1:]
        if not blocks:
            DEBUG.append(f"tg {ch} 글 없음 길이 {len(x)}")
            break
        nums = []
        for b in blocks:
            m = re.search(r'data-post="([^"]+)/(\d+)"', b)
            if not m:
                continue
            num = int(m.group(2)); nums.append(num)
            tm = re.search(r'<time[^>]*datetime="([^"]+)"', b)
            try:
                at = dt.datetime.fromisoformat(tm.group(1)).astimezone(KST) if tm else None
            except Exception:
                at = None
            tx = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
            raw = tx.group(1) if tx else ""
            links = [html.unescape(u) for u in re.findall(r'<a[^>]+href="(https?://[^"]+)"', raw)
                     if "t.me/" not in u][:5]
            text = clean(raw)
            files = [clean(f) for f in re.findall(r'<div class="tgme_widget_message_document_title[^"]*"[^>]*>(.*?)</div>', b, re.S)]
            imgs = re.findall(r"tgme_widget_message_photo_wrap[^>]*background-image:url\('([^']+)'\)", b)[:4]
            if not text and not files and not imgs:
                continue
            first = text.split("\n", 1)[0] if text else (files[0] if files else "사진")
            out.append({"id": f"{ch}/{num}", "title": first[:90], "at": at.strftime("%Y-%m-%d %H:%M") if at else "",
                        "link": f"https://t.me/{ch}/{num}", "text": text[:4000], "imgs": imgs, "files": files, "links": links, "full": 1})
        if not nums:
            break
        before = min(nums)
        oldest = min((o["at"] for o in out if o["at"]), default="")
        if oldest and oldest < (dt.datetime.now(KST) - dt.timedelta(days=2)).strftime("%Y-%m-%d"):
            break
    return out


def rss(url: str, n: int = 30) -> list[dict]:
    root = ET.fromstring(get(url).encode("utf-8"))
    out = []
    for it in list(root.iter("item"))[:n]:
        link = (it.findtext("link") or "").strip()
        try:
            at = parsedate_to_datetime((it.findtext("pubDate") or "").strip()).astimezone(KST)
        except Exception:
            at = dt.datetime.now(KST)
        if at > dt.datetime.now(KST) + dt.timedelta(minutes=10):     # 한국 언론 RSS 가 KST 를 GMT 로 표시하는 경우
            at -= dt.timedelta(hours=9)
        title = clean(it.findtext("title") or "")
        srcname = clean(it.findtext("source") or "")
        if srcname and title.endswith(" - " + srcname):
            title = title[: -len(srcname) - 3]
        desc = clean(it.findtext("description") or "")
        if desc.startswith(title[:20]):
            desc = ""
        out.append({"id": "n/" + re.sub(r"\W+", "", link)[-60:], "title": title[:160], "at": at.strftime("%Y-%m-%d %H:%M"), "link": link,
                    "text": (title + ("\n" + desc if desc else ""))[:900], "imgs": [], "press": srcname, "full": 0})
    return out


def main() -> int:
    now = dt.datetime.now(KST)
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    old = {i["id"]: i for i in prev.get("items", [])}
    cut = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    items, srcs = {}, []
    for kind, sid, name, who in SOURCES:
        ok, got = True, []
        try:
            got = blog(sid) if kind == "blog" else tg(sid)
            if kind == "blog":
                blog_fill(got, sid, old)
        except Exception as e:
            ok = False
            DEBUG.append(f"{kind} {sid} 실패 {str(e)[:80]}")
        # 이번에 못 가져온 출처는 이전 것 유지
        if not got:
            got = [i for i in old.values() if i.get("src") == sid]
        for i in got:
            i.update({"src": sid, "kind": kind, "name": name})
            if i["at"] and i["at"][:10] < cut:
                continue
            o = old.get(i["id"])
            i["first"] = (o or {}).get("first") or now.strftime("%Y-%m-%d %H:%M")
            items[i["id"]] = i
        n = sum(1 for i in items.values() if i["src"] == sid)
        srcs.append({"id": sid, "kind": kind, "name": name, "who": who, "ok": ok, "n": n,
                     "url": f"https://m.blog.naver.com/{sid}" if kind == "blog" else f"https://t.me/s/{sid}"})
        print(f"  {name}: {'성공' if ok else '실패'} · {n}개")
    # 🌐 뉴스 (출처마다 30개, 2일)
    ncut = (now - dt.timedelta(days=2)).strftime("%Y-%m-%d")
    seen_t = set()
    for sid, name, who, url in NEWS:
        ok, got = True, []
        try:
            got = rss(url)
        except Exception as e:
            ok = False
            DEBUG.append(f"news {sid} 실패 {str(e)[:80]}")
        if not got:
            got = [i for i in old.values() if i.get("src") == sid]
        for i in got:
            if sid.startswith("gn_kr") and not FIN.search(i["title"]):
                continue                                   # 사건·사고 같은 잡음 거르기
            k = re.sub(r"\W+", "", i["title"])[:40]
            if k in seen_t or (i["at"] and i["at"][:10] < ncut):
                continue
            seen_t.add(k)
            i.update({"src": sid, "kind": "news", "name": name})
            o = old.get(i["id"])
            i["first"] = (o or {}).get("first") or now.strftime("%Y-%m-%d %H:%M")
            items[i["id"]] = i
        srcs.append({"id": sid, "kind": "news", "name": name, "who": who, "ok": ok, "n": sum(1 for i in items.values() if i["src"] == sid), "url": url})
    # 🧠 두뇌가 찾은 글
    try:
        for a in json.loads(AI_FOUND.read_text(encoding="utf-8")).get("items", []):
            if (a.get("at") or "")[:10] < cut:
                continue
            iid = "ai/" + re.sub(r"\W+", "", a.get("url", a.get("title", "")))[-60:]
            items[iid] = {"id": iid, "title": a.get("title", "")[:160], "at": a.get("at", ""), "link": a.get("url", ""), "text": (a.get("title", "") + "\n" + a.get("why", "") + ("\n" + a["summary"] if a.get("summary") else ""))[:1500],
                          "imgs": [], "press": a.get("press", ""), "src": "ai_found", "kind": "ai", "name": "🧠 AI가 찾은 글", "first": (old.get(iid) or {}).get("first") or a.get("at") or now.strftime("%Y-%m-%d %H:%M"), "full": 1}
        srcs.append({"id": "ai_found", "kind": "ai", "name": "🧠 AI가 찾은 글", "who": "매시간 두뇌가 웹 검색으로 찾은 중요한 글", "ok": True,
                     "n": sum(1 for i in items.values() if i["src"] == "ai_found"), "url": ""})
    except Exception:
        pass
    lst = sorted(items.values(), key=lambda i: i.get("at") or i["first"], reverse=True)
    per = {}
    keep = []
    for i in lst:
        per[i["src"]] = per.get(i["src"], 0) + 1
        if per[i["src"]] <= 40:
            keep.append(i)
    new = [i["id"] for i in keep if i["id"] not in old]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"at": now.strftime("%Y-%m-%d %H:%M"), "sources": srcs, "new": new, "items": keep,
                               "debug": DEBUG[:20]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"내 피드 {len(keep)}개 · 새 글 {len(new)}개")
    for d in DEBUG[:10]:
        print("  ·", d, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
