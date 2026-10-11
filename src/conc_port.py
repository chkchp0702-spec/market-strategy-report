"""🎯 집중 포트 — 「오르는 시장이면 벌 때 번다」 (10/11 사용자: 선택과 집중 · 단 오르는 시장 판단이 먼저)

  검증(src/conc_bt.py → market/conc_bt.json)에서 고른 규칙:
    · 오르는 시장 판정 = S&P500 이 200일선 위 (바뀐 상태가 3거래일 이어져야 인정 — 깜빡임 방지)
    · 🟢 상승장: S&P500 50% + 나스닥100 50% (주식 100%, 현금·금 0)
    · 🔴 아니면: S&P500 25% + 나스닥100 25% + 현금 50%
    · 레버리지 없음(10/11 사용자) · 판단은 그날 종가, 비중은 다음 거래일 종가부터 · 매주 + 판정 바뀐 날 비중 맞춤 · 사고판 양 × 0.1% 비용
  💼 기본 · ⚡ 킥 포트와 나란히 같은 날(START)부터 계산 → market/conc.json
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "market"
OUT = M / "conc.json"
KST = dt.timezone(dt.timedelta(hours=9))
START = "2026-10-02"       # 💼 포트와 같은 출발일
COST = 0.001
STICK = 3
ON = {"SPY": 0.5, "QQQ": 0.5}
OFF = {"SPY": 0.25, "QQQ": 0.25, "BIL": 0.5}
INFO = {"SPY": {"name": "S&P500", "kr": {"code": "360750", "name": "TIGER 미국S&P500"}},
        "QQQ": {"name": "나스닥100", "kr": {"code": "133690", "name": "TIGER 미국나스닥100"}},
        "BIL": {"name": "현금·단기채", "us": "SGOV", "kr": {"code": "499660", "name": "TIGER CD금리"}}}


def rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d if d is not None else {}


def sticky(vals, k=STICK):
    out, cur, run = [], bool(vals[0]) if len(vals) else False, 0
    for v in vals:
        v = bool(v)
        if v != cur:
            run += 1
            if run >= k:
                cur, run = v, 0
        else:
            run = 0
        out.append(cur)
    return out


def main() -> int:
    import pandas as pd
    import yfinance as yf
    now = dt.datetime.now(KST)
    tick = ["^GSPC", "SPY", "QQQ", "BIL", "^KS11"]
    df = yf.download(tick, start="2024-06-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick if t in df.columns.get_level_values(0)})
    ks = C["^KS11"].dropna()
    C = C.drop(columns=["^KS11"]).dropna(subset=["^GSPC", "SPY", "QQQ"]).ffill()
    g = C["^GSPC"]
    ma200, ma50 = g.rolling(200).mean(), g.rolling(50).mean()
    raw = (g > ma200).fillna(False)
    reg = pd.Series(sticky(raw.values), index=C.index)
    kraw = (ks > ks.rolling(200).mean()).fillna(False)
    kreg = pd.Series(sticky(kraw.values), index=ks.index)

    # 판정이 바뀐 날들 (최근 2년)
    flips = []
    for i in range(1, len(reg)):
        if reg.iloc[i] != reg.iloc[i - 1]:
            flips.append({"d": reg.index[i].strftime("%Y-%m-%d"), "up": bool(reg.iloc[i])})
    since = flips[-1]["d"] if flips else reg.index[0].strftime("%Y-%m-%d")

    # 출발일 전날 종가에 산다(그날 종가 판정) → 출발일부터 하루하루 수익 · 💼 포트와 같은 기준
    cal = [d for d in C.index if d.strftime("%Y-%m-%d") >= START]
    R = C[["SPY", "QQQ", "BIL"]].pct_change().fillna(0.0)
    A3 = ("SPY", "QQQ", "BIL")
    p0 = C.index[C.index.get_loc(cal[0]) - 1]
    last_up = bool(reg.loc[p0])
    w = dict(ON if last_up else OFF)
    val, turn, wk = 1 - COST, 1.0, p0.isocalendar()[1]
    events = [{"d": cal[0].strftime("%Y-%m-%d"), "k": "시작", "up": last_up}]
    nav = []
    for d in cal:
        r = R.loc[d]
        val *= 1 + sum(w.get(t, 0) * float(r[t]) for t in A3)
        gw = {t: w.get(t, 0) * (1 + float(r[t])) for t in A3}
        s_ = sum(gw.values())
        w = {t: v / s_ for t, v in gw.items()}
        nav.append(round((val - 1) * 100, 2))
        up_now = bool(reg.loc[d])          # 오늘 종가 판정 → 다음 거래일부터
        if up_now != last_up or d.isocalendar()[1] != wk:
            nt = ON if up_now else OFF
            t_ = sum(abs(nt.get(t, 0) - w.get(t, 0)) for t in A3)
            turn += t_; val *= 1 - t_ * COST; w = dict(nt)
            if up_now != last_up:
                events.append({"d": d.strftime("%Y-%m-%d"), "k": "판정 바뀜", "up": up_now})
            wk, last_up = d.isocalendar()[1], up_now
    spy = [round((float(C.loc[d, "SPY"]) / float(C.loc[p0, "SPY"]) - 1) * 100, 2) for d in cal]
    qqq = [round((float(C.loc[d, "QQQ"]) / float(C.loc[p0, "QQQ"]) - 1) * 100, 2) for d in cal]

    up = bool(reg.iloc[-1])
    tgt = ON if up else OFF
    gap = float(g.iloc[-1] / ma200.iloc[-1] - 1) * 100
    P, K = rj(M / "port.json"), rj(M / "kick.json")
    BT = rj(M / "conc_bt.json")
    row = next((x for x in (BT.get("exposure") or {}).get("rows", []) if x.get("k") == "sq" and x.get("reg") == "A"), None)
    cur = next((x for x in (BT.get("exposure") or {}).get("rows", []) if x.get("k") == "cur"), None)
    bt = None
    if row:
        bt = {"oos": row.get("oos"), "is": row.get("is"), "full": row.get("full"), "yr": row.get("yr"),
              "spy_oos": (BT.get("spy") or {}).get("oos"), "spy_full": (BT.get("spy") or {}).get("full"),
              "cur_oos": (cur or {}).get("oos"), "period": BT.get("oos"), "at": BT.get("at"),
              "regime": ((BT.get("regime") or {}).get("A") or {}).get("spx_oos"),
              "line": row.get("line"), "spy_line": (BT.get("exposure") or {}).get("spy_line")}

    prev_out = rj(OUT)
    out = {
        "at": now.strftime("%Y-%m-%d %H:%M"), "start": START, "asof": cal[-1].strftime("%Y-%m-%d") if cal else None,
        "rule": {"title": "🎯 집중 포트", "judge": "S&P500 200일선 위 · 3거래일 확인",
                 "on": "🟢 상승장 → S&P500 50% + 나스닥100 50% (주식 100%)", "off": "🔴 아니면 → S&P500 25% + 나스닥100 25% + 현금 50%",
                 "how": "판정은 그날 종가 · 다음 거래일부터 · 매주 + 판정 바뀐 날 비중 맞춤 · 사고판 양 × 0.1% 비용 · 레버리지 없음"},
        "regime": {"up": up, "since": since, "spx": round(float(g.iloc[-1]), 1), "ma200": round(float(ma200.iloc[-1]), 1),
                   "ma50": round(float(ma50.iloc[-1]), 1), "gap": round(gap, 1),
                   "ma200_up": bool(ma200.iloc[-1] > ma200.iloc[-21]), "raw_today": bool(raw.iloc[-1]),
                   "kospi_up": bool(kreg.iloc[-1]) if len(kreg) else None,
                   "kospi_gap": round(float(ks.iloc[-1] / ks.rolling(200).mean().iloc[-1] - 1) * 100, 1) if len(ks) > 200 else None,
                   "flips": flips[-8:][::-1]},
        "now": [{"t": t, "pct": round(x * 100), **INFO[t]} for t, x in tgt.items()],
        "dates": [d.strftime("%Y-%m-%d") for d in cal], "nav": nav, "spy": spy, "qqq": qqq,
        "ret": nav[-1] if nav else None, "spy_ret": spy[-1] if spy else None, "qqq_ret": qqq[-1] if qqq else None,
        "d1": round(((1 + nav[-1] / 100) / (1 + nav[-2] / 100) - 1) * 100, 2) if len(nav) > 1 else None,
        "base": (P.get("stat") or {}).get("ret"), "kick": (K.get("stat") or {}).get("kick"),
        "turn": round(turn * 100), "events": events[::-1][:10], "bt": bt,
        "note": "검증한 규칙을 그대로 따랐다면의 계산(비용 포함·달러 기준). 매수 추천 아님.",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"🎯 집중 {'🟢 상승장' if up else '🔴 아님'}(S&P 200일선 {gap:+.1f}%) · {out['ret']}% vs S&P {out['spy_ret']}% · 기본 {out['base']} · 킥 {out['kick']}")

    # 판정이 바뀌면 알림 한 번
    pu = (prev_out.get("regime") or {}).get("up")
    if pu is not None and pu != up:
        try:
            import urllib.request
            msg = ("🟢 오르는 시장으로 바뀜 — S&P500 50% + 나스닥100 50%로 주식 100%" if up
                   else "🔴 오르는 시장이 아님 — 주식 절반으로 줄이고 현금 50%") + f"\nS&P {out['regime']['spx']} · 200일선 {gap:+.1f}%"
            urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=json.dumps({
                "topic": "chkchp-ch-report", "title": "🎯 집중 포트 판정 바뀜", "message": msg,
                "click": "https://chkchp0702-spec.github.io/daily-app/#port~poconc", "tags": ["dart"]}).encode(),
                headers={"Content-Type": "application/json"}), timeout=15).read()
        except Exception as ex:
            print("알림 실패", ex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
