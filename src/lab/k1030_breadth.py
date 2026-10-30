"""📈 10/30 16시 둘째 — ⚡ 킥 ☕ 신고가 돌파: 「시장 전체가 같이 뚫나」(신고가 폭 · 같은 날 돌파 수)로 고르기
결과 → market/lab/k1030_breadth.json

왜: 첫 실험 k1030_vcp — 돌파 「직전 모양」(VCP·베이스)은 뒤에서 못 갈라 줌(❌). 남은 축 = 「돌파가 혼자냐, 시장이 같이냐」.
    sentimentrader 「Breakouts haven't been this good since 2016」(순 신고가 비율 10%↑ 가 2년 공백 뒤 나오면 이후 수익 좋음) ·
    Minervini 「시장이 받쳐 줄 때만 돌파」 실전 규칙. 지수 국면 스위치가 아니라 「우리 유니버스 안 신고가 폭」으로 킥 신호만 가름.
사건·진입·출구·비용·초과·재신호·유니버스 = k1030_vcp 와 같음(build 재사용).
폭 재는 법(그 유니버스 안, g 날까지 자료):
  NB = 10일 평균 (252일 신고가 종가 종목 수 − 252일 신저가 종가 종목 수) ÷ 자료 있는 종목 수
  CR = 그날 같은 ev_nh(신고가 + 거래량 1.5배) 사건 수 ÷ 종목 수
판(결과 보기 전 정함): NB 상위⅓·하위⅓ · CR 상위⅓·하위⅓ — 경계는 500+400 앞(2008~16) 사건 분포의 ⅓·⅔ 지점(S&P600 엔 자기 앞 구간 경계).
판정 ✅: 500+400 앞에서 초과 평균 1등 판(n≥300) → 뒤에서 ALL0 보다 +0.5%p↑·초과 > 0·PF ≥ 1.1 · S&P600 앞·뒤 모두 ALL0 보다 나음 ·
  경계 ±20%(⅓→0.27·0.40 분위) 이웃 뒤 모두 ALL0 보다 나음 · 5칸 모의 뒤 연 칸 수익 > ALL0.
생존 편향: 오늘 구성 종목만(폭 숫자도 오늘 종목 기준).
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import k1030_vcp as V          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

AB = V.AB
OUT = ROOT / "market" / "lab" / "k1030_breadth.json"
IS_START, IS_END, OOS_START = V.IS_START, V.IS_END, V.OOS_START


def breadth(data):
    _, minp, minvol = AB.MKT["US"]
    nh, nl, ok, ev = {}, {}, {}, {}
    for t, d in data.items():
        if len(d) < 300:
            continue
        cs = d["close"]
        hi = cs.shift(1).rolling(252, min_periods=252).max()
        lo = cs.shift(1).rolling(252, min_periods=252).min()
        nh[t], nl[t], ok[t] = (cs > hi).astype(float), (cs < lo).astype(float), hi.notna().astype(float)
        F = KI.feats(d, minp, minvol)
        ev[t] = pd.Series(np.nan_to_num(F["ev_nh"].astype(float)), index=d.index)
    H, L, O, E = (pd.DataFrame(x).sort_index().fillna(0).sum(axis=1) for x in (nh, nl, ok, ev))
    O = O.replace(0, np.nan)
    nb = ((H - L) / O).rolling(10).mean()
    cr = E / O
    return nb, cr


def tag(df, nb, cr):
    dd = pd.to_datetime(df["date"])
    df = df.copy()
    df["nb"] = nb.reindex(dd).to_numpy()
    df["cr"] = cr.reindex(dd).to_numpy()
    return df


def stats(df, m):
    out = {}
    for pn, a, b in (("IS", IS_START, IS_END), ("OOS", OOS_START, "2100")):
        sel = (df["date"] >= a) & (df["date"] <= b)
        s = df[sel & m]
        yr = V.sleeve(s)
        ny = 9 if pn == "IS" else 9.8
        out[pn] = {**KI.pst(s["x"]), "per_yr": round(len(s) / ny, 1), "sleeve_yr": round(sum(yr.values()) / ny, 2)}
    return out


def run(df, qs=(1 / 3, 2 / 3)):
    isd = df[(df["date"] >= IS_START) & (df["date"] <= IS_END)]
    R = {"ALL0": stats(df, pd.Series(True, index=df.index))}
    for col in ("nb", "cr"):
        lo, hi = isd[col].quantile(qs[0]), isd[col].quantile(qs[1])
        R[f"{col}_hi"] = stats(df, df[col] >= hi)
        R[f"{col}_lo"] = stats(df, df[col] <= lo)
        R[f"{col}_cut"] = [round(float(lo), 4), round(float(hi), 4)]
    return R


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(V.KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = res["log"]
    idx = AB.idx_series("^GSPC")
    try:
        tb = V.uni(("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"), log, "big")
        db = AB.download(tb, log, time.time())
        nb, cr = breadth(db)
        big = tag(AB.dedupe(V.build(db, idx)).reset_index(drop=True), nb, cr)
        del db
        Rb = run(big)
        res["big"] = Rb
        keys = [k for k in Rb if k != "ALL0" and not k.endswith("_cut")]
        cand = [(Rb[k]["IS"].get("avg", -99), k) for k in keys if Rb[k]["IS"].get("n", 0) >= 300]
        pick = max(cand)[1]
        res["pick"] = pick
        nbr = {}
        for q in ((0.27, 0.73), (0.40, 0.60)):
            nbr[str(q)] = run(big, q)[pick]
        res["nb"] = nbr
        ts = V.uni(("List_of_S%26P_600_companies",), log, "sm")
        ds = AB.download(ts, log, time.time())
        nb2, cr2 = breadth(ds)
        sm = tag(AB.dedupe(V.build(ds, idx)).reset_index(drop=True), nb2, cr2)
        Rs = run(sm)
        res["small"] = Rs
        b0, p = Rb["ALL0"], Rb[pick]
        c1 = p["OOS"].get("avg", -99) - b0["OOS"]["avg"] >= 0.5 and p["OOS"].get("avg", -99) > 0 and (p["OOS"].get("pf") or 0) >= 1.1
        c2 = all(Rs[pick][pn].get("avg", -99) > Rs["ALL0"][pn]["avg"] for pn in ("IS", "OOS"))
        c3 = all(v["OOS"].get("avg", -99) > b0["OOS"]["avg"] for v in nbr.values())
        c4 = p["OOS"]["sleeve_yr"] > b0["OOS"]["sleeve_yr"]
        res["checks"] = {"oos_big": c1, "small_both": c2, "nb": c3, "sleeve": c4}
        res["verdict"] = "✅" if all((c1, c2, c3, c4)) else ("🟡" if sum((c1, c2, c3, c4)) >= 3 else "❌")
        res["summary"] = (f"앞 1등 {pick}: 앞 {p['IS'].get('avg')}%({p['IS'].get('n')}) vs {b0['IS']['avg']} · 뒤 {p['OOS'].get('avg')}%"
                          f"({p['OOS'].get('n')}, PF {p['OOS'].get('pf')}) vs {b0['OOS']['avg']} · S&P600 앞 {Rs[pick]['IS'].get('avg')} vs {Rs['ALL0']['IS']['avg']}"
                          f" · 뒤 {Rs[pick]['OOS'].get('avg')} vs {Rs['ALL0']['OOS']['avg']} · 칸 뒤 {p['OOS']['sleeve_yr']} vs {b0['OOS']['sleeve_yr']} → {res['verdict']} {res['checks']}")
        print(res["summary"], flush=True)
    except Exception:
        import traceback
        res["err"] = traceback.format_exc()[-1500:]
        print(res["err"], flush=True)
    res["sec"] = round(time.time() - t0)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
