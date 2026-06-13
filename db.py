"""SQLite 스키마 및 적재 유틸.

기존(products/snapshots/reviews)에 경쟁사 비교분석용 테이블을 추가:
  - shop_snapshots : 샵 레벨 일별 스냅샷 (등급·만족도·팔로워·쿠폰·타임세일 …)
  - image_assets   : 수집 이미지 메타 (썸네일·배너·풀캡처)
  - design_scores  : 정성 디자인 루브릭 수기 채점

snapshots 에는 상품 파생 컬럼(is_set / is_jp_limited / discount_pct)을 추가.
구버전 DB 호환을 위해 connect() 시 멱등 ALTER 마이그레이션을 수행한다.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "qoo10.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    goods_code   TEXT PRIMARY KEY,   -- 큐텐: 숫자코드 / 라쿠텐: 'rk:{shop}:{itemcode}'
    name         TEXT,
    url          TEXT,
    platform     TEXT DEFAULT 'qoo10',  -- 'qoo10' | 'rakuten'
    shop_id      TEXT,                  -- 상점 식별자 (예: colorgram, biohealboh)
    first_seen   TEXT DEFAULT (date('now'))
);

-- 일별 스냅샷: 매출 추정의 원천 데이터 + 상품 분류 파생
CREATE TABLE IF NOT EXISTS snapshots (
    goods_code   TEXT,
    snap_date    TEXT,              -- YYYY-MM-DD
    price        INTEGER,           -- 엔(¥), 할인 적용가
    list_price   INTEGER,           -- 정가(있으면)
    review_count INTEGER,
    rating       REAL,
    sold_count   INTEGER,           -- '○個 販売' 배지 (없으면 NULL)
    is_set       INTEGER,           -- 파생: 세트/기획 상품 여부 (0/1)
    is_jp_limited INTEGER,          -- 파생: 일본 한정/선행 여부 (0/1)
    discount_pct REAL,              -- 파생: (정가-판매가)/정가
    PRIMARY KEY (goods_code, snap_date)
);

-- 리뷰 원본(작성일 백필용, 본문은 저작권 고려해 선택 저장)
CREATE TABLE IF NOT EXISTS reviews (
    goods_code   TEXT,
    review_id    TEXT,
    written_at   TEXT,
    rating       REAL,
    option_text  TEXT,
    PRIMARY KEY (goods_code, review_id)
);

-- 상품 상세페이지 수집 데이터 (2차 강화: /g/{code} 방문분)
CREATE TABLE IF NOT EXISTS product_details (
    goods_code         TEXT PRIMARY KEY,
    captured_at        TEXT,
    brand              TEXT,
    review_count_detail INTEGER,   -- 상세페이지 표기 총 리뷰수 (999+ 상한 없음)
    option_count       INTEGER,
    detail_img_count   INTEGER      -- 다운로드한 상세컷 수
);

-- 비전(Claude) 상세컷 분석 → 상품별 컨셉·소구점
CREATE TABLE IF NOT EXISTS product_concepts (
    goods_code      TEXT PRIMARY KEY,
    analyzed_at     TEXT,
    model           TEXT,
    concept         TEXT,
    selling_points  TEXT,   -- JSON 배열 문자열
    hero_copy       TEXT,
    target          TEXT,
    key_ingredients TEXT,   -- JSON 배열 문자열
    tone            TEXT,
    raw_json        TEXT
);

-- 샵 레벨 일별 스냅샷
CREATE TABLE IF NOT EXISTS shop_snapshots (
    shop_id          TEXT,
    snap_date        TEXT,
    seller_grade     TEXT,
    satisfaction_pct REAL,
    follower_count   INTEGER,
    product_count    INTEGER,
    coupon_count     INTEGER,
    coupon_max_off   TEXT,
    coupon_min_spend TEXT,
    timesale_count   INTEGER,
    timesale_avg_off REAL,
    megawari_sku_count INTEGER,
    PRIMARY KEY (shop_id, snap_date)
);

-- 수집 이미지 메타
CREATE TABLE IF NOT EXISTS image_assets (
    shop_id     TEXT,
    asset_type  TEXT,     -- 'thumb' | 'banner' | 'shoptop'
    goods_code  TEXT,     -- thumb일 때만
    path        TEXT,
    captured_at TEXT,
    PRIMARY KEY (shop_id, asset_type, path)
);

-- 정성 디자인 루브릭 (수기 입력)
CREATE TABLE IF NOT EXISTS design_scores (
    shop_id      TEXT,
    scored_at    TEXT,
    thumbnail    REAL,     -- 가중치 25%
    shop_main    REAL,     -- 20%
    localization REAL,     -- 20%
    promo_design REAL,     -- 20%
    consistency  REAL,     -- 15%
    scorer       TEXT,
    note         TEXT,
    PRIMARY KEY (shop_id, scored_at, scorer)
);
"""

# 구버전 DB(파생 컬럼 없는 snapshots) 호환용 멱등 마이그레이션
_MIGRATIONS = {
    "snapshots": [
        ("is_set", "INTEGER"),
        ("is_jp_limited", "INTEGER"),
        ("discount_pct", "REAL"),
    ],
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in _MIGRATIONS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


# ── 상품 스냅샷 ───────────────────────────────────────────────────────────
def upsert_snapshot(conn, row: dict):
    """상품 + 일별 스냅샷 적재. 파생 필드는 없으면 NULL 로 저장(run.py 하위호환)."""
    row.setdefault("platform", "qoo10")
    row.setdefault("shop_id", None)
    for k in ("list_price", "rating", "sold_count", "is_set", "is_jp_limited", "discount_pct"):
        row.setdefault(k, None)
    conn.execute(
        """INSERT INTO products(goods_code, name, url, platform, shop_id)
           VALUES(:goods_code, :name, :url, :platform, :shop_id)
           ON CONFLICT(goods_code) DO UPDATE SET name=:name, url=:url,
               platform=:platform, shop_id=:shop_id""",
        row,
    )
    conn.execute(
        """INSERT OR REPLACE INTO snapshots
           (goods_code, snap_date, price, list_price, review_count, rating, sold_count,
            is_set, is_jp_limited, discount_pct)
           VALUES (:goods_code, date('now'), :price, :list_price, :review_count, :rating,
                   :sold_count, :is_set, :is_jp_limited, :discount_pct)""",
        row,
    )


# ── 샵 스냅샷 ─────────────────────────────────────────────────────────────
_SHOP_FIELDS = (
    "seller_grade", "satisfaction_pct", "follower_count", "product_count",
    "coupon_count", "coupon_max_off", "coupon_min_spend",
    "timesale_count", "timesale_avg_off", "megawari_sku_count",
)


def upsert_shop_snapshot(conn, shop_id: str, row: dict):
    """샵 레벨 일별 스냅샷 적재 (당일 기준 upsert)."""
    payload = {"shop_id": shop_id}
    for f in _SHOP_FIELDS:
        payload[f] = row.get(f)
    conn.execute(
        f"""INSERT OR REPLACE INTO shop_snapshots
            (shop_id, snap_date, {", ".join(_SHOP_FIELDS)})
            VALUES (:shop_id, date('now'), {", ".join(":" + f for f in _SHOP_FIELDS)})""",
        payload,
    )


# ── 이미지 메타 ───────────────────────────────────────────────────────────
def upsert_image_asset(conn, shop_id: str, asset_type: str, path: str,
                       goods_code: str | None = None):
    conn.execute(
        """INSERT OR REPLACE INTO image_assets
           (shop_id, asset_type, goods_code, path, captured_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (shop_id, asset_type, goods_code, path),
    )


# ── 상품 상세 / 컨셉 ──────────────────────────────────────────────────────
_DETAIL_FIELDS = ("brand", "review_count_detail", "option_count", "detail_img_count")


def upsert_product_detail(conn, goods_code: str, row: dict):
    """상품 상세페이지 수집 데이터 적재 (당일 기준 upsert)."""
    payload = {"goods_code": goods_code}
    for f in _DETAIL_FIELDS:
        payload[f] = row.get(f)
    conn.execute(
        f"""INSERT OR REPLACE INTO product_details
            (goods_code, captured_at, {", ".join(_DETAIL_FIELDS)})
            VALUES (:goods_code, datetime('now'), {", ".join(":" + f for f in _DETAIL_FIELDS)})""",
        payload,
    )


_CONCEPT_FIELDS = ("model", "concept", "selling_points", "hero_copy",
                   "target", "key_ingredients", "tone", "raw_json")


def upsert_product_concept(conn, goods_code: str, row: dict):
    """비전 분석 결과(상품별 컨셉·소구점) 적재."""
    payload = {"goods_code": goods_code}
    for f in _CONCEPT_FIELDS:
        payload[f] = row.get(f)
    conn.execute(
        f"""INSERT OR REPLACE INTO product_concepts
            (goods_code, analyzed_at, {", ".join(_CONCEPT_FIELDS)})
            VALUES (:goods_code, datetime('now'), {", ".join(":" + f for f in _CONCEPT_FIELDS)})""",
        payload,
    )
