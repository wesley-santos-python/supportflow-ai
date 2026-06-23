/* Lógica do dashboard: filtros, cards, modal de resposta, status e sincronização. */

const STATUSES = ["Pendente", "Em Andamento", "Resolvido"];
let currentFilters = { categoria: "Todos", urgencia: "Todos", status: "Todos", search: "", sender: "" };
let activeTicket = null;

/* Ícone de risco por nível de urgência (cor vem da classe .badge). */
const URGENCY_ICON = { "Alta": "i-alert", "Média": "i-bell", "Baixa": "i-check-circle" };

function urgencyBadge(urgencia) {
  const u = urgencia || "Baixa";
  return `<span class="badge ${u}">${icon(URGENCY_ICON[u] || "i-bell", "ico sm")} ${escapeHtml(u)}</span>`;
}

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
    refreshSummary();
  } catch (e) {
    toast("Erro ao carregar: " + e.message, true);
  }
}

/* Atualiza os KPIs (Total/Urgentes/Pendentes/Resolvidos) sem recarregar a página. */
async function refreshSummary() {
  try {
    const s = await api("/api/analytics");
    setText("kpiTotal", s.total);
    setText("kpiUrgentes", s.urgentes);
    setText("kpiPendentes", s.pendentes);
    setText("kpiResolvidos", s.resolvidos);
  } catch (_) {}
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

/* ---------------------------------------------------------------- Clientes */
async function loadSenders() {
  try {
    const data = await api("/api/senders");
    renderClients(data.senders || []);
  } catch (_) {}
}

function renderClients(senders) {
  const box = document.getElementById("clientsList");
  if (!box) return;
  const items = [{ sender: "", label: "Todos os clientes", total: "" }]
    .concat(senders.map((s) => ({ sender: s.sender, label: s.sender, total: s.total, abertos: s.abertos })));
  box.innerHTML = items.map((s) => `
    <button class="client-item ${currentFilters.sender === s.sender ? "active" : ""}"
            data-sender="${escapeHtml(s.sender)}" title="${escapeHtml(s.label)}">
      <span class="client-name">${escapeHtml(s.label)}</span>
      ${s.total !== "" ? `<span class="client-count ${s.abertos ? "has-open" : ""}">${s.total}</span>` : ""}
    </button>`).join("");
}

function clearClient() {
  currentFilters.sender = "";
  showClientTag();
  document.querySelectorAll("#clientsList .client-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.sender === ""));
  loadTickets();
}

function showClientTag() {
  const tag = document.getElementById("clientFilterTag");
  if (!tag) return;
  tag.hidden = !currentFilters.sender;
  if (currentFilters.sender) {
    setText("clientFilterName", currentFilters.sender);
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
    const resolved = t.status === "Resolvido";
    const card = document.createElement("div");
    card.className = "card urg-" + (t.urgencia || "Baixa") + (resolved ? " resolved" : "");
    card.onclick = () => openTicket(t.id);
    card.innerHTML = `
      ${resolved ? "" : `<button class="btn tiny ok card-quick" title="Marcar como resolvido"
        onclick="quickResolve(${t.id}, event)">${icon("i-check", "ico sm")}</button>`}
      <div class="card-top">
        <span class="card-subject">${escapeHtml(t.subject || "(sem assunto)")}</span>
        ${urgencyBadge(t.urgencia)}
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
    loadSenders();
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

  const seg = STATUSES.map((s) =>
    `<button data-status="${s}" class="${t.status === s ? "on" : ""}" onclick="setStatus(${t.id}, '${s}')">${s}</button>`
  ).join("");

  document.getElementById("modalBody").innerHTML = `
    ${urgencyBadge(t.urgencia)}
    <h2>${escapeHtml(t.subject || "(sem assunto)")}</h2>
    <p class="muted small">De: ${escapeHtml(t.sender)} · ${escapeHtml(t.categoria)}</p>

    <div class="modal-section modal-row" style="justify-content:space-between">
      <div class="seg" id="statusSeg">${seg}</div>
      <button class="btn danger tiny" onclick="deleteTicket(${t.id})">${icon("i-trash", "ico sm")} Excluir</button>
    </div>

    <div class="field">
      <label>Resumo</label>
      <p>${escapeHtml(t.resumo || "—")}</p>
    </div>

    <div class="modal-section">
      <button class="btn ghost tiny" onclick="toggleOriginal()">${icon("i-mail", "ico sm")} Ler e-mail original</button>
      <pre id="originalEmail" class="original-body" hidden>${escapeHtml(t.body || "(sem conteúdo)")}</pre>
    </div>

    <div class="modal-section">
      <div class="modal-row" style="justify-content:space-between">
        <label class="muted small">Resposta (sugestão automática — edite à vontade)</label>
        <button class="btn tiny ghost" onclick="copyResponse()">${icon("i-copy", "ico sm")} Copiar</button>
      </div>
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

/* --------------------------------------------------------------- Status */
async function setStatus(id, status) {
  try {
    await postJSON(`/api/tickets/${id}/status`, { status });
    if (activeTicket) activeTicket.status = status;
    document.querySelectorAll("#statusSeg button").forEach((b) =>
      b.classList.toggle("on", b.dataset.status === status));
    toast(`Status atualizado: ${status}`);
    loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

async function quickResolve(id, ev) {
  ev.stopPropagation();
  try {
    await postJSON(`/api/tickets/${id}/status`, { status: "Resolvido" });
    toast("Ticket marcado como resolvido");
    loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

async function deleteTicket(id) {
  if (!confirm("Excluir este ticket? Esta ação não pode ser desfeita.")) return;
  try {
    await api(`/api/tickets/${id}`, { method: "DELETE" });
    toast("Ticket excluído");
    closeModal();
    loadTickets();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

function copyResponse() {
  const text = document.getElementById("replyBody").value;
  if (!navigator.clipboard) return toast("Cópia não suportada neste navegador", true);
  navigator.clipboard.writeText(text).then(
    () => toast("Resposta copiada"),
    () => toast("Não foi possível copiar", true)
  );
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

/* Mostra/oculta o corpo original do e-mail no modal. */
function toggleOriginal() {
  const el = document.getElementById("originalEmail");
  if (el) el.hidden = !el.hidden;
}

/* -------------------------------------------------- Inicialização + refresh */
document.addEventListener("DOMContentLoaded", () => {
  loadTickets();
  loadSenders();

  // Filtro por cliente (delegação de clique no rail lateral).
  const clients = document.getElementById("clientsList");
  if (clients) {
    clients.addEventListener("click", (e) => {
      const item = e.target.closest(".client-item");
      if (!item) return;
      currentFilters.sender = item.dataset.sender || "";
      document.querySelectorAll("#clientsList .client-item").forEach((el) => el.classList.remove("active"));
      item.classList.add("active");
      showClientTag();
      loadTickets();
    });
  }

  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

  // Atualização automática (tickets, KPIs e clientes) a cada 60s.
  setInterval(() => { loadTickets(); loadSenders(); }, 60000);
});
