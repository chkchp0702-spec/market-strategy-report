"""카톡 붙여넣기용 텍스트 요약. 숫자·결론은 요약본과 같아야 한다."""
from __future__ import annotations
import re


def kakao_text(d: dict) -> str:
    y, m, dd = d["date"].split("-")
    lines = [f"[시황 {int(m)}/{int(dd)} {d['edition_label']}]"]
    k = d.get("kick") or {}
    if k and not k.get("none") and k.get("title"):
        lines.append("⚡ 킥: " + re.sub(r"<[^>]+>", "", k["title"]) + (" → " + re.sub(r"<[^>]+>", "", k.get("so", "")) if k.get("so") else ""))
    ld = d.get("leaders") or {}
    if ld.get("title"):
        lines.append("🔥 주도: " + re.sub(r"<[^>]+>", "", ld["title"]) + (" → " + re.sub(r"<[^>]+>", "", ld.get("so", "")) if ld.get("so") else ""))
    try:   # 🎯 오늘의 집중 (market/focus.json)
        import json
        from pathlib import Path
        fo = json.loads((Path(__file__).resolve().parent.parent / "market" / "focus.json").read_text(encoding="utf-8"))
        parts = []
        for t in fo.get("themes", [])[:2]:
            etf = [t["sym"]] + [x["name"] for x in t.get("etf_kr", [])[:1]]
            st = [x["name"] + ("★" if x.get("star") else "") for x in (t.get("us", [])[:2] + t.get("kr", [])[:2]) if x.get("act") != "추격 금지"]
            parts.append(f"{t['name']}({' · '.join(etf)} / {', '.join(st[:3])})")
        if parts:
            c0 = (fo.get("countries") or [{}])[0]
            lines.append("🎯 집중: " + " | ".join(parts) + (f" · 돈 들어오는 나라 {c0.get('flag', '')}{c0.get('name', '')}" if c0.get("label") else ""))
    except Exception:
        pass
    lines += d["kakao"]["lines"]
    lines.append("※ 정보 제공 목적이며 투자 권유가 아닙니다.")
    return "\n".join(lines) + "\n"
