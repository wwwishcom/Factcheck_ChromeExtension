/* ─── FF | Factcheck-Finger · background.js · v4.1 ─── */

const API_BASE = "http://localhost:8000";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  // ── LLM 분석 → 백엔드 /api/analyze ──────────────────
  if (msg.action === "llm_analyze") {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title:       msg.title       || "",
            body:        msg.body        || "",
            url:         msg.url         || "",
            trust_score: msg.trustScore  || 0,
            w5_score:    msg.w5Score     || 0,
            kw_score:    msg.kwScore     || 0,
            cb_score:    msg.cbScore     || 0,
            grade:       msg.grade       || "",
          })
        });
        if (!res.ok) throw new Error(`서버 오류 ${res.status}`);
        const json = await res.json();
        sendResponse({ ok: true, data: json.data, article_id: json.article_id });
      } catch (e) {
        // 백엔드 꺼져있으면 Claude API 직접 폴백
        chrome.storage.local.get(["ff_api_key"], async ({ ff_api_key }) => {
          if (!ff_api_key) {
            sendResponse({ error: true, message: "백엔드 서버가 꺼져 있습니다. run.bat을 실행해 주세요." });
            return;
          }
          try {
            const data = await callClaudeDirectly(ff_api_key, msg.title, msg.body);
            sendResponse({ ok: true, data });
          } catch (e2) {
            sendResponse({ error: true, message: e2.message });
          }
        });
      }
    })();
    return true;
  }

  // ── 유사 기사 검색 → /api/similar ────────────────────
  if (msg.action === "find_similar") {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/similar`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: msg.title, keywords: msg.keywords || [] })
        });
        const json = await res.json();
        sendResponse({ ok: true, data: json.data });
      } catch (e) {
        sendResponse({ error: true, message: e.message });
      }
    })();
    return true;
  }

  // ── 출처 신뢰도 → /api/source ─────────────────────────
  if (msg.action === "get_source") {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/source/${encodeURIComponent(msg.domain)}`);
        const json = await res.json();
        sendResponse({ ok: true, data: json.data });
      } catch (e) {
        sendResponse({ error: true, message: e.message });
      }
    })();
    return true;
  }

});

// ── 폴백: Claude 직접 호출 ───────────────────────────────
async function callClaudeDirectly(apiKey, title, body) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 1024,
      messages: [{ role: "user", content: `뉴스 기사 분석. JSON만 반환.\n제목: ${title}\n본문: ${(body||"").slice(0,1500)}\n형식: {"summary":"요약","terms":[],"economic_indicators":[],"fact_claims":[],"similar_keywords":[]}` }]
    })
  });

  const json = await res.json();

  // API 오류 처리 (인증 실패, 잘못된 키 등)
  if (!res.ok || json.type === "error") {
    const msg = json?.error?.message || `API 오류 (${res.status})`;
    throw new Error(msg);
  }
  if (!json.content || !json.content[0]) {
    throw new Error("Claude API 응답이 비어있습니다.");
  }

  try {
    const text = json.content[0].text.replace(/```json|```/g, "").trim();
    // JSON 객체 부분만 추출
    const match = text.match(/\{[\s\S]*\}/);
    return JSON.parse(match ? match[0] : text);
  } catch {
    // 파싱 실패시 기본값 반환
    return {
      summary: json.content[0].text.slice(0, 200),
      terms: [], economic_indicators: [], fact_claims: [], similar_keywords: []
    };
  }
}
