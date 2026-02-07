"""
Módulo core do SupportFlow AI.

Contém a lógica de negócio principal: integração com IA,
serviço de e-mail e orquestração de automação.
"""
from .ai_engine import AIService
from .automation import SupportController
from .email_service import EmailService

__all__ = ['AIService', 'SupportController', 'EmailService']
