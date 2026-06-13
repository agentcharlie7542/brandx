# 배포 가이드 (사내 단일 서버 · Docker)

웹 검수 UI + 수집/분석을 한 이미지로 컨테이너화. 사내망에서 `http://<host>:8000`.

## 1. 사전 준비
```bash
git clone https://github.com/agentcharlie7542/brandx.git
cd brandx
cp .env.example .env          # ANTHROPIC_API_KEY 입력 (AI 서사용)
touch qoo10.db                # 수집 데이터 파일 (최초 1회, 비어있어도 됨)
```

## 2. 빌드 & 기동
```bash
docker compose up -d --build
# → http://localhost:8000  (사내망이면 http://<서버IP>:8000)
docker compose logs -f web   # 로그
```
> 첫 빌드는 Chromium(+OS 의존성) 설치로 수 분 소요. CJK 폰트 포함되어 차트 한글·일본어 정상 렌더.

## 3. 사용 (웹에서 라이브 수집)
별도 수집 단계 없이 **웹 UI에서 직접** 합니다:
1. 브라우저에서 `http://<서버IP>:8000` 접속
2. 자사 1 + 경쟁사 1~3개의 **Qoo10 샵 URL**(`https://www.qoo10.jp/shop/<슬러그>`) 입력 → **분석 시작**
3. 서버가 자동으로: 라이브 수집(상품·샵·이미지) → **디자인 비전 평가(Claude)** → 정량+디자인 분석 → 검수 화면
4. 🤖 AI 초안 → 검수·편집 → ✅ 승인 → **PPTX 다운로드**

> 샵당 수집 수십 초~수 분(매너상 5초 대기 포함) + 디자인 비전 ~$0.036/샵 + 서사 ~$0.11. 보고서 1건 ≈ $0.3 안팎.
> 같은 샵을 같은 날 재분석하면 수집을 스킵해 빠릅니다.

## 4. 데이터 영속 (호스트 바인드 마운트)
| 호스트 | 컨테이너 | 내용 |
|---|---|---|
| `./qoo10.db` | `/app/qoo10.db` | 수집 스냅샷 |
| `./images` | `/app/images` | 캡처·배너 |
| `./out` | `/app/out` | 생성 PPTX·차트 |
| `./web/projects` | `/app/web/projects` | 검수 프로젝트 spec |

컨테이너를 지워도 위 디렉터리는 호스트에 남습니다.

## 5. 업데이트
```bash
git pull && docker compose up -d --build
```

## 6. 보안·운영 메모 (사내 전용)
- `.env`·`qoo10.db`·`images/`·`out/` 는 git/이미지에 **포함되지 않음**(.gitignore·.dockerignore).
- 사내망 한정 노출 권장(공개 시 인증·리버스프록시 추가). 외부 SaaS·멀티유저는 개발정의서 §4(M3: 잡큐·Postgres) 확장.
- 수집은 Qoo10 약관 준수(요청 간격·일 1회·내부분석 한정).

## CI
`.github/workflows/ci.yml` — push/PR 시 ① report-spec 스키마+샘플 검증 ② 덱 생성기 스모크(샘플→16슬라이드 PPTX) ③ import 스모크 ④ Docker 이미지 빌드 검증.
