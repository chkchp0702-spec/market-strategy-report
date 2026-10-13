"""📈 Q16-5 🕵 내부자 「평소와 다른」 매수 — 과거 검증 (사용자 10/13: "16-2,3,5 진행하고 반영시켜")
자료: SEC 「Insider Transactions Data Sets」(Form 3·4·5 분기 묶음, 2009~) https://www.sec.gov/dera/data/form-345
결과 → market/lab/k1013_insider.json · 매일 신호용 습관 매매 장부 → market/insider_hist.json.gz

근거: Cohen·Malloy·Pomorski (J. of Finance 2012) — 같은 달에 해마다 사고파는 「습관형」 내부자는 예측력 0, 나머지 「기회형」만 다음 달 초과 수익.
정의 (결과 보기 전에 정함):
  · 장내 매수 = Form 4 · 거래 코드 P. 매도(S)는 습관 판정에만 씀.
  · 습관형(routine) = 그 거래 해 기준 직전 3년 「모두」 같은 달에 그 회사 주식을 장내 매매(P 또는 S)한 사람.
  · 기회형 A(넓게) = 습관형이 아닌 모든 매수자(처음 사는 사람 포함) · 기회형 B(논문 그대로) = 직전 3년 해마다 매매는 했지만 습관형이 아닌 사람.
  · 신호 = 한 회사에서 기회형 매수자 k명(1·2·3) 이상이 「공시일 기준 10일 안」에 사고 합계 금액 ≥ v(5만·10만·25만 달러) → 마지막 공시일 다음 거래일 종가에 진입.
  · 비용 왕복 0.5% · 초과 = S&P500 대비 · 같은 종목 20거래일 안 재신호 무시 · 앞 2012~2019 고르고 2020~ 시험.
  · 유니버스 = 오늘 S&P500+400 (생존자 편향). 판정 = src/kick_ideas_bt.py verdict() 와 같음.
"""
import io, json, sys, time, zipfile, gzip, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1013_insider.json"
HIST = ROOT / "market" / "lab" / "insider_hist.json.gz"   # lab 워크플로는 market/lab 만 저장 → 뒤에 market/ 로 옮김
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"
UA = {"User-Agent": "CH-Investing-Research research-bot@users.noreply.github.com", "Accept-Encoding": "gzip, deflate"}
IS_START, IS_END, OOS_START = "2012-01-01", "2019-12-31", "2020-01-01"
COST = 0.005
BUDGET = 22 * 60


def _read(z, name, cols):
    nm = next((n for n in z.namelist() if n.upper().endswith(name)), None)
    if not nm:
        return pd.DataFrame(columns=cols)
    with z.open(nm) as f:
        d = pd.read_csv(f, sep="\t", dtype=str, on_bad_lines="skip", quoting=3, low_memory=False)
    d.columns = [c.strip().upper() for c in d.columns]
    return d[[c for c in cols if c in d.columns]]


def _date(s):
    s = s.astype(str).str.strip()
    a = pd.to_datetime(s, format="%d-%b-%Y", errors="coerce")
    b = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    return a.fillna(b)


def parse_zip(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    sub = _read(z, "SUBMISSION.TSV", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERTRADINGSYMBOL"])
    own = _read(z, "REPORTINGOWNER.TSV", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
    tr = _read(z, "NONDERIV_TRANS.TSV", ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    tr = tr[tr["TRANS_CODE"].isin(["P", "S"])]
    sub = sub[sub["DOCUMENT_TYPE"].astype(str).str.strip().isin(["4", "4/A"])]
    own = own.drop_duplicates("ACCESSION_NUMBER")      # 여러 사람이 함께 낸 공시는 첫 사람만 (단순화)
    d = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    d["fd"], d["td"] = _date(d["FILING_DATE"]), _date(d["TRANS_DATE"])
    d["val"] = pd.to_numeric(d["TRANS_SHARES"], errors="coerce") * pd.to_numeric(d["TRANS_PRICEPERSHARE"], errors="coerce")
    d["tk"] = d["ISSUERTRADINGSYMBOL"].astype(str).str.upper().str.strip().str.replace(".", "-", regex=False)
    return d[["fd", "td", "TRANS_CODE", "val", "tk", "ISSUERCIK", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"]].rename(
        columns={"TRANS_CODE": "code", "ISSUERCIK": "icik", "RPTOWNERCIK": "ocik", "RPTOWNER_RELATIONSHIP": "rel"})


def fetch_sec(log, t0):
    import requests
    parts = []
    now = dt.date.today()
    qs = [(y, q) for y in range(2009, now.year + 1) for q in (1, 2, 3, 4)]
    got = []
    for y, q in qs:
        if time.time() - t0 > BUDGET:
            log["sec_cut"] = f"{y}q{q}"
            break
        blob = None
        for att in range(3):
            try:
                r = requests.get(URL.format(y=y, q=q), headers=UA, timeout=120)
                if r.status_code == 404:
                    break
                r.raise_for_status()
                blob = r.content
                break
            except Exception as e:
                log.setdefault("sec_err", []).append(f"{y}q{q}:{repr(e)[:80]}")
                time.sleep(3 * (att + 1))
        if blob is None:
            continue
        try:
            parts.append(parse_zip(blob))
            got.append(f"{y}q{q}")
        except Exception as e:
            log.setdefault("sec_err", []).append(f"{y}q{q} parse:{repr(e)[:120]}")
        time.sleep(0.3)
    log["sec_quarters"] = got
    d = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    log["sec_rows"] = int(len(d))
    return d


def classify(d):
    """습관형·기회형 표시. 해당 해 직전 3년 같은 달 매매 여부."""
    d = d.dropna(subset=["td", "fd"]).copy()
    d = d[d["ocik"].notna() & (d["tk"] != "") & (d["tk"] != "NAN") & (d["tk"] != "NONE")]
    d["y"], d["m"] = d["td"].dt.year, d["td"].dt.month
    key = d["ocik"].astype(str) + "|" + d["icik"].astype(str)
    d["key"] = key
    ym = set(zip(key, d["y"], d["m"]))
    yy = set(zip(key, d["y"]))
    k, y, m = d["key"].to_numpy(), d["y"].to_numpy(), d["m"].to_numpy()
    d["routine"] = [all((a, b - i, c) in ym for i in (1, 2, 3)) for a, b, c in zip(k, y, m)]
    d["hist3"] = [all((a, b - i) in yy for i in (1, 2, 3)) for a, b in zip(k, y)]
    return d


def signals(buys, kmin, vmin, mode):
    """회사별로 공시일 순 10일 창 → 기회형 매수자 kmin 명 · 합계 vmin 달러 이상이 되는 첫 날 = 신호 (다음 신호는 20일 뒤부터는 dedupe 가 처리)"""
    b = buys[~buys["routine"]]
    if mode == "B":
        b = b[b["hist3"]]
    b = b[b["val"] > 0]
    out = []
    for tk, g in b.groupby("tk"):
        g = g.sort_values("fd")
        fd, oc, vv = g["fd"].to_numpy(), g["ocik"].to_numpy(), g["val"].to_numpy()
        j = 0
        last = None
        for i in range(len(g)):
            while fd[i] - fd[j] > np.timedelta64(10, "D"):
                j += 1
            ow = set(oc[j:i + 1])
            if len(ow) >= kmin and vv[j:i + 1].sum() >= vmin:
                if last is None or fd[i] - last > np.timedelta64(30, "D"):
                    out.append((tk, pd.Timestamp(fd[i]), len(ow), float(vv[j:i + 1].sum())))
                    last = fd[i]
    return pd.DataFrame(out, columns=["tk", "fd", "nown", "val"])


def outcomes(sig, data, idx):
    rows = []
    for tk, g in sig.groupby("tk"):
        if tk not in data:
            continue
        d = data[tk]
        c = d["close"].to_numpy(float)
        ma20 = pd.Series(c).rolling(20).mean().to_numpy()
        ixa = idx.reindex(d.index).ffill().to_numpy(float)
        di = d.index
        for _, s in g.iterrows():
            e = int(di.searchsorted(s["fd"], side="right"))       # 공시일 「다음」 거래일 종가
            if e >= len(di) - 1 or e < 1:
                continue
            r = dict(tk=tk, mkt="US", date=str(s["fd"].date()), ti=e, nown=int(s["nown"]), val=round(s["val"]))
            r.update(KI.outcomes(c, ma20, ixa, e, COST))
            rows.append(r)
    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    log = {}
    raw = fetch_sec(log, t0)
    print("sec", log.get("sec_rows"), len(log.get("sec_quarters", [])), round(time.time() - t0), flush=True)
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "log": log, "rule": __doc__}
    if not len(raw):
        res["verdict"], res["why"] = "❌", "SEC 자료를 못 받음"
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        return
    d = classify(raw)
    uni = set(AB.universe("US", {}))
    d = d[d["tk"].isin(uni)]
    log["rows_in_universe"] = int(len(d))
    # 매일 신호용 습관 장부: (사람|회사) → 최근 4년 매매한 (해-달) 목록
    cut = d["y"].max() - 4
    h = d[d["y"] >= cut].groupby("key").apply(lambda g: sorted({f"{a}-{b:02d}" for a, b in zip(g["y"], g["m"])}), include_groups=False).to_dict()
    with gzip.open(HIST, "wt", encoding="utf-8") as f:
        json.dump({"made": res["made"], "to": str(d["td"].max().date()), "h": h}, f)
    log["hist_keys"] = len(h)
    buys = d[d["code"] == "P"]
    log["buys"] = int(len(buys))
    log["buys_routine_share"] = round(float(buys["routine"].mean()) * 100, 1) if len(buys) else None
    dlog = {}
    data = AB.download(sorted(set(AB.universe("US", dlog)) & set(buys["tk"].unique()) | {"SPY"}), dlog, time.time())
    idx = AB.idx_series("^GSPC")
    log["prices"] = dlog
    print("prices", len(data), round(time.time() - t0), flush=True)
    grid, cache = [], {}
    for mode in ("A", "B"):
        for kmin in (1, 2, 3):
            for vmin in (50_000, 100_000, 250_000):
                nm = f"기회형{mode}|{kmin}명↑|{vmin // 1000}천달러↑"
                sg = signals(buys, kmin, vmin, mode)
                df = outcomes(sg, data, idx)
                if not len(df):
                    continue
                df = df[df["date"] >= IS_START]
                for pn, x in (("IS", df[df["date"] <= IS_END]), ("OOS", df[df["date"] >= OOS_START])):
                    cache[(nm, pn)] = AB.dedupe(x)
                for ex in ("f20", "f40", "kk"):
                    grid.append((nm, ex, KI.evals(cache[(nm, "IS")], ex)))
    # 비교용: 습관형만
    sg = signals(buys.assign(routine=~buys["routine"]), 1, 50_000, "A")
    rdf = outcomes(sg, data, idx)
    if len(rdf):
        rdf = AB.dedupe(rdf[rdf["date"] >= IS_START])
        res["routine_only"] = {ex: KI.evals(rdf, ex) for ex in ("f20", "kk")}
    ok = [g for g in grid if g[2]["x"].get("n", 0) >= 100 and (g[2]["x"].get("avg") or -9) > 0 and (g[2]["r"].get("pf") or 0) >= 1.3]
    ok.sort(key=lambda g: -g[2]["x"]["avg"])
    if not grid:
        res["verdict"], res["why"] = "❌", "신호 없음"
    else:
        pick = ok[0] if ok else max(grid, key=lambda g: (g[2]["x"].get("avg") or -99) if g[2]["x"].get("n", 0) >= 50 else -99)
        nm, ex, ins = pick
        oos = KI.evals(cache[(nm, "OOS")], ex)
        vd, why = KI.verdict(oos)
        if not ok and vd in ("✅", "🧪"):
            vd, why = ("👻" if (oos["r"].get("avg") or 0) > 0 else "❌"), why + " — 앞 기간 기준 통과 규칙 없음 → 채택 안 함"
        top = []
        for g in sorted(grid, key=lambda g: -(g[2]["x"].get("avg") or -99))[:15]:
            oo = KI.evals(cache[(g[0], "OOS")], g[1])
            top.append({"rule": g[0], "exit": g[1], "IS_n": g[2]["x"].get("n"), "IS_x": g[2]["x"].get("avg"), "IS_pf": g[2]["r"].get("pf"),
                        "OOS_n": oo["x"].get("n"), "OOS_x": oo["x"].get("avg"), "OOS_pf": oo["r"].get("pf")})
        res.update({"pick": {"rule": nm, "exit": ex, "exit_doc": KI.EXIT_DOC[ex]}, "IS": ins, "OOS": oos, "verdict": vd, "why": why, "top": top, "n_pass_IS": len(ok)})
    res["sec"] = round(time.time() - t0)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k not in ("rule", "top")}, ensure_ascii=False, default=str)[:4000])
    print(json.dumps(res.get("top"), ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
