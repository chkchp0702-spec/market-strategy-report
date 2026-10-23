"""💼 포트 — 「시황리포트대로 투자했다면」 (10/9 사용자 요청)
  · 장부(ledger.json) allocation = 리포트의 자산 배분표. 바뀔 때마다 market/port_log.json 에 날짜와 함께 쌓는다.
  · 칸마다 따라 사기 쉬운 대표 상품(미국 ETF / 한국 상장 ETF)을 정하고, 미국 상품 종가로 하루하루 성적을 계산한다.
    - 리포트(한국 아침) D 의 배분은 미국 D 거래일(전날 종가 → D 종가)부터 적용 (리포트 뒤에 살 수 있는 첫 장)
    - 매일 비중을 맞춘다고 가정(리밸런싱 비용·세금·환율 제외)
  · 비교: S&P500(SPY) · 코스피 · 주식60/채권40(AOR)
  → market/port.json (앱 💼 포트 탭)
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sys
from pathlib import Path
try:
    from src.global_peers import THEMES as _TH
    PNAME = {t: n for T in _TH for t, n in T["us"] + T["peers"]}
except Exception:
    PNAME = {}

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger" / "ledger.json"
LOG = ROOT / "market" / "port_log.json"
OUT = ROOT / "market" / "port.json"
START = "2026-10-02"        # 장부 집계 시작일 (첫 배분표)

# 칸 이름에 이 말이 있으면 → 성적 계산·따라하기용 미국 상품 (없으면 instruments 에서 미국 티커를 읽음)
US_PICK = [
    ("S&P500", ["SPY"]), ("나스닥", ["QQQ"]),       # 💼 C안 코어 (10/11)
    ("현금", ["SGOV"]), ("단기채", ["SGOV"]),
    ("전력", ["XLU", "GEV"]), ("인프라", ["XLU", "GEV"]), ("원자력", ["NLR"]),
    ("에너지", ["XLE"]), ("금융", ["KBWB"]), ("반도체", ["SOXX"]), ("금", ["GLD"]),
    ("장기채", ["TLT"]), ("소프트웨어", None), ("광통신", None),
]
NOT_TICKER = {"TIGER", "RISE", "KODEX", "ACE", "SOL", "PLUS", "KRX", "CD", "AI", "HBM", "ETF", "KIS", "TOP", "S", "KB",
              "HANARO", "KBSTAR", "ARIRANG", "KOSEF", "NH", "SK", "LG", "OIL"}
BENCH = {"SPY": "S&P500", "^KS11": "코스피", "AOR": "주식60·채권40",
         "QQQ": "나스닥100", "DIA": "다우", "^KQ11": "코스닥", "ACWI": "MSCI 전세계", "URTH": "MSCI 선진국", "EEM": "MSCI 신흥국",
         "^N225": "니케이225", "^HSI": "항셍", "510300.SS": "중국 CSI300",
         "399001.SZ": "심천성분", "588000.SS": "과창판50"}   # CSI300·과창판50 지수는 야후 시세가 멈춰 있어 추종 ETF(510300·588000)로
BENCH_GROUP = {"S&P500": "미국", "나스닥100": "미국", "다우": "미국", "코스피": "한국", "코스닥": "한국",
               "MSCI 전세계": "MSCI", "MSCI 선진국": "MSCI", "MSCI 신흥국": "MSCI", "니케이225": "아시아", "항셍": "아시아", "중국 CSI300": "중국", "심천성분": "중국", "과창판50": "중국",
               "주식60·채권40": "자산배분"}


BFX = {"^KS11": "KRW=X", "^KQ11": "KRW=X", "^N225": "JPY=X", "^HSI": "HKD=X"}   # 지수 → 달러 환산용 환율
FXT = {".T": "JPY=X", ".KS": "KRW=X", ".KQ": "KRW=X", ".SS": "CNY=X", ".SZ": "CNY=X", ".HK": "HKD=X", ".TW": "TWD=X"}
CURN = {".T": "엔", ".KS": "원", ".KQ": "원", ".SS": "위안", ".SZ": "위안", ".HK": "홍콩달러", ".TW": "대만달러"}


def sfx(t: str) -> str:
    for k in FXT:
        if t.endswith(k):
            return k
    return ""


def us_of(name: str, inst: str, picks: list | None = None) -> list[str]:
    """성적 계산·따라하기 상품. 장부 allocation 에 picks 가 있으면 그대로(미국 밖 종목도 가능 — 🌏 글로벌 동종주 비교로 고름)"""
    if picks:
        return list(picks)
    for k, v in US_PICK:
        if k in name and v:
            return v
    toks = re.findall(r"(?<![A-Za-z0-9.])([A-Z]{2,5})(?![A-Za-z0-9.])", inst)   # 2383.TW 의 TW 같은 거래소 꼬리는 빼기
    out = []
    for t in toks:
        if t not in NOT_TICKER and t not in out:
            out.append(t)
    return out[:4]


def kr_of(inst: str) -> list[dict]:
    out = []
    for nm, code in re.findall(r"([^·/]+?)\s+([0-9][0-9A-Z]{5})(?![0-9A-Z])", inst):
        nm = re.sub(r"^\s*(국내 참고|국내)\s*", "", nm).strip()
        out.append({"code": code, "name": nm, "etf": bool(re.match(r"(TIGER|RISE|KODEX|ACE|SOL|PLUS|HANARO|KBSTAR|ARIRANG)", nm))})
    return out[:4]


def update_log(now) -> list[dict]:
    L = json.loads(LEDGER.read_text(encoding="utf-8"))
    alloc = [{"pct": a["pct"], "name": a["name"], "instruments": a.get("instruments", ""), **({"picks": a["picks"]} if a.get("picks") else {}),
              **({"why_picks": a["why_picks"]} if a.get("why_picks") else {})} for a in L.get("allocation", [])]
    try:
        log = json.loads(LOG.read_text(encoding="utf-8"))
    except Exception:
        log = []
    # 🌏 고른 상품(picks)은 리포트가 칸을 다시 쓸 때 빠뜨려도 이어진다 — 바꾸려면 picks 를 새로 적고, 기본으로 돌리려면 "picks": ["기본"]
    if log:
        prevp = {x["name"]: (x.get("picks"), x.get("why_picks")) for x in log[-1]["alloc"]}
        for a in alloc:
            if a.get("picks") == ["기본"]:
                a.pop("picks"); a.pop("why_picks", None)
            elif not a.get("picks") and prevp.get(a["name"], (None,))[0]:
                a["picks"], wp = prevp[a["name"]]
                if wp: a["why_picks"] = wp
    sig = lambda a: [(x["pct"], x["name"], tuple(x.get("picks") or [])) for x in a]
    today = now.strftime("%Y-%m-%d")
    if not log:
        log = [{"date": START, "alloc": alloc, "why": "장부 시작 배분표"}]
    elif sig(log[-1]["alloc"]) != sig(alloc):
        ref = log[-2] if log[-1]["date"] == today and len(log) > 1 else log[-1]   # 같은 날 두 번 바뀌면 전날 기준으로 이유를 다시 씀(앞 변경 이유가 지워지지 않게)
        old = {x["name"]: x["pct"] for x in ref["alloc"]}
        ch = [f"{x['name']} {old.get(x['name'], 0)}→{x['pct']}%" for x in alloc if old.get(x["name"]) != x["pct"]]
        ch += [f"{n} {p}→0%" for n, p in old.items() if n not in {x["name"] for x in alloc}]
        op = {x["name"]: x.get("picks") for x in ref["alloc"]}
        ch += [f"{x['name']} 상품 {'·'.join(op.get(x['name']) or ['기본'])} → {'·'.join(x['picks'])}" + (f" ({x['why_picks']})" if x.get("why_picks") else "")
               for x in alloc if x.get("picks") and x.get("picks") != op.get(x["name"])]
        cn = L.get("change_note") or {}          # 리포트·사람이 남긴 「왜 바꿨나」 한 줄 (그날만)
        entry = {"date": today, "alloc": alloc, "why": ((cn.get("why") + " — ") if cn.get("date") == today and cn.get("why") else "") + " · ".join(ch)}
        if log[-1]["date"] == today:
            log[-1] = entry
        else:
            log.append(entry)
    else:
        log[-1]["alloc"] = alloc          # 상품 글자만 바뀐 경우 최신으로
    # ⑨ 비중·상품이 바뀐 날 알림 한 번 — 「무엇을 얼마나」 + 따라하기로 바로 (10/10 앱 업그레이드)
    e = log[-1]
    if e["date"] == today and not e.get("notified") and len(log) > 1:
        msg = e.get("why", "")
        msg = re.sub(r"\s*\([^()]*\)", "", msg)[:300]          # 괄호 근거는 앱에서
        try:
            import urllib.request
            urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=json.dumps({
                "topic": "chkchp-ch-report", "title": "💼 포트 비중 바꿈 — 오늘 맞춰 두기", "message": msg + "\n→ 따라하기에서 주 수 확인",
                "click": "https://chkchp0702-spec.github.io/daily-app/#port~pofollow", "tags": ["briefcase"]}).encode(),
                headers={"Content-Type": "application/json"}), timeout=15).read()
            e["notified"] = True
        except Exception as ex:
            print("알림 실패", ex)
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return log


def main() -> int:
    now = dt.datetime.now(KST)
    log = update_log(now)
    import yfinance as yf
    import pandas as pd

    tick = set(BENCH) | {"KRW=X"}
    for e in log:
        for a in e["alloc"]:
            tick |= set(us_of(a["name"], a["instruments"], a.get("picks")))
    try:   # 🧭 섹터 의견 그림자 채점용 (10/11 C안)
        VIEWS = json.loads(LEDGER.read_text(encoding="utf-8")).get("sector_views") or {}
    except Exception:
        VIEWS = {}
    for a in VIEWS.get("views") or []:
        tick |= set(us_of(a["name"], a["instruments"], a.get("picks")))
    tick |= {FXT[sfx(t)] for t in list(tick) if sfx(t)} | set(BFX.values())
    kr_codes = {k["code"] for a in log[-1]["alloc"] for k in kr_of(a["instruments"]) if k["code"].isdigit()}
    start = (dt.date.fromisoformat(START) - dt.timedelta(days=400)).isoformat()   # 20일 신호 + 🧪 규칙(200일선·6개월 수익) 계산용 여유
    df = yf.download(sorted(tick) + [c + ".KS" for c in kr_codes], start=start, interval="1d", auto_adjust=True, progress=False,
                     group_by="ticker", threads=True)
    C = {}
    for t in list(tick) + [c + ".KS" for c in kr_codes]:
        try:
            s = df[t]["Close"].dropna()
            if len(s):
                C[t] = s
        except Exception:
            pass
    miss = sorted(t for t in tick if t not in C)
    # 미국 거래일 달력 (SPY 기준)
    days = [d for d in C["SPY"].index if d.strftime("%Y-%m-%d") >= START]
    base_i = list(C["SPY"].index).index(days[0]) - 1      # START 전날 종가 = 출발점
    cal = list(C["SPY"].index)[base_i:]

    USD = {}

    def usd(t):
        """미국 밖 종목은 달러로 바꾼 값 (환율까지 반영)"""
        if t in USD:
            return USD[t]
        s = C.get(t)
        if s is not None and (sfx(t) or t in BFX):
            fx = C.get(BFX.get(t) or FXT[sfx(t)])
            s = (s / fx.reindex(s.index, method="ffill")).dropna() if fx is not None else None
        USD[t] = s
        return s

    def ret(t, d0, d1, local=False):
        s = C.get(t) if local else usd(t)
        if s is None:
            return None
        a = s[s.index <= d0]
        b = s[s.index <= d1]
        if not len(a) or not len(b):
            return None
        return float(b.iloc[-1] / a.iloc[-1] - 1)

    def alloc_on(d):
        ds = d.strftime("%Y-%m-%d")
        cur = log[0]
        for e in log:
            if e["date"] <= ds:
                cur = e
        return cur

    # 🧪 킥 포트 규칙 (src/rules7.py) — 10/12부터, 전날 종가까지 자료로 칸 비중을 다시 정함
    from src.rules7 import RULE_FROM, rule_weights, stats_of, quad as _quad, is_cash
    try:
        _kp = json.loads((ROOT / "market" / "kick_params.json").read_text(encoding="utf-8"))
    except Exception:
        _kp = {}
    USE = tuple(_kp.get("rules_use", ["cash", "tilt", "brake"]))
    REG = []
    try:
        import urllib.request as _u
        _R = json.loads(_u.urlopen("https://raw.githubusercontent.com/chkchp0702-spec/daily-app/main/archive/x/regime.json", timeout=30).read())
        REG = sorted({r[0]: (r[1], r[2]) for r in (_R.get("hist") or []) + (_R.get("daily") or []) if len(r) >= 3}.items())
    except Exception as e_:
        print("국면 못 받음", e_)

    def quad_on(ds):
        x = [v for d, v in REG if d <= ds]
        return _quad(*x[-1]) if x else None

    # 🎯 판정 (10/12) — S&P500(SPY) 200일선 위 · 바뀐 상태가 3거래일 이어져야 인정 (conc_port.py 와 같은 규칙)
    _spy = C["SPY"]
    _raw = (_spy > _spy.rolling(200).mean()).fillna(False).values
    _st, _cur, _run = [], bool(_raw[0]), 0
    for v in _raw:
        v = bool(v)
        if v != _cur:
            _run += 1
            if _run >= 3:
                _cur, _run = v, 0
        else:
            _run = 0
        _st.append(_cur)
    UPREG = dict(zip(_spy.index, _st))

    def up_on(d0):
        ks = [k for k in UPREG if k <= d0]
        return UPREG[ks[-1]] if ks else None

    # 🦴 변동성 맞춤 비중 (10/12 사용자 결정) — 💼 기본 = 방어형 · ⚡ 킥 기본 칸 = 중간 (src/rules7.py VOL_ROLES · 검증 src/skel_bt.py)
    from src.rules7 import VOL_FROM, VOL_ROLES, held_scale_line, is_gold
    VP_BASE = dict(VOL_ROLES["base"])
    VP_KICK = {**VOL_ROLES["kick"], **(_kp.get("vol") or {})}
    _vb, _hb = held_scale_line(C["SPY"], C["QQQ"], VP_BASE)
    _vk, _hk = held_scale_line(C["SPY"], C["QQQ"], VP_KICK)

    def scale_at(H, d0):
        s_ = H[H.index <= d0]
        return float(s_.iloc[-1]) if len(s_) else 1.0

    def vol_on(d1):
        return d1.strftime("%Y-%m-%d") >= VOL_FROM

    def base_w(e, d0, d1):
        """💼 기본 포트 그날 비중 — 배분표(장부) × 변동성 맞춤 (주식 칸만, 덜어낸 만큼 현금·단기채 칸)"""
        w = {a["name"]: float(a["pct"]) for a in e["alloc"]}
        if not vol_on(d1):
            return w
        sc = scale_at(_hb, d0)
        freed = 0.0
        for a in e["alloc"]:
            if is_cash(a["name"]) or is_gold(a["name"]):
                continue
            freed += w[a["name"]] * (1 - sc)
            w[a["name"]] *= sc
        cn = [a["name"] for a in e["alloc"] if is_cash(a["name"])]
        if cn:
            w[cn[0]] += freed
        return w

    def rules_on(e, d0, qds=None, vol=False):
        ds = qds or d0.strftime("%Y-%m-%d")      # 국면은 그 날 전까지 나온 것 (가격 판단은 d0 종가까지)
        spy = C["SPY"][C["SPY"].index <= d0]
        st = {}
        for a in e["alloc"]:
            if is_cash(a["name"]):
                continue
            ss = []
            for t in us_of(a["name"], a["instruments"], a.get("picks")):
                s_ = usd(t)
                if s_ is not None:
                    ss.append(s_[s_.index <= d0])
            st[a["name"]] = stats_of(ss, spy)
        u = up_on(d0)
        qd = ("🟢 상승장" if u else "🔴 상승장 아님") if u is not None else quad_on(ds)
        return rule_weights([(a["name"], a["pct"]) for a in e["alloc"]], st, qd, USE, scale_at(_hk, d0) if (vol and "vol" in USE) else None) + (qd, st)

    nav_rule = [1.0]
    nav, bn = [1.0], {k: [1.0] for k in BENCH}
    contrib, series_d = {}, [cal[0].strftime("%Y-%m-%d")]
    daily = []
    for i in range(1, len(cal)):
        d0, d1 = cal[i - 1], cal[i]
        e = alloc_on(d1)
        bw = base_w(e, d0, d1)
        r_tot, parts = 0.0, {}
        for a in e["alloc"]:
            us = us_of(a["name"], a["instruments"], a.get("picks"))
            rs = [x for x in (ret(t, d0, d1) for t in us) if x is not None]
            r = sum(rs) / len(rs) if rs else 0.0
            c = bw.get(a["name"], a["pct"]) / 100 * r
            r_tot += c
            parts[a["name"]] = c
            contrib[a["name"]] = contrib.get(a["name"], 0) + c * nav[-1]
        nav.append(nav[-1] * (1 + r_tot))
        if d1.strftime("%Y-%m-%d") >= RULE_FROM:
            rw = rules_on(e, d0, (d1 - pd.Timedelta(days=1)).strftime("%Y-%m-%d"), vol_on(d1))[0]
            rr = 0.0
            for a in e["alloc"]:
                us = us_of(a["name"], a["instruments"], a.get("picks"))
                rs = [x for x in (ret(t, d0, d1) for t in us) if x is not None]
                rr += rw.get(a["name"], a["pct"]) / 100 * (sum(rs) / len(rs) if rs else 0.0)
            nav_rule.append(nav_rule[-1] * (1 + rr))
        else:
            nav_rule.append(nav_rule[-1] * (1 + r_tot))
        for k in BENCH:
            r = ret(k, d0, d1)
            bn[k].append(bn[k][-1] * (1 + (r or 0)))
        series_d.append(d1.strftime("%Y-%m-%d"))
        daily.append({"d": d1.strftime("%Y-%m-%d"), "r": round(r_tot * 100, 2), "spy": round((ret("SPY", d0, d1) or 0) * 100, 2)})

    # 🧾 정직 버전 (10/11): 매일 비중을 맞춘다는 가정 대신 「주 1회(그 주 첫 거래일) + 배분표가 바뀐 날」에만 맞추고,
    #    그 사이엔 비중이 흘러가게 둔다. 맞출 때마다 사고판 양(턴오버) × 0.1% 를 비용으로 뺀다. 기존 nav·rule 은 그대로.
    TC = 0.001

    def honest_nav(target_of):
        hv, w, prev_sig, wk = [1.0], None, None, None
        for i in range(1, len(cal)):
            d0, d1 = cal[i - 1], cal[i]
            e = alloc_on(d1)
            tw = target_of(e, d0, d1)                       # {칸: 비중(0~1)} · 나머지는 수익 0 현금
            sig_ = tuple(sorted(tw.items()))
            iw = d1.isocalendar()[:2]
            v = hv[-1]
            if w is None or sig_ != prev_sig or iw != wk:
                cur = w or {}
                turn = sum(abs(tw.get(k, 0) - cur.get(k, 0)) for k in set(tw) | set(cur))
                v *= 1 - turn * TC
                w = dict(tw)
                prev_sig, wk = sig_, iw
            rr = {}
            for a in e["alloc"]:
                us = us_of(a["name"], a["instruments"], a.get("picks"))
                rs = [x for x in (ret(t, d0, d1) for t in us) if x is not None]
                rr[a["name"]] = sum(rs) / len(rs) if rs else 0.0
            g = sum(w.get(k, 0) * rr.get(k, 0.0) for k in w)
            hv.append(v * (1 + g))
            tot = 1 + g
            w = {k: w[k] * (1 + rr.get(k, 0.0)) / tot for k in w}
        return hv

    nav_h = honest_nav(lambda e, d0, d1: {k: v / 100 for k, v in base_w(e, d0, d1).items()})
    def rule_target(e, d0, d1):
        if d1.strftime("%Y-%m-%d") < RULE_FROM:
            return {a["name"]: a["pct"] / 100 for a in e["alloc"]}
        rw = rules_on(e, d0, (d1 - pd.Timedelta(days=1)).strftime("%Y-%m-%d"), vol_on(d1))[0]
        return {a["name"]: rw.get(a["name"], a["pct"]) / 100 for a in e["alloc"]}     # 위 nav_rule 과 같은 비중

    nav_rule_h = honest_nav(rule_target)

    peak, mdd = 1.0, 0.0
    for v in nav:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    fx = float(C["KRW=X"].iloc[-1]) if "KRW=X" in C else None

    # 지금 담을 것 (따라하기) — 다음 거래일 비중 (💼 변동성 맞춤 반영)
    cur = log[-1]
    nxt = cal[-1] + pd.offsets.BDay(1)
    bw_now = base_w(cur, cal[-1], nxt)
    hold = []
    for a in cur["alloc"]:
        us = us_of(a["name"], a["instruments"], a.get("picks"))
        kr = kr_of(a["instruments"])
        for k in kr:
            s = C.get(k["code"] + ".KS")
            if s is not None and len(s):
                k["px"] = round(float(s.iloc[-1]))
        chk = []
        for t in us:
            sr = usd(t)
            if sr is None or len(sr) < 25:
                continue
            last = float(sr.iloc[-1]); m20 = float(sr.iloc[-20:].mean())
            r5 = (last / float(sr.iloc[-6]) - 1) * 100; r20 = (last / float(sr.iloc[-21]) - 1) * 100
            spy = C["SPY"]; s5 = (float(spy.iloc[-1]) / float(spy.iloc[-6]) - 1) * 100; s20 = (float(spy.iloc[-1]) / float(spy.iloc[-21]) - 1) * 100
            chk.append({"t": t, "r5": round(r5, 2), "r20": round(r20, 2), "rs5": round(r5 - s5, 2), "rs20": round(r20 - s20, 2), "above20": last >= m20})
        sig = ""
        if chk:
            a20 = sum(1 for c in chk if c["above20"]) / len(chk)
            rs20 = sum(c["rs20"] for c in chk) / len(chk); rs5 = sum(c["rs5"] for c in chk) / len(chk)
            sig = ("약함 — 20일선 아래·S&P보다 약함 → 줄일 후보" if a20 < .5 and rs20 < -2 else
                   "강함 — S&P보다 강하고 20일선 위 → 유지·늘릴 후보" if a20 >= .5 and rs20 > 2 and rs5 > -1 else
                   "꺾이는 중 — 5일 약세 → 지켜보기" if rs5 < -3 else "보통")
        # 🌏 고른 상품 vs 원래 미국 상품 — 고른 날부터 누가 더 벌었나 (매일 채점 → 지면 되돌릴 근거)
        pvs = None
        if a.get("picks"):
            since = None
            for e_ in reversed(log):
                m_ = next((x for x in e_["alloc"] if x["name"] == a["name"]), None)
                if not m_ or m_.get("picks") != a.get("picks"):
                    break
                since = e_["date"]
            base_t = us_of(a["name"], a["instruments"], None)
            i0 = next((i for i, d in enumerate(cal) if d.strftime("%Y-%m-%d") >= (since or "9999")), None)
            if i0 is None or i0 == 0:
                pvs = {"since": since, "base": base_t, "pending": True}
            else:
                avg = lambda ts: (lambda v: round(sum(v) / len(v) * 100, 2) if v else None)([x for x in (ret(t, cal[i0 - 1], cal[-1]) for t in ts) if x is not None])
                rp, rb = avg(a["picks"]), avg(base_t)
                pvs = {"since": since, "base": base_t, "pick": rp, "base_r": rb, "edge": round(rp - rb, 2) if rp is not None and rb is not None else None,
                       "days": len(cal) - i0}
        hold.append({"name": a["name"], "pct": round(bw_now.get(a["name"], a["pct"]), 1), "pct_base": a["pct"], "instruments": a["instruments"], "check": chk, "sig": sig, "pick_vs": pvs,
                     "picks": a.get("picks"), "why_picks": a.get("why_picks"),
                     "us": [{"t": t, "name": PNAME.get(t), "px": round(float(C[t].iloc[-1]), 2) if t in C else None, "cur": CURN.get(sfx(t), "달러"),
                             "krw": (round(float(C[t].iloc[-1]) * (fx / float(C[FXT[sfx(t)]].iloc[-1]) if sfx(t) and FXT[sfx(t)] in C else fx)))
                                    if t in C and fx else None,
                             "r1": round((ret(t, cal[-2], cal[-1]) or 0) * 100, 2) if t in C and len(cal) > 1 else None,
                             "since": round((ret(t, cal[0], cal[-1]) or 0) * 100, 2) if t in C else None} for t in us],
                     "kr": kr, "contrib": round(contrib.get(a["name"], 0) * 100, 2)})
    prev = log[-2]["alloc"] if len(log) > 1 else None
    rw_now, why_now, cash_t, qd_now, st_now = rules_on(log[-1], cal[-1], now.strftime("%Y-%m-%d"), vol_on(nxt))     # 다음 거래일에 쓸 킥 포트 기본 비중 (국면은 오늘 것)
    rule = {"from": RULE_FROM, "use": list(USE), "quad": qd_now, "cash": cash_t, "nav": [round((v - 1) * 100, 2) for v in nav_rule],
            "now": rw_now, "why": why_now,
            "mom": {n: round(v["mom"] * 100, 1) for n, v in st_now.items() if v},
            "note": f"⚡ 킥 포트의 기본 칸은 {RULE_FROM}부터 검증을 통과한 규칙대로: " +
                    " ".join(x for k, x in (("cash", f"① 현금 = 🎯 판정 「{qd_now}」(S&P500 200일선) → {cash_t}%"), ("tilt", "③ S&P 대비 3·6개월 강한 칸 ×1.25 · 약한 칸 ×0.75"),
                                             ("brake", "④ 200일선 아래 칸 0 · 50일선 아래이면서 S&P보다 약한 칸 ½"),
                                             ("vol", f"🦴 변동성 맞춤({VP_KICK['role']}) 주식 칸 × min(1, {VP_KICK['target']}% ÷ {VP_KICK['lb']}일 변동성)·아래 한도 {round(VP_KICK['floor'] * 100)}% ({VOL_FROM}부터)")) if k in USE) +
                    f" · 검증에서 효과가 없던 규칙은 꺼 둠(market/rules_bt.json). 💼 기본 포트는 리포트 배분표 + 🦴 변동성 맞춤(방어형, {VOL_FROM}부터)."}
    # 🧭 섹터 의견 그림자 — 리포트 섹터 판단(배분표 밖)이 같은 기간 코어(S&P½+나스닥½)보다 나았나
    views = None
    if VIEWS.get("views"):
        vs = VIEWS.get("since") or START
        di = [d for d in cal if d.strftime("%Y-%m-%d") >= vs]
        if len(di) >= 1:
            d0v = cal[cal.index(di[0]) - 1] if cal.index(di[0]) > 0 else di[0]
            tw = sum(a["pct"] for a in VIEWS["views"]) or 1
            vrows, vr = [], 0.0
            for a in VIEWS["views"]:
                ts = us_of(a["name"], a["instruments"], a.get("picks"))
                rs = [x for x in (ret(t, d0v, cal[-1]) for t in ts) if x is not None]
                r = sum(rs) / len(rs) if rs else 0.0
                vr += a["pct"] / tw * r
                vrows.append({"name": a["name"], "pct": a["pct"], "ret": round(r * 100, 2), "t": ts})
            core = ((ret("SPY", d0v, cal[-1]) or 0) + (ret("QQQ", d0v, cal[-1]) or 0)) / 2
            views = {"since": vs, "days": len(di), "ret": round(vr * 100, 2), "core": round(core * 100, 2), "edge": round((vr - core) * 100, 2),
                     "rows": sorted(vrows, key=lambda x: -x["ret"]),
                     "note": "리포트의 섹터 판단을 돈 없이 따라간 성적(같은 비율). 8주 넘게 코어를 이기면 배분 칸으로 되살리는 것을 검토한다(주식 칸의 절반까지)."}
        else:
            views = {"since": vs, "days": 0, "pending": True, "rows": [{"name": a["name"], "pct": a["pct"]} for a in VIEWS["views"]]}
    def vol_state(V, H, P_, role_key, eq_base):
        on_ = vol_on(nxt)
        sc = scale_at(H, cal[-1]) if on_ else 1.0
        return {"on": True, "active": on_, "role": P_["role"], "lb": P_["lb"], f"vol{P_['lb']}": round(float(V.iloc[-1]) * 100, 1), "vol20": round(float(vol_line_(20).iloc[-1]) * 100, 1),
                "target": P_["target"], "floor": round(P_["floor"] * 100), "eq_scale": round(sc * 100), "eq_w": round(eq_base * sc, 1),
                "raw_scale": round(min(1.0, max(P_["floor"], P_["target"] / 100 / float(V.iloc[-1]))) * 100), "band": 5, "from": VOL_FROM, "asof": cal[-1].strftime("%Y-%m-%d"),
                "note": f"주식 칸 × min(1, 목표 {P_['target']}% ÷ S&P½+나스닥½ {P_['lb']}일 변동성), 아래 한도 {round(P_['floor'] * 100)}% · 5%p 넘게 바뀔 때만 · 덜어낸 만큼 현금·단기채 · 레버리지 없음"}

    from src.rules7 import vol_line as _vl
    vol_line_ = lambda lb: _vl(C["SPY"], C["QQQ"], lb)
    eq_base_b = sum(a["pct"] for a in cur["alloc"] if not is_cash(a["name"]) and not is_gold(a["name"]))
    vol_rule = vol_state(_vb, _hb, VP_BASE, "base", eq_base_b)
    rule["vol_rule"] = {**vol_state(_vk, _hk, VP_KICK, "kick", eq_base_b), "on": "vol" in USE,
                        "eq_w": round(sum(v for k, v in rw_now.items() if not is_cash(k) and not is_gold(k)), 1)}
    # 🔁 변동성 맞춤으로 💼 비중이 바뀐 날 (5%p 넘게 바뀔 때만 생김) — 앱 「비중 바뀐 날」에 같이 보임
    vchg = []
    prev_sc = 1.0
    for i in range(1, len(cal) + 1):
        d0 = cal[i - 1]
        d1 = cal[i] if i < len(cal) else nxt
        if not vol_on(d1):
            continue
        sc = scale_at(_hb, d0)
        if abs(sc - prev_sc) > 1e-9:
            vchg.append({"date": d1.strftime("%Y-%m-%d"), "why": f"🦴 변동성 맞춤(방어형): 주식 칸 {eq_base_b * prev_sc:.1f}→{eq_base_b * sc:.1f}% "
                         f"(S&P½+나스닥½ {VP_BASE['lb']}일 변동성 {float(_vb[_vb.index <= d0].iloc[-1]) * 100:.1f}% · 목표 {VP_BASE['target']}%) — 나머지는 현금·단기채"
                         + (" · 다음 거래일부터" if i == len(cal) else ""), "vol": True})
        prev_sc = sc
    changes = sorted([{"date": e["date"], "why": e.get("why", "")} for e in log] + vchg, key=lambda x: x["date"], reverse=True)
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"), "start": START, "views": views, "vol_rule": vol_rule, "asof": cal[-1].strftime("%Y-%m-%d"), "fx": round(fx, 1) if fx else None,
        "dates": series_d, "nav": [round((v - 1) * 100, 2) for v in nav],
        "bench": {BENCH[k]: [round((v - 1) * 100, 2) for v in bn[k]] for k in BENCH},
        "bench_meta": [{"name": BENCH[k], "t": k, "group": BENCH_GROUP.get(BENCH[k], ""), "ret": round((bn[k][-1] - 1) * 100, 2),
                        "local": (round((ret(k, cal[0], cal[-1], True) or 0) * 100, 2) if (sfx(k) or k in BFX) and k in C else None),
                        "r1": round((ret(k, cal[-2], cal[-1]) or 0) * 100, 2) if k in C and len(cal) > 1 else None,
                        "ok": k in C} for k in BENCH],
        "bench_fx": "달러 기준(포트와 같은 통화) · local = 현지 통화 수익률",
        "stat": {"ret": round((nav[-1] - 1) * 100, 2), "spy": round((bn["SPY"][-1] - 1) * 100, 2),
                 "kospi": round((bn["^KS11"][-1] - 1) * 100, 2), "mix": round((bn["AOR"][-1] - 1) * 100, 2),
                 "mdd": round(mdd * 100, 2), "days": len(cal) - 1, "base_honest": round((nav_h[-1] - 1) * 100, 2),
                 "win": sum(1 for x in daily if x["r"] > x["spy"]),
                 "best": max(daily, key=lambda x: x["r"]) if daily else None,
                 "worst": min(daily, key=lambda x: x["r"]) if daily else None},
        "honest": {"base": round((nav_h[-1] - 1) * 100, 2), "line": [round((v - 1) * 100, 2) for v in nav_h],
                   "rule": round((nav_rule_h[-1] - 1) * 100, 2), "rule_line": [round((v - 1) * 100, 2) for v in nav_rule_h],
                   "note": "정직 계산 — 매일이 아니라 주 1회(+배분표 바뀐 날)만 비중을 맞추고, 맞출 때마다 사고판 양 × 0.1% 비용을 뺌. 세금·환전 비용은 별도."},
        "daily": daily[-30:], "hold": hold, "changes": changes,
        "prev": prev, "miss": miss, "rule": rule,
        "note": "리포트 배분표를 그대로 따랐다면의 계산(2026-10-13부터 🦴 변동성 맞춤 방어형 반영 — vol_rule). 매일 비중 유지 가정 · 수수료·세금 제외 · 달러 기준(미국 밖 종목·지수는 환율 반영). 매수 추천 아님.",
    }
    # 10/23: 야후가 하루치(10/22)를 잠깐 빼먹어 포트가 하루 뒤로 돌아간 일 → 기존보다 옛날 기준이면 덮어쓰지 않음
    try:
        old_asof = json.loads(OUT.read_text(encoding="utf-8")).get("asof") or ""
    except Exception:
        old_asof = ""
    if old_asof and out["asof"] < old_asof and "--force" not in sys.argv:
        print(f"⚠ 새 계산 기준일 {out['asof']} < 기존 {old_asof} — 야후 시세 빠짐으로 보고 덮어쓰지 않음")
        return 0
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"포트 {out['stat']['ret']:+.2f}% vs S&P {out['stat']['spy']:+.2f}% · {out['stat']['days']}거래일 · 빠진 시세 {miss}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
