"""경쟁사 비교분석 그룹 설정.

하나의 그룹 = {자사 샵 N개 + 경쟁사 샵 M개} 묶음.
collect/score/report 가 모두 이 설정을 단일 진실 원천으로 사용한다.

샵 식별자(shop_id)는 Qoo10 샵 URL 슬러그:
    https://www.qoo10.jp/shop/{shop_id}

그룹은 자유롭게 추가 가능 (향후 타 브랜드·타 카테고리 재사용).
표시명(name)을 따로 주고 싶으면 shop_id 대신 dict 로도 줄 수 있다:
    "own": [{"shop_id": "biohealboh_official", "name": "바이오힐보"}]
"""
from __future__ import annotations

QOO10_SHOP_URL = "https://www.qoo10.jp/shop/{shop_id}"

GROUPS: dict[str, dict] = {
    "skincare": {   # 기초 스킨케어 — 자사: 바이오힐보
        "label": "기초 스킨케어",
        "own":  ["biohealboh_official"],
        "competitors": ["anua", "vtcosmetics", "skin1004japan", "skinnlab", "dalba"],
    },
    "makeup": {     # 색조 포인트 — 자사: 웨이크메이크, 컬러그램
        "label": "색조 메이크업",
        "own":  ["wakemake_official", "colorgram"],
        "competitors": ["lakaofficial", "fwee", "ROMAND", "milktouch", "amuse"],
    },
}


def _normalize(entry: str | dict) -> dict:
    """shop_id 문자열 또는 dict 를 표준 샵 레코드로 변환."""
    if isinstance(entry, str):
        shop_id, name = entry, entry
    else:
        shop_id = entry["shop_id"]
        name = entry.get("name", shop_id)
    return {
        "shop_id": shop_id,
        "name": name,
        "url": QOO10_SHOP_URL.format(shop_id=shop_id),
        "platform": "qoo10",
    }


def resolve_group(group: str) -> list[dict]:
    """그룹명 → 샵 레코드 리스트. 각 레코드에 role('own'|'competitor') 부여.

    그룹명 'all' 은 모든 그룹의 샵을 중복 제거해 반환.
    """
    if group == "all":
        seen: dict[str, dict] = {}
        for g in GROUPS:
            for rec in resolve_group(g):
                seen.setdefault(rec["shop_id"], rec)  # 첫 등장 role 유지
        return list(seen.values())

    if group not in GROUPS:
        raise KeyError(f"알 수 없는 그룹: {group!r} (사용 가능: {', '.join(GROUPS)})")

    cfg = GROUPS[group]
    shops: list[dict] = []
    for entry in cfg.get("own", []):
        rec = _normalize(entry)
        rec["role"] = "own"
        rec["group"] = group
        shops.append(rec)
    for entry in cfg.get("competitors", []):
        rec = _normalize(entry)
        rec["role"] = "competitor"
        rec["group"] = group
        shops.append(rec)
    return shops


def own_shop_ids(group: str) -> set[str]:
    """그룹의 자사 shop_id 집합 (스코어카드 자사 행 하이라이트용)."""
    return {s["shop_id"] for s in resolve_group(group) if s["role"] == "own"}


def group_label(group: str) -> str:
    return GROUPS.get(group, {}).get("label", group) if group != "all" else "전체 그룹"


if __name__ == "__main__":
    for g in list(GROUPS) + ["all"]:
        shops = resolve_group(g)
        print(f"[{g}] {group_label(g)} — {len(shops)}개 샵")
        for s in shops:
            print(f"  {s['role']:11} {s['shop_id']:22} {s['url']}")
