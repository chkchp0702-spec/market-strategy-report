"""📈 10/29 12시 — 🏦 「연준 순유동성(시장에 실제로 풀린 돈) 마를 때 주식 덜기」
  바깥 재료: 유튜브·X·국내 블로그에서 크게 도는 「순유동성 = 연준 자산(WALCL) − 재무부 현금 계좌(TGA) − 역레포(RRP)」
  (TMS 「QRA와 베센트: 순유동성」, TradingView Fed Net Liquidity 스크립트, eco3min 순유동성 자료).
  메커니즘: 재무부가 국채를 많이 팔아 TGA 를 채우거나 연준이 자산을 줄이면 은행 지준(시장에 도는 현금)이 억지로 빠짐 → 위험자산 약함.
  우리 장부엔 처음 들어오는 자료(FRED 주간 H.4.1 · 하루 RRP).
  자료 늦음 반영: 수요일 값 → 목요일 오후 발표 → 금요일 종가 판단·다음 거래일 체결(수요일 +2일 뒤부터 씀).
  ① 맞대기: 마름(L주 변화 < th) 날의 SPY 다음 20일 수익 vs 아닌 날 (앞/뒤)
  ② 💼 지금 규칙(월말 흐름 포함, k1028_qflow 틀) 위에: 마름이면 주식 칸 × (1−f) → 덜어낸 몫은 🧭 추세 칸
     격자 L∈{4,8,13}주 · th∈{0, −1%, −2%} · f∈{0.3, 0.5} → 앞에서 1등 골라 뒤에서 시험 · ±20% 흔들기
     대조군: 신호 뒤집기(늘 때 덜기) — 그냥 주식 덜어서 좋아진 건지 확인
  ③ 🎯 집중(목표 22%·한도 70%)에도 같은 판
  하루 늦은 체결 · 회전 × 0.1% · 레버리지 없음 · ETF 만(생존 편향 없음) · 매수 추천 아님
→ market/lab/k1029_netliq.json
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
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import core_run, make, drifts, G_PORT, RD_PORT, G_CONC, RD_CONC

OUT = Path("market/lab/k1029_netliq.json")


def fred(sid, log):
    import requests
    for att in range(4):
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=60,
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


def netliq(log):
    w = fred("WALCL", log)        # 백만 달러, 수요일
    t = fred("WTREGEN", log)      # 십억 달러, 수요일
    r = fred("RRPONTSYD", log)    # 십억 달러, 하루
    if w is None or t is None:
        return None
    wk = pd.DataFrame({"W": w / 1000.0}).join(pd.DataFrame({"T": t}), how="left")
    wk["T"] = wk["T"].ffill()
    if r is not None:
        rr = r.reindex(pd.date_range(r.index.min(), wk.index.max())).ffill()
        wk["R"] = rr.reindex(wk.index).fillna(0.0)
    else:
        wk["R"] = 0.0
    wk = wk.dropna()
    wk["NL"] = wk["W"] - wk["T"] - wk["R"]
    return wk


def main():
    log = {}
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    wk = netliq(log)
    out["log"] = log
    if wk is None:
        out["verdict"] = "➖ FRED 자료를 못 받음"
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"); print(out); return
    out["nl_now"] = {"date": str(wk.index[-1].date()), "NL_bn": round(float(wk["NL"].iloc[-1]), 1),
                     "chg4": round(float(wk["NL"].iloc[-1] / wk["NL"].iloc[-5] - 1) * 100, 2),
                     "chg13": round(float(wk["NL"].iloc[-1] / wk["NL"].iloc[-14] - 1) * 100, 2)}

    def drain(L, th, inv=False):
        ch = wk["NL"] / wk["NL"].shift(L) - 1
        sig = (ch > abs(th)) if inv else (ch < th)
        avail = sig.copy(); avail.index = avail.index + pd.Timedelta(days=2)   # 목요일 발표 → 금요일 종가부터
        d = avail.reindex(avail.index.union(C.index)).ffill().reindex(C.index).fillna(False).astype(bool)
        return d

    # ① 맞대기
    fwd = C["SPY"].shift(-21) / C["SPY"].shift(-1) - 1    # 다음 날부터 20일
    ls = {}
    for L in (4, 8, 13):
        for th in (0.0, -0.01, -0.02):
            dsig = drain(L, th)
            o = {}
            for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
                m = (C.index >= a) & (C.index <= b)
                x1 = fwd[m & dsig.values].dropna(); x0 = fwd[m & ~dsig.values].dropna()
                o[p] = {"on_pct": round(len(x1) / max(1, len(x1) + len(x0)) * 100), "drain_f20": round(float(x1.mean()) * 100, 2) if len(x1) else None,
                        "else_f20": round(float(x0.mean()) * 100, 2), "gap": round(float(x1.mean() - x0.mean()) * 100, 2) if len(x1) else None}
            ls[f"L{L}_th{th}"] = o
    out["ls"] = ls
    print("LS", json.dumps(ls), flush=True)

    def go(base="port", L=None, th=0.0, f=0.0, inv=False, tgt=None, floor=None):
        G, Rd = (G_PORT, RD_PORT) if base == "port" else (G_CONC, RD_CONC)
        tgt = tgt or (15.0 if base == "port" else 22.0); floor = floor or (0.30 if base == "port" else 0.70)
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        if L:
            dsig = drain(L, th, inv)
            sc = sc * (1 - f * dsig.astype(float))
        sig, fs = make(C, DM, DQ)
        nav, td = core_run(C, reg, idx, sc, sig, fs, G, Rd)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        d = nav.pct_change().fillna(0)
        o["y"] = {y: round(((1 + d[d.index.year == y]).prod() - 1) * 100, 2) for y in range(2009, idx[-1].year + 1)}
        return o

    def dlt(a, b):
        r = {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}
        r["y"] = {y: round(b["y"][y] - a["y"][y], 2) for y in a["y"]}
        r["turn_oos"] = b["oos"].get("turn")
        return r

    res = {}
    for base in ("port", "conc"):
        B = go(base)
        g = {}
        for L in (4, 8, 13):
            for th in (0.0, -0.01, -0.02):
                for f in (0.3, 0.5):
                    k = f"L{L}_th{th}_f{f}"
                    g[k] = dlt(B, go(base, L, th, f))
                    print(base, k, g[k]["is"], g[k]["oos"], flush=True)
        pick = max(g, key=lambda k: g[k]["is"]["sharpe"] + g[k]["is"]["cagr"] / 10)
        L0 = int(pick.split("_")[0][1:]); th0 = float(pick.split("_th")[1].split("_f")[0]); f0 = float(pick.split("_f")[-1])
        sh = {}
        for nm, kw in {"L-20%": dict(L=max(2, round(L0 * 0.8))), "L+20%": dict(L=round(L0 * 1.2) if round(L0 * 1.2) != L0 else L0 + 1),
                       "f-20%": dict(f=f0 * 0.8), "f+20%": dict(f=f0 * 1.2),
                       "th-0.5%": dict(th=th0 - 0.005), "th+0.5%": dict(th=th0 + 0.005)}.items():
            kw2 = dict(L=L0, th=th0, f=f0); kw2.update(kw)
            sh[nm] = dlt(B, go(base, **kw2))
            print(base, "SHAKE", nm, sh[nm]["is"]["cagr"], sh[nm]["oos"]["cagr"], flush=True)
        ctrl = dlt(B, go(base, L0, th0, f0, inv=True))
        oos_pos = sum(1 for k in g if g[k]["oos"]["cagr"] > 0)
        res[base] = {"B": {k: B[k] for k in ("is", "oos")}, "grid": g, "pick": pick, "pick_d": g[pick], "shake": sh,
                     "ctrl_inverse": ctrl, "oos_pos": f"{oos_pos}/{len(g)}",
                     "grid_med_oos_cagr": round(float(pd.Series([g[k]['oos']['cagr'] for k in g]).median()), 2),
                     "grid_med_oos_sharpe": round(float(pd.Series([g[k]['oos']['sharpe'] for k in g]).median()), 2)}
        pdx = g[pick]
        ok = (pdx["is"]["cagr"] > 0 and pdx["oos"]["cagr"] > 0 and all(sh[k]["oos"]["cagr"] > 0 for k in sh)) or \
             (pdx["is"]["mdd"] > 0 and pdx["oos"]["mdd"] > 0 and pdx["oos"]["sharpe"] > 0 and all(sh[k]["oos"]["sharpe"] > 0 for k in sh))
        res[base]["verdict"] = "✅ 앞·뒤·흔들기 통과" if ok else "❌"
        print(base, "PICK", pick, pdx["is"], pdx["oos"], res[base]["verdict"], flush=True)
    out["res"] = res
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
