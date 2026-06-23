/* Lógica da página de configurações do cliente. */

async function saveSettings(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    email_user: form.email_user.value,
    email_pass: form.email_pass.value,
    email_provider: form.email_provider.value,
    imap_server: form.imap_server.value,
    smtp_server: form.smtp_server.value,
    smtp_port: form.smtp_port.value,
    auto_download_attachments: form.auto_download_attachments.checked,
    whatsapp_enabled: form.whatsapp_enabled.checked,
    whatsapp_to: form.whatsapp_to.value,
    whatsapp_token: form.whatsapp_token.value,
  };
  try {
    await postJSON("/api/settings", payload);
    toast("✓ Configurações salvas");
    form.email_pass.value = "";
    form.whatsapp_token.value = "";
    // Após salvar, testa a conexão para mostrar de imediato se as credenciais funcionam.
    if (payload.email_user) testEmail();
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
  return false;
}

/** Testa a conexão de e-mail (IMAP) e mostra o motivo claro em caso de falha. */
async function testEmail() {
  toast("Testando conexão de e-mail...");
  try {
    const r = await postJSON("/api/settings/test-email", {});
    toast("✓ " + (r.message || "Conexão bem-sucedida!"));
  } catch (e) {
    toast("Conexão falhou: " + e.message, true);
  }
}
