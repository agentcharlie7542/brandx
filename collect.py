"""경쟁사 비교분석 — 수집기 진입점.

그룹 단위로 샵을 순회하며 단일 세션(scrape_shop_full)으로
  - 상품 목록(+분류 파생)
  - 샵 레벨 스냅샷
  - 이미지(썸네일·배너·풀캡처)
를 수집해 SQLite 에 적재한다.

사용:
  python collect.py --group skincare          # 그룹 단위 수집 (일 1회 cron)
  python collect.py --group all               # 전 그룹
  python collect.py --group makeup --no-images # 이미지 제외(빠른 지표 갱신)
  python collect.py --group skincare --shop anua   # 특정 샵만
  python collect.py --group skincare --debug  # XHR 엔드포인트 캡처 출력

수집 매너: 샵 간 5초 이상 대기, 실패 샵은 스킵 후 계속(전체 중단 금지).
"""
import asyncio
import sys
import time
from dataclasses import asdict

from db import (connect, upsert_image_asset, upsert_product_detail,
                upsert_shop_snapshot, upsert_snapshot)
from scraper import derive_product_fields, scrape_shop_details, scrape_shop_full
from shops_groups import group_label, resolve_group

WAIT_SEC = 5     # 샵 간 대기(매너)
TOP_DEFAULT = 10  # --details 시 샵당 상세 수집 상품 수(리뷰 기준 상위)


def _arg(flag: str, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def persist(conn, shop: dict, cap) -> int:
    """단일 샵 수집 결과를 DB 에 적재. 적재 상품 수 반환."""
    shop_id = shop["shop_id"]

    # 1) 상품 + 스냅샷 (분류 파생 병합)
    for it in cap.items:
        row = asdict(it)
        row["platform"] = "qoo10"
        row["shop_id"] = shop_id
        row.update(derive_product_fields(it.name, it.price, it.list_price))
        upsert_snapshot(conn, row)

    # 2) 샵 레벨 스냅샷
    if cap.snapshot:
        upsert_shop_snapshot(conn, shop_id, cap.snapshot)

    # 3) 이미지 메타
    for a in cap.assets:
        upsert_image_asset(conn, shop_id, a["asset_type"], a["path"], a.get("goods_code"))

    conn.commit()
    return len(cap.items)


def top_codes(conn, shop_id: str, n: int) -> list[str]:
    """샵의 리뷰수 상위 N개 goods_code (베이스/히어로 상품).

    GROUP BY 로 다중 스냅샷 날짜의 중복을 제거(상품당 최대 리뷰수 기준).
    """
    rows = conn.execute(
        """SELECT s.goods_code FROM snapshots s
           JOIN products p ON p.goods_code = s.goods_code
           WHERE p.shop_id = ?
           GROUP BY s.goods_code
           ORDER BY COALESCE(MAX(s.review_count), 0) DESC, s.goods_code
           LIMIT ?""",
        (shop_id, n)).fetchall()
    return [r[0] for r in rows]


def persist_details(conn, results: list[dict]) -> int:
    """상세 수집 결과(상세 데이터 + 상세컷 asset) 적재. 적재 상품 수 반환."""
    shop_id_by_code = {}
    n = 0
    for r in results:
        code = r["goods_code"]
        upsert_product_detail(conn, code, r["detail"])
        for a in r["assets"]:
            upsert_image_asset(conn, a.get("shop_id") or shop_id_by_code.get(code),
                               a["asset_type"], a["path"], a.get("goods_code"))
        n += 1
    conn.commit()
    return n


def collect_details(conn, shop: dict, top_n: int, debug: bool = False) -> int:
    """단일 샵의 상위 상품 상세페이지 수집·적재."""
    sid = shop["shop_id"]
    codes = top_codes(conn, sid, top_n)
    if not codes:
        print(f"    상세 대상 없음(먼저 목록 수집 필요): {sid}")
        return 0
    print(f"    상세 수집 상위 {len(codes)}개 (리뷰 기준)…")
    results = asyncio.run(scrape_shop_details(sid, codes, wait_sec=WAIT_SEC, debug=debug))
    # asset에 shop_id 보강(images는 shop_id를 안 채워 반환)
    for r in results:
        for a in r["assets"]:
            a["shop_id"] = sid
    n_assets = sum(len(r["assets"]) for r in results)
    persist_details(conn, results)
    print(f"    → 상세 {len(results)}개 상품 · 상세컷 {n_assets}장 적재")
    return len(results)


def main():
    group = _arg("--group", "skincare")
    only = _arg("--shop")
    capture_images = "--no-images" not in sys.argv
    with_details = "--details" in sys.argv
    top_n = int(_arg("--top", TOP_DEFAULT))
    debug = "--debug" in sys.argv

    shops = resolve_group(group)
    if only:
        shops = [s for s in shops if s["shop_id"] == only]
    if not shops:
        print(f"수집 대상 샵 없음 (group={group}, shop={only})")
        return

    conn = connect()
    print(f"=== 그룹 '{group}' ({group_label(group)}) — {len(shops)}개 샵 / "
          f"이미지={'on' if capture_images else 'off'} / "
          f"상세={'on(top%d)' % top_n if with_details else 'off'} ===")

    total = 0
    detail_total = 0
    for i, shop in enumerate(shops):
        tag = f"[{shop['role']}]"
        print(f"--- {tag} {shop['name']} ({shop['shop_id']}) ---")
        try:
            cap = asyncio.run(scrape_shop_full(
                shop["shop_id"], shop["url"], capture_images=capture_images, debug=debug))
        except Exception as e:
            print(f"  수집 실패: {e} (다음 샵 계속)")
            continue
        n = persist(conn, shop, cap)
        total += n
        snap = cap.snapshot
        print(f"  상품 {n}개 · 이미지 {len(cap.assets)}개 · "
              f"등급={snap.get('seller_grade')} 만족도={snap.get('satisfaction_pct')} "
              f"팔로워={snap.get('follower_count')}")

        if with_details:
            try:
                detail_total += collect_details(conn, shop, top_n, debug=debug)
            except Exception as e:
                print(f"  상세 수집 실패: {e} (다음 샵 계속)")

        if i < len(shops) - 1:
            time.sleep(WAIT_SEC)  # 매너 대기

    msg = f"\n적재 완료: 총 {total}개 상품 / {len(shops)}개 샵 (group={group})"
    if with_details:
        msg += f" · 상세 {detail_total}개 상품"
    print(msg)


if __name__ == "__main__":
    main()
