"""📈 11/02 10시 — 🗑 「S&P500 에서 쫓겨난 종목」(억지 매도 뒤 되돌림) 처음으로 숫자 재기
결과 → market/lab/k1102_dumped.json

왜: Q17-2(10/13 ⏳)·10/30 12시 탈락 사유 「편출 역사 목록 없음」. 위키백과 'List of S&P 500 companies' 의
    「Selected changes」 표(날짜·편입·편출 티커·사유)로 목록을 처음 만든다.
    발상: Research Affiliates 「Nixed: The Upside of Getting Dumped」(2024) — 편출 종목은 편출 뒤 5년 연 +5%↑ 초과.
    인덱스 펀드가 「규칙 때문에」 판 매물 → 반대 성격이라 킥(오르는 것 따라가기)과 덜 겹침.
사건: 편출 효력일 이후에도 yfinance 일봉이 이어지는 종목(인수 합병으로 사라진 건 자동 제외 = 억지 매도 아닌 것 빠짐).
진입: 효력일 + 지연 D 거래일 종가(목록은 효력일 며칠 전 공개 → 미리 앎) · 보유 H 거래일 · 왕복 비용 0.5%.
비교: SPY 초과 · MDY(S&P400 — 대부분 400 으로 강등) 초과.
판(결과 보기 전 정함): D ∈ {0,5,20} × H ∈ {20,60,120,250} — 앞(2008-07~2016) 1등(n≥30) → 뒤(2017~) 시험.
판정 ✅: 뒤 SPY·MDY 초과 둘 다 > 0, 이웃(H ±20%·D 이웃) 뒤 모두 +, 동일가중 바스켓 뒤 연수익 > SPY.
한계(결과에 적음): ① 오늘 상장 폐지된 파산 종목은 yfinance 에 없음 → 위로 치우침 ② 티커 재사용(다른 회사가 같은 티커)은 못 거름
  — 효력일 전후 가격이 끊기지 않고 효력일 전 60일 자료 있는 것만 씀 ③ 위키 표가 2008 이전·일부 해 빠짐.
"""
import json, re, sys, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, requests
from bs4 import BeautifulSoup
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "market" / "lab" / "k1102_dumped.json"
IS_START, IS_END, OOS_START = "2008-07-01", "2016-12-31", "2017-01-01"
COST = 0.5
DS, HS = [0, 5, 20], [20, 60, 120, 250]


def changes():
    ua = {"User-Agent": "k1102-lab/1.0 (https://github.com/chkchp0702-spec/market-strategy-report; research)"}
    tab = None
    for url in ["https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                "https://en.wikipedia.org/w/api.php?action=parse&page=List_of_S%26P_500_companies&prop=text&format=json&formatversion=2"]:
        try:
            rq = requests.get(url, headers=ua, timeout=60)
            h = rq.text
            if "api.php" in url:
                h = rq.json()["parse"]["text"]
        except Exception as e:
            print("fetch fail", url, e); continue
        print("fetched", url, rq.status_code, len(h))
        soup = BeautifulSoup(h, "html.parser")
        tab = soup.find("table", {"id": "changes"})
        if tab is None:
            for tb in soup.find_all("table"):
                tx = tb.get_text(" ")[:3000]
                if "Removed" in tx and "Reason" in tx:
                    tab = tb; break
        if tab is not None:
            break
    if tab is None:
        raise SystemExit("변경 표 못 찾음")
    rows = []
    for tr in tab.find_all("tr"):
        td = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(td) < 6:
            continue
        try:
            d = pd.to_datetime(td[0])
        except Exception:
            continue
        rows.append({"date": d.strftime("%Y-%m-%d"), "add": td[1], "rem": td[3], "rem_name": td[4], "why": td[5][:160]})
    return rows


def main():
    ev = [r for r in changes() if r["rem"] and r["date"] >= "2007-01-01"]
    print("changes rows with removal since 2007:", len(ev))
    tick = sorted({r["rem"].replace(".", "-").split()[0] for r in ev})
    px = yf.download(tick + ["SPY", "MDY"], start="2006-06-01", auto_adjust=True, progress=False, threads=True)["Close"]
    px = px.dropna(how="all")
    spy, mdy = px["SPY"], px["MDY"]
    idx = px.index
    trades, skipped = [], {"no_data": 0, "gap": 0, "short_after": 0}
    for r in ev:
        t = r["rem"].replace(".", "-").split()[0]
        if t not in px:
            skipped["no_data"] += 1; continue
        s = px[t]
        e = idx.searchsorted(pd.Timestamp(r["date"]))
        if e >= len(idx) or e < 60:
            skipped["no_data"] += 1; continue
        pre = s.iloc[e - 60:e]
        if pre.isna().mean() > 0.1:
            skipped["gap"] += 1; continue
        post = s.iloc[e:e + 25]
        if post.isna().sum() > 2 or len(post) < 20:
            skipped["short_after"] += 1; continue
        pre250 = s.iloc[max(0, e - 250):e]
        for D in DS:
            for H in [int(round(h * k)) for h in HS for k in (0.8, 1.0, 1.2)]:
                a, b = e + D, e + D + H
                if b >= len(idx):
                    continue
                pa, pb = s.iloc[a], s.iloc[b]
                if not (pa > 0) or np.isnan(pb):
                    # 중간에 사라짐(파산·인수) → 마지막 가격으로 정리
                    seg = s.iloc[a:b + 1].dropna()
                    if not (pa > 0) or len(seg) < 2:
                        continue
                    pb = seg.iloc[-1]
                rr = (pb / pa - 1) * 100 - COST
                trades.append({"t": t, "date": idx[a].strftime("%Y-%m-%d"), "D": D, "H": H, "r": rr,
                               "xs": rr - (spy.iloc[b] / spy.iloc[a] - 1) * 100,
                               "xm": rr - (mdy.iloc[b] / mdy.iloc[a] - 1) * 100,
                               "pre1y": (s.iloc[e - 1] / pre250.dropna().iloc[0] - 1) * 100 if len(pre250.dropna()) else None})
    df = pd.DataFrame(trades)
    print("trades:", len(df), skipped)

    def st(g):
        if len(g) == 0:
            return None
        w, l = g.xs[g.xs > 0].sum(), -g.xs[g.xs < 0].sum()
        return {"n": int(len(g)), "names": int(g.t.nunique()), "r": round(g.r.mean(), 2), "xs": round(g.xs.mean(), 2),
                "xs_med": round(g.xs.median(), 2), "xm": round(g.xm.mean(), 2), "win_xs": int(round((g.xs > 0).mean() * 100)),
                "pf_xs": round(w / l, 2) if l > 0 else None}

    isd = df[(df.date >= IS_START) & (df.date <= IS_END)]
    oos = df[df.date >= OOS_START]
    grid = {}
    for D in DS:
        for H in HS:
            k = f"D{D}_H{H}"
            grid[k] = {"is": st(isd[(isd.D == D) & (isd.H == H)]), "oos": st(oos[(oos.D == D) & (oos.H == H)])}
    cand = [(k, v["is"]["xs"]) for k, v in grid.items() if v["is"] and v["is"]["n"] >= 30]
    best = max(cand, key=lambda x: x[1])[0] if cand else None
    D0, H0 = (int(x[1:]) for x in best.split("_")) if best else (0, 60)
    nb = {}
    for D in DS:
        for H in [int(round(H0 * k)) for k in (0.8, 1.0, 1.2)]:
            nb[f"D{D}_H{H}"] = {"is": st(isd[(isd.D == D) & (isd.H == H)]), "oos": st(oos[(oos.D == D) & (oos.H == H)])}
    # 해마다(뒤 구간 한 해 쏠림 확인)
    by_year = {}
    g = df[(df.D == D0) & (df.H == H0)].copy()
    g["y"] = g.date.str[:4]
    for y, gg in g.groupby("y"):
        by_year[y] = st(gg)
    # 동일가중 바스켓(편출 뒤 H0 동안 보유, 매일 평균) 연수익 vs SPY
    rets = px.pct_change()
    hold = pd.DataFrame(0.0, index=idx, columns=[])
    w = {}
    for _, r in g.iterrows():
        a = idx.searchsorted(pd.Timestamp(r.date))
        w.setdefault(r.t, []).append((a + 1, a + H0))
    mask = pd.DataFrame(False, index=idx, columns=sorted(w))
    for t, lst in w.items():
        for a, b in lst:
            mask.iloc[a:b + 1, mask.columns.get_loc(t)] = True
    rr = rets[mask.columns].where(mask)
    bask = rr.mean(axis=1)
    cnt = mask.sum(axis=1)
    bask = bask.where(cnt > 0, 0.0).fillna(0.0)  # 빈 날 = 현금 0%

    def cagr(x, a, b):
        x = x[(x.index >= a) & (x.index <= b)]
        if len(x) < 50:
            return None
        nav = (1 + x).cumprod()
        yrs = len(x) / 252
        dd = (nav / nav.cummax() - 1).min() * 100
        return {"cagr": round((nav.iloc[-1] ** (1 / yrs) - 1) * 100, 2), "mdd": round(dd, 1),
                "vol": round(x.std() * np.sqrt(252) * 100, 1)}
    spr = rets["SPY"].fillna(0)
    basket = {"is": cagr(bask, IS_START, IS_END), "oos": cagr(bask, OOS_START, "2100"),
              "spy_is": cagr(spr, IS_START, IS_END), "spy_oos": cagr(spr, OOS_START, "2100"),
              "avg_names_held": round(float(cnt[cnt > 0].mean()), 1), "pct_days_held": round(float((cnt > 0).mean() * 100), 1)}
    bo = grid.get(best, {}).get("oos") or {}
    nb_ok = all((v["oos"] or {}).get("xs", -1) > 0 for v in nb.values())
    verdict = "✅" if (bo.get("xs", -1) > 0 and bo.get("xm", -1) > 0 and nb_ok
                      and (basket["oos"] or {}).get("cagr", -99) > (basket["spy_oos"] or {}).get("cagr", 99)) else "❌"
    out = {"at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "n_changes": len(ev), "skipped": skipped,
           "n_trades_all_cells": int(len(df)), "best_is": best, "grid": grid, "neighbors": nb, "by_year_best": by_year,
           "basket_best": basket, "verdict": verdict,
           "pre1y_med": round(float(g.pre1y.dropna().median()), 1) if len(g) else None,
           "caveat": "생존 편향: 파산·상장폐지 종목은 yfinance 에 없음(위로 치우침) · 티커 재사용 못 거름 · 위키 표 누락 가능",
           "sample": g.head(15)[["t", "date", "r", "xs"]].round(2).to_dict("records")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: out[k] for k in ["best_is", "verdict", "basket_best"]}, ensure_ascii=False))
    print(json.dumps(grid, ensure_ascii=False))


if __name__ == "__main__":
    main()
