"""🌃 한국 「종가 매수 → 다음 날 시가 매도」 그림자 기록 (10/22 사용자 「다 진행」 — 퀀트 운용사 조사 ⑤·⑥)

  밤 연구 #12(src/lab/k1022_overnight.py): 급등(+5~15%)·거래 3배↑ 종목을 종가에 사서 다음 날 시가에 팔면
  시험 구간(2025-04~) 비용 0.45% 뺀 평균 +0.31%·손익비 1.33(2,658건) vs 같은 종목 다음 날 장중 −0.68%.
  다만 고르는 구간(2023~2025-04)에선 −0.08%였고, 조건 없는 모든 종목도 최근엔 밤사이가 좋아짐 → 최근 상승장 몫이 섞였을 수 있음.
  그래서 바로 알림으로 쓰지 않고 그림자로만 4주 이상 쌓는다(운용사의 「작게 실전 → 키우기」).
  · 매일 저녁: 유니버스(stock-screener universe_latest.csv)에서 그날 신호를 적고, 지난 신호는 다음 날 시가로 채점
  · 문턱: 20거래일 · 40건 이상 · 비용 뺀 평균 > 0 · 손익비 ≥ 1.3 → state 「✅ 알림 후보」(사람이 켤지 정함), 아니면 「👻 기록 중」
→ market/kr_overnight.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "market" / "kr_overnight.json"
KST = dt.timezone(dt.timedelta(hours=9))
BAND, VM, COST = (5.0, 15.0), 3.0, 0.45
GATE_DAYS, GATE_N, GATE_PF = 20, 40, 1.3
FROM = "2026-10-22"          # 이 날 신호부터 그림자 기록 (소급 안 함)


def stat(rs):
    if not rs:
        return {"n": 0}
    w = [r for r in rs if r > 0]; l = [r for r in rs if r <= 0]
    return {"n": len(rs), "win": round(len(w) / len(rs) * 100), "avg": round(sum(rs) / len(rs), 2),
            "pf": round(sum(w) / -sum(l), 2) if l and sum(l) < 0 else None}


def main() -> int:
    import numpy as np
    from src.lab.k1022_overnight import fetch_csv, download
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    log = {f"{x['d']}|{x['code']}": x for x in prev.get("log", [])}
    U = fetch_csv("universe_latest.csv")
    tick = [str(c).zfill(6) + (".KS" if m == "KOSPI" else ".KQ") for c, m in zip(U["code"], U["market"])]
    name = {str(c).zfill(6): n for c, n in zip(U["code"], U["name"])}
    start = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    px, fail = download(tick, start=start)
    days = set()
    for t, s in px.items():
        s = s.copy()
        s.index = s.index.tz_localize(None).normalize() if s.index.tz is not None else s.index.normalize()
        s = s[(s["Open"] > 0) & (s["Volume"] > 0)]
        if len(s) < 22:
            continue
        code = t.split(".")[0]
        C, V, O = s["Close"], s["Volume"], s["Open"]
        ret = (C / C.shift(1) - 1) * 100
        vm = V / V.shift(1).rolling(20, min_periods=15).mean()
        idx = [d.strftime("%Y-%m-%d") for d in s.index]
        days.update(idx)
        for i in range(1, len(s)):
            d = idx[i]
            if d < FROM:
                continue
            k = f"{d}|{code}"
            if k not in log and BAND[0] <= ret.iloc[i] <= BAND[1] and vm.iloc[i] >= VM:
                log[k] = {"d": d, "code": code, "name": name.get(code, code), "close": round(float(C.iloc[i]), 2),
                          "ret": round(float(ret.iloc[i]), 2), "vm": round(float(vm.iloc[i]), 1)}
            if k in log and log[k].get("r") is None and i + 1 < len(s):
                o1 = float(O.iloc[i + 1])
                log[k].update({"open1": round(o1, 2), "d1": idx[i + 1], "r": round((o1 / log[k]["close"] - 1) * 100 - COST, 2)})
    L = sorted(log.values(), key=lambda x: (x["d"], x["code"]))
    done = [x for x in L if x.get("r") is not None]
    st = stat([x["r"] for x in done])
    nd = len({x["d"] for x in done})
    ok = nd >= GATE_DAYS and st["n"] >= GATE_N and (st.get("avg") or 0) > 0 and (st.get("pf") or 0) >= GATE_PF
    by_day = {}
    for x in done:
        by_day.setdefault(x["d"], []).append(x["r"])
    out = {"at": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "from": FROM,
           "rule": f"등락 +{BAND[0]:.0f}~{BAND[1]:.0f}% · 거래 20일 평균 {VM:.0f}배↑ → 그날 종가 매수 · 다음 날 시가 매도 · 비용 {COST}% 뺌",
           "state": "✅ 알림 후보 (사람이 켤지 정함)" if ok else "👻 기록 중",
           "gate": {"days": GATE_DAYS, "n": GATE_N, "pf": GATE_PF, "now_days": nd, "now_n": st["n"]},
           "stat": st, "day_port": stat([float(np.mean(v)) for v in by_day.values()]),
           "today": [x for x in L if x.get("r") is None], "log": L[-400:], "fail": len(fail),
           "note": "밤 연구 #12 ✅(시험 구간) 이지만 고르는 구간은 −였고 최근 상승장 몫이 섞였을 수 있어 그림자 기록부터. 매수 추천 아님."}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out["state"], out["stat"], "대기", len(out["today"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
