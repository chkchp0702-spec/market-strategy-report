#!/usr/bin/env bash
# ⏰ 시세 수집(fetch.yml) 깨우기 — GitHub 예약(schedule)이 몇 시간씩 빠지는 문제(10/12 평일 장중 8번 중 2번만 돎)를
#   피드 이어달리기가 15분마다 보고, fetch.yml 의 예약 시간대인데 마지막 실행이 50분 넘게 지났으면 직접 켠다.
#   예약 시간대 = fetch.yml cron 과 같음: 평일(UTC) 00~07시·13~20시 + 매일 21시(15분 뒤).
# 필요: GH_TOKEN(actions: write), GITHUB_REPOSITORY
set -u
H=$((10#$(date -u +%H))); M=$((10#$(date -u +%M))); D=$(date -u +%u)
due=0
if [ "$D" -le 5 ] && { [ "$H" -le 7 ] || { [ "$H" -ge 13 ] && [ "$H" -le 20 ]; }; }; then due=1; fi
if [ "$H" -eq 21 ] && [ "$M" -ge 15 ]; then due=1; fi
[ "$due" = 1 ] || { echo "fetch 예약 시간대 아님"; exit 0; }
last=$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/fetch.yml/runs?per_page=1" --jq '.workflow_runs[0].created_at' 2>/dev/null) || { echo "fetch 실행 기록 못 읽음"; exit 0; }
[ -n "$last" ] || exit 0
age=$(( ( $(date -u +%s) - $(date -u -d "$last" +%s) ) / 60 ))
if [ "$age" -ge 50 ]; then
  echo "fetch 마지막 실행 ${age}분 전 → 깨움"
  gh api -X POST "repos/$GITHUB_REPOSITORY/actions/workflows/fetch.yml/dispatches" -f ref=main -f "inputs[wake]=yes" || true
else
  echo "fetch 마지막 실행 ${age}분 전 — 그대로"
fi
exit 0
