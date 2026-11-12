// Chat: sending messages, rendering answers and managing chat history.

import { renderMarkdown } from "./markdown.js";
import { api, confirmDialog, copyText, escapeHtml, formatTime, icon, refreshIcons, toast } from "./utils.js";

const MAX_LENGTH = 4000;

const state = {
  conversationId: null,
  title: "New conversation",
  conversations: [],
  sending: false,
};

let ctx; // { setView, setTitle, onAiError, closeSidebar }
const el = {};

export function initChat(context) {
  ctx = context;
  Object.assign(el, {
    scroll: document.getElementById("chatScroll"),
    welcome: document.getElementById("welcome"),
    messages: document.getElementById("messages"),
    form: document.getElementById("composer"),
    input: document.getElementById("messageInput"),
    send: document.getElementById("sendBtn"),
    charCount: document.getElementById("charCount"),
    historyList: document.getElementById("historyList"),
    historyCount: document.getElementById("historyCount"),
  });

  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(el.input.value);
  });

  el.input.addEventListener("input", onInputChange);
  el.input.addEventListener("keydown", (e) => {
    // Enter sends, Shift+Enter makes a new line (ignore while typing with an IME)
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage(el.input.value);
    }
  });

  // Suggestion cards either send a ready-made question or open a tool
  document.getElementById("suggestions").addEventListener("click", (e) => {
    const card = e.target.closest(".suggestion");
    if (!card) return;
    if (card.dataset.action) ctx.setView(card.dataset.action);
    else if (card.dataset.prompt) sendMessage(card.dataset.prompt);
  });

  // Copy / regenerate / retry buttons inside messages (event delegation)
  el.messages.addEventListener("click", onMessageAction);

  document.getElementById("clearHistoryBtn").addEventListener("click", clearHistory);

  loadHistory();
}

// ------------------------------------------------------------------
// Input box
// ------------------------------------------------------------------
function onInputChange() {
  const input = el.input;
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 200) + "px";
  updateSendButton();

  const length = input.value.length;
  el.charCount.textContent = length > MAX_LENGTH * 0.75 ? `${length} / ${MAX_LENGTH}` : "";
  el.charCount.classList.toggle("warn", length > MAX_LENGTH * 0.9);
}

function updateSendButton() {
  el.send.disabled = state.sending || !el.input.value.trim();
  el.send.classList.toggle("loading", state.sending);
}

function setSending(sending) {
  state.sending = sending;
  updateSendButton();
  el.messages.querySelectorAll(".regen-btn, .retry-btn").forEach((b) => (b.disabled = sending));
}

// ------------------------------------------------------------------
// Rendering
// ------------------------------------------------------------------
function showWelcome(show) {
  el.welcome.classList.toggle("hidden", !show);
}

function scrollToBottom() {
  requestAnimationFrame(() => (el.scroll.scrollTop = el.scroll.scrollHeight));
}

function messageElement(message) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${message.role}`;
  wrap.dataset.id = message.id ?? "";

  const avatar = message.role === "assistant"
    ? `<div class="avatar"><img src="assets/logo.svg" alt="EduMate" /></div>`
    : `<div class="avatar">You</div>`;

  wrap.innerHTML = `${avatar}<div class="msg-body"><div class="bubble"></div><div class="msg-meta"></div></div>`;
  const bubble = wrap.querySelector(".bubble");
  const meta = wrap.querySelector(".msg-meta");

  if (message.role === "assistant") {
    bubble.classList.add("markdown");
    bubble.innerHTML = renderMarkdown(message.content);
    wrap._raw = message.content; // raw text used by the Copy button
    meta.innerHTML =
      `<time>${escapeHtml(formatTime(message.timestamp))}</time>` +
      `<button class="msg-action copy-btn" title="Copy response">${icon("copy")}<span>Copy</span></button>` +
      `<button class="msg-action regen-btn" title="Regenerate response">${icon("refresh-cw")}<span>Regenerate</span></button>`;
  } else {
    bubble.textContent = message.content; // plain text: no HTML can be injected
    meta.innerHTML = `<time>${escapeHtml(formatTime(message.timestamp))}</time>`;
  }
  return wrap;
}

function appendMessage(message) {
  const node = messageElement(message);
  el.messages.appendChild(node);
  refreshIcons();
  updateRegenerateButtons();
  return node;
}

/** Only the newest AI answer can be regenerated. */
function updateRegenerateButtons() {
  const answers = el.messages.querySelectorAll(".msg.assistant");
  answers.forEach((m, i) => {
    const btn = m.querySelector(".regen-btn");
    if (btn) btn.classList.toggle("hidden", i !== answers.length - 1);
  });
}

function showTyping() {
  const node = document.createElement("div");
  node.className = "msg assistant typing-msg";
  node.innerHTML =
    `<div class="avatar"><img src="assets/logo.svg" alt="" /></div>` +
    `<div class="msg-body"><div class="bubble typing" aria-label="EduMate is typing"><span></span><span></span><span></span></div>` +
    `<div class="typing-label">EduMate is thinking…</div></div>`;
  el.messages.appendChild(node);
  scrollToBottom();
  return node;
}

function showError(message, retryText) {
  const node = document.createElement("div");
  node.className = "msg assistant error";
  node.innerHTML =
    `<div class="avatar">${icon("circle-alert")}</div>` +
    `<div class="msg-body"><div class="bubble"><div class="error-title">${icon("circle-alert")} Something went wrong</div><div class="error-text"></div></div>` +
    `<div class="msg-meta">${retryText ? `<button class="msg-action retry-btn">${icon("rotate-ccw")}<span>Try again</span></button>` : ""}</div></div>`;
  node.querySelector(".error-text").textContent = message;
  node._retryText = retryText;
  el.messages.appendChild(node);
  refreshIcons();
  scrollToBottom();
}

function clearMessages() {
  el.messages.innerHTML = "";
}

// ------------------------------------------------------------------
// Sending & regenerating
// ------------------------------------------------------------------
export async function sendMessage(rawText) {
  const text = rawText.trim();
  if (!text || state.sending) return;
  if (text.length > MAX_LENGTH) {
    toast(`Messages can be at most ${MAX_LENGTH} characters.`, "error");
    return;
  }

  ctx.setView("chat");
  el.messages.querySelectorAll(".msg.error, .msg.pending").forEach((n) => n.remove());
  el.input.value = "";
  onInputChange();
  showWelcome(false);

  const userNode = appendMessage({ role: "user", content: text, timestamp: new Date().toISOString() });
  const typing = showTyping();
  setSending(true);

  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: { message: text, conversation_id: state.conversationId },
    });
    typing.remove();
    userNode.dataset.id = data.user_message.id;
    appendMessage(data.assistant_message);
    scrollToBottom();

    const isNew = state.conversationId !== data.conversation_id;
    state.conversationId = data.conversation_id;
    state.title = data.title;
    ctx.setTitle(state.title);
    await loadHistory();
    if (isNew) highlightActive();
  } catch (err) {
    typing.remove();
    // Nothing was saved on the server, so mark the question as unsent; "Try again" re-sends it
    userNode.classList.add("pending");
    if (err.status === 404) state.conversationId = null; // conversation was deleted elsewhere
    ctx.onAiError(err);
    showError(err.message, text);
  } finally {
    setSending(false);
    el.input.focus();
  }
}

async function regenerate(messageNode) {
  if (state.sending || !state.conversationId) return;
  const bubble = messageNode.querySelector(".bubble");
  const oldHtml = bubble.innerHTML;
  bubble.classList.remove("markdown");
  bubble.classList.add("typing");
  bubble.innerHTML = "<span></span><span></span><span></span>";
  setSending(true);

  try {
    const data = await api("/api/chat/regenerate", { method: "POST", body: { conversation_id: state.conversationId } });
    const fresh = messageElement(data);
    messageNode.replaceWith(fresh);
    refreshIcons();
    updateRegenerateButtons();
    toast("Generated a new response");
  } catch (err) {
    bubble.classList.remove("typing");
    bubble.classList.add("markdown");
    bubble.innerHTML = oldHtml;
    ctx.onAiError(err);
    toast(err.message, "error");
  } finally {
    setSending(false);
  }
}

async function onMessageAction(e) {
  const button = e.target.closest("button");
  if (!button) return;
  const messageNode = button.closest(".msg");

  if (button.classList.contains("copy-btn")) {
    await copyWithFeedback(button, messageNode._raw);
  } else if (button.classList.contains("copy-code")) {
    await copyWithFeedback(button, button.closest(".code-block").querySelector("code").textContent);
  } else if (button.classList.contains("regen-btn")) {
    regenerate(messageNode);
  } else if (button.classList.contains("retry-btn")) {
    sendMessage(messageNode._retryText); // removes the old error + unsent question first
  }
}

async function copyWithFeedback(button, text) {
  try {
    await copyText(text);
    const label = button.querySelector("span");
    button.classList.add("done");
    if (label) label.textContent = "Copied";
    toast("Copied to clipboard");
    setTimeout(() => {
      button.classList.remove("done");
      if (label) label.textContent = "Copy";
    }, 1800);
  } catch {
    toast("Could not copy. Please select the text manually.", "error");
  }
}

// ------------------------------------------------------------------
// Conversations & history
// ------------------------------------------------------------------
export function newChat() {
  if (state.sending) return;
  state.conversationId = null;
  state.title = "New conversation";
  clearMessages();
  showWelcome(true);
  ctx.setView("chat");
  ctx.setTitle(state.title);
  highlightActive();
  el.input.value = "";
  onInputChange();
  el.input.focus();
}

export function currentTitle() {
  return state.title;
}

async function loadHistory() {
  try {
    state.conversations = await api("/api/history");
    renderHistory();
  } catch (err) {
    el.historyList.innerHTML = `<div class="history-empty">${icon("wifi-off")}Could not load history.<br>${escapeHtml(err.message)}</div>`;
    refreshIcons();
  }
}

function renderHistory() {
  el.historyCount.textContent = state.conversations.length;
  if (!state.conversations.length) {
    el.historyList.innerHTML = `<div class="history-empty">${icon("messages-square")}No conversations yet.<br>Ask your first question!</div>`;
    refreshIcons();
    return;
  }
  el.historyList.innerHTML = "";
  for (const c of state.conversations) {
    const item = document.createElement("div");
    item.className = "history-item";
    item.setAttribute("role", "listitem");
    item.dataset.id = c.id;
    item.innerHTML =
      `<button class="history-open" title="">${icon("message-square")}<span class="history-title"></span></button>` +
      `<button class="history-delete" title="Delete conversation" aria-label="Delete conversation">${icon("trash-2")}</button>`;
    item.querySelector(".history-title").textContent = c.title;
    item.querySelector(".history-open").title = `${c.title} · ${formatTime(c.updated_at)}`;
    item.querySelector(".history-open").addEventListener("click", () => openConversation(c.id));
    item.querySelector(".history-delete").addEventListener("click", () => deleteConversation(c));
    el.historyList.appendChild(item);
  }
  refreshIcons();
  highlightActive();
}

function highlightActive() {
  el.historyList.querySelectorAll(".history-item").forEach((item) => {
    item.classList.toggle("active", Number(item.dataset.id) === state.conversationId);
  });
}

async function openConversation(id) {
  if (state.sending) return;
  ctx.closeSidebar();
  try {
    const data = await api(`/api/history/${id}`);
    state.conversationId = data.id;
    state.title = data.title;
    clearMessages();
    showWelcome(false);
    data.messages.forEach((m) => el.messages.appendChild(messageElement(m)));
    refreshIcons();
    updateRegenerateButtons();
    ctx.setView("chat");
    ctx.setTitle(state.title);
    highlightActive();
    el.scroll.scrollTop = el.scroll.scrollHeight;
  } catch (err) {
    toast(err.message, "error");
    loadHistory();
  }
}

async function deleteConversation(conversation) {
  const ok = await confirmDialog({
    title: "Delete conversation?",
    text: `"${conversation.title}" and all of its messages will be permanently deleted.`,
  });
  if (!ok) return;
  try {
    await api(`/api/history/${conversation.id}`, { method: "DELETE" });
    if (state.conversationId === conversation.id) newChat();
    toast("Conversation deleted");
  } catch (err) {
    toast(err.message, "error");
  }
  loadHistory();
}

async function clearHistory() {
  if (!state.conversations.length) {
    toast("Your chat history is already empty");
    return;
  }
  const ok = await confirmDialog({
    title: "Clear all history?",
    text: `All ${state.conversations.length} conversations will be permanently deleted. This cannot be undone.`,
    okText: "Clear all",
  });
  if (!ok) return;
  try {
    await api("/api/history", { method: "DELETE" });
    newChat();
    toast("Chat history cleared");
  } catch (err) {
    toast(err.message, "error");
  }
  loadHistory();
}
