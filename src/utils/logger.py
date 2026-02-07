"""
Configuração centralizada de logging do SupportFlow AI.

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
        name: Nome do módulo (geralmente __name__)
        level: Nível de log opcional (default: INFO)
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        logger.addHandler(handler)
    
    logger.setLevel(level or logging.INFO)
    return logger


# Logger global para uso rápido
default_logger = get_logger('supportflow')
