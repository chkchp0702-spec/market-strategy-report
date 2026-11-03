"""📈 11/3 14시 — ⚡ 킥 「🔗 미국→한국 선행」 신호의 첫 장기(2008~) 검증
  킥에 실제로 켜져 있는 🔗(우선순위 20) 은 지금 「최근 79일 상관」만 보고 들어감 — 2008~ 검증이 한 번도 없었음.
  규칙(지금 실전): 미국 테마 ETF 하루 +1.5%↑ · (ETF 미국일 수익 ↔ 한국 연결주 다음 한국일 수익) 상관 ≥0.3 ·
  테마 「초입·주도」 → 한국 연결주 상위 2개를 다음 한국 거래일 종가에 삼.
  여기서: 초입·주도 대용 = ETF 가 20일선 위 & 20일 S&P 대비 강함. 상관 = 지난 80개 짝(과거만).
  E1 = 미국일 다음 첫 한국 거래일 종가 진입(지금 규칙) · E2 = 그다음 한국일 종가(하루 늦게).
  출구: 킥 규칙(손절 −5% · 익절 +15% · 15일째 +3% 못 넘으면 정리 · 최대 40일) 과 고정 보유 5·10·15일.
  비교 = 같은 기간 코스피(^KS11) — 「초과」. 비용 왕복 0.45%.
  2008-07~2016 에서 손잡이 고르고 2017~ 시험 · ±20% 이웃.
  생존 편향: 연결주 목록 = 오늘 market/sectors.json (오늘 살아 있고 오늘 테마와 엮인 종목) → 위로 치우침.
→ market/lab/k1103_lead.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
from src.kick_ideas_bt import ydl
from src.conc_bt import START, IS_END, OOS_START

OUT = Path("market/lab/k1103_lead.json")
COST = 0.0045


def kick_exit(c: np.ndarray, i0: int):
    """c = 종가 배열, i0 = 진입 위치 → (나간 위치, 수익)"""
    p0 = c[i0]
    for j in range(i0 + 1, min(i0 + 41, len(c))):
        r = c[j] / p0 - 1
        if r <= -0.05 or r >= 0.15:
            return j, r
        if j - i0 == 15 and r < 0.03:
            return j, r
    j = min(i0 + 40, len(c) - 1)
    return j, c[j] / p0 - 1


def main():
    S = json.loads(Path("market/sectors.json").read_text(encoding="utf-8"))
    MAP = {}
    for r in S["rows"]:
        kr = [x["t"] for x in (r.get("members") or {}).get("kr", [])][:6]
        if kr:
            MAP[r["sym"]] = kr
    krs = sorted({k for v in MAP.values() for k in v})
    px = ydl(list(MAP) + ["SPY"], start="2007-01-01")
    kx = ydl(krs + ["^KS11"], start="2007-01-01")
    spy = px["SPY"]["close"]
    ks = kx["^KS11"]["close"]
    kidx = ks.index
    events = []   # 사건 하나 = (미국일, ETF, 한국 종목, r1, cor, stage)
    for sym, kl in MAP.items():
        if sym not in px:
            continue
        e = px[sym]["close"]
        er = e.pct_change()
        ma20 = e.rolling(20).mean()
        rs20 = (e / e.shift(20)) / (spy.reindex(e.index).ffill() / spy.reindex(e.index).ffill().shift(20)) - 1
        # 미국일 d → 다음 첫 한국 거래일 위치
        pos = kidx.searchsorted(e.index, side="right")
        for t in kl:
            if t not in kx:
                continue
            k = kx[t]["close"].reindex(kidx)
            kr1 = k.pct_change()
            ok = pos < len(kidx)
            nxt = pd.Series(np.nan, index=e.index)
            nxt[ok] = kr1.values[pos[ok]]
            # 과거 80짝 상관 — 그날(d) 의 다음 한국일 수익은 아직 모름 → shift(1)
            cor = er.rolling(80, min_periods=60).corr(nxt).shift(1)
            for i in np.where((er >= 0.01).values & ok)[0]:
                d = e.index[i]
                if d < pd.Timestamp("2008-07-01"):
                    continue
                p = pos[i]
                if np.isnan(k.values[p]) if p < len(k) else True:
                    continue
                events.append(dict(d=d, sym=sym, t=t, r1=float(er.iloc[i]), cor=float(cor.iloc[i]) if not np.isnan(cor.iloc[i]) else -9,
                                   stage=bool(e.iloc[i] > ma20.iloc[i] and rs20.iloc[i] > 0), p=int(p),
                                   gap=float(kr1.values[p]) if p < len(kr1) else np.nan))
    print("사건", len(events))
    kc = {t: kx[t]["close"].reindex(kidx).ffill().values for t in krs if t in kx}
    ksv = ks.values

    E = pd.DataFrame(events)
    E["ti"] = E["t"].map({t: i for i, t in enumerate(sorted(kc))})
    M = np.vstack([kc[t] for t in sorted(kc)])          # 종목 × 날짜 종가
    L = M.shape[1]
    kdates = np.array([str(x.date()) for x in kidx])
    PRE = {}
    for ent in (0, 1):
        i0 = (E["p"].values + ent).clip(max=L - 1)
        F = np.full((len(E), 41), np.nan)
        for h in range(41):
            F[:, h] = M[E["ti"].values, np.minimum(i0 + h, L - 1)]
        R = F / F[:, :1] - 1
        K = np.full((len(E), 41), np.nan)
        for h in range(41):
            K[:, h] = ksv[np.minimum(i0 + h, L - 1)]
        KR = K / K[:, :1] - 1
        valid = (~np.isnan(F[:, 0])) & (i0 < L - 2)
        for hold in ("kick", 5, 10, 15):
            if hold == "kick":
                hit = (R[:, 1:] <= -0.05) | (R[:, 1:] >= 0.15)
                hit[:, 14] |= R[:, 15] < 0.03
                hit[:, 39] = True
                j = hit.argmax(axis=1) + 1
            else:
                j = np.full(len(E), hold)
            j = np.minimum(j, L - 1 - i0)
            r = R[np.arange(len(E)), j]; m = KR[np.arange(len(E)), j]
            PRE[(ent, hold)] = pd.DataFrame({"r": r - COST, "x": r - COST - m, "days": j, "ent": kdates[i0], "ok": valid & ~np.isnan(r)})
    E["rank"] = E.groupby(["d", "sym"])["cor"].rank(ascending=False, method="first")

    def run(r1min, cormin, stage, ent, hold, top=2):
        msk = (E["r1"].values >= r1min) & (E["cor"].values >= cormin) & (E["stage"].values | (not stage))
        sub = E[msk].copy()
        sub["rk"] = sub.groupby(["d", "sym"])["cor"].rank(ascending=False, method="first")
        sub = sub[sub["rk"] <= top].drop_duplicates(["t", "p"])
        P = PRE[(ent, hold)].loc[sub.index]
        P = P[P["ok"]]
        return [{"ent": e, "r": a, "x": b, "days": int(c)} for e, a, b, c in zip(P["ent"], P["r"], P["x"], P["days"])]

    def st(tr, lo, hi):
        T = [x for x in tr if lo <= x["ent"] <= hi]
        if not T:
            return {"n": 0}
        x = np.array([t["x"] for t in T]); r = np.array([t["r"] for t in T])
        w, l = r[r > 0].sum(), -r[r < 0].sum()
        yrs = {}
        for t in T:
            yrs.setdefault(t["ent"][:4], []).append(t["x"])
        by = max(yrs, key=lambda y: np.mean(yrs[y]))
        return {"n": len(T), "avg": round(r.mean() * 100, 2), "x": round(x.mean() * 100, 2), "x_med": round(float(np.median(x)) * 100, 2),
                "win": round((r > 0).mean() * 100), "pf": round(w / l, 2) if l > 0 else None,
                "yr_pos": f"{sum(np.mean(v) > 0 for v in yrs.values())}/{len(yrs)}",
                "x_wo_best_yr": round(float(np.mean([v for y, L in yrs.items() if y != by for v in L])) * 100, 2) if len(yrs) > 1 else None}

    IS = ("2008-07-01", IS_END); OOS = (OOS_START, "2099-12-31")
    res = {}
    for r1 in (0.01, 0.015, 0.02, 0.03):
        for cm in (-9, 0.1, 0.2, 0.3, 0.4):
            for sg in (False, True):
                for ent in (0, 1):
                    for hold in ("kick", 5, 10, 15):
                        tr = run(r1, cm, sg, ent, hold)
                        key = f"r{r1}_c{cm}_s{int(sg)}_E{ent + 1}_H{hold}"
                        res[key] = {"is": st(tr, *IS), "oos": st(tr, *OOS)}
    live = "r0.015_c0.3_s1_E1_Hkick"
    cand = [k for k, v in res.items() if v["is"].get("n", 0) >= 60]
    best = max(cand, key=lambda k: res[k]["is"]["x"]) if cand else None
    # ±20% 이웃 (r1·상관·보유)
    neigh = {}
    if best:
        b = best.split("_")
        r1 = float(b[0][1:]); cm = float(b[1][1:]); sg = b[2]; en = b[3]; hd = b[4]
        for f in (0.8, 1.2):
            for k2 in (f"r{round(r1 * f, 4)}_c{b[1][1:]}_{sg}_{en}_{hd}", f"r{b[0][1:]}_c{round(cm * f, 3) if cm > 0 else cm}_{sg}_{en}_{hd}"):
                pr = k2.split("_")
                tr = run(float(pr[0][1:]), float(pr[1][1:]), pr[2] == "s1", int(pr[3][1:]) - 1, pr[4][1:] if pr[4][1:] == "kick" else int(pr[4][1:]))
                neigh[k2] = {"is": st(tr, *IS), "oos": st(tr, *OOS)}
    # 한국 첫날 갭(진입 전에 이미 반영된 몫) 대 진입 뒤 몫
    gap_is = [e["gap"] for e in events if e["r1"] >= 0.015 and e["cor"] >= 0.3 and str(e["d"].date()) <= IS_END and not np.isnan(e["gap"])]
    gap_oos = [e["gap"] for e in events if e["r1"] >= 0.015 and e["cor"] >= 0.3 and str(e["d"].date()) >= OOS_START and not np.isnan(e["gap"])]
    # 슬롯 모의: 🔗 이 2칸(각 전체의 3%) 을 늘 가진다고 치면 킥 포트 기여(연 %p, 코스피 초과·비용 뒤)
    def slots(key, nslot=2, w=0.03):
        pr = key.split("_")
        tr = run(float(pr[0][1:]), float(pr[1][1:]), pr[2] == "s1", int(pr[3][1:]) - 1, pr[4][1:] if pr[4][1:] == "kick" else int(pr[4][1:]))
        tr = sorted(tr, key=lambda t: t["ent"])
        busy, tot = [], {"is": [0, 0.0, 0.0], "oos": [0, 0.0, 0.0]}
        for t in tr:
            busy = [b for b in busy if b > t["ent"]]
            if len(busy) >= nslot:
                continue
            ex = kidx[min(kidx.searchsorted(pd.Timestamp(t["ent"])) + t["days"], len(kidx) - 1)]
            busy.append(str(ex.date()))
            g = "is" if t["ent"] <= IS_END else "oos"
            tot[g][0] += 1; tot[g][1] += t["r"] * w; tot[g][2] += t["x"] * w
        yrs = {"is": 8.5, "oos": (kidx[-1] - pd.Timestamp(OOS_START)).days / 365.25}
        return {g: {"n": v[0], "abs_pp_yr": round(v[1] / yrs[g] * 100, 2), "x_pp_yr": round(v[2] / yrs[g] * 100, 2)} for g, v in tot.items()}

    out = {"made": pd.Timestamp.now().isoformat(), "n_events": len(events), "n_etf": len(MAP), "n_kr": len(kc),
           "live": {"key": live, **res[live]}, "live_slots": slots(live),
           "best_is": {"key": best, **(res[best] if best else {})}, "best_slots": slots(best) if best else None, "neigh": neigh,
           "gap_kr_day1": {"is": round(float(np.mean(gap_is)) * 100, 2) if gap_is else None, "oos": round(float(np.mean(gap_oos)) * 100, 2) if gap_oos else None},
           "all": res,
           "note": "생존 편향: 오늘 sectors.json 연결주(오늘 살아 있는 종목) · 상관 = 과거 80짝 · 초입·주도 대용 = 20일선 위 & 20일 S&P 대비 강함 · 비용 왕복 0.45% · 초과 = 같은 날짜 코스피"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: out[k] for k in ("n_events", "live", "live_slots", "best_is", "best_slots", "neigh", "gap_kr_day1")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
