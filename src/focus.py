"""🎯 오늘의 집중 — "돈의 길 → 담는 법 → 행동" (10/7 사용자: "이 나라 이 섹터로 돈이 몰리고, 수혜 종목·ETF가 이거니 오늘 여기 집중하자")

  python -m src.focus          → market/focus.json (+ market/focus_log.json 성적 장부)

  입력: market/sectors.json (src.sectors 가 먼저 돈다) · CH Investing 나침반 compass.json(5개 시장)
        · 앱의 컵·갭 눈 검사 남김 목록 · 조용한 매집 목록 · opdata idx.json(종목 이름)
  1) 돈의 길: 5개 시장 점수(1주·1달 지수 + 오른 종목 비율) → 돈이 들어오는 나라
             섹터·테마 점수(S&P 대비 5일·20일 + 연속 강세) → 집중 테마 2개 (같은 계열은 하나만)
  2) 담는 법: 미국 ETF + 한국 상장 ETF(테마별 지정) + 관련주(미국·한국) — 우리 스캐너(컵·갭·매집)에 걸린 종목 ★
  3) 행동: 종목마다 「관심」「★관심(차트 자리)」「눌림 대기」「추격 금지」 + 테마마다 "이게 깨지면" 기준선(20일선·5일선)
  4) 성적: 매일 고른 테마 ETF 가 5거래일 뒤 S&P500 보다 나았나 → focus_log.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "focus.json"
LOG = ROOT / "market" / "focus_log.json"
KST = dt.timezone(dt.timedelta(hours=9))
RAW = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/"

# 테마(미국 ETF) → 한국 상장 ETF (한국 계좌로 바로 담는 법). 앞에 있는 게 대표
KR_ETF = {
    "XLK": [("381170.KS", "TIGER 미국테크TOP10"), ("133690.KS", "TIGER 미국나스닥100")],
    "XLC": [("365000.KS", "TIGER 인터넷TOP10")],
    "XLY": [("091180.KS", "KODEX 자동차")],
    "XLF": [("091170.KS", "KODEX 은행"), ("102970.KS", "KODEX 증권")],
    "XLV": [("453640.KS", "KODEX 미국S&P500헬스케어"), ("143860.KS", "TIGER 헬스케어")],
    "XLI": [("449450.KS", "PLUS K방산"), ("0115D0.KS", "KODEX 조선TOP10")],
    "XLE": [("218420.KS", "KODEX 미국S&P500에너지(합성)"), ("117460.KS", "KODEX 에너지화학")],
    "XLB": [("117680.KS", "KODEX 철강")],
    "XLU": [("487230.KS", "KODEX 미국AI전력핵심인프라"), ("487240.KS", "KODEX AI전력핵심설비")],
    "XLRE": [("329200.KS", "TIGER 리츠부동산인프라")],
    "IGV": [("481180.KS", "SOL 미국AI소프트웨어"), ("157490.KS", "TIGER 소프트웨어")],
    "SMH": [("381180.KS", "TIGER 미국필라델피아반도체나스닥"), ("091160.KS", "KODEX 반도체")],
    "CIBR": [("418670.KS", "TIGER 글로벌AI사이버보안"), ("157490.KS", "TIGER 소프트웨어")],
    "SKYY": [("371450.KS", "TIGER 글로벌클라우드컴퓨팅INDXX"), ("0127R0.KS", "RISE 미국AI클라우드인프라")],
    "BOTZ": [("445290.KS", "KODEX 로봇액티브"), ("0038A0.KS", "KODEX 미국휴머노이드로봇")],
    "IGM": [("381170.KS", "TIGER 미국테크TOP10")],
    "XBI": [("244580.KS", "KODEX 바이오"), ("364970.KS", "TIGER 바이오TOP10")],
    "IHI": [("143860.KS", "TIGER 헬스케어")],
    "KRE": [("091170.KS", "KODEX 은행")], "KBE": [("091170.KS", "KODEX 은행")],
    "IAI": [("102970.KS", "KODEX 증권"), ("157500.KS", "TIGER 증권")],
    "ITB": [("117700.KS", "KODEX 건설")],
    "ITA": [("449450.KS", "PLUS K방산"), ("0167Z0.KS", "KODEX 미국우주항공")],
    "PAVE": [("487240.KS", "KODEX AI전력핵심설비")], "GRID": [("487240.KS", "KODEX AI전력핵심설비"), ("487230.KS", "KODEX 미국AI전력핵심인프라")],
    "NLR": [("433500.KS", "ACE 원자력TOP10"), ("0098F0.KS", "KODEX 원자력SMR")], "URA": [("433500.KS", "ACE 원자력TOP10")],
    "TAN": [("457990.KS", "PLUS 태양광&ESS"), ("385510.KS", "KODEX 신재생에너지액티브")],
    "LIT": [("305720.KS", "KODEX 2차전지산업"), ("394670.KS", "TIGER 글로벌리튬&2차전지SOLACTIVE(합성)")],
    "XME": [("117680.KS", "KODEX 철강")], "COPX": [("160580.KS", "TIGER 구리실물")], "GDX": [("411060.KS", "ACE KRX금현물")],
    "XOP": [("218420.KS", "KODEX 미국S&P500에너지(합성)")], "ARKK": [("381170.KS", "TIGER 미국테크TOP10")],
}
MKT = {"US": ("🇺🇸", "미국"), "KR": ("🇰🇷", "한국"), "JP": ("🇯🇵", "일본"), "CN": ("🇨🇳", "중국"), "HK": ("🇭🇰", "홍콩")}


def get(url, t=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=t) as r:
        return r.read().decode("utf-8")


def jget(url, default=None):
    try:
        return json.loads(get(url))
    except Exception as e:
        print("  못 받음", url.split("/")[-1], e, file=sys.stderr)
        return default


def latest_accum():
    """앱 archive/accum/<가장 최근>/list.json (GitHub API 로 폴더 목록)"""
    try:
        j = json.loads(get("https://api.github.com/repos/chkchp0702-spec/daily-app/contents/archive/accum?ref=main"))
        days = sorted(x["name"] for x in j if x["type"] == "dir")
        if days:
            return jget(RAW + f"main/archive/accum/{days[-1]}/list.json", []) or []
    except Exception as e:
        print("  매집 목록 못 받음", e, file=sys.stderr)
    return []


def kr_quotes(codes):
    """한국 ETF 1·5일 등락 (yfinance)"""
    out = {}
    if not codes:
        return out
    try:
        import yfinance as yf
        df = yf.download(sorted(codes), period="1mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
        for c in codes:
            try:
                s = (df[c]["Close"] if len(codes) > 1 else df["Close"]).dropna()
                v = list(s.values)
                if len(v) >= 6:
                    out[c] = {"last": round(float(v[-1]), 2), "r1": round((v[-1] / v[-2] - 1) * 100, 2), "r5": round((v[-1] / v[-6] - 1) * 100, 2)}
            except Exception:
                pass
    except Exception as e:
        print("  한국 ETF 시세 실패", e, file=sys.stderr)
    return out


def act(r1, r5, star):
    if r1 is not None and r1 >= 8:
        return "추격 금지"
    if r5 is not None and r5 >= 15:
        return "눌림 대기"
    return "★ 관심" if star else "관심"


def main() -> int:
    S = json.loads((ROOT / "market" / "sectors.json").read_text(encoding="utf-8"))
    rows = {r["sym"]: r for r in S.get("rows", [])}
    spy = S.get("spy") or {}
    # ── 1) 나라: 나침반 5개 시장
    C = jget(RAW + "opdata/compass.json", {}) or {}
    countries = []
    for k, m in (C.get("markets") or {}).items():
        ix = (m.get("index") or [{}])[0]
        c5, c20, b10 = ix.get("chg5"), ix.get("chg20"), m.get("breadth10")
        if c5 is None:
            continue
        sc = c5 + (c20 or 0) * 0.5 + ((b10 or 50) - 50) / 5
        hot = []
        for x in (m.get("strong") or []):
            if (x.get("n") or 0) >= 4 and x.get("r1") is not None:
                br = x["up"] / x["n"] if x.get("n") else .5
                hot.append((x["r1"] + (x.get("r5") or 0) * .5 + (br - .5) * 4, x))
        hot = [{"name": x["name"], "r1": x.get("r1"), "r5": x.get("r5"), "lead": [{"s": y.get("s"), "n": y.get("n"), "r1": y.get("r1")} for y in (x.get("lead") or [])[:3]]}
               for _, x in sorted(hot, key=lambda z: -z[0])[:2]]
        countries.append({"hot": hot, "k": k, "flag": MKT.get(k, ("", k))[0], "name": MKT.get(k, ("", k))[1], "ix": ix.get("name"), "chg1": ix.get("chg1"),
                          "chg5": c5, "chg20": c20, "breadth10": b10, "regime": m.get("regime"), "date": m.get("date"), "score": round(sc, 2)})
    countries.sort(key=lambda x: -x["score"])
    for i, c in enumerate(countries):
        c["label"] = "돈이 들어오는 곳" if i == 0 and c["score"] > 0 else ("빠지는 곳" if c["score"] < -2 else "")
    # ── 2) 테마: S&P 대비 5일·20일 + 연속 강세, 같은 계열은 하나만
    fam_of = {}
    for f in S.get("families", []):
        for s_ in f.get("syms", []):
            fam_of[s_] = f["name"]
    cand = []
    for r in S.get("rows", []):
        if (r.get("r5") or 0) <= 0 or (r.get("r20") or 0) <= 0:
            continue
        sc = (r.get("rs5") or 0) + (r.get("rs20") or 0) * 0.5 + min(r.get("streak") or 0, 10) * 0.3 + (1 if r.get("kind") == "theme" else 0)
        cand.append((sc, r))
    cand.sort(key=lambda x: -x[0])
    picked, fams = [], set()
    for sc, r in cand:
        f = fam_of.get(r["sym"], r["sym"])
        if f in fams:
            continue
        picked.append((sc, r))
        fams.add(f)
        if len(picked) == 2:
            break
    # 스캐너·이름
    ec = jget(RAW + "main/archive/x/eye_cup.json", {}) or {}
    eg = jget(RAW + "main/archive/x/eye_gap.json", {}) or {}
    acc = latest_accum()
    star = {}
    for c in ec.get("keep", []):
        star[c] = "컵"
    for c in eg.get("keep", []):
        star.setdefault(c, "갭")
    for a in acc[:40]:
        c = a.get("code") if isinstance(a, dict) else None
        if c:
            star.setdefault(c, "매집")
    idx = jget(RAW + "opdata/idx.json", []) or []
    names = {x[0]: x[1] for x in idx}
    kr_codes = {c for sc, r in picked for c, _ in KR_ETF.get(r["sym"], [])}
    krq = kr_quotes(kr_codes)
    themes = []
    for sc, r in picked:
        mem = r.get("members") or {}
        st = []
        for x in (mem.get("us") or [])[:6]:
            st.append({"t": x["t"], "name": names.get(x["t"], x["t"]), "mkt": "US", "r1": x.get("r1"), "r5": x.get("r5"), "r20": x.get("r20"), "star": star.get(x["t"])})
        for x in (mem.get("kr") or [])[:6]:
            st.append({"t": x["t"], "name": names.get(x["t"], x.get("n")), "mkt": "KR", "r1": x.get("r1"), "r5": x.get("r5"), "r20": x.get("r20"), "star": star.get(x["t"])})
        for x in st:
            x["act"] = act(x["r1"], x["r5"], x["star"])
        # 미국 4 + 한국 4: ★ 먼저, 그다음 5일 강한 순 (추격 금지는 뒤로)
        key = lambda x: (x["act"] == "추격 금지", not x["star"], -(x["r5"] or -99))
        us = sorted([x for x in st if x["mkt"] == "US"], key=key)[:4]
        kr = sorted([x for x in st if x["mkt"] == "KR"], key=key)[:4]
        last, m5, m20 = r.get("last"), r.get("ma5"), r.get("ma20")
        stop = ""
        if last and m20:
            stop = f"{r['sym']} 20일선 {m20:,.2f} 아래로 마감하면 주도 끝 (지금 {(last / m20 - 1) * 100:+.1f}% 위)"
            if m5:
                stop += f" · 5일선 {m5:,.2f} 이탈은 1차 경고"
        why = []
        if (r.get("streak") or 0) >= 3:
            why.append(f"S&P보다 강한 날 {r['streak']}일 연속")
        if r.get("rs20") is not None:
            why.append(f"20일 S&P 대비 {r['rs20']:+.1f}%p")
        if r.get("off_hi") is not None:
            why.append("52주 고점 " + ("돌파 중" if r["off_hi"] >= -1 else f"{r['off_hi']:.1f}%"))
        if (r.get("rank_chg") or 0) >= 3:
            why.append(f"5일 순위 {r['rank_prev']}→{r['rank']}위로 올라옴")
        themes.append({"sym": r["sym"], "name": r["name"], "kind": r.get("kind"), "score": round(sc, 2),
                       "r1": r.get("r1"), "r5": r.get("r5"), "r20": r.get("r20"), "rs5": r.get("rs5"), "rs20": r.get("rs20"),
                       "streak": r.get("streak"), "off_hi": r.get("off_hi"), "last": last, "ma5": m5, "ma20": m20,
                       "etf_us": {"t": r["sym"], "r1": r.get("r1"), "r5": r.get("r5"), "act": act(r.get("r1"), r.get("r5"), False)},
                       "etf_kr": [{"t": c, "name": n, **krq.get(c, {}), "act": act(krq.get(c, {}).get("r1"), krq.get(c, {}).get("r5"), False)} for c, n in KR_ETF.get(r["sym"], [])],
                       "us": us, "kr": kr, "stop": stop, "why_auto": " · ".join(why)})
    avoid = [{"sym": s_, "name": rows[s_]["name"], "r5": rows[s_].get("r5"), "r20": rows[s_].get("r20")} for s_ in (S.get("cold") or [])[:3] if s_ in rows]
    # ── 4) 성적 장부: 5거래일(≈7일) 지난 픽 채점
    today = dt.datetime.now(KST).strftime("%Y-%m-%d")
    try:
        log = json.loads(LOG.read_text(encoding="utf-8"))
    except Exception:
        log = []
    asof = S.get("asof") or today
    for e in log:
        if e.get("res") is None and e["sym"] in rows and spy.get("last") and \
                (dt.date.fromisoformat(asof) - dt.date.fromisoformat(e["asof"])).days >= 7:
            a = (rows[e["sym"]]["last"] / e["last"] - 1) * 100
            b = (spy["last"] / e["spy"] - 1) * 100 if e.get("spy") else 0
            e.update({"res": round(a, 2), "spy_res": round(b, 2), "ex": round(a - b, 2), "graded": asof})
    if spy.get("last"):
        for t in themes:
            if not any(e["asof"] == asof and e["sym"] == t["sym"] for e in log):
                log.append({"date": today, "asof": asof, "sym": t["sym"], "name": t["name"], "last": t["last"], "spy": spy["last"], "res": None})
    log = log[-200:]
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=0), encoding="utf-8")
    g = [e for e in log if e.get("res") is not None]
    score = {"n": len(g), "hit": sum(1 for e in g if e["ex"] > 0), "avg_ex": round(sum(e["ex"] for e in g) / len(g), 2) if g else None,
             "recent": g[-5:][::-1], "open": [e for e in log if e.get("res") is None][-4:]}
    out = {"asof": asof, "built_kst": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "spy": spy,
           "countries": countries, "themes": themes, "avoid": avoid, "score": score}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"집중: {' / '.join(t['name'] for t in themes)} · 나라 1위 {countries[0]['name'] if countries else '-'} · 성적 {score['hit']}/{score['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
