"""📈 10/30 16시 — ⚡ 킥 ☕ 신고가 돌파: 「돌파 전 조용했나」(Minervini VCP · O'Neil 베이스) 로 고르기
결과 → market/lab/k1030_vcp.json

왜: 킥의 가장 큰 구멍 = ☕ 신고가 돌파(다음 날 종가 진입) — 10시 k1030_retest 뒤(2017~) 사건 초과 평균 −0.44%·PF 0.87.
    출구 손잡이는 10/12·10/24 에 「잡음」으로 닫힘 → 여기선 「돌파 직전 며칠의 모양」만 본다.
    실전 트레이더 규칙(Minervini 「변동성 수축 패턴 VCP」 · 25년 2.35M 자료 글: 5일 거래량 < 50일의 75% · 변동폭 수축 때 PF 1.12→1.53,
    「트렌드 템플릿」 200일선 오름·150>200, O'Neil 「베이스에서 첫 돌파」). 우리 장부에서 처음 잼.
사건 g = KI.ev_nh (252일 신고가 종가 · 거래량 1.5배 · 유동성) — 진입 g+1 종가 · 출구 KI.kexit · 왕복 0.5% · 초과 = S&P500 대비 · 20일 재신호 무시.
돌파 전 모양(모두 g-1 까지 자료, 결과 보기 전 정함):
  D 마름   : 직전 5일 평균 거래량 ≤ 그 앞 50일 평균 × 0.75
  T 좁음   : 직전 10일 (최고 고가 − 최저 저가) ÷ 전일 종가 ≤ 10%
  B 베이스 : 직전 신고가 종가 이후 ≥ 40거래일 (= 계속 신고가 찍던 종목이 아니라 쉬었다 처음 뚫음)
  TT 추세틀: 200일선 > 20일 전 200일선 · 150일선 > 200일선 · 종가 > 50일선
판 10개: ALL0(거름 없음 = 지금) · D · T · B · TT · D_T · D_T_TT · B_D · B_T · B_D_T
표본 둘: 1) S&P500+400(고르는 곳 = 앞 2008~16) 2) S&P600(안 본 표본 — 앞·뒤 모두 확인용)
판정 ✅: 앞(500+400)에서 n≥150 중 초과 평균 1등 판 →
  ① 500+400 뒤 초과 평균이 ALL0 보다 +0.5%p↑ · PF ≥ 1.1 · 초과 > 0
  ② S&P600 앞·뒤 모두 ALL0 보다 나음  ③ 손잡이 ±20% 이웃(0.6/0.9 · 8/12% · 32/48일) 뒤 모두 ALL0 보다 나음
  ④ 5칸 단순 칸 모의(칸 비면 그날 신호 거래량 배수 큰 순, 쉬는 돈 0)에서 뒤 연 칸 수익이 ALL0 보다 + (= 킥 칸 +x%p)
생존 편향: 오늘 지수 구성 종목만(실제보다 좋게 나올 수 있음 — 두 판 차이엔 덜 영향).
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
AB.TIME_BUDGET = 26 * 60
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1030_vcp.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
VARS = {"ALL0": (), "D": ("D",), "T": ("T",), "B": ("B",), "TT": ("TT",), "D_T": ("D", "T"), "D_T_TT": ("D", "T", "TT"),
        "B_D": ("B", "D"), "B_T": ("B", "T"), "B_D_T": ("B", "D", "T")}
BASE_K = {"D": 0.75, "T": 0.10, "B": 40}


def uni(pages, log, tag):
    import requests
    tk = []
    hd = {"User-Agent": "Mozilla/5.0 (research script)"}
    for pg in pages:
        try:
            r = requests.get(f"https://en.wikipedia.org/wiki/{pg}", headers=hd, timeout=30)
            for t in pd.read_html(io.StringIO(r.text)):
                col = next((x for x in t.columns if str(x).lower() in ("symbol", "ticker symbol", "ticker")), None)
                if col is not None and len(t) > 300:
                    tk += [str(s).strip().replace(".", "-") for s in t[col].dropna()]
                    break
        except Exception as e:
            log[f"err_{tag}_{pg[-12:]}"] = repr(e)[:150]
    tk = sorted(set(tk))
    log[f"src_{tag}"] = f"{len(tk)} 종목"
    return tk


def build(data, idx):
    cost = AB.COST.get("US", AB.DEF_COST)
    _, minp, minvol = AB.MKT["US"]
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        h, l, c, v = F["h"], F["l"], F["c"], F["v"]
        n = len(c)
        dates = d.index
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        cs, vs, hs, ls = pd.Series(c), pd.Series(v), pd.Series(h), pd.Series(l)
        v5 = vs.shift(1).rolling(5).mean().to_numpy()
        v50 = vs.shift(6).rolling(50, min_periods=40).mean().to_numpy()
        rng10 = ((hs.shift(1).rolling(10).max() - ls.shift(1).rolling(10).min()) / cs.shift(1)).to_numpy()
        ma50, ma150, ma200 = (cs.rolling(k).mean().to_numpy() for k in (50, 150, 200))
        ma200_20 = pd.Series(ma200).shift(20).to_numpy()
        nh = np.nan_to_num(F["nh"].astype(float)) > 0
        last = np.where(nh, np.arange(n), -1)
        prev_nh = np.maximum.accumulate(np.r_[-1, last[:-1]])      # g 전 마지막 신고가 날
        ev = F["ev_nh"]
        for g in np.where(ev & (np.arange(n) >= 262))[0]:
            e = g + 1
            if e >= n - 1:
                continue
            res = KI.kexit(c, F["ma20"], e)
            if res is None:
                continue
            r, ex = res
            if not (ixa[e] > 0 and ixa[ex] > 0):
                continue
            rr = r - cost
            rows.append(dict(tk=t, date=str(dates[g].date()), ti=int(g), e=str(dates[e].date()), xd=str(dates[ex].date()),
                             r=round(rr * 100, 2), x=round((rr - (ixa[ex] / ixa[e] - 1)) * 100, 2), vr=float(F["vr"][g]),
                             dry=float(v5[g] / v50[g]) if v50[g] > 0 else np.nan, rng=float(rng10[g]),
                             base=int(g - prev_nh[g]) if prev_nh[g] >= 0 else 999,
                             tt=bool(ma200[g] > ma200_20[g] and ma150[g] > ma200[g] and c[g] > ma50[g])))
    return pd.DataFrame(rows)


def mask(df, comps, K):
    m = np.ones(len(df), bool)
    for cpt in comps:
        if cpt == "D":
            m &= (df["dry"] <= K["D"]).to_numpy()
        elif cpt == "T":
            m &= (df["rng"] <= K["T"]).to_numpy()
        elif cpt == "B":
            m &= (df["base"] >= K["B"]).to_numpy()
        elif cpt == "TT":
            m &= df["tt"].to_numpy()
    return m


def sleeve(s, slots=5):
    """5칸 단순 모의: 진입일에 빈 칸 있으면 거래량 배수 큰 순으로 채움 · 칸당 20% · 쉬는 돈 0 · 해마다 칸 수익 합"""
    s = s.sort_values(["e", "vr"], ascending=[True, False])
    busy, yr = [], {}
    for e, xd, r in zip(s["e"], s["xd"], s["r"]):
        busy = [b for b in busy if b > e]
        if len(busy) >= slots:
            continue
        busy.append(xd)
        yr[e[:4]] = yr.get(e[:4], 0.0) + r / slots
    return yr


def period_stats(df, comps, K):
    out = {}
    for pn, a, b in (("IS", IS_START, IS_END), ("OOS", OOS_START, "2100")):
        s = df[(df["date"] >= a) & (df["date"] <= b)]
        s = s[mask(s, comps, K)]
        yr = sleeve(s)
        ny = 9 if pn == "IS" else 9.8
        out[pn] = {**KI.pst(s["x"]), "per_yr": round(len(s) / ny, 1), "sleeve_yr": round(sum(yr.values()) / ny, 2),
                   "sleeve_by_year": {k: round(v, 1) for k, v in sorted(yr.items())}}
    return out


def run(df):
    R = {}
    for k, comps in VARS.items():
        R[k] = period_stats(df, comps, BASE_K)
    return R


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = res["log"]
    idx = AB.idx_series("^GSPC")
    try:
        tb = uni(("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"), log, "big")
        db = AB.download(tb, log, time.time())
        log["sec_big"] = round(time.time() - t0)
        big = AB.dedupe(build(db, idx)).reset_index(drop=True)
        del db
        log["n_big"] = int(len(big))
        Rb = run(big)
        res["big"] = Rb
        cand = [(Rb[k]["IS"].get("avg", -99), k) for k in VARS if k != "ALL0" and Rb[k]["IS"].get("n", 0) >= 150]
        pick = max(cand)[1] if cand else None
        res["pick"] = pick
        print("pick", pick, {k: (Rb[k]["IS"].get("avg"), Rb[k]["OOS"].get("avg"), Rb[k]["IS"].get("n"), Rb[k]["OOS"].get("n"),
                                 Rb[k]["OOS"]["sleeve_yr"]) for k in VARS}, flush=True)
        # 이웃 ±20%
        nb = {}
        if pick:
            comps = VARS[pick]
            for cpt in [c for c in comps if c in BASE_K]:
                for f in (0.8, 1.2):
                    K = dict(BASE_K)
                    K[cpt] = BASE_K[cpt] * f
                    nb[f"{cpt}x{f}"] = period_stats(big, comps, K)
        res["nb"] = nb
        ts = uni(("List_of_S%26P_600_companies",), log, "sm")
        ds = AB.download(ts, log, time.time())
        log["sec_sm"] = round(time.time() - t0)
        sm = AB.dedupe(build(ds, idx)).reset_index(drop=True)
        log["n_sm"] = int(len(sm))
        Rs = run(sm)
        res["small"] = Rs
        if pick:
            b0, p = Rb["ALL0"], Rb[pick]
            c1 = (p["OOS"].get("avg", -99) - b0["OOS"].get("avg", 0) >= 0.5 and (p["OOS"].get("pf") or 0) >= 1.1 and p["OOS"].get("avg", -99) > 0)
            c2 = all(Rs[pick][pn].get("avg", -99) > Rs["ALL0"][pn].get("avg", 99) for pn in ("IS", "OOS"))
            c3 = all(v["OOS"].get("avg", -99) > b0["OOS"].get("avg", 99) for v in nb.values()) if nb else True
            c4 = p["OOS"]["sleeve_yr"] > b0["OOS"]["sleeve_yr"]
            res["checks"] = {"oos_big": c1, "small_both": c2, "nb": c3, "sleeve": c4}
            res["verdict"] = "✅" if all((c1, c2, c3, c4)) else ("🟡" if sum((c1, c2, c3, c4)) >= 3 else "❌")
            res["summary"] = (f"앞 1등 {pick}: 500+400 앞 {p['IS'].get('avg')}%({p['IS'].get('n')}) vs 지금 {b0['IS'].get('avg')}% · "
                              f"뒤 {p['OOS'].get('avg')}%({p['OOS'].get('n')}, PF {p['OOS'].get('pf')}) vs {b0['OOS'].get('avg')}% · "
                              f"S&P600 앞 {Rs[pick]['IS'].get('avg')} vs {Rs['ALL0']['IS'].get('avg')} · 뒤 {Rs[pick]['OOS'].get('avg')} vs {Rs['ALL0']['OOS'].get('avg')} · "
                              f"칸 모의 뒤 연 {p['OOS']['sleeve_yr']} vs {b0['OOS']['sleeve_yr']} → {res['verdict']} {res['checks']}")
            print(res["summary"], flush=True)
    except Exception:
        import traceback
        res["err"] = traceback.format_exc()[-1500:]
        print(res["err"], flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
