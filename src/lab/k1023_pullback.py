"""🌙 10/23 밤 연구 #6 — 모멘텀 + 단기 눌림 진입: 돌파 신호가 나와도 바로 사지 않고, W일 안에 n일 동안 dd% 이상 눌렸을 때 사기
  틀은 10/13~22 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 출구 −5%·+15%·15일(최고 +3% 못 넘으면 정리) · 판 뒤 10일 재진입 금지 · 자리 5·하루 새 진입 2
  킥 칸 대용 = 섹터·테마 ETF 52주 신고가 돌파 (개별 종목 신호는 긴 역사가 없음 → 한계)
  지금: 돌파한 날 종가까지 보고 → 다음 날 종가에 삼
  새: 돌파한 날부터 W일 동안 「지켜보기」 → 어느 날 종가가 n일 전 종가보다 dd% 이상 낮으면(눌림) → 다음 날 종가에 삼 · W일 안에 안 눌리면 버림
  손잡이: n {2·3·4} × dd {2·2.5·3·3.5·4%} × W {8·10·12·15·20} = 75조합 (이웃 = 손잡이 하나만 옆 칸 → dd·W 는 대략 ±20%)
  판단은 그날 종가까지 → 다음 날 종가 체결 · 회전율 × 0.1% 비용 · 2008-07~2016 샤프로 고르고 2017~ 에서 시험
→ market/lab/k1023_pullback.json
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
from k1011_size import load, run_mix, seg, COST
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1022_breadth import kick_breadth

OUT = Path("market/lab/k1023_pullback.json")
SIZE = 0.19
NS = [2, 3, 4]
DDS = [0.02, 0.025, 0.03, 0.035, 0.04]
WS = [8, 10, 12, 15, 20]
QUESTION = "52주 신고가 돌파 신호가 나와도 바로 사지 않고, 며칠 안에 n일 동안 dd% 눌렸을 때 사면(추격 매수 대신 눌림 매수) 킥이 S&P 를 안전하게 이기나"


def kick_pull(C, idx, pre, n=3, dd=0.03, W=10, slots=5, max_new=2, stop=-0.05, take=0.15, time_d=15, time_min=0.03, reentry=10):
    U, Pv, BRK, REL, R, bil = pre
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    watch = {}          # j → 돌파한 날 i
    rets, turns, trades, idle = [], [], [], []
    slot_w = 1.0 / slots
    missed = 0; caught = 0
    for d in idx:
        i = pos_i[d]
        r = cash * bil[i]
        for j, p in pos.items():
            rt = R[i, j]
            r += p["w"] * rt
            p["w"] *= 1 + rt
        cash *= 1 + bil[i]
        tot = cash + sum(p["w"] for p in pos.values())
        cash /= tot
        for p in pos.values():
            p["w"] /= tot
        tv = 0.0
        for j in pend_out:
            if j in pos:
                p = pos.pop(j)
                trades.append((str(C.index[p["ent_i"]].date()), Pv[i, j] / p["entry"] - 1))
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(slot_w, cash)
            if w <= 0:
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i}
            cash -= w; tv += w
            watch.pop(j, None)
        pend_in, pend_out = [], []
        c = tv * COST
        r -= c; cash -= c
        rets.append(r); turns.append(tv); idle.append(cash)
        # 출구 판단 (그날 종가까지)
        for j, p in pos.items():
            if p["ent_i"] == i:
                continue
            px = Pv[i, j]
            if np.isnan(px):
                continue
            p["held"] += 1
            p["max"] = max(p["max"], px)
            g = px / p["entry"] - 1
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min):
                pend_out.append(j)
        # 지켜보기 목록: 만료 정리 → 새 돌파 추가
        for j in [j for j, s in watch.items() if i - s > W]:
            watch.pop(j); missed += 1
        for j in range(len(U)):
            if BRK[i, j] and j not in pos and not (j in last_exit and i - last_exit[j] < reentry):
                if j not in watch:
                    watch[j] = i
        # 눌림 확인 (돌파한 날 다음 날부터)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = []
            for j, s in watch.items():
                if i <= s or i - n < 0 or j in pos:
                    continue
                a, b = Pv[i, j], Pv[i - n, j]
                if np.isnan(a) or np.isnan(b) or b <= 0 or np.isnan(REL[i, j]):
                    continue
                if a / b - 1 <= -dd:
                    cand.append((REL[i, j], j))
            cand.sort(reverse=True)
            pend_in = [j for _, j in cand[:min(free, max_new)]]
            caught += len(pend_in)
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, pd.Series(idle, index=idx), (caught, missed)


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre = prep(C)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def mean_in(s, a, b):
        x = s[(s.index >= a) & (s.index <= b)]
        return round(float(x.mean()) * 100, 1) if len(x) else None

    def pack(kk, extra):
        nav, td = run_mix(rb, tb, (kk[0], kk[1], None), reg, SIZE, SIZE)
        knav = (1 + kk[0]).cumprod()
        return {**extra,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, kk[1]), "kick_oos": seg(knav, spy, OOS_START, END, kk[1]),
                "tr_is": tstat(kk[2], START, IS_END), "tr_oos": tstat(kk[2], OOS_START, END),
                "idle_oos": mean_in(kk[3], OOS_START, END)}

    kc = kick_breadth(C, idx, pre, slots=5, max_new=2)
    cur = pack(kc, {"n": 0, "dd": 0, "W": 0})
    grid = []
    for n in NS:
        for dd in DDS:
            for W in WS:
                kk = kick_pull(C, idx, pre, n=n, dd=dd, W=W)
                g = pack(kk, {"n": n, "dd": dd, "W": W})
                g["caught"], g["missed"] = kk[4]
                grid.append(g)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))

    def find(n, dd, W):
        return next((g for g in grid if g["n"] == n and g["dd"] == dd and g["W"] == W), None)
    nbk = []
    for L, key in ((NS, "n"), (DDS, "dd"), (WS, "W")):
        k = L.index(best[key])
        for j in (k - 1, k + 1):
            if 0 <= j < len(L):
                t = {"n": best["n"], "dd": best["dd"], "W": best["W"]}; t[key] = L[j]
                nbk.append((t["n"], t["dd"], t["W"]))
    shake = [g for g in (find(*k) for k in nbk) if g is not None]

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > cur["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and all(all(ok(s["oos"]).values()) for s in shake)
    if all(chk.values()) and shake_ok:
        verdict = "✅ 통과"
    elif any(chk.values()):
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    rank_corr = round(float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank())), 2)
    beat_cur = sum(1 for g in grid if g["oos"]["sharpe"] > cur["oos"]["sharpe"])
    beat_spy = sum(1 for g in grid if g["oos"]["ex"] >= 0.5)

    def lab(g):
        return "지금(바로 삼)" if g["n"] == 0 else f"{g['n']}일 −{g['dd']*100:g}%·{g['W']}일 안"

    def row(g):
        o = g["oos"]
        return {"label": lab(g), "n": g["n"], "dd": g["dd"], "W": g["W"], "cagr": o["cagr"], "mdd": o["mdd"], "sharpe": o["sharpe"],
                "ex": o["ex"], "turn": o.get("turn"), "idle": g["idle_oos"], "trades": g["tr_oos"], "trades_is": g["tr_is"],
                "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"]}
    why = (f"고른 {lab(best)} 시험 구간 연 {best['oos']['cagr']}%·낙폭 {best['oos']['mdd']}%·샤프 {best['oos']['sharpe']} vs 지금 "
           f"{cur['oos']['cagr']}%·{cur['oos']['mdd']}%·{cur['oos']['sharpe']} (S&P {spy_row['oos']['cagr']}%·{spy_row['oos']['mdd']}%) · "
           f"빈 자리 현금 {best['idle_oos']}% vs {cur['idle_oos']}% · {len(grid)}조합 중 지금보다 샤프 높은 것 {beat_cur}개·S&P +0.5%p 넘은 것 {beat_spy}개 · 순위상관 {rank_corr}")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "question": QUESTION,
           "trials": len(grid), "from": START, "to": END, "size": SIZE,
           "is": {"from": START, "to": IS_END, "spy": spy_row["is"], "current": cur["is"], "chosen": best["is"]},
           "oos": {"from": OOS_START, "to": END, "spy": spy_row["oos"], "current": cur["oos"], "chosen": best["oos"]},
           "current": {**row(cur), "kick_oos": cur["kick_oos"]},
           "chosen": {**row(best), "kick_oos": best["kick_oos"], "caught": best["caught"], "missed": best["missed"]},
           "spy": spy_row, "check": chk,
           "grid": [row(g) for g in grid],
           "robust": {"ok": shake_ok, "rows": [{**row(s), "pass": ok(s["oos"])} for s in shake]},
           "rank_corr": rank_corr, "grid_beat_current_oos": f"{beat_cur}/{len(grid)}", "grid_beat_spy_oos": f"{beat_spy}/{len(grid)}",
           "verdict": verdict, "verdict_why": why,
           "note": "킥 신호 대신 섹터·테마 ETF 52주 신고가 돌파(개별 종목 컵·갭은 긴 역사 없음) · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 출구 −5·+15·15일 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 매수 추천 아님"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("지금", row(cur))
    print("고른", row(best), best["caught"], best["missed"])
    for g in sorted(grid, key=lambda g: -g["oos"]["sharpe"])[:10]:
        print(lab(g), "IS", g["is"]["sharpe"], "| OOS", g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["tr_oos"])
    for s in shake:
        print("이웃", lab(s), s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok, "순위상관", rank_corr, why)


if __name__ == "__main__":
    main()
