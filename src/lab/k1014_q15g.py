"""📈 Q15-5 🎯 「갭 다음 날 종가」 말고 「갭 사흘째 눌림」 — 과거 검증 (사용자 10/14 15시 보고에 답: "2,5번 실행")
결과 → market/lab/k1014_q15g.json (+ 사건표 market/lab/k1014_q15g_rows.csv.gz)

공통 틀 (Q10·Q13 과 같음): 출구 = 킥 규칙(kexit: −5% 손절 · +15% 반 익절 뒤 20일선 · 15일 +3% 못 가면 정리 · 60일 한도)
  · 왕복 0.5%(미국)/0.45%(한국) · 초과 = 같은 기간 지수 대비 · 같은 종목 20거래일 안 재신호 무시
  · 앞 2008~2016 에서 고르고 뒤 2017~ 에서 시험 · 유니버스 = 오늘 S&P500+400 · 한국 스캐너 목록(생존자 편향)

사건: 📈 gap = 시가 갭 4~8% · 전일 고가 위 시가 · 거래량 1.5~6배 · 종가 > 60일 고가 (킥 갭 필터 대용, Q13 과 같음). 갭 날 = g.
기준(지금 킥): g+1 거래일 종가 진입.
눌림 규칙(결과 보기 전 정함):
  P0 = g-1 종가(갭 시작 가격) · S = g 시가 − P0(갭 크기) · L = P0 + (1 − f)·S (f = 갭의 몇 할까지 되돌리나: f=0.5 → 갭 절반 자리)
  g+1 ~ g+W 거래일 중 처음으로 「저가 ≤ L 이고 종가 > P0」 인 날 j → j+1 종가 진입 (원안: 신호는 장 마감 뒤 확인 → 다음 날 종가)
  그 전에 종가 ≤ P0 (갭 다 메움) 이면 취소 · W 일 안에 안 눌리면 건너뜀(쫓지 않음).
  (참고) j 종가 진입(장 마감 동시호가로 바로 사는 경우)도 함께 셈.
  손잡이: W(3·5) × f(0.33·0.5·0.75). 원안 = W3·f0.5.
판정(결과 보기 전):
  ✅ = 앞 기간에서 고른 판(n≥100 중 초과 평균 최대)이 시험 기간에 기준보다 초과 평균 +0.5%p 이상 · 손익비 ≥ 1.2 · 초과 평균 > 0
       · 앞 기간도 기준보다 나음 · 변형 6개 중 시험 기간 기준보다 나은 것 ≥ 4
  🧪 = 시험 기간 기준보다 나으나 위 일부 못 미침 · ❌ = 시험 기간 기준과 같거나 나쁨 · ➖ = 표본 부족(n<30)
  덧: 눌림이 「잘 고르는 것」인지 「덜 사는 것」인지 보려고 건너뛴 사건(안 눌림·취소)의 기준 성적도 같이 적음.
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

AB.START = "2006-06-01"
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q15g.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
GRID = [(w, f) for w in (3, 5) for f in (0.33, 0.5, 0.75)]


def kx(c, ma20, ixa, e, cost):
    res = KI.kexit(c, ma20, e)
    if res is None:
        return None, None
    r, ex = res
    x = (r - cost - (ixa[ex] / ixa[e] - 1)) * 100 if ixa[e] > 0 and ixa[ex] > 0 else None
    return round((r - cost) * 100, 2), (None if x is None else round(x, 2))


def build(m, data, idx):
    isym, minp, minvol = AB.MKT[m]
    cost = AB.COST.get(m, AB.DEF_COST)
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
            if g + 7 >= n:
                continue
            p0, S = c[g - 1], o[g] - c[g - 1]
            r0, x0 = kx(c, F["ma20"], ixa, g + 1, cost)
            if r0 is None:
                continue
            row = dict(tk=t, mkt=m, date=str(dates[g].date()), ti=int(g), gp=round(float(F["gap"][g]) * 100, 2), r_b=r0, x_b=x0)
            for w, f in GRID:
                L = p0 + (1 - f) * S
                key = f"w{w}f{int(f * 100)}"
                st = "skip"
                for j in range(g + 1, min(g + w, n - 2) + 1):
                    if c[j] <= p0:
                        st = "cancel"
                        break
                    if l[j] <= L and c[j] > p0:
                        st = "in"
                        r1, x1 = kx(c, F["ma20"], ixa, j + 1, cost)
                        r2, x2 = kx(c, F["ma20"], ixa, j, cost)
                        row.update({f"r_{key}": r1, f"x_{key}": x1, f"rj_{key}": r2, f"xj_{key}": x2, f"d_{key}": j - g})
                        break
                row[f"s_{key}"] = st
            rows.append(row)
    return rows


def pst(x):
    return KI.pst(pd.Series(x, dtype=float))


def by_year(s, col):
    g = s.dropna(subset=[col])
    return {y: round(float(v.mean()), 2) for y, v in g.groupby(g["date"].str[:4])[col]}


def judge(df):
    res = {}
    for m in ("US", "KR"):
        b = AB.dedupe(df[df["mkt"] == m]).reset_index(drop=True)
        per = {"IS": b[(b["date"] >= IS_START) & (b["date"] <= IS_END)], "OOS": b[b["date"] >= OOS_START]}
        E = {"n": int(len(b)), "base": {}, "var": {}}
        for pn, s in per.items():
            E["base"][pn] = {"x": pst(s["x_b"]), "r": pst(s["r_b"]), "by_year": by_year(s, "x_b")}
        for w, f in GRID:
            k = f"w{w}f{int(f * 100)}"
            V = {}
            for pn, s in per.items():
                inn = s[s[f"s_{k}"] == "in"]
                out = s[s[f"s_{k}"] != "in"]
                V[pn] = {"x": pst(inn[f"x_{k}"]), "r": pst(inn[f"r_{k}"]), "xj": pst(inn[f"xj_{k}"]), "rj": pst(inn[f"rj_{k}"]),
                         "take": round(len(inn) / max(len(s), 1) * 100, 1),
                         "same_ev_base_x": pst(inn["x_b"]), "skipped_base_x": pst(out["x_b"]),
                         "cancel": int((s[f"s_{k}"] == "cancel").sum()), "skip": int((s[f"s_{k}"] == "skip").sum()),
                         "by_year": by_year(inn, f"x_{k}")}
            E["var"][k] = V
        bi, bo = E["base"]["IS"]["x"].get("avg"), E["base"]["OOS"]["x"].get("avg")
        cand = [k for k, V in E["var"].items() if V["IS"]["x"].get("n", 0) >= 100 and V["IS"]["x"].get("avg") is not None]
        better = sum(1 for k, V in E["var"].items() if (V["OOS"]["x"].get("avg") or -99) > (bo or 0))
        E["robust"] = f"{better}/{len(GRID)}"

        def vd(k):
            V = E["var"][k]
            o, i = V["OOS"], V["IS"]
            xa, pf, n = o["x"].get("avg"), o["r"].get("pf"), o["x"].get("n", 0)
            if xa is None or n < 30 or bo is None:
                return "➖", "표본 부족"
            s = (f"{k} · 시험 기간 {n}건(갭의 {o['take']}%) 초과 {xa:+.2f}% 손익비 {pf} vs 기준(다음 날 종가) {E['base']['OOS']['x'].get('n')}건 "
                 f"{bo:+.2f}% 손익비 {E['base']['OOS']['r'].get('pf')} · 앞 기간 {i['x'].get('avg')}% vs {bi}% · 같은 사건을 기준대로 샀다면 {o['same_ev_base_x'].get('avg')}% "
                 f"· 건너뛴 사건 기준 {o['skipped_base_x'].get('avg')}% · j 종가 진입 {o['xj'].get('avg')}% · 변형 중 기준보다 나은 것 {E['robust']}")
            if xa - bo >= 0.5 and (pf or 0) >= 1.2 and xa > 0 and (i["x"].get("avg") or -99) > (bi or 0) and better >= 4 and n >= 100:
                return "✅", s
            if xa > bo:
                return "🧪", s
            return "❌", s
        if cand:
            k = max(cand, key=lambda x: E["var"][x]["IS"]["x"]["avg"])
            E["pick"] = k
            E["verdict"], E["why"] = vd(k)
        else:
            E["verdict"], E["why"] = "➖", "앞 기간 n≥100 변형 없음"
        E["user_w3f50"] = dict(zip(("verdict", "why"), vd("w3f50")))
        print("Q15-5", m, E["verdict"], E["why"], "| 원안", E["user_w3f50"], flush=True)
        res[m] = E
    return res


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    rows = []
    for m in ("US", "KR"):
        log = {}
        tks = AB.universe(m, log)
        idx = AB.idx_series(AB.MKT[m][0])
        data = AB.download(tks, log, time.time())
        log["sec"] = round(time.time() - t0)
        res["log"][m] = log
        print(m, json.dumps(log, ensure_ascii=False), flush=True)
        rows += build(m, data, idx)
        del data
    df = pd.DataFrame(rows)
    print("rows", len(df), flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ROOT / "market" / "lab" / "k1014_q15g_rows.csv.gz", index=False, compression="gzip")
    try:
        res["q155"] = judge(df)
    except Exception as e:
        import traceback
        res["err"] = traceback.format_exc()[-800:]
        print(res["err"], flush=True)
    res["sec"] = round(time.time() - t0)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
