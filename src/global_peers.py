"""🌏 글로벌 동종주 비교 — 미국에서 잘 나가는 섹터의 일본·한국·대만·중국·홍콩 동종주가 미국보다 나은가?
  (10/10 사용자: "미국 섹터와 비슷한 곳을 일본·중국·홍콩으로 확대해서 여러 요인을 비교했을 때 낫다고 판단되면 미국 외 종목을 포트에 넣어도 돼.
   예: 어드밴테스트·아오스캉테크 같은 거 — 같은 섹터인데 미국보다 아웃퍼폼")
  · 모든 수익률은 달러 기준(환율 반영) — 원화·엔화로 사면 환율도 같이 먹기 때문
  · 요인: 1·3·6개월 수익률, 미국 테마 ETF 대비 초과(3개월), 50·200일선 위, 3개월 변동성·최대 낙폭, 위험 대비 수익(3개월 수익/변동성),
          주간 상승 비율(꾸준함), 1개월 과열(+35% 넘으면 감점)
  · 판정: 「편입 후보」 = 3개월 달러 수익이 미국 ETF 보다 +10%p 이상 · 1개월도 앞섬 · 50일선 위 · 위험 대비 수익이 ETF 이상 · 과열 아님
  → market/peers.json (앱 💼 포트 「🌏 미국 밖 동종주」 · 아침 리포트 3-C 포트 점검 재료)
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "peers.json"
KST = dt.timezone(dt.timedelta(hours=9))

# 테마: 미국 기준 ETF · 포트 칸 이름(같으면 그 칸의 대안) · 나라별 동종주 (야후 티커, 이름)
THEMES = [
    {"k": "semi_eq", "name": "반도체 장비·테스트", "etf": "SOXX", "bucket": "반도체", "us": [("AMAT", "어플라이드"), ("LRCX", "램리서치"), ("KLAC", "KLA"), ("TER", "테라다인")],
     "peers": [("6857.T", "어드밴테스트"), ("8035.T", "도쿄일렉트론"), ("6146.T", "디스코"), ("6920.T", "레이저텍"), ("7735.T", "스크린HD"),
               ("042700.KS", "한미반도체"), ("036930.KQ", "주성엔지니어링"), ("000660.KS", "SK하이닉스"), ("2330.TW", "TSMC"),
               ("002371.SZ", "북방화창"), ("688012.SS", "중미반도체"), ("0981.HK", "SMIC")]},
    {"k": "pcb_optic", "name": "PCB·기판·광통신", "etf": "GLW", "bucket": "광통신", "us": [("COHR", "코히런트"), ("LITE", "루멘텀"), ("TTMI", "TTM")],
     "peers": [("002913.SZ", "아오스캉테크(奧士康)"), ("002463.SZ", "후뎬(沪电)"), ("300308.SZ", "중지쉬촹(이노라이트)"), ("300502.SZ", "신이성(이옵토링크)"),
               ("2383.TW", "대만광전(EMC)"), ("4062.T", "이비덴"), ("007660.KS", "이수페타시스"), ("353200.KQ", "대덕전자")]},
    {"k": "power", "name": "전력·인프라", "etf": "XLU", "bucket": "전력", "us": [("GEV", "GE버노바"), ("VRT", "버티브"), ("ETN", "이튼")],
     "peers": [("6501.T", "히타치"), ("6503.T", "미쓰비시전기"), ("267260.KS", "HD현대일렉트릭"), ("298040.KS", "효성중공업"), ("010120.KS", "LS ELECTRIC"),
               ("600406.SS", "국전남서(NARI)"), ("1072.HK", "동방전기")]},
    {"k": "ai_sw", "name": "AI 소프트웨어·보안", "etf": "IGV", "bucket": "AI 소프트웨어", "us": [("CRWD", "크라우드스트라이크"), ("PANW", "팔로알토"), ("NOW", "서비스나우")],
     "peers": [("4704.T", "트렌드마이크로"), ("3993.T", "PKSHA"), ("0700.HK", "텐센트"), ("9988.HK", "알리바바"), ("035420.KS", "NAVER")]},
    {"k": "energy", "name": "에너지", "etf": "XLE", "bucket": "에너지", "us": [("XOM", "엑슨모빌"), ("CVX", "셰브론")],
     "peers": [("1605.T", "INPEX"), ("0883.HK", "CNOOC"), ("0857.HK", "페트로차이나"), ("010950.KS", "S-Oil"), ("096770.KS", "SK이노베이션")]},
    {"k": "banks", "name": "금융", "etf": "KBWB", "bucket": "금융", "us": [("JPM", "JP모건"), ("GS", "골드만")],
     "peers": [("8306.T", "MUFG"), ("8316.T", "SMFG"), ("105560.KS", "KB금융"), ("055550.KS", "신한지주"), ("0005.HK", "HSBC"), ("1398.HK", "공상은행")]},
    {"k": "gold", "name": "금·광산", "etf": "GDX", "bucket": "금", "us": [("NEM", "뉴몬트")],
     "peers": [("2899.HK", "쯔진광업"), ("5713.T", "스미토모금속광산"), ("1818.HK", "자오진광업")]},
    {"k": "defense_ship", "name": "방산·조선", "etf": "ITA", "bucket": None, "us": [("LMT", "록히드"), ("NOC", "노스롭")],
     "peers": [("012450.KS", "한화에어로스페이스"), ("329180.KS", "HD현대중공업"), ("042660.KS", "한화오션"), ("7011.T", "미쓰비시중공업"), ("7012.T", "가와사키중공업")]},
]
FX = {".T": "JPY=X", ".KS": "KRW=X", ".KQ": "KRW=X", ".SS": "CNY=X", ".SZ": "CNY=X", ".HK": "HKD=X", ".TW": "TWD=X"}
CUR = {".T": "엔", ".KS": "원", ".KQ": "원", ".SS": "위안", ".SZ": "위안", ".HK": "홍콩달러", ".TW": "대만달러"}
MKT = {".T": "JP", ".KS": "KR", ".KQ": "KR", ".SS": "CN", ".SZ": "CN", ".HK": "HK", ".TW": "TW"}


def suf(t):
    for s in FX:
        if t.endswith(s):
            return s
    return ""


def main() -> int:
    import yfinance as yf
    import pandas as pd
    tick = set(FX.values())
    for T in THEMES:
        tick.add(T["etf"])
        tick |= {t for t, _ in T["us"] + T["peers"]}
    df = yf.download(sorted(tick), period="1y", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = {}
    for t in tick:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 60:
                C[t] = s
        except Exception:
            pass

    def usd(t):
        s = C.get(t)
        if s is None:
            return None
        sx = suf(t)
        if not sx:
            return s
        fx = C.get(FX[sx])
        if fx is None:
            return None
        fx = fx.reindex(s.index, method="ffill")
        return (s / fx).dropna()

    def m(t):
        s = usd(t)
        loc = C.get(t)
        if s is None or len(s) < 70:
            return None
        r = lambda n: round((float(s.iloc[-1]) / float(s.iloc[-1 - n]) - 1) * 100, 2) if len(s) > n else None
        d = s.pct_change().dropna()
        v3 = float(d.iloc[-63:].std() * math.sqrt(252) * 100)
        w = s.iloc[-63:]
        mdd = float((w / w.cummax() - 1).min() * 100)
        wk = s.resample("W").last().pct_change().dropna().iloc[-13:]
        lp = float(loc.iloc[-1])
        out = {"r1": r(21), "r3": r(63), "r6": r(126), "r12": r(len(s) - 1) if len(s) > 200 else None,
               "ma50": lp > float(loc.iloc[-50:].mean()), "ma200": lp > float(loc.iloc[-200:].mean()) if len(loc) >= 200 else None,
               "vol": round(v3, 1), "mdd": round(mdd, 1), "upw": round(float((wk > 0).mean() * 100)), "px": round(lp, 2)}
        out["rr"] = round(out["r3"] / v3 * 100 / 100, 2) if out["r3"] is not None and v3 else None     # 3개월 수익 ÷ 연변동성
        return out

    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "note": "달러 기준 수익률(환율 반영) · 판단 재료이며 매수 추천 아님", "themes": []}
    for T in THEMES:
        e = m(T["etf"])
        if not e:
            continue
        rows = []
        for t, nm in T["us"] + T["peers"]:
            x = m(t)
            if not x:
                continue
            sx = suf(t)
            x.update({"t": t, "name": nm, "mkt": MKT.get(sx, "US"), "cur": CUR.get(sx, "달러"),
                      "ex3": round(x["r3"] - e["r3"], 2) if x["r3"] is not None else None,
                      "ex1": round(x["r1"] - e["r1"], 2) if x["r1"] is not None else None})
            # 종합 점수: 초과 수익(3·1개월) + 위험 대비 수익 + 추세 + 꾸준함 − 과열·낙폭
            sc = (x["ex3"] or 0) * 0.5 + (x["ex1"] or 0) * 0.5 + (x["rr"] or 0) * 10 + (10 if x["ma50"] else -10) + (5 if x.get("ma200") else 0) \
                + (x["upw"] - 50) * 0.2 - max(0, (x["r1"] or 0) - 35) * 0.8 + min(0, x["mdd"] + 20) * 0.5
            x["score"] = round(sc, 1)
            cand = (x["mkt"] != "US" and (x["ex3"] or -99) >= 10 and (x["ex1"] or -99) > 0 and x["ma50"]
                    and (x["rr"] or 0) >= (e["rr"] or 0) and (x["r1"] or 0) < 35)
            x["verdict"] = "편입 후보" if cand else ("과열 — 눌림 대기" if (x["r1"] or 0) >= 35 and (x["ex3"] or 0) >= 10 else
                                                ("미국보다 강함" if (x["ex3"] or 0) > 0 and x["ma50"] else ("약함" if not x["ma50"] else "비슷")))
            rows.append(x)
        rows.sort(key=lambda r: -r["score"])
        best_non_us = next((r for r in rows if r["mkt"] != "US"), None)
        best_us = next((r for r in rows if r["mkt"] == "US"), None)
        res["themes"].append({"k": T["k"], "name": T["name"], "bucket": T["bucket"], "etf": {"t": T["etf"], **e}, "rows": rows,
                              "cands": [r["t"] for r in rows if r["verdict"] == "편입 후보"][:3],
                              "lead": {"non_us": best_non_us and best_non_us["t"], "us": best_us and best_us["t"]}})
        print(f"{T['name']}: ETF {T['etf']} 3M {e['r3']:+.1f}% · 후보 {res['themes'][-1]['cands']} · 1위 {rows[0]['name'] if rows else '-'}")
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
