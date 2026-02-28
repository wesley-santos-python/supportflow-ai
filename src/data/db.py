"""
Configuração e funções de acesso ao banco de dados.

Utiliza SQLAlchemy como ORM com SQLite como backend.
"""
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.models import Base, Ticket
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuração do banco de dados
DATABASE_URL = "sqlite:///./support_flow.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Cria todas as tabelas no banco de dados se não existirem."""
    Base.metadata.create_all(bind=engine)
    logger.debug("Banco de dados inicializado")



def save_ticket(ticket_data: dict) -> bool:
    """
    Salva um novo ticket no banco de dados.
    
    Args:
        ticket_data: Dicionário com os dados do ticket.
    
    Returns:
        True se salvo com sucesso, False caso contrário.
    """
    db = SessionLocal()
    try:
        new_ticket = Ticket(**ticket_data)
        db.add(new_ticket)
        db.commit()
        logger.debug(f"Ticket salvo: {ticket_data.get('uid')}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar ticket: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_all_tickets() -> List[Ticket]:
    """
    Retorna todos os tickets ordenados por data de criação.
    
    Returns:
        Lista de objetos Ticket ordenados do mais recente ao mais antigo.
    """
    db = SessionLocal()
    try:
        return db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    finally:
        db.close()


def get_ticket_by_id(ticket_id: int) -> Optional[Ticket]:
    """
    Retorna um ticket específico pelo ID.
    
    Args:
        ticket_id: ID do ticket a buscar.
    
    Returns:
        Objeto Ticket ou None se não encontrado.
    """
    db = SessionLocal()
    try:
        return db.query(Ticket).filter(Ticket.id == ticket_id).first()
    finally:
        db.close()


def update_ticket_status(ticket_id: int, new_status: str) -> bool:
    """
    Atualiza o status de um ticket.
    
    Args:
        ticket_id: ID do ticket a atualizar.
        new_status: Novo status (ex: "Pendente", "Em Andamento", "Resolvido").
    
    Returns:
        True se atualizado com sucesso, False caso contrário.
    """
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


def delete_ticket(ticket_id: int) -> bool:
    """
    Remove um ticket do banco de dados.
    
    Args:
        ticket_id: ID do ticket a remover.
    
    Returns:
        True se removido com sucesso, False caso contrário.
    """
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
