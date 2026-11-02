"""📈 11/2 14시 — ⚡ 킥 돌파 칸을 「그날 구성 종목」으로 다시: 개별주 무리(실적 갭·컵)를 빼고 ETF 돌파만 두면?
  12시 k1102_pit/pitgap: 개별주 신호(☕·📊)를 그날 S&P500 구성 종목으로 재니 뒤(2017~) 건당 S&P 초과가 −0.65·−0.78% 로 나빠짐.
  그런데 지금까지 킥 칸 대용 실험(10/27 sigmix·10/28 order)은 E(ETF 52주 돌파) + P(실적 갭)·C(컵) 를 「오늘 대형주 102개」로 셈 → 부풀었을 수 있음.
  질문: 칸 단위(포트 전체)에서 ① 오늘 102개(지금까지 방식) ② 그날 S&P500 구성 종목(PIT · 역대 종목 중 yfinance 에 남은 것) 로 E+P+C 를 돌리면
        얼마나 달라지나 ③ 개별주를 빼고 E 만 두면(실제 kick_params 에서 개별주 무리 끄기) 정직하게 더 나은가.
  틀 = 10/28 k1028_order 그대로: C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 자리 5 · 하루 새 진입 2 · 출구 −5%·+15%·15일 정체 · 빈 자리 BIL · 같은 순위(지금 pri)
  PIT: 신호는 그날 구성 종목일 때만 · 컵 RS 순위도 그날 구성 종목끼리 · 보유 중 편출은 출구 규칙대로(강제 매도 없음)
  앞 2008-07~2016 / 뒤 2017~ · 회전율 × 0.1% · 흔들기 = 실적 갭 4·6% · 컵 손잡이 3·5일 (PIT E+P+C 와 같은 손잡이로)
  생존 편향: 상장폐지 종목은 yfinance 에 없어 PIT 도 아직 위로 치우침 → 개별주 쪽 숫자는 「이것보다 나쁨」 하한이 아니라 상한
→ market/lab/k1102_kickpit.json
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
import yfinance as yf
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, run_mix, seg
from k1012_exits import prep, tstat
from k1013_trend import base_vol
from k1014_volw import kick_vw
from k1019_cupbrk import STK, cup_state
from k1024_pead import kick_x, dq_of
import accum_bt as AB
import k1102_pit as PIT

OUT = Path("market/lab/k1102_kickpit.json")
SIZE = 0.19
DEF = {"pg": 0.05, "pv": 2.0, "ch": 4, "crs": 0.5}


def pack_from(Cidx, S, O, H, V, M=None):
    """개별주 묶음: 가격·신호 재료. M = 그날 구성 종목 표시(nd×ns bool) 또는 None"""
    U = list(S.columns); ns = len(U)
    Sf = S.ffill(limit=5)
    season = np.array([8 <= dq_of(d) <= 55 for d in Cidx])
    vavg = V.shift(1).rolling(20, min_periods=15).mean()
    hi60 = S.shift(1).rolling(60, min_periods=50).max()
    gapr = O / S.shift(1) - 1
    Pv = Sf.values
    Hs, PIVs = [], []
    for j in range(ns):
        h, pv = cup_state(Pv[:, j]); Hs.append(h); PIVs.append(pv)
    Hc = np.column_stack(Hs); PIVa = np.column_stack(PIVs)
    Hp = np.vstack([np.full((1, ns), np.nan), Hc[:-1]])
    PIVp = np.vstack([np.full((1, ns), np.nan), PIVa[:-1]])
    mom = Sf / Sf.shift(126)
    if M is not None:
        mom = mom.where(pd.DataFrame(M, index=Cidx, columns=U))
    RS = mom.rank(axis=1, pct=True).values
    return dict(U=U, ns=ns, Sf=Sf, Pv=Pv, season=season, vavg=vavg, hi60=hi60, gapr=gapr, O=O, H=H, V=V, S=S, Hp=Hp, PIVp=PIVp, RS=RS, M=M)


def sigs(pk, k):
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (pk["gapr"] >= k["pg"]) & (pk["O"] > pk["H"].shift(1)) & (pk["V"] >= k["pv"] * pk["vavg"]) & (pk["S"] > pk["hi60"])
        sp = np.nan_to_num(m.values, nan=0).astype(bool) & pk["season"][:, None]
        s = (pk["Hp"] >= k["ch"]) & (pk["Pv"] > pk["PIVp"]) & (pk["Pv"] <= pk["PIVp"] * 1.05) & (pk["RS"] >= k["crs"])
        sc = np.nan_to_num(s, nan=0).astype(bool)
    if pk["M"] is not None:
        sp &= pk["M"]; sc &= pk["M"]
    return sp, sc


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
    spy_row = {"is": seg(spy, spy, START, IS_END), "oos": seg(spy, spy, OOS_START, END)}
    oosm = C.index >= pd.Timestamp(OOS_START)
    log = {}

    # ① 오늘 대형주 102개 (지금까지 방식)
    df = yf.download(STK, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    got = [t for t in STK if t in df.columns.get_level_values(0)]
    S = pd.DataFrame({t: df[t]["Close"] for t in got}).reindex(C.index).dropna(axis=1, how="all")
    U = list(S.columns)
    def c102(f):
        return pd.DataFrame({t: df[t][f] for t in U}).reindex(C.index)
    pk102 = pack_from(C.index, S, c102("Open"), c102("High"), c102("Volume"))
    print("102개", pk102["ns"], round(time.time() - t0), flush=True)

    # ② 그날 S&P500 구성 종목
    snaps = PIT.members()
    iv, adds, today = PIT.intervals(snaps)
    ever = sorted(set(iv) | today)
    AB.START = "2006-01-01"; AB.TIME_BUDGET = 14 * 60
    data = AB.download(ever, log, time.time())
    tk = sorted(t for t, d in data.items() if len(d) >= 320)
    log["n_ever"] = len(ever); log["n_dl"] = len(tk); log["n_today_dl"] = sum(1 for t in tk if t in today)
    print("역대", len(ever), "받음", len(tk), round(time.time() - t0), flush=True)

    def col(f):
        return pd.DataFrame({t: data[t][f] for t in tk}).reindex(C.index)
    Sp, Op, Hp_, Vp = col("close"), col("open"), col("high"), col("volume")
    M = np.zeros((nd, len(tk)), bool)
    dts = C.index.values
    for j, t in enumerate(tk):
        for a, b in iv.get(t, []):
            M[:, j] |= (dts >= np.datetime64(a)) & (dts < np.datetime64(b))
    Mt = np.zeros_like(M); Mt[:, [j for j, t in enumerate(tk) if t in today]] = True   # 오늘 종목 전체 기간
    pkP = pack_from(C.index, Sp, Op, Hp_, Vp, M)
    pkT = dict(pkP); pkT["M"] = Mt
    _m = (pkP["Sf"] / pkP["Sf"].shift(126)).where(pd.DataFrame(Mt, index=C.index, columns=pkP["U"]))
    pkT["RS"] = _m.rank(axis=1, pct=True).values
    print("묶음 준비", round(time.time() - t0), flush=True)

    def go(pk, fams, kw=None, label=""):
        k = dict(DEF, **(kw or {}))
        ns = pk["ns"]
        sp, sc = sigs(pk, k)
        sigS = (sp if "P" in fams else np.zeros_like(sp)) | (sc if "C" in fams else np.zeros_like(sc))
        SIG = np.hstack([BRK if "E" in fams else np.zeros((nd, ne), bool), sigS])
        RELs = (pk["Sf"] / pk["Sf"].shift(63)).sub(C["SPY"] / C["SPY"].shift(63), axis=0).values
        Rs = pk["Sf"].pct_change().fillna(0.0).values
        Pm = np.hstack([Pe, pk["Pv"]]); R = np.hstack([Re, Rs]); REL = np.hstack([RELe, RELs])
        rk, tkk, tr, hd = kick_x(C, idx, Pm, SIG, REL, R, bil)
        nav, td = run_mix(rb, tb, (rk, tkk, None), reg, SIZE, SIZE)
        # 킥 칸 혼자(사고판 거래가 S&P 를 이겼나)
        out = {"label": label, "fams": fams, "kw": kw or {}, "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td),
               "tr_is": tstat(tr, START, IS_END), "tr_oos": tstat(tr, OOS_START, END),
               "sig_oos": {"E": int(BRK[oosm].sum()) if "E" in fams else 0, "P": int(sp[oosm].sum()) if "P" in fams else 0,
                           "C": int(sc[oosm].sum()) if "C" in fams else 0}}
        print(label, out["is"]["cagr"], out["is"]["sharpe"], "|", out["oos"]["cagr"], out["oos"]["mdd"], out["oos"]["sharpe"], out["tr_oos"], round(time.time() - t0), flush=True)
        return out

    rows = {}
    rows["E"] = go(pk102, "E", label="E ETF 돌파만")
    rows["EPC_102"] = go(pk102, "EPC", label="E+P+C 오늘 102개(지금까지)")
    rows["EPC_today"] = go(pkT, "EPC", label="E+P+C 오늘 S&P500 종목 전체기간")
    rows["EPC_pit"] = go(pkP, "EPC", label="E+P+C 그날 구성 종목")
    rows["EP_pit"] = go(pkP, "EP", label="E+P 그날 구성 종목")
    rows["EC_pit"] = go(pkP, "EC", label="E+C 그날 구성 종목")
    rows["PC_pit"] = go(pkP, "PC", label="P+C 만 그날 구성 종목")
    kk = kick_vw(C, idx, pre_etf, None)
    nav, td = run_mix(rb, tb, kk[:2] + (None,), reg, SIZE, SIZE)
    rows["E_vw"] = {"label": "지금 킥 대용(ETF 돌파·변동성 맞춤 자리 — 지난 밤들 기준)", "is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
    print("E_vw", rows["E_vw"]["oos"], flush=True)

    shake = []
    for what, kw in (("실적 갭 4%", {"pg": 0.04}), ("실적 갭 6%", {"pg": 0.06}), ("컵 손잡이 3일", {"ch": 3}), ("컵 손잡이 5일", {"ch": 5}),
                     ("거래 1.6배", {"pv": 1.6}), ("거래 2.4배", {"pv": 2.4})):
        if time.time() - t0 > 33 * 60:
            break
        r = go(pkP, "EPC", kw, label="흔들기 PIT " + what); r["what"] = what; shake.append(r)

    e = rows["E"]; p = rows["EPC_pit"]
    d_is = round(e["is"]["cagr"] - p["is"]["cagr"], 2); d_oos = round(e["oos"]["cagr"] - p["oos"]["cagr"], 2)
    sh_is = round(e["is"]["sharpe"] - p["is"]["sharpe"], 3); sh_oos = round(e["oos"]["sharpe"] - p["oos"]["sharpe"], 3)
    shake_d = [round(e["oos"]["cagr"] - s["oos"]["cagr"], 2) for s in shake]
    shake_sh = [round(e["oos"]["sharpe"] - s["oos"]["sharpe"], 3) for s in shake]
    if d_is >= 1.0 and d_oos >= 1.0 and all(x > 0 for x in shake_d):
        verdict = "✅ E 만 두기 — 앞·뒤 모두 +1%p↑·흔들기 유지"
    elif d_is > 0 and d_oos > 0 and sh_is > 0 and sh_oos > 0 and all(x > 0 for x in shake_sh):
        verdict = "🟡 E 만 두기가 앞·뒤 모두 나음(크기 1%p 미만)"
    elif d_oos > 0 or sh_oos > 0:
        verdict = "➖ 뒤에서만 나음"
    else:
        verdict = "❌ 개별주 무리 빼도 안 나아짐"
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END, "log": log,
           "spy": spy_row, "rows": rows, "shake": [{"what": s["what"], "is": s["is"], "oos": s["oos"], "tr_oos": s["tr_oos"]} for s in shake],
           "E_minus_EPCpit": {"cagr_is": d_is, "cagr_oos": d_oos, "sharpe_is": sh_is, "sharpe_oos": sh_oos, "shake_cagr_oos": shake_d, "shake_sharpe_oos": shake_sh},
           "bias_102_minus_pit": {"cagr_is": round(rows["EPC_102"]["is"]["cagr"] - p["is"]["cagr"], 2), "cagr_oos": round(rows["EPC_102"]["oos"]["cagr"] - p["oos"]["cagr"], 2)},
           "verdict": verdict, "sec": round(time.time() - t0),
           "note": "틀 = k1028_order(C안 뼈대 + 변동성 맞춤 · 킥 칸 19% · 같은 순위) · PIT = fja05680/sp500 날짜별 구성 종목, 상장폐지 종목은 yfinance 에 없어 아직 위로 치우침 · 실제 킥의 다른 신호(lead·고래 등)는 못 넣음 · 매수 추천 아님"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(verdict, out["E_minus_EPCpit"], out["bias_102_minus_pit"], out["sec"])


if __name__ == "__main__":
    main()
