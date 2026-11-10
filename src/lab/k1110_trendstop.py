"""📈 11/10 12시 — k1110_trendstop: 🧭 자산 추세 칸의 「체결 시점」 — 미리 아는 문턱에 미리 걸어 두는 주문(감시·스톱 주문)
  지금: 종가 d 가 100일 고가를 넘으면(신호) → 다음 날 종가에 삼(c1) · 50일 저가 밑이면 다음 날 종가에 팖
  그런데 문턱(어제까지 100일 고가 · 50일 저가)은 **장 열기 전에 이미 앎** → 「그 값을 넘으면 사라/밑돌면 팔아라」를
  미리 걸어 두면(스톱 주문) 넘는 그 순간 체결 = 하루 늦음이 없음. 규칙의 문턱·가중(60일 변동성 반비례)·9종은 그대로
  판(칸 단독):
    c1   = 지금(신호 다음 날 종가)
    c0   = 같은 종가(참고 · 한국에선 불가)
    o1   = 다음 날 시가(한국 밤 23:30 예약)
    stop = 들어갈 때·나올 때 둘 다 스톱 주문 (장중 고가 ≥ 문턱이면 max(시가, 문턱)에 삼 · 장중 저가 ≤ 문턱이면 min(시가, 문턱)에 팖)
    stopin / stopout = 한쪽만 스톱, 다른 쪽은 c1
  그 칸을 💼 기본(예약 종가판 s1_c1 · 지금 실제 s0_c1)·🎯 집중에 실제 크기로 넣어 다시 돌림(k1106_exectime3.run 틀)
  흔들기: 문턱 날수 100→80·120 · 50→40·60 (stop vs c1 짝으로) · 비용 칸 0.5%(기존)·1.0%
  ⚠️ 장중 고가·저가로 체결 = 실제 스톱은 미끄러짐(슬리피지) 있음 → 체결가에 0.1% 불리하게 더 얹은 판도 같이
→ market/lab/k1110_trendstop.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1110_trendstop.json")
A = math.sqrt(252) * 100


def trend_exec(px, cdaily, nin, nout, mode_in, mode_out, cost=0.005, slip=0.0, start=None):
    """mode_*: c1 다음 날 종가 · c0 같은 종가 · o1 다음 날 시가 · stop 미리 건 문턱 주문(장중)"""
    syms = [s for s in TREND_U if s in px]
    idx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in syms])))
    if start:
        idx = idx[idx >= pd.Timestamp(start)]
    C = pd.DataFrame({s: px[s]["close"] for s in syms}).reindex(idx).ffill()
    O = pd.DataFrame({s: px[s]["open"] for s in syms}).reindex(idx)
    H = pd.DataFrame({s: px[s]["high"] for s in syms}).reindex(idx).ffill()
    L = pd.DataFrame({s: px[s]["low"] for s in syms}).reindex(idx).ffill()
    O = O.fillna(C.shift(1)).fillna(C)
    R = C.pct_change(fill_method=None).fillna(0)
    hiN = H.shift(1).rolling(nin, min_periods=nin).max()
    loM = L.shift(1).rolling(nout, min_periods=nout).min()
    vol = R.rolling(60, min_periods=40).std()
    cd = cdaily.reindex(idx).fillna(0).to_numpy()
    n, k = len(idx), len(syms)
    Cv, Ov, Hv, Lv = C.to_numpy(), O.to_numpy(), H.to_numpy(), L.to_numpy()
    Hn, Lm, V, Rv = hiN.to_numpy(), loM.to_numpy(), vol.to_numpy(), R.to_numpy()
    pos = np.zeros(k); pend = [None] * k
    ret = np.zeros(n); turn = np.zeros(n); inpos = np.zeros(n)

    def wt(i, j):
        vv = V[i]
        iv = 1 / vv
        iv = iv[np.isfinite(iv)]
        if np.isfinite(1 / V[i, j]) and iv.sum() > 0:
            return min((1 / V[i, j]) / iv.sum(), 0.35)
        return 1 / k

    for i in range(1, n):
        # 기본: 어제 비중으로 오늘 종가-종가 수익, 남는 돈은 현금
        r = float(np.dot(pos, Rv[i])) + (1 - pos.sum()) * cd[i]
        for j in range(k):
            if np.isnan(Cv[i, j]) or np.isnan(Cv[i - 1, j]):
                continue
            # 1) 대기 주문(c1·o1) 실행
            if pend[j] is not None:
                kind, w, md = pend[j]
                if kind == "in" and pos[j] == 0:
                    if md == "o1":   # 시가에 삼: 밤 몫은 현금, 낮 몫(종가/시가)만
                        r += w * (Cv[i, j] / Ov[i, j] - 1) - w * cd[i]
                        pos[j] = w
                    else:            # c1: 오늘 종가에 삼 → 오늘 수익 없음
                        pos[j] = w
                    r -= w * cost / 2; turn[i] += w
                elif kind == "out" and pos[j] > 0:
                    w0 = pos[j]
                    if md == "o1":   # 시가에 팖: 오늘 몫은 밤 몫만
                        r += w0 * (Ov[i, j] / Cv[i - 1, j] - 1) - w0 * Rv[i, j] + w0 * cd[i]
                    pos[j] = 0.0  # c1: 오늘 종가 수익은 이미 받음
                    r -= w0 * cost / 2; turn[i] += w0
                pend[j] = None
            if np.isnan(Hn[i, j]) or np.isnan(Lm[i, j]):
                continue
            # 2) 스톱 주문(문턱은 어제까지 자료로 이미 앎) — 오늘 장중 체결
            if pos[j] == 0 and mode_in == "stop" and Hv[i, j] >= Hn[i, j]:
                w = wt(i - 1, j)
                px_e = max(Ov[i, j], Hn[i, j]) * (1 + slip)
                r += w * (Cv[i, j] / px_e - 1) - w * cd[i] - w * cost / 2
                pos[j] = w; turn[i] += w
                continue
            if pos[j] > 0 and mode_out == "stop" and Lv[i, j] <= Lm[i, j]:
                w0 = pos[j]
                px_x = min(Ov[i, j], Lm[i, j]) * (1 - slip)
                # 이미 w0*R(종가/어제종가) 받음 → 체결가까지로 고침
                r += w0 * (px_x / Cv[i - 1, j] - 1) - w0 * Rv[i, j] + w0 * cd[i] - w0 * cost / 2
                pos[j] = 0.0; turn[i] += w0
                continue
            # 3) 종가 신호(c0·c1·o1)
            if pos[j] == 0 and mode_in != "stop" and Cv[i, j] > Hn[i, j]:
                w = wt(i, j)
                if mode_in == "c0":
                    pos[j] = w; r -= w * cost / 2; turn[i] += w
                else:
                    pend[j] = ("in", w, mode_in)
            elif pos[j] > 0 and mode_out != "stop" and Cv[i, j] < Lm[i, j]:
                if mode_out == "c0":
                    w0 = pos[j]; pos[j] = 0.0; r -= w0 * cost / 2; turn[i] += w0
                else:
                    pend[j] = ("out", None, mode_out)
        ret[i] = r; inpos[i] = pos.sum()
    return pd.Series(ret, index=idx), pd.Series(turn, index=idx), pd.Series(inpos, index=idx)


def sstat(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]
    if len(x) < 50:
        return {}
    nav = (1 + x).cumprod()
    yrs = (x.index[-1] - x.index[0]).days / 365.25
    cg = nav.iloc[-1] ** (1 / yrs) - 1
    vv = x.std() * A
    return {"cagr": round(float(cg) * 100, 2), "vol": round(float(vv), 2), "mdd": round(float((nav / nav.cummax() - 1).min() * 100), 1),
            "sh": round(float(cg) * 100 / float(vv), 2) if vv > 0 else 0}


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {}
    for k in ["SPY", "QQQ", "GLD"]:
        O[k] = px[k] if k in TREND_U else px.pop(k)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    O["TLT"] = px["TLT"]
    tpx = {k: px[k] for k in TREND_U if k in px}
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(tpx[s].index) for s in tpx])))
    cdl = cash_daily(irx, allidx)
    common = str(max(tpx[s].index[0] for s in tpx).date())
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    DM, DQ = drifts(C)
    msig, mfs = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * A
    SC = {"port": (15.0 / rv).clip(upper=1.0, lower=0.30).fillna(1.0), "conc": (22.0 / rv).clip(upper=1.0, lower=0.70).fillna(1.0)}
    GR = {"port": (G_PORT, RD_PORT), "conc": (G_CONC, RD_CONC)}

    ON = pd.DataFrame(0.0, index=C.index, columns=KEYS); ID = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ON[k] = on; ID[k] = (1 + cc) / (1 + on) - 1

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "trend_from": common}
    sleeve, res = {}, {}
    z = pd.Series(0.0, index=C.index)

    def sh(a, k):
        return a.shift(-k).fillna(0.0)

    def variant(nm, mi, mo, nin=100, nout=50, cost=0.005, slip=0.0, ports=(("port", 1), ("port", 0), ("conc", 1))):
        s, tv, ip = trend_exec(tpx, cdl, nin, nout, mi, mo, cost, slip, start=common)
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        sleeve[nm] = {"is": sstat(s, START, IS_END), "oos": sstat(s, OOS_START, END),
                      "turn": round(float(tv.sum()) / yrs * 100), "inpos": round(float(ip.mean()) * 100, 1)}
        print("칸", nm, sleeve[nm], flush=True)
        C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
        ID["TRD"] = C["TRD"].pct_change().fillna(0.0)
        for base, sft in ports:
            G, Rd = GR[base]
            nav, td = run(C, ON, ID, reg, idx, SC[base], sh(msig, sft), sh(mfs, sft), G, Rd, "c1", 0.001)
            a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
            key = f"{base}_s{sft}_{nm}"
            res[key] = {"is": a, "oos": b}
            print(key, a["cagr"], b["cagr"], b["mdd"], a.get("vol"), b.get("vol"), flush=True)

    for nm, mi, mo in (("c1", "c1", "c1"), ("c0", "c0", "c0"), ("o1", "o1", "o1"), ("stop", "stop", "stop"),
                       ("stopin", "stop", "c1"), ("stopout", "c1", "stop")):
        variant(nm, mi, mo)
    variant("stop_slip10", "stop", "stop", slip=0.001)
    variant("stop_slip25", "stop", "stop", slip=0.0025)
    variant("c1_cost10", "c1", "c1", cost=0.010, ports=(("port", 1),))
    variant("stop_cost10", "stop", "stop", cost=0.010, ports=(("port", 1),))
    for nin, nout in ((80, 50), (120, 50), (100, 40), (100, 60)):
        variant(f"c1_{nin}_{nout}", "c1", "c1", nin, nout, ports=(("port", 1),))
        variant(f"stop_{nin}_{nout}", "stop", "stop", nin, nout, ports=(("port", 1),))
    # 칸 평균 크기(💼 예약 종가판에서 TRD 몫) — 크기 산수 확인용
    out["sleeve"] = sleeve; out["res"] = res
    out["note"] = ("🧭 추세 칸 체결 시점만 바꿈(문턱·가중·9종 그대로) · stop = 어제까지 자료로 아는 문턱에 미리 건 주문, 장중 고가·저가로 체결 판정 · "
                   "slip = 스톱 체결가 불리하게 0.1/0.25% · 💼 s1 = 예약 종가판(Q11/6-3) · s0 = 지금 실제 · ETF 만, 생존 편향 없음 · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
