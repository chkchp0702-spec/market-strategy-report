"""📈 11/11 16시 — k1111_krexec: ⏳ Q11/6-3(월말 흐름 하루 먼저 알리고 그날 밤 예약 종가)의 「한국 실전 장벽」 해부
  인사이트 렌즈 0-1 ⑥·① — 장부 vs 실제로 새는 곳: 체결 길(미국 원본 LOC · 국내 상장 ETF 시각) × 비용 × 세금
  기준 = k1106_portexec2 와 같은 틀(💼 port · 🎯 conc · 변동성 맞춤 · 국면 · 🧭 추세 칸 · 다음 날 종가 체결)
  run2 = k1106_exectime3.run 을 「금액 장부」로 다시 쓴 것 → 세금(평균 단가 · 그해 실현이익 순합 × 세율 · 연말 납부)과
         'k' 체결(국내 상장 ETF: 한국 장 마감 15:30 KST ≈ 미국 밤 몫의 θ 지점 체결) 추가 · 세금 0·k 없음이면 run 과 같은 숫자(재현 확인)
  판:
   now      = s0_c1 (지금 앱: 알림 하루 늦음 · 다음 날 종가)
   loc      = s1_c1 (미국 원본 예약 종가 LOC — 하루 먼저 알고 그날 밤 종가) · 비용 0.07·0.1·0.25%
   krA      = s1 · 국내 ETF 를 알림 받은 그날 한국 장(15:30)에 = 미국 다음 날 밤 몫 θ 지점 (예약 종가보다 하루 일찍 들어감)
   krB      = s1 · 국내 ETF 를 다음 날 한국 장에 = 예약 종가 뒤 밤 몫 θ 지점 (조금 늦게 들어감) · θ 0.3·0.5·0.7
   세금     = 미국 원본 일반 계좌 22%(250만원 공제 무시 = 큰 계좌) · 국내 상장 해외 ETF 일반 계좌 15.4%(매도 차익 · 손실 상계 없음은 무시) · 연금 계좌 0(과세 이연)
  🧭 추세 칸 안쪽 매매의 실현이익은 셈하지 않음(세금 과소) · 국내 ETF 괴리율·환율·추적 오차는 넣지 않음(밤 몫 θ 근사만)
→ market/lab/k1111_krexec.json
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
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1111_krexec.json")
A = math.sqrt(252) * 100


def run2(C, ON, ID, reg, idx, sc, sig, fs, G, Rd, mode, cost, band=0.05, tax=0.0, theta=0.5):
    regv = reg.reindex(C.index).fillna(False)
    pos_i = {d: i for i, d in enumerate(C.index)}

    def tg(i, s_now, f):
        b = G if bool(regv.iloc[i]) else Rd
        e = (b["SPY"] + b["QQQ"]) * float(sc.iloc[i])
        gl = b["GLD"]; trd = 1 - e - gl; bnd = 0.0
        if s_now > 0 and f > 0:
            bnd = e * f; e -= bnd
        elif s_now < 0 and f > 0:
            e += (gl + trd) * f; gl *= (1 - f); trd *= (1 - f)
        return {"SPY": e / 2, "QQQ": e / 2, "GLD": gl, "TRD": trd, "BND": bnd}

    V = B = None; last = None; lsig = 0.0; pend = []
    st = {"g": 0.0, "taxpaid": 0.0, "realized": 0.0}
    navs, turns = [], []

    def trade(t, frac=1.0):
        N = sum(V.values()); tv = 0.0
        for k in V:
            dlt = frac * (t[k] * N - V[k])
            if dlt < 0 and V[k] > 0:
                q = -dlt / V[k]
                gain = -dlt - B[k] * q
                st["g"] += gain; st["realized"] += gain
                B[k] *= (1 - q)
            elif dlt > 0:
                B[k] += dlt
            V[k] += dlt; tv += abs(dlt)
        tv = tv / 2 / N
        c = tv * cost * N
        for k in V:   # 비용은 비례로 뺌 · 단가는 그대로(= 비용이 사실상 필요경비로 공제되는 근사)
            V[k] -= c * (V[k] / N)
        return tv

    def grow(R, d, p=1.0):
        for k in V:
            V[k] *= (1 + R.at[d, k]) ** p if p != 1.0 else (1 + R.at[d, k])

    prevN = 1.0
    for n_, d in enumerate(idx):
        i = pos_i[d]
        if V is None:
            w0 = tg(i - 1, 0.0, 0.0); V = dict(w0); B = dict(w0); last = dict(w0)
        tvd = 0.0
        ks = [p for p in pend if p[0] == i and p[1] == "k"]
        if ks:
            grow(ON, d, theta)
            for p in ks:
                tvd += trade(p[2], p[3])
            grow(ON, d, 1 - theta)
        else:
            grow(ON, d)
        for p in [p for p in pend if p[0] == i and p[1] == "o"]:
            tvd += trade(p[2], p[3])
        grow(ID, d)
        for p in [p for p in pend if p[0] == i and p[1] == "c"]:
            tvd += trade(p[2], p[3])
        pend = [p for p in pend if p[0] != i]
        j = i + 1
        snext = float(sig.iloc[j]) if j < len(sig) else 0.0
        fnext = float(fs.iloc[j]) if j < len(fs) else 0.0
        t = tg(i, snext, fnext)
        newm = j < len(C.index) and C.index[j].month != d.month
        if newm or snext != lsig or regv.iloc[i] != regv.iloc[i - 1] or max(abs(t[k] - last[k]) for k in t) > band:
            last = dict(t)
            if pend:
                pend = [(p[0], p[1], t, p[3]) for p in pend]
            elif mode == "c0":
                tvd += trade(t)
            elif mode == "o1":
                pend.append((i + 1, "o", t, 1.0))
            elif mode == "c1":
                pend.append((i + 1, "c", t, 1.0))
            elif mode == "kA":
                pend.append((i + 1, "k", t, 1.0))
            elif mode == "kB":
                pend.append((i + 2, "k", t, 1.0))
        lsig = snext
        # 연말 세금 (그해 마지막 거래일)
        ny = (n_ + 1 < len(idx)) and idx[n_ + 1].year != d.year
        if tax > 0 and (ny or n_ + 1 == len(idx)):
            tx = tax * max(0.0, st["g"]); N = sum(V.values())
            for k in V:
                V[k] -= tx * V[k] / N; B[k] -= tx * B[k] / N if N > 0 else 0
            st["taxpaid"] += tx; st["g"] = 0.0
        elif ny:
            st["g"] = 0.0
        navs.append(sum(V.values())); turns.append(tvd)
    return pd.Series(navs, index=idx), pd.Series(turns, index=idx), st


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {}
    for k in ["SPY", "QQQ", "GLD"]:
        O[k] = px.pop(k)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    O["TLT"] = px["TLT"]
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
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * A
    SC = {"port": (15.0 / rv).clip(upper=1.0, lower=0.30).fillna(1.0), "conc": (22.0 / rv).clip(upper=1.0, lower=0.70).fillna(1.0)}
    GR = {"port": (G_PORT, RD_PORT), "conc": (G_CONC, RD_CONC)}
    ON = pd.DataFrame(0.0, index=C.index, columns=KEYS); ID = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ON[k] = on; ID[k] = (1 + cc) / (1 + on) - 1
    ID["TRD"] = C["TRD"].pct_change().fillna(0.0)

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    z = pd.Series(0.0, index=C.index)

    def sh(a, k):
        return a.shift(-k).fillna(0.0)
    res = {}
    # 재현 확인: run2(세금 0) vs run
    chk = {}
    for base in ("port", "conc"):
        G, Rd = GR[base]
        n1, _ = run(C, ON, ID, reg, idx, SC[base], sh(msig, 1), sh(mfs, 1), G, Rd, "c1", 0.001)
        n2, _, _ = run2(C, ON, ID, reg, idx, SC[base], sh(msig, 1), sh(mfs, 1), G, Rd, "c1", 0.001)
        chk[base] = round(float((n2 / n1 - 1).abs().max()) * 100, 6)
    out["repro_maxdiff_pct"] = chk
    print("재현", chk, flush=True)

    def go(nm, base, flow, mode, cost=0.001, tax=0.0, theta=0.5):
        G, Rd = GR[base]
        a_, f_ = {"none": (z, z), "s0": (msig, mfs), "s1": (sh(msig, 1), sh(mfs, 1))}[flow]
        nav, td, st = run2(C, ON, ID, reg, idx, SC[base], a_, f_, G, Rd, mode, cost, tax=tax, theta=theta)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        res[nm] = {"is": a, "oos": b, "taxpaid_x_nav0": round(st["taxpaid"], 3), "realized_x_nav0": round(st["realized"], 3)}
        print(nm, a["cagr"], b["cagr"], b["mdd"], b.get("turn"), round(st["taxpaid"], 3), flush=True)

    for base in ("port", "conc"):
        for tax in (0.0, 0.154, 0.22):
            tg_ = f"_t{int(round(tax * 1000))}"
            go(f"{base}_noflow{tg_}", base, "none", "c1", tax=tax)
            go(f"{base}_now{tg_}", base, "s0", "c1", tax=tax)
            go(f"{base}_loc{tg_}", base, "s1", "c1", tax=tax)
            go(f"{base}_krB{tg_}", base, "s1", "kB", tax=tax)
            go(f"{base}_krA{tg_}", base, "s1", "kA", tax=tax)
        for c in (0.0007, 0.0025):
            go(f"{base}_noflow_c{int(c*1e4)}", base, "none", "c1", cost=c)
            go(f"{base}_loc_c{int(c*1e4)}", base, "s1", "c1", cost=c)
            go(f"{base}_krB_c{int(c*1e4)}", base, "s1", "kB", cost=c)
        for th in (0.3, 0.7):
            go(f"{base}_krB_th{th}", base, "s1", "kB", theta=th)
            go(f"{base}_krA_th{th}", base, "s1", "kA", theta=th)
        go(f"{base}_noflow_kB", base, "none", "kB")
    out["res"] = res
    out["note"] = ("now=지금 앱(하루 늦음) · loc=미국 원본 예약 종가 · krA/krB=국내 상장 ETF 한국 장 체결 근사(밤 몫 θ 지점, 괴리율·환율 없음) · "
                   "t220=미국 원본 일반 계좌 22% · t154=국내 상장 해외 ETF 일반 계좌 15.4% · t0=연금 계좌(과세 이연) · 공제 250만원 무시 · 추세 칸 안쪽 실현이익 미반영 · 레버리지 없음 · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
