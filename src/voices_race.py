"""🗣 목소리 경주 — 10/27 A10/27-1 (사용자 「1번만 하자」)
   「누구 말을 따랐어야 했나」: 앱 안 목소리마다 「처음 부른 날 종가에 같은 돈을 넣고 지금까지 들고 있었다면」을 날짜별로 계산해
   feeds/voices_race.json 으로 냄. 앱(daily-app voices.js)이 💼 포트 탭에서 포트·지수 선과 한 그림으로 그림.

   목소리
   · 📣 피드 채널(텔레그램·블로그) — feeds/mentions.json (src/feed_score.py 가 쌓는 「글이 이름을 부른 종목」)
   · 🔎 아침 거르기 거름망 4종 — daily-app archive/screen/<날짜>/screens.json (quiet·lead·hush·triple)
   · ⚡ 킥이 고른 종목 — market/kick.json open·closed (d0 = 고른 날)
   · 👁 내 눈은 휴대폰에만 있어서 앱이 같은 규칙으로 계산(이 파일의 px 표 = 거르기 종목 종가)

   규칙(숫자를 지어내지 않음)
   · 한 목소리가 한 종목을 「처음」 부른 날 한 번만 삼(같은 종목을 매일 불러도 한 번) · 판 적은 없음(그대로 들고 있음)
   · 산 값 = 부른 날(또는 그 뒤 첫 거래일) 종가. 한국·일본은 15:30 넘어 올라온 글이면 다음 거래일 종가(그날 종가엔 못 사니까)
   · 부를 때마다 같은 돈 → 그날 값 = 그때까지 산 종목들의 수익률 평균(넣은 돈 대비)
   · 「그림자」 = 같은 날 같은 돈을 그 나라 지수(코스피·S&P500·닛케이·항셍·상해)에 넣었다면 → 지수 대비 %p
   · 통화는 각 나라 돈 그대로(환율 뺌) · 시세 없는 종목은 빼고 「빠짐 n」
   · 언급 = 추천 아님(「팔아라」 글도 「부른 날 샀다면」으로 셈) — 앱 카드에 그대로 적음

   사용
     python -m src.voices_race                 # 시세(야후) 받아 계산 → feeds/voices_race.json
     python -m src.voices_race --selftest      # 가짜 시세로 규칙 검사
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEN = ROOT / "feeds" / "mentions.json"
KICK = ROOT / "market" / "kick.json"
OUT = ROOT / "feeds" / "voices_race.json"
SCR_URL = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/archive/screen/{d}/screens.json"
KST = dt.timezone(dt.timedelta(hours=9))
BENCH = {"KR": "^KS11", "US": "^GSPC", "JP": "^N225", "HK": "^HSI", "CN": "000001.SS"}
BNAME = {"^KS11": "코스피", "^GSPC": "S&P500", "^N225": "닛케이", "^HSI": "항셍", "000001.SS": "상해종합"}
SCR = [("quiet", "🤫", "조용한 돈 유입"), ("lead", "🏆", "섹터 1등주"), ("hush", "🌱", "조용한 신고가"), ("triple", "🐋", "고래+임원+차트")]
LATE = {"KR": "15:30", "JP": "15:30"}     # 이 시각 넘은 글 → 그날 종가엔 못 삼


def now_kst():
    return dt.datetime.now(KST)


def mk_of(s: str) -> str:
    s = str(s)
    if s.endswith((".KS", ".KQ")):
        return "KR"
    if s.endswith(".T"):
        return "JP"
    if s.endswith(".HK"):
        return "HK"
    if s.endswith((".SS", ".SZ")):
        return "CN"
    return "US"


def next_day(d: str) -> str:
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()


# ───────── 부른 기록 모으기 ─────────
def calls_channels(items, start):
    """{src: {"name", "kind":"ch", "calls": {sym: (기준일, 이름, 나라)}}}"""
    V = {}
    for m in sorted(items, key=lambda m: (m["d"], m.get("t") or "")):
        if m["d"] < start:
            continue
        v = V.setdefault("ch:" + m["src"], {"name": m.get("ch") or m["src"], "ic": "📣", "kind": "ch", "calls": {}})
        if m["s"] in v["calls"]:
            continue
        mk = m.get("mk") or mk_of(m["s"])
        d = m["d"]
        if mk in LATE and (m.get("t") or "") >= LATE[mk]:
            d = next_day(d)
        v["calls"][m["s"]] = (d, m.get("n") or m["s"], mk)
    return V


def load_screens(start, today, fetch=None):
    """날짜 → screens.json (없는 날은 건너뜀)"""
    fetch = fetch or (lambda u: json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8")))
    out = {}
    d = dt.date.fromisoformat(start)
    end = dt.date.fromisoformat(today)
    while d <= end:
        try:
            out[d.isoformat()] = fetch(SCR_URL.format(d=d.isoformat()))
        except Exception:
            pass
        d += dt.timedelta(days=1)
    return out


def calls_screens(days: dict):
    V = {}
    meta = {}
    for day in sorted(days):
        D = days[day] or {}
        for k, ic, nm in SCR:
            v = V.setdefault("scr:" + k, {"name": nm, "ic": ic, "kind": "scr", "calls": {}})
            for r in D.get(k) or []:
                s = r.get("s")
                if not s:
                    continue
                mk = r.get("m") or mk_of(s)
                meta.setdefault(s, [r.get("n") or s, mk])
                if s not in v["calls"]:
                    v["calls"][s] = (D.get("date") or day, r.get("n") or s, mk)   # 아침 9시 반에 나옴 → 그날 종가에 살 수 있음
    return V, meta


def calls_kick(K: dict, start):
    v = {"name": "킥이 고른 종목", "ic": "⚡", "kind": "kick", "calls": {}}
    rows = list(K.get("closed") or []) + list(K.get("open") or [])
    for r in sorted(rows, key=lambda r: r.get("d0") or ""):
        s, d0 = r.get("code"), r.get("d0")
        if not s or not d0 or d0 < start or s in v["calls"]:
            continue
        v["calls"][s] = (d0, r.get("name") or s, r.get("mkt") or mk_of(s))
    return {"kick": v} if v["calls"] else {}


# ───────── 시세 ─────────
def get_prices(codes, start):
    import yfinance as yf
    P = {}
    codes = sorted(set(codes))
    for i in range(0, len(codes), 80):
        chunk = codes[i:i + 80]
        try:
            h = yf.download(chunk, start=start, interval="1d", progress=False, auto_adjust=False, threads=True, group_by="ticker")
        except Exception as e:
            print("✗ 시세", e)
            continue
        for c in chunk:
            try:
                s = (h[c]["Close"] if len(chunk) > 1 else h["Close"]).dropna()
                if hasattr(s, "columns"):
                    s = s.iloc[:, 0]
                if len(s):
                    P[c] = {d.strftime("%Y-%m-%d"): float(v) for d, v in s.items() if float(v) > 0}
            except Exception:
                pass
    print("시세", len(P), "/", len(codes))
    return P


# ───────── 계산 ─────────
def entry(ser: dict, d: str):
    """d 이후(포함) 첫 거래일 (날짜, 종가) 또는 None"""
    for x in sorted(ser):
        if x >= d:
            return x, ser[x]
    return None


def ffill(ser: dict, cal):
    out, last = [], None
    for d in cal:
        if d in ser:
            last = ser[d]
        out.append(last)
    return out


def race(V: dict, P: dict, cal):
    """목소리마다 날짜별 「넣은 돈 대비 수익률 %」·그림자(같은 날 지수)·종목 목록"""
    FF = {}

    def ff(s):
        if s not in FF:
            FF[s] = ffill(P.get(s) or {}, cal)
        return FF[s]

    res = []
    for key, v in V.items():
        pos, miss = [], 0
        for s, (d, nm, mk) in v["calls"].items():
            ser = P.get(s)
            e = entry(ser, d) if ser else None
            b = BENCH.get(mk, "^GSPC")
            be = entry(P.get(b) or {}, e[0]) if e else None
            if not e or not be:
                miss += 1
                continue
            pos.append({"s": s, "n": nm, "mk": mk, "d": d, "ed": e[0], "px": e[1], "b": b, "bpx": be[1]})
        if not pos:
            continue
        curve, shadow, cnt = [], [], []
        for j, day in enumerate(cal):
            rs, bs = [], []
            for p in pos:
                if p["ed"] > day:
                    continue
                c, bc = ff(p["s"])[j], ff(p["b"])[j]
                if c is None or bc is None:
                    continue
                rs.append(c / p["px"] - 1)
                bs.append(bc / p["bpx"] - 1)
            curve.append(round(sum(rs) / len(rs) * 100, 2) if rs else None)
            shadow.append(round(sum(bs) / len(bs) * 100, 2) if bs else None)
            cnt.append(len(rs))
        last = cal[-1]
        picks = []
        for p in pos:
            c = ff(p["s"])[-1]
            picks.append([p["s"], p["n"], p["ed"], round((c / p["px"] - 1) * 100, 1) if c else None, p["mk"]])
        picks.sort(key=lambda x: -(x[3] if x[3] is not None else -1e9))
        r = curve[-1]
        sh = shadow[-1]
        up = sum(1 for x in picks if x[3] is not None and x[3] > 0)
        res.append({"k": key, "name": v["name"], "ic": v["ic"], "kind": v["kind"], "n": len(pos), "miss": miss, "first": min(p["ed"] for p in pos),
                    "ret": r, "shadow": sh, "ex": round(r - sh, 2) if r is not None and sh is not None else None, "up": up,
                    "curve": curve, "cnt": cnt, "picks": picks, "asof": last})
    res.sort(key=lambda x: -(x["ret"] if x["ret"] is not None else -1e9))
    return res


def bench_lines(P, cal, start):
    out = {}
    for b in ("^KS11", "^GSPC"):
        ser = P.get(b) or {}
        e = entry(ser, start)
        if not e:
            continue
        f = ffill(ser, cal)
        out[BNAME[b]] = [round((x / e[1] - 1) * 100, 2) if x is not None and d >= e[0] else None for d, x in zip(cal, f)]
    return out


def px_table(P, meta, cal):
    """거르기 종목 종가 표(👁 내 눈을 휴대폰에서 같은 규칙으로 계산) — 거래 없는 날은 null"""
    c = {}
    for s in sorted(meta):
        ser = P.get(s)
        if not ser:
            continue
        c[s] = [round(ser[d], 4) if d in ser else None for d in cal]
    bc = {b: [round(P[b][d], 4) if d in P[b] else None for d in cal] for b in BENCH.values() if b in P}
    return {"c": c, "meta": {s: meta[s] for s in c}, "bench": bc}


def build(V, P, meta, start):
    cal = sorted({d for s in P.values() for d in s if d >= start})
    if not cal:
        return None
    voices = race(V, P, cal)
    return {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "start": start, "dates": cal,
            "rule": "목소리마다 종목을 처음 부른 날(또는 그 뒤 첫 거래일) 종가에 같은 돈을 넣고 지금까지 들고 있었다면 — 넣은 돈 대비 수익률. "
                    "한국·일본은 15:30 넘은 글이면 다음 거래일 종가. 같은 종목은 한 번만. 그림자 = 같은 날 같은 돈을 그 나라 지수에. 각 나라 돈 기준(환율 뺌). "
                    "언급 = 추천 아님 — 「팔아라」 글도 「부른 날 샀다면」으로 셈.",
            "bench": {"코스피": "^KS11", "S&P500": "^GSPC"}, "lines": bench_lines(P, cal, start),
            "voices": voices, "px": px_table(P, meta, cal)}


def selftest():
    cal_p = {"A.KS": {"2026-10-09": 100, "2026-10-10": 110, "2026-10-13": 120},
             "B": {"2026-10-09": 50, "2026-10-10": 50, "2026-10-13": 40},
             "^KS11": {"2026-10-09": 1000, "2026-10-10": 1000, "2026-10-13": 1100},
             "^GSPC": {"2026-10-09": 10, "2026-10-10": 10, "2026-10-13": 10}}
    items = [{"d": "2026-10-09", "t": "16:00", "src": "x", "ch": "엑스", "s": "A.KS", "n": "가", "mk": "KR"},    # 15:30 넘음 → 10/10 110 에 삼
             {"d": "2026-10-09", "t": "09:00", "src": "x", "ch": "엑스", "s": "B", "n": "나", "mk": "US"},
             {"d": "2026-10-10", "t": "09:00", "src": "x", "ch": "엑스", "s": "A.KS", "n": "가", "mk": "KR"}]   # 두 번째 부름 → 안 셈
    V = calls_channels(items, "2026-10-09")
    R = build(V, cal_p, {}, "2026-10-09")
    v = R["voices"][0]
    # 10/9: B 만(0%) · 10/10: A 0%, B 0% · 10/13: A +9.09%, B −20% → 평균 −5.45%
    assert v["curve"] == [0.0, 0.0, -5.45], v["curve"]
    # 그림자: A → 코스피 10/10 1000 → 1100 (+10%), B → S&P 0% → 평균 +5%
    assert v["shadow"] == 5.0 and v["ex"] == -10.45, (v["shadow"], v["ex"])
    assert v["n"] == 2 and v["picks"][0][0] == "A.KS", v["picks"]
    assert R["lines"]["코스피"] == [0.0, 0.0, 10.0]
    print("selftest ok", v["curve"], v["shadow"], v["ex"])
    return 0


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    items = json.load(open(MEN, encoding="utf-8")).get("items") or []
    start = min(m["d"] for m in items) if items else "2026-10-09"
    today = now_kst().strftime("%Y-%m-%d")
    V = calls_channels(items, start)
    days = load_screens(start, today)
    print("거르기 날", len(days))
    SV, meta = calls_screens(days)
    V.update(SV)
    try:
        V.update(calls_kick(json.load(open(KICK, encoding="utf-8")), start))
    except Exception as e:
        print("✗ kick", e)
    codes = {s for v in V.values() for s in v["calls"]} | set(BENCH.values())
    pstart = (dt.date.fromisoformat(start) - dt.timedelta(days=7)).isoformat()
    P = get_prices(codes, pstart)
    if len(P) < 10:
        print("✗ 시세가 거의 없음 — 옛 파일 유지")
        return 0
    R = build(V, P, meta, start)
    if not R:
        print("✗ 날짜 없음")
        return 0
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("✓ voices_race", len(R["voices"]), "목소리 ·", len(R["dates"]), "날 ·", [(v["name"], v["n"], v["ret"]) for v in R["voices"][:5]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
