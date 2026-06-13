"""Qoo10.jp 상점 페이지 수집기 (Playwright).

- 상점 페이지를 렌더링해 상품 목록(코드/이름/가격/리뷰수)을 추출
- scrape_shop_full(): 단일 세션에서 상품 + 샵 헤더 스냅샷 + 이미지까지 수집
  (경쟁사 비교분석 파이프라인 collect.py 가 사용)
- --debug 모드: 페이지가 호출하는 XHR(JSON) 엔드포인트를 캡처해 출력
  → 안정적인 내부 API가 식별되면 이후 JSON 직접 파싱으로 전환 가능

주의: Qoo10 DOM은 변경될 수 있어 셀렉터/정규식은 후보를 복수 등록.
첫 실행 시 --debug 로 실제 구조를 확인하고 필요 시 보강하세요.
"""
import asyncio
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import date

from playwright.async_api import async_playwright

SHOP_URL = "https://www.qoo10.jp/shop/biohealboh_official"

# 셀렉터 후보 (위에서부터 순서대로 시도)
SELECTORS = {
    "item": ["div.shop_item", "li[data-goods-no]", "div[class*='goods_item']", "a[href*='/g/']"],
    "name": ["[class*='tit']", "[class*='name']", "img[alt]"],
    "price": ["[class*='prc'] strong", "[class*='price']"],
    "review": ["[class*='review']", "[class*='rv_cnt']"],
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# 상품명 분류 키워드 (파생 필드용)
SET_KW = ("セット", "企画", "SET", "set")
JP_LIMITED_KW = ("日本限定", "日本先行")
MEGAWARI_KW = ("メガ割", "メガポ", "メガ割り")


@dataclass
class Item:
    goods_code: str
    name: str
    url: str
    price: int | None = None
    list_price: int | None = None
    review_count: int | None = None
    rating: float | None = None
    sold_count: int | None = None


@dataclass
class ShopCapture:
    """샵 1곳의 단일 세션 수집 결과."""
    items: list = field(default_factory=list)        # list[Item]
    snapshot: dict = field(default_factory=dict)     # shop_snapshots 행
    assets: list = field(default_factory=list)       # image_assets 행


def _num(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"[\d,]+", text)
    return int(m.group().replace(",", "")) if m else None


def _first(pattern: str, text: str) -> int | None:
    """텍스트에서 패턴 첫 매치(그룹1)를 정수로 반환."""
    m = re.search(pattern, text)
    return _num(m.group(1)) if m else None


def _fpct(pattern: str, text: str) -> float | None:
    """텍스트에서 패턴 첫 매치(그룹1)를 실수로 반환."""
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except (ValueError, IndexError):
        return None


# ── 상품 분류 파생 ─────────────────────────────────────────────────────────
def derive_product_fields(name: str, price: int | None, list_price: int | None) -> dict:
    """상품명·가격으로 is_set / is_jp_limited / discount_pct 파생."""
    nm = name or ""
    is_set = int(any(k in nm for k in SET_KW))
    is_jp_limited = int(any(k in nm for k in JP_LIMITED_KW))
    discount_pct = None
    if price and list_price and list_price > 0 and price <= list_price:
        discount_pct = round((list_price - price) / list_price, 4)
    return {"is_set": is_set, "is_jp_limited": is_jp_limited, "discount_pct": discount_pct}


def is_megawari(name: str) -> bool:
    return any(k in (name or "") for k in MEGAWARI_KW)


# ── 페이지 로딩/상품 추출 (scrape_shop / scrape_shop_full 공용) ──────────────
async def _load_all(page, rounds: int = 10) -> None:
    """lazy-load 상품을 위해 스크롤."""
    for _ in range(rounds):
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(800)


async def _extract_cards(page) -> list[dict]:
    """미니샵 상품 목록을 카드(DIV.item) 단위로 추출.

    실제 DOM 구조(2026-06 기준):
      - 카드 = div.item, 상품 앵커 = a.quick (href=/item/{슬러그}/{code})
      - 가격 = 'N円' (정가 → 판매가 순), 배송비 'Shipping rate/送料'는 제외
      - 리뷰 = 'レビュー (NNN)' / '(999+)'
      - 타임세일 = 'N%↓' / 'Time sale', 메가와리 = 'メガ割'
    """
    return await page.evaluate(r"""() => {
        // 리뷰수는 hover 오버레이의 OpenQuickReview(code,...) 링크에 있음 → code별 매핑
        // 주의: 미니샵 표기가 '999+' 라 1000건 이상은 999로 캡됨(히어로 상품 과소집계)
        const reviewByCode = {};
        for (const a of document.querySelectorAll("a[onclick*='OpenQuickReview']")) {
            const mc = (a.getAttribute('onclick') || '').match(/OpenQuickReview\(\s*(\d{6,})/);
            if (!mc) continue;
            const mt = (a.innerText || '').match(/([\d,]+)/);   // '(999+)' → 999
            if (mt) reviewByCode[mc[1]] = parseInt(mt[1].replace(/,/g, ''), 10);
        }
        const cards = [...document.querySelectorAll('div.item')]
            .filter(c => c.querySelector("a.quick, a[href*='/item/']"));
        const out = [];
        const seen = new Set();
        for (const card of cards) {
            const a = card.querySelector("a.quick, a[href*='/item/']");
            if (!a) continue;
            const code = (a.href.match(/\/(\d{6,})(?:\?|\/|$)/) || [])[1];
            if (!code || seen.has(code)) continue;
            seen.add(code);
            let name = '';
            try { name = decodeURIComponent((a.href.match(/\/item\/([^/]+)\//) || [])[1] || '')
                          .replace(/-/g, ' ').trim(); } catch (e) {}
            const txt = card.innerText || '';
            // 미출시('COMING SOON') 상품은 placeholder 가격(예: 9499만엔)이라 제외
            if (/COMING\s*SOON/i.test(name) || /COMING\s*SOON/i.test(txt)) continue;
            // 배송비 라인 제외 후 'N円' 추출(정가→판매가 순), 비현실 고가는 파싱오류로 제거
            const cleaned = txt.split('\n').filter(l => !/Shipping|送料/.test(l)).join(' ');
            const prices = (cleaned.match(/([\d,]+)\s*円/g) || [])
                .map(s => parseInt(s.replace(/[^\d]/g, ''), 10))
                .filter(n => n > 0 && n <= 1000000);
            out.push({
                code, name, prices,
                review: code in reviewByCode ? reviewByCode[code] : null,
                has_timesale: /Time\s*sale|タイムセール/i.test(txt),
                has_megawari: /メガ割|メガポ/.test(txt),
            });
        }
        return out;
    }""")


def _cards_to_items(cards: list[dict]) -> dict[str, Item]:
    """추출 카드 → Item. 가격은 [정가, 판매가] 순으로 해석."""
    items: dict[str, Item] = {}
    for c in cards:
        prices = c.get("prices") or []
        if len(prices) >= 2:
            list_price, price = prices[0], prices[1]
            if price > list_price:           # 순서가 뒤집힌 예외 방어
                list_price, price = price, list_price
        elif prices:
            price, list_price = prices[0], None
        else:
            price = list_price = None
        items[c["code"]] = Item(
            goods_code=c["code"],
            name=(c.get("name") or "")[:200],
            url=f"https://www.qoo10.jp/g/{c['code']}",
            price=price, list_price=list_price,
            review_count=c.get("review"))
    return items


async def _extract_items(page) -> dict[str, Item]:
    """하위호환 래퍼 (run.py / scrape_shop 용)."""
    return _cards_to_items(await _extract_cards(page))


# ── 샵 헤더 스냅샷 파싱 ─────────────────────────────────────────────────────
async def parse_shop_snapshot(page, cards: list[dict]) -> dict:
    """샵 헤더/프로모션 영역 + 카드 메타에서 샵 레벨 지표 추출.

    헤더 텍스트(만족도·팔로워·상품수)는 정규식, 쿠폰은 .tit 요소,
    타임세일·메가와리는 카드 메타 집계. 값이 없으면 None.
    """
    body = await page.inner_text("body")

    # 판매자 등급: POWER/PREMIUM 등 등급 아이콘 alt·src ('by Power grade' 텍스트도 보조)
    grade = None
    metas = await page.eval_on_selector_all(
        "img", "els => els.map(im => ((im.alt||'') + ' ' + (im.src||'')).toUpperCase())")
    blob = " ".join(metas) + " " + body.upper()
    for token in ("PREMIUM", "POWER", "BIG", "GOOD", "NEW"):
        if token in blob:
            grade = token
            break

    # 만족도: 헤더의 'NN%' (フォロワー 직전) → 보조로 '満足'
    satisfaction = (_fpct(r"(\d{1,3}(?:\.\d)?)\s*%\s*\n?\s*フォロワー", body)
                    or _fpct(r"満足[度]?\D{0,6}(\d{1,3}(?:\.\d)?)\s*%", body))
    follower = _first(r"フォロワー\D{0,3}([\d,]+)", body)
    product_count = (_first(r"全て\s*の?\s*商品\s*[（(]\s*([\d,]+)", body)
                     or _first(r"商品\s*[（(]\s*([\d,]+)\s*[)）]", body))

    # 쿠폰: .tit 요소 중 'クーポン' 포함 (예: '【1000円OFF】メガ割クーポン')
    titles = await page.eval_on_selector_all(
        ".tit", "els => els.map(e => (e.textContent||'').trim())")
    coupon_titles = [t for t in titles if "クーポン" in t]
    yen_off = [int(m.group(1).replace(",", ""))
               for t in coupon_titles for m in [re.search(r"([\d,]+)\s*円\s*OFF", t)] if m]
    pct_off = [int(m.group(1))
               for t in coupon_titles for m in [re.search(r"(\d+)\s*%\s*OFF", t)] if m]
    coupon_max_off = None
    if yen_off:
        coupon_max_off = f"¥{max(yen_off)}"
    elif pct_off:
        coupon_max_off = f"{max(pct_off)}%"
    min_spend = re.search(r"([\d,]+)\s*円\s*以上", body)
    coupon_min_spend = f"¥{min_spend.group(1)}" if min_spend else None

    # 타임세일: 퍼센트는 오버레이 '.ts em'(예: '18%↓')에만 있어 셀렉터로 직접 조회
    ts_texts = await page.eval_on_selector_all(
        ".ts em, [class*='ts'] em", "els => els.map(e => (e.textContent||'').trim())")
    ts_pcts = [int(m.group(1)) for t in ts_texts for m in [re.search(r"(\d+)\s*%", t)] if m]
    timesale_count = sum(1 for c in cards if c.get("has_timesale")) or len(ts_pcts)
    timesale_avg_off = round(sum(ts_pcts) / len(ts_pcts), 1) if ts_pcts else None
    megawari = sum(1 for c in cards if c.get("has_megawari"))

    return {
        "seller_grade": grade,
        "satisfaction_pct": satisfaction,
        "follower_count": follower,
        "product_count": product_count or (len(cards) or None),
        "coupon_count": len(coupon_titles) or None,
        "coupon_max_off": coupon_max_off,
        "coupon_min_spend": coupon_min_spend,
        "timesale_count": timesale_count or None,
        "timesale_avg_off": timesale_avg_off,
        "megawari_sku_count": megawari or None,
    }


# ── 진입 함수 ──────────────────────────────────────────────────────────────
async def scrape_shop(url: str = SHOP_URL, debug: bool = False) -> list[Item]:
    """상품 목록만 수집 (run.py 하위호환)."""
    xhr_log = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=UA, locale="ja-JP")
        if debug:
            page.on("response", lambda r: xhr_log.append((r.status, r.url))
                    if r.request.resource_type in ("xhr", "fetch") else None)
        # networkidle 은 광고·트래킹으로 안 잡혀 domcontentloaded + 명시 대기 사용
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)
        await _load_all(page)
        items = await _extract_items(page)
        if debug:
            print("=== 캡처된 XHR/Fetch (내부 API 후보) ===")
            for status, u in xhr_log[:60]:
                print(status, u)
        await browser.close()
    return list(items.values())


async def scrape_shop_full(shop_id: str, url: str, capture_images: bool = True,
                           debug: bool = False) -> ShopCapture:
    """단일 세션에서 상품 + 샵 스냅샷 + 이미지까지 수집 (collect.py 용)."""
    import images  # 지연 import (이미지 미사용 경로의 비용 회피)

    xhr_log = []
    cap = ShopCapture()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=UA, locale="ja-JP")
        if debug:
            page.on("response", lambda r: xhr_log.append((r.status, r.url))
                    if r.request.resource_type in ("xhr", "fetch") else None)

        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)
        await _load_all(page)

        cards = await _extract_cards(page)
        cap.items = list(_cards_to_items(cards).values())
        cap.snapshot = await parse_shop_snapshot(page, cards)

        if capture_images:
            cap.assets = await images.capture_all(page, shop_id, date.today().isoformat())

        if debug:
            print("=== 캡처된 XHR/Fetch (내부 API 후보) ===")
            for status, u in xhr_log[:60]:
                print(status, u)
        await browser.close()
    return cap


# ── 상품 상세페이지 수집 (2차 강화) ─────────────────────────────────────────
DETAIL_URL = "https://www.qoo10.jp/g/{code}"


async def _extract_detail(page, code: str) -> dict:
    """상세페이지에서 상세컷 URL + 비-캡 리뷰수·브랜드 파싱.

    실측(2026-06):
      - 상세 디자인컷은 GoodsDetailInfo.aspx iframe 내부 'gdetail.image-qoo10.jp' 이미지.
        텍스트가 거의 없는 이미지 기반이라 OCR/비전 분석 대상. 키 큰 것 우선.
      - 브랜드는 타이틀 '[Qoo10] {브랜드} …'.
      - 주의: 상세페이지의 'レビュー N'·#tab_review 수치는 **샵 누적 리뷰수**(분당 증가)
        이지 상품별 값이 아니다 → 999-캡 보정용으로 못 씀. review_count_detail 미저장.
    """
    review_detail = None   # 페이지에 상품별 비-캡 리뷰수 없음(샵 총계뿐) → 저장 안 함
    title = await page.title()
    mb = re.search(r"\]\s*([^\s:：【]+)", title)   # '[Qoo10] アヌア …' → 'アヌア'
    brand = mb.group(1).strip() if mb else None

    # 상세 iframe 이미지 (없으면 메인 페이지 gdetail 이미지로 폴백)
    detail_urls: list[dict] = []
    for f in page.frames:
        if "GoodsDetailInfo" in (f.url or ""):
            try:
                await f.wait_for_load_state("domcontentloaded", timeout=10_000)
            except Exception:
                pass
            detail_urls = await f.evaluate(r"""() => {
                const out = [];
                for (const im of document.querySelectorAll('img')) {
                    const s = im.currentSrc || im.src || im.getAttribute('data-src') || '';
                    const w = im.naturalWidth || im.width || 0;
                    const h = im.naturalHeight || im.height || 0;
                    if (!s || !/gdetail\.image-qoo10/.test(s) || w < 500) continue;
                    out.push({src: s, h});
                }
                return out;
            }""")
            break

    # 키 큰 상세컷(텍스트·소구점 밀도 높음) 우선 정렬
    detail_urls.sort(key=lambda d: -(d.get("h") or 0))
    urls = [d["src"] for d in detail_urls]

    # 옵션 수(인벤토리 썸네일 개수) — 참고 지표
    try:
        option_count = await page.eval_on_selector_all(
            "[id^='Img_content_inventory_']", "els => els.length") or None
    except Exception:
        option_count = None

    return {"brand": brand, "review_count_detail": review_detail,
            "option_count": option_count, "_urls": urls}


async def scrape_shop_details(shop_id: str, codes: list[str], wait_sec: int = 5,
                              detail_img_limit: int = 6, debug: bool = False) -> list[dict]:
    """샵의 상위 상품 코드 목록을 받아 상세페이지를 순회 수집.

    반환: [{goods_code, detail:{brand,review_count_detail,option_count,detail_img_count}, assets:[...]}]
    상품 간 wait_sec 대기(매너). 실패 상품은 스킵 후 계속.
    """
    import images  # 지연 import

    results: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=UA, locale="ja-JP")
        for i, code in enumerate(codes):
            try:
                await page.goto(DETAIL_URL.format(code=code),
                                wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(2500)
                for _ in range(12):                    # 상세 iframe lazy-load
                    await page.mouse.wheel(0, 3000)
                    await page.wait_for_timeout(400)

                det = await _extract_detail(page, code)
                urls = det.pop("_urls")
                assets = await images.download_detail_images(
                    page, shop_id, code, urls, limit=detail_img_limit)
                det["detail_img_count"] = len(assets)
                results.append({"goods_code": code, "detail": det, "assets": assets})
                if debug:
                    print(f"    [{code}] 상세컷 {len(assets)}개 · 리뷰(상세)="
                          f"{det['review_count_detail']} · brand={det['brand']}")
            except Exception as e:
                print(f"    [{code}] 상세 수집 실패: {e} (계속)")
            if i < len(codes) - 1:
                await page.wait_for_timeout(wait_sec * 1000)
        await browser.close()
    return results


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    # 상세페이지 단독 점검:  python scraper.py --detail 945527932
    if "--detail" in sys.argv:
        code = sys.argv[sys.argv.index("--detail") + 1]
        out = asyncio.run(scrape_shop_details("_test", [code], wait_sec=0, debug=True))
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        result = asyncio.run(scrape_shop(debug=debug))
        print(json.dumps([asdict(i) for i in result], ensure_ascii=False, indent=2))
        print(f"\n총 {len(result)}개 상품 수집", file=sys.stderr)
