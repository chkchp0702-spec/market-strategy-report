"""📈 11/20 12시 2번째 — k1120_n100mix: (k1120_n100pit 의 이어 실험) 주식 칸 절반 QQQ·절반 바구니(MIX50) 9판 전부·9판 평균·앙상블 바구니·💼 앞 1등 흔들기\n  원본 설명 ↓ k1120_n100pit: 🎯 코어(QQQ)를 「나스닥100 당시 구성 종목 중 강한 종목 Top N」으로 바꾸기
  사실(11/19): 🎯 NEW 뒤 21.49 vs QQQ 그냥 들기 19.67 — +3 은 코어가 QQQ 보다 연 ≈5%p 센 자산이어야 닿음
               지수·섹터·대형주 모멘텀(근사 목록)·변동성 한도·국면 4종 손잡이 모두 닫힘 → 남은 곳 = 개별주(당시 구성 종목)
  자료: sukhcs/n100tickers(PyPI nasdaq-100-ticker-history · tickers_as_of) — 2015-01~ 당시 구성 종목 → 생존 편향을 크게 줄인 판
        (편출 후 상장폐지·인수된 종목은 야후 가격이 없어 빠짐 = 남은 생존 편향 · 개수를 같이 적음)
  처방 판: 달 마지막 거래일, 전날 종가까지 「최근 21일 뺀 LB 일 수익」 상위 N(그날 구성 종목 안에서) 같은 비중 → 그날 종가 체결
           LB 63·126·252 × N 5·10·20 = 9판 · 그 바구니 일별 수익을 🎯 NEW 의 주식 칸(SPY·QQQ 자리)에 넣음(국면·흐름·변동성 맞춤 그대로)
           MIX = 주식 칸 절반 QQQ · 절반 바구니
  나눔: 자료가 2015~ 라 「앞 2015-01~2020-12 에서 고르고 뒤 2021-01~ 에서 시험」(2008 형 시험 없음 = 한계)
  크기 산수: 코어 비중(🎯 🟢 ≈70~100%) × 바구니가 QQQ 보다 더 버는 몫 — 11/12 근사 목록 대형주 모멘텀은 앞 전부 미달 → 기대 낮음, 사실 확인용
  틀: k1106_exectime3.run 예약 종가판 c1 (k1119_rateshock 과 같은 손잡이) · 비용 0.1%(0.25% 도) · 레버리지 없음
→ market/lab/k1120_n100pit.json
"""
from __future__ import annotations
import datetime as dt, json, math, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.conc_bt import SECT, START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS
from k1112_strongcore import yearly

OUT = Path("market/lab/k1120_n100mix.json")
A = math.sqrt(252) * 100
P_START, P_IS_END, P_OOS = "2015-01-01", "2020-12-31", "2021-01-01"
REN = {"FB": "META", "PCLN": "BKNG", "CTRP": "TCOM", "WLTW": "WTW", "SYMC": "GEN", "NLOK": "GEN", "KRFT": "KHC",
       "GOOGL": "GOOGL", "BRK.B": "BRK-B", "LILA": "LILA", "LILAK": "LILAK"}


def members_fn():
    try:
        from nasdaq_100_ticker_history import tickers_as_of
    except Exception:
        for spec in ("nasdaq-100-ticker-history", "git+https://github.com/sukhcs/n100tickers"):
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", spec], capture_output=True, text=True)
            print("pip", spec, r.returncode, r.stderr[-300:], flush=True)
            try:
                from nasdaq_100_ticker_history import tickers_as_of
                break
            except Exception as e:
                print("import 실패", e, flush=True)
        else:
            raise SystemExit("당시 구성 종목 자료를 못 불러옴")
    cache = {}

    def mem(d):
        key = (d.year, d.month)
        if key not in cache:
            y, m, out = d.year, d.month, None
            for _ in range(24):                     # 자료 끝(2026-04 무렵) 뒤면 마지막 목록
                try:
                    out = tickers_as_of(y, m, 1)
                    if out:
                        break
                except Exception:
                    pass
                m -= 1
                if m == 0:
                    y, m = y - 1, 12
            cache[key] = frozenset(out or [])
        return cache[key]
    return mem


def ysym(t):
    t = str(t).strip().upper()
    return REN.get(t, t.replace(".", "-"))


def closes(tk):
    import yfinance as yf
    out = {}
    for i in range(0, len(tk), 25):
        part = tk[i:i + 25]
        for att in range(3):
            try:
                df = yf.download(part, start="2013-06-01", auto_adjust=True, progress=False, group_by="ticker", threads=True)
                for t in part:
                    if isinstance(df.columns, pd.MultiIndex) and t in df.columns.get_level_values(0):
                        s = df[t]["Close"].dropna()
                        if len(s) > 60:
                            out[t] = s
                break
            except Exception:
                import time; time.sleep(5 * (att + 1))
    return out


def pit_basket(P, idx, mem, lb, n, cost):
    """달 마지막 거래일 · 전날 종가 모멘텀 · 그날 구성 종목 안 상위 n 같은 비중 · 그날 종가 체결"""
    R = P.pct_change()
    mom = P.shift(21) / P.shift(21 + lb) - 1
    mon = pd.Series(idx.month, index=idx)
    is_last = mon != mon.shift(-1)
    w, rets, turns, hold = {}, [], [], {}
    t0 = pd.Timestamp(P_START) - pd.Timedelta(days=40)
    for i, d in enumerate(idx):
        r = 0.0
        if w:
            rr = {k: (0.0 if pd.isna(R.at[d, k]) else R.at[d, k]) for k in w}
            r = sum(w[k] * rr[k] for k in w)
            nw = {k: w[k] * (1 + rr[k]) for k in w}; s_ = sum(nw.values()); w = {k: v / s_ for k, v in nw.items()}
        tv = 0.0
        if is_last.iloc[i] and i >= 1 and d >= t0:
            ms = {ysym(t) for t in mem(d)}
            m = mom.iloc[i - 1][[c for c in P.columns if c in ms]].dropna()
            if len(m) >= n:
                pick = list(m.sort_values(ascending=False).index[:n])
                t = {k: 1.0 / n for k in pick}
                tv = sum(abs(t.get(k, 0) - w.get(k, 0)) for k in set(t) | set(w)) / 2 if w else 1.0
                w = t; hold[str(d.date())] = pick
                r -= tv * cost
        rets.append(r); turns.append(tv)
    return pd.Series(rets, index=idx).fillna(0.0), pd.Series(turns, index=idx), hold


def main():
    mem = members_fn()
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False).astype(bool)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    ms_, fs_ = make(C, DM, DQ, f=1.0, K=5)
    sig, fs = ms_.shift(-1).fillna(0.0), fs_.shift(-1).fillna(0.0)

    # 당시 구성 종목 전체 · 가격
    months = pd.date_range(P_START, END, freq="MS")
    allm = sorted({t for d in months for t in mem(d)})
    syms = sorted({ysym(t) for t in allm})
    print("구성 종목(2015~) 고유", len(allm), "야후 기호", len(syms), flush=True)
    got = closes(syms)
    miss = sorted(set(syms) - set(got))
    print("가격 없음", len(miss), miss, flush=True)
    P = pd.DataFrame(got).reindex(C.index).ffill(limit=5)
    # 구성 종목-달 중 가격 없는 비율(남은 생존 편향 크기)
    mm_tot = mm_miss = 0
    for d in months:
        for t in mem(d):
            mm_tot += 1; mm_miss += (ysym(t) not in got)
    miss_pct = round(mm_miss / max(mm_tot, 1) * 100, 1)
    print("구성 종목-달 가격 없음", miss_pct, "%", flush=True)

    rQ = C["QQQ"].pct_change().fillna(0.0)
    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}
    W = {"is": (P_START, P_IS_END), "oos": (P_OOS, END), "all": (P_START, END)}
    cut = pd.Timestamp(P_START)

    def full(e):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e; D["QQQ"] = e
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    BK = {}
    def bk(lb, n, cost=0.001):
        key = (lb, n, cost)
        if key not in BK:
            r, t, h = pit_basket(P, C.index, mem, lb, n, cost)
            r = rQ.where(C.index < cut, r)          # 2015 전은 QQQ(창 밖)
            BK[key] = (r, t, h)
        return BK[key]

    res, pure = {}, {}
    def stat(nav):
        o = {k: seg(nav, spy, a, b) for k, (a, b) in W.items()}
        yr = yearly(nav, 2015); o["yr"] = yr
        o["worst_oos"] = min(v for y, v in yr.items() if y >= 2021)
        return o

    def go(nm, e, base="conc", cost=0.001):
        t0, fl0, G, Rd = TG[base]
        sc = (t0 / (rQ.rolling(20).std() * A)).clip(upper=1.0, lower=fl0).fillna(1.0)
        nav, td = run(C, Z, full(e), reg, idx, sc, sig, fs, G, Rd, "c1", cost)
        r = stat(nav); res[nm] = r
        print(nm, "앞", r["is"]["cagr"], r["is"]["mdd"], "| 뒤", r["oos"]["cagr"], r["oos"]["mdd"], "최악", r["worst_oos"],
              "| 해", r["yr"], flush=True)
        return r

    go("NEW", rQ); go("P_NEW", rQ, "port"); go("NEW_c25", rQ, cost=0.0025); go("P_NEW_c25", rQ, "port", cost=0.0025)
    grid = []
    for lb in (63, 126, 252):
        for n in (5, 10, 20):
            e = 0.5 * rQ + 0.5 * bk(lb, n)[0]
            go(f"X{lb}_{n}", e); go(f"PX{lb}_{n}", e, "port"); grid.append((lb, n))
    for base, pre in (("conc", "X"), ("port", "PX")):
        res[f"{pre}_AVG"] = {"oos_cagr_mean": round(sum(res[f"{pre}{g[0]}_{g[1]}"]["oos"]["cagr"] for g in grid) / len(grid), 2),
                             "is_cagr_mean": round(sum(res[f"{pre}{g[0]}_{g[1]}"]["is"]["cagr"] for g in grid) / len(grid), 2)}
        print(pre, "9판 평균", res[f"{pre}_AVG"], flush=True)
    # 바구니 고르기 운 없애기: 9판 바구니를 똑같이 섞은 「앙상블」 바구니
    ens = sum(bk(g[0], g[1])[0] for g in grid) / len(grid)
    go("ENS50", 0.5 * rQ + 0.5 * ens); go("P_ENS50", 0.5 * rQ + 0.5 * ens, "port"); go("P_ENS100", ens, "port")
    ens25 = sum(bk(g[0], g[1], 0.0025)[0] for g in grid) / len(grid)
    go("P_ENS50_c25", 0.5 * rQ + 0.5 * ens25, "port", cost=0.0025)
    best = max(grid, key=lambda g: res[f"PX{g[0]}_{g[1]}"]["is"]["cagr"])
    lb, n = best
    print("💼 MIX 앞 1등", best, flush=True)
    for lb2 in (int(round(lb * 0.8)), int(round(lb * 1.2))):
        go(f"PB_lb{lb2}", 0.5 * rQ + 0.5 * bk(lb2, n)[0], "port")
    for n2 in (max(2, int(round(n * 0.8))), int(round(n * 1.2))):
        go(f"PB_n{n2}", 0.5 * rQ + 0.5 * bk(lb, n2)[0], "port")
    for wq in (0.4, 0.6):
        go(f"PB_w{int(wq*100)}", wq * rQ + (1 - wq) * bk(lb, n)[0], "port")
    go("PB_c25", 0.5 * rQ + 0.5 * bk(lb, n, 0.0025)[0], "port", cost=0.0025)
    bo = max(grid, key=lambda g: res[f"PX{g[0]}_{g[1]}"]["oos"]["cagr"])
    qqq = C["QQQ"].reindex(idx)
    h = bk(lb, n)[2]
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": P_START, "to": END,
           "split": [P_START, P_IS_END, P_OOS],
           "spy": {k: seg(spy, spy, a, b) for k, (a, b) in W.items()}, "qqq": {k: seg(qqq, spy, a, b) for k, (a, b) in W.items()},
           "spy_yr": yearly(spy, 2015), "qqq_yr": yearly(qqq, 2015),
           "best": f"PX{lb}_{n}", "best_oos": f"PX{bo[0]}_{bo[1]}", "res": res, "pure": pure,
           "members": {"unique": len(allm), "ysyms": len(syms), "no_price": miss, "member_month_missing_pct": miss_pct},
           "best_hold_last": dict(list(h.items())[-6:]),
           "note": ("k1106_exectime3.run 예약 종가판 c1 · 비용 0.1% · NEW = 🎯 NEW(QQQ+흐름1.0) · P_ = 💼 판 · "
                    "M<LB>_<N> = 🎯 주식 칸을 나스닥100 당시 구성 종목 중 (21일 뺀 LB 일 수익) 상위 N 같은 비중 달 1회 바구니로 · "
                    "pure B = 바구니만(국면·흐름 없음) · MIX50 = 주식 칸 절반 QQQ 절반 바구니 · 변동성 맞춤은 QQQ 변동성 기준 그대로 · "
                    "앞 2015-01~2020-12 / 뒤 2021-01~ · 가격 없는 편출 종목은 빠짐(남은 생존 편향, member_month_missing_pct) · "
                    "레버리지 없음 · 매수 추천 아님")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
