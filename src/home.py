"""🏠 앱 홈 · 📊 성적표 · 🏷 종목 신호 색인 — 한 번에 만들어 앱이 파일 하나만 받게 (10/10 앱 업그레이드 ①③⑦⑧)

  market/home.json     : 첫 화면 「오늘 할 일」 — 포트 성적·킥 매매·집중·두뇌·단타 한 장
  market/scores.json   : 판단 채점을 한 곳에 — 리포트 예고 · 두뇌 선제 · 킥 신호별 · 단타 유형별 · 해외 상품 · 집중 · 포트 vs 시장 · 고래
  market/sigindex.json : 종목 → 어느 신호에 걸렸나(🐋☕📈🤫🎯) · 포트·킥에 들어 있나 — 종목 화면 배지

  fetch.yml 이 매시간 port.py · kick_sleeve.py 다음에 돌린다. 자가 업그레이드·건강검진도 scores.json 을 근거로 쓴다.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "market"
RAW_SS = "https://raw.githubusercontent.com/chkchp0702-spec/stock-screener/main/"
KN = {"cup": "컵 돌파", "gap": "돌파 갭", "accum": "매집", "whale": "고래", "focus": "집중", "lead": "선행", "nh52": "신고가", "pead": "실적 표류", "dip": "급락 반등", "trend": "추세", "earn": "실적 갭",
      "cust": "고객사 따라", "ins": "내부자 매수", "maxcut": "복권 거름망", "frog": "개구리 갭", "agree": "신호 겹침", "nonews": "뉴스 없는 급등", "pbskip": "눌림 건너뜀"}
TAG = {"cup_eye": "☕", "cup": "☕", "gap": "📈", "accum": "🤫", "whale": "🐋", "focus": "🎯", "lead": "🔗", "nh52": "🏔", "pead": "📊", "dip": "🩹", "trend": "🧭", "earn": "📊",
       "cust": "🔌", "ins": "🕵", "maxcut": "🎰", "frog": "🐸", "agree": "🤝", "nonews": "📰", "pbskip": "🪂"}


def rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d if d is not None else {}


def web(url, t=30):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ch-home"}), timeout=t) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        print("받기 실패", url, e)
        return None


def norm(code: str) -> str:
    """종목 코드 맞추기: 005930.KS → 005930, 5985.T → 5985.T(그대로), sjm → SJM"""
    c = str(code or "").strip().upper()
    if c.endswith((".KS", ".KQ")) and c[:6].isdigit():
        return c[:6]
    return c


def main() -> int:
    now = dt.datetime.now(KST)
    P, K, F = rj(M / "port.json"), rj(M / "kick.json"), rj(M / "focus.json")
    CN = rj(M / "conc.json")        # 🎯 집중 포트 (10/11)
    B, BS, L = rj(ROOT / "brain" / "state.json"), rj(M / "bets_score.json"), rj(ROOT / "ledger" / "ledger.json")
    KC = rj(M / "kick_cands.json")
    LR = json.loads(web(RAW_SS + "data/learned.json") or "{}")
    tr = web(RAW_SS + "data/tracking.csv") or ""

    # ── 💼 포트 ──
    bm = [m for m in P.get("bench_meta", []) if m.get("ok")]
    base, kick = P.get("stat", {}).get("ret"), (K.get("stat") or {}).get("kick")
    daily = P.get("daily", [])
    last = daily[-1] if daily else {}
    kd = K.get("kick", [])
    port = {
        "base": base, "kick": kick, "spy": P.get("stat", {}).get("spy"), "start": P.get("start"), "asof": P.get("asof"),
        "d1": last.get("r"), "d1_spy": last.get("spy"), "d1_date": last.get("d"),
        "d1_kick": round(((1 + kd[-1] / 100) / (1 + kd[-2] / 100) - 1) * 100, 2) if len(kd) > 1 else None,
        "beat_base": sum(1 for m in bm if base is not None and base >= m["ret"]), "beat_kick": sum(1 for m in bm if kick is not None and kick >= m["ret"]),
        "base_honest": (P.get("stat") or {}).get("base_honest"), "kick_honest": (K.get("honest") or {}).get("ret"),   # 🧾 정직(다음 날 진입·비용·주간 리밸런싱)
        "n_bench": len(bm), "nav": P.get("nav", [])[-30:], "kick_line": kd[-30:], "spy_line": (P.get("bench", {}).get("S&P500") or [])[-30:],
        "change": (P.get("changes") or [{}])[0] if (P.get("changes") or [{}])[0].get("date", "") >= (now - dt.timedelta(days=3)).strftime("%Y-%m-%d") else None,
        "weak": [h["name"] for h in P.get("hold", []) if str(h.get("sig", "")).startswith("약함")],
        "strong": [h["name"] for h in P.get("hold", []) if str(h.get("sig", "")).startswith("강함")],
        "conc": CN.get("ret"), "conc_line": (CN.get("nav") or [])[-30:], "conc_d1": CN.get("d1"),
        "conc_up": (CN.get("regime") or {}).get("up"), "conc_gap": (CN.get("regime") or {}).get("gap"),
        "conc_now": [{"name": x.get("name"), "pct": x.get("pct")} for x in (CN.get("now") or [])],
        "beat_conc": sum(1 for m in bm if CN.get("ret") is not None and CN["ret"] >= m["ret"]),
    }
    # ── ⚡ 킥 오늘(마지막 거래일) 사고판 것 ──
    asof = K.get("asof")
    kev = [e for e in K.get("events", []) if e.get("d") == asof and e.get("k") in ("사기", "팔기", "절반 정리")]
    hold = K.get("hold", [])
    kick_h = {"asof": asof, "events": kev[:6], "n": len(hold), "w": round(sum(h.get("w") or 0 for h in hold), 1),
              "best": sorted(hold, key=lambda h: -(h.get("r") or 0))[:3], "worst": sorted(hold, key=lambda h: (h.get("r") or 0))[:1]}
    # ── 🎯 집중 ──
    foc = []
    for t in (F.get("themes") or [])[:2]:
        stars = [s for s in (t.get("us") or []) + (t.get("kr") or []) if "★" in str(s.get("act", ""))][:3]
        foc.append({"sym": t.get("sym"), "name": t.get("name"), "stage": (t.get("stage") or {}).get("s"), "do": (t.get("stage") or {}).get("do"),
                    "r5": t.get("r5"), "rs20": t.get("rs20"), "stars": [{"t": s.get("t"), "name": s.get("name"), "act": s.get("act")} for s in stars],
                    "etf_kr": [{"t": x.get("t"), "name": x.get("name")} for x in (t.get("etf_kr") or [])[:1]]})
    # ── ⚡ 단타 ──
    today = now.strftime("%Y%m%d")
    rows = [l for l in tr.splitlines()[1:] if l.startswith(today)]
    strong = [f"{k} {s}" for k, v in (LR.get("types") or {}).items() for s, r in (v.get("slots") or {}).items() if r.get("st") == "강함"]
    danta = {"today": len(rows), "strong": strong, "observe": [k for k, v in (LR.get("types") or {}).items()
                                                               if all(r.get("st") in ("관찰", "닫힘") for r in (v.get("slots") or {}).values())]}
    home = {"at": now.strftime("%Y-%m-%d %H:%M"), "port": port, "kick": kick_h, "focus": foc,
            "brain": {"summary": B.get("summary"), "regime": B.get("regime"), "at": B.get("last_review"),
                      "open": sum(1 for b in B.get("bets", []) if b.get("status") == "열림"),
                      "ideas": [f"{x.get('칸') or x.get('box', '')} {x.get('제안') or x.get('idea', '')}".strip() for x in
                                sorted(B.get("port_ideas") or [], key=lambda x: str(x.get("제안", "")).startswith("유지"))[:3] if isinstance(x, dict)]},
            "danta": danta}

    # ── 📊 성적표 ──
    sc = L.get("scorecard", [])
    cnt = {}
    for r in sc:
        cnt[r.get("verdict", "?")] = cnt.get(r.get("verdict", "?"), 0) + 1
    graded = cnt.get("맞음", 0) + cnt.get("틀림", 0)
    S = []
    S.append({"k": "report", "ic": "🌐", "t": "시황리포트 예고·킥", "n": len(sc), "win": cnt.get("맞음", 0), "loss": cnt.get("틀림", 0),
              "rate": round(cnt.get("맞음", 0) / graded * 100) if graded else None, "note": " · ".join(f"{k} {v}" for k, v in cnt.items()),
              "recent": [{"d": r.get("date"), "t": r.get("wrote"), "v": r.get("verdict")} for r in sc[-4:]][::-1]})
    # 🎯 확률 채점 (10/11 규칙 ⑥): 예고마다 적은 확률이 맞았나 + 분야별 — 「잘 맞히는 분야 · 확률 65%↑」일 때만 비중을 바꾼다 (RULES 1-J)
    try:
        from src.scoring import calibration_stats
        cs_ = calibration_stats(L)
        CAT = [("금리", ("금리", "10년", "CPI", "연준", "국채")), ("수급", ("외국인", "기관", "순매수")), ("유가·원자재", ("브렌트", "유가", "WTI", "금 ")),
               ("지수", ("코스피", "S&P", "나스닥", "지수")), ("업종·종목", ("ETF", "반도체", "SW", "CIBR", "418670", "업종"))]
        bycat = {}
        for c in [x for x in L.get("calibration", []) if x.get("outcome") is not None]:
            k = next((nm for nm, kws in CAT if any(w in (c.get("text") or "") for w in kws)), "기타")
            b_ = bycat.setdefault(k, {"n": 0, "hit": 0, "bs": 0.0})
            b_["n"] += 1; b_["hit"] += c["outcome"]; b_["bs"] += (c["p"] - c["outcome"]) ** 2
        cats = [{"k": k, "n": v["n"], "rate": round(v["hit"] / v["n"] * 100), "brier": round(v["bs"] / v["n"], 2),
                 "ok": v["n"] >= 5 and v["bs"] / v["n"] <= 0.2} for k, v in sorted(bycat.items(), key=lambda kv: -kv[1]["n"])]
        S[-1]["cal"] = {"n": cs_.get("n"), "brier": cs_.get("brier"), "tone": cs_.get("tone"), "buckets": cs_.get("buckets"), "cats": cats,
                        "gate": "비중 변경은 확률 65%↑ + 그 분야 채점 5건↑·브라이어 0.20↓일 때만 (아직 아니면 「검토」로만 적음)"}
    except Exception as e_:
        print("확률 채점 실패", e_)
    bsum = BS.get("sum") or {}
    bw, bl = bsum.get("win", 0), bsum.get("loss", 0)
    S.append({"k": "bets", "ic": "🧠", "t": "두뇌 선제 아이디어", "n": bw + bl, "win": bw, "loss": bl, "rate": round(bw / (bw + bl) * 100) if bw + bl else None,
              "avg": bsum.get("avg"), "note": f"채점 중 {bsum.get('live', 0)}개 · 끝난 것 {bsum.get('closed', 0)}개"})
    ks = K.get("stat") or {}
    sig = []
    for k, v in (K.get("proof") or {}).items():
        h_ = v.get("honest") or {}
        sig.append({"k": k, "tag": TAG.get(k, ""), "on": v.get("on"), "trial": v.get("trial"), "n": v.get("n"), "pf": v.get("pf"), "avg": v.get("avg"), "why": v.get("why"),
                    "h_n": h_.get("n"), "h_avg": h_.get("avg"), "h_pf": h_.get("pf"), "h_basis": h_.get("basis"),
                    "h_oos": h_.get("oos"), "h_insample": h_.get("insample"), "fixed": v.get("fixed"), "why_note": v.get("why_note")})
    for k, v in (K.get("shadow_stat") or {}).items():
        sig.append({"k": k, "tag": v.get("tag", TAG.get(k, "")), "shadow": True, "n": v.get("n"), "pf": v.get("pf"), "avg": v.get("avg"), "win": v.get("win")})
    S.append({"k": "kick", "ic": "⚡", "t": "킥 — 신호별", "n": ks.get("trades"), "win": None, "rate": ks.get("win"), "avg": ks.get("avg"),
              "note": f"킥 {ks.get('kick', 0):+.2f}% vs 기본 {ks.get('base', 0):+.2f}% · S&P {ks.get('spy', 0):+.2f}%", "sig": sig,
              "honest_ret": (K.get("honest") or {}).get("ret"), "honest_note": (K.get("honest") or {}).get("note")})
    dt_ = []
    for k, v in (LR.get("types") or {}).items():
        dt_.append({"k": k, "n": v.get("n_all"), "avg": v.get("avg_all"), "slots": {s: {"st": r.get("st"), "n": r.get("n"), "avg": r.get("avg")} for s, r in (v.get("slots") or {}).items()}})
    if False:   # 10/10 사용자: 「단타는 성적표에서 빼고」 — 단타 성적은 ⚡ 단타 탭의 🧪 표에만
      S.append({"k": "danta", "ic": "🧪", "t": "단타 — 유형별", "n": sum(x["n"] or 0 for x in dt_), "rows": dt_, "note": f"쌓인 1분 자료 {LR.get('n_days', 0)}일 + 실제 알람 · 비용 0.3% 뺌"})
    pv = [{"name": h["name"], "picks": h.get("picks"), **(h.get("pick_vs") or {})} for h in P.get("hold", []) if h.get("pick_vs")]
    pw = [x for x in pv if x.get("edge") is not None]
    S.append({"k": "picks", "ic": "🌏", "t": "해외 상품 vs 원래 미국 상품", "n": len(pw), "win": sum(1 for x in pw if x["edge"] >= 0), "loss": sum(1 for x in pw if x["edge"] < 0),
              "rows": pv, "note": "고른 날부터 · 달러 기준" if pw else "고른 날 다음 거래일부터 채점"})
    fs = F.get("score") or {}
    S.append({"k": "focus", "ic": "🎯", "t": "오늘의 집중 테마", "n": fs.get("n"), "win": fs.get("hit"), "avg": fs.get("avg_ex"),
              "rate": round(fs["hit"] / fs["n"] * 100) if fs.get("n") else None, "note": f"채점 중 {len(fs.get('open') or [])}개 (S&P 대비 5일)"})
    S.append({"k": "port", "ic": "💼", "t": "포트 vs 시장", "n": port["n_bench"], "win": port["beat_kick"], "loss": port["n_bench"] - port["beat_kick"],
              "note": f"⚡ 킥 {kick or 0:+.2f}%는 시장 {port['n_bench']}곳 중 {port['beat_kick']}곳, 💼 기본 {base or 0:+.2f}%는 {port['beat_base']}곳보다 앞섬"})
    W = K.get("whale") or {}
    if W:
        S.append({"k": "whale", "ic": "🐋", "t": "고래 바스켓", "avg": W.get("ret"), "note": f"{W.get('q')} 13F 큰 신규 {len(W.get('rows') or [])}종목 · S&P {ks.get('spy', 0):+.2f}%"})
    # 이기는 것 · 지는 것 한 줄
    good, bad, seen_ = [], [], set()
    for x in sig:
        if x["k"] in seen_:      # 10/14: 같은 신호가 확인·그림자 두 번 나오면 한 번만
            continue
        seen_.add(x["k"])
        # 10/14 🔧: 비용 뺀 정직 채점(다음 날 진입·왕복 비용)이 10건↑ 있으면 그 손익비로 판정 — 비용 전 숫자만 보고 「이기는 것」에 넣지 않음
        tag_ = x.get("tag") or TAG.get(x["k"], "")
        nm_ = f"{tag_} {KN.get(x['k'], x['k'])}".strip()
        if (x.get("h_n") or 0) >= 10 and x.get("h_pf") is not None:
            pf_ = x["h_pf"]
            txt = f"{nm_} 손익비 {pf_} (비용 뺀 {x['h_n']}건" + (f" · 비용 전 {x['pf']}" if x.get("pf") and abs(x["pf"] - pf_) >= 0.3 else "") + ")"
        elif (x.get("n") or 0) >= 10 and x.get("pf"):
            pf_, txt = x["pf"], f"{nm_} 손익비 {x['pf']}"
        else:
            continue
        (good if pf_ >= 1.5 else bad if pf_ < 1 else []).append(txt)
    # 단타는 성적표에서 뺌 (10/10 사용자)
    scores = {"at": home["at"], "rows": S, "good": good[:6], "bad": bad[:6]}
    home["scores"] = {"good": good[:3], "bad": bad[:3]}

    # ── 10/13 「더 자주 열게」: ⑥ 어제 예고 → 오늘 결과 · ⑦ 이번 주 복기 · ③ 어제보다 바뀐 것 ──
    try:
        extra(home, now, P, K, CN, F, B, L, S)
    except Exception as e_:
        print("홈 추가 실패", e_)

    # ── 🏷 종목 신호 색인 ──
    ix = {}

    def add(code, tag=None, **kw):
        c = norm(code)
        if not c:
            return
        e = ix.setdefault(c, {"tags": ""})
        if tag and tag not in e["tags"]:
            e["tags"] += tag
        e.update({k: v for k, v in kw.items() if v is not None})
    cut = (now - dt.timedelta(days=30)).strftime("%Y-%m-%d")
    for v in (KC.get("cands") or {}).values():
        if v.get("d", "") >= cut and v.get("src") in TAG:
            add(v["code"], TAG[v["src"]], last=v.get("d"))
    for t in KC.get("whale") or []:
        add(t, "🐋")
    for b in (W.get("rows") or []):
        add(b["t"], "🐋")
    for h in hold:
        add(h["code"], None, kick=h.get("w"), kick_r=h.get("r"))
    for h in P.get("hold", []):
        for u in h.get("us") or []:
            add(u["t"], None, port=h["name"])
    for t in F.get("themes") or []:
        for s in (t.get("us") or []) + (t.get("kr") or []):
            if "★" in str(s.get("act", "")):
                add(s.get("t"), "🎯", focus=t.get("name"))
    for b in B.get("bets", []):
        if b.get("status") == "열림" and b.get("t"):
            add(b["t"], "🧠", bet=f"{b.get('dir')} {b.get('target')}")

    for name, obj in (("home.json", home), ("scores.json", scores), ("sigindex.json", {"at": home["at"], "ix": ix})):
        (M / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"홈 · 성적표 {len(S)}줄 · 신호 색인 {len(ix)}종목 · 단타 오늘 {len(rows)}건")
    return 0


def _txt(x, n=90):
    import re
    t = re.sub(r"<[^>]+>", "", str(x or "")).replace("&amp;", "&").strip()
    return t if len(t) <= n else t[:n - 1] + "…"


# 10/15 A9-5 🧵 예고 실타래 — 같은 주제가 며칠째 나오고 맞았나 (글자 열쇠: 아는 낱말 표 → 없으면 날짜 뗀 앞 낱말 2개)
_TOPIC = [("외국인", "외국인 순매수"), ("10년", "미 10년 금리"), ("CPI", "미 물가(CPI)"), ("SMH", "반도체(SMH)"), ("반도체", "반도체(SMH)"),
          ("CIBR", "사이버보안"), ("사이버보안", "사이버보안"), ("418670", "사이버보안"), ("브렌트", "유가"), ("WTI", "유가"),
          ("KBE", "은행"), ("은행", "은행"), ("XLE", "에너지"), ("에너지", "에너지"), ("삼성", "삼성 실적"), ("코스피", "코스피 지수")]


def _topic(t):
    import re
    t = _txt(t, 200).replace("어제 예고 ", "")
    t = re.sub(r"^[①②③④⑤]\s*", "", t)
    for k, v in _TOPIC:
        if k in t:
            return v
    t = re.sub(r"^\d{1,2}/\d{1,2}\s*(\([^)]*\))?\s*(밤\s*)?", "", t)
    return " ".join(t.split()[:2]) or None


def _grade_hist(fs):
    """리포트 data 파일들의 yesterday_grades(맞음/틀림만) → [{d: 채점한 리포트 날짜, k: 주제, m: ok|no}] 시간 순"""
    out, seen = [], set()
    for f in fs:
        D = rj(f) or {}
        for g in (D.get("yesterday_grades") or [])[:3]:
            if g.get("cls") not in ("ok", "no"):
                continue
            k = _topic(g.get("title"))
            key = (D.get("date"), k)
            if not k or key in seen:
                continue
            seen.add(key)
            out.append({"d": D.get("date"), "k": k, "m": g["cls"]})
    return out


def _trail(H, k, n=5):
    return [{"d": x["d"], "m": x["m"]} for x in H if x["k"] == k][-n:]


def _wk(dates, nav, start):
    """누적 수익(%) 줄에서 start 날짜 이후(포함) 주간 수익 — 시작 전날 값을 기준으로"""
    idx = [i for i, d in enumerate(dates) if d >= start]
    if not idx or not nav:
        return None
    i0 = idx[0]
    a = 1 + (nav[i0 - 1] if i0 > 0 else 0) / 100
    b = 1 + nav[-1] / 100
    return round((b / a - 1) * 100, 2)


# 🗣 10/19 A10/19-3 「엇갈린 날, 누가 맞았나」 — 앱 안 코스피 방향 의견 셋(🎲 시장확률 · 🧠 두뇌 국면 · 💭 지금 생각 열쇠)을
#   장 시작 무렵(08:30~15:00 첫 실행)에 한 번 적어 두고, 그날 코스피 종가(daily-app prob.json KR.base_date·chg)가 나오면 각각 채점.
#   규칙: 오름 = 종가 +, 내림 = 종가 −, 중립 = ±0.5% 안. 💭 는 state.json 에 kr_today(오름/내림/중립) 열쇠를 적어 준 날만(글을 억지로 안 읽음).
#   기록: market/voices.json (60일). 숫자는 지어내지 않음 — 결과가 안 난 날은 세지 않음.
_VDIR = {"오름": "up", "상승": "up", "up": "up", "내림": "down", "하락": "down", "down": "down", "중립": "flat", "보합": "flat", "반반": "flat", "flat": "flat"}


def _vdir(t):
    t = str(t or "").strip()
    if not t:
        return None
    if t in _VDIR:
        return _VDIR[t]
    if "오를" in t or "오름" in t or "상승" in t or "선호" in t or "공격" in t:
        return "up"
    if "내릴" in t or "내림" in t or "하락" in t or "회피" in t or "수비" in t:
        return "down"
    if "반반" in t or "중립" in t or "보합" in t:
        return "flat"
    return None


def _vok(d, chg):
    if d is None or chg is None:
        return None
    return chg > 0 if d == "up" else chg < 0 if d == "down" else abs(chg) <= 0.5


def _voices(now, B):
    import re
    PR = json.loads(web("https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/archive/x/prob.json", 20) or "{}")
    kr = ((PR.get("markets") or {}).get("KR") or {})
    vf = M / "voices.json"
    V = rj(vf, {"days": {}})
    days = V.setdefault("days", {})
    today, hm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
    if now.weekday() < 5 and "08:30" <= hm <= "15:00" and not (days.get(today) or {}).get("v"):
        v = {}
        if kr.get("next_day") == today and kr.get("p1") is not None:
            v["dice"] = {"d": _vdir(kr.get("tone1")) or ("up" if kr["p1"] >= 0.55 else "down" if kr["p1"] <= 0.45 else "flat"), "t": kr.get("tone1") or "", "p": round(float(kr["p1"]), 3)}
        if _vdir(B.get("regime")):
            v["brain"] = {"d": _vdir(B.get("regime")), "t": B.get("regime")}
        if _vdir(B.get("kr_today")):
            v["think"] = {"d": _vdir(B.get("kr_today")), "t": B.get("kr_today"), "at": B.get("last_review")}
        if v:
            days[today] = {"v": v, "at": hm}
    # 채점: 그날 종가가 나온 날 (prob.json KR.base_date == 그날 · chg = 그날 등락)
    bd, chg = kr.get("base_date"), kr.get("chg")
    for d, row in days.items():
        if row.get("v") and row.get("r") is None and bd == d and chg is not None:
            row["r"] = {"chg": round(float(chg), 2)}
    V["days"] = dict(sorted(days.items())[-60:])
    vf.write_text(json.dumps(V, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    out = {}
    for k in ("dice", "brain", "think"):
        rows = [(x["v"][k]["d"], x["r"]["chg"], d) for d, x in sorted(V["days"].items()) if x.get("v", {}).get(k) and x.get("r") and x["r"].get("chg") is not None]
        oks = [_vok(a, c) for a, c, _ in rows]
        out[k] = {"n": len(oks), "win": sum(1 for o in oks if o), "last10": [{"d": d, "m": "ok" if o else "no"} for (_, _, d), o in zip(rows[-10:], oks[-10:])]}
    ch = [(x, d) for d, x in sorted(V["days"].items()) if x.get("r") and x["r"].get("chg") is not None and len(x.get("v") or {}) >= 2 and len({y["d"] for y in x["v"].values()}) == 1]
    out["chorus"] = {"n": len(ch), "win": sum(1 for x, _ in ch if _vok(list(x["v"].values())[0]["d"], x["r"]["chg"])),
                     "last10": [{"d": d, "m": "ok" if _vok(list(x["v"].values())[0]["d"], x["r"]["chg"]) else "no"} for x, d in ch[-10:]]}
    t = days.get(today) or {}
    out["today"] = {"d": today, "at": t.get("at"), "v": t.get("v") or {}, "r": t.get("r")}
    out["days"] = len([1 for x in V["days"].values() if x.get("r")])
    return out


def extra(home, now, P, K, CN, F, B, L, S):
    import glob
    # ⑥ 어제 예고 → 오늘 결과 (가장 최근 리포트 data 파일)
    fs = sorted(glob.glob(str(ROOT / "data" / "2026-*.json")) + glob.glob(str(ROOT / "data" / "2027-*.json")))
    D = rj(fs[-1]) if fs else {}
    rep = next((x for x in S if x.get("k") == "report"), {})
    if D:
        # 10/14 A9-5 🗳 「예고에 내 표 던지기」: 앱이 어제 예고 ①②③ 을 오늘 같은 번호로 채점하니, 어제 리포트 날짜(prev)와 번호로 표를 짝 맞춘다
        prev = (rj(fs[-2]) or {}).get("date") if len(fs) > 1 else None
        home["grade"] = {"date": D.get("date"), "label": D.get("edition_label"), "prev": prev,
                         "items": [{"mark": g.get("mark"), "cls": g.get("cls"), "t": _txt(g.get("title"), 40).replace("어제 예고 ", ""), "x": _txt(g.get("text"), 90),
                                    "id": f"{prev}-{i + 1}" if prev else None}
                                   for i, g in enumerate((D.get("yesterday_grades") or [])[:3])],
                         "next": [{"t": _txt(c, 70), "p": (D.get("forecasts_p") or [None] * 3)[i] if i < len(D.get("forecasts_p") or []) else None,
                                   "id": f"{D.get('date')}-{i + 1}"}
                                  for i, c in enumerate((D.get("checks") or [])[:3])],
                         "rate": rep.get("rate"), "win": rep.get("win"), "loss": rep.get("loss"),
                         "one": _txt(D.get("one_liner"), 110), "kick": _txt((D.get("kick") or {}).get("title"), 90)}
        GH = _grade_hist(fs[-40:])
        for x, g in zip(home["grade"]["items"], (D.get("yesterday_grades") or [])[:3]):
            x["k"] = _topic(g.get("title")); x["tr"] = _trail(GH, x["k"])
        for x, c in zip(home["grade"]["next"], (D.get("checks") or [])[:3]):
            x["k"] = _topic(c); x["tr"] = _trail(GH, x["k"])
        home["grade"]["last10"] = [x["m"] for x in GH[-10:]]
        try:
            home["grade"]["voices"] = _voices(now, B)      # 🗣 10/19 A10/19-3
        except Exception as ex:
            print("voices:", ex)
    # ⑦ 이번 주 복기 (월요일부터 · 미국 날짜 기준)
    mon = (now - dt.timedelta(days=now.weekday())).strftime("%Y-%m-%d")      # 이번 주 월요일 (주말이면 방금 끝난 주)
    pd_ = P.get("dates") or []
    wk = {"from": mon, "base": _wk(pd_, P.get("nav") or [], mon), "spy": _wk(pd_, (P.get("bench") or {}).get("S&P500") or [], mon),
          "kospi": _wk(pd_, (P.get("bench") or {}).get("코스피") or [], mon),
          "kick": _wk(K.get("dates") or [], K.get("kick") or [], mon) if K else None,
          "conc": _wk(CN.get("dates") or [], CN.get("nav") or [], mon) if CN else None,
          "days": len([d for d in pd_ if d >= mon])}
    sc = [r for r in (L.get("scorecard") or []) if str(r.get("date", "")) >= mon]
    wk["rep"] = {"n": len(sc), "win": sum(1 for r in sc if r.get("verdict") == "맞음"), "loss": sum(1 for r in sc if r.get("verdict") == "틀림")}
    ev = [e for e in (K.get("events") or []) if str(e.get("d", "")) >= mon and e.get("k") in ("사기", "팔기", "절반 정리")]
    wk["kick_ev"] = {"buy": sum(1 for e in ev if e["k"] == "사기"), "sell": sum(1 for e in ev if e["k"] != "사기"),
                     "best": max([e for e in ev if e.get("r") is not None], key=lambda e: e["r"], default=None)}
    if wk["kick_ev"]["best"]:
        b_ = wk["kick_ev"]["best"]; wk["kick_ev"]["best"] = {"name": b_.get("name"), "r": b_.get("r"), "code": b_.get("code")}
    wk["next"] = [{"when": _txt(x.get("when"), 20), "what": _txt(x.get("what"), 60)} for x in (D.get("schedule") or [])[:4]] if D else []
    home["week"] = wk
    # ③ 어제보다 바뀐 것 — 하루 한 번 찍어 둔 모습과 비교
    reg = None
    try:
        reg = json.loads(web("https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/archive/x/regime.json", 20) or "{}").get("label")
    except Exception:
        pass
    st = P.get("stat") or {}
    snap = {"reg": reg, "focus": [t.get("name") for t in (F.get("themes") or [])[:2]], "conc_up": (CN.get("regime") or {}).get("up"),
            "gap": round((home["port"].get("kick") or 0) - (st.get("spy") or 0), 2), "brain": B.get("regime"),
            "kick_n": home["kick"].get("n"), "chg": (P.get("changes") or [{}])[0].get("date"), "rep": D.get("date") if D else None}
    sf = M / "home_snap.json"
    SN = rj(sf, {"days": {}})
    today = now.strftime("%Y-%m-%d")
    SN["days"][today] = snap
    SN["days"] = dict(sorted(SN["days"].items())[-7:])
    prev_d = max([d for d in SN["days"] if d < today], default=None)
    pv = SN["days"].get(prev_d) or {}
    ch = []
    if pv:
        if snap["reg"] and pv.get("reg") and snap["reg"] != pv["reg"]:
            ch.append({"ic": "🧭", "t": f"미국 국면 {pv['reg']} → {snap['reg']}", "lab": "미국 국면", "a": pv["reg"], "b": snap["reg"], "go": "sector"})
        if snap["conc_up"] is not None and pv.get("conc_up") is not None and snap["conc_up"] != pv["conc_up"]:
            ch.append({"ic": "🎯", "t": "상승장 판정 " + ("🔴 → 🟢" if snap["conc_up"] else "🟢 → 🔴"), "lab": "상승장 판정",
                       "a": "🟢 상승장" if pv["conc_up"] else "🔴 아님", "b": "🟢 상승장" if snap["conc_up"] else "🔴 아님", "go": "port~poconc"})
        nf = [x for x in snap["focus"] if x and x not in (pv.get("focus") or [])]
        if nf:
            ch.append({"ic": "🎯", "t": "새 집중 테마: " + ", ".join(nf), "go": "market~mkfo"})
        if pv.get("gap") is not None:
            d_ = snap["gap"] - pv["gap"]
            if abs(d_) >= 0.2:
                ch.append({"ic": "⚡", "t": f"킥 vs S&P {pv['gap']:+.1f}%p → {snap['gap']:+.1f}%p " + ("(따라붙음)" if d_ > 0 else "(벌어짐)"), "lab": "킥 vs S&P",
                           "a": f"{pv['gap']:+.1f}%p", "b": f"{snap['gap']:+.1f}%p", "note": "따라붙음" if d_ > 0 else "벌어짐", "go": "port"})
        if snap["chg"] and snap["chg"] != pv.get("chg"):
            ch.append({"ic": "🔁", "t": f"포트 비중 바뀜 ({snap['chg'][5:].replace('-', '/')})", "go": "port~pofollow"})
        if snap["brain"] and pv.get("brain") and snap["brain"] != pv["brain"]:
            ch.append({"ic": "🧠", "t": f"두뇌 판단 {pv['brain']} → {snap['brain']}", "lab": "두뇌 판단", "a": pv["brain"], "b": snap["brain"], "go": "feed"})
    kev = home["kick"].get("events") or []
    if kev:
        ch.append({"ic": "⚡", "t": "킥 " + " · ".join(f"{'사기' if e['k'] == '사기' else '팔기'} {e.get('name')}" for e in kev[:3]), "go": "port~pokick"})
    if D and D.get("date") == today:
        ch.append({"ic": "🌐", "t": "오늘 시황 나옴 — " + _txt((D.get("kick") or {}).get("title"), 46), "lab": "오늘 시황 나옴",
                       "sub": _txt((D.get("kick") or {}).get("title"), 60), "go": "market"})
    home["chg"] = {"since": prev_d, "items": ch[:5]}
    sf.write_text(json.dumps(SN, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
