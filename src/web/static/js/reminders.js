/* Lógica da página de lembretes. */

async function createReminder(event) {
  event.preventDefault();
  const form = event.target;
  const body = {
    title: form.title.value.trim(),
    note: form.note.value.trim(),
    remind_at: form.remind_at.value,
  };
  try {
    await postJSON("/api/reminders", body);
    toast("✓ Lembrete criado");
    setTimeout(() => location.reload(), 600);
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
  return false;
}

async function completeReminder(id) {
  try {
    await api(`/api/reminders/${id}/done`, { method: "POST" });
    location.reload();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}

async function deleteReminder(id) {
  if (!confirm("Remover este lembrete?")) return;
  try {
    await api(`/api/reminders/${id}`, { method: "DELETE" });
    location.reload();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
}
