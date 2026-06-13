"""
Modelos ORM do SupportFlow AI.

Define a estrutura das tabelas do banco de dados usando SQLAlchemy.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Vocabulário padronizado (usado pela IA, filtros e validação da UI).
URGENCIAS = ("Alta", "Média", "Baixa")
CATEGORIAS = ("Técnico", "Financeiro", "Logística", "Outros")
STATUSES = ("Pendente", "Em Andamento", "Resolvido")


class Ticket(Base):
    """
    Modelo ORM para tickets de suporte.

    Representa um e-mail de suporte processado pela IA, incluindo
    classificação de urgência, categoria e resposta sugerida.
    """

    __tablename__ = "tickets"

    id: int = Column(Integer, primary_key=True, index=True)
    uid: str = Column(String(255), unique=True, nullable=False, index=True)
    sender: str = Column(String(255), nullable=False)
    subject: str = Column(String(500))
    body: Optional[str] = Column(Text)
    urgencia: str = Column(String(50), default="Média", index=True)
    categoria: str = Column(String(100), default="Outros", index=True)
    resumo: Optional[str] = Column(Text)
    resposta_sugerida: Optional[str] = Column(Text)
    status: str = Column(String(50), default="Pendente", index=True)
    created_at: datetime = Column(DateTime, default=datetime.now, index=True)
    updated_at: datetime = Column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self) -> str:
        """Representação string do ticket."""
        subj = (self.subject or "")[:30]
        return f"<Ticket(id={self.id}, subject='{subj}...', urgencia='{self.urgencia}')>"

    def to_dict(self) -> dict:
        """Converte o ticket para dicionário (usado na API JSON e exportação)."""
        return {
            "id": self.id,
            "uid": self.uid,
            "sender": self.sender,
            "subject": self.subject,
            "body": self.body,
            "urgencia": self.urgencia,
            "categoria": self.categoria,
            "resumo": self.resumo,
            "resposta_sugerida": self.resposta_sugerida,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
