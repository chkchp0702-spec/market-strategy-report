"""📈 Q15-2 🕴 「회사 안 사람들이 한꺼번에 살 때」 덜어낸 몫 돌려놓기 — 과거 검증 (사용자 10/14 15시 보고에 답: "2,5번 실행")
결과 → market/lab/k1014_q15i.json (+ 하루 표 market/lab/k1014_q15i_daily.csv.gz)

근거: Seyhun(1988) · Lakonishok·Lee(2001, RFS) — 시장 전체 내부자 순매수가 많을 때 이후 시장 수익률이 높음.
자료: openinsider.com 스크리너(SEC Form 4 장내 매수 P, 2004~) — SEC 원본은 깃허브 실행기 IP 에서 403 (Q16-5 와 같은 길).
  ※ 매도까지 받으면 요청 수가 10배 넘어 시간 안에 못 받음 → 「매수 폭」만 씀: 매수 쪽이 정보가 많다는 게 Lakonishok·Lee 결과.
신호(결과 보기 전 정함):
  B(t) = 공시일 기준 지난 20거래일 동안 장내 매수(P) 공시가 있었던 서로 다른 회사 수(미국 전체 — S&P 밖 포함).
  pct(t) = B(t) 가 지난 3년(756거래일) 중 몇 % 자리인가 (보고서 원안은 5년 — 자료가 2004~ 라 2008 을 앞 기간에 넣으려고 3년).
  pct ≥ thr 인 날(장 마감 뒤 확인) → 다음 거래일부터 H 거래일 동안 주식 칸을 변동성 맞춤이 덜어낸 만큼 되돌림(배율 1 = 목표 비중, 레버리지 없음).
모의 💼 (지금 vol_rule 그대로): 주식 칸 = S&P½ + 나스닥½(SPY·QQQ) · 배율 = min(1, 15% ÷ 20일 변동성), 아래 한도 30%, 5%p 넘게 바뀔 때만
  · 덜어낸 몫 = 3개월 국채(^IRX) · 비중 바뀔 때 바뀐 양 × 0.1% 비용 · 신호·배율은 그날 종가로 정하고 다음 날 수익부터 적용.
손잡이: thr(80·90·95) × H(20·40·60). 원안 = thr90·H40. 앞 2008~2016 에서 고름(연수익이 기준 −0.5%p 안 · 샤프 최대) · 2017~ 시험.
판정(결과 보기 전):
  ✅ = 시험 기간 샤프 ≥ 기준 · 연수익 ≥ 기준 +0.3%p · 최대낙폭이 기준보다 2%p 넘게 깊지 않음 · 앞 기간도 연수익 ≥ 기준 · 변형 9개 중 시험 기간 연수익 ≥ 기준 ≥ 6
  🧪 = 시험 기간 연수익·샤프 둘 다 기준보다 나으나 위 일부 못 미침 · ❌ = 둘 다 나쁨 · ➖ = 그 밖(차이 거의 없음·엇갈림)
덧: 신호 날 다음 20·60·120거래일 S&P 수익(같은 신호 20일 안 재신호 무시) vs 모든 날 평균 — 「바닥 근처」가 맞는지.
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import k1013_insider as KN      # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q15i.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
FROM = dt.date(2004, 1, 1)
BUDGET = 28 * 60
TARGET, FLOOR, BAND, LB, COST = 0.15, 0.30, 0.05, 20, 0.001
GRID = [(t, h) for t in (80, 90, 95) for h in (20, 40, 60)]


def fetch(log, t0):
    """k1013_insider.fetch_sec 와 같은 방식 · 시작 달만 2004-01"""
    import requests
    parts, got = [], []
    now = dt.date.today()
    m = FROM
    while m <= now:
        nm = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        a, b = m.strftime("%m/%d/%Y").replace("/", "%2F"), (nm - dt.timedelta(days=1)).strftime("%m/%d/%Y").replace("/", "%2F")
        for pg in range(1, 40):
            if time.time() - t0 > BUDGET:
                log["cut"] = str(m)
                break
            html = None
            for att in range(3):
                try:
                    r = requests.get(KN.OI.format(a=a, b=b, pg=pg), headers=KN.OUA, timeout=60)
                    r.raise_for_status()
                    html = r.text
                    break
                except Exception as e:
                    log.setdefault("err", []).append(f"{m}p{pg}:{repr(e)[:80]}")
                    time.sleep(5 * (att + 1))
            if html is None:
                break
            try:
                d = KN.oi_table(html)
            except Exception as e:
                log.setdefault("err", []).append(f"{m}p{pg} parse:{repr(e)[:100]}")
                d = pd.DataFrame()
            if len(d):
                parts.append(d[["fd", "td", "tk", "name", "val"]])
            time.sleep(0.6)
            if len(d) < 1000:
                break
        if log.get("cut"):
            break
        got.append(str(m)[:7])
        m = nm
    d = pd.concat(parts, ignore_index=True).drop_duplicates() if parts else pd.DataFrame()
    log["months"] = got[:1] + got[-1:] + [len(got)]
    log["rows"] = int(len(d))
    if "err" in log:
        log["err_n"], log["err"] = len(log["err"]), log["err"][-5:]
    return d


def ydl(syms):
    import yfinance as yf
    for att in range(3):
        try:
            d = yf.download(syms, start="2003-01-01", auto_adjust=True, progress=False)["Close"]
            return d
        except Exception:
            time.sleep(10)
    raise RuntimeError("yahoo")


def breadth(ins, days):
    d = ins.dropna(subset=["fd", "tk"])
    d = d[(d["tk"] != "") & (d["tk"] != "NAN")]
    pos = days.searchsorted(pd.to_datetime(d["fd"]).dt.normalize(), side="left")   # 공시일(주말이면 다음 거래일)
    d = d.assign(p=pos)
    d = d[d["p"] < len(days)]
    out = np.zeros(len(days))
    first = d.groupby("tk")["p"].apply(lambda s: np.unique(s.to_numpy()))
    cnt = np.zeros(len(days) + LB + 1)
    for arr in first:                      # 회사마다: 그날~20거래일 동안 「있음」 1 (겹치면 한 번만)
        cover = np.zeros(len(days) + LB + 1, dtype=bool)
        for p in arr:
            cover[p:p + LB] = True
        cnt += cover
    out = cnt[:len(days)]
    return pd.Series(out, index=days)


def pct_rank(s, win=756):
    v = s.to_numpy()
    out = np.full(len(v), np.nan)
    for i in range(win, len(v)):
        w = v[i - win:i + 1]
        out[i] = (w < v[i]).mean() * 100 + (w == v[i]).mean() * 50
    return pd.Series(out, index=s.index)


def sim(E, cash, trig=None, H=0):
    """trig: 그날 종가에 신호(bool 배열) → 다음 날부터 H 일 배율 1"""
    vol = E.rolling(LB).std().to_numpy() * np.sqrt(252)
    e, cs = E.to_numpy(), cash.to_numpy()
    n = len(e)
    w, until = 1.0, -1
    r = np.zeros(n)
    over_days, fired = 0, 0
    for i in range(n - 1):
        raw = 1.0 if np.isnan(vol[i]) or vol[i] <= 0 else max(FLOOR, min(1.0, TARGET / vol[i]))
        if trig is not None and trig[i]:
            if until < i:
                fired += 1
            until = max(until, i + H)
        if i < until or (trig is not None and trig[i]):
            new = 1.0
            if raw < 1.0 - 1e-9:
                over_days += 1
        else:
            new = raw if abs(raw - w) > BAND else w
        cost = abs(new - w) * COST
        w = new
        r[i + 1] = w * e[i + 1] + (1 - w) * cs[i + 1] - cost
    return pd.Series(r, index=E.index), over_days, fired


def pstat(r):
    r = r.dropna()
    if len(r) < 20:
        return {}
    nav = (1 + r).cumprod()
    cagr = nav.iloc[-1] ** (252 / len(r)) - 1
    dd = (nav / nav.cummax() - 1).min()
    return {"cagr": round(cagr * 100, 2), "vol": round(r.std() * np.sqrt(252) * 100, 2),
            "sharpe": round(float(r.mean() / r.std() * np.sqrt(252)), 3), "mdd": round(dd * 100, 2),
            "yr": {int(k): round(float((1 + v).prod() - 1) * 100, 2) for k, v in r.groupby(r.index.year)}}


def per(r):
    return {"IS": pstat(r[(r.index >= IS_START) & (r.index <= IS_END)]), "OOS": pstat(r[r.index >= OOS_START])}


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    px = ydl(["SPY", "QQQ", "^IRX"]).dropna(subset=["SPY", "QQQ"])
    days = px.index
    E = 0.5 * px["SPY"].pct_change() + 0.5 * px["QQQ"].pct_change()
    cash = (px["^IRX"].ffill() / 100 / 252).reindex(days).fillna(0)
    log = {}
    ins = fetch(log, t0)
    res["log"]["ins"] = log
    print("ins", json.dumps(log, ensure_ascii=False), round(time.time() - t0), flush=True)
    B = breadth(ins, days)
    first = pd.to_datetime(ins["fd"]).min()
    B[B.index < first + pd.Timedelta(days=40)] = np.nan
    P = pct_rank(B)
    D = pd.DataFrame({"B": B, "pct": P.round(1), "spy": px["SPY"]})
    D.to_csv(ROOT / "market" / "lab" / "k1014_q15i_daily.csv.gz", compression="gzip")
    res["now"] = {"date": str(days[-1].date()), "B": float(B.iloc[-1]), "pct": None if np.isnan(P.iloc[-1]) else round(float(P.iloc[-1]), 1)}

    # 덧: 신호 뒤 S&P
    spy = px["SPY"].to_numpy()
    ev = {}
    for thr in (80, 90, 95):
        on = (P >= thr).to_numpy()
        idx, last = [], -99
        for i in np.where(on)[0]:
            if i - last > 20:
                idx.append(i)
            last = i
        o = {}
        for pn, lo, hi in (("IS", IS_START, IS_END), ("OOS", OOS_START, "2100")):
            sel = [i for i in idx if lo <= str(days[i].date()) <= hi]
            alld = [i for i in range(len(days)) if lo <= str(days[i].date()) <= hi and not np.isnan(P.iloc[i])]
            o[pn] = {"n": len(sel), "dates": [str(days[i].date()) for i in sel][:40]}
            for k in (20, 60, 120):
                f = lambda ii: [spy[i + k] / spy[i] - 1 for i in ii if i + k < len(spy)]
                a, b = f(sel), f(alld)
                o[pn][f"f{k}"] = round(float(np.mean(a)) * 100, 2) if a else None
                o[pn][f"all{k}"] = round(float(np.mean(b)) * 100, 2) if b else None
                o[pn][f"win{k}"] = round(float(np.mean([x > 0 for x in a])) * 100) if a else None
        ev[thr] = o
    res["event"] = ev
    print("event", json.dumps(ev, ensure_ascii=False)[:1500], flush=True)

    base, _, _ = sim(E, cash)
    S = {"base": per(base)}
    meta = {}
    for thr, H in GRID:
        trig = (P >= thr).to_numpy()
        r, od, fi = sim(E, cash, trig, H)
        k = f"t{thr}h{H}"
        S[k] = per(r)
        meta[k] = {"over_days": od, "fired": fi}
    res["runs"], res["meta"] = S, meta
    b = S["base"]
    cand = [k for k in S if k != "base" and S[k]["IS"].get("cagr") is not None and S[k]["IS"]["cagr"] >= b["IS"]["cagr"] - 0.5]
    rob = sum(1 for k in S if k != "base" and S[k]["OOS"]["cagr"] >= b["OOS"]["cagr"])
    res["robust"] = f"{rob}/{len(GRID)}"

    def judge(k):
        o, bo, i, bi = S[k]["OOS"], b["OOS"], S[k]["IS"], b["IS"]
        s = (f"{k} · 시험 기간 연수익 {o['cagr']}% vs 기준 {bo['cagr']}% · 샤프 {o['sharpe']} vs {bo['sharpe']} · 최대낙폭 {o['mdd']}% vs {bo['mdd']}% "
             f"· 앞 기간 연수익 {i['cagr']}% vs {bi['cagr']}% · 작동 {meta[k]['fired']}번 · 기준보다 나은 변형 {res['robust']}")
        if o["sharpe"] >= bo["sharpe"] and o["cagr"] >= bo["cagr"] + 0.3 and o["mdd"] >= bo["mdd"] - 2 and i["cagr"] >= bi["cagr"] and rob >= 6:
            return "✅", s
        if abs(o["cagr"] - bo["cagr"]) < 0.1 and abs(o["sharpe"] - bo["sharpe"]) < 0.01:
            return "➖", s
        if o["cagr"] > bo["cagr"] and o["sharpe"] > bo["sharpe"]:
            return "🧪", s
        if o["cagr"] < bo["cagr"] and o["sharpe"] < bo["sharpe"]:
            return "❌", s
        return "➖", s
    if cand:
        k = max(cand, key=lambda x: S[x]["IS"]["sharpe"])
        res["pick"] = k
        res["verdict"], res["why"] = judge(k)
    else:
        res["verdict"], res["why"] = "❌", "앞 기간에 기준 연수익 −0.5%p 안 변형 없음"
    res["user_t90h40"] = dict(zip(("verdict", "why"), judge("t90h40")))
    print("Q15-2", res["verdict"], res["why"], "| 원안", res["user_t90h40"], flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
