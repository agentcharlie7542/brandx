"""draft_narrative — report-spec의 정성 서사(narrative.*)를 Claude로 초안 작성.

build_spec.py가 채운 데이터부 + placeholder 서사 spec을 입력받아,
Claude(claude-opus-4-8, adaptive thinking, 구조화 출력)가 발견·SWOT·권고·시장컨텍스트 등을
**데이터 근거로** 작성한다. 결과는 review.status=draft 유지 → 사람이 웹 검수에서 확정.

가드레일: 수치는 spec의 데이터만 인용(환각 방지). 외부 리서치(시장컨텍스트) 출처는
'(출처 검수 필요)'로 표기 — 사람이 검증.

사용:
  export ANTHROPIC_API_KEY=...   (또는 .env 파일)
  python draft_narrative.py --spec samples/spec_makeup_auto.json --out samples/spec_makeup_drafted.json
  python draft_narrative.py --spec samples/spec_makeup_auto.json --pptx out/drafted_makeup.pptx
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).parent


def _load_env():
    """.env(KEY=VALUE) 로드 — python-dotenv 의존 없이."""
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

from pydantic import BaseModel  # noqa: E402

MODEL = "claude-opus-4-8"


# ── 구조화 출력 스키마 ──────────────────────────────────
class Finding(BaseModel):
    title: str
    body: str

class MarketCard(BaseModel):
    head: str
    title: str
    body: str
    source: str

class Swot(BaseModel):
    S: List[str]
    W: List[str]
    O: List[str]
    T: List[str]

class QuickWin(BaseModel):
    title: str
    kpi: str
    body: str

class StructRec(BaseModel):
    title: str
    tag: str
    body: str

class ItemComment(BaseModel):
    item: str
    comment: str

class Phase(BaseModel):
    period: str
    title: str
    body: str

class NarrativeDraft(BaseModel):
    findings: List[Finding]                       # 핵심 발견 3개
    conclusion: str                               # 결론 1문장
    market_context: List[MarketCard]              # 시장 컨텍스트 3~4
    diagnosis_swot: Swot
    recommendation_quickwin: List[QuickWin]       # Quick Win 4
    recommendation_structure: List[StructRec]     # 구조·콘텐츠 5
    design_diagnosis_comments: List[ItemComment]  # 디자인 항목별 코멘트
    next_steps_phases: List[Phase]                # 로드맵 3단계


SYSTEM = """당신은 일본 Qoo10 커머스 경쟁분석 전문 컨설턴트입니다.
한국 브랜드의 일본 Qoo10 자사몰을 경쟁사와 3-Layer(샵·상품·디자인)로 비교한 데이터를 받아,
임원 보고용 슬라이드의 '정성 서사'를 한국어로 작성합니다.

규칙(반드시 준수):
1. 모든 수치는 제공된 데이터에서만 인용한다. 데이터에 없는 숫자를 지어내지 않는다.
2. 자사(role=own)의 강점·약점을 경쟁사 대비로 진단하고, 개선 우선순위를 제시한다.
3. market_context(시장 트렌드)는 카테고리 일반 트렌드를 기술하되, 구체적 URL·통계를 날조하지 않는다.
   source 필드는 '(출처 검수 필요)'로 둔다. (사람이 검수 단계에서 실제 출처 확인)
4. 보고서 톤: 간결·단정·근거 기반. 과장·인사말·이모지 금지.
5. 각 항목 분량: findings.body ~2문장, SWOT 항목 ~12자, 권고 body ~2문장."""

USER_TMPL = """다음은 '{category}' 카테고리 경쟁분석 데이터입니다. 자사 대표샵: {own_name}.

[데이터(JSON)]
{brief}

위 데이터를 근거로 정성 서사를 작성하세요:
- findings: 핵심 발견 3개 (제목+본문). 자사 강점/병목/벤치마크 관점.
- conclusion: 한 문장 결론(핵심 레버).
- market_context: 시장 컨텍스트 3~4장 (head=주제, title=헤드라인, body=설명, source='(출처 검수 필요)').
- diagnosis_swot: S/W/O/T 각 3~4개 (데이터 근거).
- recommendation_quickwin: D+0~14 즉시 실행 4개 (title, kpi=목표지표, body).
- recommendation_structure: W2~M1 구조·콘텐츠 5개 (title, tag=요약태그, body).
- design_diagnosis_comments: 디자인 루브릭 5항목(현지화·샵 메인·프로모션 설계·일관성·썸네일) 각 코멘트.
- next_steps_phases: 로드맵 3단계 (period 고정: 'D+0 ~ D+14','W2 ~ M1','M1+'; title, body)."""


def _brief(spec: dict) -> dict:
    """AI에 넘길 데이터 요약(군더더기 제거)."""
    return {
        "category": spec["category_label"],
        "shops": [{"name": s["name"], "role": s["role"], "tagline": s.get("tagline", "")}
                  for s in spec["shops"]],
        "metrics": {sid: {k: m[k] for k in ("sku", "price_median", "review_volume",
                    "top5_power", "set_ratio", "jp_limited", "satisfaction",
                    "followers", "promo_intensity") if k in m}
                    for sid, m in spec["metrics"].items()},
        "design_scores": {sid: {k: d[k] for k in ("thumbnail", "shop_main", "localization",
                          "promo_design", "consistency", "total", "rank")}
                          for sid, d in spec["design_scores"].items()},
        "gap": spec["gap"],
        "tone": spec["marketing"].get("tone", {}),
        "collabs": spec["marketing"].get("collabs", []),
        "event_intensity": spec["marketing"].get("event_intensity", []),
    }


def draft_narrative(spec: dict) -> dict:
    """spec(데이터부 채워짐) → narrative.* 를 AI 초안으로 채운 spec 반환."""
    import anthropic
    client = anthropic.Anthropic()   # ANTHROPIC_API_KEY 환경변수/‑.env

    own = next((s for s in spec["shops"] if s["role"] == "own"), spec["shops"][0])
    brief = json.dumps(_brief(spec), ensure_ascii=False, indent=1)
    user = USER_TMPL.format(category=spec["category_label"], own_name=own["name"], brief=brief)

    resp = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},   # effort 기본값 high
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=NarrativeDraft,
    )
    d: NarrativeDraft = resp.parsed_output

    nar = spec["narrative"]
    # 데이터 자동(KPI·footnote·sources)은 유지, AI가 서사만 채움
    nar["exec_summary"]["findings"] = [f.model_dump() for f in d.findings[:3]]
    nar["exec_summary"]["conclusion"] = d.conclusion
    nar["market_context"] = [m.model_dump() for m in d.market_context[:4]]
    nar["diagnosis_swot"] = d.diagnosis_swot.model_dump()
    nar["recommendation_quickwin"] = [r.model_dump() for r in d.recommendation_quickwin[:4]]
    nar["recommendation_structure"] = [r.model_dump() for r in d.recommendation_structure[:5]]
    # 디자인 진단: 점수는 데이터, 코멘트만 AI로 교체
    comment_by_item = {c.item: c.comment for c in d.design_diagnosis_comments}
    for item in nar.get("design_diagnosis", []):
        if item["item"] in comment_by_item:
            item["comment"] = comment_by_item[item["item"]]
    # 로드맵: period 고정, body는 AI
    ai_phase = {p.period: p for p in d.next_steps_phases}
    for ph in nar["next_steps"]["phases"]:
        if ph["period"] in ai_phase:
            ph["title"] = ai_phase[ph["period"]].title or ph["title"]
            ph["body"] = ai_phase[ph["period"]].body
    spec["review"]["status"] = "draft"      # AI 초안 — 사람 승인 전
    spec["review"]["editor"] = "ai_draft"
    return spec, resp.usage


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main():
    spec_path = _arg("--spec")
    if not spec_path:
        print("usage: python draft_narrative.py --spec <spec.json> [--out <out.json>] [--pptx <out.pptx>]")
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 미설정 — 환경변수 또는 .env 에 키를 넣어주세요.")
        return 2
    spec = json.load(open(spec_path, encoding="utf-8"))
    print(f"서사 초안 생성 중 (model={MODEL}) …")
    spec, usage = draft_narrative(spec)
    out = _arg("--out", spec_path.replace(".json", "_drafted.json"))
    json.dump(spec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 서사 초안 완료: {out}")
    print(f"   findings {len(spec['narrative']['exec_summary']['findings'])} · "
          f"SWOT {sum(len(spec['narrative']['diagnosis_swot'][k]) for k in 'SWOT')}항목 · "
          f"QuickWin {len(spec['narrative']['recommendation_quickwin'])} · "
          f"구조 {len(spec['narrative']['recommendation_structure'])} · "
          f"시장컨텍스트 {len(spec['narrative']['market_context'])}")
    print(f"   토큰: in={usage.input_tokens} out={usage.output_tokens}")
    # 스키마 검증
    try:
        import jsonschema
        schema = json.load(open(ROOT / "schemas" / "report_spec.schema.json", encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(spec)
        print("   스키마 검증 통과 ✅")
    except Exception as e:
        print(f"   ⚠️ 스키마 경고: {str(e)[:120]}")
    pptx = _arg("--pptx")
    if pptx:
        from deck.build import build_deck
        build_deck(spec, pptx)
        print(f"✅ 덱 생성: {pptx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
