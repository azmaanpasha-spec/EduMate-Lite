// A tiny, SAFE Markdown renderer for AI answers.
//
// Safety rule: every piece of text is HTML-escaped FIRST, and only then are
// our own tags (<strong>, <ul>, ...) added. So even if the AI (or a user)
// writes <script>, it is displayed as text and never executed.

import { escapeHtml } from "./utils.js";

const FENCE = /```([\w+#.-]*)[^\n]*\n([\s\S]*?)(?:```|$)/g;

export function renderMarkdown(source) {
  const text = String(source || "").replace(/\r\n/g, "\n");
  let html = "";
  let last = 0;
  let match;
  FENCE.lastIndex = 0;
  while ((match = FENCE.exec(text)) !== null) {
    html += renderBlocks(text.slice(last, match.index));
    html += codeBlock(match[2].replace(/\n$/, ""), match[1]);
    last = FENCE.lastIndex;
    if (match[0].length === 0) FENCE.lastIndex++;
  }
  html += renderBlocks(text.slice(last));
  return html;
}

function codeBlock(code, lang) {
  const language = escapeHtml(lang || "code");
  return `<div class="code-block"><div class="code-head"><span>${language}</span>` +
    `<button type="button" class="msg-action copy-code"><i data-lucide="copy"></i>Copy</button></div>` +
    `<pre><code>${escapeHtml(code)}</code></pre></div>`;
}

// ---------------- inline formatting ----------------
function inline(raw) {
  let s = escapeHtml(raw);
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\*\*(?=\S)(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__(?=\S)(.+?)__/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*\w])\*(?=\S)([^*]+?)\*(?!\*)/g, "$1<em>$2</em>");
  s = s.replace(/(^|[\s(])_(?=\S)([^_]+?)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  // Only http(s) links are allowed (blocks javascript: URLs)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  s = s.replace(/\u0000(\d+)\u0000/g, (_, n) => `<code>${codes[Number(n)]}</code>`);
  return s;
}

// ---------------- block formatting ----------------
const RE = {
  heading: /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/,
  hr: /^\s{0,3}([-*_])(\s*\1){2,}\s*$/,
  quote: /^\s{0,3}>\s?(.*)$/,
  listItem: /^(\s*)([-*+•]|\d+[.)])\s+(.*)$/,
  tableSep: /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/,
};

function isBlockStart(line, next) {
  return RE.heading.test(line) || RE.hr.test(line) || RE.quote.test(line) ||
    RE.listItem.test(line) || (line.includes("|") && next !== undefined && RE.tableSep.test(next));
}

function renderBlocks(text) {
  const lines = text.split("\n");
  let html = "";
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m;

    if ((m = line.match(RE.heading))) {
      const level = Math.min(m[1].length, 4);
      html += `<h${level}>${inline(m[2])}</h${level}>`;
      i++;
    } else if (RE.hr.test(line)) {
      html += "<hr>";
      i++;
    } else if (RE.quote.test(line)) {
      const quoted = [];
      while (i < lines.length && (m = lines[i].match(RE.quote))) { quoted.push(m[1]); i++; }
      html += `<blockquote>${renderBlocks(quoted.join("\n"))}</blockquote>`;
    } else if (line.includes("|") && i + 1 < lines.length && RE.tableSep.test(lines[i + 1])) {
      const rows = [line];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) { rows.push(lines[i]); i++; }
      html += table(rows);
    } else if (RE.listItem.test(line)) {
      const items = [];
      while (i < lines.length) {
        const current = lines[i];
        if ((m = current.match(RE.listItem))) {
          items.push({ indent: m[1].replace(/\t/g, "    ").length, ordered: /\d/.test(m[2]), text: m[3] });
          i++;
        } else if (current.trim() && /^\s+/.test(current) && items.length) {
          items[items.length - 1].text += "\n" + current.trim(); // continuation line
          i++;
        } else if (!current.trim()) {
          let j = i;
          while (j < lines.length && !lines[j].trim()) j++;
          if (j < lines.length && RE.listItem.test(lines[j])) i = j; // list continues after blank line
          else break;
        } else break;
      }
      html += list(items, 0, items[0].indent).html;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !(para.length && isBlockStart(lines[i], lines[i + 1]))) {
        para.push(lines[i].trim());
        i++;
      }
      html += `<p>${para.map(inline).join("<br>")}</p>`;
    }
  }
  return html;
}

function list(items, start, baseIndent) {
  const tag = items[start].ordered ? "ol" : "ul";
  let html = `<${tag}>`;
  let i = start;
  while (i < items.length && items[i].indent >= baseIndent) {
    const item = items[i];
    i++;
    let inner = item.text.split("\n").map(inline).join("<br>");
    if (i < items.length && items[i].indent > item.indent) {
      const sub = list(items, i, items[i].indent);
      inner += sub.html;
      i = sub.next;
    }
    html += `<li>${inner}</li>`;
  }
  return { html: html + `</${tag}>`, next: i };
}

function table(rows) {
  const cells = (row) => row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => inline(c.trim()));
  const [head, ...body] = rows;
  const th = cells(head).map((c) => `<th>${c}</th>`).join("");
  const tr = body.map((r) => `<tr>${cells(r).map((c) => `<td>${c}</td>`).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
}
