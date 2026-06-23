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
      <span class="card-sender">${icon("i-mail", "ico sm")} ${escapeHtml(t.sender || "")}</span>
      <span class="card-summary">${escapeHtml(t.resumo || "Análise pendente...")}</span>
      <div class="card-foot">
        <span class="card-cat">${icon("i-folder", "ico sm")} ${escapeHtml(t.categoria || "Outros")}</span>
        <span class="card-time">
          ${t.has_attachments ? `<span class="attach-flag">${icon("i-clip", "ico sm")}</span>` : ""}
          ${icon("i-clock", "ico sm")} ${fmtDate(t.created_at)}
        </span>
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
  const original = btn.innerHTML;
  btn.innerHTML = icon("i-refresh", "ico spin") + " Sincronizando...";
  try {
    const r = await api("/api/sync", { method: "POST" });
    toast(`${r.processed} ticket(s) sincronizado(s)`);
    await loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

function openReport() {
  window.open("/report", "_blank");
}

/* --------------------------------------------------------------------- Modal */
async function openTicket(id) {
  try {
    activeTicket = await api("/api/tickets/" + id);
    renderModal(activeTicket);
    document.getElementById("modal").classList.add("open");
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

function closeModal() {
  document.getElementById("modal").classList.remove("open");
  activeTicket = null;
}

function renderModal(t) {
  const attachments = (t.attachments || []).map((a) => `
    <div class="attach-item">
      <span class="name">${icon("i-clip", "ico sm")} <span>${escapeHtml(a.filename)}</span></span>
      <span class="modal-row">
        <a class="btn tiny ghost" href="/api/attachments/${a.id}/file" target="_blank">${icon("i-print", "ico sm")} Abrir</a>
        <button class="btn tiny" onclick="downloadAttachment(${a.id})">${icon("i-download", "ico sm")} Baixar</button>
      </span>
    </div>`).join("");

  document.getElementById("modalBody").innerHTML = `
    <span class="badge ${t.urgencia}">${escapeHtml(t.urgencia)}</span>
    <h2>${escapeHtml(t.subject || "(sem assunto)")}</h2>
    <p class="muted small">De: ${escapeHtml(t.sender)} · ${escapeHtml(t.categoria)} · ${escapeHtml(t.status)}</p>

    <div class="field">
      <label>Resumo</label>
      <p>${escapeHtml(t.resumo || "—")}</p>
    </div>

    <div class="modal-section">
      <label class="muted small">Resposta (sugestão automática — edite à vontade)</label>
      <textarea id="replyBody" rows="6">${escapeHtml(t.resposta_sugerida || "")}</textarea>
      <div class="modal-row" style="margin-top:10px">
        <input id="rewriteInstruction" style="flex:1" placeholder="Refinar resposta: ex. 'mais formal'" />
        <button class="btn ghost" onclick="rewriteWithAI(${t.id})">${icon("i-ai", "ico sm")} Refinar</button>
      </div>
    </div>

    <div class="modal-section">
      <label class="muted small">Anexar arquivos</label>
      <input type="file" id="replyFiles" multiple style="margin-top:6px" />
      ${attachments ? `<div class="attach-list">${attachments}</div>` : ""}
    </div>

    <div class="modal-section modal-row" style="justify-content:space-between">
      <div class="modal-row">
        <input type="datetime-local" id="scheduleAt" />
        <button class="btn ghost" onclick="scheduleReply(${t.id})">${icon("i-calendar", "ico sm")} Agendar</button>
      </div>
      <button class="btn primary" onclick="sendReply(${t.id})">${icon("i-send", "ico sm")} Enviar agora</button>
    </div>`;
}

/* --------------------------------------------------------------- Ações IA */
async function rewriteWithAI(id) {
  const instruction = document.getElementById("rewriteInstruction").value.trim() || "melhore o tom";
  const text = document.getElementById("replyBody").value;
  try {
    const r = await postJSON(`/api/tickets/${id}/rewrite`, { text, instruction });
    document.getElementById("replyBody").value = r.text;
    toast("Resposta atualizada");
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

/* ------------------------------------------------------ Enviar / Agendar */
function buildReplyForm() {
  const fd = new FormData();
  fd.append("body", document.getElementById("replyBody").value);
  const files = document.getElementById("replyFiles").files;
  for (const f of files) fd.append("files", f);
  return fd;
}

async function sendReply(id) {
  const fd = buildReplyForm();
  try {
    await api(`/api/tickets/${id}/reply`, { method: "POST", body: fd });
    toast("Resposta enviada");
    closeModal();
    loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

async function scheduleReply(id) {
  const when = document.getElementById("scheduleAt").value;
  if (!when) return toast("Escolha data/hora para agendar", true);
  const fd = buildReplyForm();
  fd.append("scheduled_for", when);
  try {
    await api(`/api/tickets/${id}/schedule`, { method: "POST", body: fd });
    toast("Resposta agendada");
    closeModal();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

/* --------------------------------------------------------------- Anexos */
async function downloadAttachment(id) {
  try {
    const r = await postJSON(`/api/attachments/${id}/download`, {});
    toast("Anexo salvo: " + r.path);
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

/* -------------------------------------------------- Inicialização + refresh */
document.addEventListener("DOMContentLoaded", () => {
  loadTickets();
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  setInterval(loadTickets, 120000);
});
