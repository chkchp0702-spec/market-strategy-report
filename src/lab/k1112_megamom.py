"""📈 11/12 16시 — k1112_megamom: 「지수 안의 강한 것」 — 🎯 코어를 대형 성장 ETF·대형주 개별 종목 모멘텀으로
  사용자 11/11 16시: 레버리지·곱버스 금지 · 집중 종목·개별주 모멘텀 허용 · 낙폭 같이 보여 주기
  12시(k1112_strongcore): 섹터·테마 ETF 몰기 ❌ · 나스닥 100% 뒤 +2.36(위험 몫) → 이번엔 한 단계 더 안쪽(종목)
  크기 산수: 🎯 코어 100% × (대형주 12-1 모멘텀 상위 N 의 QQQ 대비 초과 ≈ 2~5%p) × 주식 평균 0.95 ≈ 2~4.7 → 통과
  틀: k1106_exectime3.run (예약 종가판) — 국면·월말 흐름·🧭 추세 칸·금 그대로 · 코어 두 칸만 바꿈 · 변동성 맞춤은 바뀐 코어의 20일 변동성(목표·한도 그대로)
  A) ETF: XLG(상위 50)·MGK(대형 성장)·OEF(S&P100)·IWF·IVW·VUG — 전부 / QQQ 반반
  B) 개별주 모멘텀(LB 일 수익, 최근 21일 뺌, 상위 N 같은 비중, 달 1회): 무리 = 「그 때 알던 대형주」
     PIT = 2008 중반 시총 상위 40(2008-07~2016) → 2016 말 시총 상위 40(2017~) 로 한 번 바꿈 — 기억으로 만든 근사 목록, 2008 목록에서 상장폐지된 것 없음
     NOW = 지금 시총 상위 30 (생존 편향 상한 — 판정에 안 씀)
  판: 고르기 = 앞 2008-07~2016(낙폭이 SPY 앞보다 얕은 것) → 뒤 2017~ 시험 · 흔들기 LB·N ±20% · 비용 0.25% · 💼 판 · Q11/12-1(Q100) 흔들기 목표 ±20%·0.25%
→ market/lab/k1112_megamom.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, THEME, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS
from k1112_strongcore import basket, yearly

OUT = Path("market/lab/k1112_megamom.json")
A = math.sqrt(252) * 100
ETFS = ["XLG", "MGK", "OEF", "IWF", "IVW", "VUG"]
U08 = ["XOM", "GE", "MSFT", "WMT", "JNJ", "PG", "CVX", "T", "IBM", "GOOGL", "BAC", "JPM", "AAPL", "KO", "PFE", "CSCO", "INTC", "PM",
       "ORCL", "HPQ", "WFC", "VZ", "PEP", "ABT", "COP", "MRK", "SLB", "BRK-B", "C", "AMGN", "QCOM", "MO", "UPS", "MCD", "OXY", "DIS",
       "HD", "GS", "CMCSA", "UNH"]
U17 = ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM", "AMZN", "META", "JNJ", "JPM", "GE", "WFC", "T", "BAC", "PG", "CVX", "VZ", "PFE", "WMT",
       "CMCSA", "KO", "MRK", "INTC", "CSCO", "HD", "V", "PM", "PEP", "ORCL", "DIS", "UNH", "IBM", "C", "MO", "AMGN", "MMM", "MCD", "MA",
       "ABBV", "BMY", "GILD"]
UNOW = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM", "LLY", "V", "UNH", "XOM", "MA", "COST", "HD",
        "PG", "JNJ", "WMT", "ORCL", "NFLX", "ABBV", "BAC", "CRM", "AMD", "KO", "CVX", "MRK", "PEP"]


def closes(tk):
    import yfinance as yf
    out = {}
    for i in range(0, len(tk), 20):
        part = tk[i:i + 20]
        for att in range(3):
            try:
                df = yf.download(part, start="2006-01-01", auto_adjust=True, progress=False, group_by="ticker", threads=True)
                for t in part:
                    if t in df.columns.get_level_values(0):
                        s = df[t]["Close"].dropna()
                        if len(s) > 100:
                            out[t] = s
                break
            except Exception:
                import time; time.sleep(5 * (att + 1))
    return out


def pit_basket(C, lb, n, cost):
    """2008 목록으로 고른 바구니(뒤 시작 전까지) + 2016 말 목록 바구니(뒤부터) 이어 붙임 — 이어지는 날 회전 비용 1번"""
    r1, t1, h1 = basket(C, U08, lb, n, cost)
    r2, t2, h2 = basket(C, U17, lb, n, cost)
    cut = pd.Timestamp(OOS_START)
    r = pd.concat([r1[r1.index < cut], r2[r2.index >= cut]])
    h = {**{k: v for k, v in h1.items() if k < OOS_START}, **{k: v for k, v in h2.items() if k >= OOS_START}}
    return r, h


def main():
    C = load()
    xs = closes(ETFS + sorted(set(U08) | set(U17) | set(UNOW)))
    out_missing = [t for t in ETFS + sorted(set(U08) | set(U17) | set(UNOW)) if t not in xs]
    print("받기 실패", out_missing, flush=True)
    for t, s_ in xs.items():
        if t not in C.columns:
            C[t] = s_.reindex(C.index).ffill(limit=5)
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {k: px.pop(k) for k in ["SPY", "QQQ", "GLD"]}
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill(); O["TLT"] = px["TLT"]
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    msig, mfs = make(C, DM, DQ)
    sig1, fs1 = msig.shift(-1).fillna(0.0), mfs.shift(-1).fillna(0.0)

    # 기준 재현용: 진짜 밤·낮 몫
    ONr = pd.DataFrame(0.0, index=C.index, columns=KEYS); IDr = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ONr[k] = on; IDr[k] = (1 + cc) / (1 + on) - 1
    IDr["TRD"] = C["TRD"].pct_change().fillna(0.0)
    Z = pd.DataFrame(0.0, index=C.index, columns=KEYS)

    def full(e1, e2):
        D = pd.DataFrame(0.0, index=C.index, columns=KEYS)
        D["SPY"] = e1; D["QQQ"] = e2
        D["GLD"] = C["GLD"].pct_change().fillna(0.0); D["BND"] = C["TLT"].pct_change().fillna(0.0)
        D["TRD"] = C["TRD"].pct_change().fillna(0.0)
        return D

    rS = C["SPY"].pct_change().fillna(0.0); rQ = C["QQQ"].pct_change().fillna(0.0)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "spy": {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END), "yr": yearly(spy)},
           "qqq": {"is": seg(C["QQQ"].reindex(idx), spy, START, IS_END), "oos": seg(C["QQQ"].reindex(idx), spy, OOS_START, END),
                   "yr": yearly(C["QQQ"].reindex(idx))}}
    res = {}
    TG = {"conc": (22.0, 0.70, G_CONC, RD_CONC), "port": (15.0, 0.30, G_PORT, RD_PORT)}

    def go(nm, base, e1, e2, cost=0.001, volon=True, ON=None, ID=None, tgt=None):
        t_, fl, G, Rd = TG[base]
        t_ = tgt or t_
        rr = 0.5 * e1 + 0.5 * e2
        sc = (t_ / (rr.rolling(20).std() * A)).clip(upper=1.0, lower=fl).fillna(1.0) if volon else pd.Series(1.0, index=C.index)
        ID_ = full(e1, e2) if ID is None else ID
        ON_ = Z if ON is None else ON
        nav, td = run(C, ON_, ID_, reg, idx, sc, sig1, fs1, G, Rd, "c1", cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        yr = yearly(nav)
        res[nm] = {"is": a, "oos": b, "yr": yr, "worst_oos": min(v for y, v in yr.items() if y >= 2017),
                   "worst_is": min(v for y, v in yr.items() if y < 2017), "eq_up": round(float(sc.reindex(idx).mean()) * 100, 1)}
        print(nm, "앞", a["cagr"], a["mdd"], "| 뒤", b["cagr"], b["mdd"], b["sharpe"], "최악", res[nm]["worst_oos"], flush=True)
        return nav

    # 0) 기준 재현: 진짜 밤·낮 vs 통째 일수익(c1 이면 같아야)
    go("base_real", "conc", rS, rQ, ON=ONr, ID=IDr)
    go("base", "conc", rS, rQ)
    out["repro_diff"] = {p: round(res["base"][p]["cagr"] - res["base_real"][p]["cagr"], 3) for p in ("is", "oos")}
    go("port_base", "port", rS, rQ)
    go("base_novol", "conc", rS, rQ, volon=False)
    go("Q100", "conc", rQ, rQ)
    go("Q100_novol", "conc", rQ, rQ, volon=False)

    out["missing"] = out_missing
    go("Q100__t-20", "conc", rQ, rQ, tgt=17.6)
    go("Q100__t+20", "conc", rQ, rQ, tgt=26.4)
    go("Q100__c25", "conc", rQ, rQ, cost=0.0025)
    go("base__c25", "conc", rS, rQ, cost=0.0025)
    go("port_base__c25", "port", rS, rQ, cost=0.0025)
    go("Q100__port", "port", rQ, rQ)

    # A) ETF
    for e in ETFS:
        if e in C.columns:
            re_ = C[e].pct_change().fillna(0.0)
            go(f"E_{e}", "conc", re_, re_)
            go(f"E_{e}_halfQ", "conc", rQ, re_)

    # B) 개별주 모멘텀
    holds = {}
    BK = {}
    for lb in (126, 252):
        for n in (5, 10, 15):
            br, hd = pit_basket(C, lb, n, 0.001)
            BK[("PIT", lb, n)] = br
            holds[f"PIT_{lb}_{n}"] = dict(list(hd.items())[-3:])
            go(f"PIT_L{lb}_N{n}", "conc", br, br)
            go(f"PIT_L{lb}_N{n}_halfQ", "conc", rQ, br)
            bn, _, hn = basket(C, UNOW, lb, n, 0.001)
            go(f"NOW_L{lb}_N{n}", "conc", bn, bn)
    # 같은 무리 같은 비중(모멘텀 없이) — 「고르기」 몫과 「무리」 몫 가르기
    for nm_, U in (("PITEW", None), ("NOWEW", UNOW)):
        if U is None:
            r1, _, _ = basket(C, U08, 1, len(U08), 0.001); r2, _, _ = basket(C, U17, 1, len(U17), 0.001)
            cut = pd.Timestamp(OOS_START); br = pd.concat([r1[r1.index < cut], r2[r2.index >= cut]])
        else:
            br, _, _ = basket(C, U, 1, len(U), 0.001)
        go(nm_, "conc", br, br)
    out["holds_recent"] = holds

    spy_is_mdd = out["spy"]["is"]["mdd"]
    picks = {}
    for fam, pre in (("ETF_full", "E_"), ("PIT", "PIT_L")):
        for form in ("", "_halfQ"):
            c = [k for k in res if k.startswith(pre) and "__" not in k and (k.endswith("_halfQ") == bool(form)) and res[k]["is"]["mdd"] > spy_is_mdd]
            if c:
                picks[f"{fam}{form or '_full'}"] = max(c, key=lambda k: res[k]["is"]["cagr"])
    out["picks"] = picks
    print("PICKS", picks, flush=True)

    shake = {}
    for pk, nm in picks.items():
        half = nm.endswith("_halfQ")
        sh = {}
        if nm.startswith("PIT_"):
            lb = int(nm.split("_L")[1].split("_")[0]); n = int(nm.split("_N")[1].split("_")[0])
            for tag, (lb2, n2) in {"lb-20": (int(lb * .8), n), "lb+20": (int(lb * 1.2), n), "n-20": (lb, max(2, round(n * .8))), "n+20": (lb, round(n * 1.2))}.items():
                b2, _ = pit_basket(C, lb2, n2, 0.001)
                go(f"{nm}__{tag}", "conc", rQ if half else b2, b2); sh[tag] = f"{nm}__{tag}"
            b25, _ = pit_basket(C, lb, n, 0.0025)
            go(f"{nm}__c25", "conc", rQ if half else b25, b25, cost=0.0025); sh["c25"] = f"{nm}__c25"
            br = BK[("PIT", lb, n)]
        else:
            e = nm.split("_")[1]; br = C[e].pct_change().fillna(0.0)
            go(f"{nm}__c25", "conc", rQ if half else br, br, cost=0.0025); sh["c25"] = f"{nm}__c25"
        go(f"{nm}__t-20", "conc", rQ if half else br, br, tgt=17.6); sh["t-20"] = f"{nm}__t-20"
        go(f"{nm}__t+20", "conc", rQ if half else br, br, tgt=26.4); sh["t+20"] = f"{nm}__t+20"
        go(f"{nm}__novol", "conc", rQ if half else br, br, volon=False); sh["novol"] = f"{nm}__novol"
        go(f"{nm}__port", "port", rQ if half else br, br); sh["port"] = f"{nm}__port"
        shake[pk] = sh
    out["shake"] = shake
    out["res"] = res
    out["note"] = ("🎯 틀(목표 22·아래 0.70·국면 25/25·월말 흐름 s1·c1 예약 종가·🧭 추세 칸)에서 코어 두 칸만 바꿈 · 변동성 맞춤은 바뀐 코어의 20일 변동성 · "
                   "PIT 무리 = 2008 중반 시총 상위 40 → 2016 말 상위 40(기억 근사 목록) · NOW = 지금 상위 30(생존 편향 상한, 판정 제외) · "
                   "비용 0.1%(c25 = 0.25%, 바구니 회전에도) · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
