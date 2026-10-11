"""💼 기본 포트 뼈대 검증 (10/11 사용자: "현금 26%·금 11%도 연구해서 수익률 개선방안을 만들어")

  기본 포트(리포트 배분표)의 「뼈대」 — 현금·금을 얼마나, 주식 칸을 무엇으로 — 를 상승장 판정에 따라 바꾸면 어땠나.
  · 주식 칸 세 가지
      sect = 지금 배분표의 섹터 칸을 긴 역사의 ETF로 바꾼 것 (전력·인프라 XLU+XLI · 에너지 XLE · 금융 XLF · 반도체·광통신 SOXX · AI 소프트웨어 IGV, 지금 비중 비율 그대로)
      core = S&P500 50% + 나스닥100 50%
      mix  = core 절반 + sect 절반
  · 현금·금: 🟢 상승장일 때 / 🔴 아닐 때 따로
  · 판정 A(S&P 200일선 위·3일 확인) · 다음 날 체결 · 매주 비중 맞춤 · 회전율 × 0.1%
  · 2008-07~2016 에서 고르고 2017~ 에서 시험 (conc_bt.py 와 같은 틀)
  ⚠ sect 칸 구성은 오늘 고른 섹터라 사후 선택이 섞여 있음 — 칸 구성보다 「현금·금을 국면에 따라 바꾸는 효과」를 보는 실험
→ market/base_bt.json
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.conc_bt import stats, regimes, sim_exp, START, IS_END, OOS_START, SECT, KST   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "base_bt.json"
# 지금(10/10) 배분표의 주식 칸 63% → 긴 역사 ETF
SECT_W = {"XLU": 10, "XLI": 10, "XLE": 13, "XLF": 8, "SOXX": 16, "IGV": 6}
CORE_W = {"SPY": 50, "QQQ": 50}
ON = [(26, 11), (15, 11), (15, 5), (10, 5), (5, 5), (5, 0), (0, 5), (0, 0)]       # 🟢 (현금, 금)
OFF = [(26, 11), (40, 10), (50, 0), (35, 20), (50, 15)]                           # 🔴 (현금, 금)


def eq(kind):
    if kind == "core":
        w = dict(CORE_W)
    elif kind == "sect":
        w = dict(SECT_W)
    else:
        w = {k: v / 2 for k, v in CORE_W.items()}
        for k, v in SECT_W.items():
            w[k] = w.get(k, 0) + v / 2
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def build(kind, cash, gold):
    e = eq(kind)
    stock = 1 - (cash + gold) / 100
    w = {k: v * stock for k, v in e.items()}
    if cash:
        w["BIL"] = w.get("BIL", 0) + cash / 100
    if gold:
        w["GLD"] = w.get("GLD", 0) + gold / 100
    return w


def main() -> int:
    import pandas as pd
    import yfinance as yf
    tick = sorted(set(list(SECT_W) + ["SPY", "QQQ", "BIL", "GLD", "^GSPC"] + SECT))
    df = yf.download(tick, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick if t in df.columns.get_level_values(0)}).dropna(how="all").ffill(limit=5)
    C = C[C.index >= "2007-01-01"]
    spy = C["SPY"]
    R = regimes(C["^GSPC"].ffill(), C[SECT])
    end = C.index[-1]
    rows = []
    for kind in ("sect", "mix", "core"):
        for (con, gon), (cof, gof) in itertools.product(ON, OFF):
            if (con, gon) == (26, 11) and (cof, gof) != (26, 11):
                continue      # 「지금처럼 늘」은 한 줄만
            on, off = build(kind, con, gon), build(kind, cof, gof)
            reg = R["A"] if (con, gon) != (cof, gof) else pd.Series(True, index=C.index)
            per = {}
            for nm, a, b in (("is", START, IS_END), ("oos", OOS_START, end), ("full", START, end)):
                nav, t = sim_exp(C, reg, on, off, a, b)
                st = stats(nav, spy)
                per[nm] = {x: st.get(x) for x in ("cagr", "ex", "mdd", "sharpe", "win12", "beat_years", "years")}
                per[nm]["turn"] = t
                if nm == "full":
                    per["yr"] = st.get("yr")
            rows.append({"eq": kind, "on": [con, gon], "off": [cof, gof], **per})
    cur = next(r for r in rows if r["eq"] == "sect" and r["on"] == [26, 11] and r["off"] == [26, 11])
    # 두 기간 모두 지금보다 나은 것 중 뒤 기간 초과수익 순 (낙폭은 S&P 보다 크지 않게)
    spy_o, spy_i = stats(spy[OOS_START:]), stats(spy[START:IS_END])
    good = [r for r in rows if r["is"]["ex"] is not None and r["oos"]["ex"] is not None
            and r["is"]["ex"] > cur["is"]["ex"] and r["oos"]["ex"] > cur["oos"]["ex"]
            and r["oos"]["mdd"] >= spy_o["mdd"] and r["is"]["mdd"] >= spy_i["mdd"]]
    top = sorted(good, key=lambda r: -(r["oos"]["ex"] + r["is"]["ex"]))[:12]
    # 칸 구성별·현금별 요약 (뒤 기간)
    by_eq = {k: {"best_oos_ex": max((r["oos"]["ex"] for r in rows if r["eq"] == k), default=None),
                 "same_as_now": next((r["oos"] for r in rows if r["eq"] == k and r["on"] == [26, 11] and r["off"] == [26, 11]), None)} for k in ("sect", "mix", "core")}
    by_on = {f"{c}/{g}": {k: next((r["oos"]["ex"] for r in rows if r["eq"] == k and r["on"] == [c, g] and r["off"] == [40, 10]), None) for k in ("sect", "mix", "core")} for c, g in ON}
    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "to": str(end.date()), "is": [START, IS_END], "oos": [OOS_START, str(end.date())],
           "sect_w": SECT_W, "on_grid": ON, "off_grid": OFF, "n": len(rows), "current": cur, "top": top, "by_eq": by_eq, "by_on_off40_10": by_on,
           "spy": {"is": spy_i, "oos": spy_o, "full": stats(spy[START:])}, "rows": rows,
           "note": "판정 A · 다음 날 체결 · 매주 비중 맞춤 · 회전율×0.1% · sect 칸은 오늘 고른 섹터(사후 선택 섞임)"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    pr = lambda r: f"{r['eq']:4} 🟢{r['on']} 🔴{r['off']} | OOS cagr {r['oos']['cagr']} ex {r['oos']['ex']} mdd {r['oos']['mdd']} by {r['oos']['beat_years']}/{r['oos']['years']} | IS ex {r['is']['ex']} mdd {r['is']['mdd']} | turn {r['oos']['turn']}"
    print("SPY", spy_i, spy_o)
    print("지금", pr(cur))
    for r in top:
        print("TOP", pr(r))
    print("by_eq", json.dumps(by_eq, ensure_ascii=False))
    print("by_on", json.dumps(by_on, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
