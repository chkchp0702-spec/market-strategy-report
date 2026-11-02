"""📈 11/2 16시 — Q11/2-1(☕ 컵 그림자) 이어서: ① 실제 크기(돌파 칸 9%)·실제 컵 거름(피벗+12% 한도·손잡이 4·RS 50%)으로 PIT 다시
  ② 🆕 「무리별 자기 성적 스위치」(equity-curve throttling 을 신호 무리 단위로): 지난 W 거래일에 끝난 사건(신호 다음 날 종가 진입·15일 뒤)의
     S&P 초과 평균이 ETF 돌파(E) 사건 평균보다 나쁘면(또는 0 아래면) 그 무리(P 실적 갭·C 컵) 신호를 그날 끔. 사건은 끝난 것만 씀(미래 안 봄).
  틀 = k1102_kickpit 그대로(C안 뼈대 + 변동성 맞춤 · 같은 순위 · 그날 S&P500 구성 종목) · 앞 2008-07~2016 / 뒤 2017~ · 회전 × 0.1%
  흔들기: W 378·504·630 (±25%) · 기준 vsE / vs0
  생존 편향: 상장폐지 종목은 yfinance 에 없어 PIT 도 위로 치우침 · 실제 킥의 🎯·🔗·🐋 는 못 넣음
→ market/lab/k1102_famsw.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1024_pead import kick_x
import accum_bt as AB
import k1102_pit as PIT
from k1102_kickpit import pack_from

OUT = Path("market/lab/k1102_famsw.json")
DEF = {"pg": 0.05, "pv": 2.0, "ch": 4, "crs": 0.5, "ext": 1.05}
H = 15


def sigs(pk, k):
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (pk["gapr"] >= k["pg"]) & (pk["O"] > pk["H"].shift(1)) & (pk["V"] >= k["pv"] * pk["vavg"]) & (pk["S"] > pk["hi60"])
        sp = np.nan_to_num(m.values, nan=0).astype(bool) & pk["season"][:, None]
        s = (pk["Hp"] >= k["ch"]) & (pk["Pv"] > pk["PIVp"]) & (pk["Pv"] <= pk["PIVp"] * k["ext"]) & (pk["RS"] >= k["crs"])
        sc = np.nan_to_num(s, nan=0).astype(bool)
    sp &= pk["M"]; sc &= pk["M"]
    return sp, sc


def ev_series(SIG, P, spyv, nd):
    """사건별 15일 S&P 초과를 「끝난 날」(i+1+H) 기준으로 합·수 일별 배열"""
    s = np.zeros(nd); c = np.zeros(nd)
    ii, jj = np.nonzero(SIG)
    for i, j in zip(ii, jj):
        k = i + 1 + H
        if k >= nd:
            continue
        e, f = P[i + 1, j], P[k, j]
        if np.isnan(e) or np.isnan(f) or e <= 0:
            continue
        x = (f / e - 1) - (spyv[k] / spyv[i + 1] - 1)
        s[k] += x; c[k] += 1
    return s, c


def gate(sf, cf, se, ce, W, mode, nmin=10):
    """그날(i) 신호를 켤지: i-1 까지 끝난 사건 W일 창 평균"""
    def roll(a):
        cs = np.cumsum(a); r = cs.copy(); r[W:] = cs[W:] - cs[:-W]
        return np.concatenate([[0.0], r[:-1]])   # 하루 늦춤
    Sf, Cf, Se, Ce = roll(sf), roll(cf), roll(se), roll(ce)
    with np.errstate(invalid="ignore", divide="ignore"):
        mf = Sf / Cf; me = Se / Ce
    thr = me if mode == "vsE" else np.zeros_like(me)
    g = np.where(Cf < nmin, True, mf > np.nan_to_num(thr, nan=0.0))
    return g


def main():
    t0 = time.time()
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre_etf = prep(C)
    Ue, Pe, BRKe, RELe, Re, bil = pre_etf
    nd, ne = len(C.index), len(Ue)
    BRK = np.nan_to_num(BRKe.astype(float), nan=0).astype(bool)
    spyv = C["SPY"].ffill().values
    log = {}
    snaps = PIT.members()
    iv, adds, today = PIT.intervals(snaps)
    ever = sorted(set(iv) | today)
    AB.START = "2006-01-01"; AB.TIME_BUDGET = 14 * 60
    data = AB.download(ever, log, time.time())
    tk = sorted(t for t, d in data.items() if len(d) >= 320)
    log["n_ever"] = len(ever); log["n_dl"] = len(tk)
    print("역대", len(ever), "받음", len(tk), round(time.time() - t0), flush=True)

    def col(f):
        return pd.DataFrame({t: data[t][f] for t in tk}).reindex(C.index)
    Sp, Op, Hp_, Vp = col("close"), col("open"), col("high"), col("volume")
    M = np.zeros((nd, len(tk)), bool)
    dts = C.index.values
    for j, t in enumerate(tk):
        for a, b in iv.get(t, []):
            M[:, j] |= (dts >= np.datetime64(a)) & (dts < np.datetime64(b))
    pk = pack_from(C.index, Sp, Op, Hp_, Vp, M)
    RELs = (pk["Sf"] / pk["Sf"].shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    Rs = pk["Sf"].pct_change().fillna(0.0).values
    Pm = np.hstack([Pe, pk["Pv"]]); R = np.hstack([Re, Rs]); REL = np.hstack([RELe, RELs])
    se, ce = ev_series(BRK, Pe, spyv, nd)
    print("준비", round(time.time() - t0), flush=True)

    def go(fams, size, kw=None, sw=None, label=""):
        k = dict(DEF, **(kw or {}))
        sp, sc = sigs(pk, k)
        if sw:
            W, mode = sw
            for nm in ("P", "C"):
                a = sp if nm == "P" else sc
                s_, c_ = ev_series(a, pk["Pv"], spyv, nd)
                g = gate(s_, c_, se, ce, W, mode)
                if nm == "P":
                    sp = sp & g[:, None]
                else:
                    sc = sc & g[:, None]
        z = np.zeros_like(sp)
        sigS = (sp if "P" in fams else z) | (sc if "C" in fams else z)
        SIG = np.hstack([BRK if "E" in fams else np.zeros((nd, ne), bool), sigS])
        rk, tkk, tr, hd = kick_x(C, idx, Pm, SIG, REL, R, bil)
        nav, td = run_mix(rb, tb, (rk, tkk, None), reg, size, size)
        o = {"label": label, "size": size, "kw": kw or {}, "sw": sw, "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
             "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END)}
        print(label, o["is"]["cagr"], o["is"]["sharpe"], o["is"]["mdd"], "|", o["oos"]["cagr"], o["oos"]["sharpe"], o["oos"]["mdd"], round(time.time() - t0), flush=True)
        return o

    rows = {}
    for size in (0.09, 0.19):
        tag = f"{int(size*100)}"
        rows[f"EPC_{tag}"] = go("EPC", size, label=f"E+P+C 컵≤+5% · {tag}%")
        rows[f"EP_{tag}"] = go("EP", size, label=f"E+P · {tag}%")
        rows[f"EPCx_{tag}"] = go("EPC", size, {"ext": 1.12}, label=f"E+P+C 실제 컵 거름 ≤+12% · {tag}%")
        rows[f"SW_{tag}"] = go("EPC", size, {"ext": 1.12}, (504, "vsE"), label=f"🆕 무리 스위치 504·vsE · {tag}%")
    shake = []
    for W in (378, 630):
        for mode in ("vsE",):
            if time.time() - t0 > 36 * 60:
                break
            shake.append(go("EPC", 0.09, {"ext": 1.12}, (W, mode), label=f"흔들기 스위치 {W}·{mode} · 9%"))
    for W in (504,):
        if time.time() - t0 < 36 * 60:
            shake.append(go("EPC", 0.09, {"ext": 1.12}, (W, "vs0"), label=f"흔들기 스위치 {W}·vs0 · 9%"))
    if time.time() - t0 < 38 * 60:
        shake.append(go("EP", 0.09, {"ext": 1.12, "pg": 0.04}, label="흔들기 E+P 갭4% · 9%"))
        shake.append(go("EP", 0.09, {"ext": 1.12, "pg": 0.06}, label="흔들기 E+P 갭6% · 9%"))

    def d(a, b, s="oos", m="cagr"):
        return round(rows[a][s][m] - rows[b][s][m], 3)
    base = "EPCx_9"
    comp = {nm: {"is": d(nm, base, "is"), "oos": d(nm, base), "sh_is": d(nm, base, "is", "sharpe"), "sh_oos": d(nm, base, "oos", "sharpe"),
                 "mdd_oos": d(nm, base, "oos", "mdd")} for nm in ("EP_9", "SW_9", "EPC_9")}
    comp["shake_oos_vs_base"] = [round(s["oos"]["cagr"] - rows[base]["oos"]["cagr"], 3) for s in shake]
    comp["shake_is_vs_base"] = [round(s["is"]["cagr"] - rows[base]["is"]["cagr"], 3) for s in shake]
    verdict = {}
    for nm in ("EP_9", "SW_9"):
        c = comp[nm]
        if c["is"] >= 1 and c["oos"] >= 1:
            v = "✅ 앞·뒤 +1%p↑"
        elif c["is"] > 0 and c["oos"] > 0:
            v = "🟡 앞·뒤 모두 + (1%p 미만)"
        elif c["oos"] > 0:
            v = "➖ 뒤에서만"
        else:
            v = "❌"
        verdict[nm] = v
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END, "log": log,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}, "rows": rows,
           "shake": [{"label": s["label"], "is": s["is"], "oos": s["oos"]} for s in shake], "vs_real_base": comp, "verdict": verdict,
           "sec": round(time.time() - t0),
           "note": "기준 = EPCx_9(실제 크기 9%·실제 컵 거름 ≤피벗+12%) · PIT(그날 S&P500 구성 종목) · 무리 스위치는 끝난 사건만(하루 늦춤) · 상장폐지 종목 빠짐(위로 치우침) · 🎯·🔗·🐋 미포함 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(verdict, comp, out["sec"])


if __name__ == "__main__":
    main()
