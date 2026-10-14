"""lab 결과(k1014_q16.json) → market/q16b_bt.json (src/kick_sleeve.py 가 읽는 판정)
   사용자 10/14 16시 「1,3,5 진행」. 판정은 결과 보기 전에 정한 기준 그대로(src/lab/k1014_q16.py 머리말).
   (10/13 의 Q16 묶음 판정 market/q16_bt.json 과 다른 파일)"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
q = json.loads((ROOT / "market" / "lab" / "k1014_q16.json").read_text(encoding="utf-8"))
FROM = "2026-10-14"
out = {"src": "src/lab/k1014_q16.py (lab 워크플로)", "made": q.get("made")}

a = q.get("q161") or {}
out["krgap"] = {"verdict": a.get("verdict") or "➖", "why": a.get("why"), "from": FROM, "neg_years": a.get("neg_years"),
                "IS": {k: a.get("IS", {}).get(k) for k in ("x", "r")}, "OOS": {k: a.get("OOS", {}).get(k) for k in ("x", "r")},
                "us_alt": a.get("us_alt"), "kr_nh": a.get("kr_nh"),
                "rule": "🇰🇷 한국 📈 돌파 갭 → 킥에 안 넣고 🇰🇷 그림자 채점만 (빈 칸은 같은 날 다른 후보 순위대로)"}

c = q.get("q163") or {}
out["china"] = {"verdict": c.get("verdict") or "➖", "why": c.get("why"), "pick": c.get("pick"), "user_k1": c.get("user_k1"),
                "robust": c.get("robust"), "kind": c.get("kind"), "now": c.get("now"), "series": c.get("series"), "from": FROM,
                "rule": "🇨🇳 중국 신용 자극(BIS 신용/GDP 2차 변화)이 줄어드는 국면 → 한국 킥 새 진입 크기 절반"}

b = q.get("q165") or {}
out["breadth"] = {}
for m in ("US", "KR"):
    r = b.get(m) or {}
    out["breadth"][m] = {"verdict": r.get("verdict") or "➖", "why": r.get("why"), "pick": r.get("pick"), "user_L60T15": r.get("user_L60T15"),
                         "robust": r.get("robust"), "now": r.get("now"), "from": FROM}
(ROOT / "market" / "q16b_bt.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"krgap": out["krgap"]["verdict"], "china": out["china"]["verdict"],
                  "breadth": {m: v["verdict"] for m, v in out["breadth"].items()}}, ensure_ascii=False))
