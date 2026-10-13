"""📈 Q18-2 🐸 「끓는 물 속 개구리」(정보 이산성 ID) — 과거 검증 (사용자 10/13 18시 보고에 답: "2,4 진행해")
결과 → market/lab/k1013_q18.json

논문: Da·Gurun·Warachka 「Frog in the Pan: Continuous Information and Momentum」(RFS 2014)
  ID = sign(PRET) × (내린 날 비율 − 오른 날 비율), PRET = 그 기간 누적 수익.
  오른 종목에서 ID 가 낮을수록(−) 「조금씩 꾸준히」, 높을수록(+) 「며칠 크게 튀어서」 오른 것.
  가설: 꾸준히 오른 쪽(ID 낮음)이 뒤 수익이 더 좋다.

공통 틀 (src/lab/k1013_q16.py · src/kick_ideas_bt.py 와 같음):
  진입 = 신호 다음 거래일 종가 · 왕복 비용 0.5%(미국)/0.45%(한국) · 초과 = 같은 기간 지수(^GSPC / ^KS11) 대비
  앞 2012~2019 에서 고르고 뒤 2020~ 에서 시험 · 같은 종목 20거래일 안 재신호 무시 · 유니버스 = 오늘 S&P500+400 · 한국 스캐너 목록(생존자 편향)
사건: 📈 돌파 갭 대용(시가 갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가) / ☕ 컵 돌파 대용(종가 52주 신고가 · 거래량 ≥1.5배)
ID 는 신호일 「전」 W 거래일(신호일 빼고), W = 60 · 120.

손잡이(앞 기간에서만 고름): W(60·120) × 규칙(「튀어 오른 ⅓ 뺌」 = ID 상위 ⅓ 뺌 / 「꾸준한 ⅓만」 = ID 하위 ⅓만)
  ⅓ 경계값은 앞 기간 사건의 ID 분위수로 고정해 시험 기간에 그대로 씀(앞을 보지 않음).
  고르는 법: 남긴 쪽 비중 ≥ 30% 중 「남긴 쪽 초과 평균 − 전체 초과 평균」 최대.
판정 기준 (결과 보기 전에 정함, Q16-3 과 같음):
  ✅ = 시험 기간 남긴 쪽 초과 평균 ≥ 전체 + 0.3%p · 남긴 쪽 손익비 ≥ 전체 · 뺀 쪽 초과 평균 < 남긴 쪽 · 해마다 비교에서 과반 해가 나아짐
  ➖ = 그 밖(남긴 쪽이 전체보다 나쁘지 않음) · ❌ = 남긴 쪽이 전체보다 나쁨
  출구: 킥 규칙(kk) 이 주 판정, 20일 보유(f20) 는 참고. 미국·한국 따로, 그리고 합쳐서.
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1013_q18.json"
IS_END, OOS_START, IS_START = "2019-12-31", "2020-01-01", "2012-01-01"
WS = (60, 120)


def id_series(c, W):
    """신호일 빼고 직전 W 일의 ID (인덱스 t 값 = t-W..t-1 일 수익으로 계산)"""
    r = pd.Series(np.r_[np.nan, c[1:] / c[:-1] - 1])
    pos = (r > 0).astype(float).shift(1).rolling(W, min_periods=W).mean()
    neg = (r < 0).astype(float).shift(1).rolling(W, min_periods=W).mean()
    cs = pd.Series(c)
    pret = cs.shift(1) / cs.shift(W + 1) - 1
    return (np.sign(pret) * (neg - pos)).to_numpy(), (pret * 100).to_numpy()


def rows_for(m, data, idx):
    isym, minp, minvol = AB.MKT[m]
    cost = AB.COST.get(m, AB.DEF_COST)
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        c = F["c"]
        ids = {W: id_series(c, W) for W in WS}
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        gapev = F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (F["o"] > F["ph"]) & (c > F["hi60"])
        nhev = F["liq"] & F["nh"] & (F["vr"] >= 1.5)
        for kind, ev in (("gap", gapev), ("nh", nhev)):
            for ti in np.where(ev & (np.arange(n) >= 260))[0]:
                if ti + 1 >= n:
                    continue
                r = dict(tk=t, kind=kind, mkt=m, date=str(dates[ti].date()), ti=int(ti))
                for W in WS:
                    v, p = ids[W][0][ti], ids[W][1][ti]
                    r[f"id{W}"] = None if np.isnan(v) else round(float(v), 4)
                    r[f"pret{W}"] = None if np.isnan(p) else round(float(p), 2)
                r.update(KI.outcomes(c, F["ma20"], ixa, ti + 1, cost))
                rows.append(r)
    return rows


def judge(d, label):
    """d = 한 묶음(kind·시장) 사건표 → 손잡이 고르기 + 시험 판정"""
    out = {"name": label}
    d = d[d["date"] >= IS_START]
    per = {"IS": AB.dedupe(d[d["date"] <= IS_END]), "OOS": AB.dedupe(d[d["date"] >= OOS_START])}
    out["n_IS"], out["n_OOS"] = int(len(per["IS"])), int(len(per["OOS"]))
    for ex in ("kk", "f20"):
        col = "x_" + ex
        grid = []
        for W in WS:
            s_is = per["IS"].dropna(subset=[col, f"id{W}"])
            if len(s_is) < 60:
                continue
            q1, q2 = (float(s_is[f"id{W}"].quantile(q)) for q in (1 / 3, 2 / 3))
            for rule in ("drop_top", "keep_low"):
                row = {}
                for pn, s in per.items():
                    s = s.dropna(subset=[col, f"id{W}"])
                    keep = s[s[f"id{W}"] < q2] if rule == "drop_top" else s[s[f"id{W}"] <= q1]
                    drop = s.drop(keep.index)
                    row[pn] = {"all": KI.evals(s, ex), "keep": KI.evals(keep, ex), "drop": KI.evals(drop, ex),
                               "keep_share": round(len(keep) / max(1, len(s)) * 100, 1),
                               "terc": {k: KI.evals(g, ex)["x"] for k, g in (("꾸준(하위⅓)", s[s[f"id{W}"] <= q1]),
                                                                             ("중간", s[(s[f"id{W}"] > q1) & (s[f"id{W}"] < q2)]),
                                                                             ("튐(상위⅓)", s[s[f"id{W}"] >= q2]))}}
                grid.append(((W, rule, round(q1, 4), round(q2, 4)), row))
        E = {"grid": {f"W{k[0]}|{k[1]}": {pn: {"keep_x": v["keep"]["x"], "all_x": v["all"]["x"], "drop_x": v["drop"]["x"],
                                                  "keep_pf": v["keep"]["r"].get("pf"), "all_pf": v["all"]["r"].get("pf"),
                                                  "keep_share": v["keep_share"], "terc": v["terc"]} for pn, v in row.items()}
                      for k, row in grid}}
        ok = [(k, row) for k, row in grid if row["IS"]["keep_share"] >= 30 and row["IS"]["keep"]["x"].get("n")]
        if not ok:
            E["verdict"], E["why"] = "➖", "앞 기간 표본 부족"
            out[ex] = E
            continue
        k, row = max(ok, key=lambda g: (g[1]["IS"]["keep"]["x"].get("avg") or -99) - (g[1]["IS"]["all"]["x"].get("avg") or 0))
        o = row["OOS"]
        ka, aa, da = o["keep"]["x"].get("avg"), o["all"]["x"].get("avg"), o["drop"]["x"].get("avg")
        kp, ap = o["keep"]["r"].get("pf") or 0, o["all"]["r"].get("pf") or 0
        ky, ay = o["keep"].get("by_year") or {}, o["all"].get("by_year") or {}
        yrs = [y for y in ay if y in ky]
        better = sum(1 for y in yrs if (ky[y]["x"] or 0) > (ay[y]["x"] or 0))
        if ka is None or aa is None:
            vd = "➖"
        elif ka >= aa + 0.3 and kp >= ap and (da is None or da < ka) and better * 2 > len(yrs):
            vd = "✅"
        elif ka < aa:
            vd = "❌"
        else:
            vd = "➖"
        rn = "튀어 오른 ⅓ 뺌" if k[1] == "drop_top" else "꾸준한 ⅓만"
        E.update({"pick": {"W": k[0], "rule": k[1], "q1": k[2], "q2": k[3]}, "verdict": vd,
                  "why": (f"고른 손잡이: {k[0]}일 · {rn} (앞 기간 남긴 쪽 {row['IS']['keep_share']}%) · 시험 기간 남긴 쪽 초과 "
                          f"{ka if ka is None else f'{ka:+.2f}'}% (n{o['keep']['x'].get('n')}) vs 전체 {aa if aa is None else f'{aa:+.2f}'}% vs 뺀 쪽 "
                          f"{da if da is None else f'{da:+.2f}'}% · 손익비 {kp} vs {ap} · 나아진 해 {better}/{len(yrs)}"),
                  "by_year": {y: {"keep": ky[y]["x"], "all": ay[y]["x"]} for y in yrs}})
        out[ex] = E
    return out


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    allrows = []
    for m in ("US", "KR"):
        log = {}
        tks = AB.universe(m, log)
        idx = AB.idx_series(AB.MKT[m][0])
        data = AB.download(tks, log, time.time())
        log["sec"] = round(time.time() - t0)
        res["log"][m] = log
        print(m, json.dumps(log, ensure_ascii=False), flush=True)
        allrows += rows_for(m, data, idx)
        del data
    df = pd.DataFrame(allrows)
    print("rows", len(df), flush=True)
    J = {}
    for kind, kn in (("gap", "📈 돌파 갭 대용"), ("nh", "☕ 컵 돌파 대용")):
        for ms, mm in (("US", ("US",)), ("KR", ("KR",)), ("US+KR", ("US", "KR"))):
            d = df[(df["kind"] == kind) & df["mkt"].isin(mm)]
            J[f"{kind}|{ms}"] = judge(d, f"{kn} · {ms}")
            print(kind, ms, J[f"{kind}|{ms}"].get("kk", {}).get("verdict"), J[f"{kind}|{ms}"].get("kk", {}).get("why"), flush=True)
    res["q182"] = J
    res["sec"] = round(time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    df.to_csv(ROOT / "market" / "lab" / "k1013_q18_rows.csv.gz", index=False, compression="gzip")
    print("done", res["sec"])


if __name__ == "__main__":
    main()
