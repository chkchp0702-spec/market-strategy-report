"""🌙 10/22 밤 연구 #5 — 🐋 고래 바스켓 넓히기: 10종목 → 15·20·전부
  10/21 밤(#11)에 「5개로 몰기」는 나빠짐 → 반대로 넓히면 승자를 덜 놓칠까?
  틀은 src/lab/k1021_whale5.py 그대로(목록 거르기·공개일 +46일 다음 거래일 종가 매수·다음 목록까지 보유·−30% 정리·교체 회전 × 0.1%).
  방식:
    nowk = 지금 순서(겹친 고래 수 n 큰 순 → 비중 w 큰 순) 상위 k 같은 비중
    wk   = 비중 w 큰 순 상위 k
  k = 8·10·12·15·18·20·24·30·전부(99)  → 앞 분기(~2025-11-16)에서 k∈{10,15,20,전부} 중 샤프 1등 고르고 뒤 분기에서 시험.
  흔들기 = 고른 k ×0.8·×1.2. 판단은 산 날 전날 종가까지.
  한계: 목록이 7분기(2024Q4~)뿐 — 앞 2분기는 종목 7·1개라 넓혀도 같음. 고래 칸 혼자 숫자(킥 전체 아님).
→ market/lab/k1022_whalewide.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import yfinance as yf

import src.lab.k1021_whale5 as W

OUT = Path("market/lab/k1022_whalewide.json")
KS = [8, 10, 12, 15, 18, 20, 24, 30, 99]
CAND = [10, 15, 20, 99]
SLEEVE = 0.15

_orig_pick = W.pick


def pick(rows, mode, k, C, d_prev):
    if mode == "wk":
        return _orig_pick(rows, "w", k, C, d_prev)
    return _orig_pick(rows, mode, k, C, d_prev)


W.pick = pick


def main():
    L, _ = W.lists()
    print("분기", [(a, q, len(r)) for a, q, r in L])
    tick = sorted({r["t"] for _, _, rows in L for r in rows} | {"SPY"})
    first = min(a for a, _, _ in L)
    s0 = (dt.date.fromisoformat(first) - dt.timedelta(days=120)).isoformat()
    C = yf.download(tick, start=s0, auto_adjust=True, progress=False, threads=True)["Close"].dropna(how="all")
    idx = C.index
    starts = [idx[idx > pd.Timestamp(a)][0] for a, _, _ in L if (idx > pd.Timestamp(a)).sum() >= 2]
    nq = len(starts)
    cut = starts[nq // 2]
    is_to, oos_from = str((cut - pd.Timedelta(days=1)).date()), str(cut.date())
    spy = C["SPY"]
    res = {"_doc": __doc__, "quarters": [(a, q, len(r)) for a, q, r in L],
           "split": {"is_to": is_to, "oos_from": oos_from, "nq": nq}, "grid": {}, "trials": 0}
    for m in ["nowk", "wk"]:
        for k in KS:
            key = f"{m}{k}"
            full, qr = W.run(L, C, m, k)
            a, _ = W.run(L, C, m, k, d_to=is_to)
            b, _ = W.run(L, C, m, k, d_from=oos_from)
            res["grid"][key] = {"is": W.st(a, spy), "oos": W.st(b, spy), "full": W.st(full, spy),
                                "q": [{x: y for x, y in r.items() if x != "pick"} | {"n": r["n"]} for r in qr]}
            res["trials"] += 1
            print(key, "앞", res["grid"][key]["is"].get("sharpe"), "뒤", res["grid"][key]["oos"])
    cand = {f"{m}{k}": res["grid"][f"{m}{k}"]["is"].get("sharpe") or -9 for m in ["nowk", "wk"] for k in CAND}
    best = max(cand, key=cand.get)
    m, k = ("wk", int(best[2:])) if best.startswith("wk") else ("nowk", int(best[4:]))
    res["chosen"] = {"key": best, "is_sharpe": cand}
    if k != 99:
        lo, hi = round(k * 0.8), round(k * 1.2)
        sh = {}
        for kk in (lo, hi):
            b, _ = W.run(L, C, m, kk, d_from=oos_from)
            sh[f"{m}{kk}"] = W.st(b, spy)
        res["shake"] = sh
    o_new, o_now = res["grid"][best]["oos"], res["grid"]["nowk10"]["oos"]
    res["kick_effect_pp"] = round((o_new["cagr"] - o_now["cagr"]) * SLEEVE, 2)
    ks = list(res["grid"])
    a = pd.Series({x: res["grid"][x]["is"].get("sharpe") for x in ks}, dtype=float)
    b = pd.Series({x: res["grid"][x]["oos"].get("sharpe") for x in ks}, dtype=float)
    res["rank_corr"] = round(float(a.rank().corr(b.rank())), 2)
    res["better_than_now_oos"] = [x for x in ks if (res["grid"][x]["oos"].get("sharpe") or -9) > (o_now.get("sharpe") or 9)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("고름", res["chosen"], "흔들기", res.get("shake"), "순위상관", res["rank_corr"], "킥 영향", res["kick_effect_pp"])


if __name__ == "__main__":
    main()
