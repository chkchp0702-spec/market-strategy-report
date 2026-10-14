"""lab 결과(k1014_q15g.json · k1014_q15i.json) → market/q15_bt.json (src/kick_sleeve.py · src/port.py 가 읽는 판정)
   사용자 10/14 15시 「2,5번 실행」. 판정은 결과 보기 전에 정한 기준 그대로(각 lab 파일 머리말)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
L = ROOT / "market" / "lab"
out = {"src": "src/lab/k1014_q15g.py · src/lab/k1014_q15i.py (lab 워크플로)"}

g = json.loads((L / "k1014_q15g.json").read_text(encoding="utf-8"))
gu, gk = g["q155"]["US"], g["q155"]["KR"]
k = gu.get("pick") or "w3f75"
W, F = int(k[1]), int(k.split("f")[1]) / 100
out["pull"] = {"made": g.get("made"), "verdict": gu["verdict"] if gu["verdict"] in ("✅", "🧪") else "❌", "W": W, "f": F, "pick": k,
               "from": "2026-10-14", "scope": "미국 📈 돌파 갭만", "why": gu["why"], "user_w3f50": gu["user_w3f50"],
               "kr": f"{gk['verdict']} {gk['why']} → 한국 갭은 눌림이든 다음 날이든 지수에 크게 짐 → 그대로(안 바꿈)",
               "robust": gu["robust"]}

try:
    q = json.loads((L / "k1014_q15i.json").read_text(encoding="utf-8"))
    pk = q.get("pick") or "t90h40"
    out["ins"] = {"made": q.get("made"), "verdict": q.get("verdict"), "pick": pk, "thr": int(pk[1:pk.index("h")]), "H": int(pk.split("h")[1]),
                  "why": q.get("why"), "user_t90h40": q.get("user_t90h40"), "robust": q.get("robust"), "now": q.get("now"),
                  "event": {t: {p: {k_: v for k_, v in o.items() if k_ != "dates"} for p, o in e.items()} for t, e in (q.get("event") or {}).items()},
                  "log": (q.get("log") or {}).get("ins")}
except FileNotFoundError:
    out["ins"] = {"verdict": "⏳", "why": "lab 결과 아직 없음"}

(ROOT / "market" / "q15_bt.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k_: v.get("verdict") for k_, v in out.items() if isinstance(v, dict)}, ensure_ascii=False))
