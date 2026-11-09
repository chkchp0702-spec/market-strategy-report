"""🌱 11/9 사용자 「1번 다시 보고」 — 🐻 하락장 계기판 「바닥 신호 → 다시 사기」 규칙 다시 보기
  배경: A11/9-1 성적표(bear_sig_bt.json)에서 코스피 하락장 10번 중 「신호 2개 처음 켜진 날」 뒤 6개월 − 6번 · 바닥이 더 남은 때 8번
        → 지금 규칙(신호 2·3·4개 → 현금 30→20→10→0)이 너무 일찍 다시 사는 것 아닌가.
  판정(🟢/🟡/🐻)·바닥 신호 4개 정의는 그대로 두고 「현금을 언제 얼마나 줄이나」만 바꾼 판 7개를 결과 보기 전에 적어 둠:
    A 지금 규칙        🐻 30·30·20·10·0 / 🟡 10·10·5·0·0 (신호 0~4개)
    B 3개부터          🐻 30·30·30·10·0 / 🟡 10·10·10·0·0
    C 저점 다지기 먼저 ① 안 켜졌으면 신호 수와 상관없이 최대 현금 · 켜지면 A
    D 5일 유지         신호 수 = 최근 5거래일 중 가장 적었던 날 수로 A
    E 추세 확인        🐻 30 → ①+④(50일선) 10 → ①+②+④ 0 / 🟡 10 → ①+④ 0 (② VIX 안 씀)
    F 신호 안 씀       판정만(🐻 30 · 🟡 10 · 🟢 0) — 판정이 풀릴 때까지 현금 유지
    G 나눠 사기+리셋   신호 2개 처음 켜진 날부터 20거래일마다 현금 ⅓씩 줄임 · 60일 새 저점(①이 0일)이 나오면 최대 현금으로 되돌림
    H 그냥 보유
  재는 것: 연수익·최대낙폭(전체 · 앞 2000~2012 · 뒤 2013~) · 하락장 구간 수익(규칙 vs 보유) · 바꾸는 횟수
           「처음 다시 사기 시작한 날」 뒤 6개월 + / − · 바닥이 더 남은 때 — 코스피·S&P500·나스닥
  규칙: 앞·뒤 두 구간 × 세 시장에서 A 보다 낫거나 같을 때만 「바꿀 만함」. 판 7개라 운으로 하나쯤 좋아 보일 수 있음 — 앞에서 1등이 뒤에서도 버티나 본다.
  현금 연 2% · 비중 바꿀 때 0.1% · 다음 날 비중 · 가격지수(배당 제외) · 🇰🇷 ④ 과거는 50일선(외국인 자료 없음)
→ market/lab/b1109_floor.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.bear_gate import judge, aligned_vix, load, MKTS, H6

OUT = Path("market/lab/b1109_floor.json")
SPLIT = "2013-01-01"
MAXC = {"🐻": 30, "🟡": 10, "🟢": 0}
A_ = {"🐻": [30, 30, 20, 10, 0], "🟡": [10, 10, 5, 0, 0], "🟢": [0] * 5}
B_ = {"🐻": [30, 30, 30, 10, 0], "🟡": [10, 10, 10, 0, 0], "🟢": [0] * 5}
VARS = {"A": "지금 규칙", "B": "3개부터", "C": "저점 다지기 먼저", "D": "5일 유지", "E": "추세 확인(①+④→②)",
        "F": "신호 안 씀(판정만)", "G": "나눠 사기+새 저점 리셋", "H": "그냥 보유"}


def days(cl, vx, start=252):
    pb, out = False, []
    for i in range(start, len(cl)):
        j = judge(cl, vx, None, "us", pb, i)
        pb = j["state"] == "🐻"
        ons = [bool(c["on"]) for c in j["checks"]]
        w = cl[max(0, i - 59):i + 1]
        lo = min(w)
        lo_ago = len(w) - 1 - max(k for k, x in enumerate(w) if x == lo)
        out.append({"i": i, "st": j["state"], "ons": ons, "n": sum(ons), "lo_ago": lo_ago})
    return out


def cash_series(D, v):
    cs, g = [], None
    for k, d in enumerate(D):
        st, n, ons = d["st"], d["n"], d["ons"]
        if st == "🟢" or v == "H":
            c = 0
            g = None
        elif v == "A":
            c = A_[st][n]
        elif v == "B":
            c = B_[st][n]
        elif v == "C":
            c = MAXC[st] if not ons[0] else A_[st][n]
        elif v == "D":
            nn = min(x["n"] if x["st"] != "🟢" else 0 for x in D[max(0, k - 4):k + 1])
            c = A_[st][nn]
        elif v == "E":
            if st == "🐻":
                c = 0 if (ons[0] and ons[1] and ons[3]) else 10 if (ons[0] and ons[3]) else 30
            else:
                c = 0 if (ons[0] and ons[3]) else 10
        elif v == "F":
            c = MAXC[st]
        elif v == "G":
            if g is None or g["st"] != st:
                g = {"st": st, "c": MAXC[st], "t0": None}
            if d["lo_ago"] == 0:
                g["c"], g["t0"] = MAXC[st], None
            elif g["t0"] is None and n >= 2:
                g["t0"] = k
            if g["t0"] is not None and (k - g["t0"]) % 20 == 0 and k > g["t0"] - 1:
                g["c"] = max(0, g["c"] - MAXC[st] / 3)
            c = round(g["c"], 1)
        cs.append(c)
    return cs


def run(cl, dates, D, cs, lo_d=None, hi_d=None):
    nav, bh, pn, pb_, mn, mb, sw, w_prev, n_days = 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0, 1 - cs[0] / 100, 0
    for k in range(1, len(D)):
        i = D[k]["i"]
        if lo_d and dates[i] < lo_d:
            w_prev = 1 - cs[k] / 100
            continue
        if hi_d and dates[i] >= hi_d:
            break
        r = cl[i] / cl[i - 1] - 1
        nav *= 1 + w_prev * r + (1 - w_prev) * 0.02 / 252
        bh *= 1 + r
        pn, pb_ = max(pn, nav), max(pb_, bh)
        mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb_ - 1)
        w = 1 - cs[k] / 100
        if abs(w - w_prev) > 1e-9:
            nav *= 1 - 0.001 * abs(w - w_prev)
            sw += 1
        w_prev = w
        n_days += 1
    y = n_days / 252
    return {"cagr": round((nav ** (1 / y) - 1) * 100, 2), "mdd": round(mn * 100, 1),
            "hold_cagr": round((bh ** (1 / y) - 1) * 100, 2), "hold_mdd": round(mb * 100, 1), "sw_y": round(sw / y, 1)}


def reentry(cl, dates, D, cs):
    """하락장마다: 현금이 최대에서 처음 줄어든 날 → 6개월 뒤 · 그 하락장 바닥이 그 뒤에 남았나"""
    eps, cur = [], None
    for k, d in enumerate(D):
        if d["st"] == "🐻" and cur is None:
            cur = {"k0": k}
        if cur is not None and d["st"] != "🐻":
            cur["k1"] = k
            eps.append(cur)
            cur = None
    res = []
    for ep in eps:
        ks = range(ep["k0"], ep["k1"])
        b = min(ks, key=lambda k: cl[D[k]["i"]])
        f = next((k for k in ks if cs[k] < 30), None)
        if f is None:
            res.append({"in": dates[D[ep["k0"]]["i"]], "first": None})
            continue
        i = D[f]["i"]
        r6 = round((cl[i + H6] / cl[i] - 1) * 100, 1) if i + H6 < len(cl) else None
        res.append({"in": dates[D[ep["k0"]]["i"]], "first": dates[i], "r6": r6, "early": f < b,
                    "more": round((cl[D[b]["i"]] / cl[i] - 1) * 100, 1) if f < b else 0.0})
    pos = sum(1 for x in res if x.get("r6") is not None and x["r6"] > 0)
    neg = sum(1 for x in res if x.get("r6") is not None and x["r6"] <= 0)
    return {"eps": len(res), "pos6": pos, "neg6": neg, "early": sum(1 for x in res if x.get("early")),
            "never": sum(1 for x in res if not x.get("first")), "rows": res}


def study(name, cl, dates, vx):
    D = days(cl, vx)
    out = {"name": name, "from": dates[D[0]["i"]], "to": dates[-1], "vars": {}}
    for v in VARS:
        cs = cash_series(D, v)
        out["vars"][v] = {"name": VARS[v], "all": run(cl, dates, D, cs), "is": run(cl, dates, D, cs, None, SPLIT),
                          "oos": run(cl, dates, D, cs, SPLIT, None), "re": reentry(cl, dates, D, cs) if v != "H" else None}
    return out


def main():
    res = {"at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "vars": VARS, "split": SPLIT, "markets": []}
    if "--local" in sys.argv:   # 세션 시험용(VIX 없음 · ③ 안 켜짐)
        j = json.load(open(sys.argv[sys.argv.index("--local") + 1]))
        d, dates = dt.date.fromisoformat(j["d0"]), []
        for x in j["dd"]:
            d = d + dt.timedelta(days=x)
            dates.append(d.isoformat())
        res["markets"].append(study("코스피(로컬·VIX 없음)", j["c"][:-1], dates[:-1], None))
    else:
        px = load("1999-01-01")
        vix = px.get("vix")
        for key, _, name, nat, _ in MKTS:
            s = px.get(key)
            if s is None:
                continue
            cl = [float(x) for x in s.tolist()]
            res["markets"].append(study(name, cl, [str(t.date()) for t in s.index], aligned_vix(s, vix)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if "--local" not in sys.argv:
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in res["markets"]:
        print("\n==", m["name"], m["from"], "~", m["to"])
        print(f"{'판':<22}{'전체 연·낙폭':>16}{'앞(~2012)':>16}{'뒤(2013~)':>16}{'바꿈/년':>8}  처음 다시 산 날 6개월 +/− · 바닥 남음")
        for v, x in m["vars"].items():
            re_ = x["re"]
            print(f"{v} {x['name']:<20}{x['all']['cagr']:>7.2f}{x['all']['mdd']:>7.1f}  {x['is']['cagr']:>7.2f}{x['is']['mdd']:>7.1f}  {x['oos']['cagr']:>7.2f}{x['oos']['mdd']:>7.1f}  {x['all']['sw_y']:>6.1f}  "
                  + (f"+{re_['pos6']} −{re_['neg6']} · 남음 {re_['early']}/{re_['eps']}" if re_ else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
