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
    // Testa a conexão com o que foi digitado, ANTES de limpar o campo de senha.
    if (payload.email_user) await testEmail();
    form.email_pass.value = "";
    form.whatsapp_token.value = "";
  } catch (e) {
    toast("Erro: " + e.message, true);
  }
  return false;
}

/**
 * Testa a conexão de e-mail (IMAP). Envia o que está no formulário; se a senha
 * estiver em branco, o servidor usa a credencial já salva.
 */
async function testEmail() {
  const form = document.getElementById("settingsForm");
  toast("Testando conexão de e-mail...");
  try {
    const r = await postJSON("/api/settings/test-email", {
      email_user: form.email_user.value,
      email_pass: form.email_pass.value,
      imap_server: form.imap_server.value,
    });
    toast("✓ " + (r.message || "Conexão bem-sucedida!"));
  } catch (e) {
    toast("Conexão falhou: " + e.message, true);
  }
}
