// Text summarizer: sends pasted text to the backend and shows the AI summary.

import { renderMarkdown } from "./markdown.js";
import { api, copyText, escapeHtml, icon, refreshIcons, setLoading, toast, wordCount } from "./utils.js";

const MIN_WORDS = 20;

const SAMPLE_TEXT = `Photosynthesis is the process by which green plants, algae and some bacteria convert light energy into chemical energy. It takes place mainly in the chloroplasts of leaf cells, which contain a green pigment called chlorophyll. Chlorophyll absorbs light, mostly in the blue and red wavelengths, and reflects green light, which is why leaves look green.

The process has two main stages. In the light-dependent reactions, which occur in the thylakoid membranes, light energy splits water molecules into oxygen, protons and electrons. The oxygen is released into the atmosphere as a by-product, while the energy is stored temporarily in the molecules ATP and NADPH. In the second stage, the light-independent reactions or Calvin cycle, which take place in the stroma, the plant uses ATP and NADPH to fix carbon dioxide from the air into glucose.

The overall equation is: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2. Several factors affect the rate of photosynthesis, including light intensity, carbon dioxide concentration and temperature. Photosynthesis is essential for life on Earth because it produces the oxygen we breathe and forms the base of almost every food chain.`;

let lastSummary = "";

export function initSummarizer({ onAiError }) {
  const input = document.getElementById("summaryInput");
  const button = document.getElementById("summarizeBtn");
  const counter = document.getElementById("summaryWordCount");
  const resultCard = document.getElementById("summaryResult");
  const output = document.getElementById("summaryOutput");
  const meta = document.getElementById("summaryMeta");
  const copyBtn = document.getElementById("copySummaryBtn");

  const update = () => {
    const words = wordCount(input.value);
    counter.textContent = words < MIN_WORDS && words > 0
      ? `${words} words · at least ${MIN_WORDS} needed`
      : `${words} word${words === 1 ? "" : "s"}`;
    if (!button.classList.contains("loading")) button.disabled = words < MIN_WORDS;
  };
  input.addEventListener("input", update);

  document.getElementById("sampleTextBtn").addEventListener("click", () => {
    input.value = SAMPLE_TEXT;
    update();
    input.focus();
  });

  button.addEventListener("click", async () => {
    const text = input.value.trim();
    if (wordCount(text) < MIN_WORDS) return;
    const length = document.querySelector('input[name="summaryLength"]:checked').value;

    setLoading(button, true, "Summarizing…");
    resultCard.classList.remove("hidden");
    copyBtn.disabled = true;
    meta.textContent = "";
    output.innerHTML = `<div class="loading-note">${icon("sparkles")} EduMate is reading your text…</div>` +
      `<div class="skeleton"><div></div><div></div><div></div><div></div></div>`;
    refreshIcons();

    try {
      const data = await api("/api/summarize", { method: "POST", body: { text, length } });
      lastSummary = data.summary;
      output.innerHTML = renderMarkdown(data.summary);
      meta.textContent = `${data.length === "short" ? "Short" : "Detailed"} · ${data.original_words} → ${data.summary_words} words`;
      copyBtn.disabled = false;
    } catch (err) {
      lastSummary = "";
      onAiError(err);
      output.innerHTML = `<div class="inline-error">${icon("circle-alert")}<span>${escapeHtml(err.message)}</span></div>`;
    } finally {
      setLoading(button, false);
      update();
      refreshIcons();
      resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  });

  copyBtn.addEventListener("click", async () => {
    if (!lastSummary) return;
    try {
      await copyText(lastSummary);
      toast("Summary copied to clipboard");
    } catch {
      toast("Could not copy. Please select the text manually.", "error");
    }
  });

  update();
}
