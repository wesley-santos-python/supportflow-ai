"""
Configuração e funções de acesso ao banco de dados.

Utiliza SQLAlchemy como ORM. SQLite por padrão, mas a ``DATABASE_URL`` pode
apontar para MySQL/PostgreSQL sem alterações no restante do código.

A aplicação é **multi-cliente**: a maioria das funções aceita um ``user_id``
para escopar os dados ao cliente autenticado. Quando ``user_id`` é ``None``,
não há filtro por cliente (uso administrativo/legado/testes).

Domínios:
    - Usuários e autenticação
    - Configurações por usuário (key/value)
    - Tickets (CRUD + filtros)
    - Anexos
    - Lembretes
    - Respostas agendadas
    - Configurações globais (key/value)
    - Métricas/analytics para os gráficos do dashboard
"""
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import case, create_engine, func, text
from sqlalchemy.orm import Session, selectinload, sessionmaker

from src.data.models import (
    AppSetting,
    Attachment,
    Base,
    Reminder,
    ScheduledReply,
    Ticket,
    User,
    UserSetting,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuração do banco de dados.
# Para trocar de banco basta exportar DATABASE_URL, ex.:
#   postgresql://usuario:senha@servidor:5432/nome_banco
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./support_flow.db")

# Provedores como Railway/Heroku expõem a URL como "postgres://", formato que
# o SQLAlchemy 2.0 não aceita — normaliza para "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ordenação por urgência reutilizada em várias consultas.
_URGENCY_ORDER = case(
    (Ticket.urgencia == "Alta", 1),
    (Ticket.urgencia == "Média", 2),
    else_=3,
)

# Tickets resolvidos afundam para o fim da lista (ficam abaixo dos abertos).
_STATUS_ORDER = case(
    (Ticket.status == "Resolvido", 2),
    else_=1,
)


def init_db() -> None:
    """Cria as tabelas (se não existirem) e aplica migrações leves."""
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    logger.debug("Banco de dados inicializado")


def _run_migrations() -> None:
    """
    Migração best-effort: adiciona a coluna ``user_id`` às tabelas de negócio
    em bancos criados antes do suporte multi-cliente. Idempotente e tolerante.
    """
    statements = [
        "ALTER TABLE tickets ADD COLUMN user_id INTEGER",
        "ALTER TABLE tickets ADD COLUMN body_html TEXT",
        "ALTER TABLE reminders ADD COLUMN user_id INTEGER",
        "ALTER TABLE scheduled_replies ADD COLUMN user_id INTEGER",
    ]
    for stmt in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
            logger.info(f"Migração aplicada: {stmt}")
        except Exception:
            # Coluna já existe (caso comum) — ignora silenciosamente.
            pass


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager com commit/rollback automático."""
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
# Usuários / autenticação
# ---------------------------------------------------------------------------
def create_user(name: str, email: str, password_hash: str) -> Optional[int]:
    """Cria um usuário. Retorna o ID ou ``None`` se o e-mail já existir."""
    db = SessionLocal()
    try:
        user = User(name=name, email=email.lower().strip(), password_hash=password_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    except Exception as e:
        logger.warning(f"Não foi possível criar usuário '{email}': {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_user_by_email(email: str) -> Optional[User]:
    """Retorna um usuário pelo e-mail (ou ``None``)."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email.lower().strip()).first()
    finally:
        db.close()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Retorna um usuário pelo ID (ou ``None``)."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def count_users() -> int:
    """Conta o total de usuários cadastrados."""
    db = SessionLocal()
    try:
        return db.query(func.count(User.id)).scalar() or 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Configurações por usuário (key/value)
# ---------------------------------------------------------------------------
def get_user_setting(user_id: int, key: str) -> Optional[str]:
    """Retorna uma configuração do usuário (ou ``None``)."""
    db = SessionLocal()
    try:
        row = (
            db.query(UserSetting)
            .filter(UserSetting.user_id == user_id, UserSetting.key == key)
            .first()
        )
        return row.value if row else None
    finally:
        db.close()


def get_user_settings_dict(user_id: int) -> Dict[str, str]:
    """Retorna todas as configurações do usuário como dicionário."""
    db = SessionLocal()
    try:
        rows = db.query(UserSetting).filter(UserSetting.user_id == user_id).all()
        return {r.key: r.value for r in rows}
    finally:
        db.close()


def set_user_setting(user_id: int, key: str, value: str) -> None:
    """Cria ou atualiza uma configuração do usuário."""
    db = SessionLocal()
    try:
        row = (
            db.query(UserSetting)
            .filter(UserSetting.user_id == user_id, UserSetting.key == key)
            .first()
        )
        if row:
            row.value = value
        else:
            db.add(UserSetting(user_id=user_id, key=key, value=value))
        db.commit()
    except Exception as e:
        logger.error(f"Erro ao salvar configuração '{key}' do usuário {user_id}: {e}")
        db.rollback()
    finally:
        db.close()


def users_with_email_configured() -> List[int]:
    """Retorna os IDs de usuários que já configuraram o e-mail (para o scheduler)."""
    db = SessionLocal()
    try:
        rows = (
            db.query(UserSetting.user_id)
            .filter(UserSetting.key == "EMAIL_USER", UserSetting.value.isnot(None), UserSetting.value != "")
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
def save_ticket(ticket_data: dict) -> Optional[int]:
    """
    Salva um novo ticket, evitando duplicidade por (``user_id``, ``uid``).

    Returns:
        O ``id`` do ticket criado, ou ``None`` em caso de duplicidade/falha.
    """
    db = SessionLocal()
    try:
        existing = (
            db.query(Ticket.id)
            .filter(
                Ticket.uid == ticket_data.get("uid"),
                Ticket.user_id == ticket_data.get("user_id"),
            )
            .first()
        )
        if existing:
            logger.debug(f"Ticket duplicado ignorado: {ticket_data.get('uid')}")
            return None

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
    user_id: Optional[int] = None,
    categoria: Optional[str] = None,
    urgencia: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sender: Optional[str] = None,
) -> List[Ticket]:
    """Consulta tickets do usuário aplicando filtros opcionais."""
    db = SessionLocal()
    try:
        query = db.query(Ticket).options(selectinload(Ticket.attachments))
        if user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        if sender and sender != "Todos":
            query = query.filter(Ticket.sender == sender)
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
        # Abertos antes de resolvidos; dentro de cada grupo, urgência e recência.
        return query.order_by(_STATUS_ORDER, _URGENCY_ORDER, Ticket.created_at.desc()).all()
    finally:
        db.close()


def get_all_tickets(user_id: Optional[int] = None) -> List[Ticket]:
    """Retorna os tickets do usuário (mais recentes primeiro)."""
    db = SessionLocal()
    try:
        query = db.query(Ticket).options(selectinload(Ticket.attachments))
        if user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        return query.order_by(Ticket.created_at.desc()).all()
    finally:
        db.close()


def list_senders(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lista os remetentes (cada e-mail é tratado como um "cliente") com a
    contagem de tickets e quantos estão pendentes, do mais ativo ao menos.
    """
    db = SessionLocal()
    try:
        pendentes = func.sum(
            case((Ticket.status != "Resolvido", 1), else_=0)
        )
        query = db.query(
            Ticket.sender,
            func.count(Ticket.id).label("total"),
            pendentes.label("abertos"),
        )
        if user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        rows = query.group_by(Ticket.sender).order_by(func.count(Ticket.id).desc()).all()

        from src.core.sender_risk import assess_sender

        result: List[Dict[str, Any]] = []
        for sender, total, abertos in rows:
            name = sender or "(desconhecido)"
            risk = assess_sender(name)
            result.append({
                "sender": name,
                "email": risk["email"] or name,
                "total": int(total or 0),
                "abertos": int(abertos or 0),
                "risk": risk["level"],
                "risk_reasons": risk["reasons"],
            })
        return result
    finally:
        db.close()


def get_ticket_by_id(ticket_id: int, user_id: Optional[int] = None) -> Optional[Ticket]:
    """Retorna um ticket pelo ID, garantindo a propriedade quando ``user_id`` é dado."""
    db = SessionLocal()
    try:
        query = db.query(Ticket).options(selectinload(Ticket.attachments)).filter(
            Ticket.id == ticket_id
        )
        if user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        return query.first()
    finally:
        db.close()


def update_ticket_status(ticket_id: int, new_status: str, user_id: Optional[int] = None) -> bool:
    """Atualiza o status de um ticket do usuário."""
    return _update_ticket(ticket_id, user_id, status=new_status)


def update_ticket_suggestion(
    ticket_id: int, resposta_sugerida: str, user_id: Optional[int] = None
) -> bool:
    """Atualiza a resposta sugerida de um ticket (ex.: após reescrita por IA)."""
    return _update_ticket(ticket_id, user_id, resposta_sugerida=resposta_sugerida)


def mark_ticket_responded(ticket_id: int, user_id: Optional[int] = None) -> bool:
    """Marca um ticket como respondido e o move para 'Resolvido'."""
    return _update_ticket(
        ticket_id,
        user_id,
        response_sent=True,
        responded_at=datetime.now(),
        status="Resolvido",
    )


def delete_ticket(ticket_id: int, user_id: Optional[int] = None) -> bool:
    """Remove um ticket (e seus anexos) do usuário."""
    db = SessionLocal()
    try:
        ticket = _ticket_query(db, ticket_id, user_id).first()
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


def _ticket_query(db: Session, ticket_id: int, user_id: Optional[int]):
    """Helper: query de um ticket com escopo de propriedade."""
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    if user_id is not None:
        query = query.filter(Ticket.user_id == user_id)
    return query


def _update_ticket(ticket_id: int, user_id: Optional[int], **fields) -> bool:
    """Helper genérico para atualizar campos de um ticket com escopo."""
    db = SessionLocal()
    try:
        ticket = _ticket_query(db, ticket_id, user_id).first()
        if not ticket:
            logger.warning(f"Ticket {ticket_id} não encontrado para atualização")
            return False
        for key, value in fields.items():
            setattr(ticket, key, value)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar ticket {ticket_id}: {e}")
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


def list_attachments(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lista todos os anexos dos tickets do usuário (com assunto/remetente)."""
    db = SessionLocal()
    try:
        query = db.query(Attachment).join(Ticket, Attachment.ticket_id == Ticket.id)
        if user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        rows = query.order_by(Attachment.created_at.desc()).all()
        result: List[Dict[str, Any]] = []
        for att in rows:
            data = att.to_dict()
            data["ticket_subject"] = att.ticket.subject if att.ticket else None
            data["ticket_sender"] = att.ticket.sender if att.ticket else None
            result.append(data)
        return result
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


def list_reminders(user_id: Optional[int] = None, only_pending: bool = False) -> List[Reminder]:
    """Lista lembretes do usuário ordenados por data de disparo."""
    db = SessionLocal()
    try:
        query = db.query(Reminder)
        if user_id is not None:
            query = query.filter(Reminder.user_id == user_id)
        if only_pending:
            query = query.filter(Reminder.done.is_(False))
        return query.order_by(Reminder.remind_at.asc()).all()
    finally:
        db.close()


def due_reminders(reference: Optional[datetime] = None) -> List[Reminder]:
    """Retorna lembretes vencidos ainda não notificados (todos os usuários)."""
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


def set_reminder_done(reminder_id: int, done: bool = True, user_id: Optional[int] = None) -> bool:
    """Marca um lembrete do usuário como concluído (ou reabre)."""
    db = SessionLocal()
    try:
        reminder = _scoped(db.query(Reminder), Reminder, user_id).filter(
            Reminder.id == reminder_id
        ).first()
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


def delete_reminder(reminder_id: int, user_id: Optional[int] = None) -> bool:
    """Remove um lembrete do usuário."""
    db = SessionLocal()
    try:
        reminder = _scoped(db.query(Reminder), Reminder, user_id).filter(
            Reminder.id == reminder_id
        ).first()
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


def list_scheduled_replies(
    user_id: Optional[int] = None, status: Optional[str] = None
) -> List[ScheduledReply]:
    """Lista respostas agendadas do usuário, opcionalmente filtrando por status."""
    db = SessionLocal()
    try:
        query = db.query(ScheduledReply)
        if user_id is not None:
            query = query.filter(ScheduledReply.user_id == user_id)
        if status:
            query = query.filter(ScheduledReply.status == status)
        return query.order_by(ScheduledReply.scheduled_for.asc()).all()
    finally:
        db.close()


def due_scheduled_replies(
    reference: Optional[datetime] = None, user_id: Optional[int] = None
) -> List[ScheduledReply]:
    """Retorna respostas agendadas pendentes cujo horário já chegou."""
    reference = reference or datetime.now()
    db = SessionLocal()
    try:
        query = db.query(ScheduledReply).filter(
            ScheduledReply.status == ScheduledReply.STATUS_PENDING,
            ScheduledReply.scheduled_for <= reference,
        )
        if user_id is not None:
            query = query.filter(ScheduledReply.user_id == user_id)
        return query.all()
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
# Configurações globais (key/value)
# ---------------------------------------------------------------------------
def get_setting(key: str) -> Optional[str]:
    """Retorna o valor de uma configuração global ou ``None``."""
    db = SessionLocal()
    try:
        setting = db.query(AppSetting).filter(AppSetting.key == key).first()
        return setting.value if setting else None
    finally:
        db.close()


def set_setting(key: str, value: str) -> None:
    """Cria ou atualiza uma configuração global key/value."""
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
def analytics_summary(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Agrega métricas dos tickets do usuário para o painel de análise."""
    db = SessionLocal()
    try:
        base = db.query(Ticket)
        if user_id is not None:
            base = base.filter(Ticket.user_id == user_id)

        total = base.with_entities(func.count(Ticket.id)).scalar() or 0
        by_category = _count_by(db, Ticket.categoria, user_id)
        by_urgency = _count_by(db, Ticket.urgencia, user_id)
        by_status = _count_by(db, Ticket.status, user_id)

        # Série temporal por dia (compatível com SQLite e demais bancos).
        day_expr = (
            func.strftime("%Y-%m-%d", Ticket.created_at)
            if DATABASE_URL.startswith("sqlite")
            else func.date(Ticket.created_at)
        )
        day_query = db.query(day_expr.label("dia"), func.count(Ticket.id))
        if user_id is not None:
            day_query = day_query.filter(Ticket.user_id == user_id)
        by_day_rows = day_query.group_by("dia").order_by("dia").all()
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


def get_urgent_tickets(user_id: Optional[int] = None, limit: int = 10) -> List[Ticket]:
    """Retorna tickets urgentes não resolvidos do usuário (para resumo/WhatsApp)."""
    db = SessionLocal()
    try:
        query = (
            db.query(Ticket)
            .options(selectinload(Ticket.attachments))
            .filter(Ticket.urgencia == "Alta", Ticket.status != "Resolvido")
        )
        if user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        return query.order_by(Ticket.created_at.desc()).limit(limit).all()
    finally:
        db.close()


def _count_by(db: Session, column, user_id: Optional[int]) -> Dict[str, int]:
    """Helper: conta tickets agrupados por uma coluna, com escopo opcional."""
    query = db.query(column, func.count(Ticket.id))
    if user_id is not None:
        query = query.filter(Ticket.user_id == user_id)
    rows = query.group_by(column).all()
    return {(label or "Outros"): count for label, count in rows}


def _scoped(query, model, user_id: Optional[int]):
    """Aplica filtro de propriedade por ``user_id`` quando informado."""
    if user_id is not None:
        return query.filter(model.user_id == user_id)
    return query
