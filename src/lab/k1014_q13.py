"""📈 Q13-1·5 — 과거 검증 (사용자 10/14 13시 보고에 답: "1,5번 진행")
결과 → market/lab/k1014_q13.json (+ 사건표 market/lab/k1014_q13_rows.csv.gz)

공통 틀 (Q10·Q16·Q18 과 같음): 신호 다음 거래일 종가 진입 · 왕복 0.5%(미국)/0.45%(한국) · 출구 = 킥 규칙(kexit)
  · 초과 = 같은 기간 지수 대비 · 같은 종목·같은 신호 20거래일 안 재신호 무시
  · 앞 2008~2016 에서 고르고 뒤 2017~ 에서 시험 · 유니버스 = 오늘 S&P500+400 · 한국 스캐너 목록(생존자 편향)

Q13-1 📰 「이유 있는 갭」 (미국만 — 한국·일본은 무료 과거 실적일 자료가 없어 시험 못 함)
  사건: 📈 gap = 시가 갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가 (킥 갭 필터 대용)
        (참고) gapw = 시가 갭 ≥4% · 전일 고가 위 시가 · 거래량 ≥1.5배 (넓은 갭 전체)
  뉴스 = 그 종목 실적 발표일(yfinance get_earnings_dates)이 갭 날 0~3 달력일 전 안에 있음 (앱의 「실적 갭」 판정과 같은 창).
        실적일 자료가 그 날짜를 덮지 못하는 사건(가장 오래된 실적일보다 100일 넘게 앞선 사건)은 「모름」으로 빼고 셈.
  판정(결과 보기 전): ✅ = 시험 기간 뉴스 없는 갭 초과 평균 < 0 · 뉴스 갭 − 뉴스 없는 갭 ≥ +0.5%p · 과반 해 뉴스 쪽이 나음
                          · 앞 기간도 뉴스 쪽이 나음 · 뉴스 없는 갭 n ≥ 100
                      🧪 = 뉴스 쪽이 시험 기간에 더 좋지만 위 기준 일부 못 미침 · ❌ = 뉴스 쪽이 같거나 나쁨 · ➖ = 표본·자료 부족
  반영(✅ 일 때): 미국 「📈 돌파 갭」(앱이 이미 실적 갭을 따로 떼어 낸 = 뉴스 없는 갭)을 킥에서 빼고 📰 그림자 채점만.

Q13-5 🧯 「같은 날 손절 여러 개 → 며칠 쉬기」 차단기
  킥처럼 5칸(한 칸 20%) 모의 운용(📈 gap + ☕ nh, 시장별 · 순위 = 20일 수익 높은 순 · Q10-3 과 같은 틀).
  출구가 「손절 −5%」인 칸이 같은 날 M 개 이상이면 그날 종가부터 P 거래일 동안 새 진입 멈춤(든 칸은 그대로).
  M(2·3) × P(1·3·5) 를 앞 기간에서 고름(샤프 최대, 연수익이 기준 −0.5%p 이상인 것 중). 사용자 원안 = M2·P3 도 따로 보고.
  판정(결과 보기 전): ✅ = 시험 기간 샤프 ≥ 기준 · 연수익 ≥ 기준 −0.5%p · (최대낙폭 2%p 이상 덜함 또는 최악의 5일 덜함)
                      ❌ = 샤프·연수익 모두 기준보다 나쁨 · ➖ = 그 밖
"""
import json, sys, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402
from k1014_q10 import pstat     # noqa: E402

AB.START = "2006-06-01"
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q13.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
STOP = -0.05
EARN_BUDGET = 14 * 60


def kexit_t(c, ma20, e, stop=STOP, take=0.15, tday=15, tmin=0.03, cap=60):
    """KI.kexit 와 같은 출구 + 출구 이유(stop/other)"""
    n = len(c)
    if e + cap >= n:
        return None
    e0, half, rh, mx = c[e], False, 0.0, c[e]
    for k in range(1, cap + 1):
        j = e + k
        p = c[j]
        mx = max(mx, p)
        r = p / e0 - 1
        if r <= stop:
            return (rh + r / 2 if half else r), j, "stop"
        if not half and r >= take:
            half, rh = True, r / 2
            continue
        if half:
            if not np.isnan(ma20[j]) and p < ma20[j]:
                return rh + r / 2, j, "ma20"
        elif k >= tday and mx / e0 - 1 < tmin:
            return r, j, "time"
    r = c[e + cap] / e0 - 1
    return (rh + r / 2 if half else r), e + cap, "cap"


def build(m, data, idx):
    isym, minp, minvol = AB.MKT[m]
    cost = AB.COST.get(m, AB.DEF_COST)
    rows, closes = [], {}
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        c, dates = F["c"], d.index
        n = len(dates)
        closes[t] = pd.Series(c, index=dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        ev = {"gap": F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (F["o"] > F["ph"]) & (c > F["hi60"]),
              "nh": F["liq"] & F["nh"] & (F["vr"] >= 1.5)}
        if m == "US":
            ev["gapw"] = F["liq"] & (F["gap"] >= 0.04) & (F["vr"] >= 1.5) & (F["o"] > F["ph"])
        for kind, e in ev.items():
            for ti in np.where(e & (np.arange(n) >= 260))[0]:
                if ti + 1 >= n:
                    continue
                r = dict(tk=t, kind=kind, mkt=m, date=str(dates[ti].date()), ti=int(ti),
                         gp=round(float(F["gap"][ti]) * 100, 2),
                         pre20=None if np.isnan(F["pre20"][ti]) else round(float(F["pre20"][ti]), 2))
                r.update(KI.outcomes(c, F["ma20"], ixa, ti + 1, cost))
                kx = kexit_t(c, F["ma20"], ti + 1)
                if kx is not None:
                    r["kx_ex"] = str(dates[kx[1]].date())
                    r["kx_why"] = kx[2]
                rows.append(r)
    return rows, closes


# ───────────────────────────── 실적일 (미국) ─────────────────────────────
def earn_dates(tks, log):
    import yfinance as yf
    t0 = time.time()
    out, err = {}, {"n": 0, "last": ""}

    def one(t):
        if time.time() - t0 > EARN_BUDGET:
            return t, None
        for att in range(3):
            try:
                df = yf.Ticker(t).get_earnings_dates(limit=100)
                if df is None or not len(df):
                    return t, []
                ds = sorted({i.strftime("%Y-%m-%d") for i in df.index})
                return t, ds
            except Exception as e:
                err["n"] += 1
                err["last"] = repr(e)[:160]
                time.sleep(3 * (att + 1))
        return t, None

    with ThreadPoolExecutor(4) as ex:
        for t, ds in ex.map(one, tks):
            if ds:
                out[t] = ds
    log.update({"earn_req": len(tks), "earn_got": len(out), "earn_err": err["n"], "earn_err_last": err["last"],
                "earn_sec": round(time.time() - t0),
                "earn_oldest_med": (sorted(v[0] for v in out.values())[len(out) // 2] if out else None)})
    return out


def tag_news(df, E):
    news = []
    for tk, d in zip(df["tk"], df["date"]):
        ds = E.get(tk)
        if not ds or (dt.date.fromisoformat(d) - dt.date.fromisoformat(ds[0])).days < 100:
            news.append(None)
            continue
        g = dt.date.fromisoformat(d)
        news.append(any(0 <= (g - dt.date.fromisoformat(x)).days <= 3 for x in ds))
    return news


def q131(df):
    res = {}
    for kind in ("gap", "gapw"):
        b = df[(df["mkt"] == "US") & (df["kind"] == kind)].dropna(subset=["x_kk"])
        b = AB.dedupe(b).reset_index(drop=True)
        known = b[b["news"].notna()].copy()
        known["news"] = known["news"].astype(bool)
        E = {"n_all": int(len(b)), "n_known": int(len(known))}
        per = {}
        for pn, s in (("IS", known[(known["date"] >= IS_START) & (known["date"] <= IS_END)]), ("OOS", known[known["date"] >= OOS_START])):
            per[pn] = {"news": KI.evals(s[s["news"]], "kk"), "nonews": KI.evals(s[~s["news"]], "kk"), "all": KI.evals(s, "kk")}
        E["per"] = {pn: {g: {"x": v["x"], "r": v["r"], "by_year": v.get("by_year"), "x_ex_best_year": v.get("x_ex_best_year")}
                         for g, v in r.items()} for pn, r in per.items()}
        o, i = per["OOS"], per["IS"]
        na, xa = o["news"]["x"].get("avg"), o["nonews"]["x"].get("avg")
        ia, ix = i["news"]["x"].get("avg"), i["nonews"]["x"].get("avg")
        nn = o["nonews"]["x"].get("n", 0)
        ay, sy = o["news"].get("by_year") or {}, o["nonews"].get("by_year") or {}
        yrs = [y for y in sy if y in ay]
        better = sum(1 for y in yrs if (ay[y]["x"] or 0) > (sy[y]["x"] or 0))
        if na is None or xa is None or nn < 30 or o["news"]["x"].get("n", 0) < 30:
            vd = "➖"
        elif xa < 0 and na - xa >= 0.5 and better * 2 > len(yrs) and ia is not None and ix is not None and ia > ix and nn >= 100:
            vd = "✅"
        elif na > xa:
            vd = "🧪"
        else:
            vd = "❌"
        E["verdict"] = vd
        E["why"] = (f"시험 기간 뉴스 갭 {o['news']['x'].get('n')}건 초과 {na:+.2f}% 손익비 {o['news']['r'].get('pf')} vs 뉴스 없는 갭 {nn}건 "
                    f"{xa:+.2f}% 손익비 {o['nonews']['r'].get('pf')} · 앞 기간 {ia:+.2f}% vs {ix:+.2f}% · 뉴스 쪽이 나은 해 {better}/{len(yrs)}"
                    if na is not None and xa is not None and ia is not None and ix is not None else "표본 없음")
        print("Q13-1", kind, vd, E["why"], flush=True)
        res[kind] = E
    return res


# ───────────────────────────── Q13-5 차단기 ─────────────────────────────
def sim(ev, R, cost, M=None, P=None, slots=5):
    dates = R.index
    pos = {}                       # tk -> (출구 날짜, 손절?)
    daily = pd.Series(0.0, index=dates)
    by_entry = {d: g.sort_values("pre20", ascending=False) for d, g in ev.groupby("entry")}
    trades, blocked_days, fired = 0, 0, 0
    Rv = R.to_numpy()
    col = {t: i for i, t in enumerate(R.columns)}
    block_until = -1
    for k, d in enumerate(dates):
        if pos:
            v = [Rv[k, col[t]] for t in pos if t in col]
            v = [x for x in v if not np.isnan(x)]
            daily.iloc[k] = sum(v) / slots
        out = [t for t, (ex, _) in pos.items() if ex <= d]
        nstop = sum(1 for t in out if pos[t][1])
        for t in out:
            del pos[t]
            daily.iloc[k] -= cost / 2 / slots
        if M is not None and nstop >= M:
            block_until = max(block_until, k + P)
            fired += 1
        if k <= block_until:
            if d in by_entry:
                blocked_days += 1
            continue
        if d in by_entry:
            for _, c in by_entry[d].iterrows():
                if len(pos) >= slots:
                    break
                t = c["tk"]
                if t in pos or t not in col:
                    continue
                pos[t] = (pd.Timestamp(c["exit"]), c["kx_why"] == "stop")
                daily.iloc[k] -= cost / 2 / slots
                trades += 1
    return daily, trades, blocked_days, fired


def q135(df, closes_by_m):
    res = {}
    for m in ("US", "KR"):
        C = pd.DataFrame(closes_by_m[m]).sort_index()
        C = C[C.index >= "2007-06-01"]
        R = C.pct_change(fill_method=None).clip(-0.5, 1.0)
        cost = AB.COST.get(m, AB.DEF_COST)
        ev = df[(df["mkt"] == m) & df["kind"].isin(["gap", "nh"])].dropna(subset=["kx_ex"]).copy()
        ev = pd.concat([AB.dedupe(g) for _, g in ev.groupby("kind")])
        di = R.index
        p_ = di.searchsorted(pd.to_datetime(ev["date"]), side="right")
        ev = ev[p_ < len(di)].copy()
        ev["entry"] = di[p_[p_ < len(di)]]
        ev["exit"] = pd.to_datetime(ev["kx_ex"])
        ev = ev[ev["entry"] >= IS_START]
        t0 = time.time()
        runs = {}
        d, tr, bl, fi = sim(ev, R, cost)
        runs["base"] = (d, tr, bl, fi)
        for M in (2, 3):
            for P in (1, 3, 5):
                runs[f"M{M}|P{P}"] = sim(ev, R, cost, M, P)
        print("Q13-5 sim", m, round(time.time() - t0), "s", flush=True)
        S = {}
        for k, (d, tr, bl, fi) in runs.items():
            S[k] = {"IS": pstat(d[(d.index >= IS_START) & (d.index <= IS_END)]), "OOS": pstat(d[d.index >= OOS_START]),
                    "trades": tr, "blocked_days": bl, "fired": fi}
        b = S["base"]
        cand = [k for k in S if k != "base" and S[k]["IS"].get("cagr") is not None and S[k]["IS"]["cagr"] >= b["IS"]["cagr"] - 0.5]
        E = {"runs": S}

        def judge(k):
            o, bo = S[k]["OOS"], b["OOS"]
            better_dd = (o["mdd"] - bo["mdd"] >= 2) or (o["worst_5d"] > bo["worst_5d"])
            if o["sharpe"] >= bo["sharpe"] and o["cagr"] >= bo["cagr"] - 0.5 and better_dd:
                v = "✅"
            elif o["sharpe"] < bo["sharpe"] and o["cagr"] < bo["cagr"]:
                v = "❌"
            else:
                v = "➖"
            return v, (f"{k} · 시험 기간 연수익 {o['cagr']}% vs 기준 {bo['cagr']}% · 샤프 {o['sharpe']} vs {bo['sharpe']} · "
                       f"최대낙폭 {o['mdd']}% vs {bo['mdd']}% · 최악의 5일 {o['worst_5d']}% vs {bo['worst_5d']}% · 작동 {S[k]['fired']}번")
        if not cand:
            E["verdict"], E["why"] = "❌", "앞 기간에 기준 연수익 −0.5%p 안에 드는 변형 없음"
        else:
            k = max(cand, key=lambda x: S[x]["IS"]["sharpe"] or -9)
            E["pick"] = k
            E["verdict"], E["why"] = judge(k)
        E["user_M2P3"] = dict(zip(("verdict", "why"), judge("M2|P3")))
        rob = sum(1 for kk in S if kk != "base" and (S[kk]["OOS"].get("sharpe") or 0) >= b["OOS"]["sharpe"])
        E["robust"] = f"{rob}/{len(S) - 1}"
        print("Q13-5", m, E.get("verdict"), E.get("why"), "| 원안", E["user_M2P3"], "| 기준 이상", E["robust"], flush=True)
        res[m] = E
    return res


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    allrows, closes_by_m, us_tks = [], {}, []
    for m in ("US", "KR"):
        log = {}
        tks = AB.universe(m, log)
        idx = AB.idx_series(AB.MKT[m][0])
        data = AB.download(tks, log, time.time())
        log["sec"] = round(time.time() - t0)
        res["log"][m] = log
        print(m, json.dumps(log, ensure_ascii=False), flush=True)
        rows, closes = build(m, data, idx)
        allrows += rows
        closes_by_m[m] = closes
        if m == "US":
            us_tks = sorted(data)
        del data
    df = pd.DataFrame(allrows)
    print("rows", len(df), flush=True)
    try:
        elog = {}
        E = earn_dates(us_tks, elog)
        res["log"]["earn"] = elog
        print("earn", json.dumps(elog, ensure_ascii=False), flush=True)
        df["news"] = None
        us = df["mkt"] == "US"
        df.loc[us, "news"] = pd.Series(tag_news(df[us], E), index=df[us].index, dtype=object)
        res["q131"] = q131(df)
    except Exception as e:
        res["q131_err"] = repr(e)[:300]
        print("q131 err", e, flush=True)
    df.to_csv(ROOT / "market" / "lab" / "k1014_q13_rows.csv.gz", index=False, compression="gzip")
    try:
        res["q135"] = q135(df, closes_by_m)
    except Exception as e:
        res["q135_err"] = repr(e)[:300]
        print("q135 err", e, flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
