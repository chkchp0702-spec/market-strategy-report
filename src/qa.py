"""💬 고객이 이렇게 물으면 — 오늘 시황으로 쓴 답 20개 (11/11 사용자 「질문 갯수를 20개까지 늘리고」 · 처음 11/10 은 10개) (11/10 사용자: 「답변이 영 시원치 않다 · 지금 네 시황을 반영해서 PB나 고객 모두 우와 할 정도로 늘 답해」)
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
START20 = "2026-11-12"        # 🙌 11/11 사용자 「질문 20개까지」 — 아침 리포트는 이 날부터 20개(시황 두뇌가 고치는 market/qa.json 은 11/11 부터)
MUST20 = ["뭐가 세|주도|어디로 가", "손실|물렸|물타기", "일본|중국|홍콩", "지켜봐|일정|중요한 날", r"(?<![현예적자])금(?= |은|을|값)", "유가|원유|기름", "ELS", "연금|IRP", "예금|만기", "적립|매달"]
GROUPS = {"주식", "금리", "상품"}   # 앱 갈래 칩 — 📈 주식 · 💱 금리·환율(금·유가 포함) · 🧺 상품·연금
LONG = 320                    # 근거 한 줄이 이보다 길면 알림만(실패 아님) — 매시간 고칠 때 덧붙이지 말고 바꿔 쓰기


def check(day: dict, full: bool | None = None) -> int:
    if str(day.get("date", "")) < START:
        return 0
    qa = day.get("qa") or {}
    items = qa.get("items") or []
    bad = []
    if full is None:
        full = str(day.get("date", "")) >= START20
    need = 19 if full else 9
    if len(items) < need:
        bad.append(f"질문이 {len(items)}개 — {'20개(적어도 19개)' if full else '9~10개'} 필요")
    qs = " / ".join(str(i.get("q", "")) for i in items)
    for m in MUST + (MUST20 if full else []):
        if not re.search(m, qs):
            bad.append(f"「{m}」 갈래 질문이 없음")
    if full:
        for g in sorted(GROUPS):
            if not any(i.get("g") == g for i in items):
                bad.append(f"갈래 g=「{g}」 인 질문이 없음 — 모든 질문에 g(주식·금리·상품)를 적으세요")
        nog = [str(i.get("q", ""))[:14] for i in items if i.get("g") not in GROUPS]
        if nog:
            bad.append(f"g(주식·금리·상품)가 없는 질문 {len(nog)}개: {' / '.join(nog[:4])}")
    long_ = [(str(i.get("q", ""))[:12], len(str(p.get("t", "")))) for i in items for p in (i.get("pts") or []) if len(str(p.get("t", ""))) > LONG]
    if long_:
        print(f"  ⚠ 근거 한 줄이 {LONG}자 넘는 것 {len(long_)}개(가장 긴 것 {max(n for _, n in long_)}자 · {long_[0][0]}…) — 휴대폰 한 화면이 넘어요. 새 숫자는 덧붙이지 말고 옛 문장을 바꿔 쓰세요.")
    bond = [it for it in items if re.search(r"채권|금리", str(it.get("q", "")))]
    if bond:   # 🧾 11/10 사용자 「채권 금리는 한국 미국 브라질 다 대답해」
        bt = json.dumps(bond[0], ensure_ascii=False)
        for w, why in ((r"한국|국고채|🇰🇷", "한국 국고채"), (r"미국|미국채|🇺🇸", "미국채"), (r"브라질|헤알|🇧🇷", "브라질 국채")):
            if not re.search(w, bt):
                bad.append(f"채권 답에 {why} 금리가 없음 — 한국·미국·브라질 모두")
        if re.search(r"브라질|헤알", bt) and not re.search(r"중개|요청", bt):
            bad.append("채권 답 브라질 부분에 「중개 상품 — 고객 요청 시에만 안내·제안 가능」 문구가 없음")
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
            if cur.get("date") == d.get("date") and str(cur.get("at", "")) >= str(qa.get("at", "")):
                return False                      # ⏱ 시황 두뇌가 매시간 더 새로 고친 답이 있으면 아침 답으로 덮지 않음
            obj = {"date": d.get("date"), "edition": d.get("edition_label"), "at": qa.get("at") or (d.get("date", "") + " 07:00"),
                   "basis": qa.get("basis") or d.get("basis"), "items": qa["items"]}
            out.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            return True
    return False


def check_file(p: str = "market/qa.json") -> int:
    """⏱ 11/10 시황 두뇌가 매시간 고친 market/qa.json 검산 — python -m src.qa check"""
    import datetime as dt
    d = json.loads((ROOT / p).read_text(encoding="utf-8"))
    kst = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    bad = check({"date": max(START, kst.strftime("%Y-%m-%d")), "qa": d}, full=True)
    at = str(d.get("at", ""))
    if at[:10] != kst.strftime("%Y-%m-%d"):
        print(f"  ✗ at 이 오늘이 아님({at}) — 고친 시각(YYYY-MM-DD HH:MM)을 적으세요"); bad = 1
    return bad


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.exit(check_file(*(sys.argv[2:3])))
    print("내보냄" if export() else "그대로")
