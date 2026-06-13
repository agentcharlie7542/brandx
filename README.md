# Qoo10 경쟁사 비교분석 도구

올리브영 비딩 1회성이 아닌, **재사용 가능한 경쟁사 분석 파이프라인**.
Playwright + SQLite + pandas 기반. 명세: `경쟁사_비교분석_도구_개발명세_20260605.md`.

```
[shops_groups.py 그룹 설정]
        │
[1] collect.py   ── 샵/상품/이미지 일일 스냅샷 → SQLite + images/
        │            └ --details: 샵당 상위 N개 상세페이지(상세컷·히어로 배너)
        │
[2] score.py     ── 정량 지표 + 정성 루브릭 병합 → out/scorecard_{group}.xlsx
        │
[2b] vision.py   ── 상세컷 Claude 비전 OCR → 상품별 컨셉·소구점 (ANTHROPIC_API_KEY 필요)
        │
[3] report.py    ── 포지셔닝 맵 png · 디자인 갤러리 · 갭표 · pptx
```

## 설치
```bash
pip install -r requirements.txt
playwright install chromium
```

## 사용
```bash
# 1) 수집 (일 1회 cron 권장)
python collect.py --group skincare          # 그룹 단위 수집(상품+샵+이미지)
python collect.py --group all               # 전 그룹
python collect.py --group makeup --no-images  # 이미지 제외(빠른 지표 갱신)
python collect.py --group skincare --debug  # 내부 XHR 엔드포인트 캡처
python collect.py --group all --details --top 10  # + 샵당 상위 10개 상세페이지(상세컷·히어로)

# 2) 스코어링
python score.py --group skincare            # 지표 계산 + 루브릭 병합 + xlsx
python score.py --group all --no-xlsx       # 콘솔 출력만

# 2b) 비전 컨셉 분석 (상세컷 OCR → 상품별 컨셉·소구점)  ※ ANTHROPIC_API_KEY 필요
python vision.py --group skincare --limit 1 # 스모크(1상품, 비용 확인)
python vision.py --group skincare           # 미분석 상품만 분석 → out/concepts_*.csv
python vision.py --group all --refresh       # 전체 재분석

# 3) 마케팅 인텔리전스 (톤앤매너·콜라보·이벤트·컨셉)
python marketing.py --group skincare        # design_intelligence_*.md + collab_*.csv

# 4) 리포트
python report.py --group skincare           # 포지셔닝 맵(png) + 갭표(csv)
python report.py --group skincare --pptx    # + PPTX 보고서(마케팅 섹션 포함)
python report.py --pptx --merge             # 전 그룹 통합 1부
```

## 마케팅 인텔리전스 (`marketing.py`)
- **인플루언서·IP 콜라보 리스트**: 수집 상품명에서 `コラボ` 파트너 자동 채굴 (재수집 불필요).
- **톤앤매너·메인 캠페인**: 샵 톱 캡처 기반 AI 시각분석(`TONE` 상수, 잠정). 이미지 배너는 alt가 없어 자동 추출 불가 → 캡처 육안 분석분을 명시 기입.
- **이벤트 강도**: 限定/先行/GIFT/セット/メガ割 등 상품명 태그 빈도 + 쿠폰·타임세일·메가와리.
- 산출: `out/design_intelligence_{group}.md`, `out/collab_{group}.csv`. PPTX에도 3개 슬라이드로 병합.
- 메인 배너 크롭(시각 인벤토리): `out/banners/{shop}_main.jpg`.

## 분석 그룹 (`shops_groups.py`)
| 그룹 | 자사 | 경쟁사 |
|---|---|---|
| skincare | biohealboh_official | anua, vtcosmetics, skin1004japan, skinnlab, dalba |
| makeup | wakemake_official, colorgram | lakaofficial, fwee, ROMAND, milktouch, amuse |

그룹은 자유롭게 추가 가능 (URL 규칙: `https://www.qoo10.jp/shop/{shop_id}`).

## 모듈
1. `shops_groups.py` — 그룹(자사/경쟁사) 정의 + `resolve_group()` 해석.
2. `collect.py` — 그룹 순회 수집 오케스트레이터. 샵 간 5초 대기, 실패 샵 스킵. `--details`로 상위 N개 상세페이지 수집.
3. `scraper.py` — Qoo10 DOM 파싱. `scrape_shop_full()`(목록+샵헤더+이미지), `scrape_shop_details()`(상세페이지·상세컷).
4. `images.py` — 썸네일/배너/풀캡처 + `capture_hero_banner()`(메인 히어로 정밀) + `download_detail_images()`(상세컷).
5. `db.py` — SQLite 스키마. `shop_snapshots`/`image_assets`/`design_scores`/`product_details`/`product_concepts`.
6. `score.py` — 정량 지표(가격·리뷰볼륨·Top5파워·세트비중·추정매출·프로모션강도) + 디자인 루브릭 병합.
7. `vision.py` — 상세컷을 세로 타일 분할 → Claude 비전(claude-opus-4-8) 구조화 추출 → `product_concepts`·`out/concepts_*.csv`.
8. `report.py` — matplotlib 포지셔닝 맵, 디자인 갤러리, 갭 분석, python-pptx 보고서.
9. `estimator.py` — 리뷰 차분 ÷ 작성률 × 가격 = 추정 매출 (score.py가 재사용).
10. `rakuten.py` — (선택) 라쿠텐 확장.

## 디자인 루브릭 (수기 채점)
정성 5개 항목을 5점 척도로 채점해 병합. 입력 우선순위: `rubric_{group}.csv` > `design_scores` 테이블.

| 항목 | 가중치 | 5점 기준 |
|---|---|---|
| 썸네일 | 25% | 소셜프루프 배지 + 베네핏 시각화 + 톤 통일 |
| 샵 메인 | 20% | 스토리·기획전·랭킹·이벤트 구좌 체계화 |
| 현지화 | 20% | TPO 컷 + UGC + 일본 정서 카피 |
| 프로모션 설계 | 20% | 쿠폰·타임세일·세트 유기적 동선 |
| 일관성 | 15% | 컬러·폰트·레이아웃 가이드 일관 |

`rubric_skincare.csv` 예시:
```csv
shop_id,thumbnail,shop_main,localization,promo_design,consistency,scorer,note
biohealboh_official,4,3,4,4,5,kang,
anua,5,5,5,4,5,kang,
```

## 데이터 한계 (실측 검증 2026-06 기준)
- **리뷰수 999 상한**: 미니샵이 1000건 이상을 `999+`로 표기 → 히어로 상품 리뷰볼륨·Top5파워가 과소집계. 정확값은 상품 상세 페이지 필요(미구현).
- **추정매출**: 2일째 스냅샷부터(차분 기반). 1일차 수집만으로는 공란.
- **디자인 루브릭**: 수기 채점 단계(`rubric_{group}.csv` 또는 `design_scores`). 미채점 시 리포트에서 자동 생략.
- **미출시(COMING SOON) 상품**은 placeholder 가격이라 수집에서 제외. 가격 100만엔 초과는 파싱오류로 폐기.
- 팔로워·만족도·등급·가격은 정확. 리뷰 기반 지표만 위 상한 영향.
- **상세페이지 리뷰수 미사용**: `/g/{code}` 상세페이지의 `レビュー N`은 상품별이 아니라 **샵 누적 리뷰수**(실시간 증가)라 999-캡 보정에 못 씀 → `product_details.review_count_detail`은 미저장.
- **상세컷·컨셉**(`--details` + `vision.py`): 상세 디자인컷은 `GoodsDetailInfo` iframe의 `gdetail.image-qoo10.jp` 이미지(키 큰 것 우선). 비전 분석은 컨셉이 자주 안 변하므로 일일 cron이 아닌 **온디맨드/주간** 실행 권장.

## 주의
- 매출 추정은 2일째 스냅샷부터 가능(차분 기반), ±30~50% 오차 — **샵 간 상대 비교** 용도.
- Qoo10 DOM 변경 시 `scraper.py`의 정규식/셀렉터 보정 필요(`--debug` 우선).
- 디자인 루브릭은 2인 교차 채점으로 편향 완화 권장(샵별 평균 병합).
- 수집 데이터·이미지는 내부 분석 용도로만 사용(저작권·약관 고려). 요청은 일 1회 권장.
- 구버전 `qoo10.db`는 `connect()`가 자동 마이그레이션(파생 컬럼 ALTER)하지만, 샵 스냅샷은 재수집 필요.
