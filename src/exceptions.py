"""
Exceções customizadas do SupportFlow AI.

Hierarquia:
    SupportFlowError (base)
    ├── EmailConnectionError
    ├── AIAnalysisError
    └── DatabaseError
"""


class SupportFlowError(Exception):
    """Exceção base do SupportFlow AI."""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class EmailConnectionError(SupportFlowError):
    """Erro de conexão com servidor de e-mail IMAP."""
    pass


class AIAnalysisError(SupportFlowError):
    """Erro na análise com Google Gemini AI."""
    pass


class DatabaseError(SupportFlowError):
    """Erro de operação no banco de dados SQLite."""
    pass
