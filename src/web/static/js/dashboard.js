/* Lógica do dashboard: filtros, cards, modal de resposta e sincronização. */

let currentFilters = { categoria: "Todos", urgencia: "Todos", status: "Todos", search: "" };
let activeTicket = null;

/* ------------------------------------------------------------------ Listagem */
async function loadTickets() {
  currentFilters.urgencia = document.getElementById("urgFilter").value;
  currentFilters.status = document.getElementById("statusFilter").value;
  currentFilters.search = document.getElementById("search").value.trim();

  const params = new URLSearchParams();
  Object.entries(currentFilters).forEach(([k, v]) => {
    if (v && v !== "Todos") params.set(k, v);
  });

  try {
    const data = await api("/api/tickets?" + params.toString());
    renderCards(data.tickets);
  } catch (e) {
    toast("Erro ao carregar: " + e.message, true);
  }
}

let _debounce;
function debouncedLoad() {
  clearTimeout(_debounce);
  _debounce = setTimeout(loadTickets, 300);
}

function renderCards(tickets) {
  const container = document.getElementById("cards");
  const empty = document.getElementById("emptyState");
  container.innerHTML = "";
  empty.hidden = tickets.length > 0;

  tickets.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";
    card.onclick = () => openTicket(t.id);
    card.innerHTML = `
      <div class="card-top">
        <span class="card-subject">${escapeHtml(t.subject || "(sem assunto)")}</span>
        <span class="badge ${t.urgencia}">${escapeHtml(t.urgencia || "Baixa")}</span>
      </div>
      <span class="card-sender">${escapeHtml(t.sender || "")}</span>
      <span class="card-summary">${escapeHtml(t.resumo || "Análise pendente...")}</span>
      <div class="card-foot">
        <span class="card-cat">📁 ${escapeHtml(t.categoria || "Outros")}</span>
        <span>${t.has_attachments ? '<span class="dot-attach">📎</span> ' : ""}${fmtDate(t.created_at)}</span>
      </div>`;
    container.appendChild(card);
  });
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) +
    " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/* ------------------------------------------------------------------- Filtros */
document.getElementById("catChips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  document.querySelectorAll("#catChips .chip").forEach((c) => c.classList.remove("active"));
  chip.classList.add("active");
  currentFilters.categoria = chip.dataset.val;
  loadTickets();
});

/* ----------------------------------------------------------- Sincronização */
async function syncNow() {
  const btn = document.getElementById("syncBtn");
  btn.disabled = true;
  btn.textContent = "⟳ Sincronizando...";
  try {
    const r = await api("/api/sync", { method: "POST" });
    toast(`✓ ${r.processed} ticket(s) sincronizado(s)`);
    await loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "⟳ Sincronizar";
  }
}

/* ------------------------------------------------------------------ Exportar */
function exportMenu() {
  window.open("/report", "_blank");
}

/* --------------------------------------------------------------------- Modal */
async function openTicket(id) {
  try {
    activeTicket = await api("/api/tickets/" + id);
    renderModal(activeTicket);
    document.getElementById("modal").hidden = false;
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

function closeModal() {
  document.getElementById("modal").hidden = true;
  activeTicket = null;
}

function renderModal(t) {
  const attachments = (t.attachments || []).map((a) => `
    <div class="attach-item">
      <span>📎 ${escapeHtml(a.filename)}</span>
      <span class="modal-row">
        <a class="btn tiny ghost" href="/api/attachments/${a.id}/file" target="_blank">Abrir / Imprimir</a>
        <button class="btn tiny" onclick="downloadAttachment(${a.id})">Baixar</button>
      </span>
    </div>`).join("");

  document.getElementById("modalBody").innerHTML = `
    <span class="badge ${t.urgencia}">${escapeHtml(t.urgencia)}</span>
    <h2>${escapeHtml(t.subject || "(sem assunto)")}</h2>
    <p class="muted small">De: ${escapeHtml(t.sender)} · ${escapeHtml(t.categoria)} · ${escapeHtml(t.status)}</p>

    <div class="field">
      <label class="muted small">Resumo da IA</label>
      <p>${escapeHtml(t.resumo || "—")}</p>
    </div>

    <div class="modal-section">
      <label class="muted small">✍️ Resposta (sugerida pela IA — edite à vontade)</label>
      <textarea id="replyBody" rows="6">${escapeHtml(t.resposta_sugerida || "")}</textarea>
      <div class="modal-row" style="margin-top:10px">
        <input id="rewriteInstruction" class="search" placeholder="Reescrever com IA: ex. 'mais formal'" />
        <button class="btn ghost" onclick="rewriteWithAI(${t.id})">🤖 Reescrever</button>
      </div>
    </div>

    <div class="modal-section">
      <label class="muted small">📎 Anexar arquivos</label>
      <input type="file" id="replyFiles" multiple style="margin-top:6px" />
      ${attachments ? `<div class="attach-list">${attachments}</div>` : ""}
    </div>

    <div class="modal-section modal-row" style="justify-content:space-between">
      <div class="modal-row">
        <input type="datetime-local" id="scheduleAt" class="search" />
        <button class="btn ghost" onclick="scheduleReply(${t.id})">📅 Agendar</button>
      </div>
      <button class="btn primary" onclick="sendReply(${t.id})">✉️ Enviar agora</button>
    </div>`;
}

/* --------------------------------------------------------------- Ações IA */
async function rewriteWithAI(id) {
  const instruction = document.getElementById("rewriteInstruction").value.trim() || "melhore o tom";
  const text = document.getElementById("replyBody").value;
  try {
    const r = await postJSON(`/api/tickets/${id}/rewrite`, { text, instruction });
    document.getElementById("replyBody").value = r.text;
    toast("✓ Resposta reescrita pela IA");
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

/* ------------------------------------------------------ Enviar / Agendar */
function buildReplyForm(id) {
  const fd = new FormData();
  fd.append("body", document.getElementById("replyBody").value);
  const files = document.getElementById("replyFiles").files;
  for (const f of files) fd.append("files", f);
  return fd;
}

async function sendReply(id) {
  const fd = buildReplyForm(id);
  try {
    await api(`/api/tickets/${id}/reply`, { method: "POST", body: fd });
    toast("✓ Resposta enviada");
    closeModal();
    loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

async function scheduleReply(id) {
  const when = document.getElementById("scheduleAt").value;
  if (!when) return toast("Escolha data/hora para agendar", true);
  const fd = buildReplyForm(id);
  fd.append("scheduled_for", when);
  try {
    await api(`/api/tickets/${id}/schedule`, { method: "POST", body: fd });
    toast("✓ Resposta agendada");
    closeModal();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

/* --------------------------------------------------------------- Anexos */
async function downloadAttachment(id) {
  try {
    const r = await postJSON(`/api/attachments/${id}/download`, {});
    toast("✓ Anexo salvo: " + r.path);
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

/* -------------------------------------------------- Inicialização + refresh */
document.addEventListener("DOMContentLoaded", () => {
  loadTickets();
  // Atualização automática a cada 2 minutos (alinhado ao scheduler).
  setInterval(loadTickets, 120000);
});
