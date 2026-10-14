"""📈 10/14 16시 Q16-1·3·5 — 과거 검증 (사용자 10/14 16시 보고에 답: "1,3,5 진행")
결과 → market/lab/k1014_q16.json  (10/13 의 Q16 묶음 = k1013_q16.py · q16_bt.json 과 다른 묶음 → 반영 판정은 market/q16b_bt.json)

공통 틀 (Q10·Q13·Q15 와 같음): 사건 = market/lab/k1014_q10_rows.csv.gz (킥 신호 대용: 📈 gap · ☕ nh(52주 신고가) · 📊 pead)
  · 신호 다음 거래일 종가 진입 · 출구 = 킥 규칙(kexit) · 왕복 0.5%(미국)/0.45%(한국) → r_kk(절대) · x_kk(같은 기간 지수 초과)
  · 같은 종목·같은 신호 20거래일 안 재신호 무시 · 앞 2008~2016 에서 고르고 뒤 2017~ 에서 시험
  · 유니버스 = 오늘 S&P500+400 · 한국 스캐너 목록 (생존자 편향 — 과거 종목 수·시장 폭이 실제보다 좋게 나옴)

Q16-1 🇰🇷 한국 돌파 갭 문 닫기 (사건표만으로 계산 — 내려받기 없음)
  판정(결과 보기 전): ✅ 닫기 = 한국 gap 초과 평균이 앞·시험 기간 모두 < 0 · 시험 기간 절대 손익비 < 1.0
                         · 시험 기간 해별 초과 < 0 인 해 ≥ 6/10 · 그 칸을 받을 미국 gap+nh 시험 기간 절대 평균이 한국 gap 보다 +0.5%p 이상
                      🧪 = 시험 기간만 위를 만족 · ❌ = 시험 기간 한국 gap 초과 평균 ≥ 0

Q16-3 🇨🇳 중국 신용 자극 → 한국 킥 크기 절반
  자료: FRED 의 BIS 「중국 민간 비금융 부문 신용 ÷ GDP(%)」 분기 (QCNPAM770A, 없으면 신용 잔액 CRDQCNAPABIS 로 대신)
  신용 자극 CI_q = (R_q − R_{q−4}) − (R_{q−4} − R_{q−8})   (R = 신용/GDP · 잔액이면 4분기 증가분 변화 ÷ 1년 전 잔액)
  쓸 수 있는 날 = 분기 끝 + 6개월 (BIS 발표 늦음 — 앞을 보지 않게 넉넉히)
  꺼짐(절반) 상태 = CI 가 k 분기 연속 줄어듦 (k = 1·2·3) 또는 CI < 0.  원안 = k1 (석 달 = 한 분기 줄어듦)
  사건 = 한국 gap+nh. 판정(결과 보기 전): 앞 기간 꺼짐 n≥100 판 중 (켜짐 − 꺼짐) 절대 평균 차이 최대를 고름 →
     ✅ = 시험 기간 꺼짐 쪽 절대 평균 ≤ 켜짐 − 1.0%p · 꺼짐 n ≥ 100 · 앞 기간도 꺼짐 < 켜짐
     🧪 = 시험 기간 꺼짐 < 켜짐 (일부 못 미침) · ❌ = 시험 기간 꺼짐 ≥ 켜짐 · ➖ = 표본 부족/자료 없음

Q16-5 🌡 시장 폭 경보
  폭 B_t = 유니버스 중 종가 > 200일 평균인 비율(%, 200일 평균이 있는 종목 100개 이상인 날만)
  경보 = 지수가 252일 최고의 3% 안 · B_t − B_{t−L} ≤ −T  (L = 40·60 · T = 10·15·20, 원안 L60·T15)
  사건 = 시장별 gap+nh. 앞 기간 경보 n≥50 판 중 (경보 아님 − 경보) 절대 평균 차이 최대를 고름 →
     ✅ = 시험 기간 경보 쪽 절대 평균 ≤ 경보 아님 − 1.0%p · 경보 n ≥ 50 · 앞 기간도 경보 < 경보 아님
          · 시험 기간 경보 날 지수 다음 60거래일 수익이 전체 날 평균보다 낮음
     🧪 = 시험 기간 경보 쪽 < 경보 아님 (일부 못 미침) · ❌ = 시험 기간 경보 ≥ 경보 아님 · ➖ = 경보 n < 30
  반영: ✅ = 킥 새 진입 크기 절반(그 시장) + 🎯 판정 옆 「주의」 · 🧪 = 「주의」 표시만 · ❌ = 안 붙임
"""
import io, json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402

AB.START = "2006-06-01"
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q16.json"
ROWS = ROOT / "market" / "lab" / "k1014_q10_rows.csv.gz"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"


def tb(a):
    """참/거짓/없음 섞인 배열 → object 배열 (True·False·None)"""
    return pd.Series([None if (v is None or (isinstance(v, float) and np.isnan(v))) else bool(v) for v in np.asarray(a, dtype=object)], dtype=object).to_numpy()


def pst(x):
    x = pd.Series(x, dtype=float).dropna()
    if not len(x):
        return {"n": 0}
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    return {"n": int(len(x)), "avg": round(float(x.mean()), 2), "med": round(float(x.median()), 2),
            "win": round(float((x > 0).mean()) * 100, 1), "pf": round(float(pos / neg), 2) if neg > 0 else None}


def periods(df):
    return {"IS": df[(df["date"] >= IS_START) & (df["date"] <= IS_END)], "OOS": df[df["date"] >= OOS_START]}


def by_year(s, col):
    g = s.dropna(subset=[col])
    return {y: round(float(v.mean()), 2) for y, v in g.groupby(g["date"].str[:4])[col]}


def load_rows():
    d = pd.read_csv(ROWS, low_memory=False)
    out = []
    for (m, k), g in d.groupby(["mkt", "kind"]):
        out.append(AB.dedupe(g))
    d = pd.concat(out)
    return d[d["r_kk"].notna()].copy()


# ───────────────────────── Q16-1 ─────────────────────────
def q161(ev):
    kg = ev[(ev["mkt"] == "KR") & (ev["kind"] == "gap")]
    us = ev[(ev["mkt"] == "US") & (ev["kind"].isin(["gap", "nh"]))]
    kn = ev[(ev["mkt"] == "KR") & (ev["kind"] == "nh")]
    E = {}
    for pn, s in periods(kg).items():
        E[pn] = {"x": pst(s["x_kk"]), "r": pst(s["r_kk"]), "by_year": by_year(s, "x_kk")}
    for nm, src in (("us_alt", us), ("kr_nh", kn)):
        E[nm] = {pn: {"x": pst(s["x_kk"]), "r": pst(s["r_kk"])} for pn, s in periods(src).items()}
    o, i = E["OOS"], E["IS"]
    yrs = o["by_year"]
    neg = sum(1 for v in yrs.values() if v < 0)
    E["neg_years"] = f"{neg}/{len(yrs)}"
    alt = E["us_alt"]["OOS"]["r"].get("avg")
    xa, xi, pf, ra = o["x"].get("avg"), i["x"].get("avg"), o["r"].get("pf"), o["r"].get("avg")
    why = (f"한국 📈 갭 대용 시험 기간 {o['x'].get('n')}건 초과 {xa:+.2f}% · 절대 {ra:+.2f}% 손익비 {pf} · 진 해 {E['neg_years']} "
           f"· 앞 기간 {i['x'].get('n')}건 초과 {xi:+.2f}% · 그 칸을 받을 미국 gap+nh 시험 기간 절대 {alt:+.2f}%")
    if xa is None:
        v = "➖"
    elif xa < 0 and (xi or 0) < 0 and (pf or 9) < 1.0 and neg >= 0.6 * len(yrs) and (alt or -99) >= ra + 0.5:
        v = "✅"
    elif xa < 0 and (pf or 9) < 1.0:
        v = "🧪"
    else:
        v = "❌"
    E["verdict"], E["why"] = v, why
    print("Q16-1", v, why, flush=True)
    return E


# ───────────────────────── Q16-3 ─────────────────────────
def fred(sid, log):
    import requests
    for att in range(3):
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=90,
                             headers={"User-Agent": "Mozilla/5.0 (research script)"})
            if r.status_code == 200 and "," in r.text[:200]:
                d = pd.read_csv(io.StringIO(r.text))
                d.columns = ["date", "v"]
                d["v"] = pd.to_numeric(d["v"], errors="coerce")
                d = d.dropna()
                d["date"] = pd.to_datetime(d["date"])
                log[sid] = f"{len(d)}개 {d['date'].min().date()}~{d['date'].max().date()}"
                return d.set_index("date")["v"]
            log[sid] = f"http {r.status_code}"
        except Exception as e:
            log[sid] = repr(e)[:160]
        time.sleep(5)
    return None


def bis(log):
    """BIS 통계 API (FRED 가 막힐 때) — 중국 민간 비금융 신용 ÷ GDP(%) 분기"""
    import requests
    urls = ["https://stats.bis.org/api/v2/data/dataflow/BIS/WS_TC/2.0/Q.CN.P.A.M.770.A?format=csv",
            "https://stats.bis.org/api/v1/data/WS_TC/Q.CN.P.A.M.770.A/all?format=csv",
            "https://stats.bis.org/api/v1/data/BIS,WS_TC,2.0/Q.CN.P.A.M.770.A?format=csv"]
    for u in urls:
        try:
            r = requests.get(u, timeout=90, headers={"User-Agent": "Mozilla/5.0 (research script)", "Accept": "text/csv"})
            if r.status_code != 200:
                log[u[-60:]] = f"http {r.status_code}"
                continue
            d = pd.read_csv(io.StringIO(r.text))
            tc = next((c for c in d.columns if c.upper() in ("TIME_PERIOD", "TIME PERIOD")), None)
            vc = next((c for c in d.columns if c.upper() in ("OBS_VALUE", "OBS VALUE", "VALUE")), None)
            if tc is None or vc is None:
                log[u[-60:]] = "열 없음 " + ",".join(map(str, d.columns[:12]))
                continue
            q = d[tc].astype(str).str.replace("-Q", "Q", regex=False)
            dt_ = pd.PeriodIndex(q, freq="Q").to_timestamp(how="start")
            out = pd.Series(pd.to_numeric(d[vc], errors="coerce").to_numpy(), index=dt_).dropna().sort_index()
            out = out[~out.index.duplicated()]
            log["bis"] = f"{len(out)}개 {out.index.min().date()}~{out.index.max().date()}"
            if len(out) >= 20:
                return out
        except Exception as e:
            log[u[-60:]] = repr(e)[:160]
    return None


def china_ci(log):
    s = fred("QCNPAM770A", log)
    if s is None or len(s) < 20:
        s = bis(log)
    kind = "ratio"
    if s is None or len(s) < 20:
        s = fred("CRDQCNAPABIS", log)
        kind = "level"
    if s is None or len(s) < 20:
        return None, kind
    s = s.sort_index()
    if kind == "ratio":
        d4 = s - s.shift(4)
        ci = d4 - d4.shift(4)
    else:
        f4 = s - s.shift(4)
        ci = (f4 - f4.shift(4)) / s.shift(4) * 100
    ci = ci.dropna()
    q_end = ci.index + pd.offsets.QuarterEnd(0)
    avail = q_end + pd.DateOffset(months=6)
    out = pd.DataFrame({"q": ci.index.strftime("%Y-%m"), "ci": ci.to_numpy(), "avail": avail})
    return out, kind


def ci_states(tab):
    ci = tab["ci"].to_numpy()
    dec = np.r_[False, ci[1:] < ci[:-1]]
    run = np.zeros(len(ci), int)
    for i in range(len(ci)):
        run[i] = run[i - 1] + 1 if (i and dec[i]) else (1 if dec[i] else 0)
    tab = tab.copy()
    tab["run"] = run
    for k in (1, 2, 3):
        tab[f"k{k}"] = run >= k
    tab["neg"] = tab["ci"] < 0
    return tab


def asof_state(dates, tab, col):
    t = tab.sort_values("avail")
    idx = np.searchsorted(t["avail"].to_numpy(), pd.to_datetime(dates).to_numpy(), side="right") - 1
    v = t[col].to_numpy()
    return np.where(idx >= 0, v[np.clip(idx, 0, None)], np.nan)


def fwd_idx(idx, H=60):
    a = idx.to_numpy(float)
    f = np.full(len(a), np.nan)
    f[:-H] = a[H:] / a[:-H] - 1
    return pd.Series(f * 100, index=idx.index)


def split_judge(ev, flag_col, pick_cands, nmin_is, nmin_oos, gap_need, idxf=None, flags_by_day=None, extra_idx=False):
    """flag=True(꺼짐/경보) vs False 의 절대 평균 차이로 고르고 판정"""
    R = {"var": {}}
    for c in pick_cands:
        V = {}
        for pn, s in periods(ev).items():
            s = s[s[c].notna()]
            on, off = s[s[c] == False], s[s[c] == True]    # noqa: E712
            V[pn] = {"flag": pst(off["r_kk"]), "rest": pst(on["r_kk"]), "flag_x": pst(off["x_kk"]), "rest_x": pst(on["x_kk"]),
                     "flag_share": round(len(off) / max(len(s), 1) * 100, 1)}
            if idxf is not None and flags_by_day is not None:
                fd = flags_by_day[c]
                per = fd[(fd.index >= pd.Timestamp(IS_START)) & (fd.index <= pd.Timestamp(IS_END))] if pn == "IS" else fd[fd.index >= pd.Timestamp(OOS_START)]
                f = idxf.reindex(per.index)
                V[pn]["idx60_flag"] = round(float(f[per == True].mean()), 2) if (per == True).any() else None   # noqa: E712
                V[pn]["idx60_all"] = round(float(f.mean()), 2)
                V[pn]["flag_days"] = int((per == True).sum())   # noqa: E712
        R["var"][c] = V

    def gap(V, pn):
        a, b = V[pn]["rest"].get("avg"), V[pn]["flag"].get("avg")
        return None if a is None or b is None else a - b
    cand = [c for c, V in R["var"].items() if V["IS"]["flag"].get("n", 0) >= nmin_is and gap(V, "IS") is not None]
    better = sum(1 for c, V in R["var"].items() if (gap(V, "OOS") or -99) > 0)
    R["robust"] = f"{better}/{len(pick_cands)}"

    def vd(c):
        V = R["var"][c]
        o, i = V["OOS"], V["IS"]
        n = o["flag"].get("n", 0)
        g_o, g_i = gap(V, "OOS"), gap(V, "IS")
        s = (f"{c} · 시험 기간 걸린 사건 {n}건({o['flag_share']}%) 절대 {o['flag'].get('avg')}% 손익비 {o['flag'].get('pf')} vs 나머지 {o['rest'].get('n')}건 "
             f"{o['rest'].get('avg')}% 손익비 {o['rest'].get('pf')} · 앞 기간 {i['flag'].get('n')}건 {i['flag'].get('avg')}% vs {i['rest'].get('avg')}% "
             f"· 초과로는 {o['flag_x'].get('avg')}% vs {o['rest_x'].get('avg')}% · 변형 중 시험 기간 걸린 쪽이 더 나쁜 것 {R['robust']}")
        if extra_idx:
            s += f" · 걸린 날 지수 다음 60일 {o.get('idx60_flag')}% vs 전체 날 {o.get('idx60_all')}%"
        if n < 30 or g_o is None:
            return "➖", s
        idx_ok = (not extra_idx) or (o.get("idx60_flag") is not None and o["idx60_flag"] < o["idx60_all"])
        if g_o >= gap_need and n >= nmin_oos and (g_i or -99) > 0 and idx_ok:
            return "✅", s
        if g_o > 0:
            return "🧪", s
        return "❌", s
    if cand:
        c = max(cand, key=lambda x: gap(R["var"][x], "IS"))
        R["pick"] = c
        R["verdict"], R["why"] = vd(c)
    else:
        R["verdict"], R["why"] = "➖", "앞 기간 표본 기준 넘는 변형 없음"
    return R, vd


def q163(ev, log):
    tab, kind = china_ci(log)
    if tab is None:
        return {"verdict": "➖", "why": "FRED 중국 신용 자료를 못 받음", "log": log}
    tab = ci_states(tab)
    kr = ev[(ev["mkt"] == "KR") & (ev["kind"].isin(["gap", "nh"]))].copy()
    cols = ["k1", "k2", "k3", "neg"]
    for c in cols:
        kr[c] = tb(asof_state(kr["date"], tab, c))
    idx = AB.idx_series("^KS11")
    days = idx.index
    fl = {}
    for c in cols:
        st = asof_state(days, tab, c)
        fl[c] = pd.Series(tb(st), index=days)
    R, vd = split_judge(kr, None, cols, 100, 100, 1.0, idxf=fwd_idx(idx), flags_by_day=fl)
    R["user_k1"] = dict(zip(("verdict", "why"), vd("k1")))
    R["kind"] = kind
    last = tab.iloc[-1]
    R["now"] = {"q": last["q"], "ci": round(float(last["ci"]), 2), "run": int(last["run"]), "avail": str(last["avail"].date()),
                "states": {c: bool(last[c]) for c in cols}}
    R["series"] = [{"q": r.q, "ci": round(float(r.ci), 2), "avail": str(r.avail.date())} for r in tab.tail(24).itertuples()]
    R["log"] = log
    print("Q16-3", R["verdict"], R["why"], "| 원안", R["user_k1"], "| now", R["now"], flush=True)
    return R


# ───────────────────────── Q16-5 ─────────────────────────
GRID5 = [(L, T) for L in (40, 60) for T in (10, 15, 20)]


def breadth(data):
    cl = pd.DataFrame({t: d["close"] for t, d in data.items()}).sort_index()
    ma = cl.rolling(200, min_periods=200).mean()
    valid = ma.notna() & cl.notna()
    above = (cl > ma) & valid
    cnt = valid.sum(axis=1)
    b = (above.sum(axis=1) / cnt.replace(0, np.nan) * 100).where(cnt >= 100)
    return b.dropna(), cnt


def q165(ev, m, data, log):
    B, cnt = breadth(data)
    idx = AB.idx_series(AB.MKT[m][0])
    idx = idx[~idx.index.duplicated()]
    B = B.reindex(idx.index).ffill(limit=3)
    near = idx >= 0.97 * idx.rolling(252, min_periods=200).max()
    fl = {}
    for L, T in GRID5:
        w = near & ((B - B.shift(L)) <= -T)
        fl[f"L{L}T{T}"] = pd.Series(tb(w.where(B.notna() & B.shift(L).notna())), index=w.index)
    e = ev[(ev["mkt"] == m) & (ev["kind"].isin(["gap", "nh"]))].copy()
    dts = pd.to_datetime(e["date"])
    for c, s in fl.items():
        e[c] = tb(s.reindex(dts).to_numpy())
    R, vd = split_judge(e, None, list(fl), 50, 50, 1.0, idxf=fwd_idx(idx), flags_by_day=fl, extra_idx=True)
    R["user_L60T15"] = dict(zip(("verdict", "why"), vd("L60T15")))
    last = B.dropna().index[-1]
    R["now"] = {"d": str(last.date()), "breadth": round(float(B[last]), 1), "b60": round(float(B.shift(60)[last]), 1) if pd.notna(B.shift(60)[last]) else None,
                "near_hi": bool(near[last]), "idx_from_hi": round(float(idx[last] / idx.rolling(252).max()[last] * 100 - 100), 2),
                "n_tickers": int(cnt.reindex([last]).iloc[0]) if last in cnt.index else None,
                "warn": {c: (bool(s[last]) if pd.notna(s[last]) else None) for c, s in fl.items()}}
    yr = B.groupby(B.index.year).agg(["min", "max"]).round(1)
    R["breadth_years"] = {int(y): [float(a), float(b)] for y, (a, b) in yr.iterrows()}
    R["log"] = log
    print("Q16-5", m, R["verdict"], R["why"], "| 원안", R["user_L60T15"], "| now", R["now"], flush=True)
    return R


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__}
    ev = load_rows()
    print("events", ev.groupby(["mkt", "kind"]).size().to_dict(), flush=True)
    try:
        res["q161"] = q161(ev)
    except Exception:
        import traceback
        res["q161_err"] = traceback.format_exc()[-800:]
        print(res["q161_err"])
    try:
        res["q163"] = q163(ev, {})
    except Exception:
        import traceback
        res["q163_err"] = traceback.format_exc()[-800:]
        print(res["q163_err"])
    res["q165"] = {}
    for m in ("US", "KR"):
        log = {}
        try:
            tks = AB.universe(m, log)
            data = AB.download(tks, log, time.time())
            log["sec"] = round(time.time() - t0)
            print(m, json.dumps(log, ensure_ascii=False), flush=True)
            res["q165"][m] = q165(ev, m, data, log)
            del data
        except Exception:
            import traceback
            res["q165"][m] = {"verdict": "➖", "err": traceback.format_exc()[-800:], "log": log}
            print(res["q165"][m]["err"])
        OUT.parent.mkdir(parents=True, exist_ok=True)
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    res["sec"] = round(time.time() - t0)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
