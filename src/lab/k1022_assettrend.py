"""🌙 10/22 밤 연구 — 💼 기본 뼈대 칸마다 추세 거르기 (Faber 10개월선 식)
  질문: 지금 운용 규칙 위에 얹어, 칸(S&P500 SPY · 나스닥100 QQQ · 금 GLD)마다 「종가 < N일선」이면 그 칸 비중을 현금(BIL)으로 돌리면 나은가
        → 노출을 줄이기만 함 (현금을 주식으로 옮기지 않음)
  기본(「지금」) = k1022_trend3 와 같은 💼 운용 규칙
     판정 S&P500(^GSPC) 200일선 위 · 3일 확인 → 🟢 47.5·47.5·금 5·현금 0 / 🔴 31.5·31.5·금 11·현금 26
     + 🦴 변동성 맞춤 방어형(20일 · 목표 15% · 바닥 30% · 5%p 밴드, 주식 칸만) · 금 조건부 없음(운용에 없음)
  손잡이: N일선 {150, 200, 210, 250} × 확인 {매일 + 3일 확인, 달 마지막 거래일만} × 적용 칸 {금만, 주식만(SPY·QQQ), 전부} = 24조합
  판단은 그날 종가까지 → 다음 날 종가 체결 · 매주 + 목표 비중이 바뀐 날 비중 맞춤 · 회전율 × 0.1% 비용
  2008-07~2016 샤프로 고르고 2017~ 에서 시험 · 흔들기 = N ×0.8 / ×1.2 (확인 방식·적용 칸은 고정)
  판정: ✅ = 시험 구간 샤프 > 지금 · 연수익 ≥ 지금 −0.3%p · 낙폭이 지금보다 2%p 넘게 나쁘지 않음 · 흔들기 둘 다 샤프 > 지금
→ market/lab/k1022_assettrend.json
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import stats, regimes, START, IS_END, OOS_START, KST
from k1022_trend3 import load, sticky, vol_scale, base_weights, evaluate, switches, rank_corr, judge, strip, COLS

OUT = Path("market/lab/k1022_assettrend.json")
NS = [150, 200, 210, 250]
CHECKS = ["daily3", "month"]
APPLY = {"gold": ["GLD"], "eq": ["SPY", "QQQ"], "all": ["SPY", "QQQ", "GLD"]}
CHECK_LAB = {"daily3": "매일 + 3일 확인", "month": "달 마지막 거래일만"}
APPLY_LAB = {"gold": "금만", "eq": "주식만(S&P·나스닥)", "all": "전부"}


def trend_flags(C: pd.DataFrame, n: int, check: str) -> pd.DataFrame:
    """칸마다 True = 추세 위(담음) / False = 현금으로. 이평 계산 전(자료 부족)은 True."""
    out = {}
    me = pd.Series(C.index.month, index=C.index)
    is_me = np.array(me != me.shift(-1), dtype=bool)   # 달 마지막 거래일
    is_me[-1] = False                            # 자료 맨 끝날은 달 끝인지 아직 모름 → 판단 안 함
    for t in ("SPY", "QQQ", "GLD"):
        p = C[t]
        ma = p.rolling(n, min_periods=n).mean()
        raw = ((p > ma) | ma.isna()).astype(bool)
        if check == "daily3":
            f = sticky(raw, 3)
        else:
            f = raw.astype(float).where(is_me).ffill().fillna(1.0) > 0.5
        out[t] = f
    return pd.DataFrame(out)


def overlay(W: np.ndarray, flags: pd.DataFrame, assets) -> np.ndarray:
    """기본 목표 비중 W 에서 추세 아래인 칸 비중을 BIL 로 (줄이기만)"""
    W = W.copy()
    bi = COLS.index("BIL")
    for t in assets:
        j = COLS.index(t)
        off = ~flags[t].values.astype(bool)
        W[off, bi] += W[off, j]
        W[off, j] = 0.0
    return W


def main():
    C = load()
    spy = C["SPY"]
    end = str(C.index[-1].date())
    sc = vol_scale(C)
    reg = regimes(C["^GSPC"], C[["SPY"]])["A"].reindex(C.index).fillna(False).astype(float)
    W0 = base_weights(reg.values, sc)
    spy_row = {"is": stats(spy[START:IS_END]), "oos": stats(spy[OOS_START:end])}

    cur = evaluate(C, W0, switches(reg), spy, end)
    cur["cfg"] = {"rule": "지금 💼 규칙 (칸 거르기 없음)"}
    FL = {}

    def run(n, check, ap):
        key = (n, check)
        if key not in FL:
            FL[key] = trend_flags(C, n, check)
        fl = FL[key]
        assets = APPLY[ap]
        W = overlay(W0, fl, assets)
        sw = switches(pd.concat([reg.rename("reg"), fl[assets].astype(float)], axis=1))
        o = evaluate(C, W, sw, spy, end)
        o["cfg"] = {"n": n, "check": check, "apply": ap}
        o["off_pct_oos"] = {t: round(float((~fl[t][OOS_START:]).mean()) * 100) for t in assets}
        o["risk_avg_oos"] = round(float(1 - W[C.index >= pd.Timestamp(OOS_START), COLS.index("BIL")].mean()) * 100, 1)
        return o

    grid = [run(n, ck, ap) for n, ck, ap in itertools.product(NS, CHECKS, APPLY)]
    chosen = max(grid, key=lambda g: (g["is"]["sharpe"] or -9, g["is"]["cagr"]))
    c = chosen["cfg"]
    robust = []
    for mult in (0.8, 1.2):
        n2 = int(round(c["n"] * mult))
        g = run(n2, c["check"], c["apply"])
        g["what"] = f"N ×{mult} ({n2}일선)"
        robust.append(g)
    verdict, why, chk = judge(chosen, cur, robust)
    rc = rank_corr(grid)
    beat = sum(1 for g in grid if (g["oos"]["sharpe"] or -9) > (cur["oos"]["sharpe"] or -9))
    # 칸별 요약 (적용 칸마다 시험 구간 샤프 가운데·지금 넘은 수)
    by_apply = {}
    for ap in APPLY:
        v = [g["oos"]["sharpe"] for g in grid if g["cfg"]["apply"] == ap]
        by_apply[ap] = {"med_sh": round(float(np.median(v)), 2), "beat": sum(1 for x in v if x > cur["oos"]["sharpe"]), "n": len(v)}

    fl_now = trend_flags(C, c["n"], c["check"]).iloc[-1]
    now = {"date": end, "reg_now": bool(reg.iloc[-1]), "vol_scale": round(float(sc[-1]), 2),
           "gap_pct": {t: round(float(C[t].iloc[-1] / C[t].rolling(c["n"]).mean().iloc[-1] - 1) * 100, 1) for t in ("SPY", "QQQ", "GLD")},
           "chosen_on": {t: bool(fl_now[t]) for t in APPLY[c["apply"]]}}

    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
           "question": "💼 기본 뼈대 위에 칸마다(S&P·나스닥·금) 「종가 < N일선이면 그 칸을 현금으로」 추세 거르기(Faber 식)를 얹으면 나은가",
           "trials": len(grid), "is": [START, IS_END], "oos": [OOS_START, end], "spy": spy_row,
           "current": strip(cur), "chosen": strip(chosen), "check": chk,
           "grid": [{"n": g["cfg"]["n"], "check": g["cfg"]["check"], "apply": g["cfg"]["apply"],
                     "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"], "is_mdd": g["is"]["mdd"],
                     "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                     "oos_turn": g["oos"]["turn"], "oos_sw": g["oos"]["sw"], "off_pct": g["off_pct_oos"], "risk_avg": g["risk_avg_oos"]} for g in grid],
           "by_apply": by_apply,
           "robust": [strip(r) for r in robust], "rank_corr": rc, "grid_beat_current_oos": f"{beat}/{len(grid)}",
           "verdict": verdict, "verdict_why": why,
           "next": ("적용 제안 — 사용자에게 「칸별 추세 거르기」 안건으로 (회전·헛바뀜 함께 보고)" if verdict == "✅"
                    else "💼 기본 규칙 그대로 · 칸 거르기는 판정+변동성 맞춤과 겹치는 방어인지 grid off_pct·risk_avg 로 확인"),
           "now": now, "check_lab": CHECK_LAB, "apply_lab": APPLY_LAB,
           "note": "기본 = 💼 C안 뼈대 + 판정(S&P 200일선·3일) + 🦴 변동성 맞춤 방어형(20일·15%·바닥 30%·5%p 밴드) · 칸 거르기는 그 위에 얹어 줄이기만 · "
                   "추세 = 칸 ETF(배당 포함) 종가 vs N일 단순이평 · 다음 날 체결 · 매주+목표 바뀐 날 비중 맞춤 · 회전율×0.1% · sw = 해마다 판정·칸 깃발 바뀐 횟수 · 매수 추천 아님"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")

    p = lambda o: f"연 {o['cagr']}% · 낙폭 {o['mdd']}% · 샤프 {o['sharpe']} · 회전 {o['turn']}% · 바뀜 {o['sw']}회/년"
    print("== 🌙 10/22 칸별 추세 거르기 (k1022_assettrend) ==")
    print("S&P   시험", spy_row["oos"].get("cagr"), spy_row["oos"].get("mdd"), spy_row["oos"].get("sharpe"))
    print("지금  시험", p(cur["oos"]), "| 앞", cur["is"]["sharpe"])
    print("고른", c, "앞 샤프", chosen["is"]["sharpe"], "| 시험", p(chosen["oos"]), "· 꺼진 비율", chosen["off_pct_oos"])
    for r in robust:
        print("흔들기", r["what"], p(r["oos"]))
    print("조합", len(grid), "· 지금보다 시험 샤프 높은 조합", beat, "· 앞/뒤 순위상관", rc, "· 칸별", by_apply)
    for g in grid:
        print(" ", g["cfg"]["n"], g["cfg"]["check"], g["cfg"]["apply"], "| 앞", g["is"]["sharpe"], g["is"]["cagr"],
              "| 시험", g["oos"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sw"], g["off_pct_oos"])
    print("오늘", now)
    print(verdict, why)


if __name__ == "__main__":
    main()
