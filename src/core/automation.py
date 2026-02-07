"""
Controlador de automação do SupportFlow AI.

Orquestra o fluxo de sincronização: e-mail -> IA -> banco de dados.
"""
from typing import List, Dict

from src.core.email_service import EmailService
from src.core.ai_engine import AIService
from src.data.db import save_ticket, init_db
from src.utils.logger import get_logger
from src.exceptions import EmailConnectionError

logger = get_logger(__name__)


class SupportController:
    """
    Controlador principal que orquestra o fluxo de suporte.
    
    Responsável por:
    - Buscar novos e-mails não lidos
    - Enviar para análise da IA
    - Salvar tickets no banco de dados
    - Marcar e-mails como lidos
    """
    
    def __init__(self) -> None:
        """Inicializa o controlador com os serviços necessários."""
        self.email_api = EmailService()
        self.ai_api = AIService()
        init_db()
        logger.info("SupportController inicializado")

    def run_sync(self) -> int:
        """
        Executa sincronização de e-mails.
        
        Busca e-mails não lidos, analisa com IA e salva no banco.
        
        Returns:
            Número de tickets processados.
        """
        logger.info("Iniciando sincronização de e-mails...")
        
        try:
            new_emails = self.email_api.fetch_unread_emails()
        except EmailConnectionError as e:
            logger.error(f"Falha na conexão: {e.message}")
            return 0
        
        if not new_emails:
            logger.info("Nenhum ticket novo encontrado")
            return 0
        
        processed = 0
        for mail in new_emails:
            if not mail['body']:
                logger.warning(f"E-mail sem corpo ignorado: {mail['subject']}")
                continue
                
            logger.info(f"Analisando ticket: {mail['subject']}")
            
            analysis = self.ai_api.analyze_ticket(mail['body'])
            
            ticket_data = {
                "uid": mail['id'],
                "sender": mail['sender'],
                "subject": mail['subject'],
                "body": mail['body'],
                "urgencia": analysis.get("urgencia", "Média"),
                "categoria": analysis.get("categoria", "Geral"),
                "resumo": analysis.get("resumo", "Sem resumo"),
                "resposta_sugerida": analysis.get("resposta_sugerida", "")
            }
            
            if save_ticket(ticket_data):
                self.email_api.mark_as_read(mail['id'])
                processed += 1
                logger.debug(f"Ticket salvo: {mail['id']}")
            
        logger.info(f"Sincronização concluída: {processed} tickets processados")
        return processed