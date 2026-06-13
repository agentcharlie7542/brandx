"""수집 대상 상점 목록.

platform: "qoo10" | "rakuten"
- qoo10  : 상점 페이지를 Playwright로 렌더링해 /g/{code} 링크 기준 수집
- rakuten: 검색 페이지(sid 필터)를 우선 사용, 실패 시 샵 톱 페이지 폴백
"""

SHOPS = [
    {
        "platform": "qoo10",
        "shop_id": "biohealboh_official",
        "name": "바이오힐보 큐텐샵",
        "url": "https://www.qoo10.jp/shop/biohealboh_official",
    },
    {
        "platform": "qoo10",
        "shop_id": "wakemake_official",
        "name": "웨이크메이크 큐텐샵",
        "url": "https://www.qoo10.jp/shop/wakemake_official",
    },
    {
        "platform": "qoo10",
        "shop_id": "colorgram",
        "name": "컬러그램 큐텐샵",
        "url": "https://www.qoo10.jp/shop/colorgram",
    },
    {
        "platform": "rakuten",
        "shop_id": "biohealboh",
        "name": "바이오힐보 라쿠텐샵 (BIOHEAL BOH公式楽天市場店)",
        "url": "https://www.rakuten.co.jp/biohealboh/",
        "rakuten_sid": 429204,  # 楽天 shop ID (검색 필터·리뷰 페이지에 사용)
    },
]
