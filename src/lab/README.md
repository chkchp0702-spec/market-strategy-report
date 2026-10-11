# 🌙 킥 포트 밤 연구 실험실
- 실험 하나 = `src/lab/kMMDD_<주제>.py` 하나. 결과는 `market/lab/kMMDD_<주제>.json` 에 쓴다.
- 돌리기: `gh api -X POST repos/chkchp0702-spec/market-strategy-report/actions/workflows/lab.yml/dispatches -f ref=main -f inputs[script]=src/lab/kMMDD_<주제>.py` → 끝나면 `git pull` (로그: market/lab/_last_log.txt)
- 공통 틀은 `src/conc_bt.py`(stats·regimes·IS/OOS 나누기), `src/rules7.py`(킥 규칙), `src/rules_bt.py`(섹터 ETF 규칙 검증)를 가져다 쓴다.
- 판정 기준: 2008-07~2016 에서 고르고 2017~ 에서 시험. 시험 구간에서 S&P 대비 연수익 + 이면서 최대낙폭이 S&P 보다 작고, 손잡이를 조금 바꿔도(±20%) 결과가 유지돼야 「통과」.
- 연구 일지: brain/kick_lab.md
