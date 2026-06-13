# 배포 가이드 (사내 단일 서버 · Docker)

웹 검수 UI + 라이브 수집/분석을 한 이미지로 컨테이너화. 사내망에서 `http://<서버IP>:8000`.
데이터는 named volume 으로 영속 → **Windows·Mac·Linux 동일하게** 동작(단일 파일 마운트 이슈 없음).

---

## A. Windows PC 에 배포 (권장 환경)

### 1. 사전 설치 (1회)
- **Docker Desktop for Windows** — https://www.docker.com/products/docker-desktop/
  설치 시 **WSL2 백엔드** 사용(설치 마법사가 안내). 설치 후 Docker Desktop 실행해 둘 것.
- **Git for Windows** — https://git-scm.com/download/win (또는 GitHub에서 ZIP 다운로드도 가능)

### 2. 코드 받기 + API 키 (PowerShell)
```powershell
git clone https://github.com/agentcharlie7542/brandx.git
cd brandx
Copy-Item .env.example .env
notepad .env        # ANTHROPIC_API_KEY=sk-ant-... 입력 후 저장
```

### 3. 빌드 + 기동
```powershell
docker compose up -d --build
```
> 첫 빌드는 Chromium(+의존성) 설치로 **수 분** 소요. CJK 폰트 포함 → 차트 한글·일본어 정상.
> `docker compose logs -f web` 로 로그 확인. `qoo10.db` 를 미리 만들 필요 없음(named volume 자동 생성).

### 4. 접속 주소 확인 + 방화벽
```powershell
ipconfig            # "IPv4 주소" 확인 (예: 192.168.0.50)
```
- Windows Defender 방화벽 → **인바운드 규칙 → 포트 8000 TCP 허용** (사내망/Private 프로필).
- 동료에게 공유: **`http://192.168.0.50:8000`** (같은 사내망에서 접속).

---

## B. 사용 (웹에서 라이브 수집)
1. 브라우저에서 `http://<서버IP>:8000`
2. 자사 1 + 경쟁사 1~3개의 **Qoo10 샵 URL**(`https://www.qoo10.jp/shop/<슬러그>`) 입력 → **분석 시작**
3. 자동: 라이브 수집(상품·샵·이미지) → **디자인 비전 평가(Claude)** → 정량+디자인 분석 → 검수 화면
4. 🤖 AI 초안 → 검수·편집 → ✅ 승인 → **PPTX 다운로드**

> 샵당 수집 수십 초~수 분 + 디자인 비전 ~$0.036/샵 + 서사 ~$0.11 → 보고서 1건 ≈ $0.3 안팎.
> 같은 샵을 같은 날 재분석하면 수집 스킵해 빠름. **샵 URL만 가능**(상품 페이지 URL은 거부).

---

## C. 운영
| 항목 | |
|---|---|
| 상시 가동 | compose `restart: unless-stopped` → 재부팅/크래시 시 자동 재기동. PC를 항상 켜둘 것 |
| 데이터 영속 | named volume(`qoo10_data`·`qoo10_images`·`qoo10_out`·`qoo10_projects`). 컨테이너 지워도 유지 |
| 업데이트 | `git pull` → `docker compose up -d --build` |
| 중지 | `docker compose down` (데이터 볼륨은 유지) |
| 데이터 초기화 | `docker compose down -v` (볼륨까지 삭제 — 주의) |

## D. 보안·준법 (사내 전용)
- `.env`·수집 데이터·이미지는 git/이미지에 **포함 안 됨**(.gitignore·.dockerignore).
- **사내망 한정** 노출 권장(외부 공개 시 인증·리버스프록시 별도). 멀티유저·외부 SaaS는 개발정의서 §4(M3) 확장.
- 수집은 Qoo10 약관 준수(요청 간격·내부 분석 한정).

## E. macOS/Linux 서버 (동일)
```bash
git clone https://github.com/agentcharlie7542/brandx.git && cd brandx
cp .env.example .env   # 키 입력
docker compose up -d --build
ipconfig getifaddr en0   # Mac (Linux: hostname -I) → http://<IP>:8000
```

## CI
`.github/workflows/ci.yml` — push/PR 시 ① report-spec 스키마+샘플 검증 ② 덱 생성 스모크(16슬라이드) ③ import ④ Docker 빌드.
