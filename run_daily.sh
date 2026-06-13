#!/bin/bash
# 큐텐 경쟁사 분석 — 일일 수집·스코어 (cron 용)
# crontab 예: 0 10 * * * "/Users/.../qoo10_scraper/run_daily.sh"
# 매일 같은 시각 실행해야 리뷰 차분(추정매출)이 정확해진다.
set -u
PROJ="/Users/charlie/Documents/Claude/Projects/올리브영 비딩 프로젝트/qoo10_scraper"
cd "$PROJ" || exit 1
PY="$PROJ/.venv/bin/python"
mkdir -p logs
LOG="logs/daily_$(date +%Y%m%d).log"
{
  echo "================ $(date) ================"
  echo "--- collect (all groups) ---"
  "$PY" collect.py --group all
  for g in skincare makeup; do
    echo "--- score $g ---";     "$PY" score.py --group "$g"
    echo "--- marketing $g ---"; "$PY" marketing.py --group "$g"
    echo "--- report $g ---";    "$PY" report.py --group "$g" --pptx
  done
  echo "--- done $(date) ---"
} >> "$LOG" 2>&1
