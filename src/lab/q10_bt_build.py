"""lab 결과(k1014_q10.json) → market/q10_bt.json (src/kick_sleeve.py 가 읽는 판정) — 사용자 10/14 「2,3,5 실행」
   판정은 결과 보기 전에 정한 기준 그대로(src/lab/k1014_q10.py 머리말). 사람 손질은 여기 이유와 함께 적는다."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
q = json.loads((ROOT / "market" / "lab" / "k1014_q10.json").read_text(encoding="utf-8"))
a = q["q102"]["US|B"]
g = a["grid"][str(a["pick_W"])]["OOS"]
out = {"made": q.get("made"), "src": "market/lab/k1014_q10.json (src/lab/k1014_q10.py, lab 워크플로)",
       "agree": {"verdict": a["verdict"], "scope": "미국만", "W": a["pick_W"], "bonus": 30,
                 "kinds": {"cup": "nh", "cup_eye": "nh", "gap": "gap", "earn": "pead", "pead": "pead", "cust": "cust"},
                 "rule": f"미국 후보에 지난 {a['pick_W']}거래일(오늘 포함) 안 다른 종류 신호(☕ 컵·📈 갭·📊 실적 갭·🔌 고객사)가 같은 종목에 있으면 🤝 합의 → 킥 순위 +30 (같은 날 갭+신고가 짝은 한 신호로 침)",
                 "why": a["why"], "by_kind_OOS": g["by_kind"],
                 "kr": "한국은 ❌ — 합의 쪽이 오히려 더 나쁨(시험 기간 −3.7% vs 단독 −1.8%) → 한국엔 안 붙임",
                 "note": "합의 종목은 그림자 장부에도 🤝 로 따로 채점(우리 장부로 다시 확인)"},
       "cluster": {"verdict": "❌", "why": q["q103"]["US"]["why"],
                   "kr": q["q103"]["KR"]["why"] + " (한국 갭·신고가 대용 자체가 시험 기간에 크게 짐 — 묶음 한도와 무관)",
                   "note": "상관 0.5~0.7 · 묶음 1~2칸 어느 것도 시험 기간 샤프·연수익을 못 올림 → 킥 규칙 안 바꿈"},
       "failrate": {"verdict": q["q105"]["verdict"], "why": q["q105"]["why"], "now": q["q105"]["now"],
                    "note": ("앞 기간에서 고른 N20 은 시험 기간 샤프 1.09 < 기준 1.13 → ❌. N100 변형은 시험 기간 최대낙폭을 −19.5→−17% 로 줄였지만 "
                             "결과를 보고 고르는 셈이라 채택 안 함. 뼈대 변동성 맞춤은 그대로(15%).")}}
(ROOT / "market" / "q10_bt.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (v.get("verdict") if isinstance(v, dict) else v) for k, v in out.items()}, ensure_ascii=False))
