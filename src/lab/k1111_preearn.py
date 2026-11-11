"""🌙 11/11 밤 연구 #29 — 📣 실적 발표 직전 프리미엄 (발표 예정일 며칠 전에 사서 발표 반응 직후 팔기)
  왜: Frazzini·Lamont 2007 「The Earnings Announcement Premium and Trading Volume」(NBER w13090) https://www.nber.org/papers/w13090
      — 발표가 있는 때 주식 수익이 높음, 특히 평소 발표 때 거래가 몰리는 종목 · 10/24·25 밤: 발표 「후」 갭은 단단 → 「전」은 아직.
  한계: 진짜 과거 발표일 자료가 없음 → 대용:
      실제 반응일 G = 분기 끝 +8~55일 안에서 「거래량 ÷ 앞 20일 평균」이 가장 큰 날(1.5배 이상일 때만)
      예정일 추정 = 1년 전 같은 분기 G + 364일(같은 요일) 뒤 첫 거래일 → 1년 묵은 자료만 쓰므로 미래 자료 없음
      무리 = 미국 대형주 102개(생존 편향) · 추정이 실제와 ±3거래일 안에 맞은 비율을 함께 적음
  거래: 추정 반응일 Ĝ 의 k 거래일 전 종가 매수 → Ĝ+e 종가 매도(손절·익절 없이 날짜로만) · 한 자리 1/5 · 하루 새 진입 2
  손잡이: k(2·5·10) × e(0·1) × 거래량 문턱 v(작년 반응일 거래량 배수 ≥ 0·2·3) × 방식(fill = 돌파 먼저·빈 자리에 / only = 발표 전 자리만) = 36조합
  무리 2개: E = 섹터·테마 ETF 52주 돌파(지금 킥 대용) + 빈 자리 발표 전 · S = 대형주 52주 돌파 + 빈 자리 발표 전
  앞 2008-07~2016 샤프로 무리마다 고르고 2017~ 시험 · 흔들기 = k ×0.8/×1.2 · e 반대 · v ±1 · 회전율 × 0.1%
→ market/lab/k1111_preearn.json
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
from k1011_size import run_mix, seg, UNIV, COST, ALL
from k1012_exits import tstat
from k1013_trend import base_vol
from k1019_cupbrk import STK

OUT = Path("market/lab/k1111_preearn.json")
SIZE = 0.19
KS = [2, 5, 10]
ES = [0, 1]
VS = [0.0, 2.0, 3.0]
MODES = ["fill", "only"]


def load_cv():
    tk = sorted(set(ALL + STK))
    df = yf.download(tk, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    have = [t for t in tk if t in df.columns.get_level_values(0)]
    Cl = pd.DataFrame({t: df[t]["Close"] for t in have})
    Vo = pd.DataFrame({t: df[t]["Volume"] for t in have})
    Cl = Cl.dropna(subset=["SPY", "QQQ", "GLD", "BIL"])
    Vo = Vo.reindex(Cl.index)
    Cl = Cl.ffill(limit=5)
    return Cl, Vo


def dq_of(d: pd.Timestamp) -> int:
    q_end_m = ((d.month - 1) // 3) * 3
    qe = pd.Timestamp(d.year - 1, 12, 31) if q_end_m == 0 else pd.Timestamp(d.year, q_end_m, 1) + pd.offsets.MonthEnd(0)
    return int((d - qe).days)


def find_events(Cl, Vo, stks):
    """종목별 분기마다 실제 반응일 G (거래량 배수 최대, ≥1.5) → [(종목, G 위치, 배수)]"""
    dates = Cl.index
    dq = np.array([dq_of(d) for d in dates])
    qkey = np.array([(d - pd.Timedelta(days=int(x))).strftime("%Y%m") for d, x in zip(dates, dq)])
    win = (dq >= 8) & (dq <= 55)
    ev = {}
    for t in stks:
        v = Vo[t]
        ratio = (v / v.shift(1).rolling(20, min_periods=15).mean()).values
        df = pd.DataFrame({"r": ratio, "q": qkey, "w": win, "i": np.arange(len(dates))})
        df = df[df["w"] & np.isfinite(df["r"])]
        out = []
        for q, g in df.groupby("q"):
            b = g.loc[g["r"].idxmax()]
            if b["r"] >= 1.5:
                out.append((int(b["i"]), float(b["r"])))
        ev[t] = sorted(out)
    return ev


def est_events(Cl, ev):
    """작년 G + 364일 → 추정 반응일 Ĝ 위치 · 정확도(올해 실제 G 와 ±3거래일)"""
    dates = Cl.index
    est, hit, n = {}, 0, 0
    for t, lst in ev.items():
        act = [i for i, _ in lst]
        e = []
        for i, r in lst:
            tgt = dates[i] + pd.Timedelta(days=364)
            j = int(dates.searchsorted(tgt))
            if j >= len(dates):
                continue
            e.append((j, r))
            near = [a for a in act if abs(a - j) <= 15]
            if near:
                n += 1
                if min(abs(a - j) for a in near) <= 3:
                    hit += 1
        est[t] = e
    return est, (round(hit / n * 100, 1) if n else None), n


def kick_pe(C, idx, U, Pv, R, bil, BRK, REL, brk_ok, pe_in, pe_out_day, mode, stop=-0.05, take=0.15,
            time_d=15, time_min=0.03, slots=5, max_new=2, reentry=10):
    """돌파(brk_ok 열만) — 지금 규칙 · 발표 전 자리 — pe_in[i] = 그날 저녁 신호 낸 [(j, 나갈 날 위치)] → 다음 날 종가 매수"""
    pos_i = {d: i for i, d in enumerate(C.index)}
    pos, cash = {}, 1.0
    pend_in, pend_out, last_exit = [], [], {}
    rets, turns, trades, pe_tr = [], [], [], []
    for d in idx:
        i = pos_i[d]
        r = cash * bil[i]
        for j, p in pos.items():
            r += p["w"] * R[i, j]
            p["w"] *= 1 + R[i, j]
        cash *= 1 + bil[i]
        tot = cash + sum(p["w"] for p in pos.values())
        cash /= tot
        for p in pos.values():
            p["w"] /= tot
        tv = 0.0
        for j in pend_out:
            if j in pos:
                p = pos.pop(j)
                g = Pv[i, j] / p["entry"] - 1
                (pe_tr if p["kind"] == "pe" else trades).append((str(C.index[p["ent_i"]].date()), g))
                cash += p["w"]; tv += p["w"]; last_exit[j] = i
        for j, kind, xo in pend_in:
            if j in pos or len(pos) >= slots:
                continue
            w = min(1.0 / slots, cash)
            if w <= 0 or np.isnan(Pv[i, j]):
                continue
            pos[j] = {"w": w, "entry": Pv[i, j], "max": Pv[i, j], "held": 0, "ent_i": i, "kind": kind, "xo": xo}
            cash -= w; tv += w
        pend_in, pend_out = [], []
        c = tv * COST
        r -= c; cash -= c
        rets.append(r); turns.append(tv)
        for j, p in pos.items():
            if p["ent_i"] == i:
                continue
            px = Pv[i, j]
            if np.isnan(px):
                continue
            p["held"] += 1
            if p["kind"] == "pe":
                if i >= p["xo"] - 1:          # 다음 날(=나갈 날) 종가 정리
                    pend_out.append(j)
                continue
            p["max"] = max(p["max"], px)
            g = px / p["entry"] - 1
            if g <= stop or g >= take or (p["held"] >= time_d and p["max"] / p["entry"] - 1 < time_min):
                pend_out.append(j)
        free = slots - len(pos) + len(pend_out)
        taken = 0
        if free > 0 and mode == "fill":
            cand = [j for j in brk_ok if BRK[i, j] and j not in pos and not (j in last_exit and i - last_exit[j] < reentry)
                    and not np.isnan(REL[i, j])]
            cand.sort(key=lambda j: -REL[i, j])
            for j in cand[:min(free, max_new)]:
                pend_in.append((j, "brk", None)); taken += 1
        free2 = min(free - taken, max_new - taken)
        if free2 > 0 and i in pe_in:
            cand = [(j, xo) for j, xo, vr in pe_in[i] if j not in pos and all(j != q for q, _, _ in pend_in)]
            for j, xo in cand[:free2]:
                pend_in.append((j, "pe", xo))
    return pd.Series(rets, index=idx), pd.Series(turns, index=idx), trades, pe_tr


def main():
    C, Vo = load_cv()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    bil_s = C["BIL"].pct_change().fillna(0.0)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    E_U = [t for t in UNIV if t in C.columns]
    S_U = [t for t in STK if t in C.columns]
    U = list(dict.fromkeys(E_U + S_U))
    col = {t: j for j, t in enumerate(U)}
    P = C[U]
    hi = P.shift(1).rolling(252, min_periods=252).max()
    BRK = ((P > hi) & (P <= hi * 1.12) & ~(P.shift(1) > hi.shift(1))).values
    REL = (P / P.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    R = P.pct_change().fillna(0.0).values
    Pv = P.values
    bil = bil_s.values

    ev = find_events(C, Vo, S_U)
    est, acc, acc_n = est_events(C, ev)
    print("반응일 찾음", sum(len(v) for v in ev.values()), "추정 정확도(±3일)", acc, acc_n, flush=True)

    # 진단: 추정 창 수익 − 같은 창 S&P (사건 단위, 겹침 무시)
    spyv = C["SPY"].values
    diag = {}
    for k in KS:
        for e in ES:
            rows = {"is": [], "oos": []}
            for t, lst in est.items():
                j = col[t]
                for g, vr in lst:
                    a, b = g - k, g + e
                    if a < 1 or b >= len(C.index) or np.isnan(Pv[a, j]) or np.isnan(Pv[b, j]):
                        continue
                    dd = str(C.index[a].date())
                    seg_ = "is" if START <= dd <= IS_END else ("oos" if dd >= OOS_START else None)
                    if seg_ is None:
                        continue
                    rows[seg_].append((Pv[b, j] / Pv[a, j] - 1) - (spyv[b] / spyv[a] - 1))
            # 같은 길이 아무 날(기준) — 대형주 평균 초과
            diag[f"k{k}_e{e}"] = {s: {"n": len(x), "ex_avg": round(float(np.mean(x)) * 100, 3) if x else None,
                                       "hit": round(float(np.mean([v > 0 for v in x])) * 100, 1) if x else None} for s, x in rows.items()}
    base_ex = {}
    for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
        m = (C.index >= a) & (C.index <= b)
        ex = C[S_U].pct_change().sub(C["SPY"].pct_change(), axis=0)[m]
        base_ex[nm] = round(float(ex.stack().mean()) * 100, 4)
    print("진단", diag, "아무 날 하루 초과(%)", base_ex, flush=True)

    PE = {}

    def pe_sig(k, e, v):
        key = (k, e, v)
        if key not in PE:
            d = {}
            for t, lst in est.items():
                j = col[t]
                for g, vr in lst:
                    if vr < v:
                        continue
                    s = g - k - 1
                    if s < 0:
                        continue
                    d.setdefault(s, []).append((j, g + e, vr))
            PE[key] = d
        return PE[key]

    def run(fam, k, e, v, mode):
        brk_ok = [col[t] for t in (E_U if fam == "E" else S_U)]
        pin = pe_sig(k, e, v) if k is not None else {}
        rk, tk, tr, ptr = kick_pe(C, idx, U, Pv, R, bil, BRK, REL, brk_ok, pin, None, mode)
        nav, td = run_mix(rb, tb, (rk, tk, None), reg, SIZE, SIZE)
        return {"fam": fam, "k": k, "e": e, "v": v, "mode": mode,
                "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "tr_oos": tstat(tr, OOS_START, END), "pe_is": tstat(ptr, START, IS_END), "pe_oos": tstat(ptr, OOS_START, END)}

    out_f, trials = {}, 0
    for fam in ("E", "S"):
        cur = run(fam, None, 0, 0.0, "fill")
        print(fam, "지금", cur["is"]["sharpe"], cur["oos"], flush=True)
        grid = []
        for k in KS:
            for e in ES:
                for v in VS:
                    for mo in MODES:
                        g = run(fam, k, e, v, mo)
                        grid.append(g)
                        print(fam, k, e, v, mo, g["is"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["pe_oos"], flush=True)
        trials += len(grid)
        best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
        ref = cur["oos"]["sharpe"]
        shake = []
        for k2 in sorted({max(1, int(round(best["k"] * 0.8))), int(round(best["k"] * 1.2))}):
            if k2 == best["k"]:
                k2 = best["k"] + (1 if k2 == int(round(best["k"] * 1.2)) else -1)
            g = run(fam, k2, best["e"], best["v"], best["mode"]); g["what"] = f"k {k2}일"; shake.append(g)
        g = run(fam, best["k"], 1 - best["e"], best["v"], best["mode"]); g["what"] = f"e {1 - best['e']}"; shake.append(g)
        for v2 in (best["v"] - 1, best["v"] + 1):
            if v2 < 0:
                continue
            g = run(fam, best["k"], best["e"], v2, best["mode"]); g["what"] = f"거래량 {v2}배"; shake.append(g)

        def ok(o):
            return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > ref)}
        chk = ok(best["oos"])
        shake_ok = all(all(ok(s["oos"]).values()) for s in shake)
        verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
        rc = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))

        def avg(key, val):
            xs = [g for g in grid if g[key] == val]
            return {"n": len(xs), "oos_sh": round(float(np.mean([g["oos"]["sharpe"] for g in xs])), 3),
                    "oos_cagr": round(float(np.mean([g["oos"]["cagr"] for g in xs])), 2),
                    "is_sh": round(float(np.mean([g["is"]["sharpe"] for g in xs])), 3)}
        by = {f"k_{x}": avg("k", x) for x in KS}
        by.update({f"e_{x}": avg("e", x) for x in ES})
        by.update({f"v_{x}": avg("v", x) for x in VS})
        by.update({f"mode_{x}": avg("mode", x) for x in MODES})
        out_f[fam] = {"current": cur, "best": best, "ref_sharpe": ref, "check": chk, "shake_ok": shake_ok, "verdict": verdict,
                      "is_oos_rank_cor": round(rc, 2), "by": by, "shake": shake,
                      "grid_beat_ref_oos": f"{sum(1 for g in grid if g['oos']['sharpe'] > ref)}/{len(grid)}",
                      "grid_all3_oos": f"{sum(1 for g in grid if all(ok(g['oos']).values()))}/{len(grid)}",
                      "grid": [{"k": g["k"], "e": g["e"], "v": g["v"], "mode": g["mode"], "is_sh": g["is"]["sharpe"],
                                "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                                "oos_ex": g["oos"]["ex"], "oos_turn": g["oos"].get("turn"), "pe_oos": g["pe_oos"]} for g in grid]}
        print(fam, "고른", best["k"], best["e"], best["v"], best["mode"], best["is"]["sharpe"], best["oos"], verdict, chk, shake_ok, flush=True)
        for s in shake:
            print("  흔들기", s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"], s["oos"]["ex"])
    verdict = "✅ 통과" if all(out_f[f]["verdict"] == "✅ 통과" for f in out_f) else (
        "➖ 애매" if any(out_f[f]["verdict"] != "❌ 기각" for f in out_f) else "❌ 기각")
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trials": trials, "spy": spy_row, "est_accuracy_pct_within3d": acc, "est_n": acc_n,
           "events": sum(len(v) for v in ev.values()), "diag_window_ex": diag, "base_daily_ex_pct": base_ex,
           "fam": out_f, "verdict": verdict,
           "note": "발표일 대용 = 분기 끝 +8~55일 중 거래량 배수 최대일(≥1.5) · 예정일 = 작년 같은 분기 +364일 · 대형주 102개(생존 편향) · "
                   "E = 섹터·테마 ETF 돌파(지금 킥 대용) / S = 대형주 돌파 · fill = 돌파 먼저 빈 자리에 발표 전 / only = 발표 전만 · "
                   "발표 전 자리는 날짜로만 정리(손절 없음) · 기본 = C안 뼈대 × 변동성 맞춤 · 킥 칸 19%·자리 5 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("SPY", spy_row["oos"], "종합", verdict)


if __name__ == "__main__":
    main()
