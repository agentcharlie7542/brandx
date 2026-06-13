"""웹 검수 UI (FastAPI) — 개발정의서 M4.

흐름: 그룹/URL 선택 → build_spec(데이터 자동) → narrative 폼 편집 → AI 초안 →
      승인(review.status=approved) → deck.build → PPTX 다운로드.
report-spec(JSON)이 단일 계약이라 화면은 이 JSON만 편집한다. 사내 전용·단일 사용자 기준.

실행:
  cd qoo10_scraper
  .venv/bin/uvicorn web.app:app --reload --port 8000
  → http://localhost:8000
"""
from __future__ import annotations
import html
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, PlainTextResponse

import threading

import build_spec as BS
import draft_narrative as DN
import pipeline as PL
from shops_groups import GROUPS
from deck.build import build_deck

PROJ = ROOT / "web" / "projects"
PROJ.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "out"
TODAY = "2026-06-13"

app = FastAPI(title="Qoo10 경쟁분석 보고서 생성기")


# ── 저장/로드 ───────────────────────────────────────────
def save_spec(pid: str, spec: dict):
    (PROJ / f"{pid}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

def load_spec(pid: str) -> dict:
    return json.loads((PROJ / f"{pid}.json").read_text(encoding="utf-8"))

def list_projects():
    out = []
    for p in sorted(PROJ.glob("*.json"), reverse=True):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
            out.append({"pid": p.stem, "label": s.get("category_label", p.stem),
                        "status": s.get("review", {}).get("status", "draft"),
                        "n": len(s.get("shops", []))})
        except Exception:
            pass
    return out


# ── HTML 헬퍼 ───────────────────────────────────────────
CSS = """
*{box-sizing:border-box} body{font-family:'Noto Sans KR',-apple-system,sans-serif;margin:0;
 background:#EFEEF6;color:#2B1B4D} a{color:#E0457B;text-decoration:none}
.bar{background:#2B1B4D;color:#fff;padding:18px 32px;display:flex;align-items:center;gap:14px}
.bar b{font-size:19px} .bar .tag{background:#E0457B;border-radius:20px;padding:2px 12px;font-size:12px}
.wrap{max-width:1100px;margin:26px auto;padding:0 24px}
.card{background:#fff;border-radius:12px;padding:22px 24px;margin-bottom:18px;
 box-shadow:0 2px 10px rgba(26,20,48,.06)}
.card h2{margin:0 0 14px;font-size:17px} .card h3{margin:18px 0 8px;font-size:14px;color:#3D2A6B}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.btn{display:inline-block;background:#E0457B;color:#fff;border:0;border-radius:8px;
 padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn.sec{background:#3D2A6B} .btn.ghost{background:#EAE4F5;color:#3D2A6B}
.btn.big{padding:13px 26px;font-size:15px}
input,textarea,select{width:100%;border:1px solid #D8D2EA;border-radius:7px;padding:9px 11px;
 font-family:inherit;font-size:13px;color:#2B1B4D;background:#fff}
textarea{resize:vertical;min-height:58px} label{font-size:12px;color:#6B6385;display:block;margin:8px 0 3px}
table{width:100%;border-collapse:collapse;font-size:12.5px} th{background:#3D2A6B;color:#fff;padding:7px 8px;text-align:center}
td{padding:6px 8px;border-bottom:1px solid #EEE;text-align:center} td.l{text-align:left;font-weight:700}
tr.own td{background:#FBEFF4} .badge{border-radius:20px;padding:2px 11px;font-size:11px;font-weight:700;color:#fff}
.b-draft{background:#E08E0B} .b-approved{background:#3FA864}
.gcard{border:1px solid #E3DFF0;border-radius:10px;padding:14px 16px}
.muted{color:#8A82A6;font-size:12px} .row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.note{background:#FBEFF4;border-left:4px solid #E0457B;padding:10px 14px;border-radius:6px;font-size:13px;margin:10px 0}
"""

def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>{CSS}</style></head><body>
<div class=bar><b>Qoo10 경쟁분석 보고서 생성기</b><span class=tag>사내 전용</span>
<span style="margin-left:auto"><a href="/" style="color:#CFC8E2">← 홈</a></span></div>
<div class=wrap>{body}</div></body></html>""")

def esc(v): return html.escape(str(v if v is not None else ""))
def badge(st): return f'<span class="badge b-{st}">{st}</span>'


# ── 홈 ──────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home():
    projlist = ""
    for p in list_projects():
        projlist += f'<tr><td class=l><a href="/p/{p["pid"]}">{esc(p["label"])}</a></td>' \
                    f'<td>{p["n"]}샵</td><td>{badge(p["status"])}</td>' \
                    f'<td class=muted>{esc(p["pid"])}</td></tr>'
    if projlist:
        projlist = f"<table><tr><th>프로젝트</th><th>샵</th><th>상태</th><th>ID</th></tr>{projlist}</table>"
    else:
        projlist = "<div class=muted>아직 프로젝트가 없습니다.</div>"

    body = f"""
    <div class=card><h2>분석 대상 입력 — 자사 1 + 경쟁사 1~3</h2>
      <p class=muted>각 샵의 Qoo10 URL을 입력하면 데이터 수집·분석 후 보고서를 생성합니다. 경쟁사는 1~3개(2·3은 선택).</p>
      <form method=post action="/analyze">
        <input type=hidden name=mode value=urls>
        <label>카테고리 라벨</label><input name=category placeholder="예: 색조 메이크업" required>
        <div class=row3 style="margin-top:8px">
          <div><label>자사 샵 URL</label><input name=own placeholder="https://www.qoo10.jp/shop/slug" required></div>
          <div><label>경쟁사 1</label><input name=c1 placeholder="https://www.qoo10.jp/shop/slug" required></div>
          <div><label>경쟁사 2 <span class=muted>(선택)</span></label><input name=c2 placeholder="https://www.qoo10.jp/shop/slug"></div>
        </div>
        <div class=row3 style="margin-top:8px">
          <div><label>경쟁사 3 <span class=muted>(선택)</span></label><input name=c3 placeholder="https://www.qoo10.jp/shop/slug"></div>
        </div>
        <div style="margin-top:16px"><button class="btn big">분석 시작 →</button></div>
        <div class=muted style="margin-top:8px">※ 새 샵은 Qoo10에서 직접 수집합니다(샵당 수십 초~수 분). 진행률이 표시됩니다.</div>
      </form></div>
    <div class=card><h2>최근 프로젝트</h2>{projlist}</div>"""
    return page("홈", body)


# ── 분석 시작 ───────────────────────────────────────────
def parse_shop(url: str):
    """Qoo10 샵 URL → 슬러그. 샵 URL(/shop/{slug})이 아니면 None (상품페이지 등 거부)."""
    url = (url or "").strip()
    if "/shop/" in url:
        slug = url.split("/shop/")[-1].split("/")[0].split("?")[0].strip()
        return slug or None
    return None

@app.post("/analyze")
async def analyze(request: Request):
    f = await request.form()
    own = parse_shop(f.get("own", ""))
    # 채워진 경쟁사 칸만 대상 (경쟁사 2·3은 선택 — 최소 1개)
    raw = [(f"경쟁사 {i}", (f.get(k, "") or "").strip()) for i, k in enumerate(("c1", "c2", "c3"), 1)]
    parsed = [(lbl, parse_shop(u), u) for lbl, u in raw if u]

    # 샵 URL 검증
    bad = []
    if not own:
        bad.append(("자사", f.get("own", "")))
    for lbl, c, u in parsed:
        if not c:
            bad.append((lbl, u))
    valid_comps = [c for lbl, c, u in parsed if c]
    if own and not valid_comps:
        bad.append(("경쟁사", "최소 1개 이상의 경쟁사 샵 URL을 입력하세요"))
    if bad:
        items = "".join(f"<li><b>{esc(lbl)}</b>: {esc(u or '(빈칸)')}</li>" for lbl, u in bad)
        return page("URL 확인", f"""<div class=card>
          <div class=note><b>샵 URL 형식이 아닙니다.</b> 각 칸에는
          <code>https://www.qoo10.jp/shop/&lt;슬러그&gt;</code> 형태의 <b>샵 URL</b>을 넣어주세요.
          (상품 상세 URL <code>/gmkt.inc/Goods/...</code> 는 샵이 아닙니다 — 상품 페이지에서 판매샵 이름을 클릭하면 샵 URL이 나옵니다.)</div>
          <ul>{items}</ul><a class=btn href="/">← 다시 입력</a></div>""")

    cat = f.get("category", "신규 카테고리") or "신규 카테고리"
    gname = f"web_{own}_{int(time.time())}"
    shops = [{"id": own, "url": f"https://www.qoo10.jp/shop/{own}", "role": "own", "name": own}] + \
            [{"id": c, "url": f"https://www.qoo10.jp/shop/{c}", "role": "competitor", "name": c}
             for c in valid_comps]
    project = {"category": cat, "gname": gname, "shops": shops}
    PL.JOBS[gname] = {"state": "queued", "msg": "대기 중…", "i": 0, "n": len(shops)}
    threading.Thread(target=PL.run_project, args=(gname, project, TODAY, save_spec),
                     daemon=True).start()
    return RedirectResponse(f"/p/{gname}", status_code=303)


# ── 검수 페이지 ─────────────────────────────────────────
def scorecard_html(spec):
    rows = ""
    order = sorted(spec["shops"], key=lambda s: spec["metrics"].get(s["id"], {}).get("review_volume", 0), reverse=True)
    for s in order:
        m = spec["metrics"].get(s["id"], {}); d = spec["design_scores"].get(s["id"], {})
        own = s["role"] == "own"
        rows += f"""<tr class="{'own' if own else ''}"><td class=l>{'★ ' if own else ''}{esc(s['name'])}</td>
          <td>{'자사' if own else '경쟁'}</td><td>{m.get('sku','')}</td><td>¥{int(m.get('price_median',0)):,}</td>
          <td>{int(m.get('review_volume',0)):,}</td><td>{d.get('total','')}</td>
          <td>{m.get('promo_intensity','')}</td><td>{int(m.get('followers',0)):,}</td></tr>"""
    return f"""<table><tr><th>샵</th><th>구분</th><th>SKU</th><th>가격중앙</th><th>리뷰볼륨</th>
      <th>디자인총점</th><th>프로모강도</th><th>팔로워</th></tr>{rows}</table>"""

def _ta(name, value, rows=2):
    return f'<textarea name="{name}" rows={rows}>{esc(value)}</textarea>'
def _in(name, value):
    return f'<input name="{name}" value="{esc(value)}">'

def narrative_form(spec):
    nar = spec["narrative"]; es = nar["exec_summary"]
    # 핵심 발견
    finds = ""
    for i, fnd in enumerate(es["findings"]):
        finds += f'<div class=gcard style="margin-bottom:10px"><label>발견 {i+1} 제목</label>{_in(f"find_{i}_title", fnd["title"])}' \
                 f'<label>본문</label>{_ta(f"find_{i}_body", fnd["body"])}</div>'
    # SWOT
    swot = ""
    names = {"S": "강점", "W": "약점", "O": "기회", "T": "위협"}
    for k in "SWOT":
        swot += f'<div><label>{names[k]} ({k}) — 한 줄에 하나</label>{_ta(f"swot_{k}", chr(10).join(nar["diagnosis_swot"][k]), 4)}</div>'
    # Quick Win
    qw = ""
    for i, r in enumerate(nar["recommendation_quickwin"]):
        qw += f'<div class=gcard style="margin-bottom:10px"><div class=grid><div><label>QuickWin {i+1} 제목</label>{_in(f"qw_{i}_title", r["title"])}</div>' \
              f'<div><label>KPI</label>{_in(f"qw_{i}_kpi", r["kpi"])}</div></div><label>본문</label>{_ta(f"qw_{i}_body", r["body"])}</div>'
    # 구조 권고
    st = ""
    for i, r in enumerate(nar["recommendation_structure"]):
        st += f'<div class=gcard style="margin-bottom:10px"><div class=grid><div><label>구조권고 {i+1} 제목</label>{_in(f"st_{i}_title", r["title"])}</div>' \
              f'<div><label>태그</label>{_in(f"st_{i}_tag", r["tag"])}</div></div><label>본문</label>{_ta(f"st_{i}_body", r["body"])}</div>'
    # 시장 컨텍스트
    mc = ""
    for i, c in enumerate(nar.get("market_context", [])):
        mc += f'<div class=gcard style="margin-bottom:10px"><div class=grid><div><label>컨텍스트 {i+1} 주제</label>{_in(f"mc_{i}_head", c["head"])}</div>' \
              f'<div><label>헤드라인</label>{_in(f"mc_{i}_title", c["title"])}</div></div><label>본문</label>{_ta(f"mc_{i}_body", c["body"])}</div>'
    if not mc:
        mc = '<div class=muted>(AI 초안 생성 시 채워집니다)</div>'
    # 로드맵
    ph = ""
    for i, p in enumerate(nar["next_steps"]["phases"]):
        ph += f'<div><label>{esc(p["period"])} — {esc(p["title"])}</label>{_ta(f"phase_{i}_body", p["body"])}</div>'

    return f"""
      <h3>핵심 발견 (3)</h3>{finds}
      <h3>결론</h3>{_ta("concl", es["conclusion"])}
      <h3>SWOT</h3><div class=grid>{swot}</div>
      <h3>Quick Win (D+0~14)</h3>{qw}
      <h3>구조·콘텐츠 권고 (W2~M1)</h3>{st}
      <h3>시장 컨텍스트</h3>{mc}
      <h3>로드맵 본문</h3><div class=row3>{ph}</div>"""

@app.get("/p/{pid}", response_class=HTMLResponse)
def review(pid: str, done: int = 0):
    if not (PROJ / f"{pid}.json").exists():
        # 아직 spec 없음 → 수집/분석 잡 진행 중이거나 에러
        job = PL.JOBS.get(pid)
        if not job:
            return page("없음", '<div class=card>프로젝트를 찾을 수 없습니다. <a href="/">홈</a></div>')
        if job["state"] == "error":
            return page("실패", f"""<div class=card>
              <div class=note><b>수집·분석에 실패했습니다.</b><br>{esc(job['msg'])}</div>
              <div class=muted>샵 URL이 유효한지, 해당 샵에 상품이 있는지 확인하세요. 처음 수집한 샵은
              추정매출 등 일부 지표가 비어 있을 수 있습니다.</div>
              <a class=btn href="/">← 다시 입력</a></div>""")
        n = job.get("n", 1) or 1
        pct = int(job.get("i", 0) / n * 100)
        phase = {"queued": "대기 중", "collecting": "라이브 수집 중",
                 "scoring": "디자인 비전 평가 중", "analyzing": "분석·보고서 조립 중"}.get(job["state"], job["state"])
        return page("진행 중", f"""<div class=card>
          <h2>⏳ {esc(phase)}</h2>
          <p class=muted>각 샵을 Qoo10에서 직접 수집 중입니다(샵당 수십 초~수 분, 매너상 5초 대기 포함). 이 화면은 자동 새로고침됩니다.</p>
          <div style="background:#EAE4F5;border-radius:20px;height:14px;overflow:hidden;margin:14px 0">
            <div style="background:#E0457B;height:100%;width:{pct}%;transition:width .3s"></div></div>
          <div style="font-size:14px"><b>{esc(job['msg'])}</b></div>
          <div class=muted style="margin-top:6px">상태: {esc(job['state'])} · {job.get('i',0)}/{n}</div>
          <meta http-equiv="refresh" content="3"></div>""")
    spec = load_spec(pid)
    st = spec["review"]["status"]
    is_ai = spec["review"].get("editor") == "ai_draft"
    dl = ""
    if done or (OUT / f"web_{pid}.pptx").exists():
        dl = f'<div class=note>✅ PPTX 생성 완료 → <a class=btn href="/p/{pid}/download">📥 다운로드</a></div>'
    body = f"""
    <div class=card><h2>{esc(spec['category_label'])} {badge(st)}</h2>
      <div class=muted>프로젝트 {esc(pid)} · {len(spec['shops'])}개 샵 · 생성 {esc(spec['generated_at'])}</div>
      {dl}
    </div>
    <div class=card><h2>데이터 (자동 — 읽기전용)</h2>{scorecard_html(spec)}
      <div class=muted style="margin-top:8px">KPI·스코어카드·갭·차트는 수집 데이터에서 자동 생성됩니다. 아래 정성 서사만 검수하세요.</div></div>
    <div class=card><h2>정성 서사 검수 {'<span class=muted>(AI 초안 — 검토 후 승인)</span>' if is_ai else '<span class=muted>(placeholder — AI 초안을 먼저 생성하세요)</span>'}</h2>
      <form method=post>
        <div style="margin:0 0 16px">
          <button class="btn ghost" formaction="/p/{pid}/draft" title="Claude로 서사 초안 생성(~$0.11)">🤖 AI 초안 {'재' if is_ai else ''}생성</button>
        </div>
        {narrative_form(spec)}
        <div style="margin-top:22px;display:flex;gap:10px">
          <button class="btn sec" formaction="/p/{pid}/save">💾 저장</button>
          <button class="btn big" formaction="/p/{pid}/approve">✅ 승인 & PPTX 생성</button>
        </div>
      </form></div>"""
    return page(spec["category_label"], body)


def apply_form(spec, f):
    nar = spec["narrative"]; es = nar["exec_summary"]
    for i in range(len(es["findings"])):
        es["findings"][i]["title"] = f.get(f"find_{i}_title", es["findings"][i]["title"])
        es["findings"][i]["body"] = f.get(f"find_{i}_body", es["findings"][i]["body"])
    es["conclusion"] = f.get("concl", es["conclusion"])
    for k in "SWOT":
        if f.get(f"swot_{k}") is not None:
            nar["diagnosis_swot"][k] = [l.strip() for l in f.get(f"swot_{k}").splitlines() if l.strip()]
    for i in range(len(nar["recommendation_quickwin"])):
        r = nar["recommendation_quickwin"][i]
        r["title"] = f.get(f"qw_{i}_title", r["title"]); r["kpi"] = f.get(f"qw_{i}_kpi", r["kpi"]); r["body"] = f.get(f"qw_{i}_body", r["body"])
    for i in range(len(nar["recommendation_structure"])):
        r = nar["recommendation_structure"][i]
        r["title"] = f.get(f"st_{i}_title", r["title"]); r["tag"] = f.get(f"st_{i}_tag", r["tag"]); r["body"] = f.get(f"st_{i}_body", r["body"])
    for i in range(len(nar.get("market_context", []))):
        c = nar["market_context"][i]
        c["head"] = f.get(f"mc_{i}_head", c["head"]); c["title"] = f.get(f"mc_{i}_title", c["title"]); c["body"] = f.get(f"mc_{i}_body", c["body"])
    for i in range(len(nar["next_steps"]["phases"])):
        nar["next_steps"]["phases"][i]["body"] = f.get(f"phase_{i}_body", nar["next_steps"]["phases"][i]["body"])
    return spec

@app.post("/p/{pid}/save")
async def save(pid: str, request: Request):
    spec = apply_form(load_spec(pid), await request.form())
    save_spec(pid, spec)
    return RedirectResponse(f"/p/{pid}", status_code=303)

@app.post("/p/{pid}/draft")
async def draft(pid: str, request: Request):
    spec = apply_form(load_spec(pid), await request.form())   # 편집중 내용 보존
    spec, _usage = DN.draft_narrative(spec)
    save_spec(pid, spec)
    return RedirectResponse(f"/p/{pid}", status_code=303)

@app.post("/p/{pid}/approve")
async def approve(pid: str, request: Request):
    spec = apply_form(load_spec(pid), await request.form())
    spec["review"]["status"] = "approved"
    save_spec(pid, spec)
    build_deck(spec, str(OUT / f"web_{pid}.pptx"))
    return RedirectResponse(f"/p/{pid}?done=1", status_code=303)

@app.get("/p/{pid}/download")
def download(pid: str):
    fp = OUT / f"web_{pid}.pptx"
    if not fp.exists():
        return PlainTextResponse("아직 생성되지 않았습니다.", status_code=404)
    return FileResponse(fp, filename=f"report_{pid}.pptx",
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
