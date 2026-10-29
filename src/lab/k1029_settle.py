"""📈 10/29 14시 — 💸 「국채 결제일 현금 빨림」: 그날 실제로 결제되는 국채 순발행 금액(재무부 DTS)이 큰 날 앞뒤로 주식 덜기
  바깥 재료: Interactive Advisors(Mott)·Seeking Alpha·Tiger 「Treasury Settlement Drains $150 Billion — Risk Assets Under Pressure」 류 글.
  메커니즘: 큰 국채 발행이 결제되는 날 투자자·딜러가 현금을 내고 국채를 받음 → 단기자금(레포·MMF)·은행 지준이 억지로 빠짐.
  12시 순유동성(TGA 「누적 변화」)과 다른 점: 달력(15일·월말)이 아니라 「그날 결제 금액 크기」, 앞으로 올 결제를 미리 앎(입찰 결과 = 결제 2영업일 이상 전 공개).
  자료: 재무부 DTS public_debt_transactions(시장성 국채 발행 − 상환, 하루, 십억 달러) — 2005~.
  큰 날 = 그날 순발행이 지난 504거래일 순발행 분포의 q 분위 위(과거 자료만으로 문턱).
  ① 맞대기: 창(window) 안 SPY−IEF 하루 평균 bp, 큰 날 vs 그 밖 / 대조군 = 15일·월말인데 작은 날
  ② 💼(월말 흐름 포함 k1028_qflow 틀) 위: 창 안에서 주식 칸 × (1−f) → 🧭추세 칸 · 격자 q{0.8,0.9}×창{pre,on,post,around}×f{0.3,0.5}
     앞에서 고르고 뒤 시험 · ±20% 흔들기 · 뒤집은 대조군(순상환 큰 날 덜기) · 🎯 도 같은 판
  하루 늦은 체결(core_run: i 종가 신호 → i+1 보유) · 회전 × 0.1% · 레버리지 없음 · ETF 만(생존 편향 없음)
→ market/lab/k1029_settle.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import core_run, make, drifts, G_PORT, RD_PORT, G_CONC, RD_CONC

OUT = Path("market/lab/k1029_settle.json")
MK = ("Bill", "Note", "Bond", "Inflation", "TIPS", "Floating", "FRN")
BAD = ("Total", "Savings", "Government Account", "State and Local", "Foreign", "Domestic Series", "Other", "Federal Financing", "Matured", "Agency")


def _get(url, log, key, tries=4, to=90):
    import requests
    for _ in range(tries):
        try:
            r = requests.get(url, timeout=to, headers={"User-Agent": "Mozilla/5.0 (research script)"})
            if r.status_code == 200:
                return r.json()
            log[key] = f"http {r.status_code}"
        except Exception as e:
            log[key] = repr(e)[:160]
        time.sleep(4)
    return None


def net_issue(log):
    base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/public_debt_transactions"
    rows, page = [], 1
    while page < 80:
        j = _get(f"{base}?filter=record_date:gte:2005-01-01&page[size]=10000&page[number]={page}", log, "DTS")
        if not j:
            break
        rows += j.get("data", [])
        if page >= int(j.get("meta", {}).get("total-pages", 1)):
            break
        page += 1
    if not rows:
        return None
    kinds = {}
    iss, red = {}, {}
    for r in rows:
        tt = r.get("transaction_type") or ""; mk = r.get("security_market") or ""; st = r.get("security_type") or ""
        k = f"{tt}|{mk}|{st}"; kinds[k] = kinds.get(k, 0) + 1
        if mk and "Nonmarketable" in mk:
            continue
        if not any(m in st for m in MK) or any(b in st for b in BAD):
            continue
        try:
            v = float(r.get("transaction_today_amt")) / 1000.0
        except (TypeError, ValueError):
            continue
        d = pd.Timestamp(r["record_date"])
        if tt.startswith("Issue"):
            iss[d] = iss.get(d, 0.0) + v
        elif tt.startswith("Redemp"):
            red[d] = red.get(d, 0.0) + v
    days = sorted(set(iss) | set(red))
    s = pd.Series({d: iss.get(d, 0.0) - red.get(d, 0.0) for d in days}).sort_index()
    log["kinds_top"] = dict(sorted(kinds.items(), key=lambda x: -x[1])[:40])
    log["net"] = f"{len(s)}일 {s.index.min().date()}~{s.index.max().date()} · 중앙 {s.median():.1f}bn · 90% {s.quantile(0.9):.1f}bn · 최근 {s.iloc[-1]:.1f}bn"
    log["yearly_q90"] = {int(y): round(float(g.quantile(0.9)), 1) for y, g in s.groupby(s.index.year)}
    log["top10"] = {str(d.date()): round(float(v), 1) for d, v in s.nlargest(10).items()}
    return s


WIN = {"pre": (-1, 0), "on": (0, 0), "post": (1, 2), "around": (-1, 1)}


def main():
    log = {}
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    N = net_issue(log)
    out["log"] = log
    if N is None or len(N) < 1000:
        out["verdict"] = "➖ DTS 자료를 못 받음"
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"); print(out); return
    Nc = N.reindex(C.index).fillna(0.0)
    pos = {d: i for i, d in enumerate(C.index)}

    def big(q, inv=False):
        x = -Nc if inv else Nc
        thr = x.shift(1).rolling(504, min_periods=250).quantile(q)
        return (x > thr) & (x > 0)

    def held(q, win, inv=False):
        """창 안 날(보유일) 표시"""
        b = big(q, inv).values; h = np.zeros(len(b), bool)
        a0, a1 = WIN[win]
        for i in np.where(b)[0]:
            h[max(0, i + a0):min(len(b), i + a1 + 1)] = True
        return pd.Series(h, index=C.index)

    def flag(q, win, inv=False):
        # core_run: sc.iloc[i] → i+1 보유. 보유일 h[i+1] → flag[i]. pre 창의 가장 이른 판단 = 결제 2영업일 전 종가(입찰 결과 공개 뒤)
        return held(q, win, inv).shift(-1).fillna(False).astype(bool)

    R = (C["SPY"].pct_change() - C["IEF"].pct_change())
    cal = pd.Series([(d.day in (14, 15, 16)) or (i + 1 < len(C.index) and C.index[i + 1].month != d.month) for i, d in enumerate(C.index)], index=C.index)
    ls = {}
    for q in (0.8, 0.9):
        for win in WIN:
            h = held(q, win)
            o = {}
            for p, a, b in (("is", START, IS_END), ("oos", OOS_START, END)):
                m = (C.index >= a) & (C.index <= b)
                x1 = R[m & h.values].dropna(); x0 = R[m & ~h.values].dropna()
                bigd = big(q).values
                ctrl_days = held_from = None
                # 대조군: 15일·월말 근처인데 큰 날 아님 → 같은 창
                cb = (cal.values & ~bigd & (Nc.values > -1e9)); hc = np.zeros(len(cb), bool); a0, a1 = WIN[win]
                for i in np.where(cb)[0]:
                    hc[max(0, i + a0):min(len(cb), i + a1 + 1)] = True
                xc = R[m & hc & ~h.values].dropna()
                t = x1.mean() / (x1.std() / math.sqrt(len(x1))) if len(x1) > 5 else None
                o[p] = {"n": int(len(x1)), "big_bp": round(float(x1.mean()) * 1e4, 1), "else_bp": round(float(x0.mean()) * 1e4, 1),
                        "calctrl_bp": round(float(xc.mean()) * 1e4, 1) if len(xc) else None, "t": round(float(t), 2) if t else None,
                        "spy_big_bp": round(float(C["SPY"].pct_change()[m & h.values].mean()) * 1e4, 1)}
            ls[f"q{q}_{win}"] = o
    out["ls"] = ls
    print("LS", json.dumps(ls), flush=True)

    def go(base="port", q=None, win="on", f=0.0, inv=False):
        G, Rd = (G_PORT, RD_PORT) if base == "port" else (G_CONC, RD_CONC)
        tgt, floor = (15.0, 0.30) if base == "port" else (22.0, 0.70)
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        if q:
            sc = sc * (1 - f * flag(q, win, inv).astype(float))
        sig, fs = make(C, DM, DQ)
        nav, td = core_run(C, reg, idx, sc, sig, fs, G, Rd)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        d = nav.pct_change().fillna(0)
        o["y"] = {y: round(((1 + d[d.index.year == y]).prod() - 1) * 100, 2) for y in range(2009, idx[-1].year + 1)}
        return o

    def dlt(a, b):
        r = {p: {k: round(float(b[p][k] - a[p][k]), 2) for k in ("cagr", "mdd", "sharpe", "vol")} for p in ("is", "oos")}
        r["y"] = {y: round(b["y"][y] - a["y"][y], 2) for y in a["y"]}
        r["turn_oos"] = b["oos"].get("turn")
        return r

    res = {}
    for base in ("port", "conc"):
        B = go(base); g = {}
        for q in (0.8, 0.9):
            for win in WIN:
                for f in (0.3, 0.5):
                    k = f"q{q}_{win}_f{f}"
                    g[k] = dlt(B, go(base, q, win, f))
                    print(base, k, g[k]["is"], g[k]["oos"], flush=True)
        pick = max(g, key=lambda k: g[k]["is"]["sharpe"] + g[k]["is"]["cagr"] / 10)
        q0 = float(pick.split("_")[0][1:]); w0 = pick.split("_")[1]; f0 = float(pick.split("_f")[-1])
        tail = 1 - q0
        sh = {}
        for nm, kw in {"tail-20%": dict(q=round(1 - tail * 0.8, 3)), "tail+20%": dict(q=round(1 - tail * 1.2, 3)),
                       "f-20%": dict(f=f0 * 0.8), "f+20%": dict(f=f0 * 1.2)}.items():
            kw2 = dict(q=q0, win=w0, f=f0); kw2.update(kw)
            sh[nm] = dlt(B, go(base, **kw2))
            print(base, "SHAKE", nm, sh[nm]["is"]["cagr"], sh[nm]["oos"]["cagr"], flush=True)
        ctrl = dlt(B, go(base, q0, w0, f0, inv=True))
        oos_pos = sum(1 for k in g if g[k]["oos"]["cagr"] > 0)
        pdx = g[pick]
        ok = pdx["is"]["cagr"] > 0 and pdx["oos"]["cagr"] > 0 and all(sh[k]["oos"]["cagr"] > 0 for k in sh)
        okdd = pdx["is"]["mdd"] > 0 and pdx["oos"]["mdd"] > 0 and pdx["oos"]["sharpe"] > 0 and all(sh[k]["oos"]["sharpe"] > 0 for k in sh)
        res[base] = {"B": {k: B[k] for k in ("is", "oos")}, "grid": g, "pick": pick, "pick_d": pdx, "shake": sh, "ctrl_inverse": ctrl,
                     "oos_pos": f"{oos_pos}/{len(g)}",
                     "grid_med_oos_cagr": round(float(pd.Series([g[k]['oos']['cagr'] for k in g]).median()), 2),
                     "verdict": "✅ 앞·뒤·흔들기 통과" if (ok or okdd) else "❌"}
        print(base, "PICK", pick, pdx["is"], pdx["oos"], res[base]["verdict"], flush=True)
    out["res"] = res
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
