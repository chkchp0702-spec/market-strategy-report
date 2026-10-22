"""🌙 10/22 밤 연구 #12 — 🌃 밤사이 보유: 한국 모멘텀 종목을 「종가에 사서 → 다음 날 시가에 팔기」가 장중 단타보다 나은가
  배경: 모멘텀 수익은 밤사이(종가→시가)에 쌓이고 장중에는 되돌려진다는 연구(Lou·Polk·Skouras 2019 「A tug of war」).
        우리 단타 알람(stock-screener)은 실전 128건 승률 약 37%·비용 0.45% 뺀 평균 약 −1.2%, 9시대 진입이 가장 나쁨.
  ① 실전 알람 직접 비교: tracking.csv 의 알람마다 알람일 종가→다음 날 시가(A)·종가→다음 날 종가(C)·알람가→다음 날 시가 를 계산해
     장중 결과(현재 = 알람가 대비 그날 종가 %)와 나란히 놓음.
  ② 본 시험: universe_latest.csv 약 466종목(코스피 .KS · 코스닥 .KQ) 일봉 2023-01~ (야후)
     신호일 = 등락률 lo~hi% · 거래량 ≥ 20일 평균 × m · (켬이면) 종가가 그날 고저 범위 위 30% 안
     손잡이: 등락 {2~5, 3~8, 3~15, 5~15}% × 거래 배수 {1.5, 2, 3} × 고가 근처 종가 {켬, 끔} = 24조합
     결과(신호 하나당): A 종가→다음 날 시가(밤) · B 다음 날 시가→종가(장중) · C 종가→다음 날 종가
     비용 왕복 0.45%(증권거래세+수수료+미끄러짐, 0.25% 민감도 함께) · 비교 기준 = 모든 종목·모든 날 조건 없이(기저율)
     날짜 앞 60% = 고르기(평균 순수익 A, n≥100) · 뒤 40% = 시험 — 시험 구간 n·승률·평균·손익비, 해마다·시장별
     겹침: 하루 평균 신호 수 · 그날 신호를 같은 비중으로 담은 「하루 포트」 A (같은 날 몰린 신호를 여러 번 세지 않게)
  판정: ✅ = 시험 구간 A 순 평균 > 0 · 손익비 ≥ 1.3 · n ≥ 200 · 이웃 조합(한 손잡이만 바꾼 것)도 모두 플러스 / 아니면 ➖·❌
  한계: 유니버스가 「오늘」 목록이라 살아남은 종목 편향 · 신호가 그날 종가로 정해지는데 그 종가에 산다고 가정(실전은 15:20 동시호가 직전 값으로 판단)
        · 야후 한국 일봉 시가 품질(거래정지·0 시가는 뺌) · 매수 추천 아님
→ market/lab/k1022_overnight.json
"""
from __future__ import annotations
import datetime as dt
import io
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("market/lab/k1022_overnight.json")
RAW = "https://raw.githubusercontent.com/chkchp0702-spec/stock-screener/main/data/"
START = "2023-01-01"
COST, COST2 = 0.0045, 0.0025
BANDS = [(2, 5), (3, 8), (3, 15), (5, 15)]
VMS = [1.5, 2.0, 3.0]
CNH = [True, False]
TOP = 0.70           # 종가가 고저 범위 위 30% 안
IS_FRAC = 0.60
MIN_IS = 100
CHUNK = 50
QUESTION = "한국 모멘텀 종목(급등+거래 급증)을 종가에 사서 다음 날 시가에 파는 「밤사이 보유」가 장중 단타보다 나은가"


def fetch_csv(name):
    req = urllib.request.Request(RAW + name, headers={"User-Agent": "ch-lab"})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
    return pd.read_csv(io.BytesIO(b), encoding="utf-8-sig", dtype={"code": str})


def _one(df, t, multi):
    if multi:
        if t not in df.columns.get_level_values(0):
            return None
        sub = df[t]
    else:
        sub = df
    need = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in sub.columns for c in need):
        return None
    sub = sub[need].copy()
    sub = sub.dropna(subset=["Close"])
    return sub if len(sub) else None


def download(tickers, start=START):
    """50개씩 나눠 받기 · 실패하면 한 번 더 · 그래도 실패하면 그 묶음은 건너뜀"""
    got, fail = {}, []
    for k in range(0, len(tickers), CHUNK):
        ch = tickers[k:k + CHUNK]
        df = None
        for attempt in range(2):
            try:
                df = yf.download(ch, start=start, interval="1d", auto_adjust=True, progress=False,
                                 group_by="ticker", threads=True)
                if df is not None and len(df):
                    break
            except Exception as e:  # noqa: BLE001
                print("받기 실패", k, attempt, repr(e)[:120])
                df = None
            time.sleep(2)
        if df is None or not len(df):
            fail += ch
            continue
        multi = isinstance(df.columns, pd.MultiIndex)
        for t in ch:
            s = _one(df, t, multi or len(ch) > 1)
            if s is None:
                fail.append(t)
            else:
                got[t] = s
        print("받음", k + len(ch), "/", len(tickers), "누적", len(got))
    return got, fail


def clean(s):
    s = s.copy()
    bad = (s["Open"] <= 0) | (s["Volume"] <= 0) | (s["High"] <= 0) | (s["Low"] <= 0)
    s.loc[bad, ["Open", "High", "Low", "Close", "Volume"]] = np.nan   # 거래정지·빈 날
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated(keep="last")]


def long_table(px, mkt):
    rows = []
    for t, s in px.items():
        s = clean(s)
        if s["Close"].notna().sum() < 60:
            continue
        O, H, L, C, V = s["Open"], s["High"], s["Low"], s["Close"], s["Volume"]
        ret = (C / C.shift(1) - 1) * 100
        avgv = V.shift(1).rolling(20, min_periods=15).mean()
        rng = H - L
        cpos = ((C - L) / rng.where(rng > 0)).where(rng > 0, np.where(ret > 0, 1.0, 0.0))
        A = O.shift(-1) / C - 1
        B = C.shift(-1) / O.shift(-1) - 1
        Cc = C.shift(-1) / C - 1
        d = pd.DataFrame({"ret": ret, "vm": V / avgv, "cpos": cpos, "A": A, "B": B, "C": Cc})
        d = d.dropna(subset=["ret", "A", "B", "C"])
        # 이상치(액면분할 등 수정 누락) 빼기: 하루 ±35% 넘는 결과
        d = d[(d[["A", "B", "C"]].abs() < 0.35).all(axis=1)]
        d["tk"] = t
        d["mkt"] = mkt.get(t, "?")
        rows.append(d)
    L_ = pd.concat(rows)
    L_.index.name = "date"
    return L_.reset_index()


def st(x):
    x = pd.Series(x, dtype=float).dropna()
    if not len(x):
        return {"n": 0}
    w, l = x[x > 0], x[x <= 0]
    return {"n": int(len(x)), "win": round(float((x > 0).mean()) * 100, 1), "avg": round(float(x.mean()) * 100, 3),
            "med": round(float(x.median()) * 100, 3),
            "pf": round(float(w.sum() / -l.sum()), 2) if len(l) and l.sum() < 0 else None}


def outcomes(d, cost=COST):
    return {k: st(d[k] - cost) for k in ("A", "B", "C")}


def sig_mask(T, band, vm, cnh):
    m = (T["ret"] >= band[0]) & (T["ret"] <= band[1]) & (T["vm"] >= vm)
    if cnh:
        m &= T["cpos"] >= TOP
    return m


def daily_port(d, cost=COST):
    """그날 신호를 같은 비중으로 담은 하루 포트 (A: 종가→다음 날 시가)"""
    if not len(d):
        return {}
    g = d.groupby("date")
    r = g["A"].mean() - cost
    cnt = g.size()
    out = st(r)
    out["days"] = out.pop("n")
    out["sig_per_day_avg"] = round(float(cnt.mean()), 2)
    out["sig_per_day_max"] = int(cnt.max())
    out["t"] = round(float(r.mean() / (r.std() / math.sqrt(len(r)))), 2) if len(r) > 2 and r.std() > 0 else None
    out["cum"] = round(float((1 + r).prod() - 1) * 100, 1)
    return out


def by_group(d, key):
    out = {}
    for k, g in d.groupby(key):
        out[str(k)] = {"n": int(len(g)), "A": st(g["A"] - COST).get("avg"), "B": st(g["B"] - COST).get("avg"),
                       "C": st(g["C"] - COST).get("avg"), "A_win": st(g["A"] - COST).get("win")}
    return out


def alarms_check(trk, px):
    """실전 알람: 장중 결과(현재) vs 그날 종가→다음 날 시가 / 다음 날 종가"""
    rows = []
    for _, a in trk.iterrows():
        code = str(a["code"]).zfill(6)
        s = None
        for suf in (".KS", ".KQ"):
            if code + suf in px:
                s = clean(px[code + suf]); break
        if s is None:
            continue
        try:
            d0 = pd.Timestamp(str(a["시각"])[:8])
        except Exception:
            continue
        if d0 not in s.index:
            continue
        k = s.index.get_loc(d0)
        if k + 1 >= len(s):
            continue
        c0, o1, c1 = s["Close"].iloc[k], s["Open"].iloc[k + 1], s["Close"].iloc[k + 1]
        ap = float(a["알람가"]) if pd.notna(a.get("알람가")) else np.nan
        if not (c0 > 0 and o1 > 0 and c1 > 0 and ap > 0):
            continue
        if abs(c0 / ap - 1) > 0.35:          # 알람가와 야후 종가가 안 맞음(수정주가 등) → 뺌
            continue
        hh = str(a["시각"])[9:11]
        rows.append({"t": str(a["시각"]), "code": code, "type": str(a.get("유형") or "?") if pd.notna(a.get("유형")) else "?",
                     "hour": "09시" if hh == "09" else "10시↑",
                     "intra_col": float(a["현재"]) / 100 if pd.notna(a.get("현재")) else np.nan,
                     "intra": c0 / ap - 1, "A": o1 / c0 - 1, "C": c1 / c0 - 1, "a_open1": o1 / ap - 1, "a_close1": c1 / ap - 1})
    if not rows:
        return {"n": 0}
    D = pd.DataFrame(rows)

    def blk(g):
        return {"n": int(len(g)),
                "장중_현재열": st(g["intra_col"] - COST), "장중_계산": st(g["intra"] - COST),
                "A_종가→다음시가": st(g["A"] - COST), "C_종가→다음종가": st(g["C"] - COST),
                "알람가→다음시가": st(g["a_open1"] - COST), "알람가→다음종가": st(g["a_close1"] - COST)}
    out = {"all": blk(D), "by_type": {k: blk(g) for k, g in D.groupby("type")}, "by_hour": {k: blk(g) for k, g in D.groupby("hour")},
           "intra_col_vs_calc_corr": round(float(D["intra_col"].corr(D["intra"])), 2) if D["intra_col"].notna().sum() > 3 else None,
           "dates": [D["t"].min(), D["t"].max()]}
    return out


def main():
    uni = fetch_csv("universe_latest.csv")
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    suf = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
    mkt = {r.code + suf.get(r.market, ".KS"): r.market for r in uni.itertuples()}
    try:
        trk = fetch_csv("tracking.csv")
        trk["code"] = trk["code"].astype(str).str.zfill(6)
    except Exception as e:  # noqa: BLE001
        print("알람 못 받음", e)
        trk = pd.DataFrame(columns=["시각", "code", "알람가", "현재", "유형"])
    extra = []
    for c in sorted(set(trk["code"]) - set(uni["code"])):
        extra += [c + ".KS", c + ".KQ"]       # 시장 모르면 둘 다 시도
    tick = sorted(mkt) + extra
    print("종목", len(mkt), "알람 밖 종목", len(extra) // 2)
    px, fail = download(tick)
    print("받은 종목", len(px), "실패", len(fail))

    alarm = alarms_check(trk, px)
    print("실전 알람", json.dumps(alarm.get("all", {}), ensure_ascii=False)[:600])

    T = long_table({t: s for t, s in px.items() if t in mkt}, mkt)
    dates = np.array(sorted(T["date"].unique()))
    cut = pd.Timestamp(dates[int(len(dates) * IS_FRAC)])
    T["is"] = T["date"] < cut
    T["year"] = T["date"].dt.year
    IS, OOS = T[T["is"]], T[~T["is"]]
    print("행", len(T), "날짜", len(dates), "자르기", cut.date())

    base = {"is": outcomes(IS), "oos": outcomes(OOS), "oos_cost25": outcomes(OOS, COST2),
            "gross_oos": outcomes(OOS, 0.0)}

    grid = []
    for band in BANDS:
        for vm in VMS:
            for cnh in CNH:
                m = sig_mask(T, band, vm, cnh)
                a, b = T[m & T["is"]], T[m & ~T["is"]]
                oa, ob = outcomes(a), outcomes(b)
                grid.append({"band": f"{band[0]}~{band[1]}", "vm": vm, "cnh": cnh,
                             "is_n": oa["A"]["n"], "is_A": oa["A"].get("avg"), "is_B": oa["B"].get("avg"), "is_C": oa["C"].get("avg"),
                             "oos_n": ob["A"]["n"], "oos_A": ob["A"].get("avg"), "oos_B": ob["B"].get("avg"), "oos_C": ob["C"].get("avg"),
                             "oos_A_pf": ob["A"].get("pf"), "oos_A_win": ob["A"].get("win"),
                             "_k": (band, vm, cnh)})
    elig = [g for g in grid if g["is_n"] >= MIN_IS and g["is_A"] is not None]
    if not elig:
        elig = [g for g in grid if g["is_A"] is not None]
    best = max(elig, key=lambda g: (g["is_A"], g["is_n"]))
    band, vm, cnh = best["_k"]
    m = sig_mask(T, band, vm, cnh)
    S_is, S_oos, S_all = T[m & T["is"]], T[m & ~T["is"]], T[m]

    chosen = {"rule": {"band": best["band"], "vm": vm, "cnh": cnh},
              "is": outcomes(S_is), "oos": outcomes(S_oos), "oos_cost25": outcomes(S_oos, COST2), "oos_gross": outcomes(S_oos, 0.0),
              "oos_port": daily_port(S_oos), "is_port": daily_port(S_is), "oos_port_cost25": daily_port(S_oos, COST2),
              "oos_by_year": by_group(S_oos, "year"), "oos_by_mkt": by_group(S_oos, "mkt"),
              "all_by_year": by_group(S_all, "year"),
              "oos_A_minus_B_pp": round((S_oos["A"].mean() - S_oos["B"].mean()) * 100, 3) if len(S_oos) else None}
    # 「지금 방식」 = 같은 신호를 다음 날 장중(시가→종가)에 단타 · 그리고 실전 알람의 장중 결과
    current = {"desc": "같은 신호를 다음 날 시가에 사서 그날 종가에 파는 장중 단타(B) · 실전 알람 장중 결과",
               "oos_B": chosen["oos"]["B"], "is_B": chosen["is"]["B"],
               "alarms_intraday": alarm.get("all", {}).get("장중_현재열")}

    # 이웃: 손잡이 하나만 옆으로
    bi, vi = BANDS.index(band), VMS.index(vm)
    nb = []
    for j in (bi - 1, bi + 1):
        if 0 <= j < len(BANDS):
            nb.append((BANDS[j], vm, cnh))
    for j in (vi - 1, vi + 1):
        if 0 <= j < len(VMS):
            nb.append((band, VMS[j], cnh))
    nb.append((band, vm, not cnh))
    robust = []
    for k in nb:
        g = next(x for x in grid if x["_k"] == k)
        robust.append({"band": g["band"], "vm": g["vm"], "cnh": g["cnh"], "oos_n": g["oos_n"], "oos_A": g["oos_A"],
                       "oos_A_pf": g["oos_A_pf"], "oos_B": g["oos_B"]})
    robust_ok = bool(robust) and all((r["oos_A"] or -1) > 0 for r in robust if r["oos_n"] >= 50)

    gi = pd.DataFrame([g for g in grid if g["is_n"] >= 30 and g["oos_n"] >= 30])
    rank_corr = round(float(gi["is_A"].rank().corr(gi["oos_A"].rank())), 2) if len(gi) >= 4 else None

    oA = chosen["oos"]["A"]
    pass_core = (oA.get("avg") or -9) > 0 and (oA.get("pf") or 0) >= 1.3 and oA["n"] >= 200
    port_pos = (chosen["oos_port"].get("avg") or -9) > 0
    if pass_core and robust_ok and port_pos:
        verdict = "✅ 통과"
    elif (oA.get("avg") or -9) > 0:
        verdict = "➖ 애매"
    else:
        verdict = "❌ 기각"
    bA, bB = oA.get("avg"), chosen["oos"]["B"].get("avg")
    al = alarm.get("all", {})
    why = (f"시험 구간 고른 신호({best['band']}%·거래 {vm}배·{'고가 근처' if cnh else '종가 위치 무관'}) 밤사이(A) 비용 뺀 평균 {bA}%·손익비 {oA.get('pf')}·n {oA['n']} "
           f"vs 같은 신호 다음 날 장중(B) {bB}% · 기저율 A {base['oos']['A'].get('avg')}%. "
           f"실전 알람 {al.get('n', 0)}건: 장중 {al.get('장중_현재열', {}).get('avg')}% vs 그날 종가→다음 시가 {al.get('A_종가→다음시가', {}).get('avg')}%.")
    nxt = ("✅ 이면: 단타 알람에 「종가 매수 → 다음 날 시가 매도」 그림자 기록부터(실전 4주) · 15:20 동시호가 전 값으로 신호 다시 확인"
           if verdict.startswith("✅") else
           "➖·❌ 이면: 밤사이 보유도 0.45% 비용을 못 넘음 → 단타는 진입 시각(9시대 금지)·비용 낮추기 쪽으로, 아니면 #5 고래 넓히기로 복귀")
    for g in grid:
        g.pop("_k", None)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "question": QUESTION,
           "trials": len(grid),
           "is": {"from": str(pd.Timestamp(dates[0]).date()), "to": str((cut - pd.Timedelta(days=1)).date()), "rows": int(len(IS)), "base": base["is"]},
           "oos": {"from": str(cut.date()), "to": str(pd.Timestamp(dates[-1]).date()), "rows": int(len(OOS)), "base": base["oos"],
                   "base_cost25": base["oos_cost25"], "base_gross": base["gross_oos"]},
           "current": current, "chosen": chosen, "alarms": alarm,
           "grid": grid, "robust": {"ok": robust_ok, "rows": robust}, "rank_corr": rank_corr,
           "verdict": verdict, "verdict_why": why, "next": nxt,
           "universe": {"n": len(mkt), "got": len(px), "fail": len(fail), "fail_some": fail[:20]},
           "note": "결과 A=종가→다음 시가 · B=다음 시가→종가 · C=종가→다음 종가 · 모두 왕복 0.45% 뺀 % (cost25 = 0.25%) · 유니버스는 오늘 목록(살아남은 종목 편향) · 신호 종가에 산다고 가정 · 매수 추천 아님"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("기저율 시험", base["oos"])
    print("고른", chosen["rule"], "IS", chosen["is"]["A"], "OOS", chosen["oos"])
    print("하루 포트", chosen["oos_port"])
    for g in grid:
        print(g["band"], g["vm"], g["cnh"], "IS", g["is_n"], g["is_A"], g["is_B"], "| OOS", g["oos_n"], g["oos_A"], g["oos_B"], g["oos_A_pf"])
    print("이웃", robust, "순위상관", rank_corr)
    print(verdict, why)


if __name__ == "__main__":
    main()
