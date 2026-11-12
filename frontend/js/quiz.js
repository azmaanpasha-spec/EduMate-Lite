// MCQ quiz: generate questions, let the student answer, then show the backend's score.

import { api, confirmDialog, escapeHtml, icon, refreshIcons, setLoading, toast } from "./utils.js";

const LETTERS = ["A", "B", "C", "D"];

const quiz = {
  data: null,     // { quiz_id, subject, topic, difficulty, questions }
  answers: [],    // selected option index per question (or null)
  index: 0,       // current question
};

let el = {};
let onAiError = () => {};

export function initQuiz(context) {
  onAiError = context.onAiError;
  el = {
    setup: document.getElementById("quizSetup"),
    play: document.getElementById("quizPlay"),
    results: document.getElementById("quizResults"),
    subject: document.getElementById("quizSubject"),
    topic: document.getElementById("quizTopic"),
    generate: document.getElementById("generateQuizBtn"),
    info: document.getElementById("quizInfo"),
    progressText: document.getElementById("quizProgressText"),
    progressBar: document.getElementById("quizProgressBar"),
    dots: document.getElementById("quizDots"),
    question: document.getElementById("quizQuestion"),
    options: document.getElementById("quizOptions"),
    prev: document.getElementById("prevQuestionBtn"),
    next: document.getElementById("nextQuestionBtn"),
    submit: document.getElementById("submitQuizBtn"),
  };

  el.setup.addEventListener("submit", (e) => {
    e.preventDefault();
    generateQuiz();
  });
  el.prev.addEventListener("click", () => goTo(quiz.index - 1));
  el.next.addEventListener("click", () => goTo(quiz.index + 1));
  el.submit.addEventListener("click", submitQuiz);

  el.options.addEventListener("click", (e) => {
    const option = e.target.closest(".option");
    if (option) selectAnswer(Number(option.dataset.index));
  });
  el.dots.addEventListener("click", (e) => {
    const dot = e.target.closest(".quiz-dot");
    if (dot) goTo(Number(dot.dataset.index));
  });

  // Keyboard shortcuts while answering: 1-4 / A-D select, arrows move
  document.addEventListener("keydown", (e) => {
    if (el.play.classList.contains("hidden") || !el.play.offsetParent) return;
    if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (!document.getElementById("confirmModal").classList.contains("hidden")) return;
    const key = e.key.toUpperCase();
    if (["1", "2", "3", "4"].includes(key)) selectAnswer(Number(key) - 1);
    else if (LETTERS.includes(key)) selectAnswer(LETTERS.indexOf(key));
    else if (e.key === "ArrowRight") goTo(quiz.index + 1);
    else if (e.key === "ArrowLeft") goTo(quiz.index - 1);
  });

  document.getElementById("retakeQuizBtn").addEventListener("click", generateQuiz);
  document.getElementById("newQuizBtn").addEventListener("click", () => {
    showStep("setup");
    el.topic.focus();
  });
}

function showStep(step) {
  el.setup.classList.toggle("hidden", step !== "setup");
  el.play.classList.toggle("hidden", step !== "play");
  el.results.classList.toggle("hidden", step !== "results");
}

function settings() {
  return {
    subject: el.subject.value.trim(),
    topic: el.topic.value.trim(),
    num_questions: Number(document.querySelector('input[name="quizCount"]:checked').value),
    difficulty: document.querySelector('input[name="quizDifficulty"]:checked').value,
  };
}

// ------------------------------------------------------------------
// Generate
// ------------------------------------------------------------------
async function generateQuiz() {
  const body = settings();
  if (!body.subject || !body.topic) {
    showStep("setup");
    (body.subject ? el.topic : el.subject).focus();
    toast("Please enter a subject and a topic.", "error");
    return;
  }

  showStep("setup");
  setLoading(el.generate, true, `Generating ${body.num_questions} questions…`);
  el.setup.querySelectorAll("input").forEach((i) => (i.disabled = true));
  removeSetupError();

  try {
    quiz.data = await api("/api/quiz/generate", { method: "POST", body });
    quiz.answers = new Array(quiz.data.questions.length).fill(null);
    quiz.index = 0;
    el.info.innerHTML =
      `<span class="chip">${escapeHtml(quiz.data.subject)}</span>` +
      `<span class="chip">${escapeHtml(quiz.data.topic)}</span>` +
      `<span class="chip diff-${quiz.data.difficulty}">${capitalize(quiz.data.difficulty)}</span>`;
    showStep("play");
    renderQuestion();
  } catch (err) {
    onAiError(err);
    showSetupError(err.message);
  } finally {
    setLoading(el.generate, false);
    el.setup.querySelectorAll("input").forEach((i) => (i.disabled = false));
  }
}

function showSetupError(message) {
  const box = document.createElement("div");
  box.className = "inline-error";
  box.id = "quizError";
  box.innerHTML = `${icon("circle-alert")}<span>${escapeHtml(message)}</span>`;
  el.setup.appendChild(box);
  refreshIcons();
}

function removeSetupError() {
  document.getElementById("quizError")?.remove();
}

// ------------------------------------------------------------------
// Taking the quiz
// ------------------------------------------------------------------
function renderQuestion() {
  const questions = quiz.data.questions;
  const total = questions.length;
  const q = questions[quiz.index];
  const answered = quiz.answers.filter((a) => a !== null).length;

  el.progressText.textContent = `Question ${quiz.index + 1} of ${total} · ${answered} answered`;
  el.progressBar.style.width = `${(answered / total) * 100}%`;

  el.dots.innerHTML = questions
    .map((_, i) => {
      const cls = ["quiz-dot", quiz.answers[i] !== null ? "answered" : "", i === quiz.index ? "current" : ""].join(" ");
      return `<button class="${cls}" data-index="${i}" aria-label="Go to question ${i + 1}">${i + 1}</button>`;
    })
    .join("");

  el.question.textContent = `${quiz.index + 1}. ${q.question}`;
  el.options.innerHTML = "";
  q.options.forEach((text, i) => {
    const button = document.createElement("button");
    const selected = quiz.answers[quiz.index] === i;
    button.className = `option${selected ? " selected" : ""}`;
    button.dataset.index = i;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", selected);
    button.innerHTML = `<span class="option-letter">${LETTERS[i]}</span><span class="option-text"></span>`;
    button.querySelector(".option-text").textContent = text;
    el.options.appendChild(button);
  });

  el.prev.disabled = quiz.index === 0;
  el.next.classList.toggle("hidden", quiz.index === total - 1);
}

function selectAnswer(optionIndex) {
  if (!quiz.data || optionIndex < 0 || optionIndex > 3) return;
  quiz.answers[quiz.index] = optionIndex;
  renderQuestion();
}

function goTo(index) {
  if (!quiz.data || index < 0 || index >= quiz.data.questions.length) return;
  quiz.index = index;
  renderQuestion();
}

// ------------------------------------------------------------------
// Submit & results
// ------------------------------------------------------------------
async function submitQuiz() {
  const unanswered = quiz.answers.filter((a) => a === null).length;
  if (unanswered > 0) {
    const ok = await confirmDialog({
      title: "Submit quiz?",
      text: `You have ${unanswered} unanswered question${unanswered > 1 ? "s" : ""}. Unanswered questions count as incorrect.`,
      okText: "Submit anyway",
      danger: false,
    });
    if (!ok) return;
  }

  setLoading(el.submit, true, "Checking…");
  try {
    const result = await api("/api/quiz/submit", {
      method: "POST",
      body: { quiz_id: quiz.data.quiz_id, answers: quiz.answers },
    });
    renderResults(result);
    showStep("results");
    document.getElementById("view-quiz").scrollTop = 0;
  } catch (err) {
    toast(err.message, "error");
    if (err.status === 404) showStep("setup"); // quiz expired (e.g. server restarted)
  } finally {
    setLoading(el.submit, false);
  }
}

function renderResults(r) {
  const pct = r.score_percentage;
  const ring = document.getElementById("scoreRing");
  ring.style.setProperty("--ring", pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--primary)" : "var(--danger)");
  ring.style.setProperty("--pct", 0);
  requestAnimationFrame(() => requestAnimationFrame(() => ring.style.setProperty("--pct", pct)));

  document.getElementById("scorePercent").textContent = `${Math.round(pct)}%`;
  document.getElementById("scoreHeadline").textContent =
    pct >= 80 ? "Excellent work! 🎉" : pct >= 50 ? "Good job — keep going!" : "Keep practising, you'll get there!";
  document.getElementById("scoreTopic").textContent = `${r.topic} · ${capitalize(r.difficulty)}`;
  document.getElementById("statTotal").textContent = r.total_questions;
  document.getElementById("statCorrect").textContent = r.correct_answers;
  document.getElementById("statIncorrect").textContent = r.incorrect_answers;
  document.getElementById("statPercent").textContent = `${pct}%`;

  const list = document.getElementById("reviewList");
  list.innerHTML = "";
  r.review.forEach((item, n) => {
    const card = document.createElement("div");
    card.className = `review-item ${item.is_correct ? "correct" : "wrong"}`;
    const options = item.options
      .map((text, i) => {
        let cls = "review-opt";
        let tag = "";
        if (i === item.correct_index) { cls += " is-correct"; tag = i === item.selected_index ? "Your answer ✓" : "Correct answer"; }
        else if (i === item.selected_index) { cls += " is-wrong"; tag = "Your answer"; }
        return `<div class="${cls}"><b>${LETTERS[i]}</b><span>${escapeHtml(text)}</span>${tag ? `<span class="tag">${tag}</span>` : ""}</div>`;
      })
      .join("");
    card.innerHTML =
      `<div class="review-q">${icon(item.is_correct ? "circle-check" : "circle-x")}<span>${n + 1}. ${escapeHtml(item.question)}</span></div>` +
      `<div class="review-options">${options}</div>` +
      (item.selected_index === null ? `<div class="meta">You skipped this question.</div>` : "") +
      `<div class="review-expl"><strong>Explanation:</strong> ${escapeHtml(item.explanation)}</div>`;
    list.appendChild(card);
  });
  refreshIcons();
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
