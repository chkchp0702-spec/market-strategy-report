"""장부(ledger.json) 읽기·집계·갱신.

규칙: 리포트의 누적·카운트·그림은 전부 여기서 나온다. 기억으로 이어 붙이지 않는다.
"""
from __future__ import annotations
import json, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger" / "ledger.json"


def load() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def save(led: dict) -> None:
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scorecard_totals(rows: list[dict]) -> dict:
    t = {"맞음": 0, "틀림": 0, "반반": 0, "보류": 0}
    for r in rows:
        t[r["verdict"]] = t.get(r["verdict"], 0) + 1
    return t


def totals_line(t: dict) -> str:
    return f"맞음 {t['맞음']} · 틀림 {t['틀림']} · 반반 {t['반반']} · 보류 {t['보류']}"


def panel_view(led: dict, today: list[dict]) -> list[dict]:
    """패널 31행에 오늘 판정을 얹어 템플릿용 행을 만든다. 누적은 장부값 + 오늘 득실(미리보기)."""
    tmap = {t["n"]: t for t in today}
    rows = []
    for p in led["panel"]:
        t = tmap.get(p["n"], {})
        win, loss = p["win"], p["loss"]
        # 오늘 판정은 '미리보기' — commit 시 장부에 반영됨. 장부가 이미 반영된 뒤 재빌드해도 중복되지 않도록
        # 오늘 verdict 를 장부에 적용했는지는 led['_applied'] 에 날짜로 기록.
        last = dict(p.get("last", {}))
        if t.get("new_quote"):
            last.update(t["new_quote"])
        rows.append({
            **p, "last": last,
            "q1": last.get("q1", ""), "q2": last.get("q2", ""), "q3": last.get("q3", ""),
            "qdate": last.get("date", ""),
            "today": t.get("today", ""), "verdict": t.get("verdict", ""),
            "is_new": bool(t.get("new_quote")),
            "cum": f"{win}:{loss}",
        })
    return rows


def group_rows(rows: list[dict]) -> list[dict]:
    out, cur = [], None
    for r in rows:
        if r["group"] != cur:
            cur = r["group"]
            out.append({"title": cur, "rows": []})
        out[-1]["rows"].append(r)
    return out


def commit(led: dict, day: dict) -> dict:
    """하루치 판정을 장부에 반영한다. 같은 날짜는 두 번 반영하지 않는다."""
    led = copy.deepcopy(led)
    date = day["date"]
    applied = led.setdefault("_applied", [])
    if date in applied:
        return led
    # 패널 득실 + 최근 발언
    tmap = {t["n"]: t for t in day.get("panel_today", [])}
    for p in led["panel"]:
        t = tmap.get(p["n"])
        if not t:
            continue
        if t.get("verdict") == "win":
            p["win"] += 1
        elif t.get("verdict") == "loss":
            p["loss"] += 1
        if t.get("new_quote"):
            p["last"] = {**p.get("last", {}), **t["new_quote"]}
    # 패널 밖
    omap = {o["name"]: o for o in day.get("outside_today", [])}
    for o in led["outside_panel"]:
        t = omap.get(o["name"])
        if t and t.get("verdict") == "win":
            o["win"] += 1
        elif t and t.get("verdict") == "loss":
            o["loss"] += 1
    # 내 성적표
    for r in day.get("scorecard_today", []):
        led["scorecard"].append({"date": date, **r})
    # 시계열
    for key, item in day.get("ledger_commit", {}).get("series_add", {}).items():
        ser = led["series"].setdefault(key, [])
        if not any(x["date"] == item["date"] for x in ser):
            ser.append(item)
            ser.sort(key=lambda x: x["date"])
    # 어제 예고 → 다음 리포트 채점용
    led["forecasts"] = {"from": f"{date} {day['edition']}", "items": [_strip(c) for c in day.get("checks", [])]}
    led["updated"] = date
    applied.append(date)
    return led


def _strip(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html)
