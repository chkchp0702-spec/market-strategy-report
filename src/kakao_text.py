"""카톡 붙여넣기용 텍스트 요약. 숫자·결론은 요약본과 같아야 한다."""
from __future__ import annotations


def kakao_text(d: dict) -> str:
    y, m, dd = d["date"].split("-")
    lines = [f"[시황 {int(m)}/{int(dd)} {d['edition_label']}]"]
    lines += d["kakao"]["lines"]
    lines.append("※ 정보 제공 목적이며 투자 권유가 아닙니다.")
    return "\n".join(lines) + "\n"
