"""📈 Q16-3 🎰 「복권 종목」 거름망 + Q16-2 🔗 고객사 → 납품사 — 과거 검증 (사용자 10/13: "16-2,3,5 진행하고 반영시켜")
결과 → market/lab/k1013_q16.json (+ 매일 신호용 연결표 market/cust_links.json 은 손으로 관리)

공통 (src/kick_ideas_bt.py 와 같은 틀): 진입 = 신호 다음 거래일 종가 · 왕복 비용 0.5% · 초과 = 같은 기간 S&P500(^GSPC) 대비
  앞 2012~2019 에서 고르고, 뒤 2020~ 에서 시험. 같은 종목 20거래일 안 재신호 무시. 유니버스 = 오늘 S&P500+400 (생존자 편향).

── Q16-3 🎰 MAX 거름망 (Bali·Cakici·Whitelaw, JFE 2011)
  MAX20 = 신호일 「전」 20거래일(신호일 빼고) 하루 최대 종가 상승률(%).
  사건: 📈 돌파 갭 대용(시가 갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가) / ☕ 컵 돌파 대용(종가 52주 신고가 · 거래량 ≥1.5배)
  거름망 후보: MAX20 ≥ 5·7·10·15·20% 이면 뺌. 앞 기간에서 「남긴 쪽 초과 평균 − 전체 초과 평균」이 가장 큰 것(남긴 쪽 n ≥ 전체의 50%)을 고름.
  판정 기준 (결과 보기 전에 정함):
    ✅ 거름망 채택 = 시험 기간 남긴 쪽 초과 평균 ≥ 전체 + 0.3%p · 남긴 쪽 손익비 ≥ 전체 · 뺀 쪽 초과 평균 < 남긴 쪽 · 시험 기간 해마다 비교에서 과반 해가 나아짐
    ➖ 효과 없음 = 그 밖(남긴 쪽이 전체보다 나쁘지 않음) · ❌ = 남긴 쪽이 전체보다 나쁨
  출구: 킥 규칙(kk) 이 주 판정, 20일 보유(f20) 는 참고.

── Q16-2 🔗 고객사 → 납품사 (Cohen·Frazzini, JF 2008)
  연결표 = 10-K 「매출 10% 넘는 고객」 공시로 알려진 짝(아래 LINKS). ※ 오늘 아는 연결을 과거에 쓰므로 앞을 본 편향이 있음.
  신호: 고객사 그날 종가 상승 ≥ th(3·5·7%) · 거래량 ≥ 1.5배(실적 날 대용) · 납품사 그날 상승 ≤ 고객사 상승 × ratio(0·⅓·½)
  보유 10·20·40일, 킥 규칙(kk). 판정은 src/kick_ideas_bt.py verdict() 와 같음 (✅ n≥100 · 초과>0 · 손익비≥1.3 · 가장 좋은 해 빼도 초과>0 / 🧪 / 👻 / ❌)
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1013_q16.json"
LINKF = ROOT / "market" / "cust_links.json"
IS_START, IS_END, OOS_START = "2012-01-01", "2019-12-31", "2020-01-01"
COST = 0.005


def _stat(x):
    x = pd.Series(x, dtype=float).dropna()
    if not len(x):
        return {"n": 0}
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    return {"n": int(len(x)), "avg": round(float(x.mean()), 2), "med": round(float(x.median()), 2),
            "win": round(float((x > 0).mean()) * 100, 1), "pf": round(float(pos / neg), 2) if neg > 0 else None}


def evals(sel, ex):
    return KI.evals(sel, ex)


# ───────────────────────── 시세 ─────────────────────────
def load_prices(extra):
    log = {}
    t0 = time.time()
    tks = sorted(set(AB.universe("US", log)) | set(extra))
    data = AB.download(tks, log, t0)
    idx = AB.idx_series("^GSPC")
    return data, idx, log


# ───────────────────────── Q16-3 ─────────────────────────
def max_rows(data, idx):
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, 5, 5e6)
        c = F["c"]
        r1 = np.r_[np.nan, c[1:] / c[:-1] - 1] * 100
        mx = pd.Series(r1).shift(1).rolling(20, min_periods=15).max().to_numpy()      # 신호일 빼고 직전 20일
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        gapev = F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (F["o"] > F["ph"]) & (c > F["hi60"])
        nhev = F["liq"] & F["nh"] & (F["vr"] >= 1.5)
        for kind, ev in (("gap", gapev), ("nh", nhev)):
            for ti in np.where(ev & (np.arange(n) >= 260))[0]:
                if ti + 1 >= n or np.isnan(mx[ti]):
                    continue
                r = dict(tk=t, kind=kind, date=str(dates[ti].date()), ti=int(ti), mx=round(float(mx[ti]), 2), mkt="US")
                r.update(KI.outcomes(c, F["ma20"], ixa, ti + 1, COST))
                rows.append(r)
    return pd.DataFrame(rows)


def q163(df):
    out = {}
    TH = (5, 7, 10, 15, 20)
    for kind, nm in (("gap", "📈 돌파 갭 대용(4~8%)"), ("nh", "☕ 컵 돌파 대용(52주 신고가·거래량)")):
        d = df[(df["kind"] == kind) & (df["date"] >= IS_START)]
        per = {"IS": AB.dedupe(d[d["date"] <= IS_END]), "OOS": AB.dedupe(d[d["date"] >= OOS_START])}
        K = {"name": nm, "n_IS": int(len(per["IS"])), "n_OOS": int(len(per["OOS"])), "mx_pct": {}}
        for pn, s in per.items():
            K["mx_pct"][pn] = {q: round(float(s["mx"].quantile(q / 100)), 1) for q in (50, 70, 80, 90)} if len(s) else {}
        for ex in ("kk", "f20"):
            col = "x_" + ex
            E = {}
            grid = []
            for th in TH:
                row = {}
                for pn, s in per.items():
                    s = s.dropna(subset=[col])
                    keep, drop = s[s["mx"] < th], s[s["mx"] >= th]
                    row[pn] = {"all": evals(s, ex), "keep": evals(keep, ex), "drop": evals(drop, ex), "keep_share": round(len(keep) / max(1, len(s)) * 100, 1)}
                grid.append((th, row))
            E["grid"] = {str(th): {pn: {k: (v if k == "keep_share" else {"x": v["x"], "r": v["r"]}) for k, v in r_.items()} for pn, r_ in row.items()} for th, row in grid}
            ok = [(th, row) for th, row in grid if row["IS"]["keep_share"] >= 50 and row["IS"]["keep"]["x"].get("n")]
            if not ok:
                E["verdict"], E["why"] = "➖", "앞 기간에 남길 표본 부족"
                out[f"{kind}|{ex}"] = {**K, **E}
                continue
            th, row = max(ok, key=lambda g: (g[1]["IS"]["keep"]["x"].get("avg") or -99) - (g[1]["IS"]["all"]["x"].get("avg") or 0))
            o = row["OOS"]
            ka, aa, da = o["keep"]["x"].get("avg"), o["all"]["x"].get("avg"), o["drop"]["x"].get("avg")
            kp, ap = o["keep"]["r"].get("pf") or 0, o["all"]["r"].get("pf") or 0
            ky, ay = o["keep"].get("by_year") or {}, o["all"].get("by_year") or {}
            yrs = [y for y in ay if y in ky]
            better = sum(1 for y in yrs if (ky[y]["x"] or 0) > (ay[y]["x"] or 0))
            s = (f"고른 기준: MAX20 ≥ {th}% 뺌 (앞 기간 남긴 쪽 {row['IS']['keep_share']}%) · 시험 기간 남긴 쪽 초과 {ka:+.2f}% vs 전체 {aa:+.2f}% vs 뺀 쪽 "
                 f"{(da if da is not None else float('nan')):+.2f}% · 손익비 {kp} vs {ap} · 나아진 해 {better}/{len(yrs)}")
            if ka is None or aa is None:
                vd = "➖"
            elif ka >= aa + 0.3 and kp >= ap and (da is None or da < ka) and better * 2 > len(yrs):
                vd = "✅"
            elif ka < aa:
                vd = "❌"
            else:
                vd = "➖"
            E.update({"pick_th": th, "verdict": vd, "why": s, "by_year": {y: {"keep": ky[y]["x"], "all": ay[y]["x"]} for y in yrs}})
            out[f"{kind}|{ex}"] = {**K, **E}
    return out


# ───────────────────────── Q16-2 ─────────────────────────
def q162(data, idx, links):
    pairs = [(s, c) for s, cs in links.items() for c in cs]
    ixs = idx
    rows = []
    for sup, cus in pairs:
        if sup not in data or cus not in data:
            continue
        S, C = data[sup], data[cus]
        j = S.index.intersection(C.index)
        if len(j) < 320:
            continue
        S, C = S.loc[j], C.loc[j]
        cc, cv = C["close"].to_numpy(float), C["volume"].to_numpy(float)
        sc = S["close"].to_numpy(float)
        cr = np.r_[np.nan, cc[1:] / cc[:-1] - 1] * 100
        sr = np.r_[np.nan, sc[1:] / sc[:-1] - 1] * 100
        vr = cv / pd.Series(cv).shift(1).rolling(50, min_periods=50).mean().to_numpy()
        liq = (pd.Series(sc * S["volume"].to_numpy(float)).rolling(50).mean().to_numpy() >= 5e6) & (sc >= 5)
        ma20 = pd.Series(sc).rolling(20).mean().to_numpy()
        ixa = ixs.reindex(j).ffill().to_numpy(float)
        n = len(j)
        for ti in np.where((cr >= 3) & (vr >= 1.5) & liq & (np.arange(n) >= 60))[0]:
            if ti + 1 >= n:
                continue
            r = dict(tk=sup, cus=cus, date=str(j[ti].date()), ti=int(ti), cr=round(float(cr[ti]), 2), sr=round(float(sr[ti]), 2), mkt="US")
            r.update(KI.outcomes(sc, ma20, ixa, ti + 1, COST))
            rows.append(r)
    df = pd.DataFrame(rows)
    out = {"pairs": len(pairs), "pairs_with_data": int(df[["tk", "cus"]].drop_duplicates().shape[0]) if len(df) else 0, "rows": int(len(df))}
    if not len(df):
        out["verdict"], out["why"] = "❌", "사건 없음"
        return out, df
    df = df[df["date"] >= IS_START]
    grid, cache = [], {}
    for th in (3, 5, 7):
        for ratio in (0.0, 1 / 3, 0.5):
            nm = f"고객사≥{th}%|납품사≤고객사×{ratio:.2f}"
            fn = (lambda d, th=th, ratio=ratio: (d["cr"] >= th) & (d["sr"] <= d["cr"] * ratio))
            for pn, d in (("IS", df[df["date"] <= IS_END]), ("OOS", df[df["date"] >= OOS_START])):
                cache[(nm, pn)] = AB.dedupe(d[fn(d)])
            for ex in ("f10", "f20", "f40", "kk"):
                grid.append((nm, ex, evals(cache[(nm, "IS")], ex)))
    ok = [g for g in grid if g[2]["x"].get("n", 0) >= 100 and (g[2]["x"].get("avg") or -9) > 0 and (g[2]["r"].get("pf") or 0) >= 1.3]
    ok.sort(key=lambda g: -g[2]["x"]["avg"])
    pick = ok[0] if ok else max(grid, key=lambda g: (g[2]["x"].get("avg") or -99) if g[2]["x"].get("n", 0) >= 50 else -99)
    nm, ex, ins = pick
    oos = evals(cache[(nm, "OOS")], ex)
    vd, why = KI.verdict(oos)
    if not ok and vd in ("✅", "🧪"):
        vd, why = ("👻" if (oos["r"].get("avg") or 0) > 0 else "❌"), why + " — 앞 기간에서 기준(n≥100·초과>0·손익비≥1.3)을 통과한 규칙이 없음 → 채택 안 함"
    top = []
    for g in sorted(grid, key=lambda g: -(g[2]["x"].get("avg") or -99))[:12]:
        oo = evals(cache[(g[0], "OOS")], g[1])
        top.append({"rule": g[0], "exit": g[1], "IS_n": g[2]["x"].get("n"), "IS_x": g[2]["x"].get("avg"), "IS_pf": g[2]["r"].get("pf"),
                    "OOS_n": oo["x"].get("n"), "OOS_x": oo["x"].get("avg"), "OOS_pf": oo["r"].get("pf")})
    by_cus = {}
    s_ = cache[(nm, "OOS")].dropna(subset=["x_" + ex])
    for cu, g in s_.groupby("cus"):
        by_cus[cu] = _stat(g["x_" + ex])
    out.update({"pick": {"rule": nm, "exit": ex, "exit_doc": KI.EXIT_DOC[ex], "how": "앞 기간 n≥100·초과>0·손익비≥1.3 중 앞 기간 초과 평균 최대" if ok else "앞 기간 기준 통과 없음 → 앞 기간 초과 평균 최대(n≥50)"},
                "IS": ins, "OOS": oos, "verdict": vd, "why": why, "top": top, "OOS_by_customer": by_cus, "n_pass_IS": len(ok)})
    return out, df


def main():
    t0 = time.time()
    L = json.load(open(LINKF, encoding="utf-8"))
    links = {k: v["cus"] for k, v in L["links"].items()}
    extra = set(links) | {c for v in links.values() for c in v}
    data, idx, log = load_prices(extra)
    print("prices", len(data), round(time.time() - t0), "s", flush=True)
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "log": log, "rule": __doc__}
    mdf = max_rows(data, idx)
    print("max rows", len(mdf), flush=True)
    res["q163"] = q163(mdf)
    print(json.dumps(res["q163"], ensure_ascii=False)[:3000], flush=True)
    res["q162"], cdf = q162(data, idx, links)
    print(json.dumps({k: v for k, v in res["q162"].items() if k != "top"}, ensure_ascii=False)[:3000], flush=True)
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    if len(mdf):
        mdf.to_csv(ROOT / "market" / "lab" / "k1013_max_rows.csv.gz", index=False, compression="gzip")
    if len(cdf):
        cdf.to_csv(ROOT / "market" / "lab" / "k1013_cust_rows.csv.gz", index=False, compression="gzip")
    print("done", res["sec"])


if __name__ == "__main__":
    main()
