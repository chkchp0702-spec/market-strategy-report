"""🔁 닮은 장 백테스트 (11/12 사용자: 「다시 원점 — 현금화·다시 비중 늘리기·단계적으로. 이번엔 지금 장과 유사했던 때들로만 백테스트.
   성격이 다른 장들까지 다 넣으니 확률이 안 올라간 것 같아」)

  결과 보기 전 등록한 것
  ─ 「닮았다」 = 그날의 여섯 숫자가 지금과 가까움 (모든 지수를 한데 모아 표준화한 거리)
       ① 고점 전 급등: 1년 고점 ÷ 2년 전 종가   ② 고점에서 얼마나 빠졌나   ③ 고점 뒤 며칠째   ④ 200일선과의 거리   ⑤ 5년 평균선과의 거리   ⑥ 60일 출렁임
       가중치 ①②⑤ 는 1.5 · 나머지 1
  ─ 찾는 곳: 지수 9개 + 나스닥100 + 반도체 지수(SOX) · 1985년~ · 그 뒤 1년 이상 자료가 남은 날만 · 같은 지수에선 1년 넘게 떨어진 때만 따로 셈
       지수마다 가장 닮은 때 12번(한 지수·한 시기에서 최대 1번) → 「닮은 장」
  ─ 그날부터 2년(없으면 1년) 동안 방식 16개를 돌림 — 현금 연 2% · 바꿀 때 0.1% · 그날 종가 신호 → 다음 날
       그날 기준(닻): 지금 다 삼 · 계속 현금 · 6개월 나눠 사기 · 12개월 나눠 사기 · 더 빠질 때마다 3분의 1(−10·−20·−30%) · 절반 지금+절반 200일선 회복 · 3분의 1씩(지금·50일선·200일선)
       규칙형: 바닥 신호 계단 · 하락장이면 현금(판정 풀리면 주식) · 10개월선 · −10% 절반/−20% 현금 · 10개월선+많이 싸면 절반 · 1년 모멘텀 · 신호 3개 계단 · 200일선 위면 주식 · 50일선 위면 주식
  ─ 보는 것: 닮은 때마다 2년 뒤 수익 → 가운데값 · 평균 · 가장 나빴던 때 · 「계속 현금」보다 나았던 횟수 · 「지금 다 삼」보다 나았던 횟수 · 그 사이 가장 크게 잃은 폭
  ─ 비교: 같은 방식을 「모든 날」에서 돌린 값(닮은 때만 봤을 때 정말 달라지나) · 닮은 때를 8번·20번으로 바꿔도 결론이 같은지
  결과: market/analog.json · 닮은 때가 12번뿐이라 「12번 중 몇 번」으로 읽는다. 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import season_bt as sb   # noqa: E402

KST = sb.KST
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "analog.json"
PX = ROOT / "market" / "lab" / "alt" / "px.csv.gz"
POOL = [("kospi", "^KS11", "코스피", "kr"), ("kosdaq", "^KQ11", "코스닥", "kr"), ("nikkei", "^N225", "닛케이225", "jp"), ("shanghai", "000001.SS", "상해종합", "cn"),
        ("shenzhen", "399001.SZ", "심천성분", "cn"), ("hsi", "^HSI", "항셍", "hk"), ("hscei", "^HSCE", "항셍 H주", "hk"), ("sp500", "^GSPC", "S&P500", "us"), ("nasdaq", "^IXIC", "나스닥", "us"),
        ("ndx", "^NDX", "나스닥100", "us"), ("sox", "^SOX", "반도체 지수", "us")]
TARGETS = [p[0] for p in POOL[:9]]
FW = np.array([1.5, 1.5, 1.0, 1.0, 1.5, 1.0])
FN = ["고점 전 2년 급등", "고점 대비", "고점 뒤 일수", "200일선 대비", "5년 평균선 대비", "60일 출렁임"]
NA = 12; H2, H1 = 504, 252
RN = {"lump": "지금 다 삼", "cash": "계속 현금", "dca6": "6개월 나눠 사기", "dca12": "12개월 나눠 사기", "dip": "더 빠질 때마다 3분의 1씩(−10·−20·−30%)",
      "half200": "절반 지금 + 절반은 200일선 회복 때", "third": "3분의 1씩(지금 · 50일선 위 · 200일선 위)",
      "floor": "하락장엔 현금 → 바닥 신호마다 3분의 1씩", "bear": "하락장(−20%)이면 현금 · 풀리면 주식", "ma10": "10개월선 위면 주식 · 아래면 현금", "ddl": "−10% 절반 · −20% 전부 현금",
      "deep": "10개월선 + 많이 싸면 절반", "mom12": "1년 전보다 높으면 주식", "step3": "신호 3개 계단(0·33·67·100)", "a200": "200일선 위면 주식 · 아래면 현금", "a50": "50일선 위면 주식 · 아래면 현금"}


def feats(s):
    hi = s.rolling(252, min_periods=120).max()
    pos = s.rolling(252, min_periods=120).apply(lambda w: len(w) - 1 - int(np.argmax(w)), raw=True)
    F = pd.DataFrame({"run": np.log(hi / s.shift(504)), "dd": s / hi - 1, "since": pos / 252, "g200": s / s.rolling(200).mean() - 1,
                      "g5": np.log(s / s.rolling(1260, min_periods=900).mean()), "vol": s.pct_change().rolling(60).std() * np.sqrt(252)})
    return F


def policies(s):
    st = sb.seasons(s); c = s.values; n = len(c)
    r = np.zeros(n); r[1:] = c[1:] / c[:-1] - 1
    lr = np.log1p(r); stp = np.roll(st, 1); stp[0] = -1
    first = int(np.argmax(st >= 0))
    W = sb.methods(s, st, lr, stp, first)
    m200, m50 = s.rolling(200).mean().values, s.rolling(50).mean().values
    for k, m in (("a200", m200), ("a50", m50)):
        w = np.where(np.isnan(m), 1.0, (c > m).astype(float)); w = np.roll(w, 1); w[0] = 1; W[k] = w
    return {k: W[k] for k in ("floor", "bear", "ma10", "ddl", "deep", "mom12", "step3", "a200", "a50")}, r, m50, m200


def window(i0, n, r, c, m50, m200, W):
    """i0 = 닮은 날 → {방식: (1년 수익, 2년 수익, 그 사이 최대 낙폭)}"""
    i2 = min(i0 + H2, n - 1); L = i2 - i0
    rr = r[i0 + 1:i2 + 1]; cc = c[i0:i2 + 1]
    ws = {"lump": np.ones(L), "cash": np.zeros(L)}
    for k, mo in (("dca6", 6), ("dca12", 12)):
        ws[k] = np.minimum(1.0, (np.arange(L) // 21 + 1) / mo)
    rel = cc[:-1] / cc[0] - 1
    ws["dip"] = np.maximum.accumulate((rel <= -0.10) / 3 + (rel <= -0.20) / 3 + (rel <= -0.30) / 3)
    a2 = np.maximum.accumulate((cc[:-1] > m200[i0:i2]).astype(float)); a5 = np.maximum.accumulate((cc[:-1] > m50[i0:i2]).astype(float))
    ws["half200"] = 0.5 + 0.5 * a2
    ws["third"] = 1 / 3 + a5 / 3 + a2 / 3
    for k, w in W.items():
        ws[k] = w[i0 + 1:i2 + 1]
    out = {}
    for k, w in ws.items():
        ch = np.abs(np.diff(w, prepend=w[0] if k in W else 0.0))
        d = w * rr + (1 - w) * sb.CASH - sb.COST * ch
        nav = np.cumprod(1 + d)
        out[k] = (round(float(nav[min(H1, L) - 1] - 1) * 100, 1), round(float(nav[-1] - 1) * 100, 1) if L >= H2 else None, round(float((nav / np.maximum.accumulate(nav) - 1).min()) * 100, 1))
    return out


def summarize(vals):
    """vals: [(1y, 2y, mdd)] → 통계 (2년 없으면 1년으로)"""
    y1 = np.array([v[0] for v in vals], float); y2 = np.array([v[1] if v[1] is not None else np.nan for v in vals], float); md = np.array([v[2] for v in vals], float)
    f = lambda a, fn: None if np.all(np.isnan(a)) else round(float(fn(a[~np.isnan(a)])), 1)
    return {"n": len(vals), "n2": int((~np.isnan(y2)).sum()), "y1_med": f(y1, np.median), "y1_avg": f(y1, np.mean), "y2_med": f(y2, np.median), "y2_avg": f(y2, np.mean), "y2_worst": f(y2, np.min), "y1_worst": f(y1, np.min),
            "mdd_avg": f(md, np.mean), "mdd_worst": f(md, np.min)}


# ───────── 🔁 규칙 채택 (11/12 사용자 「1번 · 미국 일본 중국도 다 같은 방식」) ─────────
# 고르는 법(등록): 닮은 때 2년 수익의 가운데값이 가장 높은 방식.
#   · 하나 빼고 고르기(닮은 때 11번으로 고르고 남은 1번에 적용 × 12)의 가운데값이 「계속 현금」(2년 약 4%)보다 낮으면 → 「통하는 방식 없음」(규칙 안 바꿈)
#   · 고른 게 「지금 다 삼」인데 지금 하락장(고점 −20% 아래)이면 → 「절반 지금 + 절반은 200일선 회복 때」(사용자 「단계적으로」)
#   · 한 번 고른 방식은 표에서 3등 안에 있는 동안 그대로(날마다 바뀌지 않게) · 닻(시작 날)도 그대로
# ⚠ 이 고르는 법은 닮은 장 결과를 본 뒤에 정함 — 그래서 「하나 빼고 고르기」 숫자를 함께 적음
PICK = ROOT / "market" / "analog_pick.json"
CASH2 = round(((1 + sb.CASH) ** H2 - 1) * 100, 1)
ANCH = ("lump", "cash", "dca6", "dca12", "dip", "half200", "third")


def choose(rows, idx=None):
    best = None
    for r_ in rows:
        v = np.array([np.nan if x is None else x for x in r_["each"]], float)
        if idx is not None:
            v = v[idx]
        sc = float(np.nanmedian(v))
        if best is None or sc > best[0]:
            best = (sc, r_["k"])
    return best[1]


def loo(rows):
    R = {r_["k"]: np.array([np.nan if x is None else x for x in r_["each"]], float) for r_ in rows}
    n = len(R["lump"])
    v = np.array([R[choose(rows, np.array([j for j in range(n) if j != i]))][i] for i in range(n)])
    return {"med": round(float(np.nanmedian(v)), 1), "worst": round(float(np.nanmin(v)), 1), "beat_cash": int((v > CASH2).sum()), "n": n}


def weight_now(k, s, anchor):
    """오늘 종가로 정한 내일 주식 몫(0~1) + 다음에 바뀌는 조건 글자"""
    c = s.values; m50 = float(s.rolling(50).mean().iloc[-1]); m200 = float(s.rolling(200).mean().iloc[-1]); hi = float(s.iloc[-252:].max())
    f = lambda x: f"{x:,.0f}" if x >= 1000 else f"{x:,.1f}"
    if k not in ANCH:
        s2 = pd.concat([s, pd.Series([c[-1]], index=[s.index[-1] + pd.offsets.BDay(1)])])
        w = float(policies(s2)[0][k][-1])
        nx = {"a50": f"50일선({f(m50)}) " + ("아래로 내려가면 현금" if w else "위로 올라오면 주식"), "a200": f"200일선({f(m200)}) " + ("아래로 내려가면 현금" if w else "위로 올라오면 주식"),
              "ma10": "월말 종가가 10개월선 " + ("아래면 현금" if w else "위면 주식"), "bear": (f"고점 −20%({f(hi * 0.8)}) 아래로 내려가면 현금" if w else "하락장 판정이 풀리면 주식"),
              "floor": ("하락장(고점 −20%) 되면 현금" if w >= 1 else "바닥 신호가 켜질 때마다 3분의 1씩 주식"), "ddl": f"고점 −10%({f(hi * 0.9)}) 절반 · −20%({f(hi * 0.8)}) 전부 현금"}.get(k, RN[k])
        return w, nx
    i0 = s.index.get_indexer([pd.Timestamp(anchor)], method="nearest")[0]
    cc = c[i0:]; L = len(cc)
    a2 = float((cc > s.rolling(200).mean().values[i0:]).any()); a5 = float((cc > s.rolling(50).mean().values[i0:]).any())
    rel = cc / cc[0] - 1
    if k == "lump":
        return 1.0, "그대로 보유"
    if k == "cash":
        return 0.0, "닮은 장 결과가 바뀔 때까지 현금"
    if k in ("dca6", "dca12"):
        mo = 6 if k == "dca6" else 12; w = min(1.0, ((L - 1) // 21 + 1) / mo)
        return w, f"한 달(21거래일)마다 {mo}분의 1씩 더 — 지금 {min(mo, (L - 1) // 21 + 1)}/{mo}번째"
    if k == "dip":
        w = float(((rel <= -0.10).any() + (rel <= -0.20).any() + (rel <= -0.30).any()) / 3)
        return w, f"시작한 날({anchor} · {f(cc[0])})보다 −10·−20·−30% 빠질 때마다 3분의 1씩"
    if k == "half200":
        return 0.5 + 0.5 * a2, ("그대로 보유" if a2 else f"200일선({f(m200)}) 위로 올라오면 나머지 절반도 주식")
    w = 1 / 3 + a5 / 3 + a2 / 3
    return w, ("그대로 보유" if a5 and a2 else "50일선(" + f(m50) + ") · 200일선(" + f(m200) + ") 위로 올라올 때마다 3분의 1씩 더")


def adopt(res, S):
    old = {}
    try:
        old = {m["key"]: m for m in json.loads(PICK.read_text(encoding="utf-8")).get("markets", [])}
    except Exception:
        pass
    out = {"at": res["at"], "cash2": CASH2, "markets": []}; res["cash2"] = CASH2
    for M in res["markets"]:
        rows = M["rules"]; key = M["key"]; s = S[key]; L = {r_["k"]: r_ for r_ in rows}
        k = choose(rows); lo = loo(rows); ok = lo["med"] > CASH2
        staged = False
        if k == "lump" and M["now"]["dd"] <= -20:
            k = "half200"; staged = True
        o = old.get(key) or {}
        top3 = [r_["k"] for r_ in rows[:3]]
        if o.get("k") and o.get("ok") and ok and o["k"] in L and (o["k"] in top3 or (o.get("staged") and "lump" in top3)):
            k = o["k"]; staged = bool(o.get("staged"))
        anchor = o.get("anchor") if o.get("k") == k and o.get("anchor") else str(s.index[-1].date())
        w, nx = weight_now(k, s, anchor)
        r_ = L[k]
        P = {"key": key, "name": M["name"], "nat": M["nat"], "k": k, "rule": RN[k], "ok": bool(ok), "staged": staged, "anchor": anchor, "asof": str(s.index[-1].date()),
             "stock": int(round(w * 100)), "cash": int(round((1 - w) * 100)), "next": nx, "loo": lo,
             "y2_med": r_["y2_med"], "y2_worst": r_["y2_worst"], "beat_cash": r_["beat_cash"], "n": r_["n"], "lump_med": L["lump"]["y2_med"], "lump_worst": L["lump"]["y2_worst"],
             "fwd": {x: M["fwd"][x] for x in ("more10", "more_med", "y1_up", "n")}}
        M["pick"] = P; out["markets"].append(P)
        print(f"🔁 {M['name']}: {RN[k]} → 주식 {P['stock']}% · {nx} | 하나 빼고 고르기 가운데 {lo['med']}% 최악 {lo['worst']}% 현금보다 {lo['beat_cash']}/{lo['n']} {'✅' if ok else '❌ 통하는 방식 없음'}")
    PICK.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


def main():
    px0 = pd.read_csv(PX, index_col=0, parse_dates=True)
    S, Fz, Pol = {}, {}, {}
    for key, sym, name, nat in POOL:
        s = px0[sym].dropna(); s = s[s > 0]
        S[key] = s; Fz[key] = feats(s)
        Pol[key] = policies(s)
    allF = pd.concat([Fz[k].dropna() for k in Fz])
    mu, sd = allF.mean().values, allF.std().values
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "rule_names": RN, "feat_names": FN, "markets": []}
    NM = {p[0]: (p[2], p[3]) for p in POOL}
    # 모든 날 기준(비교용): 지수마다 21일 간격으로 시작한 창
    ALL = {}
    for key in S:
        s = S[key]; W, r, m50, m200 = Pol[key]; n = len(s); c = s.values
        ok = Fz[key].dropna().index
        i_ok = [s.index.get_loc(d) for d in ok[::21] if s.index.get_loc(d) + H1 < n]
        ALL[key] = [window(i, n, r, c, m50, m200, W) for i in i_ok]
    def one(tk, na, quiet=False):
        now = Fz[tk].dropna().iloc[-1]; zn = (now.values - mu) / sd
        cands = []
        for key in S:
            F = Fz[key].dropna(); s = S[key]
            z = (F.values - mu) / sd
            dist = np.sqrt((((z - zn) * FW) ** 2).sum(axis=1) / FW.sum())
            pos = np.array([s.index.get_loc(d) for d in F.index])
            m = pos + H1 < len(s)
            if key == tk: m &= pos < len(s) - H2        # 자기 지수의 최근 2년은 빼기(지금 장 자체)
            d_, p_ = dist[m], pos[m]
            order = np.argsort(d_); took = []
            for j in order[:4000]:
                if all(abs(p_[j] - t) > 252 for t in took):
                    took.append(p_[j]); cands.append((float(d_[j]), key, int(p_[j])))
                if len(took) >= 4: break
        cands.sort()
        picked = []
        for dist_, key, p in cands:   # 같은 시기(±9개월)에 여러 지수가 겹치면 지수 국적이 다를 때만 최대 3개
            d0 = S[key].index[p]
            same = [x for x in picked if abs((S[x[1]].index[x[2]] - d0).days) < 270]
            if any(x[1] == key for x in same) or len(same) >= 3: continue
            picked.append((dist_, key, p))
            if len(picked) >= na: break
        eps, per = [], {k: [] for k in RN}
        for dist_, key, p in picked:
            s = S[key]; W, r, m50, m200 = Pol[key]; c = s.values; n = len(s)
            w = window(p, n, r, c, m50, m200, W)
            for k in RN: per[k].append(w[k])
            i2 = min(p + H2, n - 1); seg = c[p:i2 + 1]; f = Fz[key].iloc[Fz[key].index.get_loc(s.index[p])]
            eps.append({"mk": key, "name": NM[key][0], "nat": NM[key][1], "date": str(s.index[p].date()), "dist": round(dist_, 2),
                        "run": round(float(np.expm1(f["run"])) * 100), "dd": round(float(f["dd"]) * 100, 1), "since": int(round(f["since"] * 252)), "g200": round(float(f["g200"]) * 100, 1), "g5": round(float(np.expm1(f["g5"])) * 100),
                        "more": round(float(seg.min() / seg[0] - 1) * 100, 1), "to_low": int(np.argmin(seg)), "y1": w["lump"][0], "y2": w["lump"][1],
                        "path": [round(float(x / seg[0] - 1) * 100, 1) for x in seg[::21]]})
        rows = []
        lump2 = [v[1] if v[1] is not None else v[0] for v in per["lump"]]; cash2 = [v[1] if v[1] is not None else v[0] for v in per["cash"]]
        for k in RN:
            v2 = [v[1] if v[1] is not None else v[0] for v in per[k]]
            st_ = summarize(per[k]); al = summarize([w[k] for w in ALL[tk]])
            st_.update({"k": k, "name": RN[k], "beat_cash": int(sum(a > b + 0.5 for a, b in zip(v2, cash2))), "beat_lump": int(sum(a > b + 0.5 for a, b in zip(v2, lump2))),
                        "all_y2_med": al["y2_med"], "all_y1_med": al["y1_med"], "each": v2})
            rows.append(st_)
        rows.sort(key=lambda x: -(x["y2_med"] if x["y2_med"] is not None else -999))
        more = np.array([e["more"] for e in eps]); tl = np.array([e["to_low"] for e in eps])
        fwd = {"more_med": round(float(np.median(more)), 1), "more10": int((more <= -10).sum()), "more20": int((more <= -20).sum()), "to_low_med": int(np.median(tl)),
               "y1_up": int(sum(e["y1"] > 0 for e in eps)), "y2_up": int(sum((e["y2"] if e["y2"] is not None else e["y1"]) > 0 for e in eps)), "n": len(eps)}
        nowd = {"run": round(float(np.expm1(now["run"])) * 100), "dd": round(float(now["dd"]) * 100, 1), "since": int(round(now["since"] * 252)), "g200": round(float(now["g200"]) * 100, 1), "g5": round(float(np.expm1(now["g5"])) * 100), "vol": round(float(now["vol"]) * 100)}
        M = {"key": tk, "name": NM[tk][0], "nat": NM[tk][1], "now": nowd, "episodes": eps, "fwd": fwd, "rules": rows}
        if quiet:
            L = {r_["k"]: r_ for r_ in rows}
            return {"n": na, "fwd": fwd, "top": [[r_["k"], r_["y2_med"]] for r_ in rows[:3]], "lump": [L["lump"]["y2_med"], L["lump"]["beat_cash"]]}
        print(f"\n== {NM[tk][0]} 지금: 고점 전 2년 +{nowd['run']}% · 고점 대비 {nowd['dd']}% · 고점 뒤 {nowd['since']}일 · 200일선 {nowd['g200']:+}% · 5년 평균선 {nowd['g5']:+}% · 출렁임 {nowd['vol']}%")
        print("   닮은 때:", " | ".join(f"{e['name']} {e['date'][:7]}(급등 +{e['run']}% · {e['dd']}% · 거리 {e['dist']}) → 더 {e['more']}% · 1년 {e['y1']}% · 2년 {e['y2']}%" for e in eps))
        print(f"   그 뒤: 더 빠진 폭 가운데값 {fwd['more_med']}% · −10% 더 {fwd['more10']}/{fwd['n']}번 · −20% 더 {fwd['more20']}/{fwd['n']}번 · 바닥까지 {fwd['to_low_med']}일 · 1년 뒤 플러스 {fwd['y1_up']}번 · 2년 뒤 플러스 {fwd['y2_up']}번")
        for x in rows:
            print(f"   {x['name']:<34} 2년 가운데 {x['y2_med']:>6}% 평균 {x['y2_avg']:>6}% 최악 {x['y2_worst']:>6}% · 1년 가운데 {x['y1_med']:>6}% · 현금보다 {x['beat_cash']:>2}/{x['n']} · 다 삼보다 {x['beat_lump']:>2}/{x['n']} · 낙폭 평균 {x['mdd_avg']}% | 모든 날 2년 {x['all_y2_med']}%")
        return M
    for tk in TARGETS:
        M = one(tk, NA)
        M["sens"] = [one(tk, 8, True), one(tk, 20, True)]   # 닮은 때를 8번·20번으로 바꿔도 결론이 같은지
        res["markets"].append(M)
    adopt(res, S)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
