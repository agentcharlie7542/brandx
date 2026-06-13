"""build_spec — 수집·스코어링·마케팅 결과(db) → report-spec(JSON) 데이터부 자동 조립.

개발정의서 §5 단일 계약을 채운다. 정량/디자인/콜라보/이벤트/갤러리는 **자동**,
정성 서사(narrative.*)는 **AI 초안 대기 placeholder** — 이후 narrative 드래프터(Claude)가 채우고
사람이 웹 검수에서 확정한다(review.status: draft→approved).

사용:
  python build_spec.py --group makeup --out samples/spec_makeup_auto.json
  python build_spec.py --group makeup --pptx out/auto_makeup.pptx     # spec + 바로 덱 생성
"""
from __future__ import annotations
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd

from score import build_scorecard
from marketing import mine, TONE
from shops_groups import group_label, resolve_group
from db import connect
import design_vision as DV

ROOT = Path(__file__).parent
OUT = ROOT / "out"

# 갭 분석 대상(higher-is-better) + 라벨·시사점
GAP_METRICS = [
    ("review_volume", "리뷰 볼륨", "리뷰적립·물량"),
    ("promo_intensity", "프로모션 강도", "메가와리·쿠폰 확대"),
    ("follower_count", "팔로워", "고객자산 확보"),
    ("satisfaction_pct", "만족도", "운영품질 유지"),
    ("design_total", "디자인 총점", "강점 유지"),
]
RUBRIC_ITEMS = [   # (key, 표시명) — 진단 표시 순서(강점→약점은 점수로 재정렬)
    ("localization", "현지화"), ("shop_main", "샵 메인"),
    ("promo_design", "프로모션 설계"), ("consistency", "일관성"), ("thumbnail", "썸네일"),
]


# ── 포매터 ──────────────────────────────────────────────
def f_followers(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    v = float(v)
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{round(v/1000)}K"
    return str(int(v))

def f_man(v):  # 만 단위 한국어
    return f"{round(v/10000, 1):g}만" if v and v >= 10000 else (f"{int(v)}" if v else "—")

def _num(x, cast=float, default=None):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return default
        return cast(x)
    except Exception:
        return default

def _score_fmt(v):
    s = f"{v:.2f}"
    return s[:-1] if s.endswith("0") else s


# ── 데이터부 조립 ───────────────────────────────────────
def _metrics_and_design(df):
    metrics, design = {}, {}
    for _, r in df.iterrows():
        sid = r["shop_id"]
        t5 = _num(r.get("top5_power"))
        metrics[sid] = {
            "sku": _num(r.get("sku_count"), int, 0),
            "price_min": _num(r.get("price_min")),
            "price_median": _num(r.get("price_median")) or 0,
            "price_max": _num(r.get("price_max")),
            "review_volume": _num(r.get("review_volume"), int, 0),
            "review_capped": bool(t5 is not None and t5 >= 0.99),
            "top5_power": t5 if t5 is not None else 0.0,
            "set_ratio": _num(r.get("set_ratio"), float, 0.0),
            "jp_limited": _num(r.get("jp_limited_count"), int, 0),
            "satisfaction": _num(r.get("satisfaction_pct"), float, 0.0),
            "followers": _num(r.get("follower_count"), int, 0),
            "seller_grade": r.get("seller_grade") if isinstance(r.get("seller_grade"), str) else None,
            "promo_intensity": _num(r.get("promo_intensity"), float, 0.0),
            "est_revenue_30d": _num(r.get("est_revenue_30d")),
        }
        if _num(r.get("design_total")) is not None:
            design[sid] = {
                "thumbnail": _num(r.get("thumbnail"), float, 0.0),
                "shop_main": _num(r.get("shop_main"), float, 0.0),
                "localization": _num(r.get("localization"), float, 0.0),
                "promo_design": _num(r.get("promo_design"), float, 0.0),
                "consistency": _num(r.get("consistency"), float, 0.0),
                "total": round(_num(r.get("design_total"), float, 0.0), 2),
                "rank": _num(r.get("design_rank"), int),
                "scorer": "ai_draft",   # rubric_{group}.csv = AI 초안(잠정)
            }
    return metrics, design


def _gap(df, own_id):
    own = df[df["shop_id"] == own_id].iloc[0]
    rows = []
    for col, label, note in GAP_METRICS:
        if col not in df or df[col].isna().all():
            continue
        leader_val = df[col].max()
        leader_shop = df.loc[df[col].idxmax(), "shop_id"]
        own_val = _num(own.get(col), float, 0.0)
        if not leader_val:
            continue
        rows.append({
            "metric": col, "label": label,
            "own": round(own_val, 2), "leader": round(float(leader_val), 2),
            "leader_shop": leader_shop,
            "achievement_pct": round(own_val / leader_val * 100, 1),
            "note": note,
        })
    return sorted(rows, key=lambda g: g["achievement_pct"])


def _gallery(shops, design, mined, cap_img):
    cards = []
    ordered = [s for s in shops if s["role"] == "own"] + [s for s in shops if s["role"] != "own"]
    for s in ordered:
        sid = s["shop_id"]
        vm = DV.load_vision_meta(sid)
        banner = OUT / "banners" / f"{sid}_main.jpg"
        if banner.exists():
            image = str(banner.relative_to(ROOT))
        elif cap_img.get(sid):
            image = cap_img[sid]        # 수집 캡처(hero/banner/shoptop) fallback
        else:
            image = f"out/banners/{sid}_main.jpg"
        tone = TONE.get(sid, {}).get("tone", "")
        caption = (vm.get("caption") or tone.split(".")[0].split(",")[0].strip())[:28] \
            or (s.get("name") or sid)
        cards.append({
            "shop_id": sid, "image": image,
            "score": round(design.get(sid, {}).get("total", 0.0), 2),
            "caption": caption,
        })
    return cards


def _marketing(shops, mined, metrics):
    tone, collabs, events = {}, [], []
    for s in shops:
        sid = s["shop_id"]
        d = mined.get(sid, {})
        m = metrics.get(sid, {})
        t = TONE.get(sid, {})
        if t:                                     # 큐레이션된 샵
            mood = t.get("tone", "").split(".")[0].strip() or "—"
            campaign = t.get("hero", "—")
        else:                                     # 새 샵 → 비전 채점 결과
            vm = DV.load_vision_meta(sid)
            mood = vm.get("mood") or "—"
            campaign = vm.get("campaign") or "—"
        tone[sid] = {"mood": mood, "campaign": campaign}
        for ip in d.get("ip_collabs", []):
            collabs.append({"shop_id": sid, "partner": ip, "type": "IP"})
        for c in d.get("collabs", []):
            collabs.append({"shop_id": sid, "partner": c["partner"], "type": "influencer",
                            "note": f"{c['count']}건"})
        snap = d.get("snap") or [None] * 8
        coupon = snap[3]
        events.append({
            "shop_id": sid,
            "coupon": int(coupon) if coupon else "-",
            "timesale": int(snap[5]) if snap[5] else 0,
            "avg_off": round(float(snap[6]), 1) if snap[6] else 0.0,
            "megawari": int(snap[7]) if snap[7] else 0,
            "set": int(round(m.get("set_ratio", 0.0) * m.get("sku", 0))),
        })
    return {"tone": tone, "collabs": collabs, "event_intensity": events}


# ── 서사부 placeholder (AI 초안 대기) ───────────────────
PH = "(AI 초안 대기 — 검수에서 확정)"

def _narrative_skeleton(df, own_id, design, group):
    own = df[df["shop_id"] == own_id].iloc[0]
    dt = design.get(own_id, {})
    rank = dt.get("rank")
    kpis = [
        {"value": f"{_score_fmt(dt.get('total', 0))} / 5.0",
         "label": f"디자인 총점 (그룹 {rank}위)" if rank else "디자인 총점"},
        {"value": f"¥{int(_num(own.get('price_median'), float, 0)):,}", "label": "가격 중앙값"},
        {"value": f_man(_num(own.get("follower_count"), float, 0)), "label": "팔로워"},
        {"value": f"{int(_num(own.get('satisfaction_pct'), float, 0))}%", "label": "만족도"},
    ]
    vcom = DV.load_vision_meta(own_id).get("comments", {})
    vcom = vcom if isinstance(vcom, dict) else {}
    diag = sorted(
        [{"item": lbl, "score": round(dt.get(key, 0.0), 1),
          "comment": (vcom.get(key) or _rubric_comment(dt.get(key, 0.0)))}
         for key, lbl in RUBRIC_ITEMS],
        key=lambda d: -d["score"])
    return {
        "exec_summary": {
            "kpis": kpis,
            "findings": [{"title": f"{PH}", "body": PH} for _ in range(3)],
            "conclusion": PH,
            "footnote": "리뷰볼륨은 큐텐 999+ 표기 상한 영향 — 절대비교보다 구조·추세 해석에 사용.",
        },
        "market_context": [],   # AI 보강(외부 리서치) 대기
        "design_diagnosis": diag,
        "diagnosis_swot": {"S": [PH], "W": [PH], "O": [PH], "T": [PH]},
        "recommendation_quickwin": [{"title": PH, "kpi": "", "body": PH} for _ in range(2)],
        "recommendation_structure": [],
        "next_steps": {
            "phases": [
                {"period": "D+0 ~ D+14", "title": "Quick Win", "body": PH},
                {"period": "W2 ~ M1", "title": "구조·콘텐츠", "body": PH},
                {"period": "M1+", "title": "확장·자산화", "body": PH},
            ],
            "sources": [
                "1차 데이터: Qoo10 샵·상품 수집 — 팔로워·만족도·가격·SKU 실측, 리뷰볼륨은 999+ 상한 영향",
                "디자인 루브릭: 샵 톱 캡처 기반 5항목 채점(AI 초안) / 마케팅: 상품명 자동 채굴 + 캡처 AI 시각분석(잠정)",
            ],
        },
    }

def _rubric_comment(v):
    if v >= 5:
        return "최상 — 그룹 최강 수준"
    if v >= 4:
        return "양호 — 소폭 보강 여지"
    if v >= 3:
        return "개선 필요 — 우선 보완 대상"
    return "약점 — 집중 개선 필요"


# ── 메인 조립 ───────────────────────────────────────────
def build_spec(group: str, generated_at: str | None = None) -> dict:
    df = build_scorecard(group)
    # 미수집 가드: 행은 있어도 지표 컬럼이 없거나 전부 NaN이면 수집 안 된 것
    if df.empty or "review_volume" not in df.columns or df["review_volume"].notna().sum() == 0:
        raise SystemExit(f"[{group}] 스코어 데이터 없음 — 먼저 collect.py/score.py 실행")
    shops_meta = resolve_group(group)
    role = {s["shop_id"]: s["role"] for s in shops_meta}
    name = {s["shop_id"]: s["name"] for s in shops_meta}
    url = {s["shop_id"]: s["url"] for s in shops_meta}
    mined = mine(group)

    # 대표 자사샵 = 자사 중 리뷰볼륨 최대
    own_df = df[df["shop_id"].map(lambda s: role.get(s) == "own")]
    own_id = own_df.loc[own_df["review_volume"].idxmax(), "shop_id"] if not own_df.empty \
        else df.iloc[0]["shop_id"]

    metrics, design = _metrics_and_design(df)
    # 갤러리용 캡처 이미지(배너 크롭 없으면 수집 캡처로 fallback) — hero>banner>shoptop
    cap_img = {}
    conn = connect()
    for sid in df["shop_id"]:
        for t in ("hero", "banner", "shoptop"):
            r = conn.execute("SELECT path FROM image_assets WHERE shop_id=? AND asset_type=? LIMIT 1",
                             (sid, t)).fetchone()
            if r:
                cap_img[sid] = r[0]
                break
    conn.close()
    shops = [{"id": sid, "name": name.get(sid, sid), "role": role.get(sid, "competitor"),
              "url": url.get(sid, f"https://www.qoo10.jp/shop/{sid}"),
              "tagline": (TONE.get(sid, {}).get("tone", "").split(".")[0][:18]
                          or DV.load_vision_meta(sid).get("mood", "")[:18])}
             for sid in df["shop_id"]]

    spec = {
        "spec_version": "1.0",
        "project_id": f"auto-{group}",
        "category_label": group_label(group),
        "generated_at": generated_at or "(stamp-on-save)",
        "prepared_by": "Aiden Lab",
        "shops": shops,
        "metrics": metrics,
        "design_scores": design,
        "gap": _gap(df, own_id),
        "gallery": _gallery(shops_meta, design, mined, cap_img),
        "marketing": _marketing(shops_meta, mined, metrics),
        "narrative": _narrative_skeleton(df, own_id, design, group),
        "review": {"status": "draft", "editor": "auto", "edited_at": generated_at or ""},
    }
    return spec


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main():
    group = _arg("--group", "makeup")
    spec = build_spec(group)
    out = _arg("--out", f"samples/spec_{group}_auto.json")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(spec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_own = sum(1 for s in spec["shops"] if s["role"] == "own")
    print(f"✅ spec 자동 조립: {out}")
    print(f"   {len(spec['shops'])}개 샵(자사 {n_own}) · gap {len(spec['gap'])} · "
          f"콜라보 {len(spec['marketing']['collabs'])} · 이벤트 {len(spec['marketing']['event_intensity'])}행")
    print(f"   서사: status=draft (AI 초안 대기) — narrative 드래프터/검수에서 확정")
    pptx = _arg("--pptx")
    if pptx:
        from deck.build import build_deck
        build_deck(spec, pptx)
        print(f"✅ 덱 생성: {pptx}")


if __name__ == "__main__":
    main()
