"""킥 후보 찾기 — 「기대와 실제가 엇갈린 숫자」를 자동으로 뽑아 작성 단계에 넘긴다.

킥 = 남들이 안 한 계산 하나로 찾은 엇갈림 + 그래서 무엇을 하나.
  예) 9/29 「지수는 −1.5%인데 430개 종목 합산은 −21.7%」 → 지수는 멀쩡, 종목은 약세장
      10/1 「유가·물가·연준 셋 다 내렸는데 금리만 올랐다」 → 남는 원인은 공급

사용법:
  python -m src.kick            # 후보를 점수 순으로 출력 + market/kick_candidates.json 저장
작성자는 후보 중 하나를 고르거나(숫자 다시 확인), 직접 더 좋은 엇갈림을 찾는다.
엇갈림이 없는 날은 data.kick.none = true 로 「오늘은 킥 없음」을 솔직히 쓴다.
"""
from __future__ import annotations
import csv, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPASS = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/opdata/compass.json"


def _latest():
    try:
        return json.loads((ROOT / "market" / "latest.json").read_text(encoding="utf-8")).get("items", {})
    except Exception:
        return {}


def _hist():
    rows = []
    try:
        with open(ROOT / "market" / "history.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append({k: (float(v) if v not in ("", None) and k != "date" else v) for k, v in r.items()})
    except Exception:
        pass
    return rows


def _compass():
    try:
        with urllib.request.urlopen(COMPASS, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _ch(it, k):
    x = it.get(k) or {}
    return x.get("change_pct")


def _streak(rows, key, sign):
    """마지막부터 같은 방향(sign>0 오름 / <0 내림)이 며칠 이어졌나 — 값 자체(외국인) 또는 변화(나머지)"""
    vals = [r.get(key) for r in rows if isinstance(r.get(key), float)]
    n = 0
    if key == "foreign_kospi":
        for v in reversed(vals):
            if (v > 0) == (sign > 0) and v != 0:
                n += 1
            else:
                break
        return n
    for a, b in zip(reversed(vals[:-1]), reversed(vals[1:])):
        if (b - a) * sign > 0:
            n += 1
        else:
            break
    return n


def candidates():
    it, rows, C = _latest(), _hist(), _compass()
    out = []

    def add(score, title, rows_, so, kind="contrast"):
        out.append({"score": round(score, 2), "title": title, "rows": rows_, "so": so, "kind": kind})

    ten = (it.get("us10y") or {})
    d10 = _ch(it, "us10y")              # 10년 금리 % 변화(상대) → bp 로 환산
    bp10 = round((ten.get("value") or 0) * (d10 or 0) / 100 * 100, 1) if d10 is not None else None
    wti, nas, spx, vix, krw, gold = (_ch(it, k) for k in ("wti", "nasdaq", "sp500", "vix", "usdkrw", "gold"))
    kospi, ss, hx, mu, nv = (_ch(it, k) for k in ("kospi", "samsung", "hynix", "micron", "nvidia"))
    fk = (it.get("foreign_kospi") or {}).get("value")
    d2 = _ch(it, "us2y")

    # ① 금리 혼자: 유가↓·2년↓인데 10년↑
    if bp10 is not None and bp10 >= 2 and ((wti is not None and wti < -0.5) or (d2 is not None and d2 < 0)):
        add(1 + bp10 / 4 + abs(wti or 0) / 2, "금리를 내릴 재료가 나왔는데 10년 금리만 올랐다",
            [{"label": "유가(WTI)", "text": f"{wti:+.1f}%" if wti is not None else "–", "dir": -1},
             {"label": "미 2년 금리", "text": f"{d2:+.2f}%" if d2 is not None else "–", "dir": -1 if (d2 or 0) < 0 else 1},
             {"label": "미 10년 금리", "text": f"{bp10:+.1f}bp", "dir": 1, "hi": True}],
            "단기는 연준, 장기는 공급이 정한다는 증거 — 장기채 0 유지 근거")
    # ② 주식과 금리가 같이 오름 / 같이 내림
    if bp10 is not None and nas is not None and abs(bp10) >= 3 and abs(nas) >= 0.8 and (bp10 > 0) == (nas > 0):
        add(0.8 + abs(nas) / 2 + abs(bp10) / 6, "주식과 금리가 같은 방향" + ("으로 올랐다 — 주식이 금리를 무시" if nas > 0 else "으로 내렸다 — 금리 하락도 주식을 못 살림"),
            [{"label": "나스닥", "text": f"{nas:+.1f}%", "dir": 1 if nas > 0 else -1, "hi": True}, {"label": "미 10년 금리", "text": f"{bp10:+.1f}bp", "dir": 1 if bp10 > 0 else -1, "hi": True}],
            "평소엔 반대로 움직이는 둘 — 같이 가는 날이 이어지면 국면이 바뀌는 신호")
    # ③ 지수는 오르는데 외국인은 판다 (또는 반대)
    if kospi is not None and fk is not None and abs(kospi) >= 0.3 and (kospi > 0) != (fk > 0) and abs(fk) >= 1000:
        n = _streak(rows, "foreign_kospi", -1 if fk < 0 else 1)
        add(0.9 + abs(fk) / 10000 + n / 5, f"코스피는 {kospi:+.1f}%인데 외국인은 {fk/10000:+.2f}조" + (f" ({n}일째)" if n > 1 else ""),
            [{"label": "코스피", "text": f"{kospi:+.2f}%", "dir": 1 if kospi > 0 else -1}, {"label": "외국인 순매수", "text": f"{fk:+,.0f}억", "dir": 1 if fk > 0 else -1, "hi": True}],
            "누가 받쳤나(개인·기관)를 확인 — 외국인 없는 상승은 오래 못 가는 경우가 많음")
    # ④ 원화 강세인데 외국인 매도 (보통은 같이 감)
    if krw is not None and fk is not None and krw < -0.3 and fk < -3000:
        add(0.7 + abs(krw) + abs(fk) / 20000, "원화가 강해졌는데 외국인은 팔았다",
            [{"label": "원/달러", "text": f"{krw:+.2f}%", "dir": -1}, {"label": "외국인", "text": f"{fk:+,.0f}억", "dir": -1, "hi": True}],
            "환율 때문이 아닌 매도 — 업종·종목 자체를 줄이는 중일 수 있음")
    # ⑤ 반도체 엇갈림: 삼성 vs 하이닉스 / 미국 반도체 vs 한국 반도체
    if ss is not None and hx is not None and abs(ss - hx) >= 2:
        add(0.6 + abs(ss - hx) / 2, f"삼성 {ss:+.1f}% vs 하이닉스 {hx:+.1f}% — 같은 반도체, 다른 방향",
            [{"label": "삼성전자", "text": f"{ss:+.1f}%", "dir": 1 if ss > 0 else -1, "hi": ss < hx}, {"label": "SK하이닉스", "text": f"{hx:+.1f}%", "dir": 1 if hx > 0 else -1, "hi": hx < ss}],
            "HBM 익스포저 차이가 가격에 붙는 중인지 확인")
    us_semi = [v for v in (mu, nv) if v is not None]
    if us_semi and hx is not None and ss is not None:
        u, k = sum(us_semi) / len(us_semi), (hx + ss) / 2
        if abs(u - k) >= 2.5 and (u > 0) != (k > 0):
            add(0.7 + abs(u - k) / 3, f"미국 반도체 {u:+.1f}% · 한국 반도체 {k:+.1f}% — 반대로 갔다",
                [{"label": "마이크론·엔비디아", "text": f"{u:+.1f}%", "dir": 1 if u > 0 else -1}, {"label": "삼성·하이닉스", "text": f"{k:+.1f}%", "dir": 1 if k > 0 else -1, "hi": True}],
                "한국이 미국을 다음 날 따라가는지가 판정")
    # ⑥ VIX 와 S&P 가 같이 오름 = 오르면서 보험을 사는 중
    if vix is not None and spx is not None and vix > 3 and spx > 0.3:
        add(0.6 + vix / 10, f"S&P {spx:+.1f}%인데 공포지수 VIX도 {vix:+.1f}%",
            [{"label": "S&P500", "text": f"{spx:+.1f}%", "dir": 1}, {"label": "VIX", "text": f"{vix:+.1f}%", "dir": 1, "hi": True}],
            "오르면서 하락 보험을 사는 장 — 다음 충격에 민감")
    # ⑦ 금과 금리가 같이 오름
    if gold is not None and bp10 is not None and gold > 0.8 and bp10 > 3:
        add(0.6 + gold / 2, f"금리 {bp10:+.1f}bp인데 금도 {gold:+.1f}%",
            [{"label": "미 10년 금리", "text": f"{bp10:+.1f}bp", "dir": 1}, {"label": "금", "text": f"{gold:+.1f}%", "dir": 1, "hi": True}],
            "이자 없는 금이 금리와 같이 오름 = 돈의 가치(재정·물가)를 의심하는 중")
    # ⑧ 지수 vs 종목 (나침반 시장 폭)
    for mk, nm in (("KR", "코스피"), ("US", "S&P500")):
        m = (C or {}).get("markets", {}).get(mk)
        if not m or not m.get("index"):
            continue
        ix = m["index"][0]
        up, dn = m.get("up") or 0, m.get("down") or 0
        r = up / max(1, up + dn) * 100
        if ix.get("chg1") is not None and ((ix["chg1"] > 0.3 and r < 45) or (ix["chg1"] < -0.3 and r > 55)):
            add(1 + abs(ix["chg1"]) + abs(r - 50) / 10, f"{ix['name']} {ix['chg1']:+.1f}%인데 오른 종목은 {r:.0f}%",
                [{"label": ix["name"], "text": f"{ix['chg1']:+.1f}%", "dir": 1 if ix["chg1"] > 0 else -1},
                 {"label": "오른 종목 비율", "text": f"{r:.0f}% ({up:,}/{up + dn:,})", "dir": 1 if r > 50 else -1, "hi": True},
                 {"label": "종목 중간값", "text": f"{m.get('median1', 0):+.1f}%", "dir": 1 if (m.get("median1") or 0) > 0 else -1}],
                "지수는 몇 개 대형주가 끈 것 — 내 종목 체감과 다른 이유", kind="breadth")
        hi_, lo_ = m.get("highs") or 0, m.get("lows") or 0
        if ix.get("hi52") and ix.get("last") and ix["last"] >= ix["hi52"] * 0.97 and lo_ > hi_ and lo_ >= 20:
            add(1.2 + (lo_ - hi_) / max(10, hi_ + lo_), f"{ix['name']}는 1년 고점 근처인데 신저가 종목({lo_})이 신고가({hi_})보다 많다",
                [{"label": f"{ix['name']} 1년 고점 대비", "text": f"{(ix['last'] / ix['hi52'] - 1) * 100:+.1f}%", "dir": 1},
                 {"label": "52주 신고가", "text": f"{hi_}", "dir": 1}, {"label": "52주 신저가", "text": f"{lo_}", "dir": -1, "hi": True}],
                "지수와 종목이 갈라지는 장 — 지수가 아니라 종목을 봐야 함", kind="breadth")
    # ⑨ 며칠째 같은 방향 (흐름이 쌓인 것)
    for key, nm, unit in (("foreign_kospi", "외국인 코스피 순매도", "일"), ("us10y", "미 10년 금리 상승", "일")):
        n = _streak(rows, key, -1 if key == "foreign_kospi" else 1)
        if n >= 5:
            add(0.5 + n / 5, f"{nm} {n}{unit} 연속", [{"label": nm, "text": f"{n}{unit}째", "dir": -1 if key == "foreign_kospi" else 1, "hi": True}],
                "하루 뉴스가 아니라 흐름 — 끊기는 날이 판정일", kind="streak")
    out.sort(key=lambda x: -x["score"])
    return out


def main():
    c = candidates()
    (ROOT / "market").mkdir(exist_ok=True)
    (ROOT / "market" / "kick_candidates.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    if not c:
        print("자동 후보 없음 — 직접 찾거나, 엇갈림이 없으면 kick.none = true")
    for i, x in enumerate(c[:6], 1):
        print(f"{i}. [{x['score']}] {x['title']}")
        for r in x["rows"]:
            print(f"     {'★' if r.get('hi') else ' '} {r['label']}: {r['text']}")
        print(f"     → 그래서? {x['so']}")


if __name__ == "__main__":
    main()
