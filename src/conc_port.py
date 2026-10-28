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
import sys
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
    tick = ["^GSPC", "SPY", "QQQ", "BIL", "^KS11", "IEF", "TLT"]
    df = yf.download(tick, start="2024-06-01", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    C = pd.DataFrame({t: df[t]["Close"] for t in tick if t in df.columns.get_level_values(0)})
    ks = C["^KS11"].dropna()
    C = C.drop(columns=["^KS11"]).dropna(subset=["^GSPC", "SPY", "QQQ"]).ffill()
    g = C["^GSPC"]
    # 🦴 변동성 맞춤(공격형) — 10/12 사용자 결정 · src/rules7.py VOL_ROLES["conc"] · 2026-10-13부터(소급 없음)
    sys.path.insert(0, str(ROOT))
    from src.rules7 import VOL_FROM, VOL_ROLES, held_scale_line
    VP = VOL_ROLES["conc"]
    VL, HS = held_scale_line(C["SPY"], C["QQQ"], VP)
    act = lambda d: (d + pd.offsets.BDay(1)).strftime("%Y-%m-%d") >= VOL_FROM      # 그날 종가 판단이 쓰일 다음 거래일이 시작일 이후인가
    sc_at = lambda d: (float(HS[HS.index <= d].iloc[-1]) if act(d) and len(HS[HS.index <= d]) else 1.0)

    # 🧭 10/28 Q10/28-1: 현금 몫 → 자산 추세 칸 (src/trend_park.py · PARK_FROM 부터 · 소급 없음)
    from src import trend_park as TP
    TNAV, T_OPEN, T_IDLE = TP.trend_nav(START)
    C["TRD"] = TNAV.reindex(C.index, method="ffill") if TNAV is not None else 1.0
    pk = lambda d: TNAV is not None and (d + pd.offsets.BDay(1)).strftime("%Y-%m-%d") >= TP.PARK_FROM

    # 🔄 10/28 Q10/28-3: 연기금 월말 리밸런싱 앞지르기 — 💼 와 같은 규칙(src/month_flow.py) · FLOW_FROM 부터 · 소급 없음
    #   근거 market/lab/k1028_qflow.json conc.C1_vs_C0(🎯 2017~ 연 +2.34%p·낙폭 −21.4→−19.4 · 흔들기 8/8 플러스)
    from src import month_flow as MF
    for _c in ("IEF", "TLT"):
        if _c in C:
            C[_c] = C[_c].ffill().bfill()
    CALL = list(C.index)
    _MFS = {}

    def nday(d):
        """d 다음 미국 거래일(지난 날은 실제 달력, 앞날은 휴장일 규칙)"""
        i = C.index.get_loc(d)
        if i + 1 < len(C.index):
            return C.index[i + 1]
        x = d + pd.Timedelta(days=1)
        while not MF._is_td(x.date()):
            x += pd.Timedelta(days=1)
        return x

    def fl(d):
        """d 종가 판단 → 다음 거래일에 쓸 (sig, drift, 남은 거래일)"""
        d1 = nday(d); k = d1.strftime("%Y-%m-%d")
        if k not in _MFS:
            try:
                _MFS[k] = MF.state(C, CALL, d1) if "IEF" in C and "TLT" in C else (0, None, 99)
            except Exception as e_:
                print("🔄 월말 흐름 계산 실패", e_)
                _MFS[k] = (0, None, 99)
        return _MFS[k]

    def tw(up_, sc, park=False, fsig=0):
        b_ = ON if up_ else OFF
        w_ = {"SPY": b_["SPY"] * sc, "QQQ": b_["QQQ"] * sc}
        w_["BIL"] = 1 - w_["SPY"] - w_["QQQ"]
        if park:
            w_["TRD"], w_["BIL"] = w_["BIL"], 0.0
        if fsig:
            w_ = MF.apply(w_, fsig, lambda k: k in ("SPY", "QQQ"), lambda k: k in ("BIL", "TRD"))
            w_["TLT"] = w_.pop(MF.NAME, 0.0)
        return w_
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
    A3 = ("SPY", "QQQ", "BIL", "TRD") + (("TLT",) if "TLT" in C else ())
    R = C[list(A3)].pct_change().fillna(0.0)
    p0 = C.index[C.index.get_loc(cal[0]) - 1]
    last_up = bool(reg.loc[p0])
    last_sc = sc_at(p0)
    last_pk = pk(p0)
    last_fs = fl(p0)[0]
    w = tw(last_up, last_sc, last_pk, last_fs)
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
        sc_now = sc_at(d)
        pk_now = pk(d)
        fs_now = fl(d)[0]
        if up_now != last_up or d.isocalendar()[1] != wk or sc_now != last_sc or pk_now != last_pk or fs_now != last_fs:
            nt = tw(up_now, sc_now, pk_now, fs_now)
            t_ = sum(abs(nt.get(t, 0) - w.get(t, 0)) for t in A3)
            turn += t_; val *= 1 - t_ * COST; w = dict(nt)
            if up_now != last_up:
                events.append({"d": d.strftime("%Y-%m-%d"), "k": "판정 바뀜", "up": up_now})
            if sc_now != last_sc:
                events.append({"d": d.strftime("%Y-%m-%d"), "k": f"🦴 변동성 맞춤 주식 {round(last_sc * 100)}→{round(sc_now * 100)}%", "up": up_now})
            if pk_now != last_pk:
                events.append({"d": d.strftime("%Y-%m-%d"), "k": "🧭 현금 몫 → 자산 추세 칸 (Q10/28-1)", "up": up_now})
            if fs_now != last_fs:
                events.append({"d": d.strftime("%Y-%m-%d"), "k": "🔄 월말 흐름 " + ("주식 60% → 장기채" if fs_now > 0 else "추세·현금 60% → 주식" if fs_now < 0 else "끝 · 제자리로") + " (Q10/28-3)", "up": up_now})
            wk, last_up, last_sc, last_pk, last_fs = d.isocalendar()[1], up_now, sc_now, pk_now, fs_now
    spy = [round((float(C.loc[d, "SPY"]) / float(C.loc[p0, "SPY"]) - 1) * 100, 2) for d in cal]
    qqq = [round((float(C.loc[d, "QQQ"]) / float(C.loc[p0, "QQQ"]) - 1) * 100, 2) for d in cal]

    up = bool(reg.iloc[-1])
    sc_last = sc_at(C.index[-1])
    fst = fl(C.index[-1])
    tgt = {t: x for t, x in tw(up, sc_last, pk(C.index[-1]), fst[0]).items() if x > 0.004}
    if "TLT" in C:
        INFO["TLT"] = {"name": MF.NAME, "flow": True,
                       "items": [{"t": "TLT", "w": 1.0, "name": "미국 장기채", "px": round(float(C["TLT"].iloc[-1]), 2)}]}
    INFO["TRD"] = {"name": TP.NAME, "trend": True,
                   "items": [{"t": o["sym"], "w": o["w"], "name": o.get("name"), "px": o.get("now")} for o in T_OPEN] +
                            ([{"t": "SGOV", "w": round(T_IDLE, 4), "name": TP.TNAME["SGOV"], "px": TP.LAST_PX.get("SGOV")}] if T_IDLE > 0.005 else [])}
    vnow = float(VL.iloc[-1])
    vol_rule = {"on": True, "active": act(C.index[-1]), "role": VP["role"], "lb": VP["lb"], "vol20": round(vnow * 100, 1), "target": VP["target"],
                "floor": round(VP["floor"] * 100), "eq_scale": round(sc_last * 100), "eq_w": round((tgt.get("SPY", 0) + tgt.get("QQQ", 0)) * 100, 1),
                "raw_scale": round(min(1.0, max(VP["floor"], VP["target"] / 100 / vnow)) * 100), "band": 5, "from": VOL_FROM,
                "asof": C.index[-1].strftime("%Y-%m-%d"),
                "note": f"주식 × min(1, 목표 {VP['target']}% ÷ S&P½+나스닥½ {VP['lb']}일 변동성), 아래 한도 {round(VP['floor'] * 100)}% · 5%p 넘게 바뀔 때만 · 덜어낸 만큼 현금 · 레버리지 없음"}
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
                 "vol": f"🦴 변동성 맞춤(공격형, {VOL_FROM}부터): 주식 × min(1, {VP['target']}% ÷ {VP['lb']}일 변동성) · 아래 한도 {round(VP['floor'] * 100)}% → 덜어낸 만큼 " + ("🧭 자산 추세 칸" if pk(C.index[-1]) else "현금") + f" (현금 몫은 {TP.PARK_FROM}부터 🧭 자산 추세 9종 칸)",
                 "flow": f"🔄 월말 흐름({MF.FLOW_FROM}부터 · Q10/28-3): 매달 마지막 {MF.K}거래일, 60/40 펀드(S&P·중기채) 주식 비중이 ±{MF.TH * 100:.1f}%p 넘게 쏠리면 넘침 → 주식 칸 {round(MF.F * 100)}% 미국 장기채(TLT) · 모자람 → 추세·현금 칸 {round(MF.F * 100)}% 주식",
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
        "turn": round(turn * 100), "events": events[::-1][:10], "bt": bt, "vol_rule": vol_rule,
        "trend_park": {"on": pk(C.index[-1]), "from": TP.PARK_FROM, "rule": f"{TP.NIN}/{TP.NOUT}|{TP.WMODE}", "open": T_OPEN, "idle": round(T_IDLE, 3), "ok": TNAV is not None},
        "month_flow": {"on": True, "from": MF.FLOW_FROM, "sig": fst[0], "drift": round(fst[1] * 100, 2) if fst[1] is not None else None,
                       "left": fst[2], "window": fst[2] < MF.K, "k": MF.K, "th": MF.TH * 100, "f": MF.F,
                       "pct": round(tgt.get("TLT", 0.0) * 100, 1), "for": nday(C.index[-1]).strftime("%Y-%m-%d"),
                       "note": "Q10/28-3 — 💼 와 같은 월말 흐름 규칙을 🎯 에도 · 근거 market/lab/k1028_qflow.json(🎯 2017~ 연 +2.34%p) · 레버리지 없음"},
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
