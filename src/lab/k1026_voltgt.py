"""🌙 10/26 밤 연구 #8 — 킥 기본 칸 변동성 맞춤 손잡이 다시 보기 (지금 목표 18% · 아래 한도 50% · 20일)
  10/13 밤: 변동성 맞춤을 넣은 지금 킥은 낙폭 −17.6% 로 줄었지만 S&P 대비 연 +0.05%p 뿐(넣기 전 +1.08%p) → 「+0.5%p」 못 넘음
  질문: 목표를 높이거나(덜 덜어내기) 아래 한도를 올리면 낙폭 여유를 조금 쓰고 S&P 를 +0.5%p 넘길 수 있나
  틀은 10/13~25 그대로: 기본 = C안 뼈대(🟢 47.5·47.5·금 5 / 🔴 31.5·31.5·금 11·현금 26) × 변동성 맞춤 · 킥 칸 19% ·
        킥 대용 = 섹터·테마 ETF 52주 돌파(같은 크기, 출구 −5·+15·15일 정체) — 킥 쪽은 모든 조합에서 같음
  손잡이: 목표(14·16·18·20·22·25·30%) × 아래 한도(0.3·0.5·0.7) × 보는 날(10·20·40일) = 63 + 끔 1
  2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1% · 전날 종가까지로 판단(base_vol 은 하루 더 늦게 반영)
→ market/lab/k1026_voltgt.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg
from k1012_exits import prep
from k1013_trend import base_vol
from k1014_volw import kick_vw

OUT = Path("market/lab/k1026_voltgt.json")
SIZE = 0.19
TGTS = [14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 30.0]
FLOORS = [0.3, 0.5, 0.7]
LBS = [10, 20, 40]


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    pre = prep(C)
    kk = kick_vw(C, idx, pre, None)
    kick = kk[:2] + (None,)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def go(tgt, floor, lb):
        if tgt is None:
            rb, tb = base_vol(C, reg, idx, lb=20, tgt=1e9, floor=1.0)
        else:
            rb, tb = base_vol(C, reg, idx, lb=int(round(lb)), tgt=tgt, floor=floor)
        nav, td = run_mix(rb, tb, kick, reg, SIZE, SIZE)
        return {"tgt": tgt, "floor": floor, "lb": lb,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    off = go(None, None, None)
    grid = []
    for t in TGTS:
        for f in FLOORS:
            for lb in LBS:
                r = go(t, f, lb); grid.append(r)
                print("격자", t, f, lb, r["is"]["sharpe"], r["oos"]["cagr"], r["oos"]["mdd"], r["oos"]["sharpe"], flush=True)
    cur = next(r for r in grid if r["tgt"] == 18.0 and r["floor"] == 0.5 and r["lb"] == 20)
    best = max(grid + [off], key=lambda r: (r["is"]["sharpe"], r["is"]["cagr"]))
    ref_sh = cur["oos"]["sharpe"]
    shake = []
    if best["tgt"] is not None:
        t0, f0, l0 = best["tgt"], best["floor"], best["lb"]
        for what, kw in [(f"목표 {t0 * 0.8:.1f}%", (t0 * 0.8, f0, l0)), (f"목표 {t0 * 1.2:.1f}%", (t0 * 1.2, f0, l0)),
                         (f"한도 {f0 * 0.8:.2f}", (t0, f0 * 0.8, l0)), (f"한도 {min(1.0, f0 * 1.2):.2f}", (t0, min(1.0, f0 * 1.2), l0)),
                         (f"{round(l0 * 0.8)}일", (t0, f0, round(l0 * 0.8))), (f"{round(l0 * 1.2)}일", (t0, f0, round(l0 * 1.2)))]:
            r = go(*kw); r["what"] = what; shake.append(r)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref_sh)}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([r["is"]["sharpe"] for r in grid]).rank().corr(pd.Series([r["oos"]["sharpe"] for r in grid]).rank()))
    by_tgt = {str(t): {"oos_sh": round(float(np.mean([r["oos"]["sharpe"] for r in grid if r["tgt"] == t])), 3),
                       "oos_cagr": round(float(np.mean([r["oos"]["cagr"] for r in grid if r["tgt"] == t])), 2),
                       "oos_mdd": round(float(np.mean([r["oos"]["mdd"] for r in grid if r["tgt"] == t])), 2),
                       "is_sh": round(float(np.mean([r["is"]["sharpe"] for r in grid if r["tgt"] == t])), 3)} for t in TGTS}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(grid) + 1, "spy": spy_row, "current": cur, "vol_off": off, "best": best,
           "ref_sharpe": ref_sh, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "by_tgt": by_tgt,
           "grid_beat_ref_oos": f"{sum(1 for r in grid if r['oos']['sharpe'] > ref_sh)}/{len(grid)}",
           "grid_beat_spy05_oos": f"{sum(1 for r in grid if r['oos']['ex'] >= 0.5)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for r in grid if all(ok(r['oos']).values()))}/{len(grid)}",
           "shake": shake,
           "grid": [{"tgt": r["tgt"], "floor": r["floor"], "lb": r["lb"], "is_sh": r["is"]["sharpe"], "is_cagr": r["is"]["cagr"],
                     "oos_sh": r["oos"]["sharpe"], "oos_cagr": r["oos"]["cagr"], "oos_mdd": r["oos"]["mdd"],
                     "oos_ex": r["oos"]["ex"], "oos_turn": r["oos"].get("turn")} for r in grid],
           "note": "기본 = C안 뼈대 × 변동성 맞춤(S&P½+나스닥½ 실현 변동성) · 킥 칸 19% = ETF 52주 돌파 대용(모든 조합 같음) · 빈 자리·덜어낸 몫 BIL · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("지금 18/0.5/20", cur["oos"])
    print("끔", off["oos"])
    print("고른", best["tgt"], best["floor"], best["lb"], best["is"]["sharpe"], best["oos"])
    print("목표별", by_tgt)
    print("순위상관", round(rank_cor, 2), out["grid_beat_ref_oos"], out["grid_beat_spy05_oos"], out["grid_all3_oos"])
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
