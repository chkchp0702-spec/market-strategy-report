"""🌱 11/9 사용자 「각 시장마다 그냥 들고 있었을 때 대비 수익률을 극대화할 현금 비중 방법 더 연구해봐」
  묻는 것: 시장(코스피·S&P500·나스닥)마다 「언제 얼마나 현금으로 두면」 그냥 보유보다 연수익이 가장 많이 앞서나.
  규칙(결과 보기 전): 판은 모두 2012-12-31 까지(앞)로만 고르고, 2013~(뒤)에서 그대로 확인한다.
        「연수익 − 보유 연수익」(초과)을 앞·뒤 모두에서 보고, 뒤에서도 + 인 것만 「믿을 만함」. 판이 수십 개라 앞에서 1등은 운일 수 있다 →
        가족(방법 종류) 안에서 이웃 설정도 같이 좋은지(울퉁불퉁하면 운) 본다. 최대낙폭·바꾸는 횟수도 같이 적는다.
  가족:
    DD  낙폭 사다리(지금 계기판 틀): 고점(252일) 대비 −t1 🟡 / −t2 🐻 → 현금 c1 / c2 · 🐻 는 −t1 위 + 200일선 위까지 유지(F) — t·c 격자
    MA  이동평균 아래면 현금 X: n ∈ 100·150·200·250 · X ∈ 50·100 · 띠(±2%)로 깜빡임 거름 유/무
    MOM 12개월 모멘텀(252일 전보다 낮으면 현금 X) · 6개월
    FAB 10개월 이동평균 월말 판정(파버) X ∈ 50·100
    VOL 변동성 맞춤: 주식 비중 = min(1, 목표/20일 변동성) · 목표 10·15·20%
    MIX 낙폭 사다리 + 200일선(둘 중 현금 큰 쪽) · 낙폭 사다리 + 변동성
    E/F 지금 규칙(코스피 E · 미국 F) · H 보유
  셈: 다음 날 비중 · 현금 연 2% · 바꿀 때 0.1% · 가격지수 · 🇰🇷 ④는 50일선
→ market/lab/b1109_cash.json · 표는 로그(_last_log.txt)
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.bear_gate import judge, aligned_vix, load, MKTS, RULE, rule_cash

OUT = Path("market/lab/b1109_cash.json")
SPLIT = "2013-01-01"
WARM = 252


def sma(cl):
    """누적합으로 빠른 이동평균 함수"""
    cs = [0.0]
    for x in cl:
        cs.append(cs[-1] + x)
    return lambda n, i: None if i + 1 < n else (cs[i + 1] - cs[i + 1 - n]) / n


# ───────── 가족별 현금 시계열 (0~100) ─────────
def fam_dd(cl, t1, t2, c1, c2, reentry="F", vx=None):
    """낙폭 사다리 — 🟡(−t1) c1 · 🐻(−t2) c2 · 🐻 는 −t1 위 + 200일선 위까지 유지 · reentry E 면 ①+④→c2/3·+②→0"""
    S, out, pb = sma(cl), [], False
    for i in range(len(cl)):
        if i < WARM:
            out.append(0)
            continue
        hi = max(cl[max(0, i - 251):i + 1])
        dd = cl[i] / hi - 1
        m200 = S(200, i)
        if dd <= -t2 / 100:
            st = 2
        elif pb and not (dd > -t1 / 100 and m200 is not None and cl[i] > m200):
            st = 2
        elif dd <= -t1 / 100:
            st = 1
        else:
            st = 0
        pb = st == 2
        c = [0, c1, c2][st]
        if reentry == "E" and st:
            w = cl[max(0, i - 59):i + 1]
            lo = min(w)
            lo_ago = len(w) - 1 - max(k for k, x in enumerate(w) if x == lo)
            m20, m20p, m50 = S(20, i), S(20, i - 1), S(50, i)
            o1 = lo_ago >= 10
            o2 = m20 is not None and m20p is not None and cl[i] > m20 and cl[i - 1] > m20p
            o4 = m50 is not None and cl[i] > m50
            if o1 and o4:
                c = 0 if (o2 or st == 1) else round(c / 3)
        out.append(c)
    return out


def fam_ma(cl, n, x, band=0.0):
    S, out, under = sma(cl), [], False
    for i in range(len(cl)):
        m = S(n, i)
        if i < WARM or m is None:
            out.append(0)
            continue
        if under:
            under = cl[i] < m * (1 + band)
        else:
            under = cl[i] < m * (1 - band)
        out.append(x if under else 0)
    return out


def fam_mom(cl, n, x):
    return [0 if i < max(WARM, n) else (x if cl[i] < cl[i - n] else 0) for i in range(len(cl))]


def fam_fab(cl, dates, x, n=10):
    """파버: 매월 마지막 거래일 종가 vs 10개월(≈210일) 이동평균 → 다음 달 동안 유지"""
    S, out, cur = sma(cl), [], 0
    for i in range(len(cl)):
        last_of_month = i + 1 == len(cl) or dates[i + 1][:7] != dates[i][:7]
        if i >= WARM and last_of_month:
            m = S(21 * n, i)
            cur = x if (m is not None and cl[i] < m) else 0
        out.append(0 if i < WARM else cur)
    return out


def fam_vol(cl, target):
    out, rets = [], [0.0]
    for i in range(1, len(cl)):
        rets.append(math.log(cl[i] / cl[i - 1]))
    for i in range(len(cl)):
        if i < WARM:
            out.append(0)
            continue
        w = rets[i - 19:i + 1]
        mu = sum(w) / 20
        sd = math.sqrt(sum((r - mu) ** 2 for r in w) / 19) * math.sqrt(252)
        eq = 1.0 if sd == 0 else min(1.0, target / 100 / sd)
        out.append(round((1 - eq) * 100))
    return out


def fam_now(cl, vx, key):
    """지금 계기판 규칙(🇰🇷 E · 🇺🇸 F) — bear_gate.judge 그대로"""
    out, pb = [], False
    for i in range(len(cl)):
        if i < WARM:
            out.append(0)
            continue
        j = judge(cl, vx, None, "us", pb, i)
        pb = j["state"] == "🐻"
        out.append(rule_cash(RULE.get(key, "F"), j["state"], [bool(c["on"]) for c in j["checks"]]))
    return out


def mix_max(a, b):
    return [max(x, y) for x, y in zip(a, b)]


# ───────── 성적 ─────────
def run(cl, dates, cs, lo_d=None, hi_d=None):
    nav = bh = pn = pb_ = 1.0
    mn = mb = 0.0
    sw, n_days, w_prev = 0, 0, None
    for i in range(WARM + 1, len(cl)):
        d = dates[i]
        if (lo_d and d < lo_d) or (hi_d and d >= hi_d):
            w_prev = 1 - cs[i] / 100
            continue
        if w_prev is None:
            w_prev = 1 - cs[i - 1] / 100
        r = cl[i] / cl[i - 1] - 1
        nav *= 1 + w_prev * r + (1 - w_prev) * 0.02 / 252
        bh *= 1 + r
        pn, pb_ = max(pn, nav), max(pb_, bh)
        mn, mb = min(mn, nav / pn - 1), min(mb, bh / pb_ - 1)
        w = 1 - cs[i] / 100
        if abs(w - w_prev) > 1e-9:
            nav *= 1 - 0.001 * abs(w - w_prev)
            sw += 1
        w_prev = w
        n_days += 1
    y = max(n_days, 1) / 252
    cg, hg = (nav ** (1 / y) - 1) * 100, (bh ** (1 / y) - 1) * 100
    return {"cagr": round(cg, 2), "mdd": round(mn * 100, 1), "hold": round(hg, 2), "hold_mdd": round(mb * 100, 1),
            "ex": round(cg - hg, 2), "sw_y": round(sw / y, 1), "cash_avg": round(sum(cs[i] for i in range(WARM, len(cs))) / max(1, len(cs) - WARM), 1)}


def variants(cl, dates, vx, key):
    V = {}
    for t1, t2 in [(10, 20), (8, 15), (12, 25), (15, 30), (5, 10)]:
        for c1, c2 in [(10, 30), (20, 50), (30, 70), (50, 100), (0, 50), (0, 100)]:
            V[f"DD t{t1}/{t2} c{c1}/{c2}"] = ("DD", fam_dd(cl, t1, t2, c1, c2))
    for n in (100, 150, 200, 250):
        for x in (50, 100):
            V[f"MA{n} c{x}"] = ("MA", fam_ma(cl, n, x))
            V[f"MA{n} c{x} 띠2%"] = ("MA", fam_ma(cl, n, x, 0.02))
    for n, nm in ((252, "12개월"), (126, "6개월")):
        for x in (50, 100):
            V[f"MOM {nm} c{x}"] = ("MOM", fam_mom(cl, n, x))
    for x in (50, 100):
        V[f"FAB 10개월 월말 c{x}"] = ("FAB", fam_fab(cl, dates, x))
    for tg in (10, 15, 20):
        V[f"VOL 목표{tg}%"] = ("VOL", fam_vol(cl, tg))
    dd_now = fam_dd(cl, 10, 20, 10, 30)
    for n in (200,):
        for x in (50, 100):
            V[f"MIX DD10/20 c10/30 + MA{n} c{x}"] = ("MIX", mix_max(dd_now, fam_ma(cl, n, x, 0.02)))
    V["MIX DD10/20 c10/30 + VOL15"] = ("MIX", mix_max(dd_now, fam_vol(cl, 15)))
    V["MIX DD10/20 c30/70 + MA200 c50"] = ("MIX", mix_max(fam_dd(cl, 10, 20, 30, 70), fam_ma(cl, 200, 50, 0.02)))
    V["DD t10/20 c10/30 E(코스피 틀)"] = ("DD", fam_dd(cl, 10, 20, 10, 30, "E"))
    V["지금 규칙 (" + RULE.get(key, "F") + ")"] = ("NOW", fam_now(cl, vx, key))
    V["H 그냥 보유"] = ("H", [0] * len(cl))
    return V


def study(key, name, cl, dates, vx):
    V = variants(cl, dates, vx, key)
    rows = []
    for nm, (fam, cs) in V.items():
        rows.append({"name": nm, "fam": fam, "all": run(cl, dates, cs), "is": run(cl, dates, cs, None, SPLIT), "oos": run(cl, dates, cs, SPLIT, None)})
    # 가족별 「앞에서 1등 → 뒤 확인」 + 전체 1등
    fams = {}
    for r in rows:
        if r["fam"] in ("H",):
            continue
        fams.setdefault(r["fam"], []).append(r)
    pick = {}
    for f, rs in fams.items():
        best = max(rs, key=lambda r: r["is"]["ex"])
        # 이웃 안정성: 그 가족에서 앞 초과가 + 인 비율
        pick[f] = {"name": best["name"], "is_ex": best["is"]["ex"], "oos_ex": best["oos"]["ex"], "all_ex": best["all"]["ex"],
                   "mdd": best["all"]["mdd"], "sw_y": best["all"]["sw_y"], "fam_pos_is": round(sum(r["is"]["ex"] > 0 for r in rs) / len(rs) * 100),
                   "fam_pos_oos": round(sum(r["oos"]["ex"] > 0 for r in rs) / len(rs) * 100), "n": len(rs)}
    robust = sorted([r for r in rows if r["fam"] != "H" and r["is"]["ex"] > 0 and r["oos"]["ex"] > 0], key=lambda r: -min(r["is"]["ex"], r["oos"]["ex"]))
    return {"key": key, "name": name, "from": dates[WARM], "to": dates[-1], "split": SPLIT, "rows": rows, "pick": pick,
            "robust": [r["name"] for r in robust[:10]]}


def show(m):
    print(f"\n== {m['name']} {m['from']} ~ {m['to']} (앞 ~2012 · 뒤 2013~)   초과 = 연수익 − 보유")
    hold = next(r for r in m["rows"] if r["fam"] == "H")
    print(f"   보유: 전체 {hold['all']['hold']:.2f}% (낙폭 {hold['all']['hold_mdd']}) · 앞 {hold['is']['hold']:.2f} · 뒤 {hold['oos']['hold']:.2f}")
    print(f"   {'가족 1등(앞 기준)':<36}{'앞 초과':>8}{'뒤 초과':>8}{'전체':>7}{'낙폭':>7}{'바꿈/년':>7}  가족 안 + 비율(앞/뒤)")
    for f, p in m["pick"].items():
        print(f"   {p['name']:<36}{p['is_ex']:>+8.2f}{p['oos_ex']:>+8.2f}{p['all_ex']:>+7.2f}{p['mdd']:>7.1f}{p['sw_y']:>7.1f}  {p['fam_pos_is']}%/{p['fam_pos_oos']}% (n={p['n']})")
    print("   앞·뒤 모두 보유보다 나은 것(약한 쪽 초과 큰 순):")
    for nm in m["robust"]:
        r = next(x for x in m["rows"] if x["name"] == nm)
        print(f"     {nm:<36} 앞 {r['is']['ex']:+.2f} · 뒤 {r['oos']['ex']:+.2f} · 전체 {r['all']['ex']:+.2f} · 낙폭 {r['all']['mdd']} · 바꿈 {r['all']['sw_y']}/년 · 평균 현금 {r['all']['cash_avg']}%")
    top = sorted([r for r in m["rows"] if r["fam"] != "H"], key=lambda r: -r["all"]["ex"])[:5]
    print("   전체 기간 초과 1~5등(참고 — 결과 보고 고른 것이라 운 섞임):")
    for r in top:
        print(f"     {r['name']:<36} 전체 {r['all']['ex']:+.2f} (앞 {r['is']['ex']:+.2f} · 뒤 {r['oos']['ex']:+.2f}) · 낙폭 {r['all']['mdd']}")


def main():
    res = {"at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "split": SPLIT, "markets": []}
    if "--local" in sys.argv:
        for key, name, fp in [("kospi", "코스피(로컬)", "/home/claude/daily-app/archive/x/port_px/KOSPI.json"),
                              ("sp500", "S&P500(SPY 로컬)", "/home/claude/daily-app/archive/x/port_px/SPY.json"),
                              ("nasdaq", "나스닥(QQQ 로컬)", "/home/claude/daily-app/archive/x/port_px/QQQ.json")]:
            j = json.load(open(fp))
            d, dates = dt.date.fromisoformat(j["d0"]), []
            for x in j["dd"]:
                d = d + dt.timedelta(days=x)
                dates.append(d.isoformat())
            res["markets"].append(study(key, name, j["c"][:-1], dates[:-1], None))
    else:
        px = load("1999-01-01")
        vix = px.get("vix")
        for key, _, name, nat, _ in MKTS:
            s = px.get(key)
            if s is None:
                continue
            res["markets"].append(study(key, name, [float(x) for x in s.tolist()], [str(t.date()) for t in s.index], aligned_vix(s, vix)))
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in res["markets"]:
        show(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
