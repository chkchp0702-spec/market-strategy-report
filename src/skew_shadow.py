"""😨 옵션 「겁 기울기」 그림자 장부 (Q14-5 · 10/13 사용자 "Q14-5 실행해")

  무엇: 킥 후보(☕ 컵 · 📈 갭 · 🐋 고래 · 📊 실적 등) 미국 종목마다 옵션 값으로 「겁 기울기」를 잰다.
        겁 기울기 = 외가 풋(행사가/주가 0.80~0.95 중 0.95에 가장 가까운) 내재변동성 − 등가 콜(0.95~1.05 중 1.00에 가장 가까운) 내재변동성 (%p)
        만기는 10~60일 중 30일에 가장 가까운 것. (Xing·Zhang·Zhao, JFQA 2010 정의를 따름)
  근거: 겁 기울기 가장 가파른 1/5 종목이 가장 완만한 1/5보다 다음 해 약 10.9% 덜 벌었음 (JFQA 2010).
  왜 그림자: 과거 옵션 자료가 없어 오늘부터 쌓는다. 킥 매매는 바꾸지 않는다 — 기록·채점만.

  채점 (결과 보기 전에 정함 — brain/skew_lab.md 에도 같은 글):
  · 진입 = 잰 날(미국 장 날짜) 다음 거래일 종가 · 청산 = 그 뒤 20거래일 종가 · 비용 왕복 0.5% · 초과 = 같은 기간 SPY 대비
  · 「겁 큼」 = 그날까지 쌓인 전체 측정값의 상위 20% (80번째 백분위수 이상)
  · 판정: 채점 끝난 건 100건 이상 · 「겁 큼」 20건 이상일 때만.
      ✅ 거름망 효과 = 「겁 큼」 평균 초과가 나머지보다 1%p 이상 낮고, 손익비도 나머지보다 낮음 → 킥에서 빼는 것을 「제안」(자동 적용 안 함)
      ➖ 효과 없음 = 그 밖 · ⏳ 쌓는 중 = 표본 부족
  → market/skew_shadow.json   (워크플로 .github/workflows/skew-shadow.yml, KST 07:35 화~토)
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
CANDS = ROOT / "market" / "kick_cands.json"
KICK = ROOT / "market" / "kick.json"
OUT = ROOT / "market" / "skew_shadow.json"
LOOKBACK_D = 5          # 최근 며칠 신호까지 잴지 (못 잰 건 다음 날 다시 시도)
HOLD_D, COST, TOP = 20, 0.5, 0.80
JUDGE_N, JUDGE_TOP_N, JUDGE_GAP = 100, 20, 1.0
SRC_TAG = {"cup_eye": "☕", "cup": "☕", "gap": "📈", "accum": "🤫", "whale": "🐋", "focus": "🎯", "lead": "🔗", "earn": "📊",
           "nh52": "🏔", "pead": "📊", "dip": "🩹", "hold": "💼"}
NOT_STOCK = {"SPY", "QQQ", "UUP", "DBC", "EFA", "USO", "SGOV", "GLD", "TLT", "IEF", "BIL", "SHY", "IWM", "DIA"}


def _rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {} if d is None else d


def is_us_stock(code: str) -> bool:
    return bool(code) and code.replace("-", "").isalpha() and code.upper() == code and code not in NOT_STOCK


def pick(rows, spot, lo, hi, target, iv_key="impliedVolatility"):
    """rows: [{'strike','impliedVolatility','bid','openInterest'}] → 행사가/주가가 [lo,hi] 안이고 값이 살아 있는 것 중 target 에 가장 가까운 행"""
    best = None
    for r in rows:
        try:
            k, iv = float(r["strike"]), float(r.get(iv_key) or 0)
        except Exception:
            continue
        m = k / spot
        if not (lo <= m <= hi) or not (0.03 < iv < 5) or math.isnan(iv):
            continue
        if (r.get("bid") or 0) <= 0 and (r.get("openInterest") or 0) <= 0:
            continue
        if best is None or abs(m - target) < abs(best[0] - target):
            best = (m, iv, k)
    return best


def skew_from_chain(puts, calls, spot):
    p = pick(puts, spot, 0.80, 0.95, 0.95)
    c = pick(calls, spot, 0.95, 1.05, 1.00)
    if not p or not c:
        return None
    return {"skew": round((p[1] - c[1]) * 100, 2), "piv": round(p[1] * 100, 1), "civ": round(c[1] * 100, 1), "pk": p[2], "ck": c[2]}


def choose_expiry(exps, today):
    best = None
    for e in exps:
        try:
            days = (dt.date.fromisoformat(e) - today).days
        except Exception:
            continue
        if 10 <= days <= 60 and (best is None or abs(days - 30) < abs(best[1] - 30)):
            best = (e, days)
    return best


def measure(yf, code, today):
    t = yf.Ticker(code)
    h = t.history(period="7d", auto_adjust=False)
    if h is None or not len(h):
        raise RuntimeError("가격 없음")
    spot = float(h["Close"].iloc[-1])
    mdate = h.index[-1].strftime("%Y-%m-%d")
    ex = choose_expiry(list(t.options or []), today)
    if not ex:
        raise RuntimeError("10~60일 만기 없음")
    oc = t.option_chain(ex[0])
    r = skew_from_chain(oc.puts.to_dict("records"), oc.calls.to_dict("records"), spot)
    if not r:
        raise RuntimeError("쓸 만한 풋·콜 없음")
    return {**r, "spot": round(spot, 4), "m": mdate, "exp": ex[0], "dte": ex[1]}


def pct_rank_threshold(vals, q):
    v = sorted(vals)
    if not v:
        return None
    i = min(len(v) - 1, max(0, int(math.ceil(q * len(v))) - 1))
    return v[i]


def grp_stat(rs):
    if not rs:
        return {"n": 0}
    w = [x for x in rs if x > 0]
    l = [-x for x in rs if x <= 0]
    return {"n": len(rs), "avg": round(sum(rs) / len(rs), 2), "win": round(len(w) / len(rs) * 100),
            "pf": round(sum(w) / sum(l), 2) if l and sum(l) > 0 else None}


def judge(top, rest, n_done):
    if n_done < JUDGE_N or top["n"] < JUDGE_TOP_N:
        return "⏳ 쌓는 중", f"채점 끝난 {n_done}/{JUDGE_N}건 · 겁 큼 {top['n']}/{JUDGE_TOP_N}건"
    worse = top["avg"] <= rest["avg"] - JUDGE_GAP and (top.get("pf") or 0) < (rest.get("pf") or 99)
    if worse:
        return "✅ 거름망 효과", f"겁 큼 평균 초과 {top['avg']}% vs 나머지 {rest['avg']}% — 킥에서 빼는 것을 제안(자동 적용 안 함)"
    return "➖ 효과 없음", f"겁 큼 {top['avg']}% vs 나머지 {rest['avg']}% — 차이 {JUDGE_GAP}%p 미만 또는 손익비 역전 없음"


def grade(log, closes, spy):
    """closes: {code: [(date, close), ...]} 날짜순 · spy 같은 꼴 → 각 기록에 r(초과 %)·done 채움"""
    sd = [d for d, _ in spy]
    sp = dict(spy)
    for k, v in log.items():
        if v.get("done") or v.get("skew") is None:
            continue
        cs = closes.get(v["code"])
        if not cs:
            continue
        ds = [d for d, _ in cs]
        after = [i for i, d in enumerate(ds) if d > v["m"]]
        if not after:
            continue
        i0 = after[0]
        i1 = min(i0 + HOLD_D, len(ds) - 1)
        d0, d1 = ds[i0], ds[i1]
        if d0 not in sp or d1 not in sp:
            continue
        r = (cs[i1][1] / cs[i0][1] - 1) * 100 - COST
        rb = (sp[d1] / sp[d0] - 1) * 100
        v.update({"d0": d0, "d1": d1, "r": round(r - rb, 2), "days": i1 - i0, "done": (i1 - i0) >= HOLD_D})
    return log


def stats(log):
    vals = [v["skew"] for v in log.values() if v.get("skew") is not None]
    th = pct_rank_threshold(vals, TOP)
    if th is None:
        return {"th": None, "top": {"n": 0}, "rest": {"n": 0}, "n_meas": 0, "n_done": 0, "verdict": "⏳ 쌓는 중", "why": "측정 0건"}
    done = [v for v in log.values() if v.get("done") and v.get("r") is not None]
    top = grp_stat([v["r"] for v in done if v["skew"] >= th])
    rest = grp_stat([v["r"] for v in done if v["skew"] < th])
    live = [v for v in log.values() if not v.get("done") and v.get("r") is not None]
    vd, why = judge(top, rest, len(done))
    return {"th": round(th, 2), "top": top, "rest": rest, "n_meas": len(vals), "n_done": len(done),
            "live_top": grp_stat([v["r"] for v in live if v["skew"] >= th]), "live_rest": grp_stat([v["r"] for v in live if v["skew"] < th]),
            "verdict": vd, "why": why}


def main() -> int:
    import yfinance as yf
    now = dt.datetime.now(KST)
    today = now.date()
    prev = _rj(OUT)
    log = prev.get("log", {})
    errors = {}
    since = (today - dt.timedelta(days=LOOKBACK_D)).isoformat()
    C = _rj(CANDS).get("cands", {})
    todo = {}
    for v in C.values():
        if v.get("mkt") == "US" and v.get("d", "") >= since and is_us_stock(v.get("code", "")):
            key = f"{v['code']}|{v['d']}|{v['src']}"
            if key not in log:
                todo[key] = {"code": v["code"], "name": (v.get("name") or v["code"])[:40], "src": v["src"], "d": v["d"]}
    K = _rj(KICK)
    held = sorted({h["code"] for h in K.get("hold", []) if is_us_stock(h.get("code", ""))})
    cache, now_rows = {}, {}
    for code in sorted({x["code"] for x in todo.values()} | set(held)):
        try:
            cache[code] = measure(yf, code, today)
        except Exception as e:
            errors[code] = str(e)[:80]
        time.sleep(0.4)
    for key, x in todo.items():
        if x["code"] in cache:
            log[key] = {**x, **cache[x["code"]], "tag": SRC_TAG.get(x["src"], "")}
    # 채점용 종가
    codes = sorted({v["code"] for v in log.values() if not v.get("done")})
    closes, spy = {}, []
    if codes:
        m0 = min(v["m"] for v in log.values() if not v.get("done"))
        start = (dt.date.fromisoformat(m0) - dt.timedelta(days=5)).isoformat()
        df = yf.download(codes + ["SPY"], start=start, interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
        for c in codes + ["SPY"]:
            try:
                s = df[c]["Close"].dropna()
                closes[c] = [(i.strftime("%Y-%m-%d"), float(x)) for i, x in s.items()]
            except Exception:
                pass
        spy = closes.pop("SPY", [])
    if spy:
        grade(log, closes, spy)
    st = stats(log)
    th = st["th"]
    for code in held:
        if code in cache:
            r = cache[code]
            now_rows[code] = {**r, "fear": th is not None and r["skew"] >= th}
    newest = sorted([v for v in log.values() if v.get("m")], key=lambda v: (v["m"], v["skew"]), reverse=True)[:30]
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"),
        "rule": "겁 기울기 = 외가 풋(0.95) 내재변동성 − 등가 콜(1.00) 내재변동성 (%p, 만기 30일 근처) · 상위 20% = 😨 겁 큼 · 20거래일 SPY 대비 초과(비용 0.5% 뺌)로 채점 · 그림자만(킥 매매 안 바꿈)",
        "src": "Xing·Zhang·Zhao (JFQA 2010) — 기울기 가장 가파른 1/5이 가장 완만한 1/5보다 다음 해 약 10.9% 덜 벌었음",
        "stat": st,
        "hold_now": now_rows,
        "recent": [{"code": v["code"], "tag": v.get("tag", ""), "d": v["d"], "skew": v["skew"], "fear": th is not None and v["skew"] >= th,
                    "r": v.get("r"), "done": v.get("done", False)} for v in newest],
        "errors": errors,
        "log": log,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"측정 {len(cache)} · 새 기록 {sum(1 for k in todo if k in log)} · 실패 {len(errors)} · 판정 {st['verdict']} ({st['why']})")
    return 0


def selftest() -> int:
    spot = 100.0
    puts = [{"strike": 80, "impliedVolatility": 0.60, "bid": 0.1}, {"strike": 90, "impliedVolatility": 0.50, "bid": 0.5},
            {"strike": 95, "impliedVolatility": 0.45, "bid": 1.0}, {"strike": 100, "impliedVolatility": 0.40, "bid": 2.0}]
    calls = [{"strike": 95, "impliedVolatility": 0.38, "bid": 6}, {"strike": 100, "impliedVolatility": 0.35, "bid": 3},
             {"strike": 105, "impliedVolatility": 0.33, "bid": 1}]
    r = skew_from_chain(puts, calls, spot)
    assert r and r["pk"] == 95 and r["ck"] == 100 and abs(r["skew"] - 10.0) < 1e-9, r
    assert skew_from_chain([{"strike": 95, "impliedVolatility": 0.0, "bid": 1}], calls, spot) is None
    assert choose_expiry(["2026-10-16", "2026-11-13", "2026-12-18"], dt.date(2026, 10, 13))[0] == "2026-11-13"
    assert choose_expiry(["2026-10-16"], dt.date(2026, 10, 13)) is None
    days = [f"2026-10-{i:02d}" for i in range(1, 31)]
    spy = [(d, 100.0) for d in days]
    closes = {"AAA": [(d, 100.0 + i) for i, d in enumerate(days)]}
    log = {"AAA|x|cup": {"code": "AAA", "m": "2026-10-02", "skew": 5.0}}
    grade(log, closes, spy)
    v = log["AAA|x|cup"]
    assert v["d0"] == "2026-10-03" and v["days"] == 20 and v["done"] and abs(v["r"] - ((122 / 102 - 1) * 100 - 0.5)) < 0.01, v
    assert pct_rank_threshold(list(range(1, 11)), 0.8) == 8
    t, rs = grp_stat([-2] * 25), grp_stat([1, 2, -1] * 40)
    assert judge(t, rs, 140)[0].startswith("✅") and judge(t, rs, 50)[0].startswith("⏳")
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "selftest" in sys.argv else main())
