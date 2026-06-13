"""Rakuten 상점 수집기 (Playwright).

수집 전략 (순서대로 시도):
1. 검색 페이지: https://search.rakuten.co.jp/search/mall/?sid={sid}&p={page}
   - 상품명·가격·리뷰수·평점이 목록에 함께 노출되어 1회 요청으로 다수 확보
   - 페이지네이션(&p=N)으로 전 상품 순회
2. 폴백: 샵 톱 https://www.rakuten.co.jp/{shop_id}/
   - item.rakuten.co.jp/{shop_id}/{itemcode} 링크 기준 추출 (리뷰수는 미노출 가능)

goods_code 는 큐텐과 충돌하지 않도록 "rk:{shop_id}:{itemcode}" 로 네임스페이스.

주의: 첫 실행 시 --debug 로 실제 DOM 구조를 확인하고 정규식/셀렉터를 보정할 것.
"""
import asyncio
import json
import re
import sys

from playwright.async_api import async_playwright

from scraper import Item, UA, _first, _num

MAX_PAGES = 10  # 검색 페이지 최대 순회 수 (45개/페이지)


def _item_code(href: str, shop_id: str) -> str | None:
    m = re.search(rf"item\.rakuten\.co\.jp/{re.escape(shop_id)}/([^/?#]+)", href)
    return m.group(1) if m else None


async def _collect_anchors(page, shop_id: str) -> list[dict]:
    return await page.eval_on_selector_all(
        f"a[href*='item.rakuten.co.jp/{shop_id}/']",
        """els => els.map(a => ({
            href: a.href,
            text: (a.closest('[class*="searchresultitem"], [class*="content"], li, div')?.innerText
                   || a.innerText || '').slice(0, 600)
        }))""",
    )


def _parse_block(block: str) -> dict:
    """목록 블록 텍스트에서 가격·리뷰수·평점 휴리스틱 추출."""
    price = _first(r"([\d,]+)\s*円", block)
    review = _first(r"[（(]\s*([\d,]+)\s*件?[）)]", block) or _first(r"レビュー\s*([\d,]+)", block)
    rating = None
    m = re.search(r"([0-5]\.\d{1,2})\s*[（(]", block) or re.search(r"★\s*([0-5]\.\d{1,2})", block)
    if m:
        rating = float(m.group(1))
    name = next((ln.strip() for ln in block.split("\n") if len(ln.strip()) > 10), "")[:200]
    return {"price": price, "review": review, "rating": rating, "name": name}


async def scrape_rakuten_shop(shop_id: str, sid: int | None = None,
                              shop_url: str | None = None, debug: bool = False) -> list[Item]:
    items: dict[str, Item] = {}
    xhr_log = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=UA, locale="ja-JP")

        if debug:
            page.on("response", lambda r: xhr_log.append((r.status, r.url))
                    if r.request.resource_type in ("xhr", "fetch") else None)

        # 1) 검색 페이지 순회 (sid 필터)
        if sid:
            for pno in range(1, MAX_PAGES + 1):
                url = f"https://search.rakuten.co.jp/search/mall/?sid={sid}&p={pno}"
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(2500)
                anchors = await _collect_anchors(page, shop_id)
                before = len(items)
                for a in anchors:
                    code = _item_code(a["href"], shop_id)
                    if not code:
                        continue
                    parsed = _parse_block(a["text"])
                    key = f"rk:{shop_id}:{code}"
                    prev = items.get(key)
                    if prev is None or (prev.price is None and parsed["price"]):
                        items[key] = Item(
                            goods_code=key,
                            name=parsed["name"],
                            url=f"https://item.rakuten.co.jp/{shop_id}/{code}/",
                            price=parsed["price"],
                            review_count=parsed["review"],
                            rating=parsed["rating"],
                        )
                if len(items) == before:  # 신규 상품 없으면 마지막 페이지
                    break
                await page.wait_for_timeout(2000)  # 매너 대기

        # 2) 폴백: 샵 톱 페이지 (검색이 비었을 때)
        if not items and shop_url:
            await page.goto(shop_url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2500)
            for _ in range(8):
                await page.mouse.wheel(0, 2500)
                await page.wait_for_timeout(600)
            anchors = await _collect_anchors(page, shop_id)
            for a in anchors:
                code = _item_code(a["href"], shop_id)
                if not code:
                    continue
                parsed = _parse_block(a["text"])
                key = f"rk:{shop_id}:{code}"
                if key not in items:
                    items[key] = Item(
                        goods_code=key,
                        name=parsed["name"],
                        url=f"https://item.rakuten.co.jp/{shop_id}/{code}/",
                        price=parsed["price"],
                        review_count=parsed["review"],
                        rating=parsed["rating"],
                    )

        if debug:
            print("=== 캡처된 XHR/Fetch (내부 API 후보) ===")
            for status, u in xhr_log[:60]:
                print(status, u)

        await browser.close()

    return list(items.values())


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    result = asyncio.run(scrape_rakuten_shop(
        "biohealboh", sid=429204,
        shop_url="https://www.rakuten.co.jp/biohealboh/", debug=debug))
    from dataclasses import asdict
    print(json.dumps([asdict(i) for i in result], ensure_ascii=False, indent=2))
    print(f"\n총 {len(result)}개 상품 수집", file=sys.stderr)
