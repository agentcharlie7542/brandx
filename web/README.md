# web — 검수 UI (FastAPI)

개발정의서 M4. report-spec(JSON 단일 계약)을 폼으로 편집→승인→PPTX 다운로드하는 사내 웹툴.

## 실행
```bash
cd qoo10_scraper
.venv/bin/uvicorn web.app:app --reload --port 8000
# → http://localhost:8000
```
`ANTHROPIC_API_KEY`는 루트 `.env`에 (AI 초안용). 없으면 데이터+placeholder 서사까지는 동작.

## 화면 흐름
1. **홈** — 수집된 그룹(skincare/makeup) 선택 또는 자사1+경쟁3 URL 입력 → `build_spec`로 데이터부 자동 조립.
2. **검수** — 읽기전용 스코어카드(데이터 자동) + 편집 가능한 정성 서사 폼.
   - `🤖 AI 초안 생성` → `draft_narrative`(claude-opus-4-8)가 발견·SWOT·권고·시장컨텍스트 작성(~$0.11).
   - 발견·결론·SWOT·QuickWin·구조권고·시장컨텍스트·로드맵을 인라인 편집 → `💾 저장`.
   - `✅ 승인 & PPTX 생성` → review.status=approved + `deck.build` → 16슬라이드 PPTX.
3. **다운로드** — 생성된 PPTX. (PowerPoint에서 열어 검토/PDF 내보내기 — 갤러리 슬라이드 정상)

## 저장
- 프로젝트 spec: `web/projects/{pid}.json` (단일 사용자 기준 파일 저장. 멀티유저는 M3 Postgres로 이전)
- 생성 PPTX: `out/web_{pid}.pptx`

## URL 직접 입력
새 샵은 db에 수집 데이터가 있어야 분석됩니다. 미수집 시 화면에 수집 안내(CLI) 표시.
(라이브 수집을 웹에서 트리거하려면 M3 잡 큐 + 워커 필요 — 개발정의서 §4)

## 라우트
`GET /` · `POST /analyze` · `GET /p/{pid}` · `POST /p/{pid}/{save|draft|approve}` · `GET /p/{pid}/download`
