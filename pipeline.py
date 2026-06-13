"""웹 트리거 라이브 수집 → 분석 파이프라인 (백그라운드 잡).

URL 입력 → 샵별 라이브 수집(scrape_shop_full + persist) → build_spec(데이터부) → spec 저장.
수집은 수 분 걸리므로 web/app.py 가 스레드로 run_project 를 돌리고, JOBS 로 진행상태를 폴링한다.
(단일 사용자·사내 전용 기준. 멀티유저·재시작 내구성은 M3 잡큐로 확장.)
"""
from __future__ import annotations
import asyncio
import datetime
import time
import traceback

from db import connect
from scraper import scrape_shop_full
from collect import persist
from shops_groups import GROUPS
import build_spec as BS

WAIT_SEC = 5  # 샵 간 매너 대기

# pid -> {"state": queued|collecting|analyzing|done|error, "msg": str, "i": int, "n": int}
JOBS: dict[str, dict] = {}


def collect_one(shop_id: str, url: str) -> int:
    """단일 샵 라이브 수집 + db 적재. (스레드별 자체 db 커넥션)
    capture_images=True: 샵 톱 풀캡처·배너 수집 → 디자인 비전 채점·갤러리에 사용."""
    cap = asyncio.run(scrape_shop_full(shop_id, url, capture_images=True, debug=False))
    conn = connect()
    try:
        persist(conn, {"shop_id": shop_id}, cap)
    finally:
        conn.close()
    return len(cap.items)


def run_project(pid: str, project: dict, generated_at: str, save_fn) -> None:
    """백그라운드 잡: 수집 → build_spec → save_fn(pid, spec). JOBS[pid] 로 진행 보고."""
    shops = project["shops"]
    n = len(shops)
    JOBS[pid] = {"state": "collecting", "msg": "수집 준비…", "i": 0, "n": n}
    try:
        today = datetime.date.today().isoformat()
        conn = connect()
        for i, s in enumerate(shops):
            JOBS[pid] = {"state": "collecting", "msg": f"수집 {i + 1}/{n} — {s['id']}", "i": i, "n": n}
            last = conn.execute("SELECT MAX(snap_date) FROM shop_snapshots WHERE shop_id=?",
                                (s["id"],)).fetchone()[0]
            has_img = conn.execute("SELECT 1 FROM image_assets WHERE shop_id=? LIMIT 1",
                                   (s["id"],)).fetchone()
            if last == today and has_img:
                continue  # 오늘 이미 수집됨(이미지 포함) → 스킵
            try:
                collect_one(s["id"], s["url"])
            except Exception as e:
                print(f"[pipeline] {s['id']} 수집 실패: {e} (계속)")
            if i < n - 1:
                time.sleep(WAIT_SEC)  # 매너
        conn.close()

        # 디자인 비전 채점 (샵 톱 캡처 → Claude → 5항목 점수 + 톤·캡션)
        import design_vision as DV
        import anthropic
        try:
            client = anthropic.Anthropic()
        except Exception:
            client = None
        for i, s in enumerate(shops):
            JOBS[pid] = {"state": "scoring", "msg": f"디자인 평가 {i + 1}/{n} — {s['id']}", "i": i, "n": n}
            try:
                DV.score_shop_design(s["id"], client=client)
            except Exception as e:
                print(f"[pipeline] {s['id']} 디자인 채점 실패: {e} (계속)")

        JOBS[pid] = {"state": "analyzing", "msg": "데이터 분석·보고서 조립…", "i": n, "n": n}
        GROUPS[project["gname"]] = {
            "label": project["category"],
            "own": [s["id"] for s in shops if s["role"] == "own"],
            "competitors": [s["id"] for s in shops if s["role"] == "competitor"],
        }
        spec = BS.build_spec(project["gname"], generated_at=generated_at)
        save_fn(pid, spec)
        JOBS[pid] = {"state": "done", "msg": "완료", "i": n, "n": n}
    except SystemExit as e:
        JOBS[pid] = {"state": "error", "msg": str(e), "i": 0, "n": n}
    except Exception as e:
        traceback.print_exc()
        JOBS[pid] = {"state": "error", "msg": f"{type(e).__name__}: {e}", "i": 0, "n": n}
