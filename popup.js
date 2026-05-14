/* ─── FF | Factcheck-Finger · popup.js · v4.0 ─── */

// ── 색상 유틸 ──────────────────────────────────────────
function ci(score, invert = false) {
  const s = invert ? 100 - score : score;
  if (s >= 75) return { c: '#16a34a', bar: 'bg-g', badge: 'bdg-g', cls: 'c-g' };
  if (s >= 50) return { c: '#b45309', bar: 'bg-y', badge: 'bdg-y', cls: 'c-y' };
  return { c: '#dc2626', bar: 'bg-r', badge: 'bdg-r', cls: 'c-r' };
}
function trustMeta(score) {
  if (score >= 80) return { grade: '신뢰 높음', desc: '신뢰할 수 있는 기사입니다.', fillColor: '#4ade80' };
  if (score >= 60) return { grade: '보통',      desc: '일부 항목을 추가로 확인하세요.', fillColor: '#fbbf24' };
  if (score >= 40) return { grade: '주의 필요', desc: '사실 확인이 권장됩니다.', fillColor: '#fb923c' };
  return            { grade: '신뢰 낮음', desc: '출처와 사실관계를 반드시 확인하세요.', fillColor: '#f87171' };
}

// ── 아코디언 ───────────────────────────────────────────
function bindAccordion() {
  document.querySelectorAll('.fc-head').forEach(head => {
    if (head.dataset.bound) return;
    head.dataset.bound = '1';
    head.addEventListener('click', () => {
      const body  = head.nextElementSibling;
      const arrow = head.querySelector('.fc-arrow');
      const open  = body.classList.toggle('open');
      if (arrow) arrow.classList.toggle('open', open);

      // 04 섹션 처음 열 때 네이버 유사 기사 검색
      if (open && head.dataset.section === '04' && !head.dataset.loaded) {
        head.dataset.loaded = '1';
        const el = document.getElementById('ff-llm-04');
        if (el) el.innerHTML = skeletonHTML(3);

        chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
          chrome.tabs.sendMessage(tab.id, { action: 'get_article_info' }, (info) => {
            chrome.runtime.sendMessage(
              { action: 'find_similar', title: info?.title || '', keywords: info?.keywords || [] },
              (res) => {
                if (!el) return;
                if (res?.ok && res.data?.articles?.length) {
                  const articles = res.data.articles;
                  el.innerHTML = `
                    <div class="sub-txt" style="margin-top:4px;margin-bottom:8px">${res.data.verdict}</div>
                    ${articles.map(a => `
                      <div style="padding:7px 0;border-bottom:1px solid #f5f5f3">
                        <div style="font-size:11px;font-weight:700;color:#0d1b2a;margin-bottom:3px;line-height:1.4">
                          ${a.url ? `<a href="${a.url}" target="_blank" style="color:#003087;text-decoration:none">${a.title}</a>` : a.title}
                        </div>
                        <div style="font-size:10px;color:#8fa0b4;margin-bottom:3px">${a.source} · ${a.pub_date?.slice(0,16) || ''}</div>
                        <div style="font-size:11px;color:#4a607a;line-height:1.5">${a.summary}</div>
                      </div>`).join('')}
                  `;
                } else {
                  el.innerHTML = `<div class="sub-txt" style="color:#8fa0b4">유사 기사를 찾지 못했습니다.</div>`;
                }
              }
            );
          });
        });
      }
    });
  });
}

// ── 로딩 스켈레톤 ──────────────────────────────────────
function skeletonHTML(lines = 2) {
  return Array.from({ length: lines }, (_, i) =>
    `<div class="skel ${i === lines - 1 ? 'w70' : 'w85'}"></div>`
  ).join('');
}

// ── LLM 섹션 업데이트 ─────────────────────────────────
function applyLLMData(llm) {
  // 요약
  const sumEl = document.getElementById('ff-llm-summary');
  if (sumEl) sumEl.innerHTML = llm.summary
    ? `<div class="summary-body">${llm.summary}</div>`
    : '<div class="summary-body" style="color:#8fa0b4">요약 불가</div>';

  // 유사 기사 (04) — fact_claims/keywords는 별도 영역에만 표시
  // 실제 유사 기사는 아코디언 클릭 시 find_similar로 채워짐
  const claimsEl = document.getElementById('ff-llm-claims');
  if (claimsEl) {
    const claims = llm.fact_claims || [];
    const kws    = llm.similar_keywords || [];
    claimsEl.innerHTML = `
      ${claims.length ? `
        <div class="tag-lbl" style="margin-top:8px">🔍 검증이 필요한 사실 주장</div>
        <div style="margin-top:4px">${claims.map(c =>
          `<div class="llm-claim"><span class="llm-claim-dot"></span>${c}</div>`).join('')}
        </div>` : ''}
      ${kws.length ? `
        <div class="tag-lbl" style="margin-top:8px">🔎 관련 검색어</div>
        <div class="tag-row" style="margin-top:4px">
          ${kws.map(k => `<span class="tag blue">${k}</span>`).join('')}
        </div>` : ''}
    `;
  }

  // 용어 + 경제 지표 (05)
  const ind05 = document.getElementById('ff-llm-05');
  if (ind05) {
    const terms = llm.terms || [];
    const inds  = llm.economic_indicators || [];
    ind05.innerHTML = `
      ${terms.length ? `
        <div class="tag-lbl">📖 전문 용어 풀이</div>
        <div style="margin-top:4px">${terms.map(t =>
          `<div class="llm-term">
            <div class="llm-term-name">${t.term}</div>
            <div class="llm-term-exp">${t.explanation}</div>
          </div>`).join('')}
        </div>` : '<div class="sub-txt" style="color:#8fa0b4">발견된 전문 용어 없음</div>'}
      ${inds.length ? `
        <div class="tag-lbl" style="margin-top:10px">📊 경제 지표</div>
        <div style="margin-top:4px">${inds.map(ind =>
          `<div class="llm-ind">
            <div class="llm-ind-name">${ind.name}</div>
            <div class="llm-ind-val">${ind.value}</div>
            <div class="llm-ind-ctx">${ind.context}</div>
          </div>`).join('')}
        </div>` : ''}
    `;
  }
}

// ── 메인 렌더 ─────────────────────────────────────────
function renderResult(res, hasApiKey) {
  const el = document.getElementById('result');
  el.style.display = 'block';

  if (!res || res.error) {
    el.innerHTML = `<div class="err-box">⚠️ ${res?.message || '분석 실패 — 뉴스 기사 페이지에서 시도해 주세요.'}</div>`;
    return;
  }

  const t  = res.trust;
  const tm = trustMeta(t.total);
  const w5 = res.w5;
  const kw = res.kw;
  const cb = res.cb;

  const w5c  = ci(t.w5S);
  const kwc  = ci(t.kwS);
  const cbc  = ci(t.cbS);
  const cbRc = ci(cb.normalized, true);

  const w5Html = Object.entries(w5).map(([, v]) => `
    <div class="w5r">
      <div class="w5-dot ${v.found ? 'hit' : 'miss'}">${v.found ? '✓' : '✗'}</div>
      <span class="w5-lbl">${v.label}</span>
      ${v.found ? `<span class="w5-ev">${v.evidence.slice(0,2).join(', ')}</span>`
                : `<span class="w5-no">미발견</span>`}
    </div>`).join('');

  const matchTags = kw.matched.slice(0,8).map(w => `<span class="tag ok">${w}</span>`).join('');
  const missTags  = kw.missed.slice(0,4).map(w => `<span class="tag miss">${w}</span>`).join('');
  const cbDetail  = cb.reasons.length
    ? `<div class="tag-row">${cb.reasons.map(r => `<span class="tag warn">⚠ ${r}</span>`).join('')}</div>`
    : `<div class="ok-txt">✅ 자극적 패턴이 감지되지 않았습니다.</div>`;

  // LLM 섹션 초기 상태
  const llmLoading = hasApiKey ? skeletonHTML(2) : `
    <div class="beta-box">
      <span class="beta-pill">BETA</span>
      API 키를 설정하면 AI 분석이 활성화됩니다.
    </div>`;

  el.innerHTML = `

    <!-- BATTERY HERO -->
    <div class="battery-hero">
      <div class="battery-top">
        <div class="battery-left">
          <div class="battery-grade">${tm.grade}</div>
          <div class="battery-desc">${tm.desc}</div>
        </div>
        <div class="battery-score-wrap">
          <span class="battery-score-num">${t.total}</span>
          <span class="battery-score-pt">점</span>
        </div>
      </div>
      <div class="battery-bar-area">
        <div class="battery-track">
          <div class="battery-fill" style="width:${t.total}%;background:${tm.fillColor}"></div>
          <div class="battery-pct">${t.total}점</div>
        </div>
        <div class="battery-nub"></div>
      </div>
    </div>

    <!-- 뉴스 요약 (LLM) -->
    <div class="summary-card">
      <div class="sec-label">📰 뉴스 요약</div>
      ${res.title ? `<div class="summary-title">${res.title.slice(0,80)}</div>` : ''}
      <div id="ff-llm-summary">${llmLoading}</div>
    </div>

    <!-- 01 육하원칙 -->
    <div class="fc">
      <div class="fc-head">
        <span class="fc-num">01</span><span class="fc-icon">📋</span>
        <span class="fc-title">육하원칙 기반 자동 검증</span>
        <span class="fc-badge ${w5c.badge}">${t.cnt}/6 항목</span>
        <span class="fc-arrow">▼</span>
      </div>
      <div class="fc-body">
        <div class="bar"><div class="bar-fill ${w5c.bar}" style="width:${t.w5S}%"></div></div>
        <div class="sub-txt" style="margin-top:0;margin-bottom:6px">누가·무엇을·언제·어디서·왜·어떻게 — 6항목 자동 추출</div>
        ${w5Html}
      </div>
    </div>

    <!-- 02 신뢰도 점수 -->
    <div class="fc">
      <div class="fc-head">
        <span class="fc-num">02</span><span class="fc-icon">🎯</span>
        <span class="fc-title">신뢰도 점수 즉시 표시</span>
        <span class="fc-badge" style="background:rgba(0,48,135,.07);color:#003087;border-color:rgba(0,48,135,.2)">${t.total}점</span>
        <span class="fc-arrow">▼</span>
      </div>
      <div class="fc-body">
        <div class="sd-row"><span class="lbl">육하원칙 충족도<span class="wt">×40%</span></span><span class="val ${w5c.cls}">${t.w5S}점</span></div>
        <div class="bar"><div class="bar-fill ${w5c.bar}" style="width:${t.w5S}%"></div></div>
        <div class="sd-row"><span class="lbl">키워드 매칭률<span class="wt">×35%</span></span><span class="val ${kwc.cls}">${t.kwS}점</span></div>
        <div class="bar"><div class="bar-fill ${kwc.bar}" style="width:${t.kwS}%"></div></div>
        <div class="sd-row"><span class="lbl">클릭베이트 방어<span class="wt">×25%</span></span><span class="val ${cbc.cls}">${t.cbS}점</span></div>
        <div class="bar"><div class="bar-fill ${cbc.bar}" style="width:${t.cbS}%"></div></div>
        <div class="formula">${t.w5S}×0.40 + ${t.kwS}×0.35 + ${t.cbS}×0.25 = <strong style="color:${tm.fillColor==='#4ade80'?'#16a34a':tm.fillColor}">${t.total}점</strong></div>
      </div>
    </div>

    <!-- 03 클릭베이트 -->
    <div class="fc">
      <div class="fc-head">
        <span class="fc-num">03</span><span class="fc-icon">🎣</span>
        <span class="fc-title">클릭베이트 감지</span>
        <span class="fc-badge ${cbRc.badge}">${cb.reasons.length ? cb.reasons.length+'개 감지' : '이상 없음'}</span>
        <span class="fc-arrow">▼</span>
      </div>
      <div class="fc-body">
        <div class="sd-row" style="margin-top:6px"><span class="lbl">클릭베이트 위험도</span><span class="val ${cbRc.cls}">${cb.normalized}/100</span></div>
        <div class="bar"><div class="bar-fill ${cbRc.bar}" style="width:${cb.normalized}%"></div></div>
        <div class="sd-row"><span class="lbl">키워드 매칭률</span><span class="val ${kwc.cls}">${kw.score}%</span></div>
        <div class="bar"><div class="bar-fill ${kwc.bar}" style="width:${kw.score}%"></div></div>
        ${matchTags ? `<div class="tag-lbl">✅ 본문 매칭 키워드</div><div class="tag-row">${matchTags}</div>` : ''}
        ${missTags  ? `<div class="tag-lbl" style="margin-top:6px">❌ 미발견 키워드</div><div class="tag-row">${missTags}</div>` : ''}
        <div style="margin-top:6px">${cbDetail}</div>
      </div>
    </div>

    <!-- 04 유사 기사 비교 (네이버) -->
    <div class="fc">
      <div class="fc-head" data-section="04">
        <span class="fc-num">04</span><span class="fc-icon">🔗</span>
        <span class="fc-title">유사 기사 비교 · 출처 추적</span>
        <span class="fc-badge bdg-b">네이버</span>
        <span class="fc-arrow">▼</span>
      </div>
      <div class="fc-body">
        <div id="ff-llm-04"><div class="hint" style="padding:6px 0;color:#8fa0b4;font-size:11px">▼ 클릭하면 유사 기사를 검색합니다</div></div>
        <div id="ff-llm-claims"></div>
      </div>
    </div>

    <!-- 05 용어 풀이 (LLM) -->
    <div class="fc">
      <div class="fc-head">
        <span class="fc-num">05</span><span class="fc-icon">📖</span>
        <span class="fc-title">용어 즉시 풀이 · 경제 지표 연동</span>
        <span class="fc-badge bdg-b">${hasApiKey ? 'AI' : '베타'}</span>
        <span class="fc-arrow">▼</span>
      </div>
      <div class="fc-body">
        <div id="ff-llm-05">${llmLoading}</div>
      </div>
    </div>

  `;

  bindAccordion();
}

// ── API 키 설정 UI ────────────────────────────────────
document.getElementById('keyToggleBtn').addEventListener('click', () => {
  const panel = document.getElementById('keyPanel');
  panel.classList.toggle('open');
  if (panel.classList.contains('open')) {
    chrome.storage.local.get(['ff_api_key'], ({ ff_api_key }) => {
      if (ff_api_key) {
        document.getElementById('keyInput').value = ff_api_key;
        document.getElementById('keyStatus').textContent = '✅ API 키가 저장되어 있습니다.';
        document.getElementById('keyStatus').className = 'key-status ok';
      }
    });
  }
});

document.getElementById('keySaveBtn').addEventListener('click', () => {
  const key = document.getElementById('keyInput').value.trim();
  const st  = document.getElementById('keyStatus');
  if (!key.startsWith('sk-ant-')) {
    st.textContent = '⚠ 유효한 Anthropic API 키를 입력하세요 (sk-ant-로 시작)';
    st.className = 'key-status err';
    return;
  }
  chrome.storage.local.set({ ff_api_key: key }, () => {
    st.textContent = '✅ 저장되었습니다.';
    st.className = 'key-status ok';
    setTimeout(() => document.getElementById('keyPanel').classList.remove('open'), 1200);
  });
});

// ── 분석 버튼 ─────────────────────────────────────────
document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const btn = document.getElementById('analyzeBtn');
  btn.classList.add('loading');
  btn.innerHTML = '<span>⏳</span> 분석 중...';

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  // 1단계: 즉시 휴리스틱 분석
  chrome.tabs.sendMessage(tab.id, { action: 'analyze' }, async (res) => {
    btn.classList.remove('loading');
    btn.innerHTML = '<span>🔍</span> 다시 분석하기';

    const { ff_api_key } = await chrome.storage.local.get(['ff_api_key']);
    renderResult(res, !!ff_api_key);

    // 2단계: LLM 분석 (API 키 있을 때만)
    if (ff_api_key && res && !res.error) {
      chrome.runtime.sendMessage(
        { action: 'llm_analyze', title: res.title, body: res.bodyRaw || res.title },
        (llmRes) => {
          if (llmRes?.ok) applyLLMData(llmRes.data);
          else {
            const errHtml = `<div class="sub-txt" style="color:#dc2626">⚠ ${llmRes?.message || 'LLM 분석 실패'}</div>`;
            ['ff-llm-summary','ff-llm-04','ff-llm-05'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.innerHTML = errHtml;
            });
          }
        }
      );
    }
  });
});