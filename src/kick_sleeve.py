"""⚡ 킥 슬리브 — 포트의 15%를 「우리 스캐너가 확인한 순간」에만 넣는 공격 칸 (10/9 사용자: "10~20%는 시장을 이기는 베팅·킥이 필요하지 않을까")
  비교: 💼 기본 포트(리포트 배분표 그대로) vs ⚡ 킥 포트(기본에서 현금 15%p 를 킥 슬리브로)

  근거(8/30~ 장부): 컵 후보 전체는 평균 −2.2%(31% 이김)지만 기준가를 실제로 뚫은 컵은 평균 +7.0%(71%), 돌파 갭 5일 +1.7%(62%).
  → 후보가 아니라 「확인된 순간」에만 들어간다.

  규칙
  · 자리 5개, 한 자리 = 슬리브의 20% (10/10부터 돌파 9% → 포트의 1.8%). 빈 자리는 현금(SGOV).
  · 들어가는 신호 (우선순위): ① 🎯 집중 ★종목 기준가 돌파(장중 알림)  ② 눈 검사 통과 컵의 기준가 돌파  ③ 그 밖의 컵 돌파  ④ 돌파 갭(메우지 않음)
    점수 + 고래 TOP10 겹치면 +10. 하루 새로 들어가는 건 최대 2개, 같은 종목 중복 없음, 판 지 10거래일 안 된 종목 재진입 없음.
  · 들어가는 값: 신호가 뜬 날 종가.
  · 나가는 규칙: 들어간 값 −5% 종가 → 손절 / +15% → 절반 정리, 나머지는 20일선 아래 종가에 정리 / 15거래일 지나도 최고 +3% 못 넘으면 정리(시간 손절).
  · 브레이크: 슬리브가 시작 대비 −6% 아래면 10거래일 새 진입 멈춤.
  · 수익률은 각 종목 현지 통화 기준(환율 제외), 수수료·세금 제외.
  → market/kick.json (앱 💼 포트 탭 「기본 vs 킥」 비교) · 새로 사고판 날 ntfy chkchp-ch-kick 알림

  🐋 고래 바스켓 (10/10 사용자: "S&P500 을 이기는 게 쉽지 않은데 고래는 이기잖아. 킥에 고래도 좀 반영")
  · 근거(whale40 13F 큰 신규 포지션 2025Q2~2026Q2, 160종목 vs S&P): 하나씩은 반반(중앙 초과 ≈ 0)이지만 같은 비중 바스켓은
    바이오 전문 펀드를 빼면 매 분기 S&P 를 이김 — 1개월 5/5 분기(+2.8%p) · 3개월 4/4(+3.9%p) · 6개월 3/3(+10.0%p). 바이오 펀드 것은 6개월 −16.7%p.
    → 이기는 힘은 「몇 개의 큰 승자」에서 나온다. 그래서 돌파 칸의 −5% 손절·15일 시간 손절을 쓰지 않는다(큰 승자를 잘라 버림).
  · 규칙: 최신 13F 분기(분기 끝 +46일 = 공시 마감 뒤)의 큰 신규 포지션 중 바이오 전문 펀드만 산 것·ETF·미국 밖 티커를 빼고,
    여러 고래가 산 것 → 포트 비중 큰 것 순으로 최대 10종목을 같은 비중으로 사서 다음 분기 목록이 나올 때까지 들고 간다.
    한 종목이 −30% 면 그것만 현금으로(사고 대비). 킥 15% = ⚡ 돌파 9% + 🐋 고래 6% (kick_params 의 sleeve·whale_sleeve).
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
PORT = ROOT / "market" / "port.json"
CANDS = ROOT / "market" / "kick_cands.json"
OUT = ROOT / "market" / "kick.json"
RAW = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/"
PARAMS = ROOT / "market" / "kick_params.json"      # 엣지 연구(주간)가 고치는 손잡이
_DEF = {"sleeve": 0.15, "slots": 5, "stop": -0.05, "take": 0.15, "time_d": 15, "time_min": 0.03, "brake": -0.06, "brake_d": 10, "max_new": 2, "reentry": 10,
        "pri": {"focus": 40, "cup_eye": 25, "lead": 20, "cup": 10, "accum": 10, "whale": 8, "gap": 0}, "whale_bonus": 10, "off": [],
        "lead_min": 1.5, "lead_cor": 0.3, "adaptive": True,
        "gap_fill_exit": True, "cup_min_handle": 0, "cup_min_rs": 0, "cup_mkts": [], "gap_min": 0, "gap_max": 100, "gap_max_vol": 1000,
        "whale_sleeve": 0.0, "whale_n": 10, "whale_stop": -0.30}
try:
    _P = {**_DEF, **json.loads(PARAMS.read_text(encoding="utf-8"))}
except Exception:
    _P = dict(_DEF)
SLEEVE, SLOTS = _P["sleeve"], _P["slots"]
WS, WN, WSTOP = _P["whale_sleeve"], _P["whale_n"], _P["whale_stop"]
WHALE_RAW = "https://raw.githubusercontent.com/chkchp0702-spec/whale40/main/data/signals.json"
BIO = {"EcoR1 Capital", "Baker Bros. Advisors", "BVF", "Perceptive Advisors", "Deep Track Capital", "Avoro Capital Advisors", "Vivo Capital",
       "OrbiMed Advisors", "RA Capital Management", "Cormorant Asset Management", "Rock Springs Capital", "Commodore Capital", "Logos Global Management",
       "Great Point Partners", "Venrock Healthcare Capital Partners", "Janus Henderson Biotech", "Boxer Capital", "Farallon Biotech"}
NOT_STOCK = {"SPY", "QQQ", "IWM", "DIA", "VOO", "IVV", "RSP", "XLF", "XLP", "XLI", "XLE", "XLK", "XLV", "XLU", "XLY", "XLB", "XLC", "XLRE", "IGV", "SMH",
             "SOXX", "GDX", "GDXJ", "GLD", "SLV", "TLT", "IEF", "HYG", "LQD", "EWZ", "EWJ", "EWY", "FXI", "KWEB", "EEM", "EFA", "VEA", "VWO", "ARKK", "XBI",
             "IBB", "SPUU", "TQQQ", "SQQQ", "UVXY", "VXX", "NONE", "IHI", "ITA", "KRE", "KBE", "KBWB", "XME", "XHB", "XRT", "XOP", "IYR", "VNQ",
             "SCHD", "JEPI", "JEPQ", "BITO", "IBIT", "FBTC", "ETHA", "URA", "COPX", "SIL", "SILJ", "USO", "UNG", "DBC", "IAU", "SGOV", "BIL", "SHY",
             "MDY", "IJH", "IJR", "VTI", "VUG", "VTV", "QQQM", "SPLG", "TNA", "TZA", "LABU", "SOXL", "SPXL", "UPRO", "TMF", "GDXU", "ARKG", "ARKW",
             "CIBR", "HACK", "BOTZ", "AIQ", "ICLN", "TAN", "LIT", "NLR", "PAVE", "IGM", "VGT", "FDN", "SKYY", "CLOU", "MCHI", "INDA", "EWT", "EWG"}
QEND = {"Q1": "-03-31", "Q2": "-06-30", "Q3": "-09-30", "Q4": "-12-31"}


def whale_lists():
    """분기 → (목록 공개일, [종목]) — whale40 의 13F 큰 신규 포지션"""
    try:
        with urllib.request.urlopen(urllib.request.Request(WHALE_RAW, headers={"User-Agent": "ch-kick"}), timeout=40) as r:
            sig = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("고래 목록 실패", e)
        return []
    out = []
    for q, d in sig.items():
        try:
            qq, yy = q.split()
            avail = (dt.date.fromisoformat(yy + QEND[qq]) + dt.timedelta(days=46)).isoformat()
        except Exception:
            continue
        rows = []
        for t, v in d.items():
            if t in NOT_STOCK or "." in t or not t.isalpha():
                continue
            by = v.get("by") or []
            if by and all(b in BIO for b in by):
                continue                      # 바이오 전문 펀드만 산 것은 뺀다 (6개월 −16.7%p)
            if max(v.get("w") or [0]) >= 50:
                continue                      # 한 종목 몰빵 공시(특수 상황)
            rows.append({"t": t, "n": v.get("n", 1), "w": round(max(v.get("w") or [0]), 2), "by": by[:3]})
        rows.sort(key=lambda x: (-x["n"], -x["w"]))
        out.append((avail, q, rows))
    return sorted(out)
STOP, TAKE, TIME_D, TIME_MIN = _P["stop"], _P["take"], _P["time_d"], _P["time_min"]
BRAKE, BRAKE_D, MAX_NEW, REENTRY = _P["brake"], _P["brake_d"], _P["max_new"], _P["reentry"]
PRI = {**_DEF["pri"], **_P.get("pri", {})}
OFF = set(_P.get("off", []))
# 10/19 사용자 「맞는 쪽에 더 싣고 지는 쪽은 줄여 — 현시간부로」: 날짜부터만(소급 없음) 끄는 신호 · 칸 크기 바꾸기
OFF_FROM = _P.get("off_from", {}) or {}
MIX = _P.get("mix") or {}
MIX_FROM = MIX.get("from", "9999")
def sl_at(d):   # 그날의 돌파 칸 크기
    return MIX.get("sleeve", SLEEVE) if d >= MIX_FROM else SLEEVE
def w2_at(d, base):   # 그날의 고래 칸 크기(규칙 켠 뒤)
    return MIX.get("whale", base) if d >= MIX_FROM else base
SRC_NAME = {"nh52": "🏔 신고가", "pead": "📊 실적 표류", "dip": "🩹 급락 반등", "trend": "🧭 추세", "earn": "📊 실적 갭", "focus": "🎯 집중 돌파", "cup_eye": "☕ 컵 돌파(눈 검사 통과)", "cup": "☕ 컵 돌파", "gap": "📈 돌파 갭",
            "lead": "🔗 미국→한국 선행", "accum": "🤫 매집 박스 돌파", "whale": "🐋 고래 큰손 매수",
            "cust": "🔌 고객사 따라", "ins": "🕵 내부자 매수", "maxcut": "🎰 복권 거름망에 걸린 것", "frog": "🐸 튀어 오른 갭(개구리 거름망에 걸린 것)",
            "agree": "🤝 신호 합의(다른 신호 2개 이상)", "nonews": "📰 뉴스 없는 갭(실적·공시 없이 뜬 미국 돌파 갭)",
            "pbskip": "🪂 눌림 안 온 갭(Q15-5 로 건너뛴 미국 돌파 갭)", "krgap": "🇰🇷 한국 돌파 갭(Q16-1 로 킥에서 뺀 것)"}


# ✅ 성과가 확인된 신호만 킥에 들어온다 (10/10 사용자: "고래·컵·갭·조용한 매집이 성과 확인된 것만 자연스럽게, 킥 포트는 하나만")
#    기준: 우리 장부(market/edge.json)에서 표본 20건 이상 · 손익비 1.5 이상. 고래는 13F 바스켓 검증(매 분기 S&P 이김).
#    아직 아닌 신호는 「⏳ 대기」— 표본이 차면 다음 계산부터 저절로 들어온다. 🎯 집중·🔗 선행은 사용자 목록 밖이라 넣지 않는다.
TAG = {"cup_eye": "☕", "cup": "☕", "gap": "📈", "accum": "🤫", "whale": "🐋", "focus": "🎯", "lead": "🔗", "earn": "📊",
       "nh52": "🏔", "pead": "📊", "dip": "🩹", "trend": "🧭", "cust": "🔌", "ins": "🕵", "maxcut": "🎰", "frog": "🐸", "agree": "🤝", "nonews": "📰", "pbskip": "🪂", "krgap": "🇰🇷"}
KICK_SRCS = ["cup_eye", "cup", "gap", "accum", "whale", "earn", "nh52", "pead", "dip", "cust", "ins"]   # 📊 실적 갭(10/11): 우리 장부 5일 평균 −0.4%(53건)라 그림자 채점으로 먼저 확인
PROOF_N, PROOF_PF = 20, 1.5

# 🧪 10/12 새 아이디어 4개 (src/kick_ideas_bt.py 과거 검증 → market/kick_ideas_bt.json · 매일 신호 market/kick_ideas_live.json)
#   ✅ 채택 = 정식 · 🧪 시험 = 절반 크기 · 👻 그림자만 / ❌ 기각 = 그림자 채점만 (10년 넘는 과거 검증에서 진 신호라 장부 20건으로 저절로 들어오지 않음 — 다시 켜려면 새 검증 통과)
IDEAS = ("nh52", "pead", "dip", "trend", "cust", "ins")


def _rj(path, d=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return d if d is not None else {}


IB = _rj(ROOT / "market" / "kick_ideas_bt.json").get("ideas", {})
IL = _rj(ROOT / "market" / "kick_ideas_live.json")
# 📈 Q16 (10/13 사용자: "16-2,3,5 진행하고 반영시켜") — 과거 검증 판정 market/q16_bt.json · 매일 신호 market/q16_live.json (src/q16_live.py)
#   🔌 cust 고객사→납품사 · 🕵 ins 내부자 기회형 매수 = 새 아이디어처럼 판정대로(✅ 정식 · 🧪 절반 · 👻/❌ 그림자만)
#   🎰 MAX 거름망 = ☕·📈 미국 후보의 직전 20일 하루 최대 상승률이 기준 이상이면 ✅ 일 때만 킥에서 빼고, 늘 「🎰 걸린 것」 그림자 채점
Q16B = _rj(ROOT / "market" / "q16_bt.json")
Q18B = _rj(ROOT / "market" / "q18_bt.json")   # 🐸 Q18-2 개구리 거름망 판정 (src/lab/k1013_q18.py)
Q10B = _rj(ROOT / "market" / "q10_bt.json")   # 🤝 Q10-2 신호 합의 판정 (src/lab/k1014_q10.py · 사용자 10/14 「2,3,5 실행」)
Q15B = _rj(ROOT / "market" / "q15_bt.json")   # 🎯 Q15-5 갭 눌림 진입 판정 (src/lab/k1014_q15g.py · 사용자 10/14 15시 「2,5번 실행」)
Q13B = _rj(ROOT / "market" / "q13_bt.json")   # 📰 Q13-1 뉴스 없는 갭 · 🧯 Q13-5 손절 뭉침 차단기 판정 (src/lab/k1014_q13.py · 사용자 10/14 「1,5번 진행」)
BK = Q13B.get("brake") or {}
Q16X = _rj(ROOT / "market" / "q16b_bt.json")  # 🇰🇷 Q16-1 한국 갭 문 닫기 · 🇨🇳 Q16-3 중국 신용 · 🌡 Q16-5 시장 폭 (src/lab/k1014_q16.py · 사용자 10/14 16시 「1,3,5 진행」)
BK_ON, BK_M, BK_P = BK.get("verdict") in ("✅", "🧪"), int(BK.get("M") or 2), int(BK.get("P") or 3)
QL = _rj(ROOT / "market" / "q16_live.json")
IB.update({k: Q16B[k] for k in ("cust", "ins") if isinstance(Q16B.get(k), dict) and Q16B[k].get("verdict")})
_EXM = {"f10": {"hold": 10}, "f20": {"hold": 20}, "f40": {"hold": 40}, "s8_20": {"stop": -0.08, "hold": 20},
        "s8t20_20": {"stop": -0.08, "take": 0.20, "hold": 20}, "s8_40": {"stop": -0.08, "hold": 40}}


def src_exit(src):
    """신호마다 다른 출구 — 없으면 None(킥 기본: −5% 손절 · +15% 절반 · 15일 시간 손절)"""
    ov = (_P.get("src_exit") or {}).get(src)
    if ov:
        return ov
    b = IB.get(src) or {}
    if src in ("nh52", "pead", "cust", "ins") and b.get("pick", {}).get("exit") in _EXM:
        return _EXM[b["pick"]["exit"]]
    if src == "dip" and b.get("pick"):
        try:
            ex, hd = b["pick"]["rule"].split("|")[2].split("/")
            return {"ma5": ex == "ma5", "hold": int(hd.rstrip("d"))}
        except Exception:
            return {"ma5": True, "hold": 5}
    return None


XR = {k: src_exit(k) for k in ("nh52", "pead", "dip", "cust", "ins")}


def xr_doc(x):
    if not x:
        return "−5% 손절 · +15% 절반"
    o = []
    if x.get("stop") is not None:
        o.append(f"손절 {x['stop'] * 100:.0f}%")
    if x.get("take") is not None:
        o.append(f"익절 +{x['take'] * 100:.0f}%")
    if x.get("ma5"):
        o.append("5일선 위 마감이면 팖")
    o.append(f"최대 {x['hold']}일")
    return " · ".join(o)
TRIAL_N = 10          # 🧪 시험 편입: 표본 10건↑·손익비 1.5↑ 이면 절반 크기로 먼저 (10/10 — 매집처럼 사용자가 원한 신호가 표본을 못 쌓는 문제)


def proof():
    """신호별 성과 확인 — {src: {n, pf, avg, on, why}}"""
    try:
        E = json.loads((ROOT / "market" / "edge.json").read_text(encoding="utf-8"))
    except Exception:
        E = {}
    g = lambda *ks: (lambda d: d if isinstance(d, dict) else {})(__import__("functools").reduce(lambda a, k: (a or {}).get(k) if isinstance(a, dict) else None, ks, E))
    # 10/10: 컵은 피벗 기준(brk_now)이면 돌파일 점프가 섞여 부풀려짐 → 돌파일 종가 기준·킥 필터 적용 성적(brk_real_kick)
    st = {"cup": g("cup", "brk_real_kick") or g("cup", "brk_now"), "gap": g("gap", "돌파_by_size", "4-8%"), "accum": g("accum", "brk")}
    hon = {"cup": g("cup", "honest"), "gap": g("gap", "honest"), "accum": g("accum", "honest")}   # 🧾 정직(다음 날 진입·비용·뒤 절반) — 판정에는 안 씀, 옆에 보여 주기만
    wide = {"accum": g("accum", "all")}          # 돌파만으로 표본이 적으면 신호 전체 성적으로 시험 편입 판단
    out = {}
    for k, v in st.items():
        n, pf = v.get("n") or 0, v.get("pf") or 0
        on = n >= PROOF_N and pf >= PROOF_PF
        tri = False
        if not on and k in wide:
            w_ = wide[k]; wn, wpf = w_.get("n") or 0, w_.get("pf") or 0
            tri = wn >= TRIAL_N and wpf >= PROOF_PF
        out[k] = {"n": n, "pf": round(pf, 2) if pf < 100 else None, "avg": v.get("avg"), "on": on or tri, "trial": tri,
                  "why": (f"확인됨 — {n}건 · 평균 {v.get('avg'):+.1f}% · 손익비 {pf:.1f}" if on else
                          (f"🧪 시험 편입(절반 크기) — 신호 전체 {wide[k].get('n')}건 · 평균 {wide[k].get('avg'):+.1f}% · 손익비 {wide[k].get('pf'):.1f}, 돌파 표본 {n}/{PROOF_N}건 차면 정식" if tri else
                           f"⏳ 대기 — 돌파 표본 {n}/{PROOF_N}건" + (f" · 손익비 {pf:.1f}" if n and pf < 100 else "")))}
    for k in IDEAS:          # 🧪 10/12 새 아이디어 — 과거 검증 판정으로 켜고 끔
        b = IB.get(k) or {}
        vd = b.get("verdict")
        if not vd:
            continue
        o_ = b.get("OOS") or {}
        xo = o_.get("x") if isinstance(o_.get("x"), dict) else {}
        out[k] = {"n": xo.get("n") or o_.get("n") or (o_.get("trades") or {}).get("n") or 0, "pf": (o_.get("r") or {}).get("pf") or o_.get("pf") or (o_.get("trades") or {}).get("pf"),
                  "avg": xo.get("avg") if xo else o_.get("avg"), "on": vd in ("✅", "🧪"), "trial": vd == "🧪", "bt": vd, "no_promote": vd in ("👻", "❌"),
                  "why": {"✅": "✅ 채택 — ", "🧪": "🧪 시험 편입(절반 크기) — ", "👻": "👻 그림자만 — ", "❌": "❌ 기각(그림자 채점만) — "}[vd] + "과거 검증 " + (b.get("why") or ""),
                  "rule": (b.get("pick") or {}).get("rule"), "exit": xr_doc(XR.get(k)) if k != "trend" else "N일 고가 돌파 → 사고 · M일 저가 이탈 → 팖"}
    try:   # 👻 그림자 채점이 표본 20↑·손익비 1.5↑면 그 신호도 확인된 것으로 (장부 표본이 부족한 매집 등)
        SS = json.loads((ROOT / "market" / "kick.json").read_text(encoding="utf-8")).get("shadow_stat", {})
        for k, v in SS.items():
            if k in out and out[k].get("no_promote"):
                continue
            if k in out and (not out[k]["on"] or out[k].get("trial")) and (v.get("n") or 0) >= PROOF_N and (v.get("pf") or 0) >= PROOF_PF:
                out[k].update({"on": True, "trial": False, "why": f"확인됨(그림자 채점) — {v['n']}건 · 평균 {v['avg']:+.1f}% · 손익비 {v['pf']:.1f}"})
            elif k in out and not out[k]["on"] and k in KICK_SRCS and (v.get("n") or 0) >= TRIAL_N and (v.get("pf") or 0) >= PROOF_PF:
                out[k].update({"on": True, "trial": True, "why": f"🧪 시험 편입(그림자 채점) — {v['n']}건 · 평균 {v['avg']:+.1f}% · 손익비 {v['pf']:.1f}"})
    except Exception:
        pass
    for k, h in hon.items():
        if k in out:
            o_ = h.get("oos") or {}
            out[k]["honest"] = {"n": h.get("n") or 0, "avg": h.get("avg"), "pf": h.get("pf"), "win": h.get("win"), "basis": h.get("basis"),
                                "insample": h.get("insample"), "oos": {"n": o_.get("n"), "avg": o_.get("avg"), "pf": o_.get("pf")} if o_ else None}
    out["cup_eye"] = out["cup"]
    if "earn" not in out or not out["earn"].get("on"):
        sse = {}
        try:
            sse = json.loads((ROOT / "market" / "kick.json").read_text(encoding="utf-8")).get("shadow_stat", {}).get("earn", {})
        except Exception:
            pass
        out["earn"] = {"n": sse.get("n") or 0, "pf": sse.get("pf"), "avg": sse.get("avg"), "on": False, "trial": False,
                       "why": f"⏳ 그림자 채점 중 — 실적 발표가 만든 갭 {sse.get('n') or 0}/{PROOF_N}건 (10건·손익비 1.5↑면 절반 크기 시험, 20건이면 정식)"}
        n_, pf_ = sse.get("n") or 0, sse.get("pf") or 0
        if n_ >= PROOF_N and pf_ >= PROOF_PF:
            out["earn"].update({"on": True, "why": f"확인됨(그림자 채점) — {n_}건 · 평균 {sse.get('avg'):+.1f}% · 손익비 {pf_:.1f}"})
        elif n_ >= TRIAL_N and pf_ >= PROOF_PF:
            out["earn"].update({"on": True, "trial": True, "why": f"🧪 시험 편입(그림자 채점) — {n_}건 · 평균 {sse.get('avg'):+.1f}% · 손익비 {pf_:.1f}"})
    out["whale"] = {"n": 160, "pf": None, "avg": None, "on": True, "why": "확인됨 — 13F 큰 신규 바스켓이 매 분기 S&P 이김(3개월 4/4 +3.9%p · 6개월 3/3 +10.0%p)",
                    "fixed": True, "why_note": "4분기 표본 · 코드에 고정된 판정"}
    for k in ("focus", "lead"):
        out[k] = {"n": 0, "on": False, "why": "킥 대상 아님(사용자 목록: 고래·컵·갭·매집)"}
    return out


def short(x):
    import re as _re
    return _re.sub(r",? (Inc\.?|Corp\.?|Corporation|Company|Ltd\.?|plc|CORP|N\.V\.|S\.A\.|ASA)\b.*$|( Common Stock| Ordinary Shares).*$", "", str(x or ""), flags=_re.I).strip()


def get_json(path):
    with urllib.request.urlopen(urllib.request.Request(RAW + path, headers={"User-Agent": "ch-kick"}), timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def collect(now):
    """새 신호를 후보 장부에 쌓는다 (앞으로는 성적 파일이 300개로 잘려도 장부에 남음)"""
    try:
        C = json.loads(CANDS.read_text(encoding="utf-8"))
    except Exception:
        C = {"cands": {}, "sent": []}
    cands = C["cands"]
    try:
        eye = set(get_json("archive/x/eye_cup.json").get("keep", []))
    except Exception:
        eye = set()
    whale = set()
    try:
        P = get_json("archive/x/perf_cup.json")
        for x in P.get("signals", []):
            if x.get("brk") and x.get("brkd"):
                if (x.get("f_handle") or 0) < _P["cup_min_handle"] or (x.get("f_rs") or 0) < _P["cup_min_rs"] or (_P["cup_mkts"] and x.get("mkt") not in _P["cup_mkts"]):
                    continue                                   # 엣지 연구 필터 (brain/edge.md)
                _bp, _bi = x.get("bpath") or [], x.get("bpi")
                if _bi is not None and _bi < len(_bp) and _bp[_bi] >= _P.get("cup_max_ext", 999):
                    continue                                   # 10/10: 돌파일 종가가 피벗 +12% 넘게 뜬 「늦은」 돌파는 산 뒤 평균 −0.6%·손익비 0.7
                k = f"{x['code']}|{x['brkd']}"
                if k not in cands:
                    src = "cup_eye" if x["code"] in eye else "cup"
                    cands[k] = {"code": x["code"], "name": x.get("name") or x["code"], "mkt": x.get("mkt"), "d": x["brkd"], "src": src,
                                "score": x.get("score") or 0, "lv": x.get("pivot")}
    except Exception as e:
        print("컵 실패", e)
    try:
        G = get_json("archive/x/perf_gap.json")
        seen = {v["code"] for v in cands.values() if v["src"] == "gap"}
        for x in sorted(G.get("signals", []), key=lambda x: x.get("d0", "")):
            if x.get("gtype") == "돌파 갭" and not x.get("filled") and x["code"] not in seen and _P["gap_min"] <= (x.get("gap") or 0) < _P["gap_max"] and (x.get("vol") or 0) < _P["gap_max_vol"]:
                seen.add(x["code"])
                cands[f"{x['code']}|{x['d0']}"] = {"code": x["code"], "name": x.get("name") or x["code"], "mkt": x.get("mkt"), "d": x["d0"],
                                                   "src": "gap", "score": x.get("score") or 0, "lv": x.get("fill_lvl")}
        for x in sorted(G.get("signals", []), key=lambda x: x.get("d0", "")):   # 📊 실적 갭 (메우지 않은 것)
            if x.get("gtype") == "실적 갭" and not x.get("filled") and f"{x['code']}|{x['d0']}|e" not in cands:
                cands[f"{x['code']}|{x['d0']}|e"] = {"code": x["code"], "name": x.get("name") or x["code"], "mkt": x.get("mkt"), "d": x["d0"],
                                                      "src": "earn", "score": x.get("score") or 0, "lv": x.get("fill_lvl")}
    except Exception as e:
        print("갭 실패", e)
    try:
        F = get_json("archive/x/focus_live.json")
        for a in F.get("alerts", []):
            if a.get("k") != "돌파":
                continue
            day = F.get("date") or now.strftime("%Y-%m-%d")
            code = a["t"]
            us = not (code[:1].isdigit())
            if us and int((a.get("at") or "12:00")[:2]) < 12:      # 미국 장은 한국 새벽 → 미국 날짜는 하루 전
                day = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
            k = f"{code}|{day}"
            if k not in cands:
                cands[k] = {"code": code, "name": a.get("name") or code, "mkt": "US" if us else "KR", "d": day, "src": "focus", "score": 70, "theme": a.get("theme")}
    except Exception as e:
        print("집중 실패", e)
    try:   # 🤫 조용한 매집 → 20일 박스 돌파
        A = get_json("archive/x/perf_accum.json")
        for x in A.get("signals", []):
            if x.get("abrk") and x.get("abd") is not None:
                d = (dt.date.fromisoformat(x["d0"]) + dt.timedelta(days=int(x["abd"]))).isoformat() if x.get("d0") else None
                k = f"{x['code']}|{d}"
                if d and k not in cands:
                    cands[k] = {"code": x["code"], "name": x.get("name") or x["code"], "mkt": x.get("mkt"), "d": d, "src": "accum", "score": x.get("score") or 0, "lv": x.get("box")}
    except Exception as e:
        print("매집 실패", e)
    try:   # 🔗 미국 테마 ETF 가 뛰면 한국 연결주는 D+k 에 따라옴 (focus.json lag) → 다음 한국 거래일 종가에 진입
        F = json.loads((ROOT / "market" / "focus.json").read_text(encoding="utf-8"))
        asof = F.get("asof") or now.strftime("%Y-%m-%d")
        for t in F.get("themes", []):
            lg, r1 = t.get("lag") or {}, t.get("r1") or 0
            if r1 >= _P["lead_min"] and (lg.get("cor") or 0) >= _P["lead_cor"] and (t.get("stage") or {}).get("s") in ("초입", "주도"):
                for x in t.get("kr", [])[:2]:
                    if x.get("act") == "추격 금지":
                        continue
                    k = f"{x['t']}|{asof}|lead"
                    if k not in cands:
                        cands[k] = {"code": x["t"], "name": x.get("name") or x["t"], "mkt": "KR", "d": asof, "src": "lead", "score": 50 + r1 * 5,
                                    "theme": t["name"], "note": f"{t['sym']} {r1:+.1f}% → D+{lg.get('k')} 상관 {lg.get('cor')}"}
    except Exception as e:
        print("선행 실패", e)
    for x in IL.get("log") or []:               # 🏔📊🩹 새 아이디어 신호 (market/kick_ideas_live.json, 매일 KST 07:20)
        if x.get("src") in ("nh52", "pead", "dip") and x.get("code") and x.get("d"):
            k = f"{x['code']}|{x['d']}|{x['src']}"
            if k not in cands:
                cands[k] = {"code": x["code"], "name": x.get("name") or x["code"], "mkt": x.get("mkt"), "d": x["d"], "src": x["src"],
                            "score": 50 + (x.get("score") or 0) if x["src"] != "dip" else 0}   # 컵·갭 점수(40~90)와 비슷한 눈금
    for x in QL.get("log") or []:               # 🔌🕵 Q16 신호 (market/q16_live.json, 매일 KST 07:25)
        if x.get("src") in ("cust", "ins") and x.get("code") and x.get("d"):
            k = f"{x['code']}|{x['d']}|{x['src']}"
            if k not in cands:
                cands[k] = {"code": x["code"], "name": x.get("name") or x["code"], "mkt": "US", "d": x["d"], "src": x["src"],
                            "score": 50 + (x.get("score") or 0), "note": x.get("note")}
    for back in range(6):                       # 🐋 최근 고래 신호 (TOP10 · 큰손 매수)
        day = (now - dt.timedelta(days=back)).strftime("%Y-%m-%d")
        try:
            W = get_json(f"archive/whale/{day}/data.json").get("signals", {})
            for k in ("top10", "big", "mov"):
                whale |= set(W.get(k) or [])
            for tkr in (W.get("big") or [])[:6]:      # 🐋 큰손이 새로 크게 산 종목 — 그 자체로 후보
                k = f"{tkr}|{day}|whale"
                if k not in cands and not any(v["code"] == tkr and v["src"] == "whale" and v["d"] >= (now - dt.timedelta(days=20)).strftime("%Y-%m-%d") for v in cands.values()):
                    cands[k] = {"code": tkr, "name": tkr, "mkt": "US", "d": day, "src": "whale", "score": 40}
            break
        except Exception:
            continue
    C["cands"] = cands
    C["whale"] = sorted(whale)
    CANDS.write_text(json.dumps(C, ensure_ascii=False, indent=0), encoding="utf-8")
    return C


def trend_slice(D, nin, nout, wmode):
    """🧭 자산 추세 칸 — src/kick_ideas_bt.py trend_run 과 같은 규칙(신호 다음 날 종가 실행 · 왕복 0.5%). → ({날짜: 값}, 들고 있는 것, 거래)"""
    import pandas as pd
    import yfinance as yf
    from src.kick_ideas_bt import TREND_U, trend_run
    st = (dt.date.fromisoformat(D[0]) - dt.timedelta(days=500)).isoformat()
    df = yf.download(TREND_U + ["SGOV"], start=st, auto_adjust=True, progress=False, group_by="ticker", threads=True)
    px = {}
    for t in TREND_U + ["SGOV"]:
        try:
            x = df[t].rename(columns=str.lower)[["high", "low", "close"]].dropna()
            if len(x) > nin + 5:
                px[t] = x
        except Exception:
            pass
    sg = px.pop("SGOV")["close"].pct_change().fillna(0) if "SGOV" in px else None
    if len(px) < 5:
        return {}, [], []
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(v.index) for v in px.values()])))
    cd = sg.reindex(allidx).fillna(0) if sg is not None else pd.Series(0.0, index=allidx)
    s, tr, op = trend_run(px, cd, nin, nout, wmode)
    nav = (1 + s).cumprod()
    tsv = {}
    for d in D:
        a = nav[nav.index.strftime("%Y-%m-%d") <= d]
        tsv[d] = float(a.iloc[-1]) if len(a) else 1.0
    for o in op:
        c = px[o["sym"]]["close"]
        o["entry"] = round(float(c[c.index.strftime("%Y-%m-%d") >= o["d"]].iloc[0]), 4)
        o["now"] = round(float(c.iloc[-1]), 4)
    return tsv, op, [t for t in tr if t["x"] >= D[0]]


BRAIN_GATE_FROM = "2026-10-14"


def is_brain(v):
    return str(v.get("note") or "").startswith("🧠") or v.get("by") == "brain"


def brain_gate():
    """두뇌 선제 아이디어 킥 편입 문: 승패 난 것 20건↑ · 승률 45%↑ · 평균 + 일 때만 열림"""
    try:
        sb = (json.loads((ROOT / "brain" / "state.json").read_text(encoding="utf-8")).get("scorecard") or {}).get("bets") or {}
    except Exception:
        sb = {}
    w, l, avg = sb.get("win") or 0, sb.get("loss") or 0, sb.get("avg")
    n = w + l
    on = n >= 20 and w / n >= 0.45 and (avg or 0) > 0
    return {"on": on, "n": n, "win": w, "loss": l, "avg": avg,
            "why": "열림" if on else f"닫힘 — 승패 {n}건({w}승 {l}패, 평균 {avg if avg is not None else '–'}%) · 20건↑·승률 45%↑·평균 + 되면 다시 켬"}


def main() -> int:
    now = dt.datetime.now(KST)
    P = json.loads(PORT.read_text(encoding="utf-8"))
    START = P["start"]
    C = collect(now)
    PROOF = proof()
    allc = [v for v in C["cands"].values() if v["d"] >= START and v["src"] not in OFF and not (v["src"] in OFF_FROM and v["d"] >= OFF_FROM[v["src"]])]
    shadow_c = [v for v in allc if not (v["src"] in KICK_SRCS and PROOF.get(v["src"], {}).get("on"))]   # 아직 못 들어오는 신호 → 그림자 채점
    # 10/13 사용자 「둘 다 진행」: 🧠 두뇌 선제 아이디어(뉴스 재료)는 성적이 나빠(승패 난 9건 2승 7패 · 평균 −3.7%) 킥 편입을 멈추고 그림자 채점만.
    #   다시 켜는 조건: 승패 난 것 20건 이상 · 승률 45% 이상 · 평균 + (brain/state.json scorecard.bets). 10/14 이후 후보만 (지난 장부는 그대로 — 소급 안 함)
    BG = brain_gate()
    if not BG["on"]:
        _bz = [v for v in allc if v not in shadow_c and is_brain(v) and v["d"] >= BRAIN_GATE_FROM]
        shadow_c += _bz
    cands = [v for v in allc if v not in shadow_c]
    recent_sig = {}                                    # 종목 → 최근 신호 이모티콘 (고래 종목에도 ☕·📈·🤫 표시)
    for v in C["cands"].values():
        if v["src"] in TAG and v["d"] >= (now - dt.timedelta(days=30)).strftime("%Y-%m-%d"):
            recent_sig.setdefault(v["code"], set()).add(TAG[v["src"]])
    ADAPT = {}
    try:   # 우리 장부에서 배운 신호별 성적 → 가중치 (거래 5건 이상부터)
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        by = {}
        for t in prev.get("closed_all") or prev.get("closed", []):
            by.setdefault(t["src"], []).append(t["r"])
        for src, rs in by.items():
            if len(rs) >= 5 and _P.get("adaptive"):
                ADAPT[src] = {"n": len(rs), "avg": round(sum(rs) / len(rs), 2), "win": round(sum(1 for r in rs if r > 0) / len(rs) * 100), "adj": round(max(-20, min(20, sum(rs) / len(rs) * 2)), 1)}
    except Exception:
        pass
    whale = set(C.get("whale", []))
    import yfinance as yf
    WL = whale_lists() if WS > 0 else []
    tick = sorted({c["code"] for c in cands + shadow_c} | {"SGOV", "SPY"} | {r["t"] for _, _, rows in WL for r in rows[:WN * 2]})
    start = (dt.date.fromisoformat(START) - dt.timedelta(days=130)).isoformat()   # 🐸 ID60 계산에 신호일 전 60거래일 필요
    df = yf.download(tick, start=start, interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    CL = {}
    for t in tick:
        try:
            s = df[t]["Close"].dropna()
            if len(s):
                CL[t] = s
        except Exception:
            pass
    # 🎰 Q16-3 MAX 거름망 — 미국 ☕·📈 후보의 신호일 「전」 20거래일 하루 최대 상승률(%)
    MX = Q16B.get("max") or {}
    MX_TH, MX_ON = MX.get("th") or 10, MX.get("verdict") == "✅"
    cut = []
    for c in list(cands) + [v for v in shadow_c if v["src"] in ("cup", "cup_eye", "gap")]:
        if c["src"] not in ("cup", "cup_eye", "gap") or c.get("mkt") != "US" or c["code"] not in CL:
            continue
        s_ = CL[c["code"]]
        a = s_[s_.index.strftime("%Y-%m-%d") < c["d"]].iloc[-21:]
        if len(a) < 16:
            continue
        c["max20"] = round(float((a.pct_change().dropna() * 100).max()), 1)
        if c["max20"] >= MX_TH:
            cut.append(c)
    for c in cut:
        shadow_c.append({**c, "src": "maxcut"})
        if MX_ON and c in cands:
            cands.remove(c)
    # 🐸 Q18-2 개구리 거름망 — 📈 미국 갭 후보의 신호일 「전」 60거래일 ID(정보 이산성) = sign(누적) × (내린 날 − 오른 날 비율)
    #    ID ≥ 기준(앞 기간 상위 ⅓ = 며칠 크게 튀어 오른 것) → 판정 ✅ 이면 킥에서 빼고 🐸 그림자 채점, 아니면 그림자만. ☕ 컵은 표시만.
    FR = Q18B.get("frog") or {}
    FR_W, FR_TH, FR_ON = int(FR.get("W") or 60), float(FR.get("th") if FR.get("th") is not None else -0.05), FR.get("verdict") == "✅"
    fcut = []
    for c in list(cands) + [v for v in shadow_c if v["src"] in ("cup", "cup_eye", "gap")]:
        if c["src"] not in ("cup", "cup_eye", "gap") or c.get("mkt") != "US" or c["code"] not in CL:
            continue
        s_ = CL[c["code"]]
        a = s_[s_.index.strftime("%Y-%m-%d") < c["d"]].iloc[-(FR_W + 1):]
        if len(a) < FR_W + 1:
            continue
        r_ = a.pct_change().dropna()
        pret = float(a.iloc[-1] / a.iloc[0] - 1)
        c["id60"] = round(float((1 if pret > 0 else -1 if pret < 0 else 0) * ((r_ < 0).mean() - (r_ > 0).mean())), 3)
        if c["src"] == "gap" and c["id60"] >= FR_TH:
            fcut.append(c)
    for c in fcut:
        shadow_c.append({**c, "src": "frog"})
        if FR_ON and c in cands:
            cands.remove(c)
    # 📰 Q13-1 이유 있는 갭 — 앱이 실적일 0~3일 뒤 갭을 「📊 실적 갭」으로 떼어 내므로 미국 「📈 돌파 갭」 = 실적 없이 뜬 갭.
    #    판정 ✅ 이면 미국 📈 갭을 킥에서 빼고 📰 그림자 채점만, 아니면 그림자만. 한국·일본·홍콩은 과거 실적일 자료가 없어 시험 못 함 → 그대로.
    NW = Q13B.get("news") or {}
    NW_ON = NW.get("verdict") == "✅"
    ncut = [c for c in list(cands) + [v for v in shadow_c if v["src"] == "gap"] if c["src"] == "gap" and c.get("mkt") == "US"]
    for c in ncut:
        shadow_c.append({**c, "src": "nonews"})
        if NW_ON and c in cands:
            cands.remove(c)
    # 🎯 Q15-5 갭 눌림 진입 — 미국 📈 돌파 갭은 「다음 날 종가」 대신, 갭 뒤 W거래일 안에 저가가 갭의 f 만큼 되돌린 자리
    #    (P0 + (1−f)·갭 크기, P0 = 갭 전날 종가)에 닿고 종가는 P0 위에서 끝난 날 j 를 새 신호일로 → 정직 계산은 j 다음 날 종가 진입.
    #    그 전에 종가 ≤ P0(갭 다 메움)면 취소 · W일 안에 안 눌리면 건너뜀(쫓지 않음) → 🪂 그림자로 「다음 날 종가에 샀다면」 채점.
    #    눌림 진입 칸의 「갭 메움」 출구선 = P0(갭 전날 종가) — 검증 조건(종가 ≤ P0 이면 취소)과 같은 선.
    #    판정 ✅/🧪 일 때만, 그리고 PB_FROM 이후 신호만(지난 장부는 소급하지 않음). 한국 갭은 시험에서 둘 다 크게 져서 그대로.
    PB = Q15B.get("pull") or {}
    PB_ON, PB_W, PB_F = PB.get("verdict") in ("✅", "🧪"), int(PB.get("W") or 3), float(PB.get("f") or 0.75)
    PB_FROM = PB.get("from") or "2026-10-14"
    pb_rows = []
    for c in [x for x in cands if x["src"] == "gap" and x.get("mkt") == "US" and x["d"] >= PB_FROM and x["code"] in CL]:
        try:
            s_ = CL[c["code"]]
            o_ = df[c["code"]]["Open"].reindex(s_.index).to_numpy(float)
            l_ = df[c["code"]]["Low"].reindex(s_.index).to_numpy(float)
        except Exception:
            continue
        ds_ = list(s_.index.strftime("%Y-%m-%d"))
        if c["d"] not in ds_ or ds_.index(c["d"]) == 0:
            continue
        gi = ds_.index(c["d"])
        p0 = float(s_.iloc[gi - 1])
        lv = p0 + (1 - PB_F) * (o_[gi] - p0)
        st, jd = "skip", None
        for j in range(gi + 1, gi + PB_W + 1):
            if j >= len(s_):
                st = "wait"
                break
            cj = float(s_.iloc[j])
            if cj <= p0:
                st = "cancel"
                break
            if l_[j] <= lv and cj > p0:
                st, jd = "in", ds_[j]
                break
        pb_rows.append({"code": c["code"], "d": c["d"], "st": st, "j": jd, "lv": round(lv, 4), "p0": round(p0, 4)})
        if st in ("skip", "cancel"):
            shadow_c.append({**c, "src": "pbskip"})
        if not PB_ON:
            continue
        k_ = cands.index(c)
        if st == "in":
            cands[k_] = {**c, "d": jd, "d_gap": c["d"], "lv": p0, "note": f"🎯 갭 눌림 진입(Q15-5 · 갭 {c['d'][5:]} → 눌림 {jd[5:]})"}
        else:
            cands[k_] = None
    cands = [c for c in cands if c is not None]
    # 🤝 Q10-2 신호 합의 — 미국 후보에 지난 W거래일(오늘 포함, 달력 W×1.45일) 안 「다른 종류」 신호가 같은 종목에 있으면 합의.
    #    종류: ☕ 컵(=신고가) · 📈 갭 · 📊 실적 갭 · 🔌 고객사 (과거 검증에 쓴 넷만). 같은 날 갭+컵 짝은 한 신호로 침(갭이 대개 신고가라 저절로 겹침).
    #    판정 ✅(미국) 이면 킥 순위 +bonus · 늘 🤝 그림자 채점(우리 장부로 다시 확인). 한국은 ❌ 라 안 붙임.
    AG = Q10B.get("agree") or {}
    AG_ON, AG_W, AG_BONUS = AG.get("verdict") == "✅", int(AG.get("W") or 5), float(AG.get("bonus") or 30)
    AG_K = AG.get("kinds") or {"cup": "nh", "cup_eye": "nh", "gap": "gap", "earn": "pead", "pead": "pead", "cust": "cust"}
    _sig = {}
    for v in C["cands"].values():
        if v.get("mkt") == "US" and v["src"] in AG_K:
            _sig.setdefault(v["code"], []).append((v["d"], AG_K[v["src"]], v["src"]))
    agreed = []
    for c in list(cands) + [v for v in shadow_c if v["src"] in AG_K]:
        if c.get("mkt") != "US" or c["src"] not in AG_K:
            continue
        k0, lo = AG_K[c["src"]], (dt.date.fromisoformat(c["d"]) - dt.timedelta(days=round(AG_W * 1.45))).isoformat()
        oth = sorted({s_ for d_, k_, s_ in _sig.get(c["code"], []) if lo <= d_ <= c["d"] and k_ != k0 and not (d_ == c["d"] and {k_, k0} == {"gap", "nh"})})
        if oth:
            c["agree"] = [TAG.get(x, x) for x in oth]
            if c not in agreed:
                agreed.append(c)
    for c in agreed:
        shadow_c.append({**c, "src": "agree"})
    # 🇰🇷 Q16-1 한국 돌파 갭 문 닫기 — 한국 📈 갭 대용은 검증마다 크게 짐(시험 기간 초과 −2.9% · 10년 중 9년 짐).
    #    판정 ✅ 이면 KG_FROM 이후 한국 📈 갭은 킥에서 빼고 🇰🇷 그림자 채점만(빈 칸은 같은 날 다른 후보가 순위대로) · 지난 장부는 소급 안 함.
    KG = Q16X.get("krgap") or {}
    KG_ON, KG_FROM = KG.get("verdict") == "✅", KG.get("from") or "2026-10-14"
    kcut = [c for c in cands + [v for v in shadow_c if v["src"] == "gap"] if c["src"] == "gap" and c.get("mkt") == "KR" and c["d"] >= KG_FROM]
    for c in kcut:
        shadow_c.append({**c, "src": "krgap"})
        if KG_ON and c in cands:
            cands.remove(c)
    # 🇨🇳 Q16-3 중국 신용 자극 — 판정 ✅ 이고 그 신호일에 「줄어드는 국면」(쓸 수 있는 날 기준)이면 한국 후보 크기 절반 (🧪 이하면 표시만)
    CH = Q16X.get("china") or {}
    CH_ON = CH.get("verdict") == "✅"
    def _ch_off(d_):
        ser = [x for x in (CH.get("series") or []) if x.get("avail") and x["avail"] <= d_]
        if len(ser) < 4:
            return None
        ci = [x["ci"] for x in ser]
        pk = CH.get("pick") or "k1"
        if pk == "neg":
            return ci[-1] < 0
        k_ = int(pk[1:]) if pk[1:].isdigit() else 1
        return all(ci[-j] < ci[-j - 1] for j in range(1, k_ + 1))
    for c in cands:
        if c.get("mkt") == "KR" and c["d"] >= (CH.get("from") or "2026-10-14"):
            off_ = _ch_off(c["d"])
            if off_:
                c["china_off"] = True
                if CH_ON:
                    c["size"] = min(c.get("size", 1.0), 0.5)
    cal = [d for d in CL["SPY"].index if d.strftime("%Y-%m-%d") >= START]
    D = [d.strftime("%Y-%m-%d") for d in cal]

    def px(t, d):
        s = CL.get(t)
        if s is None:
            return None
        a = s[s.index.strftime("%Y-%m-%d") <= d]
        return float(a.iloc[-1]) if len(a) else None

    def ma20(t, d):
        s = CL.get(t)
        a = s[s.index.strftime("%Y-%m-%d") <= d] if s is not None else []
        return float(a.iloc[-20:].mean()) if len(a) >= 20 else None

    def ma5(t, d):
        s = CL.get(t)
        a = s[s.index.strftime("%Y-%m-%d") <= d] if s is not None else []
        return float(a.iloc[-5:].mean()) if len(a) >= 5 else None

    def by_day_of(honest_):
        """신호 날짜 → 그 날 또는 다음 미국 거래일로 묶음.
        정직(honest_): 신호는 장 마감 뒤에 나오므로 그 종목의 「다음 거래일」 종가에 산다 (그 날 이후 첫 미국 거래일에 묶음)."""
        out_ = {}
        for c in cands:
            if c["code"] not in CL:
                continue
            sd = c["d"]
            own = CL[c["code"]]
            ods = own.index.strftime("%Y-%m-%d")
            if not len(own[ods == sd]):
                continue                                 # 그 날 종가가 없으면(휴장 등) 건너뜀
            ed = sd
            if honest_:
                nxt = [x for x in ods if x > sd]
                if not nxt:
                    continue                             # 다음 날 종가가 아직 없음 → 아직 못 삼
                ed = nxt[0]
            tgt = next((x for x in D if x >= ed), None)
            if tgt:
                pr = PRI.get(c["src"], 0) + c["score"] + (_P["whale_bonus"] if c["code"] in whale else 0) + (ADAPT.get(c["src"], {}).get("adj", 0)) \
                    + (AG_BONUS if AG_ON and c.get("agree") else 0)
                out_.setdefault(tgt, []).append({**c, "pr": round(pr, 1), "whale": c["code"] in whale, "ed": ed})
        return out_

    def simulate(honest_=False):
        """돌파 슬리브 되짚기. honest_=True 면 다음 날 종가 진입 + 사고팔 때 비용(왕복 0.5% · 한국 0.45%의 절반씩)."""
        by_day = by_day_of(honest_)
        fee = (lambda m: (0.0045 if m == "KR" else 0.005) / 2) if honest_ else (lambda m: 0.0)
        cash, pos, closed, events = 1.0, [], [], []
        val, peak, pause_until = [1.0], 1.0, -1
        last_exit = {}
        prev = START
        for i, d in enumerate(D):
            # 현금 이자 (SGOV)
            if i > 0:
                a, b = px("SGOV", D[i - 1]), px("SGOV", d)
                if a and b:
                    cash *= b / a
            # 들고 있는 것 점검 (들어간 다음 날부터)
            for p in list(pos):
                p["held"] += 1
                c = px(p["code"], d)
                if c is None:
                    continue
                p["last"] = c
                p["max"] = max(p["max"], c)
                r = c / p["entry"] - 1
                why = None
                xr = XR.get(p["src"])
                if xr:                                   # 🏔📊🩹 새 아이디어는 검증한 그대로의 출구
                    m5 = ma5(p["code"], d) if xr.get("ma5") else None
                    if xr.get("stop") is not None and r <= xr["stop"]:
                        why = f"손절 {xr['stop'] * 100:.0f}%"
                    elif xr.get("take") is not None and r >= xr["take"]:
                        why = f"익절 +{xr['take'] * 100:.0f}%"
                    elif m5 and c > m5:
                        why = "5일선 위 마감 (반등 끝)"
                    elif p["held"] >= xr["hold"]:
                        why = f"{xr['hold']}일 보유 끝"
                elif r <= STOP:
                    why = "손절 −5%"
                elif _P.get("gap_fill_exit") and p["src"] == "gap" and p.get("lv") and c < p["lv"]:
                    why = "갭 메움 (메운 갭은 평균 −1.3%)"
                elif not p["half"] and r >= TAKE:
                    cash += p["sh"] / 2 * c * (1 - fee(p.get("mkt")))
                    p["sh"] /= 2
                    p["half"] = True
                    p["realized"] += (c / p["entry"] - 1) * p["cost"] / 2
                    events.append({"d": d, "k": "절반 정리", "code": p["code"], "name": p["name"], "r": round(r * 100, 1)})
                    continue
                elif p["half"]:
                    m = ma20(p["code"], d)
                    if m and c < m:
                        why = "20일선 이탈 (나머지 정리)"
                elif p["held"] >= TIME_D and p["max"] / p["entry"] - 1 < TIME_MIN:
                    why = "시간 손절 (15일 +3% 못 넘음)"
                if why:
                    cash += p["sh"] * c * (1 - fee(p.get("mkt")))
                    rr = (p["realized"] + (c / p["entry"] - 1) * (p["cost"] / 2 if p["half"] else p["cost"])) / p["cost"]
                    closed.append({**{k: p[k] for k in ("code", "name", "src", "d0", "entry", "mkt")}, "d1": d, "exit": round(c, 4), "r": round(rr * 100, 2),
                                   "days": p["held"], "why": why})
                    events.append({"d": d, "k": "팔기", "code": p["code"], "name": p["name"], "r": round(rr * 100, 1), "why": why})
                    last_exit[p["code"]] = i
                    pos.remove(p)
            total = cash + sum(p["sh"] * (px(p["code"], d) or p["entry"]) for p in pos)
            peak = max(peak, total)
            # 🧯 Q13-5 손절 뭉침 차단기 — 오늘 손절로 닫힌 칸이 M개 이상이면 오늘부터 P거래일 새 진입 멈춤(판정 ✅ 일 때만)
            if BK_ON:
                nst = sum(1 for x in closed if x["d1"] == d and str(x.get("why", "")).startswith("손절"))
                if nst >= BK_M and pause_until < i + BK_P - 1:
                    pause_until = i + BK_P - 1
                    events.append({"d": d, "k": "차단기", "why": f"같은 날 손절 {nst}개 → {BK_P}거래일 새 진입 멈춤 (🧯 Q13-5)"})
            if total - 1 <= BRAKE and pause_until < i:
                pause_until = i + BRAKE_D
                events.append({"d": d, "k": "브레이크", "why": f"슬리브 {round((total - 1) * 100, 1)}% → {BRAKE_D}거래일 새 진입 멈춤"})
            # 새로 들어가기
            if i > pause_until:
                free = SLOTS - len([p for p in pos if p["src"] != "dip"])     # 🩹 급락 반등은 빈 자리(현금)를 쓰므로 자리로 세지 않음
                held = {p["code"] for p in pos}
                pick = []
                for c in sorted(by_day.get(d, []), key=lambda x: -x["pr"]):
                    if c["src"] == "dip":
                        continue
                    if len(pick) >= min(free, MAX_NEW):
                        break
                    if c["code"] in held or c["code"] in {x["code"] for x in pick}:
                        continue
                    if c["code"] in last_exit and i - last_exit[c["code"]] < REENTRY:
                        continue
                    pick.append(c)
                for c in pick:
                    e = px(c["code"], c["ed"]) or px(c["code"], d)
                    if not e:
                        continue
                    cost = total / SLOTS * (0.5 if PROOF.get(c["src"], {}).get("trial") else 1.0) * float(c.get("size", 1.0))
                    for q in [q for q in pos if q["src"] == "dip"] if cost > cash else []:   # 새 신호가 오면 🩹 반등 칸을 비워 자리를 내줌
                        qc = px(q["code"], d) or q["entry"]
                        cash += q["sh"] * qc * (1 - fee(q.get("mkt")))
                        rr = (qc / q["entry"] - 1)
                        closed.append({**{k: q[k] for k in ("code", "name", "src", "d0", "entry", "mkt")}, "d1": d, "exit": round(qc, 4), "r": round(rr * 100, 2),
                                       "days": q["held"], "why": "새 신호에 자리 내줌"})
                        events.append({"d": d, "k": "팔기", "code": q["code"], "name": q["name"], "r": round(rr * 100, 1), "why": "새 신호에 자리 내줌"})
                        pos.remove(q)
                    if cost > cash:
                        cost = cash
                    if cost <= 0:
                        break
                    cash -= cost
                    pos.append({"code": c["code"], "name": c["name"], "mkt": c.get("mkt"), "src": c["src"], "d0": d, "entry": e, "sh": cost * (1 - fee(c.get("mkt"))) / e, "cost": cost, "lv": c.get("lv"),
                                "held": 0, "max": e, "last": e, "half": False, "realized": 0.0, "pr": c["pr"], "whale": c.get("whale")})
                    events.append({"d": d, "k": "사기", "code": c["code"], "name": c["name"], "src": SRC_NAME.get(c["src"], c["src"]), "px": round(e, 4), "note": c.get("note"),
                                   "w": round(cost / total * sl_at(d) * 100, 2)})
                # 🩹 급락 반등: 남는 빈 자리 몫(현금)으로 SPY 등을 짧게 (다른 신호보다 뒤 · 하나만)
                for c in [x for x in by_day.get(d, []) if x["src"] == "dip"][:1]:
                    if any(p["src"] == "dip" for p in pos) or c["code"] in held:
                        continue
                    e = px(c["code"], c["ed"]) or px(c["code"], d)
                    nfree = SLOTS - len([p for p in pos if p["src"] != "dip"])
                    cost = min(cash, total / SLOTS * nfree * (0.5 if PROOF.get("dip", {}).get("trial") else 1.0))
                    if not e or cost <= total * 0.01:
                        continue
                    cash -= cost
                    pos.append({"code": c["code"], "name": c["name"], "mkt": c.get("mkt"), "src": "dip", "d0": d, "entry": e, "sh": cost * (1 - fee(c.get("mkt"))) / e, "cost": cost, "lv": None,
                                "held": 0, "max": e, "last": e, "half": False, "realized": 0.0, "pr": c["pr"], "whale": False})
                    events.append({"d": d, "k": "사기", "code": c["code"], "name": c["name"], "src": SRC_NAME["dip"], "px": round(e, 4), "w": round(cost / total * sl_at(d) * 100, 2)})
            total = cash + sum(p["sh"] * (px(p["code"], d) or p["entry"]) for p in pos)
            if i > 0:
                val.append(total)
            else:
                val[0] = total
        return val, closed, events, pos, pause_until

    val, closed, events, pos, pause_until = simulate(False)
    hval, hclosed = simulate(True)[:2]

    # 👻 그림자 채점 — 킥에 못 들어온 신호도 「들어갔다면」을 같은 규칙으로 계산해 쌓는다. 표본 20↑·손익비 1.5↑면 다음부터 진짜로 들어옴.
    SH = json.loads(OUT.read_text(encoding="utf-8")).get("shadow_log", {}) if OUT.exists() else {}
    for c in shadow_c:
        key = f"{c['code']}|{c['d']}|{c['src']}"
        s_ = CL.get(c["code"])
        if s_ is None:
            continue
        ds = [x for x in s_.index if x.strftime("%Y-%m-%d") >= c["d"]]
        if len(ds) < 2:
            continue
        e0 = float(s_[ds[0]]); r, half, mx = None, False, e0
        xr = XR.get(c["src"])
        m5s = s_.rolling(5).mean() if xr and xr.get("ma5") else None
        for k_, x in enumerate(ds[1:], 1):
            p_ = float(s_[x]); mx = max(mx, p_)
            if xr:
                rr_ = p_ / e0 - 1
                if ((xr.get("stop") is not None and rr_ <= xr["stop"]) or (xr.get("take") is not None and rr_ >= xr["take"])
                        or (m5s is not None and p_ > float(m5s[x])) or k_ >= xr["hold"]):
                    r = rr_ * 100; break
                continue
            if p_ / e0 - 1 <= STOP:
                r = STOP * 100 if not half else (TAKE / 2 + (p_ / e0 - 1) / 2) * 100; break
            if not half and p_ / e0 - 1 >= TAKE:
                half = True
            if k_ >= TIME_D and mx / e0 - 1 < TIME_MIN:
                r = (p_ / e0 - 1) * 100; break
        done = r is not None or len(ds) - 1 >= (xr["hold"] if xr else TIME_D)
        if r is None:
            last = float(s_[ds[-1]]); r = ((TAKE / 2 + (last / e0 - 1) / 2) if half else (last / e0 - 1)) * 100
        SH[key] = {"src": c["src"], "code": c["code"], "d": c["d"], "r": round(r, 2), "done": done}
    shadow = {}
    for v in SH.values():
        shadow.setdefault(v["src"], []).append(v["r"])
    shadow_stat = {}
    for k_, rs in shadow.items():
        g_, l_ = sum(x for x in rs if x > 0), -sum(x for x in rs if x < 0)
        shadow_stat[k_] = {"n": len(rs), "avg": round(sum(rs) / len(rs), 2), "win": round(sum(1 for x in rs if x > 0) / len(rs) * 100),
                           "pf": round(g_ / l_, 2) if l_ > 0 else None, "tag": TAG.get(k_, "")}

    # 🐋 고래 바스켓 — 분기마다 같은 비중으로 사서 다음 목록까지 들고 감 (−30% 사고 대비만)
    wval, wbask, wq, wev, wsw = [1.0], [], None, [], []
    wv = 1.0
    for i, d in enumerate(D):
        cur = [x for x in WL if x[0] <= d]
        if cur and (wq is None or cur[-1][1] != wq):
            q, rows = cur[-1][1], cur[-1][2]
            pick = [r for r in rows if r["t"] in CL and px(r["t"], d)][:WN]
            if pick:
                old = {b["t"] for b in wbask}
                wbask = [{**r, "d0": d, "entry": px(r["t"], d), "on": True, "exit": None} for r in pick]
                wq = q
                wsw.append(d)
                wev.append({"d": d, "k": "고래 바스켓 교체" if old else "고래 바스켓 시작", "q": q, "in": [b["t"] for b in wbask if b["t"] not in old],
                            "out": sorted(old - {b["t"] for b in wbask})})
                wbase = wv
        if wbask:
            parts = []
            for b in wbask:
                c = px(b["t"], d) or b["entry"]
                if b["on"] and c / b["entry"] - 1 <= WSTOP:
                    b["on"], b["exit"] = False, c
                    wev.append({"d": d, "k": "고래 −30% 정리", "t": b["t"]})
                parts.append((b["exit"] if not b["on"] else c) / b["entry"])
            wv = wbase * sum(parts) / len(parts)
        if i > 0:
            wval.append(wv)
        else:
            wval[0] = wv
    wsv = dict(zip(D, wval))

    # 🧭 자산 추세 칸 — 과거 검증 ✅(🧪면 절반)일 때만, trend_from 부터 기본 칸에서 떼어 냄
    TB = IB.get("trend") or {}
    TS = (_P.get("trend_sleeve", 0.05) * (0.5 if TB.get("verdict") == "🧪" else 1.0)) if TB.get("verdict") in ("✅", "🧪") else 0.0
    TF = _P.get("trend_from", "2026-10-13")
    tsv, t_open, t_tr = {}, [], []
    TF0 = next((x for x in D if x >= TF), None)          # 추세 칸 첫 반영일 (그 전 줄은 0)
    if TS > 0:
        try:
            nin, nout = (int(x) for x in TB["pick"]["rule"].split("|")[0].split("/"))
            tsv, t_open, t_tr = trend_slice(D, nin, nout, TB["pick"]["rule"].split("|")[1])
        except Exception as e:
            print("추세 칸 실패", e)
            TS = 0.0

    # 기본 포트 vs 킥 포트 (같은 날짜 줄)
    pdates, pnav = P["dates"], P["nav"]
    base = [1 + v / 100 for v in pnav]
    sv = dict(zip(D, val))
    sg = {d: px("SGOV", d) for d in pdates}
    RULE = P.get("rule") or {}
    RF, WS2 = RULE.get("from", "9999"), _P.get("whale_sleeve2", WS)
    rbase = [1 + v / 100 for v in RULE["nav"]] if RULE.get("nav") and len(RULE["nav"]) == len(pdates) else None

    def combine(sv, wsv, base=base, rbase=rbase, tsv=tsv):
        kick = [1.0]
        sleeve_line = [0.0]
        lastv = 1.0
        for j in range(1, len(pdates)):
            d0, d1 = pdates[j - 1], pdates[j]
            rb = base[j] / base[j - 1] - 1
            ts = TS if (tsv and d1 >= TF and d0 in tsv and d1 in tsv) else 0.0
            rt = (tsv[d1] / tsv[d0] - 1) if ts else 0.0
            if rbase and d1 >= RF:      # 🧪 10/12부터: 기본 칸은 규칙 비중 · 🐋 고래 10% · 킥 전체(돌파 9% + 고래 10%)만큼 기본을 줄임
                rbr = rbase[j] / rbase[j - 1] - 1
                rs_ = (sv.get(d1, sv.get(d0, 1.0)) / sv.get(d0, 1.0) - 1) if d0 in sv else (sv.get(d1, 1.0) - 1)
                rw_ = (wsv.get(d1, wsv.get(d0, 1.0)) / wsv.get(d0, 1.0) - 1) if d0 in wsv else 0.0
                SLd, W2d = sl_at(d1), w2_at(d1, WS2)
                kick.append(kick[-1] * (1 + (1 - SLd - W2d - ts) * rbr + SLd * rs_ + W2d * rw_ + ts * rt))
                lastv = sv.get(d1, lastv)
                sleeve_line.append(round((lastv - 1) * 100, 2))
                continue
            rs = (sv.get(d1, sv.get(d0, 1.0)) / sv.get(d0, 1.0) - 1) if d0 in sv else (sv.get(d1, 1.0) - 1)
            rg = (sg[d1] / sg[d0] - 1) if sg.get(d0) and sg.get(d1) else 0
            rw = (wsv.get(d1, wsv.get(d0, 1.0)) / wsv.get(d0, 1.0) - 1) if d0 in wsv else 0.0
            kick.append(kick[-1] * (1 + rb - (SLEEVE + WS + ts) * rg + SLEEVE * rs + WS * rw + ts * rt))
            lastv = sv.get(d1, lastv)
            sleeve_line.append(round((lastv - 1) * 100, 2))
        return kick, sleeve_line

    kick, sleeve_line = combine(sv, wsv)
    # 🧾 정직 버전: 돌파 칸은 다음 날 종가 진입 + 비용, 고래 바스켓은 바꿀 때마다 왕복 0.5% (기본 칸 비용은 port.json base_honest 쪽)
    hwv, hw_ = {}, 1.0
    for x, v in zip(D, wval):
        if x in wsw:
            hw_ *= 1 - (0.0025 if x == wsw[0] else 0.005)     # 처음엔 사기만(편도), 교체 땐 팔고 사기(왕복)
        hwv[x] = v * hw_
    PH = P.get("honest") or {}
    hb = [1 + v / 100 for v in PH["line"]] if len(PH.get("line") or []) == len(pdates) else base
    hrb = ([1 + v / 100 for v in PH["rule_line"]] if len(PH.get("rule_line") or []) == len(pdates) else rbase) if rbase else None
    hkick, hsleeve_line = combine(dict(zip(D, hval)), hwv, hb, hrb)
    for t in closed:
        t["src_name"] = SRC_NAME.get(t["src"], t["src"])
    trades = closed
    wins = [t for t in trades if t["r"] > 0]
    loss = [t for t in trades if t["r"] <= 0]
    avg = lambda L: round(sum(t["r"] for t in L) / len(L), 2) if L else None
    last_d = D[-1]
    openp = []
    for p in pos:
        c = px(p["code"], last_d) or p["entry"]
        openp.append({"code": p["code"], "name": p["name"], "mkt": p.get("mkt"), "src": SRC_NAME.get(p["src"], p["src"]), "d0": p["d0"], "entry": round(p["entry"], 4),
                      "now": round(c, 4), "r": round((c / p["entry"] - 1) * 100, 2), "days": p["held"], "half": p["half"], "whale": p.get("whale"),
                      "stop": (round(p["entry"] * (1 + STOP), 4) if not XR.get(p["src"]) else
                               (round(p["entry"] * (1 + XR[p["src"]]["stop"]), 4) if XR[p["src"]].get("stop") is not None else None)),
                      "take": round(p["entry"] * (1 + TAKE), 4), "w": round(p["sh"] * c / val[-1] * sl_at(last_d) * 100, 2), "sk": p["src"]})
    # ⚡ 하나의 킥 포트 — 돌파로 들어온 것 + 고래 바스켓을 한 목록으로, 종목마다 어디서 왔는지 작은 이모티콘
    WSN = w2_at(last_d, WS2) if rbase else WS     # 지금(다음 거래일에) 들고 갈 고래 칸 크기 — 규칙이 켜져 있으면 10%
    wset = {b["t"] for b in wbask if b["on"]}
    hold = []
    for o in openp:
        sk = o.get("sk") or next((k for k, v in SRC_NAME.items() if v == o["src"]), "")
        tg = TAG.get(sk, "")
        tags = [tg] if tg else []
        if o["code"] in wset or o.get("whale"):
            tags.append("🐋")
        hold.append({"code": o["code"], "name": o["name"], "tags": "".join(dict.fromkeys(tags)), "w": o["w"], "r": o["r"], "d0": o["d0"], "entry": o["entry"],
                     "now": o["now"], "kind": "돌파", "rule": ("🧪 시험 편입(절반 크기) · " if PROOF.get(sk, {}).get("trial") else "") + (xr_doc(XR[sk]) if XR.get(sk) else f"손절 {o['stop']:g} · +15% 절반"), "half": o["half"]})
    for o in t_open if TS > 0 else []:
        hold.append({"code": o["sym"], "name": o["sym"], "tags": "🧭", "w": round(TS * o["w"] * 100, 2), "r": o["r"], "d0": o["d"], "entry": o.get("entry"), "now": o.get("now"),
                     "kind": "추세", "rule": f"{TB['pick']['rule'].split('|')[0].replace('/', '일 고가 돌파 보유 · ')}일 저가 이탈 시 팖" + (f" ({TF}부터 반영)" if last_d < TF else ""), "half": False})
    for b in wbask:
        if not b["on"]:
            continue
        tags = ["🐋"] + sorted(recent_sig.get(b["t"], set()) - {"🐋", "🎯", "🔗"})
        nowp = px(b["t"], last_d) or b["entry"]
        hold.append({"code": b["t"], "name": b["t"], "tags": "".join(tags), "w": round(WSN * 100 / max(1, len(wbask)), 2), "r": round((nowp / b["entry"] - 1) * 100, 2),
                     "d0": b["d0"], "entry": round(b["entry"], 4), "now": round(nowp, 4), "kind": "고래", "rule": "분기 보유 · −30%만 정리",
                     "by": b["by"][:2], "half": False})
    hold.sort(key=lambda h: -h["r"])
    # 🙋 내 포트 (10/14 사용자 「킥 종목 중 체크한 것만 + S&P·나스닥 비중 직접」) — 앱이 계산하도록
    #    종목마다 산 날(d0)부터 날짜별 누적 %(산 값 기준, 그 전은 null) · 뼈대 상품 SPY·QQQ·GLD·SGOV 날짜별 누적 %
    _need = sorted(({h["code"] for h in hold} | {"SPY", "QQQ", "GLD", "SGOV"}) - set(CL))
    if _need:
        try:
            _df2 = yf.download(_need, start=start, interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
            for t in _need:
                try:
                    try:
                        s = _df2[t]["Close"]
                    except Exception:
                        s = _df2["Close"]
                    if hasattr(s, "columns"):
                        s = s.iloc[:, 0]
                    s = s.dropna()
                    if len(s):
                        CL[t] = s
                except Exception:
                    pass
        except Exception as e:
            print("내 포트용 시세 실패", e)
    for h in hold:
        en = h.get("entry")
        if not en or h["code"] not in CL:
            continue
        L = []
        for x in pdates:
            p_ = px(h["code"], x) if x >= h["d0"] else None
            L.append(round((p_ / en - 1) * 100, 2) if p_ else None)
        h["line"] = L
    assets = {}
    for t in ("SPY", "QQQ", "GLD", "SGOV"):
        p0 = px(t, pdates[0])
        if p0:
            assets[t] = [round(((px(t, x) or p0) / p0 - 1) * 100, 2) for x in pdates]
    # 🧪 새 아이디어 상태 (앱용 한눈 요약) — state: ✅ 채택 · 🧪 시험(절반) · 👻 그림자만 · ❌ 기각
    lastsig = {}
    for x in (IL.get("log") or []) + (QL.get("log") or []):
        lastsig.setdefault(x.get("src"), []).append(x)
    ideas_out = {}
    for k in IDEAS:
        b = IB.get(k) or {}
        if not b.get("verdict"):
            continue
        L_ = lastsig.get(k, [])
        dmax = max((x["d"] for x in L_), default=None)
        today = [x["code"] for x in L_ if x["d"] == dmax] if k != "trend" else \
            sorted(a for a, v in (((IL.get("state") or {}).get("trend") or {}).get("assets") or {}).items() if v.get("on"))
        ideas_out[k] = {"name": SRC_NAME[k], "state": b["verdict"], "on": bool(PROOF.get(k, {}).get("on")) if k != "trend" else TS > 0,
                        "why": b.get("why"), "rule": (b.get("pick") or {}).get("rule"),
                        "exit": xr_doc(XR.get(k)) if k != "trend" else "N일 고가 돌파 → 사고 · M일 저가 이탈 → 팖 (신호 다음 날 종가)",
                        "today": today[:20], "today_d": dmax if k != "trend" else ((IL.get("state") or {}).get("trend") or {}).get("assets", {}).get("SPY", {}).get("d"),
                        "n30": len(L_), "live_at": QL.get("at") if k in ("cust", "ins") else IL.get("at")}
        if k == "trend":
            ideas_out[k]["sleeve"] = TS
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"), "start": START, "asof": last_d,
        "hold": hold, "assets": assets, "proof": {k: v for k, v in PROOF.items() if k in ("whale", "cup", "gap", "accum", "earn") + IDEAS},
        "ideas": ideas_out,
        "q16_max": {"on": MX_ON, "th": MX_TH, "state": MX.get("verdict") or "⏳", "why": MX.get("why"),
                    "rule": f"☕·📈 미국 후보 중 신호일 전 20거래일 하루 최대 상승률 ≥ {MX_TH:g}% → " + ("킥에서 빼고 🎰 그림자 채점" if MX_ON else "킥은 그대로 · 🎰 그림자 채점만"),
                    "cut": [{"code": c["code"], "d": c["d"], "src": c["src"], "max20": c.get("max20")} for c in sorted(cut, key=lambda c: c["d"])][-20:]},
        "q18_frog": {"on": FR_ON, "w": FR_W, "th": FR_TH, "state": FR.get("verdict") or "⏳", "why": FR.get("why"),
                     "rule": f"📈 미국 갭 후보 중 신호일 전 {FR_W}거래일 ID ≥ {FR_TH:g}(며칠 크게 튀어 오른 것) → " + ("킥에서 빼고 🐸 그림자 채점" if FR_ON else "킥은 그대로 · 🐸 그림자 채점만"),
                     "cut": [{"code": c["code"], "d": c["d"], "src": c["src"], "id60": c.get("id60")} for c in sorted(fcut, key=lambda c: c["d"])][-20:]},
        "q13_news": {"on": NW_ON, "state": NW.get("verdict") or "⏳", "why": NW.get("why"),
                     "rule": "📈 미국 돌파 갭(실적 발표 0~3일 뒤가 아닌 갭) → " + ("킥에서 빼고 📰 그림자 채점" if NW_ON else "킥은 그대로 · 📰 그림자 채점만"),
                     "cut": [{"code": c["code"], "d": c["d"]} for c in sorted(ncut, key=lambda c: c["d"])][-20:]},
        "q15_pull": {"on": PB_ON, "w": PB_W, "f": PB_F, "from": PB_FROM, "state": PB.get("verdict") or "⏳", "why": PB.get("why"),
                     "rule": f"📈 미국 돌파 갭 → 갭 뒤 {PB_W}거래일 안 갭의 {round(PB_F * 100)}% 되돌림(저가) + 종가가 갭 전날 종가 위인 날을 새 신호일로, 안 오면 건너뜀(🪂 그림자) · 한국 갭은 그대로"
                             + ("" if PB_ON else " — 꺼짐(그림자만)"),
                     "rows": pb_rows[-20:]},
        "q16_krgap": {"on": KG_ON, "from": KG_FROM, "state": KG.get("verdict") or "⏳", "why": KG.get("why"),
                      "rule": "🇰🇷 한국 📈 돌파 갭 → " + ("킥에서 빼고 🇰🇷 그림자 채점" if KG_ON else "킥은 그대로 · 🇰🇷 그림자 채점만"),
                      "cut": [{"code": c["code"], "d": c["d"]} for c in sorted(kcut, key=lambda c: c["d"])][-20:]},
        "q16_china": {"on": CH_ON, "state": CH.get("verdict") or "⏳", "why": CH.get("why"), "pick": CH.get("pick"), "now": CH.get("now"),
                      "rule": "🇨🇳 중국 신용 자극이 줄어드는 국면 → " + ("한국 킥 새 진입 크기 절반" if CH_ON else "표시만(크기는 그대로)")},
        "q16_breadth": {m_: {"state": (Q16X.get("breadth") or {}).get(m_, {}).get("verdict") or "⏳", "pick": (Q16X.get("breadth") or {}).get(m_, {}).get("pick"),
                             "why": (Q16X.get("breadth") or {}).get(m_, {}).get("why"), "now": (Q16X.get("breadth") or {}).get(m_, {}).get("now"),
                             "rule": "🌡 지수 고점 3% 안 + 200일선 위 종목 비율 급감 → " + {"✅": "킥 새 진입 크기 절반", "🧪": "「주의」 표시만"}.get(
                                 (Q16X.get("breadth") or {}).get(m_, {}).get("verdict"), "안 붙임")} for m_ in ("US", "KR")},
        "q13_brake": {"on": BK_ON, "m": BK_M, "p": BK_P, "state": BK.get("verdict") or "⏳", "why": BK.get("why")},
        "q10_agree": {"on": AG_ON, "w": AG_W, "bonus": AG_BONUS, "state": AG.get("verdict") or "⏳", "why": AG.get("why"),
                      "rule": AG.get("rule") or "🤝 미국 후보에 다른 종류 신호가 겹치면 킥 순위 가점",
                      "hits": [{"code": c["code"], "d": c["d"], "src": c["src"], "with": c.get("agree")} for c in sorted(agreed, key=lambda c: c["d"])][-20:]},
        "trend": ({"sleeve": TS, "from": TF, "rule": (TB.get("pick") or {}).get("rule"), "line": [round((tsv[x] / tsv[TF0] - 1) * 100, 2) if (tsv and TF0 and x >= TF0 and x in tsv) else 0.0 for x in pdates],
                   "open": t_open, "trades": t_tr[-10:]} if TS > 0 else None),
        "rule": {"from": RF, "whale_sleeve": WS2, "base_now": RULE.get("now"), "why": RULE.get("why"), "quad": RULE.get("quad"), "cash": RULE.get("cash"), "use": RULE.get("use")},
        "vol_rule": RULE.get("vol_rule"),   # 🦴 변동성 맞춤(중간형) 오늘 상태 — port.py 가 계산
        "shadow_stat": shadow_stat, "shadow_log": SH, "brain_gate": BG,
        "tags": {"🐋": "고래 13F 큰 신규", "☕": "컵 돌파", "📈": "돌파 갭", "🤫": "조용한 매집 돌파", "📊": "실적 갭 · 실적 표류",
                 "🏔": "거래량 동반 52주 신고가", "🩹": "상승장 급락 반등", "🧭": "자산 추세"},
        "dates": pdates, "base": [round((b - 1) * 100, 2) for b in base], "kick": [round((k - 1) * 100, 2) for k in kick],
        "sleeve": round((val[-1] - 1) * 100, 2), "sleeve_line": sleeve_line,
        "honest": {"line": [round((k - 1) * 100, 2) for k in hkick], "ret": round((hkick[-1] - 1) * 100, 2),
                   "sleeve": round((hval[-1] - 1) * 100, 2), "sleeve_line": hsleeve_line, "trades": len(hclosed),
                   "avg": round(sum(t["r"] for t in hclosed) / len(hclosed), 2) if hclosed else None,
                   "note": "정직 계산 — 신호는 장 마감 뒤에 나오므로 돌파 칸은 다음 거래일 종가에 사고, 사고팔 때마다 비용(왕복 0.5% · 한국 0.45%, 환전 포함)을 뺌. "
                           "🐋 고래 바스켓은 교체 때 비용을 뺌. 기본 칸은 위 숫자 그대로(주간 리밸런싱 비용은 💼 포트의 base_honest). 판정·켜고 끄기에는 쓰지 않음."},
        "open": openp, "closed": trades[::-1][:40], "closed_all": [{"src": t["src"], "r": t["r"], "d1": t["d1"]} for t in trades], "events": events[::-1][:40],
        "stat": {"base": round((base[-1] - 1) * 100, 2), "kick": round((kick[-1] - 1) * 100, 2), "spy": P["stat"]["spy"], "whale": round((wval[-1] - 1) * 100, 2) if WS > 0 else None,
                 "trades": len(trades), "win": round(len(wins) / len(trades) * 100) if trades else None,
                 "avg_win": avg(wins), "avg_loss": avg(loss), "avg": avg(trades), "slots": f"{len(pos)}/{SLOTS}",
                 "paused": pause_until >= len(D) - 1},
        "rules": {"sleeve": SLEEVE, "slots": SLOTS, "stop": STOP, "take": TAKE, "time": TIME_D, "brake": BRAKE, "off": sorted(OFF), "whale_sleeve": WSN, "whale_n": WN},
        "whale": {"q": wq, "ret": round((wval[-1] - 1) * 100, 2), "line": [round((wsv.get(x, 1.0) - 1) * 100, 2) for x in pdates], "sleeve": WSN,
                  "rows": [{"t": b["t"], "n": b["n"], "w13f": b["w"], "by": b["by"], "d0": b["d0"], "entry": round(b["entry"], 4),
                            "now": round(px(b["t"], last_d) or b["entry"], 4), "r": round(((b["exit"] if not b["on"] else (px(b["t"], last_d) or b["entry"])) / b["entry"] - 1) * 100, 2),
                            "on": b["on"], "w": round(WSN * 100 / max(1, len(wbask)), 2)} for b in wbask],
                  "events": wev[::-1][:10],
                  "why": "13F 큰 신규 포지션 같은 비중 바스켓은 바이오 펀드를 빼면 매 분기 S&P 를 이김(1개월 5/5 +2.8%p · 3개월 4/4 +3.9%p · 6개월 3/3 +10.0%p, 2025Q2~2026Q2). 하나씩은 반반이라 바스켓으로만, 큰 승자를 자르지 않게 분기 동안 들고 감."} if WS > 0 else None,
        "by_src": {SRC_NAME.get(k, k): v for k, v in ADAPT.items()},
        "src_names": SRC_NAME,
        "note": (f"🧪 {RF}부터 킥 포트 = 규칙을 적용한 기본 칸 {round((1 - SLEEVE - WS2) * 100)}% (① 국면 현금 ③ 강한 칸 기울이기 ④ 추세 브레이크) + 돌파 {round(SLEEVE * 100)}% + 🐋 고래 {round(WS2 * 100)}%. 💼 기본 포트(리포트 그대로)와 S&P500을 같이 놓고 이기는지 본다. " if last_d >= RF else "") +
                f"⚡ 킥 포트 = 기본 포트에서 현금 {round((SLEEVE + WS) * 100)}%p 를 떼어 「성과가 확인된 신호」(🐋 고래 · ☕ 컵 · 📈 갭 · 🤫 매집 — 표본 20건↑·손익비 1.5↑)에만 담은 것. "
                f"☕📈🤫 돌파는 확인된 순간 {round(SLEEVE / SLOTS * 100, 1)}%씩(−5% 손절 · +15% 절반 익절), 🐋 고래는 13F 큰 신규를 같은 비중으로 분기 동안(−30%만 정리). "
                "아직 확인 안 된 신호는 표본이 차면 저절로 들어온다. 10/9 이전은 같은 규칙으로 되짚은 계산. 현지 통화 기준·수수료 제외. 매수 추천 아님.",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 오늘 새로 사고판 것 알림 (한 번만)
    sent = set(C.get("sent", []))
    today_ev = [e for e in events if e["d"] == last_d and e["k"] in ("사기", "팔기", "절반 정리")]
    new = [e for e in today_ev if f"{e['d']}|{e['k']}|{e.get('code')}" not in sent]
    if new and now.strftime("%Y-%m-%d") >= "2026-10-10":
        # ⑨ 알림에 「그래서 뭘 하나」 한 줄: 무엇을 · 몇 % · 손절가 (10/10 앱 업그레이드)
        def line(e):
            sk = next((k for k, v in SRC_NAME.items() if v == e.get("src")), "")
            if e["k"] == "사기":
                w = e.get("w") or SLEEVE / SLOTS * 100 * (0.5 if PROOF.get(sk, {}).get("trial") else 1)
                stp = (XR[sk].get("stop") if XR.get(sk) else STOP)
                return f"🟢 사기 {TAG.get(sk, '')}{short(e['name'])} 포트의 {w:.1f}% · " + (f"손절 {e['px'] * (1 + stp):,.4g}" if stp is not None else xr_doc(XR.get(sk)))
            if e["k"] == "절반 정리":
                return f"🟡 절반 팔기 {short(e['name'])} {e['r']:+.1f}% · 나머지는 20일선까지"
            return f"🔴 팔기 {short(e['name'])} {e['r']:+.1f}% ({e.get('why', '')})"
        msg = "\n".join(line(e) for e in new)
        try:
            urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=json.dumps({
                "topic": "chkchp-ch-kick", "title": f"⚡ 킥 {len(new)}건 — 오늘 할 일", "message": msg[:400],
                "click": "https://chkchp0702-spec.github.io/daily-app/#port~pokick", "tags": ["zap"]}).encode(),
                headers={"Content-Type": "application/json"}), timeout=15).read()
        except Exception as e:
            print("알림 실패", e)
    for e in today_ev:
        sent.add(f"{e['d']}|{e['k']}|{e.get('code')}")
    C["sent"] = sorted(sent)[-200:]
    CANDS.write_text(json.dumps(C, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"기본 {out['stat']['base']:+.2f}% · 킥 {out['stat']['kick']:+.2f}% · 슬리브 {out['sleeve']:+.2f}% · 거래 {len(trades)} · 들고 있는 것 {len(pos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
