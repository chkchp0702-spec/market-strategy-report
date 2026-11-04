"""📈 11/4 10시 — 💱 「원화로 사는 사람의 환헤지 비율을 규칙으로」 (💼·🎯 100% 에 붙는 큰 칸)
  우리 포트 성적은 달러 기준이지만 실제 계좌는 원화 → 미국 칸 전체(💼·🎯 의 95%+)가 원/달러에 그대로 노출.
  바깥 재료: Quantpedia 「The Best Strategies for FX Hedging」(모멘텀·캐리·가치 신호로 헤지 비율 정하기) ·
  AQR 「Optimal Currency Hedging for International Equity Portfolios」 · WisdomTree 동적 환헤지 신호(금리차·모멘텀·가치) ·
  10/13 R4(💱 환헤지 스위치 — 그날 「수익률 패스」로 ⏸, 한 번도 숫자로 안 잼).
  헤지(H) 한 몫 원화 수익 ≈ 달러 수익 + (한국 3개월 금리 − 미국 3개월 금리) − 연 0.2%(헤지 실행·보수 차)
  헤지 안 한 몫 원화 수익 = (1+달러 수익)(1+원/달러 변화) − 1
  헤지 비율 h 는 어제 종가까지 자료로 정하고 오늘부터 · h 가 바뀌면 |Δh| × 0.1% 비용 · 레버리지 없음 · ETF·지수·환율만(생존 편향 없음)
  기준 = h 0 (지금처럼 환노출) · 앞 2008-07~2016 에서 고르고 2017~ 에서 시험 · ±20% 흔들기
→ market/lab/k1104_fxhedge.json  · 매수 추천 아님
"""
from __future__ import annotations
import datetime as dt
import io
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd

OUT = Path("market/lab/k1104_fxhedge.json")
FEE_H = 0.002      # 헤지 몫 연 비용(실행·보수 차)
SW = 0.001         # 헤지 비율 바꿀 때 |Δh| × 0.1%


def fred(sid, log):
    import requests
    for att in range(2):
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=(10, 90),
                             headers={"User-Agent": "Mozilla/5.0 (research script)"})
            if r.status_code == 200 and "," in r.text[:200]:
                d = pd.read_csv(io.StringIO(r.text))
                d.columns = ["date", "v"]
                d["v"] = pd.to_numeric(d["v"], errors="coerce")
                d = d.dropna(); d["date"] = pd.to_datetime(d["date"])
                log[sid] = f"{len(d)}개 {d['date'].min().date()}~{d['date'].max().date()}"
                return d.set_index("date")["v"]
            log[sid] = f"http {r.status_code}"
        except Exception as e:
            log[sid] = repr(e)[:160]
        time.sleep(5)
    return None


def kstats(r: pd.Series) -> dict:
    r = r.dropna()
    nav = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    cagr = nav.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * math.sqrt(252)
    return {"cagr": round(cagr * 100, 2), "vol": round(vol * 100, 1),
            "mdd": round(float((nav / nav.cummax() - 1).min()) * 100, 1),
            "sharpe": round(r.mean() * 252 / vol, 2) if vol > 0 else None}


def port_usd_returns():
    """💼·🎯 달러 일수익 (k1028_qflow 틀 = 지금 규칙: 변동성 맞춤 + 🧭 추세 주차 + 월말 흐름)"""
    from src.conc_bt import SECT, START, regimes
    from k1011_size import load
    from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
    from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC, G_PORT, RD_PORT
    C = load()
    px = ydl(["^IRX", "IEF", "KRW=X"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    krw = px.pop("KRW=X")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    sigM, fsM = make(C, DM, DQ)
    out = {}
    for nm, G, Rd, tgt, fl in (("port", G_PORT, RD_PORT, 15.0, 0.30), ("conc", G_CONC, RD_CONC, 22.0, 0.70)):
        sc = (tgt / rv).clip(upper=1.0, lower=fl).fillna(1.0)
        nav, _ = core_run(C, reg, idx, sc, sigM, fsM, G, Rd)
        out[nm] = nav.pct_change().fillna(0.0)
    out["spy"] = C["SPY"].reindex(idx).pct_change().fillna(0.0)
    return out, krw, irx, idx


def main():
    log = {}
    R, krw, irx, idx = port_usd_returns()
    from src.conc_bt import START, IS_END, OOS_START
    # 환율 정리: 하루 ±8% 넘는 튐은 자료 오류로 보고 앞 값 유지
    fx = krw.copy().sort_index()
    ch = fx.pct_change()
    fx[(ch.abs() > 0.08)] = np.nan
    fx = fx.ffill().reindex(idx.union(fx.index)).ffill().reindex(idx)
    kr = fred("IR3TIB01KRM156N", log)
    if kr is not None and len(kr) > 100:
        log["kr_used"] = "FRED IR3TIB01KRM156N (한 달 늦춤)"
        krd = kr.copy(); krd.index = krd.index + pd.offsets.MonthEnd(1)
    else:
        # FRED 가 막히면 한국은행 기준금리 변경 일정 + 0.15%p(CD 3개월 ≈ 기준금리 위) — 2018-11 뒤는 bluesharehub 정리 확인
        sched = [("2006-01-01", 3.75), ("2006-02-09", 4.00), ("2006-06-08", 4.25), ("2006-08-10", 4.50), ("2007-07-12", 4.75),
                 ("2007-08-09", 5.00), ("2008-08-07", 5.25), ("2008-10-09", 5.00), ("2008-10-27", 4.25), ("2008-11-07", 4.00),
                 ("2008-12-11", 3.00), ("2009-01-09", 2.50), ("2009-02-12", 2.00), ("2010-07-09", 2.25), ("2010-11-16", 2.50),
                 ("2011-01-13", 2.75), ("2011-03-10", 3.00), ("2011-06-10", 3.25), ("2012-07-12", 3.00), ("2012-10-11", 2.75),
                 ("2013-05-09", 2.50), ("2014-08-14", 2.25), ("2014-10-15", 2.00), ("2015-03-12", 1.75), ("2015-06-11", 1.50),
                 ("2016-06-09", 1.25), ("2017-11-30", 1.50), ("2018-11-30", 1.75), ("2019-07-18", 1.50), ("2019-10-16", 1.25),
                 ("2020-03-17", 0.75), ("2020-05-28", 0.50), ("2021-08-26", 0.75), ("2021-11-25", 1.00), ("2022-01-14", 1.25),
                 ("2022-04-14", 1.50), ("2022-05-26", 1.75), ("2022-07-13", 2.25), ("2022-08-25", 2.50), ("2022-10-12", 3.00),
                 ("2022-11-24", 3.25), ("2023-01-13", 3.50), ("2024-10-11", 3.25), ("2024-11-28", 3.00), ("2025-02-25", 2.75),
                 ("2025-05-29", 2.50), ("2026-07-16", 2.75), ("2026-08-27", 3.00)]
        krd = pd.Series({pd.Timestamp(a): v + 0.15 for a, v in sched})
        log["kr_used"] = "한국은행 기준금리 일정 + 0.15%p (FRED 막힘)"
    krd = krd.reindex(idx.union(krd.index)).ffill().reindex(idx)
    usd = irx.reindex(idx.union(irx.index)).ffill().reindex(idx)
    carry = (krd - usd)                       # %p, 헤지하면 받는(+)/내는(−) 금리차
    fxr = fx.pct_change().fillna(0.0)
    END = str(idx[-1].date())
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
           "from": START, "to": END, "log": log}
    out["fx_now"] = round(float(fx.iloc[-1]), 1)
    out["carry_now"] = round(float(carry.iloc[-1]), 2)
    out["carry_avg"] = {"is": round(float(carry[:IS_END].mean()), 2), "oos": round(float(carry[OOS_START:].mean()), 2)}
    out["fx_cagr"] = {}
    for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
        f = fx[a:b]; yrs = (f.index[-1] - f.index[0]).days / 365.25
        out["fx_cagr"][p] = round(((f.iloc[-1] / f.iloc[0]) ** (1 / yrs) - 1) * 100, 2)
    print("FX", out["fx_now"], out["carry_now"], out["carry_avg"], out["fx_cagr"], log, flush=True)

    def hedge_ratio(rule, N=200, H=1.0, th=0.0, m=20):
        ma = fx.rolling(N, min_periods=int(N * 0.8)).mean()
        if rule == "none":
            h = pd.Series(0.0, index=idx)
        elif rule == "full":
            h = pd.Series(H, index=idx)
        elif rule == "trend":            # 달러가 N일 평균 아래(약세 추세) → 헤지
            h = (fx < ma).astype(float) * H
        elif rule == "trendmom":         # 10/13 R4: N일 평균 아래 + m일 하락 중
            h = ((fx < ma) & (fx.pct_change(m) < 0)).astype(float) * H
        elif rule == "carry":            # 헤지가 금리차로 돈을 받을 때(+th 이상) 헤지
            h = (carry > th).astype(float) * H
        elif rule == "trendcarry":       # 약세 추세이고 금리차 손해가 th 보다 작을 때
            h = ((fx < ma) & (carry > -abs(th) if th else carry > -9e9)).astype(float) * H
        elif rule == "value":            # 달러가 N일(장기) 평균보다 th% 비싸면 헤지(되돌림 기대)
            h = (fx / ma - 1 > th / 100).astype(float) * H
        else:
            raise ValueError(rule)
        return h.fillna(0.0).shift(1).fillna(0.0)     # 어제 종가로 정하고 오늘부터

    CM = {"m": 1.0}

    def krw_ret(usd_r, h):
        un = (1 + usd_r) * (1 + fxr) - 1
        hd = usd_r + (carry * CM["m"] / 100 - FEE_H) / 252
        r = (1 - h) * un + h * hd
        r = r - h.diff().abs().fillna(0.0) * SW
        return r

    def ev(rule, port="port", **kw):
        h = hedge_ratio(rule, **kw)
        r = krw_ret(R[port], h)
        o = {}
        for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
            o[p] = kstats(r[a:b]); o[p]["h_avg"] = round(float(h[a:b].mean()) * 100)
            o[p]["sw_yr"] = round(float((h[a:b].diff().abs() > 0).sum()) / ((pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25), 1)
        yr = {}
        for y in range(2008, 2027):
            g = r[r.index.year == y]
            if len(g) > 5:
                yr[y] = round(float((1 + g).prod() - 1) * 100, 1)
        o["yr"] = yr
        o["h_now"] = round(float(h.iloc[-1]), 2)
        return o

    def dlt(a, b):
        return {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}

    grid_def = {"full_H1": ("full", dict(H=1.0)), "full_H0.5": ("full", dict(H=0.5))}
    for N in (50, 100, 150, 200, 250):
        for H in (0.5, 1.0):
            grid_def[f"trend_N{N}_H{H:g}"] = ("trend", dict(N=N, H=H))
            grid_def[f"trendmom_N{N}_H{H:g}"] = ("trendmom", dict(N=N, H=H))
    for th in (-1.0, 0.0, 1.0):
        for H in (0.5, 1.0):
            grid_def[f"carry_th{th:g}_H{H:g}"] = ("carry", dict(th=th, H=H))
    for N in (100, 200):
        for th in (1.0, 2.0):
            grid_def[f"trendcarry_N{N}_c{th:g}"] = ("trendcarry", dict(N=N, th=th, H=1.0))
    for N in (750, 1260):
        for th in (5, 10, 15):
            for H in (0.5, 1.0):
                grid_def[f"value_N{N}_th{th}_H{H:g}"] = ("value", dict(N=N, th=th, H=H))

    res = {}
    for port in ("port", "conc"):
        B = ev("none", port)
        spyk = ev("none", "spy")
        res[port] = {"base": B, "spy_krw": {p: spyk[p] for p in ("is", "oos")}, "grid": {}}
        print(port, "BASE", B["is"], B["oos"], flush=True)
        for k, (rule, kw) in grid_def.items():
            r = ev(rule, port, **kw)
            res[port]["grid"][k] = {"is": r["is"], "oos": r["oos"], "d": dlt(B, r), "h_now": r["h_now"]}
        g = res[port]["grid"]
        pick = max(g, key=lambda k: g[k]["d"]["is"]["sharpe"] + g[k]["d"]["is"]["cagr"] / 10)
        res[port]["is_pick"] = pick
        rule, kw = grid_def[pick]
        det = ev(rule, port, **kw)
        res[port]["pick_yr_d"] = {y: round(det["yr"][y] - B["yr"][y], 1) for y in det["yr"]}
        res[port]["pick_yr"] = det["yr"]; res[port]["base_yr"] = B["yr"]
        print(port, "PICK", pick, g[pick]["d"], flush=True)
        # 뒤 구간 플러스 칸 수(참고)
        res[port]["oos_pos"] = sum(1 for k in g if g[k]["d"]["oos"]["cagr"] > 0)
        res[port]["n"] = len(g)
        # ±20% 흔들기
        sh = {}
        vs = {}
        if "N" in kw:
            vs["N-20"] = dict(kw, N=int(round(kw["N"] * 0.8))); vs["N+20"] = dict(kw, N=int(round(kw["N"] * 1.2)))
        if "th" in kw and kw["th"]:
            vs["th-20"] = dict(kw, th=kw["th"] * 0.8); vs["th+20"] = dict(kw, th=kw["th"] * 1.2)
        if "H" in kw:
            vs["H-20"] = dict(kw, H=kw["H"] * 0.8)
            if kw["H"] < 1:
                vs["H+20"] = dict(kw, H=min(1.0, kw["H"] * 1.2))
        if rule in ("trend", "trendmom"):
            vs["m16"] = dict(kw, m=16); vs["m24"] = dict(kw, m=24)
        for nm, k2 in vs.items():
            r = ev(rule, port, **k2)
            sh[nm] = dlt(B, r)
            print(port, "SHAKE", nm, sh[nm], flush=True)
        res[port]["shake"] = sh
        cs = {}
        for m in (0.5, 0.0):     # 금리차를 절반·0 으로 놓아도(자료 근사 오차) 남나
            CM["m"] = m; cs[f"carry_x{m:g}"] = dlt(ev("none", port), ev(rule, port, **kw))
        CM["m"] = 1.0
        res[port]["carry_sens"] = cs
        print(port, "CARRY", cs, flush=True)
        # 비용 민감도: 헤지 비용 연 0.4%
    out["res"] = res
    out["note"] = ("원화 기준 · 💼 = G_PORT(S&P 47.5·나스닥 47.5·금 5) 목표 15%·아래 30% · 🎯 = G_CONC 목표 22%·아래 70% · "
                   "둘 다 🧭 추세 주차·월말 흐름 포함(k1028_qflow core_run) · 국면은 200일선 판정 A 로 둘 다 같게(💼 실제 4국면과 다름) · "
                   "헤지 몫 = 달러 수익 + (한국 3개월 금리(FRED 월, 한 달 늦춤) − 미국 3개월(^IRX)) − 연 0.2% · 환노출 몫 = 달러 수익 × 원/달러 · "
                   "헤지 비율은 어제 종가로 · 바꿀 때 |Δh|×0.1% · 한국 (H) ETF 의 실제 헤지 오차·세금 차이는 빠짐 · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
