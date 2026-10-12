"""⚡ 킥 새 아이디어 4개 과거 검증 + 매일 실시간 신호 (10/12 사용자: 「통하면 포트에 섞어」)

  python src/kick_ideas_bt.py fetch US   → out/ki_rows_US.csv.gz · out/ki_log_US.json   (종목 아이디어 6·7 사건 + 그 뒤 결과)
  python src/kick_ideas_bt.py macro      → out/ki_macro.json                            (지수 아이디어 8 · 자산 추세 10)
  python src/kick_ideas_bt.py stats      → market/kick_ideas_bt.json                    (변형별 성적 · 고른 규칙 · 판정)
  python src/kick_ideas_bt.py live       → market/kick_ideas_live.json                  (오늘 신호 — src/kick_sleeve.py 가 읽음)

  6 🏔 거래량 동반 52주 신고가 (nh52): 종가가 직전 252일 최고 종가 위 · 거래량 ≥ 직전 50일 평균 × k · (선택) 그 시장 지수 200일선 위
  7 📊 실적 발표 뒤 표류 좁힌 버전 (pead): 시가 갭 ≥ g (전일 고가 위에서 열림) · 거래량 ≥ k배 · 종가 > 직전 60일 고가 · 실적 철(분기 끝 +8~55일) 대용
     ※ 과거 실적 발표일은 yfinance 가 믿을 수 없어 「실적 철 + 큰 갭 + 큰 거래량」을 대용으로 씀 (진짜 실적일이 아닐 수 있음)
  8 🩹 상승장 속 급락 되돌림 (dip): SPY(또는 QQQ) 200일선 위 · 2일 RSI < th → 다음 날 종가에 사서, 종가 > 5일선 또는 N일 뒤 다음 날 종가에 팖
  10 🧭 자산 전체 추세 (trend): GLD USO TLT UUP SPY QQQ EFA EEM DBC — 종가 > 직전 N일 고가면 다음 날 종가에 사고, 종가 < 직전 M일 저가면 다음 날 종가에 팖

  공통 (src/accum_bt.py 와 같은 틀): 진입 = 신호 다음 거래일 종가 · 비용 왕복 0.5% (한국 0.45%) · 초과 = 같은 기간 그 시장 지수 대비
  · 종목 아이디어: 2012~2019 에서 고르고(앞) 2020~ 에서 시험(뒤) · 같은 종목 20거래일 안 재신호 무시 · 유니버스 = 오늘 목록(생존자 편향)
  · 지수·자산 아이디어: ≤2016 에서 고르고 2017~ 에서 시험
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accum_bt as AB  # noqa: E402  (유니버스·시세 받기·통계 함수 재사용)

ROOT = Path(__file__).resolve().parent.parent
OUTD = ROOT / "out"
RES = ROOT / "market" / "kick_ideas_bt.json"
LIVE = ROOT / "market" / "kick_ideas_live.json"
KST = dt.timezone(dt.timedelta(hours=9))
IS_START, IS_END, OOS_START = "2012-01-01", "2019-12-31", "2020-01-01"
M_IS_END, M_OOS_START = "2016-12-31", "2017-01-01"     # 지수·자산 아이디어
EXITS = ("f10", "f20", "f40", "s8_20", "s8t20_20", "s8_40", "kk")
EXIT_DOC = {"f10": "10일 보유", "f20": "20일 보유", "f40": "40일 보유", "s8_20": "−8% 손절 · 20일", "s8t20_20": "−8% 손절 · +20% 익절 · 20일",
            "s8_40": "−8% 손절 · 40일", "kk": "킥 규칙(−5% 손절 · +15% 절반 → 20일선 · 15일 +3% 못 넘으면 정리)"}
TREND_U = ["GLD", "USO", "TLT", "UUP", "SPY", "QQQ", "EFA", "EEM", "DBC"]


# ───────────────────────────── 출구 계산 ─────────────────────────────
def gexit(c, e, stop, take, hold):
    n = len(c)
    if e + hold >= n:
        return None
    for k in range(1, hold + 1):
        r = c[e + k] / c[e] - 1
        if (stop is not None and r <= stop) or (take is not None and r >= take):
            return r, e + k
    return c[e + hold] / c[e] - 1, e + hold


def kexit(c, ma20, e, stop=-0.05, take=0.15, tday=15, tmin=0.03, cap=60):
    """src/kick_sleeve.py simulate() 와 같은 순서의 출구"""
    n = len(c)
    if e + cap >= n:
        return None
    e0, half, rh, mx = c[e], False, 0.0, c[e]
    for k in range(1, cap + 1):
        j = e + k
        p = c[j]
        mx = max(mx, p)
        r = p / e0 - 1
        if r <= stop:
            return (rh + r / 2 if half else r), j
        if not half and r >= take:
            half, rh = True, r / 2
            continue
        if half:
            if not np.isnan(ma20[j]) and p < ma20[j]:
                return rh + r / 2, j
        elif k >= tday and mx / e0 - 1 < tmin:
            return r, j
    r = c[e + cap] / e0 - 1
    return (rh + r / 2 if half else r), e + cap


def outcomes(c, ma20, ixa, e, cost):
    o = {}
    for nm in EXITS:
        if nm == "kk":
            res = kexit(c, ma20, e)
        else:
            hold = int(nm.split("_")[-1]) if "_" in nm else int(nm[1:])
            stop = -0.08 if nm.startswith("s8") else None
            take = 0.20 if "t20" in nm else None
            res = gexit(c, e, stop, take, hold)
        if res is None:
            continue
        r, ex = res
        o["r_" + nm] = round((r - cost) * 100, 2)
        if ixa[e] > 0 and ixa[ex] > 0:
            o["x_" + nm] = round((r - cost - (ixa[ex] / ixa[e] - 1)) * 100, 2)
    return o


def dq_of(d: pd.Timestamp) -> int:
    """분기 끝 이후 며칠 (실적 철 대용)"""
    q_end_m = ((d.month - 1) // 3) * 3          # 0,3,6,9 → 직전 분기 끝 달
    if q_end_m == 0:
        qe = pd.Timestamp(d.year - 1, 12, 31)
    else:
        qe = pd.Timestamp(d.year, q_end_m, 1) + pd.offsets.MonthEnd(0)
    return int((d - qe).days)


# ───────────────────────────── 종목 사건 (6·7) ─────────────────────────────
def feats(d: pd.DataFrame, minp, minvol):
    o, h, l, c, v = (d[x].to_numpy(float) for x in ("open", "high", "low", "close", "volume"))
    cs, vs, hs = pd.Series(c), pd.Series(v), pd.Series(h)
    with np.errstate(divide="ignore", invalid="ignore"):
        F = dict(o=o, h=h, l=l, c=c, v=v,
                 hi252=cs.shift(1).rolling(252, min_periods=252).max().to_numpy(),
                 vr=(v / vs.shift(1).rolling(50, min_periods=50).mean().to_numpy()),
                 liq=((cs * vs).rolling(50).mean().to_numpy() >= minvol) & (c >= minp),
                 hi60=hs.shift(1).rolling(60, min_periods=60).max().to_numpy(),
                 hi20=hs.shift(1).rolling(20, min_periods=20).max().to_numpy(),
                 gap=o / cs.shift(1).to_numpy() - 1, ph=hs.shift(1).to_numpy(),
                 pre20=(c / cs.shift(20).to_numpy() - 1) * 100,
                 ma20=cs.rolling(20).mean().to_numpy())
    F["nh"] = c > F["hi252"]
    F["ev_nh"] = F["liq"] & F["nh"] & (F["vr"] >= 1.5)
    F["ev_gap"] = F["liq"] & (F["gap"] >= 0.02) & (F["vr"] >= 1.5) & (o > F["ph"])
    return F


def fetch(m: str):
    t0 = time.time()
    OUTD.mkdir(exist_ok=True)
    isym, minp, minvol = AB.MKT[m]
    cost = AB.COST.get(m, AB.DEF_COST)
    log = {"market": m, "start": AB.START}
    tks = AB.universe(m, log)
    idx = AB.idx_series(isym)
    log["index_bars"] = len(idx)
    data = AB.download(tks, log, t0)
    log["download_sec"] = round(time.time() - t0)
    i200 = idx.rolling(200).mean()
    reg = (idx > i200).astype(float).where(i200.notna())
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = feats(d, minp, minvol)
        dates = d.index
        n = len(dates)
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        rga = reg.reindex(dates).ffill().to_numpy(float)
        ev = np.where((F["ev_nh"] | F["ev_gap"]) & (np.arange(n) >= 260))[0]
        for ti in ev:
            if ti + 1 >= n:
                continue
            dte = dates[ti]
            r = dict(tk=t, mkt=m, date=str(dte.date()), ti=int(ti), nh=int(F["nh"][ti]), g=int(bool(F["ev_gap"][ti])),
                     gap=round(float(F["gap"][ti]) * 100, 2), vr=round(float(F["vr"][ti]), 2),
                     a60=int(F["c"][ti] > F["hi60"][ti]) if not np.isnan(F["hi60"][ti]) else 0,
                     o20=int(F["o"][ti] > F["hi20"][ti]) if not np.isnan(F["hi20"][ti]) else 0,
                     reg=int(rga[ti]) if not np.isnan(rga[ti]) else -1, dq=dq_of(dte),
                     pre20=round(float(F["pre20"][ti]), 1) if not np.isnan(F["pre20"][ti]) else None)
            r.update(outcomes(F["c"], F["ma20"], ixa, ti + 1, cost))
            rows.append(r)
        if time.time() - t0 > 44 * 60:
            log["cut_compute"] = t
            break
    df = pd.DataFrame(rows)
    df.to_csv(OUTD / f"ki_rows_{m}.csv.gz", index=False, compression="gzip")
    log["rows"], log["sec"] = len(df), round(time.time() - t0)
    log["last_date"] = str(max(d.index.max() for d in data.values()).date()) if data else None
    json.dump(log, open(OUTD / f"ki_log_{m}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(log, ensure_ascii=False))


# ───────────────────────────── 지수·자산 (8·10) ─────────────────────────────
def ydl(syms, start="1990-01-01"):
    import yfinance as yf
    out = {}
    for s in syms:
        for att in range(3):
            try:
                d = yf.download(s, start=start, auto_adjust=True, progress=False)
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
                if len(d):
                    out[s] = d
                    break
            except Exception:
                time.sleep(5 * (att + 1))
    return out


def rsi2(c: pd.Series, n=2) -> pd.Series:
    d = c.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    au, ad = up.ewm(alpha=1 / n, adjust=False).mean(), dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad.replace(0, np.nan))


def cash_daily(irx: pd.Series, idx) -> pd.Series:
    """^IRX(13주 국채 연%) → 일 수익률"""
    s = irx.reindex(idx).ffill().fillna(0) / 100 / 252
    return s


def dip_trades(c: pd.Series, th, ex, hold, cost, cdaily, same_day=False):
    """ex: 'ma5' = 종가 > 5일선이면 팖(최대 hold일) · 'fix' = hold일 뒤 팖. 신호·청산 모두 다음 날 종가(same_day=True 면 그날 종가)."""
    ma200, ma5, r2 = c.rolling(200).mean(), c.rolling(5).mean(), rsi2(c)
    C, A2, M5, R = c.to_numpy(), ma200.to_numpy(), ma5.to_numpy(), r2.to_numpy()
    cd = cdaily.to_numpy()
    lag = 0 if same_day else 1
    n, i, out = len(C), 200, []
    while i < n - lag:
        if not np.isnan(A2[i]) and C[i] > A2[i] and R[i] < th:
            e = i + lag
            j, k = None, 0
            for k in range(1, hold + 1):
                if e + k >= n:
                    break
                if ex == "ma5" and C[e + k] > M5[e + k]:
                    j = e + k
                    break
            if j is None:
                j = e + hold
            x = j + lag if ex == "ma5" else j
            if x >= n or x <= e:
                break
            r = C[x] / C[e] - 1 - cost
            cr = float(np.prod(1 + cd[e + 1:x + 1]) - 1)
            out.append({"d": str(c.index[i].date()), "e": str(c.index[e].date()), "x": str(c.index[x].date()), "days": int(x - e),
                        "r": round(r * 100, 3), "xc": round((r - cr) * 100, 3)})
            i = x + 1
        else:
            i += 1
    return out


def tstat(tr: list[dict], key="r") -> dict:
    if not tr:
        return {"n": 0}
    x = pd.Series([t[key] for t in tr])
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    yrs = pd.Series([t["d"][:4] for t in tr])
    by = x.groupby(yrs.values).sum()
    ex_best = (x.sum() - by.max()) / max(1, len(x) - int((yrs == by.idxmax()).sum()))
    return {"n": int(len(x)), "avg": round(float(x.mean()), 3), "win": round(float((x > 0).mean()) * 100, 1),
            "pf": round(float(pos / neg), 2) if neg > 0 else None, "sum": round(float(x.sum()), 1),
            "xc_avg": round(float(np.mean([t["xc"] for t in tr])), 3) if "xc" in tr[0] else None,
            "days_avg": round(float(np.mean([t["days"] for t in tr])), 1) if "days" in tr[0] else None,
            "years": int(len(by)), "best_year": str(by.idxmax()), "best_year_share": round(float(by.max() / x.sum()), 2) if x.sum() > 0 else None,
            "avg_ex_best_year": round(float(ex_best), 3)}


def series_stats(r: pd.Series, bench: pd.Series | None = None) -> dict:
    r = r.dropna()
    if len(r) < 20:
        return {"n_days": int(len(r))}
    nav = (1 + r).cumprod()
    yrs = len(r) / 252
    o = {"start": str(r.index[0].date()), "end": str(r.index[-1].date()), "cagr": round((float(nav.iloc[-1]) ** (1 / yrs) - 1) * 100, 2),
         "vol": round(float(r.std() * math.sqrt(252)) * 100, 2), "mdd": round(float((nav / nav.cummax() - 1).min()) * 100, 1),
         "sharpe": round(float(r.mean() / r.std() * math.sqrt(252)), 2) if r.std() > 0 else None}
    if bench is not None:
        b = bench.reindex(r.index)
        o["corr_spy"] = round(float(r.corr(b)), 2)
    return o


def trend_run(px: dict, cdaily: pd.Series, nin, nout, wmode, cost=0.005, start=None):
    """자산 추세 슬리브의 일간 수익률 · 거래 목록. 가중: eq = 1/9 씩 · risk = 60일 변동성 반비례(9개 다 들어가면 합 1)"""
    syms = [s for s in TREND_U if s in px]
    idx = sorted(set().union(*[set(px[s].index) for s in syms]))
    idx = pd.DatetimeIndex(idx)
    if start:
        idx = idx[idx >= pd.Timestamp(start)]
    C = pd.DataFrame({s: px[s]["close"] for s in syms}).reindex(idx).ffill()
    H = pd.DataFrame({s: px[s]["high"] for s in syms}).reindex(idx).ffill()
    L = pd.DataFrame({s: px[s]["low"] for s in syms}).reindex(idx).ffill()
    R = C.pct_change(fill_method=None).fillna(0)
    hiN = H.shift(1).rolling(nin, min_periods=nin).max()
    loM = L.shift(1).rolling(nout, min_periods=nout).min()
    vol = R.rolling(60, min_periods=40).std()
    cd = cdaily.reindex(idx).fillna(0).to_numpy()
    n, k = len(idx), len(syms)
    Cv, Hn, Lm, V, Rv = C.to_numpy(), hiN.to_numpy(), loM.to_numpy(), vol.to_numpy(), R.to_numpy()
    pos = np.zeros(k)          # 들고 있는 비중 (다음 날 수익에 적용)
    pend = [None] * k          # 신호 다음 날 종가 실행 대기: ('in', w) / ('out',)
    ent = [None] * k
    ret = np.zeros(n)
    trades = []
    for i in range(1, n):
        ret[i] = float(np.dot(pos, Rv[i])) + (1 - pos.sum()) * cd[i]
        for j in range(k):     # 어제 신호 → 오늘 종가에 실행
            if pend[j] is None:
                continue
            if pend[j][0] == "in" and pos[j] == 0:
                pos[j] = pend[j][1]
                ret[i] -= pos[j] * cost / 2
                ent[j] = (i, Cv[i, j])
            elif pend[j][0] == "out" and pos[j] > 0:
                ret[i] -= pos[j] * cost / 2
                ei, ep = ent[j]
                trades.append({"sym": syms[j], "d": str(idx[ei].date()), "x": str(idx[i].date()), "days": int(i - ei),
                               "r": round((Cv[i, j] / ep - 1 - cost) * 100, 3), "w": round(float(pos[j]), 4)})
                pos[j] = 0.0
            pend[j] = None
        for j in range(k):     # 오늘 종가로 신호
            if np.isnan(Cv[i, j]) or np.isnan(Hn[i, j]) or np.isnan(Lm[i, j]):
                continue
            if pos[j] == 0 and Cv[i, j] > Hn[i, j]:
                if wmode == "eq":
                    w = 1 / k
                else:
                    iv = 1 / V[i]
                    iv = iv[np.isfinite(iv)]
                    w = (1 / V[i, j]) / iv.sum() if np.isfinite(1 / V[i, j]) and iv.sum() > 0 else 1 / k
                    w = min(w, 0.35)
                pend[j] = ("in", w)
            elif pos[j] > 0 and Cv[i, j] < Lm[i, j]:
                pend[j] = ("out",)
    s = pd.Series(ret, index=idx)
    open_ = [{"sym": syms[j], "d": str(idx[ent[j][0]].date()), "w": round(float(pos[j]), 4),
              "r": round((Cv[-1, j] / ent[j][1] - 1) * 100, 2)} for j in range(k) if pos[j] > 0]
    return s, trades, open_


def macro():
    OUTD.mkdir(exist_ok=True)
    px = ydl(["SPY", "QQQ", "^IRX"] + [s for s in TREND_U if s not in ("SPY", "QQQ")])
    irx = px.pop("^IRX")["close"] if "^IRX" in px else pd.Series(dtype=float)
    out = {"data": {s: [str(d.index[0].date()), str(d.index[-1].date()), int(len(d))] for s, d in px.items()}}
    # ── 8 🩹 급락 되돌림
    D8 = {}
    for sym in ("SPY", "QQQ"):
        c = px[sym]["close"]
        cdl = cash_daily(irx, c.index)
        for th in (5, 10, 15):
            for ex, hold in (("ma5", 5), ("ma5", 10), ("fix", 5)):
                for cost, cn in ((0.005, "c50"), (0.001, "c10")):
                    for sd in (False, True):
                        key = f"{sym}|rsi<{th}|{ex}/{hold}d|{cn}|{'same' if sd else 'next'}"
                        tr = dip_trades(c, th, ex, hold, cost, cdl, same_day=sd)
                        D8[key] = {"IS": tstat([t for t in tr if t["d"] <= M_IS_END]), "OOS": tstat([t for t in tr if t["d"] >= M_OOS_START]),
                                   "last": tr[-3:]}
                        if cn == "c50" and not sd:
                            yrs = {}
                            for t in tr:
                                yrs.setdefault(t["d"][:4], []).append(t["r"])
                            D8[key]["by_year"] = {y: {"n": len(v), "sum": round(sum(v), 2)} for y, v in sorted(yrs.items())}
    out["dip"] = D8
    # ── 10 🧭 자산 추세
    spy_r = px["SPY"]["close"].pct_change()
    syms = [s for s in TREND_U if s in px]
    common = max(px[s].index[0] for s in syms)
    out["trend_start_data"] = str(common.date())
    D10 = {}
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in syms])))
    cdl = cash_daily(irx, allidx)
    # C안 뼈대 대용: SPY 47.5 · QQQ 47.5 · GLD 5 (매일 비중 맞춤 근사)
    Cr = (0.475 * px["SPY"]["close"].pct_change() + 0.475 * px["QQQ"]["close"].pct_change() + 0.05 * px["GLD"]["close"].pct_change()).dropna()
    for nin, nout in ((20, 10), (55, 20), (100, 50)):
        for wm in ("eq", "risk"):
            s, tr, op = trend_run(px, cdl, nin, nout, wm, start=str(common.date()))
            s = s[s.index >= common + pd.Timedelta(days=int(nin * 1.6))]     # 첫 신호가 가능해진 뒤부터
            key = f"{nin}/{nout}|{wm}"
            o = {}
            for pn, (a, b) in {"IS": (None, M_IS_END), "OOS": (M_OOS_START, None), "ALL": (None, None)}.items():
                ss = s
                if a:
                    ss = ss[ss.index >= pd.Timestamp(a)]
                if b:
                    ss = ss[ss.index <= pd.Timestamp(b)]
                trs = [{"d": t["d"], "r": t["r"], "days": t["days"]} for t in tr if (not a or t["d"] >= a) and (not b or t["d"] <= b)]
                cr = Cr.reindex(ss.index).dropna()
                tl = ss.reindex(cr.index)
                o[pn] = {"sleeve": series_stats(ss, spy_r), "trades": tstat(trs), "C": series_stats(cr),
                         "C_plus5": series_stats(0.95 * cr + 0.05 * tl), "C_plus3": series_stats(0.97 * cr + 0.03 * tl)}
            o["open"] = op
            yr = s.groupby(s.index.year).apply(lambda x: round(float((1 + x).prod() - 1) * 100, 1))
            o["by_year"] = {str(k): v for k, v in yr.items()}
            D10[key] = o
    out["trend"] = D10
    json.dump(out, open(OUTD / "ki_macro.json", "w"), ensure_ascii=False, indent=1, default=str)
    print("macro done", list(out["data"].keys()))


# ───────────────────────────── 종합 · 판정 ─────────────────────────────
def pst(x: pd.Series) -> dict:
    x = x.dropna()
    if not len(x):
        return {"n": 0}
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    return {"n": int(len(x)), "avg": round(float(x.mean()), 2), "med": round(float(x.median()), 2), "win": round(float((x > 0).mean()) * 100, 1),
            "pf": round(float(pos / neg), 2) if neg > 0 else None}


def evals(sel: pd.DataFrame, ex: str) -> dict:
    o = {"r": pst(sel.get("r_" + ex, pd.Series(dtype=float))), "x": pst(sel.get("x_" + ex, pd.Series(dtype=float)))}
    if len(sel) and ("x_" + ex) in sel:
        g = sel.dropna(subset=["x_" + ex])
        by = g.groupby(g["date"].str[:4])["x_" + ex]
        o["by_year"] = {y: {"n": int(len(v)), "x": round(float(v.mean()), 2)} for y, v in by}
        if len(by) >= 2:
            sm = by.sum()
            yb = sm.idxmax()
            rest = g[g["date"].str[:4] != yb]["x_" + ex]
            o["x_ex_best_year"] = round(float(rest.mean()), 2) if len(rest) else None
            o["best_year"] = yb
    return o


def verdict(oos: dict, min_n=100) -> tuple[str, str]:
    x, r = oos.get("x", {}), oos.get("r", {})
    n, xa, pf, xeb = x.get("n", 0), x.get("avg"), r.get("pf"), oos.get("x_ex_best_year")
    if not n:
        return "❌", "시험 기간 표본 없음"
    s = f"시험 기간 {n}건 · 지수 초과 {xa:+.2f}% · 손익비 {pf} · 가장 좋은 해 빼면 {xeb if xeb is not None else '-'}"
    ok = n >= min_n and xa > 0 and (pf or 0) >= 1.3 and (xeb is None or xeb > 0)
    if ok:
        return "✅", s
    if xa > 0 and (pf or 0) >= 1.2 and n >= 30:
        return "🧪", s + " — 기준 일부 못 미침"
    if (r.get("avg") or 0) > 0:
        return "👻", s + " — 절대 수익은 플러스지만 지수를 못 이김"
    return "❌", s


def stock_grid(df, idea):
    """idea → [(이름, 마스크 함수)] — 앞(2012~2019)에서만 고른다"""
    G = []
    mk_sets = {"US+KR+JP": ("US", "KR", "JP"), "US": ("US",), "KR": ("KR",), "JP": ("JP",)}
    if idea == "nh52":
        for k in (1.5, 2.0, 3.0):
            for rg in (0, 1):
                for ms, mm in mk_sets.items():
                    G.append((f"거래량≥{k}배|지수200선위={'예' if rg else '무관'}|{ms}",
                              (lambda d, k=k, rg=rg, mm=mm: (d["nh"] == 1) & (d["vr"] >= k) & ((d["reg"] == 1) if rg else True) & d["mkt"].isin(mm))))
    else:
        for g in (3.0, 5.0, 8.0):
            for k in (2.0, 3.0):
                for a in (0, 1):
                    for se in (0, 1):
                        for ms, mm in mk_sets.items():
                            G.append((f"갭≥{g:g}%|거래량≥{k:g}배|60일고가위={'예' if a else '무관'}|실적철={'예' if se else '무관'}|{ms}",
                                      (lambda d, g=g, k=k, a=a, se=se, mm=mm: (d["g"] == 1) & (d["gap"] >= g) & (d["vr"] >= k) & ((d["a60"] == 1) if a else True)
                                       & (d["dq"].between(8, 55) if se else True) & d["mkt"].isin(mm))))
    return G


def stats():
    fs = sorted(OUTD.glob("ki_rows_*.csv.gz"))
    df = pd.concat([pd.read_csv(f, dtype={"tk": str}) for f in fs], ignore_index=True) if fs else pd.DataFrame()
    logs = {}
    for f in sorted(OUTD.glob("ki_log_*.json")):
        lg = json.load(open(f, encoding="utf-8"))
        logs[lg["market"]] = lg
    out = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "logs": logs,
           "rule": {"entry": "신호 다음 거래일 종가", "cost": "왕복 0.5% (한국 0.45%)", "excess": "같은 기간 그 시장 지수(S&P500·코스피·닛케이·항셍·상해) 대비",
                    "stock_split": f"앞 {IS_START}~{IS_END}(고르기) · 뒤 {OOS_START}~(시험)", "macro_split": f"앞 ~{M_IS_END}(고르기) · 뒤 {M_OOS_START}~(시험)",
                    "dedupe": "같은 종목 20거래일 안 재신호 무시", "exits": EXIT_DOC,
                    "adopt": "✅ = 시험 기간 n≥100 · 비용 뺀 지수 초과 평균 > 0 · 손익비(비용 뺀 수익) ≥ 1.3 · 가장 좋은 해를 빼도 초과 > 0 (8·10 은 여러 해면 n 적어도 됨). "
                              "🧪 = 초과 > 0 · 손익비 ≥ 1.2 · n ≥ 30 (절반 크기). 👻 = 절대 수익만 플러스(그림자 채점). ❌ = 그 밖",
                    "survivorship": "유니버스 = 오늘 상장 목록(미국은 오늘의 S&P500+400) → 생존자 편향으로 과거 성적이 부풀려졌을 수 있음",
                    "earnings": "7은 실제 실적 발표일이 아니라 「분기 끝 +8~55일 · 큰 갭 · 큰 거래량」 대용"},
           "ideas": {}}
    if len(df):
        df = df[df["date"] >= IS_START].copy()
        per = {"IS": df[df["date"] <= IS_END], "OOS": df[df["date"] >= OOS_START]}
        out["rows"] = {m: int((df["mkt"] == m).sum()) for m in sorted(df["mkt"].unique())}
        for idea in ("nh52", "pead"):
            grid = []
            cache = {}
            for name, fn in stock_grid(df, idea):
                for pn, d in per.items():
                    cache[(name, pn)] = AB.dedupe(d[fn(d).fillna(False).astype(bool)])
                for ex in EXITS:
                    if idea == "nh52" and ex in ("f10",):
                        continue
                    if idea == "pead" and ex in ("f10",):
                        continue
                    ins = evals(cache[(name, "IS")], ex)
                    grid.append((name, ex, ins))
            ok = [g for g in grid if g[2]["x"].get("n", 0) >= 200 and (g[2]["x"].get("avg") or -9) > 0 and (g[2]["r"].get("pf") or 0) >= 1.3]
            ok.sort(key=lambda g: -(g[2]["x"]["avg"]))
            pick = ok[0] if ok else max(grid, key=lambda g: (g[2]["x"].get("avg") or -99) if g[2]["x"].get("n", 0) >= 100 else -99)
            name, ex, ins = pick
            oos_sel = cache[(name, "OOS")]
            oos = evals(oos_sel, ex)
            vd, why = verdict(oos)
            if not ok and vd in ("✅", "🧪"):
                vd, why = ("👻" if (oos["r"].get("avg") or 0) > 0 else "❌"), why + " — 하지만 앞 기간(2012~2019)에서 기준을 통과한 규칙이 없음 → 채택 안 함"
            ms = name.split("|")[-1]
            byk = {m: evals(oos_sel[oos_sel["mkt"] == m], ex) for m in ("US", "KR", "JP")}
            top = []
            for g in ok[:10]:
                oo = evals(cache[(g[0], "OOS")], g[1])
                top.append({"rule": g[0], "exit": g[1], "IS_x": g[2]["x"].get("avg"), "IS_n": g[2]["x"].get("n"), "IS_pf": g[2]["r"].get("pf"),
                            "OOS_x": oo["x"].get("avg"), "OOS_n": oo["x"].get("n"), "OOS_pf": oo["r"].get("pf")})
            I = {"pick": {"rule": name, "exit": ex, "exit_doc": EXIT_DOC[ex], "how": "앞 기간 n≥200 · 초과>0 · 손익비≥1.3 중 앞 기간 초과 평균 최대"
                          if ok else "앞 기간 기준 통과 없음 → 앞 기간 초과 평균 최대(n≥100)"},
                 "IS": {k: v for k, v in ins.items()}, "OOS": oos, "OOS_by_mkt": byk, "verdict": vd, "why": why, "top_IS": top, "n_grid": len(grid), "n_pass_IS": len(ok)}
            # 사용자가 말한 그대로의 기준선도 같이 (고르기와 별개)
            if idea == "nh52":
                ref = {"말한 그대로(거래량≥2배·지수200선위·US+KR+JP·20일)": ("거래량≥2.0배|지수200선위=예|US+KR+JP", "f20"),
                       "말한 그대로 + −8% 손절": ("거래량≥2.0배|지수200선위=예|US+KR+JP", "s8_20"),
                       "말한 그대로 + −8% 손절 · +20% 익절": ("거래량≥2.0배|지수200선위=예|US+KR+JP", "s8t20_20")}
            else:
                ref = {"말한 그대로(갭≥5%·거래량≥2배·60일고가위·실적철·US+KR+JP·20일)": ("갭≥5%|거래량≥2배|60일고가위=예|실적철=예|US+KR+JP", "f20"),
                       "말한 그대로 · 40일": ("갭≥5%|거래량≥2배|60일고가위=예|실적철=예|US+KR+JP", "f40"),
                       "말한 그대로 · 미국만 · 40일": ("갭≥5%|거래량≥2배|60일고가위=예|실적철=예|US", "f40"),
                       "대용 실적일(갭≥5%·거래량≥3배·실적철) · 20일": ("갭≥5%|거래량≥3배|60일고가위=무관|실적철=예|US+KR+JP", "f20")}
            I["ref"] = {}
            for lab, (nm, e_) in ref.items():
                if (nm, "IS") in cache:
                    I["ref"][lab] = {"IS": evals(cache[(nm, "IS")], e_), "OOS": evals(cache[(nm, "OOS")], e_)}
                    for pn in ("IS", "OOS"):
                        I["ref"][lab][pn].pop("by_year", None)
            if idea == "pead":   # 지금 📊 실적 갭(그림자) 대용: 미국 · 갭≥2% · 거래량≥1.5배 · 시가>20일 고가 · 실적 철 · 킥 규칙 출구
                for pn, d in per.items():
                    m_ = (d["g"] == 1) & (d["o20"] == 1) & d["dq"].between(8, 55) & (d["mkt"] == "US")
                    e_ = evals(AB.dedupe(d[m_]), "kk")
                    e_.pop("by_year", None)
                    I.setdefault("now_earn_proxy", {})[pn] = e_
            out["ideas"][idea] = I
    mp = OUTD / "ki_macro.json"
    if mp.exists():
        M = json.load(open(mp, encoding="utf-8"))
        out["macro_data"] = M.get("data")
        # 8: 앞 기간(≤2016)에서 고름 — 비용 0.5% · 다음 날 종가 · 거래 30건↑ 중 손익비 최대
        D8 = M["dip"]
        cand = [(k, v) for k, v in D8.items() if "|c50|next" in k and v["IS"].get("n", 0) >= 30]
        cand.sort(key=lambda kv: -(kv[1]["IS"].get("pf") or 0))
        k8, v8 = cand[0]
        o8 = v8["OOS"]
        ok8 = (o8.get("n", 0) >= 30 and (o8.get("avg") or 0) > 0 and (o8.get("pf") or 0) >= 1.3 and (o8.get("xc_avg") or 0) > 0
               and (o8.get("avg_ex_best_year") or 0) > 0 and o8.get("years", 0) >= 5)
        vd8 = "✅" if ok8 else ("🧪" if (o8.get("avg") or 0) > 0 and (o8.get("pf") or 0) >= 1.2 else ("👻" if (o8.get("avg") or 0) > 0 else "❌"))
        out["ideas"]["dip"] = {"pick": {"rule": k8, "how": "앞 기간(≤2016) 비용 0.5%·다음 날 종가 변형 중 거래 30건↑ 손익비 최대"},
                               "IS": v8["IS"], "OOS": o8, "by_year": v8.get("by_year"), "verdict": vd8,
                               "why": f"시험 기간(2017~) {o8.get('n')}건 · 평균 {o8.get('avg')}% · 현금 대비 {o8.get('xc_avg')}% · 손익비 {o8.get('pf')} · {o8.get('years')}개 해 · 가장 좋은 해 빼면 {o8.get('avg_ex_best_year')}%",
                               "grid": {k: {"IS": {kk: v["IS"].get(kk) for kk in ("n", "avg", "pf", "xc_avg")},
                                            "OOS": {kk: v["OOS"].get(kk) for kk in ("n", "avg", "pf", "xc_avg")}} for k, v in D8.items()},
                               "note": "초과 = 같은 기간 현금(13주 국채) 대비 — 킥의 빈 자리(현금)를 쓰는 아이디어라서"}
        # 10: 앞 기간 샤프 최대
        D10 = M["trend"]
        k10 = max(D10, key=lambda k: D10[k]["IS"]["sleeve"].get("sharpe") or -9)
        v10 = D10[k10]
        oo, oi = v10["OOS"], v10["IS"]
        better = ((oo["C_plus5"].get("sharpe") or 0) >= (oo["C"].get("sharpe") or 0) and (oo["C_plus5"].get("mdd") or -99) >= (oo["C"].get("mdd") or -99))
        ok10 = (oo["sleeve"].get("cagr") or 0) > 0 and (oo["trades"].get("pf") or 0) >= 1.3 and better
        vd10 = "✅" if ok10 else ("🧪" if (oo["sleeve"].get("cagr") or 0) > 0 and (oo["trades"].get("pf") or 0) >= 1.2 else ("👻" if (oo["sleeve"].get("cagr") or 0) > 0 else "❌"))
        out["ideas"]["trend"] = {"pick": {"rule": k10, "how": "앞 기간(데이터 시작~2016) 슬리브 샤프 최대"}, "IS": oi, "OOS": oo, "by_year": v10.get("by_year"),
                                 "open": v10.get("open"), "verdict": vd10, "data_start": M.get("trend_start_data"),
                                 "why": (f"시험 기간(2017~) 슬리브 연 {oo['sleeve'].get('cagr')}% · 최대낙폭 {oo['sleeve'].get('mdd')}% · S&P 상관 {oo['sleeve'].get('corr_spy')} · "
                                         f"거래 {oo['trades'].get('n')}건 손익비 {oo['trades'].get('pf')} · C안 샤프 {oo['C'].get('sharpe')}→+5% {oo['C_plus5'].get('sharpe')} · "
                                         f"낙폭 {oo['C'].get('mdd')}→{oo['C_plus5'].get('mdd')}"),
                                 "grid": {k: {p: {"sleeve": v[p]["sleeve"], "trades_pf": v[p]["trades"].get("pf"), "trades_n": v[p]["trades"].get("n"),
                                                  "C": v[p]["C"].get("sharpe"), "C_plus5": v[p]["C_plus5"].get("sharpe")} for p in ("IS", "OOS")} for k, v in D10.items()},
                                 "note": "C안 뼈대 대용 = SPY 47.5 · QQQ 47.5 · GLD 5 (매일 비중 맞춤 근사, 달러 기준). 추세 슬리브는 비어 있는 몫을 현금(13주 국채)으로"}
    RES.parent.mkdir(exist_ok=True)
    json.dump(out, open(RES, "w"), ensure_ascii=False, indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else str(x))
    print(json.dumps({k: (v.get("verdict"), v.get("pick"), v.get("why")) for k, v in out["ideas"].items()}, ensure_ascii=False, indent=1))


# ───────────────────────────── 실시간 (매일) ─────────────────────────────
def _parse_rule(rule: str) -> dict:
    o = {}
    for part in rule.split("|"):
        if "≥" in part:
            k, v = part.split("≥")
            o[k] = float(v.rstrip("배%"))
        elif "=" in part:
            k, v = part.split("=")
            o[k] = v == "예"
        else:
            o["mkts"] = part.split("+")
    return o


def live():
    """오늘 신호 — 검증 결과(market/kick_ideas_bt.json)에서 고른 규칙 그대로. 최근 30일 신호를 기록으로 남김."""
    now = dt.datetime.now(KST)
    try:
        B = json.loads(RES.read_text(encoding="utf-8"))
    except Exception:
        B = {"ideas": {}}
    try:
        prev = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    import yfinance as yf
    out = {"at": now.strftime("%F %H:%M"), "signals": [], "state": {}, "errors": []}
    I = B.get("ideas", {})
    # ── 6·7 종목 신호
    need = {}
    for idea in ("nh52", "pead"):
        if idea in I:
            P = _parse_rule(I[idea]["pick"]["rule"])
            for m in P.get("mkts", []):
                need.setdefault(m, []).append((idea, P))
    for m, ideas in need.items():
        try:
            isym, minp, minvol = AB.MKT[m]
            lg = {}
            if m == "US":
                tks = AB.universe(m, lg)
                names = {}
            else:
                u = json.load(open(AB.UNID / f"{m}.json", encoding="utf-8"))["u"]
                names = {t: n for t, n in u}
                tks = [t for t, _ in u]
            ix = yf.download(isym, period="2y", auto_adjust=True, progress=False)["Close"]
            if isinstance(ix, pd.DataFrame):
                ix = ix.iloc[:, 0]
            ix = ix.dropna()
            reg_on = bool(ix.iloc[-1] > ix.rolling(200).mean().iloc[-1])
            out["state"][f"index_{m}"] = {"sym": isym, "above200": reg_on, "d": str(ix.index[-1].date())}
            got = 0
            for i in range(0, len(tks), 100):
                part = tks[i:i + 100]
                try:
                    d = yf.download(part, period="2y", auto_adjust=True, group_by="ticker", threads=True, progress=False)
                except Exception:
                    continue
                for t in part:
                    try:
                        x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
                        x = x.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close", "volume"])
                        if len(x) < 300:
                            continue
                        got += 1
                        F = feats(x, minp, minvol)
                        j = len(x) - 1
                        dte = x.index[j]
                        if (now.date() - dte.date()).days > 6:
                            continue
                        for idea, P in ideas:
                            if idea == "nh52":
                                hit = bool(F["liq"][j] and F["nh"][j] and F["vr"][j] >= P.get("거래량", 2) and (reg_on or not P.get("지수200선위")))
                            else:
                                hit = bool(F["liq"][j] and F["gap"][j] * 100 >= P.get("갭", 5) and F["o"][j] > F["ph"][j] and F["vr"][j] >= P.get("거래량", 2)
                                           and (F["c"][j] > F["hi60"][j] or not P.get("60일고가위")) and (8 <= dq_of(dte) <= 55 or not P.get("실적철")))
                            if hit:
                                out["signals"].append({"src": idea, "code": t, "name": names.get(t, t), "mkt": m, "d": str(dte.date()),
                                                       "vr": round(float(F["vr"][j]), 1), "gap": round(float(F["gap"][j]) * 100, 1),
                                                       "px": round(float(F["c"][j]), 4), "score": round(min(30.0, float(F["vr"][j]) * 5), 1)})
                    except Exception:
                        continue
                time.sleep(0.5)
            out["state"][f"scanned_{m}"] = got
        except Exception as e:
            out["errors"].append(f"{m}: {e!r}"[:200])
    # ── 8 🩹 급락 되돌림 상태
    try:
        if "dip" in I:
            sym = I["dip"]["pick"]["rule"].split("|")[0]
            th = float(I["dip"]["pick"]["rule"].split("|")[1].split("<")[1])
            c = yf.download(sym, period="2y", auto_adjust=True, progress=False)["Close"]
            if isinstance(c, pd.DataFrame):
                c = c.iloc[:, 0]
            c = c.dropna()
            r2 = rsi2(c)
            st = {"sym": sym, "d": str(c.index[-1].date()), "close": round(float(c.iloc[-1]), 2), "ma200": round(float(c.rolling(200).mean().iloc[-1]), 2),
                  "ma5": round(float(c.rolling(5).mean().iloc[-1]), 2), "rsi2": round(float(r2.iloc[-1]), 1), "th": th}
            st["signal"] = bool(st["close"] > st["ma200"] and st["rsi2"] < th)
            out["state"]["dip"] = st
            if st["signal"]:
                out["signals"].append({"src": "dip", "code": sym, "name": sym, "mkt": "US", "d": st["d"], "px": st["close"], "score": 0, "rsi2": st["rsi2"]})
    except Exception as e:
        out["errors"].append(f"dip: {e!r}"[:200])
    # ── 10 🧭 추세 상태 (오늘 들고 있어야 할 자산)
    try:
        if "trend" in I:
            nin, nout = (int(x) for x in I["trend"]["pick"]["rule"].split("|")[0].split("/"))
            px = ydl(TREND_U, start=(now - dt.timedelta(days=500)).strftime("%F"))
            st = {}
            for s, d in px.items():
                c, h, l = d["close"], d["high"], d["low"]
                hiN, loM = h.shift(1).rolling(nin).max(), l.shift(1).rolling(nout).min()
                # 마지막 신호가 「들어가라」였는지 「나와라」였는지 거슬러 찾기
                state, since = False, None
                for k in range(len(c)):
                    if not np.isnan(hiN.iloc[k]) and c.iloc[k] > hiN.iloc[k] and not state:
                        state, since = True, str(c.index[k].date())
                    elif state and not np.isnan(loM.iloc[k]) and c.iloc[k] < loM.iloc[k]:
                        state, since = False, str(c.index[k].date())
                st[s] = {"on": state, "since": since, "close": round(float(c.iloc[-1]), 2), "hi": round(float(hiN.iloc[-1]), 2), "lo": round(float(loM.iloc[-1]), 2),
                         "d": str(c.index[-1].date())}
            out["state"]["trend"] = {"rule": f"{nin}일 고가 돌파 → 사고 · {nout}일 저가 이탈 → 팖", "assets": st}
    except Exception as e:
        out["errors"].append(f"trend: {e!r}"[:200])
    # 최근 30일 기록 (킥 장부가 하루 빠져도 놓치지 않게)
    cut = (now - dt.timedelta(days=30)).strftime("%F")
    log = {f"{s['src']}|{s['code']}|{s['d']}": s for s in prev.get("log", []) if s.get("d", "") >= cut}
    for s in out["signals"]:
        log[f"{s['src']}|{s['code']}|{s['d']}"] = s
    out["log"] = sorted(log.values(), key=lambda s: (s["d"], s["src"], s["code"]))
    LIVE.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"신호 {len(out['signals'])} · 기록 {len(out['log'])} · 오류 {out['errors']}")


if __name__ == "__main__":
    {"fetch": lambda: fetch(sys.argv[2]), "macro": macro, "stats": stats, "live": live}[sys.argv[1]]()
