"""📈 Q18-4 🔎 「검색량이 터진 뒤엔 늦다」 — 과거 검증 (사용자 10/13 18시 보고에 답: "2,4 진행해")
결과 → market/lab/k1013_q18_attn.json  (+ 검색량 저장 market/lab/k1013_attn_svi.csv.gz)

논문: Da·Engelberg·Gao 「In Search of Attention」(J. of Finance 2011) — 검색량 급증 종목은 2주쯤 더 오르다 1년 안에 되돌아감.
자료: 네이버 데이터랩 검색어 트렌드 API (https://developers.naver.com/docs/serviceapi/datalab/search/search.md)
  ※ 열쇠 필요: 깃허브 Secrets 에 NAVER_CLIENT_ID · NAVER_CLIENT_SECRET (네이버 개발자센터 → 애플리케이션 등록 → 「데이터랩(검색어트렌드)」, 무료 · 하루 1,000번)
  열쇠가 없으면 아무것도 바꾸지 않고 「열쇠 없음」만 적고 끝난다.
  한 번 부를 때 종목 5개(이름 = 검색어), 2016-01-01~ 하루 단위. 값은 그 호출 안 최대값=100 상대값이지만,
  우리는 「자기 자신의 지난 8주 평균 대비 배수」만 쓰므로 호출 간 눈금 차이는 상관없음.
  약점: 종목 이름이 일반 단어와 겹치면(예: 「한화」 「현대차」 그룹 뉴스) 잡음 · 검색어 = 오늘 이름(옛 이름 못 씀).

공통 틀(k1013_q18.py 와 같음): 📈 돌파 갭 대용 / ☕ 컵 돌파 대용 · 한국 스캐너 목록 · 신호 다음 날 종가 진입 · 왕복 0.45% · 초과 = 코스피 대비
  검색량 자료가 2016~ 이라 앞 2016-07~2020 에서 고르고 뒤 2021~ 에서 시험.
  SVI 배수 = 신호일 검색량 ÷ 신호일 전 56일(8주) 평균. 손잡이 k = 2 · 3 · 5 배.
판정 기준 (결과 보기 전에 정함):
  ✅ (과열이면 크기 절반 채택) = 시험 기간 「과열(배수 ≥ k)」 쪽 초과 평균이 「조용(배수 < k)」 쪽보다 0.5%p 이상 낮고 · 과열 쪽 손익비 < 조용 쪽 · 과열 n ≥ 30 · 해마다 비교 과반에서 과열 쪽이 나쁨
  ➖ = 차이 작음 · ❌ = 과열 쪽이 오히려 좋음(이 경우 거름망은 손해)
"""
import json, os, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1013_q18_attn.json"
SVIF = ROOT / "market" / "lab" / "k1013_attn_svi.csv.gz"
IS_START, IS_END, OOS_START = "2016-07-01", "2020-12-31", "2021-01-01"
KS = (2, 3, 5)
API = "https://openapi.naver.com/v1/datalab/search"
MAX_CALLS = 950


def fetch_svi(names, cid, sec, log):
    import requests
    have = pd.read_csv(SVIF, index_col=0, parse_dates=True) if SVIF.exists() else pd.DataFrame()
    todo = [n for n in names if n not in have.columns]
    end = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    cols, calls, errs = {}, 0, []
    for i in range(0, len(todo), 5):
        if calls >= MAX_CALLS:
            log["svi_cut"] = i
            break
        part = todo[i:i + 5]
        body = {"startDate": "2016-01-01", "endDate": end, "timeUnit": "date",
                "keywordGroups": [{"groupName": n, "keywords": [n]} for n in part]}
        for att in range(3):
            try:
                r = requests.post(API, json=body, timeout=30,
                                  headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec, "Content-Type": "application/json"})
                calls += 1
                if r.status_code == 200:
                    for g in r.json().get("results", []):
                        s = pd.Series({x["period"]: x["ratio"] for x in g.get("data", [])}, dtype=float)
                        s.index = pd.to_datetime(s.index)
                        cols[g["title"]] = s
                    break
                errs.append(f"{r.status_code} {r.text[:120]}")
                if r.status_code in (401, 403):
                    log["svi_err"] = errs[-1]
                    return have
                time.sleep(2 * (att + 1))
            except Exception as e:
                errs.append(repr(e)[:120])
                time.sleep(3)
        time.sleep(0.12)
    log["svi_calls"], log["svi_errs"] = calls, errs[:5]
    if cols:
        new = pd.DataFrame(cols)
        have = new if have.empty else have.join(new, how="outer")
        SVIF.parent.mkdir(parents=True, exist_ok=True)
        have.to_csv(SVIF, compression="gzip")
    return have


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    cid, sec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and sec):
        res["verdict"], res["why"] = "⏳", "열쇠 없음 — 깃허브 Secrets 에 NAVER_CLIENT_ID · NAVER_CLIENT_SECRET 를 넣으면 돌아감"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(res["why"])
        return
    U = json.load(open(ROOT / "src" / "lab" / "accum_uni" / "KR.json", encoding="utf-8"))["u"]
    name_of = {t: n for t, n in U}
    log = {}
    idx = AB.idx_series("^KS11")
    data = AB.download([t for t, _ in U], log, time.time())
    res["log"]["px"] = log
    print("prices", len(data), round(time.time() - t0), flush=True)
    # 사건 먼저 → 사건이 있는 종목만 검색량 받기(호출 아끼기)
    _, minp, minvol = AB.MKT["KR"]
    cost = AB.COST["KR"]
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        c = F["c"]
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        gapev = F["liq"] & (F["gap"] >= 0.04) & (F["gap"] <= 0.08) & (F["vr"] >= 1.5) & (F["vr"] <= 6) & (F["o"] > F["ph"]) & (c > F["hi60"])
        nhev = F["liq"] & F["nh"] & (F["vr"] >= 1.5)
        for kind, ev in (("gap", gapev), ("nh", nhev)):
            for ti in np.where(ev & (np.arange(n) >= 260))[0]:
                if ti + 1 >= n or str(dates[ti].date()) < IS_START:
                    continue
                r = dict(tk=t, name=name_of.get(t), kind=kind, mkt="KR", date=str(dates[ti].date()), ti=int(ti))
                r.update(KI.outcomes(c, F["ma20"], ixa, ti + 1, cost))
                rows.append(r)
    df = pd.DataFrame(rows)
    print("events", len(df), flush=True)
    names = sorted(df["name"].dropna().unique(), key=lambda x: -int((df["name"] == x).sum()))
    svi = fetch_svi(names, cid, sec, res["log"])
    if svi.empty:
        res["verdict"], res["why"] = "⏳", f"검색량을 못 받음 ({res['log'].get('svi_err') or res['log'].get('svi_errs')})"
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(res["why"])
        return
    mult = {}
    for nm in svi.columns:
        s = svi[nm].asfreq("D").fillna(0.0)
        base = s.shift(1).rolling(56, min_periods=40).mean()
        mult[nm] = (s / base.replace(0, np.nan))
    def m_of(r):
        s = mult.get(r["name"])
        if s is None:
            return np.nan
        try:
            return float(s.loc[pd.Timestamp(r["date"])])
        except KeyError:
            return np.nan
    df["svi_x"] = df.apply(m_of, axis=1)
    df = df.dropna(subset=["svi_x"])
    print("events with svi", len(df), flush=True)
    J = {}
    for kind, kn in (("gap", "📈 돌파 갭 대용"), ("nh", "☕ 컵 돌파 대용"), ("all", "둘 다")):
        d = df if kind == "all" else df[df["kind"] == kind]
        per = {"IS": AB.dedupe(d[d["date"] <= IS_END]), "OOS": AB.dedupe(d[d["date"] >= OOS_START])}
        for ex in ("kk", "f20", "f10"):
            col = "x_" + ex
            grid = {}
            for k in KS:
                row = {}
                for pn, s in per.items():
                    s = s.dropna(subset=[col])
                    hot, calm = s[s["svi_x"] >= k], s[s["svi_x"] < k]
                    row[pn] = {"hot": KI.evals(hot, ex), "calm": KI.evals(calm, ex), "hot_share": round(len(hot) / max(1, len(s)) * 100, 1)}
                grid[k] = row
            ok = [k for k in KS if (grid[k]["IS"]["hot"]["x"].get("n") or 0) >= 30]
            E = {"grid": {str(k): {pn: {"hot_x": v["hot"]["x"], "calm_x": v["calm"]["x"], "hot_pf": v["hot"]["r"].get("pf"),
                                         "calm_pf": v["calm"]["r"].get("pf"), "hot_share": v["hot_share"]} for pn, v in grid[k].items()} for k in KS}}
            if not ok:
                E["verdict"], E["why"] = "➖", "앞 기간 과열 표본 부족"
                J[f"{kind}|{ex}"] = E
                continue
            k = max(ok, key=lambda k: (grid[k]["IS"]["calm"]["x"].get("avg") or 0) - (grid[k]["IS"]["hot"]["x"].get("avg") or 0))
            o = grid[k]["OOS"]
            ha, ca = o["hot"]["x"].get("avg"), o["calm"]["x"].get("avg")
            hp, cp = o["hot"]["r"].get("pf") or 0, o["calm"]["r"].get("pf") or 0
            hy, cy = o["hot"].get("by_year") or {}, o["calm"].get("by_year") or {}
            yrs = [y for y in cy if y in hy]
            worse = sum(1 for y in yrs if (hy[y]["x"] or 0) < (cy[y]["x"] or 0))
            hn = o["hot"]["x"].get("n") or 0
            if ha is None or ca is None or hn < 30:
                vd = "➖"
            elif ha <= ca - 0.5 and hp < cp and worse * 2 > len(yrs):
                vd = "✅"
            elif ha > ca:
                vd = "❌"
            else:
                vd = "➖"
            E.update({"pick_k": k, "verdict": vd,
                      "why": f"고른 배수 {k}배 · 시험 기간 과열 {hn}건 초과 {ha}% (손익비 {hp}) vs 조용 {o['calm']['x'].get('n')}건 {ca}% (손익비 {cp}) · 과열이 나빴던 해 {worse}/{len(yrs)}",
                      "by_year": {y: {"hot": hy[y]["x"], "calm": cy[y]["x"]} for y in yrs}})
            J[f"{kind}|{ex}"] = E
            print(kind, ex, vd, E["why"], flush=True)
    res["q184"] = J
    res["n_events_svi"] = int(len(df))
    res["sec"] = round(time.time() - t0)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    df.to_csv(ROOT / "market" / "lab" / "k1013_q18_attn_rows.csv.gz", index=False, compression="gzip")
    print("done", res["sec"])


if __name__ == "__main__":
    main()
