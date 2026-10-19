"""🌙 10/19 밤 연구 #9 — ☕ 컵: 「처음 나온 날」 대신 「돌파한 날 다음 종가」부터 사기 + 손잡이 최소 일수 + RS 필터
  틀은 10/13~14 그대로: 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 출구 −5%·+15%·15일(+3% 못 넘으면 정리) · 슬롯 5·하루 새 진입 2
  킥 칸 대용 = 미국 대형주 약 90개에서 종가로 찾은 「컵 + 손잡이」 (스캐너 장부는 2026-10 이후뿐 → 긴 역사 없음, 종가만 씀 · 지금 살아남은 대형주라 생존 편향 · 일본·홍콩은 못 봄)
  컵 찾기(그날 종가까지): 왼쪽 꼭대기 L = 25~150일 전 최고 종가 · 바닥 깊이 12~40% · 오른쪽 꼭대기 R ≥ L×0.90 · R 뒤 손잡이 h일(1~25) ·
     손잡이 바닥 ≥ R×0.88 이고 컵 위쪽 절반 · 오늘 종가 < R (아직 안 뚫음) → 「컵 있음」, 돌파 기준 = R
  지금(바꾸기 전) = 「컵 있음」이 처음 켜진 날 → 다음 날 종가 매수
  새 규칙 = 어제 「컵 있음(손잡이 ≥ hmin일)」 + 오늘 종가 > R×(1+buf) 그리고 ≤ R×1.05 → 다음 날 종가 매수 · (RS 켜면 6개월 수익률 순위 상위 30%만)
  손잡이: hmin(1·2·3·4·5·6·8) × buf(0·1·2%) × RS(끔·켬) = 42조합 · 2008-07~2016 샤프로 고르고 2017~ 시험 · 회전율 × 0.1% 비용
→ market/lab/k1019_cupbrk.json
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
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1014_volw import kick_vw

OUT = Path("market/lab/k1019_cupbrk.json")
SIZE = 0.19
STK = ("AAPL MSFT AMZN GOOGL META NVDA AVGO ORCL ADBE CRM CSCO INTC AMD QCOM TXN AMAT LRCX KLAC MU ADI "
       "NFLX COST WMT HD LOW TGT NKE SBUX MCD TJX BKNG ISRG UNH JNJ LLY ABBV MRK PFE TMO DHR ABT AMGN GILD VRTX REGN "
       "JPM BAC WFC GS MS BLK SCHW AXP V MA PYPL SPGI MCO CME ICE "
       "XOM CVX COP EOG SLB CAT DE HON GE LMT RTX BA UNP UPS FDX "
       "PG KO PEP PM MO CL MDLZ NEE DUK SO LIN SHW APD ECL INTU ADP PAYX CTAS ROP MSI ANET FTNT CDNS SNPS TSCO ORLY AZO").split()
HMINS = [1, 2, 3, 4, 5, 6, 8]
BUFS = [0.0, 0.01, 0.02]


def cup_state(p):
    """그날 종가까지로 컵 상태: (손잡이 일수 h 또는 nan, 돌파 기준 R)"""
    n = len(p)
    H = np.full(n, np.nan); PIV = np.full(n, np.nan)
    for i in range(160, n):
        x = p[i]
        if np.isnan(x):
            continue
        w = p[i - 150:i - 24]
        if np.isnan(w).all():
            continue
        a = i - 150 + int(np.nanargmax(w)); L = p[a]
        seg_ = p[a:i + 1]
        b = a + int(np.nanargmin(seg_)); B = p[b]
        if not (0.60 <= B / L <= 0.88) or b >= i - 1:
            continue
        s2 = p[b:i + 1]
        r = b + int(np.nanargmax(s2)); R = p[r]
        if R < L * 0.90 or R > L * 1.05:
            continue
        h = i - r
        if not (1 <= h <= 25):
            continue
        lo = np.nanmin(p[r:i + 1])
        if lo < R * 0.88 or lo < (B + R) / 2 or x >= R:
            continue
        H[i] = h; PIV[i] = R
    return H, PIV


def main():
    C = load()
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rb, tb = base_vol(C, reg, idx)
    pre_etf = prep(C)
    df = yf.download(STK, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    S = pd.DataFrame({t: df[t]["Close"] for t in STK if t in df.columns.get_level_values(0)}).reindex(C.index).ffill(limit=5)
    U = list(S.columns)
    P = S.values
    Hs, PIVs = [], []
    for j in range(len(U)):
        h, pv = cup_state(P[:, j]); Hs.append(h); PIVs.append(pv)
    H = np.column_stack(Hs); PIV = np.column_stack(PIVs)
    REL = (S / S.shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
    RS = (S / S.shift(126)).rank(axis=1, pct=True).values
    R_ = S.pct_change().fillna(0.0).values
    bil = pre_etf[5]
    VOL = np.full_like(P, np.nan)
    has = ~np.isnan(H)
    first = has & ~np.vstack([np.zeros((1, len(U)), bool), has[:-1]])
    Hp = np.vstack([np.full((1, len(U)), np.nan), H[:-1]])
    PIVp = np.vstack([np.full((1, len(U)), np.nan), PIV[:-1]])
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}

    def go(sig):
        pre = (U, P, sig, REL, R_, bil)
        kk = kick_vw(C, idx, pre, VOL)
        nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
        knav = (1 + kk[0]).cumprod()
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
                "kick_is": seg(knav, spy, START, IS_END, kk[1]), "kick_oos": seg(knav, spy, OOS_START, END, kk[1]),
                "tr_is": tstat(kk[2], START, IS_END), "tr_oos": tstat(kk[2], OOS_START, END)}

    def brk(hmin, buf, rs):
        with np.errstate(invalid="ignore"):
            s = (Hp >= hmin) & (P > PIVp * (1 + buf)) & (P <= PIVp * 1.05)
            if rs:
                s &= RS >= rs
        return np.nan_to_num(s, nan=0).astype(bool)

    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    etf = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td), "tr_oos": tstat(kk[2], OOS_START, END)}
    cur = go(first)
    grid = []
    for hm in HMINS:
        for bf in BUFS:
            for rs in (0, 0.7):
                g = go(brk(hm, bf, rs)); g.update({"hmin": hm, "buf": bf, "rs": rs}); grid.append(g)
    best = max(grid, key=lambda g: (g["is"]["sharpe"], g["is"]["cagr"]))
    shake = []
    hm0, bf0, rs0 = best["hmin"], best["buf"], best["rs"]
    for what, kw in ((f"hmin={max(1, round(hm0 * 0.8))}", (max(1, round(hm0 * 0.8)), bf0, rs0)),
                     (f"hmin={max(hm0 + 1, round(hm0 * 1.2))}", (max(hm0 + 1, round(hm0 * 1.2)), bf0, rs0)),
                     (f"buf={round(bf0 * 0.8 if bf0 else 0.002, 4)}", (hm0, bf0 * 0.8 if bf0 else 0.002, rs0)),
                     (f"buf={round(bf0 * 1.2 if bf0 else 0.005, 4)}", (hm0, bf0 * 1.2 if bf0 else 0.005, rs0))) + \
            (((f"rs={round(rs0 * 0.8, 2)}", (hm0, bf0, rs0 * 0.8)), (f"rs={round(min(0.95, rs0 * 1.2), 2)}", (hm0, bf0, min(0.95, rs0 * 1.2)))) if rs0 else ()):
        g = go(brk(*kw)); g["what"] = what; shake.append(g)

    def ok(o):
        return {"beat": bool(o["ex"] >= 0.5), "mdd": bool(o["mdd"] > spy_row["oos"]["mdd"]), "sharpe": bool(o["sharpe"] > cur["oos"]["sharpe"])}
    chk = ok(best["oos"])
    shake_ok = bool(all(all(ok(s["oos"]).values()) for s in shake))
    verdict = "✅ 통과" if all(chk.values()) and shake_ok else ("➖ 애매" if any(chk.values()) else "❌ 기각")
    rank_cor = float(pd.Series([g["is"]["sharpe"] for g in grid]).rank().corr(pd.Series([g["oos"]["sharpe"] for g in grid]).rank()))
    beat_cur = sum(1 for g in grid if g["oos"]["sharpe"] > cur["oos"]["sharpe"])
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "n_stocks": len(U), "signals_first": int(first.sum()), "spy": spy_row, "etf_current": etf, "current_cup_first": cur, "best": best,
           "check": chk, "shake_ok": shake_ok, "verdict": verdict,
           "is_oos_rank_cor": round(rank_cor, 2), "grid_beat_current_oos": f"{beat_cur}/{len(grid)}", "shake": shake,
           "grid": [{"hmin": g["hmin"], "buf": g["buf"], "rs": g["rs"], "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"],
                     "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"], "oos_turn": g["oos"].get("turn"),
                     "tr_is": g["tr_is"], "tr_oos": g["tr_oos"]} for g in grid],
           "note": "킥 칸 대용 = 미국 대형주 약 90개 종가 컵+손잡이(생존 편향·종가만·일본/홍콩 없음) · 기본 = C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 지금 = 컵 처음 나온 날 다음 종가 / 새 = 돌파한 날 다음 종가 · 앞 2008-07~2016 고르기 / 뒤 2017~ 시험 · 회전율×0.1% 비용 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("종목", len(U), "처음 나온 신호", int(first.sum()))
    print("SPY", spy_row["oos"])
    print("ETF 지금", etf["oos"], etf["tr_oos"])
    print("컵 처음", cur["oos"], cur["tr_is"], cur["tr_oos"])
    print("고른", hm0, bf0, rs0, best["is"]["sharpe"], best["oos"], best["tr_is"], best["tr_oos"])
    print("순위상관", round(rank_cor, 2), "나은 조합", beat_cur, "/", len(grid))
    for g in grid:
        print(g["hmin"], g["buf"], g["rs"], "IS", g["is"]["sharpe"], g["tr_is"].get("avg"), "| OOS", g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sharpe"], g["tr_oos"])
    for s in shake:
        print(s["what"], s["oos"]["cagr"], s["oos"]["mdd"], s["oos"]["sharpe"])
    print(verdict, chk, shake_ok)


if __name__ == "__main__":
    main()
