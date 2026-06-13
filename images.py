"""이미지 수집 (루브릭 채점·PPTX 갤러리용).

이미 로드된 Playwright `page` 를 받아 캡처/다운로드만 수행하고
asset 메타(dict 리스트)를 반환한다. DB 적재는 collect.py 가 담당.

수집물:
  - thumb  : 상품 목록 대표 이미지 → images/{shop_id}/thumb_{goods_code}.jpg
  - banner : 샵 상단 배너 이미지   → images/{shop_id}/banner_{n}.jpg
  - shoptop: 샵 톱 풀페이지 캡처    → images/{shop_id}/shoptop_{date}.png

저장 경로는 프로젝트 루트 기준 상대경로 문자열로 반환(이식성).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent
IMAGES_DIR = ROOT / "images"

THUMB_LIMIT = 40   # 샵당 썸네일 최대 다운로드 수 (매너)
BANNER_LIMIT = 3


def _shop_dir(shop_id: str) -> Path:
    d = IMAGES_DIR / shop_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rel(path: Path) -> str:
    """프로젝트 루트 기준 상대경로(POSIX) 문자열."""
    return path.relative_to(ROOT).as_posix()


async def _download(page, url: str, dest: Path) -> bool:
    """page 컨텍스트로 이미지 바이트를 받아 dest 에 저장. 성공 여부 반환."""
    if not url or url.startswith("data:"):
        return False
    try:
        resp = await page.context.request.get(url, timeout=30_000)
        if not resp.ok:
            return False
        body = await resp.body()
        if len(body) < 512:  # 1x1 placeholder 등 방어
            return False
        dest.write_bytes(body)
        return True
    except Exception:
        return False


async def capture_shoptop(page, shop_id: str, date: str) -> list[dict]:
    """샵 톱 풀페이지 스크린샷."""
    dest = _shop_dir(shop_id) / f"shoptop_{date}.png"
    try:
        await page.screenshot(path=str(dest), full_page=True)
    except Exception:
        return []
    return [{"asset_type": "shoptop", "goods_code": None, "path": _rel(dest)}]


async def capture_banners(page, shop_id: str, limit: int = BANNER_LIMIT) -> list[dict]:
    """샵 상단 배너 이미지 다운로드. 페이지 상단 영역의 큰 img 우선."""
    srcs = await page.eval_on_selector_all(
        "img",
        """els => els
            .filter(im => (im.naturalWidth || im.width || 0) >= 600)  // 큰 배너만
            .slice(0, 12)
            .map(im => im.currentSrc || im.src || im.getAttribute('data-src') || '')""",
    )
    assets = []
    seen: set[str] = set()
    n = 0
    for src in srcs:
        if not src or src in seen:
            continue
        seen.add(src)
        dest = _shop_dir(shop_id) / f"banner_{n}.jpg"
        if await _download(page, src, dest):
            assets.append({"asset_type": "banner", "goods_code": None, "path": _rel(dest)})
            n += 1
            if n >= limit:
                break
    return assets


async def capture_thumbnails(page, shop_id: str, limit: int = THUMB_LIMIT) -> list[dict]:
    """상품 목록 대표 썸네일 다운로드. /g/{code} 앵커 내부 img 기준 매핑."""
    pairs = await page.eval_on_selector_all(
        "a[href*='/g/']",
        """els => els.map(a => {
            const im = a.querySelector('img') ||
                       a.closest('li,div')?.querySelector('img');
            return {
                href: a.href,
                src: im ? (im.currentSrc || im.src || im.getAttribute('data-src') || '') : ''
            };
        })""",
    )
    assets: list[dict] = []
    seen: set[str] = set()
    for pr in pairs:
        m = re.search(r"/g/(\d+)", pr["href"] or "")
        if not m:
            continue
        code = m.group(1)
        if code in seen or not pr["src"]:
            continue
        seen.add(code)
        dest = _shop_dir(shop_id) / f"thumb_{code}.jpg"
        if await _download(page, pr["src"], dest):
            assets.append({"asset_type": "thumb", "goods_code": code, "path": _rel(dest)})
        if len(assets) >= limit:
            break
    return assets


async def capture_hero_banner(page, shop_id: str, limit: int = 3) -> list[dict]:
    """샵 메인 히어로 배너 정밀 추출.

    조잡한 capture_banners('폭 600px↑ 아무 이미지')와 달리, 미니샵이 실제로
    디자인해 올린 영역만 타깃:
      1) 샵 헤더 배너 바  : img[id*='minishop_banner_image']
      2) 샵 톱 메인 비주얼: #...minishop_html 컨테이너의 상단 대형 이미지
    """
    srcs = await page.evaluate(r"""() => {
        const out = [];
        const seen = new Set();
        const push = (im) => {
            const s = im.currentSrc || im.src || im.getAttribute('data-src') || '';
            const w = im.naturalWidth || im.width || 0;
            if (!s || seen.has(s) || w < 500) return;
            seen.add(s);
            const r = im.getBoundingClientRect();
            out.push({src: s, top: Math.round(r.top + window.scrollY), w});
        };
        // 1) 헤더 배너 바
        document.querySelectorAll("img[id*='minishop_banner_image'], .sec_bnnr img").forEach(push);
        // 2) 미니샵 메인 영역 대형 비주얼
        document.querySelectorAll("[id*='minishop_html'] img, [id*='minishop'] img").forEach(push);
        // 위에서부터(메인 히어로 우선)
        return out.sort((a, b) => a.top - b.top).map(o => o.src);
    }""")
    assets: list[dict] = []
    seen: set[str] = set()
    n = 0
    for src in srcs:
        if not src or src in seen:
            continue
        seen.add(src)
        dest = _shop_dir(shop_id) / f"hero_{n}.jpg"
        if await _download(page, src, dest):
            assets.append({"asset_type": "hero", "goods_code": None, "path": _rel(dest)})
            n += 1
            if n >= limit:
                break
    return assets


async def download_detail_images(page, shop_id: str, code: str, urls: list[str],
                                 limit: int = 6) -> list[dict]:
    """상품 상세컷(성공 디자인 배너) 다운로드 → detail_{code}_{n}.jpg.

    urls 는 호출부(scraper)가 상세 iframe에서 추출·정렬(키 큰 것 우선)해 전달.
    """
    assets: list[dict] = []
    n = 0
    seen: set[str] = set()
    for src in urls:
        if not src or src in seen:
            continue
        seen.add(src)
        dest = _shop_dir(shop_id) / f"detail_{code}_{n}.jpg"
        if await _download(page, src, dest):
            assets.append({"asset_type": "detail", "goods_code": code, "path": _rel(dest)})
            n += 1
            if n >= limit:
                break
    return assets


async def capture_all(page, shop_id: str, date: str) -> list[dict]:
    """샵 1곳의 전체 이미지 수집 (shoptop → hero → banner → thumb 순)."""
    assets: list[dict] = []
    assets += await capture_shoptop(page, shop_id, date)
    assets += await capture_hero_banner(page, shop_id)
    assets += await capture_banners(page, shop_id)
    assets += await capture_thumbnails(page, shop_id)
    return assets
