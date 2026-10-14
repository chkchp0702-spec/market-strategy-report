"""📈 Q14-3 🎈 「테마 ETF가 쏟아지면 그 테마는 꼭대기」 — 과거 검증 (사용자 10/14 14시 보고에 답: "3번 진행")
결과 → market/lab/k1014_q14.json · 판정 기준은 결과 보기 전에 여기 적음.

자료: 테마마다 같은 테마 미국 상장 ETF 묶음(레버리지·인버스 제외, 손으로 적은 목록) → 야후 가격 첫 날 = 상장일 대용.
  ⚠ 상장폐지된 ETF 는 야후에 없음 → 붐 때 나왔다 사라진 ETF(가장 「붐」다운 것)가 빠져 신호가 약하게 잡힘(보수적 쪽 편향).
  ⚠ 한국 KRX 신규상장은 과거 자료가 없어 이번엔 미국만.
붐 신호(월말): 지난 W개월 새 상장 수 n ≥ max(m, k × 그 전 36개월의 W개월당 평균).
  고정안(보고서 그대로): W=6 · k=2 · m=2.
  고르기(2008-07~2016, 아래 (가) 의 붐−보통 12개월 초과 차이가 가장 음수인 안): W∈{6,12} × k∈{1.5,2,3} × m∈{2,3}.
검증 두 판:
 (가) 테마-달 표: 월말마다 대표 ETF 의 다음 6·12개월 수익 − SPY. 붐 vs 보통 평균 · 서로 다른 붐 「사건」 수(연속 붐 달은 하나).
 (나) 🎯 집중 대용: 레이더 테마 대표 ETF 로 focus.py 점수(rs5 + 0.5·rs20 + 연속강세·0.3 + 1, r5·r20>0)
      매주(5거래일) 상위 2개(같은 계열 하나만)를 5거래일 들고 S&P 대비. 규칙 = 붐 테마는 몫 절반(나머지 SPY).
      다음 거래일 종가 진입 · 바꿀 때 회전×0.1%.
판정: ✅ = 고른 안이 시험 기간(2017~) (가) 12개월 붐−보통 ≤ −3%p 이고 붐 사건 ≥ 8
            + (나) 규칙이 시험 기간 S&P 대비 연초과·샤프 모두 기준 이상 + 고정안도 (가) 시험 기간 방향 같음
       🧪 = (가) 시험 기간 방향은 맞지만(붐 < 보통) 위 조건 일부 못 미침 · ❌ = 시험 기간 붐 ≥ 보통
"""
import json, sys, math, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from src.conc_bt import START, IS_END, OOS_START, stats   # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "market" / "lab" / "k1014_q14.json"
COST = 0.001
res = {"made": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")}

# 테마 → (대표 ETF, 계열, 레이더에 있나, 같은 테마 ETF 묶음)
THEMES = {
    "소프트웨어·클라우드": ("IGV", "tech", True, "IGV XSW SKYY WCLD CLOU PSJ FDN ARKW IGPT".split()),
    "반도체": ("SMH", "tech", True, "SMH SOXX XSD PSI FTXL SOXQ SHOC CHPS SMHX DRAM".split()),
    "사이버보안": ("CIBR", "tech", True, "HACK CIBR BUG IHAK WCBR".split()),
    "로봇·AI": ("BOTZ", "tech", True, "BOTZ ROBO ARKQ AIQ THNQ ROBT CHAT IGPT LOUP".split()),
    "인터넷": ("IGM", "tech", True, "FDN IGM PNQI ARKW ONLN IBUY XWEB".split()),
    "바이오": ("XBI", "health", True, "XBI IBB FBT BBH PBE SBIO BBP ARKG GNOM IDNA BBC".split()),
    "의료기기": ("IHI", "health", True, "IHI XHE".split()),
    "은행": ("KBE", "fin", True, "KRE KBE QABA FTXO KBWB KBWR IAT".split()),
    "증권·거래소": ("IAI", "fin", True, "IAI KCE".split()),
    "주택건설": ("ITB", "cyc", True, "ITB XHB HOMZ".split()),
    "소매": ("XRT", "cyc", True, "XRT RTH IBUY ONLN".split()),
    "운송": ("IYT", "cyc", True, "IYT XTN JETS".split()),
    "방산·우주": ("ITA", "ind", True, "ITA XAR PPA SHLD UFO ARKX ROKT".split()),
    "인프라·전력망": ("PAVE", "ind", True, "PAVE IFRA GRID NFRA PKB".split()),
    "원전·우라늄": ("URA", "energy", True, "NLR URA URNM NUKZ URNJ".split()),
    "태양광·클린에너지": ("TAN", "energy", True, "TAN ICLN QCLN PBW ACES CNRG PBD SMOG CTEC FAN".split()),
    "2차전지·전기차": ("LIT", "mat", True, "LIT BATT DRIV KARS IDRV HAIL".split()),
    "금속·광산": ("XME", "mat", True, "XME PICK COPX CPER ICOP REMX".split()),
    "금광": ("GDX", "mat", True, "GDX GDXJ RING SGDM GOAU SGDJ".split()),
    "석유": ("XOP", "energy", True, "XOP IEO PXE FCG CRAK".split()),
    "비트코인·블록체인": ("BITO", "crypto", True, "GBTC BITO BITQ BLOK BLCN LEGR IBIT FBTC ARKB BITB HODL BRRR BTCO EZBC BTCW DEFI".split()),
    "혁신 성장": ("ARKK", "tech", True, "ARKK ARKW ARKF ARKG ARKQ".split()),
    # 레이더 밖이지만 붐 사례가 뚜렷한 테마 — (가) 표본 늘리기용
    "대마초": ("MJ", "x_cann", False, "MJ YOLO THCX MSOS CNBS POTX".split()),
    "게임·e스포츠": ("ESPO", "x_game", False, "ESPO NERD GAMR HERO BJK".split()),
    "핀테크": ("FINX", "x_fin", False, "FINX ARKF TPAY IPAY".split()),
    "3D 프린팅": ("PRNT", "x_3d", False, "PRNT ARKQ".split()),
    "희토류·전략광물": ("REMX", "x_rare", False, "REMX".split()),
}


def load():
    import yfinance as yf
    syms = sorted({s for v in THEMES.values() for s in v[3]} | {v[0] for v in THEMES.values()} | {"SPY"})
    df = yf.download(syms, period="max", auto_adjust=True, progress=False, threads=True)["Close"]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def launches(C):
    first = {}
    for s in C.columns:
        v = C[s].dropna()
        if len(v):
            first[s] = v.index[0]
    res["launch"] = {s: d.strftime("%Y-%m-%d") for s, d in sorted(first.items(), key=lambda x: x[1])}
    res["missing"] = sorted({s for v in THEMES.values() for s in v[3]} - set(first))
    return first


def boom_flags(first, months, W, k, m):
    out = {}
    for th, (_, _, _, lst) in THEMES.items():
        ds = sorted(first[s] for s in set(lst) if s in first)
        ser = []
        for me in months:
            n = sum(1 for d in ds if me - pd.DateOffset(months=W) < d <= me)
            past = sum(1 for d in ds if me - pd.DateOffset(months=W + 36) < d <= me - pd.DateOffset(months=W))
            base = past / 36 * W
            ser.append(n >= max(m, k * base))
        out[th] = pd.Series(ser, index=months)
    return out


def panel(C, flags, months):
    spy = C["SPY"]
    rows = []
    for th, (rep, _, _, _) in THEMES.items():
        if rep not in C:
            continue
        p = C[rep].dropna()
        if len(p) < 300:
            continue
        for me in months:
            if me < p.index[0] + pd.Timedelta(days=60):
                continue
            i = p.index.searchsorted(me, side="right") - 1
            if i < 0:
                continue
            d0 = p.index[i]
            r = {"th": th, "d": me, "boom": bool(flags[th].get(me, False))}
            for h in (6, 12):
                d1 = d0 + pd.DateOffset(months=h)
                if d1 > p.index[-1]:
                    continue
                j = p.index.searchsorted(d1)
                if j >= len(p):
                    continue
                s0, s1 = spy.asof(d0), spy.asof(p.index[j])
                r[f"x{h}"] = (p.iloc[j] / p.iloc[i] - 1) - (s1 / s0 - 1)
            rows.append(r)
    return pd.DataFrame(rows)


def summ_panel(P, lo, hi):
    g = P[(P.d >= lo) & (P.d <= hi)]
    o = {}
    for h in (6, 12):
        c = f"x{h}"
        if c not in g:
            continue
        b, n = g[g.boom][c].dropna(), g[~g.boom][c].dropna()
        o[f"boom{h}"] = round(b.mean() * 100, 2) if len(b) else None
        o[f"norm{h}"] = round(n.mean() * 100, 2) if len(n) else None
        o[f"diff{h}"] = round((b.mean() - n.mean()) * 100, 2) if len(b) and len(n) else None
        o[f"boom{h}_win"] = round(float((b > 0).mean()) * 100) if len(b) else None
    o["n_boom_months"] = int(g.boom.sum())
    ev = 0
    for th, gg in g.sort_values("d").groupby("th"):
        f = gg.boom.values
        ev += int(f[0]) + int(((f[1:]) & (~f[:-1])).sum()) if len(f) else 0
    o["n_events"] = ev
    o["themes_boom"] = sorted(g[g.boom].th.unique().tolist())
    return o


def focus_sim(C, first, W, k, m):
    radar = {th: v for th, v in THEMES.items() if v[2] and v[0] in C}
    reps = [v[0] for v in radar.values()]
    px = C[reps + ["SPY"]].loc["2007-01-01":].ffill()
    spy = px["SPY"]
    r1 = px.pct_change()
    r5, r20 = px.pct_change(5), px.pct_change(20)
    beat = (r1.sub(r1["SPY"], axis=0) > 0)
    st = pd.DataFrame(0, index=px.index, columns=reps)
    for s in reps:
        b = beat[s].values
        cnt, out = 0, []
        for x in b:
            cnt = cnt + 1 if x else 0
            out.append(cnt)
        st[s] = out
    months = pd.date_range("2004-12-31", px.index[-1], freq="ME")
    fl = boom_flags(first, months, W, k, m)
    rep2th = {v[0]: th for th, v in radar.items()}
    fam = {v[0]: v[1] for v in radar.values()}
    idx = px.loc[START:].index
    w_base, w_rule = pd.DataFrame(0.0, index=idx, columns=reps + ["SPY"]), None
    w_rule = w_base.copy()
    picks_log = []
    cur_b, cur_r = None, None
    for t, d in enumerate(idx):
        if t % 5 == 0:
            cand = []
            for s in reps:
                if pd.isna(px.at[d, s]) or px[s].loc[:d].dropna().shape[0] < 30:
                    continue
                a5, a20 = r5.at[d, s], r20.at[d, s]
                if not (a5 > 0 and a20 > 0):
                    continue
                sc = (a5 - r5.at[d, "SPY"]) * 100 + (a20 - r20.at[d, "SPY"]) * 50 + min(st.at[d, s], 10) * 0.3 + 1
                cand.append((sc, s))
            cand.sort(reverse=True)
            pk, fs = [], set()
            for sc, s in cand:
                if fam[s] in fs:
                    continue
                pk.append(s); fs.add(fam[s])
                if len(pk) == 2:
                    break
            me = months[months.searchsorted(d, side="right") - 1]
            booms = {s: bool(fl[rep2th[s]].get(me, False)) for s in pk}
            wb = {s: 1 / len(pk) for s in pk} if pk else {"SPY": 1.0}
            wr = {}
            for s in pk:
                wr[s] = (0.5 if booms[s] else 1.0) / len(pk)
            if pk:
                wr["SPY"] = 1 - sum(wr.values())
            else:
                wr = {"SPY": 1.0}
            cur_b, cur_r = wb, wr
            for s in pk:
                i = px.index.get_loc(d)
                f5 = px[s].iloc[min(i + 6, len(px) - 1)] / px[s].iloc[min(i + 1, len(px) - 1)] - 1 - (spy.iloc[min(i + 6, len(px) - 1)] / spy.iloc[min(i + 1, len(px) - 1)] - 1)
                f20 = px[s].iloc[min(i + 21, len(px) - 1)] / px[s].iloc[min(i + 1, len(px) - 1)] - 1 - (spy.iloc[min(i + 21, len(px) - 1)] / spy.iloc[min(i + 1, len(px) - 1)] - 1)
                picks_log.append({"d": d, "s": s, "boom": booms[s], "x5": f5, "x20": f20})
        for s, v in cur_b.items():
            w_base.at[d, s] = v
        for s, v in cur_r.items():
            w_rule.at[d, s] = v
    rr = r1.loc[idx].fillna(0)

    def nav(W_):
        Wl = W_.shift(2).fillna(0)          # 신호일 다음 거래일 종가 진입 → 그다음 날부터 수익
        Wl.iloc[:2, Wl.columns.get_loc("SPY")] = 1.0
        turn = Wl.diff().abs().sum(axis=1).fillna(0)
        ret = (Wl * rr).sum(axis=1) - turn * COST
        return (1 + ret).cumprod()
    return nav(w_base), nav(w_rule), spy.loc[idx], pd.DataFrame(picks_log)


def main():
    C = load()
    first = launches(C)
    months = pd.date_range("2005-01-31", C.index[-1], freq="ME")
    grid = {}
    for W in (6, 12):
        for k in (1.5, 2, 3):
            for m in (2, 3):
                fl = boom_flags(first, months, W, k, m)
                P = panel(C, fl, months)
                grid[f"W{W}_k{k}_m{m}"] = {"is": summ_panel(P, pd.Timestamp(START), pd.Timestamp(IS_END)),
                                          "oos": summ_panel(P, pd.Timestamp(OOS_START), pd.Timestamp("2100-01-01"))}
    res["grid"] = grid
    ok = {kk: v for kk, v in grid.items() if v["is"].get("diff12") is not None and v["is"]["n_events"] >= 5}
    pick = min(ok, key=lambda kk: ok[kk]["is"]["diff12"]) if ok else "W6_k2_m2"
    res["pick"], res["fixed"] = pick, "W6_k2_m2"
    # 지금 붐 중인 테마 (고른 안·고정안)
    for tag, key in (("now_pick", pick), ("now_fixed", "W6_k2_m2")):
        W, k, m = key.split("_")
        fl = boom_flags(first, months, int(W[1:]), float(k[1:]), int(m[1:]))
        res[tag] = sorted(th for th, s in fl.items() if bool(s.iloc[-1]))
    # (나) 🎯 집중 대용
    fz = {}
    for key in dict.fromkeys([pick, "W6_k2_m2"]):
        W, k, m = key.split("_")
        nb, nr, spy, L = focus_sim(C, first, int(W[1:]), float(k[1:]), int(m[1:]))
        o = {}
        for per, lo, hi in (("is", START, IS_END), ("oos", OOS_START, None)):
            sl = slice(lo, hi)
            o[per] = {"base": stats(nb.loc[sl] / nb.loc[sl].iloc[0], spy.loc[sl]),
                      "rule": stats(nr.loc[sl] / nr.loc[sl].iloc[0], spy.loc[sl])}
            for kk in ("base", "rule"):
                o[per][kk].pop("yr", None)
            g = L[(L.d >= pd.Timestamp(lo)) & (L.d <= pd.Timestamp(hi or "2100-01-01"))]
            o[per]["picks"] = {"n": len(g), "n_boom": int(g.boom.sum()),
                               "boom_x5": round(g[g.boom].x5.mean() * 100, 2) if g.boom.any() else None,
                               "norm_x5": round(g[~g.boom].x5.mean() * 100, 2),
                               "boom_x20": round(g[g.boom].x20.mean() * 100, 2) if g.boom.any() else None,
                               "norm_x20": round(g[~g.boom].x20.mean() * 100, 2)}
        fz[key] = o
    res["focus"] = fz
    # 판정
    G = grid[pick]["oos"]; F = grid["W6_k2_m2"]["oos"]; Z = fz[pick]["oos"]
    a = (G.get("diff12") is not None and G["diff12"] <= -3 and G["n_events"] >= 8)
    b = (Z["rule"].get("ex", -99) >= Z["base"].get("ex", 99) and (Z["rule"].get("sharpe") or 0) >= (Z["base"].get("sharpe") or 0))
    c = (F.get("diff12") is not None and F["diff12"] < 0)
    if a and b and c:
        v = "✅"
    elif G.get("diff12") is not None and G["diff12"] < 0:
        v = "🧪"
    else:
        v = "❌"
    res["verdict"] = v
    res["checks"] = {"panel_oos": a, "focus_oos": b, "fixed_dir": c}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("판정", v, "고른 안", pick, json.dumps(grid[pick], ensure_ascii=False))
    print("집중", json.dumps(fz[pick]["oos"]["picks"], ensure_ascii=False), fz[pick]["oos"]["base"].get("ex"), fz[pick]["oos"]["rule"].get("ex"))
    print("지금 붐", res["now_pick"], res["now_fixed"])


if __name__ == "__main__":
    main()
