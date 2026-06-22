"""
Modelos ORM do SupportFlow AI.

Define a estrutura das tabelas do banco de dados usando SQLAlchemy.

Tabelas:
    - tickets: e-mails de suporte processados pela IA
    - attachments: anexos vinculados a um ticket
    - reminders: lembretes/follow-ups criados pelo operador
    - scheduled_replies: respostas agendadas para envio futuro
    - app_settings: configurações da aplicação (key/value)
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Ticket(Base):
    """
    Modelo ORM para tickets de suporte.

    Representa um e-mail de suporte processado pela IA, incluindo
    classificação de urgência, categoria e resposta sugerida.

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
        status: Status atual do ticket (Pendente/Em Andamento/Resolvido).
        response_sent: Indica se já foi respondido pelo sistema.
        responded_at: Data/hora em que a resposta foi enviada.
        created_at: Data e hora de criação.
        attachments: Anexos relacionados (relacionamento ORM).
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
    response_sent: bool = Column(Boolean, default=False)
    responded_at: Optional[datetime] = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.now, index=True)

    attachments = relationship(
        "Attachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Representação string do ticket."""
        subj = (self.subject or "")[:30]
        return f"<Ticket(id={self.id}, subject='{subj}...', urgencia='{self.urgencia}')>"

    def to_dict(self, include_attachments: bool = False) -> dict:
        """Converte o ticket para dicionário serializável."""
        data = {
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
            "response_sent": self.response_sent,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "has_attachments": bool(self.attachments),
        }
        if include_attachments:
            data["attachments"] = [a.to_dict() for a in self.attachments]
        return data


class Attachment(Base):
    """
    Anexo de um e-mail/ticket.

    Os metadados ficam sempre registrados; o arquivo só é baixado para o
    disco quando o operador (ou a configuração de download automático)
    solicita, mantendo a pasta organizada por ticket.

    Attributes:
        id: Chave primária.
        ticket_id: FK para o ticket.
        filename: Nome original do arquivo.
        content_type: MIME type do anexo.
        size: Tamanho em bytes (quando conhecido).
        stored_path: Caminho local após download (None se ainda não baixado).
        downloaded: Indica se o arquivo já foi salvo no disco.
        created_at: Data de registro.
    """

    __tablename__ = "attachments"

    id: int = Column(Integer, primary_key=True, index=True)
    ticket_id: int = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    filename: str = Column(String(500), nullable=False)
    content_type: Optional[str] = Column(String(255))
    size: int = Column(Integer, default=0)
    stored_path: Optional[str] = Column(String(1000))
    downloaded: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime, default=datetime.now)

    ticket = relationship("Ticket", back_populates="attachments")

    def to_dict(self) -> dict:
        """Converte o anexo para dicionário serializável."""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "downloaded": self.downloaded,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Reminder(Base):
    """
    Lembrete/follow-up associado (opcionalmente) a um ticket.

    Attributes:
        id: Chave primária.
        ticket_id: FK opcional para o ticket relacionado.
        title: Título curto do lembrete.
        note: Observação detalhada.
        remind_at: Momento em que o lembrete deve disparar.
        done: Indica se já foi concluído.
        notified: Indica se a notificação já foi disparada pelo scheduler.
        created_at: Data de criação.
    """

    __tablename__ = "reminders"

    id: int = Column(Integer, primary_key=True, index=True)
    ticket_id: Optional[int] = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    title: str = Column(String(255), nullable=False)
    note: Optional[str] = Column(Text)
    remind_at: datetime = Column(DateTime, nullable=False, index=True)
    done: bool = Column(Boolean, default=False)
    notified: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        """Converte o lembrete para dicionário serializável."""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "title": self.title,
            "note": self.note,
            "remind_at": self.remind_at.isoformat() if self.remind_at else None,
            "done": self.done,
            "notified": self.notified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScheduledReply(Base):
    """
    Resposta agendada para envio futuro.

    Permite que o operador escreva (ou ajuste a sugestão da IA) uma resposta
    e a programe para um horário específico. O scheduler envia automaticamente
    quando o horário chega.

    Attributes:
        id: Chave primária.
        ticket_id: FK para o ticket que será respondido.
        to_email: Destinatário.
        subject: Assunto da resposta.
        body: Corpo da resposta.
        attachments_json: Lista (JSON) de caminhos de anexos a enviar.
        scheduled_for: Momento programado para envio.
        status: pendente / enviado / falhou / cancelado.
        created_at: Data de criação.
        sent_at: Data de envio efetivo.
        error: Mensagem de erro em caso de falha.
    """

    __tablename__ = "scheduled_replies"

    STATUS_PENDING = "pendente"
    STATUS_SENT = "enviado"
    STATUS_FAILED = "falhou"
    STATUS_CANCELED = "cancelado"

    id: int = Column(Integer, primary_key=True, index=True)
    ticket_id: int = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    to_email: str = Column(String(255), nullable=False)
    subject: str = Column(String(500))
    body: str = Column(Text, nullable=False)
    attachments_json: Optional[str] = Column(Text)
    scheduled_for: datetime = Column(DateTime, nullable=False, index=True)
    status: str = Column(String(30), default=STATUS_PENDING, index=True)
    created_at: datetime = Column(DateTime, default=datetime.now)
    sent_at: Optional[datetime] = Column(DateTime, nullable=True)
    error: Optional[str] = Column(Text)

    def to_dict(self) -> dict:
        """Converte a resposta agendada para dicionário serializável."""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "to_email": self.to_email,
            "subject": self.subject,
            "body": self.body,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error": self.error,
        }


class AppSetting(Base):
    """
    Configuração da aplicação no formato chave/valor.

    Permite configurar credenciais de e-mail, IA e demais parâmetros pela
    interface web, sem necessidade de editar o arquivo ``.env``.

    Attributes:
        key: Chave única da configuração.
        value: Valor (texto).
        updated_at: Última atualização.
    """

    __tablename__ = "app_settings"

    key: str = Column(String(100), primary_key=True)
    value: Optional[str] = Column(Text)
    updated_at: datetime = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict:
        """Converte a configuração para dicionário serializável."""
        return {"key": self.key, "value": self.value}
