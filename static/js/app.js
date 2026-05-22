/* ============================================================
   Lite Search — Chat Logic
   ============================================================ */

let isStreaming = false;
let currentSessionId = document.getElementById('current-session-id')?.value || '';

// ── DOM Refs ───────────────────────────────────────────────────
const chatMessages = document.getElementById('chat-messages');
const queryInput   = document.getElementById('query-input');
const sendBtn      = document.getElementById('send-btn');
const welcomeState = document.getElementById('welcome-state');
const sessionsList = document.getElementById('sessions-list');
const topbarSessionId = document.getElementById('topbar-session-id');

// ── Marked.js config ──────────────────────────────────────────
if (typeof marked !== 'undefined') {
  marked.setOptions({ breaks: true, gfm: true });
}
function renderMarkdown(text) {
  if (typeof marked !== 'undefined') return marked.parse(text);
  return `<p>${text.replace(/\n/g, '<br>')}</p>`;
}

// ── Auto-render history ───────────────────────────────────────
document.querySelectorAll('.agent-msg[data-raw]').forEach(el => {
  const raw = el.getAttribute('data-raw');
  if (raw) { el.innerHTML = renderMarkdown(raw); el.removeAttribute('data-raw'); }
});

// ── Input ──────────────────────────────────────────────────────
queryInput?.addEventListener('input', () => {
  queryInput.style.height = 'auto';
  queryInput.style.height = Math.min(queryInput.scrollHeight, 200) + 'px';
  sendBtn.disabled = !queryInput.value.trim() || isStreaming;
});

queryInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) submitQuery();
  }
});

sendBtn?.addEventListener('click', submitQuery);

function useChip(btn) {
  if (queryInput) {
    queryInput.value = btn.textContent;
    queryInput.style.height = 'auto';
    queryInput.style.height = Math.min(queryInput.scrollHeight, 200) + 'px';
    sendBtn.disabled = false;
    queryInput.focus();
  }
}
window.useChip = useChip;

// ── Submit query ───────────────────────────────────────────────
async function submitQuery() {
  const query = queryInput.value.trim();
  if (!query || isStreaming) return;

  isStreaming = true;
  sendBtn.disabled = true;
  queryInput.value = '';
  queryInput.style.height = 'auto';

  if (welcomeState) welcomeState.style.display = 'none';

  const exchange = document.createElement('div');
  exchange.className = 'exchange';
  chatMessages.appendChild(exchange);

  const userMsg = document.createElement('div');
  userMsg.className = 'user-msg';
  userMsg.textContent = query;
  exchange.appendChild(userMsg);

  const agentContainer = document.createElement('div');
  agentContainer.className = 'agent-container';
  exchange.appendChild(agentContainer);

  const thinkingDetails = document.createElement('details');
  thinkingDetails.className = 'thinking-process';
  thinkingDetails.open = true;
  thinkingDetails.innerHTML = `<summary><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: middle;"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg> Agent Reasoning Process</summary>`;
  
  const traceLog = document.createElement('div');
  traceLog.className = 'trace-log';
  thinkingDetails.appendChild(traceLog);
  agentContainer.appendChild(thinkingDetails);

  let currentTrace = appendTrace(traceLog, 'Initiating research...');

  scrollToBottom();

  try {
    await streamResponse(query, traceLog, currentTrace, agentContainer, thinkingDetails);
  } catch (err) {
    appendTrace(traceLog, `System failure: ${err.message}`, 'error');
    console.error(err);
  } finally {
    isStreaming = false;
    sendBtn.disabled = !queryInput.value.trim();
  }
}

// ── Trace helpers ──────────────────────────────────────────────
function appendTrace(container, text, type = 'active') {
  const pill = document.createElement('div');
  pill.className = `trace-pill ${type}`;
  
  if (type === 'active') {
    pill.innerHTML = `<div class="spinner"></div> <span>${escapeHtml(text)}</span>`;
  } else if (type === 'done') {
    pill.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>${escapeHtml(text)}</span>`;
  } else {
    pill.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> <span>${escapeHtml(text)}</span>`;
  }
  
  container.appendChild(pill);
  return pill;
}

function updateTrace(pill, text, type) {
  pill.className = `trace-pill ${type}`;
  if (type === 'done') {
    pill.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>${escapeHtml(text)}</span>`;
  } else if (type === 'error') {
    pill.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> <span>${escapeHtml(text)}</span>`;
  }
}

// ── SSE streaming ──────────────────────────────────────────────
async function streamResponse(query, traceLog, activeTrace, agentContainer, thinkingDetails) {
  return new Promise(async (resolve, reject) => {
    let answerBody = null;
    let rawText = '';
    let currentTrace = activeTrace;

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let data;
          try { data = JSON.parse(line.slice(6)); } catch { continue; }

          if (data.type === 'step') {
            if (currentTrace) updateTrace(currentTrace, currentTrace.textContent.trim(), 'done');
            currentTrace = appendTrace(traceLog, data.text, 'active');
            scrollToBottom();

          } else if (data.type === 'chunk') {
            if (currentTrace) { updateTrace(currentTrace, currentTrace.textContent.trim(), 'done'); currentTrace = null; }
            if (!answerBody) {
              thinkingDetails.open = false; // Auto-collapse thinking when answer starts
              answerBody = document.createElement('div');
              answerBody.className = 'agent-msg markdown-body';
              answerBody.innerHTML = '<span class="stream-cursor"></span>';
              agentContainer.appendChild(answerBody);
            }
            rawText += data.text;
            answerBody.innerHTML = renderMarkdown(rawText) + '<span class="stream-cursor"></span>';
            scrollToBottom();

          } else if (data.type === 'done') {
            if (answerBody) answerBody.innerHTML = renderMarkdown(rawText);
            if (data.citations && data.citations.length > 0) {
              renderCitations(agentContainer, data.citations);
            }
            loadSessions();
            resolve();
            return;

          } else if (data.type === 'error') {
            if (currentTrace) { updateTrace(currentTrace, data.text, 'error'); }
            else { appendTrace(traceLog, data.text, 'error'); }
            resolve();
            return;
          }
        }
      }
      if (answerBody) answerBody.innerHTML = renderMarkdown(rawText);
      resolve();
    } catch (err) { reject(err); }
  });
}

function renderCitations(container, citations) {
  const wrap = document.createElement('div');
  wrap.className = 'citation-container';
  
  const title = document.createElement('div');
  title.className = 'citation-title';
  title.textContent = 'Sources Consulted';
  wrap.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'citation-grid';

  citations.forEach((cite, i) => {
    const a = document.createElement('a');
    a.className = 'citation-card glass';
    a.href = cite.url; a.target = '_blank'; a.rel = 'noopener noreferrer';

    const domain = cite.domain || '';
    const citeTitle = cite.title || cite.url;

    a.innerHTML = `
      <div class="citation-badge">${i + 1}</div>
      <div class="citation-text">
        <span class="citation-domain">${escapeHtml(domain)}</span>
        <span class="citation-link-title">${escapeHtml(citeTitle)}</span>
      </div>
    `;
    grid.appendChild(a);
  });

  wrap.appendChild(grid);
  container.appendChild(wrap);
  scrollToBottom();
}

function scrollToBottom() {
  const chatArea = document.getElementById('chat-area');
  if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
}

// ── Sessions ───────────────────────────────────────────────────
document.getElementById('new-session-btn')?.addEventListener('click', async () => {
  if (isStreaming) return;
  try {
    const res = await fetch('/api/reset', { method: 'POST' });
    const data = await res.json();
    currentSessionId = data.session_id;
    if (topbarSessionId) topbarSessionId.textContent = currentSessionId.slice(0, 8);
    document.getElementById('current-session-id').value = currentSessionId;
    chatMessages.innerHTML = '';
    if (welcomeState) {
      const nw = welcomeState.cloneNode(true);
      nw.style.display = '';
      nw.querySelectorAll('.chip').forEach(c => { c.onclick = function() { useChip(this); }; });
      chatMessages.appendChild(nw);
    }
    loadSessions();
  } catch (err) { console.error('Reset failed:', err); }
});

async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    if (!sessionsList) return;
    if (!data.sessions || data.sessions.length === 0) {
      sessionsList.innerHTML = '<div style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; padding: 20px;">No sessions found</div>';
      return;
    }
    sessionsList.innerHTML = data.sessions.map(s => {
      const active = s.session_id === currentSessionId;
      return `
        <div class="session-item-container">
          <a class="session-item ${active ? 'active' : ''}" data-sid="${s.session_id}" onclick="loadSession('${s.session_id}')">
            <div class="session-query">${escapeHtml(s.first_query)}</div>
            <div class="session-time">${formatRelativeTime(s.timestamp)}</div>
          </a>
          <button class="btn-delete-session" onclick="deleteSession(event, '${s.session_id}')" title="Delete Session">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
          </button>
        </div>`;
    }).join('');
  } catch (err) { console.error(err); }
}

async function deleteSession(event, sessionId) {
  event.stopPropagation();
  if (!confirm("Are you sure you want to delete this session?")) return;
  
  try {
    const res = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
    if (res.ok) {
      if (sessionId === currentSessionId) {
        // Deleted current session, force reload
        document.getElementById('new-session-btn')?.click();
      } else {
        loadSessions();
      }
    }
  } catch (err) { console.error('Delete failed:', err); }
}

async function loadSession(sessionId) {
  if (isStreaming || sessionId === currentSessionId) return;
  try {
    const res = await fetch(`/api/sessions/${sessionId}/load`, { method: 'POST' });
    const data = await res.json();
    currentSessionId = data.session_id;
    if (topbarSessionId) topbarSessionId.textContent = currentSessionId.slice(0, 8);
    document.getElementById('current-session-id').value = currentSessionId;

    chatMessages.innerHTML = '';
    const history = data.history || [];
    if (history.length === 0 && welcomeState) {
      chatMessages.appendChild(welcomeState.cloneNode(true));
    } else {
      history.forEach((turn, idx) => {
        const isLast = idx === history.length - 1;
        const ex = document.createElement('div');
        ex.className = 'exchange';
        
        // Build trace pills for historical steps
        let stepsHtml = '';
        if (turn.steps && turn.steps.length > 0) {
          stepsHtml = turn.steps.map(step => `
            <div class="trace-pill done">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              <span>${escapeHtml(step)}</span>
            </div>
          `).join('');
        }

        // Build citations
        let citationsHtml = '';
        if (turn.citations && turn.citations.length > 0) {
          const cards = turn.citations.map((cite, i) => `
            <a href="${cite.url}" class="citation-card glass" target="_blank" rel="noopener noreferrer">
              <div class="citation-badge">${i + 1}</div>
              <div class="citation-text">
                <span class="citation-domain">${escapeHtml(cite.domain || '')}</span>
                <span class="citation-link-title">${escapeHtml(cite.title || cite.url)}</span>
              </div>
            </a>
          `).join('');
          
          citationsHtml = `
            <div class="citation-container">
              <div class="citation-title">Sources Consulted</div>
              <div class="citation-grid">${cards}</div>
            </div>
          `;
        }

        ex.innerHTML = `
          <div class="user-msg">${escapeHtml(turn.query)}</div>
          <div class="agent-container">
            <details class="thinking-process" ${isLast ? 'open' : ''}>
              <summary>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: middle;"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                Agent Reasoning Process
              </summary>
              <div class="trace-log">${stepsHtml}</div>
            </details>
            <div class="agent-msg markdown-body">${renderMarkdown(turn.response)}</div>
            ${citationsHtml}
          </div>
        `;
        chatMessages.appendChild(ex);
      });
      scrollToBottom();
    }
    document.querySelectorAll('.session-item').forEach(el => el.classList.toggle('active', el.dataset.sid === sessionId));
  } catch (err) { console.error(err); }
}
window.loadSession = loadSession;

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function formatRelativeTime(ts) {
  if (!ts) return '';
  try {
    const date = new Date(ts.replace(' ', 'T') + 'Z');
    const mins = Math.round((Date.now() - date.getTime()) / 60000);
    if (mins < 1)  return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const h = Math.round(mins / 60);
    if (h < 24)    return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  } catch { return ''; }
}

loadSessions();
queryInput?.focus();
