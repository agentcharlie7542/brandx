"""report-spec → 16슬라이드 PPTX 오케스트레이터.

차트(루브릭·갭·포지셔닝)는 spec에서 생성하거나 기존 PNG 재사용.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile

from pptx import Presentation
from pptx.util import Inches


def _resolve_charts(spec, workdir):
    from . import charts as CH
    out = {}
    sc = spec.get("charts", {})
    # 포지셔닝: spec 경로 있으면 재사용, 없으면 생성
    pr = sc.get("price_review")
    out["price_review"] = pr if (pr and os.path.exists(pr)) else \
        CH.positioning_price_review(spec, os.path.join(workdir, "pos_price_review.png"))
    fs = sc.get("follower_sat")
    out["follower_sat"] = fs if (fs and os.path.exists(fs)) else \
        CH.positioning_follower_sat(spec, os.path.join(workdir, "pos_follower_sat.png"))
    # 루브릭·갭: 항상 생성
    out["rubric_bar"] = CH.rubric_bar(spec, os.path.join(workdir, "rubric_bar.png"))
    out["gap_bar"] = CH.gap_bar(spec, os.path.join(workdir, "gap_bar.png"))
    return out


def validate_spec(spec, schema_path=None):
    """jsonschema 검증(설치돼 있으면). 실패 시 예외."""
    schema_path = schema_path or os.path.join(os.path.dirname(__file__), "..", "schemas", "report_spec.schema.json")
    if not os.path.exists(schema_path):
        return
    try:
        import jsonschema
    except ImportError:
        return
    schema = json.load(open(schema_path, encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(spec)


def build_deck(spec, out_path, workdir=None, validate=True):
    """spec(dict 또는 경로) → out_path(pptx)."""
    if isinstance(spec, str):
        spec = json.load(open(spec, encoding="utf-8"))
    if validate:
        try:
            validate_spec(spec)
        except Exception as e:
            print(f"[warn] spec 검증 경고: {e}")
    workdir = workdir or tempfile.mkdtemp(prefix="deck_")
    charts = _resolve_charts(spec, workdir)

    from . import slides as S
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    for builder in S.ALL_SLIDES:
        builder(prs, spec, charts)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    prs.save(out_path)
    return out_path


def main(argv):
    if len(argv) < 2:
        print("usage: python -m deck.build <spec.json> [out.pptx]")
        return 1
    spec_path = argv[1]
    out_path = argv[2] if len(argv) > 2 else "out/gen_deck.pptx"
    build_deck(spec_path, out_path)
    print(f"✅ 생성 완료: {out_path}  ({len(json.load(open(spec_path,encoding='utf-8'))['shops'])}개 샵)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
