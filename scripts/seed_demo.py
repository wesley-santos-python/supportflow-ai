"""
Popula o banco com tickets de exemplo para visualização/demonstração.

Uso:
    python scripts/seed_demo.py

Respeita a DATABASE_URL do .env (use SQLite para um teste rápido, sem Docker).
É idempotente: rodar mais de uma vez não duplica os tickets de demonstração.
"""
import os
import sys
from datetime import datetime, timedelta

# Garante que o pacote `src` seja encontrado ao rodar o script diretamente.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.db import create_ticket, init_db, session_scope

DEMO_TICKETS = [
    {
        "uid": "demo-001",
        "sender": "joao.silva@empresa.com",
        "subject": "Sistema fora do ar - não consigo acessar",
        "body": "Olá, desde manhã não consigo acessar o painel. Aparece erro 500. "
        "Isso está impactando toda a equipe de vendas. Preciso de ajuda urgente!",
        "urgencia": "Alta",
        "categoria": "Técnico",
        "resumo": "Cliente relata erro 500 no painel, impactando a equipe de vendas.",
        "resposta_sugerida": "Olá João, identificamos uma instabilidade e nossa equipe "
        "já está atuando. Em instantes o acesso será normalizado. Obrigado pela paciência.",
        "status": "Em Andamento",
    },
    {
        "uid": "demo-002",
        "sender": "financeiro@loja.com.br",
        "subject": "Dúvida sobre cobrança duplicada na fatura",
        "body": "Identificamos duas cobranças do mesmo valor na fatura deste mês. "
        "Poderiam verificar e estornar a duplicada?",
        "urgencia": "Média",
        "categoria": "Financeiro",
        "resumo": "Cliente aponta cobrança duplicada e solicita estorno.",
        "resposta_sugerida": "Olá! Verificamos a duplicidade e o estorno será processado "
        "em até 3 dias úteis. Pedimos desculpas pelo transtorno.",
        "status": "Pendente",
    },
    {
        "uid": "demo-003",
        "sender": "maria.souza@gmail.com",
        "subject": "Onde está meu pedido #48213?",
        "body": "Comprei há 10 dias e o rastreamento não atualiza desde a semana passada. "
        "Gostaria de saber a previsão de entrega.",
        "urgencia": "Média",
        "categoria": "Logística",
        "resumo": "Cliente questiona atraso e previsão de entrega do pedido #48213.",
        "resposta_sugerida": "Olá Maria! Seu pedido está em trânsito e a nova previsão "
        "de entrega é para amanhã. Enviamos o link de rastreamento atualizado por e-mail.",
        "status": "Pendente",
    },
    {
        "uid": "demo-004",
        "sender": "contato@parceiro.com",
        "subject": "Elogio ao atendimento",
        "body": "Só queria agradecer pelo excelente suporte que recebi ontem. Nota 10!",
        "urgencia": "Baixa",
        "categoria": "Outros",
        "resumo": "Cliente elogia o atendimento recebido.",
        "resposta_sugerida": "Muito obrigado pelo carinho! Ficamos felizes em ajudar. 💙",
        "status": "Resolvido",
    },
    {
        "uid": "demo-005",
        "sender": "ti@corporacao.net",
        "subject": "Falha de integração via API (timeout)",
        "body": "Nossa integração está recebendo timeout intermitente no endpoint /v1/orders. "
        "Acontece em horários de pico. Podem investigar os limites de taxa?",
        "urgencia": "Alta",
        "categoria": "Técnico",
        "resumo": "Timeouts intermitentes na API /v1/orders em horários de pico.",
        "resposta_sugerida": "Olá! Vamos analisar os logs de rate limit do endpoint /v1/orders "
        "e retornamos com um diagnóstico ainda hoje.",
        "status": "Pendente",
    },
]


def main() -> None:
    init_db()
    created = 0
    with session_scope() as db:
        for offset, data in enumerate(DEMO_TICKETS):
            # Espalha as datas de criação para um visual mais realista.
            data = {**data, "created_at": datetime.now() - timedelta(hours=offset * 7)}
            if create_ticket(db, data):
                created += 1
    print(f"✓ {created} ticket(s) de demonstração inserido(s).")
    print("Agora rode:  python main.py  →  http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
