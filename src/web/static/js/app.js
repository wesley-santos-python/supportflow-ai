/* Utilidades compartilhadas do front-end do SupportFlow AI. */

/** Alterna entre tema claro e escuro, persistindo a escolha. */
function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("theme", next); } catch (e) {}
}

/** Ícone SVG inline a partir do sprite (para HTML gerado via JS). */
function icon(id, cls = "ico") {
  return `<svg class="${cls}"><use href="#${id}"/></svg>`;
}

/** Exibe um toast temporário. */
function toast(message, isError = false) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.innerHTML = icon(isError ? "i-alert" : "i-check-circle", "ico sm") +
    `<span>${escapeHtml(message)}</span>`;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = "toast"), 3200);
}

/** Wrapper de fetch que retorna JSON e trata erros de forma uniforme. */
async function api(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

/** Atalho para POST com corpo JSON. */
function postJSON(url, body) {
  return api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Escapa texto para inserção segura em HTML. */
function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
