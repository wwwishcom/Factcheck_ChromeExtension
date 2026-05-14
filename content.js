(() => {
  // ============================================================
  //  A. 제목 / 본문 추출
  // ============================================================
  function getTitle() {
    const sels = ['h1.article-title','h1#title','h1.title','.article_head h1','.news_title h1','h1[class*="headline"]','h1[class*="title"]','h1[class*="heading"]','h1[data-testid]','[class*="articleHead"] h1','[class*="story-heading"]','[class*="caas-title"] h1','article h1','main h1','h1'];
    for (const s of sels) { const el = document.querySelector(s); if (el && el.textContent.trim().length > 5) return el.textContent.trim(); }
    const og = document.querySelector('meta[property="og:title"]');
    if (og && og.content) return og.content;
    return document.title;
  }

  function getBody() {
    const sels = ['#newsct_article','#articleBodyContents','#articeBody','#article-body','#articleBody','[class*="articleBody"]','[class*="article-body"]','[class*="article_body"]','[class*="story-body"]','[class*="content-body"]','[data-testid*="article"]','[data-testid*="story"]','[class*="caas-body"]','article [class*="body"]','article [class*="content"]','article','main article','[role="article"]','[class*="news_body"]','[class*="post-content"]','[class*="entry-content"]','.story-body','.content','main'];
    for (const s of sels) { const el = document.querySelector(s); if (el && el.textContent.trim().length > 200) return el.textContent.trim(); }
    const ps = [...document.querySelectorAll('p')].filter(p => p.textContent.trim().length > 30);
    return ps.map(p => p.textContent.trim()).join(' ');
  }

  function getBodyPreview(body) {
    const sents = body.replace(/\s+/g, ' ').split(/(?<=[.!?。])\s+/).map(s => s.trim()).filter(s => s.length > 20 && s.length < 220);
    const p = sents.slice(0, 2).join(' ');
    return p.length > 160 ? p.slice(0, 157) + '…' : p || body.slice(0, 150) + '…';
  }

  // ============================================================
  //  B. 키워드 추출
  // ============================================================
  const JOSA = ['에서는','으로는','에서도','으로서','으로도','에게서','에서','에게','까지','부터','마저','조차','만큼','처럼','같이','으로','에는','에도','와는','과는','이나','거나','은','는','이','가','을','를','의','에','와','과','도','로','서','만','요','든','라','며','고','면'];
  function removeJosa(w) { for (const j of JOSA) { if (w.length > j.length + 1 && w.endsWith(j)) return w.slice(0, -j.length); } return w; }
  function extractKeywords(text) {
    const tokens = text.replace(/[^\w\sㄱ-힣]/g, ' ').split(/\s+/).filter(t => t.length >= 2);
    const cleaned = tokens.map(removeJosa).filter(t => t.length >= 2);
    const freq = {};
    for (const w of cleaned) { const lw = w.toLowerCase(); freq[lw] = (freq[lw] || 0) + 1; }
    const stops = new Set(['하는','하고','했다','한다','있는','있다','없는','없다','되는','된다','했습니다','됩니다','있습니다','없습니다','것으로','대해','위해','통해','라고','라며','따르면','밝혔다','전했다','말했다','보도했다','알려졌다','것이다','때문','이번','지난','오늘','내일','어제','최근','현재','관련','대한','이후','그리고','하지만','그러나','또한','그래서','the','and','for','that','this','with','from','are','was','has','have','been','will','would','could','should','into','about','after','before','between']);
    return Object.entries(freq).filter(([w]) => !stops.has(w)).sort((a, b) => b[1] - a[1]).slice(0, 20).map(([word, count]) => ({ word, count }));
  }

  // ============================================================
  //  C. 육하원칙
  // ============================================================
  function extract5W1H(title, body) {
    const fullText = title + ' ' + body;
    const sentences = body.split(/[.!?。]\s*/).filter(s => s.length > 10);
    const first = sentences.slice(0, 5).join(' ');
    const result = { who:{found:false,evidence:[],label:'누가 (Who)'}, what:{found:false,evidence:[],label:'무엇을 (What)'}, when:{found:false,evidence:[],label:'언제 (When)'}, where:{found:false,evidence:[],label:'어디서 (Where)'}, why:{found:false,evidence:[],label:'왜 (Why)'}, how:{found:false,evidence:[],label:'어떻게 (How)'} };
    function m(text, patterns) { const all = []; for (const p of patterns) all.push(...[...text.matchAll(p)].map(x => x[0].trim())); return [...new Set(all)].slice(0, 3); }
    let ev;
    ev = m(first, [/([가-힣]{2,4})\s*(대통령|총리|장관|의원|교수|대표|사장|회장|위원장|감독|선수|씨|측)/g,/([A-Z][a-z]+\s+[A-Z][a-z]+)/g,/(경찰|검찰|법원|정부|청와대|국회|여당|야당|대법원|헌법재판소|국방부|외교부|교육부)/g,/(삼성|LG|SK|현대|네이버|카카오|구글|애플|테슬라|마이크로소프트|아마존|메타|엔비디아|Microsoft|Google|Apple|Amazon|Meta|Tesla|Trump|Biden)/gi]);
    if (ev.length) { result.who.found = true; result.who.evidence = ev; }
    ev = m(fullText, [/(발표|공개|출시|인수|합병|체결|서명|개최|선언|결정|승인|통과|폐지|시행|도입|철회|거부)/g,/(사고|사건|폭발|화재|지진|홍수|파업|시위|테러|전쟁|충돌|감염|확진|사망|부상)/g,/(상승|하락|급등|급락|폭등|폭락|돌파|기록|달성|경신)/g,/(논란|의혹|비판|반발|소송|고발|기소|구속|체포|수사)/g,/(announced|launched|released|signed|approved|rejected|arrested|killed|injured|surged|plunged)/gi]);
    if (ev.length) { result.what.found = true; result.what.evidence = ev; }
    ev = m(first, [/(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)/g,/(\d{1,2}월\s*\d{1,2}일)/g,/(오늘|어제|그저께|내일|모레|지난\s*\d+일|지난달|올해|작년|내년)/g,/(최근|당시|현재|이날|그날|전날)/g,/(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)/gi,/(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}/gi,/(today|yesterday|last\s+week|last\s+month|this\s+year)/gi]);
    if (ev.length) { result.when.found = true; result.when.evidence = ev; }
    ev = m(fullText, [/(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)/g,/(미국|중국|일본|러시아|영국|프랑스|독일|북한|우크라이나|대만|이스라엘|인도)/g,/(Washington|Beijing|Tokyo|Moscow|London|Paris|Berlin|New\s*York|Seoul)/gi,/(U\.?S\.?A?|China|Japan|Russia|UK|France|Germany|Ukraine|Israel|India)/gi,/(국회|청와대|백악관|유엔|UN|NATO|WHO|IMF|Pentagon|Congress|White\s*House)/gi,/([가-힣]+(시|군|구|동|읍|역|공항|병원|학교|대학|센터))\b/g]);
    if (ev.length) { result.where.found = true; result.where.evidence = ev; }
    ev = m(body, [/(때문에|이유는|원인은|배경에는|영향으로|결과로|여파로|인해|인하여)/g,/(위해|위하여|목적으로|취지로)/g,/(because|due\s+to|as\s+a\s+result|caused\s+by|in\s+order\s+to|reason|amid)/gi]);
    if (ev.length) { result.why.found = true; result.why.evidence = ev; }
    ev = m(body, [/(방법|방식|절차|과정|단계|계획|전략|대책|방안|조치)/g,/(통해|이용해|활용해|사용해|실시해|진행해|추진해)/g,/(by\s+using|through|via|method|process|strategy|measure|step)/gi]);
    if (ev.length) { result.how.found = true; result.how.evidence = ev; }
    return result;
  }

  // ============================================================
  //  D. 클릭베이트
  // ============================================================
  const CB = {
    words: {"충격":3,"경악":3,"소름":3,"전율":2,"발칵":2,"난리":2,"대박":2,"헐":2,"실화":2,"레전드":2,"정체":2,"최후":2,"눈물":1.5,"폭로":1.5,"반전":1.5,"알고보니":1.5,"shocking":3,"unbelievable":3,"insane":2},
    regex: [{pattern:/[!?]{2,}/,score:2,label:"느낌표/물음표 남발"},{pattern:/\.{3,}/,score:1.5,label:"말줄임표 낚시"},{pattern:/[ㄱ-ㅎㅋㅎ]{2,}/,score:2,label:"자음 반복"},{pattern:/(이것|이거|여기).*(정체|정말|진짜)/i,score:2.5,label:"떠보기 패턴"},{pattern:/(결국|마침내).*(밝혀|드러|알려)/i,score:2,label:"지연 공개"},{pattern:/you won't believe/i,score:2.5,label:"You won't believe"}]
  };
  function calcClickbait(title) {
    let score = 0, reasons = [];
    const t = title.toLowerCase();
    for (const [w, s] of Object.entries(CB.words)) { if (t.includes(w.toLowerCase())) { score += s; reasons.push(w); } }
    for (const { pattern, score: s, label } of CB.regex) { if (pattern.test(title)) { score += s; reasons.push(label); } }
    if (title.length > 60) score += 0.5;
    if (title.length > 80) score += 1;
    return { raw: score, normalized: Math.min(100, Math.round(score * 10)), reasons };
  }

  // ============================================================
  //  E. 키워드 매칭
  // ============================================================
  function calcKeywordMatch(title, body) {
    const kw = extractKeywords(title);
    const bt = body.toLowerCase();
    if (!kw.length) return { score: 50, matched: [], missed: [] };
    const matched = [], missed = [];
    for (const { word } of kw) { (bt.includes(word.toLowerCase()) ? matched : missed).push(word); }
    return { score: Math.round((matched.length / kw.length) * 100), matched, missed };
  }

  // ============================================================
  //  F. 종합 점수
  // ============================================================
  function calcTrust(cb, kw, w5) {
    const cbS = Math.max(0, 100 - cb.normalized);
    const kwS = kw.score;
    const cnt = Object.values(w5).filter(e => e.found).length;
    const w5S = Math.round((cnt / 6) * 100);
    const total = Math.round(cbS * 0.25 + kwS * 0.35 + w5S * 0.40);
    let grade, color, fillColor;
    if (total >= 80) { grade='신뢰 높음'; color='#16a34a'; fillColor='#4ade80'; }
    else if (total >= 60) { grade='보통'; color='#b45309'; fillColor='#fbbf24'; }
    else if (total >= 40) { grade='주의 필요'; color='#e67e22'; fillColor='#fb923c'; }
    else { grade='신뢰 낮음'; color='#dc2626'; fillColor='#f87171'; }
    return { total, grade, color, fillColor, cbS, kwS, w5S, cnt };
  }

  // ============================================================
  //  G. 뉴스 페이지 감지
  // ============================================================
  function isNewsPage() {
    const h = location.hostname;
    const hosts = ['news.naver.com','n.news.naver.com','v.daum.net','news.v.daum.net','www.chosun.com','www.donga.com','www.hani.co.kr','www.khan.co.kr','www.yna.co.kr','www.joongang.co.kr','www.mk.co.kr','www.hankyung.com','www.bbc.com','bbc.com','edition.cnn.com','www.cnn.com','www.reuters.com','www.nytimes.com','www.washingtonpost.com','www.theguardian.com','www.msn.com','msn.com','news.yahoo.com','finance.yahoo.com','news.google.com','www.bloomberg.com','www.cnbc.com','techcrunch.com','www.theverge.com','www.sedaily.com','biz.chosun.com','www.sbs.co.kr','www.kbs.co.kr','www.mbc.co.kr'];
    if (hosts.some(x => h.includes(x))) return true;
    const path = location.pathname.toLowerCase();
    if (['/news/','/article/','/story/','/post/','/press/'].some(k => path.includes(k))) return true;
    const og = document.querySelector('meta[property="og:type"]');
    if (og && og.content && og.content.includes('article')) return true;
    const art = document.querySelector('article');
    if (art && art.textContent.trim().length > 500) return true;
    return false;
  }

  // ============================================================
  //  H. 색상 유틸
  // ============================================================
  function sc(s, inv = false) {
    const v = inv ? 100 - s : s;
    if (v >= 75) return { c:'#16a34a', bar:'ff-bg-g', bdg:'ff-bdg-g', cls:'ff-c-g' };
    if (v >= 50) return { c:'#b45309', bar:'ff-bg-y', bdg:'ff-bdg-y', cls:'ff-c-y' };
    return          { c:'#dc2626', bar:'ff-bg-r', bdg:'ff-bdg-r', cls:'ff-c-r' };
  }

  // ============================================================
  //  I. LLM 섹션 업데이트 (배지용)
  // ============================================================
  function applyLLMToBadge(llm) {
    const sumEl = document.querySelector('#ff-trust-badge #ff-b-summary');
    if (sumEl && llm.summary) {
      sumEl.innerHTML = `<div style="font-size:11px;color:#4a607a;line-height:1.6">${llm.summary}</div>`;
    }
    const el04 = document.querySelector('#ff-trust-badge #ff-b-04');
    if (el04) {
      const claims = llm.fact_claims || [];
      const kws    = llm.similar_keywords || [];
      el04.innerHTML = `
        ${claims.map(c => `<div style="font-size:10px;color:#4a607a;padding:3px 0;border-bottom:1px solid #f5f5f3">▪ ${c}</div>`).join('')}
        ${kws.length ? `<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:3px">${kws.map(k=>`<span style="font-size:10px;padding:2px 7px;border-radius:20px;background:#eef2fb;color:#003087;border:1px solid rgba(0,48,135,.2)">${k}</span>`).join('')}</div>` : ''}
      ` || '<div style="font-size:10px;color:#8fa0b4">데이터 없음</div>';
    }
    const el05 = document.querySelector('#ff-trust-badge #ff-b-05');
    if (el05) {
      const terms = llm.terms || [];
      const inds  = llm.economic_indicators || [];
      el05.innerHTML = `
        ${terms.map(t => `<div style="padding:4px 0;border-bottom:1px solid #f5f5f3"><div style="font-size:10px;font-weight:700;color:#003087">${t.term}</div><div style="font-size:10px;color:#4a607a">${t.explanation}</div></div>`).join('')}
        ${inds.map(i => `<div style="background:#f8f9fc;border-radius:6px;padding:6px 8px;margin-top:5px"><div style="font-size:9px;color:#8fa0b4">${i.name}</div><div style="font-size:12px;font-weight:800;color:#003087">${i.value}</div><div style="font-size:10px;color:#4a607a">${i.context}</div></div>`).join('')}
      ` || '<div style="font-size:10px;color:#8fa0b4">발견된 용어 없음</div>';
    }
  }

  // ============================================================
  //  J. 배지 렌더링 v4.0 — 배터리 디자인
  // ============================================================
  function renderBadge(title, cb, kw, w5, trust, bodyPreview) {
    const existing = document.getElementById('ff-trust-badge');
    if (existing) existing.remove();

    const w5c  = sc(trust.w5S);
    const kwc  = sc(trust.kwS);
    const cbc  = sc(trust.cbS);
    const cbRc = sc(cb.normalized, true);

    const w5Html = Object.entries(w5).map(([, v]) => `
      <div class="ff-5w">
        <div class="ff-5w-dot ${v.found ? 'hit' : 'miss'}">${v.found ? '✓' : '✗'}</div>
        <span class="ff-5w-lbl">${v.label}</span>
        ${v.found ? `<span class="ff-5w-ev">${v.evidence.slice(0,2).join(', ')}</span>`
                  : `<span class="ff-5w-no">미발견</span>`}
      </div>`).join('');

    const matchTags = kw.matched.slice(0,7).map(w => `<span class="ff-tag ok">${w}</span>`).join('');
    const missTags  = kw.missed.slice(0,4).map(w => `<span class="ff-tag miss">${w}</span>`).join('');
    const cbTags = cb.reasons.length
      ? `<div class="ff-tags">${cb.reasons.map(r => `<span class="ff-tag warn">⚠ ${r}</span>`).join('')}</div>`
      : `<div class="ff-ok">✅ 자극적 패턴 없음</div>`;

    const llmSkel = `<div class="ff-skel"></div><div class="ff-skel" style="width:70%"></div>`;

    const badge = document.createElement('div');
    badge.id = 'ff-trust-badge';
    badge.className = 'ff-collapsed';

    badge.innerHTML = `
      <!-- PILL -->
      <div class="ff-pill" id="ff-pill">
        <span class="ff-pill-logo">FF</span>
        <span class="ff-pill-score" style="color:${trust.fillColor}">${trust.total}</span>
        <span class="ff-pill-sep"></span>
        <span class="ff-pill-grade">${trust.grade}</span>
        <span class="ff-pill-arrow" id="ff-pill-arrow">▲</span>
      </div>

      <!-- EXPANDED CARD -->
      <div class="ff-card" id="ff-card" style="display:none">

        <!-- BATTERY HEADER -->
        <div class="ff-batt-head" id="ff-card-close">
          <div class="ff-batt-top">
            <div>
              <div class="ff-batt-grade">${trust.grade}</div>
              <div class="ff-batt-brand">FF · FACTCHECK-FINGER</div>
            </div>
            <div style="display:flex;align-items:flex-start;gap:6px">
              <div style="text-align:right">
                <div class="ff-batt-num">${trust.total}</div>
                <div class="ff-batt-pt">점</div>
              </div>
              <span class="ff-batt-close">✕</span>
            </div>
          </div>
          <div class="ff-batt-bar-area">
            <div class="ff-batt-track">
              <div class="ff-batt-fill" style="width:${trust.total}%;background:${trust.fillColor}"></div>
              <div class="ff-batt-pct">${trust.total}점</div>
            </div>
            <div class="ff-batt-nub"></div>
          </div>
        </div>

        <!-- BODY -->
        <div class="ff-card-body">

          <!-- 제목 -->
          <div class="ff-title-box">📰 ${title.slice(0, 110)}</div>

          <!-- 요약 (LLM) -->
          <div class="ff-sec">
            <div class="ff-sec-head">
              <span class="ff-sec-num">요약</span>
              <span class="ff-sec-icon">📰</span>
              <span class="ff-sec-title">뉴스 요약</span>
              <span class="ff-sec-arrow">▼</span>
            </div>
            <div class="ff-sec-body">
              <div id="ff-b-summary">${llmSkel}</div>
            </div>
          </div>

          <!-- 01 육하원칙 -->
          <div class="ff-sec">
            <div class="ff-sec-head">
              <span class="ff-sec-num">01</span><span class="ff-sec-icon">📋</span>
              <span class="ff-sec-title">육하원칙 기반 자동 검증</span>
              <span class="ff-sec-badge ${w5c.bdg}">${trust.cnt}/6</span>
              <span class="ff-sec-arrow">▼</span>
            </div>
            <div class="ff-sec-body">
              <div class="ff-bar"><div class="ff-bar-fill ${w5c.bar}" style="width:${trust.w5S}%"></div></div>
              ${w5Html}
            </div>
          </div>

          <!-- 02 신뢰도 점수 -->
          <div class="ff-sec">
            <div class="ff-sec-head">
              <span class="ff-sec-num">02</span><span class="ff-sec-icon">🎯</span>
              <span class="ff-sec-title">신뢰도 점수 즉시 표시</span>
              <span class="ff-sec-badge" style="background:rgba(0,48,135,.07);color:#003087;border-color:rgba(0,48,135,.2)">${trust.total}점</span>
              <span class="ff-sec-arrow">▼</span>
            </div>
            <div class="ff-sec-body">
              <div style="display:flex;justify-content:space-between;font-size:10px;margin:6px 0 3px"><span style="color:#4a607a">육하원칙 <span style="color:#8fa0b4">×40%</span></span><span class="${w5c.cls}" style="font-weight:700">${trust.w5S}점</span></div>
              <div class="ff-bar"><div class="ff-bar-fill ${w5c.bar}" style="width:${trust.w5S}%"></div></div>
              <div style="display:flex;justify-content:space-between;font-size:10px;margin:4px 0 3px"><span style="color:#4a607a">키워드 매칭 <span style="color:#8fa0b4">×35%</span></span><span class="${kwc.cls}" style="font-weight:700">${trust.kwS}점</span></div>
              <div class="ff-bar"><div class="ff-bar-fill ${kwc.bar}" style="width:${trust.kwS}%"></div></div>
              <div style="display:flex;justify-content:space-between;font-size:10px;margin:4px 0 3px"><span style="color:#4a607a">클릭베이트 방어 <span style="color:#8fa0b4">×25%</span></span><span class="${cbc.cls}" style="font-weight:700">${trust.cbS}점</span></div>
              <div class="ff-bar"><div class="ff-bar-fill ${cbc.bar}" style="width:${trust.cbS}%"></div></div>
              <div class="ff-formula">${trust.w5S}×0.40 + ${trust.kwS}×0.35 + ${trust.cbS}×0.25 = <strong style="color:${trust.color}">${trust.total}점</strong></div>
            </div>
          </div>

          <!-- 03 클릭베이트 -->
          <div class="ff-sec">
            <div class="ff-sec-head">
              <span class="ff-sec-num">03</span><span class="ff-sec-icon">🎣</span>
              <span class="ff-sec-title">클릭베이트 감지</span>
              <span class="ff-sec-badge ${cbRc.bdg}">${cb.reasons.length ? cb.reasons.length+'개 감지':'이상 없음'}</span>
              <span class="ff-sec-arrow">▼</span>
            </div>
            <div class="ff-sec-body">
              <div class="ff-bar"><div class="ff-bar-fill ${cbRc.bar}" style="width:${cb.normalized}%"></div></div>
              ${matchTags?`<div class="ff-tag-lbl">✅ 본문 매칭</div><div class="ff-tags">${matchTags}</div>`:''}
              ${missTags?`<div class="ff-tag-lbl" style="margin-top:5px">❌ 미발견</div><div class="ff-tags">${missTags}</div>`:''}
              <div style="margin-top:6px">${cbTags}</div>
            </div>
          </div>

          <!-- 04 유사 기사 (LLM) -->
          <div class="ff-sec">
            <div class="ff-sec-head">
              <span class="ff-sec-num">04</span><span class="ff-sec-icon">🔗</span>
              <span class="ff-sec-title">유사 기사 비교 · 출처 추적</span>
              <span class="ff-sec-badge ff-bdg-b">AI</span>
              <span class="ff-sec-arrow">▼</span>
            </div>
            <div class="ff-sec-body">
              <div id="ff-b-04">${llmSkel}</div>
            </div>
          </div>

          <!-- 05 용어 풀이 (LLM) -->
          <div class="ff-sec">
            <div class="ff-sec-head">
              <span class="ff-sec-num">05</span><span class="ff-sec-icon">📖</span>
              <span class="ff-sec-title">용어 풀이 · 경제 지표 연동</span>
              <span class="ff-sec-badge ff-bdg-b">AI</span>
              <span class="ff-sec-arrow">▼</span>
            </div>
            <div class="ff-sec-body">
              <div id="ff-b-05">${llmSkel}</div>
            </div>
          </div>

        </div>
      </div>
    `;

    document.body.appendChild(badge);

    // 필 → 카드
    badge.querySelector('#ff-pill').addEventListener('click', () => {
      badge.classList.remove('ff-collapsed');
      badge.querySelector('#ff-pill').style.display = 'none';
      badge.querySelector('#ff-card').style.display = 'block';
    });

    // 카드 헤더 클릭 → 닫기
    badge.querySelector('#ff-card-close').addEventListener('click', () => {
      badge.classList.add('ff-collapsed');
      badge.querySelector('#ff-pill').style.display = 'flex';
      badge.querySelector('#ff-card').style.display = 'none';
    });

    // 아코디언 — isolated world이므로 addEventListener 직접 바인딩
    badge.querySelectorAll('.ff-sec-head').forEach(head => {
      head.addEventListener('click', (e) => {
        // 닫기 버튼 클릭 이벤트 전파 방지
        if (e.target.classList.contains('ff-batt-close')) return;
        const body  = head.nextElementSibling;
        const arrow = head.querySelector('.ff-sec-arrow');
        const open  = body.classList.toggle('open');
        if (arrow) arrow.classList.toggle('open', open);
      });
    });
  }

  // ============================================================
  //  K. 분석 실행
  // ============================================================
  function analyze() {
    const title = getTitle();
    const body  = getBody();
    if (!body || body.length < 100) return { error: true, message: '본문을 충분히 추출하지 못했습니다.' };

    const cb          = calcClickbait(title);
    const kw          = calcKeywordMatch(title, body);
    const w5          = extract5W1H(title, body);
    const trust       = calcTrust(cb, kw, w5);
    const bodyPreview = getBodyPreview(body);
    const bodyRaw     = body.slice(0, 3000);

    renderBadge(title, cb, kw, w5, trust, bodyPreview);

    // LLM 비동기 분석 (배지용)
    chrome.storage.local.get(['ff_api_key'], ({ ff_api_key }) => {
      if (!ff_api_key) {
        // API 키 없으면 스켈레톤 → 안내 메시지로 교체
        const noKeyHtml = `<div style="font-size:10px;color:#8fa0b4;padding:4px 0">API 키를 설정하면 AI 분석이 활성화됩니다.</div>`;
        ['#ff-b-summary','#ff-b-04','#ff-b-05'].forEach(sel => {
          const el = document.querySelector(`#ff-trust-badge ${sel}`);
          if (el) el.innerHTML = noKeyHtml;
        });
        return;
      }
      chrome.runtime.sendMessage({ action: 'llm_analyze', title, body: bodyRaw }, (res) => {
        if (res?.ok) applyLLMToBadge(res.data);
        else {
          const errHtml = `<div style="font-size:10px;color:#dc2626">⚠ ${res?.message||'분석 실패'}</div>`;
          ['#ff-b-summary','#ff-b-04','#ff-b-05'].forEach(sel => {
            const el = document.querySelector(`#ff-trust-badge ${sel}`);
            if (el) el.innerHTML = errHtml;
          });
        }
      });
    });

    return { title, cb, kw, w5, trust, bodyPreview, bodyRaw };
  }

  if (isNewsPage()) setTimeout(analyze, 2000);

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'analyze') sendResponse(analyze());

    // 팝업에서 유사 기사 검색할 때 현재 페이지 정보 반환
    if (msg.action === 'get_article_info') {
      const title    = getTitle();
      const body     = getBody();
      const keywords = extractKeywords(title).slice(0, 5).map(k => k.word);
      sendResponse({ title, keywords });
    }
  });
})();