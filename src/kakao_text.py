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
    lines += d["kakao"]["lines"]
    lines.append("※ 정보 제공 목적이며 투자 권유가 아닙니다.")
    return "\n".join(lines) + "\n"
