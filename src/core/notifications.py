"""
Notificações externas — resumo de e-mails urgentes via WhatsApp.

Cada cliente configura seu próprio número de WhatsApp; o resumo é gerado a
partir dos tickets urgentes daquele cliente. A integração com um provedor real
(ex.: Twilio, Meta Cloud API) pode ser plugada em :meth:`WhatsAppNotifier._send`
sem alterar o restante do sistema.

Enquanto desabilitado (``WHATSAPP_ENABLED=false``), o resumo é apenas registrado
em log, permitindo testar todo o fluxo sem credenciais externas.
"""
from src.core.ai_engine import AIService
from src.data import db
from src.user_config import UserConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppNotifier:
    """
    Notificador de resumos urgentes via WhatsApp, escopado a um cliente.

    Args:
        user_id: Cliente dono dos tickets e da configuração de WhatsApp.
    """

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.cfg = UserConfig(user_id)
        self.enabled = self.cfg.get_bool("WHATSAPP_ENABLED", False)
        self.to_number = self.cfg.get("WHATSAPP_TO", "")

    def send_urgent_summary(self) -> bool:
        """
        Gera e envia o resumo de tickets urgentes em aberto do cliente.

        Returns:
            ``True`` se um resumo foi enviado; ``False`` se não havia tickets
            urgentes ou a integração está desabilitada.
        """
        urgent = db.get_urgent_tickets(user_id=self.user_id, limit=10)
        if not urgent:
            return False

        payload = [
            {"sender": t.sender, "subject": t.subject, "resumo": t.resumo}
            for t in urgent
        ]
        summary = AIService().summarize_urgent(payload)
        return self._send(summary)

    def _send(self, message: str) -> bool:
        """
        Despacha a mensagem ao provedor de WhatsApp.

        Ponto de extensão: substituir o bloco abaixo por uma chamada real à API
        do provedor escolhido. Por ora, registra em log quando desabilitado.
        """
        if not self.enabled or not self.to_number:
            logger.info(f"[WhatsApp DESABILITADO] Resumo (user={self.user_id}):\n{message}")
            return False

        # TODO: integrar provedor real (Twilio / Meta Cloud API) usando
        #       self.cfg.get("WHATSAPP_TOKEN") e self.to_number.
        logger.info(f"[WhatsApp] Enviando para {self.to_number}:\n{message}")
        return True
