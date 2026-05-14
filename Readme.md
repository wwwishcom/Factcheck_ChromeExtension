# FF | Factcheck-Finger

뉴스 신뢰도 자동 검증 브라우저 확장 프로그램

<br>

## 서비스 소개

**Factcheck-Finger(FF)** 는 뉴스 기사를 읽는 순간 별도의 검색 없이 브라우저 위에서 신뢰도를 즉시 검증하는 크롬 확장 프로그램입니다. 허위 정보와 낚시성 기사가 범람하는 미디어 환경에서, 독자가 뉴스를 비판적으로 소비할 수 있도록 5가지 핵심 기능을 제공합니다.

<br>

## 핵심 기능

| 번호 | 기능 | 설명 |
|------|------|------|
| 01 | 육하원칙 기반 자동 검증 | 누가·무엇을·언제·어디서·왜·어떻게 6항목을 자동 추출해 충족 여부 검증 |
| 02 | 신뢰도 점수 즉시 표시 | 3개 지표의 가중 합산으로 0~100점 산출, 배터리 바로 직관적 표시 |
| 03 | 클릭베이트 감지 | 제목-본문 키워드 일치율과 자극적 표현 패턴 분석으로 낚시성 기사 탐지 |
| 04 | 유사 기사 비교 · 출처 추적 | RSS 크롤링 DB + 네이버 뉴스 API 기반 실시간 유사 기사 탐색 |
| 05 | 용어 즉시 풀이 · 경제 지표 연동 | AI 기반 전문 용어 자동 해설 및 기사 내 경제 지표 맥락 분석 |

<br>

## 기술 아키텍처

![Architecture](architecture.svg)

<br>

## 신뢰도 점수 산출 방식

```
신뢰도 점수 = 육하원칙 충족도 × 40%
            + 키워드 매칭률   × 35%
            + 클릭베이트 방어  × 25%
```

| 점수 범위 | 등급 | 의미 |
|----------|------|------|
| 80 ~ 100 | 신뢰 높음 | 신뢰할 수 있는 기사 |
| 60 ~ 79  | 보통 | 일부 항목 추가 확인 권장 |
| 40 ~ 59  | 주의 필요 | 사실 확인 권장 |
| 0 ~ 39   | 신뢰 낮음 | 출처와 사실관계 반드시 확인 |

<br>

## 기술 스택

### Chrome Extension

| 기술 | 용도 |
|------|------|
| Manifest V3 | 크롬 확장 최신 표준 |
| Content Script | 페이지 내 배지 삽입 및 본문 추출 |
| Service Worker | 백엔드 API 통신 중계 |
| Vanilla JS | 팝업 UI 및 아코디언 인터랙션 |

### Backend

| 기술 | 용도 |
|------|------|
| FastAPI (Python) | REST API 서버 |
| Supabase (PostgreSQL) | 기사 분석 이력 및 뉴스 캐시 DB |
| APScheduler | 매 1시간 RSS 자동 크롤링 |
| feedparser | 주요 언론사 RSS 피드 파싱 |
| OpenAI SDK | CNU API Gateway 호환 LLM 호출 |
| Claude Sonnet 4.6 | 뉴스 요약, 용어 풀이, 유사 기사 탐색 |
| Naver News API | 실시간 유사 기사 검색 폴백 |

<br>

## 프로젝트 구조

```
FF-Factcheck-Finger/
│
├── Chrome Extension
│   ├── manifest.json       MV3 설정, 권한 선언
│   ├── content.js          페이지 분석 + 배지 렌더링
│   ├── background.js       Service Worker, API 중계
│   ├── popup.html          팝업 UI
│   ├── popup.js            팝업 로직 + LLM 결과 렌더링
│   ├── styles.css          배지 디자인 시스템
│   ├── icon48.png
│   └── icon128.png
│
└── backend/
    ├── main.py             FastAPI 엔드포인트 + RSS 크롤러
    ├── requirements.txt
    ├── schema.sql          Supabase 테이블 정의
    ├── .env.example        환경변수 템플릿
    └── run.bat             Windows 서버 실행 스크립트
```

<br>

## 설치 및 실행

### Chrome 확장 설치

```
1. chrome://extensions 접속
2. 우측 상단 개발자 모드 ON
3. 압축해제된 확장 프로그램 로드 클릭
4. FF-Factcheck-Finger 폴더 선택
```

### 백엔드 서버 실행

```bash
# .env.example을 .env로 복사 후 키 입력
cp .env.example .env

# Windows
cd backend
run.bat

# Mac / Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 환경변수 설정 (.env)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
ANTHROPIC_API_KEY=your-api-key
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
```

### Supabase 테이블 생성

```
Supabase 대시보드 → SQL Editor → schema.sql 실행
```

<br>

## DB 스키마

### articles — 분석 기사 저장

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| title | TEXT | 기사 제목 |
| url | TEXT | 기사 URL |
| domain | TEXT | 언론사 도메인 |
| trust_score | INTEGER | 신뢰도 점수 (0~100) |
| grade | TEXT | 등급 |
| w5_score | INTEGER | 육하원칙 점수 |
| kw_score | INTEGER | 키워드 매칭 점수 |
| cb_score | INTEGER | 클릭베이트 방어 점수 |
| summary | TEXT | AI 요약 |
| terms | TEXT(JSON) | 전문 용어 풀이 |
| economic_indicators | TEXT(JSON) | 경제 지표 |
| fact_claims | TEXT(JSON) | 검증 필요 주장 |
| created_at | TIMESTAMPTZ | 분석 시각 |

### sources — 출처별 신뢰도 통계

| 컬럼 | 타입 | 설명 |
|------|------|------|
| domain | TEXT | 언론사 도메인 (UNIQUE) |
| article_count | INTEGER | 분석된 기사 수 |
| avg_trust_score | NUMERIC | 평균 신뢰도 점수 |

### news_cache — RSS 크롤링 캐시

| 컬럼 | 타입 | 설명 |
|------|------|------|
| url | TEXT | 기사 URL (UNIQUE) |
| title | TEXT | 기사 제목 |
| description | TEXT | 기사 요약 |
| source | TEXT | 언론사명 |
| pub_date | TEXT | 발행일 |
| created_at | TIMESTAMPTZ | 수집 시각 |

<br>

## 수집 언론사

연합뉴스, 네이버 뉴스 (정치/경제/사회/IT), 조선일보, 한겨레, MBC, KBS

<br>

## 보안 고려사항

- API 키는 `.env` 파일로만 관리, 코드에 하드코딩 금지
- `.env` 파일은 `.gitignore`에 반드시 추가
- Chrome Extension의 `host_permissions`으로 허용 도메인 제한
- Supabase RLS 설정으로 DB 접근 제어

<br>

© 2026 박정현의 다섯손가락 (충남대학교). All rights reserved.
