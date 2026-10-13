"""🔔 하루 두 번 「열어 볼 이유」 알림 (10/13 사용자: "사람들이 이 앱을 더 자주 열게" ②·⑦)

  ② 평일 한국 장 마감 뒤(15:40~20:00 KST) 한 번 — 💼 내 포트 어젯밤(미국) 성적 vs S&P + 오늘 코스피·코스닥 마감
  ⑦ 토요일 아침(08:30~14:00 KST) 한 번 — 📅 이번 주 복기 (포트 vs S&P · 예고 채점 · 다음 주 일정)
  보내는 곳: ntfy chkchp-ch-report → stock-screener push-relay 가 앱 「알림 받기」 켠 휴대폰으로 보냄.
  같은 날 두 번 안 보냄: market/nudge.json 에 보낸 날 기록. fetch.yml 이 매시간 home 다음에 돌린다.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "market"
TOPIC = "https://ntfy.sh/chkchp-ch-report"
APP = "https://chkchp0702-spec.github.io/daily-app/"


def rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d if d is not None else {}


def sg(v, d=1):
    return "–" if v is None else f"{v:+.{d}f}%"


def send(title, body, click, dry=False):
    print("보냄" if not dry else "(시험)", title, "|", body)
    if dry:
        return True
    try:
        req = urllib.request.Request(TOPIC, data=body.encode("utf-8"), method="POST",
                                     headers={"Title": title.encode("utf-8"), "Click": click, "Tags": "bar_chart"})
        urllib.request.urlopen(req, timeout=20).read()
        return True
    except Exception as e:
        print("보내기 실패", e)
        return False


def close_msg(H, LA, now):
    P = H.get("port") or {}
    ks, kq = (LA.get("items") or {}).get("kospi") or {}, (LA.get("items") or {}).get("kosdaq") or {}
    if not str(ks.get("asof_utc", "")).startswith(now.strftime("%Y-%m-%d")):
        return None                                      # 오늘 한국장이 안 열렸으면(휴장) 안 보냄
    d1, d1k, d1s = P.get("d1"), P.get("d1_kick"), P.get("d1_spy")
    best = max([x for x in (("기본", d1), ("킥", d1k)) if x[1] is not None], key=lambda x: x[1], default=None)
    win = best is not None and d1s is not None and best[1] >= d1s
    ex = (P.get("kick") or 0) - (P.get("spy") or 0)
    dd = str(P.get("d1_date") or "")[5:].replace("-", "/")
    title = f"📊 {now.month}/{now.day} 마감 · 내 포트 성적표"
    body = (f"💼 {dd}(미국) 기본 {sg(d1, 2)} · ⚡ 킥 {sg(d1k, 2)} · S&P {sg(d1s, 2)} → {'이겼어요 👍' if win else '졌어요'}\n"
            f"누적 킥 {sg(P.get('kick'), 2)} (S&P보다 {ex:+.2f}%p)\n"
            f"🇰🇷 오늘 코스피 {sg(ks.get('change_pct'), 2)} · 코스닥 {sg(kq.get('change_pct'), 2)}")
    return title, body, APP + "#port"


def week_msg(H, now):
    W = H.get("week") or {}
    if not W.get("days"):
        return None
    r = W.get("rep") or {}
    nx = (W.get("next") or [])[:2]
    best = max([("💼 기본", W.get("base")), ("⚡ 킥", W.get("kick")), ("🎯 집중", W.get("conc"))], key=lambda x: -999 if x[1] is None else x[1])
    title = f"📅 이번 주 복기 · {now.month}/{now.day}"
    body = (f"{best[0]} {sg(best[1], 2)} vs S&P {sg(W.get('spy'), 2)} · 코스피 {sg(W.get('kospi'), 2)}\n"
            f"시황 예고 {r.get('win', 0)}맞음 · {r.get('loss', 0)}틀림 (채점 {r.get('n', 0)}건)\n"
            + ("앞으로: " + " · ".join(f"{x['when']} {x['what'][:22]}" for x in nx) if nx else ""))
    return title, body.strip(), APP + "#home"


def main() -> int:
    dry = "--dry" in sys.argv
    now = dt.datetime.now(KST)
    if "--at" in sys.argv:                                 # 시험용: --at 2026-10-13T16:05
        now = dt.datetime.fromisoformat(sys.argv[sys.argv.index("--at") + 1]).replace(tzinfo=KST)
    H, LA = rj(M / "home.json"), rj(M / "latest.json")
    st_f = M / "nudge.json"
    ST = rj(st_f, {})
    today = now.strftime("%Y-%m-%d")
    hm = now.hour * 60 + now.minute
    sent = False
    if now.weekday() < 5 and 15 * 60 + 40 <= hm <= 20 * 60 and ST.get("close") != today:
        m = close_msg(H, LA, now)
        if m and send(*m, dry=dry):
            ST["close"] = today; sent = True
    if now.weekday() == 5 and 8 * 60 + 30 <= hm <= 14 * 60 and ST.get("week") != today:
        m = week_msg(H, now)
        if m and send(*m, dry=dry):
            ST["week"] = today; sent = True
    if sent and not dry:
        st_f.write_text(json.dumps(ST, ensure_ascii=False), encoding="utf-8")
    if not sent:
        print("지금은 보낼 때가 아님", now.strftime("%a %H:%M"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
