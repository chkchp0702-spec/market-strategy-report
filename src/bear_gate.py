"""🐻 하락장 계기판 — 시장별 판정 · 현금 권고 · 바닥 신호 체크리스트 (11/09 사용자)

  사용자 11/09: 「하락장이라고 판단되면 현금 비중 늘리게 권해야 하고, 바닥이라고 생각되면
  이 조건이 충족되면 비중을 늘리자 — 이렇게 네가 설명하고 이끌어야지」
  배경: 11/03 두뇌가 정한 판정선(코스피 5,665 = −20%)이 11/03 종가에 이미 깨졌는데,
  「위험 회피」 한 단어로 뭉뚱그려 결론·알림이 없었다 → 기계가 매일 종가로 판정하고 알린다.

  결과 보기 전 등록한 규칙 (바꾸려면 이 글과 bear.json 의 rules 를 같이 고친다)
  ─ 판정 (완성된 종가만 · 장중 막대는 버림)
     낙폭 = 종가 ÷ 최근 252거래일 최고 종가 − 1
     🟢 정상   낙폭 > −10%
     🟡 조정   −20% < 낙폭 ≤ −10%
     🐻 하락장 낙폭 ≤ −20%
     한 번 🐻 이 되면 「낙폭 > −10% 이고 200일선 위」가 될 때까지 🐻(회복 중)으로 둔다 — 반등 하루에 판정이 흔들리지 않게
  ─ 🌱 바닥 신호 4개 (조정·하락장일 때만 셈)
     ① 저점 다지기 : 최근 60일 최저 종가가 10거래일 넘게 안 깨짐
     ② 20일선 회복 : 종가가 20일선 위 2일 연속
     ③ 공포 진정   : VIX 종가 20 아래
     ④ 수급·추세   : 🇰🇷 외국인 코스피 3일 연속 순매수 / 🇺🇸 종가 50일선 위
  ─ 현금 권고 (그 시장 주식 몫 중 현금으로 둘 비율) — ★ 지금(11/09 오후 2차 「코스피는 켜고 미국은 끄는걸로」 · lab b1109_cash):
     🇰🇷 코스피 = 🐻 하락장이면 100% · 🟡 조정 0% · 판정 풀릴 때(고점 −10% 위 + 200일선 위)까지 / 🇺🇸 S&P·나스닥 = 꺼 둠(0%) · 판정은 참고
     (아래는 그 전 단계 기록 — 오전 등록본 → 오후 1차 E/F)
     (처음 등록: 🟡 10→5→0 · 🐻 30→20→10→0, 신호 2·3·4개 — lab b1109_floor 에서 코스피 처음 다시 산 날 뒤 바닥이 더 남은 때 10번 중 8번 ·
      1년에 19.5번 바뀜. 판 7개를 2012년 앞에서 고르고 뒤에서 확인: 코스피는 E 가 앞·뒤 모두 나음 / 미국은 F 가 앞에서만 나음 → 미국은 단순·덜 흔들림으로 F)
     🇰🇷 코스피 = E 추세 확인 : 🐻 30% → ① 저점 다지기 + ④ 50일선 위 → 10% → 거기에 ② 20일선 회복까지 → 0%
                               🟡 10% → ①+④ → 0%   (③ VIX 는 참고만 · ④ 외국인 순매수도 참고만 — 과거 검증은 50일선으로 했으므로)
     🇺🇸 S&P500·나스닥 = F 판정만 : 🐻 30% · 🟡 10% 를 판정이 풀릴 때(고점 −10% 위 + 200일선 위)까지 유지 · 바닥 신호는 참고만
     새 저점이 나오면 ①②④가 꺼져 E 는 자동으로 현금이 다시 늘어난다.
     🐻 판정 때 이미 −25% 넘게 빠졌으면 「바닥에서 팔지 말고 반등(20일선 근처) 때 나눠 덜기」를 같이 권한다.

  market/bear.json      : 앱 오늘 홈·시장 탭 카드, 아침 리포트, 두뇌가 읽음 (🐻 시장엔 rebounds — 11/10 A11/10-1 이번 하락장 +3% 반등 날 · 20거래일 안 저점 재돌파 기록)
  market/bear_log.json  : 판정·신호 수가 바뀐 날 기록 (나중에 채점)
  market/bear_bt.json   : --bt — 2000년부터 규칙대로 했다면 vs 그냥 들고 있기 (코스피·S&P·나스닥)
  알림: 판정이나 현금 권고가 바뀐 날 한 번 ntfy(chkchp-ch-report).
  fetch.yml 이 매시간 돌린다(값이 바뀔 때만 알림). 매수 추천 아님.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "market"
OUT, LOG, BT = M / "bear.json", M / "bear_log.json", M / "bear_bt.json"
SIG = M / "bear_sig_bt.json"   # 🌱 11/09 A11/9-1 바닥 신호 4개의 과거 성적표 (--bt 때 같이 만듦 → live 가 bear.json 시장마다 hist 로 붙임)
H6 = 126                        # 6개월 ≈ 126거래일
APP = "https://chkchp0702-spec.github.io/daily-app/"

MKTS = [  # key, 야후 코드, 이름, 나라, 장 마감(현지)
    ("kospi", "^KS11", "코스피", "kr", (15, 40)),
    ("kosdaq", "^KQ11", "코스닥", "kr", (15, 40)),   # 🌱 11/11 사용자 「코스피나 코스닥도 바닥 신호 나오면 알려주고」 — 판정·바닥 신호·알림 (현금 규칙은 참고)
    ("sp500", "^GSPC", "S&P500", "us", (16, 15)),
    ("nasdaq", "^IXIC", "나스닥", "us", (16, 15)),
]
CORR, BEAR, EXIT = -0.10, -0.20, -0.10
CASH = {"🟢": [0, 0, 0, 0, 0], "🟡": [10, 10, 5, 0, 0], "🐻": [30, 30, 20, 10, 0]}   # 처음 등록본(11/09 오전) — 지금은 RULE 로 셈
MAXC = {"🐻": 30, "🟡": 10, "🟢": 0}
# 11/09 오후 1차 「네 추천대로」(lab b1109_floor): 🇰🇷 E · 🇺🇸 F
# 11/09 오후 2차 「코스피는 켜고 미국은 끄는걸로」(lab b1109_cash · 2012 앞에서 고르고 뒤에서 확인):
#   🇰🇷 K100 = 🐻 하락장이면 주식 몫 전부 현금(100%) · 🟡 조정은 0% · 판정 풀릴 때(고점 −10% 위 + 200일선 위)까지 — 앞 +0.85 · 뒤 +1.11%p · 낙폭 −54.5→−33.7
#   🇺🇸 OFF  = 현금 규칙 끔(2013 이후 판 60개 전부 보유에 짐) — 판정은 참고로만 보여 줌
RULE = {"kospi": "K100", "kosdaq": "C6", "sp500": "B50", "nasdaq": "OFF"}
# 🏁 11/11 사용자 「각 시장의 최선을 다 백테스트 해서 수익률 제일 좋았던 방식을 채택해」 → src/best_bt.py (market/best_bt.json)
#   들어가기 7 × 나오기 5 × 몫 2 × 피난처 + 지금 규칙·지금 규칙+겹치기 · 앞(~2012)·뒤(2013~) 둘 다 보유를 이긴 것 중 전체 연수익 1등
#   🇰🇷 코스피 = 지금 규칙(K100+신용 경보) + 「버블 시계 4.5시 → 바닥 ①④ 까지 현금 100%」 · 연 9.66 → 10.66% · 낙폭 −28.7 → −25.8% (단, 2013 뒤만 보면 9.13 → 7.93%)
#   🇰🇷 코스닥 = C6 「버블 시계 6시 → 신저가 뒤 바닥 신호 3개까지 현금 100%」 · 보유 −0.81 → 4.67% · 낙폭 −72.3 → −50.8%
#   🇺🇸 S&P500 = B50 + 「신용 경보+200일선 아래 → 바닥 ①④ 까지 절반 중기국채」 · 9.20 → 9.41% · 낙폭 −42.0 → −40.1%
#   🇺🇸 나스닥 = 211판 중 앞·뒤 모두 보유를 이긴 판 없음 → 그냥 들고 있기(OFF)
BEST = {"kospi": (100, "🏁 버블 시계 4.5시"), "kosdaq": (100, "🏁 버블 시계 6시"), "sp500": (50, "🏁 신용 경보 + 200일선 아래")}
# 🌱 11/11 사용자 「코스피나 코스닥도 바닥 신호 나오면 알려주고 비중 담게 하자」 → src/kr_floor_bt.py (market/kr_floor_bt.json)
#   🐻 동안 신저가 뒤 바닥 신호(①④ · ①②④ · 3개 · 계단)로 먼저 다시 담는 판 5개 모두: 앞(~2012)은 K100 보다 +2.4~+6.3%p 좋았지만
#   뒤(2013~)는 −2.2~−2.5%p 나빴고 최대 낙폭도 커짐(코스피 −33.7 → −63%) → 비중 자동 담기는 연결 안 함 · 바닥 신호는 새로 켜질 때마다 🌱 알림(참고)
#   첫발(11/11 2차 · 사용자 「첫발 규칙 ㄱㄱ」): 신호 뒤 주식 10·20·30%만 먼저 18판(코스피·코스닥 × ①④·①②④·3개 × 10·20·30) — 앞 +0.3~+2.0%p 이지만 뒤 −0.2~−0.7%p 로 전부 탈락 → 연결 안 함 · 알림에 비용만 적음
#   코스닥 = 판정·바닥 신호·알림만(REF) · 현금 규칙은 참고(K100 을 코스닥에 쓰면 연 −1.0% vs 보유 −0.8% · 낙폭 −44.9 vs −72.3%)
# 🛡 11/11 사용자 「네 추천대로 진행해」(us_floor_bt — 사용자 제안: 경고 신호에 채권형 → 바닥 신호에 다시 주식):
#   🇺🇸 S&P500 B50 = 1년 고점 −10%(조정) 이하면 주식 몫 절반을 채권형(중기국채)으로 · 그 뒤 60일 신저가가 한 번 나오고 바닥 신호 3개 이상이면 다시 주식
#                    (신저가 없이 −10% 위로 올라오면 그냥 복귀 · 복귀 뒤 −10% 아래에서 60일 신저가가 또 나오면 다시 절반)
#   180판 중 합격 8개가 전부 이 묶음 — 앞(~2012) +0.9 · 뒤(2013~) +0.1%p/년 · 최대 낙폭 −55.2 → −42.0% (2013 뒤 −33.7 → −21.9%) · 1년 3.4번
#   🇺🇸 나스닥 = 180판 모두 탈락 → OFF 유지
# 🕰 11/11 사용자 「다 해」(버블 시계 백테스트 → 결과 좋으면 연결): 🇰🇷 코스피만 K100 위에 「대리 버블 시계」를 얹음 (KC)
#   대리 시계 ≥ 3시(신용 단계 다 울음) + 코스피 200일선 아래 → 주식 몫 전부 현금 · 시계 1.5시 아래 또는 200일선 위 + 3시 아래면 풀림
#   2012년까지 고르고 2013년부터 확인: K100 대비 앞 +1.6 · 뒤 +1.0%p/년 · 최대 낙폭 −33.7 → −28.7% (src/bubble_bt.py · market/bubble_bt.json)
#   🇺🇸 은 시계 판 32개(순서 문 있는 20 · 없는 12) 모두 2013년 뒤에 보유에 짐 → 연결 안 함
CLOCK_ON = {"kospi"}
PROXY = M / "bubble_proxy.json"
# 🧩 11/12 사용자 「규칙에 적용시켜」 → src/rule_bt.py 가 나라별 다른 자료 신호(alt_bt 통과)를 지금 규칙에 얹어 보고, 2012년까지·2013년부터 둘 다 나아진 것만 채택
#   → market/rule_overlay.json (평일 아침 alt.yml) — 🚨 경고 얹기: 켜지면 주식 몫 n% 를 현금(채권형) · 🌱 바닥 얹기: 켜지면 현금을 풂
#   11/12 첫 판: 코스닥만 채택 「🇺🇸 CAPE 비쌈(과거 상위 10%) → 주식 몫 50% 현금」 (연 3.95 → 4.91% · 최대 낙폭 −49.9 → −41.9%)
OVERLAY = M / "rule_overlay.json"
ANALOG = M / "analog_pick.json"
RULE_NM = {"E": "추세 확인 — 저점 다지기 + 50일선 위면 현금 10%, 20일선까지 회복하면 0%",
           "F": "판정만 — 하락장이 풀릴 때(고점 −10% 위 + 200일선 위)까지 현금 유지 · 바닥 신호로 미리 안 삼",
           "K100": "하락장이면 주식 몫 전부 현금(100%) — 판정이 풀릴 때(고점 −10% 위 + 200일선 위)까지 · 조정(−10%)은 현금 안 늘림",
           "B50": "조정(고점 −10%)이면 주식 몫 절반을 채권형(중기국채)으로 — 신저가가 나온 뒤 바닥 신호 3개 이상 켜지면 다시 주식",
           "C6": "버블 시계 6시가 되면 주식 몫 전부 현금 — 신저가가 나온 뒤 바닥 신호 3개 켜지면 다시 주식 (11/11 best_bt 1등)",
           "REF": "현금 규칙 없음(참고) — 판정과 바닥 신호만 보여 주고, 바닥 신호가 새로 켜지면 알림",
           "OFF": "현금 규칙 꺼 둠 — 2013년 이후엔 어떤 현금 규칙도 그냥 보유를 못 이김 · 판정은 참고로만"}
USE = {"C6": [True, True, True, True], "REF": [True, True, True, True], "B50": [True, True, True, True], "E": [True, True, False, True], "F": [False] * 4, "K100": [False] * 4, "OFF": [False] * 4}
MAXR = {"C6": {"🐻": 0, "🟡": 0, "🟢": 0}, "REF": {"🐻": 0, "🟡": 0, "🟢": 0}, "B50": {"🐻": 0, "🟡": 0, "🟢": 0},   # B50 은 상태 기계라 live 에서 b50_walk 로 셈(--bt 표는 보유로 나옴 · 진짜 검증은 us_floor_bt.json)
        "K100": {"🐻": 100, "🟡": 0, "🟢": 0}, "OFF": {"🐻": 0, "🟡": 0, "🟢": 0}}


def rule_cash(rid, st, ons):
    """ons = 바닥 신호 4개(④ = 50일선 위 종가) → 현금 %"""
    if st == "🟢":
        return 0
    if rid in MAXR:
        return MAXR[rid][st]
    if rid == "F":
        return MAXC[st]
    if st == "🐻":
        return 0 if (ons[0] and ons[1] and ons[3]) else 10 if (ons[0] and ons[3]) else 30
    return 0 if (ons[0] and ons[3]) else 10


def b50_walk(cl, vx):
    """us_floor_bt 의 states() 와 같은 걸음 — 전체 종가를 처음부터 훑어 오늘 B50 이 채권형 절반인지
       → (in?, 들어간 날 index, 신저가 봤나?, 바닥 신호 수)"""
    n = len(cl); inn = False; armed = True; seen = False; byb = False; i0 = None; nb = 0
    for i in range(260, n):
        c = cl[i]
        hi = max(cl[max(0, i - 251):i + 1]); dd = c / hi - 1
        w = cl[max(0, i - 59):i + 1]; lo = min(w)
        low60 = c <= lo
        since = len(w) - 1 - w.index(lo)
        m20, m20p, m50 = sma(cl, 20, i), sma(cl, 20, i - 1), sma(cl, 50, i)
        b1 = since > 10
        b2 = m20 is not None and m20p is not None and c > m20 and cl[i - 1] > m20p
        b3 = bool(vx and vx[i] is not None and vx[i] < 20)
        b4 = m50 is not None and c > m50
        nb = b1 + b2 + b3 + b4
        eo = eh = dd <= -0.10
        if not inn:
            if eo and armed:
                inn, seen, armed, byb, i0 = True, low60, False, False, i
            elif byb and low60 and eh:
                inn, seen, byb, i0 = True, True, False, i
            if not eh:
                armed, byb = True, False
        else:
            seen = seen or low60
            if seen and nb >= 3:
                inn, byb = False, True
            elif not seen and not eh:
                inn, armed = False, True
    return inn, i0, seen, nb


def ladder(rid, st):
    if rid == "C6":
        return [[100, "버블 시계 6시 — 주식 몫 전부 현금"], [0, "신저가 뒤 바닥 신호 3개 · 또는 신저가 없이 시계 4.5시 아래로"]]
    if rid == "REF":
        return []
    if rid == "B50":
        return [[50, "조정(고점 −10%) — 주식 몫 절반 채권형"], [0, "신저가 뒤 바닥 신호 3개 이상 · 또는 신저가 없이 −10% 위로"]]
    if st == "🟢" or rid == "OFF":
        return []
    if rid == "K100":
        return [[100, "하락장 동안"], [0, "판정 풀림 (고점 −10% 위 + 200일선 위)"]] if st == "🐻" else [[0, "조정 — 현금 안 늘림 (−20% 하락장부터 전부)"]]
    if rid == "F":
        return [[MAXC[st], "지금 판정 동안"], [0, "판정 풀림 (고점 −10% 위 + 200일선 위)"]]
    if st == "🐻":
        return [[30, "①·④ 켜지기 전"], [10, "① 저점 다지기 + ④ 50일선 위"], [0, "①+④ + ② 20일선 회복"]]
    return [[10, "①·④ 켜지기 전"], [0, "① 저점 다지기 + ④ 50일선 위"]]


def apply_rule(r, key):
    """judge() 결과에 시장별 다시 사기 규칙을 입힘 — 🇰🇷 ④는 과거 검증대로 50일선(외국인은 참고 글자로)"""
    rid = RULE.get(key, "F")
    ck = r["checks"]
    if len(ck) == 4 and ck[3]["k"] != "50일선 위 종가":
        m50 = r.get("m50")
        ck[3] = {"k": "50일선 위 종가", "on": bool(m50 and r["close"] > m50),
                 "d": (f"50일선 {m50:,.0f}" + f" · 지금 {r['close'] / m50 - 1:+.1%}" if m50 else "자료 부족") + (f" · 참고: 외국인 {ck[3]['d']}" if ck[3].get("d") else "")}
    ons = [bool(c["on"]) for c in ck]
    for c, u in zip(ck, USE[rid]):
        c["use"] = u
    r["rule"] = {"id": rid, "name": RULE_NM[rid]}
    r["nuse"] = sum(USE[rid])
    r["n"] = sum(1 for c in ck if c["use"] and c["on"]) if r["state"] != "🟢" else 0
    r["cash"] = rule_cash(rid, r["state"], ons)
    r["ladder"] = ladder(rid, r["state"])
    return r
RULES = {
    "판정": "낙폭(252일 최고 종가 대비) > −10% 🟢 정상 · −10~−20% 🟡 조정 · −20% 이하 🐻 하락장 (🐻 은 낙폭 −10% 위 + 200일선 위까지 유지)",
    "바닥 신호": "① 60일 저점 10거래일 안 깨짐 ② 20일선 위 2일 연속 ③ VIX 20 아래 ④ 🇰🇷 외국인 3일 연속 순매수 / 🇺🇸 50일선 위",
    "현금": "🔁 11/12부터 닮은 장 규칙 — 지금 장과 닮았던 과거 12번에서 2년 뒤 가장 나았던 방식이 시장마다 주식 몫을 정함(markets[].analog · more[]) · 예전 규칙 값은 cash_old",
    "등록": "2026-11-09 결과 보기 전 · 같은 날 오후 다시 사기 규칙만 시장별로 바꿈(lab b1109_floor · 사용자 확인)",
}


def rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


# ───────────────────────── 계산 (순수 함수 — 시험 가능) ─────────────────────────
def sma(v, n, i):
    return None if i + 1 < n else sum(v[i - n + 1:i + 1]) / n


def judge(closes, vix=None, foreign=None, kind="us", prev_bear=False, i=None):
    """closes: 종가 리스트(오래된→최근) · vix: 같은 길이(없으면 None) · foreign: 최근 순매수 리스트(🇰🇷)
       → dict(state, dd, n, checks, cash, ...)"""
    i = len(closes) - 1 if i is None else i
    c = closes[i]
    hi = max(closes[max(0, i - 251):i + 1])
    dd = c / hi - 1
    m20, m50, m200 = sma(closes, 20, i), sma(closes, 50, i), sma(closes, 200, i)
    if dd <= BEAR:
        st = "🐻"
    elif prev_bear and not (dd > EXIT and m200 is not None and c > m200):
        st = "🐻"
    elif dd <= CORR:
        st = "🟡"
    else:
        st = "🟢"
    # 바닥 신호
    w = closes[max(0, i - 59):i + 1]
    lo = min(w)
    lo_ago = len(w) - 1 - max(k for k, x in enumerate(w) if x == lo)
    c1 = lo_ago >= 10
    m20p = sma(closes, 20, i - 1) if i >= 1 else None
    c2 = m20 is not None and m20p is not None and c > m20 and closes[i - 1] > m20p
    vx = vix[i] if vix else None
    c3 = vx is not None and vx < 20
    if kind == "kr" and foreign is not None:
        f3 = foreign[-3:]
        c4 = len(f3) == 3 and all(x > 0 for x in f3)
        n4 = "외국인 3일 연속 순매수"
        streak = 0
        for x in reversed(foreign):
            if x > 0:
                streak += 1
            else:
                break
        d4 = f"지금 {streak}일째" if streak else f"최근 {foreign[-1]:+,.0f}억 (순매도)" if foreign else ""
    else:
        c4 = m50 is not None and c > m50
        n4 = "50일선 위 종가"
        d4 = f"50일선 {m50:,.0f}" if m50 else ""
    checks = [
        {"k": "저점 다지기", "on": c1, "d": f"저점 {lo:,.0f} · {lo_ago}거래일 안 깨짐 (10일 필요)"},
        {"k": "20일선 회복", "on": c2, "d": f"20일선 {m20:,.0f}" + (f" · 지금 {c / m20 - 1:+.1%}" if m20 else "") if m20 else "자료 부족"},
        {"k": "공포 진정 (VIX 20↓)", "on": c3, "d": f"VIX {vx:.1f}" if vx is not None else "VIX 미수집"},
        {"k": n4, "on": c4, "d": d4},
    ]
    n = sum(x["on"] for x in checks) if st != "🟢" else 0
    cash = CASH[st][n]
    return {"state": st, "dd": round(dd * 100, 1), "hi": round(hi, 2), "close": round(c, 2), "low60": round(lo, 2),
            "m20": m20 and round(m20, 2), "m50": m50 and round(m50, 2), "m200": m200 and round(m200, 2),
            "n": n, "checks": checks, "cash": cash, "late": st == "🐻" and dd <= -0.25}


def advice(name, r):
    st, cash, rid = r["state"], r["cash"], (r.get("rule") or {}).get("id", "F")
    if r.get("overlay_on") and not r.get("best_on"):
        return f"{name} {'하락장' if st == '🐻' else '조정' if st == '🟡' else '정상'} · 🧩 {r['overlay_on']} — 주식 몫 {cash}% {r.get('to', '현금')}으로 · 그 신호가 꺼지면 다시 주식"
    if r.get("best_on"):
        b = r["best"]
        return (f"{name} {'하락장' if st == '🐻' else '조정' if st == '🟡' else '정상'} · {r['best_why']}({b.get('since') or ''}~) — 주식 몫 {r['cash']}% {r.get('to', '현금')}으로 · "
                f"신저가 뒤 바닥 신호({'①④' if b.get('exit') == 'floor14' else '3개'})가 켜지면 다시 주식 · 지금 바닥 신호 {b.get('nb', 0)}/4")
    if rid == "C6":
        return f"{name} {'하락장' if st == '🐻' else '조정' if st == '🟡' else '정상'} — 주식 비중 그대로 (버블 시계 6시가 되면 전부 현금)"
    if rid == "REF":
        if st == "🟢":
            return f"{name} 정상 — 바닥 신호 볼 필요 없음"
        return (f"{name} {'하락장' if st == '🐻' else '조정'} — 바닥 신호 {sum(1 for c in r['checks'] if c['on'])}/4 · 새로 켜지면 알려 드려요 · "
                "과거(2013년 뒤) 바닥 신호에 전부 담으면 연 −2.5%p · 첫발 10%만 담으면 연 −0.2%p 안팎 — 담더라도 10%만")
    if rid == "B50":
        b = r.get("b50") or {}
        if cash:
            return (f"{name} 조정 — 주식 몫 절반을 채권형(중기국채)으로 · " +
                    (f"신저가 나옴 → 바닥 신호 {b.get('nb', 0)}/4 · 3개 켜지면 다시 주식" if b.get("seen") else "−10% 위로 올라오거나, 신저가 뒤 바닥 신호 3개가 켜지면 다시 주식"))
        return f"{name} {'정상' if st == '🟢' else '조정 끝 신호'} — 주식 비중 그대로 (고점 −10% 아래면 절반을 채권형으로)"
    if r.get("clock_cash") and st != "🐻":
        return (f"{name} {'조정' if st == '🟡' else '정상'}이지만 🕰 신용 경보(하이일드 채권 칸이 다 울음) + 200일선 아래 — "
                "주식 몫 전부 현금 · 신용 칸이 조용해지거나 200일선 위로 올라서면 다시 삼")
    if st == "🟢":
        return f"{name} 정상 — 현금 따로 늘릴 필요 없음 (포트 기본 규칙대로)"
    word = "하락장" if st == "🐻" else "조정"
    late = " · 단, 이미 크게 빠진 뒤라 투매 금지: 20일선 근처로 반등할 때 나눠 덜기" if r.get("late") else ""
    if rid == "OFF":
        return f"{name} {word} — 현금 규칙 꺼 둠(2013년 이후엔 그냥 보유가 늘 나았음) · 판정은 참고만 · 포트 기본 규칙대로"
    if rid == "K100":
        if st == "🟡":
            return f"{name} 조정 — 현금 늘리지 않음 · 고점 −20%(하락장)이 되면 주식 몫 전부 현금"
        return (f"{name} 하락장 — 주식 몫 전부 현금(100%)으로 · 판정이 풀릴 때(고점 −10% 위 + 200일선 위)까지 새로 사지 않기"
                + (" · 단, 이미 크게 빠진 뒤라 한 번에 던지지 말고 20일선 근처 반등 때 나눠 덜기" if r.get("late") else ""))
    if rid == "F":
        return f"{name} {word} — 현금 {cash}%까지 늘리고 판정이 풀릴 때(고점 −10% 위 + 200일선 위)까지 유지 · 바닥 신호로 미리 다시 사지 않기" + late
    if cash == MAXC[st]:
        return f"{name} {word} — 현금 {cash}%까지 늘리기 권고 · 새로 사지 않기" + late + " · 다시 사는 조건: ① 저점 다지기 + ④ 50일선 위"
    if cash == 0:
        return f"{name} 바닥 확인(①+②+④) — 덜어 둔 현금 전부 다시 투입 (기본 비중 복귀)"
    return f"{name} 바닥 확인 1단계(① 저점 다지기 + ④ 50일선 위) — 현금 {cash}%로 줄이며 다시 사기 · ② 20일선 회복까지 켜지면 전부"


# ───────────────────────── 🌱 바닥 신호 과거 성적표 (11/09 A11/9-1) ─────────────────────────
def _med(v):
    v = sorted(v)
    if not v:
        return None
    k = len(v) // 2
    return v[k] if len(v) % 2 else (v[k - 1] + v[k]) / 2


def sig_history(cl, vx, dates, start=252, rid="E"):
    """과거 🐻 하락장마다 바닥 신호 4개가 언제 켜졌나 · 신호 n개째 처음 켜진 날 뒤 6개월.
       판정·신호는 judge() 그대로(과거엔 🇰🇷 ④ 외국인 자료가 없어 50일선 — bear_bt 와 같음).
       「가짜 신호」 = 하락장 안에서 켜졌는데 그 뒤 더 낮은 종가(그 하락장의 바닥)가 나온 것.
       「진짜」 = 바닥 날 이후 처음 켜진 날 — 바닥에서 며칠 뒤 · 바닥보다 몇 % 위."""
    pb, rows = False, {}
    eps, cur = [], None
    for i in range(start, len(cl)):
        j = judge(cl, vx, None, "us", pb, i)
        pb = j["state"] == "🐻"
        ons = [bool(c["on"]) for c in j["checks"]]
        rows[i] = (ons, sum(ons))
        if pb and cur is None:
            cur = {"s": i, "days": []}
        if cur is not None:
            if not pb:
                cur["e"] = i
                eps.append(cur)
                cur = None
            else:
                cur["days"].append(i)
    if cur is not None:
        cur["e"] = None
        eps.append(cur)
    out = []
    for ep in eps:
        ds = ep["days"]
        b = min(ds, key=lambda i: (cl[i], i))   # 바닥(가장 낮은 종가 · 같으면 앞 날)
        sigs = []
        for k in range(4):
            fakes = []
            for i in ds:
                prev = rows.get(i - 1, ([False] * 4, 0))[0][k]
                if rows[i][0][k] and not prev and i < b:
                    fakes.append(round((cl[b] / cl[i] - 1) * 100, 1))   # 켜진 뒤 바닥까지 더 빠진 폭
            on = next((i for i in ds if i >= b and rows[i][0][k]), None)
            sigs.append({"fake": len(fakes), "fake_more": min(fakes) if fakes else None,
                         "on": dates[on] if on is not None else None,
                         "after": (on - b) if on is not None else None,
                         "up": round((cl[on] / cl[b] - 1) * 100, 1) if on is not None else None})
        step = {}   # 다시 사기 규칙의 단계마다 처음 닿은 날 (E: 현금 10% · 0% / F: 판정 풀린 날)
        if rid != "E":
            marks = {"out": ep["e"]} if ep["e"] is not None and ep["e"] < len(cl) else {"out": None}
        else:
            marks = {lv: next((i for i in ds if rule_cash(rid, "🐻", rows[i][0]) <= int(lv)), None) for lv in ("10", "0")}
        for lv, i in marks.items():
            if i is None:
                step[lv] = None
                continue
            r6 = round((cl[i + H6] / cl[i] - 1) * 100, 1) if i + H6 < len(cl) else None
            step[lv] = {"date": dates[i], "r6": r6, "early": i < b, "after": i - b,
                        "up": round((cl[i] / cl[b] - 1) * 100, 1),
                        "more": round((cl[b] / cl[i] - 1) * 100, 1) if i < b else 0.0}
        hi = max(cl[max(0, b - 251):b + 1])
        out.append({"in": dates[ep["s"]], "out": dates[ep["e"]] if ep["e"] is not None else "진행 중",
                    "bottom": dates[b], "bottom_dd": round((cl[b] / hi - 1) * 100, 1),
                    "len": len(ds), "sig": sigs, "step": step})
    done = [x for x in out if x["out"] != "진행 중"]
    names = ["저점 다지기", "20일선 회복", "공포 진정 (VIX 20↓)", "50일선 위 종가"]
    summ = []
    for k in range(4):
        tr = [x["sig"][k] for x in done if x["sig"][k]["on"]]
        fk = [x for x in done if x["sig"][k]["fake"]]
        worst = min(fk, key=lambda x: x["sig"][k]["fake_more"]) if fk else None
        summ.append({"k": names[k], "eps": len(done), "on": len(tr),
                     "after": _med([s["after"] for s in tr]), "up": _med([s["up"] for s in tr]),
                     "fake_eps": len(fk), "fake_n": sum(x["sig"][k]["fake"] for x in done),
                     "fake_worst": worst and {"y": worst["in"][:4], "more": worst["sig"][k]["fake_more"]}})
    LBL = {"10": "① 저점 다지기 + ④ 50일선 위 → 현금 10%", "0": "②까지 켜져 현금 0% (다 다시 삼)", "out": "하락장 판정 풀림 → 현금 0% (다 다시 삼)"}
    steps = []
    for lv in (("out",) if rid != "E" else ("10", "0")):
        hit = [x for x in done if x["step"].get(lv)]
        r6 = [x for x in hit if x["step"][lv]["r6"] is not None]
        early = [x for x in hit if x["step"][lv]["early"]]
        wm = min(early, key=lambda x: x["step"][lv]["more"]) if early else None
        steps.append({"lv": lv, "label": LBL[lv], "eps": len(done), "hit": len(hit),
                      "pos6": sum(x["step"][lv]["r6"] > 0 for x in r6), "neg6": sum(x["step"][lv]["r6"] <= 0 for x in r6),
                      "early": len(early), "worst_more": wm and {"y": wm["in"][:4], "more": wm["step"][lv]["more"]},
                      "after": _med([x["step"][lv]["after"] for x in hit]), "up": _med([x["step"][lv]["up"] for x in hit]),
                      "med_r6": _med([x["step"][lv]["r6"] for x in r6]),
                      "same_prev": sum(1 for x in hit if lv == "0" and x["step"].get("10") and x["step"]["10"]["date"] == x["step"][lv]["date"])})
    now = out[-1] if out and out[-1]["out"] == "진행 중" else None
    return {"episodes": out, "sig": summ, "stages": steps, "rule": rid,
            "now": now and {"in": now["in"], "len": now["len"], "bottom": now["bottom"],
                            "fake": [s["fake"] for s in now["sig"]]}}


def hist_for(key, nat):
    """bear_sig_bt.json → bear.json 시장 칸에 붙일 짧은 요약"""
    j = rj(SIG, {}) or {}
    m = next((x for x in j.get("markets", []) if x.get("key") == key), None)
    if not m:
        return None
    if m.get("rule") != RULE.get(key, "F") or "stages" not in m:   # 규칙이 바뀐 뒤 아직 다시 안 셈
        return None
    h = {"at": j.get("at"), "from": m.get("from"), "sig": m["sig"], "stages": m["stages"], "now": m.get("now"), "rule": m["rule"]}
    return h


def sig_line(h, k):
    """알림 본문용 한 줄 (신호 k 가 새로 켜진 날)"""
    try:
        s = h["sig"][k]
        if not s["on"]:
            return f"과거 하락장 {s['eps']}번: 바닥 뒤엔 한 번도 안 켜짐"
        t = f"과거 하락장 {s['eps']}번 중 {s['on']}번 켜짐 — 보통 바닥 {s['after']:.0f}거래일 뒤 · 바닥보다 {s['up']:+.0f}%"
        if s["fake_eps"]:
            t += f" · 켜졌다가 더 빠진 하락장 {s['fake_eps']}번"
        return t
    except Exception:
        return ""


REB_UP, REB_D, REB_MIN = 0.03, 20, 3   # 📨 11/10 A11/10-1 이번 하락장 반등 날 기록: +3% 넘게 오른 날 · 그 뒤 20거래일 · 3번 미만이면 앱이 안 띄움


def rebounds(cl, dates, i0, up=REB_UP, nd=REB_D):
    """이번 🐻 하락장(i0 = 시작 인덱스)부터 오늘까지 종가 +up 넘게 오른 날마다:
       그날까지 하락장 저점(종가)을 그 뒤 nd 거래일 안에 다시 깼나 → broke / held / open(아직 nd일 안 지남·안 깸)
       순수 함수 — 판정·규칙과 무관한 「기록」"""
    pts, n = [], len(cl)
    for i in range(max(i0, 1), n):
        r1 = cl[i] / cl[i - 1] - 1
        if r1 < up:
            continue
        lo = min(cl[i0:i + 1])
        after = cl[i + 1:i + 1 + nd]
        br = next((k + 1 for k, x in enumerate(after) if x < lo), None)
        if br is not None:
            out = "broke"
        elif len(after) >= nd:
            out = "held"
        else:
            out = "open"
        p = {"d": dates[i], "r1": round(r1 * 100, 1), "c": round(cl[i], 2), "lo": round(lo, 2), "out": out, "left": max(0, nd - len(after)) if out == "open" else 0}
        if br is not None:
            p["bd"] = br                                   # 며칠 만에 깼나
        if len(after) >= nd:
            p["r20"] = round((after[nd - 1] / cl[i] - 1) * 100, 1)   # 20거래일 뒤 종가 (그날 종가 대비)
        pts.append(p)
    cnt = {k: sum(p["out"] == k for p in pts) for k in ("broke", "held", "open")}
    return {"from": dates[i0], "up": round(up * 100), "nd": nd, "min": REB_MIN, "n": len(pts), **cnt,
            "last": pts[-1]["d"] if pts else None, "pts": pts,
            "note": "이번 하락장 안의 기록 · 규칙은 그대로 · 종가 기준 · 매수·매도 추천 아님"}


# ───────────────────────── 시세 ─────────────────────────
def complete(df, close_hm, tz):
    """장중(아직 안 끝난) 오늘 막대 버림"""
    now = dt.datetime.now(tz)
    if len(df) and df.index[-1].date() >= now.date() and (now.hour, now.minute) < close_hm:
        return df.iloc[:-1]
    return df


def load(start):
    import yfinance as yf
    syms = [m[1] for m in MKTS] + ["^VIX"]
    df = yf.download(syms, start=start, auto_adjust=False, progress=False, group_by="ticker", threads=True)
    out = {}
    for key, sym, _, nat, hm in MKTS + [("vix", "^VIX", "VIX", "us", (16, 15))]:
        try:
            s = df[sym]["Close"].dropna()
            s = complete(s, hm, KST if nat == "kr" else ET)
            out[key] = s
        except Exception as e:
            print("시세 실패", sym, e)
    return out


def foreign_flow():
    p = M / "history.csv"
    if not p.exists():
        return None
    rows = sorted((r for r in csv.DictReader(p.open(encoding="utf-8")) if r.get("foreign_kospi")), key=lambda r: r["date"])
    return [float(r["foreign_kospi"]) for r in rows][-10:] or None


def aligned_vix(s, vix):
    v = vix.reindex(s.index).ffill()
    return [None if x != x else float(x) for x in v.tolist()]


# ───────────────────────── 알림 ─────────────────────────
def notify(title, body, dry=False):
    print("알림" if not dry else "(시험)", title, "|", body)
    if dry:
        return True
    try:
        urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=json.dumps({
            "topic": "chkchp-ch-report", "title": title, "message": body,
            "click": APP + "#home~bear", "tags": ["bear"]}).encode(),
            headers={"Content-Type": "application/json"}), timeout=15).read()
        return True
    except Exception as e:
        print("알림 실패", e)
        return False


# ───────────────────────── 지금 판정 ─────────────────────────
def apply_analog(r, key, name):
    """🔁 11/12 사용자 「1번」 — 닮은 장 백테스트에서 고른 방식이 현금 몫을 정함 (src/analog_bt.py adopt · 하나 빼고 고르기 통과한 시장만 · 예전 규칙은 cash_old 로 남김)"""
    ap = next((x for x in (rj(ANALOG, {}) or {}).get("markets", []) if x.get("key") == key and x.get("ok")), None)
    if not ap:
        return r
    if True:
        stock, nx = ap["stock"], ap["next"]
        lv = {"a50": r.get("m50"), "a200": r.get("m200")}.get(ap["k"])
        if lv:   # 선 하나짜리는 방금 종가로 다시 봄 (닮은 장 계산은 하루 한 번)
            stock = 100 if r["close"] > lv else 0
            nx = f"{'50' if ap['k'] == 'a50' else '200'}일선({lv:,.0f}) " + ("아래로 내려가면 현금" if stock else "위로 올라오면 주식")
        if ap["k"] == "half200" and r.get("m200") and r["close"] > r["m200"]:
            stock, nx = 100, "그대로 보유"
        r["cash_old"] = r["cash"]; r["cash"] = 100 - stock
        r["analog"] = {**ap, "stock": stock, "cash": 100 - stock, "next": nx}
        r["best_on"] = False; r["clock_cash"] = False; r.pop("overlay_on", None)
        c2 = 0 if ap["k"] in ("half200", "third", "dca6", "dca12", "dip") else (max(0, r["cash"] - 33) if ap["k"] == "floor" and r["cash"] else 100 - r["cash"])
        r["ladder"] = [[r["cash"], "🔁 지금"], [c2, "다음: " + nx]] if c2 != r["cash"] else [[r["cash"], "🔁 지금 · " + nx]]
        r["rule"]["old"] = r["rule"]["name"]; r["rule"]["name"] = "🔁 닮은 장 규칙 — " + ap["rule"]
        r["advice"] = (f"{name} 🔁 닮은 장 규칙 — {ap['rule']} · 지금 주식 {stock}% · {r.get('to', '현금')} {r['cash']}% · 다음: {nx}"
                       + (f" (예전 규칙이면 {r.get('to', '현금')} {r['cash_old']}%)" if r["cash_old"] is not None and r["cash_old"] != r["cash"] else ""))
    return r


# 🌏 11/12 사용자 「ㅇㅇ」 — 일본·중국·홍콩도 판정·닮은 장 규칙·알림 (앱 다른 칸이 안 깨지게 markets 가 아니라 more 에 따로)
MORE = [("nikkei", "^N225", "닛케이225", "jp", (15, 45)), ("shanghai", "000001.SS", "상해종합", "cn", (16, 15)), ("shenzhen", "399001.SZ", "심천성분", "cn", (16, 15)),
        ("hsi", "^HSI", "항셍", "hk", (17, 15)), ("hscei", "^HSCE", "항셍 H주", "hk", (17, 15))]   # 장 마감 = 한국 시각


def more_markets(old, dry=False, px=None):
    import pandas as pd
    oldm = {m["key"]: m for m in old.get("more", [])}
    sent = old.get("sent") or {}
    out = []
    for key, sym, name, nat, hm in MORE:
        try:
            if px is not None:
                s = px[sym].dropna()
            else:
                import yfinance as yf
                s = yf.download(sym, start=(dt.date.today() - dt.timedelta(days=800)).isoformat(), auto_adjust=False, progress=False)["Close"]
                s = (s.iloc[:, 0] if hasattr(s, "columns") else s).dropna()
                s = complete(s, hm, KST)
            s = s[s > 0].iloc[-520:]
            cl = [float(x) for x in s.tolist()]
            pb = False
            for i in range(max(0, len(cl) - 252), len(cl) - 1):
                pb = judge(cl, None, None, "us", pb, i)["state"] == "🐻"
            j = judge(cl, None, None, "us", pb)
            r = {k: j.get(k) for k in ("state", "dd", "hi", "close", "m50", "m200")}
            r.update({"key": key, "name": name, "nat": nat, "asof": str(s.index[-1].date()), "cash": None, "rule": {"id": "REF", "name": "판정만"}, "ladder": []})
            apply_analog(r, key, name)
            if not r.get("analog"):
                r["advice"] = f"{name} {r['state']} 고점보다 {r['dd']:+.1f}% — 닮은 장에서 통하는 방식이 없었음 · 한 번에 사지 말고 나눠 사기만 참고"
            r = {k: r.get(k) for k in ("key", "name", "nat", "asof", "state", "dd", "close", "m50", "m200", "cash", "advice", "analog")}
            o = oldm.get(key)
            r["since"] = o.get("since", r["asof"]) if o and o.get("state") == r["state"] else r["asof"]
            k = f"{key}:{r['asof']}:{r['state']}:{r['cash']}"
            if o and (o.get("state") != r["state"] or o.get("cash") != r["cash"]) and sent.get(key) != k:
                t = f"{r['state']} {name} — " + (f"주식 {100 - o['cash']}% → {100 - r['cash']}%" if o.get("cash") is not None and r["cash"] is not None else f"{o.get('state')} → {r['state']}")
                if notify(t, r["advice"] + f"\n고점보다 {r['dd']:+.1f}%", dry):
                    sent[key] = k
            out.append(r)
        except Exception as e:
            print("🌏 실패", key, e)
            if key in oldm:
                out.append(oldm[key])
    return out, sent


def live(dry=False):
    start = (dt.date.today() - dt.timedelta(days=800)).isoformat()
    px = load(start)
    vix = px.get("vix")
    ff = foreign_flow()
    old = rj(OUT, {}) or {}
    oldm = {m["key"]: m for m in old.get("markets", [])}
    mk, changed = [], []
    for key, _, name, nat, _ in MKTS:
        s = px.get(key)
        if s is None or len(s) < 60:
            continue
        cl = [float(x) for x in s.tolist()]
        vx = aligned_vix(s, vix) if vix is not None else None
        # 🐻 유지 판정: 지난 1년을 차례로 훑어 상태를 이어 감
        pb, b0 = False, None
        for i in range(max(0, len(cl) - 252), len(cl) - 1):
            nb = judge(cl, vx, None, nat, pb, i)["state"] == "🐻"
            if nb and not pb:
                b0 = i
            pb = nb
        r = judge(cl, vx, ff if key == "kospi" else None, nat, pb)
        if r["state"] != "🐻":
            b0 = None
        elif b0 is None or not pb:   # 오늘 막 🐻 이 됐거나 1년 내내 🐻 (앞 끝)
            b0 = len(cl) - 1 if not pb else max(0, len(cl) - 252)
        apply_rule(r, key)
        if RULE.get(key) == "B50":
            inn, i0, seen, nb = b50_walk(cl, vx)
            r["cash"] = 50 if inn else 0
            r["to"] = "채권형"
            r["b50"] = {"on": inn, "since": str(s.index[i0].date()) if inn and i0 is not None else None, "seen": seen, "nb": nb}
        bb_ = ((rj(PROXY, {}) or {}).get("best") or {}).get(key)
        if key in BEST and bb_:
            r["best"] = bb_
            if bb_.get("on") and r["cash"] < BEST[key][0]:
                r["cash"] = BEST[key][0]
                r["best_on"] = True
                r["best_why"] = BEST[key][1]
                r["ladder"] = [[BEST[key][0], BEST[key][1] + " 켜짐"], [0, "신저가 뒤 바닥 신호 " + ("①④" if bb_.get("exit") == "floor14" else "3개") + " · 또는 신저가 없이 신호 꺼짐"]]
        ov = ((rj(OVERLAY, {}) or {}).get("markets") or {}).get(key) or {}
        if ov.get("pick", "base") != "base":
            r["overlay"] = {"name": ov.get("name"), "parts": ov.get("parts"), "full": ov.get("full"), "base_full": ov.get("base_full")}
            for pt in ov.get("parts") or []:
                if not pt.get("on"):
                    continue
                if pt.get("side") == "W":
                    fr = int(round(float(pt.get("arg") or 0) * 100))
                    if r["cash"] < fr:
                        r["cash"] = fr; r["overlay_on"] = pt["name"]
                        r["ladder"] = [[fr, "🧩 " + pt["name"]], [0, "그 신호가 꺼지면"]]
        if key in CLOCK_ON:
            bp = rj(PROXY, {}) or {}
            r["clock"] = {k_: bp.get(k_) for k_ in ("h", "h_kr", "kospi_on", "since", "kospi_below200", "asof_us")}
            if bp.get("kospi_on") and r["cash"] < 100:
                r["cash"] = 100
                r["clock_cash"] = True
                r["ladder"] = [[100, "🕰 신용 경보(기계 신용 칸 다 울음) + 200일선 아래"], [0, "신용 칸이 조용해짐 · 또는 200일선 위로"]]
            r["rule"]["name"] += " · 🕰 신용 경보(기계 신용 칸 다 울음) + 200일선 아래여도 전부 현금"
        # 🌱 바닥 얹기(현금 풀기)는 모든 현금 규칙 뒤에 — 11/12 사용자 「수익을 선택」: 코스피 「5년 평균선보다 많이 아래면 현금 풀고 주식」 (낙폭 기준 넘어도 채택)
        for pt in (ov.get("parts") or []) if ov.get("pick", "base") != "base" else []:
            if pt.get("side") == "B" and pt.get("on") and r["cash"] > 0:
                r["cash"] = 0 if pt.get("arg") == "0" else min(r["cash"], 50); r["overlay_on"] = pt["name"]; r["best_on"] = False; r["clock_cash"] = False
                r["ladder"] = [[r["cash"], "🧩 " + pt["name"] + " — 현금 풀기"], [100, "그 신호가 꺼지고 하락장·경보면 다시 현금"]]
        r.update({"key": key, "name": name, "nat": nat, "asof": str(s.index[-1].date()), "advice": advice(name, r)})
        apply_analog(r, key, name)
        if b0 is not None:   # 📨 11/10 A11/10-1 이번 하락장 반등 날 기록 (하락장일 때만)
            try:
                r["rebounds"] = rebounds(cl, [str(x.date()) for x in s.index], b0)
            except Exception as e:
                print("반등 기록 실패", key, e)
        hh = hist_for(key, nat)
        if hh:
            r["hist"] = hh
        o = oldm.get(key)
        if o and r["state"] != "🟢":   # 🌱 새로 켜진 바닥 신호 (알림 본문 한 줄 · 앱 「🟢 켜짐」)
            oc = [bool(c.get("on")) for c in (o.get("checks") or [])]
            r["fresh"] = [k for k, c in enumerate(r["checks"]) if c["on"] and c.get("use") and k < len(oc) and not oc[k]]
        if o and (o.get("state") != r["state"] or o.get("cash") != r["cash"]):
            changed.append((o, r))
        r["since"] = o.get("since", r["asof"]) if o and o.get("state") == r["state"] else r["asof"]
        mk.append(r)
    if not mk:
        print("판정할 시세 없음")
        return 1
    worst = max(mk, key=lambda r: (r["cash"], -r["dd"]))
    head = " · ".join(f"{r['state']} {r['name']} {r['dd']:+.0f}%" for r in mk)
    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "head": head, "lead": worst["advice"],
           "markets": mk, "rules": RULES,
           "note": "종가 기준 기계 판정 · 결과 보기 전 등록한 규칙(src/bear_gate.py) · 매수·매도 추천 아님 — 고객 성향·기간에 맞춰 판단"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log = rj(LOG, []) or []
    for o, r in changed:
        log.append({"date": r["asof"], "key": r["key"], "from": f"{o.get('state')} 현금 {o.get('cash')}%",
                    "to": f"{r['state']} 현금 {r['cash']}%", "n": r["n"], "close": r["close"], "dd": r["dd"]})
    first = not old
    if changed or first:
        LOG.write_text(json.dumps(log[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
    sent = old.get("sent") or {}
    for o, r in changed:
        k = f"{r['key']}:{r['asof']}:{r['state']}:{r['cash']}"
        if sent.get(r["key"]) == k:
            continue
        t = f"{r['state']} {r['name']} — {r.get('to', '현금')} {o.get('cash')}% → {r['cash']}%"
        body = r["advice"] + f"\n낙폭 {r['dd']:+.1f}% · 바닥 신호 {r['n']}/4"
        for k in (r.get("fresh") or []):
            ln = sig_line(r.get("hist") or {}, k)
            if ln:
                body += f"\n🌱 {r['checks'][k]['k']} 켜짐 — {ln}"
        body += "\n다시 사는 규칙: " + r["rule"]["name"]
        if notify(t, body, dry):
            sent[r["key"]] = k
    # 🌱 11/11 한국 바닥 신호 알림 — 코스피·코스닥이 🟡·🐻 일 때 바닥 신호가 새로 켜지면 (비중 규칙과 따로 · 하루 한 번)
    for r in mk:
        if r["nat"] != "kr" or r["state"] == "🟢":
            continue
        o = oldm.get(r["key"]) or {}
        oc = [bool(c.get("on")) for c in (o.get("checks") or [])]
        new = [k for k, c in enumerate(r["checks"]) if c["on"] and (k >= len(oc) or not oc[k])] if oc else []
        if not new:
            continue
        nb = sum(1 for c in r["checks"] if c["on"])
        fk = f"{r['asof']}:" + "".join("1" if c["on"] else "0" for c in r["checks"])
        if sent.get(r["key"] + "_floor") == fk:
            continue
        t = f"🌱 {r['name']} 바닥 신호 {nb}/4 — " + " · ".join(r["checks"][k]["k"] for k in new) + " 켜짐"
        body = (f"{r['state']} 낙폭 {r['dd']:+.1f}% · " + " / ".join(("🟢 " if c["on"] else "⚪ ") + c["k"] for c in r["checks"]) +
                "\n지금 규칙: " + r["rule"]["name"] + "\n참고(kr_floor_bt): 2013년 뒤 바닥 신호에 전부 담으면 연 −2.5%p · 첫발 10%만 담으면 연 −0.2%p 안팎(18판 모두 판정 풀림까지 기다리기보다 조금 못함) — 담더라도 10%만 · 매수 추천 아님")
        if notify(t, body, dry):
            sent[r["key"] + "_floor"] = fk
    if first:   # 처음 켠 날: 지금 상태를 한 번 알림 (🟢 아닌 시장만)
        bad = [r for r in mk if r["state"] != "🟢"]
        if bad and notify("🐻 하락장 계기판 시작 — " + " · ".join(f"{r['state']}{r['name']}" for r in bad),
                          "\n".join(r["advice"] for r in bad), dry):
            for r in bad:
                sent[r["key"]] = f"{r['key']}:{r['asof']}:{r['state']}:{r['cash']}"
    out["sent"] = sent
    try:
        out["more"], out["sent"] = more_markets({"more": old.get("more", []), "sent": sent}, dry)
    except Exception as e:
        print("🌏 more 실패", e); out["more"] = old.get("more", [])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("head", "lead")}, ensure_ascii=False))
    return 0


# ───────────────────────── 과거 검증 ─────────────────────────
def backtest():
    """2000년부터: 매일 종가로 판정 → 다음 날 주식 비중 = 1 − 현금% (현금은 연 2% 가정, 사고팔 때 0.1%)
       vs 그냥 들고 있기. 🇰🇷 ④는 과거 외국인 자료가 없어 50일선으로 대신함."""
    px = load("1999-01-01")
    vix = px.get("vix")
    res = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "rules": RULES,
           "note": "과거 검증 · 시장별 다시 사기 규칙(🇰🇷 E 추세 확인 · 🇺🇸 F 판정만) · ④ 50일선 · 현금 연 2% · 비중 바꿀 때 0.1% · 배당 제외(가격지수)", "markets": []}
    sigs = []
    for key, _, name, nat, _ in MKTS:
        s = px.get(key)
        if s is None or len(s) < 400:
            continue
        cl = [float(x) for x in s.tolist()]
        vx = aligned_vix(s, vix)
        dates = [str(d.date()) for d in s.index]
        pb, w_prev = False, 1.0
        nav, bh, peak_n, peak_b, mdd_n, mdd_b = 1.0, 1.0, 1.0, 1.0, 0.0, 0.0
        days_bear, switches, eps = 0, 0, []
        cur = None
        for i in range(252, len(cl)):
            r1 = cl[i] / cl[i - 1] - 1
            nav *= 1 + w_prev * r1 + (1 - w_prev) * 0.02 / 252
            bh *= 1 + r1
            peak_n, peak_b = max(peak_n, nav), max(peak_b, bh)
            mdd_n, mdd_b = min(mdd_n, nav / peak_n - 1), min(mdd_b, bh / peak_b - 1)
            j = judge(cl, vx, None, "us", pb, i)
            pb = j["state"] == "🐻"
            days_bear += pb
            w = 1 - rule_cash(RULE.get(key, "F"), j["state"], [bool(c["on"]) for c in j["checks"]]) / 100
            if abs(w - w_prev) > 1e-9:
                nav *= 1 - 0.001 * abs(w - w_prev)
                switches += 1
            if j["state"] == "🐻" and cur is None:
                cur = {"in": dates[i], "dd_in": j["dd"], "nav0": nav, "bh0": bh}
            if j["state"] != "🐻" and cur is not None:
                cur.update({"out": dates[i], "rule": round((nav / cur.pop("nav0") - 1) * 100, 1),
                            "hold": round((bh / cur.pop("bh0") - 1) * 100, 1)})
                eps.append(cur)
                cur = None
            w_prev = w
        try:
            sh = sig_history(cl, vx, dates, rid=RULE.get(key, "F"))
            sh.update({"key": key, "name": name, "from": dates[252], "to": dates[-1]})
            sigs.append(sh)
        except Exception as e:
            print("신호 성적 실패", key, e)
        yrs = (len(cl) - 252) / 252
        if cur is not None:
            cur.update({"out": "진행 중", "rule": round((nav / cur.pop("nav0") - 1) * 100, 1),
                        "hold": round((bh / cur.pop("bh0") - 1) * 100, 1)})
            eps.append(cur)
        res["markets"].append({
            "key": key, "name": name, "from": dates[252], "to": dates[-1],
            "rule": {"cagr": round((nav ** (1 / yrs) - 1) * 100, 2), "mdd": round(mdd_n * 100, 1)},
            "hold": {"cagr": round((bh ** (1 / yrs) - 1) * 100, 2), "mdd": round(mdd_b * 100, 1)},
            "bear_days_pct": round(days_bear / (len(cl) - 252) * 100, 1), "switches_per_year": round(switches / yrs, 1),
            "episodes": eps[-12:]})
    BT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if sigs:
        SIG.write_text(json.dumps({"at": res["at"], "rules": RULES,
                                   "note": "과거 🐻 하락장마다 바닥 신호가 언제 켜졌나 · 가짜 = 켜진 뒤 그 하락장 바닥이 더 낮게 나옴 · "
                                           "진짜 = 바닥 뒤 처음 켜진 날 · 6개월 = 126거래일 · 🇰🇷 ④는 외국인 대신 50일선 · 가격지수 · 표본이 적어 「n번 중 m번」으로만 읽기",
                                   "markets": sigs}, ensure_ascii=False, indent=1), encoding="utf-8")
        for m in sigs:
            print(m["name"], "신호 성적", json.dumps(m["step"], ensure_ascii=False))
    for m in res["markets"]:
        print(m["name"], "규칙", m["rule"], "보유", m["hold"])
    return 0


if __name__ == "__main__":
    if "--bt" in sys.argv:
        sys.exit(backtest())
    sys.exit(live(dry="--dry" in sys.argv))
