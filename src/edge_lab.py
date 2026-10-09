"""🔬 엣지 연구실 — 우리 장부(컵·갭·매집·집중·킥)에서 「무엇이 실제로 이겼나」를 숫자로 뽑는다.
   주간 예약 작업(엣지 연구)이 이 출력을 읽고 kick_params.json 을 고친다.
   python -m src.edge_lab  → market/edge.json + 표준출력 요약
"""
from __future__ import annotations
import datetime as dt
import json
import statistics as st
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/"


def gj(path):
    with urllib.request.urlopen(urllib.request.Request(RAW + path, headers={"User-Agent": "ch-edge"}), timeout=40) as r:
        return json.loads(r.read().decode())


def stat(v):
    v = [x for x in v if x is not None]
    if not v:
        return None
    w = sum(1 for x in v if x > 0)
    return {"n": len(v), "avg": round(st.mean(v), 2), "med": round(st.median(v), 2), "win": round(w / len(v) * 100), "pf": round(sum(x for x in v if x > 0) / max(0.01, -sum(x for x in v if x < 0)), 2)}


def cut(xs, key, bins):
    out = {}
    for lo, hi, lab in bins:
        sub = [x for x in xs if x.get(key) is not None and lo <= x[key] < hi]
        out[lab] = stat([x["bnow"] if "bnow" in x else x.get("now") for x in sub])
    return out


def main():
    E = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")}
    try:
        C = gj("archive/x/perf_cup.json")["signals"]
        brk = [x for x in C if x.get("brk")]
        E["cup"] = {"all_now": stat([x["now"] for x in C]), "brk_now": stat([x["bnow"] for x in brk]),
                    "brk_by_mkt": {m: stat([x["bnow"] for x in brk if x.get("mkt") == m]) for m in ("US", "KR", "JP", "CN", "HK")},
                    "brk_by_score": cut(brk, "score", [(0, 50, "<50"), (50, 65, "50-65"), (65, 101, "65+")]),
                    "brk_by_rs": cut(brk, "f_rs", [(0, 50, "RS<50"), (50, 70, "RS50-70"), (70, 101, "RS70+")]),
                    "brk_by_depth": cut(brk, "f_depth", [(0, 20, "얕음<20"), (20, 35, "20-35"), (35, 100, "깊음35+")]),
                    "brk_by_handle": cut(brk, "f_handle", [(0, 4, "손잡이<4일"), (4, 10, "4-10일"), (10, 100, "10일+")]),
                    "brk_status": {k: sum(1 for x in brk if x.get("bst") == k) for k in ("진행", "성공", "실패")}}
    except Exception as e:
        E["cup_err"] = str(e)[:80]
    try:
        G = gj("archive/x/perf_gap.json")["signals"]
        E["gap"] = {t: stat([x["now"] for x in G if x.get("gtype") == t]) for t in ("돌파 갭", "진행 갭", "반등 갭")}
        bg = [x for x in G if x.get("gtype") == "돌파 갭"]
        E["gap"]["돌파_by_size"] = cut(bg, "gap", [(0, 4, "갭<4%"), (4, 8, "4-8%"), (8, 100, "8%+")])
        E["gap"]["돌파_by_vol"] = cut(bg, "vol", [(0, 3, "거래<3배"), (3, 6, "3-6배"), (6, 100, "6배+")])
        E["gap"]["돌파_filled_vs_held"] = {"메움": stat([x["now"] for x in bg if x.get("filled")]), "유지": stat([x["now"] for x in bg if not x.get("filled")])}
    except Exception as e:
        E["gap_err"] = str(e)[:80]
    try:
        A = gj("archive/x/perf_accum.json")["signals"]
        E["accum"] = {"all": stat([x["now"] for x in A]), "brk": stat([x["now"] for x in A if x.get("abrk")]), "nobrk": stat([x["now"] for x in A if not x.get("abrk")])}
    except Exception as e:
        E["accum_err"] = str(e)[:80]
    try:
        K = json.loads((ROOT / "market" / "kick.json").read_text(encoding="utf-8"))
        cl = K.get("closed_all") or K.get("closed", [])
        E["kick"] = {"all": stat([t["r"] for t in cl]), "by_src": {}, "stat": K.get("stat"), "params": json.loads((ROOT / "market" / "kick_params.json").read_text(encoding="utf-8"))}
        for t in cl:
            E["kick"]["by_src"].setdefault(t["src"], []).append(t["r"])
        E["kick"]["by_src"] = {k: stat(v) for k, v in E["kick"]["by_src"].items()}
        full = K.get("closed", [])
        E["kick"]["by_why"] = {}
        for t in full:
            E["kick"]["by_why"].setdefault(t.get("why", "?"), []).append(t["r"])
        E["kick"]["by_why"] = {k: stat(v) for k, v in E["kick"]["by_why"].items()}
    except Exception as e:
        E["kick_err"] = str(e)[:80]
    try:
        L = json.loads((ROOT / "market" / "focus_log.json").read_text(encoding="utf-8"))
        done = [x for x in L if x.get("res") is not None]
        E["focus"] = {"n": len(done), "ex_vs_spy": stat([x["res"] for x in done]),
                      "by_stage": {s: stat([x["res"] for x in done if x.get("stage") == s]) for s in ("초입", "주도", "과열", "꺾임")}}
    except Exception as e:
        E["focus_err"] = str(e)[:80]
    (ROOT / "market" / "edge.json").write_text(json.dumps(E, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(E, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    sys.exit(main())
