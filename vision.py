"""비전 컨셉 분석 — 상세컷(상세페이지 디자인 이미지)을 Claude 비전으로 OCR·해석.

수집(collect.py --details)이 받아둔 상품 상세컷(image_assets.asset_type='detail')을
Claude(claude-opus-4-8)에 보내 상품별 **컨셉·소구점·히어로카피·타깃·핵심성분·톤**을
구조화 추출해 product_concepts 에 적재한다.

한국 화장품 상세페이지는 매우 길어(높이 2000~3000px) 그대로 보내면 다운스케일돼
일본어 텍스트가 뭉개진다 → 세로 타일 분할 후 가독성을 유지해 전송한다.

선행: 환경변수 ANTHROPIC_API_KEY (또는 `ant auth login`).

사용:
  python vision.py --group skincare              # 미분석 상품만
  python vision.py --group skincare --refresh     # 전체 재분석
  python vision.py --group skincare --limit 1      # 스모크(1상품, 비용 확인)
"""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

from db import connect, upsert_product_concept
from shops_groups import own_shop_ids, resolve_group

ROOT = Path(__file__).parent
OUT = ROOT / "out"
MODEL = "claude-opus-4-8"

MAX_TILES = 8        # 상품당 최대 타일 수(비용 상한)
TILE_W = 780         # 타일 폭(원본 상세컷 폭과 동일, 다운스케일 없음)
TILE_H = 1040        # 타일 높이(≈A4 비율, 텍스트 가독 유지)
TALL_RATIO = 1.4     # 높이/폭 > 이 값이면 세로 분할

SYSTEM = """あなたは日本の化粧品EC(Qoo10ジャパン)の商品詳細ページ(デザイン画像)を分析する\
マーケティング・アナリストです。与えられた画像は韓国コスメ商品の「詳細ページ」を縦に分割した\
ものです。画像内の日本語テキスト(キャッチコピー・成分・使用方法・ターゲット訴求)を読み取り(OCR)、\
ビジュアルのトーンも踏まえて、商品の「コンセプト」と「訴求ポイント」を構造化して抽出してください。

ルール:
- concept / selling_points / target / tone は日本市場向けの分析として**韓国語**で簡潔に記述。
- hero_copy は詳細ページ内の代表的な見出しコピーを**原文(日本語)のまま**1つ抜き出す。
- key_ingredients は成分名を原文表記のまま列挙(例: アゼライン酸, CICA, ヒアルロン酸)。
- 画像から読み取れない項目は推測で埋めず、空文字/空配列にする。
必ず record_concept ツールを使って結果を返すこと。"""

CONCEPT_TOOL = {
    "name": "record_concept",
    "description": "상세컷에서 추출한 상품 컨셉·소구점을 기록한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "concept": {"type": "string", "description": "상품 핵심 컨셉 한 문장(한국어)"},
            "selling_points": {"type": "array", "items": {"type": "string"},
                               "description": "핵심 소구점 3~6개(한국어, 각 짧게)"},
            "hero_copy": {"type": "string", "description": "대표 헤드라인 카피(원문 일본어 그대로)"},
            "target": {"type": "string", "description": "타깃 고객/피부고민(한국어)"},
            "key_ingredients": {"type": "array", "items": {"type": "string"},
                                "description": "핵심 성분(원문 표기)"},
            "tone": {"type": "string", "description": "톤앤매너/디자인 무드 한 줄(한국어)"},
        },
        "required": ["concept", "selling_points", "hero_copy", "target",
                     "key_ingredients", "tone"],
    },
}


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


# ── 타일링 ────────────────────────────────────────────────────────────────
def tile_image(path: Path) -> list[bytes]:
    """긴 상세컷을 세로로 분할해 JPEG 바이트 타일 리스트로 반환."""
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return []
    w, h = im.size
    # 폭이 너무 크면 TILE_W로 다운스케일(텍스트 가독 유지)
    if w > TILE_W:
        h = int(h * TILE_W / w)
        im = im.resize((TILE_W, h), Image.LANCZOS)
        w = TILE_W
    tiles: list[bytes] = []
    if h <= w * TALL_RATIO:
        segs = [(0, h)]
    else:
        n = max(1, round(h / TILE_H))
        step = h // n
        segs = [(i * step, (i + 1) * step if i < n - 1 else h) for i in range(n)]
    for top, bot in segs:
        buf = io.BytesIO()
        im.crop((0, top, w, bot)).save(buf, format="JPEG", quality=85)
        tiles.append(buf.getvalue())
    return tiles


def _image_block(data: bytes) -> dict:
    return {"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg",
        "data": base64.standard_b64encode(data).decode("ascii")}}


# ── 분석 ──────────────────────────────────────────────────────────────────
def analyze_product(client, name: str, image_paths: list[str]) -> tuple[dict, object]:
    """상품 상세컷들을 타일링해 Claude 비전 호출 → 구조화 결과 + usage 반환."""
    tiles: list[bytes] = []
    for p in image_paths:
        if len(tiles) >= MAX_TILES:
            break
        tiles.extend(tile_image(ROOT / p))
    tiles = tiles[:MAX_TILES]
    if not tiles:
        raise ValueError("타일 없음(상세컷 로드 실패)")

    content = [_image_block(t) for t in tiles]
    content.append({"type": "text",
                    "text": f"商品名: {name}\n上の詳細ページ画像を分析し、record_conceptで返してください。"})

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[CONCEPT_TOOL],
        tool_choice={"type": "tool", "name": "record_concept"},
        messages=[{"role": "user", "content": content}],
    )
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    if block is None:
        raise ValueError(f"tool_use 없음 (stop_reason={resp.stop_reason})")
    return block.input, resp.usage


def _row_for_db(data: dict) -> dict:
    return {
        "model": MODEL,
        "concept": data.get("concept", ""),
        "selling_points": json.dumps(data.get("selling_points", []), ensure_ascii=False),
        "hero_copy": data.get("hero_copy", ""),
        "target": data.get("target", ""),
        "key_ingredients": json.dumps(data.get("key_ingredients", []), ensure_ascii=False),
        "tone": data.get("tone", ""),
        "raw_json": json.dumps(data, ensure_ascii=False),
    }


def targets(conn, group: str, refresh: bool, limit: int | None):
    """그룹 내 상세컷 보유 상품 중 분석 대상(code, name, shop_id, [paths])."""
    shop_ids = [s["shop_id"] for s in resolve_group(group)]
    qmarks = ",".join("?" * len(shop_ids))
    rows = conn.execute(
        f"""SELECT ia.goods_code, p.name, p.shop_id, GROUP_CONCAT(ia.path, '|')
            FROM image_assets ia JOIN products p ON p.goods_code = ia.goods_code
            WHERE ia.asset_type='detail' AND p.shop_id IN ({qmarks})
            GROUP BY ia.goods_code""",
        shop_ids).fetchall()
    out = []
    for code, name, shop_id, paths in rows:
        if not refresh and conn.execute(
                "SELECT 1 FROM product_concepts WHERE goods_code=?", (code,)).fetchone():
            continue
        out.append((code, name or "", shop_id, sorted((paths or "").split("|"))))
    return out[:limit] if limit else out


def write_csv(conn, group: str) -> Path:
    OUT.mkdir(exist_ok=True)
    own = set(own_shop_ids(group))
    shop_ids = [s["shop_id"] for s in resolve_group(group)]
    qmarks = ",".join("?" * len(shop_ids))
    rows = conn.execute(
        f"""SELECT p.shop_id, c.goods_code, p.name, c.concept, c.selling_points,
                   c.hero_copy, c.target, c.key_ingredients, c.tone
            FROM product_concepts c JOIN products p ON p.goods_code = c.goods_code
            WHERE p.shop_id IN ({qmarks}) ORDER BY p.shop_id""",
        shop_ids).fetchall()
    csv = OUT / f"concepts_{group}.csv"
    lines = ["shop_id,is_own,goods_code,name,concept,selling_points,hero_copy,target,key_ingredients,tone"]
    for sid, code, name, concept, sp, hero, target, ki, tone in rows:
        def q(x):
            return '"' + str(x or "").replace('"', "'").replace("\n", " ") + '"'
        lines.append(",".join([sid, "Y" if sid in own else "N", code,
                               q(name), q(concept), q(sp), q(hero), q(target), q(ki), q(tone)]))
    csv.write_text("\n".join(lines), encoding="utf-8-sig")
    return csv


def main():
    import anthropic
    group = _arg("--group", "skincare")
    refresh = "--refresh" in sys.argv
    limit = int(_arg("--limit")) if "--limit" in sys.argv else None

    conn = connect()
    todo = targets(conn, group, refresh, limit)
    if not todo:
        print(f"분석 대상 없음 (group={group}). 먼저 `collect.py --details` 로 상세컷 수집 필요.")
        return

    client = anthropic.Anthropic()
    print(f"=== 비전 컨셉 분석: {group} — {len(todo)}개 상품 (model={MODEL}) ===")
    in_tok = out_tok = 0
    done = 0
    for code, name, sid, paths in todo:
        try:
            data, usage = analyze_product(client, name, paths)
        except Exception as e:
            print(f"  [{sid}] {code} 실패: {e}")
            continue
        upsert_product_concept(conn, code, _row_for_db(data))
        conn.commit()
        in_tok += usage.input_tokens + getattr(usage, "cache_read_input_tokens", 0) \
            + getattr(usage, "cache_creation_input_tokens", 0)
        out_tok += usage.output_tokens
        done += 1
        sp = " · ".join(data.get("selling_points", [])[:3])
        print(f"  [{sid}] {code} ✓ {data.get('concept','')[:40]} | {sp}")

    csv = write_csv(conn, group)
    # 비용 추정(Opus 4.8: $5/$25 per 1M)
    cost = in_tok / 1e6 * 5 + out_tok / 1e6 * 25
    print(f"\n완료: {done}/{len(todo)}개 · 토큰 in={in_tok:,} out={out_tok:,} "
          f"· 추정 ${cost:.2f}\nCSV: {csv}")


if __name__ == "__main__":
    main()
