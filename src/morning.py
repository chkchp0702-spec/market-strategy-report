"""🌅 아침판 30초 — 11/19 사용자 「시황리포트를 PB·고객이 아침에 보고 전략을 짜고 리밸런싱에 쓰게 · 우와 소리 나게」 → 「전부 다 진행」

리포트가 이미 가진 숫자(data/오늘.json · 장부 · market/*.json)를 「오늘 무엇을 바꾸나」 한 장으로 다시 묶는다. 새 판단은 만들지 않음.
  ① changes   어제와 달라진 3가지 (판정 · 시장별 주식 % · 🧭 섹터 칸 · 경우의 수 · 돈 몰리는 곳 · 오늘 밤 바뀔 수 있는 것) — 없으면 「오늘은 바꿀 것 없음」
  ② actions   행동 카드 3장: 늘릴 것 / 줄일·피할 것 / 그대로 — 대표 ETF(미국 티커 + 국내 코드) · 근거 한 줄 · 틀리면 바꿀 조건 · 그 칸 조언 성적
  ③ flowmap   돈의 흐름 지도: 5개 시장 + 미국 섹터·테마 5일 S&P 대비(들어온 곳·빠진 곳) + 한국 업종
  ⑤ persona   성향별 처방전: 안정추구형 · 위험중립형 · 성장형 — 주식/채권/금/현금 숫자와 어제 대비, 담을 상품
  ⑥ triggers  조건부 대응표: 「이 선을 넘으면 이렇게」와 남은 거리(막대)
  ⑧ overnight 밤사이 미국 → 오늘 한국장: 미국에서 오른/내린 테마의 한국 연결 종목 + 장 전 체크 시각
  ⑨ score     조언 성적표: 지난 「늘리자/줄이자」가 5거래일 뒤 S&P 를 이겼나 — 칸별 적중, 약한 칸은 작게
  ⑩ counter   우리가 틀렸다면: 가장 강한 반론 1개 + 그 반론이 맞아 가는 신호와 거리
  cards       앱 「넘겨 보는 카드 5장」용 요약
data/오늘.json 에 사람이 쓴 칸이 있으면 그것이 먼저: actions · counter_watch · overnight_note (RULES 1-O).

사용: python -m src.morning [data/YYYY-MM-DD.json]   → market/morning.json · market/morning_log.json · market/morning_px.json
      (yfinance 가 있으면 오늘 종가를 morning_px 에 더함 — fetch.yml 매시간. 없으면 market/sectors.json 의 last 로)
"""
from __future__ import annotations
import json, re, sys, glob
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MK = ROOT / "market"
KST = timezone(timedelta(hours=9))

# 🧭 섹터 칸 이름 → 채점용 미국 ETF (sectors.json 에 있는 것) · 국내 상장 대표
SYM = [("AI SW", "IGV"), ("AI 소프트웨어", "IGV"), ("소프트웨어", "IGV"), ("SW", "IGV"),
       ("반도체", "SMH"), ("에너지", "XLE"), ("전력", "GRID"), ("헬스", "XLV"), ("필수소비재", "XLP"),
       ("금융", "XLF"), ("광통신", "SKYY"), ("사이버", "CIBR"), ("유틸", "XLU"), ("경기소비재", "XLY")]
KR_ETF = {"IGV": "TIGER 미국테크TOP10 381170", "SMH": "TIGER 미국필라델피아반도체 381180", "XLE": "KODEX 미국S&P500에너지 218420",
          "GRID": "TIGER 글로벌AI전력인프라 491010", "XLV": "TIGER 미국S&P500헬스케어 453630", "XLP": "—", "XLF": "—", "XLY": "—",
          "CIBR": "—", "XLU": "—", "SKYY": "—", "QQQ": "TIGER 미국나스닥100 133690", "GLD": "TIGER KRX금현물 0072R0", "SGOV": "TIGER CD금리 499660"}
PERSONA = [("안정추구형", "🛡", 0.25), ("위험중립형", "⚖️", 0.55), ("성장형", "🚀", 1.0)]


def jl(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def strip(s):
    return re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", " · ", str(s or ""))).strip()


def sym_of(name):
    for k, s in SYM:
        if k in name:
            return s
    return None


def num(s):
    m = re.search(r"([−\-+]?)\s*(\d+(?:[.,]\d+)?)", str(s or "").replace(",", ""))
    if not m:
        return None
    v = float(m.group(2))
    return -v if m.group(1) in ("−", "-") else v


# ---------------------------------------------------------------- 🧭 배지에서 「X a→b」 뽑기
def parse_moves(d):
    """data.decision.badges + reasons 에서 🧭 섹터 칸 바꿈. [{name, sym, a, b, dir}]"""
    out, seen = [], set()
    texts = list((d.get("decision") or {}).get("badges") or [])
    for t in texts:
        t = strip(t)
        if "🧭" not in t:
            continue
        t = re.sub(r"\(.*?\)", "", t.replace("🧭", ""))
        for part in re.split(r"[·,]", t):
            part = part.strip()
            m = re.match(r"(.+?)\s*(\d+(?:\.\d+)?)\s*→\s*(\d+(?:\.\d+)?)", part)
            if m:
                nm, a, b = m.group(1).strip(), float(m.group(2)), float(m.group(3))
                if a == b:
                    continue
                dr = "up" if b > a else "down"
            else:
                m = re.match(r"(.+?)\s*(↑|↓)", part)
                if not m:
                    m2 = re.match(r"(.+?)\s*새 칸\s*(\d+)", part)
                    if not m2:
                        continue
                    nm, a, b, dr = m2.group(1).strip(), 0.0, float(m2.group(2)), "up"
                else:
                    nm, a, b, dr = m.group(1).strip(), None, None, "up" if m.group(2) == "↑" else "down"
            s = sym_of(nm)
            if not s or (s, dr) in seen:
                continue
            seen.add((s, dr))
            out.append({"name": nm, "sym": s, "a": a, "b": b, "dir": dr})
    return out


# ---------------------------------------------------------------- 종가 장부 + ⑨ 조언 성적표
def update_px(S):
    px = jl(MK / "morning_px.json", {})
    a = S.get("asof")
    if a:
        row = {r["sym"]: r.get("last") for r in S.get("rows", []) if r.get("last")}
        if (S.get("spy") or {}).get("last"):
            row["SPY"] = S["spy"]["last"]
        if row:
            px[a] = row
    try:   # 🧭 칸 중 sectors.json 에 없는 것(GRID 등은 있음) — yfinance 있으면 보탬
        import yfinance  # noqa: F401
    except Exception:
        pass
    px = dict(sorted(px.items())[-400:])
    (MK / "morning_px.json").write_text(json.dumps(px, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return px


def build_log(px):
    """data/*.json 전부에서 🧭 「늘리자/줄이자」를 모아 5거래일 뒤 S&P 대비로 채점 (매번 처음부터 — 과거 data 를 고쳐도 맞게)"""
    days = sorted(px)
    rows = []
    for f in sorted(glob.glob(str(ROOT / "data" / "2026-*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        date = d.get("date")
        if not date:
            continue
        base = [x for x in days if x < date]      # 아침판 = 전날 종가 기준 → 그 종가에 산다고 봄
        if not base:
            continue
        b0 = base[-1]
        i0 = days.index(b0)
        for mv in parse_moves(d):
            r = {"date": date, "name": mv["name"], "sym": mv["sym"], "dir": mv["dir"], "a": mv["a"], "b": mv["b"], "from": b0}
            if i0 + 5 < len(days):
                b5 = days[i0 + 5]
                p0, p5 = px[b0].get(mv["sym"]), px[b5].get(mv["sym"])
                s0, s5 = px[b0].get("SPY"), px[b5].get("SPY")
                if p0 and p5 and s0 and s5:
                    rr, sr = (p5 / p0 - 1) * 100, (s5 / s0 - 1) * 100
                    ex = rr - sr
                    r.update({"to": b5, "ret": round(rr, 2), "spy": round(sr, 2), "ex": round(ex, 2),
                              "win": (ex > 0) if mv["dir"] == "up" else (ex < 0)})
            rows.append(r)
    return rows


def score_of(rows):
    done = [r for r in rows if "win" in r]
    def agg(xs):
        n = len(xs)
        w = sum(1 for x in xs if x["win"])
        # 줄이자 조언의 「번 돈」은 피한 손실이므로 부호를 뒤집어 평균
        ed = [x["ex"] if x["dir"] == "up" else -x["ex"] for x in xs]
        return {"n": n, "win": w, "rate": round(w / n * 100) if n else None, "edge": round(sum(ed) / n, 2) if n else None}
    by_sym = {}
    for r in done:
        by_sym.setdefault(r["sym"], []).append(r)
    syms = {s: {**agg(v), "name": v[-1]["name"]} for s, v in by_sym.items()}
    weak = [s for s, v in syms.items() if v["n"] >= 3 and (v["rate"] or 0) < 40]
    strong = [s for s, v in syms.items() if v["n"] >= 3 and (v["rate"] or 0) >= 60]
    return {"all": agg(done), "up": agg([r for r in done if r["dir"] == "up"]), "down": agg([r for r in done if r["dir"] == "down"]),
            "by_sym": syms, "by_list": sorted([{"sym": k, **v} for k, v in syms.items()], key=lambda x: (-x["n"], -(x["rate"] or 0))), "weak": weak, "strong": strong, "pending": len(rows) - len(done),
            "recent": [{k: r.get(k) for k in ("date", "name", "sym", "dir", "a", "b", "ex", "win")} for r in done[-8:]][::-1],
            "rule": "아침판에 「🧭 ○○ a→b」로 바꾼 것만 · 전날 종가에 바꿨다고 보고 5거래일 뒤 그 칸 ETF − S&P500 · 늘리자는 S&P 를 이기면, 줄이자는 지면 적중 · 비용·환율 뺌"}


# ---------------------------------------------------------------- 스냅샷 · 어제와 비교
def snapshot(d, led, bear, conc, focus):
    views = {v["name"]: v.get("pct") for v in (led.get("sector_views") or {}).get("views", [])}
    mk = {}
    for m in (bear.get("markets") or []) + (bear.get("more") or []):
        a = m.get("analog") or {}
        mk[m.get("name")] = {"state": m.get("state"), "stock": a.get("stock")}
    sc = (led.get("scenario_history") or [{}])[-1]
    top = None
    for c in focus.get("countries") or []:
        if c.get("label") == "돈이 들어오는 곳":
            top = c.get("name"); break
    th = [t.get("name") for t in (focus.get("themes") or [])[:2]]
    return {"date": d.get("date"), "up": (conc.get("regime") or {}).get("up"), "skel": (led.get("skeleton") or {}).get("now"),
            "views": views, "mk": mk, "sc": {k: sc.get(k) for k in ("A", "B2", "C", "B")}, "money": top, "themes": th}


def diff(prev, now, d, moves, conc, bear):
    """중요도 순 후보 → 위 3개. kind: big(돈이 바뀜) / mid(판단 바뀜) / watch(오늘 밤 바뀔 수 있음)"""
    C = []
    if prev and prev.get("up") is not None and prev.get("up") != now.get("up"):
        C.append({"lv": "big", "ic": "🚦", "t": "해외 주식 판정 " + ("🔴 → 🟢" if now["up"] else "🟢 → 🔴"),
                  "s": "💼 기본 포트 뼈대가 바뀜 — " + ("현금 26 → 0 · 주식 63 → 95" if now["up"] else "현금 0 → 26 · 주식 95 → 63")})
    for name, v in (now.get("mk") or {}).items():
        p = ((prev or {}).get("mk") or {}).get(name) or {}
        if p and p.get("stock") is not None and v.get("stock") is not None and p["stock"] != v["stock"]:
            C.append({"lv": "big", "ic": "🔁", "t": f'{name} 주식 {p["stock"]}% → {v["stock"]}%', "s": "시장별 하락장 규칙(닮은 장)이 바뀜"})
        elif p and p.get("state") and v.get("state") and p["state"] != v["state"]:
            C.append({"lv": "mid", "ic": "🌡", "t": f'{name} {p["state"]} → {v["state"]}', "s": "장 분위기 판정이 바뀜 · 주식 % 는 그대로"})
    for mv in moves:
        if mv["a"] is not None:
            C.append({"lv": "big" if abs((mv["b"] or 0) - mv["a"]) >= 2 else "mid", "ic": "🧭",
                      "t": f'{mv["name"]} {mv["a"]:g} → {mv["b"]:g}', "s": "🧭 섹터 칸 비율 " + ("늘림" if mv["dir"] == "up" else "줄임"), "sym": mv["sym"]})
        else:
            C.append({"lv": "mid", "ic": "🧭", "t": f'{mv["name"]} {"↑" if mv["dir"] == "up" else "↓"}', "s": "🧭 섹터 칸", "sym": mv["sym"]})
    if not prev:   # 첫날(스냅샷 없음): 장부·계기판에 남은 「어제 값」으로
        sh = d.get("_sc_hist") or []
        if len(sh) >= 2 and sh[-1].get("date") == d.get("date"):
            prev = {"sc": {k: sh[-2].get(k) for k in ("A", "B2", "C", "B")}, "money": now.get("money"), "themes": now.get("themes")}
    if prev and prev.get("sc") and now.get("sc") and prev["sc"] != now["sc"]:
        ch = [f'{k} {prev["sc"].get(k)}→{now["sc"].get(k)}' for k in ("A", "B2", "C", "B") if prev["sc"].get(k) != now["sc"].get(k)]
        if ch:
            C.append({"lv": "mid", "ic": "🎲", "t": "경우의 수 " + " · ".join(ch), "s": "A = 금리 더 오름 · B2 = AI 이익 · C = 경기 둔화"})
    if prev and prev.get("money") != now.get("money"):
        C.append({"lv": "mid", "ic": "🌏", "t": "돈 몰리는 나라 " + (prev.get("money") or "없음") + " → " + (now.get("money") or "없음"), "s": "5개 시장 점수 1등이 바뀜"})
    if prev and prev.get("themes") != now.get("themes") and (now.get("themes") or prev.get("themes")):
        C.append({"lv": "mid", "ic": "🎯", "t": "집중 테마 " + (", ".join(prev.get("themes") or []) or "없음") + " → " + (", ".join(now.get("themes") or []) or "없음"),
                  "s": "S&P 보다 5·20일 강하고 3일 연속"})
    # 오늘 밤 바뀔 수 있는 것 (거리 1% 안)
    rg = conc.get("regime") or {}
    if rg.get("gap") is not None and abs(rg["gap"]) < 1.5:
        side = "아래" if rg["gap"] < 0 else "위"
        C.append({"lv": "watch", "ic": "⏳", "t": f'S&P500 200일선 {side} {abs(rg["gap"]):.1f}%',
                  "s": "아래로 3일 이어지면 🔴 — 현금 0 → 26" if rg["gap"] < 0 else "다시 아래로 가면 이탈 카운트 시작"})
    order = {"big": 0, "mid": 1, "watch": 2}
    C.sort(key=lambda x: order[x["lv"]])
    real = [c for c in C if c["lv"] != "watch"]
    return {"none": not real, "items": C[:3], "head": ("오늘은 바꿀 것 없음 — 어제 배분 그대로" if not real else f"어제와 달라진 것 {len(real)}가지"),
            "prev_date": (prev or {}).get("date")}


# ---------------------------------------------------------------- ② 행동 카드
def cond_for(d, sym, name):
    for i, t in enumerate(d.get("forecasts_if_wrong") or []):
        if sym and sym in str((d.get("checks") or [""] * 3)[i] if i < len(d.get("checks") or []) else "") or (name and name.split()[0] in t):
            return strip(t)
    return None


def why_for(d, sym, name):
    for k, v in (d.get("candidates_signal") or {}).items():
        if (sym and sym in k) or (name and name.split()[0] in k):
            return strip(v)
    return None


def actions(d, led, moves, score, focus, sec):
    if d.get("actions"):   # 사람이 쓴 것이 먼저 (RULES 1-O)
        return d["actions"]
    al = {a["name"]: a for a in led.get("allocation") or []}
    sl = next((a for a in led.get("allocation") or [] if a.get("sleeve")), {})
    views = [v for v in (led.get("sector_views") or {}).get("views", []) if float(v.get("pct") or 0) > 0]
    tot = sum(float(v["pct"]) for v in views) or 1
    real = lambda p: round(float(sl.get("pct") or 0) * float(p) / tot, 1)
    rows = {r["sym"]: r for r in sec.get("rows") or []}
    bs = score.get("by_sym") or {}

    def card(name, sym, dr, a=None, b=None):
        r = rows.get(sym) or {}
        sc = bs.get(sym)
        c = {"name": name, "sym": sym, "kr": KR_ETF.get(sym) or "—", "dir": dr,
             "r5": r.get("r5"), "rs20": r.get("rs20"),
             "why": why_for(d, sym, name) or (f'{r.get("name", sym)} 5일 {r.get("r5", 0):+.1f}% · S&P 대비 20일 {r.get("rs20", 0):+.1f}%p' if r else ""),
             "cond": cond_for(d, sym, name),
             "hit": ({"n": sc["n"], "rate": sc["rate"]} if sc else None)}
        if a is not None and b is not None:
            c["chg"] = f"섹터 칸 안 {a:g}→{b:g} (실제 {real(a)}→{real(b)}%)"
        if sym in (score.get("weak") or []):
            c["small"] = True
        return c

    up = [card(m["name"], m["sym"], "up", m["a"], m["b"]) for m in moves if m["dir"] == "up"]
    dn = [card(m["name"], m["sym"], "down", m["a"], m["b"]) for m in moves if m["dir"] == "down"]
    # 줄일 것이 없으면 「피할 것」(돈이 빠지는 곳 — 새로 사지 않기)
    for a in (focus.get("avoid") or [])[:2]:
        if len(dn) >= 2:
            break
        c = card(a.get("name"), a.get("sym"), "avoid")
        c["why"] = f'5일 {a.get("r5", 0):+.1f}% · 20일 {a.get("r20", 0):+.1f}% — 돈이 빠지는 곳'
        dn.append(c)
    hold = []
    core = next((a for a in led.get("allocation") or [] if "나스닥" in a["name"] and a.get("pct")), None)
    if core:
        hold.append({"name": core["name"], "sym": "QQQ", "kr": KR_ETF["QQQ"], "dir": "hold", "pct": core["pct"],
                     "why": f'💼 기본 포트 {core["pct"]}% — 판정(S&P500 200일선)이 바뀌기 전엔 그대로', "cond": "S&P500 200일선 아래 3일 → 50.4%"})
    moved = {m["sym"] for m in moves}
    for v in sorted(views, key=lambda v: -float(v["pct"]))[:2]:
        s = sym_of(v["name"])
        if s and s not in moved:
            c = card(v["name"], s, "hold")
            c["pct"] = real(v["pct"])
            hold.append(c)
    return {"up": up[:2], "down": dn[:2], "hold": hold[:3]}


# ---------------------------------------------------------------- ③ 돈의 흐름 지도
def flowmap(focus, sec):
    cs = [{"flag": c.get("flag"), "name": c.get("name"), "ix": c.get("ix"), "chg1": c.get("chg1"), "chg5": c.get("chg5"),
           "chg20": c.get("chg20"), "score": c.get("score"), "label": c.get("label"), "regime": c.get("regime"),
           "hot": [h.get("name") for h in (c.get("hot") or [])[:2]]} for c in focus.get("countries") or []]
    rows = [r for r in sec.get("rows") or [] if r.get("rs5") is not None]
    rows.sort(key=lambda r: -r["rs5"])
    pick = lambda r: {"sym": r["sym"], "name": r["name"], "rs5": r["rs5"], "r1": r.get("r1"), "r5": r.get("r5"), "streak": r.get("streak")}
    kr = (sec.get("compass") or {}).get("KR") or {}
    return {"asof": sec.get("asof"), "countries": cs, "in": [pick(r) for r in rows[:5]], "out": [pick(r) for r in rows[-4:]][::-1],
            "kr_in": [{"name": x.get("name"), "r1": x.get("r1"), "r5": x.get("r5")} for x in (kr.get("strong") or [])[:3]],
            "kr_out": [{"name": x.get("name"), "r1": x.get("r1"), "r5": x.get("r5")} for x in (kr.get("weak") or [])[:3]]}


# ---------------------------------------------------------------- ⑤ 성향별 처방전
def persona(led, bear, prev_up, now_up):
    sk = led.get("skeleton") or {}
    def mix(up):
        k = sk.get("up" if up else "down") or {}
        eq = sum(v for n, v in k.items() if "코어" in n or "섹터" in n)
        return eq, k.get("금", 0), k.get("현금·단기채", 0)
    E, G, Cs = mix(now_up)
    E0, G0, C0 = mix(prev_up if prev_up is not None else now_up)
    kospi = next((m for m in bear.get("markets") or [] if m.get("name") == "코스피"), {})
    kst = (kospi.get("analog") or {}).get("stock")
    out = []
    for nm, ic, f in PERSONA:
        def split(e, g, c):
            st = round(e * f)
            gd = round(g * (0.6 if f < 0.5 else 1))
            cash = round(c * f)
            bd = 100 - st - gd - cash
            return {"stock": st, "bond": bd, "gold": gd, "cash": cash}
        now, prev = split(E, G, Cs), split(E0, G0, C0)
        do = []
        if now["stock"] != prev["stock"]:
            do.append(f'주식 {prev["stock"]}→{now["stock"]}%')
        out.append({"k": nm, "ic": ic, **now, "prev": prev, "chg": " · ".join(do) or "어제 그대로",
                    "kr": (f"국내 주식은 {kst}%(코스피 하락장 규칙) — 주식 몫은 해외 ETF로" if kst is not None and kst < 50 else "국내·해외 주식 반반까지"),
                    "picks": {"stock": "TIGER 미국나스닥100 133690" + (" + 🧭 섹터 칸 ETF" if f >= 0.5 else ""),
                              "bond": "국고채 3년·우량회사채 438330" if f < 0.5 else ("단기채 SGOV · 국고채" if f < 1 else "현금성 SGOV·CD금리 499660"),
                              "gold": "TIGER KRX금현물 0072R0"}})
    return {"items": out, "kospi_stock": kst, "note": "💼 기본 포트(성장형 = 그대로)를 성향에 맞게 주식 몫만 줄인 예시 · 국내 주식·해외 주식·브라질국채는 성장형 이상, 미국채는 위험중립형 이상(제안서 성향 규칙) · 매수 권유 아님"}


# ---------------------------------------------------------------- ⑥ 조건부 대응표 · ⑩ 반론
def triggers(d, led, bear):
    T = []
    for f in d.get("falsify") or []:
        v = num(f.get("dist"))
        unit = "%p" if "%p" in str(f.get("dist")) else "%"
        span = 0.5 if unit == "%p" else 5.0   # 막대 가득 = 이만큼 남음
        T.append({"claim": strip(f.get("claim")), "signal": strip(f.get("signal")), "dist": f.get("dist"), "v": v,
                  "fill": None if v is None else round(max(0.04, 1 - min(abs(v), span) / span), 2), "near": v is not None and abs(v) <= (0.1 if unit == "%p" else 1.0)})
    for c in led.get("conditions") or []:
        if c.get("count") is not None and c.get("of"):
            T.append({"claim": strip(c.get("then")), "signal": strip(c.get("cond")), "dist": f'{c["count"]}/{c["of"]}', "v": None,
                      "fill": round(c["count"] / c["of"], 2), "near": c["count"] >= c["of"] - 1, "count": True})
    for m in (bear.get("markets") or [])[:2]:
        a = m.get("analog") or {}
        nx = a.get("next") or ""
        mm = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", nx)
        if mm and m.get("close"):
            lv = float(mm.group(1).replace(",", ""))
            gap = (lv / m["close"] - 1) * 100
            T.append({"claim": f'{m.get("name")} 주식 {a.get("stock")}% → 더 늘림', "signal": nx, "dist": f"{gap:+.1f}%", "v": gap,
                      "fill": round(max(0.04, 1 - min(abs(gap), 25) / 25), 2), "near": abs(gap) <= 2})
    return T[:6]


def counter(d, T):
    cw = d.get("counter_watch")
    if cw:
        return cw
    cs = d.get("counter") or []
    near = sorted([t for t in T if t.get("v") is not None], key=lambda t: abs(t["v"]))
    return {"claim": strip(cs[0]) if cs else None, "others": [strip(x) for x in cs[1:3]],
            "watch": near[0] if near else None,
            "note": "가장 강한 반론 1개 · 아래는 우리 판단이 가장 빨리 틀릴 수 있는 곳(거리)"}


# ---------------------------------------------------------------- ⑧ 밤사이 → 오늘 한국장
def overnight(d, sec):
    rows = [r for r in sec.get("rows") or [] if r.get("r1") is not None and (r.get("members") or {}).get("kr")]
    up = sorted([r for r in rows if r["r1"] >= 0.8], key=lambda r: -r["r1"])[:3]
    dn = sorted([r for r in rows if r["r1"] <= -1.5], key=lambda r: r["r1"])[:2]
    def kr(r):
        ms = [m for m in r["members"]["kr"] if m.get("n")][:3]
        return [{"name": m["n"], "code": re.sub(r"\.K[SQ]$", "", m.get("t") or ""), "r1": m.get("r1"), "r5": m.get("r5")} for m in ms]
    pick = lambda r: {"sym": r["sym"], "name": r["name"], "r1": r["r1"], "r5": r.get("r5"), "kr": kr(r)}
    times = [{"t": "08:40", "what": "예상 체결가 — 연결 종목이 +5% 넘게 뜨면 추격하지 않기"},
             {"t": "09:00~09:30", "what": "갭 유지 확인 — 첫 30분 안에 시가 아래로 밀리면 하루치 반짝"},
             {"t": "15:20", "what": "마감 동시호가 — 외국인 순매수 방향 확인"}]
    for s in d.get("schedule") or []:
        if "개장" in strip(s.get("what")) or "지연" in strip(s.get("what")):
            times.insert(0, {"t": strip(s.get("when")), "what": strip(s.get("what"))})
            break
    return {"up": [pick(r) for r in up], "down": [pick(r) for r in dn], "times": times[:4], "note": d.get("overnight_note"),
            "rule": "미국 테마 ETF 하루 등락 상위·하위 → sectors.json 의 한국 연결 종목(어제 등락) · 매수 권유 아님"}


# ---------------------------------------------------------------- 앱 카드 5장
def cards(M, d):
    ch, ac = M["changes"], M["actions"]
    def nm(c):
        return f'{c["name"]} {c["sym"]}'
    return [
        {"k": "결론", "t": strip(d.get("one_liner"))[:160], "s": strip((d.get("kick") or {}).get("so"))[:160]},
        {"k": "달라진 것", "t": ch["head"], "s": " · ".join(i["t"] for i in ch["items"])},
        {"k": "돈의 흐름", "t": " · ".join(f'{c["flag"]}{c["chg5"]:+.1f}%' for c in M["flowmap"]["countries"] if c.get("chg5") is not None),
         "s": "들어온 곳 " + ", ".join(x["name"] for x in M["flowmap"]["in"][:3]) + " / 빠진 곳 " + ", ".join(x["name"] for x in M["flowmap"]["out"][:3])},
        {"k": "행동", "t": "늘림 " + (", ".join(nm(c) for c in ac.get("up") or []) or "없음") + " · 줄임/피함 " + (", ".join(nm(c) for c in ac.get("down") or []) or "없음"),
         "s": "그대로 " + ", ".join(c["name"] for c in ac.get("hold") or [])},
        {"k": "일정", "t": " · ".join(strip(s.get("when")) for s in (d.get("schedule") or [])[:3]), "s": strip(((d.get("schedule") or [{}])[0]).get("what"))},
    ]


def latest_day():
    fs = sorted(glob.glob(str(ROOT / "data" / "2026-*.json")) + glob.glob(str(ROOT / "data" / "202[7-9]-*.json")))
    return Path(fs[-1]) if fs else None


def build(day: Path | None = None, write=True):
    day = day or latest_day()
    d = jl(day)
    led = jl(ROOT / "ledger" / "ledger.json")
    sec, focus, bear, conc = jl(MK / "sectors.json"), jl(MK / "focus.json"), jl(MK / "bear.json"), jl(MK / "conc.json")
    px = update_px(sec)
    rows = build_log(px)
    score = score_of(rows)
    log = jl(MK / "morning_log.json", {"snap": {}})
    snaps = log.get("snap") or {}
    now = snapshot(d, led, bear, conc, focus)
    prev = None
    for k in sorted(snaps):
        if k < d["date"]:
            prev = snaps[k]
    moves = parse_moves(d)
    d["_sc_hist"] = led.get("scenario_history") or []
    M = {"at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "date": d.get("date"), "edition": d.get("edition_label"),
         "asof": sec.get("asof"), "basis": d.get("basis")}
    M["changes"] = diff(prev, now, d, moves, conc, bear)
    M["actions"] = actions(d, led, moves, score, focus, sec)
    M["flowmap"] = flowmap(focus, sec)
    M["persona"] = persona(led, bear, (prev or {}).get("up"), now.get("up"))
    M["triggers"] = triggers(d, led, bear)
    M["counter"] = counter(d, M["triggers"])
    M["overnight"] = overnight(d, sec)
    M["score"] = score
    M["cards"] = cards(M, d)
    if write:
        snaps[d["date"]] = now
        log = {"snap": dict(sorted(snaps.items())[-60:]), "moves": rows[-200:]}
        (MK / "morning_log.json").write_text(json.dumps(log, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (MK / "morning.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def main():
    day = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    M = build(day)
    s = M["score"]["all"]
    print(f'🌅 {M["date"]} · {M["changes"]["head"]} · 행동 늘림 {len(M["actions"]["up"])} 줄임 {len(M["actions"]["down"])} · '
          f'조언 성적 {s["win"]}/{s["n"]} ({s["rate"]}%) 대기 {M["score"]["pending"]}')


if __name__ == "__main__":
    main()
