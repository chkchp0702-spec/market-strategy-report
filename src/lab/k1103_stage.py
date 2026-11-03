"""📈 11/3 12시 — 「하락장 앞부분은 방어 칸, 뒷부분은 추세 칸」 🎯 집중의 🔴 칸 안 갈아 끼우기 (2단계 방어)
  바깥 재료: Harvey·Hoyle·Rattray 외 「Best Defensive Strategies」(FAJ 2026, 220년 자료) —
  「방어적 절대수익(DAR, Cavaglia 2022)과 추세 추종은 하락의 *서로 다른 단계*를 막는다(추세는 늦게 켜짐)」 ·
  Fidelity 「추세 위기 알파는 베타 타이밍인가 시장 고르기인가」(2026) · Man Group 「추세의 주식·채권 위기 알파」.
  우리 🎯 는 🔴(200일선 아래)일 때 50% 와 변동성으로 덜어낸 몫을 🧭 자산 추세 9종(100일 고가 돌파)에 두는데,
  10/28 기록대로 이 칸은 하락 *초입*(2020-03 −2.5%·2025-04 −5.5%)엔 못 막음 → 🔴 처음 N일은 방어 칸(필수소비·유틸·헬스 / 중기 국채),
  그 뒤엔 추세 칸으로 넘기는지 시험. 레버리지·공매도 없음(DAR 의 롱 쪽만 근사).
  기준 = 지금 🎯 규칙(k1103_vrp base 와 같은 틀) · 하루 늦은 체결 · 비용 0.1% · ETF·지수만 → 생존 편향 없음 · 매수 추천 아님
→ market/lab/k1103_stage.json
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
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, core_run, G_CONC, RD_CONC

OUT = Path("market/lab/k1103_stage.json")
CRISES = {"2008-09~09-03": ("2008-09-01", "2009-03-09"), "2011-08": ("2011-07-22", "2011-10-03"),
          "2015-08": ("2015-08-10", "2016-02-11"), "2018-Q4": ("2018-10-01", "2018-12-24"),
          "2020-03": ("2020-02-19", "2020-03-23"), "2022": ("2022-01-03", "2022-10-12"),
          "2025-04": ("2025-02-19", "2025-04-08")}


def main():
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
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    tp = {k: px[k] for k in TREND_U if k in px}
    trd_cache = {}

    def trd(nin, nout):
        if (nin, nout) not in trd_cache:
            s, _, _ = trend_run(tp, cdl, nin, nout, "risk", start=str(common.date()))
            trd_cache[(nin, nout)] = s.reindex(C.index).fillna(0.0)
        return trd_cache[(nin, nout)]

    DM, DQ = drifts(C)
    sigM, fsM = make(C, DM, DQ)
    R = C.pct_change().fillna(0.0)
    def3 = R[["XLP", "XLU", "XLV"]].mean(axis=1)
    ief = R["IEF"]
    # 🔴 나이(연속 며칠째) — 그날 종가 판정 → 다음 날 칸에 반영
    red = ~reg
    grp = (red != red.shift()).cumsum()
    age = red.groupby(grp).cumsum().where(red, 0)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END,
           "red_pct": round(float(red.reindex(idx).mean()) * 100, 1)}

    def sleeve(kind, N=60, lb=(100, 50)):
        T = trd(*lb)
        if kind == "trd":
            return T
        if kind == "fast":
            return trd(50, 25)
        if kind == "def3":
            return def3
        if kind == "ief":
            return ief
        if kind == "mix_def":
            return 0.5 * T + 0.5 * def3
        if kind == "mix_ief":
            return 0.5 * T + 0.5 * ief
        early = (age.shift(1).fillna(0) > 0) & (age.shift(1).fillna(0) <= N)
        alt = {"st_def": def3, "st_ief": ief, "st_fast": trd(50, 25), "st_di": 0.5 * def3 + 0.5 * ief}[kind]
        s = alt.where(early, T)
        sw = early.astype(int).diff().abs().fillna(0)
        return s - sw * 0.001  # 칸 갈아 끼우는 날 비용(넉넉히)

    def go(kind="trd", N=60, lb=(100, 50), tgt=22.0, floor=0.70):
        Cx = C.copy()
        Cx["TRD"] = (1 + sleeve(kind, N, lb)).cumprod()
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        nav, td = core_run(Cx, reg, idx, sc, sigM, fsM, G_CONC, RD_CONC)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        o["yr"] = {}
        for y in range(2008, 2027):
            n = nav[nav.index.year == y]
            if len(n) > 5:
                prev = nav[nav.index < n.index[0]]
                b0 = prev.iloc[-1] if len(prev) else n.iloc[0]
                o["yr"][y] = round(float(n.iloc[-1] / b0 - 1) * 100, 2)
        o["crisis"] = {}
        for k, (a, b) in CRISES.items():
            n = nav[(nav.index >= a) & (nav.index <= b)]
            o["crisis"][k] = round(float(n.iloc[-1] / n.iloc[0] - 1) * 100, 2) if len(n) > 2 else None
        return o

    def dlt(a, b):
        d = {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}
        d["yr"] = {y: round(b["yr"][y] - a["yr"][y], 2) for y in b["yr"]}
        d["crisis"] = {k: (round(b["crisis"][k] - a["crisis"][k], 2) if a["crisis"][k] is not None else None) for k in b["crisis"]}
        return d

    # 칸 하나만 따로: 🔴 첫 N일 동안 각 칸의 평균 하루 수익(연율) — 앞/뒤
    probe = {}
    for N in (20, 40, 60, 120):
        e = (age > 0) & (age <= N)
        l = age > N
        row = {}
        for nm, s in (("trd", trd(100, 50)), ("fast", trd(50, 25)), ("def3", def3), ("ief", ief), ("spy", R["SPY"])):
            for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
                m = (s.index >= a) & (s.index <= b)
                row[f"{nm}_{p}_early"] = round(float(s[m & e.shift(1).fillna(False).to_numpy()].mean()) * 252 * 100, 1)
                row[f"{nm}_{p}_late"] = round(float(s[m & l.shift(1).fillna(False).to_numpy()].mean()) * 252 * 100, 1)
        probe[N] = row
    out["probe_ann_ret"] = probe
    print("PROBE", probe, flush=True)

    B = go("trd")
    out["base"] = B
    print("BASE", B["is"], B["oos"], flush=True)
    grid = {}
    for kind in ("fast", "def3", "ief", "mix_def", "mix_ief"):
        r = go(kind); grid[kind] = {"is": r["is"], "oos": r["oos"], "d": dlt(B, r)}
        print(kind, grid[kind]["d"]["is"], grid[kind]["d"]["oos"], flush=True)
    for kind in ("st_def", "st_ief", "st_fast", "st_di"):
        for N in (20, 40, 60, 90, 120):
            k = f"{kind}_N{N}"
            r = go(kind, N=N); grid[k] = {"is": r["is"], "oos": r["oos"], "d": dlt(B, r)}
            print(k, grid[k]["d"]["is"], grid[k]["d"]["oos"], flush=True)
    out["grid"] = {k: {"is": v["is"], "oos": v["oos"], "d": {p: v["d"][p] for p in ("is", "oos")}} for k, v in grid.items()}
    pick = max(grid, key=lambda k: grid[k]["d"]["is"]["sharpe"] + grid[k]["d"]["is"]["cagr"] / 10)
    out["is_pick"] = pick
    kind = pick.split("_N")[0]; N = int(pick.split("_N")[1]) if "_N" in pick else 60
    print("PICK", pick, grid[pick]["d"]["is"], grid[pick]["d"]["oos"], flush=True)
    P = go(kind, N=N)
    out["pick_detail"] = P
    out["pick_vs_base"] = dlt(B, P)
    # 같은 위험: 고른 판의 목표 변동성을 낮춰/높여 앞 변동성을 기준과 맞춤
    best = None
    for t in np.arange(16.0, 28.01, 0.5):
        r = go(kind, N=N, tgt=float(t))
        gap = abs(r["is"]["vol"] - B["is"]["vol"])
        if best is None or gap < best[0]:
            best = (gap, float(t), r)
    out["same_risk"] = {"tgt": best[1], "d": {p: dlt(B, best[2])[p] for p in ("is", "oos")}}
    print("SAMERISK", out["same_risk"], flush=True)
    # ±20% 흔들기
    sh = {}
    var = {"N-20": dict(N=max(1, round(N * 0.8))), "N+20": dict(N=round(N * 1.2)),
           "lb120_60": dict(lb=(120, 60)), "lb80_40": dict(lb=(80, 40)),
           "tgt18": dict(tgt=18.0), "tgt26": dict(tgt=26.0), "floor56": dict(floor=0.56), "floor84": dict(floor=0.84)}
    for nm, kw in var.items():
        bkw = {k: v for k, v in kw.items() if k in ("lb", "tgt", "floor")}
        b0 = go("trd", **bkw)
        r = go(kind, **{"N": N, **kw})
        d = dlt(b0, r)
        sh[nm] = {p: d[p] for p in ("is", "oos")}
        print("SHAKE", nm, sh[nm], flush=True)
    out["shake"] = sh
    out["note"] = ("기준 = 🎯 지금 규칙(200일선 판정 A · 🔴 50% · 목표 22% · 아래 한도 70% · 덜어낸 몫 🧭 추세 9종 100/50 · 월말 흐름) · "
                   "바꾼 것 = TRD 칸 안에 담는 것만 · st_* = 🔴 들어간 뒤 N일(전날 종가 기준)은 대체 칸(def3=XLP·XLU·XLV 같은 비중, ief=중기 국채, "
                   "fast=추세 50/25, di=def3 반 + ief 반), 그 뒤·🟢 때는 추세 칸 · 갈아 끼우는 날 비용 0.1% · 레버리지·공매도 없음 · ETF 만(생존 편향 없음) · 매수 추천 아님")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
