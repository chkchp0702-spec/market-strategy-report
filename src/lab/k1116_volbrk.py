"""🌙 11/16 밤 연구 #32 — 🔊 돌파 날 거래량 확인
  왜: Lee·Swaminathan 2000 「Price Momentum and Trading Volume」(J. Finance 55(5)) https://doi.org/10.1111/0022-1082.00280
      — 거래량이 모멘텀의 지속·되돌림을 가름. 11/09 밤: 「최근 많이 올랐나」로는 못 가름 → 「돈이 몰렸나」로.
  바꾸는 것: 킥 돌파 칸의 「무엇을 사나」만 (출구 −5·+15·15일·자리 5·칸 19% 그대로)
    돌파 날 거래량 ÷ 전날까지 L일 평균 거래량 ≥ x 인 것만 산다(only) / 먼저 산다(first, 나머지는 뒤로)
    x 1.25·1.5·2·2.5 × L 20·50 × only/first = 16조합 + 지금(거르기 없음)
  비용: 모든 매매 회전율 × 0.1% 로 고르고 시험 · 0.2% 로 다시 확인
  무리: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) · S = 미국 대형주 102개(생존 편향)
  전날 종가 판단(돌파·거래량 모두 그날 종가까지) → 다음 날 종가 체결 · 앞 2008-07~2016 샤프로 고르고 2017~ 시험
  흔들기 = x ×0.8/×1.2 · L ×0.8/×1.2 · only↔first · 비용 0.2%
  진단 = 돌파 사건을 거래량 배수 구간별로 나눠 다음 15거래일 S&P 대비 수익
→ market/lab/k1116_volbrk.json
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
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
import k1011_size
import k1013_trend
import k1113_trail
from k1011_size import run_mix, seg, UNIV, ALL
from k1019_cupbrk import STK
from k1105_resmom import prep
from k1113_trail import kick_trail, tr_stat

OUT = Path("market/lab/k1116_volbrk.json")
SIZE = 0.19
XS = [1.25, 1.5, 2.0, 2.5]
LS = [20, 50]
MODES = ["only", "first"]
PICK_COST = 0.001


def set_cost(c):
    for m in (k1011_size, k1013_trend, k1113_trail):
        m.COST = c


def load_cv():
    tk = sorted(set(ALL + STK))
    df = yf.download(tk, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    have = [t for t in tk if t in df.columns.get_level_values(0)]
    Cl = pd.DataFrame({t: df[t]["Close"] for t in have})
    V = pd.DataFrame({t: df[t]["Volume"] for t in have})
    Cl = Cl.dropna(subset=["SPY", "QQQ", "GLD", "BIL"])
    V = V.reindex(Cl.index)
    Cl = Cl.ffill(limit=5)
    return Cl, V


def vol_ratio(V, U, L):
    v = V[U].astype(float).where(V[U] > 0)
    avg = v.shift(1).rolling(L, min_periods=int(L * 0.8)).mean()
    return (v / avg).values


def make_pre(base_pre, VR, x, mode):
    p = dict(base_pre)
    conf = np.nan_to_num(VR, nan=0.0) >= x
    if mode == "only":
        p["brk"] = base_pre["brk"] & conf
    else:
        p["rel"] = base_pre["rel"] + np.where(conf, 100.0, 0.0)
    return p


def events(C, idx, pre, VR, a, b, h=15):
    """돌파 사건 → 다음 날 종가 매수, h 거래일 뒤 종가까지 S&P 대비 (자리·출구 없이)"""
    P, B = pre["P"], pre["brk"]
    spy = C["SPY"].values
    pos_i = {d: i for i, d in enumerate(C.index)}
    ia, ib = pos_i[idx[idx >= pd.Timestamp(a)][0]], pos_i[idx[idx <= pd.Timestamp(b)][-1]]
    buckets = {"<1": [], "1~1.5": [], "1.5~2": [], "2~3": [], "≥3": [], "모름": []}
    for i in range(ia, min(ib, len(P) - h - 1)):
        for j in np.where(B[i])[0]:
            e, z = P[i + 1, j], P[i + 1 + h, j]
            if np.isnan(e) or np.isnan(z):
                continue
            ex = (z / e - 1) - (spy[i + 1 + h] / spy[i + 1] - 1)
            v = VR[i, j]
            k = "모름" if np.isnan(v) else "<1" if v < 1 else "1~1.5" if v < 1.5 else "1.5~2" if v < 2 else "2~3" if v < 3 else "≥3"
            buckets[k].append(ex)
    return {k: ({"n": len(v), "avg_ex": round(float(np.mean(v)) * 100, 2), "win": round(float((np.array(v) > 0).mean()) * 100, 1)}
                if v else {"n": 0}) for k, v in buckets.items()}


def main():
    C, V = load_cv()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    PRE = {"E": prep(C, UNIV), "S": prep(C, list(STK))}
    VRS = {f: {L: vol_ratio(V, PRE[f]["U"], L) for L in sorted(set(LS + [16, 24, 40, 60]))} for f in PRE}
    print("무리 크기", {k: len(v["U"]) for k, v in PRE.items()}, flush=True)
    print("거래량 빈칸 비율", {f: round(float(np.isnan(VRS[f][20]).mean()), 3) for f in VRS}, flush=True)
    BASE = {}

    def base(c):
        if c not in BASE:
            set_cost(c)
            BASE[c] = k1013_trend.base_vol(C, reg, idx)
        set_cost(c)
        return BASE[c]

    def run(fam, cost, x, L, mode):
        rb, tb = base(cost)
        pre = PRE[fam] if x is None else make_pre(PRE[fam], VRS[fam][L], x, mode)
        rk, tk, tr = kick_trail(C, idx, pre)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "cost": cost, "x": x, "L": L, "mode": mode,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_is": tr_stat(tr, START, IS_END), "tr_oos": tr_stat(tr, OOS_START, END)}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        curs = {c: run(fam, c, None, None, None) for c in (0.001, 0.002)}
        for c, r in curs.items():
            print(fam, "지금", c, r["oos"], flush=True)
        grid = []
        for x in XS:
            for L in LS:
                for mo in MODES:
                    g = run(fam, PICK_COST, x, L, mo)
                    grid.append(g)
                    print(fam, x, L, mo, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"],
                          g["oos"].get("turn"), g["tr_oos"].get("n"), flush=True)
        trials += len(grid)
        cur = curs[PICK_COST]
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]

        def ok(o, r=ref):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > r)}

        shake = []
        for k in (0.8, 1.2):
            g = run(fam, PICK_COST, round(best["x"] * k, 3), best["L"], best["mode"]); g["what"] = f"배수 {g['x']}"; shake.append(g)
        for L2 in ({20: (16, 24), 50: (40, 60)}[best["L"]]):
            g = run(fam, PICK_COST, best["x"], L2, best["mode"]); g["what"] = f"평균 {L2}일"; shake.append(g)
        g = run(fam, PICK_COST, best["x"], best["L"], "first" if best["mode"] == "only" else "only"); g["what"] = f"방식 {g['mode']}"; shake.append(g)
        for s in shake:
            s["ok"] = ok(s["oos"])
        g2 = run(fam, 0.002, best["x"], best["L"], best["mode"])
        g2["ok"] = ok(g2["oos"], curs[0.002]["oos"]["sharpe"])
        shake_ok = all(all(s["ok"].values()) for s in shake)
        chk = ok(best["oos"])
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
        ev = {"is": events(C, idx, PRE[fam], VRS[fam][20], START, IS_END),
              "oos": events(C, idx, PRE[fam], VRS[fam][20], OOS_START, END)}
        out_f[fam] = {"current_by_cost": {str(c): {"oos": r["oos"], "is_sh": r["is"]["sharpe"], "tr_oos": r["tr_oos"]} for c, r in curs.items()},
                      "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "shake": shake, "cost_02": g2, "events_vr20_15d": ev,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"x": g["x"], "L": g["L"], "mode": g["mode"],
                                "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"),
                                "tr_oos_avg": g["tr_oos"].get("avg"), "tr_oos_n": g["tr_oos"].get("n"),
                                "tr_oos_pf": g["tr_oos"].get("pf")} for g in grid]}
        print(fam, "고른", best["x"], best["L"], best["mode"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
        print("  비용 0.2%", g2["oos"], g2["ok"])
        print("  사건", ev, flush=True)
    verdict = "✅ 통과" if out_f["E"]["verdict"] == "✅ 통과" else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "pick_cost_pct": PICK_COST * 100, "spy": spy_row, "fam": out_f, "verdict": verdict,
           "note": "E = 섹터·테마 ETF 52주 돌파(지금 킥 대용, 판정 기준) · S = 미국 대형주 102개(생존 편향, 참고) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5·출구 −5·+15·15일 · "
                   "거래량 배수 = 돌파 날 거래량 ÷ 전날까지 L일 평균 · only = 문턱 넘은 돌파만 · first = 넘은 것 먼저 · "
                   "비용 = 모든 매매 회전율 × 0.1%(고르기·시험) · 0.2% 확인 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
