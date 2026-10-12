"""🦴 뼈대 규칙 두 가지 검증 (10/12 사용자 승인: "효과 있으면 포트에 섞기")

  ① 변동성 맞춤 비중 — 주식 칸(S&P500½+나스닥100½)의 최근 20·60일 실현 변동성(연율)으로
     주식 비중 × min(1, 목표/실현), 아래 한도(floor) 30·50%, 1배 넘게 안 실음(레버리지 없음) · 덜어낸 만큼 현금(BIL)
  ② 금 조건부 — GLD 종가가 200일선 위(3거래일 확인)면 금 g%, 아니면 0% · 덜어낸 금은 주식으로(eq) 또는 현금으로(cash)
     비교: 금 고정 0·5·10%
  뼈대 네 가지
     C_static  = 💼 기본 C안 그대로 (S&P 47.5 · 나스닥 47.5 · 금 5 · 현금 0) — 장부 대조군
     C_reg     = ⚡ 킥 포트 기본 칸 (C안 + 🎯 판정 꺼지면 현금 26%) — rules7.py 「cash」
     conc_st   = S&P½+나스닥½ 늘 100% (판정 없음)
     conc      = 🎯 집중 포트 (상승장 S&P½+나스닥½ 100% · 아니면 그 절반 + 현금 50%)
  공통: 판정 A(S&P500 200일선 위 · 3거래일 확인) · 그날 종가로 판단 → 다음 거래일 종가부터 체결 ·
        매주 + 판정(국면·금)이 바뀐 날 + 주식 목표가 10%p 넘게 바뀐 날 비중 맞춤 · 회전율 × 0.1% · 현금 = BIL(1~3개월 T-bill ETF, 2007-05~)
        금 = GLD (2004-11~ 이라 2008 이전 200일선도 GLD 로 충분 → 금 선물 안 씀)

  미리 정한 판정 기준 (결과 보기 전에 적음)
   고르기(2008-07~2016 만): 가족(뼈대×규칙)마다 앞 기간 CAGR 이 기준보다 1.0%p 넘게 낮지 않은 것 중 앞 기간 샤프 1등
   채택(2017~ 시험 기간):
     (가) 샤프 +0.05 이상 개선  또는  최대낙폭 3%p 이상 개선
     (나) CAGR 이 기준보다 0.5%p 넘게 낮지 않음
     (다) 한 해 운 아님 — (가)가 샤프면: 시험 기간 해마다 한 해씩 빼고 다시 잰 샤프도 전부 기준보다 높음
                          (가)가 낙폭이면: 기준의 그해 안 낙폭이 −10% 이하였던 해 중 2개 해 이상에서 2%p 이상 덜 빠지고, 3%p 넘게 더 빠진 해 없음
→ market/skel_bt.json
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.conc_bt import stats, regimes, START, IS_END, OOS_START, KST   # noqa: E402
from src.rules7 import hold_band, VOL_BAND, VOL_ROLES   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "skel_bt.json"
COST = 0.001
COLS = ["SPY", "QQQ", "GLD", "BIL"]
SKEL = {   # 이름: (주식 비중(위험 칸 안), 금 비중(위험 칸 안), 판정 꺼질 때 위험 칸을 남기는 비율)
    "C_static": (0.95, 0.05, 1.0),
    "C_reg": (0.95, 0.05, 0.74),
    "conc_st": (1.0, 0.0, 1.0),
    "conc": (1.0, 0.0, 0.5),
}
SKEL_LAB = {"C_static": "💼 기본 C안 그대로", "C_reg": "⚡ 킥 기본 칸 (C안+판정 현금 26)", "conc_st": "S&P½+나스닥½ 늘 100%", "conc": "🎯 집중 포트"}
VOL_GRID = list(itertools.product([20, 60], [12, 15, 18], [0.3, 0.5]))
GOLD_GRID = [("fix", 0, None), ("fix", 5, None), ("fix", 10, None)] + [("rule", g, f) for g in (5, 10, 15) for f in ("eq", "cash")]
BAND = 0.10
# 🦴 역할별 변동성 맞춤 (10/12 사용자 결정 「기본·킥·집중에 따라 다르게」) — 앞 기간에서만 고름, 실제 운용과 같은 5%p 밴드
ROLES = {
    "base": {"skel": "C_static", "role": "방어형", "grid": list(itertools.product([20, 60], [12, 15, 18], [0.3, 0.4, 0.5, 0.6])),
             "how": "앞 기간 최대낙폭이 가장 얕은 것 (앞 기간 CAGR 손해 2%p 이내)"},
    "kick": {"skel": "C_reg", "role": "중간", "grid": list(itertools.product([20, 60], [15, 18, 20], [0.5, 0.6, 0.7])),
             "how": "앞 기간 샤프 1등"},
    "conc": {"skel": "conc", "role": "공격형", "grid": list(itertools.product([20, 60], [20, 22, 25], [0.7, 0.8])),
             "how": "앞 기간 최대낙폭을 3%p 이상 줄인 것 중 앞 기간 CAGR 손해가 가장 작은 것"},
}


def sticky(s: pd.Series, k=3) -> pd.Series:
    s = s.fillna(False).astype(bool)
    out, cur, run = [], False, 0
    for v in s.values:
        if v != cur:
            run += 1
            if run >= k:
                cur, run = v, 0
        else:
            run = 0
        out.append(cur)
    return pd.Series(out, index=s.index)


def realized_vol(C: pd.DataFrame, lb: int) -> pd.Series:
    r = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change())
    return r.rolling(lb).std() * math.sqrt(252)


def target(skel, up, gold_on, scale, gold_cfg):
    """→ (spy, qqq, gld, bil) 비중"""
    eq, gd, off_keep = SKEL[skel]
    cash_in = 0.0
    if gold_cfg is not None:
        kind, g, freed = gold_cfg
        g /= 100
        if kind == "fix":
            eq, gd = 1 - g, g
        elif gold_on:
            eq, gd = 1 - g, g
        elif freed == "eq":
            eq, gd = 1.0, 0.0
        else:
            eq, gd, cash_in = 1 - g, 0.0, g
    k = 1.0 if up else off_keep
    e, g_ = eq * k * scale, gd * k
    return np.array([e / 2, e / 2, g_, 1 - e - g_])


def simulate(C, R, regv, goldv, scale_arr, skel, gold_cfg, start, end, band=None):
    idx = C.index
    sel = np.where((idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end)))[0]
    wk = idx.isocalendar().week.values
    w = target(skel, bool(regv[sel[0]]), bool(goldv[sel[0]]), float(scale_arr[sel[0]]), gold_cfg)
    nav = np.empty(len(sel)); val = 1.0 - COST * float(np.abs(w[:3]).sum()); pend = None; turn = 0.0
    last = (wk[sel[0]], bool(regv[sel[0]]), bool(goldv[sel[0]]), w[0] + w[1])
    eqs = []
    for j, i in enumerate(sel):
        if j > 0:
            r = R[i]
            val *= 1 + float(w @ r)
            gw = w * (1 + r); s_ = gw.sum()
            if s_ > 0:
                w = gw / s_
        if pend is not None:
            t = float(np.abs(pend - w).sum()); turn += t; val *= 1 - t * COST; w = pend; pend = None
        nav[j] = val
        up, go, sc = bool(regv[i]), bool(goldv[i]), float(scale_arr[i])
        nt = target(skel, up, go, sc, gold_cfg)
        eqs.append(nt[0] + nt[1])
        if wk[i] != last[0] or up != last[1] or (gold_cfg and gold_cfg[0] == "rule" and go != last[2]) or abs(nt[0] + nt[1] - last[3]) > (BAND if band is None else band):
            pend = nt
            last = (wk[i], up, go, nt[0] + nt[1])
    dates = idx[sel]
    yrs = max(0.5, (dates[-1] - dates[0]).days / 365.25)
    return pd.Series(nav, index=dates), round(turn / yrs * 100), round(float(np.mean(eqs)) * 100, 1)


def yr_mdd(nav: pd.Series) -> dict:
    o = {}
    for y, g in nav.groupby(nav.index.year):
        if len(g) > 20:
            o[str(y)] = round(float((g / g.cummax() - 1).min()) * 100, 1)
    return o


def sharpe_of(r: pd.Series):
    return float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else 0.0


def summ(nav, spy):
    st = stats(nav, spy)
    yr = st.get("yr") or {}
    return {**{x: st.get(x) for x in ("cagr", "ex", "vol", "mdd", "sharpe", "beat_years", "years")},
            "worst_yr": min(((v[0], y) for y, v in yr.items()), default=(None, None)),
            "yr": {y: v[0] for y, v in yr.items()}, "yr_mdd": yr_mdd(nav)}


def judge(v, b, nav_v, nav_b):
    """미리 정한 채택 기준 — v/b: 시험 기간 summ · nav_*: 시험 기간 NAV"""
    d_sh = (v["sharpe"] or 0) - (b["sharpe"] or 0)
    d_mdd = v["mdd"] - b["mdd"]
    d_cagr = v["cagr"] - b["cagr"]
    rv, rb = nav_v.pct_change().dropna(), nav_b.pct_change().dropna()
    loyo = {}
    for y in sorted(set(rv.index.year)):
        m = rv.index.year != y
        loyo[str(y)] = round(sharpe_of(rv[m]) - sharpe_of(rb[m]), 3)
    sh_route = d_sh >= 0.05 and all(x > 0 for x in loyo.values())
    bad = [y for y, x in b["yr_mdd"].items() if x <= -10]
    better = [y for y in bad if v["yr_mdd"].get(y, 0) - b["yr_mdd"][y] >= 2]
    worse = [y for y in v["yr_mdd"] if v["yr_mdd"][y] - b["yr_mdd"].get(y, 0) < -3]
    mdd_route = d_mdd >= 3 and len(better) >= 2 and not worse
    cagr_ok = d_cagr >= -0.5
    return {"d_sharpe": round(d_sh, 2), "d_mdd": round(d_mdd, 1), "d_cagr": round(d_cagr, 2), "loyo_d_sharpe": loyo,
            "sharpe_route": bool(sh_route), "sharpe_raw": bool(d_sh >= 0.05), "mdd_route": bool(mdd_route), "mdd_raw": bool(d_mdd >= 3),
            "mdd_better_years": better, "mdd_worse_years": worse, "cagr_ok": bool(cagr_ok),
            "pass": bool(cagr_ok and (sh_route or mdd_route))}


def main() -> int:
    import yfinance as yf
    tick = ["SPY", "QQQ", "GLD", "BIL", "^GSPC"]
    df = yf.download(tick, start="2005-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick if t in df.columns.get_level_values(0)}).dropna(how="all")
    C = C.dropna(subset=["SPY", "QQQ", "GLD"]).ffill(limit=5)
    C["BIL"] = C["BIL"].ffill()
    R = C[COLS].pct_change().fillna(0.0).values
    spy = C["SPY"]
    reg = regimes(C["^GSPC"].ffill(), C[["SPY"]])["A"]
    gold_on = sticky(C["GLD"] > C["GLD"].rolling(200).mean())
    regv, goldv = reg.values.astype(bool), gold_on.values.astype(bool)
    RV = {lb: realized_vol(C, lb) for lb in (20, 60)}
    ones = np.ones(len(C))
    end = C.index[-1]
    PER = (("is", START, IS_END), ("oos", OOS_START, end))

    def run(skel, gold_cfg=None, vol=None):
        sc = ones if vol is None else np.clip(vol[1] / 100 / RV[vol[0]].bfill().values, vol[2], 1.0)
        o = {"skel": skel, "gold": list(gold_cfg) if gold_cfg else None, "vol": list(vol) if vol else None}
        navs = {}
        for nm, a, b in PER:
            nav, t, eqm = simulate(C, R, regv, goldv, sc, skel, gold_cfg, a, b)
            o[nm] = summ(nav, spy); o[nm]["turn"] = t; o[nm]["eq_avg"] = eqm
            navs[nm] = nav
        return o, navs

    rows, fam = [], {}
    for skel in SKEL:
        base, bnav = run(skel)
        base["kind"] = "base"
        rows.append(base)
        f_v, f_g = [], []
        for vol in VOL_GRID:
            o, n = run(skel, vol=vol); o["kind"] = "vol"; rows.append(o); f_v.append((o, n))
        for gc in GOLD_GRID:
            if skel.startswith("conc") and gc == ("fix", 0, None):
                continue      # 집중 뼈대는 금 0 이 기준 그 자체
            if skel.startswith("C") and gc == ("fix", 5, None):
                continue      # C안은 금 5 고정이 기준 그 자체
            o, n = run(skel, gold_cfg=gc); o["kind"] = "gold"; rows.append(o); f_g.append((o, n))
        for fk, F in (("vol", f_v), ("gold", f_g)):
            ok = [x for x in F if x[0]["is"]["cagr"] >= base["is"]["cagr"] - 1.0]
            pick = max(ok, key=lambda x: x[0]["is"]["sharpe"] or -9) if ok else None
            # 시험 기간 순위(정직하게: 고른 것이 시험 기간 몇 등이었나)
            rank = None
            if pick:
                order = sorted(F, key=lambda x: -(x[0]["oos"]["sharpe"] or -9))
                rank = [i for i, x in enumerate(order) if x[0] is pick[0]][0] + 1
            fam[f"{skel}:{fk}"] = {
                "skel": skel, "rule": fk, "base": {k: base[k] for k in ("is", "oos")},
                "pick": ({k: pick[0][k] for k in ("gold", "vol", "is", "oos")} if pick else None),
                "verdict": judge(pick[0]["oos"], base["oos"], pick[1]["oos"], bnav["oos"]) if pick else {"pass": False, "why": "앞 기간 CAGR 조건 통과 없음"},
                "oos_rank_sharpe": rank, "n": len(F),
                "oos_pass_any": sum(judge(x[0]["oos"], base["oos"], x[1]["oos"], bnav["oos"])["pass"] for x in F)}
    # 두 규칙 함께 (각 가족에서 고른 것) — 참고용
    combo = {}
    for skel in SKEL:
        pv, pg = fam[f"{skel}:vol"]["pick"], fam[f"{skel}:gold"]["pick"]
        if pv and pg:
            o, n = run(skel, gold_cfg=tuple(pg["gold"]), vol=tuple(pv["vol"]))
            b, bn = run(skel)
            combo[skel] = {"vol": pv["vol"], "gold": pg["gold"], "is": o["is"], "oos": o["oos"],
                           "verdict": judge(o["oos"], b["oos"], n["oos"], bn["oos"])}
    # 🦴 역할별 고르기 (앞 기간만) — 배율은 실제 운용처럼 5%p 넘게 바뀔 때만 따라감
    roles = {}
    for rk, RD in ROLES.items():
        sk = RD["skel"]
        b_is = simulate(C, R, regv, goldv, ones, sk, None, START, IS_END)[0]
        b_oos = simulate(C, R, regv, goldv, ones, sk, None, OOS_START, end)[0]
        bs = {"is": summ(b_is, spy), "oos": summ(b_oos, spy)}
        cand = []
        for lb, tg, fl in RD["grid"]:
            raw = np.clip(tg / 100 / RV[lb].bfill().values, fl, 1.0)
            held = np.array(hold_band(list(raw), VOL_BAND))
            o = {"lb": lb, "target": tg, "floor": fl}
            for nm, a, b_ in PER:
                nav, t, eqm = simulate(C, R, regv, goldv, held, sk, None, a, b_, band=0.0)
                o[nm] = summ(nav, spy); o[nm]["turn"] = t; o[nm]["eq_avg"] = eqm
            cand.append(o)
        bi = bs["is"]
        if rk == "base":
            ok = [c for c in cand if c["is"]["cagr"] >= bi["cagr"] - 2.0]
            pick = max(ok, key=lambda c: (c["is"]["mdd"], c["is"]["sharpe"])) if ok else None
        elif rk == "kick":
            pick = max(cand, key=lambda c: (c["is"]["sharpe"], c["is"]["mdd"]))
        else:
            ok = [c for c in cand if c["is"]["mdd"] >= bi["mdd"] + 3] or [c for c in cand if c["is"]["mdd"] > bi["mdd"]]
            pick = max(ok, key=lambda c: (c["is"]["cagr"], c["is"]["mdd"])) if ok else None
        live = VOL_ROLES.get(rk)
        live_row = next((c for c in cand if live and c["lb"] == live["lb"] and c["target"] == live["target"] and abs(c["floor"] - live["floor"]) < 1e-9), None)
        roles[rk] = {"skel": sk, "role": RD["role"], "how": RD["how"], "base": bs, "pick": pick, "live": live, "live_row": live_row,
                     "cand": [{k: c[k] for k in ("lb", "target", "floor")} | {nm: {x: c[nm][x] for x in ("cagr", "mdd", "sharpe", "worst_yr", "turn", "eq_avg")} for nm in ("is", "oos")} for c in cand]}
        if pick:
            print("ROLE", rk, sk, "pick", pick["lb"], pick["target"], pick["floor"],
                  "| base IS", bi["cagr"], bi["sharpe"], bi["mdd"], "OOS", bs["oos"]["cagr"], bs["oos"]["sharpe"], bs["oos"]["mdd"],
                  "| pick IS", pick["is"]["cagr"], pick["is"]["sharpe"], pick["is"]["mdd"], "OOS", pick["oos"]["cagr"], pick["oos"]["sharpe"], pick["oos"]["mdd"], "turn", pick["oos"]["turn"])
    # 오늘 상태
    now = {"date": str(end.date()), "up": bool(reg.iloc[-1]),
           "vol20": round(float(RV[20].iloc[-1]) * 100, 1), "vol60": round(float(RV[60].iloc[-1]) * 100, 1),
           "gld": round(float(C["GLD"].iloc[-1]), 2), "gld_ma200": round(float(C["GLD"].rolling(200).mean().iloc[-1]), 2),
           "gld_gap": round(float(C["GLD"].iloc[-1] / C["GLD"].rolling(200).mean().iloc[-1] - 1) * 100, 1),
           "gold_on": bool(gold_on.iloc[-1])}
    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "to": str(end.date()), "is": [START, IS_END], "oos": [OOS_START, str(end.date())],
           "skel_lab": SKEL_LAB, "vol_grid": VOL_GRID, "gold_grid": GOLD_GRID, "families": fam, "combo": combo, "roles": roles, "now": now,
           "spy": {nm: summ(spy[a:b] / spy[a:b].iloc[0], spy) for nm, a, b in PER},
           "rows": rows,
           "rule": "고르기: 앞 기간 CAGR ≥ 기준−1.0%p 중 앞 기간 샤프 1등 · 채택: 시험 기간 (샤프 +0.05↑ & 해마다 한 해 빼도 샤프 우위) 또는 (낙폭 3%p↑ 개선 & 기준 −10%↓ 해 중 2개 해 이상 2%p↑ 덜 빠짐 & 3%p 넘게 더 빠진 해 없음), 그리고 CAGR −0.5%p 이내",
           "note": "판정 A · 다음 날 체결 · 매주+판정 바뀐 날+주식 목표 10%p↑ 바뀐 날 비중 맞춤 · 회전율×0.1% · 현금 BIL · 금 GLD · 레버리지 없음"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("now", now)
    for k, f in fam.items():
        p = f["pick"]
        print(k, "base IS", f["base"]["is"]["cagr"], f["base"]["is"]["sharpe"], f["base"]["is"]["mdd"], "| OOS", f["base"]["oos"]["cagr"], f["base"]["oos"]["sharpe"], f["base"]["oos"]["mdd"])
        if p:
            print("   pick", p["gold"], p["vol"], "IS", p["is"]["cagr"], p["is"]["sharpe"], p["is"]["mdd"], "| OOS", p["oos"]["cagr"], p["oos"]["sharpe"], p["oos"]["mdd"],
                  "rank", f["oos_rank_sharpe"], "/", f["n"], "pass_any", f["oos_pass_any"], json.dumps({k2: f["verdict"][k2] for k2 in f["verdict"] if k2 != "loyo_d_sharpe"}, ensure_ascii=False))
    for k, c in combo.items():
        print("combo", k, c["vol"], c["gold"], "OOS", c["oos"]["cagr"], c["oos"]["sharpe"], c["oos"]["mdd"], c["verdict"]["pass"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
