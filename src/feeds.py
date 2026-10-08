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
    ("tg", "egzion", "이그전 (이은택의 그림 전략)", "KB증권 리서치 전략"),
    ("tg", "HANAchina", "하나 중국/신흥국 전략", "하나증권 김경환"),
    ("tg", "globalmktinsight", "미래에셋증권 시황", "미래에셋 김석환"),
]
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
