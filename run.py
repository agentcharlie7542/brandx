"""일일 실행 진입점: 수집(전 상점) → DB 적재 → 추정 리포트 CSV.

사용:
  python run.py                 # 전체 상점 수집 + 적재 + 리포트
  python run.py --debug         # XHR 엔드포인트 캡처 출력 포함
  python run.py --shop colorgram   # 특정 상점만 (shops.py의 shop_id)

수집 대상은 shops.py 의 SHOPS 에서 관리.
"""
import asyncio
import sys
from dataclasses import asdict
from pathlib import Path

from db import connect, upsert_snapshot
from estimator import estimate, summary
from rakuten import scrape_rakuten_shop
from scraper import scrape_shop
from shops import SHOPS

OUT = Path(__file__).parent / "reports"


async def collect(shop: dict, debug: bool) -> list:
    if shop["platform"] == "rakuten":
        return await scrape_rakuten_shop(
            shop["shop_id"], sid=shop.get("rakuten_sid"),
            shop_url=shop["url"], debug=debug)
    return await scrape_shop(url=shop["url"], debug=debug)


def main():
    debug = "--debug" in sys.argv
    only = sys.argv[sys.argv.index("--shop") + 1] if "--shop" in sys.argv else None

    conn = connect()
    total = 0
    for shop in SHOPS:
        if only and shop["shop_id"] != only:
            continue
        print(f"--- {shop['name']} ({shop['platform']}) ---")
        try:
            items = asyncio.run(collect(shop, debug))
        except Exception as e:
            print(f"  수집 실패: {e} (다음 상점 계속)")
            continue
        print(f"  수집: {len(items)}개 상품")
        for it in items:
            row = asdict(it)
            row.setdefault("list_price", None)
            row["platform"] = shop["platform"]
            row["shop_id"] = shop["shop_id"]
            upsert_snapshot(conn, row)
        conn.commit()
        total += len(items)
    print(f"DB 적재 완료 (총 {total}개)")

    df = estimate()
    if not df.empty and df["new_reviews"].notna().any():
        OUT.mkdir(exist_ok=True)
        rep = summary(df)
        path = OUT / "sales_estimate.csv"
        rep.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"리포트 저장: {path}")
    else:
        print("리포트는 2일째 스냅샷부터 생성됩니다(차분 필요).")


if __name__ == "__main__":
    main()
