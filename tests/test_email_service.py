"""
Testes para o serviço de e-mail.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.exceptions import EmailConnectionError


class TestEmailService:
    """Testes para a classe EmailService."""
    
    @pytest.fixture
    def mock_env(self):
        """Mock das variáveis de ambiente."""
        with patch.dict('os.environ', {
            'EMAIL_USER': 'test@gmail.com',
            'EMAIL_PASS': 'test_password'
        }):
            yield

    def test_fetch_unread_emails_success(self, mock_env):
        """Testa busca de e-mails não lidos com sucesso."""
        with patch('src.core.email_service.MailBox') as mock_mailbox:
            # Configura mock
            mock_mail = MagicMock()
            mock_mail.uid = "123"
            mock_mail.from_ = "cliente@empresa.com"
            mock_mail.subject = "Preciso de ajuda"
            mock_mail.text = "Não consigo acessar minha conta"
            mock_mail.date = datetime.now()
            
            mock_mailbox_instance = MagicMock()
            mock_mailbox_instance.__enter__ = MagicMock(return_value=mock_mailbox_instance)
            mock_mailbox_instance.__exit__ = MagicMock(return_value=False)
            mock_mailbox_instance.fetch.return_value = [mock_mail]
            mock_mailbox.return_value.login.return_value = mock_mailbox_instance
            
            from src.core.email_service import EmailService
            service = EmailService()
            emails = service.fetch_unread_emails()
            
            assert len(emails) == 1
            assert emails[0]["sender"] == "cliente@empresa.com"
            assert emails[0]["subject"] == "Preciso de ajuda"

    def test_fetch_unread_emails_empty(self, mock_env):
        """Testa retorno vazio quando não há e-mails."""
        with patch('src.core.email_service.MailBox') as mock_mailbox:
            mock_mailbox_instance = MagicMock()
            mock_mailbox_instance.__enter__ = MagicMock(return_value=mock_mailbox_instance)
            mock_mailbox_instance.__exit__ = MagicMock(return_value=False)
            mock_mailbox_instance.fetch.return_value = []
            mock_mailbox.return_value.login.return_value = mock_mailbox_instance
            
            from src.core.email_service import EmailService
            service = EmailService()
            emails = service.fetch_unread_emails()
            
            assert emails == []

    def test_fetch_unread_emails_connection_error(self, mock_env):
        """Testa que erro de conexão lança EmailConnectionError."""
        with patch('src.core.email_service.MailBox') as mock_mailbox:
            mock_mailbox.return_value.login.side_effect = Exception("Connection failed")
            
            from src.core.email_service import EmailService
            service = EmailService()
            
            # Deve lançar exceção customizada
            with pytest.raises(EmailConnectionError) as exc_info:
                service.fetch_unread_emails()
            
            assert "Falha ao conectar" in exc_info.value.message

    def test_mark_as_read(self, mock_env):
        """Testa marcação de e-mail como lido."""
        with patch('src.core.email_service.MailBox') as mock_mailbox:
            mock_mailbox_instance = MagicMock()
            mock_mailbox_instance.__enter__ = MagicMock(return_value=mock_mailbox_instance)
            mock_mailbox_instance.__exit__ = MagicMock(return_value=False)
            mock_mailbox.return_value.login.return_value = mock_mailbox_instance
            
            from src.core.email_service import EmailService
            service = EmailService()
            result = service.mark_as_read("123")

            assert result is True
            mock_mailbox_instance.flag.assert_called_once_with(["123"], '\\Seen', True)

    def test_mark_as_read_bulk(self, mock_env):
        """Testa marcação de vários e-mails em uma única conexão."""
        with patch('src.core.email_service.MailBox') as mock_mailbox:
            mock_mailbox_instance = MagicMock()
            mock_mailbox_instance.__enter__ = MagicMock(return_value=mock_mailbox_instance)
            mock_mailbox_instance.__exit__ = MagicMock(return_value=False)
            mock_mailbox.return_value.login.return_value = mock_mailbox_instance

            from src.core.email_service import EmailService
            service = EmailService()
            result = service.mark_as_read_bulk(["1", "2", "3"])

            assert result is True
            mock_mailbox_instance.flag.assert_called_once_with(["1", "2", "3"], '\\Seen', True)
            mock_mailbox.assert_called_once()  # uma única conexão

    def test_mark_as_read_bulk_empty_noop(self, mock_env):
        """Lista vazia não abre conexão."""
        with patch('src.core.email_service.MailBox') as mock_mailbox:
            from src.core.email_service import EmailService
            service = EmailService()
            assert service.mark_as_read_bulk([]) is True
            mock_mailbox.assert_not_called()
