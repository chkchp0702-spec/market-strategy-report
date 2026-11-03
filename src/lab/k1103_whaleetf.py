"""📈 11/3 16시 — 🐋 고래 칸(⚡ 의 15%)을 처음 「긴 역사」로 재 보기 (13F 복제 ETF 를 대용으로)
  왜: 우리 고래 바스켓(13F 큰 신규 · 같은 비중 10)은 이력이 7분기뿐(whale40 2024Q4~) — 2008~ 검증이 없었음.
      SEC EDGAR 은 GitHub 러너를 403 으로 막음(k1013_secprobe) → 13F 원자료 이력은 lab 에서 못 받음.
      그래서 13F 를 「같은 방식으로」 공개 복제하는 ETF 를 대용으로 씀(공시 45일 지연·분기 교체를 운용사가 이미 반영 · 실제 체결 수익):
        GURU = 집중형 헤지펀드들의 「가장 큰 확신 종목(best ideas)」 같은 비중 (2012-06~)  ← 우리 규칙(같은 비중·큰 비중)과 가장 닮음
        GVIP = 헤지펀드들이 가장 많이 겹쳐 담은 「상위 10 겹침(consensus)」 (2016-11~)
        GFGF = 구루 즐겨찾기 (2021~, 참고)
  묻는 것: ① 고래 칸 대용이 뼈대(C안 + 변동성 맞춤 18%)보다 나은가 — 칸 배분 w = 0~30% 로 ⚡ (뼈대+고래) 를 굴림
          ② 우리 7분기 실제 바스켓 분기 수익이 GURU·GVIP 중 어느 쪽과 닮았나(대용이 맞는지)
  틀: 월 1회·국면 바뀔 때 되돌림(뼈대 base_vol) · 고래 칸은 매달 목표 비중으로 되돌림 · 회전 × 0.1%
      앞 = 2012-07~2016 (GURU 시작) / 뒤 = 2017~ · GVIP 는 뒤만 · 흔들기 = w ±20% (15% → 12·18)
  한계: 대용 ETF 는 우리 규칙과 같지 않음(종목 수·펀드 고르기 다름) · 돌파 칸 4% 는 뼈대로 대신(효과 작음)
→ market/lab/k1103_whaleetf.json
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import yfinance as yf
from src.conc_bt import SECT, IS_END, OOS_START, regimes, stats
from k1013_trend import base_vol

OUT = Path("market/lab/k1103_whaleetf.json")
PROX = ["GURU", "GVIP", "GFGF", "RSP", "IWD"]
BASE_T = ["SPY", "QQQ", "GLD", "BIL"]
COST = 0.001
IS_A = "2012-07-01"
WS = [0.0, 0.05, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]
# k1021_whale5 「now10」(지금 규칙) 실제 분기 수익 — 같은 창의 대용 수익과 맞대 봄
OURQ = [("Q4 2024", "2025-02-18", "2025-05-19", -17.96), ("Q1 2025", "2025-05-19", "2025-08-18", -6.18),
        ("Q2 2025", "2025-08-18", "2025-11-17", -1.67), ("Q3 2025", "2025-11-17", "2026-02-17", 16.25),
        ("Q4 2025", "2026-02-17", "2026-05-18", 29.31), ("Q1 2026", "2026-05-18", "2026-08-17", 13.08),
        ("Q2 2026", "2026-08-17", "2026-10-21", -0.27)]


def dl(ts):
    df = yf.download(ts, start="2006-01-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    return pd.DataFrame({t: df[t]["Close"] for t in ts if t in df.columns.get_level_values(0)})


def mixnav(rb, rw, w):
    """뼈대 일수익 rb + 고래 대용 일수익 rw, 달 바뀔 때 w 로 되돌림(회전 × COST)"""
    idx = rb.index
    a, b = 1 - w, w
    nav, out = 1.0, []
    prev_m = None
    for d in idx:
        if prev_m is not None and d.month != prev_m:
            tot = a + b
            tv = abs(b / tot - w)
            a, b = (1 - w) * tot, w * tot
            nav_c = tv * COST * tot
            a -= nav_c * (1 - w); b -= nav_c * w
        prev_m = d.month
        a *= 1 + rb.at[d]; b *= 1 + rw.at[d]
        out.append(a + b)
    return pd.Series(out, index=idx)


def segs(nav, spy, a, b):
    n = nav[(nav.index >= a) & (nav.index <= b)].dropna()
    s = spy.reindex(n.index)
    if len(n) < 60:
        return {}
    o = stats(n / n.iloc[0], s / s.iloc[0])
    o.pop("yr", None)
    return o


def main():
    C = dl(sorted(set(SECT + BASE_T + PROX)))
    C = C.dropna(subset=BASE_T).ffill(limit=5)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    out = {"_doc": __doc__, "first": {t: str(C[t].first_valid_index())[:10] for t in PROX if t in C.columns}}
    spy = C["SPY"]
    res = {}
    for px, a0 in (("GURU", IS_A), ("GVIP", OOS_START), ("GFGF", "2021-01-01"), ("RSP", IS_A)):
        if px not in C.columns:
            continue
        st = max(pd.Timestamp(a0), C[px].first_valid_index() + pd.Timedelta(days=5))
        idx = C.index[(C.index >= st)]
        rb, _ = base_vol(C, reg, idx)
        rw = C[px].pct_change().reindex(idx).fillna(0.0)
        g = {}
        for w in WS:
            nav = mixnav(rb, rw, w)
            g[f"w{int(round(w * 100))}"] = {"is": segs(nav, spy, IS_A, IS_END) if px in ("GURU", "RSP") else {},
                                            "oos": segs(nav, spy, OOS_START, "2100-01-01"),
                                            "full": segs(nav, spy, str(st)[:10], "2100-01-01")}
        # 고래 칸 혼자 vs 뼈대 혼자
        alone = (1 + rw).cumprod(); base_alone = (1 + rb).cumprod()
        g["alone"] = {"is": segs(alone, spy, IS_A, IS_END) if px in ("GURU", "RSP") else {}, "oos": segs(alone, spy, OOS_START, "2100"),
                      "yr": {str(y): round(float((1 + rw[rw.index.year == y]).prod() - 1) * 100, 1) for y in sorted(set(rw.index.year))}}
        g["base"] = {"is": segs(base_alone, spy, IS_A, IS_END), "oos": segs(base_alone, spy, OOS_START, "2100"),
                     "yr": {str(y): round(float((1 + rb[rb.index.year == y]).prod() - 1) * 100, 1) for y in sorted(set(rb.index.year))}}
        # 뼈대와 상관(일)·하락장 베타
        g["corr_base"] = round(float(rw.corr(rb)), 2)
        res[px] = g
        print(px, "w0 oos", g["w0"]["oos"].get("cagr"), "w15", g["w15"]["oos"].get("cagr"), "alone", g["alone"]["oos"].get("cagr"))
    out["grid"] = res
    # 우리 7분기 바스켓 vs 대용
    qq = []
    for q, d0, d1, r in OURQ:
        row = {"q": q, "ours": r}
        for t in ["SPY", "GURU", "GVIP", "GFGF", "RSP"]:
            if t in C.columns:
                s = C[t].dropna()
                try:
                    v0 = s[s.index >= d0].iloc[0]; v1 = s[s.index <= d1].iloc[-1]
                    row[t] = round(float(v1 / v0 - 1) * 100, 2)
                except Exception:
                    pass
        qq.append(row)
    out["ourq"] = qq
    df = pd.DataFrame(qq).set_index("q")
    out["ourq_corr"] = {t: round(float(df["ours"].corr(df[t])), 2) for t in df.columns if t != "ours" and df[t].notna().sum() >= 5}
    out["ourq_sum"] = {t: round(float(((1 + df[t] / 100).prod() - 1) * 100), 1) for t in df.columns}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(out["ourq_sum"], ensure_ascii=False), out["ourq_corr"])


if __name__ == "__main__":
    main()
