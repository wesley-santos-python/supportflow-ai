/* Lógica da página de configurações. */

async function saveSettings(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    company_name: form.company_name.value,
    email_user: form.email_user.value,
    email_pass: form.email_pass.value,
    email_provider: form.email_provider.value,
    imap_server: form.imap_server.value,
    smtp_server: form.smtp_server.value,
    smtp_port: form.smtp_port.value,
    ai_api_key: form.ai_api_key.value,
    gemini_model: form.gemini_model.value,
    sync_interval_minutes: form.sync_interval_minutes.value,
    auto_download_attachments: form.auto_download_attachments.checked,
    whatsapp_enabled: form.whatsapp_enabled.checked,
    whatsapp_to: form.whatsapp_to.value,
  };
  try {
    await postJSON("/api/settings", payload);
    toast("✓ Configurações salvas");
    form.email_pass.value = "";
    form.ai_api_key.value = "";
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
  return false;
}
