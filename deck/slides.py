"""16개 슬라이드 빌더 — report-spec → 슬라이드. 모든 텍스트/수치는 spec에서.

레이아웃은 샵 수에 따라 동적(스코어카드 행·갤러리 카드·이벤트표 행).
"""
from __future__ import annotations
import math
from . import theme as T
from . import components as C


# ── 포매터 ──────────────────────────────────────────────
def f_price(v):     return f"¥{int(round(v)):,}"
def f_int(v):       return f"{int(round(v)):,}"
def f_pct0(v):      return f"{v*100:.0f}%"
def f_satp(v):      return f"{int(round(v))}%"
def f_promo(v):     return f"{v:g}"

def f_followers(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{round(v/1000)}K"
    return str(int(v))

def f_score(v):
    s = f"{v:.2f}"
    return s[:-1] if s.endswith("0") else s

def f_review(m):
    s = f"{int(m['review_volume']):,}"
    return s + ("*" if m.get("review_capped") else "")

def f_top5(m):
    return "1.0*" if m.get("review_capped") else f"{m['top5_power']:.2f}"

def role_kr(r):     return "자사" if r == "own" else "경쟁"


# ── 1. 표지 ─────────────────────────────────────────────
def slide01_cover(prs, spec, charts):
    s = C.blank_slide(prs)
    C.rect(s, 0, 0, 13.333, 7.5, fill=T.INK)
    C.rect(s, 0, 0, 0.22, 7.5, fill=T.PINK)              # 좌측 스파인
    C.text(s, 1.0, 1.55, 10, 0.4, "QOO10 JAPAN  ·  COMPETITIVE BENCHMARK",
           size=13, color=T.MUTED, bold=True)
    C.text(s, 1.0, 2.05, 11, 1.7, [
        {"t": f"{spec['category_label']} 경쟁사", "size": 44, "color": T.WHITE, "bold": True, "space_after": 2},
        {"t": "비교분석 보고서", "size": 44, "color": T.PINK, "bold": True},
    ])
    own = [sh["name"] for sh in spec["shops"] if sh["role"] == "own"]
    comp = [sh["name"] for sh in spec["shops"] if sh["role"] == "competitor"]
    vs_line = f"{' · '.join(own)}(자사)  vs  {' · '.join(comp)}"
    C.text(s, 1.0, 4.05, 11.3, 0.5, vs_line, size=17, color=hexish("D9D2EA"))
    # 하단 3 정보 카드
    info = [("분석 대상", f"{len(spec['shops'])}개 샵 (자사{len(own)}·경쟁{len(comp)})"),
            ("데이터 기준", "샵·상품·디자인 3-Layer"),
            ("용도", "올리브영 비딩 과제① 근거")]
    cw, gap, x0, y = 3.6, 0.25, 1.0, 5.15
    for i, (k, v) in enumerate(info):
        x = x0 + i * (cw + gap)
        C.rect(s, x, y, cw, 1.0, fill=hexish("3A2A60"), rounded=True, radius=0.06)
        C.text(s, x + 0.28, y + 0.18, cw - 0.5, 0.3, k, size=11, color=T.MUTED, bold=True)
        C.text(s, x + 0.28, y + 0.52, cw - 0.5, 0.35, v, size=14, color=T.WHITE, bold=True)
    C.text(s, 1.0, 6.55, 11, 0.3,
           f"Prepared by {spec.get('prepared_by','Aiden Lab')}  ·  Strategy & Performance Marketing  ·  {spec['generated_at']}",
           size=11, color=T.MUTED)
    return s


def hexish(h):  # 로컬 헬퍼
    return T.hex_color(h)


# ── 2. Executive Summary ───────────────────────────────
def slide02_exec(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "EXECUTIVE SUMMARY", "핵심 요약 — 한 장으로 보는 진단", 2)
    es = spec["narrative"]["exec_summary"]
    # KPI 카드
    kpis = es["kpis"][:4]
    cw, gap, x0, y = 2.93, 0.18, 0.60, 1.55
    for i, k in enumerate(kpis):
        x = x0 + i * (cw + gap)
        C.card(s, x, y, cw, 1.15, accent=T.KPI_ACCENTS[i % 4], accent_w=0.09)
        C.text(s, x + 0.30, y + 0.18, cw - 0.5, 0.55, k["value"], size=22, color=T.PINK if i == 0 else T.INK, bold=True)
        C.text(s, x + 0.30, y + 0.74, cw - 0.5, 0.32, k["label"], size=10.5, color=T.GREY_TXT)
    # 핵심 발견
    C.text(s, 0.60, 2.95, 6, 0.35, "핵심 발견", size=15, color=T.INK, bold=True)
    fcw, fgap, fy = 3.93, 0.20, 3.45
    for i, fnd in enumerate(es["findings"][:3]):
        x = 0.60 + i * (fcw + fgap)
        C.card(s, x, fy, fcw, 2.45)
        C.circle_num(s, x + 0.30, fy + 0.30, 0.62, i + 1)
        C.text(s, x + 0.30, fy + 1.05, fcw - 0.6, 0.5, fnd["title"], size=13, color=T.INK, bold=True)
        C.text(s, x + 0.30, fy + 1.55, fcw - 0.6, 0.8, fnd["body"], size=10.5, color=T.GREY_TXT, line_spacing=1.05)
    # 결론 바
    C.rect(s, 0.60, 6.15, 12.13, 0.62, fill=T.INK, rounded=True, radius=0.08)
    C.text(s, 0.95, 6.15, 11.5, 0.62,
           [{"t": "결론  ", "size": 12, "color": T.PINK, "bold": True},
            ], anchor="middle")
    C.text(s, 1.55, 6.15, 11.0, 0.62, es["conclusion"], size=11, color=T.WHITE, anchor="middle")
    if es.get("footnote"):
        C.text(s, 0.60, 7.12, 12.7, 0.3, es["footnote"], size=8, color=T.MUTED)
    return s


# ── 3. Methodology ─────────────────────────────────────
def slide03_method(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "METHODOLOGY", "분석 대상 & 3-Layer 비교 프레임워크", 3)
    C.text(s, 0.60, 1.45, 12, 0.4,
           "커머스 경쟁력을 유입 → 전환 → 객단가 퍼널에 대응시켜 3개 레이어로 분해하고, 정성 요소는 5점 루브릭으로 점수화했습니다.",
           size=12, color=T.GREY_TXT)
    layers = [
        ("LAYER 1", "샵(스토어) 레벨 · 정량", "셀러등급 · 만족도 · 팔로워 · 상품수 · 쿠폰/타임세일 운영 강도 · 메가와리 대응"),
        ("LAYER 2", "상품(SKU) 레벨 · 정량", "가격대 분포 · Top5 리뷰볼륨(판매 대리지표) · 세트/단품 비중 · 일본한정 기획수 · 추정매출"),
        ("LAYER 3", "디자인/콘텐츠 · 정성→점수", "썸네일25% · 샵메인20% · 현지화20% · 프로모션설계20% · 일관성15% (5점 루브릭)"),
    ]
    y, h, gap = 2.10, 1.5, 0.18
    accents = [T.PINK, T.PURPLE_DK, T.INK]
    for i, (tag, title, body) in enumerate(layers):
        ly = y + i * (h + gap)
        C.card(s, 0.56, ly, 8.6, h, accent=accents[i], accent_w=0.10)
        C.text(s, 0.95, ly, 1.7, h, tag, size=14, color=T.PINK, bold=True, anchor="middle")
        C.rect(s, 2.75, ly + 0.28, 0.015, h - 0.56, fill=T.LINE_SOFT)
        C.text(s, 2.95, ly + 0.30, 6.0, 0.4, title, size=15, color=T.INK, bold=True)
        C.text(s, 2.95, ly + 0.78, 6.0, 0.6, body, size=10.5, color=T.GREY_TXT, line_spacing=1.05)
    # 우측 패널: 분석 대상 N개 샵
    px, pw = 9.45, 3.28
    C.rect(s, px, y, pw, 3 * h + 2 * gap, fill=T.INK, rounded=True, radius=0.05)
    C.text(s, px + 0.32, y + 0.22, pw - 0.6, 0.4, f"분석 대상 {len(spec['shops'])}개 샵", size=14, color=T.WHITE, bold=True)
    panel_h = 3 * h + 2 * gap
    n = len(spec["shops"])
    step = min(0.62, (panel_h - 0.95) / n)        # 샵 수에 맞춰 칩 간격 동적
    name_sz = 12.5 if step >= 0.55 else 11.5
    sy = y + 0.74
    for sh in spec["shops"]:
        own = sh["role"] == "own"
        C.text(s, px + 0.32, sy, pw - 0.6, 0.3,
               ("★ " if own else "") + sh["name"], size=name_sz, color=T.PINK if own else T.WHITE, bold=True)
        C.text(s, px + 0.32, sy + 0.25, pw - 0.6, 0.25,
               ("자사 · " if own else "") + (sh.get("tagline") or ""), size=9.5, color=T.MUTED)
        sy += step
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 4. Market Context ──────────────────────────────────
def slide04_market(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "MARKET CONTEXT", "시장 컨텍스트 — 온라인 리서치 보강", 4)
    mc = spec["narrative"].get("market_context", [])[:4]
    head_colors = [T.hex_color("C9A227"), T.PINK, T.PURPLE_DK, T.INK]
    cw, ch, gx, gy, x0, y0 = 6.0, 2.05, 0.13, 0.22, 0.60, 1.55
    for i, card in enumerate(mc):
        r, c = divmod(i, 2)
        x = x0 + c * (cw + gx); y = y0 + r * (ch + gy)
        C.card(s, x, y, cw, ch, shadow=True)
        C.rect(s, x, y, cw, 0.52, fill=head_colors[i % 4], rounded=True, radius=0.05)
        C.rect(s, x, y + 0.26, cw, 0.26, fill=head_colors[i % 4])  # 하단 모서리 각지게
        C.text(s, x + 0.30, y, cw - 0.6, 0.52, card["head"], size=12, color=T.WHITE, bold=True, anchor="middle")
        C.text(s, x + 0.30, y + 0.66, cw - 0.6, 0.4, card["title"], size=15, color=T.INK, bold=True)
        C.text(s, x + 0.30, y + 1.16, cw - 0.6, 0.8, card["body"], size=10.5, color=T.GREY_TXT, line_spacing=1.05)
    srcs = spec["narrative"].get("next_steps", {}).get("sources", [])
    src_line = "출처: " + (mc[0].get("source") if mc and mc[0].get("source") else
                          (srcs[-1] if srcs else ""))
    C.text(s, 0.60, 6.95, 12.7, 0.3, src_line, size=8.5, color=T.MUTED)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 5. Scorecard (동적 표) ──────────────────────────────
SCORE_COLS = [
    ("샵", "name", 2.25, "left"), ("구분", "role", 0.78, "center"),
    ("SKU", "sku", 0.66, "center"), ("가격 중앙", "price", 1.02, "center"),
    ("리뷰볼륨", "review", 1.08, "center"), ("Top5\n집중도", "top5", 0.92, "center"),
    ("세트\n비중", "set", 0.82, "center"), ("일본\n한정", "jp", 0.74, "center"),
    ("만족도", "sat", 0.86, "center"), ("팔로워", "fol", 1.00, "center"),
    ("디자인\n총점", "design", 0.92, "center"), ("프로모\n강도", "promo", 0.88, "center"),
]

def slide05_scorecard(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    own_n = sum(1 for sh in spec["shops"] if sh["role"] == "own")
    suffix = f" (★ 자사 {own_n}개샵)" if own_n > 1 else " (자사 강조)"
    C.header(s, "SCORECARD", "경쟁 스코어카드" + suffix, 5)
    shops = spec["shops"]
    tot_w = sum(c[2] for c in SCORE_COLS)
    scale = 12.13 / tot_w
    widths = [c[2] * scale for c in SCORE_COLS]
    xs = [0.60]
    for w in widths[:-1]:
        xs.append(xs[-1] + w)
    top = 1.52
    head_h = 0.55
    n = len(shops)
    avail = 5.55 - top - head_h
    row_h = min(0.52, avail / n)
    # 헤더
    C.rect(s, 0.60, top, 12.13, head_h, fill=T.PURPLE_DK)
    for (label, key, _, al), x, w in zip(SCORE_COLS, xs, widths):
        C.text(s, x, top, w, head_h,
               [{"t": ln, "align": al} for ln in label.split("\n")],
               size=10, color=T.WHITE, bold=True, align=al, anchor="middle")
    # 행
    y = top + head_h
    for ri, sh in enumerate(shops):
        m = spec["metrics"][sh["id"]]; ds = spec["design_scores"][sh["id"]]
        own = sh["role"] == "own"
        bg = T.PINK_SOFT if own else (T.WHITE if ri % 2 == 0 else T.ZEBRA)
        C.rect(s, 0.60, y, 12.13, row_h, fill=bg)
        vals = {
            "name": ("★ " if own else "") + sh["name"], "role": role_kr(sh["role"]),
            "sku": str(m["sku"]), "price": f_price(m["price_median"]),
            "review": f_review(m), "top5": f_top5(m), "set": f_pct0(m["set_ratio"]),
            "jp": str(m["jp_limited"]), "sat": f_satp(m["satisfaction"]),
            "fol": f_followers(m["followers"]), "design": f_score(ds["total"]),
            "promo": f_promo(m["promo_intensity"]),
        }
        for (label, key, _, al), x, w in zip(SCORE_COLS, xs, widths):
            is_name = key == "name"
            C.text(s, x + (0.12 if is_name else 0), y, w - (0.12 if is_name else 0), row_h, vals[key],
                   size=10.5 if is_name else 10, color=T.PINK if (own and is_name) else T.INK,
                   bold=own or is_name, align=("left" if is_name else "center"), anchor="middle")
        if own:
            C.rect(s, 0.60, y, 0.06, row_h, fill=T.PINK)
        y += row_h
    C.text(s, 0.60, y + 0.12, 12.13, 0.3,
           [{"t": "읽는 법  ", "color": T.PINK, "bold": True},
            {"t": "디자인총점·세트비중·일본한정 = 현지화·기획 강점(자사 우위) / 리뷰볼륨·팔로워·프로모강도 = 규모·물량(추격 영역).", "color": T.GREY_TXT}],
           size=10)
    cap = next((g for g in spec["metrics"].values() if g.get("review_capped")), None)
    if cap:
        C.text(s, 0.60, 7.15, 12.7, 0.3,
               "* 일부 샵의 리뷰볼륨·Top5는 999+ 표기 상한에 따른 과소/왜곡 집계 — 절대비교보다 추세·구조 해석에 사용.",
               size=8, color=T.MUTED)
    return s


# ── 6·7. Positioning (차트) ────────────────────────────
def _chart_slide(prs, spec, eyebrow, title, page, img):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, eyebrow, title, page)
    C.card(s, 0.60, 1.5, 8.0, 5.3)
    C.image_inside(s, img, 0.75, 1.65, 7.7, 5.0)
    return s


def slide06_pos1(prs, spec, charts):
    s = _chart_slide(prs, spec, "POSITIONING ①", "가격 × 리뷰볼륨 — 규모와 가격 포지션", 6, charts["price_review"])
    _interp_panel(s, spec, _pos_notes_price(spec))
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


def slide07_pos2(prs, spec, charts):
    s = _chart_slide(prs, spec, "POSITIONING ②", "팔로워 × 만족도 — 고객자산 & 운영품질", 7, charts["follower_sat"])
    _interp_panel(s, spec, _pos_notes_follower(spec))
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


def _interp_panel(s, spec, notes):
    px, pw, y = 8.85, 3.88, 1.5
    C.rect(s, px, y, pw, 5.3, fill=T.INK, rounded=True, radius=0.05)
    C.text(s, px + 0.32, y + 0.22, pw - 0.6, 0.4, "해석 포인트", size=14, color=T.WHITE, bold=True)
    yy = y + 0.85
    for title, body in notes[:4]:
        C.rect(s, px + 0.32, yy + 0.05, 0.12, 0.12, fill=T.PINK, rounded=True, radius=0.5)
        C.text(s, px + 0.56, yy, pw - 0.9, 0.3, title, size=12, color=T.WHITE, bold=True)
        C.text(s, px + 0.56, yy + 0.28, pw - 0.9, 0.7, body, size=9.5, color=T.hex_color("CFC8E2"), line_spacing=1.03)
        yy += 1.05


def _pos_notes_price(spec):
    own = next(sh for sh in spec["shops"] if sh["role"] == "own")
    m = spec["metrics"][own["id"]]
    leader = max(spec["shops"], key=lambda sh: spec["metrics"][sh["id"]]["review_volume"])
    lm = spec["metrics"][leader["id"]]
    return [
        ("자사 포지션", f"{own['name']} ¥{int(m['price_median']):,} · 리뷰볼륨 {int(m['review_volume']):,} — 그룹 내 가격·규모 좌표."),
        ("리뷰볼륨 리더", f"{leader['name']} 리뷰 {int(lm['review_volume']):,}로 최다 — 벤치마크 대상."),
        ("시사점", "가격 강점은 유지하되 리뷰 적립·세트 업셀로 우상단(고전환)으로 이동하는 설계가 핵심."),
    ]


def _pos_notes_follower(spec):
    own = next(sh for sh in spec["shops"] if sh["role"] == "own")
    m = spec["metrics"][own["id"]]
    leader = max(spec["shops"], key=lambda sh: spec["metrics"][sh["id"]]["followers"])
    lm = spec["metrics"][leader["id"]]
    return [
        ("고객자산", f"{own['name']} 팔로워 {f_followers(m['followers'])} vs 1위 {leader['name']} {f_followers(lm['followers'])}."),
        ("운영품질", f"만족도 {int(m['satisfaction'])}% — 그룹 평균권. 도달(팔로워) 확장이 우선 과제."),
        ("우선순위", "팔로우 쿠폰·라이브·UGC로 팔로워 전환을 상시화해 광고 의존도↓."),
    ]


# ── 8. Design Benchmark 갤러리 (동적 그리드) ───────────
def slide08_gallery(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "DESIGN BENCHMARK", "디자인 벤치마크 갤러리 (★ 자사)", 8)
    cards = spec.get("gallery", [])
    shop_by_id = {sh["id"]: sh for sh in spec["shops"]}
    n = len(cards)
    cols = n if n <= 4 else 4
    rows = math.ceil(n / cols)
    area_l, area_t, area_w, area_b = 0.56, 1.42, 12.21, 6.95
    gx, gy = 0.16, 0.20
    cw = (area_w - (cols - 1) * gx) / cols
    img_h = min(cw / 1.55, (area_b - area_t - (rows - 1) * gy) / rows - 0.55)
    card_h = img_h + 0.52
    total_h = rows * card_h + (rows - 1) * gy
    y0 = area_t + max(0, (area_b - area_t - total_h) / 2)
    for i, g in enumerate(cards):
        r, c = divmod(i, cols)
        x = area_l + c * (cw + gx)
        y = y0 + r * (card_h + gy)
        sh = shop_by_id.get(g["shop_id"], {})
        own = sh.get("role") == "own"
        frame = C.rect(s, x, y, cw, img_h + 0.04, fill=T.WHITE, rounded=True, radius=0.04,
                       line=T.PINK if own else T.LINE_SOFT, line_w=2.2 if own else 0.75)
        C.image_inside(s, g.get("image"), x + 0.04, y + 0.04, cw - 0.08, img_h - 0.04)
        C.text(s, x + 0.04, y + img_h + 0.06, cw - 0.08, 0.28,
               ("★ " if own else "") + sh.get("name", g["shop_id"]),
               size=11.5, color=T.PINK if own else T.INK, bold=True)
        C.text(s, x + 0.04, y + img_h + 0.30, cw - 0.08, 0.24,
               f"{f_score(g['score'])} · {g['caption']}", size=9, color=T.GREY_TXT)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 9. Design Deep Dive ────────────────────────────────
def slide09_deepdive(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "DESIGN DEEP DIVE", "디자인 루브릭 심층 비교", 9)
    C.card(s, 0.55, 1.5, 7.95, 5.3)
    C.image_inside(s, charts.get("rubric_bar"), 0.70, 1.62, 7.65, 5.05)
    # 우측 진단 패널
    diag = spec["narrative"].get("design_diagnosis", [])
    px, pw, y = 8.75, 3.98, 1.5
    C.card(s, px, y, pw, 5.3)
    C.text(s, px + 0.34, y + 0.24, pw - 0.6, 0.4, "자사 항목별 진단", size=14, color=T.INK, bold=True)
    yy = y + 0.82
    for d in diag[:5]:
        C.text(s, px + 0.34, yy, pw - 1.4, 0.3, d["item"], size=12.5, color=T.INK, bold=True)
        bw = 0.74
        C.chip(s, px + pw - 0.34 - bw, yy - 0.02, bw, 0.30, f"{d['score']:g}",
               fill=T.score_badge_color(d["score"]), color=T.WHITE, size=11)
        C.text(s, px + 0.34, yy + 0.30, pw - 0.6, 0.4, d["comment"], size=9.5, color=T.GREY_TXT, line_spacing=1.03)
        yy += 0.86
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 10. Marketing ① 톤앤매너 (동적 카드) ───────────────
def slide10_tone(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "MARKETING ①", "톤앤매너 & 메인 캠페인", 10)
    tone = spec["marketing"].get("tone", {})
    shops = spec["shops"]
    # 6칸까지 카드, 초과분은 하단 캡션
    grid_shops = shops[:6]
    overflow = shops[6:]
    cols, x0, y0, cw, ch, gx, gy = 3, 0.60, 1.50, 3.97, 2.05, 0.18, 0.22
    for i, sh in enumerate(grid_shops):
        r, c = divmod(i, cols)
        x = x0 + c * (cw + gx); y = y0 + r * (ch + gy)
        own = sh["role"] == "own"
        C.card(s, x, y, cw, ch, accent=T.PINK if own else T.PURPLE_DK, accent_w=0.09)
        t = tone.get(sh["id"], {})
        C.text(s, x + 0.32, y + 0.18, cw - 0.6, 0.35,
               ("★ " if own else "") + sh["name"], size=13, color=T.PINK if own else T.INK, bold=True)
        C.chip(s, x + 0.32, y + 0.62, cw - 0.64, 0.40, t.get("mood", ""), fill=T.ZEBRA, color=T.INK, size=11)
        C.text(s, x + 0.32, y + 1.18, cw - 0.6, 0.8, t.get("campaign", ""), size=9.5, color=T.GREY_TXT, line_spacing=1.03)
    if overflow:
        names = " / ".join(sh["name"] for sh in overflow)
        ov = overflow[0]; t = tone.get(ov["id"], {})
        C.text(s, 0.60, 6.40, 12.13, 0.5,
               f"{names}: {t.get('campaign','')}", size=9.5, color=T.GREY_TXT)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 11. Marketing ② 콜라보 + 이벤트표 ──────────────────
def slide11_collab(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "MARKETING ②", "콜라보 & 이벤트 강도", 11)
    shop_by_id = {sh["id"]: sh for sh in spec["shops"]}
    # 좌: 콜라보 리스트
    C.card(s, 0.60, 1.50, 5.55, 5.30)
    C.text(s, 0.92, 1.72, 5, 0.35, "인플루언서 / IP 콜라보", size=14, color=T.INK, bold=True)
    collabs = spec["marketing"].get("collabs", [])
    # 샵별 묶기(표시 순서 = shops 순서 중 콜라보 있는 샵)
    by_shop = {}
    for c in collabs:
        by_shop.setdefault(c["shop_id"], []).append(c)
    yy = 2.20
    for sh in spec["shops"]:
        if sh["id"] not in by_shop:
            continue
        own = sh["role"] == "own"
        items = by_shop[sh["id"]]
        C.card(s, 0.90, yy, 4.95, 0.84, fill=T.PINK_SOFT if own else T.ZEBRA,
               line=T.PINK if own else None, line_w=1.2, shadow=False)
        C.text(s, 1.12, yy + 0.10, 4.6, 0.3, ("★ " if own else "") + sh["name"],
               size=12, color=T.PINK if own else T.INK, bold=True)
        partners = " · ".join(c["partner"] for c in items)
        note = next((c.get("note") for c in items if c.get("note")), "")
        C.text(s, 1.12, yy + 0.40, 4.6, 0.4,
               [{"t": partners + "  ", "color": T.INK, "bold": True},
                {"t": note, "color": T.GREY_TXT}], size=9.5)
        yy += 0.96
    # 우: 이벤트강도 표 (동적 행)
    ev = spec["marketing"].get("event_intensity", [])
    tx, tw = 6.45, 6.28
    C.card(s, tx, 1.50, tw, 5.30)
    C.text(s, tx + 0.30, 1.72, 5, 0.35, "이벤트·프로모션 강도", size=14, color=T.INK, bold=True)
    cols = [("샵", "shop", 1.55, "left"), ("쿠폰", "coupon", 0.72, "center"),
            ("타임\n세일", "timesale", 0.85, "center"), ("평균%↓", "avg_off", 1.0, "center"),
            ("메가와리", "megawari", 1.08, "center"), ("세트", "set", 0.70, "center")]
    cw_tot = sum(c[2] for c in cols); sc = (tw - 0.60) / cw_tot
    ws = [c[2] * sc for c in cols]
    cx = [tx + 0.30]
    for w in ws[:-1]:
        cx.append(cx[-1] + w)
    htop = 2.22; hh = 0.55
    C.rect(s, tx + 0.30, htop, tw - 0.60, hh, fill=T.PURPLE_DK)
    for (label, key, _, al), x, w in zip(cols, cx, ws):
        C.text(s, x, htop, w, hh, [{"t": ln} for ln in label.split("\n")],
               size=9.5, color=T.WHITE, bold=True, align="center", anchor="middle")
    n = len(ev); avail = 6.55 - htop - hh - 0.45
    rh = min(0.50, avail / max(n, 1))
    y = htop + hh
    for ri, row in enumerate(ev):
        sh = shop_by_id.get(row["shop_id"], {})
        own = sh.get("role") == "own"
        bg = T.PINK_SOFT if own else (T.WHITE if ri % 2 == 0 else T.ZEBRA)
        C.rect(s, tx + 0.30, y, tw - 0.60, rh, fill=bg)
        disp = {"shop": ("★ " if own else "") + (sh.get("name", row["shop_id"])),
                "coupon": str(row["coupon"]), "timesale": str(row["timesale"]),
                "avg_off": f"{row['avg_off']:g}", "megawari": str(row["megawari"]),
                "set": str(row["set"])}
        for (label, key, _, al), x, w in zip(cols, cx, ws):
            isname = key == "shop"
            C.text(s, x + (0.1 if isname else 0), y, w, rh, disp[key], size=10,
                   color=T.PINK if (own and isname) else T.INK, bold=own,
                   align="left" if isname else "center", anchor="middle")
        y += rh
    C.text(s, tx + 0.30, y + 0.10, tw - 0.6, 0.4,
           [{"t": "자사 시사점  ", "color": T.PINK, "bold": True},
            {"t": "IP 콜라보·타임세일은 강점. 쿠폰·메가와리 물량 확대 여지.", "color": T.GREY_TXT}], size=9.5)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 12. Gap Analysis ───────────────────────────────────
def slide12_gap(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    own = next(sh for sh in spec["shops"] if sh["role"] == "own")
    leader = spec["gap"][0]["leader_shop"] if spec["gap"] else ""
    lname = next((sh["name"] for sh in spec["shops"] if sh["id"] == leader), leader)
    C.header(s, "GAP ANALYSIS", f"자사({own['name']}) vs 그룹 1위({lname})", 12)
    C.card(s, 0.60, 1.5, 7.7, 5.3)
    C.image_inside(s, charts.get("gap_bar"), 0.75, 1.62, 7.4, 5.05)
    # 우선순위 카드
    px, pw, y = 8.55, 4.18, 1.5
    C.card(s, px, y, pw, 5.3)
    C.text(s, px + 0.32, y + 0.22, pw - 0.6, 0.4, "우선순위 (갭 큰 순)", size=14, color=T.INK, bold=True)
    rows = sorted(spec["gap"], key=lambda g: g["achievement_pct"])
    yy = y + 0.78
    ch = (5.3 - 0.85) / max(len(rows), 1)
    for g in rows:
        v = g["achievement_pct"]
        col = T.score_badge_color(5 if v >= 90 else (4 if v >= 80 else (3.6 if v >= 60 else 3)))
        C.rect(s, px + 0.28, yy, 0.10, ch - 0.16, fill=col, rounded=True, radius=0.3)
        C.text(s, px + 0.52, yy + 0.06, pw - 1.7, 0.3, g["label"], size=12.5, color=T.INK, bold=True)
        C.text(s, px + 0.52, yy + 0.36, pw - 1.7, 0.3,
               f"vs {lname} · {g.get('note','')}", size=9, color=T.GREY_TXT)
        C.text(s, px + pw - 1.25, yy, 1.0, ch - 0.16, f"{v:.0f}%" if v % 1 else f"{int(v)}%",
               size=17, color=col, bold=True, align="right", anchor="middle")
        yy += ch
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 13. SWOT ───────────────────────────────────────────
def slide13_swot(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "DIAGNOSIS", "종합 진단 — SWOT", 13)
    sw = spec["narrative"]["diagnosis_swot"]
    quad = [("S", "강점 Strength"), ("W", "약점 Weakness"), ("O", "기회 Opportunity"), ("T", "위협 Threat")]
    cw, ch, gx, gy, x0, y0 = 6.0, 2.42, 0.13, 0.22, 0.60, 1.55
    for i, (k, title) in enumerate(quad):
        r, c = divmod(i, 2)
        x = x0 + c * (cw + gx); y = y0 + r * (ch + gy)
        C.card(s, x, y, cw, ch, shadow=True)
        C.rect(s, x, y, cw, 0.52, fill=T.SWOT_COLORS[k], rounded=True, radius=0.05)
        C.rect(s, x, y + 0.26, cw, 0.26, fill=T.SWOT_COLORS[k])
        C.text(s, x + 0.30, y, cw - 0.6, 0.52, title, size=13, color=T.WHITE, bold=True, anchor="middle")
        bullets = [{"t": "• " + b, "space_after": 4} for b in sw[k]]
        C.text(s, x + 0.32, y + 0.66, cw - 0.62, ch - 0.8, bullets, size=10.5, color=T.GREY_TXT, line_spacing=1.04)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 14. Recommendation ① Quick Win ─────────────────────
def slide14_quickwin(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "RECOMMENDATION ①", "자사몰 개선 방향 — Quick Win (D+0~14)", 14)
    C.text(s, 0.60, 1.42, 12, 0.35,
           "강점을 '도달·리뷰'로 전환하는 데 집중. 비용·리스크 낮고 비딩 과제①에 바로 반영 가능.",
           size=12, color=T.GREY_TXT)
    recs = spec["narrative"].get("recommendation_quickwin", [])[:4]
    cw, ch, gx, gy, x0, y0 = 6.0, 2.05, 0.13, 0.22, 0.60, 1.95
    for i, r in enumerate(recs):
        rr, cc = divmod(i, 2)
        x = x0 + cc * (cw + gx); y = y0 + rr * (ch + gy)
        C.card(s, x, y, cw, ch)
        C.circle_num(s, x + 0.30, y + 0.28, 0.6, i + 1, fill=T.PINK if i == 0 else T.PURPLE_DK)
        C.text(s, x + 1.05, y + 0.26, cw - 1.3, 0.35, r["title"], size=13, color=T.INK, bold=True)
        C.chip(s, x + 1.05, y + 0.66, 2.0, 0.34, r["kpi"], fill=T.ZEBRA, color=T.PINK, size=10)
        C.text(s, x + 0.30, y + 1.18, cw - 0.6, 0.8, r["body"], size=10.5, color=T.GREY_TXT, line_spacing=1.05)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 15. Recommendation ② 구조·콘텐츠 ──────────────────
def slide15_structure(prs, spec, charts):
    s = C.blank_slide(prs); C.page_bg(s)
    C.header(s, "RECOMMENDATION ②", "자사몰 개선 방향 — 구조·콘텐츠 (W2~M1)", 15)
    rows = spec["narrative"].get("recommendation_structure", [])[:5]
    y0, gap = 1.55, 0.14
    rh = (6.9 - y0 - (len(rows) - 1) * gap) / max(len(rows), 1)
    for i, r in enumerate(rows):
        y = y0 + i * (rh + gap)
        C.card(s, 0.60, y, 12.13, rh, accent=T.PINK if i % 2 == 0 else T.PURPLE_DK, accent_w=0.10)
        C.text(s, 0.95, y + 0.16, 3.9, 0.4, r["title"], size=13.5, color=T.INK, bold=True)
        C.text(s, 0.95, y + rh - 0.42, 3.9, 0.35, r["tag"], size=10, color=T.PINK, bold=True)
        C.rect(s, 4.85, y + 0.22, 0.015, rh - 0.44, fill=T.LINE_SOFT)
        C.text(s, 5.05, y, 7.4, rh, r["body"], size=10.5, color=T.GREY_TXT, anchor="middle", line_spacing=1.06)
    C.footer(s, spec["category_label"], spec.get("prepared_by", "Aiden Lab"))
    return s


# ── 16. Next Steps & 출처 ──────────────────────────────
def slide16_next(prs, spec, charts):
    s = C.blank_slide(prs)
    C.rect(s, 0, 0, 13.333, 7.5, fill=T.INK)
    C.rect(s, 0, 0, 0.22, 7.5, fill=T.PINK)
    C.text(s, 1.0, 0.9, 10, 0.35, "NEXT STEPS", size=13, color=T.MUTED, bold=True)
    C.text(s, 1.0, 1.25, 11, 0.7, "실행 로드맵 & 출처", size=34, color=T.WHITE, bold=True)
    phases = spec["narrative"]["next_steps"]["phases"][:3]
    cw, gap, x0, y = 3.6, 0.25, 1.0, 2.55
    for i, p in enumerate(phases):
        x = x0 + i * (cw + gap)
        C.rect(s, x, y, cw, 0.62, fill=T.PINK, rounded=True, radius=0.06)
        C.rect(s, x, y + 0.31, cw, 0.31, fill=T.PINK)
        C.text(s, x + 0.28, y, cw - 0.5, 0.62, p["period"], size=12, color=T.WHITE, bold=True, anchor="middle")
        C.rect(s, x, y + 0.62, cw, 1.55, fill=T.hex_color("3A2A60"), rounded=True, radius=0.04)
        C.text(s, x + 0.28, y + 0.78, cw - 0.5, 0.4, p["title"], size=15, color=T.WHITE, bold=True)
        C.text(s, x + 0.28, y + 1.25, cw - 0.5, 0.85, p["body"], size=10, color=T.hex_color("CFC8E2"), line_spacing=1.05)
    # 출처 패널
    C.rect(s, 1.0, 4.7, 11.33, 1.7, fill=T.hex_color("241640"), rounded=True, radius=0.04,
           line=T.PURPLE_DK, line_w=1)
    C.text(s, 1.32, 4.9, 10, 0.35, "데이터 · 출처", size=13, color=T.PINK, bold=True)
    yy = 5.32
    for src in spec["narrative"]["next_steps"]["sources"][:3]:
        C.text(s, 1.32, yy, 10.7, 0.3, "· " + src, size=9.5, color=T.hex_color("CFC8E2"))
        yy += 0.32
    C.text(s, 1.0, 6.7, 11, 0.3,
           f"{spec.get('prepared_by','Aiden Lab')}  ·  올리브영 비딩 과제① 근거 자료  ·  Confidential",
           size=10, color=T.MUTED)
    return s


ALL_SLIDES = [
    slide01_cover, slide02_exec, slide03_method, slide04_market, slide05_scorecard,
    slide06_pos1, slide07_pos2, slide08_gallery, slide09_deepdive, slide10_tone,
    slide11_collab, slide12_gap, slide13_swot, slide14_quickwin, slide15_structure,
    slide16_next,
]
