"""🧪 kick_sleeve 시험 실행 (Q16 연결 점검) — lab 워크플로는 market/lab 만 저장하므로 진짜 kick.json 은 안 바뀜.
결과 요약 → market/lab/k1013_kicktest.json"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
r = subprocess.run([sys.executable, "-m", "src.kick_sleeve"], cwd=ROOT, capture_output=True, text=True, timeout=1500)
out = {"rc": r.returncode, "stdout_tail": r.stdout[-3000:], "stderr_tail": r.stderr[-4000:]}
try:
    K = json.loads((ROOT / "market" / "kick.json").read_text(encoding="utf-8"))
    out["ideas"] = {k: {kk: v.get(kk) for kk in ("name", "state", "on", "rule", "exit", "today", "today_d", "n30")} for k, v in (K.get("ideas") or {}).items()}
    out["proof"] = {k: {kk: v.get(kk) for kk in ("n", "pf", "on", "trial", "why")} for k, v in (K.get("proof") or {}).items() if k in ("cust", "ins", "gap", "cup")}
    out["q16_max"] = K.get("q16_max")
    out["q18_frog"] = K.get("q18_frog")
    out["shadow_stat"] = K.get("shadow_stat")
    out["stat"] = K.get("stat")
    out["open"] = [{k: o.get(k) for k in ("code", "src", "d0")} for o in K.get("open") or []]
except Exception as e:
    out["read_err"] = repr(e)
(ROOT / "market" / "lab" / "k1013_kicktest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False)[:5000])
sys.exit(r.returncode)
