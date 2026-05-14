"""
FF | Factcheck-Finger — FastAPI Backend v2.1
RSS 크롤러 + 스케줄러 + DB 유사 기사 검색
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List
from openai import OpenAI
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os, json, re, traceback, httpx, feedparser
from dotenv import load_dotenv
from urllib.parse import urlparse
from datetime import datetime

load_dotenv()

# ── RSS 피드 목록 ─────────────────────────────────────────
RSS_FEEDS = [
    {"source": "연합뉴스",  "url": "https://www.yna.co.kr/rss/news.xml"},
    {"source": "네이버-정치","url": "https://news.naver.com/rss/politics.xml"},
    {"source": "네이버-경제","url": "https://news.naver.com/rss/economy.xml"},
    {"source": "네이버-사회","url": "https://news.naver.com/rss/society.xml"},
    {"source": "네이버-IT",  "url": "https://news.naver.com/rss/it.xml"},
    {"source": "조선일보",  "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"},
    {"source": "한겨레",    "url": "https://www.hani.co.kr/rss/"},
    {"source": "MBC",       "url": "https://imnews.imbc.com/rss/news/news_00.xml"},
    {"source": "KBS",       "url": "https://news.kbs.co.kr/rss/news.xml"},
]

# ── 클라이언트 초기화 ─────────────────────────────────────
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SECRET_KEY")
)

claude = OpenAI(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://factchat-cloud.mindlogic.ai/v1/gateway"
)

def call_llm(prompt: str, model: str = "claude-sonnet-4-6") -> str:
    res = claude.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

# ── 유틸 ─────────────────────────────────────────────────
def strip_tags(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text or '').strip()

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return ""

def parse_json_safe(text: str) -> dict:
    clean = re.sub(r'```json|```', '', text).strip()
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if match:
        clean = match.group()
    return json.loads(clean)

def update_source_stats(domain: str, trust_score: int):
    if not domain:
        return
    try:
        res = supabase.table("sources").select("*").eq("domain", domain).execute()
        if res.data:
            row = res.data[0]
            new_count = row["article_count"] + 1
            new_avg = ((row["avg_trust_score"] * row["article_count"]) + trust_score) / new_count
            supabase.table("sources").update({
                "article_count": new_count,
                "avg_trust_score": round(new_avg, 1),
            }).eq("domain", domain).execute()
        else:
            supabase.table("sources").insert({
                "domain": domain, "name": domain,
                "article_count": 1, "avg_trust_score": float(trust_score),
            }).execute()
    except Exception as e:
        print(f"[source update error] {e}")

# ── RSS 크롤러 ────────────────────────────────────────────
async def crawl_rss():
    print(f"[크롤러] RSS 수집 시작 {datetime.now().strftime('%H:%M:%S')}")
    total = 0
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:20]:
                title   = strip_tags(entry.get("title", ""))
                url     = entry.get("link", "")
                summary = strip_tags(entry.get("summary", "") or entry.get("description", ""))
                pub     = entry.get("published", "") or entry.get("updated", "")
                if not title or not url:
                    continue
                # insert 시도, 중복이면 무시
                try:
                    supabase.table("news_cache").insert({
                        "url":         url,
                        "title":       title[:300],
                        "description": summary[:500],
                        "source":      feed_info["source"],
                        "pub_date":    pub,
                        "query":       "",
                    }).execute()
                    total += 1
                except Exception:
                    pass  # 중복 URL 무시
        except Exception as e:
            print(f"[크롤러 오류] {feed_info['source']}: {e}")
    print(f"[크롤러] 완료 — {total}건 저장")

# ── 스케줄러 ──────────────────────────────────────────────
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await crawl_rss()
    scheduler.add_job(crawl_rss, "interval", hours=1, id="rss_crawl")
    scheduler.start()
    print("[스케줄러] 시작 — 매 1시간마다 RSS 수집")
    yield
    scheduler.shutdown()

# ── 앱 설정 ──────────────────────────────────────────────
app = FastAPI(title="FF | Factcheck-Finger API", version="2.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 요청 모델 ─────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    title: str
    body: str
    url: str = ""
    trust_score: int = 0
    w5_score: int = 0
    kw_score: int = 0
    cb_score: int = 0
    grade: str = ""

class SimilarRequest(BaseModel):
    title: str
    keywords: List[str] = []

# ════════════════════════════════════════════════════════
#  엔드포인트
# ════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "service": "FF | Factcheck-Finger API v2.1"}


# ── 0. 연결 테스트 ────────────────────────────────────────
@app.get("/api/test")
async def test_connections():
    results = {}
    try:
        call_llm("hi")
        results["claude"] = "✅ 정상"
    except Exception as e:
        results["claude"] = f"❌ {str(e)}"
    try:
        rows = supabase.table("news_cache").select("id").limit(1).execute()
        results["supabase"] = "✅ 정상"
    except Exception as e:
        results["supabase"] = f"❌ {str(e)}"
    results["env"] = {
        "ANTHROPIC_API_KEY":   ("✅ " + os.getenv("ANTHROPIC_API_KEY","")[:12]+"...") if os.getenv("ANTHROPIC_API_KEY") else "❌ 없음",
        "SUPABASE_URL":        "✅ 있음" if os.getenv("SUPABASE_URL") else "❌ 없음",
        "SUPABASE_SECRET_KEY": ("✅ " + os.getenv("SUPABASE_SECRET_KEY","")[:12]+"...") if os.getenv("SUPABASE_SECRET_KEY") else "❌ 없음",
        "NAVER_CLIENT_ID":     "✅ 있음" if os.getenv("NAVER_CLIENT_ID") else "❌ 없음",
    }
    return results


# ── 1. 기사 분석 ─────────────────────────────────────────
@app.post("/api/analyze")
async def analyze_article(req: AnalyzeRequest):
    body_trunc = req.body[:2000]
    domain = extract_domain(req.url)

    prompt = f"""다음 뉴스 기사를 분석하고 JSON만 반환하세요. 마크다운, 코드블록, 설명 없이 순수 JSON 객체만.

제목: {req.title}
본문: {body_trunc}

반환 형식:
{{
  "summary": "2~3문장 핵심 요약 (한국어)",
  "terms": [{{"term": "전문용어", "explanation": "한 줄 설명"}}],
  "economic_indicators": [{{"name": "지표명", "value": "수치/상태", "context": "맥락"}}],
  "fact_claims": ["검증 필요한 핵심 주장1", "주장2", "주장3"],
  "similar_keywords": ["팩트체크 검색어1", "검색어2", "검색어3"]
}}

규칙:
- terms: 독자가 모를 전문용어 최대 4개, 없으면 []
- economic_indicators: 경제 지표 없으면 []
- fact_claims: 최대 3개
- similar_keywords: 반드시 3개"""

    try:
        text = call_llm(prompt)
        llm = parse_json_safe(text)
    except Exception as e:
        print(f"[LLM error] {type(e).__name__}: {e}")
        traceback.print_exc()
        llm = {
            "summary": f"LLM 오류: {type(e).__name__} — {str(e)[:100]}",
            "terms": [], "economic_indicators": [],
            "fact_claims": [], "similar_keywords": []
        }

    article_id = None
    try:
        saved = supabase.table("articles").insert({
            "url": req.url, "domain": domain, "title": req.title,
            "trust_score": req.trust_score, "grade": req.grade,
            "w5_score": req.w5_score, "kw_score": req.kw_score, "cb_score": req.cb_score,
            "summary": llm.get("summary", ""),
            "terms": json.dumps(llm.get("terms", []), ensure_ascii=False),
            "economic_indicators": json.dumps(llm.get("economic_indicators", []), ensure_ascii=False),
            "fact_claims": json.dumps(llm.get("fact_claims", []), ensure_ascii=False),
            "similar_keywords": json.dumps(llm.get("similar_keywords", []), ensure_ascii=False),
        }).execute()
        article_id = saved.data[0]["id"] if saved.data else None
        update_source_stats(domain, req.trust_score)
    except Exception as e:
        print(f"[DB error] {type(e).__name__}: {e}")
        traceback.print_exc()

    return {"ok": True, "article_id": article_id, "data": llm}


# ── 2. 유사 기사 검색 (DB 기반 + 네이버 폴백) ────────────
@app.post("/api/similar/naver")
async def find_similar(req: SimilarRequest):
    keywords = req.keywords[:5] if req.keywords else []
    query    = " ".join(keywords[:3]) if keywords else req.title[:40]

    # ① DB에서 먼저 검색
    db_articles = []
    try:
        search_term = keywords[0] if keywords else req.title[:20]
        res = supabase.table("news_cache")\
            .select("title, url, description, source, pub_date")\
            .ilike("title", f"%{search_term}%")\
            .order("created_at", desc=True)\
            .limit(4)\
            .execute()
        db_articles = res.data or []
        print(f"[DB 검색] '{search_term}' → {len(db_articles)}건")
    except Exception as e:
        print(f"[DB 검색 오류] {e}")

    # ② DB 결과 없으면 네이버 폴백
    if not db_articles:
        print(f"[네이버 폴백] '{query}' 검색")
        try:
            async with httpx.AsyncClient() as http:
                res = await http.get(
                    "https://openapi.naver.com/v1/search/news.json",
                    params={"query": query, "display": 4, "sort": "sim"},
                    headers={
                        "X-Naver-Client-Id":     os.getenv("NAVER_CLIENT_ID"),
                        "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET"),
                    }
                )
            items = res.json().get("items", [])
            db_articles = [{
                "title":       strip_tags(i.get("title", "")),
                "url":         i.get("link", ""),
                "description": strip_tags(i.get("description", "")),
                "source":      urlparse(i.get("originallink","")).netloc.replace("www.",""),
                "pub_date":    i.get("pubDate", ""),
            } for i in items]
        except Exception as e:
            print(f"[네이버 오류] {e}")

    articles = [{
        "title":    a.get("title", ""),
        "url":      a.get("url", ""),
        "summary":  a.get("description", ""),
        "source":   a.get("source", ""),
        "pub_date": a.get("pub_date", "")[:16] if a.get("pub_date") else "",
    } for a in db_articles]

    verdict = f"'{query}' 관련 유사 기사 {len(articles)}건 발견" if articles \
              else "유사 기사를 찾지 못했습니다."

    return {"ok": True, "data": {"articles": articles, "verdict": verdict}}


# ── 3. 수동 크롤링 트리거 ─────────────────────────────────
@app.post("/api/crawl")
async def trigger_crawl():
    await crawl_rss()
    try:
        rows = supabase.table("news_cache").select("id").execute()
        return {"ok": True, "message": f"크롤링 완료 — 총 {len(rows.data)}건"}
    except:
        return {"ok": True, "message": "크롤링 완료"}


# ── 4. 출처 신뢰도 조회 ───────────────────────────────────
@app.get("/api/source/{domain}")
async def get_source(domain: str):
    try:
        res = supabase.table("sources").select("*").eq("domain", domain).execute()
        return {"ok": True, "data": res.data[0] if res.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 5. 분석 이력 조회 ─────────────────────────────────────
@app.get("/api/history")
async def get_history(limit: int = Query(default=20, le=50)):
    try:
        res = supabase.table("articles")\
            .select("id, title, domain, trust_score, grade, created_at")\
            .order("created_at", desc=True).limit(limit).execute()
        return {"ok": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 6. 출처 목록 (신뢰도 순) ──────────────────────────────
@app.get("/api/sources")
async def list_sources(limit: int = Query(default=20, le=100)):
    try:
        res = supabase.table("sources")\
            .select("*").order("avg_trust_score", desc=True).limit(limit).execute()
        return {"ok": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 7. 뉴스 캐시 현황 ────────────────────────────────────
@app.get("/api/news/stats")
async def news_stats():
    try:
        rows = supabase.table("news_cache").select("source").execute()
        source_counts = {}
        for row in (rows.data or []):
            s = row["source"]
            source_counts[s] = source_counts.get(s, 0) + 1
        return {"ok": True, "total": len(rows.data), "by_source": source_counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))