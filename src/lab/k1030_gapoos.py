"""📈 10/30 14시 — Q10/30-1 「업종이 같이 센 갭은 크게」 얼린 규칙의 깨끗한 시험 (12시 다음 회차 계획 ①)
결과 → market/lab/k1030_gapoos.json

얼린 규칙(12시 k1030_gaptilt2 에서 고름, 여기서 다시 고르지 않음): R50_50 = 신호 날 그 종목 GICS 섹터 ETF(XLK·XLF…)의
  50일 수익 순위가 섹터 ETF 중 상위 50% 안이면 크기 1.5배, 밖이면 0.5배(총 투입 같게 맞춘 값 neu 도 계산).
아직 안 본 자료 세 곳(결과 보기 전 정함):
  A. S&P600 작은 종목의 📈 갭 사건 + 지금 눌림 규칙(Q15-5 w3f75) — 사건·진입·출구 = k1030_gaptilt2 와 같음
  B. S&P500+400 ☕ 신고가 돌파(KI.ev_nh · 다음 날 종가 진입 = 지금 킥) — 갭이 아닌 다른 신호
  C. S&P600 ☕ 신고가 돌파 — 다른 신호 × 다른 종목
참고(판정엔 안 씀): ±20% 이웃(L 40·60 × q 40·60).
판정: 세 곳 각각 앞(2008~16)·뒤(2017~) 안−밖 차 > 0 이면 통과. A·B·C 중 둘 이상 앞·뒤 모두 통과 → Q10/30-1 ✅ 올림 /
  하나만 → 🟡 그대로 / 없음 → ❌ 내림.
출구·비용(왕복 0.5%)·초과(S&P500 대비)·20일 재신호 무시 = 기존. 유니버스·섹터 = 오늘 것(생존 편향).
"""
import json, sys, time, io, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

AB.START = "2006-06-01"
AB.TIME_BUDGET = 25 * 60
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1030_gapoos.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
ETF = {"Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV", "Industrials": "XLI",
       "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Utilities": "XLU", "Materials": "XLB",
       "Real Estate": "XLRE", "Communication Services": "XLC"}
VARS = [(50, 50), (40, 40), (40, 60), (60, 40), (60, 60)]   # 첫째가 얼린 규칙
KEYS = [f"R{L}_{q}" for L, q in VARS]


def uni(pages, log, tag):
    import requests
    tk, sec = [], {}
    hd = {"User-Agent": "Mozilla/5.0 (research script)"}
    for pg in pages:
        try:
            r = requests.get(f"https://en.wikipedia.org/wiki/{pg}", headers=hd, timeout=30)
            for t in pd.read_html(io.StringIO(r.text)):
                col = next((x for x in t.columns if str(x).lower() in ("symbol", "ticker symbol", "ticker")), None)
                sc = next((x for x in t.columns if "sector" in str(x).lower()), None)
                if col is not None and len(t) > 300:
                    for s, g in zip(t[col], t[sc] if sc is not None else [None] * len(t)):
                        if pd.isna(s):
                            continue
                        s = str(s).strip().replace(".", "-")
                        tk.append(s)
                        if isinstance(g, str) and g.strip() in ETF:
                            sec[s] = g.strip()
                    break
        except Exception as e:
            log[f"err_{tag}_{pg[-12:]}"] = repr(e)[:150]
    tk = sorted(set(tk))
    log[f"src_{tag}"] = f"{len(tk)} 종목 · 섹터 있음 {len(sec)}"
    return tk, sec


def kx(c, ma20, ixa, e, cost):
    if e >= len(c) - 1:
        return None
    res = KI.kexit(c, ma20, e)
    if res is None:
        return None
    r, ex = res
    if not (ixa[e] > 0 and ixa[ex] > 0):
        return None
    return round((r - cost - (ixa[ex] / ixa[e] - 1)) * 100, 2)


def build(data, idx, sec, rk, kind):
    cost = AB.COST.get("US", AB.DEF_COST)
    _, minp, minvol = AB.MKT["US"]
    rows = []
    for t, d in data.items():
        s = sec.get(t)
        if s is None or len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        o, l, c = F["o"], F["l"], F["c"]
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        if kind == "gap":
            ev = F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (o > F["ph"]) & (c > F["hi60"])
        else:
            ev = F["ev_nh"]
        ef = ETF[s]
        for g in np.where(ev & (np.arange(n) >= 260))[0]:
            if g + 8 >= n:
                continue
            day = dates[g]
            if kind == "gap":
                p0, S = c[g - 1], o[g] - c[g - 1]
                L = p0 + 0.25 * S
                x = None
                for j in range(g + 1, min(g + 3, n - 2) + 1):
                    if c[j] <= p0:
                        break
                    if l[j] <= L and c[j] > p0:
                        x = kx(c, F["ma20"], ixa, j + 1, cost)
                        break
            else:
                x = kx(c, F["ma20"], ixa, g + 1, cost)
            if x is None:
                continue
            row = dict(tk=t, date=str(day.date()), ti=int(g), x=x)
            for (Lb, q), k in zip(VARS, KEYS):
                v = rk[Lb][ef].get(day, np.nan) if ef in rk[Lb] else np.nan
                row[k] = None if pd.isna(v) else bool(v <= q + 1e-9)
            rows.append(row)
    return rows


def pst(x):
    return KI.pst(pd.Series(x, dtype=float).dropna())


def yrs(s):
    return max(1e-9, (pd.Timestamp(s["date"].max()) - pd.Timestamp(s["date"].min())).days / 365.25) if len(s) else 1


def stats(s, col):
    v = s.dropna(subset=[col])
    a, b = v[v[col] == True]["x"], v[v[col] == False]["x"]  # noqa: E712
    y = yrs(s)
    sh = len(a) / max(len(v), 1)
    m = 1.5 * sh + 0.5 * (1 - sh)
    neu = ((1.5 / m - 1) * a.sum() + (0.5 / m - 1) * b.sum()) / y
    return {"in": pst(a), "out": pst(b), "diff": None if len(a) == 0 or len(b) == 0 else round(float(a.mean() - b.mean()), 2),
            "share_in": round(sh * 100, 1), "slot_neu_pp_per_yr": round(float(neu), 2), "kick_neu_pp": round(float(neu) * 0.2, 2),
            "by_year": {yy: [round(float(g[g[col] == True]["x"].mean()), 2) if (g[col] == True).any() else None,
                             round(float(g[g[col] == False]["x"].mean()), 2) if (g[col] == False).any() else None]
                        for yy, g in v.groupby(v["date"].str[:4])}}


def judge(df, name):
    if df.empty:
        return {"err": "no rows"}
    b = AB.dedupe(df).reset_index(drop=True)
    per = {"IS": b[(b["date"] >= IS_START) & (b["date"] <= IS_END)], "OOS": b[b["date"] >= OOS_START]}
    R = {"n": int(len(b)), "all": {pn: pst(s["x"]) for pn, s in per.items()}, "v": {}}
    for k in KEYS:
        R["v"][k] = {pn: stats(s, k) for pn, s in per.items()}
    f = R["v"][KEYS[0]]
    R["pass"] = bool((f["IS"]["diff"] or -99) > 0 and (f["OOS"]["diff"] or -99) > 0)
    R["nb_pos"] = {pn: f"{sum(1 for k in KEYS[1:] if (R['v'][k][pn]['diff'] or -99) > 0)}/4" for pn in per}
    R["why"] = (f"{name} R50_50 안/밖: 앞 {f['IS']['in'].get('n')}/{f['IS']['out'].get('n')}건 차 {f['IS']['diff']}%p · "
                f"뒤 {f['OOS']['in'].get('n')}/{f['OOS']['out'].get('n')}건 차 {f['OOS']['diff']}%p · 뒤 칸 연 {f['OOS']['slot_neu_pp_per_yr']:+}%p(투입 같게) · "
                f"이웃 + 앞 {R['nb_pos']['IS']} 뒤 {R['nb_pos']['OOS']}")
    print(R["why"], flush=True)
    return R


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = res["log"]
    t_big, s_big = uni(("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"), log, "big")
    t_sm, s_sm = uni(("List_of_S%26P_600_companies",), log, "sm")
    idx = AB.idx_series("^GSPC")
    etf = {e: AB.idx_series(e) for e in sorted(set(ETF.values()))}
    E = pd.DataFrame({k: v for k, v in etf.items() if len(v)}).sort_index()
    rk = {L: E.pct_change(L, fill_method=None).rank(axis=1, ascending=False, pct=True) * 100 for L in sorted({v[0] for v in VARS})}
    d_sm = AB.download(t_sm, log, time.time())
    log["sec_sm"] = round(time.time() - t0)
    res["A_sm_gap"] = judge(pd.DataFrame(build(d_sm, idx, s_sm, rk, "gap")), "A S&P600 갭(눌림)")
    res["C_sm_nh"] = judge(pd.DataFrame(build(d_sm, idx, s_sm, rk, "nh")), "C S&P600 신고가")
    del d_sm
    d_big = AB.download(t_big, log, time.time())
    log["sec_big"] = round(time.time() - t0)
    res["B_big_nh"] = judge(pd.DataFrame(build(d_big, idx, s_big, rk, "nh")), "B S&P500+400 신고가")
    np_ = sum(1 for k in ("A_sm_gap", "B_big_nh", "C_sm_nh") if res[k].get("pass"))
    res["verdict"] = "✅" if np_ >= 2 else ("🟡" if np_ == 1 else "❌")
    res["summary"] = f"얼린 R50_50 깨끗한 시험 {np_}/3 통과 → {res['verdict']}"
    print(res["summary"], flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
