"""🎯 신호 확률판 (11/12 사용자: 「어떤 신호가 왔을 때 현금 비중을 늘리는지 · 어떤 바닥 신호들이 왔을 때 주식 비중을 늘리는지 —
   동원할 수 있는 모든 방법을 동원해서 확률을 좀 높여줘」)

  어제까지는 「규칙으로 사고팔면 보유를 이겼나」만 봤다. 이번엔 신호마다 「켜진 날 뒤에 실제로 무슨 일이 얼마나 자주 있었나」를 센다.

  결과 보기 전 등록한 것
  ─ 지수 9개(season_bt 와 같음 · 가격지수) · 그날 종가 기준 · 미국발 신호(신용·금리·VIX·속살)는 아시아 지수엔 하루 늦게 붙임
  ─ 맞히려는 것
     하락: 「앞으로 6개월(126거래일) 안에 지금보다 10% 넘게 아래로 간 적이 있다」
     바닥: (1년 고점보다 −15% 넘게 빠져 있는 날만) 「6개월 뒤 지금보다 높고, 그 사이 −10% 넘게 더 빠지지도 않았다」 = 좋은 매수 자리
  ─ 경고 신호 15개: 200일선 아래 · 데드크로스(50<200) · 고점 −10% · 과열(200일선과의 거리 상위 10%) · 1년 전보다 낮음 · 변동성 급증 ·
       최근 10일 안 60일 신저가 · 🇺🇸 신용 악화(하이일드÷국채) · 장단기 금리 뒤집힘 · 뒤집혔다 다시 벌어짐 · VIX 25↑ · 지수는 고점인데 평균 종목은 약함 ·
       버블 시계 6시↑ · 미 10년 금리 6개월 +1%p · S&P500 200일선 아래
  ─ 바닥 신호 14개: 저점 10일 넘게 안 깨짐+20일선 위 · 50일선 위 · 200일선 위 · 저점에서 10일 +8% 급반등 · 팔로스루 데이(저점 4~12일 뒤 +1.7%) ·
       VIX 40↑ 찍고 30 아래 · VIX 20 아래 · 신용 회복 · 연준 금리 인하 중 · 고점 −30% 넘게 쌈 · RSI 30 아래 찍고 40 회복 · 저점이 높아짐 · S&P500 200일선 위 · 3개월 수익 플러스
  ─ 보는 법 ① 신호별: 켜진 날 확률 ÷ 평소 확률(배수) — 앞(~2012)·뒤(2013~) 둘 다 1.15배 넘고 9개 지수 중 6개 넘게 같은 방향이면 「믿을 만」
            ② 겹치기: 켜진 신호 수(전체 · 믿을 만한 것만) → 확률 계단 (앞·뒤 따로)
            ③ 모형: 로지스틱 회귀를 해마다 「그 전 자료만」으로 다시 맞춰 그 해를 맞힘(걸어가며 · 6개월 겹침 빼고) → AUC · 예측 구간별 실제 빈도
  결과: market/prob.json → 앱 🎯 신호 확률판. 날마다 겹치는 표본이라 「독립 사건 수」는 훨씬 적다 · 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bubble_bt as bb   # noqa: E402
import season_bt as sb   # noqa: E402

OUT = bb.ROOT / "market" / "prob.json"
SPLIT = pd.Timestamp("2013-01-01")
H = 126
WN = {"w_b200": "200일선 아래", "w_dc": "데드크로스(50일선<200일선)", "w_dd10": "1년 고점보다 −10%↓", "w_hot": "과열(200일선보다 한참 위)", "w_mom12": "1년 전보다 낮음",
      "w_vol": "변동성 급증", "w_low60": "최근 10일 안 60일 신저가", "w_cred": "🇺🇸 신용 악화(하이일드 채권 약세)", "w_inv": "🇺🇸 장단기 금리 뒤집힘", "w_curve": "🇺🇸 뒤집혔던 금리차 다시 벌어짐",
      "w_vix25": "VIX 25 위", "w_breadth": "🇺🇸 지수는 고점인데 평균 종목은 약함", "w_clock6": "버블 시계 6시↑", "w_rate": "🇺🇸 10년 금리 6개월 새 +1%p", "w_usbear": "S&P500 200일선 아래",
      # 2차(11/12 · 1차 결과를 본 뒤 등록 — 1차: 믿을 만한 경고 2개뿐 · 바닥 0개 · 모형 AUC 0.51): 신호 넓히기 + 「갓 켜진」 신호 + 큰 하락(−20%)·1년 뒤 목표 + 지수별 표 + 나무 모형
      "w_sox": "반도체 지수(SOX) 200일선 아래", "w_dxy": "달러 3개월 새 +5% 강세", "w_copper": "구리÷금 6개월 새 −10%", "w_oil": "유가 6개월 새 +40%", "w_hydd": "🇺🇸 하이일드 채권 고점보다 −5%",
      "w_f200": "200일선 갓 깨짐(20일 안)", "w_fdd10": "고점 −10% 갓 넘음(20일 안)", "w_fdc": "데드크로스 갓 남(20일 안)"}
BN = {"b_base": "저점 10일 넘게 안 깨짐 + 20일선 위", "b_a50": "50일선 위로", "b_a200": "200일선 위로", "b_thrust": "저점에서 10일 +8% 급반등", "b_ftd": "팔로스루 데이(저점 4~12일 뒤 +1.7%)",
      "b_vixcap": "VIX 40 찍고 30 아래로", "b_vix20": "VIX 20 아래", "b_credup": "🇺🇸 신용 회복(하이일드 채권 강세)", "b_cut": "🇺🇸 단기 금리 내리는 중(연준 인하)", "b_deep30": "1년 고점보다 −30% 넘게 쌈",
      "b_rsi": "RSI 30 아래 찍고 40 회복", "b_hl": "저점이 높아짐", "b_usup": "S&P500 200일선 위", "b_mom3": "3개월 수익 플러스",
      "b_sox": "반도체 지수(SOX) 200일선 위", "b_dxydn": "달러 3개월 새 −3% 약세", "b_hyup": "🇺🇸 하이일드 채권 50일선 위", "b_f200": "200일선 갓 회복(20일 안)", "b_gc": "골든크로스(50일선>200일선)"}
WK, BK = list(WN), list(BN)
CORE = ["w_b200", "w_mom12", "w_vol", "w_cred", "w_inv", "w_vix25", "b_base", "b_rsi"]


def globals_(px):
    g = px["^GSPC"]; idx = g.index
    A = lambda s: px[s].reindex(idx).ffill() if s in px else pd.Series(np.nan, index=idx)
    G = pd.DataFrame(index=idx)
    r = A("VWEHX") / A("VFITX"); c20, c60 = r.pct_change(20) * 100, r.pct_change(60) * 100
    G["w_cred"] = (c20 <= -1.5) | (c60 <= -3)
    G["b_credup"] = c20 >= 1.0
    t = A("^TNX"); t = t.where(t < 20, t / 10); irx = A("^IRX"); sp = t - irx
    G["w_inv"] = sp < 0
    G["w_curve"] = ((sp < 0).astype(float).rolling(252, min_periods=60).max() > 0) & (sp > 0.5)
    G["w_rate"] = (t - t.shift(126)) >= 1.0
    G["b_cut"] = (irx.shift(63) - irx) >= 0.5
    v = A("^VIX")
    G["w_vix25"] = v > 25
    G["b_vix20"] = v < 20
    G["b_vixcap"] = (v.rolling(60, min_periods=5).max() >= 40) & (v < 30)
    eq = A("RSP") / g
    G["w_breadth"] = (eq.pct_change(60) <= -0.03) & (g / g.rolling(252, min_periods=60).max() - 1 >= -0.05)
    m200 = g.rolling(200).mean()
    G["w_usbear"] = g < m200
    G["b_usup"] = g > m200
    sox = A("^SOX"); sm = sox.rolling(200).mean()
    G["w_sox"] = sox < sm; G["b_sox"] = sox > sm
    dxy = A("DX-Y.NYB"); d63 = dxy.pct_change(63)
    G["w_dxy"] = d63 >= 0.05; G["b_dxydn"] = d63 <= -0.03
    cg = A("HG=F") / A("GC=F"); G["w_copper"] = cg.pct_change(126) <= -0.10
    oil = A("CL=F"); G["w_oil"] = oil.pct_change(126) >= 0.40
    hy = A("VWEHX"); G["w_hydd"] = hy / hy.rolling(252, min_periods=120).max() - 1 <= -0.05
    G["b_hyup"] = hy > hy.rolling(50).mean()
    for k, src in (("w_sox", sm), ("b_sox", sm), ("w_dxy", d63), ("b_dxydn", d63), ("w_copper", cg.shift(126)), ("w_oil", oil.shift(126))):
        G[k] = G[k].astype(float).where(src.notna())
    C = bb.cells(px); _, _, hf = bb.clock(C)
    G["w_clock6"] = hf.reindex(idx) >= 6
    valid = pd.DataFrame({"cred": r.notna(), "vix": v.notna(), "eq": eq.notna() & eq.shift(60).notna(), "rate": t.notna() & irx.notna()}, index=idx)
    return G.astype(float).ffill(), valid


def feats(s, G, us):
    idx = s.index; c = s.values; n = len(c)
    m20, m50, m200 = (s.rolling(k).mean() for k in (20, 50, 200))
    hi = s.rolling(252, min_periods=60).max(); dd = s / hi - 1
    gap = s / m200 - 1
    q90 = gap.expanding(min_periods=500).quantile(0.9).shift(1)
    r = s.pct_change()
    rv = r.rolling(20).std()
    rvq = rv.rolling(252, min_periods=120).quantile(0.8).shift(1)
    low60 = s <= s.rolling(60, min_periods=20).min()
    since = s.rolling(60, min_periods=20).apply(lambda w: len(w) - 1 - int(np.argmin(w)), raw=True)
    a20 = s > m20
    F = pd.DataFrame(index=idx)
    F["w_b200"] = s < m200; F["w_dc"] = m50 < m200; F["w_dd10"] = dd <= -0.10; F["w_hot"] = gap > q90
    F["w_mom12"] = s / s.shift(252) < 1; F["w_vol"] = rv > rvq
    F["w_low60"] = low60.astype(float).rolling(10, min_periods=1).max() > 0
    F["b_base"] = (since > 10) & a20 & a20.shift(1).fillna(False)
    F["b_a50"] = s > m50; F["b_a200"] = s > m200
    F["b_thrust"] = ((s / s.shift(10) - 1 >= 0.08) & (since <= 12)).astype(float).rolling(20, min_periods=1).max() > 0
    F["b_ftd"] = ((r >= 0.017) & (since >= 4) & (since <= 12)).astype(float).rolling(20, min_periods=1).max() > 0
    F["b_deep30"] = dd <= -0.30
    d = s.diff(); up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    F["b_rsi"] = (rsi.rolling(20, min_periods=5).min() < 30) & (rsi > 40)
    F["b_hl"] = s.rolling(20).min() > s.shift(20).rolling(60, min_periods=30).min()
    F["b_mom3"] = s / s.shift(63) > 1
    fresh = lambda st: st & (st.astype(float).rolling(20, min_periods=20).min() < 1)
    F["w_f200"] = fresh(s < m200); F["w_fdd10"] = fresh(dd <= -0.10); F["w_fdc"] = fresh(m50 < m200)
    F["b_f200"] = fresh(s > m200); F["b_gc"] = m50 > m200
    g = G.shift(0 if us else 1).reindex(idx, method="ffill")
    for k in g.columns:
        F[k] = g[k]
    F = F.astype(float)
    ok = m200.notna() & s.shift(252).notna() & rvq.notna()
    # 맞히려는 것
    fmin = pd.Series(c[::-1], index=idx[::-1]).rolling(H, min_periods=H).min()[::-1].shift(-1) / s - 1   # 앞으로 H일 최저
    fret = s.shift(-H) / s - 1
    H2 = 252
    fmin2 = pd.Series(c[::-1], index=idx[::-1]).rolling(H2, min_periods=H2).min()[::-1].shift(-1) / s - 1
    fret2 = s.shift(-H2) / s - 1
    Y = pd.DataFrame({"crash": (fmin2 <= -0.20).astype(float).where(fmin2.notna()), "up12": (fret2 > 0).astype(float).where(fret2.notna()), "fret12": fret2, "down": (fmin <= -0.10).astype(float).where(fmin.notna()), "good": ((fret > 0) & (fmin > -0.10)).astype(float).where(fret.notna()),
                      "up": (fret > 0).astype(float).where(fret.notna()), "fret": fret, "dd": dd, "ok": ok})
    return F[WK + BK], Y


def runs(m):
    return int(((m.astype(int).diff() == 1).sum()) + int(bool(m.iloc[0]))) if len(m) else 0


def sig_table(D, keys, tgt, names):
    """D: 모든 지수 합친 표(mk·date·신호·tgt)"""
    rows = []
    base = float(D[tgt].mean()); fr, bk = D[D.date < SPLIT], D[D.date >= SPLIT]
    for k in keys:
        on = D[k] > 0.5
        if on.sum() < 200:
            rows.append({"k": k, "name": names[k], "n": int(on.sum()), "thin": True}); continue
        p_on, p_off = float(D.loc[on, tgt].mean()), float(D.loc[~on, tgt].mean())
        la = float(fr.loc[fr[k] > 0.5, tgt].mean() / fr[tgt].mean()) if (fr[k] > 0.5).sum() >= 100 else None
        lb = float(bk.loc[bk[k] > 0.5, tgt].mean() / bk[tgt].mean()) if (bk[k] > 0.5).sum() >= 100 else None
        mk_ok = mk_n = 0
        for _, d in D.groupby("mk"):
            o = d[k] > 0.5
            if o.sum() >= 60:
                mk_n += 1; mk_ok += int(d.loc[o, tgt].mean() > d[tgt].mean())
        ep = sum(runs(d[k] > 0.5) for _, d in D.groupby("mk"))
        lift = p_on / base
        rows.append({"k": k, "name": names[k], "share": round(float(on.mean()) * 100, 1), "p_on": round(p_on * 100), "p_off": round(p_off * 100), "lift": round(lift, 2),
                     "lift_a": None if la is None else round(la, 2), "lift_b": None if lb is None else round(lb, 2), "mk_ok": mk_ok, "mk_n": mk_n, "episodes": ep,
                     "fret": round(float(D.loc[on, "fret"].mean()) * 100, 1),
                     "good": bool(la is not None and lb is not None and la >= 1.15 and lb >= 1.15 and mk_n and mk_ok / mk_n > 0.66),
                     "anti": bool(la is not None and lb is not None and la <= 0.87 and lb <= 0.87)})
    return sorted(rows, key=lambda x: -(x.get("lift") or 0)), round(base * 100, 1)


def ladder(D, cnt, tgt, edges):
    out = []
    for lo, hi in edges:
        m = (cnt >= lo) & (cnt <= hi)
        f = lambda x: None if x.sum() < 150 else round(float(D.loc[x, tgt].mean()) * 100)
        out.append({"lo": lo, "hi": hi, "n": int(m.sum()), "share": round(float(m.mean()) * 100, 1), "p": f(m), "p_a": f(m & (D.date < SPLIT)), "p_b": f(m & (D.date >= SPLIT)),
                    "fret": None if m.sum() < 150 else round(float(D.loc[m, "fret"].mean()) * 100, 1)})
    return out


def logit_fit(X, y, lam=2.0, it=30):
    X1 = np.column_stack([np.ones(len(X)), X]); w = np.zeros(X1.shape[1]); R = np.eye(X1.shape[1]) * lam; R[0, 0] = 0
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(X1 @ w, -30, 30)))
        g = X1.T @ (p - y) + R @ w
        Hm = (X1 * (p * (1 - p))[:, None]).T @ X1 + R
        try:
            st = np.linalg.solve(Hm, g)
        except np.linalg.LinAlgError:
            break
        w -= st
        if np.abs(st).max() < 1e-6:
            break
    return w


def logit_pred(w, X):
    return 1 / (1 + np.exp(-np.clip(np.column_stack([np.ones(len(X)), X]) @ w, -30, 30)))


def auc(y, p):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else None


def walk(D, keys, tgt, y0=2006):
    """해마다 그 전 자료(6개월 겹침 뺌)로 맞추고 그 해를 맞힘 → 표에 p 열"""
    P = pd.Series(np.nan, index=D.index)
    for y in range(y0, int(D.date.dt.year.max()) + 1):
        tr = D[D.date < pd.Timestamp(f"{y}-01-01") - pd.Timedelta(days=190)]
        te = D[D.date.dt.year == y]
        if len(tr) < 3000 or not len(te) or tr[tgt].nunique() < 2:
            continue
        w = logit_fit(tr[keys].values, tr[tgt].values)
        P.loc[te.index] = logit_pred(w, te[keys].values)
    return P


def calib(D, P, tgt, q=(0, .2, .4, .6, .8, 1.0)):
    m = P.notna(); d = D[m]; p = P[m]
    if len(d) < 500:
        return None
    base = float(d[tgt].mean())
    cuts = np.quantile(p, q); bins = []
    for i in range(len(q) - 1):
        k = (p >= cuts[i]) & ((p <= cuts[i + 1]) if i == len(q) - 2 else (p < cuts[i + 1]))
        if k.sum():
            bins.append({"pred": round(float(p[k].mean()) * 100), "real": round(float(d.loc[k, tgt].mean()) * 100), "n": int(k.sum())})
    br = float(((p - d[tgt]) ** 2).mean()); br0 = float(((base - d[tgt]) ** 2).mean())
    per = {}
    for mk, g in d.groupby("mk"):
        if g[tgt].nunique() == 2:
            per[mk] = round(auc(g[tgt].values, p[g.index].values), 3)
    return {"auc": round(auc(d[tgt].values, p.values), 3), "brier_skill": round(1 - br / br0, 3), "base": round(base * 100, 1), "bins": bins, "n": int(len(d)),
            "from": str(d.date.min().date()), "to": str(d.date.max().date()), "auc_by_market": per}


def main():
    extra = ["^VIX", "RSP", "^SOX", "DX-Y.NYB", "HG=F", "GC=F"] + [m[1] for m in sb.MK]
    bb.SYMS = bb.SYMS + [x for x in extra if x not in bb.SYMS]
    px = {}
    for s in bb.SYMS:
        d = sb.load(s)
        if d is not None:
            px[s] = d
        else:
            print("시세 없음", s)
    G, _ = globals_(px)
    rows = []; last = {}
    for key, sym, name, nat in sb.MK:
        s = px.get(sym)
        if s is None or len(s) < 3000:
            continue
        F, Y = feats(s, G, nat == "us")
        d = pd.concat([F, Y], axis=1); d["mk"] = key; d["date"] = d.index
        d = d[d["ok"] & F[CORE].notna().all(axis=1)]
        d[WK + BK] = d[WK + BK].fillna(0.0)
        last[key] = (name, nat, d.iloc[-1], str(d.index[-1].date()))
        rows.append(d)
    A = pd.concat(rows, ignore_index=True)
    res = {"at": dt.datetime.now(bb.KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "wn": WN, "bn": BN, "targets": {}}
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier as HGB
    except Exception:
        HGB = None
    def walk_gb(D, keys, tgt):
        if HGB is None: return None
        P = pd.Series(np.nan, index=D.index)
        for y in range(2006, int(D.date.dt.year.max()) + 1):
            tr = D[D.date < pd.Timestamp(f"{y}-01-01") - pd.Timedelta(days=380 if tgt in ("crash", "up12") else 190)]; te = D[D.date.dt.year == y]
            if len(tr) < 3000 or not len(te) or tr[tgt].nunique() < 2: continue
            m = HGB(max_depth=3, max_iter=120, learning_rate=0.05, l2_regularization=1.0, random_state=0).fit(tr[keys].values, tr[tgt].values)
            P.loc[te.index] = m.predict_proba(te[keys].values)[:, 1]
        return P
    TG = [("down", "경고 → 6개월 안 −10%", WK, WN, None, "down"), ("crash", "경고 → 1년 안 −20%(큰 하락)", WK, WN, None, "down"),
          ("good", "바닥(고점 −20% 아래) → 6개월 좋은 매수 자리", BK, BN, -0.20, "up"), ("up12", "바닥(고점 −20% 아래) → 1년 뒤 플러스", BK, BN, -0.20, "up")]
    fits = {}
    for tg, title, keys, names, ddmax, side in TG:
        D = A[A[tg].notna()]
        if ddmax is not None: D = D[D.dd <= ddmax]
        D = D.reset_index(drop=True)
        tb, base = sig_table(D, keys, tg, names)
        good = [x["k"] for x in tb if x.get("good")]
        cg = D[good].sum(axis=1) if good else pd.Series(0, index=D.index)
        ng = len(good)
        edges = [(0, 0), (1, 1), (2, 2), (3, 4), (5, 99)] if ng >= 5 else [(k, k) for k in range(ng)] + [(ng, 99)] if ng else []
        lad = ladder(D, cg, tg, edges) if good else []
        # 걸어가며: 「믿을 만」 고르기까지 그 전 자료로 (해마다 다시 고르고 그 해 계단 확률을 그 전 자료로 계산) → 진짜 표본 밖 계단
        Pl = pd.Series(np.nan, index=D.index)
        for y in range(2008, int(D.date.dt.year.max()) + 1):
            tr = D[D.date < pd.Timestamp(f"{y}-01-01") - pd.Timedelta(days=380 if tg in ("crash", "up12") else 190)]; te = D[D.date.dt.year == y]
            if len(tr) < 5000 or not len(te): continue
            mid = tr.date.iloc[len(tr) // 2] if False else tr.date.quantile(0.5)
            a_, b_ = tr[tr.date < mid], tr[tr.date >= mid]
            gk = [k for k in keys if (a_[k] > .5).sum() >= 100 and (b_[k] > .5).sum() >= 100 and a_.loc[a_[k] > .5, tg].mean() >= 1.15 * a_[tg].mean() and b_.loc[b_[k] > .5, tg].mean() >= 1.15 * b_[tg].mean()]
            if not gk: Pl.loc[te.index] = float(tr[tg].mean()); continue
            ctr, cte = tr[gk].sum(axis=1).clip(upper=4), te[gk].sum(axis=1).clip(upper=4)
            mp = tr.groupby(ctr)[tg].mean(); cnt = tr.groupby(ctr)[tg].size()
            Pl.loc[te.index] = cte.map(lambda c_: float(mp[c_]) if c_ in mp.index and cnt[c_] >= 150 else float(tr[tg].mean())).values
        Pm = walk(D, keys, tg); Pg = walk_gb(D, keys, tg)
        # 지수별 믿을 만한 신호
        per = {}
        for mk_, d in D.groupby("mk"):
            if len(d) < 800: continue
            t2, b2 = sig_table(d.assign(mk=mk_), keys, tg, names)
            per[mk_] = {"base": b2, "top": [{k: x[k] for k in ("k", "name", "share", "p_on", "lift", "lift_a", "lift_b", "episodes")} for x in t2 if not x.get("thin") and x["lift_a"] and x["lift_b"] and x["lift_a"] >= 1.15 and x["lift_b"] >= 1.15][:5]}
        # 지수별 계단: 「믿을 만」 신호가 몇 개 켜졌을 때 그 지수에서 실제 빈도 (표본 150일 미만이면 전체 지수 계단으로)
        mkl = {}
        for mk_, d in D.groupby("mk"):
            c_ = d[good].sum(axis=1) if good else pd.Series(0, index=d.index)
            mkl[mk_] = {int(k): {"p": round(float(d.loc[c_ == k, tg].mean()) * 100), "n": int((c_ == k).sum()), "ep": runs(c_ == k)} for k in sorted(c_.unique()) if (c_ == k).sum() >= 150}
        T = {"title": title, "side": side, "mk_ladder": mkl, "base": base, "n": int(len(D)), "from": str(D.date.min().date()), "signals": tb, "good": good, "ladder_good": lad,
             "oos_ladder": calib(D, Pl, tg), "oos_logit": calib(D, Pm, tg), "oos_gb": calib(D, Pg, tg) if Pg is not None else None, "per_market": per}
        res["targets"][tg] = T; fits[tg] = (D, good, lad, logit_fit(D[keys].values, D[tg].values), keys)
        print(f"\n== {title} · 평소 {base}% · 표본 {len(D)}일")
        for x in tb:
            if x.get("thin"): print(f"      {x['name']:<30} 표본 적음 {x['n']}"); continue
            print(f"   {'✅' if x['good'] else '❌' if x['anti'] else '  '} {x['name']:<30} 켜진 날 {x['share']:>5}% | 켜짐 {x['p_on']:>3}% 꺼짐 {x['p_off']:>3}% · {x['lift']}배 (앞 {x['lift_a']} 뒤 {x['lift_b']}) · 지수 {x['mk_ok']}/{x['mk_n']} · {x['episodes']}번")
        print("   믿을 만 계단:", " | ".join(f"{x['lo']}~{x['hi']}개: {x['p']}% (앞 {x['p_a']} 뒤 {x['p_b']} · {x['share']}%)" for x in lad))
        for nm, k in (("계단(걸어가며)", "oos_ladder"), ("로지스틱", "oos_logit"), ("나무", "oos_gb")):
            M = T[k]
            if M: print(f"   {nm} {M['from']}~ AUC {M['auc']} · 브라이어 {M['brier_skill']} · 구간(예측,실제) {[(b['pred'], b['real']) for b in M['bins']]} · 지수별 {M['auc_by_market']}")
        for mk_, v in per.items():
            if v["top"]: print(f"   [{mk_}] 평소 {v['base']}% →", " · ".join(f"{x['name']} {x['p_on']}%({x['lift_a']}/{x['lift_b']}배·{x['episodes']}번)" for x in v["top"]))
    def lad_p(L, c):
        for x in L:
            if x["lo"] <= c <= x["hi"]: return x["p"]
        return None
    now = []
    for key, (name, nat, r, asof) in last.items():
        o = {"key": key, "name": name, "nat": nat, "asof": asof, "dd": round(float(r["dd"]) * 100, 1), "t": {}}
        for tg, title, keys, names, ddmax, side in TG:
            if ddmax is not None and not (r["dd"] <= ddmax): continue
            D, good, lad, w, _ = fits[tg]
            on = [k for k in good if (r[k] if r[k] == r[k] else 0) > 0.5]
            x = np.nan_to_num(r[keys].values.astype(float))
            pm = res["targets"][tg]["per_market"].get(key) or {}
            ml = (res["targets"][tg]["mk_ladder"].get(key) or {}).get(len(on))
            o["t"][tg] = {"on": on, "n": len(on), "of": len(good), "p": lad_p(lad, len(on)), "p_mk": ml["p"] if ml else None, "p_mk_ep": ml["ep"] if ml else None, "p_model": round(float(logit_pred(w, x[None, :])[0]) * 100), "base": res["targets"][tg]["base"], "base_mk": pm.get("base"),
                          "own_on": [t_["k"] for t_ in (pm.get("top") or []) if (r[t_["k"]] if r[t_["k"]] == r[t_["k"]] else 0) > 0.5]}
        now.append(o)
        print(f"지금 {name} (고점 {o['dd']}%):", " | ".join(f"{tg}: 믿을 만 {v['n']}/{v['of']}개 → 이 지수 {v['p_mk']}%({v['p_mk_ep']}번) 전체 {v['p']}% (모형 {v['p_model']}% · 평소 {v['base']}% · 이 지수 평소 {v['base_mk']}%) 켜짐 {v['on']} 자기신호 {v['own_on']}" for tg, v in o["t"].items()))
    res["now"] = now
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
