"""📈 10/30 12시 (둘째) — k1030_gaptilt 의 S63_4(섹터 ETF 63일 수익 4위 안) 가 앞·뒤 + 였지만 이웃 판(S63_3·S126_4)이 흔들려 ±20% 격자로 다시 잼.
격자(결과 보기 전 정함): 섹터 ETF L일 수익 백분위 순위 ≤ q% (L ∈ 42·50·63·76·84, q ∈ 30·40·50) → 15판. 지표 셋: 1.5/0.5 기울이기 · 총 투입 같게 맞춘 기울이기(neu) · 밖 갭 안 사기(skip).
(아래는 첫 실험 설명)
📈 10/30 12시 — ⚡ 킥 📈 돌파 갭: 「무엇을 사나」 쪽 크기 기울이기 (10시 다음 회차 계획 ①)
결과 → market/lab/k1030_gaptilt.json

왜: 진입 시점(10시 gaphold·retest)은 지금 눌림 규칙(Q15-5 w3f75)이 최선으로 닫힘. 이제 「어떤 갭이 더 이어지나」.
발상 출처: ① 업종 정보는 천천히 퍼지고(Moskowitz-Grinblatt 업종 모멘텀) 혼자 튄 종목 뉴스는 되돌아간다는 갈래
  ② 생산 보완 업종 사이 정보 전달(J. Fin. Econ 2024 「Production complementarity and information transmission across industries」)
  ③ HKUST 「synchronized stock returns」(같이 움직인 종목 수익은 다르게 이어짐) → 「동료도 같이 뛴 갭 = 업종 뉴스」 vs 「혼자 뛴 갭」
틀 = k1030_gaphold 와 같음: 사건(갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가) · 출구 = 킥 규칙 · 왕복 0.5% · 초과 = S&P500 대비
  · 같은 종목 20일 재신호 무시 · 앞 2008~2016 고르고 뒤 2017~ 시험 · 유니버스 = 오늘 S&P500+400 · 섹터 = 오늘 GICS 섹터
  (생존 편향 + 섹터 분류도 오늘 것 — 결과가 실제보다 좋게 나올 수 있음)
나누는 잣대(결과 보기 전 정함, 갭 날 g 종가까지 자료만):
  S{L}_{K}: 그 종목 섹터 ETF(XLK·XLF…)의 L일 수익 순위가 섹터 ETF 중 K위 안 — L ∈ {63,126}, K ∈ {3,4}
  P{T}: 갭 날 섹터 ETF 하루 수익 − S&P500 하루 수익 ≥ T%  (업종이 같이 뜀) — T ∈ {0.5, 1.0}
  N{m}: 같은 날 같은 섹터 다른 종목 중 시가 갭 ≥ 3% 인 수 ≥ m — m ∈ {2, 4}
  → 8판. 각 판에서 「안(in)」 갭은 크기 1.5배 · 「밖」 0.5배로 기울였을 때 갭 칸 연간 초과 합의 변화 = 0.5 × (안 합 − 밖 합)/년.
대상: (가) 지금 규칙이 실제로 사는 갭(눌림 w3f75 「in」) (나) 참고: 갭 전체(다음 날 종가 진입).
킥 칸 영향: 킥 한 칸 = 킥 슬리브의 20% → 킥 연수익 변화 ≈ 0.2 × 연간 초과 합 변화(%p) — 칸이 차 있으면 못 사니 상한.
판정 ✅: 앞에서 고른 판(안 n≥30)이 뒤에서 안−밖 평균 차 > 0 · 킥 연 +1%p 이상 · 앞도 + · 같은 갈래 8판 중 뒤 + ≥ 6.
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
AB.TIME_BUDGET = 22 * 60
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1030_gaptilt2.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
ETF = {"Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV", "Industrials": "XLI",
       "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Utilities": "XLU", "Materials": "XLB",
       "Real Estate": "XLRE", "Communication Services": "XLC"}
LS = (42, 50, 63, 76, 84)
QS = (30, 40, 50)
SPLITS = [f"R{L}_{q}" for L in LS for q in QS]


def uni(log):
    import requests
    tk, sec = [], {}
    hd = {"User-Agent": "Mozilla/5.0 (research script)"}
    for pg in ("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"):
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
            log[f"err_{pg[-12:]}"] = repr(e)[:150]
    tk = sorted(set(tk))
    log["us_source"] = f"S&P500+400 {len(tk)} · 섹터 있음 {len(sec)}"
    return tk, sec


def kx(c, ma20, ixa, e, cost):
    if e >= len(c) - 1:
        return None, None
    res = KI.kexit(c, ma20, e)
    if res is None:
        return None, None
    r, ex = res
    x = (r - cost - (ixa[ex] / ixa[e] - 1)) * 100 if ixa[e] > 0 and ixa[ex] > 0 else None
    return round((r - cost) * 100, 2), (None if x is None else round(x, 2))


def build(data, idx, sec, etf):
    cost = AB.COST.get("US", AB.DEF_COST)
    _, minp, minvol = AB.MKT["US"]
    # 섹터별 날짜별 갭 ≥3% 종목 수
    gapcnt = {}
    for t, d in data.items():
        s = sec.get(t)
        if s is None or len(d) < 320:
            continue
        g = (d["open"] / d["close"].shift(1) - 1) >= 0.03
        for day in d.index[g.fillna(False).to_numpy()]:
            gapcnt[(s, day)] = gapcnt.get((s, day), 0) + 1
    # 섹터 ETF 순위·하루 초과
    E = pd.DataFrame(etf).sort_index()
    rk = {L: E.pct_change(L, fill_method=None).rank(axis=1, ascending=False, pct=True) * 100 for L in LS}
    ex1 = E.pct_change(fill_method=None).sub(idx.reindex(E.index).pct_change(fill_method=None), axis=0) * 100
    rows = []
    for t, d in data.items():
        s = sec.get(t)
        if s is None or len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        o, h, l, c = F["o"], F["h"], F["l"], F["c"]
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        ev = F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (o > F["ph"]) & (c > F["hi60"])
        ef = ETF[s]
        for g in np.where(ev & (np.arange(n) >= 260))[0]:
            if g + 8 >= n:
                continue
            day = dates[g]
            p0, S = c[g - 1], o[g] - c[g - 1]
            r0, x0 = kx(c, F["ma20"], ixa, g + 1, cost)
            if r0 is None:
                continue
            row = dict(tk=t, date=str(day.date()), ti=int(g), sec=s, r_b=r0, x_b=x0)
            L = p0 + 0.25 * S
            st = "skip"
            for j in range(g + 1, min(g + 3, n - 2) + 1):
                if c[j] <= p0:
                    st = "cancel"
                    break
                if l[j] <= L and c[j] > p0:
                    st = "in"
                    row["r_p"], row["x_p"] = kx(c, F["ma20"], ixa, j + 1, cost)
                    break
            row["s_p"] = st
            for Lb in LS:
                v = rk[Lb][ef].get(day, np.nan) if ef in rk[Lb] else np.nan
                for q in QS:
                    row[f"R{Lb}_{q}"] = None if pd.isna(v) else bool(v <= q + 1e-9)
            rows.append(row)
    return rows


def pst(x):
    return KI.pst(pd.Series(x, dtype=float).dropna())


def yrs_of(s):
    return max(1e-9, (pd.Timestamp(s["date"].max()) - pd.Timestamp(s["date"].min())).days / 365.25) if len(s) else 1


def split_stats(s, col, xcol):
    v = s.dropna(subset=[col, xcol])
    a, b = v[v[col] == True][xcol], v[v[col] == False][xcol]  # noqa: E712
    y = yrs_of(s)
    gain = 0.5 * (a.sum() - b.sum()) / y   # 1.5/0.5 기울이기 → 연간 초과 합 변화
    sh = len(a) / max(len(v), 1)
    m = 1.5 * sh + 0.5 * (1 - sh)
    neu = ((1.5 / m - 1) * a.sum() + (0.5 / m - 1) * b.sum()) / y   # 총 투입 같게 맞춘 기울이기
    skip = -b.sum() / y                                              # 밖 갭은 안 삼(칸 비움)
    return {"in": pst(a), "out": pst(b), "diff": None if len(a) == 0 or len(b) == 0 else round(float(a.mean() - b.mean()), 2),
            "share_in": round(len(a) / max(len(v), 1) * 100, 1), "yr_gain": round(float(gain), 2), "kick_pp": round(float(gain) * 0.2, 2),
            "neu_kick_pp": round(float(neu) * 0.2, 2), "skip_kick_pp": round(float(skip) * 0.2, 2),
            "oos_by_year": {yy: [round(float(g[g[col] == True][xcol].mean()), 2) if (g[col] == True).any() else None, round(float(g[g[col] == False][xcol].mean()), 2) if (g[col] == False).any() else None] for yy, g in v.groupby(v["date"].str[:4])}}


def judge(df):
    b = AB.dedupe(df).reset_index(drop=True)
    per = {"IS": b[(b["date"] >= IS_START) & (b["date"] <= IS_END)], "OOS": b[b["date"] >= OOS_START]}
    R = {"n": int(len(b)), "pull": {}, "base": {}, "pull_all": {}}
    for pn, s in per.items():
        pin = s[s["s_p"] == "in"]
        R["pull_all"][pn] = {"x": pst(pin["x_p"]), "yr_sum": round(float(pin["x_p"].dropna().sum()) / yrs_of(s), 2)}
    for k in SPLITS:
        R["pull"][k], R["base"][k] = {}, {}
        for pn, s in per.items():
            pin = s[s["s_p"] == "in"].copy()
            pin.loc[:, "date"] = pin["date"]
            st = split_stats(pin, k, "x_p")
            st["yr_gain"] = round(st["yr_gain"] * yrs_of(pin) / yrs_of(s), 2)
            sc = yrs_of(pin) / yrs_of(s)
            st["kick_pp"] = round(st["yr_gain"] * 0.2, 2)
            st["neu_kick_pp"] = round(st["neu_kick_pp"] * sc, 2)
            st["skip_kick_pp"] = round(st["skip_kick_pp"] * sc, 2)
            R["pull"][k][pn] = st
            R["base"][k][pn] = split_stats(s, k, "x_b")
    cand = [k for k in SPLITS if R["pull"][k]["IS"]["in"].get("n", 0) >= 30 and R["pull"][k]["IS"]["diff"] is not None]
    pick = max(cand, key=lambda k: R["pull"][k]["IS"]["diff"]) if cand else None
    R["pick"] = pick
    pos = sum(1 for k in SPLITS if (R["pull"][k]["OOS"]["diff"] or -99) > 0)
    posi = sum(1 for k in SPLITS if (R["pull"][k]["IS"]["diff"] or -99) > 0)
    R["robust_pull_is_pos"] = f"{posi}/{len(SPLITS)}"
    posb = sum(1 for k in SPLITS if (R["base"][k]["OOS"]["diff"] or -99) > 0)
    R["robust_pull_oos_pos"], R["robust_base_oos_pos"] = f"{pos}/{len(SPLITS)}", f"{posb}/{len(SPLITS)}"
    if pick:
        p = R["pull"][pick]
        ok = (p["OOS"]["diff"] or -99) > 0 and (p["IS"]["diff"] or -99) > 0 and p["OOS"]["neu_kick_pp"] >= 1.0 and pos >= 12 and posi >= 12
        near = (p["OOS"]["diff"] or -99) > 0 and p["OOS"]["neu_kick_pp"] >= 0.33
        R["verdict"] = "✅" if ok else ("🟡" if near else "❌")
        R["why"] = (f"{pick} · 눌림 규칙 산 갭 안/밖: 앞 {p['IS']['in'].get('n')}/{p['IS']['out'].get('n')}건 차 {p['IS']['diff']}%p · "
                    f"뒤 {p['OOS']['in'].get('n')}/{p['OOS']['out'].get('n')}건 차 {p['OOS']['diff']}%p · 기울이면(투입 같게) 킥 연 {p['OOS']['neu_kick_pp']:+}%p(뒤) · 밖 안 사기 {p['OOS']['skip_kick_pp']:+}%p · 앞+ {R['robust_pull_is_pos']} · "
                    f"15판 뒤 + {R['robust_pull_oos_pos']} · 갭 전체 기준 뒤 + {R['robust_base_oos_pos']}")
    print("gaptilt2", R.get("verdict"), R.get("why"), flush=True)
    return R


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = {}
    tks, sec = uni(log)
    idx = AB.idx_series("^GSPC")
    etf = {}
    for e in sorted(set(ETF.values())):
        s = AB.idx_series(e)
        if len(s):
            etf[e] = s
    log["etf"] = {k: str(v.index[0].date()) for k, v in etf.items()}
    data = AB.download(tks, log, time.time())
    log["sec"] = round(time.time() - t0)
    res["log"] = log
    print(json.dumps(log, ensure_ascii=False)[:800], flush=True)
    df = pd.DataFrame(build(data, idx, sec, etf))
    print("rows", len(df), flush=True)
    try:
        res["r"] = judge(df)
    except Exception:
        import traceback
        res["err"] = traceback.format_exc()[-1200:]
        print(res["err"], flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
