"""🌅 11/19 아침판 — 조언 성적표(9번) 채점용 종가를 과거 market/sectors.json 커밋에서 한 번 채워 넣는다.
   gh api 로 커밋 목록 → 날짜(asof)마다 마지막 것 하나 → {asof: {sym: last}} → market/morning_px.json
   사용: python tools/morning_backfill.py 2026-10-01   (gh 로그인 필요 · 한 번만)"""
import json, subprocess, sys
from pathlib import Path

REPO = "chkchp0702-spec/market-strategy-report"
OUT = Path(__file__).resolve().parent.parent / "market" / "morning_px.json"


def gh(path, raw=False):
    cmd = ["gh", "api", path] + (["-H", "Accept: application/vnd.github.raw"] if raw else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[:200])
    return r.stdout


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else "2026-10-01"
    shas, page = [], 1
    while True:
        js = json.loads(gh(f"repos/{REPO}/commits?path=market/sectors.json&since={since}T00:00:00Z&per_page=100&page={page}"))
        if not js:
            break
        shas += [(c["commit"]["committer"]["date"], c["sha"]) for c in js]
        page += 1
    shas.sort()
    # UTC 날짜마다 마지막 커밋 하나
    last = {}
    for dt, s in shas:
        last[dt[:10]] = s
    px = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for day, s in sorted(last.items()):
        try:
            S = json.loads(gh(f"repos/{REPO}/contents/market/sectors.json?ref={s}", raw=True))
        except Exception as e:
            print(day, "실패", e); continue
        a = S.get("asof")
        if not a or a in px:
            continue
        row = {r["sym"]: r.get("last") for r in S.get("rows", []) if r.get("last")}
        if (S.get("spy") or {}).get("last"):
            row["SPY"] = S["spy"]["last"]
        px[a] = row
        print(a, len(row))
    OUT.write_text(json.dumps(dict(sorted(px.items())), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("저장", OUT, len(px), "일")


if __name__ == "__main__":
    main()
