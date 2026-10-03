"""조건 발동 알림: market/latest.json 을 장부 조건과 대조해 걸리면 GitHub Issue 를 연다.

GitHub 앱이 Issue 알림을 휴대폰으로 보내 주므로 별도 서비스가 필요 없다.
같은 조건은 하루 한 번만 (alerts/state.json 으로 중복 방지).

사용: python -m src.alerts            # 검사 + 결과 JSON 출력
      python -m src.alerts --issue    # 발동 시 Issue 생성 (GITHUB_TOKEN, GITHUB_REPOSITORY 필요)
"""
from __future__ import annotations
import json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
STATE = ROOT / "alerts" / "state.json"


def _v(items: dict, key: str):
    it = items.get(key)
    return None if not it else it.get("value")


def _chg(items: dict, key: str):
    it = items.get(key)
    return None if not it else it.get("change_pct")


def _streak_positive(hist_csv: Path, col: str, n: int = 2) -> tuple[int, list]:
    """history.csv 의 col 이 양수인 연속 일수(최근부터)."""
    import csv
    if not hist_csv.exists():
        return 0, []
    rows = [r for r in csv.DictReader(hist_csv.open(encoding="utf-8")) if r.get(col)]
    rows.sort(key=lambda r: r["date"])
    streak, tail = 0, []
    for r in reversed(rows):
        v = float(r[col])
        tail.append((r["date"], v))
        if v > 0:
            streak += 1
        else:
            break
    return streak, tail[:n]


def check(latest: dict, led: dict) -> list[dict]:
    it = latest["items"]
    hits = []
    cond = {c["id"]: c for c in led["conditions"]}

    us10 = _v(it, "us10y")
    if us10 is not None and us10 >= 5.30:
        hits.append({"id": "us10y_530", "title": f"미 10년 금리 {us10:.2f}% — 5.30 선 위", "then": cond["us10y_530"]["then"],
                     "detail": f"출처 {it['us10y']['src']} · {it['us10y']['asof_kst']} (종가 기준인지 장중인지 확인)"})
    if us10 is not None and us10 <= 5.20:
        hits.append({"id": "us10y_520", "title": f"미 10년 금리 {us10:.2f}% — 5.20 아래", "then": "\"금리 혼자 오름\" 가설 점검",
                     "detail": f"출처 {it['us10y']['src']} · {it['us10y']['asof_kst']}"})
    brent = _v(it, "brent")
    if brent is not None and brent <= 95:
        hits.append({"id": "brent_95", "title": f"브렌트 {brent:.2f}$ — 95 아래", "then": cond["brent_95"]["then"],
                     "detail": f"{it['brent']['asof_kst']}"})
    kospi = _v(it, "kospi")
    if kospi is not None and kospi <= 6500:
        hits.append({"id": "kospi_stop", "title": f"코스피 {kospi:,.0f} — 6,500 손절선", "then": cond["kospi_stop"]["then"],
                     "detail": f"{it['kospi']['asof_kst']}"})
    mu, nq = _chg(it, "micron"), _v(it, "nasdaq")
    if mu is not None and mu <= -5 and nq is not None and nq <= 26500:
        hits.append({"id": "mu_drop", "title": f"마이크론 {mu:+.1f}% + 나스닥 {nq:,.0f}", "then": cond["mu_drop"]["then"], "detail": ""})
    kbe = _chg(it, "kbe")
    if kbe is not None and kbe <= -2:
        hits.append({"id": "bank_2d_1", "title": f"미 은행 ETF {kbe:+.1f}% (하루)", "then": f"이틀 연속이면 {cond['bank_2d']['then']}", "detail": "장부 bank_2d 카운트 확인"})
    streak, tail = _streak_positive(ROOT / "market" / "history.csv", "foreign_kospi", 2)
    krw = _v(it, "usdkrw")
    if streak >= 2:
        hits.append({"id": "foreign_return", "title": f"외국인 코스피 {streak}일 연속 순매수", "then": cond["foreign_return"]["then"],
                     "detail": " · ".join(f"{d} {v:+,.0f}억" for d, v in tail) + (f" · 달러/원 {krw}" if krw else "")})
    elif streak == 1:
        hits.append({"id": "foreign_1", "title": f"외국인 코스피 순매수 전환 (1일째 {tail[0][1]:+,.0f}억)", "then": "복귀 신호 1/2", "detail": ""})
    gold = _chg(it, "gold")
    us30 = _v(it, "us30y")
    if gold is not None and gold <= -2 and us30 is not None and us30 >= 5.5:
        hits.append({"id": "gold_test", "title": f"금 {gold:+.1f}% · 30년 {us30:.2f}%", "then": cond["gold_test"]["then"], "detail": "2주 하락 시험 중"})
    vix = _v(it, "vix")
    if vix is not None and vix >= 30:
        hits.append({"id": "vix_30", "title": f"VIX {vix:.1f} — 공포 구간", "then": "비중 바꾸기 전 하루 관찰", "detail": ""})
    return hits


def create_issue(hit: dict) -> str | None:
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (tok and repo):
        print("GITHUB_TOKEN/GITHUB_REPOSITORY 없음 — Issue 생략", file=sys.stderr)
        return None
    now = datetime.now(KST).strftime("%m/%d %H:%M")
    body = (f"**{hit['title']}**\n\n- 비중 규칙: {hit['then']}\n- {hit['detail']}\n- 확인 시각: {now} KST\n\n"
            "다음 리포트에서 장부 조건에 반영합니다. 장중 수치일 수 있으니 종가로 다시 확인하세요.\n\n_자동 알림 (src/alerts.py)_")
    data = json.dumps({"title": f"⚠️ 조건 발동 · {hit['title']} ({now})", "body": body, "labels": ["alert"]}).encode()
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues", data=data, method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json", "User-Agent": "report-bot"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["html_url"]


def main() -> int:
    issue = "--issue" in sys.argv
    latest = json.loads((ROOT / "market" / "latest.json").read_text(encoding="utf-8"))
    led = json.loads((ROOT / "ledger" / "ledger.json").read_text(encoding="utf-8"))
    hits = check(latest, led)
    STATE.parent.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    today = datetime.now(KST).strftime("%Y-%m-%d")
    fired = []
    for h in hits:
        if state.get(h["id"]) == today:
            continue  # 오늘 이미 알림
        url = create_issue(h) if issue else None
        state[h["id"]] = today
        fired.append({**h, "issue": url})
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"checked": latest.get("fetched_kst"), "hits": hits, "fired": fired}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
