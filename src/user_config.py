"""
Configuração por cliente (multi-tenant).

Cada cliente tem sua própria conexão de e-mail e preferências, guardadas na
tabela ``user_settings``. Esta classe expõe a mesma interface do módulo
:mod:`src.config` (``get`` / ``get_int`` / ``get_bool``), permitindo que
serviços como :class:`EmailService` funcionem tanto no modo global quanto
escopado a um usuário.

Segredos (senha de e-mail, token de WhatsApp) são armazenados criptografados e
descriptografados sob demanda ao serem lidos.
"""
from typing import Any, Dict, Optional

from src import config, security
from src.data import db

# Chaves cujo valor é sensível e fica criptografado no banco.
SECRET_USER_KEYS = {"EMAIL_PASS", "WHATSAPP_TOKEN"}

# Chaves que cada cliente pode configurar.
USER_KEYS = [
    "EMAIL_USER",
    "EMAIL_PASS",
    "EMAIL_PROVIDER",
    "IMAP_SERVER",
    "SMTP_SERVER",
    "SMTP_PORT",
    "SYNC_INTERVAL_MINUTES",
    "AUTO_DOWNLOAD_ATTACHMENTS",
    "WHATSAPP_ENABLED",
    "WHATSAPP_TO",
    "WHATSAPP_TOKEN",
]


class UserConfig:
    """
    Acessa as configurações de um cliente específico.

    Attributes:
        user_id: ID do cliente dono das configurações.
    """

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self._cache: Dict[str, str] = db.get_user_settings_dict(user_id)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Resolve uma configuração: usuário -> padrão global -> default."""
        value = self._cache.get(key)
        if value in (None, ""):
            return default if default is not None else config.DEFAULTS.get(key)
        if key in SECRET_USER_KEYS:
            return security.decrypt(value)
        return value

    def get_int(self, key: str, default: int = 0) -> int:
        """Retorna uma configuração como inteiro (com fallback seguro)."""
        try:
            return int(str(self.get(key)))
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Retorna uma configuração como booleano."""
        value = self.get(key)
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "sim"}

    def set(self, key: str, value: str) -> None:
        """Salva uma configuração, criptografando se for sensível."""
        stored = security.encrypt(value) if key in SECRET_USER_KEYS else value
        db.set_user_setting(self.user_id, key, stored)
        self._cache[key] = stored

    def apply_email_provider(self, provider: str) -> None:
        """Aplica os servidores padrão de um provedor de e-mail conhecido."""
        preset = config.EMAIL_PROVIDERS.get((provider or "").lower())
        if not preset:
            return
        self.set("EMAIL_PROVIDER", provider.lower())
        self.set("IMAP_SERVER", preset["imap"])
        self.set("SMTP_SERVER", preset["smtp"])
        self.set("SMTP_PORT", preset["smtp_port"])

    def is_email_configured(self) -> bool:
        """Indica se o cliente já configurou e-mail e senha."""
        return bool(self.get("EMAIL_USER")) and bool(self.get("EMAIL_PASS"))

    def public_settings(self) -> Dict[str, Any]:
        """Configurações para a UI, mascarando segredos."""
        data: Dict[str, Any] = {}
        for key in USER_KEYS:
            if key in SECRET_USER_KEYS:
                data[f"{key}_set"] = bool(self.get(key))
            else:
                data[key] = self.get(key)
        return data
