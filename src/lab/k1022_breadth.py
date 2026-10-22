"""🌙 10/22 밤 연구 #13 — 킥 넓게 깔기: 돌파 칸 크기는 그대로, 자리를 5 → 7·10·12 개로 늘리고 한 자리는 더 작게
  틀은 10/13~14 그대로: 기본 = C안 뼈대 + 변동성 맞춤(10/13~) · 킥 칸 19% · 출구 −5%·+15%·15일(최고 +3% 못 넘으면 정리) · 판 뒤 10일 재진입 금지
  킥 칸 대용 = 섹터·테마 ETF 52주 신고가 돌파 (개별 종목 신호는 긴 역사가 없음 → 한계: ETF 는 24개 남짓이라 자리 10·12개는 다 못 채울 수 있음
              → 「현금으로 노는 비율」을 같이 봄. 개별 종목이면 후보가 훨씬 많아 결과가 다를 수 있음)
  지금: 자리 5 · 하루 새 진입 최대 2 · 한 자리 = 킥 칸의 1/5
  손잡이: 자리 수 {5·7·10·12} × 하루 새 진입 {2·3} × 한 종목 상한 {없음 · 자리 크기의 1.10배 넘으면 다음 날 덜어냄 — 1.25배는 익절 +15% 가 먼저 와 거의 안 걸림} = 16조합
  판단은 그날 종가까지 → 다음 날 종가 체결 · 회전율 × 0.1% 비용 · 2008-07~2016 샤프로 고르고 2017~ 에서 시험
  판정(지난 밤들과 같음): ✅ = 시험 구간 S&P +0.5%p↑ · 낙폭 S&P 보다 작음 · 샤프 지금보다 높음 · 이웃 조합도 모두 같은 조건
→ market/lab/k1022_breadth.json
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

OUT = Path("market/lab/k1022_breadth.json")
SIZE = 0.19
SLOTS = [5, 7, 10, 12]
MAXNEW = [2, 3]
CAPS = [None, 1.10]   # 1.25배는 익절 +15% 가 먼저 와서 거의 안 걸림 → 1.10배
QUESTION = "킥 돌파 칸 크기는 그대로 두고 자리를 5개 → 7·10·12개로 늘려(한 자리는 더 작게) 넓게 깔면 샤프·낙폭이 나아지나"


def kick_breadth(C, idx, pre, slots=5, max_new=2, cap=None, stop=-0.05, take=0.15, time_d=15, time_min=0.03, reentry=10):
    """k1014 kick_vw(같은 크기) + 자리 수·하루 새 진입·한 종목 상한 · 매일 현금(빈 자리) 비율도 기록"""
    U, Pv, BRK, REL, R, bil = pre
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, pend_trim, last_exit = [], [], [], {}
    rets, turns, trades, idle, nheld = [], [], [], [], []
    slot_w = 1.0 / slots
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
        for j in pend_trim:                      # 상한 넘은 종목 덜어내기
            if j in pos and cap is not None:
                x = pos[j]["w"] - cap * slot_w
                if x > 0:
                    pos[j]["w"] -= x; cash += x; tv += x
        for j in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(slot_w, cash)
            if w <= 0:
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i}
            cash -= w; tv += w
        pend_in, pend_out, pend_trim = [], [], []
        c = tv * COST
        r -= c; cash -= c
        rets.append(r); turns.append(tv); idle.append(cash); nheld.append(len(pos))
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
            elif cap is not None and p["w"] > cap * slot_w:
                pend_trim.append(j)
        free = slots - len(pos) + len(pend_out)
        if free > 0:
            cand = [(REL[i, j], j) for j in range(len(U)) if BRK[i, j] and j not in pos
                    and not (j in last_exit and i - last_exit[j] < reentry) and not np.isnan(REL[i, j])]
            cand.sort(reverse=True)
            pend_in = [j for _, j in cand[:min(free, max_new)]]
    return (pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades,
            pd.Series(idle, index=idx), pd.Series(nheld, index=idx))


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

    def run(slots=5, max_new=2, cap=None):
        kk = kick_breadth(C, idx, pre, slots=slots, max_new=max_new, cap=cap)
        nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
        knav = (1 + kk[0]).cumprod()
        return {"slots": slots, "max_new": max_new, "cap": cap,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, kk[1]), "kick_oos": seg(knav, spy, OOS_START, END, kk[1]),
                "tr_is": tstat(kk[2], START, IS_END), "tr_oos": tstat(kk[2], OOS_START, END),
                "idle_is": mean_in(kk[3], START, IS_END), "idle_oos": mean_in(kk[3], OOS_START, END),
                "held_oos": round(float(kk[4][kk[4].index >= OOS_START].mean()), 2),
                "full_oos": round(float((kk[4][kk[4].index >= OOS_START] >= slots).mean()) * 100, 1)}

    grid = [run(s, m, c) for s in SLOTS for m in MAXNEW for c in CAPS]
    cur = next(g for g in grid if g["slots"] == 5 and g["max_new"] == 2 and g["cap"] is None)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"], -g["slots"]))

    # 이웃: 손잡이 하나만 옆으로 (자리 수 앞뒤 · 하루 새 진입 다른 값 · 상한 다른 값)
    def find(s, m, c):
        return next((g for g in grid if g["slots"] == s and g["max_new"] == m and g["cap"] == c), None)
    si = SLOTS.index(best["slots"])
    nbk = [(SLOTS[j], best["max_new"], best["cap"]) for j in (si - 1, si + 1) if 0 <= j < len(SLOTS)]
    nbk += [(best["slots"], m, best["cap"]) for m in MAXNEW if m != best["max_new"]]
    nbk += [(best["slots"], best["max_new"], c) for c in CAPS if c != best["cap"]]
    shake = [find(*k) for k in nbk]
    shake = [g for g in shake if g is not None]

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > cur["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(shake) and bool(all(all(ok(s["oos"]).values()) for s in shake))
    same = best is cur
    if all(chk.values()) and shake_ok and not same:
        verdict = "✅ 통과"
    elif same:
        verdict = "➖ 지금 그대로"
    elif any(chk.values()):
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    rank_corr = round(float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank())), 2)
    beat_cur = sum(1 for g in grid if g["oos"]["sharpe"] > cur["oos"]["sharpe"])

    def row(g):
        o = g["oos"]
        return {"slots": g["slots"], "max_new": g["max_new"], "cap": g["cap"], "cagr": o["cagr"], "mdd": o["mdd"], "sharpe": o["sharpe"],
                "ex": o["ex"], "turn": o.get("turn"), "idle": g["idle_oos"], "held": g["held_oos"], "kick_turn": g["kick_oos"].get("turn"),
                "trades": g["tr_oos"]}

    def lab(g):
        return f"자리 {g['slots']}·하루 {g['max_new']}·상한 {g['cap'] or '없음'}"
    why = (f"고른 {lab(best)} 시험 구간 샤프 {best['oos']['sharpe']}·연 {best['oos']['cagr']}%·낙폭 {best['oos']['mdd']}% vs 지금(자리 5) "
           f"{cur['oos']['sharpe']}·{cur['oos']['cagr']}%·{cur['oos']['mdd']}% · 빈 자리 현금 {best['idle_oos']}% vs {cur['idle_oos']}% "
           f"(S&P {spy_row['oos']['cagr']}%·{spy_row['oos']['mdd']}%). 16조합 중 지금보다 샤프 높은 것 {beat_cur}개 · 순위상관 {rank_corr}.")
    nxt = ("✅ 이면 kick_params slots·max_new 바꾸기 제안(소급 없음) — 단 ETF 대용이라 실전 개별 종목 장부로 4주 그림자부터"
           if verdict.startswith("✅") else
           "자리 수는 그대로(5) · 다음 밤: #5 고래 바스켓 10→15·20 종목 넓히기(오늘과 같은 「넓게 깔기」 물음을 고래 칸에서)")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "question": QUESTION,
           "trials": len(grid), "from": START, "to": END, "size": SIZE,
           "is": {"from": START, "to": IS_END, "spy": spy_row["is"], "current": cur["is"], "chosen": best["is"]},
           "oos": {"from": OOS_START, "to": END, "spy": spy_row["oos"], "current": cur["oos"], "chosen": best["oos"]},
           "current": {"label": lab(cur), **row(cur), "kick_oos": cur["kick_oos"]},
           "chosen": {"label": lab(best), **row(best), "is_sharpe": best["is"]["sharpe"], "kick_oos": best["kick_oos"]},
           "spy": spy_row,
           "check": chk,
           "grid": [{**row(g), "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"]} for g in grid],
           "robust": {"ok": shake_ok, "rows": [{"label": lab(s), **row(s), "pass": ok(s["oos"])} for s in shake]},
           "rank_corr": rank_corr, "grid_beat_current_oos": f"{beat_cur}/{len(grid)}",
           "verdict": verdict, "verdict_why": why, "next": nxt,
           "note": "킥 신호 대신 섹터·테마 ETF 52주 신고가 돌파(후보 24개 남짓 → 자리 10·12는 다 못 채워 현금이 놀 수 있음, 개별 종목이면 다를 수 있음) · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 한 자리 = 1/자리 수 · 상한 = 자리 크기 1.10배 넘으면 다음 날 덜어냄 · idle = 킥 칸 안 빈 자리 현금(BIL) 평균 % · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 매수 추천 아님"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"])
    print("지금", lab(cur), row(cur))
    print("고른", lab(best), best["is"]["sharpe"], row(best))
    for g in grid:
        print(lab(g), "IS", g["is"]["sharpe"], g["is"]["cagr"], "| OOS", g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"].get("turn"), "현금", g["idle_oos"], "보유", g["held_oos"])
    for s in shake:
        print("이웃", lab(s), s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok, "순위상관", rank_corr)


if __name__ == "__main__":
    main()
