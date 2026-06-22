"""
Notificações externas — resumo de e-mails urgentes via WhatsApp.

Esta camada já deixa o fluxo pronto para o envio futuro do resumo dos e-mails
urgentes ao WhatsApp do responsável. A integração com um provedor real
(ex.: Twilio, Meta Cloud API) pode ser plugada em :meth:`WhatsAppNotifier._send`
sem alterar o restante do sistema.

Enquanto desabilitado (``WHATSAPP_ENABLED=false``), o resumo é apenas registrado
em log, permitindo testar todo o fluxo sem credenciais externas.
"""
from typing import List

from src import config
from src.core.ai_engine import AIService
from src.data import db
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppNotifier:
    """
    Notificador de resumos urgentes via WhatsApp.

    Attributes:
        enabled: Se a integração está ativa nas configurações.
        to_number: Número de destino (formato internacional).
    """

    def __init__(self) -> None:
        self.enabled = config.get_bool("WHATSAPP_ENABLED", False)
        self.to_number = config.get("WHATSAPP_TO", "")

    def send_urgent_summary(self) -> bool:
        """
        Gera e envia o resumo de tickets urgentes em aberto.

        Returns:
            ``True`` se um resumo foi gerado/enviado; ``False`` se não havia
            tickets urgentes ou a integração está desabilitada.
        """
        urgent = db.get_urgent_tickets(limit=10)
        if not urgent:
            logger.debug("Sem tickets urgentes para resumo")
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
            logger.info(f"[WhatsApp DESABILITADO] Resumo urgente:\n{message}")
            return False

        # TODO: integrar provedor real (Twilio / Meta Cloud API) usando
        #       config.get("WHATSAPP_TOKEN") e self.to_number.
        logger.info(f"[WhatsApp] Enviando para {self.to_number}:\n{message}")
        return True
