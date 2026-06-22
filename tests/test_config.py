"""
Testes para o módulo de configuração (resolução env/DB e mascaramento).
"""
from unittest.mock import patch

from src import config


class TestConfig:
    """Testes para src.config."""

    def test_get_falls_back_to_env(self):
        """Sem valor no banco, deve usar a variável de ambiente."""
        with patch("src.config._get_from_db", return_value=None):
            with patch.dict("os.environ", {"COMPANY_NAME": "MinhaEmpresa"}):
                assert config.get("COMPANY_NAME") == "MinhaEmpresa"

    def test_get_uses_default(self):
        """Sem env nem banco, deve usar o valor padrão de DEFAULTS."""
        with patch("src.config._get_from_db", return_value=None):
            with patch.dict("os.environ", {}, clear=True):
                assert config.get("GEMINI_MODEL") == "gemini-3.1-flash-lite"

    def test_db_has_priority_over_env(self):
        """Valor no banco deve ter prioridade sobre o ambiente."""
        with patch("src.config._get_from_db", return_value="DoBanco"):
            with patch.dict("os.environ", {"COMPANY_NAME": "DoAmbiente"}):
                assert config.get("COMPANY_NAME") == "DoBanco"

    def test_get_bool(self):
        """Conversão para booleano deve aceitar variações comuns."""
        with patch("src.config._get_from_db", return_value=None):
            with patch.dict("os.environ", {"WHATSAPP_ENABLED": "true"}):
                assert config.get_bool("WHATSAPP_ENABLED") is True
            with patch.dict("os.environ", {"WHATSAPP_ENABLED": "no"}):
                assert config.get_bool("WHATSAPP_ENABLED") is False

    def test_get_int_with_fallback(self):
        """Valor inválido deve retornar o default inteiro."""
        with patch("src.config._get_from_db", return_value="abc"):
            assert config.get_int("SYNC_INTERVAL_MINUTES", 2) == 2

    def test_public_settings_masks_secrets(self):
        """Configurações públicas não devem expor segredos."""
        with patch("src.config._get_from_db", return_value=None):
            with patch.dict("os.environ", {"AI_API_KEY": "secreta"}):
                data = config.public_settings()
                assert "AI_API_KEY" not in data
                assert data["AI_API_KEY_set"] is True

    def test_apply_email_provider(self):
        """Aplicar provedor conhecido deve preencher os servidores."""
        saved = {}
        with patch("src.config.set_many", side_effect=lambda m: saved.update(m)):
            config.apply_email_provider("outlook")
        assert saved["IMAP_SERVER"] == "outlook.office365.com"
        assert saved["SMTP_SERVER"] == "smtp.office365.com"
