# deck — report-spec → 폴리시드 16슬라이드 PPTX 생성기

개발정의서(`../개발정의서_웹서비스_20260612.md`)의 **M0 핵심 산출물**.
기존 "완성" 덱을 수작업이 아니라 **코드로** 생성한다. 입력은 단일 계약 `report-spec`(JSON), 출력은 16:9 PPTX.

```bash
python -m deck.build samples/report_spec_makeup.json   out/gen_makeup.pptx     # 7샵(메이크업 완성덱 재현)
python -m deck.build samples/report_spec_foursome.json out/gen_foursome.pptx   # 4샵(자사1+경쟁3, 제품 표준)
```

## 구조
| 파일 | 역할 |
|---|---|
| `theme.py` | 디자인 시스템 — 팔레트·치수·폰트(기존 덱 도형에서 측정한 실측 색/좌표) |
| `components.py` | 재사용 컴포넌트 — 헤더바·카드·칩·표셀·이미지(center-crop)·그림자 |
| `charts.py` | spec → 차트 PNG(루브릭 막대·갭 막대·포지셔닝 산점도, matplotlib) |
| `slides.py` | 16개 슬라이드 빌더. **샵 수에 따라 표 행·갤러리 카드·이벤트표 행 동적 배치** |
| `build.py` | 오케스트레이터 + CLI. spec 검증(jsonschema) → 차트 생성 → 16슬라이드 → 저장 |

## 입력 계약
`../schemas/report_spec.schema.json` (JSON Schema). 데이터(자동) + 서사(AI 초안→사람 검수)를 합친 단일 문서.
- **데이터 슬라이드**(스코어카드·포지셔닝·갤러리·이벤트표·갭): `metrics`/`design_scores`/`gap`/`marketing`/`gallery`에서 자동.
- **서사 슬라이드**(요약·시장컨텍스트·SWOT·권고·로드맵): `narrative.*` (AI가 초안, 사람이 검수).

## 동적 레이아웃
샵 수에 맞춰 자동 적응 — 검증: 7샵(4+3 갤러리·7행 표)과 4샵(1×4 갤러리·4행 표) 모두 정상.
- 스코어카드/이벤트표: 행 높이·간격을 가용 공간/N으로 계산.
- 갤러리: `cols = min(4, N)`, 행 수 자동, 이미지 center-crop.
- 헤더 문구: 자사 1개=「자사 강조」, 2개+=「★ 자사 N개샵」.

## 렌더 검증 주의 (LibreOffice)
내부 QA로 LibreOffice headless(pptx→PDF→PNG) 사용 시:
- **디자인 갤러리(p8)가 7장 2행 구성일 때 LibreOffice에서만 좌상단 축소로 깨져 보임**(원본 완성덱·생성덱 공통). **PowerPoint에서는 정상.** 4샵(1행)에선 LibreOffice도 정상.
- 일본어 자간(平成 등)도 LibreOffice 폰트 폴백 한정 이슈. 최종 산출/검수는 PowerPoint 기준.

## 다음(개발정의서 M1~)
- `core/build_spec.py`: 수집·스코어링 결과(db/score/marketing) → report-spec 데이터부 자동 조립.
- `narrative` 초안: Claude API로 서사 채움(검수 전 status=draft).
- 웹 검수 UI: report-spec 편집 → 승인 → 이 생성기 호출.
