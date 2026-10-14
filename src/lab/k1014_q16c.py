"""📈 10/14 16시 Q16-3 다시 돌리기 — 첫 실행(k1014_q16.py)에서 FRED 가 시간 초과 → BIS API 대체 경로 추가 후 Q16-3 만 다시 계산해
market/lab/k1014_q16.json 의 q163 칸만 바꿈 (판정 기준은 k1014_q16.py 머리말 그대로 · 결과 보기 전 정함)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import k1014_q16 as Q   # noqa: E402

res = json.loads(Q.OUT.read_text(encoding="utf-8"))
ev = Q.load_rows()
try:
    res["q163"] = Q.q163(ev, {})
    res.pop("q163_err", None)
except Exception:
    import traceback
    res["q163_err"] = traceback.format_exc()[-800:]
    print(res["q163_err"])
json.dump(res, open(Q.OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("done")
