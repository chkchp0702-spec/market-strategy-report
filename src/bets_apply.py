"""🧾 선제 아이디어(bets) 채점 옮겨 적기 + 규칙 집행 — 10/29 (사용자 「선제 아이디어가 맨날 안 바뀌어 · 둘 다 확인해서 고쳐」)

문제 ① 옮겨 적기가 사람 손(두뇌 세션) 몫이었다
   Actions 는 매시간 market/bets_score.json 에 진행·이김/짐을 계산하는데, state.json 으로 옮기는 건 두뇌 세션의 일이었다.
   10/27 밤부터 두뇌가 「자동값 유지」라며 옮기지 않아 앱 화면의 진행률·승패(7승 17패)가 이틀 넘게 멈췄다.
   → 이 스크립트가 기계적으로 옮긴다. 두뇌 세션(커밋 직전)과 Actions(매시간, 최신 원격 state.json 위에서) 둘 다 돌린다. 몇 번 돌려도 결과가 같다.

문제 ② 성적이 나빴다 (10/29 기준 판정 30건 8승 22패 · 평균 −2.6%)
   시장별: 미국 15건 7승 평균 −0.6% · 한국 12건 1승 평균 −4.9% · 일본 2건 0승 · 홍콩 1건 0승
   종류별: 개별 종목 24건 3승 평균 −3.5% · ETF 4건 3승 +1.1% · 비중 2건 2승 +0.8%
   미국 종목 중 「목표 +5% · 손절 −3%」 5건은 평균 +0.1%, 목표 +7~10% · 손절 −5~7% 3건은 평균 −4.6%
   → 10/29 13:30 이후 새로 만든 bets 부터 (결과 보기 전 등록):
     R1 한국·일본·홍콩·중국 개별 종목 = 👻 그림자 (채점은 계속, 승패 집계·킥에서 뺌)
     R2 미국 개별 종목 = 목표 entry +5% · 손절 entry −3% · 1주로 맞춤 (더 먼 목표·더 넓은 손절이면 고침)
     R3 ETF·지수·비중 bets 는 그대로
     되돌리기: 그림자 판정 15건↑ · 승률 45%↑ · 평균 + 가 되면 그 시장 개별 종목을 다시 진짜로 (자동, rules 칸에 기록)
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "brain" / "state.json"
SCORE = ROOT / "market" / "bets_score.json"
RULE_FROM = "2026-10-29 13:30"
ASIA = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")


def pct(res) -> float | None:
    m = re.search(r"([+\-−]\s?\d+(?:\.\d+)?)\s*%", str(res or ""))
    return float(m.group(1).replace("−", "-").replace(" ", "")) if m else None


def market(t: str) -> str:
    t = str(t or "")
    if t.endswith((".KS", ".KQ")):
        return "한국"
    if t.endswith(".T"):
        return "일본"
    if t.endswith(".HK"):
        return "홍콩"
    if t.endswith((".SS", ".SZ")):
        return "중국"
    return "미국"


def is_stock(b: dict) -> bool:
    k = str(b.get("kind") or "")
    if k in ("ETF", "비중", "지수", "환율", "금리"):
        return False
    t = str(b.get("t") or "")
    return bool(t) and not t.startswith("^") and "=" not in t and k in ("종목", "")


def stats(rs: list[float]) -> dict:
    if not rs:
        return {"n": 0, "win": 0, "loss": 0, "avg": None}
    return {"n": len(rs), "win": sum(1 for r in rs if r > 0), "loss": sum(1 for r in rs if r < 0), "avg": round(sum(rs) / len(rs), 2)}


def main() -> int:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    sc = json.loads(SCORE.read_text(encoding="utf-8")) if SCORE.exists() else {"bets": []}
    by = {}
    for x in sc.get("bets", []):
        by[x.get("id") or x.get("t")] = x
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    bets = st.get("bets", [])
    rules = st.get("bets_rules") or {}
    back = set(rules.get("live_again", []))       # 그림자에서 다시 진짜로 돌아간 시장
    changed = 0

    # ② 규칙 집행 — 새로 만든 것만
    for b in bets:
        if str(b.get("made") or "") < RULE_FROM or b.get("status") not in ("열림", "대기") or b.get("rule_ok"):
            continue
        mk = market(b.get("t"))
        if is_stock(b) and mk != "미국" and mk not in back:
            b["status"] = "그림자"; b["shadow"] = True
            b["note"] = (str(b.get("note") or "") + f" · 👻 규칙 R1(10/29): {mk} 개별 종목은 그림자 채점만").strip(" ·")
        elif is_stock(b) and mk == "미국":
            t_ = pct(str(b.get("target") or "").replace("entry", "")) if "entry" in str(b.get("target") or "") else None
            s_ = pct(str(b.get("stop") or "").replace("entry", "")) if "entry" in str(b.get("stop") or "") else None
            if (t_ is None or t_ > 5.5) or (s_ is None or s_ < -3.5) or str(b.get("horizon")) != "1주":
                b["target"], b["stop"], b["horizon"] = "entry +5%", "entry −3%", "1주"
                b["note"] = (str(b.get("note") or "") + " · 규칙 R2(10/29): 미국 종목은 +5%/−3%/1주로 맞춤").strip(" ·")
        b["rule_ok"] = True
        changed += 1

    # ① 채점 옮기기
    for b in bets:
        if b.get("status") not in ("열림", "대기", "그림자"):
            continue
        x = by.get(b.get("id")) or (by.get(b.get("t")) if b.get("t") else None)
        if not x or (x.get("id") and b.get("id") and x["id"] != b["id"]):
            continue
        if x.get("entry") is not None and b.get("entry") in (None, "", "null"):
            b["entry"] = x["entry"]
            b["entry_note"] = f"{x.get('entry_d', '')} {x.get('entry_by', '')}(bets_score)".strip()
        shadow = b.get("status") == "그림자" or b.get("shadow")
        if x.get("st") == "닫힘":
            b["status"] = "닫힘"; b["res"] = x.get("res"); b["closed_at"] = now
            if shadow:
                b["shadow"] = True
        else:
            if x.get("st") == "열림" and b.get("status") == "대기":
                b["status"] = "열림"
            b["res_now"] = x.get("res"); b["res"] = x.get("res")
            if x.get("now") is not None:
                b["now"] = x["now"]
            b["res_at"] = sc.get("at")
        changed += 1

    # 채점표 다시 세기 (그림자 빼고) + 그림자 따로
    real = [pct(b.get("res")) for b in bets if b.get("status") == "닫힘" and not b.get("shadow")]
    real = [r for r in real if r is not None]
    sh = {}
    for b in bets:
        if b.get("status") == "닫힘" and b.get("shadow"):
            r = pct(b.get("res"))
            if r is not None:
                sh.setdefault(market(b.get("t")), []).append(r)
    s = stats(real)
    st.setdefault("scorecard", {})["bets"] = {"made": sum(1 for b in bets if b.get("t") and not b.get("shadow")), "win": s["win"], "loss": s["loss"], "avg": s["avg"],
                                               "open": sum(1 for b in bets if b.get("status") == "열림"), "at": now}
    for mk, rs in sh.items():
        q = stats(rs)
        if q["n"] >= 15 and q["avg"] is not None and q["avg"] > 0 and q["win"] / q["n"] >= 0.45:
            back.add(mk)
    st["bets_rules"] = {"from": RULE_FROM,
                        "R1": "한국·일본·홍콩·중국 개별 종목 = 👻 그림자(채점만, 승패·킥 제외)",
                        "R2": "미국 개별 종목 = 목표 +5% · 손절 −3% · 1주",
                        "R3": "ETF·지수·비중은 그대로",
                        "back": "그림자 15건↑·승률 45%↑·평균 + 면 그 시장 다시 진짜로",
                        "shadow": {mk: stats(rs) for mk, rs in sh.items()},
                        "live_again": sorted(back), "at": now}
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"bets_apply: 손댄 {changed} · 채점 {s['win']}승 {s['loss']}패 평균 {s['avg']} · 그림자 {sum(len(v) for v in sh.values())}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
