"""
FF | Factcheck-Finger — Matcher
DB 유사 기사 탐색 + 신뢰도 점수 산출
"""
import json
import numpy as np
from supabase import Client
from .extractor import extract_5w1h, extract_keywords_for_embedding
from .embedder import embed_5w1h, compare_5w1h, cosine_similarity, SIMILARITY_THRESHOLD, W5H_WEIGHTS

# ── 육하원칙 기반 신뢰도 점수 산출 ───────────────────────
def calc_trust_from_match(comparison: dict) -> dict:
    """
    DB 대조 결과로 신뢰도 점수 계산
    - 같은 사건이면: 불일치 항목 기반으로 신뢰도 측정
    - 다른 사건이면: 배제
    """
    details = comparison['details']

    # 불일치 항목 분석
    mismatch_penalty = 0.0
    mismatch_items = []
    match_items = []

    for key, sim in details.items():
        if sim is None:
            continue  # 항목 없음 → 감점 없음
        weight = W5H_WEIGHTS.get(key, 0.05)
        if sim < SIMILARITY_THRESHOLD:
            mismatch_penalty += weight
            mismatch_items.append(key)
        else:
            match_items.append(key)

    # 기본 점수: 100에서 불일치 비율만큼 차감
    base_score = max(0, 100 - (mismatch_penalty * 200))

    return {
        'score':          round(base_score),
        'mismatch_items': mismatch_items,
        'match_items':    match_items,
        'penalty':        round(mismatch_penalty, 3),
    }


# ── DB에서 유사 기사 탐색 ──────────────────────────────────
def find_similar_and_score(
    supabase: Client,
    title: str,
    body: str,
    top_k: int = 5
) -> dict:
    """
    1. 기사에서 육하원칙 추출 + 임베딩 생성
    2. DB에서 키워드 기반 후보 가져오기
    3. 임베딩 유사도로 같은 사건 필터링
    4. 불일치 항목으로 신뢰도 측정
    """
    # ── Step 1: 현재 기사 처리 ────────────────────────────
    w5h     = extract_5w1h(body[:1500])
    kw      = extract_keywords_for_embedding(w5h)
    emb     = embed_5w1h(kw)

    # 검색용 키워드 (WHO 행위자 + WHAT)
    search_kw = (w5h['who']['agent'] + w5h['what'])[:3]
    search_kw = [k for k in search_kw if len(k) >= 2]

    if not search_kw:
        # 키워드 없으면 제목 첫 단어 사용
        import re
        words = re.findall(r'[가-힣A-Za-z]{2,}', title)
        search_kw = words[:2]

    # ── Step 2: DB 후보 조회 ─────────────────────────────
    candidates = []
    for kw_word in search_kw[:2]:
        try:
            res = supabase.table("news_cache")\
                .select("id, title, w5h_data, embeddings, source, confirmed_count")\
                .ilike("title", f"%{kw_word}%")\
                .order("confirmed_count", desc=True)\
                .limit(20).execute()
            candidates += (res.data or [])
        except Exception as e:
            print(f"[Matcher] DB 조회 오류: {e}")

    # 중복 제거
    seen = set()
    unique = []
    for c in candidates:
        if c['id'] not in seen:
            seen.add(c['id'])
            unique.append(c)

    if not unique:
        return {
            'case':       'unmatched',
            'candidates': 0,
            'matches':    [],
            'best_score': None,
            'comment':    'DB에 등록되지 않은 기사입니다. 추가 확인을 권장합니다.',
        }

    # ── Step 3: 임베딩 유사도 비교 ───────────────────────
    same_event_matches = []

    for cand in unique:
        try:
            cand_emb = json.loads(cand['embeddings']) if isinstance(cand['embeddings'], str) else cand['embeddings']
            if not cand_emb:
                continue

            # 모든 임베딩이 null이면 제목 텍스트 임베딩으로 폴백
            all_null = all(v is None for v in cand_emb.values())
            if all_null:
                from .embedder import embed
                cand_title_vec = embed(cand.get('title', ''))
                query_title_vec = embed(title)
                sim = cosine_similarity(cand_title_vec, query_title_vec)
                if sim >= 0.50:  # 제목 유사도 기준
                    same_event_matches.append({
                        'title':           cand['title'],
                        'source':          cand['source'],
                        'confirmed_count': cand.get('confirmed_count', 1),
                        'comparison':      {'details': {'title_sim': sim}, 'weighted_score': sim * 100, 'is_same_event': True},
                        'trust':           {'score': round(sim * 100), 'mismatch_items': [], 'match_items': ['title']},
                    })
                continue

            comparison = compare_5w1h(emb, cand_emb)
            if comparison['is_same_event']:
                trust = calc_trust_from_match(comparison)
                same_event_matches.append({
                    'title':          cand['title'],
                    'source':         cand['source'],
                    'confirmed_count': cand.get('confirmed_count', 1),
                    'comparison':     comparison,
                    'trust':          trust,
                })
        except Exception as e:
            print(f"[Matcher] 비교 오류: {e}")
            continue

    if not same_event_matches:
        return {
            'case':       'unmatched',
            'candidates': len(unique),
            'matches':    [],
            'best_score': None,
            'comment':    '동일 사건으로 판단되는 기사를 찾지 못했습니다.',
        }

    # ── Step 4: 결과 정렬 + 신뢰도 최종 산출 ────────────
    same_event_matches.sort(key=lambda x: x['comparison']['weighted_score'], reverse=True)
    top_matches = same_event_matches[:top_k]

    # 여러 언론사 확인 보너스
    sources    = list({m['source'] for m in top_matches if m['source']})
    max_conf   = max(m['confirmed_count'] for m in top_matches)
    best_trust = top_matches[0]['trust']['score']

    # confirmed_count 보너스 (여러 언론사 동일 내용)
    bonus = min(15, (len(sources) - 1) * 5 + min(max_conf - 1, 2) * 3)
    final_score = min(100, best_trust + bonus)

    return {
        'case':        'matched',
        'candidates':  len(unique),
        'matches':     top_matches,
        'best_score':  final_score,
        'sources':     sources,
        'max_confirmed': max_conf,
        'comment':     None,
        'w5h':         w5h,
    }