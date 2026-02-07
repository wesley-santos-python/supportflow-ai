"""
Testes para o módulo de banco de dados.
"""
import pytest
import os
from datetime import datetime


# Usa banco de dados de teste em memória
TEST_DB_URL = "sqlite:///:memory:"


class TestDatabase:
    """Testes para funções do banco de dados."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Configura banco de teste antes de cada teste."""
        # Sobrescreve a URL do banco para usar memória
        import src.data.db as db_module
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.data.models import Base
        
        # Cria engine de teste
        test_engine = create_engine(TEST_DB_URL)
        db_module.engine = test_engine
        db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        
        # Cria tabelas
        Base.metadata.create_all(bind=test_engine)
        
        yield
        
        # Limpa após teste
        Base.metadata.drop_all(bind=test_engine)

    def test_save_ticket_success(self):
        """Testa salvamento de ticket com sucesso."""
        from src.data.db import save_ticket, get_all_tickets
        
        ticket_data = {
            "uid": "test_uid_001",
            "sender": "cliente@email.com",
            "subject": "Problema com pedido",
            "body": "Meu pedido não chegou",
            "urgencia": "Alta",
            "categoria": "Logística",
            "resumo": "Cliente aguardando pedido",
            "resposta_sugerida": "Vamos verificar seu pedido."
        }
        
        save_ticket(ticket_data)
        tickets = get_all_tickets()
        
        assert len(tickets) == 1
        assert tickets[0].sender == "cliente@email.com"
        assert tickets[0].urgencia == "Alta"

    def test_save_duplicate_uid_fails(self):
        """Testa que UID duplicado não é salvo."""
        from src.data.db import save_ticket, get_all_tickets
        
        ticket_data = {
            "uid": "duplicate_uid",
            "sender": "test@test.com",
            "subject": "Teste",
            "body": "Corpo"
        }
        
        save_ticket(ticket_data)
        save_ticket(ticket_data)  # Tenta salvar duplicado
        
        tickets = get_all_tickets()
        assert len(tickets) == 1  # Só um deve existir

    def test_get_ticket_by_id(self):
        """Testa busca de ticket por ID."""
        from src.data.db import save_ticket, get_all_tickets, get_ticket_by_id
        
        ticket_data = {
            "uid": "test_uid_002",
            "sender": "outro@email.com",
            "subject": "Outro problema",
            "body": "Descrição"
        }
        
        save_ticket(ticket_data)
        tickets = get_all_tickets()
        ticket_id = tickets[0].id
        
        found = get_ticket_by_id(ticket_id)
        assert found is not None
        assert found.sender == "outro@email.com"

    def test_get_ticket_by_id_not_found(self):
        """Testa busca de ticket inexistente."""
        from src.data.db import get_ticket_by_id
        
        result = get_ticket_by_id(99999)
        assert result is None

    def test_update_ticket_status(self):
        """Testa atualização de status do ticket."""
        from src.data.db import save_ticket, get_all_tickets, update_ticket_status, get_ticket_by_id
        
        ticket_data = {
            "uid": "test_uid_003",
            "sender": "status@test.com",
            "subject": "Teste Status",
            "body": "Corpo"
        }
        
        save_ticket(ticket_data)
        tickets = get_all_tickets()
        ticket_id = tickets[0].id
        
        # Status inicial deve ser "Pendente"
        assert tickets[0].status == "Pendente"
        
        # Atualiza para "Resolvido"
        result = update_ticket_status(ticket_id, "Resolvido")
        assert result is True
        
        # Verifica atualização
        updated = get_ticket_by_id(ticket_id)
        assert updated.status == "Resolvido"

    def test_update_ticket_status_not_found(self):
        """Testa atualização de ticket inexistente."""
        from src.data.db import update_ticket_status
        
        result = update_ticket_status(99999, "Resolvido")
        assert result is False

    def test_ticket_default_values(self):
        """Testa valores default do modelo Ticket."""
        from src.data.db import save_ticket, get_all_tickets
        
        # Ticket mínimo sem campos opcionais
        ticket_data = {
            "uid": "minimal_uid",
            "sender": "min@test.com",
            "subject": "Mínimo",
            "body": "Corpo mínimo"
        }
        
        save_ticket(ticket_data)
        ticket = get_all_tickets()[0]
        
        assert ticket.status == "Pendente"  # Default
        assert ticket.created_at is not None  # Auto-gerado

    def test_delete_ticket_success(self):
        """Testa remoção de ticket com sucesso."""
        from src.data.db import save_ticket, get_all_tickets, delete_ticket
        
        ticket_data = {
            "uid": "delete_uid",
            "sender": "delete@test.com",
            "subject": "Para deletar",
            "body": "Corpo"
        }
        
        save_ticket(ticket_data)
        tickets = get_all_tickets()
        assert len(tickets) == 1
        
        ticket_id = tickets[0].id
        result = delete_ticket(ticket_id)
        
        assert result is True
        assert len(get_all_tickets()) == 0

    def test_delete_ticket_not_found(self):
        """Testa remoção de ticket inexistente."""
        from src.data.db import delete_ticket
        
        result = delete_ticket(99999)
        assert result is False
