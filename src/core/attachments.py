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
from typing import Any, Optional

from src import config
from src.core.email_service import EmailService
from src.data import db
from src.user_config import UserConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

# Extensões consideradas "arquivos de verdade" na guia de Anexos
# (documentos, imagens, mídia, planilhas...). Assinaturas/inline ficam de fora.
REAL_FILE_EXTS = {
    "pdf", "doc", "docx", "odt", "rtf", "txt", "csv", "xls", "xlsx", "ods",
    "ppt", "pptx", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "heic",
    "zip", "rar", "7z", "mp3", "wav", "ogg", "mp4", "mov", "avi", "mkv", "xml",
}

# Anexos técnicos que não interessam ao usuário (assinaturas, formatos da MS).
_IGNORED_NAMES = {"winmail.dat", "smime.p7s", "smime.p7m", "signature.asc"}


def is_real_file(filename: Optional[str], content_type: Optional[str] = None) -> bool:
    """
    Indica se um anexo é um arquivo "de verdade" para exibir na guia de Anexos.

    Filtra assinaturas digitais, partes inline e formatos sem extensão útil.
    """
    if not filename:
        return False
    name = filename.strip().lower()
    if name in _IGNORED_NAMES:
        return False
    _, dot, ext = name.rpartition(".")
    return bool(dot) and ext in REAL_FILE_EXTS


def _attachments_root() -> str:
    """Retorna o diretório raiz de anexos (criando-o se necessário)."""
    root = config.get("ATTACHMENTS_DIR", "data/attachments")
    os.makedirs(root, exist_ok=True)
    return root


def sanitize(name: str) -> str:
    """Normaliza um nome de arquivo/pasta para uso seguro no sistema de arquivos."""
    name = (name or "arquivo").strip().replace(" ", "_")
    return _SAFE_NAME.sub("_", name) or "arquivo"


def download_attachment(attachment_id: int, cfg: Any = None) -> Optional[str]:
    """
    Baixa um anexo do servidor de e-mail do cliente e o grava de forma organizada.

    Args:
        attachment_id: ID do anexo registrado no banco.
        cfg: Provedor de configuração (``UserConfig``) do cliente dono do anexo.
             Se ``None``, é resolvido a partir do ``user_id`` do ticket.

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

    if cfg is None and ticket.user_id is not None:
        cfg = UserConfig(ticket.user_id)
    payload = EmailService(cfg).download_attachment(ticket.uid, attachment.filename)
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
