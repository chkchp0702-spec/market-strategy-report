"""🗣 내 채널 성적표 — 10/20 A10/20-2 (사용자 「1,2 둘 다 실행」)
   피드(feeds/my_feed.json)의 사람 글(텔레그램·블로그)이 이름을 부른 종목을 기록하고(feeds/mentions.json),
   「그날 종가 → 5거래일·20거래일 뒤 종가」로 채점해 채널별 성적을 냄(feeds/feed_score.json).

   원칙(숫자를 지어내지 않음)
   · 이름 사전 = daily-app opdata idx.json (한국 상장 전 종목 + 미국 큰 종목의 한글 이름) · 한글 3자 이상만
   · 긴 이름부터 찾고 찾은 자리는 지움(「SK하이닉스」 안의 「이닉스」 같은 오탐 방지) · 앞 글자가 한글·영문·숫자면 버림
   · 한 글에 종목 이름이 7개 이상이면 그 글은 안 셈(「오늘 상한가 종목」 같은 목록 글은 의견이 아님)
   · 증권사 이름(○○증권)·스팩은 안 셈(글쓴이 소속·서명일 때가 많음)
   · 같은 채널·같은 종목·같은 날은 1번
   · 기준 = 글 날짜(한국 시각) 이후 첫 거래일 종가 · 5·20거래일 뒤 종가와 비교 · 같은 기간 지수(코스피 ^KS11 · S&P500 ^GSPC)와의 차이도
   · 「사라·팔아라」는 글로 판단하지 않음 — 「언급 뒤 올랐나」만 셈(칩 설명에 그대로 적음)

   사용
     python -m src.feed_score                 # 피드에서 언급 더하기 + 시세 받아 채점
     python -m src.feed_score --backfill      # git 기록의 옛 my_feed.json 들에서 언급만 되살림(시세 없이)
     python -m src.feed_score --selftest
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "feeds" / "my_feed.json"
MEN = ROOT / "feeds" / "mentions.json"
OUT = ROOT / "feeds" / "feed_score.json"
IDX_URL = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/opdata/idx.json"
KEEP_DAYS = 150          # 언급 기록 보관
WIN_DAYS = 90            # 성적 창(최근 90일 언급)
MAX_NAMES = 6            # 한 글에 이름이 이보다 많으면 목록 글로 보고 안 셈
STOP = {"디바이스", "인터넷", "에너지", "바이오", "솔루션", "시스템", "테크놀로지", "케미칼", "홀딩스", "글로벌", "인베스트", "파트너스",
        "코리아", "아시아", "인터내셔널", "엔터테인먼트", "아이엠", "에이스", "제이에스", "에스엠", "다이나믹", "유니온", "이노베이션",
        "하이브리드", "인공지능", "모바일", "플랫폼", "네트웍스", "커머스", "로보틱스", "반도체", "메디칼", "스마트", "레이저", "미래에셋",
        "한국투자", "삼성증권", "아시아경제", "이데일리", "한국경제", "매일경제", "서울경제", "머니투데이", "파이낸셜", "헤럴드", "아스타", "무디스", "프로그레시브", "트럼프", "골드만삭스", "모건스탠리", "블랙록", "버크셔", "엔에이치", "아이디스"}
KST = dt.timezone(dt.timedelta(hours=9))


def now_kst():
    return dt.datetime.now(KST)


# ───────── 이름 사전 ─────────
def load_idx(path: str | None = None):
    if path and os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    req = urllib.request.Request(IDX_URL, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def build_dict(idx):
    """[(이름, 야후 코드, 나라)] 긴 이름 먼저"""
    out, seen = [], set()
    for r in idx:
        try:
            code, name, mk, size = r[0], str(r[1] or "").strip(), r[2], int(r[6] or 0)
        except Exception:
            continue
        if mk not in ("KR", "US"):
            continue
        nm = re.sub(r"\s+", "", name)
        if len(nm) < 3 or not re.search(r"[가-힣]", nm):
            continue
        if mk == "US" and size < 5:          # 미국은 큰 종목만(작은 종목 한글 이름은 일반 낱말과 겹치기 쉬움)
            continue
        if mk == "KR" and not re.search(r"\.(KS|KQ)$", code):
            continue
        if "증권" in nm or "스팩" in nm or re.search(r"(ETN|ETF|KODEX|TIGER|KBSTAR|ARIRANG|HANARO|SOL|ACE|RISE|PLUS)", nm, re.I) or nm.endswith("우") or re.search(r"우[BC]?$|\d우$", nm):
            continue
        if nm in STOP:
            continue
        if nm in seen:
            continue
        seen.add(nm)
        out.append((nm, code, mk))
    out.sort(key=lambda x: -len(x[0]))
    return out


def find_names(text: str, D):
    """글 → [(이름, 코드, 나라)] (긴 이름 먼저 · 찾은 자리는 지움 · 앞 글자 경계)"""
    t = re.sub(r"\s+", " ", text or "")
    t_ns = t
    found = []
    for nm, code, mk in D:
        if nm not in t_ns:
            continue
        hit = False
        for m in re.finditer(re.escape(nm), t_ns):
            i = m.start()
            prev = t_ns[i - 1] if i > 0 else " "
            if re.match(r"[가-힣A-Za-z0-9]", prev):
                continue
            hit = True
            break
        if hit:
            found.append((nm, code, mk))
            t_ns = t_ns.replace(nm, " " * len(nm))
    return found


# ───────── 언급 기록 ─────────
def item_mentions(it, D):
    if it.get("kind") not in ("tg", "blog"):
        return []
    at = str(it.get("first") or it.get("at") or "")
    if len(at) < 10:
        return []
    names = find_names((it.get("title") or "") + " \n " + (it.get("text") or ""), D)
    if not names or len(names) > MAX_NAMES:
        return []
    return [{"d": at[:10], "t": at[11:16], "src": it.get("src"), "ch": it.get("name"), "id": it.get("id"), "s": c, "n": n, "mk": mk}
            for n, c, mk in names]


def merge(old: list, new: list):
    key = lambda m: (m["src"], m["s"], m["d"])
    have = {key(m) for m in old}
    added = 0
    for m in new:
        if key(m) not in have:
            old.append(m); have.add(key(m)); added += 1
    cut = (now_kst() - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    old = [m for m in old if m["d"] >= cut]
    old.sort(key=lambda m: (m["d"], m.get("t") or ""))
    return old, added


def load_men():
    try:
        return json.load(open(MEN, encoding="utf-8")).get("items") or []
    except Exception:
        return []


def save_men(items):
    json.dump({"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "rule": "사람 글(텔레그램·블로그) · 한글 3자 이상 종목 이름 · 같은 채널·종목·날 1번 · 이름 7개 이상인 글 제외",
               "items": items}, open(MEN, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def backfill(D, since="2026-10-01", every_h=3):
    """git 기록의 옛 my_feed.json 들 → 언급(시세 없이). every_h 시간마다 한 판(피드가 7일치를 들고 있어 충분)"""
    log = subprocess.run(["git", "log", "--since", since, "--format=%H %ct", "--", "feeds/my_feed.json"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    picks, last = [], None
    for ln in log:
        if not ln.strip():
            continue
        h, ts = ln.split()
        ts = int(ts)
        if last is None or last - ts >= every_h * 3600:
            picks.append(h); last = ts
    print("backfill 판", len(picks))
    allm = []
    for h in picks:
        try:
            raw = subprocess.run(["git", "show", f"{h}:feeds/my_feed.json"], cwd=ROOT, capture_output=True).stdout
            d = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print("✗", h[:8], e); continue
        for it in d.get("items") or []:
            allm += item_mentions(it, D)
    return allm


# ───────── 채점 ─────────
BENCH = {"KR": "^KS11", "US": "^GSPC"}


def get_prices(codes, start):
    import yfinance as yf
    P = {}
    codes = sorted(set(codes))
    for i in range(0, len(codes), 80):
        chunk = codes[i:i + 80]
        try:
            h = yf.download(chunk, start=start, interval="1d", progress=False, auto_adjust=False, threads=True, group_by="ticker")
        except Exception as e:
            print("✗ 시세", e); continue
        for c in chunk:
            try:
                s = (h[c]["Close"] if len(chunk) > 1 else h["Close"]).dropna()
                if hasattr(s, "columns"):
                    s = s.iloc[:, 0]
                if len(s):
                    P[c] = [(d.strftime("%Y-%m-%d"), float(v)) for d, v in s.items() if float(v) > 0]
            except Exception:
                pass
    print("시세", len(P), "/", len(codes))
    return P


def ret_after(series, d, k):
    """series=[(날짜, 종가)] · d 이후 첫 거래일 기준 k 거래일 뒤 수익률(%) · (기준일, 값) 또는 None"""
    if not series:
        return None
    i = next((j for j, (x, _) in enumerate(series) if x >= d), None)
    if i is None or i + k >= len(series):
        return None
    return series[i][0], (series[i + k][1] / series[i][1] - 1) * 100


def score(items, P):
    cut = (now_kst() - dt.timedelta(days=WIN_DAYS)).strftime("%Y-%m-%d")
    ch = {}
    allr = {5: [], 20: []}
    for m in items:
        if m["d"] < cut:
            continue
        c = ch.setdefault(m["src"], {"name": m.get("ch"), "n": 0, "r5": [], "x5": [], "r20": [], "x20": [], "names": {}, "last": []})
        c["n"] += 1
        c["names"][m["n"]] = c["names"].get(m["n"], 0) + 1
        row = {"d": m["d"], "n": m["n"], "s": m["s"]}
        for k in (5, 20):
            r = ret_after(P.get(m["s"]), m["d"], k)
            if not r:
                continue
            b = ret_after(P.get(BENCH[m["mk"]]), r[0], k)
            c["r%d" % k].append(r[1]); allr[k].append(r[1])
            row["r%d" % k] = round(r[1], 1)
            if b:
                c["x%d" % k].append(r[1] - b[1]); row["x%d" % k] = round(r[1] - b[1], 1)
        c["last"].append(row)
    out = {}
    for src, c in ch.items():
        o = {"name": c["name"], "n": c["n"], "top": [k for k, _ in sorted(c["names"].items(), key=lambda t: -t[1])[:4]]}
        for k in (5, 20):
            r, x = c["r%d" % k], c["x%d" % k]
            o["n%d" % k] = len(r)
            if r:
                o["up%d" % k] = round(sum(1 for v in r if v > 0) / len(r) * 100)
                o["avg%d" % k] = round(sum(r) / len(r), 2)
            if x:
                o["ex%d" % k] = round(sum(x) / len(x), 2)
                o["beat%d" % k] = round(sum(1 for v in x if v > 0) / len(x) * 100)
        sc = [r for r in c["last"] if "r5" in r]
        o["last"] = sc[-12:][::-1]                      # 최근 「채점된」 언급 12개(점 띠)
        o["pend"] = len(c["last"]) - len(sc)            # 아직 5거래일이 안 지난 언급
        out[src] = o
    base = {}
    for k in (5, 20):
        r = allr[k]
        if r:
            base["n%d" % k] = len(r); base["up%d" % k] = round(sum(1 for v in r if v > 0) / len(r) * 100); base["avg%d" % k] = round(sum(r) / len(r), 2)
    return out, base


def post_map(feed, D):
    """지금 피드 글 id → [[이름, 코드]] (카드에 「이 글이 부른 종목」 꼬리표)"""
    pm = {}
    for it in feed.get("items") or []:
        ms = item_mentions(it, D)
        if ms:
            pm[it["id"]] = [[m["n"], m["s"]] for m in ms]
    return pm


# ───────── 🐇🐢 누가 먼저 말했나 (10/23 A10/23-1) ─────────
LEAD = ROOT / "feeds" / "lead.json"


def link_of(mid: str, kinds: dict) -> str:
    src = mid.split("/")[0]
    k = kinds.get(src)
    if k == "blog":
        return "https://m.blog.naver.com/" + mid
    if k == "tg":
        return "https://t.me/" + mid
    return ""


def lead(items, P, kinds=None, today=None):
    """종목마다 채널별 「처음 부른 때」 + 그날(뒤 첫 거래일) 종가 → 가장 최근 종가 수익률 · 채널마다 「먼저 말한 비율」.
       기록 첫날(since)에 이미 불린 종목은 「누가 먼저」를 알 수 없어 채널 순위 셈에서는 뺌(종목 화면엔 「기록 시작일부터」 표시)."""
    kinds = kinds or {}
    if not items:
        return None
    since = min(m["d"] for m in items)
    by = {}
    for m in sorted(items, key=lambda m: (m["d"], m.get("t") or "")):
        s = by.setdefault(m["s"], {"n": m["n"], "mk": m["mk"], "first": {}, "cnt": 0})
        s["cnt"] += 1
        if m["src"] not in s["first"]:
            s["first"][m["src"]] = m
    S, CH = {}, {}
    for sym, s in by.items():
        ser = P.get(sym) or []
        last = ser[-1] if ser else None
        rows = []
        for src, m in s["first"].items():
            r = None
            i = next((j for j, (x, _) in enumerate(ser) if x >= m["d"]), None)
            if i is not None and last:
                r = round((last[1] / ser[i][1] - 1) * 100, 1)
                bd = ser[i][0]
            else:
                bd = None
            rows.append([m["d"], m.get("t") or "", src, m.get("ch") or src, link_of(m.get("id") or "", kinds), r, bd])
        rows.sort(key=lambda x: (x[0], x[1]))
        d0 = rows[0][0]
        px = []
        if ser:
            i0 = next((j for j, (x, _) in enumerate(ser) if x >= d0), len(ser) - 1)
            px = [[x, round(v, 4)] for x, v in ser[max(0, i0 - 5):]]
        S[sym] = {"n": s["n"], "mk": s["mk"], "cnt": s["cnt"], "first": rows, "px": px, "last": list(last) if last else None, "pre": d0 == since}
        # 채널 순위: 2채널 넘게 부른 종목 · 첫 언급이 기록 첫날 뒤
        if len(rows) >= 2 and d0 > since:
            t0 = dt.date.fromisoformat(d0)
            for k, x in enumerate(rows):
                c = CH.setdefault(x[2], {"name": x[3], "n": 0, "first": 0, "lag": [], "r": []})
                c["n"] += 1
                if k == 0:
                    c["first"] += 1
                else:
                    c["lag"].append((dt.date.fromisoformat(x[0]) - t0).days)
                if x[5] is not None:
                    c["r"].append(x[5])
    ch = {}
    for src, c in CH.items():
        ch[src] = {"name": c["name"], "n": c["n"], "first": c["first"], "first_pct": round(c["first"] / c["n"] * 100) if c["n"] else None,
                   "lag": round(sum(c["lag"]) / len(c["lag"]), 1) if c["lag"] else None,
                   "r": round(sum(c["r"]) / len(c["r"]), 1) if c["r"] else None}
    multi = [v for v in S.values() if len(v["first"]) >= 2 and not v["pre"]]
    gaps = sorted((dt.date.fromisoformat(v["first"][1][0]) - dt.date.fromisoformat(v["first"][0][0])).days for v in multi)
    return {"updated": (today or now_kst().strftime("%Y-%m-%d %H:%M")), "since": since,
            "rule": "채널(텔레그램·블로그) 글이 종목 이름을 처음 부른 때 · 수익률 = 그날(또는 뒤 첫 거래일) 종가 → 가장 최근 종가 · 채널 순위는 2채널 넘게 부른 종목 중 첫 언급이 기록 첫날 뒤인 것만 · 먼저 말한 채널이 더 낫다는 뜻은 아님",
            "n_multi": len(multi), "gap_med": gaps[len(gaps) // 2] if gaps else None, "same_day": sum(1 for g in gaps if g == 0),
            "s": S, "ch": ch}


def save_lead(L):
    if L:
        json.dump(L, open(LEAD, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("✓ lead 종목", len(L["s"]), "· 2채널+", L["n_multi"], "· 채널", len(L["ch"]))


def main():
    args = sys.argv[1:]
    idx_path = None
    if "--idx" in args:
        idx_path = args[args.index("--idx") + 1]
    D = build_dict(load_idx(idx_path))
    print("이름 사전", len(D))
    if "--selftest" in args:
        t = "SK하이닉스 실적 기대, 삼성전자도 강세. 디바이스 업종. 엔비디아 신고가"
        got = [n for n, _, _ in find_names(t, D)]
        print("selftest", got)
        assert "SK하이닉스" in got and "삼성전자" in got and "이닉스" not in got, got
        return 0
    items = load_men()
    if "--lead-offline" in args:   # 시세 없이 순서만(점검용)
        feed = json.load(open(FEED, encoding="utf-8"))
        save_lead(lead(items, {}, {x.get("id"): x.get("kind") for x in feed.get("sources") or []}))
        return 0
    if "--backfill" in args:
        items, added = merge(items, backfill(D))
        save_men(items)
        print("✓ backfill 언급", added, "· 모두", len(items))
        return 0
    feed = json.load(open(FEED, encoding="utf-8"))
    new = []
    for it in feed.get("items") or []:
        new += item_mentions(it, D)
    items, added = merge(items, new)
    save_men(items)
    print("언급 +", added, "· 모두", len(items))
    cut = (now_kst() - dt.timedelta(days=WIN_DAYS + 10)).strftime("%Y-%m-%d")
    codes = {m["s"] for m in items if m["d"] >= cut} | set(BENCH.values())
    old = {}
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        pass
    try:
        P = get_prices(codes, cut)
    except Exception as e:
        print("✗ 시세 못 받음", e); P = {}
    kinds = {x.get("id"): x.get("kind") for x in feed.get("sources") or []}
    try:
        save_lead(lead(items, P, kinds))
    except Exception as e:
        print("✗ lead", e)
    if not P and old.get("ch"):
        old["post"] = post_map(feed, D)
        json.dump(old, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("시세 없음 — 성적은 옛 값 유지"); return 0
    ch, base = score(items, P)
    R = {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "win_days": WIN_DAYS,
         "rule": "채널 글이 이름을 부른 종목 · 글 날짜 뒤 첫 거래일 종가 → 5·20거래일 뒤 종가 · 지수(코스피·S&P500) 대비도 · 사라/팔아라는 안 가림 — 「언급 뒤 올랐나」만",
         "base": base, "ch": ch, "post": post_map(feed, D)}
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("✓ feed_score 채널", len(ch), "· 전체", base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
