"""📈 Q10-2·3·5 — 과거 검증 (사용자 10/14 10시 보고에 답: "2,3,5 실행")
결과 → market/lab/k1014_q10.json (+ 사건표 market/lab/k1014_q10_rows.csv.gz)

공통 틀 (Q16·Q18 과 같음): 신호 다음 거래일 종가 진입 · 왕복 0.5%(미국)/0.45%(한국) · 출구 = 킥 규칙(kexit)
  · 초과 = 같은 기간 지수 대비 · 같은 종목·같은 신호 20거래일 안 재신호 무시
  · 앞 2008~2016 에서 고르고 뒤 2017~ 에서 시험 (사용자 방식) · 유니버스 = 오늘 S&P500+400 · 한국 스캐너 목록(생존자 편향)
사건(신호 대용): 📈 gap = 시가 갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가
               ☕ nh  = 종가 52주 신고가 · 거래량 ≥1.5배 (컵 돌파 대용)
               📊 pead = 시가 갭 ≥8% · 거래량 ≥3배 · 실적 철(분기 끝 +8~55일)
               🔗 lead = Q16-2 납품사 사건표(market/lab/k1013_cust_rows.csv.gz, 미국 2012~)

Q10-2 🤝 합의 — 사건마다 「같은 종목에 다른 종류 신호가 지난 W 거래일(오늘 포함) 안에 있었나」(앞을 보지 않음).
  정의 A = 아무 다른 종류 · 정의 B = 같은 날 gap+nh 짝은 한 신호로 침(갭이 대개 신고가라 저절로 겹침).
  W(5·10·20) 는 앞 기간에서 고름(합의 쪽 − 단독 쪽 초과 차이 최대, 합의 n ≥ 50).
  판정(결과 보기 전): ✅ = 시험 기간 합의 쪽 초과 평균 ≥ 단독 + 0.5%p · 합의 손익비 ≥ 단독 · 과반 해 나아짐 · 합의 n ≥ 100
                      🧪 = 합의 쪽이 더 좋지만 위 기준 일부 못 미침 · ❌ = 합의 쪽이 단독보다 나쁨
Q10-3 🧬 묶음 한도 — 킥처럼 5칸(한 칸 20%) 모의 운용(📈 gap + ☕ nh, 시장별). 후보 순위 = 20일 수익 높은 순.
  규칙: 새 후보와 이미 든 종목의 60일 하루 수익 상관 > thr 이면 같은 묶음, 묶음 칸 수 ≤ cap 넘으면 그 후보는 건너뜀.
  thr(0.5·0.6·0.7) × cap(1·2) 를 앞 기간에서 고름(샤프 최대, 연수익이 기준 −0.5%p 이상인 것 중).
  판정: ✅ = 시험 기간 샤프 ≥ 기준 · 연수익 ≥ 기준 −0.5%p · (최대낙폭 2%p 이상 덜함 또는 최악의 날 덜함)
        ❌ = 샤프·연수익 모두 기준보다 나쁨 · ➖ = 그 밖
Q10-5 🌡 실패 돌파율 — 미국 gap+nh 사건 중 진입 뒤 5거래일 안에 종가가 돌파선(nh=52주 고가, gap=60일 고가) 아래로
  떨어진 비율. 사건의 결과는 5거래일 뒤에야 알 수 있으므로 그날부터만 셈. 최근 N(20·50·100)건의 실패율이
  지난 1년 평균 + z×표준편차(z 0.5·1·1.5) 를 넘으면 경보 → 뼈대(S&P½+나스닥½) 변동성 목표 15% → tg(12·10%),
  실패율이 1년 평균 아래로 오면 해제. 뼈대 = 주식 × min(1, 목표/20일 변동성), 아래 한도 30%, 5%p 넘게 바뀔 때만,
  덜어낸 몫 현금(^IRX), 바꿀 때 바꾼 양 × 0.1% 비용 · 레버리지 없음.
  판정: ✅ = 시험 기간 샤프 ≥ 기준 + 0.03 · 최대낙폭 기준보다 나쁘지 않음 · 연수익 ≥ 기준 −0.3%p
        ❌ = 샤프 기준보다 낮음 · ➖ = 그 밖
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

AB.START = "2006-06-01"        # 2008 을 앞 기간에 넣으려고 (52주 고가 계산 1년 + 여유)
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q10.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
LEAD = ROOT / "market" / "lab" / "k1013_cust_rows.csv.gz"


# ───────────────────────────── 사건 만들기 ─────────────────────────────
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
        dq = np.array([KI.dq_of(x) for x in dates])
        ev = {"gap": F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (F["o"] > F["ph"]) & (c > F["hi60"]),
              "nh": F["liq"] & F["nh"] & (F["vr"] >= 1.5),
              "pead": F["liq"] & (F["gap"] >= 0.08) & (F["vr"] >= 3) & (dq >= 8) & (dq <= 55)}
        for kind, e in ev.items():
            for ti in np.where(e & (np.arange(n) >= 260))[0]:
                if ti + 1 >= n:
                    continue
                r = dict(tk=t, kind=kind, mkt=m, date=str(dates[ti].date()), ti=int(ti), pre20=None if np.isnan(F["pre20"][ti]) else round(float(F["pre20"][ti]), 2))
                r.update(KI.outcomes(c, F["ma20"], ixa, ti + 1, cost))
                kx = KI.kexit(c, F["ma20"], ti + 1)
                if kx is not None:
                    r["kx_ex"] = str(dates[kx[1]].date())
                # 실패 돌파 (Q10-5): 진입 뒤 5거래일 안 종가 < 돌파선
                if kind in ("gap", "nh") and ti + 5 < n:
                    piv = F["hi252"][ti] if kind == "nh" else F["hi60"][ti]
                    r["fail5"] = int(bool(np.nanmin(c[ti + 1:ti + 6]) < piv))
                    r["known"] = str(dates[ti + 5].date())
                rows.append(r)
    return rows, closes


def lead_rows():
    try:
        d = pd.read_csv(LEAD)
    except Exception:
        return pd.DataFrame()
    d = d[["tk", "date", "ti", "mkt", "r_kk", "x_kk"]].copy()
    d["kind"] = "lead"
    return d


# ───────────────────────────── Q10-2 합의 ─────────────────────────────
def agree_flags(df, W, same_day_pair_as_one):
    """사건마다 지난 W 거래일(약 W×1.45 달력일, 오늘 포함) 안에 같은 종목 다른 종류 신호가 있었는지 (앞을 보지 않음)"""
    cal = np.timedelta64(int(round(W * 1.45)), "D")
    dt_ = pd.to_datetime(df["date"]).to_numpy()
    kd = df["kind"].to_numpy()
    out = np.zeros(len(df), dtype=bool)
    for tk, ix in df.groupby("tk").indices.items():
        ix = ix[np.argsort(dt_[ix], kind="stable")]
        ds, ks = dt_[ix], kd[ix]
        los = np.searchsorted(ds, ds - cal, side="left")
        his = np.searchsorted(ds, ds, side="right")
        for i in range(len(ix)):
            for j in range(los[i], his[i]):
                if j == i or ks[j] == ks[i]:
                    continue
                if same_day_pair_as_one and ds[j] == ds[i] and {ks[i], ks[j]} == {"gap", "nh"}:
                    continue
                out[ix[i]] = True
                break
    return out


def q102(df):
    res = {}
    base = df.dropna(subset=["x_kk"]).copy()
    base = pd.concat([AB.dedupe(g) for _, g in base.groupby("kind")]).reset_index(drop=True)
    flags = {(W, sd): agree_flags(base, W, sd) for W in (5, 10, 20) for sd in (False, True)}
    for mk, mm in (("US", ("US",)), ("KR", ("KR",)), ("US+KR", ("US", "KR"))):
        sel = base["mkt"].isin(mm).to_numpy()
        d0 = base[sel].reset_index(drop=True)
        for defn, sd in (("A", False), ("B", True)):
            grid = {}
            for W in (5, 10, 20):
                d = d0.assign(agree=flags[(W, sd)][sel])
                row = {}
                for pn, s in (("IS", d[(d["date"] >= IS_START) & (d["date"] <= IS_END)]), ("OOS", d[d["date"] >= OOS_START])):
                    a, s1 = s[s["agree"]], s[~s["agree"]]
                    row[pn] = {"agree": KI.evals(a, "kk"), "single": KI.evals(s1, "kk"),
                               "by_kind": {k: {"agree": KI.pst(g[g["agree"]]["x_kk"]), "single": KI.pst(g[~g["agree"]]["x_kk"])}
                                           for k, g in s.groupby("kind")}}
                grid[W] = row
            ok = [(W, r) for W, r in grid.items() if r["IS"]["agree"]["x"].get("n", 0) >= 50]
            E = {"grid": {W: {pn: {"agree_x": r[pn]["agree"]["x"], "single_x": r[pn]["single"]["x"],
                                   "agree_pf": r[pn]["agree"]["r"].get("pf"), "single_pf": r[pn]["single"]["r"].get("pf"),
                                   "by_kind": r[pn]["by_kind"]} for pn in r} for W, r in grid.items()}}
            if not ok:
                E["verdict"], E["why"] = "➖", "앞 기간 합의 표본 50건 미만"
                res[f"{mk}|{defn}"] = E
                continue
            W, r = max(ok, key=lambda g: (g[1]["IS"]["agree"]["x"].get("avg") or -99) - (g[1]["IS"]["single"]["x"].get("avg") or 0))
            o = r["OOS"]
            aa, sa = o["agree"]["x"].get("avg"), o["single"]["x"].get("avg")
            ap, sp = o["agree"]["r"].get("pf") or 0, o["single"]["r"].get("pf") or 0
            an = o["agree"]["x"].get("n", 0)
            ay, sy = o["agree"].get("by_year") or {}, o["single"].get("by_year") or {}
            yrs = [y for y in sy if y in ay]
            better = sum(1 for y in yrs if (ay[y]["x"] or 0) > (sy[y]["x"] or 0))
            if aa is None or sa is None:
                vd = "➖"
            elif aa >= sa + 0.5 and ap >= sp and better * 2 > len(yrs) and an >= 100:
                vd = "✅"
            elif aa > sa:
                vd = "🧪"
            else:
                vd = "❌"
            E.update({"pick_W": W, "verdict": vd,
                      "why": (f"W={W}일 · 시험 기간 합의 {an}건 초과 {aa:+.2f}% 손익비 {ap} vs 단독 {o['single']['x'].get('n')}건 "
                              f"{sa:+.2f}% 손익비 {sp} · 나아진 해 {better}/{len(yrs)}") if aa is not None and sa is not None else "표본 없음",
                      "by_year": {y: {"agree": ay[y], "single": sy[y]} for y in yrs}})
            res[f"{mk}|{defn}"] = E
            print("Q10-2", mk, defn, vd, E["why"], flush=True)
    return res


# ───────────────────────────── 모의 운용 공통 ─────────────────────────────
def pstat(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 20:
        return {}
    nav = (1 + r).cumprod()
    yrs = len(r) / 252
    cagr = nav.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    dd = (nav / nav.cummax() - 1).min()
    yr = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return {"cagr": round(cagr * 100, 2), "vol": round(vol * 100, 2), "sharpe": round(float(r.mean() / r.std() * np.sqrt(252)), 3) if r.std() > 0 else None,
            "mdd": round(dd * 100, 2), "worst_day": round(r.min() * 100, 2), "worst_5d": round(float(r.rolling(5).sum().min()) * 100, 2),
            "worst_yr": round(float(yr.min()) * 100, 2), "yr": {int(k): round(float(v) * 100, 2) for k, v in yr.items()}}


# ───────────────────────────── Q10-3 묶음 한도 ─────────────────────────────
def sim_sleeve(ev, R, cost, thr=None, cap=None, slots=5, lb=60):
    """ev: 진입 후보(신호일·진입일·출구일·종목·순위값) · R: 하루 수익 표(날짜×종목) → 슬리브 하루 수익"""
    dates = R.index
    pos = {}                       # tk -> 출구 날짜
    daily = pd.Series(0.0, index=dates)
    by_entry = {d: g.sort_values("pre20", ascending=False) for d, g in ev.groupby("entry")}
    trades, skipped = 0, 0
    Rv = R.to_numpy()
    col = {t: i for i, t in enumerate(R.columns)}
    for k, d in enumerate(dates):
        # 오늘 하루 수익(어제 종가에 들고 있던 것)
        if pos:
            v = [Rv[k, col[t]] for t in pos if t in col]
            v = [x for x in v if not np.isnan(x)]
            daily.iloc[k] = sum(v) / slots
        # 오늘 종가에 나가기
        out = [t for t, ex in pos.items() if ex <= d]
        for t in out:
            del pos[t]
            daily.iloc[k] -= cost / 2 / slots
        # 오늘 종가에 들어가기
        if d in by_entry:
            for _, c in by_entry[d].iterrows():
                if len(pos) >= slots:
                    break
                t = c["tk"]
                if t in pos or t not in col:
                    continue
                if thr is not None and pos:
                    lo = max(0, k - lb)
                    a = Rv[lo:k, col[t]]
                    same = 0
                    for h in pos:
                        b = Rv[lo:k, col[h]]
                        ok = ~(np.isnan(a) | np.isnan(b))
                        if ok.sum() >= 40 and np.corrcoef(a[ok], b[ok])[0, 1] > thr:
                            same += 1
                    if same >= cap:
                        skipped += 1
                        continue
                pos[t] = pd.Timestamp(c["exit"])
                daily.iloc[k] -= cost / 2 / slots
                trades += 1
    return daily, trades, skipped


def q103(df, closes_by_m):
    res = {}
    for m in ("US", "KR"):
        C = pd.DataFrame(closes_by_m[m]).sort_index()
        C = C[C.index >= "2007-06-01"]
        R = C.pct_change(fill_method=None).clip(-0.5, 1.0)
        cost = AB.COST.get(m, AB.DEF_COST)
        ev = df[(df["mkt"] == m) & df["kind"].isin(["gap", "nh"])].dropna(subset=["kx_ex"]).copy()
        ev = pd.concat([AB.dedupe(g) for _, g in ev.groupby("kind")])
        di = R.index
        pos = di.searchsorted(pd.to_datetime(ev["date"]), side="right")
        ev = ev[pos < len(di)].copy()
        ev["entry"] = di[pos[pos < len(di)]]
        ev["exit"] = pd.to_datetime(ev["kx_ex"])
        ev = ev[ev["entry"] >= IS_START]
        runs = {}
        t0 = time.time()
        base, tr, _ = sim_sleeve(ev, R, cost)
        runs["base"] = {"daily": base, "trades": tr, "skipped": 0}
        for thr in (0.5, 0.6, 0.7):
            for cap in (1, 2):
                d, tr, sk = sim_sleeve(ev, R, cost, thr, cap)
                runs[f"thr{thr}|cap{cap}"] = {"daily": d, "trades": tr, "skipped": sk}
        print("Q10-3 sim", m, round(time.time() - t0), "s", flush=True)
        S = {}
        for k, v in runs.items():
            d = v["daily"]
            S[k] = {"IS": pstat(d[(d.index >= IS_START) & (d.index <= IS_END)]), "OOS": pstat(d[d.index >= OOS_START]),
                    "trades": v["trades"], "skipped": v["skipped"]}
        b = S["base"]
        cand = [k for k in S if k != "base" and S[k]["IS"].get("cagr") is not None and S[k]["IS"]["cagr"] >= b["IS"]["cagr"] - 0.5]
        E = {"runs": S}
        if not cand:
            E["verdict"], E["why"] = "❌", "앞 기간에 기준 연수익 −0.5%p 안에 드는 변형 없음"
        else:
            k = max(cand, key=lambda x: S[x]["IS"]["sharpe"] or -9)
            o, bo = S[k]["OOS"], b["OOS"]
            better_dd = (o["mdd"] - bo["mdd"] >= 2) or (o["worst_day"] > bo["worst_day"])
            if o["sharpe"] >= bo["sharpe"] and o["cagr"] >= bo["cagr"] - 0.5 and better_dd:
                vd = "✅"
            elif o["sharpe"] < bo["sharpe"] and o["cagr"] < bo["cagr"]:
                vd = "❌"
            else:
                vd = "➖"
            E.update({"pick": k, "verdict": vd,
                      "why": (f"고른 것 {k} · 시험 기간 연수익 {o['cagr']}% vs 기준 {bo['cagr']}% · 샤프 {o['sharpe']} vs {bo['sharpe']} · "
                              f"최대낙폭 {o['mdd']}% vs {bo['mdd']}% · 최악의 날 {o['worst_day']}% vs {bo['worst_day']}% · "
                              f"최악의 5일 {o['worst_5d']}% vs {bo['worst_5d']}%")})
        print("Q10-3", m, E.get("verdict"), E.get("why"), flush=True)
        res[m] = E
    return res


# ───────────────────────────── Q10-5 실패 돌파율 ─────────────────────────────
def fail_series(df, N, dates):
    e = df[(df["mkt"] == "US") & df["kind"].isin(["gap", "nh"])].dropna(subset=["fail5"]).copy()
    e = e.sort_values("known")
    e["k"] = pd.to_datetime(e["known"])
    f = e["fail5"].rolling(N, min_periods=N).mean().to_numpy()
    s = pd.Series(f, index=e["k"].to_numpy())
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(dates, method="ffill")


def skel(R2, cash, scale_tg, band=0.05, floor=0.30, lb=20, tc=0.001):
    """R2 = S&P½+나스닥½ 하루 수익 · scale_tg = 날짜별 목표 변동성(%)"""
    vol = R2.rolling(lb).std() * np.sqrt(252) * 100
    raw = np.minimum(1.0, np.maximum(floor, scale_tg / vol)).shift(1)   # 어제까지 정보로 오늘 비중
    held, w = [], 1.0
    for x in raw.to_numpy():
        if not np.isnan(x) and abs(x - w) > band:
            w = x
        held.append(w)
    held = pd.Series(held, index=R2.index)
    turn = held.diff().abs().fillna(0)
    return held * R2 + (1 - held) * cash - turn * tc, held


def q105(df, px):
    spy, qqq, irx = px["SPY"]["close"], px["QQQ"]["close"], px["^IRX"]["close"]
    R2 = (0.5 * spy.pct_change() + 0.5 * qqq.pct_change()).dropna()
    R2 = R2[R2.index >= "2007-06-01"]
    cash = (irx.reindex(R2.index).ffill() / 100 / 252).fillna(0)
    base_tg = pd.Series(15.0, index=R2.index)
    base, _ = skel(R2, cash, base_tg)
    res = {"base": {"IS": pstat(base[(base.index >= IS_START) & (base.index <= IS_END)]), "OOS": pstat(base[base.index >= OOS_START])}}
    grid, alarms = {}, {}
    for N in (20, 50, 100):
        fr = fail_series(df, N, R2.index)
        mu = fr.rolling(252, min_periods=126).mean()
        sd = fr.rolling(252, min_periods=126).std()
        for z in (0.5, 1.0, 1.5):
            on, a = False, []
            for v, m_, s_ in zip(fr.to_numpy(), mu.to_numpy(), sd.to_numpy()):
                if np.isnan(v) or np.isnan(m_) or np.isnan(s_):
                    a.append(False)
                    continue
                if not on and v > m_ + z * s_:
                    on = True
                elif on and v < m_:
                    on = False
                a.append(on)
            al = pd.Series(a, index=R2.index).shift(1).fillna(False).astype(bool)   # 오늘 경보 → 내일부터
            for tg in (12.0, 10.0):
                r, _ = skel(R2, cash, base_tg.where(~al, tg))
                k = f"N{N}|z{z}|tg{int(tg)}"
                grid[k] = {"IS": pstat(r[(r.index >= IS_START) & (r.index <= IS_END)]), "OOS": pstat(r[r.index >= OOS_START]),
                           "alarm_share": round(float(al.mean()) * 100, 1)}
                alarms[k] = al
    b = res["base"]
    k = max(grid, key=lambda x: grid[x]["IS"].get("sharpe") or -9)
    o, bo = grid[k]["OOS"], b["OOS"]
    if o["sharpe"] >= bo["sharpe"] + 0.03 and o["mdd"] >= bo["mdd"] and o["cagr"] >= bo["cagr"] - 0.3:
        vd = "✅"
    elif o["sharpe"] < bo["sharpe"]:
        vd = "❌"
    else:
        vd = "➖"
    al = alarms[k]
    ep = []          # 경보 켜진 구간
    st = None
    for d_, v in al.items():
        if v and st is None:
            st = d_
        if not v and st is not None:
            ep.append([str(st.date()), str(d_.date())])
            st = None
    if st is not None:
        ep.append([str(st.date()), "지금까지"])
    # 손잡이 둔감도: 같은 tg 에서 N·z 바꿔도 시험 기간 샤프가 기준보다 나은 비율
    same_tg = [g for kk, g in grid.items() if kk.endswith(k.split("|")[-1])]
    robust = sum(1 for g in same_tg if (g["OOS"].get("sharpe") or 0) > bo["sharpe"])
    res.update({"grid": grid, "pick": k, "verdict": vd, "episodes": ep[-40:], "robust": f"{robust}/{len(same_tg)}",
                "why": (f"고른 것 {k} · 시험 기간 연수익 {o['cagr']}% vs 기준 {bo['cagr']}% · 샤프 {o['sharpe']} vs {bo['sharpe']} · "
                        f"최대낙폭 {o['mdd']}% vs {bo['mdd']}% · 최악의 해 {o['worst_yr']}% vs {bo['worst_yr']}% · 경보 켜진 날 {grid[k]['alarm_share']}% · "
                        f"같은 목표에서 다른 손잡이도 기준보다 나음 {robust}/{len(same_tg)}")})
    # 지금 상태(마지막 값)
    fr = fail_series(df, int(k.split("|")[0][1:]), R2.index)
    res["now"] = {"rate": round(float(fr.iloc[-1]) * 100, 1) if not np.isnan(fr.iloc[-1]) else None,
                  "mean1y": round(float(fr.rolling(252).mean().iloc[-1]) * 100, 1), "alarm": bool(al.iloc[-1])}
    print("Q10-5", vd, res["why"], res["now"], flush=True)
    return res


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    allrows, closes_by_m = [], {}
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
        del data
    df = pd.DataFrame(allrows)
    lr = lead_rows()
    print("rows", len(df), "lead", len(lr), flush=True)
    df.to_csv(ROOT / "market" / "lab" / "k1014_q10_rows.csv.gz", index=False, compression="gzip")
    try:
        res["q102"] = q102(pd.concat([df, lr], ignore_index=True))
    except Exception as e:
        res["q102_err"] = repr(e)[:300]
        print("q102 err", e, flush=True)
    try:
        res["q103"] = q103(df, closes_by_m)
    except Exception as e:
        res["q103_err"] = repr(e)[:300]
        print("q103 err", e, flush=True)
    try:
        px = KI.ydl(["SPY", "QQQ", "^IRX"], start="2006-06-01")
        res["q105"] = q105(df, px)
    except Exception as e:
        res["q105_err"] = repr(e)[:300]
        print("q105 err", e, flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
