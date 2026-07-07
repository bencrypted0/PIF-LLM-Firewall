/**
 * PIF Agent — Chat Application Logic
 * Handles conversation history and UI interactions.
 */

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  history: [],        // [{role, content}]
  isStreaming: false,
  currentModel: null,
};

// ── DOM References ─────────────────────────────────────────────────────────────
const el = {
  appShell: document.querySelector('.app-shell'),
  sidebar: document.getElementById('sidebar'),
  sidebarToggle: document.getElementById('sidebarToggle'),
  mobileToggle: document.getElementById('mobileToggle'),
  newChatBtn: document.getElementById('newChatBtn'),
  clearBtn: document.getElementById('clearBtn'),
  themeToggleBtn: document.getElementById('themeToggleBtn'),
  welcomeState: document.getElementById('welcomeState'),
  messagesList: document.getElementById('messagesList'),
  messagesContainer: document.getElementById('messagesContainer'),
  messageInput: document.getElementById('messageInput'),
  sendBtn: document.getElementById('sendBtn'),
  sendIcon: document.getElementById('sendIcon'),
  stopIcon: document.getElementById('stopIcon'),
  charCount: document.getElementById('charCount'),
  chatSubtitle: document.getElementById('chatSubtitle'),
  statusDot: document.getElementById('statusDot'),
  statusModel: document.getElementById('statusModel'),
  statusUrl: document.getElementById('statusUrl'),
  modelsList: document.getElementById('modelsList'),
};

// ── Utilities ─────────────────────────────────────────────────────────────────
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatMessage(text) {
  // Simple markdown-like formatting
  let html = escapeHtml(text);

  // Code blocks (```...```)
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code>${code.trim()}</code></pre>`;
  });

  // Inline code (`...`)
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold (**...**)
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic (*...*)
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  return html;
}

function scrollToBottom(smooth = true) {
  el.messagesContainer.scrollTo({
    top: el.messagesContainer.scrollHeight,
    behavior: smooth ? 'smooth' : 'instant',
  });
}

function setSubtitle(text) {
  el.chatSubtitle.textContent = text;
}

// ── Health & Models ───────────────────────────────────────────────────────────
async function checkHealth() {
  el.statusDot.className = 'status-indicator checking';
  el.statusModel.textContent = 'Checking...';

  try {
    const res = await fetch('/health');
    const data = await res.json();

    state.currentModel = data.model;

    if (data.status === 'ok') {
      el.statusDot.className = 'status-indicator online';
      el.statusModel.textContent = data.model;
      el.statusUrl.textContent = data.ollama_url;
      setSubtitle(`Connected · ${data.model}`);
    } else {
      el.statusDot.className = 'status-indicator error';
      el.statusModel.textContent = 'Ollama unreachable';
      el.statusUrl.textContent = data.ollama_url;
      setSubtitle('Ollama not reachable — check your container');
    }
  } catch (err) {
    el.statusDot.className = 'status-indicator error';
    el.statusModel.textContent = 'Server error';
    setSubtitle('Cannot connect to backend');
  }
}

async function selectModel(modelName, modelElement) {
  if (state.isStreaming) return;
  if (modelName === state.currentModel) return;

  const originalText = modelElement.textContent;
  modelElement.textContent = `Switching...`;
  modelElement.classList.add('switching');

  try {
    const res = await fetch('/models/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelName }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || 'Failed to switch model');
    }

    const data = await res.json();
    state.currentModel = data.model;

    // Update status indicators and chat header subtitle
    el.statusModel.textContent = data.model;
    setSubtitle(`Connected · ${data.model}`);
  } catch (err) {
    console.error(err);
    // Display error temporarily on the status model
    el.statusModel.textContent = 'Switch failed';
    setTimeout(() => {
      el.statusModel.textContent = state.currentModel || 'Ollama';
    }, 3000);
  } finally {
    await loadModels();
  }
}

async function loadModels() {
  try {
    const res = await fetch('/models');
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();

    el.modelsList.innerHTML = '';
    if (data.models && data.models.length > 0) {
      data.models.forEach(m => {
        const div = document.createElement('div');
        div.className = 'model-item' + (m === data.current ? ' active' : '');
        div.textContent = m;
        div.addEventListener('click', () => selectModel(m, div));
        el.modelsList.appendChild(div);
      });
    } else {
      el.modelsList.innerHTML = '<span class="models-loading">No models found</span>';
    }
  } catch {
    el.modelsList.innerHTML = '<span class="models-loading">Could not load models</span>';
  }
}

// ── Message Rendering ─────────────────────────────────────────────────────────
function createMessageElement(role, content = '', model = null) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';

  if (role === 'user') {
    avatar.textContent = 'U';
  } else {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
      <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
      <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
    </svg>`;
  }

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  const roleLabel = document.createElement('div');
  roleLabel.className = 'message-role';
  if (role === 'user') {
    roleLabel.textContent = 'You';
  } else if (model === 'firewall') {
    roleLabel.textContent = 'Injection Firewall · Blocked';
    roleLabel.style.color = 'var(--error)';
    roleLabel.style.fontWeight = '600';
  } else {
    roleLabel.textContent = `Agent · ${model || state.currentModel || 'Ollama'}`;
  }

  const textDiv = document.createElement('div');
  textDiv.className = 'message-text';
  textDiv.innerHTML = formatMessage(content);

  contentDiv.appendChild(roleLabel);
  contentDiv.appendChild(textDiv);
  wrapper.appendChild(avatar);
  wrapper.appendChild(contentDiv);

  return { wrapper, textDiv };
}

function createTypingIndicator() {
  const wrapper = document.createElement('div');
  wrapper.className = 'typing-indicator';
  wrapper.id = 'typingIndicator';

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.style.background = 'linear-gradient(135deg, hsl(180, 70%, 55%), hsl(200, 70%, 50%))';
  avatar.innerHTML = `<svg viewBox="0 0 24 24" fill="none" width="16" height="16">
    <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M2 17L12 22L22 17" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M2 12L12 17L22 12" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
  </svg>`;

  const dots = document.createElement('div');
  dots.className = 'typing-dots';
  dots.innerHTML = '<span></span><span></span><span></span>';

  wrapper.appendChild(avatar);
  wrapper.appendChild(dots);
  return wrapper;
}

// ── Send & Stream ─────────────────────────────────────────────────────────────
async function sendMessage(userText) {
  if (!userText.trim() || state.isStreaming) return;

  // Hide welcome, show messages
  el.welcomeState.style.display = 'none';

  // Add user message
  const { wrapper: userMsg } = createMessageElement('user', userText);
  el.messagesList.appendChild(userMsg);
  state.history.push({ role: 'user', content: userText });
  scrollToBottom();

  // Show typing indicator
  const typingEl = createTypingIndicator();
  el.messagesList.appendChild(typingEl);
  scrollToBottom();

  // Update UI state
  state.isStreaming = true;
  el.sendBtn.disabled = true;
  el.messageInput.disabled = true;
  setSubtitle('Thinking...');

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userText,
        history: state.history.slice(0, -1), // exclude current user msg
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    typingEl.remove();

    if (data.response) {
      const { wrapper } = createMessageElement('assistant', data.response, data.model);
      el.messagesList.appendChild(wrapper);
      state.history.push({ role: 'assistant', content: data.response });
      scrollToBottom();
    } else {
      throw new Error('Empty response from model');
    }
  } catch (err) {
    typingEl.remove();
    const { wrapper } = createMessageElement(
      'assistant',
      `Error: ${err.message}\n\nMake sure the local backend and Ollama are running correctly.`
    );
    el.messagesList.appendChild(wrapper);
    scrollToBottom();
  } finally {
    state.isStreaming = false;
    el.sendBtn.disabled = !el.messageInput.value.trim();
    el.messageInput.disabled = false;
    el.messageInput.focus();
    setSubtitle(`Connected · ${state.currentModel || 'Ollama'}`);
  }
}

// ── Input Handling ────────────────────────────────────────────────────────────
function autoResize() {
  el.messageInput.style.height = 'auto';
  el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 200) + 'px';
}

el.messageInput.addEventListener('input', () => {
  autoResize();
  const len = el.messageInput.value.length;
  el.sendBtn.disabled = len === 0 || state.isStreaming;
  el.charCount.textContent = len > 0 ? `${len} chars` : '';
});

el.messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const text = el.messageInput.value.trim();
    if (text && !state.isStreaming) {
      el.messageInput.value = '';
      el.messageInput.style.height = 'auto';
      el.charCount.textContent = '';
      el.sendBtn.disabled = true;
      sendMessage(text);
    }
  }
});

el.sendBtn.addEventListener('click', () => {
  const text = el.messageInput.value.trim();
  if (text && !state.isStreaming) {
    el.messageInput.value = '';
    el.messageInput.style.height = 'auto';
    el.charCount.textContent = '';
    el.sendBtn.disabled = true;
    sendMessage(text);
  }
});

// ── Suggestion Chips ──────────────────────────────────────────────────────────
document.querySelectorAll('.suggestion-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const prompt = chip.dataset.prompt;
    if (prompt && !state.isStreaming) {
      sendMessage(prompt);
    }
  });
});

// ── Clear Conversation ─────────────────────────────────────────────────────────
function clearConversation() {
  state.history = [];
  el.messagesList.innerHTML = '';
  el.welcomeState.style.display = '';
  el.welcomeState.style.removeProperty('display');
  setSubtitle(`Connected · ${state.currentModel || 'Ollama'}`);
}

el.clearBtn.addEventListener('click', clearConversation);
el.newChatBtn.addEventListener('click', clearConversation);

// ── Sidebar Toggle ─────────────────────────────────────────────────────────────
function toggleSidebar() {
  if (window.innerWidth <= 768) {
    el.sidebar.classList.toggle('open');
  } else {
    el.appShell.classList.toggle('sidebar-collapsed');
  }
}

el.sidebarToggle.addEventListener('click', toggleSidebar);
el.mobileToggle.addEventListener('click', toggleSidebar);

// Close sidebar on outside click (mobile)
document.addEventListener('click', (e) => {
  if (window.innerWidth <= 768) {
    if (!el.sidebar.contains(e.target) &&
      !el.mobileToggle.contains(e.target) &&
      !el.sidebarToggle.contains(e.target)) {
      el.sidebar.classList.remove('open');
    }
  }
});

// ── Theme Management ──────────────────────────────────────────────────────────
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
}

el.themeToggleBtn.addEventListener('click', toggleTheme);

// ── Init ──────────────────────────────────────────────────────────────────────
(async function init() {
  initTheme();
  await checkHealth();
  await loadModels();
  el.messageInput.focus();

  // Refresh health every 30s
  setInterval(checkHealth, 30000);
})();
