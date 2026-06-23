/* Lógica da página de configurações do cliente. */

function val(form, name) {
  const el = form.elements[name];
  return el ? el.value : "";
}

/* Campos de classificação + marca (reusados em salvar e pré-visualizar). */
function brandingFields(form) {
  return {
    categories: val(form, "categories"),
    urgency_criteria: val(form, "urgency_criteria"),
    email_format: val(form, "email_format"),
    email_template: val(form, "email_template"),
    email_header: val(form, "email_header"),
    company_name: val(form, "company_name"),
    company_logo_url: val(form, "company_logo_url"),
    company_email: val(form, "company_email"),
    company_phone: val(form, "company_phone"),
    company_site: val(form, "company_site"),
    company_address: val(form, "company_address"),
  };
}

async function saveSettings(event) {
  event.preventDefault();
  const form = event.target;
  const payload = Object.assign({
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
  }, brandingFields(form));

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

/** Pré-visualiza como o e-mail será enviado, usando os valores atuais do formulário. */
async function previewEmail() {
  const form = document.getElementById("settingsForm");
  const wrap = document.getElementById("emailPreviewWrap");
  const frame = document.getElementById("emailPreview");
  const text = document.getElementById("emailPreviewText");
  try {
    const r = await postJSON("/api/email/preview", brandingFields(form));
    wrap.hidden = false;
    if (r.format === "plain") {
      frame.hidden = true;
      text.hidden = false;
      text.textContent = r.text || "";
    } else {
      text.hidden = true;
      frame.hidden = false;
      frame.srcdoc = r.html || "";
    }
  } catch (e) {
    toast("Erro na prévia: " + e.message, true);
  }
}
