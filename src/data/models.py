"""
Modelos ORM do SupportFlow AI.

Define a estrutura das tabelas do banco de dados usando SQLAlchemy.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Ticket(Base):
    """
    Modelo ORM para tickets de suporte.
    
    Representa um e-mail de suporte processado pela IA,
    incluindo classificação de urgência e resposta sugerida.
    
    Attributes:
        id: Chave primária auto-incremento.
        uid: ID único do e-mail (IMAP UID).
        sender: Endereço de e-mail do remetente.
        subject: Assunto do e-mail.
        body: Corpo completo do e-mail.
        urgencia: Classificação de urgência (Alta/Média/Baixa).
        categoria: Categoria do ticket (Técnico/Financeiro/Logística/Outros).
        resumo: Resumo gerado pela IA.
        resposta_sugerida: Resposta sugerida pela IA.
        status: Status atual do ticket.
        created_at: Data e hora de criação.
    """
    
    __tablename__ = 'tickets'
    
    id: int = Column(Integer, primary_key=True, index=True)
    uid: str = Column(String(255), unique=True, nullable=False, index=True)
    sender: str = Column(String(255), nullable=False)
    subject: str = Column(String(500))
    body: Optional[str] = Column(Text)
    urgencia: str = Column(String(50), default="Média")
    categoria: str = Column(String(100), default="Outros")
    resumo: Optional[str] = Column(Text)
    resposta_sugerida: Optional[str] = Column(Text)
    status: str = Column(String(50), default="Pendente", index=True)
    created_at: datetime = Column(DateTime, default=datetime.now, index=True)
    
    def __repr__(self) -> str:
        """Representação string do ticket."""
        return f"<Ticket(id={self.id}, subject='{self.subject[:30]}...', urgencia='{self.urgencia}')>"
    
    def to_dict(self) -> dict:
        """Converte o ticket para dicionário."""
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
            "created_at": self.created_at.isoformat() if self.created_at else None
        }