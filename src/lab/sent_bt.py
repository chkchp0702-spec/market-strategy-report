"""🫀 심리 규칙 검증 (사전 등록 R1·R1x·R4 그대로 — brain/sentiment_lab.md) → market/sentiment_bt.json
  R1·R1x : ^VIX·^VIX3M 2007~ (yfinance) · SPY 앞으로 5·20거래일
  R4     : 외국인 코스피200 선물 일별 순매수(계약, 네이버 m.stock api backfill market/lab/kr_flow_hist.json) · ^KS11 앞으로 5·20거래일
  비교: 같은 기간 아무 날(기저) 평균 · 신호는 「첫날」만 세고 20일 안 재발은 묶음(겹침 제거)
"""
import json, math, statistics as st
from pathlib import Path
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "market" / "sentiment_bt.json"


def closes(sym, period="max"):
    h = yf.Ticker(sym).history(period=period, auto_adjust=True)
    return {i.strftime("%Y-%m-%d"): float(c) for i, c in zip(h.index, h["Close"]) if not math.isnan(float(c))}


def fwd(px_dates, px, d, n):
    i = next((k for k, x in enumerate(px_dates) if x >= d), None)
    if i is None or i + n >= len(px_dates):
        return None
    return (px[px_dates[i + n]] / px[px_dates[i]] - 1) * 100


def stat(rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return {"n": 0}
    return {"n": len(rs), "avg": round(st.mean(rs), 2), "med": round(st.median(rs), 2),
            "win": round(100 * sum(r > 0 for r in rs) / len(rs)), "sd": round(st.pstdev(rs), 2) if len(rs) > 1 else None,
            "worst": round(min(rs), 2)}


def dedup(days, gap=20, order=None):
    out, last = [], None
    for d in days:
        if last is None or order[d] - order[last] > gap:
            out.append(d); last = d
    return out


def main():
    res = {}
    spy = closes("SPY"); vix = closes("^VIX"); v3 = closes("^VIX3M")
    sd = sorted(spy); order = {d: i for i, d in enumerate(sd)}
    common = [d for d in sd if d in vix and d in v3]
    base5 = [fwd(sd, spy, d, 5) for d in common]; base20 = [fwd(sd, spy, d, 20) for d in common]
    res["base_spy"] = {"from": common[0], "r5": stat(base5), "r20": stat(base20)}
    vv = [vix[d] for d in common]
    r1, r1x, bw = [], [], []
    for k, d in enumerate(common):
        b = vix[d] > v3[d]
        if b:
            bw.append(d)
        win = vv[max(0, k - 251):k + 1]
        p = sum(x <= vix[d] for x in win) / len(win) * 100
        if b and p >= 90 and len(win) >= 200:
            r1.append(d)
        if k and (vix[common[k - 1]] > v3[common[k - 1]]) and not b:
            r1x.append(d)
    for name, days in (("R1", r1), ("R1x", r1x), ("backwardation_all", bw)):
        dd = dedup(days, 20, order) if name != "backwardation_all" else days
        res[name] = {"days": len(days), "episodes": len(dd),
                     "r5": stat([fwd(sd, spy, d, 5) for d in dd]), "r20": stat([fwd(sd, spy, d, 20) for d in dd]),
                     "since2018_r20": stat([fwd(sd, spy, d, 20) for d in dd if d >= "2018-01-01"]),
                     "last5": dd[-5:]}
    # R1x 변형: 역전이 3일↑ 이어진 뒤 풀린 날만 (짧은 깜빡임 제외)
    r1x3 = []
    for k, d in enumerate(common):
        if k >= 3 and not (vix[d] > v3[d]) and all(vix[common[k - j]] > v3[common[k - j]] for j in (1, 2, 3)):
            r1x3.append(d)
    dd = dedup(r1x3, 20, order)
    res["R1x_3d"] = {"episodes": len(dd), "r5": stat([fwd(sd, spy, d, 5) for d in dd]), "r20": stat([fwd(sd, spy, d, 20) for d in dd]),
                     "note": "변형(사후 탐색) — 판정엔 안 씀"}

    # R4 한국 선물
    flow = json.loads((ROOT / "market/lab/kr_flow_hist.json").read_text())
    ks = closes("^KS11", "5y"); kd = sorted(ks); ko = {d: i for i, d in enumerate(kd)}
    fd = sorted(d for d in flow if "FUT" in flow[d])
    fut = {d: flow[d]["FUT"][1] for d in fd}
    spot = {d: flow[d]["KOSPI"][1] for d in fd if "KOSPI" in flow[d]}
    kb5 = [fwd(kd, ks, d, 5) for d in fd]; kb20 = [fwd(kd, ks, d, 20) for d in fd]
    res["base_kospi"] = {"from": fd[0] if fd else None, "to": fd[-1] if fd else None, "days": len(fd), "r5": stat(kb5), "r20": stat(kb20)}
    fo = {d: i for i, d in enumerate(fd)}  # 겹침 제거는 수급 날짜 순서로 (휴장 차이 무시)
    s5 = {}
    for k in range(4, len(fd)):
        s5[fd[k]] = sum(fut[fd[k - j]] for j in range(5))
    r4 = []
    for k in range(5, len(fd)):
        d, p = fd[k], fd[k - 1]
        if p in s5 and d in s5 and s5[p] <= -10000 and s5[d] > 0:
            r4.append(d)
    dd = dedup(r4, 10, fo)
    res["R4"] = {"days": len(r4), "episodes": len(dd), "r5": stat([fwd(kd, ks, d, 5) for d in dd]),
                 "r20": stat([fwd(kd, ks, d, 20) for d in dd]), "list": dd[-10:]}
    # 강건성: 문턱 바꿔 보기 (사후 — 판정엔 안 씀)
    rob = {}
    for th in (-5000, -20000, -30000):
        x = [fd[k] for k in range(5, len(fd)) if fd[k - 1] in s5 and s5[fd[k - 1]] <= th and s5[fd[k]] > 0]
        x = dedup(x, 10, fo)
        rob[str(th)] = {"episodes": len(x), "r5": stat([fwd(kd, ks, d, 5) for d in x]), "r20": stat([fwd(kd, ks, d, 20) for d in x])}
    res["R4_robust"] = rob
    # 5분위: 외국인 선물 5일 누적 → 다음 5일 코스피
    pairs = [(s5[d], fwd(kd, ks, d, 5)) for d in s5 if fwd(kd, ks, d, 5) is not None]
    pairs.sort()
    q = []
    for i in range(5):
        seg = pairs[i * len(pairs) // 5:(i + 1) * len(pairs) // 5]
        if seg:
            q.append({"q": i + 1, "s5_lo": seg[0][0], "s5_hi": seg[-1][0], "fwd5": stat([r for _, r in seg])})
    res["fut_s5_quintile"] = q
    # 극단 매도 그 자체(지금 −2만↓) 다음 5일
    ext = dedup(sorted(d for d in s5 if s5[d] <= -20000), 10, fo) if s5 else []
    res["fut_s5_le_-20000"] = {"episodes": len(ext), "r5": stat([fwd(kd, ks, d, 5) for d in sorted(ext)]), "r20": stat([fwd(kd, ks, d, 20) for d in sorted(ext)])}
    # 선물 vs 현물 엇갈림: 외국인 현물 5일 매도인데 선물 5일 매수 → ?
    div = []
    for k in range(4, len(fd)):
        d = fd[k]
        if all(fd[k - j] in spot for j in range(5)):
            sp5 = sum(spot[fd[k - j]] for j in range(5))
            if sp5 < 0 and s5.get(d, 0) > 10000:
                div.append(d)
    div = dedup(div, 10, fo)
    res["fut_buy_spot_sell"] = {"episodes": len(div), "r5": stat([fwd(kd, ks, d, 5) for d in div]), "r20": stat([fwd(kd, ks, d, 20) for d in div]),
                                "rule": "외국인 현물 5일 순매도 + 선물 5일 +1만 계약↑"}
    res["now"] = {"fut_s5": s5.get(fd[-1]) if fd else None, "fut_today": fut.get(fd[-1]) if fd else None, "d": fd[-1] if fd else None}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
