/* ═══════════════════════════════════════════════
   VinLex AI — Chat UI
═══════════════════════════════════════════════ */

// ── State ──────────────────────────────────────
let currentConvId = null;
let isLoading = false;

// ── Init ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Configure marked.js
  if (typeof marked !== 'undefined') {
    marked.setOptions({
      breaks: true,
      gfm: true,
    });
  }
  await loadConversations();
});

// ── Sidebar & Conversations ────────────────────

async function loadConversations() {
  try {
    const res = await fetch('/api/conversations');
    const convs = await res.json();
    renderConvList(convs);

    if (convs.length > 0) {
      await loadConversation(convs[0].id);
    } else {
      showEmptyState();
    }
  } catch (e) {
    console.error('Failed to load conversations:', e);
  }
}

function renderConvList(convs) {
  const list = document.getElementById('conv-list');
  const emptyMsg = document.getElementById('conv-empty-msg');

  // Remove old conv items (keep empty msg)
  list.querySelectorAll('.conv-item').forEach(el => el.remove());

  if (convs.length === 0) {
    emptyMsg.style.display = '';
    return;
  }
  emptyMsg.style.display = 'none';

  convs.forEach(conv => {
    const item = createConvItem(conv);
    list.appendChild(item);
  });
}

function createConvItem(conv) {
  const div = document.createElement('div');
  div.className = 'conv-item' + (conv.id === currentConvId ? ' active' : '');
  div.dataset.convId = conv.id;
  div.onclick = () => loadConversation(conv.id);

  div.innerHTML = `
    <span class="conv-title">${escapeHtml(conv.title)}</span>
    <button class="conv-delete-btn" onclick="deleteConversation(event, '${conv.id}')" title="Xóa">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
      </svg>
    </button>
  `;
  return div;
}

async function loadConversation(convId) {
  currentConvId = convId;

  // Update sidebar active state
  document.querySelectorAll('.conv-item').forEach(el => {
    el.classList.toggle('active', el.dataset.convId === convId);
  });

  // Load messages
  try {
    const res = await fetch(`/api/conversations/${convId}/messages`);
    if (!res.ok) return;
    const messages = await res.json();

    clearMessages();
    if (messages.length === 0) {
      showEmptyState();
    } else {
      hideEmptyState();
      messages.forEach(msg => renderMessage(msg));
      scrollToBottom();
    }

    // Update title
    const convItem = document.querySelector(`[data-conv-id="${convId}"] .conv-title`);
    const title = convItem ? convItem.textContent : 'VinLex AI';
    document.getElementById('current-conv-title').textContent = title;
  } catch (e) {
    console.error('Failed to load conversation:', e);
  }

  // Close mobile sidebar
  closeSidebar();
}

async function createNewConversation() {
  try {
    const res = await fetch('/api/conversations', { method: 'POST' });
    const conv = await res.json();
    currentConvId = conv.id;
    clearMessages();
    showEmptyState();
    document.getElementById('current-conv-title').textContent = 'Cuộc trò chuyện mới';
    await loadConversations();
    // Re-select in sidebar
    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.convId === conv.id);
    });
    document.getElementById('chat-input').focus();
  } catch (e) {
    console.error('Failed to create conversation:', e);
  }
}

async function deleteConversation(event, convId) {
  event.stopPropagation();
  if (!confirm('Xóa cuộc trò chuyện này?')) return;

  try {
    await fetch(`/api/conversations/${convId}`, { method: 'DELETE' });
    if (currentConvId === convId) {
      currentConvId = null;
    }
    await loadConversations();
    if (!currentConvId) {
      clearMessages();
      showEmptyState();
      document.getElementById('current-conv-title').textContent = 'VinLex AI';
    }
  } catch (e) {
    console.error('Failed to delete conversation:', e);
  }
}

// ── Send message ───────────────────────────────

async function sendMessage() {
  if (isLoading) return;
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;

  // Ensure we have a conversation
  if (!currentConvId) {
    const res = await fetch('/api/conversations', { method: 'POST' });
    const conv = await res.json();
    currentConvId = conv.id;
  }

  // Clear input immediately
  input.value = '';
  autoResize(input);

  // Hide empty state, show user bubble
  hideEmptyState();
  renderMessage({ role: 'user', content: message });
  scrollToBottom();

  // Clear any old alerts
  clearAlerts();

  // Show typing indicator
  showTypingIndicator();
  setLoading(true);

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: currentConvId, message }),
    });

    hideTypingIndicator();

    if (!res.ok) {
      throw new Error(`Server error: ${res.status}`);
    }

    const data = await res.json();

    // Update current conv id (server may have created a new one)
    if (data.conversation_id) {
      currentConvId = data.conversation_id;
    }

    // Render assistant response
    renderMessage({
      role: 'assistant',
      content: data.answer,
      sources: data.sources || [],
    });

    // Handle special cases
    if (data.redirect_to_contact) {
      showContactAlert();
    }
    if (data.suggest_counseling) {
      showCounselingAlert();
    }

    scrollToBottom();

    // Refresh sidebar to update title
    await refreshConvList();

  } catch (e) {
    hideTypingIndicator();
    showErrorAlert('Có lỗi xảy ra khi kết nối với máy chủ. Vui lòng thử lại.');
    console.error('Chat error:', e);
  } finally {
    setLoading(false);
  }
}

async function refreshConvList() {
  try {
    const res = await fetch('/api/conversations');
    const convs = await res.json();
    renderConvList(convs);
    // Re-apply active state
    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.convId === currentConvId);
    });
    // Update topbar title
    const activeItem = document.querySelector(`.conv-item[data-conv-id="${currentConvId}"] .conv-title`);
    if (activeItem) {
      document.getElementById('current-conv-title').textContent = activeItem.textContent;
    }
  } catch (e) { /* silent */ }
}

// ── Render messages ────────────────────────────

function renderMessage(msg) {
  const messagesEl = document.getElementById('chat-messages');
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper ${msg.role}`;

  const bubble = document.createElement('div');
  bubble.className = `msg-bubble ${msg.role}`;

  if (msg.role === 'assistant') {
    // Render markdown
    if (typeof marked !== 'undefined') {
      bubble.innerHTML = marked.parse(msg.content || '');
    } else {
      bubble.textContent = msg.content || '';
    }

    // Add sources if present
    if (msg.sources && msg.sources.length > 0) {
      bubble.appendChild(renderSources(msg.sources));
    }
  } else {
    bubble.textContent = msg.content || '';
  }

  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
}

function renderSources(sources) {
  const block = document.createElement('div');
  block.className = 'sources-block';

  const toggle = document.createElement('div');
  toggle.className = 'sources-toggle';
  toggle.innerHTML = `
    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414
               a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
    </svg>
    <span>${sources.length} nguồn trích dẫn</span>
    <svg class="w-3 h-3 toggle-arrow transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
    </svg>
  `;

  const list = document.createElement('div');
  list.className = 'sources-list';
  list.style.display = 'none';

  sources.forEach(src => {
    const pill = document.createElement('span');
    pill.className = 'source-pill';
    const name = src.pdf_name || src.source_pdf || 'Tài liệu';
    const page = src.page ? `, trang ${src.page}` : '';
    pill.innerHTML = `📄 ${escapeHtml(name)}${page}`;
    list.appendChild(pill);
  });

  toggle.onclick = () => {
    const isOpen = list.style.display !== 'none';
    list.style.display = isOpen ? 'none' : 'flex';
    toggle.querySelector('.toggle-arrow').style.transform = isOpen ? '' : 'rotate(180deg)';
  };

  block.appendChild(toggle);
  block.appendChild(list);
  return block;
}

// ── Typing indicator ───────────────────────────

function showTypingIndicator() {
  const messagesEl = document.getElementById('chat-messages');
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper assistant';
  wrapper.id = 'typing-indicator';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble assistant';
  bubble.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
}

function hideTypingIndicator() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

// ── Alert banners ──────────────────────────────

function showContactAlert() {
  const alert = document.createElement('div');
  alert.className = 'alert-banner alert-contact';
  alert.innerHTML = `
    <span>📞</span>
    <div class="flex-1">
      <strong>Câu hỏi về tài chính/học bổng</strong> — Vui lòng liên hệ trực tiếp với Phòng Đào Tạo.
      <a href="/contact" class="underline ml-1 font-semibold">Xem thông tin liên hệ →</a>
    </div>
    <button class="alert-close" onclick="this.parentElement.remove()">✕</button>
  `;
  document.getElementById('alert-area').appendChild(alert);
}

function showCounselingAlert() {
  const alert = document.createElement('div');
  alert.className = 'alert-banner alert-counseling';
  alert.innerHTML = `
    <span>💙</span>
    <div class="flex-1">
      Tôi nhận thấy bạn đang có vẻ căng thẳng. Nếu cần hỗ trợ tâm lý, hãy liên hệ
      <strong>Bộ phận Tư vấn Tâm lý VinUniversity</strong> hoặc Phòng Đào Tạo.
    </div>
    <button class="alert-close" onclick="this.parentElement.remove()">✕</button>
  `;
  document.getElementById('alert-area').appendChild(alert);
}

function showErrorAlert(msg) {
  const alert = document.createElement('div');
  alert.className = 'alert-banner alert-error';
  alert.innerHTML = `
    <span>⚠️</span>
    <div class="flex-1">${escapeHtml(msg)}</div>
    <button class="alert-close" onclick="this.parentElement.remove()">✕</button>
  `;
  document.getElementById('alert-area').appendChild(alert);
}

function clearAlerts() {
  document.getElementById('alert-area').innerHTML = '';
}

// ── Suggested questions ────────────────────────

function handleSuggestedQuestion(text) {
  const input = document.getElementById('chat-input');
  input.value = text;
  autoResize(input);
  sendMessage();
}

// ── UI helpers ─────────────────────────────────

function clearMessages() {
  const el = document.getElementById('chat-messages');
  el.innerHTML = '';
}

function showEmptyState() {
  const emptyState = document.getElementById('empty-state');
  if (emptyState) return; // already there

  const el = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.id = 'empty-state';
  div.className = 'empty-state';
  div.innerHTML = `
    <div class="mb-2">
      <img src="/static/images/vinuniversity_logo.png" alt="VinUni" class="h-14 w-auto mx-auto opacity-80" />
    </div>
    <h2 class="text-xl font-bold text-vin-navy mt-3">Xin chào! Tôi là VinLex AI</h2>
    <p class="text-gray-500 text-sm mt-2 max-w-sm">
      Trợ lý tư vấn quy chế học vụ VinUniversity. Hãy hỏi tôi bất kỳ điều gì về học vụ!
    </p>
    <div class="suggestions-grid">
      ${(typeof SUGGESTED_QUESTIONS !== 'undefined' ? SUGGESTED_QUESTIONS : []).map(q =>
        `<button class="suggestion-card" onclick="handleSuggestedQuestion('${escapeHtml(q).replace(/'/g, "\\'")}')">${escapeHtml(q)}</button>`
      ).join('')}
    </div>
    <p class="text-xs text-gray-400 mt-6">
      ⚠️ Câu trả lời chỉ mang tính tham khảo. Vui lòng xác nhận với Phòng Đào Tạo cho các quyết định quan trọng.
    </p>
  `;
  el.appendChild(div);
}

function hideEmptyState() {
  const el = document.getElementById('empty-state');
  if (el) el.remove();
}

function scrollToBottom() {
  const el = document.getElementById('chat-messages');
  el.scrollTop = el.scrollHeight;
}

function setLoading(val) {
  isLoading = val;
  const btn = document.getElementById('send-btn');
  const input = document.getElementById('chat-input');
  btn.disabled = val;
  input.disabled = val;
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Mobile sidebar ─────────────────────────────

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    closeSidebar();
  } else {
    sidebar.classList.add('open');
    overlay.classList.add('active');
  }
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('active');
}
