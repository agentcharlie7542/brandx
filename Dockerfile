# Qoo10 경쟁분석 보고서 생성기 — 단일 이미지(웹 검수 UI + 수집/분석)
# 수집(collect/scraper)은 Playwright/Chromium 필요 → --with-deps 로 설치.
FROM python:3.12-slim

# 차트(matplotlib) 한글·일본어 렌더용 CJK 폰트 + 기본 빌드 유틸
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk fonts-noto-cjk-extra \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 1) 의존성 (레이어 캐시) + Chromium + OS 의존성
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

# 2) 앱 소스 (.dockerignore 로 .env·data·.venv 제외)
COPY . .

# 3) 런타임 데이터 디렉터리 (compose 에서 볼륨 마운트)
RUN mkdir -p out web/projects images logs

EXPOSE 8000

# 기본 = 웹 검수 UI. 수집은 `docker compose run --rm web python collect.py ...`
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
