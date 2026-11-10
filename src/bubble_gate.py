"""🫧 버블 경보판 — 「주식보다 채권이 먼저 운다」 (11/10 사용자: 전병서 11/11 글을 올리며 「네 두뇌에 생각을 더해주려는 거야 · 이 글부터 바로 반영」)

  글의 경보표(빅테크 FCF · 회사채 발행 · AI CDS·신용스프레드 · 10년물·연준 · 규제·정치 · 지정학 · 반등 완충장치 · 경기침체)를
  매시간 🔴/🟠/🟢 로 갱신한다. 기계로 받을 수 있는 칸은 자동, 나머지는 brain/bubble_manual.json(두뇌가 출처와 함께 갱신).

  결과 보기 전 등록한 자동 칸 규칙 (바꾸려면 이 글과 bubble.json rules 를 같이 고친다)
  ─ 💳 신용 (HYG ÷ IEF = 하이일드가 국채보다 강한가)            🔴 20일 −1.5% 이하 또는 60일 −3% 이하 · 🟠 20일 −0.5% 이하 · 🟢 그 외
       (FRED 하이일드 스프레드는 GitHub 에서 막혀 ETF 비율로 대신 — 비율이 내려가면 스프레드가 벌어진 것)
       곁들임: 반도체(SOXX)와 신용 비율의 60일 상관 — 글 「올해 신용지수가 필라델피아 반도체와 한 몸처럼」 확인용(참고)
  ─ 📈 10년물 (^TNX)                                              🔴 5% 이상 5거래일 연속(고착) · 🟠 4.75% 이상 · 🟢 그 외
  ─ 🛢️ 지정학 = 브렌트 (BZ=F)                                     🔴 100달러 이상 · 🟠 90달러 이상 · 🟢 그 외
  ─ 🧊 속살 = 동일가중 S&P(RSP) 1년 고점 대비                     🔴 −15% 이하 · 🟠 −8% 이하 · 🟢 그 외 (글: 평균 종목 −21% · 42%가 −20% 넘게)
  ─ 🔄 순환 vs 도피 (최근 20거래일)
       방어 3종(XLP·XLV·XLU 평균) − 기술(XLK) 20일 수익 차              🟠 +3%p 이상 = 「AI 방을 빠져나와 옆방으로」(업종 갈아타기)
       🔴 「현금 도피」 = 나스닥100(QQQ) 하루 −5% 이하 날 + 그날 방어 3종도 하락 + 신용 비율 20일 하락 — 세 개 다
       (11/5 −6.36% 같은 날 · 글: 「업종을 옮겨 다니던 돈이 아예 현금으로 도망친 날」 — 🐻 하락장 계기판과 함께 본다)
  ─ 종합: 🔴·🟠·🟢 개수 · 신용 4칸(FCF·회사채·AI CDS·신용스프레드) 중 🔴 2개 이상이면 「신용 경보 켜짐」

  쓰는 법 (RULES 1-O)
  ─ 이 판은 「생각의 틀」이다. 포트 비중·현금 규칙을 혼자 바꾸지 않는다(현금은 🐻 계기판 · 비중은 아침 리포트).
  ─ 신용 경보가 켜진 동안 두뇌·리포트는 ① AI 종목을 「현금이 스스로 도는 곳(FCF+)」과 「빚으로 짓는 곳(FCF−·CDS↑)」으로 나눠 말하고
     ② ⚡ 공격 후보가 같은 점수면 FCF+·전력·데이터 인프라 쪽을 먼저 ③ 「현금 도피」가 켜진 날은 1쪽 맨 위에 계기판과 같이 적는다.
  ─ 판정이 바뀐 날을 market/bubble_log.json 에 남겨 뒤에 채점한다(그림자). 알림: 「현금 도피」가 새로 켜진 날만 ntfy.
  fetch.yml 이 매시간 돌린다. 매수·매도 추천 아님.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "market"
OUT, LOG = M / "bubble.json", M / "bubble_log.json"
MAN = ROOT / "brain" / "bubble_manual.json"
APP = "https://chkchp0702-spec.github.io/daily-app/"
SYMS = ["HYG", "IEF", "SOXX", "^TNX", "BZ=F", "RSP", "SPY", "XLP", "XLV", "XLU", "XLK", "QQQ"]
ORDER = ["fcf", "bonds", "cds", "credit", "rate", "policy", "geo", "buffer", "recession", "breadth", "flow"]
RED, ORG, GRN = "🔴", "🟠", "🟢"


def rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def chg(s, n):
    if s is None or len(s) <= n:
        return None
    a, b = float(s.iloc[-1 - n]), float(s.iloc[-1])
    return (b / a - 1) * 100 if a else None


def f1(v, unit="%", sign=True):
    if v is None:
        return "–"
    return (("+" if v > 0 else "−" if v < 0 else "") if sign else "") + f"{abs(v):.1f}{unit}"


# ───────────────────────── 자동 칸 ─────────────────────────
def g_credit(px):
    h, i = px.get("HYG"), px.get("IEF")
    if h is None or i is None:
        return None
    r = (h / i).dropna()
    c20, c60 = chg(r, 20), chg(r, 60)
    st = RED if (c20 is not None and c20 <= -1.5) or (c60 is not None and c60 <= -3) else ORG if (c20 is not None and c20 <= -0.5) else GRN
    corr = None
    sx = px.get("SOXX")
    if sx is not None:
        try:
            j = r.pct_change().to_frame("c").join(sx.pct_change().rename("s"), how="inner").dropna().tail(60)
            corr = round(float(j["c"].corr(j["s"])), 2) if len(j) >= 40 else None
        except Exception:
            corr = None
    now = f"하이일드÷국채(HYG/IEF) 20일 {f1(c20)} · 60일 {f1(c60)}" + (" — 하이일드가 국채보다 약함(스프레드 벌어짐)" if (c20 or 0) < 0 else " — 하이일드 버팀")
    if corr is not None:
        now += f" · 반도체와 60일 상관 {corr:+.2f}"
    return {"key": "credit", "name": "신용스프레드", "grp": "신용", "th": "하이일드가 국채보다 약해짐", "state": st, "now": now,
            "auto": True, "v": {"c20": None if c20 is None else round(c20, 2), "c60": None if c60 is None else round(c60, 2), "corr_soxx": corr}}


def g_rate(px):
    t = px.get("^TNX")
    if t is None or not len(t):
        return None
    v = float(t.iloc[-1])
    v = v / 10 if v > 20 else v      # 야후 ^TNX 는 예전엔 ×10
    last5 = [float(x) / (10 if float(x) > 20 else 1) for x in t.tail(5)]
    st = RED if len(last5) == 5 and min(last5) >= 5.0 else ORG if v >= 4.75 else GRN
    hi = max(float(x) / (10 if float(x) > 20 else 1) for x in t.tail(60))
    return {"key": "rate", "name": "미 10년물 금리", "grp": "바늘", "th": "5% 이상 고착", "state": st,
            "now": f"{v:.2f}% (60일 최고 {hi:.2f}%) · 5% 위 {sum(1 for x in last5 if x >= 5)}/5일", "auto": True, "v": {"y10": round(v, 3)}}


def g_geo(px):
    b = px.get("BZ=F")
    if b is None or not len(b):
        return None
    v = float(b.iloc[-1])
    st = RED if v >= 100 else ORG if v >= 90 else GRN
    return {"key": "geo", "name": "지정학 (브렌트)", "grp": "바늘", "th": "유가 재급등", "state": st,
            "now": f"브렌트 {v:.1f}달러 · 20일 {f1(chg(b, 20))} — 이란·호르무즈가 다시 뛰면 연준 셈법이 꼬임", "auto": True, "v": {"brent": round(v, 2)}}


def g_breadth(px):
    r = px.get("RSP")
    if r is None or len(r) < 60:
        return None
    hi = float(r.tail(252).max())
    dd = (float(r.iloc[-1]) / hi - 1) * 100
    sp = px.get("SPY")
    sdd = (float(sp.iloc[-1]) / float(sp.tail(252).max()) - 1) * 100 if sp is not None and len(sp) else None
    st = RED if dd <= -15 else ORG if dd <= -8 else GRN
    return {"key": "breadth", "name": "속살 (평균 종목)", "grp": "바늘", "th": "지수 밑 약세장", "state": st,
            "now": f"동일가중 S&P 1년 고점보다 {f1(dd)} · 시총가중 {f1(sdd)}" + (" — 지수보다 속이 더 아픔" if sdd is not None and dd < sdd - 2 else ""),
            "auto": True, "v": {"rsp_dd": round(dd, 2), "spy_dd": None if sdd is None else round(sdd, 2)}}


def g_flow(px):
    need = ["XLP", "XLV", "XLU", "XLK", "QQQ"]
    if any(px.get(k) is None or len(px[k]) < 25 for k in need):
        return None
    defn = sum(chg(px[k], 20) for k in ("XLP", "XLV", "XLU")) / 3
    tech = chg(px["XLK"], 20)
    gap = defn - tech
    q = px["QQQ"].pct_change() * 100
    dd_ = [px[k].pct_change() * 100 for k in ("XLP", "XLV", "XLU")]
    cr = None
    if px.get("HYG") is not None and px.get("IEF") is not None:
        cr = chg((px["HYG"] / px["IEF"]).dropna(), 20)
    flight = []
    for d in q.tail(20).index:
        if q[d] <= -5:
            dm = sum(float(s.get(d, 0) or 0) for s in dd_) / 3
            if dm < 0:
                flight.append({"d": d.strftime("%Y-%m-%d"), "qqq": round(float(q[d]), 2), "def": round(dm, 2)})
    is_flight = bool(flight) and cr is not None and cr < 0
    if is_flight:
        st, word = RED, "현금 도피"
    elif gap >= 3:
        st, word = ORG, "업종 갈아타기"
    else:
        st, word = GRN, "뚜렷한 쏠림 없음"
    now = f"{word} — 20일 방어 3종 {f1(defn)} vs 기술 {f1(tech)} (차 {f1(gap, '%p')})"
    if flight:
        now += " · 투매 날 " + ", ".join(f"{int(x['d'][5:7])}/{int(x['d'][8:])} 나스닥100 {f1(x['qqq'])}" for x in flight)
    return {"key": "flow", "name": "순환 vs 현금 도피", "grp": "바늘", "th": "방어주로 순환 → 투매", "state": st, "now": now,
            "auto": True, "word": word, "v": {"def20": round(defn, 2), "tech20": round(tech, 2), "flight": flight}}


def load():
    import yfinance as yf
    start = (dt.date.today() - dt.timedelta(days=420)).isoformat()
    df = yf.download(SYMS, start=start, auto_adjust=True, progress=False, group_by="ticker", threads=True)
    out = {}
    for s in SYMS:
        try:
            out[s] = df[s]["Close"].dropna()
        except Exception as e:
            print("시세 실패", s, e)
    return out


def notify(title, body):
    try:
        urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=json.dumps({
            "topic": "chkchp-ch-report", "title": title, "message": body,
            "click": APP + "#home~bubble", "tags": ["warning"]}).encode(),
            headers={"Content-Type": "application/json"}), timeout=15).read()
    except Exception as e:
        print("알림 실패", e)


def build(px, man, now=None):
    now = now or dt.datetime.now(KST)
    items = {x["key"]: dict(x, auto=False) for x in (man or {}).get("items", [])}
    for g in (g_credit, g_rate, g_geo, g_breadth, g_flow):
        try:
            r = g(px)
        except Exception as e:
            print("칸 실패", g.__name__, e)
            r = None
        if r:
            r["src"] = "자동 · 야후 종가"
            r["at"] = now.strftime("%Y-%m-%d %H:%M")
            items[r["key"]] = r
    L = [items[k] for k in ORDER if k in items] + [v for k, v in items.items() if k not in ORDER]
    red = sum(1 for x in L if x["state"] == RED)
    org = sum(1 for x in L if x["state"] == ORG)
    grn = sum(1 for x in L if x["state"] == GRN)
    cred = sum(1 for x in L if x.get("grp") == "신용" and x["state"] == RED)
    flow = items.get("flow", {})
    credit_on = cred >= 2
    if flow.get("state") == RED:
        lead = "🔴 현금 도피 — 업종을 갈아타던 돈이 현금으로 나갔어요. 🐻 계기판 판정을 먼저 보고, 빚으로 짓는 AI부터 줄일 때"
    elif credit_on:
        lead = "🔴 주식보다 채권이 먼저 울고 있어요. 새로 담을 땐 현금이 스스로 도는 곳(FCF+)·전력·데이터 인프라부터"
    elif red >= 3:
        lead = "🟠 경보가 여러 개 — 새로 살 땐 현금흐름(FCF+) 먼저 확인"
    else:
        lead = "🟢 경보 적음 — 평소대로"
    sub = ""
    if any(x["key"] == "buffer" and x["state"] == GRN for x in L):
        sub = "다만 완충장치(CTA 매도 소진·자사주·중간선거 효과)가 살아 있어 단기 반등 여지는 있음 — 붕괴를 점칠 때가 아니라 출구를 설계할 때"
    return {
        "at": now.strftime("%Y-%m-%d %H:%M"),
        "head": f"🫧 버블 경보 🔴{red} · 🟠{org} · 🟢{grn}" + (" · 신용 경보 켜짐" if credit_on else ""),
        "lead": lead, "sub": sub, "red": red, "orange": org, "green": grn, "credit_on": credit_on,
        "flow": flow.get("word"), "items": L,
        "dates": [d for d in (man or {}).get("dates", []) if d.get("d", "") >= now.strftime("%Y-%m-%d")],
        "frame": (man or {}).get("frame"),
        "rules": {"credit": "HYG/IEF 20일 ≤−1.5% 또는 60일 ≤−3% 🔴 · 20일 ≤−0.5% 🟠",
                  "rate": "10년물 5% 이상 5일 연속 🔴 · 4.75% 이상 🟠",
                  "geo": "브렌트 100$ 🔴 · 90$ 🟠",
                  "breadth": "RSP 1년 고점 대비 −15% 🔴 · −8% 🟠",
                  "flow": "QQQ 하루 −5%↓ + 방어주도 하락 + 신용 비율 20일 하락 = 현금 도피 🔴 · 방어−기술 20일 +3%p = 업종 갈아타기 🟠",
                  "credit_on": "신용 4칸(FCF·회사채·AI CDS·신용스프레드) 중 🔴 2개 이상",
                  "use": "생각의 틀 — 포트 비중·현금 규칙을 혼자 바꾸지 않음(그림자 채점)"},
        "note": "출처: 전병서 「AI 버블, 지금 몇 시인가」(2026-11-11) 경보표를 틀로 · 자동 칸은 야후 종가 · 손 칸은 두뇌가 출처와 함께 갱신 · 매수·매도 추천 아님",
    }


def main():
    dry = "--dry" in sys.argv
    man = rj(MAN, {})
    try:
        px = load()
    except Exception as e:
        print("시세 못 받음 — 손 칸만", e)
        px = {}
    out = build(px, man)
    prev = rj(OUT, {}) or {}
    M.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sig = lambda o: [(x["key"], x["state"]) for x in o.get("items", [])]
    if sig(prev) != sig(out):
        log = rj(LOG, []) or []
        log.append({"at": out["at"], "head": out["head"], "states": dict(sig(out))})
        LOG.write_text(json.dumps(log[-400:], ensure_ascii=False, indent=0), encoding="utf-8")
    was = next((x for x in prev.get("items", []) if x["key"] == "flow"), {}).get("state")
    if out.get("flow") == "현금 도피" and was != RED and not dry:
        notify("🫧 현금 도피 신호", next(x for x in out["items"] if x["key"] == "flow")["now"])
    print(out["head"], "|", out["lead"])


if __name__ == "__main__":
    main()
