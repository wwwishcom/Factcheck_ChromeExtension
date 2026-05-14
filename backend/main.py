"""
FF | Factcheck-Finger — FastAPI Backend v1.0
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import anthropic
from openai import OpenAI
from supabase import create_client, Client
import os, json, re, traceback
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# ── 앱 설정 ──────────────────────────────────────────────
app = FastAPI(title="FF | Factcheck-Finger API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 클라이언트 초기화 ─────────────────────────────────────
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SECRET_KEY")
)

# 충남대 API Gateway (OpenAI 호환 형식)
claude = OpenAI(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://factchat-cloud.mindlogic.ai/v1/gateway"
)

def call_llm(prompt: str, model: str = "claude-sonnet-4-6") -> str:
    """충남대 API Gateway 호출"""
    res = claude.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

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

# ── 유틸 ─────────────────────────────────────────────────
def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return ""

def parse_json_safe(text: str) -> dict:
    """Claude 응답에서 JSON 파싱 (코드블록 제거 포함)"""
    clean = re.sub(r'```json|```', '', text).strip()
    # JSON 객체만 추출
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if match:
        clean = match.group()
    return json.loads(clean)

def update_source_stats(domain: str, trust_score: int):
    """출처별 신뢰도 통계 업데이트"""
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
                "domain": domain,
                "name": domain,
                "article_count": 1,
                "avg_trust_score": float(trust_score),
            }).execute()
    except Exception as e:
        print(f"[source update error] {e}")


# ════════════════════════════════════════════════════════
#  엔드포인트
# ════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "service": "FF | Factcheck-Finger API v1.0"}


# ── 0. API 키 연결 테스트 ─────────────────────────────────
@app.get("/api/test")
async def test_connections():
    results = {}

    # Claude API (충남대 Gateway) 테스트
    try:
        text = call_llm("hi", model="claude-sonnet-4-6")
        results["claude"] = f"✅ 정상 → {text[:30]}"
    except Exception as e:
        results["claude"] = f"❌ {str(e)}"

    # Supabase 테스트
    try:
        supabase.table("articles").select("id").limit(1).execute()
        results["supabase"] = "✅ 정상"
    except Exception as e:
        results["supabase"] = f"❌ {str(e)}"

    # 환경변수 확인
    results["env"] = {
        "ANTHROPIC_API_KEY": ("✅ 있음 → " + os.getenv("ANTHROPIC_API_KEY", "")[:12] + "...") if os.getenv("ANTHROPIC_API_KEY") else "❌ 없음",
        "SUPABASE_URL":      "✅ 있음" if os.getenv("SUPABASE_URL") else "❌ 없음",
        "SUPABASE_SECRET_KEY": ("✅ 있음 → " + os.getenv("SUPABASE_SECRET_KEY", "")[:12] + "...") if os.getenv("SUPABASE_SECRET_KEY") else "❌ 없음",
    }

    return results


# ── 1. 기사 분석 (LLM 요약 + DB 저장) ────────────────────
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

    # DB 저장
    article_id = None
    try:
        saved = supabase.table("articles").insert({
            "url":                  req.url,
            "domain":               domain,
            "title":                req.title,
            "trust_score":          req.trust_score,
            "grade":                req.grade,
            "w5_score":             req.w5_score,
            "kw_score":             req.kw_score,
            "cb_score":             req.cb_score,
            "summary":              llm.get("summary", ""),
            "terms":                json.dumps(llm.get("terms", []), ensure_ascii=False),
            "economic_indicators":  json.dumps(llm.get("economic_indicators", []), ensure_ascii=False),
            "fact_claims":          json.dumps(llm.get("fact_claims", []), ensure_ascii=False),
            "similar_keywords":     json.dumps(llm.get("similar_keywords", []), ensure_ascii=False),
        }).execute()
        article_id = saved.data[0]["id"] if saved.data else None
        update_source_stats(domain, req.trust_score)
    except Exception as e:
        print(f"[DB error] {type(e).__name__}: {e}")
        traceback.print_exc()

    return {"ok": True, "article_id": article_id, "data": llm}


# ── 2. 유사 기사 검색 (Claude web_search) ────────────────
@app.post("/api/similar")
async def find_similar(req: SimilarRequest):
    keywords = " ".join(req.keywords[:3]) if req.keywords else req.title[:60]

    prompt = f"""다음 뉴스 기사와 관련된 유사 기사를 웹에서 검색하고, 팩트체크에 유용한 정보를 찾아주세요.

기사 제목: {req.title}
핵심 키워드: {keywords}

반드시 아래 JSON 형식으로만 반환하세요 (마크다운 없이):
{{
  "articles": [
    {{
      "title": "기사 제목",
      "source": "언론사",
      "url": "URL (없으면 빈 문자열)",
      "summary": "한 줄 요약",
      "relevance": "이 기사와의 관련성"
    }}
  ],
  "verdict": "유사 기사들을 종합한 판단 (1~2문장)"
}}

최대 4개까지만."""

    try:
        text = call_llm(prompt)
        data = parse_json_safe(text)
    except json.JSONDecodeError:
        data = {"articles": [], "verdict": "유사 기사 파싱에 실패했습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "data": data}


# ── 3. 출처 신뢰도 조회 ───────────────────────────────────
@app.get("/api/source/{domain}")
async def get_source(domain: str):
    try:
        res = supabase.table("sources").select("*").eq("domain", domain).execute()
        return {"ok": True, "data": res.data[0] if res.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 4. 분석 이력 조회 ─────────────────────────────────────
@app.get("/api/history")
async def get_history(limit: int = Query(default=20, le=50)):
    try:
        res = supabase.table("articles")\
            .select("id, title, domain, trust_score, grade, created_at")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return {"ok": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 5. 출처 목록 (신뢰도 순) ──────────────────────────────
@app.get("/api/sources")
async def list_sources(limit: int = Query(default=20, le=100)):
    try:
        res = supabase.table("sources")\
            .select("*")\
            .order("avg_trust_score", desc=True)\
            .limit(limit)\
            .execute()
        return {"ok": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))