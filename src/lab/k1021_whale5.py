"""🌙 10/21 밤 연구 #11 — 🐋 고래 「임팩트 5」: 10종목 같은 비중 대신 점수 상위 5개에 몰기
  고래 목록 = whale40 data/signals.json (13F 큰 신규 포지션) — 2025Q2 쯤부터 몇 분기뿐 → 2008~2016 역사가 없다.
  그래서 「앞 분기들에서 고르고 뒤 분기들에서 시험」으로 나눈다(분기 목록 앞쪽 절반 = 고르기, 뒤쪽 = 시험). 표본이 아주 작다는 한계.
  거르기는 src/kick_sleeve.whale_lists 그대로(ETF·미국 밖·바이오 펀드만 산 것·50%↑ 몰빵 공시 빼기).
  목록 공개일 = 분기 끝 +46일 → 공개일 「다음」 거래일 종가에 사서 다음 목록 공개 다음 거래일 종가까지 보유(−30% 면 그 종목만 현금).
  판단은 산 날 전날 종가까지(50일선 등). 교체 때 회전율 × 0.1% 비용.
  방식:
    now   = 지금 규칙: (겹친 고래 수 n 큰 순, 비중 w 큰 순) 상위 10 같은 비중
    w     = 새로 담은 비중 w 큰 순 상위 k
    n2    = 2곳 이상 겹친 것 먼저(그 안에서 w 순) 상위 k
    ma    = 지금 순서 중 전날 종가 > 50일선 인 것 상위 k
    score = 점수(w 순위 + n 순위 + 50일선 위 가산) 상위 k
    nowk  = 지금 순서 그대로 상위 k (몰기만의 효과)
  k = 4·5·6 (5 ±20%) · ④ 「우리 신호와 겹침」은 신호 역사가 없어 못 봄.
→ market/lab/k1021_whale5.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("market/lab/k1021_whale5.json")
RAW = "https://raw.githubusercontent.com/chkchp0702-spec/whale40/main/data/signals.json"
QEND = {"Q1": "-03-31", "Q2": "-06-30", "Q3": "-09-30", "Q4": "-12-31"}
COST = 0.001
STOP = -0.30
KS = [4, 5, 6]
MODES = ["nowk", "w", "n2", "ma", "score"]
SLEEVE = 0.15   # 지금 킥의 고래 칸 크기(10/19~)


def lists():
    from src.kick_sleeve import BIO, NOT_STOCK
    with urllib.request.urlopen(urllib.request.Request(RAW, headers={"User-Agent": "ch-lab"}), timeout=60) as r:
        sig = json.loads(r.read().decode("utf-8"))
    out, sample = [], None
    for q, d in sig.items():
        try:
            qq, yy = q.split()
            avail = (dt.date.fromisoformat(yy + QEND[qq]) + dt.timedelta(days=46)).isoformat()
        except Exception:
            continue
        rows = []
        for t, v in d.items():
            if sample is None:
                sample = {t: v}
            if t in NOT_STOCK or "." in t or not t.isalpha():
                continue
            by = v.get("by") or []
            if by and all(b in BIO for b in by):
                continue
            if max(v.get("w") or [0]) >= 50:
                continue
            rows.append({"t": t, "n": v.get("n", 1), "w": round(max(v.get("w") or [0]), 2)})
        rows.sort(key=lambda x: (-x["n"], -x["w"]))
        out.append((avail, q, rows))
    return sorted(out), sample


def pick(rows, mode, k, C, d_prev):
    ok = [r for r in rows if r["t"] in C.columns and not math.isnan(C[r["t"]].get(d_prev, float("nan")))]

    def above(t):
        s = C[t].loc[:d_prev].dropna()
        return len(s) >= 50 and s.iloc[-1] > s.iloc[-50:].mean()
    if mode == "now":
        return [r["t"] for r in ok[:10]]
    if mode == "nowk":
        return [r["t"] for r in ok[:k]]
    if mode == "w":
        return [r["t"] for r in sorted(ok, key=lambda x: -x["w"])[:k]]
    if mode == "n2":
        return [r["t"] for r in sorted(ok, key=lambda x: (x["n"] < 2, -x["w"]))[:k]]
    if mode == "ma":
        a = [r for r in ok if above(r["t"])]
        return [r["t"] for r in (a + [r for r in ok if r not in a])[:k]]
    if mode == "score":
        wr = {r["t"]: i for i, r in enumerate(sorted(ok, key=lambda x: -x["w"]))}
        nr = {r["t"]: i for i, r in enumerate(sorted(ok, key=lambda x: -x["n"]))}
        sc = {r["t"]: wr[r["t"]] + nr[r["t"]] - (len(ok) / 2 if above(r["t"]) else 0) for r in ok}
        return sorted(sc, key=lambda t: sc[t])[:k]
    raise ValueError(mode)


def run(L, C, mode, k, d_from=None, d_to=None):
    """분기 바스켓을 이어 붙인 매일 가치 + 분기별 수익"""
    idx = C.index
    starts = []
    for avail, q, rows in L:
        after = idx[idx > pd.Timestamp(avail)]
        if len(after) < 2:
            continue
        starts.append((after[0], q, rows))
    nav, v, prev, qret = {}, 1.0, set(), []
    for j, (d0, q, rows) in enumerate(starts):
        d1 = starts[j + 1][0] if j + 1 < len(starts) else idx[-1]
        if d_from and d0 < pd.Timestamp(d_from):
            continue
        if d_to and d0 > pd.Timestamp(d_to):
            continue
        dp = idx[idx.get_loc(d0) - 1]
        ts = pick(rows, mode, k, C, dp)
        if not ts:
            continue
        cur = set(ts)
        turn = 1.0 if not prev else len(cur - prev) / len(cur)
        v *= (1 - turn * COST)
        prev = cur
        seg = C.loc[d0:d1, ts].ffill()
        e = seg.iloc[0]
        rel = seg / e
        # −30% 정리: 처음 닿은 뒤로 그 값에 고정
        for t in ts:
            hit = rel[t] <= 1 + STOP
            if hit.any():
                h = hit.idxmax()
                rel.loc[h:, t] = rel.loc[h, t]
        bas = rel.mean(axis=1)
        v0 = v
        for d, x in bas.items():
            nav[d] = v0 * x
        v = v0 * bas.iloc[-1]
        sp = C.loc[d0:d1, "SPY"]
        qret.append({"q": q, "d0": str(d0.date()), "d1": str(d1.date()), "n": len(ts), "ret": round((bas.iloc[-1] - 1) * 100, 2),
                     "spy": round((sp.iloc[-1] / sp.iloc[0] - 1) * 100, 2), "pick": ts})
    s = pd.Series(nav).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s, qret


def st(nav, spy):
    nav = nav.dropna()
    if len(nav) < 20:
        return {}
    r = nav.pct_change().dropna()
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    b = spy.reindex(nav.index).ffill()
    tot, btot = nav.iloc[-1] / nav.iloc[0] - 1, b.iloc[-1] / b.iloc[0] - 1
    return {"tot": round(tot * 100, 2), "spy_tot": round(btot * 100, 2), "cagr": round(((1 + tot) ** (1 / yrs) - 1) * 100, 2),
            "spy_cagr": round(((1 + btot) ** (1 / yrs) - 1) * 100, 2), "mdd": round(((nav / nav.cummax()) - 1).min() * 100, 1),
            "spy_mdd": round(((b / b.cummax()) - 1).min() * 100, 1),
            "sharpe": round(r.mean() / r.std() * math.sqrt(252), 2) if r.std() > 0 else None,
            "spy_sharpe": round(b.pct_change().dropna().mean() / b.pct_change().dropna().std() * math.sqrt(252), 2),
            "days": len(nav), "yrs": round(yrs, 2)}


def main():
    L, sample = lists()
    print("분기", [(a, q, len(r)) for a, q, r in L], "예시", sample)
    tick = sorted({r["t"] for _, _, rows in L for r in rows} | {"SPY"})
    first = min(a for a, _, _ in L)
    s0 = (dt.date.fromisoformat(first) - dt.timedelta(days=120)).isoformat()
    px = yf.download(tick, start=s0, auto_adjust=True, progress=False, threads=True)["Close"]
    C = px.dropna(how="all")
    print("가격", C.shape, "없는 종목", [t for t in tick if t not in C.columns or C[t].isna().all()][:30])
    idx = C.index
    starts = [idx[idx > pd.Timestamp(a)][0] for a, _, _ in L if (idx > pd.Timestamp(a)).sum() >= 2]
    nq = len(starts)
    cut = starts[nq // 2] if nq >= 2 else starts[0]          # 앞 절반 분기 = 고르기, 뒤 = 시험
    is_to = str((cut - pd.Timedelta(days=1)).date())
    oos_from = str(cut.date())
    spy = C["SPY"]
    res = {"_doc": __doc__, "quarters": [(a, q, len(r)) for a, q, r in L], "split": {"is_to": is_to, "oos_from": oos_from, "nq": nq},
           "grid": {}}
    combos = [("now", 10)] + [(m, k) for m in MODES for k in KS]
    for m, k in combos:
        key = f"{m}{k}"
        full, qr = run(L, C, m, k)
        a, _ = run(L, C, m, k, d_to=is_to)
        b, qb = run(L, C, m, k, d_from=oos_from)
        res["grid"][key] = {"is": st(a, spy), "oos": st(b, spy), "full": st(full, spy), "q": qr}
        print(key, "앞", res["grid"][key]["is"].get("sharpe"), "뒤", res["grid"][key]["oos"])
    # 고르기: 앞 구간 샤프 1등 (k=5 만 후보 — 흔들기는 4·6)
    cand = {m: res["grid"][f"{m}5"]["is"].get("sharpe") or -9 for m in MODES}
    best = max(cand, key=cand.get)
    res["chosen"] = {"mode": best, "k": 5, "is_sharpe": cand}
    # 킥 칸(15%) 대신 넣었을 때 포트 영향 대략: (새 − 지금) 연수익 차 × 15%
    o_new, o_now = res["grid"][f"{best}5"]["oos"], res["grid"]["now10"]["oos"]
    if o_new and o_now:
        res["kick_effect_pp"] = round((o_new["cagr"] - o_now["cagr"]) * SLEEVE, 2)
    # 순위 상관 (앞 vs 뒤 샤프)
    ks = [f"{m}{k}" for m, k in combos]
    a = pd.Series({x: res["grid"][x]["is"].get("sharpe") for x in ks}, dtype=float)
    b = pd.Series({x: res["grid"][x]["oos"].get("sharpe") for x in ks}, dtype=float)
    res["rank_corr"] = round(float(a.rank().corr(b.rank())), 2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("고름", res["chosen"], "순위상관", res["rank_corr"], "킥 영향", res.get("kick_effect_pp"))


if __name__ == "__main__":
    main()
