"""📈 Q11-3 🐋 13D 「일주일 늦은 고래」 — 과거 검증 (사용자 10/14 「1,3,4 실행」)
k1014_q11 점검: SEC www.sec.gov·data.sec.gov 는 깃허브 실행기에서 403, EDGAR 전체 검색(efts.sec.gov)은 브라우저 머리글로 200 → 그걸로 모음.
결과 → market/lab/k1014_q113.json · 사건표 market/lab/k1014_q113_rows.csv.gz

정의 (결과 보기 전에 정함):
  · 사건 = Schedule 13D 「첫」 공시(SC 13D · 2025~ SCHEDULE 13D, 정정 /A 제외) 중 대상 회사가 오늘 S&P500+400 (생존자 편향)
  · 진입 = 공시일 「다음」 거래일 종가 · 비용 왕복 0.5% · 초과 = S&P500 대비 · 같은 종목 20거래일 안 재공시 무시
  · 주 성적 = 60거래일 보유(x60) · 참고 = 킥 규칙 출구(x_kk)·20·40일
  · 앞 2008~2016 · 시험 2017~ · 판정 = src/kick_ideas_bt.py verdict()(시험 기간 n≥100 · 초과 > 0 · 손익비 ≥ 1.3 · 가장 좋은 해 빼도 +)
  · 묶음: ① 전체 13D(주 판정) ② 고래 명단 펀드(whale40 signals.json 의 by 이름과 공시자 이름이 겹침) — 표본 작으면 참고만
"""
import json, re, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402
AB.START = "2006-06-01"
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q113.json"
ROWS = ROOT / "market" / "lab" / "k1014_q113_rows.csv.gz"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "application/json"}
EFTS = "https://efts.sec.gov/LATEST/search-index"
IS_END, OOS = "2016-12-31", "2017-01-01"
COST = 0.005
TKRE = re.compile(r"\(([A-Z0-9.\-]{1,7}(?:,\s*[A-Z0-9.\-]{1,7})*)\)\s*\(CIK")
res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}


def get(params):
    for att in range(4):
        try:
            r = requests.get(EFTS, params=params, headers=UA, timeout=40)
            if r.status_code == 200:
                return r.json()
            res["log"].setdefault("codes", {}).setdefault(str(r.status_code), 0)
            res["log"]["codes"][str(r.status_code)] += 1
        except Exception as e:
            res["log"]["last_err"] = repr(e)[:150]
        time.sleep(2 * (att + 1))
    return None


def collect():
    # 질의 방식 점검: q 없이 → 안 되면 「"Schedule 13D"」 문구
    base = {"forms": "SC 13D,SCHEDULE 13D", "dateRange": "custom", "startdt": "2015-03-01", "enddt": "2015-03-14"}
    j = get(base)
    mode = "noq" if (j and j.get("hits", {}).get("hits")) else "q"
    res["log"]["mode"] = mode
    filings = {}
    d0, end = dt.date(2008, 1, 1), dt.date.today()
    t0 = time.time()
    while d0 <= end:
        d1 = min(end, d0 + dt.timedelta(days=13))
        frm = 0
        while True:
            p = {"forms": "SC 13D,SCHEDULE 13D", "dateRange": "custom", "startdt": d0.isoformat(), "enddt": d1.isoformat(), "from": frm}
            if mode == "q":
                p["q"] = '"Schedule 13D"'
            j = get(p)
            if not j:
                res["log"].setdefault("miss", []).append(d0.isoformat())
                break
            hh = j.get("hits", {}).get("hits", [])
            for h in hh:
                s = h.get("_source", {})
                if s.get("form") not in ("SC 13D", "SCHEDULE 13D"):
                    continue
                ad = h.get("_id", "").split(":")[0]
                if ad and ad not in filings:
                    filings[ad] = {"d": s.get("file_date"), "names": s.get("display_names") or []}
            tot = j.get("hits", {}).get("total", {}).get("value", 0)
            frm += len(hh)
            if not hh or frm >= tot or frm >= 9900:
                break
            time.sleep(0.25)
        d0 = d1 + dt.timedelta(days=1)
        time.sleep(0.25)
    res["log"]["filings"] = len(filings)
    res["log"]["collect_sec"] = round(time.time() - t0)
    print("filings", len(filings), "sec", res["log"]["collect_sec"], flush=True)
    return filings


def whale_names():
    try:
        sig = requests.get("https://raw.githubusercontent.com/chkchp0702-spec/whale40/main/data/signals.json", timeout=40).json()
        nm = set()
        for q, d in sig.items():
            for t, v in d.items():
                for b in v.get("by") or []:
                    nm.add(b)
        return nm
    except Exception as e:
        res["log"]["whale_err"] = repr(e)[:150]
        return set()


def norm(s):
    s = re.sub(r"\(.*?\)", "", s.upper())
    s = re.sub(r"[^A-Z ]", " ", s)
    stop = {"LLC", "LP", "L", "P", "INC", "LTD", "CO", "CORP", "MANAGEMENT", "CAPITAL", "PARTNERS", "ADVISORS", "GROUP", "THE", "FUND", "MASTER", "INVESTMENT", "INVESTMENTS", "HOLDINGS", "LIMITED", "TRUST", "ASSOCIATES", "GP", "MGMT"}
    return " ".join(w for w in s.split() if w not in stop)


def pst(x):
    return AB.pstats(pd.Series(x, dtype=float))


def block(d, col):
    o = {"x": pst(d[col]), "r": pst(d[col.replace("x", "r", 1)])}
    by = {}
    for y, g in d.groupby(d.date.dt.year):
        by[str(y)] = {"n": len(g), "x": round(float(g[col].mean()), 2)}
    o["by_year"] = by
    if by:
        best = max(by, key=lambda y: by[y]["x"])
        rest = d[d.date.dt.year != int(best)][col]
        o["x_ex_best_year"] = round(float(rest.mean()), 2) if len(rest) else None
    return o


def main():
    t0 = time.time()
    filings = collect()
    log = {}
    tks = AB.universe("US", log)
    U = set(tks)
    WN = {norm(n) for n in whale_names()} - {""}
    res["log"]["whale_names"] = len(WN)
    ev = []
    for ad, f in filings.items():
        subj, filers = [], []
        for n in f["names"]:
            m = TKRE.search(n)
            hit = [t.strip().replace(".", "-") for t in m.group(1).split(",")] if m else []
            hit = [t for t in hit if t in U]
            (subj if hit else filers).append((n, hit))
        if len(subj) != 1:
            continue          # 대상이 우리 유니버스 1곳으로 딱 안 정해지면 버림
        fn = [norm(n) for n, _ in filers]
        ev.append({"tk": subj[0][1][0], "fd": f["d"], "filer": "; ".join(n for n, _ in filers)[:120],
                   "whale": int(any(a and (a in WN or any(a.startswith(w) or w.startswith(a) for w in WN if len(w) >= 6)) for a in fn))})
    E = pd.DataFrame(ev)
    print("events(universe)", len(E), "whale", int(E.whale.sum()) if len(E) else 0, flush=True)
    res["log"]["events_universe"] = len(E)
    need = sorted(set(E.tk)) if len(E) else []
    data = AB.download(need, log, time.time())
    idx = AB.idx_series("^GSPC")
    res["log"]["dl"] = log
    rows = []
    for t, g in E.groupby("tk"):
        if t not in data:
            continue
        d = data[t]; c = d["close"].to_numpy(float); dates = d.index
        ma20 = pd.Series(c).rolling(20).mean().to_numpy()
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        last = -10 ** 9
        for _, e in g.sort_values("fd").iterrows():
            ti = int(np.searchsorted(dates.values, np.datetime64(pd.Timestamp(e.fd)), side="right"))   # 공시일 다음 거래일
            if ti >= len(c) - 1 or ti < 25 or ti - last < 20:
                continue
            last = ti
            r = {"tk": t, "date": str(dates[ti].date()), "fd": e.fd, "whale": e.whale, "filer": e.filer}
            r.update(KI.outcomes(c, ma20, ixa, ti, COST))
            if ti + 60 < len(c) and ixa[ti] > 0:
                rr = c[ti + 60] / c[ti] - 1 - COST
                r["r_60"] = round(rr * 100, 2); r["x_60"] = round((rr - (ixa[ti + 60] / ixa[ti] - 1)) * 100, 2)
            r["pre20"] = round((c[ti - 1] / c[ti - 21] - 1) * 100, 2)
            rows.append(r)
    D = pd.DataFrame(rows)
    D["date"] = pd.to_datetime(D["date"])
    D.to_csv(ROWS, index=False, compression="gzip")
    D = D[D.date >= pd.Timestamp("2008-01-01")]
    o = {}
    for gname, G in (("all", D), ("whale", D[D.whale == 1])):
        o[gname] = {}
        for pn, P in (("IS", G[G.date <= IS_END]), ("OOS", G[G.date >= OOS])):
            o[gname][pn] = {col: block(P.dropna(subset=[col]), col) for col in ("x_60", "x_kk", "x_f20", "x_f40") if col in P}
        oos = o[gname]["OOS"].get("x_60")
        if oos:
            v, why = KI.verdict(oos)
            o[gname]["verdict"], o[gname]["why"] = v, why
        print(gname, json.dumps({pn: {c_: (o[gname][pn][c_]["x"].get("n"), o[gname][pn][c_]["x"].get("avg"), o[gname][pn][c_]["r"].get("pf")) for c_ in o[gname][pn]} for pn in ("IS", "OOS")}), o[gname].get("verdict"), flush=True)
    res["groups"] = o
    res["recent"] = D.sort_values("date").tail(15)[["tk", "fd", "whale", "filer", "x_60"]].astype(str).to_dict("records")
    res["sec"] = round(time.time() - t0)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("done", res["sec"])


main()
