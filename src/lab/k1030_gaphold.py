"""📈 10/30 10시 — ⚡ 킥 🌱/📈 미국 돌파 갭 진입: 「갭 첫날 저가를 지킨 둘째 날」 (10/29 16시 다음 회차 계획 ①)
결과 → market/lab/k1030_gaphold.json

왜: 킥 정직 성적의 가장 큰 구멍 = 📈 돌파 갭(다음 날 종가 진입 37건 평균 −0.5% · PF 0.72).
지금 규칙(Q15-5 ✅ w3f75): 갭 뒤 3일 안 갭의 75% 자리까지 눌렸다 갭 위 종가로 버티면 다음 날 종가 진입 — 갭의 약 14% 만 삼, 나머지 86% 는 건너뜀.
질문: 건너뛴 86% 중 「눌림이 안 오고 갭 첫날 저가를 지킨」 강한 갭을 따로 사면 낫나? (브레이크어웨이 갭 「첫날 저가 = 손절선」 실전 규칙, nasdaq 2026 기사·트레이더 유튜브)

공통 틀 = k1014_q15g 와 같음: 출구 = 킥 규칙(KI.kexit) · 왕복 0.5% · 초과 = 같은 기간 S&P500 대비 · 같은 종목 20거래일 재신호 무시
  · 앞 2008~2016 고르고 뒤 2017~ 시험 · 유니버스 = 오늘 S&P500+400(생존 편향: 오늘 살아 있는 종목만 — 결과가 실제보다 좋게 나올 수 있음)
사건(g): 시가 갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가 (Q15g 와 같음).
변형(결과 보기 전 정함):
  hold_k{K}_t{T}: g+1 … g+K 거래일 모두 저가 ≥ 갭 날 저가 × (1 − T%) 이고 g+K 종가 > 갭 날 시가의 반(=P0 + S/2) → g+K+1 종가 진입(정직)
                  (참고: g+K 종가 진입 j 판도 셈). K ∈ {1,2}, T ∈ {0, 1, 2}  → 6판
  pull = 지금 규칙 w3f75 (비교용)
  combo_k{K}_t{T}: 지금 눌림 규칙이 사면 그대로, 눌림 규칙이 건너뛴(skip, cancel 아닌) 사건 중 hold 조건 맞는 것 추가 → 킥 갭 칸이 「더 사는」 판
판정: ✅ = 앞에서 고른 hold 판이 뒤에서 초과 평균 > 0 · 손익비 ≥ 1.2 · n ≥ 100 · combo 의 뒤 「연간 초과 합(건수×평균)」이 지금 규칙보다 + · 앞도 + · 흔들기(6판) 중 뒤 + ≥ 4.
킥 칸 영향 근사: 킥 칸 15% · 5칸 → 한 건 = 포트 3%. 연간 초과 합 × 3% … 실제 킥은 칸이 차 있으면 못 사니 상한값.
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
OUT = ROOT / "market" / "lab" / "k1030_gaphold.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
HG = [(k, t) for k in (1, 2) for t in (0, 1, 2)]


def uni(log):
    import requests
    tk = []
    hd = {"User-Agent": "Mozilla/5.0 (research script)"}
    for pg in ("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"):
        try:
            r = requests.get(f"https://en.wikipedia.org/wiki/{pg}", headers=hd, timeout=30)
            for t in pd.read_html(io.StringIO(r.text)):
                col = next((x for x in t.columns if str(x).lower() in ("symbol", "ticker symbol", "ticker")), None)
                if col is not None and len(t) > 300:
                    tk += [str(s).strip().replace(".", "-") for s in t[col].dropna()]
                    break
        except Exception as e:
            log[f"err_{pg[-12:]}"] = repr(e)[:150]
    tk = sorted(set(tk))
    if len(tk) < 500:
        tk = AB.US_FALLBACK.split() if isinstance(AB.US_FALLBACK, str) else list(AB.US_FALLBACK)
    log["us_source"] = f"S&P500+400 {len(tk)}"
    return tk


def kx(c, ma20, ixa, e, cost):
    if e >= len(c) - 1:
        return None, None
    res = KI.kexit(c, ma20, e)
    if res is None:
        return None, None
    r, ex = res
    x = (r - cost - (ixa[ex] / ixa[e] - 1)) * 100 if ixa[e] > 0 and ixa[ex] > 0 else None
    return round((r - cost) * 100, 2), (None if x is None else round(x, 2))


def build(data, idx):
    cost = AB.COST.get("US", AB.DEF_COST)
    _, minp, minvol = AB.MKT["US"]
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        o, h, l, c = F["o"], F["h"], F["l"], F["c"]
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        ev = F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (o > F["ph"]) & (c > F["hi60"])
        for g in np.where(ev & (np.arange(n) >= 260))[0]:
            if g + 8 >= n:
                continue
            p0, S = c[g - 1], o[g] - c[g - 1]
            r0, x0 = kx(c, F["ma20"], ixa, g + 1, cost)
            if r0 is None:
                continue
            row = dict(tk=t, date=str(dates[g].date()), ti=int(g), r_b=r0, x_b=x0)
            # 지금 규칙 w3f75
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
            for K, T in HG:
                key = f"k{K}t{T}"
                ok = all(l[j] >= l[g] * (1 - T / 100) for j in range(g + 1, g + K + 1)) and c[g + K] > p0 + S / 2
                row[f"h_{key}"] = bool(ok)
                if ok:
                    row[f"r_{key}"], row[f"x_{key}"] = kx(c, F["ma20"], ixa, g + K + 1, cost)
                    row[f"rj_{key}"], row[f"xj_{key}"] = kx(c, F["ma20"], ixa, g + K, cost)
            rows.append(row)
    return rows


def pst(x):
    return KI.pst(pd.Series(x, dtype=float).dropna())


def yr_sum(s, col):
    g = s.dropna(subset=[col])
    yrs = max(1e-9, (pd.Timestamp(s["date"].max()) - pd.Timestamp(s["date"].min())).days / 365.25) if len(s) else 1
    return round(float(g[col].sum()) / yrs, 2), round(len(g) / yrs, 1)


def judge(df):
    b = AB.dedupe(df).reset_index(drop=True)
    per = {"IS": b[(b["date"] >= IS_START) & (b["date"] <= IS_END)], "OOS": b[b["date"] >= OOS_START]}
    E = {"n": int(len(b)), "base": {}, "pull": {}, "hold": {}, "combo": {}, "by_year": {}}
    for pn, s in per.items():
        E["base"][pn] = {"x": pst(s["x_b"]), "r": pst(s["r_b"]), "yr": yr_sum(s, "x_b")}
        pin = s[s["s_p"] == "in"]
        E["pull"][pn] = {"x": pst(pin["x_p"]), "r": pst(pin["r_p"])}
        E["pull"][pn]["yr"] = (round(float(pin["x_p"].dropna().sum()) / ((pd.Timestamp(s["date"].max()) - pd.Timestamp(s["date"].min())).days / 365.25), 2), round(len(pin) / ((pd.Timestamp(s["date"].max()) - pd.Timestamp(s["date"].min())).days / 365.25), 1))
    for K, T in HG:
        k = f"k{K}t{T}"
        H, C = {}, {}
        for pn, s in per.items():
            yrs = (pd.Timestamp(s["date"].max()) - pd.Timestamp(s["date"].min())).days / 365.25
            hin = s[s[f"h_{k}"] == True]  # noqa: E712
            add = s[(s["s_p"] == "skip") & (s[f"h_{k}"] == True)]  # noqa: E712
            H[pn] = {"x": pst(hin[f"x_{k}"]), "r": pst(hin[f"r_{k}"]), "xj": pst(hin[f"xj_{k}"]), "take": round(len(hin) / max(len(s), 1) * 100, 1),
                     "same_ev_base_x": pst(hin["x_b"]), "overlap_pull": int((hin["s_p"] == "in").sum())}
            pin = s[s["s_p"] == "in"]
            cx = pd.concat([pin["x_p"], add[f"x_{k}"]]).dropna()
            cr = pd.concat([pin["r_p"], add[f"r_{k}"]]).dropna()
            C[pn] = {"x": pst(cx), "r": pst(cr), "add": pst(add[f"x_{k}"]), "add_r": pst(add[f"r_{k}"]),
                     "yr_sum": round(float(cx.sum()) / yrs, 2), "yr_n": round(len(cx) / yrs, 1),
                     "pull_yr_sum": round(float(pin["x_p"].dropna().sum()) / yrs, 2)}
            if pn == "OOS":
                E["by_year"][k] = {y: round(float(v.mean()), 2) for y, v in add.dropna(subset=[f"x_{k}"]).groupby(add["date"].str[:4])[f"x_{k}"]}
        E["hold"][k], E["combo"][k] = H, C
    cand = [k for k in E["hold"] if E["hold"][k]["IS"]["x"].get("n", 0) >= 100]
    pick = max(cand, key=lambda k: E["hold"][k]["IS"]["x"].get("avg") or -99) if cand else None
    E["pick"] = pick
    good = sum(1 for k in E["combo"] if (E["combo"][k]["OOS"]["add"].get("avg") or -99) > 0)
    E["robust_add_pos_oos"] = f"{good}/{len(HG)}"
    if pick:
        h, cIS, cOOS = E["hold"][pick], E["combo"][pick]["IS"], E["combo"][pick]["OOS"]
        ok = ((h["OOS"]["x"].get("avg") or -99) > 0 and (h["OOS"]["r"].get("pf") or 0) >= 1.2 and h["OOS"]["x"].get("n", 0) >= 100
              and (cOOS["add"].get("avg") or -99) > 0 and (cIS["add"].get("avg") or -99) > 0 and good >= 4)
        E["verdict"] = "✅" if ok else ("🧪" if (cOOS["add"].get("avg") or -99) > 0 else "❌")
        E["why"] = (f"{pick} · 뒤 hold {h['OOS']['x'].get('n')}건 초과 {h['OOS']['x'].get('avg')}% PF {h['OOS']['r'].get('pf')} · "
                    f"추가분(눌림 규칙이 건너뛴 것) 앞 {cIS['add'].get('n')}건 {cIS['add'].get('avg')}% / 뒤 {cOOS['add'].get('n')}건 {cOOS['add'].get('avg')}% · "
                    f"갭 칸 연간 초과 합 뒤 {cOOS['pull_yr_sum']} → {cOOS['yr_sum']} · 흔들기 뒤 추가분 + {E['robust_add_pos_oos']}")
    print("gaphold", E.get("verdict"), E.get("why"), flush=True)
    return E


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = {}
    tks = uni(log)
    idx = AB.idx_series("^GSPC")
    data = AB.download(tks, log, time.time())
    log["sec"] = round(time.time() - t0)
    res["log"] = log
    print(json.dumps(log, ensure_ascii=False), flush=True)
    df = pd.DataFrame(build(data, idx))
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
