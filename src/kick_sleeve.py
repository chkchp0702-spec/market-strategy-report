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
SRC_NAME = {"focus": "🎯 집중 돌파", "cup_eye": "☕ 컵 돌파(눈 검사 통과)", "cup": "☕ 컵 돌파", "gap": "📈 돌파 갭",
            "lead": "🔗 미국→한국 선행", "accum": "🤫 매집 박스 돌파", "whale": "🐋 고래 큰손 매수"}


# ✅ 성과가 확인된 신호만 킥에 들어온다 (10/10 사용자: "고래·컵·갭·조용한 매집이 성과 확인된 것만 자연스럽게, 킥 포트는 하나만")
#    기준: 우리 장부(market/edge.json)에서 표본 20건 이상 · 손익비 1.5 이상. 고래는 13F 바스켓 검증(매 분기 S&P 이김).
#    아직 아닌 신호는 「⏳ 대기」— 표본이 차면 다음 계산부터 저절로 들어온다. 🎯 집중·🔗 선행은 사용자 목록 밖이라 넣지 않는다.
TAG = {"cup_eye": "☕", "cup": "☕", "gap": "📈", "accum": "🤫", "whale": "🐋", "focus": "🎯", "lead": "🔗"}
KICK_SRCS = ["cup_eye", "cup", "gap", "accum", "whale"]
PROOF_N, PROOF_PF = 20, 1.5


def proof():
    """신호별 성과 확인 — {src: {n, pf, avg, on, why}}"""
    try:
        E = json.loads((ROOT / "market" / "edge.json").read_text(encoding="utf-8"))
    except Exception:
        E = {}
    g = lambda *ks: (lambda d: d if isinstance(d, dict) else {})(__import__("functools").reduce(lambda a, k: (a or {}).get(k) if isinstance(a, dict) else None, ks, E))
    st = {"cup": g("cup", "brk_now"), "gap": g("gap", "돌파_by_size", "4-8%"), "accum": g("accum", "brk")}
    out = {}
    for k, v in st.items():
        n, pf = v.get("n") or 0, v.get("pf") or 0
        on = n >= PROOF_N and pf >= PROOF_PF
        out[k] = {"n": n, "pf": round(pf, 2) if pf < 100 else None, "avg": v.get("avg"), "on": on,
                  "why": (f"확인됨 — {n}건 · 평균 {v.get('avg'):+.1f}% · 손익비 {pf:.1f}" if on else f"⏳ 대기 — 돌파 표본 {n}/{PROOF_N}건" + (f" · 손익비 {pf:.1f}" if n and pf < 100 else ""))}
    out["cup_eye"] = out["cup"]
    out["whale"] = {"n": 160, "pf": None, "avg": None, "on": True, "why": "확인됨 — 13F 큰 신규 바스켓이 매 분기 S&P 이김(3개월 4/4 +3.9%p · 6개월 3/3 +10.0%p)"}
    for k in ("focus", "lead"):
        out[k] = {"n": 0, "on": False, "why": "킥 대상 아님(사용자 목록: 고래·컵·갭·매집)"}
    return out


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


def main() -> int:
    now = dt.datetime.now(KST)
    P = json.loads(PORT.read_text(encoding="utf-8"))
    START = P["start"]
    C = collect(now)
    PROOF = proof()
    cands = [v for v in C["cands"].values() if v["d"] >= START and v["src"] not in OFF and v["src"] in KICK_SRCS and PROOF.get(v["src"], {}).get("on")]
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
    tick = sorted({c["code"] for c in cands} | {"SGOV", "SPY"} | {r["t"] for _, _, rows in WL for r in rows[:WN * 2]})
    start = (dt.date.fromisoformat(START) - dt.timedelta(days=45)).isoformat()
    df = yf.download(tick, start=start, interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    CL = {}
    for t in tick:
        try:
            s = df[t]["Close"].dropna()
            if len(s):
                CL[t] = s
        except Exception:
            pass
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

    # 신호 날짜 → 그 날 또는 다음 미국 거래일로 묶음
    by_day = {}
    for c in cands:
        if c["code"] not in CL:
            continue
        sd = c["d"]
        own = CL[c["code"]]
        if not len(own[own.index.strftime("%Y-%m-%d") == sd]):
            continue                                 # 그 날 종가가 없으면(휴장 등) 건너뜀
        tgt = next((x for x in D if x >= sd), None)
        if tgt:
            pr = PRI.get(c["src"], 0) + c["score"] + (_P["whale_bonus"] if c["code"] in whale else 0) + (ADAPT.get(c["src"], {}).get("adj", 0))
            by_day.setdefault(tgt, []).append({**c, "pr": round(pr, 1), "whale": c["code"] in whale})

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
            if r <= STOP:
                why = "손절 −5%"
            elif _P.get("gap_fill_exit") and p["src"] == "gap" and p.get("lv") and c < p["lv"]:
                why = "갭 메움 (메운 갭은 평균 −1.3%)"
            elif not p["half"] and r >= TAKE:
                cash += p["sh"] / 2 * c
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
                cash += p["sh"] * c
                rr = (p["realized"] + (c / p["entry"] - 1) * (p["cost"] / 2 if p["half"] else p["cost"])) / p["cost"]
                closed.append({**{k: p[k] for k in ("code", "name", "src", "d0", "entry", "mkt")}, "d1": d, "exit": round(c, 4), "r": round(rr * 100, 2),
                               "days": p["held"], "why": why})
                events.append({"d": d, "k": "팔기", "code": p["code"], "name": p["name"], "r": round(rr * 100, 1), "why": why})
                last_exit[p["code"]] = i
                pos.remove(p)
        total = cash + sum(p["sh"] * (px(p["code"], d) or p["entry"]) for p in pos)
        peak = max(peak, total)
        if total - 1 <= BRAKE and pause_until < i:
            pause_until = i + BRAKE_D
            events.append({"d": d, "k": "브레이크", "why": f"슬리브 {round((total - 1) * 100, 1)}% → {BRAKE_D}거래일 새 진입 멈춤"})
        # 새로 들어가기
        if i > pause_until:
            free = SLOTS - len(pos)
            held = {p["code"] for p in pos}
            pick = []
            for c in sorted(by_day.get(d, []), key=lambda x: -x["pr"]):
                if len(pick) >= min(free, MAX_NEW):
                    break
                if c["code"] in held or c["code"] in {x["code"] for x in pick}:
                    continue
                if c["code"] in last_exit and i - last_exit[c["code"]] < REENTRY:
                    continue
                pick.append(c)
            for c in pick:
                e = px(c["code"], c["d"]) or px(c["code"], d)
                if not e:
                    continue
                cost = total / SLOTS
                if cost > cash:
                    cost = cash
                if cost <= 0:
                    break
                cash -= cost
                pos.append({"code": c["code"], "name": c["name"], "mkt": c.get("mkt"), "src": c["src"], "d0": d, "entry": e, "sh": cost / e, "cost": cost, "lv": c.get("lv"),
                            "held": 0, "max": e, "last": e, "half": False, "realized": 0.0, "pr": c["pr"], "whale": c.get("whale")})
                events.append({"d": d, "k": "사기", "code": c["code"], "name": c["name"], "src": SRC_NAME.get(c["src"], c["src"]), "px": round(e, 4), "note": c.get("note")})
        total = cash + sum(p["sh"] * (px(p["code"], d) or p["entry"]) for p in pos)
        if i > 0:
            val.append(total)
        else:
            val[0] = total

    # 🐋 고래 바스켓 — 분기마다 같은 비중으로 사서 다음 목록까지 들고 감 (−30% 사고 대비만)
    wval, wbask, wq, wev = [1.0], [], None, []
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

    # 기본 포트 vs 킥 포트 (같은 날짜 줄)
    pdates, pnav = P["dates"], P["nav"]
    base = [1 + v / 100 for v in pnav]
    sv = dict(zip(D, val))
    sg = {d: px("SGOV", d) for d in pdates}
    kick = [1.0]
    sleeve_line = [0.0]
    lastv = 1.0
    for j in range(1, len(pdates)):
        d0, d1 = pdates[j - 1], pdates[j]
        rb = base[j] / base[j - 1] - 1
        rs = (sv.get(d1, sv.get(d0, 1.0)) / sv.get(d0, 1.0) - 1) if d0 in sv else (sv.get(d1, 1.0) - 1)
        rg = (sg[d1] / sg[d0] - 1) if sg.get(d0) and sg.get(d1) else 0
        rw = (wsv.get(d1, wsv.get(d0, 1.0)) / wsv.get(d0, 1.0) - 1) if d0 in wsv else 0.0
        kick.append(kick[-1] * (1 + rb - (SLEEVE + WS) * rg + SLEEVE * rs + WS * rw))
        lastv = sv.get(d1, lastv)
        sleeve_line.append(round((lastv - 1) * 100, 2))
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
                      "stop": round(p["entry"] * (1 + STOP), 4), "take": round(p["entry"] * (1 + TAKE), 4), "w": round(p["sh"] * c / val[-1] * SLEEVE * 100, 2)})
    # ⚡ 하나의 킥 포트 — 돌파로 들어온 것 + 고래 바스켓을 한 목록으로, 종목마다 어디서 왔는지 작은 이모티콘
    wset = {b["t"] for b in wbask if b["on"]}
    hold = []
    for o in openp:
        tg = TAG.get(next((k for k, v in SRC_NAME.items() if v == o["src"]), ""), "")
        tags = [tg] if tg else []
        if o["code"] in wset or o.get("whale"):
            tags.append("🐋")
        hold.append({"code": o["code"], "name": o["name"], "tags": "".join(dict.fromkeys(tags)), "w": o["w"], "r": o["r"], "d0": o["d0"], "entry": o["entry"],
                     "now": o["now"], "kind": "돌파", "rule": f"손절 {o['stop']:g} · +15% 절반", "half": o["half"]})
    for b in wbask:
        if not b["on"]:
            continue
        tags = ["🐋"] + sorted(recent_sig.get(b["t"], set()) - {"🐋", "🎯", "🔗"})
        nowp = px(b["t"], last_d) or b["entry"]
        hold.append({"code": b["t"], "name": b["t"], "tags": "".join(tags), "w": round(WS * 100 / max(1, len(wbask)), 2), "r": round((nowp / b["entry"] - 1) * 100, 2),
                     "d0": b["d0"], "entry": round(b["entry"], 4), "now": round(nowp, 4), "kind": "고래", "rule": "분기 보유 · −30%만 정리",
                     "by": b["by"][:2], "half": False})
    hold.sort(key=lambda h: -h["r"])
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"), "start": START, "asof": last_d,
        "hold": hold, "proof": {k: v for k, v in PROOF.items() if k in ("whale", "cup", "gap", "accum")},
        "tags": {"🐋": "고래 13F 큰 신규", "☕": "컵 돌파", "📈": "돌파 갭", "🤫": "조용한 매집 돌파"},
        "dates": pdates, "base": [round((b - 1) * 100, 2) for b in base], "kick": [round((k - 1) * 100, 2) for k in kick],
        "sleeve": round((val[-1] - 1) * 100, 2), "sleeve_line": sleeve_line,
        "open": openp, "closed": trades[::-1][:40], "closed_all": [{"src": t["src"], "r": t["r"], "d1": t["d1"]} for t in trades], "events": events[::-1][:40],
        "stat": {"base": round((base[-1] - 1) * 100, 2), "kick": round((kick[-1] - 1) * 100, 2), "spy": P["stat"]["spy"], "whale": round((wval[-1] - 1) * 100, 2) if WS > 0 else None,
                 "trades": len(trades), "win": round(len(wins) / len(trades) * 100) if trades else None,
                 "avg_win": avg(wins), "avg_loss": avg(loss), "avg": avg(trades), "slots": f"{len(pos)}/{SLOTS}",
                 "paused": pause_until >= len(D) - 1},
        "rules": {"sleeve": SLEEVE, "slots": SLOTS, "stop": STOP, "take": TAKE, "time": TIME_D, "brake": BRAKE, "off": sorted(OFF), "whale_sleeve": WS, "whale_n": WN},
        "whale": {"q": wq, "ret": round((wval[-1] - 1) * 100, 2), "line": [round((wsv.get(x, 1.0) - 1) * 100, 2) for x in pdates], "sleeve": WS,
                  "rows": [{"t": b["t"], "n": b["n"], "w13f": b["w"], "by": b["by"], "d0": b["d0"], "entry": round(b["entry"], 4),
                            "now": round(px(b["t"], last_d) or b["entry"], 4), "r": round(((b["exit"] if not b["on"] else (px(b["t"], last_d) or b["entry"])) / b["entry"] - 1) * 100, 2),
                            "on": b["on"], "w": round(WS * 100 / max(1, len(wbask)), 2)} for b in wbask],
                  "events": wev[::-1][:10],
                  "why": "13F 큰 신규 포지션 같은 비중 바스켓은 바이오 펀드를 빼면 매 분기 S&P 를 이김(1개월 5/5 +2.8%p · 3개월 4/4 +3.9%p · 6개월 3/3 +10.0%p, 2025Q2~2026Q2). 하나씩은 반반이라 바스켓으로만, 큰 승자를 자르지 않게 분기 동안 들고 감."} if WS > 0 else None,
        "by_src": {SRC_NAME.get(k, k): v for k, v in ADAPT.items()},
        "src_names": SRC_NAME,
        "note": f"⚡ 킥 포트 = 기본 포트에서 현금 {round((SLEEVE + WS) * 100)}%p 를 떼어 「성과가 확인된 신호」(🐋 고래 · ☕ 컵 · 📈 갭 · 🤫 매집 — 표본 20건↑·손익비 1.5↑)에만 담은 것. "
                f"☕📈🤫 돌파는 확인된 순간 {round(SLEEVE / SLOTS * 100, 1)}%씩(−5% 손절 · +15% 절반 익절), 🐋 고래는 13F 큰 신규를 같은 비중으로 분기 동안(−30%만 정리). "
                "아직 확인 안 된 신호는 표본이 차면 저절로 들어온다. 10/9 이전은 같은 규칙으로 되짚은 계산. 현지 통화 기준·수수료 제외. 매수 추천 아님.",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 오늘 새로 사고판 것 알림 (한 번만)
    sent = set(C.get("sent", []))
    today_ev = [e for e in events if e["d"] == last_d and e["k"] in ("사기", "팔기", "절반 정리")]
    new = [e for e in today_ev if f"{e['d']}|{e['k']}|{e.get('code')}" not in sent]
    if new and now.strftime("%Y-%m-%d") >= "2026-10-10":
        msg = " · ".join(f"{e['k']} {e['name']}" + (f" {e['r']:+.1f}%" if e.get("r") is not None else "") for e in new)
        try:
            urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=json.dumps({
                "topic": "chkchp-ch-kick", "title": "⚡ 킥 슬리브", "message": msg[:300],
                "click": "https://chkchp0702-spec.github.io/daily-app/#port", "tags": ["zap"]}).encode(),
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
