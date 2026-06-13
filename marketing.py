"""마케팅 인텔리전스 — 톤앤매너 · 진행 이벤트/행사 · 인플루언서/IP 콜라보 정리.

데이터 출처:
  - 자동 채굴: 수집된 상품명(products)에서 コラボ 파트너·한정/기획/GIFT 키워드,
    shop_snapshots에서 쿠폰·타임세일·메가와리 지표 (재수집 불필요, 매 수집마다 갱신).
  - 정성(AI 시각분석): 샵 톱 캡처 기반 톤앤매너·메인 캠페인. TONE/HERO 상수에 큐레이션.
    ※ 이미지 배너는 alt가 없어 자동 추출 불가 → 캡처 육안 분석 결과를 명시적으로 기입.

산출:
  out/design_intelligence_{group}.md  — 상세 리포트(톤앤매너/이벤트/콜라보 표)
  out/collab_{group}.csv              — 콜라보 리스트(샵·파트너·상품)

사용:
  python marketing.py --group skincare
  python marketing.py --group makeup
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from db import connect
from shops_groups import group_label, own_shop_ids, resolve_group

OUT = Path(__file__).parent / "out"

EVENT_KW = ["限定", "日本限定", "先行", "GIFT", "プレゼント", "贈呈", "セット",
            "企画", "メガ割", "アワーズ", "1位", "先着"]

# 이미지 전용 배너라 상품명에 안 잡히는 IP 콜라보 (캡처 육안 확인분 보강)
IP_COLLAB = {
    "wakemake_official": ["HELLO KITTY (산리오 IP)"],
    "fwee": ["NAYEON / TWICE (포스터 증정)"],
}

# 캡처(샵 톱) 육안 분석 — 톤앤매너 + 현재 메인 캠페인 (AI 시각분석, 잠정)
TONE = {
    # skincare
    "biohealboh_official": {
        "tone": "퍼플＋레드 프리미엄. 베네핏 카피 구좌(#3Dクリーム 등) 정연, Qoo10 AWARDS 수상 배지로 소셜프루프.",
        "hero": "週末限定 人気クリーム3種特価(6/6~6/7) · Qoo10 AWARDS 2025 受賞ショップ",
    },
    "anua": {
        "tone": "파스텔 여름 일러스트＋일본풍 캐릭터. 정서적 스토리텔링, 브랜드 세계관 강함.",
        "hero": "真夏のスイート・ドロップ 일러스트 시즌캠페인 + 公式ショップ 요일별 세일 캘린더 + LIVE",
    },
    "vtcosmetics": {
        "tone": "아이돌 모델＋마스코트 일러스트. 고채도 활기, 쿠폰·세트 동선 강조(다소 산만).",
        "hero": "VTと過ごす癒しの夏 메가割 最大71%OFF + VTショップクーポン 10%(병용)",
    },
    "skin1004japan": {
        "tone": "스카이블루 프리미엄. 베네핏 태그(#鎮静/#バリア/#保湿), 카탈로그형 일관성 최상.",
        "hero": "ヒアルーTECAライン誕生(신라인) + センテラ 注目アイテム %OFF 그리드",
    },
    "skinnlab": {
        "tone": "블루＋핑크 타이포 히어로. 깔끔 미니멀, 쿠폰 설계 강점.",
        "hero": "mega wari + 계단식 쿠폰(1000↑50/3000↑150/5000↑350円) + 先着5,000名 스타트쿠폰",
    },
    "dalba": {
        "tone": "골드＋핑크 럭셔리. 이벤트·증정 밀도 최상(다소 과밀).",
        "hero": "678day 사은품(7,000円↑ 미스트 증정) + UV下地/ミスト 1+1 + 全商品無料発送",
    },
    # makeup
    "wakemake_official": {
        "tone": "핑크 Hello Kitty 콜라보. 레트로(平成ギャル) 트렌드, 일본 IP 현지화 최상.",
        "hero": "HELLO KITTY × 平成ギャルエディション(5/29~6/10) + 계단식쿠폰 + 콜라보 증정구좌",
    },
    "colorgram": {
        "tone": "Y2K 핑크 키치. 짱구(クレヨンしんちゃん) IP, 日本限定 캐릭터 굿즈.",
        "hero": "ギャルしんちゃん(짱구)コラボ コレクション 日本限定 Qoo10先行販売",
    },
    "lakaofficial": {
        "tone": "에디토리얼 패션. 미니멀 블랙/그레이 프리미엄, 젠더리스 무드.",
        "hero": "MEGAWARI ~57%OFF + 프로모션 캘린더(요일별 1日特価) + Shop Coupon(200円/10%)",
    },
    "fwee": {
        "tone": "블루/핑크 스크랩북. 발랄·경쾌, 세트 강조(다소 과밀).",
        "hero": "All Day Cushion 6月메가割 + NAYEON 포스터 증정 + 세트 45/41%OFF + 송료무료",
    },
    "ROMAND": {
        "tone": "누드/베이지 브랜드 일관성 최상. 모델 비주얼, 신컬러 런칭 스토리.",
        "hero": "豆乳カラーコレクション 신컬러 + ZO FRIENDS 콜라보 라인 + Qoo10先行発売",
    },
    "milktouch": {
        "tone": "핑크 하트. 모델 클로즈업, 깔끔 단순·일관.",
        "hero": "6月메가割 + 채널별 쿠폰(LIPS 3%/LINE 5%/メガ割 500円) + 하트 립 히어로",
    },
    "amuse": {
        "tone": "드리미 스카이블루. 모델, 라이브커머스, 정연한 혜택 구조.",
        "hero": "메가割 最大64%OFF + 쿠폰 3종(LIVE 포함) + 금액별 증정 + 日替わりイベント",
    },
}


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def _collab_partner(name: str) -> str | None:
    """상품명에서 'コラボ' 직전 파트너명 추출."""
    idx = name.find("コラボ")
    if idx < 0:
        return None
    before = name[:idx].strip()
    if not before:
        return None
    toks = before.split()
    partner = toks[-1]
    # 영문 2단어 브랜드(예: ZO FRIENDS) 보정
    if len(toks) >= 2 and toks[-1].isascii() and toks[-1].isupper() \
            and toks[-2].isascii() and toks[-2].isupper():
        partner = f"{toks[-2]} {toks[-1]}"
    # 노이즈 토큰 방어
    return None if partner in ("公式", "限定") else partner


def mine(group: str) -> dict:
    """그룹 샵별 콜라보·이벤트·프로모션 채굴."""
    conn = connect()
    shops = resolve_group(group)
    own = own_shop_ids(group)
    result = {}
    for s in shops:
        sid = s["shop_id"]
        names = [r[0] or "" for r in
                 conn.execute("SELECT name FROM products WHERE shop_id=?", (sid,))]
        # 콜라보(상품명) + IP(캡처)
        collabs = defaultdict(list)   # partner -> [상품명…]
        for nm in names:
            if "コラボ" in nm:
                p = _collab_partner(nm)
                if p:
                    collabs[p].append(nm)
        collab_list = [{"partner": p, "count": len(v), "sample": v[0]}
                       for p, v in sorted(collabs.items(), key=lambda x: -len(x[1]))]
        ip = IP_COLLAB.get(sid, [])
        # 이벤트 키워드 빈도
        kw = {k: sum(1 for nm in names if k in nm) for k in EVENT_KW}
        # 샵 스냅샷 프로모션
        snap = conn.execute(
            """SELECT seller_grade, satisfaction_pct, follower_count, coupon_count,
                      coupon_max_off, timesale_count, timesale_avg_off, megawari_sku_count
               FROM shop_snapshots WHERE shop_id=? ORDER BY snap_date DESC LIMIT 1""",
            (sid,)).fetchone()
        # 상세페이지 비전 분석 컨셉(있으면)
        concepts = []
        for cr in conn.execute(
                """SELECT p.name, c.concept, c.selling_points, c.hero_copy, c.target,
                          c.key_ingredients, c.tone
                   FROM product_concepts c JOIN products p ON p.goods_code=c.goods_code
                   WHERE p.shop_id=? ORDER BY p.name""", (sid,)):
            def _j(x):
                try:
                    return json.loads(x) if x else []
                except Exception:
                    return []
            concepts.append({
                "name": cr[0] or "", "concept": cr[1] or "",
                "selling_points": _j(cr[2]), "hero_copy": cr[3] or "",
                "target": cr[4] or "", "key_ingredients": _j(cr[5]), "tone": cr[6] or "",
            })
        result[sid] = {
            "name": s["name"], "role": s["role"], "is_own": sid in own,
            "sku": len(names), "collabs": collab_list, "ip_collabs": ip,
            "kw": kw, "snap": snap, "concepts": concepts,
            "tone": TONE.get(sid, {}).get("tone", "—"),
            "hero": TONE.get(sid, {}).get("hero", "—"),
        }
    return result


def write_reports(group: str, data: dict) -> tuple[Path, Path]:
    OUT.mkdir(exist_ok=True)
    L = []
    L.append(f"# 마케팅 인텔리전스 — {group_label(group)} ({group})\n")
    L.append("> 톤앤매너·메인 캠페인은 샵 톱 캡처 기반 **AI 시각분석(잠정)**, "
             "콜라보·이벤트 키워드는 수집 상품명 **자동 채굴**.\n")

    # 1) 톤앤매너 + 메인 캠페인
    L.append("\n## 1. 상점 톤앤매너 · 진행 메인 캠페인\n")
    L.append("| 샵 | 구분 | 톤앤매너 | 현재 메인 이벤트/행사 |")
    L.append("|---|---|---|---|")
    for sid, d in data.items():
        star = "★" if d["is_own"] else ""
        L.append(f"| {star}{sid} | {d['role']} | {d['tone']} | {d['hero']} |")

    # 2) 인플루언서/IP 콜라보 리스트
    L.append("\n## 2. 인플루언서 · IP 콜라보 리스트\n")
    L.append("| 샵 | 파트너 | 유형 | 상품수 | 대표 상품 |")
    L.append("|---|---|---|---|---|")
    any_collab = False
    for sid, d in data.items():
        star = "★" if d["is_own"] else ""
        for ip in d["ip_collabs"]:
            L.append(f"| {star}{sid} | {ip} | IP(배너) | – | – |")
            any_collab = True
        for c in d["collabs"]:
            L.append(f"| {star}{sid} | {c['partner']} | 인플루언서/IP | {c['count']} | {c['sample'][:46]} |")
            any_collab = True
    if not any_collab:
        L.append("| – | (콜라보 없음) | – | – | – |")

    # 3) 이벤트/행사 키워드 강도
    L.append("\n## 3. 이벤트·행사 강도 (상품명 태그 빈도)\n")
    head = "| 샵 | " + " | ".join(EVENT_KW) + " |"
    L.append(head)
    L.append("|" + "---|" * (len(EVENT_KW) + 1))
    for sid, d in data.items():
        star = "★" if d["is_own"] else ""
        cells = " | ".join(str(d["kw"][k]) for k in EVENT_KW)
        L.append(f"| {star}{sid} | {cells} |")

    # 4) 프로모션(쿠폰·타임세일·메가와리) 현황
    L.append("\n## 4. 프로모션 현황 (샵 스냅샷)\n")
    L.append("| 샵 | 등급 | 만족도 | 팔로워 | 쿠폰수 | 최대할인 | 타임세일 | 평균%↓ | 메가와리SKU |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for sid, d in data.items():
        star = "★" if d["is_own"] else ""
        s = d["snap"] or [None] * 8
        L.append(f"| {star}{sid} | {s[0]} | {s[1]} | {s[2]} | {s[3]} | {s[4]} | "
                 f"{s[5]} | {s[6]} | {s[7]} |")

    # 5) 시사점 (데이터 기반)
    L.append("\n## 5. 자사 vs 경쟁 시사점\n")

    def _partners(filt):
        out = []
        for sid, d in data.items():
            if filt(d):
                out += d["ip_collabs"] + [c["partner"] for c in d["collabs"]]
        return out
    own_p = _partners(lambda d: d["is_own"])
    comp_p = _partners(lambda d: not d["is_own"])
    own_ids = [sid for sid, d in data.items() if d["is_own"]]
    no_collab = [sid for sid, d in data.items()
                 if not d["is_own"] and not d["collabs"] and not d["ip_collabs"]]

    L.append(f"- **자사**({', '.join(own_ids)}) 콜라보 {len(own_p)}건"
             f"{' — ' + ', '.join(own_p) if own_p else ' (없음)'}")
    L.append(f"- **경쟁사** 콜라보 {len(comp_p)}건"
             f"{' — ' + ', '.join(sorted(set(comp_p))) if comp_p else ' (없음)'}")
    if own_p:
        L.append("- 자사도 콜라보를 운용 중 → 협업 IP/인플루언서의 **화제성·일본 현지 적합도**가 관건. "
                 "경쟁사 파트너군과 비교해 차별 포인트 점검.")
    else:
        L.append("- 자사 콜라보 부재 → 경쟁사 대비 명확한 약점. 일본 현지 인플루언서/IP 협업 검토 권장.")
    if no_collab:
        L.append(f"- 콜라보 미운용 경쟁사: {', '.join(no_collab)} (캠페인·쿠폰 설계로 차별).")
    L.append("- 이벤트 형식(시즌 일러스트 캠페인·요일별 세일 캘린더·라이브커머스·계단식/채널별 쿠폰·"
             "1+1/증정) 다양화 정도가 톤앤매너 완성도와 직결.")

    # 6) 상품별 컨셉·소구점 (상세페이지 비전 분석)
    has_concepts = any(d.get("concepts") for d in data.values())
    if has_concepts:
        L.append("\n## 6. 상품별 컨셉·소구점 (상세페이지 비전 OCR 분석)\n")
        L.append("> 샵당 상위 상품(리뷰 기준)의 상세페이지 디자인컷을 Claude 비전으로 OCR·해석한 "
                 "결과. 손으로 채우던 톤앤매너(1번 표)를 상품 단위 실데이터로 보강.\n")
        for sid, d in data.items():
            if not d.get("concepts"):
                continue
            star = "★" if d["is_own"] else ""
            L.append(f"\n### {star}{sid} ({d['role']})\n")
            L.append("| 상품 | 컨셉 | 핵심 소구점 | 타깃 | 핵심성분 | 대표카피 |")
            L.append("|---|---|---|---|---|---|")
            for c in d["concepts"]:
                sp = " · ".join(c["selling_points"][:5])
                ki = ", ".join(c["key_ingredients"][:5])
                L.append(f"| {c['name'][:30]} | {c['concept']} | {sp} | {c['target']} "
                         f"| {ki} | {c['hero_copy'][:40]} |")

    md = OUT / f"design_intelligence_{group}.md"
    md.write_text("\n".join(L), encoding="utf-8")

    # collab CSV
    csv = OUT / f"collab_{group}.csv"
    rows = ["shop_id,role,partner,type,product_count,sample_product"]
    for sid, d in data.items():
        for ip in d["ip_collabs"]:
            rows.append(f'{sid},{d["role"]},"{ip}",IP,,')
        for c in d["collabs"]:
            rows.append(f'{sid},{d["role"]},"{c["partner"]}",influencer,'
                        f'{c["count"]},"{c["sample"][:60]}"')
    csv.write_text("\n".join(rows), encoding="utf-8-sig")
    return md, csv


def main():
    group = _arg("--group", "skincare")
    data = mine(group)
    md, csv = write_reports(group, data)
    # 콘솔 요약
    print(f"=== 마케팅 인텔리전스: {group} ({group_label(group)}) ===")
    for sid, d in data.items():
        cs = ", ".join(f"{c['partner']}×{c['count']}" for c in d["collabs"]) or "-"
        ip = ", ".join(d["ip_collabs"])
        allc = " / ".join(x for x in [ip, cs] if x and x != "-") or "콜라보 없음"
        print(f"  {'★' if d['is_own'] else ' '} {sid:20} 콜라보: {allc}")
    print(f"\n리포트: {md}\n콜라보 CSV: {csv}")


if __name__ == "__main__":
    main()
