"""💬 고객이 이렇게 물으면 — 오늘 시황으로 쓴 답 10개 (11/10 사용자: 「답변이 영 시원치 않다 · 지금 네 시황을 반영해서 PB나 고객 모두 우와 할 정도로 늘 답해」)
  · 아침 리포트 세션이 data/YYYY-MM-DD.json 의 "qa" 에 직접 쓴다 (RULES 1-N) — 틀에 숫자만 끼운 답이 아니라 그날 리포트의 킥·집중·대결·계기판·수급을 녹인 답
  · check(day): 검산 (src/verify.py 가 부름) — 빠졌거나 빈약하면 실패
  · export(): 가장 최근 data 파일의 qa → market/qa.json (앱 daily-app mine.js 가 읽음 · src/home.py 가 매번 부름)
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = "2026-11-11"          # 이 날부터 필수
MUST = ["팔", "사도", "외국인", "미국", "바닥|저점|언제", "현금", "채권|금리", "환율|달러"]   # 꼭 있어야 하는 질문 갈래(질문 글에 이 말이 들어감)


def check(day: dict) -> int:
    if str(day.get("date", "")) < START:
        return 0
    qa = day.get("qa") or {}
    items = qa.get("items") or []
    bad = []
    if len(items) < 9:
        bad.append(f"질문이 {len(items)}개 — 9~10개 필요")
    qs = " / ".join(str(i.get("q", "")) for i in items)
    for m in MUST:
        if not re.search(m, qs):
            bad.append(f"「{m}」 갈래 질문이 없음")
    for n, it in enumerate(items, 1):
        q = it.get("q", f"{n}번")
        if len(str(it.get("a", ""))) < 25:
            bad.append(f"{q}: 결론(a)이 너무 짧음 — 한 문장으로 분명하게")
        pts = it.get("pts") or []
        if len(pts) < 3:
            bad.append(f"{q}: 근거(pts)가 {len(pts)}개 — 3개 필요")
        if sum(1 for p in pts if re.search(r"\d", str(p.get("t", "")))) < 2:
            bad.append(f"{q}: 근거에 오늘 숫자가 거의 없음 — 3개 중 2개 이상은 숫자")
        if len(it.get("act") or []) < 2:
            bad.append(f"{q}: 고객 유형별 행동(act)이 2줄 미만")
        if len(str(it.get("flip", ""))) < 12:
            bad.append(f"{q}: 「이 답이 바뀌는 조건」(flip)이 없음 — 숫자·선으로")
        if re.search(r"사세요|매수하세요|무조건|반드시 오|확실히 오", json.dumps(it, ensure_ascii=False)):
            bad.append(f"{q}: 매수 권유·단정 문구가 있음")
    if bad:
        print("\n💬 고객 질문 답(qa) 검산 — RULES 1-N:")
        for b in bad[:14]:
            print("  ✗", b)
        print("  → data 파일의 \"qa\" 를 고치세요 (양식: data/_template.json · 본보기: market/qa.json).")
        return 1
    print(f"💬 고객 질문 답 {len(items)}개 OK")
    return 0


def export() -> bool:
    files = sorted((ROOT / "data").glob("20*.json"))
    cur = {}
    out = ROOT / "market" / "qa.json"
    try:
        cur = json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        pass
    for f in reversed(files[-5:]):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        qa = d.get("qa") or {}
        if (qa.get("items") or []):
            if str(d.get("date", "")) < str(cur.get("date", "")):
                return False                      # 이미 더 새 것이 있음(장중에 손으로 다시 쓴 답)
            if cur.get("date") == d.get("date") and str(cur.get("at", "")) > str(qa.get("at", "")):
                return False
            obj = {"date": d.get("date"), "edition": d.get("edition_label"), "at": qa.get("at") or (d.get("date", "") + " 07:00"),
                   "basis": qa.get("basis") or d.get("basis"), "items": qa["items"]}
            out.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            return True
    return False


if __name__ == "__main__":
    print("내보냄" if export() else "그대로")
