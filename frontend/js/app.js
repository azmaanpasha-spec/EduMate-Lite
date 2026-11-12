// Entry point: theme, sidebar, view switching and AI status.

import { initChat, newChat, currentTitle } from "./chat.js";
import { initQuiz } from "./quiz.js";
import { initSummarizer } from "./summarizer.js";
import { api, refreshIcons } from "./utils.js";

const VIEW_TITLES = { summarizer: "Text Summarizer", quiz: "MCQ Practice Quiz" };
let currentView = "chat";

// ---------------- Theme ----------------
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.getElementById("themeLabel").textContent = theme === "dark" ? "Light mode" : "Dark mode";
  try { localStorage.setItem("edumate-theme", theme); } catch { /* storage blocked */ }
}

function initTheme() {
  applyTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  document.getElementById("themeToggle").addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
}

// ---------------- Sidebar (mobile drawer) ----------------
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("sidebarOverlay");

function openSidebar() {
  sidebar.classList.add("open");
  overlay.classList.add("show");
}

function closeSidebar() {
  sidebar.classList.remove("open");
  overlay.classList.remove("show");
}

// ---------------- Views ----------------
function setTitle(title) {
  if (currentView === "chat") document.getElementById("topbarTitle").textContent = title;
}

function setView(view) {
  currentView = view;
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  document.querySelectorAll(".tool-link").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.getElementById("topbarTitle").textContent = VIEW_TITLES[view] || currentTitle();
  closeSidebar();
  if (view === "chat") document.getElementById("messageInput").focus({ preventScroll: true });
}

// ---------------- AI status ----------------
const banner = document.getElementById("configBanner");
const status = document.getElementById("aiStatus");

function setStatus(kind, text) {
  status.className = `ai-status ${kind}`;
  status.querySelector(".ai-status-text").textContent = text;
}

async function checkHealth() {
  try {
    const health = await api("/api/health");
    if (health.ai.configured) {
      setStatus("ok", `Gemini · ${health.ai.model}`);
      banner.classList.add("hidden");
    } else {
      setStatus("warn", "AI not configured");
      banner.classList.remove("hidden");
    }
  } catch {
    setStatus("bad", "Server offline");
  }
}

/** Called by every feature when an AI request fails. */
function onAiError(err) {
  if (err.code === "ai_not_configured") {
    banner.classList.remove("hidden");
    setStatus("warn", "AI not configured");
  } else if (err.code === "offline") {
    setStatus("bad", "Server offline");
  } else if (err.code === "invalid_api_key") {
    setStatus("bad", "Invalid API key");
  }
}

// ---------------- Start ----------------
function init() {
  initTheme();

  document.getElementById("menuBtn").addEventListener("click", openSidebar);
  document.getElementById("sidebarClose").addEventListener("click", closeSidebar);
  overlay.addEventListener("click", closeSidebar);
  document.querySelectorAll(".tool-link").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));

  const context = { setView, setTitle, onAiError, closeSidebar };
  initChat(context);
  initSummarizer(context);
  initQuiz(context);

  const startNewChat = () => newChat();
  document.getElementById("newChatBtn").addEventListener("click", startNewChat);
  document.getElementById("topNewChat").addEventListener("click", startNewChat);

  refreshIcons();
  checkHealth();
}

init();
