#!/usr/bin/env bash
# 대시보드 데이터 갱신 + git push
# 사용: scripts/publish.sh
# 데몬으로: while true; do scripts/publish.sh; sleep 3600; done

set -e
cd "$(dirname "$0")/.."

echo "[$(date '+%F %T')] export 시작"
python3 scripts/export_for_web.py 2>&1 | grep -v NotOpenSSL | grep -v warnings.warn || true

if [ ! -d .git ]; then
  echo "git repo 아님 — git init 필요"
  exit 1
fi

# 원격이 없으면 push 스킵
if ! git remote get-url origin > /dev/null 2>&1; then
  echo "git remote 'origin' 미설정 — push 스킵"
  exit 0
fi

# 변경이 없으면 스킵
if git diff --quiet docs/data 2>/dev/null && ! ls docs/data/*.json > /dev/null 2>&1; then
  echo "변경 없음"
  exit 0
fi

git add docs/

if git diff --cached --quiet; then
  echo "스테이지된 변경 없음"
  exit 0
fi

git commit -m "data: $(date '+%F %T') 대시보드 데이터 갱신" || true
git push origin main || git push origin master || echo "push 실패 (원격 확인)"
