// Small helpers shared by every part of the frontend.

// Longer than the backend's worst case (30 s per model x 3 models), so the
// backend can always send its own clear error message first.
const REQUEST_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  constructor(message, status = 0, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Call the backend and return parsed JSON, or throw an ApiError with a friendly message. */
export async function api(path, { method = "GET", body } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw new ApiError("The request timed out. Please try again.", 0, "timeout");
    throw new ApiError("Cannot reach the EduMate server. Make sure the backend is running.", 0, "offline");
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try { data = await response.json(); } catch { /* empty or non-JSON body */ }

  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (HTTP ${response.status}).`;
    throw new ApiError(detail, response.status, data?.error_code || "");
  }
  return data;
}

export function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function formatTime(isoString) {
  const date = isoString ? new Date(isoString) : new Date();
  const now = new Date();
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (date.toDateString() === now.toDateString()) return time;
  return `${date.toLocaleDateString([], { day: "numeric", month: "short" })}, ${time}`;
}

export function wordCount(text) {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/** Re-render Lucide icons for newly inserted elements. */
export function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

export function icon(name) {
  return `<i data-lucide="${name}"></i>`;
}

export function toast(message, type = "success") {
  const box = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(type === "error" ? "circle-alert" : "circle-check")}<span></span>`;
  el.querySelector("span").textContent = message;
  box.appendChild(el);
  refreshIcons();
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 300);
  }, type === "error" ? 4500 : 2200);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Fallback for browsers that block the Clipboard API
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    if (!ok) throw new Error("copy failed");
  }
}

/** Show a confirmation dialog. Resolves to true (confirmed) or false. */
export function confirmDialog({ title, text, okText = "Delete", danger = true }) {
  const modal = document.getElementById("confirmModal");
  const ok = document.getElementById("confirmOk");
  const cancel = document.getElementById("confirmCancel");
  document.getElementById("confirmTitle").textContent = title;
  document.getElementById("confirmText").textContent = text;
  ok.textContent = okText;
  ok.className = `btn ${danger ? "btn-danger" : "btn-primary"}`;
  modal.querySelector(".modal-icon").style.display = danger ? "" : "none";
  modal.classList.remove("hidden");
  ok.focus();

  return new Promise((resolve) => {
    const close = (result) => {
      modal.classList.add("hidden");
      ok.removeEventListener("click", onOk);
      cancel.removeEventListener("click", onCancel);
      modal.removeEventListener("click", onBackdrop);
      document.removeEventListener("keydown", onKey);
      resolve(result);
    };
    const onOk = () => close(true);
    const onCancel = () => close(false);
    const onBackdrop = (e) => { if (e.target === modal) close(false); };
    const onKey = (e) => { if (e.key === "Escape") close(false); };
    ok.addEventListener("click", onOk);
    cancel.addEventListener("click", onCancel);
    modal.addEventListener("click", onBackdrop);
    document.addEventListener("keydown", onKey);
  });
}

/** Put a button into (or out of) a loading state. */
export function setLoading(button, loading, loadingText) {
  const label = button.querySelector("span");
  if (loading) {
    button.dataset.label = label ? label.textContent : "";
    if (label && loadingText) label.textContent = loadingText;
    button.classList.add("loading");
    button.disabled = true;
  } else {
    if (label && button.dataset.label) label.textContent = button.dataset.label;
    button.classList.remove("loading");
    button.disabled = false;
  }
}
