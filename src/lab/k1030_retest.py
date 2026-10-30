"""📈 10/30 10시 둘째 실험 — ⚡ 킥 ☕ 컵(신고가) 돌파 진입: 「돌파 뒤 기준선 되밟기(리테스트)」 때 사기
결과 → market/lab/k1030_retest.json
왜: 첫 실험(k1030_gaphold)에서 📈 갭은 「눌림 기다리기」(지금 Q15-5)가 기준보다 뒤 +0.95%p 나음을 다시 확인 — 같은 「눌림 진입」을
    킥의 가장 큰 칸 ☕ 컵 돌파(지금 다음 날 종가 진입)에 처음 붙여 봄. 실전 유튜브·트레이더 「돌파 → 되밟기(리테스트) → 진입」 규칙.
사건(g) = KI.ev_nh(252일 신고가 종가 · 거래량 1.5배 · 유동성) — q10 에서 쓴 ☕ 컵 대용(진짜 컵 모양 아님). 기준선 B = 직전 252일 고가.
기준 = g+1 종가 진입(지금 킥). 되밟기 r_w{W}f{F}: g+1…g+W 중 처음 「저가 ≤ B×(1+F%) 이고 종가 > B」 인 날 j → j+1 종가 진입(정직),
    그 전에 종가 < B×0.97(돌파 실패)면 취소 · W 안에 안 오면 건너뜀. W∈{3,5,8} × F∈{0,1.5,3} = 9판(결과 보기 전 정함). j 종가 진입도 참고.
출구·비용·초과·앞뒤·유니버스(오늘 S&P500+400 — 생존 편향)·20일 재신호 무시 = k1030_gaphold 와 같음.
판정 ✅ = 앞에서 고른 판(n≥100) 뒤 초과 평균이 기준보다 +0.5%p↑ · 손익비 ≥ 1.2 · 초과 > 0 · 앞도 기준보다 나음 · 9판 중 뒤 기준보다 나은 것 ≥ 6.
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
OUT = ROOT / "market" / "lab" / "k1030_retest.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"
GRID = [(w, f) for w in (3, 5, 8) for f in (0, 1.5, 3)]


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
        l, c = F["l"], F["c"]
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        for g in np.where(F["ev_nh"] & (np.arange(n) >= 260))[0]:
            if g + 10 >= n:
                continue
            B = F["hi252"][g]
            r0, x0 = kx(c, F["ma20"], ixa, g + 1, cost)
            if r0 is None or not B > 0:
                continue
            row = dict(tk=t, date=str(dates[g].date()), ti=int(g), r_b=r0, x_b=x0)
            for w, f in GRID:
                key = f"w{w}f{f:g}"
                st = "skip"
                for j in range(g + 1, min(g + w, n - 2) + 1):
                    if c[j] < B * 0.97:
                        st = "cancel"
                        break
                    if l[j] <= B * (1 + f / 100) and c[j] > B:
                        st = "in"
                        row[f"r_{key}"], row[f"x_{key}"] = kx(c, F["ma20"], ixa, j + 1, cost)
                        row[f"rj_{key}"], row[f"xj_{key}"] = kx(c, F["ma20"], ixa, j, cost)
                        break
                row[f"s_{key}"] = st
            rows.append(row)
    return rows


def pst(x):
    return KI.pst(pd.Series(x, dtype=float).dropna())


def judge(df):
    b = AB.dedupe(df).reset_index(drop=True)
    per = {"IS": b[(b["date"] >= IS_START) & (b["date"] <= IS_END)], "OOS": b[b["date"] >= OOS_START]}
    E = {"n": int(len(b)), "base": {}, "var": {}}
    for pn, s in per.items():
        E["base"][pn] = {"x": pst(s["x_b"]), "r": pst(s["r_b"])}
    for w, f in GRID:
        k = f"w{w}f{f:g}"
        V = {}
        for pn, s in per.items():
            inn, out = s[s[f"s_{k}"] == "in"], s[s[f"s_{k}"] != "in"]
            V[pn] = {"x": pst(inn[f"x_{k}"]), "r": pst(inn[f"r_{k}"]), "xj": pst(inn[f"xj_{k}"]), "take": round(len(inn) / max(len(s), 1) * 100, 1),
                     "same_ev_base_x": pst(inn["x_b"]), "skipped_base_x": pst(out["x_b"]),
                     "by_year": {y: round(float(v.mean()), 2) for y, v in inn.dropna(subset=[f"x_{k}"]).groupby(inn["date"].str[:4])[f"x_{k}"]}}
        E["var"][k] = V
    bi, bo = E["base"]["IS"]["x"].get("avg"), E["base"]["OOS"]["x"].get("avg")
    better = sum(1 for V in E["var"].values() if (V["OOS"]["x"].get("avg") or -99) > (bo or 0))
    E["robust"] = f"{better}/{len(GRID)}"
    cand = [k for k, V in E["var"].items() if V["IS"]["x"].get("n", 0) >= 100]
    if cand:
        k = max(cand, key=lambda x: E["var"][x]["IS"]["x"].get("avg") or -99)
        o, i = E["var"][k]["OOS"], E["var"][k]["IS"]
        xa, pf = o["x"].get("avg") or -99, o["r"].get("pf") or 0
        ok = xa - bo >= 0.5 and pf >= 1.2 and xa > 0 and (i["x"].get("avg") or -99) > bi and better >= 6 and o["x"].get("n", 0) >= 100
        E["pick"], E["verdict"] = k, ("✅" if ok else ("🧪" if xa > bo else "❌"))
        E["why"] = (f"{k} · 뒤 {o['x'].get('n')}건(사건의 {o['take']}%) 초과 {xa}% PF {pf} vs 기준 {E['base']['OOS']['x'].get('n')}건 {bo}% PF {E['base']['OOS']['r'].get('pf')} · "
                    f"앞 {i['x'].get('avg')}% vs {bi}% · 같은 사건 기준대로 {o['same_ev_base_x'].get('avg')}% · 건너뛴 사건 기준 {o['skipped_base_x'].get('avg')}% · j 종가 {o['xj'].get('avg')}% · 9판 중 나은 것 {E['robust']}")
    print("retest", E.get("verdict"), E.get("why"), flush=True)
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
