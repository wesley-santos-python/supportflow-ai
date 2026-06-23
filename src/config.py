"""
Gerenciamento centralizado de configuração do SupportFlow AI.

A configuração é resolvida em camadas, na seguinte ordem de prioridade:

    1. Tabela ``app_settings`` no banco de dados (editável pela interface web)
    2. Variáveis de ambiente / arquivo ``.env``
    3. Valores padrão definidos em :data:`DEFAULTS`

Isso permite que o usuário conecte o e-mail e a IA rapidamente pela tela de
configurações, sem precisar editar arquivos.
"""
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


# Valores padrão da aplicação. Servem de fallback final.
DEFAULTS: Dict[str, str] = {
    "COMPANY_NAME": "Floatech",
    "APP_NAME": "SupportFlow AI",
    # Chave para assinar sessões e derivar a criptografia de segredos.
    # DEVE ser definida via variável de ambiente SECRET_KEY em produção.
    "SECRET_KEY": "dev-insecure-secret-change-me",
    "EMAIL_PROVIDER": "gmail",
    "IMAP_SERVER": "imap.gmail.com",
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": "587",
    "GEMINI_MODEL": "gemini-3.1-flash-lite",
    "SYNC_INTERVAL_MINUTES": "10",
    "AUTO_DOWNLOAD_ATTACHMENTS": "false",
    "ATTACHMENTS_DIR": "data/attachments",
    "REPORTS_DIR": "data/reports",
    "WHATSAPP_ENABLED": "false",
    "WHATSAPP_TO": "",
    # Classificação personalizável por cliente (alimenta a IA).
    "CATEGORIES": "Técnico,Financeiro,Logística,Outros",
    "URGENCY_CRITERIA": "prazo vencendo, sistema parado, multa, cobrança indevida, "
                        "cliente irritado, palavra 'urgente'",
    # Marca / aparência do e-mail enviado.
    "EMAIL_FORMAT": "html",          # "html" (bonito) ou "plain" (texto)
    "EMAIL_TEMPLATE": "moderno",     # moderno | classico | minimalista
    "EMAIL_HEADER": "",              # frase/tagline do cabeçalho (opcional)
    "COMPANY_LOGO_URL": "",
    "COMPANY_EMAIL": "",
    "COMPANY_PHONE": "",
    "COMPANY_SITE": "",
    "COMPANY_ADDRESS": "",
    # Controle interno da primeira sincronização (últimos 7 dias).
    "INITIAL_SYNC_DONE": "false",
}

# Mapa de provedores de e-mail conhecidos -> (IMAP, SMTP, porta SMTP).
EMAIL_PROVIDERS: Dict[str, Dict[str, str]] = {
    "gmail": {"imap": "imap.gmail.com", "smtp": "smtp.gmail.com", "smtp_port": "587"},
    "outlook": {"imap": "outlook.office365.com", "smtp": "smtp.office365.com", "smtp_port": "587"},
}

# Chaves sensíveis que nunca devem ser expostas em respostas da API.
SECRET_KEYS = {"EMAIL_PASS", "AI_API_KEY", "WHATSAPP_TOKEN"}


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Resolve o valor de uma configuração seguindo a ordem de prioridade.

    Args:
        key: Nome da configuração (ex.: ``"AI_API_KEY"``).
        default: Valor a retornar caso nada seja encontrado.

    Returns:
        O valor da configuração ou ``default``.
    """
    db_value = _get_from_db(key)
    if db_value not in (None, ""):
        return db_value

    env_value = os.getenv(key)
    if env_value not in (None, ""):
        return env_value

    if default is not None:
        return default
    return DEFAULTS.get(key)


def get_bool(key: str, default: bool = False) -> bool:
    """Retorna uma configuração como booleano."""
    value = get(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "sim"}


def get_int(key: str, default: int = 0) -> int:
    """Retorna uma configuração como inteiro (com fallback seguro)."""
    value = get(key)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def set_value(key: str, value: str) -> None:
    """Persiste uma configuração no banco de dados."""
    # Import tardio para evitar dependência circular com a camada de dados.
    from src.data.db import set_setting

    set_setting(key, value)


def set_many(values: Dict[str, str]) -> None:
    """Persiste várias configurações de uma vez, ignorando valores vazios."""
    for key, value in values.items():
        if value is None:
            continue
        set_value(key, value)


def apply_email_provider(provider: str) -> None:
    """
    Aplica os servidores padrão de um provedor de e-mail conhecido.

    Args:
        provider: ``"gmail"`` ou ``"outlook"``.
    """
    provider = (provider or "").lower()
    preset = EMAIL_PROVIDERS.get(provider)
    if not preset:
        return
    set_many(
        {
            "EMAIL_PROVIDER": provider,
            "IMAP_SERVER": preset["imap"],
            "SMTP_SERVER": preset["smtp"],
            "SMTP_PORT": preset["smtp_port"],
        }
    )


def public_settings() -> Dict[str, Any]:
    """
    Retorna as configurações para exibição na UI, mascarando segredos.

    Chaves secretas retornam apenas um indicador booleano ``*_set`` informando
    se já existe valor configurado, sem expor o conteúdo.
    """
    keys = [
        "COMPANY_NAME",
        "APP_NAME",
        "EMAIL_USER",
        "EMAIL_PROVIDER",
        "IMAP_SERVER",
        "SMTP_SERVER",
        "SMTP_PORT",
        "GEMINI_MODEL",
        "SYNC_INTERVAL_MINUTES",
        "AUTO_DOWNLOAD_ATTACHMENTS",
        "WHATSAPP_ENABLED",
        "WHATSAPP_TO",
    ]
    data: Dict[str, Any] = {k: get(k) for k in keys}
    for secret in SECRET_KEYS:
        data[f"{secret}_set"] = bool(get(secret))
    return data


def is_email_configured() -> bool:
    """Indica se as credenciais mínimas de e-mail estão presentes."""
    return bool(get("EMAIL_USER")) and bool(get("EMAIL_PASS"))


def is_ai_configured() -> bool:
    """Indica se a chave da IA está configurada."""
    return bool(get("AI_API_KEY"))


def _get_from_db(key: str) -> Optional[str]:
    """Lê uma configuração do banco, tolerando indisponibilidade do mesmo."""
    try:
        from src.data.db import get_setting

        return get_setting(key)
    except Exception as exc:  # pragma: no cover - banco ainda não inicializado
        logger.debug(f"Configuração '{key}' não lida do banco: {exc}")
        return None
