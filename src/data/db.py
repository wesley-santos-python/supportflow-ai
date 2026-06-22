"""
Configuração e funções de acesso ao banco de dados.

Utiliza SQLAlchemy como ORM. SQLite por padrão, mas a ``DATABASE_URL`` pode
apontar para MySQL/PostgreSQL sem alterações no restante do código.

O módulo expõe funções utilitárias agrupadas por domínio:

    - Tickets (CRUD + filtros)
    - Anexos
    - Lembretes
    - Respostas agendadas
    - Configurações (key/value)
    - Métricas/analytics para os gráficos do dashboard
"""
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import case, create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from src.data.models import (
    AppSetting,
    Attachment,
    Base,
    Reminder,
    ScheduledReply,
    Ticket,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuração do banco de dados.
# Para trocar de banco basta exportar DATABASE_URL, ex.:
#   postgresql://usuario:senha@servidor:5432/nome_banco
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./support_flow.db")
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ordenação por urgência reutilizada em várias consultas.
_URGENCY_ORDER = case(
    (Ticket.urgencia == "Alta", 1),
    (Ticket.urgencia == "Média", 2),
    else_=3,
)


def init_db() -> None:
    """Cria todas as tabelas no banco de dados se não existirem."""
    Base.metadata.create_all(bind=engine)
    logger.debug("Banco de dados inicializado")


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Context manager que fornece uma sessão com commit/rollback automático.

    Uso:
        with session_scope() as db:
            db.add(obj)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
def save_ticket(ticket_data: dict) -> Optional[int]:
    """
    Salva um novo ticket no banco de dados.

    Args:
        ticket_data: Dicionário com os dados do ticket.

    Returns:
        O ``id`` do ticket criado, ou ``None`` em caso de falha/duplicidade.
    """
    db = SessionLocal()
    try:
        new_ticket = Ticket(**ticket_data)
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        logger.debug(f"Ticket salvo: {ticket_data.get('uid')}")
        return new_ticket.id
    except Exception as e:
        logger.error(f"Erro ao salvar ticket: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def query_tickets(
    categoria: Optional[str] = None,
    urgencia: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Ticket]:
    """
    Consulta tickets aplicando filtros opcionais.

    Args:
        categoria: Filtra por categoria (ignora "Todos"/None).
        urgencia: Filtra por urgência.
        status: Filtra por status.
        search: Busca textual em assunto, remetente e resumo.

    Returns:
        Lista de tickets ordenados por urgência e data (mais recentes primeiro).
    """
    db = SessionLocal()
    try:
        query = db.query(Ticket)
        if categoria and categoria != "Todos":
            query = query.filter(Ticket.categoria == categoria)
        if urgencia and urgencia != "Todos":
            query = query.filter(Ticket.urgencia == urgencia)
        if status and status != "Todos":
            query = query.filter(Ticket.status == status)
        if search:
            like = f"%{search}%"
            query = query.filter(
                Ticket.subject.ilike(like)
                | Ticket.sender.ilike(like)
                | Ticket.resumo.ilike(like)
            )
        return query.order_by(_URGENCY_ORDER, Ticket.created_at.desc()).all()
    finally:
        db.close()


def get_all_tickets() -> List[Ticket]:
    """Retorna todos os tickets ordenados do mais recente ao mais antigo."""
    db = SessionLocal()
    try:
        return db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    finally:
        db.close()


def get_ticket_by_id(ticket_id: int) -> Optional[Ticket]:
    """Retorna um ticket específico pelo ID (ou ``None``)."""
    db = SessionLocal()
    try:
        return db.query(Ticket).filter(Ticket.id == ticket_id).first()
    finally:
        db.close()


def update_ticket_status(ticket_id: int, new_status: str) -> bool:
    """Atualiza o status de um ticket. Retorna ``True`` se atualizado."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            ticket.status = new_status
            db.commit()
            logger.info(f"Ticket {ticket_id} atualizado para: {new_status}")
            return True
        logger.warning(f"Ticket {ticket_id} não encontrado")
        return False
    except Exception as e:
        logger.error(f"Erro ao atualizar ticket: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def update_ticket_suggestion(ticket_id: int, resposta_sugerida: str) -> bool:
    """Atualiza a resposta sugerida de um ticket (ex.: após reescrita por IA)."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False
        ticket.resposta_sugerida = resposta_sugerida
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar sugestão: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def mark_ticket_responded(ticket_id: int) -> bool:
    """Marca um ticket como respondido e atualiza o status para 'Resolvido'."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False
        ticket.response_sent = True
        ticket.responded_at = datetime.now()
        ticket.status = "Resolvido"
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao marcar ticket respondido: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def delete_ticket(ticket_id: int) -> bool:
    """Remove um ticket (e seus anexos) do banco de dados."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            db.delete(ticket)
            db.commit()
            logger.info(f"Ticket {ticket_id} removido")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao remover ticket: {e}")
        db.rollback()
        return False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Anexos
# ---------------------------------------------------------------------------
def add_attachment(attachment_data: dict) -> Optional[int]:
    """Registra os metadados de um anexo vinculado a um ticket."""
    db = SessionLocal()
    try:
        attachment = Attachment(**attachment_data)
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment.id
    except Exception as e:
        logger.error(f"Erro ao registrar anexo: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_attachment(attachment_id: int) -> Optional[Attachment]:
    """Retorna um anexo pelo ID."""
    db = SessionLocal()
    try:
        return db.query(Attachment).filter(Attachment.id == attachment_id).first()
    finally:
        db.close()


def mark_attachment_downloaded(attachment_id: int, stored_path: str) -> bool:
    """Marca um anexo como baixado e registra o caminho local."""
    db = SessionLocal()
    try:
        att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
        if not att:
            return False
        att.stored_path = stored_path
        att.downloaded = True
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar anexo: {e}")
        db.rollback()
        return False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Lembretes
# ---------------------------------------------------------------------------
def create_reminder(data: dict) -> Optional[int]:
    """Cria um lembrete. Retorna o ID criado."""
    db = SessionLocal()
    try:
        reminder = Reminder(**data)
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder.id
    except Exception as e:
        logger.error(f"Erro ao criar lembrete: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def list_reminders(only_pending: bool = False) -> List[Reminder]:
    """Lista lembretes ordenados por data de disparo."""
    db = SessionLocal()
    try:
        query = db.query(Reminder)
        if only_pending:
            query = query.filter(Reminder.done.is_(False))
        return query.order_by(Reminder.remind_at.asc()).all()
    finally:
        db.close()


def due_reminders(reference: Optional[datetime] = None) -> List[Reminder]:
    """Retorna lembretes vencidos ainda não notificados."""
    reference = reference or datetime.now()
    db = SessionLocal()
    try:
        return (
            db.query(Reminder)
            .filter(
                Reminder.done.is_(False),
                Reminder.notified.is_(False),
                Reminder.remind_at <= reference,
            )
            .all()
        )
    finally:
        db.close()


def set_reminder_done(reminder_id: int, done: bool = True) -> bool:
    """Marca um lembrete como concluído (ou reabre)."""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            return False
        reminder.done = done
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao concluir lembrete: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def mark_reminder_notified(reminder_id: int) -> None:
    """Marca um lembrete como já notificado pelo scheduler."""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.notified = True
            db.commit()
    except Exception as e:
        logger.error(f"Erro ao marcar lembrete notificado: {e}")
        db.rollback()
    finally:
        db.close()


def delete_reminder(reminder_id: int) -> bool:
    """Remove um lembrete."""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            return False
        db.delete(reminder)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Respostas agendadas
# ---------------------------------------------------------------------------
def create_scheduled_reply(data: dict) -> Optional[int]:
    """Cria uma resposta agendada. Retorna o ID criado."""
    db = SessionLocal()
    try:
        reply = ScheduledReply(**data)
        db.add(reply)
        db.commit()
        db.refresh(reply)
        return reply.id
    except Exception as e:
        logger.error(f"Erro ao agendar resposta: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def list_scheduled_replies(status: Optional[str] = None) -> List[ScheduledReply]:
    """Lista respostas agendadas, opcionalmente filtrando por status."""
    db = SessionLocal()
    try:
        query = db.query(ScheduledReply)
        if status:
            query = query.filter(ScheduledReply.status == status)
        return query.order_by(ScheduledReply.scheduled_for.asc()).all()
    finally:
        db.close()


def due_scheduled_replies(reference: Optional[datetime] = None) -> List[ScheduledReply]:
    """Retorna respostas agendadas pendentes cujo horário já chegou."""
    reference = reference or datetime.now()
    db = SessionLocal()
    try:
        return (
            db.query(ScheduledReply)
            .filter(
                ScheduledReply.status == ScheduledReply.STATUS_PENDING,
                ScheduledReply.scheduled_for <= reference,
            )
            .all()
        )
    finally:
        db.close()


def update_scheduled_reply_status(
    reply_id: int, status: str, error: Optional[str] = None
) -> bool:
    """Atualiza o status de uma resposta agendada (enviado/falhou/cancelado)."""
    db = SessionLocal()
    try:
        reply = db.query(ScheduledReply).filter(ScheduledReply.id == reply_id).first()
        if not reply:
            return False
        reply.status = status
        reply.error = error
        if status == ScheduledReply.STATUS_SENT:
            reply.sent_at = datetime.now()
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar resposta agendada: {e}")
        db.rollback()
        return False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Configurações (key/value)
# ---------------------------------------------------------------------------
def get_setting(key: str) -> Optional[str]:
    """Retorna o valor de uma configuração ou ``None``."""
    db = SessionLocal()
    try:
        setting = db.query(AppSetting).filter(AppSetting.key == key).first()
        return setting.value if setting else None
    finally:
        db.close()


def set_setting(key: str, value: str) -> None:
    """Cria ou atualiza uma configuração key/value."""
    db = SessionLocal()
    try:
        setting = db.query(AppSetting).filter(AppSetting.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(AppSetting(key=key, value=value))
        db.commit()
    except Exception as e:
        logger.error(f"Erro ao salvar configuração '{key}': {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Analytics / métricas para os gráficos
# ---------------------------------------------------------------------------
def analytics_summary() -> Dict[str, Any]:
    """
    Agrega métricas dos tickets para alimentar o painel de análise.

    Returns:
        Dicionário com:
            - total, pendentes, resolvidos, urgentes
            - by_category, by_urgency, by_status (dict label->contagem)
            - by_day (últimos registros agrupados por dia)
    """
    db = SessionLocal()
    try:
        total = db.query(func.count(Ticket.id)).scalar() or 0

        by_category = _count_by(db, Ticket.categoria)
        by_urgency = _count_by(db, Ticket.urgencia)
        by_status = _count_by(db, Ticket.status)

        # Série temporal por dia (compatível com SQLite e demais bancos).
        day_expr = func.strftime("%Y-%m-%d", Ticket.created_at) if DATABASE_URL.startswith(
            "sqlite"
        ) else func.date(Ticket.created_at)
        by_day_rows = (
            db.query(day_expr.label("dia"), func.count(Ticket.id))
            .group_by("dia")
            .order_by("dia")
            .all()
        )
        by_day = {str(row[0]): row[1] for row in by_day_rows if row[0]}

        return {
            "total": total,
            "pendentes": by_status.get("Pendente", 0),
            "em_andamento": by_status.get("Em Andamento", 0),
            "resolvidos": by_status.get("Resolvido", 0),
            "urgentes": by_urgency.get("Alta", 0),
            "by_category": by_category,
            "by_urgency": by_urgency,
            "by_status": by_status,
            "by_day": by_day,
        }
    finally:
        db.close()


def get_urgent_tickets(limit: int = 10) -> List[Ticket]:
    """Retorna tickets urgentes não resolvidos (para resumo/WhatsApp)."""
    db = SessionLocal()
    try:
        return (
            db.query(Ticket)
            .filter(Ticket.urgencia == "Alta", Ticket.status != "Resolvido")
            .order_by(Ticket.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def _count_by(db: Session, column) -> Dict[str, int]:
    """Helper: conta tickets agrupados por uma coluna."""
    rows = db.query(column, func.count(Ticket.id)).group_by(column).all()
    return {(label or "Outros"): count for label, count in rows}
