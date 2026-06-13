"""
Configuração e funções de acesso ao banco de dados.

Utiliza SQLAlchemy como ORM. O backend é definido por `DATABASE_URL` no .env
(PostgreSQL por padrão; SQLite/MySQL também são suportados sem alterar o código).
"""
from contextlib import contextmanager
from typing import Iterator, List, Optional

from sqlalchemy import case, create_engine, func, or_
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import settings
from src.data.models import Base, Ticket
from src.utils.logger import get_logger

logger = get_logger(__name__)

# SQLite precisa de configuração extra para uso multi-thread (FastAPI/threadpool);
# os demais bancos usam pool_pre_ping para conexões resilientes.
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

# Ordenação por prioridade de urgência (Alta > Média > Baixa).
_URGENCY_ORDER = case(
    (Ticket.urgencia == "Alta", 1),
    (Ticket.urgencia == "Média", 2),
    else_=3,
)


def init_db() -> None:
    """Cria todas as tabelas no banco de dados se não existirem."""
    Base.metadata.create_all(bind=engine)
    logger.debug("Banco de dados inicializado")


def get_db() -> Iterator[Session]:
    """Dependência FastAPI: fornece uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão transacional para scripts e tarefas em background."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ticket_exists(db: Session, uid: str) -> bool:
    """Verifica se já existe um ticket com o UID informado."""
    return db.query(Ticket.id).filter(Ticket.uid == uid).first() is not None


def create_ticket(db: Session, data: dict) -> Optional[Ticket]:
    """
    Cria um novo ticket. Ignora UIDs duplicados.

    Returns:
        O ticket criado, ou None em caso de duplicidade/erro.
    """
    if ticket_exists(db, data.get("uid", "")):
        logger.debug(f"Ticket duplicado ignorado: {data.get('uid')}")
        return None
    try:
        ticket = Ticket(**data)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        logger.debug(f"Ticket salvo: {ticket.uid}")
        return ticket
    except Exception as e:
        logger.error(f"Erro ao salvar ticket: {e}")
        db.rollback()
        return None


def list_tickets(
    db: Session,
    *,
    search: str = "",
    categoria: str = "Todos",
    urgencia: str = "Todos",
    status: str = "Todos",
    limit: int = 50,
    offset: int = 0,
) -> List[Ticket]:
    """Lista tickets com busca, filtros e paginação, ordenados por urgência e data."""
    query = db.query(Ticket)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Ticket.subject.ilike(like),
                Ticket.sender.ilike(like),
                Ticket.resumo.ilike(like),
            )
        )
    if categoria and categoria != "Todos":
        query = query.filter(Ticket.categoria == categoria)
    if urgencia and urgencia != "Todos":
        query = query.filter(Ticket.urgencia == urgencia)
    if status and status != "Todos":
        query = query.filter(Ticket.status == status)

    return (
        query.order_by(_URGENCY_ORDER, Ticket.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def get_ticket(db: Session, ticket_id: int) -> Optional[Ticket]:
    """Retorna um ticket pelo ID, ou None."""
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()


def set_status(db: Session, ticket_id: int, new_status: str) -> bool:
    """Atualiza o status de um ticket."""
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        logger.warning(f"Ticket {ticket_id} não encontrado")
        return False
    ticket.status = new_status
    db.commit()
    logger.info(f"Ticket {ticket_id} atualizado para: {new_status}")
    return True


def delete_ticket(db: Session, ticket_id: int) -> bool:
    """Remove um ticket."""
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        return False
    db.delete(ticket)
    db.commit()
    logger.info(f"Ticket {ticket_id} removido")
    return True


def get_stats(db: Session) -> dict:
    """Retorna métricas agregadas para o painel de KPIs."""
    total = db.query(func.count(Ticket.id)).scalar() or 0

    def _group(column) -> dict:
        rows = db.query(column, func.count(Ticket.id)).group_by(column).all()
        return {key: count for key, count in rows}

    by_urgencia = _group(Ticket.urgencia)
    by_status = _group(Ticket.status)

    return {
        "total": total,
        "alta": by_urgencia.get("Alta", 0),
        "media": by_urgencia.get("Média", 0),
        "baixa": by_urgencia.get("Baixa", 0),
        "pendente": by_status.get("Pendente", 0),
        "em_andamento": by_status.get("Em Andamento", 0),
        "resolvido": by_status.get("Resolvido", 0),
    }
