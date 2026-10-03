# market-strategy-report — 매일 시황리포트 자동 제작

매일 아침 「시황리포트 시작해」 한 마디로 만들던 리포트를 코드로 옮긴 것.
**JSON 하나(그날의 판단) + 장부(누적 기록) → PDF 2개 + 카톡 텍스트**.

- `Market_Strategy_Report_YYYY_MM_DD_{AM|PM|HOL}.pdf` — 전체본 6쪽
- `Market_Strategy_Summary_YYYY_MM_DD_{AM|PM|HOL}.pdf` — 한 쪽 요약본
- `kakao.txt` — 카톡 붙여넣기용 10줄 안팎

방법(규칙)은 [`RULES.md`](RULES.md), 기록은 [`ledger/ledger.json`](ledger/ledger.json)이 원본이다.

## 폴더 구조

```
market-strategy-report/
├─ RULES.md                 # 작성 규칙 전체 (방법의 원본)
├─ data/
│  ├─ _template.json        # 하루치 입력 양식 (복사해서 채움)
│  └─ 2026-10-03.json       # 예시: 10/3 휴장판 입력
├─ ledger/
│  └─ ledger.json           # 장부: 배분·경우의 수·조건 카운트·패널 31명 누적·성적표·예고·20일 시계열
├─ src/
│  ├─ build_report.py       # 진입점. JSON+장부 → HTML → PDF → 카톡 → (--commit) 장부 반영
│  ├─ ledger.py             # 장부 읽기/쓰기, 패널 표 합성, 누적 집계, 그날 반영(중복 방지)
│  ├─ charts.py             # 고정 그림 2개 SVG (외국인 20일 · 미 10년 금리 20일)
│  ├─ render.py             # Chromium(Playwright) PDF 변환 + 쪽 넘침 검사
│  └─ kakao_text.py         # 카톡 텍스트
├─ templates/
│  ├─ base.css              # 공통 스타일 (A4, Noto Sans CJK KR)
│  ├─ report.html.j2        # 전체본 6쪽
│  └─ summary.html.j2       # 요약본 1쪽
├─ reports/
│  └─ 2026-10-03_HOL/       # 빌드 결과 (PDF·HTML·kakao.txt)
└─ .github/workflows/build.yml  # data/*.json push → 자동 빌드·커밋
```

## 설치

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
# 한글 글꼴 (Ubuntu/Debian)
sudo apt-get install -y fonts-noto-cjk
```

## 매일 흐름

1. **장부 먼저 읽기** — `ledger/ledger.json`. 누적 점수·조건 카운트·20일 그림은 전부 여기서 나온다.
2. 시세·발언을 웹에서 새로 확인한다. 확정치가 없으면 「장중 수치」, 출처가 다르면 범위로.
3. `data/_template.json`을 복사해 `data/YYYY-MM-DD.json`을 채운다. **그날의 판단만** 적는다 (누적·카운트는 적지 않는다).
4. 빌드:
   ```bash
   python -m src.build_report data/2026-10-06.json --commit
   ```
   - `reports/2026-10-06_AM/`에 PDF 2개 + HTML + kakao.txt 생성
   - 어떤 쪽이든 푸터 위 40px 안으로 글이 들어오면 **빌드 실패(exit 2)** → 글을 줄이고 다시
   - `--commit`: 장부에 그날 줄 반영(패널 득점/실점·새 발언·성적표·시계열·예고). 같은 날짜는 두 번 반영되지 않음(`_applied`)
   - `--no-strict`: 넘침이 있어도 PDF는 만든다(확인용)
5. 전달 순서: 요약본 PDF → 전체본 PDF → 카톡 텍스트.

### 판 구분
| 판 | 코드 | 언제 |
|---|---|---|
| 아침판 | `AM` | 미국 전날 종가 + 한국 전날 종가 + 밤사이 뉴스 |
| 장마감판 | `PM` | 한국 장 끝난 뒤 |
| 휴장판 | `HOL` | 한국 휴장일 |

## 입력 JSON (`data/YYYY-MM-DD.json`) 핵심 필드

| 필드 | 뜻 | 들어가는 쪽 |
|---|---|---|
| `yesterday_grades[3]` | 어제 예고 채점 띠 (`cls` ok/no/hold, `mark` ✓/✗/보류) | 1쪽·요약 |
| `one_liner` | 오늘의 한 줄 (HTML `<em>` 허용) | 1쪽·요약 |
| `kpis[8]` | 숫자 카드: 값·변화·「그래서?」·출처 | 1쪽 (요약은 `summary.kpis_pick`) |
| `decision` | 바꿈/안 바꿈 배지 + 이유 3 | 1쪽 |
| `checks[3]` | 오늘 체크할 것 | 1쪽·요약 |
| `story`, `counter[3]` | 핵심 이야기 · 반대 의견 | 2쪽 |
| `panel_today[]` | 패널 중 오늘 새 발언 (`n`, `today`, `verdict` win/loss, `new_quote`) | 3쪽 + 장부 |
| `duel`, `quotes[4]`, `outside_today[]`, `scorecard_today[]` | 1:1 대결·발언·패널 밖·성적표 | 4쪽 + 장부 |
| `allocation_seen[8]`, `scenario_delta`, `triangle`, `candidates_signal` | 배분표 비고·경우의 수 변화·삼각 점검·축 후보 | 5쪽 |
| `schedule[]`, `falsify[]`, `missing`, `sources` | 일정·틀렸다는 신호·못 찾은 것·출처 | 6쪽 |
| `ledger_commit.series_add` | 장부 시계열에 더할 그날 값 (외국인·10Y) | 그림 |
| `summary`, `kakao` | 요약본 전용 줄·카톡 줄 | 요약·카톡 |

## 장부 (`ledger/ledger.json`) 구성

- `allocation[8]` 비중 · `scenarios[4]` 경우의 수 확률 · `scenario_history`
- `conditions[10]` 비중 바꾸는 조건과 카운트 (예: 10년 5.0~5.3 머문 날 n/20, 외국인 복귀 신호 0/2)
- `panel[31]` 전략가 고정 패널 — 순서·판정 숫자·`win/loss` 누적·마지막 입장(q1/q2/q3)
- `outside_panel`, `scorecard`(맞음·틀림·반반·보류), `forecasts`(다음 판 채점 대상)
- `series.foreign_kospi`, `series.us10y` — 20일 그림 원천 (`range` 필드로 출처 차이 기록)
- `candidates` 축 후보 · `_applied` 반영된 날짜 목록

집계 시작: **2026-10-02**. 그 전 숫자는 넣지 않는다.

## GitHub Actions

`data/*.json`(또는 템플릿·소스)을 push하면 `.github/workflows/build.yml`이
가장 최신 데이터 파일로 빌드 → `reports/`와 `ledger/`를 `report-bot` 이름으로 커밋 → PDF를 artifact로도 올린다.
수동 실행: Actions → build-report → Run workflow → `data/2026-10-06.json`.

> 넘침으로 빌드가 실패하면 Actions가 빨간불. 로그의 `p1:+NN` 숫자가 음수인 쪽을 줄인다.

## 절대 규칙

**시황 전략과 고객 제안서는 섞지 않는다.** 이 리포지토리에는 고객 이름·고객 포트폴리오·제안서 내용이 들어가지 않는다. (`RULES.md` 00)

## 유의사항

정보 제공 목적이며 투자자문이 아님 · 비중·확률·조건·채점은 작성자 판단 · 종목·ETF는 예시이며 매수 추천 아님 · 원금 손실 가능.

## 대시보드 (휴대폰 한 장)
- `python -m src.build_dashboard` → `docs/index.html`(GitHub Pages용) + `docs/artifact.html`(Claude 아티팩트 본문)
- 매일 아침 예약 작업이 다시 만들어 `docs/ARTIFACT_URL.txt`에 적힌 Claude 아티팩트 주소로 다시 올린다 (주소는 그대로).
- GitHub Pages 를 켜면(Settings → Pages → main, /docs) `https://chkchp0702-spec.github.io/market-strategy-report/` 로도 열린다. 비공개 저장소는 요금제에 따라 막힐 수 있다.

## 자동 수집·알림 (`.github/workflows/fetch.yml`)
- `src/fetch_market.py`: Yahoo Finance(지수·금리·환율·원자재·종목), 미 재무부(10년·30년 확정치), 네이버 금융(외국인 순매수, 되면), James Lee 블로그 RSS → `market/latest.json`, `market/history.csv`, `feeds/james_lee.json`
- 매일 07:00 KST + 한국·미국 장중 매시간. 못 받은 값은 null — 숫자를 만들지 않는다.
- `src/alerts.py`: 10년 5.30↑/5.20↓ · 브렌트 95↓ · 코스피 6,500 · 마이크론 −5%+나스닥 · 은행 ETF −2% · 외국인 순매수 전환/2일 · 금+30년 · VIX 30 → **GitHub Issue** 로 알림(휴대폰 GitHub 앱 알림). 같은 조건은 하루 한 번(`alerts/state.json`).

## 채점·순위·회고
- `data → forecasts_p`: 「볼 것 3개」각각의 확률. 다음 리포트 채점과 짝지어 `ledger.calibration` 에 쌓이고 브라이어 점수·구간별 적중이 4쪽 성적표와 대시보드에 나온다.
- `--rerank`: 매월 첫 리포트에서 패널을 그룹 안 적중률 순으로 재정렬 (판정 2건 이상), `ledger.panel_rank_history` 기록.
- `python -m src.review weekly --date <일요일>`: 지난 7일 집계(`reviews/weekly_*.md/json`) — 일요일 **주간판(WK)** 본문 재료.
- `python -m src.review monthly --month YYYY-MM`: 틀린 것만 모은 회고 골격(`reviews/YYYY-MM.md`). 「왜 틀렸나」는 사람이 채우고, 고친 규칙은 RULES.md 이력에 적는다.
- `python -m src.verify data/YYYY-MM-DD.json`: 입력 숫자를 자동 수집치와 대조해 어긋난 것을 표로 낸다.
