"""🌙 10/22 밤 연구 — 💼 기본 뼈대 판정 바꾸기: 「S&P 200일선 + 3일 확인」 하나 대신 AQR 식 여러 기간 추세 투표
  질문: S&P500(SPY 배당 포함 가격)의 1·3·12개월 수익 부호로 투표하면 지금 판정보다 나은가 (헛바뀜·낙폭·샤프)
  기본 = 지금 운용 그대로의 💼 뼈대
     🟢 S&P 47.5 · 나스닥 47.5 · 금 5 · 현금 0 / 🔴 31.5 · 31.5 · 금 11 · 현금 26 (ledger.skeleton)
     + 🦴 변동성 맞춤(방어형, rules7.VOL_ROLES["base"]: 20일 · 목표 15% · 아래 한도 30% · 5%p 넘게 바뀔 때만 따라감) — 주식 칸만, 덜어낸 만큼 현금
     · 금 조건부는 운용에 없음(10/12 skel_lab ➖) → 금은 뼈대 고정 비중
  「지금」 판정 = S&P500(^GSPC) 200일선 위 · 바뀐 상태가 3거래일 이어져야 인정 (conc_bt.regimes["A"])
  새 판정 손잡이
     기간 묶음 {1,3,12} · {1,3,6,12} · {3,6,12}개월 (1개월 = 21거래일)
     방식 maj = 과반(양수 표 > ½)이면 🟢 · all = 전부 양수여야 🟢 · frac = 양수 표 비율만큼 🟢·🔴 뼈대를 섞음
     확인 일수 1 · 3 (maj·all 은 합친 판정에, frac 은 표 하나하나에)
  판단은 그날 종가까지 → 다음 날 종가 체결 · 매주 + 목표 비중이 바뀐 날 비중 맞춤 · 회전율 × 0.1% 비용 · 현금 = BIL
  2008-07~2016 샤프로 고르고 2017~ 에서 시험 · 흔들기 = 기간 전부 ×0.8 / ×1.2 (예: 12개월 → 약 10 / 14개월)
  판정: ✅ = 시험 구간 샤프 > 지금 · 연수익 ≥ 지금 −0.3%p · 낙폭이 지금보다 2%p 넘게 나쁘지 않음 · 흔들기 둘 다 샤프 > 지금
→ market/lab/k1022_trend3.json
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
from src.rules7 import VOL_ROLES, held_scale_line

OUT = Path("market/lab/k1022_trend3.json")
COST = 0.001
COLS = ["SPY", "QQQ", "GLD", "BIL"]
G_UP = np.array([0.475, 0.475, 0.05, 0.0])      # 🟢 ledger.skeleton.up
G_DN = np.array([0.315, 0.315, 0.11, 0.26])     # 🔴 ledger.skeleton.down
MD = 21                                          # 1개월 = 21거래일
LB_SETS = [(1, 3, 12), (1, 3, 6, 12), (3, 6, 12)]
MODES = ["maj", "all", "frac"]
CONFS = [1, 3]
MODE_LAB = {"maj": "과반이면 🟢", "all": "전부 양수여야 🟢", "frac": "양수 표 비율만큼 섞기"}


# ---------------------------------------------------------------- 공통 (k1022_assettrend.py 도 씀)
def load():
    import yfinance as yf
    tick = ["SPY", "QQQ", "GLD", "BIL", "^GSPC"]
    df = yf.download(tick, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick if t in df.columns.get_level_values(0)}).dropna(how="all")
    C = C.dropna(subset=["SPY", "QQQ", "GLD"]).ffill(limit=5)
    C["BIL"] = C["BIL"].ffill()          # BIL 은 2007-05~ (그 전은 수익 0 — 시작 2008-07 이라 영향 없음)
    C["^GSPC"] = C["^GSPC"].ffill()
    return C


def sticky(s: pd.Series, k: int) -> pd.Series:
    """바뀐 상태가 k거래일 이어져야 인정 (k<=1 이면 그대로) — 시작값은 첫날 값"""
    s = s.fillna(False).astype(bool)
    if k <= 1:
        return s
    out, cur, run = [], bool(s.iloc[0]), 0
    for v in s.values:
        if v != cur:
            run += 1
            if run >= k:
                cur, run = v, 0
        else:
            run = 0
        out.append(cur)
    return pd.Series(out, index=s.index)


def vol_scale(C) -> np.ndarray:
    """💼 방어형 변동성 맞춤 배율 (운용과 같은 rules7.held_scale_line · 5%p 밴드)"""
    _, h = held_scale_line(C["SPY"], C["QQQ"], VOL_ROLES["base"])
    return h.reindex(C.index).ffill().fillna(1.0).values.astype(float)


def base_weights(f: np.ndarray, sc: np.ndarray) -> np.ndarray:
    """f = 🟢 비율(0~1) · sc = 변동성 배율 → (n, 4) 목표 비중 [SPY, QQQ, GLD, BIL]"""
    f = np.asarray(f, dtype=float)
    B = f[:, None] * G_UP + (1 - f)[:, None] * G_DN
    eq = (B[:, 0] + B[:, 1]) * sc
    return np.column_stack([eq / 2, eq / 2, B[:, 2], 1 - eq - B[:, 2]])


def simulate(C, W: np.ndarray, start=START):
    """W[i] = i일 종가로 정한 목표 → i+1일 종가에 체결. 매주 첫 판단일 + 목표가 바뀐 날 비중 맞춤.
       반환: (일별 NAV Series, 일별 회전(|Δw| 합) Series)"""
    idx = C.index
    R = C[COLS].pct_change().fillna(0.0).values
    sel = np.where(idx >= pd.Timestamp(start))[0]
    iso = idx.isocalendar()
    wk = (iso.year.values * 100 + iso.week.values)
    i0 = sel[0]
    w = W[i0 - 1].copy() if i0 > 0 else W[i0].copy()
    last_t, last_k = w.copy(), wk[i0 - 1] if i0 > 0 else None
    nav = np.empty(len(sel)); turn = np.zeros(len(sel)); val = 1.0; pend = None
    for j, i in enumerate(sel):
        if j > 0:
            r = R[i]
            val *= 1 + float(w @ r)
            gw = w * (1 + r); s_ = gw.sum()
            if s_ > 0:
                w = gw / s_
        if pend is not None:
            t = float(np.abs(pend - w).sum()); turn[j] = t
            val *= 1 - t * COST; w = pend; pend = None
        nav[j] = val
        tg = W[i]
        if wk[i] != last_k or float(np.abs(tg - last_t).max()) > 1e-9:
            pend = tg.copy(); last_t = tg.copy(); last_k = wk[i]
    d = idx[sel]
    return pd.Series(nav, index=d), pd.Series(turn, index=d)


def seg(nav, turn, sw, spy, a, b) -> dict:
    n = nav[a:b]
    st = stats(n, spy[a:b])
    yrs = max(0.5, (n.index[-1] - n.index[0]).days / 365.25)
    return {"cagr": st.get("cagr"), "vol": st.get("vol"), "mdd": st.get("mdd"), "sharpe": st.get("sharpe"), "ex": st.get("ex"),
            "beat_years": st.get("beat_years"), "years": st.get("years"),
            "turn": round(float(turn[a:b].sum()) / yrs * 100), "sw": round(float(sw[a:b].sum()) / yrs, 1)}


def switches(x) -> pd.Series:
    """노출(또는 깃발) 줄이 바뀐 횟수 (일별)"""
    x = pd.DataFrame(x) if not isinstance(x, pd.DataFrame) else x
    return (x.astype(float).diff().abs() > 1e-9).sum(axis=1).astype(float)


def evaluate(C, W, sw, spy, end):
    nav, turn = simulate(C, W)
    sw = sw.reindex(nav.index).fillna(0.0)
    return {"is": seg(nav, turn, sw, spy, START, IS_END), "oos": seg(nav, turn, sw, spy, OOS_START, end), "_nav": nav}


def rank_corr(rows) -> float | None:
    a = pd.Series([r["is"]["sharpe"] for r in rows], dtype=float)
    b = pd.Series([r["oos"]["sharpe"] for r in rows], dtype=float)
    v = a.rank().corr(b.rank())
    return None if v != v else round(float(v), 2)


def judge(ch, cur, robust) -> tuple[str, str, dict]:
    """✅ = 시험 샤프 > 지금 · 연수익 ≥ 지금 −0.3%p · 낙폭 2%p 넘게 안 나빠짐 · 흔들기 전부 샤프 > 지금"""
    o, c = ch["oos"], cur["oos"]
    chk = {"sharpe": bool((o["sharpe"] or -9) > (c["sharpe"] or -9)),
           "cagr": bool(o["cagr"] >= c["cagr"] - 0.3),
           "mdd": bool(o["mdd"] >= c["mdd"] - 2.0),
           "robust": bool(robust and all((r["oos"]["sharpe"] or -9) > (c["sharpe"] or -9) for r in robust))}
    d = f"시험 구간 샤프 {o['sharpe']} vs 지금 {c['sharpe']} · 연 {o['cagr']}% vs {c['cagr']}% · 낙폭 {o['mdd']}% vs {c['mdd']}%"
    if all(chk.values()):
        return "✅", f"네 조건 모두 통과 — {d}. 흔들기도 지금보다 샤프가 높음.", chk
    if not chk["sharpe"] and not chk["cagr"]:
        return "❌", f"샤프·연수익 둘 다 지금보다 못함 — {d}.", chk
    miss = [k for k, v in chk.items() if not v]
    lab = {"sharpe": "샤프", "cagr": "연수익(−0.3%p 안)", "mdd": "낙폭(2%p 안)", "robust": "흔들기"}
    return "➖", f"{'·'.join(lab[k] for k in miss)} 조건 못 넘음 — {d}.", chk


def strip(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


# ---------------------------------------------------------------- 이 실험
def votes(spy_tr: pd.Series, lbs_days, k) -> pd.DataFrame:
    """기간마다 「L일 수익 > 0」 표 · k일 확인은 표 하나하나에"""
    return pd.DataFrame({L: sticky(spy_tr / spy_tr.shift(L) - 1 > 0, k) for L in lbs_days})


def exposure(spy_tr, lbs_m, mode, k, mult=1.0) -> pd.Series:
    days = [max(5, int(round(MD * m * mult))) for m in lbs_m]
    if mode == "frac":
        return votes(spy_tr, days, k).mean(axis=1)
    share = votes(spy_tr, days, 1).mean(axis=1)
    on = share > 0.5 if mode == "maj" else share >= 1.0 - 1e-9
    return sticky(on, k).astype(float)


def main():
    C = load()
    spy = C["SPY"]
    end = str(C.index[-1].date())
    sc = vol_scale(C)
    reg = regimes(C["^GSPC"], C[["SPY"]])["A"].reindex(C.index).fillna(False).astype(float)
    spy_row = {"is": {k: v for k, v in stats(spy[START:IS_END]).items()}, "oos": {k: v for k, v in stats(spy[OOS_START:end]).items()}}

    cur = evaluate(C, base_weights(reg.values, sc), switches(reg), spy, end)
    cur["cfg"] = {"rule": "S&P500 200일선 위 · 3일 확인 (지금)"}

    def run(lbs, mode, k, mult=1.0):
        f = exposure(spy, lbs, mode, k, mult)
        o = evaluate(C, base_weights(f.values, sc), switches(f), spy, end)
        o["cfg"] = {"lbs": list(lbs), "mode": mode, "k": k, "mult": mult}
        o["up_pct_oos"] = round(float(f[OOS_START:].mean()) * 100)
        return o

    grid = [run(lbs, m, k) for lbs, m, k in itertools.product(LB_SETS, MODES, CONFS)]
    chosen = max(grid, key=lambda g: (g["is"]["sharpe"] or -9, g["is"]["cagr"]))
    c = chosen["cfg"]
    robust = []
    for mult in (0.8, 1.2):
        g = run(c["lbs"], c["mode"], c["k"], mult)
        g["what"] = f"기간 ×{mult} ({', '.join(str(round(m * mult, 1)) for m in c['lbs'])}개월)"
        robust.append(g)
    verdict, why, chk = judge(chosen, cur, robust)
    rc = rank_corr(grid)
    beat = sum(1 for g in grid if (g["oos"]["sharpe"] or -9) > (cur["oos"]["sharpe"] or -9))

    # 오늘 상태
    days_now = {m: MD * m for m in sorted({m for s in LB_SETS for m in s})}
    now = {"date": end, "reg_now": bool(reg.iloc[-1]),
           "ret": {f"{m}m": round(float(spy.iloc[-1] / spy.iloc[-1 - L] - 1) * 100, 1) for m, L in days_now.items()},
           "chosen_exposure": round(float(exposure(spy, c["lbs"], c["mode"], c["k"]).iloc[-1]), 2), "vol_scale": round(float(sc[-1]), 2)}

    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
           "question": "💼 기본 뼈대의 🟢/🔴 판정을 「S&P 200일선 + 3일 확인」 대신 1·3·12개월 등 여러 기간 S&P 수익 부호 투표(AQR 식)로 바꾸면 나은가",
           "trials": len(grid), "is": [START, IS_END], "oos": [OOS_START, end], "spy": spy_row,
           "current": strip(cur), "chosen": strip(chosen), "check": chk,
           "grid": [{"lbs": g["cfg"]["lbs"], "mode": g["cfg"]["mode"], "k": g["cfg"]["k"],
                     "is_sh": g["is"]["sharpe"], "is_cagr": g["is"]["cagr"], "is_mdd": g["is"]["mdd"],
                     "oos_sh": g["oos"]["sharpe"], "oos_cagr": g["oos"]["cagr"], "oos_mdd": g["oos"]["mdd"],
                     "oos_turn": g["oos"]["turn"], "oos_sw": g["oos"]["sw"], "up_pct": g["up_pct_oos"]} for g in grid],
           "robust": [strip(r) for r in robust], "rank_corr": rc, "grid_beat_current_oos": f"{beat}/{len(grid)}",
           "verdict": verdict, "verdict_why": why,
           "next": ("적용 제안 — 사용자에게 「판정 바꾸기」 안건으로 (헛바뀜·회전 함께 보고)" if verdict == "✅"
                    else "판정은 지금(200일선·3일) 그대로 · 다음 밤: 자산별 추세 거르기(k1022_assettrend)"),
           "now": now, "mode_lab": MODE_LAB,
           "note": "기본 = 💼 C안 뼈대(🟢 47.5·47.5·금 5 / 🔴 31.5·31.5·금 11·현금 26) + 🦴 변동성 맞춤 방어형(20일·15%·바닥 30%·5%p 밴드) · 금 조건부 없음 · "
                   "투표 = SPY(배당 포함) 21·63·126·252거래일 수익 부호 · 다음 날 체결 · 매주+목표 바뀐 날 비중 맞춤 · 회전율×0.1% · sw = 해마다 노출 바뀐 횟수 · 매수 추천 아님"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")

    p = lambda o: f"연 {o['cagr']}% · 낙폭 {o['mdd']}% · 샤프 {o['sharpe']} · 회전 {o['turn']}% · 판정 바뀜 {o['sw']}회/년"
    print("== 🌙 10/22 추세 투표 (k1022_trend3) ==")
    print("S&P   시험", spy_row["oos"].get("cagr"), spy_row["oos"].get("mdd"), spy_row["oos"].get("sharpe"))
    print("지금  시험", p(cur["oos"]), "| 앞", cur["is"]["sharpe"])
    print("고른", c, "앞 샤프", chosen["is"]["sharpe"], "| 시험", p(chosen["oos"]))
    for r in robust:
        print("흔들기", r["what"], p(r["oos"]))
    print("조합", len(grid), "· 지금보다 시험 샤프 높은 조합", beat, "· 앞/뒤 순위상관", rc)
    for g in grid:
        print(" ", g["cfg"]["lbs"], g["cfg"]["mode"], g["cfg"]["k"], "| 앞", g["is"]["sharpe"], g["is"]["cagr"], "| 시험", g["oos"]["sharpe"], g["oos"]["cagr"], g["oos"]["mdd"], g["oos"]["sw"])
    print("오늘", now)
    print(verdict, why)


if __name__ == "__main__":
    main()
