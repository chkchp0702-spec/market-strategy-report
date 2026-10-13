"""lab 결과(k1013_q16.json · k1013_insider.json) → market/q16_bt.json (src/kick_sleeve.py · src/q16_live.py 가 읽는 판정)
   판정 손질(앞 기간에 정한 기준 밖의 사람 판단)은 여기 OVERRIDE 에 이유와 함께 적는다."""
import json, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
L = ROOT / "market" / "lab"
q = json.loads((L / "k1013_q16.json").read_text(encoding="utf-8"))
ins = json.loads((L / "k1013_insider.json").read_text(encoding="utf-8")) if (L / "k1013_insider.json").exists() else {}
mx = q["q163"]
main_ = mx.get("gap|kk") or {}
out = {"made": q.get("made"), "src": "src/lab/k1013_q16.py · src/lab/k1013_insider.py (lab 워크플로)",
       "max": {"verdict": main_.get("verdict"), "th": 10, "why": " / ".join(f"{k}: {v.get('verdict')} {v.get('why')}" for k, v in mx.items()),
               "note": "판정 ❌ → 킥은 그대로, MAX20 ≥ 10% 후보는 🎰 그림자 채점만 (우리 장부에서도 확인)"},
       "cust": {k: q["q162"].get(k) for k in ("pick", "IS", "OOS", "verdict", "why", "OOS_by_customer", "top")},
       "ins": {k: ins.get(k) for k in ("pick", "IS", "OOS", "verdict", "why", "top", "routine_only")} if ins.get("verdict") else {}}
out["max"]["verdict"] = "❌" if all(v.get("verdict") == "❌" for v in mx.values()) else main_.get("verdict")
(ROOT / "market" / "q16_bt.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
h = L / "insider_hist.json.gz"
if h.exists():
    shutil.copy(h, ROOT / "market" / "insider_hist.json.gz")
print(json.dumps({k: (v.get("verdict") if isinstance(v, dict) else v) for k, v in out.items()}, ensure_ascii=False))
