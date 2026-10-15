"""🇺🇸 미국 상장 전 종목 + ETF 목록 만들기 → src/lab/accum_uni/US.json

10/15 사용자: 「미국에 상장된 종목, ETF 다 동원해」 — 예전엔 S&P500+400(약 900개)만 썼음.
출처: 나스닥 트레이더 종목 사전(nasdaqlisted.txt · otherlisted.txt) = 나스닥·NYSE·NYSE American·
NYSE Arca·Cboe 등 미국 거래소에 상장된 모든 종목·ETF (장외 OTC 는 거래소 상장이 아니라 빠짐).

빼는 것 (거래 대상이 아닌 껍데기):
  · 시험용 종목(Test Issue = Y) · 워런트·유닛·권리·우선주(티커에 $ 또는 이름에 Warrant/Unit/Right/Preferred)
  · 레버리지·인버스 ETF (2배·3배·곱버스) — 사용자 결정 「1배·레버리지 없이」
나머지는 전부 넣음. 신호 계산 쪽 유동성 하한(주가 $5·거래대금 $5M, accum_bt.MKT)은 그대로라
거래 안 되는 종목은 받기만 하고 신호는 안 뜸.

python -m src.us_universe           → 받아서 US.json 저장
python -m src.us_universe selftest  → 거름 규칙 시험(인터넷 불필요)
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "lab" / "accum_uni" / "US.json"
URLS = {
    "nasdaq": ["https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
               "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt"],
    "other": ["https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
              "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt"],
}
MIN_OK = 5000   # 이보다 적으면 받기가 깨진 것으로 보고 기존 파일 유지

SHELL = re.compile(r"(?i)(\bwarrants?\b|(?<!common )\bunits?\b|\brights?\b|\bpreferred\b|\bnotes due\b|"
                   r"\bsubordinated\b|\bdebentures?\b|\bwhen[- ]issued\b)")
LEV = re.compile(r"(?i)(\d+(\.\d+)?\s?x\b|\d+(\.\d+)?x\s?(long|short|lev)|-\s?\d+(\.\d+)?x\b|leveraged|\bultra(pro)?\b|"
                 r"\bproshares\s+(ultra|short)|\binverse\b|\bbear\b(?!ish)|[23]00%|150%|"
                 r"daily\s.*\b(bull|bear|long|short)\b|\bultra\s?short\b(?!.*\b(income|bond|fixed|treasury|municipal|tips|tax-free|duration)\b)|"
                 r"\bshort\b(?!.{0,3}(term|duration|maturity|dated|treasury|bond|govt|government|corporate|municipal|muni|high yield|income|credit|tips|inflation)))")


def _get(urls: list[str]) -> str:
    err = None
    for u in urls:
        for att in range(3):
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (research script)"})
                return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
            except Exception as e:
                err = e
                time.sleep(5 * (att + 1))
    raise RuntimeError(f"받기 실패 {urls[0]}: {err!r}"[:300])


def _rows(txt: str) -> list[dict]:
    lines = [l for l in txt.splitlines() if l.strip()]
    hd = lines[0].split("|")
    return [dict(zip(hd, l.split("|"))) for l in lines[1:] if not l.startswith("File Creation Time")]


def yahoo(sym: str) -> str:
    return sym.strip().replace(".", "-").replace("/", "-")


def pick(nasdaq_txt: str, other_txt: str) -> dict:
    keep, etf, drop = {}, set(), {"test": 0, "shell": 0, "lev": 0, "dup": 0}
    for src, txt, sym_col in (("nasdaq", nasdaq_txt, "Symbol"), ("other", other_txt, "ACT Symbol")):
        for r in _rows(txt):
            s = (r.get(sym_col) or "").strip()
            name = (r.get("Security Name") or "").strip()
            if not s:
                continue
            if r.get("Test Issue", "N") == "Y":
                drop["test"] += 1
                continue
            is_etf = r.get("ETF", "N") == "Y"
            if "$" in s or (not is_etf and SHELL.search(name)):
                drop["shell"] += 1
                continue
            if is_etf and LEV.search(name):
                drop["lev"] += 1
                continue
            t = yahoo(s)
            if t in keep:
                drop["dup"] += 1
                continue
            keep[t] = re.sub(r"\s*-\s*(Common Stock|Class [A-Z] Common Stock|Ordinary Shares?).*$", "", name)[:80] or t
            if is_etf:
                etf.add(t)
    u = sorted(keep.items())
    return {"u": [[t, n] for t, n in u], "etf": sorted(etf), "n_stock": len(u) - len(etf), "n_etf": len(etf), "dropped": drop}


def build() -> dict:
    d = pick(_get(URLS["nasdaq"]), _get(URLS["other"]))
    d["asof"] = datetime.now(timezone.utc).strftime("%F")
    d["src"] = "nasdaqtrader SymDir (nasdaqlisted+otherlisted)"
    return d


def selftest():
    nas = ("Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
           "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
           "QQQ|Invesco QQQ Trust, Series 1|G|N|N|100|Y|N\n"
           "TQQQ|ProShares UltraPro QQQ|G|N|N|100|Y|N\n"
           "SQQQ|ProShares UltraPro Short QQQ|G|N|N|100|Y|N\n"
           "ABCDW|Abcd Corp - Warrant|S|N|N|100|N|N\n"
           "ZZZZT|Test Co|S|Y|N|100|N|N\n"
           "File Creation Time: 1015202600:00|||||||\n")
    oth = ("ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
           "BRK.B|Berkshire Hathaway Inc. Class B|N|BRK.B|N|100|N|BRK.B\n"
           "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY\n"
           "SHV|iShares Short Treasury Bond ETF|P|SHV|Y|100|N|SHV\n"
           "VGSH|Vanguard Short-Term Treasury ETF|P|VGSH|Y|100|N|VGSH\n"
           "SH|ProShares Short S&P500|P|SH|Y|100|N|SH\n"
           "TBT|ProShares UltraShort Lehman 20  Year Treasury|P|TBT|Y|100|N|TBT\n"
           "DLUX|DoubleLine Ultrashort Income ETF|P|DLUX|Y|100|N|DLUX\n"
           "TSL|GraniteShares 1.25x Long TSLA Daily ETF|P|TSL|Y|100|N|TSL\n"
           "HDLB|ETRACS Monthly Pay 2xLeveraged US High Dividend|P|HDLB|Y|100|N|HDLB\n"
           "REK|ProShares Short Real Estate|P|REK|Y|100|N|REK\n"
           "BOTZ|Global X Robotics & Artificial Intelligence ETF|P|BOTZ|Y|100|N|BOTZ\n"
           "UUP|Invesco DB USD Index Bullish Fund ETF|P|UUP|Y|100|N|UUP\n"
           "SOXL|Direxion Daily Semiconductor Bull 3X Shares|P|SOXL|Y|100|N|SOXL\n"
           "C$N|Citigroup Preferred|N|CprN|N|100|N|C-N\n"
           "EPD|Enterprise Products Partners L.P. Common Units|N|EPD|N|100|N|EPD\n"
           "USO|United States Oil Fund, LP Units|P|USO|Y|100|N|USO\n"
           "ABCU|Abc Acquisition Corp Unit|N|ABCU|N|100|N|ABCU\n")
    d = pick(nas, oth)
    got = {t for t, _ in d["u"]}
    want = {"AAPL", "QQQ", "BRK-B", "SPY", "SHV", "VGSH", "EPD", "USO", "DLUX", "BOTZ", "UUP"}
    assert got == want, (got, want)
    assert set(d["etf"]) == {"QQQ", "SPY", "SHV", "VGSH", "USO", "DLUX", "BOTZ", "UUP"}, d["etf"]
    assert d["dropped"]["lev"] == 8 and d["dropped"]["test"] == 1, d["dropped"]
    print("selftest ok", d["dropped"])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    d = build()
    n = len(d["u"])
    print(f"US 목록: 종목 {d['n_stock']} · ETF {d['n_etf']} · 합계 {n} · 뺌 {d['dropped']}")
    if n < MIN_OK:
        print(f"⚠️ {n}개뿐 — 받기가 깨진 듯해 기존 파일 유지")
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
