"""선호 ETF 목록(ledger/pref_etf.json, 사용자 10/13) — 지금 포트 상품을 목록 상품으로 바꿔도 수익률이 비슷한가?
RULES.md 1-L. 결과 → market/etf_pref.json (+ market/lab/e1013_pref.json 복사)

기준 (결과 보기 전에 정함 · 같은 기간 · 배당 포함 가격):
  같은 기간 250거래일 이상 · 연 수익 차이 ≤ 1.0%p · 최근 1년 수익 차이 ≤ 2.0%p · 최대 낙폭이 3%p 넘게 더 깊지 않음
  · (현금성이 아니면) 일간 상관 ≥ 0.90 · 변동성 비율 0.7~1.3  → 모두 맞으면 「교체」, 하나라도 아니면 「유지」
  현금성(둘 다 연 변동성 2% 미만)은 상관·변동성 비율을 보지 않음.
"""
import json, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
KST = dt.timezone(dt.timedelta(hours=9))

# (어느 포트·칸, 지금 상품, 목록 후보, 메모)
PAIRS = [
    ("💼·⚡·🎯 현금·단기채 (한국)", "499660.KS", "438330.KS", "TIGER CD금리 → TIGER 우량회사채액티브"),
    ("💼·⚡·🎯 현금·단기채 (미국)", "SGOV", "SHY", "0~3개월 국채 → 1~3년 국채"),
    ("🎯 현금 (계산용 BIL)", "BIL", "SHY", "1~3개월 국채 → 1~3년 국채"),
    ("⚡ 🧭 추세 칸 장기채", "TLT", "IEF", "20년+ 국채 → 7~10년 국채"),
    ("🧭 섹터 의견 반도체 (미국)", "SOXX", "SMH", "필라델피아반도체 → 반에크 반도체"),
    ("🧭 섹터 의견 AI 소프트웨어 (한국)", "418670.KS", "466950.KS", "TIGER 글로벌AI사이버보안 → TIGER 글로벌AI액티브"),
    ("🧭 섹터 의견 전력·인프라 (미국)", "XLU", "PAVE", "유틸리티 → 미국 인프라"),
    ("참고: 💼 S&P500 한국 상품", "360750.KS", "448290.KS", "환노출 → 환헤지(H) — 목록 안끼리 참고"),
    ("참고: 💼 나스닥100 한국 상품", "133690.KS", "448300.KS", "환노출 → 환헤지(H) — 목록 안끼리 참고"),
]
CRIT = {"days": 250, "cagr": 1.0, "y1": 2.0, "mdd": 3.0, "corr": 0.90, "vol_lo": 0.7, "vol_hi": 1.3, "cash_vol": 2.0}


def stats(s):
    r = s.pct_change().dropna()
    yrs = len(r) / 252
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    mdd = (s / s.cummax() - 1).min()
    y1 = s.iloc[-1] / s.iloc[-253] - 1 if len(s) > 253 else np.nan
    return {"cagr": round(cagr * 100, 2), "vol": round(r.std() * np.sqrt(252) * 100, 2), "mdd": round(mdd * 100, 2),
            "y1": round(y1 * 100, 2) if y1 == y1 else None}


def main():
    tick = sorted({t for p in PAIRS for t in p[1:3]})
    df = yf.download(tick, period="max", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    px = {}
    for t in tick:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 20: px[t] = s
        except Exception:
            pass
    rows = []
    for slot, cur, cand, memo in PAIRS:
        row = {"slot": slot, "cur": cur, "cand": cand, "memo": memo}
        if cur not in px or cand not in px:
            row.update(verdict="유지", why="시세 없음(" + ", ".join(t for t in (cur, cand) if t not in px) + ")"); rows.append(row); continue
        j = pd.concat([px[cur], px[cand]], axis=1, join="inner").dropna(); j.columns = ["a", "b"]
        row["from"], row["to"], row["days"] = str(j.index[0].date()), str(j.index[-1].date()), len(j)
        if len(j) < CRIT["days"]:
            row.update(verdict="유지", why=f"같은 기간 {len(j)}일 — 250일 미만(표본 부족)"); rows.append(row); continue
        a, b = stats(j["a"]), stats(j["b"])
        ra, rb = j["a"].pct_change().dropna(), j["b"].pct_change().dropna()
        corr = round(float(ra.corr(rb)), 3)
        cash = a["vol"] < CRIT["cash_vol"] and b["vol"] < CRIT["cash_vol"]
        d_cagr = round(b["cagr"] - a["cagr"], 2)
        d_y1 = round((b["y1"] or 0) - (a["y1"] or 0), 2) if a["y1"] is not None and b["y1"] is not None else None
        d_mdd = round(b["mdd"] - a["mdd"], 2)   # 음수 = 후보가 더 깊게 빠짐
        vr = round(b["vol"] / a["vol"], 2) if a["vol"] else None
        fails = []
        if abs(d_cagr) > CRIT["cagr"]: fails.append(f"연 수익 차이 {d_cagr:+.2f}%p")
        if d_y1 is not None and abs(d_y1) > CRIT["y1"]: fails.append(f"1년 수익 차이 {d_y1:+.2f}%p")
        if d_mdd < -CRIT["mdd"]: fails.append(f"최대 낙폭 {abs(d_mdd):.1f}%p 더 깊음")
        if not cash:
            if corr < CRIT["corr"]: fails.append(f"상관 {corr}")
            if vr is not None and not (CRIT["vol_lo"] <= vr <= CRIT["vol_hi"]): fails.append(f"변동성 비율 {vr}")
        row.update(a=a, b=b, corr=corr, cash=cash, d_cagr=d_cagr, d_y1=d_y1, d_mdd=d_mdd, vol_ratio=vr,
                   verdict="교체" if not fails else "유지", why="기준 모두 통과" if not fails else " · ".join(fails))
        rows.append(row)
    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "crit": CRIT, "rows": rows,
           "note": "RULES 1-L — 선호 ETF 목록(ledger/pref_etf.json) 상품으로 바꿔도 수익률이 비슷하면 교체, 차이가 크거나 대체할 것이 없으면 유지."}
    for p in (ROOT / "market" / "etf_pref.json", ROOT / "market" / "lab" / "e1013_pref.json"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(r["slot"], r["cur"], "→", r["cand"], r["verdict"], "|", r["why"], "|", r.get("a"), r.get("b"), r.get("corr"))


if __name__ == "__main__":
    main()
