"""📈 11/2 12시 — 「그날 구성 종목」으로 다시 재기(생존 편향) + 🆕 S&P500 편입 직후 신호
결과 → market/lab/k1102_pit.json

왜: 지금까지 ⚡ 킥 개별주 실험(☕ 신고가·📈 갭·📊 실적 갭)은 「오늘 지수에 있는 종목」으로만 2008~ 를 쟀다
    → 나중에 커서 들어온 종목(미래의 승자)이 들어온 「전부터」 표본에 끼어 앞 구간이 부풀었을 수 있다.
    10시에 창고에 넣은 fja05680/sp500 「날짜별 S&P500 구성 종목」 CSV 로 처음 그날 기준으로 다시 잰다.
새 발상(바깥): 지수 편입은 「인덱스 펀드가 억지로 사는」 사건 — 편입 직후엔 가격 압력이 풀리며 되돌림이 있다는 연구
    (편입 효과 퇴색·편입 뒤 약세: Alpha Architect·Morningstar·S&P DJI 「Wag the dog」) → ① 편입 직후 N일 안의 ☕ 돌파는
    억지 매수가 만든 가짜 돌파인가(빼면 나아지나) ② 편입 종목을 효력일 뒤 사 들고 있으면(🆕 바스켓 칸) 이기나.
사건 = KI.ev_nh(252일 신고가 종가·거래량 1.5배) — 진입 g+1 종가 · 출구 KI.kexit · 왕복 0.5% · 초과 = S&P500 대비.
표본:
  TODAY   : 오늘(최신 CSV) S&P500 종목의 모든 사건 (= 지금까지 방식)
  PIT     : 그날 S&P500 에 있던 종목의 사건만 (편출·상폐 종목 중 yfinance 에 남은 것 포함)
  PRE     : 오늘 종목인데 사건 날엔 아직 편입 전 (= 지금까지 방식에 낀 「미래의 승자」)
편입 직후 거름(PIT 안, 앞 2008~16 에서 고름): 편입 뒤 {20,60,120,250}거래일 안 사건 vs 나머지. 이웃 ±20%.
🆕 바스켓: 편입 효력일 + D{0,5,20}거래일 종가 진입 · H{20,60,120,250}일 보유 · 초과 평균·중앙·PF, 앞 1등을 뒤에서.
생존 편향: 상장폐지·파산 종목은 yfinance 에 없어 PIT 도 아직 위로 치우침(그래도 TODAY 보다 덜함).
"""
import json, sys, time, io, re, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402

AB.START = "2006-06-01"
AB.TIME_BUDGET = 30 * 60
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1102_pit.json"
IS_START, IS_END, OOS_START = "2008-01-01", "2016-12-31", "2017-01-01"


def members():
    ls = requests.get("https://api.github.com/repos/fja05680/sp500/contents", timeout=60).json()

    def _k(f):
        m = re.search(r"\((\d\d)-(\d\d)-(\d{4})\)", f["name"])
        return (m.group(3) + m.group(1) + m.group(2)) if m else ("9" if "Updated" in f["name"] else "0")
    fs = sorted([f for f in ls if f["name"].startswith("S&P 500 Historical Components") and f["name"].endswith(".csv")], key=_k)
    f = fs[-1]
    print("fja file", f["name"], flush=True)
    df = pd.read_csv(io.StringIO(requests.get(f["download_url"], timeout=120).text))
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= "2005-01-01"].sort_values("date")
    snaps = []
    for d, s in zip(df["date"], df["tickers"]):
        cur = set()
        for x in str(s).split(","):
            x = x.strip()
            if x:
                cur.add(re.sub(r"-\d{6}$", "", x).replace(".", "-"))
        snaps.append((d, cur))
    return snaps


def intervals(snaps):
    """종목별 [들어온 날, 나간 날) 목록 + 편입 날짜(2006 이후 새로 들어온 것만)"""
    iv, adds, prev, start = {}, [], set(), {}
    first = snaps[0][0]
    for d, cur in snaps:
        for t in cur - prev:
            start[t] = d
            if d > first:
                adds.append((t, d))
        for t in prev - cur:
            iv.setdefault(t, []).append((start.pop(t), d))
        prev = cur
    for t, s in start.items():
        iv.setdefault(t, []).append((s, pd.Timestamp("2100-01-01")))
    return iv, adds, prev


def build(data, idx, iv):
    cost = AB.COST.get("US", AB.DEF_COST)
    _, minp, minvol = AB.MKT["US"]
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        c = F["c"]
        n = len(c)
        dates = d.index
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        ev = F["ev_nh"]
        tiv = iv.get(t, [])
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
            gd = dates[g]
            inn, since = False, 99999
            for a, b in tiv:
                if a <= gd < b:
                    inn = True
                    since = int(((dates > a) & (dates <= gd)).sum())
            rr = r - cost
            rows.append(dict(tk=t, date=str(gd.date()), ti=int(g), e=str(dates[e].date()), xd=str(dates[ex].date()),
                             r=round(rr * 100, 2), x=round((rr - (ixa[ex] / ixa[e] - 1)) * 100, 2), vr=float(F["vr"][g]),
                             pit=inn, since=since))
    return pd.DataFrame(rows)


def sleeve(s, slots=5):
    s = s.sort_values(["e", "vr"], ascending=[True, False])
    busy, yr = [], {}
    for e, xd, r in zip(s["e"], s["xd"], s["r"]):
        busy = [b for b in busy if b > e]
        if len(busy) >= slots:
            continue
        busy.append(xd)
        yr[e[:4]] = yr.get(e[:4], 0.0) + r / slots
    return yr


def pstats(s):
    out = {}
    for pn, a, b, ny in (("IS", IS_START, IS_END, 9), ("OOS", OOS_START, "2100", 9.8)):
        q = s[(s["date"] >= a) & (s["date"] <= b)]
        yr = sleeve(q)
        out[pn] = {**KI.pst(q["x"]), "per_yr": round(len(q) / ny, 1), "sleeve_yr": round(sum(yr.values()) / ny, 2)}
    return out


def basket(data, idx, adds, D, H):
    rows = []
    for t, d0 in adds:
        if t not in data or d0 < pd.Timestamp("2007-06-01"):
            continue
        c = data[t]["close"].to_numpy(float)
        dates = data[t].index
        i0 = int(np.searchsorted(dates, d0))
        e, x = i0 + D, i0 + D + H
        if x >= len(c) or i0 >= len(c) or (dates[min(i0, len(c) - 1)] - d0).days > 7:
            continue
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        if not (c[e] > 0 and ixa[e] > 0):
            continue
        r = c[x] / c[e] - 1 - 0.005
        rows.append(dict(tk=t, date=str(dates[e].date()), r=r * 100, x=(r - (ixa[x] / ixa[e] - 1)) * 100))
    df = pd.DataFrame(rows)
    out = {}
    for pn, a, b in (("IS", IS_START, IS_END), ("OOS", OOS_START, "2100")):
        q = df[(df["date"] >= a) & (df["date"] <= b)] if len(df) else df
        if len(q) == 0:
            out[pn] = {"n": 0}
            continue
        w, l = q["x"][q["x"] > 0].sum(), -q["x"][q["x"] < 0].sum()
        out[pn] = {"n": int(len(q)), "xs": round(q["x"].mean(), 2), "xs_med": round(q["x"].median(), 2),
                   "win": int(round((q["x"] > 0).mean() * 100)), "pf": round(w / l, 2) if l > 0 else None}
    return out


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = res["log"]
    try:
        snaps = members()
        iv, adds, today = intervals(snaps)
        ever = sorted(set(iv) | today)
        log["n_ever"], log["n_today"], log["n_adds"] = len(ever), len(today), len(adds)
        print("ever", len(ever), "today", len(today), "adds", len(adds), flush=True)
        idx = AB.idx_series("^GSPC")
        data = AB.download(ever, log, time.time())
        log["n_dl"] = len(data)
        log["n_dl_gone"] = len([t for t in data if t not in today])
        log["sec_dl"] = round(time.time() - t0)
        ev = AB.dedupe(build(data, idx, iv)).reset_index(drop=True)
        ev["today"] = ev["tk"].isin(today)
        log["n_ev"] = int(len(ev))
        S = {"TODAY": ev[ev["today"]], "PIT": ev[ev["pit"]], "PRE": ev[ev["today"] & ~ev["pit"]],
             "PIT_GONE": ev[ev["pit"] & ~ev["today"]], "TODAY_IN": ev[ev["today"] & ev["pit"]]}
        res["samples"] = {k: pstats(v) for k, v in S.items()}
        print({k: (v["IS"].get("n"), v["IS"].get("avg"), v["OOS"].get("n"), v["OOS"].get("avg"), v["IS"]["sleeve_yr"], v["OOS"]["sleeve_yr"])
               for k, v in res["samples"].items()}, flush=True)
        # 편입 직후 거름
        P = S["PIT"]
        G = {}
        for N in (16, 20, 24, 48, 60, 72, 96, 120, 144, 200, 250, 300):
            G[f"in{N}"] = pstats(P[P["since"] <= N])
            G[f"out{N}"] = pstats(P[P["since"] > N])
        res["since_grid"] = G
        base_is = res["samples"]["PIT"]["IS"].get("avg", 0)
        cand = []
        for N in (20, 60, 120, 250):
            o = G[f"out{N}"]["IS"]
            cand.append((o.get("avg", -99) - base_is, N))
        dN = max(cand)[1]
        nbN = {20: (16, 24), 60: (48, 72), 120: (96, 144), 250: (200, 300)}[dN]
        b0 = res["samples"]["PIT"]
        pk = G[f"out{dN}"]
        c1 = pk["IS"].get("avg", -99) > b0["IS"].get("avg", 99) and pk["OOS"].get("avg", -99) > b0["OOS"].get("avg", 99)
        c2 = all(G[f"out{m}"]["OOS"].get("avg", -99) > b0["OOS"].get("avg", 99) and G[f"out{m}"]["IS"].get("avg", -99) > b0["IS"].get("avg", 99) for m in nbN)
        c3 = pk["OOS"]["sleeve_yr"] > b0["OOS"]["sleeve_yr"]
        res["since_pick"] = {"N": dN, "checks": {"both": c1, "nb": c2, "sleeve": c3},
                             "verdict": "✅" if (c1 and c2 and c3) else ("🟡" if (c1 and (c2 or c3)) else "❌"),
                             "summary": f"편입 뒤 {dN}일 안 돌파 빼기: 앞 {pk['IS'].get('avg')} vs {b0['IS'].get('avg')} · 뒤 {pk['OOS'].get('avg')} vs {b0['OOS'].get('avg')} · 칸 뒤 {pk['OOS']['sleeve_yr']} vs {b0['OOS']['sleeve_yr']}"}
        print(res["since_pick"], flush=True)
        # 🆕 바스켓
        B = {}
        for D in (0, 5, 20):
            for H in (20, 60, 120, 200, 250, 300):
                B[f"D{D}_H{H}"] = basket(data, idx, adds, D, H)
        res["add_basket"] = B
        best = max(((v["IS"].get("xs", -99), k) for k, v in B.items() if k.split("_H")[1] in ("20", "60", "120", "250")))[1]
        res["add_pick"] = {"cell": best, "IS": B[best]["IS"], "OOS": B[best]["OOS"]}
        print("adds", res["add_pick"], {k: (v["IS"].get("xs"), v["OOS"].get("xs")) for k, v in B.items()}, flush=True)
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
