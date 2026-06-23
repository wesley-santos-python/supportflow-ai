"""
Geração de relatórios do SupportFlow AI.

Formatos suportados:
    - JSON: exportação completa dos tickets
    - CSV: planilha simples para análise externa
    - HTML: relatório imprimível (o usuário pode imprimir/salvar em PDF pelo
      próprio navegador, via "Imprimir" do sistema)

Os arquivos são gravados em ``REPORTS_DIR``.
"""
import csv
import io
import json
import os
from datetime import datetime
from typing import List

from src import config
from src.data import db
from src.data.models import Ticket
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cabeçalhos usados no CSV e no relatório HTML.
_FIELDS = [
    "id",
    "created_at",
    "sender",
    "subject",
    "categoria",
    "urgencia",
    "status",
    "resumo",
]


def _reports_root() -> str:
    """Retorna o diretório de relatórios (criando-o se necessário)."""
    root = config.get("REPORTS_DIR", "data/reports")
    os.makedirs(root, exist_ok=True)
    return root


def _timestamp() -> str:
    """Carimbo de data/hora para nomes de arquivo."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def export_json(tickets: List[Ticket]) -> str:
    """Exporta os tickets para um arquivo JSON e retorna o caminho."""
    data = [t.to_dict(include_attachments=True) for t in tickets]
    path = os.path.join(_reports_root(), f"relatorio_{_timestamp()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Relatório JSON gerado: {path} ({len(data)} tickets)")
    return path


def export_csv(tickets: List[Ticket]) -> str:
    """Exporta os tickets para um arquivo CSV e retorna o caminho."""
    path = os.path.join(_reports_root(), f"relatorio_{_timestamp()}.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        for t in tickets:
            writer.writerow(_ticket_row(t))
    logger.info(f"Relatório CSV gerado: {path} ({len(tickets)} tickets)")
    return path


def csv_string(tickets: List[Ticket]) -> str:
    """Retorna o CSV como string (para download direto via HTTP)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_FIELDS)
    writer.writeheader()
    for t in tickets:
        writer.writerow(_ticket_row(t))
    return buffer.getvalue()


def _ticket_row(ticket: Ticket) -> dict:
    """Converte um ticket em uma linha de relatório (campos selecionados)."""
    row = ticket.to_dict()
    return {field: row.get(field, "") for field in _FIELDS}


def report_context(user_id=None) -> dict:
    """
    Monta o contexto de dados para o relatório HTML imprimível do cliente.

    Args:
        user_id: Cliente dono do relatório (escopa os dados).

    Returns:
        Dicionário com métricas agregadas e a lista de tickets.
    """
    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "summary": db.analytics_summary(user_id),
        "tickets": db.get_all_tickets(user_id),
        "company": config.get("COMPANY_NAME", "Floatech"),
    }
