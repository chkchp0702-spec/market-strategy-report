"""🔥 주도 섹터·테마 레이더 — 「지금 돈이 어디로 몰리나」를 매일 아침 자동으로 계산한다.

왜: 리포트가 거시(금리·환율·지수)만 보다 보니, 미국 소프트웨어처럼 며칠째 시장을 이끄는 테마를 놓쳤다(10/6 사용자 지적).
무엇을:
  ① 미국 섹터 11개 + 테마 ETF 약 30개 — 1·5·20·60일 수익률, S&P500 대비(상대강도), S&P보다 강한 날 연속 일수,
     52주 고점까지 거리, 50·200일선 위/아래, 5일 전 대비 순위 변화(새로 뜬 곳 / 밀려난 곳), 테마별 대장주 5일 성적
  ② 종목 전체 기준 업종 강약 (CH Investing 나침반 compass.json — 미국·한국 업종 r1·r5, 끌어올린 종목)
  ③ 자동 문장 후보 (리포트 작성 단계가 고르고 다듬는다) + 킥 후보용 엇갈림 (src/kick.py 가 읽음)
출력: market/sectors.json
  python -m src.sectors
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .fetch_market import _get, _yahoo_warmup, KST

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "sectors.json"
COMPASS = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/opdata/compass.json"

# (티커, 이름, 종류, 대장주) — 종류: 섹터 / 테마
UNIVERSE = [
    ("XLK", "기술", "섹터", []), ("XLC", "통신·미디어", "섹터", []), ("XLY", "경기소비재", "섹터", []),
    ("XLF", "금융", "섹터", []), ("XLV", "헬스케어", "섹터", []), ("XLI", "산업재", "섹터", []),
    ("XLE", "에너지", "섹터", []), ("XLB", "소재", "섹터", []), ("XLU", "유틸리티", "섹터", []),
    ("XLRE", "부동산", "섹터", []), ("XLP", "필수소비재", "섹터", []),
    ("IGV", "소프트웨어", "테마", ["MSFT", "ORCL", "CRM", "NOW", "PLTR", "ADBE", "INTU", "SNOW"]),
    ("SMH", "반도체", "테마", ["NVDA", "TSM", "AVGO", "AMD", "MU", "ASML"]),
    ("CIBR", "사이버보안", "테마", ["PANW", "CRWD", "FTNT", "ZS", "NET"]),
    ("SKYY", "클라우드", "테마", ["DDOG", "MDB", "NET", "SNOW"]),
    ("BOTZ", "로봇·AI", "테마", ["ISRG", "ABBNY"]),
    ("IGM", "빅테크·인터넷", "테마", ["META", "GOOGL", "AMZN", "NFLX"]),
    ("XBI", "바이오", "테마", []), ("IHI", "의료기기", "테마", ["ISRG", "SYK", "BSX"]),
    ("KRE", "지역은행", "테마", []), ("KBE", "은행", "테마", ["JPM", "BAC", "WFC"]), ("IAI", "증권·거래소", "테마", ["GS", "MS", "SCHW", "HOOD"]),
    ("ITB", "주택건설", "테마", ["DHI", "LEN"]), ("XRT", "소매", "테마", []), ("IYT", "운송", "테마", ["UBER", "UNP", "FDX"]),
    ("JETS", "항공", "테마", []), ("ITA", "방산·우주", "테마", ["RTX", "LMT", "NOC", "GE"]),
    ("PAVE", "인프라·건설", "테마", ["ETN", "PWR", "URI"]), ("GRID", "전력망", "테마", ["ETN", "PWR", "VRT", "GEV"]),
    ("NLR", "원전", "테마", ["CEG", "VST", "OKLO", "SMR"]), ("URA", "우라늄", "테마", ["CCJ"]),
    ("TAN", "태양광", "테마", ["FSLR", "ENPH"]), ("LIT", "2차전지·리튬", "테마", ["ALB"]),
    ("XME", "금속·광산", "테마", ["FCX", "NUE"]), ("COPX", "구리", "테마", ["FCX", "SCCO"]), ("GDX", "금광", "테마", ["NEM", "AEM"]),
    ("XOP", "석유 개발", "테마", ["XOM", "COP"]), ("IBIT", "비트코인", "테마", ["COIN", "MSTR"]),
    ("ARKK", "혁신 성장", "테마", ["TSLA", "ROKU"]), ("IWM", "소형주", "테마", []), ("MTUM", "모멘텀", "테마", []),
]
REF = "SPY"
LOG: list[str] = []


def hist(sym: str, rng: str = "1y") -> list[tuple[str, float]]:
    """Yahoo 일봉 종가 [(날짜, 종가)] — 실패하면 []"""
    _yahoo_warmup()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval=1d"
    err = None
    for k, host in enumerate(("query2", "query1", "query2", "query1")):
        try:
            j = json.loads(_get(url.replace("query1", host)))
            res = j["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            out = [(datetime.fromtimestamp(t, tz=timezone.utc).astimezone(KST).strftime("%Y-%m-%d"), c)
                   for t, c in zip(res["timestamp"], q["close"]) if c is not None]
            return out
        except Exception as e:
            err = e
            time.sleep(1.5 * (k + 1))                       # 야후가 막으면(429) 조금씩 더 기다렸다 다시
    print(f"  {sym}: 실패 ({err})", file=sys.stderr)
    LOG.append(f"{sym}: {str(err)[:120]}")
    return []


MEMBERS = {  # 테마 → (미국 관련주, [(한국 코드, 이름)]) — 앱에서 테마를 누르면 보조 창에 나옴
 "XLK": (["NVDA","AAPL","MSFT","AVGO","ORCL","AMD","CRM","CSCO"], []),
 "XLC": (["META","GOOGL","NFLX","TMUS","DIS"], [("035420.KS","NAVER"),("035720.KS","카카오")]),
 "XLY": (["AMZN","TSLA","HD","MCD","BKNG","NKE"], [("005380.KS","현대차"),("000270.KS","기아")]),
 "XLF": (["BRK-B","JPM","V","MA","BAC","GS"], [("105560.KS","KB금융"),("055550.KS","신한지주"),("086790.KS","하나금융지주")]),
 "XLV": (["LLY","UNH","JNJ","ABBV","MRK","ISRG"], [("207940.KS","삼성바이오로직스"),("068270.KS","셀트리온")]),
 "XLI": (["GE","CAT","RTX","UBER","HON","ETN"], [("012450.KS","한화에어로스페이스"),("267260.KS","HD현대일렉트릭")]),
 "XLE": (["XOM","CVX","COP","EOG","SLB"], [("096770.KS","SK이노베이션"),("010950.KS","S-Oil")]),
 "XLB": (["LIN","SHW","FCX","NEM","NUE"], [("005490.KS","POSCO홀딩스"),("010130.KS","고려아연")]),
 "XLU": (["NEE","SO","CEG","VST","DUK"], [("015760.KS","한국전력")]),
 "XLRE": (["PLD","AMT","EQIX","WELL","O"], []),
 "XLP": (["WMT","COST","PG","KO","PEP"], [("097950.KS","CJ제일제당"),("271560.KS","오리온")]),
 "IGV": (["MSFT","ORCL","CRM","NOW","PLTR","ADBE","INTU","SNOW","WDAY","ADSK","APP","DDOG"], [("012510.KS","더존비즈온"),("018260.KS","삼성에스디에스"),("035420.KS","NAVER"),("035720.KS","카카오"),("030520.KQ","한글과컴퓨터"),("053800.KQ","안랩")]),
 "SMH": (["NVDA","TSM","AVGO","AMD","MU","ASML","QCOM","AMAT","LRCX","KLAC","ARM","INTC"], [("005930.KS","삼성전자"),("000660.KS","SK하이닉스"),("042700.KS","한미반도체"),("403870.KQ","HPSP"),("036930.KQ","주성엔지니어링"),("058470.KQ","리노공업")]),
 "CIBR": (["PANW","CRWD","FTNT","ZS","NET","OKTA","S","CYBR","CHKP","QLYS","TENB"], [("053800.KQ","안랩"),("263860.KQ","지니언스"),("042510.KQ","라온시큐어"),("150900.KQ","파수"),("067920.KQ","이글루코퍼레이션"),("136540.KQ","윈스")]),
 "SKYY": (["SNOW","DDOG","MDB","NET","NOW","CRM","ORCL","AMZN","MSFT","GOOGL","TEAM","HUBS"], [("012510.KS","더존비즈온"),("018260.KS","삼성에스디에스"),("093320.KQ","케이아이엔엑스"),("181710.KS","NHN")]),
 "BOTZ": (["NVDA","ISRG","TER","SYM","ROK"], [("454910.KS","두산로보틱스"),("277810.KQ","레인보우로보틱스"),("108490.KQ","로보티즈"),("090360.KQ","로보스타")]),
 "IGM": (["META","GOOGL","AMZN","NFLX","AAPL","MSFT","NVDA"], [("035420.KS","NAVER"),("035720.KS","카카오")]),
 "XBI": (["VRTX","REGN","ALNY","INSM","EXAS","SRPT","MRNA"], [("207940.KS","삼성바이오로직스"),("068270.KS","셀트리온"),("196170.KQ","알테오젠"),("028300.KQ","HLB")]),
 "IHI": (["ISRG","SYK","BSX","ABT","MDT","EW"], [("214150.KQ","클래시스"),("328130.KQ","루닛")]),
 "KRE": (["ZION","CFG","KEY","RF","HBAN","FITB"], [("105560.KS","KB금융"),("055550.KS","신한지주"),("086790.KS","하나금융지주")]),
 "KBE": (["JPM","BAC","WFC","C","USB","PNC"], [("105560.KS","KB금융"),("055550.KS","신한지주"),("086790.KS","하나금융지주")]),
 "IAI": (["GS","MS","SCHW","HOOD","IBKR","CME"], [("039490.KS","키움증권"),("006800.KS","미래에셋증권"),("016360.KS","삼성증권")]),
 "ITB": (["DHI","LEN","PHM","NVR","TOL"], [("000720.KS","현대건설"),("375500.KS","DL이앤씨"),("006360.KS","GS건설")]),
 "XRT": (["WMT","COST","AMZN","TGT","ANF"], [("139480.KS","이마트"),("023530.KS","롯데쇼핑")]),
 "IYT": (["UBER","UNP","FDX","UPS","ODFL","DAL"], [("086280.KS","현대글로비스"),("000120.KS","CJ대한통운")]),
 "JETS": (["DAL","UAL","AAL","LUV"], [("003490.KS","대한항공"),("272450.KS","진에어")]),
 "ITA": (["RTX","LMT","NOC","GD","GE","BA","LHX"], [("012450.KS","한화에어로스페이스"),("079550.KS","LIG넥스원"),("064350.KS","현대로템"),("047810.KS","한국항공우주")]),
 "PAVE": (["ETN","PWR","URI","VMC","MLM"], [("267260.KS","HD현대일렉트릭"),("298040.KS","효성중공업")]),
 "GRID": (["ETN","PWR","VRT","GEV","HUBB"], [("267260.KS","HD현대일렉트릭"),("298040.KS","효성중공업"),("010120.KS","LS ELECTRIC"),("103590.KS","일진전기")]),
 "NLR": (["CEG","VST","OKLO","SMR","CCJ","BWXT"], [("034020.KS","두산에너빌리티"),("052690.KS","한전기술"),("051600.KS","한전KPS"),("083650.KQ","비에이치아이")]),
 "URA": (["CCJ","UEC","NXE","DNN"], [("034020.KS","두산에너빌리티")]),
 "TAN": (["FSLR","ENPH","NXT","RUN","SEDG"], [("009830.KS","한화솔루션"),("112610.KS","씨에스윈드")]),
 "LIT": (["ALB","SQM","TSLA"], [("373220.KS","LG에너지솔루션"),("006400.KS","삼성SDI"),("247540.KQ","에코프로비엠"),("003670.KS","포스코퓨처엠")]),
 "XME": (["FCX","NUE","STLD","AA","CLF"], [("005490.KS","POSCO홀딩스"),("010130.KS","고려아연")]),
 "COPX": (["FCX","SCCO","TECK"], [("010130.KS","고려아연"),("103140.KS","풍산")]),
 "GDX": (["NEM","AEM","GOLD","WPM","FNV"], []),
 "XOP": (["XOM","COP","EOG","DVN","OXY"], [("096770.KS","SK이노베이션"),("010950.KS","S-Oil")]),
 "IBIT": (["COIN","MSTR","MARA","RIOT","HOOD"], []),
 "ARKK": (["TSLA","ROKU","COIN","PLTR","SHOP","CRSP"], []),
 "IWM": ([], []), "MTUM": ([], []),
}


BULK: dict[str, list[tuple[str, float]]] = {}


def bulk(syms: list[str], period: str = "1y") -> None:
    """yfinance 로 한꺼번에 받기 (요청 수가 적어 야후 429를 덜 맞음). 실패하면 하나씩(hist) 받는다."""
    try:
        import yfinance as yf
        df = yf.download(syms, period=period, interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
        for s_ in syms:
            try:
                ser = df[s_]["Close"].dropna()
                BULK[s_] = [(d.strftime("%Y-%m-%d"), float(v)) for d, v in ser.items()]
            except Exception:
                pass
        print(f"  yfinance 묶음 {len(BULK)}/{len(syms)}")
    except Exception as e:
        LOG.append(f"yfinance: {str(e)[:120]}")


def get_hist(sym: str, rng: str = "1y") -> list[tuple[str, float]]:
    h = BULK.get(sym)
    return h if h and len(h) > 5 else hist(sym, rng)


def ret(c: list[float], n: int, end: int = 0) -> float | None:
    """끝에서 end일 앞 기준, n일 수익률(%)"""
    i = len(c) - 1 - end
    if i - n < 0:
        return None
    return round((c[i] / c[i - n] - 1) * 100, 2)


def stats(h: list[tuple[str, float]], ref: list[tuple[str, float]]) -> dict | None:
    if len(h) < 30:
        return None
    rd = dict(ref)
    common = [(d, c) for d, c in h if d in rd]
    c = [x for _, x in h]
    out = {"asof": h[-1][0], "last": round(c[-1], 2)}
    for n in (1, 5, 20, 60):
        out[f"r{n}"] = ret(c, n)
    out["r5_prev"] = ret(c, 5, 5)                    # 5일 전 기준 5일 수익률 (순위 변화용)
    # S&P 보다 강한 날 연속 (하루 수익률 비교)
    st = 0
    for i in range(len(common) - 1, 0, -1):
        a = common[i][1] / common[i - 1][1] - 1
        b = rd[common[i][0]] / rd[common[i - 1][0]] - 1
        if a > b:
            st += 1
        else:
            break
    out["streak"] = st
    hi = max(c[-252:])
    out["off_hi"] = round((c[-1] / hi - 1) * 100, 2)        # 52주 고점까지 (%)
    ma = lambda n: sum(c[-n:]) / n if len(c) >= n else None
    m50, m200 = ma(50), ma(200)
    out["above50"] = bool(m50 and c[-1] > m50)
    out["above200"] = bool(m200 and c[-1] > m200)
    return out


def compass() -> dict:
    try:
        with urllib.request.urlopen(COMPASS, timeout=25) as r:
            j = json.loads(r.read().decode("utf-8"))
        res = {}
        for mk in ("US", "KR"):
            m = (j.get("markets") or {}).get(mk) or {}
            pick = lambda L: [{"name": x.get("name"), "r1": x.get("r1"), "r5": x.get("r5"), "n": x.get("n"),
                               "lead": [{"n": y.get("n"), "s": y.get("s"), "r1": y.get("r1"), "r5": y.get("r5")} for y in (x.get("lead") or x.get("hot") or [])[:3]]}
                              for x in (L or [])[:8]]
            res[mk] = {"date": m.get("date"), "strong": pick(m.get("strong")), "weak": pick(m.get("weak")),
                       "sectors": [{"name": s.get("name"), "r1": s.get("r1"), "r5": s.get("r5"), "r20": s.get("r20")} for s in (m.get("sectors") or [])]}
        return res
    except Exception as e:
        print("  나침반 실패", e, file=sys.stderr)
        return {}


def pct(v):
    return "–" if v is None else f"{v:+.1f}%"


def main() -> int:
    bulk([REF] + [u[0] for u in UNIVERSE] + sorted({t for u in UNIVERSE for t in u[3]} | {t for v in MEMBERS.values() for t in v[0]} | {k for v in MEMBERS.values() for k, _ in v[1]}))
    ref = get_hist(REF)
    if not ref:
        print("SPY 실패 — 중단", file=sys.stderr)
        (ROOT / "market" / "sectors_log.txt").write_text("\n".join(LOG), encoding="utf-8")
        return 1
    rs = stats(ref, ref)
    rows, leaders_needed = [], set()
    for sym, name, kind, leads in UNIVERSE:
        s = stats(get_hist(sym), ref)
        if not s:
            continue
        s.update({"sym": sym, "name": name, "kind": kind, "leaders": leads})
        for k in (5, 20, 60):
            if s.get(f"r{k}") is not None and rs.get(f"r{k}") is not None:
                s[f"rs{k}"] = round(s[f"r{k}"] - rs[f"r{k}"], 2)
        rows.append(s)
        leaders_needed.update(leads)
        if sym not in BULK:
            time.sleep(0.6)
    # 순위 (5일 상대강도) 지금 vs 5일 전
    rows.sort(key=lambda x: -(x.get("r5") if x.get("r5") is not None else -99))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    prev = sorted(rows, key=lambda x: -(x.get("r5_prev") if x.get("r5_prev") is not None else -99))
    for i, r in enumerate(prev):
        r["rank_prev"] = i + 1
        r["rank_chg"] = r["rank_prev"] - r["rank"]           # + = 올라옴
    # 대장주 5일 성적
    lead = {}
    for t in sorted(leaders_needed):
        h = get_hist(t, "3mo")
        if len(h) > 6:
            c = [x for _, x in h]
            lead[t] = {"r1": ret(c, 1), "r5": ret(c, 5), "r20": ret(c, 20) if len(c) > 21 else None}
        if t not in BULK:
            time.sleep(0.4)
    for r in rows:
        r["lead"] = sorted([dict(t=t, **lead[t]) for t in r["leaders"] if t in lead], key=lambda x: -(x["r5"] or -99))
        del r["leaders"]
        us, kr = MEMBERS.get(r["sym"], ([], []))
        def one(t):
            h = BULK.get(t) or []
            c = [x for _, x in h]
            return {"r1": ret(c, 1), "r5": ret(c, 5), "r20": ret(c, 20)} if len(c) > 6 else None
        mu = [dict(t=t, **one(t)) for t in us if one(t)]
        mk = [dict(t=t, n=n, **one(t)) for t, n in kr if one(t)]
        r["members"] = {"us": sorted(mu, key=lambda x: -(x["r5"] or -99)), "kr": sorted(mk, key=lambda x: -(x["r5"] or -99))}

    themes = [r for r in rows if r["kind"] == "테마"]
    sects = [r for r in rows if r["kind"] == "섹터"]
    key = lambda r: (r.get("rs20") or 0) * 0.5 + (r.get("rs5") or 0) + r.get("streak", 0) * 0.3
    hot = sorted(themes, key=key, reverse=True)
    cold = sorted(themes, key=key)
    risers = sorted([r for r in rows if r.get("rank_chg", 0) >= 8], key=lambda r: -r["rank_chg"])[:4]
    fallers = sorted([r for r in rows if r.get("rank_chg", 0) <= -8], key=lambda r: r["rank_chg"])[:4]

    # 자동 문장 후보 — 작성 단계가 고르고 숫자를 다시 확인한다
    notes = []
    by_ = {r["sym"]: r for r in rows}
    for r in hot[:3]:
        bits = [f"5일 {pct(r['r5'])}", f"20일 {pct(r['r20'])}", f"S&P보다 20일 {pct(r.get('rs20'))}"]
        if r["streak"] >= 3:
            bits.append(f"{r['streak']}일 연속 S&P보다 강함")
        if r["off_hi"] is not None and r["off_hi"] > -3:
            bits.append(f"52주 고점 {pct(r['off_hi'])}")
        ld = ", ".join(f"{x['t']} {pct(x['r5'])}" for x in r["lead"][:3])
        notes.append(f"🔥 {r['name']}({r['sym']}) " + " · ".join(bits) + (f" — 대장주 {ld}" if ld else ""))
    # 계열 묶음: 같은 흐름이 여러 ETF에 나뉘어 있을 때 (예: 소프트웨어 = IGV·CIBR·SKYY)
    FAM = [("소프트웨어 계열", ["IGV", "CIBR", "SKYY"]), ("반도체·AI 하드웨어", ["SMH", "BOTZ"]), ("빅테크", ["IGM", "XLC"]),
           ("원전·우라늄·전력", ["NLR", "URA", "GRID", "XLU"]), ("금융", ["XLF", "KBE", "KRE", "IAI"]), ("원자재·금", ["XME", "COPX", "GDX"]),
           ("에너지", ["XLE", "XOP"]), ("방산·인프라", ["ITA", "PAVE"]), ("경기민감 소비", ["XLY", "XRT", "ITB", "JETS"])]
    fam = []
    for nm, ss in FAM:
        R = [by_[x] for x in ss if x in by_ and by_[x].get("r5") is not None]
        if len(R) < 2:
            continue
        a5 = sum(r["r5"] for r in R) / len(R); a20 = sum((r.get("r20") or 0) for r in R) / len(R)
        fam.append({"name": nm, "syms": [r["sym"] for r in R], "r5": round(a5, 2), "r20": round(a20, 2), "rs5": round(a5 - (rs.get("r5") or 0), 2),
                    "all_up": all(r["r5"] > 0 for r in R), "best": max(R, key=lambda r: r["r5"])["sym"]})
    fam.sort(key=lambda f: -(f["rs5"] + f["r20"] / 4))
    for f in fam[:1]:
        if f["rs5"] > 1.5:
            notes.insert(0, f"🔥 {f['name']} 전체가 강함 — {'·'.join(f['syms'])} 평균 5일 {pct(f['r5'])} · 20일 {pct(f['r20'])} (S&P보다 5일 {pct(f['rs5'])}p){' · 모두 오름' if f['all_up'] else ''}")
    for f in fam[-1:]:
        if f["rs5"] < -1.5:
            notes.append(f"🧊 {f['name']} 전체가 약함 — 평균 5일 {pct(f['r5'])} · 20일 {pct(f['r20'])}")
    for r in risers[:2]:
        notes.append(f"⬆️ 새로 뜬 곳: {r['name']}({r['sym']}) 5일 순위 {r['rank_prev']}→{r['rank']}위 ({pct(r['r5'])})")
    for r in cold[:2]:
        notes.append(f"🧊 돈이 빠진 곳: {r['name']}({r['sym']}) 5일 {pct(r['r5'])} · 20일 {pct(r['r20'])}")

    # 킥 후보: 같은 큰 묶음 안에서 갈라진 것 (소프트웨어 vs 반도체 등) · 섹터 1등과 꼴등
    by = {r["sym"]: r for r in rows}
    pairs = [("IGV", "SMH", "소프트웨어 vs 반도체"), ("XLK", "XLE", "기술 vs 에너지"), ("IWM", "SPY", "소형주 vs S&P"),
             ("KRE", "XLF", "지역은행 vs 금융"), ("GDX", "IBIT", "금광 vs 비트코인"), ("XLY", "XLP", "경기소비재 vs 필수소비재"),
             ("CIBR", "IGV", "사이버보안 vs 소프트웨어"), ("NLR", "XLU", "원전 vs 유틸리티")]
    kick = []
    for a, b, lab in pairs:
        A, B = by.get(a), (by.get(b) if b != "SPY" else dict(rs, sym="SPY", name="S&P500"))
        if not A or not B or A.get("r5") is None or B.get("r5") is None:
            continue
        gap5 = A["r5"] - B["r5"]
        gap20 = (A.get("r20") or 0) - (B.get("r20") or 0)
        if abs(gap5) >= 3 or abs(gap20) >= 6:
            w, l = (A, B) if gap5 > 0 else (B, A)
            kick.append({"score": round(abs(gap5) + abs(gap20) / 2, 1), "label": lab,
                         "title": f"{w.get('name')} 5일 {pct(w['r5'])} vs {l.get('name')} {pct(l['r5'])} — 5일 차이 {abs(gap5):.1f}%p, 20일 {abs(gap20):.1f}%p",
                         "rows": [{"label": f"{w.get('name')} ({w.get('sym')}) 5일", "text": pct(w["r5"]), "dir": 1 if w["r5"] > 0 else -1, "hi": True},
                                  {"label": f"{l.get('name')} ({l.get('sym')}) 5일", "text": pct(l["r5"]), "dir": 1 if l["r5"] > 0 else -1},
                                  {"label": f"{w.get('name')} 20일", "text": pct(w.get("r20")), "dir": 1 if (w.get("r20") or 0) > 0 else -1},
                                  {"label": f"{l.get('name')} 20일", "text": pct(l.get("r20")), "dir": 1 if (l.get("r20") or 0) > 0 else -1}]})
    kick.sort(key=lambda x: -x["score"])

    out = {"fetched_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "asof": rs["asof"], "spy": rs,
           "rows": rows, "hot": [r["sym"] for r in hot[:6]], "cold": [r["sym"] for r in cold[:4]],
           "sectors_rank": [r["sym"] for r in sorted(sects, key=lambda r: -(r.get("r5") or -99))],
           "risers": [r["sym"] for r in risers], "fallers": [r["sym"] for r in fallers],
           "notes": notes, "families": fam, "kick": kick[:4], "compass": compass()}
    out["errors"] = LOG[:40]
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"섹터·테마 {len(rows)}개 · 대장주 {len(lead)}개 → {OUT}")
    for n in notes:
        print(" ", n)
    for k in kick[:3]:
        print("  ⚡", k["title"])
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:                               # 어떤 실패든 이유를 파일로 남김 (Actions 로그를 못 볼 때 대비)
        import traceback
        (ROOT / "market" / "sectors_log.txt").write_text(traceback.format_exc() + "\n" + "\n".join(LOG), encoding="utf-8")
        raise
    sys.exit(code)
