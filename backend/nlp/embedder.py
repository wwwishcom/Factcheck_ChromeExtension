"""
FF | Factcheck-Finger — Embedder
한국어 문장/단어 임베딩 생성
모델: jhgan/ko-sroberta-multitask (한국어 특화 Sentence-BERT)
"""
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Optional

# ── 모델 lazy load ────────────────────────────────────────
_model = None
MODEL_NAME = "jhgan/ko-sroberta-multitask"

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[Embedder] 모델 로딩 중: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
        print("[Embedder] 모델 로딩 완료")
    return _model

# ── 단일 텍스트 임베딩 ────────────────────────────────────
def embed(text: str) -> list[float]:
    """텍스트 → 임베딩 벡터 (768차원)"""
    if not text or not text.strip():
        return [0.0] * 768
    model = get_model()
    vec = model.encode(text, convert_to_numpy=True)
    return vec.tolist()

# ── 육하원칙 항목별 임베딩 ───────────────────────────────
def embed_5w1h(keywords: dict) -> dict:
    """
    육하원칙 각 항목에 대한 임베딩 생성
    Args:
        keywords: extract_keywords_for_embedding() 결과
    Returns:
        항목별 임베딩 딕셔너리
    """
    model = get_model()
    result = {}
    for key, text in keywords.items():
        if text and text.strip():
            result[key] = model.encode(text, convert_to_numpy=True).tolist()
        else:
            result[key] = None
    return result

# ── 코사인 유사도 ─────────────────────────────────────────
def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """두 벡터의 코사인 유사도 계산"""
    if not v1 or not v2:
        return 0.0
    a = np.array(v1)
    b = np.array(v2)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

# ── 육하원칙 항목별 유사도 계산 ──────────────────────────
# 항목별 가중치 (WHY/HOW는 없어도 감점 적게)
W5H_WEIGHTS = {
    'who_agent':   0.25,
    'who_patient': 0.15,
    'what':        0.25,
    'when':        0.15,
    'where':       0.12,
    'why':         0.05,
    'how':         0.03,
}

SIMILARITY_THRESHOLD = 0.45  # 같은 항목으로 판단하는 유사도 기준 (완화)

def compare_5w1h(emb1: dict, emb2: dict) -> dict:
    """
    두 기사의 육하원칙 임베딩 비교
    Returns:
        {
            'match_count': 일치 항목 수,
            'weighted_score': 가중 유사도 점수,
            'details': 항목별 유사도,
            'is_same_event': 같은 사건 여부 (3개 이상 일치)
        }
    """
    details = {}
    match_count = 0
    weighted_score = 0.0
    total_weight = 0.0

    for key, weight in W5H_WEIGHTS.items():
        v1 = emb1.get(key)
        v2 = emb2.get(key)

        if v1 and v2:
            sim = cosine_similarity(v1, v2)
            details[key] = round(sim, 3)
            total_weight += weight
            weighted_score += sim * weight
            if sim >= SIMILARITY_THRESHOLD:
                match_count += 1
        else:
            details[key] = None  # 항목 없음

    # 정규화
    if total_weight > 0:
        weighted_score = weighted_score / total_weight

    # 같은 사건 판단: WHO 또는 WHAT 하나만 일치해도 되고, 전체 2개 이상 일치해도 됨
    who_match  = (details.get('who_agent', 0) or 0) >= SIMILARITY_THRESHOLD
    what_match = (details.get('what', 0) or 0) >= SIMILARITY_THRESHOLD
    when_match = (details.get('when', 0) or 0) >= SIMILARITY_THRESHOLD
    where_match = (details.get('where', 0) or 0) >= SIMILARITY_THRESHOLD
    is_same_event = who_match or what_match or when_match or where_match or (match_count >= 2)

    # 유효한 임베딩이 하나도 없으면 제목 키워드 기반으로 판단 불가
    if total_weight == 0:
        is_same_event = False

    return {
        'match_count':   match_count,
        'weighted_score': round(weighted_score * 100, 1),
        'details':       details,
        'is_same_event': is_same_event,
    }