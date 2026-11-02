"""📈 11/2 12시 ② — 📊 실적 갭 대용(킥 #7·#19~21 에서 「가장 단단한 신호」)도 「그날 구성 종목」으로 다시 재기
결과 → market/lab/k1102_pitgap.json
사건(10/24 k1024_pead 와 같은 정의): 시가 갭 ≥5% · 시가 > 전일 고가 · 거래량 ≥ 50일 평균 2배 · 종가 > 60일 고가 · 분기 끝 +8~55일 · 유동성
진입 g+1 종가(정직) · 출구 KI.kexit · 왕복 0.5% · 초과 = S&P500 대비. 표본 TODAY/PIT/PRE/PIT_GONE (k1102_pit 와 같음). 손잡이 갭 4·6% · 거래 1.6·2.4배.
생존 편향: 상장폐지 종목은 yfinance 에 없어 PIT 도 아직 위로 치우침.
"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "lab"))
import accum_bt as AB          # noqa: E402
import kick_ideas_bt as KI     # noqa: E402
import k1102_pit as P          # noqa: E402

AB.START = "2006-06-01"
AB.TIME_BUDGET = 30 * 60
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1102_pitgap.json"


def build(data, idx, iv, gth, vth):
    cost = AB.COST.get("US", AB.DEF_COST)
    _, minp, minvol = AB.MKT["US"]
    rows = []
    for t, d in data.items():
        if len(d) < 320:
            continue
        F = KI.feats(d, minp, minvol)
        c = F["c"]
        n = len(c)
        dates = d.index
        season = np.array([8 <= KI.dq_of(x) <= 55 for x in dates])
        ev = F["liq"] & (np.nan_to_num(F["gap"]) >= gth) & (F["o"] > F["ph"]) & (np.nan_to_num(F["vr"]) >= vth) & (c > F["hi60"]) & season
        ixa = idx.reindex(dates).ffill().to_numpy(float)
        tiv = iv.get(t, [])
        for g in np.where(ev & (np.arange(n) >= 262))[0]:
            e = g + 1
            if e >= n - 1:
                continue
            res = KI.kexit(c, F["ma20"], e)
            if res is None:
                continue
            r, ex = res
            if not (ixa[e] > 0 and ixa[ex] > 0):
                continue
            gd = dates[g]
            inn = any(a <= gd < b for a, b in tiv)
            rr = r - cost
            rows.append(dict(tk=t, date=str(gd.date()), ti=int(g), e=str(dates[e].date()), xd=str(dates[ex].date()),
                             r=round(rr * 100, 2), x=round((rr - (ixa[ex] / ixa[e] - 1)) * 100, 2), vr=float(F["vr"][g]), pit=inn))
    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    res = {"made": dt.datetime.now(KST).strftime("%F %H:%M"), "rule": __doc__, "log": {}}
    log = res["log"]
    try:
        snaps = P.members()
        iv, adds, today = P.intervals(snaps)
        ever = sorted(set(iv) | today)
        idx = AB.idx_series("^GSPC")
        data = AB.download(ever, log, time.time())
        log["n_dl"] = len(data)
        for name, gth, vth in (("base", 0.05, 2.0), ("g4", 0.04, 2.0), ("g6", 0.06, 2.0), ("v16", 0.05, 1.6), ("v24", 0.05, 2.4)):
            ev = AB.dedupe(build(data, idx, iv, gth, vth)).reset_index(drop=True)
            ev["today"] = ev["tk"].isin(today)
            S = {"TODAY": ev[ev["today"]], "PIT": ev[ev["pit"]], "PRE": ev[ev["today"] & ~ev["pit"]], "PIT_GONE": ev[ev["pit"] & ~ev["today"]]}
            res[name] = {k: P.pstats(v) for k, v in S.items()}
            print(name, {k: (v["IS"].get("n"), v["IS"].get("avg"), v["IS"].get("pf"), v["OOS"].get("n"), v["OOS"].get("avg"), v["OOS"].get("pf"),
                             v["IS"]["sleeve_yr"], v["OOS"]["sleeve_yr"]) for k, v in res[name].items()}, flush=True)
    except Exception:
        import traceback
        res["err"] = traceback.format_exc()[-1500:]
        print(res["err"], flush=True)
    res["sec"] = round(time.time() - t0)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", res["sec"])


if __name__ == "__main__":
    main()
