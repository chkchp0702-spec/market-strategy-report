"""⚡ 킥 슬리브 — 포트의 15%를 「우리 스캐너가 확인한 순간」에만 넣는 공격 칸 (10/9 사용자: "10~20%는 시장을 이기는 베팅·킥이 필요하지 않을까")
  비교: 💼 기본 포트(리포트 배분표 그대로) vs ⚡ 킥 포트(기본에서 현금 15%p 를 킥 슬리브로)

  근거(8/30~ 장부): 컵 후보 전체는 평균 −2.2%(31% 이김)지만 기준가를 실제로 뚫은 컵은 평균 +7.0%(71%), 돌파 갭 5일 +1.7%(62%).
  → 후보가 아니라 「확인된 순간」에만 들어간다.

  규칙
  · 자리 5개, 한 자리 = 슬리브의 20% (= 포트의 3%). 빈 자리는 현금(SGOV).
  · 들어가는 신호 (우선순위): ① 🎯 집중 ★종목 기준가 돌파(장중 알림)  ② 눈 검사 통과 컵의 기준가 돌파  ③ 그 밖의 컵 돌파  ④ 돌파 갭(메우지 않음)
    점수 + 고래 TOP10 겹치면 +10. 하루 새로 들어가는 건 최대 2개, 같은 종목 중복 없음, 판 지 10거래일 안 된 종목 재진입 없음.
  · 들어가는 값: 신호가 뜬 날 종가.
  · 나가는 규칙: 들어간 값 −5% 종가 → 손절 / +15% → 절반 정리, 나머지는 20일선 아래 종가에 정리 / 15거래일 지나도 최고 +3% 못 넘으면 정리(시간 손절).
  · 브레이크: 슬리브가 시작 대비 −6% 아래면 10거래일 새 진입 멈춤.
  · 수익률은 각 종목 현지 통화 기준(환율 제외), 수수료·세금 제외.
  → market/kick.json (앱 💼 포트 탭 「기본 vs 킥」 비교) · 새로 사고판 날 ntfy chkchp-ch-kick 알림
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
SLEEVE = 0.15
SLOTS = 5
STOP, TAKE, TIME_D, TIME_MIN = -0.05, 0.15, 15, 0.03
BRAKE, BRAKE_D, MAX_NEW, REENTRY = -0.06, 10, 2, 10
PRI = {"focus": 40, "cup_eye": 25, "cup": 10, "gap": 0}
SRC_NAME = {"focus": "🎯 집중 돌파", "cup_eye": "☕ 컵 돌파(눈 검사 통과)", "cup": "☕ 컵 돌파", "gap": "📈 돌파 갭"}


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
            if x.get("gtype") == "돌파 갭" and not x.get("filled") and x["code"] not in seen:
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
    for back in range(6):                       # 🐋 최근 고래 신호 (TOP10 · 큰손 매수)
        day = (now - dt.timedelta(days=back)).strftime("%Y-%m-%d")
        try:
            W = get_json(f"archive/whale/{day}/data.json").get("signals", {})
            for k in ("top10", "big", "mov"):
                whale |= set(W.get(k) or [])
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
    cands = [v for v in C["cands"].values() if v["d"] >= START]
    whale = set(C.get("whale", []))
    import yfinance as yf
    tick = sorted({c["code"] for c in cands} | {"SGOV", "SPY"})
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
            pr = PRI[c["src"]] + c["score"] + (10 if c["code"] in whale else 0)
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
                pos.append({"code": c["code"], "name": c["name"], "mkt": c.get("mkt"), "src": c["src"], "d0": d, "entry": e, "sh": cost / e, "cost": cost,
                            "held": 0, "max": e, "last": e, "half": False, "realized": 0.0, "pr": c["pr"], "whale": c.get("whale")})
                events.append({"d": d, "k": "사기", "code": c["code"], "name": c["name"], "src": SRC_NAME[c["src"]], "px": round(e, 4)})
        total = cash + sum(p["sh"] * (px(p["code"], d) or p["entry"]) for p in pos)
        if i > 0:
            val.append(total)
        else:
            val[0] = total

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
        kick.append(kick[-1] * (1 + rb - SLEEVE * rg + SLEEVE * rs))
        lastv = sv.get(d1, lastv)
        sleeve_line.append(round((lastv - 1) * 100, 2))
    trades = closed
    wins = [t for t in trades if t["r"] > 0]
    loss = [t for t in trades if t["r"] <= 0]
    avg = lambda L: round(sum(t["r"] for t in L) / len(L), 2) if L else None
    last_d = D[-1]
    openp = []
    for p in pos:
        c = px(p["code"], last_d) or p["entry"]
        openp.append({"code": p["code"], "name": p["name"], "mkt": p.get("mkt"), "src": SRC_NAME[p["src"]], "d0": p["d0"], "entry": round(p["entry"], 4),
                      "now": round(c, 4), "r": round((c / p["entry"] - 1) * 100, 2), "days": p["held"], "half": p["half"], "whale": p.get("whale"),
                      "stop": round(p["entry"] * (1 + STOP), 4), "take": round(p["entry"] * (1 + TAKE), 4), "w": round(p["sh"] * c / val[-1] * SLEEVE * 100, 2)})
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"), "start": START, "asof": last_d,
        "dates": pdates, "base": [round((b - 1) * 100, 2) for b in base], "kick": [round((k - 1) * 100, 2) for k in kick],
        "sleeve": round((val[-1] - 1) * 100, 2), "sleeve_line": sleeve_line,
        "open": openp, "closed": trades[::-1][:40], "events": events[::-1][:40],
        "stat": {"base": round((base[-1] - 1) * 100, 2), "kick": round((kick[-1] - 1) * 100, 2), "spy": P["stat"]["spy"],
                 "trades": len(trades), "win": round(len(wins) / len(trades) * 100) if trades else None,
                 "avg_win": avg(wins), "avg_loss": avg(loss), "avg": avg(trades), "slots": f"{len(pos)}/{SLOTS}",
                 "paused": pause_until >= len(D) - 1},
        "rules": {"sleeve": SLEEVE, "slots": SLOTS, "stop": STOP, "take": TAKE, "time": TIME_D, "brake": BRAKE},
        "note": "킥 포트 = 기본 포트에서 현금 15%p 를 ⚡ 킥 슬리브로. 슬리브는 우리 스캐너가 「확인한 순간」(컵 기준가 돌파·돌파 갭·🎯 집중 돌파)에만 3%씩 들어가고 규칙대로 나옴. "
                "10/9 이전은 같은 규칙으로 되짚은 계산(눈 검사는 10/9 결과를 썼으니 실전보다 조금 유리할 수 있음 — 10/10부터는 실시간 기록). 현지 통화 기준·수수료 제외. 매수 추천 아님.",
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
