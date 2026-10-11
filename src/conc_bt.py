"""🎯 선택과 집중 검증 (10/11 사용자: "오르는 시장이면 벌 때 벌어야 — 확신 있는 섹터·종목 비중을 늘려 아웃퍼폼. 단 오르는 시장 판단이 먼저")

1) 「오르는 시장」 판정 규칙을 먼저 검증: 판정이 켜졌을 때 S&P·코스피의 다음 20·60일이 실제로 더 좋았나, 얼마나 자주 뒤집히나
2) 그 위에서 집중: 상승장이면 모멘텀 상위 K개 섹터·테마 ETF에 몰고, 아니면 S&P 또는 절반 현금
   · 판단은 그날 종가까지, 체결은 다음 거래일 종가(하루 늦게) · 회전율 × 0.1% 비용
   · 2008-07 ~ 2016-12 에서 고르고(앞), 2017-01 ~ 지금에서 시험(뒤) — 뒤 기간 성적이 진짜 성적
   · 미리 정해 둔 「사용자 원안」 하나는 고르기 없이 그대로 보고
   · 유니버스 두 개: ① 섹터 SPDR 9개(사후 선택 없음) ② + 반도체·소프트웨어·바이오 등 테마 ETF(오늘 아는 테마가 섞여 유리할 수 있음)
→ market/conc_bt.json
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "conc_bt.json"
KST = dt.timezone(dt.timedelta(hours=9))
SECT = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
THEME = ["SOXX", "IGV", "IBB", "ITA", "XHB", "KRE", "XME", "XOP", "IYT", "QQQ", "XLRE", "XLC", "SKYY", "CIBR", "TAN", "PAVE", "GLD"]
NAMES = {"XLB": "소재", "XLE": "에너지", "XLF": "금융", "XLI": "산업재", "XLK": "기술", "XLP": "필수소비재", "XLU": "유틸리티", "XLV": "헬스케어",
         "XLY": "임의소비재", "SOXX": "반도체", "IGV": "소프트웨어", "IBB": "바이오", "ITA": "방산·항공", "XHB": "주택건설", "KRE": "지역은행",
         "XME": "금속·광업", "XOP": "석유 탐사", "IYT": "운송", "QQQ": "나스닥100", "XLRE": "리츠", "XLC": "통신", "SKYY": "클라우드",
         "CIBR": "사이버보안", "TAN": "태양광", "PAVE": "인프라", "GLD": "금"}
IS_END, OOS_START = "2016-12-31", "2017-01-01"
START = "2008-07-01"
COST = 0.001


def stats(nav: pd.Series, bench: pd.Series | None = None) -> dict:
    nav = nav.dropna()
    if len(nav) < 30:
        return {}
    r = nav.pct_change().dropna()
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    vol = r.std() * math.sqrt(252)
    mdd = (nav / nav.cummax() - 1).min()
    o = {"cagr": round(cagr * 100, 2), "vol": round(vol * 100, 1), "mdd": round(mdd * 100, 1),
         "sharpe": round((r.mean() * 252) / (r.std() * math.sqrt(252)), 2) if r.std() > 0 else None}
    if bench is not None:
        b = bench.reindex(nav.index).dropna()
        n2 = nav.reindex(b.index)
        by = (b.iloc[-1] / b.iloc[0]) ** (1 / yrs) - 1
        o["ex"] = round((cagr - by) * 100, 2)
        # 12개월 굴린 창에서 S&P 이긴 비율
        rn, rb = n2.pct_change(252), b.pct_change(252)
        m = (rn - rb).dropna()
        o["win12"] = round(float((m > 0).mean()) * 100) if len(m) else None
        yr = {}
        for y, g in n2.groupby(n2.index.year):
            gb = b.loc[g.index]
            if len(g) > 20:
                yr[str(y)] = [round((g.iloc[-1] / g.iloc[0] - 1) * 100, 1), round((gb.iloc[-1] / gb.iloc[0] - 1) * 100, 1)]
        o["yr"] = yr
        o["beat_years"] = sum(1 for v in yr.values() if v[0] > v[1])
        o["years"] = len(yr)
    return o


def regimes(spx: pd.Series, univ: pd.DataFrame) -> dict[str, pd.Series]:
    m50, m200 = spx.rolling(50).mean(), spx.rolling(200).mean()
    up_a = spx > m200
    up_b = up_a & (m50 > m200)
    up_c = up_b & (m200 > m200.shift(20))
    br = (univ > univ.rolling(200).mean()).sum(axis=1) / univ.notna().sum(axis=1).clip(lower=1)
    up_d = up_c & (br >= 0.6)
    # 판정이 하루 이틀로 깜빡이지 않게: 바뀐 상태가 3거래일 이어져야 인정
    def sticky(s, k=3):
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
    return {"none": pd.Series(True, index=spx.index), "A": sticky(up_a), "B": sticky(up_b), "C": sticky(up_c), "D": sticky(up_d)}


REG_LAB = {"none": "판정 없이 늘 집중", "A": "S&P 200일선 위", "B": "200일선 위 + 50일선>200일선",
           "C": "B + 200일선이 오르는 중", "D": "C + 종목 60% 이상 200일선 위(시장 폭)"}


def regime_eval(px: pd.Series, reg: pd.Series) -> dict:
    f20, f60 = px.shift(-20) / px - 1, px.shift(-60) / px - 1
    d = pd.DataFrame({"r": reg.reindex(px.index).fillna(False), "f20": f20, "f60": f60}).dropna()
    on, off = d[d.r], d[~d.r]
    flips = int((reg.astype(int).diff().abs() > 0).sum())
    yrs = (reg.index[-1] - reg.index[0]).days / 365.25

    def g(x, c):
        return {"avg": round(x[c].mean() * 100, 2), "win": round((x[c] > 0).mean() * 100), "worst10": round(x[c].quantile(0.1) * 100, 1)} if len(x) else None
    return {"on_pct": round(len(on) / max(1, len(d)) * 100), "flips_per_year": round(flips / yrs, 1),
            "on": {"f20": g(on, "f20"), "f60": g(on, "f60")}, "off": {"f20": g(off, "f20"), "f60": g(off, "f60")},
            "edge20": round((on.f20.mean() - off.f20.mean()) * 100, 2) if len(on) and len(off) else None}


def momentum(C: pd.DataFrame, kind: str) -> pd.DataFrame:
    if kind == "3m":
        return C / C.shift(63) - 1
    if kind == "6m":
        return C / C.shift(126) - 1
    if kind == "12-1":
        return C.shift(21) / C.shift(252) - 1
    # mix: 3·6개월 평균 (최근 1주 빼고 — 단기 되돌림 피함)
    return 0.5 * (C.shift(5) / C.shift(68) - 1) + 0.5 * (C.shift(5) / C.shift(131) - 1)


_CACHE: dict = {}


def _prep(C, univ, mom):
    key = (tuple(univ), mom)
    if key not in _CACHE:
        cols = list(univ) + ["SPY", "BIL"]
        P = C[cols]
        R = P.pct_change().fillna(0.0).values
        M = momentum(C[univ], mom).values
        ma = C[univ].rolling(200).mean().values
        px = C[univ].values
        _CACHE[key] = (cols, R, M, ma, px)
    return _CACHE[key]


def simulate(C, univ, spy, bil, reg, k, mode, off, reb, mom, start, end, conv=False):
    """반환: 일별 NAV. 판단일 t 종가 → t+1 종가부터 새 비중."""
    cols, R, M, ma, px = _prep(C, univ, mom)
    n_u = len(univ)
    idx = C.index
    sel = np.where((idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end)))[0]
    regv = reg.reindex(idx).fillna(False).values.astype(bool)
    keys = (idx.isocalendar().week.values if reb == "W" else idx.month.values)
    w = np.zeros(len(cols)); w[n_u] = 1.0
    nav = np.empty(len(sel)); val = 1.0; pend = None; last_key = None; turn_sum = 0.0
    for j, i in enumerate(sel):
        if j > 0:
            r = R[i]
            val *= 1 + float(w @ r)
            gw = w * (1 + r); s_ = gw.sum()
            if s_ > 0:
                w = gw / s_
        if pend is not None:
            t = float(np.abs(pend - w).sum()); turn_sum += t
            val *= 1 - t * COST; w = pend; pend = None
        nav[j] = val
        kk = keys[i]
        if kk == last_key:
            continue
        last_key = kk
        nw = np.zeros(len(cols))
        if regv[i]:
            m = M[i]
            ok = (~np.isnan(m)) & (~np.isnan(ma[i])) & (px[i] > ma[i])
            cand = np.where(ok)[0]
            if len(cand):
                order = cand[np.argsort(-m[cand])][:k]
                sat = 1.0 if mode == "full" else 0.5
                if conv and len(order) > 1:
                    sc = np.clip(m[order] - m[order].min() + 0.02, 0.01, None); ws = sc / sc.sum()
                else:
                    ws = np.full(len(order), 1 / len(order))
                nw[order] += sat * ws
                nw[n_u] += 1 - sat
            else:
                nw[n_u] = 1.0
        else:
            if off == "spy":
                nw[n_u] = 1.0
            else:
                nw[n_u], nw[n_u + 1] = 0.5, 0.5
        pend = nw
    dates = idx[sel]
    yrs = max(0.5, (dates[-1] - dates[0]).days / 365.25)
    return pd.Series(nav, index=dates), round(turn_sum / yrs * 100)


# =============================== 2차: 「벌 때 벌기」를 노출(주식 비중·배수)로 — 상승장이면 더 싣고, 아니면 줄임
BORROW = 0.005   # 빌린 돈에 T-bill 위로 연 0.5% (레버리지 ETF·신용 비용 근사)


def sim_exp(C, reg, on: dict, off: dict, start, end, sat=0.0, sat_k=3, sat_univ=None, reb="W"):
    """on/off: {티커: 비중} (BIL 음수 = 빌림). sat>0 이면 상승장일 때 그만큼을 모멘텀 상위 sat_k 위성으로(on 비중은 1-sat 로 줄임)."""
    univ = list(sat_univ or [])
    cols = sorted(set(list(on) + list(off) + ["SPY", "BIL"] + univ))
    ci = {c: i for i, c in enumerate(cols)}
    P = C[cols]
    R = P.pct_change().fillna(0.0).values
    idx = C.index
    sel = np.where((idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end)))[0]
    regv = reg.reindex(idx).fillna(False).values.astype(bool)
    keys = idx.isocalendar().week.values if reb == "W" else idx.month.values
    if univ:
        M = momentum(C[univ], "mix").values; ma = C[univ].rolling(200).mean().values; px = C[univ].values
    w = np.zeros(len(cols)); w[ci["SPY"]] = 1.0
    nav = np.empty(len(sel)); val = 1.0; pend = None; last_key = None; last_up = None; turn = 0.0
    for j, i in enumerate(sel):
        if j > 0:
            r = R[i]
            val *= 1 + float(w @ r)
            b = -w[ci["BIL"]] if w[ci["BIL"]] < 0 else 0.0
            val *= 1 - b * BORROW / 252
            gw = w * (1 + r); s_ = gw.sum()
            if s_ > 0:
                w = gw / s_
        if pend is not None:
            t = float(np.abs(pend - w).sum()); turn += t; val *= 1 - t * COST; w = pend; pend = None
        nav[j] = val
        up = bool(regv[i])
        kk = keys[i]
        if kk == last_key and up == last_up:
            continue
        last_key, last_up = kk, up
        nw = np.zeros(len(cols))
        if up:
            base = 1.0 - (sat if univ else 0.0)
            for c, x in on.items():
                nw[ci[c]] += x * base
            if univ and sat > 0:
                m = M[i]; ok = (~np.isnan(m)) & (~np.isnan(ma[i])) & (px[i] > ma[i]); cand = np.where(ok)[0]
                if len(cand):
                    order = cand[np.argsort(-m[cand])][:sat_k]
                    for o in order:
                        nw[ci[univ[o]]] += sat / len(order)
                else:
                    nw[ci["SPY"]] += sat
        else:
            for c, x in off.items():
                nw[ci[c]] += x
        pend = nw
    dates = idx[sel]
    yrs = max(0.5, (dates[-1] - dates[0]).days / 365.25)
    return pd.Series(nav, index=dates), round(turn / yrs * 100)


EXP = [   # (키, 이름, on, off, sat, sat_k)
    ("cur", "지금 포트 닮은꼴 — 늘 섹터 같은 비중 74% + 현금 26%", None, None, 0, 0),
    ("e100", "상승장 S&P 100% · 아니면 S&P 50%+현금 50%", {"SPY": 1.0}, {"SPY": 0.5, "BIL": 0.5}, 0, 0),
    ("e130", "상승장 S&P 1.3배 · 아니면 S&P 50%", {"SPY": 1.3, "BIL": -0.3}, {"SPY": 0.5, "BIL": 0.5}, 0, 0),
    ("e150", "상승장 S&P 1.5배 · 아니면 S&P 50%", {"SPY": 1.5, "BIL": -0.5}, {"SPY": 0.5, "BIL": 0.5}, 0, 0),
    ("e130o", "상승장 S&P 1.3배 · 아니면 S&P 100%(줄이지 않음)", {"SPY": 1.3, "BIL": -0.3}, {"SPY": 1.0}, 0, 0),
    ("qqq", "상승장 나스닥100 100% · 아니면 S&P 50%", {"QQQ": 1.0}, {"SPY": 0.5, "BIL": 0.5}, 0, 0),
    ("sat20", "상승장 S&P 80% + 강한 테마 3개 20% · 아니면 S&P 50%", {"SPY": 1.0}, {"SPY": 0.5, "BIL": 0.5}, 0.2, 3),
    ("sat30", "상승장 S&P 70% + 강한 테마 3개 30% · 아니면 S&P 50%", {"SPY": 1.0}, {"SPY": 0.5, "BIL": 0.5}, 0.3, 3),
    ("sq", "🎯 집중 포트 규칙 — 상승장 S&P½+나스닥½ 100% · 아니면 그 절반 + 현금 50%", {"SPY": 0.5, "QQQ": 0.5}, {"SPY": 0.25, "QQQ": 0.25, "BIL": 0.5}, 0, 0),
    ("sat20l", "상승장 S&P 1.2배 + 강한 테마 3개 20% · 아니면 S&P 50%", {"SPY": 1.2, "BIL": -0.2}, {"SPY": 0.5, "BIL": 0.5}, 0.2, 3),
]


def exposure(C, R, spy, end, out):
    theme_u = [t for t in SECT + THEME if t in C.columns and t not in ("QQQ", "GLD")]
    rows = []
    for rk in ("A", "B", "C"):
        for key, lab, on, off, sat, sk in EXP:
            if key == "cur" and rk != "A":
                continue
            per = {}
            for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, end), ("full", START, end)):
                if key == "cur":
                    reg = pd.Series(True, index=C.index)
                    on_ = {t: 0.74 / len(SECT) for t in SECT}; on_["BIL"] = 0.26
                    nav, t = sim_exp(C, reg, on_, on_, a, b, reb="M")
                else:
                    nav, t = sim_exp(C, R[rk], on, off, a, b, sat=sat, sat_k=sk, sat_univ=theme_u if sat else None)
                st_ = stats(nav, spy)
                per[nm] = {x: st_.get(x) for x in ("cagr", "ex", "mdd", "sharpe", "win12", "beat_years", "years")}
                per[nm]["turn"] = t
                if nm == "full":
                    per["yr"] = st_.get("yr")
                    per["line"] = [round(float(x), 4) for x in nav.iloc[::21].values]
            rows.append({"k": key, "reg": rk if key != "cur" else "-", "lab": lab, **per})
    out["exposure"] = {"rows": rows, "spy_line": [round(float(x), 4) for x in (spy[START:] / spy[START:].iloc[0]).iloc[::21].values],
                       "note": "레버리지는 빌린 돈에 T-bill+연 0.5% · 상승장 판정 바뀔 때와 매주 비중 맞춤 · 다음 날 체결 · 회전율×0.1%",
                       "warn": "나스닥100(QQQ)은 지금 아는 승자라 유리하게 나올 수 있음 — 뒤 기간(2017~) 숫자로만 판단"}
    # 코스피에 같은 판정: 상승장 코스피 100%/1.3배 · 아니면 50%
    print("exposure", json.dumps([{k: r[k] for k in ("k", "reg")} | {"oos": r["oos"], "full": {x: r["full"][x] for x in ("cagr", "ex", "mdd", "sharpe")}} for r in rows], ensure_ascii=False))


def main() -> int:
    import yfinance as yf
    tick = sorted(set(SECT + THEME + ["SPY", "BIL", "^KS11", "^GSPC"]))
    df = yf.download(tick, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick if t in df.columns.get_level_values(0)})
    C = C.dropna(how="all")
    ks = C["^KS11"].dropna()
    C = C.drop(columns=["^KS11"]).ffill(limit=5)
    C = C[C.index >= "2007-01-01"]
    spy, bil = C["SPY"], C["BIL"]
    gspc = C["^GSPC"].dropna()
    R = regimes(gspc.reindex(C.index).ffill(), C[SECT])
    end = C.index[-1]

    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "to": str(end.date()), "from": START,
           "is": [START, IS_END], "oos": [OOS_START, str(end.date())], "names": NAMES, "reg_lab": REG_LAB,
           "note": "판단은 그날 종가까지·체결은 다음 거래일 종가 · 회전율×0.1% 비용 · 앞(2008~2016)에서 고르고 뒤(2017~)에서 시험"}

    # 1) 상승장 판정 검증 — S&P 와 코스피(코스피는 같은 규칙을 코스피 자체에)
    ks_r = regimes(ks, pd.DataFrame({"k": ks}))
    out["regime"] = {}
    for rk in ("A", "B", "C", "D"):
        out["regime"][rk] = {"lab": REG_LAB[rk], "spx": regime_eval(gspc.reindex(C.index).ffill(), R[rk]),
                             "spx_oos": regime_eval(gspc.reindex(C.index).ffill()[OOS_START:], R[rk][OOS_START:]),
                             "kospi": regime_eval(ks, ks_r[rk]) if rk != "D" else None,
                             "now": bool(R[rk].iloc[-1])}
    # 오늘 상태 상세
    g = gspc.reindex(C.index).ffill()
    out["now"] = {"date": str(end.date()), "spx": round(float(g.iloc[-1]), 1), "ma50": round(float(g.rolling(50).mean().iloc[-1]), 1),
                  "ma200": round(float(g.rolling(200).mean().iloc[-1]), 1),
                  "ma200_up": bool(g.rolling(200).mean().iloc[-1] > g.rolling(200).mean().iloc[-21]),
                  "breadth": round(float(((C[SECT] > C[SECT].rolling(200).mean()).sum(axis=1) / len(SECT)).iloc[-1]) * 100),
                  "kospi_up": {rk: bool(ks_r[rk].iloc[-1]) for rk in ("A", "B", "C")}}

    # 2) 집중 전략 격자
    grid = list(itertools.product(["none", "A", "B", "C", "D"], [1, 2, 3, 5], ["full", "core"], ["spy", "half"], ["W", "M"], ["3m", "6m", "12-1", "mix"]))
    res = {}
    for uk, univ in (("sect", SECT), ("theme", [t for t in SECT + THEME if t in C.columns])):
        rows = []
        for rk, k, mode, off, reb, mom in grid:
            if rk == "none" and off == "half":
                continue
            nav_is, t_is = simulate(C, univ, spy, bil, R[rk], k, mode, off, reb, mom, START, IS_END)
            nav_oos, t_oos = simulate(C, univ, spy, bil, R[rk], k, mode, off, reb, mom, OOS_START, end)
            s_is, s_oos = stats(nav_is, spy), stats(nav_oos, spy)
            rows.append({"cfg": [rk, k, mode, off, reb, mom], "is": {x: s_is.get(x) for x in ("cagr", "ex", "mdd", "sharpe", "win12")},
                         "oos": {x: s_oos.get(x) for x in ("cagr", "ex", "mdd", "sharpe", "win12", "beat_years", "years")}, "turn": t_oos})
        # 앞 기간 기준으로 고르기: 낙폭이 S&P(앞 기간)보다 크게 나쁘지 않은 것 중 초과수익 순
        spy_is = stats(spy[START:IS_END])
        pick = sorted([r for r in rows if r["is"]["mdd"] is not None and r["is"]["mdd"] >= spy_is["mdd"] - 10],
                      key=lambda r: -(r["is"]["ex"] or -99))[:5]
        oos_ex = [r["oos"]["ex"] for r in rows if r["oos"]["ex"] is not None]
        by_reg = {}
        for rk in ("none", "A", "B", "C", "D"):
            v = [r["oos"]["ex"] for r in rows if r["cfg"][0] == rk and r["oos"]["ex"] is not None]
            vm = [r["oos"]["mdd"] for r in rows if r["cfg"][0] == rk and r["oos"]["mdd"] is not None]
            by_reg[rk] = {"n": len(v), "med_ex": round(float(np.median(v)), 2) if v else None, "beat": round(sum(x > 0 for x in v) / max(1, len(v)) * 100),
                          "med_mdd": round(float(np.median(vm)), 1) if vm else None}
        by_k = {}
        for k in (1, 2, 3, 5):
            v = [r["oos"]["ex"] for r in rows if r["cfg"][1] == k and r["cfg"][0] != "none" and r["oos"]["ex"] is not None]
            by_k[str(k)] = {"med_ex": round(float(np.median(v)), 2) if v else None, "beat": round(sum(x > 0 for x in v) / max(1, len(v)) * 100)}
        res[uk] = {"n": len(rows), "picked_is": pick, "oos_beat_pct": round(sum(x > 0 for x in oos_ex) / max(1, len(oos_ex)) * 100),
                   "oos_med_ex": round(float(np.median(oos_ex)), 2), "by_regime": by_reg, "by_k": by_k}
        # 사용자 원안 (미리 정함, 고르기 없음): C 판정 · 상위 3 · 전부 집중 · 상승장 아니면 S&P · 매주 · mix
        pre = ["C", 3, "full", "spy", "W", "mix"]
        nav_full, t_full = simulate(C, univ, spy, bil, R["C"], 3, "full", "spy", "W", "mix", START, end)
        res[uk]["preset"] = {"cfg": pre, "full": stats(nav_full, spy), "turn": t_full,
                             "oos": stats(nav_full[OOS_START:], spy[OOS_START:]),
                             "line": [round(float(x), 4) for x in nav_full.iloc[::21].values],
                             "spy_line": [round(float(x), 4) for x in (spy[START:] / spy[START:].iloc[0]).reindex(nav_full.index).iloc[::21].values]}
        # 지금 이 규칙이면 무엇을 담나
        M = momentum(C[univ], "mix").iloc[-1].dropna()
        ma = C[univ].rolling(200).mean().iloc[-1]
        okk = [t for t in M.index if C[t].iloc[-1] > ma[t]]
        res[uk]["now_top"] = [{"t": t, "name": NAMES.get(t, t), "mom": round(float(M[t]) * 100, 1)} for t in M[okk].sort_values(ascending=False).index[:5]]
    out["res"] = res
    exposure(C, R, spy, end, out)
    out["spy"] = {"is": stats(spy[START:IS_END]), "oos": stats(spy[OOS_START:]), "full": stats(spy[START:])}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("regime", "now", "spy")}, ensure_ascii=False, indent=1)[:5000])
    for uk in res:
        print(uk, json.dumps({k: res[uk][k] for k in ("oos_beat_pct", "oos_med_ex", "by_regime", "by_k", "picked_is")}, ensure_ascii=False)[:4000])
        print(uk, "preset", json.dumps({k: res[uk]["preset"][k] for k in ("cfg", "turn")}, ensure_ascii=False),
              json.dumps({k: res[uk]["preset"]["full"].get(k) for k in ("cagr", "ex", "mdd", "sharpe", "win12", "beat_years", "years")}),
              json.dumps({k: res[uk]["preset"]["oos"].get(k) for k in ("cagr", "ex", "mdd", "sharpe", "win12")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
