"""📈 Q12-1 🧭 스캐너 나침반 — 과거 검증 (사용자 10/14 12시 보고에 답: "1번만 실행")
결과 → market/lab/k1014_q12.json · 판정 기준은 결과 보기 전에 여기 적음.

규칙: 매주 마지막 거래일, 지난 W거래일 미국 돌파 사건(📈 gap + ☕ nh(컵 대용), market/lab/k1014_q10_rows.csv.gz,
  유니버스 = 오늘 S&P500+400) 중 나스닥100 소속 비율 r ÷ 「살아 있는」 감시 종목 중 나스닥100 비율 u = 쏠림 s.
  (살아 있음 = 사건표에 첫 사건이 이미 나온 종목 — 가격 자료 시작의 대용)
  s ≥ hi → 주식 칸 안 나스닥 몫 +d, s ≤ lo → −d, 사이 → 50/50. 사건 W일 합계 < 10 이면 50/50.
  d 는 「포트 전체 %p」 기준(주식 칸 95% 일 때 5%p = 주식 칸 안 5.26%).
뼈대 = 💼 기본 C안(S&P·나스닥 반반 95% + 금 5%, 판정 없음) + 🦴 방어형 변동성 맞춤(20일·15%·아래 30%, 5%p 밴드)
  · 다음 거래일 종가 체결 · 매주 + 배율 바뀐 날 + 기울기 바뀐 날 비중 맞춤 · 회전율×0.1% · 현금 BIL · 레버리지 없음.
고정안(보고서 그대로): W=20 · hi/lo=1.5/0.67 · d=5%p.
고르기(2008-07~2016 샤프 1등): W∈{20,60} × (hi,lo)∈{(1.5,0.67),(1.25,0.8)} × d∈{5,10}%p.
판정(💼): ✅ = 고른 안이 시험 기간(2017~) skel_bt.judge 통과 + 앞 기간 샤프가 기준보다 0.02 넘게 낮지 않음
              + 고정안도 시험 기간 샤프 ≥ 기준 (손잡이 바꿔도 유지)
         🧪 = 고른 안 시험 기간 샤프 ≥ 기준 & CAGR −0.5%p 이내지만 ✅ 못 미침 · ❌ = 그 밖
참고: 🎯 집중(conc: 200일선·3일, 꺼지면 50%, 공격형 20일·22%·70%)에 고른 안 그대로 · 쏠림의 예측력
  (기울기 방향 vs 다음 20거래일 QQQ−SPY) · 소속 분류를 GICS 정보기술+커뮤니케이션으로 바꾼 판.
주의: 나스닥100·S&P 명단 모두 「오늘」 기준(생존자 편향) — 과거 나스닥 쏠림이 부풀려질 수 있음.
"""
import io, json, sys, itertools, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from src.conc_bt import START, IS_END, OOS_START   # noqa: E402
from src.skel_bt import sticky, realized_vol, summ, judge   # noqa: E402
from src.rules7 import hold_band, VOL_ROLES               # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q12.json"
COST = 0.001
HD = {"User-Agent": "Mozilla/5.0 (research script)"}
res = {"made": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")}


def wiki_tables(pg):
    import requests
    r = requests.get(f"https://en.wikipedia.org/wiki/{pg}", headers=HD, timeout=30)
    return pd.read_html(io.StringIO(r.text))


NDX_FALLBACK = """AAPL ABNB ADBE ADI ADP ADSK AEP AMAT AMD AMGN AMZN ANSS APP ARM ASML AVGO AXON AZN BIIB BKNG BKR CCEP CDNS CDW CEG
CHTR CMCSA COST CPRT CRWD CSCO CSGP CSX CTAS CTSH DASH DDOG DXCM EA EXC FANG FAST FTNT GEHC GFS GILD GOOG GOOGL HON IDXX
INTC INTU ISRG KDP KHC KLAC LIN LRCX LULU MAR MCHP MDLZ MELI META MNST MRVL MSFT MSTR MU NFLX NVDA NXPI ODFL ON ORLY PANW
PAYX PCAR PDD PEP PLTR PYPL QCOM REGN ROP ROST SBUX SHOP SNPS TEAM TMUS TSLA TTD TTWO TXN VRSK VRTX WBD WDAY XEL ZS""".split()


def ndx_members():
    try:
        for t in wiki_tables("Nasdaq-100"):
            cols = [str(x[-1] if isinstance(x, tuple) else x) for x in t.columns]
            ci = next((i for i, x in enumerate(cols) if x.strip().lower() in ("ticker", "symbol", "ticker symbol")), None)
            if ci is not None and 80 <= len(t) <= 130:
                res["ndx_source"] = "wikipedia"
                return sorted({str(s).strip().replace(".", "-") for s in t.iloc[:, ci].dropna()})
    except Exception as e:
        res["ndx_err"] = repr(e)[:200]
    res["ndx_source"] = "fallback(2025~26 명단)"
    return sorted(NDX_FALLBACK)


def tech_members():
    out = set()
    for pg in ("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"):
        for t in wiki_tables(pg):
            col = next((x for x in t.columns if str(x).lower() in ("symbol", "ticker symbol", "ticker")), None)
            sec = next((x for x in t.columns if "gics sector" in str(x).lower()), None)
            if col is not None and sec is not None and len(t) > 300:
                m = t[sec].astype(str).isin(["Information Technology", "Communication Services"])
                out |= {str(s).strip().replace(".", "-") for s in t.loc[m, col]}
                break
    return sorted(out)


def tilt_series(ev, members, idx, W, hi, lo, d_pp):
    """→ 날짜별 나스닥 몫(주식 칸 안) · 쏠림 s"""
    ev = ev.copy()
    ev["m"] = ev["tk"].isin(members)
    first = ev.groupby("tk")["date"].min()
    pos = idx.searchsorted(ev["date"].values)        # 사건일 → 거래일 번호
    ev["p"] = np.clip(pos, 0, len(idx) - 1)
    n_all = np.bincount(ev["p"], minlength=len(idx)).astype(float)
    n_m = np.bincount(ev.loc[ev["m"], "p"], minlength=len(idx)).astype(float)
    ca, cm = np.cumsum(n_all), np.cumsum(n_m)
    win_a = ca - np.concatenate([np.zeros(W), ca[:-W]])
    win_m = cm - np.concatenate([np.zeros(W), cm[:-W]])
    fp = idx.searchsorted(first.values)
    alive_all = np.cumsum(np.bincount(np.clip(fp, 0, len(idx) - 1), minlength=len(idx)))
    fpm = idx.searchsorted(first[first.index.isin(members)].values)
    alive_m = np.cumsum(np.bincount(np.clip(fpm, 0, len(idx) - 1), minlength=len(idx)))
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(win_a > 0, win_m / win_a, np.nan)
        u = np.where(alive_all > 0, alive_m / alive_all, np.nan)
        s = r / u
    d = d_pp / 0.95 / 100
    q = np.full(len(idx), 0.5)
    q[(s >= hi) & (win_a >= 10)] = 0.5 + d
    q[(s <= lo) & (win_a >= 10)] = 0.5 - d
    # 매주 마지막 거래일에만 바꿈 (그 사이엔 지난 값 유지)
    wk = idx.isocalendar().week.values
    last_of_week = np.r_[wk[1:] != wk[:-1], True]
    out = np.empty(len(idx)); cur = 0.5
    for i in range(len(idx)):
        if last_of_week[i]:
            cur = q[i]
        out[i] = cur
    return out, s, win_a


def sim(C, R, keep, scale, qsh, eqw, gdw, a, b):
    idx = C.index
    sel = np.where((idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b)))[0]
    wk = idx.isocalendar().week.values

    def tgt(i):
        e = eqw * keep[i] * scale[i]; g = gdw * keep[i]
        return np.array([e * (1 - qsh[i]), e * qsh[i], g, 1 - e - g])
    w = tgt(sel[0]); val = 1 - COST * float(w[:3].sum()); pend = None; turn = 0.0
    last = (wk[sel[0]], keep[sel[0]], scale[sel[0]], qsh[sel[0]]); nav = np.empty(len(sel)); qs = []
    for j, i in enumerate(sel):
        if j > 0:
            r = R[i]; val *= 1 + float(w @ r); gw = w * (1 + r); s_ = gw.sum()
            if s_ > 0:
                w = gw / s_
        if pend is not None:
            t = float(np.abs(pend - w).sum()); turn += t; val *= 1 - t * COST; w = pend; pend = None
        nav[j] = val; qs.append(qsh[i])
        cur = (wk[i], keep[i], scale[i], qsh[i])
        if cur[0] != last[0] or cur[1:] != last[1:]:
            pend = tgt(i); last = cur
    d = idx[sel]; yrs = max(0.5, (d[-1] - d[0]).days / 365.25)
    qs = np.array(qs)
    return pd.Series(nav, index=d), round(turn / yrs * 100), {"up": round(float((qs > 0.5).mean()) * 100, 1), "down": round(float((qs < 0.5).mean()) * 100, 1)}


def main():
    import yfinance as yf
    tick = ["SPY", "QQQ", "GLD", "BIL", "^GSPC"]
    import time
    cols = {}
    for t in tick:
        for k in range(4):
            try:
                h = yf.Ticker(t).history(start="2005-01-01", auto_adjust=True)["Close"]
                if len(h) > 1000:
                    h.index = pd.to_datetime(h.index).tz_localize(None).normalize(); cols[t] = h; break
            except Exception as e:
                print("retry", t, repr(e)[:100])
            time.sleep(3)
    C = pd.DataFrame(cols).dropna(subset=["SPY", "QQQ", "GLD"]).ffill(limit=5)
    C["BIL"] = C["BIL"].ffill()
    R = C[["SPY", "QQQ", "GLD", "BIL"]].pct_change().fillna(0.0).values
    idx = C.index; spy = C["SPY"]; end = idx[-1]
    PER = (("is", START, IS_END), ("oos", OOS_START, end))

    ev = pd.read_csv(ROOT / "market" / "lab" / "k1014_q10_rows.csv.gz", usecols=["tk", "kind", "mkt", "date"])
    ev = ev[(ev.mkt == "US") & ev.kind.isin(["gap", "nh"])].copy()
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["date"] <= end]
    ndx = ndx_members()
    uni = set(ev.tk)
    res["ndx"] = {"members": len(ndx), "in_universe": len(uni & set(ndx)), "universe": len(uni), "events": int(len(ev))}
    print("ndx", res["ndx"])

    ones = np.ones(len(idx))
    pb = VOL_ROLES["base"]
    sc_b = np.array(hold_band(list(np.clip(pb["target"] / 100 / realized_vol(C, pb["lb"]).bfill().values, pb["floor"], 1.0))))
    half = np.full(len(idx), 0.5)

    def run(keep, sc, qsh, eqw, gdw):
        o, navs = {}, {}
        for pn, a, b in PER:
            nav, t, tl = sim(C, R, keep, sc, qsh, eqw, gdw, a, b)
            s = summ(nav, spy); s.update(turn=t, tilt_pct=tl); o[pn] = s; navs[pn] = nav
        return o, navs

    base, bnav = run(ones, sc_b, half, 0.95, 0.05)
    grid = {}
    for W, (hi, lo), d in itertools.product((20, 60), ((1.5, 0.67), (1.25, 0.8)), (5, 10)):
        q, s, na = tilt_series(ev, ndx, idx, W, hi, lo, d)
        o, nv = run(ones, sc_b, q, 0.95, 0.05)
        grid[f"W{W}_{hi}/{lo}_d{d}"] = (o, nv, q, s, na)
        print("Q121", f"W{W}_{hi}/{lo}_d{d}", {pn: {x: o[pn][x] for x in ("cagr", "sharpe", "mdd", "turn")} for pn in ("is", "oos")})
    fixed_k = "W20_1.5/0.67_d5"
    pick_k = max(grid, key=lambda k: grid[k][0]["is"]["sharpe"] or -9)
    out = {"base": base, "grid": {k: {pn: {x: v[0][pn][x] for x in ("cagr", "sharpe", "mdd", "turn", "tilt_pct", "ex")} for pn in ("is", "oos")} for k, v in grid.items()},
           "fixed": fixed_k, "pick": pick_k}
    for k in (fixed_k, pick_k):
        o, nv = grid[k][0], grid[k][1]
        jg = judge(o["oos"], base["oos"], nv["oos"], bnav["oos"])
        out.setdefault("detail", {})[k] = {"is": o["is"], "oos": o["oos"], "judge": jg}
    pj = out["detail"][pick_k]["judge"]
    po = grid[pick_k][0]; fo = grid[fixed_k][0]
    is_ok = (po["is"]["sharpe"] or 0) >= (base["is"]["sharpe"] or 0) - 0.02
    fixed_ok = (fo["oos"]["sharpe"] or 0) >= (base["oos"]["sharpe"] or 0)
    soft = (po["oos"]["sharpe"] or 0) >= (base["oos"]["sharpe"] or 0) and pj["cagr_ok"]
    out["verdict"] = "✅" if (pj["pass"] and is_ok and fixed_ok) else ("🧪" if soft else "❌")

    # 쏠림의 예측력: 매주 마지막 날 기울기 방향 vs 다음 20거래일 QQQ−SPY
    q, s, na = grid[fixed_k][2], grid[fixed_k][3], grid[fixed_k][4]
    rel = (C["QQQ"].shift(-20) / C["QQQ"] - C["SPY"].shift(-20) / C["SPY"]).values * 100
    wk = idx.isocalendar().week.values
    low = np.r_[wk[1:] != wk[:-1], True]
    pred = {}
    for pn, a, b in PER:
        m = low & (idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b)) & ~np.isnan(rel) & (na >= 10)
        o = {}
        for nm, mm in (("up", q > 0.5), ("mid", q == 0.5), ("down", q < 0.5)):
            x = rel[m & mm]
            o[nm] = {"n": int(len(x)), "avg": round(float(np.mean(x)), 2) if len(x) else None,
                     "qqq_win": round(float((x > 0).mean()) * 100) if len(x) else None}
        ss = s[m]; rr = rel[m]; ok = ~np.isnan(ss)
        o["corr"] = round(float(np.corrcoef(np.log(ss[ok]), rr[ok])[0, 1]), 3) if ok.sum() > 10 else None
        pred[pn] = o
    out["predict"] = pred
    out["now"] = {"date": str(end.date()), "s": round(float(s[-1]), 2) if not np.isnan(s[-1]) else None, "events_20d": int(na[-1]),
                  "nasdaq_share_in_eq": round(float(q[-1]) * 100, 1)}
    # 최근 몇 주 쏠림
    out["recent"] = [{"d": str(idx[i].date()), "s": round(float(s[i]), 2), "n": int(na[i])} for i in np.where(low)[0][-8:] if not np.isnan(s[i])]

    # 참고: 🎯 집중에 고른 안
    pc = VOL_ROLES["conc"]
    sc_c = np.array(hold_band(list(np.clip(pc["target"] / 100 / realized_vol(C, pc["lb"]).bfill().values, pc["floor"], 1.0))))
    gs = C["^GSPC"].ffill()
    keep_c = np.where(sticky(gs > gs.rolling(200).mean(), 3).values, 1.0, 0.5)
    cb, cbn = run(keep_c, sc_c, half, 1.0, 0.0)
    cp, cpn = run(keep_c, sc_c, grid[pick_k][2], 1.0, 0.0)
    out["conc_ref"] = {"base": {pn: {x: cb[pn][x] for x in ("cagr", "sharpe", "mdd", "turn")} for pn in ("is", "oos")},
                       "pick": {pn: {x: cp[pn][x] for x in ("cagr", "sharpe", "mdd", "turn")} for pn in ("is", "oos")},
                       "judge": judge(cp["oos"], cb["oos"], cpn["oos"], cbn["oos"])}
    # 참고: 소속 분류를 GICS 정보기술+커뮤니케이션으로
    try:
        tech = tech_members()
        W_, hl, d_ = pick_k.split("_")
        hi, lo = map(float, hl.split("/"))
        qt, _, _ = tilt_series(ev, tech, idx, int(W_[1:]), hi, lo, int(d_[1:]))
        ot, _ = run(ones, sc_b, qt, 0.95, 0.05)
        out["tech_ref"] = {"members": len(tech), **{pn: {x: ot[pn][x] for x in ("cagr", "sharpe", "mdd", "turn")} for pn in ("is", "oos")}}
    except Exception as e:
        out["tech_ref"] = {"err": repr(e)[:200]}
    res["q121"] = out
    print("verdict", out["verdict"], "pick", pick_k, "now", out["now"])
    print("predict", json.dumps(pred, ensure_ascii=False))


if __name__ == "__main__":
    main()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
