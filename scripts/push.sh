#!/usr/bin/env bash
# 안전한 push — 이 실행에서 만든 파일만 올리고, 다른 사람(두뇌 세션·다른 워크플로)이 올린 건 절대 덮지 않는다.
#   사용: scripts/push.sh "커밋 메시지" 경로1 [경로2 ...]
#   1) 주어진 경로만 add → 바뀐 게 있으면 commit
#   2) 최대 6번: pull --rebase → push. 충돌이면 rebase 를 버리고, origin/main 위에 「우리가 만든 파일」만 다시 얹어 커밋
#      (reset --soft 로 다른 파일은 원격 것이 그대로 남는다 — -X theirs 처럼 남의 수정을 조용히 지우지 않음)
#   3) 6번 다 실패하면 exit 1 (잡 실패로 보이게)
set -u
IFS=$'\n'
msg="$1"; shift
[ $# -ge 1 ] || { echo "push.sh: 경로가 없음"; exit 2; }
git config user.name >/dev/null || git config user.name "report-bot"
git config user.email >/dev/null || git config user.email "report-bot@users.noreply.github.com"

git add -A -- "$@"
if git diff --cached --quiet; then
  echo "push.sh: 바뀐 것 없음"; exit 0
fi
git commit -q -m "$msg"

# 우리 커밋이 바꾼 파일 목록과 그 내용(재시도 때 다시 얹기용)
files=$(git -c core.quotepath=off diff --name-only HEAD~1 HEAD)
stash_dir=$(mktemp -d)
for f in $files; do
  if [ -e "$f" ]; then mkdir -p "$stash_dir/$(dirname "$f")"; cp -p "$f" "$stash_dir/$f"; fi
done

delay=5
for i in 1 2 3 4 5 6; do
  if git pull -q --rebase --autostash origin main; then
    if git push -q origin HEAD:main; then echo "push.sh: 올림 ($i번째)"; rm -rf "$stash_dir"; exit 0; fi
  else
    echo "push.sh: rebase 충돌 → 원격 위에 우리 파일만 다시 얹음"
    git rebase --abort 2>/dev/null || true
    git fetch -q origin main
    git reset -q --soft origin/main          # 작업 트리는 그대로, HEAD 만 원격으로
    git reset -q                             # 인덱스 비우기
    git checkout -q origin/main -- . 2>/dev/null || true   # 우리가 안 만든 파일은 원격 것으로
    for f in $files; do
      if [ -e "$stash_dir/$f" ]; then mkdir -p "$(dirname "$f")"; cp -p "$stash_dir/$f" "$f"; git add -- "$f"
      else git rm -q --ignore-unmatch -- "$f"; fi
    done
    if git diff --cached --quiet; then echo "push.sh: 원격과 같아짐 — 올릴 것 없음"; rm -rf "$stash_dir"; exit 0; fi
    git commit -q -m "$msg"
    if git push -q origin HEAD:main; then echo "push.sh: 올림 ($i번째, 다시 얹음)"; rm -rf "$stash_dir"; exit 0; fi
  fi
  [ $i -eq 6 ] && break
  echo "push.sh: 실패 $i/6 — ${delay}초 뒤 다시"
  sleep $delay; [ $delay -lt 40 ] && delay=$((delay * 2))
done
rm -rf "$stash_dir"
echo "push.sh: 6번 모두 실패"; exit 1
