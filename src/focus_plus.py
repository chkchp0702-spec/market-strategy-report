"""🎯 오늘의 집중 강화 (10/7 사용자 "이쪽에 더 집중")
  ① 돈의 흐름 선: 테마 ETF 가 S&P 대비 20일 동안 어떻게 벌어졌나 + 거래대금(5일/60일) → 「들어오는 중」
  ② 테마 단계: 초입(모아가기) → 주도(눌림 매수) → 과열(추격 금지·일부 정리) → 꺾임(끝났나?)
  ③ 미국 → 한국 전염 시차: 미국 테마 ETF 가 뛴 뒤 한국 연결 종목이 며칠 뒤 따라오나(상관이 가장 큰 날)
  ④ 종목별 매수 자리: 컵 기준가 · 갭 시가 · 20일선 중 하나 + 지금 몇 % 위/아래
  ⑥ 수급: 한국 연결 종목 외국인·기관 5일 순매수(네이버), 미국 ETF 는 거래대금 배수
  ⑦ 주간 회고 재료: 고를 때의 단계를 장부에 남겨, 졌을 때 이유를 자동으로 붙인다
"""
from __future__ import annotations
import csv
import io
import re
import sys
import urllib.request

CUP = "https://raw.githubusercontent.com/chkchp0702-spec/Cup/main/results/list1_cup.csv"
GAP = "https://raw.githubusercontent.com/chkchp0702-spec/Gap/main/results/list1_gap.csv"
DEBUG: list[str] = []


def _get(url, t=25, enc="utf-8", ref=None):
    h = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    if ref:
        h["Referer"] = ref
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t) as r:
        return r.read().decode(enc, "ignore")


def _f(v):
    try:
        x = float(str(v).replace(",", ""))
        return None if x != x else x
    except Exception:
        return None


def scanner_levels():
    """컵 매수기준가 · 갭 시가 (코드 → {k, lv, d})"""
    out = {}
    for url, kind in ((GAP, "gap"), (CUP, "cup")):          # 컵이 나중 → 겹치면 컵 우선
        try:
            for r in csv.DictReader(io.StringIO(_get(url).lstrip("﻿"))):
                c = r.get("코드")
                if kind == "cup" and _f(r.get("매수기준가")):
                    out[c] = {"k": "컵 기준가", "lv": _f(r["매수기준가"]), "d": _f(r.get("기준가까지%"))}
                elif kind == "gap" and _f(r.get("갭시가")):
                    out[c] = {"k": "갭 시가", "lv": _f(r["갭시가"]), "d": _f(r.get("갭시가대비%"))}
        except Exception as e:
            DEBUG.append(f"{kind} 목록 실패 {str(e)[:60]}")
    return out


def history(tickers, period="6mo"):
    H = {}
    try:
        import yfinance as yf
        import pandas as pd
        df = yf.download(sorted(set(tickers)), period=period, interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
        for t in set(tickers):
            try:
                sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                s = sub[["Close", "Volume"]].dropna(subset=["Close"])
                if len(s) > 25:
                    H[t] = s
            except Exception:
                pass
    except Exception as e:
        DEBUG.append(f"시세 실패 {str(e)[:80]}")
    return H


def supply_kr(code):
    """네이버 외국인·기관 일별 순매매량 → 5일 합(주)"""
    c6 = code.split(".")[0]
    try:
        x = _get(f"https://finance.naver.com/item/frgn.naver?code={c6}", enc="euc-kr", ref="https://finance.naver.com/")
        rows = re.findall(r'<tr[^>]*onMouseOver[^>]*>(.*?)</tr>', x, re.S)
        org = frg = 0
        n = 0
        for tr in rows:
            tds = [re.sub(r"<[^>]+>|\s|&nbsp;", "", t) for t in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) >= 7 and re.match(r"\d{4}\.\d{2}\.\d{2}", tds[0]):
                o, f = _f(tds[5]), _f(tds[6])
                if o is None or f is None:
                    continue
                org += o
                frg += f
                n += 1
                if n == 5:
                    break
        if n >= 3:
            return {"frg": int(frg), "org": int(org), "n": n}
        DEBUG.append(f"수급 표 없음 {c6}")
    except Exception as e:
        DEBUG.append(f"수급 실패 {c6} {str(e)[:50]}")
    return None


def _ret(s):
    v = list(s.values)
    return [v[i] / v[i - 1] - 1 for i in range(1, len(v))]


def lag_of(etf, kr_list, H):
    """미국 ETF 하루 수익률 → 한국 연결 종목(같은 비중 묶음)이 k 거래일 뒤 따라오는 정도(상관)"""
    import pandas as pd
    if etf not in H:
        return None
    kr = [H[k]["Close"] for k in kr_list if k in H]
    if len(kr) < 2:
        return None
    us = H[etf]["Close"].pct_change().dropna()
    basket = pd.concat([s.pct_change() for s in kr], axis=1).mean(axis=1).dropna()
    kd = list(basket.index)
    best = None
    for k in (1, 2, 3):
        xs, ys = [], []
        for d, v in us.iloc[-80:].items():
            later = [x for x in kd if x > d]
            if len(later) >= k:
                xs.append(v)
                ys.append(basket[later[k - 1]])
        if len(xs) >= 25:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
            vx = sum((a - mx) ** 2 for a in xs)
            vy = sum((b - my) ** 2 for b in ys)
            if vx > 0 and vy > 0:
                cor = cov / (vx * vy) ** .5
                beta = cov / vx
                if best is None or cor > best["cor"]:
                    best = {"k": k, "cor": round(cor, 2), "beta": round(beta, 2), "n": len(xs)}
    return best


def stage_of(t, members):
    last, m5, m20 = t.get("last"), t.get("ma5"), t.get("ma20")
    d20 = (last / m20 - 1) * 100 if last and m20 else 0
    hot = sum(1 for x in members if (x.get("r1") or 0) >= 8)
    hot_r = hot / max(1, len(members))
    st = t.get("streak") or 0
    if (m20 and last < m20) or ((t.get("r5") or 0) < 0 and m5 and last < m5):
        return {"s": "꺾임", "do": "끝났나? — 새로 사지 않고, 들고 있으면 20일선 기준으로 정리", "c": "b"}
    if d20 > 10 or (t.get("r5") or 0) > 12 or hot_r >= .4:
        return {"s": "과열", "do": "추격 금지 · 일부 정리 — 5일선까지 눌릴 때를 기다림", "c": "r"}
    if 2 <= st <= 5 and d20 < 6:
        return {"s": "초입", "do": "모아가기 — 나눠서 조금씩, 20일선이 손절선", "c": "g"}
    return {"s": "주도", "do": "눌림 매수 — 5일선 근처로 쉬는 날 담기", "c": "o"}


def enrich(themes, spy_sym="SPY"):
    """focus.json 의 themes 에 flow·stage·lag·자리·수급을 붙인다"""
    lv = scanner_levels()
    tick = [spy_sym]
    for t in themes:
        tick.append(t["sym"])
        tick += [x["t"] for x in t["us"] + t["kr"]]
        tick += t.get("_kr_all", [])
    H = history(tick)
    for t in themes:
        sym = t["sym"]
        # ① 흐름 선
        if sym in H and spy_sym in H:
            a, b = H[sym]["Close"], H[spy_sym]["Close"]
            j = a.index.intersection(b.index)
            a, b = a.loc[j], b.loc[j]
            if len(a) > 21:
                base = a.iloc[-21] / b.iloc[-21]
                line = [round((a.iloc[i] / b.iloc[i] / base - 1) * 100, 2) for i in range(len(a) - 21, len(a))]
                dv = (H[sym]["Close"] * H[sym]["Volume"])
                r5 = float(dv.iloc[-5:].mean()) / max(1.0, float(dv.iloc[-60:].mean()))
                up5 = line[-1] - line[-6] if len(line) > 6 else 0
                t["flow"] = {"rs": line, "dv": round(r5, 2), "up5": round(up5, 2),
                             "lab": "들어오는 중" if up5 > 1 and r5 >= 1.1 else ("들어오는 중(거래 조용)" if up5 > 1 else ("빠지는 중" if up5 < -1 else "멈춤"))}
        # ② 단계
        t["stage"] = stage_of(t, t["us"] + t["kr"])
        # ③ 시차
        lg = lag_of(sym, t.get("_kr_all", []), H)
        if lg:
            r1 = t.get("r1") or 0
            t["lag"] = {**lg, "txt": f"미국 {sym}이(가) 움직이면 한국 연결주는 보통 D+{lg['k']}에 따라와요 (상관 {lg['cor']:.2f})",
                        "today": (f"어젯밤 {sym} {r1:+.1f}% → 오늘 한국 연결주 예상 {r1 * lg['beta']:+.1f}% 안팎" if abs(r1) >= 1 and lg["cor"] >= .2 else "")}
        # ④ 자리 · ⑥ 수급
        for x in t["us"] + t["kr"]:
            p = lv.get(x["t"])
            if not p and x["t"] in H:
                s = H[x["t"]]["Close"]
                m20 = float(s.iloc[-20:].mean())
                p = {"k": "20일선", "lv": round(m20, 2), "d": round((float(s.iloc[-1]) / m20 - 1) * 100, 2)}
            if p:
                x["pos"] = p
            if x["t"] in H:
                s = H[x["t"]]["Close"]
                x["ma5"] = round(float(s.iloc[-5:].mean()), 2)
                x["ma20"] = round(float(s.iloc[-20:].mean()), 2)
                x["last"] = round(float(s.iloc[-1]), 2)
        for x in t["kr"]:
            sp = supply_kr(x["t"])
            if sp:
                x["sup"] = sp
        ks = [x["sup"] for x in t["kr"] if x.get("sup")]
        if ks:
            t["supply"] = {"frg": sum(k["frg"] for k in ks), "org": sum(k["org"] for k in ks), "n": len(ks)}
        t.pop("_kr_all", None)
    return themes


def lesson(e):
    """진 날 이유 한 줄 (고를 때 단계·그 뒤 흐름)"""
    if e.get("ex") is None or e["ex"] > 0:
        return ""
    s = e.get("stage")
    if s == "과열":
        return "과열 단계에서 골랐음 → 과열이면 집중에서 빼거나 '눌림 대기'로"
    if s == "꺾임":
        return "이미 꺾인 테마였음 → 20일선 아래 테마는 고르지 않기"
    if (e.get("res") or 0) < 0 and (e.get("spy_res") or 0) > 0:
        return "시장은 올랐는데 테마만 빠짐 → 주도가 바뀐 신호, 다음 날 순위 변화 먼저 확인"
    return "시장과 같이 빠짐 → 테마보다 시장 전체 위험이 컸음"
