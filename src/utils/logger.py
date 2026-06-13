"""
Configuração centralizada de logging do SupportFlow AI.

O nível de log é definido pela variável de ambiente LOG_LEVEL (default: INFO).

Uso:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Mensagem de log")
"""
import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Retorna um logger configurado para o módulo especificado.

    Args:
        name: Nome do módulo (geralmente __name__).
        level: Nível de log opcional. Se omitido, usa LOG_LEVEL do ambiente.

    Returns:
        Logger configurado.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    if level is None:
        # Importado aqui para evitar dependência circular na inicialização.
        from src.config import settings
        level = logging.getLevelName(settings.log_level.upper())
        if not isinstance(level, int):
            level = logging.INFO

    logger.setLevel(level)
    return logger
