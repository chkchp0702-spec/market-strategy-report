"""🔬 조용한 매집(Cup 스캐너 detect_accum) 과거 검증 — 왜 성적이 안 좋은지, 더 나은 규칙이 있는지

  python src/accum_bt.py fetch KR   → out/accum_rows_KR.csv.gz, out/accum_log_KR.json  (시세 받기 + 매일 검출)
  python src/accum_bt.py stats      → market/accum_bt.json  (out/accum_rows_*.csv.gz 모아 변형별 성적)

· 검출 함수는 Cup/.github/workflows/scan.yaml 의 detect_accum·_prep 를 그대로 옮김 (매일 그날까지의 데이터만 사용)
· 진입 = 신호 다음 거래일 종가, 왕복 비용 0.5% (한국 0.45%), 지수 대비 초과수익도 같이
· 2012~2019 에서 고르고(앞), 2020~ 에서 시험(뒤)
· 한 종목은 신호 뒤 20거래일 안에 다시 신호가 나와도 무시 (변형마다 따로 적용)
· 유니버스 = 오늘 상장 목록(생존자 편향 있음). 미국은 S&P500+S&P400 (위키백과, 실패 시 고정 목록)
"""
from __future__ import annotations
import datetime as dt
import gzip
import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTD = ROOT / "out"
UNID = ROOT / "src" / "lab" / "accum_uni"
RES = ROOT / "market" / "accum_bt.json"
KST = dt.timezone(dt.timedelta(hours=9))

START = "2010-06-01"
IS_START, IS_END, OOS_START = "2012-01-01", "2019-12-31", "2020-01-01"
# 스캐너와 같은 가격·거래대금 하한 (현지 통화)
MKT = {"KR": ("^KS11", 5000, 2e9), "US": ("^GSPC", 5, 5e6), "HK": ("^HSI", 3, 2e7),
       "JP": ("^N225", 500, 2e8), "CN": ("000001.SS", 5, 5e7)}
COST = {"KR": 0.0045}
DEF_COST = 0.005
TIME_BUDGET = 38 * 60   # 시세 받기에 쓸 최대 시간(초)

A = dict(win=20, base=60, volx_min=3.0, chg_lo=-5.0, chg_hi=3.0, days2x_min=10, off52_max=40.0, show_min=55)
HZ = (5, 10, 20, 40, 60)


# ───────────────────────────── 검출 (scan.yaml 그대로) ─────────────────────────────
def detect_accum(o, h, l, c, v, minp, minvol):
    """o,h,l,c,v: 그날까지(포함)의 배열 (이미 NaN 행 제거됨). scan.yaml 의 _prep + detect_accum 과 같은 계산."""
    if len(c) < 150:
        return None
    last = float(c[-1])
    if last < minp:
        return None
    advol = float(np.nanmean(c[-50:] * v[-50:]))
    if minvol and advol < minvol:
        return None
    n = len(c)
    W, B = A["win"], A["base"]
    if n < W + B + 20:
        return None
    vw, vb = v[-W:], v[-W - B:-W]
    base_v = float(np.nanmean(vb))
    if base_v <= 0:
        return None
    volx = float(np.nanmean(vw)) / base_v
    if volx < A["volx_min"]:
        return None
    chg = (c[-1] / c[-W - 1] - 1) * 100
    if not (A["chg_lo"] <= chg <= A["chg_hi"]):
        return None
    days2x = int(np.sum(vw >= base_v * 2))
    if days2x < A["days2x_min"]:
        return None
    hi52 = float(np.max(h[-252:])) if n >= 252 else float(np.max(h))
    off52 = (1 - last / hi52) * 100
    if off52 > A["off52_max"]:
        return None
    cw = c[-W - 1:]
    dc = np.diff(cw)
    upv = float(np.sum(vw[dc > 0])); dnv = float(np.sum(vw[dc < 0]))
    ud = upv / dnv if dnv > 0 else 9.0
    big = vw >= base_v * 2
    rng = h[-W:] - l[-W:]
    clv = np.where(rng > 0, (c[-W:] - l[-W:]) / np.where(rng > 0, rng, 1), 0.5)
    clv_big = float(np.mean(clv[big])) if big.any() else 0.5
    prev = (c[-W - 1] / c[-W - B - 1] - 1) * 100
    lo1, lo2 = float(np.min(l[-W:-W // 2])), float(np.min(l[-W // 2:]))
    hl = (lo2 / lo1 - 1) * 100 if lo1 > 0 else 0.0
    tr = rng / c[-W:]
    contr = float(np.mean(tr[-W // 2:]) / max(np.mean(tr[:W // 2]), 1e-9))
    sc = 0.0
    sc += 30 if volx >= 5 else 24 if volx >= 4 else 18
    sc += 20 if days2x >= 15 else 14 if days2x >= 12 else 8
    sc += 25 if ud >= 1.5 else 18 if ud >= 1.2 else 10 if ud >= 0.9 else 0
    sc += 15 if prev <= 0 else 10 if prev <= 20 else 3 if prev <= 50 else 0
    sc += 10 if off52 <= 15 else 6 if off52 <= 30 else 2
    sc += 5 if hl > 0 else 0
    sc += 5 if contr <= 0.8 else 0
    sc += 5 if clv_big >= 0.6 else (-5 if clv_big <= 0.35 else 0)
    dist = bool(ud <= 0.8 or prev >= 50)
    if dist:
        sc -= 15
    tag = ("분배 의심" if dist else "강한 매집" if (ud >= 1.5 and clv_big >= 0.55) else "매집" if ud >= 1.1 else "중립")
    return dict(score=round(float(np.clip(sc, 0, 100)), 1), tag=tag, dist=int(dist), volx=round(volx, 2),
                chg=round(chg, 2), days2x=days2x, ud=round(ud, 3), clv=round(clv_big, 3), prev=round(prev, 1),
                hl=round(hl, 2), contr=round(contr, 3), off52=round(off52, 1), advol=advol,
                box_hi=float(np.max(h[-W:])), box_hic=float(np.max(c[-W:])))


# ───────────────────────────── 유니버스·시세 ─────────────────────────────
US_FALLBACK = ("AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO JPM V MA UNH XOM JNJ PG HD COST ABBV MRK LLY PEP KO WMT BAC CRM "
               "ORCL ADBE CSCO ACN MCD TMO ABT DHR NKE TXN QCOM INTC AMD AMAT LRCX KLAC MU ADI NFLX DIS CMCSA T VZ PFE "
               "BMY AMGN GILD CVS CI HUM ELV MDT SYK ISRG BSX ZBH BDX EW GE HON CAT DE MMM UPS FDX UNP CSX NSC LMT RTX "
               "BA NOC GD GS MS C WFC SCHW BLK SPGI MCO ICE CME AXP COF USB PNC TFC MET PRU AIG ALL TRV CB PGR").split()


def universe(m: str, log: dict) -> list[str]:
    if m == "US":
        tk = []
        try:
            import requests
            hd = {"User-Agent": "Mozilla/5.0 (research script)"}
            for pg in ("List_of_S%26P_500_companies", "List_of_S%26P_400_companies"):
                r = requests.get(f"https://en.wikipedia.org/wiki/{pg}", headers=hd, timeout=30)
                tabs = pd.read_html(io.StringIO(r.text))
                for t in tabs:
                    col = next((x for x in t.columns if str(x).lower() in ("symbol", "ticker symbol", "ticker")), None)
                    if col is not None and len(t) > 300:
                        tk += [str(s).strip().replace(".", "-") for s in t[col].dropna()]
                        break
            tk = sorted(set(tk))
            log["us_source"] = f"wikipedia S&P500+400 ({len(tk)})"
        except Exception as e:
            log["us_source_err"] = repr(e)[:200]
        if len(tk) < 500:
            tk = US_FALLBACK
            log["us_source"] = f"fallback ({len(tk)})"
        return tk
    u = [t for t, _ in json.load(open(UNID / f"{m}.json", encoding="utf-8"))["u"]]
    if m == "CN":   # 스캐너처럼 창업판·과창판 제외 (후강퉁 필터는 과거 목록이 없어 생략, 거래대금 하한만)
        u = [t for t in u if not t[:3] in ("300", "301", "302", "688", "689")]
    return u


def download(tks: list[str], log: dict, t0: float) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out, CH = {}, 80
    fails = 0
    for i in range(0, len(tks), CH):
        if time.time() - t0 > TIME_BUDGET:
            log["cut_at"] = i
            break
        part = tks[i:i + CH]
        for att in range(3):
            try:
                d = yf.download(part, start=START, auto_adjust=True, group_by="ticker", threads=True, progress=False)
                break
            except Exception as e:
                d = None
                time.sleep(10 * (att + 1))
        if d is None or d.empty:
            fails += len(part)
            continue
        for t in part:
            try:
                x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
                x = x.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
                x = x.dropna(subset=["high", "low", "close", "volume"])
                if len(x) >= 200:
                    out[t] = x
                else:
                    fails += 1
            except Exception:
                fails += 1
        time.sleep(1.0)
    log["requested"], log["got"], log["failed_or_short"] = len(tks), len(out), fails
    return out


def idx_series(sym: str) -> pd.Series:
    import yfinance as yf
    for att in range(3):
        try:
            d = yf.download(sym, start=START, auto_adjust=True, progress=False)
            c = d["Close"]
            if isinstance(c, pd.DataFrame):
                c = c.iloc[:, 0]
            return c.dropna()
        except Exception:
            time.sleep(10)
    return pd.Series(dtype=float)


# ───────────────────────────── 매매 결과 계산 ─────────────────────────────
def fwd(c: np.ndarray, ix: np.ndarray, e: int, cost: float, pre: str) -> dict:
    """e = 진입 바 인덱스(그날 종가에 산다). 고정 20/40/60일, −8% 손절(60일 한도), 고점 대비 −15% 추적손절(60일 한도)."""
    o = {}
    n = len(c)
    if e >= n or not (c[e] > 0):
        return o
    for k in HZ:
        if e + k < n:
            r = c[e + k] / c[e] - 1
            o[f"{pre}r{k}"] = round((r - cost) * 100, 2)
            if ix[e] > 0 and ix[e + k] > 0:
                o[f"{pre}x{k}"] = round((r - cost - (ix[e + k] / ix[e] - 1)) * 100, 2)
    if e + 60 < n:
        for nm, kind in (("s8", "stop"), ("tr", "trail")):
            pk, ex = c[e], e + 60
            for d in range(1, 61):
                p = c[e + d]
                pk = max(pk, p)
                if (kind == "stop" and p <= c[e] * 0.92) or (kind == "trail" and p <= pk * 0.85):
                    ex = e + d
                    break
            r = c[ex] / c[e] - 1
            o[f"{pre}{nm}"] = round((r - cost) * 100, 2)
            if ix[e] > 0 and ix[ex] > 0:
                o[f"{pre}{nm}x"] = round((r - cost - (ix[ex] / ix[e] - 1)) * 100, 2)
            o[f"{pre}{nm}d"] = ex - e
    return o


def fetch(m: str):
    t0 = time.time()
    OUTD.mkdir(exist_ok=True)
    isym, minp, minvol = MKT[m]
    cost = COST.get(m, DEF_COST)
    log = {"market": m, "start": START}
    tks = universe(m, log)
    idx = idx_series(isym)
    log["index_bars"] = len(idx)
    data = download(tks, log, t0)
    log["download_sec"] = round(time.time() - t0)
    # 시장 안 6개월 수익률 백분위 (그날 기준)
    closes = pd.DataFrame({t: d["close"] for t, d in data.items()})
    closes = closes.sort_index()
    r126 = closes.pct_change(126, fill_method=None)
    rsp = r126.rank(axis=1, pct=True)
    i200 = idx.rolling(200).mean()
    reg = (idx > i200).astype(float).where(i200.notna())
    rows = []
    CTRL, SURGE = [], []
    W, B = A["win"], A["base"]
    for t, d in data.items():
        o, h, l, c, v = (d[x].to_numpy(float) for x in ("open", "high", "low", "close", "volume"))
        n = len(c)
        if n < 150:
            continue
        dates = d.index
        # 빠른 1차 거르기 (검출 함수의 앞 조건과 같은 계산) → 통과한 날만 정식 검출
        vs = pd.Series(v)
        mw = vs.rolling(W).mean().to_numpy()
        mb = vs.shift(W).rolling(B).mean().to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            vx = mw / mb
            ch = (c / np.roll(c, W) - 1) * 100
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        # ── 비교군: (A) 아무 날 아무 종목(같은 가격·거래대금 하한, 10거래일마다 하나), (B) 거래량 폭증+가격 급등, (C) 거래량 폭증+가격 급락
        with np.errstate(divide="ignore", invalid="ignore"):
            adv = pd.Series(c * v).rolling(50).mean().to_numpy()
            liq = (adv >= minvol) & (c >= minp) & (np.arange(n) >= 149)
            fx = {}
            for k in (20, 40, 60):
                e = np.arange(n) + 1
                ok = e + k < n
                rr = np.full(n, np.nan); ii = np.full(n, np.nan)
                rr[ok] = c[e[ok] + k] / c[e[ok]] - 1
                ii[ok] = ixa[e[ok] + k] / ixa[e[ok]] - 1
                fx[k] = ((rr - cost) * 100, (rr - cost - ii) * 100)
        dnum = dates.year * 10000 + dates.month * 100 + dates.day
        for ti in np.where(liq & (np.arange(n) % 10 == 0))[0]:
            CTRL.append((dnum[ti], fx[20][1][ti], fx[40][1][ti], fx[60][1][ti], fx[20][0][ti], fx[40][0][ti], fx[60][0][ti]))
        for kind, msk in (("up", ch > 10), ("dn", ch < -10)):
            last_k = -10 ** 9
            for ti in np.where(liq & (vx >= 3) & msk)[0]:
                if ti - last_k < 20:
                    continue
                bv = np.mean(v[ti - 79:ti - 19])
                if bv <= 0 or np.sum(v[ti - 19:ti + 1] >= 2 * bv) < 10:
                    continue
                last_k = ti
                SURGE.append((kind, t, dnum[ti], fx[20][1][ti], fx[40][1][ti], fx[60][1][ti], fx[40][0][ti]))
        cand = np.where((vx >= A["volx_min"] * 0.999) & (ch >= A["chg_lo"] - 0.01) & (ch <= A["chg_hi"] + 0.01))[0]
        cand = cand[cand >= 149]
        if not len(cand):
            continue
        rga = reg.reindex(dates).ffill().to_numpy(float)
        ma50 = pd.Series(c).rolling(50).mean().to_numpy()
        ma200 = pd.Series(c).rolling(200).mean().to_numpy()
        for ti in cand:
            s0 = 0 if ti < 320 else ti - 300
            r = detect_accum(o[s0:ti + 1], h[s0:ti + 1], l[s0:ti + 1], c[s0:ti + 1], v[s0:ti + 1], minp, minvol)
            if r is None:
                continue
            dte = dates[ti]
            r.update(tk=t, mkt=m, date=str(dte.date()), ti=int(ti))
            try:
                r["rs6"] = round(float(rsp.at[dte, t]), 3)
            except Exception:
                r["rs6"] = np.nan
            r["a50"] = int(c[ti] > ma50[ti]) if not np.isnan(ma50[ti]) else -1
            r["a200"] = int(c[ti] > ma200[ti]) if not np.isnan(ma200[ti]) else -1
            r["reg"] = int(rga[ti]) if not np.isnan(rga[ti]) else -1
            r["r6"] = round((c[ti] / c[ti - 126] - 1) * 100, 1) if ti >= 126 else np.nan
            r.update(fwd(c, ixa, ti + 1, cost, ""))
            # 돌파 확인: 신호 뒤 10거래일 안에 종가가 매집 구간(20일) 고가를 넘으면 그다음 날 종가에 진입
            bo = None
            for j in range(ti + 1, min(ti + 11, n)):
                if c[j] > r["box_hi"]:
                    bo = j
                    break
            if bo is not None:
                r["b_d"] = bo - ti
                r.update(fwd(c, ixa, bo + 1, cost, "b_"))
            # 종가 기준 박스(20일 최고 종가) 돌파 — 더 느슨한 버전
            bo2 = None
            for j in range(ti + 1, min(ti + 11, n)):
                if c[j] > r["box_hic"]:
                    bo2 = j
                    break
            if bo2 is not None:
                r["c_d"] = bo2 - ti
                r.update(fwd(c, ixa, bo2 + 1, cost, "c_"))
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUTD / f"accum_rows_{m}.csv.gz", index=False, compression="gzip")
    np.save(OUTD / f"accum_ctrl_{m}.npy", np.array(CTRL, dtype=np.float64).reshape(-1, 7))
    pd.DataFrame(SURGE, columns=["kind", "tk", "d", "x20", "x40", "x60", "r40"]).assign(mkt=m).to_csv(
        OUTD / f"accum_surge_{m}.csv.gz", index=False, compression="gzip")
    log["ctrl_n"], log["surge_n"] = len(CTRL), len(SURGE)
    log["raw_rows"] = len(df)
    log["sec"] = round(time.time() - t0)
    log["last_date"] = str(closes.index.max().date()) if len(closes) else None
    json.dump(log, open(OUTD / f"accum_log_{m}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(log, ensure_ascii=False))


# ───────────────────────────── 변형별 성적 ─────────────────────────────
def dedupe(g: pd.DataFrame, gap=20) -> pd.DataFrame:
    g = g.sort_values(["tk", "ti"])
    keep, last_tk, last_ti = [], None, -10 ** 9
    for tk, ti in zip(g["tk"].to_numpy(), g["ti"].to_numpy()):
        if tk != last_tk:
            last_tk, last_ti = tk, -10 ** 9
        if ti - last_ti >= gap:
            keep.append(True)
            last_ti = ti
        else:
            keep.append(False)
    return g[np.array(keep, dtype=bool)]


def pstats(x: pd.Series) -> dict:
    x = x.dropna()
    if len(x) == 0:
        return {"n": 0}
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    return {"n": int(len(x)), "avg": round(float(x.mean()), 2), "avg_w": round(float(x.clip(-100, 300).mean()), 2),
            "glitch": int((x.abs() > 1000).sum()), "med": round(float(x.median()), 2),
            "win": round(float((x > 0).mean()) * 100, 1), "pf": round(float(pos / neg), 2) if neg > 0 else None,
            "p10": round(float(x.quantile(0.1)), 1)}


def summarize(t: pd.DataFrame, pre: str = "", exits=True) -> dict:
    o = {"n": int(len(t))}
    for k in HZ:
        o[f"r{k}"] = pstats(t.get(f"{pre}r{k}", pd.Series(dtype=float)))
        o[f"x{k}"] = pstats(t.get(f"{pre}x{k}", pd.Series(dtype=float)))
    if exits:
        for nm in ("s8", "tr"):
            o[nm] = pstats(t.get(f"{pre}{nm}", pd.Series(dtype=float)))
            o[nm + "x"] = pstats(t.get(f"{pre}{nm}x", pd.Series(dtype=float)))
            if f"{pre}{nm}d" in t:
                o[nm + "_days"] = round(float(t[f"{pre}{nm}d"].mean()), 1) if t[f"{pre}{nm}d"].notna().any() else None
    return o


def variants() -> dict:
    """이름 → (조건 함수, 진입 접두어). 진입 접두어: '' = 신호 다음날, 'b_' = 고가 돌파 다음날, 'c_' = 종가 박스 돌파 다음날"""
    base = lambda d: d["score"] >= 55
    nodist = lambda d: (d["dist"] == 0) & (d["prev"] > -30)
    strong = lambda d: (d["ud"] >= 1.5) & (d["clv"] >= 0.55)
    rs = lambda d: d["rs6"] >= 0.7
    ma = lambda d: (d["a50"] == 1) & (d["a200"] == 1)
    reg = lambda d: d["reg"] == 1
    V = {
        "V0_기준(점수55)": (base, ""),
        "V0b_검출 전부(점수무관)": (lambda d: d["score"] >= 0, ""),
        "V1_점수70": (lambda d: d["score"] >= 70, ""),
        "V2_돌파확인(고가)": (base, "b_"),
        "V2c_돌파확인(종가)": (base, "c_"),
        "V3a_상대강도상위30%": (lambda d: base(d) & rs(d), ""),
        "V3b_50·200일선 위": (lambda d: base(d) & ma(d), ""),
        "V3c_RS30%+이평선": (lambda d: base(d) & rs(d) & ma(d), ""),
        "V4_지수200일선 위": (lambda d: base(d) & reg(d), ""),
        "V5_강한매집": (lambda d: base(d) & strong(d), ""),
        "V6_분배·급락 제외": (lambda d: base(d) & nodist(d), ""),
        "V7_돌파+RS": (lambda d: base(d) & rs(d), "b_"),
        "V7b_돌파+이평선": (lambda d: base(d) & ma(d), "b_"),
        "V7c_돌파+지수": (lambda d: base(d) & reg(d), "b_"),
        "V7d_돌파+분배제외": (lambda d: base(d) & nodist(d), "b_"),
        "V8_RS+지수": (lambda d: base(d) & rs(d) & reg(d), ""),
        "V8b_이평선+지수": (lambda d: base(d) & ma(d) & reg(d), ""),
        "V9_돌파+RS+지수": (lambda d: base(d) & rs(d) & reg(d), "b_"),
        "V9b_돌파+이평선+지수": (lambda d: base(d) & ma(d) & reg(d), "b_"),
        "V10_강한매집+이평선": (lambda d: base(d) & strong(d) & ma(d), ""),
        "V10b_강한매집+돌파": (lambda d: base(d) & strong(d), "b_"),
    }
    return V


def stats():
    fs = sorted(OUTD.glob("accum_rows_*.csv.gz"))
    df = pd.concat([pd.read_csv(f, dtype={"tk": str}) for f in fs], ignore_index=True)
    logs = {}
    for f in sorted(OUTD.glob("accum_log_*.json")):
        lg = json.load(open(f, encoding="utf-8"))
        logs[lg["market"]] = lg
    df = df[df["date"] >= IS_START]
    per = {"IS": df[df["date"] <= IS_END], "OOS": df[df["date"] >= OOS_START]}
    out = {"made": dt.datetime.now(KST).strftime("%F %H:%M"),
           "rule": {"params": A, "entry": "신호 다음 거래일 종가", "cost": "왕복 0.5% (한국 0.45%)",
                    "is": f"{IS_START}~{IS_END}", "oos": f"{OOS_START}~", "dedupe": "같은 종목 20거래일 안 재신호 무시",
                    "avg_w": "평균을 −100%~+300% 로 자른 값 (시세 오류 한두 개가 평균을 망치는 것 방지)", "exits": "r/x=고정 20·40·60일(수익/지수초과), s8=−8% 손절·60일 한도, tr=고점대비 −15% 추적·60일 한도"},
           "logs": logs, "raw_rows": int(len(df)), "variants": {}, "by_market": {}, "diag": {}}
    V = variants()
    mk = sorted(df["mkt"].unique())
    for name, (fn, pre) in V.items():
        out["variants"][name] = {}
        out["by_market"][name] = {}
        for pn, d in per.items():
            sel = d[fn(d).fillna(False).astype(bool)]
            if pre:   # 돌파가 나온 신호만 남긴 뒤 중복 제거 (실시간: 신호 종목을 지켜보다 돌파하면 산다)
                sel = sel[sel[f"{pre}d"].notna()] if f"{pre}d" in sel else sel.iloc[0:0]
            sel = dedupe(sel)
            out["variants"][name][pn] = summarize(sel, pre)
            out["by_market"][name][pn] = {m: summarize(sel[sel["mkt"] == m], pre, exits=False) for m in mk}
    # 진단: 기준 규칙 안에서 특징별로 쪼개 보기 (40일 지수초과)
    def buck(d, col, edges, labels):
        return pd.cut(d[col], edges, labels=labels)
    diag_spec = {
        "tag": None,
        "score": ([-1, 54.9, 64.9, 74.9, 101], ["<55", "55-64", "65-74", "75+"]),
        "ud": ([-1, 0.8, 1.1, 1.5, 99], ["≤0.8", "0.8-1.1", "1.1-1.5", ">1.5"]),
        "prev": ([-999, -30, 0, 20, 50, 9999], ["<-30", "-30~0", "0~20", "20~50", "≥50"]),
        "volx": ([0, 4, 5, 8, 1e9], ["3-4", "4-5", "5-8", "8+"]),
        "clv": ([-1, 0.35, 0.55, 2], ["≤0.35", "0.35-0.55", ">0.55"]),
        "off52": ([-1, 15, 30, 41], ["≤15", "15-30", "30-40"]),
        "rs6": ([-1, 0.3, 0.7, 1.01], ["하위30%", "중간", "상위30%"]),
        "reg": ([-2, 0.5, 2], ["지수<200일선", "지수>200일선"]),
        "a200": ([-2, 0.5, 2], ["주가<200일선", "주가>200일선"]),
        "chg": ([-6, -2, 1, 3.1], ["-5~-2", "-2~1", "1~3"]),
    }
    for pn, d in per.items():
        allg = dedupe(d)            # 검출된 것 전부 (점수 무관) 기준으로 특징별
        out["diag"][pn] = {}
        for col, spec in diag_spec.items():
            if spec is None:
                grp = allg[col]
            else:
                grp = buck(allg, col, *spec)
            res = {}
            for k, g in allg.groupby(grp, observed=True):
                res[str(k)] = {"n": int(len(g)), "x20": pstats(g["x20"]).get("avg"), "x40": pstats(g["x40"]).get("avg"),
                               "x60": pstats(g["x60"]).get("avg"), "win40": pstats(g["r40"]).get("win"),
                               "pf40": pstats(g["r40"]).get("pf")}
            out["diag"][pn][col] = res
        # 연도별 기준 규칙
        b = dedupe(d[d["score"] >= 55])
        out["diag"][pn]["year"] = {str(y): {"n": int(len(g)), "x40": pstats(g["x40"]).get("avg"), "r40": pstats(g["r40"]).get("avg")}
                                   for y, g in b.groupby(b["date"].str[:4])}
    # 비교군
    out["controls"] = {}
    ctrl = {}
    for f in sorted(OUTD.glob("accum_ctrl_*.npy")):
        ctrl[f.stem.split("_")[-1]] = np.load(f)
    sg = [pd.read_csv(f, dtype={"tk": str}) for f in sorted(OUTD.glob("accum_surge_*.csv.gz"))]
    sg = pd.concat(sg, ignore_index=True) if sg else pd.DataFrame()
    rng_ = {"IS": (20120101, 20191231), "OOS": (20200101, 99999999)}
    for pn, (a, b) in rng_.items():
        oc = {}
        for m in mk + ["ALL"]:
            arr = np.concatenate(list(ctrl.values())) if m == "ALL" else ctrl.get(m, np.zeros((0, 7)))
            arr = arr[(arr[:, 0] >= a) & (arr[:, 0] <= b)] if len(arr) else arr
            cm = {"random": {f"x{k}": pstats(pd.Series(arr[:, i])) for i, k in ((1, 20), (2, 40), (3, 60))}}
            cm["random"]["r40"] = pstats(pd.Series(arr[:, 5])) if len(arr) else {"n": 0}
            if len(sg):
                s2 = sg[(sg["d"] >= a) & (sg["d"] <= b) & ((sg["mkt"] == m) | (m == "ALL"))]
                for kd in ("up", "dn"):
                    g = s2[s2["kind"] == kd]
                    cm["surge_" + kd] = {"x20": pstats(g["x20"]), "x40": pstats(g["x40"]), "x60": pstats(g["x60"]), "r40": pstats(g["r40"])}
            oc[m] = cm
        out["controls"][pn] = oc
    RES.parent.mkdir(exist_ok=True)
    json.dump(out, open(RES, "w"), ensure_ascii=False, indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x)
    print("rows", len(df), {m: int((df["mkt"] == m).sum()) for m in mk})


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(sys.argv[2])
    else:
        stats()
