"""design_vision — 샵 캡처(샵 톱 풀페이지·배너)를 Claude 비전으로 디자인 루브릭 자동채점.

images.py 가 수집한 shoptop(샵 톱 풀캡처)·hero·banner 를 claude-opus-4-8 에 보내
썸네일·샵메인·현지화·프로모션설계·일관성 5항목을 1~5점 + 근거로 채점 →
design_scores 테이블(scorer='vision') 적재. 톤앤매너·기획전·갤러리 캡션도 함께 추출해
out/vision_design/{shop}.json 저장 → build_spec 이 새 샵의 디자인/톤/갤러리 슬라이드를 채운다.

비전 1회/샵 (~수십 원). vision.py 의 타일 분할(긴 캡처 가독 유지)을 재사용.
"""
from __future__ import annotations
import datetime
import json
import os
from pathlib import Path

from db import connect
from vision import tile_image, _image_block, MAX_TILES  # 재사용

ROOT = Path(__file__).parent
OUT = ROOT / "out"
MODEL = "claude-opus-4-8"


def _load_env():
    """.env(KEY=VALUE) 로드 — 단독 실행 시에도 ANTHROPIC_API_KEY 확보."""
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

SYSTEM = """あなたは日本のQoo10ジャパンに出店するブランド公式ショップの「トップページ」デザインを\
評価するEC・クリエイティブの専門アナリストです。与えられた画像は、あるショップのトップページ\
(メインバナー・特集/企画展・クーポン導線・商品グリッド)を縦に分割したものです。\
画像内の日本語を読み取り、ビジュアルの完成度を踏まえて、次の5項目を各1〜5点(5=最高)で採点してください。

採点基準:
- thumbnail(썸네일, 25%): ソーシャルプルーフ/受賞バッジ + ベネフィット可視化 + トーン統一
- shop_main(샵 메인, 20%): ストーリー・企画展・ランキング・イベント区画の体系化
- localization(현지화, 20%): TPO/ライフスタイルカット・UGC・日本の情緒に合うコピー(韓国語直訳でない)
- promo_design(프로모션 설계, 20%): クーポン・タイムセール・セットの有機的な導線設計
- consistency(일관성, 15%): カラー・フォント・レイアウトの一貫性

ルール:
- スコアは画像から読み取れる事実に基づくこと。判断材料が乏しい場合は中央値寄りにし、過大評価しない。
- comments は各項目の根拠を**韓国語**で簡潔に(各〜20자)。
- mood は톤앤매너を韓国語で一行、campaign は現在のメイン企画/キャンペーンを一行(日本語原文可)、
  caption はギャラリー用の短い一行要約(韓国語, 点数は含めない)。
- 必ず record_design ツールで返すこと。"""

_ITEM = lambda d: {"type": "integer", "minimum": 1, "maximum": 5, "description": d}
DESIGN_TOOL = {
    "name": "record_design",
    "description": "샵 톱 페이지 디자인을 5항목 루브릭으로 채점한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "thumbnail": _ITEM("썸네일(소셜프루프·베네핏 시각화·톤 통일)"),
            "shop_main": _ITEM("샵 메인(스토리·기획전·랭킹·이벤트 구좌 체계화)"),
            "localization": _ITEM("현지화(TPO 컷·UGC·일본 정서 카피)"),
            "promo_design": _ITEM("프로모션 설계(쿠폰·타임세일·세트 동선)"),
            "consistency": _ITEM("일관성(컬러·폰트·레이아웃)"),
            "comments": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in
                               ("thumbnail", "shop_main", "localization", "promo_design", "consistency")},
                "description": "항목별 근거(한국어 간결)",
            },
            "mood": {"type": "string", "description": "톤앤매너 한 줄(한국어)"},
            "campaign": {"type": "string", "description": "현재 메인 캠페인/기획전 한 줄(원문 가능)"},
            "caption": {"type": "string", "description": "갤러리용 한 줄 요약(한국어, 점수 제외)"},
        },
        "required": ["thumbnail", "shop_main", "localization", "promo_design",
                     "consistency", "mood", "campaign", "caption"],
    },
}


def _design_images(conn, shop_id: str) -> list[str]:
    """샵의 디자인 평가용 캡처 경로: shoptop(풀캡처) 우선, 없으면 hero·banner."""
    for t in ("shoptop", "hero", "banner"):
        rows = conn.execute(
            "SELECT path FROM image_assets WHERE shop_id=? AND asset_type=? ORDER BY captured_at DESC",
            (shop_id, t)).fetchall()
        if rows:
            return [r[0] for r in rows[:3]]
    return []


def score_shop_design(shop_id: str, client=None):
    """단일 샵 디자인 비전 채점 → design_scores 적재 + json 저장. (결과, usage) | None."""
    import anthropic
    conn = connect()
    paths = _design_images(conn, shop_id)
    if not paths:
        conn.close()
        return None
    tiles: list[bytes] = []
    for p in paths:
        if len(tiles) >= MAX_TILES:
            break
        tiles.extend(tile_image(ROOT / p))
    tiles = tiles[:MAX_TILES]
    if not tiles:
        conn.close()
        return None

    client = client or anthropic.Anthropic()
    content = [_image_block(t) for t in tiles]
    content.append({"type": "text", "text":
                    "上の画像はこのショップのトップページ(メインバナー・特集・クーポン・商品グリッド)です。"
                    "record_design で5項目を採点してください。"})
    resp = client.messages.create(
        model=MODEL, max_tokens=1500,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[DESIGN_TOOL], tool_choice={"type": "tool", "name": "record_design"},
        messages=[{"role": "user", "content": content}],
    )
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    if block is None:
        conn.close()
        return None
    d = block.input

    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute("DELETE FROM design_scores WHERE shop_id=? AND scorer='vision'", (shop_id,))
    conn.execute(
        """INSERT OR REPLACE INTO design_scores
           (shop_id, scored_at, thumbnail, shop_main, localization, promo_design,
            consistency, scorer, note)
           VALUES (?,?,?,?,?,?,?, 'vision', ?)""",
        (shop_id, now, d["thumbnail"], d["shop_main"], d["localization"],
         d["promo_design"], d["consistency"], json.dumps(d.get("comments", {}), ensure_ascii=False)))
    conn.commit()
    conn.close()

    (OUT / "vision_design").mkdir(parents=True, exist_ok=True)
    (OUT / "vision_design" / f"{shop_id}.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d, resp.usage


def load_vision_meta(shop_id: str) -> dict:
    """build_spec 용: 저장된 비전 디자인 메타(mood·campaign·caption·comments) 로드."""
    p = OUT / "vision_design" / f"{shop_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}
