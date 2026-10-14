"""📈 Q11-1·3·4 — 과거 검증 (사용자 10/14 11시 보고에 답: "1,3,4 실행")
결과 → market/lab/k1014_q11.json · 판정 기준은 결과 보기 전에 여기 적음.

Q11-1 🎻 합창단 판정 — 🎯 집중의 상승장 판정(S&P500 200일선 위 · 3거래일 확인 = 표 1개)을
  9표(이동평균 150·200·250일 × 확인 1·3·5거래일)로. 「위」 표 k개 → 위험 칸 남기는 비율 = 0.5 + 0.5×k/9
  (기준은 k∈{0,9} 두 단계: 100% / 50%). 고르기 없음(9표 고정) — 3표(150·200·250 × 3일)는 참고.
  뼈대 = skel_bt 「conc」 + 🦴 변동성 맞춤(공격형 20일·22%·아래 70%, 5%p 밴드) 그대로 · 다음 거래일 체결 ·
  매주 + 남기는 비율 바뀐 날 + 배율 바뀐 날 비중 맞춤 · 회전율×0.1% · 현금 BIL · 레버리지 없음.
  참고: ⚡ 킥 기본 칸(C_reg: 금 5% · 판정 꺼지면 위험 칸 74%, 중간형 20일·18%·50%)에도 같은 틀(0.74+0.26×k/9).
  판정(🎯): ✅ = 시험 기간(2017~) skel_bt.judge 통과(샤프 +0.05 & 해마다 한 해 빼도 우위, 또는 낙폭 3%p↑ 개선 …, CAGR −0.5%p 이내)
              그리고 앞 기간(2008-07~2016) 샤프가 기준보다 0.02 넘게 낮지 않음
           🧪 = 시험 기간 샤프 ≥ 기준 & CAGR −0.5%p 이내지만 ✅ 못 미침 · ❌ = 그 밖
Q11-4 ⛏ 원자재 같은 방향 — 미국 📈 gap·☕ nh(컵 대용) 사건표(market/lab/k1014_q10_rows.csv.gz) 중 원자재 회사
  (위키백과 S&P500·400 GICS 세부업종 → 대응 선물: 구리·종합광업·알루미늄·철강 → HG=F · 금 → GC=F ·
   은·귀금속 → SI=F · 석유가스 탐사생산·통합·시추·장비서비스·석탄 → CL=F; 정유·저장운송은 제외)를
  신호일 종가 기준 선물 > 50일선(같은 방향) / 아래(반대)로 나눔. 성적 = x_kk(킥 규칙 출구 지수 초과, 비용 뺌) ·
  같은 종목·같은 신호 20거래일 안 재신호 무시. 50일 고정(20·100일은 참고).
  판정: ✅ = 시험 기간(2017~) 반대 쪽 n ≥ 100 · 반대 쪽 초과 평균 ≤ 같은 쪽 −0.5%p · 반대 쪽 손익비(r) < 같은 쪽 ·
              양쪽 5건↑ 해 중 과반에서 반대 쪽이 나쁨 · 앞 기간(2008~2016)도 같은 방향(반대 < 같은)
           🧪 = 시험 기간 반대 쪽이 더 나쁘지만 위 기준 일부 못 미침 · ❌ = 시험 기간 반대 쪽이 같거나 더 좋음
Q11-3 🐋 13D — SEC 자료가 깃허브 실행기에서 403(k1013_secprobe) → 다시 점검만(머리글 바꿔서 · EDGAR 전체 검색 efts 포함).
"""
import io, json, sys, math, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from src.conc_bt import stats, START, IS_END, OOS_START   # noqa: E402
from src.skel_bt import sticky, realized_vol, summ, judge   # noqa: E402
from src.rules7 import hold_band, VOL_ROLES               # noqa: E402
import accum_bt as AB                                     # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q11.json"
COST = 0.001
res = {"made": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")}


# ───────────────────────── Q11-1 ─────────────────────────
def sim(C, R, keep, scale, eqw, gdw, a, b):
    idx = C.index
    sel = np.where((idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b)))[0]
    wk = idx.isocalendar().week.values

    def tgt(i):
        e = eqw * keep[i] * scale[i]; g = gdw * keep[i]
        return np.array([e / 2, e / 2, g, 1 - e - g])
    w = tgt(sel[0]); val = 1 - COST * float(w[:3].sum()); pend = None; turn = 0.0
    last = (wk[sel[0]], keep[sel[0]], scale[sel[0]]); nav = np.empty(len(sel)); chg = 0; eqs = []
    for j, i in enumerate(sel):
        if j > 0:
            r = R[i]; val *= 1 + float(w @ r); gw = w * (1 + r); s_ = gw.sum()
            if s_ > 0:
                w = gw / s_
        if pend is not None:
            t = float(np.abs(pend - w).sum()); turn += t; val *= 1 - t * COST; w = pend; pend = None
        nav[j] = val
        eqs.append(w[0] + w[1])
        if keep[i] != last[1]:
            chg += 1
        if wk[i] != last[0] or keep[i] != last[1] or scale[i] != last[2]:
            pend = tgt(i); last = (wk[i], keep[i], scale[i])
    d = idx[sel]; yrs = max(0.5, (d[-1] - d[0]).days / 365.25)
    return pd.Series(nav, index=d), round(turn / yrs * 100), round(chg / yrs, 1), round(float(np.mean(eqs)) * 100, 1)


def q111():
    import yfinance as yf
    tick = ["SPY", "QQQ", "GLD", "BIL", "^GSPC"]
    df = yf.download(tick, start="2005-01-01", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick}).dropna(subset=["SPY", "QQQ", "GLD"]).ffill(limit=5)
    C["BIL"] = C["BIL"].ffill()
    R = C[["SPY", "QQQ", "GLD", "BIL"]].pct_change().fillna(0.0).values
    gs = C["^GSPC"].ffill()
    votes = {(L, k): sticky(gs > gs.rolling(L).mean(), k).values.astype(float) for L in (150, 200, 250) for k in (1, 3, 5)}
    f1 = votes[(200, 3)]
    f9 = np.mean([v for v in votes.values()], axis=0)
    f3 = np.mean([votes[(L, 3)] for L in (150, 200, 250)], axis=0)
    end = C.index[-1]; PER = (("is", START, IS_END), ("oos", OOS_START, end)); spy = C["SPY"]
    out = {"now": {"date": str(end.date()), "votes_up": int(round(f9[-1] * 9)), "detail": {f"{L}d·{k}일": bool(v[-1]) for (L, k), v in votes.items()},
                   "gspc": round(float(gs.iloc[-1]), 1), **{f"ma{L}": round(float(gs.rolling(L).mean().iloc[-1]), 1) for L in (150, 200, 250)}}}
    for sk, eqw, gdw, off, role in (("conc", 1.0, 0.0, 0.5, "conc"), ("C_reg", 0.95, 0.05, 0.74, "kick")):
        p = VOL_ROLES[role]
        raw = np.clip(p["target"] / 100 / realized_vol(C, p["lb"]).bfill().values, p["floor"], 1.0)
        sc = np.array(hold_band(list(raw)))
        o = {}; navs = {}
        for nm, f in (("base", f1), ("v9", f9), ("v3", f3)):
            keep = np.round(off + (1 - off) * f, 4)
            o[nm] = {}
            for pn, a, b in PER:
                nav, t, fl, eqm = sim(C, R, keep, sc, eqw, gdw, a, b)
                s = summ(nav, spy); s.update(turn=t, keep_changes_per_yr=fl, eq_avg=eqm)
                o[nm][pn] = s; navs[(nm, pn)] = nav
        for nm in ("v9", "v3"):
            jg = judge(o[nm]["oos"], o["base"]["oos"], navs[(nm, "oos")], navs[("base", "oos")])
            o[nm]["judge"] = jg
            is_ok = (o[nm]["is"]["sharpe"] or 0) >= (o["base"]["is"]["sharpe"] or 0) - 0.02
            soft = (o[nm]["oos"]["sharpe"] or 0) >= (o["base"]["oos"]["sharpe"] or 0) and jg["cagr_ok"]
            o[nm]["verdict"] = "✅" if (jg["pass"] and is_ok) else ("🧪" if soft else "❌")
        out[sk] = o
        for nm in ("base", "v9", "v3"):
            print("Q111", sk, nm, {pn: {x: o[nm][pn][x] for x in ("cagr", "sharpe", "mdd", "turn", "keep_changes_per_yr")} for pn in ("is", "oos")}, o[nm].get("verdict"))
    return out


# ───────────────────────── Q11-4 ─────────────────────────
CMAP = {"Copper": "HG=F", "Diversified Metals & Mining": "HG=F", "Aluminum": "HG=F", "Steel": "HG=F",
        "Gold": "GC=F", "Silver": "SI=F", "Precious Metals & Minerals": "SI=F",
        "Oil & Gas Exploration & Production": "CL=F", "Integrated Oil & Gas": "CL=F", "Oil & Gas Drilling": "CL=F",
        "Oil & Gas Equipment & Services": "CL=F", "Coal & Consumable Fuels": "CL=F"}


def gics():
    import requests
    hd = {"User-Agent": "Mozilla/5.0 (research script)"}; m = {}
    for pg in ("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"):
        r = requests.get(f"https://en.wikipedia.org/wiki/{pg}", headers=hd, timeout=30)
        for t in pd.read_html(io.StringIO(r.text)):
            cols = [str(c) for c in t.columns]
            sc = next((c for c in t.columns if str(c).lower() in ("symbol", "ticker symbol", "ticker")), None)
            sub = next((c for c in t.columns if "sub-industry" in str(c).lower() or "sub industry" in str(c).lower()), None)
            if sc is not None and sub is not None and len(t) > 300:
                for s, u in zip(t[sc], t[sub]):
                    m[str(s).strip().replace(".", "-")] = str(u).strip()
                break
    return m


def grp(d):
    s = AB.pstats(d["x_kk"]); r = AB.pstats(d["r_kk"])
    return {"n": s.get("n", 0), "x": s.get("avg"), "x_med": s.get("med"), "win": s.get("win"), "pf_r": r.get("pf"), "r": r.get("avg")}


def q114():
    import yfinance as yf
    sub = gics()
    rows = pd.read_csv(ROOT / "market" / "lab" / "k1014_q10_rows.csv.gz", dtype={"tk": str})
    rows = rows[(rows.mkt == "US") & rows.kind.isin(["gap", "nh"])]
    rows = pd.concat([AB.dedupe(g) for _, g in rows.groupby("kind")])
    rows["sub"] = rows.tk.map(sub)
    rows["fut"] = rows["sub"].map(CMAP)
    rows["date"] = pd.to_datetime(rows["date"])
    F = yf.download(sorted(set(CMAP.values())), start="2005-01-01", auto_adjust=True, progress=False, group_by="ticker")
    above = {}
    for f in set(CMAP.values()):
        c = F[f]["Close"].dropna()
        above[f] = {L: (c > c.rolling(L).mean()).astype(float).where(c.rolling(L).mean().notna()) for L in (20, 50, 100)}
    cm = rows[rows.fut.notna()].copy()
    for L in (20, 50, 100):
        cm[f"up{L}"] = [above[f][L].asof(d) if d >= above[f][L].index[0] else np.nan for f, d in zip(cm.fut, cm.date)]
    cm["per"] = np.where(cm.date <= pd.Timestamp(IS_END), "is", "oos")
    cm = cm[cm.date >= pd.Timestamp("2008-01-01")]
    non = rows[rows.fut.isna() & (rows.date >= pd.Timestamp("2008-01-01"))].copy()
    non["per"] = np.where(non.date <= pd.Timestamp(IS_END), "is", "oos")
    out = {"n_sub_mapped": int(rows["sub"].notna().sum()), "n_rows": int(len(rows)),
           "commodity_tickers": sorted(cm.tk.unique().tolist()), "by_fut": cm.fut.value_counts().to_dict(), "res": {}}
    for L in (20, 50, 100):
        o = {}
        for pn in ("is", "oos"):
            d = cm[cm.per == pn]
            o[pn] = {"with": grp(d[d[f"up{L}"] == 1]), "against": grp(d[d[f"up{L}"] == 0]),
                     "all_commodity": grp(d), "non_commodity": grp(non[non.per == pn])}
            o[pn]["by_kind"] = {k: {"with": grp(d[(d.kind == k) & (d[f"up{L}"] == 1)]), "against": grp(d[(d.kind == k) & (d[f"up{L}"] == 0)])} for k in ("gap", "nh")}
            o[pn]["by_fut"] = {f: {"with": grp(d[(d.fut == f) & (d[f"up{L}"] == 1)]), "against": grp(d[(d.fut == f) & (d[f"up{L}"] == 0)])} for f in sorted(d.fut.unique())}
        yrs = {}
        d = cm[cm.per == "oos"]
        for y, g in d.groupby(d.date.dt.year):
            w_, a_ = g[g[f"up{L}"] == 1].x_kk, g[g[f"up{L}"] == 0].x_kk
            yrs[str(y)] = {"with": [len(w_), round(float(w_.mean()), 2) if len(w_) else None], "against": [len(a_), round(float(a_.mean()), 2) if len(a_) else None]}
        o["oos_years"] = yrs
        W, A = o["oos"]["with"], o["oos"]["against"]
        ev = [v for v in yrs.values() if v["with"][0] >= 5 and v["against"][0] >= 5]
        worse = sum(1 for v in ev if v["against"][1] < v["with"][1])
        o["years_against_worse"] = [worse, len(ev)]
        if A["n"] and W["n"] and A["x"] is not None and W["x"] is not None:
            is_dir = (o["is"]["against"]["x"] or 0) < (o["is"]["with"]["x"] or 0)
            ok = (A["n"] >= 100 and A["x"] <= W["x"] - 0.5 and (A["pf_r"] or 0) < (W["pf_r"] or 0) and worse * 2 > len(ev) and is_dir)
            o["verdict"] = "✅" if ok else ("🧪" if A["x"] < W["x"] else "❌")
        else:
            o["verdict"] = "❌"
        out["res"][str(L)] = o
        print("Q114", L, "IS", o["is"]["with"], o["is"]["against"], "| OOS", W, A, "years", o["years_against_worse"], o["verdict"])
    out["verdict"] = out["res"]["50"]["verdict"]
    # 오늘 상태
    out["now"] = {f: {"close": round(float(F[f]["Close"].dropna().iloc[-1]), 2), "ma50": round(float(F[f]["Close"].dropna().rolling(50).mean().iloc[-1]), 2),
                      "up50": bool(above[f][50].dropna().iloc[-1] == 1)} for f in set(CMAP.values())}
    out["now"]["TECK_2026-10-02"] = {"HG=F_up50": float(above["HG=F"][50].asof(pd.Timestamp("2026-10-02")))}
    return out


# ───────────────────────── Q11-3 점검 ─────────────────────────
def q113():
    import requests
    U = ["https://www.sec.gov/Archives/edgar/full-index/2020/QTR1/form.idx",
         "https://efts.sec.gov/LATEST/search-index?q=%22SC%2013D%22&forms=SC%2013D&dateRange=custom&startdt=2024-01-01&enddt=2024-01-31",
         "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+13D&count=40&output=atom"]
    UAS = ["CHInvesting Research Bot (contact via github.com/chkchp0702-spec)", "python-requests/2.32", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"]
    out = []
    for u in U:
        for ua in UAS:
            try:
                r = requests.get(u, headers={"User-Agent": ua, "Accept": "*/*"}, timeout=30)
                out.append({"u": u[:80], "ua": ua[:25], "code": r.status_code, "head": r.text[:120]})
            except Exception as e:
                out.append({"u": u[:80], "ua": ua[:25], "err": repr(e)[:120]})
            time.sleep(0.5)
    print("Q113", [(x["u"][:40], x.get("code")) for x in out])
    return {"probe": out, "ok": any(x.get("code") == 200 for x in out)}


for k, fn in (("q111", q111), ("q114", q114), ("q113", q113)):
    t0 = time.time()
    try:
        res[k] = fn()
    except Exception as e:
        import traceback; traceback.print_exc()
        res[k] = {"err": repr(e)[:300]}
    res[k + "_sec"] = round(time.time() - t0)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("done")
