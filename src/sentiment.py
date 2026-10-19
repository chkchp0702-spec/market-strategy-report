"""🫀 심리 계기판 — 공포·탐욕이 가격보다 먼저 움직이는 자리를 숫자로 본다 (10/19 사용자: "심리지표·선물 영향·외가격/내가격 옵션·풋콜·신용 물량에서 심리 흐름을 봐")

출력: market/sentiment.json  (두뇌가 매시간 읽음 · 앱 📰 피드 「🫀 심리」)
      market/sentiment_log.json (날짜별 스냅샷 — 그림자 채점용, 180일)

원천 (GitHub Actions 에서만 받아짐 — 두뇌 세션은 시세 사이트가 막혀 있음):
  🇺🇸 yfinance  ^VIX ^VIX3M ^VIX9D ^SKEW (1년 일봉) · SPY 옵션 체인(10~60일 만기 중 30일 근처) — 풋/콜 거래량·미결제, 외가 풋(0.95·0.90) vs 등가 콜 내재변동성
  🇰🇷 네이버 금융  투자자별 매매동향(선물 sosok=03 · 콜 04 · 풋 05 · 코스피 01) · 고객예탁금·신용잔고(sise_deposit)
원칙: 못 받은 값은 null. 숫자를 만들지 않는다. 규칙은 결과 보기 전에 적었다(brain/sentiment_lab.md) — 채점은 그림자만, 킥 매매를 바꾸지 않는다.

사전 등록 규칙 (R1~R5, 상세는 brain/sentiment_lab.md):
  R1 😨 미 공포 극단 : VIX 1년 백분위 ≥ 90 이고 VIX > VIX3M(역전)      → 「크기 줄이기」 국면. 방향 신호 아님(FlashAlpha 2018~26: 중앙값 같고 분산만 60% 넓음)
  R1x 😮‍💨 공포 해소  : 어제 역전(VIX>VIX3M)이었다가 오늘 정상(VIX<VIX3M) 첫날 → 20일 SPY 채점(가설: 평균 +)
  R2 🔁 풋콜 리셋   : SPY 풋/콜 거래량 10일 평균의 84일 순위가 ≥99% 를 찍은 뒤 <56% 로 내려오고 SPY 5일 수익률 > 0 → 3개월 SPY 채점(SentimenTrader: 51회 중 80% 승)
  R3 🧾 한국 신용 청산: 신용융자 잔고가 60일 최고 대비 −10% 넘게 줄고 5일 변화 ≥ 0 (줄어들기를 멈춤) 첫날 → 20일 코스피 채점(가설: 7~8월처럼 잔고 −25% 뒤 바닥)
  R4 🔄 선물 매도 정리: 외국인 선물 5일 누적이 −10,000계약 이하였다가 +로 바뀐 첫날 → 5·20일 코스피 채점(앨버트로스 10/19: "기존 매도자 정리만으로 반등 시작")
  R5 🎈 외가 풋 비쌈  : SPY 0.90 풋 IV − 등가 콜 IV 가 스스로 쌓은 기록의 상위 20% → 「보험 수요 극단」 20일 SPY 채점(Xing·Zhang·Zhao 2010 는 종목 단위 음(−), 지수 단위는 반대일 수 있어 가설만)
"""
from __future__ import annotations
import datetime as dt, json, math, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MK = ROOT / "market"
OUT, LOG = MK / "sentiment.json", MK / "sentiment_log.json"
KST = dt.timezone(dt.timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "*/*"}
ERR: dict[str, str] = {}
KEEP_D = 180
sys.path.insert(0, str(ROOT))
from src.skew_shadow import implied_vol, opt_price, _num, choose_expiry, pick  # noqa: E402


def _rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {} if d is None else d


def _get(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def pct_rank(vals, x):
    v = [a for a in vals if a is not None]
    if not v or x is None:
        return None
    return round(100 * sum(1 for a in v if a <= x) / len(v))


# ───────────── 🇺🇸 미국 ─────────────
def us_vol(yf):
    out = {}
    hist = {}
    for sym, key in (("^VIX", "vix"), ("^VIX3M", "vix3m"), ("^VIX9D", "vix9d"), ("^SKEW", "skew_idx")):
        try:
            h = yf.Ticker(sym).history(period="1y", auto_adjust=False)
            c = [float(x) for x in h["Close"].tolist() if not math.isnan(float(x))]
            if not c:
                raise RuntimeError("빈 값")
            hist[key] = c
            out[key] = round(c[-1], 2)
            out[key + "_p1y"] = pct_rank(c, c[-1])
            out[key + "_d"] = h.index[-1].strftime("%Y-%m-%d")
        except Exception as e:
            ERR[sym] = str(e)[:160]
            out[key] = None
    if out.get("vix") and out.get("vix3m"):
        out["vix_vix3m"] = round(out["vix"] / out["vix3m"], 3)
        out["backwardation"] = out["vix"] > out["vix3m"]
        # 어제 역전이었나 (R1x 판정용)
        v, v3 = hist.get("vix", []), hist.get("vix3m", [])
        out["backwardation_prev"] = (len(v) > 1 and len(v3) > 1 and v[-2] > v3[-2])
    if out.get("vix") and out.get("vix9d"):
        out["vix9d_vix"] = round(out["vix9d"] / out["vix"], 3)
    return out


def us_options(yf, code="SPY"):
    """SPY 체인: 풋/콜 거래량·미결제 비율 + 외가 풋 IV − 등가 콜 IV (0.95·0.90)"""
    t = yf.Ticker(code)
    h = t.history(period="7d", auto_adjust=False)
    spot = float(h["Close"].iloc[-1])
    mdate = h.index[-1].strftime("%Y-%m-%d")
    today = dt.datetime.now(KST).date()
    ex = choose_expiry(list(t.options or []), today)
    if not ex:
        raise RuntimeError("10~60일 만기 없음")
    oc = t.option_chain(ex[0])
    P, C = oc.puts.to_dict("records"), oc.calls.to_dict("records")
    pv, cv = sum(_num(r.get("volume")) for r in P), sum(_num(r.get("volume")) for r in C)
    po, co = sum(_num(r.get("openInterest")) for r in P), sum(_num(r.get("openInterest")) for r in C)
    T = max(ex[1], 1) / 365
    stale = (dt.date.fromisoformat(mdate) - dt.timedelta(days=3)).isoformat()
    atm_c = pick("c", C, spot, 0.98, 1.02, 1.00, T, stale)
    p95 = pick("p", P, spot, 0.93, 0.97, 0.95, T, stale)
    p90 = pick("p", P, spot, 0.88, 0.92, 0.90, T, stale)
    r = {"spot": round(spot, 2), "m": mdate, "exp": ex[0], "dte": ex[1],
         "pc_vol": round(pv / cv, 3) if cv > 0 else None, "pc_oi": round(po / co, 3) if co > 0 else None,
         "atm_civ": round(atm_c[1] * 100, 1) if atm_c else None,
         "p95_iv": round(p95[1] * 100, 1) if p95 else None, "p90_iv": round(p90[1] * 100, 1) if p90 else None}
    if atm_c and p95:
        r["skew95"] = round((p95[1] - atm_c[1]) * 100, 2)
    if atm_c and p90:
        r["skew90"] = round((p90[1] - atm_c[1]) * 100, 2)
    return r


def spy_roc(yf, n=5):
    h = yf.Ticker("SPY").history(period="1mo", auto_adjust=False)
    c = h["Close"].tolist()
    return round((c[-1] / c[-1 - n] - 1) * 100, 2) if len(c) > n else None


# ───────────── 🇰🇷 한국 ─────────────
_NUM = re.compile(r"-?[\d,]+")


def naver_investor(sosok="03"):
    """finance.naver.com 투자자별 매매동향 일별 (sosok 01 코스피 · 03 선물 · 04 콜 · 05 풋). 첫 5행 → [{d, indiv, foreign, inst}] (선물·옵션은 계약 수)"""
    url = f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={dt.datetime.now(KST):%Y%m%d}&sosok={sosok}"
    html = _get(url, headers={"Referer": "https://finance.naver.com/"}).decode("euc-kr", "ignore")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) >= 4 and re.match(r"\d{2}\.\d{2}\.\d{2}", tds[0]):
            try:
                nums = [int(x.replace(",", "")) for x in tds[1:4]]
            except ValueError:
                continue
            rows.append({"d": "20" + tds[0].replace(".", "-"), "indiv": nums[0], "foreign": nums[1], "inst": nums[2]})
        if len(rows) >= 10:
            break
    if not rows:
        raise RuntimeError("행 없음")
    return rows


def naver_deposit():
    """고객예탁금·신용잔고 (finance.naver.com/sise/sise_deposit.naver) 최근 행들 → [{d, deposit, credit}] 단위 억원"""
    html = _get("https://finance.naver.com/sise/sise_deposit.naver", headers={"Referer": "https://finance.naver.com/"}).decode("euc-kr", "ignore")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) >= 5 and re.match(r"\d{2}\.\d{2}\.\d{2}", tds[0]):
            try:
                dep = int(tds[1].replace(",", "")); cr = int(tds[3].replace(",", ""))
            except ValueError:
                continue
            rows.append({"d": "20" + tds[0].replace(".", "-"), "deposit": dep, "credit": cr})
    if not rows:
        raise RuntimeError("행 없음")
    return rows


# ───────────── 규칙 판정 ─────────────
def judge(us, opt, kr, log, spy5):
    sig = []
    # R1 / R1x
    if us.get("vix_p1y") is not None and us.get("backwardation") is not None:
        on = us["vix_p1y"] >= 90 and us["backwardation"]
        sig.append({"id": "R1", "name": "😨 미 공포 극단", "on": on,
                    "level": f"VIX {us['vix']} (1년 {us['vix_p1y']}%) · VIX/VIX3M {us.get('vix_vix3m')}",
                    "then": "크기 줄이기 — 새 bets horizon 짧게·목표 좁게. 방향 신호 아님"})
        relief = us.get("backwardation_prev") and not us["backwardation"]
        sig.append({"id": "R1x", "name": "😮‍💨 공포 해소 첫날", "on": bool(relief),
                    "level": "어제 VIX>VIX3M → 오늘 정상" if relief else "역전 중" if us["backwardation"] else "정상(콘탱고)",
                    "then": "20일 SPY 채점 — 가설: 평균 +"})
    # R2 풋콜 리셋 — 자기 기록으로 10일 평균·84일 순위
    pcs = [(d, v.get("pc_vol")) for d, v in sorted(log.items()) if v.get("pc_vol")]
    if opt.get("pc_vol") is not None:
        vals = [x for _, x in pcs][-84:]
        ma10 = [sum(vals[i - 9:i + 1]) / 10 for i in range(9, len(vals))]
        rank = pct_rank(ma10, ma10[-1]) if ma10 else None
        peak_recent = max(ma10[-20:]) if len(ma10) >= 20 else None
        peak_rank = pct_rank(ma10, peak_recent) if peak_recent is not None else None
        on = bool(rank is not None and peak_rank is not None and peak_rank >= 99 and rank < 56 and (spy5 or 0) > 0 and len(vals) >= 84)
        sig.append({"id": "R2", "name": "🔁 풋콜 리셋", "on": on,
                    "level": f"SPY 풋/콜 거래량 {opt['pc_vol']} · 10일평균 84일 순위 {rank}% (기록 {len(vals)}/84일)" + ("" if len(vals) >= 84 else " — 쌓는 중"),
                    "then": "3개월 SPY 채점 (SentimenTrader 51회 80% 승)"})
    # R3 한국 신용 청산
    cr = kr.get("credit_hist") or []
    if cr:
        c = [x["credit"] for x in cr]  # 최신이 앞
        hi60 = max(c[:60]); now = c[0]
        d5 = (now / c[5] - 1) * 100 if len(c) > 5 else None
        off = (now / hi60 - 1) * 100
        on = bool(off <= -10 and d5 is not None and d5 >= 0 and len(c) > 5)
        sig.append({"id": "R3", "name": "🧾 한국 신용 청산 멈춤", "on": on,
                    "level": f"신용잔고 {now/10000:.1f}조 · 60일 최고 대비 {off:+.1f}% · 5일 {d5:+.1f}%" if d5 is not None else f"신용잔고 {now/10000:.1f}조 (기록 {len(c)}일)",
                    "then": "20일 코스피 채점 — 가설: 잔고 −10%↑ 줄고 멈춘 뒤 바닥 (7~8월: 38.6→27.4조 뒤 반등)"})
    # R4 외국인 선물 매도 정리
    fut = kr.get("fut") or []
    if len(fut) >= 6:
        s5 = sum(r["foreign"] for r in fut[:5]); s5_prev = sum(r["foreign"] for r in fut[1:6])
        on = bool(s5_prev <= -10000 and s5 > 0)
        sig.append({"id": "R4", "name": "🔄 외국인 선물 매도 정리", "on": on,
                    "level": f"외국인 선물 5일 누적 {s5:+,}계약 (어제까지 {s5_prev:+,}) · 오늘 {fut[0]['foreign']:+,}",
                    "then": "5·20일 코스피 채점 — 앨버트로스: 기존 매도자 정리만으로 반등 시작"})
    # R5 외가 풋 비쌈
    sk = [v.get("skew90") for v in log.values() if v.get("skew90") is not None]
    if opt.get("skew90") is not None:
        rank = pct_rank(sk, opt["skew90"]) if len(sk) >= 20 else None
        on = bool(rank is not None and rank >= 80)
        sig.append({"id": "R5", "name": "🎈 외가 풋 비쌈(보험 수요)", "on": on,
                    "level": f"SPY 0.90풋 IV−등가 콜 IV {opt['skew90']:+.1f}%p · 0.95풋 {opt.get('skew95')}" + (f" · 기록 순위 {rank}%" if rank is not None else f" (기록 {len(sk)}/20일 — 쌓는 중)"),
                    "then": "20일 SPY 채점 — 가설만(종목은 −, 지수는 반대일 수 있음)"})
    return sig


# ───────────── 그림자 채점 ─────────────
def score(yf, log):
    """log 의 각 날짜에 켜졌던 신호(on) → 그날 종가 뒤 5·20거래일 SPY/코스피 수익률. 판정은 n≥20 부터"""
    px = {}
    for sym, k in (("SPY", "SPY"), ("^KS11", "KOSPI")):
        try:
            h = yf.Ticker(sym).history(period="1y", auto_adjust=False)
            px[k] = [(i.strftime("%Y-%m-%d"), float(c)) for i, c in zip(h.index, h["Close"].tolist())]
        except Exception as e:
            ERR["score " + sym] = str(e)[:120]
    idx_for = {"R1": "SPY", "R1x": "SPY", "R2": "SPY", "R5": "SPY", "R3": "KOSPI", "R4": "KOSPI"}
    res = {}
    for d, v in log.items():
        for s in v.get("on", []):
            k = idx_for.get(s, "SPY")
            ser = px.get(k) or []
            i = next((n for n, (dd, _) in enumerate(ser) if dd >= d), None)
            if i is None:
                continue
            e = res.setdefault(s, {"n": 0, "r5": [], "r20": []})
            e["n"] += 1
            if i + 5 < len(ser):
                e["r5"].append(round((ser[i + 5][1] / ser[i][1] - 1) * 100, 2))
            if i + 20 < len(ser):
                e["r20"].append(round((ser[i + 20][1] / ser[i][1] - 1) * 100, 2))
    out = {}
    for s, e in res.items():
        def st(rs):
            if not rs:
                return {"n": 0}
            return {"n": len(rs), "avg": round(sum(rs) / len(rs), 2), "win": round(100 * sum(1 for x in rs if x > 0) / len(rs))}
        out[s] = {"days_on": e["n"], "r5": st(e["r5"]), "r20": st(e["r20"]),
                  "verdict": "⏳ 쌓는 중" if len(e["r20"]) < 20 else ("✅ 쓸 만함" if st(e["r20"])["avg"] > 0 and st(e["r20"])["win"] >= 55 else "❌ 효과 없음")}
    return out


def main():
    import yfinance as yf
    now = dt.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    log = _rj(LOG, {})
    us, opt, kr = {}, {}, {}
    try:
        us = us_vol(yf)
    except Exception as e:
        ERR["us_vol"] = str(e)[:160]
    try:
        opt = us_options(yf)
    except Exception as e:
        ERR["spy_options"] = str(e)[:160]
    try:
        spy5 = spy_roc(yf)
    except Exception as e:
        ERR["spy5"] = str(e)[:120]; spy5 = None
    for key, sosok in (("fut", "03"), ("call", "04"), ("put", "05"), ("kospi", "01")):
        try:
            kr[key] = naver_investor(sosok)
        except Exception as e:
            ERR["naver " + key] = str(e)[:160]
    try:
        dep = naver_deposit()
        # 자기 기록과 합쳐 60일 이상 유지 (네이버 페이지는 최근 몇 행만)
        hist = {r["d"]: r for r in (_rj(MK / "sentiment_log.json", {}).get("_credit") or [])}
        for r in dep:
            hist[r["d"]] = r
        kr["credit_hist"] = sorted(hist.values(), key=lambda r: r["d"], reverse=True)[:120]
    except Exception as e:
        ERR["naver deposit"] = str(e)[:160]
        kr["credit_hist"] = (log.get("_credit") or [])
    sig = judge(us, opt, kr, {k: v for k, v in log.items() if not k.startswith("_")}, spy5)
    on_ids = [s["id"] for s in sig if s["on"]]
    # 날짜별 스냅샷 (하루에 여러 번 돌면 덮어씀 — 미국 옵션은 미국 장중 값이 가장 정확)
    snap = {"pc_vol": opt.get("pc_vol"), "pc_oi": opt.get("pc_oi"), "skew90": opt.get("skew90"), "skew95": opt.get("skew95"),
            "vix": us.get("vix"), "vix_vix3m": us.get("vix_vix3m"), "on": on_ids, "at": now.strftime("%H:%M")}
    prev = log.get(today, {})
    # 옵션 값은 미국 장중·마감 직후(KST 22~09시)에 받은 것을 우선 — 장 밖 값은 비어 있을 때만
    us_open = now.hour >= 22 or now.hour < 9   # 미국 장중~마감 직후(KST 22~09시) 값이 가장 정확
    if prev and not us_open and prev.get("pc_vol") is not None:
        for k in ("pc_vol", "pc_oi", "skew90", "skew95"):
            snap[k] = prev.get(k)
    snap["on"] = sorted(set(on_ids) | set(prev.get("on", [])))
    log[today] = snap
    log["_credit"] = kr.get("credit_hist") or []
    cutoff = (now - dt.timedelta(days=KEEP_D)).strftime("%Y-%m-%d")
    log = {k: v for k, v in log.items() if k.startswith("_") or k >= cutoff}
    sc = score(yf, {k: v for k, v in log.items() if not k.startswith("_")})
    # 한 줄 요약 (두뇌·앱용)
    parts = []
    if us.get("vix"):
        parts.append(f"VIX {us['vix']}({us.get('vix_p1y')}%)" + (" 역전" if us.get("backwardation") else ""))
    if opt.get("pc_vol") is not None:
        parts.append(f"SPY 풋/콜 {opt['pc_vol']}")
    if opt.get("skew90") is not None:
        parts.append(f"외가풋 프리미엄 {opt['skew90']:+.1f}%p")
    if kr.get("credit_hist"):
        parts.append(f"신용 {kr['credit_hist'][0]['credit']/10000:.1f}조")
    if kr.get("fut"):
        parts.append(f"외인 선물 {sum(r['foreign'] for r in kr['fut'][:5]):+,}계약(5일)")
    out = {"at": now.strftime("%Y-%m-%d %H:%M"), "line": " · ".join(parts) or "값 없음",
           "on": on_ids, "signals": sig, "us": us, "spy_opt": opt, "spy_roc5": spy5,
           "kr": {"fut": (kr.get("fut") or [])[:5], "call": (kr.get("call") or [])[:3], "put": (kr.get("put") or [])[:3],
                  "kospi": (kr.get("kospi") or [])[:5], "credit": (kr.get("credit_hist") or [])[:5]},
           "score": sc, "errors": ERR,
           "rule": "규칙 R1~R5 는 brain/sentiment_lab.md 에 결과 보기 전에 적음 · 그림자 채점만(킥 매매 안 바꿈) · 판정은 20일 채점 n≥20 부터"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.write_text(json.dumps(log, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(out["line"], "| on:", on_ids, "| errors:", ERR)


def selftest():
    log = {"2026-09-%02d" % i: {"pc_vol": 1.0 + (i % 3) * 0.1, "skew90": 5 + i % 4} for i in range(1, 30)}
    us = {"vix": 30, "vix_p1y": 95, "vix3m": 28, "backwardation": True, "backwardation_prev": False, "vix_vix3m": 1.07}
    kr = {"credit_hist": [{"d": "x", "credit": 300000}] * 6 + [{"d": "z", "credit": 350000}] * 10,
          "fut": [{"foreign": 25000}] + [{"foreign": -4000}] * 5}
    s = {x["id"]: x for x in judge(us, {"pc_vol": 1.2, "skew90": 6.0, "skew95": 3.0}, kr, log, 1.0)}
    assert s["R1"]["on"] and not s["R1x"]["on"], s
    assert s["R3"]["on"], s["R3"]          # 350000→300000 = −14%, 5일 변화 0 = 줄어들기 멈춤
    assert s["R4"]["on"], s["R4"]
    assert "R5" in s and not s["R2"]["on"]
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        main()
