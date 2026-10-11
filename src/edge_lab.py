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
    """raw 가 막힌 환경(예약 세션 프록시)에서는 DAILY_APP_DIR(daily-app 클론)에서 읽는다"""
    import os
    try:
        with urllib.request.urlopen(urllib.request.Request(RAW + path, headers={"User-Agent": "ch-edge"}), timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception:
        loc = os.environ.get("DAILY_APP_DIR")
        if not loc:
            raise
        return json.loads((Path(loc) / path).read_text(encoding="utf-8"))


def stat(v):
    v = [x for x in v if x is not None]
    if not v:
        return None
    w = sum(1 for x in v if x > 0)
    return {"n": len(v), "avg": round(st.mean(v), 2), "med": round(st.median(v), 2), "win": round(w / len(v) * 100), "pf": round(sum(x for x in v if x > 0) / max(0.01, -sum(x for x in v if x < 0)), 2)}


# ── 정직 버전 (10/11 사용자: 「지금 숫자 + 정직 숫자 둘 다」) ──────────────────────────────
#   신호는 장 마감 뒤에 계산되므로 신호 날 종가는 살 수 없다 → 「다음 날 종가」에 산다고 보고,
#   왕복 비용(수수료·세금·환전 스프레드)을 뺀다. 그리고 표본을 날짜순 반으로 갈라 「뒤 절반」(oos)을 따로 보여 준다.
#   insample=True 는 그 필터(컵 손잡이·RS·늦은 돌파, 갭 4-8%)를 같은 표본으로 고른 것이라 숫자가 부풀 수 있다는 표시.
COST = {"KR": 0.45}          # 왕복 % — 그 밖(미국·일본·홍콩·중국)은 0.5 (환전 스프레드 포함)
COST_ETC = 0.5
BASIS = "다음 날 종가 진입 · 왕복 비용 0.5%(미국·일본·홍콩·중국)/0.45%(한국)"


def cost_of(mkt):
    return COST.get(mkt or "", COST_ETC)


def path_ret(p, i):
    """% 경로 p 에서 i 번째 종가에 사서 마지막 종가까지 (보유 하루 이상일 때만)"""
    if not p or i is None or i + 1 >= len(p):
        return None
    return ((1 + p[-1] / 100) / (1 + p[i] / 100) - 1) * 100


def honest(rows, insample, note=""):
    """rows: [(날짜, 비용 빼기 전 %, 시장)] → 정직 성적 + 날짜순 뒤 절반(oos)"""
    rows = sorted((d or "", r - cost_of(m)) for d, r, m in rows if r is not None)
    s = stat([r for _, r in rows]) or {"n": 0}
    h = len(rows) // 2
    oos = stat([r for _, r in rows[h:]]) if len(rows) >= 4 else None
    ins = stat([r for _, r in rows[:h]]) if len(rows) >= 4 else None
    for o in (s, oos, ins):            # 지는 거래가 거의 없으면 손익비가 수천이 됨 → 100↑ 은 「계산 불가」(None)
        if o and (o.get("pf") or 0) >= 100:
            o["pf"] = None
    return {**s, "basis": BASIS + (f" · {note}" if note else ""), "insample": insample,
            "oos": ({k: oos[k] for k in ("n", "avg", "pf", "win")} | {"from": rows[h][0]}) if oos else None,
            "is": {k: ins[k] for k in ("n", "avg", "pf", "win")} if ins else None}


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
        # 10/10 엣지 연구: bnow 는 「피벗」 기준이라 돌파 당일 점프(중앙 +4.5%)까지 들어가 부풀려진다.
        # 킥은 돌파일 「종가」에 사므로 실제로 먹을 수 있는 수익 = 돌파일 종가 → 지금 (bpath[bpi] → bpath[-1]).
        def real(x):
            p, i = x.get("bpath"), x.get("bpi")
            if not p or i is None or i >= len(p):
                return None
            return round(((1 + p[-1] / 100) / (1 + p[i] / 100) - 1) * 100, 2)

        def ext(x):
            p, i = x.get("bpath"), x.get("bpi")
            return p[i] if p and i is not None and i < len(p) else None
        try:
            KP = json.loads((ROOT / "market" / "kick_params.json").read_text(encoding="utf-8"))
        except Exception:
            KP = {}
        for x in brk:
            x["_real"], x["_ext"] = real(x), ext(x)
        kf = [x for x in brk if (x.get("f_handle") or 0) >= KP.get("cup_min_handle", 0) and (x.get("f_rs") or 0) >= KP.get("cup_min_rs", 0)
              and (not KP.get("cup_mkts") or x.get("mkt") in KP["cup_mkts"]) and x["_ext"] is not None and x["_ext"] < KP.get("cup_max_ext", 999)]
        E["cup"].update({"brk_real": stat([x["_real"] for x in brk]),
                         "brk_real_by_ext": {lab: stat([x["_real"] for x in brk if x["_ext"] is not None and lo <= x["_ext"] < hi])
                                             for lo, hi, lab in [(-99, 3, "피벗+3%미만"), (3, 7, "3-7%"), (7, 12, "7-12%"), (12, 999, "12%+")]},
                         "brk_real_by_mkt": {m: stat([x["_real"] for x in brk if x.get("mkt") == m]) for m in ("US", "KR", "JP", "CN", "HK")},
                         "brk_real_kick": stat([x["_real"] for x in kf])})
        # 정직: 돌파일 「다음 날」 종가에 사서 지금(돌파 뒤 최대 30일)까지 · 비용 뺌 · 킥 필터(손잡이·RS·늦은 돌파)는 같은 표본으로 고른 것
        nx = lambda x: path_ret(x.get("bpath"), (x["bpi"] + 1) if x.get("bpi") is not None else None)
        E["cup"]["honest"] = honest([(x.get("brkd"), nx(x), x.get("mkt")) for x in kf], True, "킥 필터 적용 · 필터를 같은 표본으로 고름")
        E["cup"]["honest_all"] = honest([(x.get("brkd"), nx(x), x.get("mkt")) for x in brk], False, "필터 없는 컵 돌파 전체")
    except Exception as e:
        E["cup_err"] = str(e)[:80]
    try:
        G = gj("archive/x/perf_gap.json")["signals"]
        E["gap"] = {t: stat([x["now"] for x in G if x.get("gtype") == t]) for t in ("돌파 갭", "진행 갭", "반등 갭")}
        bg = [x for x in G if x.get("gtype") == "돌파 갭"]
        E["gap"]["돌파_by_size"] = cut(bg, "gap", [(0, 4, "갭<4%"), (4, 8, "4-8%"), (8, 100, "8%+")])
        E["gap"]["돌파_by_vol"] = cut(bg, "vol", [(0, 3, "거래<3배"), (3, 6, "3-6배"), (6, 100, "6배+")])
        E["gap"]["돌파_filled_vs_held"] = {"메움": stat([x["now"] for x in bg if x.get("filled")]), "유지": stat([x["now"] for x in bg if not x.get("filled")])}
        b48 = [x for x in bg if x.get("gap") is not None and 4 <= x["gap"] < 8]
        E["gap"]["honest"] = honest([(x.get("d0"), path_ret(x.get("path"), 1), x.get("mkt")) for x in b48], True, "갭 4-8% 구간은 같은 표본으로 고름")
    except Exception as e:
        E["gap_err"] = str(e)[:80]
    try:
        A = gj("archive/x/perf_accum.json")["signals"]
        E["accum"] = {"all": stat([x["now"] for x in A]), "brk": stat([x["now"] for x in A if x.get("abrk")]), "nobrk": stat([x["now"] for x in A if not x.get("abrk")])}
        # 정직: 박스 돌파 「다음 날」 종가에 사서 지금까지 (abd = 신호 뒤 몇 번째 봉에서 돌파)
        E["accum"]["honest"] = honest([(x.get("d0"), path_ret(x.get("path"), int(x["abd"]) + 1), x.get("mkt")) for x in A if x.get("abrk") and x.get("abd") is not None],
                                      False, "박스 돌파 다음 날 진입")
        E["accum"]["honest_all"] = honest([(x.get("d0"), path_ret(x.get("path"), 1), x.get("mkt")) for x in A], False, "신호 전체 · 신호 다음 날 진입")
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
