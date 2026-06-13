"""디자인 시스템 — 색상·치수·폰트 상수.

기존 "완성" 덱(report_*_완성_*.pptx)의 실제 도형에서 측정한 값을 그대로 코드화.
슬라이드 = 13.33 x 7.5 in (16:9).
"""
from __future__ import annotations
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor


def hex_color(h: str) -> RGBColor:
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ── 팔레트 ──────────────────────────────────────────────
INK          = hex_color("2B1B4D")   # 헤더 배경 / 본문 짙은 보라
PINK         = hex_color("E0457B")   # 핵심 액센트
PINK_SOFT    = hex_color("FBEFF4")   # 자사 강조 행 배경
PURPLE_DK    = hex_color("3D2A6B")   # 표 헤더 / 칩
ZEBRA        = hex_color("EAE4F5")   # 표 zebra
WHITE        = hex_color("FFFFFF")
PAGE_BG      = hex_color("EFEEF6")   # 콘텐츠 슬라이드 배경(연라벤더)
CARD_BG      = WHITE
MUTED        = hex_color("8A82A6")   # 흐린 텍스트
GREY_TXT     = hex_color("6B6385")
LINE_SOFT    = hex_color("E3DFF0")

# KPI 카드 좌측 액센트 바 색 순환
KPI_ACCENTS  = [PINK, PURPLE_DK, hex_color("C0392B"), hex_color("C9A227")]

# SWOT 사분면 헤더 색
SWOT_COLORS  = {
    "S": hex_color("3FA864"),  # 강점 green
    "W": hex_color("C0392B"),  # 약점 red
    "O": PURPLE_DK,            # 기회 purple
    "T": hex_color("E08E0B"),  # 위협 orange
}

# 디자인 점수 배지 색(값 기준)
def score_badge_color(v: float) -> RGBColor:
    if v >= 4.5:
        return hex_color("3FA864")   # green
    if v >= 4.0:
        return hex_color("3FA864")
    if v >= 3.5:
        return hex_color("E08E0B")   # orange
    return hex_color("C0392B")       # red


# ── 치수 ────────────────────────────────────────────────
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

MARGIN_L     = Inches(0.60)
HEADER_H     = Inches(1.18)
ACCENT_H     = Inches(0.06)
FOOTER_Y     = Inches(7.16)

# ── 폰트 ────────────────────────────────────────────────
# 한글 렌더 가능한 산세리프. 미설치 시 LibreOffice/PowerPoint가 대체 폰트로 치환.
FONT      = "Noto Sans KR"
FONT_BOLD = "Noto Sans KR"


def slide_dims():
    return SLIDE_W, SLIDE_H
