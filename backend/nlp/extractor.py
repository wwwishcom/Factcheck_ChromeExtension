"""
FF | Factcheck-Finger — NLP Extractor
NER + 형태소 분석으로 육하원칙 추출
"""
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from konlpy.tag import Okt
import kss
import re
from typing import Optional

# ── 형태소 분석기 ─────────────────────────────────────────
_okt = None
def get_okt():
    global _okt
    if _okt is None:
        _okt = Okt()
    return _okt

# ── KLUE NER 모델 (lazy load) ────────────────────────────
_ner_pipeline = None
def get_ner():
    global _ner_pipeline
    if _ner_pipeline is None:
        print("[NLP] KLUE NER 모델 로딩 중...")
        tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
        model = AutoModelForTokenClassification.from_pretrained(
            "snunlp/KR-FinBert-SC"  # NER 파인튜닝 모델
        )
        _ner_pipeline = pipeline(
            "ner",
            model="leo-bsk/KoELECTRA-NER",  # 한국어 NER
            tokenizer="leo-bsk/KoELECTRA-NER",
            aggregation_strategy="simple"
        )
        print("[NLP] NER 모델 로딩 완료")
    return _ner_pipeline

# ── 조사/어미 제거 ────────────────────────────────────────
STOP_POS = {'Josa', 'Eomi', 'PreEomi', 'Suffix', 'Punctuation', 'Foreign'}

def clean_tokens(text: str) -> list[str]:
    """형태소 분석 후 조사/어미 제거, 원형으로 변환"""
    okt = get_okt()
    morphs = okt.pos(text, norm=True, stem=True)
    return [word for word, pos in morphs if pos not in STOP_POS and len(word) >= 2]

# ── 시간 표현 패턴 ────────────────────────────────────────
TIME_PATTERNS = [
    r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
    r'\d{1,2}월\s*\d{1,2}일',
    r'오늘|어제|그저께|내일|모레',
    r'지난\s*(주|달|해|월요일|화요일|수요일|목요일|금요일|토요일|일요일)',
    r'이번\s*(주|달|해)',
    r'올해|작년|내년|지난해',
    r'최근|당시|현재|이날|그날|전날|다음날',
    r'\d+일\s*(전|후|만)',
    r'오전|오후\s*\d+시',
]

# ── 장소 표현 패턴 ────────────────────────────────────────
PLACE_PATTERNS = [
    r'[가-힣]+(시|군|구|동|읍|면|로|길|역|공항|항구|병원|학교|대학|센터|빌딩|타워|호텔)',
    r'서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주',
    r'미국|중국|일본|러시아|영국|프랑스|독일|북한|우크라이나|대만|이스라엘|인도',
    r'국회|청와대|백악관|법원|검찰청|경찰청|유엔|UN',
]

# ── 인과관계 패턴 (WHY) ───────────────────────────────────
WHY_PATTERNS = [
    r'(.+?)(때문에|으로\s*인해|인해|탓에|덕분에)',
    r'(때문|원인|이유|배경).{0,20}(은|는|이|가).{0,50}',
    r'(.+?)(위해|위하여|목적으로)',
]

# ── 방법/수단 패턴 (HOW) ──────────────────────────────────
HOW_PATTERNS = [
    r'(.+?)(으로|로|을\s*통해|통해|이용해|활용해)',
    r'(방법|방식|수단|절차).{0,20}(으로|로)',
]

# ── SRL 기반 주어/목적어 역할 구분 ───────────────────────
def extract_subject_object(sentence: str) -> dict:
    """
    주어(행위자)와 목적어(피행위자)를 구분
    조사 패턴 기반: 이/가/께서 → 주어(행위자), 을/를/에게 → 목적어
    """
    okt = get_okt()
    morphs = okt.pos(sentence, norm=True, stem=True)

    subject = []    # 행위자 (주어)
    obj = []        # 피행위자 (목적어/부사어)
    current_noun = []

    for i, (word, pos) in enumerate(morphs):
        if pos in ('Noun', 'Alpha', 'Number'):
            current_noun.append(word)
        elif pos == 'Josa':
            if current_noun:
                noun = ''.join(current_noun)
                # 주격 조사 → 행위자
                if word in ('이', '가', '께서', '은', '는'):
                    subject.append(noun)
                # 목적격/여격 조사 → 피행위자
                elif word in ('을', '를', '에게', '한테', '께'):
                    obj.append(noun)
                current_noun = []
        else:
            current_noun = []

    return {
        'agent':   subject,   # 행위를 하는 주체
        'patient': obj        # 행위를 당하는 대상
    }

# ── 메인 추출 함수 ────────────────────────────────────────
def extract_5w1h(text: str) -> dict:
    """
    텍스트에서 육하원칙 추출
    Returns:
        {
            'who':   {'agent': [...], 'patient': [...]},
            'what':  [...],
            'when':  [...],
            'where': [...],
            'why':   [...],
            'how':   [...],
            'sentences': [...]
        }
    """
    # 문장 분리
    try:
        sentences = kss.split_sentences(text)
    except:
        sentences = [s.strip() for s in re.split(r'[.!?]\s+', text) if len(s.strip()) > 5]

    result = {
        'who':       {'agent': [], 'patient': []},
        'what':      [],
        'when':      [],
        'where':     [],
        'why':       [],
        'how':       [],
        'sentences': sentences[:10]  # 최대 10문장
    }

    full_text = ' '.join(sentences[:10])

    # ── WHO: 주어/목적어 역할 구분 ──────────────────────────
    for sent in sentences[:5]:
        roles = extract_subject_object(sent)
        result['who']['agent']   += roles['agent']
        result['who']['patient'] += roles['patient']

    # 중복 제거
    result['who']['agent']   = list(dict.fromkeys(result['who']['agent']))[:5]
    result['who']['patient'] = list(dict.fromkeys(result['who']['patient']))[:5]

    # ── WHEN: 시간 표현 ────────────────────────────────────
    for pattern in TIME_PATTERNS:
        matches = re.findall(pattern, full_text)
        result['when'] += [m if isinstance(m, str) else m[0] for m in matches]
    result['when'] = list(dict.fromkeys(result['when']))[:3]

    # ── WHERE: 장소 표현 ───────────────────────────────────
    for pattern in PLACE_PATTERNS:
        matches = re.findall(pattern, full_text)
        result['where'] += matches
    result['where'] = list(dict.fromkeys(result['where']))[:3]

    # ── WHY: 인과관계 ──────────────────────────────────────
    for pattern in WHY_PATTERNS:
        matches = re.findall(pattern, full_text)
        for m in matches:
            clause = m[0].strip() if isinstance(m, tuple) else m.strip()
            if len(clause) > 2:
                result['why'].append(clause[:50])
    result['why'] = list(dict.fromkeys(result['why']))[:2]

    # ── HOW: 방법/수단 ─────────────────────────────────────
    for pattern in HOW_PATTERNS:
        matches = re.findall(pattern, full_text)
        for m in matches:
            clause = m[0].strip() if isinstance(m, tuple) else m.strip()
            if len(clause) > 2:
                result['how'].append(clause[:50])
    result['how'] = list(dict.fromkeys(result['how']))[:2]

    # ── WHAT: 핵심 동사구 (형태소에서 동사 추출) ────────────
    okt = get_okt()
    morphs = okt.pos(full_text[:500], norm=True, stem=True)
    verbs = [w for w, p in morphs if p == 'Verb' and len(w) >= 2]
    result['what'] = list(dict.fromkeys(verbs))[:5]

    return result


def extract_keywords_for_embedding(w5h: dict) -> dict:
    """
    임베딩 생성을 위한 항목별 텍스트 반환
    조사/어미 제거된 핵심 단어만
    """
    return {
        'who_agent':   ' '.join(w5h['who']['agent']),
        'who_patient': ' '.join(w5h['who']['patient']),
        'what':        ' '.join(w5h['what']),
        'when':        ' '.join(w5h['when']),
        'where':       ' '.join(w5h['where']),
        'why':         ' '.join(w5h['why']),
        'how':         ' '.join(w5h['how']),
    }
