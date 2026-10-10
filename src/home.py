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
KN = {"cup": "컵 돌파", "gap": "돌파 갭", "accum": "매집", "whale": "고래", "focus": "집중", "lead": "선행"}
TAG = {"cup_eye": "☕", "cup": "☕", "gap": "📈", "accum": "🤫", "whale": "🐋", "focus": "🎯", "lead": "🔗"}


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
        "n_bench": len(bm), "nav": P.get("nav", [])[-30:], "kick_line": kd[-30:], "spy_line": (P.get("bench", {}).get("S&P500") or [])[-30:],
        "change": (P.get("changes") or [{}])[0] if (P.get("changes") or [{}])[0].get("date", "") >= (now - dt.timedelta(days=3)).strftime("%Y-%m-%d") else None,
        "weak": [h["name"] for h in P.get("hold", []) if str(h.get("sig", "")).startswith("약함")],
        "strong": [h["name"] for h in P.get("hold", []) if str(h.get("sig", "")).startswith("강함")],
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
    bsum = BS.get("sum") or {}
    bw, bl = bsum.get("win", 0), bsum.get("loss", 0)
    S.append({"k": "bets", "ic": "🧠", "t": "두뇌 선제 아이디어", "n": bw + bl, "win": bw, "loss": bl, "rate": round(bw / (bw + bl) * 100) if bw + bl else None,
              "avg": bsum.get("avg"), "note": f"채점 중 {bsum.get('live', 0)}개 · 끝난 것 {bsum.get('closed', 0)}개"})
    ks = K.get("stat") or {}
    sig = []
    for k, v in (K.get("proof") or {}).items():
        sig.append({"k": k, "tag": TAG.get(k, ""), "on": v.get("on"), "trial": v.get("trial"), "n": v.get("n"), "pf": v.get("pf"), "avg": v.get("avg"), "why": v.get("why")})
    for k, v in (K.get("shadow_stat") or {}).items():
        sig.append({"k": k, "tag": v.get("tag", TAG.get(k, "")), "shadow": True, "n": v.get("n"), "pf": v.get("pf"), "avg": v.get("avg"), "win": v.get("win")})
    S.append({"k": "kick", "ic": "⚡", "t": "킥 — 신호별", "n": ks.get("trades"), "win": None, "rate": ks.get("win"), "avg": ks.get("avg"),
              "note": f"킥 {ks.get('kick', 0):+.2f}% vs 기본 {ks.get('base', 0):+.2f}% · S&P {ks.get('spy', 0):+.2f}%", "sig": sig})
    dt_ = []
    for k, v in (LR.get("types") or {}).items():
        dt_.append({"k": k, "n": v.get("n_all"), "avg": v.get("avg_all"), "slots": {s: {"st": r.get("st"), "n": r.get("n"), "avg": r.get("avg")} for s, r in (v.get("slots") or {}).items()}})
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
    good, bad = [], []
    for x in sig:
        if (x.get("n") or 0) >= 10 and x.get("pf"):
            (good if x["pf"] >= 1.5 else bad if x["pf"] < 1 else []).append(f"{x['tag']} {KN.get(x['k'], x['k'])} 손익비 {x['pf']}")
    for x in dt_:
        if (x.get("n") or 0) >= 15 and x.get("avg") is not None:
            (good if x["avg"] > 0.2 else bad if x["avg"] < -0.3 else []).append(f"단타 {x['k']} {x['avg']:+.2f}%")
    scores = {"at": home["at"], "rows": S, "good": good[:6], "bad": bad[:6]}
    home["scores"] = {"good": good[:3], "bad": bad[:3]}

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


if __name__ == "__main__":
    sys.exit(main())
