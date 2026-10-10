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
    # ── 반도체·AI 하드웨어 (10/10 사용자: "대만 종목은 빼고, 중국·홍콩 종목 중 반도체·반도체 장비·AI 인프라·PCB·광통신·광모듈·MLCC 다 찾아서 비교") ──
    {"k": "semi_chip", "name": "반도체 칩·메모리·AI칩", "etf": "SOXX", "bucket": "반도체",
     "us": [("NVDA", "엔비디아"), ("AVGO", "브로드컴"), ("MU", "마이크론"), ("AMD", "AMD")],
     "peers": [("000660.KS", "SK하이닉스"), ("005930.KS", "삼성전자"), ("285A.T", "키옥시아"),
               ("0981.HK", "SMIC(중신국제)"), ("688981.SS", "SMIC A주"), ("1347.HK", "화홍반도체"), ("688347.SS", "화홍반도체 A주"),
               ("688256.SS", "캠브리콘(寒武纪)"), ("688041.SS", "하이곤(海光信息)"), ("688008.SS", "몬타주(澜起科技)"),
               ("603986.SS", "기가디바이스(兆易创新)"), ("603501.SS", "옴니비전(豪威集团)"), ("688521.SS", "베리실리콘(芯原)"),
               ("600584.SS", "JCET(长电科技)"), ("002156.SZ", "퉁푸마이크로(通富微电)"), ("1385.HK", "상하이푸단"), ("688126.SS", "NSIG(沪硅产业)")]},
    {"k": "semi_eq", "name": "반도체 장비·테스트", "etf": "SOXX", "bucket": "반도체",
     "us": [("AMAT", "어플라이드"), ("LRCX", "램리서치"), ("KLAC", "KLA"), ("TER", "테라다인")],
     "peers": [("6857.T", "어드밴테스트"), ("8035.T", "도쿄일렉트론"), ("6146.T", "디스코"), ("6920.T", "레이저텍"), ("7735.T", "스크린HD"),
               ("042700.KS", "한미반도체"), ("036930.KQ", "주성엔지니어링"),
               ("002371.SZ", "나우라(北方华创)"), ("688012.SS", "AMEC(中微公司)"), ("688072.SS", "피오테크(拓荆科技)"),
               ("688120.SS", "화하이칭커(华海清科)"), ("688082.SS", "ACM상하이(盛美上海)"), ("688037.SS", "킹세미(芯源微)"),
               ("300604.SZ", "창촨커지(长川科技·테스트)"), ("0522.HK", "ASMPT")]},
    {"k": "ai_infra", "name": "AI 서버·데이터센터 인프라", "etf": ["SMCI", "DELL", "VRT", "ANET", "CLS"], "bucket": None,
     "us": [("VRT", "버티브"), ("ANET", "아리스타"), ("CLS", "셀레스티카"), ("DELL", "델")],
     "peers": [("601138.SS", "폭스콘인더스트리얼(工业富联)"), ("000977.SZ", "인스퍼(浪潮信息)"), ("603019.SS", "슈광(中科曙光)"),
               ("000938.SZ", "유니스플렌더(紫光股份)"), ("002837.SZ", "인비크(英维克·액체냉각)"), ("0763.HK", "ZTE H"), ("0992.HK", "레노버"),
               ("5803.T", "후지쿠라"), ("6501.T", "히타치")]},
    {"k": "optic", "name": "광통신·광모듈", "etf": ["COHR", "LITE", "FN", "CIEN", "AAOI"], "bucket": "광통신",
     "us": [("LITE", "루멘텀"), ("COHR", "코히런트"), ("FN", "패브리넷"), ("CIEN", "시에나")],
     "peers": [("300308.SZ", "이노라이트(中际旭创)"), ("300502.SZ", "이옵토링크(新易盛)"), ("300394.SZ", "TFC(天孚通信)"),
               ("002281.SZ", "액셀링크(光迅科技)"), ("688498.SS", "위안제(源杰科技·레이저칩)"), ("300570.SZ", "T&S(太辰光)"),
               ("000988.SZ", "HG테크(华工科技)"), ("600487.SS", "헝퉁광전(亨通光电)"), ("600522.SS", "중톈커지(中天科技)"),
               ("601869.SS", "YOFC(长飞光纤) A주"), ("6869.HK", "YOFC(长飞光纤) H주"), ("5803.T", "후지쿠라"), ("5801.T", "후루카와전기")]},
    {"k": "pcb", "name": "PCB·기판·CCL", "etf": ["TTMI", "SANM", "JBL"], "bucket": "광통신",
     "us": [("TTMI", "TTM")],
     "peers": [("002463.SZ", "후뎬(沪电股份)"), ("300476.SZ", "빅토리자이언트(胜宏科技)"), ("002916.SZ", "선난서킷(深南电路)"),
               ("600183.SS", "성이커지(生益科技·CCL)"), ("688183.SS", "성이전자(生益电子)"), ("002913.SZ", "아오스캉테크(奥士康)"),
               ("603228.SS", "킨웡(景旺电子)"), ("002938.SZ", "아바리(鹏鼎控股)"), ("1888.HK", "킹보드라미네이트(建滔积层板)"),
               ("0148.HK", "킹보드홀딩스(建滔集团)"), ("4062.T", "이비덴"), ("007660.KS", "이수페타시스"), ("353200.KQ", "대덕전자")]},
    {"k": "mlcc", "name": "MLCC·수동부품", "etf": "SOXX", "bucket": None,
     "us": [("VSH", "비샤이"), ("APH", "암페놀")],
     "peers": [("6981.T", "무라타"), ("6762.T", "TDK"), ("6976.T", "다이요유덴"), ("009150.KS", "삼성전기"),
               ("000636.SZ", "펑화가오커(风华高科)"), ("300408.SZ", "산환그룹(三环集团)"), ("603678.SS", "훠쥐전자(火炬电子)"),
               ("603267.SS", "훙위안전자(鸿远电子)"), ("300285.SZ", "궈츠소재(国瓷材料)"), ("002138.SZ", "선러드(顺络电子)")]},
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
FX = {".T": "JPY=X", ".KS": "KRW=X", ".KQ": "KRW=X", ".SS": "CNY=X", ".SZ": "CNY=X", ".HK": "HKD=X"}
CUR = {".T": "엔", ".KS": "원", ".KQ": "원", ".SS": "위안", ".SZ": "위안", ".HK": "홍콩달러"}
MKT = {".T": "JP", ".KS": "KR", ".KQ": "KR", ".SS": "CN", ".SZ": "CN", ".HK": "HK"}


def buyable(t):
    """한국 개인이 살 수 있나 — 후강퉁·선강퉁에서 창업판(300·301)·과창판(688·689)은 기관 전문투자자만 (HKEX 안내)"""
    c = t.split(".")[0]
    if t.endswith(".SZ") and c[:3] in ("300", "301"):
        return False, "창업판 — 한국 개인 매매 불가(기관만)"
    if t.endswith(".SS") and c[:3] in ("688", "689"):
        return False, "과창판 — 한국 개인 매매 불가(기관만)"
    return True, ""


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
        tick |= set(T["etf"]) if isinstance(T["etf"], list) else {T["etf"]}
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

    # 미국 기준이 ETF 가 아니라 대표 종목 묶음이면 같은 비중 평균 지수로 만든다 (광모듈·AI 서버·PCB 는 딱 맞는 ETF 가 없음)
    for T in THEMES:
        if isinstance(T["etf"], list):
            ss = [C[t] / C[t].iloc[0] for t in T["etf"] if t in C]
            if ss:
                C["BASKET:" + T["k"]] = pd.concat(ss, axis=1).ffill().dropna().mean(axis=1) * 100

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

    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "note": "달러 기준 수익률(환율 반영) · 대만 제외(10/10) · 창업판(300)·과창판(688)은 비교만, 한국 개인은 후강퉁·선강퉁으로 못 삼 · 판단 재료이며 매수 추천 아님", "themes": []}
    for T in THEMES:
        bk = isinstance(T["etf"], list)
        e = m("BASKET:" + T["k"] if bk else T["etf"])
        if not e:
            continue
        rows = []
        for t, nm in T["us"] + T["peers"]:
            x = m(t)
            if not x:
                continue
            sx = suf(t)
            ok_buy, why_no = buyable(t)
            x.update({"t": t, "name": nm, "mkt": MKT.get(sx, "US"), "cur": CUR.get(sx, "달러"), **({} if ok_buy else {"nobuy": why_no}),
                      "ex3": round(x["r3"] - e["r3"], 2) if x["r3"] is not None else None,
                      "ex1": round(x["r1"] - e["r1"], 2) if x["r1"] is not None else None})
            # 종합 점수: 초과 수익(3·1개월) + 위험 대비 수익 + 추세 + 꾸준함 − 과열·낙폭
            sc = (x["ex3"] or 0) * 0.5 + (x["ex1"] or 0) * 0.5 + (x["rr"] or 0) * 10 + (10 if x["ma50"] else -10) + (5 if x.get("ma200") else 0) \
                + (x["upw"] - 50) * 0.2 - max(0, (x["r1"] or 0) - 35) * 0.8 + min(0, x["mdd"] + 20) * 0.5
            x["score"] = round(sc, 1)
            cand = (x["mkt"] != "US" and (x["ex3"] or -99) >= 10 and (x["ex1"] or -99) > 0 and x["ma50"]
                    and (x["rr"] or 0) >= (e["rr"] or 0) and (x["r1"] or 0) < 35)
            if cand and not ok_buy:
                x["verdict"] = "강함 — 개인 매매 불가"
            else:
              x["verdict"] = "편입 후보" if cand else ("과열 — 눌림 대기" if (x["r1"] or 0) >= 35 and (x["ex3"] or 0) >= 10 else
                                                ("미국보다 강함" if (x["ex3"] or 0) > 0 and x["ma50"] else ("약함" if not x["ma50"] else "비슷")))
            rows.append(x)
        rows.sort(key=lambda r: -r["score"])
        best_non_us = next((r for r in rows if r["mkt"] != "US"), None)
        best_us = next((r for r in rows if r["mkt"] == "US"), None)
        res["themes"].append({"k": T["k"], "name": T["name"], "bucket": T["bucket"],
                              "etf": {"t": ("미국 " + "·".join(T["etf"]) + " 평균") if bk else T["etf"], **e}, "rows": rows,
                              "cands": [r["t"] for r in rows if r["verdict"] == "편입 후보"][:3],
                              "lead": {"non_us": best_non_us and best_non_us["t"], "us": best_us and best_us["t"]}})
        print(f"{T['name']}: 기준 {res['themes'][-1]['etf']['t']} 3M {e['r3']:+.1f}% · 후보 {res['themes'][-1]['cands']} · 1위 {rows[0]['name'] if rows else '-'}")
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
