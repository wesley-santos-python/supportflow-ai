"""
Gerenciador de anexos.

Organiza o armazenamento dos anexos baixados em uma estrutura previsível::

    <ATTACHMENTS_DIR>/<ticket_uid>/<nome_do_arquivo>

O download é opcional: por padrão apenas os metadados são registrados, e o
arquivo só é gravado em disco quando o operador solicita (ou quando o download
automático está habilitado nas configurações).
"""
import os
import re
from typing import Optional

from src import config
from src.core.email_service import EmailService
from src.data import db
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _attachments_root() -> str:
    """Retorna o diretório raiz de anexos (criando-o se necessário)."""
    root = config.get("ATTACHMENTS_DIR", "data/attachments")
    os.makedirs(root, exist_ok=True)
    return root


def sanitize(name: str) -> str:
    """Normaliza um nome de arquivo/pasta para uso seguro no sistema de arquivos."""
    name = (name or "arquivo").strip().replace(" ", "_")
    return _SAFE_NAME.sub("_", name) or "arquivo"


def download_attachment(attachment_id: int) -> Optional[str]:
    """
    Baixa um anexo do servidor de e-mail e o grava de forma organizada.

    Args:
        attachment_id: ID do anexo registrado no banco.

    Returns:
        Caminho local do arquivo salvo, ou ``None`` em caso de falha.
    """
    attachment = db.get_attachment(attachment_id)
    if not attachment:
        logger.warning(f"Anexo {attachment_id} não encontrado")
        return None

    if attachment.downloaded and attachment.stored_path and os.path.isfile(attachment.stored_path):
        return attachment.stored_path

    ticket = db.get_ticket_by_id(attachment.ticket_id)
    if not ticket:
        return None

    payload = EmailService().download_attachment(ticket.uid, attachment.filename)
    if payload is None:
        return None

    folder = os.path.join(_attachments_root(), sanitize(ticket.uid))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, sanitize(attachment.filename))

    with open(path, "wb") as f:
        f.write(payload)

    db.mark_attachment_downloaded(attachment_id, path)
    logger.info(f"Anexo salvo em {path}")
    return path
