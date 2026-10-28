"""🎯 예고의 「공짜 확률(기저율)」 계산 — 10/28 사용자 「다 고쳐」 (예고가 아무 생각 없이 찍어도 맞는 문제로 바뀌었던 것)

예고 하나가 「아무 판단 없이 찍어도 몇 % 맞는 문제인가」를 과거 자료로 잰다.
지금 값에서 그 선(또는 띠)까지의 거리를 「다음 거래일(또는 N거래일) 수익률」로 바꿔, 최근 500거래일 중 그만큼 움직인 날의 비율을 센다.

사용:
  python -m src.fcbase <야후티커> above <선>          # 다음 거래일 종가가 선 위
  python -m src.fcbase <야후티커> below <선>          # 선 아래
  python -m src.fcbase <야후티커> band <아래> <위>     # 띠 안
  python -m src.fcbase <야후티커> up | down           # 오른다/내린다
  python -m src.fcbase <티커A> beat <티커B>            # A 가 B 보다 더 오른다(같은 날 수익률)
  옵션 --days N (기본 1 = 다음 거래일) · --now 값 (지금 값을 직접 줄 때. 없으면 마지막 종가)
예: python -m src.fcbase ^TNX band 4.90 5.10   ·   python -m src.fcbase BZ=F above 110   ·   python -m src.fcbase CIBR beat SPY
출력: 기저율 0.xx · 표본 n — 리포트 data 의 forecasts_base 에 이 숫자를, forecasts_base_how 에 이 명령을 적는다.
규칙(RULES 1-F): 기저율 0.65 넘는 예고는 「공짜 문제」라 내지 않는다(src.verify 가 막음).
"""
from __future__ import annotations
import sys


def series(t: str, days: int = 520):
    import yfinance as yf
    df = yf.download(t, period="3y", interval="1d", auto_adjust=True, progress=False)
    s = df["Close"]
    if hasattr(s, "columns"):
        s = s.iloc[:, 0]
    return s.dropna().iloc[-days:]


def base(args: list[str]) -> tuple[float, int, str]:
    days = 1
    now = None
    if "--days" in args:
        i = args.index("--days"); days = int(args[i + 1]); del args[i:i + 2]
    if "--now" in args:
        i = args.index("--now"); now = float(args[i + 1]); del args[i:i + 2]
    t, op = args[0], args[1]
    s = series(t)
    last = now if now is not None else float(s.iloc[-1])
    r = (s.shift(-days) / s - 1).dropna()          # N거래일 뒤 수익률 (과거 분포)
    if op == "beat":
        o = series(args[2])
        ro = (o.shift(-days) / o - 1).dropna()
        j = r.index.intersection(ro.index)
        hit = (r.loc[j] > ro.loc[j]).mean()
        return float(hit), len(j), f"{t} 가 {args[2]} 보다 더 오름 ({days}거래일)"
    if op == "up":
        return float((r > 0).mean()), len(r), f"{t} 오름 ({days}거래일)"
    if op == "down":
        return float((r < 0).mean()), len(r), f"{t} 내림 ({days}거래일)"
    if op == "above":
        need = float(args[2]) / last - 1
        return float((r > need).mean()), len(r), f"{t} {args[2]} 위 (지금 {last:,.4g} · 필요한 움직임 {need * 100:+.2f}%)"
    if op == "below":
        need = float(args[2]) / last - 1
        return float((r < need).mean()), len(r), f"{t} {args[2]} 아래 (지금 {last:,.4g} · 필요한 움직임 {need * 100:+.2f}%)"
    if op == "band":
        lo, hi = float(args[2]) / last - 1, float(args[3]) / last - 1
        return float(((r >= lo) & (r <= hi)).mean()), len(r), f"{t} {args[2]}~{args[3]} 안 (지금 {last:,.4g} · 띠 {lo * 100:+.2f}%~{hi * 100:+.2f}%)"
    raise SystemExit("op 는 above · below · band · up · down · beat")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__); return 2
    b, n, what = base(sys.argv[1:])
    flag = " ⛔ 공짜 문제(0.65 초과) — 내지 말 것" if b > 0.65 else ""
    print(f"기저율 {b:.2f} · 표본 {n} · {what}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
