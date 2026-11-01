"""🌙 11/01 밤 연구 #18 — 📅 월말·월초 계절성: 달이 바뀌는 며칠에만 주식을 더 싣기
  왜: Lakonishok·Smidt 1988 · McConnell·Xu 2008 「Equity Returns at the Turn of the Month」(https://doi.org/10.2469/faj.v64.n2.11)
      — 미국 주식 수익의 상당 부분이 「달 마지막 거래일 ~ 다음 달 첫 3거래일」에 몰린다는 연구.
  틀: 10/13~30 틀 그대로(C안 뼈대 × 변동성 맞춤 + 킥 칸 19%·자리 5·ETF 52주 돌파·출구 −5·+15·15일).
  창(window): 달 마지막 pre 거래일 + 다음 달 첫 post 거래일 (pre 1·2·3 × post 2·3·4 = 9).
  방식 3가지 (주식 = S&P½+나스닥½, 현금 = BIL):
    idle   = 킥 칸 빈 자리 돈만 창 안에서 주식으로 (창 밖은 현금 — 지금 실험 틀)
    cash f = 포트 전체 현금(기본 칸 국면·변동성 현금 + 킥 빈 자리)의 f(50·100%)를 창 안에서 주식으로 — 빚 없음
    swap g = 창 밖에서는 기본 칸 주식의 g(10·20·30%)를 현금으로 덜어 두고 창 안에서만 다 싣기
  = 9 × 6 = 54조합. 판단: 창은 거래소 달력으로 미리 아는 날짜(가격 미래 자료 안 씀) → 전날 종가에 싣고 다음 날 수익부터 반영.
  계산: run_mix 로 만든 포트 일별 수익 위에 「덧칠」 x_t × (주식 − 현금) — 기본 칸 비중은 목표 비중 근사 · 킥 빈 자리 비율은 k1019 방식으로 잼
  비용: 덧칠 비중 변화 |Δx| × 0.1% (회전율에 더함)
  앞 2008-07~2016 샤프로 고르고 2017~ 시험 · 흔들기 = 창 pre±1·post±1 · 크기 ×0.8/×1.2
  한계: 덧칠은 매일 목표 비중 근사(월중 표류 무시) · 창 마지막 날 판정은 다음 거래일 날짜를 씀(달력으로 미리 아는 정보)
→ market/lab/k1101_tom.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg, COST
from k1012_exits import prep
from k1014_volw import kick_vw

OUT = Path("market/lab/k1101_tom.json")
SIZE = 0.19
PRES, POSTS = [1, 2, 3], [2, 3, 4]
MODES = [("idle", None), ("cash", 0.5), ("cash", 1.0), ("swap", 0.1), ("swap", 0.2), ("swap", 0.3)]


def base_targets(C, reg, idx, lb=20, tgt=18.0, floor=0.5):
    """k1013 base_vol 의 목표 비중(전날 판단) — 주식·현금 비중 시리즈"""
    G = {"SPY": .475, "QQQ": .475, "GLD": .05}
    Rd = {"SPY": .315, "QQQ": .315, "GLD": .11}
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(lb).std() * math.sqrt(252) * 100
    sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
    regv = reg.reindex(C.index).fillna(False)
    e, b = [], []
    for i in range(len(C.index)):
        j = max(i - 1, 0)
        base = G if regv.iloc[j] else Rd
        eq = (base["SPY"] + base["QQQ"]) * float(sc.iloc[j])
        e.append(eq); b.append(1 - eq - base["GLD"])
    return pd.Series(e, index=C.index).reindex(idx), pd.Series(b, index=C.index).reindex(idx)


def tom_flags(index):
    s = pd.Series(1, index=index)
    ym = index.year * 100 + index.month
    from_start = s.groupby(ym).cumsum()
    from_end = s[::-1].groupby(ym[::-1]).cumsum()[::-1]
    return pd.Series(from_start.values, index=index), pd.Series(from_end.values, index=index)


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    from k1013_trend import base_vol
    rb, tb = base_vol(C, reg, idx)
    U, Pv, BRK, REL, R, bil = prep(C)
    n = len(C.index)
    VOL = np.full_like(Pv, np.nan, dtype=float)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    # 지금 킥(빈 자리 현금) + 빈 자리 비율
    eps = 1e-6
    k0 = kick_vw(C, idx, (U, Pv, BRK, REL, R, bil), VOL)
    k1 = kick_vw(C, idx, (U, Pv, BRK, REL, R, bil + eps), VOL)
    idle = ((k1[0] - k0[0]) / eps).clip(0, 1)
    nav0, td0 = run_mix(rb, tb, (k0[0], k0[1], None), reg, SIZE, SIZE)
    r0 = nav0.pct_change().fillna(0.0)

    eqw, cashb = base_targets(C, reg, idx)
    eqr = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).fillna(0.0).reindex(idx)
    bilr = C["BIL"].pct_change().fillna(0.0).reindex(idx)
    spread = eqr - bilr
    fs, fe = tom_flags(C.index)
    fs, fe = fs.reindex(idx), fe.reindex(idx)
    cash_all = (1 - SIZE) * cashb + SIZE * idle
    eq_all = (1 - SIZE) * eqw

    def overlay(pre, post, mode, amt):
        tom = ((fe <= pre) | (fs <= post)).astype(float)
        if mode == "idle":
            x = tom * SIZE * idle
        elif mode == "cash":
            x = tom * amt * cash_all
        else:
            x = -(1 - tom) * amt * eq_all
        dx = x.diff().abs().fillna(x.abs())
        r = r0 + x * spread - dx * COST
        nav = (1 + r).cumprod()
        td = td0 + dx
        return nav, td, x

    def run(pre, post, mode, amt):
        nav, td, x = overlay(pre, post, mode, amt)
        return {"pre": pre, "post": post, "mode": mode, "amt": amt,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "x_avg_oos": round(float(x[x.index >= OOS_START].mean()) * 100, 2)}

    cur = {"is": seg(nav0, spy, START, IS_END, td0), "oos": seg(nav0, spy, OOS_START, END, td0)}
    ref = cur["oos"]["sharpe"]

    # 참고: 10/19 적용한 🅿️ park(빈 자리 = 기본 칸과 똑같이)
    pos_i = {d: i for i, d in enumerate(C.index)}
    core = np.zeros(n)
    for d, v in rb.items():
        core[pos_i[d]] = v
    kp = kick_vw(C, idx, (U, Pv, BRK, REL, R, core), VOL)
    rkp = kp[0] - kp[1] * COST
    navp, tdp = run_mix(rb, tb, (rkp, kp[1] * 2, None), reg, SIZE, SIZE)
    park = {"is": seg(navp, spy, START, IS_END, tdp), "oos": seg(navp, spy, OOS_START, END, tdp)}

    # 날 효과 그대로 (S&P 하루 평균 수익, 창 1+3)
    tom13 = (fe <= 1) | (fs <= 3)
    sr = C["SPY"].pct_change().reindex(idx)
    raw = {}
    for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
        m = (sr.index >= a) & (sr.index <= b)
        raw[nm] = {"tom_bp": round(float(sr[m & tom13].mean()) * 1e4, 1), "other_bp": round(float(sr[m & ~tom13].mean()) * 1e4, 1),
                   "tom_days_pct": round(float(tom13[m].mean()) * 100, 1),
                   "tom_share_of_sum_pct": round(float(sr[m & tom13].sum() / sr[m].sum()) * 100, 1)}
    print("날 효과", raw, flush=True)
    print("지금 킥", cur["oos"], "park", park["oos"], flush=True)

    grid = []
    for p in PRES:
        for q in POSTS:
            for mode, amt in MODES:
                g = run(p, q, mode, amt)
                grid.append(g)
                print(p, q, mode, amt, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["oos"]["ex"], flush=True)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}

    shake = []
    for pp in (best["pre"] - 1, best["pre"] + 1):
        if pp >= 0:
            g = run(pp, best["post"], best["mode"], best["amt"]); g["what"] = f"pre {pp}"; shake.append(g)
    for qq in (best["post"] - 1, best["post"] + 1):
        g = run(best["pre"], qq, best["mode"], best["amt"]); g["what"] = f"post {qq}"; shake.append(g)
    if best["amt"] is not None:
        for k in (0.8, 1.2):
            a = round(best["amt"] * k, 3)
            g = run(best["pre"], best["post"], best["mode"], a); g["what"] = f"크기 {a}"; shake.append(g)
    chk = ok(best["oos"])
    shake_ok = all(all(ok(s["oos"]).values()) for s in shake)
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
    by_mode = {}
    for mode, amt in MODES:
        gg = [g for g in grid if g["mode"] == mode and g["amt"] == amt]
        by_mode[f"{mode}_{amt}"] = {"is_sh": round(float(np.mean([g["is"]["sharpe"] for g in gg])), 3),
                                    "oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in gg])), 3),
                                    "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in gg])), 2),
                                    "oos_mdd": round(float(np.mean([g["oos"]["mdd"] for g in gg])), 2)}
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": len(grid), "spy": spy_row, "current": cur, "park_ref": park, "raw_tom": raw,
           "idle_pct": {"is": round(float(idle[idle.index <= IS_END].mean()) * 100, 1), "oos": round(float(idle[idle.index >= OOS_START].mean()) * 100, 1)},
           "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "shake": shake, "verdict": verdict,
           "is_oos_rank_cor": round(rc, 2), "by_mode": by_mode,
           "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
           "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
           "grid": [{"pre": g["pre"], "post": g["post"], "mode": g["mode"], "amt": g["amt"], "is_sh": g["is"]["sharpe"],
                     "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_ex": g["oos"]["ex"],
                     "oos_turn": g["oos"].get("turn"), "x_avg_oos": g["x_avg_oos"]} for g in grid],
           "note": "월말·월초 창(달 마지막 pre + 첫 post 거래일)에 주식(S&P½+나스닥½) 더 싣기 · idle=킥 빈 자리만 · cash f=포트 현금의 f · swap g=창 밖에서 기본 주식 g 덜기 · "
                   "기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19% ETF 52주 돌파 · 덧칠 근사 · 비용 |Δx|×0.1% · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 매수 추천 아님"}
    for k in ("is", "oos"):
        for o in (out["spy"][k], out["current"][k], out["park_ref"][k], out["best"][k]):
            o.pop("yr", None)
    for s in shake:
        for k in ("is", "oos"):
            s[k].pop("yr", None)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("고른", best["pre"], best["post"], best["mode"], best["amt"], best["oos"], verdict, chk, shake_ok)
    for s in shake:
        print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    print("SPY", spy_row["oos"])


if __name__ == "__main__":
    main()
