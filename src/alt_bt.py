"""📦 나라별 「다른 자료」 신호 검증 (11/12 사용자: 「각 국의 쓸 수 있는, 할 수 있는 검증은 다 해」)

  신호 확률판(prob_bt)은 시세·금리·신용만 봤다. 여기선 나라마다 구할 수 있는 다른 종류의 자료를 같은 방식으로 본다.
  자료: market/lab/alt/*.csv (src/alt_fetch.py · 매주) — 🇺🇸 CAPE·PER·PBR·이익수익률(multpl) · AAII 개인 심리 / 🇰🇷 외국인·개인 순매수(다음 2016~) · 환율 · (받아지면) 예탁금·신용잔고
       🇯🇵 엔화 / 🇨🇳 상해·심천 PER · PBR · 주식−채권 금리차 · 시총÷GDP · 융자잔고 · 북향 자금 · 위안 / 🇭🇰 남향 자금 · 홍콩달러 · 위안 / 전부: 5년 평균선과의 거리

  결과 보기 전 등록한 것
  ─ 「비싸다/싸다」는 그날까지 자기 과거 대비 순위(확장 백분위 · 5년치 쌓인 뒤부터) — 미래 값 안 봄 · 월 자료는 한 달 늦게 · 미국 자료는 아시아에 하루 늦게
  ─ 경고 신호 → 「6개월 안 −10%」「1년 안 −20%」 · 싸다/바닥 신호 → 「1년 뒤 플러스」「6개월 좋은 매수 자리」(모든 날 · 고점 −20% 아래인 날 따로)
  ─ 통과(✅): 자료 기간을 반으로 잘라 앞·뒤 둘 다 평소보다 1.15배 넘거나 +8%p 넘고, 켜진 날 150일↑ · 따로 떨어진 때 5번↑
  결과: market/alt.json → 앱 🎯 신호 확률판 「나라별 다른 자료」. 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent
ALT = ROOT / "market" / "lab" / "alt"
OUT = ROOT / "market" / "alt.json"
MK = [("kospi", "^KS11", "코스피", "kr"), ("kosdaq", "^KQ11", "코스닥", "kr"), ("nikkei", "^N225", "닛케이225", "jp"), ("shanghai", "000001.SS", "상해종합", "cn"),
      ("shenzhen", "399001.SZ", "심천성분", "cn"), ("hsi", "^HSI", "항셍", "hk"), ("hscei", "^HSCE", "항셍 H주", "hk"), ("sp500", "^GSPC", "S&P500", "us"), ("nasdaq", "^IXIC", "나스닥", "us")]
TG = {"down": "6개월 안 −10%", "crash": "1년 안 −20%", "up12": "1년 뒤 플러스", "good": "6개월 좋은 매수 자리"}


def rd(name, datecol=0):
    p = ALT / f"{name}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d.index = pd.to_datetime(d.iloc[:, datecol].astype(str), errors="coerce"); d = d[d.index.notna()].sort_index()
    return d[~d.index.duplicated(keep="last")]   # 날짜가 20261110 꼴이어도 to_datetime 이 읽음


def epct(x, minp):
    """그날까지 자기 과거 대비 순위(0~1)"""
    return x.expanding(min_periods=minp).rank(pct=True)


def lag_month(s):
    """월 자료: 그 달 값은 다음 달 1일부터 씀"""
    s = s.dropna().copy(); s.index = (s.index.to_period("M") + 1).to_timestamp(); return s[~s.index.duplicated(keep="last")]


def runs(m):
    m = m.astype(int); return int((m.diff() == 1).sum() + int(m.iloc[0] == 1)) if len(m) else 0


def targets(s):
    c = s.values; idx = s.index
    def fmin(H): return pd.Series(c[::-1], index=idx[::-1]).rolling(H, min_periods=H).min()[::-1].shift(-1) / s - 1
    f6, f12 = fmin(126), fmin(252); r6, r12 = s.shift(-126) / s - 1, s.shift(-252) / s - 1
    dd = s / s.rolling(252, min_periods=60).max() - 1
    return pd.DataFrame({"down": (f6 <= -0.10).astype(float).where(f6.notna()), "crash": (f12 <= -0.20).astype(float).where(f12.notna()),
                         "up12": (r12 > 0).astype(float).where(r12.notna()), "good": ((r6 > 0) & (f6 > -0.10)).astype(float).where(r6.notna()), "r12": r12, "dd": dd})


def build(px):
    """→ {지수: [(k, 이름, 쪽(W/B), 날짜별 bool Series)]}"""
    us = px["^GSPC"].dropna().index
    F = {k: [] for k, *_ in MK}
    def daily(s, idx, lag=0):
        return s.reindex(s.index.union(idx)).ffill().shift(lag).reindex(idx)
    def add(mks, k, name, side, ser, lag=0):
        for mk in mks:
            sym = next(m[1] for m in MK if m[0] == mk); idx = px[sym].dropna().index
            x = daily(ser.astype(float), idx, lag)
            F[mk].append((k, name, side, x))
    ALL = [m[0] for m in MK]; KR, JP, CN, HK, US = ["kospi", "kosdaq"], ["nikkei"], ["shanghai", "shenzhen"], ["hsi", "hscei"], ["sp500", "nasdaq"]
    # 전부: 5년 평균선과의 거리
    for mk, sym, *_ in MK:
        s = px[sym].dropna(); g = s / s.rolling(1260, min_periods=900).mean() - 1; p = epct(g, 1260)
        F[mk].append(("x_hi5", "5년 평균선보다 많이 위(자기 과거 상위 10%)", "W", (p >= 0.9).astype(float).where(p.notna())))
        F[mk].append(("x_lo5", "5년 평균선보다 많이 아래(자기 과거 하위 15%)", "B", (p <= 0.15).astype(float).where(p.notna())))
    # 🇺🇸
    M = rd("us_multpl")
    if M is not None:
        t10 = px["^TNX"].dropna(); t10 = t10.where(t10 < 20, t10 / 10)
        for col, nm in (("cape", "CAPE(10년 평균 이익 대비 주가)"), ("pe", "PER"), ("pb", "PBR")):
            v = lag_month(pd.to_numeric(M[col], errors="coerce")); v = v[v.index >= "1950"]
            if len(v) < 80: continue
            p = epct(v, 60 if col != "pb" else 24)
            add(US, f"us_{col}_hi", f"🇺🇸 {nm} 비쌈(과거 상위 10%)", "W", (p >= 0.9).astype(float).where(p.notna()))
            add(US, f"us_{col}_lo", f"🇺🇸 {nm} 쌈(과거 하위 30%)", "B", (p <= 0.3).astype(float).where(p.notna()))
        ey = lag_month(pd.to_numeric(M["ey"], errors="coerce")); ey = ey[ey.index >= "1962"]
        erp = (ey.reindex(ey.index.union(t10.index)).ffill().reindex(t10.index) - t10).dropna(); p = epct(erp, 1260)
        add(US, "us_erp_lo", "🇺🇸 주식 이익수익률 − 국채 금리가 낮음(하위 10%)", "W", (p <= 0.1).astype(float).where(p.notna()))
        add(US, "us_erp_hi", "🇺🇸 주식 이익수익률 − 국채 금리가 높음(상위 20%)", "B", (p >= 0.8).astype(float).where(p.notna()))
        add([m for m in ALL if m not in US], "g_cape_hi", "🇺🇸 CAPE 비쌈(과거 상위 10%)", "W", (epct(lag_month(pd.to_numeric(M["cape"], errors="coerce"))["1950":], 60) >= 0.9).astype(float), lag=1)
    A = rd("us_aaii")
    if A is not None:
        sp = (pd.to_numeric(A["bull"], errors="coerce") - pd.to_numeric(A["bear"], errors="coerce")).dropna().rolling(4).mean().dropna()
        sp.index = sp.index + pd.Timedelta(days=1)
        add(US, "us_aaii_euph", "🇺🇸 개인 심리 들뜸(낙관−비관 4주 +25%p↑)", "W", (sp >= 0.25).astype(float))
        add(US, "us_aaii_fear", "🇺🇸 개인 심리 겁먹음(낙관−비관 4주 −15%p↓)", "B", (sp <= -0.15).astype(float))
        add([m for m in ALL if m not in US], "g_aaii_fear", "🇺🇸 개인 심리 겁먹음(낙관−비관 4주 −15%p↓)", "B", (sp <= -0.15).astype(float), lag=1)
    # 환율
    def fx(sym, mks, up_name, dn_name, up_side, dn_side, up=0.05, dn=-0.04):
        if sym not in px: return
        x = px[sym].dropna(); ch = x.pct_change(63)
        add(mks, "fx_up", up_name, up_side, (ch >= up).astype(float).where(ch.notna()))
        add(mks, "fx_dn", dn_name, dn_side, (ch <= dn).astype(float).where(ch.notna()))
    fx("KRW=X", KR, "원화 약세(달러/원 3개월 +5%)", "원화 강세(달러/원 3개월 −4%)", "W", "B")
    fx("JPY=X", JP, "엔화 약세(달러/엔 3개월 +5%)", "엔화 강세(달러/엔 3개월 −5%)", "B", "W", 0.05, -0.05)
    fx("CNY=X", CN + HK, "위안 약세(달러/위안 3개월 +2%)", "위안 강세(달러/위안 3개월 −2%)", "W", "B", 0.02, -0.02)
    if "HKD=X" in px:
        h = px["HKD=X"].dropna(); add(HK, "hkd_weak", "홍콩달러 약세 한계선 근처(7.84↑ · 돈이 빠져나감)", "W", (h >= 7.84).astype(float))
    # 🇰🇷 투자자별
    I = rd("kr_investor")
    if I is not None:
        for mk, code in (("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")):
            d = I[I["mk"] == code]
            f20 = (pd.to_numeric(d["foreignStraightPurchasePrice"], errors="coerce") / 1e8).rolling(20).sum(); i20 = (pd.to_numeric(d["individualStraightPurchasePrice"], errors="coerce") / 1e8).rolling(20).sum()
            pf, pi = epct(f20, 500), epct(i20, 500)
            add([mk], "kr_for_sell", "외국인 20일 순매도 심함(과거 하위 10%)", "W", (pf <= 0.1).astype(float).where(pf.notna()))
            add([mk], "kr_ind_buy", "개인 20일 순매수 몰림(과거 상위 10%)", "W", (pi >= 0.9).astype(float).where(pi.notna()))
            add([mk], "kr_for_buy", "외국인 20일 순매수 강함(과거 상위 20%)", "B", (pf >= 0.8).astype(float).where(pf.notna()))
            turn = (f20 > 0) & (f20.shift(20) < 0) & (pf.shift(20).rolling(40, min_periods=1).min() <= 0.15)
            add([mk], "kr_for_turn", "외국인 심한 매도 뒤 20일 순매수로 돌아섬", "B", turn.astype(float).rolling(20, min_periods=1).max().where(pf.notna()))
    K, Kc = rd("kr_kofia_funds"), rd("kr_kofia_credit")   # 금융투자협회 — 예탁금·미수금·반대매매 / 신용거래융자(전체·유가·코스닥) · 이틀 늦게 나옴
    if K is not None and Kc is not None:
        n_ = lambda d, c: pd.to_numeric(d[c], errors="coerce").replace(0, np.nan).dropna()
        dep, forced = n_(K, "TMPV2"), n_(K, "TMPV6")
        for mk, col in (("kospi", "TMPV3"), ("kosdaq", "TMPV4")):
            cr = n_(Kc, col)
            if len(cr) < 1500: cr = n_(Kc, "TMPV2")
            ratio = (cr / dep).dropna(); pr = epct(ratio, 1260); cg = cr.pct_change(60); cdd = cr / cr.rolling(252, min_periods=120).max() - 1
            add([mk], "kr_credit_hi", "신용잔고÷예탁금 높음(빚투 과열 · 과거 상위 10%)", "W", (pr >= 0.9).astype(float).where(pr.notna()), lag=2)
            add([mk], "kr_credit_surge", "신용잔고 60일 새 +15%(빚투 급증)", "W", (cg >= 0.15).astype(float).where(cg.notna()), lag=2)
            add([mk], "kr_credit_flush", "신용잔고 1년 고점보다 −20%(빚 털림)", "B", (cdd <= -0.20).astype(float).where(cdd.notna()), lag=2)
        dg = dep.pct_change(60); dd_ = dep / dep.rolling(252, min_periods=120).max() - 1
        add(KR, "kr_dep_surge", "예탁금 60일 새 +20%(대기 자금 몰림)", "W", (dg >= 0.20).astype(float).where(dg.notna()), lag=2)
        add(KR, "kr_dep_drop", "예탁금 1년 고점보다 −20%(개인 자금 떠남)", "B", (dd_ <= -0.20).astype(float).where(dd_.notna()), lag=2)
        f20 = forced.rolling(20, min_periods=10).mean(); pf_ = epct(f20 / dep.reindex(f20.index).ffill(), 1260)
        add(KR, "kr_forced", "반대매매 급증(예탁금 대비 20일 평균 · 과거 상위 5% = 투매)", "B", (pf_ >= 0.95).astype(float).where(pf_.notna()), lag=2)
        add(KR, "kr_forced_w", "반대매매 늘어남(과거 상위 20%)", "W", (pf_ >= 0.8).astype(float).where(pf_.notna()), lag=2)
    # 🇨🇳
    def cn_val(file, col, key, nm, mks, minp=60):
        d = rd(file)
        if d is None: return
        v = pd.to_numeric(d[col], errors="coerce").dropna(); v.index = v.index + pd.Timedelta(days=1); p = epct(v, minp)
        add(mks, key + "_hi", f"{nm} 비쌈(과거 상위 20%)", "W", (p >= 0.8).astype(float).where(p.notna()))
        add(mks, key + "_lo", f"{nm} 쌈(과거 하위 20%)", "B", (p <= 0.2).astype(float).where(p.notna()))
    cn_val("cn_pe_sh", "平均市盈率", "cn_pe", "🇨🇳 상해 PER", ["shanghai"] + HK)
    cn_val("cn_pe_sz", "平均市盈率", "cn_pe", "🇨🇳 심천 PER", ["shenzhen"])
    cn_val("cn_pb_sh", "市净率", "cn_pb", "🇨🇳 상해 PBR", ["shanghai"] + HK)
    cn_val("cn_pb_all", "middlePB", "cn_pbm", "🇨🇳 A주 PBR 가운데값", CN)
    E = rd("cn_ebs")
    if E is not None:
        v = pd.to_numeric(E["股债利差"], errors="coerce").dropna(); v.index = v.index + pd.Timedelta(days=1); p = epct(v, 1000)
        add(CN + HK, "cn_ebs_lo", "🇨🇳 주식−채권 금리차 낮음(주식 비쌈 · 하위 20%)", "W", (p <= 0.2).astype(float).where(p.notna()))
        add(CN + HK, "cn_ebs_hi", "🇨🇳 주식−채권 금리차 높음(주식 쌈 · 상위 20%)", "B", (p >= 0.8).astype(float).where(p.notna()))
    Bf = rd("cn_buffett")
    if Bf is not None:
        v = (pd.to_numeric(Bf["总市值"], errors="coerce") / pd.to_numeric(Bf["GDP"], errors="coerce")).dropna(); v.index = v.index + pd.Timedelta(days=1); p = epct(v, 1000)
        add(CN, "cn_buf_hi", "🇨🇳 시가총액÷GDP 높음(상위 20%)", "W", (p >= 0.8).astype(float).where(p.notna()))
        add(CN, "cn_buf_lo", "🇨🇳 시가총액÷GDP 낮음(하위 20%)", "B", (p <= 0.2).astype(float).where(p.notna()))
    Mg = rd("cn_margin_macro")
    if Mg is not None:
        v = pd.to_numeric(Mg["融资余额"], errors="coerce").dropna(); v = v[v.index >= "2011"]; v.index = v.index + pd.Timedelta(days=1)
        g = v.pct_change(60); d_ = v / v.rolling(250, min_periods=120).max() - 1
        add(CN, "cn_mg_surge", "🇨🇳 융자잔고 60일 새 +25%(빚투 급증)", "W", (g >= 0.25).astype(float).where(g.notna()))
        add(CN, "cn_mg_flush", "🇨🇳 융자잔고 1년 고점보다 −20%(빚 털림)", "B", (d_ <= -0.20).astype(float).where(d_.notna()))
    for file, key, nm, mks in (("cn_north", "cn_north", "🇨🇳 북향(외국인) 자금", CN), ("hk_south", "hk_south", "🇭🇰 남향(본토) 자금", HK)):
        d = rd(file)
        if d is None: continue
        v = pd.to_numeric(d["当日成交净买额"], errors="coerce").dropna()
        if len(v) < 800: continue
        f20 = v.rolling(20).sum(); f20.index = f20.index + pd.Timedelta(days=1); p = epct(f20, 500)
        add(mks, key + "_buy", f"{nm} 20일 순매수 강함(상위 20%)", "B", (p >= 0.8).astype(float).where(p.notna()))
        add(mks, key + "_sell", f"{nm} 20일 순매도 심함(하위 10%)", "W", (p <= 0.1).astype(float).where(p.notna()))
    Nk = rd("jp_nikkei_val")
    if Nk is not None and len(Nk) > 1500:
        try:
            d = Nk[Nk["kind"] == "per"]; v = pd.to_numeric(d.iloc[:, -1], errors="coerce").dropna(); v.index = v.index + pd.Timedelta(days=1); p = epct(v, 1000)
            add(JP, "jp_per_hi", "🇯🇵 닛케이 PER 비쌈(상위 20%)", "W", (p >= 0.8).astype(float).where(p.notna()))
            add(JP, "jp_per_lo", "🇯🇵 닛케이 PER 쌈(하위 20%)", "B", (p <= 0.2).astype(float).where(p.notna()))
            d = Nk[Nk["kind"] == "pbr"]; v = pd.to_numeric(d.iloc[:, -1], errors="coerce").dropna(); v.index = v.index + pd.Timedelta(days=1); p = epct(v, 1000)
            add(JP, "jp_pbr_lo", "🇯🇵 닛케이 PBR 쌈(하위 20%)", "B", (p <= 0.2).astype(float).where(p.notna()))
            add(JP, "jp_pbr_hi", "🇯🇵 닛케이 PBR 비쌈(상위 20%)", "W", (p >= 0.8).astype(float).where(p.notna()))
        except Exception as e:
            print("닛케이 해석 실패", e)
    return F


def test(x, y, r12):
    """x: 신호(0/1/NaN) · y: 목표 → 통계 dict"""
    m = x.notna() & y.notna(); x, y = x[m], y[m]
    if len(x) < 750 or x.sum() < 150 or y.nunique() < 2:
        return {"thin": True, "n": int(len(x)), "on": int(x.sum()) if len(x) else 0}
    on = x > 0.5; base = float(y.mean()); p = float(y[on].mean())
    mid = x.index[len(x) // 2]; A, B = x.index < mid, x.index >= mid
    def half(k):
        o = on & k
        if o.sum() < 60 or y[k].mean() == 0: return None, None
        return float(y[o].mean()), float(y[k].mean())
    pa, ba = half(A); pb, bb_ = half(B)
    ok = lambda p_, b_: p_ is not None and (p_ >= 1.15 * b_ or p_ - b_ >= 0.08)
    ep = runs(on); yrs = int(pd.Series(x.index[on].year).nunique())
    return {"years": yrs, "n": int(len(x)), "from": str(x.index[0].date()), "share": round(float(on.mean()) * 100, 1), "p_on": round(p * 100), "base": round(base * 100), "lift": round(p / base, 2) if base else None,
            "a": None if pa is None else [round(pa * 100), round(ba * 100)], "b": None if pb is None else [round(pb * 100), round(bb_ * 100)], "episodes": ep,
            "r12_on": round(float(r12[m][on].mean()) * 100, 1) if r12[m][on].notna().any() else None, "r12_base": round(float(r12[m].mean()) * 100, 1),
            "good": bool(ok(pa, ba) and ok(pb, bb_) and ep >= 5), "anti": bool(pa is not None and pb is not None and pa < ba * 0.9 and pb < bb_ * 0.9)}


def main():
    px = pd.read_csv(ALT / "px.csv.gz", index_col=0, parse_dates=True)
    F = build(px)
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "rules": __doc__.split("결과 보기 전 등록한 것")[1].split("결과:")[0].strip(), "targets": TG, "markets": []}
    tot = good = 0
    for mk, sym, name, nat in MK:
        s = px[sym].dropna(); Y = targets(s)
        rows = []
        for k, nm, side, x in F[mk]:
            x = x.reindex(s.index)
            T = {}
            for tg in (("down", "crash") if side == "W" else ("up12", "good")):
                T[tg] = test(x, Y[tg], Y["r12"])
                if side == "B":
                    deep = Y["dd"] <= -0.20
                    T[tg + "_deep"] = test(x.where(deep), Y[tg].where(deep), Y["r12"])
            lastv = x.dropna()
            g = [t for t, v in T.items() if v.get("good")]
            tot += 1; good += bool(g)
            rows.append({"k": k, "name": nm, "side": side, "now": None if not len(lastv) else bool(lastv.iloc[-1] > 0.5), "asof": None if not len(lastv) else str(lastv.index[-1].date()), "t": T, "good": g})
        g5 = s / s.rolling(1260, min_periods=900).mean() - 1; p5 = epct(g5, 1260)
        res["markets"].append({"key": mk, "name": name, "nat": nat, "asof": str(s.index[-1].date()), "dd": round(float(Y["dd"].iloc[-1]) * 100, 1),
                               "x5": {"gap": round(float(g5.iloc[-1]) * 100, 1), "pct": round(float(p5.iloc[-1]) * 100)}, "signals": rows})
        print(f"\n== {name}")
        for r in rows:
            for tg, v in r["t"].items():
                if v.get("thin"):
                    if not tg.endswith("_deep"): print(f"      {r['side']} {r['name']:<34} {tg}: 표본 적음(켜진 날 {v['on']})")
                    continue
                print(f"   {'✅' if v['good'] else '❌' if v['anti'] else '  '} {r['side']} {r['name']:<34} {tg:<10} {v['from'][:4]}~ 켜진 날 {v['share']:>5}% · 켜짐 {v['p_on']:>3}% 평소 {v['base']:>3}% · 앞 {v['a']} 뒤 {v['b']} · {v['episodes']}번/{v['years']}개 해 · 1년 평균 {v['r12_on']}% (평소 {v['r12_base']}%)" + (" · 지금 켜짐" if r["now"] else ""))
    res["n_tested"] = tot; res["n_good"] = good
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n신호 {tot}개 중 통과 {good}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
