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
def extract_keywords_simple(text: str) -> str:
    """제목에서 핵심 키워드 추출 (2글자 이상 명사)"""
    tokens = re.findall(r'[가-힣A-Za-z]{2,}', text)
    stops = {'하는','하고','했다','한다','있는','있다','없다','됩니다','합니다','것으로','관련','대한','이후'}
    return ' '.join([t for t in tokens if t not in stops][:8])

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

                kw = extract_keywords_simple(title)

                # 유사 기사 이미 있는지 확인 (제목 첫 키워드로 검색)
                first_kw = kw.split()[0] if kw.split() else title[:10]
                try:
                    existing = supabase.table("news_cache")\
                        .select("id, confirmed_count")\
                        .ilike("title", f"%{first_kw}%")\
                        .neq("url", url)\
                        .limit(1).execute()

                    if existing.data:
                        # 유사 기사 발견 → confirmed_count 증가
                        row = existing.data[0]
                        supabase.table("news_cache").update({
                            "confirmed_count": (row.get("confirmed_count") or 1) + 1
                        }).eq("id", row["id"]).execute()
                except Exception:
                    pass

                # 새 기사 insert
                try:
                    supabase.table("news_cache").insert({
                        "url":             url,
                        "title":           title[:300],
                        "description":     summary[:500],
                        "source":          feed_info["source"],
                        "pub_date":        pub,
                        "query":           "",
                        "keywords":        kw,
                        "confirmed_count": 1,
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

class Verify5WRequest(BaseModel):
    title: str
    body: str
    pub_date: str = ""   # 기사 발행일 (페이지에서 추출)
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
  "score_reason": "이 기사의 신뢰도를 한두 문장으로 평가 (제목-본문 일치도, 근거 명확성, 출처 신뢰성 관점에서)",
  "terms": [{{"term": "전문용어", "explanation": "한 줄 설명"}}],
  "economic_indicators": [{{"name": "지표명", "value": "수치/상태", "context": "맥락"}}],
  "fact_claims": ["검증 필요한 핵심 주장1", "주장2", "주장3"],
  "similar_keywords": ["팩트체크 검색어1", "검색어2", "검색어3"]
}}

규칙:
- score_reason: 반드시 작성, 2문장 이내
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


# ── 8. 육하원칙 DB 대조 검증 ─────────────────────────────
@app.post("/api/verify5w")
async def verify_5w(req: Verify5WRequest):
    """
    1. DB에서 같은 날짜 + 키워드 유사 기사 검색
    2. 있으면 → DB 대조 방식으로 육하원칙 검증
    3. 없으면 → 정규식 패턴 매칭 + 최신 기사 안내
    """
    keyword = req.keywords[0] if req.keywords else req.title[:20]
    pub_date_display = ""

    # 발행일 파싱 (다양한 포맷 대응)
    if req.pub_date:
        for fmt in ["%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d",
                    "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dt = datetime.strptime(req.pub_date[:25], fmt)
                pub_date_display = dt.strftime("%Y.%m.%d")
                break
            except:
                continue
        if not pub_date_display:
            pub_date_display = req.pub_date[:10]

    # DB에서 유사 기사 검색
    db_articles = []
    try:
        res = supabase.table("news_cache")\
            .select("title, description, source, pub_date")\
            .ilike("title", f"%{keyword}%")\
            .order("created_at", desc=True)\
            .limit(5)\
            .execute()
        db_articles = res.data or []
    except Exception as e:
        print(f"[verify5w DB 오류] {e}")

    # ── DB 대조 방식 ──
    if db_articles:
        # DB 기사들의 내용을 합쳐서 육하원칙 요소 추출
        db_text = " ".join([a.get("title","") + " " + a.get("description","") for a in db_articles])
        prompt = f"""다음 두 텍스트를 비교해 육하원칙 6항목의 일치 여부를 분석하세요.
JSON만 반환하세요.

분석 대상 기사:
제목: {req.title}
본문: {req.body[:800]}

DB 유사 기사:
{db_text[:800]}

반환 형식:
{{
  "who":   {{"match": true/false, "article": "추출값", "db": "DB값", "note": "일치/불일치 이유"}},
  "what":  {{"match": true/false, "article": "추출값", "db": "DB값", "note": ""}},
  "when":  {{"match": true/false, "article": "추출값", "db": "DB값", "note": ""}},
  "where": {{"match": true/false, "article": "추출값", "db": "DB값", "note": ""}},
  "why":   {{"match": true/false, "article": "추출값", "db": "DB값", "note": ""}},
  "how":   {{"match": true/false, "article": "추출값", "db": "DB값", "note": ""}}
}}

규칙: 항목을 찾을 수 없으면 match=false, 값은 빈 문자열."""

        try:
            text = call_llm(prompt)
            comparison = parse_json_safe(text)
        except Exception as e:
            print(f"[verify5w LLM 오류] {e}")
            comparison = {}

        matched = sum(1 for v in comparison.values() if isinstance(v, dict) and v.get("match"))

        return {
            "ok": True,
            "method": "db",
            "pub_date": pub_date_display,
            "db_count": len(db_articles),
            "db_sources": list({a.get("source","") for a in db_articles}),
            "matched": matched,
            "total": 6,
            "comparison": comparison
        }

    # ── 정규식 패턴 매칭 방식 (DB 없을 때) ──
    else:
        return {
            "ok": True,
            "method": "pattern",
            "pub_date": pub_date_display,
            "db_count": 0,
            "db_sources": [],
            "matched": None,
            "total": 6,
            "comparison": {},
            "reason": f"{'최신 기사 (' + pub_date_display + ') — ' if pub_date_display else ''}DB에 등록되지 않은 기사입니다. 정규식 패턴 매칭으로 분석합니다."
        }


# ── 9. DB 신뢰도 매칭 점수 ───────────────────────────────
class DbMatchRequest(BaseModel):
    title: str
    keywords: List[str] = []
    pub_date: str = ""

@app.post("/api/db_match")
async def db_match(req: DbMatchRequest):
    """
    신뢰도 있는 언론사 DB와 대조해 신뢰도 점수 산출
    - 매칭 있음: DB 일치율 기반 점수 (최대 100)
    - 매칭 없음: 최신 기사 판정, 최대 70점 상한 적용
    """
    keyword = req.keywords[0] if req.keywords else req.title[:20]

    # DB에서 유사 기사 검색
    db_articles = []
    try:
        res = supabase.table("news_cache")\
            .select("title, source, confirmed_count, pub_date")\
            .ilike("title", f"%{keyword}%")\
            .order("confirmed_count", desc=True)\
            .limit(5).execute()
        db_articles = res.data or []
    except Exception as e:
        print(f"[db_match 오류] {e}")

    if db_articles:
        # 확인된 언론사 수
        sources = list({a.get("source","") for a in db_articles if a.get("source")})
        source_count = len(sources)
        # 가장 높은 confirmed_count
        max_confirmed = max(a.get("confirmed_count") or 1 for a in db_articles)

        # 점수 계산: 기본 50 + 언론사 수 보너스 + 중복 확인 보너스
        db_score = min(100, 50 + (source_count * 15) + min(max_confirmed * 5, 20))

        return {
            "ok": True,
            "case": "matched",          # DB 매칭 케이스
            "db_score": db_score,
            "source_count": source_count,
            "sources": sources,
            "max_confirmed": max_confirmed,
            "comment": None             # 주의 코멘트 없음
        }
    else:
        # DB 미매칭 → 최대 70점 상한, 주의 코멘트
        pub_display = req.pub_date[:10] if req.pub_date else ""
        return {
            "ok": True,
            "case": "unmatched",        # DB 미매칭 케이스
            "db_score": None,
            "source_count": 0,
            "sources": [],
            "max_confirmed": 0,
            "comment": f"{'최신 기사 (' + pub_display + ') — ' if pub_display else ''}신뢰도 높은 언론사에서 아직 확인되지 않은 기사입니다. 내용을 추가로 확인하는 것을 권장합니다."
        }