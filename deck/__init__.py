"""deck — report-spec(JSON) → 폴리시드 16슬라이드 PPTX 생성기.

사용:
    python -m deck.build samples/report_spec_makeup.json out/gen_makeup.pptx
"""
from .build import build_deck  # noqa: F401
