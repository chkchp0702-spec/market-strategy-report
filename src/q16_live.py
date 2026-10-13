"""📈 Q16 매일 신호 (사용자 10/13: "16-2,3,5 진행하고 반영시켜") → market/q16_live.json (src/kick_sleeve.py 가 읽음)

  🔌 cust — Q16-2 고객사 → 납품사: market/cust_links.json 짝마다, 고객사 그날 ≥ th% · 거래량 ≥1.5배 인데 납품사 ≤ 고객사 × ratio
  🕵 ins  — Q16-5 내부자 「평소와 다른」 매수: openinsider.com 최근 7일 장내 매수(P, SEC Form 4 모음 — SEC 원본은 실행기 IP 403),
           습관형(직전 3년 모두 같은 달 매매, market/insider_hist.json.gz)은 빼고, 10일 안 k명 · 합계 v달러 이상이면 신호(공시일)
  규칙 숫자는 과거 검증 결과(market/q16_bt.json 의 pick)를 그대로 쓴다. 없으면 아래 기본값.
  🎰 MAX 거름망(Q16-3)은 kick_sleeve 가 시세를 받은 뒤 직접 계산한다.

  python -m src.q16_live            (KST 07:25 화~토, .github/workflows/q16-live.yml)
  python -m src.q16_live selftest   (네트워크 없이 파싱·규칙 점검)
"""
from __future__ import annotations
import datetime as dt
import gzip
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "q16_live.json"
BT = ROOT / "market" / "q16_bt.json"
LINKS = ROOT / "market" / "cust_links.json"
HIST = ROOT / "market" / "insider_hist.json.gz"
STORE = ROOT / "market" / "insider_live.json"
KST = dt.timezone(dt.timedelta(hours=9))
UA = {"User-Agent": "CH-Investing-Research research-bot@users.noreply.github.com"}
DEF = {"cust": {"th": 5.0, "ratio": 1 / 3}, "ins": {"mode": "A", "kmin": 2, "vmin": 100_000}}


def _rj(p, d=None):
    try:
        if str(p).endswith(".gz"):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                return json.load(f)
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d if d is not None else {}


def rules():
    b = _rj(BT)
    out = json.loads(json.dumps(DEF))
    try:
        m = re.match(r"고객사≥(\d+(?:\.\d+)?)%\|납품사≤고객사×([\d.]+)", b["cust"]["pick"]["rule"])
        out["cust"] = {"th": float(m.group(1)), "ratio": float(m.group(2))}
    except Exception:
        pass
    try:
        m = re.match(r"기회형([AB])\|(\d)명↑\|(\d+)천달러↑", b["ins"]["pick"]["rule"])
        out["ins"] = {"mode": m.group(1), "kmin": int(m.group(2)), "vmin": int(m.group(3)) * 1000}
    except Exception:
        pass
    return out


# ───────────────────────── 🔌 고객사 → 납품사 ─────────────────────────
def cust_signals(R, errors):
    import yfinance as yf
    import numpy as np
    L = _rj(LINKS).get("links", {})
    tks = sorted(set(L) | {c for v in L.values() for c in v["cus"]})
    df = yf.download(tks, period="6mo", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    out = []
    for sup, v in L.items():
        for cus in v["cus"]:
            try:
                S, C = df[sup].dropna(subset=["Close"]), df[cus].dropna(subset=["Close"])
                j = S.index.intersection(C.index)
                S, C = S.loc[j], C.loc[j]
                cc, cv, sc = C["Close"].to_numpy(float), C["Volume"].to_numpy(float), S["Close"].to_numpy(float)
                for ti in range(max(51, len(j) - 5), len(j)):
                    cr = (cc[ti] / cc[ti - 1] - 1) * 100
                    sr = (sc[ti] / sc[ti - 1] - 1) * 100
                    vr = cv[ti] / np.nanmean(cv[ti - 50:ti])
                    if cr >= R["th"] and vr >= 1.5 and sr <= cr * R["ratio"]:
                        out.append({"src": "cust", "code": sup, "name": sup, "mkt": "US", "d": str(j[ti].date()), "score": round(cr, 1),
                                    "note": f"고객 {cus} {cr:+.1f}%(거래량 {vr:.1f}배) · {sup} {sr:+.1f}% — {v.get('memo', '')}"})
            except Exception as e:
                errors.append(f"cust {sup}/{cus}: {repr(e)[:80]}")
    return out


# ───────────────────────── 🕵 내부자 ─────────────────────────
def norm(x):
    return str(x or "").strip().upper()


OI = ("http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd={days}&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1"
      "&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1")
OUA = {"User-Agent": "Mozilla/5.0 (compatible; CHInvestingResearch/1.0; +https://github.com/chkchp0702-spec)"}


def parse_oi(html):
    """openinsider 표 → [{tk, icik(=티커), ocik(=이름 대문자), code, td, fd, val, acc}]"""
    import io
    import pandas as pd
    tabs = pd.read_html(io.StringIO(html), attrs={"class": "tinytable"})
    if not tabs:
        return []
    t = tabs[0]
    t.columns = [str(c).replace("\xa0", " ").strip() for c in t.columns]
    col = lambda *ks: next((c for c in t.columns if any(k.lower() == c.lower() for k in ks)), None)
    rows = []
    for _, x in t.iterrows():
        tk = str(x[col("Ticker")]).upper().strip().replace(".", "-")
        nm = norm(x[col("Insider Name", "Insider")])
        try:
            val = abs(float(re.sub(r"[^0-9.\-]", "", str(x[col("Value")])) or 0))
        except ValueError:
            val = 0.0
        fd, td = str(x[col("Filing Date", "Filing")])[:10], str(x[col("Trade Date", "Trade")])[:10]
        rows.append({"tk": tk, "icik": tk, "ocik": nm, "code": "P", "td": td, "fd": fd, "val": round(val), "acc": f"{fd}|{nm}|{tk}|{td}"})
    return rows


def oi_recent(days, errors):
    """SEC 원본은 깃허브 실행기 IP 에서 403 → openinsider.com 최근 장내 매수(P)"""
    import requests
    try:
        r = requests.get(OI.format(days=days), headers=OUA, timeout=60)
        r.raise_for_status()
        return parse_oi(r.text)
    except Exception as e:
        errors.append(f"openinsider: {repr(e)[:120]}")
        return []


def routine_of(hist, ocik, icik, td):
    y, m = int(td[:4]), int(td[5:7])
    ms = set(hist.get(f"{ocik}|{icik}", []))
    rt = all(f"{y - i}-{m:02d}" in ms for i in (1, 2, 3))
    h3 = all(any(s.startswith(f"{y - i}-") for s in ms) for i in (1, 2, 3))
    return rt, h3


def ins_signals(store, R, hist):
    """store 의 최근 매수(P) → 기회형만 → 회사별 10일 창 k명·v달러 → 신호"""
    buys = []
    for x in store:
        if x["code"] != "P" or not x.get("val"):
            continue
        rt, h3 = routine_of(hist, x["ocik"], x["icik"], x["td"] or x["fd"])
        if rt or (R["mode"] == "B" and not h3):
            continue
        buys.append(x)
    out = []
    by = {}
    for x in sorted(buys, key=lambda x: x["fd"]):
        by.setdefault(x["tk"], []).append(x)
    for tk, g in by.items():
        last = None
        for i, x in enumerate(g):
            d1 = dt.date.fromisoformat(x["fd"])
            win = [y for y in g[:i + 1] if (d1 - dt.date.fromisoformat(y["fd"])).days <= 10]
            own = {y["ocik"] for y in win}
            val = sum(y["val"] for y in win)
            if len(own) >= R["kmin"] and val >= R["vmin"] and (last is None or (d1 - last).days > 30):
                out.append({"src": "ins", "code": tk, "name": tk, "mkt": "US", "d": x["fd"], "score": round(min(30, len(own) * 5 + val / 1e5), 1),
                            "note": f"기회형 내부자 {len(own)}명 · {val / 1e3:,.0f}천 달러 (10일 안 공시)"})
                last = d1
    return out


def main():
    now = dt.datetime.now(KST)
    R = rules()
    errors, log = [], []
    try:
        log += cust_signals(R["cust"], errors)
    except Exception as e:
        errors.append(f"cust: {repr(e)[:200]}")
    hist = _rj(HIST, {}).get("h", {})
    st = _rj(STORE, {"rows": []})
    try:
        sys.path.insert(0, str(ROOT / "src"))
        import accum_bt as AB
        uni = set(AB.universe("US", {}))
        new = [x for x in oi_recent(7, errors) if x["tk"] in uni]
        have = {x["acc"] for x in st["rows"]}
        st["rows"] += [x for x in new if x["acc"] not in have]
        cut = (now.date() - dt.timedelta(days=45)).isoformat()
        st["rows"] = [x for x in st["rows"] if x["fd"] >= cut]
        st["at"] = now.strftime("%F %H:%M")
        st["src"] = "openinsider.com (SEC Form 4 장내 매수 모음) · 유니버스 S&P500+400"
        STORE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        errors.append(f"insider: {repr(e)[:200]}")
    log += ins_signals(st["rows"], R["ins"], hist)
    prev = _rj(OUT, {"log": []}).get("log", [])
    keep = {(x["src"], x["code"], x["d"]) for x in log}
    cut = (now.date() - dt.timedelta(days=60)).isoformat()
    log += [x for x in prev if (x["src"], x["code"], x["d"]) not in keep and x["d"] >= cut]
    log.sort(key=lambda x: (x["d"], x["src"]), reverse=True)
    out = {"at": now.strftime("%F %H:%M"), "rules": R, "hist_ok": bool(hist), "log": log, "errors": errors[:30],
           "note": "🔌 고객사→납품사(Q16-2) · 🕵 내부자 기회형 매수(Q16-5) 매일 신호 — 킥에 들어갈지는 과거 검증 판정(market/q16_bt.json)대로"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if k != "log" else v[:10]) for k, v in out.items()}, ensure_ascii=False)[:3000])


def selftest():
    html = """<table class="tinytable"><thead><tr><th>X</th><th>Filing&nbsp;Date</th><th>Trade&nbsp;Date</th><th>Ticker</th><th>Insider Name</th><th>Title</th>
<th>Trade&nbsp;Type</th><th>Price</th><th>Qty</th><th>Owned</th><th>ΔOwn</th><th>Value</th></tr></thead><tbody>
<tr><td>M</td><td>2026-10-10 16:05:11</td><td>2026-10-09</td><td>BRK.B</td><td>Doe John</td><td>Dir</td><td>P - Purchase</td><td>$75.50</td><td>+1,000</td><td>5,000</td><td>+25%</td><td>+$75,500</td></tr>
<tr><td>M</td><td>2026-10-12 16:05:11</td><td>2026-10-10</td><td>BRK.B</td><td>Roe Jane</td><td>CEO</td><td>P - Purchase</td><td>$75.00</td><td>+400</td><td>5,000</td><td>+5%</td><td>+$30,000</td></tr>
</tbody></table>"""
    r = parse_oi(html)
    assert r[0]["tk"] == "BRK-B" and r[0]["ocik"] == "DOE JOHN" and r[0]["val"] == 75500 and r[0]["fd"] == "2026-10-10", r
    hist = {"DOE JOHN|BRK-B": ["2023-10", "2024-10", "2025-10"]}
    assert routine_of(hist, "DOE JOHN", "BRK-B", "2026-10-09") == (True, True)
    assert routine_of(hist, "DOE JOHN", "BRK-B", "2026-11-09") == (False, True)
    s = ins_signals(r, {"mode": "A", "kmin": 2, "vmin": 100000}, {})
    assert len(s) == 1 and s[0]["d"] == "2026-10-12", s
    assert ins_signals(r, {"mode": "A", "kmin": 2, "vmin": 100000}, hist) == []      # 첫 사람이 습관형 → 1명뿐
    print("selftest ok", rules())


if __name__ == "__main__":
    selftest() if sys.argv[1:] == ["selftest"] else main()
