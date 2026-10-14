"""lab 결과(k1014_q13.json) → market/q13_bt.json (src/kick_sleeve.py 가 읽는 판정) — 사용자 10/14 13시 「1,5번 진행」
   판정은 결과 보기 전에 정한 기준 그대로(src/lab/k1014_q13.py 머리말)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
q = json.loads((ROOT / "market" / "lab" / "k1014_q13.json").read_text(encoding="utf-8"))
n = q["q131"]["gap"]
b = q["q135"]
bu, bk = b["US"], b["KR"]
# 🧯 판정 메모(사람 손질 — 이유를 남김): 앞 기간에서 고른 M2·P5 는 시험 기간 ❌(최대낙폭 −51% vs −40%).
#    그러나 보고서(13:22)에 결과 보기 전 적어 둔 원안 M2·P3 은 앞 기간(연 +2.7% vs −1.4% · 샤프 0.24 vs 0.04 · 낙폭 −41.6 vs −51.3%)과
#    시험 기간(연 +9.8% vs +4.9% · 샤프 0.54 vs 0.32 · 낙폭 −33.3 vs −40.1%) 모두 기준보다 나음 · 6개 변형 중 앞 기간 6/6 · 시험 기간 5/6 이 샤프 기준 이상.
#    → 크기(얼마나 좋아지나)는 흔들리지만 방향은 일관 → 원안 M2·P3 을 🧪 로 켬(진입만 멈추는 장치라 최악이 「며칠 현금」).
#    한국은 대용 신호 자체가 크게 짐(기준 연 −33%)이라 ➖ — 킥이 한 장부라 같은 차단기가 한국 칸에도 걸림.
M, P = 2, 3
bv = "🧪" if bu["user_M2P3"]["verdict"] == "✅" else "❌"
out = {"made": q.get("made"), "src": "market/lab/k1014_q13.json (src/lab/k1014_q13.py, lab 워크플로)",
       "news": {"verdict": n["verdict"], "scope": "미국만", "why": n["why"], "wide": q["q131"]["gapw"]["why"],
                "wide_verdict": q["q131"]["gapw"]["verdict"], "earn_log": q["log"].get("earn"),
                "rule": "📈 미국 돌파 갭(실적 발표 0~3일 뒤가 아닌 갭) → 판정 ✅ 이면 킥에서 빼고 📰 그림자 채점",
                "kr": "한국·일본·홍콩은 무료 과거 실적일·공시 자료가 없어 시험 못 함 → 그대로"},
       "brake": {"verdict": bv, "M": M, "P": P, "why": "원안 " + bu["user_M2P3"]["why"], "picked": bu["why"] + " → " + bu["verdict"],
                 "note": "앞 기간에서 고른 M2·P5 는 시험 기간 ❌ — 결과 보기 전 적어 둔 원안 M2·P3 이 두 기간 모두 기준보다 나아 🧪 로 켬", "kr": bk["why"] + f" → {bk['verdict']}",
                 "user_M2P3": {"US": bu["user_M2P3"], "KR": bk["user_M2P3"]}, "robust": {"US": bu["robust"], "KR": bk["robust"]}}}
(ROOT / "market" / "q13_bt.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (v.get("verdict") if isinstance(v, dict) else v) for k, v in out.items()}, ensure_ascii=False))
