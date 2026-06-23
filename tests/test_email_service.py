"""
Testes para o serviço de e-mail.
"""
import json
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
            
            # Deve lançar exceção customizada com mensagem amigável + erro bruto em details
            with pytest.raises(EmailConnectionError) as exc_info:
                service.fetch_unread_emails()

            assert exc_info.value.message  # mensagem amigável ao usuário
            assert "Connection failed" in (exc_info.value.details or "")

    def test_send_reply_sanitizes_newline_subject(self, mock_env):
        """Assunto com quebra de linha (ex.: notificação do GitHub) não deve
        quebrar o envio com 'Header values may not contain linefeed...'."""
        with patch('src.core.email_service.smtplib.SMTP') as mock_smtp:
            server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            from src.core.email_service import EmailService
            service = EmailService()
            ok = service.send_reply(
                "cliente@empresa.com",
                "Re: Run failed: Tests - main\n (07b97b3)",
                "Olá, segue a resposta.",
            )

            assert ok is True
            sent_msg = server.send_message.call_args[0][0]
            assert "\n" not in sent_msg["Subject"]
            assert "\r" not in sent_msg["Subject"]
            # A serialização completa não pode levantar erro de header.
            assert sent_msg.as_bytes()

    def test_send_reply_uses_resend_when_key_set(self, mock_env):
        """Com RESEND_API_KEY configurada, o envio vai pela API do Resend
        (HTTP), com Reply-To = e-mail do cliente, sem tocar no SMTP."""
        env = {
            'EMAIL_USER': 'cliente-suporte@gmail.com',
            'EMAIL_PASS': 'app_pass',
            'RESEND_API_KEY': 're_test_123',
            'RESEND_FROM': 'Suporte <atendimento@floatech.app>',
        }
        with patch.dict('os.environ', env), \
                patch('src.core.email_service.smtplib.SMTP') as mock_smtp, \
                patch('src.core.email_service.urllib.request.urlopen') as mock_open:
            resp = MagicMock()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = b'{"id": "abc"}'
            mock_open.return_value = resp

            from src.core.email_service import EmailService
            service = EmailService()
            ok = service.send_reply("final@empresa.com", "Re: Olá", "Resposta.")

            assert ok is True
            mock_smtp.assert_not_called()  # não usou SMTP
            sent_request = mock_open.call_args[0][0]
            assert sent_request.full_url == "https://api.resend.com/emails"
            assert sent_request.headers["Authorization"] == "Bearer re_test_123"
            payload = json.loads(sent_request.data.decode("utf-8"))
            assert payload["from"] == "Suporte <atendimento@floatech.app>"
            assert payload["to"] == ["final@empresa.com"]
            assert payload["reply_to"] == "cliente-suporte@gmail.com"

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
            mock_mailbox_instance.flag.assert_called_once_with("123", '\\Seen', True)
